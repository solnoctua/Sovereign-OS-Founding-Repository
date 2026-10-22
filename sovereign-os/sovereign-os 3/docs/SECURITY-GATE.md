# V0 Security Gate — before storing actual private life data

**Current status: NOT PASSED. Synthetic or intentionally non-sensitive demonstrations only.**

## Current concrete protections

- Loopback-only server documented (`127.0.0.1:8765`), fixed host allowlist, deny most cross-origin state-changing requests, JSON-only write operations.
- API keys read from environment variables rather than database or code. Repository hygiene: a root `.gitignore` excludes vault DBs, Python caches, environment files and common key formats; the previously tracked prototype `data/sovereign.db` and `__pycache__` artifacts have been removed from the current tree, and CI checks tracked paths. This is **not** a secret scanner or a Git-history purge. Review `git status` and staged diffs before every commit; if real private data ever entered Git history, treat it as a separate incident requiring investigation and remediation.
- No automatic cloud memory disclosure. Cloud context is compiled locally by deterministic policy (ADR-0004) and sent only after a per-request approval of the exact previewed bundle, bound by a context token (any relevant change → 409, no provider call). Sensitive records and claims inheriting sensitivity never leave; explicitly selected sensitive records are refused server-side. Cloud prompts carry request-scoped labels (M1/E1…), never durable record or claim IDs. Bundles and questions are not persisted.
- Local evidence mode never calls a model provider.
- Imported content treated as data in prompts; no external tool calling enabled.
- Memory claims: ordinary import cannot create approved claims, change or delete local data, or raise an existing claim's support; trusted restore requires explicit confirmation; claim lifecycle, history, evidence identity and links, supersession lineage and Forget are enforced by SQLite triggers for all DML including `REPLACE`/upsert forms (not against schema changes by a process controlling the vault file). **Hidden-rowid defect (found 2026-10-20, Issue #6) repaired in schema 5** ([ADR-0006](adr/0006-rowid-free-canonical-tables.md), PR #10): the canonical tables have no rowid, so `INSERT OR REPLACE`/`REPLACE` or `UPDATE OR REPLACE … SET rowid` can no longer delete or replace a row without its guard firing, with or without `recursive_triggers`. Claims made before schema 5 are preserved but not authoritative until a human revalidates their surviving evidence, new claims commit their complete evidence set write-once, a vault no backup could restore exactly is refused unchanged, and current canonical text cannot hold an embedded NUL. This holds against connections; a process that can change the schema or rewrite the file is outside it. Vaults migrated from schema 4 need their approved claims revalidated before they count as approved memory again. (PR #3 first documented the defect.) Exports are single-snapshot and bounded by one shared size limit. See ADR-0003.

## Missing security and reliability protections

- User authentication / device binding and comprehensive browser/localhost threat model. No remote exposure permitted.
- Encrypted vault at rest with key management and tested recovery; OS disk encryption cannot substitute for all application risks.
- Authenticated offline iPhone capture and protected synchronization.
- Consent and disclosure receipts with precise provider policy/retention metadata; sensitive-topic classification beyond a user-chosen label.
- Robust deletion across SQLite WAL, logs, backups, sync, indexes, provider transmissions; secure erasure is NOT claimed.
- Signed/integrity-checked backups (trusted restore currently trusts the file it is given) and authenticated user/device identity for claim decisions.
- Security reviews, dependency scan, input-size/rate limits, error monitoring and more complete adversarial tests.
- Backup of encrypted state plus test of restoration to a fresh Mac.
- **Lineage sensitivity (ADR-0005 D15, deferred by the founder 2026-10-21):** a private claim that supersedes a sensitive claim may restate it, and under current ADR-0004 behavior (unchanged) its text is eligible for cloud plans. No lineage-sensitivity policy is ratified; changing this needs a dedicated Tier 2 policy proposal, independent adversarial review and founder approval. The deferral does not certify current lineage sensitivity as safe for real private data. **Proposal prepared (2026-10-22):** [ADR-0007](adr/0007-lineage-sensitivity.md) (PROPOSED), transitive and fail-closed over claim supersession **and record correction**. It also records a sibling gap: the record-correction API accepts a lower `sensitivity` than the record it corrects.

Do not use real sensitive medical/financial/relationship data, third-party conversations, account secrets, or raw personal history until the security gate is passed.

## Proposed second-brain/graph exposure risks — not yet mitigated

ADR-0005 discusses deferred FTS/embedding indexes, typed relationships as structured MemoryClaims (future), and an Obsidian-compatible local Markdown export. **None is an implemented security control or safe real-data capability.** Generated filenames, note links, graph topology, entity names, vectors, preview snippets and export manifests may reveal private information even without full source text. New derived stores Sovereign manages must be protected, export-scoped and removed on Forget/correction (user-held exports: see below); unauthorized cloud uploads, Obsidian Sync/plugin leakage, residual backups and local UI/API access all require explicit threat models and tests before real personal use. Specific mechanisms to design for (ADR-0005 §6–§7 and §9, OBSIDIAN-PROJECTION §7, §8 and §11):

