# PR #24 Codex Tier 2 audit: builder response record, 2026-11-03

**Status:** builder-authored evidence, by `owlbuilder`.

- **What this is not.** It is not an independent review, not a findings artifact, and not the audit.
- **The audit.** An independent Codex Tier 2 review of the Builder 1 specification at `ed7776d26fbcdf147e60e642f43c87c4eec2b3ba` returned CHANGES REQUIRED: nine P1 findings and one P2, no P0. The founder relayed it on PR #24 (comment of 2026-11-03 08:43 UTC).
- **The reviewer-owned artifacts are not in this repository, and the builder has not seen them.** They are the report, the findings JSON, the evidence bundle and the benchmark-run template.
  - Under `docs/engineering/FINDINGS-FORMAT.md`, they are recorded by the reviewer or the founder, never paraphrased into a findings file by the builder. This record therefore creates no findings file.
  - The finding IDs below are the audit's. Each **Relayed** line quotes the founder's relay. It is not the reviewer's text.
- **No finding is closed by this record.** Every response below is pending an independent disposition, which the reviewer records in its own artifact.
- **A missed input.** The founder's benchmark protocol addendum to Issue #22 (2026-11-02 23:38 UTC) was posted before PR #24 opened. Revision 1 missed it. Revision 2 adopts it, under F-9.

**Environment:**

- the audited head `ed7776d` and the baseline `main` `99f302637d95f3d78cdd26a9f75d7a8ca336be99`;
- Git 2.43.0 and Python 3.13.18;
- for F-3 only, markdown-it-py 3.0.0 in a throwaway environment. It is not a dependency of anything;
- synthetic repositories in a scratch directory, and no real personal data.

**Method.** Each finding was reproduced against revision 1's rules before its correction was written, in one of three ways:

1. synthetic Git fixtures (F-1, F-4);
2. literal models of revision 1's rules (F-2, F-3, F-5, F-6). These are throwaway scripts: not committed, and not Builder 1;
3. Git objects at the pinned commits (F-6 to F-10).

The commands and their observed output are summarized under each finding.

## F-1 (P1): untrusted Git states and the network

**Relayed:** "partial-clone detection insufficient (effective promisor remote configuration, upstream Git 2.43 lazy fetch), graft ancestry changes, unreviewed alternates; harden trusted-clone/environment boundary, disable or reject network-capable and untrusted Git states, enforce subprocess limits and content-free errors. Do not claim a Python socket monkeypatch controls Git."

**Reproduced** with Git 2.43.0, a local `file://` server and synthetic blobs:

| Case | Setup | Observed |
| --- | --- | --- |
| Detection | `git clone --filter=blob:none file://…/server.git client` | The local configuration holds `remote.origin.promisor=true`, `remote.origin.partialclonefilter=blob:none` and a `*.promisor` pack, and **no** `extensions.partialClone`. Revision 1 checked only that key, so it passed this clone |
| Lazy fetch | `cat-file -p <missing blob>` | Exit 0, and the blob became present. `GIT_TRACE` shows `git fetch origin … --filter=blob:none` and `upload-pack` |
| `GIT_NO_LAZY_FETCH=1` | the same, on a fresh client | Exit 128. The blob is still missing, and no fetch was traced |
| `-c protocol.allow=never` | the same, on a fresh client | Exit 128: `fatal: transport 'file' not allowed`. The blob is still missing |
| Grafts | `.git/info/grafts` with the line `C X`, read with `--no-replace-objects` | `merge-base C X` changed from `e3c0f80` to `f6aa681` (= X). C's parent became X. `diff-tree C` now reports `M f.txt` and `D x.txt` |
| Alternates | `objects/info/alternates` pointing at another repository | `cat-file -t <outside commit>` gave "could not get object info" before, and `commit` after. The outside blob's content was readable |
| Standard error | `cat-file blob HEAD:private-notes/SYNTHETIC-SECRET-NAME.txt` | `fatal: path 'private-notes/SYNTHETIC-SECRET-NAME.txt' does not exist in 'HEAD'`: a repository-derived name |
| Socket monkeypatch | Python with `socket.socket` and `socket.create_connection` replaced, then `git ls-remote https://github.com/solnoctua/Sovereign-OS-Founding-Repository refs/heads/main` as a child process | Python's own socket was blocked. The Git child exited 0 and printed `99f302637d95… refs/heads/main` |

**Response in revision 2.** All in `SPEC.md`:

