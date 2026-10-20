# Benchmark 0003 — Retrieval evaluation (Context Compiler V0)

**Purpose:** measure how well the merged Context Compiler retrieval finds what a question needs, what it costs in irrelevant context and disclosure surface, and what cheap, deterministic, local alternatives would change. The aim is not a more sophisticated retriever. The aim is trustworthy, auditable evidence for any future retrieval change.

**Scope:** evaluation only. This is the second-brain workstream's **SB-1**, the synthetic evaluation slice. It changes no production code: memory authority, retrieval, the Context Compiler, disclosure and storage are exactly as merged. Every ADR-0003 and ADR-0004 invariant holds.

## Status and founder direction (2026-10-20)

**Production retrieval stays exactly as merged.** The founder has decided:

1. **Production retriever.** Keep the merged Context Compiler V0 lexical retriever unchanged. **No experimental retriever in this benchmark is approved for production.**
2. **Porter normalisation** is a measured candidate, not an approved implementation.
3. **Deferred:** IDF, BM25, FTS5 and embeddings. No derived index is adopted.
4. **ADR-0004 founder decision 3 is preserved.** Records or claims reached only through provenance or graph links do not become relevant model context. The provenance experiments below are counterfactual.
5. **Budget:** 12 items and 12,000 characters, unchanged.
6. **Disclosure:** no new cloud-disclosure eligibility or permission.
7. **Fingerprint.** The context fingerprint is not weakened for ranking convenience.
   - It binds the complete policy-relevant retrieval state, including matching candidates below the cutoff.
   - A future *policy-equivalent* fingerprint would need its own ADR-0004 amendment, formal proof obligations, adversarial tests and founder approval. Nothing here implements or assumes one.
8. **Security Gate: NOT PASSED.** Synthetic data only. No real or sensitive personal data enters these experiments.

**Relationship to PR #3** ([solnoctua/Sovereign-OS-Founding-Repository#3](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/pull/3), proposed, not merged):

- PR #3 proposes ADR-0005 (governed second brain).
- It retired its own draft retrieval benchmark in favour of `docs/second-brain/SECOND-BRAIN-VALIDATION.md`, which specifies the future graph, Obsidian, temporal and relational acceptance tests.
- **This document is the only executed Benchmark 0003.** It does not re-specify those tests.
- ADR-0005's decisions D1–D15 and intended retrieval positions R1–R7 belong to PR #3 and are not ratified here.

## Starting point and run record

- **Base:** `main` at `4fbecbefd0c0bd0f3b159111fb48902b21cf4171`, the merge of Context Compiler V0 with policy `sovereign.context.v0`.
- **Builder:** Claude Code in a cloud session. No human interventions during the run, and no paid API cost (no provider is ever called).
- **Environment:** SQLite 3.45.1, with identical results under Python 3.12 and 3.13.
- **Ground truth:** unchanged since it was written, before the first experiment ran, including through this revision.
- **Results artifact:** every result number in this document comes from the committed `evaluation/retrieval/results.json`. The test suite and `python -m evaluation.retrieval --check` verify that file against the code.
- **No timing claims.** This benchmark measures no latency or wall-clock time.

## Task

Build a small, deterministic synthetic corpus and a harness that evaluate Context Compiler retrieval:

- measure it before policy filtering, and as the governed context the model would actually receive;
- separate the reasons something is missing (the failure taxonomy below);
- compare the merged lexical retrieval with cheap, deterministic, local alternatives;
- report every relevance gain together with its precision, privacy and token-stability cost.

Run it with `python -m evaluation.retrieval` from the project directory, which writes `results.json` and `report.md`. `--check` verifies that the committed artifacts are current.

| File | Content |
|---|---|
| `evaluation/retrieval/corpus.json` | Synthetic vault: 99 hand-written records, 3 generated families (155 records) and 16 claims. |
| `evaluation/retrieval/queries.json` | 56 queries with explicit ground truth. |
| `evaluation/retrieval/aliases.json` | The fixed alias map used by one experiment. |
| `evaluation/retrieval/retrievers.py` | The experimental relevance functions (evaluation only; the app never imports them). |
| `evaluation/retrieval/harness.py` | Corpus loading, ground-truth validation, metrics, taxonomy, navigation, token stability and report. |
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

