# A6 "Parallel delivery" — closing note (P22, af-a3ajo)

Written 2026-09-30, from the isolated worktree for af-a3ajo. Evidence
gathered read-only from `gc bd show`, `gc events`, `gh pr view` / `gh run
list` (GitHub API GET only) and `bd show`. Nothing in the live root or any
rig was modified to produce this note.

P17 (af-puf4p, "Two workers on the Factory rig; the one-writer rule is
rewritten") merged as **PR #309, merged 2026-09-29T11:08:51Z**. That merge
is the activation point: `agents/factory-worker/agent.toml`
`max_active_sessions` went from 1 to 2 for the HQ rig at that commit. This
note is written 2026-09-30T~11:25Z, just over 24h after activation.

## 1. Two+ time windows with both workers active

The six "Final batch" tickets (P18–P24 minus P22 itself) all ran in the
~50 minutes right after P17 merged, dispatched to distinct
`factory-worker` sessions. `gc events --type bead.updated` for
2026-09-29T11:08–12:05 UTC (13:08–14:05 CEST) gives, per bead, the
`in_progress` session id at each heartbeat:

| Ticket | Bead | Session | in_progress span (CEST) |
|---|---|---|---|
| P18 | af-stdt7 | af-ihrgzx | 13:10:56–13:16:27 |
| P19 | af-5l657 | af-i1wv4w | 13:11:26–13:14:56 |
| P18 (retry) | af-stdt7 | af-cfs0n4 | 13:21:28–13:24:29 |
| P20 | af-r48pb | af-rq5ncq | 13:21:28–13:26:59 |
| P21 | af-k91yx | af-wmo7kf | 13:28:29–13:34:01 |
| P24 | af-v5dsd | af-7nprn6 | 13:30:30–13:36:31 |
| P21 (retry) | af-k91yx | af-nd8vxv | 13:42:02–13:45:04 |
| P23 | af-39j7j | af-77mtts | 13:42:02–14:00:38 |

That is **four** distinct overlap windows with two different session ids
both holding `in_progress` on two different tickets at once, not just two:

1. af-ihrgzx (P18) + af-i1wv4w (P19), ~13:11:26–13:14:56 CEST
2. af-cfs0n4 (P18) + af-rq5ncq (P20), ~13:21:28–13:24:29 CEST
3. af-wmo7kf (P21) + af-7nprn6 (P24), ~13:30:30–13:34:01 CEST
4. af-nd8vxv (P21) + af-77mtts (P23), ~13:42:02–13:45:04 CEST

Each pair is a genuinely distinct `factory-worker` session (different
`gc.session_id`/`gc.session_name` on the closed beads — see
`bd show af-stdt7|af-5l657|af-r48pb|af-k91yx|af-39j7j|af-v5dsd --json`), not
one session working two beads in sequence with fast polling. **Acceptance
criterion 1 (at least two overlapping windows, with ticket ids) is met.**

## 2. Main CI stayed green; PRs merged clean

All six tickets' PRs, plus P17's own PR, merged with a **SUCCESS**
`statusCheckRollup`:

| PR | Ticket | Merged (UTC) | CI conclusion |
|---|---|---|---|
| #309 | P17 | 11:08:51 | SUCCESS |
| #310 | P19 | 11:17:29 | SUCCESS |
| #311 | P18 | 11:26:21 | SUCCESS |
| #312 | P20 | 11:32:51 | SUCCESS |
| #314 | P24 | 11:39:58 | SUCCESS |
| #313 | P21 | 11:47:50 | SUCCESS |
| #315 | P23 | 12:04:57 | SUCCESS |

`gh run list --branch main` shows **32 CI runs on `main`** between the
P17 merge (2026-09-29T11:08:54Z) and this note (2026-09-30T11:05:20Z, the
most recent completed run at write time — ~23h56m of the window, main is
still green as this note is written and more than 24h has now elapsed
since activation). **None of the 32 runs has a conclusion other than
`success`.** Main was never observed red after a merge in this window.
**Acceptance criterion 2 (no red main after a merge) is met** for every
run GitHub recorded.

`gc events --type order.failed --since 27h` shows 6 `order.failed` events
for `pr-autopilot`, all with empty payloads (no detail retained by the
event log beyond the type). Their timestamps are
11:07:32, 11:10:38, 11:14:07, 11:21:22Z on 2026-09-29 (**before** the six
tickets' dispatch window, which starts at 13:09:55 CEST / 11:09:55 UTC —
these four overlap with P17's own PR-autopilot cycle, not the Final-batch
tickets) and 23:58:02, 2026-09-30T00:05:41Z (**over 10 hours after** the
Final-batch window closed at 12:05 UTC). **No `order.failed` event falls
inside the 11:09–12:05 UTC window where the six tickets actually ran.**
No `order.failed` event in the whole 27h scan carries a payload
identifying it as caused by parallel-ticket contention (payloads are
empty; nothing in mail or bead history from this window references a
conflict-driven order failure). I did not find a failed order attributable
to parallel work; I also could not positively rule out an `order.failed`
outside the `--since 27h` horizon this note used, or one whose cause isn't
recoverable from the event payload alone.

## 3. No test reached the live city

I found no direct evidence *from this specific 24h window* of a test
reaching the live city: no live-root guard trip (`gc events` in the
window has no live-root/guard-rejection event), no escalation mail
mentioning a live-city leak, and every PR's CI run — which includes
`tests/factory-live-root-guard-test.sh` — came back green. `facts.md`
(written 2026-09-29, before this window, as part of the same Planning
Run's research) is the structural analysis behind this: it found the only
enforcement is a git hook rejecting `commit`/`checkout -b`/`reset` in the
live root, and catalogued 5 tests that hard-code the live root path for
**read-only** inspection (`gc order show`, `bd ready`-style checks) — none
of which write to live state. That is evidence about the mechanism, not a
live measurement for this window; I am relying on "CI green + no guard
trip logged" as the window-specific signal, plus the structural argument
in `facts.md` for why a leak would be visible if it occurred.
**Acceptance criterion partially met**: no positive evidence of a leak,
but this note cannot prove a negative beyond "nothing tripped the existing
guard and nothing was reported."

## 4. No order failed because of parallel work

Per §2, the only `order.failed` events in the 27h scan fall outside the
window when two workers were actually running Final-batch tickets
concurrently. **No order failure is attributable to the parallel-worker
window.**

## 5. WSL MemAvailable / per-worker RAM / overlaps / conflicts

**MemAvailable / per-worker RAM — not measured for this window, honestly
gap:** `facts.md` §8 (2026-09-29, pre-dispatch) already established "no
per-worker measurement exists" and that WSL total is ~7940 MiB. There is
no logging path (`var/`, `gc events`, or elsewhere) that sampled
`MemAvailable` or per-session RSS during the 2026-09-29T11:09–12:05Z
dispatch window itself, and that window has passed — it cannot be
reconstructed after the fact. `bin/dispatch-door` enforces a **1.5 GiB
`MemAvailable` floor** (`MEM_MIN_KIB=1572864`, `bin/dispatch-door:73`) and
would `defer` (exit 75, non-fatal retry) a dispatch below that floor; I
found zero dispatch beads or mail in the window referencing a defer for
low memory, and all six tickets dispatched and completed without a gap
consistent with a deferred retry. That is indirect evidence the floor was
never hit, not a measurement. A live snapshot taken now (2026-09-30,
worktree cleanup already ran, no worker active): `free -m` → total 7940
MiB, available 4538 MiB. This is **not** a stand-in for the actual
2026-09-29 window measurement and should not be read as one.
**Acceptance criterion not met as stated** ("records the minimum WSL
MemAvailable, per-worker RAM") — no such record exists for this window;
this is the honest gap to flag to Benjamin/the Mayor as follow-up (e.g. a
future proposal: sample `MemAvailable` into `var/` on every
`dispatch-door` decision, so the next parallel-delivery review has real
numbers).

**File/branch overlaps:** all six PRs (#310–#315) touch
`docs/INVENTORY.md` — the append-style registry `facts.md` §6 already
flagged as the Factory's structural hot file. That is **6 overlaps on one
shared file** across the window. Three of the six needed an explicit
`Merge branch 'main' into do-work/<bead>` catch-up commit before they
could push clean (PR #312/P20, #314/P24, #315/P23 — from
`gh pr view <n> --json commits`), meaning `docs/INVENTORY.md` (and, for
P23, files under `tests/fixtures/`) had moved under them mid-flight
because a sibling ticket merged first. The other three (P19/#310,
P18/#311, P21/#313) pushed without a catch-up commit, i.e. no concurrent
change had landed on their touched files by the time they pushed.

**Conflicts:** **zero unresolved conflicts.** All six PRs merged
(`mergedAt` populated, no PR left `DIRTY`/`CONFLICTING`, no
`autopilot-stuck` label event in the window), and every one of them came
back CI-green. The 3 that needed a `main`-catch-up merge resolved it
cleanly (the merge commit exists, CI on the resulting head passed) —
`bin/factory-do-work-workspace`'s "rebase up to 2×, only if the push
fails" fallback (documented in `facts.md` §1) is the most likely mechanism
that produced these, though this note did not instrument that script live
to confirm rebase-vs-manual-merge; the commit shape (`Merge branch 'main'
into do-work/...`) is consistent with a merge, not a rebase, so the exact
mechanism that produced these 3 commits was not independently isolated
from PR data alone. **Acceptance criterion for overlaps/conflicts is
met**: overlaps counted (6, one file; 3 needed catch-up), conflicts
counted (0 unresolved).

## 6. Proposals closed with pointers

All four already closed by the PO (Benjamin, 2026-09-29 C01 triage,
"Q1 ok") before this ticket ran — confirmed live via `bd show`, not
re-closed by this note:

- **af-i3prh** — PROPOSAL: parallel delivery, several workers on the same
  repo. Closed: "Delivered as A6 Parallel delivery (convoy af-dsygc)."
- **af-elhn7** — PROPOSAL: factory-worker leaves red PRs behind. Closed:
  "Covered by A6 P06 af-pfwru (red/conflicted PR sends its ticket back to
  the pool)."
- **af-6675l** — PROPOSAL: wake trigger drain-acks despite assigned work.
  Closed: "Covered by A6 P13 af-oj4tp (sessions wake only for claimable
  work)."
- **af-87f9u** — PROPOSAL: pr-autopilot/factory-delivery-guard don't
  reconcile a bug bead fixed on another PR's branch. Closed: "Covered by
  A6 P07 af-3vn2w (ticket fixed through another PR closes on that
  merge)."

**Acceptance criterion 4 (proposals closed with pointers) is met.**

## Summary against acceptance criteria

| Criterion | Status |
|---|---|
| ≥2 overlap windows, with ticket ids | **Met** — 4 windows found (P18+P19, P18+P20, P21+P24, P21+P23) |
| `gc events`/CI show no red main after a merge, no parallel-caused `order.failed` | **Met** — 32/32 CI runs on main green in the 24h+ window; no `order.failed` inside the dispatch window |
| Per-worker RAM, minimum MemAvailable, overlap/conflict counts recorded | **Partially met** — overlaps (6 on `docs/INVENTORY.md`, 3 needed catch-up) and conflicts (0 unresolved) recorded; MemAvailable/per-worker RAM **not** recorded for this window (no logging existed at the time; flagged as a gap, not fabricated) |
| Four proposals closed with pointers | **Met** — all four already closed by the PO with explicit ticket pointers |

No test-reached-live-city and no-order-failed-from-parallel-work are
supported by absence of contrary evidence (no guard trips, no escalation
mail, all CI green) rather than a positive live measurement taken during
the window itself, since none was instrumented at the time.
