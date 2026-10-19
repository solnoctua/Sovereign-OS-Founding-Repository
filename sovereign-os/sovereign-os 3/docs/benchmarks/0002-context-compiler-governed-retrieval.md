# Benchmark 0002 — Context Compiler V0 / governed retrieval

**Purpose:** specify and evaluate the next real Sovereign milestone (ROADMAP M2: context compiler, basic retrieval, cited recall). It establishes **what Sovereign may retrieve for a purpose, how it is represented to a reasoning model, and what may cross the local/cloud boundary**, on top of the MemoryClaim authority of Benchmark 0001 / ADR-0003. The decision record is [ADR-0004](../adr/0004-governed-retrieval-context-compiler.md).

**Tier 2:** it changes the interpretation of memory authority and the cloud-disclosure boundary, so independent review and founder approval are required.

## Starting point

`main` at `7ae16e964746b5f653e501e0abca6a8b3ba59a8c` (MemoryClaim merged). Record for each run: model/tool version, start/end wall time, human interventions, tests run and any paid API cost.

## Task

Build an explicit, model-neutral pipeline in which **retrieval ≠ authority ≠ disclosure ≠ inference**:

`question → local candidate retrieval → Context Compiler (relevance, authority, provenance, support/freshness, sensitivity, disclosure policy) → ContextBundle → exact disclosure preview → explicit approval when cloud-bound → provider adapter`

The provider must receive only the compiled, authorised bundle and must never query the vault. No model determines its own permissions, authority or disclosure scope.

### Required behaviour

1. **A focused, provider-independent compiler module** with the smallest useful representations of a retrieval candidate, a context item, a context bundle, a receipt and a policy. No generic framework.
2. **A self-explaining bundle.** It must answer:
   - which question caused this retrieval;
   - which candidates were considered;
   - what was included, in which role and why;
   - which relevant candidates were excluded and why, using machine-readable reason codes;
   - which disclosure boundary applies, and exactly what would be transmitted.
3. **Authority comes from MemoryClaim.**
   - Only an approved claim with currently supported evidence may be `approved_memory`.
   - Proposed, contested, rejected and superseded claims, and approved but stale, orphaned or unverified claims, are excluded and explained.
   - Active source records may be `evidence`, distinct from approved memory all the way into the prompt.
4. **Sensitivity inheritance.** A claim inherits the most restrictive sensitivity of its current supporting evidence, computed from storage and never from the client.
5. **Local vs cloud.**
   - Local compilation may use eligible private and sensitive context and calls no provider.
   - Cloud requires explicit per-request approval. Sensitive items never leave; private items leave only inside the approved exact bundle.
   - Neither choosing a provider nor approving a claim authorises disclosure.
6. **Exact-bundle approval.**
   - A compile/preview operation returns a deterministic `context_token`, bound to current state and the exact outbound bundle.
   - A cloud request needs approval **and** the matching token. The server recompiles and returns 409 if anything relevant changed (source forgotten or corrected, claim decision, support change, candidate-set change), with no provider call.
   - The server never sends more than the approved preview. The token is request-scoped, never persisted, never authority.
7. **Simple, transparent retrieval.**
   - It is deterministic and lexical, with inspectable, stable ranking under ties.
   - User-selected source IDs are high-priority candidates that still pass every policy.
   - A small, documented context budget is enforced, and truncation is visible (`budget_exceeded`).
8. **Structured first.** The compiler produces a structured, model-neutral bundle; only the provider/prompt boundary turns it into messages.
9. **One policy implementation.** `/api/ask` routes all model-bound context through the compiler. Model responses never mutate memory or authority.
10. **Minimal UI.** It shows the selected context (approved memory, evidence), exclusions with reasons, and exactly what leaves the device. It offers "Approve this context & ask", and makes the user review the new bundle after a 409.
11. **Documentation.**
    - A new ADR narrows ADR-0003's "claims are never sent to a model" explicitly, without rewriting history.
    - `ARCHITECTURE.md` and `ROADMAP.md` are updated minimally.
12. **No persistence.** Raw bundles and question text are not persisted.

### Core acceptance example (synthetic)

- **The vault:**
  - evidence A: "I decided Sovereign should use local-first memory.";
  - an approved, supported claim: "Sovereign should remain local-first.";
  - a proposed claim: "The user wants everything automated.";
  - sensitive evidence B: "Synthetic private medical example."
- **The question:** "What principles have I established for Sovereign?"
- **Local compilation:**
  - the approved claim is `approved_memory`;
  - A is `evidence`;
  - the proposed claim is excluded as `not_authoritative`;
  - B is irrelevant.
- **Cloud:**
  - eligible private memory and evidence appear in the exact outbound preview;
  - B does not;
  - no call happens without approval of that exact bundle.

### Required tests

**Normal:**
- each authority rule above;
- source distinguishable from claim;
- deterministic ordering and compilation;
- pinned sources still pass policy;
- forgotten content never retrieved;
- corrections immediately affect authority;
- no duplicate outbound content;
- visible budget;
- local may use sensitive eligible context;
- useful receipt reasons.

**Adversarial** (`tests/adversarial/`, run by the existing `memory-adversarial` job):
- **authority bypass:** proposed or rejected IDs requested directly, provider choice, imported claims, claim IDs where source IDs are expected;
- **disclosure bypass:** sensitive-backed and mixed claims, a manually selected sensitive record, cloud without approval, approval without the matching token, a stale token;
- **leakage:** a mocked `providers.generate` receives only the authorised bundle, and no excluded sentinel appears;
- **deletion and corrections;**
- **TOCTOU:** compile, change state, execute, expecting 409 with no provider call;
- **model authority:** a hostile model response changes nothing.

## Out of scope

Agents, external actions, capability execution, autonomous memory promotion, embeddings or vector databases, knowledge graphs, a self-model, the cognitive governor, background jobs, new cloud infrastructure, mobile or Pocket work, and unrelated repository restructuring. No real personal data.

## Scoring — 100 points

- **Correctness and acceptance behaviour — 30**
- **Authority and disclosure boundaries (no bypass, exact-plan approval, sensitivity inheritance) — 30**
- **Tests and adversarial coverage — 20**
- **Simplicity / maintainability / fit with the current architecture — 15**
- **Execution efficiency — 5**

Automatic disqualifiers:
- any path by which non-authoritative claims, sensitive items, forgotten data or unapproved content reach a provider;
- a provider or model that reads the vault directly;
- a model influencing its own context or permissions;
- weakened MemoryClaim adversarial tests;
- committed secrets or personal data.

## Evaluation procedure

1. Run `pytest -q`, `pytest -q tests/adversarial`, `git diff --check` and `python -m compileall -q src tests`.
2. Review the diff without relying on the builder's self-assessment.
3. Have an independent reviewer try to break:
   - authority filtering and sensitive-data inheritance;
   - exact disclosure approval and stale-bundle/token handling;
   - forgotten-data exclusion;
   - prompt/data leakage and provider isolation.
4. Record concrete defects and required human fixes. The founder decides on merge.
