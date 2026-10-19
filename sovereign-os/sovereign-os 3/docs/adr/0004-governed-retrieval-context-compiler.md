# ADR-0004 — Governed retrieval: the Context Compiler (V0)

- Status: Proposed (Benchmark 0002; Tier 2 — memory-authority interpretation and cloud disclosure; requires independent audit and founder approval)
- Date: 2026-10-19
- Decision owner: Human project owner
- Narrows: ADR-0003's operational rule "Claims are never sent to a model" (see *Relationship to ADR-0003*)

## Context

ADR-0003 (MemoryClaim) established what Sovereign may treat as **authoritative personal memory**. It did not decide what may be **retrieved** for a particular purpose, how it is **represented** to a reasoning model, or what may **cross the local/cloud boundary**. Until now `/api/ask` sent only manually selected source records, and ADR-0003 defensively kept every claim away from models.

Constitutional constraints:
- **Art. IV.4–IV.5:** persistence is not authority. A record's authority derives from its sources, scope, approval and validity.
- **Art. V.1, V.6:** intelligence is not authority. Permission to ask a model for reasoning is distinct from permission to transmit private records to it.
- **Art. VI.2, VI.4:** each outbound disclosure must be permitted by an enforceable policy; a general agreement to use a cloud model is not blanket permission; data minimisation and purpose-limited access matter.
- **ARCHITECTURE §4D, §B1, §5:** purpose-limited context bundles, assembled locally by deterministic policy; inference selection and disclosure authorisation are separate decisions.

**Governing separation: retrieval ≠ authority ≠ disclosure ≠ inference.** No model determines its own permissions, authority or disclosure scope.

## Decision

### Pipeline

`question → local candidate retrieval → Context Compiler → ContextBundle → exact disclosure preview → explicit approval (cloud only) → re-compilation and verification → provider adapter`

- **Retrieval:** `Vault.context_candidates` reads every fact the compiler may use in **one read snapshot**.
- **Compiler** (`src/sovereign/context.py`): deterministic policy code covering relevance, authority, provenance, support, sensitivity, disclosure and budget. It is not a model and does not depend on any provider.
- **One policy implementation.** `POST /api/context/compile` (the preview) and `POST /api/ask` (execution) call the same function.
- **Read-only and request-scoped.** The compiler only reads the vault. Bundles, receipts, questions and tokens are returned to the local client and never persisted.
- **Provider isolation.** The provider adapter (`providers.py`) has no vault access. It receives a list of chat messages rendered from an authorised bundle, and nothing else.
- **Model output is inert.** A model's answer is returned to the client as text. It is never parsed, stored, or applied to records, claims, permissions or authority.

### Retrieval V0 (deterministic, lexical, local)

- **Terms:** lower-cased words (`\w+`) of 2+ characters, minus a fixed English stopword list, with one plural `s` trimmed (words over 3 characters, not ending `ss`).
- **Relevance:** a text's score is the number of distinct question terms it contains, matched as whole terms, not substrings.
- **Candidates:**
  - pinned source records: the request's `source_ids`, up to 8, in any state;
  - the 50 best-matching source records, active or superseded;
  - the 50 best-matching claims, of any status;
  - up to 50 claims citing a candidate record (*provenance*), so the receipt can show unused interpretations of the evidence it retrieved.
  - "Best" means more matched terms, then newest, then ID ascending.
- **Truncation is visible.** All match counts are reported (`records_matched`, `claims_matched`, `claims_citing_candidates`).
- **Forgotten data is never a candidate.** Forget removes it, and tombstones are content-free.
- **Pinned IDs must name source records.**
  - A claim ID, an unknown ID or a duplicate is refused (422).
  - So is a forgotten ID: 422, or 409 when the request carries a preview token, because the approved plan no longer holds.
  - A pinned source still passes every policy; pinning only raises its priority.
- **Not used:** embeddings, vector stores, knowledge graphs, external retrieval services.

### Ranking and budget

