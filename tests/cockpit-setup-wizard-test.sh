#!/usr/bin/env bash
#
# T25 (af-tzk0s4): bin/cockpit-setup-wizard guides Benjamin's one-time
# iPhone access setup (Pushover secrets, Healthchecks.io check parameters,
# Tailscale Serve, Focus-mode push check). This test drives it
# non-interactively (flags + a scripted JSON answers file for `run`)
# against a fake `tailscale` binary and asserts:
#   * no secret value ever appears in captured stdout/stderr;
#   * a secret is written only to the exact out-of-repo path named for it,
#     never anywhere else (in particular never inside this git repo);
#   * a Serve configuration that uses Funnel, or that targets the gc
#     supervisor's own port, is refused with a French error and a non-zero
#     exit code, before any secret or config is ever written.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
WIZARD="$ROOT/bin/cockpit-setup-wizard"
TEST_TMP=$(mktemp -d)
trap 'rm -rf -- "$TEST_TMP"' EXIT
TESTS_RUN=0

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }
pass() { TESTS_RUN=$((TESTS_RUN + 1)); }

SECRET_TOKEN="sekrit-token-9F3Q"
SECRET_USER_KEY="sekrit-userkey-7A1Z"
SECRET_E2E_KEY="sekrit-e2ekey-4B8P"
SECRET_HC_URL="https://hc-ping.com/super-secret-check-id"

FAKE_TAILSCALE="$TEST_TMP/fake-tailscale"
cat >"$FAKE_TAILSCALE" <<'EOF'
#!/usr/bin/env python3
import sys
args = sys.argv[1:]
if args[:1] == ["serve"]:
    print("ok")
    sys.exit(0)
if args[:2] == ["funnel", "status"]:
    print("https://example.ts.net/ (tailnet only)")
    sys.exit(0)
sys.stderr.write("fake tailscale: no canned response for %r\n" % args)
sys.exit(1)
EOF
chmod +x "$FAKE_TAILSCALE"

# ---------------------------------------------------------------------------
# 1. pushover-secrets: writes exactly the intended file, never echoes the
#    secret to stdout/stderr.
# ---------------------------------------------------------------------------
SECRETS_PATH="$TEST_TMP/outside-repo/pushover-secrets.json"
OUT="$TEST_TMP/out.txt"; ERR="$TEST_TMP/err.txt"
printf '{"token":"%s","user_key":"%s","e2e_key":"%s"}' \
  "$SECRET_TOKEN" "$SECRET_USER_KEY" "$SECRET_E2E_KEY" \
  | "$WIZARD" pushover-secrets --path "$SECRETS_PATH" >"$OUT" 2>"$ERR"
RC=$?
[ "$RC" -eq 0 ] || fail "pushover-secrets exited $RC"
pass

[ -f "$SECRETS_PATH" ] || fail "secrets file was not written"
pass

grep -q "$SECRET_TOKEN" "$SECRETS_PATH" || fail "secrets file missing the token"
pass

if grep -q "$SECRET_TOKEN" "$OUT" || grep -q "$SECRET_TOKEN" "$ERR"; then
  fail "the Pushover token leaked into wizard stdout/stderr"
fi
if grep -q "$SECRET_USER_KEY" "$OUT" || grep -q "$SECRET_USER_KEY" "$ERR"; then
  fail "the Pushover user key leaked into wizard stdout/stderr"
fi
if grep -q "$SECRET_E2E_KEY" "$OUT" || grep -q "$SECRET_E2E_KEY" "$ERR"; then
  fail "the Pushover E2E key leaked into wizard stdout/stderr"
fi
pass

# ---------------------------------------------------------------------------
# 2. pushover-secrets refuses a path inside the repository — nothing written.
# ---------------------------------------------------------------------------
INSIDE_REPO_PATH="$ROOT/tests/fixtures/should-never-exist-secrets.json"
rm -f "$INSIDE_REPO_PATH"
set +e
printf '{"token":"t","user_key":"u","e2e_key":"e"}' \
  | "$WIZARD" pushover-secrets --path "$INSIDE_REPO_PATH" >"$OUT" 2>"$ERR"
RC=$?
set -e
[ "$RC" -ne 0 ] || fail "pushover-secrets accepted a path inside the repo"
pass
[ ! -f "$INSIDE_REPO_PATH" ] || { rm -f "$INSIDE_REPO_PATH"; fail "a secrets file was written inside the repo"; }
pass
grep -qi "dépôt" "$ERR" || fail "expected a French refusal mentioning the repository"
pass

# ---------------------------------------------------------------------------
# 3. heartbeat-secret: same contract, for the Healthchecks.io ping URL.
# ---------------------------------------------------------------------------
HC_PATH="$TEST_TMP/outside-repo/heartbeat-url.txt"
printf '%s\n' "$SECRET_HC_URL" | "$WIZARD" heartbeat-secret --path "$HC_PATH" >"$OUT" 2>"$ERR"
RC=$?
[ "$RC" -eq 0 ] || fail "heartbeat-secret exited $RC"
pass
grep -q "$SECRET_HC_URL" "$HC_PATH" || fail "heartbeat URL file missing its content"
pass
if grep -q "$SECRET_HC_URL" "$OUT" || grep -q "$SECRET_HC_URL" "$ERR"; then
  fail "the heartbeat ping URL leaked into wizard stdout/stderr"
fi
pass

