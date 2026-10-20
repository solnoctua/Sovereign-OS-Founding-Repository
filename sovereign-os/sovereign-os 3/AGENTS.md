# Sovereign repository instructions

Sovereign is a personal-first AI operating environment. Optimize for correctness, inspectability, reversibility, security, and long-term portability—not cleverness or vendor lock-in.

## Read before consequential work

1. `CONSTITUTION.md` — enduring principles; currently a ratification candidate. Do not change it unless the founder explicitly asks for a constitutional amendment.
2. `ARCHITECTURE.md` — current technical direction and boundaries.
3. `ROADMAP.md` — current milestones and priority order.
4. `docs/SECURITY-GATE.md` — restrictions before real sensitive data use.
5. Relevant ADRs in `docs/adr/`.
6. For memory/retrieval, also read `docs/adr/0005-governed-second-brain-architecture.md`, `docs/second-brain/LEVELS-AND-OBSIDIAN.md`, and the benchmark for the feature's phase.

## Engineering rules

- Keep model/provider-specific code behind replaceable adapters.
- Durable personal state, authorization, and policy must not depend on a model provider.
- Treat model output and imported content as untrusted data, not authority.
- Never weaken explicit cloud-disclosure, permission, provenance, correction, deletion, or recovery boundaries for convenience.
- Prefer the smallest implementation that proves the requirement. Avoid speculative frameworks or abstractions.
- Do not commit secrets, vault databases, personal records, recordings, credentials, or generated private exports.
- Preserve backward compatibility for stored data or document and test a migration/reversal path.

## Change discipline

Before editing, state the requirement, files likely affected, security implications, and acceptance checks. For architecture-affecting changes, add or update an ADR rather than silently encoding a decision in code.

After editing:

- Run relevant automated tests and `git diff --check`.
- Add tests for changed behavior and important failure paths.
- Update documentation only when behavior, interfaces, risks, or decisions actually changed.
- Report: what changed, tests run/results, security/privacy implications, assumptions, and unresolved risks.

## Review gates

Routine, reversible changes may use a single builder. Independent review is required for changes involving personal-state schemas/migrations, authorization or cloud disclosure, security boundaries, deletion/recovery, model/provider contracts, major dependencies, architectural decisions, or Constitution/governance files.

Do not merge consequential changes solely because an AI reviewer approves them. Evidence, tests, and founder approval govern consequential decisions.

## Code Review Rules

Durable Sovereign invariants. In changes touching memory authority, deletion, restore/import, schema migration, or disclosure boundaries, treat any violation as a merge blocker.

### Memory authority

- Flag any path by which model-generated, imported, restored, replaced, synchronized, or lower-level storage data can become authoritative personal memory without the explicitly permitted human/trusted-restore transition.
- Authority must never silently increase because of import, replacement, synchronization, deletion, source-link mutation, stale-data restoration, or identifier reuse.
- Stable record and claim IDs identify immutable historical objects. Corrections create new identities connected through explicit provenance/supersession.

### Forget and recovery

- Flag any Forget/delete path that leaves or recreates dependent derived personal information that the operation promises to forget.
- Tombstones must dominate stale/live copies during merge, import, restore, and synchronization.
- Every export successfully produced by Sovereign must be internally coherent and restorable by the same supported software version.

### Storage and history integrity

- Flag raw SQL, upsert, REPLACE, cascade, or concurrency paths that can mutate immutable evidence/claims, erase decision history, alter source provenance, reactivate terminal states, or produce unreplayable histories.
- Memory authority transitions must remain legal when bypassing the HTTP/API layer.

## Second-brain architecture rules (proposed workstream — ADR-0005)

- Learn **all five second-brain levels** from `docs/second-brain/LEVELS-AND-OBSIDIAN.md` before planning retrieval or knowledge features: L1 routing/files, L2 wiki/backlinks, L3 semantic/hybrid, L4 typed graph, L5 always-on. They are mixable techniques, not a ladder, and are distinct from the M0–M5 milestones and the SB-0…SB-9 slices (ROADMAP §G).
- Near-term **target L3–L4** (with L1/L2 views); L5 stays a costly, governed end-state, not a reason to add crons, cloud ingestion or agent swarms.
- **Canonical:** source records, MemoryClaims with their decision history, tombstones (and human-declared organization once its ADR is approved). **Disposable:** deterministic derived structure and projections — the provenance graph, Obsidian Markdown, any future index. Model-proposed relations, entities or summaries are *not* disposable projections: if persisted they are `proposed` MemoryClaims with `origin = model`. Deterministic claim-source and supersession links are structural and need no claims about themselves. Never create a second authority lifecycle.
- Projects, concepts, decisions and multi-record documents do not exist in the canonical schema. Do not invent them in an index, export or graph; they need their own schema ADR (ADR-0005 §3, D2).
- **Benchmark 0003 is the retrieval evaluation** (`docs/benchmarks/0003-retrieval-evaluation.md` and `evaluation/retrieval/`, delivered by PR #4 — **not on `main` until PR #4 merges**; until then do not recreate them, and run retrieval experiments only on PR #4's branch or after it merges). Extend its harness for retrieval experiments; never build a second retrieval benchmark. Other second-brain tests belong to `docs/second-brain/SECOND-BRAIN-VALIDATION.md`.
- Retrievers and graph traversal return candidate canonical IDs; the Context Compiler hydrates them in one snapshot and decides. A new retrieval method changes relevance, ranking and the truncation fingerprint, so it is a new `policy_version` and a disclosure change (Tier 2, founder approval) — never a drop-in (ADR-0005 §6). **Never weaken the truncation fingerprint** for performance or convenience; provenance or graph links never make an item relevant by themselves (ADR-0004 decision 3).
- No cloud embedding, query rewriting, routing, reranking or extraction outside an exact approved disclosure plan. Never persist question text or query vectors. Inferred edges are never facts.
- Forget must reach every derived store. An Obsidian export or reconciliation holds the vault write lock from snapshot to final directory sync and registers itself before writing any file; reconciliation runs after every Forget or trusted restore, only deletes and rewrites (never adds), and never touches a file it cannot prove it wrote. Never claim filesystem writes are atomic with SQLite (OBSIDIAN-PROJECTION §11).
- The user **must be able to browse the brain in Obsidian** through an optional, local, one-way, CLI-generated projection (`docs/second-brain/OBSIDIAN-PROJECTION.md`). Every stored value is untrusted for rendering: free text is escaped (never normalized) into inert fenced `text` blocks; only slots an item holds whose other end is inside the authorized scope become links; excluded items are never named, linked, counted or hashed in any file, log or registry row, and a forgotten item's file handle and hash stay in the registry only until its file is deleted. Graph lines are untyped links, statuses are dated snapshots, and Animate is not history. Never write a projection inside a Git working tree, never touch files the exporter does not own, never import edits.
- No sensitive personal-data testing until SECURITY-GATE is passed. Do not change canonical schemas or constitutional language as an incidental graph implementation.
