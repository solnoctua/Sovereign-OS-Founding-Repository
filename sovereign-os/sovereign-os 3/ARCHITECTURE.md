# SOVEREIGN — Initial Architecture

**Architecture hypothesis v0.2 · October 18, 2026 · REVIEW BRANCH, NOT RATIFIED · Revisable**

**Constitutional authority:** [`CONSTITUTION.md`](CONSTITUTION.md)  
**Status:** proposed, not an implementation specification or security certification.

## 1. What is being built?

Sovereign is an **AI-native personal computing layer**, initially for one person and their devices. It is *not* a replacement operating-system kernel for macOS/iOS/Linux in V0. It owns a durable personal state and governs how replaceable intelligences, tools, interfaces, and future devices interact with that state. In time it can become the main interface through which the user engages with digital life.

Its underlying purpose is a lifelong personal cognitive companion and platform that strengthens rather than displaces human intelligence and presence.

## 1A. Founding decisions recorded October 16, 2026

1. **Sovereignty:** local-first durable control, with scoped, independently authorized use of remote intelligence. Provider access and data disclosure are distinct decisions; no model receives blanket vault access.
2. **Audience:** one founder's actual lifelong system first. Multi-user product requirements are future hypotheses, not requirements that complicate V0 or override other people's agency.
3. **Cognitive posture:** proactively challenge when useful, but make the intervention visible and easily overridable. Tool-policy denials are independent of coaching and cannot be overridden merely by choosing a conversational mode.
4. **Memory governance:** risk-based, source-linked promotion. Capture, inference, and promotion are distinct; low-risk promotion may be automated within a visible policy, sensitive or identity-shaping claims require human approval.

See [`docs/adr/0001-founding-choices.md`](docs/adr/0001-founding-choices.md). These are human decisions; the amendments implementing them are still proposals.

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
- **Derived memory / claims:** assertions extracted or inferred from evidence, explicitly typed, scoped, time-bounded where appropriate, linked to sources, and revisable. **Stored** does not mean **promoted to authoritative memory**.
- **Working context:** temporary context assembled for a particular task, model, purpose, and disclosure boundary; *not* the canonical memory itself.
- **Life/project models:** explicit goals, workstreams, commitments, skills, interests, relationships, habits and evolving hypotheses about the user. These are useful models, not an authoritative definition of a person.
- **World knowledge:** externally sourced facts and models with citation, date, uncertainty and freshness policies; distinguished from autobiographical memory.
- **Governance records:** approvals, grants, denials, changes, revocations and important action receipts.

Indexing, embedding, semantic search, graphs, condensed profiles, and future memory algorithms are **derived projections**. They should be disposable and rebuildable from the retained evidence where possible. A non-deterministic model output may not be exactly reproducible; its inputs, provenance, model version and outcome can still be traceable.

**Memory authority policy (proposed V0):** Claims use `proposed → active → contested / superseded / deleted`, with possible `rejected` for proposals not accepted. Importing a record can create a proposal without promoting it. A verified user declaration may be given higher evidentiary weight than an inferred preference, but both retain links to the original and the user's current corrections. Do not feed `proposed` or `contested` claims into a model as established personal facts. Every automatic promotion records its policy version, reasons, source IDs, and a reversible decision.

| Promotion class | Examples | Default treatment |
| --- | --- | --- |
| Routine / low impact | User-authorized project titles, factual task descriptions, source-linked notes | Policy-limited automatic promotion *may* be enabled; visible history and undo required |
| Uncertain / conflicting | Contradictory project deadlines, ambiguous personal preferences, inferred intentions | Keep proposed or contested; ask when material to a decision |
| Sensitive / identity-shaping | Health, finances, relationships, intimate information, traits, personal value judgments | No autonomous approval of AI inferences; explicit human confirmation before canonical promotion |
| External action or public claim | Sending a message, publishing a statement, authorizing payment or deletion | Memory status does not itself authorize action; separate capability grant and action approval |

Risk class and approval requirements must depend on **source, inference type, sensitivity, downstream consequence, and user policy**, not a model confidence score alone.

**Deletion design:** Append-only logical event history is a useful audit pattern, **not** a perpetual-retention mandate. Deletion must support physical removal or cryptographic erasure of personal content, lifecycle-aware backup deletion, and appropriate tombstones to prevent sync resurrection. Never claim to erase content already retained by outside providers.

