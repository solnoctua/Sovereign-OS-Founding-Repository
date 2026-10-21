# Sovereign — Build, engineering, design and integration plan

**Status:** execution proposal for founder review; not an ADR, constitutional amendment, security certification, or blanket approval to integrate software. **Snapshot:** 2026-10-21, `main` at `c6ef14bef7d85eafc69fb2d5287365551037d259`. Reconcile against the actual branch/CI before acting; status below is not a live dashboard.

**Purpose:** turn the founding direction and the external-repository research into a small, testable engineering program. Improve what exists before expanding the stack. This document is the **execution crosswalk**, not a new source of authority: [Constitution](../../CONSTITUTION.md) (v0.3 candidate, NOT RATIFIED) → [confirmed founder choices](../adr/0001-founding-choices.md) and approved ADRs → [Architecture](../../ARCHITECTURE.md) → [Roadmap](../../ROADMAP.md) → bounded PRs. Existing [Development](../DEVELOPMENT.md), [Security Gate](../SECURITY-GATE.md), [ADR-0003](../adr/0003-memory-claim-authority.md), [ADR-0004](../adr/0004-governed-retrieval-context-compiler.md) and [ADR-0005](../adr/0005-governed-second-brain-architecture.md) retain their own scope.

## 1. Verified starting position

