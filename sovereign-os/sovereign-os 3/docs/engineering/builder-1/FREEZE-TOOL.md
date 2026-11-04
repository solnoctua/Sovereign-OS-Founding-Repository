# Benchmark freeze tool: usage guide

**Status:** PROPOSED tooling for [`BENCHMARK-PLAN.md`](BENCHMARK-PLAN.md) §5.

- **The tool:** [`scripts/benchmark_freeze.py`](../../../scripts/benchmark_freeze.py). It needs only the Python 3.11+ standard library and Git 2.24 or later.
- **How it is tested:** `tests/test_benchmark_freeze.py` runs every command below as a subprocess, on synthetic repositories and on this repository's pinned commits.
- **What it does not do.** It compiles no context and runs no agent. It measures nothing.

## When it is used

**The freeze happens after Builder 1 exists** (BENCHMARK-PLAN §5, lifecycle phase L3). By then the implementation commit is merged and its selection version is fixed.

**Nothing here is needed to implement Builder 1:**

- `prepare` needs the tool's commit;
- `manifest` needs the finished input files and bundles.

## Files

| File | Who writes it | Format | Where it lives |
| --- | --- | --- | --- |
| Task plan | builder, reviewed | [`benchmark-tasks.json`](benchmark-tasks.json), schema [`benchmark-tasks.schema.json`](benchmark-tasks.schema.json) | this repository. No hashes |
| Freeze plan | `prepare`, then the independent party | schema [`freeze-plan.schema.json`](freeze-plan.schema.json), example [`freeze-plan.example.json`](freeze-plan.example.json) | private until the results PR |
| Input files | the independent party | statement, arm A handoff, gold sheet, hidden tests, evaluator instructions, at the paths the freeze plan binds | a private inputs directory |
| Bundles | `bundle` | one Git bundle per task, holding exactly its pinned commits | a bundles directory |
| Freeze manifest | `manifest` | schema [`benchmark-freeze.schema.json`](benchmark-freeze.schema.json) | outside every bundle. Only its SHA-256 is published (§5, step 9) |
| Workspace | `workspace` | a Git work tree on branch `work` at the target, with `.devcontext/task.md` and the arm's context file | one per run |
| Start record | `verify --record` | schema [`benchmark-run.schema.json`](benchmark-run.schema.json), with `run: null` | written only after verification passes |

**About the checked-in example.** `freeze-plan.example.json` is exactly what `prepare` produces from the task plan with the commands below. Its tool and protocol commits (`1111…`, `2222…`) are placeholders, because no implementation exists yet.

## Commands

**Run them from the project directory** (`sovereign-os/sovereign-os 3`). `$INPUTS` and `$BUNDLES` are existing directories you choose.

1. **Derive the freeze plan** from the published task plan. Unpinned tasks (T3 and T4 today) are reported on standard error and left out.

   ```bash
   python scripts/benchmark_freeze.py prepare --tasks docs/engineering/builder-1/benchmark-tasks.json \
     --tool-commit <implementation commit> --protocol-commit <commit approving BENCHMARK-PLAN.md> \
     --agent claude-code --agent codex --out freeze-plan.json
   ```

2. **Write the input files** where the plan binds them. The defaults are `T1/statement.md`, `T1/handoff_a.md`, `T1/gold_sheet.json`, `T1/hidden_tests.py` and `T1/evaluator_instructions.md`.
   - Add held-out tasks to `freeze-plan.json` by hand. They never appear in the published task plan.
   - Set `hidden_tests` or `evaluator_instructions` to `null` where a task has none.

3. **Bundle each task's pinned commits** from a trusted, full (not shallow) clone:

   ```bash
   python scripts/benchmark_freeze.py bundle --repo /path/to/trusted/clone --plan freeze-plan.json --task T1 --bundles "$BUNDLES"
   ```

4. **Write the manifest**, then publish the SHA-256 it prints (§5, step 9):

   ```bash
   python scripts/benchmark_freeze.py manifest --plan freeze-plan.json --inputs "$INPUTS" --bundles "$BUNDLES" --out freeze-manifest.json
   ```

5. **Verify the frozen inputs and bundles:**

   ```bash
   python scripts/benchmark_freeze.py verify --manifest freeze-manifest.json --inputs "$INPUTS" --bundles "$BUNDLES"
   ```

