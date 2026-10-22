"""Regressions for the Codex audit of PR #11 (SB-2a provenance navigation) at 35c7af6: F-5, F-6, F-7.

Builder-written: the finding IDs are the audit's, and each test states the property it checks.

- F-5: forgotten, never-present and ineligible endpoints never become nodes or edges, never use capacity and never
  set `truncated`.
- F-6: identity is a typed (kind, id) pair everywhere: in lookups, nodes, edge endpoints and the API.
- F-7: traversal work, response bytes and decision-history hydration are bounded, and the stored history is never
  limited.

Also covered: exact capacity, id collisions, large history, high-degree hubs, Forget, and snapshot consistency
against a concurrent writer. Synthetic data only.
"""
from __future__ import annotations

import json
import re
import sqlite3
import threading
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sovereign import claims as rules
from sovereign import provenance, store
from sovereign.app import create_app
from sovereign.store import Vault

T = "2026-10-22T00:00:00+00:00"
BYTES = 256 * 1024     # the response contract: a serialized graph never exceeds this
HISTORY = 50           # the most recent decisions shown for the focus claim
APP_JS = Path(__file__).resolve().parents[2] / "src" / "sovereign" / "static" / "app.js"


@pytest.fixture
def vault(tmp_path):
    return Vault(str(tmp_path / "vault.db"))


def nb(vault, kind, ident, **kw):
    return provenance.neighborhood(vault, kind, ident, **kw)


def fetch(client, kind, ident, hops):
    """(status, body bytes, graph) from the API."""
    response = client.get(f"/api/provenance/{kind}/{ident}?hops={hops}")
    return response.status_code, len(response.content), response.json()


def raw(vault):
    db = sqlite3.connect(vault.path, isolation_level=None)
    db.execute("PRAGMA ignore_check_constraints=ON")   # an ordinary connection; triggers still apply
    return db


def cite(vault, record_id, claim_ids, evidence, text="An interpretation of the evidence"):
    """Create proposed claims citing one record, in one raw transaction (fast enough for large hubs)."""
    with closing(raw(vault)) as db:
        db.execute("BEGIN")
        for cid in claim_ids:
            db.execute("INSERT INTO claims(id,text,origin,status,created_at) VALUES(?,?,'human','proposed',?)", (cid, text, T))
            db.execute("INSERT INTO claim_sources(claim_id,record_id,evidence_sha256) VALUES(?,?,?)", (cid, record_id, evidence))
            db.execute("INSERT INTO claim_events(claim_id,from_status,to_status,actor,at) VALUES(?,NULL,'proposed','human',?)",
                       (cid, T))
        db.execute("COMMIT")


def raw_record(vault, ident, content, status="active", supersedes_id=None):
    with closing(raw(vault)) as db:
        db.execute("INSERT INTO records(id,content,source,sensitivity,status,created_at,supersedes_id) "
                   "VALUES(?,?,'manual','private',?,?,?)", (ident, content, status, T, supersedes_id))
        db.row_factory = sqlite3.Row
        return dict(db.execute("SELECT * FROM records WHERE id=?", (ident,)).fetchone())


def key(endpoint):
    return (endpoint["kind"], endpoint["id"])


def nodes_of(graph):
    return {(n["kind"], n["id"]) for n in graph["nodes"]}


def edges_of(graph):
    return {(e["type"], key(e["from"]), key(e["to"])) for e in graph["edges"]}


def node(graph, k):
    return next(n for n in graph["nodes"] if (n["kind"], n["id"]) == k)


