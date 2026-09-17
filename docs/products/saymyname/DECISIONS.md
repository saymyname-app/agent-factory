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

### 2026-09-14 — Group visibility, expiry and consented personal continuity

Groups are private by default: profiles are visible only to authorized active
members, and no profile is exposed in a join preview. Time-bounded groups require
an explicit end date and advance reminders; durable communities may remain open.
Closing a group or losing membership ends access to its protected profiles and
stops their scheduled reviews.

A person who controls a claimed profile has both an account-wide sharing default
and a clear per-group choice, with the specific choice taking precedence. The
protective default is group-only visibility with no retention after access ends.
The choice is requested when the profile is created or claimed, shown again when
joining a group, and reviewable before that group expires. It is granular,
reversible and never inferred from silence.

Personal continuity is an explicit, authorized copy rather than a silent export.
When the profile owner permits it, a learner may keep only the approved fields and
photo in their private personal home, together with provenance and the private
learning state. Revocation removes the source-provided fields and media from
personal copies and prevents further review unless the learner has a separate
lawful personal source.

For an organization-imported profile that no user has claimed, the organization
may control visibility only inside the group and within its declared authority.
The profile is not personally copyable after access ends by default, and the
organization cannot turn ordinary directory access into permanent member copies.
Claiming the profile lets the person choose prospectively. Without authorized
continuity, per-person learning state and identifying content are removed at the
end of access; only genuinely anonymized aggregate learning measures may remain.

Learners may create private personal profiles and add their own notes, facts and
photos, including material found publicly, when they have a lawful right to use
it. Public availability alone is not permission to copy or share: SayMyName keeps
source/provenance, provides correction and removal paths, and does not republish
personal additions without separate authority.

### 2026-09-14 — Public cultural challenges are product

Challenges featuring recognizable public figures are a legitimate consumer use
and acquisition path. Anonymous trial is allowed; saving progress requires an
account. Published content requires versioned editorial review, factual and image
provenance, license/rights handling and withdrawal. Editorial roles remain scoped
to the public catalogue rather than creating an omnipotent global super-admin.

### 2026-09-14 — Presidents first for the localized public demo

The V1 public demo targets France first while keeping the challenge format
reusable internationally. Its first collection is French presidents. For each
additional national audience deliberately supported, the initial catalogue stays
limited to one collection and presents that country's presidents when applicable
and available. The catalogue and editorial path must make later sets easy to add,
but V1 does not require broad international coverage. Country selection and
fallback behavior remain implementation choices. Every localized collection
still requires verified factual and image provenance and lawful reuse.

### 2026-09-14 — Frozen V1 product boundary

The delivered public-challenge and personal-home foundation is the first V1
increment, not the whole V1. The pilot-ready boundary additionally requires the
participative promotion/event journey and the France-first French-presidents
collection. The complete V1 core then adds administered-organization CSV import,
personal people import and the scoped editorial publication workflow.

Natural-language retrieval, the first external connector, federation, pricing
and general launch readiness remain evidence-gated extensions. They stay visible
and ordered on the product board, but they are not allowed to silently expand the
V1 completion contract. The Mayor campaign-mode candidate is an operating-system
improvement and is not part of the SayMyName product V1.

### 2026-09-14 — Three organization archetypes

Planned organization needs are covered by participative groups, administered
organizations and federated organizations. Promotions, events and communities
are configurations of a participative group; an officially imported school or
company population is administered; multiple access spaces and delegated central
governance are federated. Size, sector and duration do not create additional
technical organization types.

### 2026-09-14 — Universal participative group with guided presets

The participative journey starts from the personal home with one user-facing
group concept rather than separate promotion, event and community products.
Creation asks what brings people together and offers four understandable starting
presets: a moment, a period, an ongoing group, or custom settings. Promotion,
training, conference, club and similar terms are contextual examples, not fixed
product or technical types. Presets supply editable defaults for duration,
admission and continuity; organizers may change them without replacing the group
or losing its configuration.

Participative groups use the planned tenant/workspace model as their access and
isolation boundary. The tenant remains an implementation and authorization
concept rather than another choice exposed during onboarding, and a preset never
creates or weakens a separate security boundary.

