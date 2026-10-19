# ADR-0005 — Governed Second Brain: Level 3–4 Retrieval, Knowledge Graphs and Obsidian Views

- **Status:** PROPOSED — architecture direction for founder review; not ratified or implemented
- **Date:** 2026-10-19
- **Decision owner:** Human project owner
- **Review tier:** Tier 3 direction; implementation affecting security, schema, memory authority or disclosure requires a separate Tier 2+ review
- **Read alongside:** [Second-Brain Levels and Obsidian Design](../second-brain/LEVELS-AND-OBSIDIAN.md), [Architecture](../../ARCHITECTURE.md), [Roadmap](../../ROADMAP.md), [Benchmark 0003](../benchmarks/0003-second-brain-retrieval-evaluation.md), ADR-0003 and ADR-0004
- **Constitution:** subordinate to the proposed Constitution; no constitutional text is amended or ratified by this document

## 1. Problem and mission

Sovereign is a long-lived, local-first personal intelligence environment. A file search alone cannot reliably reconstruct ideas expressed in different words, relationships between months-old projects, what changed in an earlier decision, or why a memory is believed. A useful second brain must organize, find, relate, explain and correct knowledge while increasing the person's independent understanding.

**Decision proposed:** extend the already-planned Sovereign Brain with **Level 3 semantic/hybrid discovery plus Level 4 typed, source-backed relationship exploration**, retaining Level 1 structured files and Level 2 linked wikis as complementary human-facing representations. **Level 5 continuous intelligence is a long-term possibility, not a present requirement.**

The underlying video supplied a *heuristic*, not an industry standard or maturity certification: use the least complex knowledge structure that answers real questions reliably. Sovereign's authority, privacy, retention, correction and action boundaries are **orthogonal** to all five levels; a Level 4 graph is not inherently safer, more truthful or more advanced than a Level 2 wiki.

## 2. Five-level vocabulary — required context for all builders

| Level | Name and mechanism | Suitable retrieval/task | Characteristic failure | Sovereign role |
| --- | --- | --- | --- | --- |
| **L1** | **Structured files and routing.** Markdown, folders, indexes and agent instruction files tell humans/agents where information lives. | Known project/document, stable instructions, direct inspection. | Misses information if route/name unknown; duplicated or stale instructions. | Keep transparent repository docs and optional readable projections. |
| **L2** | **Linked wiki and curated memory.** Concept notes, indexes, backlinks and crosslinks; Obsidian graph normally shows note-to-note links. | Navigate topics, synthesize project context, browse transcripts. | A backlink is not a typed or trustworthy relationship; AI-authored summaries may distort sources. | Generated knowledge pages with links to canonical evidence; not another authoritative memory.md. |
| **L3** | **Semantic/hybrid retrieval.** Chunking and embeddings find conceptually similar material; combine with exact/lexical/full-document/temporal lookups and reranking as warranted. | Paraphrased questions across many notes, discovery across projects. | Top-k chunks omit document-wide context; near meaning is not factual equality; stale vectors. | Primary near-term discovery upgrade, evaluated against baseline. |
| **L4** | **Typed evidence-backed knowledge graph.** Entities and relationships such as DEPENDS_ON, CONTRADICTS, SUPERSEDES, SUPPORTED_BY; optionally graph-assisted retrieval. | Multi-hop connections, provenance inspection, longitudinal decisions, cross-project dependencies. | False extraction, identity collisions, stale edges, confusing visual density, accidental authority laundering. | Provenance graph first, domain relationship pilot later; visual Obsidian/native explorer. |
| **L5** | **Continuously maintained cognitive environment.** Scheduled ingestion, live connectors, updates, agents and selective consolidation. | Periodic changes, proactive assistance and ongoing synchronization. | Recurring costs, over-collection, stale/compounding beliefs, sensitive data leakage and excessive autonomy. | **Deferred destination** with explicit permission, cost, security and benefit gates. |

The levels describe **techniques, not a ladder that every folder must climb**. One source may need a complete document view; another an index; a third a graph. Never vectorize all data by default or infer that a graph is always needed.

### Essential distinctions

- **Backlinks vs graph assertions:** an Obsidian `[[link]]` says that notes reference each other. It does not encode an enforceable predicate, truth, provenance or time. L4 needs typed, qualified relationships and evidence.
- **Similarity vs truth:** nearby embeddings mean semantically related, not "this exact record proves the proposition." Exact dates, rule numbers and maximum values need deterministic lookup/calculation.
- **Storage vs context:** retaining a source or generating a wiki/graph never promotes it to approved memory. Task context is temporary and purpose-limited.
- **Snapshot vs live:** immutable history and durable decisions differ from current operational app state. Live connectors are queried at use time when authorized; not copied wholesale into durable memory.
- **Graph display vs graph reasoning:** a visual network is optional UI. Graph traversal has to be benchmarked for improved answers.

