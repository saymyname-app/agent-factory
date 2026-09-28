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
