# Issue #6 reproduction record — builder evidence, 2026-10-22

**Status:** builder-authored reproduction evidence, **not** an independent review and not a findings artifact. The independent reviewer writes `docs/reviews/<date>-issue-6-findings.json` separately (`docs/engineering/FINDINGS-FORMAT.md`).

**Environment:** `main` at `eeed753311382047fb2042515a5d2d0f68e94b04`; Python 3.13; SQLite 3.45.1; disposable synthetic vaults only.

**Method:** commit `39853be` adds `tests/adversarial/test_storage_integrity_rowid.py` before any fix. Each attack was also run alone, on a freshly populated vault, under each of four pragma configurations, comparing every row of the six canonical tables before and after.

**Results on `main`.** The table counts the 36 rowid attacks: 6 tables × (3 aliases + `REPLACE` + 2 `UPDATE OR REPLACE`).

| Configuration | Attacks that changed canonical state |
| --- | --- |
| `foreign_keys` ON, `recursive_triggers` OFF | 18: `records` ×6, `tombstones` ×4, `claim_sources` ×4, `claim_tombstones` ×4 |
| `foreign_keys` OFF, `recursive_triggers` OFF | 24: the above plus `claims` ×6 |
| `recursive_triggers` ON (either FK setting) | 0 |

- **Unaffected in every configuration:**
  - The 9 primary-key replacement forms.
  - `claim_events`, whose rowid is `seq`.
  - The `UPDATE OR REPLACE … SET rowid` form on tables whose triggers fire on any update (`tombstones`, `claim_sources`, `claim_tombstones`, `claim_events`).
- **Observed effects:**
  - A record deleted with no tombstone (`UPDATE OR REPLACE records SET rowid=…`).
  - Records, tombstones and claim tombstones replaced by forged rows.
  - An approved claim deleted, leaving links and history orphaned.
  - An approved claim's only evidence link deleted, after which `support_of([])` returned `supported`, so the claim stayed authoritative and could be re-approved.

**After the fix** (this branch): all 36 rowid attacks and 9 primary-key attacks leave canonical state unchanged under all four configurations. The full suite and the adversarial suite pass, and the Benchmark 0003 `--check` passes (results unchanged). Details are in ADR-0006 and the PR.
