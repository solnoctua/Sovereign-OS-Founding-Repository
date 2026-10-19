# ADR-0003 — Source evidence versus derived memory claims (V0)

- Status: Proposed (Benchmark 0001; Tier 2 — hardened after independent audits of `c847f9d` and `708e9de`; requires delta audit and founder approval)
- Date: 2026-10-19
- Decision owner: Human project owner

## Context

Constitution Article IV.4: *persistence is not authority* — evidence may be retained without being believed, an extracted claim may exist without being approved, and an approved claim may later be contested or superseded. Article III.2 requires that the user can delete personal data **and derived records**. ARCHITECTURE §4A/§5 require that a derived interpretation never silently becomes fact.

Two adversarial audits shaped this revision:
- **`c847f9d`** reproduced forged authority via import, claim resurrection across vaults, derived text surviving source deletion, raw-SQL lifecycle bypasses, source-link manipulation, and concurrent decisions producing unreplayable history.
- **`708e9de`** reproduced:
  - SQLite `REPLACE` semantics rewriting claims and erasing history;
  - source records replaced under the same ID (stale authority restored, sensitivity downgraded);
  - raw source deletion bypassing Forget;
  - partial restore plus ordinary import rebuilding authority piecemeal;
  - incoherent exports under concurrency;
  - unvalidated supersession graphs;
  - a 100-event ceiling that made legitimate claims unrestorable.

**Governing invariant:** once Sovereign records an epistemic decision, no lower-level storage, import, deletion, replacement, restore or concurrency operation may silently change its meaning or authority.

## Decision

### Evidence and claims
- **Source records (`records`) are evidence with insert-only identity.**
  - A record ID is never replaced: no `REPLACE`, upsert or delete-then-insert.
  - It is never resurrected after being forgotten.
  - It never appears *after* a claim cites it, or after its own correction.
  - Its identity fields (content, source, sensitivity, created time, lineage) are immutable.
  - Its status changes only `active → superseded`, and only by inserting its correction.
- **A `MemoryClaim` (`claims`) is a separate, immutable row** linked via `claim_sources` to 1–8 records.
  - Each link pins `evidence_sha256`: a SHA-256 over the record's identity (`id, content, source, sensitivity, created_at, supersedes_id`).
  - An approval made against evidence E therefore never transfers to a different E′ that reuses E's ID, including one that differs only in sensitivity.
- **Claims are never sent to a model.** `/api/ask` accepts only active source-record IDs, and evidence sensitivity is immutable.

### Provenance
- **`origin` is a provider-neutral class:**
  - `human`: local UI/API.
  - `model`: reserved for a future internal extraction path, `Vault.add_claim(..., "model")`; not reachable from HTTP.
  - `imported`: ordinary import.
- **The browser cannot supply `origin`.** The create API forbids extra fields, so a client-supplied `origin`, `status` or `history` is a 422.
- **`claim_events` is an append-only history** (`from_status`, `to_status`, `actor`, `note`, `at`), the V0 form of `MemoryPromotionDecision`.
- **No authenticated identity in V0.** `actor = 'human'` means "via the local decision path", not a verified person.

### Lifecycle (`claims.py`, compiled into the triggers)

| From | Allowed to |
| --- | --- |
| *(create)* | `proposed` only |
| `proposed` | `approved`, `rejected`, `contested`, `superseded` |
| `approved` | `contested`, `rejected`, `superseded` |
| `contested` | `approved`, `rejected`, `superseded` |
| `rejected`, `superseded` | — terminal |

- Every claim, of any origin, is created `proposed`.
- Human authority is immediately revocable: `approved → rejected` needs no contest step.
- Approval requires intact evidence (checked in the domain layer).
- **Correction happens only by supersession.** In one transaction, the old claim → `superseded`, then a new `proposed` claim is created with `supersedes_id` and its own fixed evidence links.
- **Authoritative = `approved` AND every link's evidence is present, active and hash-identical.**
  - A corrected source makes a claim `stale`.
  - A missing or non-identical source makes it `orphaned` (shown per source as `missing` or `unverified`).
- **History length is unbounded.** Approve/contest cycles are legitimate, so there is no per-claim event ceiling.

### Supersession graphs (records and claims)
- **Lineage is linear.** No self-supersession; at most one successor per record or claim. **Multiple descendants (forks) are not allowed in V0.**
- **Lineage is built oldest-first.**
  - A record or claim cannot be inserted after its successor exists, which also makes cycles impossible.
  - A claim replacement requires its predecessor to be already `superseded`, or absent (for example, forgotten).
  - A record correction may name an `active` predecessor (it is superseded by the insert) or an already-superseded one with no successor.
