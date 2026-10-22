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

**F-1 remains open.** Until D-A is decided and implemented, an approved claim that lost part of its evidence set before schema 5 keeps its authority after migration. Every vault today is synthetic, so no real authority is at stake, but the PR must not merge as a complete repair of Issue #6 while F-1 is open.
