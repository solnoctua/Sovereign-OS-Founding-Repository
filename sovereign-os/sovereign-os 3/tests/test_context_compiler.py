"""Context Compiler V0 / governed retrieval (ADR-0004, Benchmark 0002). Synthetic data only."""
import json

from fastapi.testclient import TestClient
import pytest
from sovereign import context, providers, store
from sovereign.app import create_app
from sovereign.store import Vault

T = "2026-10-01T00:00:00+00:00"
CONFIRM = {"confirm": True}
QUESTION = "What principles have I established for Sovereign?"


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(str(tmp_path / "vault.db")))


@pytest.fixture
def cloud(monkeypatch):
    """A configured, mocked cloud provider that records exactly what it receives."""
    seen = []
    monkeypatch.setattr(providers, "available", lambda: [{"id": "local", "ready": True}, {"id": "kimi", "ready": True}])
    monkeypatch.setattr(providers, "generate", lambda p, m: seen.append((p, m)) or "Mocked answer")
    return seen


def note(client, text, sensitivity="private"):
    resp = client.post("/api/memories", json={"content": text, "sensitivity": sensitivity})
    assert resp.status_code == 201, resp.text
    return resp.json()


def claim(client, sources, text):
    resp = client.post("/api/claims", json={"text": text, "source_ids": [s["id"] for s in sources]})
    assert resp.status_code == 201, resp.text
    return resp.json()


def decide(client, c, action, expected="proposed", **body):
    resp = client.post(f"/api/claims/{c['id']}/{action}", json={**CONFIRM, "expected_status": expected, **body})
    assert resp.status_code == 200, resp.text
    return resp.json()


def approved(client, sources, text):
    return decide(client, claim(client, sources, text), "approve")


def compile_(client, question=QUESTION, provider="local", source_ids=()):
    resp = client.post("/api/context/compile", json={"question": question, "provider": provider,
                                                     "source_ids": list(source_ids)})
    assert resp.status_code == 200, resp.text
    return resp.json()


def included(plan, role=None):
    return [i["id"] for i in plan["included"] if role is None or i["role"] == role]


def excluded(plan):
    return {e["id"]: e["reason"] for e in plan["excluded"]}


def disclosed_ids(plan):
    """The durable ids of the disclosed items, resolved locally: outbound carries labels, never ids."""
    by_label = {i["label"]: i["id"] for i in plan["included"]}
    return [by_label[i["label"]] for i in plan["outbound"]["items"]]


@pytest.fixture
def acceptance(client):
    """Benchmark 0002's core example."""
    a = note(client, "I decided Sovereign should use local-first memory.")
    b = note(client, "Synthetic private medical example.", "sensitive")
    memory = approved(client, [a], "Sovereign should remain local-first.")
    automation = claim(client, [a], "The user wants everything automated.")
    return {"a": a, "b": b, "memory": memory, "automation": automation}


# --- The core acceptance example ---------------------------------------------------------------

def test_acceptance_example_local(client, acceptance):
    plan = compile_(client)
    assert included(plan, "approved_memory") == [acceptance["memory"]["id"]]
    assert included(plan, "evidence") == [acceptance["a"]["id"]]
    assert excluded(plan)[acceptance["automation"]["id"]] == "not_authoritative"
    assert acceptance["b"]["id"] not in included(plan) and acceptance["b"]["id"] not in excluded(plan)   # irrelevant
    assert plan["outbound"] is None and not plan["disclosure"]["transmits"]


def test_acceptance_example_cloud(client, acceptance, cloud):
    plan = compile_(client, provider="kimi")
    assert disclosed_ids(plan) == [acceptance["memory"]["id"], acceptance["a"]["id"]]
    assert plan["disclosure"]["outbound_sensitivities"] == ["private"]
    payload = json.dumps(plan["outbound"]["messages"])
    assert "Sovereign should remain local-first." in payload and "local-first memory" in payload
    assert "automated" not in payload and "medical" not in payload
    ask = {"question": QUESTION, "provider": "kimi", "source_ids": []}
    assert client.post("/api/ask", json=ask).status_code == 403                                   # no approval
    assert client.post("/api/ask", json={**ask, "approve_cloud_disclosure": True}).status_code == 428  # no exact plan
    assert not cloud
    resp = client.post("/api/ask", json={**ask, "approve_cloud_disclosure": True, "context_token": plan["context_token"]})
    assert resp.status_code == 200 and resp.json()["cloud_disclosure"]
    assert cloud == [("kimi", plan["outbound"]["messages"])]                                      # exactly the preview


