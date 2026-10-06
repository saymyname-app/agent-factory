#!/usr/bin/env bash
# ticket-author-check — the check Gas City runs when a step of the formula
# mol-ticket-author is closed (T12, af-i3q5a5; Spec af-wf4w5r §0 rule 4).
#
# This file is the source; a formula names its copy in the store of the
# ticket, `.gc/scripts/checks/ticket-author-check.sh`, which
# `bin/factory-build-gates` materialises in the city root and in each rig.
#
# Gas City gives an exec check no argument (tried on 1.4.1 in an isolated
# city, 2026-10-06: `args` of a `[steps.check.check]` is not passed), only
# its environment: GC_BEAD_ID, the bead of the step it just saw closed, and
# GC_CITY_PATH, the city root. `ticket-author check` reads the step and the
# ticket from that bead and runs the gate of the step: exit 0 lets the next
# step start; anything else re-opens the step, with the refusal (stderr) in
# its attempt log.
set -euo pipefail
exec "${GC_CITY_PATH:?ticket-author-check: GC_CITY_PATH is not set, this check is run by Gas City}/bin/ticket-author" check
