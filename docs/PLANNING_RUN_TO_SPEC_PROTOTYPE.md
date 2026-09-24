# Planning Run to Spec (B03)

## Status and purpose

`bin/planning-run-to-spec-oracle` proves that a simple request can stay in
one healthy interactive Planning Session, establish Shared Understanding
with the human, and synthesize one readable, reproducible Spec -- without
the mandatory Wayfinder ceremony or another interview round, and without
loading any context beyond what the Project Planning Profile (B02)
declared authoritative. The tool is a deterministic synthetic prototype,
not a live Gas City Planning Run: it takes a Planning Session record (the
request, its declared context, its target rigs and the Shared
Understanding reached so far) and either synthesizes a Spec artifact or
returns the session to planning.

## Run it

```bash
./bin/planning-run-to-spec-oracle run tests/fixtures/planning-run-to-spec/sessions/simple-request.json \
    --city-registry tests/fixtures/planning-run-to-spec/city-registry.json \
    --out /tmp/spec-out
python3 tests/planning-run-to-spec-oracle-test.py
```

`run` prints one of two outcomes: `{"result": "spec_synthesized", "spec":
{...}}` or `{"result": "returned_to_planning", "signal": "...", "reason":
"..."}`. A structural violation (undeclared context, an unregistered
target rig, a simple request forced through the Wayfinder ceremony or a
second interview round) is rejected outright with a non-zero exit and
`{"result": "rejected", "error": "..."}` before any Spec is attempted.

## Session contract (`agent-factory-planning-session/v1`)

| Field | Meaning |
| --- | --- |
| `session_id` | Stable id; the synthesized Spec's identity (`spec-<session_id>`) is a pure function of it. |
| `request.complexity` | `"simple"` triggers the no-ceremony rule below. |
| `target_rigs` | Rigs this run touches; each must already be in the City's rig registry (the `--city-registry` argument), the same check `project-planning-profile register` applies to `participant_rigs`. |
| `declared_context.project_knowledge_path` / `.work_graph_path` | The run's only legitimate sources -- normally a project's registered Project Planning Profile (B02) paths. |
| `context_probe` | What the run actually loaded; any path not in `declared_context` is rejected before synthesis. |
| `wayfinder_ceremony_invoked`, `interview_rounds` | A `"simple"` request may not set the former `true` or the latter above `1`. |
| `signals` | Explicit `contradiction` / `missing_trace` / `undecided_behavior` / `new_test_seam` markers a session may carry; any present sends the run back to planning immediately. |
| `shared_understanding` | Confirmed entries, each tagged with one of the seven required topics below. |

## Spec sections and their Shared Understanding topics

| Spec section | Shared Understanding topic |
| --- | --- |
| `behavior` | `behavior` |
| `boundaries` | `boundary` |
| `decisions` | `decision` |
| `acceptance_evidence` | `acceptance_evidence` |
| `provenance` | `provenance` |
| `experiments` | `experiment` |
| `non_objectives` | `non_objective` |

A required topic with zero confirmed entries is itself a missing trace:
the run returns to planning naming the exact missing topic rather than
inventing that section.

## Identity, digest and single-artifact discipline

A synthesized Spec's `spec_id` depends only on `session_id`; its
`content_digest` is a canonical SHA-256 of its `sections` object. Running
the same session twice reproduces byte-identical output. `run --out
<dir>` writes exactly one file, `<spec_id>.json`; repeated runs overwrite
it with the same bytes rather than accumulating a second prose artifact
or a Release Contract that would repeat the Spec.

## Acceptance mapping

| Acceptance criterion | How the tool and tests check it |
| --- | --- |
| The run loads only the Project Planning Profile's declared authoritative context. | `test_run_loads_only_declared_authoritative_context`; `test_probing_an_undeclared_source_is_rejected_before_synthesis` proves an extra probed path is rejected before any Spec is attempted. |
| The Spec contains behavior, boundaries, decisions, acceptance evidence, provenance, experiments and non-objectives. | `test_synthesized_spec_contains_all_required_sections`. |
| The Spec has a stable identity and reproducible content digest. | `test_spec_identity_and_digest_are_reproducible_across_runs`, `test_spec_digest_changes_when_confirmed_content_changes`. |
| A real contradiction, missing trace, undecided behavior or new test seam returns to planning instead of being invented. | `test_contradiction_returns_to_planning_instead_of_inventing_a_spec`, `test_explicit_missing_trace_returns_to_planning`, `test_undecided_behavior_returns_to_planning`, `test_new_test_seam_returns_to_planning`, `test_missing_required_topic_returns_to_planning_rather_than_fabricating` (a missing topic is treated as a missing trace, not fabricated). |
| No Release Contract or second prose artifact repeats the Spec. | `test_repeated_runs_write_exactly_one_spec_artifact`, `test_repeated_runs_write_byte_identical_artifacts`. |

Also proven, in support of the "one healthy interactive session" framing:
`test_simple_request_does_not_require_wayfinder_ceremony` and
`test_simple_request_does_not_require_another_interview_round` show a
`"simple"` request is rejected outright if the session tries to force
either; `test_target_rig_outside_registry_is_rejected` reuses B02/P05's
rig-registry check at the Planning Run boundary.

## Scope of proof

- **TARGET**: any simple request that reaches one Spec through a single
  healthy Planning Session, with no invented content and no duplicated
  prose artifact.
- **CONFIGURED**: the `agent-factory-planning-session/v1` and
  `agent-factory-planning-run-spec/v1` contracts, and the fixture context,
  city registry and eleven session records under
  `tests/fixtures/planning-run-to-spec/`.
- **OBSERVED**: the deterministic `run` CLI output and the fifteen
  acceptance-mapped tests above, reproduced identically on every run.
- **PROVEN**: within this fixture set, that a Spec is synthesized only
  when every required topic traces to confirmed Shared Understanding and
  no return-to-planning signal or undeclared-context probe is present;
  that its identity and digest are reproducible; and that repeated runs
  never produce a second artifact.

Not proven here: a live Gas City Planning Session actually driving an
interactive interview with a human (that is the surface B03 targets, not
this synthetic harness), or approval/freeze-by-digest of a synthesized
Spec (B05's concern).
