"""Local source record vault.

Source records are evidence. Memory claims are separate, source-linked
interpretations governed by `claims.py` (ADR-0003): created `proposed`, changed
only by explicit, recorded human decisions, and never sent to a model. Claim
support is derived at read time from current evidence, so correcting or deleting
a source record immediately stops dependent claims presenting as supported.

Revision records are kept locally; deletion clears content in the active DB and
writes a content-free identifier tombstone. Full secure erasure including
backups/WAL is NOT provided.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Iterator
from uuid import uuid4

from . import claims as rules

SCHEMA_VERSION = 1  # PRAGMA user_version. 0 = records only (pre-claims vaults).
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

# Version 1: additive only. Existing `records`/`tombstones` rows are untouched.
CLAIMS_SCHEMA = """
    CREATE TABLE claims (
        id TEXT PRIMARY KEY,
        text TEXT NOT NULL,
        origin TEXT NOT NULL CHECK(origin IN ('human', 'model')),
        status TEXT NOT NULL CHECK(status IN ('proposed', 'approved', 'rejected', 'contested', 'superseded')),
        created_at TEXT NOT NULL,
        supersedes_id TEXT
    );
    -- No foreign key to records: evidence may be deleted while the claim remains, orphaned.
    CREATE TABLE claim_sources (
        claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
        record_id TEXT NOT NULL,
        PRIMARY KEY (claim_id, record_id)
    );
    -- Append-only decision history (the V0 form of MemoryPromotionDecision).
    CREATE TABLE claim_events (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
        from_status TEXT,
        to_status TEXT NOT NULL,
        actor TEXT NOT NULL CHECK(actor IN ('human', 'model')),
        note TEXT,
        at TEXT NOT NULL,
        CHECK((from_status IS NULL) = (to_status = 'proposed')),
        CHECK(to_status = 'proposed' OR actor = 'human')
    );
    CREATE INDEX ix_claim_events_claim ON claim_events(claim_id, seq);
    CREATE TABLE claim_tombstones (
        id TEXT PRIMARY KEY,
        deleted_at TEXT NOT NULL
    );
    -- Storage-level guards, independent of the API layer.
    CREATE TRIGGER claims_created_proposed BEFORE INSERT ON claims WHEN NEW.status <> 'proposed'
    BEGIN SELECT RAISE(ABORT, 'claims must be created as proposed'); END;
    CREATE TRIGGER claims_terminal BEFORE UPDATE OF status ON claims WHEN OLD.status IN ('rejected', 'superseded')
    BEGIN SELECT RAISE(ABORT, 'rejected and superseded claims are final'); END;
    CREATE TRIGGER claims_status_recorded BEFORE UPDATE OF status ON claims
    WHEN NEW.status IS NOT (SELECT to_status FROM claim_events WHERE claim_id = NEW.id ORDER BY seq DESC LIMIT 1)
    BEGIN SELECT RAISE(ABORT, 'claim status change must be recorded as an event'); END;
    CREATE TRIGGER claims_immutable BEFORE UPDATE OF id, text, origin, created_at, supersedes_id ON claims
    BEGIN SELECT RAISE(ABORT, 'claims are immutable; supersede instead'); END;
    CREATE TRIGGER claim_events_append_only BEFORE UPDATE ON claim_events
    BEGIN SELECT RAISE(ABORT, 'claim history is append-only'); END;
