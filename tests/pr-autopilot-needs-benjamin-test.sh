#!/usr/bin/env bash
#
# af-qe1bqx: a merged PR whose work bead still waits on Benjamin is not a
# delivery error. deliver-close must keep refusing to close it, while
# pr-autopilot leaves it pending, reconciles other work, and retries it after
# the decision is answered.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
AUTOPILOT="$REPO_ROOT/bin/pr-autopilot"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/factory/rigs/example-backend" "$TMP/factory/rigs/example-frontend" "$TMP/bin"
: > "$TMP/deliver-close.log"

cat > "$TMP/merged.json" <<'JSON'
[
 {"number":705,"headRefName":"do-work/af-waiting","mergeCommit":{"oid":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},"mergedAt":"2026-10-21T00:40:00Z"},
 {"number":706,"headRefName":"do-work/af-ready","mergeCommit":{"oid":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},"mergedAt":"2026-10-21T00:41:00Z"}
]
JSON
cat > "$TMP/all-beads.json" <<'JSON'
[
 {"id":"af-waiting","status":"in_progress","metadata":{"gc.work_branch":"do-work/af-waiting","gc.delivery_contract":"pr-ci-merged-v1","gc.needs_benjamin":"Choisir une variante"}},
 {"id":"af-ready","status":"in_progress","metadata":{"gc.work_branch":"do-work/af-ready","gc.delivery_contract":"pr-ci-merged-v1"}}
]
JSON

cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
if [[ "\$1" == pr && "\$2" == list ]]; then
  if [[ "\$*" != *"example-backend"* ]]; then echo '[]'; exit 0; fi
  if [[ "\$*" == *"--state merged"* ]]; then cat "$TMP/merged.json"; else echo '[]'; fi
  exit 0
fi
if [[ "\$1" == pr && "\$2" == view ]]; then echo '["OPEN","false"]' | jq -r '@tsv'; exit 0; fi
exit 0
STUB
cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
if [[ "\$1" == bd && "\$2" == list && "\$*" == *"--status open"* ]]; then echo '[]'; exit 0; fi
if [[ "\$1" == bd && "\$2" == list && "\$*" == *"--all"* ]]; then cat "$TMP/all-beads.json"; exit 0; fi
if [[ "\$1" == mail ]]; then exit 0; fi
exit 0
STUB
cat > "$TMP/bin/deliver-close" <<STUB
#!/usr/bin/env bash
set -Eeuo pipefail
echo "\$*" >> "$TMP/deliver-close.log"
needs=\$(jq -r --arg id "\$1" '.[] | select(.id == \$id) | .metadata["gc.needs_benjamin"] // ""' "$TMP/all-beads.json")
if [[ -n "\$needs" && "\$needs" != none ]]; then
  echo "deliver-close: ERROR: \$1 carries an active NEEDS BENJAMIN" >&2
  exit 1
fi
exit 0
STUB
chmod +x "$TMP/bin/"*
export PATH="$TMP/bin:$PATH"
export FACTORY_ROOT="$TMP/factory"
export GC_PR_AUTHORS=example-operator
export REVERSIBILITY_CHECK_BIN="$TMP/bin/gh"
export DELIVER_CLOSE_BIN="$TMP/bin/deliver-close"
export PROTECTED_RIGS_CONFIG_DIR="$REPO_ROOT/tests/fixtures/pr-autopilot-projects"
export PR_AUTOPILOT_RECONCILE_CACHE="$TMP/factory/.gc/reconciled.tsv"

if ! out=$("$AUTOPILOT" 2>&1); then
  echo "$out" >&2
  fail "an active NEEDS BENJAMIN made the whole order fail"
fi
grep -q '^af-waiting ' "$TMP/deliver-close.log" \
  && fail "pr-autopilot called the delivery door for a bead it knows cannot close"
grep -q '^af-ready ' "$TMP/deliver-close.log" \
  || fail "the held bead prevented unrelated merged work from reconciling"

jq 'map(if .id == "af-waiting" then .metadata["gc.needs_benjamin"] = "none" else . end)' \
  "$TMP/all-beads.json" > "$TMP/all-beads.next.json"
mv "$TMP/all-beads.next.json" "$TMP/all-beads.json"
: > "$TMP/deliver-close.log"

out=$("$AUTOPILOT" 2>&1) || { echo "$out" >&2; fail "the answered bead did not resume cleanly"; }
grep -q '^af-waiting ' "$TMP/deliver-close.log" \
  || fail "pr-autopilot did not reconcile the bead after NEEDS BENJAMIN cleared"

echo "OK pr-autopilot leaves active NEEDS BENJAMIN work pending and resumes it after the answer"
