---
sovereign_projection: 1
kind: navigation
title: "Timeline"
tags: [sovereign/navigation]
generation: 1
generated_at: "2026-10-19"
demo: synthetic
---
> [!NOTE]
> Synthetic demo of a Sovereign projection (generation 1, 2026-10-19). A snapshot, not memory: Sovereign is authoritative, and edits here are never imported.

# Timeline

Capture times and decision times, oldest first. Sovereign records when something was written down and when a human decided about a claim. It does not yet record when a statement was true in the world, or whether a replacement was a correction or a change (SB-6); this demo states the reason in words.

- **2026-03-02** — source captured: [[Lantern kickoff note (s-0001)]]
- **2026-03-03** — decision approved: [[Lantern stores readings in PostgreSQL (c-0001)]]
- **2026-04-10** — source captured: [[Harbor design memo r1 (s-0003)]]
- **2026-04-11** — claim approved: [[Harbor syncs every 5 minutes (c-0003)]]
- **2026-04-12** — source corrected (a capture error): [[Harbor design memo r2 (s-0004)]] replaces r1, and the 5-minute claim becomes **stale**
- **2026-06-14** — source captured: [[Lantern storage review (s-0002)]]
- **2026-06-15** — decision replaced (a change of plan): [[Lantern stores readings in SQLite on device (c-0002)]] supersedes the PostgreSQL decision and is approved
- **2026-06-16** — claim approved: [[Lantern battery lasts about 14 days (c-0004)]]
- **2026-06-20** — source captured: [[Field test log (s-0006)]]
- **2026-06-21** — claim contested: [[Lantern battery lasts about 14 days (c-0004)]]
- **2026-07-01** — source captured: [[Harbor planning call (s-0005)]]
- **2026-07-02** — relationship approved: [[Harbor DEPENDS_ON Lantern (r-0001)]]
- **2026-07-05** — relationship proposed by a model, unreviewed: [[Harbor USES PostgreSQL (r-0002)]]