- **Payload chains are validated:** no self-supersession, duplicate IDs, forks or cycles, and an item with a successor in the payload must be `superseded`. Valid chains are applied predecessors-first, whatever their order in the file.

### Concurrency
- **One SQLite transaction per operation.** Writes use `BEGIN IMMEDIATE`; reads, including the whole export, use one read transaction. An export is therefore a single snapshot: before or after any concurrent change, never a mixture.
- **Decisions are compare-and-set.**
  - Every decision HTTP request must carry `expected_status`.
  - The storage trigger requires each event's `from_status` to equal the claim's current status.
  - Two conflicting decisions never both succeed: one commits, the other gets 409 and leaves no event.

### Forget (the default meaning of Delete)
- **Forgetting is a storage-level operation:** writing a record's tombstone.
  - A trigger removes the record and tombstones every claim citing it.
  - The claim tombstones remove each claim's text, links, history and notes.
  - A raw `DELETE FROM records` is refused, so Forget cannot be bypassed.
  - Tombstones are permanent, content-free and idempotent; `REPLACE` cannot rewrite them.
  - Claims can never cite forgotten evidence.
- **`DELETE /api/memories/{id}`** forgets that record and every earlier revision still present (lineage walks backward). A newer revision survives if only an older one is forgotten.
- **`DELETE /api/claims/{id}`** forgets one claim.
- **Not claimed:** WAL, backup and forensic erasure. API forgets run with `secure_delete`; raw-SQL connections may not.
- **Deferred:** a separate future operation, *remove evidence, retain derived memory* (orphaning), is deliberately not offered in V0.

### Import vs trusted restore

