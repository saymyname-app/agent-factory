# Role, concurrency and retention qualification prototype (P06)

## Status and purpose

`bin/role-qualification-oracle` is a bounded, deterministic prototype
comparing provider-independent planning roles, an initial concurrency
ceiling, and decision-session retention against declared evidence. It is a
synthetic comparison over an evidence manifest, not a live multi-provider
load test — the same scope `planning-allocation-prototype` (P02) used for
allocation viability and `planning-run-resume-oracle` (P04) used for
cross-provider continuity. P04 explicitly left concurrency and retention
economics to P06; this prototype closes that gap at the same evidence-bound
level.

## Run it

```bash
./bin/role-qualification-oracle validate
./bin/role-qualification-oracle run
python3 tests/role-qualification-oracle-test.py
```

`run` emits one deterministic JSON result: per-work-class, per-provider load
evidence (quality, lost decisions, rework, elapsed time, tokens, machine
pressure), whether each provider's role mapping meets one shared acceptance
standard, the chosen concurrency ceiling and whether any reduction from the
initial ceiling was justified by observed evidence, the chosen
decision-session retention and why, and whether every exercised role stays
within the no-Astra/no-Fable/medium-or-lower ceiling. The scenario source is
`config/role-qualification-prototype.json`.

## What the prototype models

- **Work classes.** `simple` and `wayfinding` each declare one role per
  supported provider (`codex`, `claude`) and one load-evidence entry per
  role. The oracle rejects a manifest where a work class's provider set
  differs from another's — the same role mapping must be qualified against
  the same provider set everywhere.
- **Acceptance standard.** `acceptance_standard.min_quality` and
  `max_lost_decisions` are declared once and applied identically to every
  provider's evidence in every work class — "the chosen role mapping meets
  the same acceptance standard across supported providers" is a computed
  fact (`providers_meeting_standard`), not an assertion.
- **Concurrency.** `concurrency.initial_ceiling` must be at least twice
  `minimum_ceiling` — a deliberately high starting point, not a
  cautious default. The oracle only lowers the chosen ceiling to
  `minimum_ceiling` when `observed_host_pressure` is true or
  `observed_completion_quality_ok` is false; absent that evidence the
  initial ceiling stands.
- **Retention.** `retention_candidates` must include a `zero` candidate
  (`retained_turns: 0`). If `zero.planning_graph_evidence_sufficient` is
  true, zero retention is selected. Otherwise the oracle picks the shortest
  candidate whose `diagnostic_need_evidenced` is true, and refuses to run at
  all if no candidate has an evidenced diagnostic need — retention is never
  assumed.

## Acceptance mapping

| Acceptance criterion | How the oracle checks it |
| --- | --- |
| Quality, lost decisions, rework, elapsed time, tokens and machine pressure are reported separately by work class. | Every role's `load_evidence` entry must carry all six metric keys; validation fails on any missing key, and the result nests them per provider under each work class id. |
| The chosen role mapping meets the same acceptance standard across supported providers. | `providers_meeting_standard` applies one `acceptance_standard` to every provider's evidence across every work class; the acceptance criterion requires all providers (and more than one) to pass. |
| The initial ceiling is reduced only when observed host pressure or completion quality requires it. | `reduction_justified = observed_host_pressure or not observed_completion_quality_ok`; `chosen_ceiling` drops to `minimum_ceiling` only then, and the acceptance check is an exact XOR between "ceiling unchanged" and "reduction justified". |
| Zero retention is preferred when Planning Graph evidence is sufficient; otherwise the shortest evidenced diagnostic retention is selected. | `select_retention` picks `zero` first when its sufficiency flag is true, else the minimum-`retained_turns` candidate with an evidenced diagnostic need, else raises rather than defaulting. |
| No candidate uses Astra, Fable or reasoning above medium. | Every role's `model` is checked against the forbidden-token list and every `effort` against the allowed ceiling before the scenario runs, exactly as in P04. |

`tests/role-qualification-oracle-test.py` exercises the default scenario
twice for determinism, then proves each guard rejects the manifest it is
meant to reject: effort above medium, a forbidden model name, a missing load
metric, a provider-set mismatch across work classes, and a concurrency
ceiling that is not deliberately high; then proves both concurrency-reduction
triggers, the zero-retention default, the shortest-evidenced fallback, and
the refusal to retain anything when no candidate has an evidenced diagnostic
need.

## Scope of proof

- **TARGET**: live multi-provider planning-role deployment with real
  concurrency and retention economics.
- **CONFIGURED**: the two work classes, their per-provider roles and load
  evidence, the concurrency ceiling pair, and the retention candidates in
  `config/role-qualification-prototype.json`.
- **OBSERVED**: the deterministic per-work-class, per-provider comparison and
  its five acceptance checks, reproduced identically on every run.
- **PROVEN**: within this synthetic scenario, that one acceptance standard
  applies uniformly across providers, that a concurrency ceiling reduction
  requires stated evidence, and that decision-session retention defaults to
  zero and only grows on an evidenced diagnostic need.

Not proven here: live host resource pressure, real cross-provider load
measurement, and production concurrency-controller behavior — those remain
the province of a future kernel, not this qualification prototype.
