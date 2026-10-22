"""Schema 4 -> 5 migration (ADR-0006, Issue #6): safety, equivalence, rollback and compatibility.

A genuine version-4 vault is produced by this very code with the 4 -> 5 step disabled
(`SCHEMA_VERSION` = 4 and a no-op rebuild), because the version-4 schema text (BASE_SCHEMA,
LEGACY_SCHEMA, CLAIMS_SCHEMA) is unchanged in version 5. Synthetic data only.
"""
from __future__ import annotations

import sqlite3
import threading
import types

import pytest

from sovereign import store
from sovereign.store import Vault

T = "2026-10-01T00:00:00+00:00"
TABLES = {"records": "id", "tombstones": "id", "claims": "id", "claim_sources": "claim_id, record_id",
          "claim_tombstones": "id", "claim_events": "seq"}


def strip(export):
    return {k: export[k] for k in ("records", "tombstones", "claims", "claim_tombstones")}


def rows(path):
    db = sqlite3.connect(path)
    try:
        return {t: db.execute(f"SELECT * FROM {t} ORDER BY {k}").fetchall() for t, k in TABLES.items()}
    finally:
        db.close()


def schema(path, kind):
    db = sqlite3.connect(path)
    try:
        return dict(db.execute("SELECT name, sql FROM sqlite_master WHERE type=? AND sql IS NOT NULL", (kind,)).fetchall())
    finally:
        db.close()


def scalar(path, sql):
    db = sqlite3.connect(path)
    try:
        return db.execute(sql).fetchone()[0]
    finally:
        db.close()


def dump(path):
    db = sqlite3.connect(path)
    try:
        return list(db.iterdump())
    finally:
        db.close()


@pytest.fixture
def as_version_4(monkeypatch):
    """Context in which Vault behaves exactly like the released schema-4 software."""
    def enable():
        monkeypatch.setattr(store, "SCHEMA_VERSION", 4)
        monkeypatch.setattr(store, "_rebuild_without_rowid", lambda db: None)
    return enable


def populated_v4(path, as_version_4, monkeypatch):
    """A version-4 vault with legacy rows, corrections, every claim status, Forget and claim Forget."""
    db = sqlite3.connect(path)
    db.executescript(f"""
        CREATE TABLE records (id TEXT PRIMARY KEY, content TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'manual',
          sensitivity TEXT NOT NULL CHECK(sensitivity IN ('private','sensitive')), status TEXT NOT NULL CHECK(status IN ('active','superseded')),
          created_at TEXT NOT NULL, supersedes_id TEXT);
        CREATE TABLE tombstones (id TEXT PRIMARY KEY, deleted_at TEXT NOT NULL);
        INSERT INTO records VALUES ('legacy/1','Legacy synthetic note','manual','private','active','{T}',NULL);
        INSERT INTO tombstones VALUES ('legacy-gone','{T}');
    """)
    db.close()
    as_version_4()
    v = Vault(path)
    a = v.add("Synthetic note A")
    b = v.add("Synthetic note B, sensitive", "sensitive")
    a2 = v.add("Synthetic note A, corrected", supersedes_id=a["id"])
    approved = v.add_claim("Approved claim", [a2["id"], "legacy/1"])
    v.transition_claim(approved["id"], "approved", expected_status="proposed")
    contested = v.add_claim("Contested claim", [b["id"]])
    v.transition_claim(contested["id"], "contested", note="unsure", expected_status="proposed")
    rejected = v.add_claim("Rejected claim", [a2["id"]])
    v.transition_claim(rejected["id"], "rejected", expected_status="proposed")
    old = v.add_claim("Claim to supersede", [a2["id"]])
    v.supersede_claim(old["id"], "Superseding claim", [a2["id"]], expected_status="proposed")
    v.delete_claim(v.add_claim("Claim to forget", [b["id"]])["id"])
    v.delete(v.add("Synthetic note to forget")["id"])
    export = v.export()
    monkeypatch.undo()
    assert scalar(path, "PRAGMA user_version") == 4
    return export


