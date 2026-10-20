# Benchmark 0003 — Retrieval evaluation (Context Compiler V0)

**Purpose:** measure how well the merged Context Compiler retrieval finds what a question needs, and say with evidence which upgrade, if any, the next retrieval change should be. The aim is not a more sophisticated retriever. The aim is to earn the right to one with evidence.

**Scope:** evaluation only. No production code changes, and every ADR-0003 / ADR-0004 invariant still holds. The decisions this benchmark informs (a retrieval change, a policy change) are Tier 2 and belong in separate reviewed PRs.

## Starting point

- `main` at `4fbecbefd0c0bd0f3b159111fb48902b21cf4171`: the merge of Context Compiler V0, with policy `sovereign.context.v0`.
- **Builder:** Claude Code in a cloud session.
- **Run:**
  - no human interventions during the run;
  - no paid API cost (no provider is ever called);
  - the full evaluation takes about 4 s.

## Task

Build a small, deterministic synthetic corpus and a harness that evaluate Context Compiler retrieval:

- measure it before policy filtering, and as the governed context the model would actually receive;
- separate the reasons something is missing (the failure taxonomy below);
- compare the merged lexical retrieval with cheap, deterministic, local alternatives.

Run it with `python -m evaluation.retrieval` from the project directory, which writes `results.json` and `report.md`. `--check` verifies that the committed artifacts are current.

| File | Content |
|---|---|
| `evaluation/retrieval/corpus.json` | Synthetic vault: 99 hand-written records, 3 generated families (155 records) and 16 claims. |
| `evaluation/retrieval/queries.json` | 56 queries with explicit ground truth. |
| `evaluation/retrieval/aliases.json` | The fixed alias map used by one experiment. |
| `evaluation/retrieval/retrievers.py` | The experimental relevance functions (evaluation only; the app never imports them). |
| `evaluation/retrieval/harness.py` | Corpus loading, ground-truth validation, metrics, taxonomy and report. |
| `evaluation/retrieval/results.json` | Machine-readable results, per retriever and per query. |
| `evaluation/retrieval/report.md` | Generated tables, including per-query outcomes. |
| `tests/test_retrieval_evaluation.py` | Harness tests (see *Tests*). |

## Method

### Corpus

The vault holds 254 records (5 sensitive) and 16 claims. Every person, pet, project, amount and date is invented. The vault is built through the ordinary **trusted restore** path (`Vault.restore_trusted`), so storage triggers, lifecycle replay, evidence hashes and support derivation are the production ones:

- **Corrections:** records with `corrects` supersede their predecessor.
- **Claim histories:** each claim's `path` (for example proposed → approved → superseded) is replayed and validated.
- **Orphaned claim:** one claim's evidence link has no hash, so its support derives as `orphaned`.

Three generated families supply realistic, newer distractors that share vocabulary with old, correct evidence:

| Family | Items | Dates | Shared vocabulary |
|---|---|---|---|
| Weekly reviews | 60 | 2025–2026 | garden, budget |
| Stand-ups | 55 | 2025–2026 | checklist, owner, deploy |
| Run logs | 40 | 2025–2026 | morning, pace, km |

**Coverage.** A query can carry several tags.

| Category | Queries | Category | Queries |
|---|---|---|---|
| exact match | 7 | approved claims vs raw evidence | 8 |
| plural / morphology | 7 | proposed / contested / rejected / stale / orphaned / superseded claims | 7 |
| paraphrase, no shared words | 7 | sensitive evidence (local vs cloud) | 6 |
| synonym | 5 | corrections / superseded records | 3 |
| abbreviation / acronym | 5 | provenance-linked claims | 4 |
| names / entities | 11 | multi-evidence answers | 3 |
| temporal wording (as of 2026-10-19) | 5 | old correct evidence among many newer distractors | 6 |
| multiple related notes | 4 | needs more than the 12-item budget | 1 |
| distractors with overlapping vocabulary | 7 | | |

### Ground truth

**Judged by meaning, not by word overlap,** and fixed before any experiment ran. It was not edited after seeing results.

Each query lists:

- every **expected** item, with its intended governed outcome:
  - `evidence` or `approved_memory` for items that should reach the context;
  - otherwise the exclusion reason the compiler should give (`superseded`, `contested`, `stale`, `sensitive_cloud`, …), separately for the local and the cloud target;
