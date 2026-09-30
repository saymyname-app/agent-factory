#!/usr/bin/env bash
# project_registry.sh — reads config/projects/<project>.toml (one file per
# project: rig_dir, repo, protected_branch, required_ci) so a rig's
# protection data lives in exactly one place instead of the N hardcoded
# lists (lib/protected_rigs.sh, bin/factory-guard's rig loop,
# bin/factory-delivery-guard's RIGS array, bin/deliver-close's required-CI
# case statement) that used to drift independently (af-vsevn). Every one of
# those now sources this file and reads config/projects/ through it.
#
# Functions take a <config_dir> argument (normally "$ROOT/config/projects")
# rather than hardcoding a path, so tests can point them at a fixture
# directory.

# project_registry_rows <config_dir>
#   Prints one row per config/projects/*.toml file, sorted by filename:
#     rig_dir|repo|protected_branch|required_ci|project_name
#   Fails loudly (non-zero, message on stderr) if a project file is missing
#   a required field.
project_registry_rows() {
  local config_dir="$1" file project_name rig_dir repo protected_branch required_ci key value

  [ -d "$config_dir" ] || return 0

  for file in "$config_dir"/*.toml; do
    [ -e "$file" ] || continue
    project_name="$(basename "$file" .toml)"
    rig_dir="" repo="" protected_branch="" required_ci=""

    while IFS='=' read -r key value; do
      key="$(printf '%s' "$key" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
      value="$(printf '%s' "$value" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^"//' -e 's/"$//')"
      case "$key" in
        rig_dir) rig_dir="$value" ;;
        repo) repo="$value" ;;
        protected_branch) protected_branch="$value" ;;
        required_ci) required_ci="$value" ;;
      esac
    done < <(grep -E '^[a-zA-Z_]+[[:space:]]*=' "$file")

    if [ -z "$rig_dir" ] || [ -z "$repo" ] || [ -z "$protected_branch" ] || [ -z "$required_ci" ]; then
      echo "project_registry: $file is missing one of rig_dir/repo/protected_branch/required_ci" >&2
      return 1
    fi

    printf '%s|%s|%s|%s|%s\n' "$rig_dir" "$repo" "$protected_branch" "$required_ci" "$project_name"
  done | sort
}

# project_registry_rig_names <config_dir>
#   Prints the directory name of each product rig (i.e. every project whose
#   rig_dir is under "rigs/", excluding the HQ root project whose rig_dir is
#   "."), one per line.
project_registry_rig_names() {
  local config_dir="$1" rig_dir _repo _branch _ci _name
  while IFS='|' read -r rig_dir _repo _branch _ci _name; do
    case "$rig_dir" in
      rigs/*) printf '%s\n' "${rig_dir#rigs/}" ;;
    esac
  done < <(project_registry_rows "$config_dir")
}

# project_registry_ci_for_repo <config_dir> <repo>
#   Prints the required_ci for <repo> on stdout and returns 0; returns 1
#   with nothing printed if no project file names that repo.
project_registry_ci_for_repo() {
  local config_dir="$1" repo="$2" r_dir r_repo r_branch r_ci r_name
  while IFS='|' read -r r_dir r_repo r_branch r_ci r_name; do
    if [ "$r_repo" = "$repo" ]; then
      printf '%s\n' "$r_ci"
      return 0
    fi
  done < <(project_registry_rows "$config_dir")
  return 1
}

# project_registry_field <config_dir> <project_name> <key>
#   Prints the raw value of <key> from config_dir/<project_name>.toml, or
#   nothing if the file or the key is absent (returns 0 either way -- these
#   are optional fields; project_registry_rows above already fails loudly
#   on a missing required one). Used for the dispatch-door fields below,
#   which not every project_registry consumer needs.
project_registry_field() {
  local config_dir="$1" project_name="$2" key="$3" file value
  file="$config_dir/$project_name.toml"
  [ -f "$file" ] || return 0
  value=$(grep -E "^[[:space:]]*${key}[[:space:]]*=" "$file" | tail -1 | cut -d'=' -f2-)
  value="$(printf '%s' "$value" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^"//' -e 's/"$//')"
  printf '%s\n' "$value"
}

# project_registry_dispatch_target <config_dir> <project_name>
#   Prints the project's sling_target (the bare qualified-agent name
#   bin/dispatch-door routes to, e.g. "factory-worker" or "claude"), or
#   nothing if unset.
project_registry_dispatch_target() {
  project_registry_field "$1" "$2" "sling_target"
}

# project_registry_dispatch_formulas <config_dir> <project_name>
#   Prints the project's comma-separated allowed-formulas list (e.g.
#   "mol-do-work,build-basic"), or nothing if unset.
project_registry_dispatch_formulas() {
  project_registry_field "$1" "$2" "formulas"
}

# project_registry_check_coverage <config_dir> <rig-dir-1> [<rig-dir-2> ...]
#   Given the rig directories Gas City actually has registered (relative to
#   the Factory root, "." for the HQ root itself), fails with an
#   operator-readable reason on stderr if any of them has no project file.
project_registry_check_coverage() {
  local config_dir="$1"
  shift
  local registered_dir known_dirs missing=0 found

  known_dirs="$(project_registry_rows "$config_dir" | cut -d'|' -f1)" || return 1

  for registered_dir in "$@"; do
    found=0
    while IFS= read -r d; do
      [ "$d" = "$registered_dir" ] && { found=1; break; }
    done <<<"$known_dirs"
    if [ "$found" -ne 1 ]; then
      echo "project_registry: rig '$registered_dir' is registered in Gas City but has no config/projects/*.toml file" >&2
      missing=1
    fi
  done

  [ "$missing" -eq 0 ]
}

# project_registry_check_project_coverage <descriptors_dir> <rig-1> [<rig-2> ...]
#   config/projects/*.toml files (read above) describe rigs, not projects;
#   config/project-descriptors/*.json files (T04, af-xqgvat) each declare a
#   project_id and the rigs it spans. One rig must belong to exactly one
#   project. Given the rig names actually registered with Gas City, fails
#   loudly on stderr, naming the rig, if it belongs to no declared project
#   or to more than one -- this is the CI check the spec asks for (af-oohx2x
#   .12).
project_registry_check_project_coverage() {
  local descriptors_dir="$1"
  shift
  local mapping rig owners count problem=0

  mapping="$(python3 -c '
import json
import sys
from pathlib import Path

directory = Path(sys.argv[1])
if directory.is_dir():
    for file in sorted(directory.glob("*.json")):
        try:
            data = json.loads(file.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        project_id = data.get("project_id")
        rigs = data.get("rigs")
        if not isinstance(project_id, str) or not isinstance(rigs, list):
            continue
        for rig in rigs:
            if isinstance(rig, str):
                print(f"{rig}|{project_id}")
' "$descriptors_dir")" || {
    echo "project_registry: failed to read project descriptors in $descriptors_dir" >&2
    return 1
  }

  for rig in "$@"; do
    owners="$(printf '%s\n' "$mapping" | awk -F'|' -v r="$rig" '$1==r{print $2}')"
    count="$(printf '%s\n' "$owners" | grep -c . || true)"
    if [ "$count" -eq 0 ]; then
      echo "project_registry: rig '$rig' belongs to no declared project (config/project-descriptors/*.json)" >&2
      problem=1
    elif [ "$count" -gt 1 ]; then
      echo "project_registry: rig '$rig' is declared in more than one project: $(printf '%s' "$owners" | tr '\n' ' ')" >&2
      problem=1
    fi
  done

  [ "$problem" -eq 0 ]
}