- **§4.2: a preflight that refuses, with exit 5, before any read:**
  - shallow repositories;
  - promisor or partial clones: any `extensions.partialclone`, `remote.*.promisor` or `remote.*.partialclonefilter` key, or any `*.promisor` pack;
  - alternates, including `http-alternates`;
  - grafts;
  - an ownership refusal.
- **§4.3: the Git invocation.**
  - A plumbing allow-list.
  - `-c protocol.allow=never` and `GIT_ALLOW_PROTOCOL=` (empty).
  - A scrubbed environment.
  - Per-call and per-run time and output limits.
  - Standard error discarded.
  - Explicit claims and non-claims about the network. `GIT_NO_LAZY_FETCH` is set but not relied on.
- **§3:** content-free errors.
- **§11:** threat rows.
- **AT-7,** rewritten: each state exits 5 before any blob read, and `protocol.allow=never` is tested with the preflight bypassed. Revision 1's socket-monkeypatch claim, in its AT-12, is withdrawn.

**Disposition:** pending independent review.

## F-2 (P1): disclosure checks

**Relayed:** "selected-chunk regexes do not cover tasks, metadata, status lines, test names, error output or private but non-secret text. Restrict to reviewed public/synthetic sources, apply whole-artifact checks and precise disclosure limitations, fail when mandatory evidence is withheld."

**Reproduced** with a literal model of revision 1's §9, whose patterns applied to the selected chunk only, using synthetic strings:

| Where | Pattern matches | Scanned by revision 1 | Result |
| --- | --- | --- | --- |
| A status line | yes | no | leaks |
| The task text and terms | yes | no | leaks |
| A `missing` entry naming a withheld path | yes | no | leaks |
| The test name `test_ghp_…` | no: `\bghp_` cannot match after `_` | no | leaks undetected |
| Private but non-secret text | no | yes | not detectable by any pattern |
| A mandatory `AGENTS.md` section containing `password = '…'` | yes | yes | withheld and recorded in `missing`, and the run continues without mandatory evidence |

**Two baseline facts behind the corrected prefix rule:**

- A prefix with no anchor at all, `sk-`, matches inside `risk-management-framework` (`docs/SOURCE-NOTES.md:24`).
- The corrected patterns match exactly two lines at `99f3026`, both in tests:
  - `SECRET = "SYNTHETIC-SECRET-PAYLOAD-4242"` (`tests/adversarial/test_pr10_audit_regressions.py:232`);
  - `token="from-plan"` (`tests/adversarial/test_context_compiler_adversarial.py:62`).

**Response in revision 2.**

- **`SPEC.md` §1:** V1 is authorized only for this repository's tracked content, and is not a privacy control.
- **§9:**
  - The patterns run on every string field, and on the final JSON and Markdown as a whole.
  - A prefix must not follow a letter or a digit.
  - Exit 2 for the task, and exit 6 for a match in mandatory evidence or in the final output.
  - The limitations are stated precisely.
- **§3:** exit 6.
- **AT-5.**
- **Test:** `test_example_passes_the_whole_output_disclosure_check_and_the_check_is_not_vacuous`.

**Disposition:** pending independent review.

## F-3 (P1): Markdown rendering

**Relayed:** "Markdown fences must have at least three backticks and exceed the longest embedded run; inertly render all repository-derived fields, paths and test commands, not excerpts only."

**Reproduced** with markdown-it-py 3.0.0's CommonMark preset:

| Input | Rendered as | Active tokens |
| --- | --- | --- |
| An excerpt with no backticks, holding a blank line, `<img src=x onerror=…>` and `## Injected heading` | revision 1's fence of one backtick | `heading_open`, `html_block` |
| The same excerpt | a fence of at least three backticks | none |
| The path `docs/[x](javascript:alert(3))<img src=y onerror=1>.md` | revision 1's raw citation line | `html_inline` |
| The same path | inside a fenced block | none |
| A test command containing `<script>` | raw, then fenced | `html_inline`, then none |

**Response in revision 2.**

- **`SPEC.md` §7.4:**
  - Fences have at least three backticks, and one more than any inner run.
  - Every repository- or task-derived value appears only inside fenced `text` blocks.
  - Labels are fixed strings.
  - Control and bidirectional characters are shown as visible markers.
  - The JSON is written with `ensure_ascii`.
- **§11.**
- **AT-10,** with structural checks that need no dependency.
- **D-12.**

**Disposition:** pending independent review.

## F-4 (P1): recorded findings and decision scope

**Relayed:** "the filename pattern `*-findings.json` does not prove independent ownership; label as recorded/unverified unless separately attested, never infer closure from `accepted` alone or conflate locally reused finding IDs. Preserve approved decision scope, not all content of a named ADR."

