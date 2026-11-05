"""Regressions for the second Codex audit of PR #11 at 7b8dec8, finding F-7: memory allocated before graph output.

The audit imported a record with a valid but very long timestamp and found the graph allocating about 100 MB in
Python to return a few hundred bytes. The node, byte and work limits applied only after values were materialised.
These tests measure Python's peak allocation during the graph read (tracemalloc), not only the response size.

Builder-written: the finding ID is the audit's, and each test states the property it checks. Synthetic data only.
"""
from __future__ import annotations

import json
import sqlite3
import traceback
import tracemalloc
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from sovereign import context, provenance, store
from sovereign.app import create_app
from sovereign.store import Vault

T = "2026-10-22T00:00:00+00:00"
MARK = "SYNTHETIC-SECRET"
BIG = 16 * 2**20               # an oversized value: 16 MiB, far above provenance.VALUE_BYTES
PEAK = 2 * 2**20               # Python allocation allowed for one graph read that touches it
EMOJI = "\U0001F600"           # four bytes in UTF-8


@pytest.fixture
def vault(tmp_path):
    return Vault(str(tmp_path / "vault.db"))


def peak_of(fn):
    """(result or raised exception, peak bytes Python allocated while fn ran)."""
    tracemalloc.start()
    try:
        tracemalloc.reset_peak()
        try:
            result = fn()
        except Exception as exc:  # noqa: BLE001 - the exception is the result under test
            result = exc
        return result, tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def graph_peak(vault, kind, ident, **kw):
    return peak_of(lambda: provenance.neighborhood(vault, kind, ident, **kw))


def big_time(n=BIG):
    """A timestamp the importer accepts: a valid instant with excess fractional-second digits."""
    return "2026-10-22T00:00:00." + "0" * n + "+00:00"


def payload(records=(), claims=()):
    return {"schema": store.EXPORT_SCHEMA, "records": list(records), "tombstones": [], "claims": list(claims),
            "claim_tombstones": []}


def raw(vault):
    db = sqlite3.connect(vault.path, isolation_level=None)
    db.execute("PRAGMA ignore_check_constraints=ON")   # an ordinary connection; triggers still apply
    return db


def nodes_of(graph):
    return {(n["kind"], n["id"]) for n in graph["nodes"]}


def assert_content_free(exc):
    assert isinstance(exc, provenance.ProvenanceTooLarge), exc
    text = "".join(traceback.format_exception(exc))
    assert MARK not in text and "0" * 64 not in text and EMOJI * 8 not in text and "s" * 64 not in text
    assert exc.__cause__ is None and exc.__suppress_context__


def import_big_record(vault, ident="imported-ts"):
    vault.import_untrusted(payload([{"id": ident, "content": "Imported synthetic note " + MARK, "source": "import",
                                     "sensitivity": "private", "status": "active", "created_at": big_time()}]))
    return ident


# --- 1. The audit's case --------------------------------------------------------------------------

def test_f7_codex_an_imported_record_with_an_oversized_timestamp_is_refused_before_it_is_loaded(vault):
    ident = import_big_record(vault)
    result, peak = graph_peak(vault, "record", ident)
    assert_content_free(result)
    assert peak < PEAK, peak                  # 7b8dec8: several times the 16 MiB value, for a ~300-byte answer


def test_f7_codex_the_api_answers_409_with_a_fixed_message(tmp_path):
    app = create_app(str(tmp_path / "api.db"))
    ident = import_big_record(app.state.vault)
    response = TestClient(app).get(f"/api/provenance/record/{ident}")
    assert response.status_code == 409
    assert response.json() == {"detail": "This item cannot be shown within the provenance size limit."}


# --- 2. Oversized but valid legacy text and metadata ------------------------------------------------

def legacy(ident, content="Legacy synthetic note " + MARK, **fields):
    return {"id": ident, "content": content, "source": "manual", "sensitivity": "private", "status": "active",
            "created_at": T, "supersedes_id": None, "legacy": 1, **fields}


@pytest.mark.parametrize("field", ["source", "created_at"])
def test_f7_oversized_legacy_metadata_is_refused_before_it_is_loaded(vault, field):
    vault.restore_trusted(payload([legacy("legacy/big", content="Legacy\x00note " + MARK, **{field: "s" * BIG})]))
    result, peak = graph_peak(vault, "record", "legacy/big")
    assert_content_free(result)
    assert peak < PEAK, peak


