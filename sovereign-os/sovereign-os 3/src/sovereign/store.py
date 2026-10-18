"""Local source record vault.

V0 deliberately stores source records, not AI-authored claims. The user controls
which sources, if any, are offered to a cloud model. Revision records are kept
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
            """)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA secure_delete=ON")
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

    def export(self) -> dict:
        with self.connection() as db:
            rows = db.execute("SELECT * FROM records ORDER BY created_at,id").fetchall()
            tombs = db.execute("SELECT * FROM tombstones ORDER BY deleted_at,id").fetchall()
            return {"schema": "sovereign.v0.records.1", "exported_at": stamp(),
                    "records": [dict(r) for r in rows], "tombstones": [dict(t) for t in tombs]}

    def restore(self, payload: dict) -> dict:
        """Merge idempotently. Tombstones win over imported records."""
        if payload.get("schema") != "sovereign.v0.records.1":
            raise ValueError("Unsupported export schema.")
        records, tombs = payload.get("records"), payload.get("tombstones")
        if not isinstance(records, list) or not isinstance(tombs, list) or len(records) > 10000 or len(tombs) > 10000:
            raise ValueError("Invalid export lists.")
        count = 0
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
        return {"imported": count}
