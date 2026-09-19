# Exposure ledger — read once, before the first real cohort

Stage: **`pre_production`** (declared in `DESIGN_GOVERNANCE.md`, 2026-09-16).

While the **deployed** product holds no real personal data about third parties,
a decision that widens who can see personal data does not escalate. It is
taken, recorded in `DECISIONS.md` like any delegated decision, and **appended
here**. (Correction 2026-09-19: the development database and the two private
repositories DO hold real people's data — Oxyl members' trombinoscope, for
development only, on the CEO's oral accord — see `DECISIONS.md`
2026-09-19. That data must never reach a deployed product, a build, a proof or a
fixture.)

This file exists because the visibility defaults written during development are
the defaults the first real cohort will meet, and nobody re-reads them at
launch. Entering stage `piloted` is an escalation whose single precondition is
Benjamin reading this file in one pass and confirming or amending each line.

One human review, at the moment it becomes load-bearing — instead of one
interruption per decision now, when nothing is at stake.

## How to append

One row per decision that widens visibility. Keep it short enough to review
fifty of them in one sitting.

| date | decision ref | what became visible | to whom | default on/off | reversal |
| --- | --- | --- | --- | --- | --- |

## Entries

_No widening decision yet. The seven `af-hr1v` decisions of 2026-09-16 widened
nothing: the sole reader of an imported personal contact is the importing
person._

| date | decision ref | what is held | by whom | default | reversal |
| --- | --- | --- | --- | --- | --- |
| 2026-09-19 | `DECISIONS.md` Oxyl development data | ~246 named photos and trombinoscope data of real people, in the dev database and (until `af-ldvic` lands) tracked in both private repositories | Benjamin's development environment only; never shown to a user | development and test only, never published | untrack (`af-ldvic`); history purge is a separate, irreversible pre-release decision |

## Before entering `piloted`

- [ ] Every row above reviewed by Benjamin, confirmed or amended.
- [ ] Every default that exposes anything to a second person is deliberate.
- [ ] Oxyl development data: the CEO's oral accord confirmed in writing (or the
      data removed), and the git-history purge decided by Benjamin.
- [ ] Withdrawal and correction paths work for a person who did not choose to
      be in the product.
- [ ] The stage line in `DESIGN_GOVERNANCE.md` is changed to `piloted` in the
      same act.
