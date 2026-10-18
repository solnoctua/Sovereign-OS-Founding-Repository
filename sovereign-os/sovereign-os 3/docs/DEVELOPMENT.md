# Sovereign — Multi-model development workflow

**Status:** founder development strategy, not Constitution and not a permanent product-architecture requirement.

## Objective

Use complementary AI systems to increase engineering quality, architectural integrity, execution speed, and cost efficiency while preserving founder authority and a clean Git history.

The workflow is intentionally provisional. Model roles are earned by observed performance and may change as tools improve.

## Default loop

**Specify → Build → Audit → Challenge → Test → Approve → Merge**

Not every change needs every stage as a separate session. The amount of review is proportional to consequence and reversibility.

### 1. Specify

Create a bounded task with:

- problem and desired outcome;
- relevant architecture/security constraints;
- explicit acceptance checks;
- out-of-scope items;
- migration/reversal requirements when state is affected.

For small tasks this can be the issue/prompt itself. Create an ADR only for durable architecture decisions.

### 2. Build

One model is the **primary builder**. Give it the same canonical repository state and task specification that a human engineer would receive. It may inspect the repository, implement, test, and document within scope.

The current provisional candidates are Claude Code and Codex. Do not encode either as the permanent builder in repository policy.

### 3. Audit / Challenge

Use an independent model when the review tier requires it. Give the reviewer the requirement, final diff, test evidence, and relevant founding documents. Ask it to find defects and tradeoffs—not to rewrite the feature by preference.

Resolve disagreement by, in order:

1. Constitution and accepted ADRs;
2. observable requirements and tests;
3. security/reliability evidence;
4. simpler reversible design;
5. explicit founder judgment when a value/tradeoff remains.

Model confidence or prestige is not evidence.

### 4. Test

Mechanical checks are the neutral arbiter wherever possible. At minimum for Python code in V0:

```bash
pytest -q
git diff --check
python -m compileall -q src tests
```

Add targeted failure/adversarial tests for security-sensitive behavior.

### 5. Approve / Merge

The founder approves consequential architecture, scope, security, provider, schema, and governance changes. Routine implementation changes can merge after their required checks and review pass.

Prefer short-lived branches and comprehensible commits. Do not let AI-generated session transcripts become canonical project context.

## Review tiers

### Tier 0 — mechanical/routine

Examples: typo, narrow styling change, test fixture cleanup, isolated refactor with unchanged behavior.

**Process:** one builder + tests. No independent model required.

### Tier 1 — normal product change

Examples: bounded endpoint, UI behavior, retrieval improvement, internal refactor with meaningful behavior.

**Process:** one builder + tests; lightweight second-model review when uncertainty is nontrivial.

### Tier 2 — consequential

Examples: personal-state schema/migration, memory-authority logic, provider/disclosure behavior, permissions, deletion/recovery, new major dependency, agent/tool execution, authentication.

**Process:** written spec + primary builder + independent reviewer + adversarial tests + founder approval.

### Tier 3 — foundational

Examples: Constitution amendment, major architecture rewrite, trust model, system-wide memory model, migration strategy, self-modification, high-impact security design.

**Process:** independent architecture reasoning by at least two strong models, explicit disagreement analysis, evidence/research as needed, frontier-model escalation when useful, and founder decision before implementation/merge.

## Frontier API escalation

Use paid API inference when expected decision value exceeds cost. Good triggers:

- Tier 3 work or a genuinely hard Tier 2 problem;
- two capable models disagree on a material issue;
- repeated implementation/debug failure;
- security or migration design where an additional independent view materially reduces risk;
- a benchmark needs a stronger reference solution or audit.

Do not spend frontier tokens on routine code generation, documentation polish, or questions answered by tests/source docs. Start with a task-level cap, inspect value received, and only escalate further when justified. Keep provider/model names out of durable project requirements unless the product itself depends on them.

Treat the current **$60 API budget as a reserve, not a quota**. Spend against uncertainty and consequence, not by pre-allocating dollars to vendors. A difficult foundational review can justify meaningful spend; an ordinary feature should usually consume none. Record material API spend in the task/benchmark notes so quality-per-dollar can be compared over time.

## Canonical context and handoff

Git is the source of truth. Shared context should normally consist of:

- the current commit/branch;
- `AGENTS.md`;
- the task/issue specification;
- applicable Constitution/Architecture/ADR/security files;
- the diff and test output for review.

Do **not** maintain giant model-specific memory files or paste full previous AI conversations into the repo.

A useful handoff is five short fields:

```text
Task:
Starting commit:
Changed files / diff:
Tests and results:
Risks / unresolved questions:
```

If a material decision emerges during implementation, record it in an ADR or task specification rather than relying on an AI chat to preserve it.

## Builder assignment

Use benchmark results, not reputation, to choose the default builder. Re-run a benchmark when either coding system materially changes or when observed performance drifts. A default builder is a convenience, not an authority hierarchy.
