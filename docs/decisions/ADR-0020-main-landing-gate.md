# ADR-0020: A local pre-push gate blocks broken commits from landing on `main`

- Status: Accepted
- Date: 2026-09-16
- Decided by: Claude Code, PO + Tech Lead pilot (Codex quota exhausted until
  ~2026-09-21), acting under ADR-0016 standing delegation — no Benjamin
  effect-test trigger applies (no navigation/invitation/consent/personal-data
  exposure).
- Applies to: `saymyname-app/agent-factory` itself, whose default branch is
  `main` (the rigs' `dev` branches already have a required-check gate covered
  by `docs/DELIVERY.md`'s closed-loop delivery section — this ADR does not
  change that).

## Context

Commit `8d92c13` ("Defer all Enterprise-tier SayMyName decisions...") landed
directly on `main` on 2026-09-16 and broke referential integrity between
`docs/products/saymyname/DECISIONS.md` and `config/products/saymyname.json`'s
`decision_refs`. `tests/factory-cockpit-test.py` already had 13 test cases
that caught exactly this class of breakage — the check existed and was
correct. The problem was that nothing forced it to run and pass before the
commit reached `main`. Both Factory CI and the live cockpit stayed broken for
hours before a later session noticed and fixed it (commits `19158b0`,
`46562bd`).

This repository cannot use GitHub branch protection or required-check rules
to close the gap: it is a private repository without GitHub Pro, and the API
returns `403 Upgrade to GitHub Pro or make this repository public`. Commits
also land on `main` both ways in practice — via PR (most recent history) and
by direct commit (as `8d92c13` did) — so a PR-only assumption would not have
caught this incident either.

`bin/pr-autopilot` was checked and does not push locally: it lands PRs with
`gh pr merge` (a GitHub-side API call), so a local `git push` gate never
touches its path. It was therefore safe to add friction to `git push` without
touching the automated delivery loop at all.

## Decision

Add `bin/factory-main-gate`, installed as `.githooks/pre-push` (this repo
already sets `core.hooksPath = .githooks`, see `.githooks/post-checkout`).
It fires on every `git push` whose ref list includes `refs/heads/main`, reads
the list of guarded tests directly out of `.github/workflows/ci.yml` (every
`python`/`bash tests/*.py|*.sh` invocation under the `Tests` job), runs them
locally, and refuses the push if any fail. It does nothing for pushes that do
not touch `main` — no added friction on feature branches, worktree pushes, or
rig PRs.

Deriving the test list from `ci.yml` rather than hardcoding a second list
avoids exactly the class of drift `tests/ci-registration-test.sh` was built
to prevent (CI's own job list once drifted to 7 of 14 registered tests,
ADR-0017). One source of truth; the gate and CI can never silently diverge.

The standard git escape hatch (`git push --no-verify`) remains available for
a genuine emergency, same as any other local hook — this is a local
convenience gate, not a security boundary.

## Consequences (ADR-0017's four conditions)

1. **Verified, not asserted** — `tests/factory-main-gate-test.sh` builds a
   throwaway repo with its own fixture CI/test, and proves: a push to `main`
   whose guarded test fails is rejected and the bad commit never reaches the
   remote's `main`; the same branch pushes cleanly once fixed; a push to a
   non-`main` branch is never gated, even while broken.
2. **Increases autonomy** — no human has to notice a red push-triggered CI
   run on `main` after the fact and then fix it under time pressure; the
   author is told immediately, on their own machine, before anything is
   public.
3. **Optimises** — removes the multi-hour window (2026-09-16 incident: hours)
   where both Factory CI and the live cockpit were broken for anyone
   reading them, at zero model-token cost (pure local git/python/bash).
4. **Documented for both audiences** — this ADR and `docs/CONTEXT_INDEX.md`
   for agents; `docs/DELIVERY.md`'s "Main-landing gate" section names the
   incident and the mechanism in the same place the closed-loop delivery
   contract already lives.

## Related

- ADR-0017 — four conditions every factory improvement must meet.
- ADR-0016 — standing delegation this decision was made under.
- `docs/DELIVERY.md` — Closed-loop delivery (why `pr-autopilot` is unaffected)
  and the new Main-landing gate section.
- `bin/factory-delivery-guard` — same reactive-guard-after-incident pattern,
  same day, different failure mode (a delivery bead closed without proof).
