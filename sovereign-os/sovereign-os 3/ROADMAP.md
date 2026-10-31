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
- MemoryClaim authority (ADR-0003, Benchmark 0001) and **Context Compiler V0 / governed retrieval** (ADR-0004, Benchmark 0002) are merged: deterministic local retrieval, MemoryClaim-derived authority, inherited sensitivity and exact-plan cloud approval (M2).
- **Retrieval evaluation** ([Benchmark 0003](docs/benchmarks/0003-retrieval-evaluation.md), the second-brain track's SB-1) is merged to `main` on 2026-10-22 (`eeed753`) as evaluation infrastructure only (PR #4): a synthetic corpus and harness measuring retrieval before and after policy, with its precision, disclosure and token-stability costs. Production retrieval stays the merged lexical retriever (founder direction 2026-10-20; ADR-0005 R1–R7 approved as planning positions on 2026-10-21): no experimental retriever is approved, and IDF, BM25, FTS5 and embeddings are deferred.
- One provider adapter supports Moonshot/Kimi and OpenAI Chat Completions if separately configured. Live provider calls are **not** verified here without credentials.
- `python -m sovereign` serves at `127.0.0.1:8765`.
- **Not yet safe for sensitive real-world data:** unencrypted database, no app login, backups/recovery and audit trails incomplete.

## G. Governed second-brain track (proposed; complementary to M0–M5)

See [ADR-0005](docs/adr/0005-governed-second-brain-architecture.md) (direction approved 2026-10-21; not implemented), [the five-level guide](docs/second-brain/LEVELS-AND-OBSIDIAN.md), [the Obsidian export spec](docs/second-brain/OBSIDIAN-PROJECTION.md) and [the second-brain validation spec](docs/second-brain/SECOND-BRAIN-VALIDATION.md). This track **extends memory and the context pipeline**, not the kernel's permissions or goals. **Target Levels 3–4**, with Levels 1–2 as readable routing/wiki views; Level 5 continuous intelligence stays a later option behind cost, consent and security gates. L1–L5 are techniques; the slices below are this track's only numbering (acceptance details in ADR-0005 §11).

**Status as of 2026-10-22:** the Context Compiler (PR #2) and ADR-0005 (PR #3) are merged to `main`. Retrieval evaluation is **Benchmark 0003**, executed in [PR #4](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/pull/4) and merged to `main` on 2026-10-22 (`eeed753`) as evaluation infrastructure only (its Codex P2 was resolved at `da52ce9`; CI passed; no production retrieval change). By founder direction, production retrieval stays the merged lexical retriever; ADR-0005's retrieval positions R1–R7 (§12.2) agree; on 2026-10-21 the founder approved ADR-0005's direction (D1–D14) and R1–R7 as planning positions, and deferred D15 (ADR-0005 §15.1). The founder has also simplified the Obsidian requirement to a user-requested **snapshot export** (D8, D9, D14 settled).

| Slice | Delivers | State / gate |
| --- | --- | --- |
| **SB-0** | Direction docs, Obsidian and validation specs, synthetic demo vault (PR #3) | D1–D14 approved 2026-10-21; D15 deferred (ADR-0005 §15.1) |
| **SB-1** | Benchmark 0003 retrieval evaluation (synthetic corpus, harness, governed recall/noise/precision, lexical alternatives, provenance navigation and counterfactual admission) | Executed in PR #4 and merged to `main` on 2026-10-22 (`eeed753`); Codex P2 resolved, CI passed; no production retrieval change (R1) |
| **SB-2** | Split on 2026-10-22 into **SB-2a** (provenance graph computed on read, surfaced as navigation in the existing UI — **first user-visible slice**) and **SB-2b** (one-way Obsidian **snapshot export**, ZIP first, opaque filenames with readable displayed titles, inert serialization, scope closure, structural verification; after SB-2a has shown practical value). The split is a delivery decision inside ADR-0005's approved scope, not an amendment (see §H) | Tier 2 each; no registry and no canonical schema change; validation spec §3 (SB-2a) and §4 (SB-2b); before any real personal data: the Tier 2 storage-integrity fix below (Issue #6) |
| **SB-3** | Human-declared projects/concepts and membership → project/concept hubs | Tier 2 schema ADR |
| **SB-4** | A lexical retrieval change — **none is authorized** (R1); Porter normalization and the exact-stem tie-break are evaluated candidates only | If ever proposed: its own Tier 2 PR with a policy version bump, regenerated Benchmark 0003, independent review and founder approval; IDF/BM25 and any persistent FTS5 index deferred (R2) |
| **SB-5** | Local embeddings | Deferred (R6) until representative, legitimate usage shows meaningful improvement |
| **SB-6** | Temporal claim extension: valid time, correction vs change | Tier 2 (extends ADR-0003) |
| **SB-7** | Typed relations as structured MemoryClaims; human-authored first | Tier 2/3 |
| **SB-8** | Graph- or provenance-assisted context | Deferred (R3); local exploration and independent evaluation first |
| **SB-9** | Level 5 research only | Measured utility, budget, consent, security |

**Evaluation state** (ADR-0005 §12.4, updated 2026-10-22): retrieval evaluation executed in PR #4 and merged (`eeed753`); provenance-graph and snapshot-export tests specified but not implemented (no native Obsidian check executed); entity, temporal and relationship tests future; semantic/hybrid experiments deferred and, when run, inside the Benchmark 0003 harness; generated-answer evaluation optional, separate and not established by SB-1.

**Delivery discipline:** distinct, reviewable changes; do not conflate visualization with evidence verification. User agency, capture/recovery and security work remain prerequisites for live personal data, independent of this track. Separately, the repository-hygiene PR (#5, on `main`) restored `.gitignore` and untracked `data/sovereign.db` and `__pycache__`, and a **high-priority Tier 2 storage-integrity repair**, independently implemented and audited, must close the hidden-rowid replacement bypass of the ADR-0003 triggers — tombstone loss, record or claim deletion without Forget, broken evidence links, claim authority or sensitivity changes — before production SB-2 relies on those invariants (see `docs/SECURITY-GATE.md`). Simplifying the Obsidian export does not remove this dependency.

## H. Consolidated execution sequence (founder directive, 2026-10-22)

This section replaces the provisional §H proposed in PR #7 and is the only sequence to follow. The master execution plan with work packages, acceptance criteria and gates is [`docs/engineering/BUILD-AND-INTEGRATION-PLAN.md`](docs/engineering/BUILD-AND-INTEGRATION-PLAN.md); founder decisions are recorded in [`docs/FOUNDER-DECISIONS.md`](docs/FOUNDER-DECISIONS.md). M0–M5 and SB-0…SB-9 keep their meaning; this section orders the next slices across them.

**Binding founder decisions (2026-10-22):** D1 application-level kernel first; D2 SB-2 first, then Builder, with lightweight Builder practices immediately; D3 minimal Sovereign-owned channel contract before any OpenClaw/Hermes benchmark, neither installed by default; D4 one monorepo, incremental hygiene, major cleanup after the Builder workflow is proven; D5 Sovereign-native model research as a formal track with no training infrastructure.

| Order | Slice | Depends on | Gate to proceed | Status |
| --- | --- | --- | --- | --- |
| 0 | **Repository truth and consolidation** (this section, ARCHITECTURE §14, registry, research catalog, decision register) | — | Founder review of the WP-0 draft PR | On `main` through PR #19, which replaced #8 (merged 2026-10-31) |
| 0 | **Repository hygiene** (PR #5) | — | Founder merge | On `main`: `.gitignore`, runtime vault and caches untracked, CI hygiene check |
| 0 | **Builder 0 practice** (WP-1: loop, reviewer-owned findings, CODEOWNERS, policy tests) | — | Founder review; founder decisions on review requirements and the draft-check gap (`docs/DEVELOPMENT.md`) | On `main` through PR #18, which replaced #9 (D-E: required jobs run on drafts); D-F applied on 2026-10-27: agent identity `owlbuilder`, one approval and Code Owner review required (`docs/engineering/GITHUB-GOVERNANCE-SETUP.md`) |
| 1 | **Storage-integrity repair** (WP-2, Issue #6, zero-source authority) | WP-0 docs | Fresh independent Codex PASS of the exact head; founder approval of ADR-0006 and its proposed ADR-0003 amendments | Candidate, not merged: PR #20, the replacement for #10. Independent Codex Tier 2 audit of `ab51bae`: PASS (2026-10-31, as reported by the founder); ADR-0006 and its ADR-0003 amendments ratified 2026-10-31. Before merge: an independent review of the exact head with a reviewer-owned findings artifact, then the founder's Code Owner approval and merge |
| 1 | **SB-2a provenance navigation** in the existing UI | WP-2 (stacked on it: bounded, id-ordered neighbour queries rely on the schema 5 index order) | Validation spec §3 tests; fresh independent review of the exact head | Draft PR; Codex audit CHANGES REQUIRED, remediation in review |
| 2 | **First-use trial** on a deliberately non-sensitive project dataset (WP-4) | SB-2a helpful but not required | Measured outcomes recorded | Planned |
| 2 | **D15 lineage sensitivity** (Tier 2 proposal) | WP-2 | Founder approval of the policy; `policy_version` bump; Benchmark 0003 regenerated | Proposal |
| 3 | **Builder 1 specification** (Git-first development-context compiler, WP-5) | SB-2a demonstrated useful; first-use trial | Founder approval of the spec | Planned |
| 3 | **SB-2b snapshot exporter** (optional, ZIP first) | SB-2a used in practice; founder sequencing decision | Validation spec §4 subset in `BUILD-AND-INTEGRATION-PLAN.md` §5.4; independent audit | Planned, may follow Builder 1 |
| 4 | **Local generative inference** (device boundary) | Runtime network behaviour verified | ADR-0004 policy amendment, `policy_version` bump, adversarial tests | Research, then proposal |
| 4 | **Capture lane** (local CLI and macOS Shortcut; offline phone-note import; authenticated capture-only API later) | Issue #6 and D15 for the authenticated step | Threat model; non-sensitive data until the private-data threshold | Planned |
| 5 | **Private-data security milestones** (thresholds in SECURITY-GATE) | all of the above | Independent review and founder approval per threshold | Not started |
| 5 | **Builder-assisted monorepo cleanup** | Builder 1 proven | Founder approval | Not started |
| 6 | **K3 action gate**, channel contract benchmark (OpenClaw/Hermes), governed automations | A concrete authorized action or channel need | Separate ADRs | Not started |

**Parallel work allowed:** WP-0, WP-1, WP-2 and SB-2a touch disjoint files and may proceed concurrently; two builders must never edit `store.py`, `context.py`, `claims.py`, `app.py` or a governing document at the same time. **Sequential joins:** authenticated capture after WP-2 and D15; Builder 1 after SB-2a is demonstrated; SB-2b after SB-2a use; any real personal data after the thresholds in `docs/SECURITY-GATE.md`; K3 after a real action exists.

**Stop conditions:** a confirmed canonical-integrity defect stops real-data plans; a provider payload differing from its preview stops cloud use; personal data in Git, logs or the development vault stops all work until remediated; a change to a path listed explicitly in `.github/CODEOWNERS` (not only by the catch-all `*`) without a reviewer-owned findings artifact is not merged.
