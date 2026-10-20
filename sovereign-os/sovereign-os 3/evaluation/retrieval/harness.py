"""Benchmark 0003: offline evaluation of Context Compiler retrieval (docs/benchmarks/0003-retrieval-evaluation.md).

Builds a throwaway vault from the synthetic corpus through the ordinary trusted-restore path, then, for
every retriever and query, compiles the context with the production Context Compiler for a local and a
cloud target (no provider is ever called) and compares it with the ground truth.

Two views are measured:
- **Retrieval, before policy:** the retriever's own relevance ranking of every matching record and claim
  (score, then newest, then id: the production tie-break), giving Recall@K and MRR over all expected items.
- **Governed context, after policy:** what the compiled bundle actually includes, giving governed recall,
  noise and an outcome for every expected item (see OUTCOMES).

Deterministic: fixed timestamps and ids, total orderings, rounded numbers, no clock or randomness.
"""
from __future__ import annotations

from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import tempfile

from sovereign import context
from sovereign.context import POLICY, build_bundle, compile_context, inherited_sensitivity
from sovereign.store import Vault, evidence_hash

from .retrievers import Aliases, Document, Retriever, build, documents

HERE = Path(__file__).resolve().parent
BENCHMARK = "0003-retrieval-evaluation"
TARGETS = {"local": "local", "cloud": "openai"}   # boundary -> provider id; compiling never calls a provider
KS = (1, 5, 10, 50)
ROLES = ("evidence", "approved_memory")
# The outcome of one expected item in one compiled context. The first five are the failure taxonomy.
OUTCOMES = {
    "recalled": "Successful governed recall: an eligible item is in the context in its expected role.",
    "policy_excluded": "Authority/policy exclusion: an ineligible item was retrieved and excluded for the expected "
                       "reason. Correct behaviour, not a retrieval failure.",
    "retrieval_failure": "Retrieval failure: the item never matched the question (no_match), or surfaced only as a "
                         "provenance link without matching it, which policy treats as not relevant (provenance_only).",
    "ranking_failure": "Ranking failure: the item matched but ranked below the per-kind retrieval cutoff "
                       "(below_cutoff), or the budget filled with items ranked above it that the question did not "
                       "require (outranked).",
    "budget_failure": "Context-budget failure: the item was excluded by the budget although every included item was "
                      "itself expected: the budget is too small for this question.",
    "policy_violation": "An item ground truth says is ineligible reached the context. Must never happen.",
    "policy_mismatch": "Excluded for a reason other than the expected one (a ground-truth or policy error).",
}
FAILURES = ("retrieval_failure", "ranking_failure", "budget_failure")
# An unrelated write for the token-stability check: a record sharing no word with any question.
CONTROL_RECORD = {"id": "r-control-01", "at": "2026-10-18", "text": "Zebra quokka xylophone."}


# --- Corpus -------------------------------------------------------------------------------------

def load() -> tuple[dict, dict, Aliases]:
    corpus = json.loads((HERE / "corpus.json").read_text("utf-8"))
    queries = json.loads((HERE / "queries.json").read_text("utf-8"))
    aliases = json.loads((HERE / "aliases.json").read_text("utf-8"))
    return corpus, queries, Aliases(aliases["groups"])


def fingerprint() -> str:
    """SHA-256 over the three input files, so a results file names the exact corpus it measured."""
    digest = hashlib.sha256()
    for name in ("corpus.json", "queries.json", "aliases.json"):
        digest.update(name.encode() + b"\0" + (HERE / name).read_bytes() + b"\0")
    return digest.hexdigest()


def _stamp(day: str | date, hours: int = 0) -> str:
    day = date.fromisoformat(day) if isinstance(day, str) else day
    return f"{day.isoformat()}T{9 + hours:02d}:00:00+00:00"


def expand_records(corpus: dict) -> list[dict]:
    """Hand-written records plus every generated family member, in a fixed order."""
    records = [dict(r) for r in corpus["records"]]
    for family in corpus["families"]:
        start = date.fromisoformat(family["start"])
        for n in range(family["count"]):
            slots = {k: family[k][n % len(family[k])] for k in ("a", "b")}
            records.append({"id": f"{family['id']}-{n + 1:03d}", "text": family["template"].format(**slots),
                            "at": start + timedelta(days=n * family["every_days"])})
    return records


