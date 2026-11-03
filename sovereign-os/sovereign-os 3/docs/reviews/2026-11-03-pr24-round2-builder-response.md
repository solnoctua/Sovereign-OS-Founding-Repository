# PR #24 second independent review: builder response record (round 2), 2026-11-03

**Status:** builder-authored evidence, by `owlbuilder`.

- **What this is not.** It is not an independent review, not a findings artifact, and not the review itself.
- **The review.** The second independent Codex review of the specification, at `a03c5245e3adfa092a033d80050e3eba2ac10b41`, returned CHANGES REQUIRED. The founder relayed it in a directive of 2026-11-03:
  - **Accepted:** F-1 to F-4 and F-6 to F-9.
  - **Partly resolved:** F-5 and F-10, each with a remaining P2 defect.
  - **New:** F-11, a P1 benchmark-commitment and freeze-order defect.
- **The reviewer-owned artifacts are not in this repository, and the builder has not seen them.** That includes the reviewer's local commit `2bc2daa`, which was not pushed. No ref holding `2bc2daa` exists on the remote.
  - Each **Relayed** paragraph below quotes the founder's directive. It is not the reviewer's text.
  - The accepted status of F-1 to F-4 and F-6 to F-9 is the relay's statement, not this record's.
- **No finding is closed by this record.** Every response below is pending an independent disposition.

**Environment:**

- the reviewed head `a03c524`, the specification's baseline `99f3026`, and `main` at `3740119`;
- Git 2.43.0;
- Python 3.13.18 and 3.12.3. Python 3.11 is not installed here;
- synthetic repositories in a scratch directory, and no real personal data.

**Method.** The founder asked for each defect to be resolved at its cause, not patched where an audit points.

1. **Reproduce first.** Each defect was reproduced against revision 2 before any correction was written.
2. **Design from first principles.** The coverage, determinism and commitment contracts were redesigned.
3. **Check the design against the data.** The builder wrote a **throwaway reference model** of revision 3's rules and ran it on real tasks. It is not committed and is not Builder 1. It was used to:
   - find ambiguities in the written rules;
   - evaluate selection on natural-language tasks;
   - test determinism across clones and interpreters;
   - generate the specification's example.
4. **Write the specification last**, together with the schemas, example, tests and the freeze verifier.

## F-5 (P2 remaining): one coverage contract

**Relayed:** "The current specification has inconsistent or insufficiently precise meanings for: Required paths. Required symbols. Critical windows. Required line ranges. Coverage completeness. Partial coverage. Optional truncation. Output validity. Success and failure." … "If essential evidence is absent or cannot fit: Do not mark the package complete. … Do not emit a success result that an agent is encouraged to treat as qualified when it lacks critical evidence."

**Reproduced against revision 2.** The first two items are the specification's own text at `a03c524`; the rest were computed with a model of revision 2's rules.

1. **An incomplete package was a success.**
   - §5.4, line 351: when a critical window was left out, `coverage.complete` became `false` and the Markdown said INCOMPLETE.
   - §10, line 570, gives no exit code for it. §3's exit-code table (lines 168–173) has no code for it either, so the run exited 0.
2. **Symbol anchors resolved only inside anchored paths** (§5.1, line 275). `Vault.delete`, written alone, generated nothing, and the package was trivially complete.
3. **A path stood in for its methods.** For a path anchor without a symbol, the critical window was the file's best-scoring window (line 341).
   - **The task:** "Forget fails when stored text in src/sovereign/store.py is not valid UTF-8", at `99f3026`.
   - **The best window** of `store.py`'s 82 windows was `Vault._undecodable_text` (lines 979–995, score 4).
   - **The Forget methods ranked** 11th (`_forget_plan`), 13th (`forget_preview`) and 31st (`delete`).
   - **Yet revision 2 would have reported `complete: true`.**
