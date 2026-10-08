#!/usr/bin/env bash
#
# Shared stop of an isolated-city trial (af-v9t5vz).
#
# Every tests/*-isolated-city-test.sh runs a real supervisor in a trial
# directory and stops it in its cleanup. `gc supervisor stop` names no
# supervisor: it stops the one GC_HOME points at, and with GC_HOME unset or
# left to a session's own value that is the live Factory's. The stop was
# safe only because each test exports GC_HOME to its trial directory a few
# lines below its cleanup. On 2026-10-08 a worker copied part of such a test
# into a probe, without those lines: the cleanup body ran as plain commands,
# reached the live supervisor, and the Factory stayed down 56 minutes.
#
# Usage, in a trial's cleanup:
#
#   . "$ROOT/tests/lib/isolated-city.sh"
#   isolated_city_stop "$TRIAL" "$CITY" >/dev/null 2>&1 || true
#
# isolated_city_stop <trial-dir> <city-dir>
#   Stops the trial's city, then its supervisor -- only when GC_HOME is a
#   path inside <trial-dir>. Otherwise it stops nothing, says why on stderr
#   and returns 1. The city is stopped only when it is inside <trial-dir>
#   too: `gc --city "" stop` would walk up from the current directory.
#
# A copy of a cleanup that does not carry this file calls a function that
# does not exist, and stops nothing either. No test stops a supervisor or a
# city any other way: tests/isolated-city-stop-guard-test.sh checks it.

# _isolated_city_inside <path> <dir>: <path> resolves strictly inside <dir>.
_isolated_city_inside() {
  local path dir
  [ -n "${1:-}" ] && [ -n "${2:-}" ] || return 1
  dir=$(realpath -m -- "$2" 2>/dev/null) || return 1
  path=$(realpath -m -- "$1" 2>/dev/null) || return 1
  [ "$dir" != "/" ] || return 1
  case "$path" in
    "$dir"/*) return 0 ;;
  esac
  return 1
}

isolated_city_stop() {
  local trial=${1:-} city=${2:-}
  if ! _isolated_city_inside "${GC_HOME:-}" "$trial"; then
    echo "isolated_city_stop: nothing stopped -- GC_HOME (${GC_HOME:-unset}) is not inside the trial directory (${trial:-none}): gc would reach the live supervisor" >&2
    return 1
  fi
  if _isolated_city_inside "$city" "$trial"; then
    gc --city "$city" stop || true
  fi
  gc supervisor stop
}
