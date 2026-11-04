# Builder 1: Git-first development-context compiler (specification, PROPOSED, revision 4)

**Status:** PROPOSED. Tier 2 specification for WP-5, [Issue #22](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/issues/22).

- **No implementation exists.** Nothing here authorizes one. An implementation PR needs the founder's approval of this specification and of the decisions in §15.
- **Revision history.**
  - **Revision 2** answered the first independent Codex Tier 2 audit, of `ed7776d`: F-1 to F-10.
  - **Revision 3 (2026-11-03)** answers the second independent review, of `a03c524`, as relayed in the founder's directive: F-5 and F-10 were partly open (P2), and F-11 was new (P1).
  - Revision 3 also corrects the further defects that the builder's own review found (round-2 builder record).
  - **Revision 4 (2026-11-04)** answers the third independent review, of `5304b5b`: F-10 to F-15, all P2. Per the founder's directive, that review accepted F-5 and retained the earlier accepted corrections.
- **The builder records**, which are not reviewer artifacts:
  - [`docs/reviews/2026-11-03-pr24-builder-response.md`](../../reviews/2026-11-03-pr24-builder-response.md) (round 1);
  - [`docs/reviews/2026-11-03-pr24-round2-builder-response.md`](../../reviews/2026-11-03-pr24-round2-builder-response.md) (round 2);
  - [`docs/reviews/2026-11-04-pr24-round3-builder-response.md`](../../reviews/2026-11-04-pr24-round3-builder-response.md) (round 3).
  - The reviewer-owned findings are not in this repository, and nothing here closes them.
- **Baseline:** `main` at `99f302637d95f3d78cdd26a9f75d7a8ca336be99`, with schema 5.
  - SB-2a has since merged: PR #21 merged into `main` as `374011976b210f8624d1155e13e5e244bba2c0b6` on 2026-11-03, and this branch includes it.
  - Every fact below that names a commit stays pinned to that commit.
- **Not authority:** this is not an ADR, not a security certification, and not authority over anything it describes. Git and the founder's decisions win (§2).

**Companion files:**

| File | Content |
| --- | --- |
| [`BENCHMARK-PLAN.md`](BENCHMARK-PLAN.md) | The benchmark plan. No results |
| [`context-package.schema.json`](context-package.schema.json) | The output schema |
| [`context-package.example.json`](context-package.example.json), [`context-package.example.md`](context-package.example.md) | An example output and its Markdown rendering, generated from Git objects by the builder's throwaway reference model (§7.3) |
| [`benchmark-tasks.json`](benchmark-tasks.json) | The benchmark task plan. No hashes |
| [`benchmark-freeze.schema.json`](benchmark-freeze.schema.json), [`freeze-plan.schema.json`](freeze-plan.schema.json), [`freeze-plan.example.json`](freeze-plan.example.json), [`benchmark-tasks.schema.json`](benchmark-tasks.schema.json) | The detached freeze manifest, its single input (the freeze plan) and an example, and the task plan's schema. [`scripts/benchmark_freeze.py`](../../../scripts/benchmark_freeze.py) writes and verifies them; [`FREEZE-TOOL.md`](FREEZE-TOOL.md) is its usage guide |
| [`benchmark-run.schema.json`](benchmark-run.schema.json), [`gold-sheet.schema.json`](gold-sheet.schema.json) | The benchmark's records and reviewer-owned gold sheets |

## 1. Purpose, scope and non-goals

**Purpose.** Before a coding agent starts a task, give it a concise, verifiable, source-linked development package, built from the repository at exact commits. The agent is Claude Code, Codex or a human. The package carries:

- the task and the exact commits;
- the governance core and the decisions that apply, with their recorded scope;
- the source and test windows that the task names, or that ranking finds;
- recorded review findings;
- what is in conflict, missing or left out.

The package is meant to replace or supplement the hand-written handoff of `docs/DEVELOPMENT.md` § *Canonical context and handoff*. Whether it improves engineering outcomes is the [benchmark](BENCHMARK-PLAN.md)'s question. This document claims no gain.

**V1 scope.** `python -m devcontext` (§15 D-3). V1 is:

- local and offline;
- read-only;
- deterministic: the same canonical inputs give a byte-identical `package` (§4.1, §8).

It reads Git objects of one pinned target commit and, optionally, of a candidate commit and their merge base.

**Supported environment.** Linux or macOS, CPython 3.11 to 3.13 (the project's `requires-python` is `>=3.11`), and Git 2.24 or later. Windows is not supported in V1.

**Authorized sources (F-2).** V1 is authorized only for the tracked content of this repository, `solnoctua/Sovereign-OS-Founding-Repository`. Repository policy keeps that content synthetic or intentionally non-sensitive (`docs/SECURITY-GATE.md`, `scripts/check_repository_hygiene.py`).

- **V1 is not a privacy control.** It must not be run on another repository, a fork, or a branch that may hold private material.
- **Pattern checks are a backstop only.** §9 says exactly what they can and cannot detect.

**Repository context, not live state.** V1 reports what Git holds at the pinned commits. It does not know the current state of GitHub issues, pull requests or reviews. Those reach an agent through the normal Builder 0 handoff (§2.5).

**Non-goals.** These come from Issue #22, the founder's benchmark addendum to Issue #22, BUILD plan §5.6 and §6, `FOUNDER-DECISIONS.md`, and the founder's directive of 2026-11-03.

- **No autonomy:** no autonomous agent, self-editing, merges, approvals, test execution, tool broker, agent orchestration or Builder 2.
- **No network of any kind:** no provider or model calls, no embeddings, no GitHub API, and no Git transport (§4.3).
- **No new state:** no graph database, persistent index or cache, background indexing, or automatic synchronization.
- **No third-party tooling:** no code graph (Graphify is deferred until an ablation shows benefit, BENCHMARK-PLAN §2), and no third-party code, skills or hooks.
- **Nothing installed into agents:** no model-specific memory dump, and nothing installed into Claude Code or Codex.
- **No personal data:** no personal vault, no `SOVEREIGN_DB_PATH`, no `*.db` file, no canonical memory read or write. No secrets, credentials or environment values in the output.
- **No development vault in V1** (§2.4).
- **No changes elsewhere:** no change to the production Context Compiler (`context.py`), its policy, tokens or disclosure, or to any `sovereign` module.
- **No new runtime dependency.** The standard library and the `git` executable are enough.

## 2. Authority model

### 2.1 Order

When the target commit has the line, the package carries the authority order verbatim, extracted as follows:

1. Take the first line of `docs/engineering/BUILD-AND-INTEGRATION-PLAN.md` that starts with `**Authority order:**`.
2. Keep the text after that label up to the first `. ` or the end of the line.
3. Split it at ` → `.
4. Trim each part, and keep it otherwise unchanged.

The line itself is a core item (§5.4). `authority_order` names that item and lists the parts. At the baseline this gives: Constitution candidate (NOT RATIFIED) → founder decisions → approved ADRs → `ARCHITECTURE.md` → `ROADMAP.md` §H → this plan → bounded PRs.

**When the line is absent** (F-8), `authority_order` is `null` and `missing` records it. The line does not exist at `eeed753`, T1's start, for example. The order is never invented.

### 2.2 Classes and status lines

**Every item has exactly one class.** It is assigned by the item's path, and in `docs/FOUNDER-DECISIONS.md` by the table that a register row sits in (§5.3). Classes never move upward:

- a recorded review file is never presented as verified reviewer evidence;
- a proposal is never presented as a decision;
- an ADR is never presented as approved as a whole.

| Class | Meaning |
| --- | --- |
| `constitution_candidate` | `CONSTITUTION.md`: a ratification candidate, not ratified |
| `binding_decision` | a row of the *Approved* table in `docs/FOUNDER-DECISIONS.md`. Its scope is the row's own text (§2.3) |
| `proposed_or_historical` | rows of that file's other tables, and other Markdown files whose status line's first word is `proposed` (§5.3, rule 8). Historical sections are not detected by content: their own dates and labels are quoted as written |
| `adr` | text from `docs/adr/NNNN-*.md` |
| `governance_doc` | the project and repository-root `AGENTS.md` and `CLAUDE.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `docs/SECURITY-GATE.md`, `docs/DEVELOPMENT.md`, the Markdown files directly in `docs/engineering/`, and the text of `docs/FOUNDER-DECISIONS.md` outside its table rows |
| `registry_fact` | `docs/architecture/systems-registry.toml` |
| `recorded_findings` | a `docs/reviews/*-findings.json` file. Ownership is **not verified** (§2.3) |
| `builder_record` | any other file in `docs/reviews/` |
| `source`, `test`, `other` | code under `src/` and `evaluation/`, tests under `tests/`, and any other tracked text |

**Status line.** A Markdown file's status line is the first of its first 10 lines that starts with `Status:`, after a leading `- ` and the emphasis marks `*`, `_` and `` ` `` are removed.

- The match is case-sensitive.
- Lines inside a leading YAML front-matter block (`---` … `---`) are never considered.
- **Matches:** `- Status: Proposed (…)` and `**Status:** PROPOSED.`
- **Does not match:** `**Current status: NOT PASSED.**`, or a demo note's front matter `status: "proposed"`.

A file's status line is stored once, in its `sources[]` entry (§7.1). It is cut to at most 512 bytes on a UTF-8 character boundary, with `status_line_truncated: true`.

### 2.3 Rules the package must keep

1. **Status is quoted, never inferred.** The package reports facts and resolves nothing.
   - **The status keyword** is whichever of `proposed`, `accepted`, `approved`, `confirmed`, `superseded`, `rejected`, `deprecated` occurs first in an ADR's status line, after emphasis marks are removed.
   - **A `decision_status` conflict** is reported for an ADR that is anchored, or that an included item cites, when either:
     - the keyword is `proposed` and a row of the register's *Approved* table names the ADR; or
     - the keyword is `accepted`, `approved` or `confirmed`, and only *Proposed* or *Rejected* rows name it.
   - **Its `sides` are the status line and the rows, verbatim.** Its summary never says that an ADR is approved or binding.
   - **At the baseline `99f3026`**, among all seven ADRs, the rule finds exactly ADR-0003 and ADR-0004 (AT-8).
2. **Decision scope (F-4).** A register row is a decision with exactly the scope its text states. The package carries the row verbatim and never extends it to the whole ADR that it names.
   - At the baseline, the 2026-10-21 row approves ADR-0005's D1–D14 as direction and R1–R7 as planning positions, and *defers* D15. Text from ADR-0005's D15 sections stays class `adr`, and no field calls it approved (AT-19).
   - A row that proposes an *amendment* to an ADR is not a proposal of that ADR. Row 34 at the baseline, an ADR-0004 amendment, is an example.
3. **Recorded findings (F-4).**
   - **Ownership is not verified.** A `docs/reviews/*-findings.json` file is *recorded*, not proven to be reviewer-owned. Its path and Git author can both be written by anyone with push access, and a builder-written file with a forged author was reproduced (round-1 record, F-4).
     - Every finding therefore carries `attribution: "recorded; ownership not verified"`.
     - Verifying ownership, for example through signed commits, is a later decision (§15 D-11).
   - **Fields are copied, not interpreted.** `severity`, `confidence`, `status` and `independent_disposition` are copied verbatim, and the package never derives *closed*, *open* or *resolved*.
     - `independent_disposition: accepted` is the reviewer's word on a builder response, and that response can be `deferred_with_reason`.
     - So `accepted` is never presented as closure, or as the technical issue being resolved.
   - **A finding's identity is the pair (findings file, `id`).** IDs are unique only within a file (`docs/engineering/FINDINGS-FORMAT.md`).
     - `F-1` already names different findings: at the baseline, the PR #10 audit's evidence-set finding and an unrelated example finding in `docs/engineering/findings-example.json`.
     - An `F-N` anchor resolves to every file that contains it, and all matches are listed, never merged.
4. **Git wins.** The package describes pinned commits. Statements in them about other states are quoted as text, not checked: for example "PR #20 merged" or "candidate, not merged". The package never asserts GitHub state (§2.5).
5. **Nothing is reconciled.** Contradictions, gaps and omissions go to `conflicts`, `missing` and `omitted`.

### 2.4 Development vault: deferred

BUILD plan §6 and `ARCHITECTURE.md` §14 describe a development vault: a second K1 store on a separate file. **V1 reads no vault.**

If a later version reads one:

- it opens only a file passed explicitly, read-only;
- it refuses `SOVEREIGN_DB_PATH`, `./data/sovereign.db` and the personal data directory;
- it classifies every claim as subordinate to Git.

BUILD §5.6 says that disagreement makes a claim `contested`. That is a write, so a read-only tool can only report the disagreement. That version needs its own ADR (§15 D-6).

### 2.5 Dynamic GitHub state: excluded in V1

Issue and PR state, comments and reviews are not in Git, so V1 does not read them.

- Each issue or PR anchor in the task is reported in `missing` with reason `outside_v1_scope`.
- **Current GitHub status reaches an agent through a separate, human-written handoff.** The Builder 0 five-field handoff (`docs/DEVELOPMENT.md`) gives the PR, review and issue state at a stated time, beside the package. The package's header says it does not carry that state.
- A later version may accept an explicit snapshot file, made by a human outside the tool. The tool would include it with its SHA-256 and stated time, labelled non-canonical, and would never fetch it itself (§15 D-5).

## 3. Command-line contract

```text
python -m devcontext (--task TEXT | --task-file PATH) [--repo PATH] [--rev REV] [--candidate REV]
                     [--max-output-bytes N] [--max-items N] [--format json|md] [--out FILE]
```

**How it runs.** From the project directory (`sovereign-os/sovereign-os 3`), with no installation step. `python -m devcontext --help` prints the arguments, limits and exit codes below.

**Inputs.**

| Argument | Required | Default | Rule |
| --- | --- | --- | --- |
| `--task TEXT` or `--task-file PATH` | one of them | — | 1–2,000 characters of UTF-8, with no NUL. A file is read before any repository access, and one final `\n` is removed from it, if present. A task that matches a credential pattern exits 2, and the task is not echoed |
| `--repo PATH` | no | current directory | Git is invoked only as `git -C PATH`. The repository must pass the preflight (§4.2) |
| `--rev REV` | no | `HEAD` | The target. Resolved once to a full commit SHA. A full SHA is recommended, because an abbreviated one can become ambiguous |
| `--candidate REV` | no | none | A commit to integrate. Resolved once. Its merge base with the target must be unique (§4.1) |
| `--max-output-bytes N` | no | 49,152 | The bound on the whole serialized output, 16,384–262,144 (§6) |
| `--max-items N` | no | 40 | 1–200 |
| `--format` | no | `md` | `json` prints the output object; `md` prints its rendering (§7.4) |
| `--out FILE` | no | standard output | Creates a new file only. Refuses a path that exists (including a dangling symbolic link), a path whose parent directory does not exist, and a path inside the `--repo` repository. It is opened with exclusive creation, and removed again if writing fails |

**Exit codes.** Nothing is printed to standard output unless the exit code is 0.

| Code | Meaning |
| --- | --- |
| 0 | A package was produced. Every known mandatory obligation is satisfied (§5.4) |
| 1 | Internal error. The message is fixed, and has no traceback or content |
| 2 | Invalid arguments or task: out-of-range values, a task that is too long or has more than 32 anchors, or a task that matches a credential pattern |
| 3 | A required input is missing or unresolvable: not a Git repository; the target or candidate cannot be resolved, or is ambiguous; no unique merge base; no unique project root; the `AGENTS.md` section or the Security Gate status line is missing |
| 4 | Mandatory evidence cannot be delivered: an anchored path is not readable; the core exceeds `core_bytes`; the mandatory excerpts exceed the excerpt budget or `max_items`; the candidate changes more than `max_candidate_paths` paths; or mandatory content alone exceeds `max_output_bytes` |
| 5 | Unsafe repository state (§4.2), Git older than 2.24, or a Git resource limit (§4.3) |
| 6 | The disclosure check failed: mandatory evidence or the final output matched (§9) |

**Errors are content-free and actionable.**

- An error message is a fixed sentence naming the condition. It may echo what the user supplied: an argument, or an anchor's text from the task.
- It may give sizes and counts, for example: mandatory evidence needs 20,214 bytes in 18 items, and the excerpt budget is 8,192 bytes.
- It never includes Git's standard error, repository content, or a repository path that the user did not supply. Git's standard error was shown to echo repository-derived names (round-1 record, F-1).

## 4. Reading the repository

### 4.1 Canonical inputs and what is derived from them (F-10)

**The canonical inputs are everything that can change the `package`:**

1. **The target commit SHA**, and the candidate commit SHA or none.
2. **The task text:** the exact characters, as normalized by §3 (one final newline removed from a task file, and nothing else).
3. **The parameters**, every effective value of §6.
4. **The generator:**
   - `version`;
   - `selection_version` (`devcontext-selection-3`), which covers the rules of §5 and §9's patterns;
   - the stopword list's SHA-256;
   - `python_grammar` (`3.11`, §4.5);
   - the forbidden-path predicate shipped with the running tool (§4.4).

**Everything else in the package is derived from those inputs through Git's content addressing:**

- the trees;
- the merge base, from `merge-base --all`;
- the history set: every commit reachable from the target and the candidate, from `rev-list`;
- the blobs.

A commit SHA fixes its entire reachable history. The preflight (§4.2) refuses the states in which a repository could present different history for the same SHA: shallow, partial, grafted, alternates. Replace refs are ignored. So the history needed for a task is part of the canonical inputs without being listed: it is a deterministic function of the pinned SHAs.

**Never canonical (F-10).** These never change the package, and some are reported only as observations (§7.2):

- the checkout location, working directory and installation location;
- the working-tree state, and whether the repository is bare;
- loose versus packed objects, unrelated or unreachable objects, and unrelated branches, tags and other refs;
- Git's standard error, the Git version (2.24 or later), and the Python version (3.11 to 3.13);
- hostname, user, time and locale.

**Resolution is history-scoped.**

- **Caller references.** `--rev` and `--candidate` are resolved once with `git rev-parse --verify --end-of-options <rev>^{commit}`, which can depend on local refs. From then on only full SHAs are used, and the package records only the SHAs.
- **Anchors** (§5.2) resolve only against the pinned trees and the history set. Nothing consults the object database as a whole.
- **Why.** Revision 2 resolved commit anchors with `cat-file -e`. One clone holding an unrelated dangling commit then resolved an anchor that another clone left unresolved, which changed the package (round-2 record, F-10).

**Candidate mode.**

- `git merge-base --all target candidate` must return exactly one commit; otherwise the run exits 3.
- **The candidate's changes** are those from the merge base to the candidate, from `diff-tree -r --no-renames --name-status`. For each changed path the package records:
  - its status;
  - the changed line ranges in the candidate version;
  - whether the target also changed the path since the merge base.
- **Changed line ranges** are computed in Python with `difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)`, over the `replace` and `insert` opcodes, rather than by Git's diff, whose output depends on version and configuration. They are capped at 20 ranges per path, and the overflow is counted.
- **Items of candidate-changed paths** are read from the candidate tree. Governance and the core always come from the target tree.
- **Why not a two-tree diff.** A two-tree target-to-candidate diff was rejected. On T2 it lists 52 paths, of which only 11 are the candidate's own changes (round-1 record, F-8).

**Every citation names its commit and blob.**

### 4.2 Repository trust preflight (F-1)

Before any object is read, every condition below is checked. Any failure exits 5, with a fixed message naming the condition.

| Condition | Why refused | Check |
| --- | --- | --- |
| **Shallow repository** | Ancestry and merge bases are incomplete, and missing objects invite fetches | `rev-parse --is-shallow-repository` |
| **Promisor or partial clone** | A lazy fetch is network access. Git 2.43.0 marks a `--filter` clone with `remote.<name>.promisor=true` and **not** with `extensions.partialClone` (round-1 record, F-1) | `config --get-regexp` (all files, includes honoured) for `extensions.partialclone`, `remote\..*\.promisor` and `remote\..*\.partialclonefilter`, plus any `objects/pack/*.promisor` file |
| **Alternates** | Objects can come from an unreviewed store outside the repository | `objects/info/alternates` or `objects/info/http-alternates` exists and is not empty |
| **Grafts** | `--no-replace-objects` does **not** disable grafts, and a graft changed the merge base in a reproduction | `info/grafts` exists |
| **Ownership** | Git's `safe.directory` refusal | any refusal of `rev-parse` |
| **Git version** | `--end-of-options` and `protocol.allow` need Git 2.24 or later | `git --version` |

- **Paths come from Git.** Paths inside the Git directory are obtained with `rev-parse --git-path` and `--git-common-dir`, and only their existence and size are read.
- **Replace refs.** `refs/replace/*` is neutralized by `--no-replace-objects` and `GIT_NO_REPLACE_OBJECTS=1`, and its count is an observation (§7.2).

### 4.3 Git invocation (F-1)

**Allowed commands.** Only these plumbing commands may run, through one helper, with an argument list and never a shell:

- `rev-parse` (`--verify`, `--end-of-options`, `--is-bare-repository`, `--is-shallow-repository`, `--git-path`, `--git-common-dir`, `--show-toplevel`);
- `cat-file` (`blob`, `-t`, `-s`, and `--batch` on stdin);
- `ls-tree -r -z -l --full-tree`;
- `diff-tree -r -z --no-renames --name-status --no-textconv --no-ext-diff`;
- `merge-base --all`;
- `rev-list` of the target and candidate (the history set, §4.1);
- `config --get-regexp` with the fixed patterns of §4.2;
- `diff-index --quiet --no-ext-diff --no-textconv HEAD --` and `ls-files --others --exclude-standard -z`. These two feed observations only, and only their exit status and count are used;
- `git --version`.

| Control | Setting |
| --- | --- |
| Arguments | `git -C <repo> --no-pager --no-replace-objects -c protocol.allow=never -c core.fsmonitor=false -c core.hooksPath=/dev/null -c diff.external= -c core.pager=cat` |
| Environment | Every inherited `GIT_*` variable is removed, then these are set: `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_TERMINAL_PROMPT=0`, `GIT_ALLOW_PROTOCOL=` (empty: no protocol allowed), `GIT_NO_REPLACE_OBJECTS=1`, `GIT_NO_LAZY_FETCH=1`, `LC_ALL=C` |
| Limits | `stdin` closed except for `--batch`. 30 seconds per call and 120 seconds per run. Standard output capped per call: 300 KiB for a blob, 8 MiB for a tree listing or history. Reaching a limit exits 5 |
| Standard error | Captured and discarded. It is never printed, logged or included (§3) |

**What V1 claims about the network, and what it does not.** It cannot prove that a Git binary never opens a connection. It claims three things, each with a behavioural test (AT-7) on local `file://` fixtures:

1. Only local plumbing runs.
2. Every transport is disabled by `protocol.allow=never` and `GIT_ALLOW_PROTOCOL`. In a reproduction, `protocol.allow=never` stopped a lazy fetch: "transport 'file' not allowed".
3. Network-capable states are refused before any read (§4.2).

It does not rely on `GIT_NO_LAZY_FETCH`, whose presence varies by build, or on a Python socket monkeypatch, which does not stop a Git child process (round-1 record, F-1).

### 4.4 Which blobs are read

**Tree entries** of the target tree, and of the candidate tree for candidate-changed paths, are considered in Git's tree order. They are filtered as follows:

1. **Modes.** Only regular files (modes `100644` and `100755`). Symbolic links and submodules are counted in `excluded` and never followed.
2. **Unsafe paths.** These are counted as `unsafe_path` and never read:
   - a path that is not valid UTF-8;
   - a path longer than 512 bytes;
   - a path holding a C0 or C1 control character, DEL, or a bidirectional or zero-width format character.
3. **Forbidden paths.** A path that `forbidden(path)` refuses is never read: vault databases and sidecars, `.env*`, keys, caches, private export folders.
   - `forbidden` is the predicate of `scripts/check_repository_hygiene.py` **as shipped with the running tool**, not as found in the repository being read.
   - A bare clone has no work tree to import it from, and a target commit must not be able to change the predicate that protects it.
4. **Size.** A blob over `max_file_bytes` (262,144 bytes) is never read. At the baseline, `evaluation/retrieval/results.json` (886 KB) is excluded this way.
5. **Encoding.** A blob that is not valid UTF-8, or that holds NUL, is counted as binary.
6. **Caps.** At most 5,000 tree entries and 64 MiB of blob bytes per run. Beyond either cap the run exits 5.

### 4.5 Lines and Python grammar

- **Lines.** A text is split on `\n` only: line N is the Nth element of `text.split("\n")`, and a final empty element after a trailing `\n` is not a line. `\r`, form feed and Unicode line separators are ordinary characters.
  - `str.splitlines()` would split on them too, and would cite different line numbers for the same blob.
  - No baseline blob differs between the two rules, but the rule is fixed here so that every implementation cites the same lines.
- **Python.** Python files are parsed with `ast.parse(text, feature_version=(3, 11))`. A file that does not parse (`SyntaxError`, `ValueError`, `RecursionError` or `MemoryError`) is treated as other text (§5.3).
  - The grammar is pinned because the interpreter's default grammar changes with its version. A file using Python 3.13 syntax parses into definitions under 3.13 and fails under 3.12, so two interpreters would build different packages from the same inputs (round-2 record, F-10).
  - **Residual limit:** a pathologically nested file that one supported interpreter parses and another rejects would still diverge. The repository's own files are checked by AT-1.

## 5. Selection

These rules are deterministic: no randomness, time, locale, model or hash ordering. Every sort below has a total order. `selection_version` is `devcontext-selection-3`, and any change to §5 or to §9's patterns changes it.

### 5.1 Task terms

- **Terms.** Replace each non-ASCII character of the task by a space, lowercase `A`–`Z`, split on characters that are not ASCII letters or digits, and drop words shorter than three characters and stopwords. The terms are sorted and de-duplicated. The first 64 in sorted order are kept, and the rest are counted in `task.terms_omitted`.
- **Stopwords (V1, 63 words):** about, after, all, also, and, any, are, been, before, being, but, can, could, did, does, each, for, from, had, has, have, how, into, its, may, must, not, only, our, out, over, per, should, such, than, that, the, their, them, then, there, these, they, this, those, under, use, using, via, was, were, what, when, where, which, while, who, why, will, with, would, you, your.
  - `generator.stopwords_sha256` is the SHA-256 of these words sorted, joined with `\n`, with a final `\n`: `d7201270c0b668153c2531f2646d5f0115bb8e6f388abe4a0841541939482c9b`.
- **Name tokens.** For the name signals of §5.5, a file name (without extension) or a definition's last name component is split on `_`, `-` and lowercase-to-uppercase boundaries, then turned into terms by the same rule.
  - A task term of at least 5 characters **matches** a name token of at least 5 characters when they are equal, or when both are at least 6 characters long and share their first 6.
  - So `migration` matches `_migrate`, and `navigation` matches `navigate`, while `context` does not match `content`.

### 5.2 Anchors

**What an anchor is.** Anchors are explicit references in the task. Each one generates mandatory evidence (§5.4) or a reported fact. At most 32 are allowed; a task with more exits 2.

**Recognition.**

- **The candidate tokens are:**
  - backtick-quoted strings;
  - whitespace-delimited tokens, with `([{<"'` removed from the start and `)]}>"',;:.!?` from the end. A final `()` is kept.
- Each recognizer below runs on its own. When matches overlap, the one that starts first wins, then the longest, then the earlier kind in the table's order.

| Kind | Recognized form | Resolution, against the pinned trees and history only |
| --- | --- | --- |
| `span` | `<path>:<L>` or `<path>:<L>-<M>`, where `<path>` would be a path anchor | the path resolves, and 1 ≤ L ≤ M ≤ its line count |
| `path` | a token containing `/`, or a file name with an extension of 2–10 characters (such as `store.py`) that resolves | in order, stopping at the first rule that matches: (1) the path relative to the project root; (2) the path relative to the repository root; (3) a unique path that ends with `/` + the token. Several matches are `ambiguous`. A token with `/` that matches nothing is `unresolved`; a bare file name that matches nothing is not an anchor |
| `symbol` | `Name.name…` starting with an uppercase letter; `name()` or `a.b()`; a backtick-quoted identifier or dotted identifier; or a bare identifier containing `_` that matches a definition | definitions by `ast` (§5.3) in the eligible Python files under the project root in the target tree, and in the candidate's changed Python files. A dotted name matches a qualified name exactly; a bare name matches the last component. A bare identifier that matches nothing is not an anchor |
| `adr` | `ADR-NNNN`, standalone | `docs/adr/NNNN-*.md` exists in the target tree |
| `finding` | `F-N`, standalone | records with that `id` in the target tree's `docs/reviews/*-findings.json`; every file that has one is a match |
| `issue_or_pr` | `#N`, after URLs and Markdown link targets are blanked; the expression is below | an eligible text in the target or candidate tree has the same standalone reference |
| `commit` | 7–40 lowercase hex characters with at least one letter, standalone | a unique prefix of a commit in the **history set** (§4.1). Several matches are `ambiguous`. An object that exists elsewhere in the database does not count |

The `issue_or_pr` expression is applied after URLs (`https?://\S+`) and Markdown link targets are replaced by spaces:

```text
(?:(?<=^)|(?<=[\s(\[]))#(\d+)(?![\w-])
```

At the baseline, the naive substring `#15` occurs 8 times on 7 lines, 5 of them link fragments. This rule keeps exactly the 3 issue references (AT-9).

**Outcomes.** Every anchor is listed in `task.anchors` with `resolution` (`resolved`, `ambiguous` or `unresolved`), its `target_count`, and at most 8 of its `targets`, in sorted order: full paths, `path:qualified-name`, `path:L-M`, or full SHAs. Resolution and obligations are decided on the full count, never on the listed targets (§6.1).

- **1 to `max_anchor_matches` (4) targets:** every target generates an obligation (§5.4), whether the anchor is resolved or ambiguous. All of them are listed.
- **More than 4 targets:** no obligation. `missing` says `ambiguous` and suggests qualifying the anchor.
- **Unresolved:** no obligation, and `missing` says `unresolved`. An unresolved anchor is a fact about the commits: a task may name a method it is about to create. The Markdown header lists it prominently.
- **`issue_or_pr`:** never an obligation. GitHub state is listed in `missing` as `outside_v1_scope`.
- **`commit`:** never an obligation. Its full SHA is recorded.

### 5.3 Chunks, windows and classes (F-6)

**Chunks.** Each eligible blob is cut into **contiguous** chunks of whole lines. Blank lines at the edges of a chunk are dropped.

| File type | Chunks and symbols |
| --- | --- |
| Python that parses | One chunk per top-level function. For each top-level class: its header (from its first decorator or `class` line to the line before its first member) and each **direct member** (function or nested class) separately. Lines of a class after its last member form one more chunk. Every maximal run of lines outside any top-level definition is its own chunk. Symbols: the function name, `Class`, or `Class.member` for a member; none for runs |
| Markdown | From an ATX heading (`#` to `######` and a space, outside fenced blocks) to the line before the next heading. Symbol: the heading text without its `#` marks |
| `docs/FOUNDER-DECISIONS.md` | Each table body row is its own one-line chunk, classed by its table. The rest is cut at headings and at rows, like other Markdown |
| TOML | From each table or array-of-tables header to the line before the next. Symbol: the header line |
| Other text (including JSON, JavaScript, Python that does not parse) | Consecutive blocks of 60 lines. No symbol |

**Why every chunk is contiguous.** Revision 2's "module header (docstring and top-level statements outside definitions)" was not a contiguous range. A model that took it literally produced a 900-line chunk spanning every definition (round-2 record).

**Windows.**

- A chunk larger than `max_item_bytes` (2,048) is split greedily into consecutive windows on line boundaries.
- A window's size is the UTF-8 length of its lines joined by `\n`.
- A single line longer than `max_item_bytes` forms a window on its own. It is admitted only as mandatory evidence; as optional evidence it is skipped and counted.
- Each window records its chunk's `symbol` and `span`, the chunk's first and last lines.
- **Every excerpt is exact:** it equals the cited lines, with no truncation.

**Why windows.** Revision 1 kept a 2 KiB *prefix* of each chunk. At the baseline the `Vault` class is 56,551 bytes, with 38 methods. The prefix kept 3.6% of it, and every method a Forget task needs lay outside it (round-1 record, F-6).

**Class rules.** They match the path relative to the project root, and the first match wins:

1. `CONSTITUTION.md`
2. `docs/FOUNDER-DECISIONS.md`: rows by table, the rest `governance_doc`
3. `docs/adr/`
4. `docs/reviews/*-findings.json`: `recorded_findings`
5. `docs/reviews/`
6. `docs/architecture/systems-registry.toml`
7. the governance documents of §2.2
8. any other Markdown file whose status line has `proposed` as its first word
9. `src/` and `evaluation/`
10. `tests/`
11. everything else

Outside the project root, the repository-root `AGENTS.md` and `CLAUDE.md` are `governance_doc`, and everything else is `other`. At the baseline, rule 8 matches exactly `docs/second-brain/OBSIDIAN-PROJECTION.md` and `docs/second-brain/SECOND-BRAIN-VALIDATION.md`.

### 5.4 Evidence obligations and completeness (F-5)

**The package distinguishes three kinds of evidence** (item `role`, §7.1):

| Kind | Role | How it is chosen | If it cannot be delivered |
| --- | --- | --- | --- |
| **Mandatory: the governance core** | `core` | The selection invariants below, always | Exit 3 if absent; exit 4 if it exceeds `core_bytes` |
| **Mandatory: task obligations** | `required` (excerpts), or the field named below | Generated from resolved anchors and from the candidate (§5.2, §4.1) | Exit 4 |
| **Optional: discovered evidence** | `optional`, with tier `linked` or `related` | Ranked deterministically (§5.5) | Left out, counted and listed in `omitted`. Never an error |

**Obligations.** Each obligation has an id (`M1`, `M2`, …), a kind, the anchor that generated it (or none), and what satisfies it. They are generated in this order: `agents`, `security_gate` and `authority_order`; then, for each anchor in the task's order, one obligation per target; then `candidate`; then `codeowners`.

| Kind | Generated by | Satisfied when the package contains |
| --- | --- | --- |
| `agents` | always | every window of the project `AGENTS.md` section *Read before consequential work* (935 bytes at the baseline). Claude Code and Codex load the whole file themselves |
| `security_gate` | always | the first line of `docs/SECURITY-GATE.md` containing `Current status:` |
| `authority_order` | the line exists (§2.1) | that line |
| `adr` | each resolved ADR anchor | the ADR's source entry, with its status line, and **every** register row naming it, verbatim |
| `symbol` | each target of a symbol anchor | **every** window of the definition's span |
| `span` | each target of a span anchor | every window covering lines L to M |
| `path` | each target of a path anchor | the file's source entry and its **outline**: the qualified names (Python), headings (Markdown) or table headers (TOML) with their line spans, at most `max_outline_entries` (200), with the overflow counted. A file of other text has an empty outline |
| `finding` | each resolved finding anchor | every matching record, in `findings[]` |
| `candidate` | `--candidate` | the change map `inputs.candidate.changes` (§4.1), with at most `max_candidate_paths` (100) paths |
| `codeowners` | any required path: anchored path, span and symbol paths, and candidate-changed paths | every `.github/CODEOWNERS` rule matching any of them, in file order, matched with GitHub's documented pattern rules. The last matching rule is the effective one |

`agents`, `security_gate`, `authority_order`, `codeowners` and the register rows of `adr` are core items, and count against `core_bytes`.

**`coverage.complete` has one meaning.** It is `true` when every obligation is satisfied, and only then.

- **A successful run always has `complete: true`.** A package with an unmet obligation is never produced: the run exits 4 or 6 instead, with a content-free diagnostic. That diagnostic lists the unmet obligations by kind and anchor text, with the bytes needed and available.
- **Completeness is not sufficiency.** It is never a claim that the package holds everything the task needs. The schema's description, the Markdown header and a fixed note all say so.
- **A task with no anchors and no candidate has only governance obligations.** `coverage.task_obligations` is then 0, and the Markdown header says that everything else was found by ranking.
- **A path is not a method.** A `path` obligation guarantees the file's identity and outline, not its content. The outline shows which definitions exist, the items show which windows were included, and the Markdown lists the rest. To require a method, anchor the method; to require lines, anchor the span.

**Why this contract (F-5).**

- **Revision 2 exited 0 with `complete: false`.** When a critical window was left out, it still emitted a package, marked INCOMPLETE.
- **Its "critical window" for an anchored path was that file's best-scoring window.**
  - At the baseline, for a store-level Forget task anchoring only `src/sovereign/store.py`, that window was `Vault._undecodable_text`.
  - `_forget_plan`, `forget_preview` and `delete` ranked 11th, 13th and 31st of 82, yet the package would have said `complete: true`.
- **Its symbol anchors resolved only in anchored paths.** So `Vault.delete`, written alone, generated nothing.
- **Its required-path shares were split evenly, but the critical windows were unbounded.** For T2, the 11 critical windows total 21,323 bytes against a 16,384-byte share, with no rule for what happens then (round-2 record, F-5).

### 5.5 Discovered evidence (F-5)

**Candidates.** Every window of an eligible blob that is not already mandatory: in the target tree, and in the candidate tree for candidate-changed paths.

**Links.** A candidate's **links** are the distinct reasons why the task points at it:

- `required_path`: it is in a required path (§5.4);
- `anchor:<value>`: it mentions a resolved anchor. That is the anchor's text as a standalone token for ADRs and findings, the `issue_or_pr` expression for issues, and the definition's last name component as an identifier for symbols;
- `candidate_change`: in candidate mode, it overlaps a changed line range of the candidate version;
- `path_term:<terms>`: its file name matches task terms (§5.1);
- `name_term:<terms>`: it is a Python definition whose last name component matches task terms.

**Score.** The distinct task terms in the window's text, plus the distinct task terms in its symbol or heading.

**Tiers.** The full set of links counts, for the tier and for the order, before any display limit. An item lists at most 8 reasons, with `reasons_total` giving the full number (§6.1).

A candidate with at least one link is `linked`. One with no link but a score above 0 is `related`. Anything else is not a candidate.

**Order:** `(tier, −links, −score, class rank, tree, path bytes, first line)`.

- `linked` sorts before `related`.
- Class rank follows §2.2's table.
- The target tree sorts before the candidate tree.

The order is total, so ties cannot depend on enumeration order.

**Fill.** R is the excerpt budget left after mandatory evidence.

1. **Quota passes, in this order:**
   - tests (`test_percent` = 15% of R);
   - source (`source_percent` = 35% of R);
   - decision and design documents (`docs_percent` = 25% of R). These are the classes `constitution_candidate`, `binding_decision`, `proposed_or_historical`, `adr`, `governance_doc`, `registry_fact`, `recorded_findings` and `builder_record`.

   Each pass walks the order and takes the windows of its classes that fit both its share and R, at most `per_file_windows` (3) per path.
2. **The global pass** walks the order and takes every remaining window that fits R, with no per-path limit.
3. **`max_items`** applies throughout.

The sequence of acceptances is the **acceptance order** used by §6. Windows not taken are `omitted`. Their count, by tier, and the first 20 in the order (path, commit, lines and tier) are listed, so an agent can read them in the repository.

**Why these signals.** A builder self-check on nine natural-language tasks at `3740119` asked for 26 sources the builder judged necessary (round-2 record, §6.1).

- **Before the name signals and the documents quota:** 15 of the 26 were found. Long prose windows won on raw term counts.
- **With them:** 22 of 26.
- **The four misses are lexical limits that V1 does not hide:**
  - `static/app.js`, UI code with no Python definitions;
  - `README.md`;
  - two SB-2b dependencies that the task never mentioned.

  Anchoring them delivers them.
- **No embeddings or code graph were needed for these gains.**

### 5.6 Findings

- **Mandatory:** every record matched by a finding anchor (§5.4).
- **Optional:** records whose `title` or `summary` shares a task term, ordered by (−shared terms, file path, `id`).
- **Limits:** at most 20 findings in all, mandatory ones first. More than 20 mandatory findings exit 4: they are obligations, and none may be dropped. Optional findings beyond the room are counted in `overflow.findings`. Each copied field is cut to 256 bytes on a character boundary, with `truncated: true`.
- **What is copied:** `id`, `severity`, `confidence`, `status` and `independent_disposition` (null if absent), verbatim, with the constant `attribution`. `builder_response` entries are not copied; the citation points to them.
- **Unreadable files:** a findings file that is not a JSON object with a `findings` list is listed in `missing` as `unreadable`.

### 5.7 Tests

**Which files.** For each required path that is a Python file under `src/`, its module name is the path without `src/` and `.py`, with `/` replaced by `.`. Test files under `tests/` are listed when their `ast` imports that module (`import m`, `from m import …`, or `from parent import leaf`).

**Which names.** The test functions (`test*`, top level or in a `Test*` class) whose name, split on `_` into terms (§5.1), shares a term with the task terms or with the anchored symbols' last name components.

**Limits.** At most 30 names per file, 60 names in all and 20 files, ordered by (−names, path).

**Commands.** Each file gets the suggested command `python -m pytest -q <path>`. The path is relative to the project root and quoted with `shlex.quote`. The command is never run, and the Markdown marks it as a suggestion.

### 5.8 Conflicts

V1 reports `decision_status` conflicts (§2.3), at most 20.

Revision 2's `stale_path` and `unknown_commit` checks are **withdrawn** to V1.1 (§15 D-7):

- **`unknown_commit` was nondeterministic.** It needed the object database, and when restated against the history set, it flags every mention of an unmerged branch's commit. This repository's documents routinely mention those.
- **`stale_path` flags every planned path.** This very specification names `devcontext/git.py`, for example.
- Both need evaluation before they are worth their noise.

## 6. Budgets, cardinality and finalization (F-7, F-10, F-15)

| Parameter | Default | Meaning |
| --- | --- | --- |
| `max_output_bytes` | 49,152 | the whole serialized output: the JSON object, and separately its Markdown rendering |
| `observation_bytes` | 512 | the fixed share of `max_output_bytes` kept for the observation envelope (§7.2). Canonical content must fit in the rest |
| `reserve_bytes` | 8,192 | kept for everything that is not an excerpt |
| excerpt budget | `max_output_bytes − reserve_bytes` | the UTF-8 bytes of all excerpts |
| `core_bytes` | 8,192 | the core's excerpts (§5.4). At the baseline, a task anchoring ADR-0003 needs 3,103 bytes, and the register rows naming ADR-0006 alone are 2,351 bytes |
| `source_percent`, `test_percent`, `docs_percent` | 35, 15, 25 | quota shares of R (§5.5) |
| `per_file_windows` | 3 | per path, in the quota passes |
| `max_items` | 40 | windows |
| `max_item_bytes` | 2,048 | one window |
| `max_file_bytes` | 262,144 | one blob read |
| `max_candidate_paths` | 100 | candidate-changed paths |
| `max_anchor_matches` | 4 | targets of one anchor that become obligations |
| `max_outline_entries` | 200 | outline entries per path |

**Only two parameters can be changed:** `max_output_bytes` and `max_items`, with `--max-output-bytes` and `--max-items` (§3). The others are fixed in V1 (D-4), and the schema holds each to its value. The limits of §6.1 are computed from those values, so they hold by construction: with `max_anchor_matches` at 16, for example, 32 anchors could need 517 obligations.

### 6.1 Cardinality and overflow (F-15)

**One rule for every collection.** Every decision is made on the **full logical set**: whether an anchor resolves, whether it is ambiguous, whether it generates obligations, and how a window ranks. Only then is the **display** bounded. A bounded display always carries the full count, so it can never make an anchor look unique, an obligation look met, or a constraint disappear.

| Field | Displayed at most | Beyond that |
| --- | --- | --- |
| `task.text` | 2,000 characters | exit 2 |
| `task.terms` | 64 | the rest is counted in `terms_omitted`; terms only score |
| `task.anchors` | 32 | exit 2: anchors carry obligations, so none may be dropped |
| `task.anchors[].targets` | 8 | `target_count` is the full number. Resolution and obligations use it: 0 is `unresolved`, 1 `resolved`, more `ambiguous`; obligations exist only when it is 1 to `max_anchor_matches` (4), so every obligation's targets are listed |
| `items[].reasons` | 8 | `reasons_total` is the full number. Tier and order use the full set of links (§5.5) |
| `items[].symbol`, outline names | 256 bytes, cut on a character boundary | `symbol_truncated`, and the outline's `names_truncated` count |
| `findings` | 20 | mandatory findings come first. More than 20 mandatory findings exit 4. Optional findings beyond the room are counted in `overflow.findings` |
| `tests` | 20 files, 30 names each, 60 names in all | `overflow.test_files` and `overflow.test_names` |
| `conflicts` | 20 | `overflow.conflicts` |
| `conflicts[].sides` | 16 | `sides_total` |
| `missing` | 64 | `overflow.missing` |
| `omitted.top` | 20 | `omitted.count`, with `linked` and `related` |
| `inputs.candidate.changes` | 100 | exit 4 (`max_candidate_paths`): the change map is mandatory |
| `inputs.candidate.changes[].changed` | 20 | `ranges_omitted` |
| `sources[].outline.entries` | `max_outline_entries` | `omitted` |
| `obligations`, `items`, `sources` | 200, 200, 512 | cannot be exceeded: 32 anchors × 4 targets, plus 5, gives at most 133 obligations; items are at most `max_items`; sources are at most 498 by the same arithmetic |
| a path | 512 bytes | the file is excluded (`unsafe_path`) |
| a status line | 512 bytes | `status_line_truncated` |
| a finding field | 256 bytes | the finding's `truncated` |
| notes | 3 fixed sentences | — |

`context-package.schema.json` uses exactly these limits, and `tests/test_builder1_spec.py` checks that the two agree.

### 6.2 Finalization, step by step (F-10)

**Order matters: canonical content is finished, and fingerprinted, before anything local is added.**

1. **Resolve the canonical inputs** (§4.1).
2. **Generate the candidates and the obligations** (§5).
3. **Mandatory evidence must fit.**
   - The core's excerpts must fit `core_bytes`.
   - All mandatory excerpts must fit the excerpt budget, and their windows `max_items`.
   - Otherwise the run exits 4, saying how many bytes and items are needed and available.
4. **Fill optional windows** (§5.5).
5. **Prune canonically.**
   - **Measure** the *canonical output*: the compact JSON of `{schema, fingerprint, package}`, with `fingerprint` as a placeholder of its fixed 71-character length. Measure also the *canonical rendering*: the Markdown without the observation block.
   - **Prune.** While either exceeds `max_output_bytes − observation_bytes`:
     - remove the optional window accepted **last** (§5.5's acceptance order), and add it to `omitted`;
     - rebuild the sources, ids and lists, and measure again.
   - **Stop.** Each pass removes one window, so the loop ends. Mandatory items are never removed. If none is left to remove and the bound is still exceeded, the run exits 4.
6. **Fingerprint** the package (§8).
7. **Add the observations** (§7.2) and serialize the final JSON (compact, sorted keys, `ensure_ascii=True`). Render the final Markdown, which is the canonical rendering with the observation block inserted (§7.4).
8. **Check the final bound.** Both outputs must be within `max_output_bytes`.
   - This holds by construction. Every observation field is bounded, so the observation member serializes to at most 226 bytes and the observation block renders to at most 201 bytes, both under `observation_bytes`.
   - A failure here would be a defect: the run exits 1 and never prunes canonical content.

**Why (F-10).** Revision 3 pruned until the *final* output fit, observations included. The same canonical package serialized to 49,152 bytes in a bare clone (`"none"`, `"bare"`) and to 49,158 in a work tree (`"clean"`, `"work_tree"`). At a 49,152-byte bound, only the work tree pruned a window, so two clones built different packages from the same inputs (round-3 record, F-10).

**No self-reference.** The fingerprint covers `package` only (§8), and its length is fixed, so measuring with a placeholder gives exactly the final size. The measured sizes are not written into the output. Tests measure them (AT-17).

## 7. Output

The output is one JSON object with four members, defined by [`context-package.schema.json`](context-package.schema.json), schema `sovereign.devcontext.v1`:

- `schema`;
- `fingerprint`;
- `package`, which is canonical (§7.1);
- `observations`, which are local (§7.2).

### 7.1 `package`: canonical and fingerprinted

| Field | Content |
| --- | --- |
| `task` | `text`, `terms`, `terms_omitted`, and `anchors` (each with `kind`, `value`, `resolution`, `targets` (at most 8) and `target_count`) |
| `inputs` | `project_root`; `target` (`commit`, `tree`); and `candidate`, which is null or holds `commit`, `tree`, `merge_base` and `changes` (`path`, `status`, `changed` [[first, last]…], `ranges_omitted`, `both_changed`) |
| `generator` | `name`, `version`, `selection_version`, `stopwords_sha256`, `python_grammar` |
| `parameters` | every value of §6 |
| `usage` | `excerpt_bytes`, `items`, `mandatory_bytes`, `core_bytes` |
| `authority_order` | null, or `item` (the core item holding the line) and `order` |
| `coverage` | `complete` (always `true` in a produced package), `obligations` (their count) and `task_obligations` (those from anchors or the candidate) |
| `obligations[]` | `id`, `kind`, `anchor`, `items` (the item ids that satisfy it), `sources` (the source ids that satisfy it: ADR status lines, outlines, findings files) |
| `sources[]` | one entry per cited file version, numbered `R1`… in order of first citation: items, then obligations, then findings, then tests, then conflicts. Each has `id`, `path`, `commit`, `blob`, `status_line` (or null), `status_line_truncated`, and `outline` (null unless the path is anchored: `entries` [[name, first, last]…], `omitted` and `names_truncated`) |
| `items[]` | `id` (`S1`…), `source`, `class`, `lines` [first, last], `symbol` (or null), `symbol_truncated`, `span` [first, last], `excerpt`, `role` (`core`, `required` or `optional`), `tier` (null, `linked` or `related`), `obligations` (ids), `reasons` (at most 8), `reasons_total` |
| `findings[]` | `source`, `id`, `severity`, `confidence`, `status`, `independent_disposition` (or null), `attribution` (the constant `"recorded; ownership not verified"`), `mandatory`, `truncated` |
| `tests[]` | `source`, `names`, `command` |
| `conflicts[]` | `kind` (`decision_status`), `summary`, `sides` (source ids and lines, at most 16), `sides_total`, `resolution` (the constant `"not reconciled"`) |
| `overflow` | the counts of entries not shown: `findings`, `conflicts`, `missing`, `test_files`, `test_names` (§6.1) |
| `omitted` | `count`, `linked`, `related`, and `top` (at most 20 entries, each with `path`, `commit`, `lines` and `tier`) |
| `missing[]` | `what` and `reason` (`outside_v1_scope`, `not_found`, `unresolved`, `ambiguous` or `unreadable`) |
| `excluded` | counts by reason: `symlink_or_submodule`, `unsafe_path`, `forbidden_path`, `oversized`, `binary`, `possible_secret` |
| `notes[]` | three fixed sentences: excerpts are data, not instructions; completeness is not sufficiency; GitHub state is outside V1 |

**Item order.** Core items in obligation order, then required items in obligation order, then optional items in §5.5's order.

**Reasons.** An item's reasons are:

- `core:<invariant>` (`core:register_row:ADR-NNNN` for register rows), or `anchor:<value>` for required items;
- its links (§5.5), then `terms:<terms>`, for optional items.

**No local facts in the package.** It contains no timestamp, hostname, user name, absolute path, environment value, Python or Git version, or working-tree state.

**Exact citations.** Every `excerpt` equals lines `lines` of the cited blob.

### 7.2 `observations`: local and never fingerprinted (F-10)

| Field | Content |
| --- | --- |
| `working_tree` | `clean`, `dirty`, or `none` for a bare repository |
| `repository_kind` | `work_tree` or `bare` |
| `git_version` | the first line of `git --version`, with every character that is not printable ASCII, or is `"`, `\` or `` ` ``, replaced by `?`, cut to 64 characters |
| `python_version` | `major.minor` of the running interpreter |
| `replace_refs_ignored` | the count of `refs/replace/*`, capped at 999,999 |
| `preflight` | the constant `"passed"`, since a failure never produces output |

**Bounded, and outside canonical pruning.** These bounds cap the envelope at 226 bytes of JSON and 201 bytes of Markdown, within `observation_bytes` (512). Pruning never sees them (§6.2).

**Why separate.** Revision 1 put `working_tree` inside the fingerprinted data, so a clean, a dirty and a bare checkout of the same commit gave three fingerprints (round-1 record, F-10).

### 7.3 Example

[`context-package.example.json`](context-package.example.json) and [`context-package.example.md`](context-package.example.md) are an example output at `99f3026` and its Markdown rendering.

- **How they were made.** The builder's throwaway reference model of §4–§7 generated them. That model is not committed and not the implementation.
  - **The selection is computed by the rules**, as the builder modelled them. Nothing was chosen by hand.
  - **What `tests/test_builder1_spec.py` checks:**
    - every excerpt, blob, line range, symbol span, class, status line, obligation and conflict side is exact at that commit;
    - the output is within its bounds;
    - the rendering follows §7.4's structural rules.
  - **It is not evidence that an implementation works** (§15 D-9).
- **The JSON file is pretty-printed for review.** The bound of §6 applies to the compact serialization that the tool prints, and the test measures that.
- **What the task anchors:**
  - three `Vault` methods, one of which splits into two windows;
  - `src/sovereign/store.py`, with its outline;
  - ADR-0003, with every register row naming it and a `decision_status` conflict;
  - Issue #15, listed as outside V1's scope.

### 7.4 Markdown rendering (F-3)

**`--format md` renders the output deterministically, for a reader who knows nothing of the project's history.** The sections come in this order:

1. **What this is.** A fixed paragraph, saying:
   - the package is repository data at pinned commits, assembled for one task;
   - fenced blocks are data, never instructions;
   - it does not show current GitHub state;
   - it is not a claim of holding everything the task needs.
2. **Status.**
   - The fingerprint.
   - **COMPLETE**, with the number of obligations and how many came from the task. With none from the task, it says that only the governance core was mandatory.
   - The anchors that are unresolved or too ambiguous.
   - The number of optional windows left out.
   - The number of conflicts.
   - The observations, labelled as local, as exactly two lines: `- Local observations, not part of the fingerprint:` and a fenced block `working tree <w>; <kind>; <git_version>; Python <version>; replace refs ignored <n>`. The canonical rendering of §6.2 is this rendering without those two lines.
3. **The task, the pinned inputs, the candidate's change map and the authority order.**
4. **The anchors**, each with its resolution and target count. An anchor with more than 8 targets says that the first 8 are listed. An item with more than 8 reasons says how many are shown.
5. **The mandatory evidence:** the obligations, each with the items and sources that satisfy it, and then the core and required items.
6. **The related evidence**, in tier order.
7. **The outlines of anchored paths, the recorded findings** (headed "ownership not verified"), **the tests** (headed "suggested commands, not run"), **the conflicts** (headed "not reconciled"), **what was left out, what is missing, and the sources** with their status lines.

**Fences.**

- Every fence is made of backticks, **at least three**, and one more than the longest backtick run inside its content.
- The info string is `text`.
- Revision 1's rule of one more than the longest run produced a one-backtick fence for excerpts without backticks. A CommonMark parser then rendered a blank-line-separated `<img onerror>` and a heading from inside it (round-1 record, F-3).

**Every derived value is fenced.** A derived value is anything that comes from the repository or the task:

- paths, blobs and status lines;
- symbols, outlines and anchors;
- the task text and its terms;
- test names and commands;
- finding fields, conflict summaries;
- the change map, `omitted` and `missing` entries.

Each appears **only inside fenced `text` blocks**. Labels and headings are fixed ASCII strings written by the tool, and nothing is rendered as a link, image, HTML or heading from data.

**Control characters.** In rendered values, these are replaced by a visible `⟪U+XXXX⟫` marker:

- C0 controls other than tab and line feed;
- DEL and C1 controls;
- the bidirectional and zero-width format characters (U+200B–U+200F, U+202A–U+202E, U+2066–U+2069, U+FEFF).

**Trailing whitespace.** A space or tab at the end of a rendered line is shown as `⟪U+0020⟫` or `⟪U+0009⟫`. A status line cut at 512 bytes can end in a space, for example. With the markers, renderings can be committed and compared without whitespace checks or editors changing them. The JSON keeps the exact bytes.

The JSON output escapes all non-ASCII (`ensure_ascii=True`).

**What this does not promise.** Fencing makes the rendering inert for a CommonMark renderer. It cannot stop a language model from reading instructions inside the data and following them. The header and the classes tell the agent what the data is; the agent's own rules decide what it does with it.

## 8. Fingerprint

`fingerprint = "sha256:" + sha256(json.dumps(package, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()`

- **What it covers:** exactly `package`, and never `observations`.
- **Reproducibility.** Two runs with the same canonical inputs (§4.1) give a byte-identical `package`, and so the same fingerprint, whatever the clone's location, kind, object store, refs or working-tree state, and whatever the supported Git and Python versions (AT-1).
- **It is not a disclosure token.** It approves nothing, and it is unrelated to the Context Compiler's `context_token` (§15 D-2).

## 9. Disclosure checks (F-2)

**What is checked.** The credential patterns are applied to every string that can enter the output:

- the task, which is refused before the run (exit 2) and never echoed;
- every excerpt, status line, outline entry and symbol;
- every path, test name and command;
- every finding field, conflict summary, change-map path, `omitted` path and `missing` entry;
- **the final serialized JSON and Markdown as a whole.**

**The patterns.** They are:

- a private-key header;
- the token prefixes `ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`, `github_pat_`, `sk-`, `AKIA` and `xox[abpr]-`, each followed by at least 16 token characters;
- `password`, `secret` or `token` assigned a quoted literal.

**How a prefix is matched.**

- **A prefix must not follow an ASCII letter or digit, but may follow `_` or punctuation.** Revision 1's `\b` failed after `_`, so a token inside `test_ghp_…` was missed (round-1 record, F-2).
- With no anchor at all, `sk-` would match inside `risk-management-framework` (`docs/SOURCE-NOTES.md:24` at the baseline).
- **At the baseline the patterns match two lines, both in tests:**
  - a synthetic `SECRET = "…"` assignment;
  - a `token="from-plan"` default argument.

  As optional windows they are withheld. In mandatory evidence they exit 6. Anchoring `ask()`, whose window holds that default argument, exits 6 (AT-5).
- The exact expressions belong to `selection_version`.

**Outcomes.**

| Match in | Result |
| --- | --- |
| the task | exit 2 |
| an optional window or finding | the whole entry is withheld, never masked, and counted in `excluded.possible_secret` |
| mandatory evidence | **exit 6**: it would otherwise be withheld |
| the final JSON or Markdown | **exit 6** |

**Limits, stated exactly.** The patterns detect only the listed credential formats. They cannot detect:

- private but non-secret text, such as a name, health detail or address;
- encoded, split or novel secrets;
- secrets in formats not listed.

They are a backstop behind the source restriction (§1), not a privacy control.

## 10. Failure behaviour

| Condition | Behaviour |
| --- | --- |
| Out-of-range argument; task too long, empty or with NUL; more than 32 anchors; credential pattern in the task | exit 2 |
| Not a Git repository; target or candidate unresolvable or ambiguous; no unique merge base; no unique project root (the one directory holding both `AGENTS.md` and `docs/SECURITY-GATE.md`); the `AGENTS.md` section or Security Gate line missing | exit 3 |
| An anchored path that is not readable (§4.4); the core over `core_bytes`; mandatory excerpts over the excerpt budget or `max_items`; more than 20 mandatory findings; candidate changes over `max_candidate_paths`; the canonical bound unmet with mandatory content only | exit 4 |
| A preflight condition (§4.2); Git older than 2.24; a Git limit (§4.3) | exit 5 |
| A disclosure match in mandatory evidence or in the final output (§9) | exit 6 |
| An unexpected exception; the observation envelope exceeding its reserve (impossible with the bounds of §7.2) | exit 1, with a fixed message |
| No authority-order line; no `.github/CODEOWNERS`; no findings file; no register | exit 0; `missing` |
| An unresolved or over-ambiguous anchor; an anchored issue or PR | exit 0; `missing`, and the header lists it |
| Optional windows that do not fit | exit 0; `omitted` |
| A `decision_status` mismatch | exit 0; `conflicts`, **never resolved** |

A `registry_vs_code` check, comparing `code_facts` with source parsed statically by `ast.literal_eval`, is left for V1.1 (§15 D-7), with the conflicts of §5.8.

## 11. Threat model

The repository is untrusted input.

| Threat | Example | Control | Test |
| --- | --- | --- | --- |
| Path traversal | `../../etc/passwd` in the task; a tracked symbolic link | Only tree entries are read, by blob id. Symbolic links and submodules are not followed. `--out` refuses existing paths, dangling links and the repository | AT-6 |
| Command execution through Git configuration | `core.fsmonitor`, textconv, external diff, hooks | Plumbing only, with the arguments and environment of §4.3, and no shell | AT-7 |
| Network through Git | a promisor remote without `extensions.partialClone`; lazy fetch; alternates on a network mount | Preflight refusal (§4.2); `protocol.allow=never` and `GIT_ALLOW_PROTOCOL=`; tested behaviourally | AT-7 |
| Spoofed history or content | grafts; replace refs; alternates | Grafts and alternates refused; `--no-replace-objects`; commit, tree and blob ids recorded | AT-7 |
| Local state changing the package | an unrelated dangling commit; extra refs; a dirty or bare clone | History-scoped resolution (§4.1); observations kept outside the fingerprint | AT-1 |
| Stale or misleading text | a branch named like a SHA; text claiming "merged" | Refs resolved once to SHAs. Text quoted with its class, never turned into state | AT-1, AT-8 |
| Hostile names and paths | paths with spaces, Unicode, controls or newlines | Unsafe paths excluded (§4.4); every derived value fenced, with controls marked | AT-6, AT-10 |
| Prompt injection through Markdown, code or review files | "ignore previous instructions"; a closing fence; HTML; links in paths | Every derived value fenced; controls marked; a header says the excerpts are data. No promise about a model's behaviour (§7.4) | AT-10 |
| Untrusted commands shown as context | a test path with shell metacharacters | Paths quoted with `shlex.quote`; commands fenced and marked "not run" | AT-10 |
| Poisoned review conclusions | a builder-written `*-findings.json` with a forged author, claiming F-7 closed | `recorded; ownership not verified`; fields verbatim; no closure wording; identity per file | AT-11 |
| Decision-scope inflation | an ADR treated as approved because a register row names it | Rows carried verbatim with their scope; ADR text stays `adr` | AT-19 |
| Context starvation | governance or prose crowding out the code and tests the task needs | Core cap; obligations; relevance with name and path signals; quotas; `omitted` listed | AT-15, AT-16 |
| Silent incompleteness | a required method that does not fit; a path standing in for a method | Unmet obligation means exit 4; outlines and `omitted` show what is absent | AT-16, AT-21 |
| Credential or private-text leakage | a token in a status line, test name, path or the task | Checks on every field and the whole output; exit 6 for mandatory matches; the source restriction for what patterns cannot see | AT-5 |
| Personal data | the vault path, a `*.db` file | `forbidden(path)`; no `sqlite3` or `sovereign` import; `SOVEREIGN_DB_PATH` never read | AT-12 |
| Unbounded work or output | a giant repository, blob or class; many tests, findings or changes | Tree, blob, time and output caps; per-field limits; windows | AT-3, AT-17 |
| Historical leakage in benchmarks | later commits present in a "fresh" clone | Bundle-based run environments, verified by `scripts/benchmark_freeze.py` (BENCHMARK-PLAN §4) | `tests/test_benchmark_freeze.py` |

## 12. Isolation, removal, rollback and use

- **A separate package.** V1 is a top-level `devcontext/` in the project directory, beside `evaluation/`. It is not part of the installed `sovereign` package (§15 D-3).
- **How to run it.** From a clean checkout, `cd "sovereign-os/sovereign-os 3"` and run `python -m devcontext …`. Python's `-m` finds the package in the current directory, and no installation, path setting or shell configuration is needed. A short usage guide comes with the implementation (§14).
- **Policy tests, added with the implementation:**
  - no `sovereign` module imports `devcontext`;
  - `devcontext` imports no `sovereign` module, no `sqlite3` and no network client;
  - its only subprocess call is the Git helper of §4.3.
- **No state.** It writes nothing except standard output or the one new file given to `--out`.
- **Removal.** Delete `devcontext/` and its tests. Canonical user state, Git, the Context Compiler, and the current Claude Code and Codex workflows are unaffected.
- **Rollback** is a revert of the implementation PR.

## 13. Acceptance tests for the implementation PR

They run the real command as a subprocess against synthetic repositories in temporary directories, local `file://` fixtures, and this repository at pinned commits. Internal helpers are tested in addition, never instead.

| ID | Requirement |
| --- | --- |
| AT-1 | **Determinism (F-10).** The same canonical inputs give a byte-identical `package` and fingerprint across all of these: a work-tree clone; a bare clone; a dirty work tree; a repacked clone; a clone at a path with spaces and Unicode; a clone with extra branches, tags, notes and replace refs; a clone holding an unrelated unreachable commit whose prefix the task names as a commit anchor; Python 3.11, 3.12 and 3.13, as available; and two runs. `observations` may differ. `--format md` is identical when the observations are equal |
| AT-2 | **Pinning.** A commit made after resolution changes nothing. A branch name records the resolved SHA |
| AT-3 | **Caps.** The tree, blob, time and per-call output caps exit 5 |
| AT-4 | **Citations.** Every excerpt equals its blob lines. Every `span` contains its `lines`, and a Python symbol is the `ast` qualified name at that span |
| AT-5 | **Disclosure (F-2).** Planted synthetic tokens never appear in either output format, including `test_ghp_…`, a private-key header and a `password = "x"` assignment, whether in a status line, test name, path, outline, finding or excerpt. A token in the task exits 2 without echo. A match in mandatory evidence exits 6, as does anchoring `ask()` at `3740119`. A final-output match exits 6. Forbidden paths are not read, which is checked by blob-read accounting |
| AT-6 | **Paths and output.** Symbolic links and submodules are not followed. `../` in the task is an unresolved anchor. Paths with controls are excluded. `--out` refuses an existing file, a dangling link, a missing parent and the repository, and leaves nothing behind on failure |
| AT-7 | **Git trust (F-1).** Each of these exits 5 before any blob is read: a `file://` partial clone (`remote.origin.promisor=true`, with **no** `extensions.partialClone`); `extensions.partialClone` alone; a `*.promisor` pack; alternates; `info/grafts`; a shallow clone; a Git older than 2.24 (simulated). With the preflight bypassed in the test, `protocol.allow=never` leaves a promisor-missing object missing. Hostile `core.fsmonitor`, textconv and hooks run no program. A replace ref does not change the content read. Git's standard error never appears |
| AT-8 | **Status.** At `99f3026`, a task anchoring all seven ADRs reports `decision_status` conflicts for exactly ADR-0003 and ADR-0004, with verbatim sides, and no summary saying that an ADR is approved or binding |
| AT-9 | **Anchors.** At `99f3026`, `#15` resolves through exactly `docs/adr/0006-rowid-free-canonical-tables.md:60`, `docs/architecture/systems-registry.toml:57` and `docs/reviews/2026-10-22-pr10-audit-remediation.md:116`. Two findings files that both contain `F-1` give two targets. `README.md` resolves to the project README. `ask()` is a symbol anchor. A 7-hex prefix of a commit outside the history set is unresolved |
| AT-10 | **Inert rendering (F-3).** Structural checks: every fence has at least three backticks and is longer than any inner run, and every derived value occurs only between fence lines. A CommonMark parser (test-only, §15 D-12) confirms that fixtures render no HTML, link, image or heading outside fences. The fixtures are: no backticks; a blank line followed by `<img onerror>`; a path containing `](javascript:…)<img>`; a test path with `$(…)`. Control and bidirectional characters appear as markers |
| AT-11 | **Recorded findings (F-4).** A builder-written `*-findings.json` with a forged author keeps `attribution: "recorded; ownership not verified"`, with its fields copied verbatim. `accepted` together with `deferred_with_reason` is not presented as closure. No output contains "closed" or "resolved" about a finding, except inside a verbatim field |
| AT-12 | **Isolation.** The policy tests of §12 |
| AT-13 | **Removal.** With `devcontext/` deleted, `pytest -q` passes |
| AT-14 | **Schema.** Every output validates against `context-package.schema.json` |
| AT-15 | **Ranking (F-5).** At `3740119`, the nine natural-language tasks of the round-2 record, §6.1, include the sources that record lists as found. Relevant tests that rank below documents still enter through the test quota. Quotas and the per-file limit hold |
| AT-16 | **Windows and completeness (F-5, F-6).** A task anchoring `Vault.delete` and `Vault._forget_plan` includes every window of both, and `_forget_plan` (2,104 bytes) is split into two. With a budget too small for them, the run exits 4 and names both anchors, with the bytes needed and available. A method outside the first 2 KiB of its class is delivered whole |
| AT-17 | **Output bound and finalization (F-7, F-10).** For every fixture, the JSON and the Markdown are each at most `max_output_bytes`, and the limits of §6.1 hold. The shrink loop removes in reverse acceptance order and measures canonical content only. Boundary fixtures, including a package whose final JSON is 49,152 bytes in a bare clone and 49,158 in a work tree, give byte-identical packages, fingerprints, optional selections and `omitted` lists across bare, clean and dirty clones, Git version strings of 18 to 64 characters, checkout paths, and extra objects and refs. A fixture whose mandatory content alone exceeds the canonical bound exits 4 |
| AT-18 | **Candidate (F-8).** For T2's commits: `merge_base` is `8ea54b5`; the change map has the 11 candidate paths, with changed line ranges; `both_changed` is set exactly for `SECOND-BRAIN-VALIDATION.md`; and candidate items cite `59272b8`. An ambiguous merge base exits 3. More than `max_candidate_paths` changed paths exits 4 |
| AT-19 | **Decision scope (F-4).** At `99f3026`, a task anchoring ADR-0005 carries every register row naming it, verbatim. No field presents D15 text as approved |
| AT-20 | **Old commits (F-8).** At `eeed753` (T1's start), a run succeeds, with `authority_order: null` recorded in `missing` |
| AT-21 | **Obligations (F-5).** Each of these gives its documented result: a missing method (unresolved, exit 0); methods over budget (exit 4); several ADRs over `core_bytes` 4,096 (exit 4), and the same task at 8,192 (exit 0); a task with no anchors (`task_obligations` 0, and the header says so); a path anchor (an outline, with no claim about methods); mandatory evidence matching a pattern (exit 6). No produced package has an unmet obligation, which is checked by recomputing every obligation from the output |
| AT-22 | **CLI.** `--help` documents every argument, limit and exit code. Standard output, `--out`, JSON and Markdown all work from the project directory of a clean checkout. Every exit code is reachable and prints nothing on standard output |
| AT-23 | **Cardinality (F-15).** An anchor matching 17 definitions is `ambiguous`, has `target_count` 17, lists 8 targets, and generates no obligation. A window linked to 9 findings ranks by all 9 links, and lists 8 reasons with `reasons_total` 10. The same holds, bounded, with 1,000 matches and 1,000 links. Every output validates against the schema |

## 14. Minimal implementation plan

This is for a separate PR, after the decisions in §15. The pipeline has one function per stage, each with an explicit contract and its own failure codes:

1. **Validate** the arguments and the task (§3) → exit 2.
2. **Preflight** the repository (§4.2) → exit 5. Resolve the commits, the merge base and the project root (§4.1) → exit 3.
3. **Read:** trees, eligibility, lines, chunks and windows (§4.4, §4.5, §5.3).
4. **Parse the task:** terms and anchors (§5.1, §5.2).
5. **Build the obligations** (§5.4) → exit 4. Check disclosure on mandatory evidence → exit 6.
6. **Select** optional evidence (§5.5), findings, tests and conflicts (§5.6–5.8).
7. **Bound** the output (§6) → exit 4. Run the whole-output disclosure check → exit 6.
8. **Fingerprint and render** (§7, §8), and write the output.

**Modules:**

- `devcontext/git.py`: the preflight and the hardened helper;
- `devcontext/read.py`: steps 3 and 4;
- `devcontext/select.py`: steps 5 and 6;
- `devcontext/disclose.py`: §9;
- `devcontext/package.py`: steps 7 and 8;
- `devcontext/render.py`: §7.4;
- `devcontext/__main__.py`: the command-line interface.

**Also delivered:**

- AT-1 to AT-23 and the policy tests;
- a usage guide (`devcontext/README.md`) covering requirements, the commands, pinning, candidates, labels, refusals, limits, the separate GitHub-status handoff, removal, and how to reproduce the demonstrations;
- three demonstration packages of real tasks (the store and Forget, SB-2a provenance, SB-2b planning), each checked against the source.

**Constraints:** no new runtime dependency, no change under `src/sovereign/`, and no workflow change except, if the founder wants it, `compileall` of `devcontext`.

## 15. Decisions required before implementation

| ID | Decision | Recommendation |
| --- | --- | --- |
| D-1 | **Scope:** V1 as specified: local, read-only, deterministic, Git objects only, with the authorized-source restriction of §1 | Approve |
| D-2 | **Reuse of the production Context Compiler.** BUILD §5.6 says Builder 1 "reuses `build_bundle`, `render_messages` and the token". Their contracts encode personal-memory roles, sensitivity, cloud disclosure and a disclosure-approval token | Reuse none of them. Amend §5.6 (§16) |
| D-3 | **Location and command** | `devcontext/` in the project directory, run as `python -m devcontext`; the `sovereign dev context` alias when a `sovereign` command exists |
| D-4 | **Budgets:** the defaults of §6 | Approve as starting values; revisit with evidence |
| D-5 | **GitHub snapshots** (§2.5) | Defer |
| D-6 | **Development vault** (§2.4) | Defer; a separate ADR |
| D-7 | **The `registry_vs_code`, `stale_path` and `commit_not_in_history` checks** (§5.8, §10) | V1.1, after evaluating their noise |
| D-8 | **Dirty work tree:** observe it, or refuse it | Observe (§7.2) |
| D-9 | **Review tier of the implementation PR** | Tier 2, with an independent reviewer artifact. Its acceptance rests on the real command and AT-1 to AT-23, never on this example |
| D-10 | **The benchmark protocol and its parameters** ([BENCHMARK-PLAN.md](BENCHMARK-PLAN.md) §5 phase L0, §11) | Approve the protocol before implementation. Its run inputs are frozen only after the implementation exists (phase L3) |
| D-11 | **Verifying findings ownership:** signed commits or tags by a configured reviewer key | Defer. V1 labels every finding as recorded and unverified |
| D-12 | **A CommonMark parser as a test-only dependency** for AT-10 | Use `markdown-it-py` in the `dev` extra only, as a test tool. The structural checks always run as well |
| D-13 | **Supported environment** (§1): Linux and macOS, CPython 3.11–3.13, Git 2.24 or later | Approve; Windows later if needed |

## 16. Follow-up reconciliation

This branch changes no shared governance document. PR #21 merged on 2026-11-03 (`3740119`), so these edits no longer conflict with it. They wait for the founder's decisions. Then one documentation change should:

- **BUILD §5.6:** replace the reuse sentence (D-2), and state V1's scope and the deferred development vault.
- **ROADMAP §H, Builder 1 row:** on `main` at `3740119` the row still lists "SB-2a demonstrated useful; first-use trial" as its dependency. The founder relaxed the SB-2a dependency for the specification only (Issue #22). SB-2a has merged. Implementation waits only for the founder's approval of this specification, its decisions (§15) and the benchmark *protocol* (BENCHMARK-PLAN §5, phase L0). It never waits for the benchmark *freeze*, which needs the implementation's own commit (phase L3), or for benchmark results.
- **The registry:** a `builder-1-devcontext` entry, with status `approved` on approval and `implemented` with the implementation.
- **`docs/DEVELOPMENT.md`:** mention the package in *Canonical context and handoff*, after the benchmark.
