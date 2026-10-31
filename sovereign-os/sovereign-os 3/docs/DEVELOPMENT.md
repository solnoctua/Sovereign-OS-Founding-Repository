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
| **2 consequential** | personal-state schema or migration, memory-authority logic, provider or disclosure behaviour, permissions, deletion or recovery, new major dependency, agent or tool execution, authentication, any path listed explicitly in `.github/CODEOWNERS` (the catch-all `*` alone does not make a change Tier 2) | written spec + primary builder + **independent reviewer artifact** + adversarial tests + founder approval |
| **3 foundational** | Constitution amendment, major architecture rewrite, trust model, system-wide memory model, migration strategy, self-modification, high-impact security design | independent architecture reasoning by at least two strong models, explicit disagreement analysis, evidence or research as needed, frontier-model escalation when useful, founder decision before implementation or merge |

## Pull request contract (the quality bar for every PR)

Every PR body, using `.github/pull_request_template.md`, states: (1) the exact goal; (2) the current baseline (`HEAD`) and affected invariants; (3) impacted files; (4) why the implementation is minimal; (5) acceptance tests; (6) how existing behaviour was verified intact; (7) security or policy impact; (8) the tests actually executed, with results; (9) what was not tested; (10) rollback strategy; (11) reviewer findings separated from builder responses; (12) founder decisions still required. A PR touching a path listed explicitly in `.github/CODEOWNERS` without a reviewer-owned findings artifact must not be merged. This is a process rule: GitHub enforces the founder's approval (see below), not the artifact.

## Containment of coding agents (what actually holds)

A coding agent with shell and repository write access can edit `store.py`, `context.py` or the triggers; no Python check contains it. What does:

- **The GitHub ruleset on `main`.** Ruleset `25374786` "Main branch protection" is active on the default branch. It has no bypass actors and was last updated on 2026-10-27 (decision D-F). There is no legacy branch protection. This was verified through the REST API on 2026-10-27. The state before D-F, verified on 2026-10-22 (Codex audit F-10), is recorded in `docs/engineering/GITHUB-GOVERNANCE-SETUP.md`.
  - **Enforced:**
    - a pull request before merging, with one approving review;
    - review from `.github/CODEOWNERS`, once the file is on `main` (GitHub reads it from the target branch);
    - dismissal of stale approvals, and approval of the last push by someone other than its pusher;
    - all review threads resolved;
    - required checks `full-test-suite` and `memory-adversarial` from GitHub Actions, with the branch up to date with `main`;
    - merge commits only, no force-push and no deletion.

    Auto-merge is disabled for the repository.
  - **Not enforced:** who presses merge. Once the approval and the checks are in place, any account with write access can merge, including the agent identity. Agents are instructed never to merge (no autonomous merges); that is an instruction, not a control.
  - **Who approves.** Coding agents act as `owlbuilder`, with Write and no bypass, and open the PRs. The founder approves and merges as `solnoctua`, the only code owner, after a reviewer-owned findings artifact where one is required and a fresh independent review of the exact head. GitHub does not let an author approve their own PR, so PRs that `solnoctua` opened are re-opened by `owlbuilder`.
  - **Skipped checks count as passing.** Both CI jobs are skipped while a PR is a draft (`if: … draft == false`), and GitHub counts a skipped required check as passing. On draft heads the required check runs report `conclusion: skipped` (verified on `ddec603`, `d43e579` and `f0b6539`). A draft cannot be merged. But a PR just marked ready shows green required checks until the `ready_for_review` run registers, and so does any PR whose jobs are skipped for another reason.
