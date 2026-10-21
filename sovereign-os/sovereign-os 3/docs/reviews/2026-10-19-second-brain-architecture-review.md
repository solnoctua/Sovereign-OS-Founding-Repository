# Independent review — governed second brain (PR #3), 2026-10-19

**Status:** review record, not authority. Decisions live in [ADR-0005](../adr/0005-governed-second-brain-architecture.md) (PROPOSED at the time of this review; direction approved 2026-10-21); this file records what was found and why the documentation changed.

**Note (2026-10-20):** "Benchmark 0003" below means PR #3's draft specification, since renamed [`SECOND-BRAIN-VALIDATION.md`](../second-brain/SECOND-BRAIN-VALIDATION.md). Benchmark 0003 now denotes PR #4's executed retrieval evaluation. Follow-up: [Codex audit remediation](2026-10-20-codex-audit-remediation.md).

**Reviewed:** branch `docs/governed-second-brain-and-obsidian` at `bae766e` (one commit on `8a9e625`), against `main` at `4fbecbe` (PR #2 merged, including `cee2c66`), the implementation in `src/sovereign/` (`store.py`, `claims.py`, `context.py`) and every file the PR added, changed or deleted.

## Findings

### Blockers — resolved in documentation by this review

| # | What was wrong | Why it matters | Resolution |
| --- | --- | --- | --- |
| B1 | L3/L4 retrievers were described as drop-in candidate providers. In the merged compiler, an unpinned item with no shared term is `not_relevant`, ADR-0004 decision 3 keeps provenance-only claims out, and since `cee2c66` the token binds the policy state of the whole relevant candidate universe. | A semantic hit would be silently discarded; changing the gate widens which unpinned private items may go to the cloud (ADR-0004 decision 1); approximate-NN and non-deterministic embeddings would break exact-plan tokens. An implementer would have to invent disclosure policy. | ADR-0005 §6: each method is a new `policy_version`; relevance, fusion, fingerprint and determinism specified; cloud eligibility (D4) and graph-reached context (D5) are founder decisions. |
| B2 | Projects, concepts, decisions and multi-record documents have no canonical basis (records: content, source, sensitivity, status, time, lineage; claims: text, origin, status, lineage, links), yet the ADR, demo vault and benchmark assumed them. | The most likely invention — model extraction or index-side entity tables — would create unreviewed authority outside MemoryClaim. | ADR-0005 §3 state classes; human-declared organization as slice SB-3 (D2); the demo marks every future-only element. |
| B3 | A separate relationship lifecycle (`review_state`) was proposed, and "domain relationship hypotheses" were listed as disposable projections. | It duplicates MemoryClaim status, history, Forget and import rules; a rebuild would discard human review decisions. | Typed relationships are structured MemoryClaims (D3); model proposals are `proposed` claims with `origin = model`. |
| B4 | Forget across derived representations was required but not designed; "atomically reconcile" exports is impossible across a directory. | Verified on SQLite 3.45.1: after an FTS5 `DELETE`, forgotten text remains in the index and the database file, even with `PRAGMA secure_delete` on; FTS5's `secure-delete` option (SQLite ≥ 3.42) removes it. Vectors are partly invertible. Exports live outside the vault transaction. | ADR-0005 §7 per-representation table; in-vault indexes in the Forget transaction (D6); crash-consistent export reconciliation and post-commit cleanup with pending state (D8); residual copies disclosed. |

### Important improvements — made

| # | Issue | Resolution |
| --- | --- | --- |
| I1 | Benchmark 0003 required graph status to "reflect canonical authority on every view", impossible for a static export. | Snapshot banner and `generation` on every note; benchmark checks status per export generation. |
| I2 | Obsidian specifics: node labels are filenames (readable vs private trade-off unaddressed); Graph view *can* show direction (Arrows) but the guide said it could not; links were written both ways, doubling edges and making arrows meaningless; a hub linked everything; tags could become nodes; `_Start Here.md` linked outside the vault (unresolvable in Obsidian). | New [projection spec](../second-brain/OBSIDIAN-PROJECTION.md): filename policy (D7), one relationship = one link = one explanation, lineage-only reverse links, navigation excluded from the graph, tags off, color groups, health metrics; capabilities checked against Obsidian's published help. |
| I3 | The five-note demo could not show decisions, temporal change, corrections, contradictions, typed relations or why a line exists. | Rebuilt as a 19-note fictional vault with five guided paths, including a deliberately wrong unreviewed model proposal. |
| I4 | Export "after local device/vault authorization" relied on authentication that does not exist; an HTTP export endpoint would be an unauthenticated file-write capability. | CLI-only export; refuses Git working trees and non-owned folders; ownership marker; never touches other files. |
| I5 | Correction and change both end in `superseded`; no valid time. | ADR-0005 §8.3; `superseded` never rendered as "false"; temporal extension SB-6 (D10); benchmark scores correction and change separately. |
| I6 | Retrieval itself can disclose (cloud embedding, query rewriting, routing, reranking, extraction). | ADR-0005 §6.7, AGENTS rule, SECURITY-GATE entry. |
| I7 | Three inconsistent numberings with different orders (ADR phases 1–6, ROADMAP SB-01…06, guide R0–R4; the L2 wiki missing from two). | One sequence, SB-0…SB-9, in ADR-0005 §11 and ROADMAP §G; first implementation is SB-1 + SB-2. |
| I8 | PR #3 is based on `8a9e625`, missing `cee2c66`; it targets `feat/context-compiler-v0`, already merged to `main`; ROADMAP still said the Context Compiler was "in review". | ROADMAP corrected; ADR-0005 reconciled against `main`. `git merge-tree` shows a clean merge onto `main`. Retargeting is left to the founder. |
| I9 | No root `AGENTS.md`/`CLAUDE.md`; the project `CLAUDE.md` pointed to a "repository-root `AGENTS.md`" that did not exist, so agents started at the repository root received no instructions. | Root routing files added; project `CLAUDE.md` wording fixed. |
| I10 | No `.gitignore` exists, although README and SECURITY-GATE said the database was excluded. An empty `data/sovereign.db` and `__pycache__` files are tracked; running the test suite modified tracked files during this review. | Documentation corrected and warns. **Not fixed here:** restoring `.gitignore` and untracking the files is a separate change (it deletes tracked files). |
| I11 | The cleanup removed the v0.1 baseline that the founding review compares against, with no commit pointer; the project README still claimed "`main` retains the original v0.1". | Pointer to `37553c0` (where all seven files were added, unchanged afterwards) in both READMEs and the founding review. |
| I12 | Benchmark 0003 assumed structured numeric data and document groupings that do not exist, and measured only candidates, not what the compiler's policy and budget admit. | Fixture built through the canonical API with ground truth as metadata; numeric case expects abstention; bundle-level metrics; budget-pressure category. |

### Optional enhancements

- Pre-configured `.obsidian/graph.json` in the demo (done; Obsidian's format is undocumented, so Start Here repeats the settings).
- W3C PROV mapping for provenance edges (noted, not adopted).
- ~~Fresh exports written oldest-first so Obsidian's time-lapse replays history (specified).~~ Withdrawn 2026-10-20 (Codex F6): Animate follows file-creation order, not MemoryClaim history; see the [remediation record](2026-10-20-codex-audit-remediation.md).
- Typed-edge rendering plugin or a native Sovereign graph explorer (later, separately evaluated).
- Property table views (core Bases or community Dataview) over the projection; not required.
- Multilingual and cross-lingual benchmark cases if the founder writes in more than one language.

### Deliberately deferred

Level 5 (scheduled ingestion, live connectors, agents); approximate-NN indexes; hosted vector or graph databases; GraphRAG/LightRAG-style model-built graphs; generated wiki prose and summaries; bidirectional Obsidian editing; model-proposed relation extraction (needs its own extraction and disclosure ADR); excerpt-level disclosure; graph-assisted context retrieval (SB-8).

## Repository cleanup audit

Each of the seven removed files was compared line by line with its project copy at `8a9e625`. `docs/adr/0000-template.md` is identical; `docs/SOURCE-NOTES.md` is a strict subset of the project copy; every other line unique to an old copy is superseded by later text in the project copy or settled by ADR-0001 (the old question on value conflicts is covered by Constitution Art. X.4). No unique, still-relevant decision or provenance was lost; the full text remains at `37553c0`. No constitutional text was modified; no code, schema, dependency or CI file changed; the test suite (588 tests) passes on the PR head.

## Checks executed

- Link checker over all Markdown (relative links, `#anchors`, vault-internal wikilinks; links leaving the Obsidian vault are flagged): no errors.
- Demo-vault validator: frontmatter parses; tags agree with status and support; `authoritative` equals approved and supported; filename suffix equals `sovereign_id`; basenames unique case-insensitively, sanitized, NFC; the graph without navigation notes is one connected component with no orphans; only lineage pairs are linked both ways.
- `git diff --check`; `pytest -q` (588 passed); `git merge-tree` against `main` (clean).
- FTS5 deletion residue with and without `secure-delete` and `PRAGMA secure_delete` (SQLite 3.45.1); presence of `secure-delete` in the SQLite FTS5 source at tags 3.41.2 (absent) and 3.42.0 (present).

**Requires manual validation:** opening the demo vault in the Obsidian application (Graph view, Local graph depth 2, color groups from `.obsidian/graph.json`, Backlinks) — not possible in the review environment.
