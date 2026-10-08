# Project Planning Profile (B02)

## Status and purpose

`bin/project-planning-profile` lets a project register with a City through
one Project Planning Profile: a single JSON object naming that project's
authoritative Project Knowledge, Work Graph, participating rigs, checks,
risk thresholds, autonomy policy and genuine rig-local extensions, without
copying Factory-wide configuration and without carrying any SayMyName-
specific field. The tool is stateless — `register` is a pure function of the
profile and the City rig registry it is given on that call — so registering
one project can never make it a global default or leak state into another
project's registration.

## Run it

```bash
./bin/project-planning-profile validate tests/fixtures/project-planning-profile/profiles/project-a.json
./bin/project-planning-profile register tests/fixtures/project-planning-profile/profiles/project-a.json \
    --city-registry tests/fixtures/project-planning-profile/city-registry.json
python3 tests/project-planning-profile-test.py
```

`validate` reports `{"valid": true}` or an actionable diagnostic naming the
exact field at fault. `register` re-validates the profile, checks every
`participant_rigs` entry against the City's rig registry (the same check
`project-isolation-oracle` uses for `agent_scope`), and prints a
`agent-factory-project-registration/v1` record: the project's effective
scope, its checks, risk thresholds, autonomy policy and extensions, and
nothing else — no Factory-wide field and no marker declaring the project a
default.

## Profile contract (`agent-factory-project-planning-profile/v1`)

| Field | Meaning |
| --- | --- |
| `project_id` | Safe identifier for the project. |
| `project_knowledge.path` | Path to the project's authoritative Project Knowledge; must resolve to a real file. |
| `work_graph.path` | Path to the project's authoritative Work Graph; must resolve to a real file. |
| `work_graph.rigs` | Optional; every rig named here must already be in `participant_rigs`, or the profile is rejected as internally contradictory. |
| `participant_rigs` | The rigs this project spans; checked against the City's rig registry at `register` time — the same scope model P05 (`project-isolation-oracle`) enforces at the filesystem boundary. |
| `checks` | Project-selected check names. |
| `risk_thresholds` | Project-selected risk thresholds. |
| `autonomy_policy.safety` | Common people/data safety principles (below); a profile may add stricter keys but can never set one of the required ones to a falsy value. |
| `extensions` | Genuine rig-local extensions. |

Any field or value anywhere in the profile matching `saymyname` (case
insensitive), or a top-level key belonging to Factory-wide-only
configuration (`cost_policy`, `mail_format`, `escalation_contract`,
`standing_admin_allowlist`, `inter_agent_mail_format`), fails validation
before registration proceeds.

## Common safety principles

`autonomy_policy.safety` always resolves with these keys present and truthy:

- `no_production_without_human`
- `no_personal_data_widening_without_human`
- `no_unrecoverable_destruction_without_human`
- `no_external_publication_without_human`
- `no_spend_without_human`

A profile that omits one inherits it as `true`. A profile that sets one to
`false` is rejected outright — project policy can tighten the common
boundary (add its own stricter `risk_thresholds` or extra `safety` keys) but
can never silently disable it.

## Acceptance mapping

| Acceptance criterion | How the tool and tests check it |
| --- | --- |
| Registration succeeds without any SayMyName-specific field or copied Factory-wide configuration. | `test_registration_succeeds_without_saymyname_or_factory_wide_fields`; `test_saymyname_specific_field_is_rejected` and `test_copied_factory_wide_configuration_is_rejected` prove both are rejected before registration. |
| Missing or contradictory authoritative sources fail with an actionable diagnostic. | `test_missing_authoritative_source_fails_with_actionable_diagnostic` names the exact missing path; `test_contradictory_authoritative_sources_fail_with_actionable_diagnostic` names the rig `work_graph.rigs` and `participant_rigs` disagree on. |
| Project policy can tighten but cannot silently disable common people and data safety principles. | `test_project_policy_cannot_disable_a_common_safety_principle` proves rejection; `test_project_policy_can_tighten_safety_without_rejection` proves a profile declaring its own stricter thresholds still validates. |
| The profile applies the isolation and explicit-grant behavior selected by P05. | `register` checks every `participant_rigs` entry against the City's rig registry exactly as `project-isolation-oracle` checks `agent_scope`; `test_registration_rejects_a_rig_outside_the_city_registry` proves the rejection. |
| The fixture City can load two different project profiles without treating either as a global default. | `test_fixture_city_loads_two_profiles_without_either_becoming_default` registers `project-a` and `project-b` against the same registry, interleaved, and proves each keeps its own scope/checks/extensions with no `default`/`is_default` marker on either result. |

