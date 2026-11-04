# PR #24 third independent review: builder response record (round 3), 2026-11-04

**Status:** builder-authored evidence, by `owlbuilder`.

- **What this is not.** It is not an independent review, not a findings artifact, and not the review itself.
- **The review.** The third independent Codex review of the specification, at `5304b5b37371c926e69415b8094a505f83c97cde`, returned CHANGES REQUIRED: six P2 findings, F-10 to F-15, and no new P0 or P1. It accepted F-5 and retained the earlier accepted corrections. The founder relayed it in a directive of 2026-11-04.
- **The reviewer-owned artifacts are not in this repository, and the builder has not seen them.** On 2026-11-04, PR #24 had no review and no reviewer comment for round 3, Issue #22 had none either, and no reviewer branch existed on the remote. Each finding below is the founder's relay of it, not the reviewer's text.
- **No finding is closed by this record.** Every response below is pending an independent disposition.
- **Earlier records:** [round 1](2026-11-03-pr24-builder-response.md) and [round 2](2026-11-03-pr24-round2-builder-response.md). They stay as they were.

**Where the evidence lives:**

- `tests/test_builder1_spec.py` and `tests/test_benchmark_freeze.py`, which run in CI;
- the commands below, which anyone can repeat on a checkout of this branch;
- a throwaway reference model of the selection rules, kept outside the repository. It generated the example package and the determinism table below. It is not the implementation, and AT-1 to AT-23 do not rest on it.

| Finding | Reproduced against `5304b5b` | Correction | Main regression tests |
| --- | --- | --- | --- |
| **F-10** | The same canonical package: 49,152 bytes of final JSON from a bare clone, 49,158 from a work tree. At a 49,152-byte bound only the work tree pruned a window | SPEC §6.2: canonical pruning against `max_output_bytes − observation_bytes`, then the fingerprint, then the observations, whose envelope is bounded by construction (§7.2) | `test_finalization_is_identical_across_clones_and_fits_the_bound` |
| **F-11** | SPEC §16: "implementation waits for the founder's decisions and the benchmark freeze", while the freeze needs the implementation's commit | BENCHMARK-PLAN §5.1: phases L0 to L5. SPEC §15 D-10 and §16 | `test_the_lifecycle_never_makes_implementation_wait_for_the_freeze` |
| **F-12** | `manifest` given the published task plan: `KeyError: 'target'`, exit 1, a traceback | One input, the freeze plan, derived by `prepare`, with a schema, an example and a guide | `test_the_manifest_command_refuses_invalid_freeze_plans` and the workflow tests |
| **F-13** | `verify` printed "verified" for an empty repository, a checkout of the wrong commit, and a dirty checkout | The workspace checks cover presence as well as absence | one test per invalid start, through `verify` |
| **F-14** | A 16-byte bundle, `# v2 git bundle\n`, looped until `timeout 5` killed it (exit 124) | A bounded parser that refuses EOF before the terminator | `test_malformed_bundle_headers_are_refused`, in a timed child process |
| **F-15** | 17 targets: "17 items" against a maximum of 16. 10 reasons: "10 items" against 8 | SPEC §6.1: decisions on the full set, a bounded display with full counts | `test_seventeen_targets_…`, `test_nine_finding_links_…` |

## F-10 (P2): pruning depended on observations

**Relayed:** "the same canonical package produces 49,152 serialized JSON bytes with bare-repository observations [and] 49,158 serialized JSON bytes with work-tree observations. The 49,152-byte cap therefore causes different optional-window pruning, despite identical canonical inputs."

**Reproduced.**

- `test_the_reviewers_counterexample_pruned_differently_under_revision_3` builds the reviewer's case from the example package, padded to exactly 49,152 bytes in a bare clone. Under revision 3's rule, the bare clone keeps a window that the work tree prunes.
- The same comparison, run across boundary positions with the four observation sets of the test:

  | Rule | Padding 0 | 300 | 2,000 | 5,000 |
  | --- | --- | --- | --- | --- |
  | Revision 3: prune the final output, observations included | **2 distinct packages** (21 and 22 items) | 1 | 1 | 1 |
  | Revision 4: prune the canonical output against `max_output_bytes − observation_bytes` | 1 | 1 | 1 | 1 |

