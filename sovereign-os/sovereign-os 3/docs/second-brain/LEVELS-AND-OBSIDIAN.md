# Second-Brain Levels, Retrieval Strategy and Obsidian Graph

**Status:** architecture guide for a planned capability; nothing here is implemented. Decisions and invariants live in [ADR-0005](../adr/0005-governed-second-brain-architecture.md) (PROPOSED); the Obsidian format contract lives in [OBSIDIAN-PROJECTION.md](OBSIDIAN-PROJECTION.md). Sovereign's active project root is the directory containing `AGENTS.md`, `src/sovereign` and this `docs/` tree.

## 1. Why the five levels matter

The source video describes **five interoperable techniques**. They are not a standard, and a higher level does not mean better quality. One Sovereign project may use L1 folders, an L2 wiki, L3 semantic retrieval and a small L4 graph at once. A lifelong personal brain needs the *right lookup for the question*, not one index for everything.

Keep three numbering schemes apart: **M0–M5** are product milestones (ROADMAP §C), **L1–L5** are these techniques, and **SB-0…SB-9** are the delivery slices of this workstream (ADR-0005 §11, ROADMAP §G).

### Level 1 — structured files and routing

**Shape:** stable directory tree, Markdown documentation, indexes, orientation files. A human or an agent can walk from an overview to the note or original document.

**Strengths:** cheap, human-verifiable, portable, readable offline, no embedding bill. **Failure modes:** unknown filenames, stale pointers, summaries drifting from their sources. **In Sovereign:** repository routing (`AGENTS.md`, READMEs) and generated index pages inside an Obsidian export. `AGENTS.md` and `CLAUDE.md` are never personal-memory authority.

### Level 2 — linked wiki

**Shape:** concept and project pages, source indexes, backlinks and topic hierarchies, usually Markdown. Obsidian's Graph view draws the `[[links]]` between pages.

**Strengths:** inspectable navigation and cross-project orientation; easy export. **Failure modes:** a backlink is not a predicate (a link between two companies does not mean they compete); generated wiki prose can misstate its sources. **In Sovereign:** deterministic hub and index pages built from canonical items — lists, timelines and status tables, not generated prose. Project and concept hubs need **human-declared organization**, which does not exist yet (SB-3, decision D2).

### Level 3 — semantic and hybrid retrieval (target; embeddings deferred, R6)

**Shape:** lexical/FTS terms plus optional local embeddings over records or bounded segments; rank fusion; whole-document expansion.

**Strengths:** finds material by meaning when wording differs, including across languages with a multilingual model. **Failure modes:** top-k segments omit the rest of a document; similarity does not establish a fact; IDs and dates need exact matching; indexes go stale; vectors can be partially inverted back into text. **In Sovereign:** discovery of candidate canonical IDs only. It is *not* a drop-in: the Context Compiler's relevance gate is lexical, so adopting L3 is a compiler policy and disclosure change (ADR-0005 §6). Benchmark 0003 (PR #4, evaluation only, not yet merged) measured the cheap lexical options on a synthetic corpus: Porter normalization recovers 2 more expected items but admits 47 more irrelevant ones; using stems only to order exact matches recovers 1 with no added noise; weighted ranking (IDF, BM25) stales almost every pending preview on an unrelated write; no lexical method recovers paraphrases. By founder direction, production retrieval is unchanged: no experimental retriever is approved, Porter and the exact-stem tie-break are evaluated candidates only, weighted ranking and embeddings are deferred, and precision comes before recall for cloud plans (ADR-0005 §12.2).

Use **whole-record access** for "the entire note", **exact lookup** for an ID or date, **timeline ordering** for "what changed", **hybrid search** for conceptual discovery. A Sovereign record holds at most 10,000 characters, so whole-record retrieval needs no chunking today.

### Level 4 — typed knowledge/relationship graph (near-term extension)

**Shape:** nodes for evidence, claims, projects and other entities; typed relationships with source references, valid time and MemoryClaim status. In Sovereign a typed edge is itself a relation claim: `Project ← subject — [DEPENDS_ON relation claim] — object → Project`, and that relation claim is `SUPPORTED_BY` its source records.

**Strengths:** multi-hop connections, dependencies, contradictory assumptions, tracing a conclusion to its sources. **Failure modes:** invented predicates, conflated entities, stale edges, unreadable dense visuals, and *authority laundering* — an edge looking approved because the claim beside it is. **In Sovereign:** first a deterministic provenance graph computed from existing links (SB-2); later typed relations as **structured MemoryClaims** (SB-7) with the normal approval lifecycle. Model-extracted relations remain `proposed` until a human approves them.

### Level 5 — continuously maintained intelligence (eventual goal)