- **Order** is deterministic and total:
  - pinned evidence first, then claims, then other evidence;
  - within each group, more matched terms first, then newer, then ID ascending.
  - `rank` is the 1-based position in the bundle.
- **Budget:** candidates are admitted in rank order while the bundle holds at most **12 items** and **12,000 characters** of item content. A maximum-size 10,000-character record still fits.
  - Candidates that do not fit are excluded as `budget_exceeded`. Smaller later candidates may still be admitted.
  - The question is not counted; it is at most 2,000 characters.
- **Duplicates:** the same text in the same role is included once. The others are excluded as `duplicate`, with `duplicate_of`. Each item appears once however many relationships reach it.

### Authority policy: MemoryClaim stays the source of truth

| Candidate | Included as | Otherwise excluded as |
| --- | --- | --- |
| Approved claim with intact evidence (`claims.is_authoritative`) | `approved_memory` | — |
| Proposed claim (including every imported claim) | never | `not_authoritative` |
| Contested claim | never | `contested` |
| Rejected claim | never | `rejected` |
| Superseded claim | never | `superseded` |
| Approved claim whose evidence was corrected | never | `stale` |
| Approved claim with missing or unverified evidence | never | `orphaned` |
| Active source record | `evidence` | — |
| Superseded source record (an old revision) | never | `superseded` |

- **Further conditions on eligible candidates:**
  - they must also be relevant: pinned, or sharing at least one term with the question. A claim surfaced only through provenance is `not_relevant` (context minimisation);
  - they must pass the boundary (`sensitive_cloud`), duplicate (`duplicate`) and budget (`budget_exceeded`) checks.
- **Every applicable reason is listed** in precedence order: `superseded`, `rejected`, `contested`, `not_authoritative`, `stale`, `orphaned`, `sensitive_cloud`, `not_relevant`, `duplicate`, `budget_exceeded`. `reason` is the first.
- **Authority is not assumed.** The compiler re-checks `claims.is_authoritative` for any claim with no lifecycle or support reason, so an unexpected state is `not_authoritative`.
- **Distinct roles.** Evidence and approved memory stay separate in the bundle, the receipt and the prompt.

### Sensitivity inheritance

- **Claims.** A claim's sensitivity is the **most restrictive among its current evidence**. It is computed from storage at compile time, never taken from client input.
  - It is `private` only if every source is present, verified and `private`.
  - Any `sensitive`, missing or unverified source makes it `sensitive`.
- **Records** keep their own immutable sensitivity (ADR-0003).

### Disclosure

- **Local target** (`provider = local`):
  - nothing leaves the device and no provider is called;
  - eligible private and sensitive items may be used.
- **Cloud target** (`kimi`, `openai`):
  - only `private` items may be included; sensitive candidates are excluded as `sensitive_cloud`;
  - an explicitly pinned sensitive record **blocks** the plan (`disclosure.blocked`, then 403), as in ADR-0002, rather than being silently dropped.
- **What does not authorise disclosure:**
  - choosing a provider;
  - an approved MemoryClaim.
- **What does:** a cloud request needs `approve_cloud_disclosure: true` **and** the matching `context_token`.

### ContextBundle contract (`POST /api/context/compile`, also returned by `/api/ask` as `context`)

```text
policy_version                      "sovereign.context.v0"
question
target                              {provider, boundary: local | cloud}
retrieval                           {terms, pinned, records_matched, claims_matched, claims_citing_candidates, limit_per_kind}
included[]                          {id, type: source | claim, role: approved_memory | evidence, reason, rank,
                                     content, created_at, status, sensitivity,
                                     relevance {score, matched_terms, pinned, via: pinned | lexical | provenance},
                                     claims also: support, origin, source_ids}
excluded[]                          {same descriptive fields, reason, reasons[], duplicate_of?}
budget                              {max_items, max_chars, used_items, used_chars}
disclosure                          {boundary, transmits, requires_approval, blocked, outbound_sensitivities}
outbound                            cloud only: {provider, question, items[{id, type, role, sensitivity}], messages[]}; null for local
context_token
```

