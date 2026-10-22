"""Founder decision D-A (2026-10-22, ADR-0006): write-once evidence-set commitments and governed revalidation.

- Every claim made under schema 5 commits its complete evidence set (link count and a digest of every link) when
  it is created, so the later loss of any link is detectable and the claim stops being authoritative.
- A claim made before schema 5 keeps its status and history but is not authoritative until a human, shown the
  surviving evidence, revalidates exactly those links, or reconstructs the claim by superseding it.
- Integrity is a separate state; ordinary claim statuses and histories are unchanged.

Old vaults are genuine schema-4 fixtures written by the released eeed753 code (tests/fixtures/v4). Synthetic data only.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from sovereign import claims as rules
from sovereign import context, store
from sovereign.app import create_app
from sovereign.store import Vault

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "v4"
PROVIDERS = ("local", "kimi", "openai")
T = "2026-10-22T00:00:00+00:00"


def load_v4(name: str, tmp_path: Path) -> str:
    path = tmp_path / f"{name}.db"
    db = sqlite3.connect(path)
    db.execute("PRAGMA ignore_check_constraints=ON")
    db.executescript((FIXTURES / f"{name}.sql").read_text("utf-8"))
    db.close()
    return str(path)


def raw(vault: Vault):
    db = sqlite3.connect(vault.path, isolation_level=None)
    db.execute("PRAGMA ignore_check_constraints=ON")   # an ordinary connection: CHECKs off, triggers still apply
    return db


def by_text(vault: Vault, prefix: str) -> dict:
    return next(c for c in vault.list_claims() if c["text"].startswith(prefix))


def claim(vault: Vault, claim_id: str) -> dict:
    return next(c for c in vault.list_claims() if c["id"] == claim_id)


def reviewed(c: dict) -> list[dict]:
    return [{"id": rid, "evidence_sha256": c["source_hashes"][rid]} for rid in c["source_ids"]]


def reason_for(vault: Vault, claim_id: str, question: str) -> dict:
    """The compiler's decision about one claim for every provider target: its role, or its exclusion reason."""
    out = {}
    for provider in PROVIDERS:
        bundle = context.compile_context(vault, question, provider, [])
        roles = {i.candidate.id: i.role for i in bundle.included}
        reasons = {e.candidate.id: e.reason for e in bundle.excluded}
        out[provider] = roles.get(claim_id) or reasons.get(claim_id)
    return out


@pytest.fixture
def vault(tmp_path):
    return Vault(str(tmp_path / "vault.db"))


def approved_on_two(vault: Vault) -> tuple[dict, dict, dict]:
    r1, r2 = vault.add("Lantern logs readings locally"), vault.add("Lantern battery lasts two weeks")
    c = vault.add_claim("Lantern is a local-first device with long battery life", [r1["id"], r2["id"]])
    vault.transition_claim(c["id"], "approved", expected_status="proposed")
    return r1, r2, claim(vault, c["id"])


# --- Commitment at creation -----------------------------------------------------------------------

def test_every_new_claim_commits_its_complete_evidence_set_at_creation(vault):
    r1, r2, c = approved_on_two(vault)
    assert c["evidence_set"]["basis"] == "creation" and c["evidence_set"]["link_count"] == 2
    assert c["evidence_set"]["digest"] == store.evidence_set_digest(c["id"], c["source_hashes"])
    assert (c["integrity"], c["authoritative"]) == ("committed", True)
    assert reason_for(vault, c["id"], "lantern local battery") == {p: "approved_memory" for p in PROVIDERS}
    # The same holds for a correction (supersede) and for an untrusted import's proposals.
    replacement = vault.supersede_claim(c["id"], "Lantern is local-first", [r1["id"]], expected_status="approved")["replacement"]
    assert replacement["evidence_set"]["basis"] == "creation" and replacement["integrity"] == "committed"
    imported = Vault(vault.path.replace("vault.db", "other.db"))
    result = imported.import_untrusted(vault.export())
    assert result["claims_imported_as_proposed"] >= 1
    assert all(x["integrity"] == "committed" for x in imported.list_claims())


@pytest.mark.parametrize("statement,values", [
    ("INSERT INTO claim_evidence_sets(claim_id,link_count,digest,basis,note,at) VALUES(?,2,?,'creation',NULL,?)", None),
    ("UPDATE claim_evidence_sets SET link_count = 1 WHERE claim_id = ?", None),
    ("UPDATE claim_evidence_sets SET digest = ? WHERE claim_id = ?", None),
    ("DELETE FROM claim_evidence_sets WHERE claim_id = ?", None),
    ("INSERT OR REPLACE INTO claim_evidence_sets(claim_id,link_count,digest,basis,note,at) VALUES(?,2,?,'creation',NULL,?)", None),
])
def test_a_commitment_is_write_once_for_any_connection(vault, statement, values):
    *_, c = approved_on_two(vault)
    before = claim(vault, c["id"])["evidence_set"]
    args = {"INSERT": (c["id"], "0" * 64, T), "UPDATE": ("0" * 64, c["id"]) if "digest" in statement else (c["id"],),
            "DELETE": (c["id"],)}[statement.split()[0]]
    db = raw(vault)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(statement, args)
    db.close()
    after = claim(vault, c["id"])
    assert after["evidence_set"] == before and after["authoritative"] is True