4. **Critical windows had no bound.** Revision 2 split `required_bytes` evenly, with no rule for critical windows larger than a share (line 346).
   - For T2, 11 required paths share 16,384 bytes, or 1,489 bytes each.
   - Their critical windows alone total 21,323 bytes.
   - What happens then was undefined.
5. **The module-header chunk was not contiguous.** "The module header (docstring and top-level statements outside definitions)" is not a contiguous range. A model that took it literally built one chunk from line 1 to the end of `store.py` and cited windows inside other definitions.

**Correction (`SPEC.md` revision 3):**

- **§5.4: three kinds of evidence.**
  - Mandatory core.
  - Mandatory task obligations, generated from resolved anchors and the candidate.
  - Optional discovered evidence.
- **Each obligation kind says exactly what satisfies it.** A `symbol` obligation needs every window of the definition. A `path` obligation needs the file's identity and outline, never a stand-in method. A `span` obligation needs every window of its lines.
- **`coverage.complete` has one meaning:** every known obligation is satisfied.
  - A run with an unmet obligation produces nothing and exits 4, or 6 if disclosure blocks it, with a content-free diagnostic that does the byte arithmetic.
  - So a produced package always has `complete: true`.
  - **Completeness is stated as not being sufficiency.** The schema, the Markdown header, a fixed note and AT-21 all say so.
  - `task_obligations: 0` says when only the governance core was mandatory.
- **§5.2: anchors.**
  - Symbols resolve across the target's Python files, with `ast`.
  - Span anchors (`path:L-M`) give "required line ranges" a meaning.
  - A bare identifier containing `_` is an anchor only when it names a definition.
  - An anchor with up to 4 targets makes each target an obligation. Beyond 4 it is listed as ambiguous.
- **§5.3: every chunk is contiguous.**
- **§5.5: optional evidence** has tiers, links, a total order, quotas, a per-file limit, and an `omitted` list.
- **§6:** the accounting.
- **§10:** the failure table, now complete.
- **§13:** AT-16 and AT-21.
- **The schema:** `coverage.complete` is the constant `true`; `obligations[]`; items with `role`, `tier` and `obligations`.

**The difficult cases the founder listed, run through the model** at `3740119` unless stated:

| Case | Result |
| --- | --- |
| A missing method (`Vault.frobnicate`) | The anchor is unresolved, listed in `missing`, exit 0. Nothing is invented |
| Eight methods over a 16 KiB output | exit 4: "mandatory evidence needs 20214 bytes and 18 items; the excerpt budget is 8192 bytes and 40 items" |
| One method over several windows | `Vault._forget_plan` (2,104 bytes) becomes two windows, both mandatory |
| A method outside the first 2 KiB of its class | Delivered whole (`Vault.import_untrusted`, `Vault._validity_findings`) |
| Four ADRs anchored with `core_bytes` 4,096 | exit 4, "governance core needs 4425 bytes". At the default 8,192: exit 0 |
| No anchors | `task_obligations: 0`, and the header says that only the core was mandatory |
| Candidate changes across many files | T2's 11 changed paths are obligations through the change map. More than 100 paths exits 4 |
| Tests that rank below documents | The test quota and the name signals deliver them (`test_provenance.py`, `test_schema_v5_migration.py`) |
| A source made important by a candidate diff | `candidate_change` links windows that overlap the changed lines |
| Mandatory evidence matching a pattern | Anchoring `ask()`, whose window holds `token="from-plan"`, exits 6 |

**Tests.**

- `test_example_citations_symbols_classes_and_obligations_are_exact_at_the_pinned_commit` recomputes every obligation of the example from Git: the `AGENTS.md` section, the Security Gate line, the authority line, every window of each symbol, the outline, every register row naming the ADR, and the CODEOWNERS rules.
- The schema test shows that `complete: false` is rejected.

**What remains uncertain:**

- Completeness is only as strong as the anchors a task gives. Lexical selection still misses some sources (§6.1 below).
- The model is unreviewed. AT-21 must establish the behaviour on the real implementation.

## F-10 (P2 remaining): reproducibility