**Judged by meaning, not by word overlap,** fixed before any experiment ran, and never edited after seeing results.

Each query lists:

- every **expected** item, with its intended governed outcome:
  - `evidence` or `approved_memory` for items that should reach the context;
  - otherwise the exclusion reason the compiler should give (`superseded`, `contested`, `stale`, `sensitive_cloud`, …), separately for the local and the cloud target;
- **acceptable** items, which may appear without counting as noise.

In total there are 99 expected items:

- **88 eligible locally**, of which 79 are eligible for cloud;
- **11 intentionally excluded**, each with its reason.

**Validation.** Before measuring, the harness checks every expected outcome against the production policy, treating the item as relevant (`context._reasons`). An expectation that disagrees with policy stops the run, and a test proves that typos are caught.

### What an experiment may change

A retriever here only supplies `score(text) -> (score, matched_terms)`, the seam `Vault.context_candidates` already takes. Everything else is the merged production code:

- **Candidate selection:** one read snapshot, top 50 per kind, provenance-linked claims.
- **Policy** (`build_bundle`): authority, sensitivity inheritance, disclosure, duplicates, budget, token.

The baseline is evaluated through `compile_context` itself, and a test proves that the experiment path with the production scorer is token-identical to `compile_context`. So a retriever can change what surfaces and in what order, never what may be used or disclosed. Every compile happens for the `local` and for a cloud target, but no provider is called.

The experiments' indexes are in-memory SQLite databases. They are built from a read-only snapshot and discarded after the run; nothing is written to the vault or persisted.

### Metrics

**Retrieval, before policy (candidate recall).** All matching records and claims are ranked by the retriever's score, with ties broken newest first and then by id (the production tie-break).

- **Recall@1/5/10/50:** the mean share of a query's expected items in the top K. Every expected item counts, including ineligible ones: surfacing an ineligible item is what lets the receipt explain its exclusion.
- **MRR**, overall and per category: mean reciprocal rank of the first expected item. *Temporal MRR* is MRR over the 5 temporal queries.

**Governed context, after policy.**

- **Governed recall** for local and cloud: per query, the share of eligible expected items included in their expected role; reported as the mean over queries and as item counts (`recalled / eligible`).
- **Noise:** included items that are neither expected nor acceptable. In a cloud plan these are private items that would be disclosed if the plan were approved.
- **Precision:** the share of included items that are not noise.
- **Cloud items:** the total number of items across all 56 cloud plans. This is the private disclosure surface an approval would cover.
- **Budget displacement:** expected eligible items excluded by the budget, either outranked or with a budget too small.

**Policy outcomes.** Exclusion reasons over all candidates, policy violations and policy mismatches.

**Load:** rows scanned per compile, matches, and candidates returned before policy. These are deterministic counts, not timings.

**Token stability.**

