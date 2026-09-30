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
