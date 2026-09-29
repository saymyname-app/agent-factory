#!/usr/bin/env bash
#
# af-yl964 (P05): enable-strict-main-protection must apply
# strict_required_status_checks_policy + allow_update_branch on
# saymyname-app/agent-factory only, be idempotent (a second run makes no
# write calls once applied), and support --rollback. This drives it against
# a faked `gh` that persists ruleset/repo state on disk, and proves:
#  1. it refuses any --repo other than saymyname-app/agent-factory, before
#     making any write call;
#  2. a first run flips both settings and reads them back true;
#  3. a second run makes no PUT/PATCH call (already applied);
#  4. --rollback flips both settings back to false.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
SCRIPT="$REPO_ROOT/bin/enable-strict-main-protection"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/bin"
: > "$TMP/gh.log"

cat > "$TMP/ruleset.json" <<'JSON'
{"id":23626687,"name":"AF-main-protection","target":"branch","source_type":"Repository","source":"saymyname-app/agent-factory","enforcement":"active","conditions":{"ref_name":{"exclude":[],"include":["refs/heads/main"]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"},{"type":"required_status_checks","parameters":{"strict_required_status_checks_policy":false,"do_not_enforce_on_create":false,"required_status_checks":[{"context":"Tests","integration_id":15368}]}}],"bypass_actors":[]}
JSON

cat > "$TMP/repo.json" <<'JSON'
{"full_name":"saymyname-app/agent-factory","allow_update_branch":false}
JSON

# gh stub: reads/writes the ruleset and repo fixtures above, logs every
# call. Refuses (loudly, like the real gh would with a 404) any repo other
# than saymyname-app/agent-factory so a bug that skips the script's own
# guard would still fail the test instead of silently "succeeding".
cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gh.log"
args=("\$@")

if [[ "\${args[0]}" != api ]]; then
  echo "unexpected gh subcommand: \${args[*]}" >&2
  exit 1
fi

path=""
method="GET"
jq_filter=""
input_from_stdin=0
i=1
while [[ \$i -le \${#args[@]} ]]; do
  a="\${args[\$i]}"
  case "\$a" in
    -X) i=\$((i+1)); method="\${args[\$i]}" ;;
    --jq) i=\$((i+1)); jq_filter="\${args[\$i]}" ;;
    -F) i=\$((i+1)) ;; # field, consumed positionally below via FIELD_ARG
    --input) i=\$((i+1)); [[ "\${args[\$i]}" == "-" ]] && input_from_stdin=1 ;;
    *)
      if [[ -z "\$path" ]]; then path="\$a"; fi
      ;;
  esac
  i=\$((i+1))
done

if [[ "\$path" != repos/saymyname-app/agent-factory* ]]; then
  echo "gh stub: repo not found: \$path" >&2
  exit 1
fi

case "\$path" in
  repos/saymyname-app/agent-factory/rulesets)
    list=\$(jq -c '[{id: .id, name: .name}]' "$TMP/ruleset.json")
    if [[ -n "\$jq_filter" ]]; then
      printf '%s' "\$list" | jq -r "\$jq_filter"
    else
      printf '%s\n' "\$list"
    fi
    exit 0
    ;;
  repos/saymyname-app/agent-factory/rulesets/23626687)
    if [[ "\$method" == "PUT" ]]; then
      if [[ "\$input_from_stdin" -ne 1 ]]; then
        echo "gh stub: expected --input -" >&2
        exit 1
      fi
      new=\$(cat)
      # Real GitHub keeps server-assigned fields (id, source*) even though a
      # PUT body only carries the mutable ones -- merge them back in so the
      # fixture still round-trips like the live API would.
      jq --slurpfile orig "$TMP/ruleset.json" '. + {id: \$orig[0].id, source_type: \$orig[0].source_type, source: \$orig[0].source}' <<<"\$new" > "$TMP/ruleset.json.tmp"
      mv "$TMP/ruleset.json.tmp" "$TMP/ruleset.json"
      exit 0
    fi
    if [[ -n "\$jq_filter" ]]; then
      jq -r "\$jq_filter" "$TMP/ruleset.json"
    else
      cat "$TMP/ruleset.json"
    fi
    exit 0
    ;;
  repos/saymyname-app/agent-factory)
    if [[ "\$method" == "PATCH" ]]; then
      for a in "\${args[@]}"; do
        if [[ "\$a" == allow_update_branch=* ]]; then
          value="\${a#allow_update_branch=}"
          jq --argjson v "\$value" '.allow_update_branch = \$v' "$TMP/repo.json" > "$TMP/repo.json.tmp"
          mv "$TMP/repo.json.tmp" "$TMP/repo.json"
        fi
      done
      exit 0
    fi
    if [[ -n "\$jq_filter" ]]; then
      jq -r "\$jq_filter" "$TMP/repo.json"
    else
      cat "$TMP/repo.json"
    fi
    exit 0
    ;;
  *)
    echo "gh stub: unhandled path: \$path" >&2
    exit 1
    ;;
