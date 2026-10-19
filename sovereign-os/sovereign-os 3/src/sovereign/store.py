"""Local source record vault.

Source records are evidence. Memory claims are separate, source-linked
interpretations governed by `claims.py` (ADR-0003): created `proposed`, changed
only by explicit, recorded human decisions, and never sent to a model. Claim
support is derived at read time from current evidence, so correcting a source
record immediately stops dependent claims presenting as supported.

Deleting a source record means *forget*: the record, its earlier revisions and
every claim derived from them are removed from the active DB and replaced by
content-free identifier tombstones that block resurrection. Full secure erasure
including backups/WAL is NOT provided.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Iterator
from uuid import uuid4

from . import claims as rules

# PRAGMA user_version. 0 = records-only vaults (ADR-0002). 1 = unreleased draft (c847f9d).
SCHEMA_VERSION = 2
EXPORT_SCHEMAS = ("sovereign.v0.records.1", "sovereign.v0.records.2")

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


_ALLOWED = ", ".join(f"'{key}'" for key in rules.transition_keys())
_TERMINAL = ", ".join(f"'{s}'" for s, targets in rules.TRANSITIONS.items() if not targets)
_TOMBSTONED = "EXISTS (SELECT 1 FROM claim_tombstones WHERE id = {})"

# Version 2: additive only. Existing `records`/`tombstones` rows are untouched.
# These triggers are the storage contract (ADR-0003): they hold for any connection
# issuing INSERT/UPDATE/DELETE, but not against schema changes (DROP TRIGGER) or
# direct file edits by a process that already controls the vault file.
CLAIMS_SCHEMA = f"""
    -- Evidence is immutable apart from active -> superseded (correction), and forgotten ids stay forgotten.
    CREATE TRIGGER records_immutable BEFORE UPDATE OF id, content, source, sensitivity, created_at, supersedes_id ON records
    {_abort('source records are immutable evidence')}
    CREATE TRIGGER records_status_forward BEFORE UPDATE OF status ON records
    WHEN NOT (OLD.status = 'active' AND NEW.status = 'superseded')
    {_abort('a source record can only move from active to superseded')}
    CREATE TRIGGER records_not_resurrected BEFORE INSERT ON records
    WHEN EXISTS (SELECT 1 FROM tombstones WHERE id = NEW.id)
    {_abort('record id was forgotten')}
    CREATE TRIGGER tombstones_no_update BEFORE UPDATE ON tombstones {_abort('tombstones are permanent')}
    CREATE TRIGGER tombstones_no_delete BEFORE DELETE ON tombstones {_abort('tombstones are permanent')}

    CREATE TABLE claims (
        id TEXT PRIMARY KEY,
        text TEXT NOT NULL,
        origin TEXT NOT NULL CHECK(origin IN ('human', 'model', 'imported')),
        status TEXT NOT NULL CHECK(status IN ('proposed', 'approved', 'rejected', 'contested', 'superseded')),
        created_at TEXT NOT NULL,
        supersedes_id TEXT
    );
    -- No foreign key to records: the link must survive so support can derive as orphaned.
    -- evidence_sha256 pins the exact evidence the claim was made from (NULL = never seen).
    CREATE TABLE claim_sources (
        claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
        record_id TEXT NOT NULL,
        evidence_sha256 TEXT CHECK(evidence_sha256 IS NULL OR length(evidence_sha256) = 64),
        PRIMARY KEY (claim_id, record_id)
    );
    -- Append-only decision history (the V0 form of MemoryPromotionDecision).
    CREATE TABLE claim_events (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
        from_status TEXT,
        to_status TEXT NOT NULL,
        actor TEXT NOT NULL CHECK(actor IN ('human', 'model', 'imported')),
        note TEXT,
        at TEXT NOT NULL,
        CHECK((from_status IS NULL) = (to_status = 'proposed')),
        CHECK(from_status IS NULL OR actor = 'human')
    );
    CREATE INDEX ix_claim_events_claim ON claim_events(claim_id, seq);
    CREATE INDEX ix_claim_sources_record ON claim_sources(record_id);
    CREATE TABLE claim_tombstones (
        id TEXT PRIMARY KEY,
        deleted_at TEXT NOT NULL
    );

    -- Claims: born proposed, immutable, never reusing a forgotten id, removed only by forgetting.
    CREATE TRIGGER claims_created_proposed BEFORE INSERT ON claims WHEN NEW.status <> 'proposed'
    {_abort('claims must be created as proposed')}
    CREATE TRIGGER claims_not_resurrected BEFORE INSERT ON claims WHEN {_TOMBSTONED.format('NEW.id')}
    {_abort('claim id was forgotten')}
    CREATE TRIGGER claims_immutable BEFORE UPDATE OF id, text, origin, created_at, supersedes_id ON claims
    {_abort('claims are immutable; supersede instead')}
    CREATE TRIGGER claims_status_recorded BEFORE UPDATE OF status ON claims
    WHEN NEW.status IS NOT (SELECT to_status FROM claim_events WHERE claim_id = NEW.id ORDER BY seq DESC LIMIT 1)
      OR (OLD.status IN ({_TERMINAL}) AND NEW.status IS NOT OLD.status)
    {_abort('claim status changes only through a recorded legal event')}
    CREATE TRIGGER claims_delete_forgotten_only BEFORE DELETE ON claims WHEN NOT {_TOMBSTONED.format('OLD.id')}
    {_abort('claims are removed only by forgetting (claim tombstone)')}

    -- Evidence links are fixed when the claim's creation event is written.
    CREATE TRIGGER claim_sources_fixed_insert BEFORE INSERT ON claim_sources
    WHEN NOT EXISTS (SELECT 1 FROM claims WHERE id = NEW.claim_id)
      OR EXISTS (SELECT 1 FROM claim_events WHERE claim_id = NEW.claim_id)
    {_abort('claim evidence links are fixed at creation')}
    CREATE TRIGGER claim_sources_fixed_update BEFORE UPDATE ON claim_sources
    {_abort('claim evidence links are fixed at creation')}
    CREATE TRIGGER claim_sources_fixed_delete BEFORE DELETE ON claim_sources WHEN NOT {_TOMBSTONED.format('OLD.claim_id')}
    {_abort('claim evidence links are fixed at creation')}

    -- History: one creation event by the claim's origin, then legal human transitions from the
    -- *current* status (compare-and-set: a stale concurrent decision aborts). Inserting an event is
    -- the only way to change a claim's status.
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
    CREATE TRIGGER claim_events_no_delete BEFORE DELETE ON claim_events WHEN NOT {_TOMBSTONED.format('OLD.claim_id')}
    {_abort('claim history is append-only')}

    -- Forgetting a claim = writing its tombstone; the claim, links and history go with it
    -- (explicit deletes, so this does not depend on PRAGMA foreign_keys).
    CREATE TRIGGER claim_tombstones_forget AFTER INSERT ON claim_tombstones BEGIN
        DELETE FROM claim_events WHERE claim_id = NEW.id;
        DELETE FROM claim_sources WHERE claim_id = NEW.id;
        DELETE FROM claims WHERE id = NEW.id;
    END;
    CREATE TRIGGER claim_tombstones_no_update BEFORE UPDATE ON claim_tombstones {_abort('tombstones are permanent')}
    CREATE TRIGGER claim_tombstones_no_delete BEFORE DELETE ON claim_tombstones {_abort('tombstones are permanent')}
