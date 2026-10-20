---
sovereign_projection: 1
sovereign_projection_id: "demo-projection"
kind: navigation
title: "Start Here"
scope: "private items; sensitive items excluded; review scope on (includes one unreviewed proposal)"
tags: [sovereign/navigation]
generation: 1
generated_at: "2026-10-19"
demo: synthetic
---
> [!NOTE]
> Everything in this vault is **fictional**: a hand-written example of the proposed Sovereign → Obsidian projection (spec: `docs/second-brain/OBSIDIAN-PROJECTION.md` in the Sovereign repository). It is not an exporter and not anyone's memory.

# Start here

Two fictional projects — **Lantern**, a garden-sensor prototype, and **Harbor**, an offline notes app — with their sources, claims, decisions and relationships.

**Scope of this projection:** private items only; sensitive items are excluded and leave no trace; review scope is on, so one unreviewed model proposal is included for teaching (a default export omits proposals).

## Open the graph

1. Use a copy of this folder outside any Git checkout, opened with **Open folder as vault**.
2. Open **Graph view**. The bundled `.obsidian/graph.json` applies these defaults; if your Obsidian ignores it, set them in the graph settings:
   - **Filters → search:** `-path:_Navigation` (hides these navigation notes, which link to everything)
   - **Filters → Tags:** off
   - **Display → Arrows:** on (each line points away from the note that holds the relationship)
   - **Groups:** the colors in the legend below, in that order
3. For everyday use, open a project or decision and choose **Open local graph** with depth 2 instead of the global graph.

*Animate* only shows notes in the order their files were created on your disk. It is not a history view: it knows nothing of capture times, corrections or decisions. For chronology use [[Timeline]] and each claim's decision history.

## Legend

| Color | Group query | Meaning |
| --- | --- | --- |
| Grey | `tag:#sovereign/status/superseded` | Superseded: replaced by a newer version (not "false") |
| Amber | `tag:#sovereign/support/stale` | Approved, but its evidence was corrected: needs review |
| Orange | `tag:#sovereign/status/contested` | Contested |
| Purple | `tag:#sovereign/status/proposed` | Proposed and unreviewed: not a fact |
| Blue | `path:Projects` | Project hub *(future: human-declared organization, SB-3)* |
| Green | `path:Concepts` | Concept hub *(future, SB-3)* |
| Brown | `path:Sources` | Source record: evidence, not belief |
| Red | `path:Decisions` | Decision: a MemoryClaim *(the decision form is future)* |
| Teal | `path:Claims` | Claim: a MemoryClaim |
| Pink | `path:Relationships` | Typed relationship *(future: structured MemoryClaim, SB-7)* |

Groups apply top-down, so status colors win over kind colors.

## Reading a line

Lines are untyped. Every line comes from **one link in one note**, under a heading that names the relationship — `SUPPORTED_BY`, `CORRECTS`, `SUPERSEDES`, a hub's filing sections, or `Why this connection exists` — next to its dates. To learn why two notes are connected, open the note the arrow starts from. Reverse directions are in the **Backlinks** pane; only lineage (`CORRECTED_BY`, `SUPERSEDED_BY`) is linked both ways, so an outdated note always points to its replacement.

Text that came from a record, claim or decision note is shown in grey `text` blocks. It is displayed verbatim and is never active: links, images, tags or HTML inside it do nothing.

## Seven paths to try

1. **Why is this decision believed?** [[Lantern stores readings in SQLite on device (c-39798e)]] → `SUPPORTED_BY` → its source.
2. **What changed, and when?** Open [[Timeline]], then [[Lantern stores readings in PostgreSQL (c-fcbaf2)]]: an approved decision superseded because the plan *changed*, not because it was wrong.
3. **A corrected source.** [[Harbor design memo r1 (s-03d37f)]] was corrected by r2, so the claim citing r1, [[Harbor syncs every 5 minutes (c-96826c)]], is stale and stays out of model context until a human reviews it.
4. **A contradiction.** [[Lantern battery lasts about 14 days (c-acdade)]] was contested after a field test.
5. **Why are two projects connected?** [[Harbor DEPENDS_ON Lantern (r-8222a6)]] has evidence and a human approval. [[Harbor USES PostgreSQL (r-6b50eb)]] is an unreviewed model proposal whose own evidence shows it is wrong — the reason model-extracted relationships never count as facts.
6. **A partial view.** [[Field test log (s-8421e4)]] was corrected by a revision that is outside this export's scope. The note says so without revealing anything about the excluded item.
7. **Hostile text stays inert.** [[Feature request from the Harbor beta list (s-b8489b)]] contains links, an image, HTML, tags and a script block. In Graph view it connects only to its hub; nothing in it loads or runs.

## What Sovereign could generate today

| Element in this demo | Produced by the planned exporter (SB-2)? |
| --- | --- |
| Sources, revisions, claims, decision histories, `SUPPORTED_BY`, `CORRECTS`, `SUPERSEDES`, timeline and status indexes | **Yes**, from existing canonical data |
| Readable titles in filenames | Yes, derived from the text (privacy decision D7) |
| Project and concept hubs | No: needs human-declared organization (SB-3) |
| The *Decisions* folder | No: needs a claim form; today these are ordinary claims |
| Typed relationships | No: needs structured MemoryClaims (SB-7) |
| Valid-from dates; "changed" vs "corrected" | No: needs the temporal claim extension (SB-6) |

A note's `available_after` property names the slice it needs; `future_fields` lists properties Sovereign does not have yet.

Indexes: [[Timeline]] · [[Claims by status]]
