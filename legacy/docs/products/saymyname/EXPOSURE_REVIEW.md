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
| 2026-09-19 | `DECISIONS.md` Oxyl development data (updated 2026-09-20) | REMOVED on 2026-09-20: database rows, tracked files, git history of both repositories, local copies. What remains is listed under "Residual exposure" below | nobody | n/a | none for the history purge; the database is restorable from the encrypted backup |

## Residual exposure after the 2026-09-20 cleanup

Real people's data was removed everywhere the Factory controls. What is left,
and why it stays:

- **GitHub, server side.** `refs/pull/*` (back 45, front 25) and cached views keep
  serving the old commits until GitHub Support acts (ticket sent 2026-09-20). Old
  pull-request discussions may still name people.
- **GitHub-hosted CI runners** cloned both repositories before the purge; those
  clones are ephemeral and not controllable.
- **Agent and LLM session transcripts** displayed real file names in command
  outputs during earlier sessions and during the cleanup (local transcripts and
  provider side). The Factory cannot purge them.
- **Bead history (Dolt).** Earlier bead text (`af-guejb` gave file names as
  examples) stays in the Dolt history even after the description was sanitized.
- **Encrypted archives.** Three copies (workstation and external drive, gpg
  AES-256, passphrase in Benjamin's password manager) hold the real data by design,
  to be destroyed after the V1 release (PO recommendation).

## Before entering `piloted`

- [ ] Every row above reviewed by Benjamin, confirmed or amended.
- [ ] Every default that exposes anything to a second person is deliberate.
- [x] Oxyl development data removed from the database, the tracked files, the git
      history of both repositories and the workstation (2026-09-20); the history
      purge was decided and executed by Benjamin.
- [ ] GitHub Support has removed the old pull-request references (ticket sent
      2026-09-20). Check: the commits API must answer 404 for
      `ec69d4126dab0d23eff35c1b618b7845434d0e07` (back) and
      `fec807431d271b0e12a69ca2c73c845ea7dfe770` (front).
- [ ] The three encrypted archives are destroyed after the V1 release (PO
      recommendation, not a decision).
- [ ] The CEO's oral accord confirmed in writing, or the residual exposure below
      accepted by Benjamin.
- [ ] Withdrawal and correction paths work for a person who did not choose to
      be in the product.
- [ ] The stage line in `DESIGN_GOVERNANCE.md` is changed to `piloted` in the
      same act.
