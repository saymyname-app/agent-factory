#!/usr/bin/env bash
#
# bin/factory-host-install installs a fresh host (af-o6l5rl): its `root` and
# `user` commands change a machine and are never run here. What this proves
# without a fresh host: the file parses; `check` prints one verdict a line;
# its pins are the binaries this host runs, when it has them (an upgrade that
# forgets the installer goes red on the Factory's host); its embedded
# AppArmor profile of bwrap is the tracked one, and the capture browser's
# parses.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
INSTALL="$REPO_ROOT/bin/factory-host-install"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

[ -x "$INSTALL" ] || fail "$INSTALL is not executable"
bash -n "$INSTALL" || fail "syntax"

grep -q 'factory-host-install check' <<<"$("$INSTALL" --help)" || fail "--help does not show the usage"
rc=0; "$INSTALL" nonsense >/dev/null 2>&1 || rc=$?
[ "$rc" = 2 ] || fail "an unknown command exits $rc, expected 2"

# --- check: one verdict per line ---------------------------------------------
rc=0; "$INSTALL" check > "$TMP/check.out" 2>&1 || rc=$?
[ "$rc" = 0 ] || [ "$rc" = 1 ] || fail "check exits $rc: $(cat "$TMP/check.out")"
other=$(grep -v -E '^(OK|WARN|MISSING) ' "$TMP/check.out" || true)
[ -z "$other" ] || fail "check prints something else than verdicts: $other"
grep -q -E '^(OK|MISSING) +gc ' "$TMP/check.out" || fail "check has no verdict for gc"

# --- the pins are what this host runs ---------------------------------------
for tool in gc bd dolt; do
  [ -x "/usr/local/bin/$tool" ] || continue
  grep -q -E "^OK +$tool .*pinned binary" "$TMP/check.out" \
    || fail "/usr/local/bin/$tool is not the binary pinned in bin/factory-host-install: after an upgrade, change the pin too"
done

# --- the embedded AppArmor profile is the tracked one -----------------------
sed -n "/^bwrap_profile() {/,/^EOF/p" "$INSTALL" | sed '1,2d;$d' > "$TMP/embedded"
grep -v '^#' "$REPO_ROOT/config/fixture-city-bwrap.apparmor" | sed '/./,$!d' > "$TMP/tracked"
diff -u "$TMP/tracked" "$TMP/embedded" || fail "the embedded bwrap profile differs from config/fixture-city-bwrap.apparmor"

# --- the capture browser's profile parses, and names the browser the tools take
sed -n "/^browser_profile() {/,/^EOF/p" "$INSTALL" | sed '1,2d;$d' | sed "s|\$FACTORY_HOME|/home/benja|" > "$TMP/browser"
grep -q -F '/home/benja/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell ' "$TMP/browser" \
  || fail "the capture browser's profile is not attached to Playwright's headless shell"
PARSER=$(PATH="$PATH:/usr/sbin:/sbin" command -v apparmor_parser || true)
if [ -n "$PARSER" ]; then
  "$PARSER" -Q -K -T "$TMP/browser" 2>"$TMP/parse.err" || fail "the capture browser's profile does not parse: $(cat "$TMP/parse.err")"
fi

echo "PASS factory-host-install"
