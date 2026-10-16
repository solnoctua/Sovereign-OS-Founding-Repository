# SOVEREIGN — Initial Architecture

**Architecture hypothesis v0.1 · October 16, 2026 · Revisable**

**Constitutional authority:** [`CONSTITUTION.md`](CONSTITUTION.md)  
**Status:** proposed, not an implementation specification or security certification.

## 1. What is being built?

Sovereign is an **AI-native personal computing layer**, initially for one person and their devices. It is *not* a replacement operating-system kernel for macOS/iOS/Linux in V0. It owns a durable personal state and governs how replaceable intelligences, tools, interfaces, and future devices interact with that state. In time it can become the main interface through which the user engages with digital life.

Its underlying purpose is a lifelong personal cognitive companion and platform that strengthens rather than displaces human intelligence and presence.

## 2. Invariants versus implementation choices

| Preserve across architectures | Deliberately replaceable |
| --- | --- |
| User authority, identity and controlled permissions | Cloud or local models; Kimi, OpenAI, or future AGI |
| Portable personal records, sources and history (subject to retention/deletion) | PostgreSQL, SQLite, object stores, sync systems |
| Explicit separation between observations, claims and authorizations | Embeddings, vector search, knowledge graphs, RAG methods |
| Provenance, corrective pathways, inspectable action receipts | Prompts, agents, orchestration frameworks and model routers |
| Versioned contracts, migrations, recovery, tested exits | Desktop, web, iPhone, Pocket or other interfaces |
| Policy enforcement independent from model instructions | Individual software services and hardware vendors |

**Design rule:** a component may be as sophisticated as necessary, but it should have an intelligible contract and a tested path to replacement.

## 3. Conceptual topology

```text
INTERFACES                    Sovereign Pocket | iPhone capture | Desktop | future surfaces
       |                      (interfaces change; personal state persists)
       v
SOVEREIGN KERNEL              Identity & Key Access
  |                            Policy / Capability Gate -----> External tools & agents
  |                            Context Compiler
  |                            Cognitive Governor
  |                            Model Gateway -----------> Kimi | other cloud models | local models
  |                            Evaluation / Observability
       |
       v
PERSONAL STATE                Source Events + Attachments
                               Derived Memory / Claims / Knowledge
                               Projects / Goals / Skills / Preferences / Relationships
                               Authority Grants / Action Receipts / Costs
                               Portable Export / Recovery / Sync
```

The kernel is a **control plane and set of enforceable boundaries**, not necessarily one monolithic process. A user request can use the model and the tools, but a model cannot grant itself capabilities or rewrite approved personal facts merely by generating text.

## 4. The six core architectural domains

### A. Personal state & memory (Sovereign Brain)

Preserve a source record for authorized inputs and transformations; derive useful knowledge without confusing a summary with its evidence. The user may opt out of storing a source or choose limited retention. Different types of state should remain distinguishable:

- **Events / evidence:** user inputs, imported files, messages, observations and execution outcomes, with source, time, consent, and retention policy.
- **Derived memory / claims:** assertions extracted or inferred from evidence, explicitly typed, scoped, time-bounded where appropriate, linked to sources, and revisable.
- **Working context:** temporary context assembled for a particular task, model, purpose, and disclosure boundary; *not* the canonical memory itself.
- **Life/project models:** explicit goals, workstreams, commitments, skills, interests, relationships, habits and evolving hypotheses about the user. These are useful models, not an authoritative definition of a person.
- **World knowledge:** externally sourced facts and models with citation, date, uncertainty and freshness policies; distinguished from autobiographical memory.
- **Governance records:** approvals, grants, denials, changes, revocations and important action receipts.

Indexing, embedding, semantic search, graphs, condensed profiles, and future memory algorithms are **derived projections**. They should be disposable and rebuildable from the retained evidence where possible. A non-deterministic model output may not be exactly reproducible; its inputs, provenance, model version and outcome can still be traceable.

**Deletion design:** Append-only logical event history is a useful audit pattern, **not** a perpetual-retention mandate. Deletion must support physical removal or cryptographic erasure of personal content, lifecycle-aware backup deletion, and appropriate tombstones to prevent sync resurrection. Never claim to erase content already retained by outside providers.

