# Pre-refactor material — what is kept here, where the rest is

Intent (Benjamin, his words, 2026-10-11): « on supprime le legacy on garde
l'historique c'est ok si ya pas de secret »
Mechanism (agent interpretation, af-996mmd): the `legacy/` directory is gone
from `main`. Git history keeps every file of it: nothing was rewritten. The
nine pre-refactor ADRs a rule in force still cites were moved into this
directory, beside the refactor-born ADR-0025 and later. It does not mean
those nine were re-validated, nor that the removed files are trusted.

Everything named on this page predates the project-agnostic refactor
(Planning Run kernel, ADR-0025..0028).

## Where the removed files are

| What | Last commit holding it | List | Read one |
|---|---|---|---|
| Documents: ADR-0001..0024, `docs/products/` (SayMyName and example), 16 pre-refactor docs (57 files) | `987d497ffb0d129df42c32315324616e3552559e` | `git ls-tree -r --name-only 987d497 -- legacy/` | `git show 987d497:legacy/<path>` |
| Code, tests and config: `legacy/{agents,bin,config,lib,orders,tests,ui}` (73 files, 26,652 lines; removed by af-xbu9gq) | `b4ceba798cab85fa045a9a39953220420164134e` | `git ls-tree -r --name-only b4ceba7 -- legacy/` | `git show b4ceba7:legacy/<path>` |

- **Untrusted.** Do not use a removed file as a source of truth, a design
  reference or a template. Read one only to investigate a concrete recurring
  problem.
- **Nothing that runs may name a `legacy/` path**, and the directory must not
  come back: `tests/legacy-isolation-test.sh`.
- Paths mirrored their former location (`legacy/lib/x.py` was `lib/x.py`).
  The table below names files as they were moved, for lookup in Git history.
- The nine ADRs kept here are unchanged: a path they name
  (`docs/products/saymyname/...`, `docs/PRODUCT_QUEUE.md`) is the path at the
  time they were written, to look up under `legacy/` in Git history.

## Contents, by move (code rows now in Git history only)

