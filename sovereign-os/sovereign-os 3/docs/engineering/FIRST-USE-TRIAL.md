# WP-4 First-use trial: is Sovereign useful for project knowledge?

**Status:** runnable trial protocol plus the builder's dry-run results (2026-10-22). The founder's own measurements are not yet recorded. Threshold 2 only (deliberately non-sensitive project use, `docs/SECURITY-GATE.md`): the seed is public Sovereign project knowledge, nothing private.

## Purpose

To find out whether Sovereign provides practical value for recalling accepted project decisions with their evidence, compared with reading the documents directly. Correctness is already tested elsewhere; this trial tests usefulness.

## What is in the trial vault

- Fourteen short notes in `evaluation/first_use/seed.json`. Each note's `source` points back to its authoritative Git location (`git:docs/adr/0005…#8.1`), so the vault adds governed working knowledge without copying ADRs. If a note disagrees with Git, Git wins: correct or contest the note.
- One correction chain: an early note that "SB-2 is blocked" is corrected to "development is not blocked; real data is". It exercises lineage and provenance navigation.
- Five claims, imported as **unverified proposals**. You approve, reject or contest them in the UI; the seed decides nothing.

## How to run it

```bash
cd "sovereign-os/sovereign-os 3"
python -m evaluation.first_use --dry-run                                      # builder measurement on a temporary vault
python -m evaluation.first_use --vault ~/sovereign-trial/project.db           # a NEW file, outside any Git tree
SOVEREIGN_DB_PATH=~/sovereign-trial/project.db python -m sovereign           # then open http://127.0.0.1:8765
```

The loader refuses an existing file and any path inside a Git working tree.

## Builder dry run (2026-10-22, `main` + this PR; lexical retrieval, local target, no provider called)

| Question | Expected evidence recalled | Notes |
| --- | --- | --- |
| t1 Why did we choose computed-on-read provenance? | 1/1 | |
| t2 Which issues currently block SB-2? | 2/2 | The correction (`fu-03`) is included; its superseded predecessor is excluded as `superseded` |
| t3 What changed after the independent architecture audit? | 2/2 | 2 other notes also included |
| t4 Why are OpenClaw and Hermes deferred? | 2/2 | |
| t5 Which architectural assumptions remain unverified? | 2/2 | |
| p1 Is anything stopping the graph work right now? | **0/2** | paraphrase probe |
| p2 Why not just plug in an existing agent platform for messaging? | **1/2** | paraphrase probe |
| p3 What do we still not know for sure? | **0/2** | paraphrase probe |

After approving all five proposals, each of t1–t5 also returns one or two approved claims as approved memory. Evidence recall is unchanged. A cloud plan offers 3–5 private items per question for approval.

**What this does and does not show:**

- **The questions t1–t5 share words with the notes because one author wrote both.** Their perfect recall is an upper bound, not evidence of usefulness.
- **The paraphrase probes are the real signal.** Ordinary wording finds 1 of 6 expected items. This matches Benchmark 0003, where no lexical method recovered a paraphrase.
- On today's retrieval, Sovereign is useful when you use the vault's own vocabulary, pin records, or navigate provenance (PR #11). It is not yet useful for loosely worded questions.
- This is the measured need that ADR-0005 R6 requires before local embeddings or a local model are reconsidered. It is not, by itself, a decision to adopt either.

## Founder protocol (about 30 minutes, then one week of ordinary use)

1. Load the trial vault (above). Review the five proposals; approve, contest or reject each. Note how long each decision takes.
2. Ask t1–t5 **in your own words first**. For each, record:
   - whether the preview contained the answer with its evidence;
   - seconds to an answer you trust;
   - seconds to the same answer by searching the repository documents directly.
3. Use **Provenance** on one claim and one corrected note. Record whether it explained "why do I believe this, and what changed" without opening Git.
4. Forget one note. Confirm that its claims disappear, that the preview no longer offers it, and that the Forget dialog stated the limits correctly.
5. For one week, add a note whenever you make or learn a project decision, citing where it lives in Git. At the end, record the counts below.

## Measures (the five actionable early metrics)

| Metric | How | Target that would justify the next step |
| --- | --- | --- |
| Correct recall with evidence | Share of your own-words questions whose preview contained the evidence | ≥ 70% before relying on it; below 50% argues for retrieval work before SB-2b |
| Time to an accepted decision | Seconds, Sovereign versus repository search | Sovereign at least as fast for ≥ 3 of 5 questions |
| Repeated explanations avoided | Times in the week you handed a coding agent a vault answer instead of re-explaining | Any non-zero count supports Builder 1 |
| Approval burden | Decisions per day and seconds per decision | Low enough that you still read what you approve |
| Privacy incidents | Anything private entering this vault, or any unexpected egress | Zero; any incident stops the trial |

Record results in a new section below. Do not edit the dry-run section.

## Founder results

_Not yet recorded._
