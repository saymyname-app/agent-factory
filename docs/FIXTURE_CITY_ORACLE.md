# Fixture City public-behavior oracle

## Status and purpose

`bin/fixture-city-oracle` is the deterministic acceptance seam for the new
project-agnostic Factory path. It starts with a synthetic project intent and
observes externally meaningful lifecycle state without inspecting prompts,
session layout, formulas, orders, agent roles, or candidate persistence.

The harness and its reference fixture are **PROVEN** by
`tests/fixture-city-oracle-test.py`. A real planning implementation remains
**TARGET** until its adapters pass the same oracle. The delivery of one
ticket of a marked convoy is walked by a second kind of scenario (below). Passing the reference
fixture does not select or endorse a Gas City allocation.

## Run it

Both adapters are explicit executable files. They may be the same executable,
as in the reference fixture, but the interfaces remain separate:

```bash
./bin/fixture-city-oracle run \
  tests/fixtures/fixture-city/single-rig.json \
  --operator "$PWD/tests/fixtures/fixture-city/operator" \
  --publication-door "$PWD/tests/fixtures/fixture-city/operator"
```

The result is one deterministic JSON object. It names the observed Planning Run
states, Planning Artifact identity and digest, publication digest and convoy,
exact integration evidence, Delivered/Accepted result, invoked public
interfaces, and a digest of the oracle result itself. It contains no temporary
workspace path or process identity, so equal public behavior produces equal
output.

## Scenario contract

Scenarios use `agent-factory-fixture-scenario/v1` and contain:

- a synthetic `project_id` and product-language `intent`;
- one or two fixture rigs, each backed by checked-in synthetic source and
  pinned to the exact deterministic Git commit produced from that source;
- independently observable vertical slices and their blocker keys;
- `inject.publication_failure`, either `none` or `after-stage`; and
- `request.legacy_path`, either `none` (default) or one of `planning-base`,
  `release-contract`, `cockpit-v1-export` (see "Legacy path quarantine" below).

The oracle rejects duplicate IDs, undeclared rigs, non-exact revisions, missing
blockers, self-dependencies, and cyclic graphs before invoking an adapter.

## Legacy path quarantine

ADR-0027 fences the legacy planning-base methodology, the duplicated Release
Contract, and Cockpit V1's routes/screens/state model so that a new Planning
Run cannot select or reuse them. A scenario proves this by setting
`request.legacy_path` to `planning-base`, `release-contract`, or
`cockpit-v1-export` instead of the default `none`.

When `legacy_path` is set, the oracle calls only the operator's `start`
command (with `check=False`) and requires it to exit non-zero with a
non-empty, operator-readable reason on stderr. No Planning Run identity,
artifact, publication, or write door is ever invoked — the run result carries
`planning_run_id: null`, `planning_states: []`, and a
`legacy_path_rejection: {selection, reason}` object instead of the full
lifecycle trace. A request that omits `legacy_path` is completely unaffected
and completes the full lifecycle exactly as before, which is how
already-attached delivery convoys keep working without depending on the new
planner.
See `tests/fixtures/fixture-city/legacy-planning-base.json`,
`legacy-release-contract.json`, and `legacy-cockpit-v1-export.json`.

## Public adapter boundary

An adapter is copied into the ephemeral workspace and called only as:

```text
<absolute executable> --workspace <ephemeral-directory> <command> [arguments]
```

The operator surface implements `start`, `synthesize`, `observe`, `artifact`,
`approve`, `integrate`, `verify-assembly`, `deliver`, and `accept`. The
deterministic write-door surface implements `publish`. `observe` returns
`agent-factory-fixture-observation/v1`; `artifact` returns public artifact
content plus its ID and digest. Adapters are self-contained executables; they
cannot depend on undeclared files outside the fixture workspace. No command
exposes candidate storage, prompts, sessions, or orchestration topology to the
oracle.

Every observation carries:

- Planning Run state;
- positive Work Plane data and routability;
- Planning Artifact and exact approval identity/digest;
- publication, graph, blocker-edge, and convoy identity;
- exact per-rig integration evidence;
- distinct Delivered and Accepted states; and
- an `effects` list, which must remain empty.

The oracle recomputes artifact and graph digests from public content. Planning
items must be non-routable. Delivery items must be publication-validated and
attached to the observed convoy. A Delivered Outcome is observed before the
separate acceptance action.

## Hermeticity and failure injection

