#!/usr/bin/env bash
#
# af-8hdaf1: PR #867 merged at 13:35Z on 2026-11-12 and its ticket af-batj8g
# (open: sent back to the pool for a conflict earlier) stayed open, with no
# merge trace, until 17:48Z. Under a load of 75 to 95 the whole-history
# `gc bd list --all` was cut on every pass, and pr-autopilot skipped every
# merged PR on that alone, although the ticket it closes was in the open
# beads it had read in full. This drives pr-autopilot against stub gh/gc
# binaries whose `gc bd list --all` is cut (exit 124, what timeout(1) returns)
# and proves:
#   (a) a merged PR whose ticket is open is reconciled through deliver-close;
#   (b) a merged PR whose ticket is not among the open beads is not, and the
#       cut is reported (unknown, retried next tick -- not "no ticket");
#   (c) a DIRTY ticket-owned PR whose ticket is open goes back to the pool;
#   (d) a DIRTY PR with no open ticket is left undecided, not flagged stuck.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
AUTOPILOT="$REPO_ROOT/bin/pr-autopilot"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/factory/rigs/example-backend" "$TMP/factory/rigs/example-frontend" "$TMP/bin"
: > "$TMP/gh.log"; : > "$TMP/gc.log"

# PR 70 (DIRTY) belongs to the open ticket af-dirty; PR 71 (DIRTY) to none
# among the open beads.
cat > "$TMP/open.json" <<'JSON'
[
 {"number":70,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"DIRTY","statusCheckRollup":[],"headRefOid":"sha70a","headRefName":"do-work/af-dirty","labels":[]},
 {"number":71,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"DIRTY","statusCheckRollup":[],"headRefOid":"sha71a","headRefName":"feature/elsewhere","labels":[]}
]
JSON
# PR 80 merged, its ticket af-sent-back is open (rejected once for a
# conflict, the af-batj8g shape); PR 81 merged, its ticket is not open.
cat > "$TMP/merged.json" <<'JSON'
[
 {"number":80,"headRefName":"do-work/af-sent-back","mergeCommit":{"oid":"cccccccccccccccccccccccccccccccccccccccc"},"mergedAt":"2026-11-12T13:35:00Z"},
 {"number":81,"headRefName":"do-work/af-older","mergeCommit":{"oid":"dddddddddddddddddddddddddddddddddddddddd"},"mergedAt":"2026-11-12T13:36:00Z"}
]
JSON
cat > "$TMP/open-beads.json" <<'JSON'
[
 {"id":"af-sent-back","status":"open","metadata":{"gc.work_branch":"do-work/af-sent-back","gc.pr_rejection_count":"2","gc.pr_rejection_reason":"conflict with main@310021f8732f"}},
 {"id":"af-dirty","status":"in_progress","metadata":{"gc.work_branch":"do-work/af-dirty"}}
]
JSON

cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gh.log"
if [[ "\$1" == pr && "\$2" == list ]]; then
  if [[ "\$*" != *"example-backend"* ]]; then echo '[]'; exit 0; fi
  if [[ "\$*" == *"--state open"* ]]; then cat "$TMP/open.json";
  elif [[ "\$*" == *"--state merged"* ]]; then cat "$TMP/merged.json";
  else echo '[]'; fi
  exit 0
fi
if [[ "\$1" == pr && "\$2" == view && "\$*" == *"--json headRefName"* ]]; then
  case " \$* " in
    *" 70 "*) echo "do-work/af-dirty" ;;
    *" 71 "*) echo "feature/elsewhere" ;;
  esac
  exit 0
fi
if [[ "\$1" == pr && "\$2" == view && "\$*" == *"--json comments"* ]]; then exit 0; fi
if [[ "\$1" == pr && "\$2" == view ]]; then echo '["OPEN","false"]' | jq -r '@tsv'; exit 0; fi
if [[ "\$1" == api && "\$*" == *"/commits/"* ]]; then echo "deadbeefcafefeed1234567890abcdef12345678"; exit 0; fi
if [[ "\$1" == api ]]; then exit 1; fi
exit 0
STUB
cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gc.log"
if [[ "\$1" == bd && "\$2" == list && "\$*" == *"--all"* ]]; then exit 124; fi
if [[ "\$1" == bd && "\$2" == list ]]; then cat "$TMP/open-beads.json"; exit 0; fi
exit 0
STUB
cat > "$TMP/bin/deliver-close" <<STUB
#!/usr/bin/env bash
echo "deliver-close \$*" >> "$TMP/gc.log"
STUB
cat > "$TMP/bin/escalation-door" <<'STUB'
#!/usr/bin/env bash
exit 0
STUB
chmod +x "$TMP/bin/"*
export PATH="$TMP/bin:$PATH"
export GC_BIN="$TMP/bin/gc"
export FACTORY_ROOT="$TMP/factory"
export GC_PR_AUTHORS=example-operator
export REVERSIBILITY_CHECK_BIN="$TMP/bin/gh"
export DELIVER_CLOSE_BIN="$TMP/bin/deliver-close"
export ESCALATION_DOOR_BIN="$TMP/bin/escalation-door"
export PROTECTED_RIGS_CONFIG_DIR="$REPO_ROOT/tests/fixtures/pr-autopilot-projects"
export PR_AUTOPILOT_RECONCILE_CACHE="$TMP/factory/.gc/reconciled.tsv"

out=$("$AUTOPILOT" 2>&1 || true)

# (a) the open ticket of merged PR 80 is reconciled despite the cut history.
grep -q "^deliver-close af-sent-back --repo example-corp/example-backend --pr 80 " "$TMP/gc.log" \
  || { echo "$out" >&2; fail "(a) merged PR 80's open ticket was not reconciled while the whole history read was cut"; }
# (b) merged PR 81 has no open ticket: nothing closed, the cut is reported.
grep -q "^deliver-close .*--pr 81 " "$TMP/gc.log" \
  && { echo "$out" >&2; fail "(b) merged PR 81 was reconciled with no ticket known"; }
grep -q "closed beads unknown (gc bd list --all timed out)" <<<"$out" \
  || { echo "$out" >&2; fail "(b) the cut whole-history read was not reported"; }
# (c) DIRTY PR 70's open ticket goes back to the pool.
grep -q "^bd update af-dirty .*--status open" "$TMP/gc.log" \
  || { echo "$out" >&2; fail "(c) DIRTY PR 70's open ticket was not sent back to the pool"; }
# (d) DIRTY PR 71 with no open ticket: undecided, not filed as stuck.
grep -q "PR #71: DIRTY, ticket link unknown" <<<"$out" \
  || { echo "$out" >&2; fail "(d) DIRTY PR 71 was not left undecided"; }
grep -q "^bd create .*PR #71" "$TMP/gc.log" \
  && { echo "$out" >&2; fail "(d) DIRTY PR 71 was filed while its ticket link was unknown"; }

echo "OK pr-autopilot links PRs to their open tickets when the whole-history read is cut"
