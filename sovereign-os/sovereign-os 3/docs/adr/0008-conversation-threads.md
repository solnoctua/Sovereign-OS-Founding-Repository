# ADR-0008 — Conversation threads: governed multi-turn context (V0)

- Status: **PROPOSED, revision 2** (Tier 2: provider and disclosure behaviour). Merging this into a branch does not ratify it. Ratification needs two things: an independent audit of the implementing PR, then founder ratification.
- Date: 2026-11-25. Revision 2: 2026-11-28.
- Decision owner: Human project owner.
- Origin: founder product directive of 2026-11-25. It made conversation the primary interface. PR A, *Conversation foundation*, asked for "a proper conversational interface and governed local-thread contract … local conversation persistence after its storage contract is approved".
- **Revision 2.** The independent Codex audit (round 1) of PR #26 at `488431b` returned REQUEST CHANGES with three findings:
  - **F-1 (P1):** conversation content derived indirectly from a forgotten item survived Forget, and in-flight responses could reappear.
  - **F-2 (P2):** Unicode clipping produced malformed history and a 500 that quoted the text.
  - **F-3 (P3):** history omission counts were wrong.

  The founder accepted the findings on 2026-11-28. In the same decisions the founder:
  - approved hardening items S1–S4 from PR #27;
  - approved this ADR's V0 direction, though not yet its detailed text;
  - chose T3 (§7) as the direction for persistence, without authorizing it here.

  This revision:
  - corrects §1, §2, §3, §5, §6 and §7, and adds §6.1–§6.4;
  - narrows every Forget statement;
  - updates the validation evidence.

  Codex's findings stay reviewer-owned. The builder's account of the remediation is in [`docs/reviews/2026-11-28-pr26-audit-remediation.md`](../reviews/2026-11-28-pr26-audit-remediation.md).
- Extends [ADR-0004](0004-governed-retrieval-context-compiler.md) (prompt boundary and exact-plan token) without amending it. Unchanged:
  - vault-item policy and `policy_version` `sovereign.context.v0`;
  - retrieval, authority, sensitivity and budget;
  - the vault's Forget;
  - the single-question output, byte for byte.

## Context

Today `/api/ask` sends a cloud model a system message plus one user message, which holds the question and the compiled context (ADR-0004). Sovereign answers one question at a time, and every question starts from zero.

The founder wants to talk with Sovereign as naturally as with a chat assistant, across many turns and several conversations. Meanwhile its second brain supplies relevant, governed memory to each turn.

For a turn to work, the model must see the earlier exchanges. Those exchanges are personal content leaving the device, so under ADR-0004 they are a disclosure. They must appear in the exact preview, be bound by the approval token, and be approved per request.

Earlier replies may also come from a different provider than the next turn's target (model portability). The founder requires that carryover to be visible and explicitly approved: "no unapproved carryover of prior cloud conversations to another provider".

These constraints apply unchanged:

- **Retrieval ≠ authority ≠ disclosure ≠ inference** (ADR-0004; ADR-0005 §4.2). A conversation must not widen what the compiler retrieves or admits.
- **Model answers are never persisted automatically** (ADR-0004 decision 6). **Query text is never persisted** (ADR-0005 §3 class 7, §6.4).
- **A new retrieval method is a new `policy_version`** (ADR-0005 §6). D15 (ADR-0007, PROPOSED) has claimed `sovereign.context.v1`.
- **Forget reaches every derived store Sovereign manages** (ADR-0005 §4.5). A store outside the vault needs its own defined Forget behaviour before it is considered (ADR-0005 §5).
- **No sensitive personal data** until the Security Gate thresholds are met (`docs/SECURITY-GATE.md`, NOT PASSED).

## Decision

### 1. A conversation is request-scoped rendering, not memory

A conversation turn is an ADR-0004 request with an optional `conversation` object:

```text
POST /api/context/compile   and   POST /api/ask
{ question, provider, source_ids, [approve_cloud_disclosure, context_token],
  conversation: { history: [ {role: "user", content}, {role: "assistant", content, provider: "kimi" | "openai"}, … ] } }
```

