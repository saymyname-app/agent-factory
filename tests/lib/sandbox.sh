#!/usr/bin/env bash
#
# Shared sandbox harness (P10, af-ygibh): every test gets a throwaway HOME,
# city, beads dir and tmux dir, with fake `gc`, `bd`, `gh`, `codex` and
# `claude` first on PATH. A test that needs the real `gc`/`bd` opts in
# explicitly and still runs only against the throwaway city this harness
# creates, never the live one.
#
# Before this, tests/local-only-tests-order-test.sh and
# tests/backup-freshness-order-test.sh each hand-rolled this same isolation
# (throwaway TEST_CITY, stub tmux dir, env-scrubbing `run_clean`) because
# GC_CITY/GC_CITY_PATH/GC_BEADS_SCOPE_ROOT silently redirect a `gc`/`bd` call
# at the LIVE Factory city if left set (live incident during this ticket's
# own development: af-ize6u), and a real `gc mail send --notify` execs the
# real `codex`/`claude` CLI under a live tmux server if not stubbed (an
# orphaned session held the live escalation-door flock for 40+ min,
# root-caused 2026-09-28).
#
# Usage:
#
#   . "$ROOT/tests/lib/sandbox.sh"
#   sandbox_init                 # fake gc/bd/gh/codex/claude first on PATH
#   ... use $SANDBOX_CITY as --city / $GC_CITY ...
#
#   sandbox_init --real-gc       # opt in: real gc/bd reachable; codex/claude
#                                 # stay faked. Point every gc/bd call at
#                                 # $SANDBOX_CITY -- never anything else.
#
# sandbox_init exports HOME, TMUX_TMPDIR, GC_CITY, GC_CITY_PATH,
# GC_BEADS_SCOPE_ROOT and PATH, unsets the env vars that can redirect a call
# at the live city or session, and registers an EXIT trap that kills
# anything the test started under $SANDBOX_DIR and removes it. Set
# KEEP_SANDBOX=1 to preserve the directory (e.g. for debugging a failure)
# instead of deleting it.
#
# It also (re)exports GC_BIN/BD_BIN/GH_BIN to the fakes: every Gas City
# agent session pre-exports GC_BIN to the real installed `gc`, and a script
# resolving `${GC_BIN:-gc}` picks that up regardless of what is first on
# PATH -- a stubbed PATH alone does not stop it (live incident 2026-09-29,
# af-0h4vnc: factory-watchdog-test.sh's own PATH stub was bypassed this way
# by bin/escalation-door, paging the live Mayor).

SANDBOX_DIR=""
SANDBOX_CITY=""
SANDBOX_STUB_BIN=""

sandbox_init() {
  local real_gc=0 fixtures name
  case "${1:-}" in
    --real-gc) real_gc=1 ;;
    "") ;;
    *) echo "sandbox_init: unknown argument: $1" >&2; return 2 ;;
  esac

  SANDBOX_DIR=$(mktemp -d "${TMPDIR:-/tmp}/af-sandbox.XXXXXX")
  SANDBOX_CITY="$SANDBOX_DIR/city"
  SANDBOX_STUB_BIN="$SANDBOX_DIR/stubbin"
  mkdir -p "$SANDBOX_CITY" "$SANDBOX_STUB_BIN" "$SANDBOX_DIR/home" "$SANDBOX_DIR/tmux"

  fixtures="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../fixtures" && pwd -P)"
  if [ "$real_gc" -eq 1 ]; then
    for name in codex claude; do
      cp "$fixtures/fake-$name.py" "$SANDBOX_STUB_BIN/$name"
      chmod +x "$SANDBOX_STUB_BIN/$name"
    done
  else
    for name in gc bd gh codex claude; do
      cp "$fixtures/fake-$name.py" "$SANDBOX_STUB_BIN/$name"
      chmod +x "$SANDBOX_STUB_BIN/$name"
    done
  fi

  export HOME="$SANDBOX_DIR/home"
  export TMUX_TMPDIR="$SANDBOX_DIR/tmux"
  export GC_CITY="$SANDBOX_CITY"
  export GC_CITY_PATH="$SANDBOX_CITY"
  export GC_BEADS_SCOPE_ROOT="$SANDBOX_CITY"
  export PATH="$SANDBOX_STUB_BIN:$PATH"

  if [ "$real_gc" -eq 1 ]; then
    unset GC_BIN BD_BIN
  else
    export GC_BIN="$SANDBOX_STUB_BIN/gc"
    export BD_BIN="$SANDBOX_STUB_BIN/bd"
  fi
  export GH_BIN="$SANDBOX_STUB_BIN/gh"

  unset GC_DOLT_HOST GC_DOLT_PORT GC_DOLT_DATABASE GC_DOLT_PROJECT_ID GC_DOLT_USER
  unset GC_SESSION_ID GC_SESSION_NAME GC_ALIAS GC_AGENT
  unset GC_BEAD_ID GC_ROOT_BEAD_ID GC_CONTINUATION_GROUP
  unset GC_CITY_RUNTIME_DIR GC_DIR
  unset GC_TRIGGER_BEAD_ID GC_TRIGGER_WORK_BEAD_ID GC_TRIGGER_BEAD_STORE_REF GC_TRIGGER_WORK_STORE_REF

  trap 'sandbox_cleanup' EXIT
}

sandbox_cleanup() {
  local status=$? sock
  trap - EXIT
  if [ -z "$SANDBOX_DIR" ]; then
    exit "$status"
  fi
  for sock in "$SANDBOX_DIR"/tmux/tmux-*/*; do
    [ -S "$sock" ] || continue
    tmux -S "$sock" kill-server >/dev/null 2>&1 || true
  done
  # Wait for anything matched to actually die before rm -rf: a signalled-
  # but-still-exiting process can hold the data dir open long enough to
  # leave files behind (silent, but a slow leak across CI runs).
  pkill -f -- "$SANDBOX_DIR" >/dev/null 2>&1 || true
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    pgrep -f -- "$SANDBOX_DIR" >/dev/null 2>&1 || break
    sleep 0.3
  done
  pkill -9 -f -- "$SANDBOX_DIR" >/dev/null 2>&1 || true
  if [ "${KEEP_SANDBOX:-0}" = 1 ]; then
    echo "sandbox preserved at $SANDBOX_DIR" >&2
  else
    rm -rf -- "$SANDBOX_DIR"
  fi
  exit "$status"
}
