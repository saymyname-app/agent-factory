#!/usr/bin/env bash
#
# af-lw581v: bin/factory-metrics appends one JSON line per day to
# var/factory-metrics.jsonl, computed only from records that already exist:
# ticket merge records (gc bd), .gc/events.jsonl order events and Claude
# transcripts. A field whose source is missing is null and listed in
# `unavailable` -- never invented. gc is a stub on PATH.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
METRICS="$REPO_ROOT/bin/factory-metrics"
. "$REPO_ROOT/tests/lib/sandbox.sh"
sandbox_init
TMP="$SANDBOX_DIR"
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }
export TZ=UTC

mkdir -p "$TMP/city/.gc" "$TMP/bin" "$TMP/projects/proj"

# Tickets: two merged on the day (one record encoded as a string, as
# bin/convoy-state writes it), one merged the day before, one conflict.
cat > "$TMP/beads.json" <<'JSON'
[
 {"id":"af-t1","metadata":{"gc.flow.merge":"{\"at\":\"2026-10-14T10:00:00Z\",\"outcome\":\"merged\"}","gc.flow.counter.resumes":2}},
 {"id":"af-t2","metadata":{"gc.flow.merge":{"at":"2026-10-14T20:00:00Z","outcome":"merged"},"gc.flow.counter.resumes":0}},
 {"id":"af-t3","metadata":{"gc.flow.merge":{"at":"2026-10-13T23:00:00Z","outcome":"merged"},"gc.flow.counter.resumes":5}},
 {"id":"af-t4","metadata":{"gc.flow.merge":{"at":"2026-10-14T11:00:00Z","outcome":"conflict"}}}
]
JSON
cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
[ "\$1 \$2" = "bd list" ] && cat "$TMP/beads.json"
STUB
chmod +x "$TMP/bin/gc"

ev() { printf '{"seq":1,"type":"%s","ts":"%s","actor":"controller","subject":"%s"}\n' "$1" "$2" "$3"; }
{
  ev order.completed 2026-10-14T01:00:00+00:00 order-a
  ev order.completed 2026-10-14T02:00:00+00:00 order-a
  ev order.completed 2026-10-14T03:00:00+00:00 order-a
  ev order.failed    2026-10-14T04:00:00+00:00 order-a
  ev order.fired     2026-10-14T04:00:00+00:00 order-a
  ev order.completed 2026-10-14T05:00:00+00:00 order-b
  ev order.completed 2026-10-14T23:59:59+00:00 order-b
  ev order.failed    2026-10-15T00:00:01+00:00 order-b
  ev session.woke    2026-10-14T05:00:00+00:00 mayor
} > "$TMP/city/.gc/events.jsonl"

as() { printf '{"type":"assistant","timestamp":"%s","message":{"id":"%s","usage":{"input_tokens":%s,"output_tokens":%s,"cache_read_input_tokens":%s,"cache_creation_input_tokens":0}}}\n' "$@"; }
{ # s1: one turn over 150k context, its record repeated (one per content block)
  as 2026-10-14T09:00:00Z m1 10 5 160000
  as 2026-10-14T09:00:00Z m1 10 5 160000
  as 2026-10-14T09:01:00Z m2 1 1 0
} > "$TMP/projects/proj/s1.jsonl"
{ # s2: under 150k on the day; its huge turn of the day before does not count
  as 2026-10-13T09:00:00Z m3 900000 0 0
  as 2026-10-14T12:00:00Z m4 100 0 0
} > "$TMP/projects/proj/s2.jsonl"

export GC_BIN="$TMP/bin/gc"
export FACTORY_METRICS_TRANSCRIPTS="$TMP/projects"
run() { FACTORY_ROOT="$TMP/city" "$METRICS" "$@"; }
field() { jq -c ".$1" <<<"$2"; }

# 1. every field from its source, --print appends nothing ---------------------
out=$(run --day 2026-10-14 --print)
[ "$(field day "$out")" = '"2026-10-14"' ] || fail "day: $out"
[ "$(field tickets_merged "$out")" = 2 ] || fail "tickets_merged counts merged-on-the-day only: $out"
[ "$(field merged_tickets "$out")" = '["af-t1","af-t2"]' ] || fail "merged_tickets: $out"
[ "$(field attempts_per_ticket "$out")" = '{"af-t1":3,"af-t2":1}' ] || fail "attempts = 1 + resumes: $out"
[ "$(field attempts_mean "$out")" = 2 ] || fail "attempts_mean: $out"
[ "$(field tokens_total "$out")" = 160117 ] || fail "tokens_total dedups message ids, day only: $out"
[ "$(field tokens_per_merged_ticket "$out")" = 80058.5 ] || fail "tokens_per_merged_ticket: $out"
[ "$(field order_failure_rate "$out")" = 0.1667 ] || fail "order_failure_rate = failed/(completed+failed): $out"
[ "$(field 'order_runs["order-a"]' "$out")" = '{"completed":3,"failed":1,"failure_rate":0.25}' ] || fail "per-order: $out"
[ "$(field 'order_runs["order-b"]' "$out")" = '{"completed":2,"failed":0,"failure_rate":0}' ] || fail "per-order b: $out"
[ "$(field sessions_over_150k "$out")" = 1 ] || fail "sessions_over_150k: $out"
[ "$(field evaluation_duration_seconds "$out")" = null ] || fail "evaluation records carry no start: $out"
[ "$(field unavailable "$out")" = '["evaluation_duration_seconds"]' ] || fail "unavailable: $out"
[ "$(jq -r '.unavailable_reasons.evaluation_duration_seconds' <<<"$out")" != null ] || fail "reason missing: $out"
[ ! -e "$TMP/city/var/factory-metrics.jsonl" ] || fail "--print must not append"

# 2. without --print: exactly one line appended per run ------------------------
run --day 2026-10-14 >/dev/null
run --day 2026-10-14 >/dev/null
[ "$(wc -l < "$TMP/city/var/factory-metrics.jsonl")" = 2 ] || fail "one line per run"
jq -e '.tickets_merged == 2' < <(head -1 "$TMP/city/var/factory-metrics.jsonl") >/dev/null || fail "appended line"

# 3. missing sources -> null + unavailable, never zero -------------------------
printf '#!/usr/bin/env bash\nexit 1\n' > "$TMP/bin/gc"
rm "$TMP/city/.gc/events.jsonl"
export FACTORY_METRICS_TRANSCRIPTS="$TMP/nowhere"
out=$(run --day 2026-10-14 --print)
for f in tickets_merged attempts_mean tokens_total tokens_per_merged_ticket order_failure_rate sessions_over_150k evaluation_duration_seconds; do
  [ "$(field "$f" "$out")" = null ] || fail "$f must be null without its source: $out"
  jq -e --arg f "$f" '(.unavailable | index($f)) != null and .unavailable_reasons[$f] != null' <<<"$out" >/dev/null \
    || fail "$f must be listed unavailable with a reason: $out"
done

# 4. no merged ticket: per-ticket figures are null, the count is a real 0 -----
printf '#!/usr/bin/env bash\necho "[]"\n' > "$TMP/bin/gc"
out=$(run --day 2026-10-14 --print)
[ "$(field tickets_merged "$out")" = 0 ] || fail "zero merged is a value, not unavailable: $out"
[ "$(field tokens_per_merged_ticket "$out")" = null ] || fail "no per-ticket tokens without a merged ticket: $out"

# 5. bad --day is refused -------------------------------------------------------
if run --day yesterday --print >/dev/null 2>&1; then fail "--day must be YYYY-MM-DD"; fi

echo "PASS: factory-metrics"
