#!/usr/bin/env bash
#
# legacy/ holds pre-refactor documents that are untrusted (legacy/README.md);
# its code, tests and config were removed on 2026-10-11 (af-xbu9gq, Git history
# keeps them). Nothing that runs may depend on it: no script,
# library, order, formula, config, CI step, hook or test outside legacy/ may
# name a path under it. Markdown (docs, agent prompts) may still point there,
# because telling a reader "that is retired and untrusted" is the point of a
# signpost. Roadmap A4 (2026-09-27): zero reference from trusted code to
# legacy/, enforced here instead of by a one-off review.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
cd "$REPO_ROOT"

# Tests that assert a signpost's wording must quote it.
ALLOWED='^(tests/operator-context-test\.sh|tests/legacy-isolation-test\.sh)$'

hits=$(git ls-files -z \
  | grep -zv -E '^legacy/|^docs/|\.md$' \
  | grep -zv -E "$ALLOWED" \
  | xargs -0 -r grep -nI -E '(^|[^A-Za-z0-9_.-])legacy/' -- || true)

if [[ -n "$hits" ]]; then
  printf 'FAIL: trusted code names a legacy/ path (see legacy/README.md):\n%s\n' "$hits" >&2
  exit 1
fi

# Only documents live under legacy/: code, tests or config must not come back.
strays=$(git ls-files -- legacy | grep -v -E '^legacy/(README\.md$|docs/)' || true)
if [[ -n "$strays" ]]; then
  printf 'FAIL: legacy/ holds only README.md and docs/; found:\n%s\n' "$strays" >&2
  exit 1
fi
# An ADR a live rule cites must still be there.
[[ -n $(git ls-files -- legacy/docs/decisions) ]] \
  || { echo 'FAIL: legacy/docs/decisions is gone but AGENTS.md cites it' >&2; exit 1; }

# The check must actually see the tree it guards.
[[ -f bin/factory-guard ]] || { echo 'FAIL: run from the Factory repo' >&2; exit 1; }
echo 'legacy-isolation: ok'