def test_v4_vault_migrates_to_v5_preserving_every_row_rule_and_export(tmp_path, as_version_4, monkeypatch):
    path = str(tmp_path / "v4.db")
    export_v4 = populated_v4(path, as_version_4, monkeypatch)
    rows_v4, triggers_v4, indexes_v4 = rows(path), schema(path, "trigger"), schema(path, "index")
    tables_v4 = schema(path, "table")
    max_seq = max(r[0] for r in rows_v4["claim_events"])

    v = Vault(path)

    assert scalar(path, "PRAGMA user_version") == store.SCHEMA_VERSION == 5
    assert rows(path) == rows_v4                       # every row of every canonical table, byte for byte
    assert schema(path, "trigger") == triggers_v4      # all 36 triggers, identical text
    assert len(triggers_v4) == 36
    assert schema(path, "index") == indexes_v4
    tables_v5 = schema(path, "table")
    for table in store.ROWID_FREE_TABLES:              # exact definitions, plus WITHOUT ROWID only
        # ALTER TABLE ... RENAME stores the new name quoted; that token is the only other difference.
        renamed = tables_v5[table].replace(f'CREATE TABLE "{table}" ', f"CREATE TABLE {table} ", 1)
        assert renamed == tables_v4[table] + " WITHOUT ROWID"
    assert tables_v5["claim_events"] == tables_v4["claim_events"]
    assert scalar(path, "PRAGMA integrity_check") == "ok"
    assert scalar(path, "SELECT count(*) FROM pragma_foreign_key_check") == 0
    assert strip(v.export()) == strip(export_v4)

    # Everything legitimate still works, and history keeps its sequence.
    r = v.add("Post-migration synthetic note")
    c = v.add_claim("Post-migration claim", [r["id"]])
    v.transition_claim(c["id"], "approved", expected_status="proposed")
    assert scalar(path, "SELECT min(seq) FROM claim_events WHERE claim_id=(SELECT id FROM claims WHERE text='Post-migration claim')") > max_seq
    assert v.delete(r["id"])["claims_forgotten"] == 1
    Vault(path)                                        # re-opening is idempotent
    assert schema(path, "table") == tables_v5


def test_failed_migration_leaves_the_v4_vault_exactly_unchanged(tmp_path, as_version_4, monkeypatch):
    path = str(tmp_path / "v4.db")
    populated_v4(path, as_version_4, monkeypatch)
    before = dump(path)
    # Fail after every trigger has been dropped and all five tables rebuilt: the worst point.
    monkeypatch.setattr(store, "ROWID_FREE_TABLES", store.ROWID_FREE_TABLES + ("no_such_table",))
    with pytest.raises(sqlite3.OperationalError):
        Vault(path)
    assert dump(path) == before
    assert scalar(path, "PRAGMA user_version") == 4
    monkeypatch.undo()
    Vault(path)
    assert scalar(path, "PRAGMA user_version") == 5


def test_unverifiable_migration_is_refused_and_rolled_back(tmp_path, as_version_4, monkeypatch):
    """If post-rebuild verification fails (here: integrity_check reports a problem), nothing is committed."""
    path = str(tmp_path / "v4.db")
    populated_v4(path, as_version_4, monkeypatch)
    before = dump(path)

    class Lying(sqlite3.Connection):
        def execute(self, sql, *args):
            if sql == "PRAGMA integrity_check":
                return super().execute("SELECT 'corrupt'")
            return super().execute(sql, *args)

    shim = types.SimpleNamespace(**{k: getattr(sqlite3, k) for k in dir(sqlite3) if not k.startswith("__")})
    shim.connect = lambda *a, **k: sqlite3.connect(*a, factory=Lying, **k)
    monkeypatch.setattr(store, "sqlite3", shim)
    with pytest.raises(RuntimeError, match="could not be verified"):
        Vault(path)
    monkeypatch.undo()
    assert dump(path) == before
    assert scalar(path, "PRAGMA user_version") == 4


def test_null_primary_key_in_a_malformed_legacy_vault_is_refused(tmp_path):
    path = str(tmp_path / "v0.db")
    db = sqlite3.connect(path)
    db.executescript(f"""
        CREATE TABLE records (id TEXT PRIMARY KEY, content TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'manual',
          sensitivity TEXT NOT NULL CHECK(sensitivity IN ('private','sensitive')), status TEXT NOT NULL CHECK(status IN ('active','superseded')),
          created_at TEXT NOT NULL, supersedes_id TEXT);
        CREATE TABLE tombstones (id TEXT PRIMARY KEY, deleted_at TEXT NOT NULL);
        INSERT INTO records VALUES (NULL,'Malformed legacy note','manual','private','active','{T}',NULL);
    """)
    db.close()
    before = dump(path)
    with pytest.raises(RuntimeError, match="NULL primary key"):
        Vault(path)
    assert dump(path) == before
    assert scalar(path, "PRAGMA user_version") == 0