**Reproduced:**

- **A forged author.** In a synthetic repository, a builder committed `docs/reviews/2026-11-03-pr24-findings.json` with `--author="Independent Reviewer <reviewer@example.invalid>"`.
  - Git recorded that author, with the committer `builder`.
  - Revision 1's class rule 4 classed the file as `reviewer_finding`.
- **What `accepted` means.** `docs/engineering/FINDINGS-FORMAT.md`, lines 8, 23 and 24, makes `independent_disposition` the reviewer's word on a builder response. That response can be `deferred_with_reason`.
- **IDs are reused.** At `99f3026`, `F-1` names the PR #10 audit's evidence-set finding (ADR-0006 lines 53, 83 and 117; the PR #10 record), and an unrelated finding in `docs/engineering/findings-example.json`.
- **Decision scope at `99f3026`:**
  - register row 12 (2026-10-21) reads "ADR-0005 D1–D14 approved as architectural direction; R1–R7 as planning positions; D15 deferred";
  - row 34, in the *Proposed* table, is "an ADR-0004 amendment".

**Response in revision 2.**

- **`SPEC.md` §2.2:** the class `recorded_findings`.
- **§2.3, rules 2 and 3:**
  - Register rows are carried verbatim, with their scope.
  - Every finding carries `attribution: "recorded; ownership not verified"`, with its fields copied verbatim.
  - `accepted` is never presented as closure.
  - A finding's identity is the pair of file and `id`, and an anchor matching several files is `ambiguous`.
- **§5.6, §7.1 and §11.**
- **AT-11, AT-19 and D-11.**
- **In the schema,** `attribution` is a constant.
- **Tests:** `test_baseline_status_conflicts_and_decision_scope_are_as_stated` checks the row texts. The example test checks every conflict side, and every item class against §5.2.

**Disposition:** pending independent review.

## F-5 (P1): class-priority ranking starves source and tests

**Relayed:** "class-priority ranking starves necessary source/tests. Retain small mandatory governance core, use task relevance for remainder, enforce/diagnose required source/test coverage."

**Reproduced** with a literal model of revision 1's §5.1–5.4 and §6, at `99f3026`, using the task "Make Forget work by record id when stored text is not valid UTF-8; the memory list and Forget fail with 500 and log row content":

- There were 771 candidates. 28 were selected, totalling 32,764 bytes:

  | Class | Items | Bytes |
  | --- | --- | --- |
  | `constitution_candidate` | 7 | 8,377 |
  | `binding_decision` | 4 | 1,986 |
  | `proposed_or_historical` | 14 | 22,278 |
  | `source` | 2 | 48 |
  | `test` | 1 | 75 |

- The first source or test candidate ranked 215th of 771, behind 271,854 bytes of higher-class chunks.
- The best-scoring source candidates were not chosen. They were the `store.py` module chunk and the `Vault` class, each with score 11.

**Response in revision 2.**

- **`SPEC.md` §5.3:** a mandatory core, capped by `core_bytes`.
- **§5.4:** required paths, critical windows, a coverage report, and exit 4 when a required path contributes nothing.
- **§5.5:** relevance first, class only as a tie-breaker, and `source_percent` and `test_percent` quotas.
- **§6 and AT-15.**
- **One later change.** The core cap was first written as 4,096 bytes and then raised to 8,192 in this revision. At the baseline, the register rows naming ADR-0006 alone are 2,351 bytes, so 4,096 would refuse ordinary tasks that anchor several ADRs. The example's core is 3,103 bytes.

**Disposition:** pending independent review.

## F-6 (P1): a 2 KiB prefix of a large class

**Relayed:** "2 KiB prefix of a 56 KB class loses methods needed for the task; split methods/large blocks into relevant bounded windows and fail/mark incomplete where critical evidence is absent."

**Reproduced** with `ast`, over `src/sovereign/store.py` at `99f3026`:

- `Vault` spans lines 447–1284: 838 lines, 56,551 bytes and 38 methods.
- Revision 1's 2 KiB prefix ends at line 477, with 2,044 bytes, or 3.6% of the class. The only whole method inside it is `__init__`.
- Methods outside the prefix include:
  - `search` (555–565);
  - `_forget_plan` (651–679, 2,104 bytes);
  - `forget_preview` (681–684);
  - `delete` (686–708);
  - `_claim` (712–743);
  - `list_claims` (850–856);
  - `export` (942–949);
  - `_validity_findings` (1009–1056).

**Response in revision 2.**