| PR | Date | What moved | Replacement |
|----|------|------------|-------------|
| 1 | 2026-09-26 | Cockpit V1 (`bin/factory-cockpit`, `lib/factory_cockpit.py`, `ui/factory-cockpit/`, `config/cockpit.json`, `config/product-cockpit.schema.json`, 5 tests) and ntfy phone push (`bin/ntfy-notify`, `lib/ntfy_notify.py`, `orders/ntfy-notify.toml`, 1 test) | Cockpit V2 Planning Run (C01); ntfy notifications and ritual reminders are recorded as its requirements in `config/planning-run-reservation.json` |
| 2 | 2026-09-26 | Campaign: `bin/mayor-campaign` + `orders/mayor-campaign.toml` (the 1-min sentinel), `lib/factory_campaign.py`, `lib/factory_liveness.py`, `lib/factory_continuity.py`, `factory-improvement-axes` (bin, lib, 2 configs), 7 tests + `tests/fixtures/mayor-campaign/` | Mayor executes approved graphs (Benjamin's decisions 7-9, 2026-09-25); orders re-planned in the Planning Run "Factory operations v2" |
| 3 | 2026-09-26 | SayMyName product queue: `bin/product-queue`, `bin/saymyname-product-{queue,status}`, `bin/saymyname-preview`, `bin/factory-human-state`, `bin/factory-queue-guard`, `lib/factory_state.py`, `config/products/`, `config/factory-human-status.schema.json`, 5 tests + 2 fixture dirs | Work enters through the Planning Run flow; project status lives in each project's own repository |
| 4 | 2026-09-26 | Release contract: `bin/product-release`, `lib/product_release.py`, `config/product-release.schema.json`, `config/releases/`, 1 test | Approved Specs and ticket graphs from the Planning Run flow (ADR-0027 keeps the `release-contract` fence) |
| 5 | 2026-09-27 | ADR-0001..0024 (`docs/decisions/`), `docs/products/` (SayMyName + example), 16 pre-refactor docs (audit, continuity, cockpit/product templates, product queue, migration, target architecture, 4 a.m. runbook, incident, load test, proposals…) | Refactor-born ADR-0025..0028 and docs; project knowledge lives in each project's own repository |
| 6 | 2026-09-28 | O14 (Factory operations v2, spec-factory-operations-v2-2026-09-28): standalone `claude-reviewer` agent (`agents/claude-reviewer/`, its `[[patches.agent]]` in `city.toml`) and 2 orphan JSON Schema files nothing loaded (`config/factory-observe-policy.schema.json`, `config/factory-observe-measures.schema.json`); real-PII guard (`bin/factory-pii-guard`, its `.githooks/pre-push` call, `factory-guard` §3c call, 1 test) | F15: independent GUARDED review comes from `build-basic`'s own review steps or the on-demand `ux-reviewer`, not a standalone reviewer pool; F20: `factory-observe`/`factory-measures` policy validation stays hand-written in `lib/factory_observe.py`/`lib/factory_measures.py`. PII guard: retired per Benjamin (Q4.3) — the written rule stays in the SayMyName repo's own `knowledge/real-person-data.md` |

Edges cut in PR 1: `bin/factory-boot` no longer starts a cockpit;
`bin/factory-watchdog` §5 (stall frequency) is removed with its lib/tests,
because Cockpit V1 was the only writer of
`.gc/runtime/factory-continuity-history.json`; CI no longer runs the moved
suites.

Edges cut in PR 2: `bin/factory-boot` no longer resumes a campaign;
`bin/factory-guard` §7 (campaign liveness) and §7c (coordination repair)
are gone -- the "Mayor session down" page that lived inside §7 is kept as
the new §7, its rule now in `lib/factory_session_boot.py`;
`bin/factory-watchdog` §6 (sentinel ticks) and §7 (liveness re-nudge) are
gone; `bin/provider-failover` no longer parks/resumes the campaign on total
exhaustion.

Edges cut in PR 3: factory-guard §9 (queue status drift) is gone with
`factory-queue-guard`; `AGENTS.md` and `README.md` no longer route status
questions to `saymyname-product-status`.

## Still running, to decide later

- `.gc/runtime/factory-watchdog-signals.json` is still written by
  `bin/factory-watchdog`, `bin/on-order-failed` and `bin/on-session-stranded`,
  but its only readers (Cockpit V1, ntfy) are retired. Input for the Planning
  Run "Factory operations v2": keep as the Cockpit V2 feed, or drop.
- The coordination bead `af-1vr4` keeps its `gc.campaign_*` metadata (inert);
  factory-guard §7/§7b still use it to store dedup pointers.
- `bin/campaign-pointer` stays: `formulas/mol-scoped-work.formula.toml` uses
  it to escalate. The Mayor prompt is rewritten in its own PR (decisions
  7-9 of 2026-09-25).
- Nothing wakes the Mayor when `bin/ticket-graph-publish` publishes an
  approved graph (ADR-0025's sentinel scope left with the campaign); until
  "Factory operations v2" adds a trigger, whoever publishes mails the Mayor.
- On total provider exhaustion nothing is parked any more; whether an
  equivalent is needed is an input for "Factory operations v2".
- Host-local runtime files `.gc/runtime/factory-cockpit-*` are no longer read;
  they are not versioned.

## Pre-refactor ADRs whose mechanism still runs (active, not re-validated)

ADR-0009 (work-record outcome, `deliver-close --outcome`), ADR-0016 (six delivery
proof fields; standing ADMIN allowlist in `AGENTS.md`), ADR-0017 (four conditions
for Factory improvements), ADR-0018 (provider failover), ADR-0019 (reversibility
gate), ADR-0020 (main-landing gate), ADR-0022 (live-root enforcement), ADR-0023
(coordination write doors: `campaign-pointer`, `deliver-close`), ADR-0024 (shared
drain worktree). These nine files are in this directory. Re-decide each through
the Planning Run flow when touched.

## ADRs whose mechanism was retired (code in Git history)

- ADR-0006 (token-free human cockpit) — mechanism retired with Cockpit V1.
- ADR-0018 (provider failover) — only its ntfy re-auth hint map
  (`lib/ntfy_notify.py`) was retired; the failover itself still runs.
- ADR-0027 §5 — the quarantined Cockpit V1 files were retired unchanged; the
  `cockpit-v1-export` fence still applies.