Admission supports direct invitation or a revocable link/QR, with direct entry or
organizer approval. Before joining, visitors see the group's purpose, organizer,
timing and applicable rules but no member profiles. A member voluntarily creates
or claims their own profile; only active members may see shared profiles, and
each learner's selections, attempts, errors, schedule and progress remain private.
Organizer analytics are strictly aggregate and are withheld when the group is too
small to prevent inference about an individual.

Names, presets, dates and admission settings remain understandable and editable,
but an edit that broadens the audience or extends profile visibility cannot apply
retroactively through silence. In particular, continuing a time-bounded group as
an ongoing group requires an explicit choice from each member. Leaving, removal,
link revocation, expiry and recovery from invitation or permission errors must be
clear. The delivered journey includes mobile, keyboard, focus, loading, empty,
error and recovery states.

### 2026-09-14 — Import is core, authority remains explicit

Personal and organization imports are core friction-reduction paths. CSV is the
universal first source; Google, Microsoft, contacts, HRIS and social-network
connectors are selected only after evidence and provider feasibility. Public
availability, OAuth authorization and lawful reuse are distinct: every import
must have a defined destination, provenance, scope, revocation behavior and data
authority. Importing a profile never silently creates an account or invitation.

### 2026-09-15 — Administered CSV journey approval

Benjamin approved the seven blocking administered-CSV choices in a PO
conversation prior to 2026-09-15, and reconfirmed that approval with Claude
acting as PO on 2026-09-15 after a cockpit display bug had hidden the pending
decision from his interface, wrongly suggesting it was still unanswered.
Creating an administered organization
requires a server-granted entitlement or pre-provisioned administrator status;
unrestricted public self-service is excluded. Creation atomically provisions one
implicit **All people** workspace and its owner boundary. Imports begin as
administrator-only drafts. Publication is a separate explicit action exposing
only approved fields to active authorized workspace members and never creating a
private learning selection.

V1 invitations are nominative and always triggered separately. Import and
publication create no account, invitation or group link. Exact replay and an
already-applied stable external row identifier are idempotent no-ops. Possible
duplicates are skipped by default; creating a separate person requires an
explicit row choice. Automatic merge and update-existing behavior are excluded
from V1, and no existing correction or private note is silently overwritten.

The raw file is deleted after successful parsing. Parsed staging rows remain
only until apply or discard, for at most 30 days, then are purged. Applied audit
keeps only necessary provenance, mapping and policy versions, actor, timestamps,
content hash, lawful stable external identifiers and aggregate counts, never raw
cell values.

Publishable organization-supplied fields are limited to declared, authorized
identity and learning context: display/preferred name, given and family name when
authorized, pronunciation, photo, role or function, and organization context
such as cohort, team or department. Email, telephone, internal identifiers and
private notes are hidden by default; email is used only for nominative invitation
unless a later explicit policy says otherwise. A participant has a clear
correction path. A disputed field may be hidden until resolution. Unpublishing,
removal or loss of access immediately ends workspace visibility and future review
from that organization source; no durable personal copy survives without consent
or a separate lawful source.

### 2026-09-14 — Google Contacts as the first external connector candidate