### B. Identity, trust and authorization (Sovereign Kernel)

Separate identity and permission from the reasoning model. A `CapabilityGrant` should, when relevant, name subject/agent, permitted operation, resources, scope, duration, spending ceiling, confirmation policy, and revocation state.

All external tool calls pass an enforcement boundary *outside the LLM*. The model may propose actions; the policy service determines what is permitted; the user approves consequential actions. Retrieval from untrusted webpages, transcripts, emails or files must not itself confer instructions or authority.

A future multi-device / multi-agent system requires authenticated device identity, key rotation/recovery, independent audit records, and possibly cryptographically verifiable receipts. Those are evolution targets, not proof of security at V0.

### B1. Cloud disclosure and local authority

**Control plane local-first:** policy decisions, key access, canonical memory writes, approval records, and outgoing-context assembly occur in the user-controlled environment by default. Remote models may compute over **minimized, preapproved context bundles**; they do not receive general vault credentials, self-authorized tool access, or master keys.

A cloud request requires two independent decisions:

1. **Inference selection** — whether this task may use a named model/provider class, taking into account task quality, cost, latency, availability, and provider conditions.
2. **Data disclosure authorization** — exactly which content and sensitivity classes may leave the private boundary, for which purpose, under what expiry and retention/training guarantees *actually supported* by the provider.

A prompt cannot grant its own exception. Implement a local, deterministic gateway policy independent of the LLM. If authorization is insufficient, ask for explicit permission, use a suitable local mode, or refuse disclosure. A grant controls future exports; it cannot retroactively withdraw data already delivered to a provider. Keep an outbound disclosure receipt containing only the minimum metadata necessary to audit transmission. Avoid logging secret content into observability systems.

**Offline/degraded mode:** basic capture, local storage, search, review, deletion, and policy management should remain usable without cloud inference. The iPhone may queue authenticated, locally protected capture until its chosen vault is reachable. V0 need not offer high-quality offline generative intelligence or continuous Pocket availability. Lost-device revocation, sync conflicts, and recovery must be designed before multi-device sync expands.

### C. Intelligence layer (model gateway)

Models should be interchangeable behind a thin request/response and tool-call adapter. Route by task complexity, privacy classification, latency, cost, and observed reliability. Support remote and local models without granting either implicit access to the complete vault.

The **development assistant subscription** (e.g., Kimi Code) is distinct from the **runtime model API budget** incurred by Sovereign itself. Keep model-use logs and opt-in spending ceilings. Avoid premature multi-model orchestration; one primary model and one independently evaluated alternative are sufficient for early tests.

Candidate contract: `ModelRequest(context_bundle_id, purpose, allowed_tools, privacy_class, budget)` → `ModelResponse(content, model_id, usage, proposed_tool_calls, references, limitations)`.

### D. Context compiler and epistemic governance

For each request, assemble a **purpose-limited context bundle** from relevant, permitted records. Filter by access rights, source type, relevance, staleness, user approvals, contradictions and sensitivity. Label direct evidence separately from inference. Record what material sources were considered and selected when meaningful.

A model output is **not** automatically trustworthy. Risk-scoped automatic promotion is allowed only for categories expressly authorized in `MemoryPromotionPolicy`; every such decision is logged, linked to evidence, correctable, and undoable. Sensitive, disputed, identity-shaping, or high-impact claims require explicit approval before entering canonical state. If an assistant paraphrases a user declaration, its status and meaning must not exceed the underlying source. In a recall answer, display source-linked observations separately from inferred hypotheses.

### E. Cognitive Governor

Choose an interaction posture in service of agency and attention:

- **Automate:** handle low-value repetition within a defined mandate.
- **Collaborate:** think together; offer evidence, options, and critique.
- **Train:** teach, elicit retrieval and reasoning, and preserve productive struggle.
- **Challenge:** stress-test assumptions or decisions rather than agree reflexively.
- **Silence:** defer, batch or suppress nonessential intervention.

An optional **Raw** mode bypasses pedagogical shaping to give a direct answer when requested. The governor should be user-steerable and accountable, not covertly optimize the user according to a model's private theory of flourishing.