def test_f7_a_legacy_neighbour_with_an_oversized_id_fails_closed_without_loading_it(vault):
    vault.restore_trusted(payload([legacy("legacy/root", status="superseded"),
                                   legacy("legacy/" + "i" * BIG, supersedes_id="legacy/root")]))
    result, peak = graph_peak(vault, "record", "legacy/root")
    assert_content_free(result)               # the neighbour list itself cannot be read within the limit
    assert peak < PEAK, peak


def test_f7_legacy_text_whose_sqlite_length_stops_at_a_nul_is_measured_in_bytes(vault):
    with closing(raw(vault)) as db:           # length() counts 1 here, so the storage trigger lets it in
        db.execute("INSERT INTO records(id,content,source,sensitivity,status,created_at,legacy) "
                   "VALUES('legacy/nul', ?, 'manual', 'private', 'active', ?, 1)", ("a\x00" + "b" * BIG, T))
    result, peak = graph_peak(vault, "record", "legacy/nul")
    assert_content_free(result)
    assert peak < PEAK, peak


def test_f7_a_blob_where_text_belongs_is_measured_in_bytes(vault):
    r = vault.add("Evidence")
    with closing(raw(vault)) as db:           # CHECKs off: a claim time stored as a BLOB
        db.execute("INSERT INTO claims(id,text,origin,status,created_at) VALUES('blob-time','A claim','human','proposed',?)",
                   (b"\x01" * BIG,))
        db.execute("INSERT INTO claim_sources(claim_id,record_id,evidence_sha256) VALUES('blob-time',?,?)",
                   (r["id"], store.evidence_hash(r)))
    result, peak = graph_peak(vault, "claim", "blob-time")
    assert_content_free(result)               # 7b8dec8: a TypeError from JSON serialisation (an HTTP 500)
    assert peak < PEAK, peak