"""


def evidence_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
            for statement in _statements(BASE_SCHEMA + CLAIMS_SCHEMA):
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
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA secure_delete=ON")
        db.execute("PRAGMA foreign_keys=ON")
        if write:
            # Take the write lock before reading, so read-check-write is atomic across processes.
            db.execute("BEGIN IMMEDIATE")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _record(row: sqlite3.Row) -> dict:
        return dict(row)

    def add(self, content: str, sensitivity: str = "private", supersedes_id: str | None = None) -> dict:
        content = content.strip()
        if not content or len(content) > 10000:
            raise ValueError("Text must be between 1 and 10,000 characters.")
        if sensitivity not in {"private", "sensitive"}:
            raise ValueError("Invalid sensitivity.")
        record_id = str(uuid4())
        with self.connection(write=True) as db:
            if supersedes_id:
                old = db.execute("SELECT * FROM records WHERE id=? AND status='active'", (supersedes_id,)).fetchone()
                if old is None:
                    raise KeyError("Record to correct was not found or is already superseded.")
                db.execute("UPDATE records SET status='superseded' WHERE id=?", (supersedes_id,))
            db.execute("INSERT INTO records(id,content,sensitivity,status,created_at,supersedes_id) VALUES(?,?,?,?,?,?)",
                       (record_id, content, sensitivity, "active", stamp(), supersedes_id))
            row = db.execute("SELECT * FROM records WHERE id=?", (record_id,)).fetchone()
            return self._record(row)

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

    @staticmethod
    def _forget_records(db: sqlite3.Connection, ids: list[str], at: str) -> int:
        """Tombstone records and forget every claim derived from them. Returns claims forgotten."""
        forgotten = 0
        for rid in ids:
            db.execute("INSERT OR IGNORE INTO tombstones (id,deleted_at) VALUES (?,?)", (rid, at))
            db.execute("DELETE FROM records WHERE id=?", (rid,))
            for row in db.execute("SELECT DISTINCT claim_id FROM claim_sources WHERE record_id=?", (rid,)).fetchall():
                forgotten += db.execute("INSERT OR IGNORE INTO claim_tombstones (id,deleted_at) VALUES (?,?)",
                                        (row["claim_id"], at)).rowcount
        return forgotten

    def delete(self, record_id: str) -> dict | None:
        """Forget a source record, its earlier revisions and all dependent claims."""
        with self.connection(write=True) as db:
            row = db.execute("SELECT id FROM records WHERE id=?", (record_id,)).fetchone()
            if not row:
                return None
            ids = [record_id]
            pointer = record_id
            while True:
                previous = db.execute("SELECT supersedes_id FROM records WHERE id=?", (pointer,)).fetchone()
                if not previous or not previous["supersedes_id"]:
                    break
                pointer = previous["supersedes_id"]
                if pointer in ids:
                    break
                ids.append(pointer)
            # Do not claim backup/WAL/forensic secure deletion here.
            return {"records_forgotten": len(ids), "claims_forgotten": self._forget_records(db, ids, stamp())}

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
            rec = db.execute("SELECT status, content, sensitivity FROM records WHERE id=?", (rid,)).fetchone()
            if rec is None:
                sources.append({"id": rid, "state": "missing", "content": None, "sensitivity": None})
            elif link["evidence_sha256"] != evidence_hash(rec["content"]):
                # Not the evidence this claim was made from (substituted, or never seen at link time).
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
        return text

    @staticmethod
    def _insert_claim(db, claim_id: str, text: str, source_hashes: dict[str, str | None], origin: str,
                      supersedes_id: str | None, created_at: str, note: str | None = None) -> None:
        db.execute("INSERT INTO claims(id,text,origin,status,created_at,supersedes_id) VALUES (?,?,?,'proposed',?,?)",
                   (claim_id, text, origin, created_at, supersedes_id))
        db.executemany("INSERT INTO claim_sources(claim_id,record_id,evidence_sha256) VALUES (?,?,?)",
                       [(claim_id, rid, digest) for rid, digest in source_hashes.items()])
        db.execute("INSERT INTO claim_events(claim_id,from_status,to_status,actor,note,at) VALUES (?,NULL,'proposed',?,?,?)",
                   (claim_id, origin, note, created_at))

    def _new_claim(self, db, text: str, source_ids: list[str], origin: str, supersedes_id: str | None) -> str:
        hashes = {}
        for rid in source_ids:
            rec = db.execute("SELECT content FROM records WHERE id=? AND status='active'", (rid,)).fetchone()
            if rec is None:
                raise ValueError(f"Source record missing or superseded: {rid}")
            hashes[rid] = evidence_hash(rec["content"])
        claim_id = str(uuid4())
        self._insert_claim(db, claim_id, text, hashes, origin, supersedes_id, stamp())
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

    def list_claims(self, status: str | None = None, limit: int = 100) -> list[dict]:
        with self.connection() as db:
            if status:
                rows = db.execute("SELECT * FROM claims WHERE status=? ORDER BY created_at DESC,id DESC LIMIT ?", (status, min(limit, 200)))
            else:
                rows = db.execute("SELECT * FROM claims ORDER BY created_at DESC,id DESC LIMIT ?", (min(limit, 200),))
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
            new_id = self._new_claim(db, text, source_ids, "human", claim_id)
            self._record_transition(db, claim_id, old["status"], "superseded", note, stamp())
            return {"superseded": self._get_claim(db, claim_id), "replacement": self._get_claim(db, new_id)}

    def delete_claim(self, claim_id: str) -> bool:
        """Forget a claim: its tombstone removes the claim, its links and its history."""
        with self.connection(write=True) as db:
            if not db.execute("SELECT 1 FROM claims WHERE id=?", (claim_id,)).fetchone():
                return False
            db.execute("INSERT INTO claim_tombstones(id,deleted_at) VALUES (?,?)", (claim_id, stamp()))
            return True

    # --- Portability ----------------------------------------------------------

    def export(self) -> dict:
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
    def _parse(payload: dict) -> tuple[list, list, list, list]:
        if payload.get("schema") not in EXPORT_SCHEMAS:
            raise ValueError("Unsupported export schema.")
        parts = (payload.get("records"), payload.get("tombstones"),
                 payload.get("claims", []), payload.get("claim_tombstones", []))
        for items in parts:
            if not isinstance(items, list) or len(items) > 10000:
                raise ValueError("Invalid export lists.")
        for tomb in parts[1] + parts[3]:
            if not isinstance(tomb, dict) or not isinstance(tomb.get("id"), str) or not isinstance(tomb.get("deleted_at"), str):
                raise ValueError("Invalid tombstone in import.")
        for claim in parts[2]:
            if not isinstance(claim, dict):
                raise ValueError("Invalid claim in import.")
            text, source_ids = claim.get("text"), claim.get("source_ids")
            if (not isinstance(claim.get("id"), str) or not isinstance(text, str) or not 0 < len(text) <= rules.MAX_TEXT
                    or claim.get("origin") not in rules.ORIGINS or claim.get("status") not in rules.STATUSES
                    or not isinstance(claim.get("created_at"), str)
                    or not (claim.get("supersedes_id") is None or isinstance(claim.get("supersedes_id"), str))
                    or not isinstance(source_ids, list) or not 0 < len(source_ids) <= rules.MAX_SOURCES
                    or not all(isinstance(r, str) for r in source_ids) or len(set(source_ids)) != len(source_ids)):
                raise ValueError("Invalid claim in import.")
            hashes = claim.get("source_hashes", {})
            if (not isinstance(hashes, dict) or not set(hashes) <= set(source_ids)
                    or not all(h is None or (isinstance(h, str) and len(h) == 64) for h in hashes.values())):
                raise ValueError("Invalid claim evidence hashes in import.")
        return parts

    @staticmethod
    def _insert_records(db, records: list, skip_ids: set[str]) -> int:
        count = 0
        for row in records:
            if not isinstance(row, dict):
                raise ValueError("Invalid record in import.")
            rid = str(row["id"])
            if rid in skip_ids or db.execute("SELECT 1 FROM tombstones WHERE id=?", (rid,)).fetchone():
                continue
            if row["sensitivity"] not in ("private", "sensitive") or row["status"] not in ("active", "superseded"):
                raise ValueError("Invalid record in import.")
            if len(row["content"]) > 10000:
                raise ValueError("Record too large in import.")
            cursor = db.execute("INSERT OR IGNORE INTO records(id,content,source,sensitivity,status,created_at,supersedes_id) VALUES (?,?,?,?,?,?,?)",
                (rid, row["content"], row["source"], row["sensitivity"], row["status"], row["created_at"], row.get("supersedes_id")))
            count += cursor.rowcount
        return count

    def import_untrusted(self, payload: dict) -> dict:
        """Ordinary import: the file is external, untrusted content.

        Records are imported as evidence. Live claims (file status proposed,
        approved or contested) are imported as new `proposed` claims with origin
        `imported`; the file's history, origin and approvals are not trusted and
        are only noted. Rejected/superseded claims are not imported. The file's
        tombstones only filter the file's own content: an untrusted file cannot
        forget local records or claims. Local tombstones always win.
        """
        records, tombs, claims, claim_tombs = self._parse(payload)
        file_tombs = {t["id"] for t in tombs}
        file_claim_tombs = {t["id"] for t in claim_tombs}
        imported_claims = skipped = 0
        with self.connection(write=True) as db:
            count = self._insert_records(db, records, file_tombs)
            now = stamp()
            for claim in claims:
                cid = claim["id"]
                forgotten_source = any(r in file_tombs or db.execute("SELECT 1 FROM tombstones WHERE id=?", (r,)).fetchone()
                                       for r in claim["source_ids"])
                if (claim["status"] in ("rejected", "superseded") or cid in file_claim_tombs or forgotten_source
                        or db.execute("SELECT 1 FROM claims WHERE id=? UNION SELECT 1 FROM claim_tombstones WHERE id=?", (cid, cid)).fetchone()):
                    skipped += 1
                    continue
                note = f"Imported from an untrusted file (stated origin {claim['origin']}, status {claim['status']}; not trusted)."
                # Pin whatever evidence is now local; a link to absent evidence stays unverified forever.
                hashes = {}
                for rid in claim["source_ids"]:
                    rec = db.execute("SELECT content FROM records WHERE id=?", (rid,)).fetchone()
                    hashes[rid] = evidence_hash(rec["content"]) if rec else None
                self._insert_claim(db, cid, claim["text"], hashes, "imported", None, now, note)
                imported_claims += 1
        return {"imported": count, "claims_imported_as_proposed": imported_claims, "claims_skipped": skipped}

    def restore_trusted(self, payload: dict) -> dict:
        """Trusted restore of a Sovereign-owned backup (explicitly confirmed by the user).

        Tombstones in the backup dominate: matching local records are forgotten
        (with their dependent claims) and matching local claims are forgotten.
        Claim histories are validated and replayed through the storage lifecycle
        triggers, so prior authority is preserved but no illegal history can be
        written. A local claim is never overwritten. Integrity of the backup file
        itself (signing) is not verified in V0.
        """
        records, tombs, claims, claim_tombs = self._parse(payload)
        for claim in claims:
            rules.validate_history(claim.get("history"), claim["origin"], claim["status"])
        restored = approved = skipped = forgotten = 0
        with self.connection(write=True) as db:
            for tomb in tombs:
                forgotten += self._forget_records(db, [tomb["id"]], tomb["deleted_at"])
            for tomb in claim_tombs:
                forgotten += db.execute("INSERT OR IGNORE INTO claim_tombstones(id,deleted_at) VALUES (?,?)",
                                        (tomb["id"], tomb["deleted_at"])).rowcount
            count = self._insert_records(db, records, set())
            for claim in claims:
                cid = claim["id"]
                if db.execute("SELECT 1 FROM claim_tombstones WHERE id=?", (cid,)).fetchone():
                    continue
                if any(db.execute("SELECT 1 FROM tombstones WHERE id=?", (r,)).fetchone() for r in claim["source_ids"]):
                    # Derived from forgotten evidence: forget it too.
                    db.execute("INSERT INTO claim_tombstones(id,deleted_at) VALUES (?,?)", (cid, stamp()))
                    forgotten += 1
                    continue
                if db.execute("SELECT 1 FROM claims WHERE id=?", (cid,)).fetchone():
                    skipped += 1
                    continue
                created = claim["history"][0]
                hashes = {rid: claim.get("source_hashes", {}).get(rid) for rid in claim["source_ids"]}
                self._insert_claim(db, cid, claim["text"], hashes, claim["origin"],
                                   claim.get("supersedes_id"), created["at"], created.get("note"))
                for event in claim["history"][1:]:
                    self._record_transition(db, cid, event["from_status"], event["to_status"], event.get("note"), event["at"])
                restored += 1
                approved += claim["status"] == "approved"
        return {"imported": count, "claims_restored": restored, "approved_claims_restored": approved,
                "claims_skipped_existing": skipped, "claims_forgotten": forgotten}


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
