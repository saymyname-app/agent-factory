# Design note: concurrent tracking + wake-key dedup for the mayor-campaign sentinel

## Status and purpose

Design-only. Written for af-rw53b (B07 re-scope) after af-ztnbi (B07)
closed blocked: the worker correctly declined to make this change live
without a design pass first. Reviews the blast radius on the live
dispatch loop and files a narrower implementation ticket. No code
changes ship from this bead.

## Problem

`lib/factory_campaign.py:plan_idle_ladder` and its caller
`bin/mayor-campaign:ladder_decision`/`sentinel` track **exactly one**
Factory delivery bead at a time:

- `gc.campaign_ladder_bead` (singular scalar) is the one bead the ladder
  is watching (`plan_idle_ladder` lines 608-667: "One Factory bead at a
  time, exactly like product results").
- `gc.campaign_wake_key` / `gc.campaign_wake_state` (two singular
  scalars) track the one pending-or-sent notification to the Mayor.
- `tests/mayor-campaign-test.py:707 test_one_factory_bead_at_a_time`
  pins this: given a tracked in-progress bead, the ladder returns
  `("none", "ladder_active")` regardless of what else is ready.

B07's acceptance criterion 1 ("parallel dispatch of independent delivery
slices while a dependent slice waits") has no implementation path today:
even when two ready Factory beads have disjoint dependency closures, the
sentinel will only ever point the Mayor at one, and won't consider a
second candidate until the first bead leaves `in_progress`.

## Design

### 1. Concurrent tracking

Replace the singular `gc.campaign_ladder_bead` with a bounded set,
`gc.campaign_ladder_beads`: a JSON array of bead ids, written and read
only through `bin/mayor-campaign` (the existing `gc.campaign_*` write
door, ADR-0023). A `LADDER_MAX_CONCURRENT` constant (proposed default:
2, matching the "prove it on a canary before going wider" posture used
elsewhere in this codebase) caps how many the sentinel will track at
once.

`plan_idle_ladder` changes shape:

1. For **each** currently-tracked bead, run the existing per-bead
   finalize/fail/stale logic unchanged (workflow closed → `finalize:` or
   failure wake; stale past `LADDER_STALE_SECONDS` → unstick and drop).
   This logic is already per-bead in the current code; it only needs to
   run in a loop instead of once.
2. Any bead whose in-progress check still holds stays tracked and
   contributes no wake this tick.
3. If the tracked set has spare capacity (`len(tracked) <
   LADDER_MAX_CONCURRENT`), fall through to `plan_factory_lane` for
   **additional** candidates — filtered to exclude beads already in the
   tracked set — up to the remaining capacity. `plan_factory_lane`'s
   existing `blockers_are_delivery_complete` check already guarantees a
   new candidate's blockers are delivery-complete, i.e. it does not
   depend on unfinished work; it does **not** need to know about
   siblings, because two candidates that both pass that check are by
   construction not blocking each other (a "blocks" edge between them
   would fail the check for whichever is downstream). No new
   independence check is needed beyond what already exists — only the
   loop and the capacity bound are new.
4. Each newly-selected candidate gets its own `wake_key` in the existing
   `ladder:factory:<id>` shape, and is appended to
   `gc.campaign_ladder_beads`.

### 2. Wake-key dedup

The two flat scalars `gc.campaign_wake_key` / `gc.campaign_wake_state`
collapse to one pending-or-sent notification. With up to
`LADDER_MAX_CONCURRENT` tracked beads, more than one can become due for
a wake in the same tick (e.g. two workflows both finalize between polls).
Today's code already has a narrow precedent for this — the reminder path
(`sentinel`, ~line 1145) bundles a stale product wake and a ladder wake
into one message rather than invent a second wake slot — and that
bundling approach is the one to generalize, not a switch to N
independent mail sends:

- Replace the two scalars with `gc.campaign_wake_keys`: a JSON object
  keyed by `wake_key`, each value `{"state": "pending"|"sent",
  "sent_at": <iso>, "resends": <int>}`. Same shape the two old scalars
  encoded, just keyed instead of singular.
- Each `sentinel` tick computes the **set** of decisions due this tick
  (one per tracked bead that finalized/failed, plus at most one
  new-candidate wake per freed capacity slot, plus the existing
  product-lane decision when not in ladder-only mode) instead of a
  single `decision`.
- All wakes due in the same tick are sent as **one** mail (matching the
  existing bundling precedent), with one subject line per constituent
  wake and the existing per-wake `message` bodies concatenated — not one
  mail per wake_key. This keeps the Mayor's inbox load unchanged in the
  common case (nothing new due) and bounded in the worst case
  (`LADDER_MAX_CONCURRENT` + 1 constituents, not unbounded).
- Dedup rule generalizes directly: a wake_key already `"sent"` in the
  map and not yet `rewake_due` is dropped from this tick's outgoing set,
  exactly as today's single-key check does. `wake_target_resolved`
  sweeps the map instead of one scalar, clearing any entry whose bead
  has since closed.

### 3. What does not change

- `plan_transition` (product lane) is untouched — this is scoped to the
  Factory/ladder lane only.
- The per-bead finalize/fail/stale state machine inside
  `plan_idle_ladder` is untouched in substance, only its cardinality.
- `plan_factory_lane`'s selectors (`is_ladder_bead`,
  `is_scoped_delivery_bead`, `blockers_are_delivery_complete`) are
  untouched; concurrency reuses them as-is per candidate.