**Shape:** scheduled ingestion and sync, ongoing indexing, refresh of changing operational data, proactive or autonomous agents.

**Strengths:** current, less manual capture, timely prompts. **Failure modes:** continual token, API and infrastructure cost; noise; unintended storage of third-party data; stale or compounding auto-memory; invisible permissions and disclosure. **In Sovereign:** a future permissioned, stoppable, budgeted option **after** L3–L4 prove useful in daily life. Re-running an exporter or updating a local index on write is *not* Level 5.

### Practical selection guide

| Question or need | Prefer | Available on today's canonical data? |
| --- | --- | --- |
| Locate an exact decision, named item or record ID | Exact/lexical lookup | Yes |
| Read a whole note | Locate (L1/L3), then fetch the entire authorized record | Yes (records ≤ 10,000 chars) |
| Find a discussion described in other words, or another language | L3 hybrid semantic + lexical | No: embeddings deferred until representative usage shows the need (SB-5, R6) |
| See how something changed over time | Timeline ordering + revision and supersession lineage | Partly: stored/decision times only; valid time needs SB-6 |
| Show why a claim is believed | Provenance graph: claim → sources → revisions, plus decision history | Yes (SB-2) |
| Browse a project | L2 project hub | After SB-3 |
| Summarize a multi-part meeting | Group of records, then whole-record expansion | After SB-3 grouping |
| Compute a maximum or total | Structured data and deterministic computation | No structured sources exist; expect abstention |
| Find dependency chains between projects | L4 typed relations with evidence | After SB-7 |
| Ask about live app or inbox state | A future authorized connector queried at use time | No |
| Refresh everything daily | L5 | Deferred |

## 2. Two views, not two truths

**Provenance graph** uses only links Sovereign already stores: `Claim —SUPPORTED_BY→ Source`, `Revision —CORRECTS→ earlier revision`, `Claim —SUPERSEDES→ earlier claim`. Status and support are read from the vault, never from note names.

**Domain graph** connects projects, concepts and other entities: `Project Harbor —DEPENDS_ON→ Project Lantern`, but only as a structured, status-labeled claim with evidence. "Related" is not "caused" or "approved". Keep human decisions, observed events, model hypotheses and contested propositions visibly distinct.

Both may be drawn together; canonical evidence always wins over generated graph data.

## 3. Time: correction is not change

Sovereign records **when something was stored** (capture time, or a time carried in by import or restore) and **when a human decided about a claim**, but not **when a proposition was true**. A corrected typo and a reversed project decision both end in `superseded`. Until the temporal claim extension (SB-6, D10) exists, read `superseded` as "no longer the current approved interpretation", never as "was false", and answer "what did we decide then vs now" in local views from stored and decision times; model prompts cannot carry that history through the governed path yet (ADR-0005 §8.3). Benchmark 0003 does not measure this distinction (validation spec §2); SB-6's tests score correction and change separately (validation spec §5).

## 4. Obsidian: requirement, constraints and demo

The user explicitly wants to **browse Sovereign's brain as an Obsidian graph**. A planned exporter (SB-2) writes a **local, one-way Markdown vault** with `[[wikilinks]]` and YAML properties that works in Obsidian's core Graph view, Local graph and Backlinks pane with no plugin. The format, naming, scope, Forget and acceptance rules are in [OBSIDIAN-PROJECTION.md](OBSIDIAN-PROJECTION.md).

**What Obsidian can and cannot show** (core features):

| Can | Cannot |
| --- | --- |
| Draw a line for every link between notes; show its **direction** with the *Arrows* display option | Label a line, type it, or attach evidence, time or confidence to it |
| Color nodes by search query (folder, tag, property) | Distinguish two kinds of line between the same notes |
| Local graph of one note at a chosen depth | Show validity intervals or filter by date |
| *Animate*: notes appear in **file-creation** order, i.e. the order files were written on this disk | Replay history: it knows nothing of stored times, corrections, supersessions or MemoryClaim status changes. Use the Timeline and decision-history notes for chronology |
| Backlinks pane: every note that links here | Validate anything, or query Sovereign live |
| Node labels from **filenames** | Use a title property as the graph label (without a plugin) |

So: **every line comes from exactly one link in one note, under a heading that names the relationship, followed by its evidence and time.** That is how a reader finds out *why* a connection exists. An Obsidian graph is a view, not a truth engine, and every exported status is a dated snapshot.

Three further rules keep an export trustworthy (export spec §7, §8, §11): text from records, claims and notes is shown **inert**, inside fenced blocks, so it can never create a link, embed, tag or network request; only items inside the export's **authorized scope** are linked or named, and an excluded endpoint becomes a fixed "provenance partial" sentence; and an export is an honest **snapshot**: it is made only when you ask, shows the vault as of its snapshot time, is verified before it is offered, and says plainly that forgetting something in Sovereign later does not erase it — delete old exports and export again.

