#!/usr/bin/env bash
#
# af-37h58 (P03): pr-autopilot used to gate arming on an aggregate over every
# statusCheckRollup entry, regardless of name -- so an unrelated check (or a
# workflow-name/check-name mismatch) could hold a healthy PR, or a genuinely
# red required check could be lost in a sea of green noise. Each repo's real
# ruleset requires a specific check by name (`Tests` for agent-factory,
# `Maven verify` for Say-my-name-back, `Tests and build` for
# Say-my-name-front) -- distinct from the Actions *workflow* name
# (required_ci) deliver-close/retry still key on. This drives pr-autopilot
# against all three repos using their real config/projects/*.toml
# required_check and proves:
#  1. a PR whose required check is green is armed, red is not -- per repo;
#  2. an unrelated check failing never holds a PR whose required check is
#     green (name-specific gating, not an aggregate);
#  3. a config naming a check its live ruleset does not require is reported
#     loudly (a "LOUD:" line and a non-zero exit), via a faked read-only
#     `gh api` ruleset read -- pr-autopilot never mutates GitHub to check this.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
AUTOPILOT="$REPO_ROOT/bin/pr-autopilot"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/factory/rigs/saymyname-backend" "$TMP/factory/rigs/saymyname-frontend" "$TMP/bin"
: > "$TMP/gh.log"; : > "$TMP/gc.log"

# PR 10: agent-factory, required check "Tests" green -> armed.
# PR 11: agent-factory, required check "Tests" red -> not armed.
# PR 12: agent-factory, unrelated check "Lint" red but "Tests" green -> still
#        armed (name-specific gating, not an aggregate over every check).
# PR 20/21: same green/red shape for Say-my-name-back's "Maven verify".
# PR 30/31: same green/red shape for Say-my-name-front's "Tests and build".
cat > "$TMP/af_open.json" <<'JSON'
[
 {"number":10,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"name":"Tests","conclusion":"SUCCESS"}],"headRefOid":"af10","labels":[]},
 {"number":11,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"BLOCKED","statusCheckRollup":[{"name":"Tests","conclusion":"FAILURE"}],"headRefOid":"af11","labels":[]},
 {"number":12,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"name":"Lint","conclusion":"FAILURE"},{"name":"Tests","conclusion":"SUCCESS"}],"headRefOid":"af12","labels":[]}
]
JSON
cat > "$TMP/be_open.json" <<'JSON'
[
 {"number":20,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"context":"Maven verify","state":"SUCCESS"}],"headRefOid":"be20","labels":[]},
 {"number":21,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"BLOCKED","statusCheckRollup":[{"context":"Maven verify","state":"FAILURE"}],"headRefOid":"be21","labels":[]}
]
JSON
cat > "$TMP/fe_open.json" <<'JSON'
[
 {"number":30,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"name":"Tests and build","conclusion":"SUCCESS"}],"headRefOid":"fe30","labels":[]},
 {"number":31,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"BLOCKED","statusCheckRollup":[{"name":"Tests and build","conclusion":"FAILURE"}],"headRefOid":"fe31","labels":[]}
]
JSON

# Ruleset reads (`gh api repos/<repo>/rules/branches/<branch>`, read-only):
# each repo's live required check matches its config/projects declaration --
# proven separately by the mismatch scenario below.
cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gh.log"
if [[ \$1 == api ]] && [[ "\$*" == *"rules/branches"* ]]; then
  case "\$*" in
    *"saymyname-app/agent-factory"*) echo '["Tests"]' ;;
    *"Say-my-name-back"*)            echo '["Maven verify"]' ;;
    *"Say-my-name-front"*)           echo '["Tests and build"]' ;;
    *)                                echo '[]' ;;
  esac
  exit 0
fi
if [[ \$1 == pr && \$2 == list ]]; then
  if [[ "\$*" == *"--state merged"* ]]; then echo '[]'; exit 0; fi
  case "\$*" in
    *"saymyname-app/agent-factory"*) cat "$TMP/af_open.json" ;;
    *"Say-my-name-back"*)            cat "$TMP/be_open.json" ;;
    *"Say-my-name-front"*)           cat "$TMP/fe_open.json" ;;
    *)                                echo '[]' ;;
  esac
  exit 0
