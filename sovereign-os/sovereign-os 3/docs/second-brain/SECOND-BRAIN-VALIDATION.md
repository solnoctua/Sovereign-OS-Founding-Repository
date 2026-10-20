# Second-Brain Validation Specification

**Status:** PROPOSED; no test described here is implemented. This document owns the test requirements for the [ADR-0005](../adr/0005-governed-second-brain-architecture.md) slices *other than* retrieval evaluation. It is a validation specification, not a benchmark, and carries no benchmark number.

**History:** this file began in PR #3 as a draft "Benchmark 0003" retrieval specification. Retrieval evaluation now belongs to the executed Benchmark 0003 in PR #4, so the draft was renamed and narrowed to the provenance graph, Obsidian projection and later second-brain slices. Nothing in it re-specifies or duplicates PR #4's harness.

## 1. What is validated where

| Area | Owner | State (2026-10-20) |
| --- | --- | --- |
| Retrieval and governed-context evaluation (SB-1) | **Benchmark 0003 — retrieval evaluation**: `docs/benchmarks/0003-retrieval-evaluation.md` and the `evaluation/retrieval/` harness, delivered by [PR #4](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/pull/4) | Executed on synthetic data; **not merged**; its Codex P2 finding on scale timings is open; the founder's intended positions on it (R1–R7 in ADR-0005 §12.2) are pending, and its decisions 1, 2 and 6 stay open (ADR-0005 §12.2) |
| A future lexical change (SB-4, Porter normalization) | The implementing PR regenerates Benchmark 0003 | Not started; depends on R1 |
| Provenance graph (SB-2) | §3 | Not implemented |
| Safe Obsidian projection (SB-2) | §4 | Not implemented |
| Human-declared organization, temporal claims, structured relations (SB-3, SB-6, SB-7) | §5 | Future; each needs its own ADR |
| Semantic/hybrid experiments (SB-5) | A new retriever inside the **Benchmark 0003 harness**, behind the same `score` seam and ground truth — never a second harness | Deferred (R6) |
| Generated-answer evaluation | §6 | Optional; **not established by SB-1** |

## 2. What Benchmark 0003 establishes, and what it does not

This section reconciles Codex finding F5 (benchmark oracle) with PR #4 as it exists at `3f1c8d7`.

**Established (non-generative, deterministic):**

- **An explicit oracle.** Each of the 56 queries lists every expected item with its intended governed outcome per target (`evidence`, `approved_memory`, or the exclusion reason such as `superseded`, `stale`, `sensitive_cloud`), plus acceptable items. The ground truth was fixed before any experiment, and the harness validates every expectation against production policy before measuring, stopping on disagreement.
- **Retrieval before policy:** Recall@1/5/10/50 and MRR.
- **Governed context after policy:** governed recall, noise and precision for the local and cloud targets; exclusion reasons; budget binding.
- **A failure taxonomy:** recalled, policy-excluded, no match, provenance only, below cutoff, outranked, budget.
- **Token stability** under an unrelated write, and **zero policy violations** for every retriever, with no sensitive item in any cloud plan.
- **Isolation:** experiments swap only the `score` function; candidate selection and policy are production code; no provider is called.

**NOT MEASURED:**

- **Generated-answer correctness.** No model is called, so whether an answer is right, grounded or well cited is not measured.
- **Abstention.** Every query has at least one expected item, so neither answer abstention nor retrieval behavior on questions with *no* relevant evidence is measured.
- **Temporal interpretation.** The 5 temporal and 3 correction queries are measured as retrieval ranking and policy outcome (for example temporal MRR, `superseded` exclusions). Whether an answer distinguishes "then" from "now", or a correction from a change, is not measured.
- Pinned questions, languages other than English, and real usage frequencies (the corpus is self-authored and over-represents hard cases by design).

**Not evidence:** the indicative scale timings in Benchmark 0003's finding 8. Codex P2 on PR #4 found they have no reproducible generation path in the harness or committed artifacts. PR #3 relies on none of them, and they are not an architectural capacity guarantee. Resolving that finding belongs to PR #4.

**Remaining gaps and where they belong:**

| Gap | Why it matters | Where |
| --- | --- | --- |
| No-evidence queries | Measures what would be offered for disclosure when nothing is relevant (R4). Partly covered for cloud: six queries whose expected items are all `sensitive_cloud` already report cloud noise (22 items under the baseline, 12 in q40; 33 under Porter normalization). Still missing: questions with no relevant item at all, local and cloud | Benchmark 0003 harness: in PR #4 before merge, or a follow-up harness PR — not PR #3 |
| Unchanged-vault token stability | Repeat compiles of the same question on the same vault state give the same token (ADR-0005 §6.4). The harness reports only tokens changed by an unrelated write | Benchmark 0003 harness follow-up, before SB-5 — not PR #3 |
| Generated answers, abstention, temporal interpretation | Answer quality is a different property from retrieval | §6, a separate optional evaluation with its own PR and number |
| Projection and graph behavior | Not retrieval | §3–§4 of this spec |

## 3. Provenance graph (SB-2)

The provenance graph is computed on read from `claim_sources`, `records.supersedes_id` and `claims.supersedes_id` (ADR-0005 §8.1).

1. **Edges are exactly canonical:** every `SUPPORTED_BY`, `CORRECTS` and `SUPERSEDES` edge corresponds to one stored link, and nothing else produces an edge. These are structural facts and need no claims about themselves.
2. **Status, support and authority are read live**, equal `claims.is_authoritative` and derived support, and change immediately after a decision or correction.
3. **Forget leaves nothing:** after record or claim Forget, no node, edge, title or count of the forgotten item is returned.
4. **Navigation is not relevance (R3):** traversing the graph never changes a Context Compiler decision. A test compiles every Benchmark 0003 query (requires PR #4 merged; otherwise the SB-2 synthetic corpus) with and without graph code loaded and requires identical tokens.
5. **Bounded and local:** neighborhood queries are hop- and size-bounded; graph responses never enter `outbound`, provider messages or receipts.
6. **Read-only:** the canonical export before and after any graph query is byte-identical.

## 4. Obsidian projection (SB-2)

Contract: [OBSIDIAN-PROJECTION.md](OBSIDIAN-PROJECTION.md). All tests use synthetic vaults only. The corpus is built through the real APIs — `Vault.add`, `import_untrusted` (attacker-chosen record IDs, content, `source` and `created_at`), `restore_trusted` (attacker-chosen claim IDs, times and decision notes, and a squatted-record-ID scenario) and ADR-0002 legacy migration — and every payload carries a unique canary token, a canary host under a reserved `.invalid` or `.example` domain, a literal private IP and a `file://` canary path.

### 4.1 Structure

1. Every active wikilink resolves; basenames are unique case-insensitively; titles follow the §5 rule (idempotent, NFC-stable, no reserved characters, no imitation of a handle); filenames are at most 200 bytes.
2. Frontmatter parses identically in at least two independent YAML parsers, uses only schema keys in order, has escape-free one-line values, and carries no raw `sovereign_id` by default (D13); no payload ID (`[[Start Here]]`, `obsidian://…`, empty, `/`, 5,000-character legacy, import-derived UUIDv5 or sequential UUID-shaped) appears anywhere.
3. Every note starts with the banner; only Start Here carries `generation`; statuses, support and authority equal the compiler's view at that generation.
4. Graph lines correspond one-to-one to authorized slots, plus lineage reverse links only; `graph.json` holds only the tag-anchored constants, and titles such as "Claims about Harbor" or "_Navigation backup" are neither recolored nor hidden.
5. Two runs on one snapshot are byte-identical; the pinned Unicode data version is recorded.

### 4.2 Inert serialization (Codex F3)

6. **Adversarial corpus:** records, claims, decision notes, cited passages and `source` values containing at least: wikilinks and heading/block links; embeds; Markdown links including `obsidian://` and `file://`; remote images and media; raw HTML (`img`, `iframe`, `audio`, `video`, `object`, `style`, `link`); callouts; tags matching the vault's color-group tags; `%%` comments; block IDs; Dataview inline fields and `dataviewjs` blocks; Templater `<% %>`; Mermaid and math; footnotes; headings, setext headings and thematic breaks; forged frontmatter delimiters; fence breakouts with backtick, tilde, U+FF40 and U+1FEF runs; bare CR, CRLF, NUL, VT, FF, NEL, U+2028 and U+2029; bidi, zero-width and tag characters; 2,000 combining marks; a 10,000-backtick record and a 10,000-character line. The rules they must defeat are OBSIDIAN-PROJECTION §6–§7.
7. **Golden skeleton:** replacing every inert block with a placeholder leaves text built only from classes G, E, N, T, S and L; any interpolated class-U value fails.
8. **Multi-parser oracle:** with several CommonMark/GFM parsers (pinned versions), the fenced blocks are exactly the expected list (count, order, info string `text`, content equal to the escaped value), every fence is at document level and column 0, and no link, image, HTML, autolink, footnote or extra heading node comes from anything but generated text. No canary token or host appears outside code.
9. **Normalization and line endings:** each fence is longer than the longest backtick run of its content in raw, NFC, NFD, NFKC and NFKD forms, and NFC-, NFD-, NFKC- and CRLF-converted copies of every file stay inert. Regression: an emitter that normalizes or nests a block inside a list must fail.
10. **Escape properties:** decoding the escape restores the original (modulo CRLF); no output contains `<%`, `%%` or `::`; fixed vectors cover every escaped class.
11. **Typed fields:** nonstandard `created_at`, `claim_events.at` and `source` values render as *time not recorded* or appear only inside inert blocks; every decision-history cell matches its column grammar.
12. **Authorized evidence:** in the squatted-record-ID and missing-evidence scenarios, a claim note neither links to the squatted or missing record nor shows its raw ID.
13. **Native Obsidian test (recorded):** pinned Obsidian version, fresh profile or VM, Restricted mode, updates and spellcheck off, not signed in to Sync. Visit every note in Reading view, Live Preview and Source mode, hover every link, expand Backlinks (including unlinked mentions), Outline and Properties, open Graph view and Local graph at depth 2, search for the canary token, export one adversarial note to PDF. Pass only if (a) Obsidian's metadata cache lists exactly the authorized links and no embeds, frontmatter links, body tags, blocks or footnotes; (b) the rendered DOM contains no `img`, `iframe`, media, `object`, `style`, `link` or `url(` apart from Obsidian's own icons, every anchor is an internal link in the authorized set, and the callout count equals the generated banners; (c) **zero network requests** leave the machine. Measure (c) with OS-level isolation — a network namespace or VM whose only route is a logging sinkhole for DNS and every TCP/UDP port, plus packet capture and a syscall trace of connect attempts, and file-access watching for `file://` canaries — validated by a positive-control vault whose remote image *must* be logged, or the run is void.
14. **Plugin profiles (recorded):** with Dataview (JavaScript queries on), forged inline fields return no rows and the `dataviewjs` payload does not run; with Templater (trigger on file creation on), neither a fresh nor an incremental export run creates the Templater canary while Obsidian is open. Other plugins are outside the guarantee, and the export preview says so.
15. **Root guard:** an export into a folder inside another Obsidian vault is refused without confirmation; with confirmation the preview lists the enabled plugins and the specific warnings.

### 4.3 Scope and reference closure (Codex F4)

16. **Twin-vault oracle (property-based):** for generated pairs of vaults that agree on the authorized set, on its items' own rows and events, on its edges and on the partial flags, but differ arbitrarily outside it (extra sensitive records; decisions on excluded claims; Forget of excluded items), every owned file and every registry row apart from counters is byte-identical, and no file is written, touched or renamed.
17. **Chains crossing scope:** a private record corrected by a sensitive revision and corrected again by a private one; claim supersession across sensitivity and across the date range; a superseded claim whose successor was forgotten; legacy anomalies through trusted restore (meaningful IDs, forks, self-pointers, dangling pointers, non-date times). Each included item shows only its own status, at most one fixed partial sentence at the fixed position, no link across the omitted item, no ordinal, and none of the omitted item's title, handle, ID, time or content canary. The partial notes are byte-equal to twins where the omitted item is merely excluded rather than forgotten.
18. **Edge-attached data:** supersession notes, "superseded by/on" dates, relational Timeline entries and "became stale" events appear only when both endpoints are included.
19. **Inbound invariance and inherited sensitivity:** a record cited by an excluded sensitive claim is byte-identical to a twin without that claim; a restored claim with missing or unverified evidence is excluded by default.
20. **Scope-shrink matrix:** dropping superseded records, narrowing dates, turning sensitive inclusion off, switching readable to opaque names and turning proposals off each yield a projection byte-identical to a fresh export with the same key (modulo Start Here's generation and date), with every old filename gone and no unresolved link.
21. **Handles and IDs:** an excluded ID chosen to share a handle prefix with an included item changes no included filename; two projections of one vault share no handle; no raw canonical ID (including import-derived UUIDv5 and sequential UUID-shaped IDs), storage sequence number, evidence hash or digest of any object appears in output; the registry holds only handles and hashes of rendered files.
22. **Navigation and metrics:** twins with 0 and 500 excluded items give byte-identical Timeline, indexes, hubs and metrics, and Start Here differs at most in generation and date.
23. **Closed mode:** the drop-to-fixpoint terminates, is deterministic and yields the largest subset of A in which every slot held by a member points to a member; an item cited by an excluded claim is kept (inbound edges are not slots).
24. **Output channels:** stdout, stderr and server logs of export, narrowing, Forget reconciliation and injected I/O failures contain only handles and counts; the registry file contains no excluded item's ID, handle or title and no path, title, raw ID or content of any item; a forgotten item's handle and file hash remain only until its file is deleted.

### 4.4 Export versus Forget (Codex F2)

25. **The four-step race:** hold an export inside its fenced section and attempt Forget of an exported item from another process; Forget either waits and runs after publication (then the projection is reconciled) or fails as busy without committing. Under no interleaving may a published file contain content forgotten before that export acquired the fence.
26. **Every tombstone path:** record Forget (with earlier revisions and dependent claims), direct claim Forget, a trusted restore whose tombstones dominate, and raw-SQL `INSERT INTO tombstones` / `INSERT INTO claim_tombstones` from an independent SQLite connection each leave no canary in any owned file, staging file or registry row once cleanup reports `reconciled` — never `needs_attention` merely because a Forget changed the tombstone sets; surviving notes that linked the forgotten items are rewritten, with no unresolved link. The raw-SQL insert waits or fails busy while a run holds the fence, and with the server running and no restart it is reconciled by the next periodic or status trigger.
27. **Crash points:** kill the exporter after registration but before any file, after the pending-hash commit but before a rename, mid-staging, mid-rename, between rewrite and delete, before and after the registry commit; kill the Forget path after the canonical commit and after the registry marking. At every kill point, after a process kill or a simulated power loss, no owned note links to a deleted note and every file on disk matches a recorded hash; after restart, reconciliation converges to the fresh-export bytes (modulo Start Here's generation and date), and pending state is reconstructed from durable state alone. Also: kill a CLI export after a rename, then Forget through the already-running server; its reconciliation verifies and promotes the stranded file's hash and deletes or rewrites it.
27a. **Self-check precedes writing:** a render that would leak an out-of-set handle, canonical ID, link target or link display text into any file is stopped before the first file is written; two revisions sharing a title, items stored in the same second and short content that is a substring of another note do **not** trip it; when it fails during a reconciliation, every owned file whose entry left the set is still deleted and the projection is reported `needs_attention`.
27b. **Reconciliation never adds:** after a Forget, reconciliation of a projection deletes and rewrites only; items stored since the last confirmed export do not appear until a user-confirmed export.
27c. **One ownership rule:** inside the root, an unedited owned note that the user renamed, moved or copied is found by filename or `sovereign_handle` property and deleted, every copy, when its item leaves the set; the same note with edited content is reported `needs_attention`, kept in the registry across restarts until the user resolves it, and never silently deleted; copies outside the root are unmanaged and covered by the fixed caveat.
28. **Durability:** with unlinks that can be lost on power failure (simulated), cleanup is not recorded as complete until directories are synced.
29. **Concurrency and ownership:** two exporters to one root, and to different roots, never interleave publication; a root with a foreign or missing marker is never written; a file with a forged marker or `sovereign_handle` property but unmatched bytes, and a symbolic link swapped into the root, are never deleted or followed; edited owned files are reported, not overwritten; concurrent runs never overwrite each other's registration, because registration happens inside the fence.
30. **Unavailable root:** with the root unmounted (including an empty mount-point directory without its marker), Forget reports the projection as pending and marks its entries `delete_pending` immediately; on remount the projection is reconciled by the next trigger (periodic check, status or export command, or start-up) without restarting Sovereign.
30a. **Navigation notes are owned:** Start Here, Timeline and the status index are reserved registry entries; after a Forget their bytes no longer contain the forgotten item's title, handle or link, and they are rewritten by every reconciliation.
30b. **Vault anomalies:** pointing Sovereign at another vault path, or replacing the vault with an older copy (fewer tombstones), still runs fail-closed reconciliation and then leaves the projection `needs_attention` rather than `clean`; only a user-confirmed export re-binds it. A lost tombstone plus a new Forget that restores the old count is still detected as an anomaly (prefix mismatch) and reconciled, while a Forget, claim Forget or trusted restore in the same vault yields `reconciled`, never `needs_attention`. A different vault at the same path whose tombstone tables begin with the same rows is the documented residual of projection spec §11.5.
30c. **Lost registry and unregistering:** with the registry deleted, a non-empty old root is refused rather than adopted, and every Forget result carries the caveat about projections Sovereign no longer knows; the unregister command previews, optionally deletes owned files, and removes the projection's entries and key.
30d. **Opening the vault during a run:** opening a new Vault, starting the server and running a CLI preview while a run holds the fence are measured and reported (they wait up to the busy timeout); captures, decisions and Forgets fail cleanly as busy, never partially.
30e. **Lineage residual (D15):** the export preview states, without naming any item, that included claims may restate superseded sensitive claims.
31. **Preview binding:** if the authorized counts differ between the confirmed preview and the fenced execution, the run stops before writing.
32. **Acknowledgment:** the Forget response distinguishes "forgotten in Sovereign" from each projection's state, identifies projections by ID and counts over HTTP, and never reports an external deletion that has not happened.

### 4.5 Usability (reported, not gated)

Link resolution must be 100%. Report, over the authorized set, orphan share, largest component share, maximum hub degree and the share of readable titles. Manual check: Local graph at depth 2 from a project hub answers "what is connected, and why" from note text alone.

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

Fail immediately for: unauthorized approval or promotion; model-selected vault access; forgotten-derived content in any store or projection after reconciliation; any unauthorized network request from a projection; a cloud transmission that differs from the approved messages; durable IDs in `outbound`; any test requiring real personal data. The Security Gate remains NOT PASSED.