def restore_payload(corpus: dict) -> dict:
    """The corpus as a Sovereign backup (export schema 2), so it enters storage through trusted restore."""
    expanded = expand_records(corpus)
    corrected = {r["corrects"] for r in expanded if r.get("corrects")}
    records = [{"id": r["id"], "content": r["text"], "source": "manual", "sensitivity": r.get("sensitivity", "private"),
                "status": "superseded" if r["id"] in corrected else "active", "created_at": _stamp(r["at"]),
                "supersedes_id": r.get("corrects")} for r in expanded]
    by_id = {r["id"]: r for r in records}
    claims = []
    for c in corpus["claims"]:
        history = [{"from_status": None if i == 0 else c["path"][i - 1], "to_status": status, "note": None,
                    "actor": "human", "at": _stamp(c["at"], i)} for i, status in enumerate(c["path"])]
        claims.append({"id": c["id"], "text": c["text"], "origin": "human", "status": c["path"][-1],
                       "created_at": _stamp(c["at"]), "supersedes_id": c.get("supersedes"),
                       "source_ids": c["sources"],
                       "source_hashes": {rid: None if c.get("unverified_link") else evidence_hash(by_id[rid])
                                         for rid in c["sources"]},
                       "history": history})
    return {"schema": "sovereign.v0.records.2", "records": records, "tombstones": [], "claims": claims,
            "claim_tombstones": []}


def build_vault(directory: str, corpus: dict) -> Vault:
    payload = restore_payload(corpus)
    vault = Vault(str(Path(directory) / "evaluation.db"))
    result = vault.restore_trusted(payload)
    if result["imported"] != len(payload["records"]) or result["claims_restored"] != len(payload["claims"]):
        raise RuntimeError(f"Corpus did not restore completely: {result}")
    return vault


def validate(queries: dict, docs: list[Document], vault: Vault) -> list[str]:
    """Ground-truth consistency: ids exist, texts are unique, and every expected outcome is what the
    production policy gives that item once it is relevant (so a typo cannot pose as a retrieval result)."""
    errors = []
    texts = [d.text for d in docs]
    if len(set(texts)) != len(texts):
        errors.append("Corpus texts must be unique (retrievers score text).")
    known = {d.id for d in docs}
    claims = {c["id"]: c for c in vault.list_claims()}
    records = {r["id"]: r for r in vault.export()["records"]}
    seen = set()
    for q in queries["queries"]:
        if q["id"] in seen:
            errors.append(f"{q['id']}: duplicate query id")
        seen.add(q["id"])
        ids = [e["id"] for e in q["expected"]]
        if not ids or len(set(ids)) != len(ids) or set(ids) & set(q["acceptable"]):
            errors.append(f"{q['id']}: expected ids must be non-empty, distinct and not also acceptable")
        for item_id in ids + q["acceptable"]:
            if item_id not in known:
                errors.append(f"{q['id']}: unknown id {item_id}")
        for e in q["expected"]:
            if e["id"] not in known:
                continue
            for boundary in TARGETS:
                want = e.get(boundary, e["local"])
                reasons = _policy_reasons(e["id"], records, claims, boundary)
                got = reasons[0] if reasons else ("approved_memory" if e["id"] in claims else "evidence")
                if want != got:
                    errors.append(f"{q['id']}: {e['id']} {boundary} expected {want}, policy gives {got}")
    return errors


def _policy_reasons(item_id: str, records: dict, claims: dict, boundary: str) -> tuple[str, ...]:
    """The production exclusion reasons for an item as a relevant, unpinned candidate."""
    if item_id in claims:
        c = claims[item_id]
        candidate = context.RetrievalCandidate(c["id"], "claim", c["text"], c["created_at"], c["status"], c["support"],
                                               inherited_sensitivity(c["sources"]), tuple(c["source_ids"]), c["origin"],
                                               False, 1, (), "lexical")
    else:
        r = records[item_id]
        candidate = context.RetrievalCandidate(r["id"], "source", r["content"], r["created_at"], r["status"], None,
                                               r["sensitivity"], (), None, False, 1, (), "lexical")
    return context._reasons(candidate, boundary, POLICY)