Each adapter command runs under Bubblewrap with every namespace except the
network namespace unshared. The network namespace is retained because some CI
runtimes permit Bubblewrap but deny its loopback setup; a seccomp filter denies
socket creation and `io_uring` inside the adapter process and all descendants.
Ubuntu runners that apply AppArmor's host-wide unprivileged-user-namespace
restriction load `config/fixture-city-bwrap.apparmor`. The attachment-specific
profile grants `userns` only to `/usr/bin/bwrap`; CI does not disable the global
restriction. This lets Bubblewrap create the mount namespace while keeping the
runner's policy in force for every other executable.
The sandbox exposes only read-only system runtime directories and the writable
ephemeral fixture workspace; the host's home, identity files, repositories,
and other data are absent. Each run also receives a new HOME, TMPDIR, and XDG
cache. Credentials, provider variables, proxy configuration, and the caller's
other environment are not inherited. `FIXTURE_CITY_EFFECT_MODE=deny` is
mandatory for the adapter. A containment scenario probes the absence of host
identity files, network socket creation, and system-directory writes. The
checked-in scenarios contain only synthetic identities and revisions, so the
fixture run cannot create a production, personal-data, external-publication,
or spend effect.

Exact-revision assembly directories are over-mounted read-only inside every
adapter sandbox, and the oracle requires clean Git worktrees before and after
the runnable assembly check. A negative adapter attempts to replace a committed
executable and proves the mount rejects it.

For `after-stage`, the publication door must return non-zero. The oracle then
queries the operator again and requires all of these to be absent: a Delivery
Work Graph, delivery-plane items, a graph digest, and a convoy ID. The negative
fixture deliberately leaks one staged node and proves the oracle rejects that
candidate. Recording the failed attempt is allowed; publishing any fraction of
the graph is not.

## Single-rig and multi-rig evidence

A single-rig scenario reports `single-rig`. For every rig, the oracle creates a
deterministic local Git repository from the checked-in synthetic source,
requires its commit to equal the scenario's pinned revision, and assembles a
detached checkout at that revision. It independently records the Git tree ID.

A scenario with more than one rig reports `exact-revision-multi-rig` only when
the public integration evidence exactly matches every assembled
`(rig, revision, tree)` tuple in order. The public `verify-assembly` operator
command executes the consumer from one exact checkout against the provider from
the other, inside the same sandbox; its evidence is then observed through the
operator surface before Delivered is allowed. The negative assembly advertises
a compatible manifest but its runnable consumer requires incompatible behavior,
proving declarations alone cannot pass. Another negative scenario proves that
an arbitrary SHA fails. Per-rig green claims, branch names, or approximate
revisions are insufficient.

This first protocol deliberately supports one rig or one two-rig
provider/consumer assembly. It rejects larger topologies instead of reporting
participants that the runnable check did not exercise; later work may extend
the protocol with a check that consumes every additional participant.

Cockpit V1 is deliberately outside this contract. It may consume future public
state, but the deterministic fixture City remains the acceptance oracle.

## Assembled-diff review and rejection routing (B10)

Delivered proves exact-revision integration and assembled public behavior;
Accepted is a separate, later decision, and the oracle keeps the two visibly
distinct in every observation and result. Between them, a multi-slice outcome
(`request.slices` names more than one vertical slice, regardless of rig
count) requires exactly one independent `review-assembly` before `deliver`,
scoped to the assembled diff and focused on `interaction_risks` and
`spec_drift`. The oracle proves both directions: a multi-slice request must
receive that review, and a second review over the same outcome is rejected
(one unique review, not one per slice). A single-slice request must be
refused a final review entirely — there is nothing left to assemble, so a
duplicate review is not offered. `result.review` reports `{required,
performed}` for both cases; see `tests/fixtures/fixture-city/multi-rig.json`
(review required) and `containment.json` (single slice, no review).

`inject.reject_reason` (`none` by default, or `spec_mismatch`,
`changed_behavior`, `active_danger`) drives a scenario through `reject`
instead of `accept` once Delivered is reached. Each reason routes to a
distinct, fixed destination instead of a generic failure:

| Reason | Routing |
|---|---|
| `spec_mismatch` | `targeted_repair` |
| `changed_behavior` | `planning` |
| `active_danger` | `safe_neutralization` |

