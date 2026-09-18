# Intake review tiers — what `mol-intake` actually runs, per tier

Operational companion to `docs/INTAKE_REVIEW_TIERS.md` (the protocol design,
written against SayMyName) and `docs/decisions/ADR-0021-existing-code-review-tiers.md`
(the decision). Cited by ADR-0021 §4 as `agents/intake/review-tiers.md`. This
file is what an agent running `formulas/mol-intake.formula.toml`'s
`review-existing-code` step reads to know which command to run for which
tier, for **any** takeover project — not SayMyName-specific wording. Where
this file and `docs/INTAKE_REVIEW_TIERS.md` disagree on the escalation rule,
`docs/INTAKE_REVIEW_TIERS.md` is authoritative; this file only adds the
concrete commands.

Scope: runs once per takeover-derived block (a capability, criterion, or
journey whose `evidence[]` includes a `kind: "scan"` entry from
`origin.discovery`) after Pass 1 discovery has populated
`origin.discovery.findings` and Pass 2 has drafted the block. Never runs
against a Factory-authored block — those already went through a PR and CI.

## Escalation rule

Same mechanical table as `docs/INTAKE_REVIEW_TIERS.md`:

| condition | tier |
| --- | --- |
| non-reserved block, tier 1 clean | stop at tier 1 → `reviewed_ok` |
| non-reserved block, tier 1 flags something | tier 2 |
| block's kind intersects a reserved class (`identity_and_consent`, `irreversible`, `money`, `authority`, `legal`) | at least tier 2, always |
| tier 2 concludes with justified confidence | stop, record verdict |
| tier 2 inconclusive, or reserved-class and still ambiguous | tier 3 |

## Tier 1 — static (0 tokens): what actually runs

For each takeover-derived block, over the files its `evidence[].ref` cites:

```bash
# 1. the block's own tests, whatever the rig's runner is
<rig test command> -- <files the block's evidence cites>

# 2. CI status for the last commit touching those files
gh api "repos/{owner}/{repo}/commits/$(git log -1 --format=%H -- <files>)/status" --jq .state

# 3. a deterministic, 0-token correctness pass
/code-review low <files>
```

Write each command's outcome as a `review.ref[]` evidence entry
(`kind: "test"` for #1, `kind: "scan"` for #2 and #3). If all three are
clean, set on the block:

```json
"review": {"state": "reviewed_ok", "tier": "static", "reviewed_at": "<now>",
           "reviewed_by": "factory:static", "ref": [...], "notes": "..."}
```

Otherwise (or if the block's `kind` is a reserved class), continue to tier 2
without setting `review.state` yet.

## Tier 2 — model-assisted (bounded: one call per block)

Use the prompt template verbatim from `docs/INTAKE_REVIEW_TIERS.md` (§Tier 2),
substituting `{block.title}`, `{block.description}`, `{origin.statement}`,
the block's discovery evidence refs, and the tier-1 findings from above. One
call, no follow-ups. Record the result:

```json
"review": {"state": "reviewed_ok" | "needs_rework", "tier": "model",
           "reviewed_at": "<now>", "reviewed_by": "factory:model",
           "ref": [...tier-1 refs + this call's transcript ref...],
           "notes": "<the model's cited justification, verbatim>"}
```

If `needs_rework`: append one `origin.conflicts[]` entry per ADR-0015 §5b
(`code_evidence` = this review's `ref`, `intent_ref` = the target criterion
it contradicts, `resolution: "pending"`) and add one `decisions[]` entry with
`reserved_class: "outcome"`, `status: "decision_required"` — mechanically,
from the model's structured verdict. Never let the model call itself write
into `origin.conflicts[]` or set a `resolution`.

## Tier 3 — human E2E (reserved, not default)

Only reached when tier 2 is inconclusive, or the block is reserved-class and
tier 2 alone did not resolve it. `mol-intake` does not generate this step's
content by model call — it is PO-authored:

1. Write a 3–6 step click-through protocol ("open X, do Y, expect Z") as
   `review.ref` (`kind: "document"`).
2. File it as an ordinary `decisions[]` entry (`status: "decision_required"`)
   — never a campaign stop; other eligible intake/review work keeps running.
3. When Benjamin completes the protocol, record the result the same shape as
   tiers 1/2, with `reviewed_by` set to his name instead of `"factory:<tier>"`.

## What this file does not do

- It does not decide `keep_target` / `adapt_target` / `mix` on a conflict —
  that stays Benjamin's reserved `outcome` decision every time (ADR-0015 §5b),
  regardless of which tier raised it.
- It does not run on Factory-authored code, or replace normal PR review for
  new work the Mayor produces going forward (`DELIVERY.md`).
- It does not decide which tier to *start* at outside the escalation rule
  above — that decision is mechanical, not the calling agent's judgment call.