- **History.** `history` holds the active conversation's earlier complete cloud exchanges, oldest first. Each exchange is the person's message followed by the reply it received, and the reply names the cloud provider that wrote it. Strict request bodies reject any other field, role or shape with a 422.
- **No conversation object.** Without `conversation`, a request is ADR-0004's single question, byte for byte: the same messages, bundle, receipt and token. Golden digests in `tests/test_conversation.py` check this, and Benchmark 0003 `--check` is unchanged.
- **Retrieval reads the current message only.** Earlier turns never widen retrieval, admission, ranking or budget. `included`, `excluded`, `retrieval` and `blocked` are identical to a single-question compile of the same message (tested). Retrieval that uses conversation context, for follow-ups such as "what about its battery?", changes relevance. That belongs to a later PR with its own `policy_version` (ADR-0005 §6).
- **Earlier turns' compiled context is never replayed.** Only conversation text travels: what the person wrote and what the model replied. Memory and evidence are compiled fresh for each turn from current state. So a record that has since been forgotten, corrected, contested or made ineligible is never re-sent *through context*. Its text can still travel inside an earlier reply that quoted it; §6.2 and §6.4 cover that case.
- **Local turns stay local.** A local-evidence turn calls no model and never becomes part of a cloud model's history. A reply in `history` must name a cloud provider; `local` is refused.

### 2. A separately versioned conversation policy

`ConversationPolicy` (`context.CONVERSATION`, `sovereign.conversation.v0`) governs conversation text only:

| Constant | Value | Meaning |
| --- | --- | --- |
| `max_request_messages` | 64 | earlier messages one request may carry (422 beyond) |
| `max_message_chars` | 16,000 | Unicode code points in one earlier message (422 beyond) |
| `max_history_messages` | 40 | earlier messages sent at most |
| `max_history_chars` | 32,000 | code points of earlier messages sent at most; the latest exchange always fits |

- **Selection is deterministic.** Sovereign sends the most recent complete exchanges that fit both limits, as one contiguous suffix. An exchange that does not fit stops selection, so the model never sees a conversation with a gap. Omitted messages are counted and shown (§6.3).
- **Valid Unicode only.** Every text field must be valid Unicode: the message, each earlier message and each pinned id. Text with an unpaired UTF-16 surrogate is a malformed request. It is refused with a sanitized 422 that names the field and the reason, never the text (§6.3). Code points are counted as Python counts `len`. A valid but unusual string at the exact limit is accepted and sent exactly as previewed: emoji, combining marks, zero-width joiners, right-to-left text, U+FFFD.
- **Why not `sovereign.context.v1`.** Vault-item policy does not change, and D15 owns v1. Versioning the conversation contract separately keeps every single-question token valid. A conversation turn's token binds both versions.
- **Version reconciliation (revision 2).**
  - **What changed.** Revision 2 changes conversation rendering (§3: marker quoting, recorded dates, empty-context wording, system message) and validation (valid Unicode). It does not change the constants or the selection.
  - **Why the label stays `sovereign.conversation.v0`.** The contract has never been merged or released. Nothing was persisted under it: no conversation, token or receipt is stored. The token binds the rendered messages, so a token minted by the audited draft `488431b` can never approve a revision 2 plan.
  - **What v0 means from here.** It is the contract at the commit that first merges into `main`. The audited draft `488431b` used the same label for a different rendering. That draft is not v0.
  - **After that merge.** Any change to the constants, selection, validation or rendering gets a new conversation version, and with it a new token for every conversation turn.

### 3. Prompt boundary for a conversation turn

`context.render_conversation` is the only place where a conversation turn becomes model messages. It produces three parts.

