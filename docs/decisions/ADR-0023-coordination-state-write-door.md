# ADR-0023: Coordination state is written through one door, never by hand

- Status: Accepted
- Date: 2026-09-18
- Decided by: the PO session (Claude), under ADR-0016 standing delegation
  and Benjamin's instruction of 2026-09-18: "il vaut mieux revoir la big
  picture plutôt que réparer les détails à chaque fois" — for every
  finding, ask why the system allowed it, and automate what is normal.
- Extends: ADR-0016 (delivery proof fields), ADR-0022 (live root).
- Implements via: factory-lane candidate "ADR-0023 write door" (see below).

## Context — four incidents, one cause

In 48 hours the Factory stopped four times, each time because a WRITER put
a wrong, missing or prose value in a `gc.*` field on a Bead and a READER
died on it, taking the whole status projection — and with it the campaign
— down:

| when | field | what was written | by whom |
|---|---|---|---|
| 2026-09-16 | six delivery proof fields | nothing (raw `gc bd close`) | a worker |
| 2026-09-17 21:08Z | `gc.next_outcome` | stale title after a materialize | nobody updates it: it is prose |
| 2026-09-18 23:53Z | `status` of two queue candidates | `in_progress`/`open` by hand | a PO session |
| 2026-09-18 02:40Z | `gc.current` | `"af-smmwz / smb-99wi — Stop cross-org…"` | the Mayor |

Plus two "labels applied by hand" cases the same day (`product-queue` on
ordinary beads → false BLOQUÉ; `product-goal` on review tasks → a proof the
guard could never obtain).

The 2026-09-18 audit of every `gc.*` key (writer, reader, failure mode)
shows the pattern precisely:

- Every state that has a **door** — `bin/product-queue` for `gc.queue_*`,
  `bin/mayor-campaign` for `gc.campaign_*`, `bin/deliver-close` for the six
  proof fields — was never corrupted *through* the door. It was corrupted
  **around** it: raw `gc bd update/close`, or a prompt telling an agent to
  set a field by hand.
- The pointers on the coordination root (`gc.current`, `gc.current_jit`,
  `gc.last_delivered`, `gc.next_outcome`, `gc.needs_benjamin`,
  `gc.blocked_reason`, `gc.resume_*`) have **no door at all**: `docs/
  OPERATIONS.md` and the Mayor prompt tell the Mayor to set them by hand.
- Readers were fail-closed by design ("never show a wrong state"). Since
  2026-09-17 they are being converted one by one to "degrade the section,
  warn, keep the projection" (product-status, product-queue list, cockpit).
  That is the right read-side rule, but it only limits the blast radius; it
  does not stop the corruption.

Each repair so far was a PO session hand-editing the Bead — which is itself
another hand-write.

## Decision

1. **Every semantic write goes through a door.** A door is a script that
   validates ids, checks the transition, writes all the fields of the
   transition together, and records who asked. The doors are:
   - `bin/product-queue` — candidates (existing; `mayor-campaign` must stop
     writing `gc.queue_state` directly and call a new `quarantine`
     subcommand);
   - `bin/mayor-campaign` — campaign fields (existing);
   - `bin/deliver-close` — the six proof fields (existing; `mol-do-work`
     must stop writing `gc.work_outcome` itself);
   - **new `bin/campaign-pointer`** for the coordination root:
     `start <bead>` (sets `gc.current` and `gc.current_jit` to that id after
     checking it exists and is open/in_progress), `finish <bead>` (moves it
     to `gc.last_delivered` only if `deliver-close` proof is present, sets
     current to `none`), `escalate <bead> "<reason>"` (sets
     `gc.needs_benjamin` + notes + mails human in one go — the escalation
     contract as code, not as four prompt lines), `clear-decision`.
     `gc.next_outcome` is retired: the queue is authoritative, the field is
     removed from the reader after one release of warnings.
2. **Pointer fields hold one bead id or `none`.** Titles live on beads.
3. **Semantic labels are set by doors too**: `product-queue` sets
   `product-queue`; `deliver-close`/the campaign sets `product-goal`. A label
   found on a bead that never went through its door is a finding, not a
   state.
4. **Readers degrade, never die** on one malformed item (governance
   invariant a). A door refusing a mutation is the only fail-closed left.
5. **factory-guard verifies the invariants every 5 minutes and repairs the
   mechanical ones** (id shape, orphan labels, candidate status drift) and
   pages the Mayor once for the rest. What it repairs it says (`FIXED:`).
6. **Prompts and docs stop describing hand-writes.** Every "`gc bd update
   ... --set-metadata gc.<key>`" instruction in `agents/`, `formulas/`,
   `docs/OPERATIONS.md`, `docs/PRODUCT_QUEUE.md` and `lib/factory_campaign.py`
   mail texts is replaced by the door command. The Mayor prompt keeps one
   sentence: "coordination state is written with these commands, never with
   `--set-metadata`".

## What this deliberately does not do

- No new orchestrator, no daemon, no schema migration: doors are the same
  bash/python scripts the Factory already runs, called instead of raw
  `gc bd update`.
- No lock beyond the per-door `flock` that already exists.
- No attempt to make `gc bd update` itself impossible: Gas City owns that
  command. The guard catches what slips through.

## Consequences

- One more script (`bin/campaign-pointer`, ~150 lines) and one subcommand
  in `product-queue`; a prompt/docs pass that removes hand-write
  instructions; guard checks.
- The PO session also stops hand-editing beads: it uses the same doors.
- Reversal: delete `bin/campaign-pointer` and restore the prose
  instructions — nothing else depends on it.

## Evidence

- Audit 2026-09-18 (PO session, read-only): inventory of every `gc.*` key
  with writer/reader/failure mode; "no door at all" list quoted above.
- Incidents: `docs/INCIDENT_2026-09-16-silent-campaign-stall.md`, PR #90,
  memory of 2026-09-18 02:05Z and 02:40Z (this ADR's table).
