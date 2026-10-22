"""SB-2a provenance navigation: second-brain validation spec §3, items 1-6 (ADR-0005 §8.1, R3).

1. Edges are exactly canonical.   2. Status, support and authority are read live.
3. Forget leaves nothing.          4. Navigation is not relevance (identical compiler tokens).
5. Bounded and local.              6. Read-only.
Synthetic data only.
"""
from __future__ import annotations

import ast
import json
import sqlite3
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from sovereign import context, provenance
from sovereign.app import create_app
from sovereign.store import Vault

SRC = Path(__file__).resolve().parents[1] / "src" / "sovereign"


@pytest.fixture
def vault(tmp_path):
    return Vault(str(tmp_path / "vault.db"))


def world(v):
    """r1 -> r1b (correction); c1 cites r1b and r2 (approved); c1 superseded by c2; c3 cites r2 (proposed).

    Returns typed (kind, id) keys: record and claim ids are separate namespaces."""
    r1 = v.add("Lantern stores readings on device")
    r1b = v.add("Lantern stores readings on device in SQLite", supersedes_id=r1["id"])
    r2 = v.add("Field test showed fourteen days of battery")
    c1 = v.add_claim("Lantern uses SQLite on device", [r1b["id"], r2["id"]])
    v.transition_claim(c1["id"], "approved", expected_status="proposed")
    c2 = v.supersede_claim(c1["id"], "Lantern keeps readings in SQLite on the device", [r1b["id"]],
                           expected_status="approved")["replacement"]
    c3 = v.add_claim("Battery lasts about two weeks", [r2["id"]])
    return {"r1": ("record", r1["id"]), "r1b": ("record", r1b["id"]), "r2": ("record", r2["id"]),
            "c1": ("claim", c1["id"]), "c2": ("claim", c2["id"]), "c3": ("claim", c3["id"])}


def canonical_edges(v):
    """Every link the vault stores, read straight from SQL, between items that are present (every evidence link
    in these worlds verifies; unverified links are covered in tests/adversarial/test_pr11_audit_regressions.py)."""
    db = sqlite3.connect(v.path)
    try:
        q = lambda sql: set(db.execute(sql).fetchall())
        supported = q("""SELECT 'SUPPORTED_BY', s.claim_id, s.record_id FROM claim_sources s
                         JOIN claims c ON c.id=s.claim_id JOIN records r ON r.id=s.record_id""")
        corrects = q("SELECT 'CORRECTS', a.id, a.supersedes_id FROM records a JOIN records b ON b.id=a.supersedes_id")
        supersedes = q("SELECT 'SUPERSEDES', a.id, a.supersedes_id FROM claims a JOIN claims b ON b.id=a.supersedes_id")
        kinds = {"SUPPORTED_BY": ("claim", "record"), "CORRECTS": ("record", "record"), "SUPERSEDES": ("claim", "claim")}
        return {(t, (kinds[t][0], a), (kinds[t][1], b)) for t, a, b in supported | corrects | supersedes}
    finally:
        db.close()


def key(endpoint):
    return (endpoint["kind"], endpoint["id"])


def edges_of(graph):
    return {(e["type"], key(e["from"]), key(e["to"])) for e in graph["edges"]}


def ids_of(graph):
    return {(n["kind"], n["id"]) for n in graph["nodes"]}


# 1. Edges are exactly canonical -------------------------------------------------------------------

def test_every_edge_is_one_stored_link_and_nothing_else(vault):
    ids = world(vault)
    stored = canonical_edges(vault)
    union = set()
    for ident in ids.values():
        graph = provenance.neighborhood(vault, *ident, hops=2)
        assert edges_of(graph) <= stored
        for e in graph["edges"]:                       # both endpoints are nodes of the response
            assert {key(e["from"]), key(e["to"])} <= ids_of(graph)
        union |= edges_of(graph)
    assert union == stored                             # and every stored link is reachable


def test_one_hop_neighbourhood_of_a_claim_is_exactly_its_own_links(vault):
    ids = world(vault)
    graph = provenance.neighborhood(vault, *ids["c1"], hops=1)
    assert edges_of(graph) == {("SUPPORTED_BY", ids["c1"], ids["r1b"]), ("SUPPORTED_BY", ids["c1"], ids["r2"]),
                               ("SUPERSEDES", ids["c2"], ids["c1"])}
    assert ids_of(graph) == {ids["c1"], ids["r1b"], ids["r2"], ids["c2"]}


# 2. Status, support and authority are read live --------------------------------------------------

def node(graph, k):
    return next(n for n in graph["nodes"] if (n["kind"], n["id"]) == k)