## Scope of proof

- **TARGET**: any project registering with a City through one Project
  Planning Profile, with no Factory-wide or other-project field leaking in
  and no silent weakening of common safety principles.
- **CONFIGURED**: the `agent-factory-project-planning-profile/v1` contract
  and the fixture profiles/knowledge/work-graphs under
  `tests/fixtures/project-planning-profile/`.
- **OBSERVED**: the deterministic validate/register CLI output and the ten
  acceptance-mapped tests above, reproduced identically on every run.
- **PROVEN**: within this fixture set, that registration is rejected before
  any effect when sources are missing/contradictory, when a SayMyName or
  Factory-wide field is present, or when policy tries to disable a common
  safety principle; and that registering two distinct projects is mutually
  side-effect-free.

Not proven here: a live Gas City actually loading a registered profile into
a running Planning Run (that is B03/B04's concern), or a schema for rig-
local extension *content* beyond "this tool does not interpret it."

## Declared human approver (A6b, W04)

`human-approver --project <id> [--config-dir <dir>]` reports the human
approver a project has declared in its own `config/projects/<id>.toml`
file (the file `lib/project_registry.sh` already reads for rig
protection data) -- one field, `human_approver`, added to that same file
rather than a second registry. `bin/spec-approve bd-approve` refuses to
record any `--approved-by` other than the value this reports, so a wrong
approver on a Spec bead is rejected mechanically instead of trusted from
the caller. Missing project file or missing/blank `human_approver` fails
with an actionable diagnostic naming the exact path at fault; nothing is
written.

```bash
./bin/project-planning-profile human-approver --project agent-factory
```

## Extended descriptor (T04, af-xqgvat: "descripteur de projet", un rig = un projet)

Spec af-oohx2x .12 extends the same Project Planning Profile so it also
serves the Cockpit: every project declared to the Factory — today `usine`
and `saymyname` — has one descriptor under `config/project-descriptors/`
(contract `agent-factory-project-descriptor/v1`), distinct from
`config/projects/*.toml` (which describes rigs, not projects — see
`lib/project_registry.sh`). One rig belongs to exactly one project.

| Field | Meaning |
| --- | --- |
| `project_id` | Safe identifier for the project (the project key: `agent-factory`, `saymyname`). |
| `display_name` | The project's name in the Operator Language. |
| `rigs` | The rigs this project spans. |
| `knowledge_repo` | `owner/repo` pointer to the project's knowledge repository — may be a different repo than this one (SayMyName's knowledge lives in `saymyname-app/Say-my-name-product`), so it is checked for shape only, never for local existence. |
| `roadmap_path` | Path to the project's structured roadmap (e.g. `docs/roadmap.toml`), inside `knowledge_repo` — also not checked for local existence, for the same reason. |
| `rituals_status_command` | The command that reports this project's rituals status (e.g. `bin/rituals-status` for the Factory itself, `tools/rituals-status.sh` for SayMyName). |
| `promotion_branch` | Optional, per rig: `{from, to}`. Absent for a rig means it has no Promotion Step. Every key must already be in `rigs`, or the descriptor is rejected as internally contradictory. |

A descriptor carries no production/deployment field and no language field
(Operator Language is one Factory-wide field on `operator.toml`) —
`describe` rejects a `production` or `language` key outright.

```bash
./bin/project-planning-profile describe config/project-descriptors/agent-factory.json
./bin/project-planning-profile describe config/project-descriptors/saymyname.json
./bin/project-planning-profile list
```