esac
STUB
chmod +x "$TMP/bin/gh"

export PATH="$TMP/bin:$PATH"

# 1. Refuses any repo other than agent-factory, before any gh call.
if "$SCRIPT" --repo saymyname-app/Say-my-name-back >/dev/null 2>"$TMP/refuse.err"; then
  fail "expected the script to refuse a non-agent-factory --repo"
fi
grep -q "only ever targets saymyname-app/agent-factory" "$TMP/refuse.err" || fail "refusal message did not name the guarded repo"
[[ -s "$TMP/gh.log" ]] && fail "refused run must not call gh at all"

# 2. First run flips both settings.
out1=$("$SCRIPT")
printf '%s\n' "$out1" | grep -q "strict_required_status_checks_policy -> true" || fail "first run did not report flipping strict to true"
printf '%s\n' "$out1" | grep -q "allow_update_branch -> true" || fail "first run did not report flipping allow_update_branch to true"

strict_now=$(jq -r '.rules[] | select(.type == "required_status_checks") | .parameters.strict_required_status_checks_policy' "$TMP/ruleset.json")
[[ "$strict_now" == "true" ]] || fail "ruleset fixture was not actually updated to strict=true"
allow_now=$(jq -r '.allow_update_branch' "$TMP/repo.json")
[[ "$allow_now" == "true" ]] || fail "repo fixture was not actually updated to allow_update_branch=true"

other_repo_hit=$(grep -c "Say-my-name" "$TMP/gh.log" || true)
[[ "$other_repo_hit" -eq 0 ]] || fail "the run touched a repo other than agent-factory"

# 3. Second run is a no-op: no PUT/PATCH call.
: > "$TMP/gh.log"
out2=$("$SCRIPT")
printf '%s\n' "$out2" | grep -q "already true -- no change" || fail "second run did not report the idempotent no-op for strict"
printf '%s\n' "$out2" | grep -q "allow_update_branch already true -- no change" || fail "second run did not report the idempotent no-op for allow_update_branch"
grep -qE '^api -X (PUT|PATCH)' "$TMP/gh.log" && fail "idempotent second run made a write call"

# 4. --rollback flips both back to false.
out3=$("$SCRIPT" --rollback)
printf '%s\n' "$out3" | grep -q "strict_required_status_checks_policy -> false" || fail "rollback did not flip strict to false"
printf '%s\n' "$out3" | grep -q "allow_update_branch -> false" || fail "rollback did not flip allow_update_branch to false"
strict_after=$(jq -r '.rules[] | select(.type == "required_status_checks") | .parameters.strict_required_status_checks_policy' "$TMP/ruleset.json")
[[ "$strict_after" == "false" ]] || fail "ruleset fixture was not reverted by --rollback"
allow_after=$(jq -r '.allow_update_branch' "$TMP/repo.json")
[[ "$allow_after" == "false" ]] || fail "repo fixture was not reverted by --rollback"

echo "PASS: enable-strict-main-protection-test"
