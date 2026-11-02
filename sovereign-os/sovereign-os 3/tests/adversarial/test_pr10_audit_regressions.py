"""Regressions for the independent Codex audit of PR #10 (audited head 04ba75c): findings F-1 to F-4.

The audit report is reviewer-owned and is not reproduced or paraphrased here. These tests encode the
builder's own reproduction of each finding as summarized in the founder's remediation directive of
2026-10-22, using genuine schema-4 fixtures produced by the released eeed753 code (tests/fixtures/v4).
The two tests that depended on a founder policy decision (F-1, F-4) were strict expected failures until the
founder decided D-A (A1) and D-C (C1) on 2026-10-22; they now pass against those implementations. The decisions'
own regressions are in test_evidence_set_commitments.py and test_embedded_nul.py. Synthetic data only.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from sovereign import claims as rules
from sovereign import context, store
from sovereign.app import create_app
from sovereign.store import Vault

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "v4"
T = "2026-10-22T00:00:00+00:00"
PROVIDERS = ("local", "kimi", "openai")


def load_v4(name: str, tmp_path: Path) -> str:
    path = tmp_path / f"{name}.db"
    db = sqlite3.connect(path)
    db.execute("PRAGMA ignore_check_constraints=ON")   # the damaged fixtures hold the violations the attacker left
    db.executescript((FIXTURES / f"{name}.sql").read_text("utf-8"))
    db.close()
    return str(path)


def dump(path: str) -> list[str]:
    db = sqlite3.connect(path)
    try:
        return list(db.iterdump())
    finally:
        db.close()


def user_version(path: str) -> int:
    db = sqlite3.connect(path)
    try:
        return db.execute("PRAGMA user_version").fetchone()[0]
    finally:
        db.close()


def by_text(vault: Vault, prefix: str) -> dict:
    return next(c for c in vault.list_claims() if c["text"].startswith(prefix))


def strip(export: dict) -> dict:
    return {k: export[k] for k in ("records", "tombstones", "claims", "claim_tombstones")}


def raw_counts(path: str) -> dict:
    db = sqlite3.connect(path)
    try:
        return {t: db.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                for t in ("records", "tombstones", "claims", "claim_sources", "claim_events", "claim_tombstones")}
    finally:
        db.close()


def raw(vault: Vault):
    db = sqlite3.connect(vault.path, isolation_level=None)
    db.execute("PRAGMA ignore_check_constraints=ON")   # an ordinary connection: a per-connection pragma, not a schema change
    return db


# --- F-1: partial evidence-set loss across the v4 migration ------------------------------------

def test_f1_claim_that_lost_part_of_its_evidence_before_migration_is_not_authoritative(tmp_path):
    """Founder decision D-A (A1): every claim made before schema 5 is preserved but not authoritative until a human
    revalidates it, because schema 4 never recorded how many links a claim had."""
    vault = Vault(load_v4("v4_partial_link_loss", tmp_path))
    claim = by_text(vault, "Approved claim resting on evidence one AND evidence two")
    assert claim["status"] == "approved" and len(claim["source_ids"]) == 1   # history is preserved, nothing invented
    assert claim["support"] == "supported"          # the surviving link alone looks intact ...
    assert claim["integrity"] == "unconfirmed" and claim["authoritative"] is False   # ... but completeness is unproven
    for provider in PROVIDERS:
        bundle = context.compile_context(vault, "approved claim resting evidence", provider, [])
        assert claim["id"] not in [i.candidate.id for i in bundle.included]
        assert {e.candidate.id: e.reason for e in bundle.excluded}[claim["id"]] == "revalidation_required"


def test_f1_migration_does_not_invent_or_erase(tmp_path):
    """Policy-independent half of F-1: whatever is decided, migration must not invent links or erase history."""
    path = load_v4("v4_partial_link_loss", tmp_path)
    before = raw_counts(path)
    vault = Vault(path)
    assert raw_counts(path) == before
    claim = by_text(vault, "Approved claim resting on evidence one AND evidence two")
    assert [e["to_status"] for e in claim["history"]] == ["proposed", "approved"]


# --- F-2: damaged states versus backup and restore ---------------------------------------------

@pytest.mark.parametrize("fixture", ["v4_zero_link_loss", "v4_claim_row_replaced", "v4_check_bypass", "v4_nul_lengths"])
def test_f2_vault_holding_states_no_backup_could_restore_is_not_migrated(tmp_path, fixture):
    path = load_v4(fixture, tmp_path)
    before = dump(path)
    with pytest.raises(store.VaultStateInvalid) as refused:
        Vault(path)
    assert refused.value.findings                         # named classes, never row contents
    assert dump(path) == before and user_version(path) == 4


@pytest.mark.parametrize("fixture", ["v4_clean", "v4_partial_link_loss"])
def test_f2_every_vault_that_migrates_backs_up_and_restores_losslessly(tmp_path, fixture):
    path = load_v4(fixture, tmp_path)
    vault = Vault(path)
    export = vault.export()
    restored = Vault(str(tmp_path / "restored.db"))
    restored.restore_trusted(export)
    assert strip(restored.export()) == strip(export)
    assert raw_counts(restored.path) == raw_counts(path)   # no orphan row silently dropped


def test_f2_export_refuses_a_live_state_that_restore_would_reject(tmp_path):
    vault = Vault(str(tmp_path / "live.db"))
    r = vault.add("Synthetic evidence")
    c = vault.add_claim("Approved synthetic claim", [r["id"]])
    vault.transition_claim(c["id"], "approved", expected_status="proposed")
    db = sqlite3.connect(vault.path, isolation_level=None)   # a schema-level process, outside the K1 model
    db.execute("DROP TRIGGER claim_sources_fixed_delete")
    db.execute("DELETE FROM claim_sources")
    db.close()
    with pytest.raises(store.VaultStateInvalid):
        vault.export()
    client = TestClient(create_app(vault.path))
    response = client.get("/api/export")
    assert response.status_code == 409 and "attachment" not in response.headers.get("content-disposition", "")


# --- F-3: positive validation of evidence states -------------------------------------------------

@pytest.mark.parametrize("states,expected", [
    ([], "orphaned"), (["active"], "supported"), (["active", "superseded"], "stale"),
    (["archived"], "orphaned"), (["active", "pending"], "orphaned"), (["ACTIVE"], "orphaned"),
    ([None], "orphaned"), (["active", "missing"], "orphaned"), (["unverified"], "orphaned"),
])
def test_f3_support_requires_known_verified_states(states, expected):
    assert rules.support_of(states) == expected


def test_f3_record_in_an_unknown_state_never_enters_any_context(tmp_path):
    vault = Vault(str(tmp_path / "live.db"))
    db = raw(vault)
    db.execute("INSERT INTO records(id,content,source,sensitivity,status,created_at) "
               "VALUES('odd','Quarterly figures draft','manual','private','pending',?)", (T,))
    db.close()
    for provider in PROVIDERS:
        bundle = context.compile_context(vault, "quarterly figures", provider, [])
        assert "odd" not in [i.candidate.id for i in bundle.included]
        excluded = {e.candidate.id: e for e in bundle.excluded}
        assert excluded["odd"].reason == "invalid_state"


def test_f3_claim_on_evidence_in_an_unknown_state_is_sensitive_unsupported_and_unapprovable(tmp_path):
    vault = Vault(str(tmp_path / "live.db"))
    db = raw(vault)
    db.execute("INSERT INTO records(id,content,source,sensitivity,status,created_at) "
               "VALUES('odd','Note in an unknown state','manual','private','archived',?)", (T,))
    record = dict(zip(("id", "content", "source", "sensitivity", "created_at", "supersedes_id"),
                      ("odd", "Note in an unknown state", "manual", "private", T, None)))
    db.execute("INSERT INTO claims(id,text,origin,status,created_at) VALUES('c-odd','Claim on an odd note','human','proposed',?)", (T,))
    db.execute("INSERT INTO claim_sources(claim_id,record_id,evidence_sha256) VALUES('c-odd','odd',?)", (store.evidence_hash(record),))
    db.execute("INSERT INTO claim_events(claim_id,from_status,to_status,actor,at) VALUES('c-odd',NULL,'proposed','human',?)", (T,))
    db.close()
    claim = next(c for c in vault.list_claims() if c["id"] == "c-odd")
    assert claim["support"] == "orphaned" and claim["authoritative"] is False
    assert context.inherited_sensitivity(claim["sources"]) == "sensitive"
    with pytest.raises(rules.TransitionError):
        vault.transition_claim("c-odd", "approved", expected_status="proposed")


# --- F-4: SQLite and Python length semantics -----------------------------------------------------

def test_f4_length_hidden_behind_an_embedded_nul_is_never_exported(tmp_path):
    """Schema 5 refuses an embedded NUL in current text (D-C), so only a legacy record can still hide length from
    SQLite; the validity scan measures it in Python and refuses the export."""
    vault = Vault(str(tmp_path / "live.db"))
    vault.add("Ordinary evidence")
    db = raw(vault)
    db.execute("INSERT INTO records(id,content,source,sensitivity,status,created_at,legacy) "
               "VALUES('legacy-nul','N' || char(0) || ?, 'manual','private','active',?,1)", ("x" * 10050, T))
    db.close()
    with pytest.raises(store.VaultStateInvalid, match="not_restorable"):
        vault.export()


def test_f4_every_text_value_in_a_migrated_clean_vault_measures_the_same_in_sqlite_and_python(tmp_path):
    path = load_v4("v4_clean", tmp_path)
    Vault(path)
    db = sqlite3.connect(path)
    for table, column in [("records", "id"), ("records", "content"), ("records", "source"), ("claims", "id"),
                          ("claims", "text"), ("claim_events", "note"), ("tombstones", "id")]:
        for value, sqlite_length in db.execute(f"SELECT {column}, length({column}) FROM {table} WHERE {column} IS NOT NULL"):
            assert len(value) == sqlite_length, (table, column)
    db.close()


@pytest.mark.parametrize("table,sql,values", [
    ("claims", "INSERT INTO claims(id,text,origin,status,created_at) VALUES('c-nul',?,'human','proposed',?)",
     ("C\x00" + "y" * 2500, T)),
    ("claims", "INSERT INTO claims(id,text,origin,status,created_at) VALUES('c-nul',?,'human','proposed',?)", ("C\x00y", T)),
    ("records", "INSERT INTO records(id,content,source,sensitivity,status,created_at) VALUES('r-nul',?,'manual','private','active',?)",
     ("R\x00" + "x" * 10050, T)),
])
def test_f4_storage_itself_refuses_text_whose_true_length_exceeds_its_bound(tmp_path, table, sql, values):
    """Founder decision D-C (C1): storage refuses an embedded NUL in current canonical text, by trigger, so a
    connection that switches CHECK constraints off cannot store a length SQLite does not count."""
    vault = Vault(str(tmp_path / "live.db"))
    db = raw(vault)                                   # ignore_check_constraints=ON
    with pytest.raises(sqlite3.IntegrityError, match="embedded NUL"):
        db.execute(sql, values)
    assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
    db.close()


# --- Independent adversarial review of the validity scan (2026-10-22) --------------------------
# Builder regressions for the reviewer's reproduced findings: a state the scan exists to refuse must be refused
# as VaultStateInvalid (HTTP 409) naming classes and counts only, never as an exception carrying row content.

SECRET = "SYNTHETIC-SECRET-PAYLOAD-4242"


def invalid_utf8_vault(tmp_path):
    vault = Vault(str(tmp_path / "live.db"))
    vault.add("Ordinary evidence")
    db = sqlite3.connect(vault.path, isolation_level=None)          # ordinary connection, default pragmas
    db.execute(f"INSERT INTO records(id,content,sensitivity,status,created_at) "
               f"VALUES('x', CAST('{SECRET}' || X'FF' AS TEXT),'sensitive','active',?)", (T,))
    db.close()
    return vault


def test_review_text_that_is_not_utf8_is_refused_without_disclosing_it(tmp_path):
    vault = invalid_utf8_vault(tmp_path)
    with pytest.raises(store.VaultStateInvalid) as refused:
        vault.export()
    assert refused.value.findings == {"unreadable_rows": 1}
    assert SECRET not in str(refused.value) and refused.value.__cause__ is None and refused.value.__suppress_context__
    response = TestClient(create_app(vault.path)).get("/api/export")
    assert response.status_code == 409 and SECRET not in response.text


def test_review_a_schema_4_vault_with_text_that_is_not_utf8_is_refused_unchanged(tmp_path):
    path = load_v4("v4_clean", tmp_path)
    db = sqlite3.connect(path, isolation_level=None)
    db.execute(f"INSERT INTO records(id,content,sensitivity,status,created_at) "
               f"VALUES('x', CAST('{SECRET}' || X'FF' AS TEXT),'sensitive','active',?)", (T,))
    db.close()
    before = Path(path).read_bytes()                                  # iterdump itself cannot decode the row
    with pytest.raises(store.VaultStateInvalid, match="unreadable_rows") as refused:
        Vault(path)
    assert SECRET not in str(refused.value)
    assert Path(path).read_bytes() == before and user_version(path) == 4


@pytest.mark.parametrize("statement,values", [
    ("INSERT INTO claims(id,text,origin,status,created_at) VALUES(?,'Blob id','human','proposed',?)", (b"blob-id", T)),
    ("INSERT INTO claim_sources(claim_id,record_id,evidence_sha256) VALUES('c-blob',?,NULL)", (b"blob-record",)),
])
def test_review_a_mistyped_value_is_refused_not_a_crash(tmp_path, statement, values):
    vault = Vault(str(tmp_path / "live.db"))
    r = vault.add("Ordinary evidence")
    vault.add_claim("Ordinary claim", [r["id"]])
    db = raw(vault)                                                   # CHECKs off: an ordinary connection
    if "claim_sources" in statement:
        db.execute("INSERT INTO claims(id,text,origin,status,created_at) VALUES('c-blob','Claim','human','proposed',?)", (T,))
    db.execute(statement, values)
    db.close()
    with pytest.raises(store.VaultStateInvalid, match="integrity_check"):
        vault.export()
    assert TestClient(create_app(vault.path)).get("/api/export").status_code == 409


def test_review_a_schema_5_vault_relabelled_as_schema_4_is_refused_clearly(tmp_path):
    vault = Vault(str(tmp_path / "live.db"))
    vault.add("Ordinary evidence")
    db = sqlite3.connect(vault.path, isolation_level=None)
    db.execute("PRAGMA user_version=4")
    db.close()
    with pytest.raises(RuntimeError, match="already holds schema 5 tables"):
        Vault(vault.path)
