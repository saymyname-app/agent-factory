#!/usr/bin/env bash
#
# The installed gh on the Factory host is 2.45, which has no
# `gh pr update-branch` subcommand. On 2026-09-29 bin/pr-autopilot called it
# anyway: every tick with a BEHIND PR failed (order.failed) and stderr was
# discarded, while its test passed because a fake gh accepted the
# nonexistent subcommand. Fakes cannot catch a command the real tool lacks,
# so this guard pins the known-absent forms out of shipped code: use the REST
# endpoint (`gh api -X PUT repos/{repo}/pulls/{num}/update-branch`) instead.
# Comment lines are ignored so the history can still be explained in place.

set -Eeuo pipefail
REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)

hits=$(grep -rnE '^[^#]*\bgh[[:space:]]+pr[[:space:]]+update-branch\b' \
  "$REPO_ROOT/bin" "$REPO_ROOT/lib" 2>/dev/null || true)
if [ -n "$hits" ]; then
  printf '%s\n' "$hits" >&2
  echo "FAIL: 'gh pr update-branch' does not exist in the installed gh (2.45);" \
    "use: gh api -X PUT repos/<repo>/pulls/<num>/update-branch" >&2
  exit 1
fi
echo "OK no shipped code calls 'gh pr update-branch'"
