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
