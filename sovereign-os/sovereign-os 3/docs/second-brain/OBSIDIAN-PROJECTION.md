# Obsidian Projection — format and behavior (proposed v1)

**Status:** PROPOSED specification for slice SB-2 and later slices of [ADR-0005](../adr/0005-governed-second-brain-architecture.md); no exporter exists. Revision 2 (2026-10-20) adds the export/Forget protocol (Codex F2), inert serialization (F3) and scope closure (F4), and corrects Animate (F6). Founder decisions it depends on: D7 (filenames), D8 (Forget cleanup), D9 (rebuild trigger). Tests: [validation spec §4](SECOND-BRAIN-VALIDATION.md#4-obsidian-projection-sb-2). The [demo vault](obsidian-demo-vault/) is a hand-written instance of this format.

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
| Decision history per claim | `claim_events` | Today |
| Timeline and status index notes | Capture and decision times | Today |
| Note titles | None: derived from the first line of the text (§5) | Today, with D7 privacy rules |
| Project and concept hubs, membership | Human-declared organization | After SB-3 (D2) |
| Decisions as their own folder | A claim form/kind | After SB-3 or SB-7 |
| Typed domain relations | Structured MemoryClaims | After SB-7 (D3) |
| `valid_from` / `valid_until`; correction vs change | Temporal claim extension | After SB-6 (D10) |

Anything not in this table — model summaries, inferred entities, co-occurrence links, similarity links — is **not** projected. A "related notes by similarity" view, if ever wanted, is a local UI feature, not Markdown links.

## 3. Obsidian capabilities this format relies on

Core features only, checked against Obsidian's published help; verify against the installed version.

- **Graph view / Local graph:** one line per linked note pair; *Arrows* shows direction; *Groups* color nodes by a search query (`path:`, `tag:`, `[property:value]`); a filter query hides notes; *Tags* and *Orphans* toggles; Local graph depth. **Node labels are note names, i.e. filenames.**
- **Animate:** shows notes appearing in file-creation order on that disk. It is **not** a history view: it knows nothing of capture times, corrections, supersessions or MemoryClaim status changes, and the exporter makes no attempt to control it. Chronology is in the Timeline and decision-history notes (§9).
- **Backlinks pane:** incoming links for the open note — the reverse direction of every relationship without writing reverse links.
- **Properties:** YAML frontmatter is shown and searchable. Links inside properties are handled differently across versions, so **graph-relevant links live in the note body**, never only in properties.
- **Not available:** edge labels, edge properties, per-edge colors, typed or temporal edges, clicking an edge.

## 4. Vault layout

```text
<projection root>/                      chosen by the user; outside any Git working tree
  .sovereign-projection.json            root marker: projection id and installation id; no content
  _Navigation/                          excluded from the graph by the default filter
    Start Here.md                       scope, legend, how to read lines, paths to try
    Timeline.md                         chronological capture and decision events (in scope)
    Claims by status.md                 approved / stale / contested / proposed / superseded
  Projects/   Concepts/                 hubs (after SB-3)
  Sources/                              one note per record revision
  Claims/     Decisions/                one note per claim (Decisions/ once a claim form exists)
  Relationships/                        one note per structured relation claim (after SB-7)
  .obsidian/graph.json                  optional default graph settings (§10)
  .sovereign-staging/                   exists only while a run is publishing (§11)
```

The **projection registry** (§11.1) lives in Sovereign's data directory beside the vault, never in the projection, so sync services and plugins pointed at the vault do not receive the ID-to-path map. Obsidian does not index dot-prefixed files and folders; that is verified natively, not assumed (validation spec §4.2).

## 5. Identity, filenames and links

- **Identity** is `sovereign_id` in frontmatter, never the filename.
- **Filename (D7 recommendation):** `<readable title> (<short id>).md`. Graph labels are filenames, so readable titles are what make the graph usable; the short ID prevents collisions and silent merges when two titles match.
- **Short ID:** `<kind letter>-<first 6 hex digits of SHA-256 of the canonical ID>`, lengthened two digits at a time until unique case-insensitively within the projection. Never derived from the raw ID: legacy ADR-0002 IDs can be arbitrary text.
- **Opaque mode:** `<short id>.md` for users who do not want content in filenames. Filenames appear in OS file listings, search indexes, backups and sync logs; that is a disclosure surface.
- **Title derivation:** first line of the text, whitespace-collapsed, Unicode NFC, characters outside the whitelist (letters, digits, space and `- _ . , ' ( ) &`) replaced with `-`, truncated at a word boundary to ≤ 60 characters, `Untitled` if empty. The whitelist excludes every character that begins Markdown or Obsidian syntax (`[ ] ! # ^ | < > ` * ~ % $ : = { } \ /`), so a title cannot form a link, embed, tag, entity or HTML. The same sanitized title is used for the filename, the H1 heading, link display text and frontmatter `title`.
- **Renames:** when a title changes, the file is renamed and every link to it is rewritten in the same run; the previous path is deleted (§11). Users should keep their own notes outside the projection, because links from them will not be maintained.
- **Links:** `[[basename]]` or `[[basename|sanitized title]]`; basenames are unique vault-wide, so links never need folder paths. Every link must resolve, and every link is generated (§7–§8).

## 6. Note format

Every generated note starts with frontmatter and the snapshot banner.

| Property | Kinds | Meaning |
| --- | --- | --- |
| `sovereign_projection` | all | Format version (`1`) |
| `sovereign_projection_id` | all | The projection's random ID; with the manifest, identifies exporter-owned files |
| `sovereign_id` | all but navigation | Canonical ID, YAML-escaped (it may be arbitrary legacy text) |
| `kind` | all | `source`, `claim`, `project`, `concept`, `relationship`, `navigation` |
| `title` | all | The sanitized title |
| `status` | all but navigation | Source: `active`/`superseded`. Claim and relationship: lifecycle status. Hub: `active`/`archived` |
| `support`, `authoritative` | claims, relationships | Derived at export: `supported`/`stale`/`orphaned`; `authoritative` = approved and supported |
| `origin` | claims, relationships | `human`, `model`, `imported` |
| `sensitivity` | sources, claims | `private` (sensitive items are excluded unless explicitly included) |
| `captured_at` / `created_at` | sources / claims | Canonical times |
| `provenance` | any | `partial` when a linked item is outside the export's scope (§8) |
| `scope` | navigation (Start Here) | The confirmed export scope, in words |
| `generation`, `generated_at` | all | Projection run that wrote this file |
| `tags` | all | Only from the fixed vocabulary `sovereign/<kind>`, `sovereign/status/<status>`, `sovereign/support/<support>`, `sovereign/form/<form>` — used by graph color groups |
| `claim_form`, `predicate`, `subject`, `object`, `valid_from`, `valid_until`, `supersession_reason` | future | Only when the canonical field exists (SB-3/6/7) |

**Snapshot banner** (first body block; renders as an Obsidian callout and a GitHub alert):

```markdown
> [!NOTE]
> Generated by Sovereign — projection generation 12, 2026-10-19. A snapshot, not memory: Sovereign is authoritative, and edits here are never imported.
```

**Body by kind** (every piece of record or claim text appears only as described in §7):

- **Source:** title; one line with capture time, status ("active evidence — what was written down, not a verified fact") and sensitivity; `## Content` with the text in an inert block; `## CORRECTS` (link to the predecessor revision) and, on a superseded revision, `## CORRECTED_BY` (link to its successor), or the §8 partial sentence when that revision is outside scope. Claims citing it and hubs organizing it appear in Backlinks.
- **Claim / decision:** title; one line stating whether it is approved memory *now* and, if not, why (`proposed`, `contested`, `stale` because evidence was corrected, `superseded`); `## Claim text` (inert block); `## SUPPORTED_BY` (one line per cited record with its capture time and current state); `## SUPERSEDES` / `## SUPERSEDED_BY`; `## Decision history`: a table of generated fields only (number, time, from → to, actor) followed by the free-text decision notes in one inert block, keyed by row number.
- **Hub (after SB-3):** what a human filed here, grouped as current decisions, earlier decisions, claims needing attention (stale/contested), and sources; hubs above a size limit list the most recent N members and link to an index note.
- **Relationship (after SB-7):** subject, predicate (registry version), object, validity, status and decision history; `## Why this connection exists` with one line per cited record and the cited passage in an inert block.
- **Navigation:** Start Here (including the confirmed scope), Timeline and status indexes; excluded from the graph by default.

**One canonical relationship, one link, one explanation.** The link sits in the note that holds the relationship (claim → sources; revision → predecessor; claim → predecessor claim; hub → members; relation → subject, object and evidence) under a heading naming the predicate. Reverse links are written only for lineage (`CORRECTED_BY`, `SUPERSEDED_BY`), because a reader who lands on an outdated note must be sent to the current one; everything else is reached through Backlinks. Never link two notes whose connection is not a canonical fact — for example, a stale claim does not link to the corrected revision it never cited.

## 7. Inert serialization of untrusted text (Codex F3)

Text that came from a person, an import or a model — record content, claim text, decision notes (`claim_events.note`), cited passages, and later entity or relationship descriptions — is **data, never markup**. Only the exporter's own code creates active Obsidian constructs, and only from the authorized canonical relationship set (§8). A Markdown blockquote is not enough: links, embeds, tags, HTML and callouts stay active inside blockquotes.

1. **Normalize:** CRLF and CR → LF; C0 control characters (except tab and LF) and DEL → U+FFFD; bidirectional controls and zero-width characters → visible `<U+XXXX>` markers; Unicode NFC.
2. **Fence:** emit each untrusted string only as the entire content of a generated fenced code block with the info string exactly `text`, using a backtick fence one longer than the longest backtick run in the string (minimum 3), unindented. Inside a fenced block CommonMark and Obsidian render text verbatim: no wikilinks, embeds, images, Markdown links, HTML, tags, callouts, block references, comments, inline fields or headings are recognized, and the content cannot close the fence.
3. **Never elsewhere:** untrusted text never appears in a heading, table cell, list text, link target or display text, callout, filename or frontmatter. Titles reach those places only through the whitelist (§5); raw canonical IDs reach frontmatter only YAML-escaped.
4. **Frontmatter:** a fixed key schema, fixed value types, strings as YAML double-quoted scalars with backslash, quote and control characters escaped; `tags` only from the fixed vocabulary (§6). No content can add a key, a tag, a status or an ownership marker.
5. **Generated constructs only:** wikilinks only between authorized nodes; no Markdown-style links, embeds, images, HTML, inline tags, block IDs or comments are ever generated; callouts only the fixed snapshot banner and the fixed proposal warning.
6. **No network surface:** no generated construct references a URL. Any network request while viewing a projection is therefore a defect, and the native test requires zero.
7. **Limits:** the guarantee covers core Obsidian. Community plugins that parse raw note text or execute code blocks by their own rules are outside it; the export preview recommends Restricted mode (no community plugins) for projection vaults. Whether core Obsidian ignores links and tags inside fenced blocks, and dot-prefixed paths, is verified natively for each supported version.

The payload classes the adversarial corpus must cover are listed in the validation spec §4.2.

## 8. Scope and reference closure (Codex F4)

An export must not reveal objects outside its scope through links, titles, filenames, IDs, frontmatter, navigation or registry metadata.

1. **Scope first.** The user confirms a scope: kinds, statuses, a date range (capture or creation time), sensitivity (default: private only), and whether unreviewed proposals are included (default: no). Later slices add hubs and projects.
2. **Authorized node set before edges.** From one snapshot, compute the set A of items satisfying the scope. A claim's sensitivity is computed exactly as the Context Compiler computes it (inherited from current evidence; missing or unverified evidence counts as sensitive). A relation claim is in A only if the claim, its subject and its object are all in A. A hub is in A only if its entity is in scope.
3. **Edges only inside A.** A link is emitted only for a canonical relationship whose two endpoints are both in A.
4. **Non-identifying omission.** Where a relationship section has an endpoint outside A, the note contains exactly the fixed sentence *"Provenance partial: at least one linked item is outside this export's scope."* — the same wording whatever the reason or number, with no count, title, ID, date, status, sensitivity or ordering hint — and the note gets `provenance: partial`. An item's own properties (for example a revision's `superseded` status) are still shown, because they belong to the item.
5. **Never widen.** Scope is never enlarged to complete a link or a chain.
6. **Everything derives from A.** Filenames, titles, aliases, tags, hubs, Timeline, status indexes, `graph.json` (which holds no item data) and registry entries are built from A only. Timeline entries for excluded items are simply absent.
7. **Scope changes.** A run with a different scope reconciles: owned files whose items left A (including previously generated and renamed filenames) are deleted, and every surviving note whose links or partial sentences changed is rewritten (§11).
8. **What closure cannot hide.** Free text inside an authorized item may mention excluded things; that is content, guarded by sensitivity inheritance and inert rendering, not structure. A partial sentence reveals that *something* is outside scope, and the overall size of an export is visible. Both are stated in the export preview.

## 9. Time in the projection

- The banner and `generation` make every status explicitly "as of".
- Revision and supersession chains are navigable both ways within scope.
- Every claim note carries its decision history; `Timeline.md` lists capture, correction, approval, contest and supersession events of in-scope items in order.
- Until SB-6, `superseded` is rendered as "no longer the current approved interpretation" and never as "false"; the supersession reason appears only once it exists canonically.
- Obsidian's *Animate* is not used to convey history (§3).

## 10. Making the graph meaningful in daily use

A graph is useful when a local neighborhood answers a question; a global hairball is decoration. Defaults:

- **Filter** `-path:_Navigation` (navigation hubs would otherwise connect everything); **Tags** off (tag nodes would connect every note of a kind); **Arrows** on (links follow the relationship direction); **Orphans** on (an uncited source is informative).
- **Color groups, applied top-down:** superseded (grey), stale (amber), contested (orange), proposed (purple), then kinds: projects, concepts, sources, decisions, claims, relationships. Groups match only the generator's fixed tags, which content cannot forge (§7).
- **Start from a hub or claim with Local graph, depth 1–2**, not from the global graph.
- **Default scope excludes** sensitive items and unreviewed model proposals; a review scope can include proposals, colored distinctly.
- **Health metrics reported by the exporter:** link resolution (must be 100%), orphan share, largest component share, maximum hub degree, share of notes with readable titles. Report them; do not optimize node counts.

`.obsidian/graph.json` is Obsidian's own, undocumented settings file. The exporter may write it only into a projection it created, only with these defaults, and Start Here repeats the settings for manual use.

## 11. Export, Forget and recovery protocol (Codex F2)

**The race to prevent:** (1) an exporter reads a snapshot containing X; (2) Forget removes X and finishes its cleanup; (3) the exporter publishes its old snapshot; (4) X reappears in the projection. Filesystem writes are never atomic with SQLite transactions, so the protocol guarantees **ordering and eventual reconciliation with visible pending state**, not atomicity.

### 11.1 State

- **Projection registry** — non-canonical operational state in a small SQLite file in Sovereign's data directory, beside the vault and never inside a projection; not exported or restored; one per installation. Per projection: random `projection_id`, root path, confirmed scope, `status` (`publishing`, `clean`, `pending`, `needs_attention`), `generation`, and the record and claim tombstone counts at its last successful reconciliation. Its **manifest** lists, per owned file, the path, `sovereign_id`, content hash, the IDs the file names (link targets and partial sentences), and previous paths awaiting deletion. Paths contain titles, so the registry is protected like the vault and cleaned by reconciliation. It needs no canonical schema change.
- **Root marker** `.sovereign-projection.json`: `projection_id` and the installation ID; no content.
- **Ownership:** a file is exporter-owned if the manifest lists it, if it lies under `.sovereign-staging/`, or (during recovery, when the manifest may be behind) if its frontmatter carries this projection's `sovereign_projection_id`. Nothing else is ever modified or deleted.

### 11.2 The fence and the linearization point

Every canonical mutation — capture, correction, claim decision, record Forget, claim Forget, import, trusted restore — already begins with `BEGIN IMMEDIATE` on the vault. An export or reconciliation run takes the **same write lock** (`BEGIN IMMEDIATE`, writing nothing to the vault) and holds it from its snapshot read until its last file operation and directory sync. That lock, not any journal-mode side effect, is the fence: it excludes every canonical writer in both rollback-journal and WAL modes, while previews and searches keep reading.

- **Linearization:** an export's published files equal canonical state at the moment it acquired the fence, and no canonical mutation can commit until it releases. A Forget is linearized at its commit. So a Forget that committed before the fence is absent from the published snapshot, and a Forget that commits after it reconciles the published files.
- **Multiple exporters:** two runs on one installation serialize on the same lock. A run from another installation is refused by the root marker; an OS advisory lock on the marker, released if the process dies, prevents two installations writing one root at once.

### 11.3 Export run

1. **Preview and confirm** the scope, root, filename mode and counts. Refuse a root inside a Git working tree, a non-empty folder without this projection's marker, and network or cloud-synced locations unless explicitly confirmed.
2. **Register first:** commit (and sync) the registry row with `status = publishing` and the new `generation` **before any file is written**. For a new root, write and sync the root marker next.
3. **Take the fence.** If the busy timeout expires, stop with "vault busy" — nothing but the registration exists.
4. Inside the fence: **read one snapshot**, compute the authorized set (§8), render every note (§6–§7), and read the current tombstone counts.
5. Inside the fence: **write** each new or changed note to `.sovereign-staging/`, sync it, and rename it into place (same filesystem); **delete** every owned file that is no longer rendered, including previous filenames and stray marker-carrying files; remove the staging folder; **sync every touched directory**.
6. Inside the fence: **commit the registry** — manifest, `generation`, the tombstone counts read in step 4, `status = clean`.
7. **Release the fence.**

### 11.4 Forget, claim Forget and trusted restore

- The canonical operation is unchanged. It cannot commit while a run holds the fence: it waits up to the busy timeout and, if the run is still going, **fails as busy without forgetting anything**; the user retries. A Forget is never partially applied.
- After it commits, the same process runs **reconciliation** for every registered projection: steps 3–7 of §11.3 against the current snapshot. Owned files of forgotten records, revisions and claims are deleted; surviving notes that named them — a newer revision's `CORRECTS`, a successor's `SUPERSEDES`, hubs, Timeline, status indexes — are rewritten, because the manifest records which files name which IDs. Reconciliation is the export code path, so there is one protocol, not two.
- **Every tombstone path** is covered the same way: record Forget (with earlier revisions and dependent claims), direct claim Forget, and a trusted restore whose tombstones dominate all add tombstones. Ordinary import cannot forget, so it only makes projections stale, never unsafe.
- **Sensitivity:** an item can leave the authorized set only through Forget or a scope change in V0 (record sensitivity is immutable; a claim's inherited sensitivity rises only when evidence goes missing, which Forget causes and cascades). Reconciliation recomputes the authorized set anyway.

### 11.5 Pending cleanup and acknowledgment

- **Pending is derived, not stored separately:** a projection is pending when the vault's current record or claim tombstone count exceeds the counts stored at its last reconciliation, or its status is `publishing`, `pending` or `needs_attention`. Tombstones are permanent and insert-only, so the counts are monotonic and durable; pending cleanup is always reconstructible after a crash, without an outbox.
- Sovereign attempts reconciliation of pending projections after each Forget or trusted restore and at start-up, whenever the root is available.
- **The Forget preview** lists, per registered projection, how many owned files name affected items, and which projections are unavailable.
- **The Forget result** reports the canonical outcome separately from each projection: `reconciled`, `pending` (root unavailable, vault busy, or failed, with the reason) or `needs attention` (marker missing or foreign). It says "forgotten in Sovereign", never "deleted everywhere", and always repeats that copies made by sync, backups, plugins or Obsidian's own caches are outside Sovereign's control.

### 11.6 Crash recovery, limits and acceptance gates

- **Interrupted before the first manifest, mid-staging or mid-rename:** the registry says `publishing`, so the next run or start-up verifies the root marker, deletes `.sovereign-staging/`, scans for files carrying this `sovereign_projection_id`, and reconciles. A rename on a local POSIX filesystem leaves either the old or the new file, never a mixture.
- **Interrupted after a canonical Forget, before cleanup:** the tombstone counts exceed the stored counts, so the projection is pending and is reconciled at the next opportunity.
- **Durability:** stored counts advance only after file and directory syncs (step 6 after step 5), so a power loss cannot leave a projection recorded as clean while an unlinked file reappears.
- **Unavailable root:** pending; Sovereign never writes elsewhere instead.
- **Externally modified root:** edited owned files are overwritten and reported; owned files moved within the root are found by their marker and removed or rewritten; files copied or moved outside the root are unmanaged copies and are disclosed in general terms; a missing or foreign root marker puts the projection in `needs_attention`, and Sovereign neither writes nor deletes there until the user explicitly re-adopts the folder.
- **Lost registry** (deleted, reinstalled, or the vault restored into a fresh installation): Sovereign can no longer find earlier projections. The export preview warns about this, and re-adoption of a folder is explicit. **Acceptance gate:** SB-2 documents the registry location and the adoption step.
- **Lock duration:** while a run holds the fence, captures, decisions and Forgets wait up to the 10 s busy timeout and then fail cleanly. **Acceptance gate:** SB-2 measures export duration on its synthetic vault with a reproducible procedure committed in that PR (not Benchmark 0003's indicative timings). If runs can approach the timeout, SB-2 adopts the staged variant — render and stage outside the fence, then, inside a short fence, re-read the tombstone counts; if they changed, re-render the affected files before renaming. The linearization argument is the same with a shorter critical section.
- **Network or synced folders:** refused by default; their rename and sync semantics are weaker, and a sync client may copy staged files before cleanup.

### 11.7 Alternatives considered

- **Transactional outbox table:** unnecessary; the tombstone tables already are a durable, monotonic record of what was forgotten.
- **Reconciliation without a fence:** rejected; it cannot stop step 3 of the race, a stale publication after cleanup has finished.
- **Generation fencing with staging outside the lock:** correct, but more moving parts; kept as the fallback in §11.6.

## 12. Privacy and boundaries

- Local only. No Git check-in, Obsidian Sync, cloud drive, publishing or plugin is enabled by Sovereign; opening the vault in an Obsidian with sync or plugins configured may copy it, and the preview says so.
- Sensitive items excluded by default; including them requires an explicit flag and forces opaque filenames for those items.
- No plugin is required. Community plugins are the user's choice; Restricted mode keeps them off.
- Durable IDs appear in frontmatter. That is acceptable locally; it is one reason the vault must not be synced or published by default.
- The CLI writes only to roots the user registered; a Forget-triggered reconciliation writes only to registered roots, never to a path supplied by an HTTP request.

## 13. Edits

The projection is one-way. Owned files modified since the last run (hash mismatch) are reported and then overwritten; an edited copy of forgotten content is never preserved. A governed import of edits would need its own ADR.

## 14. Validation

All acceptance tests live in the [validation spec §4](SECOND-BRAIN-VALIDATION.md#4-obsidian-projection-sb-2): structure (§4.1), inert serialization (§4.2), scope closure (§4.3), export versus Forget (§4.4) and usability (§4.5). Native Obsidian checks have not yet been executed in any review environment.