A rejection never performs a default whole-outcome rollback: the published
delivery graph, convoy, and every already-verified per-rig integration
survive it unchanged, and only the Delivered→Accepted boundary is affected.
Acceptance is refused once an outcome is rejected. See
`tests/fixtures/fixture-city/reject-spec-mismatch.json`,
`reject-changed-behavior.json`, and `reject-active-danger.json`.

The oracle also calls the operator's `attempt-effect` interface at multiple
lifecycle points — after Delivered, after Accepted, and after a rejection —
and requires every attempt to be refused with `effects` staying empty. This
proves a sensitive effect (production, external publication, spend,
destructive, or wider personal-data access) stays blocked on explicit human
authority independent of how far integration or acceptance has progressed;
the fixture's deny-mode operator never grants it regardless of any
`--authority` value supplied, because the real authorization channel is a
human decision outside the deterministic fixture, not a flag the fixture
itself can honor.

## The delivery of one ticket (T19)

A second kind of scenario (`agent-factory-fixture-delivery-scenario/v1`)
walks one ticket of a marked convoy through the delivery flow and
requires its lifecycle, in this order and with none skipped:
`published`, `started`, `red`, `frozen`, `coded`, `reviewed`, `evaluated`,
`merged`, `closed` (by the ticket-end gate, `docs/TICKET_END.md`).

```bash
./bin/fixture-city-oracle run \
  tests/fixtures/fixture-city/one-ticket-end-to-end.json \
  --delivery-driver "$PWD/tests/fixtures/fixture-city/delivery-driver"
```

The **driver** makes the flow advance; the **oracle** observes. The driver
is called as `<driver> --workspace <dir> prepare [--inject NAME] [--project
NAME] | publish | advance | stop`. `prepare` says where the public state is read (convoy,
ticket, repository, environment of the state commands, and optionally the
`profile` an Acceptance Session launches the product by); a driver that
publishes through a door that numbers the convoy and the ticket names them
in the answer of `publish` instead. Each `advance`
plays one event: one pass of the Factory's order (the real
`bin/convoy-advance`) or what one agent session leaves behind. After each
event the oracle itself runs `bin/convoy-state show`, reads the branches of
the repository, and at the end runs `bin/ticket-end check` and
`bin/evidence-capture verify`. It reads no prompt, no formula and no role,
and it does not trust what the driver prints beyond « nothing changed ».

What the oracle requires at every observation:

- the states reached are a prefix of the lifecycle, never one without those
  before it, and never fewer than at the observation before;
- the times of their public records follow the order of the lifecycle
  (several states may appear in one observation: a pass that evaluates,
  merges and closes);
- a merge is the tip of the ticket's branch, on the integration branch;
- a closed ticket carries the record of the gate: its version, its nine
  passing verdicts, the commit that was merged. A ticket closed without it
  fails the run;
- the convoy is never in an « état sans règle ».

The scenario says what the walk must end in: `expect: {closed: true}`, or
`{closed: false, missing: [numbers]}` — the ticket stays open and
`bin/ticket-end check` names exactly those conditions.

| Scenario | Walk | Result |
| --- | --- | --- |
| `one-ticket-end-to-end.json` | nothing goes wrong | the nine states, closed by the gate |
| `one-ticket-missing-condition.json` | a criterion is edited on the ticket once its author has finished | stops at `evaluated`; the gate names conditions 1 and 6 |
| `one-ticket-closed-by-hand.json` | the ticket is closed in the tracker outside the gate | the oracle fails |
| `one-ticket-second-project.json` | nothing goes wrong, on a ticket of the second project of the fixture (T35) | the nine states, closed by the gate |
| `three-failures-parked.json` | the convoy holds two more tickets: one whose author session ends three times without a Ticket Exit, one that waits for it (T20) | the walked ticket reaches its nine states and is closed by the gate; the two others are parked; one grouped request names them both |
| `story-repaired-delivered.json` | the Spec holds a second user story the product does not serve when the walked ticket closes (T26) | the end of the Spec refuses once on the Outcome Evaluation; one `repair` is published and delivered by the flow of a ticket; the whole gate is replayed on the new tip; the convoy is Delivered |

### A ticket that fails three times is parked (T20)

`expect: {closed: true, parked: N}` adds to the walk what Spec §8 asks of
the resumes (`docs/CONVOY_ADVANCE.md`). `parked` is a positive number and
goes with `closed: true` only. With it:

- the walk does not end when the walked ticket closes: it goes on until an
  event changes nothing, within 32 events instead of 16;
