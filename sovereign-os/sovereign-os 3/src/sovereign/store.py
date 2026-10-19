"""Local source record vault.

Source records are evidence. Memory claims are separate, source-linked
interpretations governed by `claims.py` (ADR-0003): created `proposed` and changed
only by explicit, recorded human decisions. A claim reaches a model only through
the Context Compiler (`context.py`, ADR-0004), and only when approved with intact
evidence. Claim support is derived at read time from current evidence, so
correcting a source record immediately stops dependent claims presenting as supported.

Deleting a source record means *forget*: the record, its earlier revisions and
every claim derived from them are removed from the active DB and replaced by
content-free identifier tombstones that block resurrection. Full secure erasure
including backups/WAL is NOT provided.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Iterator, Mapping
from uuid import UUID, uuid4, uuid5

from . import claims as rules

# PRAGMA user_version. 0 = records-only vaults (ADR-0002). 1, 2, 3 = unreleased drafts (c847f9d, 708e9de, 36c9bbc).
SCHEMA_VERSION = 4
EXPORT_SCHEMAS = ("sovereign.v0.records.1", "sovereign.v0.records.2")
# One explicit size policy shared by export, import and restore: anything export produces is restorable.
MAX_BACKUP_BYTES = 128 * 1024 * 1024
MAX_ID, MAX_CONTENT, MAX_SOURCE = 200, 10000, 200
MAX_PAGE = 200   # claims per listing page (pages are complete via the cursor, not capped)
# Ordinary import gives claims deterministic ids in this namespace, so a file can never occupy
# (squat) the id of a genuine claim and block its later trusted restore.
IMPORT_NAMESPACE = UUID("8a6c9a1e-5b7d-4f3e-9d2a-0c1b2e3f4a5b")
# What a claim link pins: everything that identifies the evidence except its revision status.
EVIDENCE_FIELDS = ("id", "content", "source", "sensitivity", "created_at", "supersedes_id")

BASE_SCHEMA = """
    CREATE TABLE IF NOT EXISTS records (
        id TEXT PRIMARY KEY,
        content TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'manual',
        sensitivity TEXT NOT NULL CHECK(sensitivity IN ('private', 'sensitive')),
        status TEXT NOT NULL CHECK(status IN ('active', 'superseded')),
        created_at TEXT NOT NULL,
        supersedes_id TEXT
    );
    CREATE TABLE IF NOT EXISTS tombstones (
        id TEXT PRIMARY KEY,
        deleted_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS ix_records_status ON records(status,created_at);
"""


def _abort(message: str) -> str:
    return f"BEGIN SELECT RAISE(ABORT, '{message}'); END;"


# Records that existed before the claims era (migrated from an ADR-0002 vault, or restored from a
# backup of one) carry legacy = 1. They are preserved exactly as the ADR-0002 restore accepted them:
# within the bounds below, and exempt from the newer lineage rules. Everything written now is
# legacy = 0 and must meet the current bounds. Ordinary import never creates legacy rows.
LEGACY_SCHEMA = """
    ALTER TABLE records ADD COLUMN legacy INTEGER NOT NULL DEFAULT 0 CHECK(legacy IN (0, 1));
    UPDATE records SET legacy = 1;
"""

_ALLOWED = ", ".join(f"'{key}'" for key in rules.transition_keys())
_TERMINAL = ", ".join(f"'{s}'" for s, targets in rules.TRANSITIONS.items() if not targets)
_CLAIM_FORGOTTEN = "EXISTS (SELECT 1 FROM claim_tombstones WHERE id = {})"
_RECORD_FORGOTTEN = "EXISTS (SELECT 1 FROM tombstones WHERE id = {})"

# Version 3: additive only. Existing `records`/`tombstones` rows are untouched.
# These triggers are the storage contract (ADR-0003). They hold for any connection issuing
# INSERT/UPDATE/DELETE, including OR REPLACE / upsert forms (every insert path is checked by a
# BEFORE INSERT trigger, which runs before SQLite's REPLACE deletes), with or without
# PRAGMA foreign_keys/recursive_triggers. They do not hold against schema changes
# (DROP TRIGGER) or direct file edits by a process that already controls the vault file.
CLAIMS_SCHEMA = f"""
    CREATE TABLE claims (
        id TEXT PRIMARY KEY CHECK(typeof(id) = 'text' AND length(id) BETWEEN 1 AND {MAX_ID}),
        text TEXT NOT NULL CHECK(typeof(text) = 'text' AND length(text) BETWEEN 1 AND {rules.MAX_TEXT}),
        origin TEXT NOT NULL CHECK(origin IN ('human', 'model', 'imported')),
        status TEXT NOT NULL CHECK(status IN ('proposed', 'approved', 'rejected', 'contested', 'superseded')),
        created_at TEXT NOT NULL CHECK(typeof(created_at) = 'text'),
        supersedes_id TEXT,
        CHECK(supersedes_id IS NULL OR (typeof(supersedes_id) = 'text' AND length(supersedes_id) BETWEEN 1 AND {MAX_ID}
                                        AND supersedes_id <> id))
    );
    -- No foreign key to records: the link must survive so support can derive as orphaned.
    -- evidence_sha256 pins the exact evidence the claim was made from (NULL = never seen).
    -- No ON DELETE CASCADE anywhere: claim rows are removed only by the forget trigger below.
    CREATE TABLE claim_sources (
        claim_id TEXT NOT NULL REFERENCES claims(id),
        record_id TEXT NOT NULL CHECK(typeof(record_id) = 'text' AND length(record_id) BETWEEN 1 AND {MAX_ID}),
        evidence_sha256 TEXT CHECK(evidence_sha256 IS NULL OR (typeof(evidence_sha256) = 'text' AND length(evidence_sha256) = 64)),
        PRIMARY KEY (claim_id, record_id)
    );
    -- Append-only decision history (the V0 form of MemoryPromotionDecision).
    CREATE TABLE claim_events (
        seq INTEGER PRIMARY KEY AUTOINCREMENT CHECK(seq > 0),
        claim_id TEXT NOT NULL REFERENCES claims(id),
        from_status TEXT,
        to_status TEXT NOT NULL,
        actor TEXT NOT NULL CHECK(actor IN ('human', 'model', 'imported')),
        note TEXT CHECK(note IS NULL OR (typeof(note) = 'text' AND length(note) <= {rules.MAX_NOTE})),
        at TEXT NOT NULL CHECK(typeof(at) = 'text'),
        CHECK((from_status IS NULL) = (to_status = 'proposed')),
        CHECK(from_status IS NULL OR actor = 'human')
    );
    CREATE TABLE claim_tombstones (
        id TEXT PRIMARY KEY CHECK(typeof(id) = 'text' AND length(id) BETWEEN 1 AND {MAX_ID}),
        deleted_at TEXT NOT NULL CHECK(typeof(deleted_at) = 'text')
    );
    CREATE INDEX ix_claims_supersedes ON claims(supersedes_id);
    CREATE INDEX ix_claim_events_claim ON claim_events(claim_id, seq);
    CREATE INDEX ix_claim_sources_record ON claim_sources(record_id);
    CREATE INDEX IF NOT EXISTS ix_records_supersedes ON records(supersedes_id);

    -- Claims: born proposed, never replaced, immutable, never reusing a forgotten id, linear
    -- supersession (a replacement needs an already-superseded or absent predecessor; a claim
    -- cannot appear after its replacement, which also rules out cycles), removed only by forgetting.
    CREATE TRIGGER claims_no_replace BEFORE INSERT ON claims WHEN EXISTS (SELECT 1 FROM claims WHERE id = NEW.id)
    {_abort('claim id already exists; claims are never replaced')}
    CREATE TRIGGER claims_created_proposed BEFORE INSERT ON claims WHEN NEW.status <> 'proposed'
    {_abort('claims must be created as proposed')}
    CREATE TRIGGER claims_not_resurrected BEFORE INSERT ON claims WHEN {_CLAIM_FORGOTTEN.format('NEW.id')}
    {_abort('claim id was forgotten')}
    CREATE TRIGGER claims_linear_supersession BEFORE INSERT ON claims WHEN
        EXISTS (SELECT 1 FROM claims WHERE supersedes_id = NEW.id)
        OR (NEW.supersedes_id IS NOT NULL AND (
            EXISTS (SELECT 1 FROM claims WHERE supersedes_id = NEW.supersedes_id)
            OR EXISTS (SELECT 1 FROM claims WHERE id = NEW.supersedes_id AND status <> 'superseded')))
    {_abort('invalid claim supersession')}
    CREATE TRIGGER claims_immutable BEFORE UPDATE OF id, text, origin, created_at, supersedes_id ON claims
    {_abort('claims are immutable; supersede instead')}
    CREATE TRIGGER claims_status_recorded BEFORE UPDATE OF status ON claims
    WHEN NEW.status IS NOT (SELECT to_status FROM claim_events WHERE claim_id = NEW.id ORDER BY seq DESC LIMIT 1)
      OR (OLD.status IN ({_TERMINAL}) AND NEW.status IS NOT OLD.status)
    {_abort('claim status changes only through a recorded legal event')}
    CREATE TRIGGER claims_removed_only_by_forgetting BEFORE DELETE ON claims WHEN NOT {_CLAIM_FORGOTTEN.format('OLD.id')}
    {_abort('claims are removed only by forgetting (claim tombstone)')}

    -- Evidence links are fixed when the claim's creation event is written, and never cite forgotten evidence.
    CREATE TRIGGER claim_sources_no_replace BEFORE INSERT ON claim_sources
    WHEN EXISTS (SELECT 1 FROM claim_sources WHERE claim_id = NEW.claim_id AND record_id = NEW.record_id)
    {_abort('claim evidence links are never replaced')}
    CREATE TRIGGER claim_sources_fixed_insert BEFORE INSERT ON claim_sources
    WHEN NOT EXISTS (SELECT 1 FROM claims WHERE id = NEW.claim_id)
      OR EXISTS (SELECT 1 FROM claim_events WHERE claim_id = NEW.claim_id)
      OR (SELECT count(*) FROM claim_sources WHERE claim_id = NEW.claim_id) >= {rules.MAX_SOURCES}
      OR {_RECORD_FORGOTTEN.format('NEW.record_id')}
    {_abort('claim evidence links are fixed at creation and cannot cite forgotten evidence')}
    CREATE TRIGGER claim_sources_fixed_update BEFORE UPDATE ON claim_sources
    {_abort('claim evidence links are fixed at creation')}
    CREATE TRIGGER claim_sources_fixed_delete BEFORE DELETE ON claim_sources WHEN NOT {_CLAIM_FORGOTTEN.format('OLD.claim_id')}
    {_abort('claim evidence links are fixed at creation')}

    -- History: one creation event by the claim's origin, then legal human transitions from the
    -- *current* status (compare-and-set: a stale concurrent decision aborts). Inserting an event is
    -- the only way to change a claim's status; events are never replaced, edited or deleted.
    CREATE TRIGGER claim_events_no_replace BEFORE INSERT ON claim_events WHEN EXISTS (SELECT 1 FROM claim_events WHERE seq = NEW.seq)
    {_abort('claim history is never replaced')}
    CREATE TRIGGER claim_events_creation BEFORE INSERT ON claim_events WHEN NEW.from_status IS NULL AND (
        NOT EXISTS (SELECT 1 FROM claims WHERE id = NEW.claim_id AND status = 'proposed' AND origin = NEW.actor)
        OR EXISTS (SELECT 1 FROM claim_events WHERE claim_id = NEW.claim_id)
        OR NOT EXISTS (SELECT 1 FROM claim_sources WHERE claim_id = NEW.claim_id))
    {_abort('invalid claim creation event')}
    CREATE TRIGGER claim_events_transition BEFORE INSERT ON claim_events WHEN NEW.from_status IS NOT NULL AND (
        NEW.actor <> 'human'
        OR (NEW.from_status || '>' || NEW.to_status) NOT IN ({_ALLOWED})
        OR NEW.from_status IS NOT (SELECT status FROM claims WHERE id = NEW.claim_id)
        OR NEW.from_status IS NOT (SELECT to_status FROM claim_events WHERE claim_id = NEW.claim_id ORDER BY seq DESC LIMIT 1))
    {_abort('illegal or stale claim transition')}
    CREATE TRIGGER claim_events_apply AFTER INSERT ON claim_events WHEN NEW.from_status IS NOT NULL
    BEGIN UPDATE claims SET status = NEW.to_status WHERE id = NEW.claim_id; END;
    CREATE TRIGGER claim_events_no_update BEFORE UPDATE ON claim_events {_abort('claim history is append-only')}
    CREATE TRIGGER claim_events_no_delete BEFORE DELETE ON claim_events WHEN NOT {_CLAIM_FORGOTTEN.format('OLD.claim_id')}
    {_abort('claim history is append-only')}

    -- Forgetting a claim = writing its tombstone; the claim, links and history go with it.
    CREATE TRIGGER claim_tombstones_idempotent BEFORE INSERT ON claim_tombstones WHEN {_CLAIM_FORGOTTEN.format('NEW.id')}
    BEGIN SELECT RAISE(IGNORE); END;
    CREATE TRIGGER claim_tombstones_forget AFTER INSERT ON claim_tombstones BEGIN
        DELETE FROM claim_events WHERE claim_id = NEW.id;
        DELETE FROM claim_sources WHERE claim_id = NEW.id;
        DELETE FROM claims WHERE id = NEW.id;
    END;
    CREATE TRIGGER claim_tombstones_no_update BEFORE UPDATE ON claim_tombstones {_abort('tombstones are permanent')}
    CREATE TRIGGER claim_tombstones_no_delete BEFORE DELETE ON claim_tombstones {_abort('tombstones are permanent')}

    -- Evidence: insert-only identity (never replaced or resurrected, never introduced under an id that
    -- claims already cite or after its own correction), immutable apart from being superseded by an
    -- inserted correction, strictly linear lineage, removed only by forgetting. Legacy rows keep the
    -- ADR-0002 bounds and are exempt from the lineage rules (they are preserved, never re-shaped).
    CREATE TRIGGER records_well_formed BEFORE INSERT ON records WHEN
        typeof(NEW.id) <> 'text' OR typeof(NEW.content) <> 'text' OR length(NEW.content) > {MAX_CONTENT}
        OR typeof(NEW.source) <> 'text' OR typeof(NEW.created_at) <> 'text'
        OR (NEW.supersedes_id IS NOT NULL AND typeof(NEW.supersedes_id) <> 'text')
        OR (NEW.legacy = 0 AND (length(NEW.id) NOT BETWEEN 1 AND {MAX_ID} OR length(NEW.content) < 1
                                OR length(NEW.source) NOT BETWEEN 1 AND {MAX_SOURCE}
                                OR (NEW.supersedes_id IS NOT NULL AND length(NEW.supersedes_id) NOT BETWEEN 1 AND {MAX_ID})))
    {_abort('malformed source record')}
    CREATE TRIGGER records_no_replace BEFORE INSERT ON records WHEN EXISTS (SELECT 1 FROM records WHERE id = NEW.id)
    {_abort('record id already exists; evidence is never replaced')}
    CREATE TRIGGER records_not_resurrected BEFORE INSERT ON records WHEN {_RECORD_FORGOTTEN.format('NEW.id')}
    {_abort('record id was forgotten')}
    CREATE TRIGGER records_not_after_claims BEFORE INSERT ON records
    WHEN EXISTS (SELECT 1 FROM claim_sources WHERE record_id = NEW.id)
    {_abort('evidence cannot appear after claims that cite it')}
    -- Current rows: strictly linear and built oldest-first. Legacy rows may keep ADR-0002 lineage
    -- anomalies, but only among legacy rows: a legacy row never supersedes a current row, never joins
    -- a lineage that already has a current correction, and never appears after a current correction.
    CREATE TRIGGER records_not_after_correction BEFORE INSERT ON records
    WHEN EXISTS (SELECT 1 FROM records s WHERE s.supersedes_id = NEW.id AND (NEW.legacy = 0 OR s.legacy = 0))
    {_abort('a record cannot appear after its correction')}
    CREATE TRIGGER records_linear_lineage BEFORE INSERT ON records WHEN NEW.supersedes_id IS NOT NULL AND (
        (NEW.legacy = 0 AND (NEW.supersedes_id = NEW.id
                             OR EXISTS (SELECT 1 FROM records s WHERE s.supersedes_id = NEW.supersedes_id)))
        OR (NEW.legacy = 1 AND (EXISTS (SELECT 1 FROM records s WHERE s.supersedes_id = NEW.supersedes_id AND s.legacy = 0)
                                OR EXISTS (SELECT 1 FROM records p WHERE p.id = NEW.supersedes_id AND p.legacy = 0))))
    {_abort('a record is corrected at most once and never by itself')}
    CREATE TRIGGER records_correction_supersedes AFTER INSERT ON records WHEN NEW.legacy = 0 AND NEW.supersedes_id IS NOT NULL
    BEGIN UPDATE records SET status = 'superseded' WHERE id = NEW.supersedes_id AND status = 'active'; END;
    CREATE TRIGGER records_immutable BEFORE UPDATE OF id, content, source, sensitivity, created_at, supersedes_id, legacy ON records
    {_abort('source records are immutable evidence')}
    CREATE TRIGGER records_superseded_only_by_correction BEFORE UPDATE OF status ON records
    WHEN NOT (OLD.status = 'active' AND NEW.status = 'superseded'
              AND EXISTS (SELECT 1 FROM records WHERE supersedes_id = OLD.id))
    {_abort('evidence is superseded only by inserting its correction')}
    CREATE TRIGGER records_removed_only_by_forgetting BEFORE DELETE ON records WHEN NOT {_RECORD_FORGOTTEN.format('OLD.id')}
    {_abort('records are removed only by forgetting (tombstone)')}

    -- Forgetting evidence = writing its tombstone: the record and every claim citing it go with it.
    CREATE TRIGGER tombstones_well_formed BEFORE INSERT ON tombstones
    WHEN typeof(NEW.id) <> 'text' OR typeof(NEW.deleted_at) <> 'text'
    {_abort('malformed tombstone')}
    CREATE TRIGGER tombstones_idempotent BEFORE INSERT ON tombstones WHEN {_RECORD_FORGOTTEN.format('NEW.id')}
    BEGIN SELECT RAISE(IGNORE); END;
    CREATE TRIGGER tombstones_forget AFTER INSERT ON tombstones BEGIN
        INSERT INTO claim_tombstones(id, deleted_at)
            SELECT DISTINCT claim_id, NEW.deleted_at FROM claim_sources WHERE record_id = NEW.id;
        DELETE FROM records WHERE id = NEW.id;
    END;
    CREATE TRIGGER tombstones_no_update BEFORE UPDATE ON tombstones {_abort('tombstones are permanent')}
    CREATE TRIGGER tombstones_no_delete BEFORE DELETE ON tombstones {_abort('tombstones are permanent')}
"""


class ForgetImpactChanged(Exception):
    """The effect of a Forget changed between its preview and its execution."""


def evidence_hash(record: Mapping) -> str:
    """Fingerprint of a record's identity: id, content, provenance, sensitivity, time and lineage."""
    canonical = json.dumps([record[k] for k in EVIDENCE_FIELDS], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _encode_cursor(created_at: str, claim_id: str) -> str:
    return base64.urlsafe_b64encode(json.dumps([created_at, claim_id]).encode("utf-8")).decode("ascii")


def _decode_cursor(cursor: str) -> tuple[str, str]:
    try:
        key = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")))
    except (ValueError, UnicodeError):
        raise ValueError("Invalid cursor.") from None
    if not (isinstance(key, list) and len(key) == 2 and all(isinstance(k, str) for k in key)):
        raise ValueError("Invalid cursor.")
    return key[0], key[1]


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _is_text(value, low: int = 0, high: int | None = None) -> bool:
    return isinstance(value, str) and low <= len(value) and (high is None or len(value) <= high)


def _lineage_order(items: list[dict], final_status) -> list[dict]:
    """Validate a payload's supersession lineage and order it predecessors-first.

    V0 lineage is linear: no self-supersession, at most one successor per item, no cycles,
    and an item superseded by another item in the same payload must itself be `superseded`.
    """
    by_id: dict[str, dict] = {}
    for item in items:
        if item["id"] in by_id:
            raise ValueError("Duplicate id in import.")
        by_id[item["id"]] = item
    successor: dict[str, str] = {}
    for item in items:
        predecessor = item["supersedes_id"]
        if predecessor is None:
            continue
        if predecessor == item["id"]:
            raise ValueError("Self-supersession in import.")
        if predecessor in successor:
            raise ValueError("Multiple successors for one item in import.")
        successor[predecessor] = item["id"]
        if predecessor in by_id and final_status(by_id[predecessor]) != "superseded":
            raise ValueError("An item with a successor in the import must be superseded.")
    ordered = []
    for item in items:
        if item["supersedes_id"] in by_id:
            continue  # not a chain start
        node = item
        while node is not None:
            ordered.append(node)
            node = by_id.get(successor.get(node["id"]))
    if len(ordered) != len(items):
        raise ValueError("Cyclic supersession in import.")
    return ordered


class Vault:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    def _migrate(self) -> None:
        db = sqlite3.connect(self.path, isolation_level=None, timeout=10)
        try:
            db.execute("BEGIN IMMEDIATE")  # serialise concurrent first opens
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise RuntimeError(f"Vault schema {version} is newer than this software supports ({SCHEMA_VERSION}).")
            if version == SCHEMA_VERSION:
                db.execute("COMMIT")
                return
            if version != 0 or db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='claims'").fetchone():
                # Only unreleased benchmark drafts created these; refuse rather than guess.
                raise RuntimeError("Vault was created by a pre-release claims build; export records and restore into a new vault.")
            # One transaction: either the vault is fully at the new version or unchanged.
            for statement in _statements(BASE_SCHEMA + LEGACY_SCHEMA + CLAIMS_SCHEMA):
                db.execute(statement)
            db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            db.execute("COMMIT")
        except Exception:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    @contextmanager
    def connection(self, write: bool = False) -> Iterator[sqlite3.Connection]:
        """One SQLite transaction per operation.

        Writes take the write lock up front (BEGIN IMMEDIATE) so read-check-write is atomic
        across processes; reads run in one read transaction, so a multi-query read such as an
        export observes a single consistent snapshot rather than a mixture of states.
        """
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA secure_delete=ON")
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        try:
            yield db
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    @staticmethod
    def _exists(db: sqlite3.Connection, sql: str, *args) -> bool:
        return db.execute(sql, args).fetchone() is not None

    @staticmethod
    def _record(row: sqlite3.Row) -> dict:
        return dict(row)

    def add(self, content: str, sensitivity: str = "private", supersedes_id: str | None = None) -> dict:
        content = content.strip()
        if not content or len(content) > MAX_CONTENT:
            raise ValueError("Text must be between 1 and 10,000 characters.")
        if sensitivity not in {"private", "sensitive"}:
            raise ValueError("Invalid sensitivity.")
        record_id = str(uuid4())
        with self.connection(write=True) as db:
            if supersedes_id and not self._exists(db, "SELECT 1 FROM records WHERE id=? AND status='active'", supersedes_id):
                raise KeyError("Record to correct was not found or is already superseded.")
            if supersedes_id and (len(supersedes_id) > MAX_ID
                                  or self._exists(db, "SELECT 1 FROM records WHERE supersedes_id=?", supersedes_id)):
                # A new correction obeys the current rules even for a legacy predecessor.
                raise ValueError("This record cannot be corrected: its legacy id or lineage is outside current V0 rules.")
            # Inserting the correction is what supersedes its predecessor (storage trigger).
            db.execute("INSERT INTO records(id,content,sensitivity,status,created_at,supersedes_id) VALUES(?,?,?,?,?,?)",
                       (record_id, content, sensitivity, "active", stamp(), supersedes_id))
            return self._record(db.execute("SELECT * FROM records WHERE id=?", (record_id,)).fetchone())

    def get(self, record_id: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM records WHERE id=? AND status='active'", (record_id,)).fetchone()
            return self._record(row) if row else None

    def search(self, q: str = "", limit: int = 50) -> list[dict]:
        with self.connection() as db:
            if q.strip():
                # Local substring retrieval only; first milestone favors inspectability.
                rows = db.execute(
                    "SELECT * FROM records WHERE status='active' AND instr(lower(content),lower(?))>0 ORDER BY created_at DESC,id DESC LIMIT ?",
                    (q.strip(), min(limit, 100)),
                ).fetchall()
            else:
                rows = db.execute("SELECT * FROM records WHERE status='active' ORDER BY created_at DESC,id DESC LIMIT ?", (min(limit, 100),)).fetchall()
            return [self._record(row) for row in rows]

    def context_candidates(self, score, pinned_ids: list[str], limit: int) -> dict:
        """Local candidate retrieval for the Context Compiler (ADR-0004), in ONE read snapshot.

        `score(text) -> (score, matched_terms)` is the compiler's lexical relevance. Returns how each
        pinned id resolves (record | forgotten | claim | unknown); candidate records (the pinned ones,
        plus the `limit` best-matching active or superseded records); and candidate claims (the `limit`
        best-matching claims, plus up to `limit` that cite a candidate record), each with its derived
        support and the state and sensitivity of every source. Facts only: the compiler decides.
        Read-only. Forgotten content cannot appear: Forget removes it and tombstones hold ids only.
        """
        def best(rows: list[dict]) -> list[dict]:
            rows.sort(key=lambda r: r["id"])
            rows.sort(key=lambda r: r["created_at"], reverse=True)
            rows.sort(key=lambda r: -r["score"])
            return rows[:limit]

        with self.connection() as db:
            pinned = []
            for pid in pinned_ids:
                if self._exists(db, "SELECT 1 FROM records WHERE id=?", pid):
                    kind = "record"
                elif self._exists(db, "SELECT 1 FROM tombstones WHERE id=?", pid):
                    kind = "forgotten"
                elif (self._exists(db, "SELECT 1 FROM claims WHERE id=?", pid)
                      or self._exists(db, "SELECT 1 FROM claim_tombstones WHERE id=?", pid)):
                    kind = "claim"
                else:
                    kind = "unknown"
                pinned.append({"id": pid, "kind": kind})
            pinned_records = [p["id"] for p in pinned if p["kind"] == "record"]

            matches = []
            for row in db.execute("SELECT id, content, created_at FROM records"):
                points, _ = score(row["content"])
                if points:
                    matches.append({"id": row["id"], "created_at": row["created_at"], "score": points})
            records = []
            for rid in dict.fromkeys(pinned_records + [m["id"] for m in best(matches)]):
                row = db.execute("SELECT * FROM records WHERE id=?", (rid,)).fetchone()
                points, terms = score(row["content"])
                records.append({**{k: row[k] for k in ("id", "content", "sensitivity", "status", "created_at")},
                                "score": points, "matched_terms": terms, "pinned": rid in pinned_records})

            claim_matches = []
            for row in db.execute("SELECT id, text, created_at FROM claims"):
                points, _ = score(row["text"])
                if points:
                    claim_matches.append({"id": row["id"], "created_at": row["created_at"], "score": points})
            linked = []
            if records:
                marks = ",".join("?" * len(records))
                linked = [{"id": r["id"], "created_at": r["created_at"], "score": 0} for r in db.execute(
                    f"""SELECT DISTINCT c.id, c.created_at FROM claims c JOIN claim_sources s ON s.claim_id = c.id
                        WHERE s.record_id IN ({marks})""", [r["id"] for r in records])]
            claims = []
            for cid in dict.fromkeys([m["id"] for m in best(claim_matches)] + [m["id"] for m in best(linked)]):
                claim = self._get_claim(db, cid)
                points, terms = score(claim["text"])
                claims.append({**{k: claim[k] for k in ("id", "text", "origin", "status", "created_at", "support", "source_ids")},
                               "sources": [{"id": s["id"], "state": s["state"], "sensitivity": s["sensitivity"]}
                                           for s in claim["sources"]],
                               "score": points, "matched_terms": terms})
            return {"pinned": pinned, "records": records, "claims": claims,
                    "matched": {"records": len(matches), "claims": len(claim_matches), "claims_linked": len(linked)}}

    def _forget_plan(self, db: sqlite3.Connection, record_id: str) -> dict | None:
        """The exact effect of forgetting `record_id` in the current state; None if it does not exist.

        This is the single source of truth for Forget: the preview returns it and `delete` executes
        it, so what the user confirms and what the vault does cannot drift apart. Forget covers the
        record, every earlier revision still present (lineage walks backward), and every claim that
        cites any of them (the storage trigger forgets exactly those claims).
        """
        if not self._exists(db, "SELECT 1 FROM records WHERE id=?", record_id):
            return None
        ids = [record_id]
        while True:
            previous = db.execute("SELECT r.id FROM records r JOIN records s ON s.supersedes_id = r.id WHERE s.id=?",
                                  (ids[-1],)).fetchone()
            if previous is None or previous["id"] in ids:
                break
            ids.append(previous["id"])
        marks = ",".join("?" * len(ids))
        claim_rows = db.execute(f"""SELECT * FROM claims WHERE id IN (SELECT claim_id FROM claim_sources WHERE record_id IN ({marks}))
                                    ORDER BY created_at DESC, id DESC""", ids).fetchall()
        claims = [self._claim(db, row) for row in claim_rows]
        # The token covers what is removed *and* its authority: a decision taken after the preview
        # (e.g. approving a listed claim) also invalidates the confirmation.
        impact = hashlib.sha256(json.dumps([sorted(ids), sorted([c["id"], c["status"], c["authoritative"]] for c in claims)])
                                .encode()).hexdigest()
        return {"record_id": record_id, "impact_token": impact,
                "records_forgotten": len(ids), "claims_forgotten": len(claims),
                "records": [self._record(db.execute("SELECT * FROM records WHERE id=?", (rid,)).fetchone()) for rid in ids],
                "claims": [{k: c[k] for k in ("id", "text", "status", "origin", "authoritative", "source_ids")} for c in claims]}

    def forget_preview(self, record_id: str) -> dict | None:
        """What Forget would remove right now (read-only)."""
        with self.connection() as db:
            return self._forget_plan(db, record_id)

    def delete(self, record_id: str, expected_impact: str | None = None) -> dict | None:
        """Forget a source record, its earlier revisions and all dependent claims.

        With `expected_impact` (the preview's token) the operation refuses to run if its effect has
        changed since the preview, so a confirmation can never understate what is removed.
        """
        with self.connection(write=True) as db:
            plan = self._forget_plan(db, record_id)
            if plan is None:
                return None
            if expected_impact is not None and expected_impact != plan["impact_token"]:
                raise ForgetImpactChanged("What Forget would remove changed since the preview; review it again.")
            claims_before = db.execute("SELECT count(*) FROM claims").fetchone()[0]
            ids = [r["id"] for r in plan["records"]]
            # The storage trigger removes each record and forgets every claim citing it.
            db.executemany("INSERT INTO tombstones (id,deleted_at) VALUES (?,?)", [(rid, stamp()) for rid in ids])
            removed = claims_before - db.execute("SELECT count(*) FROM claims").fetchone()[0]
            survivors = [c["id"] for c in plan["claims"] if self._exists(db, "SELECT 1 FROM claims WHERE id=?", c["id"])]
            if removed != plan["claims_forgotten"] or survivors:
                raise RuntimeError("Forget effect diverged from its plan; nothing was changed.")   # rolls back
            # Do not claim backup/WAL/forensic secure deletion here.
            return {"records_forgotten": len(ids), "claims_forgotten": removed,
                    "record_ids": ids, "claim_ids": [c["id"] for c in plan["claims"]]}

    # --- Memory claims -----------------------------------------------------

    def _claim(self, db: sqlite3.Connection, row: sqlite3.Row) -> dict:
        claim = dict(row)
        links = db.execute("SELECT record_id, evidence_sha256 FROM claim_sources WHERE claim_id=? ORDER BY record_id",
                           (claim["id"],)).fetchall()
        claim["source_ids"] = [link["record_id"] for link in links]
        claim["source_hashes"] = {link["record_id"]: link["evidence_sha256"] for link in links}
        sources = []
        for link in links:
            rid = link["record_id"]
            rec = db.execute("SELECT * FROM records WHERE id=?", (rid,)).fetchone()
            if rec is None:
                sources.append({"id": rid, "state": "missing", "content": None, "sensitivity": None})
            elif link["evidence_sha256"] != evidence_hash(rec):
                # Not the evidence this claim was made from (different identity, or never seen at link time).
                sources.append({"id": rid, "state": "unverified", "content": rec["content"], "sensitivity": rec["sensitivity"]})
            else:
                sources.append({"id": rid, "state": rec["status"], "content": rec["content"], "sensitivity": rec["sensitivity"]})
        claim["sources"] = sources
        # Support is derived from current evidence, never stored, so it cannot drift.
        claim["support"] = rules.support_of([s["state"] for s in sources])
        claim["authoritative"] = rules.is_authoritative(claim["status"], claim["support"])
        claim["history"] = [dict(e) for e in db.execute(
            "SELECT from_status,to_status,actor,note,at FROM claim_events WHERE claim_id=? ORDER BY seq", (claim["id"],))]
        claim["superseded_by"] = next((r["id"] for r in db.execute(
            "SELECT id FROM claims WHERE supersedes_id=?", (claim["id"],))), None)
        return claim

    def _get_claim(self, db: sqlite3.Connection, claim_id: str) -> dict:
        row = db.execute("SELECT * FROM claims WHERE id=?", (claim_id,)).fetchone()
        if row is None:
            raise KeyError("Claim not found.")
        return self._claim(db, row)

    @staticmethod
    def _validate_new(text: str, source_ids: list[str], origin: str) -> str:
        text = text.strip()
        if not text or len(text) > rules.MAX_TEXT:
            raise ValueError("Claim text must be between 1 and 2,000 characters.")
        if origin not in rules.ORIGINS:
            raise ValueError("Invalid claim origin.")
        if not source_ids or len(source_ids) > rules.MAX_SOURCES or len(set(source_ids)) != len(source_ids):
            raise ValueError("A claim needs 1-8 distinct source record IDs.")
        if not all(1 <= len(rid) <= MAX_ID for rid in source_ids):
            raise ValueError("A claim cannot cite a record whose (legacy) id is outside current V0 bounds.")
        return text

    def _insert_claim(self, db, claim_id: str, text: str, source_hashes: dict[str, str | None], origin: str,
                      supersedes_id: str | None, created_at: str, history: list[dict]) -> None:
        """Insert a claim and its fixed links, then write its history through the lifecycle triggers."""
        db.execute("INSERT INTO claims(id,text,origin,status,created_at,supersedes_id) VALUES (?,?,?,'proposed',?,?)",
                   (claim_id, text, origin, created_at, supersedes_id))
        db.executemany("INSERT INTO claim_sources(claim_id,record_id,evidence_sha256) VALUES (?,?,?)",
                       [(claim_id, rid, digest) for rid, digest in source_hashes.items()])
        if history:
            first = history[0]
            db.execute("INSERT INTO claim_events(claim_id,from_status,to_status,actor,note,at) VALUES (?,NULL,'proposed',?,?,?)",
                       (claim_id, origin, first.get("note"), first["at"]))
            for event in history[1:]:
                self._record_transition(db, claim_id, event["from_status"], event["to_status"], event.get("note"), event["at"])

    def _new_claim(self, db, text: str, source_ids: list[str], origin: str, supersedes_id: str | None) -> str:
        hashes = {}
        for rid in source_ids:
            rec = db.execute("SELECT * FROM records WHERE id=? AND status='active'", (rid,)).fetchone()
            if rec is None:
                raise ValueError(f"Source record missing or superseded: {rid}")
            hashes[rid] = evidence_hash(rec)
        claim_id, now = str(uuid4()), stamp()
        self._insert_claim(db, claim_id, text, hashes, origin, supersedes_id, now, [{"at": now}])
        return claim_id

    @staticmethod
    def _record_transition(db, claim_id: str, current: str, target: str, note: str | None, at: str) -> None:
        """Append a human decision. The storage trigger applies it only if `current` is still current."""
        try:
            db.execute("INSERT INTO claim_events(claim_id,from_status,to_status,actor,note,at) VALUES (?,?,?,'human',?,?)",
                       (claim_id, current, target, note, at))
        except sqlite3.IntegrityError as exc:
            raise rules.TransitionError(f"Claim changed or transition not allowed: {exc}") from None

    def add_claim(self, text: str, source_ids: list[str], origin: str = "human") -> dict:
        """Create a claim. Always `proposed`; there is deliberately no status argument.

        `origin` is set by the caller inside the server: the HTTP API always passes
        `human`; a future internal model-extraction path would pass `model`.
        """
        text = self._validate_new(text, source_ids, origin)
        with self.connection(write=True) as db:
            return self._get_claim(db, self._new_claim(db, text, source_ids, origin, None))

    def claims_page(self, status: str | None = None, limit: int = 100, cursor: str | None = None) -> dict:
        """One page of claims, newest first, with an opaque keyset cursor for the next page.

        The order (created_at DESC, id DESC) is total and deterministic, and the cursor is the last
        row's key, so paging never repeats a claim and reaches every claim that exists throughout
        the paging. Claims added meanwhile appear at their own place in the order (new ones before
        the first page) and are seen on refresh.
        """
        if not 1 <= limit <= MAX_PAGE:
            raise ValueError(f"limit must be between 1 and {MAX_PAGE}.")
        where, args = [], []
        if status:
            where.append("status = ?"); args.append(status)
        if cursor:
            where.append("(created_at, id) < (?, ?)"); args.extend(_decode_cursor(cursor))
        sql = ("SELECT * FROM claims" + (" WHERE " + " AND ".join(where) if where else "")
               + " ORDER BY created_at DESC, id DESC LIMIT ?")
        with self.connection() as db:
            rows = db.execute(sql, (*args, limit + 1)).fetchall()
            page = rows[:limit]
            more = len(rows) > limit
            return {"claims": [self._claim(db, row) for row in page],
                    "next_cursor": _encode_cursor(page[-1]["created_at"], page[-1]["id"]) if more else None}

    def list_claims(self, status: str | None = None, limit: int | None = None) -> list[dict]:
        """Every claim (or the newest `limit`), newest first. HTTP clients page with `claims_page`."""
        with self.connection() as db:
            where, args = ("WHERE status=?", [status]) if status else ("", [])
            tail, extra = ("LIMIT ?", [limit]) if limit is not None else ("", [])
            rows = db.execute(f"SELECT * FROM claims {where} ORDER BY created_at DESC,id DESC {tail}", (*args, *extra))
            return [self._claim(db, row) for row in rows.fetchall()]

    def transition_claim(self, claim_id: str, target: str, note: str | None = None,
                         expected_status: str | None = None) -> dict:
        """Explicit human decision: approve, reject or contest. Recorded in claim history.

        `expected_status` (optional) makes the caller's view part of the compare-and-set.
        """
        if target not in ("approved", "rejected", "contested"):
            raise ValueError("Use supersede to replace a claim.")
        if note is not None and len(note) > rules.MAX_NOTE:
            raise ValueError("Note too long.")
        with self.connection(write=True) as db:
            claim = self._get_claim(db, claim_id)
            if expected_status is not None and claim["status"] != expected_status:
                raise rules.TransitionError(f"Claim is now {claim['status']}, not {expected_status}.")
            rules.check_transition(claim["status"], target, claim["support"])
            self._record_transition(db, claim_id, claim["status"], target, note, stamp())
            return self._get_claim(db, claim_id)

    def supersede_claim(self, claim_id: str, text: str, source_ids: list[str], note: str | None = None,
                        expected_status: str | None = None) -> dict:
        """Human correction: the old claim becomes `superseded`; its replacement starts `proposed`."""
        text = self._validate_new(text, source_ids, "human")
        if note is not None and len(note) > rules.MAX_NOTE:
            raise ValueError("Note too long.")
        with self.connection(write=True) as db:
            old = self._get_claim(db, claim_id)
            if expected_status is not None and old["status"] != expected_status:
                raise rules.TransitionError(f"Claim is now {old['status']}, not {expected_status}.")
            rules.check_transition(old["status"], "superseded")
            # Supersede first: storage only accepts a replacement whose predecessor is already superseded.
            self._record_transition(db, claim_id, old["status"], "superseded", note, stamp())
            new_id = self._new_claim(db, text, source_ids, "human", claim_id)
            return {"superseded": self._get_claim(db, claim_id), "replacement": self._get_claim(db, new_id)}

    def delete_claim(self, claim_id: str) -> bool:
        """Forget a claim: its tombstone removes the claim, its links and its history."""
        with self.connection(write=True) as db:
            if not self._exists(db, "SELECT 1 FROM claims WHERE id=?", claim_id):
                return False
            db.execute("INSERT INTO claim_tombstones(id,deleted_at) VALUES (?,?)", (claim_id, stamp()))
            return True

    # --- Portability ----------------------------------------------------------

    def export(self) -> dict:
        """A single-snapshot export (one read transaction), restorable by this software version."""
        keys = ("id", "text", "origin", "status", "created_at", "supersedes_id", "source_ids", "source_hashes", "history")
        with self.connection() as db:
            rows = db.execute("SELECT * FROM records ORDER BY created_at,id").fetchall()
            tombs = db.execute("SELECT * FROM tombstones ORDER BY deleted_at,id").fetchall()
            claim_rows = db.execute("SELECT * FROM claims ORDER BY created_at,id").fetchall()
            claims = [{k: c[k] for k in keys} for c in (self._claim(db, r) for r in claim_rows)]
            claim_tombs = db.execute("SELECT * FROM claim_tombstones ORDER BY deleted_at,id").fetchall()
            return {"schema": "sovereign.v0.records.2", "exported_at": stamp(),
                    "records": [dict(r) for r in rows], "tombstones": [dict(t) for t in tombs],
                    "claims": claims, "claim_tombstones": [dict(t) for t in claim_tombs]}

    @staticmethod
    def _parse(payload: dict, trusted: bool) -> tuple[list, list, list, list]:
        """Validate a backup/import payload against the same rules storage enforces.

        Returns normalised records and claims ordered predecessors-first. There is no count
        limit; size is bounded once, by MAX_BACKUP_BYTES at the HTTP boundary and on export.

        Records flagged `legacy` (pre-claims ADR-0002 data) are accepted only by a *trusted*
        restore, under the ADR-0002 bounds and without the newer lineage rules, and come first so
        they are preserved exactly. Ordinary import ignores the flag: every record it accepts meets
        the current rules, so legacy compatibility cannot be used to forge new malformed state.
        """
        if not isinstance(payload, dict) or payload.get("schema") not in EXPORT_SCHEMAS:
            raise ValueError("Unsupported export schema.")
        raw_records, tombs = payload.get("records"), payload.get("tombstones")
        raw_claims, claim_tombs = payload.get("claims", []), payload.get("claim_tombstones", [])
        for items in (raw_records, tombs, raw_claims, claim_tombs):
            if not isinstance(items, list):
                raise ValueError("Invalid export lists.")
        for tomb in tombs:
            # Record tombstones accept any text id, as storage does: ADR-0002 accepted record ids of any
            # length, and forgetting such a legacy record writes a tombstone with that id.
            if not isinstance(tomb, dict) or not _is_text(tomb.get("id")) or not _is_text(tomb.get("deleted_at")):
                raise ValueError("Invalid tombstone in import.")
        for tomb in claim_tombs:
            # Claim ids are always 1-MAX_ID, and so are claim tombstones (storage CHECK).
            if not isinstance(tomb, dict) or not _is_text(tomb.get("id"), 1, MAX_ID) or not _is_text(tomb.get("deleted_at")):
                raise ValueError("Invalid tombstone in import.")
        records = []
        for row in raw_records:
            if not isinstance(row, dict):
                raise ValueError("Invalid record in import.")
            flagged = row.get("legacy") in (True, 1)
            record = {"id": row.get("id"), "content": row.get("content"), "source": row.get("source", "manual"),
                      "sensitivity": row.get("sensitivity"), "status": row.get("status"),
                      "created_at": row.get("created_at"), "supersedes_id": row.get("supersedes_id"),
                      "legacy": 1 if trusted and flagged else 0}
            common = (record["sensitivity"] in ("private", "sensitive") and record["status"] in ("active", "superseded")
                      and _is_text(record["created_at"]))
            if record["legacy"]:   # ADR-0002 bounds: what its restore accepted and migration preserved
                valid = (common and _is_text(record["id"]) and _is_text(record["content"], 0, MAX_CONTENT)
                         and _is_text(record["source"]) and (record["supersedes_id"] is None or _is_text(record["supersedes_id"])))
            else:
                valid = (common and _is_text(record["id"], 1, MAX_ID) and _is_text(record["content"], 1, MAX_CONTENT)
                         and _is_text(record["source"], 1, MAX_SOURCE)
                         and (record["supersedes_id"] is None or _is_text(record["supersedes_id"], 1, MAX_ID)))
            if not valid:
                raise ValueError("Legacy record outside current V0 bounds: only a trusted restore of your own backup accepts it."
                                 if flagged and not trusted else "Invalid record in import.")
            records.append(record)
        claims = []
        for row in raw_claims:
            if not isinstance(row, dict):
                raise ValueError("Invalid claim in import.")
            claim = {k: row.get(k) for k in ("id", "text", "origin", "status", "created_at", "supersedes_id", "source_ids")}
            claim["history"] = row.get("history", [])
            source_ids, hashes = claim["source_ids"], row.get("source_hashes", {})
            if (not _is_text(claim["id"], 1, MAX_ID) or not _is_text(claim["text"], 1, rules.MAX_TEXT)
                    or claim["origin"] not in rules.ORIGINS or claim["status"] not in rules.STATUSES
                    or not _is_text(claim["created_at"])
                    or not (claim["supersedes_id"] is None or _is_text(claim["supersedes_id"], 1, MAX_ID))
                    or claim["supersedes_id"] == claim["id"]
                    or not isinstance(source_ids, list) or len(source_ids) > rules.MAX_SOURCES
                    or not all(_is_text(r, 1, MAX_ID) for r in source_ids) or len(set(source_ids)) != len(source_ids)):
                raise ValueError("Invalid claim in import.")
            if (not isinstance(hashes, dict) or not set(hashes) <= set(source_ids)
                    or not all(h is None or _is_text(h, 64, 64) for h in hashes.values())):
                raise ValueError("Invalid claim evidence hashes in import.")
            claim["source_hashes"] = {rid: hashes.get(rid) for rid in source_ids}
            if trusted:
                rules.validate_history(claim["history"], claim["origin"], claim["status"])
                if claim["history"] and not source_ids:
                    raise ValueError("A claim with a recorded history needs evidence links.")
            claims.append(claim)
        if len({r["id"] for r in records}) != len(records):
            raise ValueError("Duplicate id in import.")
        legacy_rows = [r for r in records if r["legacy"]]   # preserved exactly, in file order
        records = legacy_rows + _lineage_order([r for r in records if not r["legacy"]], lambda r: r["status"])
        if trusted:
            claims = _lineage_order(claims, lambda c: c["status"])
        elif len({c["id"] for c in claims}) != len(claims):
            raise ValueError("Duplicate id in import.")
        return records, tombs, claims, claim_tombs

    def _can_introduce(self, db, record: dict, inserted: set[str], allow_correction: bool) -> bool:
        """Whether a payload record may enter this vault without changing existing epistemic state."""
        rid, predecessor = record["id"], record["supersedes_id"]
        if (self._exists(db, "SELECT 1 FROM records WHERE id=?", rid)          # evidence is never replaced
                or self._exists(db, "SELECT 1 FROM tombstones WHERE id=?", rid)   # forgotten stays forgotten
                or self._exists(db, "SELECT 1 FROM claim_sources WHERE record_id=?", rid)):  # would change claims' support
            return False

        def blocking_successors(of: str) -> list[str]:
            # Current rows follow strictly linear lineage. A legacy row mirrors its backup's (possibly
            # anomalous) ADR-0002 lineage, so only evidence that was here *before* this operation blocks it.
            found = [r["id"] for r in db.execute("SELECT id FROM records WHERE supersedes_id=?", (of,))]
            return [f for f in found if f not in inserted] if record["legacy"] else found

        if blocking_successors(rid):
            return False   # already corrected here
        if predecessor is None:
            return True
        if blocking_successors(predecessor):
            return False   # lineage is linear: the predecessor (present or not) already has a correction here
        if record["legacy"] and self._exists(db, "SELECT 1 FROM records WHERE id=? AND legacy=0", predecessor):
            return False   # legacy lineage never reaches into current evidence
        if predecessor not in inserted and self._exists(db, "SELECT 1 FROM records WHERE id=?", predecessor):
            return allow_correction   # correcting local evidence: never from an untrusted file
        return True

    def _insert_records(self, db, records: list[dict], skip_ids: set[str], allow_correction: bool) -> tuple[int, int]:
        inserted: set[str] = set()
        skipped = 0
        for record in records:
            if record["id"] in skip_ids or not self._can_introduce(db, record, inserted, allow_correction):
                skipped += 1
                continue
            db.execute("INSERT INTO records(id,content,source,sensitivity,status,created_at,supersedes_id,legacy) VALUES (?,?,?,?,?,?,?,?)",
                       tuple(record[k] for k in ("id", "content", "source", "sensitivity", "status", "created_at", "supersedes_id", "legacy")))
            inserted.add(record["id"])
        return len(inserted), skipped

    def import_untrusted(self, payload: dict) -> dict:
        """Ordinary import: the file is external, untrusted content.

        It can add evidence and *proposed* claims; it can never grant authority, change or
        delete local state, or raise the support of an existing claim. Records are skipped if
        they already exist, were forgotten, are cited by an existing claim, are already
        corrected here, or would correct local evidence. Live claims (file status proposed,
        approved or contested) arrive as new `proposed` claims with origin `imported` and a
        deterministic id derived from the file's id; history/approvals in the file are noted,
        not trusted, and they attach only to evidence present in the vault. The file's
        tombstones only filter the file's own content.
        """
        records, tombs, claims, claim_tombs = self._parse(payload, trusted=False)
        file_tombs = {t["id"] for t in tombs}
        file_claim_tombs = {t["id"] for t in claim_tombs}
        imported_claims = skipped_claims = 0
        with self.connection(write=True) as db:
            imported, skipped_records = self._insert_records(db, records, file_tombs, allow_correction=False)
            now = stamp()
            for claim in claims:
                original, cid = claim["id"], str(uuid5(IMPORT_NAMESPACE, claim["id"]))
                forgotten = lambda i: self._exists(db, "SELECT 1 FROM claim_tombstones WHERE id=?", i)
                if (claim["status"] in ("rejected", "superseded") or not claim["source_ids"] or original in file_claim_tombs
                        or forgotten(original) or forgotten(cid)
                        or self._exists(db, "SELECT 1 FROM claims WHERE id IN (?,?)", cid, original)   # already here, genuine or imported
                        or self._exists(db, "SELECT 1 FROM claims WHERE supersedes_id=?", cid)          # already replaced here
                        or any(r in file_tombs for r in claim["source_ids"])):
                    skipped_claims += 1
                    continue
                # Proposals attach only to evidence present here. Linking an absent id would block that
                # record from ever being introduced later (storage rule), letting a file squat on it.
                evidence = [db.execute("SELECT * FROM records WHERE id=?", (rid,)).fetchone() for rid in claim["source_ids"]]
                if any(rec is None for rec in evidence):
                    skipped_claims += 1
                    continue
                hashes = {rec["id"]: evidence_hash(rec) for rec in evidence}
                note = (f"Imported from an untrusted file (file claim {original[:64]}, stated origin {claim['origin']}, "
                        f"status {claim['status']}; not trusted).")
                self._insert_claim(db, cid, claim["text"], hashes, "imported", None, now, [{"at": now, "note": note}])
                imported_claims += 1
        return {"imported": imported, "records_skipped": skipped_records,
                "claims_imported_as_proposed": imported_claims, "claims_skipped": skipped_claims}

    def restore_trusted(self, payload: dict) -> dict:
        """Trusted restore of a Sovereign-owned backup (explicitly confirmed by the user).

        Tombstones in the backup dominate: matching local records are forgotten (with their
        dependent claims) and matching local claims are forgotten. Records then claims are
        merged predecessors-first; claim histories are validated and replayed through the
        storage lifecycle triggers, so prior authority is preserved but no illegal history can
        be written. Local state is never overwritten and the support of claims already in the
        vault is never raised. Integrity of the backup file itself (signing) is not verified in V0.
        """
        records, tombs, claims, claim_tombs = self._parse(payload, trusted=True)
        restored = approved = existing = conflicts = 0
        with self.connection(write=True) as db:
            live_before = db.execute("SELECT count(*) FROM claims").fetchone()[0]
            db.executemany("INSERT INTO tombstones(id,deleted_at) VALUES (?,?)", [(t["id"], t["deleted_at"]) for t in tombs])
            db.executemany("INSERT INTO claim_tombstones(id,deleted_at) VALUES (?,?)", [(t["id"], t["deleted_at"]) for t in claim_tombs])
            forgotten = live_before - db.execute("SELECT count(*) FROM claims").fetchone()[0]
            imported, skipped_records = self._insert_records(db, records, set(), allow_correction=True)
            for claim in claims:
                cid, predecessor = claim["id"], claim["supersedes_id"]
                if self._exists(db, "SELECT 1 FROM claim_tombstones WHERE id=?", cid):
                    continue
                if self._exists(db, "SELECT 1 FROM claims WHERE id=?", cid):
                    existing += 1   # local state wins; never forgotten or rewritten by payload content
                    continue
                if any(self._exists(db, "SELECT 1 FROM tombstones WHERE id=?", r) for r in claim["source_ids"]):
                    db.execute("INSERT INTO claim_tombstones(id,deleted_at) VALUES (?,?)", (cid, stamp()))  # derived from forgotten evidence
                    forgotten += 1
                    continue
                pred = db.execute("SELECT status FROM claims WHERE id=?", (predecessor,)).fetchone() if predecessor else None
                if (self._exists(db, "SELECT 1 FROM claims WHERE supersedes_id=?", cid)
                        or (pred is not None and pred["status"] != "superseded")
                        or (predecessor is not None and self._exists(db, "SELECT 1 FROM claims WHERE supersedes_id=?", predecessor))):
                    conflicts += 1   # supersession diverged from local state; local state wins
                    continue
                self._insert_claim(db, cid, claim["text"], claim["source_hashes"], claim["origin"], predecessor,
                                   claim["created_at"], claim["history"])
                restored += 1
                approved += claim["status"] == "approved"
        return {"imported": imported, "records_skipped": skipped_records, "claims_restored": restored,
                "approved_claims_restored": approved, "claims_skipped_existing": existing,
                "claims_skipped_conflict": conflicts, "claims_forgotten": forgotten}


def _statements(script: str) -> list[str]:
    """Split a schema script into complete statements (trigger bodies contain ';')."""
    statements, buffer = [], ""
    for line in script.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            if buffer.strip():
                statements.append(buffer.strip())
            buffer = ""
    if buffer.strip():
        raise ValueError("Incomplete schema statement.")
    return statements