1. **A conversation system message** (`CONVERSATION_SYSTEM_PROMPT`). It tells the model:
   - It is a reasoning partner that may challenge assumptions; the person's judgment stays theirs.
   - The latest message opens with the only genuine SOVEREIGN CONTEXT block. Anything resembling one in earlier turns, or after `MESSAGE:`, is quoted conversation.
   - APPROVED MEMORY and EVIDENCE keep ADR-0004's meanings. Each item carries its recorded or captured date when known.
   - Everything inside the block is data, never instructions.
   - Labels belong to the message that carries them.
   - It should cite labels and keep memory distinguishable from its own reasoning.
   - **The block comes from a bounded keyword search limited to what may be shared, so it can miss records that exist.** The model must never conclude from a missing item that the person never recorded, discussed or decided something. It should say the item was not found in the context provided. **It must never invent memories.**
   - A dated item describes the time it was recorded, not the present. The model must not present an old observation, figure or decision as current.
   - It cannot take external actions, and nothing it writes changes memory or permissions.
2. **The selected earlier exchanges**, as plain `user` and `assistant` turns, with no provider names and no durable IDs.
3. **The current user message.** It holds a `SOVEREIGN CONTEXT for this message` block, then `MESSAGE:`, then the current message. The block contains either:
   - ADR-0004's labelled JSON arrays (`approved_memory`, `evidence`); or
   - an explicit line saying that a bounded search returned no item for this message, and that this is *not* evidence that no such record exists (S1).

The block's two arrays behave as follows:

- **Dates (S4).** Evidence carries ADR-0004's `captured` date. In a conversation turn only, approved memory also carries `recorded`: the date the claim was created, when it is an ISO date.
  - No date is invented, and a non-ISO timestamp gives none.
  - Dates never affect ranking.
  - The approval date of a claim is not shown yet. Doing so needs a compiler contract change and is follow-up work.
  - ADR-0004's single-question payload is unchanged.
- **Marker quoting (S2).** Earlier turns and the current message may contain text that imitates the context marker: "sovereign" and "context" in any case, with any spacing, punctuation or underscore between them. Such text is rewritten to `Sovereign context (quoted text)`. Two consequences follow:
  - Only the server-compiled block that opens the latest message reads as context.
  - The rewritten text is what the preview shows, the token binds and the provider receives.

  This is visible neutralization, not a security boundary. A model can still be misled by text that avoids the pattern, such as spaced letters. The structure, and the system message's statement that only the opening block is genuine, carry that case.

Durable Sovereign IDs never enter provider messages (unchanged), and the reply's provider attribution stays local.

### 4. Exact-plan approval covers the conversation

- **The token binds the whole conversation.** In addition to ADR-0004's binding, it covers:
  - the conversation policy version;
  - every earlier message the request carries, sent *or* omitted, with its role and claimed provider;
  - the sent and omitted counts.

  After the preview, any of these is a 409 with no provider call (tested): an edit, removal, addition or re-attribution of an earlier message, or a switch between a single-question plan and a conversation plan.
- **The preview shows it.** `outbound.messages` is the exact payload, including earlier turns. The bundle's `conversation` section reports `history_messages`, `sent_messages`, `omitted_messages`, `sent_chars`, `replies_by_provider` and **`carryover`**. Carryover lists the replies written by a provider other than the target. It is never automatic: it is shown in the preview and leaves only under that exact approval.
- **The receipt stays content-free.** It adds the conversation policy version and the sent and omitted counts.
- **Approval stays per request.** A lower-friction session consent would be a separate, reviewed policy decision (founder directive).

### 5. Client-held history cannot prove its own provenance

The browser holds the conversation and sends it with each request. The server cannot verify who wrote an earlier message, so it cannot tell:

- whether a "reply" came from the named provider, or from any model;
- whether it was edited after it arrived;
- whether it quotes an item that has since been forgotten.

Provider attribution and carryover are therefore the client's claims. They are bound into the token and shown so the person can judge them; Sovereign never verifies them.

This grants no authority. Earlier messages are only rendered as conversation text, which the person sees in the exact preview and approves. They are never memory, evidence, approved claims, policy or permissions, and model output stays inert.

A forged or hostile earlier reply can mislead the model, as any text the person types can. It cannot widen retrieval, admission or disclosure of vault items. Tests cover hostile history, hostile replies and forged context blocks.

### 6. This slice persists nothing

**Conversations live only in the open browser tab's memory.**

