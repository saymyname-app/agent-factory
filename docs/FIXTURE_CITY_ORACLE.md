# Fixture City public-behavior oracle

## Status and purpose

`bin/fixture-city-oracle` is the deterministic acceptance seam for the new
project-agnostic Factory path. It starts with a synthetic project intent and
observes externally meaningful lifecycle state without inspecting prompts,
session layout, formulas, orders, agent roles, or candidate persistence.

The harness and its reference fixture are **PROVEN** by
`tests/fixture-city-oracle-test.py`. A real planning implementation remains
**TARGET** until its adapters pass the same oracle. Passing the reference
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
- independently observable vertical slices and their blocker keys; and
- `inject.publication_failure`, either `none` or `after-stage`.

The oracle rejects duplicate IDs, undeclared rigs, non-exact revisions, missing
blockers, self-dependencies, and cyclic graphs before invoking an adapter.

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
