# PR #24 fourth independent review: builder response record (round 4), 2026-11-05

**Status:** builder-authored evidence, by `owlbuilder`.

- **What this is not.** It is not an independent review, not a findings artifact, and not the review itself.
- **The review.** The fourth independent Codex review, of `9c2715b783ae5c9545c1f5002cfd02742043c807`, returned CHANGES REQUIRED, as relayed in the founder's directive of 2026-11-05.
  - It accepted the architecture, and the specification's determinism, lifecycle, coverage, cardinality and security controls.
  - It left four findings in the benchmark freeze tool: F-12 (P2), F-13 (P2), F-16 (P2) and F-17 (P3).
- **The reviewer-owned artifacts are not in this repository, and the builder has not seen them.** On 2026-11-05, PR #24 and Issue #22 held no round-4 review or reviewer comment. Each finding below is the founder's relay of it.
- **No finding is closed by this record.** Every response is pending an independent disposition. The earlier records are unchanged.

**Scope.** Changed: `scripts/benchmark_freeze.py`, `tests/test_benchmark_freeze.py`, the guide [`FREEZE-TOOL.md`](../engineering/builder-1/FREEZE-TOOL.md), BENCHMARK-PLAN (§4 step 3 and a header note), the list of builder records in `tests/test_builder1_spec.py`, and this record. The specification, schemas and example are untouched.

| Finding | Reproduced against `9c2715b`, as uid 30033 | Correction |
| --- | --- | --- |
| **F-13** | `skip-worktree` or `assume-unchanged`, then the later outcome's code: `verified`, exit 0, and a start record with `freeze.valid: true`. The same for a root `.git` that is a symbolic link, or a gitfile, to metadata elsewhere holding the gold sheet | The verifier no longer trusts Git's view of the work tree. It hashes every tracked file itself, finds every other path by walking the directory, and requires `.git` to be an ordinary directory inside the workspace |
| **F-12** | An unreadable `.devcontext/task.md`, or an unreadable frozen gold sheet: a `PermissionError` traceback | Every read is contained. What `verify` cannot read is a failed check (exit 1); an unreadable input to `manifest` or `prepare` is invalid input (exit 2) |
| **F-16** | A dangling symbolic link at `bundles/T1.bundle`: `bundle` exited 0 and wrote the bundle at the link's target, outside the directory | Every output is written in a private staging directory and hard-linked into place. An occupied path is refused, never followed or replaced |
| **F-17** | Keys holding `ESC[31m` and U+202E reached standard error raw | Every line the tool writes is escaped and bounded at one point, usage errors included |

## F-13 (P2): false certification of altered sources or concealed private files

**Relayed:** `freeze.valid: true` for four invalid starts:

- `git update-index --skip-worktree`, then an altered source;
- `--assume-unchanged`, then an altered source;
- a root `.git` symbolic link to external metadata holding an exact gold sheet;
- a root `.git` gitfile to relocated metadata holding an exact gold sheet.

**Reproduced.** All four printed `verified: manifest …` and wrote a start record with `freeze.valid: true`. In each, `git status --porcelain` printed nothing.

**Causes.**

- **The work tree was judged by `git status`.** It honours both index flags, so a flagged file is never compared.
- **The private scan walked the workspace without following links, and skipped nothing else.** A `.git` link or gitfile moved the metadata outside the walk, while Git itself still used it.

**Correction** (`check_workspace` and the functions it calls):

1. **The metadata.** `.git` must be a real directory inside the workspace: not a symbolic link, not a gitfile. It must hold no `commondir`, and Git must report that directory and the workspace as its top level. Anything else is refused before Git is asked about the work tree.
2. **The index** must equal the target tree, entry for entry (`ls-files --stage` against `ls-tree -r`). A `skip-worktree` or `assume-unchanged` flag is refused, and so is an unmerged entry.
3. **The tracked files** are checked by the tool itself, with no Git stat cache, flag or filter:
   - each tracked file must be a regular file, not hard-linked, whose bytes hash to the target's blob, with the target's executable bit;
   - each tracked link must hold the target's link text;
   - Git is asked only for the checkout form of a file that `.gitattributes` converts. That comes after the configuration check has ruled out every filter program.
