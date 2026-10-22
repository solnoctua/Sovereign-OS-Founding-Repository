# Sovereign — Development workflow (Builder 0)

**Status:** founder development strategy (Builder 0, adopted by the 2026-10-22 directive), not Constitution and not a permanent product-architecture requirement. Model roles are earned by observed performance and may change. This is the **only** place the loop, the review tiers and the pull-request contract are defined; `AGENTS.md` and `CLAUDE.md` point here and do not restate them.

## Objective

Use complementary AI systems and a disciplined loop to raise engineering quality, architectural integrity, speed and cost efficiency while preserving founder authority, independent verification and a clean Git history. Builder 0 is practice, not software: Claude Code and GPT/Codex remain external agents. Builder 1 (a Git-first development-context compiler) and Builder 2 (controlled execution) are specified in `engineering/BUILD-AND-INTEGRATION-PLAN.md` §5.6 and are not part of this document.

## The loop

```text
ORIENT → MINIMIZE → SPECIFY → BUILD → VERIFY → INDEPENDENT AUDIT → CHALLENGE / REPRODUCE → COMPOUND → FOUNDER APPROVAL → MERGE
```

Not every change needs every stage as a separate session; the amount of review is proportional to consequence and reversibility (tiers below).

1. **Orient.** Establish ground truth before designing: current `HEAD` and working tree; open PRs and issues; `AGENTS.md`; the ADRs and `ARCHITECTURE.md` §14 boundaries the change touches; `ROADMAP.md` §H position; the affected source files and their existing tests; `docs/SECURITY-GATE.md` limitations. Report material conflicts with the task before editing. Never create an abstraction before establishing what exists.
2. **Minimize.** Find the smallest implementation that fully satisfies the requirement (`engineering/MINIMIZE.md`). Minimal never means fewer validations, security checks or essential tests.
3. **Specify.** Write the contract before code: goal; scope and out of scope; invariants that must hold; risks; files affected; acceptance tests; failure cases; review tier; rollback. For a small task the issue or prompt suffices. Create an ADR only for durable architecture decisions, with its status marked honestly (PROPOSED until approved).
4. **Build.** One primary builder per change, given the same canonical repository state a human engineer would receive. It may inspect, implement, test and document within scope. Do not encode any model as the permanent builder.
5. **Verify.** Mechanical evidence, never a model asserting success:

   ```bash
   pytest -q
   pytest -q tests/adversarial
   python -m compileall -q src tests evaluation
   git diff --check
   ```

   Add targeted failure and adversarial tests for security-sensitive behaviour. Record exactly what was run and what was not.
6. **Independent audit** (Tier 2 and above). A reviewer operating independently of the builder (different session, and for Tier 2/3 a different model where available) receives the requirement, final diff, test evidence and governing documents, and writes a findings artifact in the reviewer-owned format (`engineering/FINDINGS-FORMAT.md`). The builder never writes or edits that artifact. If no independent reviewer is available, the PR stays **awaiting independent audit**; passing tests written by the same builder are not independent proof.
7. **Challenge / reproduce.** Every `confirmed` finding is reproduced (by the builder or the reviewer) before it is fixed; every rejected finding is rejected with evidence, recorded in the builder-response section, never by rewriting the finding. Hallucinated vulnerabilities and superficial approvals are both failures.
8. **Compound.** Retain a conclusion only when it is verified, generalizable, likely to matter again, not already documented and consistent with accepted architecture. Durable homes, in order: an ADR (decision), `AGENTS.md` Code Review Rules (a reviewable invariant), a test (a mechanical check), the development vault once Builder 1 exists (working knowledge referencing Git). Never session transcripts, never a growing pile of notes.
9. **Founder approval.** The founder approves consequential architecture, scope, security, provider, schema and governance changes. Routine changes can merge after their required checks and review.
10. **Merge.** Short-lived branches, comprehensible commits, no force-push to `main`, no autonomous merges.

Resolve disagreement by, in order: Constitution candidate and accepted ADRs; observable requirements and tests; security and reliability evidence; the simpler reversible design; explicit founder judgment. Model confidence or prestige is not evidence.

## Review tiers

