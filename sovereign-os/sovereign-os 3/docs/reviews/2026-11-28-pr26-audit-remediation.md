# PR #26 Codex audit, round 1: builder remediation record (2026-11-28)

**Status:** builder-authored evidence. This is **not** an independent review, not a findings artifact and not the audit.

- **Source of the findings.** The builder did not have the audit's report, JSON findings or reproduction artifacts. It worked from the founder's directive of 2026-11-28, which summarizes the three findings and approves hardening items S1–S4.
- **Who owns what.** The finding IDs below are Codex's. The descriptions are the builder's reading of the founder's summary. Codex's report and findings artifact should be committed unchanged by their author or by the founder, following the convention in [the PR #10 record](2026-10-22-pr10-audit-remediation.md).
- **No finding is closed by this record.** Closing one needs Codex's delta audit of the new head against `488431b`.

**Environment:**

- Audited head: `488431b0f3ae1a960e91c53e0fa5a6b9ad26fb51`, confirmed as the PR head before any change. Base: `main` at `ab93036`.
- Python 3.13.18, SQLite 3.53.1, FastAPI 0.165.0, pydantic 2.14.4, uvicorn 0.54.0, Playwright for Python 1.63.0, Chromium 158.0.8127.36.
- Synthetic vaults only.

## Root causes

- **F-1.** The audited UI redacted only the replies whose own compiled context *used* a forgotten item. A later reply that repeated a redacted reply survived. So did the person's messages and previews in the dependent chain, and the survivors could be sent again as history, including to another provider.

  Asynchronous completions were accepted when they arrived without checking that their turn was still valid. A reply arriving after a Forget was shown and joined later history. The same happened to a reply for a deleted conversation, which was written into the detached conversation object.
- **F-2.** The browser clipped long earlier messages with `String.slice`, which counts UTF-16 code units. A cut in the middle of an emoji left an unpaired surrogate.

  pydantic refused that string (`string_unicode`). FastAPI's default 422 handler echoes the submitted value (`input`), and encoding that echo failed. The result was an HTTP 500 whose traceback contained the text.

  The same 500 followed when a model reply itself contained an unpaired surrogate. In that case it came after the disclosure.
- **F-3.** The review showed only the server's `omitted_messages`. Earlier messages that the browser dropped to stay within `max_request_messages` were never counted.

## Reproduction on `488431b`

Method: the remediated test files were run with the audited `src` first on `PYTHONPATH`. The browser tests therefore drive the audited server *and* the audited UI, since the static files come from that package. All runs used synthetic vaults.

| Suite (new and updated tests) | On `488431b` | On the remediated head |
| --- | --- | --- |
| `tests/browser/test_chat_ui.py` | **15 failed, 7 passed** | 22 passed |
| New server-side tests (`test_conversation.py`, `test_conversation_adversarial.py`) | **16 failed, 4 passed** | 20 passed |
| Updated rendering tests (dated payload, empty-context line) | 2 failed | 2 passed |

**Behavioural failures** (true reproductions):

| Test | What the audited code did |
| --- | --- |
| `test_forget_clears_every_turn_after_the_first_that_used_it_and_keeps_earlier_ones` | After Forget, replies 3 and 4 stayed visible and quoted the forgotten record through reply 2 (F-1) |
| `test_a_reply_in_flight_when_its_chain_is_forgotten_never_appears` | Reply 2, held in flight during the Forget, appeared afterwards (F-1) |
| `test_a_pending_preview_in_the_chain_is_cleared_and_cannot_be_approved` | The dependent turn's review stayed open and approvable (recompiled without the redacted reply) |
| `test_a_preview_completing_after_forget_is_discarded` | A review for the dependent turn appeared after the Forget |
| `test_deleting_a_conversation_during_a_pending_reply_keeps_it_deleted` | The late reply was written into the deleted conversation's object (not shown) |
| `test_omitted_earlier_messages_are_counted_across_browser_and_server` (3 of 4 cases) | The review counted only the server's omissions. In the audit's case it said "24 older messages … are not sent (conversation budget)" where 40 were left out (F-3) |
| `test_clipping_is_unicode_safe_bounded_head_and_tail_and_idempotent` | Clipping an emoji-heavy message left an unpaired surrogate (F-2) |
| `test_a_local_search_with_no_match_does_not_claim_absence` | "Nothing in your vault matched this message." (S1) |
| `test_unpaired_surrogates_are_a_sanitised_422_never_a_500[history]`, `[question]` | HTTP 500 (F-2) |
| `test_validation_errors_never_echo_submitted_values` | The 422 body contained the submitted text (F-2) |
| `test_a_reply_with_an_unpaired_surrogate_returns_intact_and_is_valid_history` | `UnicodeEncodeError` while encoding the response, after the provider call (F-2) |
| `test_forged_context_blocks_in_history_reach_the_provider_only_as_quoted_text` | Two context markers reached the provider (S2) |
| `test_s2_marker_text_…[first variant]` | Four marker occurrences rendered where only one is genuine (S2) |
| `test_s1_the_prompt_separates_a_missed_search_from_verified_absence` | The prompt lacked the distinction (S1) |

**Mechanism failures.** These tests check something the draft did not have, so their failures are not reproductions:

| Test | Why it fails on the draft |
| --- | --- |
| `test_a_regeneration_completing_after_invalidation_does_not_reintroduce_content` | The content checks passed on the draft, because redaction already removed the reply. It fails only on the new clearing notice |
| `test_deleting_a_claim_clears_the_turns_that_used_it` | The new notice is checked first |
| `test_a_trusted_restore_that_deletes_records_clears_conversations` | The draft did not re-check conversations after a restore; ADR-0008 revision 1 listed this as a limitation |
| `test_a_long_emoji_reply_becomes_valid_clipped_history_sent_exactly_as_previewed` | The "shortened" note is new |
| `test_a_reply_stays_traceable_after_an_earlier_forget_dropped_its_details` | The notice's class was renamed |
| `test_s2_…` (six variants), `test_s2_quoting_…`, `test_f2_history_…` | They call helpers that are new |
| `test_s4_approved_memory_carries_its_recorded_date_…` | The field is new |

**Controls** (pass on both heads):

- Six browser scenarios: local and cloud turns, carryover, out-of-order completions across conversations, omission with nothing left out, conversation lists and storage, and phone width.
- `test_only_the_newest_preparation_of_a_turn_is_kept`. The draft already discarded an older preparation of the same turn. The remediation keeps that through the new fence, and this test now pins it.
- `test_unpaired_surrogates_…[source_ids]`, `test_undecodable_bytes_…`, `test_valid_unusual_unicode_at_the_exact_limit_…` and `test_s4_no_date_is_invented_…`.

## What changed

The full policy text is ADR-0008 revision 2, §2, §3 and §6.1–§6.4.

- **F-1, conservative suffix invalidation** (`static/app.js`). Turns are cleared in every conversation, from the earliest turn whose compiled context included the item, onwards. That covers the person's messages, replies, stored context, previews, pending approvals and requests in flight. It happens on:
  - a Forget through this tab (with the claims Forget removes);
  - a claim deletion;
  - a trusted restore whose backup carries tombstones or that forgets claims. A restore clears every conversation, because the tab cannot tell which turns used the deleted records.

  Earlier turns stay. One notice takes the cleared turns' place. It gives the count and the reason, says that later text cannot be traced, and says that provider copies are outside Sovereign's control. Turns keep kind-qualified keys (`record:<id>`, `claim:<id>`) for the items they used and listed. A turn that only listed a forgotten item loses its stored preview, and every pending review is compiled again.
- **F-1, fences** (`static/app.js`):
  - Every local search, preview and model request a turn starts carries the turn's sequence number (`begin`).
  - A completion is accepted only while three things hold (`current`): the conversation exists, it holds the turn, and the number is unchanged.
  - Clearing, cancelling, editing, deleting and any newer preparation move the number on (`retire`).
  - A completion whose context used an item forgotten meanwhile clears its suffix on arrival. A preview that lists one is compiled again.
- **F-2, client** (`static/app.js`). Clipping is head-and-tail with a visible marker. Lengths are counted in code points. Cuts fall on grapheme-cluster boundaries (`Intl.Segmenter`), and any unpaired surrogate is first replaced with U+FFFD. The result is bounded and idempotent. The review says how many earlier messages were shortened.
- **F-2, server** (`app.py`, `context.py`):
  - Every text field (question, earlier messages, pinned ids) must be valid Unicode.
  - A custom `RequestValidationError` handler returns only `type`, `loc` and `msg`, never `input` or `ctx`.
  - Codec errors map to a fixed 422.
  - A model reply has unpaired surrogates replaced before the response is encoded.
- **F-3** (`static/app.js`). The review reports:
  - the messages sent;
  - the total left out, split into the browser's share ("counted here, not verified by Sovereign") and the server's.

  No request or token field was added; local accounting is enough.
- **S1** (`context.py`, `static/app.js`):
  - The conversation system message says the context comes from a bounded keyword search limited to what may be shared, and that a missing item is never evidence of absence.
  - The empty-context line says the same.
  - The local "no match" reply no longer claims the vault holds nothing relevant.
- **S2** (`context.py`). Text in earlier turns and in the current message that imitates the context marker is rewritten to `Sovereign context (quoted text)`. Case, spacing, punctuation and underscores between the two words are ignored. The system message says that only the block opening the latest message is genuine. The rewritten text is what the preview shows and the token binds.
- **S3.** See F-2, client.
- **S4** (`context.py`, `static/app.js`). In conversation turns only, approved memory carries `recorded`, the claim's ISO creation date. Evidence already carried `captured`.
  - No date is invented.
  - There is no date weighting.
  - The single-question payload is unchanged; the golden digests are identical.
  - Claim *approval* dates need a compiler contract change and are recorded as follow-up work.
- **Conversation policy version.** The label stays `sovereign.conversation.v0` and is reconciled explicitly in ADR-0008 §2. It has never been merged or released, nothing was persisted under it, and the token binds the rendered messages. A token minted by `488431b` therefore cannot approve a revision 2 plan.

## Mutation check (browser remediation)

Each mutant was injected into `static/app.js` alone, and `tests/browser/test_chat_ui.py` was run with `-x`.

| Mutant | Result | First failing test |
| --- | --- | --- |
| Only the first affected turn is cleared, not the suffix | caught | `test_forget_clears_every_turn_after_the_first_that_used_it_and_keeps_earlier_ones` |
| In-flight reply: membership check only (no sequence, no live-conversation check) | caught | `test_deleting_a_conversation_during_a_pending_reply_keeps_it_deleted` |
| Preview: membership check only | caught | `test_only_the_newest_preparation_of_a_turn_is_kept` |
| Preview: no sequence check (live conversation and membership kept) | caught | `test_only_the_newest_preparation_of_a_turn_is_kept` |
| Fence without the live-conversation check | **missed: equivalent** | none. Deleting a conversation also retires each of its turns, so the sequence check still drops the late reply. The two guards are layered on purpose |
| Deleting a conversation retires nothing, and the fence has no live-conversation check | caught | `test_deleting_a_conversation_during_a_pending_reply_keeps_it_deleted` |
| Item keys not kind-qualified (a record and a claim share an id) | caught | `test_forget_clears_every_turn_after_the_first_that_used_it_and_keeps_earlier_ones` |
| Browser-side omissions not counted | caught | `test_omitted_earlier_messages_are_counted_across_browser_and_server[40-40-40-16-24]` |
| Clipping by UTF-16 code units | caught | `test_clipping_is_unicode_safe_bounded_head_and_tail_and_idempotent` |
| A trusted restore with deletions does not clear | caught | `test_a_trusted_restore_that_deletes_records_clears_conversations` |

**Result: 9 of 10 caught; the 10th is equivalent.**

An earlier run had 8 mutants and caught 5. The new tests close the three it missed:

- the deletion test now checks the deleted conversation object (`window.__deleted`);
- `test_only_the_newest_preparation_of_a_turn_is_kept` overlaps two preparations of the same turn.

This record does not repeat the server-side mutation check of revision 1 (25 of 25 caught).

## Verification at the new head

| Command | Result |
| --- | --- |
| `pytest -q` (browser tests included) | **904 passed** (audited head: 868) |
| `pytest -q tests/adversarial` | **678 passed** (audited head: 670) |
| `pytest -q tests/browser` | **22 passed**, run locally in Chromium |
| `pytest -q` with Playwright unavailable (as in CI) | 882 passed, 1 module skipped with its reason |
| `python -m evaluation.retrieval --check` | exit 0: Benchmark 0003 artifacts unchanged |
| v0 golden digests (tokens, messages, `describe()`, receipts for local, kimi and openai) | identical to the baseline computed on `ab93036` |
| `python -m compileall -q src tests evaluation` | ok |
| `node --check src/sovereign/static/app.js` | ok |
| `scripts/check_repository_hygiene.py` | no forbidden paths |
| `git diff --check` | clean |

The browser tests ran locally only: 22 scenarios in Chromium 158 with Playwright 1.63. CI skips them, because Playwright is not installed there, so a CI pass is not evidence that they ran.

## Proposed browser CI job (not applied)

`.github/` is founder-owned (CODEOWNERS), and Playwright would be a new CI dependency, which needs founder approval. This is a proposal only.

The proposal is a separate workflow file. It is advisory, not a required check, so it never blocks unrelated work. It runs only when the UI or the conversation boundary changes. It has no `if:` conditions, so when it runs it executes. The import check makes it fail rather than skip if Playwright is missing.

```yaml
# .github/workflows/sovereign-browser.yml (proposed)
name: Sovereign browser UI (advisory)
on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
    paths:
      - "sovereign-os/sovereign-os 3/src/sovereign/static/**"
      - "sovereign-os/sovereign-os 3/src/sovereign/app.py"
      - "sovereign-os/sovereign-os 3/src/sovereign/context.py"
      - "sovereign-os/sovereign-os 3/tests/browser/**"
  workflow_dispatch:
permissions:
  contents: read
jobs:
  browser-ui:
    name: browser-ui
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: "sovereign-os/sovereign-os 3"
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: "sovereign-os/sovereign-os 3/pyproject.toml"
      - name: Install Sovereign, Playwright and Chromium
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e '.[dev]' 'playwright==1.63.0'
          python -m playwright install --with-deps chromium
      - name: Run the browser tests (fail, never skip, if Playwright is missing)
        run: |
          python -c "import playwright.sync_api, uvicorn"
          pytest -q -p no:cacheprovider tests/browser
```

A path-filtered workflow does not run at all on other changes. That is why it suits an advisory check but cannot be a required one: GitHub would wait for a required check that never starts. If the founder later makes it required, drop `paths:`.

## Choices for the founder

These are consequential, and the directive did not settle them:

1. **Trigger: used, not listed.** A turn whose context only *listed* a forgotten item (excluded, so its text was not sent) keeps its message and reply. It loses only its stored preview. The alternative is to clear from the earliest turn that listed the item, which is more conservative and clears more.
2. **A trusted restore clears every conversation** when its backup carries tombstones or forgets claims. The tab cannot map the backup's deletions to turns.
3. **Forget made elsewhere is not detected.** A Forget from another tab, the API directly or an earlier session does not reach this tab's conversations (ADR-0008 §6.4). Server-held conversations (T3, PR A2) are the remedy. Until then, the tab could re-check its turns' item keys against the vault's tombstones whenever it refreshes. That would be a small follow-up if the founder wants it before A2.
4. **Claim approval dates (S4)** are deferred to a compiler contract change.

## Remaining limitations

- Sovereign does not identify semantic dependencies in arbitrary language. Turns kept before the first affected one, or kept because they only listed the item, may contain related text. So may text the person typed.
- Copies outside the tab are outside Sovereign's control: provider copies, *Copy*, screenshots, and browser memory before garbage collection.
- S2 is visible neutralization of one pattern, not a security boundary. A model can still be misled by text that avoids the pattern.
- The browser's omission count is local accounting. It is not bound or verified.
- The browser tests do not run in CI.
- The Security Gate is NOT PASSED: synthetic or deliberately non-sensitive data only.