4. **Every other path** is found by walking the directory without following links, whatever the ignore rules say. Outside the arm's allow-list it is refused, and so are FIFOs, sockets and devices. `git status` is no longer used.
5. **The private scan** covers every regular file, `.git` included. An input of at least 64 bytes, without its trailing whitespace, is also found inside a larger file.
6. **The configuration check still comes first.** With an untrusted configuration, the work tree is not compared with the target, and the walk-based checks still run.
7. **No record on refusal.** The start record is written only when there is no failure, through the same safe publication as every output (F-16).

**Valid workspaces still pass:** fresh A, B and N workspaces, a task with a candidate branch, and a target whose `.gitattributes` converts line endings on checkout.

**Regression tests** (each through `verify --record`, asserting exit 1 and no record):

- `test_index_flags_cannot_hide_an_altered_source` (both flags, with and without a change);
- `test_relocated_git_metadata_holding_a_private_file_is_rejected` (link and gitfile);
- `test_content_is_checked_without_git_and_untracked_paths_by_walking`. Its cases:
  - a restaged change, a mode change, and a tracked file swapped for a link;
  - a hard-linked or symlinked bootstrap file;
  - an ignored file, a FIFO, a symlinked directory, and `commondir`;
- `test_embedded_private_inputs_and_deep_trees_are_handled`;
- `test_valid_candidate_workspaces_and_checkout_conversions_still_verify`.

**Disposition:** pending independent review.

## F-12 (P2): unreadable files raised tracebacks

**Relayed:** raw `PermissionError` tracebacks for an unreadable `.devcontext/task.md` and an unreadable frozen gold input.

**Reproduced** as uid 30033: both gave a traceback ending in `PermissionError: [Errno 13] Permission denied`.

**Causes, found by inspecting every read, not only those two:**

- frozen inputs, bootstrap files, bundles and schemas were read without a guard;
- `pathlib`'s `is_file()` and `is_dir()` raise on a permission error;
- `os.walk` drops a directory it cannot list without a word, which also hid its files from the private scan;
- a Git failure caused by an unreadable workspace ended as exit 3.

**Correction:**

- **Probes that never raise.** `kind_of`, `is_regular` and `is_directory` answer every question about a path.
- **One kind of read.** `read_regular` and `digest_regular` read regular files only, never follow a link where it matters, never block on a FIFO, and return nothing rather than raise.
- **`verify` and `workspace`:** a file, directory or piece of Git metadata that cannot be read is a failed check that names it (exit 1). No record is written, and no workspace is built.
- **`prepare`, `bundle` and `manifest`:** an unreadable input, plan or manifest is invalid input (exit 2), and nothing is written.
- **A last guard** turns any other filesystem error into exit 3 with its name, not a traceback.

**Regression test:** `test_unreadable_files_fail_cleanly_without_a_record_or_partial_output`. It covers:

- `task.md`, a tracked source and a directory holding the gold sheet;
- the gold sheet through `verify`, `manifest` and `workspace`;
- a bundle, a plan, and a read-only output directory.

It is skipped as root, which reads any file. It ran as uid 30033 here, and it runs in CI, whose runner is not root.

**Disposition:** pending independent review.

## F-16 (P2): a dangling symbolic link at the bundle's path

**Relayed:** a dangling link at the bundle's output name made `bundle` write to an unintended place.

**Reproduced:** exit 0. The bundle appeared at the link's target outside the bundles directory, and the link remained.

**Cause.** `out.exists()` is false for a dangling link, and `git bundle create` was then given `Path(out).resolve()`, which follows it.

