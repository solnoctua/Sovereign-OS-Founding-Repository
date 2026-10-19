# ADR-0003 — Source evidence versus derived memory claims (V0)

- Status: Proposed (Benchmark 0001; Tier 2 — hardened after independent audit of `c847f9d`; requires delta audit and founder approval)
- Date: 2026-10-19
- Decision owner: Human project owner

## Context

Constitution Article IV.4: *persistence is not authority* — evidence may be retained without being believed, an extracted claim may exist without being approved, and an approved claim may later be contested or superseded. Article III.2 requires that the user can delete personal data **and derived records**. ARCHITECTURE §4A/§5 require that a derived interpretation never silently becomes fact. An adversarial audit of `c847f9d` reproduced forged authority via import, claim resurrection across vaults, derived text surviving source deletion, raw-SQL lifecycle bypasses, source-link manipulation and concurrent decisions producing unreplayable history. This revision closes those.

## Decision

### Evidence and claims
- Source records (`records`) are evidence. After creation they are immutable except `active → superseded` (correction), enforced by triggers.
- A `MemoryClaim` (`claims`) is a separate, immutable row linked via `claim_sources` to 1–8 records. Each link pins the SHA-256 of the evidence content it was made from (`evidence_sha256`).
- Claims are never sent to a model; `/api/ask` accepts only active source-record IDs.

### Provenance
- `origin` is a provider-neutral class: `human` (local UI/API), `model` (reserved for a future internal extraction path, `Vault.add_claim(..., "model")`; not reachable from HTTP), or `imported` (ordinary import).
- The browser cannot supply `origin`: the create API forbids extra fields, so a client-supplied `origin`, `status` or `history` is a 422.
- `claim_events` is an append-only history (`from_status`, `to_status`, `actor`, `note`, `at`), the V0 form of `MemoryPromotionDecision`.
- V0 has **no authenticated user or device identity**, so `actor = 'human'` means "via the local decision path", not a verified person.

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
- Correction happens only by supersession. In one transaction, the old claim → `superseded` and a new `proposed` claim with `supersedes_id` and new evidence links is created.
- **Authoritative = `approved` AND every link's evidence is present, active, and hash-identical.**
  - A corrected source makes a claim `stale`.
  - A missing, substituted or never-seen source makes it `orphaned` (shown per source as `missing` or `unverified`).

### Concurrency
- Every decision HTTP request must carry `expected_status` (the state the human saw). Writes run in `BEGIN IMMEDIATE` transactions.
- The storage trigger additionally requires each event's `from_status` to equal the claim's current status (compare-and-set).
- Two conflicting decisions from the same state therefore never both succeed: one commits, the other gets 409 and leaves no event.

### Forget (the default meaning of Delete)
`DELETE /api/memories/{id}` forgets:
- the record and its earlier revisions (record tombstones);
- every claim linked to any of them, including that claim's text, links, history and notes (claim tombstones).

`DELETE /api/claims/{id}` forgets one claim. Tombstones are permanent, content-free, and block re-insertion of the same IDs. WAL, backup and forensic erasure is **not** claimed.

A separate future operation — *remove evidence, retain derived memory* (orphaning) — is deliberately not offered in V0.

### Import vs trusted restore

| | `POST /api/import` (ordinary, untrusted) | `POST /api/restore` (trusted, `{"confirm_trusted_restore": true, "backup": …}`) |
| --- | --- | --- |
| Records | imported as evidence (local tombstones win) | imported (tombstones win) |
| Claims | live claims (`proposed`/`approved`/`contested` in the file) become new `proposed` claims, `origin = imported`; supplied history and approvals ignored and noted; `rejected`/`superseded` skipped | history validated and replayed through the lifecycle triggers; prior authority preserved |
| File tombstones | only filter the file's own content; **cannot delete local data** | **dominate**: matching local records are forgotten with dependent claims; matching local claims are forgotten |
| Claims on forgotten evidence | skipped | skipped and tombstoned |
| Existing local claim | never overwritten | never overwritten |

Backup signing is deferred, so trusted restore trusts the file the user explicitly confirms.

### Storage contract (SQLite triggers, `store.py` `CLAIMS_SCHEMA`)

For any connection issuing INSERT/UPDATE/DELETE, with or without `PRAGMA foreign_keys`, the triggers enforce the following.
- **Claims:**
  - Created only as `proposed`; never reusing a tombstoned ID.
  - `text`, `origin`, `created_at` and `supersedes_id` are immutable.
  - Status changes only via an event: the event trigger applies it, and a direct `UPDATE` must match the latest event.
  - Terminal statuses are final.
  - Removed only through a tombstone.
- **Events:**
  - Exactly one creation event, by the claim's origin, after its links exist.
  - Transitions only by `human`, only along the table, only from the current status.
  - No update; no delete except by tombstone.
- **Links:** fixed once the creation event exists; no update; no delete except by tombstone.
- **Tombstones** (record and claim): no update or delete.
- **Records:** immutable except `active → superseded`; no re-insert of a tombstoned ID.

**Not guaranteed:**
- Schema changes (`DROP TRIGGER`, `writable_schema`) or direct file edits by a process that already controls the vault file.
- Distinguishing a raw-SQL but lifecycle-legal human-attributed event from a UI decision, since there is no authentication.
- The approval-requires-supported-evidence check is domain-level only. A raw-SQL approval of unsupported evidence is still never *authoritative*, because authority is derived on read.

### Migration
- `PRAGMA user_version`: 0 = records-only vaults (ADR-0002); 2 = this schema.
- Migration 0 → 2 is additive (new tables and triggers; existing rows byte-identical) and runs in one `BEGIN IMMEDIATE` transaction.
- It refuses newer vaults, and refuses vaults from the unreleased drafts (`user_version = 1` from `c847f9d`, or an unversioned `claims` table).

## Alternatives considered

- *Orphan instead of forget* (the `c847f9d` behaviour): rejected for V0 because it keeps derived personal text after the user deleted its evidence. It remains a possible future, explicitly named operation.
- *Signed backups*: the right long-term mechanism for trusted restore; deferred because key custody is not designed yet.
- *Demote everything on restore*: would break the user's own backups.
- *Optional `expected_status`*: lets approve-then-reject both succeed under a race (legal, but two conflicting user actions both "win"). Required at the HTTP boundary instead.

## Consequences and risks

- Forget is broad: one source deletion removes every claim citing it, including multi-source claims. The UI states the count before confirming.
- A user who restores a backup from an attacker-supplied file grants that file authority. The explicit confirmation and the wording of the restore UI are the V0 mitigation.
- Approval with no authentication: anyone able to make local same-origin JSON requests can approve.
- Claim history is removed with its claim on forget (by design).

## Migration and reversibility

- To reverse, drop the four claim tables and the triggers on `records`/`tombstones`, then set `PRAGMA user_version = 0`.
- Alternatively, export and restore records into an older build after stripping the `claims` keys and setting `schema` to `.1`.
- Tested: migration of a records-only vault, rollback on forced failure, and refusal of newer and pre-release vaults.

## Validation

- `tests/test_memory_claims.py` covers behaviour.
- `tests/test_memory_claims_adversarial.py` holds one or more regression tests for each audit blocker:
  - forged ordinary import;
  - restore-confirmation bypass and illegal histories;
  - cross-vault tombstones and restore ordering;
  - forget → export → restore → old-export replay;
  - 23 raw-SQL attacks × FK on/off;
  - evidence-link surgery and evidence substitution;
  - storage compare-and-set;
  - threaded vault-level races and HTTP races with a replay check.