# ---------------------------------------------------------------------------
# 4. healthchecks-check: refuses a non-conforming "Usine muette" check;
#    accepts the exact spec parameters and notes the live-capability checks
#    as non-blocking defects rather than failing.
# ---------------------------------------------------------------------------
set +e
"$WIZARD" healthchecks-check --name "Usine muette" --period-minutes 10 \
  --grace-minutes 10 --up-notifications off >"$OUT" 2>"$ERR"
RC=$?
set -e
[ "$RC" -ne 0 ] || fail "healthchecks-check accepted a wrong period"
pass

"$WIZARD" healthchecks-check --name "Usine muette" --period-minutes 5 \
  --grace-minutes 10 --up-notifications off --repeat-2h unknown --priority1 unknown \
  >"$OUT" 2>"$ERR"
RC=$?
[ "$RC" -eq 0 ] || fail "healthchecks-check refused the conforming parameters"
pass
grep -q "défaut noté" "$OUT" || fail "expected a non-blocking defect note for the unverified 2h/priority-1 capability"
pass

# ---------------------------------------------------------------------------
# 5. serve: refuses Funnel outright, and refuses targeting the gc port —
#    both before ever invoking the fake tailscale for real serve work.
# ---------------------------------------------------------------------------
set +e
"$WIZARD" serve --tailscale-bin "$FAKE_TAILSCALE" --target-port 8173 --gc-port 8372 --funnel \
  >"$OUT" 2>"$ERR"
RC=$?
set -e
[ "$RC" -ne 0 ] || fail "serve accepted a Funnel configuration"
pass
grep -qi "funnel" "$ERR" || fail "expected a French refusal mentioning Funnel"
pass

set +e
"$WIZARD" serve --tailscale-bin "$FAKE_TAILSCALE" --target-port 8372 --gc-port 8372 \
  >"$OUT" 2>"$ERR"
RC=$?
set -e
[ "$RC" -ne 0 ] || fail "serve accepted pointing at the gc API port"
pass
grep -qi "gc" "$ERR" || fail "expected a French refusal mentioning the gc API"
pass

# A well-formed Serve request (own port, no Funnel) succeeds against the fake.
"$WIZARD" serve --tailscale-bin "$FAKE_TAILSCALE" --target-port 8173 --gc-port 8372 \
  >"$OUT" 2>"$ERR"
RC=$?
[ "$RC" -eq 0 ] || fail "serve refused a valid, Funnel-free configuration"
pass

# ---------------------------------------------------------------------------
# 6. run: drives every step from one JSON answers file — the full
#    non-interactive path — and still leaks nothing.
# ---------------------------------------------------------------------------
RUN_SECRETS_PATH="$TEST_TMP/outside-repo/run-secrets.json"
RUN_HC_PATH="$TEST_TMP/outside-repo/run-heartbeat.txt"
ANSWERS="$TEST_TMP/answers.json"
cat >"$ANSWERS" <<EOF
{
  "pushover_secrets": {"path": "$RUN_SECRETS_PATH", "secret": {"token": "$SECRET_TOKEN", "user_key": "$SECRET_USER_KEY", "e2e_key": "$SECRET_E2E_KEY"}},
  "heartbeat_secret": {"path": "$RUN_HC_PATH", "url": "$SECRET_HC_URL"},
  "healthchecks_check": {"name": "Usine muette", "period_minutes": 5, "grace_minutes": 10, "up_notifications": "off", "repeat_2h": "yes", "priority1": "yes"},
  "serve": {"tailscale_bin": "$FAKE_TAILSCALE", "target_port": 8173, "gc_port": 8372, "funnel": false},
  "focus_check": {"confirmed": "yes"}
}
EOF

"$WIZARD" run --answers "$ANSWERS" >"$OUT" 2>"$ERR"
RC=$?
[ "$RC" -eq 0 ] || fail "run exited $RC with a fully conforming answers file"
pass

[ -f "$RUN_SECRETS_PATH" ] || fail "run did not write the pushover secrets file"
[ -f "$RUN_HC_PATH" ] || fail "run did not write the heartbeat URL file"
pass

if grep -qE "$SECRET_TOKEN|$SECRET_USER_KEY|$SECRET_E2E_KEY|$SECRET_HC_URL" "$OUT" "$ERR"; then
  fail "run leaked a secret into stdout/stderr"
fi
pass

grep -q "défaut noté" "$OUT" && fail "run should not have noted a defect: every answer confirmed"
pass

# run stops (refuses) on a Funnel attempt embedded in the answers file, and
# writes nothing for any step after the refusal.
BAD_ANSWERS="$TEST_TMP/bad-answers.json"
BAD_SECRETS_PATH="$TEST_TMP/outside-repo/should-not-exist.json"
cat >"$BAD_ANSWERS" <<EOF
{
  "serve": {"tailscale_bin": "$FAKE_TAILSCALE", "target_port": 8173, "gc_port": 8372, "funnel": true},
  "focus_check": {"confirmed": "no"}
}
EOF
set +e
"$WIZARD" run --answers "$BAD_ANSWERS" >"$OUT" 2>"$ERR"
RC=$?
set -e
[ "$RC" -ne 0 ] || fail "run accepted an answers file with a Funnel attempt"
pass
grep -qi "funnel" "$ERR" || fail "expected a French refusal mentioning Funnel from run"
pass

echo "PASS: $TESTS_RUN assertions in cockpit-setup-wizard-test.sh"
