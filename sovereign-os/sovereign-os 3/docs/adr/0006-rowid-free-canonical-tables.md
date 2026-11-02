# ADR-0006 — Rowid-free canonical tables (schema version 5)

- **Status:** **ACCEPTED** (Tier 2). Ratified by the founder on 2026-10-31, together with the ADR-0003 amendments and backup format 3, after the independent Codex Tier 2 audit of `ab51bae` returned PASS, as reported by the founder (*Founder ratification (2026-10-31)*). Merging PR #20 still needs an independent review of the exact head with a reviewer-owned findings artifact (`docs/DEVELOPMENT.md`, Tier 2), then the founder's Code Owner approval and explicit merge authorization. Not applied to any real vault. No real personal-data migration or production SB-2 deployment is authorized, and the Security Gate remains NOT PASSED.
- **Revised:** 2026-10-22 after the independent Codex audit of head `04ba75c` (verdict CHANGES REQUIRED). The audit report is reviewer-owned and is not reproduced here; see *Audit remediation*.
- **Revised again:** 2026-10-22 after the founder's decisions D-A (A1, refined), D-B (B1) and D-C (C1), now implemented (*Founder decisions*). They change the schema-5 contract and the backup format; the amendments to ADR-0003 are proposed explicitly below and take effect only with the founder's approval of this ADR.
- **Date:** 2026-10-22
- **Decision owner:** Human project owner
- **Amends:** [ADR-0003](0003-memory-claim-authority.md): the storage contract and migration sections (coverage becomes true), and, as ratified in *Amendments to ADR-0003 and the backup contract*, the authority rule (evidence-set integrity), the canonical text rule (no embedded NUL) and the backup format (version 3).
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
7. (D-A) Partial loss of a claim's evidence links is detectable, and a claim whose complete evidence set cannot be proven is never authoritative until a human revalidates it, without erasing its history or inventing evidence.
8. (D-C) SQLite and Python count the same characters for every length-limited, non-legacy canonical value (decision 6 lists the columns); legacy data is preserved, never altered.
9. (D-B) No migration or backup is reported as successful for a state that a restore would reject or shorten.

## Decision

1. **Schema version 5.** The five tables above are rebuilt `WITHOUT ROWID`, keeping their exact stored definitions with only `WITHOUT ROWID` appended. Without a rowid, the only uniqueness constraint left is each table's primary key, which the existing BEFORE triggers already guard. `claim_events` is unchanged.
2. **Migration** (`store._rebuild_without_rowid`, inside `_migrate`'s `BEGIN IMMEDIATE`, with `foreign_keys` off on that connection, per SQLite's documented ALTER TABLE procedure):
   1. Record every trigger and index definition, the row counts and the `foreign_key_check` findings.
   2. Drop **every** trigger. Cross-table trigger bodies otherwise block `ALTER TABLE … RENAME`; this was verified, since without it the rename fails.
   3. For each table: refuse a NULL primary key, create `<table>__v5 … WITHOUT ROWID`, copy all columns, drop the old table, and rename.
   4. Recreate the indexes and every trigger from their stored text.
   5. Verify that row counts, trigger and index definitions and foreign-key findings are unchanged, and that `integrity_check` returns `ok`. If verification fails, refuse.

   Version 0 goes to 4 (unchanged code) and then 5 in the same transaction. Version 4 goes to 5.
