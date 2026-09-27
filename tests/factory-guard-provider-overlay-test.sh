#!/usr/bin/env bash
#
# factory-guard must regenerate a missing provider overlay (ADR-0018).
#
# city.toml includes city.provider.toml. That file is generated and
# gitignored: git cannot restore it, and without it `gc` refuses to load the
# city config at all -- verified on a copy of this city on 2026-09-16
# ("loading fragment city.provider.toml: no such file or directory"). The guard
# is the thing that runs every five minutes, so it is the thing that repairs it.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
GUARD="$REPO_ROOT/bin/factory-guard"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

git init -q --bare "$TMP/origin.git"
git init -q "$TMP/city"
cd "$TMP/city"
git config user.email t@t; git config user.name t; git config commit.gpgsign false
git remote add origin "$TMP/origin.git"
mkdir -p .gc bin
printf '.gc/\ncity.provider.toml\n' > .gitignore
printf 'include = ["city.provider.toml"]\n\n[workspace]\nprovider = "claude"\n' > city.toml
# A stand-in for the real tool: the guard's job is to call it, not to be it.
cat > bin/provider-failover <<'STUB'
#!/usr/bin/env bash
[ "$1 $2" = "apply --no-reload" ] || exit 64
printf '[workspace]\nprovider = "claude"\n' > city.provider.toml
echo "overlay written"
STUB
chmod +x bin/provider-failover
git add -A; git commit -qm city; git branch -M main; git push -q origin main; git fetch -q origin

# af-kecgg: this test only exercises the provider-overlay section (1b, which
# never touches gc/gh), but factory-guard's later sections are gated on
# `[ -f city.toml ]` -- true for this fixture too -- not on "is this a real
# city", so they run for real: later sections query the live Beads
# store, and delivery-proof (8) shells out to `gh pr view` against the real
# GitHub repo for every closed product-goal bead it finds there. In a
# sandbox with no outbound network, that `gh` call never returns, which is
# the hang (confirmed via `ps --forest` mid-run: the tree bottoms out at
# `gh pr view <n> --repo .../agent-factory ...` blocked in-kernel). A PATH
# stub alone does not fully fix it: factory-queue-guard/dispatch-guard/
# waiting-guard and factory-delivery-guard resolve their gc/gh calls via
# `${GC_BIN:-gc}`/`${GH_BIN:-gh}`, and every Gas City agent session
# (including the one that runs this test) pre-exports GC_BIN to the real
# `gc` binary, which silently outranks a PATH-only stub and defeats the
# ${VAR:-default} fallback (same fix already used by
# tests/factory-delivery-guard-test.sh). Stub both the bare commands (PATH)
# and the GC_BIN/GH_BIN overrides so every code path -- factory-guard's own
# direct `gc` calls and every sub-guard's `$GC_BIN`/`$GH_BIN` -- resolves
# locally and returns immediately, with no live store or network reachable
# from this test at all.
mkdir -p "$TMP/bin"
cat > "$TMP/bin/gc" <<'STUB'
#!/usr/bin/env bash
case "$1 $2" in
  "bd show")      echo '[]' ;;
  "bd list")      echo '[]' ;;
  "session list") echo '{"sessions":[]}' ;;
  "rig list")     echo '[]' ;;
esac
exit 0
STUB
chmod +x "$TMP/bin/gc"
cat > "$TMP/bin/gh" <<'STUB'
#!/usr/bin/env bash
exit 1
STUB
chmod +x "$TMP/bin/gh"

guard() {
  FACTORY_ROOT="$TMP/city" GC_BIN="$TMP/bin/gc" GH_BIN="$TMP/bin/gh" \
    PATH="$TMP/bin:$PATH" "$GUARD" "$@" 2>&1 || true
}

# --check-only reports and repairs nothing
out=$(guard --check-only)
grep -q "city.provider.toml is missing — the city config cannot load" <<<"$out" \
  || { echo "$out" >&2; fail "missing overlay not reported"; }
[ ! -f city.provider.toml ] || fail "--check-only wrote the overlay"

# the default run regenerates it
out=$(guard)
grep -q "regenerated the missing provider overlay" <<<"$out" || { echo "$out" >&2; fail "overlay not regenerated"; }
[ -f city.provider.toml ] || fail "overlay still missing after the guard ran"

# and is quiet once it exists
out=$(guard --check-only)
grep -q "provider.toml is missing" <<<"$out" && fail "guard still complains with the overlay present"

# a failing generator is reported, not hidden
rm -f city.provider.toml
printf '#!/usr/bin/env bash\nexit 1\n' > bin/provider-failover
out=$(guard)
grep -q "could not be regenerated" <<<"$out" || { echo "$out" >&2; fail "failed regeneration not reported"; }

# a city that does not include the overlay is left alone
printf '[workspace]\nprovider = "claude"\n' > city.toml
out=$(guard --check-only)
grep -q "provider.toml" <<<"$out" && fail "guard demanded an overlay the city does not include"

echo "OK factory-guard regenerates the provider overlay"
