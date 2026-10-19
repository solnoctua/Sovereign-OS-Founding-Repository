# V0 Security Gate — before storing actual private life data

**Current status: NOT PASSED. Synthetic or intentionally non-sensitive demonstrations only.**

## Current concrete protections

- Loopback-only server documented (`127.0.0.1:8765`), fixed host allowlist, deny most cross-origin state-changing requests, JSON-only write operations.
- API keys read from environment variables rather than database or code. `.gitignore` ignores vault data, secrets and backups.
- No automatic cloud memory disclosure. Cloud context is compiled locally by deterministic policy (ADR-0004) and sent only after a per-request approval of the exact previewed bundle, bound by a context token (any relevant change → 409, no provider call). Sensitive records and claims inheriting sensitivity never leave; explicitly selected sensitive records are refused server-side. Bundles and questions are not persisted.
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
