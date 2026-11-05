# ADR-0007 — Lineage sensitivity: correction and supersession never make content cloud-eligible (D15)

- **Status:** **PROPOSED — revision 2 (2026-11-05).** The founder approved the **policy direction** on 2026-11-05: D15 *Option C*, full transitive, fail-closed sensitivity inheritance across source records and MemoryClaims ([founder decision comment on PR #13](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/pull/13#issuecomment-6672042826)). The detailed policy in this document and its implementation are **pending independent Tier 2 policy review and the founder's ratification and merge authorization**; this document does not ratify itself. **Nothing is implemented.** Current behaviour is ADR-0004's and is not certified safe for real private data. The Security Gate remains **NOT PASSED**.
- **Date:** 2026-10-22 (revision 1, `bc9a924`); 2026-11-05 (revision 2, against `main` at `3740119`)
- **Decision owner:** Human project owner
- **Review tier:** Tier 2 (cloud-disclosure policy and write validation). The implementation is a separate Tier 2 PR (§14).
- **Resolves:** [ADR-0005](0005-governed-second-brain-architecture.md) D15, deferred on 2026-10-21 (§15.1 there).
- **Amends, on acceptance:** [ADR-0004](0004-governed-retrieval-context-compiler.md) (*Sensitivity inheritance*, *Disclosure*, *Exact-plan approval*, the bundle contract, `policy_version`) and [ADR-0003](0003-memory-claim-authority.md) (the record-correction endpoint; ordinary import of claim lineage). This PR edits neither; the amendment text lands with the implementation (§14).
- **Defers:** D16, governed declassification, to [Issue #25](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/issues/25). It is a future direction, not an authorization (§11).
- **Required before:** usage threshold 3 (`docs/SECURITY-GATE.md`). Not required for synthetic or threshold-2 use.

## Summary

Today a source record's cloud eligibility follows its own stored label, and a MemoryClaim's follows its current evidence (ADR-0004). So correction and supersession can make restated sensitive content cloud-eligible without any decision that says so.

This ADR defines one **effective sensitivity**. It is derived at read time from canonical state, in the compiler's single snapshot, and it is the only value the cloud boundary uses. An item is effectively `private` only if its own label (record) or its evidence (claim) is private **and** every item it corrects or supersedes, transitively, can be resolved and is private. A predecessor that is missing, cyclic, malformed or beyond a fixed bound fails closed.

Stored labels, authority, support, local use and Forget are unchanged. The correction API refuses ordinary downgrades. There is no declassification in D15.

## 1. Context

### 1.1 Current mechanisms (verified on `main` at `3740119`)

| Mechanism | Where | Behaviour today |
| --- | --- | --- |
| Record label | `records.sensitivity`; immutable (`records_immutable` trigger); part of `evidence_hash` | `private` or `sensitive` (storage CHECK) |
| Record correction | `POST /api/memories/{id}/correct` → `Vault.add(content, sensitivity, supersedes_id)` | Accepts any requested label. `NoteIn.sensitivity` defaults to `private`. The UI resends the original's stored label, but the server does not require it |
| Claim sensitivity | `context.inherited_sensitivity(sources)` | `private` only if every current link is present, hash-verified and its record is *stored* `private`. Predecessors are not consulted |
| Candidate label | `context._candidates` | records: the stored label; claims: the evidence-derived value above |
| Cloud exclusion | `context._reasons` | `sensitive_cloud` when the candidate's label is not in `ContextPolicy.cloud_sensitivities = {"private"}` |
| Pinned sensitive record | `context.build_bundle` | `blocked` (`sensitive_selected`), then 403, when a pinned record's stored label is not `private` |
| Fingerprint | `store._record_retrieval_state`, `store._claim_retrieval_state` | records: stored label and evidence hash; claims: evidence-derived sensitivity, and each source's state, stored label and pinned hash |
| Token | `context._token` | included items: their label among other fields; excluded items: id, type and reasons only |
| Policy version | `context.POLICY_VERSION` | `sovereign.context.v0` |

### 1.2 Gaps, reproduced on `main` with synthetic data (2026-11-05)

Each gap was reproduced against `3740119` in a throwaway vault, with a mocked provider that was never called. The reproduction script and its output are attached to PR #13 for the reviewer.

- **G1 — correction downgrade.** A `sensitive` record corrected with `"sensitivity": "private"` returns 200. The correction is stored `private` and is **included** in a cloud preview.
- **G2 — claim supersession.** Claim A cites sensitive evidence. B supersedes A and cites only private evidence. B is included in a cloud preview as `private`. So is C, which supersedes B (two hops).
- **G3 — dangling claim predecessor.** Forgetting A's evidence forgets A (ADR-0003 trigger). B survives with a `supersedes_id` that names nothing, and stays eligible.
- **G4 — dangling record predecessor.** Forgetting an older revision leaves its correction with a dangling `supersedes_id`. The correction stays eligible.
- **G5 — malformed lineage is reachable.**
  - A raw connection with `PRAGMA ignore_check_constraints=ON` can insert a claim that supersedes itself: the BEFORE INSERT trigger cannot see the row being inserted, and the CHECK that forbids it is off.
  - Legacy (ADR-0002) records may hold self-supersession, forks, cycles and dangling pointers.
  - A current correction can be attached to a legacy record whose own lineage reaches a cycle (reproduced with a trusted restore of legacy rows).
- **G6 — untrusted import.**
  - A file chain `sensitive → private` is imported with its record lineage intact and the lower label kept.
  - A file record whose predecessor is absent is accepted.
  - An imported claim's `supersedes_id` is discarded, so the lineage the file states is lost.
- **G7 — evidence laundering (found in this revision).** Claim sensitivity reads each evidence record's *stored* label. A claim citing a record whose label was lowered by G1, G6 or raw SQL would stay `private` even if record lineage alone were fixed.

Revision 1 named G1–G4 and part of G6. G5, G7 and the claim side of G6 are new in revision 2. Benchmark 0003's corpus contains none of these patterns (§15, row 17).

### 1.3 Scope

D15 decides one thing: whether an item may cross the cloud boundary. It does not decide authority (ADR-0003, ADR-0006), relevance or ranking (ADR-0004), or what the owner may read locally.

## 2. Founder decisions recorded

**2026-11-05** (the founder's PR #13 comment and the founder directive for this revision):

1. **D15 = Option C, approved as direction.** Full transitive, fail-closed sensitivity inheritance for **both** source records and MemoryClaims. A successor inherits the most restrictive of:
   - its own classification;
   - its evidence and dependencies;
   - every predecessor in its correction or supersession lineage;
   - any unresolved predecessor, which counts as sensitive.
2. **Fail closed.** A missing, forgotten, dangling, invalid, unverified, malformed or unevaluable predecessor makes the successor sensitive, whatever the successor's stored label. Legacy and malformed histories are bounded and fail safely.
3. **Write boundary.** An ordinary correction cannot silently request `private`, and the correction API rejects requested downgrades. Historical and raw-SQL-lowered rows are restricted at the disclosure boundary, whatever their stored label.
4. **Two levels stay** (`private`, `sensitive`). No new classifications, category rankings, persistent sensitivity store or redesigned memory schema.
5. **Disclosure is not authority.** Approval, evidence integrity, support (`stale`, `orphaned`), canonical authority, local retrieval eligibility and Forget semantics are unchanged. A claim may be authoritative locally and still be prohibited from cloud transmission.
6. **Rationale is not permission.** Classification rationale, provenance annotations, explanatory prose, unverifiable lineage metadata and model judgments may inform later human review. They never make an item fail open.
7. **No covert ledger.** No new ledger, no retained forgotten content, no expanded tombstones. A missing ancestor therefore stays sensitive.
8. **No declassification in D15 V1.**
   - An ordinary unlinked new note is not a declassification act; it is a documented restatement limitation.
   - No human or automatic release endpoint is authorized.
9. **Integration.**
   - Effective sensitivity is computed in one read snapshot together with candidate selection and the complete pre-truncation retrieval state.
   - The fingerprint binds lineage-derived sensitivity, so earlier approvals are invalidated.
   - `sovereign.context.v0` becomes `v1`, Benchmark 0003 is regenerated, and adversarial tests are added.
10. **D16 (Option D) is approved as future direction only** (Issue #25):
    - first, explicit human-authorized declassification with a precise affected-memory preview;
    - later, local rule- and model-assisted recommendations;
    - no autonomous downgrade.
11. **Process.**
    - This PR is policy and specification only.
    - The implementation is a separate Tier 2 PR with tests, the policy-version bump, an independent findings artifact and founder approval.
    - Nothing here authorizes a merge, real personal data or a new external disclosure. PR #24 is untouched.

**Earlier:** on 2026-10-21 the founder deferred D15 (ADR-0005 §15.1). The 2026-11-05 direction ends that deferral and changes none of ADR-0005's other decisions.

## 3. Terms

- **Stored label:** `records.sensitivity` as written. It is immutable and remains a property of the historical record. Claims have no stored label.
- **Effective sensitivity:** `private` or `sensitive`, derived at read time. It is the only value the cloud boundary uses, and it is never stored.
- **Predecessor:** the item an item's `supersedes_id` names, looked up **in the same kind only**: a record's among `records`, a claim's among `claims`. The two id namespaces are separate, as in SB-2a.
- **Lineage:** the predecessors reached by following `supersedes_id`, in order p1, p2, ….
- **Own-private:**
  - a record whose stored label is exactly the text `private`;
  - a claim whose **evidence-derived sensitivity** (§4.2) is `private`.
  - Anything else counts as sensitive, including NULL, other text and non-text values (positive validation, as today).
- **Bound `L`:** `ContextPolicy.max_lineage_depth = 1000` predecessors (§8).

## 4. Decision: the effective-sensitivity contract

### 4.1 Source records

A record is effectively `private` **iff** all of the following hold:

- it is own-private;
- its lineage is resolved (§4.3);
- every record in its lineage is own-private.

Otherwise it is effectively `sensitive`. The stored label is never changed. Effective sensitivity is always equal to or stricter than the stored label.

### 4.2 MemoryClaims

A claim's **evidence-derived sensitivity** is `private` **iff** all of the following hold:

1. it has at least one evidence link;
2. every link is present and hash-verified (state `active` or `superseded`, `claims.VERIFIED_STATES`);
3. every linked record is **effectively** `private` (§4.1), not merely stored `private`. This closes G7;
4. its evidence-set integrity is `committed` (ADR-0006, D-A). A set whose completeness cannot be proven (`unconfirmed`), or that differs from its commitment (`mismatch`), may have lost a sensitive link, so it cannot vouch for `private`.

Conditions 1–2 are today's `inherited_sensitivity`; conditions 3 and 4 are new. An approved, authoritative claim is always `committed`, so condition 4 changes nothing for any claim that can be included today. It matters only for display and for successors.

A claim is effectively `private` **iff** all of the following hold:

- its evidence-derived sensitivity is `private`;
- its lineage is resolved (§4.3);
- every claim in its lineage has evidence-derived sensitivity `private`.

The two inheritance routes:

- **Routes that exist.** A claim inherits through its own supersession lineage, and through the record lineage of each piece of its evidence (condition 3).
- **Routes that do not.** A claim does not inherit from other claims that cite the same evidence. Records never inherit from claims.

Record resolution never consults claims, so the two resolutions cannot depend on each other cyclically.

**Example (founder directive).** A is sensitive; B supersedes A and cites private evidence; C supersedes B and cites private evidence. B and C are effectively `sensitive` (basis `lineage`). No ordinary supersession erases A's restriction.

### 4.3 Unresolved lineage fails closed

Walking predecessors, the lineage is **unresolved** at the first step where any of the following holds:

- the pointer is not text (**malformed**);
- no item of the same kind has that id (**missing**: forgotten, never restored or never existing). Sovereign does not distinguish these cases and reads no tombstone to do so;
- the item was already visited in this walk, the start included (**self-supersession or cycle**);
- `L` predecessors have been visited and the last one still names a predecessor (**bound**).

An item whose lineage is unresolved is effectively `sensitive`.

Status anomalies do not make a lineage unresolved, for example a predecessor that is not `superseded`, or two successors of one predecessor. The predecessor can still be evaluated, and inheritance can only add restriction.

### 4.4 Reference definition and explanation code

This is the normative definition. An implementation must return exactly its result for every item. It may memoize (§8).

```text
own_private(item):
    record: stored label is exactly the text "private"
    claim:  evidence-derived sensitivity is "private"            # §4.2, conditions 1–4

resolve(x, L):                                                     # x is a record or a claim
    if not own_private(x):
        return "sensitive", ("own" if x is a record else "evidence")
    visited = {x}; walked = []; ending = "root"; current = x
    while current.supersedes_id is not NULL:
        pointer = current.supersedes_id
        if pointer is not text:            ending = "unresolved"; break      # malformed
        if len(walked) == L:               ending = "unresolved"; break      # bound
        p = the item of x's kind whose id == pointer
        if p is None or p in visited:      ending = "unresolved"; break      # missing, self or cycle
        visited.add(p); walked.append(p); current = p
    if any(not own_private(p) for p in walked):  return "sensitive", "lineage"
    if ending == "unresolved":                   return "sensitive", "lineage_unresolved"
    return "private", null
```

`sensitivity_basis` explains an effectively sensitive item, using one of these codes:

| Code | Meaning |
| --- | --- |
| `own` | The record's own stored label is not `private`. |
| `evidence` | The claim's evidence-derived sensitivity is not `private`. |
| `lineage` | A predecessor it reached is not own-private. |
| `lineage_unresolved` | Its lineage is missing, malformed, cyclic or beyond `L`, and no reached predecessor is sensitive. |
| `null` | Effectively `private`. |

The precedence is the order of the `return` statements. The basis is a function of the item's own lineage, so it does not depend on which other items a request touches.

### 4.5 What does not change

- **Storage.** Stored labels, the schema, the triggers (44), `SCHEMA_VERSION` 5, backup format 3 and the export payload.
- **Authority.** The MemoryClaim lifecycle, support, evidence-set integrity, `claims.is_authoritative` and ADR-0004's authority table.
- **The local boundary.** `sensitive_cloud` applies only to cloud targets. Local bundles may use effectively sensitive eligible items exactly as today.
- **Relevance, ranking, budget and candidate sets.** Lineage only restricts; it never admits, ranks or pins anything. An ancestor is read for its sensitivity only and never becomes a candidate through lineage, so ADR-0004 decision 3 holds.
- **Forget.** The Forget plan, its impact token and its effect are unchanged, and so are tombstones.
- **Provider boundary.** Provider isolation, prompt rendering and request-scoped labels.

## 5. Write boundary: record correction (amends ADR-0003)

- **Request.** `POST /api/memories/{id}/correct` takes `sensitivity` as optional: `private`, `sensitive`, or omitted. It gets its own request model. `POST /api/memories` (a new, unlinked record) is unchanged.
- **Check.** `Vault.add` computes the predecessor's effective sensitivity (§4.1, bound `L`) inside the correction's existing `BEGIN IMMEDIATE` transaction, before inserting:

  | Requested | Predecessor effectively `private` | Predecessor effectively `sensitive` |
  | --- | --- | --- |
  | omitted | stored `private` | stored `sensitive` |
  | `sensitive` | accepted | accepted |
  | `private` | accepted | **422**, nothing written |

- **Refusal text.** The 422 uses one fixed message that carries no record content, no id and no predecessor detail: *"This record is restricted to this device, directly or through an earlier version, so its correction cannot be marked private. Omit the classification or choose sensitive."*
- **Why the effective value, not the stored one.** A stored-`private` successor of a sensitive record (from G1 history, G6 or raw SQL) is then not relabelled `private` again at each correction. The stored label of every new correction is honest.
- **Not the security boundary.** The read-time derivation (§4) is. A correction inserted by raw SQL with any label is still effectively sensitive.
- **No storage trigger enforces it**, for three reasons:
  - a trusted restore must round-trip historical downgrades that are already stored (`AGENTS.md`, *Forget and recovery*). A trigger would make such backups unrestorable, or need a legacy exemption that reopens the gap;
  - triggers are an integrity mechanism against connections, not a boundary against processes (`ARCHITECTURE.md` §14);
  - a trigger is a schema change (the trigger-count invariant and a migration), and the derivation already covers raw SQL.
- **Claims.** Claim supersession has no label in its request, so it needs no write check.
- **UI.** The correction dialog sends no classification and states: "A correction keeps the restriction of the record it corrects."

## 6. Import, restore, export, legacy data and raw SQL

- **Export and trusted restore: unchanged.** They carry stored labels and pointers exactly, and the target vault derives effective sensitivity on read. A historical downgrade round-trips as stored and stays effectively sensitive.
- **Trusted restore with a conflict-skipped or absent predecessor.** The successor is stored with a dangling pointer, as today, and is effectively sensitive (`lineage_unresolved`).
- **Ordinary import, records: unchanged.** The file's record lineage is kept (G6), and §4.1 applies to it. A file chain `sensitive → private` and a file record with an absent predecessor are effectively sensitive.
- **Ordinary import, claims (amends ADR-0003's import table; resolves the claim side of G6).** Today the file's `supersedes_id` is discarded, so an imported correction loses the lineage its file states. Proposed rule:
  - **Pointer.** When a live file claim names a predecessor `P`, the imported claim is stored with `supersedes_id = uuid5(IMPORT_NAMESPACE, P)`. That is the namespaced id a file claim `P` itself would receive.
  - **Effect.** Superseded file claims are never imported, so that id normally names nothing. The imported claim is then effectively sensitive (`lineage_unresolved`): it fails closed on a lineage Sovereign cannot verify.
  - **Skip instead.** The claim is skipped, and counted in `claims_skipped`, when:
    - the namespaced predecessor already exists here and is not `superseded`; or
    - another claim here already names it as predecessor.

    These are the cases the `claims_linear_supersession` trigger would refuse, so an inconsistent file never aborts the whole import.
  - **Safety.** The rule restricts an untrusted file's own claims; it never lowers anything local.
  - **Unchanged.** Imported claims stay `proposed`, `origin = imported`, and attach only to evidence already present.
- **Legacy (ADR-0002) records.** Stored labels and anomalous lineage are preserved exactly. A legacy record whose lineage is or reaches a dangling, self-referencing or cyclic pointer is effectively sensitive. Legacy records without lineage are unaffected; the legacy-ID egress fixture in `tests/adversarial/test_context_compiler_adversarial.py` has none.
- **Raw SQL and lower-level writers.** §4 evaluates on read every row a connection can write; nothing depends on the API path.
  - Labels and pointers are immutable under the triggers, so a connection can add rows but cannot lower an existing label.
  - An added row's effective sensitivity is never lower than its lineage's.
  - A process that drops triggers or rewrites the file is outside the guarantee (ADR-0003, *Not guaranteed*), as today.

## 7. Disclosure boundary: compiler, preview, payload and token

### 7.1 One snapshot

- `Vault.context_candidates` computes the effective sensitivity and basis of every item it reports, inside its existing single read transaction and from the same rows:
  - candidate records, pinned and retrieved;
  - candidate claims, and each of their sources;
  - every matching record and claim, and every provenance-linked claim, that enters the fingerprint.
- Ancestors are read in that transaction even when they are not candidates, lie below the cutoff or are irrelevant to the question.
- Nothing is derived after the transaction closes, and nothing is cached between requests.

### 7.2 One value everywhere

- **Candidates.** `RetrievalCandidate.sensitivity` holds the effective value. This is a contract change for records; for claims it was already a derived value. A new field, `sensitivity_basis`, carries the code.
- **Exclusion.** `_reasons` gives `sensitive_cloud` when the effective value is not in `cloud_sensitivities`. There is no new reason code, and the ADR-0004 precedence is unchanged.
- **Pinned records.** A pinned record that is effectively sensitive blocks a cloud plan (`sensitive_selected`, then 403). The detail is a fixed, content-free sentence: *"Sensitive source records, including corrections of sensitive or unverifiable earlier versions, cannot be sent to cloud providers. Deselect them or use local mode."*
- **Execution.** `/api/ask` recompiles with the same function. The provider receives the verified bundle's `messages`, built only from included items, all of them effectively private. No other path reads sensitivity for egress.
- **Outbound.** `outbound.items[].sensitivity` and `disclosure.outbound_sensitivities` use the effective value (always `private` for included items). `sensitivity_basis` never enters `outbound` or `messages`.

### 7.3 Fingerprint and token (amends ADR-0004, *Exact-plan approval*)

- **`_record_retrieval_state`** appends the effective sensitivity and the basis. The stored label is already pinned by the evidence hash.
- **`_claim_retrieval_state`** replaces the evidence-only inherited sensitivity with the effective sensitivity and the basis. Each source entry gains that record's effective sensitivity.
- **`_token`**:
  - an included entry appends the basis; its `sensitivity` field now holds the effective value;
  - an excluded entry becomes `[id, type, reasons, effective sensitivity, basis]`.
- **Why the derived pair is enough.** Lineage affects policy only through (effective sensitivity, basis). Binding that pair for every relevant item and every candidate therefore binds the policy-relevant state of every predecessor consulted. Binding raw ancestor fields (status, history) would only add over-invalidation.
- **What invalidates.** Any change that alters a relevant item's pair changes the fingerprint or the token. The old cloud approval then gets 409, with no provider call, even when the item is below the cutoff and the messages are identical. Examples:
  - a predecessor or its evidence forgotten;
  - a restore or raw-SQL insertion reaching the item's lineage;
  - an evidence change;
  - a lineage crossing the bound.
- **What still does not.** A change that alters no relevant item's pair leaves the token valid, as ADR-0004 requires.
- **Conservative.** The basis is bound, so a change from `lineage` to `lineage_unresolved` invalidates even though the decision is the same (ADR-0004, *Invalidation is conservative*).

### 7.4 Policy version

- `sovereign.context.v0` (verified as the current value) becomes `sovereign.context.v1`. `ContextPolicy.max_lineage_depth = 1000` is part of v1.
- Every pending token, cloud and local, changes once: a previewed plan gets 409 and must be previewed again.
- No v0 token can authorize a v1 plan, because the version is inside the token.

### 7.5 Explanation and content safety

| Basis | Preview text (local only) |
| --- | --- |
| `own` | "sensitive — stays on this device" (the existing label) |
| `evidence` | "cites sensitive or unverifiable evidence — stays on this device" |
| `lineage` | "corrects or supersedes something sensitive — stays on this device" |
| `lineage_unresolved` | "an earlier version is missing or its history cannot be verified — stays on this device" |

- **Where it appears.** The codes appear only locally: in the bundle's `included[]` and `excluded[]`, and in the library. They contain no text from any item, never name an ancestor, never say whether a missing predecessor was forgotten (no tombstone is read), and never reach a provider.
- **Library.** `GET /api/memories` adds `effective_sensitivity` and `sensitivity_basis` to each record; its `sensitivity` stays the stored label. The UI tag shows the effective value and marks it as inherited when it differs from the stored label.
- **Provenance view.** SB-2a keeps showing the stored label, captioned as such, because navigation is not disclosure policy (ADR-0005 §8.1). It does not compute effective sensitivity.
- **Forget dialog.** It gains one static sentence: "Later revisions of what you forget, and claims that replaced the claims it removes, stay restricted to this device." The Forget plan, impact token and effect are unchanged.

## 8. Resource bounds and complexity

- **Per-item bound.** No walk visits more than `L` predecessors; one more makes the lineage unresolved (§4.3). The result depends only on the item's own lineage, so it is deterministic.
- **Compile (`context_candidates`):**
  - **Records.** The existing `SELECT * FROM records` scan already reads every record. The resolver uses an in-memory map built from that scan (id → pointer, stored label). There is no SQL per lineage step.
  - **Claims.** The existing `SELECT id, text, created_at FROM claims` scan adds `supersedes_id`, which gives an in-memory pointer map. Predecessors that are not already hydrated candidates need their evidence-derived sensitivity. It is read set-oriented:
    - their `claim_sources` and `claim_evidence_sets` rows are fetched in batches of ids, a bounded number of statements per batch, never one per lineage step;
    - each linked record's state and effective sensitivity come from the record map;
    - `evidence_hash` is computed at most once per record.
  - **Memoized.** Each item's result is computed once per compile and shared by every candidate whose lineage reaches it. For example, store per item the distance to its first predecessor that is not own-private and how and where its walk ends, capped at `L + 1`; resolve cycle members by one bounded walk.
  - **Cost.** Total work is O(R + C + links) for R records, C claims and their links in the snapshot, the same order as the scan the compiler already performs. Memory is O(R + C) identifiers, small next to the record contents that scan already loads.
  - **Iterative.** Walks are iterative, so no recursion limit applies.
- **Correction check.** At most `L + 1` primary-key lookups, or one recursive CTE with a depth limit, in the write transaction.
- **Library listing.** A batched walk for the listed records (at most 60): at most `L + 1` batched queries, or one lightweight scan of `(id, supersedes_id, sensitivity)`.
- **Failure mode.** Exceeding the bound or meeting malformed state never raises and never returns partial results. The affected item is effectively sensitive with basis `lineage_unresolved`; every other item is unaffected. A row SQLite cannot decode already makes the compile fail before any provider call (unchanged), and D15 adds no new decoding path.
- **Why `L = 1000`.**
  - It is two orders of magnitude above the longest lineage in any fixture (14, in `test_long_lineages_restore_in_any_payload_order`) or in the benchmark (2).
  - It keeps the write-time check to at most 1,001 indexed lookups.
  - A longer lineage is unusual enough to restrict, and the preview says why.
  - Changing `L` is a policy-version change.
- **Measurement.** Performance acceptance counts SQL statements and lookups, never wall-clock time (§15, P1–P4). Benchmark 0003 makes no timing claims either.

## 9. Content, provenance, rationale and authorization stay separate

| Concept | What it is | In D15 V1 |
| --- | --- | --- |
| Canonical memory content | Record content, claim text | Governed by Forget, unchanged. D15 reads only live rows |
| Provenance | `supersedes_id`, `claim_sources` | Read as it is; never created, extended or copied (except the import pointer in §6, which names a file id, not content) |
| Classification rationale | Why something is restricted | Only the derived `sensitivity_basis` code, recomputed per request and never stored. No rationale text exists |
| Authorization decision | A human permitting a disclosure | Only ADR-0004's per-request exact-plan approval. No standing or declassification authorization |

- **Nothing new is stored.** No new table, column, ledger, cache or log; no tombstone gains a field. Effective sensitivity is never persisted, so Forget has nothing new to reach.
- **Forget is never a declassification route.** Removing a sensitive predecessor, or the evidence whose Forget removes it, leaves its successors pointing at nothing, and that fails closed. Without fail closed, Forget would release exactly the restated text it should protect.
- **Rationale never authorizes.** The derivation reads no note, prose field, model output, import note or annotation. Inferred meaning, such as a model or rule judging content harmless, is not an input in V1. Under D16 it could at most produce a recommendation for a human.
- **Future receipts (D16).** If a decision receipt cannot be retained without keeping forgotten content or reconstructable details, the receipt is redesigned. Forget is not weakened.

## 10. Ordinary unlinked notes

- **Judged on their own.** A new record (`POST /api/memories`) or a new claim (`POST /api/claims`) has no lineage. It is judged on its own label or evidence, exactly as today.
- **Not declassification.** Sovereign cannot tell a deliberate rewrite from a sensitive fact copied into a new note; the act is not recorded as a release; and nothing verifies who did it or why. Revision 1's description of this as the declassification path is withdrawn (§12, C1).
- **A documented limitation.** D15 protects only the lineage Sovereign recorded. Content restated outside recorded lineage is outside D15 (§16, R1), for example:
  - a new note;
  - a new claim citing different evidence;
  - text pasted between items;
  - an edited import file.

  D15 adds no content-similarity check: a classifier is not a policy (ADR-0004).
- **UI.** The UI must not present writing a new note as a way to make something cloud-eligible.

## 11. D16: deferred, and what D15 must not foreclose

Governed declassification is approved only as a future direction, tracked in [Issue #25](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/issues/25). Its requirements and the staged path from human decisions to local intelligence (stages A–D) are recorded there; none is authorized. D15 V1 keeps that path open without weakening its guarantees:

1. **Derived, not stored.** A future verified authorization can become one more explicit input to the derivation, scoped to an item, a derivative, a field or a sanitized summary, without migrating stored labels or releasing the ancestor chain.
2. **The default stays fail closed.** An exception exists only where a verified, scoped, recorded human authorization grants it. A missing, ambiguous or unverifiable authorization grants nothing.
3. **The fingerprint will bind authorization state,** so that a revocation or an expiry invalidates pending approvals, as lineage changes do now. A revocation stops future disclosure only; it cannot recall a transmission or export already made.
4. **Receipts** need explicit retention, consent and deletion rules compatible with Forget, and never keep forgotten content.
5. **Preview before authorization**, as Issue #25 requires:
   - **what is affected:** the lineage, successors, dependent claims, newly eligible items and their recipients;
   - **what is uncertain or stays protected,** including what nothing can recall: historical transmissions and exports;
   - **how it is confirmed:** the smallest scope by default, compare-and-set confirmation, and only items visible to the owner;
   - **what is exact and what is inferred,** kept separate.
6. **Classification dimensions** (content category, audience, purpose, duration, provenance, human authority, confidence) are orthogonal, not one severity rank. D15's binary value then becomes the cloud-boundary projection of them.

**Not in D15 V1:** any declassification endpoint, receipt, category, taxonomy, rule engine or model, or storage for any of them.

## 12. Contradictions found and resolved

| # | Contradiction | Resolution |
| --- | --- | --- |
| C1 | Revision 1 required "a deliberate, recorded human act" to lower sensitivity, then recommended an unlinked new note, which is neither recorded nor verifiable | No declassification in V1; unlinked notes are ordinary items and a documented limitation (§10) |
| C2 | "Chains are linear and acyclic (ADR-0003), so the walk terminates" is false for legacy records and for CHECK-disabled claims (G5) | Bounded walk with cycle, self and malformed detection that fails closed (§4.3, §8) |
| C3 | Revision 1 fixed record lineage, but claim evidence still read stored labels (G7) | Evidence uses effective record sensitivity (§4.2, condition 3) |
| C4 | "Reject a correction whose requested sensitivity is lower than its predecessor's" did not say stored or effective, and the API default `private` meant an omitted field silently requested `private` | Compare with the effective value; an omitted field inherits it (§5) |
| C5 | "Imported claims are proposals; approving one is the human decision" conflated authority with disclosure | Keep the file's lineage as a namespaced pointer, which fails closed (§6) |
| C6 | Revision 1's test "a new, unlinked note … is `private` (the declassification path works)" presented a residual as a feature | The test is kept and relabelled as the documented limitation (§15, A4) |
| C7 | "Benchmark numbers unchanged apart from tokens": the benchmark stores no tokens, and its harness reimplements the evidence-only rule in `_policy_reasons` | What changes is the recorded policy version; the harness must call the shared derivation (§14) |
| C8 | ADR-0004 states "Records keep their own immutable sensitivity" and calls the evidence hash a record's "complete eligibility and disclosure state"; both become untrue for disclosure under D15 | Listed as ADR-0004 amendments (§14, step 9). The stored label stays immutable, so ADR-0003 holds |
| C9 | An `unconfirmed` or `mismatch` evidence set could vouch `private` for a predecessor that lost a sensitive link | §4.2, condition 4. This extends the founder-accepted invariant that insufficiently verified evidence is never authoritative: here, it never yields `private` |
| C10 | ADR-0005 D15 named claims only; the founder direction covers records and claims | Both (§4) |
| C11 | D15 was "deferred" in ADR-0005, the Security Gate, the roadmap, the open questions, `ARCHITECTURE.md` §14 and the registry, and only a proposal in the decision register | This PR records the 2026-11-05 direction there; the policy text and the implementation remain pending |
| C12 | Revision 1: "every change of effective sensitivity invalidates pending cloud approvals" ignored ADR-0004's relevance scope | Relevant items and candidates only, which is what protects decisions (§7.3) |

**Flagged, not resolved here:** the status lines of ADR-0003 and ADR-0004 still read "Proposed", although `docs/FOUNDER-DECISIONS.md` records their approval on 2026-10-19. Reconciling them is founder bookkeeping outside this PR.

## 13. Alternatives considered

| Alternative | Assessment |
| --- | --- |
| One predecessor only | Rejected: A → B → C drops A's restriction after two hops |
| A missing predecessor counts as absent (fail open) | Rejected: it makes Forget a declassification route (§9) |
| A stored sensitivity column for claims, or rewriting stored labels | Rejected: a schema change and a second source of truth for a derived value, which goes stale when an ancestor is forgotten |
| A storage trigger that refuses downgraded corrections | Rejected (§5) |
| Tombstones that keep the forgotten item's label, so a private forgotten predecessor need not fail closed | Rejected: it expands tombstones (founder decision 7) and retains metadata about forgotten items |
| Imported claims stay lineage-free | Rejected: it discards a lineage the file states. *Skip imported corrections* is safe but loses data; the namespaced pointer keeps the claim and fails closed (§6) |
| Unbounded walk | Rejected: legacy and CHECK-disabled cycles exist (G5) |
| Fail the whole compile on malformed lineage | Rejected: it would break local use and unrelated items; failing closed per item suffices |
| New exclusion reason codes (`inherited_sensitive_cloud`, …) | Rejected: the decision is the same. A separate basis field explains it without changing ADR-0004's reason precedence |
| Bind every consulted ancestor row into the fingerprint | Rejected: more over-invalidation and no protected decision gained (§7.3) |
| Backward propagation: a stricter label on a correction reclassifies earlier revisions | Not adopted in V1. The founder's definition is forward-only; superseded records are never context evidence and stale claims are never approved memory. Residual R3, with Forget as the mitigation; question Q1 |
| A content-similarity or model classifier | Rejected for V1: a classifier is not a policy. Under D16 stages B–C it can only recommend |
| Keep deferring and forbid cloud use at threshold 3 | Viable, but loses governed cloud reasoning over private data; the founder chose Option C |
| Declassify by writing a new unlinked note (revision 1) | Withdrawn (§10) |

## 14. Implementation plan (a separate Tier 2 PR, after review and founder authorization)

Builder rules: one builder; no concurrent edit of `store.py`, `context.py`, `claims.py` or `app.py` (ROADMAP §H). Synthetic data only.

**Sequence:**

1. **Resolver, test-first.** Add a pure resolver in `context.py`, which owns the rule:
   - the §4.4 reference, plus the memoized form (§8);
   - one evidence-derived-sensitivity function implementing §4.2, conditions 1–4.

   Write the equivalence and unit tests first (§15, A1).
2. **Snapshot.** In `store.context_candidates`:
   - build the record and claim pointer maps from the existing scans;
   - derive the pair for every reported item and every claim source;
   - read predecessor evidence in batches;
   - pass the pairs into both retrieval-state projections and into the facts.
3. **Compiler.** In `context.py`:
   - `RetrievalCandidate.sensitivity` holds the effective value, and `sensitivity_basis` is added;
   - `_candidates`; `build_bundle`'s `blocked` (effective value, new detail text); `_token` entries; `describe`;
   - `POLICY_VERSION = "sovereign.context.v1"`, `ContextPolicy.max_lineage_depth = 1000`, and the module docstring.
4. **Correction.** `Vault.add` checks within its write transaction and raises a fixed-message `ValueError`. `app.py` gets a correction request model whose `sensitivity` is optional; the existing 422 mapping applies.
5. **Library.** `Vault.search` returns `effective_sensitivity` and `sensitivity_basis`.
6. **Ordinary import.** The namespaced predecessor pointer, and the skip on conflict (§6).
7. **UI** (`static/app.js`, `static/index.html`):
   - the correction dialog sends no classification, with its sentence;
   - library and Ask-panel tags show the effective value and mark it inherited;
   - the context preview shows the basis text;
   - the provenance view captions the stored label;
   - the Forget dialog gains its sentence.
8. **Benchmark 0003.**
   - `harness._policy_reasons` calls the shared derivation instead of reading stored labels.
   - Regenerate `results.json` and `report.md`. Predicted change: the policy version string only (§15, row 17). Any other change is explained in `docs/benchmarks/0003-retrieval-evaluation.md`, not assumed away.
9. **Documents:**
   - the ADR-0004 amendment text (sensitivity inheritance, disclosure, fingerprint and token, contract, policy version);
   - the ADR-0003 amendment (correction endpoint, import table);
   - this ADR's status, on ratification;
   - `docs/SECURITY-GATE.md`;
   - `ARCHITECTURE.md` §5 and §14;
   - `docs/architecture/systems-registry.toml`: `code_facts.limits` (`context.POLICY.version` becomes `sovereign.context.v1`, `context.POLICY.max_lineage_depth = 1000` is added; `tests/test_systems_registry.py` enforces both) and the `context-compiler` entry;
   - `ROADMAP.md` §H; `OPEN-QUESTIONS.md`;
   - the D15 residual wording in `OBSIDIAN-PROJECTION.md` §11 and `SECOND-BRAIN-VALIDATION.md` item 34, and the export's default scope there ("sensitive items excluded" then means effectively sensitive).
10. **Tests** (§15): a new `tests/adversarial/test_lineage_sensitivity.py`, and updates elsewhere only where the v1 contract changes a field, each listed in the PR.

**Not changed by the implementation:**

- `claims.py`, `provenance.py`, `providers.py`;
- the schema and triggers (the count stays 44), `SCHEMA_VERSION`, `EXPORT_SCHEMA`;
- Forget, authority and support derivation, and every provider call site.

**Rollback:** revert the PR. Tokens change again (a pending preview gets one 409). No data migration is needed in either direction, because nothing is stored.

## 15. Acceptance matrix (for the implementing PR; nothing here has been executed)

All tests use synthetic data, a recording mock provider, and count calls to `providers.generate`.

| # | Requirement | Proposed test and setup | Expected |
| --- | --- | --- | --- |
| 1 | Sensitive A corrected by B requesting `private` | API: A `sensitive`, `POST …/correct` with `private` | 422 with the fixed message; no row written; A still `active`. Also: omitted → `sensitive`; `sensitive` accepted; `private` → `private` and `private` → `sensitive` accepted |
| 2 | Historical B stored `private`, descended from sensitive A | B inserted by a trigger-respecting raw connection (as a pre-D15 API would have stored it) | B effectively `sensitive`, basis `lineage`; `sensitive_cloud` for cloud; included as evidence locally |
| 3 | A → B → C record chain | A `sensitive`, B and C `private` (raw) | C effectively `sensitive`, basis `lineage`; correcting C with `private` → 422 |
| 4 | Sensitive claim A superseded by B with only private evidence | API supersede, then approve B | B authoritative and `approved_memory` locally; `sensitive_cloud` for cloud, basis `lineage` |
| 5 | A → B → C claim chain | as 4, twice | C restricted |
| 6 | Evidence and lineage combine | Matrix: own or evidence private/sensitive × predecessor private/sensitive/missing; a claim citing a downgraded record successor (G7) | Sensitive iff any input is; basis follows §4.4 precedence |
| 7 | Missing, forgotten or dangling predecessor | (a) Forget A's evidence, so B dangles; (b) `DELETE /api/claims/A`; (c) Forget an older record revision; (d) trusted restore with an absent predecessor; (e) raw insert pointing at a nonexistent id | Effectively `sensitive`, `lineage_unresolved`; stored labels unchanged |
| 8 | Corrupt, cyclic, inconsistent or excessive ancestry | Claim self-supersession with CHECKs off; legacy self, cycle and rho shapes via trusted restore plus a current correction; a non-text pointer (CHECKs off); a predecessor not `superseded`; chains of exactly `L` and `L + 1` | The compile returns; the affected items are `sensitive` / `lineage_unresolved` (exactly `L` resolves normally; a non-superseded predecessor inherits normally); unaffected items unchanged; nothing raised |
| 9 | Untrusted imports and legacy records | File chain `sensitive → private`; file record with an absent predecessor; file claim naming a predecessor; the two conflict cases; existing legacy-ID egress test | Records restricted; claim pointer namespaced, `lineage_unresolved`; conflicts skipped without aborting; legacy records without lineage unchanged |
| 10 | A cloud preview never includes an effectively sensitive item | Seeded random vaults with lineage built through the API and raw SQL; every included item checked against the §4.4 reference | Zero violations |
| 11 | Explicitly pinned effectively sensitive sources cannot leak | Pin B from row 2, cloud | `blocked` / 403 `sensitive_selected`; no provider call. Locally: included |
| 12 | A stale approval is rejected | Preview, then: Forget a record ancestor; Forget a claim ancestor; Forget an ancestor's evidence; a below-cutoff variant on the truncation fixture with identical messages; a token computed with `ContextPolicy(version="sovereign.context.v0")`. Control: an unrelated change | 409 `CHANGED`, no provider call; a fresh preview succeeds. Control: token unchanged |
| 13 | No provider call on a denied or stale request | All 409, 403, 422 and 428 paths above | Zero calls |
| 14 | Local evidence mode unchanged | Local plans with effectively sensitive eligible items; local ask; Benchmark 0003 local outcomes | Included as before; no provider call; outcomes unchanged |
| 15 | Authority and support unchanged | For every claim in the fixtures, `status`, `support`, `integrity` and `authoritative` equal what the unchanged `claims.py` functions give; approve, contest, reject, revalidate and the Forget preview payload are unaffected | Equal |
| 16 | Forget resurrects and preserves nothing | Canary text in A; Forget; scan every table's text, `sqlite_master` (same tables, 44 triggers) and the export | No canary anywhere; B `lineage_unresolved`; no new table or column |
| 17 | Benchmark 0003 regenerated | `python -m evaluation.retrieval`, then `--check` | Diff limited to `policy.version` in `results.json` and `report.md`; anything else is explained. Predicted from a measurement on `3740119`: 3 corrections and 1 supersession, all `private → private`; no dangling predecessor; all 16 claims `committed` |
| 18 | Full suites pass | `pytest -q`, `pytest -q tests/adversarial`, `python -m compileall -q src tests evaluation`, `git diff --check`; both CI jobs on the exact head | Pass |
| A1 | The memoized resolver equals the reference | Seeded random functional graphs for both kinds: cycles, self-loops, forks, missing and non-text pointers, chains of `L − 1`, `L` and `L + 1`, many starts sharing ancestors | Identical (effective, basis) for every item |
| A2 | The basis stays local and content-free | Inspect `outbound`, `messages` and the 422 and 403 texts | No basis code, ancestor id or content in them; fixed texts |
| A3 | Library | `GET /api/memories` | `effective_sensitivity` and `sensitivity_basis` present; `sensitivity` still the stored label |
| A4 | An unlinked note is the documented limitation | A new `private` note restating a sensitive one | Eligible for cloud. The test names this as residual R1, not declassification |
| A5 | Evidence-set integrity | An `unconfirmed` predecessor (schema 4 fixture, migrated) and a `committed` one | Successor `sensitive` / `lineage` (the predecessor counts as evidence-sensitive); normal for `committed` |
| A6 | Raw-SQL correction | Raw insert of a `private` correction under a `sensitive` predecessor, bypassing the API | Effectively `sensitive`; trigger count still 44 |
| P1 | No SQL per lineage step | A vault with 1,000 relevant records in one chain, against 1,000 relevant records without lineage; count statements with `set_trace_callback` | Equal statement counts |
| P2 | Shared ancestors are read once | 50 relevant claims sharing a 300-claim ancestor chain | Each ancestor's links read once (`claim_sources` statements ≤ ⌈ancestors / batch⌉ + the existing per-candidate reads) |
| P3 | The bound caps the work | A chain of `L + 500`, with an instrumented lookup counter | At most `L + 1` predecessors examined per item; `lineage_unresolved` |
| P4 | The correction check is bounded | Correct a record whose predecessor has `L` ancestors | At most `L + 1` lookups; correct accept or refuse decision |

## 16. Limitations and residual risks

- **R1 — Semantic restatement outside recorded lineage.** A new note, a new claim citing different evidence, or pasted or edited text is not caught (§10), even an exact copy of a sensitive item's text: the compiler then excludes the sensitive item and may include the private copy. This is the main residual. D16 stage B or C may later recommend, never decide.
- **R2 — Over-restriction.** These stay cloud-ineligible, with no release route until D16:
  - a correction that genuinely removed the sensitive part;
  - the successors of a forgotten older revision or of a forgotten predecessor claim;
  - every successor of a superseded pre-schema-5 claim, which cannot be revalidated because it is terminal;
  - legacy records with anomalous lineage;
  - lineages longer than `L`;
  - an imported correction.
- **R3 — Forward-only.** A stricter label on a correction does not reclassify earlier revisions or claims citing them. A successor of such a claim can restate the earlier revision, as the owner labelled it then. Mitigation: forgetting the earlier revision forgets the claims citing it, and their successors then fail closed. Mislabelling at creation is outside D15.
- **R4 — Untrusted files can strip lineage.** A hand-edited file without `supersedes_id` is external content, like a new note.
- **R5 — Processes that control the vault file** can drop triggers or rewrite labels (ADR-0003, *Not guaranteed*).
- **R6 — No recall.** D15 cannot reverse transmissions or exports already made. Behaviour before D15 was never certified, and only synthetic data has ever been permitted.
- **R7 — Over-invalidation.** The v1 bump invalidates every pending token once, and basis changes invalidate conservatively.
- **R8 — Local explanation.** `lineage_unresolved` tells the local user that an earlier version is missing. The successor's `supersedes_id` already shows this locally, and nothing leaves the device.
- **R9 — Future exports.** When SB-2b is built, the Obsidian export scope must use effective sensitivity; this is not yet specified there (§14, step 9).
- **R10 — No authentication** (unchanged): any local client can create, correct and approve.
- **R11 — Cost.** A compile stays O(vault), as ADR-0004 states; D15 adds linear work, not a new complexity class.

## 17. Questions for review

Decisions this revision makes that the independent reviewer should test hardest. Q1 is a genuine policy judgment for the founder.

- **Q1 — Forward-only propagation.** Should a stricter label on a correction propagate to dependants of earlier revisions? Recommended: no in V1, which matches the founder's definition; residual R3 has a Forget mitigation.
- **Q2 — The value of `L`.** 1,000 (§8).
- **Q3 — Import pointer or skip** (§6).
- **Q4 — Integrity as a sensitivity input** (§4.2, condition 4), and its permanent over-restriction for successors of superseded pre-schema-5 claims.
- **Q5 — Omitted classification on correction inherits** rather than being required (§5).

## 18. Evidence for this revision

- **Read:**
  - the root and project `AGENTS.md` and `CLAUDE.md`, `ARCHITECTURE.md`, `ROADMAP.md`;
  - `docs/DEVELOPMENT.md`, `docs/SECURITY-GATE.md`, `docs/FOUNDER-DECISIONS.md`;
  - ADR-0003 to ADR-0006 and revision 1 of this ADR;
  - PR #13 and its founder comments; Issue #25;
  - `context.py`, `store.py`, `claims.py`, `app.py`, `provenance.py`, `static/app.js`;
  - the compiler, claims and storage adversarial tests;
  - Benchmark 0003 and its harness.
- **Run on `main` at `3740119`** (Python 3.13, SQLite from the standard library):
  - the full suite: 787 passed;
  - the gap reproduction (G1–G6), with synthetic data and no provider call. G7 follows from reading `inherited_sensitivity` and matters once record lineage is enforced;
  - a measurement of Benchmark 0003's corpus lineage (§15, row 17).
- **Not run:** no implementation exists, so no acceptance test in §15 has run and no runtime behaviour is claimed. This is a documentation-only change.

## Revision notes

- **Revision 2 (2026-11-05).**
  - Rewritten against `main` at `3740119`, after the founder approved the direction (Option C) on 2026-11-05.
  - Adds:
    - the founder decisions of 2026-11-05 (§2), covering records and claims together;
    - G5, G7 and the claim side of G6;
    - the normative reference definition, the bound and the basis codes;
    - effective evidence sensitivity and the evidence-set integrity condition;
    - the correction-request semantics and the import rule;
    - the snapshot, fingerprint and token specification;
    - the complexity bounds;
    - the separation of content, provenance, rationale and authorization;
    - the D16 deferral (Issue #25);
    - the contradictions table, the implementation plan, the acceptance matrix, and the residuals and questions.
  - Withdraws revision 1's "declassify by writing a new unlinked note" recommendation and its founder questions, which the 2026-11-05 decisions answer.
- **Revision 1 (2026-10-22, `bc9a924`).** The first proposal, against `eeed753`: transitive, fail-closed lineage over claim supersession and record correction; correction-endpoint refusal; `v0` → `v1`.