### Demo available now (synthetic only)

[`obsidian-demo-vault/`](obsidian-demo-vault/) is a small, **fictional** vault that shows the target export format, including elements that require future slices (each marked in its note). It is not an exporter and contains no real memories.

1. Copy the `obsidian-demo-vault` folder **out of the Git checkout** (Obsidian writes its own settings into a vault folder), then in Obsidian choose **Open folder as vault**.
2. Open `_Navigation/Start Here`, then **Graph view**. The bundled `.obsidian/graph.json` hides navigation notes, turns tags off, turns arrows on and colors nodes by kind and status; the Start Here note lists the same settings to apply by hand if your Obsidian version ignores the file.
3. Open a project and choose **Open local graph**, depth 2.
4. Walk the seven paths in Start Here: why a decision is believed, what changed, a corrected source, a contested claim, why two projects are connected (including one deliberately wrong, unreviewed model proposal), a partial view whose linked item is outside the export's scope, and an adversarial note whose links, image, HTML, tags and script stay inert.

No plugin, account or online service is needed.

## 5. Prior art: what to borrow, what not to adopt

"Maturity" distinguishes proven designs from speculation. Nothing below is adopted; each would need a measured Sovereign problem first (ADR-0005 §13).

| Technique / project | Maturity | Borrow | Do not adopt now, because |
| --- | --- | --- | --- |
| BM25 / SQLite FTS5 | Proven | Nothing now: no lexical change is authorized (R1); Porter and the exact-stem tie-break are evaluated candidates only | Measured in Benchmark 0003: FTS5 BM25 with Porter stemming gives +3 items over baseline, only +1 over Porter alone; without stemming it gives −9 (57/88). 51–53/56 previews are invalidated by an unrelated write and the recency prior is lost; deferred (R2); an index would also need FTS5 `secure-delete` |
| Dense + lexical hybrid with Reciprocal Rank Fusion | Proven | Fusion rule if embeddings ever land | Embeddings deferred (R6); fusion is weighted ranking, so R2 applies |
| Parent-document ("small-to-big") retrieval | Established practice | Chunk hits resolve to the whole record | Records are already ≤ 10,000 chars |
| Approximate-NN indexes (HNSW etc.) | Proven at scale | — | Non-reproducible candidate universe breaks exact-plan tokens; personal scale fits brute force |
| LLM-generated chunk context ("contextual retrieval") | Vendor-reported gains | — | One model call per chunk; creates derived text; cloud use is disclosure |
| Microsoft GraphRAG (entity graph, communities, summaries) | Published; costly indexing | Idea of global summaries for very large corpora | Model authors the graph; community summaries mix many sources, so one Forget forces re-summarization |
| LightRAG | Published, active | Incremental graph update idea | Extraction-dependent authority; no Sovereign-grade provenance or Forget |
| HippoRAG / HippoRAG 2 (personalized PageRank) | Research | Deterministic graph ranking over a *governed* graph (SB-8) | Built on open information extraction triples |
| Graphiti / Zep temporal knowledge graph | Published, product | Bitemporal edges, episodes as provenance, invalidate rather than delete (SB-6/SB-7) | Model resolves contradictions automatically; needs an external graph DB |
| Mem0, Letta (MemGPT) agent memory | Products; vendor benchmarks contested | Negative reference; evaluation ideas | A model decides what to add, update or delete in memory |
| LongMemEval, LoCoMo (memory benchmarks) | Published benchmarks | Category design: knowledge updates, temporal reasoning, abstention | Their chat-history data is not Sovereign's record/claim model |
| W3C PROV | Standard | Edge vocabulary for provenance export | No interchange need yet |
| Obsidian community plugins (Smart Connections, Dataview, Breadcrumbs, Juggl, ExcaliBrain) | Community | Possible typed-edge rendering later | Not required; some send note content to cloud APIs; each is an exfiltration surface |

## 6. Delivery

The slices are defined once, in [ADR-0005 §11](../adr/0005-governed-second-brain-architecture.md#11-delivery-slices) and ROADMAP §G: SB-1 retrieval evaluation (Benchmark 0003, executed in PR #4) → SB-2 provenance graph and Obsidian snapshot export → SB-3 human-declared organization → SB-4 a lexical change, none authorized → SB-5 embeddings, deferred → SB-6 temporal claims → SB-7 typed relations → SB-8 graph-assisted context, deferred → SB-9 Level 5 research. Retrieval evaluation: Benchmark 0003, `docs/benchmarks/0003-retrieval-evaluation.md` ([PR #4](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/pull/4), not yet merged). Everything else: [the validation spec](SECOND-BRAIN-VALIDATION.md).