- **`SPEC.md` §5.2:** a chunk per method, and windows that carry `symbol` and `span`.
- **§5.4:**
  - critical windows;
  - `coverage.complete`, with the omitted ranges listed;
  - **INCOMPLETE** in the Markdown header.
- **AT-4 and AT-16.**
- **The example** carries `Vault._forget_plan` as two windows, lines 651–678 and 679, beside `forget_preview` and `delete`.
- **The test** checks each symbol's span with `ast`, and that the windows tile it exactly.

**Disposition:** pending independent review.

## F-7 (P1): the output bound

**Relayed:** "whole output (JSON/Markdown, metadata, notes, findings, diagnostics) needs a final measured serialized-byte bound and per-field limits, with reserved mandatory evidence/omission room."

**Reproduced** from revision 1's example and the tree at `99f3026`:

- **The example's excerpts were 6,340 bytes, but its whole JSON was 14,822 bytes,** 2.34 times larger. Repeated status text alone was 1,142 bytes.
- **The longest status line is 1,041 bytes,** in `docs/second-brain/OBSIDIAN-PROJECTION.md`.
- **Test names were uncapped:** 259 test functions in 19 files, whose names alone serialize to 14,760 bytes.
- **Status text alone could exceed the bound:** 40 items × 1,041 bytes = 41,640 bytes, against `max_bytes` 32,768.

**Response in revision 2.**

- **`SPEC.md` §6:**
  - `max_output_bytes` (49,152) bounds the whole JSON, and separately its Markdown;
  - `reserve_bytes`;
  - per-field limits;
  - a deterministic shrink loop;
  - exit 4.
- **§7.1:** a status line is stored once per source, cut at 512 bytes.
- **§5.4:** the cap on tests.
- **AT-17.**
- **The example** serializes to 20,483 bytes in compact form. `test_example_respects_the_output_bound_and_the_per_field_limits` checks the bound and every limit.

**Disposition:** pending independent review.

## F-8 (P1): benchmark tasks that cannot run

**Relayed:** "T1's pinned start lacks required governance files and verbatim task exceeds max length; T2 target tree lacks candidate files and target..candidate diff includes irrelevant drift. Freeze executable task/source manifests and realistic provenance, keeping historical work explicitly calibration."

**Reproduced:**

- **T1 at `eeed753`:**
  - `AGENTS.md` and `docs/SECURITY-GATE.md` are present.
  - `docs/FOUNDER-DECISIONS.md` and `docs/engineering/BUILD-AND-INTEGRATION-PLAN.md` are absent, so revision 1 would have exited 3.
  - Issue #6's title is 65 characters and its body 2,103, against a 2,000-character limit.
- **T2:**
  - `src/sovereign/provenance.py` and `tests/test_provenance.py` are absent at `99f3026` and present at `59272b8`.
  - The merge base is `8ea54b5`.
  - Revision 1's two-tree range lists 52 paths, against the candidate's own 11. The drift includes `.github/CODEOWNERS`, the PR template, the CI workflow, `.gitignore` and `README.md`.
  - The target side changed 42 paths since the merge base. The only path changed on both sides is `docs/second-brain/SECOND-BRAIN-VALIDATION.md`.

**Response in revision 2.**

- **`SPEC.md`:**
  - **§2.1:** an absent authority order is `null`, recorded in `missing`.
  - **§3 and §4.1:** `--candidate`, with merge-base semantics.
  - **§10, AT-18 and AT-20.**
- **`BENCHMARK-PLAN.md` §3:** calibration tasks are never evidence of gain, and §3.2 defines executable manifests.
- **`benchmark-tasks.json` v2:**
  - the target, candidate and expected merge base;
  - the paths present and absent;
  - the candidate's changed paths and the paths changed on both sides;
  - the bundle refs, and the commits that must be absent;
  - a frozen statement of at most 2,000 characters, by the founder.
- **The test** `test_benchmark_manifests_are_executable_and_nothing_is_frozen` checks all of this against Git.

**Disposition:** pending independent review.

## F-9 (P1): the benchmark design

**Relayed:** "benchmark must add six-task pilot and at least twelve tasks including fresh held-outs, end-to-end independently accepted solutions, model/tool/CI/rework/human time and provider/token costs, no exceptions for missing critical security constraints, source/authority factual truth scored separately from exact quotation. Freeze gold sets independently; prevent later object leakage in historical runs."

**Reproduced: the leakage.**

- **Revision 1's control leaked.** A clone at T1's start, `eeed753`, was given a run branch. Its remote was removed, every other ref deleted and the reflog expired. Even so:
  - `git cat-file -t 8ea54b5` and `git cat-file -t 99f3026` both returned `commit`;
  - the outcome's `store.py` was readable.