# --- Authority policy (MemoryClaim is the source of truth) ---------------------------------------

def test_approved_supported_claim_is_approved_memory(client):
    a = note(client, "Invented: the Sovereign garden plan starts in May.")
    c = approved(client, [a], "The Sovereign garden plan starts in May.")
    item = next(i for i in compile_(client, "When does the Sovereign garden plan start?")["included"] if i["id"] == c["id"])
    assert item["role"] == item["reason"] == "approved_memory" and item["type"] == "claim"
    assert item["status"] == "approved" and item["support"] == "supported" and item["source_ids"] == [a["id"]]


@pytest.mark.parametrize("decision, reason", [
    (None, "not_authoritative"),
    ("contest", "contested"),
    ("reject", "rejected"),
])
def test_non_approved_claims_are_never_context(client, cloud, decision, reason):
    a = note(client, "Invented: the Sovereign archive should be offline.")
    c = claim(client, [a], "Sovereign archive must be offline forever.")
    if decision:
        decide(client, c, decision, note="Invented reason" if decision == "contest" else None)
    for provider in ("local", "kimi"):
        plan = compile_(client, "What about the Sovereign archive?", provider)
        assert excluded(plan)[c["id"]] == reason and c["id"] not in included(plan)
    assert "offline forever" not in json.dumps(plan["outbound"])


def test_superseded_claim_excluded_and_its_replacement_needs_approval(client):
    a = note(client, "Invented: Sovereign meetings happen on Mondays.")
    old = approved(client, [a], "Sovereign meetings are on Mondays.")
    resp = client.post(f"/api/claims/{old['id']}/supersede",
                       json={**CONFIRM, "expected_status": "approved", "text": "Sovereign meetings are on Mondays at 9.",
                             "source_ids": [a["id"]]})
    new = resp.json()["replacement"]
    plan = compile_(client, "When are Sovereign meetings?")
    assert excluded(plan)[old["id"]] == "superseded" and excluded(plan)[new["id"]] == "not_authoritative"
    decide(client, new, "approve")
    assert new["id"] in included(compile_(client, "When are Sovereign meetings?"), "approved_memory")


def test_approved_claim_becomes_stale_the_moment_its_evidence_is_corrected(client):
    a = note(client, "Invented: Sovereign uses Postgres.")
    c = approved(client, [a], "Sovereign uses Postgres.")
    before = compile_(client, "What does Sovereign use?")
    assert c["id"] in included(before, "approved_memory")
    fixed = client.post(f"/api/memories/{a['id']}/correct", json={"content": "Invented: Sovereign uses SQLite."}).json()
    after = compile_(client, "What does Sovereign use?")
    assert excluded(after)[c["id"]] == "stale" and excluded(after)[a["id"]] == "superseded"
    assert included(after) == [fixed["id"]] and after["context_token"] != before["context_token"]


def restore_with_claim(v, claim_id, text, record, digest):
    history = [{"from_status": None, "to_status": "proposed", "actor": "human", "note": None, "at": T},
               {"from_status": "proposed", "to_status": "approved", "actor": "human", "note": None, "at": T}]
    return v.restore_trusted({"schema": "sovereign.v0.records.2", "records": [], "tombstones": [], "claim_tombstones": [],
                              "claims": [{"id": claim_id, "text": text, "origin": "human", "status": "approved",
                                          "created_at": T, "supersedes_id": None, "source_ids": [record],
                                          "source_hashes": {record: digest}, "history": history}]})


def test_approved_claim_with_missing_or_unverified_evidence_is_excluded(client):
    v = client.app.state.vault
    restore_with_claim(v, "c-missing", "Sovereign missing evidence claim", "absent-record", "0" * 64)
    squatted = note(client, "Invented note that is not the claim's evidence")
    restore_with_claim(v, "c-unverified", "Sovereign unverified evidence claim", squatted["id"], "0" * 64)
    plan = compile_(client, "Sovereign evidence claim")
    assert excluded(plan)["c-missing"] == "orphaned" and excluded(plan)["c-unverified"] == "orphaned"
    assert all(v.list_claims()[i]["status"] == "approved" for i in range(2))              # approved, yet not memory


