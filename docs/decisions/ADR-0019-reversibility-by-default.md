# ADR-0019: Reversibility by default, enforced before merge

- Status: Accepted
- Date: 2026-09-16
- Decided by: Benjamin delegated it in conversation on 2026-09-16 (« la
  réversibilité par défaut ok je te laisse en autonomie dessus aussi »); the
  design below is the PO/Tech Lead's.
- Implements: ADR-0016 §7 row "Escalation 4 — not undoable inside the release"
  (bead af-l463).

## Context

ADR-0016 keeps escalation test 4 in the safety floor and asks for it to fire
less often by making reversibility the engineering default. A default nobody
checks is a wish: the bead that asked for this said so itself, asking for "a
concrete, checkable practice … rather than the current unenforced prose".

What the live system showed on 2026-09-16:

- `docs/DELIVERY.md` classifies Flyway/schema changes as **GUARDED**, yet
  `bin/pr-autopilot` armed every green PR to `dev`, migrations included.
- Replaying the check below on the backend's own history flags five of its
  eleven migrations — V4 and V9 dropped columns, V6 deleted rows, V7 rewrote a
  whole column, V8 renamed columns — and passes the three additive ones (V2,
  V10, V11). V6 explained itself in a prose comment no tool could read.
- The backend runs Flyway Community: `U` undo migrations are a paid feature and
  would never run. Reversibility cannot mean "Flyway undo" here.
- Neither rig has a feature-flag mechanism.

## Decision

### 1. A mechanical classification of every new migration

`lib/reversibility.py`, exposed as `bin/reversibility-check`, reads a diff and
classifies each **added** file under `db/migration/`, statement by statement,
comments stripped:

| class | statements | accepted declaration |
|---|---|---|
| schema loss | `DROP TABLE/SCHEMA/DATABASE/TYPE`, `ALTER … DROP [COLUMN]`, `TRUNCATE` | `rollback:` or `irreversible:` |
| data loss | `DELETE` | `rollback:` or `irreversible:` |
| data rewrite | `UPDATE`, `MODIFY`, `ALTER COLUMN … TYPE` | also `reversible:` |
| rename | `RENAME`, `ALTER … RENAME`, `CHANGE [COLUMN]` | also `reversible:` |

Dropping recreatable schema objects (indexes, constraints, keys, defaults) is
not loss. A modified or deleted existing migration is `history_rewrite` and is
never accepted, because Flyway records applied checksums.

A writer answers a finding with one comment line in the migration:
`-- rollback: <file>` (a script under `db/rollback/`, added in the same change,
never run by Flyway), `-- reversible: <why>` (rewrites and renames only), or
`-- irreversible: <why>` (an explicit test-4 escalation). A `reversible:` claim
is not accepted for loss: a drop needs a way back, not an assurance.

### 2. The merge actor holds what cannot be undone

Before arming — and before its "already armed" shortcut, since a later push can
add a destructive migration to an armed PR — `bin/pr-autopilot` runs the check
on each open PR, cached per head commit:

- `ok` → armed exactly as before. Additive schema changes keep flowing.
- `needs_declaration` / `history_rewrite` → not armed, disarmed if armed,
  labelled `reversibility-declaration-needed`, explained once on the PR in
  French. The next push is re-checked; a fixed PR is released and armed.
- `irreversible` → the same, labelled `irreversible-change`, plus one mail to
  the Mayor: test 4 applies, park the subgraph, queue the decision for
  Benjamin. pr-autopilot never merges it; only a human merge does.
- the check cannot run → not armed this pass (fail closed), counted as an
  error.

### 3. What is not mechanical, and says so

Whether a behaviour change needs a flag cannot be read from a diff, and the rigs
have no flag mechanism. It stays a reviewer checklist item in
`docs/DELIVERY.md` (Réversibilité par défaut).

## Consequences

- The five-in-eleven pattern above can no longer reach `dev` silently.
- Writers get the fix in the PR comment and can run the same check before
  opening the PR, so most holds should be resolved by the writer, not escalated.
- Escalations to Benjamin happen only for changes someone explicitly declared
  irreversible — which is test 4 applied deliberately instead of by chance.
- **Flagged, not changed:** DELIVERY.md still says every Flyway change is
  GUARDED, while additive ones auto-merge (as they did before this ADR). Whether
  additive schema changes should also wait for a human is Benjamin's call.
- Known limit: agents act on GitHub with Benjamin's identity, so no GitHub-side
  signal can prove that a merge of an `irreversible-change` PR was human. The
  guarantee is that no factory automation merges it.
- Cost: one `gh pr diff` per PR per push; zero model tokens.

## Evidence

- `tests/reversibility-test.py` — the backend's real migrations, recreatable
  objects, comments, declarations, rollback presence, history rewrite, CLI and
  git modes.
- `tests/pr-autopilot-reversibility-test.sh` — the real merge actor against
  stubs: arm / hold / disarm + escalate, cache per commit, release after a fix,
  fail closed, dry-run inert. Fails against the previous pr-autopilot.
- Live: `reversibility-check --git` over the backend history flags exactly V4,
  V6, V7, V8, V9; a live `pr-autopilot --dry-run` held nothing and errored on
  nothing (no open PRs at the time).
