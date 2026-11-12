#!/usr/bin/env bash
#
# af-41i8d0 (decision af-wpzic4, docs/DELIVERY.md): on the Factory's own
# repo, pr-autopilot also merges a maintenance PR into a convoy's
# integration/<spec> branch -- never armed (those branches have no ruleset),
# merged directly once its required check is green and it is CLEAN -- and
# only when lib/integration_maintenance.py accepts its bead and the files it
# changes; otherwise it is held, labelled and explained once. A merged one is
# finalized through bin/deliver-close like any other. The rule itself (which
# bead, which files) is proven by tests/integration-maintenance-test.py; this
# file proves its transmission through pr-autopilot.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
AUTOPILOT="$REPO_ROOT/bin/pr-autopilot"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/bin" "$TMP/projects"
: > "$TMP/gh.log"; : > "$TMP/close.log"
cat > "$TMP/projects/factory.toml" <<'TOML'
rig_dir = "."
repo = "example-corp/factory"
protected_branch = "main"
required_ci = "Factory CI"
required_check = "Tests"
TOML

# --- the Factory checkout (rig "."), its origin, a convoy, two repairs --------
g() { git -c user.email=t@t -c user.name=t -c commit.gpgsign=false "$@"; }
git init -q --bare "$TMP/origin.git"
git init -q -b main "$TMP/factory"
mkdir -p "$TMP/factory/tests" "$TMP/factory/bin"
echo base > "$TMP/factory/tests/t.py"; echo tool > "$TMP/factory/bin/tool"
g -C "$TMP/factory" add -A; g -C "$TMP/factory" commit -qm base
git -C "$TMP/factory" remote add origin "$TMP/origin.git"
git -C "$TMP/factory" push -q origin main
work() {  # branch from file content -> pushes <branch> off <from>, prints its head
  g -C "$TMP/factory" checkout -q -b "$1" "$2"
  echo "$4" > "$TMP/factory/$3"; g -C "$TMP/factory" commit -qam "$1"
  git -C "$TMP/factory" push -q origin "$1"; git -C "$TMP/factory" rev-parse HEAD
  g -C "$TMP/factory" checkout -q main
}
work integration/af-spec main tests/t.py convoy >/dev/null
OK_SHA=$(work do-work/af-ok integration/af-spec tests/t.py repaired)
BAD_SHA=$(work do-work/af-bad integration/af-spec bin/tool changed)

pr() {  # number branch sha -> one green, CLEAN, unarmed PR of the operator
  printf '{"number":%s,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"name":"Tests","conclusion":"SUCCESS"}],"headRefOid":"%s","headRefName":"%s","labels":[]}' "$1" "$3" "$2"
}
printf '[%s,%s]\n' "$(pr 10 do-work/af-ok "$OK_SHA")" "$(pr 11 do-work/af-bad "$BAD_SHA")" > "$TMP/integration-open.json"
printf '[{"number":12,"headRefName":"do-work/af-done","mergeCommit":{"oid":"%s"},"mergedAt":"2026-11-12T17:00:00Z"}]\n' \
  "$(printf 'c%.0s' {1..40})" > "$TMP/integration-merged.json"

bead() {  # id status
  printf '{"id":"%s","status":"%s","labels":["maintenance"],"metadata":{"gc.authorized_by":"af-wpzic4","gc.work_branch":"do-work/%s","gc.work_base_branch":"integration/af-spec"}}' "$1" "$2" "$1"
}
printf '[%s,%s,%s]\n' "$(bead af-ok in_progress)" "$(bead af-bad in_progress)" "$(bead af-done in_progress)" > "$TMP/beads.json"
printf 'Closes af-ok.\n\nCatégorie : aucune — test\nOù ailleurs : aucun\nContrôle de catégorie : aucun\n' > "$TMP/body"

cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gh.log"
if [[ \$1 == pr && \$2 == comment ]]; then
  prev=; for a in "\$@"; do [[ \$prev == --body-file ]] && cat "\$a" >> "$TMP/comments-\$3.md"; prev=\$a; done
  exit 0
fi
if [[ \$1 == pr && \$2 == view && "\$*" == *"--json comments"* ]]; then cat "$TMP/comments-\$3.md" 2>/dev/null; exit 0; fi
if [[ \$1 == pr && \$2 == view && "\$*" == *"--json body"* ]]; then exec cat "$TMP/body"; fi
if [[ \$1 == pr && \$2 == view && "\$*" == *"--json state"* ]]; then echo MERGED; exit 0; fi
if [[ \$1 == pr && \$2 == list ]]; then
  case "\$*" in
    *"--state open --base integration/af-spec"*) cat "$TMP/integration-open.json" ;;
    *"--state merged --base integration/af-spec"*) cat "$TMP/integration-merged.json" ;;
    *) echo '[]' ;;
  esac
  exit 0
fi
if [[ \$1 == api && \$2 == repos/example-corp/factory/git/matching-refs/heads/integration/ ]]; then
  echo refs/heads/integration/af-spec; exit 0
fi
exit 0
STUB
cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
if [[ \$1 == bd && \$2 == list ]]; then cat "$TMP/beads.json"; exit 0; fi
if [[ \$1 == bd && \$2 == show ]]; then jq --arg id "\$3" '[.[]|select(.id==\$id)]' "$TMP/beads.json"; exit 0; fi
exit 0
STUB
cat > "$TMP/bin/deliver-close" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/close.log"
STUB
printf '#!/usr/bin/env bash\nexit 0\n' > "$TMP/bin/true-check"
chmod +x "$TMP/bin/"*
export PATH="$TMP/bin:$PATH"
export FACTORY_ROOT="$TMP/factory"
export GC_BIN="$TMP/bin/gc"
export DELIVER_CLOSE_BIN="$TMP/bin/deliver-close"
export GC_PR_AUTHORS=example-operator
export REVERSIBILITY_CHECK_BIN="$TMP/bin/true-check"
export PROTECTED_RIGS_CONFIG_DIR="$TMP/projects"
export GC_OPERATOR_NAME=operator-1
export REVERSIBILITY_CACHE="$TMP/factory/.gc/rev-cache.tsv"

out=$("$AUTOPILOT" 2>&1 || true)

# Allowed: merged directly at its exact head, never armed.
grep -q "^pr merge 10 --repo example-corp/factory --squash --match-head-commit $OK_SHA" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "an allowed repair into integration/af-spec was not merged at its head"; }
grep -q "^pr merge 1[01] .*--auto" "$TMP/gh.log" && fail "a PR into integration/af-spec was armed"

# Refused (bin/tool is not test/harness code): held, labelled, explained, not merged.
grep -q "^pr merge 11 " "$TMP/gh.log" && fail "a PR changing bin/tool was merged into integration/af-spec"
grep -q "PR #11: HELD -> integration-maintenance-refused" <<<"$out" || { echo "$out" >&2; fail "PR 11 was not held"; }
grep -qF "bin/tool : hors code de test/harnais" "$TMP/comments-11.md" || fail "PR 11's explanation does not name bin/tool"
grep -q "^api -X POST repos/example-corp/factory/issues/11/labels -f labels\[\]=integration-maintenance-refused" "$TMP/gh.log" \
  || fail "PR 11 not labelled"

# Merged into integration/af-spec: finalized through deliver-close.
grep -q "^af-done --repo example-corp/factory --pr 12 " "$TMP/close.log" \
  || { echo "$out" >&2; fail "the merged integration PR was not finalized through deliver-close"; }

echo "OK pr-autopilot merges into integration/<spec> only what docs/DELIVERY.md allows, and finalizes it"
