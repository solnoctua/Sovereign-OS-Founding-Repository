# ADR-0006 — Rowid-free canonical tables (schema version 5)

- **Status:** **PROPOSED** (Tier 2). Requires an independent reviewer findings artifact (`docs/engineering/FINDINGS-FORMAT.md`) and founder approval before merge. Not applied to any real vault; no production data migration is authorized.
- **Revised:** 2026-10-22 after the independent Codex audit of head `04ba75c` (verdict CHANGES REQUIRED). The audit report is reviewer-owned and is not reproduced here; see *Audit remediation* for what changed and what remains open. Three decisions (D-A, D-B, D-C) are requested from the founder before the policy-dependent parts are implemented.
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
3. **Positive evidence validation** (revised after audit finding F-3): `support_of` is `supported` only when a claim has at least one link and every link is `active`, `stale` only when every link is `active` or `superseded`, and `orphaned` otherwise, including no links, missing or unverified links, and any state outside the storage CHECK set. `inherited_sensitivity` is `private` only for present, verified, `private` evidence. A source record in any state other than `active` or `superseded` is excluded from every context as `invalid_state`. These rules change no outcome for any state a CHECK-respecting writer can produce: all 168 Benchmark 0003 bundles (56 questions × `local`, `kimi`, `openai`) are byte-identical to `main`, tokens included, so `policy_version` is unchanged.
4. **Validity scan, refusal instead of carrying damage forward** (interim, audit findings F-2 and F-4): before any destructive DDL, and before an export is handed out, `Vault._validity_findings` checks the snapshot. It runs `integrity_check` (structure and every NOT NULL and CHECK constraint), `foreign_key_check` (orphaned rows), forgotten identities still present or cited, and claims with history but no evidence, and it runs the trusted-restore validator (`_parse`) with Python's character counts. Any finding raises `VaultStateInvalid` naming finding classes and counts, never contents: the migration rolls back and leaves the vault at its version, and `/api/export` answers 409. A migration or backup is therefore never reported as successful for a state that a restore would reject or shorten. Whether such vaults should instead be quarantined is decision D-B.

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
| Error after destructive DDL: at the last table's rename (every trigger and all five tables already dropped), while recreating triggers, or at the post-rebuild verification | Transaction rolls back; `iterdump()` identical; user_version 4; the next open succeeds. The statement log proves the failure came after `DROP TRIGGER` and `DROP TABLE` for all five tables (audit F-8: the earlier test failed before the first `DROP`) | `test_failed_migration_after_destructive_ddl_leaves_the_v4_vault_exactly_unchanged` ×3, on a genuine v4 vault |
| Post-rebuild verification fails | `RuntimeError`, rollback, vault unchanged | `test_unverifiable_migration_is_refused_and_rolled_back` |
| Vault holds a state no backup could restore exactly (claim with history but no evidence, orphaned link or history rows, CHECK violations, lengths hidden behind an embedded NUL) | `VaultStateInvalid` before any DDL; vault unchanged at version 4 | `test_f2_vault_holding_states_no_backup_could_restore_is_not_migrated` ×4 genuine v4 fixtures |
| Live vault later holds such a state (only possible for a connection that disables CHECKs or changes the schema) | `export()` raises `VaultStateInvalid`; `/api/export` returns 409; nothing is handed out | `test_f2_export_refuses_a_live_state_that_restore_would_reject`, `test_f4_length_hidden_behind_an_embedded_nul_is_never_exported` |
| NULL primary key in a malformed pre-claims vault | Refused by the validity scan (`not_restorable`); the rebuild's own NULL-key refusal remains as defence in depth; vault unchanged | `test_null_primary_key_in_a_malformed_legacy_vault_is_refused` |
| Vault already damaged by the Issue #6 attack so that a restore would fail | **Refused** (revised after audit F-2; earlier revisions migrated it and produced an unrestorable backup) | `test_pre_existing_damage_is_refused_not_carried_forward` |
| Vault damaged so that an approved claim kept only part of its evidence | **Migrates, and the claim stays authoritative.** This is open audit finding F-1, decision D-A | `test_f1_…_is_not_authoritative` (strict xfail until D-A is implemented) |
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

## Audit remediation (2026-10-22)

Builder record, not the reviewer's: the finding IDs are the audit's, and the descriptions are the builder's reproduction of the founder's summary. Each was reproduced on `04ba75c` before any change, with genuine schema-4 fixtures generated by the released `eeed753` code (`tests/fixtures/v4`). Tests are in `tests/adversarial/test_pr10_audit_regressions.py` and `tests/test_schema_v5_migration.py`. **No finding is closed by this record**; closure needs a fresh independent review of the new head.

