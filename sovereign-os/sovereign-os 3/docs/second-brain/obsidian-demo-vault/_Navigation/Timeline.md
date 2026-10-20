---
sovereign_projection: 1
sovereign_projection_id: "demo-projection"
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

Capture times and decision times of the items **in this export's scope**, oldest first. Sovereign records when something was written down and when a human decided about a claim. It does not yet record when a statement was true in the world, or whether a replacement was a correction or a change (SB-6); this demo states the reason in words.

- **2026-03-02** — source captured: [[Lantern kickoff note (s-6cfaa4)]]
- **2026-03-03** — decision approved: [[Lantern stores readings in PostgreSQL (c-fcbaf2)]]
- **2026-04-10** — source captured: [[Harbor design memo r1 (s-03d37f)]]
- **2026-04-11** — claim approved: [[Harbor syncs every 5 minutes (c-96826c)]]
- **2026-04-12** — source corrected (a capture error): [[Harbor design memo r2 (s-9e44d1)]] replaces r1, and the 5-minute claim becomes **stale**
- **2026-06-14** — source captured: [[Lantern storage review (s-560123)]]
- **2026-06-15** — decision replaced (a change of plan): [[Lantern stores readings in SQLite on device (c-39798e)]] supersedes the PostgreSQL decision and is approved
- **2026-06-16** — claim approved: [[Lantern battery lasts about 14 days (c-acdade)]]
- **2026-06-20** — source captured: [[Field test log (s-8421e4)]]
- **2026-06-21** — claim contested: [[Lantern battery lasts about 14 days (c-acdade)]]
- **2026-07-01** — source captured: [[Harbor planning call (s-38b9bd)]]
- **2026-07-02** — relationship approved: [[Harbor DEPENDS_ON Lantern (r-8222a6)]]
- **2026-07-05** — relationship proposed by a model, unreviewed: [[Harbor USES PostgreSQL (r-6b50eb)]]
- **2026-07-09** — source imported: [[Feature request from the Harbor beta list (s-b8489b)]]
