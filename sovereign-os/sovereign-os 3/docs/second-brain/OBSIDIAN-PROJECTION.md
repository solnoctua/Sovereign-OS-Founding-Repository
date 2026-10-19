# Obsidian Projection — format and behavior (proposed v1)

**Status:** PROPOSED specification for slice SB-2 and later slices of [ADR-0005](../adr/0005-governed-second-brain-architecture.md); no exporter exists. Founder decisions it depends on: D7 (filenames), D8 (Forget cleanup), D9 (rebuild trigger). The [demo vault](obsidian-demo-vault/) is a hand-written instance of this format.

## 1. Purpose and non-goals

**Purpose:** let the person explore Sovereign's knowledge visually and navigably in Obsidian — Graph view, Local graph, Backlinks, search — and answer "what is connected to this, why, and since when?" from the notes themselves.

**Non-goals:** the projection is not memory, not a backup, not a sync target, not an editing surface and not a source of authority. Removing Obsidian or the projection changes nothing in Sovereign.

## 2. What the projection may contain

Only canonical state, rendered deterministically. "Today" means derivable from the current schema once the exporter exists.

| Element | Canonical basis | Available |
| --- | --- | --- |
| Source notes: content, capture time, active/superseded, sensitivity | `records` | Today |
| Revision chains (`CORRECTS` / `CORRECTED_BY`) | `records.supersedes_id` | Today |
| Claim notes: text, status, support, authority, origin | `claims`, `claim_sources`, derived support | Today |
| `SUPPORTED_BY` links | `claim_sources` | Today |
| Claim supersession chains (`SUPERSEDES` / `SUPERSEDED_BY`) | `claims.supersedes_id` | Today |
| Decision history table per claim | `claim_events` | Today |
| Timeline and status index notes | Capture and decision times | Today |
| Note titles | None: derived from the first line or characters of the text | Today, with D7 privacy rules |
| Project and concept hubs, membership | Human-declared organization | After SB-3 (D2) |
| Decisions as their own folder | A claim form/kind | After SB-3 or SB-7 (a claim form) |
| Typed domain relations | Structured MemoryClaims | After SB-7 (D3) |
| `valid_from` / `valid_until`; correction vs change | Temporal claim extension | After SB-6 (D10) |

Anything not in this table — model summaries, inferred entities, co-occurrence links, similarity links — is **not** projected. A "related notes by similarity" view, if ever wanted, is a local UI feature, not Markdown links.

## 3. Obsidian capabilities this format relies on

Core features only; verify against the installed version.

- **Graph view / Local graph:** one line per linked note pair; *Arrows* shows direction; *Groups* color nodes by a search query (`path:`, `tag:`, `[property:value]`); a filter query hides notes; *Tags* and *Orphans* toggles; Local graph depth; *Animate* replays notes in file-creation order. **Node labels are note names, i.e. filenames.**
- **Backlinks pane:** incoming links for the open note — the reverse direction of every relationship without writing reverse links.
- **Properties:** YAML frontmatter is shown and searchable. Links inside properties are handled differently across versions, so **graph-relevant links live in the note body**, never only in properties.
- **Not available:** edge labels, edge properties, per-edge colors, typed or temporal edges, clicking an edge.

## 4. Vault layout

```text
<projection root>/                      chosen by the user; outside any Git working tree
  _Navigation/                          excluded from the graph by the default filter
    Start Here.md                       legend, how to read lines, paths to try
    Timeline.md                         chronological capture and decision events
    Claims by status.md                 approved / stale / contested / proposed / superseded
  Projects/   Concepts/                 hubs (after SB-3)
  Sources/                              one note per record revision
  Claims/     Decisions/                one note per claim (Decisions/ once a claim form exists)
  Relationships/                        one note per structured relation claim (after SB-7)
  .obsidian/graph.json                  optional default graph settings (§8)
```

The manifest and export registry live in Sovereign's data directory, **not** in the projection, so sync services and plugins pointed at the vault do not receive the ID-to-path map.

## 5. Identity, filenames and links