# --- Evidence vs memory stay distinct, into the prompt ----------------------------------------------

def test_source_and_claim_stay_distinguishable_in_bundle_and_prompt(client, acceptance, cloud):
    plan = compile_(client, provider="kimi")
    roles = {i["id"]: (i["type"], i["role"]) for i in plan["included"]}
    assert roles[acceptance["memory"]["id"]] == ("claim", "approved_memory")
    assert roles[acceptance["a"]["id"]] == ("source", "evidence")
    user = plan["outbound"]["messages"][1]["content"]
    payload = json.loads(user[user.index("{"):user.rindex("}") + 1])
    # The model sees request-scoped labels and the authorised text; provenance runs through labels.
    assert payload["approved_memory"] == [{"label": "M1", "text": acceptance["memory"]["text"], "evidence": ["E1"]}]
    assert payload["evidence"] == [{"label": "E1", "text": acceptance["a"]["content"],
                                    "captured": acceptance["a"]["created_at"][:10]}]
    sent = json.dumps(plan["outbound"]["messages"])
    assert acceptance["memory"]["id"] not in sent and acceptance["a"]["id"] not in sent      # durable ids stay local
    assert [i["label"] for i in plan["outbound"]["items"]] == ["M1", "E1"]                 # outbound: labels only
    assert [i["id"] for i in plan["included"]] == [acceptance["memory"]["id"], acceptance["a"]["id"]]   # ids: local
    assert "APPROVED MEMORY" in plan["outbound"]["messages"][0]["content"]


# --- Determinism ---------------------------------------------------------------------------------

def test_compilation_is_deterministic_for_unchanged_state(client, acceptance):
    for provider in ("local", "kimi"):
        first, second = compile_(client, provider=provider), compile_(client, provider=provider)
        assert first == second
    assert compile_(client)["context_token"] != compile_(client, provider="kimi")["context_token"]
    assert compile_(client)["context_token"] != compile_(client, "Which principles for Sovereign?")["context_token"]


def test_ranking_is_deterministic_and_stable_under_ties(tmp_path):
    v = Vault(str(tmp_path / "v.db"))
    backup = {"schema": "sovereign.v0.records.2", "tombstones": [], "claims": [], "claim_tombstones": [],
              "records": [{"id": rid, "content": text, "source": "manual", "sensitivity": "private", "status": "active",
                           "created_at": created, "supersedes_id": None}
                          for rid, text, created in [("r-b", "garden plan", T), ("r-a", "garden plan notes", T),
                                                     ("r-c", "garden", "2026-10-02T00:00:00+00:00"),
                                                     ("r-d", "garden plan draft", "2026-09-01T00:00:00+00:00")]]}
    v.restore_trusted(backup)
    order = [i.candidate.id for i in context.compile_context(v, "garden plan", "local", []).included]
    # More matched terms first; then newest; then id ascending for identical keys.
    assert order == ["r-a", "r-b", "r-d", "r-c"]
    assert order == [i.candidate.id for i in context.compile_context(v, "garden plan", "local", []).included]
    assert [i.rank for i in context.compile_context(v, "garden plan", "local", []).included] == [1, 2, 3, 4]


# --- Pinned (explicitly selected) sources -----------------------------------------------------------

def test_pinned_source_is_considered_first_but_still_passes_policy(client, cloud):
    unrelated = note(client, "Invented note about bicycles.")
    secret = note(client, "Invented sensitive note.", "sensitive")
    a = note(client, "Invented: Sovereign v1.")
    client.post(f"/api/memories/{a['id']}/correct", json={"content": "Invented: Sovereign v2."})
    plan = compile_(client, QUESTION, source_ids=[unrelated["id"], a["id"]])
    assert included(plan)[0] == unrelated["id"]                                   # pinned: relevant by choice
    assert excluded(plan)[a["id"]] == "superseded"                                 # pinned, yet not current evidence
    blocked = compile_(client, QUESTION, "kimi", [secret["id"]])
    assert blocked["disclosure"]["blocked"]["ids"] == [secret["id"]] and excluded(blocked)[secret["id"]] == "sensitive_cloud"
    assert secret["id"] in included(compile_(client, QUESTION, "local", [secret["id"]]))   # local may use it


