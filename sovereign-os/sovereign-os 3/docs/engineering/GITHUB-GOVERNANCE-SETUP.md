# GitHub governance setup: separate agent identity and enforced review (founder decision D-F)

**Status:** applied on 2026-10-27, except step 6 (in progress). The founder approved D-F in principle on 2026-10-22:
- separate the coding agents' GitHub identity and credentials from the founder's account;
- enforce human review and Code Owner requirements through effective GitHub rulesets.

Only the founder changes accounts, permissions and repository settings. No agent has changed any of them. Writing these steps down enforces nothing. Only the verification commands below show what GitHub actually enforces.

## Current state (verified through the REST API on 2026-10-27)

**Identities.**
- Coding agents act as `owlbuilder`, the account connected at <https://claude.ai/connect-github> (`GET /user` in a Claude Code session). It has Write access, without Maintain or Admin, and cannot bypass the ruleset.
- The founder reviews, approves and merges as `solnoctua`, the only code owner.

**Ruleset `25374786`** ("Main branch protection") is active on the default branch, has no bypass actors and was last updated on 2026-10-27. `main-ruleset.proposed.json` records the same rules.

| Rule | Current setting |
| --- | --- |
| Pull request before merging | Required |
| Approving reviews | **1** |
| Code Owner review | **Required**, from `.github/CODEOWNERS` on the target branch (see below) |
| Stale approvals | **Dismissed** on push |
| Last push | **Must be approved** by someone other than its pusher |
| Review threads resolved | Required |
| Required checks `full-test-suite` and `memory-adversarial` | Required, with the branch up to date with `main` |
| Merge methods | **Merge commits only** |
| Force-push and deletion | Blocked |

Merge commits keep every commit's attribution, and a squash or rebase of #10 would rewrite commits that the stacked #11 contains.

**What this enforces, and what it does not.**
- **Code Owner review needs CODEOWNERS on the target branch.** GitHub reads `.github/CODEOWNERS` from the PR's base branch. Until the file is on `main` (PR #18, which replaces #9), one approval from any account with write access satisfies the rule, and that is all that gates PR #18 itself. Once it is on `main`, every path needs `solnoctua`'s approval. The file's first rule is the catch-all `* @solnoctua`, and `tests/test_policy_invariants.py` fails if that rule is removed or moved, or if a later rule drops the founder.
- **Neither the author nor the last pusher can approve.** The founder should therefore not push to an agent's branch, including with GitHub's *Update branch* button: the founder would become the last pusher, and their approval would no longer count. Ask the agent to update the branch instead.
- **Who presses merge is not enforced.** Once the approval and the checks are in place, any account with write access can merge, `owlbuilder` included. Agents never merge. That is an instruction, not a control.
- **Draft checks are real only once D-E is on `main`.** Until PR #18 merges, other PRs' draft runs still report `skipped` (`docs/DEVELOPMENT.md`, D-E).

## Setup steps

Steps 1–5 are done. They stay here as the record of what was set up, in order.

1. **Create the agent identity. Done:** `owlbuilder`. The account is for coding agents only. It needs its own email address and two-factor authentication, and never the founder's credentials. A GitHub App was the alternative, but Claude Code sessions use the account connected at claude.ai.
2. **Grant it Write and nothing more. Done.** Never grant Maintain or Admin. Write lets it push branches and open PRs.
3. **Point agent sessions at it. Done:** Claude Code sessions connect `owlbuilder` at <https://claude.ai/connect-github> instead of `solnoctua`. The Claude GitHub App stays installed on this repository.
4. **Remove founder credentials from agent environments. Done for the 2026-10-27 session:** it held no personal access token, SSH key or `gh` login of `solnoctua`, and no secret derived from one. Any such token ever given to an agent must be revoked; only the founder can confirm that.
5. **Apply the ruleset. Done on 2026-10-27.** The plan applied it after this PR merged. It was applied before, so Code Owner review takes effect only when CODEOWNERS reaches `main` (see above). Re-applying the recorded rules is a founder action:
   ```sh
   gh api -X PUT repos/solnoctua/Sovereign-OS-Founding-Repository/rulesets/25374786 \
     --input "sovereign-os/sovereign-os 3/docs/engineering/main-ruleset.proposed.json"
   ```
6. **Re-open the founder-authored PRs under the agent identity. In progress.** `solnoctua` cannot approve PRs that `solnoctua` authored. `owlbuilder` opens a new PR from each existing branch, with the same commits and no rewrite. The old PR is closed with a link to its replacement once the founder authorizes it.
   - #9 is replaced by #18 (opened 2026-10-27). #9 stays open until the founder closes it.
   - Still authored by `solnoctua` on 2026-10-27: #7, #8, #10, #11, #12 and #13.
   - Rejected: a temporary bypass for `solnoctua`, which is recorded but weakens the gate; merging those PRs before the ruleset applied, which would have left them unenforced.

## Verification

| Check | Command | Expected |
| --- | --- | --- |
| Agent identity | In a new coding session: `gh api user --jq .login` | `owlbuilder` |
| Agent permission | `gh api repos/solnoctua/Sovereign-OS-Founding-Repository/collaborators/owlbuilder/permission --jq .permission` (as the founder) | `write` |
| Effective rules | `gh api repos/solnoctua/Sovereign-OS-Founding-Repository/rules/branches/main --jq '.[] \| {type, parameters}'` | `required_approving_review_count: 1`, `require_code_owner_review: true`, `dismiss_stale_reviews_on_push: true`, `require_last_push_approval: true`, `allowed_merge_methods: ["merge"]`, both required checks, no bypass |
| CODEOWNERS parses | `gh api "repos/solnoctua/Sovereign-OS-Founding-Repository/codeowners/errors?ref=main"` (before the merge, `ref=<PR branch>`) | `{"errors":[]}` |
| Approval is enforced | `owlbuilder` opens a PR that is ready for review, with green checks | `mergeable_state: blocked` until `solnoctua` approves; `owlbuilder` cannot approve its own PR |
| Checks really ran | `gh api repos/solnoctua/Sovereign-OS-Founding-Repository/commits/<head sha>/check-runs --jq '.check_runs[] \| {name, conclusion}'` on a draft PR head | both `success` (or `failure`), never `skipped` |

## Before D-F (verified through the REST API on 2026-10-22)

Claude Code sessions acted as `solnoctua`, the founder's own account, which was also the author of every open PR and the only code owner. Ruleset `25374786` required a pull request, resolved threads, both strict checks and blocked force-push and deletion. It required no approving review and no Code Owner review, left stale-approval dismissal and last-push approval off, and allowed all three merge methods. Nothing in GitHub distinguished an agent's merge from the founder's.
