# ADR-0017: Four conditions every factory improvement must meet

- Status: Accepted
- Date: 2026-09-16
- Decided by: Benjamin, in conversation, 2026-09-16, stated as a standing rule
  and not as an instruction for one session: « et ça c'est la règle pour toutes
  les améliorations usines ».
- Applies to: every change to the factory itself — `bin/`, `lib/`, `city.toml`,
  orders, packs, guards, agent configuration, host configuration. It does not
  govern product delivery inside a rig, which `DELIVERY.md` covers.

## Context

The factory improves itself faster than any human can audit it, and the changes
that matter most are precisely the ones nobody watches. Three failures from the
same week make the shape of the problem concrete.

A guard reported `✓ work-backup — nothing exists only on this machine` while
twenty entries, including two Accepted ADRs, existed nowhere else. It had only
ever compared `refs/heads/` to origin and had never looked at the working tree.
Nobody doubted it, because it was green.

CI enumerated its test files by hand. The list had drifted to seven of fourteen:
five suites that pass on a bare runner had simply been forgotten. A test that is
never invoked cannot fail, so the gap reported itself as silence.

The periodic Dolt maintenance loop existed, worked, and had never been enabled.
Compaction therefore happened only when a human noticed the store growing — and
a single clean shutdown reclaimed 132 MB that had been sitting there.

Each of these is the same failure in a different costume: something was
*asserted* rather than *verified*, or was left depending on a human remembering.
Neither shows up in a diff review.

## Decision

Every factory improvement must satisfy all four conditions. They are not a
checklist to tick at the end; a change that cannot meet them is not ready.

### 1. Verified, not asserted

You prove it works against the live system, and you say what you observed. "It
should now do X" is not evidence. A test that exercises the fixed path is the
normal form of proof; a before/after observation on the running factory is
stronger and is preferred when the state can only exist transiently.

Corollary: when you change a check, prove it still fails when it should. A fix
that quiets an alarm without preserving the alarm is a regression wearing the
costume of a fix.

### 2. It must increase autonomy

Fewer human interventions after the change than before. A change that adds a
step somebody must remember has failed this condition even if it works.

This is why a guard that merely *reports* unsaved work is worth less than one
that *saves* it, and why enforcing a rule mechanically beats documenting it.
When a change cannot remove a human step, say so explicitly rather than letting
the reader assume it did.

### 3. It must optimise something

Resources, tokens, or human time — name which one and by how much. A change that
optimises nothing and adds surface area needs a different justification.

### 4. It must be documented for BOTH audiences

Two distinct readers, and satisfying one does not satisfy the other:

- **Agents**, who need to find it without being told: root `AGENTS.md`, an entry
  in `docs/CONTEXT_INDEX.md`, versioned files under `docs/`. A document no index
  points at does not exist.
- **Humans**, who need it readable and findable — in French when the intended
  reader is Benjamin, which is the case for anything he operates himself.

A commit message is documentation for whoever reads that commit, which is
nobody. Durable facts go in Git, per the authority order in `CONTEXT_INDEX.md`.

## Consequences

- An improvement that fails any of the four is incomplete, not merely imperfect.
  Finish it or state plainly which condition you did not meet and why — scaling
  the work down is Benjamin's call, not the agent's.
- Reviews of factory changes check these four explicitly.
- Condition 1 makes "I fixed it" an unacceptable report on its own. Every claim
  of a fix carries its evidence.
- Condition 4 means a change lands with its index entry in the same commit, not
  in a follow-up that never comes.

## Evidence from the session that produced this ADR

All four conditions were applied to the 2026-09-16 maintenance work:

| Change | Verified by | Autonomy gained |
|---|---|---|
| `factory-guard` sees the working tree | `tests/factory-guard-dirty-tree-test.sh`, plus the live blind spot reproduced | unsaved work reaches origin with no human |
| CI registration enforced | `tests/ci-registration-test.sh` | a new test can no longer be silently unprotected |
| Planned window ≠ dead controller | observed live on both sides of the fix, plus a fixture test asserting the real alarm still fires | a deliberate stop no longer triggers an investigation |
| Off-box archive backup | `gc doctor` moved from `⚠ local-only` to push mode, then a real push verified | store exports leave the machine every 15 min |
| `[maintenance.dolt] enabled` | `gc maintenance status` shows the loop scheduled | compaction stops depending on somebody noticing |

## Related

- ADR-0016 — standing delegation; an escalation must never stop the campaign.
- ADR-0015 — declared autonomy and reserved questions.
- `docs/RUNBOOK_STOP_AND_RESTART.md` — the procedure this session produced and
  verified, and the worked example of condition 4.