# --- Evaluation ---------------------------------------------------------------------------------

def compile_with(vault: Vault, retriever: Retriever, question: str, provider: str) -> context.ContextBundle:
    """Production compilation; only the relevance function differs between retrievers."""
    if retriever.production:
        return compile_context(vault, question, provider, [])
    facts = vault.context_candidates(retriever.scorer(question), [], POLICY.retrieval_limit)
    return build_bundle(question, provider, [], facts, POLICY)


def ranking(docs: list[Document], score) -> list[str]:
    """The retriever's relevance ranking of every matching record and claim, before cutoff and policy."""
    scored = [(score(d.text)[0], d) for d in docs]
    hits = sorted((pair for pair in scored if pair[0]), key=lambda pair: pair[1].id)
    hits.sort(key=lambda pair: pair[1].created_at, reverse=True)
    hits.sort(key=lambda pair: -pair[0])
    return [d.id for _, d in hits]


def _outcome(item_id: str, want: str, bundle, scores: dict, expected: set[str]) -> str:
    included = {i.candidate.id: i.role for i in bundle.included}
    excluded = {e.candidate.id: e for e in bundle.excluded}
    if want in ROLES:
        if included.get(item_id) == want:
            return "recalled"
        if item_id in included:
            return "policy_mismatch"
        if item_id in excluded:
            reason = excluded[item_id].reason
            if reason == "budget_exceeded":
                unrequired = [i for i in included if i not in expected]
                return "ranking_failure/outranked" if unrequired else "budget_failure"
            if reason == "not_relevant":
                return "retrieval_failure/provenance_only"
            return "policy_mismatch"
    else:
        if item_id in included:
            return "policy_violation"
        if item_id in excluded:
            return "policy_excluded" if excluded[item_id].reason == want else "policy_mismatch"
    return "ranking_failure/below_cutoff" if scores[item_id] else "retrieval_failure/no_match"


def evaluate_query(vault: Vault, docs: list[Document], retriever: Retriever, q: dict) -> dict:
    score = retriever.scorer(q["question"])
    scores = {d.id: score(d.text)[0] for d in docs}
    ranked = ranking(docs, score)
    position = {item_id: i + 1 for i, item_id in enumerate(ranked)}
    expected = [e["id"] for e in q["expected"]]
    relevant = set(expected) | set(q["acceptable"])
    first = min((position[i] for i in expected if i in position), default=None)
    out = {
        "ranks": {i: position.get(i) for i in expected},
        "recall": {str(k): _round(sum(1 for i in expected if position.get(i, k + 1) <= k) / len(expected)) for k in KS},
        "reciprocal_rank": _round(1 / first) if first else 0.0,
        "matched": len(ranked),
    }
    for boundary, provider in TARGETS.items():
        bundle = compile_with(vault, retriever, q["question"], provider)
        outcomes = {e["id"]: _outcome(e["id"], e.get(boundary, e["local"]), bundle, scores, set(expected))
                    for e in q["expected"]}
        eligible = [e["id"] for e in q["expected"] if e.get(boundary, e["local"]) in ROLES]
        reasons: dict[str, int] = {}
        for e in bundle.excluded:
            reasons[e.reason] = reasons.get(e.reason, 0) + 1
        out[boundary] = {
            "outcomes": outcomes,
            "eligible": len(eligible),
            "recalled": sum(outcomes[i] == "recalled" for i in eligible),
            "returned": len(bundle.included) + len(bundle.excluded),
            "included": len(bundle.included),
            "noise": sorted(i.candidate.id for i in bundle.included if i.candidate.id not in relevant),
            "excluded_reasons": dict(sorted(reasons.items())),
            "budget_binding": "budget_exceeded" in reasons,
            "budget_dropped_expected": any(o in ("budget_failure", "ranking_failure/outranked") for o in outcomes.values()),
        }
    return out


def _round(value: float) -> float:
    return round(value, 4)


