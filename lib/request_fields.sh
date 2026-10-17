#!/usr/bin/env bash
# request_fields.sh — the one check of a request's fields at the door that
# writes it (T59, af-qjq1t6): bin/escalation-door and bin/proposal-door
# source it, so a request the operator could not act on is refused the same
# way at both doors, before anything is written.
#
# The sourcing door provides `die <message>` (prints and exits non-zero)
# and sets REQUEST_INCOMPLETE, the words that open a refusal for a missing
# field ("requête incomplète", "proposition incomplète").
#
#   field_ok <label> <value>      a single-line field: present, not made of
#                                 spaces only, no newline, <= MAX_LINE_LENGTH
#   validate_que_faire <json>     a non-empty array of options, each with
#                                 its option and its consequence, at most
#                                 one recommended and that one with its
#                                 raison; prints it back with a .lettre
#                                 (a, b, c, ...) added to each option

MAX_LINE_LENGTH=140
OPTION_LETTERS="abcdefghijklmnopqrstuvwxyz"

field_ok() {  # $1 = label (for the diagnostic) $2 = value
  local label=$1 value=$2
  [[ -n ${value//[[:space:]]/} ]] || die "$REQUEST_INCOMPLETE : champ « $label » manquant."
  [[ $value != *$'\n'* && $value != *$'\r'* ]] || die "champ « $label » doit tenir sur une seule ligne."
  (( ${#value} <= MAX_LINE_LENGTH )) || die "champ « $label » dépasse $MAX_LINE_LENGTH caractères."
}

validate_que_faire() {  # $1 = JSON array
  local json=$1
  jq -e 'type == "array" and length > 0' <<<"$json" >/dev/null 2>&1 \
    || die "$REQUEST_INCOMPLETE : champ « que faire » manquant ou vide."
  local count i
  count=$(jq 'length' <<<"$json")
  for ((i = 0; i < count; i++)); do
    local item option consequence recommande raison
    item=$(jq -c ".[$i]" <<<"$json")
    option=$(jq -r '.option // ""' <<<"$item")
    consequence=$(jq -r '.consequence // ""' <<<"$item")
    recommande=$(jq -r 'if (.recommande // false) == true then "true" else "false" end' <<<"$item")
    raison=$(jq -r '.raison // ""' <<<"$item")
    field_ok "option $((i + 1))" "$option"
    field_ok "conséquence de l'option $((i + 1))" "$consequence"
    if [[ $recommande == true ]]; then
      field_ok "raison de la recommandation" "$raison"
    fi
  done
  local recommended_count
  recommended_count=$(jq '[.[] | (.recommande // false)] | map(select(. == true)) | length' <<<"$json")
  (( recommended_count <= 1 )) || die "au plus une option « Recommandé »."
  jq -c --arg letters "$OPTION_LETTERS" \
    '[to_entries[] | .value + {lettre: $letters[.key:(.key + 1)]}]' <<<"$json"
}
