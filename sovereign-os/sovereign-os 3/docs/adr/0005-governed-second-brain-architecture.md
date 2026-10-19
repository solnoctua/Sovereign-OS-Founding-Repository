# ADR-0005 — Governed Second Brain: Level 3–4 Retrieval, Knowledge Graphs and Obsidian Views

- **Status:** PROPOSED — architecture direction for founder review; not ratified, not implemented. Revision 2 (2026-10-19) incorporates an independent architecture review; see [*Revision notes*](#revision-notes).
- **Date:** 2026-10-19
- **Decision owner:** Human project owner
- **Review tier:** Tier 3 direction. Every implementation slice that changes schema, memory authority, deletion, retrieval relevance or disclosure is separately Tier 2 (see `AGENTS.md`, `docs/DEVELOPMENT.md`).
- **Builds on:** [ADR-0003](0003-memory-claim-authority.md) (MemoryClaim authority) and [ADR-0004](0004-governed-retrieval-context-compiler.md) (Context Compiler) **as merged to `main`** (merge `4fbecbe`, which includes `cee2c66`, the policy-state truncation fingerprint). This ADR amends neither; §6 names exactly where a later slice would have to.
- **Read alongside:** [Second-brain levels guide](../second-brain/LEVELS-AND-OBSIDIAN.md), [Obsidian projection spec](../second-brain/OBSIDIAN-PROJECTION.md), [Benchmark 0003](../benchmarks/0003-second-brain-retrieval-evaluation.md), [Architecture](../../ARCHITECTURE.md), [Roadmap §G](../../ROADMAP.md)
- **Constitution:** subordinate to the proposed Constitution; no constitutional text is amended or ratified by this document.

## 1. Problem and mission

Sovereign is a long-lived, local-first personal intelligence environment. Lexical search alone cannot reliably reconstruct ideas expressed in different words, relationships between months-old projects, what changed in an earlier decision, or why a memory is believed. A second brain must help the person **find, relate, explain and correct** what they know — and, per Constitution Art. I.6 and II.1–II.4, it is judged by whether the person understands, recalls and decides better, not by how many notes, vectors or graph nodes exist.

**Decision proposed:** extend the Sovereign Brain (ARCHITECTURE §4A) with **Level 3 semantic/hybrid discovery** and **Level 4 typed, source-backed relationship exploration**, keeping **Level 1 structured files** and **Level 2 linked wiki views** as human-facing representations. **Level 5 continuous intelligence is a long-term destination, not a present requirement.** The user must be able to **explore the result visually in Obsidian** (§9).

**What this is not:** a second store of record, a second authority lifecycle, or a second path to a model. Every new mechanism plugs into the existing records → MemoryClaims → Context Compiler → exact disclosure pipeline.

The five-level framing comes from a video heuristic, not an industry standard or maturity certification: use the least complex structure that answers real questions reliably. Authority, privacy, retention, correction and action boundaries are **orthogonal** to the levels; a Level 4 graph is not inherently safer, truer or more advanced than a Level 2 wiki.

## 2. Five-level vocabulary — required context for all builders

| Level | Mechanism | Suits | Characteristic failure | Sovereign role |
| --- | --- | --- | --- | --- |
| **L1** | **Structured files and routing.** Markdown, folders, indexes, instruction files that tell humans/agents where things live. | Known project or document, stable instructions, direct inspection. | Misses what is unnamed or misfiled; stale pointers. | Repository routing; generated index pages in the projection. |
| **L2** | **Linked wiki.** Concept and project pages, backlinks, crosslinks; Obsidian's graph shows note-to-note links. | Browsing a topic, orienting across projects. | A backlink is not a typed or trustworthy relationship; generated prose can distort sources. | Deterministic hub/index pages over canonical items (no generated prose in V0). |
| **L3** | **Semantic/hybrid retrieval.** Lexical/FTS plus embeddings, fusion, reranking, whole-document expansion. | Paraphrased or cross-lingual questions; discovery across projects. | Near meaning ≠ factual equality; top-k chunks lose document context; stale vectors; vectors leak content. | Candidate discovery only, evaluated against the lexical baseline (§6). |
| **L4** | **Typed, evidence-backed knowledge graph.** Entities and qualified relationships (`DEPENDS_ON`, `CONTRADICTS`, `SUPERSEDES`, `SUPPORTED_BY`), optionally graph-assisted retrieval. | Multi-hop connections, provenance, how decisions evolved, cross-project dependencies. | Wrong extraction, conflated entities, stale edges, hairball visuals, authority laundering. | Provenance graph first (computed from canonical links); typed relations later as structured MemoryClaims (§8). |
| **L5** | **Continuously maintained environment.** Scheduled ingestion, live connectors, background agents, consolidation. | Changing operational data, proactive help. | Recurring cost, over-collection, compounding stale beliefs, leakage, excessive autonomy. | **Deferred** behind explicit benefit, cost, consent and security gates (§10). |

The levels are **composable techniques, not a ladder**. One source needs whole-document access, another an index entry, a third a graph edge. Never vectorize everything by default or assume a graph is always needed.

**Three numbering schemes, three meanings:** **M0–M5** are Sovereign product milestones (ROADMAP §C); **L1–L5** are second-brain techniques (this section); **SB-0…SB-9** are the delivery slices of this workstream (§11, ROADMAP §G). Do not conflate them.

### Essential distinctions

- **Backlink vs assertion:** an Obsidian `[[link]]` says two notes reference each other. It carries no predicate, truth value, provenance or time.
- **Similarity vs truth:** a nearby vector means "semantically related", not "this record proves the proposition". IDs, dates and numbers need exact lookup.
- **Storage vs authority vs context:** retaining a source, indexing it or drawing it in a graph never promotes it to approved memory; task context is temporary and purpose-limited.
- **Correction vs change:** "the record was wrong" and "the world changed" both end in `superseded` today; they mean different things (§8.3).
- **Snapshot vs live:** a materialized view (Obsidian) shows state as of its generation; Sovereign's live state is authoritative.
- **Graph display vs graph reasoning:** a visual network is UI. Graph traversal used for answers must be benchmarked and governed separately (§6.5).

## 3. State classes and authority

The second brain adds representations; it must not blur which ones carry authority. Every artifact belongs to exactly one class:

| # | Class | Examples | Authority | Written by | On Forget | Export/restore | Reaches a model |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Source evidence** (canonical) | `records` | Evidence, not belief | Human capture/import | Tombstone trigger (ADR-0003) | Exported | As `evidence`, via the compiler |
| 2 | **Claims and decisions** (canonical) | `claims`, `claim_sources`, `claim_events` | Only `approved` + `supported` is approved memory | Humans decide; a model may only *propose* (`origin = model`, reserved by ADR-0003) | Forgotten with any cited record | Exported | As `approved_memory`, via the compiler |
| 3 | **Human-declared organization** (canonical, *proposed — does not exist yet*) | Projects, concepts, membership of records/claims | Organizational, not a truth claim | Human | Membership removed with its member; entity Forget cascades (§7) | Exported (new schema, SB-3) | Not until its own ADR |
| 4 | **Deterministic derived indexes and projections** | FTS5 tables, vectors, the provenance graph | None | Sovereign code; rebuildable | Same transaction (in-vault, §7) | **Not** exported; rebuilt | Never directly — candidate IDs only |
| 5 | **Rendered external projections** | Obsidian Markdown vault | None; a dated snapshot | Exporter CLI | Post-commit cleanup; residual copies disclosed (§7) | Not a backup | Never |
| 6 | **Working context** | ContextBundle, query text, query vector | Request-scoped | Compiler | Never persisted | — | Only the exact approved bundle |

Consequences that revision 1 got wrong or left implicit:

- **Model-proposed relationships, entities or summaries are not disposable projections.** A model run is not reproducible, costs money, and a human review of its output is a *decision*. If persisted, they are class 2: MemoryClaims with `origin = model`, created `proposed`. If not persisted, they are class 6 and vanish.
- **A typed relationship is a MemoryClaim with a structured form, not a new lifecycle** (decision D3). Revision 1's `review_state: proposed | reviewed | contested` would have duplicated `claims.status`, its history, its Forget cascade and its import/restore rules.
- **Projects, concepts, decisions and multi-record documents do not exist in the canonical schema.** Records hold `content, source, sensitivity, status, created_at, supersedes_id`; claims hold text, origin, status, lineage and source links. Hubs in Obsidian, project pages in an L2 wiki and "summarize the whole meeting" all need class 3 first (D2). Until then a projection can honestly show only sources, claims, revisions and decision histories.
- **Immutability makes indexing simple.** Record and claim IDs are insert-only and their content immutable (ADR-0003), so an index keyed by ID can become *existence*-stale (forgotten) but never *content*-stale. Claim status and support are always read live at hydration, never from an index.

## 4. Invariants

1. **One system of record.** Records, MemoryClaims, decision histories, tombstones and (once approved) human-declared organization live in the local vault. No Markdown export, FTS/vector index, entity table, LLM summary or external graph store becomes a competing system of record.
2. **Retrieval ≠ authority ≠ disclosure ≠ inference ≠ action.** Retrievers and graph traversal propose candidate canonical IDs. The compiler hydrates them from one snapshot, applies authority, sensitivity, relevance and budget, and builds the disclosure plan. Models and adapters never read the vault or widen their own disclosure.
3. **Approved memory means approved and supported.** Only `claims.is_authoritative` items may appear as approved memory — including structured relation claims. An edge never inherits approval from the claims or sources that support it.
4. **Exact-plan consent survives every retrieval upgrade.** Preview and execution use the same compiler; a new retrieval method enters only with a new `policy_version` whose token binds its complete relevant state (§6). Nothing is appended after approval.
5. **Forget reaches every derived representation** without resurrection through rebuild, restore or stale materialization; tombstones dominate; whatever cannot be guaranteed is disclosed, never concealed (§7).
6. **Derived structure is personal data.** Graph topology, entity names, generated titles and filenames, link sets and vectors can reveal sensitive information. No implicit cloud embedding, indexing, routing or graph publishing.
7. **Portability.** Indexes and renderers are replaceable; canonical export never depends on them. Removing every second-brain component restores lexical, canonical behavior and changes no authority.

## 5. Component model

```text
Capture/import + deliberate authoring (human-declared organization, SB-3)
          |
          v
  Canonical local vault (SQLite, one transaction boundary)
    records ── evidence identity, revisions, tombstones
    claims  ── decisions, source links, support derived on read
    [organization: projects/concepts/membership — proposed]
    [derived tables: FTS5, vectors — rebuildable, not exported]
          |
Question -> in-vault retrievers (lexical | FTS5 | semantic | timeline)   <- deterministic, local
          -> candidate IDs + per-method rank (same read snapshot)
          -> hydration: status, support, inherited sensitivity, policy state
          -> Context Compiler (relevance, authority, sensitivity, budget, disclosure, token)
          -> ContextBundle -> local evidence | exact preview -> approved provider
          |
          +--> provenance graph, computed on read (local UI/CLI)        [SB-2]
          +--> one-way Obsidian projection, CLI, outside the vault      [SB-2]
```

**Candidate contract (sketch, not a frozen schema).** Generalize ADR-0004's `RetrievalCandidate.via` from one value (`pinned | lexical | provenance`) to the set of methods that surfaced the item, each with its rank and quantized score. `Vault.context_candidates` remains the **single read snapshot** that runs in-vault retrievers and hydrates their hits. An out-of-vault retriever, if ever added, returns *hints* that are rehydrated in that snapshot; unknown or forgotten IDs are dropped and counted locally (`dropped_hints`), never surfaced as content.

**Routing.** Choose methods deterministically and inspectably: exact lookup for IDs and dates, timeline ordering for "what changed", hybrid search for paraphrase, whole-record access for "the entire note", graph traversal only for explicit relationship questions (SB-8). No model constructs SQL or graph queries, and no cloud model is used to route, rewrite or expand a question (§6.7).

## 6. Integration with the Context Compiler — what L3/L4 actually change

Revision 1 treated new retrievers as drop-in candidate providers. Against the merged ADR-0004 they are not. Each point below is a **compiler policy change** requiring a new `policy_version`, tests in the adversarial suite, and Tier 2 review.

1. **Relevance gate.** ADR-0004 excludes any unpinned candidate sharing no question term as `not_relevant`. An embedding hit with zero lexical overlap — exactly what L3 exists to find — is therefore discarded today. Changing the gate is a **disclosure change**: ADR-0004 decision 1 lets *relevant* unpinned private items enter an approved cloud plan, so a higher-recall retriever is also a wider-disclosure retriever. The new policy must define relevance per method (lexical: ≥1 term; semantic: quantized similarity ≥ τ calibrated on Benchmark 0003; graph: §6.5), list every method in `relevance.via`, and mark semantic-only items distinctly in the preview. Cloud eligibility of semantic-only items is founder decision **D4**.
2. **Ranking.** Today's order is pinned → claims → evidence, then lexical score, recency, ID. Fuse per-method ranks with **Reciprocal Rank Fusion** (well established; deterministic; needs no score calibration), keep the group order unless the benchmark shows harm, and break ties by `created_at` then ID. Fusion constants belong to the policy version.
3. **Truncation fingerprint.** Since `cee2c66`, an approval binds the policy-relevant state of the **complete relevant candidate universe** behind the cutoff. Lexical matching defines that universe crisply. A semantic retriever must too: the universe is every item with quantized similarity ≥ τ under an **exact (brute-force) scan**, fingerprinted with ID, quantized score and policy state, plus the retriever identity (model file hash, dimension, normalization, τ). Approximate-nearest-neighbor indexes cannot define this universe reproducibly; defer them until scale requires it and the token semantics are re-decided. Personal scale (≲10⁵ items) is comfortably brute-forceable.
4. **Determinism.** Record vectors are computed once at indexing and stored; only the query vector is computed per compile. Hold the query vector in an **in-memory, never-persisted** cache keyed by (question, retriever identity) so preview and execution see the same vector, and quantize similarities before thresholding. Gate: repeated compiles of an unchanged vault yield identical tokens (100%); a runtime that cannot meet it keeps semantic retrieval local-only.
5. **Graph-reached candidates.** ADR-0004 decision 3 keeps provenance-only claims `not_relevant`. Graph traversal generalizes provenance reach, so using it to admit context is a reversal of a founder decision (**D5**). Until then, graphs serve local navigation, explanation and review only. If later allowed, a path-reached item must still pass every policy, its path is shown locally in the preview, and path IDs never enter `outbound`.
6. **Whole documents and budget.** A record holds at most 10,000 characters and the V0 budget is 12,000, so "full document" today means "the whole record"; no chunking is needed. If embeddings use sub-record chunks, chunk hits resolve to the parent record ID and the disclosure unit stays the whole record (excerpt disclosure is a new semantics, deferred). Multi-record documents need class-3 grouping (SB-3). A task exceeding the budget runs locally or is split into separately approved requests — the cloud budget is never raised silently.
7. **Retrieval can itself disclose.** Cloud embedding of records or questions, cloud query rewriting (e.g. HyDE), cloud routing or planning, cloud reranking and cloud extraction all transmit personal content outside an approved plan. All are prohibited by default. Bulk cloud embedding or extraction would be a whole-vault disclosure and needs its own disclosure design, not a per-request preview.

## 7. Forget, correction and rebuild across representations

ADR-0003's rule — *the preview is the plan* — extends to every representation:

| Representation | Lives in | On Forget | On correction | Rebuild / export |
| --- | --- | --- | --- | --- |
| FTS5 lexical index | Vault DB, derived tables maintained by triggers | Deleted in the Forget transaction. Requires FTS5 `secure-delete` (SQLite ≥ 3.42); without it deleted terms persist in index segments — verified during review even with `PRAGMA secure_delete` on — so refuse to enable the index | New revision indexed on insert; old revision stays (it is still a record) | Rebuilt from canonical tables; not exported; rebuilt after restore |
| Vectors | Vault DB table keyed by ID + retriever identity | Same transaction. Vectors are treated as content (published embedding-inversion work recovers much of the input text) | As above | Re-embed; not exported |
| Provenance graph | Computed on read | Nothing to delete | Reads current lineage and support | — |
| Human-declared organization (SB-3) | Vault DB, canonical | Membership removed with its member. Forgetting an entity removes it, its memberships and every structured claim naming it | — | Exported with the canonical export |
| Structured relation claims (SB-7) | `claims` | Existing triggers (forgotten with cited evidence), plus forgotten with a forgotten subject/object entity | Stale when evidence is corrected, as any claim | Exported |
| Obsidian projection | User-chosen folder, **outside** the vault transaction | Post-commit: delete manifest-owned files for forgotten IDs and regenerate notes that linked them; anything not removed is recorded as pending (content-free IDs) and shown until done | Regenerate affected notes | Fully regenerable; never a backup |
| Projection manifest | Sovereign data directory, not the Obsidian vault | Entries for forgotten IDs removed by the same cleanup | — | Regenerated |
| Copies Sovereign does not control | Obsidian caches and file-recovery snapshots, trash folders, OS backups and search indexes, sync services, plugins | Cannot be guaranteed | — | Disclosed in the Forget preview and result |

- The Forget preview must count affected projection files per registered projection, so confirmation never understates the effect, and the result must report the actual cleanup outcome. Exports are not transactional; the projection spec defines crash-consistent, idempotent reconciliation instead of claiming atomicity.
- Index tables live **inside** the vault database by recommendation (**D6**): candidate generation and hydration then share one snapshot, and Forget is atomic. They are excluded from export and rebuilt after restore, so the backup format is unchanged.

## 8. Graphs

### 8.1 Provenance graph — first, deterministic, no new storage

Derived without inference from canonical facts, computed on read:

- **Nodes:** records (active and superseded revisions) and claims, with lifecycle status, derived support, authority, sensitivity (local UI only) and capture/decision times.
- **Edges:** `SUPPORTED_BY` (claim → record, from `claim_sources`); `CORRECTS` (record revision → predecessor, from `records.supersedes_id`); `SUPERSEDES` (claim → predecessor claim, from `claims.supersedes_id`). They map onto W3C PROV (`wasDerivedFrom`, `wasRevisionOf`) if an interchange vocabulary is ever wanted.
- **Scope:** a selected item plus a bounded number of hops; never the whole vault in one view.
- **No new authority, no new table, no Forget burden.** Status and support are read live.

### 8.2 Domain graph — later, governed through existing machinery

- **Entities** are class-3 human-declared organization (projects, concepts; people only with the sensitivity rules below). A model may *suggest* an entity; it exists only when a human creates it.
- **Relationships** are structured MemoryClaims (D3): `(subject_entity, predicate, object_entity, valid_from?, valid_until?)` plus a human-readable sentence, 1–8 cited records, normal lifecycle. Approving the claim is approving the edge; a wrong predicate is rejected like any wrong claim.
- **Predicate registry:** small, versioned, documented; no free-form predicates invented by a model.
- **Entity resolution** (aliases, renames, two people with one name) is a reversible human operation recorded in history; claims reference entity IDs, never names, so a merge never rewrites claims.
- **People and third parties:** nodes about other people are sensitive by default (Constitution Art. VI.3–VI.4), excluded from cloud plans and from default projection scope.
- **Contradictions** surface as `contested` claims or proposed `CONTRADICTS` relation claims; nothing silently chooses a winner (Art. IV.3).

### 8.3 Temporal semantics

Sovereign has two clocks today: **capture time** (`records.created_at`) and **decision time** (`claim_events.at`). It has no **valid time** — when a proposition held in the world. Two different situations both end in `superseded`:

- **Correction:** the capture or interpretation was wrong (a record corrected through `supersedes_id`, or a claim superseded because it was mistaken).
- **Change:** it was true and stopped being true (a project decision reversed).

Until **D10** is resolved, every view and every prompt treats `superseded` as *"no longer the current approved interpretation"*, never as *"was false"*, and temporal answers cite capture and decision times rather than inventing validity intervals. Recommendation: before typed relations are persisted, extend MemoryClaim with optional `valid_from`/`valid_until` and a supersession reason (`correction | change`) — the established bitemporal model (valid time vs record time) used by SQL:2011 temporal tables and by temporal knowledge-graph memories such as Graphiti — through its own ADR-0003 extension.

## 9. Obsidian — a first-class optional visual client

**Requirement:** the user can open a Sovereign-generated vault in Obsidian, see a meaningful Graph view and Local graph, follow projects, concepts, sources, claims and decisions, and find out from the notes *why* any line exists and *when* things changed. This is an acceptance requirement, not decoration. The full contract is in the [Obsidian projection spec](../second-brain/OBSIDIAN-PROJECTION.md); the rules that bind the architecture are:

- **Local, opt-in, one-way, CLI-generated.** No HTTP endpoint writes files (V0 has no authentication, so an endpoint would let any same-origin client write to disk). Output goes to a user-chosen folder outside any Git working tree; the exporter only creates, rewrites or deletes files it owns.
- **Honest about Obsidian.** Graph lines are untyped links; Obsidian can show link *direction* (Arrows) but not edge labels, edge properties or validity. Node labels are filenames. Semantics, evidence and time live in note text under predicate-named headings — **one canonical relationship, one link, one explanation**.
- **A snapshot, labeled as such.** Every note carries its generation and states that Sovereign is authoritative; statuses are as of export, never "live".
- **Shows only what is canonical.** Today: sources, claims, revisions, decision histories and their links. Project/concept hubs require SB-3; typed relations require SB-7; validity intervals require SB-6. Unreviewed model proposals are excluded from the default scope.
- **Private by default.** Sensitive items excluded unless explicitly included; an opaque-filename mode exists (**D7**); no plugin is required; sync and plugins are the user's explicit choice and are warned about.
- **Forget and correction** follow §7; edits made in Obsidian are never imported (a governed import would need its own ADR).

The [synthetic demo vault](../second-brain/obsidian-demo-vault/) shows the target, including future-only elements clearly marked.

## 10. Cost, cadence and Level 5

**Near term (L3–L4):** deterministic local retrieval, optional local embeddings after measurement, a computed provenance graph, manual exports. **No recurring model bill is needed to keep the brain usable.** Paid calls happen only through the existing approved request path, or through a future capped extraction workflow with its own ADR, disclosure design and per-run cost preview.

**Level 5:** periodic sync, proactive conflict detection, live connectors, agent coordination. Revisit only when daily utility, security and recovery, explicit user and bystander consent, provider limits and a **measured monthly cost and energy budget** justify it. Always-on is not a permission or retention policy. Local, event-triggered index maintenance and an exporter re-run are **not** Level 5. Future connectors are queried at use time when authorized; copying their content into the vault is capture, with provenance, consent and retention.

**Long horizon.** Far more capable models and very long contexts may make some retrieval unnecessary *for capability*; they do not make it unnecessary *for disclosure*. Art. VI.2 still forbids sending the life history because a model could read it. The durable value is the canonical state plus governance; retrieval methods stay replaceable behind the candidate contract, and the compiler stays the single choke point — including for future agentic retrieval, where a model may propose queries but never decides disclosure.

## 11. Delivery slices

Deliberately small first; one numbering (also ROADMAP §G):

| Slice | Delivers | Level | Tier / gate |
| --- | --- | --- | --- |
| **SB-0** | This ADR, guide, projection spec, demo vault, Benchmark 0003 spec (docs only) | — | Founder decisions §15 |
| **SB-1** | Benchmark 0003 Stage A: synthetic fixtures, runner, baseline report on the *current* compiler (candidate and bundle level). No production change | L3 evaluation | Tier 1 |
| **SB-2** | Provenance graph computed on read + one-way Obsidian projection CLI for sources, claims, revisions and histories, with manifest and Forget/correction cleanup. No schema change. **First user-visible slice** | L2 view + L4 provenance | Tier 2 (deletion reaches an external store) |
| **SB-3** | Human-declared projects/concepts and membership; projection hubs | L1/L2 | Tier 2 schema ADR; D2 |
| **SB-4** | FTS5/BM25 candidates inside the vault, measured against SB-1 | L3 lexical | Tier 2; D6 |
| **SB-5** | Local embeddings + fusion — **only if** SB-1/SB-4 data show paraphrase or cross-lingual misses that matter | L3 semantic | Tier 2; D4, D11 |
| **SB-6** | Temporal claim extension: valid time, supersession reason | L4 prerequisite | Tier 2; D10 |
| **SB-7** | Typed relations as structured MemoryClaims; human-authored first, model-proposed after an extraction ADR | L4 domain | Tier 2/3; D3 |
| **SB-8** | Graph-assisted context retrieval | L4 retrieval | Tier 2; D5 |
| **SB-9** | Level 5 research only | L5 | §10 gates |

These slices complement, and never displace, M0–M5. Security, recovery and daily capture remain prerequisites for real data; a graph visualization must not delay them.

## 12. Evaluation and gates

Measure, against an unchanged baseline: candidate recall@k and bundle recall of *policy-eligible* expected IDs, exact-ID correctness, temporal accuracy (including correction vs change), abstention, irrelevant-context fraction, grounded edge-path precision, latency, index size and build time, and per-query cost. A better retrieval score never compensates for a broken invariant.

**Must-pass (zero tolerance):** no unauthorized promotion; no forgotten content in any derived store or registered projection after Forget (canary-string scan); no sensitive egress; no candidate, vector or graph content outside the approved preview; identical tokens for an unchanged vault; no third-party sync of personal graph data without an explicit action; canonical export/restore unchanged. Loopback serving is not authentication. The security gate remains **NOT PASSED**: synthetic or intentionally non-sensitive data only.

## 13. Prior art — borrowed ideas, not dependencies

Proven: lexical BM25/FTS, dense + lexical hybrid retrieval with rank fusion, parent-document expansion, bitemporal modeling, provenance vocabularies. Established but costly or unproven at personal scale: LLM-built community graphs (GraphRAG), LLM-maintained incremental graphs (LightRAG), LLM-generated chunk context. Research or vendor-reported: personalized-PageRank multi-hop (HippoRAG), autonomous memory layers (Mem0, Letta), temporal agent-memory graphs (Graphiti/Zep). The [guide](../second-brain/LEVELS-AND-OBSIDIAN.md#5-prior-art-what-to-borrow-what-not-to-adopt) records what each would contribute and why none is adopted now: each either makes a model the author of memory, needs an external graph database, or creates derived text whose Forget cost is unbounded — and none answers a problem Sovereign has measured yet.

## 14. Alternatives and reversal

- Replace canonical memory with LightRAG/Neo4j/an Obsidian vault: **rejected** (retrieval and extraction must not determine memory authority).
- A separate relationship review lifecycle: **rejected** in favor of structured MemoryClaims (D3).
- Vector-only or graph-only retrieval: **rejected as exclusive methods** (weak on exactness, chronology and whole documents; extraction errors).
- Approximate-NN vector index now: **deferred** (§6.3).
- Generated wiki prose in V0: **deferred**; a generated summary, if ever persisted, is a proposed MemoryClaim with source links.
- Always-on Level 5 now: **deferred** (§10).
- Bidirectional Obsidian editing: **deferred** (would bypass the approval workflow).
- Hosted vector/graph databases: **not required** at single-user scale; SQLite tables and recursive queries suffice for bounded traversal.

**Reversal:** derived tables and projections are disposable; dropping them restores lexical/canonical behavior without touching authority or the backup format. Class-3 organization and structured claims are canonical once adopted and need migration, export/restore and Forget tests in their own ADRs.

## 15. Decisions requested from the founder

| ID | Decision | Recommendation |
| --- | --- | --- |
| **D1** | Approve the L3–L4 target, deferred L5, and the slice order of §11 (benchmark and provenance/Obsidian before retrieval changes) | Approve |
| **D2** | Where project/concept nodes come from | Human-declared organization (SB-3) first; model suggestions later, accepted only by a human |
| **D3** | How typed relationships are governed | As structured MemoryClaims; no second lifecycle |
| **D4** | May semantic-only (zero-term) candidates enter **cloud** plans? | Local-only in the first semantic policy; cloud eligibility only after Benchmark 0003 shows precision at τ no worse than lexical, and always marked in the preview |
| **D5** | May graph traversal admit context items (revisits ADR-0004 decision 3)? | Not now; navigation and explanation only until SB-8 evidence |
| **D6** | Where derived indexes live | Inside the vault DB, maintained in the same transaction, excluded from export |
| **D7** | Obsidian filenames: readable titles or opaque IDs | `Readable title (short-id).md` for private items in scope; opaque mode available; sensitive items excluded by default |
| **D8** | Obsidian cleanup on Forget | Automatic post-commit deletion of owned files, pending state shown, residual copies disclosed |
| **D9** | When projections are rebuilt | Manual CLI run first; local event-triggered rebuild later (not L5) |
| **D10** | Temporal claim semantics | Add valid time and supersession reason (correction vs change) before SB-7 |
| **D11** | Local embedding model, runtime and dependency | Choose only if SB-1/SB-4 data justify it; pin by file hash; new dependency review |

## 16. Open engineering questions (no founder decision needed yet)

- Calibration of τ and fusion constants; multilingual behavior (ADR-0004's stopword list is English-only).
- Whether FTS5 replaces the compiler's term scan or only supplies candidates, and how that changes `fingerprint`.
- Export format version for class-3 organization and its import/restore authority rules.
- Projection scope language (by project, date range, status) and how a scope is previewed.
- Cost ceilings and preview format for any future extraction run.

**No implementation, new permission, persistent schema, background ingestion or constitutional amendment is authorized by this document.**

## Revision notes

Revision 2 (independent review, 2026-10-19; findings in [the review record](../reviews/2026-10-19-second-brain-architecture-review.md)) changed revision 1 (`bae766e`) as follows:

- Added the state-class table (§3); reclassified model proposals and reviewed relationships as MemoryClaims instead of disposable projections; replaced `review_state` with structured MemoryClaims.
- Recorded that projects, concepts, decisions and multi-record documents have no canonical basis yet, and made human-declared organization an explicit slice and decision.
- Replaced "retrievers are drop-in candidate providers" with the concrete compiler policy changes L3/L4 require (§6), including the `cee2c66` fingerprint, ADR-0004 decisions 1 and 3, determinism and retrieval-time disclosure.
- Specified Forget per representation (§7), including FTS5 segment retention, vector invertibility and non-transactional exports; replaced "atomically reconcile" exports with crash-consistent reconciliation.
- Added temporal semantics (correction vs change, valid time).
- Corrected Obsidian capabilities (direction can be shown; labels cannot; labels are filenames), made export CLI-only, and moved the format contract into a dedicated spec.
- Unified the delivery numbering (SB-0…SB-9) across ADR, guide and roadmap, and listed founder decisions D1–D11.
