"""Regressions for the independent Codex audit of PR #10 (audited head 04ba75c): findings F-1 to F-4.

The audit report is reviewer-owned and is not reproduced or paraphrased here. These tests encode the
builder's own reproduction of each finding as summarized in the founder's remediation directive of
2026-10-22, using genuine schema-4 fixtures produced by the released eeed753 code (tests/fixtures/v4).
Tests that depend on a founder policy decision are xfail(strict=True): they state the required outcome
and must be un-marked when the chosen policy is implemented (ADR-0006, "Decisions requested").
Synthetic data only.
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

@pytest.mark.xfail(strict=True, reason="F-1: the recovery policy for historically unverifiable approvals awaits a "
                                        "founder decision (ADR-0006, Decisions requested, D-A)")
def test_f1_claim_that_lost_part_of_its_evidence_before_migration_is_not_authoritative(tmp_path):
    vault = Vault(load_v4("v4_partial_link_loss", tmp_path))
    claim = by_text(vault, "Approved claim resting on evidence one AND evidence two")
    assert claim["status"] == "approved" and len(claim["source_ids"]) == 1   # history is preserved, nothing invented
    assert claim["authoritative"] is False


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
    vault = Vault(str(tmp_path / "live.db"))
    r = vault.add("Ordinary evidence")
    db = sqlite3.connect(vault.path, isolation_level=None)
    db.execute("INSERT INTO claims(id,text,origin,status,created_at) VALUES('c-nul',?,'human','proposed',?)",
               ("C\x00" + "y" * 2500, T))
    db.execute("INSERT INTO claim_sources(claim_id,record_id,evidence_sha256) VALUES('c-nul',?,?)", (r["id"], store.evidence_hash(r)))
    db.execute("INSERT INTO claim_events(claim_id,from_status,to_status,actor,at) VALUES('c-nul',NULL,'proposed','human',?)", (T,))
    db.close()
    with pytest.raises(store.VaultStateInvalid):
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


@pytest.mark.xfail(strict=True, reason="F-4 storage semantics await a founder decision (ADR-0006, Decisions requested, D-C)")
def test_f4_storage_itself_refuses_text_whose_true_length_exceeds_its_bound(tmp_path):
    vault = Vault(str(tmp_path / "live.db"))
    db = sqlite3.connect(vault.path, isolation_level=None)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO claims(id,text,origin,status,created_at) VALUES('c-nul',?,'human','proposed',?)",
                   ("C\x00" + "y" * 2500, T))
    db.close()
