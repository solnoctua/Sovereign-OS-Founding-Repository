# Second-Brain Validation Specification

**Status:** PROPOSED; no test described here is implemented. This document owns the test requirements for the [ADR-0005](../adr/0005-governed-second-brain-architecture.md) slices *other than* retrieval evaluation. It is a validation specification, not a benchmark, and carries no benchmark number.

**History:** this file began in PR #3 as a draft "Benchmark 0003" retrieval specification. Retrieval evaluation now belongs to the executed Benchmark 0003 in PR #4, so the draft was renamed and narrowed to the provenance graph, Obsidian projection and later second-brain slices. Nothing in it re-specifies or duplicates PR #4's harness.

## 1. What is validated where

| Area | Owner | State (2026-10-20) |
| --- | --- | --- |
| Retrieval and governed-context evaluation (SB-1) | **Benchmark 0003 — retrieval evaluation**: `docs/benchmarks/0003-retrieval-evaluation.md` and the `evaluation/retrieval/` harness, delivered by [PR #4](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/pull/4) | Executed on synthetic data; **not merged**; its Codex P2 finding on scale timings is open; its founder decisions (R1–R7 in ADR-0005 §12) are pending |
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
| No-evidence queries | Measures what would be offered for disclosure when nothing is relevant (R4) | Benchmark 0003 harness: in PR #4 before merge, or a follow-up harness PR — not PR #3 |
| Generated answers, abstention, temporal interpretation | Answer quality is a different property from retrieval | §6, a separate optional evaluation with its own PR and number |
| Projection and graph behavior | Not retrieval | §3–§4 of this spec |

## 3. Provenance graph (SB-2)

The provenance graph is computed on read from `claim_sources`, `records.supersedes_id` and `claims.supersedes_id` (ADR-0005 §8.1).

1. **Edges are exactly canonical:** every `SUPPORTED_BY`, `CORRECTS` and `SUPERSEDES` edge corresponds to one stored link, and nothing else produces an edge. These are structural facts and need no claims about themselves.
2. **Status, support and authority are read live**, equal `claims.is_authoritative` and derived support, and change immediately after a decision or correction.
3. **Forget leaves nothing:** after record or claim Forget, no node, edge, title or count of the forgotten item is returned.
4. **Navigation is not relevance (R3):** traversing the graph never changes a Context Compiler decision. A test compiles every Benchmark 0003 query with and without graph code loaded and requires identical tokens.
5. **Bounded and local:** neighborhood queries are hop- and size-bounded; graph responses never enter `outbound`, provider messages or receipts.
6. **Read-only:** the canonical export before and after any graph query is byte-identical.

## 4. Obsidian projection (SB-2)

Contract: [OBSIDIAN-PROJECTION.md](OBSIDIAN-PROJECTION.md). All tests use synthetic vaults only.

### 4.1 Structure

1. Every active wikilink resolves; basenames are unique case-insensitively; filenames are sanitized and NFC; short IDs are hash-derived.
2. Frontmatter parses, uses only schema keys, and every string value round-trips through a YAML parser.
3. Every note starts with the snapshot banner and carries its `generation`.
4. Statuses, support and authority in each note equal the compiler's view **at that export's generation**.
5. Graph lines correspond one-to-one to canonical relationships between authorized nodes, plus lineage reverse links only.

### 4.2 Inert serialization (Codex F3)

6. **Adversarial corpus:** synthetic records, claims, decision notes and quotations containing at least these payload classes: wikilinks and heading/block links; embeds and transclusions; Markdown links including `obsidian://` and `file://` URIs; remote images and media; raw HTML (`img`, `iframe`, `audio`, `video`, `object`, `style`, `link`); callouts; tags matching the vault's color-group tags; `%%` comments; block IDs; Dataview inline fields and `dataviewjs` blocks; Mermaid and math; footnotes; headings, setext headings and thematic breaks; forged frontmatter delimiters; fence breakouts with backtick and tilde runs; CRLF, NUL and other control characters; bidi and zero-width characters; very long lines. The rules they must defeat are OBSIDIAN-PROJECTION §7.
7. **Structural test:** every untrusted string appears only inside generated fenced blocks whose fence is longer than any backtick run it contains; parsing each note with a CommonMark parser plus Obsidian's link, embed, tag and callout rules yields exactly the authorized link set, the generated banners and no image, embed, HTML, tag or link node from content.
8. **Frontmatter forging:** no payload changes the parsed frontmatter, adds a key, or alters `tags`, `status` or ownership markers.
9. **Native Obsidian test (manual or scripted, recorded):** open the adversarial projection in a clean Obsidian profile with no community plugins; visit every note in Reading and Live Preview and open Graph view and Local graph. Pass only if Graph view shows no edge, tag node or color that the authorized set does not contain, and **zero network requests** leave the machine. Measure with OS-level egress blocking and logging (a firewall rule or proxy that logs and refuses everything), with Obsidian's own update and sync checks disabled. Any logged attempt fails the test.
10. **Plugin caveat recorded:** repeat item 9 with Dataview installed to confirm `dataviewjs` content stays inert inside `text` fences; other plugins are outside the guarantee and the export preview says so.

### 4.3 Scope and reference closure (Codex F4)

11. The authorized node set is computed before any edge, filename or navigation entry; no output file, manifest entry, alias, tag, link or count refers to an object outside it.
12. **Chains crossing scope:** a private record corrected by a sensitive revision; a sensitive record corrected by a private one; a claim superseded by a claim outside the date scope; a claim whose inherited sensitivity is sensitive. Each produces only the fixed partial-provenance wording, and the excluded object's title, ID, date and existence are absent.
13. **Scope shrinking:** export with scope S, then with S′ ⊂ S; every file for S \ S′, including previously generated filenames and renamed files, is deleted, and every surviving note that linked them is rewritten.
14. **No widening:** a test asserts that a narrower scope never pulls in an excluded endpoint to complete a link.

### 4.4 Export versus Forget (Codex F2)

15. **The four-step race:** hold an export inside its fenced section, attempt Forget of an exported item from another process, and require that Forget either waits and runs after publication (then cleans the projection) or fails as busy without committing. Under no interleaving may a published file contain content forgotten before that export's fence was acquired.
16. **Every tombstone path:** record Forget (with earlier revisions and dependent claims), direct claim Forget and a trusted restore whose tombstones dominate each leave no canary string in any owned file, staging file or manifest, after cleanup reports `reconciled`.
17. **Surviving notes:** a newer revision, a successor claim, hubs and navigation notes that named a forgotten item no longer contain its title or link.
18. **Crash points:** kill the exporter after registration but before any file, mid-staging, mid-rename, before the manifest, and after the manifest; kill the Forget cleanup after the canonical commit. After restart, reconciliation leaves no stale or partial file, and pending state is reconstructed from durable state alone.
19. **Durability:** with the projection on a filesystem where unlinks can be lost on power failure (simulated), cleanup is not recorded as complete until the directory is synced.
20. **Concurrency:** two exporters to the same root, and to different roots, never interleave publication; an exporter from a different vault refuses a root it does not own.
21. **Unavailable or modified roots:** with the root unmounted, Forget reports the projection as pending and later reconciles it; a root whose marker is missing or foreign is never written to or deleted from; user-edited owned files are reported and overwritten; non-owned files are never touched.
22. **Acknowledgment:** the Forget response distinguishes "forgotten in Sovereign" from each projection's cleanup state, and never reports external deletion that has not happened.

### 4.5 Usability (reported, not gated)

Link resolution must be 100%. Report orphan share, largest component share, maximum hub degree and the share of readable titles. Manual check: Local graph at depth 2 from a project hub answers "what is connected, and why" from note text alone.

### 4.6 Native checks not yet executed

No native Obsidian test has been run in any review environment so far. Items 9–10 and the manual part of 4.5 remain open acceptance gates.

## 5. Future slices

- **SB-3 human-declared organization:** migration, export/restore round trip, import authority (an imported membership never raises authority), Forget of a member and of an entity, hub regeneration, and scope closure for hubs.
- **SB-6 temporal claims:** correction and change cases scored separately; `superseded` never rendered or prompted as "false"; valid intervals only from canonical fields.
- **SB-7 structured relations:** relation claims follow the MemoryClaim lifecycle exactly; an edge never inherits approval from supporting claims or sources; the predicate registry is versioned; entity merges are reversible and never rewrite claims; people nodes are sensitive by default; a relation is projected only when the claim, subject and object are all authorized.
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
