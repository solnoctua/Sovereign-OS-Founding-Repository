---
sovereign_projection: 1
kind: "navigation"
title: "Start Here"
generation: 1
generated_at: "2026-10-20"
scope: "private items; all statuses; review scope on"
tags:
  - sovereign/navigation
---
> [!NOTE]
> Synthetic demo of a Sovereign projection. A snapshot, not memory: Sovereign is authoritative, and edits here are never imported. Lists and links only items included in this export. Stored text is shown inert; invisible or control characters appear as ⟪U+XXXX⟫. Generation and date: below.
>
> Everything in this vault is **fictional**: a hand-written example of the proposed Sovereign → Obsidian projection (spec: `docs/second-brain/OBSIDIAN-PROJECTION.md` in the Sovereign repository). It is not an exporter and not anyone's memory.

# Start here

Two fictional projects — **Lantern**, a garden-sensor prototype, and **Harbor**, an offline notes app — with their sources, claims, decisions and relationships.

**Generation 1 · 2026-10-20.** Statuses in every note are as of this generation.

**Scope (by filter class only):** private items; all statuses; review scope on, so unreviewed model proposals are included (a default export omits them).

**About partial notes.** A note that says *"Provenance partial: at least one directly linked item is not included in this export."* has at least one direct link that was left out — because of a filter, the date range, review status, sensitivity, or because the item is no longer in Sovereign. The note never says which item, how many, or why. Lists in every note show only items included in this export; Backlinks likewise.

## Open the graph

1. Use a copy of this folder outside any Git checkout and outside any other Obsidian vault, opened with **Open folder as vault**, with community plugins off (Restricted mode).
2. Open **Graph view**. The bundled `.obsidian/graph.json` applies these defaults; if your Obsidian ignores it, set them in the graph settings:
   - **Filters → search:** `-tag:#sovereign/navigation` (hides these navigation notes, which link to everything)
   - **Filters → Tags:** off
   - **Display → Arrows:** on (each line points away from the note that holds the relationship)
   - **Groups:** the colors in the legend below, in that order
3. For everyday use, open a project or decision and choose **Open local graph** with depth 2 instead of the global graph.

*Animate* only shows notes in the order their files were created on your disk. It is not a history view: it knows nothing of stored times, corrections or decisions. For chronology use [[Timeline]] and each claim's decision history.

## Legend

| Color | Group query | Meaning |
| --- | --- | --- |
| Grey | `tag:#sovereign/status/superseded` | Superseded: replaced by a newer version (not "false") |
| Charcoal | `tag:#sovereign/status/rejected` | Rejected by a human: not memory |
| Blue-grey | `tag:#sovereign/support/orphaned` | Evidence it cites is missing or fails its hash check (orphaned): not approved memory |
| Amber | `tag:#sovereign/support/stale` | Evidence it cites was corrected (stale): not approved memory |
| Orange | `tag:#sovereign/status/contested` | Contested |
| Purple | `tag:#sovereign/status/proposed` | Proposed and unreviewed: not a fact |
| Blue | `tag:#sovereign/project` | Project hub *(future: human-declared organization, SB-3)* |
| Green | `tag:#sovereign/concept` | Concept hub *(future, SB-3)* |
| Brown | `tag:#sovereign/source` | Source record: evidence, not belief |
| Red | `tag:#sovereign/form/decision` | Decision: a MemoryClaim *(the decision form is future)* |
| Teal | `tag:#sovereign/claim` | Claim: a MemoryClaim |
| Pink | `tag:#sovereign/relationship` | Typed relationship *(future: structured MemoryClaim, SB-7)* |

Groups apply top-down, so status colors win over kind colors. Every query uses tags the exporter generates; text inside notes cannot produce them.

## Reading a line

Lines are untyped. Every line comes from **one link in one note**, under a heading that names the relationship — `SUPPORTED_BY`, `CORRECTS`, `CORRECTED_BY`, `SUPERSEDES`, `SUPERSEDED_BY`, a hub's filing sections, or `Why this connection exists`. To learn why two notes are connected, open the note the arrow starts from. Reverse directions are in the **Backlinks** pane; only lineage is linked both ways, so an outdated note always points to its replacement when that replacement is included.

Text that came from a record, claim or decision note appears in grey `text` blocks, each introduced by a label with its size and closed by *End of stored text.* It is displayed verbatim and is never active: links, images, tags, HTML or plugin syntax inside it do nothing. The *only* generated part of a file name is its final parenthesized handle.

## Paths to try (demo-only teaching section; a generated Start Here never contains it)

1. **Why is this decision believed?** [[Lantern stores readings in SQLite on device (c-i4wgm7lh)|Lantern stores readings in SQLite on device]] → `SUPPORTED_BY` → its source.
2. **What changed, and when?** Open [[Timeline]], then [[Lantern stores readings in PostgreSQL (c-igermtp3)|Lantern stores readings in PostgreSQL]]: an approved decision superseded because the plan *changed*, not because it was wrong.
3. **A corrected source.** Two notes share the title *Harbor design memo*: [[Harbor design memo (s-g4xykl2z)|Harbor design memo]] is the superseded revision and [[Harbor design memo (s-bnpxlmya)|Harbor design memo]] its correction, so the claim citing the old one, [[Harbor syncs every 5 minutes (c-hr5ebnrp)|Harbor syncs every 5 minutes]], is stale.
4. **A contradiction.** [[Lantern battery lasts about 14 days (c-7h2xuih2)|Lantern battery lasts about 14 days]] was contested after a field test.
5. **Why are two projects connected?** [[Project Harbor depends on Project Lantern (r-urfcpc5x)|Project Harbor depends on Project Lantern]] has evidence and a human approval. [[Project Harbor uses PostgreSQL (r-5bpwiiwh)|Project Harbor uses PostgreSQL]] is an unreviewed model proposal whose own evidence shows it is wrong — the reason model-extracted relationships never count as facts.
6. **A partial note.** [[Field test log (s-4mfnn4hw)|Field test log]] carries the fixed partial sentence.
7. **Hostile text stays inert.** [[Feature request from the Harbor beta list (s-45q4l4lw)|Feature request from the Harbor beta list]] contains links, an image, HTML, tags, plugin syntax and a script block. It is designed so that, in Graph view, it connects only to its hub and nothing in it loads or runs (not yet verified in Obsidian).

## What Sovereign could generate today

| Element in this demo | Produced by the planned exporter (SB-2)? |
| --- | --- |
| Sources, revisions, claims, decision histories, `SUPPORTED_BY`, `CORRECTS`, `SUPERSEDES`, timeline and status indexes | **Yes**, from existing canonical data |
| Readable titles in filenames | Yes, from each item's own text (privacy decision D7) |
| Project and concept hubs | No: needs human-declared organization (SB-3) |
| The *Decisions* folder | No: needs a claim form; today these are ordinary claims |
| Typed relationships | No: needs structured MemoryClaims (SB-7) |
| Valid-from dates; "changed" vs "corrected" | No: needs the temporal claim extension (SB-6) |

A note's `available_after` property names the slice it needs; `future_fields` lists properties Sovereign does not have yet; `adversarial_fixture` marks the hostile test note. These three keys exist only in this demo; an exporter never writes them.

Indexes: [[Timeline]] · [[Claims by status]]