- **Reviewer-owned findings artifacts** the builder cannot rewrite (format below).
- **Policy tests** (`tests/test_policy_invariants.py`): personal content leaves the process only through `providers.generate`; `app.py` calls it at exactly one site; the schema version in code is documented in an ADR; the trigger set changes only with an ADR reference; `.github/CODEOWNERS` keeps the founder catch-all `* @solnoctua` first, and every rule names the founder.
- **Dependency pinning** (ranges in `pyproject.toml` today; hash-pinned lock when the first real-data instance exists), **signed tags** for anything run on real data, and **rollback** by previous tag plus a canonical export. A schema-5 export (format 3) cannot be restored by schema-4 software as it is. It must first be rewritten as format 2, and its claims are then unconfirmed until revalidated when moved forward again ([ADR-0006 § Compatibility and reversal](adr/0006-rowid-free-canonical-tables.md#compatibility-and-reversal)).

Agents never receive the personal vault path; development knowledge lives in Git and, once Builder 1 exists, in a separate development vault file.

### Founder decisions (2026-10-22, F-10)

- **D-E: approved (E1).** Required CI jobs must execute on draft PRs and on exact reviewed commits; a skipped job is not evidence that tests ran.
  - **Implemented in this PR:** both jobs in `.github/workflows/sovereign-ci.yml` lost their `if:` condition.
  - **When it takes effect:** a `pull_request` run uses the workflow file of the PR's merge commit. Until this PR is on `main`, other PRs' draft heads still report `skipped`; a `workflow_dispatch` run on a branch executes both jobs on its exact head.
  - **What the checks test:** `pull_request` CI tests the merge commit. Because the ruleset requires branches to be up to date with `main`, at merge time that merge commit has the same tree as the reviewed head.
- **D-F: approved in principle; applied on 2026-10-27.** Separate the coding agents' GitHub identity and credentials from the founder's account, and enforce human and Code Owner review through effective rulesets.
  - **Applied:** coding agents act as `owlbuilder` with Write. Ruleset `25374786` requires one approval, Code Owner review, stale-approval dismissal and last-push approval, and allows merge commits only. `docs/engineering/GITHUB-GOVERNANCE-SETUP.md` has the current state, the completed steps, the verification commands and the remaining step: re-opening the founder-authored PRs under `owlbuilder`. `docs/engineering/main-ruleset.proposed.json` records the applied rules.
  - **Who acts:** only the founder changes accounts, permissions and settings. No agent has changed any of them.

The options as presented before the decisions:

**D-E. Required checks that never ran.**

| Option | Change | Effect | Cost |
| --- | --- | --- | --- |
| **E1 (recommended)** Run both required jobs on every PR event, drafts included | Delete the two `if: … draft == false` lines in `.github/workflows/sovereign-ci.yml` | A required check on any head is a real run of that head; no ruleset change | CI on every draft push. Actions minutes are free for public repositories |
| E2 Gate job | Add a job `ci-gate` that always runs, `needs` both jobs, and fails unless both succeeded. Make `ci-gate` the only required check in the ruleset | Skipped jobs make the gate fail; drafts show a failing gate | A workflow change plus a ruleset change |
| E3 Process only | Before merging, the founder confirms a completed, non-skipped run of both checks on the exact head SHA | Unchanged settings | Relies on attention |

**D-F. An enforced founder approval.**

| Option | Change | Effect | Cost |
| --- | --- | --- | --- |
| **F1 (recommended)** Separate agent identity, then required code-owner approval | Coding agents open PRs from a dedicated machine account or GitHub App without merge rights. Then set `required_approving_review_count: 1` and `require_code_owner_review: true`, keeping `solnoctua` as code owner, and turn on stale-approval dismissal and last-push approval | The founder's approval becomes a GitHub-enforced act, and an agent can neither approve nor merge | Creating and scoping the identity; the founder approves each PR in GitHub |
| F2 Keep today's settings and document them | None | The founder's merge is the approval act, as described above; an agent with the founder's token remains technically able to merge | No setup |
| F3 Require approval, with the founder as bypass actor | Approvals required; `solnoctua` bypasses | Every merge is a recorded bypass; an agent with the founder's token can bypass too | Gives no separation while agents use the founder's identity |

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
