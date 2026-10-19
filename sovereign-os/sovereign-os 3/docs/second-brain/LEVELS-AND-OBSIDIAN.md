# Second-Brain Levels, Retrieval Strategy and Obsidian Graph

**Status:** architecture guide / planned capability, not implemented product instructions. Start with [ADR-0005](../adr/0005-governed-second-brain-architecture.md). Sovereign's active project root is the directory containing `AGENTS.md`, `src/sovereign` and this `docs/` tree.

## 1. Why the five levels matter

The source video defines **five interoperable techniques**. They are not a universal standard and do not imply that higher level means better quality. A single Sovereign project may have L1 source folders, an L2 wiki, L3 semantic retrieval and a small L4 graph simultaneously. A long-lived personal brain needs the *right lookup for the question*, not one index for everything.

### Level 1 — folders and routing

**Shape:** stable directory tree, Markdown documentation, indexes, agents' orientation files. A human and an AI can traverse from a project overview to its notes or original document.

**Strengths:** cheap, human-verifiable, portable, readable offline, no embedding bill. **Failure modes:** unknown filenames, stale pointers, drift between summaries and source evidence. **Use in Sovereign:** canonical code/docs routing and generated human-readable project indexes. Do not make `AGENTS.md` or `CLAUDE.md` personal-memory authority.

### Level 2 — linked wiki and memory pages

**Shape:** concept pages with links, source indexes, backlinks and topic hierarchies, usually Markdown. Obsidian's Graph view visualizes `[[links]]` among pages.

**Strengths:** inspectable navigation and cross-project orientation; easy export. **Failure modes:** backlinks are not predicates; a link between two companies does not mean they compete. Auto-generated wiki prose can summarize incorrectly. **Use in Sovereign:** opt-in rebuildable Markdown pages with canonical references and explicit source attribution.

### Level 3 — semantic and hybrid retrieval (near-term core)

**Shape:** lexical/FTS terms plus optionally local embeddings over source text or bounded segments; candidate reranking; document expansion.

**Strengths:** search by meaning even when wording differs; can find similar episodes. **Failure modes:** top-k segment retrieval may miss the rest of a meeting; a similar vector does not establish a legal/financial fact; dates/IDs need exact matching; index can be stale. **Use in Sovereign:** discovery of canonical IDs, never authority or independent cloud context.

Use **full document** for "summarize this entire meeting"; **structured calculation** for numeric extrema; **exact lookup** for an ID/date; **hybrid search** for conceptual discovery. Chunking strategy should preserve parent document and provenance.

### Level 4 — typed knowledge/relationship graph (near-term extension)

**Shape:** nodes for evidence/claims/projects/entities; edges with relationship types, source references, valid time and review state. A query can traverse `Project -> DEPENDS_ON -> Technology -> DISCUSSED_IN -> Source`.

**Strengths:** multi-hop reasoning, dependencies, finding contradictory assumptions, tracing a conclusion to sources. **Failure modes:** invented predicates, conflated entities, stale edges, dense unreadable visualizations. **Use in Sovereign:** deterministic MemoryClaim provenance graph first, then benchmarked typed domain edges. Model-extracted relationships remain hypotheses until governed review.

### Level 5 — continuously maintained intelligence (eventual goal)

**Shape:** scheduled ingestion/sync, ongoing indexing, refresh of changing operational data, autonomous or proactive agents.

**Strengths:** up-to-date, less manual capture, notifications/action candidates. **Failure modes:** continual token/API/infrastructure costs, runaway noise, unintended storage of third-party data, stale auto-memory, invisible permissions and disclosure. **Use in Sovereign:** future permissioned, stoppable, budgeted option **after** Level 3–4 proves useful; not a default daemon now.

### Practical selection guide

| Query/user need | Prefer |
| --- | --- |
| Locate exact decision, named file or record ID | L1/L2 + exact/lexical lookup |
| Browse how a project developed | L2 project index + chronology |
| Find a discussion described using different words | L3 hybrid semantic + lexical |
| Summarize full transcript | Locate by L1/L3; then fetch entire authorized original |
| Compare years or calculate maxima | Structured/time-indexed sources, deterministic computation |
| Show why a claim is approved | L4 evidence/provenance graph (live MemoryClaim support) |
| Find project-to-project dependency chains | L4 typed graph with evidence checks |
| Ask about live app or inbox state | Future authorized connector, not blindly durable memory |
| Run autonomous refresh daily | L5, deferred until approved costs/permissions/security |

## 2. Two views, not two truths

**Evidence graph** uses only canonical source and claim links that already exist. Example: `Claim A --SUPPORTED_BY--> Source B`; `Claim A --SUPERSEDED_BY--> Claim C`. Validity is read from the source vault, not inferred from note names.

**Domain graph** maps topic/project/entity relationships. Example: `Project A --DEPENDS_ON--> Concept B`, but only as a grounded, status-labeled assertion. "Related" is not "caused" or "approved". Distinguish human decision, observed event, model hypothesis and contested proposition.

