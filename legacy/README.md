# legacy/ — pre-refactor code and docs, untrusted

Everything here predates the project-agnostic refactor (Planning Run kernel,
ADR-0025..0028). It is kept only as readable evidence. **Nothing here runs**:
no order, script, test or CI step outside `legacy/` may reference it.

- **Untrusted.** Do not use it as a source of truth, a design reference or a
  template. Consult it only to investigate a concrete recurring problem.
- **Delete freely.** Any file here can be removed without notice; Git history
  keeps it.
- Paths mirror their former location (`legacy/lib/x.py` was `lib/x.py`).
  Moved files are unchanged, so their own relative paths and tests no longer
  resolve.

## Contents, by move

| PR | Date | What moved | Replacement |
|----|------|------------|-------------|
| 1 | 2026-09-26 | Cockpit V1 (`bin/factory-cockpit`, `lib/factory_cockpit.py`, `ui/factory-cockpit/`, `config/cockpit.json`, `config/product-cockpit.schema.json`, 5 tests) and ntfy phone push (`bin/ntfy-notify`, `lib/ntfy_notify.py`, `orders/ntfy-notify.toml`, 1 test) | Cockpit V2 Planning Run (C01); ntfy notifications and ritual reminders are recorded as its requirements in `config/planning-run-reservation.json` |
| 2 | 2026-09-26 | Campaign: `bin/mayor-campaign` + `orders/mayor-campaign.toml` (the 1-min sentinel), `lib/factory_campaign.py`, `lib/factory_liveness.py`, `lib/factory_continuity.py`, `factory-improvement-axes` (bin, lib, 2 configs), 7 tests + `tests/fixtures/mayor-campaign/` | Mayor executes approved graphs (Benjamin's decisions 7-9, 2026-09-25); orders re-planned in the Planning Run "Factory operations v2" |
| 3 | 2026-09-26 | SayMyName product queue: `bin/product-queue`, `bin/saymyname-product-{queue,status}`, `bin/saymyname-preview`, `bin/factory-human-state`, `bin/factory-queue-guard`, `lib/factory_state.py`, `config/products/`, `config/factory-human-status.schema.json`, 5 tests + 2 fixture dirs | Work enters through the Planning Run flow; project status lives in each project's own repository |

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
  but its only readers (Cockpit V1, ntfy) are here now. Input for the Planning
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

## ADRs whose mechanism moved here

- ADR-0006 (token-free human cockpit) — mechanism now entirely in `legacy/`.
- ADR-0018 (provider failover) — only its ntfy re-auth hint map
  (`lib/ntfy_notify.py`) moved; the failover itself still runs.
- ADR-0027 §5 — the quarantined Cockpit V1 files moved here unchanged; the
  `cockpit-v1-export` fence still applies.

ADR-0001..0024 themselves move here in a later PR.
