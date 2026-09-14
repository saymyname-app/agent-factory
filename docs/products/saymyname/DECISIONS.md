# SayMyName product decisions

This is the concise durable decision log for the PO cockpit. Record accepted
product/operating decisions here; keep implementation progress and evidence in
Beads and GitHub.

## Accepted

### 2026-09-14 — Social-memory companion product vision

SayMyName is not limited to an organizational directory. Its durable purpose is
to help a person recognize faces, recall names and retain chosen useful context
for real-world social interactions across public culture, organizations and
private life. The defensible promise is improvement on people and information
actually trained, not broad intelligence, health or therapeutic claims.

### 2026-09-14 — Personal learning home in V1

A minimal personal home is part of V1 and remains independent of organization
membership. It combines available sources, the learner's explicit selections,
due reviews and private progress. It is not modeled as a personal organization
and does not require a full personal CRM in V1.

### 2026-09-14 — Three sources and learner choice

People may become available through public challenges, authorized organizations
or personal additions/imports. Availability never enrolls a person or every field
into learning automatically; the learner chooses what to practice. Their
selection, attempts, errors, schedule and progress are private from organizations
and other users.

### 2026-09-14 — Public cultural challenges are product

Challenges featuring recognizable public figures are a legitimate consumer use
and acquisition path. Anonymous trial is allowed; saving progress requires an
account. Published content requires versioned editorial review, factual and image
provenance, license/rights handling and withdrawal. Editorial roles remain scoped
to the public catalogue rather than creating an omnipotent global super-admin.

### 2026-09-14 — Three organization archetypes

Planned organization needs are covered by participative groups, administered
organizations and federated organizations. Promotions, events and communities
are configurations of a participative group; an officially imported school or
company population is administered; multiple access spaces and delegated central
governance are federated. Size, sector and duration do not create additional
technical organization types.

### 2026-09-14 — Import is core, authority remains explicit

Personal and organization imports are core friction-reduction paths. CSV is the
universal first source; Google, Microsoft, contacts, HRIS and social-network
connectors are selected only after evidence and provider feasibility. Public
availability, OAuth authorization and lawful reuse are distinct: every import
must have a defined destination, provenance, scope, revocation behavior and data
authority. Importing a profile never silently creates an account or invitation.

### 2026-09-14 — Intelligent retrieval without invented identity

SayMyName should eventually retrieve a person using remembered natural-language
clues, but only within profiles the learner may access. Results explain matches
from existing fields and the product asks for another clue or abstains when
evidence is insufficient. This is not camera-based facial recognition and must
not infer sensitive characteristics.

### 2026-09-14 — Free student-cohort pilot before payment

The first accessible validation target is a new adult student cohort reached
through Benjamin's former school administration or student association. The
pilot is free, requires no payment method and tests onboarding, delayed recall,
return and real-interaction usefulness. Payment implementation and exact pricing
wait for evidence and buyer conversations.

### 2026-09-14 — Single PO cockpit

Benjamin's normal SayMyName entrance is the Codex local project rooted at
`C:\Dev\Projects\SayMyName`. The assistant in that project acts as the sole
product-facing PO and uses the Mayor for Factory execution.

### 2026-09-14 — Native desktop/mobile bridge

Codex desktop/CLI on BenForge plus Codex Remote on the phone is the accepted
control bridge. A custom plugin, MCP server or public dashboard is deferred until
a concrete missing capability is demonstrated.

### 2026-09-14 — Strict PO/Mayor ownership split

The PO owns what and why: product intent, priority, acceptance, durable context,
and the concise conversation with Benjamin. The Mayor owns how and execution:
executable Beads, formulas, dispatch, workers, session monitoring, retries,
recovery, branches, PR/CI/merge, and operational closure. Once an outcome is
handed off, the PO waits for product-level milestones and never runs a parallel
control loop over the Mayor.

### 2026-09-14 — One execution system

Gas City and the Mayor coordinate work, Beads stores executable outcomes and
dependencies, and GitHub proves delivery. Linear is historical reference only.

### 2026-09-14 — Ordered product candidate queue

Benjamin and the PO may keep future outcomes in an exact, reorderable queue of
deferred Beads. Candidates are not executable work, paused entries are skipped,
and urgency does not silently change order. The Mayor alone materializes the
first eligible candidate into a separate execution Bead; reprioritization never
interrupts work already underway.

### 2026-09-14 — Full access with bounded authority

The SayMyName cockpit may be configured with full host access so it can reach the
Windows repos, local database helpers and WSL Factory. This capability never
implies permission to reveal secrets, expose services publicly, mutate production,
spend money, reboot the host or perform irreversible/destructive actions.

### 2026-09-14 — Safe database posture

Agent database inspection is read-only. Flyway owns schema migrations; persistent
migration execution needs explicit authorization and tests use isolated databases.

## Open

- Administration or student-association distribution for the first cohort.
- First challenge themes after content and image feasibility.
- Pilot success thresholds and duration.
- Exact group visibility, expiry and post-group retention rules.
- First buyer and pricing test.
- First external connector justified by observed user data.
- Brand/name evolution after the broader value proposition is tested.

## Update rule

Add or amend an entry only after Benjamin approves or explicitly asks to record a
decision. If a new decision supersedes an old one, mark the old entry superseded
and link the replacement rather than silently rewriting history.