Both may be visualized together after controls permit it; local source evidence always wins over generated graph data.

## 3. Obsidian requirement and constraints

The user explicitly wants Sovereign's brain visible as an **Obsidian graph**. A planned exporter shall generate a **local Markdown vault with `[[wikilinks]]` and YAML metadata**, usable in Obsidian's built-in Graph view without proprietary dependencies.

**Important limitation:** built-in Graph view shows note-links. It does **not** inherently show edge labels, arrow directions, per-edge timestamps, confidence or provenance enforcement. Put typed relationships in sections/frontmatter or dedicated relation notes. A rich typed graph renderer is a later optional enhancement. An Obsidian graph is *a view*, not a truth engine.

### Demo available now (synthetic only)

The directory [`obsidian-demo-vault/`](obsidian-demo-vault/) is a small **synthetic Markdown sample**, not an exporter and not real memories.

1. In Obsidian, choose **Open folder as vault**, then select the `obsidian-demo-vault` folder from a local copy of this repository.
2. Open `_Start Here.md`; click **Graph view**.
3. Follow a project, a claim and its source; notice wiki backlinks.
4. Inspect the `SUPPORTED_BY` section of the example claim: Graph view draws a line, the note text supplies the typed meaning.
5. Use Graph view filters/grouping and Local graph to avoid the full graph becoming unreadable.

No plugin, model account or online service is required to view the synthetic notes.

### Planned generated-vault structure (proposal, no exporter yet)

```text
Sovereign-Obsidian-Projection/          (outside Git; private directory)
  _Start Here.md
  Projects/
    p-<stable-safe-id>.md
  Topics/
    t-<stable-safe-id>.md
  Sources/
    s-<stable-safe-id>.md
  Claims/
    c-<stable-safe-id>.md
  Relationships/                      (optional typed-edge notes)
  .sovereign-projection-manifest.json   (mapping + generation, private)
```

A projection file might look like:

```markdown
---
sovereign_id: "synthetic-claim-id"
kind: "claim"
status: "approved"
source_refs: ["synthetic-source-id"]
projection_version: 1
tags: [sovereign/claim]
---
# Synthetic memory: local-first

## SUPPORTED_BY
- [[s-example-source|Evidence: design note]]

## ABOUT
- [[p-example-project|Example project]]

This is example content, not verified personal data.
```

Use YAML quoted fields; avoid identifiers/paths that expose raw personal content. Use stable collision-safe path mapping so aliases or title changes do not silently merge entities. Generated backlinks must survive ordinary reopen in Obsidian. Preserve date/valid-time fields only when supported by canonical sources.

### Export semantics and safety (implementation requirements)

- **Opt in:** the person chooses source scope and output folder after inspecting what will be materialized. Existence of graph nodes may itself reveal sensitive information.
- **Local only by default:** no automatic Git check-in, cloud embedding, Obsidian Sync, third-party graph plugin or remote note publishing. Clarify that merely opening the vault in an environment with user-configured sync/plugins may copy data.
- **One way:** generated notes are read-only projections. Editing a Markdown note cannot approve/correct a MemoryClaim until a separate explicit governed import path exists.
- **Atomic reconciliation:** maintain a manifest; on correction/Forget, remove stale derived note bodies, filenames, links, previews and aliases, then rebuild. Test restart and interrupted export. Canonical Forget cannot promise deletion of unmanaged copies, filesystem backups or synced mirrors.
- **No hidden credentials/URLs:** no private filesystem paths or secret IDs in cloud prompts; provider only sees exactly compiled, authorized context.
- **Graph quality:** use small neighborhood expansions, source-first labels, filtering by note type/approval state, dedicated start/index pages. Do not make all transcripts permanent densely linked graph nodes by default.
- **Portability:** every note remains ordinary Markdown; removing Obsidian leaves canonical memory intact.

## 4. Retrieval and graph roadmap

**R0 — synthetic evaluation:** benchmark current lexical behavior, no new index or cloud calls.

**R1 — local search:** measure FTS5 and optional embeddings on paraphrase queries; handle exact, timeline, full document and numerical questions correctly.

**R2 — provenance graph and Obsidian:** read-only projection of real stored source/claim/supersession edges, scoped local view and opt-in export; demonstrate Forget cleanup and no authority change.

**R3 — domain graph:** typed/temporal relationship extraction from synthetic evidence and a human-review process. Store new graph data only after a schema/deletion ADR.

**R4 — Level 5 someday:** selective, consented, capped background maintenance and agentic work after testing usefulness, security and recurring budget.

Details and non-negotiable boundaries: [ADR-0005](../adr/0005-governed-second-brain-architecture.md). Acceptance/evaluation: [Benchmark 0003](../benchmarks/0003-second-brain-retrieval-evaluation.md).
