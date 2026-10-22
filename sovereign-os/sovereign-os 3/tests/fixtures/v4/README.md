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

Load a fixture with `PRAGMA ignore_check_constraints=ON` (the damaged ones contain the CHECK violations the attacker left), then `executescript`.

SHA-256 at generation:

```text
8f36d7e9e76641defedb9ce3f3b7072ca47dac3d659a8c3f776b1f3648b693a1 v4_check_bypass.sql
67da98da20202549c462a5f1782603fe6bd41f414f8ffa773bd3fe5ac4582c5f v4_claim_row_replaced.sql
0c468fce9d477c7a762fa324a128ba7617aca1226f844d06312b69ea391a3dc6 v4_clean.sql
c0ea7e07edaa45edabcbe2dcd71b414882e5cae47499575c51dd266882e4702a v4_nul_lengths.sql
4e1ff318363b343595163815de44ac1118e34cd66c1f341e3da32887495b1a21 v4_partial_link_loss.sql
9e33b60621bce59f4ab80fad3cf2695e3283743290a6ed4ada85aa24637ccd6f v4_zero_link_loss.sql
```