def wire(graph) -> int:
    """Bytes as FastAPI's JSONResponse renders them."""
    return len(json.dumps(graph, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8"))


def assert_well_formed(graph):
    keys = nodes_of(graph)
    assert len(keys) == len(graph["nodes"])                              # no node twice
    assert key(graph["focus"]) in keys
    for e in graph["edges"]:                                              # endpoints are typed nodes of the response
        assert key(e["from"]) in keys and key(e["to"]) in keys
        assert (e["from"]["kind"], e["to"]["kind"]) == {"SUPPORTED_BY": ("claim", "record"),
                                                        "SUPERSEDES": ("claim", "claim"),
                                                        "CORRECTS": ("record", "record")}[e["type"]]


# --- F-5: absent and ineligible endpoints ---------------------------------------------------------

@pytest.mark.parametrize("predecessor", ["present", "forgotten"])
def test_f5_a_forgotten_endpoint_never_sets_truncated(vault, predecessor):
    old = vault.add("Older revision of a note")
    new = vault.add("Newer revision of a note", supersedes_id=old["id"])
    if predecessor == "forgotten":
        with closing(raw(vault)) as db:       # forgetting only the older revision is a legitimate Forget
            db.execute("INSERT INTO tombstones(id, deleted_at) VALUES (?, ?)", (old["id"], T))
    graph = nb(vault, "record", new["id"], hops=1, max_nodes=1)
    assert nodes_of(graph) == {("record", new["id"])} and graph["edges"] == []
    assert graph["truncated"] is (predecessor == "present")    # only an eligible item left out sets it


def test_f5_a_link_to_a_record_that_was_never_present_never_sets_truncated(vault):
    cite(vault, "never-present", ["c-missing"], "0" * 64)
    graph = nb(vault, "claim", "c-missing", hops=2, max_nodes=1)
    assert nodes_of(graph) == {("claim", "c-missing")} and graph["edges"] == [] and graph["truncated"] is False
    assert "never-present" not in json.dumps(graph)


def test_f5_unverified_evidence_links_are_not_edges_nodes_or_truncation(vault):
    rec = vault.add("A record whose identity differs from what two claims pinned")
    cite(vault, rec["id"], ["a-unverified-1", "a-unverified-2"], "0" * 64)
    for ident in ("a-unverified-1", "a-unverified-2"):
        graph = nb(vault, "claim", ident, hops=2, max_nodes=1)
        assert nodes_of(graph) == {("claim", ident)} and graph["truncated"] is False
        assert node(graph, ("claim", ident))["support"] == "orphaned"   # the claim itself says so
    graph = nb(vault, "record", rec["id"], hops=2, max_nodes=1)
    assert nodes_of(graph) == {("record", rec["id"])} and graph["truncated"] is False


def test_f5_records_in_unrecognised_states_are_never_nodes_and_never_set_truncated(vault):
    raw_record(vault, "odd", "Quarterly figures draft", status="pending")
    fix = raw_record(vault, "odd-fix", "Quarterly figures, corrected", supersedes_id="odd")
    raw_record(vault, "odd-next", "Quarterly figures, recut", status="archived", supersedes_id="odd-fix")
    assert nb(vault, "record", "odd") is None                       # not a valid focus either
    graph = nb(vault, "record", fix["id"], hops=2, max_nodes=1)
    assert nodes_of(graph) == {("record", "odd-fix")} and graph["edges"] == [] and graph["truncated"] is False


@pytest.mark.parametrize("noise", [0, 1, 40])
def test_f5_exact_capacity_is_independent_of_ineligible_neighbours(vault, noise):
    hub = vault.add("A record cited by five claims")
    cite(vault, hub["id"], [f"c{i}" for i in range(5)], store.evidence_hash(hub))
    cite(vault, hub["id"], [f"a{i:02d}" for i in range(noise)], "0" * 64)     # sort first; never eligible
    for capacity, truncated in ((7, False), (6, False), (5, True), (2, True), (1, True)):
        graph = nb(vault, "record", hub["id"], max_nodes=capacity)
        assert_well_formed(graph)
        assert graph["truncated"] is truncated
        expected = {("record", hub["id"])} | {("claim", f"c{i}") for i in range(min(capacity, 6) - 1)}
        assert nodes_of(graph) == expected                      # deterministic: smallest (kind, id) first
        assert edges_of(graph) == {("SUPPORTED_BY", k, ("record", hub["id"])) for k in expected if k[0] == "claim"}


# --- F-6: typed identity --------------------------------------------------------------------------

def collision(vault):
    """Record X and claim X share an id. Claim X cites record r; claim Y cites record X."""
    r = vault.add("Evidence cited by the claim called X")
    x = raw_record(vault, "X", "The record called X")
    cite(vault, r["id"], ["X"], store.evidence_hash(r), text="The claim called X")
    cite(vault, "X", ["Y"], store.evidence_hash(x), text="The claim called Y")
    return r["id"]


def test_f6_a_record_and_a_claim_sharing_an_id_are_distinct_and_both_reachable(vault):
    r = collision(vault)
    as_record = nb(vault, "record", "X", hops=2)
    as_claim = nb(vault, "claim", "X", hops=2)
    for graph in (as_record, as_claim):
        assert_well_formed(graph)
    assert as_record["focus"] == {"kind": "record", "id": "X"}
    assert node(as_record, ("record", "X"))["text"] == "The record called X"
    assert nodes_of(as_record) == {("record", "X"), ("claim", "Y")}
    assert edges_of(as_record) == {("SUPPORTED_BY", ("claim", "Y"), ("record", "X"))}
    assert as_claim["focus"] == {"kind": "claim", "id": "X"}
    assert node(as_claim, ("claim", "X"))["text"] == "The claim called X"
    assert nodes_of(as_claim) == {("claim", "X"), ("record", r)}
    assert edges_of(as_claim) == {("SUPPORTED_BY", ("claim", "X"), ("record", r))}


def test_f6_forgetting_the_claim_x_leaves_the_record_x_and_vice_versa(vault):
    collision(vault)
    vault.delete_claim("X")
    assert nb(vault, "claim", "X") is None
    graph = nb(vault, "record", "X", hops=2)
    assert nodes_of(graph) == {("record", "X"), ("claim", "Y")}
    vault.delete("X")                     # forgets record X and claim Y, which cites it
    assert nb(vault, "record", "X") is None and nb(vault, "claim", "Y") is None


def test_f6_the_api_addresses_items_by_kind_and_id(tmp_path):
    app = create_app(str(tmp_path / "api.db"))
    client = TestClient(app)
    collision(app.state.vault)
    as_record = client.get("/api/provenance/record/X?hops=2")
    as_claim = client.get("/api/provenance/claim/X?hops=2")
    assert as_record.status_code == 200 and as_record.json()["focus"] == {"kind": "record", "id": "X"}
    assert as_claim.status_code == 200 and as_claim.json()["focus"] == {"kind": "claim", "id": "X"}
    assert client.get("/api/provenance/note/X").status_code == 422           # kind is closed
    assert client.get("/api/provenance/claim/never-existed").status_code == 404
    assert client.get("/api/provenance/X").status_code in (404, 422)         # never resolved without a kind


def test_f6_every_ui_navigation_names_the_kind():
    script = APP_JS.read_text(encoding="utf-8")
    calls = re.findall(r"openProvenance\(([^()]*(?:\([^()]*\)[^()]*)*)\)", script)
    assert calls and "async function openProvenance(kind,id)" in script
    for args in calls:
        if args == "kind,id":
            continue
        assert args.count(",") >= 1, args       # (kind, id), never an id alone


# --- F-7: bounded work, bytes and history ----------------------------------------------------------

class Metered(sqlite3.Connection):
    """Counts SQLite VM work in steps of 10 instructions, and still runs the code's own progress handler."""
    instances: list = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.steps, self.inner, self.every = 0, None, 1
        Metered.instances.append(self)
        super().set_progress_handler(self._tick, 10)

    def _tick(self):
        self.steps += 1
        if self.inner is not None and self.steps % self.every == 0:
            return self.inner()
        return 0

    def set_progress_handler(self, handler, n):
        self.inner, self.every = handler, max(1, n // 10)


def work(monkeypatch, fn):
    real = sqlite3.connect
    Metered.instances = []
    monkeypatch.setattr(store.sqlite3, "connect", lambda *a, **k: real(*a, factory=Metered, **k))
    try:
        result = fn()
    finally:
        monkeypatch.setattr(store.sqlite3, "connect", real)
    return result, sum(c.steps for c in Metered.instances)


def hub(vault, degree, prefix="c", text="An interpretation of the evidence"):
    h = vault.add("A record cited by many claims")
    cite(vault, h["id"], [f"{prefix}{i:05d}" for i in range(degree)], store.evidence_hash(h), text=text)
    return h


def test_f7_traversal_work_does_not_grow_with_hub_degree(tmp_path, monkeypatch):
    measured = {}
    for degree in (100, 3000):
        v = Vault(str(tmp_path / f"hub{degree}.db"))
        h = hub(v, degree)
        graph, steps = work(monkeypatch, lambda: nb(v, "record", h["id"], hops=2))
        assert len(graph["nodes"]) == provenance.MAX_NODES and graph["truncated"] is True
        measured[degree] = steps
    assert measured[3000] <= measured[100] * 1.5, measured


def test_f7_ineligible_links_never_change_the_answer_and_excess_work_fails_closed(tmp_path, monkeypatch):
    v = Vault(str(tmp_path / "noise.db"))
    h = v.add("A record with one verified claim and many unverifiable links")
    cite(v, h["id"], [f"a{i:05d}" for i in range(3000)], "0" * 64)
    cite(v, h["id"], ["z-verified"], store.evidence_hash(h))
    graph = nb(v, "record", h["id"], max_nodes=2)
    assert nodes_of(graph) == {("record", h["id"]), ("claim", "z-verified")} and graph["truncated"] is False
    monkeypatch.setattr(provenance, "WORK_LIMIT", 5)
    with pytest.raises(provenance.ProvenanceTooLarge):
        nb(v, "record", h["id"], max_nodes=2)


def test_f7_response_bytes_are_bounded_for_worst_case_text(tmp_path):
    app = create_app(str(tmp_path / "bytes.db"))
    client = TestClient(app)
    escaped = "\x01" * rules.MAX_TEXT                 # every character serialises as six bytes
    h = hub(app.state.vault, 80, text=escaped)
    for kind, ident in (("record", h["id"]), ("claim", "c00000")):
        for hops in (1, 2):
            status, size, graph = fetch(client, kind, ident, hops)
            assert status == 200
            assert size <= BYTES, (kind, hops, size)
            assert_well_formed(graph)
            for n in graph["nodes"]:
                if (n["kind"], n["id"]) != (kind, ident):
                    assert len(n["text"]) <= 400 and "history" not in n
                    assert n["text_truncated"] is (n["kind"] == "claim")


def test_f7_the_byte_budget_truncates_consistently(vault, monkeypatch):
    h = hub(vault, 30, text="y" * 300)
    monkeypatch.setattr(provenance, "MAX_RESPONSE_BYTES", 4000)
    graph = nb(vault, "record", h["id"])
    assert_well_formed(graph)
    assert wire(graph) <= 4000 and graph["truncated"] is True and 1 < len(graph["nodes"]) < 31


def test_f7_focus_history_is_the_most_recent_decisions_and_stored_history_is_untouched(vault):
    r = vault.add("Evidence for a long-debated claim")
    c = vault.add_claim("A long-debated claim", [r["id"]])
    with closing(raw(vault)) as db:                 # 1,500 legitimate human decisions in one transaction
        db.execute("BEGIN")
        status = "proposed"
        for i in range(1500):
            to = "contested" if status == "approved" else "approved"
            db.execute("INSERT INTO claim_events(claim_id,from_status,to_status,actor,note,at) VALUES(?,?,?,'human',?,?)",
                       (c["id"], status, to, f"decision {i:04d} " + "n" * 480, T))
            status = to
        db.execute("COMMIT")
    graph = nb(vault, "claim", c["id"])
    focus = node(graph, ("claim", c["id"]))
    assert len(focus["history"]) == HISTORY and focus["history_complete"] is False
    assert [e["note"][:13] for e in focus["history"]] == [f"decision {i:04d}" for i in range(1450, 1500)]
    assert wire(graph) <= BYTES
    assert "history" not in node(graph, ("record", r["id"]))
    stored = next(x for x in vault.export()["claims"] if x["id"] == c["id"])
    listed = next(x for x in vault.list_claims() if x["id"] == c["id"])
    assert len(stored["history"]) == 1501 and len(listed["history"]) == 1501


def test_f7_history_hydration_work_does_not_grow_with_history(tmp_path, monkeypatch):
    measured = {}
    for length in (100, 3000):            # both beyond the 50 decisions shown
        v = Vault(str(tmp_path / f"history{length}.db"))
        r = v.add("Evidence")
        c = v.add_claim("A claim", [r["id"]])
        with closing(raw(v)) as db:
            db.execute("BEGIN")
            status = "proposed"
            for i in range(length):
                to = "contested" if status == "approved" else "approved"
                db.execute("INSERT INTO claim_events(claim_id,from_status,to_status,actor,at) VALUES(?,?,?,'human',?)",
                           (c["id"], status, to, T))
                status = to
            db.execute("COMMIT")
        _, measured[length] = work(monkeypatch, lambda: nb(v, "claim", c["id"]))
    assert measured[3000] <= measured[100] * 1.5, measured


# --- Forget and snapshot consistency --------------------------------------------------------------

def test_a_forget_racing_a_read_never_mixes_snapshots(vault, monkeypatch):
    h = vault.add("A record three claims rest on")
    claims = [vault.add_claim(f"Interpretation number {i}", [h["id"]]) for i in range(3)]
    before = nb(vault, "record", h["id"], hops=2)
    paused, release, out = threading.Event(), threading.Event(), {}
    real = Vault._claim

    def slow(self, db, row, *args, **kwargs):     # pause the read after its first claim is loaded
        if threading.current_thread().name == "reader" and not paused.is_set():
            paused.set()
            release.wait(10)
        return real(self, db, row, *args, **kwargs)

    monkeypatch.setattr(Vault, "_claim", slow)
    reader = threading.Thread(name="reader", target=lambda: out.setdefault("graph", nb(vault, "record", h["id"], hops=2)))
    writer = threading.Thread(name="writer", target=lambda: out.setdefault("forget", vault.delete_claim(claims[0]["id"])))
    reader.start()
    assert paused.wait(10)
    writer.start()
    writer.join(0.5)
    assert writer.is_alive() and "forget" not in out          # the Forget waits for the read's snapshot to end
    release.set()
    reader.join(10)
    writer.join(10)
    assert out["graph"] == before                              # one snapshot: entirely before the Forget
    after = nb(vault, "record", h["id"], hops=2)
    assert ("claim", claims[0]["id"]) not in nodes_of(after)
    assert "Interpretation number 0" not in json.dumps(after)
    assert nodes_of(after) == nodes_of(before) - {("claim", claims[0]["id"])}
