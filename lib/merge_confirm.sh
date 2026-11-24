#!/usr/bin/env bash
# merge_confirm.sh — the one passage point of rule S.merge-confirmed
# (docs/DEFECT_CLASSES.md): « Un état de PR (armée, fusionnée, relancée) n'est
# annoncé qu'une fois relu sur GitHub. »
#
# A zero exit from gh says the request was accepted, not that GitHub is in the
# state asked for: an armed request left no autoMergeRequest (af-npz9v1.50.1,
# PR #767), a merge request only queued the PR (af-nk5nm6, PR #778), a rerun
# was announced while the workflow still ran (af-1l3znv). merge_and_confirm
# makes the request, reads the PR (or the run) back from GitHub, and says the
# state that read shows, never the state that was asked for (af-56yoam.6).
#
#   merge_and_confirm arm    <repo> <num>
#   merge_and_confirm merge  <repo> <num> <head-sha|unknown>
#   merge_and_confirm disarm <repo> <num>
#   merge_and_confirm rerun  <repo> <run-id>
#
# Sets MERGE_CONFIRMED_STATE to the state read back:
#   merged    the PR reads MERGED
#   armed     the PR reads OPEN with an autoMergeRequest
#   disarmed  the PR reads OPEN without one (after disarm)
#   rerun     the run reads anything but completed (after rerun)
#   open      the PR reads OPEN, the asked-for state not reached
#   queued    the PR reads OPEN after an accepted merge request: in the merge
#             queue or waiting for its checks, not merged
#   closed    the PR reads CLOSED
#   completed the run still reads completed: the rerun did not start
#   unknown   the request or the read timed out or failed: say nothing
# MERGE_CONFIRMED_VIEW holds the JSON read back (empty when unknown), and
# MERGE_CONFIRMED_REQUEST_RC the request's own exit code.
#
# Returns 0 when the read confirms the action (merged, armed — or merged —
# after arm, disarmed, rerun), 1 when GitHub reads another state, 2 unknown.
#
# Calls go through the caller's `bounded <cap> cmd...` when it defines one
# (bin/pr-autopilot's time budget), else through timeout(1). Caps:
# MERGE_CONFIRM_WRITE_CAP / MERGE_CONFIRM_READ_CAP (default 30 / 20 s).

MERGE_CONFIRMED_STATE=""; MERGE_CONFIRMED_VIEW=""; MERGE_CONFIRMED_REQUEST_RC=""

_merge_confirm_call() {  # cap cmd...
  if declare -F bounded >/dev/null; then bounded "$@"; else timeout -k 5 "$@"; fi
}
_merge_confirm_timed_out() { [ "$1" = 124 ] || [ "$1" = 137 ]; }

merge_and_confirm() {
  local action=$1 repo=$2 target=$3 sha=${4:-unknown}
  local wcap=${MERGE_CONFIRM_WRITE_CAP:-30} rcap=${MERGE_CONFIRM_READ_CAP:-20}
  local -a req read
  local rc view state armed
  MERGE_CONFIRMED_STATE=unknown; MERGE_CONFIRMED_VIEW=""; MERGE_CONFIRMED_REQUEST_RC=""
  case "$action" in
    arm)    req=(pr merge "$target" --repo "$repo" --auto --squash) ;;
    merge)  req=(pr merge "$target" --repo "$repo" --squash)
            [ "$sha" != "unknown" ] && req+=(--match-head-commit "$sha") ;;
    disarm) req=(pr merge "$target" --repo "$repo" --disable-auto) ;;
    rerun)  req=(run rerun "$target" --repo "$repo" --failed) ;;
    *) printf 'merge_and_confirm: unknown action %s\n' "$action" >&2; return 2 ;;
  esac
  if [ "$action" = rerun ]; then
    read=(run view "$target" --repo "$repo" --json status,conclusion)
  else
    read=(pr view "$target" --repo "$repo"
          --json state,autoMergeRequest,mergeStateStatus,statusCheckRollup,headRefOid)
  fi

  _merge_confirm_call "$wcap" gh "${req[@]}" >/dev/null 2>&1; MERGE_CONFIRMED_REQUEST_RC=$?
  # A request cut by the clock has an unknown outcome; the next pass reads it.
  # A merge is the exception: gh exits non-zero after a good merge it could
  # not clean up locally, so a merge request is always read back.
  if _merge_confirm_timed_out "$MERGE_CONFIRMED_REQUEST_RC" && [ "$action" != merge ]; then return 2; fi
  # A refused rerun leaves the old run completed: nothing to confirm.
  if [ "$action" = rerun ] && [ "$MERGE_CONFIRMED_REQUEST_RC" != 0 ]; then
    MERGE_CONFIRMED_STATE=completed; return 1
  fi

  view=$(_merge_confirm_call "$rcap" gh "${read[@]}" 2>/dev/null); rc=$?
  if [ "$rc" != 0 ] || ! jq -e 'type=="object"' >/dev/null 2>&1 <<<"$view"; then return 2; fi
  MERGE_CONFIRMED_VIEW=$view

  if [ "$action" = rerun ]; then
    state=$(jq -r '.status // ""' <<<"$view")
    case "$state" in
      '') return 2 ;;
      completed) MERGE_CONFIRMED_STATE=completed; return 1 ;;
      *) MERGE_CONFIRMED_STATE=rerun; return 0 ;;
    esac
  fi

  state=$(jq -r '.state // ""' <<<"$view")
  armed=$(jq -r 'if .autoMergeRequest == null then "false" else "true" end' <<<"$view")
  case "$state" in
    MERGED) MERGE_CONFIRMED_STATE=merged
            [ "$action" = disarm ] && return 1
            return 0 ;;
    CLOSED) MERGE_CONFIRMED_STATE=closed; return 1 ;;
    OPEN) ;;
    *) return 2 ;;
  esac
  if [ "$action" = merge ] && _merge_confirm_timed_out "$MERGE_CONFIRMED_REQUEST_RC"; then
    return 2   # still open after a cut request: it may yet land
  fi
  case "$action:$armed" in
    arm:true)     MERGE_CONFIRMED_STATE=armed; return 0 ;;
    disarm:false) MERGE_CONFIRMED_STATE=disarmed; return 0 ;;
    disarm:true)  MERGE_CONFIRMED_STATE=armed; return 1 ;;
    merge:*)      if [ "$MERGE_CONFIRMED_REQUEST_RC" = 0 ]; then MERGE_CONFIRMED_STATE=queued
                  else MERGE_CONFIRMED_STATE=open; fi
                  return 1 ;;
    *)            MERGE_CONFIRMED_STATE=open; return 1 ;;
  esac
}