- In the checked-in revision 3 example, the observation member alone made the canonical JSON 48,320 bytes from a bare clone and 48,326 from a clean work tree.

**Correction** (SPEC §6.2 and §7.2):

1. Resolve the canonical inputs, generate candidates and obligations, and check that mandatory evidence fits.
2. Fill optional windows, then **prune canonically**: measure `{schema, fingerprint, package}` with a fixed-length placeholder fingerprint, and the rendering without its observation block. Prune against `max_output_bytes − observation_bytes`, last accepted window first.
3. Fingerprint the package.
4. Add the observations, serialize, and render.
5. Check both final outputs against `max_output_bytes`. A failure there is a defect (exit 1); canonical content is never pruned for it.

**The envelope is bounded by construction.**

- `git_version` is cut to 64 printable ASCII characters, excluding `"`, `\` and the backtick. JSON escaping and a longer Markdown fence therefore cannot grow it.
- `replace_refs_ignored` is capped at 999,999.
- The worst case is 226 bytes of JSON and 201 bytes of Markdown, within the fixed `observation_bytes` of 512.
- No observation names a path, an ordinary ref or an unrelated object.
- Lengths are never self-referential: the fingerprint covers `package` only, its length is fixed, and measured sizes are not written into the output.

**Regression tests:**

- `test_finalization_is_identical_across_clones_and_fits_the_bound`: five observation sets (bare; clean; dirty with the longest Git version and Python 3.11; another Git with Python 3.12; another checkout path with unrelated refs and objects) at four boundary positions. It asserts identical package bytes, selections and fingerprints, and every final JSON within the bound.
- `test_the_observation_envelope_is_bounded_by_construction`: the worst-case member and block; hostile `git_version` values refused by the schema; `observation_bytes` fixed at 512.
- `test_example_parameters_are_the_specification_defaults`: the example's parameters equal the SPEC §6 table.
- `test_example_respects_the_output_bound_and_the_per_field_limits`: the canonical JSON and rendering within `max_output_bytes − observation_bytes`, the final ones within `max_output_bytes`.

**With real clones** (the reference model, 99f3026, the example's task). The clones were:

- a bare clone;
- a clean work tree at a Unicode path with spaces;
- a dirty work tree, repacked, with an extra branch and tag, an unrelated dangling commit and a replace ref;
- the original checkout.

| Bound | Fingerprint | Items | Largest JSON | Largest Markdown |
| --- | --- | --- | --- | --- |
| 49,152 | `477c1046256f001a…` (the example) | 22 | 47,181 | 38,530 |
| 47,175 (the bare clone's final size), and ±6 | three values, one per bound, identical across clones | 22 | 44,658 | 36,131 |
| 47,687 | `44950502df1bc386…` | 21 | 46,660 | 38,013 |
| 40,000 | `98347be0e73651ed…` | 18 | 39,531 | 31,373 |
| 32,768 | `7d2c1274b99b4c46…` | 13 | 31,559 | 23,673 |

- At every bound, all four clones gave the same package bytes, fingerprint and selection, and both outputs were within the bound. Their observations differed in all four.
- The table is identical on Python 3.11.18, 3.12.3 and 3.13.18.
- Only Git 2.43.0 was available. Other Git versions are covered by the observation strings in the tests, not by running them.

**Disposition:** pending independent review.

## F-11 (P2): implementation and freeze ordering

**Relayed:** "the specification still says implementation waits for the benchmark freeze, while the freeze itself requires the implementation commit."

**Reproduced.** At `5304b5b`, SPEC §16 read: "implementation waits for the founder's decisions and the benchmark freeze". BENCHMARK-PLAN §5 step 2 froze the tool commit, which only an implementation has.

**Correction.** BENCHMARK-PLAN §5.1 sets six phases, and every document now follows them:

| Phase | When | Needs | Never needs |
| --- | --- | --- | --- |
| L0. Protocol approval | before implementation | — | a tool commit, any hash, any gold sheet |
| L1. Implementation | after L0 | L0 | benchmark inputs or results |
| L2. Tool freeze | after L1 merges | the merged implementation | — |
| L3. Run-input freeze and qualification | after L2 | the tool commit | — |
| L4. Runs | after L3 | the published manifest | — |
| L5. Scoring and publication | after L4 | the runs | — |

- **Kept apart:** protocol approval (L0), implementation correctness (L1: AT-1 to AT-23 and the independent audit), qualification (§7.1, in L3), and measured value (L5).
- **SPEC §15 D-10:** approve the protocol before implementation; its run inputs are frozen only after the implementation exists.
- **SPEC §16:** implementation never waits for the benchmark freeze or for results.
- **FREEZE-TOOL.md:** the freeze happens after Builder 1 exists.

**Regression test:** `test_the_lifecycle_never_makes_implementation_wait_for_the_freeze` checks the phase table, its order and its needs. It also checks that no specification document makes implementation wait for the freeze or for results. Run against the documents of `5304b5b`, it fails on the sentence quoted above.

**Disposition:** pending independent review.

## F-12 (P2): the CLI did not accept its published input

**Relayed:** the published `benchmark-tasks.json`, run through the manifest command, gave `KeyError: 'target'`.

**Reproduced** at `5304b5b`, with the documented command:

```text
python scripts/benchmark_freeze.py manifest --plan docs/engineering/builder-1/benchmark-tasks.json --inputs … --bundles … \
  --tool-commit 1111… --protocol-commit 2222… --out …
