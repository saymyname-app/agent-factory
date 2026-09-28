#!/usr/bin/env bash
# ci: local-only — drives the live `gc` binary and the city's bead store
#
# af-1isbx: orders/idle-ready-work-wake.toml shipped with a `condition`
# trigger and a `check=` leg but no `exec=` leg. `gc order` requires both
# (a condition order with nothing to run on success is meaningless), so
# `gc order list`/`gc order show` rejected it -- but `gc order list` still
# exits ok:true and just omits the broken order from its output, so nothing
# failed loudly and the order silently never ran. This test loads every
# orders/*.toml through gc's own validation (`gc order show <name>`) so a
# malformed order fails a test instead of silently dropping out of rotation.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

shopt -s nullglob
orders=("$ROOT"/orders/*.toml)
shopt -u nullglob

[ "${#orders[@]}" -gt 0 ] || fail "no orders/*.toml files found under $ROOT/orders"

for f in "${orders[@]}"; do
  name=$(basename -- "$f" .toml)
  err=$(mktemp)
  out=$(gc order show "$name" --city "$ROOT" --json 2>"$err") || {
    cat "$err" >&2
    rm -f "$err"
    fail "gc order show $name failed validation: $out"
  }
  rm -f "$err"
  jq -e '.ok == true and .order != null' >/dev/null 2>&1 <<<"$out" \
    || fail "gc order show $name did not return a valid order: $out"
done

echo "PASS: every orders/*.toml (${#orders[@]}) validates through gc order show"
