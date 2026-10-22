# Genuine schema-4 vault fixtures

Each `.sql` file is a lossless dump of a vault produced by the **released schema-4 code at `eeed753`**: its own `Vault` API, plus, where a fixture records damage, the Issue #6 attack itself on an ordinary default-pragma connection. They are not emulations of version 4. `generate_v4_fixtures.py` regenerates them from a checkout of that commit (ids and times are random per run; tests locate items by text). Text values are written as `CAST(X'…' AS TEXT)` so embedded NUL characters survive exactly. Each file reloads and re-dumps byte-identically, and the v4 code opens each one without migrating (verified 2026-10-22). Synthetic data only.

| Fixture | Produced by | Used for |
| --- | --- | --- |
| `v4_clean` | v0 legacy rows migrated by v4; corrections, every claim status, supersession, claim Forget, record Forget, a 7-event history | migration equivalence, rollback after destructive DDL |
| `v4_partial_link_loss` | an approved claim on two sources loses one link to the Issue #6 attack | F-1 |
| `v4_zero_link_loss` | an approved claim with history loses its only link | F-2 |
| `v4_claim_row_replaced` | an approved claim row is replaced; its link and events are orphaned | F-2 |
| `v4_check_bypass` | a record with status `archived` written with `ignore_check_constraints`; v4 approves a claim resting on it | F-2, F-3 |
| `v4_nul_lengths` | record content of 10,052 and claim text of 2,502 characters, each hidden behind an embedded NUL from SQLite's `length()` | F-2, F-4 |
| `v4_nul_short` | a current claim whose text `Short<NUL>claim` holds an embedded NUL within every length bound (v4 accepts it) | D-C: migration refused |
| `v4_legacy_nul` | an ADR-0002 legacy record whose content holds an embedded NUL, migrated by v4 with `legacy = 1` | D-C: legacy data preserved |
| `v4_clean.export.json` | the v4 code's own export of `v4_clean` (`--export`) | migration export equivalence |
| `v5_backup_as_format_2.json` | a backup made by schema-5 code (this branch), rewritten as format 2 for v4 software (ADR-0006 reversal) | reversal input |
| `v4_restored_from_v5_backup` | the vault the v4 code itself made by trusted-restoring `v5_backup_as_format_2.json` (`--restore`) | reversal: v4 accepts it; back in v5 every claim is unconfirmed |

Load a fixture with `PRAGMA ignore_check_constraints=ON` (the damaged ones contain the CHECK violations the attacker left), then `executescript`.

SHA-256 at generation:

```text
8f36d7e9e76641defedb9ce3f3b7072ca47dac3d659a8c3f776b1f3648b693a1 v4_check_bypass.sql
67da98da20202549c462a5f1782603fe6bd41f414f8ffa773bd3fe5ac4582c5f v4_claim_row_replaced.sql
7a886dad832f96c64a9ef7cf94c30b04a6630b1b6ba61802fac29934df41ac17 v4_clean.export.json
0c468fce9d477c7a762fa324a128ba7617aca1226f844d06312b69ea391a3dc6 v4_clean.sql
84836ca0e0e3c29e12a102d07ae0daa133420c68870f35169cd01a0b4541262b v4_legacy_nul.sql
c0ea7e07edaa45edabcbe2dcd71b414882e5cae47499575c51dd266882e4702a v4_nul_lengths.sql
c706899a9d90fe061d7ec82e433df19fb063fc23bf05041b4ad66a10dc89e874 v4_nul_short.sql
4e1ff318363b343595163815de44ac1118e34cd66c1f341e3da32887495b1a21 v4_partial_link_loss.sql
a9d429461ccecb3ecc795a939e42ef0f7883937bd768814c1b7396d31f972141 v4_restored_from_v5_backup.sql
9e33b60621bce59f4ab80fad3cf2695e3283743290a6ed4ada85aa24637ccd6f v4_zero_link_loss.sql
2e053e07551ba35c31dba171fdb6b9d5af2426bf49a825e12161c08f31a5a57d v5_backup_as_format_2.json
```
