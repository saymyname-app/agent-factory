# Getting started: install an independent Factory from Git

This is a from-scratch tutorial for a new operator on a **Windows + Ubuntu
WSL** host. It clones the Factory, registers one generic project, starts a
City, and reaches the first Planning Run. Everything here is generic: it
names no product, no SayMyName path, and no credential. Where this repository
currently runs a specific product (SayMyName), that only shows up as example
rig entries in `city.toml` — remove them, as shown below, before registering
your own project.

Distribution is Git only. There is no installer, no managed update
mechanism, and no shared/hosted service: cloning this repository is the
entire install step, and every host runs its own independent City.

## 0. Prerequisites

You need, on the WSL side:

- `git`
- [Gas City](https://github.com/gastownhall/gascity) (`gc`) and
  [Beads](https://github.com/gastownhall/beads) (`bd`) installed and on
  `PATH`
- `python3`
- `tmux`
- at least one coding-agent provider CLI installed and authenticated (for
  example Claude Code or Codex)

Check what is actually missing rather than guessing:

```bash
for bin in git gc bd python3 tmux; do
  command -v "$bin" >/dev/null 2>&1 && echo "OK   $bin" || echo "MISSING $bin"
done
```

Install whatever is `MISSING` from that tool's own instructions, then re-run
the check above. This loop is read-only: it never edits any file or Factory
state, so you can retry it as many times as you need before moving on.

Once a City exists (after step 2), `gc doctor` gives a fuller, still
read-only health check — binary dependencies, config validity, controller
status — and only ever changes something if you pass `--fix` explicitly.

## 1. Clone the Factory

```bash
git clone https://github.com/saymyname-app/agent-factory.git my-factory
cd my-factory
```

`my-factory` is your own independent clone. Nothing you do inside it talks
to any other clone or any hosted service; every command below is local to
this directory.

## 2. Remove the example product rigs

The repository ships `city.toml` and `pack.toml` already committed, because
this same repository also runs the SayMyName City described in the root
`AGENTS.md`. Your clone starts with that same `city.toml`, which currently
names two example rigs (`saymyname-backend`, `saymyname-frontend`). Those
belong to that other City's product, not to yours — drop them before you
register your own project:

```bash
gc rig remove saymyname-backend
gc rig remove saymyname-frontend
```

Run these from inside `my-factory`. `gc rig remove` edits `city.toml` in
place and only in the City it is pointed at — pass `--city <path>` explicitly
if you are not sure which City a shell will resolve to (an inherited
`GC_CITY`/`GC_CITY_PATH` environment variable takes priority over your
current directory).

After this, `city.toml` carries no project-specific rig, path, or rule —
only the generic Factory scaffolding: agent roles, provider tiers, and the
formulas that drive delivery.

## 3. Register your project

A project registers with the City in two steps: a Gas City **rig** (the
project directory the City orchestrates: its own Beads database, agent
hooks, and cross-rig routing), and a **Project Planning Profile** (what
authority that project has: its Project Knowledge, Work Graph, participating
rigs, checks, risk thresholds, and autonomy policy — see
[`PROJECT_PLANNING_PROFILE.md`](PROJECT_PLANNING_PROFILE.md)).

```bash
gc init --preserve-existing --default-provider claude .
gc rig add /path/to/your-project --name your-project
```

`gc rig add` auto-detects the project's default branch from its Git remote
and initializes its Beads database; pass `--default-branch` explicitly if
the project has no remote yet. `--preserve-existing` on `gc init` keeps the
Factory's own committed `pack.toml`/`city.toml`/agent prompts instead of
overwriting them with a blank template — that is what carries over the
delivery formulas this tutorial relies on in step 5.

Then write a Project Planning Profile for it and validate it before
registering:

```bash
./bin/project-planning-profile validate path/to/your-profile.json
./bin/project-planning-profile register path/to/your-profile.json \
    --city-registry <(gc rig list --json)
```

`validate`/`register` reject the profile with an exact field-level reason if
it is missing a required source, contradicts itself, tries to weaken a
common safety principle, or carries a SayMyName-specific or Factory-wide
field — see [`PROJECT_PLANNING_PROFILE.md`](PROJECT_PLANNING_PROFILE.md) for
the full contract and field reference.

## 4. Start the City

```bash
gc start --dry-run   # preview which agents would start, nothing runs yet
gc start
```

`gc start` registers the City with the machine-wide supervisor and brings up
its configured agent sessions, including the Mayor. This is the first point
at which any model provider is called, so confirm your provider CLI is
authenticated (step 0) before running it without `--dry-run`.

## 5. Reach the first Planning Run

Talk to the Mayor in product terms — describe the outcome you want, not
Factory internals:

```bash
gc mail send mayor -s "New project" -m "Register your-project and help me plan <the outcome you want>."
```

The Mayor drives Shared Understanding and, for anything beyond a single
session, promotes the work into a durable Wayfinding Run before producing an
approved Spec and a Ticket Graph Draft — see
[`WAYFINDING_RUN.md`](WAYFINDING_RUN.md) for how that promotion and its
Planning Map work. You approve the Spec and the resulting Ticket Graph
before any delivery work is published.

Under the hood, every new Planning Run — simple or Wayfinding — runs through
one door, `bin/planning-run-router run <request.json>`
([`PLANNING_RUN_ROUTER.md`](PLANNING_RUN_ROUTER.md)): there is no other
coded path, and no flag reactivates a manual, tool-by-tool sequence. While a
reservation is active (`.gc/runtime/planning-run-reservation.json`, seeded
from the tracked `config/planning-run-reservation.json`: first
`factory-operations-v2`, then C01 Cockpit V2, promoted when the previous one
publishes), the router blocks any other new Planning Run until the reserved
run has published.

## 6. Observe without spending tokens

Once the City is running, check on it without waking any agent:

```bash
gc status
```

This performs zero model calls — it is a deterministic read of Gas City and
Beads state. The first run after `gc start` costs nothing beyond that read;
you only spend tokens when you send the Mayor a message (step 5) or when a
Planning Run needs a decision only you can make. The Gas City dashboard
(`http://127.0.0.1:8372`) shows the same state in detail.

## What this tutorial does not do

- It does not claim support for any host other than Windows + Ubuntu WSL —
  no cross-platform behavior is asserted or verified here.
- It does not set up a managed update path or a shared/hosted City: your
  clone is independent, and staying current means pulling this repository
  yourself.
- It does not touch production, external publication, spend, or personal
  data — those remain explicit human decisions regardless of how the
  project's autonomy policy is configured (see the common safety principles
  in [`PROJECT_PLANNING_PROFILE.md`](PROJECT_PLANNING_PROFILE.md)).