def summarise(per_query: dict, queries: list[dict], docs: list[Document]) -> dict:
    n = len(queries)
    summary = {
        "queries": n,
        "scanned_per_query": len(docs),
        "recall_at": {str(k): _round(sum(r["recall"][str(k)] for r in per_query.values()) / n) for k in KS},
        "mrr": _round(sum(r["reciprocal_rank"] for r in per_query.values()) / n),
        "matched_mean": _round(sum(r["matched"] for r in per_query.values()) / n),
    }
    for boundary in TARGETS:
        rows = [r[boundary] for r in per_query.values()]
        counted = [row for row in rows if row["eligible"]]
        outcomes: dict[str, int] = {}
        reasons: dict[str, int] = {}
        for row in rows:
            for o in row["outcomes"].values():
                outcomes[o] = outcomes.get(o, 0) + 1
            for reason, count in row["excluded_reasons"].items():
                reasons[reason] = reasons.get(reason, 0) + count
        categories = {c: sum(v for o, v in outcomes.items() if o.split("/")[0] == c) for c in OUTCOMES}
        summary[boundary] = {
            "governed_recall": _round(sum(row["recalled"] / row["eligible"] for row in counted) / len(counted)),
            "governed_recall_items": f"{sum(row['recalled'] for row in rows)}/{sum(row['eligible'] for row in rows)}",
            "queries_fully_recalled": sum(row["recalled"] == row["eligible"] for row in counted),
            "queries_with_eligible_items": len(counted),
            "outcomes": categories,
            "outcome_details": dict(sorted(outcomes.items())),
            "noise_total": sum(len(row["noise"]) for row in rows),
            "context_precision": _round(1 - sum(len(row["noise"]) for row in rows) / sum(row["included"] for row in rows)),
            "returned_mean": _round(sum(row["returned"] for row in rows) / n),
            "included_mean": _round(sum(row["included"] for row in rows) / n),
            "excluded_reasons": dict(sorted(reasons.items())),
            "budget_binding_queries": sum(row["budget_binding"] for row in rows),
            "budget_dropped_expected_queries": sum(row["budget_dropped_expected"] for row in rows),
        }
    return summary


def by_tag(per_query: dict, queries: list[dict]) -> dict:
    tags = sorted({t for q in queries for t in q["tags"]})
    out = {}
    for tag in tags:
        rows = [per_query[q["id"]] for q in queries if tag in q["tags"]]
        local = [r["local"] for r in rows]
        failures = {c: sum(o.split("/")[0] == c for row in local for o in row["outcomes"].values()) for c in FAILURES}
        out[tag] = {"queries": len(rows),
                    "recall_at_10": _round(sum(r["recall"]["10"] for r in rows) / len(rows)),
                    "mrr": _round(sum(r["reciprocal_rank"] for r in rows) / len(rows)),
                    "governed_recall_items": f"{sum(r['recalled'] for r in local)}/{sum(r['eligible'] for r in local)}",
                    "failures": failures}
    return out


def local_tokens(vault: Vault, retriever: Retriever, queries: list[dict]) -> dict[str, str]:
    return {q["id"]: compile_with(vault, retriever, q["question"], "local").context_token for q in queries}


def token_changes(directory: Path, corpus: dict, queries: list[dict], aliases: Aliases, before: dict) -> dict[str, int]:
    """Per retriever, how many local context tokens one unrelated write invalidates.

    A pending approval should survive changes that cannot affect its plan. Scores enter the retrieval
    fingerprint (ADR-0004), so a score that depends on vault-wide statistics (IDF, BM25) changes with
    every write: still safe (fail-closed, 409 and re-preview), but every pending preview goes stale.
    """
    vault = build_vault(str(directory), {**corpus, "records": corpus["records"] + [CONTROL_RECORD]})
    docs = documents(vault.export())
    changed = {}
    for retriever in build(docs, aliases):
        for q in queries:
            if retriever.scorer(q["question"])(CONTROL_RECORD["text"])[0]:
                raise RuntimeError(f"The control record matches {q['id']} under {retriever.name}.")
        after = local_tokens(vault, retriever, queries)
        changed[retriever.name] = sum(after[qid] != token for qid, token in before[retriever.name].items())
    return changed