- **A bundle holding only the start ref did not leak.** Cloned, it gave "could not get object info" for both later commits, and the objects reachable from its refs equalled all the objects present.

**Revision 1's plan, against the finding:**

- it stopped at a written plan, with no end-to-end outcome;
- it had three tasks, two of them retrospective;
- its gate G3 accepted shortfalls "from a documented V1 limit".

**Response in revision 2.** `BENCHMARK-PLAN.md` is rewritten:

- **§1:** two benchmarks, context correctness and end-to-end outcome.
- **§2:** the arms, with the Graphify ablation deferred.
- **§3: the task sets.**
  - Calibration: T1 and T2.
  - Pilot: 6 tasks.
  - Main: at least 12, with at least 4 held out, and the forward tasks T3 (SB-2b planning) and T4 (SB-2b implementation).
- **§4:** bundle-built environments, the object-set verification, and agent isolation.
- **§5:** the freeze order.
- **§6:**
  - reviewer-owned gold sheets, frozen by hash and including negative facts;
  - truth (C3) scored separately from quotation fidelity (C4);
  - adversarial controls.
- **§7:**
  - runs until an independently accepted solution;
  - staged timing that includes compiling the context, CI, review, revision loops and founder minutes;
  - tokens, and metered charges apart from subscription billing.
- **§8:** p50 and p90, paired deltas, and every run reported.
- **§9:**
  - a hard gate with no exceptions;
  - the founder's quality and value targets, as hypotheses;
  - amortization.
- **New collection formats:** `gold-sheet.schema.json` and `benchmark-run.schema.json`, checked by `test_collection_formats_accept_unmeasured_records_and_reject_invented_values`.

**The reviewer's benchmark-run template** was not available. The new run schema is builder-authored, and the founder decides which governs (`BENCHMARK-PLAN.md` §11, decision 8).

**Disposition:** pending independent review.

## F-10 (P2): canonical inputs and observations

**Relayed:** "define canonical deterministic package inputs separately from dirty/bare/local clone observations and make reproducibility tests honor the distinction."

**Reproduced** from revision 1's example:

- Its committed fingerprint was `sha256:728f841e68da15c8…`, and recomputing it matched.
- Changing only `repository.working_tree` gave a different fingerprint:
  - `dirty_not_read` gave `sha256:961e61ceb6e8606e…`;
  - `not_a_work_tree` gave `sha256:f4b20dbd9aa3f1e7…`.
- That is three fingerprints for one commit, task and set of arguments, contrary to revision 1's AT-1.

**Response in revision 2.**

- **`SPEC.md`:**
  - **§4.1:** the canonical inputs.
  - **§7:** the output is `{schema, fingerprint, package, observations}`.
  - **§7.2:** the observations are the working-tree state, the repository kind, the Git version, the count of ignored replace refs, and the preflight result.
  - **§8:** the fingerprint covers `package` only, with `ensure_ascii`.
  - **AT-1** covers work-tree, bare and dirty clones.
- **Schema and example:** updated to match.
- **The test** `test_fingerprint_covers_the_package_and_never_the_observations` changes only the observations and gets the same fingerprint, and changes one package character and gets a different one.

**Disposition:** pending independent review.

## Changes not tied to a single finding

- **The decision list grew.** `SPEC.md` §15 adds D-11 (verifying findings ownership) and D-12 (a CommonMark test dependency, recommended against). The founder's relay refers to D-1 to D-10.
- **The class moved.** An item's class is now carried on the item, not on its source file, because the rows of `docs/FOUNDER-DECISIONS.md` take their class from their table.
- **The example** is rebuilt from Git objects at `99f3026` for the new structure. It is still hand-assembled, and it is labelled as such.

## What this record does not do

- It does not close, accept or disposition any finding.
- It does not reproduce or replace any reviewer-owned artifact.
- It does not implement Builder 1, change `src/`, or touch PR #21.

## Erratum (added in round 2, 2026-11-03)

**The F-9 reproduction above that "a bundle holding only the start ref did not leak" was vacuous.** It bundled `refs/tmp/bench-start`. A plain clone fetches only `refs/heads` and `refs/tags`, so the clone held 0 objects, and every absence check passed trivially.

Repeated correctly, the conclusion holds: the clone of T1's start holds 849 objects, all reachable from the start commit, which is present, and `8ea54b5` and `99f3026` are absent. The details are in [`2026-11-03-pr24-round2-builder-response.md`](2026-11-03-pr24-round2-builder-response.md) (F-11). Nothing else in this record is changed.
