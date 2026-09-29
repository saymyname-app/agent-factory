#!/usr/bin/env bash
# protected_rigs.sh — single source of truth for which rig+branch pairs are
# protected: no writer formula may commit directly to them, only land
# changes through a branch + PR. Sourced by bin/pr-autopilot (to decide what
# to arm for auto-merge) and bin/factory-do-work-workspace (to decide when a
# do-work dispatch must be isolated in a worktree instead of committing in
# place). Keep both consumers pointed at this one table (af-09hxz) so a rig
# added here is protected everywhere, not just in whichever script an author
# remembered to update.
#
# The actual data lives in config/projects/<project>.toml (one file per
# project — af-vsevn), not here: this file just loads it, through
# lib/project_registry.sh, into the PROTECTED_RIGS array consumers already
# expect, so adding a rig means adding one project file, not editing this
# array by hand.
#
# PROTECTED_RIGS rows: "rig_dir|repo|protected_branch|required_ci"
#
# PROTECTED_RIGS_CONFIG_DIR overrides the config/projects directory this
# reads (default: this repo's real config/projects) so tests can point it at
# a synthetic project-fixture directory instead of asserting against the
# real SayMyName rig names (P23). Unset in every real dispatch/pr-autopilot
# invocation, so production behavior is unchanged.
_PROTECTED_RIGS_LIB_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=lib/project_registry.sh
. "$_PROTECTED_RIGS_LIB_DIR/project_registry.sh"

PROTECTED_RIGS=()
while IFS='|' read -r _pr_rig_dir _pr_repo _pr_branch _pr_ci _pr_name; do
  PROTECTED_RIGS+=("${_pr_rig_dir}|${_pr_repo}|${_pr_branch}|${_pr_ci}")
done < <(project_registry_rows "${PROTECTED_RIGS_CONFIG_DIR:-$_PROTECTED_RIGS_LIB_DIR/../config/projects}")
unset _pr_rig_dir _pr_repo _pr_branch _pr_ci _pr_name
