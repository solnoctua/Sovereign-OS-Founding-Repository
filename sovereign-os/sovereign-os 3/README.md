# SOVEREIGN

**More life. Less interface.** · Founding prototype v0.1 · October 18, 2026

Sovereign is a proposed long-lived, personal-first AI operating environment designed to increase independent human capability, agency and presence. The Constitution defines enduring values; the Architecture and code are deliberately replaceable.

**Governance:** [`CONSTITUTION.md`](CONSTITUTION.md) is a **v0.3 candidate awaiting explicit ratification**. Do not call it approved. See [`ARCHITECTURE.md`](ARCHITECTURE.md), [`docs/SOURCE-RECONCILIATION.md`](docs/SOURCE-RECONCILIATION.md), and [`docs/adr/0002-first-vertical-slice.md`](docs/adr/0002-first-vertical-slice.md).

**Development:** shared AI coding instructions live in [`AGENTS.md`](AGENTS.md); the lightweight multi-model workflow is in [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md). Model/vendor roles are provisional and are not part of Sovereign's Constitution or permanent architecture.

## What's working in the first build

1. A real local browser interface to capture and search source notes.
2. SQLite persistence independent of a model provider.
3. Source revisions/corrections, active-record deletion with tombstones, JSON export and import.
4. Ask through a deterministic Context Compiler: it selects approved memory and evidence for a question, shows exactly what would leave the device, and sends a cloud model only that approved, exact context ([ADR-0004](docs/adr/0004-governed-retrieval-context-compiler.md)).
5. Offline, non-generative evidence inspection without any API key.
6. Optional Kimi/Moonshot or OpenAI API integration with explicit per-request consent. **There are no automatic provider requests or model-driven tool actions.**

### Critical safety warning

This is **prototype software for synthetic or deliberately non-sensitive sample data only**. There is no login, encrypted database, authenticated mobile access, background scheduler, secure wipe of backups, hardened threat model or independent security review. Running it on `127.0.0.1` is not a guarantee of secrecy against local malware or a compromised browser. Do **not** expose the server on a public host or store actual private life records yet. See [`docs/SECURITY-GATE.md`](docs/SECURITY-GATE.md).

## Run it on your Mac

Python 3.11+ required. Open Terminal inside the repository folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m sovereign
```

Open **http://127.0.0.1:8765** in your Mac's browser. The server creates a local SQLite database in `./data/sovereign.db` (excluded from Git). Press Ctrl+C in Terminal to stop it.

Run checks:

```bash
pytest -q
```

## Optional cloud model connection

Cloud is OFF unless you choose a provider in the UI, preview the compiled context and approve that exact context for the request. Only the private items shown in the preview are sent, together with your question; sensitive items never leave, and any change before sending requires a new review. Model API usage can incur provider charges.

Kimi and OpenAI APIs have distinct API keys/billing from their respective chat or coding subscriptions. Configure only what you intend to use; find a current supported model identifier in the provider's own API account:

```bash
export KIMI_API_KEY='...'
export KIMI_MODEL='<model-id-from-your-Moonshot-API-account>'
# or
export OPENAI_API_KEY='...'
export OPENAI_MODEL='<model-id-from-your-OpenAI-API-account>'
python -m sovereign
```

No key is stored in the database; **never paste secrets into chat or commit `.env` files**. Kimi API base URL is `https://api.moonshot.ai/v1`. A future model provider should be added through a similarly scoped adapter, not scattered across feature code. Provider behavior is not independently certified; research their actual retention/terms before real data use.

## Git and public/private state

`main` retains the original v0.1 founding proposal. The review branch retained v0.2. This feature branch proposes Constitution v0.3 **and** includes the first prototype; it has not been merged or ratified. Push only to a **private** GitHub repository after review. Vault data, secrets, images, recordings, and personal archives must never enter the source code repository.

## Next development tickets

- `SOV-002`: threat model, encrypted vault, auth boundary, recovery and deletion guarantee tests.
- `SOV-003`: explicit evidence/claim/intention states with approval workflow.
- `SOV-004`: evaluated memory retrieval + context policy / disclosure receipt. Context Compiler V0 (ADR-0004) provides deterministic retrieval, the context policy and a request-scoped receipt; evaluated retrieval and durable disclosure receipts remain.
- `SOV-005`: first meaningful use case (project commitment → reason → propose → human approve → observe outcome).
- `SOV-006`: iPhone local/offline capture and authenticated sync.

The Pocket hardware and sophisticated world model remain important research tracks, not blockers to a useful, safe software baseline.

## Governed second brain — planned Level 3–4 extension

Sovereign's next knowledge capability is a **governed second brain**, combining structured project/wiki views (Levels 1–2), local hybrid semantic discovery (Level 3) and source-backed provenance/domain graphs (Level 4). It must preserve the existing canonical vault, MemoryClaim authority, the Context Compiler and exact disclosure approvals. **Level 5 always-on agents and continuous ingestion are deferred** pending demonstrated value, security, and operating-cost budgets.

An **Obsidian-compatible, one-way Markdown graph projection** is an explicit future interface requirement. For an immediately viewable **synthetic** Obsidian graph, open [`docs/second-brain/obsidian-demo-vault/`](docs/second-brain/obsidian-demo-vault/) as a local Obsidian vault. This is a demonstration, **not** a working exporter or a place to put personal memory.

Read [ADR-0005](docs/adr/0005-governed-second-brain-architecture.md), [the five-level/Obsidian guide](docs/second-brain/LEVELS-AND-OBSIDIAN.md) and [Benchmark 0003](docs/benchmarks/0003-second-brain-retrieval-evaluation.md). These describe a proposed workstream, not currently running retrieval, graph or sync features.
