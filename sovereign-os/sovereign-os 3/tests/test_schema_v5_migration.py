"""Schema 4 -> 5 migration (ADR-0006, Issue #6): safety, equivalence, rollback and compatibility.

Every version-4 vault here was written by the released schema-4 code itself (`eeed753`, tests/fixtures/v4), not
an emulation: schema 5 adds evidence-set commitments (D-A), so the current code can no longer behave as v4 did.
Synthetic data only.
"""
from __future__ import annotations

import json
from pathlib import Path
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


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "v4"


def load_v4(name, tmp_path):
    """A genuine schema-4 vault produced by the released eeed753 code (tests/fixtures/v4)."""
    path = tmp_path / f"{name}.db"
    db = sqlite3.connect(path)
    db.execute("PRAGMA ignore_check_constraints=ON")
    db.executescript((FIXTURES / f"{name}.sql").read_text("utf-8"))
    db.close()
    return str(path)


class _Failing(sqlite3.Connection):
    """Records every statement and raises at the `occurrence`-th statement matching `fail_on`."""
    fail_on: str = ""
    occurrence: int = 1
    log: list = []

    def execute(self, sql, *args):
        cls = type(self)
        cls.log.append(sql)
        if cls.fail_on and sql.startswith(cls.fail_on) and sum(s.startswith(cls.fail_on) for s in cls.log) == cls.occurrence:
            raise sqlite3.OperationalError(f"injected failure at: {sql[:60]}")
        return super().execute(sql, *args)


def _inject(monkeypatch, fail_on, occurrence=1):
    _Failing.fail_on, _Failing.occurrence, _Failing.log = fail_on, occurrence, []
    shim = types.SimpleNamespace(**{k: getattr(sqlite3, k) for k in dir(sqlite3) if not k.startswith("__")})
    shim.connect = lambda *a, **k: sqlite3.connect(*a, factory=_Failing, **k)
    monkeypatch.setattr(store, "sqlite3", shim)


@pytest.mark.parametrize("fail_on,occurrence", [
    ("ALTER TABLE claim_tombstones__v5 RENAME", 1),   # after every trigger and all five original tables were dropped
    ("CREATE TRIGGER records_well_formed", 1),         # after the rebuild, while the trigger set is being recreated
    ("PRAGMA integrity_check", 2),                     # the post-rebuild verification (the first is the pre-rebuild scan)
])
def test_failed_migration_after_destructive_ddl_leaves_the_v4_vault_exactly_unchanged(tmp_path, monkeypatch, fail_on, occurrence):
    """F-8: the failure must come after destructive DDL, which the test proves from the statement log."""
    path = load_v4("v4_clean", tmp_path)
    before = dump(path)
    _inject(monkeypatch, fail_on, occurrence)
    with pytest.raises(sqlite3.OperationalError, match="injected failure"):
        Vault(path)
    log = _Failing.log
    failed_at = max(i for i, sql in enumerate(log) if sql.startswith(fail_on))
    executed = log[:failed_at]
    assert any(s.startswith("DROP TRIGGER") for s in executed), "no trigger was dropped before the failure"
    assert {f"DROP TABLE {t}" for t in store.ROWID_FREE_TABLES} <= set(executed), "tables were not dropped before the failure"
    monkeypatch.undo()
    assert dump(path) == before
    assert scalar(path, "PRAGMA user_version") == 4
    Vault(path)                                   # a later, uninterrupted open succeeds
    assert scalar(path, "PRAGMA user_version") == 5


# The schema-5 rules (ADR-0006 D-A, D-C): eight new triggers, and the claim Forget trigger also removes a commitment.
NEW_TRIGGERS = {"claim_evidence_sets_write_once", "claim_evidence_sets_no_update", "claim_evidence_sets_no_delete",
                "records_no_nul", "claims_no_nul", "claim_sources_no_nul", "claim_events_no_nul", "claim_tombstones_no_nul"}


