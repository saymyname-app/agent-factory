# SayMyName social-memory product strategy

This document is durable product strategy. It separates accepted direction from
delivery state. Gas City, Beads, Git and GitHub remain authoritative for live
execution.

## Product thesis

People often recognize a face, remember context about the person, yet fail to
retrieve the proper name. That failure is socially meaningful: remembering can
signal attention and belonging, while forgetting can create embarrassment or a
feeling of being unseen. SayMyName helps a learner decide whose identity and
which useful details deserve internal memory, then practices retrieval before the
next real interaction.

The durable loop is:

```text
public challenges ---------+
organizations -------------+--> personal selection --> learn and review
personal additions --------+             |                    |
                                          +--> real encounter <-+
```

The phone is both a safe external store and a trainer. The goal is not to retain
everything or condemn digital tools; it is to internalize selected information so
the user does not need to consult the phone during the interaction.

## Evidence and claim boundaries

Research supports that proper names are unusually difficult to retrieve, and
that active retrieval with feedback and spaced practice can improve retention of
trained face-name associations. It also supports a social effect in context:
students who believe an instructor knows their name report stronger belonging,
and using a name can improve rapport but can backfire when incorrect, excessive
or embarrassing.

SayMyName may claim that it helps users practice and retain the people actually
trained. It must not claim without product-specific evidence that it improves
general intelligence, prevents cognitive decline, treats social anxiety or
automatically makes someone socially skilled.

Primary research references:

- Hanley and Kay, proper-name retrieval difficulty:
  https://pubmed.ncbi.nlm.nih.gov/9534002/
- Morris et al., retrieval practice and semantic association for names:
  https://onlinelibrary.wiley.com/doi/pdf/10.1002/acp.1115
- Carpenter, Pan and Butler, spacing and retrieval practice:
  https://doi.org/10.1038/s44159-022-00089-1
- Cooper et al., instructors knowing student names:
  https://pubmed.ncbi.nlm.nih.gov/28188281/
- Name use, rapport and discomfort in service interactions:
  https://www.sciencedirect.com/science/article/pii/S0022435926000278
- Sparrow, Liu and Wegner, external/transactive memory:
  https://pubmed.ncbi.nlm.nih.gov/21764755/
- Risko and Gilbert, cognitive offloading:
  https://discovery.ucl.ac.uk/id/eprint/1508770/
- Melby-Lervag et al., limits of broad transfer from memory training:
  https://pmc.ncbi.nlm.nih.gov/articles/PMC4968033/

## Four memory jobs

| Job | User outcome | Product behavior |
|---|---|---|
| Recognize | Know that a face is familiar and where from | Visual exposure with varied authorized images when available |
| Recall | Retrieve a name, pronunciation, role or chosen context | Attempt before reveal, correction and spaced review |
| Prepare | Refresh the people expected at a class, meeting or event | User-selected or group-scoped short session |
| Remind or look up | Recover a date, promise, phone number or other fact | Timely reminder or search; memorization only when explicitly selected |

Success happens outside the app. Time spent, streaks and number of stored contacts
are secondary metrics and must not replace delayed recall or reported usefulness
in a real encounter.

## Personal home

The personal home is the stable entry point after authentication. It contains:

- `Today`: due reviews, chosen preparations and relevant source updates.
- `My learning`: the exact people and fields selected by the learner.
- `Sources`: public challenges, organizations and personal additions.
- `My people`: search and private context for people the learner may access.
- `Progress`: evidence by field and exercise mode, never a vague global mastery.

An account is optional for an initial anonymous public challenge and required to
save progress, add people, create or join a private group, or import data.

## People and access model

The product must keep these concepts separate:

- A person/profile is content that may be learned.
- A user account authenticates an individual.
- A membership grants access to a group or organization.
- A personal selection points to authorized content and holds private learning
  state.
- A payer funds an offer and need not be the learner or profile subject.
- A source owns or supplies facts and their lifecycle.

Profiles from separate sources are not merged on name alone. Homonyms remain
separate, identity suggestions cannot reveal hidden profiles, and a person import
does not silently create an account or invitation.

Losing organization access stops new consultation and review of its protected
content. The exact retention of private attempt statistics must be minimized and
documented; it may not preserve source fields or media as an uncontrolled copy.

## Organization archetypes

Only three archetypes are needed. Onboarding asks understandable questions about
purpose, admission, source and duration; it does not expose these internal names.

