# SayMyName product context

This document stores durable product context, not live execution state. Refresh
live work with `./bin/saymyname-product-status` and the relevant Bead.

## Product intent

SayMyName helps people learn and remember the names and useful attributes of the
people in their organization. The product should turn an awkward memory problem
into a short, clear and trustworthy learning loop while giving authorized admins
simple control over membership and data.

## Core users

- Member/learner: recognizes colleagues and improves recall through quizzes.
- Workspace administrator: manages the tenant, people and learning data safely.
- Benjamin/Product Owner: decides product value and priority through the PO
  cockpit; he should not need to interpret Factory internals.

## Approved outcome sequence

1. Onboarding and tenant lifecycle.
2. Quiz and learning engine.
3. Admin and data management.
4. V1 release readiness and launch evidence.
5. Competitive or expansion work only after the V1 path is explicit.

The active/next item is never inferred from this list; Beads is authoritative.

## Product principles

- Optimize for recognition and learning clarity, not feature count.
- The backend is authoritative for identity, tenant boundaries and persisted data.
- Never show invented progress, fake statistics, or success without evidence.
- Prefer a simple, usable path over exposing technical machinery to users.
- Preserve privacy, authorization and tenant isolation in every feature.
- Keep product wording and interaction coherent across frontend and backend.

## Operating model

Benjamin speaks to the SayMyName PO cockpit. The PO owns product intent,
priorities, acceptance and durable decisions, then hands a bounded outcome to the
Factory Mayor. The Mayor exclusively translates it into executable Beads and owns
dispatch, workers, recovery, branches, PR/CI/merge and operational closure. The PO
receives product milestones and never becomes a second orchestrator. Gas City,
Beads and GitHub remain execution truth; Linear and chats do not.

## Known constraints and debt

- Backend and Frontend are separate Git repositories with their own safeguards.
- Database access from agents is read-only by default; Flyway owns schema changes.
- Existing broad lint or technical debt must not be hidden inside unrelated work;
  isolate it as an explicit outcome when it affects delivery.
- Production/cloud mutation and public exposure remain explicit ADMIN decisions.

## Product questions still owned by Benjamin

- Primary first customer/profile and the purchasing decision-maker.
- V1 success metric and acceptable onboarding/learning outcome.
- Business model, pricing and distribution path.
- Exact production launch criteria and acceptable operational risk.

These are open decisions, not blockers unless a selected outcome depends on them.
