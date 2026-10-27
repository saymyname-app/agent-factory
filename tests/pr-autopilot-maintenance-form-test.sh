#!/usr/bin/env bash
#
# pr-autopilot arms a fix of the Factory itself (rig ".", branch fix/... or
# do-work/...) only once its body says where else its defect is:
# « Catégorie : » a code of docs/DEFECT_CLASSES.md, « Où ailleurs : »,
# « Contrôle de catégorie : » (af-npz9v1.25, study B, PR #720). From 15 to
# 22/10/2026 three defect classes came back 5 to 7 times each: every fix
# repaired the place it was seen and wrote the rest « hors périmètre ».
# Without the lines the PR is held, labelled and explained once; a product
# rig's PR, or a Factory PR that is not a fix branch, is not affected.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
AUTOPILOT="$REPO_ROOT/bin/pr-autopilot"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/factory/rigs/example-backend" "$TMP/bin" "$TMP/projects" "$TMP/bodies"
: > "$TMP/gh.log"; : > "$TMP/gc.log"
cat > "$TMP/projects/factory.toml" <<'TOML'
rig_dir = "."
repo = "example-corp/factory"
protected_branch = "main"
required_ci = "Factory CI"
required_check = "Tests"
TOML
cp "$REPO_ROOT/tests/fixtures/pr-autopilot-projects/backend.toml" "$TMP/projects/"

pr() {  # number branch -> one green, unarmed PR of the operator
  printf '{"number":%s,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"conclusion":"SUCCESS"}],"headRefOid":"sha%s","headRefName":"%s","labels":[]}' "$1" "$1" "$2"
}
# 1: fix/ without the lines       2: do-work/ with the three lines
# 3: fix/ naming a class unknown on main, which its head adds
# 4: feat/ without the lines      5: fix/ « Catégorie : aucune — raison »
printf '[%s,%s,%s,%s,%s]\n' "$(pr 1 fix/launch-copies)" "$(pr 2 do-work/af-abc123)" "$(pr 3 fix/new-class)" \
  "$(pr 4 feat/cockpit-page)" "$(pr 5 fix/decision-carried-out)" > "$TMP/factory-open.json"
printf '[%s]\n' "$(pr 6 fix/backend-thing)" > "$TMP/backend-open.json"
printf 'Corrige le cas observé.\n' > "$TMP/bodies/1"
printf 'Closes af-abc123.\n\nCatégorie : P — survit à son lanceur\nOù ailleurs : grep, 2 chemins corrigés ici\nContrôle de catégorie : tests/project-launch-test.py\n' > "$TMP/bodies/2"
printf 'Catégorie : Q — nouvelle\nOù ailleurs : aucun autre chemin\nContrôle de catégorie : tests/q-test.py\n' > "$TMP/bodies/3"
printf 'Une page.\n' > "$TMP/bodies/4"
printf 'Catégorie : aucune — exécute une décision de Benjamin\n' > "$TMP/bodies/5"
printf 'rien\n' > "$TMP/bodies/6"
{ cat "$REPO_ROOT/docs/DEFECT_CLASSES.md"
  printf '\n## Q — Nouvelle\n\n- Invariant : x.\n- Contrôle : aucun — y.\n- Occurrences : #3.\n- Ouvertes : aucune connue.\n'
} > "$TMP/head-registry-3.md"

cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gh.log"
if [[ \$1 == pr && \$2 == comment ]]; then
  prev=; for a in "\$@"; do [[ \$prev == --body-file ]] && cat "\$a" >> "$TMP/comments-\$3.md"; prev=\$a; done
  exit 0
fi
if [[ \$1 == pr && \$2 == view && "\$*" == *"--json comments"* ]]; then cat "$TMP/comments-\$3.md" 2>/dev/null; exit 0; fi
if [[ \$1 == pr && \$2 == view && "\$*" == *"--json body"* ]]; then exec cat "$TMP/bodies/\$3"; fi
if [[ \$1 == pr && \$2 == list ]]; then
  if [[ "\$*" == *"--state open"* && "\$*" == *"example-corp/factory"* ]]; then cat "$TMP/factory-open.json"
  elif [[ "\$*" == *"--state open"* && "\$*" == *"example-backend"* ]]; then cat "$TMP/backend-open.json"
  else echo '[]'; fi
  exit 0
fi
if [[ \$1 == pr && \$2 == view ]]; then echo '["OPEN","false"]' | jq -r '@tsv'; exit 0; fi
if [[ \$1 == api ]]; then
  for a in "\$@"; do
    if [[ "\$a" == repos/example-corp/factory/contents/docs/DEFECT_CLASSES.md?ref=sha3 ]]; then cat "$TMP/head-registry-3.md"; exit 0; fi
    if [[ "\$a" == *contents/docs/DEFECT_CLASSES.md* ]]; then echo 'Not Found' >&2; exit 1; fi
  done
  exit 0
