# Sovereign — Master execution plan (build, security foundation, SB-2, Builder)

**Status:** execution plan for founder review, consolidated 2026-10-22 from the founding investigation, two independent architecture reviews (2026-10-22) and the founder's implementation directive. **Supersedes** the provisional plan proposed in PR #7 (`docs/engineering-integration-plan-20261021`), whose verified starting position, integration seams and do-not-compromise checks are carried forward below. It is not an ADR, a constitutional amendment, a security certification or blanket approval to integrate software. **Snapshot:** `main` at `eeed753311382047fb2042515a5d2d0f68e94b04` (PR #4 merged 2026-10-22). Reconcile against the live branch before acting.

**Authority order:** Constitution candidate (NOT RATIFIED) → founder decisions (`../FOUNDER-DECISIONS.md`) → approved ADRs → `ARCHITECTURE.md` → `ROADMAP.md` §H → this plan → bounded PRs. This document never ratifies anything.

**Labels used throughout:** APPROVED (founder decision), IMPLEMENTED (on `main`, tested), ADR-DIRECTION (approved architectural direction, not implemented), REVIEWER-REC (independent reviewer recommendation), PROPOSAL (needs founder approval), DEFERRED, GAP (known limitation or unsatisfied gate).

## 1. Verified starting position (2026-10-22)