def test_records_only_vault_migrates_directly_to_v5(tmp_path):
    path = str(tmp_path / "v0.db")
    db = sqlite3.connect(path)
    db.executescript(f"""
        CREATE TABLE records (id TEXT PRIMARY KEY, content TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'manual',
          sensitivity TEXT NOT NULL CHECK(sensitivity IN ('private','sensitive')), status TEXT NOT NULL CHECK(status IN ('active','superseded')),
          created_at TEXT NOT NULL, supersedes_id TEXT);
        CREATE TABLE tombstones (id TEXT PRIMARY KEY, deleted_at TEXT NOT NULL);
        INSERT INTO records VALUES ('r1','Legacy synthetic note','manual','private','active','{T}',NULL);
    """)
    db.close()
    Vault(path)
    assert scalar(path, "PRAGMA user_version") == 5
    for table in store.ROWID_FREE_TABLES:
        assert schema(path, "table")[table].endswith("WITHOUT ROWID")
    assert scalar(path, "SELECT legacy FROM records WHERE id='r1'") == 1


def test_concurrent_first_opens_of_a_v4_vault_migrate_once(tmp_path, as_version_4, monkeypatch):
    path = str(tmp_path / "v4.db")
    populated_v4(path, as_version_4, monkeypatch)
    before = rows(path)
    errors, barrier = [], threading.Barrier(4)

    def open_vault():
        try:
            barrier.wait()
            Vault(path)
        except Exception as exc:   # pragma: no cover - reported below
            errors.append(exc)

    threads = [threading.Thread(target=open_vault) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert scalar(path, "PRAGMA user_version") == 5
    assert rows(path) == before
    assert scalar(path, "SELECT count(*) FROM sqlite_master WHERE type='trigger'") == 36


def test_newer_vault_is_refused_after_v5(tmp_path):
    path = str(tmp_path / "v.db")
    Vault(path)
    db = sqlite3.connect(path)
    db.execute("PRAGMA user_version=6")
    db.commit()
    db.close()
    with pytest.raises(RuntimeError, match="newer"):
        Vault(path)


def test_reversal_route_v5_export_restores_into_v4_software_and_back(tmp_path, as_version_4, monkeypatch):
    """ADR-0006 reversal: the export format is unchanged, so a v5 export restores into v4 software."""
    v5 = Vault(str(tmp_path / "v5.db"))
    a = v5.add("Synthetic note")
    c = v5.add_claim("Synthetic claim", [a["id"]])
    v5.transition_claim(c["id"], "approved", expected_status="proposed")
    v5.delete(v5.add("Forgotten synthetic note")["id"])
    export_v5 = v5.export()
    as_version_4()
    v4 = Vault(str(tmp_path / "v4.db"))
    v4.restore_trusted(export_v5)
    assert strip(v4.export()) == strip(export_v5)
    assert scalar(v4.path, "PRAGMA user_version") == 4
    monkeypatch.undo()
    back = Vault(str(tmp_path / "back.db"))
    back.restore_trusted(v4.export())
    assert strip(back.export()) == strip(export_v5)


def test_pre_existing_damage_is_preserved_not_hidden_or_refused(tmp_path, as_version_4, monkeypatch):
    """A v4 vault already damaged through Issue #6 migrates faithfully; derivation keeps it non-authoritative."""
    path = str(tmp_path / "v4.db")
    as_version_4()
    v = Vault(path)
    a = v.add("Synthetic evidence")
    c = v.add_claim("Approved synthetic claim", [a["id"]])
    v.transition_claim(c["id"], "approved", expected_status="proposed")
    monkeypatch.undo()
    db = sqlite3.connect(path, isolation_level=None)   # the Issue #6 attack, on v4, default pragmas
    rowid = db.execute("SELECT rowid FROM claim_sources WHERE claim_id=?", (c["id"],)).fetchone()[0]
    db.execute("INSERT INTO claims(id,text,origin,status,created_at) VALUES('atk','x','human','proposed',?)", (T,))
    db.execute("INSERT OR REPLACE INTO claim_sources(rowid,claim_id,record_id) VALUES(?,'atk',?)", (rowid, a["id"]))
    db.close()
    damaged = rows(path)
    v = Vault(path)
    assert rows(path) == damaged
    claim = next(x for x in v.list_claims() if x["id"] == c["id"])
    assert claim["source_ids"] == [] and claim["support"] == "orphaned" and claim["authoritative"] is False