fi
exit 0
STUB
cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gc.log"
if [[ \$1 == bd && (\$2 == list || \$2 == show) ]]; then echo '[]'; exit 0; fi
exit 0
STUB
printf '#!/usr/bin/env bash\nexit 0\n' > "$TMP/bin/true-check"
chmod +x "$TMP/bin/"*
export PATH="$TMP/bin:$PATH"
export FACTORY_ROOT="$TMP/factory"
export GC_PR_AUTHORS=example-operator
export REVERSIBILITY_CHECK_BIN="$TMP/bin/true-check"
export PROTECTED_RIGS_CONFIG_DIR="$TMP/projects"
export GC_OPERATOR_NAME=operator-1
export REVERSIBILITY_CACHE="$TMP/factory/.gc/rev-cache.tsv"
export PR_AUTOPILOT_NOW_EPOCH
PR_AUTOPILOT_NOW_EPOCH=$(date -u -d '2026-10-27T16:00:00Z' +%s)

pilot() { "$AUTOPILOT" "$@" 2>&1 || true; }
armed() { grep -q "^pr merge $1 --repo $2 --auto --squash" "$TMP/gh.log"; }

# --- dry run: reported, nothing changes -----------------------------------------
out=$(pilot --dry-run)
grep -q "PR #1: HELD -> maintenance-form-missing" <<<"$out" || { echo "$out" >&2; fail "dry run did not report the hold of PR 1"; }
grep -qE '^(pr (merge|comment)|label create|api -X)' "$TMP/gh.log" && fail "--dry-run mutated GitHub"

# --- the real pass --------------------------------------------------------------
: > "$TMP/gh.log"
out=$(pilot)
armed 1 example-corp/factory && fail "a fix without its three lines was armed"
grep -q "^pr comment 1 " "$TMP/gh.log" || { echo "$out" >&2; fail "PR 1's hold was not explained"; }
for line in "Catégorie :" "Où ailleurs :" "Contrôle de catégorie :"; do
  grep -qF "« $line » absente" "$TMP/comments-1.md" || fail "PR 1's explanation does not name « $line »"
done
grep -q "^api -X POST repos/example-corp/factory/issues/1/labels -f labels\[\]=maintenance-form-missing" "$TMP/gh.log" \
  || fail "PR 1 not labelled"
armed 2 example-corp/factory || { echo "$out" >&2; fail "a do-work fix carrying its three lines was not armed"; }
armed 3 example-corp/factory || { echo "$out" >&2; fail "a fix whose head adds its new class was not armed"; }
armed 4 example-corp/factory || { echo "$out" >&2; fail "a feature branch was held by the maintenance form"; }
armed 5 example-corp/factory || { echo "$out" >&2; fail "« Catégorie : aucune — raison » was not accepted"; }
armed 6 example-corp/example-backend || { echo "$out" >&2; fail "a product rig's PR was held by the maintenance form"; }
grep -q "pr view 6 .*--json body" "$TMP/gh.log" && fail "the body of a product rig's PR was read"

# --- second pass: labelled -> explained once ------------------------------------
jq '(.[]|select(.number==1)).labels=[{"name":"maintenance-form-missing"}]' "$TMP/factory-open.json" > "$TMP/next.json"
mv "$TMP/next.json" "$TMP/factory-open.json"
: > "$TMP/gh.log"
pilot >/dev/null
grep -q "^pr comment 1 " "$TMP/gh.log" && fail "PR 1's hold was explained twice"
armed 1 example-corp/factory && fail "held PR 1 was armed on a later pass"

# --- the body is completed: label removed, armed --------------------------------
cp "$TMP/bodies/2" "$TMP/bodies/1"
: > "$TMP/gh.log"
out=$(pilot)
grep -q "^api -X DELETE repos/example-corp/factory/issues/1/labels/maintenance-form-missing" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "PR 1 kept its label once its body was complete"; }
armed 1 example-corp/factory || { echo "$out" >&2; fail "PR 1 was not armed once its body was complete"; }

# --- an unreadable body is never read as complete -------------------------------
rm "$TMP/bodies/2"
printf '[%s]\n' "$(pr 2 do-work/af-abc123)" > "$TMP/factory-open.json"
: > "$TMP/gh.log"
out=$(pilot)
armed 2 example-corp/factory && { echo "$out" >&2; fail "a PR whose body could not be read was armed"; }
grep -q "PR #2: body unreadable" <<<"$out" || { echo "$out" >&2; fail "an unreadable body was not reported"; }

echo "OK pr-autopilot arms a Factory fix only once it says where else its defect is"