@pytest.mark.parametrize("bad, status", [("unknown-id", 422), ("claim", 422), ("dup", 422)])
def test_invalid_pins_are_rejected(client, bad, status):
    a = note(client, "Invented note")
    ids = {"unknown-id": ["unknown-id"], "claim": [claim(client, [a], "Invented claim")["id"]], "dup": [a["id"], a["id"]]}[bad]
    assert client.post("/api/context/compile", json={"question": "Q", "source_ids": ids}).status_code == status


# --- Forget and correction dominate retrieval ---------------------------------------------------------

def test_forgotten_content_is_never_retrieved(client, acceptance):
    assert client.delete(f"/api/memories/{acceptance['a']['id']}").status_code == 200
    plan = compile_(client)
    text = json.dumps(plan)
    assert "local-first" not in text and "automated" not in text and plan["included"] == []
    assert client.post("/api/context/compile", json={"question": QUESTION, "source_ids": [acceptance["a"]["id"]]}
                       ).status_code == 422                                      # pinning a forgotten id is invalid


def test_corrections_and_decisions_change_authority_immediately(client):
    a = note(client, "Invented: Sovereign deploys on Fridays.")
    c = claim(client, [a], "Sovereign deploys on Fridays.")
    q = "When does Sovereign deploy?"
    assert excluded(compile_(client, q))[c["id"]] == "not_authoritative"
    decide(client, c, "approve")
    assert c["id"] in included(compile_(client, q), "approved_memory")
    decide(client, c, "reject", "approved")
    assert excluded(compile_(client, q))[c["id"]] == "rejected"


# --- Duplicates and budget ----------------------------------------------------------------------------

def test_duplicate_relationships_never_duplicate_outbound_content(client, cloud):
    a = note(client, "Invented: Sovereign keeps evidence.")
    b = note(client, "Invented: Sovereign keeps claims.")
    twin = note(client, "Invented:   Sovereign keeps evidence.")                  # same text, other record
    both = approved(client, [a, b], "Sovereign keeps evidence and claims.")         # cites two candidates
    plan = compile_(client, "What does Sovereign keep?", "kimi", [a["id"]])         # a: pinned and lexical
    ids = disclosed_ids(plan)
    assert len(ids) == len(set(ids)) and ids.count(a["id"]) == 1 and ids.count(both["id"]) == 1
    assert excluded(plan)[twin["id"]] == "duplicate"
    assert next(e for e in plan["excluded"] if e["id"] == twin["id"])["duplicate_of"] == a["id"]
    assert plan["outbound"]["messages"][1]["content"].count("Sovereign keeps evidence.") == 1


def test_context_budget_is_enforced_visibly(client):
    for i in range(20):
        note(client, f"Invented Sovereign note {i:02d}")
    plan = compile_(client, "Sovereign note")
    assert len(plan["included"]) == context.POLICY.max_items == plan["budget"]["used_items"]
    assert [e["reason"] for e in plan["excluded"]] == ["budget_exceeded"] * 8
    long = {note(client, (f"Budget item {i} " + "x" * 5000)[:5000])["id"] for i in range(3)}
    plan = compile_(client, "budget item")
    assert len(plan["included"]) == 2 and set(included(plan)) < long                  # 2 × 5,000 ≤ 12,000 characters
    assert set(excluded(plan).values()) == {"budget_exceeded"} and set(excluded(plan)) == long - set(included(plan))
    assert plan["budget"]["used_chars"] == 10000 <= plan["budget"]["max_chars"]


def test_retrieval_truncation_is_visible(client):
    v = client.app.state.vault
    for i in range(context.POLICY.retrieval_limit + 5):
        v.add(f"Invented Sovereign record {i}")
    plan = compile_(client, "Sovereign record")
    assert plan["retrieval"]["records_matched"] == 55 and plan["retrieval"]["limit_per_kind"] == 50
    assert len(plan["included"]) + len(plan["excluded"]) == 50


