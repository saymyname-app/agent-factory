# Observe planning and delivery changes without idle model calls (B09)

## Status and purpose

`bin/factory-observe` lets an operator monitor Planning Runs, delivery
progress and adaptation measures through deterministic observations that
wake judgment only when a new actionable fact appears. `observe` diffs a
caller-supplied structured snapshot against the last-observed one persisted
in a host-local state file: an unchanged snapshot diffs to nothing and makes
zero model/agent calls; a new or changed fact wakes exactly the smallest
qualified role for that fact's area, once, with the fact itself preserved
verbatim as evidence. The same call re-evaluates any declared exemption or
automatic handoff against its own named evidence -- it activates only when
every required signal holds, and restores (deactivates) the instant one
regresses.

This mirrors the policy/state split the pre-refactor improvement-axes
register used (policy versioned and human-edited, state host-local and
mutable; that register is retired, its code in Git history:
`decisions/PRE_REFACTOR.md`) and the locked-register concurrency discipline
`bin/planning-exception` (B08) already proved. `observe` remains the public
caller-supplied JSON seam. `live` is its VM adapter: the existing
`factory-watchdog` order calls it every five minutes, it collects bounded
Beads, Git and GitHub facts, and routes only new transitions through the
roles already declared by the policy. It creates no service, daemon or
second orchestrator.

## Run it

```bash
./bin/factory-observe policy-validate
./bin/factory-observe observe --snapshot snapshot.json --evidence evidence.json
./bin/factory-observe live
./bin/factory-observe status --json
./bin/factory-observe measures-validate --measures measures.json
./bin/factory-observe measures-show --measures measures.json
python3 tests/factory-observe-test.py
```

`snapshot.json` is `{"areas": {area: {id: fact, ...}, ...}}` -- e.g.
`{"areas": {"delivery": {"af-x": {"status": "in_progress"}}}}`. `evidence.json`
maps an exemption name to its signal booleans, e.g.
`{"tactical-resolve-auto-handoff": {"decision_kind_tactical": true, "patch_not_required": true}}`.

## Lifecycle

| Subcommand | Effect |
| --- | --- |
| `policy-validate` | Read-only. Validates `config/factory-observe-policy.json` against its contract (`lib/factory_observe.py::validate_policy`, hand-written — no JSON Schema file backs it). |
| `observe --snapshot --evidence` | Diffs the current snapshot against the persisted one; wakes the smallest qualified role once per new/changed fact (empty diff => `action: "none"`, zero wakes); re-evaluates every declared exemption against `--evidence`, activating/restoring only on a transition; persists the new snapshot and history under an exclusive file lock. |
| `live` | Reads marked or held Beads and active durable human requests, the Factory Git revision and the latest 50 GitHub PRs. The first pass persists a baseline without waking anyone; later transitions and their pending routes are persisted before the alert, then mailed with the route id as a stable deduplication key to the holding worker or, when no worker owns the fact, the Mayor. A failed mail stays queued for the next pass; it retries the worker while that session exists and falls back to the Mayor if the worker disappears. The baseline and a final snapshot at +2 h are persisted; the due final is itself one new fact and wakes the Mayor once. |
| `status [--json]` | Read-only. Reports the areas currently tracked, current exemption activation, and recent history. |
| `measures-validate --measures` | Read-only. Validates a measures document against its contract (`lib/factory_measures.py::validate_measures`, hand-written — no JSON Schema file backs it). |
| `measures-show --measures` | Read-only. Prints each work class's six measures, kept separate -- never summed or blended across classes. |

## Acceptance mapping

| Acceptance criterion | How the tool and tests check it |
| --- | --- |
| Repeated observation of unchanged state makes zero model calls. | `diff_snapshot` over identical inputs returns `[]`; `test_observe_called_twice_with_unchanged_input_wakes_zero_both_times` and `test_cli_observe_twice_with_identical_snapshot_wakes_zero_the_second_time` prove a second `observe` call with the same snapshot returns `action: "none"`, `wakes: []` -- the caller that only acts on `wakes` never invokes a model. |
| A newly actionable fact wakes the smallest qualified role once and preserves its evidence. | `test_new_delivery_fact_wakes_the_smaller_delivery_worker_role_not_the_mayor` proves `select_smallest_qualified_role` picks the lower-rank role over a more expensive fallback; `test_a_second_identical_fact_does_not_wake_again` and `test_evidence_pointer_is_preserved_verbatim_across_state_persistence` prove a fact wakes exactly once and its `before`/`after` values survive a round trip through the persisted state file. |
| Live VM reads stay silent until a real transition. | `LiveObservationTest` drives the public `live` command with minimal R2/A2 incident shapes. It proves an identical second read sends no mail, an `unblocked` resume goes once to the holding worker, the transition and pending route are durable before the alert and the route id is its stable deduplication key, A2's human request and answer remain in evidence while the Mayor is woken once, a failed route retries an active worker but falls back once to the Mayor after that worker disappears, and the persisted +2 h final wakes once. |
| Measures separate lost decisions, escaped defects, human rework, maintainability, elapsed time and tokens by comparable work class. | `lib/factory_measures.py`'s schema requires all six keys per work class; `test_two_work_classes_keep_distinct_values_no_cross_contamination` proves two work classes keep distinct values with no leakage, including after mutating one class's returned dict. |
| Every material adaptation or gate records baseline, reason, signal, cost, review point and retain/replace/remove outcome in one register. | `docs/ADAPTATION_REGISTER.md` AR-004 records this adaptation's baseline, but, selected adaptation, viable alternative, evidence, observed cost, bounded reversibility, review point and retain/replace/remove rule, in the same single register as AR-001..003; `test_register_has_an_entry_for_this_adaptation` proves the entry and every required field exist. |
| Review exemptions or automatic handoffs can activate only under predefined evidence and restore on regression. | `evaluate_exemption`/`apply_exemptions` require every declared `requires` signal to be true before activating, record an `activated` transition only on the rising edge and a `restored` transition only on the falling edge, and never re-emit a transition while the state is unchanged; `ExemptionTest` (including an end-to-end CLI activate-then-regress pass) proves all three paths. |

## Scope of proof

- **TARGET**: every project rig supplies the same bounded live facts and can
  resolve an owning worker without falling back to the Mayor.
- **CONFIGURED**: the `agent-factory-observe-policy/v1` role/exemption
  policy (`config/factory-observe-policy.json`), the
  `agent-factory-observe-measures/v1` measures contract
  (hand-written in `lib/factory_measures.py`; the JSON Schema file that once
  documented its shape had no reader and was removed, `decisions/PRE_REFACTOR.md` — F20),
  the caller-supplied JSON seam, and the existing five-minute
  `factory-watchdog` order as the live trigger.
- **OBSERVED**: deterministic snapshots of authoritative Beads/Git/GitHub
  interfaces, with request text represented by a fingerprint and Bead id so
  sensitive prose is not copied into runtime logs.
- **PROVEN**: by the public-interface tests above, identical live reads are
  silent, a transition and its pending route are readable before their alert,
  and the stable route id prevents a restart from delivering the same live
  mail twice. Failed delivery is retried and reassigned to the Mayor if its
  worker disappears; a human request is not erased; and the initial/final
  two-hour evidence is persisted under the same `fcntl.flock` discipline as
  `observe`.

Not proven here: live adoption beyond the Factory VM, or that a particular
two-hour canary contains enough useful transitions for a PASS rather than an
INCONCLUSIVE verdict. The final evidence lets the Mayor make that verdict;
the collector does not invent it.