- The server stores no conversation, message, reply, bundle or token.
- The UI uses no `localStorage`, `sessionStorage`, IndexedDB, cookies or caches. A policy test checks the UI source.
- Reloading or closing the tab ends every conversation, and the UI says so.

#### 6.1 Two lifetimes

Once a provider receives an approved request, that transmission is outside Sovereign's control. No action in Sovereign retracts it: Forget, clearing, deletion and reload all leave it in place. What Sovereign controls is local state:

- what the tab shows;
- what it keeps;
- what it will offer for a later request.

Every guarantee below is about local state only. The UI says so in each clearing notice, and in the confirmations for Forget and for deleting a conversation.

#### 6.2 Conservative suffix invalidation (F-1)

Sovereign cannot trace every way later text repeats earlier text. A reply can quote, paraphrase or build on an earlier reply without retrieving anything. So when an item a turn *used* becomes unusable, the tab clears that turn **and every later turn in the same conversation**. That includes:

- the person's messages;
- replies;
- stored context;
- previews and pending approvals;
- requests in flight.

Earlier turns stay. One content-free notice takes the cleared turns' place. It states how many messages were cleared and why. It also says that copies already sent to a provider are outside Sovereign's control.

Cleared turns are never shown, reused, retried, regenerated or offered as history again.

| Operation in this tab | What is cleared |
| --- | --- |
| Forget a source record (with the claims Forget removes with it) | In every conversation, from the earliest turn whose compiled context **included** a forgotten record or claim, onwards |
| Delete a claim | From the earliest turn whose context included that claim, onwards |
| Trusted restore whose backup carries record or claim tombstones, or that forgets claims | Every conversation in the tab, from its first turn. A restore can delete records, and the tab cannot tell which turns used them |
| Delete a conversation | That conversation, including its in-flight requests |
| Cancel, or edit the last message | That turn |

- **Kind-qualified keys.** Each turn keeps the kind-qualified keys (`record:<id>`, `claim:<id>`) of the items it used and listed, apart from its displayed context. A record and a claim can share an id, and a later Forget still finds a turn whose display an earlier Forget already removed.
- **Used versus listed.** The trigger is *used*: the item was in `included`, so its text reached the model.

  If a turn only *listed* a forgotten item (in `excluded`, so its text was not sent), the turn keeps its message and reply. It does lose its stored preview and context display.

  Every pending review is compiled again, so its preview reflects current state.
- **Not triggers.** Corrections, contest, reject and supersession clear nothing. They are not deletions: the earlier version stays in the vault's history until it is forgotten. Every later turn compiles fresh context from current state.

#### 6.3 Asynchronous completions are fenced; counts are honest; text is valid

- **Sequence fence.** Every local search, preview and model request a turn starts carries the turn's sequence number. A completion is accepted only if all three still hold:
  - the conversation still exists;
  - it still holds that turn;
  - the turn's number is unchanged.

  Clearing, cancelling, editing, deleting, and any newer preparation of the same turn all move the number on. A completion that arrives late is therefore dropped before it touches state: it never appears, enters later history, or becomes the turn's preview. Typical late arrivals are a reply after a Forget, a preview after a Forget, a reply after the conversation was deleted, an older compile after a newer one, and a regeneration after its turn was cleared.

  A completion whose own context used an item forgotten meanwhile clears its suffix on arrival. A preview whose context lists one is compiled again.

  Completions that return out of order land in their own conversation, whichever one is on screen. A request already transmitted cannot be recalled (§6.1). Its reply is simply never accepted.
- **Two kinds of omission (F-3).** The browser offers the server at most `max_request_messages` (64) of the most recent eligible earlier messages. The server then applies `max_history_messages` and `max_history_chars`. The review shows:
  - the messages sent;
  - the total left out, split into messages "left out by this browser before the request (counted here, not verified by Sovereign)" and messages left out "by Sovereign's conversation budget".

  Audit case: 80 earlier messages; the browser sends 64 and the server includes 40. The review reads "40 earlier messages" sent and "40 older messages … are not sent: 16 left out by this browser … and 24 by Sovereign's conversation budget".

  The browser's count is local UI accounting. It is not sent, bound or verified. The exact outbound payload stays authoritative for what is transmitted.
