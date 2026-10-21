# Sovereign — Founding review of the four decisions

**Date:** 2026-10-16

**Status:** AMENDMENTS PROPOSED — Constitution NOT ratified

**Baseline:** main branch founding draft v0.1 (the former `sovereign-os/*.md` files; removed from the working tree in PR #3 and preserved unchanged at commit `37553c0`)

**Candidate:** review/founding-decisions-v0.2

## Founder decisions (confirmed)

1. Local-first with permissioned cloud intelligence.
2. One founder's lifelong AI OS first; optional wider adoption later.
3. AI should challenge when useful, with visible user override.
4. Risk-based, evidence-linked promotion of personal memories.

These decisions constrain technical direction. They do **not** imply blanket acceptance of the exact v0.2 amendments.

## Constitutional amendments proposed

| Article | Amendment | Why | What remains flexible |
| --- | --- | --- | --- |
| Preamble and I | Explicitly personal-first; future users retain their own agency | Prevent premature multi-user architecture and founder paternalism in a commercial product | Business model, packaging, distribution |
| II | Challenge may be proactive but recognizable, adjustable, dismissible; fallible self-model | Resolve augmentation versus optimization of a human life | Interface and challenge algorithms |
| IV | Differentiate evidence persistence, claim status and authority; conditional risk-based promotion | Avoid both burdensome approval and AI-generated false biography | Specific thresholds and workflow |
| V | Inference, cloud disclosure and tool execution require distinct authorization | Stop capability or model selection turning into unbounded access | Mechanism for grants and policy storage |
| VI | Establish local-first control plane and scoped external disclosure; honest external retention limits and offline baseline | Make sovereignty testable, not a slogan | Cloud providers, local model quality, sync transport |
| VIII | Require test gates on upgrades and migrations | Adapt over 10+ years without dispossession | Databases, models, and evaluation tooling |
| X | Ratification is an explicit recorded human event | A proposed document must not silently become law because an AI committed it | Repository workflow |

## Principal tensions and resolutions

**Powerful cloud models versus privacy.** Use two checks: provider/model is allowed for this task, AND these specific records are permitted to leave. Cloud access is optional and scoped. Remote disclosures can't be magically revoked after transmission.

**Personal-first versus eventual product.** V0 is a single-user project. Generalization is a future design question; others should not inherit the founder's private data, values, or defaults.

**Challenge versus autonomy.** Challenges are visible and dismissible. A preference for a direct answer never bypasses external-action authorization or another person's rights.

**Automated memory versus false authority.** Source events are evidence, proposals are not facts, and only risk-authorized claims become active. Sensitive identity-shaping inferences need human confirmation. Approval decisions remain provenance-linked.

**Audit history versus deletion.** Keep useful provenance subject to retention, deletion and backup lifecycle policy; don't conflate append-only event ordering with permanent possession of personal content.

**Model evolution versus trusted continuity.** Version contracts and migrations; evaluate rollouts; separate Lab, Next, and Stable; cannot self-promote privilege.

## Architecture changes proposed

- Explicit canonical local authority, with separate `CloudDisclosureGrant` and `CapabilityGrant`.
- Memory transition workflow: `proposed → active → contested / superseded / deleted`, plus `rejected`.
- Promotion by policy version, provenance, sensitivity, effect, and undo; low-risk auto-approval allowed only within human-defined bounds.
- Cloud: context minimization, denied disclosure fallback, egress metadata, no remote master keys or vault credentials.
- Offline: capture, storage, local search/review, deletion and permissions; generation may be degraded.
- Cognitive challenge modes with dismiss/override and independent authorization controls.
- Evaluation cases for unapproved promotions, revocations, model outages, undesired repeated challenges, provider exit, and deletion resurrection.

## Change-control / next steps

1. Review the exact proposed new article clauses in `CONSTITUTION.md`; accept, edit or reject them.
2. Import/reconcile the full external Kimi sources or explicitly waive that pre-ratification audit gap.
3. Record cloud disclosure baseline, raw capture retention and key/backup design before processing real sensitive material.
4. After approval, produce a ratification declaration and tag **only that approved commit** (for example `constitution-v1.0`).
5. Implement SOV-001 against the architecture's trust boundaries; architecture remains revisable through ADRs.

**Out of scope:** construction of working OS code, claims that any privacy/security measures have been technically verified, and publication of the repository to GitHub.