def test_status_support_and_authority_are_live(vault):
    ids = world(vault)
    c3 = lambda: node(provenance.neighborhood(vault, *ids["c3"]), ids["c3"])
    assert (c3()["status"], c3()["authoritative"]) == ("proposed", False)
    vault.transition_claim(ids["c3"][1], "approved", expected_status="proposed")
    assert (c3()["status"], c3()["support"], c3()["authoritative"]) == ("approved", "supported", True)
    vault.add("Field test showed twelve days of battery", supersedes_id=ids["r2"][1])   # correct the evidence
    assert (c3()["support"], c3()["authoritative"]) == ("stale", False)
    graph = provenance.neighborhood(vault, *ids["c3"])
    assert {e["evidence_state"] for e in graph["edges"] if e["type"] == "SUPPORTED_BY"} == {"superseded"}
    stored = [c for c in vault.list_claims() if c["id"] == ids["c3"][1]][0]
    assert (stored["support"], stored["authoritative"]) == (c3()["support"], c3()["authoritative"])


# 3. Forget leaves nothing ------------------------------------------------------------------------

def assert_absent(vault, forgotten_ids, canaries, focus_ids):
    for ident in forgotten_ids:
        assert provenance.neighborhood(vault, *ident) is None
    for ident in focus_ids:
        graph = provenance.neighborhood(vault, *ident, hops=2)
        if graph is None:
            continue
        text = json.dumps(graph)
        assert not (ids_of(graph) & set(forgotten_ids))
        assert not any({key(e["from"]), key(e["to"])} & set(forgotten_ids) for e in graph["edges"])
        for _, forgotten in forgotten_ids:
            assert forgotten not in text
        for canary in canaries:
            assert canary not in text


def test_record_forget_removes_revisions_dependent_claims_and_every_trace(vault):
    ids = world(vault)
    vault.delete(ids["r1b"][1])  # forgets r1b, r1 (earlier revision) and every claim citing either
    assert_absent(vault, [ids["r1"], ids["r1b"], ids["c1"], ids["c2"]],
                  ["stores readings on device", "SQLite"], [ids["r2"], ids["c3"]])
    graph = provenance.neighborhood(vault, *ids["r2"], hops=2)
    assert edges_of(graph) == {("SUPPORTED_BY", ids["c3"], ids["r2"])}


def test_forgetting_only_an_older_revision_leaves_no_edge_to_it(vault):
    ids = world(vault)
    db = sqlite3.connect(vault.path, isolation_level=None)       # a raw tombstone insert is a legitimate Forget
    db.execute("INSERT INTO tombstones(id, deleted_at) VALUES (?, '2026-10-22T00:00:00+00:00')", (ids["r1"][1],))
    db.close()
    graph = provenance.neighborhood(vault, *ids["r1b"], hops=2)
    assert ids["r1"] not in ids_of(graph)
    assert not [e for e in graph["edges"] if e["type"] == "CORRECTS"]
    assert node(graph, ids["r1b"])["status"] == "active"


def test_claim_forget_and_restored_tombstones_leave_nothing(vault, tmp_path):
    ids = world(vault)
    vault.delete_claim(ids["c3"][1])
    assert_absent(vault, [ids["c3"]], ["Battery lasts about two weeks"], [ids["r2"], ids["c1"]])
    other = Vault(str(tmp_path / "other.db"))
    other.restore_trusted(vault.export())
    backup = other.export()
    backup["tombstones"].append({"id": ids["r2"][1], "deleted_at": "2026-10-22T00:00:00+00:00"})
    vault.restore_trusted(backup)      # tombstones in a trusted backup dominate
    assert_absent(vault, [ids["r2"], ids["c1"]], ["fourteen days"], [ids["r1b"], ids["c2"]])


# 4. Navigation is not relevance ------------------------------------------------------------------

