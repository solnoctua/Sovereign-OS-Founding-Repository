# External second-brain references: assessment, retrieval pilot and adoption gates

**Status:** research record (2026-11-27), not approval, not a dependency list, not an architecture. It applies the candidate evaluation protocol of [`BUILD-AND-INTEGRATION-PLAN.md` §4](../engineering/BUILD-AND-INTEGRATION-PLAN.md) to five repositories named in the founder's addendum of 2026-11-25, and adds them to the [research catalog](INTEGRATION-RESEARCH-CATALOG.md) as rows 43–47. Production retrieval stays the merged lexical retriever (ADR-0005 R1); embeddings stay deferred (R6) until the gates in §6 are met. Nothing here changes code, policy or data. The Security Gate remains **NOT PASSED**.

**Evidence standard.** Every repository was read at a pinned commit (source, not README). Khoj's retrieval was also reimplemented independently and run through Benchmark 0003's own harness with the same models and threshold ([pilot script](pilots/2026-11-27-dense-retrieval-pilot.py), [results](pilots/2026-11-27-dense-retrieval-pilot.results.json); two runs byte-identical). Nothing from any upstream repository was executed, and no upstream code was copied.

## 1. Findings in brief

1. **Dense retrieval as Khoj configures it is a real improvement on synthetic paraphrases, and safest as an admission signal.** On Benchmark 0003, `gte-small` at Khoj's default threshold recovers 6 of 7 paraphrase queries (baseline 0/7). Used **only to admit** items while lexical ranking and the newest-first tie-break stay (`hybrid_admission_only@0.85`), it is a strict improvement over the merged baseline: 72/88 governed local recall versus 66/88, **identical noise (166)**, temporal recall unchanged (16/18), and tokens 56/56 stable on repeat and after an unrelated write.
2. **It does not fix the founder's actual paraphrase failures.** On the first-use trial (draft PR #12; project knowledge), every variant stays at 1/6 to 2/6. The gold records rank 1st–7th by cosine but score 0.776–0.826, straddling Khoj's absolute 0.82 cut: **project jargon** ("the graph work" ⇄ "SB-2") and abstract questions defeat a small general model at a fixed threshold. Aliases, human-declared concept membership (SB-3) and representative evaluation are needed, not just a model.
3. **Frameworks fragment.** In the builder-authored investment probe, the framework spread over three records is retrieved one fragment at a time (members rank 1, 2 and 4 by cosine; two fall below the threshold). A reusable framework should be one retrievable unit: an approved MemoryClaim that cites its records (PR E), not three loose notes.
4. **The cross-encoder rerank added nothing measurable** to governed recall on any set: admission is unchanged and the 12-item budget rarely binds. It is a precision-floor candidate (R4), not a reordering need.
5. **Pure dense ranking destroys the temporal prior:** temporal recall 16/18 → 14/18 at 0.82, 3/18 at 0.85, 1/18 at 0.88. Any semantic signal must keep the compiler's lexical tiers and newest-first tie-break.
6. **The best non-retrieval ideas are verification and freshness disciplines,** not storage:
   - verbatim-quote proof before a contradiction is shown (obsidian-second-brain);
   - "timeless, dated, or a pointer" facts (obsidian-second-brain);
   - per-turn memory scope that fails closed (DeerFlow);
   - neutralising forged context markers (DeerFlow);
   - deterministic-first graphs that never merge inferred edges into explicit ones (Understand-Anything shows the failure: it does).
7. **vLLM is a Linux GPU server, not a Mac backend today:** Apple Silicon support is experimental (build from source, CPU only, no wheels), and it **collects usage statistics by default**.

## 2. Comparative assessment

Dispositions use the catalog's vocabulary.