### B. Identity, trust and authorization (Sovereign Kernel)

Separate identity and permission from the reasoning model. A `CapabilityGrant` should, when relevant, name subject/agent, permitted operation, resources, scope, duration, spending ceiling, confirmation policy, and revocation state.

All external tool calls pass an enforcement boundary *outside the LLM*. The model may propose actions; the policy service determines what is permitted; the user approves consequential actions. Retrieval from untrusted webpages, transcripts, emails or files must not itself confer instructions or authority.

A future multi-device / multi-agent system requires authenticated device identity, key rotation/recovery, independent audit records, and possibly cryptographically verifiable receipts. Those are evolution targets, not proof of security at V0.

### C. Intelligence layer (model gateway)

Models should be interchangeable behind a thin request/response and tool-call adapter. Route by task complexity, privacy classification, latency, cost, and observed reliability. Support remote and local models without granting either implicit access to the complete vault.

The **development assistant subscription** (e.g., Kimi Code) is distinct from the **runtime model API budget** incurred by Sovereign itself. Keep model-use logs and opt-in spending ceilings. Avoid premature multi-model orchestration; one primary model and one independently evaluated alternative are sufficient for early tests.

Candidate contract: `ModelRequest(context_bundle_id, purpose, allowed_tools, privacy_class, budget)` → `ModelResponse(content, model_id, usage, proposed_tool_calls, references, limitations)`.

### D. Context compiler and epistemic governance

For each request, assemble a **purpose-limited context bundle** from relevant, permitted records. Filter by access rights, source type, relevance, staleness, user approvals, contradictions and sensitivity. Label direct evidence separately from inference. Record what material sources were considered and selected when meaningful.

No model output is automatically promoted to stable memory. The promotion policy may range from explicit user confirmation for sensitive identity facts to cautiously automated suggestions for lower-risk project details, with review and rollback.

### E. Cognitive Governor

Choose an interaction posture in service of agency and attention:

- **Automate:** handle low-value repetition within a defined mandate.
- **Collaborate:** think together; offer evidence, options, and critique.
- **Train:** teach, elicit retrieval and reasoning, and preserve productive struggle.
- **Challenge:** stress-test assumptions or decisions rather than agree reflexively.
- **Silence:** defer, batch or suppress nonessential intervention.

An optional **Raw** mode bypasses pedagogical shaping to give a direct answer when requested. The governor should be user-steerable and accountable, not covertly optimize the user according to a model's private theory of flourishing.

### F. Interfaces and embodiment

The intelligence and personal state are continuous while input/output changes by context:

- **Mac/Desktop:** deep research, creation, studying, coding, audits and complicated decisions.
- **iPhone first:** fast voice/text capture, secure recall and notifications before custom hardware exists.
- **Sovereign Pocket, later:** a small, discreet, largely screenless, physical interface for presence-first capture, calls, private audio, minimal gesture/physical controls and haptic cues. Silent composition/review of essential private messages must remain possible via an appropriate private interface (not necessarily a large phone screen).
- **Future research:** Optical Keyhole, Virtual Window, richer local sensing, standalone communications, and advanced physical interfaces; these remain research directions, not architectural dependencies.

Do not design the core around a future Pocket device; validate the experience on existing hardware first.

## 5. Trust boundaries and permitted information flow

| Boundary | Rule | Failure to test |
| --- | --- | --- |
| Capture → state | Source, consent, data class and retention must be recorded or handled explicitly | Audio retained without intent/permission |
| Source → memory | Derivation is identified and correctable; sensitive inferences not silently canonical | A hallucinated belief becomes 'fact' |
| State → cloud model | Context filtered to purpose and disclosure policy; usage logged | Sensitive unrelated records leaked upstream |
| Model → tool | Proposal only; independent capability check + confirmation when required | Prompt injection causes send/delete/pay |
| Tool → state | Store results, receipts, failures and reversal options | Agent claims success despite failed action |
| Device → sync | Authenticated device and revocable access; conflict/deletion handling | Lost device restores erased information |
| Stable → experimental | Versioned schema / eval gates / rollback | New model rewrites identity or breaks migration |

**No security claims should be made until the boundary has been tested.**

## 6. Minimal data contracts (conceptual)

