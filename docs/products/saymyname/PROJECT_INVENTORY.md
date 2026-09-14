# SayMyName project inventory

Refreshed 2026-09-14 from product status, Beads, the product queue, merged Backend
PR #34, merged Frontend PR #46 and their green CI evidence. A route or API surface
proves code exists; it does not by itself prove a complete, usable or released
customer journey.

## Frozen baseline — 2026-09-14

- Delivery is idle: no current outcome and no current agent.
- Last delivered outcome is `af-u8id.1`, the anonymous public-challenge and
  minimal personal-home foundation. Backend PR #34 merged as `1ee99155` and
  Frontend PR #46 as `7adb96b6`; exact-head, post-merge and integrated product
  validation are recorded green in the outcome Bead.
- The delivered catalogue proof is U.S. Founding Fathers. It does not satisfy the
  accepted France-first French-presidents collection decision; candidate
  `af-3ytx` now records that missing V1 result.
- Next eligible product outcome is `af-hxji`, the participative
  promotion/event/community journey. It remains deferred until Benjamin + PO
  approve or amend its design-ready navigation, admission, consent, visibility
  and revocation contract.
- The ordered V1 core after the delivered foundation is `af-hxji`, `af-3ytx`,
  `af-9hqe`, `af-ccvr`, then `af-k8we`. Retrieval `af-8u63`, external connector
  `af-ox36`, federation `af-9wy2` and pricing/launch `af-nynt` remain paused,
  evidence-gated extensions.
- `af-cm1l` is an eligible Factory campaign-mode improvement after the product
  candidates. It is intentionally outside the SayMyName product V1.

This is an audit snapshot, not a substitute for live status. Gas City, Beads,
GitHub and the product queue remain authoritative after this timestamp.

## View catalogue

| Product area | Observed code surfaces | Product assessment |
|---|---|---|
| Access | sign in, sign up, email verification, password recovery | Existing foundation; preserve and simplify |
| Invitation and onboarding | invitation preview/acceptance, onboarding | Existing and recently hardened; validate the complete first-session path |
| Learning | training options, course, course hub, quiz, progress APIs | Existing core engine; reconnect it to the new personal home |
| People | trombinoscope, profile, person search, subscriptions | Existing organization-oriented capability; adapt to explicit personal selections |
| Organization admin | dashboard, people, members, invitations, attributes, change requests | Broad existing surface; keep behind scoped roles and do not make it the universal home |
| Public challenge | anonymous catalogue/play/feedback routes plus versioned Backend content, rights, receipt and withdrawal contracts | Foundation delivered; France-first French-presidents content still queued |
| Personal home | independent home, explicit saved selections, due reviews and private progress backed by persisted attempts/schedules | Minimal V1 foundation delivered; reconnect broader existing learning sources incrementally |
| Participative groups | partial organization/invitation primitives | Next product outcome; dedicated journey still missing |
| Administered import | no complete CSV customer journey observed | Queued after participative journey and France-first catalogue |
| Personal import | public-challenge save exists; no general personal CSV/import journey observed | Queued after administered import |
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