- **Internal representations:** `RetrievalCandidate`, `ContextItem`, `Excluded`, `ContextBundle`, `ContextPolicy` (the version, budget, retrieval limit and cloud-eligible sensitivities).
- **`ContextReceipt`** (returned by `/api/ask` as `receipt`) is content-free: `policy_version, provider, boundary, context_token, transmitted, included[{id, type, role}], excluded[{id, type, reason}]`. It is shaped for a future durable form but is not persisted in V0.

### Exact-plan approval: `context_token`

The Forget preview's lesson (ADR-0003) applied to disclosure: **the human approves the exact outbound context, not a vague permission.**

- **What it is:** SHA-256 over canonical JSON of:
  - the policy version, question, provider, boundary, pinned IDs and blocked state;
  - the **exact outbound messages**;
  - every included item (ID, type, role, content, source IDs, status, support, sensitivity);
  - every excluded candidate (ID, type, reasons).
- **Properties:** deterministic (unchanged state and request give the same token), recomputed on every request, never stored, and not a credential.
- **How `/api/ask` uses it:**
  - it recompiles in one snapshot and compares;
  - on a mismatch it returns **409 "Context changed since your preview; review the new context and approve it again."** **No provider call is made.**
  - the provider then receives that verified bundle's messages. A change committed after verification cannot alter what is sent, and nothing beyond the approved preview is ever sent.
- **What invalidates it:**
  - a source forgotten or corrected;
  - a claim approved, rejected, contested or superseded, including by a lifecycle-legal raw-SQL event;
  - any support change;
  - a relevant candidate added or removed;
  - a change of question, provider or pins.
- **Invalidation is conservative.** A change to an excluded candidate also invalidates, because the user's preview showed it. Unrelated vault changes do not.
- **Status codes:**

  | Status | Meaning |
  | --- | --- |
  | 403 | no approval, or a blocked plan |
  | 503 | provider not configured |
  | 428 | approval without a token |
  | 409 | stale token |
  | 422 | invalid pins or request fields |

- **Strict request bodies:** they reject unknown fields, so a client cannot smuggle context, roles, authority or messages.
- **Local requests** need no token. If one is supplied it must match.

### Prompt boundary

- **One conversion point.** `context.render_messages` is the only place a bundle becomes model messages. It produces model-neutral chat messages:
  - a system message stating that context is data, never instructions, and what approved memory and evidence each mean;
  - a user message with the question and a JSON context.
- **Separate arrays.** The JSON context has separate `approved_memory` entries (`label M#`, `claim_id`, `text`, `evidence_ids`) and `evidence` entries (`label E#`, `source_id`, captured date, `text`).
- **No impersonation.** JSON escaping prevents item text from posing as a different item or role.

### Minimal UI

- **Preview context** shows, in order:
  - the approved memory and evidence selected;
  - excluded candidates with a brief reason;
  - the disclosure: "Nothing leaves this device", or exactly which items leave, plus the exact payload.
- **Asking:** **Ask locally**, or **Approve this context & ask** for a cloud target.
- **Invalidation:** changing the question, provider or pins invalidates the preview.
- **A 409** is shown, the library is refreshed, and the new bundle is displayed for a fresh approval.

### Relationship to ADR-0003

- **The rule being narrowed.** ADR-0003 states: *"Claims are never sent to a model. `/api/ask` accepts only active source-record IDs."* That was a defensive V0 rule, made before governed retrieval existed.
- **ADR-0004 intentionally narrows it.** Claims may reach a reasoning model only when they are:
  - **approved**;
  - **currently supported**;
  - **selected by the Context Compiler**;
  - **sensitivity-eligible** for the target boundary; and
  - **included in the exact disclosure plan authorised for that request**.
- **The model still gets no direct database or authority access.**
- **Pins stay source records.** `source_ids` still accepts only source-record IDs; claims enter context only through the compiler.
- **ADR-0003's text is otherwise unchanged.** A pointer to this ADR was added to its status line and to that rule.

