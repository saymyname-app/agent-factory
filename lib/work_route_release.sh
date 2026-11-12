#!/usr/bin/env bash
# work_route_release.sh — what a Factory tool removes from a work ticket it
# reopens without launching it again (af-asymry, proposal af-h1os1o, class L
# of docs/DEFECT_CLASSES.md).
#
# A work ticket is worked by the session its launch (bin/dispatch-door, then
# mol-do-work) started for it. Reopened with its route (gc.routed_to) or with
# the back-reference of the session that held it (gc.session_id,
# gc.session_name), it is ready, unassigned and routed to the factory-worker
# pool -- or Gas City's detached-orphan sweep routes it there again from that
# back-reference (pool_detached_orphan_sweep.go: open, no assignee, a
# gc.work_branch and a session reference). The next worker's
# `gc hook --claim` then takes it in place of the ticket it was launched for
# (2026-11-11: the session launched for af-fv8ca4 took af-8fk8nz, reopened by
# `escalation-door repondre`, and resumed it on the wrong branch).
#
# Without them the reopened ticket waits to be launched again: ready, it is
# what bin/idle-ready-work-wake shows the Mayor, who dispatches it through the
# door, and mol-do-work stamps the new session back on it.
#
# Sourced by every tool that reopens a work ticket; tests/work-route-release-
# test.py holds each such write to these arguments.
# shellcheck disable=SC2034  # read by the tools that source this file
WORK_ROUTE_RELEASE_ARGS=(--unset-metadata gc.routed_to
  --unset-metadata gc.session_id --unset-metadata gc.session_name)
