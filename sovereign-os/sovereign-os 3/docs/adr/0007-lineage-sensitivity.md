# ADR-0007 — Lineage sensitivity: correction and supersession never make content cloud-eligible (D15)

- **Status:** **PROPOSED — revision 2 (2026-11-05), amended 2026-11-07** after the independent Codex Tier 2 policy review of `8f7576c` (CHANGES REQUIRED: F-1 and F-2 at P2, F-3 and F-4 at P3) and its delta review of `6f47380` (CHANGES REQUIRED: F-5 at P2). Dispositions are in §19. The founder approved the **policy direction** on 2026-11-05: D15 *Option C*, full transitive, fail-closed sensitivity inheritance across source records and MemoryClaims ([founder decision comment on PR #13](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/pull/13#issuecomment-6672042826)). The detailed policy in this document and its implementation are **pending independent Tier 2 policy review and the founder's ratification and merge authorization**; this document does not ratify itself. **Nothing is implemented.** Current behaviour is ADR-0004's and is not certified safe for real private data. The Security Gate remains **NOT PASSED**.
- **Date:** 2026-10-22 (revision 1, `bc9a924`); 2026-11-05 (revision 2, against `main` at `3740119`, head `8f7576c`); amended 2026-11-07
- **Decision owner:** Human project owner
- **Review tier:** Tier 2 (cloud-disclosure policy and write validation). The implementation is a separate Tier 2 PR (§14).
- **Resolves:** [ADR-0005](0005-governed-second-brain-architecture.md) D15, deferred on 2026-10-21 (§15.1 there).
- **Amends, on acceptance:** [ADR-0004](0004-governed-retrieval-context-compiler.md) (*Sensitivity inheritance*, *Disclosure*, *Exact-plan approval*, the bundle contract, `policy_version`) and [ADR-0003](0003-memory-claim-authority.md) (the record-correction endpoint; ordinary import of claim lineage). This PR edits neither; the amendment text lands with the implementation (§14).
- **Defers:** D16, governed declassification, to [Issue #25](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/issues/25). It is a future direction, not an authorization (§11).
- **Required before:** usage threshold 3 (`docs/SECURITY-GATE.md`). Not required for synthetic or threshold-2 use.

## Summary

Today a source record's cloud eligibility follows its own stored label, and a MemoryClaim's follows its current evidence (ADR-0004). So correction and supersession can make restated sensitive content cloud-eligible without any decision that says so.

This ADR defines one **effective sensitivity**. It is derived at read time from canonical state, in the compiler's single snapshot, and it is the only value the cloud boundary uses. An item is effectively `private` only if its own label (record) or its evidence (claim) is private **and** every item it corrects or supersedes, transitively, can be resolved and is private. A predecessor that is missing, cyclic, malformed or beyond a fixed bound fails closed. A record that is still `active` although another record already names it as its predecessor is restricted too, and so is every record and claim that descends from it (§4.6, a recommended refinement pending the founder's ratification).

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
| Fingerprint | `store._record_retrieval_state`, `store._claim_retrieval_state` | records: stored label and evidence hash; claims: evidence-derived sensitivity, and each source's state, stored label and pinned hash. A claim's evidence-set integrity is not included (G8) |
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
- **G8 — the fingerprint omits evidence-set integrity (review F-1; pre-existing on `main` since ADR-0006).**
  - **How it arises.** An approved claim below the claim cutoff can move from integrity `unconfirmed` to `mismatch`: a raw connection inserts a commitment with the right link count and a wrong digest, which the write-once trigger accepts.
  - **What changes.** Its exclusion reason as a candidate would change from `revalidation_required` to `evidence_set_mismatch`. Its status, support, authority and every fingerprinted field stay the same.
  - **Reproduced** on `3740119` with 56 matching claims: the token did not change, the old cloud token was accepted, and the provider was called.
  - **Why revision 2 missed it.** Its projection adds only the sensitivity pair, which is (`sensitive`, `evidence`) in both states, so the gap would have remained.
- **G9 — two active revisions (review F-2).**
  - **The history.** Legacy record A (`private`, `active`, no predecessor) and legacy record B (`sensitive`, `active`, `supersedes_id = A`) both stay `active`, because a legacy correction does not supersede its predecessor. A committed, approved claim citing A stays supported and authoritative.
  - **Reproduced** on `3740119`: A and the claim enter a cloud plan today.
  - **Why revision 2 missed it.** Its forward-only rule keeps A and the claim cloud-private, because A has no predecessor. §4.6 closes this.

Revision 1 named G1–G4 and part of G6. G5, G7 and the claim side of G6 are new in revision 2. G8 and G9 were found by the independent review of revision 2 (§19). Benchmark 0003's corpus contains none of these patterns (§15, row 17).

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

**2026-11-07 — pending ratification, not approved authority.**

- **Proposed by the founder,** in response to the independent review:
  - keep forward-only inheritance for internally consistent correction histories (accepted residual R3);
  - add one exceptional, disclosure-only consistency check for an `active` record that already has a stored correction (§4.6). After the delta review (F-5), that restriction propagates forward to every descendant, like any other predecessor restriction.
- **Ratification.** The founder will ratify the precise rule after reviewing this amendment.
- **The review's view, as the founder relayed it.** It accepted the core architecture, the transitive fail-closed resolver, the 1,000-predecessor bound, the evidence-commitment rule and the namespaced import pointer, subject to F-1 to F-4. The delta review of `6f47380` accepted F-1, F-3 and F-4 and the resolution of F-2's original example, and found F-5.

## 3. Terms

- **Stored label:** `records.sensitivity` as written. It is immutable and remains a property of the historical record. Claims have no stored label.
- **Effective sensitivity:** `private` or `sensitive`, derived at read time. It is the only value the cloud boundary uses, and it is never stored.
- **Predecessor:** the item an item's `supersedes_id` names, looked up **in the same kind only**: a record's among `records`, a claim's among `claims`. The two id namespaces are separate, as in SB-2a.
- **Lineage:** the predecessors reached by following `supersedes_id`, in order p1, p2, ….
- **Stored correction of a record P:** any other record row in the snapshot whose `supersedes_id` is text equal to P's id. A record that supersedes itself is not its own stored correction; §4.3 handles it.
- **Own-private:**
  - a record whose stored label is exactly the text `private`;
  - a claim whose **evidence-derived sensitivity** (§4.2) is `private`.
  - Anything else counts as sensitive, including NULL, other text and non-text values (positive validation, as today).
- **Bound `L`:** `ContextPolicy.max_lineage_depth = 1000` predecessors (§8).

## 4. Decision: the effective-sensitivity contract

### 4.1 Source records

A record is effectively `private` **iff** all of the following hold:

- it is own-private;
- it is not an `active` record with a stored correction (§4.6, a recommended refinement pending ratification);
- its lineage is resolved (§4.3);
- every record in its lineage is own-private and is not `active` with a stored correction (§4.4, §4.6; review F-5).

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

Status anomalies do not make a lineage unresolved, for example a predecessor that is not `superseded`, or two successors of one predecessor. The predecessor can still be evaluated, and inheritance can only add restriction:

- a walked **record** predecessor that is still `active` is restrictive (§4.4, §4.6), so the item gets `lineage`;
- a walked **claim** predecessor is evaluated by its evidence.

### 4.4 Reference definition and explanation code

This is the normative definition. An implementation must return exactly its result for every item. It may memoize (§8).

```text
own_private(item):
    record: stored label is exactly the text "private"
    claim:  evidence-derived sensitivity is "private"            # §4.2, conditions 1–4

active_with_correction(record r):                                 # §4.6, pending ratification
    r.status is exactly "active" and r has a stored correction (§3)

resolve(x, L):                                                     # x is a record or a claim
    if not own_private(x):
        return "sensitive", ("own" if x is a record else "evidence")
    if x is a record and active_with_correction(x):
        return "sensitive", "active_with_correction"
    visited = {x}; walked = []; ending = "root"; current = x
    while current.supersedes_id is not NULL:
        pointer = current.supersedes_id
        if pointer is not text:            ending = "unresolved"; break      # malformed
        if len(walked) == L:               ending = "unresolved"; break      # bound
        p = the item of x's kind whose id == pointer
        if p is None or p in visited:      ending = "unresolved"; break      # missing, self or cycle
        visited.add(p); walked.append(p); current = p
    def restrictive(p):                                            # review F-5
        return not own_private(p) or (x is a record and active_with_correction(p))
    if any(restrictive(p) for p in walked):      return "sensitive", "lineage"
    if ending == "unresolved":                   return "sensitive", "lineage_unresolved"
    return "private", null
```

`sensitivity_basis` explains an effectively sensitive item, using one of these codes:

| Code | Meaning |
| --- | --- |
| `own` | The record's own stored label is not `private`. |
| `evidence` | The claim's evidence-derived sensitivity is not `private`. |
| `active_with_correction` | The record is `active`, yet another record names it as its predecessor (§4.6). |
| `lineage` | A predecessor it reached is restrictive: not own-private or, for a record, `active_with_correction`. |
| `lineage_unresolved` | Its lineage is missing, malformed, cyclic or beyond `L`, and no reached predecessor is restrictive. |
| `null` | Effectively `private`. |

The precedence is the order of the `return` statements:

1. `own` or `evidence`;
2. `active_with_correction`;
3. `lineage`;
4. `lineage_unresolved`.

So a walk failure never hides a reached restrictive predecessor, and neither hides the item's own label or evidence.

- **Inputs.** The basis is a function of the item, its stored corrections and its own lineage, all read in one snapshot. It does not depend on which other items a request touches.
- **Walked predecessors (review F-5).** A walked predecessor is restrictive if:
  - it is not own-private: for a record its stored label, for a claim its evidence-derived value; or
  - it is a record that is `active_with_correction`.

  `own_private` itself is unchanged.
- **Forward propagation.** The §4.6 restriction therefore propagates forward:
  - to every record whose walk reaches the anomalous record;
  - through §4.2, to every claim citing those records.

  Nothing inherits backwards.
- **Implementation note.** A walked record predecessor always has a stored correction: the item before it in the walk, because the visited check excludes a self-reference. So for walked records, `active_with_correction(p)` reduces to p's status being exactly `active`.
  - This needs no incoming-set lookup and no extra query.
  - It gives identical results. This revision checked that on seeded random graphs (§18), and §15, A1 requires the implementation to check it again.

### 4.5 What does not change

- **Storage.** Stored labels, the schema, the triggers (44), `SCHEMA_VERSION` 5, backup format 3 and the export payload.
- **Authority.** The MemoryClaim lifecycle, support, evidence-set integrity, `claims.is_authoritative` and ADR-0004's authority table.
- **The local boundary.** `sensitive_cloud` applies only to cloud targets. Local bundles may use effectively sensitive eligible items exactly as today.
- **Relevance, ranking, budget and candidate sets.** Lineage only restricts; it never admits, ranks or pins anything. An ancestor is read for its sensitivity only and never becomes a candidate through lineage, so ADR-0004 decision 3 holds.
- **Forget.** The Forget plan, its impact token and its effect are unchanged, and so are tombstones.
- **Provider boundary.** Provider isolation, prompt rendering and request-scoped labels.

### 4.6 Consistency exception: an active record with a stored correction (recommended refinement, pending ratification)

**Status:** recommended by the founder on 2026-11-07 in response to review finding F-2, with the forward propagation that review finding F-5 requires. The founder will ratify the precise rule, propagation included, after independent acceptance; it is not ratified authority.

- **Why.** Forward-only inheritance is safe for a consistent history, because a corrected record is `superseded`: it is never context evidence, and claims citing it are `stale`, never approved memory. A history in which a corrected record is still `active` breaks that premise (G9). The older revision stays usable evidence and its claims stay authoritative, although a stored correction says it was revised.
- **Rule.** A record P is effectively `sensitive`, with basis `active_with_correction`, when both hold in the snapshot:
  1. P's `status` is exactly the text `active`;
  2. P has a stored correction (§3). That correction's status, label, `legacy` value and own effective sensitivity do not matter.

  `own` takes precedence (§4.4).
- **Effect.** P is `active_with_correction`, and the restriction reaches everything that descends from it (review F-5):
  - every record whose walk reaches P is effectively `sensitive`: P's corrections, their corrections, and every branch of a fork. Its basis is `lineage`, unless `own` or `active_with_correction` applies to it first (§4.4);
  - claims citing P, or any of those records, become evidence-sensitive through §4.2, condition 3;
  - the successors of those claims inherit through §4.2.

  Nothing else changes:
  - P's status and stored label, its claims' support and authority, and local retrieval are unchanged. Locally, P is still `evidence`, and a claim citing it can still be `approved_memory`;
  - the restriction flows forward only, along `supersedes_id` from successors back to P. No record or claim is restricted because of something that descends from it, and no reverse traversal is needed. `own_private` itself is unchanged;
  - it is not general backward propagation: a `superseded` predecessor is never reclassified (§16, R3).
- **Where it occurs.**
  - **Legacy (ADR-0002) rows.** Migration and trusted restore preserve two active revisions, and a legacy correction does not supersede its predecessor (`records_correction_supersedes` fires only for `legacy = 0`). A later trusted restore can also add a legacy correction to an existing active legacy record.
  - **CHECK-disabled connections.** Such a connection can write a `legacy` value outside {0, 1}, which no lineage trigger examines, and so add an active correction to a **current** record without superseding it (reproduced on `3740119`, 2026-11-07). The rule therefore never reads the `legacy` flag.
  - **Consistent histories never meet the rule.** A trigger-respecting current correction always supersedes its predecessor in the same insert.
- **Claims: no equivalent rule.** With the schema intact, a claim's successor can be inserted only when its predecessor is already `superseded` (terminal) or absent, and a predecessor cannot be inserted after its successor (`claims_linear_supersession`). Both were refused on `3740119` with CHECK constraints off. A live claim with a successor requires a schema change, which is outside ADR-0003's guarantee.
- **Deterministic and bounded.**
  - **One pass.** The compile builds an incoming-correction set during the existing pass over `SELECT * FROM records`: the ids named by any other row's text `supersedes_id`. This costs O(R) time and memory, and fan-in (many rows naming one predecessor; compare Issue #16) costs nothing extra. Each lookup is O(1).
  - **No reverse traversal.** Only P's direct incoming edges are consulted; successors of successors are never followed.
  - **Outside the compile,** one indexed existence query on `ix_records_supersedes` answers the question for one record. The library listing asks it for each listed record (at most 60). The correction check never needs it for the predecessor itself, because `Vault.add` already refuses to correct a record that has a successor. The predecessor's own lineage is still walked, and an `active` record in that lineage makes the predecessor `lineage` (§5). Walks need no such query: a walked record's stored correction is the item before it (§4.4).
- **Snapshot semantics.** The rule reads the live snapshot only.
  - Forgetting the correction through the API also forgets P, because Forget walks backward.
  - A raw tombstone of the correction alone removes only that row. P then has no stored correction and is judged as an ordinary record.
  - A lower-level status update can mark P `superseded`; the storage trigger permits it because P has a correction (reproduced on `3740119`). That makes the history consistent:
    - P and its descendants are then judged by forward-only inheritance;
    - claims citing P become `stale`;
    - the changed pairs invalidate pending approvals (§7.3).
  - No tombstone is consulted (founder decision 7).
- **Bound into the plan.** The pair (`sensitive`, `active_with_correction`) is P's effective sensitivity and basis. §7.3 therefore binds:
  - P's pair, for every relevant record and candidate;
  - the (`sensitive`, `lineage`) pair of every descendant in the same way;
  - the per-source effective sensitivity of every claim citing P or a descendant.

  A pinned P, or a pinned descendant, blocks a cloud plan (§7.2).

## 5. Write boundary: record correction (amends ADR-0003)

- **Request.** `POST /api/memories/{id}/correct` takes `sensitivity` as optional: `private`, `sensitive`, or omitted. It gets its own request model. `POST /api/memories` (a new, unlinked record) is unchanged.
- **Check.** `Vault.add` computes the predecessor's effective sensitivity (§4.1, bound `L`) inside the correction's existing `BEGIN IMMEDIATE` transaction, before inserting:

  | Requested | Predecessor effectively `private` | Predecessor effectively `sensitive` |
  | --- | --- | --- |
  | omitted | stored `private` | stored `sensitive` |
  | `sensitive` | accepted | accepted |
  | `private` | accepted | **422**, nothing written |

- **Propagation applies.** The predecessor's effective sensitivity is §4.4's, including §4.6 and its forward propagation. Take the two-active example of §15.1, E1: B is `private` and its predecessor A is `active` with B as its correction. Correcting B with `private` is refused, and an omitted classification stores `sensitive`.
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
- **Legacy (ADR-0002) records.** Stored labels and anomalous lineage are preserved exactly, and D15 never reads the `legacy` flag. Each anomaly ADR-0003 lists, and its treatment:
  - **self-supersession, cycles, and dangling or over-long pointers:** effectively sensitive through §4.3 (`lineage_unresolved`, unless a reached predecessor gives `lineage`);
  - **two active revisions in one chain:** the older one is `active_with_correction` (§4.6). The newer one is `lineage` (§4.4), as is every record whose walk reaches the older one;
  - **forks (two corrections of one record):**
    - if the shared record is still `active`, it is `active_with_correction` and every branch is `lineage`, so no private branch escapes;
    - if the shared record is `superseded`, each branch is judged by its own lineage, and a branch that restates a sensitive sibling is **not** caught (§16, R12);
  - **a `superseded` record with no stored correction:** never context evidence (ADR-0004). Claims citing it are `stale`, and it is judged by its own lineage.

  Not every legacy anomaly is harmless; §16 lists the residuals. Legacy records without lineage are unaffected; the legacy-ID egress fixture in `tests/adversarial/test_context_compiler_adversarial.py` has none.
- **Raw SQL and lower-level writers.** §4 evaluates on read every row a connection can write; nothing depends on the API path.
  - Labels and pointers are immutable under the triggers, so a connection can add rows but cannot lower an existing label.
  - An added row's effective sensitivity is never lower than its lineage's.
  - A CHECK-disabled connection can write a `legacy` value outside {0, 1}, which bypasses the record lineage triggers (§4.6). D15 never reads that flag.
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
- **`_claim_retrieval_state`** replaces the evidence-only inherited sensitivity with the effective sensitivity and the basis. It also **adds the claim's evidence-set integrity**, as derived in the snapshot (`committed`, `unconfirmed` or `mismatch`; review F-1, G8). Each source entry gains that record's effective sensitivity.
- **Who participates.** As today:
  - the claim projection covers every lexically matching claim before the cutoff, and every provenance-linked claim before its limit;
  - the record projection covers every matching record before the cutoff.

  Every candidate is in one of those sets, so candidates and below-cutoff items are bound alike.
- **`_token`**:
  - an included entry appends the basis; its `sensitivity` field now holds the effective value;
  - an excluded entry becomes `[id, type, reasons, effective sensitivity, basis]`.
- **Why lineage needs only the derived pair.** Lineage affects policy only through (effective sensitivity, basis). Binding that pair for every relevant item and every candidate therefore binds the policy-relevant state of every predecessor consulted. Binding raw ancestor fields (status, history) would only add over-invalidation.
- **Every independent decision input is bound.** With integrity added, the projections cover every input `_reasons`, the duplicate rule, the budget and the prompt use:

  | Input | Record | Claim |
  | --- | --- | --- |
  | Status | `status` | `status` |
  | Authority | — | `support`, integrity (added), `authoritative` |
  | Sensitivity | effective sensitivity and basis (added) | effective sensitivity and basis (added); each source's state, stored label, effective sensitivity (added) and pinned hash |
  | Relevance and rank | score, `created_at` | score, `created_at` |
  | Content (duplicates, budget, messages) | the evidence hash, which pins content, source, label, time and pointer | the id: claim text is immutable, and a claim id is never reused (ADR-0003 triggers) |

  - **Integrity** was the only independent input missing.
  - **What stays out,** because it changes no decision:
    - decision history and notes;
    - the commitment's `basis` and `at`;
    - claim `origin`;
    - an ancestor's own integrity, which cannot change any pair: both `unconfirmed` and `mismatch` make an ancestor evidence-sensitive;
    - raw ancestor rows.
- **What invalidates.** Any change to a bound input of a relevant item changes the fingerprint or the token: its pair, its integrity, or any other field above.
  - **The refusal.** The old cloud approval is then refused, with no provider call, even when the item is below the cutoff and the messages are identical. The answer is 409 at the token check, or 403 earlier when a pinned record has become effectively sensitive, because `/api/ask` checks `blocked` before the token (§7.4).
  - **Examples**, each only **when it alters a bound input**:
    - a predecessor or its evidence forgotten;
    - a restore or raw-SQL insertion reaching the item's lineage, adding a stored correction to an active record, or marking an `active` corrected record `superseded`. Each of these also changes the pair of every relevant descendant (§4.6);
    - an evidence change, or an evidence-set integrity change;
    - a lineage crossing the bound.
  - **Not every ancestor change does.** Forgetting an ancestor beyond a nearer sensitive predecessor leaves the pair (`sensitive`, `lineage`) unchanged, and the token stays valid if nothing else bound changed.
- **What still does not.** A change that alters no bound input of any relevant item or candidate leaves the token valid, as ADR-0004 requires.
- **Conservative.** The basis is bound, so a change from `lineage` to `lineage_unresolved` invalidates even though the decision is the same (ADR-0004, *Invalidation is conservative*).

### 7.4 Policy version

- `sovereign.context.v0` (verified as the current value) becomes `sovereign.context.v1`. `ContextPolicy.max_lineage_depth = 1000` is part of v1.
- Every pending token, cloud and local, changes once.
- A previewed cloud plan is then refused and must be previewed again: 409 at the token check, or 403 earlier if one of its pins is now blocked.
- The refusal order is `/api/ask`'s existing one:
  1. a pin forgotten since the preview: 409;
  2. no approval: 403;
  3. a blocked plan: 403;
  4. the provider not configured: 503;
  5. no token: 428;
  6. a stale token: 409.
- No v0 token can authorize a v1 plan, because the version is inside the token.

### 7.5 Explanation and content safety

| Basis | Preview text (local only) |
| --- | --- |
| `own` | "sensitive — stays on this device" (the existing label) |
| `evidence` | "cites sensitive or unverifiable evidence — stays on this device" |
| `lineage` | "corrects or supersedes something sensitive — stays on this device" |
| `lineage_unresolved` | "an earlier version is missing or its history cannot be verified — stays on this device" |
| `active_with_correction` | "a later correction exists, but this record is still marked current — stays on this device" |

- **Where it appears.** The codes appear only locally: in the bundle's `included[]` and `excluded[]`, and in the library. They contain no text from any item, never name an ancestor, never say whether a missing predecessor was forgotten (no tombstone is read), and never reach a provider.
- **Library.** `GET /api/memories` adds `effective_sensitivity` and `sensitivity_basis` to each record; its `sensitivity` stays the stored label. The UI tag shows the effective value and marks it as inherited when it differs from the stored label.
- **Provenance view.** SB-2a keeps showing the stored label, captioned as such, because navigation is not disclosure policy (ADR-0005 §8.1). It does not compute effective sensitivity.
- **Forget dialog.** It gains one static sentence: "Later revisions of what you forget, and claims that replaced the claims it removes, stay restricted to this device." The Forget plan, impact token and effect are unchanged.

## 8. Resource bounds and complexity

- **Per-item bound.** No walk visits more than `L` predecessors; one more makes the lineage unresolved (§4.3). The result depends only on the item, its stored corrections and its own lineage (§4.4), so it is deterministic.
- **Compile (`context_candidates`):**
  - **Records.** The existing `SELECT * FROM records` scan already reads every record. The resolver uses an in-memory map built from that scan (id → pointer, stored label, status). The same pass builds the §4.6 incoming-correction set. There is no SQL per lineage step.
  - **Claims.** The existing `SELECT id, text, created_at FROM claims` scan adds `supersedes_id`, which gives an in-memory pointer map. Predecessors that are not already hydrated candidates need their evidence-derived sensitivity. It is read set-oriented, through a **lightweight ancestor projection**:
    - from `claim_sources`: `claim_id`, `record_id` and the pinned `evidence_sha256`;
    - from `claim_evidence_sets`: `claim_id`, `link_count` and `digest`, the integrity inputs;
    - from the record map: each linked record's presence, `status`, stored label, effective sensitivity, and the fields `evidence_hash` covers, which the scan already holds.

    These rows are fetched in batches of ids, a bounded number of statements per batch and never one per lineage step, and `evidence_hash` is computed at most once per record.

    An ancestor is never hydrated through `Vault._claim`. So no ancestor's decision history (`claim_events`), notes (event notes, the commitment's `note`), commitment `basis` or `at`, or claim text is read for classification. The claim text is read by the existing scan, for scoring only.
  - **Memoized.** Each item's result is computed once per compile and shared by every candidate whose lineage reaches it. For example, store per item the distance to its first restrictive predecessor and how and where its walk ends, capped at `L + 1`. A predecessor is restrictive if it is not own-private, or if it is a record whose status is `active` (§4.4). Resolve cycle members by one bounded walk. The restrictive test reads only the predecessor's own row from the scan, so memoization needs no extra state.
  - **Cost of the resolver.** Given the batched hydration and memoization above, the work D15 adds is O(R + C + links), for R records, C claims and their links in the snapshot. Its memory is O(R + C) identifiers and pointers.
  - **Not the compiler's total cost.** A compile also does, as today:
    - tokenize every record and claim text, in proportion to the bytes stored;
    - sort the matches, O(n log n);
    - hydrate each matching or linked claim with `Vault._claim`, which reads its complete decision history;
    - carry any oversized stored metadata.

    D15 neither introduces nor removes a bound on those. Issues #14 (unbounded claim histories) and #17 (unbounded timestamps and legacy metadata) remain separate availability work and are not redesigned here.
  - **Iterative.** Walks are iterative, so no recursion limit applies.
- **Correction check.** At most `L + 1` primary-key lookups in the write transaction, each reading the id, pointer, label and status; one recursive CTE with a depth limit may fetch the same rows in one statement. Either way, SQL only fetches rows: the decision is made by the same resolver function as the compile (§14, step 1).
- **Library listing.** A batched walk for the listed records (at most 60): at most `L + 1` batched queries, or one lightweight scan of `(id, supersedes_id, sensitivity)`. Status is read with each row, so propagation adds nothing. One indexed existence query per listed record answers §4.6 for the listed record itself. SQL only fetches rows; the same resolver decides.
- **Failure mode.** Exceeding the bound or meeting malformed state never raises and never returns partial results. Every other item is unaffected.
  - The affected item is effectively sensitive. Its basis follows §4.4's precedence:
    - `own`, `evidence` or `active_with_correction` when the item itself is restricted;
    - `lineage` when a reached predecessor is restrictive (§4.4);
    - `lineage_unresolved` only otherwise.
  - A row SQLite cannot decode already makes the compile fail before any provider call (unchanged; Issue #15). D15 adds no new decoding path.
- **Why `L = 1000`.**
  - It is two orders of magnitude above the longest lineage in any fixture (14, in `test_long_lineages_restore_in_any_payload_order`) or in the benchmark (2).
  - It keeps the write-time check to at most 1,001 indexed lookups.
  - A longer lineage is unusual enough to restrict, and the preview says why.
  - Changing `L` is a policy-version change.
- **Measurement.** Performance acceptance counts SQL statements and lookups, never wall-clock time (§15, P1–P5). Benchmark 0003 makes no timing claims either.

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
| C13 | Review F-2: the forward-only rationale (§13; §16, R3) assumed a corrected record is `superseded`, but legacy and CHECK-disabled histories can keep it `active` and usable as evidence (G9) | §4.6, a disclosure-only consistency exception (recommended, pending ratification). Forward-only is kept for consistent histories |
| C14 | Review F-1: §7.3 treated the sensitivity pair as completing the claim projection, but evidence-set integrity is an independent decision input the fingerprint never carried (G8, pre-existing since ADR-0006) | Integrity is bound, and every independent input is enumerated (§7.3) |
| C15 | Review F-4: §8 and §15 expected `lineage_unresolved` and 409 where §4.4's precedence or `/api/ask`'s order gives `own`, `evidence`, `lineage` or 403 | §8 and §15 aligned with §4.4 and with the real execution order (§7.4) |
| C16 | Review F-3: §8 presented O(R + C + links) as the compile's total cost | Stated as the resolver's added cost only; the ancestor projection is specified (§8) |
| C17 | Review F-5: §4.4 and §4.6 evaluated `active_with_correction` only for the item being resolved, and stated that it never applied to walked predecessors. A correction of an anomalous record, a claim citing it, or a private fork branch therefore stayed `private`, contradicting transitive inheritance | A walked record that is `active_with_correction` is restrictive (§4.4), and the restriction propagates forward to every descendant (§4.6). Reproduced against `6f47380` and corrected; the statement that the check never applies to walked predecessors is withdrawn |

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
| General backward propagation: a stricter label on a correction reclassifies earlier revisions | Not adopted. The founder's definition is forward-only, and in a consistent history the earlier revision is `superseded`: never context evidence, with only `stale` claims. Accepted as residual R3. The one inconsistent case, an `active` earlier revision, is §4.6 |
| Restrict only the anomalous record, not its descendants (the first 2026-11-07 amendment) | Withdrawn after review F-5. A correction of an anomalous record can restate it, so it and its dependants would stay `private`. Descendants inherit the restriction (§4.6) |
| Restrict only when the correction is sensitive | Not adopted. Conditioning on the correction's label would leave an inconsistent history usable whenever the correction is private |
| A content-similarity or model classifier | Rejected for V1: a classifier is not a policy. Under D16 stages B–C it can only recommend |
| Keep deferring and forbid cloud use at threshold 3 | Viable, but loses governed cloud reasoning over private data; the founder chose Option C |
| Declassify by writing a new unlinked note (revision 1) | Withdrawn (§10) |

## 14. Implementation plan (a separate Tier 2 PR, after review and founder authorization)

Builder rules: one builder; no concurrent edit of `store.py`, `context.py`, `claims.py` or `app.py` (ROADMAP §H). Synthetic data only.

**Sequence:**

1. **Resolver, test-first.** Add a pure resolver in `context.py`, which owns the rule:
   - the §4.4 reference, plus the memoized form (§8);
   - one evidence-derived-sensitivity function implementing §4.2, conditions 1–4;
   - **one resolver for every path:** the compiler's candidates and fingerprints, the library listing and the correction check. SQL only fetches the bounded rows each path needs: in-memory maps for the compile, primary-key and indexed lookups otherwise. No path may implement its own, weaker semantics; §15, A1 runs all three paths against the reference.

   Write the equivalence and unit tests first (§15, A1).
2. **Snapshot.** In `store.context_candidates`:
   - build the record and claim pointer maps, and the §4.6 incoming-correction set, from the existing scans;
   - derive the pair for every reported item and every claim source;
   - read predecessor evidence in batches;
   - pass the pairs, and each claim's evidence-set integrity (§7.3), into both retrieval-state projections and into the facts.
3. **Compiler.** In `context.py`:
   - `RetrievalCandidate.sensitivity` holds the effective value, and `sensitivity_basis` is added;
   - `_candidates`; `build_bundle`'s `blocked` (effective value, new detail text); `_token` entries; `describe`;
   - `POLICY_VERSION = "sovereign.context.v1"`, `ContextPolicy.max_lineage_depth = 1000`, and the module docstring.
4. **Correction.** `Vault.add` checks within its write transaction and raises a fixed-message `ValueError`. `app.py` gets a correction request model whose `sensitivity` is optional; the existing 422 mapping applies.
5. **Library.** `Vault.search` returns `effective_sensitivity` and `sensitivity_basis`, §4.6 included.
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

All tests use synthetic data, a recording mock provider, and count calls to `providers.generate`. An *all-own-private* fixture is one in which the item is own-private and not `active_with_correction`, and no predecessor its walk reaches is restrictive (§4.4). Only such fixtures can assert `lineage_unresolved`.

| # | Requirement | Proposed test and setup | Expected |
| --- | --- | --- | --- |
| 1 | Sensitive A corrected by B requesting `private` | API: A `sensitive`, `POST …/correct` with `private` | 422 with the fixed message; no row written; A still `active`. Also: omitted → `sensitive`; `sensitive` accepted; `private` → `private` and `private` → `sensitive` accepted |
| 2 | Historical B stored `private`, descended from sensitive A | B inserted by a trigger-respecting raw connection (as a pre-D15 API would have stored it) | B effectively `sensitive`, basis `lineage`; `sensitive_cloud` for cloud; included as evidence locally |
| 3 | A → B → C record chain | A `sensitive`, B and C `private` (raw) | C effectively `sensitive`, basis `lineage`; correcting C with `private` → 422 |
| 4 | Sensitive claim A superseded by B with only private evidence | API supersede, then approve B | B authoritative and `approved_memory` locally; `sensitive_cloud` for cloud, basis `lineage` |
| 5 | A → B → C claim chain | as 4, twice | C restricted |
| 6 | Evidence and lineage combine | Matrix: own or evidence private/sensitive × predecessor private/sensitive/missing; a claim citing a downgraded record successor (G7) | Sensitive iff any input is; basis follows §4.4 precedence |
| 7 | Missing, forgotten or dangling predecessor | All-own-private fixtures (defined above): (a) Forget A's evidence, so B dangles; (b) `DELETE /api/claims/A`; (c) Forget an older record revision; (d) trusted restore with an absent predecessor; (e) raw insert pointing at a nonexistent id. Companion fixtures: a sensitive predecessor reached before the gap; the item itself not own-private | All-own-private: `sensitive` / `lineage_unresolved`. Companions: `lineage`; `own` or `evidence` (§4.4 precedence). Stored labels unchanged |
| 8 | Corrupt, cyclic, inconsistent or excessive ancestry | Claim self-supersession with CHECKs off; legacy self, cycle and rho shapes via trusted restore plus a current correction; a non-text pointer (CHECKs off); a predecessor not `superseded`; chains of exactly `L` and `L + 1`. Each with all-own-private members, and again with one sensitive member | The compile returns and nothing is raised. All-own-private: the affected items are `sensitive` / `lineage_unresolved`. With a sensitive member reached: `lineage`. Exactly `L` resolves normally. With a non-superseded predecessor: a claim inherits normally; for a record, an `active` predecessor is itself `active_with_correction` and makes the item `lineage` (§4.4). Unaffected items unchanged |
| 9 | Untrusted imports and legacy records | File chain `sensitive → private`; file record with an absent predecessor; file claim naming a predecessor; the two conflict cases; existing legacy-ID egress test | Records restricted; claim pointer namespaced, `lineage_unresolved`; conflicts skipped without aborting; legacy records without lineage unchanged |
| 10 | A cloud preview never includes an effectively sensitive item | Seeded random vaults with lineage built through the API and raw SQL; every included item checked against the §4.4 reference | Zero violations |
| 11 | Explicitly pinned effectively sensitive sources cannot leak | Pin B from row 2, cloud | `blocked` / 403 `sensitive_selected`; no provider call. Locally: included |
| 12 | A stale approval is rejected | Preview, then make a change that **alters a bound input** of a relevant item, using all-own-private fixtures whose pair turns from (`private`, null) to (`sensitive`, `lineage_unresolved`): Forget an irrelevant record ancestor; Forget an irrelevant claim ancestor; Forget an ancestor's evidence; a below-cutoff variant on the truncation fixture with identical messages; a token computed with `ContextPolicy(version="sovereign.context.v0")`. Pinned variant: a pinned record becomes effectively sensitive. Controls: an unrelated change; Forget of an irrelevant ancestor beyond a nearer sensitive predecessor, so the pair stays (`sensitive`, `lineage`) | Unpinned: 409 `CHANGED`. Pinned: 403 `sensitive_selected`, because `/api/ask` checks `blocked` before the token (§7.4). No provider call in either case. A fresh preview succeeds, and is blocked in the pinned case. Controls: token unchanged |
| 13 | No provider call on a denied or stale request | All 409, 403, 422, 428 and 503 paths above, in `/api/ask`'s order (§7.4) | Zero calls |
| 14 | Local evidence mode unchanged | Local plans with effectively sensitive eligible items; local ask; Benchmark 0003 local outcomes | Included as before; no provider call; outcomes unchanged |
| 15 | Authority and support unchanged | For every claim in the fixtures, `status`, `support`, `integrity` and `authoritative` equal what the unchanged `claims.py` functions give; approve, contest, reject, revalidate and the Forget preview payload are unaffected | Equal |
| 16 | Forget resurrects and preserves nothing | Canary text in A; Forget; scan every table's text, `sqlite_master` (same tables, 44 triggers) and the export | No canary anywhere; B (own-private) `lineage_unresolved`; no new table or column |
| 17 | Benchmark 0003 regenerated | `python -m evaluation.retrieval`, then `--check` | Diff limited to `policy.version` in `results.json` and `report.md`; anything else is explained. Predicted from a measurement on `3740119`: 3 corrections and 1 supersession, all `private → private`; no dangling predecessor; all 16 claims `committed` |
| 18 | Full suites pass | `pytest -q`, `pytest -q tests/adversarial`, `python -m compileall -q src tests evaluation`, `git diff --check`; both CI jobs on the exact head | Pass |
| A1 | The memoized resolver equals the reference, on every access path | Seeded random functional graphs for both kinds: cycles, self-loops, forks, missing and non-text pointers, chains of `L − 1`, `L` and `L + 1`, many starts sharing ancestors, `active` and `superseded` predecessors, random row insertion and resolution orders. Each graph is resolved through the compile's in-memory path, the library listing and the correction check's lookups | Identical (effective, basis) for every item, path and order. The walk-local status test equals the normative `active_with_correction(p)` |
| A2 | The basis stays local and content-free | Inspect `outbound`, `messages` and the 422 and 403 texts | No basis code, ancestor id or content in them; fixed texts |
| A3 | Library | `GET /api/memories` | `effective_sensitivity` and `sensitivity_basis` present; `sensitivity` still the stored label |
| A4 | An unlinked note is the documented limitation | A new `private` note restating a sensitive one | Eligible for cloud. The test names this as residual R1, not declassification |
| A5 | Evidence-set integrity | An `unconfirmed` predecessor (schema 4 fixture, migrated) and a `committed` one | Successor `sensitive` / `lineage` (the predecessor counts as evidence-sensitive); normal for `committed` |
| A6 | Raw-SQL correction | Raw insert of a `private` correction under a `sensitive` predecessor, bypassing the API | Effectively `sensitive`; trigger count still 44 |
| A7 | Evidence-set integrity is bound below the cutoff (review F-1) | More than 50 matching claims. An approved claim below the claim cutoff (restored from a format-2 backup, so `unconfirmed`) gains a commitment with the right link count and a wrong digest, and becomes `mismatch`. Its status, support, authority and pair (`sensitive`, `evidence`) stay identical, and so do the top candidates and the messages. Variant: a provenance-linked claim beyond the linked limit | The fingerprint changes. The old cloud token gets 409 `CHANGED`, with no provider call, and a fresh preview succeeds. Same for the variant |
| A8 | Two active revisions (review F-2) | Trusted restore of legacy A (`private`, `active`, no predecessor) and legacy B (`sensitive`, `active`, `supersedes_id = A`). A committed, approved claim X cites A; a successor of X cites private evidence. Variants: B `private`; a later trusted restore adds B to an existing A; a CHECK-disabled connection adds an active `legacy = 2` correction to a current record | A: `sensitive` / `active_with_correction`. X: `sensitive` / `evidence`. X's successor: `sensitive` / `lineage`. B: `sensitive` / `own` (its own label). In the variant where B is `private`: `sensitive` / `lineage` (review F-5). Status, support, authority and local inclusion unchanged. Cloud: A and X excluded `sensitive_cloud`; pinning A gives 403; zero provider calls. A preview taken before B arrives gets 409 afterwards |
| A9 | Consistent histories never meet §4.6 | API corrections of current records (chains of 1, 2 and 15); a trusted restore of the same; a consistent legacy chain whose predecessors are `superseded` | No item has basis `active_with_correction`, and no `lineage` result comes from an `active` predecessor. Effective sensitivities equal the forward-only result |
| P1 | No SQL per lineage step | A vault with 1,000 relevant records in one chain, against 1,000 relevant records without lineage; count statements with `set_trace_callback` | Equal statement counts |
| P2 | Shared ancestors are read once | 50 relevant claims sharing a 300-claim ancestor chain | Each ancestor's links read once (`claim_sources` statements ≤ ⌈ancestors / batch⌉ + the existing per-candidate reads) |
| P3 | The bound caps the work | An all-own-private chain of `L + 500`, with an instrumented lookup counter | At most `L + 1` predecessors examined per item; `lineage_unresolved` |
| P4 | The correction check is bounded | Correct a record whose predecessor has `L` ancestors | At most `L + 1` lookups; correct accept or refuse decision |
| P5 | §4.6 costs O(R) | 1,000 legacy records naming one active predecessor (fan-in), against 1,000 records without lineage | Equal SQL statement counts; the predecessor is `active_with_correction` |

### 15.1 Propagation scenarios (review F-5)

- **How the fixtures are built.** Legacy rows come from a trusted restore of `legacy: 1` records; current rows come from the API.
- **What every scenario checks.** Each uses a recording mock provider and counts calls to `providers.generate`.
- **Notation.** Pairs are (effective sensitivity, basis).
- **Status codes** follow `/api/ask`'s order (§7.4).

| # | Scenario | Setup | Expected |
| --- | --- | --- | --- |
| E1 | Two active private revisions | Legacy A (`private`, `active`, no predecessor); legacy B (`private`, `active`, `supersedes_id = A`) | A: (`sensitive`, `active_with_correction`). B: (`sensitive`, `lineage`). Both stay `active`; stored labels unchanged. Correcting B with `private` → 422; omitted → stored `sensitive` |
| E2 | A claim citing B | E1, plus a claim X citing B, created and approved through the API (`committed`, `supported`, authoritative) | X: (`sensitive`, `evidence`). X stays `approved_memory` locally. Cloud: `sensitive_cloud`, zero provider calls |
| E3 | Multi-hop descendants | E1, then current corrections C of B and D of C through the API (B becomes `superseded`) | B, C and D: (`sensitive`, `lineage`). Correcting D with `private` → 422; omitted → stored `sensitive` |
| E4 | Malformed fork | Legacy A (`private`, `active`); legacy S1 (`sensitive`, `active`, supersedes A); legacy S2 (`private`, `active`, supersedes A); an approved claim Y citing S2 | A: `active_with_correction`; S1: `own`; S2: `lineage`; Y: `evidence`. No branch and no claim is cloud-eligible |
| E5 | Consistent correction chain | API chain A → B → C, all `private` (A and B `superseded`); an approved claim citing C | All (`private`, null), included in cloud plans exactly as under forward-only inheritance |
| E6 | Sensitive correction of a correctly superseded private predecessor | A (`private`) corrected through the API by B (`sensitive`); a claim made on A before the correction | A: (`private`, null), not reclassified. B: (`sensitive`, `own`). The claim on A is `stale`, never approved memory |
| E7 | Imported and legacy variants | (a) E1–E6 rebuilt by trusted restore of a backup, in file order, reversed and shuffled. (b) An ordinary import of a file holding E1's shape. (c) E1 with B written as `legacy = 2` by a CHECK-disabled connection against a current A | (a) Identical pairs in every order. (b) The file is refused whole (422, "An item with a successor in the import must be superseded"), as today; nothing is imported. (c) The same pairs as E1 |
| E8 | Claims citing an anomalous ancestor directly and indirectly | E1 and E3, plus approved claims X1 citing A (direct), X2 citing B and X3 citing D (descendants); then X1 superseded by Z citing only unrelated private evidence | X1, X2, X3: (`sensitive`, `evidence`). Z: (`sensitive`, `lineage`). Authority and support unchanged; none is in a cloud plan |
| E9 | Fingerprint binding, below the cutoff | More than 50 relevant records and claims; the changed items lie below their cutoffs; top candidates and messages identical. Preview a cloud plan, then: (a) a later trusted restore adds a legacy correction to an `active` legacy record that a relevant claim cites; (b) a raw status update marks E1's A `superseded`, so B (`sensitive`, `lineage`) becomes (`private`, null); (c) as (a) with that record pinned | (a), (b): the fingerprint changes; the old cloud token gets 409 `CHANGED`; zero provider calls; a fresh preview succeeds. (c): 403 `sensitive_selected`, before the token check; zero provider calls |
| E10 | No provider call on a denied or invalidated plan | Every refusal in E1–E9, plus the 403 (no approval), 428 and 503 paths | Zero calls; every refusal is content-free |
| E11 | Local use and canonical authority unchanged | E1–E8 compiled for the local target; approve, contest and reject on X, X1 and X2; the Forget preview of A | Local plans include the same items as before D15. `status`, `support`, `integrity` and `authoritative` equal the unchanged `claims.py` values. The Forget preview payload and impact token are unchanged |
| E12 | Independence of order, and complexity | E1–E8 built in several row orders (trusted restore applies legacy rows in file order) and resolved in random order; a vault with 1,000 relevant current descendants of one `active` corrected legacy record | Identical pairs in every build and order. Statement counts equal those of the same vault without the anomaly (as in P1 and P5); each predecessor's restrictive test reads only its own row |

## 16. Limitations and residual risks

- **R1 — Semantic restatement outside recorded lineage.** A new note, a new claim citing different evidence, or pasted or edited text is not caught (§10), even an exact copy of a sensitive item's text: the compiler then excludes the sensitive item and may include the private copy. This is the main residual. D16 stage B or C may later recommend, never decide.
- **R2 — Over-restriction.** These stay cloud-ineligible, with no release route until D16:
  - a correction that genuinely removed the sensitive part;
  - the successors of a forgotten older revision or of a forgotten predecessor claim;
  - every successor of a superseded pre-schema-5 claim, which cannot be revalidated because it is terminal;
  - legacy records with anomalous lineage;
  - lineages longer than `L`;
  - an `active` record with a stored correction, even a private correction, and every record and claim descending from it (§4.6);
  - an imported correction.
- **R3 — Forward-only (accepted residual).**
  - **Not covered.** In a consistent history, a normal newer sensitive correction does not retroactively reclassify the already superseded predecessor, the `stale` claims citing it, or those claims' successors. D15 also performs no semantic restatement detection. So a successor of such a claim can restate the earlier revision as the owner labelled it then.
  - **Mitigation.** Forgetting the earlier revision forgets the claims citing it, and their successors then fail closed.
  - **Out of scope.** Mislabelling at creation is outside D15.
  - **Covered elsewhere.** The inconsistent case, an earlier revision that is still `active`, is §4.6.
- **R4 — Untrusted files can strip lineage.** A hand-edited file without `supersedes_id` is external content, like a new note.
- **R5 — Processes that control the vault file** can drop triggers or rewrite labels (ADR-0003, *Not guaranteed*).
- **R6 — No recall.** D15 cannot reverse transmissions or exports already made. Behaviour before D15 was never certified, and only synthetic data has ever been permitted.
- **R7 — Over-invalidation.** The v1 bump invalidates every pending token once, and basis changes invalidate conservatively.
- **R8 — Local explanation.** `lineage_unresolved` tells the local user that an earlier version is missing. The successor's `supersedes_id` already shows this locally, and nothing leaves the device.
- **R9 — Future exports.** When SB-2b is built, the Obsidian export scope must use effective sensitivity; this is not yet specified there (§14, step 9).
- **R10 — No authentication** (unchanged): any local client can create, correct and approve.
- **R11 — Cost.** A compile stays O(vault), as ADR-0004 states. D15 adds linear work, not a new complexity class; §8 separates that from the compile's other costs.
- **R12 — Legacy anomalies are not all harmless.**
  - When a fork's shared record is `superseded`, a branch can restate a sensitive sibling and is still judged by its own lineage. (When the shared record is still `active`, every branch is restricted: §4.6.)
  - §4.6 reads the live snapshot. So a raw tombstone of a correction alone leaves its predecessor an ordinary record again; the API's Forget also removes the predecessor. Likewise, a raw status update that marks the predecessor `superseded` returns it and its descendants to forward-only inheritance.
  - Any anomaly that needs a schema change is outside ADR-0003's guarantee, although §4.3 still makes the resolver terminate on it.

## 17. Questions for review

Decisions this revision makes that the independent reviewer should test hardest. Q1 is a genuine policy judgment for the founder.

- **Q1 — Ratify the §4.6 exception.** The founder's ratification would cover forward-only inheritance for consistent histories (accepted residual R3), together with §4.6's exact rule:
  - an `active` record named by another record's text `supersedes_id` is effectively sensitive, whatever that correction's label, status or `legacy` value;
  - its restriction propagates forward to every descendant record and to the claims citing them (review F-5), with no backward inheritance;
  - it applies to records only;
  - it changes no status, support, authority or local retrieval.
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
- **Run on 2026-11-07, on `8f7576c`** (code identical to `3740119`):
  - reproductions of review findings F-1 (G8) and F-2 (G9), and of the two reachability facts in §4.6, with synthetic data;
  - a scratch model of §4.4, not repository code, applied to the F-2 snapshot with and without §4.6.
- **Run on 2026-11-07, against `6f47380`'s §4.4** (scratch transcriptions, not repository code; code identical to `3740119`):
  - the F-5 reproduction, on snapshots built by trusted restore and the API: Examples A to C, multi-hop descendants, and consistent controls;
  - a seeded random check over 3,000 graphs (60,135 items): the corrected predicate's normative and walk-local forms and a memoized resolver agree, whatever the insertion and resolution order;
  - an ordinary import of E1's shape (refused whole) and a raw status repair (permitted), with synthetic data.
- **Not run:** no implementation exists, so no acceptance test in §15 has run and no runtime behaviour is claimed. This is a documentation-only change.

## 19. Independent review of revision 2 and dispositions

The independent Codex Tier 2 policy review of `8f7576c` returned **CHANGES REQUIRED**, as relayed by the founder on 2026-11-07. Its delta review of `6f47380`, also relayed by the founder on 2026-11-07, accepted the dispositions of F-1, F-3 and F-4 and the resolution of F-2's original example. It found one P2 defect, F-5. The reviewer-owned findings artifacts are not in the repository. This table is the builder's response, not the findings.

| Finding | Severity | Reproduced | Disposition |
| --- | --- | --- | --- |
| F-1: the fingerprint omits evidence-set integrity | P2 | Yes (G8), on `3740119` too | Fixed: §7.3 binds integrity and enumerates every independent decision input; §15, A7 |
| F-2: legacy histories invalidate the forward-only rationale | P2 | Yes (G9) | §4.6, a recommended refinement pending founder ratification; also §6, §13, §16 (R3, R12) and §15 (A8, A9, P5) |
| F-3: complexity claims | P3 | Not applicable (wording) | §8: the resolver's cost is separated from the compile's total cost, and the lightweight ancestor projection is specified. Issues #14 and #17 stay separate |
| F-4: acceptance and basis precedence | P3 | Not applicable (wording) | §8's failure mode, and §15 rows 7, 8, 12 and 13, aligned with §4.4 and with `/api/ask`'s order (§7.4) |
| F-5: §4.6 does not propagate through descendants | P2 | Yes, against `6f47380`'s §4.4: Examples A to C and multi-hop descendants | Fixed. A walked record that is `active_with_correction` is restrictive (§4.4). Forward propagation is stated in §4.1, §4.3, §4.6, §5, §6, §7.3 and §8; one resolver serves every path (§14). New: §15.1 (E1–E12), §16 (R2, R12) and C17 |

## Revision notes

- **Revision 2, second amendment (2026-11-07).** Made after the delta review of `6f47380` (§19).
  - **F-5:** a walked record that is `active_with_correction` is restrictive. §4.6's restriction therefore propagates forward to every descendant record and to the claims citing them.
  - **What it does not add:** no backward inheritance, and no new query; a walked record's stored correction is the item before it.
  - **Added:** C17 and §15.1 (E1–E12).
  - **Updated:** §4.1, §4.3, §4.4, §4.6, §5, §6, §7.3, §8, §13, §14, §15 (A1, A8, A9, row 8), §16, §17, §18 and §19.

  Nothing else changes.
- **Revision 2, first amendment (2026-11-07).** Made after the independent review of `8f7576c` (§19):
  - **F-1:** integrity is bound in the claim projection, and the independent decision inputs are enumerated.
  - **F-2:** the §4.6 consistency exception, recommended and pending ratification, with the accepted forward-only residual stated.
  - **F-3:** the resolver's cost is separated from the compiler's, and the ancestor projection is specified.
  - **F-4:** precedence and status codes are aligned in §8 and §15.
  - **Also added:** G8, G9, C13–C16, A7–A9, P5, R12 and §19.

  Nothing else in the contract changes.
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
