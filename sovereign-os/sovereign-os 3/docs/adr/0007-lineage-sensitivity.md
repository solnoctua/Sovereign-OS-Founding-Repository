# ADR-0007 — Sensitivity never decreases through lineage (D15)

- **Status:** **PROPOSED** (Tier 2, Context Compiler disclosure policy). Nothing is implemented. Adopting it is an ADR-0004 amendment with a `policy_version` bump, adversarial tests, an independent reviewer findings artifact and founder approval. Current behaviour is unchanged and not certified safe for real private data (ADR-0005 D15, deferred 2026-10-21).
- **Date:** 2026-10-22
- **Decision owner:** Human project owner
- **Required before:** usage threshold 3, intermediate private use (`docs/SECURITY-GATE.md`). Not required for synthetic or threshold-2 project use.

## Problem

Cloud eligibility follows the sensitivity of an item's **current evidence** (ADR-0004). Two paths let the restated content of a sensitive item become cloud-eligible without any decision that says so.

1. **Claim supersession (D15).** Claim B supersedes sensitive claim A. B cites only private records, so B is `private`, yet B's text often restates A's.
2. **Record correction (new, found 2026-10-22).** `POST /api/memories/{id}/correct` accepts any `sensitivity`. A correction of a `sensitive` record can be stored as `private`, and its content usually restates the original. The browser UI resends the original sensitivity, but the server does not require it.

Benchmark 0003's corpus contains neither pattern: its 3 record corrections and 1 claim supersession keep their sensitivity. The rule below would therefore change no inclusion or exclusion there, only the `policy_version` inside tokens.

## Requirements

1. An item's effective sensitivity is never lower than that of any item it corrects or supersedes, transitively. An accidental correction flow must not lower it.
2. A predecessor that is missing (forgotten, never restored, dangling) **fails closed**: the successor is treated as `sensitive`, because Sovereign can no longer tell what it restated.
3. Lowering sensitivity is possible only through a deliberate, recorded human act that names what it is doing.
4. Every change of effective sensitivity invalidates pending cloud approvals (the truncation fingerprint already binds the derived sensitivity of every relevant claim; records would need theirs added).
5. Local use is unaffected: the restriction concerns the cloud boundary only.

## Proposed decision

1. **Claims.** `inherited_sensitivity` becomes the most restrictive of:
   - the claim's own evidence (today's rule);
   - the derived sensitivity of every predecessor reached by following `supersedes_id`, transitively. Chains are linear and acyclic (ADR-0003), so the walk terminates.

   A dangling predecessor yields `sensitive`.
2. **Records.** A record's *effective* cloud sensitivity becomes the most restrictive along its correction lineage (`supersedes_id`, transitively), and a dangling predecessor yields `sensitive`. The stored `sensitivity` column stays immutable and unchanged, so no schema change is needed. Additionally, the correction endpoint rejects a correction whose requested sensitivity is lower than its predecessor's, with a 422 that names the declassification path.
3. **Declassification (requirement 3).** It needs one explicit act in V0. Recommended: **write a new, unlinked record or claim**, which already exists and needs no code. A new item has no lineage, so it is judged on its own evidence. The UI copy for correction states that a correction keeps the original's sensitivity, and that to declassify one writes a new note deliberately. A recorded "declassify" transition with a reason is a possible later refinement and would need a schema change.
4. **Fingerprint.** `_claim_retrieval_state` uses the lineage-aware sensitivity. `_record_retrieval_state` adds the record's effective sensitivity, because today it carries only the stored column.
5. **Policy version.** `sovereign.context.v0` becomes `sovereign.context.v1`. Every pending token changes once. Benchmark 0003 is regenerated in the same PR, and its numbers are expected to be unchanged apart from tokens.

## Alternatives

| Alternative | Assessment |
| --- | --- |
| One predecessor only (the reviewer's first suggestion) | Rejected: A → B → C lets C drop A's sensitivity after two hops |
| Dangling predecessor treated as absent | Rejected: forgetting a sensitive record forgets the claims citing it, leaving a private successor whose text may restate it, so absent must fail closed |
| A stored `sensitivity` column on claims set at supersession | Rejected for V0: a schema change and a second source of truth for a derived value |
| Keep deferring and forbid cloud use at threshold 3 | Viable and simpler; loses cloud reasoning over private data until decided |
| Content similarity checks between successor and predecessor | Rejected: a classifier is not a policy (ADR-0004) |

## Risks

- **Over-restriction.** A correction that genuinely removed the sensitive part stays sensitive for cloud use until the owner writes a new note. This is acceptable in V0 and visible as `sensitive_cloud` in the preview.
- **Out of scope: laundering through a new note.** Writing a new unlinked note is the declassification path. It is a human act, and V0 cannot distinguish deliberate from careless use of it. The UI copy is the mitigation.
- **Untrusted import** brings claims without lineage (`supersedes_id` is dropped). Imported claims are proposals; approving one is the human decision.

## Tests the implementing PR must include

- Sensitive A superseded by B (private evidence): B is `sensitive_cloud`. The same holds for A → B → C.
- A forgotten, so the predecessor dangles: B is `sensitive`. Trusted restore with a conflict-skipped predecessor gives the same result.
- A sensitive record corrected: the API refuses `private`; a correction stored by raw SQL is still effectively sensitive.
- A new, unlinked note citing private evidence is `private` (the declassification path works).
- A pending cloud token returns 409 when a predecessor's effective sensitivity changes, for example when it is forgotten.
- Local plans are unaffected.
- Benchmark 0003 regenerated with no inclusion change.
- The adversarial suite passes.

## Founder decisions requested

1. Adopt transitive, fail-closed lineage for claims **and** records (recommended), or claims only.
2. V0 declassification by writing a new unlinked note (recommended), or a recorded declassify transition (schema change).
3. Whether the correction endpoint should reject lowering sensitivity (recommended) or only warn.
