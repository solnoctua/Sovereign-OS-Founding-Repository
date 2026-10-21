# Second-Brain Validation Specification

**Status:** PROPOSED; no test described here is implemented. This document owns the test requirements for the [ADR-0005](../adr/0005-governed-second-brain-architecture.md) slices *other than* retrieval evaluation. It is a validation specification, not a benchmark, and carries no benchmark number.

**History:** this file began in PR #3 as a draft "Benchmark 0003" retrieval specification. Retrieval evaluation now belongs to the executed Benchmark 0003 in PR #4, so the draft was renamed and narrowed to the provenance graph, the Obsidian snapshot export and later second-brain slices. Nothing in it re-specifies or duplicates PR #4's harness.

## 1. What is validated where

| Area | Owner | State (2026-10-20) |
| --- | --- | --- |
| Retrieval and governed-context evaluation (SB-1) | **Benchmark 0003 — retrieval evaluation**: `docs/benchmarks/0003-retrieval-evaluation.md` and the `evaluation/retrieval/` harness, delivered by [PR #4](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/pull/4) | Executed on synthetic data, evaluation only, **not merged**; at `da52ce9` its Codex P2 finding (scale timings) is resolved by removing the timings, and CI passed. By founder direction (2026-10-20) no production retrieval change is authorized (R1–R7, ADR-0005 §12.2); its remaining founder decisions are listed there |
| A future lexical change (SB-4) | The implementing PR regenerates Benchmark 0003 | **Not authorized** (R1): Porter normalization and the exact-stem tie-break are evaluated candidates only |
| Provenance graph (SB-2) | §3 | Specified, not implemented |
| Obsidian snapshot export (SB-2) | §4 | Specified, not implemented |
| Human-declared organization, temporal claims, structured relations (SB-3, SB-6, SB-7) | §5 | Future; each needs its own ADR |
| Semantic/hybrid experiments (SB-5) | A new retriever inside the **Benchmark 0003 harness**, behind the same `score` seam and ground truth — never a second harness | Deferred (R6) |
| Generated-answer evaluation | §6 | Optional; **not established by SB-1** |

## 2. What Benchmark 0003 establishes, and what it does not

This section reconciles Codex finding F5 (benchmark oracle) with PR #4 as it exists at `da52ce9`.

**Established (non-generative, deterministic):**

- **An explicit oracle.** Each of the 56 queries lists every expected item with its intended governed outcome per target (`evidence`, `approved_memory`, or the exclusion reason such as `superseded`, `stale`, `sensitive_cloud`), plus acceptable items. The ground truth was fixed before any experiment, and the harness validates every expectation against production policy before measuring, stopping on disagreement.
- **Retrieval before policy:** Recall@1/5/10/50 and MRR.
- **Governed context after policy:** governed recall, noise and precision for the local and cloud targets; exclusion reasons; budget binding.
- **A failure taxonomy:** recalled, policy-excluded, no match, provenance only, below cutoff, outranked, budget.
- **Token stability**, measured under an unrelated write (no token changed for text-local scorers; 51–54 of 56 for IDF and BM25 scorers) and on an unchanged vault (56/56 identical for every retriever), and **zero policy violations** for every retriever, with no sensitive item in any cloud plan.
- **Navigation as discovery:** one stored link from what the preview already shows makes 10 of the baseline's 22 missed expected items discoverable without changing relevance, context or token — the SB-2 direction (§3).
- **Isolation:** experiments swap only the `score` function; candidate selection and policy are production code; no provider is called.

**NOT MEASURED:**

- **Generated-answer correctness.** No model is called, so whether an answer is right, grounded or well cited is not measured.
- **Abstention.** Every query has at least one expected item, so neither answer abstention nor retrieval behavior on questions with *no* relevant evidence is measured.
- **Temporal interpretation.** The 5 temporal and 3 correction queries are measured as retrieval ranking and policy outcome (for example temporal MRR, `superseded` exclusions). Whether an answer distinguishes "then" from "now", or a correction from a change, is not measured.
- Pinned questions, languages other than English, and real usage frequencies (the corpus is self-authored and over-represents hard cases by design).

**Scale and latency:** NOT MEASURED. PR #4 removed its indicative scale timings at `da52ce9`, resolving its Codex P2 finding; PR #3 never relied on them, and incidental container timings are not an architectural capacity guarantee.

**Remaining gaps and where they belong:**

| Gap | Why it matters | Where |
| --- | --- | --- |
| No-evidence queries | Measures what would be offered for disclosure when nothing is relevant (R4). Partly covered for cloud: six queries whose expected items are all `sensitive_cloud` already report cloud noise (22 items under the baseline, 12 in q40; 33 under Porter normalization). Still missing: questions with no relevant item at all, local and cloud | A follow-up Benchmark 0003 harness PR (PR #4 defers them because they change the fixture; a founder decision there) — not PR #3 |
| Generated answers, abstention, temporal interpretation | Answer quality is a different property from retrieval | §6, a separate optional evaluation with its own PR and number |
| Snapshot export and graph behavior | Not retrieval | §3–§4 of this spec |

## 3. Provenance graph (SB-2)

The provenance graph is computed on read from `claim_sources`, `records.supersedes_id` and `claims.supersedes_id` (ADR-0005 §8.1).

1. **Edges are exactly canonical:** every `SUPPORTED_BY`, `CORRECTS` and `SUPERSEDES` edge corresponds to one stored link, and nothing else produces an edge. These are structural facts and need no claims about themselves.
2. **Status, support and authority are read live**, equal `claims.is_authoritative` and derived support, and change immediately after a decision or correction.
3. **Forget leaves nothing:** after record or claim Forget, no node, edge, title or count of the forgotten item is returned.
4. **Navigation is not relevance (R3):** traversing the graph never changes a Context Compiler decision. A test compiles every Benchmark 0003 query (requires PR #4 merged; otherwise the SB-2 synthetic corpus) with and without graph code loaded and requires identical tokens.
5. **Bounded and local:** neighborhood queries are hop- and size-bounded; graph responses never enter `outbound`, provider messages or receipts.
6. **Read-only:** the canonical export before and after any graph query is byte-identical.

## 4. Obsidian snapshot export (SB-2)

Contract: [OBSIDIAN-PROJECTION.md](OBSIDIAN-PROJECTION.md) revision 3 — a one-shot, user-requested snapshot written as a ZIP or a new folder, with no registry, no write-lock fence and no automatic cleanup. All tests use synthetic vaults only. The corpus is built through the real APIs — `Vault.add`, `import_untrusted` (attacker-chosen record IDs, content, `source` and `created_at`), `restore_trusted` (attacker-chosen claim IDs, times and decision notes, and a squatted-record-ID scenario) and ADR-0002 legacy migration — and every payload carries a unique canary token, a canary host under a reserved `.invalid` or `.example` domain, a literal private IP and a `file://` canary path. Tests that compare outputs fix the export key and snapshot time.

### 4.1 Structure and filenames

1. Every active wikilink resolves; basenames are unique case-insensitively; titles follow the §5 rule (idempotent, NFC-stable, no reserved characters, no imitation of a handle).
2. **Filename length (Codex N4):** every basename — title, handle after collision extension, and `.md` — is valid NFC UTF-8 of at most 140 bytes, and every relative path inside the export is at most 160 bytes. Property tests cover 60-character titles of 2-, 3- and 4-byte characters (for example Greek, CJK and CJK Extension B), titles with modifier letters and combining marks (Japanese, Devanagari, Thai), a variation selector or U+034F after a letter (mapped to `-`), a title that is one long word (a single ASCII word of 61–124 characters is cut to 60 whole graphemes, not replaced by *Untitled*), the longest handle extensions forced by colliding keys, and opaque mode; a cut never splits a code point or a grapheme and never alters the handle, and such titles stay readable.
3. Frontmatter parses identically in at least two independent YAML parsers, uses only schema keys in order, has escape-free one-line values, and carries no raw `sovereign_id` by default (D13); no payload ID (`[[Start Here]]`, `obsidian://…`, empty, `/`, 5,000-character legacy, import-derived UUIDv5 or sequential UUID-shaped) appears in any generated position — filename, frontmatter value, link target or display text, navigation entry — checked structurally; free-text absence is asserted only for collision-free canary IDs.
4. Every note starts with the banner, which carries the snapshot time; only Start Here carries `snapshot_at` and the class-level scope; statuses, support and authority equal the compiler's view at the snapshot.
5. Graph lines correspond one-to-one to authorized slots, plus lineage reverse links only; `graph.json` holds only the tag-anchored constants, and titles such as "Claims about Harbor" or "_Navigation backup" are neither recolored nor hidden.
5a. Two exports of one snapshot with the same export key and snapshot time are byte-identical; the pinned Unicode data version is recorded.

### 4.2 Inert serialization (Codex F3)

6. **Adversarial corpus:** records, claims, decision notes, cited passages and `source` values containing at least: wikilinks and heading/block links; embeds; Markdown links including `obsidian://` and `file://`; remote images and media; raw HTML (`img`, `iframe`, `audio`, `video`, `object`, `style`, `link`); callouts; tags matching the vault's color-group tags; `%%` comments; block IDs; Dataview inline fields and `dataviewjs` blocks; Templater `<% %>`; Mermaid and math; footnotes; headings, setext headings and thematic breaks; forged frontmatter delimiters; fence breakouts with backtick, tilde, U+FF40 and U+1FEF runs; bare CR, CRLF, NUL, VT, FF, NEL, U+2028 and U+2029; bidi, zero-width and tag characters; 2,000 combining marks; a 10,000-backtick record and a 10,000-character line. The rules they must defeat are OBSIDIAN-PROJECTION §6–§7.
7. **Golden skeleton:** replacing every inert block with a placeholder leaves text built only from classes G, E, N, T, S and L; any interpolated class-U value fails.
8. **Multi-parser oracle:** with several CommonMark/GFM parsers (pinned versions), the fenced blocks are exactly the expected list (count, order, info string `text`, content equal to the escaped value), every fence is at document level and column 0, and no link, image, HTML, autolink, footnote or extra heading node comes from anything but generated text. No canary token or host appears outside code.
9. **Normalization and line endings:** each fence is longer than the longest backtick run of its content in raw, NFC, NFD, NFKC and NFKD forms, and NFC-, NFD-, NFKC- and CRLF-converted copies of every file stay inert. Regression: an emitter that normalizes or nests a block inside a list must fail.
10. **Escape properties:** decoding the escape restores the original (modulo CRLF); no output contains `<%`, `%%` or `::`; fixed vectors cover every escaped class.
11. **Typed fields:** nonstandard `created_at`, `claim_events.at` and `source` values render as *time not recorded* or appear only inside inert blocks; every decision-history cell matches its column grammar.
12. **Authorized evidence:** in the squatted-record-ID and missing-evidence scenarios, a claim note neither links to the squatted or missing record nor shows its raw ID.
13. **Native Obsidian test (recorded):** pinned Obsidian version, fresh profile or VM, Restricted mode, updates and spellcheck off, not signed in to Sync. Visit every note in Reading view, Live Preview and Source mode, hover every link, expand Backlinks (including unlinked mentions), Outline and Properties, open Graph view and Local graph at depth 2, search for the canary token, export one adversarial note to PDF. Pass only if (a) Obsidian's metadata cache lists exactly the authorized links and no embeds, frontmatter links, body tags, blocks or footnotes; (b) the rendered DOM contains no `img`, `iframe`, media, `object`, `style`, `link` or `url(` apart from Obsidian's own icons, every anchor is an internal link in the authorized set, and the callout count equals the generated banners; (c) **zero network requests** leave the machine. Measure (c) with OS-level isolation — a network namespace or VM whose only route is a logging sinkhole for DNS and every TCP/UDP port, plus packet capture and a syscall trace of connect attempts, and file-access watching for `file://` canaries — validated by a positive-control vault whose remote image *must* be logged, or the run is void.
14. **Plugin profiles (recorded):** with Dataview (JavaScript queries on), forged inline fields return no rows and the `dataviewjs` payload does not run; with Templater (trigger on file creation on), opening and browsing a freshly extracted export does not create the Templater canary. Other plugins are outside the guarantee, and the export preview says so.
15. **Output guard:** an output inside a Git working tree, or one that is an existing folder (empty or not) or an existing file, is always refused; an output inside another Obsidian vault is refused without confirmation, and with confirmation the preview lists that vault's enabled plugins and the specific warnings.

### 4.3 Scope, reference closure and structural verification (Codex F4, N3)

16. **Twin-vault oracle (property-based):** for generated pairs of vaults that agree on the authorized set, on its items' own rows and events, on its edges and on the partial flags, but differ arbitrarily outside it (extra sensitive records; decisions on excluded claims; Forget of excluded items), exports made with the same export key and snapshot time have the same file set and byte-identical files.
17. **Chains crossing scope:** a private record corrected by a sensitive revision and corrected again by a private one; claim supersession across sensitivity and across the date range; a superseded claim whose successor was forgotten; legacy anomalies through trusted restore (meaningful IDs, forks, self-pointers, dangling pointers, non-date times). Each included item shows only its own status, at most one fixed partial sentence at the fixed position, no link across the omitted item, no ordinal, none of the omitted item's handle or content canary, and no generated position derived from its title, ID or time (checked structurally, since revisions share titles and items can share a stored second). The partial notes are byte-equal to twins where the omitted item is merely excluded rather than forgotten.
18. **Edge-attached data:** supersession notes, "superseded by/on" dates, relational Timeline entries and "became stale" events appear only when both endpoints are included.
19. **Inbound invariance and inherited sensitivity:** a record cited by an excluded sensitive claim is byte-identical to a twin without that claim; a restored claim with missing or unverified evidence is excluded by default.
20. **Scope-shrink matrix:** dropping superseded records, narrowing dates, turning sensitive inclusion off, switching readable to opaque names and turning proposals off each yield an export containing only the narrowed set, with no unresolved link and no filename, title or handle of a dropped item; no item note's filename or handle from an earlier export recurs in a new one (fresh key); the fixed navigation, marker and `graph.json` names are the same in every export. Earlier exports are separate artifacts and are never modified.
21. **Handles and IDs:** an excluded ID chosen to share a handle prefix with an included item changes no included filename; two exports of one vault share no handle; no raw canonical ID (including import-derived UUIDv5 and sequential UUID-shaped IDs), storage sequence number, evidence hash or digest of any object appears in a generated position (decision tables carry per-claim ordinals only), checked structurally, and no collision-free canary ID appears anywhere; after an export finishes, Sovereign holds no export key, handle or file hash.
22. **Navigation and metrics:** twins with 0 and 500 excluded items give byte-identical Timeline, indexes, hubs, metrics and Start Here (same key and snapshot time).
23. **Closed mode:** the drop-to-fixpoint terminates, is deterministic and yields the largest subset of A in which every slot held by a member points to a member; an item cited by an excluded claim is kept (inbound edges are not slots).
24. **Output channels:** stdout, stderr and server logs of export, verification failures and injected I/O failures contain only handles and counts; nothing is written or deleted outside the run's own staging folder, temporary file and destination, apart from the vault itself, which is opened as every Sovereign process opens it (a legacy vault may be migrated).
24a. **Structural verification (Codex N3):** fault-injection builds of the exporter that (a) link to an out-of-set handle, (b) add a navigation entry or metric for an excluded item, (c) write an extra frontmatter key or a wrong value, (d) place a wikilink, embed, tag or callout outside a generated position, (e) alter an inert block's content, (f) write an extra file, (g) put a wrong title in an H1 or a wrong value in a status line, decision-history cell or inert-block label, (h) duplicate or misplace the partial sentence, or (i) add a color group to `graph.json` are each stopped by export spec §11.3 before anything is offered. Conversely, verification does **not** fail when an excluded item's legacy ID is an ordinary word ("harbor", "notes") that occurs in included text, when two revisions share a title, or when items were stored in the same second.

### 4.4 Snapshot export and the Forget boundary (Codex F2, N1, N2)

25. **Snapshot boundary:** a record Forget (with earlier revisions and dependent claims), a direct claim Forget, a trusted restore whose tombstones dominate, and a plain raw-SQL tombstone insert from an independent connection, each committed before an export's snapshot, leave no canary and no structural trace in that export; notes that linked the forgotten items show only included links.
26. **Forget after the snapshot:** a Forget that commits after the snapshot's first read but before the report is not reflected in the export, the report's post-snapshot notice says so, and an export started afterwards excludes the item. A Forget committed between `BEGIN` and the first read is reflected, and the recorded snapshot time is taken after that first read, so no commit after the stated snapshot time is ever reflected.
27. **Failure and interruption:** inject failures and kill the process during the snapshot read, rendering, verification and packaging, for ZIP and folder outputs. No success is reported; nothing partial or unverified ever appears under the destination name (a kill after the final move may leave a complete, verified, unreported export); a failed run removes its own staging or temporary file on a best-effort basis; a killed run leaves at most a hidden, recognizably named staging folder or temporary file beside the destination, which the next export lists for the user and does not delete; no export deletes anything but its own staging and temporary files; the next export succeeds from scratch. A syscall trace or filesystem shim shows that a folder export syncs every staged file and directory before its no-replace move. No partial result is required to survive power loss.
28. **No overwrite, no touch:** an existing ZIP path, an existing folder (empty or not) and a folder inside a Git working tree are always refused; a folder inside another Obsidian vault is refused unless explicitly confirmed. A destination that appears between preview and packaging (a file, an empty folder or a non-empty folder) makes the export fail without being replaced. A running export never modifies an earlier export or anything outside its own staging, temporary file and destination (other than opening the vault, as in test 24); notes the user edited or added in an earlier export are untouched. A destination under a listed sync-client root or on a network filesystem is refused, and any other destination gets the incomplete-detection warning.
29. **Concurrent exports:** a second export started as a separate process while the first reads its snapshot either waits or fails cleanly as busy at vault open; exports to different destinations in the same parent folder never touch each other's staging or temporary files; two exports to the same destination: exactly one succeeds and the other fails without touching the winner's output.
30. **Writers, opens and reads during the read:** captures, decisions, Forgets and new vault opens issued while an export reads its snapshot wait (bounded by the 10 s busy timeout) or fail cleanly as busy, never partially, and reads queued behind a waiting writer are reported; SB-2 reports the read-phase duration on its synthetic vault and keeps it well within the busy timeout; no transaction stays open while files are written.
31. **Preview binding:** if the authorized counts differ between the confirmed preview and the snapshot, the run stops before writing and re-previews.
32. **Forget boundary disclosure:** the Forget preview and result say that earlier exports, and leftovers of interrupted exports, are outside Sovereign's control and must be deleted by the user, and never say "deleted everywhere"; every note's banner and Start Here state the snapshot time and that forgetting in Sovereign does not change the export.
33. **ZIP hygiene:** entries are relative paths under one top folder with the UTF-8 name flag, regular files only, with no `..`, absolute paths or symbolic links; extracting with at least two common tools (pinned) yields the verified tree byte for byte.
34. **Lineage residual (D15):** the export preview states, without naming any item, that included claims may restate superseded sensitive claims.
35. **Storage prerequisite (before production SB-2):** once the separate Tier 2 storage fix lands, raw `INSERT OR REPLACE`/`REPLACE` naming an existing rowid in `tombstones`, `claim_tombstones`, `records`, `claims` or `claim_sources`, and `UPDATE OR REPLACE … SET rowid`, are rejected on a connection with `recursive_triggers` off (SECURITY-GATE).

### 4.5 Usability (reported, not gated)

Link resolution must be 100%. Report, over the authorized set, orphan share, largest component share, maximum hub degree and the share of readable titles. Manual check: Local graph at depth 2 from a claim or source note (from a project hub after SB-3) answers "what is connected, and why" from note text alone.

### 4.6 Native checks not yet executed

No native Obsidian test has been run in any review environment so far. Items 13–15, the manual part of 4.5, and the Obsidian-specific assumptions they verify (link and tag recognition inside long fences, comment spanning, property links, `path:` semantics, dot-prefixed paths, snippet rendering, baseline network silence with updates off) remain open acceptance gates, to be repeated on every Obsidian upgrade.

## 5. Future slices

- **SB-3 human-declared organization:** migration, export/restore round trip, import authority (an imported membership never raises authority), Forget of a member and of an entity, hub regeneration, and scope closure for hubs.
- **SB-6 temporal claims:** correction and change cases scored separately; `superseded` never rendered or prompted as "false"; valid intervals only from canonical fields.
- **SB-7 structured relations:** relation claims follow the MemoryClaim lifecycle exactly; an edge never inherits approval from supporting claims or sources; the predicate registry is versioned; entity merges are reversible and never rewrite claims; people nodes are sensitive by default; a relation is projected only when the claim, subject and object are all authorized. After the ADR-0004 amendment for entity-aware sensitivity (ADR-0005 §8.2), an approved relation claim that cites only private records but names a sensitive entity is excluded from a cloud plan as `sensitive_cloud`, and changing the entity's sensitivity invalidates a pending token. A merge or split of an entity a relation claim pins removes that claim from approved memory until a human re-approves or supersedes it, and invalidates a pending token. Forgetting a subject or object entity forgets every relation claim that names it. Contradictions are tested only as `contested` claims until a `CONTRADICTS` relation is designed; if one is, forgetting either endpoint claim must forget it.
- **SB-5 semantic/hybrid (deferred, R6):** inside the Benchmark 0003 harness; report governed recall *and* noise and precision, local and cloud (R4); token stability on an unchanged vault must be 100%; the truncation fingerprint keeps binding the complete relevant candidate state (R2); no real sensitive notes while the Security Gate is NOT PASSED.
- **SB-8 graph-assisted context (deferred, R3):** local-only exploration first; any proposal to make linked items relevant needs an independent evaluation and a founder decision on ADR-0004 decision 3.

## 6. Optional generated-answer evaluation (not established by SB-1)

If answer quality is ever evaluated, it is a separate, explicitly approved evaluation with its own PR and number, assigned then:

- **Oracle:** per question, the facts a correct answer must state and cite, facts it must not state, and expected abstention for questions with no relevant evidence; temporal questions scored on "then vs now" and on correction vs change.
- **Data:** synthetic only while the Security Gate is NOT PASSED.
- **Models:** a local model, or a cloud model reached only through exact, per-request approved plans, under a stated cost cap.
- **Separation:** answer scores never replace Benchmark 0003's retrieval and policy metrics, and model output is never persisted as memory (ADR-0004 decision 6).

## 7. Hard gates for every slice

Fail immediately for: unauthorized approval or promotion; model-selected vault access; forgotten-derived content in any store Sovereign manages, or in a new export of a snapshot taken after the Forget; any unauthorized network request from a projection; a cloud transmission that differs from the approved messages; durable IDs in `outbound`; any test requiring real personal data. The Security Gate remains NOT PASSED.
