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

# gh's --jq takes a single expression and has no --arg/--argjson. Until
# 2026-11-09 bin/pr-autopilot's retry of a red required check passed
# `--jq --arg wf "$workflow" '<expr>'`: gh read `--arg` as the expression and
# failed on `wf`, so no red was ever retried or filed (af-toyety, since #207),
# while its test fake answered anyway. Pipe gh's --json output into jq instead.
# A gh command is read whole, across its `\` continuation lines, up to its
# first pipe.
hits=$(python3 - "$REPO_ROOT/bin" "$REPO_ROOT/lib" <<'SCAN'
import re, sys
from pathlib import Path
for root in sys.argv[1:]:
    for path in sorted(Path(root).rglob("*")):
        if not path.is_file():
            continue
        lines = path.read_text(errors="ignore").splitlines()
        i = 0
        while i < len(lines):
            start, command = i, lines[i]
            while command.endswith("\\") and i + 1 < len(lines):
                i += 1
                command = command[:-1] + " " + lines[i]
            i += 1
            if command.lstrip().startswith("#"):
                continue
            for m in re.finditer(r"\bgh\s[^|]*", command):
                if re.search(r"\s--jq\b", m.group(0)) and re.search(r"\s--arg(json)?\s", m.group(0)):
                    print(f"{path}:{start + 1}: {lines[start].strip()}")
SCAN
)
if [ -n "$hits" ]; then
  printf '%s\n' "$hits" >&2
  echo "FAIL: gh --jq has no --arg/--argjson; pipe gh's --json output into" \
    "jq --arg instead" >&2
  exit 1
fi
echo "OK no shipped gh --jq call passes --arg"