- **acceptable** items, which may appear without counting as noise.

In total there are 99 expected items:

- **88 eligible locally**, of which 79 are eligible for cloud;
- **11 intentionally excluded**, each with its reason.

**Validation.** Before measuring, the harness checks every expected outcome against the production policy, treating the item as relevant (`context._reasons`). An expectation that disagrees with policy is a ground-truth error and stops the run, and a test proves that typos are caught.

### What an experiment may change

A retriever here only supplies `score(text) -> (score, matched_terms)`, the seam `Vault.context_candidates` already takes. Everything else is the merged production code:

- **Candidate selection:** one read snapshot, top 50 per kind, provenance-linked claims.
- **Policy** (`build_bundle`): authority, sensitivity inheritance, disclosure, duplicates, budget, token.

The baseline is evaluated through `compile_context` itself, and a test proves that the experiment path with the production scorer is token-identical to `compile_context`. So a retriever can change what surfaces and in what order, never what may be used or disclosed. Every compile happens for the `local` and for a cloud target, but no provider is called.

The experiments' indexes are in-memory SQLite databases. They are built from a read-only snapshot and discarded after the run; nothing is written to the vault or persisted.

### Metrics

**Retrieval, before policy.** All matching records and claims are ranked by the retriever's score, with ties broken newest first and then by id (the production tie-break). This is the retriever's own relevance order, independent of the compiler's role ordering.

- **Recall@1/5/10/50:** the mean share of a query's expected items in the top K, so a 3-item query contributes 1/3 per item. Every expected item counts, including ineligible ones: retrieval cannot know eligibility, and surfacing an ineligible item is what lets the receipt explain its exclusion.
- **MRR:** mean reciprocal rank of the first expected item.

**Governed context, after policy.**

- **Governed recall:**
  - per query, the share of eligible expected items included in their expected role;
  - reported as the mean over queries, and as item counts (`recalled / eligible`), for local and cloud.
- **Noise:** included items that are neither expected nor acceptable. In a cloud plan these are private items that would be disclosed if the plan were approved.
- **Precision:** the share of included items that are not noise.
- **Counts:**
  - rows scanned per compile, matches, candidates returned before policy and items included;
  - exclusion reasons over all candidates;
  - queries where the budget was binding, and where it dropped an expected item.
- **Token stability:** how many of the 56 local context tokens one unrelated write invalidates. The unrelated write is a record matching no question.

### Failure taxonomy

Every expected item gets exactly one outcome per target:

| Outcome | Meaning |
|---|---|
| **Successful governed recall** (`recalled`) | Eligible, and in the context in its expected role. |
| **Authority/policy exclusion** (`policy_excluded`) | Ineligible, retrieved, and excluded for the expected reason. Correct behaviour, **not a retrieval failure**. |
| **Retrieval failure** | `no_match`: the item never matched the question. `provenance_only`: it surfaced only as a claim citing a retrieved record, which policy treats as `not_relevant` (ADR-0004 founder decision 3). |
| **Ranking failure** | `below_cutoff`: it matched, but ranked below the 50-per-kind retrieval cutoff, so it is invisible even in the receipt. `outranked`: the budget filled with items the question did not require, ranked above it. |
| **Context-budget failure** | Excluded by the budget although every included item was itself expected: the budget is too small for this question. |
| `policy_violation` / `policy_mismatch` | An ineligible item included, or an unexpected exclusion reason. Both must be 0, and are 0 for every retriever. |

### Experiments

These are cheap and deterministic only: no model, no network, no embeddings or vector store.

| Retriever | What changes |
|---|---|
| `baseline` | Merged V0, unchanged: distinct question terms matched (`\w+`, English stopwords, one plural `s` trimmed). |
| `porter_count` | The same score over Porter-stemmed tokens (the SQLite FTS5 `porter` tokenizer): **normalisation only**. |
| `porter_idf` | Porter tokens, each match weighted by IDF: **normalisation + term weighting**. |
| `fts5_bm25` | SQLite FTS5 (`unicode61`, no stemming) with `bm25()`: weighting and length normalisation only. |
| `fts5_porter_bm25` | SQLite FTS5 with Porter stemming and `bm25()`. |
| `fts5_porter_bm25_aliases` | The previous retriever plus the fixed alias map (28 generic groups such as couch/sofa, GP/general practitioner and CI/continuous integration). This is an optimistic **upper bound**, because the queries' author also wrote the map. |
| `fts5_porter_bm25_provenance` | **Diagnostic, not a proposal.** It adds one hop of relevance along links storage already holds (citation and correction), at half the neighbour's score. It would change ADR-0004 founder decision 3. |

