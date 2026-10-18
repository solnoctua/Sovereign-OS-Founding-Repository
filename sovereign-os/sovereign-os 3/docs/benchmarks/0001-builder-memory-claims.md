# Benchmark 0001 — Memory claim authority workflow

**Purpose:** choose the default V0 coding agent empirically between available coding systems. This is also useful real Sovereign work; no throwaway benchmark feature.

## Starting point

Both builders start from the same commit and receive the same task specification. Use separate Git worktrees/branches. They must not see the competing implementation until both runs are complete.

Record for each run: model/tool version, start/end wall time, human interventions, tests run, and any paid API cost. Do not optimize prompts differently after seeing one result.

## Task

Implement the first explicit separation between **source evidence** and **derived memory claims**.

A source record is evidence and must remain unchanged by this feature. A claim is a proposed interpretation derived from one or more source records and must never become authoritative merely because a model generated it.

### Required behavior

1. Add a durable `MemoryClaim` representation linked to one or more existing source-record IDs.
2. Claim lifecycle for V0: `proposed` → `approved` or `rejected`.
3. Creating a claim defaults to `proposed`. No endpoint or model response may silently create an `approved` claim.
4. Approval/rejection is an explicit local human action through the API and visible UI.
5. A claim stores provenance sufficient to identify its source record IDs, creation time, status, and whether it was human-written or model-proposed.
6. Claims whose source records are deleted must not continue to present themselves as supported facts. Choose a simple, documented behavior (for example invalidate/orphan) and test it.
7. Export/import preserves claims and their authority state without allowing deleted source evidence to resurrect.
8. Existing capture/search/correction/deletion/cloud-disclosure behavior and tests must continue to pass.
9. UI should make the evidence/claim distinction understandable without adding a complex dashboard.
10. No new cloud call, agent framework, graph database, vector database, or major dependency is justified by this task.

### Required tests

At minimum cover:

- claim creation defaults to proposed;
- explicit approve and reject paths;
- invalid/missing source IDs fail safely;
- source deletion changes dependent claim validity as documented;
- export/restore does not elevate claim authority or resurrect deleted evidence;
- existing cloud-disclosure restrictions remain intact.

## Out of scope

Automatic LLM claim extraction, confidence scoring, temporal knowledge graphs, embeddings, autonomous approval, user-profile inference, multi-user permissions, encryption migration.

## Scoring — 100 points

- **Correctness and acceptance behavior — 35**
- **Security / epistemic-authority boundaries — 25**
- **Tests and failure-path coverage — 15**
- **Simplicity / maintainability / fit with current architecture — 15**
- **Execution efficiency — 10** (time, interventions, unnecessary diff/dependencies, cost)

Automatic disqualifiers: silently approving model-derived claims; weakening cloud disclosure/security checks; committing secrets/personal data; destructive migration without a tested recovery path.

## Evaluation procedure

1. Run the same repository checks on both solutions.
2. Review diffs without relying on the builders' self-assessments.
3. Have the non-building model review each solution against this spec; where practical, hide which system authored which branch.
4. Record concrete defects and required human fixes.
5. Founder chooses the default builder based on total evidence, not the numerical score alone.
6. Preserve the better implementation; delete benchmark-only branches after useful findings are recorded.

## Suggested worktree setup

From the benchmark base commit:

```bash
git worktree add ../sovereign-bench-codex -b bench/codex-memory-claims
git worktree add ../sovereign-bench-claude -b bench/claude-memory-claims
```

Give each tool the contents of this file as the task. Both should read `AGENTS.md` and the referenced project documents before implementation.