**Relayed:** "The system is supposed to generate the same canonical context from the same declared inputs. That guarantee must remain true regardless of irrelevant local repository state." … "The presence of an unrelated object must not change an anchor from unresolved to resolved."

**Reproduced against revision 2:**

1. **Commit anchors read the object database.** Revision 2 resolved them with `cat-file -e` (§5.1, line 276).
   - **Setup:** clone `a` of a synthetic repository; clone `b` holds one extra unrelated, dangling commit. The task names that commit's prefix.
   - **`cat-file -e <prefix>^{commit}`:** unresolved in clone `a`, **RESOLVED** in clone `b`. The package, and so the fingerprint, differ.
   - **The history rule** (`rev-list` of the target) finds 0 matches in both.
2. **The grammar followed the interpreter.** A blob containing `def f[T = int](x: T) -> T:` raises `SyntaxError` under Python 3.12.3, so it would be cut into text windows. Under 3.13.18 it parses into the definitions `f` and `g`. With `feature_version=(3, 11)`, both raise `SyntaxError`.
3. **Line splitting was unspecified.** On a synthetic text, `split("\n")` gives 3 lines and `str.splitlines()` gives 5. No baseline blob differs between the two rules, so this was a latent ambiguity.
4. **The forbidden-path predicate's source was unspecified.**
   - The model first imported it from the repository's work tree, and failed on a bare clone, which has none.
   - Reading it from the target commit would also let that commit change the rule that protects it.
5. **Ordering and shrinking were underspecified.**
   - Ties between the target and candidate versions of a path had no rule.
   - "Remove the lowest-ranked optional window" was ambiguous once quotas exist.

**Correction (`SPEC.md` revision 3):**

- **§4.1:** the canonical inputs are listed exhaustively. Everything else is shown to be derived through content addressing.
- **§4.1 and §5.2: resolution is history-scoped.** Commit anchors resolve only against the history set from `rev-list`.
- **§4.5:** lines split on LF only, and the Python grammar is pinned to 3.11.
- **§4.4:** the forbidden-path predicate is the one shipped with the running tool.
- **§5.5:** the order is total, including the tree.
- **§6:** shrinking removes in reverse acceptance order.
- **§7.2:** `python_version` is an observation.
- **AT-1** is extended to cover the clone variants below.

**Shown with the model.** The same task (naming `#15`, `Vault.delete` and the 10-character prefix of an unrelated commit) at `3740119` gave the identical fingerprint, `sha256:e0e343b22cade163…`, in six runs: under Python 3.13.18 and 3.12.3, in each of these:

- the original repository;
- a clone that was dirty and repacked, at a path with spaces and `ünï`, holding an extra branch, a notes ref and the unrelated commit;
- a bare clone.

The commit anchor was unresolved in every run.

**What remains uncertain:**

- A pathologically nested file that one supported interpreter parses and another rejects would still diverge (§4.5).
- Python 3.11 was not available here to test.

## F-11 (P1, new): the benchmark commitments were cyclic

**Relayed:** "The benchmark currently contains contradictory freeze-order rules and hash dependencies that cannot be executed reproducibly." … "A bundle must not include the manifest whose hash refers to that same bundle. A gold sheet must not hash itself. A task manifest must not require the hash of an artifact that cannot exist until after that same manifest is committed."

**Reproduced against revision 2:**

1. **The gold sheet and the manifest committed to each other.**
   - `gold-sheet.schema.json` required `manifest_sha256` and `written_before_packages`.
   - `benchmark-tasks.json` carried `gold_sheet_sha256`, `hidden_tests_sha256` and `environment.bundle_sha256` for each task.
2. **A manifest inside its own bundle cannot converge.** Revision 2's plan froze "the manifest" with "the bundle's hash" (BENCHMARK-PLAN §5, lines 130–136), in this repository. T3's target is `main` at or after `3740119` (line 99), so T3's bundle would contain the manifest.
   - **Reproduction:** in a synthetic repository, a manifest recording the bundle hash was committed, and the bundle of that commit was rebuilt, three times. Each attempt recorded the previous hash and produced a new one (`71ed2ce3a37f`, `2af0d9db234b`, `b6c3b182e388`). A file cannot contain the hash of a bundle that contains it.

