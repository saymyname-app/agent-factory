# Planning Exception (B08)

## Status and purpose

`bin/planning-exception` implements Q22's structured signal: a delivery
worker that meets a question about approved intent, behavior, or work
topology never redesigns the graph itself -- it raises a Planning Exception
back to its originating Planning Run. `classify` tells a worker whether its
situation is bounded technical repair (stays inside the current ticket, no
exception) or a genuine semantic/topology surprise (must `raise`). `raise`
records exactly one non-executable Planning Decision and parks only the
affected bead and its transitive descendants in a caller-supplied Delivery
Work Graph snapshot -- unrelated Ready Frontier work is never touched. A
second `raise` against work already covered by an open decision is detected
as a duplicate and recorded as such rather than creating a second decision or
parking twice.

`resolve --kind tactical` closes the decision and unparks with no artifact
change -- a clarification doesn't alter the Spec or Ticket Graph Draft.
`resolve --kind behavioral|topology` requires an already-drafted, already-
validated revised Ticket Graph Draft and routes it through
`bin/ticket-graph-publish patch` (B06's extension for this ticket) -- the same
deterministic to-tickets door, never a second one. `patch` refuses to touch
any ticket that is already delivered (`status: closed`), updates unfinished
tickets in place keeping their IDs, and creates Beads only for genuinely new
scope. If the patch fails, `resolve` fails too and the decision stays open,
still parked.

This is a deterministic synthetic prototype operating on a caller-supplied
JSON register and graph snapshot, the same fixture-bound scope B04's
`wayfinding-run` declared -- it does not itself read or write live Beads.

## Run it

```bash
./bin/planning-exception classify --kind repair
./bin/planning-exception init --run run-1 --out register.json
./bin/planning-exception raise register.json --graph tests/fixtures/planning-exception/graph.json \
    --bead af-b08 --kind semantic --run run-1 --decision-id pd-1 \
    --summary "spec says X, delivery found Y" --raised-by worker-1
./bin/planning-exception resolve register.json --decision pd-1 --kind tactical \
    --note "naming clarification, resume as-is"
./bin/planning-exception status register.json
python3 tests/planning-exception-test.py
```

## Lifecycle

| Subcommand | Effect |
| --- | --- |
| `classify --kind repair\|semantic\|topology` | Read-only. Reports whether the signal requires a Planning Exception (`repair`: no; `semantic`/`topology`: yes). |
| `init --run --out` | Creates a new empty register bound to a Planning/Wayfinding Run id. |
| `raise <register> --graph --bead --kind semantic\|topology --run --decision-id --summary --raised-by` | Refuses `repair`. Computes the affected bead's descendants from the graph snapshot and parks `{bead} ∪ descendants`. If an open decision already covers that bead, records a `duplicate_detected` history event and returns the existing decision id instead of creating a second one. |
| `resolve <register> --decision --kind tactical\|behavioral\|topology --note [--patched-draft]` | Requires the decision to be `open`. `tactical` unparks immediately. `behavioral`/`topology` require `--patched-draft` and invoke `ticket-graph-publish patch`; on failure the decision stays open and parked, on success it resolves and unparks. |
| `status <register>` | Reports each decision's status and the union of all currently parked beads. |

## Acceptance mapping

| Acceptance criterion | How the tool and tests check it |
| --- | --- |
| Technical repair that fits the approved slice remains inside that slice. | `test_classify_repair_never_requires_a_planning_exception` and `test_raise_rejects_a_repair_kind_signal` prove `repair` never creates a Planning Exception and `raise` refuses it outright. |
| A semantic or topology signal creates one planning-plane decision and parks only descendants that depend on it. | `test_raise_parks_only_the_affected_bead_and_its_descendants` and `test_raise_on_a_bead_with_no_descendants_parks_only_itself` prove the parked set is exactly `{bead} ∪ descendants(bead)` against a graph fixture with unrelated siblings. |
| Unrelated Ready Frontier work continues. | The same tests assert `af-b09`/`af-b11` (unrelated beads in the fixture graph) never appear in `parked`. |
| Tactical clarification resumes the existing slice; behavioral or topology change creates immutable revised artifacts and a validated patch to unfinished work through the sole to-tickets authority. | `test_resolve_tactical_unparks_with_no_artifact_patch` proves tactical resolve unparks with `patch: null`. `test_resolve_behavioral_routes_through_ticket_graph_publish_patch` and `test_resolve_behavioral_leaves_the_decision_open_when_the_patch_fails` prove behavioral/topology resolve calls `ticket-graph-publish patch` and only unparks on success. `tests/ticket-graph-publish-test.py::test_patch_refuses_to_touch_an_already_delivered_ticket` and `test_patch_updates_unfinished_tickets_and_creates_new_ones` prove the door itself protects delivered work and creates only new scope. |
| Classification and duplicate-escalation evidence is recorded in the Adaptation Register. | `test_raise_on_an_already_open_bead_is_detected_as_duplicate_not_double_parked` proves a second raise on covered work is detected as a duplicate and recorded in register history instead of double-parking; `docs/ADAPTATION_REGISTER.md` AR-003 cites this evidence. |

## Scope of proof

- **TARGET**: a delivery worker signals a semantic or topology surprise,
  only the affected subgraph pauses, unrelated Ready Frontier work
  continues, a tactical clarification resumes cleanly, and a genuine
  behavioral/topology change patches unfinished work through the sole
  to-tickets authority without becoming a second decomposition authority.
- **CONFIGURED**: the `agent-factory-planning-exception-register/v1` register
  contract, a caller-supplied Delivery Work Graph snapshot
  (`{"beads": {id: {"blocked_by": [...]}}}`), and
  `tests/fixtures/planning-exception/`.
- **OBSERVED**: the deterministic CLI output and the acceptance-mapped tests
  above, including the duplicate-detection, tactical-resume, and
  patch-failure-leaves-decision-open paths.
- **PROVEN**: within this fixture set, that `classify`/`raise`/`resolve`/
  `status` hold every acceptance criterion against a plain JSON register and
  a plain JSON graph snapshot, using the same `fcntl.flock` read-modify-write
  discipline B04 proved for concurrent map writers, and that the extended
  `ticket-graph-publish patch` door protects already-delivered tickets.

Not proven here: translating a live Beads Delivery Work Graph into the
snapshot format `raise` consumes, or a live Planning Run actually authoring
the revised draft `resolve --kind behavioral|topology` requires -- both are
callers of this tool, not part of it.

## Enforcing that raising isn't optional (af-zwhh0)

Recognizing a semantic/topology surprise and actually raising a Planning
Exception used to be two separate, disconnected steps: B12 (af-4a44k) hit
exactly this surprise, its own worker's closing note said as much, but
`bin/planning-exception raise` was never invoked -- the Mayor separately
created an ad-hoc, self-authorized redecomposition bead instead (AR-003's
"second decomposition authority in disguise"). Two pieces close that gap:

- `bin/deliver-close --outcome blocked|abandoned` requires
  `--classification repair|semantic|topology` (af-cphvt: leaving it optional
  let a worker skip the triage question entirely by just never passing the
  flag). `repair` writes `gc.blocked_classification` and closes as before.
  `semantic`/`topology` requires `--planning-exception-id <decision-id>`
  naming the decision an earlier `raise` actually produced for this bead --
  without it the close is refused outright, before any Beads write. A
  blocked/abandoned close with no `--classification` at all is refused the
  same way.
- `bin/factory-planning-exception-guard` (wired into `factory-guard`) is the
  detection net for everything that bypasses that door: a bead closed
  `blocked`/`abandoned` with `gc.blocked_classification` semantic/topology
  and no `gc.planning_exception_id` is flagged once and the Mayor paged once,
  never auto-repaired. It also flags a bead carrying
  `gc.redecomposes=<bead-id>` (a bead that exists to redesign or re-scope
  that bead's blocked work) unless the target already has an open Planning
  Exception, or `gc.authorized_by` names a real human decision -- not the
  target bead's own id acting as its own authority.

See `tests/factory-planning-exception-guard-test.sh` and the
`--classification`/`--planning-exception-id` cases in
`tests/deliver-close-test.sh` for the regression proof.
