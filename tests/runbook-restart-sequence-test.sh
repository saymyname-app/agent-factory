#!/usr/bin/env bash
#
# docs/RUNBOOK_STOP_AND_RESTART.md §3 (the manual restart after a planned stop
# window) lists every command bin/factory-boot runs, in the same order
# (af-8j6lsz).
#
# §3 is a hand-written copy of factory-boot, and it drifted twice: it left out
# the Cockpit (2026-10-09: stopped from the planned window of 17:36 Paris until
# Benjamin noticed), and it still said `gc supervisor start` after factory-boot
# had moved to the systemd unit (2026-10-08: 84 failed unit starts in 7
# minutes), so every planned window recreated the state §6 point 1 describes.
#
# Everything is fake: gc, systemctl, and every ./bin script factory-boot names.
# factory-boot runs in a sandbox on the case a planned window leaves behind
# (supervisor down, unit installed, Cockpit down, controller down), and the
# commands it runs are read back from the fakes.
#   1. each command factory-boot ran is a line of the §3 block, in that order
#   2. the §3 block never starts the supervisor with `gc supervisor start`
#   3. the §3 block resumes the city (`gc resume`, which factory-boot never
#      does) after the supervisor is started and before `gc start`

set -Eeuo pipefail
REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
SELF=$(basename -- "${BASH_SOURCE[0]}")
BOOT="$REPO_ROOT/bin/factory-boot"
RUNBOOK="$REPO_ROOT/docs/RUNBOOK_STOP_AND_RESTART.md"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

ROOT="$TMP/city"
STUB="$TMP/stub"
CALLS="$TMP/calls.log"
SUPERVISOR="$TMP/supervisor-state"   # "up" or "down"
CONTROLLER="$TMP/controller-state"   # "true" or "false"
mkdir -p "$ROOT/bin" "$ROOT/.gc/runtime" "$STUB"
: > "$CALLS"
echo down > "$SUPERVISOR"
echo false > "$CONTROLLER"

# One fake per ./bin script factory-boot names, so a step added to it later
# is recorded here without an edit. `cockpit status` is a question, not a step.
while read -r name; do
  cat > "$ROOT/bin/$name" <<STUBEOF
#!/usr/bin/env bash
[ "$name \$*" = "cockpit status" ] && exit 1
line="./bin/$name \$*"
printf '%s\n' "\${line% }" >> "$CALLS"
STUBEOF
  chmod +x "$ROOT/bin/$name"
done < <(grep -oE '\./bin/[a-z0-9-]+' "$BOOT" | sed 's|^\./bin/||' | sort -u)

cat > "$STUB/gc" <<STUBEOF
#!/usr/bin/env bash
case "\$*" in
  "supervisor status")
    if [ "\$(cat "$SUPERVISOR")" = up ]; then echo "Supervisor is running (PID 4242)"; exit 0; fi
    echo "Supervisor is not running"; exit 1 ;;
  "status --json")
    echo "{\"running\": \$(cat "$CONTROLLER"), \"suspended\": false}" ;;
  start)
    printf 'gc start\n' >> "$CALLS"; echo true > "$CONTROLLER" ;;
  *) printf 'gc %s\n' "\$*" >> "$CALLS" ;;
esac
STUBEOF
cat > "$STUB/systemctl" <<STUBEOF
#!/usr/bin/env bash
case "\$*" in
  "--user cat gascity-supervisor.service") exit 0 ;;
  "--user start gascity-supervisor.service")
    printf 'systemctl %s\n' "\$*" >> "$CALLS"; echo up > "$SUPERVISOR" ;;
  *) printf 'systemctl %s\n' "\$*" >> "$CALLS" ;;
esac
STUBEOF
chmod +x "$STUB"/*

out=$(env FACTORY_ROOT="$ROOT" GC_BIN="$STUB/gc" SYSTEMCTL_BIN="$STUB/systemctl" \
  FACTORY_BOOT_LOG="$TMP/factory-boot.log" FACTORY_BOOT_LOCK="$TMP/factory-boot.lock" \
  FACTORY_BOOT_WAIT_SECONDS=1 FACTORY_BOOT_SUPERVISOR_WAIT_SECONDS=1 "$BOOT") \
  || fail "factory-boot failed in the sandbox: $out"
[ -s "$CALLS" ] || fail "factory-boot ran no command in the sandbox"

# The commands of the first bash block of §3, comments and padding removed.
mapfile -t block < <(awk '
  /^## 3\. /            { section = 1; next }
  section && /^## /     { exit }
  section && /^```bash/ { inside = 1; next }
  inside && /^```/      { exit }
  inside' "$RUNBOOK" | sed -E 's/[[:space:]]+#.*$//; s/[[:space:]]+/ /g; s/^ //; s/ $//' | grep -v '^$')
[ "${#block[@]}" -gt 0 ] || fail "no bash block found under '## 3.' in $RUNBOOK"

position() {  # position <command>: its index in the §3 block, or nothing
  local i
  for i in "${!block[@]}"; do
    [ "${block[$i]}" = "$1" ] && { echo "$i"; return 0; }
  done
  return 1
}

last=-1
while read -r call; do
  at=$(position "$call") || fail "1: factory-boot runs '$call', which is not a line of the §3 block of $RUNBOOK. Add it there, at factory-boot's place for it. The block is:
$(printf '%s\n' "${block[@]}")"
  [ "$at" -gt "$last" ] || fail "1: '$call' is not at factory-boot's place in the §3 block of $RUNBOOK. factory-boot's order is:
$(cat "$CALLS")"
  last=$at
done < "$CALLS"

if position "gc supervisor start" >/dev/null; then
  fail "2: the §3 block starts the supervisor with 'gc supervisor start', which forks one outside its systemd unit (§6 point 1)"
fi

resume=$(position "gc resume") || fail "3: the §3 block does not resume the city: factory-boot never does, a planned window suspends it (§2.1)"
supervisor=$(position "systemctl --user start gascity-supervisor.service")
controller=$(position "gc start")
[ "$resume" -gt "$supervisor" ] && [ "$resume" -lt "$controller" ] \
  || fail "3: 'gc resume' belongs after the supervisor start and before 'gc start' in the §3 block"

echo "PASS: $SELF"
