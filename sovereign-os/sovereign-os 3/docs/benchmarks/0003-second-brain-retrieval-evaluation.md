# Benchmark 0003 — Level 3 Retrieval Evaluation and Level 4 Graph Readiness

**Status:** PROPOSED specification only; no code or tests are implemented by this document.
**Purpose:** repeatable evidence for deciding whether to add in-vault FTS, local embeddings, a provenance graph and an Obsidian projection — without weakening canonical memory, the Context Compiler or exact cloud disclosure.

## Context

The five-level vocabulary, the L3–L4 target and the delivery slices are in [ADR-0005](../adr/0005-governed-second-brain-architecture.md) and [the levels guide](../second-brain/LEVELS-AND-OBSIDIAN.md). Stage A is slice **SB-1**; Stage B serves SB-4/SB-5; Stage C serves SB-2. This benchmark does not authorize replacing the current lexical retrieval.

## Fixture corpus

An entirely synthetic, versioned fixture built **only through the current canonical model** — records, MemoryClaims and their decision histories — loaded through the public `Vault` API so every storage trigger applies. No personal data, API keys or real provider calls.

- At least 40 records across several fictitious projects, including: long records near the 10,000-character limit; record corrections (capture errors); a reversed decision expressed as a later record plus claim supersession (a *change*); approved, proposed, contested, rejected, superseded and stale claims; sensitive records; deliberate near-duplicates and confusable identifiers; and, if the founder writes in more than one language, records and questions in each.
- **Ground truth is benchmark metadata, not canonical data:** expected record and claim IDs per query, project labels, relationship labels and temporal labels live in the fixture's answer file. Projects and relationships do not exist in the schema yet; the benchmark must not create them in the vault.

## Query categories

| Category | Synthetic case | Expected behavior |
| --- | --- | --- |
| Exact identifier | "What was rule S-017?" beside S-071 and S-17 | The exact record; never a similar ID |
| Paraphrase | "control layer for AI transactions" vs "agent permissions and liability" | Retrieve despite vocabulary difference (records the lexical gap SB-5 would need to close) |
| Cross-lingual (if applicable) | Question in one language, record in another | As paraphrase |
| Whole record | "Summarize the whole design memo" | The entire record within budget; never a fragment |
| Multi-record document | "Summarize the whole meeting" (spread over records) | Baseline: report the missing grouping; after SB-3: the full group |
| Knowledge update (change) | A decision reversed by a later record | Distinguish then vs now; the earlier one is superseded, not false |
| Correction | A capture corrected by a revision | Only the corrected revision is evidence; dependent claims are `stale` |
| Cross-project | Two fictitious projects share an assumption | Both grounded records; abstain without evidence |
| Contradiction | Two records disagree and no claim is approved | Both shown as evidence; no invented consensus |
| Unanswerable | A decision never recorded | No evidence; the answer abstains |
| Numeric aggregate | "Highest weekly count" | No structured sources exist: expected abstention |
| Authority | Proposed, contested, rejected, stale or orphaned claims | Never in the `approved_memory` role |
| Forget / sensitivity | Forgotten, sensitive or stale index hit | No forgotten text anywhere; nothing sensitive in a cloud plan |
| Outbound validity | Candidate, truncation or index state changes after preview | 409; the provider payload never differs from the approved preview |
| Budget pressure | More eligible items than the 12-item / 12,000-character budget | Report which expected items the budget dropped |
| Obsidian projection | Synthetic export, then correction, Forget and rebuild | See Stage C |

## Metrics

Measured at two levels, because a retriever can find an item that the compiler's policy or budget then drops:

- **Candidate level:** recall@5/10/50 of *policy-eligible* expected IDs (eligible for the target boundary: local or cloud), mean reciprocal rank, exact-ID precision.
- **Bundle level:** bundle recall (expected eligible IDs that reach `included[]`), irrelevant-context fraction, items dropped by budget, abstention accuracy, temporal accuracy (correction and change scored separately).
- **Graph:** grounded edge-path precision; for projections, link resolution and the structure metrics in OBSIDIAN-PROJECTION §8.
- **Operational:** latency p50/p95, index build time and size, per-query cost (zero expected), **token stability** (identical tokens over repeated compiles of an unchanged vault).
- **Zero-tolerance counters:** authority violations, forget residue (canary strings found in any derived store, registered projection, manifest or registry), sensitive egress, preview/payload differences.

Record per-query failures, code revision, `policy_version`, retriever identity and corpus fingerprint. Scoring is about retrieval and policy; it is not a claim that models are deterministic.

## Stage A — freeze and measure the baseline (SB-1)

Fixtures, runner and a baseline report for the **current** compiler (`sovereign.context.v0`). The report proposes acceptance thresholds per category for founder approval; it does not set them unilaterally. No production behavior changes.

## Stage B — compare retrieval candidates (SB-4, SB-5)

Compare the unchanged baseline with in-vault FTS5 candidates, then — only if Stage A shows paraphrase or cross-lingual misses that matter — local embeddings with rank fusion. Each candidate is evaluated as a full compiler policy version (ADR-0005 §6): relevance gate, ranking, truncation fingerprint and determinism, reported locally and for the cloud boundary separately. Report regressions as prominently as gains, including how many additional private items become cloud-eligible per query.

No vector database is chosen by reputation or model recommendation. No record, question or vector is sent to a third-party embedding or indexing service.

## Stage C — provenance graph and Obsidian projection (SB-2)

With synthetic records and claims, compute the provenance graph on read and export a projection; verify the acceptance tests in [OBSIDIAN-PROJECTION §12](../second-brain/OBSIDIAN-PROJECTION.md#12-acceptance-tests-sb-2), in particular:

- every `[[wikilink]]` resolves, and graph lines correspond to canonical relationships;
- statuses in each note equal the compiler's view **at that export's generation**, and every note carries the snapshot banner (a static export cannot be "live");
- correction and Forget regenerate or remove exactly the affected notes, with no canary residue and no dangling link;
- an interrupted export recovers, and non-owned files are untouched;
- the provenance graph and export write nothing to canonical tables;
- manual: Graph view, Local graph and Backlinks behave as the demo's Start Here describes.

## Hard safety gates

**Fail immediately** for unauthorized approval or promotion, model-selected vault access, forgotten-derived content in any store or projection, a cloud transmission that differs from the approved messages, durable IDs in `outbound`, or any test requiring real personal data.

Tests include restore followed by index rebuild, failure during projection update, concurrent correction during export, index drift between preview and execution, and local UI metadata exposure. Review tiers follow `AGENTS.md`. The security gate remains NOT PASSED.

## Scope and delivery

First PR (SB-1): fixtures, runner and baseline report only — no production retrieval change, provider call, migration or persistent graph data. Each later slice states its migration and reversal, actual test results, latency and cost budget, and unresolved risks.

Accept a feature only when it measurably improves a category of real questions while passing *all* existing memory, Forget and disclosure tests. Node counts, embedding counts and dense visualizations are not success criteria.
