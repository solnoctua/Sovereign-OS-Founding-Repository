# Builder 1 benchmark plan: manual handoffs against generated context (PLAN, no results)

**Status:** PLAN for [Issue #22](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/issues/22).

- **No results.** No run has been executed. No gold set, frozen manual handoff or Builder 1 implementation exists.
- **No claims.** Nothing here says that generated context is better or worse than a manual handoff. The pinned tasks are in [`benchmark-tasks.json`](benchmark-tasks.json). The tool under test is specified in [`SPEC.md`](SPEC.md).
- **Not a retrieval benchmark.** This plan measures development handoffs given to coding agents, not personal-memory retrieval. It never uses or extends the Benchmark 0003 harness (`AGENTS.md`).

## 1. Questions

For the three pinned tasks:

1. Does a Builder 1 package carry the sources and constraints that a correct change needs at least as completely as a manual handoff?
2. Does it carry fewer false assertions?
3. At what size, and for how much human preparation time?
4. When Claude Code or Codex works from it, does an independent reviewer find fewer or more corrections that trace back to missing or wrong context?

These are questions. The answers are whatever the measurements in §4 show, reported in full.

## 2. Arms

| Arm | Context given to the agent, besides the task statement and the repository at the start commit |
| --- | --- |
| **A: manual** | A handoff written by the founder in the five-field form of `docs/DEVELOPMENT.md` § *Canonical context and handoff*: Task, Starting commit, Changed files / diff, Tests and results, Risks / unresolved questions. For T1 and T2, the founder's historical handoff is used verbatim if the founder provides it, because it was written without hindsight. Otherwise a new one is written and timed |
| **B: generated** | The Markdown rendering of `python -m devcontext "<task statement>" --rev <start> [--range …]`, with default budgets, unedited |
| **C: none (optional)** | The task statement only. This is a floor that shows what any context adds. The founder decides whether to run it (§9) |

The **task statement** is identical in every arm. For T1 it is Issue #6's title and body, snapshotted with their retrieval time. For T2 it is the founder's integration instruction. For T3 it is a short planning request written by the founder.

## 3. Tasks

| ID | Task | Kind | Start | Reference outcome |
| --- | --- | --- | --- | --- |
| T1 | **Issue #6:** schema-v5 repair of the hidden-rowid `REPLACE` bypass and of zero-source authority | Retrospective implementation | `eeed753` (`main` before PR #10) | PR #10 head `8ea54b5`, merged through PR #20 as `99f3026`. The Codex audits of `04ba75c` (CHANGES REQUIRED: F-1–F-4, F-8) and `8ea54b5` (PASS), as recorded in `docs/reviews/2026-10-22-f9-f10-reconciliation.md` |
| T2 | **SB-2a integration:** PR #11 into `main` | Retrospective integration | `99f3026`, with `--range 99f3026..59272b8` (#11's head) and the rehearsed R11 `e639178` | PR #21: `4c34317` (Codex Tier 2 CONDITIONAL PASS: F-9 condition, F-12 / Issue #23, as handed off by the founder) and `b00a5b3` (the F-9 correction) |
| T3 | **SB-2b:** plan the minimal snapshot exporter | Prospective planning | `main` after PR #21 merges, pinned when it does | None: judged by the rubric of §4.3 |

**Why these three.** They are the work the issue names. Two have a recorded independent review, which gives an observed baseline of reviewer corrections. One is real upcoming work, where nobody knows the answer yet.

**Contamination control** for T1 and T2: every run uses a fresh clone at the start commit with no remotes and no refs beyond those pinned. Later commits, including the reference outcome, are therefore not reachable from inside the run.

## 4. Measures

### 4.1 Gold sets: written before any generated context exists

For each task, the founder or an independent reviewer, **never the Builder 1 implementer**, writes `gold/<task>.json`. It contains:

- `required_sources`: paths an agent must read, each with a one-line reason;
- `constraints`: atomic, checkable statements, each with a citation at the start commit and an importance of `must` or `should`;
- `known_traps`: facts that a plausible change gets wrong. Example *kinds*, not items: a stale status statement, a failure mode outside the happy path, an approval or ruleset subtlety.

Only the gold file's SHA-256 is committed when the inputs are frozen. The file itself is committed after the generated contexts exist (§5), so the implementation cannot be tuned to it.

### 4.2 Context-level measures (both arms, no agent run)

| ID | Measure | Definition |
| --- | --- | --- |
| M1 | Source coverage | share of `required_sources` that the context includes or cites by path |
| M2 | Constraint coverage | per `must` and per `should` constraint: *present and correct*, *present but wrong*, or *absent*, as judged by the scorer against the citation |
| M3 | Omitted constraints | the list of absent `must` constraints |
| M4 | False assertions | declarative statements about the repository, its decisions or its state that the start commit contradicts. Statements Git cannot settle are counted separately as *unverifiable*. For B, excerpts are true by construction when their citations are exact; the tool's own sentences (conflict summaries, missing items) are scored like prose |
| M5 | Size | UTF-8 bytes of the context. Input tokens only as each agent reports them, never estimated |
| M6 | Preparation effort | human minutes from start to a context ready to hand over, with start and stop recorded by the founder. For A: writing. For B: running, reading and deciding to use it. For B, any edit makes it a different arm and is reported as such |
| M7 | Reproducibility (B) | two runs on two clones give the same fingerprint |

### 4.3 Outcome-level measures (agent runs)

Each run stops at a written plan: files to change, approach, risks and tests. T2 may also stop at the first integration commit (§9).

| ID | Measure | Definition |
| --- | --- | --- |
| O1 | Plan correctness | per `must` constraint: respected, omitted or violated in the plan |
| O2 | Context-attributable reviewer corrections | An independent reviewer, blind to the arm, records findings on the plan in the `docs/engineering/FINDINGS-FORMAT.md` style. Only then, shown the context, the reviewer marks each finding *attributable* (the needed fact was absent or wrong in the context) or *not attributable* |
| O3 | Effort | agent turns and reported tokens to the plan, and wall-clock minutes |

For T1 and T2, the historical reviews are listed in §3 as an observed baseline for arm A's real outcomes. They are not runs of this protocol and are not compared numerically with new runs.

## 5. Protocol

1. **Freeze the inputs** before the Builder 1 implementation is run on any task, and preferably before the implementation PR opens. Commit:
   - the task statements;
   - the arm A handoffs, with their M6 times;
   - the SHA-256 of each gold file;
   - the agent list.
2. **Freeze the tool:** the implementation commit and `selection_version`. A change to selection after this point restarts the benchmark.
3. **Generate** arm B packages with default budgets. Record the fingerprints, and confirm M7 on a second clone.
4. **Reveal** the gold files. Compute M1–M5 for A and B. The scorer is not the builder.
5. **Run the agents.** For each task, arm and agent (Claude Code, Codex), start a fresh session on a fresh clone, with the same instructions apart from the arm's context. Arm order is randomized per task. Transcripts are not committed (`docs/DEVELOPMENT.md`); only the measures and the plan text are.
6. **Review blind** (O2), then mark attribution.
7. **Report** every run, including failed or aborted ones, in a results PR. Nothing is extrapolated beyond these three tasks.

## 6. Adoption gate, fixed in advance

The gate informs the founder's decision on whether to use Builder 1 for SB-2b. It is not a performance claim.

| Gate | Condition |
| --- | --- |
| G1 | Every arm B package is schema-valid, its citations are exact, it is within budget, and it is reproducible (M7) |
| G2 | Arm B has zero false assertions (M4) |
| G3 | On each task, B's `must`-constraint coverage (M2) is at least A's, or every shortfall comes from a documented V1 limit, such as GitHub state being outside V1 |
| G4 | B's preparation effort (M6) is at most A's on at least two of the three tasks |
| G5 | Summed over tasks, B shows no more context-attributable corrections (O2) than A. With this sample size this is a sanity check, not a statistical result |

**Outcomes.**

- **G1 or G2 fails:** fix the tool and re-freeze, or stop.
- **Mixed results on G3–G5:** the founder judges, from the full report.

## 7. Artifacts

These are proposals, decided under §9:

- **Results report:** `docs/benchmarks/0004-builder1-development-context.md`. The numbering follows `docs/benchmarks/`. It is a development-handoff benchmark, not a second retrieval benchmark.
- **Frozen inputs and outputs:** `evaluation/devcontext/<task>/`:
  - `task.md`;
  - `handoff-a.md`;
  - `gold.sha256`, then `gold.json`;
  - `package-b.json`, `package-b.md`;
  - `scores.json`.

## 8. Threats to validity

- **Three tasks** cannot show a general effect. Agent behaviour also varies between runs and model versions.
- **Hindsight.** The gold sets for T1 and T2 are written knowing the outcome. That is intended, since they define what was needed. Arm A's historical handoffs were written without hindsight; a newly written A handoff would not be.
- **Tuning.** The tool's author knows the tasks. Freezing `selection_version` before the gold sets are revealed limits tuning to the gold sets, not to the tasks. T3 is the least exposed task.
- **Imperfect blinding.** A generated package and a manual handoff look different, so context-level scoring cannot be blind. The outcome scoring (O1, O2) is blind until the attribution step.
- **Scorer burden.** M2 and M4 are judgments; borderline calls are recorded with a reason. A second scorer is optional (§9).

## 9. Decisions for the founder

1. **Who writes the gold sets and arm A handoffs:** the founder, or an independent reviewer. The Builder 1 implementer never does.
2. **Agents and runs per cell.** Minimum: Claude Code and Codex, 1 run per arm per task, giving 12 plan-stage runs. Arm C is optional, adding 6.
3. **Stopping point:** whether T2 continues past the plan to the first integration commit.
4. **Cost cap** for the agent runs.
5. **Second scorer** for M2 and M4.
6. **Artifact locations** (§7), and the number `0004`.

## 10. Results

**None.** No run has been executed. Results will appear only in a separate PR, after the implementation and the freeze of §5.