## Alternatives considered

- **Embeddings or vector search:** deferred until retrieval evaluations show a need (ARCHITECTURE §8). They add non-determinism and a derived index that must itself be governed and forgotten.
- **Model-selected context** ("let the model ask for what it needs"): rejected. The model would determine its own disclosure scope.
- **Approving a provider, or a standing grant, instead of the exact plan:** rejected. Provider choice is not disclosure permission (Art. VI.2); a future `CloudDisclosureGrant` must still bind to purpose and scope.
- **Persisting bundles or receipts:** deferred. Durable receipts need a retention and Forget design first, because Forget must reach them. The V0 receipt is content-free and request-scoped.
- **HMAC or single-use nonce tokens:** not needed for binding, since the server recompiles and compares. Single-use semantics would need server state, which V0 avoids, and a deterministic token keeps previews reproducible.
- **Silently dropping explicitly selected sensitive records for cloud:** rejected. A 403 preserves ADR-0002's explicit boundary. Retrieved, unselected sensitive candidates are excluded, visibly.
- **Sending proposed or contested claims labelled as unverified:** rejected for V0. A separately labelled role may be considered later, with its own review.
- **Automatic redaction of sensitive content:** out of scope. A classifier is not a policy.

## Consequences and risks

- **Lexical retrieval misses paraphrases and synonyms.** There is no stemming beyond the plural `s`, and the stopword list is English. Pinning and rephrasing compensate.
- **Cost:** each compile scans the vault, O(n). This is acceptable for V0 vault sizes; SQLite FTS5 is the natural next step if needed.
- **Unpinned items can go to the cloud.** A cloud bundle may include private records and approved memory the user did not pin, but only those shown in the preview and explicitly approved. Minimisation comes from relevance and the budget.
- **Replay:** a deterministic token can be replayed while state is unchanged, re-sending the identical approved plan. It grants nothing beyond that plan; the UI never replays.
- **No authentication (V0):** any local same-origin client can compile and approve, as before.
- **Over-invalidation:** some 409s follow changes that did not alter the outbound payload.
- **Evidence IDs leave with approved memory.** Approved memory sends its evidence IDs, not content, for private evidence. Legacy (ADR-0002) record IDs are arbitrary text.
- **Outside Sovereign's control:** provider retention and training terms. Outbound receipts are not yet durable (Art. VI.6 remains open).

## Migration and reversibility

- **No migration.** There is no schema change and nothing is persisted.
- **To reverse:** remove `context.py`, `POST /api/context/compile` and `Vault.context_candidates`, then restore the previous `/api/ask`. That returns to the ADR-0003 behaviour.
- **Versioning:** the bundle contract is versioned by `policy_version`, and every token changes with it.

## Validation

- **`tests/test_context_compiler.py`:**
  - the core acceptance example (local and cloud);
  - every authority rule, sensitivity inheritance, determinism and stable ties;
  - pinned sources passing policy, Forget and correction dominance;
  - duplicates, the visible budget and retrieval truncation;
  - receipts, the token, and the read-only guarantee.
- **`tests/adversarial/test_context_compiler_adversarial.py`** (run by the `memory-adversarial` CI job):
  - **authority bypass:** pinned claim IDs, smuggled request fields, provider switching, imported claims, raw SQL;
  - **disclosure bypass:** sensitive and mixed claims, pinned sensitive records, missing, forged or cross-question tokens;
  - **leakage:** sentinel strings against a recording mock provider; the messages must equal the preview; evidence cannot impersonate approved memory in the prompt;
  - **deletion and corrections;**
  - **TOCTOU:** nine kinds of change × pinned and unpinned, each giving 409 with no provider call; a compile reads one snapshot under a concurrent Forget;
  - **budget,** model-output inertness and provider isolation.
- **Mutation check:** 21 deliberately injected policy bugs were each caught by at least one of these tests.