def test_f7_legitimate_text_at_its_limits_is_shown_whole(vault):
    """The limit refuses nothing a bounded field can hold: content at 10,000 four-byte characters (40,000 bytes),
    legacy text with an embedded NUL, and legacy metadata up to VALUE_BYTES, all counted in bytes."""
    under, over = EMOJI * (provenance.VALUE_BYTES // 4), EMOJI * (provenance.VALUE_BYTES // 4 + 1)
    vault.restore_trusted(payload([legacy("legacy/nul-ok", content="Legacy\x00note"), legacy("legacy/under", source=under),
                                   legacy("legacy/over", source=over)]))
    full = vault.add(EMOJI * store.MAX_CONTENT)
    focus = provenance.neighborhood(vault, "record", full["id"])["nodes"][0]
    assert focus["text"] == EMOJI * store.MAX_CONTENT and focus["text_truncated"] is False
    assert provenance.neighborhood(vault, "record", "legacy/nul-ok")["nodes"][0]["text"] == "Legacy\x00note"
    assert provenance.neighborhood(vault, "record", "legacy/under") is not None
    with pytest.raises(provenance.ProvenanceTooLarge):     # 65,540 bytes in 16,385 characters
        provenance.neighborhood(vault, "record", "legacy/over")


# --- 3. Large evidence reached through links ------------------------------------------------------

def test_f7_large_evidence_behind_an_incoming_link_is_left_out_not_loaded(vault):
    local = vault.add("Local synthetic evidence")
    import_big_record(vault, "imported-big")
    claim = vault.add_claim("A claim citing local and imported evidence", [local["id"], "imported-big"])
    result, peak = graph_peak(vault, "record", local["id"], hops=2)
    assert peak < PEAK, peak
    assert nodes_of(result) == {("record", local["id"])} and result["edges"] == []
    assert result["truncated"] is True        # an eligible neighbour (the claim) was left out by the value-size limit
    result, peak = graph_peak(vault, "claim", claim["id"])
    assert_content_free(result)               # as focus, its support cannot be verified within the limit
    assert peak < PEAK, peak


def test_f7_an_unreadable_neighbour_uses_no_capacity(vault):
    local = vault.add("Local synthetic evidence")
    import_big_record(vault, "imported-big")
    vault.add_claim("Claim A cites the imported record", [local["id"], "imported-big"])
    readable = [vault.add_claim(f"Claim {i} cites only local evidence", [local["id"]]) for i in range(3)]
    graph = provenance.neighborhood(vault, "record", local["id"], max_nodes=4)   # exactly the focus + 3 readable
    assert nodes_of(graph) == {("record", local["id"])} | {("claim", c["id"]) for c in readable}
    assert graph["truncated"] is True         # the unreadable one is still an eligible neighbour left out


# --- 4. High-degree neighbourhoods ----------------------------------------------------------------

def fat_hub(vault, degree):
    fat = EMOJI * store.MAX_CONTENT           # every record at the content limit: 40,000 bytes
    hub = vault.add(fat)
    others = [vault.add(fat[:-1] + str(i)) for i in range(7)]
    links = [(r["id"], store.evidence_hash(r)) for r in [hub, *others]]
    with closing(raw(vault)) as db:
        db.execute("BEGIN")
        for i in range(degree):
            cid = f"c{i:05d}"
            db.execute("INSERT INTO claims(id,text,origin,status,created_at) VALUES(?,?,'human','proposed',?)",
                       (cid, "An interpretation " + "x" * 1900, T))
            for rid, digest in links:
                db.execute("INSERT INTO claim_sources(claim_id,record_id,evidence_sha256) VALUES(?,?,?)", (cid, rid, digest))
            db.execute("INSERT INTO claim_events(claim_id,from_status,to_status,actor,at) VALUES(?,NULL,'proposed','human',?)",
                       (cid, T))
        db.execute("COMMIT")
    return hub


def test_f7_a_high_degree_neighbourhood_keeps_only_what_expansion_needs(vault):
    hub = fat_hub(vault, 120)
    for kind, ident, hops in (("record", hub["id"], 1), ("record", hub["id"], 2), ("claim", "c00000", 2)):
        graph, peak = graph_peak(vault, kind, ident, hops=hops)
        assert len(graph["nodes"]) == provenance.MAX_NODES and graph["truncated"] is True
        assert peak < 4 * 2**20, (kind, hops, peak)     # 7b8dec8 kept every admitted claim's evidence: ~19 MB
    graph = provenance.neighborhood(vault, "record", hub["id"])
    assert len([e for e in graph["edges"] if e["type"] == "SUPPORTED_BY"]) == provenance.MAX_NODES - 1
    # every edge above is a verified link: the evidence hash was computed over the whole 40,000-byte content


# --- 5. Long-lived claims ---------------------------------------------------------------------------

def test_f7_allocation_does_not_grow_with_decision_history(tmp_path):
    peaks = {}
    for n in (100, 1500):
        v = Vault(str(tmp_path / f"h{n}.db"))
        r = v.add("Evidence for a long-debated claim")
        c = v.add_claim("A long-debated claim", [r["id"]])
        with closing(raw(v)) as db:
            db.execute("BEGIN")
            status = "proposed"
            for i in range(n):
                to = "contested" if status == "approved" else "approved"
                db.execute("INSERT INTO claim_events(claim_id,from_status,to_status,actor,note,at) "
                           "VALUES(?,?,?,'human',?,?)", (c["id"], status, to, f"decision {i:04d} " + EMOJI * 485, T))
                status = to
            db.execute("COMMIT")
        graph, peaks[n] = graph_peak(v, "claim", c["id"])
        assert len(next(x for x in graph["nodes"] if x["kind"] == "claim")["history"]) == 50
    assert peaks[1500] < PEAK and peaks[1500] <= peaks[100] * 1.5 + 64 * 1024, peaks


def test_f7_an_oversized_decision_time_is_refused_for_the_focus(vault):
    r = vault.add("Evidence")
    c = vault.add_claim("A claim", [r["id"]])
    with closing(raw(vault)) as db:           # a trusted restore accepts any text time; this is the same state
        db.execute("INSERT INTO claim_events(claim_id,from_status,to_status,actor,at) VALUES(?,'proposed','approved','human',?)",
                   (c["id"], big_time()))
    result, peak = graph_peak(vault, "claim", c["id"])
    assert_content_free(result)
    assert peak < PEAK, peak


# --- 9. Navigation is not relevance: no side effect on the Context Compiler ----------------------

def test_f7_refused_and_bounded_reads_leave_context_fingerprints_unchanged(vault):
    local = vault.add("Lantern readings from the synthetic device")
    import_big_record(vault, "imported-big")
    vault.add_claim("Lantern readings are synthetic", [local["id"]])
    tokens = lambda: [context.compile_context(vault, "Lantern readings device", p, []).context_token
                      for p in ("local", "kimi", "openai")]
    before = tokens()
    with pytest.raises(provenance.ProvenanceTooLarge):
        provenance.neighborhood(vault, "record", "imported-big")
    provenance.neighborhood(vault, "record", local["id"], hops=2)
    assert tokens() == before
    assert json.dumps(before)                 # tokens are plain strings; nothing of the graph reaches them
