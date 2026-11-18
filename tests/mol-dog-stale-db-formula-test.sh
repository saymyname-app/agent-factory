#!/usr/bin/env bash
# af-lmjqkf: a vapor wisp's dog executes its step as `gc bd formula show`
# prints it, and `formula show` renders no variable. Upstream mol-dog-stale-db
# left {{max_orphans_for_sql}} and {{warn_threshold}} in its script; on
# af-0p7ylg Bash failed on the literal warn token. This test takes the step
# script out of the Factory's shadow formula exactly as written and runs it,
# with stubbed gc and bd, on the zero-orphan path and on the safe-apply path.
# It also refuses any vapor formula of formulas/ that still holds a template
# token, since none of them is ever rendered.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
FORMULA="$ROOT/formulas/mol-dog-stale-db.formula.toml"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

# Category check: no vapor formula of this repository holds a template token.
python3 - "$ROOT/formulas" <<'PY' || fail "a vapor formula holds an unrendered template token"
import pathlib, re, sys, tomllib
bad = []
for path in sorted(pathlib.Path(sys.argv[1]).glob("*.toml")):
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    if data.get("phase") != "vapor":
        continue
    texts = [data.get("description", "")] + [s.get("description", "") for s in data.get("steps", [])]
    for token in sorted({t for text in texts for t in re.findall(r"\{\{[^}]*\}\}", text)}):
        bad.append(f"{path.name}: {token}")
for line in bad:
    print(line, file=sys.stderr)
raise SystemExit(1 if bad else 0)
PY

python3 - "$FORMULA" > "$TMP/cleanup.sh" <<'PY'
import re, sys, tomllib
data = tomllib.loads(open(sys.argv[1], encoding="utf-8").read())
assert data["phase"] == "vapor", data["phase"]
step = next(s for s in data["steps"] if s["id"] == "cleanup")
print(re.search(r"^```bash\n(.*?)^```$", step["description"], re.DOTALL | re.MULTILINE).group(1))
PY
grep -q '^MAX_ORPHANS_FOR_SQL=20$' "$TMP/cleanup.sh" || fail "step script does not set MAX_ORPHANS_FOR_SQL=20"
grep -q '^WARN_THRESHOLD=5$' "$TMP/cleanup.sh" || fail "step script does not set WARN_THRESHOLD=5"

# Stubs: every call is logged; `gc dolt-cleanup` answers the case's scan or
# apply report.
mkdir -p "$TMP/bin"
cat > "$TMP/bin/gc" <<'SH'
#!/usr/bin/env bash
printf 'gc %s\n' "$*" >> "$CASE/calls.log"
if [ "$1" = dolt-cleanup ]; then
  case " $* " in *" --force "*) cat "$CASE/apply.json" ;; *) cat "$CASE/scan.json" ;; esac
fi
SH
cat > "$TMP/bin/bd" <<'SH'
#!/usr/bin/env bash
printf 'bd %s\n' "$1 $2" >> "$CASE/calls.log"
SH
chmod +x "$TMP/bin/gc" "$TMP/bin/bd"

run_case() {
  CASE="$TMP/$1"
  mkdir -p "$CASE"
  printf '%s' "$2" > "$CASE/scan.json"
  printf '%s' "${3:-}" > "$CASE/apply.json"
  CASE="$CASE" PATH="$TMP/bin:$PATH" TMPDIR="$CASE" GC_BEAD_ID=wisp-stale-db \
    GC_MAINTENANCE_DONE_TARGET=deacon \
    bash "$TMP/cleanup.sh" > "$CASE/out" 2> "$CASE/err" \
    || { cat "$CASE/err" >&2; fail "$1: step script exited non-zero"; }
  if grep -q 'integer expression' "$CASE/err"; then
    cat "$CASE/err" >&2; fail "$1: Bash reported an integer-expression error"
  fi
  grep -q '{{' "$CASE/calls.log" && fail "$1: a template token reached a command"
  grep -qx 'bd close wisp-stale-db' "$CASE/calls.log" || fail "$1: work bead not closed"
  grep -qx 'gc runtime drain-ack' "$CASE/calls.log" || fail "$1: no drain-ack"
}

# Zero orphans: no apply, no warning, bead closed.
run_case zero-orphans '{"schema":"gc.dolt.cleanup.v1","dropped":{"count":0},"reaped":{"targets":[]},"summary":{"errors_total":0}}'
grep -q -- '--force' "$TMP/zero-orphans/calls.log" && fail "zero-orphans: apply ran"
grep -q 'MAINTENANCE_WARN' "$TMP/zero-orphans/calls.log" && fail "zero-orphans: warned below threshold"
grep -q 'MAINTENANCE_DONE: stale-db - orphans: 0, applied: 0, escalated: 0' "$TMP/zero-orphans/calls.log" \
  || fail "zero-orphans: done notice missing"

# Safe apply: 3 stale databases (<= 20) and 4 orphan processes (7 >= 5).
SCAN='{"schema":"gc.dolt.cleanup.v1","dropped":{"count":3},"reaped":{"targets":[1,2,3,4]},"purge":{"bytes_reclaimed":100},"summary":{"bytes_freed_disk":100,"bytes_freed_rss":50,"errors_total":0}}'
APPLY='{"schema":"gc.dolt.cleanup.v1","dropped":{"count":3,"failed":[]},"reaped":{"count":4,"targets":[1,2,3,4]},"purge":{"bytes_reclaimed":100},"summary":{"bytes_freed_disk":100,"bytes_freed_rss":50,"errors_total":0},"errors":[]}'
run_case safe-apply "$SCAN" "$APPLY"
grep -qx 'gc dolt-cleanup --json --probe --force --max-orphan-dbs 20' "$TMP/safe-apply/calls.log" \
  || fail "safe-apply: apply not called with --max-orphan-dbs 20"
grep -q 'MAINTENANCE_WARN: 7 Dolt orphan(s) seen this scan (warn_threshold=5)' "$TMP/safe-apply/calls.log" \
  || fail "safe-apply: warning notice missing"
grep -q 'MAINTENANCE_DONE: stale-db - orphans: 7, applied: 1, escalated: 0' "$TMP/safe-apply/calls.log" \
  || fail "safe-apply: done notice missing"

echo "PASS: mol-dog-stale-db runs its zero-orphan and safe-apply paths with numeric thresholds"
