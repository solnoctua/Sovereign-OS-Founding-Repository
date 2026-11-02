# PR #10 Codex audit — builder remediation record, 2026-10-22

**Status:** builder-authored evidence. This is **not** an independent review, not a findings artifact, and not the audit. The Codex audit is the reviewer's own document and should be committed unchanged, by its author or the founder, as `docs/reviews/2026-10-22-pr10-codex-audit.md` (or as `…-findings.json` under `docs/engineering/FINDINGS-FORMAT.md`). The builder did not have the audit's text; it worked from the founder's directive, which summarizes F-1 to F-4 and F-8. The finding IDs below are the audit's. The descriptions are the builder's reading of that summary. **No finding is closed by this record.** Closure needs a fresh independent review of the new head.

**Environment:** pinned audited head `04ba75ce7d59e62f7e2d021ac54cfa92e4303be1`, confirmed as the PR head before any change. Python 3.13.16, SQLite 3.45.1, synthetic vaults only.

## Method

1. **Genuine schema-4 fixtures.** `tests/fixtures/v4/generate_v4_fixtures.py` runs against a detached worktree of the released schema-4 code (`eeed753`). Through ordinary vault operations it produces one clean vault and five damaged vaults, the damage being exactly what the Issue #6 attacks and a CHECK bypass leave behind. It dumps each vault as SQL that reloads exactly, rowids included. SHA-256 hashes are in `tests/fixtures/v4/README.md`.
2. **Regressions written first.** `tests/adversarial/test_pr10_audit_regressions.py` and the F-8 changes in `tests/test_schema_v5_migration.py` were run against `04ba75c` before any code changed.
3. **The smallest change per finding.** The policy-dependent parts were left open as founder decisions (below).

## Regression evidence

| Run | `test_pr10_audit_regressions.py` |
| --- | --- |
| Pinned `04ba75c` (code unchanged, new tests; pinned `src` first on `PYTHONPATH`) | **12 failed, 9 passed, 2 xfailed** |
| This revision | **21 passed, 2 xfailed (strict)** |

The 12 failures on `04ba75c` are listed below. The 9 tests that passed there are positive controls: the clean-vault round trip, the "no invention, no erasure" check, and the already-correct `support_of` cases.

- F-2 (5 failures):
  - all four damaged fixtures migrate, where the test expects them to be refused with the vault unchanged;
  - export of a live damaged vault succeeds.
- F-3 (6 failures):
  - four unknown or unverified state sets reach `supported` or `stale`;
  - a live record in state `pending` enters every provider's context;
  - a claim on `archived` evidence is authoritative and approvable.
- F-4 (1 failure): a claim of 10,052 characters with an embedded NUL is exported, where SQLite's `length()` reports 1.

The two strict xfails are the policy-dependent tests. Each fails today and will start passing, failing the run, when its decision is implemented:

- `test_f1_claim_that_lost_part_of_its_evidence_before_migration_is_not_authoritative` (D-A);
- `test_f4_storage_refuses_text_whose_sqlite_length_hides_characters` (D-C).

**F-8:** the migration-rollback test is parametrized over three injected failures after destructive DDL:

- `ALTER TABLE claim_tombstones__v5 RENAME`;
- `CREATE TRIGGER records_well_formed`;
- the second `PRAGMA integrity_check`.

For each, a statement log proves that every `DROP TRIGGER` and the `DROP TABLE` of all five rebuilt tables ran before the failure. On `04ba75c` the old injection fired at the first `count(*)`, before any `DROP`.

## Results on this revision

| Check | Result |
| --- | --- |
| `pytest -q` (full) | 665 passed, 2 xfailed |
| `pytest -q tests/adversarial` | 556 passed, 2 xfailed |
| `tests/test_schema_v5_migration.py` | 12 passed |
| `python -m evaluation.retrieval --check` | exit 0. `results.json` unchanged. `report.md` regenerated: it gains an all-zero `invalid_state` reason column |
| Benchmark 0003 bundles: 56 questions × `local`, `kimi`, `openai` = 168 compiled bundles, comparing tokens, plan descriptions and receipts | byte-identical on `main` (`eeed753`), `04ba75c` and this revision (canonical JSON sha256 prefix `17bd68094cb87888`) |

## Decisions requested

