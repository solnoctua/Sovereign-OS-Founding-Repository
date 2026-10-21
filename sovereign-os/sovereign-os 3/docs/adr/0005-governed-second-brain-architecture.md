# ADR-0005 — Governed Second Brain: Level 3–4 Retrieval, Knowledge Graphs and Obsidian Views

- **Status:** APPROVED AS ARCHITECTURAL DIRECTION (Tier 3) by the founder on 2026-10-21 — D1–D14 approved per the §15 recommendations and R1–R7 approved as planning positions (§12.2); **D15 explicitly deferred**; nothing is implemented, and every implementation slice still needs its own reviews and approvals. See [*15.1 Founder decision record*](#151-founder-decision-record-2026-10-21). Revision 4 (2026-10-20) makes the Obsidian export a user-requested snapshot (founder direction) and aligns with Benchmark 0003 as of PR #4's `da52ce9`; revision 3 resolved the Codex architecture audit (F1–F6). See [*Revision notes*](#revision-notes).
- **Date:** 2026-10-20 (revision 4; first proposed 2026-10-19); direction approved 2026-10-21
- **Decision owner:** Human project owner
- **Review tier:** Tier 3 direction. Every implementation slice that changes schema, memory authority, deletion, retrieval relevance or disclosure is separately Tier 2 (see `AGENTS.md`, `docs/DEVELOPMENT.md`).
- **Builds on:** [ADR-0003](0003-memory-claim-authority.md) (MemoryClaim authority) and [ADR-0004](0004-governed-retrieval-context-compiler.md) (Context Compiler) **as merged to `main`** (`4fbecbe`, including `cee2c66`, the policy-state truncation fingerprint, which this branch now contains). This ADR amends neither; §6, §7, §8.2–§8.3 and D15 name where a later slice would have to.
- **Read alongside:** [Second-brain levels guide](../second-brain/LEVELS-AND-OBSIDIAN.md), [Obsidian export spec](../second-brain/OBSIDIAN-PROJECTION.md), [Second-brain validation spec](../second-brain/SECOND-BRAIN-VALIDATION.md), [Architecture](../../ARCHITECTURE.md), [Roadmap §G](../../ROADMAP.md). Retrieval evaluation: Benchmark 0003, `docs/benchmarks/0003-retrieval-evaluation.md`, delivered by [PR #4](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/pull/4) and **not yet merged**.
- **Constitution:** subordinate to the proposed Constitution; no constitutional text is amended or ratified by this document.

## 1. Problem and mission

Sovereign is a long-lived, local-first personal intelligence environment. Lexical search alone cannot reliably reconstruct ideas expressed in different words, relationships between months-old projects, what changed in an earlier decision, or why a memory is believed. A second brain must help the person **find, relate, explain and correct** what they know — and, per Constitution Art. I.6 and II.1–II.4, it is judged by whether the person understands, recalls and decides better, not by how many notes, vectors or graph nodes exist, nor by a synthetic recall metric.

**Decision proposed:** extend the Sovereign Brain (ARCHITECTURE §4A) with **Level 3 semantic/hybrid discovery** and **Level 4 typed, source-backed relationship exploration**, keeping **Level 1 structured files** and **Level 2 linked wiki views** as human-facing representations. **Level 5 continuous intelligence is a long-term destination, not a present requirement.** The user must be able to **explore the result visually in Obsidian** (§9).

**What this is not:** a second store of record, a second authority lifecycle, or a second path to a model. Every new mechanism plugs into the existing records → MemoryClaims → Context Compiler → exact disclosure pipeline. **Retrieval ≠ authority ≠ disclosure ≠ inference ≠ action.**

The five-level framing comes from a video heuristic, not an industry standard or maturity certification: use the least complex structure that answers real questions reliably. Authority, privacy, retention, correction and action boundaries are **orthogonal** to the levels; a Level 4 graph is not inherently safer, truer or more advanced than a Level 2 wiki.

## 2. Five-level vocabulary — required context for all builders

| Level | Mechanism | Suits | Characteristic failure | Sovereign role |
| --- | --- | --- | --- | --- |
| **L1** | **Structured files and routing.** Markdown, folders, indexes, instruction files that tell humans/agents where things live. | Known project or document, stable instructions, direct inspection. | Misses what is unnamed or misfiled; stale pointers. | Repository routing; generated index pages in the projection. |
| **L2** | **Linked wiki.** Concept and project pages, backlinks, crosslinks; Obsidian's graph shows note-to-note links. | Browsing a topic, orienting across projects. | A backlink is not a typed or trustworthy relationship; generated prose can distort sources. | Deterministic hub/index pages over canonical items (no generated prose in V0). |
| **L3** | **Semantic/hybrid retrieval.** Lexical/FTS plus embeddings, fusion, reranking, whole-document expansion. | Paraphrased or cross-lingual questions; discovery across projects. | Near meaning ≠ factual equality; top-k chunks lose document context; stale vectors; vectors leak content; more recall can mean more disclosure. | Candidate discovery only, evaluated in Benchmark 0003 (§6, §12). |
| **L4** | **Typed, evidence-backed knowledge graph.** Entities and qualified relationships (`DEPENDS_ON`, `CONTRADICTS`, `SUPERSEDES`, `SUPPORTED_BY`), optionally graph-assisted retrieval. | Multi-hop connections, provenance, how decisions evolved, cross-project dependencies. | Wrong extraction, conflated entities, stale edges, hairball visuals, authority laundering. | Provenance graph first (computed from canonical links); typed relations later as structured MemoryClaims (§8). |
| **L5** | **Continuously maintained environment.** Scheduled ingestion, live connectors, background agents, consolidation. | Changing operational data, proactive help. | Recurring cost, over-collection, compounding stale beliefs, leakage, excessive autonomy. | **Deferred** behind explicit benefit, cost, consent and security gates (§10). |

The levels are **composable techniques, not a ladder**. One source needs whole-document access, another an index entry, a third a graph edge. Never vectorize everything by default or assume a graph is always needed.

**Numbering schemes:** **M0–M5** are Sovereign product milestones (ROADMAP §C); **L1–L5** are second-brain techniques (this section); **SB-0…SB-9** are the delivery slices of this workstream (§11, ROADMAP §G); **D1–D15** are this ADR's founder decisions (§15); **R1–R7** are the founder's intended retrieval positions from Benchmark 0003 (§12). Do not conflate them.

### Essential distinctions

- **Backlink vs assertion:** an Obsidian `[[link]]` says two notes reference each other. It carries no predicate, truth value, provenance or time.
- **Similarity vs truth:** a nearby vector means "semantically related", not "this record proves the proposition". IDs, dates and numbers need exact lookup.
- **Storage vs authority vs context:** retaining a source, indexing it or drawing it in a graph never promotes it to approved memory; task context is temporary and purpose-limited.
- **Navigation vs relevance:** following a provenance link locally is not a reason to put the linked item into model context (R3).
- **Correction vs change:** "the record was wrong" and "the world changed" both end in `superseded` today; they mean different things (§8.3).
- **Snapshot vs live:** an Obsidian export shows state as of its snapshot time; Sovereign's live state is authoritative, and forgetting something in Sovereign does not change an export already made.
- **Graph display vs graph reasoning:** a visual network is UI. Graph traversal used for answers must be benchmarked and governed separately (§6).

## 3. State classes and authority

The second brain adds representations; it must not blur which ones carry authority. Every artifact belongs to exactly one class:

| # | Class | Examples | Authority | Written by | On Forget | Export/restore | Reaches a model |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Source evidence** (canonical) | `records` | Evidence, not belief | Human capture/import | Tombstone trigger (ADR-0003) | Exported | As `evidence`, via the compiler |
| 2 | **Claims and decisions** (canonical) | `claims`, `claim_sources`, `claim_events` | Only `approved` + `supported` is approved memory | Humans decide; a model may only *propose* (`origin = model`, reserved by ADR-0003) | Forgotten with any cited record | Exported | As `approved_memory`, via the compiler |
| 3 | **Human-declared organization** (canonical, *proposed — does not exist yet*) | Projects, concepts, membership of records/claims | Organizational, not a truth claim | Human | Membership removed with its member; entity Forget cascades (§7) | Exported (new schema, SB-3) | Not until its own ADR |
| 4 | **Deterministic derived structure** | The provenance graph (computed on read); any future index | None | Sovereign code; rebuildable | Nothing stored, or same transaction (§7) | **Not** exported; rebuilt | Never directly — candidate IDs only |
| 5 | **Rendered external exports** | Obsidian Markdown snapshot (a ZIP or a new folder) | None; a dated snapshot | Exporter CLI, on request | Not reached: an export already made is outside Sovereign's control; a new export reflects its snapshot (§7, §9) | Not a backup | Never |
| 6 | **Export staging** (transient, non-canonical) | One run's hidden staging folder or temporary file beside its destination | None | Exporter | Not reached; removed by its own run on a best-effort basis, and an interrupted run can leave it behind (listed to the user by later exports, never deleted by them) | Not exported | Never |
| 7 | **Working context** | ContextBundle, query text | Request-scoped | Compiler | Never persisted | — | Only the exact approved bundle |

Consequences:

- **Model-proposed relationships, entities or summaries are not disposable projections.** A model run is not reproducible, costs money, and a human review of its output is a *decision*. If persisted, they are class 2: MemoryClaims with `origin = model`, created `proposed`. If not persisted, they are class 7 and vanish.
- **A typed factual relationship is a MemoryClaim with a structured form, not a new lifecycle** (decision D3). A separate `review_state` would duplicate `claims.status`, its history, its Forget cascade and its import/restore rules.
- **Deterministic provenance edges are structural, not claims.** `SUPPORTED_BY`, `CORRECTS` and `SUPERSEDES` are facts Sovereign already stores; they need no redundant claim about themselves.
- **Projects, concepts, decisions and multi-record documents do not exist in the canonical schema.** Records hold `content, source, sensitivity, status, created_at, supersedes_id`; claims hold text, origin, status, lineage and source links. Hubs in Obsidian, project pages in an L2 wiki and "summarize the whole meeting" all need class 3 first (D2), through a separately reviewed data model. Until then an export can honestly show only sources, claims, revisions and decision histories.
- **Immutability makes derived structure simple.** Record and claim IDs are insert-only and their content immutable (ADR-0003), so anything keyed by ID can become *existence*-stale (forgotten) but never *content*-stale. Claim status and support are always read live, never from a derived copy.

## 4. Invariants

1. **One system of record.** Records, MemoryClaims, decision histories, tombstones and (once approved) human-declared organization live in the local vault. No Markdown export, index, entity table, LLM summary or external graph store becomes a competing system of record.
2. **Retrieval ≠ authority ≠ disclosure ≠ inference ≠ action.** Retrievers and graph traversal propose candidate canonical IDs. The compiler hydrates them from one snapshot, applies authority, sensitivity, relevance and budget, and builds the disclosure plan. Models and adapters never read the vault or widen their own disclosure.
3. **Approved memory means approved and supported.** Only `claims.is_authoritative` items may appear as approved memory — including structured relation claims. An edge never inherits approval from the claims or sources that support it.
4. **Exact-plan consent survives every retrieval change.** Preview and execution use the same compiler; a new retrieval method enters only with a new `policy_version`, and the token keeps binding the complete policy-relevant retrieval state (§6.3). Nothing is appended after approval.
5. **Forget reaches every derived store Sovereign manages** (class 4: the computed graph and any future index or vectors, which live inside the vault) without resurrection through rebuild, restore or stale materialization; tombstones dominate. An Obsidian export and its transient staging (classes 5–6) are bounded by their snapshot: a new export excludes what was forgotten before its snapshot boundary, a Forget that commits after that boundary is not reflected in it (the post-snapshot notice reports this when it can detect it), and exports already made are outside Sovereign's control. This is disclosed, never concealed (§7, §9).
6. **Derived structure is personal data.** Graph topology, entity names, generated titles and filenames, link sets and vectors can reveal sensitive information. No implicit cloud embedding, indexing, routing or graph publishing, and no reference to an object outside an export's authorized scope (§9).
7. **Untrusted text is data, never markup.** Record, claim and note text is rendered inert in every projection; only canonical relationships between authorized items become links (§9).
8. **Portability.** Indexes and renderers are replaceable; canonical export never depends on them. Removing every second-brain component restores lexical, canonical behavior and changes no authority.

## 5. Component model

```text
Capture/import + deliberate authoring (human-declared organization, SB-3)
          |
          v
  Canonical local vault (SQLite, one transaction boundary)
    records ── evidence identity, revisions, tombstones
    claims  ── decisions, source links, support derived on read
    [organization: projects/concepts/membership — proposed]
          |
Question -> in-vault retrieval (lexical today; see §6)                    <- deterministic, local
          -> candidate IDs (same read snapshot)
          -> hydration: status, support, inherited sensitivity, policy state
          -> Context Compiler (relevance, authority, sensitivity, budget, disclosure, token)
          -> ContextBundle -> local evidence | exact preview -> approved provider
          |
          +--> provenance graph, computed on read (local navigation only)  [SB-2]
          +--> one-way Obsidian snapshot export, CLI, on request         [SB-2]
                 (a ZIP or a new folder, never inside a Git tree)
```

**Candidate contract (sketch, not a frozen schema).** If a second retrieval method is ever added, generalize ADR-0004's `RetrievalCandidate.via` from one value (`pinned | lexical | provenance`) to the set of methods that surfaced the item. `Vault.context_candidates` remains the **single read snapshot** that runs in-vault retrieval and hydrates the hits. Any retriever's derived state lives inside the vault transaction (D6), so Forget reaches it atomically and its candidate universe is bound by the fingerprint; a store outside the vault would need its own §7 row and a defined, reported Forget behavior before it could be considered. Dropping unknown or forgotten IDs at hydration is defense in depth, never the Forget mechanism.

**Routing.** Choose methods deterministically and inspectably: exact lookup for IDs and dates, timeline ordering for "what changed", whole-record access for "the entire note", graph traversal only for local exploration. No model constructs SQL or graph queries, and no cloud model is used to route, rewrite or expand a question (§6.7).

## 6. Integration with the Context Compiler — what L3/L4 actually change

New retrieval methods are **not** drop-in candidate providers. Against the merged ADR-0004, each point below is a **compiler policy change** requiring a new `policy_version`, tests in the adversarial suite, a regenerated Benchmark 0003, Tier 2 review and founder approval. Benchmark 0003 (PR #4) has now measured the cheap lexical alternatives; the evidence and the founder's intended positions are in §12.

1. **Relevance gate.** ADR-0004 excludes any unpinned candidate sharing no question term as `not_relevant`. An embedding hit with zero lexical overlap — exactly what L3 exists to find — is therefore discarded today. Changing the gate is a **disclosure change**: ADR-0004 decision 1 lets *relevant* unpinned private items enter an approved cloud plan, so a higher-recall retriever is also a wider-disclosure retriever. Benchmark 0003 shows the effect even lexically: Porter normalization recovers 2 more expected items and admits 47 more irrelevant ones, and admitting stem-only matches costs exactly as much; only the exact-stem tie-break, which orders texts the baseline already admits, recovers an item (1) with no added noise. **No production retrieval change is authorized** (R1).
2. **Ranking.** Today's order is pinned → claims → evidence, then matched-term count, recency, ID; its recency tie-break is an implicit temporal prior. Weighted ranking (IDF, BM25) is **deferred** (R2): in Benchmark 0003 it invalidates 51–54 of 56 pending previews after one unrelated write, and BM25 loses the recency prior (temporal MRR 0.733 → 0.473). Any future weighted or fused ranking is evaluated in the Benchmark 0003 harness first.
3. **Truncation fingerprint — not to be weakened.** Since `cee2c66`, an approval binds the policy-relevant state of the **complete relevant candidate universe**, including candidates below the cutoff. It must not be weakened for performance or convenience (R2). Weighted scores that change after unrelated writes would make previews stale. That is fail-closed (409, re-preview), and under R2 (pending) it is preferred to weakening the fingerprint, but it reverses ADR-0004's statement that irrelevant vault changes do not invalidate an approval. Adopting weighted scores therefore needs an ADR-0004 amendment, whether pending previews are allowed to go stale or an order-preserving projection is bound instead. Pending (R2). A *policy-equivalent fingerprint* that ignores numerical score changes is a research question only: a score change could be ignored **only if** equivalence of every protected decision is demonstrated — full relevant candidate membership including below-cutoff matches; policy-relevant ordering and cutoff membership; authority, status, support and sensitivity; eligibility and inclusion/exclusion decisions; exact outbound content and disclosure policy. It would need an ADR-0004 amendment, independent adversarial review and explicit founder approval. **It is not proposed here.** A semantic retriever, if ever adopted, must define its relevant universe as crisply as lexical matching does (an exact scan, not approximate nearest neighbors).
4. **Determinism.** Any retriever must keep token stability on an unchanged vault at 100%: the same vault state and question always give the same token. This is separate from Benchmark 0003's unrelated-write metric, which weighted scoring fails (§6.3); Benchmark 0003 reports it too, at 56/56 for every retriever as of `da52ce9`. A runtime that cannot meet it keeps that retriever local-only. Query text and query vectors are never persisted.
5. **Provenance and graph-reached candidates.** ADR-0004 decision 3 keeps claims reached only through provenance `not_relevant`, and **that conservative exclusion is preserved** (R3). Claim-source and supersession links are valuable for deterministic, local navigation in the UI and Obsidian (SB-2), but traversal must never by itself make a connected record or claim relevant for any model context, local or cloud; even a local-only expansion is a change to ADR-0004 decision 3 with its own `policy_version`. Benchmark 0003 measures both sides. Admitting one hop of existing provenance over the baseline (`baseline_provenance`, counterfactual) would recover 6 items (72/88) for 7 more irrelevant items and 12 more private items in cloud plans. **Navigation** — showing one stored link from what the preview already lists, with no compiler change — makes 10 of the baseline's 22 missed items discoverable. Navigation is the SB-2 direction; admission stays deferred and would need an independent evaluation, starting local-only, and a founder decision (SB-8, D5).
6. **Whole documents and budget.** A record holds at most 10,000 characters and the V0 budget is 12,000, so "full document" today means "the whole record"; no chunking is needed. The **12-item and 12,000-character limits are retained** (R5): one synthetic question needing 14 items does not justify a global change. Multi-record documents need class-3 grouping (SB-3). The budget applies to every target, local included, and changing it for any target is a `policy_version` change (ADR-0004 decision 5). *Proposed, not part of R5:* a task that exceeds the budget could be split into separately compiled requests, each cloud one separately approved.
7. **Retrieval can itself disclose.** Cloud embedding of records or questions, cloud query rewriting (e.g. HyDE), cloud routing or planning, cloud reranking and cloud extraction all transmit personal content outside an approved plan. All are prohibited by default. Bulk cloud embedding or extraction would be a whole-vault disclosure and needs its own disclosure design, not a per-request preview.
8. **Precision is a priority, especially for cloud plans** (R4). Benchmark 0003 finds governed context precision-poor under every retriever (about 27–34%): in crowded vocabularies the budget fills with lexical noise, and in a cloud plan that noise is private data offered for disclosure. Improving recall while widening the preview is not automatically progress. Relevance floors, thresholds, or cloud-specific ranking and budgets need their own evaluation and a versioned policy approval.

## 7. Forget, correction and rebuild across representations

ADR-0003's rule — *the preview is the plan* — extends to every representation:

| Representation | Lives in | On Forget | On correction | Rebuild / export |
| --- | --- | --- | --- | --- |
| Provenance graph | Computed on read | Nothing to delete | Reads current lineage and support | — |
| Human-declared organization (SB-3) | Vault DB, canonical | Membership removed with its member. Forgetting an entity removes it, its memberships and every structured claim naming it | — | Exported with the canonical export |
| Structured relation claims (SB-7) | `claims` | Existing triggers (forgotten with cited evidence), plus forgotten with a forgotten subject/object entity (a new trigger, decided with SB-7) | Stale when evidence is corrected, as any claim; non-authoritative when a pinned entity is merged or split (§8.2) | Exported |
| Obsidian export | A ZIP or folder the user holds, **outside** Sovereign | A new export reflects its snapshot and excludes what was forgotten before it; an export already made is neither changed nor erased, and the Forget preview and result say so (§9) | A new export shows the new revision | A fresh export on request; never a backup |
| Future FTS5 index (deferred, R2) | Vault DB, maintained by triggers | Same transaction. Requires FTS5 `secure-delete` (SQLite ≥ 3.42); without it deleted terms persist in index segments — reproduced during review even with `PRAGMA secure_delete` on — so refuse to enable the index | New revision indexed on insert | Rebuilt; not exported |
| Future vectors (deferred, R6) | Vault DB, keyed by ID + retriever identity | Same transaction. Vectors are treated as content (published embedding-inversion work recovers much of the input text) | As above | Re-embed; not exported |
| Copies Sovereign does not control | Obsidian exports already made (downloaded ZIPs, extracted folders, their copies), Obsidian caches and file-recovery snapshots, trash folders, OS backups and search indexes, sync services, plugins | Cannot be guaranteed | — | Disclosed in the Forget preview and result |

- The Forget preview and result state that Obsidian exports made earlier, and hidden leftovers of interrupted exports, are outside Sovereign's control and must be deleted by the user to remove the item from them; Sovereign keeps no list of exports and claims no deletion of them. Exports are never transactional with SQLite; an export is consistent at its snapshot boundary only (§9).
- If an index is ever adopted, its tables live **inside** the vault database (D6) so candidate generation and hydration share one snapshot and Forget is atomic; they are excluded from export and rebuilt after restore.

## 8. Graphs

### 8.1 Provenance graph — first, deterministic, no new storage

Derived without inference from canonical facts, computed on read:

- **Nodes:** records (active and superseded revisions) and claims, with lifecycle status, derived support, authority, sensitivity (local UI only) and stored/decision times.
- **Edges:** `SUPPORTED_BY` (claim → record, from `claim_sources`); `CORRECTS` (record revision → predecessor, from `records.supersedes_id`); `SUPERSEDES` (claim → predecessor claim, from `claims.supersedes_id`). They map onto W3C PROV (`wasDerivedFrom`, `wasRevisionOf`) if an interchange vocabulary is ever wanted.
- **Scope:** a selected item plus a bounded number of hops; never the whole vault in one view.
- **No new authority, no new table, no Forget burden, no effect on relevance.** Status and support are read live, and traversal never changes a compiler decision (R3).

### 8.2 Domain graph — later, governed through existing machinery

- **Entities** are class-3 human-declared organization (projects, concepts; people only with the sensitivity rules below). A model may *suggest* an entity; it exists only when a human creates it.
- **Relationships** are structured MemoryClaims (D3): `(subject_entity, predicate, object_entity, valid_from?, valid_until?)` plus a human-readable sentence, 1–8 cited records, normal lifecycle. Approving the claim is approving the edge; a wrong predicate is rejected like any wrong claim.
- **Predicate registry:** small, versioned, documented; no free-form predicates invented by a model.
- **Entity resolution** (aliases, renames, two people with one name) is a reversible human operation recorded in history; claims reference entity IDs, never names, so a merge never rewrites claims. Because a merge or split changes what an approved relation claim refers to, relation claims **pin the identity version** of their subject and object, as `evidence_sha256` pins a record: a merge or split makes the claim non-authoritative (a stale-like support state, bound into the truncation fingerprint) until a human re-approves or supersedes it.
- **People and third parties:** entities about other people are sensitive by default (Constitution Art. VI.3–VI.4) and excluded from default export scope. Keeping a relation claim that names such an entity out of cloud plans needs **entity-aware sensitivity**: a structured claim inherits the most restrictive sensitivity of its cited evidence *and* of every entity it names. That is an ADR-0004 amendment (sensitivity inheritance and the fingerprint's policy state) with a `policy_version` bump, decided with SB-3/SB-7, not assumed here.
- **Contradictions** surface as `contested` claims; nothing silently chooses a winner (Art. IV.3). A typed `CONTRADICTS` relation between two claims would need claim-valued endpoints, which the structured form above does not have, and a Forget rule that forgets the relation when either endpoint claim is forgotten (an ADR-0003 trigger amendment); it is deferred until both are designed.

### 8.3 Temporal semantics

Sovereign has two clocks today: **stored time** (`records.created_at`, set at capture or carried in by ordinary import and trusted restore, so not proof of when something was captured) and **decision time** (`claim_events.at`, which trusted restore also carries in from the backup). It has no **valid time** — when a proposition held in the world. Two different situations both end in `superseded`:

- **Correction:** the capture or interpretation was wrong (a record corrected through `supersedes_id`, or a claim superseded because it was mistaken).
- **Change:** it was true and stopped being true (a project decision reversed).

Until **D10** is resolved, every local view (Timeline, decision histories, the Obsidian export) treats `superseded` as *"no longer the current approved interpretation"*, never as *"was false"*, and shows stored and decision times rather than inventing validity intervals. Model prompts cannot answer "then vs now" through the governed path today: ADR-0004 never sends superseded claims and sends no decision times for approved memory, so prompt-level temporal answers would need an ADR-0004 prompt-boundary change with its own `policy_version`. Recommendation: before typed relations are persisted, extend MemoryClaim with optional `valid_from`/`valid_until` and a supersession reason (`correction | change`) — the established bitemporal model (valid time vs record time) — through its own ADR-0003 extension.

## 9. Obsidian — a first-class optional visual client

**Requirement:** the user can open a Sovereign-generated vault in Obsidian, see a meaningful Graph view and Local graph, follow projects, concepts, sources, claims and decisions, and find out from the notes *why* any line exists and *when* things changed. This is an acceptance requirement, not decoration. The full contract is in the [Obsidian export spec](../second-brain/OBSIDIAN-PROJECTION.md); its tests are in the [validation spec](../second-brain/SECOND-BRAIN-VALIDATION.md) §4. The rules that bind the architecture:

- **Local, opt-in, one-way, on request.** The user runs the export CLI; a later UI button may call the same operation and return a download, but no HTTP request ever chooses a filesystem path (V0 has no authentication). The output is a ZIP or a new folder that does not exist yet, never inside a Git working tree (another Obsidian vault only with explicit confirmation); an export never writes into an existing folder or over an existing file, and never deletes anything but its own staging and temporary files.
- **A snapshot, not a managed projection (founder direction 2026-10-20; Codex F2, N1, N2).** One read transaction is the snapshot boundary: what was forgotten before it is absent, and nothing that commits after it is reflected. The export is rendered, verified, packaged with a no-replace move, and reported complete only when it is; a failed export is reported as failed and cleans up its own temporary files on a best-effort basis; an interrupted process reports nothing and never leaves a partial or unverified result under the destination name (only a hidden, recognizably named leftover beside it); neither is ever reported as complete; after an OS crash, power loss or storage failure nothing is guaranteed — flushing is best effort, not durability — and any export produced around such an event is treated as potentially invalid and regenerated; the next export starts fresh. There is no registry, no ownership hash, no write lock held during file writes, no automatic cleanup and no background reconciliation, and nothing claims that filesystem writes are atomic with SQLite. An export already made is an independently held artifact: Sovereign cannot erase downloaded, copied, synced or backed-up exports, and the Forget preview and result, the export report and every note say so. Export spec §11.
- **Untrusted text is inert (Codex F3).** Every stored value is untrusted for rendering, whatever path it arrived by — including times, source labels and IDs, which ordinary import and trusted restore can set to arbitrary text. Free text is escaped (never Unicode-normalized, since normalization can manufacture backticks) and emitted only as its own top-level fenced `text` block whose fence is unclosable under every normalization form, with plugin syntaxes neutralized. Times appear only after a strict parse; raw IDs are not written (D13); titles pass a Unicode-category whitelist; filenames carry keyed per-export handles and fit 140 UTF-8 bytes including the handle and `.md` (Codex N4); frontmatter values are escape-free by construction; links, tags and callouts are generated only from the authorized canonical relationship set. A blockquote alone is insufficient. Parser-based and native Obsidian tests, including a zero-unauthorized-network-request test, are acceptance gates.
- **Scope is closed before edges are built (Codex F4).** The authorized set is computed first, from the single snapshot and the confirmed class-level scope; a link is emitted only for a slot the item itself holds whose other end is in the set, never composed across an omitted item, and `SUPPORTED_BY` only to evidence whose pinned hash still matches. Excluded, forgotten, missing and malformed endpoints are one class, so changes outside the set change no file. An item with an omitted slot carries one fixed, non-identifying sentence at a fixed position, or, in closed mode, is left out (D12); scope is never widened to complete a link; nothing excluded appears in a title, filename, handle, ID, folder, frontmatter, navigation note, metric or log. Before anything is offered, the export is verified **structurally** against the exporter's own model — files, filenames, frontmatter values, generated lines and links — never by scanning free text for excluded IDs, which can coincide with ordinary words (Codex N3).
- **Honest about Obsidian.** Graph lines are untyped links; Obsidian can show link *direction* (Arrows) but not edge labels, edge properties or validity. Node labels are filenames. Semantics, evidence and time live in note text under predicate-named headings — **one canonical relationship, one link, one explanation**.
- **Animate is not history (Codex F6).** Graph view's *Animate* shows notes in file-creation order on that disk. It does not replay stored times, corrections, supersessions or MemoryClaim status changes. Chronology comes from the Timeline note and each claim's decision history; no animation engine is planned.
- **A snapshot, labeled as such.** Every note's banner states the snapshot time, that it may be out of date, that forgetting in Sovereign does not change it, and that Sovereign is authoritative; Start Here states the class-level scope and how to refresh (export again); statuses are as of the snapshot, never "live".
- **Shows only what is canonical.** Today: sources, claims, revisions, decision histories and their links. Project/concept hubs require SB-3; typed relations require SB-7; validity intervals require SB-6. Unreviewed model proposals are excluded from the default scope.
- **Private by default.** Sensitive items excluded unless explicitly included; an opaque-filename mode exists (D7); no plugin is required; sync and plugins are the user's explicit choice and are warned about. Edits made in Obsidian are never imported.

The [synthetic demo vault](../second-brain/obsidian-demo-vault/) shows the target, including an inert adversarial note, a partial-provenance note and future-only elements clearly marked.

## 10. Cost, cadence and Level 5

**Near term (L3–L4):** deterministic local retrieval, a computed provenance graph, manual exports. **No recurring model bill is needed to keep the brain usable.** Paid calls happen only through the existing approved request path, or through a future capped extraction workflow with its own ADR, disclosure design and per-run cost preview.

**Level 5:** periodic sync, proactive conflict detection, live connectors, agent coordination. Revisit only when daily utility, security and recovery, explicit user and bystander consent, provider limits and a **measured monthly cost and energy budget** justify it. Always-on is not a permission or retention policy. A user-requested export is **not** Level 5, and none runs automatically. Future connectors are queried at use time when authorized; copying their content into the vault is capture, with provenance, consent and retention.

**Long horizon.** Far more capable models and very long contexts may make some retrieval unnecessary *for capability*; they do not make it unnecessary *for disclosure*. Art. VI.2 still forbids sending the life history because a model could read it. The durable value is the canonical state plus governance; retrieval methods stay replaceable behind the candidate contract, and the compiler stays the single choke point — including for future agentic retrieval, where a model may propose queries but never decides disclosure. Benchmark optimization does not dictate this architecture: the goal is trustworthy lifelong knowledge continuity, not a synthetic recall score.

## 11. Delivery slices

Deliberately small first; one numbering (also ROADMAP §G):

| Slice | Delivers | Level | State / gate |
| --- | --- | --- | --- |
| **SB-0** | This ADR, guide, export spec, validation spec, demo vault (docs only; PR #3) | — | D1–D14 approved 2026-10-21; D15 deferred (§15.1) |
| **SB-1** | Benchmark 0003 retrieval evaluation: synthetic corpus, harness, governed-recall/noise/precision baseline, lexical alternatives, provenance admission (counterfactual) and navigation | L3 evaluation | **Executed in PR #4 (`da52ce9`), not merged**; its Codex P2 is resolved and CI passed; no production retrieval change authorized (R1) |
| **SB-2** | Provenance graph computed on read (local navigation only) + a one-way **Obsidian snapshot export** CLI (a ZIP or a new folder) for sources, claims, revisions and histories, with inert serialization, scope closure, structural verification and byte-limited filenames; no registry, no reconciliation, no canonical schema change. **First user-visible slice** | L2 view + L4 provenance | Tier 2 (it renders personal data into a file the user takes away); validation spec §3–§4; **before production use:** the separate high-priority Tier 2 storage-integrity fix (SECURITY-GATE) |
| **SB-3** | Human-declared projects/concepts and membership; export hubs | L1/L2 | Tier 2 schema ADR; D2 |
| **SB-4** | A lexical change — **none is authorized** (R1). Porter normalization and the exact-stem tie-break are evaluated candidates only; any proposal is its own Tier 2 PR with a `POLICY_VERSION` bump, regenerated Benchmark 0003, independent review and founder approval, and chooses its stemmer implementation there. IDF, BM25 and any persistent FTS5 index deferred (R2) | L3 lexical | Not authorized |
| **SB-5** | Local embeddings — **deferred** until representative, legitimate usage shows meaningful improvement over deterministic retrieval (R6) | L3 semantic | Tier 2; D4, D11 |
| **SB-6** | Temporal claim extension: valid time, supersession reason | L4 prerequisite | Tier 2; D10 |
| **SB-7** | Typed relations as structured MemoryClaims; human-authored first, model-proposed after an extraction ADR | L4 domain | Tier 2/3; D3 |
| **SB-8** | Graph- or provenance-assisted context — **deferred**; local-only exploration and an independent evaluation first (R3) | L4 retrieval | Tier 2; D5 |
| **SB-9** | Level 5 research only | L5 | §10 gates |

These slices complement, and never displace, M0–M5. Security, recovery and daily capture remain prerequisites for real data; a graph visualization must not delay them.

## 12. Evidence and evaluation

### 12.1 Benchmark 0003 (PR #4, `da52ce9`) — executed, evaluation only, not merged

Benchmark 0003 is the canonical retrieval evaluation (subject to its own audit and merge). It evaluates the merged Context Compiler on a synthetic corpus of 254 records, 16 claims and 56 queries with an explicit, policy-validated oracle; it measures retrieval before policy and governed context after policy, for local and cloud targets; no provider is called. Results for locally eligible expected items (88), from PR #4 at `da52ce9`; every retriever keeps 56/56 tokens on an unchanged vault, and none produces a policy violation:

| Approach | Recalled | Noise | Previews invalidated by an unrelated write |
| --- | ---: | ---: | ---: |
| Current baseline | 66/88 | 166 | 0/56 |
| Porter normalization | 68/88 | 213 | 0/56 |
| Porter + IDF | 69/88 | 212 | 53/56 |
| FTS5 Porter BM25 | 69/88 | 212 | 53/56 |
| Exact-stem tie-break (stems only order exact matches) | 67/88 | 165 | 0/56 |
| Baseline + one-hop provenance admission (counterfactual) | 72/88 | 173 | 0/56 |

- **What it establishes and does not:** see the validation spec §2. Generated-answer correctness, abstention and temporal interpretation are **NOT MEASURED**. No query lacks a relevant item; six queries whose expected items are all `sensitive_cloud` already show what a cloud plan offers when no expected item is disclosable (22 noise items across them under the baseline, 33 under Porter normalization), but questions with no relevant item at all are not measured.
- **Navigation, not admission:** one stored link from what the preview already shows makes 10 of the baseline's 22 misses discoverable without changing relevance, context or token (§6.5).
- **Founder direction recorded in PR #4 (2026-10-20):** production retrieval stays the merged lexical retriever; no experimental retriever is approved; IDF, BM25, FTS5 and embeddings are deferred; ADR-0004 decision 3, the budgets, disclosure eligibility and the fingerprint are unchanged.
- **Review dependency resolved:** PR #4's Codex P2 (unreproducible scale timings) was resolved by removing the timings; its CI passed. This ADR relies on no timing, and incidental container timings are not a capacity guarantee.

### 12.2 Founder's retrieval positions — approved planning positions

These positions follow from Benchmark 0003 and agree with the founder direction recorded in PR #4 on 2026-10-20. **The founder approved them on 2026-10-21 as planning and evaluation constraints, not as a production retrieval implementation** (§15.1); implementing any change is a separate reviewed PR — never PR #3.

| ID | Position (approved planning position, 2026-10-21) | Where reflected |
| --- | --- | --- |
| **R1** | **No production retrieval change is authorized.** Porter normalization (+2 expected items, +47 irrelevant) and the exact-stem tie-break (+1 expected item, no added noise or cloud items) are evaluated candidates only; either would need its own Tier 2 PR, `policy_version` bump, regenerated Benchmark 0003, independent review and founder approval. | §6.1, SB-4 |
| **R2** | Defer IDF/BM25. Do not weaken the fingerprint for performance or convenience; a policy-equivalent fingerprint is future research needing demonstrated equivalence of every protected decision (§6.3), an ADR-0004 amendment, independent adversarial review and founder approval. | §6.2–6.3 |
| **R3** | Provenance links serve deterministic local navigation (10 of 22 baseline misses discoverable this way); traversal never automatically makes items relevant for any model context, local or cloud; ADR-0004 decision 3 preserved. | §6.5, §8.1, SB-2, SB-8, D5 |
| **R4** | Retrieval precision is a priority, especially for cloud; floors, thresholds or cloud-specific policies need separate evaluation and versioned approval. | §6.8 |
| **R5** | Keep the 12-item and 12,000-character budgets. | §6.6 |
| **R6** | Defer local embeddings until representative, legitimate usage shows meaningful improvement; no sensitive personal notes while the Security Gate is NOT PASSED. | SB-5, D4, D11 |
| **R7** | Keep PR #4's synthetic framework, reproducibility discipline, policy-eligibility checks and regression comparisons; resolve its own findings in PR #4. | §12.1, validation spec §1 |

PR #4 lists founder decisions that remain open: (1) whether any candidate, most plausibly the exact-stem tie-break, should ever be prepared as a production proposal, with its stemmer implementation, FTS5 availability and `policy_version`; (2) a relevance floor, threshold or cloud-specific policy to address precision; (3) evaluation follow-ups — no-evidence queries, and a private, never-committed founder-run evaluation on real notes after the Security Gate (the harness would need to read a corpus from a path); (4) evaluation infrastructure (`evaluation/` as a non-shipped package, pytest configuration, a results-match-code test).

### 12.3 Gates

A better retrieval score never compensates for a broken invariant. **Must-pass (zero tolerance):** no unauthorized promotion; no forgotten content in any store Sovereign manages, or in an export whose snapshot follows the Forget (canary scan); no unauthorized network request from an export; no sensitive egress; no candidate, vector or graph content outside the approved preview; identical tokens for an unchanged vault; no third-party sync of personal graph data without an explicit action; canonical export/restore unchanged. Loopback serving is not authentication. The security gate remains **NOT PASSED**: synthetic or intentionally non-sensitive data only.

### 12.4 Evaluation state (as of 2026-10-20; mirrors validation spec §1)

1. **Retrieval evaluation (SB-1):** Benchmark 0003, executed in PR #4 (`da52ce9`), **not merged**; production retrieval unchanged.
2. **Provenance graph tests (SB-2, validation spec §3):** specified, **not implemented**.
3. **Obsidian snapshot export tests (SB-2, validation spec §4):** specified, **not implemented**; no native Obsidian check has been executed.
4. **Structured entity, temporal and relationship tests (SB-3, SB-6, SB-7, validation spec §5):** future; each needs its own ADR.
5. **Semantic and hybrid experiments (SB-5):** future and deferred (R6); run inside the Benchmark 0003 harness, never as a second benchmark.
6. **Generated-answer evaluation (validation spec §6):** optional and separate; **not established by SB-1**, and NOT MEASURED today.

## 13. Prior art — borrowed ideas, not dependencies

Proven: lexical BM25/FTS, dense + lexical hybrid retrieval with rank fusion, parent-document expansion, bitemporal modeling, provenance vocabularies. Established but costly or unproven at personal scale: LLM-built community graphs (GraphRAG), LLM-maintained incremental graphs (LightRAG), LLM-generated chunk context. Research or vendor-reported: personalized-PageRank multi-hop (HippoRAG), autonomous memory layers (Mem0, Letta), temporal agent-memory graphs (Graphiti/Zep). The [guide](../second-brain/LEVELS-AND-OBSIDIAN.md#5-prior-art-what-to-borrow-what-not-to-adopt) records what each would contribute and why none is adopted now: each either makes a model the author of memory, needs an external graph database, or creates derived text whose Forget cost is unbounded — and none answers a problem Sovereign has measured.

## 14. Alternatives and reversal

- Replace canonical memory with LightRAG/Neo4j/an Obsidian vault: **rejected** (retrieval and extraction must not determine memory authority).
- A separate relationship review lifecycle: **rejected** in favor of structured MemoryClaims (D3).
- Vector-only or graph-only retrieval: **rejected as exclusive methods** (weak on exactness, chronology and whole documents; extraction errors).
- Weighted ranking or an approximate-NN index now: **deferred** (R2, §6.3).
- A managed Obsidian projection — a registry of owned files and hashes, the vault write lock held across file publication, automatic reconciliation after every Forget (revision 3): **superseded for V0** by founder direction (2026-10-20). It was a second state-management system for an optional view; a labeled snapshot with a disclosed Forget boundary gives the person what they need (export spec §11.5).
- Generated wiki prose in V0: **deferred**; a generated summary, if ever persisted, is a proposed MemoryClaim with source links.
- An Obsidian animation engine: **rejected** (F6).
- Always-on Level 5 now: **deferred** (§10).
- Bidirectional Obsidian editing: **deferred** (would bypass the approval workflow).
- Hosted vector/graph databases: **not required** at single-user scale; SQLite tables and recursive queries suffice for bounded traversal.

**Reversal:** derived structure and projections are disposable; dropping them restores lexical/canonical behavior without touching authority or the backup format. Class-3 organization and structured claims are canonical once adopted and need migration, export/restore and Forget tests in their own ADRs.

## 15. Decisions requested from the founder

| ID | Decision | Recommendation |
| --- | --- | --- |
| **D1** | Approve the L3–L4 target, deferred L5, and the slice order of §11 (evaluation and provenance/Obsidian before retrieval changes) | Approve |
| **D2** | Where project/concept nodes come from | Human-declared organization (SB-3) first; model suggestions later, accepted only by a human |
| **D3** | How typed relationships are governed | As structured MemoryClaims; no second lifecycle |
| **D4** | May semantic-only (zero-term) candidates ever enter **cloud** plans? | Not while embeddings are deferred (R6); if revisited, local-only first, then only with Benchmark 0003 evidence that precision does not fall (R4), always marked in the preview |
| **D5** | May graph or provenance traversal admit context items (revisits ADR-0004 decision 3)? | No; local navigation only (R3) until an independent evaluation justifies a proposal |
| **D6** | Where a derived index would live, if one is ever adopted | Inside the vault DB, same-transaction Forget, excluded from export (moot while R2 defers FTS5) |
| **D7** | Obsidian filenames: readable titles or opaque handles | `Readable title (handle).md`, where the handle is the keyed per-export handle (§9, D13), for private items in scope; opaque mode `<handle>.md` available; sensitive items excluded by default |
| **D8** | Obsidian exports and Forget | **Settled by founder direction (2026-10-20):** no automatic cleanup. An export is a snapshot outside Sovereign's control; a new export reflects its snapshot; the Forget preview and result disclose that earlier exports are not erased |
| **D9** | When exports are made | **Settled (2026-10-20):** only when the user asks — CLI first, a later UI button calling the same operation; no scheduled, background or automatic regeneration. Replacing an existing export folder would be a separate, user-confirmed operation that protects user edits |
| **D10** | Temporal claim semantics | Add valid time and supersession reason (correction vs change) before SB-7 |
| **D11** | Local embedding model, runtime and dependency | Not now (R6); choose only after representative usage justifies it; pin by file hash; new dependency review |
| **D12** | Default Obsidian provenance mode | *Label* mode (one fixed partial sentence) for local browsing; *closed* mode (drop items with omitted links) recommended for removable, synced or shared exports |
| **D13** | Raw canonical IDs in exported notes | None: the keyed handle only. Even canonical-UUID IDs can be enumerable (ordinary import derives claim IDs with a public UUIDv5 namespace), so a raw ID could reveal a gap where an excluded item sits |
| **D14** | Projection registry | **Not needed for V0 (2026-10-20):** exports keep no persistent state; revisit only if an in-place refresh is ever proposed |
| **D15** | Lineage sensitivity of claims: a private claim that supersedes a sensitive claim often restates it | **Deferred by the founder (2026-10-21); not ratified** (§15.1). Proposed direction: decide in the Context Compiler (an ADR-0004 amendment, Tier 2), because the same text is eligible for cloud plans today; the projection only warns until then |

D8, D9 and D14 record the founder's 2026-10-20 direction. The founder's decisions on this table and on R1–R7 (§12.2) are recorded in §15.1.

### 15.1 Founder decision record (2026-10-21)

**Approved — architectural direction (Tier 3).** On 2026-10-21 the founder approved **D1–D14** according to the recommendations above, in particular:

- L3–L4 remain the strategic second-brain target; L5 is deferred.
- Human-declared projects and concepts precede model-proposed organization.
- Typed factual relationships use governed MemoryClaims.
- Semantic-only relevance remains local-only initially.
- Graph traversal does not expand Context Compiler model context.
- Future indexes must be governed, rebuildable and compatible with Forget.
- Obsidian is an optional one-shot snapshot export, initially through a manual CLI.
- Previously downloaded exports are not automatically erased after Forget.
- No persistent export registry, continuous synchronization or background reconciliation is required for V0.
- Temporal semantics remain a future implementation requirement.
- Embeddings remain deferred.
- Export scope, lineage omissions, filenames and keyed handles follow D7 and D12–D14.

**Approved — retrieval planning positions R1–R7 (§12.2).** No experimental retriever is authorized for production; Porter and the exact-stem tie-break remain evaluated candidates only; IDF/BM25/FTS5 and embeddings remain deferred; the current conservative fingerprint and context budgets are preserved; provenance is for local navigation, not automatic model-context admission; retrieval precision and cloud-disclosure minimization are priorities; Benchmark 0003's evaluation infrastructure is retained. These are planning constraints, not a production retrieval implementation.

**Deferred — D15 (lineage sensitivity).** No new lineage-sensitivity or cloud-disclosure policy is ratified. Current ADR-0004 behavior is preserved unchanged. **Residual risk:** a private successor claim may restate a sensitive predecessor, and that text is eligible for cloud plans today ([SECURITY-GATE](../SECURITY-GATE.md)). Changing this requires a dedicated Tier 2 policy proposal, independent adversarial review and founder approval. The deferral is **not** a certification that current lineage sensitivity is safe for real private data.

**Boundaries of this approval.** It approves this ADR's Tier 3 architectural direction only. It does not ratify the Constitution or ADR-0003/0004; approve a new schema, embedding system or retrieval policy; authorize broader cloud disclosure; certify the Security Gate (still NOT PASSED); approve the production Obsidian exporter; waive future Tier 2 reviews; or resolve the pre-existing SQLite hidden-rowid storage-integrity defect, which remains a separate high-priority Tier 2 repair required before production SB-2.

**Audit evidence.** Codex's independent architecture audit of PR #3 (F1–F6, CONDITIONAL PASS at `b17b6a2`) and its follow-up findings N1–N4 are dispositioned in the [remediation record](../reviews/2026-10-20-codex-audit-remediation.md); Codex's final verification closed N2 and N4 — and with them every PR #3 specification finding — with a **PASS at the specification level** on the Codex-verified commit `591c011027cddcd9383941bbde60075ec54c3935`. The approved text is revision 4 as verified there; this record changes status and decision metadata only.

## 16. Open engineering questions (no founder decision needed yet)

- Calibration and form of any relevance floor (R4), and how a narrower cloud policy is versioned.
- Export format version for class-3 organization and its import/restore authority rules.
- Projection scope language (by project, date range, status) and how a scope is previewed.
- How long an export's snapshot read may hold writers back on a large vault, measured in SB-2 (export spec §11.1).
- Whether an in-place refresh of a Sovereign-generated export folder is ever wanted (a separate, user-confirmed operation that protects user edits; D9).
- Cost ceilings and preview format for any future extraction run.

**No implementation, new permission, persistent schema, background ingestion or constitutional amendment is authorized by this document.**

## Revision notes

**Founder approval** (2026-10-21; status and decision metadata only, no technical change): the Status line, §11 SB-0, §12.2 and §15 record the approval of D1–D14 and R1–R7 and the deferral of D15; §15.1 is the decision record.

**Revision 4** (2026-10-20; [remediation record](../reviews/2026-10-20-codex-audit-remediation.md#founder-simplification-and-codex-n1n4)) applies the founder's simplification and aligns with PR #4 at `da52ce9`:

- **Obsidian is a snapshot viewer:** the export is a one-shot, user-requested ZIP or new folder, verified before it is offered; the managed projection of revision 3 — registry, write-lock fence, ownership hashes, automatic Forget reconciliation — is removed (§3, §7, §9, §14; D8, D9 and D14 settled). Canonical Forget, evidence and Context Compiler contracts are unchanged.
- **§4 invariant 5** is narrowed to the stores Sovereign manages; exports and their staging are bounded by their snapshot, and that boundary is disclosed.
- **Codex N1–N4:** N1 (multi-version ownership recovery) no longer applies; N2 (crash atomicity, generation consistency) is resolved by not claiming either, while failed or interrupted exports are never reported as complete; N3 (excluded-ID leakage) by typed structural verification instead of free-text scanning; N4 by a 140-byte UTF-8 basename limit that accounts for the handle and `.md`.
- **PR #4:** R1 corrected — no production retrieval change is authorized; Porter and the exact-stem tie-break are evaluated candidates only. Navigation (10 of 22 misses discoverable) and the provenance-admission counterfactual recorded; unchanged-vault token stability is now measured; PR #4's Codex P2 is resolved.
- **Storage integrity:** the pre-existing hidden-rowid replacement defect (SECURITY-GATE) is a high-priority Tier 2 repair required before production SB-2.

**Revision 3** (2026-10-20; [remediation record](../reviews/2026-10-20-codex-audit-remediation.md)) resolves the Codex architecture audit and reconciles with PR #4:

- **F1:** this branch now contains `main` (merge of `4fbecbe`, including `cee2c66` and its three regression tests) and targets `main`.
- **F2:** export publication is fenced by the vault write lock, registered before writing, and reconciled whenever the vault's tombstone state changes; projection spec §11. *(Superseded in revision 4 by the snapshot export.)*
- **F3:** inert serialization contract and adversarial tests; projection spec §6–§7, validation spec §4.2. Hardened by an independent red-team (45 attacks, several reproduced with Markdown parsers): escape instead of normalize, normalization-proof fences, top-level blocks only, closed value classes for times and IDs, plugin-syntax neutralization, tag-anchored graph groups, root and symlink guards.
- **F4:** authorized set before edges, non-identifying partial-provenance wording; projection spec §8, validation spec §4.3. Hardened by an independent red-team (37 leak vectors): OUT as one class, held slots only, no composed edges, verified evidence only, keyed per-projection handles, no raw IDs (D13), no per-note run stamps, a registry without paths or titles, label and closed modes (D12), and a byte-stability invariant. *(Registry and per-projection handles superseded in revision 4: no persistent state, per-export handles.)*
- **F5:** Benchmark 0003 (PR #4) is the retrieval oracle; what it does not measure is stated as NOT MEASURED; PR #3's draft benchmark became the validation spec.
- **F6:** Animate is file-creation order, not history.
- Reflected the founder's intended retrieval positions R1–R7 as pending; SB-1, SB-4, SB-5 and SB-8 updated accordingly; FTS5 and vectors moved to deferred rows; added founder decisions D12–D15.

**Revision 2** (independent review, 2026-10-19; [review record](../reviews/2026-10-19-second-brain-architecture-review.md)) changed revision 1 (`bae766e`): state-class table and MemoryClaim-based relationships; the missing canonical basis for projects, concepts and decisions; the concrete compiler policy changes L3/L4 require; Forget per representation; correction vs change; corrected Obsidian capabilities and a dedicated projection spec; one delivery numbering and decisions D1–D11.
