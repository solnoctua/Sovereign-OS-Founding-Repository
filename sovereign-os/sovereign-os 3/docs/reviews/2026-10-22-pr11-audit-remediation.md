# PR #11 Codex audit — builder remediation record, 2026-10-22

**Status:** builder-authored evidence. This is **not** an independent review, not a findings artifact, and not the audit. The Codex audit should be committed unchanged by its author or the founder (see [the PR #10 record](2026-10-22-pr10-audit-remediation.md) for the convention). The builder did not have the audit's text; it worked from the founder's directive, which summarizes F-5 to F-7. The finding IDs below are the audit's. The descriptions are the builder's reading of that summary. **No finding is closed by this record.** Closure needs a fresh independent review of the new head.

**Environment:** pinned audited head `35c7af64dce74eb12d6115e0ae62f9e2e2900300`, confirmed as the PR head before any change. Python 3.13.16, SQLite 3.45.1, synthetic vaults only.

## Stacking on PR #10

PR #11 now sits on top of PR #10. `fix/issue-6-rowid-free-storage` at `f0b6539` was merged into this branch with a merge commit: no force push, no conflicts.

The reason is the work bound. The bounded neighbour queries read eligible neighbours in id order straight from an index, with no sort. That works only under schema 5. There, `ix_claim_sources_record`, `ix_records_supersedes` and `ix_claims_supersedes` sit on WITHOUT ROWID tables, so each index entry ends with the row's primary key and comes out in id order. Under schema 4 the same index is ordered by rowid, so `ORDER BY claim_id` needs a sort over every link to the record.

The merge sequence was already PR #10, then PR #11. The PR's base is now `fix/issue-6-rowid-free-storage`, so its diff shows only this PR's changes.

## Reproduction on `35c7af6`

| Finding | Reproduced |
| --- | --- |
| F-5 | At capacity 1, a forgotten predecessor and a link to a never-present record each set `truncated: true` with no eligible neighbour left out. A claim whose evidence link does not verify (hash mismatch) is drawn as `SUPPORTED_BY`, and such claims take capacity: with 40 of them sorting first, the 5 verified claims are crowded out. A record in an unrecognised state (`pending`) is returned as a node and as a focus. |
| F-6 | Record `X` and claim `X` share an id. Lookup prefers the record, so claim `X` is unreachable through the API. Edge endpoints are bare ids, and the UI keys nodes by id alone. |
| F-7 | Work on a hub grows with its degree: 76, 301 and 1,051 progress ticks of 100 VM instructions at degree 500, 5,000 and 20,000, for the same 60 nodes. Responses reach 143,379 bytes for 2,000-character claims and 731,311 bytes when every character escapes to six. Every claim node carries its full history, so a claim with 1,502 decisions gives a 931,417-byte response. |

## Regression evidence

The tests are in `tests/adversarial/test_pr11_audit_regressions.py`. The existing `tests/test_provenance.py` was ported to typed identity.

For the pinned run, a copy of the regression file replaced only two helpers (`nb` and `fetch`) with adapters to the untyped signature, and the pinned `src` came first on `PYTHONPATH`. So the failures come from behaviour, not from the call shape. The F-6 API and UI tests were deliberately left unadapted, because the missing typed route and typed calls are part of F-6.

| Run | Result |
| --- | --- |
| Pinned `35c7af6` | **16 failed, 3 passed** |
| This revision | **19 passed** |

Every pinned failure is behavioural except `test_f7_the_byte_budget_truncates_consistently`, which tests a mechanism the pinned code does not have. The three tests that pass on `35c7af6` are controls:

- `[present]` predecessor at capacity 1;
- exact capacity with no ineligible neighbours;
- a Forget racing a read. The read transaction already gave a single snapshot.

| Measurement (same scenario before and after) | `35c7af6` | This revision |
| --- | --- | --- |
| Work, hub of degree 100 vs 3,000, two hops (steps of 10 VM instructions) | 652 → 2,102 | 857 → 857 |
| Work, focus claim with 100 vs 3,000 decisions | 236 → 5,456 | 98 → 98 |
| Work, hub of degree 500 / 5,000 / 20,000, one hop (ticks of 100) | 76 / 301 / 1,051 | 81 / 81 / 81 |
| Largest worst-case response (80 claims of 2,000 control characters) | 731,311 bytes | 171,695 bytes (bound 262,144) |
| Claim with 1,502 decisions | 931,417 bytes, all 1,502 events | 31,252 bytes, 50 most recent, `history_complete: false`. The export still holds all 1,502, and the regression test checks both the export and the claim listing |

## What changed

- **F-5, eligibility before capacity.** Every neighbour query enforces eligibility before anything is counted. An endpoint is eligible when it is:
  - present;
  - not tombstoned;
  - in a recognised state (records `active` or `superseded`, claims in `claims.STATUSES`);
  - for evidence, linked by a verified link (pinned hash matches).

  Absent, forgotten and ineligible endpoints never become nodes or edges, never use capacity and never set `truncated`. `truncated` now means exactly that an eligible neighbour of an expanded item was left out.

  `SUPPORTED_BY` is drawn only for verified evidence. This follows the rule the project already set for its other graph surface, [OBSIDIAN-PROJECTION §8](../second-brain/OBSIDIAN-PROJECTION.md) item 6. The claim's own `support` value still reports missing or unverified evidence, and the UI says so in the empty *Supported by* section.
- **F-6, typed identity.**
  - `neighborhood(vault, kind, id, …)`.
  - The API is `GET /api/provenance/{kind}/{id}`, with `kind` limited to `claim` or `record`; the untyped route is gone.
  - Edges carry `{"kind", "id"}` endpoints.
  - The UI keys nodes and the focus by `kind:id`, and every `openProvenance` call names the kind.
  - A Chromium check against a vault where record `X` and claim `X` coexist opened each one from its own list, then navigated to claim `Y`, with no page errors.
- **F-7, bounds.**
  - Neighbour queries are `INDEXED BY` the existing indexes, ordered by id and `LIMIT`ed to the remaining capacity plus one. `EXPLAIN QUERY PLAN` shows index searches and no temporary B-tree.
  - Non-focus text is a 400-character excerpt with `text_truncated`.
  - Only the focus claim carries history: its 50 most recent decisions, read by `Vault._claim(…, history_limit=…)`, which leaves every other caller and the stored history unchanged.
  - The serialised response is held under 256 KiB by a byte budget applied at admission.
  - A SQLite progress handler caps each read at 5,000 ticks of 1,000 VM instructions. A read that would go past the cap fails closed with `ProvenanceTooLarge` (HTTP 409) and returns nothing partial. This cap exists because rows that fail eligibility, such as thousands of unverifiable links, are skipped inside the query and so cost work without counting toward the `LIMIT`.
- **Snapshot.** The read stays in one transaction. A Forget issued during a read waits for it, and the read returns the pre-Forget graph exactly.

## Results of the remediation round

The suites ran on the stacked tree: PR #10 at `f0b6539` plus this change.

| Check | Result |
| --- | --- |
| `pytest -q` (full) | 697 passed, 2 xfailed. The xfails are PR #10's F-1 and F-4 policy tests |
| `pytest -q tests/adversarial` | 575 passed, 2 xfailed |
| `python -m evaluation.retrieval --check` | exit 0 |
| Benchmark 0003 bundles: 56 questions × `local`, `kimi`, `openai` = 168 | byte-identical on `main`, `35c7af6` and this revision (canonical sha256 prefix `17bd68094cb87888`) |

## Founder decisions carried into this PR (2026-10-22)

The founder decided D-A, D-B and D-C for PR #10, which implements them. PR #10 was merged into this branch again with merge commits only, no force push:

| Merge | PR #10 head |
| --- | --- |
| `d88208f` | `a267b6a` (D-A, D-C) |
| `9f885d1` | `48436c9` (independent scan review fixes) |
| `3486ab3` | `8ea54b5` (issue links in the PR #10 record; documentation only) |

The only conflicts were in `d88208f`, in `Vault._claim` and the UI:

- `_claim` now combines the evidence-set integrity with this PR's `history_limit`;
- the UI keeps both the revalidation dialog and the provenance panel.

Provenance follows D-A:

- **Claim nodes** carry `integrity` beside `support` and `authoritative`.
- **The focus panel** explains why a claim is not authoritative: `unconfirmed` (approved before schema 5, awaiting revalidation in the claims list) or `mismatch` (links differ from the committed set).
- **Eligibility is unchanged.** An unconfirmed claim is still a recognised status, so it stays a node. It is shown as not authoritative, never hidden.
- **Test.** `test_a_claim_made_before_schema_5_shows_as_unconfirmed_until_revalidated` (in `tests/test_provenance.py`) starts from a genuine schema-4 fixture. It checks the claim's node before and after a governed revalidation.

### Results on `9f885d1`

The code is the same at `3486ab3`, whose merge changed only the PR #10 record.

| Check | Result |
| --- | --- |
| `pytest -q` (full) | 739 passed |
| `pytest -q tests/adversarial` | 616 passed. PR #10's two strict xfails are now passing regressions |
| `python -m evaluation.retrieval --check` | exit 0 |
| Benchmark 0003 bundles (168) | byte-identical to `main` (`17bd68094cb87888`) |

## Observed outside this PR (not changed)

`GET /api/claims` and `Vault.list_claims` hydrate every listed claim's full decision history, so a page of up to 200 claims grows without bound as decisions accumulate. This behaviour was already on `main` before PR #11 and is not part of SB-2a. It is tracked separately as [Issue #14](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/issues/14), not fixed here.

## Second Codex audit: F-7 and F-9 (2026-10-27)

**Verdicts, as the founder reported them:**

| Head | Verdict |
| --- | --- |
| PR #10 `8ea54b5` | PASS |
| PR #11 `7b8dec8` | CHANGES REQUIRED |
| Integration `85bda11` (the rehearsal branch) | BLOCK |

The remaining findings are F-7 (P2) and F-9 (P2). The second report and its evidence package were not available to the builder: they were not on GitHub, in the repository, or in this session's upload and attachment directories. The builder worked from the founder's summary. **No finding is closed by this record.** Closing them needs a targeted independent re-audit.

### F-7: memory allocated before graph output

**Cause.** The import boundary accepts a record's `created_at` of any length. The graph then read whole rows (`SELECT *`) and hashed them, and every admitted item kept its hydrated content, including each claim's sources. The node, byte and work limits applied only afterwards.

**Reproduction.** Synthetic vaults were built through the real APIs. Each graph read ran in a fresh process; "Python peak" is tracemalloc's peak during the read.

| Case | `7b8dec8`: Python peak / RSS growth / response | `2b4b9b1`: Python peak / RSS growth / outcome |
| --- | --- | --- |
| Codex's case: an imported record with a ~100 MB timestamp, as focus | 310 MB / 286 MB / 326 B | 0.7 MB / 95.5 MB / 409, content-free |
| Legacy record with a 20 MB source and a 20 MB timestamp | 114 MB / 155 MB / 327 B | 0.7 MB / 38.2 MB / 409 |
| Legacy root whose correction has a 20 MB id | 81 MB / 136 MB / 278 B, `truncated` | 0.7 MB / 20.0 MB / 409: the neighbour list cannot be read |
| Ordinary record whose citing claim also cites the ~100 MB record | 310 MB / 286 MB / 804 B | 0.02 MB / 95.9 MB / 337 B: the claim left out, `truncated` |
| That claim as focus | 310 MB / 286 MB / 1,332 B | 0.7 MB / 95.8 MB / 409 |
| Hub of 1,000 claims, each citing 8 records at the content limit (40,000 bytes each), one hop | 18.8 MB / 20.4 MB / 85,489 B | 1.1 MB / 2.3 MB / the same 85,489 B |
| Same hub, claim focus, two hops | 17.0 MB / 19.1 MB / 112,230 B | 1.5 MB / 3.1 MB / the same 112,230 B |
| Claim with 1,500 decisions (notes of 485 four-byte characters) | 0.4 MB / 0.8 MB / 104,011 B | 0.4 MB / 0.9 MB / the same 104,011 B |

The 0.7 MB in refused cases includes formatting the exception in the measuring script.

**Mechanism.** The graph's read connection sets `SQLITE_LIMIT_LENGTH` to `VALUE_BYTES` (64 KiB). Measured on SQLite 3.45.1, a stored value above the limit raises `SQLITE_TOOBIG` (`sqlite3.DataError`) from its stored byte length, before it is loaded:

| Value | Without the limit | With it |
| --- | --- | --- |
| 100 MB text | 100 MB in Python | 0 MB, refused |
| 100 MB BLOB | — | refused |
| Legacy text `a\x00` + 100 MB (`length()` reports 1) | — | refused (bytes counted) |
| 25 M four-byte characters | — | refused |
| A value compared in SQL (`JOIN … ON u.k = t.v`) | — | refused |
| Binding an oversized parameter | — | refused |
| 64,000 bytes (16,000 four-byte characters) | — | read |
| 68,000 bytes | — | refused |

Values are read whole or not at all, so evidence hashes are always computed over canonical values. The focus fails closed with the content-free `ProvenanceTooLarge` (HTTP 409). An unreadable neighbour is left out and sets `truncated`; it can leave capacity unused within that expansion, and `truncated` says so. An unreadable neighbour list fails closed. Rows are read by explicit columns, and an admitted item keeps only what expansion needs. Canonical storage, history, evidence hashes, Forget and the Context Compiler are unchanged.

**Regressions:** `tests/adversarial/test_pr11_f7_allocation.py`, 14 tests covering the nine required properties.

| Run | Result |
| --- | --- |
| `7b8dec8` (pinned `src`) | **13 failed, 1 passed** |
| `2b4b9b1` | **14 passed** |

On `7b8dec8`:
- **12 failures are behavioural:**
  - large values were loaded: 54 MB for the incoming-evidence case and 19.7 MB for the hub;
  - a BLOB timestamp raised `TypeError` during JSON serialisation, which the API would answer with a 500.
- **1 failure is a missing mechanism:** `VALUE_BYTES` does not exist.
- **The pass** is the decision-history control, which `HISTORY_LIMIT` already bounded.

**Remaining limitation ([Issue #17](https://github.com/solnoctua/Sovereign-OS-Founding-Repository/issues/17), not changed here).** RSS still grows by about the oversized row's size in the refused cases. The cause is not the graph: on schema 5's WITHOUT ROWID tables, SQLite's B-tree search reads a whole overflowing cell into C memory to compare keys, before any value limit applies. A bare lookup of that row costs the same 95.5 MB. On `main` the same imported value costs:

| Operation on `main` | RSS growth |
| --- | --- |
| Adding an unrelated note | 97 MB |
| Listing memories | 479 MB |
| A Context Compiler run | 382 MB |

The remedy is a bound on time values and legacy metadata at the write boundaries. That changes PR #10's audited storage contract, so it is left to the founder.

### F-9 in this PR

The validation spec now says that §3 is implemented by this PR and maps each item to its tests. It states item 4's real coverage:
- tokens over all 56 queries for `local` and `kimi`;
- a static import check;
- no run with the module removed.

The other F-9 observations concern the integrated documents. They are fixed in PR #8 (the inventory test and the honest claims exit) and in the revised reconciliation commits R10 and R11. See `docs/reviews/2026-10-22-f9-f10-reconciliation.md` on PR #8.

### Results at `7017394`

The record commit that follows changes documentation only.

| Check | Result |
| --- | --- |
| `pytest -q` (full) | 753 passed |
| `pytest -q tests/adversarial` | 630 passed |
| `python -m evaluation.retrieval --check` | exit 0 |
| Benchmark 0003, 168 bundles (56 questions × `local`, `kimi`, `openai`) | byte-identical to `main` (`17bd68094cb87888`) |
