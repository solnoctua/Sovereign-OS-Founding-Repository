# SOVEREIGN — First steps and build plan

**Working draft v0.1 · October 16, 2026**

## A. Founding sequence (do this before coding)

1. **Ratify the Constitution.** Review scope and language. Record accepted principles and any amendments; keep Draft v0.1 until approved.
2. **Reconcile source discussions.** Export or copy the original Kimi *Sovereign* folder and the long *Estimate Kimi Costs* discussion. Note where they confirm, enrich or contradict this draft. Avoid silently making speculative assistant proposals canonical.
3. **Select V0's narrow use case.** Default recommendation: iPhone/Mac thought capture → provenance-aware memory → reliable recall/correction → export and restore.
4. **Choose the trust baseline.** Decide where the canonical local vault lives, which provider classes may see data, whether raw audio is retained, and how keys and backups work.
5. **Choose the V0 store via an ADR.** SQLite versus local PostgreSQL, with one sample migration and restoration test. Don't prematurely optimize for multi-user scale.

## B. Git protocol

- `main` is the reviewed, intended current specification and later stable product.
- New architecture proposals and features use short-lived branches, pull requests or reviewable diffs.
- Every substantive architecture change includes an ADR: context, decision, alternatives, consequences, migration/reversal plan.
- Constitution changes include explicit human approval, reasons, semantic version increment, and a dedicated commit.
- Provider secrets, private recordings, vault databases, identity keys and sensitive real data are **never committed**.
- First remote repository should be private; publication and licensing are separate conscious decisions.

## C. Development milestones

### M0 — Birth / governance

**Deliverable:** approved Constitution + documented architecture + Git repository; source reconciliation and open decisions tracked.

Acceptance: user can explain what must remain invariant, what can change, and what counts as unauthorized power.

### M1 — The owned record

**Deliverable:** local event store and import/capture API, provenance, retention metadata, correction, deletion and export.

Acceptance: one new thought survives process restart and export/restore; deletion is not accidentally reversed by reimport.

### M2 — The first intelligence loop

**Deliverable:** one replaceable model adapter, context compiler, basic retrieval, derived claims, cited recall.

Acceptance: five seeded test memories answered from sources; ambiguity identified; provider swap does not lose state.

### M3 — Bounded action and cognitive modes

**Deliverable:** permission-gated tool calls, user-confirmed high-impact action, audit receipts; Automate/Collaborate/Train/Challenge/Silence modes.

Acceptance: adversarial 'ignore permissions' instructions fail; revoked capability fails; study mode improves engagement rather than simply answers.

### M4 — Daily use and recovery

**Deliverable:** iPhone quick capture + Desktop retrieval; encryption and backup posture tested; basic cost and error monitoring; local documentation.

Acceptance: a week of personal use with correctable memory and no unapproved cloud disclosure; recovery from a fresh machine/directory.

### M5 — Hardware R&D (later)

**Deliverable:** Pocket experience requirements based on daily M4 use; hardware design studies only after software flow is useful.

Acceptance: device reduces interaction costs without losing core functionality or meaningful privacy.

## D. The very first coding ticket

**Ticket SOV-001 — Save, retrieve, correct, delete and export a sourced thought.**

Input: one text thought (audio capture can be next). Output: locally stored `SourceEvent` and optional linked `MemoryClaim`. A command or tiny UI should allow source-backed retrieval, explicit correction, deletion, portable export, and a successful restore into an empty instance.

**Out of scope:** embeddings, fine-tuning, autonomous agents, hardware, real-world email access, phone replacement and permanent architectural commitments.

## E. Questions to answer at the founding review

See [`OPEN-QUESTIONS.md`](OPEN-QUESTIONS.md), especially default data boundary, raw-data retention, memory approval and what counts as meaningful agency.
