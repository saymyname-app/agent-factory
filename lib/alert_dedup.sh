#!/usr/bin/env bash
# alert_dedup.sh — the one passage point of rule S.alert-dedup
# (docs/DEFECT_CLASSES.md): « Une alerte cherche son double parmi tous les
# beads non fermés et ne remonte pas un bead fermé. »
#
# An alert names its cause with one metadata field (key=value, e.g.
# gc.order_subject=pr-autopilot), never with its title: a title is reworded,
# a key is not. Its double is looked for among every unfinished status: a bead
# taken for repair or parked is still the bead of its cause (af-yzojic,
# 2026-11-13, three duplicates beside the in_progress af-65mbq2). A closed bead
# is never reopened: it answers the failures seen until its closing, so only
# its closing time is read (af-yzo8fo.2).
#
#   alert_dedup_unfinished <key>=<value>
#       prints the unfinished beads carrying that field, as a JSON array
#       (oldest first; [] when none)
#   alert_dedup_last_closed <key>=<value>
#       prints the latest closed_at among the closed ones, or « none »
#
# Both return 1 and print nothing when the tracker cannot be read: a failed
# read is never « no bead », it filed a duplicate on the saturated host
# (af-yqci4n beside af-giox6p, 2026-10-12).

alert_dedup_unfinished() {
  local out
  out=$(gc bd list --status open,in_progress,blocked,deferred --limit 0 --metadata-field "$1" --json 2>/dev/null) \
    || return 1
  jq -ce 'if type == "array" then sort_by(.created_at // "") else error end' <<<"$out" 2>/dev/null || return 1
}

alert_dedup_last_closed() {
  local out
  out=$(gc bd list --status closed --limit 0 --metadata-field "$1" --json 2>/dev/null) || return 1
  jq -re 'if type == "array" then ([.[].closed_at // empty] | max // "none") else error end' <<<"$out" 2>/dev/null \
    || return 1
}