## 3. Fit with Sovereign's existing architecture

Sovereign already separates **Source Records**, derived **MemoryClaims**, their **approval and support lifecycle**, **Context Compiler**, **ContextBundle**, and cloud **disclosure approval**. Preserve them.

**Invariants:**

1. **Canonical state:** records, MemoryClaims, corrections, claim histories, tombstones and governed permissions remain in the local vault. No Markdown export, FTS index, vector index, entity node, LLM summary or external graph store becomes a competing system of record.
2. **Retrieval ≠ authority ≠ disclosure ≠ inference ≠ action.** Retrievers propose *candidate canonical IDs*. The local compiler resolves current sources and support, applies authority, sensitivity, relevance, freshness and budget, and authorizes outbound context. Models and provider adapters never read the vault directly or expand their own disclosure.
3. **Approved memory:** only currently supported and approved MemoryClaims may appear as approved personal memory. Proposed/contested/rejected/stale claims may be shown for authorized local review, not silently embedded as approved facts in model context.
4. **Evidence is distinct:** active source records can be used as labeled evidence, not automatically as externally verified claims. Derived graph assertions do not inherit approval simply because a source is active.
5. **Exact-plan consent:** preview and execution use the same compiler and revalidation. Changes to relevant candidates, ranked truncation/metadata, index generations or the actual outbound content require documented versioned invalidation semantics. No extra graph/vector bytes, durable IDs or metadata are appended after approval.
6. **Forgetting:** a forgotten record, its dependent claims and their derived index/wiki/graph representations must disappear and not be resurrected through rebuild, restore or stale materialized export. Tombstones dominate. Incomplete deletion of external copies must be disclosed, never concealed.
7. **Privacy:** graph topology, existence of an entity, links, generated names, embeddings and labels can reveal sensitive information. Treat them as protected derived personal data. No implicit cloud embedding/indexing or public graph publishing.
8. **Portability:** indexes and rendering integrations are replaceable. Export of canonical state must not depend on a graph tool. Retrieval falls back to safe canonical/lexical behavior, never to a weaker security gate.

## 4. Component model

```text
Capture/import + deliberate authoring
          |
          v
  Canonical local vault
  Source records ── evidence hashes, revisions, Forget/tombstones
  MemoryClaims  ── approval decisions, source links, support-on-read
          |
          +--> rebuildable L1/L2 project/wiki markdown views
          +--> rebuildable L3 lexical/FTS and optional local vector indexes
          +--> rebuildable L4 provenance and typed graph projections
          |
Question -> retrieval planner (exact / lexical / semantic / full document / timeline / graph)
          -> candidate canonical IDs + local diagnostic metadata
          -> hydration/authorization from one consistent source snapshot
          -> Context Compiler (authority, sensitivity, relevance, budget, disclosure)
          -> ContextBundle + local explanation / exact cloud preview
          -> local evidence or separately approved provider
          |
          +--> optional LOCAL Obsidian projection (view only, never source of authority)
```

**Retrieval interface (design sketch, NOT a current API/schema):**

```text
CandidateHit {
  kind: source | claim,
  canonical_id,
  methods: [exact, lexical, semantic, graph, temporal, full_document],
  diagnostics,                 // bounded; local only
  projection_generation?,
  provenance_path_ids?         // local only
}
```

Return IDs and scores, not copied content as approved memory. Rehydrate and validate source identity, support, status and inherited sensitivity from the vault in a consistent read. Retrieved graph paths cannot independently enter a model prompt: resolve any underlying approved claim or evidence, then apply compiler policy. If a stale index is used, a missing or invalid canonical ID fails closed. Never persist context bundles or raw question text merely to enable second-brain features.

**Router policies:** choose exact search for IDs/numbers/dates; whole-document expansion for full meeting summaries; structured calculation for maxima and totals; temporal query for "what changed"; hybrid search for paraphrases; graph traversal for explicit multi-hop relationship questions. Start deterministic and inspectable. Allow multiple methods to contribute candidate IDs but do not allow the model to construct privileged SQL/graph queries or circumvent request filtering.

## 5. Two graph projections with different semantics

### A. Evidence/provenance graph — earliest useful graph