`describe` validates one descriptor and prints it as JSON, or
`{"valid": false, "error": "..."}` naming the exact field at fault.
`list` validates every `config/project-descriptors/*.json` file (or
`--descriptors-dir`) and prints the declared projects — `project_id`,
`display_name`, `rigs` — as JSON.

`lib/project_registry.sh`'s `project_registry_check_project_coverage
<descriptors_dir> <rig...>` is the CI-run check that a rig belongs to
exactly one project: it fails loudly, naming the rig, if a rig Gas City
has registered belongs to no descriptor's `rigs` or to more than one
(`tests/project-registry-test.sh`). Adding a project is a new
`config/project-descriptors/*.json` file plus a PR; per `AGENTS.md`, a PR
that adds or removes a project does not merge itself — `pr-autopilot`
holds it for Benjamin.

### Real descriptors

- `config/project-descriptors/agent-factory.json`: rig `agent-factory`, no
  `promotion_branch` (the Factory has no Promotion Step), roadmap and
  rituals status from T03 (`docs/roadmap.toml`, `bin/rituals-status`).
- `config/project-descriptors/saymyname.json`: rigs `saymyname-backend`
  and `saymyname-frontend`, each promoting `dev` → `main`, knowledge repo
  `saymyname-app/Say-my-name-product`, roadmap `knowledge/roadmap.toml`,
  rituals status `tools/rituals-status.sh`.

## Launch declarations and `bin/project-launch` (T01, af-m8m1kc)

Spec af-wf4w5r .12 (D01) requires a project's launch recipe and entry
points to live in its profile so the Delivery Workflow can launch any
project the same way: an author proving a demonstration line, an Evaluator
judging a ticket, and an Acceptance Session judging a Delivered Outcome all
launch the product through the same `bin/project-launch`, never a
hand-typed command.

A descriptor's optional `launch` block is validated by the same `describe`
command, and -- unlike every other descriptor field -- is all-or-nothing:
declaring `launch` at all requires every one of these sub-fields, or
`describe`/`validate` fails loudly naming exactly which is missing:

| Field | Meaning |
| --- | --- |
| `recipe` | argv tokens to launch the product; `{python}`, `{port}`, `{dataset}` are substituted by `project-launch`. |
| `entry_points` | the product's public interfaces (`kind`, `method`, `path`), named so an Evaluator or criterion test knows where to look. |
| `health_probe` | `{path, expect_status}` — polled by `project-launch start` until it answers or the timeout expires. |
| `datasets` | named synthetic dataset files (fixed `generated_at` time included) a launch can select with `--dataset`. |
| `test_perimeter` | paths a ticket's red step may write criterion tests under. |
| `frozen_harness_paths` | test harness/config paths frozen at the ticket's freeze step. |
| `test_command` | runs one criterion test and writes its per-test report: it carries `{test}` (the test id) and `{report}` (the JUnit XML file to write, where an assertion `failure` is distinct from an `error` and from `skipped`); read by `bin/tdd-step` (`docs/TDD_STEP.md`). |
| `seam_mode` | `black_box` or `import_rule` — how a criterion test is proven to go through a real entry point. |
| `regression_command` | the `prefactoring` regime's before/after command; also the tests `bin/spec-integration` runs on each merged result of the integration branch (T18, `docs/SPEC_INTEGRATION.md`): it runs from the root of a clean tree and exits 0 when green. |
| `k` | consecutive green runs required at the ticket's green step. |
| `red_error_types` | optional — error types (e.g. `AttributeError`) that are a valid red on a library seam, where a missing symbol is the red. Absent: only an assertion failure is a red. |
| `screens` | optional, required by `bin/prototype-fidelity` (T16, `docs/PROTOTYPE_FIDELITY.md`) — the screens compared to the Validated Prototype: `[{name, path, states}]`, the path the launched product serves the screen at and its prototyped states. A state is the dataset of the same name and belongs to one screen; a duplicate name, a path that does not start with `/`, an empty list of states or a state that is no declared dataset is rejected. |
| `anchors` | optional — the equivalent of the anchors for an interface that is **not a web page** (a command line, an API; T35, spec af-wf4w5r §12). Exactly one of: `{"equivalent": [{name, entry_point, observable}]}`, what stands for the anchors of a screen — each a unique name, the declared entry point that answers it (`"METHOD path"`) and the observable read there (a field, an exit status, a line of output); or `{"not_applicable": "<reason>"}`. An empty list, a missing reason, both forms at once, an unknown field, a duplicate name or an entry point that is not declared is rejected. `describe` renders it. |
| `import_rule` | optional, required by `bin/tdd-step` when `seam_mode` is `import_rule` — `{product_import, entry_point_import}`, two regular expressions applied to each line of a test: a line that imports the product must import one of its entry points. |

A descriptor with no `launch` block at all (e.g. the Factory's own
`agent-factory.json`) is unaffected — `describe` reports `launch: null`,
and `bin/project-launch start` refuses that project outright, naming the
missing declaration, before anything is spawned.

```bash
./bin/project-planning-profile describe tests/fixtures/delivery-fixture-city/descriptor.json
./bin/project-launch start tests/fixtures/delivery-fixture-city/descriptor.json \
    --commit HEAD --dataset content --state-file /tmp/launch.json
./bin/project-launch stop --state-file /tmp/launch.json
```

`--repo-root <dir>` (before `start`) names the repository of the product
when it is not the Factory's own; the profile tool is always the one next
to the launcher (T10: `bin/tdd-step` launches the product of a ticket
worktree this way).

`start` resolves `--commit` to an exact SHA and checks it out into a fresh
`git worktree` — never the caller's current working tree, so an
uncommitted local change is never what gets served — picks a free
127.0.0.1 port, substitutes it (and the chosen dataset's absolute path)
into `recipe`, and polls `health_probe` until it answers or `--timeout`
(default 15s) expires, printing one JSON record (`address`, `port`, `pid`,
`worktree`, `commit`, `dataset`). `stop` reads that record back from
`--state-file`, terminates the process, removes the worktree, and frees
the port. Two concurrent launches each get their own port and worktree and
do not disturb each other; stopping one leaves the other answering.
`tests/project-launch-test.py` and `tests/fixtures/delivery-fixture-city/`
are the fixture project and its proof.

### The same flow whatever the language or the layer (T35)

The Delivery Fixture City holds a second project,
`tests/fixtures/delivery-fixture-city-api/`: a JSON API on Node.js
(`server.js`: `GET /items`, `GET /health`), another language than the first
project and no web page. Its profile declares the same `launch` block — the
recipe names `node`, the test command is its own `tests/harness.js` (one
JUnit XML report per test, an `AssertionError` a `failure`, anything else an
`error` with its type), the regression command its `tests/regression.js` —
no `screens`, and `anchors.equivalent` in their place.

No script of the flow knows which project it works on: the launcher, the red
step, the freeze, the green step, the prefactoring regime, the evaluation,
the merge and the ticket-end gate read the profile. A ticket of a project
with no screen and no Validated Prototype passes condition 4 of the gate
(fidelity) as a ticket that touches no screen.

| Proof | What it shows |
| --- | --- |
| `tests/fixture-second-project-test.py` (CI) | the launch command starts it by its recipe and its probe answers; `tdd-step red`, `freeze`, `green` and `prefactoring` pass on one of its tickets, with criterion tests written in JavaScript; each refusal leaves the tracker and the evidence store as they were; `describe` renders the anchors' equivalent |
| `one-ticket-second-project.json` (CI, `docs/FIXTURE_CITY_ORACLE.md`) | one of its tickets walks the nine lifecycle states and is closed by the ticket-end gate, observed at the same events and with the same verdicts as a ticket of the first project |
| `tests/second-project-isolated-city-test.sh` (local-only) | on a real controller, order and tracker, one of its tickets goes from started to closed by the gate through the real `mol-ticket-author`, `mol-code-review` and `mol-ticket-evaluation` |

Limits. The `anchors` declaration is read by `describe` only: no gate
compares a delivered API to a prototype, and a profile with neither `screens`
nor `anchors` is still accepted. The black-box seam of `bin/tdd-step` records
HTTP entry points: a project whose only interface is a command line has no
mechanical proof of its seam yet. A recipe names its interpreter itself
(`node`); only `{python}` is substituted by the launcher.