**Correction: one publication path, `publish`.**

- The output is written in a private staging directory created beside the destination, then hard-linked to its name. `link(2)` never follows or replaces an existing path, a dangling link included.
- The staging directory is always removed. A failed Git run therefore publishes nothing, and a refusal leaves nothing behind.
- **All four file outputs use it:** the freeze plan, a bundle, the manifest and a start record.
- **`workspace --out`** creates its directory with a single `mkdir`, which refuses an occupied path the same way, and removes it again on any failure.

**Regression test:** `test_outputs_never_follow_or_replace_an_occupied_path`.

- **For `bundle`:** a dangling link, a link to an existing file and an existing file are each refused. Nothing outside is created or changed, the link is untouched, and nothing staged is left behind. An ordinary new path still works, and its printed hash matches the file.
- **For the other four outputs:** the freeze plan, the manifest, a record and a workspace each refuse a dangling link.

**Disposition:** pending independent review.

## F-17 (P3): diagnostic keys were not escaped

**Relayed:** user-controlled keys reached the terminal unescaped.

**Reproduced:** a freeze plan with the keys `ESC[31mRED` and U+202E put a raw ESC byte and a raw U+202E on standard error.

**Correction:**

- **One escaping point.** Every line the tool writes goes through `emit`. It escapes each non-printable character (`\x1b`, `‮`) and bounds the line to 2,000 characters.
- **Field names are bounded.** An unexpected field name is cut to 80 characters, so one long key cannot hide the others.
- **Usage errors too.** They used to print the user's arguments raw. They now raise through the same path.

**Regression test:** `test_diagnostics_escape_and_bound_user_controlled_text`, covering hostile keys, a hostile `--task`, and a hostile stray argument.

**Disposition:** pending independent review.

## Problems found in the builder's own review

Each was fixed with a regression test.

1. **Unreadable directories hid their files.** `os.walk` skipped them without a word. Now they fail the check.
2. **`RecursionError` on deep trees.** On Python 3.11, a directory 1,100 levels deep made `os.walk` raise it. The walk is now iterative.
3. **Embedded copies.** A gold sheet pasted inside a larger file, including without its final newline, was not found.
4. **Hard links and symbolic links.** A tracked or bootstrap file hard-linked to a file outside the work tree passed, and so did a bootstrap file that was a symbolic link to a frozen input.
5. **Ignore rules.** `git status` could be told to ignore a file, or to trust a stale untracked cache. The tool now walks the directory itself.
6. **A planted `.git/commondir`** moved the shared metadata outside the workspace.
7. **A relative `--out`.** `workspace` cloned a relative `--out` with a directory in it to the wrong place, because Git ran in the parent with the relative path again.
8. **Raw usage errors.** `argparse` printed the user's arguments raw.
9. **Deeply nested JSON** raised `RecursionError`. It is now invalid input (exit 2).
10. **Two exit codes were wrong:**
    - an input that exists but cannot be reached was reported as missing;
    - Git failing inside the workspace gave exit 3, where it now fails the check (exit 1).

## Whole-workflow run

The documented workflow ran through the public CLI only, on a disposable synthetic repository, as uid 30033, on Python 3.11.18, 3.12.3 and 3.13.18. The workflow was `prepare`, `bundle`, `manifest`, `verify`, then `workspace` with `verify --record`.

- **Valid starts.** T1 under arms A and N, and T2 (with a candidate) under arms B and N, each wrote a start record.
- **Refused output paths.** A dangling link at each output path, and a link to an existing file, were refused. Nothing was written through them.
- **32 invalid starts, each through `verify --record`.** Every one exited 1 and wrote no record:
  - the four round-4 bypasses;
  - a staged outcome, a changed file, a changed mode, and a file swapped for a link;
  - a hard-linked `task.md`, an ignored file, an untracked file, a FIFO, and a link to the private inputs;
  - `commondir`, a gold sheet in the work tree, one in a nested `.git`, hidden tests in `.git`, and a gold sheet embedded in `.git/description`;
  - a configuration filter, which never ran;
  - the later commit fetched, a remote, a detached HEAD, an empty repository, a dirty checkout, and a wrong HEAD;
  - a missing candidate branch, a bare repository, and missing objects;
  - an unreadable `task.md`, an unreadable tracked file, and the gold sheet in an unreadable directory;
  - a crafted file name.
