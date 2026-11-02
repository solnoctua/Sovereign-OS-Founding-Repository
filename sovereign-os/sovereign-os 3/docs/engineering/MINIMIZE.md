# Minimize: the smallest implementation that fully satisfies the requirement

**Status:** Builder 0 guidance (2026-10-22). Written in Sovereign's own words. The ladder idea is adapted from the Ponytail project (https://github.com/DietrichGebert/ponytail, MIT license, Dietrich Gebert and contributors), whose text is **not** copied here; its plugin, hooks and UI are not installed (`docs/research/INTEGRATION-RESEARCH-CATALOG.md` #17).

**Rule:** write only what the task needs, and never cut validation, error handling, security checks, essential tests, migration safety, readable structure or the documentation a change actually requires. Code is small because it is necessary, not because it was golfed. Lazy about the solution, never about reading.

## The ladder (climb before writing a line)

1. **Is it needed?** State the requirement and the acceptance test. If no test would fail without the change, stop.
2. **Does the codebase already do it?** Read the relevant modules and trace the flow (`store.py`, `claims.py`, `context.py`, `app.py` are small; read them whole). Reuse the existing seam (`Vault.context_candidates`, `build_bundle`, the trigger pattern) before inventing one.
3. **Does the standard library do it?** Python 3.11+ ships `sqlite3`, `tomllib`, `hashlib`, `json`, `dataclasses`, `uuid`; prefer them.
4. **Does the platform do it?** macOS and Linux provide file ACLs, FileVault, Keychain and process isolation; do not re-implement them in Python.
5. **Does an installed dependency do it?** FastAPI, Starlette, httpx and the OpenAI SDK are already present; a second HTTP client or framework is not minimal.
6. **Only then write the minimum that works**, with one small test for every branch, loop, parser, migration or security concern.

## Non-negotiables (never on the chopping block)

Trust-boundary validation (request models with `extra="forbid"`, server-side policy checks); storage invariants (triggers, CHECKs, one transaction per operation); disclosure checks (the exact-plan token recomputed at execution); Forget semantics; migration atomicity and rollback; adversarial regression tests; honest documentation of limits.

## Review questions a minimizer asks of a diff

- Does every changed line trace to the requirement?
- Was anything deleted that a test or the Security Gate relies on?
- Is there a new abstraction with only one caller? Remove it.
- Is there speculative extensibility ("for a future provider")? Remove it until the second instance exists.
- Could the change be two smaller PRs with separate reviewers? Then it should be.
