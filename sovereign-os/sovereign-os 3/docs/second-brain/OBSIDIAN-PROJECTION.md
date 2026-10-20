# Obsidian Projection — format and behavior (proposed v1)

**Status:** PROPOSED specification for slice SB-2 and later slices of [ADR-0005](../adr/0005-governed-second-brain-architecture.md); no exporter exists. Revision 2 (2026-10-20) adds the export/Forget protocol (Codex F2), inert serialization (F3) and scope closure (F4), and corrects Animate (F6); it was hardened by independent red-team reviews whose attacks are reflected in the rules and in the [validation spec §4](SECOND-BRAIN-VALIDATION.md#4-obsidian-projection-sb-2). Founder decisions it depends on: D7, D8, D9 and D12–D14. The [demo vault](obsidian-demo-vault/) is a hand-written instance of this format.

## 1. Purpose and non-goals

**Purpose:** let the person explore Sovereign's knowledge visually and navigably in Obsidian — Graph view, Local graph, Backlinks, search — and answer "what is connected to this, why, and since when?" from the notes themselves.

**Non-goals:** the projection is not memory, not a backup, not a sync target, not an editing surface and not a source of authority. Removing Obsidian or the projection changes nothing in Sovereign.

## 2. What the projection may contain

Only canonical state, rendered deterministically. "Today" means derivable from the current schema once the exporter exists.

| Element | Canonical basis | Available |
| --- | --- | --- |
| Source notes: content, stored time, active/superseded, sensitivity | `records` | Today |
| Revision chains (`CORRECTS` / `CORRECTED_BY`) | `records.supersedes_id` | Today |
| Claim notes: text, status, support, authority, origin | `claims`, `claim_sources`, derived support | Today |
| `SUPPORTED_BY` links (verified evidence only, §8) | `claim_sources` | Today |
| Claim supersession chains (`SUPERSEDES` / `SUPERSEDED_BY`) | `claims.supersedes_id` | Today |
| Decision history per claim | `claim_events` | Today |
| Timeline and status index notes | Stored and decision times | Today |
| Note titles | None: derived from the item's own text (§5) | Today, with D7 privacy rules |
| Project and concept hubs, membership | Human-declared organization | After SB-3 (D2) |
| Decisions as their own folder | A claim form/kind | After SB-3 or SB-7 |
| Typed domain relations | Structured MemoryClaims | After SB-7 (D3) |
| `valid_from` / `valid_until`; correction vs change | Temporal claim extension | After SB-6 (D10) |

Anything not in this table — model summaries, inferred entities, co-occurrence links, similarity links — is **not** projected. Records carry no import marker, so a projection cannot truthfully say whether a record was captured or imported; it says "stored".

## 3. Obsidian capabilities this format relies on

Core features only, checked against Obsidian's published help; every behavior the guarantees depend on is verified natively per supported version (validation spec §4.2).

- **Graph view / Local graph:** one line per linked note pair; *Arrows* shows direction; *Groups* color nodes by a search query; a filter query hides notes; *Tags* and *Orphans* toggles; Local graph depth. **Node labels are note names, i.e. filenames.**
- **Animate:** shows notes appearing in file-creation order on that disk. It is **not** a history view: it knows nothing of stored times, corrections, supersessions or MemoryClaim status changes, and the exporter makes no attempt to control it. Chronology is in the Timeline and decision-history notes (§9).
- **Backlinks pane:** incoming links for the open note — the reverse direction of every relationship without writing reverse links.
- **Properties:** YAML frontmatter is shown and searchable. A quoted `"[[...]]"` property value is a documented internal link, so no property value may ever contain link syntax (§6); graph-relevant links live in the note body only.
- **Not available:** edge labels, edge properties, per-edge colors, typed or temporal edges, clicking an edge.

## 4. Vault layout

```text
<projection root>/                      chosen by the user; outside any Git working tree and any other Obsidian vault
  .sovereign-projection.json            root marker: format and projection_id only; no content, no installation ID
  _Navigation/                          hidden from the default graph by tag
    Start Here.md                       generation, date, class-level scope, legend, how to read lines
    Timeline.md                         stored and decision events of included items
    Claims by status.md                 approved / stale / contested / proposed / superseded / rejected
  Projects/   Concepts/                 hubs (after SB-3)
  Sources/                              one note per record revision
  Claims/     Decisions/                one note per claim (Decisions/ once a claim form exists)
  Relationships/                        one note per structured relation claim (after SB-7)
  .obsidian/graph.json                  optional default graph settings, constants only (§10)
  .sovereign-staging/                   exists only while a run is publishing (§11)
```

The fixed set of kind folders is created on every run, empty or not, so a folder's existence reveals nothing. The **projection registry** (§11.1) lives in Sovereign's data directory beside the vault, never in the projection.

## 5. Identity, handles, filenames and titles

- **Handle:** each projection has a random key `k_P` kept in the registry. An item's handle is its kind letter, a hyphen and the first 8 characters of the lowercase base32 encoding of HMAC-SHA256(`k_P`, `sovereign-projection/v1` NUL kind NUL canonical ID). Handles are stable within a projection, differ between projections of the same vault (so two exports cannot be correlated), and cannot be computed by anyone who only guesses an ID. Uniqueness is checked case-insensitively **within the authorized set only**; only colliding handles are extended.
- **Identity in the note:** `sovereign_handle` always; the raw `sovereign_id` only when it is a canonical UUID string (D13). Imported, restored and legacy IDs can be arbitrary, sequential or meaningful text, and a sequence gap would reveal an excluded item.
- **Filename (D7):** `<title> (<handle>).md`; opaque mode `<handle>.md`. Graph labels are filenames, so readable titles make the graph usable; filenames also appear in OS listings, search indexes, backups and sync logs, which is a disclosure surface. Only the final parenthesized token is generated.
- **Title:** from the item's **own text only** — never from a neighbour, never an ordinal, chain position or "N of M". Take the first non-blank line; apply NFC; keep characters of Unicode general categories Lu, Ll, Lt, Lo and Nd (excluding default-ignorable code points and the Hangul fillers U+115F, U+1160, U+3164, U+FFA0) plus space, `-`, `.`, `,`, `'` and `&`; map everything else to `-` (so `( ) _ [ ] ! # ^ | < > ` * ~ % $ : = { } \ /` and all other symbols can never form syntax or imitate a handle); collapse runs; strip leading and trailing space, `.` and `-`; truncate at a word boundary to 60 characters; use `Untitled <kind>` if empty; prefix `Item ` to a Windows reserved device name. Relationship titles are composed from their endpoints' titles and the predicate constant. Two revisions of one record usually share a title; their handles and status tell them apart.
- **Links:** `[[<basename>|<title>]]`, unique by basename, never with a folder path, subpath or embed.
- **Renames:** a changed title renames the file and rewrites links to it in the same run; the old path is deleted (§11.3). Users should keep their own notes outside the projection; links from them are never maintained.

## 6. Note format

### 6.1 Value classes

Every byte written belongs to one class, whatever path the data arrived by (UI, ordinary import, trusted restore or legacy migration — all are untrusted for rendering):

| Class | What | Where it may appear |
| --- | --- | --- |
| G | Generated constants (headings, banners, labels, fixed sentences) | Anywhere |
| E | Closed enums re-validated against the storage CHECK sets: kind, status, support, origin/actor, sensitivity, transitions | Prose, tables, frontmatter, tags |
| N | Exporter-computed numbers, booleans, handles | Prose, tables, frontmatter |
| T | Canonical times: a stored string matching `YYYY-MM-DDTHH:MM:SS+00:00` that parses, re-formatted by the exporter; anything else renders as the fixed *time not recorded* | Prose, tables, frontmatter |
| S | Sanitized titles (§5) | Filename, H1, link display text, frontmatter `title` |
| L | Generated links between authorized items (§8) | Generated list items under predicate headings |
| U | Everything else: record content, claim text, decision notes, cited passages, `records.source`, nonstandard times, future descriptions | **Only** inside an inert block (§7) |

### 6.2 Frontmatter

Keys in fixed order: `sovereign_projection`, `sovereign_handle`, `sovereign_id` (canonical UUID only), `kind`, `title`, `status`, `support`, `authoritative`, `origin`, `sensitivity`, `created_at` (class T only), `provenance` (`partial`, §8, absent otherwise), `tags`, and future fields only once canonical (`claim_form`, `predicate`, `valid_from`, `valid_until`, `supersession_reason`). Navigation's Start Here alone carries `generation`, `generated_at` and a class-level `scope`. **Item notes carry no run stamp**, so an unchanged item's file stays byte-identical across runs (§8). Strings are double-quoted and escape-free by construction: every value must match its key's grammar, which excludes `"`, `\`, control characters, `[`, `]`, `|`, `#` and `://`; the emitter refuses anything else. One key per line, no folding. Tags only from the fixed vocabulary `sovereign/<kind>`, `sovereign/status/<status>`, `sovereign/support/<support>`, `sovereign/form/<form>`, `sovereign/navigation`. Never `aliases`, `cssclasses`, `publish`, `permalink` or any content-derived key.

### 6.3 Banner and body

The first body block is the fixed banner: *a snapshot, not memory; Sovereign is authoritative; edits are never imported; lists and links only items included in this export; stored text is shown inert, with invisible or control characters as ⟪U+XXXX⟫; generation and date in Start Here.* Then the H1 (title, optionally prefixed by a generated label such as "Decision:"), one status line built from classes G, E and T, the partial sentence when applicable (§8), and the **fixed section set of the kind**, each listing only included links, ordered by the endpoint's own time and handle, or the fixed *None in this export.*:

- **Source:** `## Content` (inert block), `## CORRECTS`, `## CORRECTED_BY`. A superseded revision says *superseded — no longer the current revision in Sovereign*, with no "by", date or pointer to the other endpoint.
- **Claim / decision:** `## Claim text` (inert), `## SUPPORTED_BY` (with each source's stored time and state), `## SUPERSEDES`, `## SUPERSEDED_BY`, `## Decision history` — a table of per-claim ordinal, stored time (class T), transition and actor only (never `claim_events.seq`), followed by the free-text decision notes in one inert block keyed by ordinal. A stale claim says *evidence it cites has been corrected*, without saying which.
- **Hub (after SB-3):** what a human filed here, grouped as current decisions, earlier decisions, claims needing attention, and sources, always with *Lists only items included in this export.*
- **Relationship (after SB-7):** subject, predicate (registry version), object, status; `## Why this connection exists` with one line per cited record and its cited passage in an inert block; decision history.
- **Navigation:** Start Here (generation, date, class-level scope, legend, the generic explanation of partial notes), Timeline and status indexes; excluded from the graph by default.

**One canonical relationship, one link, one explanation.** The link sits in the note that holds the relationship (claim → sources; revision → predecessor; claim → predecessor claim; hub → members; relation → subject, object and evidence) under a heading naming the predicate. Reverse links are written only for lineage (`CORRECTED_BY`, `SUPERSEDED_BY`), so an outdated note points to its replacement when that replacement is included; everything else is reached through Backlinks.

## 7. Inert serialization of untrusted text (Codex F3)

Class U text is **data, never markup**. Only exporter code creates active Obsidian constructs. A blockquote is not enough: links, embeds, tags, HTML and callouts stay active inside blockquotes.

1. **Escape, never normalize.** Convert CRLF to LF. Replace with a visible `⟪U+XXXX⟫` marker: `⟪` itself; a lone CR; every control character except tab and LF (including NUL, VT, FF, DEL, C1 and NEL); U+2028 and U+2029; format characters (bidirectional controls, zero-width characters, BOM, soft hyphen, tag characters) and other default-ignorable code points; private-use and unassigned code points; combining marks after the third consecutive one. Neutralize plugin syntax that some plugins read even inside code blocks: a `%` preceded by `<` or `%` becomes `⟪U+0025⟫` (Templater, `%%` comments), and `::` becomes `:⟪U+003A⟫` (Dataview inline fields). Untrusted text is **never** Unicode-normalized: normalization can turn characters such as U+1FEF and U+FF40 into backticks.
2. **One top-level block per value.** Each U value is written as its own fenced code block with the info string exactly `text`, at document top level and column 0 — never inside a list, blockquote, callout, table, footnote or HTML — preceded by a generated label line stating its length and line count and a blank line, and followed by a blank line and the generated line *End of stored text.*
3. **Unclosable fence.** The fence is backticks, one longer than the longest backtick run found in the escaped text **and** in its NFC, NFD, NFKC and NFKD forms (minimum 3).
4. **Forbidden placements.** U text, or anything derived from it other than through the title rule, never appears in a heading, paragraph, list item, table cell, link target or display text, inline code, callout, frontmatter, filename, folder name or `graph.json`.
5. **Generated constructs only.** Wikilinks only from the authorized edge set; no embeds, Markdown `[..](..)` links, autolinks, URLs or URI schemes, HTML, inline or body tags, footnotes, block IDs or comments are ever generated; callouts only the fixed banner and the fixed proposal warning. Since nothing generated references a network resource, any network request while viewing a projection is a defect.
6. **Bytes.** UTF-8 without BOM, LF only, final LF; the same snapshot, format version and pinned Unicode data version give byte-identical output.
7. **Root safety.** Refuse a root inside another Obsidian vault (any ancestor with `.obsidian/`) unless explicitly confirmed. The preview lists community plugins enabled for the root, warns about plugins that execute or upload note content (for example Templater with trigger-on-creation, AI assistants, sync), and states that guarantees cover core Obsidian plus the tested plugin versions only. Restricted mode is recommended.

## 8. Scope and reference closure (Codex F4)

An export must not reveal objects outside its scope through links, titles, filenames, handles, IDs, frontmatter, folders, navigation, metrics, the registry or its own logs.

1. **Inside the fence.** The snapshot, the authorized set and the rendering are all computed inside the export fence (§11.2).
2. **Scope by class.** The user confirms a scope by filter class: kinds, statuses, a date range, sensitivity (default: private only), proposals (default: unreviewed `model` or `imported` proposals excluded). A time counts only if it is class T; an unparseable time fails every bounded range. A claim's sensitivity is computed exactly as the Context Compiler computes it. Nothing is ever added to complete a link (**no widening**).
3. **Naming closure.** Remove every object whose rendered fields would name an object outside the set — today none; after SB-3/SB-7, relation claims whose subject or object is outside, hubs whose entity is outside — repeating to a fixpoint. The result is the authorized set **A**.
4. **Slots.** For each item in A, list only the slots it **holds**, from canonical columns: a record's predecessor and successors; a claim's evidence links, predecessor and successor. A `superseded` item with no successor in A has an out-of-set successor slot. Inbound edges are never slots: a record cited by an excluded claim is unaffected.
5. **OUT is one class.** Excluded, forgotten, missing, never-existing and malformed endpoints are treated identically, so forgetting an endpoint that was already outside A changes nothing.
6. **Edges.** Only in-set slots become links. Never compose edges: no transitive `CORRECTS`/`SUPERSEDES` across an omitted node, no "latest revision" shortcut, no link from a claim to a revision it never cited. `SUPPORTED_BY` links only to evidence whose pinned hash still matches (active or superseded); unverified or missing evidence is an OUT slot, which also keeps a squatted record ID from being linked to a genuine claim.
7. **Mode (D12).** *Label* mode: an item with an OUT slot carries the fixed sentence *"Provenance partial: at least one directly linked item is not included in this export."* exactly once, directly after the status line, never inside or next to a section, and gets `provenance: partial`; its sections list only included links or *None in this export.* *Closed* mode: repeatedly drop every item with an OUT slot until nothing changes, leaving only provenance components wholly inside scope, with no partial sentence.
8. **Wording.** The sentence and its surroundings never carry a count, title, handle, ID, date, status, sensitivity, kind word, relation word, reason or ordering word. Item status wording never refers to the other endpoint. Data attached to an omitted edge — such as the note and time of the transition into `superseded` when the successor is out of the set — is omitted as if absent. Completeness is never claimed: no "No corrections", "uncited", "original", "only source" or "no trace"; empty sections say *None in this export.* and every note says it lists only included items.
9. **Navigation and metrics.** Start Here, Timeline, status indexes and hubs are built from A and its edges only. A Timeline entry relates two objects only if both are in A; otherwise it shows the included object's own event; derived-state events ("became stale") appear only if their cause is in A. Start Here describes scope by class only and explains the partial sentence generically ("a filter, the date range, review status, sensitivity, or because the item is no longer in Sovereign"), never with examples. Health metrics, "most recent N" lists and counts are computed over A. Counts of excluded items appear only in the interactive terminal preview, never on disk.
10. **Invariant.** For two vault states that agree on A, on every A item's own row and events, on the edges and on the partial flags, every owned file and every registry row (apart from counters) is byte-identical. Changes outside A write, touch and rename nothing.
11. **Residuals stated in the preview.** Free text inside included items may mention excluded things (content, rendered inert); a partial sentence reveals that something linked is not included; an included item's own truthful status or support (for example *stale*) may reflect an excluded neighbour; someone who keeps successive generations sees changes. Closed mode and export into a fresh folder reduce these.

## 9. Time in the projection

- Statuses are "as of" the generation stated in Start Here.
- Revision and supersession chains are navigable both ways within the authorized set.
- Every claim note carries its decision history; Timeline lists stored, correction, approval, contest and supersession events of included items in order, under §8.9.
- Until SB-6, `superseded` is rendered as "no longer the current approved interpretation" and never as "false"; the supersession reason appears only once it exists canonically.
- Obsidian's *Animate* is not used to convey history (§3).

## 10. Making the graph meaningful in daily use

A graph is useful when a local neighborhood answers a question; a global hairball is decoration. Defaults:

- **Filter** `-tag:#sovereign/navigation`; **Tags** off; **Arrows** on; **Orphans** on (an item not cited by any claim in this export is informative).
- **Color groups, applied top-down, by generated tags only** (content cannot forge them, and folder-substring queries could be matched by titles): superseded (grey), stale (amber), contested (orange), proposed (purple), then projects, concepts, sources, decisions, claims, relationships.
- **Start from a hub or claim with Local graph, depth 1–2**, not from the global graph.
- **Health metrics reported by the exporter over A:** link resolution (must be 100%), orphan share, largest component share, maximum hub degree, share of readable titles.

`.obsidian/graph.json` is Obsidian's own, undocumented settings file. The exporter may write it only into a projection it created, only with these constants, and Start Here repeats the settings for manual use.

## 11. Export, Forget and recovery protocol (Codex F2)

**The race to prevent:** (1) an exporter reads a snapshot containing X; (2) Forget removes X and finishes its cleanup; (3) the exporter publishes its old snapshot; (4) X reappears in the projection. Filesystem writes are never atomic with SQLite transactions, so the protocol guarantees **ordering and eventual reconciliation with visible pending state**, not atomicity.

### 11.1 State

- **Projection registry** — non-canonical operational state in a separate SQLite file in Sovereign's data directory, beside the vault and never inside a projection; opened in rollback-journal mode with `secure_delete`, file mode 0600; not exported or restored; one per installation; no canonical schema change (registry placement is D14). Per projection: `projection_id`, root path, key `k_P`, confirmed scope (filter classes), mode, `status` (`publishing`, `clean`, `pending`, `needs_attention`), `generation`, and the record and claim tombstone counts at its last successful reconciliation. Per owned file: **handle, kind, content hash and state only** — no path, title or ID of any item, and no list of the items a file mentions. Files are located by the handle in their name.
- **Root marker** `.sovereign-projection.json`: format and `projection_id` only.
- **Ownership:** the exporter may modify or delete a file only if it lies under `.sovereign-staging/`, or the registry holds its handle and the file's bytes match the recorded hash. A marker or a matching name alone never authorizes deletion. Files are never opened through symbolic links: every path is opened without following links and its resolved location is checked to be inside the root.

### 11.2 The fence and the linearization point

Every canonical mutation — capture, correction, claim decision, record Forget, claim Forget, import, trusted restore — already begins with `BEGIN IMMEDIATE` on the vault. An export or reconciliation run takes the **same write lock** (`BEGIN IMMEDIATE`, writing nothing to the vault) and holds it from its snapshot read until its last file operation and directory sync. That lock, not any journal-mode side effect, is the fence: it excludes every canonical writer in both rollback-journal and WAL modes, while previews and searches keep reading.

- **Linearization:** an export's published files equal canonical state at the moment it acquired the fence, and no canonical mutation can commit until it releases. A Forget is linearized at its commit. So a Forget that committed before the fence is absent from the published snapshot, and a Forget that commits after it reconciles the published files.
- **Multiple exporters:** two runs on one installation serialize on the same lock. A root whose marker names a projection this registry does not hold is refused; an OS advisory lock on the marker, released if the process dies, prevents two processes writing one root at once.

### 11.3 Export run

1. **Preview and confirm** the class-level scope, mode, root, filename mode and counts (counts of excluded items appear only here, interactively). Refuse a root inside a Git working tree or another Obsidian vault, a non-empty folder without this projection's marker, and network or cloud-synced locations, unless explicitly confirmed where §7.7 allows.
2. **Register first:** commit (and sync) the registry row with `status = publishing` and the new `generation` **before any file is written**; write and sync the root marker for a new root.
3. **Take the fence.** If the busy timeout expires, stop with "vault busy" — nothing but the registration exists.
4. Inside the fence: **read one snapshot**, compute A (§8) and render every note. **Preview binding:** if A's counts by kind or the include flags differ from the confirmed preview, stop and re-preview (the export analogue of "the preview is the plan").
5. Inside the fence, **publish in this order**: (a) record each file about to be written as a pending registry row (handle and new hash); write it to `.sovereign-staging/`, sync it, and rename it into place, but only if its bytes differ — so files that stop linking to a leaving item are rewritten first; (b) delete every owned file whose handle is not in A, every second path of an included handle (old title, user rename), and the staging folder; (c) **sync every touched directory**. At every interruption point no owned note links to a deleted note.
6. Inside the fence, **self-check** in memory: re-parse every written note and assert that its links equal the authorized edges, its partial flag is the computed one, and no title, handle, ID, time or content of any out-of-set item appears in any owned file or registry row; on any hit, stop with `status = publishing` and let recovery handle it.
7. Inside the fence, **commit the registry**: rows for A only, `generation`, the tombstone counts read in step 4, `status = clean`.
8. **Release the fence.**

### 11.4 Forget, claim Forget and trusted restore

- The canonical operation is unchanged. It cannot commit while a run holds the fence: it waits up to the busy timeout and, if the run is still going, **fails as busy without forgetting anything**; the user retries. A Forget is never partially applied.
- After it commits, the same process first scrubs the registry without touching any root (rows whose handles belong to forgotten items become pending and lose their hash), then runs **reconciliation** for every registered projection: steps 3–8 of §11.3 against the current snapshot. Owned files of forgotten records, revisions and claims are deleted; surviving notes whose rendering changes because a neighbour left A are rewritten. Reconciliation is the export code path, so there is one protocol, not two.
- **Every tombstone path** is covered the same way: record Forget (with earlier revisions and dependent claims), direct claim Forget, and a trusted restore whose tombstones dominate. Ordinary import cannot forget.
- **Which changes need reconciliation:** in V0 an item's sensitivity is immutable and a live claim's inherited sensitivity cannot rise without Forget, so privacy-relevant membership changes only through tombstones. Status changes (contest, supersession, correction) can still move items in or out of a status-scoped export; they make a projection stale, not unsafe, and are picked up by the next run. Any future mutable sensitivity (for example of SB-3 entities) must trigger reconciliation.

### 11.5 Pending cleanup and acknowledgment

- **Pending is derived, not stored separately:** a projection is pending when the vault's current record or claim tombstone count exceeds the counts stored at its last reconciliation, or its status is not `clean`. Tombstones are permanent and insert-only, so the counts are monotonic and durable; pending cleanup is always reconstructible after a crash, without an outbox.
- Sovereign attempts reconciliation of pending projections after each Forget or trusted restore and at start-up, whenever the root is available.
- **The Forget preview** reports, per registered projection, how many of its files would be deleted or rewritten (the plan's items found among A's handles, plus included neighbours whose bytes would change), and which projections are unavailable. Over the unauthenticated local HTTP API it identifies projections by ID and counts, not by folder path.
- **The Forget result** reports the canonical outcome separately from each projection: `reconciled`, `pending` (root unavailable, vault busy, or failed), or `needs attention` (marker missing or foreign, or an owned file edited outside Sovereign that still contains forgotten content). It says "forgotten in Sovereign", never "deleted everywhere", and always repeats that copies made by sync, backups, plugins or Obsidian's own caches are outside Sovereign's control.
- **Logs and messages** identify files by handle and count only, never by path or title.

### 11.6 Crash recovery, limits and acceptance gates

- **Interrupted before or during publication:** the registry says `publishing` and holds pending rows with hashes for every file written so far, so the next run or start-up deletes the staging folder, verifies hashes, and reconciles. A rename on a local POSIX filesystem leaves either the old or the new file, never a mixture.
- **Interrupted after a canonical Forget, before cleanup:** the tombstone counts exceed the stored counts, so the projection is pending and is reconciled at the next opportunity.
- **Durability:** stored counts advance only after file and directory syncs (step 7 after step 5c), so a power loss cannot leave a projection recorded as clean while an unlinked file reappears.
- **Unavailable root:** pending; Sovereign never writes elsewhere instead.
- **Externally modified root:** a hash mismatch means the user edited an owned file; it is reported as needing attention and is not silently deleted or overwritten; files moved or copied out of their place are unmanaged copies, disclosed in general terms; a missing or foreign root marker puts the projection in `needs_attention`, and Sovereign neither writes nor deletes there until the user explicitly re-adopts the folder.
- **Lost registry** (deleted, reinstalled, or the vault restored into a fresh installation): Sovereign can no longer find earlier projections. The export preview warns about this, and re-adoption is explicit. **Acceptance gate:** SB-2 documents the registry location and the adoption step.
- **Lock duration:** while a run holds the fence, captures, decisions and Forgets wait up to the 10 s busy timeout and then fail cleanly. **Acceptance gate:** SB-2 measures export duration on its synthetic vault with a reproducible procedure committed in that PR (not Benchmark 0003's indicative timings). If runs can approach the timeout, SB-2 adopts the staged variant — render and stage outside the fence, then, inside a short fence, re-read the tombstone counts; if they changed, re-render the affected files before renaming. The linearization argument is the same with a shorter critical section.
- **Obsidian's own state and other copies:** workspace files, File recovery snapshots, Obsidian's caches, trash folders, OS search indexes and backups, and sync services can keep titles or content of removed notes; the exporter never touches them, and the preview and Forget results say so. After narrowing a scope, exporting into a fresh folder is recommended.
- **Network or synced folders:** refused by default; their rename and sync semantics are weaker, and a sync client may copy staged files before cleanup.

### 11.7 Alternatives considered

- **Transactional outbox table:** unnecessary; the tombstone tables already are a durable, monotonic record of what was forgotten.
- **Reconciliation without a fence:** rejected; it cannot stop step 3 of the race, a stale publication after cleanup has finished.
- **Generation fencing with staging outside the lock:** correct, but more moving parts; kept as the fallback in §11.6.

## 12. Privacy and boundaries

- Local only. No Git check-in, Obsidian Sync, cloud drive, publishing or plugin is enabled by Sovereign; opening the vault in an Obsidian with sync or plugins configured may copy it, and the preview says so.
- Sensitive items excluded by default; including them requires an explicit flag and forces opaque filenames for those items.
- Raw canonical IDs appear only as UUIDs in frontmatter (D13); that is one more reason the vault must not be synced or published by default.
- The CLI writes only to roots the user registered; a Forget-triggered reconciliation writes only to registered roots, never to a path supplied by an HTTP request.

## 13. Edits

The projection is one-way and never imports edits. An owned file edited outside Sovereign is reported and left for the user to resolve (§11.6), because silently overwriting it would destroy their work and silently keeping it would keep content Sovereign may have to forget. A governed import of edits would need its own ADR.

## 14. Validation

All acceptance tests live in the [validation spec §4](SECOND-BRAIN-VALIDATION.md#4-obsidian-projection-sb-2): structure (§4.1), inert serialization (§4.2), scope closure (§4.3), export versus Forget (§4.4) and usability (§4.5). Native Obsidian checks have not yet been executed in any review environment.
