# mol-intake dry run — greenfield, 2026-09-18

Evidence for af-4gu62 (mol-intake: run the ADR-0015 intake as a formula, with
a greenfield dry run). Produced by running Pass 1 (`bin/intake-scan`) and the
mechanical half of Pass 2/3 (`bin/intake-draft`, both wired from
`lib/intake_contract.py`) against a throwaway fixture repository, then
validating the result with `lib/product_release.py` unchanged, per the
scope-discipline note in af-4gu62's description.

## What ran

Repository: `tests/fixtures/intake-dryrun-greenfield/` (a `README.md` and
nothing else — no stack, no tests, no CI, no history beyond what `git init`
gives it; kept in the repo as a throwaway fixture, not deleted after the run,
so this dry run stays reproducible).

```bash
./bin/intake-scan tests/fixtures/intake-dryrun-greenfield --origin-kind greenfield \
  | ./bin/intake-draft --product dryrun-fixture --title "Dry-run fixture product V1" \
      --pitch "A throwaway greenfield fixture to prove mol-intake produces a valid contract without a human writing JSON." \
      --pitch-author "mol-intake-dry-run" --origin-kind greenfield \
  > tests/fixtures/intake-dryrun-greenfield/contract-v1.json

python3 bin/product-release validate tests/fixtures/intake-dryrun-greenfield/contract-v1.json
```

This exercises the formula's `discover` and `draft-skeleton` steps exactly as
`formulas/mol-intake.formula.toml` runs them (same two binaries, same
arguments). It does not exercise `draft-target` (Pass 2 judgment drafting)
or `file-questions` (PO filing), because both require either a real product
pitch worth drafting against or a live Beads/product-queue store — neither
applies to a throwaway fixture. Both are covered instead by
`tests/intake-contract-test.py`'s `CheckIntakeExitTest`, which exercises the
exit-check logic those steps feed into.

## Result

`bin/product-release validate` output:

```json
{"valid":true,"contract":"agent-factory-product-release/v1","product":"dryrun-fixture","version":"V1"}
```

`validate_release_contract` accepted the produced contract without manual
editing — the exact acceptance-criteria bar in af-4gu62. The produced
contract is committed at
`tests/fixtures/intake-dryrun-greenfield/contract-v1.json` (143 lines).

Notable shape, matching ADR-0015 §2 Pass 1 and Pass 4:

- `origin.discovery.findings` is `[]` — the "empty-but-explicit" finding set
  Pass 1 requires for a greenfield project, not an absent or null field.
- `intake.questions` has exactly two entries, both `admitted_by: "reserved"`,
  `status: "pending"`: `q-outcome` and `q-authority`. These are the two
  reserved classes (ADR-0015 §3) that no one-line pitch or repository scan
  can ever answer on their own — "what does done mean" and "who decides" —
  so `mol-intake` always asks them for a new project; the formula does not
  guess an answer for either.
- `intake.state` is `awaiting_human` — not `complete` and not the enum value
  named informally in af-4gu62's acceptance text ("open"); `awaiting_human`
  is the closest existing `INTAKE_STATES` member and is what
  `lib/intake_contract.check_intake_exit` computes for a contract whose
  reserved questions are still unanswered (ADR-0015 §2 Pass 4, condition 3).
- `capabilities`/`criteria`/`work_graph` each carry exactly one placeholder
  entry (`intake-in-progress` / `intake-target-defined` / `intake-resolve`),
  because `product_release.py` rejects an empty `work_graph` outright and a
  criterion must reference a capability — `mol-intake`'s `draft-target` step
  (Pass 2, real judgment) is the one that replaces these with the drafted
  product target; this dry run does not run that step, so they stand as
  recorded, not silently dropped.

## Cost

| pass | model calls | wall-clock |
| --- | --- | --- |
| Pass 1 (`intake-scan`, deterministic scan) | 0 | <1 ms (empty fixture repo) |
| Pass 2 mechanical half (`intake-draft`, skeleton assembly + validation) | 0 | <1 ms |
| **Total for this dry run** | **0** | **~0.2 ms** measured (`wall_clock_seconds=0.0002` from the driver script; `bin/product-release validate` CLI invocation adds Python startup, not measured separately, order of 50-100 ms) |

Both steps this dry run exercises are pure Pass 1 / mechanical-Pass-2 work by
construction — ADR-0015 places the only model call in Pass 2's judgment
drafting (`draft-target`), which a throwaway fixture has nothing worth
drafting against, so this run's token cost is exactly zero, not merely low.

## What this does and does not prove

- **Proves:** `mol-intake`'s deterministic steps (`discover`,
  `draft-skeleton`) run end to end against a real filesystem path and produce
  a contract `validate_release_contract` accepts unchanged, for
  `origin.kind=greenfield`, without a human writing JSON.
- **Does not prove:** Pass 2 judgment drafting, Pass 3 PO-candidate filing,
  or the `origin.kind=takeover` discovery-to-review pipeline
  (`agents/intake/review-tiers.md`) end to end against a real takeover
  repository. Those need either a live product pitch or a live Beads store,
  neither of which belongs in a committed dry-run fixture; `tests/intake-contract-test.py`
  covers their logic in isolation instead (14 tests, both origin kinds, all
  passing at the time of this run).
