"""Benchmark 0003 harness (evaluation/retrieval): ground truth, determinism, isolation and policy invariants.

The harness measures retrieval; it must never change it. These tests pin that the committed results are
what the code produces, that experiments run through the production candidate selection and policy, and
that no relevance function, however it ranks, can put an ineligible or sensitive item into a plan.
"""
import copy
import json
import re
import sqlite3
import tempfile
from types import SimpleNamespace

import pytest

from evaluation.retrieval import harness
from evaluation.retrieval.retrievers import Aliases, Document, Retriever, build, documents
from sovereign.context import compile_context, scorer


def _fts5() -> bool:
    try:
        sqlite3.connect(":memory:").execute("CREATE VIRTUAL TABLE t USING fts5(x, tokenize='porter unicode61')")
        return True
    except sqlite3.OperationalError:
        return False


pytestmark = pytest.mark.skipif(not _fts5(), reason="this SQLite build has no FTS5")


@pytest.fixture(scope="module")
def results():
    return harness.evaluate()


@pytest.fixture(scope="module")
def setup():
    corpus, queries, aliases = harness.load()
    directory = tempfile.mkdtemp(prefix="sovereign-benchmark-0003-test-")
    vault = harness.build_vault(directory, corpus)
    docs = documents(vault.export())
    return SimpleNamespace(corpus=corpus, queries=queries, aliases=aliases, vault=vault, docs=docs,
                           retrievers=build(docs, aliases))


def test_committed_artifacts_are_what_the_code_produces(results):
    """results.json and report.md are regenerated with `python -m evaluation.retrieval`, never edited by hand."""
    assert (harness.HERE / "results.json").read_text("utf-8") == harness.to_json(results), \
        "results.json is stale: run `python -m evaluation.retrieval`"
    assert (harness.HERE / "report.md").read_text("utf-8") == harness.report(results), \
        "report.md is stale: run `python -m evaluation.retrieval`"


def test_evaluation_is_deterministic(results):
    assert harness.to_json(harness.evaluate()) == harness.to_json(results)


def test_ground_truth_agrees_with_policy_and_typos_are_caught(setup):
    assert harness.validate(setup.queries, setup.docs, setup.vault) == []
    broken = copy.deepcopy(setup.queries)
    broken["queries"][0]["expected"][0]["local"] = "contested"           # an active record is never contested
    broken["queries"][1]["acceptable"].append("r-does-not-exist")
    broken["queries"][16]["expected"][0].pop("cloud")                     # sensitive evidence would be sent
    errors = harness.validate(broken, setup.docs, setup.vault)
    assert any("q01: r-bike-03 local expected contested, policy gives evidence" in e for e in errors)
    assert any("q02: unknown id r-does-not-exist" in e for e in errors)
    assert any("q17: r-health-01 cloud expected evidence, policy gives sensitive_cloud" in e for e in errors)


def test_corpus_restores_completely_and_contains_no_contact_details(setup):
    payload = harness.restore_payload(setup.corpus)
    assert len(setup.docs) == len(payload["records"]) + len(payload["claims"]) == 270
    texts = " ".join(d.text for d in setup.docs)
    assert not re.search(r"@|https?://|www\.|\+?\d[\d ()-]{8,}\d", texts), "synthetic notes carry no contact details"


def test_experiments_run_through_the_production_compiler(setup):
    """With the production relevance function, the experiment path is exactly `compile_context`."""
    class Same(Retriever):
        name, description = "same", "production scorer through the experiment path"

        def scorer(self, question):
            return scorer(question)

    for q in setup.queries["queries"]:
        for provider in harness.TARGETS.values():
            assert (harness.compile_with(setup.vault, Same(), q["question"], provider).context_token
                    == compile_context(setup.vault, q["question"], provider, []).context_token)


def test_no_relevance_function_can_include_ineligible_or_sensitive_items(results, setup):
    for name, r in results["retrievers"].items():
        for boundary in harness.TARGETS:
            outcomes = r["summary"][boundary]["outcomes"]
            assert outcomes["policy_violation"] == outcomes["policy_mismatch"] == 0, name
    for retriever in setup.retrievers:
        for q in setup.queries["queries"]:
            bundle = harness.compile_with(setup.vault, retriever, q["question"], "openai")
            for item in bundle.included:
                c = item.candidate
                assert c.sensitivity == "private", (retriever.name, q["id"], c.id)
                assert (c.type, c.status, c.support) in {("source", "active", None), ("claim", "approved", "supported")}


def test_merged_retrieval_keeps_tokens_stable_under_unrelated_writes(results):
    changed = {name: r["summary"]["tokens_changed_by_unrelated_write"] for name, r in results["retrievers"].items()}
    assert changed["baseline"] == changed["porter_count"] == 0
    assert changed["porter_idf"] > 0 and changed["fts5_porter_bm25"] > 0   # vault-wide statistics enter the fingerprint


def _bundle(included=(), excluded=()):
    item = lambda i, role: SimpleNamespace(candidate=SimpleNamespace(id=i), role=role)
    gone = lambda i, reason: SimpleNamespace(candidate=SimpleNamespace(id=i), reason=reason)
    return SimpleNamespace(included=[item(*x) for x in included], excluded=[gone(*x) for x in excluded])


@pytest.mark.parametrize("want, bundle, score, outcome", [
    ("evidence", _bundle(included=[("a", "evidence")]), 1, "recalled"),
    ("evidence", _bundle(included=[("x", "evidence")], excluded=[("a", "budget_exceeded")]), 1, "ranking_failure/outranked"),
    ("evidence", _bundle(included=[("b", "evidence")], excluded=[("a", "budget_exceeded")]), 1, "budget_failure"),
    ("approved_memory", _bundle(excluded=[("a", "not_relevant")]), 0, "retrieval_failure/provenance_only"),
    ("evidence", _bundle(), 3, "ranking_failure/below_cutoff"),
    ("evidence", _bundle(), 0, "retrieval_failure/no_match"),
    ("evidence", _bundle(excluded=[("a", "superseded")]), 1, "policy_mismatch"),
    ("contested", _bundle(excluded=[("a", "contested")]), 1, "policy_excluded"),
    ("contested", _bundle(excluded=[("a", "stale")]), 1, "policy_mismatch"),
    ("contested", _bundle(included=[("a", "approved_memory")]), 1, "policy_violation"),
    ("contested", _bundle(), 0, "retrieval_failure/no_match"),
])
def test_outcome_taxonomy(want, bundle, score, outcome):
    assert harness._outcome("a", want, bundle, {"a": score}, {"a", "b"}) == outcome


def test_relevance_ranking_breaks_ties_newest_first_then_by_id():
    docs = [Document("b", "source", "x", "2025-01-01", ()), Document("a", "source", "y", "2025-01-01", ()),
            Document("c", "source", "z", "2026-01-01", ()), Document("d", "source", "w", "2027-01-01", ())]
    points = {"x": 1, "y": 1, "z": 1, "w": 0}
    assert harness.ranking(docs, lambda text: (points[text], ())) == ["c", "a", "b"]


def test_alias_map_rewrites_whole_words_and_keeps_inflections():
    aliases = Aliases(json.loads((harness.HERE / "aliases.json").read_text("utf-8"))["groups"])
    assert aliases("Fixed the couch; prefix unchanged.") == "repaired the sofa; prefix unchanged."
    assert aliases("Ask the Project Manager") == "ask the pm"
    assert aliases("Two movies") == "two films"