| | Khoj | obsidian-second-brain | DeerFlow | Understand-Anything | vLLM |
| --- | --- | --- | --- | --- | --- |
| Pinned commit | `ae229ca8` | `7f4ddfda` | `aa9913c4` | `b232f356` | `b40b2a99` |
| License | **AGPL-3.0-or-later** | MIT | MIT | MIT | Apache-2.0 |
| What it is | Django + Postgres/pgvector second brain with chat | Claude Code plugin: prompt commands, Python linters, hooks over an Obsidian vault | LangGraph agent harness: sandbox, subagents, memory, knowledge providers | LLM + tree-sitter knowledge-graph builder with a graph dashboard | OpenAI-compatible inference server |
| Owns memory? | Yes (own store, model-written entries) | Writes the vault (rewrites with confirmation by default) | Yes (LLM-extracted facts) | Writes a graph JSON | No |
| Best idea for Sovereign | Exact-scan dense admission | Quote-verified contradictions; freshness rule; false-absence rule | Scope modes; forged-marker stripping; versioned summaries | Deterministic-first graph; freshness watermark | Swappable local endpoint |
| Disposition | **Pattern** (technique only; no code) | **Pattern** | **Pattern** | **Pattern** | **Isolate later** |

### 2.1 Khoj — `khoj-ai/khoj@ae229ca894c0b80ad84664afcfdde523b5e87057`

- **Paths:**
  - `src/khoj/processor/embeddings.py`: bi-encoder `thenlper/gte-small`, normalised; cross-encoder `mixedbread-ai/mxbai-rerank-xsmall-v1` with sigmoid; optional remote Hugging Face/OpenAI inference endpoints.
  - `src/khoj/search_type/text_search.py`: max cosine distance 0.18, top 10, rerank then sort.
  - `src/khoj/database/adapters/__init__.py:2150`: lexical filters, then pgvector `CosineDistance ≤ 0.18`, ordered by distance.
  - No approximate-nearest-neighbour index in any migration, so the scan is exact.
  - `src/khoj/processor/content/text_to_entries.py:61`: chunks of ≤ 256 tokens, no overlap; entries keyed by content hash for incremental updates.
- **Behaviour verified:** source read at the commit; behaviour reimplemented with ONNX Runtime and measured (§3).
- **Invariants affected:**
  - relevance is disclosure (ADR-0004 decision 1, ADR-0005 §6.1);
  - fingerprint and determinism (§6.3–6.4);
  - Forget reaches derived vectors in the same transaction (ADR-0005 §4.5, D6);
  - no cloud embedding (§6.7);
  - R1 and R6.
- **Smallest reusable component:** the technique.
  - An exact cosine scan over an in-vault vector table.
  - One text per inference call, so a vector depends only on (model, text).
  - Rounded scores.
  - Admission only, alongside lexical tiers.
  - The models are licensed independently of Khoj: `gte-small` is MIT, `mxbai-rerank-xsmall-v1` is Apache-2.0.
