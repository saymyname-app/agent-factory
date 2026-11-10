#!/usr/bin/env bash
#
# bin/convoy-parent-sweep (af-cbvryy, class S): a sweep cut by its own budget
# under load is deferred, not an order failure; only sweeps cut in a row
# fail. A sweep that finishes passes gc's own output and exit through. gc is a
# stub named by CONVOY_PARENT_SWEEP_GC_BIN: no case reaches a live store.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
SWEEP="$REPO_ROOT/bin/convoy-parent-sweep"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/city"
CALLS="$TMP/calls"
HUNG_DONE="$TMP/hung-done"
cat > "$TMP/gc" <<STUB
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$CALLS"
if [ -n "\${TEST_GC_SLEEP:-}" ]; then
  sleep "\$TEST_GC_SLEEP"
  printf 'survived\n' > "$HUNG_DONE"
fi
printf '%s\n' "\${TEST_GC_OUT:-{\"closed\":[]\}}"
exit "\${TEST_GC_RC:-0}"
STUB
chmod +x "$TMP/gc"
DEFERRED_FILE="$TMP/city/.gc/runtime/convoy-parent-sweep-deferred-passes"
sweep() {
  FACTORY_ROOT="$TMP/city" CONVOY_PARENT_SWEEP_GC_BIN="$TMP/gc" "$SWEEP" "$@" 2>&1
}
cut_sweep() { TEST_GC_SLEEP=4 CONVOY_PARENT_SWEEP_BUDGET_SECONDS=0.3 sweep; }

# 1. a sweep cut by the budget is deferred; the third cut in a row fails ------
started_ns=$(date +%s%N)
set +e
out=$(cut_sweep); rc=$?
set -e
elapsed_ns=$(( $(date +%s%N) - started_ns ))
[ "$rc" = "0" ] || { echo "$out" >&2; fail "one sweep cut by the budget must be deferred, not failed (was $rc)"; }
grep -q 'budget exceeded after 0.3s — sweep deferred to the next closing (1 of 3 in a row, loadavg ' <<<"$out" \
  || { echo "$out" >&2; fail "a deferred sweep must name its budget and its count"; }
[ "$elapsed_ns" -lt 3000000000 ] || fail "a slow gc must be cut at the budget, not waited for"
set +e
cut_sweep >/dev/null; out=$(cut_sweep); rc=$?
set -e
[ "$rc" = "2" ] || { echo "$out" >&2; fail "a third sweep cut in a row must exit 2 (was $rc)"; }
grep -q 'budget exceeded after 0.3s — 3 sweeps in a row cut short' <<<"$out" \
  || { echo "$out" >&2; fail "a repeated budget expiry must say it is repeated"; }
sleep 4
[ ! -e "$HUNG_DONE" ] || fail "the cut gc survived the sweep's budget"

# 2. a sweep that finishes is gc's own: output and exit, and clears the count -
out=$(TEST_GC_OUT='{"closed":["af-c1"]}' sweep)
[ "$out" = '{"closed":["af-c1"]}' ] || fail "a finished sweep must print gc's output unchanged (was: $out)"
[ "$(tail -n1 "$CALLS")" = "convoy check --json" ] || fail "the sweep must run gc convoy check --json"
[ ! -e "$DEFERRED_FILE" ] || fail "a finished sweep must clear the count of sweeps cut in a row"

# 3. gc failing on its own is still a failure, not a deferral -----------------
cut_sweep >/dev/null
set +e
out=$(TEST_GC_RC=1 sweep); rc=$?
set -e
[ "$rc" = "1" ] || { echo "$out" >&2; fail "a gc error must keep its exit (was $rc)"; }
[ ! -e "$DEFERRED_FILE" ] || fail "a sweep that ran to its end must clear the deferred count"

# 4. a stray argument is refused ----------------------------------------------
set +e
out=$(sweep --all); rc=$?
set -e
[ "$rc" = "2" ] && grep -q 'takes no argument' <<<"$out" || fail "an argument must be refused with exit 2"

# 5. the order runs this sweep, and its deadline covers the gate, the budget
#    and the kill grace -----------------------------------------------------------
ORDER="$REPO_ROOT/orders/convoy-parent-sweep.toml"
grep -qF -- 'exec = "/home/benja/agent-factory/bin/order-pause gate convoy-parent-sweep -- /home/benja/agent-factory/bin/convoy-parent-sweep"' "$ORDER" \
  || fail "orders/convoy-parent-sweep.toml must run bin/convoy-parent-sweep through the pause gate"
order_s=$(sed -n 's/^timeout = "\([0-9]*\)s"$/\1/p' "$ORDER")
budget_s=$(sed -n 's/^BUDGET_SECONDS="${CONVOY_PARENT_SWEEP_BUDGET_SECONDS:-\([0-9]*\)}"$/\1/p' "$SWEEP")
gate_s=$(sed -n 's/^READ_TIMEOUT_SECONDS = \([0-9]*\)$/\1/p' "$REPO_ROOT/bin/order-pause")
[ -n "$order_s" ] && [ -n "$budget_s" ] && [ -n "$gate_s" ] || fail "could not read the order, sweep or gate bounds"
[ $(( gate_s + budget_s + 5 )) -lt "$order_s" ] \
  || fail "gate ${gate_s}s + budget ${budget_s}s + 5s grace must stay under the order's ${order_s}s"

printf 'PASS: a convoy sweep cut by its budget under load is deferred, only three in a row fail, and a finished sweep is gc'"'"'s own\n'
