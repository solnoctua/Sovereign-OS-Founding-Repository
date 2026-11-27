"""Evaluation-only pilot: Khoj's default bi-encoder and cross-encoder through Sovereign's Benchmark 0003 harness.

Not part of Sovereign, its tests or Benchmark 0003's committed results; nothing here is a dependency. It answers one
question before any ADR work: does dense retrieval, as Khoj configures it, recover the paraphrase misses of the merged
lexical retriever, and at what disclosure (noise) and token-stability cost?

Method. Khoj (khoj-ai/khoj@ae229ca, AGPL-3.0; read, not copied) embeds with `thenlper/gte-small` (mean pooling,
normalized), keeps hits with cosine distance <= 0.18 (similarity >= 0.82) by exact scan, and optionally reranks with
`mixedbread-ai/mxbai-rerank-xsmall-v1` (sigmoid). This pilot reimplements that behaviour independently with ONNX
Runtime and plugs it into Benchmark 0003 as relevance functions: `compile_with` then runs the real Context Compiler
(authority, sensitivity, budget, token), unchanged. Every text is embedded alone (batch size 1, one thread), so a
vector depends only on (model, text). Scores are rounded to 6 decimals, as the harness does.

Requirements (scratch environment only, never Sovereign's): onnxruntime, tokenizers, numpy; model files pinned by
revision and sha256 below, laid out as <models>/gte-small/{tokenizer.json,onnx/model.onnx} and
<models>/mxbai-rerank-xsmall/{tokenizer.json,onnx/model.onnx}. The first-use inputs are
`evaluation/first_use/{seed,queries}.json` from draft PR #12 (branch eval/wp4-first-use-trial at 4a37f84).

Usage, from the project folder:
    python docs/research/pilots/2026-11-27-dense-retrieval-pilot.py "$PWD" <models> <seed.json> <queries.json>
It writes the .results.json beside itself; two runs on 2026-11-27 (Linux x86-64, Python 3.13, onnxruntime 1.32.0,
one thread) produced byte-identical files. Cross-platform determinism (for example macOS arm64) is not yet tested.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

PROJECT, MODELS, FU_SEED, FU_QUERIES = (Path(p) for p in sys.argv[1:5])
sys.path.insert(0, str(PROJECT))

from evaluation.retrieval import harness  # noqa: E402
from evaluation.retrieval.retrievers import Baseline, Retriever, documents, neighbours  # noqa: E402
from sovereign.context import POLICY, build_bundle, scorer as production_scorer  # noqa: E402
from sovereign.store import Vault  # noqa: E402

PINNED = {  # file -> sha256 (Hugging Face revisions: gte-small 17e1f347, mxbai-rerank-xsmall-v1 b5c6e9da)
    "gte-small/onnx/model.onnx": "0b01312b59bec0a2558a626f2937be4cbe4bb16d1511560153f598cec488f1f8",
    "mxbai-rerank-xsmall/onnx/model.onnx": "536b7183f8964dd212c4e2f4029fcc595cfc03ac233aba03d293546aaa5a875b",
}
KHOJ_DEFAULT = 0.82   # Khoj: bi_encoder_confidence_threshold (max cosine distance) 0.18


def verify_models() -> None:
    for rel, want in PINNED.items():
        got = hashlib.sha256((MODELS / rel).read_bytes()).hexdigest()
        assert got == want, f"{rel}: sha256 {got} != pinned {want}"


def session(path: Path) -> ort.InferenceSession:
    options = ort.SessionOptions()
    options.intra_op_num_threads = options.inter_op_num_threads = 1
    return ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])


class BiEncoder:
    def __init__(self, directory: Path):
        self.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self.tokenizer.enable_truncation(512)
        self.session = session(directory / "onnx" / "model.onnx")
        self.cache: dict[str, np.ndarray] = {}

    def __call__(self, text: str) -> np.ndarray:
        if text not in self.cache:
            enc = self.tokenizer.encode(text)
            ids = np.array([enc.ids], dtype=np.int64)
            mask = np.array([enc.attention_mask], dtype=np.int64)
            hidden = self.session.run(None, {"input_ids": ids, "attention_mask": mask,
                                             "token_type_ids": np.zeros_like(ids)})[0][0]
            vector = (hidden * mask[0][:, None]).sum(0) / mask[0].sum()
            self.cache[text] = vector / np.linalg.norm(vector)
        return self.cache[text]

    def cosine(self, a: str, b: str) -> float:
        return round(float(np.dot(self(a), self(b))), 6)


class CrossEncoder:
    def __init__(self, directory: Path):
        self.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self.tokenizer.enable_truncation(512)
        self.session = session(directory / "onnx" / "model.onnx")
        self.cache: dict[tuple[str, str], float] = {}

    def __call__(self, query: str, text: str) -> float:
        key = (query, text)
        if key not in self.cache:
            enc = self.tokenizer.encode(query, text)
            logit = self.session.run(None, {"input_ids": np.array([enc.ids], dtype=np.int64),
                                            "attention_mask": np.array([enc.attention_mask], dtype=np.int64)})[0][0][0]
            self.cache[key] = round(float(1 / (1 + np.exp(-logit))), 6)
        return self.cache[key]


class Dense(Retriever):
    """Khoj-style relevance: exact cosine scan, admitted at similarity >= tau."""
    def __init__(self, encoder: BiEncoder, tau: float):
        self.encoder, self.tau = encoder, tau
        self.name, self.description = f"dense_gte_small@{tau}", f"gte-small cosine >= {tau} (exact scan)"

    def scorer(self, question):
        def score(text):
            cos = self.encoder.cosine(question, text)
            return (cos, ()) if cos >= self.tau else (0, ())
        return score


class Hybrid(Retriever):
    """Lexical OR dense admission. Lexical hits keep their tier (distinct terms matched) and come first; cosine
    orders texts within a tier; dense-only hits rank below every lexical hit."""
    def __init__(self, encoder: BiEncoder, tau: float):
        self.encoder, self.tau = encoder, tau
        self.name, self.description = f"hybrid_baseline_or_dense@{tau}", f"baseline terms, or gte-small cosine >= {tau}"

    def scorer(self, question):
        lexical = production_scorer(question)

        def score(text):
            matched, terms = lexical(text)
            cos = self.encoder.cosine(question, text)
            within = round((cos + 1) / 2 * 0.999, 6)          # in [0, 1): orders inside a tier
            if matched:
                return (matched + within, terms)
            return (within, ()) if cos >= self.tau else (0, ())
        return score


class HybridAdmission(Retriever):
    """Dense similarity as an admission signal only: lexical hits keep the production score (distinct terms), so
    the compiler's newest-first tie-break is untouched; dense-only hits share one score below every lexical hit
    and are therefore ordered newest first as well."""
    def __init__(self, encoder: BiEncoder, tau: float):
        self.encoder, self.tau = encoder, tau
        self.name, self.description = f"hybrid_admission_only@{tau}", f"baseline ranking; gte-small cosine >= {tau} only admits"

    def scorer(self, question):
        lexical = production_scorer(question)

        def score(text):
            matched, terms = lexical(text)
            if matched:
                return (matched, terms)
            return (0.5, ()) if self.encoder.cosine(question, text) >= self.tau else (0, ())
        return score


def diagnose(encoder: BiEncoder, vault: Vault, queries: list[tuple], label: str) -> dict:
    """Cosine of each expected record to its question, and its rank among all active records (1 = most similar)."""
    texts = {r["id"]: r["content"] for r in vault.export()["records"]}
    out = {}
    for qid, question, expected, _ in queries:
        sims = sorted(((encoder.cosine(question, t), rid) for rid, t in texts.items()), reverse=True)
        rank = {rid: n + 1 for n, (_, rid) in enumerate(sims)}
        out[qid] = {e: {"cosine": encoder.cosine(question, texts[e]), "rank": rank[e], "of": len(texts)} for e in expected}
        print(f"  [{label}] {qid}: " + ", ".join(f"{e} cos {v['cosine']:.3f} rank {v['rank']}/{v['of']}"
                                                for e, v in out[qid].items()), flush=True)
    return out


class Rerank(Retriever):
    """Khoj-style rerank: the inner retriever's admission is unchanged; its top_n are reordered by the
    cross-encoder (sigmoid), ahead of the rest of its ranking."""
    def __init__(self, inner: Retriever, cross: CrossEncoder, texts: list[str], top_n: int = 20):
        self.inner, self.cross, self.texts, self.top_n = inner, cross, texts, top_n
        self.name, self.description = f"{inner.name}+rerank{top_n}", f"{inner.name}, top {top_n} reranked by mxbai-rerank-xsmall"

    def scorer(self, question):
        inner = self.inner.scorer(question)
        scored = sorted(((inner(t)[0], t) for t in self.texts if inner(t)[0]), key=lambda p: (-p[0], p[1]))
        boosted = {t: 1000 + self.cross(question, t) for _, t in scored[: self.top_n]}

        def score(text):
            value, terms = inner(text)
            if not value:
                return (0, ())
            return (boosted.get(text, value), terms)
        return score


def benchmark(retrievers: list[Retriever]) -> dict:
    """Benchmark 0003 through its own harness functions, plus token stability measured without the harness's
    fixed ladder: a repeat compile with fresh scorers, and the unrelated control write."""
    corpus, queries, _ = harness.load()
    out = {}
    with tempfile.TemporaryDirectory() as directory:
        vault = harness.build_vault(str(Path(directory) / "a"), corpus)
        docs = documents(vault.export())
        links = neighbours(docs)
        control = harness.build_vault(str(Path(directory) / "b"),
                                      {**corpus, "records": corpus["records"] + [harness.CONTROL_RECORD]})
        for r in retrievers:
            per_query = {q["id"]: harness.evaluate_query(vault, docs, r, q, links) for q in queries["queries"]}
            summary = harness.summarise(per_query, queries["queries"], docs)
            tags = harness.by_tag(per_query, queries["queries"])
            before = harness.local_tokens(vault, r, queries["queries"])
            again = harness.local_tokens(vault, r, queries["queries"])
            after = harness.local_tokens(control, r, queries["queries"])
            nonsense = sum(1 for q in queries["queries"] if r.scorer(q["question"])(harness.CONTROL_RECORD["text"])[0])
            out[r.name] = {
                "recall_at_10": summary["recall_at"]["10"], "mrr": summary["mrr"],
                "local": {k: summary["local"][k] for k in ("governed_recall_items", "noise_total", "context_precision",
                                                           "included_total")},
                "cloud": {k: summary["cloud"][k] for k in ("governed_recall_items", "noise_total", "context_precision",
                                                           "included_total")},
                "tags": {t: {"recall_at_10": tags[t]["recall_at_10"], "local": tags[t]["governed_recall_items"]}
                         for t in ("paraphrase", "synonym", "abbreviation", "morphology", "names", "temporal",
                                   "distractors", "exact")},
                "tokens_identical_on_repeat": sum(before[k] == again[k] for k in before),
                "tokens_changed_by_unrelated_write": sum(before[k] != after[k] for k in before),
                "queries_admitting_nonsense_control_record": nonsense,
            }
            print(f"  {r.name:42} R@10 {out[r.name]['recall_at_10']:.3f}  local {out[r.name]['local']['governed_recall_items']:>6} "
                  f"noise {out[r.name]['local']['noise_total']:>4}  cloud {out[r.name]['cloud']['governed_recall_items']:>6} "
                  f"noise {out[r.name]['cloud']['noise_total']:>4}  paraphrase {out[r.name]['tags']['paraphrase']['local']}", flush=True)
    return out


# A builder-authored synthetic probe for the founder's two target scenarios. It is NOT founder data and NOT part of
# Benchmark 0003: its oracle needs independent review before it can become a benchmark extension (see the plan).
PROBE_RECORDS = [
    ("pk-1", "Pocket: a small, mostly screenless device for presence-first capture: voice notes, private audio and haptic cues."),
    ("pk-2", "Pocket hardware stays deferred until the software flow is useful on the phone and the Mac."),
    ("pk-3", "Sovereign OS idea: one personal intelligence layer that every device talks to, local-first, with permissioned cloud reasoning."),
    ("pk-4", "Spoken interaction must work without a screen; a reply slower than about 300 ms breaks the feel of a conversation."),
    ("pk-5", "Keep the control plane on my own machine and rent reasoning from cloud models only per approved request."),
    ("iv-1", "Investment approach (August): durable competitive advantage first, then management quality and capital allocation. A great company is not a great investment at any price."),
    ("iv-2", "Valuation rule: compare the price with normalised earnings and with what the market already expects; demand a margin of safety."),
    ("iv-3", "Before buying, write down the downside scenario and the catalyst; size positions by conviction, never more than 15% in one name."),
    ("iv-4", "Lesson from the September mistake: I ignored balance-sheet risk because the growth story was exciting."),
    ("iv-5", "Revised framework (October): hold for five years or more, and reject businesses whose moat depends on a single regulator."),
    ("dx-1", "Bought new running shoes; the old pair lasted about 800 km."),
    ("dx-2", "Garden: the tomatoes need staking before the end of June."),
    ("dx-3", "Harbor's sync job runs every five minutes."),
    ("dx-4", "Lantern battery lasts about 14 days in the field test."),
    ("dx-5", "Dinner with Sam: we talked about his startup's hiring plan and his first sales."),
    ("dx-6", "Coffee stock is running low; reorder beans on Friday."),
    ("dx-7", "The desktop monitor arm is loose; tighten the screws."),
    ("dx-8", "Company offsite agenda: product roadmap, hiring and budget."),
]
PROBE_QUERIES = [
    ("pocket-1", "I've been thinking about creating a voice-activated desktop computer.", ["pk-1", "pk-3", "pk-4"], ["pk-2", "pk-5"]),
    ("pocket-2", "What earlier ideas relate to a computer you talk to instead of typing on?", ["pk-1", "pk-4"], ["pk-3", "pk-2"]),
    ("invest-1", "Research this company and help me decide whether it's an attractive investment.", ["iv-1", "iv-2", "iv-3"], ["iv-4", "iv-5"]),
    ("invest-2", "How should I judge whether a stock is worth buying at today's price?", ["iv-2", "iv-1"], ["iv-3", "iv-5"]),
    ("invest-3", "What mistakes have I made before when evaluating businesses?", ["iv-4"], ["iv-1", "iv-5"]),
    ("invest-4", "What is my current rule on how long I hold positions?", ["iv-5"], ["iv-3"]),
]


def small_set(name: str, vault: Vault, queries: list[tuple], retrievers: list[Retriever]) -> dict:
    """Recall of expected records into the compiled local context (the Context Compiler decides), plus noise."""
    out = {}
    for r in retrievers:
        recalled = total = noise = 0
        rows = {}
        for qid, question, expected, acceptable in queries:
            score = r.scorer(question)
            facts = vault.context_candidates(score, [], POLICY.retrieval_limit)
            bundle = build_bundle(question, "local", [], facts, POLICY)
            got = [i.candidate.id for i in bundle.included]
            hit = [e for e in expected if e in got]
            extra = [g for g in got if g not in expected and g not in acceptable]
            recalled, total, noise = recalled + len(hit), total + len(expected), noise + len(extra)
            rows[qid] = {"recalled": hit, "missed": [e for e in expected if e not in got], "noise": extra}
        out[r.name] = {"recalled": f"{recalled}/{total}", "noise": noise, "queries": rows}
        print(f"  [{name}] {r.name:42} recalled {recalled}/{total}  noise {noise}", flush=True)
    return out


def main() -> None:
    verify_models()
    encoder = BiEncoder(MODELS / "gte-small")
    cross = CrossEncoder(MODELS / "mxbai-rerank-xsmall")
    corpus, _, _ = harness.load()
    with tempfile.TemporaryDirectory() as directory:
        texts = [d.text for d in documents(harness.build_vault(str(Path(directory) / "t"), corpus).export())]
    ladder = lambda texts: [Baseline(), Dense(encoder, KHOJ_DEFAULT), Dense(encoder, 0.85), Dense(encoder, 0.88),  # noqa: E731
                            Hybrid(encoder, KHOJ_DEFAULT), Hybrid(encoder, 0.85), Hybrid(encoder, 0.88),
                            HybridAdmission(encoder, KHOJ_DEFAULT), HybridAdmission(encoder, 0.85),
                            Rerank(Dense(encoder, KHOJ_DEFAULT), cross, texts), Rerank(Hybrid(encoder, 0.85), cross, texts)]
    results = {"benchmark_0003": None, "first_use": None, "probe": None}
    print("Benchmark 0003 (254 records, 16 claims, 56 queries; 88 locally eligible expected items):")
    results["benchmark_0003"] = benchmark(ladder(texts))

    with tempfile.TemporaryDirectory() as directory:
        vault = Vault(str(Path(directory) / "fu.db"))
        vault.import_untrusted(json.loads(FU_SEED.read_text("utf-8")))
        fu = [(q["id"], q["question"], q["expected"], []) for q in json.loads(FU_QUERIES.read_text("utf-8"))["queries"]]
        fu_texts = [r["content"] for r in vault.export()["records"]]
        print("First-use trial (PR #12 seed; t1-t5 own vocabulary, p1-p3 paraphrases):")
        results["first_use"] = {
            "own_vocabulary": small_set("first-use own", vault, [q for q in fu if q[0].startswith("t")], ladder(fu_texts)),
            "paraphrase": small_set("first-use paraphrase", vault, [q for q in fu if q[0].startswith("p")], ladder(fu_texts)),
            "paraphrase_diagnosis": diagnose(encoder, vault, [q for q in fu if q[0].startswith("p")], "first-use"),
        }

    with tempfile.TemporaryDirectory() as directory:
        vault = Vault(str(Path(directory) / "probe.db"))
        ids = {}
        for rid, text in PROBE_RECORDS:
            ids[rid] = vault.add(text)["id"]
        back = {v: k for k, v in ids.items()}
        queries = [(qid, q, [ids[e] for e in exp], [ids[a] for a in acc]) for qid, q, exp, acc in PROBE_QUERIES]
        print("Builder-authored probe (Pocket cross-project and investment-framework scenarios; not founder data):")
        probe = small_set("probe", vault, queries, ladder([t for _, t in PROBE_RECORDS]))
        diagnosis = diagnose(encoder, vault, queries, "probe")
        results["probe_diagnosis"] = {qid: {back[e]: v for e, v in row.items()} for qid, row in diagnosis.items()}
        for row in probe.values():
            for q in row["queries"].values():
                for key in ("recalled", "missed", "noise"):
                    q[key] = [back.get(i, i) for i in q[key]]
        results["probe"] = probe
    print(json.dumps(results, indent=1, sort_keys=True), file=open(Path(__file__).with_suffix(".results.json"), "w"))


if __name__ == "__main__":
    main()