3. **Positive evidence validation** (revised after audit finding F-3): `support_of` is `supported` only when a claim has at least one link and every link is `active`, `stale` only when every link is `active` or `superseded`, and `orphaned` otherwise, including no links, missing or unverified links, and any state outside the storage CHECK set. `inherited_sensitivity` is `private` only for present, verified, `private` evidence. A source record in any state other than `active` or `superseded` is excluded from every context as `invalid_state`. These rules change no outcome for any state a CHECK-respecting writer can produce: all 168 Benchmark 0003 bundles (56 questions × `local`, `kimi`, `openai`) are byte-identical to `main`, tokens included, so `policy_version` is unchanged.
4. **Validity scan, refusal instead of carrying damage forward** (interim, audit findings F-2 and F-4): before any destructive DDL, and before an export is handed out, `Vault._validity_findings` checks the snapshot. It runs `integrity_check` (structure and every NOT NULL and CHECK constraint), `foreign_key_check` (orphaned rows), forgotten identities still present or cited, and claims with history but no evidence, and it runs the trusted-restore validator (`_parse`) with Python's character counts. Any finding raises `VaultStateInvalid` naming finding classes and counts, never contents: the migration rolls back and leaves the vault at its version, and `/api/export` answers 409. A migration or backup is therefore never reported as successful for a state that a restore would reject or shorten. Founder decision D-B (B1) keeps this refusal as the policy; schema 5 adds the classes `embedded_nul` and `evidence_set_mismatch`. After the independent adversarial review of the scan (2026-10-22), SQLite's own checks run before any row is decoded, and a value that cannot be read (text that is not valid UTF-8, which an ordinary connection can write) or any other failure while building the payload is the finding `unreadable_rows`; the refusal is raised without its cause, so no row content reaches a message, traceback or log. Counts are exact except `integrity_check` (SQLite stops at 100 problems) and `not_restorable` (the first failure), which are lower bounds.
5. **Evidence-set commitments and revalidation** (founder decision D-A, A1 refined; audit F-1).
   - **Commitment.** A new write-once table `claim_evidence_sets` (WITHOUT ROWID) holds, per claim, the number of evidence links and a SHA-256 digest binding the claim id to every `(record id, pinned evidence hash)` link (`store.evidence_set_digest`). Every claim made under schema 5 (proposal, correction, ordinary import) writes it in its creation transaction, after its links and before its creation event (`basis = creation`). Storage triggers make it write-once for any connection: no second insert, no update, no delete except when the claim is forgotten, a link count that must equal the claim's links, and a creation commitment only before the creation event. The claim Forget trigger also removes it.
   - **Integrity, a separate state.** `claims.integrity_of` derives `committed` (current links are exactly the committed set), `unconfirmed` (no commitment) or `mismatch` (links differ from the commitment). `is_authoritative` now requires `approved`, `supported` **and** `committed`. Statuses, transitions and histories are unchanged. The Context Compiler excludes an approved claim that is not committed as `revalidation_required` or `evidence_set_mismatch`; the retrieval fingerprint keeps its layout because the authority it already binds now includes integrity.
   - **Claims made before schema 5** are migrated with their status and full history but without a commitment, so they are `unconfirmed`: preserved, never authoritative, until revalidated. Migration invents no link and no commitment.
   - **Governed revalidation** (`Vault.revalidate_claim`, `POST /api/claims/{id}/revalidate`, UI dialog). The person is shown every surviving source in full and must tick each one; the request must name exactly the surviving links and their evidence hashes as displayed (a compare-and-set, so a confirmation never covers evidence nobody saw), the claim's expected status, and `confirm: true`, with an optional note. It is refused for a terminal claim, for a claim already committed or in `mismatch`, and whenever any surviving link is not current verified evidence (`support` other than `supported`). A successful revalidation writes the commitment with `basis = revalidation`, its note and time; the claim's status and history are untouched.
   - **Reconstruction.** When the surviving evidence is not adequate, the owner supersedes the claim with evidence they choose (the existing correction flow): the old claim becomes `superseded` history and the replacement starts `proposed`, committed at creation, and needs an ordinary approval.
