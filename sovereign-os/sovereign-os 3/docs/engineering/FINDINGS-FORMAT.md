# Independent audit findings: format and ownership

**Status:** Builder 0 rule (2026-10-22). Structure adapted from the phases and record states of Cloudflare's `security-audit-skill` (MIT; `docs/research/INTEGRATION-RESEARCH-CATALOG.md` #27), not copied. Schema: `findings.schema.json`; example: `findings-example.json`.

## Ownership

- A findings file is **authored by the reviewer** in a session independent of the builder and committed under the reviewer's attribution (or posted as a PR review). Its path is `docs/reviews/<date>-<pr-or-topic>-findings.json`.
- The builder **never edits** `evidence`, `reproduction`, `severity`, `confidence` or `status` of a finding. The builder appends only `builder_response` entries. The reviewer (or another independent reviewer) sets `independent_disposition`.
- Original reviewer evidence stays separate from remediation results; a remediation commit references the finding ID.
- Findings relayed verbally by the founder are recorded by the founder or the reviewer, never paraphrased into the file by the builder.

## Record fields

| Field | Meaning |
| --- | --- |
| `id` | `F-<n>` within the file |
| `severity` | `P0` blocks everything, `P1` blocks merge, `P2` must be fixed or explicitly deferred, `P3` advisory |
| `title`, `summary` | one line, one paragraph |
| `evidence` | file paths, line numbers, commands, outputs; a claim without a source trace is `needs_validation`, not `confirmed` |
| `reproduction` | exact steps and the observed result; `null` if not reproduced |
| `confidence` | `confirmed` (reproduced with a complete source trace and bounded observed result), `needs_validation` (an exact unresolved fact, no severity attached), `rejected` (disproved, with the disproof) |
| `status` | `open`, `fixed`, `wontfix`, `deferred` |
| `builder_response[]` | dated entries: `reproduced` / `fixed` / `rejected_with_evidence` / `deferred_with_reason`, with commit references |
| `independent_disposition` | reviewer's closing word on each response: `accepted`, `not_accepted`, `pending` |

## Minimum phases for a Tier 2 audit

1. **Reconnaissance:** architecture, trust boundaries and input surfaces touched by the diff (`ARCHITECTURE.md` §14 is the map).
2. **Hunting:** the whole surrounding implementation, not only the diff.
3. **Validation:** try to disprove each candidate; execute target code only in a disposable environment with synthetic data.
4. **Record:** write the file in the shape of `findings.schema.json`. The repository has no JSON Schema validator dependency; `tests/test_policy_invariants.py` checks the example's required fields and enums, and a reviewer may validate with any external validator.
5. **Report:** severity requires impact; only established boundary failures are `confirmed`.