| Archetype | Typical uses | Population | Admission | Data authority | Commercial unit |
|---|---|---|---|---|---|
| Participative group | Student cohort, party, event, club, durable community | Participants create or verify profiles | Link/QR, open, approval or invitation | Participant plus organizer rules | Group and period, or recurring community |
| Administered organization | School, association, company | Admin imports and maintains people | Nominative invitation or approved membership | Organization, with participant correction | Published population band |
| Federated organization | Large school/company, multiple divisions | Central directory plus delegated spaces | Enterprise identity and assignments | Central and field-level source rules | Annual contract, governed population and integrations |

Size alone does not select an archetype. A large open community may stay
participative; a smaller regulated company may need federation. A team is a
learning/filter grouping. A workspace is an access boundary. They are not
synonyms.

## Initial school pilot

The first accessible pilot is an adult student cohort reached through Benjamin's
former school administration or student association.

Initial path:

1. An organizer creates a private promotion.
2. They configure duration, admission and profile visibility.
3. A revocable link or QR code is distributed by the organizer.
4. Students create accounts and voluntarily create or verify their profile.
5. Each learner chooses people from the promotion.
6. A short session attempts recall, gives the correct answer and schedules later
   review.
7. Aggregate adoption may be visible to the organizer; individual choices,
   answers and errors are not.

The pilot is free, needs no payment method and exists to validate activation,
delayed recall, return and reported real-life usefulness. It does not prove who
will pay. Administration, student association and individual willingness to pay
must be tested separately.

## Public challenges

Public challenges use recognizable public figures and are both a real consumer
use and an acquisition path. They are not fake organizations and should be
presented as `Challenges` or `Collections`.

The V1 public demo targets France first while keeping the format reusable
internationally. It starts with one French-presidents collection. Each additional
national audience deliberately supported initially gets at most one collection,
showing that country's presidents when applicable and available. Country
selection and fallback behavior remain implementation choices. The catalogue and
editorial path must make later sets easy to add without requiring broad
international coverage in V1. Every set still depends on editorial usefulness
and portraits that can be lawfully reused.

Anonymous visitors can play a short challenge. They create an account only to
save progress, continue scheduled reviews, add other sources or create a group.
Sharing emphasizes improvement without publishing individual mistakes.

Every published profile needs provenance, factual source, image author, license,
original URL, transformations and verification date. Public visibility of a
person or photo does not by itself authorize commercial reuse.

Use a narrowly scoped editorial workflow:

- Writer: create and preview drafts.
- Publisher: verify provenance/rights, publish and withdraw versions.
- Organization admin: no public-catalogue privilege.
- Support/operations: no implicit ability to read private learning or personal
  notes.

Do not build an omnipotent global super-admin as the convenience path. Even when
Benjamin initially holds both editorial roles, permissions remain distinct and
server-enforced.

Relevant current guidance:

- Wikimedia Commons reuse and attribution:
  https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia/licenses
- French government guidance on image and author rights:
  https://www.economie.gouv.fr/apie/droit-limage-des-personnes-et-des-biens

## Imports

Import is not a back-office extra; it determines whether a learner reaches value
before abandoning. The common path is:

1. Choose destination and source.
2. Authorize or upload.
3. Select people and fields.
4. Map columns or source properties.
5. Preview omissions, errors and possible duplicates.
6. Confirm an idempotent import into draft/controlled visibility.
7. Separate profile publication, account creation and invitation.
8. Reach the first useful learning selection.

V1 starts with CSV for personal and organization destinations. It must support
mapping, preview, error download, idempotent replay, conservative duplicate
handling and explicit missing-photo state. Corrections and private notes are not
silently overwritten.

Later candidates, selected by customer evidence:

- vCard or native contact selection;
- Google Contacts and Microsoft Outlook contacts for personal use;
- Google Workspace or Microsoft Entra for organizations;
- HRIS and continuous synchronization for federated organizations.

LinkedIn relationship access is restricted to approved developers; Meta access
does not provide a dependable general friends import; X introduces paid API
dependency. Social-network imports must therefore not gate V1 or appear as
promised capabilities before provider access and terms are verified.

OAuth from the account owner authorizes an API call; it does not automatically
settle the lawful treatment of every third party in the returned data. Each
connector needs minimal scopes, a clear destination, retention and revocation
behavior, and an explanation visible to the importer.

Current platform references:

- Google People API: https://developers.google.com/people/api/rest/v1/people.connections/list
- Microsoft Graph users: https://learn.microsoft.com/en-us/graph/api/user-list?view=graph-rest-1.0
- LinkedIn Connections API restrictions: https://learn.microsoft.com/en-us/linkedin/shared/integrations/people/connections-api
- CNIL guidance on reuse of public Internet data:
  https://www.cnil.fr/fr/recommandations-reutilisateurs-donnees-internet

