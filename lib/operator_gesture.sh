# shellcheck shell=bash
#
# operator_gesture.sh -- a gesture in the operator's name needs a verifiable
# reference (ADR-0036 point 5, J3 of af-q55qqx, af-q55qqx.1).
#
# On 12/10/2026 decisions were recorded as Benjamin's while he slept
# (af-yowfs9): `--actor benjamin` was declarative. A door sourcing this file
# refuses an acteur that names the operator unless --ref cites one of:
#
#   cockpit:<login>   a confirmed Cockpit click; the Cockpit's action guard
#                     has already checked the Tailscale identity
#                     (lib/cockpit/access/guard.py) before calling the door.
#   session:<id>      the id of the live chat session or message where he
#                     said it (Claude Code session, Codex thread or message).
#   github:<url>      a comment of his on GitHub (#issuecomment-N or
#                     #pullrequestreview-N).
#
# Limit, stated honestly: the reference is required and its form checked,
# not proven. Every agent of this host runs as the same Unix user and holds
# the owner's GitHub token (pr-autopilot comments as him), so nothing on the
# host can tell his gesture from a forged one; per-role identity is J11
# (af-q55qqx decision 3). What this closes is the silent case: a gesture in
# his name now names where he said it, and the record carries it.
#
# Needs: die(); reads OPERATOR_NAME when the door set it.
OPERATOR_NAME_GESTURE=${OPERATOR_NAME:-Benjamin}

OPERATOR_REF_RE='^(cockpit:[^[:space:]]+|session:[A-Za-z0-9][A-Za-z0-9._:-]{7,}|github:https://github\.com/[^[:space:]/]+/[^[:space:]/]+/(issues|pull)/[0-9]+#(issuecomment|pullrequestreview)-[0-9]+)$'

operator_actor() {  # $1 = acteur -> 0 when it names the operator
  local a=${1,,}
  [[ $a == benjamin || $a == benjamin-* || $a == "${OPERATOR_NAME_GESTURE,,}" ]]
}

operator_gesture_check() {  # acteur ref -> dies unless the gesture is allowed
  local acteur=$1 ref=${2:-}
  if [[ -n $ref ]]; then
    [[ $ref =~ $OPERATOR_REF_RE ]] \
      || die "référence « $ref » illisible : cockpit:<login>, session:<id> ou github:<url d'un commentaire> (ADR-0036 point 5)."
  fi
  operator_actor "$acteur" || return 0
  [[ -n $ref ]] \
    || die "un geste au nom de $OPERATOR_NAME_GESTURE exige --ref <référence vérifiable> (cockpit:<login>, session:<id>, github:<url d'un commentaire>) ; sans elle, l'acteur est l'agent (ADR-0036 point 5). Rien n'est écrit."
}
