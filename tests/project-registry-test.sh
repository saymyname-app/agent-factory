#!/usr/bin/env bash
#
# lib/project_registry.sh is the one loader config/projects/<project>.toml
# files feed into lib/protected_rigs.sh (bin/pr-autopilot's and
# bin/factory-do-work-workspace's protection table), bin/factory-guard's
# rig loop and project-file coverage check, bin/factory-delivery-guard's
# RIGS array, and bin/deliver-close's required-CI lookup (af-vsevn). This
# proves that adding a third, wholly synthetic project gets picked up by
# every one of those consumer paths with nothing but a new project file --
# and that a rig Gas City knows about with no project file is caught with
# an operator-readable reason, not silently skipped.
#
# All project/rig names here are synthetic fixtures, never real Factory data.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

# shellcheck source=lib/project_registry.sh
. "$REPO_ROOT/lib/project_registry.sh"

CONFIG_DIR="$TMP/config/projects"
mkdir -p "$CONFIG_DIR"

cat > "$CONFIG_DIR/zz-fixture-hq.toml" <<'EOF'
rig_dir = "."
repo = "zz-fixture/hq-repo"
protected_branch = "main"
required_ci = "HQ CI"
EOF

cat > "$CONFIG_DIR/zz-fixture-rig-a.toml" <<'EOF'
rig_dir = "rigs/zz-fixture-rig-a"
repo = "zz-fixture/rig-a-repo"
protected_branch = "dev"
required_ci = "Rig A CI"
EOF

# ---------------------------------------------------------------------------
# 1. baseline: two projects, protected_rigs.sh-shaped rows and rig names
# ---------------------------------------------------------------------------
rows="$(project_registry_rows "$CONFIG_DIR")"
[ "$(printf '%s\n' "$rows" | wc -l)" -eq 2 ] \
  || fail "expected 2 rows before adding the third project, got: $rows"

names="$(project_registry_rig_names "$CONFIG_DIR")"
[ "$names" = "zz-fixture-rig-a" ] \
  || fail "expected only zz-fixture-rig-a before adding the third project, got: $names"

# ---------------------------------------------------------------------------
# 2. add a third, wholly synthetic project with only a new project file --
#    no code change anywhere else -- and it must appear everywhere.
# ---------------------------------------------------------------------------
cat > "$CONFIG_DIR/zz-fixture-rig-b.toml" <<'EOF'
rig_dir = "rigs/zz-fixture-rig-b"
repo = "zz-fixture/rig-b-repo"
protected_branch = "dev"
required_ci = "Rig B CI"
EOF

# 2a. lib/protected_rigs.sh / pr-autopilot coverage: the new project's row
#     appears in PROTECTED_RIGS-shaped output.
rows="$(project_registry_rows "$CONFIG_DIR")"
printf '%s\n' "$rows" | grep -qx "rigs/zz-fixture-rig-b|zz-fixture/rig-b-repo|dev|Rig B CI|zz-fixture-rig-b" \
  || fail "the new project's row did not appear in project_registry_rows: $rows"

# 2b. bin/factory-guard's rig loop / bin/factory-delivery-guard's RIGS:
#     the new rig's directory name appears.
names="$(project_registry_rig_names "$CONFIG_DIR")"
printf '%s\n' "$names" | grep -qx "zz-fixture-rig-b" \
  || fail "the new rig did not appear in project_registry_rig_names: $names"

# 2c. bin/deliver-close's required-CI lookup: the new repo resolves to its
#     project file's required_ci.
ci="$(project_registry_ci_for_repo "$CONFIG_DIR" "zz-fixture/rig-b-repo")" \
  || fail "project_registry_ci_for_repo did not find the new project's repo"
[ "$ci" = "Rig B CI" ] || fail "expected required_ci 'Rig B CI', got '$ci'"

# 2d. bin/factory-guard's project-file coverage check: passes once Gas City's
#     registered rigs (., zz-fixture-rig-a, zz-fixture-rig-b) all have a
#     project file.
project_registry_check_coverage "$CONFIG_DIR" "." "rigs/zz-fixture-rig-a" "rigs/zz-fixture-rig-b" \
  || fail "check_coverage failed even though every registered rig has a project file"