- **Unreadable and malformed inputs.** An unreadable gold sheet failed `verify` and `workspace` (exit 1) and `manifest` (exit 2). An unreadable bundle, an unreadable plan and a read-only output directory were refused. So were the published task plan given as a freeze plan, malformed JSON, hostile keys and a hostile task name, the 16-byte bundle, and a SHA-256 bundle.
- **Totals.** 63 commands on each Python version, with no unexpected result, no traceback and no raw escape byte.

**No invalid start can produce a record through the known bypasses:**

- every rejection test passes `--record` and asserts that no record exists;
- each of the 32 invalid starts above was run with `--record`;
- removing any one of the checks, in 27 planted mutations, is caught by a test.

## Non-regression

- **F-1 to F-11, F-14 and F-15:** the specification, schemas and example are unchanged, and `tests/test_builder1_spec.py` passes.
- **Earlier freeze-tool tests:** every test from rounds 2 and 3 still passes, including the bundle-header tests of F-14 and the refusals of F-12 and F-13. One expected message changed wording: a workspace whose configuration is untrusted is "not compared with the target", no longer "not inspected", because the walk-based checks still run.

## Verification

On the final working tree, before the commit:

| Check | As root | As uid 30033 |
| --- | --- | --- |
| `pytest -q`, the whole repository, Python 3.11.18, 3.12.3 and 3.13.18 | 869 passed, 1 skipped (the permission test) on each | **870 passed** on each |
| `pytest -q tests/adversarial`, the same three versions | 630 passed on each | 630 passed on each |
| `tests/test_benchmark_freeze.py` | 60 passed, 1 skipped | **61 passed** |
| `tests/test_builder1_spec.py` | 22 passed | — |
| The whole-workflow run, 63 commands | — | no unexpected result on all three versions |

- **Each full run reports one warning:** a deprecation notice from the installed Starlette test client, unrelated to this change.
- **Mutation checks, run as uid 30033 so that the permission test counts.** 27 of 27 planted defects in the freeze tool were caught, each by the test named for it.
- **Earlier mutation checks.** The 43 that concern the specification, schemas, example and task plan, run again, were all caught. An observations-only change to the example still fails nothing.
- **Against `9c2715b`:** all 11 new round-4 test cases fail there and pass here.
- **Clean:** repository hygiene, `compileall`, `git diff --check`, the JSON files and the relative links of the changed documents.
- **CI** runs on the pushed head, whose runner is not root, so the permission test runs there too. Its result is reported in the PR.

## Limits that remain

- **Changed bytes.** A private input whose bytes were changed (a paraphrase, an encoding, a compressed copy, or a fragment) is not found.
- **Pre-run only.** `verify` proves the start state at the moment it runs. Isolating the agent's network, memory and filesystem beyond the workspace remains the runner's duty (BENCHMARK-PLAN §4).
- **What the tool trusts.** It trusts the `git` executable and the operating system. It reads the Git configuration only after refusing any key a fresh clone does not write.
- **Coverage.** The permission tests need a user other than root. Hard-link publication needs a filesystem that supports hard links. Only Linux and Git 2.43.0 were run; macOS and Windows were not.

## What this record does not do

- It does not close, accept or reword any reviewer finding.
- It does not reproduce or replace the reviewer's artifacts.
- It does not implement Builder 1, and it measures nothing.
- It does not change the Security Gate, which remains NOT PASSED.