**Challenge policy:** Default is measured, relevant challenge—e.g., when evidence conflicts with a declared objective, an assumption is unsupported, or a decision has material downsides. User controls include `direct answer`, `challenge`, `training`, `silence`, frequency, and dismissal. Repeatedly pushing a dismissed suggestion is a failure. A cognitive-mode override does **not** bypass privacy, tool authorization, legal constraints, or third-party rights. Self-model objectives are explicit, tentative, and editable; do not infer a person's ultimate values from engagement metrics.

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
| State → cloud model | Separately authorize inference and outbound disclosure; apply context minimization; log egress metadata | Provider gets the whole vault, or implicit disclosure from model choice |
| Model → tool | Proposal only; independent capability check + confirmation when required | Prompt injection causes send/delete/pay |
| Tool → state | Store results, receipts, failures and reversal options | Agent claims success despite failed action |
| Device → sync | Authenticated device and revocable access; conflict/deletion handling | Lost device restores erased information |
| Stable → experimental | Versioned schema / eval gates / rollback | New model rewrites identity or breaks migration |

**No security claims should be made until the boundary has been tested.**

## 6. Minimal data contracts (conceptual)

| Contract | Essential fields | Responsibility |
| --- | --- | --- |
| `SourceEvent` | id, source, actor, occurred_at, captured_at, consent, classification, payload_ref, retention | What was captured; not automatically believed |
| `MemoryClaim` | id, text/structure, kind, source_ids, confidence, valid_time, status, revision, risk_class | What may be inferred or recalled, not necessarily authoritative |
| `MemoryPromotionDecision` | claim_id, before_status, after_status, approver_or_policy, policy_version, rationale, time, undo_ref | Why a claim became authoritative (or did not) |
| `MemoryPromotionPolicy` | version, eligible_types, prohibited_types, risk_thresholds, approval_requirements | Controls automatic promotion with human override |
| `CloudDisclosureGrant` | id, recipient, purpose, permitted_classes, record_scope, expiry, provider_terms, revocation | What information may leave the local control boundary |
| `ContextBundle` | id, purpose, model_target, included_record_ids, exclusions, policy_version | What a model was authorized to see |
| `CapabilityGrant` | id, subject, capability, resource_scope, expiry, budget, approval, revocation | What an agent may attempt |
| `ActionReceipt` | id, actor, intent, grant_id, request, outcome, evidence, timestamp, reversal | What actually happened |
| `CognitivePolicy` | mode, scope, override, feedback | How to help without overriding agency |

These are **conceptual fields, not frozen schemas**. Stable versions and migration paths become mandatory when code is introduced.

## 7. The first complete user journey (V0 golden path)

1. Capture a spoken or written thought on a device you already own.
2. Store its source, provenance, classification and retention intent in a locally controlled vault.
3. Transcribe or transform it, creating a *proposed*, source-linked claim or task.
4. Independently verify whether model selection and disclosure of the chosen context are allowed; use local recall if not, then optionally route through an approved model.
5. Give an evidence-linked answer and clearly separate fact from inference.
6. Correct, supersede or delete the claim; verify it changes future recall.
7. Export, back up, restore and retrieve it *without requiring the original model provider*.
8. Demonstrate a denied unauthorized tool action and inspect a comprehensible receipt.

**Definition of useful first system:** all eight behaviors work end-to-end in a small, local, single-user workflow. Not necessary initially: autonomous swarms, social graph, elaborate RAG, custom Pocket hardware, phone replacement, cryptographic blockchain infrastructure, or an on-device frontier model.

## 8. Candidate implementation (NOT constitutional)

- **Host / boundary:** founder's user-controlled Mac as canonical first vault; separate local capture queue on iPhone when unreachable. No public internet exposure in V0.
- **Language / API:** Python with a thin HTTP service (FastAPI is one candidate).
- **Durable store:** local SQLite for minimum operational burden *or* locally hosted PostgreSQL for stronger multi-service growth. **Decision open**; decide with migration/backup tests, not ideology.
- **Files / audio:** content-addressed files in a user-owned local vault with metadata in the store; never store secrets or recordings in Git.
- **Indexing:** simple structured lookups / full-text search first; add embeddings only after retrieval evaluations demonstrate the need.
- **Models:** Kimi or another provider through one adapter; local model fallback as capability permits.
- **Security:** OS credential store/key management, encryption where appropriate, network access controlled, separate cloud authorization from inference; documented threat model and clear recovery/key-loss rules before exposure to other devices or providers.
- **Testing:** unit/schema/migration tests and scenario-based evals; no test credentials or personal recordings in repo.