| Tier | Examples | Process |
| --- | --- | --- |
| **0 mechanical** | typo, narrow styling change, fixture cleanup, behaviour-preserving refactor | one builder + tests |
| **1 normal product change** | bounded endpoint, UI behaviour, internal refactor with meaningful behaviour, documentation of process | one builder + tests; lightweight second-model review when uncertainty is nontrivial |
| **2 consequential** | personal-state schema or migration, memory-authority logic, provider or disclosure behaviour, permissions, deletion or recovery, new major dependency, agent or tool execution, authentication, anything under `.github/CODEOWNERS` | written spec + primary builder + **independent reviewer artifact** + adversarial tests + founder approval |
| **3 foundational** | Constitution amendment, major architecture rewrite, trust model, system-wide memory model, migration strategy, self-modification, high-impact security design | independent architecture reasoning by at least two strong models, explicit disagreement analysis, evidence or research as needed, frontier-model escalation when useful, founder decision before implementation or merge |

## Pull request contract (the quality bar for every PR)

Every PR body, using `.github/pull_request_template.md`, states: (1) the exact goal; (2) the current baseline (`HEAD`) and affected invariants; (3) impacted files; (4) why the implementation is minimal; (5) acceptance tests; (6) how existing behaviour was verified intact; (7) security or policy impact; (8) the tests actually executed, with results; (9) what was not tested; (10) rollback strategy; (11) reviewer findings separated from builder responses; (12) founder decisions still required. A PR touching a `.github/CODEOWNERS` path without a reviewer-owned findings artifact is not mergeable.

## Containment of coding agents (what actually holds)

A coding agent with shell and repository write access can edit `store.py`, `context.py` or the triggers; no Python check contains it. What does:

- **GitHub settings the founder must apply** (a file cannot set them; this document reports them as **not yet configured** as of 2026-10-22): branch protection on `main` requiring a pull request, required status checks (`full-test-suite`, `memory-adversarial`), review from `.github/CODEOWNERS` for protected paths, no force-pushes, no deletions, no bypass for administrators used as routine, and no auto-merge.
- **Reviewer-owned findings artifacts** the builder cannot rewrite (format below).
- **Policy tests** (`tests/test_policy_invariants.py`): personal content leaves the process only through `providers.generate`; `app.py` calls it at exactly one site; the schema version in code is documented in an ADR; the trigger set changes only with an ADR reference.
- **Dependency pinning** (ranges in `pyproject.toml` today; hash-pinned lock when the first real-data instance exists), **signed tags** for anything run on real data, and **rollback** by previous tag plus a canonical export.

Agents never receive the personal vault path; development knowledge lives in Git and, once Builder 1 exists, in a separate development vault file.

## Builder 0 benchmark plan (minimal)

The first Builder experiment is the Issue #6 repair (WP-2): two sessions from the same commit and the same specification, one with `engineering/MINIMIZE.md` in context and one without, each audited independently, exactly one merged. Record per session, in the PR: wall-clock to green CI; tokens or API cost; lines changed versus lines the reviewer judged necessary; adversarial regressions added; reviewer findings confirmed versus rejected; founder review minutes. A second arm may add two or three `mattpocock/skills` skills (tdd, code-review, to-spec) once licensed text is reviewed. Decide adoption on these numbers, never on reputation; re-run when a coding system materially changes.

## Frontier API escalation

Use paid API inference when expected decision value exceeds cost: Tier 3 work or a genuinely hard Tier 2 problem; two capable models disagreeing on a material issue; repeated implementation or debug failure; security or migration design where another independent view materially reduces risk; a benchmark needing a stronger reference solution or audit. Do not spend frontier tokens on routine code, documentation polish or questions answered by tests or source. Treat the current API budget as a reserve, not a quota; record material spend in the task notes so quality per dollar can be compared.

## Canonical context and handoff

Git is the source of truth. Shared context is normally: the current commit and branch; `AGENTS.md`; the task specification; the applicable Constitution, Architecture, ADR and Security Gate files; the diff and test output. Do not maintain giant model-specific memory files or paste previous AI conversations into the repository. A useful handoff has five fields:

```text
Task:
Starting commit:
Changed files / diff:
Tests and results:
Risks / unresolved questions:
```

If a material decision emerges during implementation, record it in an ADR or the task specification rather than in a chat.

## Builder assignment

Choose the default builder from benchmark results (Benchmark 0001 and the Builder 0 plan above), not reputation; re-benchmark when either coding system materially changes or performance drifts. A default builder is a convenience, not an authority hierarchy.
