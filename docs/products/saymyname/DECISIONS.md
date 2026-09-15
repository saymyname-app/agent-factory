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

### 2026-09-14 — Free student-cohort pilot before payment

The first accessible validation target is a new adult student cohort reached
through Benjamin's former school administration or student association. The
pilot is free, requires no payment method and tests onboarding, delayed recall,
return and real-interaction usefulness. Payment implementation and exact pricing
wait for evidence and buyer conversations.

### 2026-09-14 — Dedicated private pilot environment and single feedback loop

The first student pilot runs on a dedicated, private and stable environment,
separate from both technical staging and public production. It has an identifiable
pilot URL, access restricted to the invited cohort and controlled changes during
the observation period. The exact hostname remains an implementation choice.

Testers use one short feedback form as the canonical channel, reachable from the
product and pilot communications, with email as a fallback rather than parallel
informal channels. The previous assignment of recruitment and collective relays
to a school sponsor is superseded by [Pilot recruitment ownership deliberately
unspecified in V1](#2026-09-15--pilot-recruitment-ownership-deliberately-unspecified-in-v1)
below. Benjamin is the named SayMyName support owner and remains accountable for
replies and triage. An LLM may assist him later, but this is optional support
rather than a transfer of responsibility or a prerequisite for the first pilot.

Ordinary feedback is grouped for analysis without promising an immediate change
for every suggestion. Any suspected personal-data exposure, unauthorized access
or defective consent suspends the affected journey conservatively and triggers
technical escalation before it is reopened.

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

### 2026-09-15 — Pilot recruitment ownership deliberately unspecified in V1

V1 does not designate the former school's administration, its student
association or another sponsor by default to own recruitment and distribution
for the first pilot. Benjamin and the school will choose the appropriate owner
and channel together when preparing the V1 pilot, based on the actual counterpart
and conditions at that time. They may adjust that arrangement later if needed;
this operational choice does not change the V1 product boundary.

### 2026-09-15 — ITEEM as the first tester pool

The first pilot recruitment pool is Benjamin's former school, ITEEM. Cohorts
contain about 65 students; because some year groups are away on internships, the
working assumption is that two or three cohorts will be reachable at school and
that one cohort will be especially interested. Pilot planning therefore uses an
initial reachable pool of about 100 people, with 300 as an absolute upper bound.

These figures estimate people who may be invited, not consented or active
testers. A later extension to the wider Centrale Lille population remains an
option if the ITEEM pilot justifies broadening recruitment; it is not part of the
first cohort by default.

### 2026-09-15 — Open opt-in for the first ITEEM cohort

The first ITEEM pilot is open to every adult student in the confirmed reachable
pool rather than being hand-picked in advance. The invitation uses one common,
clear message through the relay agreed with ITEEM, explains the pilot commitment
and personal-data use, and requires each tester to opt in explicitly. Silence,
presence in an existing contact base and receipt of the invitation never count as
consent.

The recruitment target is **25 consented testers**, sought across the reachable
year groups during a defined enrolment window. If more than 25 volunteer, the
pilot may include up to **30**, prioritizing a useful spread across those year
groups rather than speed of response alone. If fewer volunteer, the pilot keeps
the actual volunteers and records the shortfall as recruitment evidence; it does
not pressure students or silently broaden recruitment beyond ITEEM. The exact
names, reachable pool size, invitation relay and dates are confirmed when the
pilot is prepared, without reopening this composition rule.

### 2026-09-15 — Balanced success contract for the first pilot

The first ITEEM pilot has a one-week enrolment period followed by four weeks of
observation. Its conclusions are judged against the following thresholds fixed
before observation begins:

- at least **15 activated testers**;
- at least **60% activation** among people who start registration, where
  activation means completing their profile, selecting people to learn and
  completing a first learning session;
- at least **50% return** among activated testers, measured by completing another
  learning session at least seven days later;
- a median improvement of at least **20 percentage points in delayed recall**
  between the first attempt and a comparable check at least seven days later;
- at least **40% reported real-life usefulness** among testers who had a relevant
  interaction opportunity, meaning SayMyName helped them at least once;
- **no serious privacy, consent or unauthorized-access incident**.

The pilot supports continuation when all thresholds are met and no serious
incident occurs. It supports correction followed by another test when the sample
is insufficient, or when only one quantitative threshold misses by fewer than ten
percentage points and an identifiable cause can be addressed. The value
proposition is reconsidered when both delayed recall and real-life usefulness
remain weak despite satisfactory activation.

This contract validates initial user value, not pricing, the identity of the
buyer or acquisition at scale. Those require separate evidence.

### 2026-09-15 — First price test is a paid founding-organization pilot

The first paid-buyer profile is not tied in advance to a named institution or
sector. It is the first qualified sponsor reached at a school or employer who has
a concrete need to help a bounded cohort learn one another, can judge the outcome
and has access to the relevant budget. Benjamin's former school, another school
and his former ESN are all valid routes; an interested learner without buying
authority is not the first-buyer test.

The free ITEEM cohort pilot remains free and does not require a payment method.
Once there is enough usage evidence to present the outcome credibly, the first
price test is one real, written founding offer: **EUR 1,500 excluding tax for
three months and up to 100 invited learners**, covering one organization cohort,
assisted onboarding and an outcome review. The price is a test, not the final
tariff. Success requires a signed order or payment; a budget holder's written
commitment blocked only by normal procurement is directional evidence, while a
hypothetical “I would pay” is not. A refusal and its stated reason are retained as
evidence before changing the price or package.

An optional donation may later coexist with the free personal experience, but it
is not the first price test and is not treated as evidence of product willingness
to pay. Consumer Premium remains a later evidence-gated offer for recurring user
value; SayMyName does not design consumable spending or “whale” mechanics around
a small number of disproportionate spenders.

Evidence considered: RevenueCat's 2026 dataset reports a 2.1% median
download-to-paid conversion for freemium subscription apps, an Education annual
price median of USD 44.99, and materially different iOS and Android conversion;
an approximately 100-person pilot would therefore provide a weak consumer price
signal. A meta-analysis of 77 willingness-to-pay studies estimates average
hypothetical bias at 21%, supporting a real offer over a stated-price survey.
Pay-what-you-want field experiments also show that voluntary pricing can measure
fairness and self-image and can reduce purchase participation. Sources:
[RevenueCat 2026](https://www.revenuecat.com/state-of-subscription-apps),
[Schmidt and Bijmolt (2020)](https://doi.org/10.1007/s11747-019-00666-6), and
[Gneezy et al. (2012)](https://doi.org/10.1073/pnas.1120893109).

### 2026-09-15 — SayMyName remains the working name through the first pilot

SayMyName remains the product's working name through the first pilot rather than
being treated now as either a definitive public brand or a name that must be
changed on intuition alone. During this period it is accompanied by a short
descriptive promise conveying the broader value, such as helping people retain
faces, names and useful context; the exact wording may evolve without reopening
the naming decision.

The name and positioning are reviewed after the pilot using evidence in three
areas: user understanding of the proposition, trust and comfort with the framing,
and relevance to prospective buyers. A change is justified by repeated
misunderstanding, a recurring trust objection, a material commercial mismatch,
or a serious legal or digital availability obstacle, not by an isolated naming
preference. Legal and digital availability must be checked before material public
brand investment and may force an earlier change.

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


## Open

### Enterprise

- **Responsable et canal du premier pilote** — Choisir si l’administration de l’ancienne école, l’association étudiante ou un autre sponsor porte le recrutement et la diffusion.
- **Première cohorte de testeurs** — Définir le premier vivier nominatif, sa taille cible, les critères et la manière d’inviter les testeurs consentants.
- **Contrat de réussite du pilote** — Fixer durée et seuils de succès avant l’observation afin de ne pas redéfinir le résultat après coup.
- **Premier acheteur et test de prix** — Identifier le premier profil acheteur et le premier entretien, test d’offre ou de volonté de payer; le pilote gratuit ne répond pas seul à cette question.
- **Point de contrôle marque et nom** — Décider à quel niveau de preuve conserver ou faire évoluer le nom et le positionnement SayMyName.

### Product

- **Premier connecteur externe** — Choisir Google, Microsoft, les contacts natifs ou une autre source uniquement selon les frictions observées et la faisabilité fournisseur.

### Project

- **Architecture des vues produit** — Valider l’inventaire complet des vues et l’ordre de conception puis livraison des parcours manquants.
- **Socle du workflow design** — Confirmer une gouvernance design-system code-first et le seuil à partir duquel un prototype Figma devient utile.
- **Environnement pilote et boucle de retours** — Choisir l’URL ou environnement pilote, le canal de retour, le responsable support et le chemin d’incident avant le recrutement.

## Superseded

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