# ---------------------------------------------------------------------------
# 3. a rig Gas City knows about with NO project file fails loudly, by name,
#    not silently -- this is what would have caught af-vsevn's failure mode.
# ---------------------------------------------------------------------------
coverage_err="$(project_registry_check_coverage "$CONFIG_DIR" "." "rigs/zz-fixture-rig-a" "rigs/zz-fixture-rig-b" "rigs/zz-fixture-orphan-rig" 2>&1)" && \
  fail "check_coverage should have failed for an unregistered project file"
printf '%s\n' "$coverage_err" | grep -q "zz-fixture-orphan-rig" \
  || fail "check_coverage's failure did not name the orphan rig: $coverage_err"

echo "OK lib/project_registry.sh: a new project file alone gives a rig protected_rigs/guard/delivery-guard/deliver-close coverage, and an unregistered rig fails loudly by name"

# ---------------------------------------------------------------------------
# 4. project_registry_check_project_coverage: config/project-descriptors/
#    (T04, af-xqgvat) each declare a project_id and the rigs it spans -- one
#    rig must belong to exactly one project.
# ---------------------------------------------------------------------------
DESCRIPTORS_DIR="$TMP/config/project-descriptors"
mkdir -p "$DESCRIPTORS_DIR"

cat > "$DESCRIPTORS_DIR/zz-fixture-project-a.json" <<'EOF'
{
  "contract": "agent-factory-project-descriptor/v1",
  "project_id": "zz-fixture-project-a",
  "display_name": "Fixture A",
  "rigs": ["zz-fixture-rig-a"],
  "knowledge_repo": "zz-fixture/knowledge-a",
  "roadmap_path": "docs/roadmap.toml",
  "rituals_status_command": "bin/rituals-status",
  "promotion_branch": {}
}
EOF

cat > "$DESCRIPTORS_DIR/zz-fixture-project-b.json" <<'EOF'
{
  "contract": "agent-factory-project-descriptor/v1",
  "project_id": "zz-fixture-project-b",
  "display_name": "Fixture B",
  "rigs": ["zz-fixture-rig-b"],
  "knowledge_repo": "zz-fixture/knowledge-b",
  "roadmap_path": "docs/roadmap.toml",
  "rituals_status_command": "bin/rituals-status",
  "promotion_branch": {}
}
EOF

# 4a. every given rig belongs to exactly one declared project: passes.
project_registry_check_project_coverage "$DESCRIPTORS_DIR" "zz-fixture-rig-a" "zz-fixture-rig-b" \
  || fail "check_project_coverage failed even though every rig belongs to exactly one project"

# 4b. a rig with no declared project fails loudly, by name.
coverage_err="$(project_registry_check_project_coverage "$DESCRIPTORS_DIR" "zz-fixture-rig-a" "zz-fixture-orphan-rig" 2>&1)" && \
  fail "check_project_coverage should have failed for a rig with no declared project"
printf '%s\n' "$coverage_err" | grep -q "zz-fixture-orphan-rig" \
  || fail "check_project_coverage's failure did not name the orphan rig: $coverage_err"

# 4c. a rig declared in two projects fails loudly, by name, naming both
#     projects.
cat > "$DESCRIPTORS_DIR/zz-fixture-project-c.json" <<'EOF'
{
  "contract": "agent-factory-project-descriptor/v1",
  "project_id": "zz-fixture-project-c",
  "display_name": "Fixture C",
  "rigs": ["zz-fixture-rig-a"],
  "knowledge_repo": "zz-fixture/knowledge-c",
  "roadmap_path": "docs/roadmap.toml",
  "rituals_status_command": "bin/rituals-status",
  "promotion_branch": {}
}
EOF

coverage_err="$(project_registry_check_project_coverage "$DESCRIPTORS_DIR" "zz-fixture-rig-a" 2>&1)" && \
  fail "check_project_coverage should have failed for a rig declared in two projects"
printf '%s\n' "$coverage_err" | grep -q "zz-fixture-rig-a" \
  || fail "check_project_coverage's failure did not name the doubly-declared rig: $coverage_err"