The three founder decisions (D-A, D-B and D-C) are set out in [ADR-0006 § Decisions requested from the founder](../adr/0006-rowid-free-canonical-tables.md#decisions-requested-from-the-founder). Each gives exact alternatives and a recommended default.

At the time of the round above, F-1 was open: an approved claim that lost part of its evidence set before schema 5 kept its authority after migration. The founder decided D-A, D-B, D-C, D-E and D-F on 2026-10-22 (next section).

## Founder decisions round (2026-10-22)

The founder approved A1 (refined), B1 and C1, and decided D-E and D-F (`docs/FOUNDER-DECISIONS.md` on PR #8, [ADR-0006 § Founder decisions](../adr/0006-rowid-free-canonical-tables.md#founder-decisions-2026-10-22)). This PR implements D-A, D-B and D-C. D-E and D-F are repository settings, prepared on PR #9. The Codex audit text was still not available to the builder; the directive's summary remained the only source for the findings.

**Implemented on this PR:**

- **D-A (F-1).**
  - Claims made before schema 5 are kept, with their statuses and histories unchanged, but have integrity `unconfirmed`. They are not authoritative and are excluded from context as `revalidation_required` until the owner revalidates them.
  - Revalidation shows every surviving source in full and needs each one confirmed. It is a compare-and-set on exactly those links and hashes, so it is not a blind button. Inadequate evidence is reconstructed through the existing supersede flow.
  - New claims commit their complete evidence set write-once (`claim_evidence_sets`). Losing part of a link set is now detectable as integrity `mismatch`.
  - Backup format `sovereign.v0.records.3` carries the commitment. Formats `.1` and `.2` restore their claims as `unconfirmed`.
- **D-B (F-2).** Invalid vaults are refused with classes and counts only, and the file is left unchanged. The offline recovery pathway is documented (ADR-0006 decision 7) but not built. There is no quarantine subsystem.
- **D-C (F-4).** Embedded NUL is rejected in new canonical text and identifiers by application validators and by storage triggers (44 triggers in total). Legacy records keep theirs exactly. A schema-4 vault holding NUL in current text is refused, unchanged.

The amendments to ADR-0003 and to the backup contract are **proposed, not ratified** (ADR-0006 § Proposed amendments).

**Policy-dependent xfails replaced.** The two strict xfails became passing regressions:

- `test_f1_claim_that_lost_part_of_its_evidence_before_migration_is_not_authoritative`;
- `test_f4_storage_refuses_text_whose_sqlite_length_hides_characters` (three cases). The hidden-length export case now uses a legacy record, the only place schema 5 still allows a NUL.

**Old vaults** in the migration tests are now genuine schema-4 fixtures written by `eeed753`, replacing the earlier emulation. The new fixtures are `v4_nul_short`, `v4_legacy_nul`, a clean export, and a schema-5 backup rewritten to format 2 and restored by `eeed753`. Hashes are in `tests/fixtures/v4/README.md`.

### Regression evidence for the decisions

| File | Pinned `ddec603` (before the decisions) | `114ecd2` (decisions implemented) |
| --- | --- | --- |
| `tests/adversarial/test_evidence_set_commitments.py` (D-A) | 17 failed | 17 passed |
| `tests/adversarial/test_embedded_nul.py` (D-C) | 13 failed, 2 passed (the legacy-preservation controls) | 15 passed |
| `tests/adversarial/test_pr10_audit_regressions.py` | 4 failed, 21 passed | 25 passed |

### Independent adversarial review of the validity scan

At the founder's request, a reviewer with no part in writing the scan reviewed it for consistency, recovery behaviour and resource use. This was a separate builder-side agent, not the Codex audit, and is not a substitute for it. It fuzzed about 38,000 damaged states and found no state that the scan let through and a restore then rejected.

| ID | Finding | Disposition |
| --- | --- | --- |
| F1 | Text that is not valid UTF-8, which an ordinary connection can write, crashed export and migration with a traceback quoting the row | Fixed in `5e722b2`: `unreadable_rows`, raised without its cause |
| F2 | A mistyped value in a CHECK-only column crashed the payload build before `integrity_check` could report it | Fixed: SQLite's checks run before any row is decoded |
| N1 | `integrity_check` (capped at 100 by SQLite) and `not_restorable` (first failure) are lower bounds | Documented in the docstring and ADR-0006 |
| N2 | Trusted restore is quadratic when many legacy records name the same predecessor | Pre-existing on `main`; tracked as [Issue #16](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/issues/16) |
| N3 | No guidance for a schema-4 vault refused for `embedded_nul` | Interim guidance in ADR-0006 decision 7 |
| N4 | Export peaks at about 3.3–3.9 × the backup size in memory | Pre-existing behaviour (`36c9bbc`); noted only |
| N5 | A schema-5 vault relabelled as schema 4 failed with a confusing error | Fixed: refused with a clear message |

The five review regressions in `test_pr10_audit_regressions.py` fail on `a267b6a` and pass on `5e722b2`. The reviewer measured synthetic vaults near the 128 MiB backup limit:

- the whole scan took 0.8–1.9 s;
- `export()` took 3.2–4.7 s;
- migration took 5.1–8.3 s.

Nothing in export, scan or migration is quadratic.

**Tracked separately** (not part of this PR):

- the unbounded `GET /api/claims` history response ([Issue #14](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/issues/14));
- the app-wide effect of non-UTF-8 text, which is pre-existing on `main`: `GET /api/memories` answers 500, the row cannot be forgotten through the app, and the exception text quotes the row ([Issue #15](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/issues/15));
- N2, the quadratic restore ([Issue #16](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/issues/16)).

### Results on `5e722b2`

| Check | Result |
| --- | --- |
| `pytest -q` (full) | 706 passed |
| `pytest -q tests/adversarial` | 597 passed |
| `tests/test_schema_v5_migration.py` | 12 passed |
| `python -m evaluation.retrieval --check` | exit 0. `results.json` unchanged. `report.md` gains all-zero `revalidation_required` and `evidence_set_mismatch` columns |
| Benchmark 0003 bundles (168) | byte-identical to `main` (`17bd68094cb87888`). The harness restores its claims in format 3 with creation commitments, so they are committed and their tokens are unchanged |

**No finding is closed by this record.** F-1 to F-4 and F-8 now have implementations and passing regressions on this branch. Closing them needs a fresh independent audit of the exact final head, followed by founder approval of ADR-0006.