| Finding | Reproduced on `04ba75c` | Change in this revision | State |
| --- | --- | --- | --- |
| F-1 partial evidence-set loss across the v4 migration | An approved claim that lost one of two links stays `supported`, authoritative, and offered to a cloud plan | None to authority; a policy-independent test proves migration neither invents links nor erases history | **Open: decision D-A** |
| F-2 damaged state versus backup and restore | Zero-link vault migrates, then its backup fails to restore; a replaced-claim vault migrates with 3 FK violations and its orphaned rows are silently dropped by a restore | Validity scan; migration and export refuse such states, leaving the vault unchanged | Interim fail-closed; quarantine alternative is **decision D-B** |
| F-3 negative validation of evidence states | A live v5 record in state `pending` enters a cloud plan; under v4, a claim on `archived` evidence was authoritative | Positive validation in `support_of`, `inherited_sensitivity` and source-record admission (`invalid_state`) | Fixed pending review |
| F-4 SQLite versus Python length semantics | `length()` counts 1 where Python counts 10,052; the migrated backup does not restore; live v5 storage accepts a 2,502-character claim | Validity scan uses Python counts, so such vaults are refused at migration and export | Interim fail-closed; storage rule is **decision D-C** |
| F-8 rollback test failed before destructive DDL | The injected failure fired at the first `count(*)`; no `DROP` had run | Three injections after destructive DDL, each proven by the statement log | Fixed pending review |

## Decisions requested from the founder

**D-A. Claims approved before schema 5 whose evidence-set completeness cannot be established (F-1).** Schema 4 never recorded how many evidence links a claim had, so a link removed by the Issue #6 attack before migration leaves no trace. Schema 5 prevents new losses but cannot detect old ones.

| Option | What happens | Satisfies "no authority from one remaining link" | Cost |
| --- | --- | --- | --- |
| **A1 (recommended)** Re-confirmation | Migration records every claim that existed before schema 5 in a new canonical table. Such a claim derives a new support state `unconfirmed` and is not authoritative until the owner re-confirms it with a recorded human decision. History is kept, nothing is invented, and nothing is grandfathered | Yes | One review per historical approved claim. Today every vault is synthetic, so the cost is zero now. Needs a schema element and an ADR-0003 amendment |
| A2 Explicit owner attestation | The owner runs the migration with a flag stating no other process wrote to the vault, recorded as a governance event; claims keep their authority | Only by trusting an unverifiable statement | Low effort; not silent, but still grandfathering |
| A3 Re-import route | Refuse in-place migration of vaults holding approved or contested claims; the owner exports with v4 software and does an untrusted import, so claims arrive as proposals | Yes | Loses the recorded decision history (the import keeps only a note), which conflicts with "do not erase historical approval" |
| A4 Heuristic detection | Flag claims whose v4 link rowids show the replacement pattern; others keep authority | No: undetected losses are silently grandfathered | Rejected |

**D-B. Representation of states no backup could restore (F-2).**

| Option | What happens | Cost |
| --- | --- | --- |
| **B1 (recommended, implemented as the interim)** Refuse | Migration and export refuse with finding classes and counts; the vault is unchanged and stays usable under the software that wrote it | A damaged vault cannot be migrated or backed up until it is repaired by hand |
| B2 Quarantine | Migration moves invalid rows, losslessly and raw, into quarantine tables that never count for authority, context or graph; exports carry a `quarantine` section that restore reproduces; the owner then forgets or repairs | Schema and export-format change (new backup contract), plus a repair UI |

**D-C. Storage semantics for lengths and embedded NUL (F-4).** SQLite's `length()` stops at an embedded NUL, and no pure-SQL expression counts the remaining characters (verified on 3.45.1: `replace`, `substr` and blob casts all stop too); only `instr(x, char(0))` sees it.

| Option | What happens | Cost |
| --- | --- | --- |
| **C1 (recommended)** Forbid embedded NUL in new canonical text | Storage adds `instr(x, char(0)) = 0` to non-legacy text checks and Python validators reject NUL, so both layers count the same characters; legacy rows keep NUL and are checked in Python by the scan | A validity-contract change. It is cheapest before schema 5 is released, and needs a schema 6 afterwards |
| C2 Byte-based limits everywhere | Limits in UTF-8 bytes (`octet_length` and `len(s.encode())`) | Changes every limit's meaning; CJK text loses two-thirds of its budget |
| C3 Keep the interim | Storage keeps `length()`; the validity scan refuses mismatches at migration and export | A raw connection can still store an over-long NUL value; it is caught only when exporting or migrating |

## Consequences

The Security Gate remains **NOT PASSED**. Tests establish only the following, on synthetic vaults and SQLite 3.45.1:

- hidden-rowid replacement no longer changes canonical state;
- migration from genuine v4 vaults is row-, trigger-, index- and export-equivalent, or is refused with the vault unchanged;
- rollback after destructive DDL leaves the vault unchanged;
- every export that succeeds restores losslessly for the tested fixtures;
- unknown evidence states fail closed.

They do **not** establish the completeness of evidence sets for claims approved before schema 5 (F-1), behaviour on large or real vaults, or other SQLite versions. This closes one integrity defect against ordinary connections. It does not defend against a process that can change the schema or rewrite the file, and it does not add authentication, encryption or backups.