- **Clipping (F-2, S3).** An earlier message longer than `max_message_chars` is shortened in the browser *before* the preview. Clipping works as follows:
  - Lengths are counted in code points, as the server counts them.
  - Any unpaired surrogate is first replaced with U+FFFD.
  - The head and the tail are kept around a visible marker, `…[N characters omitted by Sovereign]…`.
  - Cuts fall on grapheme-cluster boundaries (`Intl.Segmenter`, where the browser has it), never inside a surrogate pair.
  - The result is within the bound, and clipping it again changes nothing.

  The review says how many earlier messages were shortened. The clipped text is what the preview shows, the token binds and the provider receives.
- **Malformed input (F-2).** A request with an unpaired surrogate in any text field is refused with a 422 at validation. The same applies to undecodable bytes. A repeated attempt gets the same 422.

  Validation errors never contain submitted values: Sovereign replaces FastAPI's default handler, which echoes `input`. Codec errors are mapped to a fixed message.

  A model reply containing an unpaired surrogate has it replaced with U+FFFD before the response is encoded. So the reply returns intact and is valid history for the next turn.

#### 6.4 What is and is not protected

Protected, in the open tab:

- **The tracked chain.** Once a Forget, claim deletion or trusted restore is committed *through this tab*, no turn from the first affected one onwards can be shown or reused. That includes in-flight completions, pending previews, regenerations and carryover to another provider.
- **Laundering through replies, within the chain.** A later reply that repeats a forgotten item's text cannot re-enter history through the chain, because the whole suffix is cleared.

Not protected:

- **Dependencies Sovereign cannot see.** Sovereign does not identify semantic dependencies in arbitrary language. Some turns are kept because they precede the first turn that used the item, or because they only listed it, yet they may still contain related text:
  - text the person typed or pasted;
  - the model's general knowledge;
  - a paraphrase in a conversation that never used the item.
- **Deletions made elsewhere.** A Forget made in another tab, through the API directly, or by an earlier session does not reach this tab's conversations. The tab learns only of the Forgets it commits itself. Server-held conversations (§7, T3) are the remedy.
- **Copies outside the tab.** These are outside Sovereign's control:
  - text copied out with *Copy*;
  - screenshots;
  - the browser's own memory before garbage collection;
  - the provider's copy.
- **Model behaviour.** Within a kept turn, text an earlier reply quoted returns as an `assistant` turn, and the model may treat it as its own words. This affects model behaviour only, never Sovereign's authority or disclosure.

The tab is not a managed store, and none of this is a deletion guarantee.

There is no path from a conversation to memory in this slice. A dropped completion therefore cannot become a memory candidate, and PR E's contribution workflow must keep that property.

### 7. Persistent conversation storage: direction chosen, not decided here

Remembering conversations across reloads and years is a new class of personal state: the person's own messages plus model output. ADR-0005 §3 has no row for it, so it needs its own approved storage contract.

| Option | What | Forget | Cost and risk |
| --- | --- | --- | --- |
| **T1** (this ADR) | Tab memory only | Nothing persisted | Conversations vanish on reload; no retention or Forget risk; deletions made elsewhere do not reach the tab (§6.4) |
| **T2** | A separate local SQLite conversation store beside the vault | Not atomic with the vault: a purge after each Forget, a startup reconciliation against vault tombstones, and a read-time filter so forgotten content is never shown or sent again | ADR-0005 §5 asks such a store for its own Forget design; cross-file windows; a separate backup story |
| **T3** | Conversation tables inside the vault (schema 6, triggers, ADR) | Atomic: the Forget transaction removes every turn whose context or receipt cited a forgotten item, and its suffix | A Tier 2 schema migration and a backup-format decision (export or exclude); the strongest Forget guarantee; consistent with ADR-0005 D6 |

**Founder decision of 2026-11-28: T3 is the intended direction.** This is not authorization to implement persistence in PR #26, which stays T1. A separate Tier 2 schema and storage contract (PR A2) must resolve these points before any conversation is stored:

