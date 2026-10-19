#!/usr/bin/env bash
#
# af-wplvhs: Factory CI gives the tests the headless browser the hosts run.
# The Cockpit's criterion tests measure pages in a headless Chromium. On
# GitHub's Ubuntu 24.04 runner unprivileged user namespaces are restricted
# by AppArmor: the runner's own Chromium aborts and Playwright's headless
# shell ends on « No usable sandbox! », an empty page -- « the browser
# measured nothing » (PR #683, #684; diagnostic run 39333740352,
# 2026-10-20). The hosts get past it with the profile of
# bin/factory-host-install; the workflow installs the same pinned browser
# and loads the same profile, without lifting the restriction for the rest
# of the runner (tests/fixture-city-oracle-test.py forbids `sysctl -w`).
# On a GitHub runner this also launches the browser: a page it renders is
# the proof the profile attaches.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
CI="$REPO_ROOT/.github/workflows/ci.yml"
INSTALL="$REPO_ROOT/bin/factory-host-install"
PROFILE="$REPO_ROOT/config/ci-capture-browser.apparmor"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

version=$(sed -n 's/^PLAYWRIGHT_VERSION=\([0-9][0-9.]*\).*/\1/p' "$INSTALL")
[ -n "$version" ] || fail "no PLAYWRIGHT_VERSION in $INSTALL"
grep -qF "playwright@$version install chromium-headless-shell" "$CI" \
  || fail "$CI does not install the headless shell pinned by bin/factory-host-install (playwright@$version)"
echo "ok   the workflow installs the browser the hosts run (playwright@$version)"

[ -f "$PROFILE" ] || fail "$PROFILE is missing"
grep -qF "config/ci-capture-browser.apparmor" "$CI" || fail "$CI does not load $PROFILE"
sed -n "/^browser_profile() {/,/^EOF/p" "$INSTALL" | sed '1,2d;$d' | sed "s|\$FACTORY_HOME|/home/runner|" > "$TMP/host"
grep -v '^#' "$PROFILE" | sed '/./,$!d' > "$TMP/ci"
diff -u "$TMP/host" "$TMP/ci" || fail "$PROFILE is not the hosts' capture browser profile (bin/factory-host-install) for /home/runner"
PARSER=$(PATH="$PATH:/usr/sbin:/sbin" command -v apparmor_parser || true)
if [ -n "$PARSER" ]; then
  "$PARSER" -Q -K -T "$PROFILE" 2>"$TMP/parse.err" || fail "$PROFILE does not parse: $(cat "$TMP/parse.err")"
fi
echo "ok   the workflow loads the hosts' profile for the browser, the restriction stays"

if [ "${GITHUB_ACTIONS:-}" = true ] && [ "${RUNNER_ENVIRONMENT:-}" = github-hosted ]; then
  shell=$(compgen -G "$HOME/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell" | head -1 || true)
  [ -n "$shell" ] || fail "no headless shell in $HOME/.cache/ms-playwright on this runner"
  rc=0
  timeout 60 "$shell" --headless --disable-gpu "--user-data-dir=$TMP/profile" --dump-dom \
    'data:text/html,<p id=x>rendu</p>' >"$TMP/dom" 2>"$TMP/browser.log" || rc=$?
  grep -qF 'rendu' "$TMP/dom" || fail "the headless shell rendered nothing on this runner (exit $rc): $(tail -5 "$TMP/browser.log")"
  echo "ok   on this runner the headless shell renders a page"
fi

echo "PASS ci-capture-browser"