def test_a_commitment_must_match_the_links_and_precede_the_history(vault):
    r = vault.add("Evidence for raw claims")
    h = store.evidence_hash(r)
    db = raw(vault)
    db.execute("INSERT INTO claims(id,text,origin,status,created_at) VALUES('c1','A raw claim','human','proposed',?)", (T,))
    db.execute("INSERT INTO claim_sources(claim_id,record_id,evidence_sha256) VALUES('c1',?,?)", (r["id"], h))
    with pytest.raises(sqlite3.IntegrityError):         # wrong link count
        db.execute("INSERT INTO claim_evidence_sets VALUES('c1',2,?,'creation',NULL,?)", (store.evidence_set_digest("c1", {r["id"]: h}), T))
    db.execute("INSERT INTO claim_events(claim_id,from_status,to_status,actor,at) VALUES('c1',NULL,'proposed','human',?)", (T,))
    with pytest.raises(sqlite3.IntegrityError):         # a creation commitment after the creation event
        db.execute("INSERT INTO claim_evidence_sets VALUES('c1',1,?,'creation',NULL,?)", (store.evidence_set_digest("c1", {r["id"]: h}), T))
    db.close()
    assert claim(vault, "c1")["integrity"] == "unconfirmed"


def test_forgetting_a_claim_or_its_evidence_removes_the_commitment(vault):
    r1, r2, c = approved_on_two(vault)
    other = vault.add_claim("Lantern stores readings", [r1["id"]])
    vault.delete_claim(other["id"])
    vault.delete(r2["id"])                              # forgets the approved claim, which cites r2
    db = sqlite3.connect(vault.path)
    assert db.execute("SELECT count(*) FROM claim_evidence_sets").fetchone()[0] == 0
    db.close()


# --- Partial-link loss after schema 5 is detectable ------------------------------------------------

def lose_one_link(vault: Vault, claim_id: str, record_id: str) -> None:
    """Simulate a process that can change the schema (outside the K1 threat model) deleting one evidence link."""
    db = sqlite3.connect(vault.path, isolation_level=None)
    db.execute("DROP TRIGGER claim_sources_fixed_delete")
    db.execute("DELETE FROM claim_sources WHERE claim_id = ? AND record_id = ?", (claim_id, record_id))
    db.close()


def test_partial_link_loss_after_schema_5_is_detected_and_never_authoritative(vault):
    r1, r2, c = approved_on_two(vault)
    lose_one_link(vault, c["id"], r2["id"])
    after = claim(vault, c["id"])
    assert after["support"] == "supported"                       # the surviving link alone looks intact ...
    assert (after["integrity"], after["authoritative"]) == ("mismatch", False)   # ... the commitment says otherwise
    assert reason_for(vault, c["id"], "lantern local battery") == {p: "evidence_set_mismatch" for p in PROVIDERS}
    with pytest.raises(store.VaultStateInvalid, match="evidence_set_mismatch"):
        vault.export()
    with pytest.raises(rules.TransitionError, match="reconstruct"):
        vault.revalidate_claim(c["id"], reviewed(after), expected_status="approved")


def test_a_backup_that_lost_part_of_a_claims_evidence_is_refused(vault, tmp_path):
    r1, r2, c = approved_on_two(vault)
    backup = vault.export()
    damaged = {**backup, "claims": [{**x, "source_ids": [r1["id"]], "source_hashes": {r1["id"]: x["source_hashes"][r1["id"]]}}
                                    for x in backup["claims"]]}
    target = Vault(str(tmp_path / "target.db"))
    before = target.export()
    with pytest.raises(ValueError, match="committed evidence set"):
        target.restore_trusted(damaged)
    assert {k: v for k, v in target.export().items() if k != "exported_at"} == {k: v for k, v in before.items() if k != "exported_at"}


def test_a_format_2_backup_restores_every_claim_unconfirmed(vault, tmp_path):
    *_, c = approved_on_two(vault)
    backup = vault.export()
    old_format = {**backup, "schema": "sovereign.v0.records.2",
                  "claims": [{k: v for k, v in x.items() if k != "evidence_set"} for x in backup["claims"]]}
    target = Vault(str(tmp_path / "target.db"))
    assert target.restore_trusted(old_format)["approved_claims_restored"] == 1
    restored = claim(target, c["id"])
    assert restored["status"] == "approved" and restored["history"] == c["history"]
    assert (restored["integrity"], restored["authoritative"]) == ("unconfirmed", False)


# --- Claims made before schema 5 -------------------------------------------------------------------

@pytest.mark.parametrize("fixture", ["v4_clean", "v4_partial_link_loss"])
def test_every_claim_made_before_schema_5_is_preserved_but_not_authoritative(tmp_path, fixture):
    vault = Vault(load_v4(fixture, tmp_path))
    claims = vault.list_claims()
    assert claims and all(c["integrity"] == "unconfirmed" and c["evidence_set"] is None for c in claims)
    approved = [c for c in claims if c["status"] == "approved"]
    assert approved and not any(c["authoritative"] for c in approved)
    assert all(c["history"][-1]["to_status"] == "approved" for c in approved)     # decisions kept, not erased


