# ADR-0006 — Rowid-free canonical tables (schema version 5)

- **Status:** **PROPOSED** (Tier 2). Requires an independent reviewer findings artifact (`docs/engineering/FINDINGS-FORMAT.md`) and founder approval before merge. Not applied to any real vault; no production data migration is authorized.
- **Date:** 2026-10-22
- **Decision owner:** Human project owner
- **Amends:** [ADR-0003](0003-memory-claim-authority.md) storage contract and migration sections (the contract's guarantees are unchanged; their coverage becomes true).
- **Fixes:** [Issue #6](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/issues/6), plus the evidence-empty authority gap found on 2026-10-22.

## Context

ADR-0003's storage triggers guard every canonical row against deletion, replacement and re-keying. They do so through BEFORE INSERT/UPDATE/DELETE triggers. SQLite's `REPLACE` conflict resolution deletes a conflicting row **without firing its DELETE triggers unless `recursive_triggers` is on**, a per-connection setting that is off by default and that Sovereign cannot impose on other connections.

The primary key was already guarded: a BEFORE INSERT trigger runs before REPLACE resolves a primary-key conflict. The **hidden rowid** was not. Any statement naming `rowid`, `_rowid_` or `oid` could collide with an existing row's rowid and make SQLite delete that row unguarded.

**Reproduction** (builder record, `docs/reviews/2026-10-22-issue-6-reproduction.md`; tests `tests/adversarial/test_storage_integrity_rowid.py`): on `main` at `eeed753`, SQLite 3.45.1, 24 distinct statements changed canonical state with `recursive_triggers` off. They used `INSERT OR REPLACE` or `REPLACE` naming a rowid alias, or `UPDATE OR REPLACE … SET rowid/oid`, against `records`, `tombstones`, `claims`, `claim_sources` and `claim_tombstones`. The effects were:

- A record deleted without a tombstone.
- A tombstone replaced, so forgotten evidence could return.
- An approved claim deleted with its history orphaned.
- An approved claim's only evidence link deleted.

`foreign_keys=ON` incidentally protected `claims` only. `claim_events` was not affected: its rowid *is* `seq`, which `claim_events_no_replace` guards.

**Evidence-empty authority.** `claims.support_of([])` returned `supported`. An approved claim stripped of every link therefore stayed authoritative and could be re-approved. The founder accepted the invariant on 2026-10-22: *a MemoryClaim with missing, invalid, corrupted or insufficiently verified required evidence is never authoritative.*

## Requirements (independent of the chosen fix)

1. No SQL statement on an ordinary connection, under any combination of `foreign_keys` and `recursive_triggers`, can delete, replace or re-key a row of `records`, `tombstones`, `claims`, `claim_sources`, `claim_tombstones` or `claim_events` without the corresponding guard firing.
2. A claim with zero present, hash-verified evidence links is never authoritative.
3. The migration is one transaction. On any failure the vault is left exactly at its previous version.
4. Every row, rule (trigger, CHECK, default, reference) and index is preserved. Every export of a version-4 vault restores into version 5 identically. Version-0 vaults still migrate.
5. Pre-release (1–3) and newer vaults are still refused.
6. Documentation claims no coverage that tests do not demonstrate.

## Decision (proposed)

1. **Schema version 5.** The five tables above are rebuilt `WITHOUT ROWID`, keeping their exact stored definitions with only `WITHOUT ROWID` appended. Without a rowid, the only uniqueness constraint left is each table's primary key, which the existing BEFORE triggers already guard. `claim_events` is unchanged.
2. **Migration** (`store._rebuild_without_rowid`, inside `_migrate`'s `BEGIN IMMEDIATE`, with `foreign_keys` off on that connection, per SQLite's documented ALTER TABLE procedure):
   1. Record every trigger and index definition, the row counts and the `foreign_key_check` findings.
   2. Drop **every** trigger. Cross-table trigger bodies otherwise block `ALTER TABLE … RENAME`; this was verified, since without it the rename fails.
   3. For each table: refuse a NULL primary key, create `<table>__v5 … WITHOUT ROWID`, copy all columns, drop the old table, and rename.
   4. Recreate the indexes and every trigger from their stored text.
   5. Verify that row counts, trigger and index definitions and foreign-key findings are unchanged, and that `integrity_check` returns `ok`. If verification fails, refuse.

   Version 0 goes to 4 (unchanged code) and then 5 in the same transaction. Version 4 goes to 5.
3. **Zero-source rule:** `support_of([])` returns `orphaned`. Authority (`approved` and `supported`) is therefore impossible without present, verified evidence. Approval of an orphaned claim is refused by the existing domain check, and the Context Compiler already treats evidence-less claims as `sensitive` and excludes them as `orphaned`.

## Alternatives considered

| Alternative | Why not |
| --- | --- |
| `PRAGMA recursive_triggers=ON` in Sovereign's connections | Per connection; an attacker's or tool's connection does not set it (already rejected in ADR-0003) |
| `sqlite3.Connection.set_authorizer` denying `rowid` | Per connection, same flaw |
| Application-layer checks only | Bypassed by any other connection; does not meet requirement 1 |
| A `UNIQUE` index or trigger on rowid | REPLACE resolves unique conflicts by **deleting** the other row, the very problem; triggers cannot see the hidden-rowid collision before the delete |
| Rebuilding with explicit new DDL instead of the stored definitions | Duplicates schema text and risks drift from the legacy-column definition added by `ALTER TABLE`; deriving from `sqlite_master` preserves the exact constraints, and the test checks byte equality apart from the suffix and the quoted name `RENAME` writes |
| Rebuilding `claim_events` too | `AUTOINCREMENT` is not allowed on WITHOUT ROWID tables; its rowid is `seq` and is already guarded (tested for `rowid`, `_rowid_`, `oid` and `seq`) |

## Failure modes and how they are handled

| Failure | Handling | Test |
| --- | --- | --- |
| Error at any point in the rebuild (here after all triggers are dropped and all five tables rebuilt) | Transaction rolls back; `iterdump()` identical; user_version 4; the next open succeeds | `test_failed_migration_leaves_the_v4_vault_exactly_unchanged` |
| Post-rebuild verification fails | `RuntimeError`, rollback, vault unchanged | `test_unverifiable_migration_is_refused_and_rolled_back` |
| NULL primary key in a malformed pre-claims vault | Refused with an explicit message; vault unchanged | `test_null_primary_key_in_a_malformed_legacy_vault_is_refused` |
| Vault already damaged by the Issue #6 attack | Migrated faithfully, not hidden or refused; derivation keeps the damaged claim `orphaned` and non-authoritative | `test_pre_existing_damage_is_preserved_not_hidden_or_refused` |
| Concurrent first opens | `BEGIN IMMEDIATE` serializes; migration runs once | `test_concurrent_first_opens_of_a_v4_vault_migrate_once` |
| Newer vault opened by older software | v4 software refuses schema 5 ("newer than this software supports"); v5 refuses 6 | existing test plus `test_newer_vault_is_refused_after_v5` |
| Large vault | One rebuild copies every row once and runs `integrity_check` once; cost is O(n), measured only on synthetic vaults | not measured on real data |

## Compatibility and reversal

- **Code:** no Sovereign code uses `rowid`, `last_insert_rowid` or rowid ordering (verified by search). The only rowid users are the Benchmark 0003 harness's in-memory FTS tables, which are unaffected.
- **Export format:** unchanged (`sovereign.v0.records.2`).
- **Reversal:** export from version 5 and trusted-restore into version-4 software. This is tested both ways and is identical (`test_reversal_route_v5_export_restores_into_v4_software_and_back`). A direct SQL reverse rebuild (the same procedure with rowid tables and user_version 4) is possible but is not shipped.
- **No automatic pre-migration copy:** a silent `.bak` would be an unmanaged plaintext copy that Forget cannot reach. Owners should export before upgrading a vault that matters. This is an open founder question.

## Verification plan for the independent reviewer

1. On `main`, run `pytest tests/adversarial/test_storage_integrity_rowid.py`. Expect failures under the `fk_on` and `fk_off` configurations, the WITHOUT ROWID check and the zero-source tests. On this branch, expect them all to pass.
2. Reproduce at least the record-deletion and tombstone-replacement attacks by hand on a disposable v4 vault, then confirm they fail on v5.
3. Confirm the trigger count (36) and every trigger's text are unchanged after migration. Confirm the index set is unchanged. Confirm table definitions differ only by `WITHOUT ROWID` and the quoted name.
4. Run the migration-failure, verification-failure, NULL-key, concurrency, reversal and damaged-vault tests. Try one additional injected failure of your own choosing.
5. Run `pytest -q`, `pytest -q tests/adversarial` and `python -m evaluation.retrieval --check` (Benchmark 0003 results must be unchanged), then `python -m compileall -q src tests evaluation`.
6. Write the findings file. The builder may only append responses.

## Consequences

The Security Gate remains **NOT PASSED**. This closes one integrity defect against ordinary connections. It does not defend against a process that can change the schema or rewrite the file, and it does not add authentication, encryption or backups.