## Intelligent retrieval

The planned promise is: `Find someone among the people I may access from the
fragments I remember.` Example: `the marketing person in Lyon working on Atlas`.

The first version should search an explicitly selected scope over authorized
names, aliases, groups, roles, locations, projects, tags and short allowed
context. It returns a few candidates and explains each using fields that actually
exist. It asks for another clue or abstains when evidence is insufficient.

Access filtering occurs before any external model receives records and also
applies to indexes, caches and derived data. Private notes stay private. Deleted
or revoked content disappears from search. The feature does not identify a
person from a camera image, infer sensitive traits or fabricate confidence.

## Offers and payment hypothesis

Payment is deferred for the initial pilot. The eventual offer family follows the
three organization archetypes without multiplying onboarding choices:

| Offer | Initial value | Likely pricing basis |
|---|---|---|
| Personal | Public challenges and private social-memory practice | Freemium, later consumer subscription hypothesis |
| Group | Promotion, event or community | Group and period, or recurring subscription |
| Organization | Managed population and import | Published population band |
| Enterprise | Federation, governance and synchronization | Annual negotiated contract |

`Personal` is not a fourth organization archetype. Exact limits and prices remain
open until the free pilot produces usage evidence and buyer conversations.

## Product roadmap

The roadmap is a sequence of customer outcomes, not engineering tickets. The
frozen V1 baseline adopted on 2026-09-14 is:

1. **Delivered foundation** — public cultural challenge playable anonymously,
   account save and minimal personal learning home. The shipped proof currently
   uses a U.S. Founding Fathers collection; it proves the reusable format but does
   not satisfy the later France-first catalogue decision.
2. **Pilot-ready participative journey** — promotion/event/community creation,
   join link or QR, voluntary claimed profiles, private learning selection,
   revocation and aggregate-only organizer adoption.
3. **France-first public catalogue** — one verified French-presidents collection
   using the delivered challenge foundation.
4. **Administered organization path** — organization creation and CSV import
   through the first useful quiz.
5. **Personal import path** — personal people import and chosen contextual
   memory.
6. **Sustainable public publishing** — safe editorial creation, versioned
   publication and withdrawal of challenges.

Items 1–3 form the pilot-ready V1 boundary. Items 1–6 form the complete V1 core.
The exact candidate order is stored in the product queue; at this baseline it is
2, 3, 4, 5, then 6 after the delivered foundation.

The following remain ordered, visible, evidence-gated extensions rather than V1
completion criteria:

7. Natural-language retrieval among authorized people.
8. First external people connector chosen from pilot evidence.
9. Federated organizations with governed workspaces, delegated administration,
   synchronized lifecycle and enterprise identity.
10. Evidence-based pricing and launch readiness.

Evidence-gated items may remain paused in the product candidate queue. The Mayor
owns decomposition into executable Beads and delivery order within each
materialized outcome. The separate campaign-mode candidate improves Factory
operation and is not part of the SayMyName roadmap.

## Measurement

Measure the complete value path:

- challenge start, completion, improvement, save and share;
- explicit person/field selection followed by a first recall attempt;
- delayed recall by exercise type, not just multiple-choice recognition;
- second useful session, without treating episodic usage as failure;
- time and abandonment from source to usable people;
- reported help, no effect or discomfort after a real encounter;
- group profile completion and member activation;
- transition from public challenge to personal or organization use;
- confidence about who can see profiles and learning data;
- access leaks, stale content and failed revocation as launch-blocking failures.

Initial numeric thresholds are intentionally not invented. They must be agreed
before each pilot so results cannot redefine success after the fact.

## Explicitly deferred or prohibited by default

- No facial recognition from a camera or ambient identification.
- No inference of sensitive traits or automatic dossiers about third parties.
- No organization visibility into individual mistakes or learning selections.
- No promises of broad brain, therapeutic or intelligence improvement.
- No unrestricted social-network scraping.
- No automatic cross-organization identity merge.
- No payment implementation before the free pilot needs it.
- No complex nested workspace hierarchy without an engaged customer need.

## Human decisions still required

The authoritative, categorized list is the `Open` section of `DECISIONS.md`.
It deliberately separates company choices (market, testers, buyer), product
choices (user behavior and scope), and project choices (delivery, views and
design). The cockpit projects that list without asking a model.