## Results

All tables, the per-category breakdown and per-query outcomes are in [`evaluation/retrieval/report.md`](../../evaluation/retrieval/report.md). Every number below comes from `results.json`.

### Baseline (merged V0)

**Retrieval quality**

| R@1 | R@5 | R@10 | R@50 | MRR | Governed recall, local | Governed recall, cloud | Precision, local / cloud |
|---|---|---|---|---|---|---|---|
| 44.0% | 68.8% | 71.2% | 72.6% | 0.691 | 70.9% (66/88) | 70.4% (59/79) | 33.6% / 31.8% |

**Outcomes of expected items (local)**

| Outcome | Count |
|---|---|
| Recalled | 66 |
| Policy-excluded as expected | 10 |
| Retrieval failures: no match | 16 |
| Retrieval failures: provenance only | 2 |
| Ranking failures: below cutoff | 2 |
| Ranking failures: outranked | 1 |
| Budget failures | 2 |
| Policy violations | 0 |

**Load, budget and token stability (local)**

| Measure | Value |
|---|---|
| Rows scanned per compile | 270 |
| Mean matches | 9.7 |
| Mean candidates returned | 9.2 |
| Mean items included | 4.5 |
| Queries where the budget was binding | 8 |
| Queries where the budget dropped an expected item | 2 |
| Tokens changed by an unrelated write | 0/56 |

Policy behaves exactly as ADR-0004 specifies, and every expected exclusion is retrieved and explained, with one exception: the rejected claim behind a paraphrased question was never retrieved (q04).

The 22 eligible items the baseline misses (local), grouped by the cheapest mechanism that could recover them:

| Mechanism needed | Items | Queries |
|---|---|---|
| Morphology: stemming | 2 | q06 *decide/decided*: old evidence tied with 60 newer reviews and **fell below the cutoff**. q07 *plant/planted*. |
| Term weighting / length normalisation | 2 | q08 owner record **below the cutoff** behind 55 stand-ups (its approved claim was still recalled). q47 outranked by 40 run logs. |
| Fixed vocabulary (aliases) | 3 | q11 CI, q18 GP, q32 sofa/couch. |
| A link storage already holds (citation, correction) | 6 | q22, q38, q44, q56 (evidence of a matching claim, or a correction of a matching record); q39, q46 (approved claim surfaced only by provenance). |
| Meaning: paraphrase with no shared words | 7 | q04, q20, q21, q27, q30, q42 (one item), q43. |
| A larger budget, or temporal filtering | 2 | q53: 14 films this year, 12-item budget. |

### What each upgrade fixes

Items are local governed recall out of 88 eligible items.

**Recall**

| Retriever | Items | Fixed vs baseline | Broken vs baseline | R@10 | MRR | Temporal MRR |
|---|---|---|---|---|---|---|
| `baseline` | 66 | — | — | 71.2% | 0.691 | 0.733 |
| `porter_count` | 68 | q06, q07 | none | 73.9% | 0.686 | 0.733 |
| `porter_idf` | 69 | q06, q07, q47 | none | 74.8% | 0.693 | 0.717 |
| `fts5_bm25` (no stemming) | 57 | q08, q47 | 11 of q53 (*films*/*film*, *watch*/*watched*) | 71.0% | 0.664 | 0.340 |
| `fts5_porter_bm25` | 69 | q06, q07, q08, q47 | 1 of q53 (2025 films outrank 2026 ones) | 75.5% | 0.705 | 0.473 |
| `+ aliases` (upper bound) | 72 | the previous four + q11, q18, q32 | the same q53 item | 80.9% | 0.797 | 0.473 |
| `+ provenance` (diagnostic) | 74 | the previous four + q38, q39, q44, q46, q56 | the same q53 item | 80.2% | 0.705 | 0.473 |

**Costs**