- threads and messages;
- conversation versus canonical-memory authority;
- the classification of model output;
- sensitivity and retention;
- atomic deletion of known dependencies;
- indirectly derived content, including whether §6.2's suffix rule carries over;
- export and restore semantics;
- storage bounds;
- historical corrections;
- deletion of one conversation;
- deletion of a source cited by many conversations;
- cached summaries and derived indexes;
- reconciliation with ADR-0005's rule that query text is never persisted.

Putting a transcript in SQLite does not by itself solve transitive Forget.

Under any option:

- Conversation history is never canonical memory or authority.
- It is not a retrieval source for the Context Compiler without its own policy version and evaluation.
- Model replies stay model output. A reply becomes memory only through PR E's governed contribution workflow, either as a `proposed` claim with `origin = model` or as a record the person chooses to keep.
- Retention, deletion, export and Forget are specified before any real conversation is stored.
- The Security Gate thresholds apply.

## Alternatives considered

- **Bump `sovereign.context.v0` to v1 for conversations.** Rejected. Vault-item policy is unchanged, D15 owns v1, and every single-question token would change for no disclosure reason.
- **Bump the conversation version for revision 2.** Not needed before the first merge (§2, version reconciliation).
- **Replay earlier turns' full rendered messages, context included.** Rejected. It would re-disclose context compiled under an earlier state, since forgotten, corrected or made ineligible, under a new approval.
- **Render history as data inside the JSON context instead of as chat turns.** Rejected for V0. Models converse markedly better with native turns, and history is the person's own conversation, not vault evidence. The cost, that text from an earlier reply is read as the model's own words, is listed under *Consequences and risks*.
- **Redact only the replies that used a forgotten item.** This was the audited draft's behaviour. Rejected by the founder after F-1: a later reply can repeat a redacted one without using the item.
- **A model-generated semantic dependency graph between turns.** Rejected for V0 (founder decision). Its correctness is hard to establish. Conservative suffix invalidation is simple, comprehensible and testable.
- **Server-held threads, in process or on disk.** Deferred to §7. Any server retention of question text needs an approved storage contract.
- **Browser storage (`localStorage`, IndexedDB).** Rejected: plaintext outside the vault, unreachable by Forget, export or restore.
- **Using earlier turns for retrieval.** Deferred. It changes relevance, so it needs its own `policy_version`, a Benchmark 0003 evaluation and founder approval.

## Consequences and risks

- **Gained:**
  - multi-turn conversations, several per session;
  - fresh governed memory for each turn;
  - a visible, bound disclosure of earlier turns;
  - model portability within a conversation under explicit approval.
- **Carryover is real disclosure.** Switching provider sends the earlier conversation to the new one once approved. That includes replies written by another provider, which may paraphrase private context approved for that provider. The preview names the carryover; the person decides.
- **Forget can clear more than strictly necessary.** Suffix invalidation removes every turn after the first one that used a forgotten item, including turns that did not depend on it. The person loses that part of the conversation in the tab. A notice says why.
- **Laundering through replies** is limited to kept turns, and is listed in §6.4.
- **Label collisions.** `E1` in an earlier reply referred to that turn's context. The system message says so, but a model may still conflate the two.
- **Approval friction.** Every cloud turn still needs one review and approval. Lower friction is a separate policy decision.
- **Cost and latency grow with history**, up to 32,000 code points of earlier turns per request. Streaming, usage and cost reporting belong to the provider PR (B).
- **Reload loses conversations** until §7 is implemented.
- **Follow-up questions** such as "why did we change it?" may retrieve nothing new, because retrieval reads only the current message. The model still has the earlier exchanges, and the empty-context line tells it that a miss is not absence.

## Migration and reversibility

- **No schema change; nothing is persisted.** To reverse, remove these: `conversation` from the request models, `ConversationPolicy`, `render_conversation` and the conversation UI. Single-question behaviour is already byte-identical, so nothing else changes.
- **Versioning.** The conversation contract is versioned by `sovereign.conversation.v0`, as reconciled in §2.