**Correction:**

- **`BENCHMARK-PLAN.md` revision 3:**
  - **§3.2:** the task plan holds no hashes, and a **detached freeze manifest** commits to the inputs.
  - **§4:** bundle-built workspaces, verified before each run.
  - **§5:** the 13-step commitment order as a dependency table, with the reasons it is acyclic, what `verify` refuses, held-out handling and re-freezing.
  - **§7.1:** qualification before trusted use.
- **The task plan and schemas:**
  - `benchmark-tasks.json` v3 has no hash fields.
  - `benchmark-freeze.schema.json` is new.
  - `gold-sheet.schema.json` loses `manifest_sha256`.
  - `benchmark-run.schema.json` gains `freeze.manifest_sha256` and `freeze.valid`.
- **`scripts/benchmark_freeze.py`** (standard library and `git`) has three commands:
  - `bundle`: exactly the pinned commits, under temporary branch refs that are then deleted;
  - `manifest`: the input and bundle hashes, the tool and protocol commits, and an arm assignment that follows from the input hashes;
  - `verify`: the inputs, the bundles, the acyclicity, and an agent's workspace.
- **`tests/test_benchmark_freeze.py`** (13 tests) runs the freeze sequence end to end on synthetic artifacts. Each failure case is refused:
  - an input changed or missing;
  - a bundle with a later commit, or an incomplete one;
  - a freeze manifest, or an input, stored in the source history;
  - an edited arm assignment;
  - an unreachable later object, or a fetched later commit, in the workspace;
  - a hidden test or gold sheet copied into the workspace;
  - alternates, or a remote, in the workspace.

**Erratum to the round-1 record (F-9).**

- **The round-1 reproduction of bundle isolation was vacuous.** It bundled `refs/tmp/bench-start`. A plain clone fetches only `refs/heads` and `refs/tags`, so its clone held **0 objects**, and every absence check passed trivially. Repeated today with that method, the clone again holds 0 objects, and the start commit is missing.
- **Repeated correctly,** with `scripts/benchmark_freeze.py bundle` on the real repository, the clone of T1's start holds 849 objects. All are reachable from the start commit, which is present, and `8ea54b5` and `99f3026` are absent.
- **The conclusion of round 1 holds, but its evidence did not.**
- **The verifier now prevents a repeat:** it fails when a pinned commit is missing from a clone, so an empty clone cannot pass.
- An erratum note has been added to the round-1 record.

**What remains uncertain:**

- Hash checks cannot detect a modified copy of a private file in a workspace.
- A model's training data may contain later history.
- The publication channel for the manifest hash is the founder's decision (BENCHMARK-PLAN §11, decision 10).

## Problems found in the builder's own review

The founder asked for defects to be found before the next independent review. These were found in this round and corrected in revision 3. None is claimed to be independently confirmed.

1. **The project root was undefined, though the class rules depend on it.** It is now the one directory holding both `AGENTS.md` and `docs/SECURITY-GATE.md`. Otherwise the run exits 3.
2. **Path anchors had no tokenization rule.** The model resolved `README.md` to the repository-root README. Resolution now tries the project-relative path first.
3. **`name()` anchors were lost.** Stripping trailing punctuation turned `ask()` into `ask(`. A final `()` is now kept.
4. **`excerpt_truncated` had no stated use** once chunks are windowed. It is removed: every excerpt is exact, and a line longer than a window is admitted only as mandatory evidence.
5. **`stale_path` and `unknown_commit` were nondeterministic or noisy.**
   - The commit check read the object database.
   - Restated against history, it flags every mention of an unmerged branch's commit.
   - The path check flags every planned path.
   - Both are withdrawn to V1.1 (§5.8, D-7).
