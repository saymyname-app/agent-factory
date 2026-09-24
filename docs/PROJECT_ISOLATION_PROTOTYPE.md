# Project isolation prototype (P05)

## Status and purpose

`bin/project-isolation-oracle` is a black-box proof that an agent scoped to
one fixture project rig cannot read another registered rig by default, that
registering both rigs in one City grants no cross-project access on its own,
and that a declared multi-project outcome exposes only its named
participants. It uses the same Bubblewrap mount-namespace mechanism
`fixture-city-oracle` already relies on for hermeticity — here the mechanism
itself is the thing under test, not incidental containment.

## Run it

```bash
./bin/project-isolation-oracle validate tests/fixtures/project-isolation/scenarios/single-scope.json
./bin/project-isolation-oracle run tests/fixtures/project-isolation/scenarios/single-scope.json
python3 tests/project-isolation-oracle-test.py
```

`run` emits one deterministic JSON result naming the declared city registry,
the agent's own scope, any declared multi-project grant, the resulting
effective scope, and — per probed rig — whether a public adapter running
inside the sandbox could read that rig's fixture content and its digest. The
adapter (`tests/fixtures/project-isolation/probe`) has no knowledge of which
rigs it is supposed to see; it only reports what the filesystem it actually
finds allows, exactly like `fixture-city-oracle`'s adapters observe only
public interfaces.

## What the prototype models

- **Two isolated fixture project rigs.** `tests/fixtures/project-isolation/rigs/project-a`
  and `project-b`, each holding one deterministic secret file. This is
  `fixture_project_rigs` from the ticket graph's `target_rigs` block.
- **A City registry that alone grants nothing.** A scenario's `city_registry`
  can name both rigs while `agent_scope` names only one; the oracle computes
  `effective_scope` from `agent_scope` plus any `declared_grant.participant_rigs`
  — registry membership by itself never contributes to scope.
- **An explicit, named multi-project grant.** `declared_grant` carries an
  `outcome_id` and the exact `participant_rigs` it authorizes; only those
  rigs are added to the effective scope, and the oracle rejects a grant
  naming any rig outside the registry.
- **The enforcement mechanism.** Only rig directories in the effective scope
  are bind-mounted read-only into the sandbox; the sandbox root starts empty
  (`--unshare-all` with no root bind), so an out-of-scope rig is not merely
  access-denied but absent from the mount namespace.

## Acceptance mapping

| Acceptance criterion | How the oracle checks it |
| --- | --- |
| An agent scoped to fixture project A cannot read fixture project B by default. | `single-scope.json`: `agent_scope=[project-a]`, no grant; `read_results.project-b.readable` is `false` and its digest is `null`. |
| Merely registering both rigs in one City grants no cross-project access. | The same `single-scope.json` scenario registers both rigs in `city_registry` while `agent_scope` still names only `project-a`; `effective_scope` and the observed readable set both stay `[project-a]`. |
| A declared multi-project outcome exposes only its named participant rigs. | `multi-project-grant.json`: `declared_grant.participant_rigs=[project-a, project-b]`; both rigs become readable and their digests match the fixture content exactly. |
| Revoking the grant removes the additional access without changing unrelated projects. | `grant-revoked.json` repeats `single-scope`'s shape after a grant existed; `project-b` becomes unreadable again, and re-running `multi-project-grant` afterward reads back the identical `project-b` digest, proving the fixture itself was never mutated by revocation. |
| The selected enforcement mechanism and unsupported host claims are explicit. | Every result carries a `mechanism` string and a `host_support` object; `host_support.note` states the Bubblewrap/userns dependency, and the oracle raises an explicit `OracleError` instead of a silent pass when `bwrap` is absent. |

`tests/project-isolation-oracle-test.py` also proves two negative cases: a
`declared_grant.participant_rigs` entry outside `city_registry`, and an
`agent_scope` entry outside `city_registry`, are both rejected before any
sandbox runs.

## Scope of proof

- **TARGET**: a live agent process, scoped by its Project Planning Profile,
  reading only its own project's files and repositories, with a real
  multi-project outcome declaring its exact participant rigs.
- **CONFIGURED**: the scenario contract `agent-factory-project-isolation-scenario/v1`
  and the fixture rigs/probe under `tests/fixtures/project-isolation/`.
- **OBSERVED**: the deterministic sandboxed-read trace and its five
  acceptance checks above, reproduced identically on every run.
- **PROVEN**: within this synthetic scenario, that Bubblewrap mount-namespace
  isolation enforces default single-project scope, that City registration
  alone confers no access, that an explicit named grant is both necessary
  and sufficient for cross-project reads, and that revoking it is
  side-effect-free on the untouched rig.

Not proven here: enforcement inside a live Gas City agent process (this
prototype isolates a probe adapter, not a running agent session), a
production Project Planning Profile's grant lifecycle, or hosts that deny
Bubblewrap/userns entirely — the oracle fails closed and explicit on those
hosts rather than claiming isolation it did not exercise.