Derive *without LLM inference* from existing canonical facts:

- Nodes: source records and MemoryClaims. Display type, current lifecycle, sensitivity at local UI only, support state, dates when grounded.
- Edges: `CLAIM_SUPPORTED_BY_SOURCE` from claim_sources; `SOURCE_SUPERSEDES_SOURCE` from record lineage; `CLAIM_SUPERSEDES_CLAIM` from claim lineage.
- Every link resolves to the underlying canonical record. Use current status/support at read time; do not cache "approved" indefinitely.
- Forget of source removes dependent claim content and edges in projections. Backward revision walk and tombstones take precedence.
- UI: scope by a selected source/claim or search hit, small bounded number of hops; inspect evidence behind a link. Do not render the whole personal vault in one browser view.

This can initially be a read-only local graph response and optional Obsidian Markdown export; **no new authority lifecycle**.

### B. Domain knowledge graph — evaluated later

Entities: projects, companies, people, technologies, goals, decisions, arguments, research topics and events as warranted by tested queries. Relationship assertions might use `PART_OF`, `DEPENDS_ON`, `RELATED_TO`, `PROPOSED_BY`, `CONTRADICTS`, `DECIDED_IN`, `SUPERSEDES`. The predicate vocabulary is *versioned and limited*, not free-form hidden LLM invention.

```text
ProposedRelationship {
  subject_entity, predicate, object_entity,
  source_record_ids[], support_claim_ids[],
  extracted_by, asserted_at, valid_from?, valid_until?,
  scope?, confidence_as_diagnostic?,
  review_state: proposed | reviewed | contested
}
```

This is **not an accepted new SQL schema**, and review_state does not replace MemoryClaim status. A relationship inferred from a transcript is a hypothesis; visual edges must disclose uncertainty. An approved MemoryClaim may support an edge, but extracting the wrong predicate still makes the edge invalid. Entity alias resolution (e.g., two people with same name, changed company names) is a separate reviewable operation. Time and provenance are needed for "used to", "now", and "why" queries. Contradiction detection surfaces alternatives; it cannot silently choose which personal belief wins.

## 6. Obsidian is a first-class optional visual client

**User requirement:** be able to open a Sovereign-generated, graph-linked Markdown vault in **Obsidian**, browse nodes, follow relationships, and inspect sources. This is an explicit acceptance requirement, not decorative future art.

Design a **local, opt-in, one-way materialized Markdown projection** from *authorized canonical state* into a separate directory that Obsidian can open as a vault. It is not the Git repository, not an automatically synced public vault and not the canonical memory database. Native Sovereign graph explorer may follow later, but must not be a prerequisite.

- **Output:** UTF-8 Markdown with Obsidian-compatible `[[wikilinks]]`, stable collision-safe filenames, readable titles, and YAML frontmatter with `sovereign_id`, `kind`, `status`, `source_refs`, `derived_at`, and `projection_version`. An explicit `_Start Here.md` leads to projects, claims, evidence, concepts and graph-use instructions.
- **Views:** a human-readable project/topic wiki, a provenance/evidence overlay, and later vetted domain relationships. Use local graph filters/groups based on tags/kinds; default to neighborhood views, not a full personal graph.
- **Typed edges:** Obsidian's *built-in Graph view only draws untyped links between notes*. Store meaningful predicate, temporal validity and evidence in frontmatter and note body (or dedicated relation notes). Do **not** pretend that Obsidian draws arrow labels or validates edge authority. A custom renderer/plugin can be evaluated later, separately.
- **Example:** `Claims/EX-Claim-01.md` contains a `SUPPORTED_BY` section linking to `[[EX-Source-01]]`, and a `PROJECT` section linking to `[[EX-Project-01]]`. Those backlinks appear visually; the sections encode semantics for the reader.
- **Export manifests:** map canonical IDs to generated files and dependencies, track projection generation and source fingerprints, and atomically reconcile removal/renames when source is forgotten or changed. Derived names, contents and embeddings must also be removed; stale files must not be left as visible personal-history remnants.
- **Edits:** user's changes inside exported notes must **not** silently update canonical claims. Initial exporter is one-way; if bidirectional editing is desired, define a separate safe import/review workflow.
- **Boundary:** require local device/vault authorization before any graph listing or export; provide explicit directory, data-class scope and user confirmation. Never send the export to GitHub, Obsidian Sync, iCloud or plugins without user authorization. Warn that filesystem snapshots/backups/indexes may retain earlier copies; do not claim secure erasure.
- **Acceptance:** a synthetic vault, opened in Obsidian, renders meaningful backlinks in Graph view, and source correction/Forget rebuild leaves no stale exported note or link. See [Obsidian plan and demo](../second-brain/LEVELS-AND-OBSIDIAN.md).