Superseded by [Google Contacts selected as the first external connector](#2026-09-15--google-contacts-selected-as-the-first-external-connector).

The first external connector candidate was Google Contacts, for importing
selected people into the learner's personal home. The choice was still
conditional on observed friction and Google People API feasibility.

### 2026-09-15 — Google Contacts selected as the first external connector

Google Contacts is the selected first external connector for importing chosen
people into the learner's personal home. It is the simplest cross-device default:
one cloud source can serve the same learner on PC and mobile, it fits the existing
Google sign-in path and it is likely to suit the intended student audience. This
choice deliberately accepts that Microsoft-first users and contacts stored only
on a phone are not covered initially.

Contact access remains separate from Google sign-in: authentication does not
grant it. The connector requires its own minimal OAuth scopes, explicit contact
selection and preview, provenance, retention and revocation behavior. It must
import into SayMyName rather than silently synchronize or modify the user's
address book.

This is a product choice, not delivery authorization. Implementation remains
after the core CSV paths and is conditional on confirming Google People API
provider feasibility and that observed import friction justifies the connector.
School or company directories remain organization imports rather than variants
of this personal connector.

### 2026-09-14 — Intelligent retrieval without invented identity

SayMyName should eventually retrieve a person using remembered natural-language
clues, but only within profiles the learner may access. Results explain matches
from existing fields and the product asks for another clue or abstains when
evidence is insufficient. This is not camera-based facial recognition and must
not infer sensitive characteristics.

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

### 2026-09-14 — Visibilité et conservation des groupes

Primary classification: **Product**. Design validation: **Benjamin + PO
satisfied**.

A person enters a participative group only through an invitation or a revocable,
expiring link or QR code. Before admission, member profiles are invisible. After
admission, a member sees only the minimal profile information required by the
group and by memorization that the group authorizes. The organizer may revoke
access, and every member has an explicit action to leave the group.

Retaining a personal profile beyond the event requires separate consent. The
navigation starts in the personal space, continues through groups and then
create or join, and always offers an explicit return to the personal space. This
contract does not change the universal participative-group model or any already
accepted presets.

### 2026-09-14 — Code-first design governance

The versioned product code and its reusable tokens, components and interaction
states are the default design system. Figma is used only when a genuinely
ambiguous or high-impact journey benefits from comparison before implementation;
it never becomes a second implementation truth. The approval tiers and the
design-ready checklist in `DESIGN_GOVERNANCE.md` apply to every outcome.

### 2026-09-15 — V1 is a versioned production-autonomous release contract

Benjamin defines the target and maturity of each SayMyName release. For V1, the
target is the complete product perimeter approved by Benjamin, publishable in
production and usable autonomously by its intended users. The contract covers the
whole product, including existing capabilities such as authentication, profiles,
trombinoscope, quizzes, training, settings, theme and design as well as newly
delivered capabilities. A list of recent or future work is not the V1 definition.

The versioned product documentation is the durable product truth. The cockpit's
Product view is its understandable, editable V1 projection: it shows included and
excluded capabilities, user journeys, end-to-end evidence, dependencies, open
decisions and release readiness. Benjamin may amend V1 through this product
presentation while no V2 campaign has started. Starting execution of the V2
campaign freezes the V1 contract and its evidence as immutable history; later
changes belong to V2 or a subsequent version rather than silently rewriting V1.

The PO behaves as Benjamin's product expert: it reconstructs an existing project
from durable intent and observed UI, API, data and tests; identifies incomplete or
unproven end-to-end journeys; proposes a bounded release contract; and asks
Benjamin only for decisions that materially change product behavior, scope,
exposure or operations. The Mayor may create and execute all work demonstrably
required by the approved release target. A blocking decision suspends only the
dependent capability or edge; independent eligible work continues whenever safe.
Every release must at minimum be testable and usable, while the user-selected
maturity target determines the stronger release gates.

### 2026-09-15 — Administered CSV import: authority, correction and withdrawal

Arbitrated by the PO under an explicit live delegation from Benjamin on
2026-09-15 ("tranche à ma place"). Benjamin delegated the arbitration; he did not
approve these seven points individually. Any of them may be reopened at no cost
while the V1 campaign has not frozen.

Resolves the seven decisions gated on Benjamin + PO in `af-u8id.3.1` and unblocks
`af-u8id.3`.

1. **Creator eligibility.** Administered-organization creation requires a
   server-granted entitlement or pre-provisioned admin status. No unrestricted
   self-service.
2. **Default workspace and publication.** One implicit `All people` workspace is
   created with the organization. Imports land as admin-only drafts; explicit
   publication exposes approved fields to active members of that workspace only;
   no automatic learning selection.
3. **Invitations.** Nominative and separate in V1. Import and publication never
   create accounts, send invitations or issue group links.
4. **Duplicates.** Possible duplicates are skipped by default, with an explicit
   *Create separate*. Merge and update-existing are deferred beyond V1.
5. **Retention.** The raw file is deleted after parsing. Parsed staging is kept at
   most 30 days, then purged. Applied audit and provenance keep hashes, mapping,
   actor, timestamps and counts, never raw values.
6. **Field authority, correction and withdrawal.** The mechanism already exists
   and is not rebuilt: `Attribute.editPolicy` declares authority per field and
   `FactService.applyChangesForPerson` enforces it server-side — `FREE` allows a
   direct edit, `RESTRICTED` returns 403 and makes change-request approval the
   only write path, `DERIVED` is immutable even through a change request. What
   this decision settles is which policy applies, because every attribute
   currently defaults to `FREE`:

   - identity components and organization-supplied fields imported by an
     administered organization are created `RESTRICTED`, set explicitly at import
     rather than inherited;
   - a contact detail the person adds for themselves stays `FREE`;
   - a photo supplied by the organization is `RESTRICTED` for modification.

   Correction therefore flows through the existing change-request queue and the
   organization resolves it, including by refusing it.

   **Withdrawal does not.** Withdrawing a photo, and withdrawing one's published
   profile, are unconditional rights exercised directly by the person: they never
   enter the change-request queue and the organization cannot refuse them. A
   correction is negotiable; a withdrawal is not. Two reasons: the product's whole
   promise rests on people accepting to be memorized, and a directory that can
   refuse removal is the fastest way to lose that consent; and it costs the
   organization nothing, because withdrawal is unpublication, not deletion.

   Withdrawal unpublishes: the profile leaves the published workspace, other
   members lose access to it, and its scheduled reviews stop — consistent with the
   2026-09-14 group-visibility decision. Organization-authored facts remain the
   organization's records, and the audit trail keeps hashes, mapping, actor and
   timestamps without raw values, consistent with point 5.
7. **One implicit default workspace as the initial access boundary.** Accepted.

Open consequence, deliberately accepted: an organization can refuse a correction
indefinitely. That asymmetry is tolerable only because withdrawal is not
refusable. If withdrawal ever becomes negotiable, this decision must be reopened.

### 2026-09-16 — Personal CSV import: the seven af-hr1v decisions

**Tier: delegated.** Taken under the standing design-decision delegation Benjamin
recorded in `DESIGN_GOVERNANCE.md` on 2026-09-16. Verified against the four
escalation tests before recording: the sole reader of an imported personal
contact is the importing person (nothing widens), nothing leaves the system, and
every change below is undoable within the current release by a code revert plus
a reversible migration — none of the seven fails a test. Design-ready options and
recommendations are in `af-hr1v` (40988-char contract, mayor-verified persisted
2026-09-15/16).

1. **Personal tenant provisioning trigger.** Lazily and atomically provision a
   `TenantPersonal` (+ membership + default workspace + identity attributes) the
   first time the user opens the personal-import entry point, gated only on
   `!existsByOwnerUserId`, no separate entitlement.
   Basis: `DECISIONS.md` "Personal learning home in V1" (independent of
   organization membership, no personal CRM) plus tie-breaker 2, reusing
   `ManagedOrganizationService`'s already-tested atomic-provisioning pattern.
   Reversal: revert the provisioning commit; drop any provisioned empty personal
   tenants via a reversible down-migration (no imported data is lost, since
   provisioning alone creates no person rows).
2. **Reuse vs. fork of `ImportService`/`ImportController` for personal scope.**
   Reuse the existing, already-shipped classes unmodified; add a route-level
   guard rejecting `PERSONAL`-kind tenants from `/publish`/`/invite`-adjacent
   endpoints, while `confirm()` auto-publishes internally for that kind.
   Basis: the 2026-09-15 "Administered CSV import" decision (reuse the same
   shipped, tested import mechanism) and tie-breaker 2.
   Reversal: revert the tenant-kind branch; personal scope loses the guard and
   the service reverts to organization-only behavior.
3. **Duplicate policy for personal imports.** Inherit the organization policy
   unchanged: possible duplicates skipped by default, explicit "Create
   separate" per row, computed strictly within the caller's own tenant.
   Basis: the 2026-09-15 "Administered CSV import" decision point 4 (identical
   policy) plus "Three sources and learner choice" (private, tenant-isolated).
   Reversal: revert the config; duplicate detection is a UX filter, not
   data-destructive, so reversal loses no data.
4. **Review/scheduling model for personal-imported people.** Fork
   `PersonalLearningService`'s scheduler onto a new
   `PersonalPersonSelection`/`PersonalPersonSchedule` model; do not weaken the
   organization `QuizEngine`'s mandatory-approved-photo join.
   Basis: "Three sources and learner choice" (learner selects, private
   progress) plus tie-breakers 2 and 3 — reuses an already-tested scheduler and
   keeps the narrower exposure by leaving the shared org pipeline untouched.
   Reversal: revert the new model and its additive migration via a reversible
   down-migration; the organization quiz pipeline is never touched, so nothing
   else to restore.
5. **Retention and deletion timing for personal data.** Shorten parsed-staging
   retention to 7 days (organization import uses 30). Deletion of an imported
   person is an immediate, ungraced hard delete server-side, with only a
   client-side confirmation dialog against accidental clicks — no server-side
   grace window.
   Basis: **Benjamin, 2026-09-16, in conversation** — standing rule: "pour
   trancher il faut faire le même choix que mes concurrents feraient."
   Applied: comparable products that hold user-owned personal data
   (Google Contacts, Apple Contacts, Notion, Gmail, photo libraries) converge
   on a recoverable delete with a user-visible recovery window of about 30
   days, a permanent purge afterwards, and an explicit "delete permanently
   now" action for anyone who wants it immediate. A bounded, documented window
   remains compatible with GDPR erasure "without undue delay".
   **Decision: recoverable delete with a 30-day owner-visible recovery window,
   an explicit permanent-delete action, and hard purge at expiry.** Parsed
   staging retention is aligned to the same 30 days as the organization import
   rather than shortened to 7, so there is one retention rule instead of two.
   History: an earlier PO recommendation (relayed 2026-09-16, misrecorded that
   day as Benjamin's own instruction) argued for an immediate server-side hard
   delete. That was the minority choice and it is superseded here. The
   correction matters beyond this entry: PO mail is sent under the `human`
   identity, so a PO recommendation must never again be recorded as Benjamin's
   word.
   **No longer escalated.** The point was escalated on 2026-09-16 because an
   ungraced hard delete met escalation test 2 (destruction beyond recovery).
   A recoverable delete does not meet that test, so the escalation is resolved
   by the choice itself rather than by accepting a risk. The deletion subgraph
   is unparked.
   Reversal: the window length is a config value; the recovery model is a
   revertible code path plus a reversible additive migration for the
   soft-deleted state. Nothing is destroyed while the window is open.

6. **Publication/visibility default for personal imports.** Skip Draft/Published
   entirely for personal scope: `confirm()` auto-invokes the existing
   idempotent `WorkspacePersonDao.publish` for `PERSONAL`-kind tenants; the
   frontend never shows a Publish action.
   Basis: "Personal learning home in V1" and "Three sources and learner
   choice" (private from organizations and other users; a personal tenant
   structurally has only one viewer) plus tie-breaker 2 (reuse the existing
   idempotent `publish()`).
   Reversal: revert the auto-publish branch; personal imports would then need
   an explicit publish action again, no data implication.
7. **`person_sources`/provenance schema boundary.** Do not use `person_sources`
   for personal imports in V1; rely solely on
   `import_batches`/`workspace_persons.source_batch_id`, exactly as the
   organization `ImportService` already does today.
   Basis: consistency with the already-shipped organization path (tie-breaker
   2) and tie-breaker 4 (the smaller, already-provable slice); fixing
   `person_sources.fk_ps_tenant`'s generic-tenant ambiguity is real, separate
   work, not bundled here.
   Reversal: this decision changes nothing (no new schema use), so there is
   nothing to revert.

Date and deciding role: 2026-09-16, Mayor, under the standing PO/Mayor design
delegation. Any of the seven may be reopened at no cost while the V1 campaign
has not frozen. This resolves the block on `af-7700`; delivery resumes.

### 2026-09-18 — Leaderboard: scoped, opt-in, comparable (resolves `leaderboard-exposure-outcome`)

**Who decided what.** Benjamin, live conversation 2026-09-18: the existing
leaderboard "a été bâclé et ne reflète pas la cible voulue" and must be
redesigned entirely; its purpose is to make users challenge each other, like
Duolingo and comparable apps, to maximise engagement and learning;
"les leaderboards servent à comparer ce qui est comparable"; and the choice of
scope was explicitly handed to the PO in that same message ("Choisis pour
moi ... choisit le scope où appliquer"). Everything under "PO choice" below is
the PO session's call under that explicit delegation, not Benjamin's own
wording, and he may amend any of it at no cost before it ships.

**ADR-0015 §5b outcome: `mix`.** The takeover-derived global leaderboard is
removed; a new leaderboard is a wanted product capability, but scoped and
consented.

**PO choice — scope (what is comparable).**
1. The unit of comparison is **one collection inside one audience**: learners
   are ranked only against people practising the *same set of people*, because
   XP earned on a 25-president deck and on a 400-person organization are not
   the same effort.
   - *Public challenge board*: one board per public collection (V1: the French
     presidents), among account holders who joined it.
   - *Organization board*: one board per organization (access space), members
     only. Never across organizations; in a federated organization, per local
     access space, not the federation.
2. **No platform-wide board.** Nothing ranks all SayMyName users together.
3. **Weekly window.** The board ranks XP earned during the current ISO week on
   that scope's content and resets every Monday, so a newcomer can compete with
   a veteran (the Duolingo league mechanic, without promotion tiers in V1). A
   lifetime total may be shown to the learner alone.
4. **Score = real recall events only** on that scope's content (consistent with
   "never show invented progress"). No XP for opening the app.

**PO choice — consent and what is exposed** (class `identity_and_consent`).
5. Participation is **opt-in per board**, offered once at a natural moment
   (end of the first completed session on that scope), reversible at any time
   in settings; leaving removes the learner from the board immediately.
6. A board shows **display name, weekly XP and rank — nothing else**: never
   selections, errors, schedule, per-person results or `lastAnswerAt`.
7. An organization administrator sees a board **only as a participating
   member would**; there is no admin view of it and no export. A learner who
   has not opted in is invisible to everyone, administrators included.
8. `private-learning` stays in force for everything else. Its acceptance is
   amended to carve out exactly item 6 for learners who opted in.

**Delivery consequence.** Slice 1 (V1 blocker, it contradicts a V1 criterion):
`/api/leaderboard` and `/api/leaderboard/me` stop returning any cross-scope
data. Slice 2: the scoped, weekly, opt-in boards above, backend then frontend.
Tracked by product-queue candidate `af-9qn1q` (acceptance rewritten in EARS
form); decomposition is the Mayor's.

Reversal: the opt-in flag and the board endpoints are additive; removing the
capability again is a feature removal with no data migration. Re-opening the
scope choice costs nothing until slice 2 ships.

Supersedes the 2026-09-17 open entry (kept below for the finding itself).

<details><summary>2026-09-17 finding as raised</summary>

Raised, not decided: reserved `outcome` question (ADR-0015 §5b), produced by
the ADR-0021 existing-code review (`af-j41c2`) of the takeover-derived
`private-selection` capability.

Finding: `LeaderboardDao.getTop()`/`findTop()` (backend) and
`LeaderboardController`'s `/api/leaderboard` and `/api/leaderboard/me`
endpoints carry no tenant/organization scoping predicate — any authenticated
user can see every other user's display name, XP, rank and last-answer time,
platform-wide, regardless of organization. This is pre-existing
(takeover-derived) code, not something the Factory built for V1. It
contradicts the `private-learning` criterion's own acceptance text: "Un
administrateur d'organisation connecté au même environnement ne peut observer
ni les sélections, ni les erreurs, ni le planning, ni la progression
individuelle d'un apprenant." — XP/rank is a direct proxy for progress.

Recorded in `config/releases/saymyname-v1.json` as
`origin.conflicts.leaderboard-cross-org-exposure`, with reserved decision
`leaderboard-exposure-outcome` offering the three fixed ADR-0015 §5b options:
`keep_target` (tenant-scope the leaderboard — the reviewing tier's
recommendation, not its decision), `adapt_target` (amend `private-learning`'s
acceptance to knowingly exclude the pre-existing gamification leaderboard
from "progression"), or `mix`. Follow-up implementation work is queued as
product-queue candidate `af-9qn1q` under goal `af-u8id`, naturally blocked
until this decision lands.

This is the one genuinely open Product/Project question at this stage of
delivery; the sentence below no longer holds until it is resolved.

</details>

## Open

None. All Enterprise-tier questions are deferred — see `## Deferred`
below — and every other Product/Project question is either decided above or
does not exist yet at this stage of delivery.

## Deferred — Enterprise, until after V1 release

**2026-09-16, Benjamin, in conversation, with immediate effect.** Every
Enterprise-tier decision made so far — pilot recruitment ownership, the ITEEM
tester pool and its opt-in composition, the pilot's success contract, the
first paid-buyer/price test, and the brand/name review — is retracted, not
merely superseded. Benjamin's own assessment: most were answered by accepting
the first recommendation offered, or by a reply that did not really engage
the question, at a point in the project where none of them were yet
load-bearing. They are removed from active scope rather than kept as
decisions that happen to agree with what a later, more considered pass might
produce.

**Standing rule going forward:** no Enterprise-tier question — who recruits
or tests, pricing, buyer identity, brand/name — is raised, decided, or acted
on by the PO or the Mayor before V1 is released. This extends the existing V1
boundary that already deferred payment (`Frozen V1 product boundary`,
2026-09-14) to the whole Enterprise domain. Reopening this is Benjamin's act
alone, when the project is actually approaching that phase.

The seven retracted titles, for reference only — their full text is not
repeated here and remains recoverable from this file's Git history if ever
genuinely needed, but is not to be read as live or binding:

- Free student-cohort pilot before payment (2026-09-14)
- Dedicated private pilot environment and single feedback loop (2026-09-14)
- Pilot recruitment ownership deliberately unspecified in V1 (2026-09-15)
- ITEEM as the first tester pool (2026-09-15)
- Open opt-in for the first ITEEM cohort (2026-09-15)
- Balanced success contract for the first pilot (2026-09-15)
- First price test is a paid founding-organization pilot (2026-09-15)
- SayMyName remains the working name through the first pilot (2026-09-15)

## Superseded

### 2026-09-16 — Stale `## Open` list superseded by existing decisions

The `## Open` list carried seven items that already had `Accepted` decisions
above them and were never removed when those decisions landed, found stale
during an intake-protocol dry run: the first external connector, the first
tester pool, the pilot's success contract, the first buyer/price test, the
brand/name checkpoint, the pilot environment/feedback loop, the design
workflow threshold, and the product view architecture. Six of those eight
target decisions (all but the connector and the design-workflow choice) were
themselves retracted the same day — see `## Deferred` above — so the links
that once pointed to them are removed here rather than left dead.

Removed rather than left to mislead the next reading — an earlier session
(this one) nearly re-decided all seven from scratch before catching the
duplication.

### 2026-09-14 — Open Product question: Visibilité et conservation des groupes

Superseded by [Visibilité et conservation des
groupes](#2026-09-14--visibilité-et-conservation-des-groupes). The prior open
question was: “Décider la visibilité des profils, l’expiration du groupe et les
données d’apprentissage conservées après la fin d’accès.”

## Update rule

Add or amend an entry only after Benjamin approves or explicitly asks to record a
decision. If a new decision supersedes an old one, mark the old entry superseded
and link the replacement rather than silently rewriting history.

Every open decision belongs to exactly one domain: Enterprise decides market and
company outcomes; Product decides user value and behavior; Project decides how
the product is shaped and safely delivered. Do not duplicate one choice across
domains; link related decisions in the explanation instead.
