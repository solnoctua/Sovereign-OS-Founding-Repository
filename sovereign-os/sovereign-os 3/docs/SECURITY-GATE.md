# V0 Security Gate — before storing actual private life data

**Current status: NOT PASSED. Synthetic or intentionally non-sensitive demonstrations only.**

## Current concrete protections

- Loopback-only server documented (`127.0.0.1:8765`), fixed host allowlist, deny most cross-origin state-changing requests, JSON-only write operations.
- API keys read from environment variables rather than database or code. `.gitignore` ignores vault data, secrets and backups. **Known defect (found 2026-10-19):** the repository currently has **no** `.gitignore`; an empty `data/sovereign.db` and `__pycache__` files are tracked, so running the app or tests from the project folder modifies tracked files. Until a separate fix restores the ignore rules and untracks those files, check `git status` before every commit.
- No automatic cloud memory disclosure. Cloud context is compiled locally by deterministic policy (ADR-0004) and sent only after a per-request approval of the exact previewed bundle, bound by a context token (any relevant change → 409, no provider call). Sensitive records and claims inheriting sensitivity never leave; explicitly selected sensitive records are refused server-side. Cloud prompts carry request-scoped labels (M1/E1…), never durable record or claim IDs. Bundles and questions are not persisted.
- Local evidence mode never calls a model provider.
- Imported content treated as data in prompts; no external tool calling enabled.
- Memory claims: ordinary import cannot create approved claims, change or delete local data, or raise an existing claim's support; trusted restore requires explicit confirmation; claim lifecycle, history, evidence identity and links, supersession lineage and Forget are enforced by SQLite triggers for all DML including `REPLACE`/upsert forms (not against schema changes by a process controlling the vault file). Exports are single-snapshot and bounded by one shared size limit. See ADR-0003.

## Missing security and reliability protections

- User authentication / device binding and comprehensive browser/localhost threat model. No remote exposure permitted.
- Encrypted vault at rest with key management and tested recovery; OS disk encryption cannot substitute for all application risks.
- Authenticated offline iPhone capture and protected synchronization.
- Consent and disclosure receipts with precise provider policy/retention metadata; sensitive-topic classification beyond a user-chosen label.
- Robust deletion across SQLite WAL, logs, backups, sync, indexes, provider transmissions; secure erasure is NOT claimed.
- Signed/integrity-checked backups (trusted restore currently trusts the file it is given) and authenticated user/device identity for claim decisions.
- Security reviews, dependency scan, input-size/rate limits, error monitoring and more complete adversarial tests.
- Backup of encrypted state plus test of restoration to a fresh Mac.

Do not use real sensitive medical/financial/relationship data, third-party conversations, account secrets, or raw personal history until the security gate is passed.

## Proposed second-brain/graph exposure risks — not yet mitigated

ADR-0005 proposes optional FTS/embedding indexes, typed relationship projections and an Obsidian-compatible local Markdown export. **None is an implemented security control or safe real-data capability.** Generated filenames, note links, graph topology, entity names, vectors, preview snippets and export manifests may reveal private information even without full source text. New derived stores must be protected, export-scoped and removed on Forget/correction; unauthorized cloud uploads, Obsidian Sync/plugin leakage, residual backups and local UI/API access all require explicit threat models and tests before real personal use. Specific mechanisms to design for (ADR-0005 §6–§7 and §9, OBSIDIAN-PROJECTION §7, §8 and §11):

- **FTS5 deletions** leave terms in index segments, and therefore in the database file, unless the FTS5 `secure-delete` option (SQLite ≥ 3.42) is enabled; `PRAGMA secure_delete` alone does not remove them (reproduced on SQLite 3.45.1 during the 2026-10-19 review).
- **Embeddings are content:** published inversion attacks recover much of the input text from vectors.
- **Retrieval can disclose:** cloud embedding, query rewriting, routing, reranking or extraction would send personal content outside an approved plan.
- **A wider relevance gate is a wider disclosure gate:** semantic retrieval makes more unpinned private items eligible for cloud plans.
- **Exports are outside the vault transaction:** an exporter that read a snapshot before a Forget could republish the forgotten content after the Forget's cleanup. The design fences publication with the vault write lock and reconciles after every Forget or trusted restore, but cleanup can still be pending (for example an unplugged folder), and Obsidian caches and file-recovery snapshots, trash, OS backups and search indexes, sync services and plugins can retain copies Sovereign cannot erase.
- **Untrusted Markdown is active content:** record or claim text containing links, embeds, remote images, HTML, tags or plugin code blocks would create fabricated graph edges, forged properties or network requests when opened in Obsidian. The design renders all such text inside inert fenced blocks; a zero-network-request native test is an acceptance gate.
- **Graph structure leaks excluded items:** a link, title, filename or navigation entry can reveal a sensitive or out-of-scope record even when its text is excluded. The design computes the authorized node set before any edge and replaces excluded endpoints with a fixed, non-identifying sentence.
- **Filesystem writes:** an export endpoint without authentication would let any same-origin client write files; exports are CLI-only and refuse Git working trees and folders they do not own.

No change to the current NOT PASSED status.
