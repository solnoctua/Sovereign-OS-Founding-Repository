"""Local source record vault.

Source records are evidence. Memory claims are separate, source-linked
interpretations that start as `proposed` and only become `approved` or
`rejected` through an explicit human decision (ADR-0003). Claim support is
derived at read time from the current evidence, so deleting a source record
immediately stops dependent claims from presenting as supported. The user
controls which sources, if any, are offered to a cloud model; claims are never
sent. Revision records are kept
locally; deletion clears content in the active DB and writes a content-free
identifier tombstone. Full secure erasure including backups/WAL is NOT provided.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Iterator
from uuid import uuid4


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Vault:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
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
                CREATE TABLE IF NOT EXISTS claims (
                    id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    origin TEXT NOT NULL CHECK(origin IN ('human', 'model')),
                    status TEXT NOT NULL DEFAULT 'proposed' CHECK(status IN ('proposed', 'approved', 'rejected')),
                    created_at TEXT NOT NULL,
                    decided_at TEXT,
                    CHECK((status = 'proposed') = (decided_at IS NULL))
                );
                -- No foreign key: evidence may be deleted while the claim remains as an orphan.
                CREATE TABLE IF NOT EXISTS claim_sources (
                    claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
                    record_id TEXT NOT NULL,
                    PRIMARY KEY (claim_id, record_id)
                );
                CREATE TABLE IF NOT EXISTS claim_tombstones (
                    id TEXT PRIMARY KEY,
                    deleted_at TEXT NOT NULL
                );
            """)

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
            return True

    # --- Memory claims -----------------------------------------------------

    def _claim(self, db: sqlite3.Connection, row: sqlite3.Row) -> dict:
        claim = dict(row)
        claim["source_ids"] = [r["record_id"] for r in db.execute(
            "SELECT record_id FROM claim_sources WHERE claim_id=? ORDER BY record_id", (claim["id"],))]
        # Support is derived from current evidence, never stored, so it cannot drift.
        states = []
        for rid in claim["source_ids"]:
            rec = db.execute("SELECT status FROM records WHERE id=?", (rid,)).fetchone()
            states.append(rec["status"] if rec else "missing")
        if any(state == "missing" for state in states):
            claim["support"] = "orphaned"   # a source was deleted (or never restored)
        elif any(state == "superseded" for state in states):
            claim["support"] = "stale"      # a source was corrected after the claim was made
        else:
            claim["support"] = "supported"
        claim["authoritative"] = claim["status"] == "approved" and claim["support"] == "supported"
        return claim

    def add_claim(self, text: str, source_ids: list[str], origin: str = "human") -> dict:
        """Create a claim. Always `proposed`; there is deliberately no status argument."""
        text = text.strip()
        if not text or len(text) > 2000:
            raise ValueError("Claim text must be between 1 and 2,000 characters.")
        if origin not in {"human", "model"}:
            raise ValueError("Invalid claim origin.")
        if not source_ids or len(source_ids) > 8 or len(set(source_ids)) != len(source_ids):
            raise ValueError("A claim needs 1-8 distinct source record IDs.")
        claim_id = str(uuid4())
        with self.connection() as db:
            for rid in source_ids:
                if not db.execute("SELECT 1 FROM records WHERE id=? AND status='active'", (rid,)).fetchone():
                    raise KeyError(f"Source record missing or superseded: {rid}")
            db.execute("INSERT INTO claims(id,text,origin,status,created_at) VALUES (?,?,?,'proposed',?)",
                       (claim_id, text, origin, stamp()))
            db.executemany("INSERT INTO claim_sources(claim_id,record_id) VALUES (?,?)",
                           [(claim_id, rid) for rid in source_ids])
            return self._claim(db, db.execute("SELECT * FROM claims WHERE id=?", (claim_id,)).fetchone())

    def list_claims(self, limit: int = 100) -> list[dict]:
        with self.connection() as db:
            rows = db.execute("SELECT * FROM claims ORDER BY created_at DESC,id DESC LIMIT ?", (min(limit, 200),)).fetchall()
            return [self._claim(db, row) for row in rows]

    def decide_claim(self, claim_id: str, decision: str) -> dict:
        """Explicit human decision. Only proposed claims with intact evidence may be approved."""
        if decision not in {"approved", "rejected"}:
            raise ValueError("Invalid decision.")
        with self.connection() as db:
            row = db.execute("SELECT * FROM claims WHERE id=?", (claim_id,)).fetchone()
            if row is None:
                raise KeyError("Claim not found.")
            claim = self._claim(db, row)
            if claim["status"] != "proposed":
                raise ValueError(f"Claim is already {claim['status']}; V0 decisions are final.")
            if decision == "approved" and claim["support"] != "supported":
                raise ValueError(f"Cannot approve a claim whose evidence is {claim['support']}.")
            db.execute("UPDATE claims SET status=?, decided_at=? WHERE id=?", (decision, stamp(), claim_id))
            return self._claim(db, db.execute("SELECT * FROM claims WHERE id=?", (claim_id,)).fetchone())

    def delete_claim(self, claim_id: str) -> bool:
        with self.connection() as db:
            if not db.execute("SELECT 1 FROM claims WHERE id=?", (claim_id,)).fetchone():
                return False
            db.execute("INSERT OR IGNORE INTO claim_tombstones(id,deleted_at) VALUES (?,?)", (claim_id, stamp()))
            db.execute("DELETE FROM claims WHERE id=?", (claim_id,))  # claim_sources cascade
            return True

    # --- Portability ----------------------------------------------------------

    def export(self) -> dict:
        with self.connection() as db:
            rows = db.execute("SELECT * FROM records ORDER BY created_at,id").fetchall()
            tombs = db.execute("SELECT * FROM tombstones ORDER BY deleted_at,id").fetchall()
            claims = [{k: c[k] for k in ("id", "text", "origin", "status", "created_at", "decided_at", "source_ids")}
                      for c in (self._claim(db, r) for r in db.execute("SELECT * FROM claims ORDER BY created_at,id"))]
            claim_tombs = db.execute("SELECT * FROM claim_tombstones ORDER BY deleted_at,id").fetchall()
            return {"schema": "sovereign.v0.records.2", "exported_at": stamp(),
                    "records": [dict(r) for r in rows], "tombstones": [dict(t) for t in tombs],
                    "claims": claims, "claim_tombstones": [dict(t) for t in claim_tombs]}

    def restore(self, payload: dict) -> dict:
        """Merge idempotently. Tombstones win over imported records and claims.

        Schema .1 (records only) is still accepted. Imported claims never overwrite a
        local claim, so import cannot change an existing decision. Claims whose
        evidence is tombstoned are kept but derive as `orphaned`, never authoritative.
        """
        if payload.get("schema") not in ("sovereign.v0.records.1", "sovereign.v0.records.2"):
            raise ValueError("Unsupported export schema.")
        records, tombs = payload.get("records"), payload.get("tombstones")
        claims, claim_tombs = payload.get("claims", []), payload.get("claim_tombstones", [])
        for items in (records, tombs, claims, claim_tombs):
            if not isinstance(items, list) or len(items) > 10000:
                raise ValueError("Invalid export lists.")
        count = claim_count = approved_count = 0
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
                cid = str(claim["id"])
                source_ids = claim["source_ids"]
                if (claim["origin"] not in ("human", "model") or claim["status"] not in ("proposed", "approved", "rejected")
                        or (claim["status"] == "proposed") != (claim.get("decided_at") is None)
                        or not isinstance(claim["text"], str) or not 0 < len(claim["text"]) <= 2000
                        or not isinstance(source_ids, list) or not 0 < len(source_ids) <= 8
                        or len(set(map(str, source_ids))) != len(source_ids)):
                    raise ValueError("Invalid claim in import.")
                if db.execute("SELECT 1 FROM claim_tombstones WHERE id=?", (cid,)).fetchone():
                    continue
                cursor = db.execute("INSERT OR IGNORE INTO claims(id,text,origin,status,created_at,decided_at) VALUES (?,?,?,?,?,?)",
                    (cid, claim["text"], claim["origin"], claim["status"], str(claim["created_at"]), claim.get("decided_at")))
                if cursor.rowcount:
                    db.executemany("INSERT INTO claim_sources(claim_id,record_id) VALUES (?,?)",
                                   [(cid, str(rid)) for rid in source_ids])
                    claim_count += 1
                    approved_count += claim["status"] == "approved"
            db.execute("DELETE FROM claims WHERE id IN (SELECT id FROM claim_tombstones)")
        return {"imported": count, "claims_imported": claim_count, "approved_claims_restored": approved_count}
