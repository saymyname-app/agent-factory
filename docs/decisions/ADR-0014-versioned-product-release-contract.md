# ADR-0014: Versioned product release contract and graph-aware campaign selection

- Status: Accepted
- Date: 2026-09-15

## Context

SayMyName product truth, the Product view, PO decisions, and the Mayor
campaign each described "V1" in their own shape. Nothing forced them to agree
on scope, maturity, or what still lacked proof, and nothing modeled what
happens when a later version starts: V1 evidence could silently drift or be
overwritten instead of being frozen. Benjamin recorded the durable decision
*V1 is a versioned production-autonomous release contract* on 2026-09-15
(`docs/products/saymyname/DECISIONS.md#2026-09-15-v1-is-a-versioned-production-autonomous-release-contract`).
This continues ADR-0012 (human state/resume contract) and ADR-0013
(Mayor-owned continuous campaign) without adding a second orchestrator, a
second queue, or a second UI.

## Decision

A product's versioned release truth lives in Git as a single schema-validated
document — `config/product-release.schema.json`, contract
`agent-factory-product-release/v1`, one file per product under
`config/releases/` (`config/releases/saymyname-v1.json` for SayMyName V1,
referenced from `config/products/saymyname.json#release_contract`). It models
version, capabilities, journeys, included/excluded scope, dependencies,
decisions, evidence-backed criteria, a `work_graph`, factory improvements,
maturity, and release state. `lib/product_release.py` is deliberately pure: it
reads no live state, writes no files, and calls no model. It only validates or
projects a value the caller already loaded from Git.

**Evidence status** is one of `proven`, `partial`, `unverified`, `absent`,
`out_of_version`, or `decision_required`, attached with typed, referenced
evidence (`ui`, `api`, `data`, `test`, `document`, `bead`, `github`) — never a
bare claim.

**Release state** is `draft → approved → executing → frozen`, enforced by
`transition_release`: idempotent for a same-state call, fail-closed for any
skip or backward move, and permanently immutable once `frozen`.
`start_next_version` requires the current release to already be `executing`
or `frozen`, requires the caller's `next_version` to match the contract's own
`next_version`, and freezes the current release before a later version may
start — V2 can never begin by silently overwriting V1's evidence.

**Graph-aware campaign selection** is the only interface the Mayor campaign
may use to pick work from a release: `select_campaign_work` returns exactly
one `work_graph` node that is a product-kind candidate, criterion-traceable,
dependency-satisfied (every `depends_on` entry `delivered`), unblocked, and
independence-`proven` — never more than one, never reordering the queue, and
never materializing work itself. When no such node exists it returns a typed,
explained stop instead of guessing: `release_not_executable` (release not yet
`approved`/`executing`), `independence_unknown` (a candidate exists but its
independence is unproven), a `blocked_<decision|admin|limit|durable_failure|dependency>`
reason carrying the blocker's owner/cause/action (and `decision_id` only for
`decision`-kind blocks), `release_target_proven` (every criterion is already
`proven` — nothing left to do), or `no_proven_independent_work`. A decision
blocker only ever stops its own subgraph; unrelated independent work is
unaffected. `af-cm1l` and any other Factory-scoped work can never be recorded
as a V1 product capability — only as a `factory_improvements` entry — enforced
in `validate_release_contract`, not left to convention.

**Product view projection** stays a read-only overlay. `project_release`
adds human-facing status labels, embeds the current campaign selection, and
surfaces at most one `decision_required` intervention with a deep link;
`project_operational_release` adds only the `truth_state` (Git) versus
`operational_state` (runtime) distinction the cockpit needs: a `draft`
release can never be reported as campaign-executing (fail-closed), an
`approved`/`executing` release with the campaign enabled reports
`executing`, and a `frozen` release always stays `frozen` regardless of
campaign state. Neither projection function mutates Git or Beads state.

## Consequences

- Product truth, the Product view, PO decisions, and the Mayor campaign read
  one versioned Git document instead of four independently-drifting shapes.
- A release cannot be silently reinterpreted: schema plus semantic validation
  (`tests/product-release-test.py`) reject dangling references, duplicate
  IDs, `work_graph` cycles, self-dependency, and mismatched blocker/decision
  pairs before the value ever reaches a projection or the campaign.
- The campaign remains bounded to exactly one proven-independent, deduplicated
  unit of work at a time, with every stop reason durable, typed, and
  attributable to an owner and an exact action.
- Starting V2 is the only way to freeze V1; V1 evidence is then immutable and
  auditable rather than overwritten.
- No new orchestrator, queue, or UI was added; `bin/product-release` is a
  thin, read-only CLI over the same pure module the cockpit and campaign use.
