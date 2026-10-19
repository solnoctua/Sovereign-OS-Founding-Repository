# Sovereign repository instructions

Sovereign is a personal-first AI operating environment. Optimize for correctness, inspectability, reversibility, security, and long-term portability—not cleverness or vendor lock-in.

## Read before consequential work

1. `CONSTITUTION.md` — enduring principles; currently a ratification candidate. Do not change it unless the founder explicitly asks for a constitutional amendment.
2. `ARCHITECTURE.md` — current technical direction and boundaries.
3. `ROADMAP.md` — current milestones and priority order.
4. `docs/SECURITY-GATE.md` — restrictions before real sensitive data use.
5. Relevant ADRs in `docs/adr/`.

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