6. **No embedded NUL in current canonical text** (founder decision D-C, C1; audit F-4). Storage triggers (not CHECK constraints, which a connection can switch off) refuse an embedded NUL in exactly these columns: non-legacy records (`id`, `content`, `source`, `created_at`, `supersedes_id`); claims (`id`, `text`, `created_at`, `supersedes_id`); evidence links (`record_id`, `evidence_sha256`); claim history (`note`, `at`); claim tombstones (`id` only); commitments (`digest`, `note`, `at`). The application write paths reject it in every value a caller supplies (ids and times they generate themselves). Trusted restore rejects it in the same columns. Ordinary import rejects it in the record and claim values it keeps, and ignores the file's history and commitments. **Not covered:** records flagged legacy, which keep theirs exactly (ADR-0002 records, and legacy rows that a trusted restore of a backup brings in); record tombstones (`id` and `deleted_at`), which accept any record id so such a record can always be forgotten; and claim tombstones' `deleted_at`. Sovereign writes tombstone times itself, but a trusted restore or a raw connection can store a NUL there, and it is then exported and restored unchanged. The tombstone columns have no length limit; legacy records keep ADR-0002's bounds, which the validity scan checks with Python's counts. No other column is covered by these triggers. A schema-4 vault holding NUL in current text is refused (`embedded_nul`), unchanged, rather than altered.
7. **Recovery of a refused vault** (founder decision D-B, B1). A refusal changes nothing: the vault stays at its version, and the message names finding classes and counts only, never the affected items. A schema-4 vault whose migration is refused cannot be opened by version-5 software at all: the app fails at start-up while opening it. The v4 software that wrote it can still open it, but only with the defect that caused the refusal and with Issue #6 unrepaired, and its backups may not restore, which is why it was refused. A schema-5 vault whose export is refused still opens, but cannot be backed up. In either version, if the vault holds text that is not valid UTF-8, the memory list and Forget of the affected record fail too (Issue #15). Sovereign offers no automatic repair. The eventual recovery pathway is explicit and offline, and is not built yet: on a *copy* of the vault file, a separate command lists each finding with its rows for the owner alone; the owner chooses, per finding, to forget the affected item or to restore it from an earlier good backup; the tool writes a new vault and the owner verifies it with an export and a restore before replacing anything. A quarantine subsystem (option B2) is not built and stays a possible later decision. Until that tool exists, a schema-4 vault refused for `embedded_nul` can sometimes be cleared with the v4 software. If the NUL is in a claim's or record's text, forgetting that item there lets the migration proceed. Correcting it is not enough, because the superseded claim or record revision keeps its text and is still refused. If the NUL is in a claim id or a claim-tombstone id, Forget does not help: forgetting writes a permanent claim tombstone with the same id, which schema 5 also refuses, so such a vault has no route to schema 5 until the recovery tool exists. These cases were checked with the v4 code at `eeed753` on the fixture `v4_nul_short`, a synthetic record and a synthetic claim with a NUL id; other locations are untested. Its v4 export cannot be restored into schema 5 either, because the same rule applies to backups (D-C).

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
| Vault damaged so that an approved claim kept only part of its evidence (F-1) | Migrates with status and history, but every claim made before schema 5 is `unconfirmed` and not authoritative until revalidated (D-A) | `test_f1_claim_that_lost_part_of_its_evidence_before_migration_is_not_authoritative`, `test_every_claim_made_before_schema_5_is_preserved_but_not_authoritative` |
| A schema-5 claim later loses a link (only possible for a process that changes the schema) | Integrity `mismatch`: never authoritative, excluded as `evidence_set_mismatch`, export refused, revalidation refused | `test_partial_link_loss_after_schema_5_is_detected_and_never_authoritative` |
| A backup whose claim lost a link but kept its commitment | Restore refused, vault unchanged | `test_a_backup_that_lost_part_of_a_claims_evidence_is_refused` |
| A schema-4 vault with an embedded NUL in current text | Refused (`embedded_nul`), vault unchanged | `test_a_schema_4_vault_with_nul_in_current_text_is_refused_unchanged` (genuine fixture `v4_nul_short`) |
| Text that is not valid UTF-8, written by an ordinary connection with default pragmas (found by the independent scan review) | Export and migration refuse with `unreadable_rows`, without the row's content in any message; the file is unchanged | `test_review_text_that_is_not_utf8_is_refused_without_disclosing_it`, `test_review_a_schema_4_vault_with_text_that_is_not_utf8_is_refused_unchanged` |
| A mistyped value in a CHECK-only column (CHECKs switched off) | Refused by `integrity_check` before any row is decoded, not a crash | `test_review_a_mistyped_value_is_refused_not_a_crash` |
| A schema-5 vault whose `user_version` was rewritten to 4 | Refused with a clear message, unchanged | `test_review_a_schema_5_vault_relabelled_as_schema_4_is_refused_clearly` |
| An embedded NUL only in a legacy record | Migrates; the record is preserved byte for byte, exported and restored | `test_a_schema_4_vault_with_nul_only_in_a_legacy_record_migrates_and_keeps_it` (genuine fixture `v4_legacy_nul`) |
| Concurrent first opens | `BEGIN IMMEDIATE` serializes; migration runs once | `test_concurrent_first_opens_of_a_v4_vault_migrate_once` |
| Newer vault opened by older software | v4 software refuses schema 5 ("newer than this software supports"); v5 refuses 6 | existing test plus `test_newer_vault_is_refused_after_v5` |
| Large vault | One rebuild copies every row once; the scan reads the snapshot once more. Measured by the independent review on synthetic vaults near the 128 MiB backup limit: whole scan 0.8–1.9 s, `export()` 3.2–4.7 s, migration 5.1–8.3 s, peak memory 2–3.5 × the export size; nothing in export, scan or migration is quadratic | synthetic only; not measured on real data |