def test_genuine_v4_vault_migrates_preserving_every_row_rule_and_export(tmp_path):
    """Equivalence on a vault written by the released v4 code itself, against that code's own export."""
    path = load_v4("v4_clean", tmp_path)
    export_v4 = json.loads((FIXTURES / "v4_clean.export.json").read_text("utf-8"))
    rows_v4, triggers_v4, indexes_v4, tables_v4 = rows(path), schema(path, "trigger"), schema(path, "index"), schema(path, "table")
    max_seq = max(r[0] for r in rows_v4["claim_events"])
    assert len(triggers_v4) == 36

    v = Vault(path)

    assert scalar(path, "PRAGMA user_version") == store.SCHEMA_VERSION == 5
    assert rows(path) == rows_v4                                  # every row of every canonical table, byte for byte
    assert scalar(path, "SELECT count(*) FROM claim_evidence_sets") == 0   # no commitment invented for an old claim
    triggers_v5 = schema(path, "trigger")
    assert set(triggers_v5) == set(triggers_v4) | NEW_TRIGGERS and len(triggers_v5) == 44
    assert {n: t for n, t in triggers_v5.items() if n in triggers_v4 and n != "claim_tombstones_forget"} == \
        {n: t for n, t in triggers_v4.items() if n != "claim_tombstones_forget"}       # identical text
    assert "DELETE FROM claim_evidence_sets WHERE claim_id = NEW.id" in triggers_v5["claim_tombstones_forget"]
    assert schema(path, "index") == indexes_v4
    tables_v5 = schema(path, "table")
    for table in store.ROWID_FREE_TABLES:              # exact definitions, plus WITHOUT ROWID only
        # ALTER TABLE ... RENAME stores the new name quoted; that token is the only other difference.
        renamed = tables_v5[table].replace(f'CREATE TABLE "{table}" ', f"CREATE TABLE {table} ", 1)
        assert renamed == tables_v4[table] + " WITHOUT ROWID"
    assert tables_v5["claim_events"] == tables_v4["claim_events"]
    assert set(tables_v5) == set(tables_v4) | {"claim_evidence_sets"}
    assert scalar(path, "PRAGMA integrity_check") == "ok"
    assert scalar(path, "SELECT count(*) FROM pragma_foreign_key_check") == 0

    # The export is the v4 export in format 3: identical, with each claim's `evidence_set` null (made before schema 5).
    export_v5 = v.export()
    assert export_v4["schema"] == "sovereign.v0.records.2" and export_v5["schema"] == "sovereign.v0.records.3"
    assert all(c.pop("evidence_set") is None for c in export_v5["claims"])
    assert strip(export_v5) == strip(export_v4)
    # D-A: history preserved, authority withdrawn until a human revalidates.
    approved = [c for c in v.list_claims() if c["status"] == "approved"]
    assert approved and all(c["integrity"] == "unconfirmed" and not c["authoritative"] for c in approved)
    assert all(len(c["history"]) > 1 for c in approved)

    # Everything legitimate still works, history keeps its sequence, and a new claim is committed at creation.
    r = v.add("Post-migration synthetic note")
    c = v.add_claim("Post-migration claim", [r["id"]])
    v.transition_claim(c["id"], "approved", expected_status="proposed")
    assert scalar(path, "SELECT min(seq) FROM claim_events WHERE claim_id=(SELECT id FROM claims WHERE text='Post-migration claim')") > max_seq
    assert [x for x in v.list_claims() if x["id"] == c["id"]][0]["authoritative"] is True
    assert v.delete(r["id"])["claims_forgotten"] == 1
    assert scalar(path, "SELECT count(*) FROM claim_evidence_sets") == 0   # forgotten with its claim
    restored = Vault(str(tmp_path / "restored.db"))
    restored.restore_trusted(v.export())
    assert strip(restored.export()) == strip(v.export())
    Vault(path)                                        # re-opening is idempotent
    assert schema(path, "table") == tables_v5


def test_fresh_and_migrated_vaults_have_the_same_schema(tmp_path):
    migrated = load_v4("v4_clean", tmp_path)
    Vault(migrated)
    fresh = str(tmp_path / "fresh.db")
    Vault(fresh)
    for kind in ("trigger", "index"):
        assert schema(fresh, kind) == schema(migrated, kind), kind
    # `records` and `tombstones` keep the text of the pre-claims software that created them (ADR-0002); every
    # table the claims schema or schema 5 created is identical.
    pre_claims = ("records", "tombstones")
    assert {n: t for n, t in schema(fresh, "table").items() if n not in pre_claims} == \
        {n: t for n, t in schema(migrated, "table").items() if n not in pre_claims}


