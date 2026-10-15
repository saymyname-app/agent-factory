# Author formula: the sequence of a ticket held by scripts (T12, Spec af-wf4w5r §0 rule 4, §4, §5)

## Status and purpose

A ticket of a convoy that carries the **new-flow mark** is worked by one
fresh author session, in a work tree of its own, on a branch that leaves
from the integration branch of the Spec (`docs/SPEC_INTEGRATION.md`). The
formula `mol-ticket-author` holds the sequence — work tree, red step, code,
demonstration on the launched product, Ticket Exit — and each passage from
one step to the next is a check run by code. What the agent says closes
nothing. A convoy without the mark is not touched: it is dispatched,
merged and closed as before.

Only `bin/convoy-advance` starts the formula (`config/delivery-flow.json`,
`start.formula`), through `bin/dispatch-door --role author --convoy`. Nobody
slings it by hand.

What follows the exit « terminé » is not the author's: the code review of
the ticket is sent by the flow to a reviewer session (T14,
`docs/CODE_REVIEW.md`), and the ticket is evaluated on the launched product
by an Evaluator session (T15, `docs/TICKET_EVALUATION.md`). What they
refuse goes, once, to another fresh author session on the formula
`mol-ticket-correction`, which takes the ticket with the same `start`
(T17, `docs/CORRECTION_ROUND.md`). A merged ticket is closed by the
ticket-end gate (T19, `docs/TICKET_END.md`). A ticket whose author must take
it again — session interrupted, ticket returned by the merge, repair closed,
request answered, finished branch behind the tip of the integration branch
(T44) — goes to one fresh author session on the formula
`mol-ticket-resume`, which takes it with the same `start`, on the same
branch; resumes are counted and the third parks the ticket (T20,
`docs/CONVOY_ADVANCE.md`). A stopped ticket is not resumed, but for a
Ticket Evaluation without result, once per tip of the integration branch.

## The pieces

| Piece | Role |
|---|---|
| `formulas/mol-ticket-author.formula.toml` | the five steps and the teardown; each step carries an exec check |
| `assets/scripts/checks/ticket-author-check.sh` | the check Gas City runs when a step is closed; it only runs `bin/ticket-author check` |
| `bin/ticket-author` | `start`, `demonstrate`, `gate`, `check`, `release`, `locate` |
| `bin/convoy-state set-session` | records which session took the ticket (`docs/CONVOY_STATE.md`) |
| `bin/ticket-exit` | the exit; « terminé » now needs the demonstration proof (`docs/TICKET_EXIT.md`) |
| `agents/delivery-author/agent.toml`, `work_query` | Gas City's default work query with one difference: a session that has ever been assigned a bead is offered, of the unassigned work, only that of its own workflow, so a session that holds a ticket never takes the first step of another one |
| `agents/delivery-author/agent.toml`, `max_active_sessions` | N authors in parallel (Spec §4): equal to `max_sessions` of `config/delivery-flow.json`, the ceiling `bin/convoy-advance` enforces across the three roles. A lower cap leaves a started ticket waiting for the session of another one (`tests/delivery-agents-test.sh` holds the two equal; `tests/fresh-sessions-isolated-city-test.sh`, local-only, shows two author sessions alive at once) |
| `agents/delivery-author/overlay/.claude/` | the settings and the guard that stop an author from handing the writing to a sub-agent, and the local settings that keep the operator's account plugins out of the session |

## How Gas City holds a step (tried on 1.4.1, isolated city, 2026-10-06)

A step declares `[steps.check] max_attempts = 3` and `[steps.check.check]
mode = "exec"`, `path = ".gc/scripts/checks/ticket-author-check.sh"`. What
was observed:

- The check receives **no argument** (`args` is not passed). It receives an
  environment: `GC_BEAD_ID`, the bead of the attempt just closed (it carries
  `gc.step_id` and `gc.root_bead_id`; the root carries `gc.input_convoy_id`),
  and `GC_CITY_PATH`, the city root. Its working directory is the root of
  the store the bead lives in.
- Its `HOME` is **the city root**, not the home of the account (seen on the
  real city under Gas City 1.5.0, af-r35155: the `workspace` gate looked for
  the work tree under the city root and refused three times a ticket whose
  work tree was in place). `bin/ticket-author` therefore places the work
  trees under the home of the account as the password database gives it,
  the same for the author session and for the check.
- Exit 0: the next step opens.
- Any other exit: a new attempt of the same step goes back to the same
  session; the stderr of the check is kept in `gc.attempt_log`.
- After `max_attempts`, the step fails; with `gc.on_fail = "abort_scope"`
  the scope fails, the steps that remain are closed `skipped`, and the
  workflow ends `fail`.

The path is resolved in the store of the ticket. `bin/factory-build-gates`
(run by `bin/factory-boot` and `bin/factory-guard`) copies the check from
`assets/scripts/checks/` into `.gc/scripts/checks/` of the city root and of
each rig, and reports a missing or modified copy.

## `bin/ticket-author`

```bash
./bin/ticket-author locate af-t1                                  # the marked convoy that tracks the ticket
./bin/ticket-author start af-convoy af-t1                         # work tree, branch, session; run again = read again
./bin/ticket-author demonstrate af-convoy af-t1 --repo <worktree> --profile <profile> --dataset <name> -- <command>
./bin/ticket-author demonstrate af-convoy af-t1 --repo <worktree> --profile <profile> --dataset <name> --path /page
./bin/ticket-author gate af-convoy af-t1 --step workspace|red|code|demonstration|exit
./bin/ticket-author release af-convoy af-t1                       # removes the work tree of a ticket that has exited
./bin/ticket-author check                                         # the gate of the step named by GC_BEAD_ID
```

