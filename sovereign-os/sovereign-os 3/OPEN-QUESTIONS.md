# SOVEREIGN — Founding decisions and remaining questions

**Status:** four founding decisions confirmed October 16; v0.3 constitutional additions proposed October 18; ratification and real-data security architecture remain open.

## Confirmed founding choices — NOT pending questions

1. **Sovereignty:** local-first, permissioned cloud intelligence.
2. **Audience:** founder's lifelong personal OS first; possible broader use later.
3. **Challenge:** useful and proactive when relevant, explicitly overridable.
4. **Memory authority:** risk-based approvals, with provenance.

See [`docs/adr/0001-founding-choices.md`](docs/adr/0001-founding-choices.md) and the proposed Constitution v0.2 language.

## Unresolved decisions, prioritized

### A. Required for the first real-data V0

- **Cloud data classes:** Which categories are never sent to external models by default, even when cloud AI is enabled? Recommend deny-by-default for sensitive content and explicit one-task disclosure grants; no blanket vault upload.
- **Capture/retention:** Retain raw recordings always, optionally, or selectively? Recommend configurable source retention with explicit default and special consideration of recording third parties.
- **Key and recovery design:** What protects local vault contents and how are backups/recovery keys handled? What is acceptable if keys are lost?
- **Deletion and evidence:** Exactly which log metadata survives deletion and for how long? How do exports, sync and backups avoid resurrecting deleted content?
- **Sensitive memory definition:** Which personal claim categories always require an explicit approval? Proposed: high-impact or identity/health/financial/relationship inference, subject to refined schema.
- **Cloud/provider terms:** Record what providers actually support for retention, training opt-outs, and deletion; don't assume external content can be recalled.

### B. Implementation choices — should get ADRs, not constitutional clauses

- V0 durable database: **provisional SQLite for the local prototype** (ADR-0002); revisit after measured concurrency and deployment needs. Encryption and backup work remain unresolved.
- V0 provider adapter: Kimi/OpenAI-compatible chat behind an explicit cloud egress gate (implemented for synthetic tests); model policy, costs, and review strategy remain future ADRs.
- Real device binding, offline iPhone capture and sync transport; Mac-local V0 first.
- Exact boundary for `MemoryPromotionPolicy`, `CloudDisclosureGrant`, revocation and audit receipts.
- First integrations after capture/retrieval: filesystem, calendar, email, browser, agent skills and tools.
- Trusted test corpus, hallucination benchmarks, and evaluation gates for Stable/Next/Lab.
- December 2026 success definition: daily-use private software prototype, not custom Pocket hardware.

### C. Source-completeness decision before final ratification

The full pinned AI chat, Kimi `Sovereign` folder, complete `Estimate Kimi Costs` export, and saved hardware design materials have **not** all been verified against the written draft. Either reconcile those originals before constitutional v1.0 ratification, or explicitly record that ratification proceeds with that evidence gap and schedule an audit. Do not represent the archive as completely reconciled.

## Final ratification checklist

- [ ] Founder reviews the exact v0.2 constitutional wording and marks amendments accepted/rejected.
- [ ] Source-completeness audit completed **or** explicitly waived with tracked follow-up.
- [ ] Cloud disclosure defaults and memory approval boundaries documented sufficiently to avoid accidental release of personal data during V0.
- [ ] A human ratification declaration identifies the text, date, version and repository commit.

## Prototype trust note

The founding build is **not a secure personal vault**. Local server is loopback only; API has no user authentication and SQLite data is unencrypted at application layer. API keys come from environment variables; never store them in Git. Real personal or third-party data must wait for security and recovery acceptance tests.

## D. Governed second-brain extension — scoped future decisions

Architectural vocabulary, Level 3–4 target, and Obsidian requirement are documented in [ADR-0005](docs/adr/0005-governed-second-brain-architecture.md), [the levels guide](docs/second-brain/LEVELS-AND-OBSIDIAN.md), [the Obsidian projection spec](docs/second-brain/OBSIDIAN-PROJECTION.md) and [the validation spec](docs/second-brain/SECOND-BRAIN-VALIDATION.md). They are proposed direction, not deployed functionality or a change to memory authority.

**Retrieval positions from Benchmark 0003 (PR #4, not merged) — intended, pending formal approval** ([ADR-0005 §12.2](docs/adr/0005-governed-second-brain-architecture.md#122-founders-intended-retrieval-positions--pending-formal-approval)):

- **R1** Porter normalization only as a separate Tier 2 PR with a policy version bump; its precision cost (+47 irrelevant items for +2 expected) stated, not hidden.
- **R2** Defer IDF/BM25; never weaken the truncation fingerprint for performance or convenience; a policy-equivalent fingerprint would need demonstrated equivalence of every protected decision (ADR-0005 §6.3), an ADR-0004 amendment, independent adversarial review and founder approval.
- **R3** Provenance links for local navigation only; ADR-0004 decision 3 preserved.
- **R4** Precision first, especially for cloud plans; floors, thresholds or cloud-specific budgets need their own evaluation and a versioned policy.
- **R5** Keep the 12-item and 12,000-character budgets.
- **R6** Defer local embeddings until representative, legitimate usage shows meaningful improvement; no sensitive personal notes while the Security Gate is NOT PASSED.
- **R7** Keep PR #4's evaluation framework; resolve its findings (including the Codex P2 on scale timings) in PR #4.

**Second-brain decisions requested**, with recommendations in [ADR-0005 §15](docs/adr/0005-governed-second-brain-architecture.md#15-decisions-requested-from-the-founder):

- **D1** Approve the L3–L4 target, deferred L5, and the slice order (evaluation and provenance/Obsidian before retrieval changes)?
- **D2** Where do project and concept nodes come from — human-declared organization, model suggestions, or both?
- **D3** Are typed relationships structured MemoryClaims, or a separate lifecycle?
- **D4** May semantic-only candidates (no shared term) ever enter cloud plans? (Moot while R6 defers embeddings.)
- **D5** May graph or provenance traversal admit context items (revisits ADR-0004 decision 3)? (Recommended: no, per R3.)
- **D6** If a derived index is ever adopted, does it live inside the vault database (same-transaction Forget)? (Moot while R2 defers FTS5.)
- **D7** Obsidian filenames: readable titles with a keyed handle, or the handle alone?
- **D8** On Forget, does Sovereign automatically reconcile its registered Obsidian projections?
- **D9** Manual projection rebuilds only, with reconciliation (deletes and rewrites only) after Forget or trusted restore, at start-up, before export or status, and periodically — or anything more automatic?
- **D10** Add valid time and a correction-vs-change supersession reason to MemoryClaims?
- **D11** Which local embedding model and runtime, if representative usage ever justifies one?
- **D12** Obsidian provenance mode by default: label (one fixed partial sentence) or closed (omit items whose links lead outside scope)?
- **D13** May projected notes carry raw canonical IDs, and only when they are canonical UUIDs?
- **D14** Projection registry as a separate SQLite file beside the vault, or as an operational table inside the vault database?
- **D15** Should a claim that supersedes a sensitive claim inherit its sensitivity? (A Context Compiler question: an ADR-0004 amendment, Tier 2.)

Level 5 remains deferred: which measured daily-use gains, monthly budget, permission model and interruption controls would justify scheduled sync or agents is a later question. No default always-on ingestion.
