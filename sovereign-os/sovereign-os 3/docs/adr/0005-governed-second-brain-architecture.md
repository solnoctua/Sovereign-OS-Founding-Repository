# ADR-0005 — Governed Second Brain: Level 3–4 Retrieval, Knowledge Graphs and Obsidian Views

- **Status:** PROPOSED — architecture direction for founder review; not ratified, not implemented. Revision 3 (2026-10-20) resolves the Codex architecture audit (F1–F6) and reconciles with Benchmark 0003 (PR #4); see [*Revision notes*](#revision-notes).
- **Date:** 2026-10-20 (revision 3; first proposed 2026-10-19)
- **Decision owner:** Human project owner
- **Review tier:** Tier 3 direction. Every implementation slice that changes schema, memory authority, deletion, retrieval relevance or disclosure is separately Tier 2 (see `AGENTS.md`, `docs/DEVELOPMENT.md`).
- **Builds on:** [ADR-0003](0003-memory-claim-authority.md) (MemoryClaim authority) and [ADR-0004](0004-governed-retrieval-context-compiler.md) (Context Compiler) **as merged to `main`** (`4fbecbe`, including `cee2c66`, the policy-state truncation fingerprint, which this branch now contains). This ADR amends neither; §6, §7, §8.2–§8.3 and D15 name where a later slice would have to.
- **Read alongside:** [Second-brain levels guide](../second-brain/LEVELS-AND-OBSIDIAN.md), [Obsidian projection spec](../second-brain/OBSIDIAN-PROJECTION.md), [Second-brain validation spec](../second-brain/SECOND-BRAIN-VALIDATION.md), [Architecture](../../ARCHITECTURE.md), [Roadmap §G](../../ROADMAP.md). Retrieval evaluation: Benchmark 0003, `docs/benchmarks/0003-retrieval-evaluation.md`, delivered by [PR #4](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/pull/4) and **not yet merged**.
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
- **Snapshot vs live:** a materialized view (Obsidian) shows state as of its generation; Sovereign's live state is authoritative.
- **Graph display vs graph reasoning:** a visual network is UI. Graph traversal used for answers must be benchmarked and governed separately (§6).

## 3. State classes and authority

The second brain adds representations; it must not blur which ones carry authority. Every artifact belongs to exactly one class:

| # | Class | Examples | Authority | Written by | On Forget | Export/restore | Reaches a model |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Source evidence** (canonical) | `records` | Evidence, not belief | Human capture/import | Tombstone trigger (ADR-0003) | Exported | As `evidence`, via the compiler |
| 2 | **Claims and decisions** (canonical) | `claims`, `claim_sources`, `claim_events` | Only `approved` + `supported` is approved memory | Humans decide; a model may only *propose* (`origin = model`, reserved by ADR-0003) | Forgotten with any cited record | Exported | As `approved_memory`, via the compiler |
| 3 | **Human-declared organization** (canonical, *proposed — does not exist yet*) | Projects, concepts, membership of records/claims | Organizational, not a truth claim | Human | Membership removed with its member; entity Forget cascades (§7) | Exported (new schema, SB-3) | Not until its own ADR |
| 4 | **Deterministic derived structure** | The provenance graph (computed on read); any future index | None | Sovereign code; rebuildable | Nothing stored, or same transaction (§7) | **Not** exported; rebuilt | Never directly — candidate IDs only |
| 5 | **Rendered external projections** | Obsidian Markdown vault | None; a dated snapshot | Exporter CLI | Fenced publication + reconciliation (§9, projection spec §11) | Not a backup | Never |
| 6 | **Projection registry** (operational, non-canonical) | Registered roots, manifests, reconciliation counters | None | Exporter and Forget cleanup | Entries for forgotten items removed by reconciliation | Not exported; per installation | Never |
| 7 | **Working context** | ContextBundle, query text | Request-scoped | Compiler | Never persisted | — | Only the exact approved bundle |

Consequences:

- **Model-proposed relationships, entities or summaries are not disposable projections.** A model run is not reproducible, costs money, and a human review of its output is a *decision*. If persisted, they are class 2: MemoryClaims with `origin = model`, created `proposed`. If not persisted, they are class 7 and vanish.
- **A typed factual relationship is a MemoryClaim with a structured form, not a new lifecycle** (decision D3). A separate `review_state` would duplicate `claims.status`, its history, its Forget cascade and its import/restore rules.
- **Deterministic provenance edges are structural, not claims.** `SUPPORTED_BY`, `CORRECTS` and `SUPERSEDES` are facts Sovereign already stores; they need no redundant claim about themselves.
- **Projects, concepts, decisions and multi-record documents do not exist in the canonical schema.** Records hold `content, source, sensitivity, status, created_at, supersedes_id`; claims hold text, origin, status, lineage and source links. Hubs in Obsidian, project pages in an L2 wiki and "summarize the whole meeting" all need class 3 first (D2), through a separately reviewed data model. Until then a projection can honestly show only sources, claims, revisions and decision histories.
- **Immutability makes derived structure simple.** Record and claim IDs are insert-only and their content immutable (ADR-0003), so anything keyed by ID can become *existence*-stale (forgotten) but never *content*-stale. Claim status and support are always read live, never from a derived copy.

## 4. Invariants

1. **One system of record.** Records, MemoryClaims, decision histories, tombstones and (once approved) human-declared organization live in the local vault. No Markdown export, index, entity table, LLM summary or external graph store becomes a competing system of record.
2. **Retrieval ≠ authority ≠ disclosure ≠ inference ≠ action.** Retrievers and graph traversal propose candidate canonical IDs. The compiler hydrates them from one snapshot, applies authority, sensitivity, relevance and budget, and builds the disclosure plan. Models and adapters never read the vault or widen their own disclosure.
3. **Approved memory means approved and supported.** Only `claims.is_authoritative` items may appear as approved memory — including structured relation claims. An edge never inherits approval from the claims or sources that support it.
4. **Exact-plan consent survives every retrieval change.** Preview and execution use the same compiler; a new retrieval method enters only with a new `policy_version`, and the token keeps binding the complete policy-relevant retrieval state (§6.3). Nothing is appended after approval.
5. **Forget reaches every derived representation** without resurrection through rebuild, restore, stale materialization or a concurrent export; tombstones dominate; whatever cannot be guaranteed is disclosed, never concealed (§7, §9).
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
          +--> one-way Obsidian projection, CLI, fenced against Forget      [SB-2]
                 (registry beside the vault; files outside any Git tree)
```

**Candidate contract (sketch, not a frozen schema).** If a second retrieval method is ever added, generalize ADR-0004's `RetrievalCandidate.via` from one value (`pinned | lexical | provenance`) to the set of methods that surfaced the item. `Vault.context_candidates` remains the **single read snapshot** that runs in-vault retrieval and hydrates the hits. Any retriever's derived state lives inside the vault transaction (D6), so Forget reaches it atomically and its candidate universe is bound by the fingerprint; a store outside the vault would need its own §7 row and fenced, reported Forget before it could be considered. Dropping unknown or forgotten IDs at hydration is defense in depth, never the Forget mechanism.

**Routing.** Choose methods deterministically and inspectably: exact lookup for IDs and dates, timeline ordering for "what changed", whole-record access for "the entire note", graph traversal only for local exploration. No model constructs SQL or graph queries, and no cloud model is used to route, rewrite or expand a question (§6.7).

## 6. Integration with the Context Compiler — what L3/L4 actually change

New retrieval methods are **not** drop-in candidate providers. Against the merged ADR-0004, each point below is a **compiler policy change** requiring a new `policy_version`, tests in the adversarial suite, a regenerated Benchmark 0003, Tier 2 review and founder approval. Benchmark 0003 (PR #4) has now measured the cheap lexical alternatives; the evidence and the founder's intended positions are in §12.

1. **Relevance gate.** ADR-0004 excludes any unpinned candidate sharing no question term as `not_relevant`. An embedding hit with zero lexical overlap — exactly what L3 exists to find — is therefore discarded today. Changing the gate is a **disclosure change**: ADR-0004 decision 1 lets *relevant* unpinned private items enter an approved cloud plan, so a higher-recall retriever is also a wider-disclosure retriever. Benchmark 0003 shows the effect even lexically: Porter normalization recovers 2 more expected items and admits 47 more irrelevant ones.
2. **Ranking.** Today's order is pinned → claims → evidence, then matched-term count, recency, ID; its recency tie-break is an implicit temporal prior. Weighted ranking (IDF, BM25) is **deferred** (R2): in Benchmark 0003 it invalidates 51–54 of 56 pending previews after one unrelated write, and BM25 loses the recency prior (temporal MRR 0.733 → 0.473). Any future weighted or fused ranking is evaluated in the Benchmark 0003 harness first.
3. **Truncation fingerprint — not to be weakened.** Since `cee2c66`, an approval binds the policy-relevant state of the **complete relevant candidate universe**, including candidates below the cutoff. It must not be weakened for performance or convenience (R2). Weighted scores that change after unrelated writes would make previews stale. That is fail-closed (409, re-preview), and under R2 (pending) it is preferred to weakening the fingerprint, but it reverses ADR-0004's statement that irrelevant vault changes do not invalidate an approval. Adopting weighted scores under either option of PR #4's decision 2 (accept that writes stale previews, or bind an order-preserving projection) therefore needs an ADR-0004 amendment. Pending (R2). A *policy-equivalent fingerprint* that ignores numerical score changes is a research question only: a score change could be ignored **only if** equivalence of every protected decision is demonstrated — full relevant candidate membership including below-cutoff matches; policy-relevant ordering and cutoff membership; authority, status, support and sensitivity; eligibility and inclusion/exclusion decisions; exact outbound content and disclosure policy. It would need an ADR-0004 amendment, independent adversarial review and explicit founder approval. **It is not proposed here.** A semantic retriever, if ever adopted, must define its relevant universe as crisply as lexical matching does (an exact scan, not approximate nearest neighbors).
4. **Determinism.** Any retriever must keep token stability on an unchanged vault at 100%: the same vault state and question always give the same token. This is not Benchmark 0003's unrelated-write metric, which weighted scoring is expected to fail (§6.3), and the Benchmark 0003 harness does not yet report it (validation spec §2). A runtime that cannot meet it keeps that retriever local-only. Query text and query vectors are never persisted.
5. **Provenance and graph-reached candidates.** ADR-0004 decision 3 keeps claims reached only through provenance `not_relevant`, and **that conservative exclusion is preserved** (R3). Claim-source and supersession links are valuable for deterministic, local navigation in the UI and Obsidian (SB-2), but traversal must never by itself make a connected record or claim relevant for any model context, local or cloud; even a local-only expansion is a change to ADR-0004 decision 3 with its own `policy_version`. Benchmark 0003's one-hop provenance retriever (74/88: +5 over the FTS5 Porter BM25 retriever it extends, +8 over baseline; not measured over the baseline or Porter scorer) is a diagnostic, not a proposal; any expansion needs an independent evaluation, starting local-only, and a founder decision (D5).
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
| Obsidian projection | User-chosen folder, **outside** the vault transaction | Reconciled under the export fence: owned files of forgotten items deleted, notes that named them rewritten; pending until done (§9) | Picked up by the next user-run export; reconciliation never adds the new revision | Fully regenerable; never a backup |
| Projection registry | Beside the vault, never inside the projection | Entries of forgotten items marked `delete_pending`; a forgotten item's handle and file hash are kept only until its file is deleted; never a path, title, raw ID or content | — | Not exported |
| Future FTS5 index (deferred, R2) | Vault DB, maintained by triggers | Same transaction. Requires FTS5 `secure-delete` (SQLite ≥ 3.42); without it deleted terms persist in index segments — reproduced during review even with `PRAGMA secure_delete` on — so refuse to enable the index | New revision indexed on insert | Rebuilt; not exported |
| Future vectors (deferred, R6) | Vault DB, keyed by ID + retriever identity | Same transaction. Vectors are treated as content (published embedding-inversion work recovers much of the input text) | As above | Re-embed; not exported |
| Copies Sovereign does not control | Obsidian caches and file-recovery snapshots, trash folders, OS backups and search indexes, sync services, plugins | Cannot be guaranteed | — | Disclosed in the Forget preview and result |

- The Forget preview counts the projection files a Forget would delete or rewrite, per registered projection, as of the preview; the canonical confirmation token (ADR-0003) does not bind projection state, so an export between preview and confirmation can change that count. The result reports the actual cleanup state. Exports are never transactional with SQLite; §9 defines how they are fenced and reconciled instead.
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
- **People and third parties:** entities about other people are sensitive by default (Constitution Art. VI.3–VI.4) and excluded from default projection scope. Keeping a relation claim that names such an entity out of cloud plans needs **entity-aware sensitivity**: a structured claim inherits the most restrictive sensitivity of its cited evidence *and* of every entity it names. That is an ADR-0004 amendment (sensitivity inheritance and the fingerprint's policy state) with a `policy_version` bump, decided with SB-3/SB-7, not assumed here.
- **Contradictions** surface as `contested` claims; nothing silently chooses a winner (Art. IV.3). A typed `CONTRADICTS` relation between two claims would need claim-valued endpoints, which the structured form above does not have, and a Forget rule that forgets the relation when either endpoint claim is forgotten (an ADR-0003 trigger amendment); it is deferred until both are designed.

### 8.3 Temporal semantics

Sovereign has two clocks today: **stored time** (`records.created_at`, set at capture or carried in by ordinary import and trusted restore, so not proof of when something was captured) and **decision time** (`claim_events.at`, which trusted restore also carries in from the backup). It has no **valid time** — when a proposition held in the world. Two different situations both end in `superseded`:

- **Correction:** the capture or interpretation was wrong (a record corrected through `supersedes_id`, or a claim superseded because it was mistaken).
- **Change:** it was true and stopped being true (a project decision reversed).

Until **D10** is resolved, every local view (Timeline, decision histories, the Obsidian projection) treats `superseded` as *"no longer the current approved interpretation"*, never as *"was false"*, and shows stored and decision times rather than inventing validity intervals. Model prompts cannot answer "then vs now" through the governed path today: ADR-0004 never sends superseded claims and sends no decision times for approved memory, so prompt-level temporal answers would need an ADR-0004 prompt-boundary change with its own `policy_version`. Recommendation: before typed relations are persisted, extend MemoryClaim with optional `valid_from`/`valid_until` and a supersession reason (`correction | change`) — the established bitemporal model (valid time vs record time) — through its own ADR-0003 extension.

## 9. Obsidian — a first-class optional visual client

**Requirement:** the user can open a Sovereign-generated vault in Obsidian, see a meaningful Graph view and Local graph, follow projects, concepts, sources, claims and decisions, and find out from the notes *why* any line exists and *when* things changed. This is an acceptance requirement, not decoration. The full contract is in the [Obsidian projection spec](../second-brain/OBSIDIAN-PROJECTION.md); its tests are in the [validation spec](../second-brain/SECOND-BRAIN-VALIDATION.md) §4. The rules that bind the architecture:

- **Local, opt-in, one-way, CLI-generated.** No HTTP endpoint writes files to a caller-chosen path (V0 has no authentication). Output goes to a user-chosen folder outside any Git working tree; the exporter only creates, rewrites or deletes files it owns.
- **Export is fenced against Forget (Codex F2).** An export or reconciliation run takes the vault's write lock (`BEGIN IMMEDIATE`, which every canonical mutation also needs) and holds it from its snapshot read until its last file operation and directory sync. Inside that critical section — the run's **linearization point** — it registers itself before writing any file, verifies which recorded hash each file on disk matches, self-checks the rendered output, publishes, and only then records the new state. A Forget, claim Forget or trusted restore commits either before the run (and is not in its snapshot) or after it (and then marks the forgotten entries and triggers reconciliation, which only deletes and rewrites, never adds). Pending cleanup is derived from durable state — registry entry states and the vault's append-only tombstone tables (their counts and a keyed fingerprint of their insertion-ordered prefix), so any new tombstone, including a raw-SQL one, triggers reconciliation and a replaced or older vault is flagged — so no separate outbox is needed. The registry lives beside the vault, never in the projection, and holds no item's path, title, raw ID or content: per item only a handle and hashes, per projection its root, vault path, key, scope and counters; the exporter deletes only files it can prove it wrote, and reports files edited outside Sovereign instead of touching them. Filesystem writes are **not** atomic with SQLite; the guarantee is ordering plus reported, eventual reconciliation, and the exact protocol, crash recovery and residual limits are in projection spec §11.
- **Untrusted text is inert (Codex F3).** Every stored value is untrusted for rendering, whatever path it arrived by — including times, source labels and IDs, which ordinary import and trusted restore can set to arbitrary text. Free text is escaped (never Unicode-normalized, since normalization can manufacture backticks) and emitted only as its own top-level fenced `text` block whose fence is unclosable under every normalization form, with plugin syntaxes neutralized. Times appear only after a strict parse; raw IDs are not written (D13); titles pass a Unicode-category whitelist; filenames carry keyed per-projection handles; frontmatter values are escape-free by construction; links, tags and callouts are generated only from the authorized canonical relationship set. A blockquote alone is insufficient. Parser-based and native Obsidian tests, including a zero-unauthorized-network-request test, are acceptance gates.
- **Scope is closed before edges are built (Codex F4).** The authorized set is computed first, inside the export fence, from the confirmed class-level scope; a link is emitted only for a slot the item itself holds whose other end is in the set, never composed across an omitted item, and `SUPPORTED_BY` only to evidence whose pinned hash still matches. Excluded, forgotten, missing and malformed endpoints are one class, so changes outside the set change no file. An item with an omitted slot carries one fixed, non-identifying sentence at a fixed position, or, in closed mode, is left out (D12); scope is never widened to complete a link; nothing excluded appears in a title, filename, handle, ID, folder, frontmatter, navigation note, metric, log or the registry.
- **Honest about Obsidian.** Graph lines are untyped links; Obsidian can show link *direction* (Arrows) but not edge labels, edge properties or validity. Node labels are filenames. Semantics, evidence and time live in note text under predicate-named headings — **one canonical relationship, one link, one explanation**.
- **Animate is not history (Codex F6).** Graph view's *Animate* shows notes in file-creation order on that disk. It does not replay stored times, corrections, supersessions or MemoryClaim status changes. Chronology comes from the Timeline note and each claim's decision history; no animation engine is planned.
- **A snapshot, labeled as such.** Every note's banner states that Sovereign is authoritative; Start Here states the generation and date; statuses are as of export, never "live". Item notes carry no per-run stamp, so an unchanged item's file stays byte-identical across runs.
- **Shows only what is canonical.** Today: sources, claims, revisions, decision histories and their links. Project/concept hubs require SB-3; typed relations require SB-7; validity intervals require SB-6. Unreviewed model proposals are excluded from the default scope.
- **Private by default.** Sensitive items excluded unless explicitly included; an opaque-filename mode exists (D7); no plugin is required; sync and plugins are the user's explicit choice and are warned about. Edits made in Obsidian are never imported.

The [synthetic demo vault](../second-brain/obsidian-demo-vault/) shows the target, including an inert adversarial note, a partial-provenance note and future-only elements clearly marked.

## 10. Cost, cadence and Level 5

**Near term (L3–L4):** deterministic local retrieval, a computed provenance graph, manual exports. **No recurring model bill is needed to keep the brain usable.** Paid calls happen only through the existing approved request path, or through a future capped extraction workflow with its own ADR, disclosure design and per-run cost preview.

**Level 5:** periodic sync, proactive conflict detection, live connectors, agent coordination. Revisit only when daily utility, security and recovery, explicit user and bystander consent, provider limits and a **measured monthly cost and energy budget** justify it. Always-on is not a permission or retention policy. Local reconciliation after a Forget and a user-run export are **not** Level 5. Future connectors are queried at use time when authorized; copying their content into the vault is capture, with provenance, consent and retention.

**Long horizon.** Far more capable models and very long contexts may make some retrieval unnecessary *for capability*; they do not make it unnecessary *for disclosure*. Art. VI.2 still forbids sending the life history because a model could read it. The durable value is the canonical state plus governance; retrieval methods stay replaceable behind the candidate contract, and the compiler stays the single choke point — including for future agentic retrieval, where a model may propose queries but never decides disclosure. Benchmark optimization does not dictate this architecture: the goal is trustworthy lifelong knowledge continuity, not a synthetic recall score.

## 11. Delivery slices

Deliberately small first; one numbering (also ROADMAP §G):

| Slice | Delivers | Level | State / gate |
| --- | --- | --- | --- |
| **SB-0** | This ADR, guide, projection spec, validation spec, demo vault (docs only; PR #3) | — | Founder decisions D1–D15 |
| **SB-1** | Benchmark 0003 retrieval evaluation: synthetic corpus, harness, governed-recall/noise/precision baseline and lexical alternatives | L3 evaluation | **Executed in PR #4, not merged**; Codex P2 (scale timings) open there; founder decisions R1–R7 pending |
| **SB-2** | Provenance graph computed on read (local navigation only) + one-way Obsidian projection CLI for sources, claims, revisions and histories, with registry, export fence, inert serialization, scope closure and Forget reconciliation. No canonical schema change (given D14's recommended separate registry file). **First user-visible slice** | L2 view + L4 provenance | Tier 2 (deletion reaches an external store); validation spec §3–§4 |
| **SB-3** | Human-declared projects/concepts and membership; projection hubs | L1/L2 | Tier 2 schema ADR; D2 |
| **SB-4** | Porter normalization of the existing distinct-term score, with a `POLICY_VERSION` bump and regenerated Benchmark 0003 — **only if R1 is approved**, with its precision cost stated. The stemmer implementation (PR #4's decision 1, which includes a transient in-memory FTS5 `porter` tokenizer) is chosen in that PR. IDF, BM25 and any persistent FTS5 index deferred (R2) | L3 lexical | Separate Tier 2 PR |
| **SB-5** | Local embeddings — **deferred** until representative, legitimate usage shows meaningful improvement over deterministic retrieval (R6) | L3 semantic | Tier 2; D4, D11 |
| **SB-6** | Temporal claim extension: valid time, supersession reason | L4 prerequisite | Tier 2; D10 |
| **SB-7** | Typed relations as structured MemoryClaims; human-authored first, model-proposed after an extraction ADR | L4 domain | Tier 2/3; D3 |
| **SB-8** | Graph- or provenance-assisted context — **deferred**; local-only exploration and an independent evaluation first (R3) | L4 retrieval | Tier 2; D5 |
| **SB-9** | Level 5 research only | L5 | §10 gates |

These slices complement, and never displace, M0–M5. Security, recovery and daily capture remain prerequisites for real data; a graph visualization must not delay them.

## 12. Evidence and evaluation

### 12.1 Benchmark 0003 (PR #4) — executed, not merged

Benchmark 0003 is the canonical retrieval evaluation (subject to its own audit and merge). It evaluates the merged Context Compiler on a synthetic corpus of 254 records, 16 claims and 56 queries with an explicit, policy-validated oracle; it measures retrieval before policy and governed context after policy, for local and cloud targets; no provider is called. Results for locally eligible expected items (88):

| Approach | Recalled | Noise | Previews invalidated by an unrelated write |
| --- | ---: | ---: | ---: |
| Current baseline | 66/88 | 166 | 0/56 |
| Porter normalization | 68/88 | 213 | 0/56 |
| Porter + IDF | 69/88 | 212 | 53/56 |
| FTS5 Porter BM25 | 69/88 | 212 | 53/56 |

- **What it establishes and does not:** see the validation spec §2. Generated-answer correctness, abstention and temporal interpretation are **NOT MEASURED**. No query lacks a relevant item; six queries whose expected items are all `sensitive_cloud` already show what a cloud plan offers when no expected item is disclosable (22 noise items across them under the baseline, 33 under Porter normalization), but questions with no relevant item at all are not measured.
- **Review dependency:** Codex P2 on PR #4 found that the indicative scale timings in its finding 8 have no reproducible generation path. They must be made reproducible and qualified, or removed from its evidence, **on PR #4**. This ADR relies on none of them, and incidental container timings are not a capacity guarantee.

### 12.2 Founder's intended retrieval positions — pending formal approval

These positions follow from Benchmark 0003 and are reflected throughout this ADR. None is ratified; each needs the founder's formal approval, and implementing any of them is a separate reviewed PR — never PR #3.

| ID | Position (intended, pending) | Where reflected |
| --- | --- | --- |
| **R1** | Favor Option B narrowly: Porter normalization as a separate Tier 2 implementation with a policy-version bump. Not an unconditional improvement: +2 expected items, +47 irrelevant items. | §6.1, SB-4 |
| **R2** | Defer IDF/BM25. Do not weaken the fingerprint for performance or convenience; a policy-equivalent fingerprint is future research needing demonstrated equivalence of every protected decision (§6.3), an ADR-0004 amendment, independent adversarial review and founder approval. | §6.2–6.3 |
| **R3** | Provenance links serve deterministic local navigation; traversal never automatically makes items relevant for any model context, local or cloud; ADR-0004 decision 3 preserved. | §6.5, §8.1, SB-8, D5 |
| **R4** | Retrieval precision is a priority, especially for cloud; floors, thresholds or cloud-specific policies need separate evaluation and versioned approval. | §6.8 |
| **R5** | Keep the 12-item and 12,000-character budgets. | §6.6 |
| **R6** | Defer local embeddings until representative, legitimate usage shows meaningful improvement; no sensitive personal notes while the Security Gate is NOT PASSED. | SB-5, D4, D11 |
| **R7** | Keep PR #4's synthetic framework, reproducibility discipline, policy-eligibility checks and regression comparisons; resolve its own findings in PR #4. | §12.1, validation spec §1 |

PR #4 also lists decisions R1–R7 do not settle: the stemmer implementation (its decision 1, left to the SB-4 PR), whether to accept stale previews or bind an order-preserving projection under weighted scores (its decision 2, an ADR-0004 amendment either way, §6.3), and a private, never-committed founder-run evaluation on real notes with a harness that reads a corpus from a path (its decision 6, which stays open and subject to the Security Gate).

### 12.3 Gates

A better retrieval score never compensates for a broken invariant. **Must-pass (zero tolerance):** no unauthorized promotion; no forgotten content in any store or registered projection after reconciliation (canary scan); no unauthorized network request from a projection; no sensitive egress; no candidate, vector or graph content outside the approved preview; identical tokens for an unchanged vault; no third-party sync of personal graph data without an explicit action; canonical export/restore unchanged. Loopback serving is not authentication. The security gate remains **NOT PASSED**: synthetic or intentionally non-sensitive data only.

### 12.4 Evaluation state (as of 2026-10-20; mirrors validation spec §1)

1. **Retrieval evaluation (SB-1):** Benchmark 0003, executed in PR #4, **not merged**.
2. **Provenance graph tests (SB-2, validation spec §3):** specified, **not implemented**.
3. **Safe Obsidian exporter tests (SB-2, validation spec §4):** specified, **not implemented**; no native Obsidian check has been executed.
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
- An outbox table for exports: **not needed** — the export fence plus registry entry states and the tombstone counts and prefix fingerprint give the same guarantees with less state (§9). Reconciliation is a trigger-driven check of those durable states, not a separate queue.
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
| **D7** | Obsidian filenames: readable titles or opaque handles | `Readable title (handle).md`, where the handle is the keyed per-projection handle (§9, D13), for private items in scope; opaque mode `<handle>.md` available; sensitive items excluded by default |
| **D8** | Obsidian cleanup on Forget | Automatic reconciliation of registered projections under the export fence; pending state shown; residual copies disclosed |
| **D9** | When projections are rebuilt | Manual CLI run only; no scheduled rebuilds. Reconciliation (which only deletes and rewrites) runs after every Forget or trusted restore, at start-up, before every export or status command, and periodically while Sovereign runs (projection spec §11.4) |
| **D10** | Temporal claim semantics | Add valid time and supersession reason (correction vs change) before SB-7 |
| **D11** | Local embedding model, runtime and dependency | Not now (R6); choose only after representative usage justifies it; pin by file hash; new dependency review |
| **D12** | Default Obsidian provenance mode | *Label* mode (one fixed partial sentence) for local browsing; *closed* mode (drop items with omitted links) recommended for removable, synced or shared exports |
| **D13** | Raw canonical IDs in projected notes | None: the keyed handle only. Even canonical-UUID IDs can be enumerable (ordinary import derives claim IDs with a public UUIDv5 namespace), so a raw ID could reveal a gap where an excluded item sits |
| **D14** | Projection registry placement | A separate SQLite file beside the vault (no schema change; a crash between a Forget commit and the registry marking is caught by the next reconciliation trigger), rather than an operational table inside the vault DB |
| **D15** | Lineage sensitivity of claims: a private claim that supersedes a sensitive claim often restates it | Decide in the Context Compiler (an ADR-0004 amendment, Tier 2), because the same text is eligible for cloud plans today; the projection only warns until then |

R1–R7 (§12.2) are separate intended positions awaiting the founder's formal approval.

## 16. Open engineering questions (no founder decision needed yet)

- Calibration and form of any relevance floor (R4), and how a narrower cloud policy is versioned.
- Export format version for class-3 organization and its import/restore authority rules.
- Projection scope language (by project, date range, status) and how a scope is previewed.
- Bounding run duration under the write-lock fence for large vaults, and whether opening the vault should stop taking the write lock when no migration is needed (projection spec §11.2, §11.6).
- Cost ceilings and preview format for any future extraction run.

**No implementation, new permission, persistent schema, background ingestion or constitutional amendment is authorized by this document.**

## Revision notes

**Revision 3** (2026-10-20; [remediation record](../reviews/2026-10-20-codex-audit-remediation.md)) resolves the Codex architecture audit and reconciles with PR #4:

- **F1:** this branch now contains `main` (merge of `4fbecbe`, including `cee2c66` and its three regression tests) and targets `main`.
- **F2:** export publication is fenced by the vault write lock, registered before writing, and reconciled whenever the vault's tombstone state changes; projection spec §11.
- **F3:** inert serialization contract and adversarial tests; projection spec §6–§7, validation spec §4.2. Hardened by an independent red-team (45 attacks, several reproduced with Markdown parsers): escape instead of normalize, normalization-proof fences, top-level blocks only, closed value classes for times and IDs, plugin-syntax neutralization, tag-anchored graph groups, root and symlink guards.
- **F4:** authorized set before edges, non-identifying partial-provenance wording; projection spec §8, validation spec §4.3. Hardened by an independent red-team (37 leak vectors): OUT as one class, held slots only, no composed edges, verified evidence only, keyed per-projection handles, no raw IDs (D13), no per-note run stamps, a registry without paths or titles, label and closed modes (D12), and a byte-stability invariant.
- **F5:** Benchmark 0003 (PR #4) is the retrieval oracle; what it does not measure is stated as NOT MEASURED; PR #3's draft benchmark became the validation spec.
- **F6:** Animate is file-creation order, not history.
- Reflected the founder's intended retrieval positions R1–R7 as pending; SB-1, SB-4, SB-5 and SB-8 updated accordingly; FTS5 and vectors moved to deferred rows; added founder decisions D12–D15.

**Revision 2** (independent review, 2026-10-19; [review record](../reviews/2026-10-19-second-brain-architecture-review.md)) changed revision 1 (`bae766e`): state-class table and MemoryClaim-based relationships; the missing canonical basis for projects, concepts and decisions; the concrete compiler policy changes L3/L4 require; Forget per representation; correction vs change; corrected Obsidian capabilities and a dedicated projection spec; one delivery numbering and decisions D1–D11.
