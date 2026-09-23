# Planning Run resume prototype (P04)

## Status and purpose

`bin/planning-run-resume-oracle` is a bounded, deterministic prototype of one
Planning Run decision surviving a provider and operator-surface change
without Benjamin repeating it. It is a synthetic simulation, not a live
Codex/Claude/Cockpit integration — the same scope `planning-allocation-prototype`
used to compare candidate allocations before any candidate ran for real.

## Run it

```bash
./bin/planning-run-resume-oracle validate
./bin/planning-run-resume-oracle run
python3 tests/planning-run-resume-oracle-test.py
```

`run` emits one deterministic JSON result: which role resolved the decision,
which role resumed it, whether the provider and surface actually changed,
whether the resuming role retrieved the decision from the Planning Graph
evidence ledger rather than a copied transcript, the measured conversation
visibility between roles, whether any retained conversation view meets its
retention contract, and whether every exercised role stays within the
no-Astra/no-Fable/medium-or-lower ceiling. The scenario source is
`config/planning-run-resume-prototype.json`.

## What the prototype models

- **Resolve.** `codex-planner` (provider `codex`, surface `codex-cli`)
  resolves decision `D-P04-001` and writes it to an in-memory evidence
  ledger — the stand-in for the Planning Graph and its linked evidence.
- **Interruption.** The oracle discards `codex-planner`'s transcript; nothing
  carries it forward.
- **Resume.** `claude-planner` (provider `claude`, surface `claude-code-cli`)
  starts with no transcript at all and retrieves the decision only by
  reading the evidence ledger. The oracle rejects any manifest where the
  resume role shares a provider or a surface with the resolve role, so the
  scenario cannot pass by skipping the actual change it is meant to exercise.
- **Observe.** `cockpit-adapter`, the minimal synthetic Cockpit adapter,
  reads a read-only status view of `claude-planner`'s session. The manifest
  declares `conversation_view.reverse_exists: false`: `claude-planner` (or
  `codex-planner`) has no symmetric way to query the Cockpit adapter's or
  each other's live conversation. The oracle requires this field to be
  present explicitly — an omitted value fails validation — so the harness
  cannot claim one-way visibility it never measured.

## Acceptance mapping

| Acceptance criterion | How the oracle checks it |
| --- | --- |
| A resolved decision remains available after provider and surface change without Benjamin repeating it. | `resumed_without_repeat`: the resume role's ledger read matches the resolve role's write, and the manifest is rejected unless both provider and surface actually changed. |
| The Planning Graph and linked evidence, not a retained chat transcript, carry continuity. | The resume step never reads `discarded_transcript`; only the evidence ledger is consulted. |
| The observed one-way conversation visibility is measured rather than assumed to be bidirectional. | `conversation_view.reverse_exists` must be stated explicitly; the default scenario states `false` and the oracle reports `directionality: one_way`. |
| Any cross-surface conversation view is retained only if native, read-only, zero-token and cheap to maintain. | A retained `conversation_view` must satisfy all four gates or validation fails outright — there is no partial-credit retention. |
| All exercised roles obey the no-Astra, no-Fable and medium-or-lower ceiling. | Every role's `model` is checked against the forbidden-token list and every `effort` against the allowed ceiling before the scenario runs. |

`tests/planning-run-resume-oracle-test.py` exercises the default scenario
twice for determinism, then proves each guard rejects the manifest it is
meant to reject: effort above medium, a forbidden model name, a resume step
that does not change provider or surface, a partially-compliant retained
view, an unmeasured `reverse_exists`, and the valid-but-weaker case of
dropping the conversation view entirely (which forfeits the visibility
criterion honestly instead of hiding it).

## Scope of proof

- **TARGET**: a live Planning Run resumed across a real Codex session, a real
  Claude Code session, and a real Cockpit read.
- **CONFIGURED**: the roles, the resolve/resume/observe sequence, and the
  conversation-view retention contract in
  `config/planning-run-resume-prototype.json`.
- **OBSERVED**: the deterministic resolve → interruption → resume →
  observe trace and its five acceptance checks, reproduced identically on
  every run.
- **PROVEN**: within this synthetic scenario, that continuity requires no
  transcript, that one-way visibility must be declared rather than assumed,
  and that a partially-compliant conversation view cannot be retained.

Not proven here: live provider behavior, the real `factory-cockpit`
adapter's actual read-only/zero-token properties (asserted in
`AGENTS.md` and `bin/factory-cockpit`, not re-verified by this harness), and
concurrency or retention economics, which P06 owns.
