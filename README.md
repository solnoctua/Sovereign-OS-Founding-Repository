# Sovereign OS — repository entry point

**Canonical active project:** [`sovereign-os/sovereign-os 3/`](sovereign-os/sovereign-os%203/README.md)

Start with the active project's [README](sovereign-os/sovereign-os%203/README.md), [AGENTS.md](sovereign-os/sovereign-os%203/AGENTS.md), [Architecture](sovereign-os/sovereign-os%203/ARCHITECTURE.md), [Roadmap](sovereign-os/sovereign-os%203/ROADMAP.md) and [Constitution (founding candidate, not ratified)](sovereign-os/sovereign-os%203/CONSTITUTION.md). Run code, tests and CI from that folder (it contains `pyproject.toml`). Coding agents: the root [`AGENTS.md`](AGENTS.md) and [`CLAUDE.md`](CLAUDE.md) only route to the project's `AGENTS.md`, which governs the whole repository.

The older duplicate `sovereign-os/*.md` v0.1 founding files have been removed from the working tree to prevent assistants or contributors using obsolete architectural authority. They are preserved unchanged in Git history at commit `37553c0` (for example `git show 37553c0:sovereign-os/CONSTITUTION.md`), which is the v0.1 baseline that [the founding review](sovereign-os/sovereign-os%203/docs/founding-review-2026-10-16.md) compares against. Do not use old foundation snapshots as live project instructions.

**Planned governed second brain:** target Levels 3–4 (hybrid semantic retrieval and an evidence-backed graph, with Levels 1–2 readable views), plus an explicit Obsidian graph projection requirement. Level 5 always-on intelligence is deferred. Read the [ADR](sovereign-os/sovereign-os%203/docs/adr/0005-governed-second-brain-architecture.md) (PROPOSED), the [five-level guide](sovereign-os/sovereign-os%203/docs/second-brain/LEVELS-AND-OBSIDIAN.md) and the [Obsidian projection spec](sovereign-os/sovereign-os%203/docs/second-brain/OBSIDIAN-PROJECTION.md). This is architectural direction, not deployed graph functionality.

**Security:** current prototype is only for synthetic/intentionally non-sensitive content; do not commit personal records, database files, recordings or secrets. The repository currently lacks a `.gitignore` (see the project's [Security Gate](sovereign-os/sovereign-os%203/docs/SECURITY-GATE.md)); check `git status` before committing.