- **Working code:** Mac-local FastAPI/SQLite browser prototype, source revisions/Forget, MemoryClaim lifecycle and provenance, export/import/confirmed restore, deterministic Context Compiler, exact-plan cloud approval, local evidence mode, and replaceable Moonshot/OpenAI provider adapters. This is not a production OS, secure vault, agent runtime or deployed graph.
- **Architecture:** Constitution v0.3 is **review only**; four founding choices in ADR-0001 are confirmed. ADR-0005's D1–D14 and R1–R7 are approved **direction/planning positions**, not deployed code or constitutional ratification. D15 lineage sensitivity remains deferred and is a real cloud-risk gap.
- **Evaluation:** Benchmark 0003 is in [PR #4](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/pull/4), **evaluation only / DO NOT MERGE**. The merged lexical retriever, 12-item/12,000-character budgets, and full relevant-universe truncation fingerprint remain unchanged. Do not recreate the benchmark on `main` or silently adopt its experiments.
- **Security:** [Security Gate](../SECURITY-GATE.md) is **NOT PASSED**. In particular, no app authentication, encrypted vault/recovery posture, or approval to hold real sensitive life data. The documented SQLite hidden-`rowid` REPLACE bypass can defeat the ADR-0003 storage triggers on default raw connections.
- **Repository hygiene:** `main` lacks a root `.gitignore` and tracks a prototype database/bytecode. A narrow fix is open in [PR #5](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/pull/5), **not merged**. Storage repair is tracked in [issue #6](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/issues/6).
- **Second brain:** SB-2 (computed-on-read provenance navigation and one-way, user-requested Obsidian ZIP/new-folder snapshot) is the first planned user-visible slice. Its export and security acceptance tests are specified, not implemented. The storage-integrity repair is a prerequisite for relying on its invariants.

## 2. The philosophical foundation: preserve what Sovereign does better

These are **Sovereign's distinctive design choices**, grounded in the founding documents. They are not unverified claims that any named external repository violates them. The comparative research must test each candidate against them with primary-source evidence.

| Founding advantage to preserve | Source and practical engineering consequence | Attractive shortcut that erodes it |
| --- | --- | --- |
| **More life, less interface; human competence over engagement** | Constitution preamble, Arts I–II, VII: measure better judgment, learning, follow-through and presence; preserve Automate/Collaborate/Train/Challenge/Silence and the right to disengage | Always-on feed, unrequested proactive chatter, interaction-maximizing dashboards or agents |
| **The human, not the model, owns authority** | Constitution Arts I, IV–V; ADR-0003: source evidence ≠ approved claim ≠ action permission; human-governed transitions and revocation | Framework memory automatically treated as truth; agent self-grants tools; opaque promotion |
| **Durable personal state survives any model or vendor** | Constitution Arts III, VI, VIII; ADR-0001: local-first canonical records, documented export/restore, replaceable inference | Hosted agent memory, proprietary graph or embedding store as the only source of truth |
| **Disclosure is a separate, inspectable decision** | Constitution Arts V–VI; ADR-0004: Context Compiler builds exact approved bundle, checks authority/sensitivity, fails closed on change | Retriever, plugin, router or model sending arbitrary vault content without a previewed plan |
| **Epistemic humility and repairable history** | Constitution Art IV; ADR-0003: provenance, evidence hashes, support, conflict, correction, supersession and Forget | Summaries that overwrite source evidence, inferred graph edges promoted to facts |
| **Sovereignty without isolation or bespoke everything** | Constitution Arts III and VI.9; ADR-0002: use established OS/security/cloud capabilities deliberately, with scoped adapters and tested exit | Reimplementing cryptography or whole operating systems for ideological purity |
| **Views are not owners** | ADR-0005 ``3–9: graph/index/Obsidian are derived or one-way projections; canonical state and authority stay in the vault | Bi-directional Obsidian sync, separate graph authority lifecycle, permanent projection registry |

**Do-not-compromise checks for every adoption:** (a) source of truth stays explicit; (b) imported/model output cannot raise authority; (c) permissions and cloud disclosure remain independently enforced; (d) correction/Forget and restoration semantics survive; (e) removal leaves canonical state intact; (f) the UI increases agency rather than dependence; (g) the rights/privacy of third parties are respected. A failed check is a **stop**, not a low score offset by features.

**Authority distinctions:** ADR-0001's four choices are confirmed founder decisions. ADR-0005's scoped direction is approved. The Constitution itself remains an **unratified candidate**; this document cannot ratify it. Suggested quantitative UX targets, provider criteria and external-project scores below are **new review proposals**, not founder commitments.

## 3. Integration policy: choose a capability, not another operating system

Sovereign is the control plane. External repositories can supply **replaceable implementations**, never a competing authority layer. Use existing interfaces first. A dependency is justified only when it solves a demonstrated gap more safely, simply or economically than a bounded local change.

**Allowed integration seams (conditional, not blanket approval):**

| Seam | Current owner / boundary | What a candidate may provide | What it must never own |
| --- | --- | --- | --- |
| Model inference | `providers.py` adapter behind `app.py` and `context.py` approval | Additional model endpoint, transport or capability adapter | Vault reads, cloud scope decisions, keys beyond its own, tool authorization |
| Memory and storage | `store.py` + ADR-0003 schema and decision history | A tested storage/migration implementation **only via its own Tier 2 ADR** | Memory approval, evidence identity, tombstones, unreviewed restore |
| Retrieval and context | `context.py` / ADR-0004 | Offline candidate-ID generation evaluated in Benchmark 0003 | Relevance/disclosure policy, direct outbound prompts, altered fingerprint or budgets |
| Knowledge exploration | Future SB-2 read-only provenance and snapshot renderer | A disposable local visualization/export library if it truly reduces work | Canonical writes, implicit Obsidian sync, fabricated entities, graph-derived authority |
| Tool execution | **Not implemented**; M3 authorization still required | Future narrowly scoped tool adapter after threat model and permission engine | Self-authorization, silent consequential actions, broad vault access |
| UI and capture | Existing local browser; later mobile | Accessible components and narrowly scoped capture clients | Engagement objectives, bypass of preview/approval, uncontrolled sync |

**Evaluation protocol for each of the researched repositories (including all 42 when the external report is available):**

1. **Evidence:** repo name, pinned commit/version, license, maintenance/security signals, actual relevant modules and tested behavior. Distinguish README claims from verified behavior; don't invent an integration or claim comparative superiority without evidence.
2. **Need now?** State the current failing user journey or test, why existing code cannot reasonably solve it, and why deferring has a measurable cost. If there is no concrete need, decision = **defer**.
3. **Philosophy gate:** compare to the seven founding advantages above, name the constitutional/ADR clause, mark `pass / adapter-isolation-required / fail`, and record an explicit **philosophy erosion risk** (data ownership, autonomy, attention, authority, disclosure, exit).
4. **Technical fit:** boundary, dependency tree, license obligations, operational burden, testability, performance/privacy budget, maintenance, security and rollback. Technical maturity is **separate** from philosophical alignment; more stars or features cannot waive a failed gate.
5. **Alternatives:** keep existing code, implement a small local slice, use a library, or isolate a larger system behind an anti-corruption adapter. Explain the **Sovereign wins / repo wins** trade-off rather than replacing the plan wholesale.
6. **Exit test:** disable or remove the candidate; canonical export/restore, claims, Forget, permission enforcement and local evidence mode still work. Specify how data/config are migrated and how vendor outages degrade.
7. **Decision and review:** `adopt now / evaluate in lab / defer / reject` with owner, acceptance tests, founder signoff tier, and the exact PR/ADR. No bulk merge or auto-install of all 42.

**Candidate register row template:** `repo@commit | concrete need | component/seam | Sovereign philosophical advantage | repo's demonstrated advantage | philosophy alignment (pass/isolate/fail) | erosion/lock-in risk | license/security | smallest trial | rollback/exit proof | ROI (qualitative) | decision/status | ADR/PR/owner`. Populate from research; no candidate is approved by this template.

## 4. Prioritized delivery — smallest high-ROI work first

Priority means **risk reduction and useful capability per unit of complexity**, not a fabricated numerical forecast. M0–M5 and SB-0…SB-9 remain the authoritative numbering; these are cross-workstream execution packets.

| Order | Work packet and existing anchor | Why now | Gate / definition of done |
| --- | --- | --- | --- |
| **P0-A** | Repository hygiene — [PR #5](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/pull/5) | Stop committing local DB/bytecode/secrets; very small blast radius | Ignore/untrack tracked artifacts, CI path guard, full tests; review and merge separately |
| **P0-B** | Hidden-rowid storage-integrity repair — [issue #6](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/issues/6), ADR-0003 | Known bypass threatens tombstones, claim authority and evidence; blocks trustworthy SB-2 | Independent Tier 2 spec, adversarial exploit/recovery tests, schema/migration decision, full suite, founder approval; **separate PR** |
| **P0-C** | SOV-002 trust baseline: one-page threat model → auth/key/backup/restore/deletion policy ADRs | Needed before any real personal data, remote client or consequential tool | Defined attacker/assets/boundaries, failure tests, clean-machine recovery drill, explicit Security Gate review; **no premature claim of secure vault** |
| **P1-A** | Preserve and review Benchmark 0003 — [PR #4](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/pull/4) | Gives evidence for retrieval without changing disclosure | Keep **evaluation-only / DO NOT MERGE** pending its own direction; don't reimplement, don't enable Porter/BM25/embeddings |
| **P1-B** | SB-2 computed-on-read provenance + on-request Obsidian snapshot CLI | First valuable second-brain view without new authority/store | **After P0-B**; no schema change; exact scope, inert Markdown, closure, verification, snapshot disclosure, no sync, independent Tier 2 review |
| **P1-C** | First user journey / SOV-005 product-design pass | Existing app needs a clear, useful loop, not more infrastructure | Synthetic capture → inspect evidence/claim → correct → compile/preview → local answer/export → restore; usability and no-disclosure checks |
| **P2-A** | M3 bounded action and cognitive modes | Valuable after auth/policy is testable, not an agent-swarm prerequisite | Permission engine, scoped/revocable grants, action receipts, adversarial tool-input tests; separate Tier 2 ADR |
| **P2-B** | M4 offline mobile capture/sync | Useful only after local identity, recovery and tombstone semantics are safe | Authenticated device, offline queue, merge/Forget tests, loss recovery; not yet an integration to turn on |

**Explicitly not needed now:** autonomous agent swarms, scheduler/ambient ingestion (L5), new model gateways that bypass existing adapters, FTS5/BM25, embeddings/vector databases, external graph DBs, project/concept hubs without SB-3 schema approval, bi-directional Obsidian sync, native OS rewrite, new hardware, new telemetry/engagement dashboards, or a second retrieval benchmark. Revisit only against measured failure and approved scope.

## 5. Concrete engineering packets and acceptance checks

### Packet A — repository safety (Tier 0/1, PR #5)

- Keep `.gitignore` at the repository root; untrack the existing prototype DB and generated bytecode. Preserve synthetic demo Markdown/vault fixtures, not personal exports.
- CI rejects tracked DB/journal, bytecode, credential-like and private-export paths. Run existing full and adversarial suites and `git diff --check`.
- Explain that an ignore rule does **not** delete Git history or prevent a deliberately forced add. Do not claim secret scanning or real-data readiness.

### Packet B — storage-integrity blocker (Tier 2, issue #6)

- Start from the reproducible hidden-`rowid` REPLACE / UPDATE OR REPLACE defect in [Security Gate](../SECURITY-GATE.md) and [Codex audit](../reviews/2026-10-20-codex-audit-remediation.md). A per-connection `recursive_triggers=ON` setting alone is not a schema-level solution for arbitrary raw SQLite connections.
- First land an independently reviewed exploit matrix using synthetic vaults and default-pragmas connections. Test records, tombstones, claims, claim tombstones, evidence links and event history; include rowid aliases, ID reuse, approved-claim laundering and stale restore/import.
- Compare schema-level defenses, including `WITHOUT ROWID` where suitable, with explicit migration/legacy data and `claim_events` key semantics. Do not prescribe a risky migration without proof. Ensure every supported export still restores and that a failed migration leaves the original DB intact.
- Require independent adversarial review, versioned migration, documented reversal/recovery, and founder approval. Update claims of all-DML protection only **after** the fix passes.

### Packet C — Security Gate and recovery (Tier 2/3 design before sensitive data)

- Model threats: local browser and other localhost clients, malware on a device, malicious imported text, untrusted tools, stolen laptop/backup, provider disclosure/retention, user-held exports, third-party data, and sync replay.
- Decide authenticated local access and device identity; encrypted-at-rest vault and key custody; signed/integrity-checked backup and restore; retention/Forget/WAL/backups; consent/disclosure receipts; cost/error reporting. Use established primitives rather than custom cryptography.
- Test fresh-machine restore, failed/corrupted backup, unauthorized client, revoked capability, offline use, provider outage, and delete/reimport/restore tombstone dominance. No sensitive data until the full gate is independently passed.
- ADR-0005 **D15 remains deferred**: current lineage sensitivity is not certified safe. Do not treat a low-sensitivity successor as automatically safe for cloud simply because the current compiler allows it.

### Packet D — SB-2 user-visible second brain (Tier 2 after B)

- Compute canonical provenance nodes/edges **on read**, never via a second authoritative graph store. Local navigation may show claim-source and supersession links but may **not** admit linked records to model context (ADR-0004 decision 3, ADR-0005 R3).
- CLI exports a requested, authorized, one-way ZIP or *new* folder snapshot; no automatic sync/cleanup/registry, no import of edited Markdown. Follow [Obsidian projection](../second-brain/OBSIDIAN-PROJECTION.md) and [validation](../second-brain/SECOND-BRAIN-VALIDATION.md) exactly, including 140-byte names, inert text, scoped links, structural verification, no overwrite, Git-tree refusal and interrupted-export reporting.
- Test scope exclusion without leaking excluded IDs, Markdown/HTML injection, path collisions/traversal, interrupted writes, full structural link closure and native Obsidian no-network behavior where required. State that previous user-held exports are not erased by Forget.
- Only after evidence and founder review, offer the smallest discoverable UI affordance. Do not invent projects/concepts/typed factual edges.

### Packet E — product/design quality (Tier 1, synthetic data only)

- Treat **capture → inspect → correct → recall → control disclosure → export/restore** as the design spine. Make evidence vs. approved memory visibly distinct; don't conceal uncertainty or silently switch to cloud.
- Preserve an explicit local/offline path and a readable exact outbound-context preview. Sensitive/no-cloud refusal should explain the boundary without exposing other excluded items.
- Design for *fewer steps to a real result*, clear recovery, keyboard/accessibility, comprehensible copy, minimal notifications and no engagement loops. Use existing HTML/CSS/JS before adopting a component framework.
- Suggested (not yet founder-approved) evaluation: observe a small synthetic-task walkthrough, count completion/errors and unnecessary prompts, measure whether a user can explain what was sent, and ensure correction/export/restore are discoverable. Never optimize time-on-app as success.
- Avoid cosmetic rebrand or a dashboard rewrite before the golden path works.

## 6. Technical guardrails for every PR

- **One responsibility per PR:** don't combine storage migrations, retrieval policy, Obsidian export and UX redesign. Follow [Development review tiers](../DEVELOPMENT.md) and the existing CI; Tier 2/3 needs independent review and founder decision.
- **One canonical authority path:** storage writes and claim decisions through governed contracts; external tools may not bypass `store.py`/claim transitions. An external library cannot silently define schema semantics.
- **One disclosure choke point:** only the Context Compiler and explicit exact-plan approval may prepare/send personal context. Candidate retrievers return IDs for hydration; a policy change bumps `policy_version` and needs Benchmark 0003, adversarial tests and ADR-0004 review.
- **Reversibility:** for each stateful change document migration, restore, rollback, what survives removal, and which data copies cannot be recalled. For stateless features, prove removal returns baseline behavior.
- **Test what is claimed:** targeted unit/adversarial tests, complete `pytest -q`, `python -m compileall -q src tests`, `git diff --check` and applicable native/manual checks. Do not report CI as passed until its run completes.
- **Source hygiene:** no real private notes, credentials, provider payloads or vault DBs in Git, logs, fixtures or AI review transcripts. PR #5's tracked-path check is defense in depth, not comprehensive secret scanning.
- **Minimal dependency footprint:** prefer standard library and existing FastAPI/SQLite stack. A new service, queue, model framework or database requires a demonstrated need, cost and exit test.

## 7. Decision records, ownership and what happens next

| Decision | Current state | Owner / next action |
| --- | --- | --- |
| Constitutional ratification and source-completeness gap | **Open**; v0.3 candidate | Founder reviews exact text, reconciliation/waiver and records explicit founding act. This plan does not amend it |
| ADR-0005 D1–D14, R1–R7 | **Approved direction / planning** | Build only bounded approved slices, with their own reviews |
| ADR-0005 D15 lineage sensitivity | **Deferred; safety gap** | Founder-led Tier 2 proposal before relying on sensitive cloud workflows |
| Repo hygiene | **PR #5 open** | Review CI and merge independently |
| Storage rowid repair | **Issue #6 open** | Separate Tier 2 specification, implementation, adversarial audit and founder approval |
| Benchmark 0003 | **PR #4 open, DO NOT MERGE** | Preserve as evaluation; any change to that direction needs explicit decision |
| Security and real-data use | **Gate NOT PASSED** | Threat model, key/recovery/auth decisions, tests, independent review |
| External 42-repo research | **Comparison results not yet incorporated here** | Evaluate candidates one by one against `3; update a register only with evidence, no bulk import |

**Suggested next review order:** PR #5 hygiene → issue #6 storage-integrity spec and repair → security threat-model/recovery ADR → SB-2 scoped implementation → golden-path UX validation. Benchmark 0003 remains separate and evaluation-only. If research identifies a smaller proven solution, evaluate it using the same gates; **do not sacrifice Sovereign's founding advantage just because another repository is more feature-complete.**

**Definition of progress:** the founder can safely understand and reverse each new capability; existing local records, authority and exit survive every integration; useful tasks get easier; security claims become more evidence-backed; the number of dependencies and autonomous agents does not grow without need.