# --- Sensitivity inheritance and the local/cloud boundary -----------------------------------------------

def test_claim_inherits_most_restrictive_sensitivity_from_current_evidence(client):
    private = note(client, "Invented: Sovereign private evidence.")
    sensitive = note(client, "Invented: Sovereign sensitive evidence.", "sensitive")
    only_private = approved(client, [private], "Sovereign claim from private evidence.")
    mixed = approved(client, [private, sensitive], "Sovereign claim from mixed evidence.")
    plan = compile_(client, "Sovereign claim evidence")
    sens = {i["id"]: i["sensitivity"] for i in plan["included"]}
    assert sens[only_private["id"]] == "private" and sens[mixed["id"]] == "sensitive"


def test_local_compilation_may_use_sensitive_eligible_context(client, cloud):
    s = note(client, "Invented: Sovereign therapy notes.", "sensitive")
    c = approved(client, [s], "Sovereign therapy is weekly.")
    local = compile_(client, "Sovereign therapy")
    assert set(included(local)) == {s["id"], c["id"]}
    remote = compile_(client, "Sovereign therapy", "kimi")
    assert excluded(remote) == {c["id"]: "sensitive_cloud", s["id"]: "sensitive_cloud"} and remote["outbound"]["items"] == []
    assert remote["disclosure"]["blocked"] is None                       # retrieved (not pinned): dropped, never sent


# --- Receipts and the /api/ask integration ----------------------------------------------------------------

def test_receipt_explains_inclusion_and_exclusion_without_content(client, acceptance):
    resp = client.post("/api/ask", json={"question": QUESTION, "provider": "local"})
    body = resp.json()
    assert resp.status_code == 200 and not body["cloud_disclosure"]
    receipt = body["receipt"]
    assert receipt["included"] == [{"id": acceptance["memory"]["id"], "type": "claim", "role": "approved_memory"},
                                   {"id": acceptance["a"]["id"], "type": "source", "role": "evidence"}]
    assert receipt["excluded"] == [{"id": acceptance["automation"]["id"], "type": "claim", "reason": "not_authoritative"}]
    assert receipt["boundary"] == "local" and receipt["transmitted"] is False
    assert "local-first" not in json.dumps(receipt) and "automated" not in json.dumps(receipt)   # ids, not content
    reasons = next(e for e in body["context"]["excluded"] if e["id"] == acceptance["automation"]["id"])["reasons"]
    assert reasons == ["not_authoritative", "not_relevant"]                   # every applicable reason, in order


def test_local_ask_checks_a_supplied_token_and_never_calls_a_provider(client, acceptance, cloud):
    plan = compile_(client)
    ok = client.post("/api/ask", json={"question": QUESTION, "provider": "local", "context_token": plan["context_token"]})
    assert ok.status_code == 200 and ok.json()["context"] == plan
    decide(client, acceptance["automation"], "approve")
    stale = client.post("/api/ask", json={"question": QUESTION, "provider": "local", "context_token": plan["context_token"]})
    assert stale.status_code == 409 and not cloud


def test_compile_never_writes_to_the_vault(client, acceptance):
    before = client.app.state.vault.export()
    compile_(client); compile_(client, provider="kimi")
    client.post("/api/ask", json={"question": QUESTION, "provider": "local"})
    after = client.app.state.vault.export()
    assert {k: v for k, v in before.items() if k != "exported_at"} == {k: v for k, v in after.items() if k != "exported_at"}


def test_bundle_contract_shape(client, acceptance):
    plan = compile_(client, provider="kimi")
    assert set(plan) == {"policy_version", "question", "target", "retrieval", "included", "excluded", "budget",
                         "disclosure", "outbound", "context_token"}
    assert plan["policy_version"] == context.POLICY_VERSION and plan["target"] == {"provider": "kimi", "boundary": "cloud"}
    assert set(plan["included"][0]) >= {"id", "type", "role", "reason", "content", "source_ids", "status", "support",
                                        "sensitivity", "relevance", "rank"}
    assert set(plan["excluded"][0]) >= {"id", "type", "reason", "reasons", "relevance"}
    assert len(plan["context_token"]) == 64 and int(plan["context_token"], 16) >= 0