def evaluate() -> dict:
    corpus, queries, aliases = load()
    with tempfile.TemporaryDirectory(prefix="sovereign-benchmark-0003-") as directory:
        vault = build_vault(directory, corpus)
        docs = documents(vault.export())
        errors = validate(queries, docs, vault)
        if errors:
            raise ValueError("Invalid ground truth:\n" + "\n".join(errors))
        retrievers = build(docs, aliases)
        results = {}
        for retriever in retrievers:
            per_query = {q["id"]: evaluate_query(vault, docs, retriever, q) for q in queries["queries"]}
            results[retriever.name] = {"description": retriever.description,
                                       "summary": summarise(per_query, queries["queries"], docs),
                                       "by_tag": by_tag(per_query, queries["queries"]),
                                       "queries": per_query}
        before = {r.name: local_tokens(vault, r, queries["queries"]) for r in retrievers}
        control = Path(directory) / "control"
        control.mkdir()
        for name, count in token_changes(control, corpus, queries["queries"], aliases, before).items():
            results[name]["summary"]["tokens_changed_by_unrelated_write"] = count
    return {
        "benchmark": BENCHMARK,
        "inputs_sha256": fingerprint(),
        "corpus": {"records": sum(d.kind == "source" for d in docs), "claims": sum(d.kind == "claim" for d in docs),
                   "queries": len(queries["queries"]),
                   "expected_items": sum(len(q["expected"]) for q in queries["queries"])},
        "policy": {"version": POLICY.version, "max_items": POLICY.max_items, "max_chars": POLICY.max_chars,
                   "retrieval_limit": POLICY.retrieval_limit},
        "outcomes": OUTCOMES,
        "retrievers": results,
    }


# --- Output -------------------------------------------------------------------------------------

