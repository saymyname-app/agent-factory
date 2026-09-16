# ADR-0021: Existing-code review tiers — closing the existant/cible gap for takeover projects

- Status: Accepted
- Date: 2026-09-16
- Decided by: Benjamin, live conversation 2026-09-16 — "tout le projet saymyname
  actuel est scope V1 par défaut... existant = cible... [le code existant] doit
  etre review... les 3 paliers... documenté et protocolé et réutilisable... à
  toi de voir [le mécanisme]... je te donne toute permission." Tier design and
  schema mechanism are the PO/Tech Lead's, per that delegation.
- Extends: ADR-0015 (project intake and target contract), specifically §5b
  (takeover conflicts) and the `status` evidence enum.
- Implements via: bead `af-caht` (schema wiring, already queued) plus a new
  dependent bead this ADR creates (see §4) for applying the protocol to
  SayMyName.

## Context

ADR-0015 already specifies the shape of a takeover project: `origin.kind =
"takeover"`, deterministic discovery (Pass 1, 0 model calls), model-assisted
drafting (Pass 2), and — critically — a mechanism for when discovered code
contradicts the stated target (§5b: `origin.conflicts[]`, resolved by a
reserved `outcome` decision offering `keep_target` / `adapt_target` / `mix`).

What ADR-0015 does not say: how does a piece of *discovered* code earn the
right to be marked `proven` for V1? Today `status = proven` only requires
*evidence that the behavior exists* — a passing test, a live route. For a
capability the Factory built itself, that is the right bar: the Factory
already reviewed its own work through a PR and CI before it could reach
`proven`. For a takeover capability, nobody on the Factory side has looked at
it yet. Letting discovery alone promote existing code to `proven` would
silently convert "the previous team's code passes the previous team's tests"
into "this is what SayMyName V1 ships," without the Factory ever forming an
opinion on it.

Benjamin's decision in this session: all of SayMyName's current code is V1
scope by definition — it is V1. The intake documentation must become the full
V1 contract: existing code and target capability reconciled into one document,
such that "delivered" means existing = target. Existing code is not read as
proof of itself; it is read as a claim that needs review, the same way a
teammate's unreviewed PR is a claim, not a fact. A review may conclude the
code is fine, or that it needs rework, replacement, or deletion — and either
outcome must be visible, not silently assumed. He asked for the review to run
across three tiers, used intelligently rather than always maxed out, token-
economical by default, executed by the Mayor autonomously, and for the method
and its prompts to be documented as a reusable Factory protocol rather than a
one-off pass over SayMyName.

## Decision

### 1. `review` — a status orthogonal to `evidence.status`

Add a `review` object to `evidencedBlock` (capabilities, criteria, journeys)
wherever `origin.discovery` cites the block as evidence — i.e. the block is
takeover-derived, not authored by the Factory itself through normal delivery:

```jsonc
"review": {
  "state": "unreviewed | reviewed_ok | needs_rework",
  "tier": "static | model | human_e2e | null",
  "reviewed_at": "date-time | null",
  "reviewed_by": "string | null",   // \"factory:static\", \"factory:model\", or the human's name
  "ref": [ /* evidence[], what the review looked at or produced */ ],
  "notes": "string"
}
```

Default on creation from discovery: `state: "unreviewed"`, `tier: null`.

New fail-closed rule in `validate_release_contract`, alongside the existing
dangling-ref/cycle/duplicate-id checks: a takeover-derived block may not carry
`status: "proven"` while `review.state == "unreviewed"`. It is capped at
`assumed` or `partial` until reviewed. This is the direct fix for the gap
above — existing code stops being silently trusted the moment it is merely
discovered.

`review.state = "needs_rework"` does not itself create the takeover conflict —
it *triggers* one, reusing the existing mechanism rather than adding a second
one. The reviewing tier records an `origin.conflicts[]` entry per §5b
(`code_evidence` = the review's own findings, `intent_ref` = the target
criterion it contradicts) and raises the reserved `outcome` decision
(`keep_target` / `adapt_target` / `mix`). Because that decision class is
reserved, it is always asked of Benjamin and can never be answered by an
assumption — consistent with ADR-0015 §3.

### 2. Three tiers, escalated only on demand

Applied per block, in order, never all three by default — token economy is
Benjamin's explicit constraint. Tier assignment is a mechanical rule, not left
to a model's discretion:

**Tier 1 — static (0 tokens).** Deterministic signal only: do the block's own
tests pass, is CI green for the files its discovery evidence cites, does
`/code-review` at effort `low` (existing Factory tooling) run clean against
that diff/file. Sets `review.tier = "static"`. Concludes `reviewed_ok` if
nothing flags; otherwise escalates. This is the natural companion to Pass 1's
`deterministic_scan` — same 0-model-call budget.