- **Alternatives:**
  - the fixed alias map (Benchmark 0003's best lexical result, R@10 0.809);
  - the exact-stem tie-break;
  - human-declared concept membership (SB-3);
  - framework claims;
  - other small embedding models (bge-small, e5-small), evaluated in the same harness.
- **Removal test:** delete the vector table and the retriever, and restore the previous `policy_version`. Benchmark 0003 then regenerates byte-identical baseline results and tokens (ADR-0005 §4.8).
- **Measurable benefit:** §3.
- **License:** nothing may be copied without an explicit license decision. The pilot was written from scratch from the described behaviour.

### 2.2 obsidian-second-brain — `eugeniughelbur/obsidian-second-brain@7f4ddfdafa4e4652b01209f1847c3a3fc7d07754`

- **Paths:**
  - `references/ai-first-rules.md`:
    - seven note rules (self-contained notes, a "For future agent" preamble, recency markers, verbatim sources, typed edges with inverses, confidence levels);
    - anti-fabrication rules: **false absence** ("never assert that a note does NOT exist without an exhaustive search"), search completeness, sources-are-data, and confirm-before-rewrite.
  - `references/freshness-policy.md` and `scripts/freshness_lint.py`: every fact is timeless, dated or a pointer; checks FRESH-1 to FRESH-5.
  - `commands/obsidian-reconcile.md` and `scripts/verify_quotes.py`: a contradiction counts only if both sides are verbatim quotes the checker finds; unproven ones are dropped.
  - `commands/obsidian-challenge.md`: red-teams a position against the vault's own decisions, failures and contradictions.
  - `commands/obsidian-retrieval-eval.md`: paraphrase cases that avoid the gold note's words.
  - `hooks/obsidian-recall.py`: at most 4 notes and 900 characters; abstains on weak matches; fails closed; logs only the prompt's *length*.
  - `integrations/obsidian-mcp-server/vault_ops.py` `_freshness_rerank`:
    - fades stale-status notes and notes superseded by another;
    - multiplies scores by an age decay `0.6 + 0.4·e^(−age/130 d)`.
- **Behaviour verified:** source read; not executed.
- **Invariants affected:**
  - MemoryClaim authority: its "clear winner → rewrite the page" step and the `unattended` rewrite opt-out.
  - Token determinism: age decay changes scores with the calendar, not the vault.
  - Disclosure: prompt hooks inject vault text outside any approved plan.
- **Smallest reusable components:**
  - the false-absence rule (prompt text);
  - quote verification of model-proposed contradictions against canonical record text by ID (an own implementation of about 40 lines);
  - freshness as *information*: capture and approval dates beside approved memory, plus an advisory "undated fast fact" hint at claim approval;
  - the challenge structure (position, cited counter-evidence, blind spots, verdict);
  - lexical-avoidance paraphrase cases for evaluation;
  - typed-relation vocabulary with inverses (SB-7).
- **Alternatives:** none needed. Sovereign already refuses rewrites (immutable records; corrections are revisions), so only the detection and verification halves transfer.
- **Removal test:** prompt text and advisory checks only; removing them changes no stored state.
- **Benefit (to measure):**
  - fabricated-absence rate in generated-answer evaluation;
  - share of proposed contradictions proven versus dropped;
  - undated fast facts flagged in a synthetic set.

### 2.3 DeerFlow — `bytedance/deer-flow@aa9913c4cc2d3ba537d78a48de9ef531fdcbbb05`

- **Paths** (under `backend/packages/harness/deerflow/`):
  - `agents/memory/AGENTS.md`, rules including:
    - "confirmation needs human evidence";
    - "the retrieval index is derived data";
    - "an unreadable file is corruption, not absence";
    - "diagnostics carry no memory content";
    - "gateway input handling removes forged dynamic-context markers".
  - `agents/memory/manager.py`: `get_context(query hint)`, `on_pre_compress`, a fatal-or-tolerated read-failure policy.
  - `knowledge/contract.py` and `knowledge/providers.py`:
    - read-only `RetrievalProvider` and `ScopedRetrievalProvider`;
    - validated `KnowledgeSource` records before anything becomes "model-visible evidence";
    - per-turn scope `all | disabled | selected`;
    - a provider that cannot apply a selected scope **fails closed**.
  - `agents/middlewares/summarization_middleware.py`: a versioned compaction transform with `summary_prompt_hash`; head-and-tail shortening with a visible marker.
  - `agents/middlewares/durable_context_middleware.py`: injected summaries are "untrusted data"; a 6,000-character render budget.
  - `projects/memory.py`: at most 30 facts or 2 KB per project; a **revision fence** so a user's deletion invalidates queued model extraction.
- **Behaviour verified:** source read; not executed.
- **Invariants affected:**
  - memory authority: LLM extraction writes facts automatically;
  - disclosure: remote memory backends mem0, honcho and openviking;
  - ADR-0008 §5 (client-held history) and §7 (conversation storage).
- **Smallest reusable components:**
  - a per-message memory scope (`all | none | selected`), bound into the token;
  - neutralising the `SOVEREIGN CONTEXT` marker inside earlier turns;
  - head-and-tail shortening of long earlier replies;
  - versioned, hashed, labelled summaries (later);
  - a revision fence for PR E's proposal queue.
- **Alternatives:** none; these are patterns.
- **Removal test:** each is one request field or prompt rule.
- **Benefit:** `memory: none` sends 0 vault items by construction; summaries trade tokens against continuity, to be measured in the first-use trial (PR G).

### 2.4 Understand-Anything — `Egonex-AI/Understand-Anything@b232f356446295e4eaa05b9b285e08ce5cd5e8a0`

- **Paths** (under `understand-anything-plugin/`):
  - `skills/understand-knowledge/parse-knowledge-base.py`: deterministic wikilink edges (`related`, weight 0.7) and index categories; unresolved links become warnings, not edges.
  - `skills/understand-knowledge/merge-knowledge-graph.py:183-212`:
    - LLM edges are normalised into the same types as wikilink edges;
    - **unknown types become `related`**;
    - weight defaults to 0.5 via `setdefault`, so a model-emitted weight overrides it;
    - deduplication by (source, target, type);
    - **no provenance field**.
  - `packages/core/src/staleness.ts` and `fingerprint.ts`: the graph records the commit it was built from (fresh, behind, ahead or diverged) and keeps SHA-256 fingerprints per file.
  - `packages/core/src/embedding-search.ts`: an exact cosine scan with a threshold, written to be bit-identical.
- **Behaviour verified:** source read; not executed.
- **Invariants affected:** inferred edges are never facts (ADR-0005 §3); a graph never admits context (R3).
- **Smallest reusable components:**
  - deterministic-first extraction with structural validation;
  - a freshness watermark for any derived view built outside the vault transaction;
  - bit-identical scan discipline.
- **Reject:** its merge semantics, which launder inferred edges into the same form as explicit ones.
- **Removal test:** views are derived; deleting them changes nothing canonical.
- **Benefit:** navigation discoverability (Benchmark 0003: 10 of 22 baseline misses reachable by one stored link); relevant again with SB-3 hubs.

### 2.5 vLLM — `vllm-project/vllm@b40b2a99c09e780d6c3c22ef496e3b3ee002fa0c`

- **Paths:**
  - `vllm/entrypoints/openai/chat_completion/api_router.py:44`: `/v1/chat/completions`.
  - `vllm/entrypoints/openai/models/api_router.py:20`: `/v1/models`.
  - `docs/getting_started/installation/cpu.apple.inc.md`: Apple Silicon is "experimental", must be built from source, CPU FP32/FP16 only, "no pre-built Apple silicon CPU wheels"; GPU through the community vllm-metal plugin (MLX models).
  - `docs/usage/usage_stats.md`: **anonymous usage data collected by default**; opt out with `VLLM_NO_USAGE_STATS=1`, `DO_NOT_TRACK=1` or `~/.config/vllm/do_not_track`.
- **Behaviour verified:** documentation and route source read; not run (no GPU here).
- **Invariants affected:** the K2 device boundary. "Local is a location, not a security level" (ARCHITECTURE §14.2 rule 4); "a loopback endpoint is not proof of offline operation" (Security Gate).
- **Smallest reusable component:** none to import. `providers.py` could address it by `base_url`.
- **Alternatives on a Mac:** llama.cpp server, Ollama, LM Studio, MLX-LM (all OpenAI-compatible; catalog note).
- **Removal test:** remove the provider entry.
- **Benefit:** only on a Linux GPU host; measure quality, tokens per second and cost against cloud models for the same task set.

## 3. Retrieval pilot: Khoj's models through Benchmark 0003

**Method.**
- **Models:** `thenlper/gte-small` (Hugging Face revision `17e1f347`, ONNX SHA-256 `0b01312b…`) and `mixedbread-ai/mxbai-rerank-xsmall-v1` (`b5c6e9da`, `536b7183…`).
- **Runtime:** ONNX Runtime, one thread, one text per call, scores rounded to 6 decimals.
- **Plumbing:**
  - each candidate is a relevance function in Benchmark 0003's harness;
  - the real Context Compiler then applies authority, sensitivity, budget and the token, unchanged;
  - token stability uses the harness's control record ("Zebra quokka xylophone.").
- **Variants:**
  - `dense` admits at cosine ≥ τ and ranks by cosine;
  - `hybrid_baseline_or_dense` admits lexical or dense and orders by cosine within a lexical tier;
  - `hybrid_admission_only` keeps baseline ranking and uses dense similarity only to admit;
  - `+rerank20` reorders the top 20 by the cross-encoder.

**Benchmark 0003** (254 records, 16 claims, 56 queries, 88 locally eligible expected items). Every variant: 0 nonsense-control admissions, 0 policy violations.

| Retriever | R@10 | Local recalled | Local noise | Local precision | Cloud recalled | Cloud noise | Paraphrase | Synonym | Abbrev. | Temporal | Tokens: repeat; changed by unrelated write |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `baseline` (merged) | 0.712 | 66/88 | 166 | 0.336 | 59/79 | 163 | 0/7 | 5/6 | 3/5 | 16/18 | 56/56; 0 |
| `dense@0.82` (Khoj default) | 0.916 | 77/88 | 139 | 0.408 | 69/79 | 140 | 6/7 | 6/6 | 4/5 | 14/18 | 56/56; 0 |
| `dense@0.82+rerank20` | 0.906 | 77/88 | 139 | 0.408 | 69/79 | 140 | 6/7 | 6/6 | 4/5 | 14/18 | 56/56; 0 |
| `dense@0.85` | 0.763 | 56/88 | 61 | 0.531 | 49/79 | 61 | 3/7 | 6/6 | 4/5 | 3/18 | 56/56; 0 |
| `dense@0.88` | 0.561 | 38/88 | 16 | 0.742 | 34/79 | 16 | 0/7 | 4/6 | 3/5 | 1/18 | 56/56; 0 |
| `hybrid_baseline_or_dense@0.82` | 0.907 | 77/88 | 208 | 0.320 | 69/79 | 206 | 6/7 | 6/6 | 4/5 | 14/18 | 56/56; 0 |
| `hybrid_baseline_or_dense@0.85` | 0.845 | 73/88 | 165 | 0.355 | 65/79 | 162 | 3/7 | 6/6 | 4/5 | 14/18 | 56/56; 0 |
| `hybrid_admission_only@0.82` | 0.873 | 76/88 | 209 | 0.317 | 68/79 | 207 | 6/7 | 6/6 | 4/5 | 16/18 | 56/56; 0 |
| **`hybrid_admission_only@0.85`** | 0.810 | **72/88** | **166** | 0.352 | **64/79** | **163** | 3/7 | 6/6 | 4/5 | **16/18** | 56/56; 0 |

**First-use trial and builder probe** (records included in the compiled local context):
- **First-use:** draft PR #12's seed and questions.
- **Probe:** six builder-authored synthetic questions for the Pocket and investment scenarios. It is **not founder data**, and its oracle is unreviewed.

| Retriever | First-use, own vocabulary | First-use, paraphrase | Probe |
| --- | ---: | ---: | ---: |
| `baseline` | 9/9 (noise 4) | 1/6 (noise 2) | 6/12 (noise 4) |
| `dense@0.82` | 9/9 (noise 5) | 1/6 (noise 1) | 8/12 (noise 0) |
| `hybrid_admission_only@0.82` | 9/9 (noise 6) | 2/6 (noise 2) | 10/12 (noise 4) |
| `hybrid_admission_only@0.85` | 9/9 (noise 4) | 1/6 (noise 2) | 7/12 (noise 4) |

**Diagnosis.**
- **Ranking is good, the fixed threshold is not.** In the first-use paraphrases, gold records rank 1, 2, 2, 4 and 7 of 14 by cosine, but score 0.776–0.826.
- **Pocket recovered fully.** "voice-activated desktop computer" reached all three Pocket records (baseline: one, plus the "desktop monitor arm" distractor).
- **The investment framework stayed fragmented.** "Research this company…" reached only the framework's first record; the valuation and downside records rank 2nd and 4th at 0.815 and 0.806, just under the cut.

**Caveats.**
- The suites are synthetic and small; Benchmark 0003's paraphrase tag has 7 queries.
- Thresholds were swept, not pre-registered, so treat 0.85 as a hypothesis.
- Cross-platform determinism (macOS arm64 versus Linux x86-64) is untested.
- Generated answers were not evaluated.

## 4. Retrieval experiment plan (Benchmark 0003 extension; evaluation only)

Benchmark 0003 stays the only retrieval benchmark: these are corpus, oracle and retriever additions to its harness. Production retrieval is unchanged until §6's gates are met.

1. **Corpus and oracle first, reviewed before any candidate runs.** Synthetic, dated records, claims and corrections, in seven groups:
   - **`cross_project`**: a Pocket and Sovereign OS idea trail across months, plus vocabulary-sharing projects that are *not* related. These score speculative connections: unrelated items admitted.
   - **`framework`**: an investment framework built over several records, one version as an approved framework claim citing them, and questions about a *different* company with little lexical overlap.
   - **`revision`**: a later framework that corrects one criterion (record correction and claim supersession); the current rule must be admitted and the superseded one excluded by policy.
   - **`contradiction`**: two incompatible frameworks and an explicit correction.
   - **`stale_fact`**: dated financial figures that must reach the model with their dates.
   - **`jargon`**: project codenames against plain-language questions.
   - **`no_answer`**: questions with no relevant record, to measure false admission.

   An independent reviewer (Codex) audits the oracle **before** results exist, so thresholds cannot be tuned to them.
2. **Candidates.**
   - `dense@{0.80,0.82,0.85,0.88}`;
   - `hybrid_admission_only@{0.80,0.82,0.85}`;
   - a **rank-gated** variant (top *k* within a margin δ of the best match), testing whether ranks generalise better than absolute thresholds and what unrelated writes then cost in tokens;
   - aliases combined with hybrid admission;
   - one alternative small model.

   Rerank appears only as a precision floor.
3. **Metrics.**
   - Existing: governed recall and noise for local and cloud, context precision (R4), R@k, MRR, per-tag results, temporal recall, token stability on repeat and after an unrelated write.
   - New:
     - nonsense and `no_answer` admissions;
     - framework completeness (all members admitted);
     - revision correctness;
     - stale facts reaching the model with their date;
     - **cross-platform token identity** (Linux x86-64 and macOS arm64);
     - embedding time per record, query latency, index size and cold start on a Mac.
4. **Representative evaluation (R6).** Extend the first-use trial (PR G) with paraphrase questions **written by the founder**, not the builder, on deliberately non-sensitive project knowledge. This is the "representative, legitimate usage" R6 requires.
5. **Pre-registered decision rule for a production proposal.** All of the following must hold:
   1. governed local recall improves overall and on `paraphrase`, `cross_project` and `framework`;
   2. cloud noise does not increase;
   3. temporal recall does not decrease;
   4. tokens are 100% identical on repeat, after an unrelated write and across platforms;
   5. zero sensitive egress and zero nonsense admissions, and `no_answer` admissions are no higher than baseline;
   6. the gain replicates on the founder's own questions.

   `hybrid_admission_only@0.85` meets conditions 1–5 on today's Benchmark 0003 (except across platforms, which is untested) and **fails condition 6** on the first-use paraphrases.
6. **Dependencies (founder decision).** `onnxruntime` and `tokenizers` as an optional evaluation-only extra; model files pinned by SHA-256 and loaded offline; no network at evaluation time after download. This is not a production dependency.

## 5. Shortlist worth adapting

| # | Component or pattern | From | Sovereign home | Tier |
| --- | --- | --- | --- | --- |
| S1 | False-absence rule: no context is not evidence that something never happened | obsidian-second-brain | ADR-0008 conversation prompt | 2 (fold into PR A) |
| S2 | Neutralise the `SOVEREIGN CONTEXT` marker inside earlier turns | DeerFlow | ADR-0008 rendering | 2 (fold into PR A) |
| S3 | Head-and-tail shortening of over-long earlier replies | DeerFlow | ADR-0008 client clipping | 1 (fold into PR A) |
| S4 | Dates beside approved memory in context ("timeless, dated, or a pointer") | obsidian-second-brain | Conversation rendering now, or the D15 `policy_version` bump | 2 |
| S5 | Per-message memory scope `all \| none \| selected`, fail closed, bound into the token | DeerFlow | ADR-0004 amendment; first slice of PR D | 2 |
| S6 | Dense **admission** (exact scan, in-vault vector table, deterministic per-text embedding, lexical ranking kept) | Khoj (technique) | Benchmark 0003 extension now; production only after §6 | 2 |
| S7 | Quote-verified contradiction proposals as a review queue, resolved through existing claim transitions | obsidian-second-brain | PR E | 2 |
| S8 | Framework claims: a reusable method is one approved claim citing its records, with scope and date | Pilot finding (§3) | PR E (claim kinds) | 2 |
| S9 | Revision fence: deletion invalidates queued model proposals | DeerFlow | PR E proposal queue | 2 |
| S10 | Challenge mode (position, cited counter-evidence, blind spots, verdict) | obsidian-second-brain | Conversation mode; history role later | 1, then 2 |
| S11 | Freshness watermark for out-of-transaction derived views | Understand-Anything | Any future index or graph view | 2 |
| S12 | Typed-relation vocabulary with inverses (`supersedes`, `depends_on`, `contradicts`) | obsidian-second-brain | SB-7 structured claims | 2 |

## 6. Recommendations

**Now** (no new dependency; within current paths):
- **PR A (PR #26) review round, founder's call:** S1, S2, S3, and S4 in conversation rendering only (conversation v0 is unreleased). This is a small hardening before the Codex audit.
- **Benchmark 0003 extension:** the oracle PR of §4.1 first, then the candidate PR of §4.2 (evaluation only; R1 unchanged).
- **PR E design input:** S7, S8 and S9 (specification only).

**Later** (each behind its gate):
- S5 as PR D's first slice.
- S6 production proposal only when §4.5 holds, including the founder-written paraphrases.
- S10 challenge mode, with a labelled history role for superseded and contested claims (needs an ADR-0004 amendment).
- DeerFlow-style versioned, labelled conversation summaries after the ADR-0008 §7 storage decision.
- S11 and S12 with SB-3 and SB-7.
- The cross-encoder only as a precision-floor experiment (R4).
- vLLM only on a Linux GPU host, as a `device` boundary provider, with telemetry disabled and network isolation verified; on a Mac, evaluate llama.cpp, Ollama or MLX-LM first.

**Reject:**
- Copying Khoj code (AGPL), or running Khoj as a backend: its own store and memory would shadow Sovereign's authority.
- Remote embedding or rerank endpoints: disclosure outside an approved plan.
- Autonomous vault rewrites, including reconcile's "clear winner" rewrites, `unattended` mode, and model fact extraction or eviction.
- Age-decay scores in the compiler: they break token determinism; show dates instead.
- Prompt hooks that inject vault text outside the Context Compiler.
- DeerFlow's harness, sandbox, subagents and remote memory backends.
- Understand-Anything's graph merge semantics, and LLM-built graphs as navigation truth.
- vLLM in the kernel process or as the Mac default.

## 7. ADR amendments and independent Codex audit gates

| Change | ADR work | Tier | Gate before merge |
| --- | --- | --- | --- |
| S1–S4 in PR A | Amend ADR-0008 (PROPOSED) in the same PR | 2 | Codex Tier 2 audit of PR #26's exact head; founder approval of ADR-0008 |
| Benchmark 0003 oracle extension | None (evaluation); update `docs/benchmarks/0003` | 1 | Independent oracle review **before** candidate results; reproducibility check (Codex reruns, byte-identical results) |
| Dense candidates in the harness | None for evaluation; founder approval of the optional evaluation dependency and model licenses | 1–2 | Codex rerun; license and supply-chain review (pinned SHA-256, offline load) |
| S5 memory scope | ADR-0004 amendment: request field bound into the token, fail-closed scopes | 2 | Adversarial tests (scope smuggling, `none` sends zero items, a selected scope cannot widen); Codex audit |
| S6 production dense admission | **New ADR: derived semantic index** (in-vault table keyed by kind, ID, content hash and model SHA-256; deleted in the Forget transaction; never exported or imported, only rebuilt; exact scan; determinism rules; vectors treated as content). **ADR-0005 amendment** lifting R6 for this method. **ADR-0004 amendment and new `policy_version`** (after D15's v1) | 2, approaching 3 | §4.5 met; Benchmark 0003 regenerated; Forget, correction and restore canary tests; cross-platform token test; Codex audit; founder approval |
| S7–S9 | PR E ADR: claim kinds (framework, hypothesis, decision), verified contradiction proposals, revision fence; ADR-0003 untouched or explicitly amended | 2 | Adversarial tests: a model proposal never gains authority; forged quotes are refused; a deleted item is never re-proposed. Codex audit |
| S10 history role | ADR-0004 amendment (a labelled role for superseded and contested claims) | 2 | Leakage and impersonation tests; Codex audit |
| vLLM or another local runtime | ADR-0004 amendment for a `device` boundary (ROADMAP §H order 4) | 2 | Network-isolation verification of the runtime (no telemetry, no downloads); Codex audit |

## 8. Licensing and attribution

- **Khoj** is AGPL-3.0-or-later. No Khoj code is in this repository or the pilot; the pilot independently implements a standard technique from Khoj's described behaviour. Any future reuse of Khoj code needs an explicit founder license decision first.
- **The two models** are separate works: `gte-small` is MIT and `mxbai-rerank-xsmall-v1` is Apache-2.0. Their licenses and SHA-256 hashes must be recorded wherever they are used.
- **obsidian-second-brain, DeerFlow and Understand-Anything** are MIT. Only ideas are adopted here. Copying code later requires keeping their copyright notices and license text, with attribution in the adopting file.
- **vLLM** is Apache-2.0, and is used only as an external server if ever adopted.