- after each event the oracle also reads the parked tickets of the convoy on
  `bin/convoy-state show` and the operator's list on `bin/escalation-door
  list`. More than one request for the convoy fails the run, and so does a
  request raised while a ticket that is not parked is still open;
- at the end: exactly N tickets are left, all parked, each by a parked
  ticket of the convoy and for its cause; the operator's list shows exactly
  one request, which names each of them; and the walked ticket advanced
  after the first parking — the tickets that wait for no parked ticket keep
  going.

The result then carries `parking`: the parked tickets (cause, origin, count
of resumes), the states the walked ticket reached after the first parking,
the number of requests and the tickets the request names.

With `--inject three-failures` the reference driver adds the two tickets to
the convoy and plays, for the first, an author session that takes it and
ends without a Ticket Exit, three times, each once the order has sent the
resume of the failure before. The order itself — the real
`bin/convoy-advance` — counts the resumes, parks at the third and raises
the request.

### A story not observed at the end is repaired, then Delivered (T26)

`expect: {closed: true, outcome: "delivered", repairs: N}` adds to the walk
what Spec §9 asks of the end of the Spec (`docs/SPEC_END.md`,
`docs/CONVOY_ADVANCE.md`). `outcome` goes with `closed: true` and without
`parked`; `repairs` (zero when absent) goes with `outcome` only. With it:

- the walk does not end when the walked ticket closes: it goes on until an
  event changes nothing, within 48 events;
- after each event the oracle also reads, on `bin/convoy-state show`, the
  tickets the convoy gained since its publication — more than N, or one
  that is not a `repair`, fails the run — and requires of each the
  lifecycle of a ticket, as of the walked one; it runs `bin/spec-end check`
  and reads the operator's list on `bin/escalation-door list`, where any
  request fails the run until the convoy carries `delivered`;
- Delivered is never recorded while a condition is missing: at every
  observation where the convoy carries `delivered`, `bin/spec-end check`
  must exit 0 and answer `delivered: true`, with no condition named and no
  ticket open. The reverse (the command answers Delivered, the convoy
  carries no record) fails too;
- from the observation that first shows Delivered on (T28, Spec §11): the
  operator's list holds exactly one request, on the convoy, and its line
  ends with ` — dossier : <page>`, the page `bin/evidence-pack check`
  answers for the convoy's Evidence Pack — the Acceptance Request, sent by
  the pass that recorded Delivered and never sent again;
- at the end, once an event changed nothing: exactly N repairs, each with
  the nine states and closed by the ticket-end gate (its record, tied to
  the commit that was merged); `convoy.delivered.commit`,
  `convoy.spec_end.commit` and the commit `bin/spec-end check` answers are
  all the tip of the integration branch, read in the repository, and that
  tip holds the merge of every repair — the gate was replayed in full on
  the new tip; the first observation that showed Delivered came with the N
  repairs closed; `convoy.end_stop` is null; `convoy.counters.end_rounds` is
  zero without a repair and between 1 and N with repairs (a round publishes
  at least one repair, a repair belongs to one round); the operator's list
  holds the one Acceptance Request;
- then the oracle runs `bin/acceptance-session open` on the convoy (the
  repository and the profile `prepare` named): every address it answers
  must serve HTTP, and the commit it answers must be both the commit of the
  Evidence Pack and the tip of the integration branch. It runs
  `bin/acceptance-session close`, after which no address may answer.

The result then carries `outcome`: `state`, the tickets `published` at
first, the `repairs` (id, kind, lifecycle, closed by the gate),
`end_rounds`, `end_stop`, `refused` (the verdicts `bin/spec-end check`
named at the observation that first showed a round counted — absent when
no round was), `spec_end` (the version of the list and its verdicts on the
tip), `delivered` (how many observations showed it and were checked, how
many repairs were closed at the first one), the number of `requests` and
`acceptance`: `{request: 1, dossier_linked: true,
launched_at_dossier_commit: true, stopped: true}` — counts and booleans
only, no address, commit or path. `interfaces.read` gains `git rev-parse`,
`spec-end check`, `escalation-door list`, `evidence-pack check`,
`acceptance-session open` and `acceptance-session close`. A scenario that names no `outcome` keeps the result
it had: nothing of the end of the Spec is read for it, and its walk still
ends at the closed ticket.

With `--inject story-not-observed` the reference driver publishes through
the real publication door (`bin/ticket-graph-publish bd-publish`, after
the real `bin/graph-review`): an approved Spec with two user stories — the
home page, and the items in JSON at `GET /items`, which the product of the
fixture does not serve — and an approved draft whose one slice covers
both. The stand-in Evaluator of the end fetches `GET /items` on the
launched product, does not observe the second story and drafts its repair;
the order itself — the real `bin/convoy-advance` — counts the round,
publishes the repair through the patch door and starts it. The driver then
plays the author session of the repair, whose commit adds the route to the
product for real; the reviewer and the Evaluator of the ticket answer for
it (the Evaluator on `GET /items`), the order merges and closes it, then
replays the gate: `bin/spec-end run`, the Outcome Evaluation on the new
tip, where the story is now observed, the end review, the Evidence Pack,
and `bin/spec-end run` again, which records Delivered.

A scenario may name the `project` of the fixture its ticket belongs to; the
oracle hands the name to the driver (`prepare --project`) and reports it in
its result. Absent, the ticket is an interface ticket of the first project
(`delivery-fixture-city`: a web page in Python, with a Validated Prototype).
`delivery-fixture-city-api` is the second one: a JSON API on Node.js, with no
web page and no prototype (`docs/PROJECT_PLANNING_PROFILE.md`). The oracle
requires the same lifecycle of both and reads the same public state; what the
flow does differently is read by the flow in the profile of the project.

The result is one deterministic JSON object
(`agent-factory-fixture-delivery-result/v1`): the lifecycle, what each
observation added, the verdicts of the gate, the names of the verified
pieces. It holds no path, commit or time.

Limits of the reference driver (`tests/fixtures/fixture-city/delivery-driver`):

- It is **not contained by the no-socket sandbox** of the planning adapters:
  the evaluation and the fidelity check launch the product on a loopback
  port. It gets a clean environment and a throwaway workspace.
- The tracker is the fake one of `tests/fixtures/convoy-state/gc`. No agent
  runs: the reviewer and the Evaluator are the stand-ins of their suites,
  the author files its steps through `tests/lib/ticket_proofs.py` (each
  piece sealed by the real `bin/evidence-capture`), not through
  `bin/tdd-step`, `bin/demonstrate` and `bin/ticket-exit`.
- `publish` leaves what the publication door leaves (the ticket, the mark,
  the integration branch) without calling `bin/ticket-graph-publish`,
  except with `--inject story-not-observed`, where the real door publishes
  (the patch door needs a published graph to revise). The door then writes
  the tracker through the fake `bd` of
  `tests/fixtures/ticket-graph-publish/bd-bead-mode`, on the same file as
  the fake `gc`; the approved Spec, the approved draft and the verdict of
  the graph review are written by the driver, as a Planning Run leaves them.
- The browser of the fidelity check is the fake one of
  `tests/fixtures/prototype-fidelity/browser`.
- On the second project the product is launched, and the merged result
  tested, with Node.js: when `node` is not on the bare `PATH` the oracle
  gives its adapters, the driver adds the user's `~/.local/bin` to the `PATH`
  of the order, and fails if it is not there either.
- Without `expect.outcome` the walk ends at the closed ticket. With it the
  end of the Spec is walked up to Delivered (T26), on the first project
  only, and with the stand-ins of the Evaluator and the reviewer of the end
  (`tests/fixtures/outcome-evaluation/evaluator`,
  `tests/fixtures/spec-end-review/reviewer`). The other ways the end can go
  — a second round, the rounds exhausted and the « non conforme » request, a
  red integration branch, a Blocking Finding of the end review — and
  Benjamin's answer to the Acceptance Request are not scenarios of this
  oracle: they are proven by the suites of the gate and of the pass
  (`docs/SPEC_END.md`, `docs/CONVOY_ADVANCE.md`). Of the acceptance the
  oracle walks the request, the opening and the closing of the session; the
  session outage, the « non conforme » session and « no delay accepts » are
  in `tests/convoy-stops-fixture-city-test.py`.
- The reference driver gives the session its own state directory in the
  workspace (`ACCEPTANCE_SESSION_STATE_DIR`), `stop` closes a session left
  open, and the order reads `ESCALATION_DOOR_NOW`, `PROPOSAL_DOOR_NOW` and
  `PR_AUTOPILOT_NOW_EPOCH` from the driver's environment when a caller
  simulates the clock.