def test_unverifiable_migration_is_refused_and_rolled_back(tmp_path, monkeypatch):
    """If post-rebuild verification fails (here: integrity_check reports a problem), nothing is committed."""
    path = load_v4("v4_clean", tmp_path)
    before = dump(path)

    class Lying(sqlite3.Connection):
        seen = 0

        def execute(self, sql, *args):
            if sql == "PRAGMA integrity_check":
                type(self).seen += 1
                if type(self).seen == 2:   # the post-rebuild verification; the first call is the pre-rebuild scan
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
    # Refused first by the pre-rebuild validity scan (ADR-0006, F-2); the rebuild's own NULL-key refusal is defence in depth.
    with pytest.raises(store.VaultStateInvalid, match="not_restorable"):
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


def test_concurrent_first_opens_of_a_v4_vault_migrate_once(tmp_path):
    path = load_v4("v4_clean", tmp_path)
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
    assert scalar(path, "SELECT count(*) FROM sqlite_master WHERE type='trigger'") == 44


def test_newer_vault_is_refused_after_v5(tmp_path):
    path = str(tmp_path / "v.db")
    Vault(path)
    db = sqlite3.connect(path)
    db.execute("PRAGMA user_version=6")
    db.commit()
    db.close()
    with pytest.raises(RuntimeError, match="newer"):
        Vault(path)


def to_format_2(export):
    """ADR-0006 reversal, step 1: a format-3 backup rewritten for v4 software (which knows formats 1 and 2)."""
    return {**export, "schema": "sovereign.v0.records.2",
            "claims": [{k: v for k, v in c.items() if k != "evidence_set"} for c in export["claims"]]}


def test_reversal_route_v5_backup_restores_into_v4_software_and_back(tmp_path):
    """ADR-0006 reversal. `v5_backup_as_format_2.json` is a schema-5 backup rewritten with `to_format_2`, and
    `v4_restored_from_v5_backup` is the vault the released v4 code made by restoring it. Back in schema 5 every row
    returns, but no claim is authoritative until revalidated: a format-2 backup carries no commitments (D-A)."""
    backup = json.loads((FIXTURES / "v5_backup_as_format_2.json").read_text("utf-8"))
    assert backup["schema"] == "sovereign.v0.records.2" and not any("evidence_set" in c for c in backup["claims"])
    path = load_v4("v4_restored_from_v5_backup", tmp_path)
    assert scalar(path, "PRAGMA user_version") == 4
    back = Vault(path)
    export = back.export()
    assert all(c.pop("evidence_set") is None for c in export["claims"])
    assert strip(export) == strip(backup)
    claims = back.list_claims()
    assert {c["status"] for c in claims} == {"approved", "contested"}
    assert all(c["integrity"] == "unconfirmed" and not c["authoritative"] for c in claims)
    # The rewrite itself, on a backup made now: only the format and the commitments change.
    v5 = Vault(str(tmp_path / "v5.db"))
    r = v5.add("Synthetic note")
    v5.add_claim("Synthetic claim", [r["id"]])
    export = v5.export()
    downgraded = to_format_2(export)
    assert strip({**downgraded, "claims": [{**c, "evidence_set": None} for c in downgraded["claims"]]}) == \
        strip({**export, "claims": [{**c, "evidence_set": None} for c in export["claims"]]})


def test_pre_existing_damage_is_refused_not_carried_forward(tmp_path):
    """A v4 vault damaged through Issue #6 so that no backup could restore it is refused (F-2), unchanged."""
    path = load_v4("v4_zero_link_loss", tmp_path)
    before = dump(path)
    with pytest.raises(store.VaultStateInvalid, match="claim_with_history_without_evidence"):
        Vault(path)
    assert dump(path) == before and scalar(path, "PRAGMA user_version") == 4