## 7. Cost, cadence and end-state

**Near term (Level 3–4):** local-first deterministic retrieval and FTS, benchmarked optional local embeddings, on-demand graph projection, capped neighborhood traversal, optional manual/opt-in graph extraction. No recurring model bill is required just to keep the brain usable. Paid LLM calls happen through existing approved request paths or a separately governed, capped extraction workflow only after its own ADR.

**Future (Level 5):** periodic sync and selective memory updates, proactive conflict detection, live integrations and potentially agent coordination. Only revisit when daily utility, security/recovery, explicit user/bystander consent, model/provider limits and measured cost/energy budgets justify it. Always-on is **not** a permission or retention policy. Local event-triggered rebuilds are not the same as autonomous cloud agents.

## 8. Phased engineering strategy

1. **Benchmark first:** synthetic multi-domain corpus and fixed expected source IDs covering exact match, paraphrase, full-document, numerical, temporal, cross-project, conflict and no-answer cases. Report baseline metrics; no production behavior changes.
2. **L3 candidate retrieval:** evaluate full-text improvements and optional local semantic index as replaceable adapters. Recheck canonical evidence in one snapshot. Rank and context-budget diagnostics must remain inspectable; preserve exact disclosure.
3. **L4 provenance graph:** deterministic, read-only source/claim/supersession projection with a scoped local viewer and a synthetic Obsidian export. Test correction, Forget, export cleanup and offline use.
4. **L2 generated wiki:** project/topic index notes and backlinks as rebuildable documentation over canonical memory. No competing autonomous memory.md.
5. **L4 domain pilot:** evaluate proposed entity relationships against manually labeled synthetic data, entity deduplication, temporal semantics and grounded multi-hop answers. New persistent schema needs separate ADR.
6. **L5 research track only:** evaluate trigger/cadence, cost, information half-life, safe retention, and bounded agent authority after preceding milestones.

These are **second-brain workstream phases**, not replacements for the main ROADMAP's M0–M5 operating-system milestones. Security/recovery and daily useful capture remain priorities; do not let a graph visualization delay them.

## 9. Quality, adversarial tests and gates

Measure source recall at k, answer completeness, exact-answer correctness, temporal accuracy, graph-path grounding, hallucinated-edge rate, abstention, latency, storage footprint, upfront/indexing and per-query API cost. Compare every retrieval change to an unchanged baseline. A higher retrieval score cannot compensate for violation of MemoryClaim or disclosure rules.

Must-pass invariants: no unauthorized authority promotion; no forgotten evidence or derived graph content resurfacing; no sensitive-data egress; no unseen graph/vector context added after exact preview; no obsolete embeddings or Obsidian files after materialized projection rebuild; no third-party sync of personal graph without express action; full export/restore unaffected. For local UI privacy, do not confuse loopback-only serving with authentication.

Current security gate remains **NOT PASSED**: synthetic/intentionally non-sensitive data only, no assertion of secure deletion in backups/WAL/third-party copies.

## 10. Alternatives and reversal

- Replace canonical memory with LightRAG/Neo4j/markdown: **rejected** (retrieval/extraction must not determine memory authority).
- Vector-only search: **rejected as exclusive method** (weak on exactness, totals, chronology, complete-document coverage).
- Graph-only brain: **rejected as exclusive method** (wrong/missing entity extraction; source text still essential).
- Build an always-on Level 5 orchestration now: **deferred** (cost, complexity, security and consent).
- Direct bidirectional Obsidian writes: **deferred** (could overwrite canonical claims outside approval workflow).
- Hosted vector/graph databases: **not required** for initial single-user prototype.

Indices, graph projections and Obsidian export are disposable; disabling/removing them restores lexical/canonical access and must not alter claim authority or canonical backup format. New persistent entity schema, if eventually selected, requires migration/export/restore/deletion tests and an independent security review.

## 11. Open questions

Local embedding choice (if justified by benchmark), index generation and token semantics, entity resolution and predicate registry, Obsidian user-auth/export/delete threat model, selective retention policies, future live-source provenance, and explicit capped monthly budgets for optional Level 5 remain to be resolved in bounded ADRs.

**No implementation, new permissions, permanent data schema, background ingestion or constitutional amendment is authorized merely by proposing this architecture.**