## Validation

Revision 2, at the head of PR #26 after remediation.

- **`tests/test_conversation.py`** (46 tests) covers:
  - ADR-0004 single questions byte-identical to golden digests computed on `main` at `ab93036`;
  - separate policy versions;
  - rendering order and the context block, with recorded dates (S4) and no invented date for a non-ISO timestamp;
  - the empty-context line, which disclaims absence (S1), and the system message, which separates a missed search from verified absence;
  - marker quoting for seven forged variants, visible and touching only the marker (S2);
  - no durable IDs or provider names sent;
  - admission identical to the single question, and retrieval that reads only the current message;
  - character and message budgets, with the latest exchange always fitting and no gaps;
  - validation of every malformed shape, including history with unpaired surrogates (F-2);
  - the token binding every earlier message, sent or omitted, and its attribution;
  - content-free receipts, local turns sending nothing, and carryover reporting.
- **`tests/adversarial/test_conversation_adversarial.py`** (48 tests, in the `memory-adversarial` job) covers the revision 1 suite plus F-2 and S2:
  - **Revision 1:**
    - the exact previewed payload;
    - no replay of earlier compiled context;
    - 19 smuggling shapes refused;
    - request bounds;
    - every change after the preview being a 409 with no provider call;
    - plan separation;
    - unchanged vault invalidation, authority, sensitivity and Forget;
    - local turns never calling a provider;
    - carryover;
    - content-free receipts;
    - hostile history and replies.
  - **F-2:**
    - unpaired surrogates in history, the question or `source_ids` give a sanitized 422, never a 500, on repeated attempts, with no text in the response or the logs;
    - validation errors never echo submitted values;
    - undecodable bytes are refused without content;
    - valid unusual Unicode at the exact limit is sent exactly as previewed;
    - a reply with an unpaired surrogate returns intact and is valid history.
  - **S2:** forged context blocks in history reach the provider only as quoted text.
- **`tests/browser/test_chat_ui.py`** (22 scenarios). These run in Chromium against a live server and a recording mock provider. The provider quotes the record in its context and repeats its previous reply, which reproduces F-1's dependency chain. The scenarios run where Playwright for Python is installed; CI skips them. Covered:
  - **Revision 1:** local turns, approval, the exact payload, inert replies with citation chips, history, carryover, a vault change after the preview, lists and search, no browser storage, reload, and phone width.
  - **F-1:**
    - Forget clearing the suffix of four dependent turns and keeping the earlier one, then carryover to another provider without the cleared text;
    - a reply in flight during Forget;
    - a pending preview in the chain;
    - a preview completing after Forget;
    - only the newest preparation of a turn being kept;
    - a regeneration after invalidation;
    - deleting a conversation during a pending reply;
    - out-of-order completions across conversations;
    - claim deletion;
    - a trusted restore that deletes records;
    - traceability after an earlier Forget.
  - **F-3:** omission counts across browser and server for four boundary cases, including the audit's.
  - **F-2 and S3:** clipping that is Unicode-safe, bounded, head-and-tail and idempotent, for emoji, combining marks and zero-width-joiner sequences; and a long emoji reply becoming valid clipped history sent exactly as previewed.
  - **S1:** a local search with no match does not claim absence.
- **Reproduction.** On `488431b` these fail:
  - 15 of the 22 browser scenarios;
  - 16 of the 20 new server-side tests;
  - the 2 updated rendering tests.

  The remediation record lists which failures are behavioural and which test a mechanism the draft did not have.
- **Mutation checks:**
  - **Revision 1:** 25 injected bugs in the server-side conversation code, each caught.
  - **Revision 2:**
    - ten injected bugs in the browser remediation;
    - nine are caught;
    - one is equivalent: removing only the fence's live-conversation check. Deleting a conversation also retires each of its turns, so the sequence check still drops the late reply. Removing both guards is caught.

  The remediation record lists each mutant.
- **`tests/test_policy_invariants.py`:** the UI uses no browser storage API, parses no string as HTML and loads no inline script.
