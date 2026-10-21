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

# isolated_city_disable_dog <trial-dir> <city-dir>
#   The minimal Gas City template imports bd.dog with a pool of two sessions.
#   Delivery trials replace the workspace provider with a role-specific stub,
#   so an unrelated maintenance wisp would run that stub with the wrong
#   contract and contend with the actors under test. Disable the imported pool
#   in these disposable cities; Dolt itself and the controller keep running.
isolated_city_disable_dog() {
  local trial=${1:-} city=${2:-} config
  if ! _isolated_city_inside "$city" "$trial"; then
    echo "isolated_city_disable_dog: city (${city:-unset}) is not inside the trial directory (${trial:-none})" >&2
    return 1
  fi
  config="$city/city.toml"
  if [ ! -f "$config" ]; then
    echo "isolated_city_disable_dog: city config does not exist: $config" >&2
    return 1
  fi
  grep -qF '# isolated-city: disable bd.dog' "$config" && return 0
  printf '\n# isolated-city: disable bd.dog\n[[patches.agent]]\nname = "dog"\nmax_active_sessions = 0\n' >> "$config"
}

# isolated_city_remove <trial-dir>
#   Removes the trial directory once its processes are stopped (af-foq4t7).
#   A process still writing in it -- one whose command line does not name the
#   trial, so `pkill -f "$TRIAL/"` missed it -- makes `rm -rf` fail with
#   "Directory not empty"; under `set -e` in the EXIT trap that failed a
#   trial that had passed (2026-10-18 nightly,
#   tests/ticket-author-isolated-city-test.sh: a gc run under the trial's
#   GC_HOME was refilling $TRIAL/h/cache). Each retry kills the processes
#   whose working directory or environment points inside the trial, never
#   this shell itself, which first leaves for /. Refuses an empty path or /.
isolated_city_remove() {
  local trial=${1:-} proc cwd _
  [ -n "$trial" ] && [ "$(realpath -m -- "$trial" 2>/dev/null)" != / ] || return 1
  trial=$(realpath -m -- "$trial")
  cd / || return 1
  for _ in 1 2 3 4 5; do
    rm -rf -- "$trial" 2>/dev/null && return 0
    for proc in /proc/[0-9]*; do
      [ "${proc#/proc/}" != "$$" ] && [ "${proc#/proc/}" != "${BASHPID:-$$}" ] || continue
      cwd=$(readlink -- "$proc/cwd" 2>/dev/null) || continue
      case "$cwd" in
        "$trial"|"$trial"/*) kill -9 "${proc#/proc/}" 2>/dev/null || true ;;
        *) grep -qF -- "=$trial/" <<<"$(tr '\0' '\n' 2>/dev/null <"$proc/environ")" \
             && kill -9 "${proc#/proc/}" 2>/dev/null || true ;;
      esac
    done
    pkill -9 -f -- "$trial/" >/dev/null 2>&1 || true
    sleep 1
  done
  rm -rf -- "$trial"
}
