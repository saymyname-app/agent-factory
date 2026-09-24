#!/usr/bin/env bash
# protected_rigs.sh — single source of truth for which rig+branch pairs are
# protected: no writer formula may commit directly to them, only land
# changes through a branch + PR. Sourced by bin/pr-autopilot (to decide what
# to arm for auto-merge) and bin/factory-do-work-workspace (to decide when a
# do-work dispatch must be isolated in a worktree instead of committing in
# place). Keep both consumers pointed at this one table (af-09hxz) so a rig
# added here is protected everywhere, not just in whichever script an author
# remembered to update.
#
# rig_dir (relative to FACTORY_ROOT, "." for the factory root itself) | repo | protected branch | required GitHub Actions workflow
PROTECTED_RIGS=(
  "rigs/saymyname-backend|saymyname-app/Say-my-name-back|dev|Backend CI"
  "rigs/saymyname-frontend|saymyname-app/Say-my-name-front|dev|Frontend CI"
  ".|saymyname-app/agent-factory|main|Factory CI"
)
