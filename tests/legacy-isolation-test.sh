#!/usr/bin/env bash
#
# The legacy/ directory (pre-refactor code, then documents) is gone from main:
# code on 2026-10-11 by af-xbu9gq, documents the same day by af-996mmd. Git
# history keeps it (docs/decisions/PRE_REFACTOR.md says where). Nothing that
# runs may depend on it: no script, library, order, formula, config, CI step,
# hook or test may name a path under it. Markdown (docs, agent prompts) may
# still name one, because "that file is in Git history at legacy/<path>" is
# how a reader finds it. Roadmap A4 (2026-09-27): zero reference from trusted
# code to legacy/, enforced here instead of by a one-off review.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
cd "$REPO_ROOT"

# This test names the directory it guards.
ALLOWED='^tests/legacy-isolation-test\.sh$'

hits=$(git ls-files -z \
  | grep -zv -E '^docs/|\.md$' \
  | grep -zv -E "$ALLOWED" \
  | xargs -0 -r grep -nI -E '(^|[^A-Za-z0-9_.-])legacy/' -- || true)

if [[ -n "$hits" ]]; then
  printf 'FAIL: trusted code names a legacy/ path (see docs/decisions/PRE_REFACTOR.md):\n%s\n' "$hits" >&2
  exit 1
fi

# The directory must not come back.
strays=$(git ls-files -- legacy)
if [[ -n "$strays" ]]; then
  printf 'FAIL: legacy/ was removed from main (docs/decisions/PRE_REFACTOR.md); found:\n%s\n' "$strays" >&2
  exit 1
fi

# Every pre-refactor ADR the signpost says is kept must be there.
for n in 0009 0016 0017 0018 0019 0020 0022 0023 0024; do
  compgen -G "docs/decisions/ADR-$n-*.md" >/dev/null \
    || { echo "FAIL: docs/decisions/ADR-$n-*.md is gone but docs/decisions/PRE_REFACTOR.md says it is kept" >&2; exit 1; }
done

# The check must actually see the tree it guards.
[[ -f bin/factory-guard ]] || { echo 'FAIL: run from the Factory repo' >&2; exit 1; }
echo 'legacy-isolation: ok'