- *Unrelated write:* how many of the 56 local context tokens one unrelated write invalidates (a record matching no question).
- *Unchanged vault:* how many stay identical on a repeat compile *and* on an independently rebuilt, identical vault with freshly built retrievers. ADR-0005 §6.4 (PR #3) requires 100% here.

**Local navigation (discovery, not admission).** Items one stored link away (claim ↔ cited record, record ↔ its correction):

- from the **context** (included items);
- from the **preview** (included and excluded candidates, which the receipt lists).

Navigation never changes relevance, context or token. It counts how many expected items the context missed that a local view could still surface, and how many irrelevant items it would show.

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

These are cheap and deterministic only: no model, no network, no embeddings or vector store. **None is a proposal.** Each is measured to inform future, separately reviewed work.

| Retriever | What changes |
|---|---|
| `baseline` | Merged V0, unchanged: distinct question terms matched (`\w+`, English stopwords, one plural `s` trimmed). |
| `porter_count` | The same score over Porter-stemmed tokens (the SQLite FTS5 `porter` tokenizer): broad normalisation. |
| `porter_idf` | Porter tokens, each match weighted by IDF: normalisation + term weighting. |
| `fts5_bm25` | SQLite FTS5 (`unicode61`, no stemming) with `bm25()`. |
| `fts5_porter_bm25` | SQLite FTS5 with Porter stemming and `bm25()`. |
| `fts5_porter_bm25_aliases` | The previous retriever plus a fixed alias map of 28 generic groups. This is an optimistic **upper bound**, because the queries' author also wrote the map. |
| `fts5_porter_bm25_provenance` | The previous BM25 retriever plus one hop of relevance along stored links. Counterfactual. |
| `exact_stem` | **Experiment A:** exact matches first, stem matches second, and stem-only texts are admitted. |
| `exact_stem_tiebreak` | **Experiment A, without admission:** stems only order texts that already match exactly. |
| `baseline_provenance` | **Experiment B, context admission (counterfactual):** the merged baseline plus one hop of relevance along stored links. |
| `exact_stem_provenance` | **Experiment C:** A combined with B. |

**Experiment A — exact-primary / stem-secondary, defined precisely:**

- **Exact match.** A distinct question term (the production `terms_of`) that is among the text's production terms. The exact count is therefore exactly the baseline score; a test checks this for every query and document.
- **Stem match.** A question term with no exact match whose Porter stem (of any question word producing that term) is among the text's Porter stems.
- **Each term counts once.** A term that matches exactly is never counted again as a stem match, so a text matching a term in both tiers counts it as exact.
- **Score and ordering.** The pair (exact, stem) in lexicographic order, encoded as `exact + stem / (terms + 1)`.
  - One more exact match always outranks any number of stem matches.
  - Stem matches only break ties between equal exact counts.
  - In `exact_stem`, stem matches also admit texts with no exact match, ranked below every exact match.
  - In `exact_stem_tiebreak`, a text with no exact match scores 0, so the set of relevant texts is exactly the baseline's (also tested).
- **Recency and tie-breaking.** Unchanged: equal scores sort newest first, then by id.
- **Cutoff.** Unchanged: the top 50 per kind by that order. Stem-only texts therefore enter only after every exact-matching text.
- **Token binding.**
  - The score depends on the question and the text alone, never on other documents, so an unrelated write cannot change it.
  - Scores still enter the fingerprint unchanged; nothing is relaxed.
  - Adopting either variant would change relevance or ranking, so it would need a new `policy_version`.

**Experiment B — one-hop existing provenance links.** The links are only those storage already holds canonically: claim → cited record (`claim_sources`), record → citing claim, and a record's correction ↔ the record it corrects (`records.supersedes_id`). There is no graph database, no new schema and no inference. Two modes:

- **Navigation and discovery** (measured for every retriever, see *Metrics*): local exploration of stored links from what the preview shows. It adds no relevance, and context and token are unchanged.
- **Context admission** (`baseline_provenance`): **counterfactual, not authorised.**
  - A document with no direct match inherits half the best direct score among its one-hop neighbours, and so becomes relevant within the unchanged Context Compiler policy.
  - Inherited items still pass every authority, sensitivity, budget and disclosure rule.
  - It would reverse ADR-0004 founder decision 3, which the founder has preserved.

## Results

All tables are in [`evaluation/retrieval/report.md`](../../evaluation/retrieval/report.md), including per-query outcome letters for every retriever.

### Baseline (merged V0)

**Retrieval and governed context**

| R@1 | R@5 | R@10 | R@50 | MRR | Governed recall, local | Governed recall, cloud | Precision, local / cloud | Cloud items |
|---|---|---|---|---|---|---|---|---|
| 44.0% | 68.8% | 71.2% | 72.6% | 0.691 | 70.9% (66/88) | 70.4% (59/79) | 33.6% / 31.8% | 239 |

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

**Load and token stability**

| Measure | Value |
|---|---|
| Rows scanned per compile | 270 |
| Mean matches | 9.7 |
| Mean candidates returned | 9.2 |
| Mean items included | 4.5 |
| Queries where the budget was binding | 8 |
| Budget-displaced expected items | 3 |
| Tokens changed by an unrelated write | 0/56 |
| Tokens identical on an unchanged vault | 56/56 |

Every expected exclusion is retrieved and explained, with one exception: the rejected claim behind a paraphrased question (q04) was never retrieved.

**The 22 eligible items the baseline misses** (local), grouped by the cheapest mechanism that could recover them:

| Mechanism needed | Items | Queries |
|---|---|---|
| Morphology: stemming | 2 | q06 *decide/decided*: old evidence tied with 60 newer reviews and **fell below the cutoff**. q07 *plant/planted*: no exact match at all. |
| Term weighting / length normalisation | 2 | q08 owner record **below the cutoff** behind 55 stand-ups (its approved claim was still recalled). q47 outranked by 40 run logs. |
| Fixed vocabulary (aliases) | 3 | q11 CI, q18 GP, q32 sofa/couch. |
| A link storage already holds (citation, correction) | 6 | q22, q38, q44, q56: evidence of a matching claim, or a correction of a matching record. q39, q46: approved claim surfaced only by provenance. |
| Meaning: paraphrase with no shared words | 7 | q04, q20, q21, q27, q30, q42 (one item), q43. |
| A larger budget, or temporal filtering | 2 | q53: 14 films this year, 12-item budget. |

### Gains versus costs, every retriever

Items recalled are out of 88 eligible locally and 79 for cloud. *Noise* and *precision* are local / cloud. *Displaced* is local budget displacement. *Unrelated* and *Unchanged* are local tokens out of 56.

**Recall and ranking**

| Retriever | Local | Cloud | R@1 | R@10 | MRR | Temporal MRR |
|---|---|---|---|---|---|---|
| `baseline` | 66 | 59 | 44.0% | 71.2% | 0.691 | 0.733 |
| `porter_count` | 68 | 61 | 43.1% | 73.9% | 0.686 | 0.733 |
| `porter_idf` | 69 | 62 | 44.9% | 74.8% | 0.693 | 0.717 |
| `fts5_bm25` | 57 | 50 | 40.6% | 71.0% | 0.664 | 0.340 |
| `fts5_porter_bm25` | 69 | 62 | 43.1% | 75.5% | 0.705 | 0.473 |
| `fts5_porter_bm25_aliases` | 72 | 64 | 54.7% | 80.9% | 0.797 | 0.473 |
| `fts5_porter_bm25_provenance` | 74 | 67 | 43.1% | 80.2% | 0.705 | 0.473 |
| `exact_stem` | 68 | 61 | 45.8% | 74.8% | 0.712 | 0.733 |
| `exact_stem_tiebreak` | 67 | 60 | 45.8% | 73.0% | 0.709 | 0.733 |
| `baseline_provenance` | 72 | 64 | 44.0% | 76.7% | 0.691 | 0.733 |
| `exact_stem_provenance` | 74 | 66 | 45.8% | 80.3% | 0.712 | 0.733 |

**Costs and stability**

| Retriever | Noise | Precision | Cloud items | Displaced | Unrelated | Unchanged |
|---|---|---|---|---|---|---|
| `baseline` | 166 / 163 | 33.6% / 31.8% | 239 | 3 | 0 | 56 |
| `porter_count` | 213 / 210 | 28.8% / 27.1% | 288 | 3 | 0 | 56 |
| `porter_idf` | 212 / 209 | 29.1% / 27.4% | 288 | 2 | 53 | 56 |
| `fts5_bm25` | 151 / 150 | 33.2% / 30.9% | 217 | 0 | 51 | 56 |
| `fts5_porter_bm25` | 212 / 209 | 29.1% / 27.4% | 288 | 3 | 53 | 56 |
| `fts5_porter_bm25_aliases` | 225 / 220 | 28.6% / 26.9% | 301 | 3 | 54 | 56 |
| `fts5_porter_bm25_provenance` | 223 / 220 | 29.2% / 27.6% | 304 | 4 | 53 | 56 |
| `exact_stem` | 213 / 210 | 28.8% / 27.1% | 288 | 3 | 0 | 56 |
| `exact_stem_tiebreak` | 165 / 162 | 34.0% / 32.2% | 239 | 3 | 0 | 56 |
| `baseline_provenance` | 173 / 170 | 34.2% / 32.3% | 251 | 3 | 0 | 56 |
| `exact_stem_provenance` | 223 / 221 | 29.2% / 27.3% | 304 | 3 | 0 | 56 |

No retriever produces a policy violation or mismatch, and no sensitive item enters a cloud plan under any of them (checked for every cloud bundle of every retriever).

**What a production version would need**

| Retriever | Derived state | Vault-wide statistics | Other dependencies |
|---|---|---|---|
| `baseline` | none (merged) | no | — |
| `porter_count`, `exact_stem`, `exact_stem_tiebreak` | none | no | A Porter stemmer: the FTS5 tokenizer, a vendored stemmer or a new dependency |
| `porter_idf` | none | yes, document frequencies per compile | A Porter stemmer |
| `fts5_bm25`, `fts5_porter_bm25` | a persistent FTS5 index, with Forget (`secure-delete`) and rebuild semantics | yes | — |
| `fts5_porter_bm25_aliases` | the FTS5 index | yes | A maintained vocabulary file |
| provenance variants | none: they read `claim_sources` and `supersedes_id` in the same snapshot | as their inner scorer | Reverses ADR-0004 decision 3 |

### Experiment A — exact-primary / stem-secondary

- **`exact_stem` recovers exactly what broad Porter recovers, and costs exactly as much noise.**
  - It recovers q06 and q07 locally and in cloud, with no regression.
  - It admits the same 213 / 210 noise items in total as `porter_count`; 8 local items differ, all in q22, q27 and q40.
  - It improves ranking over both broad Porter and the baseline: R@1 45.8% (Porter 43.1%, baseline 44.0%) and MRR 0.712 (0.686, 0.691). It keeps the baseline's temporal MRR (0.733).
  - **The hypothesis that tiering avoids Porter's noise is not supported.** The noise comes from *admission* (any stem-only match becomes relevant and fills unused budget), not from ordering.
- **`exact_stem_tiebreak` separates the two effects.** With stems only ordering exact matches:
  - it recovers q06 (old evidence that fell below the cutoff) and not q07 (which has no exact match), so 67/88 locally and 60/79 for cloud;
  - noise is 165 / 162 (baseline 166 / 163), precision 34.0% / 32.2% (baseline 33.6% / 31.8%), and cloud items 239 (baseline 239);
  - token stability is unchanged (0 and 56).
  - Recovering a morphology failure with **no exact match at all** necessarily widens the relevance gate, and that is where the noise comes from. Recovering one that is merely ranked too low does not.

### Experiment B — one-hop existing provenance links

**Navigation and discovery.** No relevance, context or token change; all counts are local.

| Start set (baseline) | Missed items discoverable | Neighbours shown | Of which irrelevant |
|---|---|---|---|
| From the context (included items) | 6 of 22: q08, q22, q39, q46, q47, q56 | 29 | 16 |
| From the whole preview (included and excluded candidates) | 10 of 22 (listed as excluded, or one hop away): the 6 above + q38, q44 and both q53 films | 13 beyond what the preview already lists | 8 |

Without changing a single compiler decision, a local view of stored links and of the existing receipt already surfaces 10 of the baseline's 22 misses.

**Context admission (`baseline_provenance`, counterfactual):**

- **Recovered:** 72/88 locally (+6: q22, q38, q39, q44, q46, q56) and 64/79 for cloud (+5). In cloud, q22's sensitive record becomes correctly `sensitive_cloud`-excluded instead of unretrieved.
- **Lost:** none.
- **Noise:** 173 / 170 (+7 / +7). Precision rises slightly, to 34.2% / 32.3%.
- **Cloud plans:** 251 items, up from 239. That is 12 more private items offered for approval: 5 expected, 7 irrelevant.
- **Policy handling:** inherited items pass every rule unchanged (0 violations, 0 mismatches), and ranking and temporal MRR are unchanged.
- **Tokens:** 0 changed by an unrelated write, and 56/56 identical on an unchanged vault.
- **Admission and navigation recover different items.** Admission gets q38 and q44, whose links start from excluded candidates. Navigation from the context gets q08 and q47, whose records are linked to included claims but lose ranking or budget under admission.

### Experiment C — combination (`exact_stem_provenance`)

- **Recovered:** 74/88 locally and 66/79 for cloud.
- **Its gains are exactly the union of A and B:** q06 and q07 from `exact_stem`, plus the 6 provenance items. No item appears in both, and none regresses.
- **Its cost is almost exactly the sum of both:** noise 223 / 221 (A alone 213 / 210, B alone 173 / 170), precision 29.2% / 27.3%, and 304 cloud items.
- **Token stability holds:** 0 changed by an unrelated write, and 56/56 identical on an unchanged vault.
- **Comparison with the BM25-based provenance diagnostic:** it matches its 74/88 locally (66 vs 67 in cloud) without its token churn (53/56) or its lost recency prior (temporal MRR 0.473), and with the same local noise (223).

### Findings

1. **Lexical upgrades are real but small.** Stemming and weighting recover 1–4 of the 22 misses. Broad stemming recovers 2, at +47 local noise items (213 against 166) and +49 cloud items (288 against 239).
2. **The cheapest noise-free gain is ordering, not admission.** Stem-as-tie-break recovers the one *invisible* failure (q06, old evidence below the cutoff) with no extra noise, cloud items or token churn. Every recovery that needs a wider relevance gate (q07, the provenance items) adds disclosure surface.
3. **Plain FTS5 regresses.** Its default tokenizer loses the baseline's plural trimming (57/88).
4. **BM25 removes an implicit temporal prior.** The baseline's ties sort newest first, which suits "latest" and "this year" questions. BM25 breaks those ties: temporal MRR falls from 0.733 to 0.473.
5. **Vault-wide statistics break token stability under unrelated writes.** IDF and BM25 scores depend on the whole vault, and scores are bound into the fingerprint, so one unrelated write invalidates 51–54 of 56 previews.
   - This is fail-closed (409, then re-preview), but almost any write would stale a pending approval.
   - Every text-local scorer (baseline, Porter, the exact-stem variants and the provenance variants over them) invalidates none.
   - All eleven retrievers keep 56/56 tokens on an unchanged vault.
   - Per the founder, the fingerprint is not relaxed to accommodate weighted scores.
6. **Paraphrase is untouched by everything lexical.** None of the 7 items that need meaning is recovered by any retriever. The corpus over-represents paraphrase by design, so its real frequency is unknown.
7. **Stored links are the largest deterministic lever, and most of it is available without admission.**
   - Admission recovers 6 items for 7 noise items.
   - Navigation, a local view of links from what the preview already shows, makes 10 misses discoverable without changing relevance, context or disclosure. This is the SB-2 direction.
8. **Governed context is precision-poor under every retriever (27–34%).** Whenever 12 or more eligible items share any question word, the budget fills with lexical noise, and in a cloud plan that noise is private data offered for disclosure. Any future recall gain must be judged against this.
9. **Scale is not measured.** Every compile scores every record and claim: rows scanned equals vault size (270 here), a deterministic count. This benchmark measures no latency and draws no conclusion about when an index would become necessary.

## Candidates for future evaluation — none authorised for production

Each candidate below would need its own Tier 2 PR, a `policy_version` bump, regenerated results here, independent review and founder approval.

- **Exact-stem tie-break** (`exact_stem_tiebreak`): the lowest-risk ranking candidate measured.
  - It recovers the one below-cutoff old-evidence miss without widening relevance.
  - It adds no noise, no cloud items, no derived state and no token churn.
  - It still changes ranking, so it is a policy change.
- **Navigation of stored links** (ADR-0005's SB-2, proposed in PR #3): measured here as discovery only.
  - It needs no compiler change at all.
  - It belongs with the provenance-graph slice, not in context admission.
- **Stem admission** (`porter_count`, `exact_stem`) and **provenance admission**: measured, not recommended.
  - Each recovers items only by widening the relevance gate.
  - Provenance admission also reverses ADR-0004 decision 3 (ADR-0005's SB-8, deferred).
- **Deferred by founder decision:** IDF, BM25, FTS5, aliases and embeddings.

## Dependencies and sequencing

- **Workstream order** (ADR-0005 §11, proposed in PR #3):
  1. SB-1: this benchmark.
  2. SB-2: the computed, read-only provenance graph and a safe one-way Obsidian projection.
  3. SB-3: human-declared projects, concepts and membership.
  4. SB-4: further lexical or FTS evaluation, if justified.
  5. SB-5: local semantic retrieval, if evidence justifies it.
  6. SB-6 and SB-7: temporal semantics and structured typed MemoryClaims.
  7. SB-8: possible graph-assisted model context, after evaluation and a new ADR-0004 policy decision.

  Level 5 stays deferred.
- **Storage-integrity dependency.** PR #3's review found a pre-existing storage-contract defect on `main`.
  - Raw SQLite `INSERT OR REPLACE`, `REPLACE` and `UPDATE OR REPLACE` naming an existing rowid can bypass the tombstone and immutability triggers on connections with `recursive_triggers` off, which is SQLite's default.
  - That threatens permanent Forget identity and immutable history.
  - It needs a separate, independently audited Tier 2 storage fix and **blocks production SB-2**.
  - It does not affect this benchmark's results: the harness writes only through `Vault.restore_trusted`, which issues plain `INSERT`s, and no evaluation code issues `REPLACE`.
- **Integration order:**
  1. PR #3 completes its independent audit.
  2. The founder approves its decisions.
  3. PR #3 merges.
  4. This PR integrates the updated `main`, reconciles overlapping documentation (ROADMAP and status references) and regenerates its results.
  5. This PR reruns all tests and CI.
  6. This PR receives a fresh independent audit.
  7. The founder decides on merge.

## Remaining founder decisions

These are not settled by the 2026-10-20 direction:

1. Whether any candidate above, most plausibly the exact-stem tie-break, should ever be prepared as a production proposal. Several sub-questions would follow:
   - the stemmer implementation (FTS5 tokenizer, vendored stemmer or new dependency);
   - its availability where SQLite lacks FTS5;
   - its `policy_version`.
2. A relevance floor, threshold or cloud-specific policy to address precision (27–34%). Each needs its own evaluation and a versioned policy approval.
3. Evaluation follow-ups:
   - **No-evidence queries.** Every query has at least one expected item, so what is offered for disclosure when nothing is relevant is not measured. Adding them changes the fixture, so it belongs in a follow-up.
   - **A private, founder-run local evaluation on real notes**, never committed and only after the Security Gate. It needs the harness to read a corpus from a path.
4. Evaluation infrastructure:
   - `evaluation/` as a non-shipped package;
   - pytest `pythonpath = ["."]`;
   - a test that requires the committed results to match the code, so any change to retrieval or policy regenerates them in the same PR.

## Tests

`tests/test_retrieval_evaluation.py` runs in the normal suite:

- **Artifacts:** the committed `results.json` and `report.md` are exactly what the code produces, and two runs are identical.
- **Ground truth:**
  - it agrees with production policy, and injected typos are caught;
  - the corpus restores completely and carries no contact details.
- **Production path:** with the production scorer, the experiment path is token-identical to `compile_context` for every query and target.
- **Policy invariants:** no retriever can put an ineligible, non-authoritative or sensitive item into a plan. Every cloud bundle of every retriever is checked.
- **Token stability:**
  - every retriever is deterministic on an unchanged vault;
  - text-local scorers are stable under an unrelated write;
  - weighted ones are not.
- **Exact-stem scorer:**
  - the exact tier equals the baseline score for every query and document;
  - the tie-break variant's relevant set equals the baseline's;
  - exact matches outrank stem matches, with no double counting.
- **Harness logic:** every branch of the outcome taxonomy, the ranking tie-break and the alias rewriting are tested.

The module is skipped where SQLite lacks FTS5.

## NOT MEASURED

- **Answer quality:** generated-answer correctness, abstention, and the temporal interpretation of answers ("then" vs "now", correction vs change). No model is called.
- **Questions with no relevant evidence.**
- **Narrower settings:** pinned questions, other languages, and real usage frequencies.
- **Latency and scale behaviour.**

## Threats to validity

- **Self-authored:** one author wrote the corpus, the queries, the ground truth and the alias map. Hard categories are deliberately over-represented, so counts show which mechanism fixes which failure, not how often each failure occurs.
- **Small:** with 88 eligible items, one item is about 1.1 points. Differences of one or two items are not significant.
- **Inheritance rule:** the provenance experiments use one rule (half the best neighbour's score). It decides ranking among admitted items, not which items are admitted.
- **Platform:** `bm25()` and the exact-stem scores are rounded to 6 decimals. Noise depends on the `acceptable` lists.

## Out of scope

The following are excluded:

- production retrieval, Context Compiler, disclosure or storage changes;
- agents and external actions;
- autonomous memory promotion;
- embeddings or vector databases;
- graph databases or new schema;
- background jobs;
- cloud infrastructure;
- mobile or Pocket work;
- real personal data.

## Evaluation procedure

1. Run `pytest -q`, `pytest -q tests/adversarial`, `python -m evaluation.retrieval --check`, `git diff --check` and `python -m compileall -q src tests evaluation`.
2. Review the corpus and ground truth for bias toward any retriever, then check the claimed gains and costs against `report.md` and `results.json`.
3. Confirm that no experiment code is imported by `src/`, and that the baseline is `compile_context` unchanged.
4. The founder decides. This PR changes no production behaviour.