Every answer is one JSON object on stdout; `check` also writes the refusal
on stderr.

| Exit | Meaning |
|---|---|
| 0 | done, or the step is proven |
| 1 | refused (`{"ok": false, "error": "refus : …"}`); nothing was written unless the answer says what was |
| 4 | the convoy does not carry the mark: « pas un convoi du nouveau flux » |

**`start`** creates the work tree and the branch `ticket/<ticket>` at the tip
of `integration/<spec>`, and records the branch (`set-branch`) and the
session (`set-session`). It is refused for a ticket the dispatch door did
not start, for a closed ticket, when the integration branch is not open,
and for a session that already took another ticket of the convoy: one fresh
session per ticket. It also writes the model the author role runs on
(`bin/convoy-state set-model`, role `author`): what the code review compares
the model of its reviewer with. When that model cannot be read nothing is
written, and the review says so.

**`demonstrate`** launches the product at the head commit of the ticket
branch through `bin/project-launch`, captures the demonstration line on it
through `bin/evidence-capture` (piece `demonstration`), and stops the
product. The command must exit 0; it receives the address in
`PRODUCT_ADDRESS`. `--path` captures a screenshot instead.

**`gate`** writes nothing. It reads `bin/convoy-state show`, the pieces
through `bin/evidence-capture verify`, and the tip of the ticket branch.

| Step | Proven when |
|---|---|
| `workspace` | the session and the branch are recorded on the ticket, the work tree is on that branch, the branch leaves from the integration branch |
| `red` | the red is proven and the criterion tests frozen (`bin/tdd-step`); no test review precedes the freeze, the code review reads them after the green (ADR-0030 L3); nothing asked of a `prefactoring` |
| `code` | the criterion tests and the profile's regression are green at the tip (`bin/tdd-step green`, ADR-0030 L1); for a `prefactoring`, its regression at the tip |
| `demonstration` | the piece `demonstration` verifies, was captured on the launched product, and is at the tip; nothing asked of a `prefactoring` |
| `exit` | a Ticket Exit is recorded; « terminé » is at the tip, with its Handoff |

Once a Ticket Exit other than « terminé » is recorded after the session took
the ticket, the gates of the steps that remain pass: the session closes
them and leaves. The destination of that exit is fixed by `bin/ticket-exit`
(parking, repair, push), and such a ticket is never merged.

A **stopped** ticket (`bin/convoy-state`, `stop`: a criterion already green,
a second amendment, or a stop a test review wrote before ADR-0030 L3) is
refused by every gate: the step comes back, its attempts are spent, and the
sequence ends failed with the remaining steps skipped. The code that
stopped the ticket is what raises it to the operator.

## What bounds the author

- **The approved intent, not a list of files.** The Declared Scope orders
  tickets; no gate reads it. A file touched outside it is written in the
  records of the Handoff (`files_outside_declared_scope`) by code.
- **A deviation of a sibling ticket is never a convention.** The formula
  says it at the `workspace` step, where the author receives the Ticket
  Handoffs of its blockers: what a Handoff lists under « Écarts » or « Non
  fait » is a fact to know, never a precedent to follow (Spec af-wf4w5r §5,
  « Précédent »). No gate reads it: the rule is the formula's text, verified
  by reading.
- **Characterization tests first.** A `prefactoring` on a project with no
  test at its start commit is refused by `bin/tdd-step prefactoring` until a
  first commit adds nothing but tests, green on the product as received
  (`docs/TDD_STEP.md`, « Prefactoring »).
- **A behaviour the Spec fixes.** The author commits nothing that changes it
  and takes the exit `planning_exception`: the ticket is parked, its branch
  is not merged.
- **No writing sub-agent.** `agents/delivery-author/overlay/.claude/settings.json`
  runs `guards/author-subagent-guard` before every `Agent`, `Task` or
  `Workflow` call. Only the types `Explore` and `Plan` pass; any other
  type, a call with no type, and a workflow are blocked (exit 2).
  `bin/role-adoption-trial` asks a real author session to launch a
  sub-agent that writes and one that reads, and records what happened;
  `bin/dispatch-door` refuses the author role without a passing trial for
  the current distribution. Limit: a read-only sub-agent still has a shell.
  The guard covers the tool the session is given, not every way to write.
- **Only the skills of its role.** The plugins and skills the operator
  enabled on their Claude account are synced into every Claude Code session
  of the machine; one of them brings a `code-review` skill.
  `agents/delivery-author/overlay/.claude/settings.local.json` turns that
  sync off for the author's work directory (`syncClaudeAiPlugins`,
  `syncClaudeAiSkills`: Claude Code reads them from a local settings file,
  not from `settings.json`). The same adoption trial asks the session to
  launch a review and fails if one is listed or launched.

## Tests

| What | Where |
|---|---|
| each command, one test per pass and per refusal, on a fake tracker; the state is read again after a refusal | `tests/ticket-author-test.py` |
| the session field | `tests/convoy-state-test.py` |
| « terminé » without the demonstration proof | `tests/ticket-exit-test.py` |
| the guard, call by call | `tests/author-subagent-guard-test.py` |
| the check materialised in the city root | `tests/factory-build-gates-test.py` |
| the real formula on a real controller, started by the real order, with a scripted author (local only) | `tests/ticket-author-isolated-city-test.sh` |
| a real author session and the guard (outside CI) | `./bin/role-adoption-trial run --role author` |