## 9. Evolution channels

- **Stable:** trusted daily-driver; only evaluated upgrades, backup compatibility, easy rollback.
- **Next:** candidate upgrades against a scrubbed or permissioned test corpus; measurable quality, cost, latency, usability and safety.
- **Lab:** speculative world models, memory research, new interfaces, agent frameworks, automated self-improvement and hardware experiments—isolated from sensitive stable state unless specifically approved.

An experiment cannot promote itself to Stable or expand its authority. A governance gate must preserve evaluation records and approval.

## 10. Evaluation framework

Before adding sophistication, measure:

- **Memory:** sourced factual recall, false-memory rate, contradiction handling, staleness, corrections, deletion, unauthorized promotion and recovery from rejected claims.
- **Agency:** user override of cognitive challenge works, unauthorized actions still fail, high-impact actions wait for approval, productivity *and* independent competence.
- **Privacy:** no unapproved context disclosure, no provider receives raw vault credentials, scrubbed egress logs, secure recovery, deliberate retention, tested provider exit.
- **Resilience:** offline core behavior, restore time, migration to a second model and second store.
- **Experience:** speed of capture, task completion, interruptions, unnecessary friction, sense of presence.
- **Economics:** task-level model cost, spending thresholds, accuracy per dollar.

Tests should include negative cases: revoked permission, contradictory old/new memories, source injection, cloud outage, device loss, and malicious imported content.

## 11. Decisions intentionally deferred

See [`OPEN-QUESTIONS.md`](OPEN-QUESTIONS.md). No architecture preference becomes an invariant without testing it against the Constitution. Future architecture decision records (ADRs) belong in `docs/adr/`.

---

## 9. Founding implementation — vertical slice, October 18, 2026

This section describes a **replaceable prototype**, not a locked architecture or a claim of ratified governance. For details see [ADR-0002](docs/adr/0002-first-vertical-slice.md) and [Security Gate](docs/SECURITY-GATE.md).

### Loop implemented

`Browser UI → local FastAPI endpoints → SQLite source records → explicit selected context preview → local evidence or permissioned cloud model adapter → source-linked answer`

The service exposes `/api/memories` (create/list/search), `/api/memories/{id}/correct`, `/api/memories/{id}` (delete), `/api/export`, `/api/import`, `/api/ask`, `/api/status`, `/api/claims` (list/propose/approve/reject/contest/supersede/delete), `/api/restore` (explicitly confirmed trusted restore) and the browser UI. Prototype records are human-entered **evidence**, not automatically authoritative biographical claims. Source-linked `MemoryClaim`s start `proposed` and change status (`approved`, `rejected`, `contested`, `superseded`) only by explicit, recorded human decisions; their support is derived from current, hash-pinned evidence, so corrected sources make them non-authoritative, and forgetting a source forgets the claims derived from it. Ordinary import is untrusted and yields only proposed claims; only an explicitly confirmed trusted restore preserves prior approvals (see [ADR-0003](docs/adr/0003-memory-claim-authority.md)). No model may create an approved claim; no model has a tool-execution capability.

### Boundaries demonstrated

- Selecting a cloud model is separate from approving the transfer of the question and selected source records.
- No implicit bulk context, and sensitive-classified sources are blocked for cloud requests.
- The server, not the UI alone, rejects requests missing an explicit approval.
- Source IDs and original evidence are returned to the interface. Generative model citations are not verified; source evidence can be manually inspected.
- Offline local evidence reads never call a model. API keys are process environment variables.
- SQLite schema export/restore with tombstones supports a first portability smoke test; tombstones from a trusted restore dominate live state, while an untrusted import cannot delete local data. It does **not** guarantee secure removal from backups or forensic images.

### Deliberately unfinished

- Threat-model-reviewed user/device authentication and all-device capture.
- Encryption/key recovery, backup/restore and sensitive-data deletion.
- Automatic claim extraction, risk classes and promotion policy; user goals/intentions, timeline semantics, outcome measurement and cognitive modes.
- Embeddings, sophisticated indexing, trained inference, full agent tool execution and Pocket hardware.

The next milestone is a trusted **memory authority/permissions layer** and real-data security gate, followed by a human-value workflow. The implementation layer may be discarded without changing the Constitution.