| Retriever | Noise, local / cloud | Tokens changed by an unrelated write |
|---|---|---|
| `baseline` | 166 / 163 | 0/56 |
| `porter_count` | 213 / 210 | 0/56 |
| `porter_idf` | 212 / 209 | 53/56 |
| `fts5_bm25` (no stemming) | 151 / 150 | 51/56 |
| `fts5_porter_bm25` | 212 / 209 | 53/56 |
| `+ aliases` (upper bound) | 225 / 220 | 54/56 |
| `+ provenance` (diagnostic) | 223 / 220 | 53/56 |

Cloud results follow the same pattern, out of 79 eligible items: 59 → 61 → 62 → 50 → 62 → 64 → 67. No retriever produces a policy violation, and no sensitive item enters a cloud plan under any of them.

**Findings**

1. **The lexical upgrades are real but small.** Stemming plus weighting recovers 3 or 4 of the 22 misses. Normalisation alone recovers 2 with no regression, and those 2 include the only case where correct old evidence silently fell below the cutoff (q06).
2. **Plain FTS5 regresses.** Its default tokenizer loses the baseline's plural trimming (57/88). FTS5 helps only with stemming.
3. **BM25 removes an implicit temporal prior.** The baseline's ties sort newest first, which is right for "latest" and "this year" questions. BM25's length normalisation breaks those ties: temporal MRR falls from 0.733 to 0.473, and older films displace this year's in q53.
4. **Vault-wide statistics break token stability.** With IDF or BM25, the score of every match depends on the whole vault, and scores are bound into the retrieval fingerprint (ADR-0004). One unrelated write therefore invalidates 51–54 of 56 pending previews. This is still fail-closed (409, then re-preview), so nothing leaks, but almost any write makes a pending approval stale. The baseline and `porter_count` invalidate none.
5. **Paraphrase is untouched by everything lexical:** none of the 7 items that need meaning is recovered by any retriever. It is the largest single failure class here (7 of 22), but only because the corpus contains 7 paraphrase queries by design. This benchmark cannot say how common it is in real use.
6. **Links already in storage are the largest deterministic lever.** One hop along citation and correction links recovers 5 more items, with no new index and no model. Adopting it would reverse ADR-0004 founder decision 3 for claims.
7. **Governed context is precision-poor under every retriever (about 27–34%).** Whenever 12 or more eligible items share any question word, the budget fills with lexical noise, and in a cloud plan that noise is private data offered for disclosure. Stemming makes this slightly worse (precision 33.6% → 28.8%). The fix is a policy question (a relevance floor, or a smaller cloud budget), not a choice of retrieval engine.
8. **Scale is not yet a reason for an index.** The baseline compile is linear in vault size, measured on the development container and indicative only:

   | Records | Median compile time |
   |---|---|
   | 254 | 3 ms |
   | 2,254 | 23 ms |
   | 10,254 | 93 ms |
   | 50,254 | 480 ms |

## Recommendation: **B, narrowly — stronger lexical normalisation, not FTS5 yet**

Adopt Porter normalisation of the existing distinct-term score (`porter_count`) in a separate, reviewed Tier 2 PR. That PR should bump `POLICY_VERSION`, carry its own tests and regenerate this benchmark. Do not adopt IDF, BM25, FTS5 or the alias map now.

Why:

- **It is the only upgrade with no regression and no new risk.**
  - It gains +2 items locally and +2 in cloud.
  - It removes the invisible below-cutoff miss of old evidence (q06).
  - It keeps every property V0 tokens and receipts rely on:
    - 0/56 tokens disturbed by unrelated writes;
    - recency tie-breaks unchanged (temporal MRR 0.733);
    - no derived index, so no new Forget, restore or rebuild semantics.
  - Its cost is honest: +47 noise items locally and +47 in cloud (precision 33.6% → 28.8%), visible in every preview.
- **Weighting does not pay for itself yet.**
  - IDF adds one item (q47); BM25 adds the same one and q08.
  - Both make 95% of pending previews stale on any write.
  - BM25 also loses the recency prior and, as FTS5, needs a persistent derived index. That index would need explicit deletion (Forget must purge it, including FTS5 segments) and rebuild semantics.
  - At V0 sizes (under 100 ms at 10,000 records) there is no scale reason to pay that cost.
  - Revisit when weighting can be bound without over-invalidation, or when the vault size makes the O(n) scan matter.

Not A: normalisation fixes measured failures at no measured cost to binding, ordering or authority.

Not C:

