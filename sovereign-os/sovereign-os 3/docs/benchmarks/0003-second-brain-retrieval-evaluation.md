# Benchmark 0003 — Level 3 Retrieval Evaluation and Level 4 Graph Readiness

**Status:** PROPOSED specification only; no code or tests implemented by this document.
**Purpose:** establish repeatable evidence for deciding whether to add local hybrid search, a provenance graph and an Obsidian projection, without weakening canonical memory, Context Compiler or cloud disclosure.

## Context

The five-level second-brain vocabulary and target Level 3–4 are specified in [ADR-0005](../adr/0005-governed-second-brain-architecture.md) and [the levels/Obsidian guide](../second-brain/LEVELS-AND-OBSIDIAN.md). This benchmark is a **future bounded engineering task**, not authorization to replace the current lexical retrieval.

## Stage A — freeze and measure baseline

Build an entirely synthetic, versioned fixture vault with expected canonical source IDs, MemoryClaim approval histories and topic relationships. Include a corpus with at least 40 sources across several fictitious projects, plus a small set of long documents and deliberate confusing/negative examples. No personal data, API keys or real provider calls.

Evaluate at least these query categories:

| Category | Adversarial synthetic case | Expected behavior |
| --- | --- | --- |
| Exact identifier | "What was rule S-017?" with similar numbered rules | Return correct record, never a similar ID |
| Semantic paraphrase | "control layer for AI transactions" vs "agent permissions and liability" | Retrieve relevant source despite vocabulary difference |
| Complete document | Summarize the whole multi-part meeting | Discover parent; expand full authorized document, not 5 arbitrary chunks |
| Numeric maximum | Highest weekly count across all rows | Structured exact calculation; correct maximum, not top-k snippet guess |
| Temporal | Earlier decision reversed by later source | Distinguish then vs now; link valid revisions |
| Cross-project | Two fictitious projects share an assumption | Trace two grounded sources; abstain if no evidence |
| Contradiction | Two records disagree and neither is approved | Clearly expose disagreement, not invent consensus |
| Unanswerable | User asks for an unstored decision | Return no evidence or appropriately abstain |
| Authority | Proposed/contested/rejected or unsupported claims | Never enter approved-memory role |
| Forget/sensitivity | Forgotten, sensitive or stale graph/vector hit | Do not return forgotten text or transmit sensitive content |
| Outbound validity | Candidate/truncation/index state changes after preview | No unreviewed changes in actual provider payload |
| Obsidian | Synthetic note links + deletion/rebuild | Valid backlinks, no stale files, no canonical writes |

**Baseline metrics:** recall@5/10 of *eligible canonical source IDs*, exact-ID correctness, full-document coverage, temporal accuracy, irrelevant-context fraction, grounded edge-path precision, abstention accuracy, latency and indexing/query cost. Record per-query failures, code revision, policy version and corpus fingerprint. Benchmark scoring is **not** a claim that models themselves are deterministic.

## Stage B — compare retrieval candidates

Compare unchanged lexical baseline to a local FTS5 candidate approach, then optional local embeddings/hybrid reranking if measured paraphrase recall warrants it. Keep candidate IDs distinct from hydrated authoritative data. Report both improvements and regressions, including false positive privacy/cost implications and source-ID resolution.

Do not choose a vector database by reputation or LLM recommendation. No embeddings shall be sent to third-party indexing services without a separately approved disclosure design.

## Stage C — provenance/Obsidian graph validation

With synthetic records and claims, materialize read-only edges from existing claim-source and supersession links. Export a synthetic Obsidian-compatible vault and verify:

- every `[[wikilink]]` resolves to a stable generated note, with readable source context;
- Graph view renders expected connections (manual visual smoke test); labels are explicitly in Markdown, not implied UI capabilities;
- graph status reflects canonical authority on every view;
- corrections and Forget remove dependent note bodies and links under a documented manifest/rebuild;
- stale graph hits cannot bypass exact disclosure preview, authorization or source hydration;
- no SQL schema alteration or write-back to canonical memory.

## Hard safety gates

**Fail immediately** for unauthorized approval/promotion, model-selected vault access, leaked sensitive or forgotten-derived content, preserved deleted graph exports, cloud transmission that differs from approved messages, invalid raw-ID leakage, or tests requiring real personal data.

Tests should include replay/restore, failure during projection update, concurrent source correction, graph snapshot drift and local UI metadata exposure. Review tiers follow AGENTS.md. Security gate remains not passed.

## Scope and delivery

First PR: fixtures + benchmark runner + baseline report only. No production retrieval changes, extra provider calls, migration or persistent graph data. Subsequent separate PRs can implement a demonstrably better local candidate index and a read-only provenance graph. Each phase states migration/reversal, actual test results, latency/cost budget and unresolved risks.

Accept a feature only when it improves a category of real user questions measurably while passing *all* existing memory, Forget and disclosure tests. Graph node count, embedding count and aesthetically dense visualizations are not success criteria.
