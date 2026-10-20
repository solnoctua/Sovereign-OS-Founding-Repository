# SOVEREIGN — First steps and build plan

**Working draft v0.2 · October 16, 2026 · founding review branch**

## A. Founding sequence (do this before coding)

1. **Review v0.2 amendments; do not ratify by implication.** Four strategic founding choices have been decided (ADR-0001), but the actual textual amendments in `CONSTITUTION.md` still require signoff.
2. **Reconcile source discussions or expressly waive the gap.** Export or copy the original Kimi *Sovereign* folder, pinned AI chat, and long *Estimate Kimi Costs* discussion. Note confirmations/contradictions. Do not represent the v0.2 review as a full audit.
3. **Select V0's narrow use case.** Default recommendation: iPhone/Mac thought capture → provenance-aware memory → reliable recall/correction → export and restore.
4. **Choose the trust baseline.** Mac-local authority and permissioned cloud inference are the current direction. Specify per-category cloud disclosure, raw audio retention, memory approval classes, and keys/backups before importing real sensitive data.
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

**Deliverable:** candidate Constitution v0.3 + documented architecture + Git feature branch and tested proof-of-concept. Ratification is a separate explicit decision.

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

See [`OPEN-QUESTIONS.md`](OPEN-QUESTIONS.md). The four high-level founder questions are settled; the remaining decisions are concrete security, source-completeness, and V0 architecture choices.


## F. Development execution strategy — provisional

Sovereign development uses a lightweight multi-model loop documented in [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md). Git remains canonical; AI chats do not. The operating loop is **Specify → Build → Audit → Challenge → Test → Approve → Merge**, with review proportional to consequence.

Current provisional tooling: ChatGPT/Codex for architecture, reasoning and/or implementation; Claude Code as an alternate implementation system; selective frontier API inference for difficult or foundational problems. These are personal development resources, **not** product architecture or constitutional commitments.

Before choosing a default coding agent, run [`docs/benchmarks/0001-builder-memory-claims.md`](docs/benchmarks/0001-builder-memory-claims.md) from the same starting commit. The benchmark implements real M2 work: explicit source-evidence versus derived-memory-claim authority. Choose the builder on correctness, security, test quality, maintainability and execution efficiency, and re-benchmark after major model/tool changes.

Tier 2/3 changes (state schemas, memory authority, permissions/disclosure, deletion/recovery, security, major architecture, Constitution) require independent review and founder approval. Routine changes do not require two models.

## Current progress — October 18, 2026

- Prototype local app is implemented under `src/sovereign`.
- API for save/search/correct/delete/export/import is implemented and tested on synthetic records.
- UI previews the compiled context and requires approval of that exact context before any cloud request; no cloud model is contacted by default.
- MemoryClaim authority (ADR-0003, Benchmark 0001) is merged. **Context Compiler V0 / governed retrieval** (ADR-0004, Benchmark 0002) is in review: deterministic local retrieval, MemoryClaim-derived authority, inherited sensitivity and exact-plan cloud approval (M2).
- One provider adapter supports Moonshot/Kimi and OpenAI Chat Completions if separately configured. Live provider calls are **not** verified here without credentials.
- `python -m sovereign` serves at `127.0.0.1:8765`.
- **Not yet safe for sensitive real-world data:** unencrypted database, no app login, backups/recovery and audit trails incomplete.

## G. Governed second-brain track (proposed; complementary to M0–M5)

See [ADR-0005](docs/adr/0005-governed-second-brain-architecture.md) (PROPOSED), [the five-level guide](docs/second-brain/LEVELS-AND-OBSIDIAN.md), [the Obsidian projection spec](docs/second-brain/OBSIDIAN-PROJECTION.md) and [the second-brain validation spec](docs/second-brain/SECOND-BRAIN-VALIDATION.md). This track **extends memory and the context pipeline**, not the kernel's permissions or goals. **Target Levels 3–4**, with Levels 1–2 as readable routing/wiki views; Level 5 continuous intelligence stays a later option behind cost, consent and security gates. L1–L5 are techniques; the slices below are this track's only numbering (acceptance details in ADR-0005 §11).

**Status as of 2026-10-20:** the Context Compiler (PR #2) is merged to `main`, and PR #3 is integrated with it. Retrieval evaluation is **Benchmark 0003**, executed in [PR #4](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/pull/4) and not yet merged; PR #4 also refreshes the *Current progress* list above. The founder's intended retrieval positions R1–R7 (ADR-0005 §12.2) await formal approval.

| Slice | Delivers | State / gate |
| --- | --- | --- |
| **SB-0** | Direction docs, Obsidian and validation specs, synthetic demo vault (PR #3) | Founder decisions D1–D11 (ADR-0005 §15) |
| **SB-1** | Benchmark 0003 retrieval evaluation (synthetic corpus, harness, governed recall/noise/precision, lexical alternatives) | Executed in PR #4, not merged; Codex P2 on its scale timings open there; R1–R7 pending |
| **SB-2** | Provenance graph computed on read (local navigation only) + one-way Obsidian projection CLI with registry, export fence, inert serialization, scope closure and Forget reconciliation — **first user-visible slice** | Tier 2; no canonical schema change; validation spec §3–§4 |
| **SB-3** | Human-declared projects/concepts and membership → project/concept hubs | Tier 2 schema ADR |
| **SB-4** | Porter normalization of the existing score, with a policy version bump — only if R1 is approved, precision cost stated | Separate Tier 2 PR; IDF/BM25/FTS5 deferred (R2) |
| **SB-5** | Local embeddings | Deferred (R6) until representative, legitimate usage shows meaningful improvement |
| **SB-6** | Temporal claim extension: valid time, correction vs change | Tier 2 (extends ADR-0003) |
| **SB-7** | Typed relations as structured MemoryClaims; human-authored first | Tier 2/3 |
| **SB-8** | Graph- or provenance-assisted context | Deferred (R3); local exploration and independent evaluation first |
| **SB-9** | Level 5 research only | Measured utility, budget, consent, security |

**Delivery discipline:** distinct, reviewable changes; do not conflate visualization with evidence verification. User agency, capture/recovery and security work remain prerequisites for live personal data, independent of this track. Separately, a small repository-hygiene PR should restore `.gitignore` and untrack `data/sovereign.db` and `__pycache__` (see `docs/SECURITY-GATE.md`).
