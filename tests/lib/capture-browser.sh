# shellcheck shell=bash
# skip_unless_capture_browser_sandbox <browser>: exit 77 (SKIPPED by
# bin/local-only-tests) when the capture browser is refused by the host's
# sandbox -- Chromium's own "No usable sandbox" (AppArmor restricts
# unprivileged user namespaces until the profile factory-capture-browser is
# loaded by `bin/factory-host-install root`, af-yb2cb5). The probe is the one
# `bin/factory-host-install check` runs. A browser that starts, or that fails
# any other way, returns: the test runs and a real regression stays red.
skip_unless_capture_browser_sandbox() {
  local profile err
  profile=$(mktemp -d)
  err=$( { (ulimit -c 0; timeout 30 "$1" --headless --disable-gpu "--user-data-dir=$profile" --dump-dom about:blank) >/dev/null; } 2>&1 ) || true
  rm -rf -- "$profile"
  if grep -q 'No usable sandbox' <<<"$err"; then
    echo "SKIP: the capture browser does not start on this host: No usable sandbox (AppArmor profile factory-capture-browser not loaded; root gesture tracked in af-yb2cb5)"
    exit 77
  fi
}