| Contract | Essential fields | Responsibility |
| --- | --- | --- |
| `SourceEvent` | id, source, actor, occurred_at, captured_at, consent, classification, payload_ref, retention | What was captured; not automatically believed |
| `MemoryClaim` | id, text/structure, kind, source_ids, confidence, valid_time, status, revision | What may be inferred or recalled |
| `ContextBundle` | id, purpose, model_target, included_record_ids, exclusions, policy_version | What a model was authorized to see |
| `CapabilityGrant` | id, subject, capability, resource_scope, expiry, budget, approval, revocation | What an agent may attempt |
| `ActionReceipt` | id, actor, intent, grant_id, request, outcome, evidence, timestamp, reversal | What actually happened |
| `CognitivePolicy` | mode, scope, override, feedback | How to help without overriding agency |

These are **conceptual fields, not frozen schemas**. Stable versions and migration paths become mandatory when code is introduced.

## 7. The first complete user journey (V0 golden path)

1. Capture a spoken or written thought on a device you already own.
2. Store its source, provenance, classification and retention intent in a locally controlled vault.
3. Transcribe or transform it, creating a *proposed*, source-linked claim or task.
4. Search / recall through a selected model with only relevant, approved context.
5. Give an evidence-linked answer and clearly separate fact from inference.
6. Correct, supersede or delete the claim; verify it changes future recall.
7. Export, back up, restore and retrieve it *without requiring the original model provider*.
8. Demonstrate a denied unauthorized tool action and inspect a comprehensible receipt.

**Definition of useful first system:** all eight behaviors work end-to-end in a small, local, single-user workflow. Not necessary initially: autonomous swarms, social graph, elaborate RAG, custom Pocket hardware, phone replacement, cryptographic blockchain infrastructure, or an on-device frontier model.

## 8. Candidate implementation (NOT constitutional)

- **Host / boundary:** user-controlled Mac, local service by default; intentional authenticated access from iPhone.
- **Language / API:** Python with a thin HTTP service (FastAPI is one candidate).
- **Durable store:** local SQLite for minimum operational burden *or* locally hosted PostgreSQL for stronger multi-service growth. **Decision open**; decide with migration/backup tests, not ideology.
- **Files / audio:** content-addressed files in a user-owned local vault with metadata in the store; never store secrets or recordings in Git.
- **Indexing:** simple structured lookups / full-text search first; add embeddings only after retrieval evaluations demonstrate the need.
- **Models:** Kimi or another provider through one adapter; local model fallback as capability permits.
- **Security:** OS credential store/key management, encryption where appropriate, network access controlled, separate data disclosure from inference; documented threat model before exposing services publicly.
- **Testing:** unit/schema/migration tests and scenario-based evals; no test credentials or personal recordings in repo.

## 9. Evolution channels

- **Stable:** trusted daily-driver; only evaluated upgrades, backup compatibility, easy rollback.
- **Next:** candidate upgrades against a scrubbed or permissioned test corpus; measurable quality, cost, latency, usability and safety.
- **Lab:** speculative world models, memory research, new interfaces, agent frameworks, automated self-improvement and hardware experiments—isolated from sensitive stable state unless specifically approved.

An experiment cannot promote itself to Stable or expand its authority. A governance gate must preserve evaluation records and approval.

## 10. Evaluation framework

Before adding sophistication, measure:

- **Memory:** sourced factual recall, false-memory rate, contradiction handling, staleness, corrections, deletion.
- **Agency:** user override works, unauthorized actions fail, high-impact actions wait for approval, productivity *and* independent competence.
- **Privacy:** no unapproved context disclosure, secure recovery, deliberate retention, tested provider exit.
- **Resilience:** offline core behavior, restore time, migration to a second model and second store.
- **Experience:** speed of capture, task completion, interruptions, unnecessary friction, sense of presence.
- **Economics:** task-level model cost, spending thresholds, accuracy per dollar.

Tests should include negative cases: revoked permission, contradictory old/new memories, source injection, cloud outage, device loss, and malicious imported content.

## 11. Decisions intentionally deferred

See [`OPEN-QUESTIONS.md`](OPEN-QUESTIONS.md). No architecture preference becomes an invariant without testing it against the Constitution. Future architecture decision records (ADRs) belong in `docs/adr/`.