- Rungs 3-5 (generative/axis) stay singular — they are not delivery
  slices and B07's acceptance criterion is about delivery-slice
  parallelism specifically.

## Blast radius on the live dispatch loop

This touches the schema and logic that gates **all** live Factory
dispatch, not an isolated feature:

- **Coordination bead schema.** `gc.campaign_ladder_bead` and
  `gc.campaign_wake_key`/`gc.campaign_wake_state` are read and written
  in at least 9 call sites in `bin/mayor-campaign` (reset blocks at
  lines 243, 269, 298, 327, 452, 523-524, 535-537, 690, plus the
  read/write sites at 909, 954, 1095-1103, 1181-1182, 1188). A schema
  change here is ADR-0023 write-door territory: every site must move
  together in one change, and the migration must handle a coordination
  bead already carrying the old singular fields (read old-shape,
  normalize to new-shape, write new-shape only) rather than requiring a
  hand migration of live state.
- **Live-root worktree enforcement (ADR-0022) and one-writer-per-rig
  (AGENTS.md V1 invariant).** Dispatching two Factory beads
  concurrently means two simultaneous `do-work` formulas against the HQ
  rig, each isolated in its own worktree via
  `bin/factory-do-work-workspace` (already proven per-bead, this
  session included: af-rw53b runs in
  `/home/benja/.local/share/agent-factory-runtime-worktrees/af-rw53b`).
  Concurrent *tracking* by the sentinel is safe to design now; concurrent
  *dispatch* is gated on AGENTS.md's existing statement that "V1 allows
  one writer per rig until worktree isolation is proven by canary" — the
  follow-up implementation ticket must either cite an existing canary
  result clearing multi-writer HQ dispatch, or run one, before enabling
  `LADDER_MAX_CONCURRENT > 1` against the live HQ rig. Landing the code
  with `LADDER_MAX_CONCURRENT = 1` (a no-op today, format-compatible for
  `= 2` later) is a safe way to decouple the schema migration from that
  canary.
- **Test surface.** `test_one_factory_bead_at_a_time` encodes the old
  contract and must be rewritten as a
  `test_ladder_tracks_up_to_max_concurrent` (or similar) that asserts
  the capacity bound, not zero-concurrency. Every other
  `plan_idle_ladder`/`ladder_decision` test that passes a bare `tracked`
  dict/`None` needs updating to the new list-shaped tracked parameter;
  this is mechanical but touches most of `tests/mayor-campaign-test.py`'s
  ladder section (the file is 1357 lines; the ladder tests are a
  meaningful fraction).
- **Failure/liveness accounting.** `gc.campaign_progress_at`,
  `PROGRESS_REASONS`, and factory-guard's stale-campaign detection key
  off the single `ladder_active` reason and the single wake_key/state
  pair (per af-pl39t's rationale, already cited in af-fpl1x's
  description in this same workflow: an unclaimed-looking in-progress
  bead reads as "vivante mais immobile" every ~5-6 min). The
  keyed-map version must preserve "at least one tracked bead making
  progress → liveness advances", not require all tracked beads to
  advance in lockstep — otherwise concurrency could make a healthy
  two-bead ladder look stalled to factory-guard whenever one of the two
  is legitimately slow.
- **Mail volume.** Bundling (section 2) keeps mail volume bounded and
  matches existing user-facing behavior (one notification per tick,
  not per wake); this is a design constraint carried forward
  deliberately, not an incidental side effect.

## Follow-up implementation ticket

Filed: **af-nkuwa** — "Implement concurrent-tracking + wake-key dedup in
mayor-campaign sentinel (from af-rw53b design)", scoped to:

1. `gc.campaign_ladder_beads` (list) and `gc.campaign_wake_keys` (map)
   schema migration in `bin/mayor-campaign`, land with
   `LADDER_MAX_CONCURRENT = 1` (behavior-preserving).
2. `plan_idle_ladder` loop-ification in `lib/factory_campaign.py`, per
   section 1 above.
3. Wake bundling in `sentinel`, per section 2 above.
4. Test rewrite: `test_one_factory_bead_at_a_time` →
   `test_ladder_tracks_up_to_max_concurrent`, plus the mechanical
   `tracked` shape updates across the ladder test section.
5. A separate, later step (not in this ticket) raises
   `LADDER_MAX_CONCURRENT` above 1 against the live HQ rig, gated on the
   multi-writer-per-rig canary called out above.

Depends on af-rw53b (this design). Does not depend on the narrower,
separable convoy-attachment/`publication_validated` gap in
`is_scoped_delivery_bead` that af-ztnbi's closing note also flagged —
that gap is orthogonal and should stay its own ticket if pursued.