def test_revalidation_shows_exactly_the_surviving_evidence_and_restores_authority(tmp_path):
    vault = Vault(load_v4("v4_partial_link_loss", tmp_path))
    c = by_text(vault, "Approved claim resting on evidence one AND evidence two")
    events = len(c["history"])
    # Refused: nothing reviewed, a link nobody was shown, a wrong hash, or a stale status.
    for wrong in ([], reviewed(c) + [{"id": "invented", "evidence_sha256": None}],
                  [{**reviewed(c)[0], "evidence_sha256": "0" * 64}]):
        with pytest.raises((ValueError, rules.TransitionError)):
            vault.revalidate_claim(c["id"], wrong, expected_status="approved")
    with pytest.raises(rules.TransitionError, match="now approved"):
        vault.revalidate_claim(c["id"], reviewed(c), expected_status="contested")
    assert claim(vault, c["id"])["integrity"] == "unconfirmed"
    # Confirmed by a human who reviewed exactly the surviving link.
    after = vault.revalidate_claim(c["id"], reviewed(c), note="Evidence one alone supports it", expected_status="approved")
    assert after["evidence_set"]["basis"] == "revalidation" and after["evidence_set"]["note"] == "Evidence one alone supports it"
    assert (after["integrity"], after["authoritative"], after["status"]) == ("committed", True, "approved")
    assert len(after["history"]) == events                       # status and history untouched
    assert reason_for(vault, c["id"], "approved claim resting evidence") == {p: "approved_memory" for p in PROVIDERS}
    with pytest.raises(rules.TransitionError, match="already committed"):
        vault.revalidate_claim(c["id"], reviewed(after), expected_status="approved")
    # It survives a backup; a claim revalidated and later rejected still restores.
    vault.transition_claim(c["id"], "rejected", expected_status="approved")
    target = Vault(str(tmp_path / "target.db"))
    target.restore_trusted(vault.export())
    assert claim(target, c["id"])["evidence_set"]["basis"] == "revalidation"


def test_revalidation_is_refused_unless_the_surviving_evidence_is_current_and_verified(tmp_path):
    vault = Vault(load_v4("v4_clean", tmp_path))
    rejected = by_text(vault, "Rejected claim")
    with pytest.raises(rules.TransitionError, match="rejected claim cannot be revalidated"):
        vault.revalidate_claim(rejected["id"], reviewed(rejected), expected_status="rejected")
    approved = by_text(vault, "Approved claim on two sources")
    # Correct one of its sources: support becomes stale, so it cannot be confirmed as it stands.
    corrected = next(s for s in approved["sources"] if s["id"] != "legacy/1")
    new = vault.add("Synthetic note A, corrected again", supersedes_id=corrected["id"])
    stale = claim(vault, approved["id"])
    assert stale["support"] == "stale"
    with pytest.raises(rules.TransitionError, match="reconstruct"):
        vault.revalidate_claim(stale["id"], reviewed(stale), expected_status="approved")
    # Reconstruct: supersede it with evidence the owner chooses; the replacement is committed and needs approval.
    replacement = vault.supersede_claim(stale["id"], "Approved claim on current sources", [new["id"], "legacy/1"],
                                        expected_status="approved")["replacement"]
    assert (replacement["status"], replacement["integrity"], replacement["authoritative"]) == ("proposed", "committed", False)
    assert vault.transition_claim(replacement["id"], "approved", expected_status="proposed")["authoritative"] is True
    assert claim(vault, stale["id"])["status"] == "superseded"     # the old claim is kept as history


def test_a_claim_created_under_schema_5_has_nothing_to_revalidate(vault):
    *_, c = approved_on_two(vault)
    with pytest.raises(rules.TransitionError, match="already committed"):
        vault.revalidate_claim(c["id"], reviewed(c), expected_status="approved")


def test_the_api_requires_the_reviewed_evidence_and_an_explicit_confirmation(tmp_path):
    client = TestClient(create_app(load_v4("v4_partial_link_loss", tmp_path)))
    c = next(x for x in client.get("/api/claims").json()["claims"]
             if x["text"].startswith("Approved claim resting on evidence one AND evidence two"))
    url = f"/api/claims/{c['id']}/revalidate"
    assert client.post(url, json={"confirm": True, "expected_status": "approved"}).status_code == 422          # blind
    assert client.post(url, json={"expected_status": "approved", "evidence": reviewed(c)}).status_code == 422   # no confirm
    stale_view = [{"id": c["source_ids"][0], "evidence_sha256": "0" * 64}]
    assert client.post(url, json={"confirm": True, "expected_status": "approved", "evidence": stale_view}).status_code == 409
    ok = client.post(url, json={"confirm": True, "expected_status": "approved", "evidence": reviewed(c), "note": "checked"})
    assert ok.status_code == 200 and ok.json()["authoritative"] is True
    assert client.post(url, json={"confirm": True, "expected_status": "approved", "evidence": reviewed(c)}).status_code == 409
