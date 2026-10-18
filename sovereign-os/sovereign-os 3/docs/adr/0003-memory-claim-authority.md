# ADR-0003 — Source evidence versus derived memory claims (V0)

- Status: Proposed (Benchmark 0001 implementation; requires independent review and founder approval — Tier 2)
- Date: 2026-10-18
- Decision owner: Human project owner

## Context

ARCHITECTURE §4A and §5 require that a derived interpretation never silently becomes a "fact" and that source evidence stays distinct from claims. ADR-0002 listed the claim state schema as an immediate next decision. Benchmark 0001 specifies the first slice.

## Decision

- **Source records stay evidence** and are unchanged by this feature. A `MemoryClaim` is a separate row (`claims`) linked through `claim_sources` to 1–8 source-record IDs. Provenance stored: source IDs, `created_at`, `status`, `decided_at`, and `origin` (`human` | `model`).
- **Lifecycle:** `proposed → approved | rejected`. Creation always writes `proposed`; the store method has no status parameter, the API model forbids extra fields (a client-supplied `status`/`decided_at` is a 422, not silently ignored), and a SQL `CHECK` ties `decided_at` to a non-proposed status. Decisions are final in V0 (no un-approve; delete and re-propose instead).
- **Explicit human decision:** `POST /api/claims/{id}/approve|reject` requires the JSON body `{"confirm": true}` and passes the existing same-origin/JSON-only middleware. No model code path calls these endpoints; no model has tool execution.
- **Claim support is derived, not stored.** On every read, each claim computes `support` from its current evidence: `supported` (all sources active), `stale` (a source was corrected/superseded), or `orphaned` (a source was deleted or is absent). `authoritative = status == approved AND support == supported`. Only `supported` proposed claims may be approved. Because nothing is cached, deleting evidence takes effect immediately and cannot drift out of sync.
- **Deletion of evidence orphans, it does not cascade.** The claim keeps its text and its decision history but no longer presents as supported. Claims can be deleted explicitly (`DELETE /api/claims/{id}`), which writes a content-free claim tombstone.
- **Portability:** export schema `sovereign.v0.records.2` adds `claims` and `claim_tombstones`; `.1` exports still import. Import is idempotent and never overwrites an existing local claim (so it cannot change a local decision). Record tombstones still win, so deleted evidence is never resurrected; claims citing it import as `orphaned`. Claim tombstones prevent deleted claims from returning. Malformed claims (bad status/origin, approved without `decided_at`, proposed with one, bad source list) fail the whole import transaction.
- **Claims never leave the vault.** `/api/ask` only accepts active source-record IDs; claims are not included in cloud context.

## Alternatives considered

- *Stored `invalidated` flag set at delete time* — extra write path that import/restore must also maintain; derivation is simpler and cannot be bypassed.
- *Cascade-delete claims with their evidence* — strongest privacy outcome but silently destroys human-written interpretations and decision history; rejected for V0, see risks.
- *Demote imported approvals to proposed* — safer against forged files but violates "export/import preserves authority state" for the user's own backups.

## Consequences and risks

- **Claim text can restate deleted evidence.** Orphaning keeps it; the UI flags the claim as unsupported and offers deletion. A future policy may cascade-delete or prompt on evidence deletion.
- **Import trusts the export file for approvals.** A hand-crafted export could restore `approved` claims into an empty vault. Mitigations: local-only JSON endpoint, no overwrite of existing claims, the response reports `approved_claims_restored`, and such claims still become non-authoritative if their evidence is missing. Signed/integrity-checked exports are deferred.
- `origin` is a self-declared label in V0 (no authentication or model extraction exists yet). It records provenance; it does not grant or restrict authority — every origin needs the same explicit approval.
- No `contested/superseded` claim states, risk classes, promotion policy, or decision-audit table yet (ARCHITECTURE §6 `MemoryPromotionDecision`). `decided_at` is the only decision record.

## Migration and reversibility

New tables are created with `CREATE TABLE IF NOT EXISTS`; existing `records`/`tombstones` are untouched, so an existing vault opens unchanged. Reverting the code leaves the extra tables unused and harmless; dropping them removes only claims. Older `.1` exports remain importable; a `.2` export can be read by older code only after removing the `claims` keys and resetting `schema`.

## Validation

`tests/test_memory_claims.py`: default `proposed`, smuggled-authority rejection, explicit approve/reject with confirmation, final decisions, cross-origin/form-encoded rejection, invalid/missing/duplicate/too-many source IDs, superseded sources (stale), deletion orphaning, export/restore preserving status without resurrecting evidence or deleted claims, import unable to elevate an existing claim, atomic rejection of malformed claims, `.1` compatibility, and claims excluded from cloud requests while the sensitive/approval restrictions still hold.
