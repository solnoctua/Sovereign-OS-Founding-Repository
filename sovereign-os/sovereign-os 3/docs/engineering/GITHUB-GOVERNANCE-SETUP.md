# GitHub governance setup: separate agent identity and enforced review (founder decision D-F)

**Status:** prepared, **not applied**. The founder approved D-F in principle on 2026-10-22:
- separate the coding agents' GitHub identity and credentials from the founder's account;
- enforce human review and Code Owner requirements through effective GitHub rulesets.

Every step below changes accounts, permissions or repository settings, so the founder performs it. No agent has changed any of them. Writing these steps down enforces nothing. Only the verification commands below show what GitHub actually enforces.

## Current state (verified through the REST API on 2026-10-22)

**Identity.** Claude Code sessions act as the GitHub account connected at <https://claude.ai/connect-github>. Today that is `solnoctua`, the founder's own account (`GET /user`). It is also the author of every open PR and the only code owner.

**Ruleset `25374786`** ("Main branch protection") is active on the default branch and has no bypass actors.

| Rule | Current setting |
| --- | --- |
| Pull request before merging | Required |
| Review threads resolved | Required |
| Required checks `full-test-suite` and `memory-adversarial` | Required, with the branch up to date with `main` |
| Force-push and deletion | Blocked |
| Approving reviews | **None required** (count 0) |
| Code-owner review | **Not required** |
| Stale-approval dismissal, last-push approval | **Off** |

**Consequence.** Nothing in GitHub distinguishes an agent's merge from the founder's. "No autonomous merges" is an instruction, not a control.

## Order of operations

The order matters. GitHub never lets a PR's author approve that PR, so requiring an approval while agents still act as `solnoctua` would block every merge.

1. **Create the agent identity.** Create a GitHub account for coding agents only, for example `sovereign-builder`. Give it its own email address and two-factor authentication. Do not reuse the founder's credentials. A GitHub App is an alternative, but it needs a host that can use App tokens; Claude Code sessions use the account connected at claude.ai.
2. **Grant it Write and nothing more.** In the repository's *Settings → Collaborators*, invite `sovereign-builder` with the **Write** role. Never grant Maintain or Admin. Write lets it push branches and open PRs. Once step 5 is in place, it cannot merge to `main` without the founder's approval.
3. **Point agent sessions at it.** For the claude.ai account that runs coding sessions, connect `sovereign-builder` at <https://claude.ai/connect-github> instead of `solnoctua`, and keep the Claude GitHub App installed on this repository. The founder reviews and merges on github.com as `solnoctua`.
4. **Remove founder credentials from agent environments.** Agent environments must hold no personal access token, SSH key or `gh` login of `solnoctua`, and no environment secret derived from one. Revoke any such token that was ever given to an agent.
5. **Apply the ruleset**, as `solnoctua`, from a checkout of `main` after this PR merges:
   ```sh
   gh api -X PUT repos/solnoctua/Sovereign-OS-Founding-Repository/rulesets/25374786 \
     --input "sovereign-os/sovereign-os 3/docs/engineering/main-ruleset.proposed.json"
   ```
   The file changes only the pull-request rule:
   - one approving review;
   - code-owner review (`.github/CODEOWNERS` names `solnoctua`);
   - stale approvals dismissed on push;
   - the last push approved by someone other than its pusher.

   Deletion, force-push, thread resolution and the two strict required checks are carried over unchanged, and there are still no bypass actors. The required checks only mean something once D-E is in effect, which this PR does: both jobs run on draft PRs too.
6. **Re-open the existing PRs under the agent identity.** PRs already authored by `solnoctua` (#5 and #8–#13) cannot be approved by `solnoctua`.
   - **Recommended:** `sovereign-builder` opens a new PR from each existing branch, with the same commits and no rewrite, and the old PR is closed with a link to its replacement.
   - **Not recommended:** a temporary bypass for `solnoctua`, which is recorded but weakens the gate.
   - **Not recommended:** applying the ruleset only after those merges, which would leave them unenforced.

## Verification (run after each step)

| Check | Command | Expected |
| --- | --- | --- |
| Agent identity | In a new coding session: `gh api user --jq .login` | `sovereign-builder` |
| Agent permission | `gh api repos/solnoctua/Sovereign-OS-Founding-Repository/collaborators/sovereign-builder/permission --jq .permission` (as the founder) | `write` |
| Effective rules | `gh api repos/solnoctua/Sovereign-OS-Founding-Repository/rules/branches/main --jq '.[] \| {type, parameters}'` | `required_approving_review_count: 1`, `require_code_owner_review: true`, `dismiss_stale_reviews_on_push: true`, `require_last_push_approval: true`, both required checks, no bypass |
| CODEOWNERS parses | `gh api "repos/solnoctua/Sovereign-OS-Founding-Repository/codeowners/errors?ref=main"` | `{"errors":[]}` |
| Approval is enforced | `sovereign-builder` opens a trivial PR | Merge blocked until `solnoctua` approves; `sovereign-builder` cannot approve its own PR |
| Checks really ran | `gh api repos/solnoctua/Sovereign-OS-Founding-Repository/commits/<head sha>/check-runs --jq '.check_runs[] \| {name, conclusion}'` on a draft PR head | both `success` (or `failure`), never `skipped` |

## Optional, separate from D-F

Allowed merge methods could be restricted to `merge` (merge commits):
- a squash or rebase merge of #10 would rewrite the commits that the stacked #11 contains;
- merge commits keep every commit's attribution.

This is a separate choice. It is not in the proposed file.