**Tier 2 — model-assisted (bounded, targeted).** Fires only when tier 1
flagged something, or the block intersects a reserved class
(`identity_and_consent`, `irreversible`, `money`, `authority`, `legal` — the
same table ADR-0015 §3 already defines). One bounded model call per block,
using the reusable prompt template below, comparing the block's target
criteria and `origin.statement` against tier 1's findings. Concludes
`reviewed_ok` or `needs_rework`, always with a written `notes` justification —
it may not silently pass a block a human should see.

**Tier 3 — human E2E (reserved, not default).** Fires only when tier 2 itself
cannot resolve the question from static + model evidence — genuinely
subjective UX judgment, or a reserved-class capability where the answer
depends on Benjamin actually using it. Produces a short PO-authored click-
through protocol (steps, what "correct" looks like), attached as
`review.ref`, surfaced in the cockpit as an ordinary `decision_required` —
never a campaign stop, just a queued decision like any other.

Escalation rule, stated once so it's reusable: reserved-class block → at least
tier 2; tier 1 clean and non-reserved → done at tier 1; tier 1 flags →
tier 2; tier 2 inconclusive, or reserved-class and still ambiguous after
tier 2 → tier 3.

### 3. Reusable prompt templates — live in the Factory, not in this ADR

New file `docs/INTAKE_REVIEW_TIERS.md`: the tier-2 and tier-3 prompt
templates, parameterized by `{block.title}`, `{block.description}`,
`{origin.statement}`, `{discovery evidence refs}`, `{tier-1 findings}`, plus
the mechanical escalation rule from §2 stated once as a lookup table. Indexed
from `docs/CONTEXT_INDEX.md` alongside ADR-0015's own intake material, so the
next takeover project reuses the same tiering instead of a future PO
re-deriving it from a chat transcript. Whichever worker role ends up running
tier 2/3 (an existing agent role or a new one under `agents/`) reads its
prompt from this file rather than embedding a copy — that wiring choice is
left to whoever implements the dependent bead in §4, not fixed here. This
file, not this ADR, is the artifact that makes the protocol "documenté et
protocolé et réutilisable."

### 4. Applying it to SayMyName without stalling the campaign

This ADR is specification, like ADR-0015's schema draft was — it does not run
the review itself. Running it is Mayor-owned execution, per the existing
PO/Mayor split (`AGENTS.md`): the PO does not become a second orchestrator.
Two beads carry it:

- `af-caht` (already queued, goal unchanged): wires the extended schema —
  including this ADR's `review` object and the new `validate_release_contract`
  check — onto `lib/product_release.py`, and migrates
  `config/releases/saymyname-v1.json`.
- A new bead, dependent on `af-caht` (created alongside this ADR — see the
  companion bead update): runs intake Pass 1 discovery against both rigs
  (`saymyname-backend`, `saymyname-frontend`), applies the three-tier protocol
  per discovered capability using `agents/intake/review-tiers.md`, and —
  the part that keeps the campaign from ever idling on "nothing left to do" —
  **every `needs_rework` finding must materialize as a normal product-queue
  bead** under goal `af-u8id` (or a new goal, if the discovered scope doesn't
  fit an existing one), not merely a document annotation. The automatic
  campaign already knows how to pick up one queued eligible item at a time in
  order; this bead's job is to make sure discovered rework becomes that kind
  of item, so review naturally keeps generating work instead of dead-ending
  in a report nobody re-reads.

## Consequences

- Existing SayMyName capabilities can no longer read `proven` by default:
  right after this lands, some "État prouvé, partiel ou à décider" cards in
  the cockpit will visibly show `assumed` or `partial` where they previously
  showed nothing tracked at all, until reviewed. That is accurate, not a
  regression — it replaces an invisible assumption with a visible one, which
  is ADR-0015's own stated goal applied to code instead of intent.
- Token spend stays bounded by construction: tier 1 is free and is expected to
  clear most of the backend/frontend surface, since both rigs already carry
  tests and CI; tier 2 fires only on flags or reserved classes; tier 3 spends
  Benjamin's time only where it is actually load-bearing.
- Nothing here changes autonomy level, the reserved-class set, or who may
  freeze a version. This is additive to ADR-0015, not a new grant.

## Arbitration record

Settled by Benjamin, live conversation, 2026-09-16: all current SayMyName code
is V1 scope by default; intake must reconcile existing vs. target into one V1
contract such that existing = target at delivery; existing code is
auto-flagged unreviewed, never auto-trusted; review uses three tiers,
applied intelligently rather than maxed out, token-economical; mechanism
design delegated to PO/Tech Lead ("à toi de voir"); the Mayor executes, the PO
does not supervise every step or become a second orchestrator; full autonomy
granted to proceed — including creating new beads — so the campaign keeps
running unattended while Benjamin is away.