- Paraphrase failures exist (7 of 22 here) but their frequency is unmeasured.
- Embeddings would add non-determinism and a derived index that must itself be governed and forgotten (ADR-0004).
- C needs evidence from real usage first.

Not D now, but the evidence points there next:

- Link-reachable failures (6 of 22) are the largest class that deterministic code can fix.
- They need no graph store, only the provenance and correction links already stored.
- Adopting them is a founder decision on ADR-0004 decision 3, not a retrieval-engine change.
- Temporal needs appear in two places: q53, and BM25's loss of recency ordering. That argues for keeping recency explicit in any future ranking, not for a temporal engine yet.

## Decisions for the founder

1. **Authorise the narrow B change** as its own Tier 2 PR (Porter normalisation, policy version bump), and choose its stemmer implementation:
   - SQLite FTS5's `porter` tokenizer in a transient in-memory table, as here: no new dependency, but it requires an SQLite built with FTS5;
   - a small vendored pure-Python Porter stemmer;
   - a new dependency.
2. **Token binding under weighted scores.** If IDF or BM25 is ever wanted, either accept that any write stales pending previews, or bind an order-preserving projection (membership, order, matched terms) instead of raw scores. The latter is an ADR-0004 amendment and must not weaken retrieval-state binding.
3. **Provenance-link relevance** (founder decision 3): it is the largest measured deterministic gain (+5 items). Should a claim citing relevant evidence, the evidence of a relevant claim, and the correction of a relevant record count as relevant?
4. **Context precision and disclosure.** About two thirds of included items are lexical noise in crowded vocabularies, and they would be disclosed in an approved cloud plan. Consider a relevance floor or a smaller cloud budget (a policy version change).
5. **Budget constants** (founder decision 5): one list question needs 14 items against a budget of 12. No change is recommended on one query; keep it measured.
6. **Before C:** run this harness on a private, founder-authored local query set over real notes. It would never be committed and would follow the Security Gate. A small follow-up would let the harness read a corpus from a path.
7. **Evaluation infrastructure:**
   - `evaluation/` is a non-shipped package.
   - pytest gains `pythonpath = ["."]`.
   - A test requires the committed results to match the code, so any change to retrieval or policy must regenerate them in the same PR.

## Tests

`tests/test_retrieval_evaluation.py` runs in the normal suite:

- The committed `results.json` and `report.md` are exactly what the code produces, and two runs are identical.
- Ground truth agrees with production policy, and injected typos are caught.
- The corpus restores completely and carries no contact details.
- The experiment path with the production scorer is token-identical to `compile_context` for every query and target.
- No retriever can put an ineligible, non-authoritative or sensitive item into a plan. Every cloud bundle of every retriever is checked.
- The merged retrieval keeps tokens stable under unrelated writes, while weighted retrievers do not.
- Every branch of the outcome taxonomy, the ranking tie-break and the alias rewriting are tested.

The module is skipped where SQLite lacks FTS5.

## Threats to validity

- **Self-authored:** one author wrote the corpus, the queries, the ground truth and the alias map. Hard categories are deliberately over-represented, so counts show which mechanism fixes which failure, not how often each failure occurs.
- **Small:** with 88 eligible items, one item is about 1.1 points. Differences of one or two items, such as IDF vs BM25, are not significant.
- **Narrow:** English only; unpinned questions only (pins are policy-checked elsewhere); fixed "now" (2026-10-19). Noise depends on the `acceptable` lists.
- **Platform:** `bm25()` scores are rounded to 6 decimals. Results were generated with SQLite 3.45.1 on Python 3.12 and 3.13.

## Out of scope

The following are excluded:

- production retrieval changes;
- agents and external actions;
- autonomous memory promotion;
- embeddings or vector databases;
- knowledge graphs;
- background jobs;
- cloud infrastructure;
- mobile or Pocket work;
- real personal data.

## Evaluation procedure

1. Run `pytest -q`, `pytest -q tests/adversarial`, `python -m evaluation.retrieval --check`, `git diff --check` and `python -m compileall -q src tests evaluation`.
2. Review the corpus and ground truth for bias toward any retriever, then check the claimed fixes against the per-query table in `report.md`.
3. Confirm that no experiment code is imported by `src/`, and that the baseline is `compile_context` unchanged.
4. The founder decides on the recommendation and on the decisions above. This PR changes no production behaviour.
