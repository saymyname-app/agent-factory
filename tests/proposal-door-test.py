#!/usr/bin/env python3
"""C01 Cockpit V2, T07: proposal-door is the one door for every proposal.
Proves: `create` refuses a proposal missing its required fields (quoi /
pourquoi / que_faire / langue in the Operator Language) without writing
anything, and creates a complete one labelled `proposal`; `accepter`,
`rejeter` (refuses without a reason) and `reporter` each trace their action
on the bead (comment + metadata, acteur); `compte` excludes accepted and
rejected proposals from the pending count, while a legacy proposal with no
gc.proposal_state still counts as pending.
"""

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "proposal-door"

FAKE_GC = r"""#!/usr/bin/env bash
set -Eeuo pipefail

: "${PD_BEAD_DIR:?PD_BEAD_DIR must be set by the test}"
: "${PD_CALL_LOG:?PD_CALL_LOG must be set by the test}"
: "${PD_NEXT_ID_FILE:?PD_NEXT_ID_FILE must be set by the test}"
printf '%q ' "$@" >>"$PD_CALL_LOG"
printf '\n' >>"$PD_CALL_LOG"

bead_file() { printf '%s/%s.json' "$PD_BEAD_DIR" "$1"; }

if [[ ${1:-} == bd && ${2:-} == create ]]; then
  id=$(cat "$PD_NEXT_ID_FILE")
  printf '{"id":"%s","status":"open","metadata":{},"notes":"","labels":["proposal"]}' "$id" >"$(bead_file "$id")"
  printf 'created %s\n' "$id"
  exit 0
fi

if [[ ${1:-} == bd && ${2:-} == show && ${4:-} == --json ]]; then
  id=$3
  file=$(bead_file "$id")
  [[ -f $file ]] || { printf 'not found\n' >&2; exit 42; }
  jq -c '[.]' "$file"
  exit 0
fi

if [[ ${1:-} == bd && ${2:-} == update ]]; then
  id=$3
  file=$(bead_file "$id")
  [[ -f $file ]] || printf '{"id":"%s","status":"open","metadata":{},"notes":"","labels":["proposal"]}' "$id" >"$file"
  shift 3
  tmp="${file}.tmp"
  cp "$file" "$tmp"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --set-metadata)
        pair=$2
        key=${pair%%=*}
        value=${pair#*=}
        jq --arg key "$key" --arg value "$value" '.metadata[$key] = $value' "$tmp" >"${tmp}.next"
        mv "${tmp}.next" "$tmp"
        shift 2
        ;;
      --append-notes)
        jq --arg note "$2" '.notes = ((.notes // "") + "\n" + $note)' "$tmp" >"${tmp}.next"
        mv "${tmp}.next" "$tmp"
        shift 2
        ;;
      *)
        printf 'unsupported gc bd update flag: %s\n' "$1" >&2
        exit 64
        ;;
    esac
  done
  mv "$tmp" "$file"
  printf '{}\n'
  exit 0
fi

if [[ ${1:-} == bd && ${2:-} == list ]]; then
  shift 2
  status_filter=""
  label=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --status) status_filter=$2; shift 2 ;;
      --label) label=$2; shift 2 ;;
      --json) shift ;;
      *) shift ;;
    esac
  done
  matches=()
  for file in "$PD_BEAD_DIR"/*.json; do
    [[ -f $file ]] || continue
    [[ $file == *.tmp* ]] && continue
    bead=$(jq -c '.' "$file")
    if [[ -n $status_filter ]]; then
      status=$(jq -r '.status // "open"' <<<"$bead")
      IFS=',' read -r -a wanted <<<"$status_filter"
      keep=0
      for w in "${wanted[@]}"; do [[ $w == "$status" ]] && keep=1; done
      [[ $keep == 1 ]] || continue
    fi
    if [[ -n $label ]]; then
      has_label=$(jq -r --arg l "$label" '(.labels // []) | index($l) != null' <<<"$bead")
      [[ $has_label == true ]] || continue
    fi
    matches+=("$bead")
  done
  if [[ ${#matches[@]} -eq 0 ]]; then
    printf '[]\n'
  else
    (IFS=,; printf '[%s]\n' "${matches[*]}")
  fi
  exit 0
fi

printf 'unsupported gc fixture command: %s\n' "$*" >&2
exit 64
"""


class ProposalDoorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.bead_dir = root / "beads"
        self.bead_dir.mkdir()
        self.call_log = root / "calls.log"
        self.call_log.write_text("", encoding="utf-8")
        self.next_id_file = root / "next-id"
        self.next_id_file.write_text("af-prop1", encoding="utf-8")
        fake_gc = root / "gc"
        fake_gc.write_text(FAKE_GC, encoding="utf-8")
        fake_gc.chmod(fake_gc.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        self.env = {
            **os.environ,
            "GC_BIN": str(fake_gc),
            "PD_BEAD_DIR": str(self.bead_dir),
            "PD_CALL_LOG": str(self.call_log),
            "PD_NEXT_ID_FILE": str(self.next_id_file),
            "PROPOSAL_DOOR_LOCK_FILE": str(root / "lock"),
            "PROPOSAL_DOOR_NOW": "1790000000",
        }

    def door(self, *args, check=False):
        return subprocess.run(
            (str(SCRIPT),) + args, env=self.env, text=True, capture_output=True, check=check
        )

    def seed(self, bead_id, payload):
        (self.bead_dir / f"{bead_id}.json").write_text(json.dumps(payload), encoding="utf-8")

    def bead(self, bead_id):
        return json.loads((self.bead_dir / f"{bead_id}.json").read_text(encoding="utf-8"))

    def set_next_id(self, bead_id):
        self.next_id_file.write_text(bead_id, encoding="utf-8")

    COMPLETE = {
        "quoi": "Proposer des leases dynamiques pour les conflits PR répétés",
        "pourquoi": "3 conflits PR sans chevauchement déclaré en 7 jours",
        "que_faire": [
            {
                "option": "Étudier les leases dynamiques au prochain Planning Run",
                "consequence": "Aucun changement immédiat ; trié à la prochaine carte.",
                "recommande": True,
                "raison": "Le seuil est franchi trois fois cette semaine.",
            }
        ],
        "langue": "fr",
    }

    # --- create --------------------------------------------------------

    def test_create_refuses_a_proposal_missing_a_required_field(self):
        missing = {k: v for k, v in self.COMPLETE.items() if k != "pourquoi"}
        result = self.door("create", json.dumps(missing))
        self.assertNotEqual(0, result.returncode)
        self.assertEqual([], list(self.bead_dir.glob("*.json")))

    def test_create_refuses_an_option_with_no_consequence(self):
        payload = json.loads(json.dumps(self.COMPLETE))
        del payload["que_faire"][0]["consequence"]
        result = self.door("create", json.dumps(payload))
        self.assertNotEqual(0, result.returncode)

    def test_create_refuses_a_language_other_than_the_operator_language(self):
        payload = json.loads(json.dumps(self.COMPLETE))
        payload["langue"] = "en"
        result = self.door("create", json.dumps(payload))
        self.assertNotEqual(0, result.returncode)

    def test_create_writes_a_complete_proposal_labelled_proposal(self):
        self.set_next_id("af-prop1")
        result = self.door("create", json.dumps(self.COMPLETE), check=True)
        self.assertIn("af-prop1", result.stdout)
        bead = self.bead("af-prop1")
        self.assertIn("proposal", bead["labels"])
        self.assertEqual(self.COMPLETE["quoi"], bead["metadata"]["gc.proposal_quoi"])
        self.assertEqual("ouverte", bead["metadata"]["gc.proposal_state"])

    # --- accepter / rejeter / reporter ----------------------------------

    def test_accepter_moves_to_a_planifier_and_traces_actor(self):
        self.seed("af-x", {"id": "af-x", "status": "open", "metadata": {}, "notes": "", "labels": ["proposal"]})
        result = self.door("accepter", "af-x", "benjamin", check=True)
        self.assertIn("af-x", result.stdout)
        bead = self.bead("af-x")
        self.assertEqual("a_planifier", bead["metadata"]["gc.proposal_state"])
        self.assertEqual("benjamin", bead["metadata"]["gc.proposal_response_actor"])
        self.assertIn("ACCEPTÉE", bead["notes"])

    def test_rejeter_without_a_reason_is_refused(self):
        self.seed("af-x", {"id": "af-x", "status": "open", "metadata": {}, "notes": "", "labels": ["proposal"]})
        result = self.door("rejeter", "af-x", "", "benjamin")
        self.assertNotEqual(0, result.returncode)
        bead = self.bead("af-x")
        self.assertNotIn("gc.proposal_state", bead["metadata"])

    def test_rejeter_with_a_reason_is_traced(self):
        self.seed("af-x", {"id": "af-x", "status": "open", "metadata": {}, "notes": "", "labels": ["proposal"]})
        result = self.door("rejeter", "af-x", "Hors périmètre du Planning Run", "benjamin", check=True)
        self.assertIn("af-x", result.stdout)
        bead = self.bead("af-x")
        self.assertEqual("rejetee", bead["metadata"]["gc.proposal_state"])
        self.assertEqual("Hors périmètre du Planning Run", bead["metadata"]["gc.proposal_reject_reason"])
        self.assertEqual("benjamin", bead["metadata"]["gc.proposal_response_actor"])

    def test_reporter_defers_until_an_hour_and_traces_actor(self):
        self.seed("af-x", {"id": "af-x", "status": "open", "metadata": {}, "notes": "", "labels": ["proposal"]})
        result = self.door("reporter", "af-x", "demain 09:00", "benjamin", check=True)
        self.assertIn("af-x", result.stdout)
        bead = self.bead("af-x")
        self.assertEqual("demain 09:00", bead["metadata"]["gc.proposal_report_until"])
        self.assertEqual("benjamin", bead["metadata"]["gc.proposal_response_actor"])
        # A deferred proposal is still pending: reporter never sets proposal_state.
        self.assertNotIn("gc.proposal_state", bead["metadata"])

    # --- compte ----------------------------------------------------------

    def test_compte_excludes_accepted_and_rejected_proposals(self):
        self.seed("af-legacy", {"id": "af-legacy", "status": "open", "metadata": {}, "notes": "", "labels": ["proposal"]})
        self.seed("af-accepted", {"id": "af-accepted", "status": "open", "metadata": {"gc.proposal_state": "a_planifier"}, "notes": "", "labels": ["proposal"]})
        self.seed("af-rejected", {"id": "af-rejected", "status": "open", "metadata": {"gc.proposal_state": "rejetee"}, "notes": "", "labels": ["proposal"]})
        self.seed("af-open", {"id": "af-open", "status": "open", "metadata": {"gc.proposal_state": "ouverte"}, "notes": "", "labels": ["proposal"]})
        result = self.door("compte", check=True)
        self.assertEqual("2", result.stdout.strip())

    def test_compte_is_zero_with_no_proposals(self):
        result = self.door("compte", check=True)
        self.assertEqual("0", result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