## Compatibility and reversal

- **Code:** no Sovereign code uses `rowid`, `last_insert_rowid` or rowid ordering (verified by search). The only rowid users are the Benchmark 0003 harness's in-memory FTS tables, which are unaffected.
- **Export format:** version 3 (`sovereign.v0.records.3`) adds each claim's `evidence_set` (null for a claim made before schema 5). Versions 1 and 2 are still accepted; their claims restore `unconfirmed`. A version-3 backup whose claim links do not match its commitment is refused.
- **Reversal:** export from version 5, rewrite it as version 2 (set `schema` to `sovereign.v0.records.2` and remove every claim's `evidence_set`), and trusted-restore it into version-4 software. The released v4 code accepts it: fixture `v4_restored_from_v5_backup` is the vault that `eeed753` itself produced from such a backup (`v5_backup_as_format_2.json`). Going forward again, every row returns, but no claim is authoritative until revalidated, because the commitments were dropped (`test_reversal_route_v5_backup_restores_into_v4_software_and_back`). The route starts from an export, so it exists only for a vault that passes the validity scan, and it is tested on synthetic fixtures only. A vault the scan refuses has no reversal route and no recovery tool yet (decision 7). A direct SQL reverse rebuild is possible but is not shipped.
- **No automatic pre-migration copy:** a silent `.bak` would be an unmanaged plaintext copy that Forget cannot reach. Founder decision (2026-10-31): no automatic unmanaged plaintext backup is authorized, and this change adds no mandatory programmatic pre-upgrade export. Before any future non-disposable vault is deployed or migrated, a verified backup and recovery procedure is required.

## Verification plan for the independent reviewer

1. On `main`, run `pytest tests/adversarial/test_storage_integrity_rowid.py`. Expect failures under the `fk_on` and `fk_off` configurations, the WITHOUT ROWID check and the zero-source tests. On this branch, expect them all to pass.
2. Reproduce at least the record-deletion and tombstone-replacement attacks by hand on a disposable v4 vault, then confirm they fail on v5.
3. Confirm that after migration there are 44 triggers: the 36 of schema 4 with identical text, except `claim_tombstones_forget`, which also removes a commitment, plus the 8 schema-5 triggers (`claim_evidence_sets_*` ×3, `*_no_nul` ×5). Confirm the index set is unchanged, the five rebuilt tables differ only by `WITHOUT ROWID` and the quoted name, `claim_evidence_sets` is new and empty, and a fresh vault has the same schema as a migrated one.
4. Run the migration-failure, verification-failure, NULL-key, concurrency, reversal and damaged-vault tests. Try one additional injected failure of your own choosing.
5. Run `pytest -q`, `pytest -q tests/adversarial` and `python -m evaluation.retrieval --check` (Benchmark 0003 results must be unchanged), then `python -m compileall -q src tests evaluation`.
6. Write the findings file. The builder may only append responses.

## Audit remediation (2026-10-22)

Builder record, not the reviewer's: the finding IDs are the audit's, and the descriptions are the builder's reproduction of the founder's summary. Each was reproduced on `04ba75c` before any change, with genuine schema-4 fixtures generated by the released `eeed753` code (`tests/fixtures/v4`). Tests are in `tests/adversarial/test_pr10_audit_regressions.py` and `tests/test_schema_v5_migration.py`. **No finding is closed by this record**; closure needs a fresh independent review of the new head.

| Finding | Reproduced on `04ba75c` | Change in the first remediation (`f0b6539`) | State after the founder decisions |
| --- | --- | --- | --- |
| F-1 partial evidence-set loss across the v4 migration | An approved claim that lost one of two links stays `supported`, authoritative, and offered to a cloud plan | None to authority; a policy-independent test proves migration neither invents links nor erases history | D-A (A1) implemented: commitments and governed revalidation; pending fresh independent review |
| F-2 damaged state versus backup and restore | Zero-link vault migrates, then its backup fails to restore; a replaced-claim vault migrates with 3 FK violations and its orphaned rows are silently dropped by a restore | Validity scan; migration and export refuse such states, leaving the vault unchanged | D-B (B1) adopted as policy; recovery pathway documented; pending fresh independent review |
| F-3 negative validation of evidence states | A live v5 record in state `pending` enters a cloud plan; under v4, a claim on `archived` evidence was authoritative | Positive validation in `support_of`, `inherited_sensitivity` and source-record admission (`invalid_state`) | Fixed pending review |
| F-4 SQLite versus Python length semantics | `length()` counts 1 where Python counts 10,052; the migrated backup does not restore; live v5 storage accepts a 2,502-character claim | Validity scan uses Python counts, so such vaults are refused at migration and export | D-C (C1) implemented at both boundaries; pending fresh independent review |
| F-8 rollback test failed before destructive DDL | The injected failure fired at the first `count(*)`; no `DROP` had run | Three injections after destructive DDL, each proven by the statement log | Fixed pending review |

The states in the last column are as of 2026-10-22. On 2026-10-31 the founder reported that the independent Codex Tier 2 audit of `ab51bae` closed F-1 to F-4 and F-8 (*Founder ratification (2026-10-31)*).

## Founder decisions (2026-10-22)

Options were presented with recommended defaults in the previous revision of this ADR (preserved in commit `ddec603`). The founder decided:

- **D-A: A1, refined.** Claims made before schema 5 whose original evidence-set completeness cannot be proven stay historically preserved but non-authoritative pending explicit human revalidation; revalidation displays the surviving evidence and lets the owner confirm, or reconstruct an adequately supported claim through a governed process (a blind confirmation button is insufficient); future claims get a write-once commitment to their complete evidence set so partial-link loss becomes detectable; a separate integrity state is preferred over new ordinary statuses. Implemented as decision item 5. Not chosen: A2 (attestation), A3 (re-import; it would erase recorded decisions), A4 (heuristic; rejected).
- **D-B: B1.** Refuse invalid migrations and exports rather than pretending they succeeded; preserve the original state; report the reason without disclosing unnecessary content; document an eventual explicit offline recovery pathway; no quarantine subsystem now. Implemented as decision items 4 and 7. Not chosen now: B2 (quarantine).
- **D-C: C1.** Reject embedded NUL in new canonical text and identifiers at both the application and the storage boundary; preserve legacy data and refuse an incompatible migration rather than deleting or altering it. Implemented as decision item 6. Not chosen: C2 (byte limits), C3 (keep the interim).

## Founder ratification (2026-10-31)

The founder approved this ADR's schema-5 design, the amendments below and backup format 3, consistent with D-A, D-B and D-C:

- A claim has authority only if it is `approved`, its support is `supported` and its evidence-set integrity is `committed`.
- Claims approved before schema 5, whose complete evidence cannot be proven, stay historically preserved but are not authoritative until a governed revalidation.
- Invalid migration and export states fail closed (decisions 4 and 7).
- The embedded-NUL restrictions and their exceptions are those of decision 6, as implemented.
- No automatic unmanaged plaintext backup, and no mandatory programmatic pre-upgrade export in this change. A verified backup and recovery procedure is required before any future non-disposable vault is deployed or migrated.
- Issue #17 is accepted as a separately tracked availability risk for this synthetic-only prototype, not for personal-data production use. Issues #14–#17 remain open.
- The Security Gate remains NOT PASSED. No real personal-data migration or production SB-2 deployment is authorized.

**Audit basis, as reported by the founder:** the independent Codex Tier 2 audit dated 2026-10-31 returned PASS for PR #20's head `ab51bae`. It reported F-1 to F-4 and F-8 independently closed, no additional mandatory runtime fix, and one P3 advisory, F-11, on documentation. The audit report and its findings artifact are reviewer-owned and are not in this repository. They are to be committed unchanged by their author or the founder. The results above are the founder's report: the builder has not seen the audit text and closes no finding.

## Amendments to ADR-0003 and the backup contract

These change accepted text. The founder ratified them on 2026-10-31 (above). ADR-0003's own text is not edited beyond pointers.

1. **Authority (ADR-0003 derived support and authority):** "A claim is approved memory only if its status is `approved`, its support is `supported`, and its evidence-set integrity is `committed`." Integrity is derived on read from the commitment, like support, and is never stored as authority.
2. **Storage contract (ADR-0003 triggers):** add `claim_evidence_sets` and its write-once rules, the claim Forget trigger's removal of the commitment, and the rejection of embedded NUL in the canonical text and identifiers listed in decision 6 (legacy records, record tombstones and claim tombstones' `deleted_at` exempt).
3. **Backup contract (ADR-0003 export and restore):** the export format becomes version 3 with a per-claim `evidence_set`; a trusted restore refuses a version-3 claim whose links do not match its commitment; versions 1 and 2 restore claims as `unconfirmed`; ordinary import gives its proposals new creation commitments and ignores any in the file; import and restore reject embedded NUL in the values decision 6 lists.
4. **Lifecycle (ADR-0003 transitions):** unchanged. Revalidation is not a status transition; it writes the commitment and is recorded with its note and time in the commitment itself.

## Consequences

The Security Gate remains **NOT PASSED**. Tests establish only the following, on synthetic vaults and SQLite 3.45.1:

- hidden-rowid replacement no longer changes canonical state;
- migration from genuine v4 vaults is row-, trigger-, index- and export-equivalent, or is refused with the vault unchanged;
- rollback after destructive DDL leaves the vault unchanged;
- every export that succeeds restores losslessly for the tested fixtures;
- unknown evidence states fail closed;
- a claim made before schema 5 is never authoritative until a human revalidates exactly its surviving evidence, and the loss of a link from a schema-5 claim is detected;
- no value in the columns that decision 6 protects can hold an embedded NUL, so SQLite's and Python's lengths agree for every length-limited non-legacy value. Legacy records are measured in Python by the validity scan, and tombstone timestamps and record tombstone ids are not covered (they have no length limit).

They do **not** establish behaviour on large or real vaults or other SQLite versions. Every vault migrated from schema 4 will need its approved claims revalidated before they count as approved memory again; that is the intended cost of D-A. This closes one integrity defect against ordinary connections. It does not defend against a process that can change the schema or rewrite the file, and it does not add authentication, encryption or backups.