printf '%s\n' "$coverage_err" | grep -q "zz-fixture-project-a" \
  || fail "check_project_coverage's failure did not name one of the two projects: $coverage_err"
printf '%s\n' "$coverage_err" | grep -q "zz-fixture-project-c" \
  || fail "check_project_coverage's failure did not name the other of the two projects: $coverage_err"

echo "OK lib/project_registry.sh: project_registry_check_project_coverage refuses a rig with no project and a rig declared in two projects"

# TOML syntax is decoded by the standard parser for rows and optional fields.
PARSER_DIR="$TMP/parser"
mkdir -p "$PARSER_DIR"
cat > "$PARSER_DIR/fixture.toml" <<'TOML'
rig_dir = 'rigs/fixture'
repo = "fixture/repo" # an inline comment is not part of the value
protected_branch = 'dev'
required_ci = "CI = \"green\""
sling_target = 'fixture-worker' # optional fields use the same TOML semantics
TOML
[ "$(project_registry_rows "$PARSER_DIR")" = 'rigs/fixture|fixture/repo|dev|CI = "green"|fixture' ] \
  || fail "rows did not decode TOML strings and comments"
[ "$(project_registry_dispatch_target "$PARSER_DIR" fixture)" = fixture-worker ] \
  || fail "optional field did not decode TOML"
[ -z "$(project_registry_field "$PARSER_DIR" fixture absent)" ] || fail "absent optional key must stay empty"
[ -z "$(project_registry_field "$PARSER_DIR" absent absent)" ] || fail "absent optional file must stay empty"
[ -z "$(project_registry_rows "$TMP/absent")" ] || fail "absent registry directory must stay empty"

# A file that declares none of the four rig fields is the file of a project
# that spans several rigs (af-vx1tkf): it prints no row and names no rig, and
# its own fields stay readable by its name.
cat > "$PARSER_DIR/zz-fixture-project.toml" <<'TOML'
human_approver = "zz-fixture-approver"
TOML
[ "$(project_registry_rows "$PARSER_DIR")" = 'rigs/fixture|fixture/repo|dev|CI = "green"|fixture' ] \
  || fail "a project file with no rig field must print no row"
[ "$(project_registry_rig_names "$PARSER_DIR")" = fixture ] \
  || fail "a project file with no rig field must name no rig"
[ "$(project_registry_field "$PARSER_DIR" zz-fixture-project human_approver)" = zz-fixture-approver ] \
  || fail "a project file with no rig field must keep its own fields readable"
if coverage_err=$(project_registry_check_coverage "$PARSER_DIR" rigs/zz-fixture-project 2>&1); then
  fail "a project file with no rig field must not cover a registered rig"
fi
[[ "$coverage_err" == *"rigs/zz-fixture-project"* ]] \
  || fail "the coverage refusal did not name the rig left without a file: $coverage_err"

# Required fields and invalid TOML must fail even without the caller's pipefail.
for invalid in missing empty number malformed; do
  cp "$PARSER_DIR/fixture.toml" "$PARSER_DIR/invalid.toml"
  case "$invalid" in
    missing) sed -i '/^required_ci/d' "$PARSER_DIR/invalid.toml" ;;
    empty) sed -i 's/^required_ci.*/required_ci = ""/' "$PARSER_DIR/invalid.toml" ;;
    number) sed -i 's/^required_ci.*/required_ci = 42/' "$PARSER_DIR/invalid.toml" ;;
    malformed) echo 'invalid = [' >> "$PARSER_DIR/invalid.toml" ;;
  esac
  if error=$(set +o pipefail; project_registry_rows "$PARSER_DIR" 2>&1); then
    fail "$invalid registry should be refused"
  fi
  [[ "$error" == *invalid.toml* ]] || fail "refusal must name the invalid file: $error"
done
if project_registry_field "$PARSER_DIR" invalid sling_target >/dev/null 2>&1; then
  fail "optional-field lookup must refuse malformed TOML"
fi
echo "OK project registry: TOML decoding, optional absence, project file with no rig field, and invalid-file refusal"
