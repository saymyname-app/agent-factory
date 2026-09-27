# SayMyName product context

This document stores durable product context, not live execution state. Refresh
live work with `./bin/saymyname-product-status` and the relevant Bead.

## Product intent

SayMyName is a social-memory companion. It helps people recognize a face, recall
the right name and retain useful context for future real-world interactions. The
product combines a private personal learning home with three sources of people:
public cultural challenges, organizations the learner may access, and people the
learner adds personally.

The product should turn an awkward memory problem into a short, clear and
trustworthy learning loop: choose, learn, recall, meet, and adjust. Organizations
remain authoritative for the profiles they provide, while the learner alone
controls their selection, attempts, schedule and progress.

## Core users

- Individual learner: chooses people and information to learn across public,
  organizational and personal sources; their progress is private.
- Participant/member: joins a promotion, event or community and may maintain
  their own shared profile.
- Organizer: creates a participative group and controls admission, visibility,
  duration and ownership.
- Organization administrator: imports and maintains an authorized population,
  publishes profiles and grants access without seeing private learning errors.
- Federated organization administrator: governs multiple access spaces and data
  sources while delegating local administration.
- Benjamin/Product Owner: decides product value and priority through the PO
  cockpit; he should not need to interpret Factory internals.

## Approved product direction

1. A minimal personal home is part of V1. It is not a personal tenant or a full
   CRM: it holds sources, explicit learning selections, due reviews, private
   progress and small personal additions.
2. Public challenges with recognizable people are a legitimate product and an
   acquisition loop, not disposable fake demos. Visitors may try them without an
   account; an account is required to save progress.
3. Organizations supply authorized content. A learner chooses which available
   people and fields to learn; joining an organization never exposes their
   individual attempts to its administrators.
4. Three organization archetypes cover the planned needs: participative group,
   administered organization and federated organization. Sector, duration and
   size configure an archetype rather than create more product types.
5. Imports are a core friction-reduction capability for personal and
   organizational use. CSV is the universal first path; platform connectors are
   selected from customer evidence and their actual authorization constraints.
6. Natural-language retrieval of a forgotten person is a planned extension over
   data the learner is already authorized to access. The product abstains rather
   than inventing an identity.
7. The first accessible pilot is a new adult student cohort reached through
   Benjamin's former school administration or its student association. The pilot
   is free and validates usage before payment is implemented.
8. The V1 public demo targets France first with one French-presidents collection.
   The format remains reusable internationally: each additional supported
   national audience initially gets at most one presidents collection when
   applicable and available. More sets must be easy to add later, without making
   broad international coverage a V1 requirement. Country selection and fallback
   behavior remain implementation choices, and every collection remains subject
   to verified content and image rights.

The detailed durable strategy and roadmap are in `PRODUCT_STRATEGY.md`.

The active/next item is never inferred from this list; Beads is authoritative.

## Product principles

- Optimize for useful real-world recall, not profile count, time in app or feature
  count.
- Distinguish recognition, active recall, preparation, reminders and lookup; not
  every stored fact should be memorized.
- Use retrieval practice, correction and spacing without making unsupported
  claims about intelligence, health or broad cognitive transfer.
- Let the learner explicitly choose people and fields; never enroll every
  accessible person into learning automatically.
- Keep learning selections, mistakes, schedules and progress private from
  organizations, subjects and other users. Single exception (Benjamin,
  2026-09-18): a learner who opts in to a leaderboard exposes their display
  name, weekly XP and rank on that board only.
- Leaderboards exist to make learners challenge each other and compare only
  what is comparable: one collection inside one audience (a public collection,
  or one organization), weekly, opt-in, never platform-wide. See `DECISIONS.md`
  2026-09-18.
- Preserve source authority: losing access to organization content stops its
  consultation and review; private selection is not an uncontrolled copy.
- Treat public availability, OAuth access and permission to reuse as different
  concepts. Import only with a defined authority, destination and provenance.
- Keep person/profile, user account, membership, learning selection and payer as
  distinct concepts.
- Prefer an editorial publisher role scoped to public challenges over an
  omnipotent SayMyName super-admin account.
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

Future outcomes may be kept in the ordered SayMyName product queue as deferred,
non-executable candidates. Benjamin and the PO may revise candidate intent and
order; the Mayor alone materializes the first eligible candidate into executable
work. Queue changes never interrupt the outcome already in delivery.

## Known constraints and debt

- Backend and Frontend are separate Git repositories with their own safeguards.
- Database access from agents is read-only by default; Flyway owns schema changes.
- Existing broad lint or technical debt must not be hidden inside unrelated work;
  isolate it as an explicit outcome when it affects delivery.
- Production/cloud mutation and public exposure remain explicit ADMIN decisions.

## Product questions still owned by Benjamin

- The first external connector justified by pilot data: personal contacts,
  Google, Microsoft or another source (already decided as Google Contacts,
  see `DECISIONS.md`; kept here as a placeholder for whichever connector
  actually gets built from real friction evidence).
- Exact production launch criteria and acceptable operational risk.

Every Enterprise-tier question — pilot distribution, cohort, go/no-go
thresholds, buyer, price, brand — is deferred until after V1 release; see
`DECISIONS.md#deferred--enterprise-until-after-v1-release`. Not tracked as a
live open question before then.

These are open decisions, not blockers unless a selected outcome depends on them.
