# ADR-0012 — Portable distribution and release preparation

Status: implemented in an isolated branch; active-host adoption pending.

## Problem

The working installation contains host paths, personal defaults and product
state. Copying it does not produce a clean installation for another user.
Existing product context does not establish first-release definition readiness.

## Decision

Ship a reviewed allowlist export, not a copy of the working installation.
Separate reusable source, ignored non-secret installation profile and project
dossiers. Use upstream Gas City initialization in no-start mode; do not add a
runtime supervisor or replace Beads.

New/import onboarding creates the same PO preparation mandate and evidence
requirements. Imports observe Git metadata without mutating source repositories.
Readiness tracks missing requirements and invalidates review after evidence
changes. It is a structural check, not semantic proof or execution authorization.
The Mayor verifies a separate bounded campaign mandate and existing delivery gates.

The generic cockpit selects product identity, PO model, sandbox and preview
command from configuration; legacy configuration remains compatible.
No live process, active configuration, existing product decision or source
checkout is migrated by this change.

## Validation and limits

Test offline exports/new/import/readiness and legacy cockpit regression.
A clean-host paid canary and activation remain separate qualification steps.
The Codex PO bridge is qualified structurally; universal provider adapters are
not claimed. Export excludes historical project-specific operations documents.
