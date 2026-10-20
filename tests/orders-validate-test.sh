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
#
# af-9gxs9a: an order listed in city.toml `[orders] skip` (a deliberate pause,
# e.g. convoy-advance since af-tys6ff) is hidden by gc, so `gc order show`
# answers "not found" for it. Such an order is reported as skipped, not
# validated -- the pause is an operator decision, not a broken file.
#
# ORDERS_VALIDATE_CITY points the check at another city (its own test,
# tests/orders-validate-skip-test.sh, uses a fresh one); default: this repo.

set -Eeuo pipefail

ROOT=${ORDERS_VALIDATE_CITY:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)}

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

shopt -s nullglob
orders=("$ROOT"/orders/*.toml)
shopt -u nullglob

[ "${#orders[@]}" -gt 0 ] || fail "no orders/*.toml files found under $ROOT/orders"

skipped=$(python3 -c '
import sys, tomllib
with open(sys.argv[1], "rb") as f:
    print("\n".join(tomllib.load(f).get("orders", {}).get("skip", [])))
' "$ROOT/city.toml") || fail "could not read [orders] skip from $ROOT/city.toml"

validated=0
skipped_here=()
for f in "${orders[@]}"; do
  name=$(basename -- "$f" .toml)
  if grep -qxF -- "$name" <<<"$skipped"; then
    skipped_here+=("$name")
    continue
  fi
  err=$(mktemp)
  out=$(gc order show "$name" --city "$ROOT" --json 2>"$err") || {
    cat "$err" >&2
    rm -f "$err"
    fail "gc order show $name failed validation: $out"
  }
  rm -f "$err"
  jq -e '.ok == true and .order != null' >/dev/null 2>&1 <<<"$out" \
    || fail "gc order show $name did not return a valid order: $out"
  validated=$((validated + 1))
done

if [ "${#skipped_here[@]}" -gt 0 ]; then
  echo "SKIPPED (city.toml [orders] skip): ${skipped_here[*]}"
fi
echo "PASS: every orders/*.toml not skipped in city.toml ($validated) validates through gc order show"
