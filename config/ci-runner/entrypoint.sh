#!/bin/bash
# Inside the job's container: take the one-job runner configuration on the
# first line of standard input (never on a command line of the host, never in
# a file) and run GitHub's runner with it. It serves one job and exits.
set -euo pipefail
IFS= read -r jitconfig || true
[ -n "${jitconfig:-}" ] || { echo "factory-ci-entrypoint: no runner configuration received" >&2; exit 64; }
exec /runner/run.sh --jitconfig "$jitconfig"