6. **Test names were unbounded, and suggested commands were unquoted.** Names are now capped at 60 in all, and commands are quoted with `shlex.quote` and marked "not run".
7. **`--out` was underspecified.** Dangling links, missing parents and partial writes are now defined (§3).
8. **There was no internal-error exit, and failures had no stdout rule.** Exit 1 is added, and nothing is printed on any failure.
9. **The supported environment was unstated.** It is now Linux and macOS, CPython 3.11–3.13 (`requires-python >=3.11`) and Git 2.24 or later (D-13).
10. **More than 32 anchors were silently dropped**, and dropped anchors meant dropped obligations. Such a task now exits 2.
11. **The benchmark's bundle refs were outside `refs/heads`.** That is the vacuity above.
12. **D-12** now follows the founder's direction: a CommonMark parser as a test-only tool.

## Selection on natural-language tasks

**What was asked and how it was checked.** The founder asked whether lexical selection finds what tasks need, before anything heavier is added. The model was run at `3740119` on nine tasks, one per area the founder listed, all written in natural language. The builder listed 26 sources that it judged each task needs; this is a builder self-check, not a gold sheet.

**Before the name signals and the documents quota: 15 of 26 found.** Long prose windows won on raw term counts.

**Three deterministic signals were added:**

- a bare identifier containing `_` that names a definition is an anchor;
- **path terms:** task terms in a file's name;
- **name terms:** task terms in a Python definition's name, matched on their first 6 characters.

Adding them first starved documents (ADR-0006 dropped out). A documents quota and a per-file limit then restored balance.

**After: 22 of 26 found.**

| Task | Found | Missed |
| --- | --- | --- |
| Schema migration | `Vault._migrate`, `test_schema_v5_migration.py`, ADR-0006 | — |
| Context Compiler invariants | `context.py` (`build_bundle`, `_token`), its adversarial tests, ADR-0004 | — |
| Provenance UI (`.` and `..` IDs) | `provenance.py`, `test_provenance.py` | `static/app.js` |
| SB-2b Obsidian export | `OBSIDIAN-PROJECTION.md` | `SECOND-BRAIN-VALIDATION.md`, `provenance.py` |
| Import bounds (security) | `Vault.import_untrusted`, `app.py` | — |
| A named failing test | the test itself (anchored by its name), the Forget methods | — |
| Server-address documentation | `SECURITY-GATE.md`, `app.py` | `README.md` |
| ADR-0005 scope | the ADR, and the three register rows | — |
| SB-2a candidate integration | `provenance.py`, `test_provenance.py`, `app.py` | — |

**The four misses are lexical limits:**

- `static/app.js` is UI code with no Python definitions;
- `README.md` shares few terms with the task;
- the two SB-2b dependencies were never mentioned in the task.

**Anchoring each one delivers it,** through a `path` obligation and linked windows. V1 states these limits rather than hiding them. No embeddings or code graph were needed for the gains above.

## Verification

**Tests:**

| Check | Result |
| --- | --- |
| `pytest -q`, Python 3.13.18 | 814 passed |
| `pytest -q`, Python 3.12.3 | 814 passed |
| `tests/adversarial` | 630 passed |
| `tests/test_builder1_spec.py` | 14 passed |
| `tests/test_benchmark_freeze.py` | 13 passed |
| Mutation checks on the spec tests | every planted defect detected |

The CI result for the pushed head is reported on PR #24.

**Accepted areas that revision 3 touches.** These changes need the reviewer's fresh look:

- **F-6:** the windowing rules, in §5.3.
- **F-7:** the bound and its shrink order, in §6.
- **F-8 and F-9:** the task plan and the benchmark protocol.

## What this record does not do

- It does not close, accept or disposition any finding, and it does not reproduce any reviewer-owned artifact.
- It does not implement Builder 1. The reference model is a throwaway analysis aid, and it is not committed.
- It does not change `src/`, CI, rulesets or any shared governance document.
