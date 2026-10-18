# ADR-0003 — Source evidence versus derived memory claims (V0)

- Status: Proposed (Benchmark 0001 implementation; Tier 2 — requires independent review and founder approval)
- Date: 2026-10-18
- Decision owner: Human project owner

## Context

Constitution Article IV.4: *persistence is not authority* — evidence may be retained without being believed, an extracted claim may exist without being approved, and an approved claim may later be contested or superseded. ARCHITECTURE §4A/§5 require that a derived interpretation never silently becomes fact. ADR-0002 listed the claim schema as an immediate next decision; Benchmark 0001 specifies the first slice.

## Decision

**Evidence vs. claims.** Source records (`records`) are unchanged evidence. A `MemoryClaim` (`claims`) is a separate, immutable row linked via `claim_sources` to 1–8 source-record IDs. Claims are never included in model context; `/api/ask` accepts only active source-record IDs.

**Provenance.** Each claim stores `origin` (`human` | `model` — a provider-neutral provenance class; no provider or model name enters the core schema), `created_at`, its source IDs, `supersedes_id` for corrections, and an append-only `claim_events` history (`from_status`, `to_status`, `actor`, optional `note`, `at`) — the V0 form of `MemoryPromotionDecision`.

**Lifecycle** (`src/sovereign/claims.py`, pure domain rules):

| From | Allowed to |
| --- | --- |
| *(create)* | `proposed` only |
| `proposed` | `approved`, `rejected`, `contested`, `superseded` |
| `approved` | `contested`, `superseded` |
| `contested` | `approved`, `rejected`, `superseded` |
| `rejected` | — terminal |
| `superseded` | — terminal |

- Every claim, whether human-written or model-proposed, is created `proposed`. The create API forbids extra fields, so a client-supplied `status` is a 422, not ignored.
- Every status change is an explicit human action (`POST /api/claims/{id}/approve|reject|contest|supersede` with `{"confirm": true}`, behind the existing same-origin/JSON-only middleware), and is recorded as an event with `actor = 'human'`. No model code path calls these endpoints.
- Approval requires intact evidence (`support == supported`).
- Retracting an approved claim takes two visible steps: contest, then reject.
- **Supersession is the only correction path.** The old claim becomes `superseded`, and a new `proposed` claim with `supersedes_id` is created atomically, so a correction must itself be approved. The old text, sources and history are kept.
- A rejected claim cannot be reactivated, contested, superseded or overwritten by import. Re-proposing the same idea creates a new, visibly separate `proposed` claim.

**Storage-level guards** (SQLite triggers, independent of the API): inserts must be `proposed`; terminal statuses cannot change; a status change must match the latest recorded event; claim text/origin/sources-of-record fields are immutable; events cannot be updated; a non-creation event must have a human actor.

**Derived support and authority.** On every read each claim computes `support` from its current evidence — `supported` (all sources active), `stale` (a source was corrected), or `orphaned` (a source was deleted or is absent) — and `authoritative = status == approved AND support == supported`. Nothing is cached, so evidence changes take effect immediately.

**Source deletion policy: orphan, do not cascade.** Deleting a source record leaves dependent claims in place with their status and history, but they derive as `orphaned`, can never be authoritative or approved, and show the source as `deleted` with no content. Claims can be deleted explicitly (`DELETE /api/claims/{id}`), which removes their history and writes a content-free claim tombstone.

**Portability.** Export schema `sovereign.v0.records.2` adds `claims` (with full history and source IDs) and `claim_tombstones`; `.1` exports still import.
- Import replays each claim's history through the same lifecycle rules. It rejects the whole import if a history doesn't start with creation as `proposed` by the claim's origin, has a non-human decision, makes an illegal transition (e.g. `rejected → approved`), or doesn't end at the stated status.
- Import never overwrites an existing local claim, so it cannot change a local decision.
- Record and claim tombstones win, so deleted evidence and claims are not resurrected. Claims citing deleted evidence import as `orphaned`.

**Migration.** The vault schema is versioned with `PRAGMA user_version` (0 = records-only vaults from ADR-0002; 1 = claims). Migration is additive and runs in one transaction. It refuses vaults newer than the software, and refuses an unversioned `claims` table left by the unreleased first benchmark draft, rather than guessing.

## Alternatives considered

- *Stored `invalidated` flag at delete time* — another write path that import must maintain; derivation cannot drift.
- *Cascade-delete claims with their evidence* — strongest privacy outcome but silently destroys human interpretations and decision history. Kept as an open founder decision (see risks).
- *Demote imported approvals to proposed* — safer against forged files, but breaks "export/import preserves claim state" for the user's own backups.
- *Allow `approved → rejected` directly / `rejected → proposed`* — fewer clicks, but weakens the "rejected stays rejected" and "retraction is visible" guarantees.
- *Naming:* ARCHITECTURE §4A sketches `proposed → active → contested/superseded/deleted`; this ADR uses the benchmark's `approved` for `active`, and models deletion as removal + tombstone rather than a status.

## Consequences and risks

- **Claim text may restate deleted evidence.** Orphaned claims keep their text until explicitly deleted. Whether evidence deletion should cascade to (or prompt about) dependent claims is a privacy/epistemic trade-off for the founder.
- **Imports trust the file.** A hand-crafted but lifecycle-legal export can restore `approved` claims into a vault that lacks them. Mitigations: local-only JSON endpoint; existing claims never overwritten; the response reports `approved_claims_restored`; such claims are non-authoritative if their evidence is absent. Signed exports are deferred.
- **`origin` and `actor` are self-declared** in V0 (no authentication; no automatic model extraction exists yet). They record provenance; every origin requires the same explicit human approval.
- No risk classes, promotion policy, automatic promotion, or confidence fields (out of scope). Claim history is deleted with its claim.

## Migration and reversibility

Version 0 → 1 only creates new tables, indexes and triggers; `records`/`tombstones` rows are byte-for-byte unchanged (tested). A forced failure mid-migration leaves the vault at version 0 with no new tables (tested). Reversal: drop `claims`, `claim_sources`, `claim_events`, `claim_tombstones` (triggers drop with their tables) and set `PRAGMA user_version = 0`; or export and restore records into an older build after stripping the `claims` keys and setting `schema` to `.1`.

## Validation

`tests/test_memory_claims.py` (35 tests) covers: model-origin defaults to `proposed`; smuggled authority fields rejected; only approved-and-supported claims are authoritative; explicit, confirmed, recorded approval/rejection; cross-origin/form-encoded refusal; terminal rejection (API, transition table, and SQLite triggers); contest → resolve; supersession linkage and atomicity; source correction → stale; invalid source IDs; deletion → orphaned; export/import round-trip equality including history; non-resurrection; import cannot change decisions; illegal imported histories rejected atomically; `.1` compatibility; migration of a records-only vault, rollback on failure, refusal of newer/pre-release vaults; claims never sent to cloud; sensitive/approval cloud gates intact.