6. **Build one run's workspace.** The arm is `A` (manual handoff), `B` (generated context: pass `--context` with the package's Markdown) or `N` (statement only):

   ```bash
   python scripts/benchmark_freeze.py workspace --manifest freeze-manifest.json --inputs "$INPUTS" --bundles "$BUNDLES" \
     --task T1 --arm A --out /path/to/run-T1-A
   ```

7. **Verify the start state, and record it.** Give the run's agent the workspace only after this exits 0:

   ```bash
   python scripts/benchmark_freeze.py verify --manifest freeze-manifest.json --inputs "$INPUTS" --bundles "$BUNDLES" \
     --workspace /path/to/run-T1-A --task T1 --arm A --record run-T1-A-start.json
   ```

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Success. For `verify`: every check passed |
| 1 | A verification check failed. The start state is **not** valid, and the run must not start. One line per failed check |
| 2 | Invalid input or usage, so nothing was checked or written. The causes include: missing or malformed JSON; an unsupported schema version; a schema violation; an unpinned task; a binding outside the inputs directory or to a missing file; a missing or malformed bundle; a missing `--inputs` or `--bundles` directory; a `--repo` that is not a full Git clone; a JSON input over 16 MiB, or a `--context` over 262,144 bytes; a target commit that tracks `.devcontext/`; an existing `--out`, `--record` or bundle file, including a dangling symbolic link |
| 3 | An operating failure: Git missing, failing, or slower than 300 seconds |

Messages name tasks, roles, fields and the files the user supplied. They never print file contents. An expected invalid input never produces a traceback.

## What `verify` checks

**The manifest, always:**

- It is valid against its schema, with at least one task and one agent, and no duplicates.
- Every input exists and has its frozen SHA-256 and size.
- Every task has a statement, an arm A handoff and a gold sheet.
- No input refers to the manifest.
- The digest and the arm assignment follow from the inputs.

**Each bundle:**

- Its hash and size are the frozen ones, and its header is valid and bounded.
- It has no prerequisites, and its refs are exactly the pinned commits.
- Its objects are all reachable, and their count is the frozen one.
- It holds no later commit, no input file, no manifest, and no freeze manifest inside the source history.
- A candidate task has a unique merge base.

**A workspace, with `--workspace`.** Each check covers both presence and absence.

- **What it is:**
  - a non-bare work tree, at its own top level;
  - not shallow, with no alternates, grafts, promisor state, replace refs or remotes;
  - only the configuration a fresh clone writes, and no file in `.git/info` but `exclude`. Anything else could run a program or change what `git status` reports, so the work tree is then not inspected.
- **Where it points:**
  - HEAD is born, on branch `work`, at the target commit;
  - the refs are exactly `work`, plus `candidate` at the candidate commit.
- **Its Git objects:** exactly the task bundle's objects. None is missing, and there is no extra one, reachable or not. No later commit is present.
- **Its files:**
  - no staged change, and no tracked file that differs from the target;
  - no untracked or ignored file outside the arm's allow-list in `.devcontext/`;
  - the arm's bootstrap files are present, with `task.md` and `handoff.md` byte-identical to the frozen inputs, and `context.md` naming the target commit;
  - no file anywhere in the workspace, `.git` included, has the bytes of any task's gold sheet, hidden tests or evaluator instructions;
  - no nested `.git`, and no symbolic link inside the repository's own `.git`. Git lists no path inside a `.git` directory, and the scan follows no link to a directory, so neither could otherwise be checked.

**A bare repository is never a valid workspace.** Bundles are cloned bare only inside the tool, for analysis.

**Pre-run, not post-run.** `verify` checks the start of a run. The agent is expected to change files afterwards. Judging the result is for the independent reviewers (BENCHMARK-PLAN §7).

## What it cannot detect

- A private file whose bytes were changed (a paraphrase, or a pasted fragment).
- A model's knowledge of the repository's later history from its training.
- Anything outside the workspace that an agent can reach. The agent's network and memory isolation is the runner's duty (BENCHMARK-PLAN §4).

## Removal

Delete `scripts/benchmark_freeze.py`, its test, and this guide. Nothing else depends on them.