- IMPLEMENTED: Mac-local FastAPI/SQLite browser prototype; records with revisions and Forget; MemoryClaim lifecycle with append-only history; export, untrusted import, confirmed trusted restore; deterministic Context Compiler with exact-plan token; local evidence mode; Kimi/OpenAI adapter with no vault access; 613 tests passing on `main` (run 2026-10-22 on Python 3.13, SQLite 3.45.1).
- IMPLEMENTED (evaluation only): Benchmark 0003 retrieval evaluation (PR #4, merged `eeed753`); production retrieval unchanged (R1).
- ADR-DIRECTION: ADR-0005 D1–D14 and R1–R7 approved 2026-10-21; D15 deferred.
- APPROVED (2026-10-22): founder decisions D1–D5 (`ROADMAP.md` §H); K1/K2/K3 separation of governance from enforcement (`ARCHITECTURE.md` §14); SB-2 split into SB-2a/SB-2b; Builder 0 practices now, Builder 1 after SB-2a, Builder 2 not now; usage thresholds 1–6 (`SECURITY-GATE.md`).
- REPAIRED: Issue #6 and zero-source authority (schema 5, ADR-0006, PR #10); claims made before schema 5 need revalidation. GAP: D15 deferred; no authentication; no at-rest encryption beyond the host; repository is public while founding guidance said private first (founder decision pending); the `main` ruleset (active since 2026-10-19) enforces pull requests, the required checks `full-test-suite` and `memory-adversarial` (up to date with `main`), resolved review threads, and no force-push or deletion, but **no approving review and no code-owner review** until the founder applies D-F (`docs/engineering/GITHUB-GOVERNANCE-SETUP.md`); since D-E the required jobs run on draft PRs too, so a required check is never a skipped one (`docs/DEVELOPMENT.md`).
- Open PRs: #5 hygiene (merges cleanly), #7 provisional plan (superseded by this file; recommend closing after WP-0 review).

## 2. Founding advantages to preserve (carried forward from PR #7)

| Advantage | Source | Shortcut that erodes it |
| --- | --- | --- |
| More life, less interface; human competence over engagement | Constitution preamble, Arts. I–II, VII | Always-on feeds, unrequested proactive chatter |
| The human, not the model, owns authority | Arts. I, IV–V; ADR-0003 | Framework memory treated as truth; agent self-grants |
| Durable personal state survives any model or vendor | Arts. III, VI, VIII; ADR-0001 | Hosted agent memory or proprietary store as source of truth |
| Disclosure is a separate, inspectable decision | Arts. V–VI; ADR-0004 | Retriever, plugin or router sending content outside a previewed plan |
| Epistemic humility and repairable history | Art. IV; ADR-0003 | Summaries overwriting evidence; inferred edges promoted to facts |
| Sovereignty without isolation or bespoke everything | Arts. III, VI.9; ADR-0002 | Reimplementing cryptography or operating systems for purity |
| Views are not owners | ADR-0005 §3–§9 | Two-way Obsidian sync; a second graph authority |

**Do-not-compromise checks for every adoption:** (a) source of truth stays explicit; (b) imported or model output cannot raise authority; (c) permissions and disclosure stay independently enforced; (d) correction, Forget and restore semantics survive; (e) removal leaves canonical state intact; (f) the UI increases agency rather than dependence; (g) third-party rights are respected. A failed check is a stop.

## 3. Enforcement boundaries (summary; authoritative text in `ARCHITECTURE.md` §14)

K1 canonical store (implemented; integrity repair pending), K2 governed context and disclosure (implemented; D15 gap), K3 action gate (represented, not implemented). Every external capability has exactly one relationship to Sovereign: **prompt text in the repository** (Builder skills), **library inside the kernel process** (read-only or stateless only), or **out-of-process runtime behind a narrow contract** (model runtimes, channels, automations, agents) with no vault file and its own credentials only. Builder tools never receive the personal vault path.

## 4. Integration seams (conditional, not approvals)

| Seam | Owner / boundary | A candidate may provide | It must never own |
| --- | --- | --- | --- |
| Model inference | `providers.py` behind `app.py` and `context.py` approval | An additional endpoint or transport (cloud or local) | Vault reads, disclosure scope, keys beyond its own, tool authorization |
| Memory and storage | `store.py`, ADR-0003 schema | A tested storage or migration implementation via its own Tier 2 ADR | Approval, evidence identity, tombstones, unreviewed restore |
| Retrieval and context | `context.py`, ADR-0004 | Offline candidate IDs evaluated in Benchmark 0003 | Relevance or disclosure policy, outbound prompts, fingerprint, budgets |
| Knowledge exploration | SB-2a graph on read; SB-2b snapshot renderer | A disposable local visualization library if it truly reduces work | Canonical writes, implicit sync, fabricated entities, graph-derived authority |
| Channel intake (future) | A Sovereign-owned `InboundEnvelope` contract (D3) | Reachability; untrusted messages as evidence or proposals | Approvals, permissions, canonical memory |
| Tool execution (future, K3) | Broker process | A narrowly scoped adapter after threat model | Self-authorization, silent side effects, broad vault access |
| Development intelligence | Builder (separate development vault; Git authoritative) | Minimization, audit methodology, context compilation for coding agents | Personal vault access; merge authority; audit-record rewriting |

Evaluation protocol per candidate (from PR #7, unchanged): evidence (pinned commit, license, behaviour verified, not README claims) → need now? → philosophy gate (pass / isolate / fail) → technical fit → alternatives → exit test → decision with owner, tests, tier and ADR/PR. The research catalog that applies it is `../research/INTEGRATION-RESEARCH-CATALOG.md`.

## 5. Work packages

Each is an independently reviewable PR from a clean `main`. Quality bar for every PR: `docs/DEVELOPMENT.md` §"Pull request contract".

### 5.1 WP-0 Repository truth and architecture consolidation (Tier 0/1, docs only) — this PR
Reconcile PR #4's merge in every document; renumber `ARCHITECTURE.md` §9/§12 collision; add §14 (governance vs enforcement) and §15; `ROADMAP.md` §H; usage thresholds and Issue #6/zero-source status in `SECURITY-GATE.md`; this plan; `../research/INTEGRATION-RESEARCH-CATALOG.md`; `../architecture/systems-registry.toml` with a validating test; `../FOUNDER-DECISIONS.md`; `../CONSTITUTIONAL-AMENDMENT-CANDIDATES.md` (NOT RATIFIED). Acceptance: no "not merged" statement about PR #4 remains; registry test passes; full suite unchanged. Rollback: revert the PR.

### 5.2 WP-1 Builder 0 workflow (Tier 1, docs, CODEOWNERS, policy tests)
One loop in `docs/DEVELOPMENT.md` (Orient → Minimize → Specify → Build → Verify → Independent audit → Challenge/Reproduce → Compound → Founder approval → Merge); reviewer-owned findings format (`FINDINGS-FORMAT.md`, `findings.schema.json`); minimization guidance citing Ponytail (MIT) without copying it; `.github/CODEOWNERS`; PR template with the quality bar; `tests/test_policy_invariants.py` (single egress call site, registry consistency); branch-protection checklist the founder applies in GitHub (cannot be set from a file). Acceptance: tests pass; no new dependency; no hooks or frameworks installed.

### 5.3 WP-2 Storage-integrity repair (Tier 2, code + migration) — Issue #6
Reproduce first (adversarial tests fail on `main`), then the narrowest sound repair: schema version 5 with the five canonical tables rebuilt `WITHOUT ROWID` (`claim_events` keeps `INTEGER PRIMARY KEY AUTOINCREMENT`; its sequence is its rowid and is already guarded), migration 0→5 and 4→5 in one `BEGIN IMMEDIATE` transaction that drops and recreates every trigger (cross-table trigger bodies otherwise block `RENAME`), refusal of unknown versions, `support_of([])` → `orphaned`, corrected ADR-0003 text. Tests: rowid and primary-key replacement in every statement form on every table under the four pragma combinations; zero-source and corrupted-source authority; forgotten identities; lineage; migration atomicity with injected failure; legacy v0 compatibility; export/restore equivalence; concurrency (second opener waits). Evidence separation: the reproduction record and the migration proposal (ADR-0006, PROPOSED) are kept apart from implementation results. **Draft PR only; independent reviewer artifact and founder approval of the migration approach required; no production vault is migrated.**

### 5.4 WP-3 SB-2a provenance navigation (Tier 2, code + UI)
Computed-on-read neighborhood from `claim_sources`, `records.supersedes_id`, `claims.supersedes_id`; status, support and authority read live; typed (kind, id) identity; eligibility checked before capacity; bounded hops, nodes, work, response bytes and shown history; one read snapshot; GET endpoint; UI panels ("Supported by", "Cites", "Corrects / corrected by", "Supersedes / superseded by", current evidence status, decision history) with "pin this record". No ontology, no graph database, no inferred edges, no compiler change, no retrieval change. Tests: validation spec §3 items 1–6 including token identity over all 56 Benchmark 0003 queries. **On `main` (PR #11), after an independent PASS.**

SB-2b minimum (after SB-2a has shown value; PROPOSAL reconciling, not discarding, `OBSIDIAN-PROJECTION.md`): one-way ZIP snapshot; opaque handle filenames with the readable title as H1 and link display text; inert fenced blocks; no raw canonical IDs; scope closure; structural verification; snapshot banner and Forget boundary wording; Git-tree and existing-path refusal. Acceptance subset: validation §4 items 1, 3, 4, 5a, 6–10, 12, 15, 16, 17, 21, 24a, 25, 26, 27 (process kill), 28, 32, 33 (one extractor), 34. Deferred to SB-2c: readable filenames with grapheme-cluster rules, folder output with no-replace rename primitives, native Obsidian network-isolation runs, power-loss recordings.

### 5.5 WP-4 First-use trial (Tier 1)
A runnable, deliberately non-sensitive project-knowledge trial: a small seeded vault whose records reference Git paths and decisions instead of copying ADRs, five founder queries (why computed-on-read provenance; what blocks SB-2; what changed after the independent audit; why OpenClaw and Hermes are deferred; which assumptions remain unverified), measurement of recall with evidence, time to an accepted decision, repeated explanations avoided, correction and Forget behaviour, and usefulness against reading the documents directly. Outcomes recorded in `docs/engineering/FIRST-USE-TRIAL.md`.

### 5.6 WP-5 Builder 1 specification (Tier 2 spec; implementation after SB-2a is demonstrated)
`sovereign dev context "<task>"`: a Git-first development-context compiler combining Git source, accepted ADRs, architecture, open issues and PR context, test evidence, independently recorded findings, development-vault claims and project constraints into a bounded, reproducible, evidence-linked task bundle. Reuses `build_bundle`, `render_messages` and the token; candidate sources differ; state is a separate development vault file; never the personal vault. No competing canonical development authority: Git wins; disagreement makes a development claim `contested`.

### 5.7 Later work (ordered in `ROADMAP.md` §H)
D15 policy (Tier 2 proposal); local generative inference with a verified device boundary (ADR-0004 amendment); capture lane (local CLI and Shortcut; offline phone-note import; authenticated capture-only API after WP-2 and D15; device identity and revocation; private transport; protected backups); private-data thresholds 3 and 4; Builder-assisted monorepo cleanup; K3 when an external action exists; OpenClaw/Hermes benchmark when a channel need is concrete; broader integrations.

## 6. The development vault and Builder authority

Git, accepted ADRs, approved documents, issues and founder decisions are the development authority. The development vault is a **second instance of the K1 store on a different file**, holding governed working knowledge that adds value beyond Git (why a decision was taken, what a reviewer found, which defect recurred) with explicit references back to paths and commits. It never holds personal data; personal tools never hold its path; it is not flooded with copied ADRs. Developer indexes, generated code graphs and agent transcripts are projections or working context, never authority.

## 7. Self-improvement governance (what actually contains a coding agent)

No Python check contains an agent with shell and repository write. What does: the GitHub ruleset on `main` (pull request required, required CI up to date with `main`, review threads resolved, no force-push, no deletion; **approving and code-owner review are not enforced**, which is a founder decision recorded in `docs/DEVELOPMENT.md`), the founder's own merge as the approval act, and no autonomous merges; reviewer-owned findings artifacts the builder cannot rewrite; policy tests that fail CI when the egress single call site, the trigger set or the schema version change without an ADR reference; hash-pinned dependencies; signed tags for anything run on real data; the owner's running instance updated only from signed tags; rollback by previous tag plus export.

## 8. Definition of progress

The founder can safely understand and reverse each new capability; existing records, authority and exit survive every integration; useful tasks get easier and are measured (WP-4); security claims become more evidence-backed; dependencies and autonomous agents do not grow without need.
