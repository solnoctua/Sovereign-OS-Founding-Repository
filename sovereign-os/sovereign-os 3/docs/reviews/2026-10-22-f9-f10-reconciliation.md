# Codex audit F-9 and F-10 — builder reconciliation record, 2026-10-22

**Status:** builder-authored evidence. This is not an independent review, and no finding is closed by it. The builder did not have the audit's text; it worked from the founder's directive. F-9 asks for the registry, schema version, security limits and SB-2a status to be reconciled against the integrated code. F-10 asks for GitHub's effective rules to be verified and for enforced review requirements to be separated from missing ones. The Security Gate remains **NOT PASSED**, and no proposal is ratified here.

## F-9: documents that the integrated code contradicts

**Method.** In a scratch worktree, never pushed, `main` (`eeed753`) was merged with the six open PR heads:

| PR | Head |
| --- | --- |
| #11, which includes #10 at `ddec603` | `d43e579` |
| #8 | `9415447` |
| #9 | `b1d8d14` |
| #12 | `4a37f84` |
| #13 | `bc9a924` |

The merges had no conflicts, and the integrated tree passes the full suite: 713 passed, 2 xfailed. That is F-9's point: no test notices that these statements are false on that tree.

| Where (as introduced by PR #8 unless noted) | Statement | True on the integrated tree? |
| --- | --- | --- |
| `systems-registry.toml`, canonical-store | `schema user_version 4 (5 proposed in WP-2, unmerged)` | No: `store.SCHEMA_VERSION` is 5 |
| `systems-registry.toml`, canonical-store and memory-claim-governance | hidden-rowid bypass open; `support_of([])` returns `supported` | No: both are fixed by PR #10 |
| `systems-registry.toml`, sb2a-provenance-navigation | `approved`, `unmerged` | No: `src/sovereign/provenance.py` exists |
| `SECURITY-GATE.md` status update | Issue #6 repair and zero-source rule "not merged" | No |
| `SECURITY-GATE.md` (PR #10) | "Until that PR merges, this defect stands" | No, once PR #10 is the merged PR |
| `ROADMAP.md` order table | WP-2 and SB-2a "Draft PR"; SB-2a depends on nothing technically | No: SB-2a is stacked on WP-2 |
| `ARCHITECTURE.md` §14 K1 row | "integrity repair in progress (Issue #6)" | No |
| `BUILD-AND-INTEGRATION-PLAN.md` §1 GAP | Issue #6 and zero-source open | No |
| `FOUNDER-DECISIONS.md` | WP-2 "(unmerged)"; schema 5 approach "Proposed" | Depends on the founder's decision at merge |
| `SECOND-BRAIN-VALIDATION.md` item 35 | ADR-0006 "PROPOSED, unmerged" | Depends on the founder's decision at merge |

The stated limits match the code on both `main` and the integrated tree:

- `MAX_BACKUP_BYTES` 128 MiB;
- records of at most 10,000 characters;
- claim text of at most 2,000 characters, at most 8 sources, notes of at most 500 characters;
- the compiler budget of 12 items, 12,000 characters and 50 candidates;
- `policy_version` `sovereign.context.v0`.

One qualification belongs to PR #10's F-4: SQLite's `length()` undercounts text containing an embedded NUL, so storage can hold a value longer than the documented limit. ADR-0006 decision D-C covers it.

## F-9 change in this PR

`docs/architecture/systems-registry.toml` gains `[code_facts]`, and its entries gain an optional `code` list. `tests/test_systems_registry.py` checks each fact against the code in the same tree:

- `schema_user_version` equals `store.SCHEMA_VERSION`;
- every value in `[code_facts.limits]` equals the named constant;
- `known_gaps` equals exactly the set of gaps that probes find in the code:
  - `issue-6-hidden-rowid`: a canonical table that still has a hidden rowid;
  - `zero-source-authority`: `support_of([])` returns `supported`;
- an entry whose code exists is `implemented`, and an `implemented` entry's code exists.

`pull_request` CI checks out the merge commit, and the ruleset requires branches to be up to date. So whichever of PRs #8, #10 and #11 merges later fails CI until it reconciles the registry.

**Demonstration on the scratch integration:**

- With this PR's registry, 3 tests fail:
  - `assert 4 == 5`;
  - `registry lists ['issue-6-hidden-rowid', 'zero-source-authority']; the code has []`;
  - `sb2a-provenance-navigation has code in this tree but is marked approved`.
- With the reconciled registry below, all 11 pass. The reconciliation is `schema_user_version = 5`, `known_gaps = []`, the six SB-2a constants added to the limits, and SB-2a `implemented`.

Prose cannot be checked this way. The rule is that the PR that changes a fact updates the statements above in the same PR. The SECURITY-GATE status update now says it describes `main` at `eeed753`.

**What PR #10 must update when it is brought up to date with `main` after this PR merges:**

- registry `schema_user_version` and `known_gaps`, and the two `boundary` texts;
- SECURITY-GATE status-update bullets and its own "until that PR merges" sentence;
- ARCHITECTURE §14 K1 row;
- BUILD plan GAP line;
- ROADMAP WP-2 status;
- FOUNDER-DECISIONS rows, recording the founder's decisions D-A, D-B and D-C;
- SECOND-BRAIN-VALIDATION item 35;
- ADR-0006 status, set only by the founder's decision.

**What PR #11 must update:** the registry's SB-2a entry and its six limits, and the ROADMAP and BUILD plan SB-2a status.

## F-10: effective GitHub rules on `main` (REST API, 2026-10-22)

Ruleset `25374786` "Main branch protection" is active and targets the default branch. It has no bypass actors (`current_user_can_bypass: never`) and was last updated on 2026-10-19. There is no legacy branch protection.

| Requirement | Enforced? |
| --- | --- |
| Pull request before merging | **Yes** |
| Review threads resolved | **Yes** |
| Required checks `full-test-suite`, `memory-adversarial` (GitHub Actions, app 15368), branch up to date | **Yes**, with the draft gap below |
| No force-push (`non_fast_forward`), no deletion | **Yes** |
| Auto-merge | Disabled at repository level |
| Approving reviews | **No** (`required_approving_review_count: 0`) |
| Code-owner review | **No** (`require_code_owner_review: false`). CODEOWNERS parses without errors on the WP-1 branch but has no effect |
| Dismiss stale approvals; approval of the last push | **No** |
| Merge methods | merge, squash and rebase all allowed |

**Structural constraint.** Every PR is opened by `solnoctua`, who is also the only code owner and the identity of the agent token. GitHub does not let an author approve their own PR. So requiring one approval or a code-owner review today would block every merge, unless a second reviewer identity exists or a bypass is configured.

**Draft-check gap (verified).** Both CI jobs carry `if: … draft == false`. On the draft heads `ddec603`, `d43e579` and `f0b6539`, the required check runs from the Actions app report `conclusion: skipped`, and GitHub counts a skipped required check as passing. A draft cannot be merged. But until the `ready_for_review` run registers, a PR marked ready shows green required checks for runs that never executed, and so does any non-draft PR whose jobs are skipped for any reason.

The options and recommended defaults are in `docs/DEVELOPMENT.md` (PR #9). This record changes no setting.