KeyError: 'target'          (a traceback, exit 1)
```

**Correction: one input contract.**

- **The task plan** (`benchmark-tasks.json`) stays public and holds no hashes. It now has a schema, `benchmark-tasks.schema.json`.
- **The freeze plan** is the only input of `manifest` and `bundle`. `prepare` derives it from the task plan: it binds each pinned task's input files and bundle, and reports each unpinned task on standard error. Its schema is `freeze-plan.schema.json`. `freeze-plan.example.json` is exactly `prepare`'s output from the checked-in task plan, and a test regenerates it.
- **Validation comes before any processing:** the schema version, the schema, uniqueness, pins absent from `must_be_absent`, and bindings that are regular files inside the inputs directory, with no symbolic link out.
- **Errors** name tasks, fields and the files the user supplied, never file contents. Exit codes: 0 success, 1 a check failed, 2 invalid input, 3 an operating failure.
- **The guide,** [`FREEZE-TOOL.md`](../engineering/builder-1/FREEZE-TOOL.md), gives every command.

**The ten mandatory cases**, each run through the command line:

| Case | Test | Result |
| --- | --- | --- |
| 1. Valid frozen task | the documented workflow; the real T1 at `eeed753` | exit 0 |
| 2. Prospective task without pins | `prepare` leaves it out and names it; a freeze plan holding one is refused | exit 0 and exit 2 |
| 3. Missing target | `missing target` | exit 2 |
| 4. Invalid binding | `../escape.md`, a missing file, a symbolic link out | exit 2 |
| 5. Missing bundle | `bundle file absent.bundle is missing` | exit 2 |
| 6. Malformed JSON | the plan and the manifest | exit 2 |
| 7. Empty task list | `$.tasks: 0 entries` | exit 2 |
| 8. Unsupported schema version | `freeze-plan.v0`, `benchmark-tasks.v2` | exit 2 |
| 9. Invalid agents | none, a duplicate, a malformed name | exit 2 |
| 10. Manifest produced and independently verified | `manifest`, then `verify` | exit 0 |

No expected invalid input prints a traceback: the test helper fails on one.

**Disposition:** pending independent review.

## F-13 (P2): the verifier accepted invalid starting states

**Relayed:** `verify` returned success for an empty repository, a checkout at the wrong commit, a dirty tree holding later outcome code, and a manifest with empty tasks and agents.

**Reproduced** at `5304b5b`, on a synthetic repository, through the CLI: `empty`, `wrong` and `dirty` each printed `verified: manifest 8a608a73…` and exited 0.

**Correction:** `verify --workspace` checks presence as well as absence (BENCHMARK-PLAN §4, step 3; FREEZE-TOOL.md).

- **What the repository is:**
  - a non-bare work tree at its own top level;
  - not shallow, with no alternates, grafts, promisor state, replace refs or remotes;
  - only the configuration a fresh clone writes (self-review defect 3).
- **Where it points:** HEAD is born, on `work`, at the target. The refs are exactly `work`, plus `candidate` at the candidate.
- **Its Git objects:** exactly the bundle's objects. None missing, none extra, reachable or not, and no later commit.
- **Its files:**
  - no staged change, and no tracked file that differs from the target;
  - no untracked or ignored file outside the arm's allow-list;
  - the bootstrap files present, byte-identical to the frozen inputs where those exist;
  - no file anywhere in the workspace, `.git` included, with the bytes of a private input.
- **A bare repository is never a valid workspace.** Bundles are cloned bare only inside the tool, for analysis.
- **The manifest is checked first:** its schema, at least one task and one agent, every input's hash and size, and every bundle.
- **Pre-run only.** The agent is expected to change files afterwards. Judging the result is for the independent reviewers.
- **A refused start writes no record.** Every rejection test asserts it.

**The fourteen mandatory cases**, each through the CLI, each refused with exit 1 unless stated:

| Case | Diagnostic (excerpt) |
| --- | --- |
| Empty `git init` | `HEAD is unborn`, `3 Git object(s) of the task's bundle are missing` |
| Unborn HEAD with the right objects | `HEAD is unborn; nothing is checked out` |
| Wrong checkout | `HEAD is not the task's target commit` |
| Missing pinned commit (another task's workspace) | `HEAD is not the task's target commit`, objects missing |
| Missing required object | `Git object(s) of the task's bundle are missing` |
| Dirty tracked file | `tracked file store.py differs from the target commit` |
| Staged change | `staged change to store.py` |
| Unapproved untracked source | `unapproved untracked file helper.py` |
| Outcome-bearing fixture | `private input hidden_tests is present at tests/test_hidden.py` |
| Empty manifest | exit 2: `$.tasks: 0 entries` |
| Invalid schema | exit 2 |
| Missing bootstrap context | `required bootstrap file .devcontext/handoff.md is missing` |
| Gold or hidden files | `private input gold_sheet is present at …` |
| Later objects, reachable or not | `Git object(s) not in the task's bundle`, `later commit … is present` |

A clean workspace built by `workspace` is accepted for each arm (A, B and N).

**Disposition:** pending independent review.

## F-14 (P2): an infinite loop on a truncated bundle header

**Relayed:** a truncated bundle loops forever, because EOF was not distinguished from the header's blank-line terminator.

**Reproduced** at `5304b5b`: the header parser read `iter(handle.readline, b"\n")`. On the 16-byte file `# v2 git bundle\n` it never returned, and `timeout 5` killed it (exit 124).

**Correction:** `bundle_heads` reads at most 1 MiB, 4,096 bytes per line and 10,000 lines, and refuses:

- EOF before the terminator;
- a line without its newline;
- an unknown signature or version;
- a line that is not UTF-8;
- a malformed reference or prerequisite;
- a capability line in v2, or after a reference;
- an object format other than SHA-1;
- a header with no references.

`manifest` refuses a malformed header with exit 2. `verify` reports it as a failed check, with exit 1. Every Git call has a 300-second limit, and an expiry is exit 3.

**Regression tests,** each running the parser in a child process with a 30-second limit, so that a regressed loop fails instead of hanging the test run:

- the 12 malformed headers: empty, the 16-byte signature, a missing terminator, an unsupported version, an over-long line, an oversized header, invalid encoding, a truncated reference, a malformed prerequisite, a v2 capability, an unsupported object format, no references;
- a valid bundle;
- the 16-byte file through `manifest` (exit 2) and through `verify` with its hash re-frozen (exit 1), each under a 30-second limit.

**Disposition:** pending independent review.

## F-15 (P2): schema and specification cardinality

**Relayed:** an anchor matching 17 definitions, where the schema allowed 16 targets; a window with nine finding links, where the schema allowed eight reasons.

**Reproduced** against the schema of `5304b5b`: the 17-target anchor gives `targets: 17 items`, and the item with ten links gives `reasons: 10 items`. Revision 3's specification asked for every target and every reason to be listed.

**Correction:** one rule (SPEC §6.1).

- **Every decision is made on the full logical set:** resolution, ambiguity, obligations and ranking.
- **Only then is the display bounded,** and it always carries the full count:
  - `target_count`, with at most 8 `targets`;
  - `reasons_total`, with at most 8 `reasons`;
  - `sides_total`, with at most 16 `sides`;
  - symbols and outline names cut to 256 bytes on a character boundary, with `symbol_truncated` and `names_truncated`;
  - an `overflow` object for findings, conflicts, missing entries and tests.
- **Where nothing may be dropped, the run refuses:** more than 32 anchors (exit 2), more than 20 mandatory findings (exit 4), or more than 100 candidate paths (exit 4).
- **A truncated display cannot make an anchor look unique or an obligation look complete.** Obligations exist only for 1 to 4 targets, all of which are listed.
- **The parameters these limits depend on are fixed in V1** (self-review defect 9). Only `max_output_bytes` and `max_items` vary, within their command-line ranges.
- **Updated:** the schema, the example, the Markdown contract (§7.4) and AT-23.

**Regression tests:**

- `test_seventeen_targets_stay_ambiguous_bounded_and_without_obligations`: 17 targets, then 1,000.
- `test_nine_finding_links_rank_fully_and_display_boundedly`: 9 links, then 1,000.
- `test_schema_limits_equal_the_specification_overflow_table`: every limit in the schema equals the §6.1 table.
- `test_example_parameters_are_the_specification_defaults`.

**Disposition:** pending independent review.

## Problems found in the builder's own review

1. **`bundle` with a missing `--bundles` directory exited 3** ("git bundle failed"), as if Git had failed. Found by the whole-workflow run, because the tests created the directory first.
   - Now exit 2: "`--bundles … is not an existing directory`".
   - `bundle` also refuses, with exit 2, a `--repo` that is not a Git repository and a shallow clone.
   - Test: `test_bundle_refuses_a_missing_directory_a_non_repository_and_a_shallow_clone`.
2. **A private input inside a `.git` directory passed `verify`.** The scan skipped every directory named `.git`, as it already did at `5304b5b`, and Git lists no path inside one. A gold sheet at `docs/.git/notes.json`, or at `.git/notes.json`, gave exit 0.
   - The scan now covers every regular file, `.git` included.
   - A nested `.git` is refused, and so is a symbolic link inside `.git`.
   - Test: `test_private_files_hidden_where_git_never_looks_are_rejected`.
3. **The workspace's own Git configuration could run a program during `verify`.** This revision's new status check runs `git status`. A clean filter set in `.git/config`, with `.git/info/attributes`, then ran, and `verify` still passed. Such a filter could also make a modified tracked file look unchanged. It was found and fixed before this revision was pushed.
   - Only the keys a fresh clone writes are allowed. Any other key, and any file in `.git/info` other than `exclude`, is refused.
   - When either is found, `git status` is not run at all.
   - Test: `test_workspace_configuration_cannot_run_programs_or_bend_the_status`. It also checks that the planted command never ran.
4. **Crafted file names reached the terminal raw.** Paths and configuration keys in messages are now escaped when they are not printable. Test: `test_crafted_names_cannot_drive_the_terminal`.
5. **An unreadable file in the workspace would have raised a traceback.** It is now a failed check. It is not tested, because the tests run as root, which can read any file.
6. **The observation envelope could grow.** A first draft allowed `"`, `\` and the backtick in `git_version`, so JSON escaping or a longer fence could exceed the computed maximum. The character set now excludes them. The maxima are 226 and 201 bytes; the draft said 236 and 213.
7. **The header tests ran in-process,** so a regressed loop would have hung the test run. They now run in a timed child process.
8. **No test bound the example's parameters to the specification,** and the finalization tests hard-coded 49,152 and 512. They now read the SPEC §6 table.
9. **The schema admitted parameter values that break §6.1's arithmetic.** With `max_anchor_matches` at 16, which the schema allowed, 32 anchors could need 517 obligations against a limit of 200. The obligations' targets could also exceed the 8 listed.
   - Every parameter except `max_output_bytes` and `max_items` is now a constant in the schema, as V1 fixes it.
   - SPEC §6 says so.
10. **No test checked that a refused start writes no record.** Every rejection test now does.
11. **Defects in the tool's first draft:**
    - `--help` exited 2;
    - staged changes were detected twice;
    - a missing parent of `--out` gave exit 3;
    - an unpinned task had no specific message;
    - a `git status` failure was exit 3, where it is now the failed check "the repository is damaged".
12. **`workspace` with a missing `--context` raised a traceback and left a partial workspace.** Found by probing every command with invalid arguments.
    - `--context` is now read, and bounded to 262,144 bytes, before anything is built.
    - Any later failure removes the partial workspace.
    - A target commit that tracks `.devcontext/` is refused.
    - Tests: `test_workspace_and_verify_refuse_bad_arguments_without_leaving_anything_behind` and `test_a_target_that_tracks_the_bootstrap_directory_is_refused_cleanly`.
13. **Inputs and messages:**
    - JSON inputs were read whole, at any size. They are now bounded to 16 MiB.
    - A missing `--inputs` or `--bundles` directory is refused with exit 2 before any check.
    - An existing `--record` was reported as "`--out` … exists".
    - A directory given as the manifest was reported as missing.
    - A dangling symbolic link at `--out` is refused.
14. **Stale statements and a noisy diff.** BENCHMARK-PLAN's freeze-order heading still said "revision 3's order", and the revision 4 summary left out F-14. A draft of this revision re-serialized `context-package.schema.json`, hiding its 52 changed lines in a 900-line diff. Its unchanged parts keep their earlier layout.

## Whole-workflow run

On a disposable synthetic repository, through the public CLI only:

- the source repository holds a start commit, a commit on `main`, a candidate branch and a later outcome commit;
- T1 is an implementation task, T2 an integration task with a candidate, and T3 is unpinned.

| Step | Command | Result |
| --- | --- | --- |
| 1 | `prepare --tasks … --tool-commit … --protocol-commit … --agent claude-code --agent codex --out freeze-plan.json` | exit 0, 2 tasks; "T3: not pinned (after T2); left out of the freeze plan" |
| 2 | write the bound inputs (synthetic) | 5 files per task |
| 3 | `bundle … --task T1` before creating the directory | exit 2: "is not an existing directory" |
| 3 | `bundle … --task T1`, then `--task T2` | exit 0, each bundle's SHA-256; no temporary ref left behind |
| 4 | `manifest --plan … --inputs … --bundles … --out freeze-manifest.json` | exit 0; the printed SHA-256 equals `sha256sum` |
| 5 | `verify` | exit 0 |
| 6–7 | `workspace` and `verify --record` for T1/A, T2/B (with `--context`) and T1/N | exit 0 each; three start records, valid against `benchmark-run.schema.json` by the spec suite's validator |
| 8 | 23 contaminated or invalid starts, each with `--record` | exit 1 each, and no record written |
| 9 | the published task plan given to `manifest`; malformed JSON | exit 2, no traceback |
| 9 | `prepare` on the real `benchmark-tasks.json` | exit 0: T1 and T2; T3 and T4 named as not pinned |
| 10 | `manifest` with the 16-byte bundle | exit 2 in 64 to 87 ms: "T1: bundle header ends before its terminating blank line" |

The 23 starts in step 8:

- the gold sheet in the work tree, and another task's hidden tests in a subdirectory;
- the later outcome commit fetched, so present but unreachable;
- a tracked file changed, an untracked source file, and a staged change;
- `task.md` missing, and `handoff.md` edited;
- a remote, an extra tag, a detached HEAD, and an alternates file;
- evaluator instructions inside the repository's `.git`, and the gold sheet in a nested `.git`;
- a clean filter in the workspace's own configuration, which never ran;
- the three cases `5304b5b` accepted: an empty repository, a dirty checkout of the target, and a wrong checkout (T2's `work` moved to the merge base);
- T2 without `candidate`, and T2's `context.md` not naming the target;
- a bare repository, another task's valid workspace, and arm A's workspace verified as arm N.

The run executed 40 commands, with the same results on Python 3.11.18, 3.12.3 and 3.13.18, and no traceback.

No Builder 1 output was fabricated. Arm B's context file is a synthetic placeholder naming the target commit, as the verifier requires.

## Non-regression of accepted findings

Every test from earlier rounds still runs and passes:

| Finding | Covered by |
| --- | --- |
| F-1: untrusted Git states and the network | §4.2 unchanged; the freeze tool keeps every transport off except `file` for bundles |
| F-2: disclosure checks | `test_example_passes_the_whole_output_disclosure_check_and_the_check_is_not_vacuous` |
| F-3: Markdown rendering | `test_example_rendering_is_inert_and_every_derived_value_is_fenced` |
| F-4: recorded findings and decision scope | `test_example_output_validates_and_the_validator_is_not_vacuous`: the schema holds `attribution` to `recorded; ownership not verified`, and a finding claiming `reviewer-owned` is refused. `test_baseline_status_conflicts_and_decision_scope_are_as_stated` |
| F-5: one coverage contract | `test_example_citations_symbols_classes_and_obligations_are_exact_at_the_pinned_commit`, which recomputes every obligation from Git |
| F-6: windowing | the same test: every symbol window, nothing more |
| F-7: the output bound | `test_example_respects_the_output_bound_and_the_per_field_limits` |
| F-8: executable tasks | `test_benchmark_task_plan_is_executable_and_holds_no_hashes`; the real T1 freeze test |
| F-9: the benchmark design | `test_collection_formats_accept_unmeasured_records_and_reject_invented_values` |

## Verification

On the final working tree, before the commit:

| Check | Python 3.11.18 | Python 3.12.3 | Python 3.13.18 |
| --- | --- | --- | --- |
| `pytest -q`, the whole repository | 859 passed | 859 passed | 859 passed |
| `pytest -q tests/adversarial` | 630 passed | 630 passed | 630 passed |
| `tests/test_builder1_spec.py` | 22 passed | 22 passed | 22 passed |
| `tests/test_benchmark_freeze.py` | 50 passed | 50 passed | 50 passed |
| the whole-workflow run, 40 commands | no unexpected result | no unexpected result | no unexpected result |
| the determinism run, 4 repositories at 7 bounds | identical | identical | identical |

- **Each full run reports one warning:** a deprecation notice from the installed Starlette test client, unrelated to this change.
- **Mutation checks: 67 of 67 planted defects were caught**, each by the test named for it. They covered the example, the schemas, the specification, the task plan and the freeze tool. An observations-only change to the example fails nothing.
- **Clean:** repository hygiene, `compileall`, `git diff --check`, the JSON files, and the relative links of the changed documents.
- **The environment:** SQLite 3.45.1 under Python 3.11 and 3.12, 3.53.1 under 3.13; Git 2.43.0; Linux only. macOS and Windows were not run.
- **CI** runs on the pushed head. Its result is reported in the PR, because a commit cannot record its own CI run.
- **Builder-local scripts.** The mutation, whole-workflow and determinism scripts are not committed. The committed tests reproduce each finding's reproduction and correction.

## What this record does not do

- It does not close, accept or reword any reviewer finding.
- It does not reproduce or replace the reviewer's artifacts.
- It does not implement Builder 1, and it measures nothing.
- It does not change the Security Gate, which remains NOT PASSED.