- **Identity** is `sovereign_id` in frontmatter, never the filename.
- **Filename (D7 recommendation):** `<readable title> (<short id>).md`, where the short ID is a stable prefix of the canonical ID long enough to be unique (case-insensitively) across the projection. Graph labels are filenames, so readable titles are what make the graph usable; the ID suffix prevents collisions and silent merges when two titles match.
- **Opaque mode:** `<kind>-<short id>.md` for users who do not want content in filenames. Filenames appear in OS file listings, search indexes, backups and sync logs; that is a disclosure surface.
- **Title derivation:** first line of the text, whitespace-collapsed, truncated at a word boundary to ≤ 60 characters. Sanitize to letters, digits, spaces and `- _ . , ' ( ) &`; replace everything else (including `# ^ [ ] | \ / : * ? " < >`) with `-`. Normalize to Unicode NFC. Keep the whole filename ≤ 200 bytes.
- **Renames:** when a title changes, the file is renamed and every link to it is regenerated in the same run. Users should keep their own notes outside the projection, because links from them will not be maintained.
- **Links:** `[[basename]]` or `[[basename|display text]]`; basenames are unique vault-wide, so links never need folder paths. Every link must resolve.

## 6. Note format

Every generated note starts with frontmatter and the snapshot banner.

| Property | Kinds | Meaning |
| --- | --- | --- |
| `sovereign_projection` | all | Format version (`1`); also marks the file as exporter-owned |
| `sovereign_id` | all but navigation | Canonical ID |
| `kind` | all | `source`, `claim`, `project`, `concept`, `relationship`, `navigation` |
| `title` | all | Display title |
| `status` | all but navigation | Source: `active`/`superseded`. Claim and relationship: lifecycle status. Hub: `active`/`archived` |
| `support`, `authoritative` | claims, relationships | Derived at export: `supported`/`stale`/`orphaned`; `authoritative` = approved and supported |
| `origin` | claims, relationships | `human`, `model`, `imported` |
| `sensitivity` | sources, claims | `private` (sensitive items are excluded unless explicitly included) |
| `captured_at` / `created_at` | sources / claims | Canonical times |
| `generation`, `generated_at` | all | Projection run that wrote this file |
| `tags` | all | `sovereign/<kind>`, `sovereign/status/<status>`, `sovereign/support/<support>` — used by graph color groups |
| `claim_form`, `predicate`, `subject`, `object`, `valid_from`, `valid_until`, `supersession_reason` | future | Only when the canonical field exists (SB-3/6/7) |

**Snapshot banner** (first body block, renders as an Obsidian callout and a GitHub alert):

```markdown
> [!NOTE]
> Generated by Sovereign — projection generation 12, 2026-10-19. A snapshot, not memory: Sovereign is authoritative, and edits here are never imported.
```

**Body by kind:**

- **Source:** title; one line with capture time, status ("active evidence — what was written down, not a verified fact") and sensitivity; the content as a quote; `## CORRECTS` (link to the predecessor revision) and, on a superseded revision, `## CORRECTED_BY` (link to its successor). Claims citing it and hubs organizing it appear in Backlinks.
- **Claim / decision:** title; one line stating whether it is approved memory *now* and, if not, why (`proposed`, `contested`, `stale` because evidence was corrected, `superseded`); `## SUPPORTED_BY` (one line per cited record with its capture time and current state); `## SUPERSEDES` / `## SUPERSEDED_BY`; `## Decision history` (table of `claim_events`: time, from → to, actor, note).
- **Hub (after SB-3):** what a human filed here, grouped as current decisions, earlier decisions, claims needing attention (stale/contested), and sources; hubs above a size limit list the most recent N members and link to an index note.
- **Relationship (after SB-7):** the assertion in words; subject, predicate (registry version), object, validity, status and decision history; `## Why this connection exists` with one line per cited record and the relevant quote.
- **Navigation:** Start Here, Timeline and status indexes; excluded from the graph by default.

**One canonical relationship, one link, one explanation.** The link sits in the note that holds the relationship (claim → sources; revision → predecessor; claim → predecessor claim; hub → members; relation → subject, object and evidence) under a heading naming the predicate. Reverse links are written only for lineage (`CORRECTED_BY`, `SUPERSEDED_BY`), because a reader who lands on an outdated note must be sent to the current one; everything else is reached through Backlinks. Never link two notes whose connection is not a canonical fact — for example, a stale claim does not link to the corrected revision it never cited.

## 7. Time in the projection

- The banner and `generation` make every status explicitly "as of".
- Revision and supersession chains are navigable both ways.
- Every claim note carries its decision history; `Timeline.md` lists capture, correction, approval, contest and supersession events in order.
- Until SB-6, `superseded` is rendered as "no longer the current approved interpretation" and never as "false"; the supersession reason appears only once it exists canonically.

## 8. Making the graph meaningful in daily use

A graph is useful when a local neighborhood answers a question; a global hairball is decoration. Defaults:

- **Filter** `-path:_Navigation` (navigation hubs would otherwise connect everything); **Tags** off (tag nodes would connect every note of a kind); **Arrows** on (links follow the relationship direction); **Orphans** on (an uncited source is informative).
- **Color groups, applied top-down:** superseded (grey), stale (amber), contested (orange), proposed (purple), then kinds: projects, concepts, sources, decisions, claims, relationships.
- **Start from a hub or claim with Local graph, depth 1–2**, not from the global graph.
- **Default scope excludes** sensitive items and unreviewed model proposals; a review scope can include proposals, colored distinctly.
- **Health metrics reported by the exporter:** link resolution (must be 100%), orphan share, largest component share, maximum hub degree, share of notes with readable titles. Report them; do not optimize node counts.

`.obsidian/graph.json` is Obsidian's own, undocumented settings file. The exporter may write it only into a projection it created, only with these defaults, and Start Here repeats the settings for manual use.

## 9. Export procedure

- **CLI only**, run by the user (for example `python -m sovereign export-obsidian --scope … --out DIR`). No HTTP endpoint writes files.
- **Preview first:** counts by kind, whether sensitive items or proposals are included, filename mode and output path; the user confirms.
- **Refuse** an output inside a Git working tree (any ancestor contains `.git`), a non-empty folder that is not a registered projection, and network or cloud-synced locations unless explicitly confirmed.
- **Read one snapshot** of the vault for the whole run.
- **Create a fresh projection oldest-first** (by capture or decision time), so Obsidian's *Animate* time-lapse, which follows file-creation order, replays the history. Incremental runs and temp-file renames reset creation times; the time-lapse is only meaningful right after a fresh export.
- **Write crash-consistently:** each file via a temporary file and rename; delete removed files; write the manifest last, with generation, `sovereign_id → path` and a content hash per file. An interrupted run is completed by the next run, which identifies its own files by the `sovereign_projection` property. Exports are not atomic across files; never claim they are.
- **Ownership:** create, rewrite or delete only files the manifest or the `sovereign_projection` marker identifies as owned. Never touch other files.
- **Edits:** owned files modified since the last run (hash mismatch) are reported and then overwritten; the projection is one-way, and an edited copy of forgotten content is never preserved.

## 10. Forget and correction

- **Forget preview** lists, per registered projection, how many owned files contain affected items.
- **After the Forget commits:** delete owned files for forgotten IDs, regenerate notes that linked them (no dangling links), remove their manifest entries, and report the outcome. If a projection is unavailable (for example an unplugged drive), keep a content-free pending list of IDs, show "Forget incomplete for projection X", and finish on the next run or start.
- **Correction:** regenerate the new revision, the superseded revision (now with `CORRECTED_BY`), and every claim citing it (now `stale`).
- **Disclose what Sovereign cannot erase:** Obsidian's own caches and file-recovery snapshots in its application data, trash folders, OS backups and search indexes, sync services and plugins. Secure erasure is not claimed.

## 11. Privacy and boundaries

- Local only. No Git check-in, Obsidian Sync, cloud drive, publishing or plugin is enabled by Sovereign; opening the vault in an Obsidian with sync or plugins configured may copy it, and the preview says so.
- Sensitive items excluded by default; including them requires an explicit flag and forces opaque filenames for those items.
- No plugin is required. Community plugins (some send note content to cloud models) are the user's choice; Obsidian's Restricted mode keeps them off.
- Durable IDs appear in frontmatter. That is acceptable locally; it is one reason the vault must not be synced or published by default.

## 12. Acceptance tests (SB-2)

1. Every wikilink resolves; basenames are unique case-insensitively; filenames are sanitized and NFC.
2. Statuses, support and authority in notes equal the compiler's view at export time.
3. Graph lines correspond one-to-one to canonical relationships, plus lineage reverse links only.
4. After Forget, a canary string from the forgotten record appears in no owned file, the manifest or the registry; no link dangles.
5. After correction, the superseded revision, its successor and every citing claim are regenerated.
6. An interrupted export is completed by the next run; files without the ownership marker are never modified or deleted.
7. Export refuses Git working trees and non-owned non-empty folders.
8. Sensitive items and proposals are absent from the default scope.
9. Export never writes to canonical tables (verified by comparing the canonical export before and after).
10. Manual: the demo-equivalent synthetic projection opens in Obsidian; Graph view, Local graph (depth 2) and Backlinks behave as described in Start Here.
