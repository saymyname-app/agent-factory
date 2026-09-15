# SayMyName project inventory

Reviewed 2026-09-14 from the React router, frontend feature folders, backend HTTP
controllers, product strategy, Beads and GitHub delivery evidence. A route or API
surface proves code exists; it does not by itself prove a complete, usable or
released customer journey.

## View catalogue

| Product area | Observed code surfaces | Product assessment |
|---|---|---|
| Access | sign in, sign up, email verification, password recovery | Existing foundation; preserve and simplify |
| Invitation and onboarding | invitation preview/acceptance, onboarding | Existing and recently hardened; validate the complete first-session path |
| Learning | training options, course, course hub, quiz, progress APIs | Existing core engine; reconnect it to the new personal home |
| People | trombinoscope, profile, person search, subscriptions | Existing organization-oriented capability; adapt to explicit personal selections |
| Organization admin | dashboard, people, members, invitations, attributes, change requests | Broad existing surface; keep behind scoped roles and do not make it the universal home |
| Public challenge | no complete public journey observed | In delivery now |
| Personal home | no stable independent home observed | In delivery now |
| Participative groups | partial organization/invitation primitives | Next product outcome; dedicated journey still missing |
| Imports | no complete CSV customer journey observed | Planned after group foundation |
| Editorial catalogue | no scoped writer/publisher journey observed | Planned |
| Intelligent retrieval | person search exists, natural-language authorized retrieval not observed | Planned after product evidence |
| Commercial | no offer/pricing/billing journey required for free pilot | Deferred until buyer evidence |

## Functional capabilities already present

- Authentication, session and account recovery.
- Invitations, organization membership and scoped administration.
- Person/profile data, photos, attributes, subscriptions and search primitives.
- Quiz/course lifecycle, answers, help, statistics, performance and leaderboard.
- Administrative change requests and member/person management.

## Tracking rule

The versioned catalogue is the reviewed baseline. Live delivery status is derived
from Beads, Gas City and GitHub. A lightweight deterministic check may compare
declared repository HEAD journals with this review; an AI review is event-triggered
only after a material feature merge or explicit PO request, never on every
cockpit refresh.
