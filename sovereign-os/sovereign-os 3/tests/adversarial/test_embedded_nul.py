"""Founder decision D-C (2026-10-22, ADR-0006): no embedded NUL in current canonical text or identifiers.

SQLite's `length()` and its string functions stop at an embedded NUL while Python counts every character, so storage
bounds could not be trusted for such text (F-4). Schema 5 rejects it at both boundaries: application validators and
storage triggers (which a connection cannot switch off as it can CHECK constraints). Legacy ADR-0002 records keep
theirs exactly; a schema 4 vault holding NUL in current text is refused, unchanged, rather than altered.
Old vaults are genuine schema-4 fixtures written by the released eeed753 code. Synthetic data only.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from sovereign import claims as rules
from sovereign import store
from sovereign.app import create_app
from sovereign.store import Vault

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "v4"
T = "2026-10-22T00:00:00+00:00"
NUL = "\x00"


def load_v4(name: str, tmp_path: Path) -> str:
    path = tmp_path / f"{name}.db"
    db = sqlite3.connect(path)
    db.execute("PRAGMA ignore_check_constraints=ON")
    db.executescript((FIXTURES / f"{name}.sql").read_text("utf-8"))
    db.close()
    return str(path)


def dump(path: str) -> list[str]:
    db = sqlite3.connect(path)
    try:
        return list(db.iterdump())
    finally:
        db.close()


def raw(vault: Vault):
    db = sqlite3.connect(vault.path, isolation_level=None)
    db.execute("PRAGMA ignore_check_constraints=ON")
    return db


@pytest.fixture
def vault(tmp_path):
    return Vault(str(tmp_path / "vault.db"))


def world(vault: Vault):
    r = vault.add("Ordinary evidence")
    c = vault.add_claim("Ordinary claim", [r["id"]])
    return r, c


# --- Storage boundary ------------------------------------------------------------------------------

STORAGE_CASES = [
    ("records", "INSERT INTO records(id,content,source,sensitivity,status,created_at) VALUES(?,?,?,?,?,?)",
     [("r\x00", "c", "manual", "private", "active", T), ("r2", "c\x00", "manual", "private", "active", T),
      ("r3", "c", "man\x00ual", "private", "active", T), ("r4", "c", "manual", "private", "active", T + NUL)]),
    ("claims", "INSERT INTO claims(id,text,origin,status,created_at) VALUES(?,?,'human','proposed',?)",
     [("c\x00", "text", T), ("c2", "te\x00xt", T), ("c3", "text", T + NUL)]),
    ("claim_events", "INSERT INTO claim_events(claim_id,from_status,to_status,actor,note,at) VALUES(?,NULL,'proposed','human',?,?)",
     [("{claim}", "no\x00te", T), ("{claim}", None, T + NUL)]),
    ("claim_tombstones", "INSERT INTO claim_tombstones(id,deleted_at) VALUES(?,?)", [("gone\x00", T)]),
]


@pytest.mark.parametrize("table,sql,rows", STORAGE_CASES)
def test_storage_refuses_embedded_nul_even_with_check_constraints_off(vault, table, sql, rows):
    r = vault.add("Evidence for a raw claim")
    db = raw(vault)
    db.execute("INSERT INTO claims(id,text,origin,status,created_at) VALUES('raw','Raw claim','human','proposed',?)", (T,))
    db.execute("INSERT INTO claim_sources(claim_id,record_id,evidence_sha256) VALUES('raw',?,?)", (r["id"], store.evidence_hash(r)))
    before = db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    for values in rows:
        values = tuple("raw" if v == "{claim}" else v for v in values)
        with pytest.raises(sqlite3.IntegrityError, match="embedded NUL"):
            db.execute(sql, values)
    assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == before
    with pytest.raises(sqlite3.IntegrityError, match="embedded NUL"):   # an evidence link naming a NUL id
        db.execute("INSERT INTO claim_sources(claim_id,record_id,evidence_sha256) VALUES('raw',?,NULL)", ("x\x00",))
    db.close()


def test_a_legacy_record_keeps_its_embedded_nul_through_storage_export_and_restore(vault, tmp_path):
    db = raw(vault)
    db.execute("INSERT INTO records(id,content,source,sensitivity,status,created_at,legacy) "
               "VALUES('legacy/nul', 'Legacy' || char(0) || 'note', 'manual','private','active',?,1)", (T,))
    db.close()
    export = vault.export()
    legacy = next(r for r in export["records"] if r["id"] == "legacy/nul")
    assert legacy["content"] == "Legacy\x00note" and legacy["legacy"] == 1
    target = Vault(str(tmp_path / "target.db"))
    target.restore_trusted(export)
    assert next(r for r in target.export()["records"] if r["id"] == "legacy/nul")["content"] == "Legacy\x00note"


# --- Application boundary --------------------------------------------------------------------------

def test_every_write_operation_rejects_embedded_nul_and_changes_nothing(vault):
    r, c = world(vault)
    before = {k: v for k, v in vault.export().items() if k != "exported_at"}
    attempts = [
        lambda: vault.add("Note with a\x00NUL"),
        lambda: vault.add("A correction", supersedes_id="r\x00"),
        lambda: vault.add_claim("Claim with a\x00NUL", [r["id"]]),
        lambda: vault.add_claim("Claim citing a NUL id", ["x\x00"]),
        lambda: vault.transition_claim(c["id"], "contested", note="why\x00", expected_status="proposed"),
        lambda: vault.supersede_claim(c["id"], "Replacement\x00", [r["id"]], expected_status="proposed"),
        lambda: vault.supersede_claim(c["id"], "Replacement", [r["id"]], note="n\x00", expected_status="proposed"),
    ]
    for attempt in attempts:
        with pytest.raises((ValueError, KeyError)):
            attempt()
    assert {k: v for k, v in vault.export().items() if k != "exported_at"} == before


@pytest.mark.parametrize("damage", ["record_content", "record_id", "claim_text", "history_note", "claim_tombstone"])
def test_import_and_restore_reject_embedded_nul_in_current_text(vault, tmp_path, damage):
    world(vault)
    backup = vault.export()
    record, claim = backup["records"][0], backup["claims"][0]
    if damage == "record_content":
        backup["records"][0] = {**record, "content": "x\x00y"}
    elif damage == "record_id":
        backup["records"][0] = {**record, "id": "r\x00"}
    elif damage == "claim_text":
        backup["claims"][0] = {**claim, "text": "t\x00"}
    elif damage == "history_note":
        backup["claims"][0] = {**claim, "history": [{**claim["history"][0], "note": "n\x00"}]}
    else:
        backup["claim_tombstones"] = [{"id": "gone\x00", "deleted_at": T}]
    target = Vault(str(tmp_path / "target.db"))
    with pytest.raises(ValueError):
        target.restore_trusted(backup)
    if damage != "history_note":   # an ordinary import ignores history, so it validates only what it would write
        with pytest.raises(ValueError):
            target.import_untrusted(backup)
    assert target.export()["records"] == [] and target.export()["claims"] == []


def test_the_api_rejects_embedded_nul_with_422(tmp_path):
    client = TestClient(create_app(str(tmp_path / "api.db")))
    assert client.post("/api/memories", json={"content": "a\x00b"}).status_code == 422
    rid = client.post("/api/memories", json={"content": "ordinary"}).json()["id"]
    assert client.post("/api/claims", json={"text": "c\x00", "source_ids": [rid]}).status_code == 422


# --- Migration --------------------------------------------------------------------------------------

def test_a_schema_4_vault_with_nul_in_current_text_is_refused_unchanged(tmp_path):
    path = load_v4("v4_nul_short", tmp_path)
    before = dump(path)
    with pytest.raises(store.VaultStateInvalid, match="embedded_nul"):
        Vault(path)
    assert dump(path) == before


def test_a_schema_4_vault_with_nul_only_in_a_legacy_record_migrates_and_keeps_it(tmp_path):
    path = load_v4("v4_legacy_nul", tmp_path)
    db = sqlite3.connect(path)
    before = db.execute("SELECT * FROM records WHERE id='legacy/nul'").fetchone()
    db.close()
    vault = Vault(path)
    db = sqlite3.connect(path)
    assert db.execute("PRAGMA user_version").fetchone()[0] == 5
    assert db.execute("SELECT * FROM records WHERE id='legacy/nul'").fetchone() == before
    db.close()
    assert next(r for r in vault.export()["records"] if r["id"] == "legacy/nul")["content"] == "Legacy\x00note"


def test_sqlite_and_python_lengths_agree_for_all_current_text(tmp_path):
    vault = Vault(load_v4("v4_legacy_nul", tmp_path))
    r = vault.add("Synthetic note")
    c = vault.add_claim("Synthetic claim", [r["id"]])
    vault.transition_claim(c["id"], "contested", note="unsure", expected_status="proposed")
    db = sqlite3.connect(vault.path)
    for table, column, where in [("records", "content", "legacy = 0"), ("records", "id", "legacy = 0"), ("claims", "text", "1"),
                                 ("claim_events", "note", "note IS NOT NULL"), ("claim_evidence_sets", "digest", "1")]:
        for value, length in db.execute(f"SELECT {column}, length({column}) FROM {table} WHERE {where}"):
            assert len(value) == length, (table, column)
    db.close()
    assert rules.MAX_TEXT == 2000   # the bound the claims CHECK states is now exact for every current value
