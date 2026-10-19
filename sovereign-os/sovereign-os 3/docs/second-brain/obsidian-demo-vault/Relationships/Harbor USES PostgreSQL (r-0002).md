---
sovereign_projection: 1
sovereign_id: "r-0002"
kind: relationship
title: "Harbor USES PostgreSQL"
predicate: USES
subject: "p-harbor"
object: "k-postgresql"
status: proposed
support: supported
authoritative: false
origin: model
created_at: "2026-07-05"
extracted_by: "synthetic local extractor"
future_fields: [predicate, subject, object, extracted_by]
available_after: "SB-7"
tags: [sovereign/relationship, sovereign/status/proposed, sovereign/support/supported]
generation: 1
generated_at: "2026-10-19"
demo: synthetic
---
> [!NOTE]
> Synthetic demo of a Sovereign projection (generation 1, 2026-10-19). A snapshot, not memory: Sovereign is authoritative, and edits here are never imported.

> [!WARNING]
> **Unreviewed model proposal — not a fact.** A default export leaves proposals out; this demo includes one to show why.

# Harbor USES PostgreSQL

- **Subject:** [[Project Harbor (p-harbor)]]
- **Predicate:** `USES` (predicate registry v1)
- **Object:** [[PostgreSQL (k-postgresql)]]
- **Status:** proposed by a model on 2026-07-05; not reviewed

## Why this connection exists

- [[Lantern kickoff note (s-0001)]] — "Lantern will store sensor readings in PostgreSQL on the home server."

The cited evidence is about **Lantern**, not Harbor, and that plan was later replaced. A reviewer reading this section should reject the proposal. A misattributed extraction still draws a confident-looking line in the graph; that is why model-extracted relationships never become approved memory without review.

## Decision history

| When | Change | By | Note |
| --- | --- | --- | --- |
| 2026-07-05 | created as proposed | model | Extraction run (synthetic) |