- **FTS5 deletions** leave terms in index segments, and therefore in the database file, unless the FTS5 `secure-delete` option (SQLite ≥ 3.42) is enabled; `PRAGMA secure_delete` alone does not remove them (reproduced on SQLite 3.45.1 during the 2026-10-19 review).
- **Embeddings are content:** published inversion attacks recover much of the input text from vectors.
- **Retrieval can disclose:** cloud embedding, query rewriting, routing, reranking or extraction would send personal content outside an approved plan.
- **A wider relevance gate is a wider disclosure gate:** semantic retrieval makes more unpinned private items eligible for cloud plans.
- **Exports are snapshots outside Sovereign's control:** an Obsidian export shows the vault as of its snapshot time and is not kept in sync. Forgetting something in Sovereign does not erase exports already made — downloaded ZIPs, extracted folders and their copies — nor Obsidian caches, file-recovery snapshots and trash, OS backups and search indexes, sync services or plugins. The design discloses this in the Forget preview and result, the export report and every exported note, makes a new export reflect its snapshot, and claims no secure deletion of exported or temporary files.
- **Untrusted Markdown is active content:** record or claim text containing links, embeds, remote images, HTML, tags or plugin code blocks would create fabricated graph edges, forged properties or network requests when opened in Obsidian. The design renders all such text inside inert fenced blocks; a zero-network-request native test is an acceptance gate.
- **Graph structure leaks excluded items:** a link, title, filename or navigation entry can reveal a sensitive or out-of-scope record even when its text is excluded. The design computes the authorized node set before any edge, replaces excluded endpoints with a fixed, non-identifying sentence, and verifies every export structurally before offering it.
- **Filesystem writes and downloads:** an export endpoint without authentication would let any local client write files or download every included note; V0 exports are CLI-only, write only a new ZIP or a new folder (plus their own hidden temporary file or staging folder beside it), always refuse Git working trees and existing files or folders, refuse other Obsidian vaults unless explicitly confirmed, and refuse known sync and network locations on a best-effort basis. A later UI download button needs its own threat review.

## Status update 2026-10-22 (founder directive; consolidation)

This section was written before the Issue #6 repair; PR #10 updated its first two items. The PR that changes one of these facts updates this section in the same PR; the facts the code can show (schema version, stated limits, known gaps, what is implemented) are checked against the code by `tests/test_systems_registry.py`.

- **Issue #6 (hidden-rowid replacement):** reproduced on 2026-10-22 against `eeed753`; repaired by schema 5 (ADR-0006, PR #10), including ADR-0003's storage-contract sentence on coverage "with or without `recursive_triggers`", which is now true.
- **Zero-source authority:** `claims.support_of([])` is `orphaned` since PR #10, and authority also requires a committed evidence set. The founder-accepted invariant holds: *a MemoryClaim with missing, invalid, corrupted or insufficiently verified required evidence is never authoritative.*
- **D15 (lineage sensitivity):** still deferred; the Tier 2 policy proposal is [ADR-0007](adr/0007-lineage-sensitivity.md) (PROPOSED, not ratified, not implemented; PR #13). Current behaviour is unchanged and not certified safe for real private data.
- **Enforcement claims:** `ARCHITECTURE.md` §14 now states, per mechanism, what K1 and K2 resist and do not resist. SQLite triggers are an integrity mechanism against connections, not a security boundary against processes; the single egress call site is a correctness property of one process, not isolation.

### Usage thresholds (labels, not permissions)

No threshold is authorized merely by being named. Each requires explicit threat modelling, independent verification and founder approval before any data of that class enters a vault.

| Threshold | Name | Requires (all independently reviewed) | Data permitted |
| --- | --- | --- | --- |
| 1 | Safe synthetic development | Current state | Synthetic fixtures only |
| 2 | Deliberately non-sensitive project use | PR #5 merged; WP-0 reconciled; a separate project vault file; the owner's written discipline that nothing private enters it | Project, study, development and public knowledge |
| 3 | Intermediate private use under disclosed limitations | Issue #6 repair and zero-source rule merged; D15 resolved; bearer token on every `/api` route; vault file mode 0600; FileVault verified on; provider keys in Keychain; encrypted backups with a restore drill on a fresh account; no sync; residual risks written down (journal pages, Spotlight, Time Machine, provider retention) | The owner's own private data; no third-party sensitive content; no account secrets |
| 4 | Trusted lifelong personal data | Threshold 3 plus: app-level or hardware-backed encryption decision; signed backups; device identity and revocation; deletion lifecycle across backups; independent security review of the whole | Full personal life |
| 5 | Governed external actions | K3 broker in a separate process; grants, scoped tokens, receipts, idempotency; adversarial injection tests | Side effects |
| 6 | More autonomous operation | Standing grants with review cadence; budgets; stop controls; measured approval burden; ADR-0005 §10 gates | Proactive agents |

Authentication alone does not pass any threshold. Localhost is not isolation. A loopback model endpoint is not proof of offline operation.

No change to the current NOT PASSED status.