| | `POST /api/import` (ordinary, untrusted) | `POST /api/restore` (trusted, `{"confirm_trusted_restore": true, "backup": …}`) |
| --- | --- | --- |
| Records | added as new evidence only | merged predecessors-first |
| Never introduced (both) | a record that already exists (never replaced); one forgotten here; one cited by a claim already in the vault (would raise that claim's support); one whose correction is already here | same |
| Correcting local evidence | refused (an untrusted file cannot change local state) | allowed if unambiguous; it only lowers support |
| Claims | live claims (`proposed`/`approved`/`contested` in the file) become new `proposed` claims, `origin = imported`, with a deterministic namespaced ID (UUIDv5 of the file's ID), so a file can never occupy a genuine claim's ID; history and approvals are noted, not trusted; attached only to evidence present here; `rejected`/`superseded` skipped | history validated and replayed through the lifecycle triggers; prior authority preserved |
| File tombstones | only filter the file's own content; **cannot delete local data** | **dominate**: matching local records are forgotten with dependent claims; matching local claims are forgotten |
| Claims on forgotten evidence | skipped | skipped and tombstoned |
| Existing local claims | never changed; support never raised | never changed; support never raised |

- **Unsigned backups.** Signing is deferred, so trusted restore trusts the file the user explicitly confirms.
- **Partial vaults stay partial.** A partially restored vault cannot later be completed for claims that already cite missing evidence; those claims stay non-authoritative. Recovery is a full restore into a fresh vault.

### Size policy
- **There are no count limits.** The former 10,000-item caps and the 100-event cap were removed.
- **One explicit limit, `MAX_BACKUP_BYTES` (128 MiB), is shared by all three paths:**
  - export refuses (413) to produce a larger file;
  - import and restore refuse larger bodies (413) and bodies without `Content-Length` (411).
- **Restore accepts everything storage accepts.** Storage CHECKs and triggers enforce the same well-formedness rules restore validates: text types, lengths, ≤ 8 links, notes ≤ 500, legal histories. So any state Sovereign can hold within the size limit exports and restores, exactly, with the same software version.

### Storage contract (SQLite triggers, `store.py` `CLAIMS_SCHEMA`)

The triggers enforce the following for any connection issuing INSERT/UPDATE/DELETE, including `INSERT OR REPLACE`, `REPLACE` and upsert forms. Every insert is checked by a BEFORE INSERT trigger, which runs before SQLite's REPLACE deletions. This holds with or without `PRAGMA foreign_keys` and `recursive_triggers`. There are no `ON DELETE CASCADE` actions; rows are removed only by the forget triggers.
- **Claims:**
  - Never replaced or re-created; never reusing a tombstoned ID.
  - Created only as `proposed`.
  - `text`, `origin`, `created_at` and `supersedes_id` are immutable.
  - Status changes only via an event; a direct `UPDATE` must match the latest event, and terminal statuses are final.
  - Linear supersession as above.
  - Removed only through a tombstone.
- **Events:**
  - Never replaced.
  - Exactly one creation event, by the claim's origin, after its links exist.
  - Transitions only by `human`, only along the table, only from the current status.
  - No update; no delete except by tombstone.
- **Links:**
  - Never replaced.
  - Fixed once the creation event exists; at most 8.
  - Never citing forgotten evidence.
  - No update; no delete except by tombstone.
- **Records:** as in *Evidence and claims* above.
- **Tombstones** (record and claim): idempotent; no update or delete. Inserting one performs the complete forget.

**Not guaranteed:**
- Schema changes (`DROP TRIGGER`, `writable_schema`) or direct file edits by a process that already controls the vault file.
- Distinguishing a raw-SQL but lifecycle-legal human-attributed event (or a raw-SQL forget or correction) from a UI action, since there is no authentication.
- The approval-requires-supported-evidence check is domain-level only. A raw-SQL approval of unsupported evidence is still never *authoritative*: authority is derived on read, and unsupported evidence can never become supported later (it cannot arrive, revert or change identity).
- Exports hold a read lock for their duration; a concurrent write waits up to the 10 s busy timeout.

### Migration
- **Versions** (`PRAGMA user_version`): 0 = records-only vaults (ADR-0002); 3 = this schema.
- **Migration 0 → 3** is additive (new tables, indexes and triggers; existing rows byte-identical) and runs in one `BEGIN IMMEDIATE` transaction.
- **Refused:** vaults newer than this version, and vaults from the unreleased drafts (`user_version` 1 = `c847f9d`, 2 = `708e9de`, or an unversioned `claims` table).

## Alternatives considered

- *Orphan instead of forget* (the `c847f9d` behaviour): rejected for V0 because it keeps derived personal text after the user deleted its evidence. It remains a possible future, explicitly named operation.
- *Unique indexes for lineage*: rejected, because `INSERT OR REPLACE` resolves unique-index conflicts by **deleting** the other row. BEFORE INSERT triggers are used instead.
- *`PRAGMA recursive_triggers` so REPLACE deletions fire DELETE triggers*: rejected, because it is per-connection and an attacker's connection would not set it.
- *Coercing malformed payloads*: rejected. Payloads are validated against the same rules as storage and rejected whole.
- *Signed backups*: the right long-term mechanism for trusted restore; deferred because key custody is not designed yet.
- *Demote everything on restore*: would break the user's own backups.
- *Optional `expected_status`*: lets approve-then-reject both succeed under a race (legal, but two conflicting user actions both "win"). Required at the HTTP boundary instead.

## Consequences and risks

- **Forget is broad:** one source deletion removes every claim citing it, including multi-source claims. The UI states the count before confirming.
- **Trusted restore trusts its file:** a user who restores a backup from an attacker-supplied file grants that file authority. The explicit confirmation and the wording of the restore UI are the V0 mitigation.
- **Record IDs can still be squatted:** ordinary import keeps record IDs (pre-existing behaviour, covered by the original tests). An untrusted file can occupy a record ID before a genuine trusted restore arrives. That cannot raise authority (identity hashes differ) but can leave genuine claims `unverified`.
- **No authentication:** anyone able to make local same-origin JSON requests can approve.
- **History goes with its claim:** claim history is removed with its claim on forget (by design).

## Migration and reversibility

- **To reverse:** drop the four claim tables, the triggers on `records`/`tombstones` and `ix_records_supersedes`, then set `PRAGMA user_version = 0`.
- **Alternatively:** export and restore records into an older build after stripping the `claims` keys and setting `schema` to `.1`.
- **Tested:** migration of a records-only vault, rollback on forced failure, and refusal of newer and pre-release vaults.

## Validation

- `tests/test_memory_claims.py` covers behaviour.
- `tests/test_memory_claims_adversarial.py` covers the `c847f9d` audit blockers.
- `tests/test_memory_claims_hardening.py` covers the `708e9de` audit blockers. Raw-SQL attacks run under four pragma configurations (foreign keys and recursive triggers on/off):
  - SQL replacement in three statement forms;
  - source replacement and sensitivity downgrade;
  - E vs E′ for each identity field;
  - raw delete and raw tombstone forget;
  - the reported partial-restore attack and variants;
  - export races against decisions, supersession, forget and correction (every export restores and round-trips exactly);
  - record and claim lineage attacks and malformed payloads;
  - histories of 260+ events and backups over 10,000 records;
  - the shared size limit;
  - randomised operation sequences across two vaults, asserting that import/restore never raise existing authority and that every vault stays coherent and restorable.
