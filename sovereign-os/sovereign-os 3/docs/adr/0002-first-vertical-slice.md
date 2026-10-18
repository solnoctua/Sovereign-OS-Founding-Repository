# ADR-0002 — A small local-first vertical slice before framework scale

**Status:** Accepted for prototype implementation only · October 18, 2026

## Decision

- Start with a single-user Python/FastAPI loopback service and an inspectable browser UI, not a native desktop or custom hardware app.
- Persist human-entered source records in SQLite (application-layer encryption **not included** in this prototype).
- Keep retrieval local and deterministic before adding embeddings, temporal graphs, or vector services.
- Provide a replaceable provider adapter for Kimi/Moonshot and OpenAI with explicit server-side cloud disclosure approval for each request; selected source texts are shown in the UI before approval. Sensitive-classified source records are blocked from cloud sending in V0.
- Avoid agent-tool execution until permissions and threat model are independently implemented.

## Why

This is a test of the most important end-to-end system boundary: user intent, private record, context assembly, provider selection, and model disclosure. It can demonstrate utility without creating many architectural dependencies. The V0 requirement is a real running app, not only architecture diagrams.

## Tradeoffs and risks

- No local generative model. "Local evidence" lists source records without pretending to perform advanced inference.
- SQLite and the browser UI are replaceable. Migration and encrypted persistence will be separately evaluated.
- Loopback-only exposure helps but is **not authentication or encryption**. A compromised local machine can read records; localhost web threats are not fully eliminated.
- No robust data-at-rest encryption, mobile capture, OAuth, provider policy snapshots, consent receipts, audit events, background agents, or secure deletion of backups.
- Model responses are not guaranteed to cite correctly. Source records are returned separately for verification.
- Cloud use requires an API key and valid configured model, which were not available for a live integration test.

## Immediate next decisions

1. One-page threat model with assets/attackers/trust boundaries.
2. Data-at-rest encryption and key recovery ADR.
3. Cloud consent and provider retention policy tracking.
4. Memory claim state schema (`evidence` → `proposed` → `approved` or `rejected`) separate from raw capture.
5. Benchmarked retrieval upgrades only after actual failure cases.

## Reversibility

Original notes are JSON-exportable with schema version and tombstones. SQLite is a prototype implementation, not canonical semantics. A future store must test full export/import and failure rollback before promotion.