"""


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Vault:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    def _migrate(self) -> None:
        db = sqlite3.connect(self.path, isolation_level=None)
        try:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise RuntimeError(f"Vault schema {version} is newer than this software supports ({SCHEMA_VERSION}).")
            if version == SCHEMA_VERSION:
                return
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='claims'").fetchone():
                # Only the unreleased first benchmark draft created this; refuse rather than guess.
                raise RuntimeError("Vault has an unversioned claims table from a pre-release build; export records and restore into a new vault.")
            # One transaction: either the vault is fully at version 1 or unchanged.
            db.executescript(f"BEGIN; {BASE_SCHEMA} {CLAIMS_SCHEMA} PRAGMA user_version = {SCHEMA_VERSION}; COMMIT;")
        except Exception:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA secure_delete=ON")
        db.execute("PRAGMA foreign_keys=ON")
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
        with self.connection() as db:
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

    def delete(self, record_id: str) -> bool:
        with self.connection() as db:
            row = db.execute("SELECT id FROM records WHERE id=?", (record_id,)).fetchone()
            if not row:
                return False
            # Delete this and earlier revisions (the chain); tombstone every id.
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
            for rid in ids:
                db.execute("INSERT OR IGNORE INTO tombstones (id,deleted_at) VALUES (?,?)", (rid, stamp()))
                db.execute("DELETE FROM records WHERE id=?", (rid,))
            # Do not claim backup/WAL/forensic secure deletion here.
            # Dependent claims are not touched: their support now derives as `orphaned`.
            return True

    # --- Memory claims -----------------------------------------------------

    def _claim(self, db: sqlite3.Connection, row: sqlite3.Row) -> dict:
        claim = dict(row)
        claim["source_ids"] = [r["record_id"] for r in db.execute(
            "SELECT record_id FROM claim_sources WHERE claim_id=? ORDER BY record_id", (claim["id"],))]
        sources = []
        for rid in claim["source_ids"]:
            rec = db.execute("SELECT status, content, sensitivity FROM records WHERE id=?", (rid,)).fetchone()
            if rec:
                sources.append({"id": rid, "state": rec["status"], "content": rec["content"], "sensitivity": rec["sensitivity"]})
            else:
                gone = db.execute("SELECT 1 FROM tombstones WHERE id=?", (rid,)).fetchone()
                sources.append({"id": rid, "state": "deleted" if gone else "missing", "content": None, "sensitivity": None})
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

    def _insert_claim(self, db, text: str, source_ids: list[str], origin: str, supersedes_id: str | None) -> str:
        for rid in source_ids:
            if not db.execute("SELECT 1 FROM records WHERE id=? AND status='active'", (rid,)).fetchone():
                raise ValueError(f"Source record missing or superseded: {rid}")
        claim_id, now = str(uuid4()), stamp()
        db.execute("INSERT INTO claims(id,text,origin,status,created_at,supersedes_id) VALUES (?,?,?,'proposed',?,?)",
                   (claim_id, text, origin, now, supersedes_id))
        db.executemany("INSERT INTO claim_sources(claim_id,record_id) VALUES (?,?)", [(claim_id, rid) for rid in source_ids])
        db.execute("INSERT INTO claim_events(claim_id,from_status,to_status,actor,at) VALUES (?,NULL,'proposed',?,?)",
                   (claim_id, origin, now))
        return claim_id

    @staticmethod
    def _record_transition(db, claim_id: str, current: str, target: str, note: str | None, at: str) -> None:
        db.execute("INSERT INTO claim_events(claim_id,from_status,to_status,actor,note,at) VALUES (?,?,?,'human',?,?)",
                   (claim_id, current, target, note, at))
        db.execute("UPDATE claims SET status=? WHERE id=?", (target, claim_id))

    def add_claim(self, text: str, source_ids: list[str], origin: str = "human") -> dict:
        """Create a claim. Always `proposed`; there is deliberately no status argument."""
        text = self._validate_new(text, source_ids, origin)
        with self.connection() as db:
            return self._get_claim(db, self._insert_claim(db, text, source_ids, origin, None))

    def list_claims(self, status: str | None = None, limit: int = 100) -> list[dict]:
        with self.connection() as db:
            if status:
                rows = db.execute("SELECT * FROM claims WHERE status=? ORDER BY created_at DESC,id DESC LIMIT ?", (status, min(limit, 200)))
            else:
                rows = db.execute("SELECT * FROM claims ORDER BY created_at DESC,id DESC LIMIT ?", (min(limit, 200),))
            return [self._claim(db, row) for row in rows.fetchall()]

    def transition_claim(self, claim_id: str, target: str, note: str | None = None) -> dict:
        """Explicit human decision: approve, reject or contest. Recorded in claim history."""
        if target not in ("approved", "rejected", "contested"):
            raise ValueError("Use supersede to replace a claim.")
        if note is not None and len(note) > rules.MAX_NOTE:
            raise ValueError("Note too long.")
        with self.connection() as db:
            claim = self._get_claim(db, claim_id)
            rules.check_transition(claim["status"], target, claim["support"])
            self._record_transition(db, claim_id, claim["status"], target, note, stamp())
            return self._get_claim(db, claim_id)

    def supersede_claim(self, claim_id: str, text: str, source_ids: list[str], note: str | None = None) -> dict:
        """Human correction: the old claim becomes `superseded`; its replacement starts `proposed`."""
        text = self._validate_new(text, source_ids, "human")
        if note is not None and len(note) > rules.MAX_NOTE:
            raise ValueError("Note too long.")
        with self.connection() as db:
            old = self._get_claim(db, claim_id)
            rules.check_transition(old["status"], "superseded")
            new_id = self._insert_claim(db, text, source_ids, "human", claim_id)
            self._record_transition(db, claim_id, old["status"], "superseded", note, stamp())
            return {"superseded": self._get_claim(db, claim_id), "replacement": self._get_claim(db, new_id)}

    def delete_claim(self, claim_id: str) -> bool:
        with self.connection() as db:
            if not db.execute("SELECT 1 FROM claims WHERE id=?", (claim_id,)).fetchone():
                return False
            db.execute("INSERT OR IGNORE INTO claim_tombstones(id,deleted_at) VALUES (?,?)", (claim_id, stamp()))
            db.execute("DELETE FROM claims WHERE id=?", (claim_id,))  # sources and history cascade
            return True

    # --- Portability ----------------------------------------------------------

    def export(self) -> dict:
        keys = ("id", "text", "origin", "status", "created_at", "supersedes_id", "source_ids", "history")
        with self.connection() as db:
            rows = db.execute("SELECT * FROM records ORDER BY created_at,id").fetchall()
            tombs = db.execute("SELECT * FROM tombstones ORDER BY deleted_at,id").fetchall()
            claim_rows = db.execute("SELECT * FROM claims ORDER BY created_at,id").fetchall()
            claims = [{k: c[k] for k in keys} for c in (self._claim(db, r) for r in claim_rows)]
            claim_tombs = db.execute("SELECT * FROM claim_tombstones ORDER BY deleted_at,id").fetchall()
            return {"schema": "sovereign.v0.records.2", "exported_at": stamp(),
                    "records": [dict(r) for r in rows], "tombstones": [dict(t) for t in tombs],
                    "claims": claims, "claim_tombstones": [dict(t) for t in claim_tombs]}

    def restore(self, payload: dict) -> dict:
        """Merge idempotently. Tombstones win over imported records and claims.

        Schema .1 (records only) is still accepted. An imported claim never
        overwrites a local claim, so import cannot change an existing decision.
        Imported histories are replayed through the lifecycle rules; a history
        the rules would not allow fails the whole import.
        """
        if payload.get("schema") not in EXPORT_SCHEMAS:
            raise ValueError("Unsupported export schema.")
        records, tombs = payload.get("records"), payload.get("tombstones")
        claims, claim_tombs = payload.get("claims", []), payload.get("claim_tombstones", [])
        for items in (records, tombs, claims, claim_tombs):
            if not isinstance(items, list) or len(items) > 10000:
                raise ValueError("Invalid export lists.")
        count = claim_count = approved_count = skipped = 0
        with self.connection() as db:
            for tomb in tombs:
                rid = str(tomb["id"])
                db.execute("INSERT OR IGNORE INTO tombstones(id,deleted_at) VALUES (?,?)", (rid, str(tomb["deleted_at"])))
            for row in records:
                rid = str(row["id"])
                if db.execute("SELECT 1 FROM tombstones WHERE id=?", (rid,)).fetchone():
                    continue
                if row["sensitivity"] not in ("private", "sensitive") or row["status"] not in ("active", "superseded"):
                    raise ValueError("Invalid record in import.")
                if len(row["content"]) > 10000:
                    raise ValueError("Record too large in import.")
                cursor = db.execute("INSERT OR IGNORE INTO records(id,content,source,sensitivity,status,created_at,supersedes_id) VALUES (?,?,?,?,?,?,?)",
                    (rid, row["content"], row["source"], row["sensitivity"], row["status"], row["created_at"], row.get("supersedes_id")))
                count += cursor.rowcount
            db.execute("DELETE FROM records WHERE id IN (SELECT id FROM tombstones)")
            for tomb in claim_tombs:
                db.execute("INSERT OR IGNORE INTO claim_tombstones(id,deleted_at) VALUES (?,?)", (str(tomb["id"]), str(tomb["deleted_at"])))
            for claim in claims:
                cid, text, source_ids = str(claim["id"]), claim["text"], claim["source_ids"]
                if (not isinstance(text, str) or not 0 < len(text) <= rules.MAX_TEXT
                        or claim["origin"] not in rules.ORIGINS or claim["status"] not in rules.STATUSES
                        or not isinstance(source_ids, list) or not 0 < len(source_ids) <= rules.MAX_SOURCES
                        or len(set(map(str, source_ids))) != len(source_ids)):
                    raise ValueError("Invalid claim in import.")
                rules.validate_history(claim["history"], claim["origin"], claim["status"])
                if db.execute("SELECT 1 FROM claim_tombstones WHERE id=?", (cid,)).fetchone():
                    continue
                if db.execute("SELECT 1 FROM claims WHERE id=?", (cid,)).fetchone():
                    skipped += 1
                    continue
                created = claim["history"][0]
                db.execute("INSERT INTO claims(id,text,origin,status,created_at,supersedes_id) VALUES (?,?,?,'proposed',?,?)",
                           (cid, text, claim["origin"], str(claim["created_at"]),
                            None if claim.get("supersedes_id") is None else str(claim["supersedes_id"])))
                db.executemany("INSERT INTO claim_sources(claim_id,record_id) VALUES (?,?)", [(cid, str(r)) for r in source_ids])
                db.execute("INSERT INTO claim_events(claim_id,from_status,to_status,actor,note,at) VALUES (?,NULL,'proposed',?,?,?)",
                           (cid, created["actor"], created.get("note"), created["at"]))
                # Replay recorded human decisions (transition legality already checked above).
                for event in claim["history"][1:]:
                    self._record_transition(db, cid, event["from_status"], event["to_status"], event.get("note"), event["at"])
                claim_count += 1
                approved_count += claim["status"] == "approved"
        return {"imported": count, "claims_imported": claim_count,
                "approved_claims_restored": approved_count, "claims_skipped_existing": skipped}
