# Founder decision register

**Status:** record of decisions, not a roadmap (sequence lives in `ROADMAP.md` §H; detail in `docs/engineering/BUILD-AND-INTEGRATION-PLAN.md`). Entries are short. A decision is binding only when listed under *Approved*. Writing a reviewer recommendation here does not approve it.

## Approved

| Date | Decision | Where it is applied |
| --- | --- | --- |
| 2026-10-16 | Four founding choices: local-first with permissioned cloud; founder's lifelong system first; proactive but overridable challenge; risk-based memory approvals with provenance | ADR-0001 |
| 2026-10-19 | ADR-0003 MemoryClaim authority; ADR-0004 governed retrieval and exact-plan disclosure (V0 decisions 1–6) | `store.py`, `claims.py`, `context.py` |
| 2026-10-20 | Obsidian is a user-requested snapshot export, not a managed projection (D8, D9, D14) | ADR-0005 rev. 4 |
| 2026-10-21 | ADR-0005 D1–D14 approved as architectural direction; R1–R7 as planning positions; D15 deferred | ADR-0005 §15.1 |
| 2026-10-22 | PR #4 (Benchmark 0003) merged as evaluation infrastructure only; no production retrieval change | `eeed753` |
| 2026-10-22 | **D1** application-level kernel first; **D2** SB-2 first then Builder, lightweight Builder practices now; **D3** minimal Sovereign-owned channel contract before any OpenClaw/Hermes benchmark, neither installed by default; **D4** one monorepo, incremental hygiene, major cleanup after the Builder workflow is proven; **D5** Sovereign-native model research track, no training infrastructure | `ROADMAP.md` §H |
| 2026-10-22 | Separation of the Governance Architecture from the Enforcement Kernel; K1/K2/K3 with honest attacker statements; K3 represented, not implemented | `ARCHITECTURE.md` §14 |
| 2026-10-22 | Invariant accepted: a MemoryClaim with missing, invalid, corrupted or insufficiently verified required evidence is never authoritative | PR #20, the replacement for #10 (schema 5) |
| 2026-10-22 | SB-2 delivered as SB-2a (provenance navigation in the UI) then SB-2b (snapshot exporter after SB-2a shows value); a sequencing decision within ADR-0005's scope | `ROADMAP.md` §H |
| 2026-10-22 | Usage thresholds 1–6 are labels, not permissions; the Security Gate stays NOT PASSED; authentication alone passes nothing | `docs/SECURITY-GATE.md` |
| 2026-10-22 | Independent reviewer findings remain reviewer-owned and separately attributable; the builder never rewrites them | WP-1 `FINDINGS-FORMAT.md` |
| 2026-10-22 | Builder 2 is not built now; no autonomous merges; no agent receives the personal vault | `BUILD-AND-INTEGRATION-PLAN.md` §5.6, §7 |
| 2026-10-22 | **D-A** (A1, refined): claims made before schema 5, whose original evidence-set completeness cannot be proven, stay historically preserved but non-authoritative pending explicit human revalidation; revalidation shows the surviving evidence and lets the owner confirm or reconstruct through a governed process (no blind confirmation); future claims carry a write-once commitment to their complete evidence set; a separate integrity state, not new ordinary statuses; ADR-0003 amendments proposed explicitly | PR #20, the replacement for #10 (ADR-0006) |
| 2026-10-22 | **D-B** (B1): refuse invalid migrations and exports rather than pretend they succeeded; preserve the original state; report the reason without disclosing unnecessary content; document an eventual explicit offline recovery pathway; no quarantine subsystem now | PR #20, the replacement for #10 (ADR-0006) |
| 2026-10-22 | **D-C** (C1): reject embedded NUL in new canonical text and identifiers at the application and storage boundaries; preserve legacy data; refuse an incompatible migration rather than delete or alter | PR #20, the replacement for #10 (ADR-0006) |
| 2026-10-22 | **D-E**: required CI jobs execute on draft PRs and exact reviewed commits; a skipped job is not evidence of test execution | PR #18, which replaced #9 (`.github/workflows/sovereign-ci.yml`) |
| 2026-10-22 | **D-F** (in principle): separate the coding agents' GitHub identity and credentials from the founder's account; enforce human and Code Owner review through effective rulesets; prepare the settings for the founder, change no account permission without authorization | Applied on 2026-10-27: agent identity `owlbuilder` (Write); ruleset `25374786` requires one approval and Code Owner review (`docs/engineering/GITHUB-GOVERNANCE-SETUP.md`, PR #18) |
| 2026-10-22 | Target merge sequence **#5 → #9 → #8 → #10 → #11 → #12 → #13**, each subject to its own approval and integration gates; #10 needs D-A/B/C resolved and a fresh independent PASS; #11 stays stacked on #10 until #10 merges, then is retargeted to `main`, its diff and ancestry verified, required CI run and an independent PASS obtained; registry and Security Gate reconciled against the final integration state; #13 remains a proposal; no merge without the founder's explicit authorization of that merge | `ROADMAP.md` §H; `docs/reviews/2026-10-22-f9-f10-reconciliation.md` |
| 2026-10-31 | **Ratification of ADR-0006** (schema 5), its ADR-0003 evidence-integrity amendments and backup format 3, consistent with D-A, D-B and D-C: a claim has authority only if it is `approved`, `supported` and its evidence-set integrity is `committed`; claims approved before schema 5 without proof of complete evidence stay historically preserved but non-authoritative until governed revalidation; invalid migration and export states fail closed; embedded-NUL restrictions and legacy exceptions as implemented (ADR-0006 decision 6). No automatic unmanaged plaintext backup; no mandatory programmatic pre-upgrade export in PR #20; a verified backup and recovery procedure is required before any future non-disposable vault is deployed or migrated. Issue #17 is accepted as a separately tracked availability risk for this synthetic-only prototype, not for personal-data production use; Issues #14–#17 remain open. The Security Gate remains NOT PASSED; no real personal-data migration or production SB-2 deployment is authorized. Given after the independent Codex Tier 2 audit of `ab51bae` returned PASS (2026-10-31) | ADR-0006, ADR-0003 (PR #20, the replacement for #10); `docs/SECURITY-GATE.md` |

## Proposed (require founder approval before merge)

| Proposal | Recommended option | Blocking what | Where |
| --- | --- | --- | --- |
| D15 lineage sensitivity: inherit the most restrictive sensitivity over the whole supersession chain, with a deliberate human declassification path | Prepare as a Tier 2 proposal after WP-2 | Threshold 3 | `ROADMAP.md` §H |
| Local generative inference as a `device` boundary provider after the runtime's network behaviour is verified | Research first, then an ADR-0004 amendment | Stage A+ usefulness | `ROADMAP.md` §H |
| Authenticated capture-only API for non-sensitive data after WP-2 and D15 | Approve the threat-model step | Capture lane | `ROADMAP.md` §H |
| Close PR #7 in favour of the reconciled master plan in WP-0 (done: the founder closed #7 on 2026-10-31) | Approve after reviewing WP-0 | Documentation coherence | PR #7 |
| Repository visibility: public today; founding guidance said private first | Founder decision; no personal data is in history (scanned 2026-10-22) | — | PR #7 note |
| Constitutional amendment candidates A–F | See `docs/CONSTITUTIONAL-AMENDMENT-CANDIDATES.md`; decide at the ratification act | Ratification | that file |

## Deferred

Embeddings (R6); IDF/BM25/FTS5 (R2); graph- or provenance-admitted context (R3, SB-8); Level 5 always-on (ADR-0005 §10); OpenClaw/Hermes benchmark (until a channel or agent need is concrete, D3); n8n, LangGraph, Graphify, RAGFlow (research catalog); multi-device sync; Pocket hardware; Sovereign-native model training (D5); Builder 2.

## Rejected options

Forking Linux now; a graph database; a managed Obsidian projection with registry and reconciliation; a separate relationship lifecycle; a blockchain or custom hash-chain for constitutional history; installing large skill frameworks with hooks (SuperClaude, ECC, Agency Agents, gstack by default); treating stars as evidence; a second master plan.

## Required next approvals

1. WP-0 (this consolidation): done (PR #19, which replaced #8, merged 2026-10-31). PR #7 is closed.
2. WP-1 Builder 0 documents and the GitHub settings checklist: done (PR #18, merged 2026-10-27; D-F settings applied).
3. WP-2 migration approach (ADR-0006): ratified 2026-10-31, after the independent Codex Tier 2 audit of `ab51bae` returned PASS (as reported by the founder; the reviewer's report and findings artifact are not in the repository). Merging PR #20 still needs an independent review of the exact head with a reviewer-owned findings artifact (`docs/DEVELOPMENT.md`, Tier 2), then the founder's Code Owner approval and explicit merge authorization.
4. WP-3 SB-2a after independent audit.
