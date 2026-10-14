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
`resolve --kind behavioral|topology --project <id>` requires an approved
revised Ticket Graph Draft Bead and routes it through
`bin/ticket-graph-publish bd-patch` -- the same
deterministic to-tickets door, never a second one. `bd-patch` refuses to touch
any ticket that is already delivered (`status: closed`), updates unfinished
tickets in place keeping their IDs, and creates Beads only for genuinely new
scope. If the patch fails, `resolve` fails too and the decision stays open,
still parked.

The register and graph snapshot are caller-supplied JSON. `raise` and
`tactical` resolution do not write live Beads. Behavioral/topology resolution
invokes the live `bd-patch` door, which validates the approved draft and writes
the revised graph to Beads only after its checks pass.

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

### Authorized replacement draft for an already stopped vertical slice

`bin/replacement-draft create` is the bounded entry before `planning-exception
resolve` and `ticket-graph-publish bd-patch` when the project owner has already
authorized exactly one replacement for an already stopped `vertical_slice`.
It clones the approved source graph, preserves the stopped ticket's criteria
and declared scope, replaces only its graph key and dependent edges, and creates
one immutable revised Ticket Graph Draft in a single tracker write. The draft
cites the decision, stopped ticket, convoy, approved Spec/digest, criteria,
scope and useful commit. It never edits or closes the stopped ticket, never
removes `gc.flow.stop`, never publishes the patch and never launches work.

Human and agent entry is the same command, from the live Factory root:

```bash
bin/replacement-draft create --decision <decision-bead> --evidence '<exact recorded words>' \
  --stopped-ticket <bead> --convoy <convoy> --source-draft <approved-draft> \
  --replacement-id <new-graph-key> --useful-commit <40-char-sha> \
  --planning-exception <decision-in-register> --approved-by <project-owner> \
  --author-session <po-agent/session>
```

Every cited equality is checked before the sole `bd create`; missing or stale
evidence refuses with no write. The resulting draft remains only an input to
the existing Planning Exception and `bd-patch` doors.

## Lifecycle

| Subcommand | Effect |
| --- | --- |
| `classify --kind repair\|semantic\|topology` | Read-only. Reports whether the signal requires a Planning Exception (`repair`: no; `semantic`/`topology`: yes). |
| `init --run --out` | Creates a new empty register bound to a Planning/Wayfinding Run id. |
| `raise <register> --graph --bead --kind semantic\|topology --run --decision-id --summary --raised-by` | Refuses `repair`. Computes the affected bead's descendants from the graph snapshot and parks `{bead} ∪ descendants`. If an open decision already covers that bead, records a `duplicate_detected` history event and returns the existing decision id instead of creating a second one. |
| `resolve <register> --decision --kind tactical\|behavioral\|topology --note [--patched-draft <bead-id> --project <id>]` | Requires the decision to be `open`. `tactical` unparks immediately. `behavioral`/`topology` require `--patched-draft` and authorize only that draft for `ticket-graph-publish bd-patch`; on failure the decision stays open and parked, on success it resolves and unparks. |
| `status <register>` | Reports each decision's status and the union of all currently parked beads. |

## Acceptance mapping

| Acceptance criterion | How the tool and tests check it |
| --- | --- |
| Technical repair that fits the approved slice remains inside that slice. | `test_classify_repair_never_requires_a_planning_exception` and `test_raise_rejects_a_repair_kind_signal` prove `repair` never creates a Planning Exception and `raise` refuses it outright. |
| A semantic or topology signal creates one planning-plane decision and parks only descendants that depend on it. | `test_raise_parks_only_the_affected_bead_and_its_descendants` and `test_raise_on_a_bead_with_no_descendants_parks_only_itself` prove the parked set is exactly `{bead} ∪ descendants(bead)` against a graph fixture with unrelated siblings. |
| Unrelated Ready Frontier work continues. | The same tests assert `af-b09`/`af-b11` (unrelated beads in the fixture graph) never appear in `parked`. |
| Tactical clarification resumes the existing slice; behavioral or topology change creates immutable revised artifacts and a validated patch to unfinished work through the sole to-tickets authority. | `test_resolve_tactical_unparks_with_no_artifact_patch` proves tactical resolve unparks with `patch: null`. `test_resolve_behavioral_routes_through_ticket_graph_publish_patch` and `test_resolve_behavioral_leaves_the_decision_open_when_the_patch_fails` prove behavioral/topology resolve calls `ticket-graph-publish bd-patch` with the register and only unparks on success. `tests/ticket-graph-publish-test.py::test_patch_refuses_to_touch_an_already_delivered_ticket` and `test_patch_updates_unfinished_tickets_and_creates_new_ones` prove the door itself protects delivered work and creates only new scope. |
| Classification and duplicate-escalation evidence is recorded in the Adaptation Register. | `test_raise_on_an_already_open_bead_is_detected_as_duplicate_not_double_parked` proves a second raise on covered work is detected as a duplicate and recorded in register history instead of double-parking; `docs/ADAPTATION_REGISTER.md` AR-003 cites this evidence. |

The live `bd-patch` gate accepts a resolved decision or a temporary authorization
for this exact revised draft and withdrawn bead. During `resolve`, the decision
remains open and its descendants parked while the patch runs. Failure removes
that authorization; an interrupted attempt remains parked and must be
reconciled or retried. The gate still validates the revised graph, Spec,
approvals and delivery status before any write.

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
- **PROVEN**: the command tests cover the JSON register and graph snapshot,
  the `fcntl.flock` read-modify-write discipline, and an end-to-end topology
  resolution through the actual `bd-patch` command against a fake tracker.
  The patch is bound to its draft and affected ticket; failed patches leave
  the decision open and the affected work parked. The door's separate tests
  protect already-delivered tickets.

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
  flag). `repair` writes `gc.blocked_classification`; `blocked` then parks
  the bead (status `blocked`, never closed -- af-1al0t1) and `abandoned`
  closes it.
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