def to_json(results: dict) -> str:
    return json.dumps(results, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def report(results: dict) -> str:
    """The human-readable tables (generated; the benchmark document interprets them)."""
    r = results["retrievers"]
    names = list(r)
    queries = json.loads((HERE / "queries.json").read_text("utf-8"))["queries"]
    lines = [
        "# Benchmark 0003 — generated results",
        "",
        f"Generated by `python -m evaluation.retrieval` from inputs `{results['inputs_sha256'][:12]}`. Do not edit by hand. "
        "Interpretation: [`docs/benchmarks/0003-retrieval-evaluation.md`](../../docs/benchmarks/0003-retrieval-evaluation.md).",
        "",
        f"Corpus: {results['corpus']['records']} records, {results['corpus']['claims']} claims; "
        f"{results['corpus']['queries']} queries with {results['corpus']['expected_items']} expected items. "
        f"Policy `{results['policy']['version']}`: {results['policy']['max_items']} items, {results['policy']['max_chars']:,} characters, "
        f"{results['policy']['retrieval_limit']} candidates per kind.",
        "",
        "## Retrieval before policy and governed context",
        "",
        "Recall@K and MRR rank every matching record and claim by the retriever's score (all expected items, eligible or not). "
        "Governed recall is the mean, over queries with eligible items, of the share of eligible expected items in the compiled context.",
        "",
        "Noise counts included items that are neither expected nor acceptable; in a cloud plan they are private items that "
        "would be disclosed if the plan were approved. Precision is the share of included items that are not noise.",
        "",
        "| Retriever | R@1 | R@5 | R@10 | R@50 | MRR | Governed recall (local) | Items (local) | Governed recall (cloud) | Items (cloud) | Noise (local / cloud) | Precision (local / cloud) |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name in names:
        s = r[name]["summary"]
        lines.append(f"| `{name}` | " + " | ".join(_pct(s["recall_at"][str(k)]) for k in KS) + f" | {s['mrr']:.3f} | "
                     f"{_pct(s['local']['governed_recall'])} | {s['local']['governed_recall_items']} | "
                     f"{_pct(s['cloud']['governed_recall'])} | {s['cloud']['governed_recall_items']} | "
                     f"{s['local']['noise_total']} / {s['cloud']['noise_total']} | "
                     f"{_pct(s['local']['context_precision'])} / {_pct(s['cloud']['context_precision'])} |")
    for boundary in TARGETS:
        lines += ["", f"## Outcomes of expected items ({boundary})", "",
                  "| Retriever | Recalled | Policy excluded | Retrieval failure | Ranking failure | Budget failure | Policy violation | Policy mismatch |",
                  "|---|---|---|---|---|---|---|---|"]
        for name in names:
            o = r[name]["summary"][boundary]["outcomes"]
            lines.append(f"| `{name}` | " + " | ".join(str(o[c]) for c in OUTCOMES) + " |")
    lines += ["", "## Failure details (local)", "", "| Retriever | " + " | ".join(
        d for d in ("retrieval_failure/no_match", "retrieval_failure/provenance_only", "ranking_failure/below_cutoff",
                    "ranking_failure/outranked", "budget_failure")) + " |", "|---|---|---|---|---|---|"]
    for name in names:
        d = r[name]["summary"]["local"]["outcome_details"]
        lines.append(f"| `{name}` | " + " | ".join(str(d.get(k, 0)) for k in (
            "retrieval_failure/no_match", "retrieval_failure/provenance_only", "ranking_failure/below_cutoff",
            "ranking_failure/outranked", "budget_failure")) + " |")
    lines += ["", "## Candidates and budget (local)", "",
              "Scanned: rows scored per query (every record and claim). Matched: mean records and claims with a non-zero score. "
              "Returned: mean candidates the compiler received (before policy). Included: mean items in the context.",
              "Tokens changed: of the queries' local context tokens, how many one unrelated write (a record matching no question) "
              "invalidates.",
              "", "| Retriever | Scanned | Matched | Returned | Included | Budget binding (queries) | Budget dropped an expected item (queries) | Tokens changed by an unrelated write |",
              "|---|---|---|---|---|---|---|---|"]
    for name in names:
        s = r[name]["summary"]
        lines.append(f"| `{name}` | {s['scanned_per_query']} | {s['matched_mean']:.1f} | {s['local']['returned_mean']:.1f} | "
                     f"{s['local']['included_mean']:.1f} | {s['local']['budget_binding_queries']} | {s['local']['budget_dropped_expected_queries']} | "
                     f"{s['tokens_changed_by_unrelated_write']}/{s['queries']} |")
    lines += ["", "## Exclusion reasons over all candidates (local / cloud)", "", "| Retriever | " + " | ".join(context.REASONS) + " |",
              "|---|" + "---|" * len(context.REASONS)]
    for name in names:
        s = r[name]["summary"]
        lines.append(f"| `{name}` | " + " | ".join(
            f"{s['local']['excluded_reasons'].get(x, 0)} / {s['cloud']['excluded_reasons'].get(x, 0)}" for x in context.REASONS) + " |")
    tags = list(r[names[0]]["by_tag"])
    lines += ["", "## Governed recall by query category (local, items recalled / eligible)", "",
              "| Category | Queries | " + " | ".join(f"`{n}`" for n in names) + " |", "|---|---|" + "---|" * len(names)]
    for tag in tags:
        lines.append(f"| {tag} | {r[names[0]]['by_tag'][tag]['queries']} | " + " | ".join(
            r[n]["by_tag"][tag]["governed_recall_items"] for n in names) + " |")
    lines += ["", "## MRR by query category (retrieval before policy)", "",
              "| Category | " + " | ".join(f"`{n}`" for n in names) + " |", "|---|" + "---|" * len(names)]
    for tag in tags:
        lines.append(f"| {tag} | " + " | ".join(f"{r[n]['by_tag'][tag]['mrr']:.3f}" for n in names) + " |")
    lines += ["", "## Per-query outcomes (local)", "",
              "One letter per expected item, in ground-truth order: R recalled, P policy-excluded as expected, "
              "N no match, L provenance link only, C below cutoff, O outranked within the budget, B budget too small, "
              "! policy violation or mismatch.", "",
              "| Query | Tags | " + " | ".join(f"`{n}`" for n in names) + " |", "|---|---|" + "---|" * len(names)]
    letter = {"recalled": "R", "policy_excluded": "P", "retrieval_failure/no_match": "N",
              "retrieval_failure/provenance_only": "L", "ranking_failure/below_cutoff": "C",
              "ranking_failure/outranked": "O", "budget_failure": "B", "policy_violation": "!", "policy_mismatch": "!"}
    for q in queries:
        cells = ["".join(letter[r[n]["queries"][q["id"]]["local"]["outcomes"][e["id"]]] for e in q["expected"])
                 for n in names]
        lines.append(f"| {q['id']} {q['question']} | {', '.join(q['tags'])} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"
