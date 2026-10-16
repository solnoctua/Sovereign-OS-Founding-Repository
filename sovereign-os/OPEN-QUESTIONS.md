# SOVEREIGN — Founding questions

These are **real decision points**, not reasons to delay the initial draft. Recommendations are hypotheses pending approval.

## Constitutional / purpose decisions (highest priority)

**Q1 — Who is Sovereign for first?**  
Recommended: one user and their devices, with open interfaces and future capability for other users; not a consumer SaaS constitution yet. Decide whether the founder's personal product and a future mass-market Sovereign are conceptually the same system or two products sharing a kernel.

**Q2 — What does 'sovereignty' require in practice?**  
Recommended: ownership + portability + enforced consent + real exit + meaningful offline access, **not** an absolute ban on external AI. Specify any non-negotiable forbidden data flows.

**Q3 — How prescriptive may the Cognitive Governor be?**  
Recommended: default to user-steerable assistance and optional challenge/training, no covert behavioral optimization. Decide whether/when Sovereign may interrupt to protect a declared long-term goal.

**Q4 — Which values govern conflicts?**  
Examples: a user-authorized high-risk act versus a safety policy; private convenience versus another person's consent; perfect recall versus the right to forget; less interface versus expressiveness. Proposed answer: transparent trade-offs, explicit approval, law/other people's rights, reversible defaults.

## Architectural decisions (for ADRs, not the Constitution)

**Q5 — Canonical vault host?** Mac-local first, user-controlled home server, or managed encrypted sync? Recommended first: Mac-local; no public internet exposure at V0.

**Q6 — Raw capture retention?** Store all input, transcript only, or per-event selectable? Recommended: selective, transparent retention; avoid always-on passive recording and assume consent is required for recording others.

**Q7 — Memory promotion?** Manual approval of every claim versus risk-scoped automatic promotion? Recommended: source-preserving suggestions with human approval for identity, relationships, health, financial and other sensitive claims.

**Q8 — Local database?** SQLite or PostgreSQL? Recommended: benchmark one minimal event/claim workflow and test backup/migration; prefer least complexity consistent with invariants.

**Q9 — Cloud disclosure policy?** Which content may be sent to which providers, at what budget, with what retention guarantees? Recommended: explicit classification and provider policy before uploading any real sensitive memories.

**Q10 — Device and key loss?** Which recovery mechanism is acceptable, and who can recover the vault? Recommended: encrypted backup + tested restore + documented key-loss consequences before daily use.

**Q11 — Earliest approved integrations?** Thought capture, filesystem, calendar, email, web, agents, calls, messages? Recommended: capture and retrieval before write-access services.

**Q12 — December definition of success?** A secure daily personal intelligence loop, or a custom device / phone replacement? Recommended: software daily-driver proof by December; device hardware as separate research workstream.

## Evidence still missing

- Exact contents of the Kimi *Sovereign* folder and the full *Estimate Kimi Costs* export.
- The full pinned AI chat and any locally saved hardware designs.
- Existing project repositories, if any.

When obtained, add direct source notes and revise this draft with traceable decisions rather than overwriting it without history.