fi
if [[ \$1 == pr && \$2 == view ]]; then echo '["OPEN","false"]' | jq -r '@tsv'; exit 0; fi
if [[ \$1 == run && \$2 == list ]]; then echo ''; exit 0; fi
exit 0
STUB
cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gc.log"
if [[ \$1 == bd && \$2 == list ]]; then echo '[]'; exit 0; fi
exit 0
STUB
chmod +x "$TMP/bin/"*
export PATH="$TMP/bin:$PATH"
export FACTORY_ROOT="$TMP/factory"
export REVERSIBILITY_CHECK_BIN="$TMP/bin/gh"

pilot() { "$AUTOPILOT" "$@" 2>&1 || true; }

out=$(pilot)

# --- 1 & 2: green required check arms, red does not, unrelated noise ignored ---
grep -q "^pr merge 10 --repo saymyname-app/agent-factory --auto --squash --delete-branch" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "agent-factory PR #10 (Tests green) was not armed"; }
grep -q "^pr merge 11 " "$TMP/gh.log" && { echo "$out" >&2; fail "agent-factory PR #11 (Tests red) was armed"; }
grep -qF "bd create [ci] PR #11 failed required checks" "$TMP/gc.log" \
  || { echo "$out" >&2; fail "agent-factory PR #11 (Tests red) was not flagged"; }
grep -q "^pr merge 12 --repo saymyname-app/agent-factory --auto --squash --delete-branch" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "agent-factory PR #12 (Lint red, Tests green) was held by an unrelated check"; }

grep -q "^pr merge 20 --repo saymyname-app/Say-my-name-back --auto --squash --delete-branch" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "backend PR #20 (Maven verify green) was not armed"; }
grep -q "^pr merge 21 " "$TMP/gh.log" && { echo "$out" >&2; fail "backend PR #21 (Maven verify red) was armed"; }
grep -qF "bd create [ci] PR #21 failed required checks" "$TMP/gc.log" \
  || { echo "$out" >&2; fail "backend PR #21 (Maven verify red) was not flagged"; }

grep -q "^pr merge 30 --repo saymyname-app/Say-my-name-front --auto --squash --delete-branch" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "frontend PR #30 (Tests and build green) was not armed"; }
grep -q "^pr merge 31 " "$TMP/gh.log" && { echo "$out" >&2; fail "frontend PR #31 (Tests and build red) was armed"; }
grep -qF "bd create [ci] PR #31 failed required checks" "$TMP/gc.log" \
  || { echo "$out" >&2; fail "frontend PR #31 (Tests and build red) was not flagged"; }

# --- 3: config declares a check name the live ruleset does not require -> loud ---
: > "$TMP/gh.log"; : > "$TMP/gc.log"
cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gh.log"
if [[ \$1 == api ]] && [[ "\$*" == *"rules/branches"* ]]; then
  case "\$*" in
    *"saymyname-app/agent-factory"*) echo '["Some Other Check"]' ;;
    *"Say-my-name-back"*)            echo '["Maven verify"]' ;;
    *"Say-my-name-front"*)           echo '["Tests and build"]' ;;
    *)                                echo '[]' ;;
  esac
  exit 0
fi
if [[ \$1 == pr && \$2 == list ]]; then echo '[]'; exit 0; fi
exit 0
STUB
chmod +x "$TMP/bin/gh"

set +e
out=$("$AUTOPILOT" 2>&1); rc=$?
set -e
printf '%s\n' "$out" | grep -qF "LOUD: config/projects names required_check='Tests' for saymyname-app/agent-factory but the live ruleset on main does not require it" \
  || { echo "$out" >&2; fail "config/ruleset drift on agent-factory was not reported loudly"; }
[ "$rc" -ne 0 ] || { echo "$out" >&2; fail "config/ruleset drift did not fail the run (exit 0)"; }
printf '%s\n' "$out" | grep -q "LOUD:.*Say-my-name-back" && fail "backend's required_check matched its live ruleset but was reported as drift"
printf '%s\n' "$out" | grep -q "LOUD:.*Say-my-name-front" && fail "frontend's required_check matched its live ruleset but was reported as drift"

echo "OK pr-autopilot arms/holds on each repo's real required check name and reports config/ruleset drift loudly"