def test_neither_the_compiler_nor_the_store_imports_the_graph():
    for name in ("context.py", "store.py", "claims.py", "providers.py"):
        tree = ast.parse((SRC / name).read_text(encoding="utf-8"))
        imported = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                imported |= {a.name for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                imported |= {n.module or ""} | {a.name for a in n.names}
        assert not any("provenance" in i for i in imported), (name, imported)


def test_graph_queries_leave_every_benchmark_token_identical():
    from evaluation.retrieval import harness
    corpus, queries, _ = harness.load()
    with tempfile.TemporaryDirectory() as d:
        vault = harness.build_vault(d, corpus)
        questions = [q["question"] for q in queries["queries"]]
        assert len(questions) == 56
        tokens = lambda: [context.compile_context(vault, q, p, []).context_token
                          for q in questions for p in ("local", "kimi")]
        before = tokens()
        db = sqlite3.connect(vault.path)
        every = db.execute("SELECT 'record', id FROM records UNION ALL SELECT 'claim', id FROM claims").fetchall()
        db.close()
        for kind, ident in every:
            provenance.neighborhood(vault, kind, ident, hops=2)
        assert tokens() == before


# 5. Bounded and local; 6. Read-only ---------------------------------------------------------------

def test_hops_and_size_are_bounded(vault):
    ids = world(vault)
    with pytest.raises(ValueError):
        provenance.neighborhood(vault, *ids["c1"], hops=0)
    with pytest.raises(ValueError):
        provenance.neighborhood(vault, *ids["c1"], hops=provenance.MAX_HOPS + 1)
    with pytest.raises(ValueError):
        provenance.neighborhood(vault, *ids["c1"], max_nodes=provenance.MAX_NODES + 1)
    with pytest.raises(ValueError):
        provenance.neighborhood(vault, "note", ids["c1"][1])
    hub = vault.add("A record cited by many claims")
    for n in range(12):
        vault.add_claim(f"Interpretation number {n}", [hub["id"]])
    graph = provenance.neighborhood(vault, "record", hub["id"], hops=1, max_nodes=5)
    assert len(graph["nodes"]) == 5 and graph["truncated"] is True
    assert {key(e["from"]) for e in graph["edges"]} <= ids_of(graph)


def test_graph_queries_never_write(vault):
    ids = world(vault)
    before, raw = vault.export(), Path(vault.path).read_bytes()
    for ident in ids.values():
        provenance.neighborhood(vault, *ident, hops=2)
    after = vault.export()
    assert {k: after[k] for k in after if k != "exported_at"} == {k: before[k] for k in before if k != "exported_at"}
    assert Path(vault.path).read_bytes() == raw


def test_graph_output_never_reaches_a_bundle_or_receipt(vault):
    ids = world(vault)
    provenance.neighborhood(vault, *ids["c2"], hops=2)
    bundle = context.compile_context(vault, "Lantern readings SQLite device", "kimi", [])
    text = json.dumps(bundle.describe()) + json.dumps(bundle.receipt(transmitted=False).describe())
    for marker in ("SUPPORTED_BY", "SUPERSEDES", "CORRECTS", "evidence_state"):
        assert marker not in text


# API --------------------------------------------------------------------------------------------

def test_api_returns_the_graph_and_hides_forgotten_items(tmp_path):
    app = create_app(str(tmp_path / "api.db"))
    client = TestClient(app)
    ids = world(app.state.vault)
    c2, c3 = ids["c2"][1], ids["c3"][1]
    r = client.get(f"/api/provenance/claim/{c2}")
    assert r.status_code == 200 and r.json()["focus"] == {"kind": "claim", "id": c2}
    assert client.get(f"/api/provenance/claim/{c2}?hops=2").json()["hops"] == 2
    assert client.get(f"/api/provenance/claim/{c2}?hops=3").status_code == 422
    assert client.get(f"/api/provenance/record/{c2}").status_code == 404         # a claim id is not a record id
    app.state.vault.delete_claim(c3)
    assert client.get(f"/api/provenance/claim/{c3}").status_code == 404          # forgotten
    assert client.get("/api/provenance/claim/never-existed").status_code == 404   # same answer: no oracle
    assert client.post(f"/api/provenance/claim/{c2}", json={}).status_code == 405


def test_api_serves_legacy_ids_containing_slashes(tmp_path):
    path = str(tmp_path / "legacy.db")
    db = sqlite3.connect(path)
    db.executescript("""CREATE TABLE records (id TEXT PRIMARY KEY, content TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'manual',
        sensitivity TEXT NOT NULL CHECK(sensitivity IN ('private','sensitive')), status TEXT NOT NULL CHECK(status IN ('active','superseded')),
        created_at TEXT NOT NULL, supersedes_id TEXT);
        CREATE TABLE tombstones (id TEXT PRIMARY KEY, deleted_at TEXT NOT NULL);
        INSERT INTO records VALUES ('notes/2024/a','Legacy synthetic note','manual','private','active','2024-01-01T00:00:00+00:00',NULL);""")
    db.close()
    client = TestClient(create_app(path))
    r = client.get("/api/provenance/record/notes/2024/a")
    assert r.status_code == 200 and r.json()["nodes"][0]["text"] == "Legacy synthetic note"


# Evidence-set integrity (ADR-0006, D-A) ---------------------------------------------------------

def test_a_claim_made_before_schema_5_shows_as_unconfirmed_until_revalidated(tmp_path):
    fixture = Path(__file__).resolve().parent / "fixtures" / "v4" / "v4_partial_link_loss.sql"
    path = tmp_path / "v4.db"
    db = sqlite3.connect(path)
    db.execute("PRAGMA ignore_check_constraints=ON")
    db.executescript(fixture.read_text("utf-8"))
    db.close()
    vault = Vault(str(path))
    c = next(x for x in vault.list_claims() if x["text"].startswith("Approved claim resting on evidence one"))
    focus = node(provenance.neighborhood(vault, "claim", c["id"]), ("claim", c["id"]))
    assert (focus["status"], focus["integrity"], focus["authoritative"]) == ("approved", "unconfirmed", False)
    vault.revalidate_claim(c["id"], [{"id": r, "evidence_sha256": c["source_hashes"][r]} for r in c["source_ids"]],
                           expected_status="approved")
    focus = node(provenance.neighborhood(vault, "claim", c["id"]), ("claim", c["id"]))
    assert (focus["integrity"], focus["authoritative"]) == ("committed", True)     # read live, never copied
