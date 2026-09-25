Use the built-in Gas City publish flow.

If publishing is enabled, publish the finalized build-basic result with the existing publish helper. If publishing is disabled, record a no-op publish outcome with the final artifact paths.

For build-basic, a finalized result can be an approved source anchor/worktree.
Do not mark publish failed or downgrade the workflow merely because the launcher
rig root was not mutated. When publishing is disabled, record a `noop` publish
result while preserving the approved build outcome.

`gc.outcome` is the workflow step outcome, not the publish mode. Never set
`gc.outcome=noop`. A disabled/no-op publish is a successful publish step:

```bash
bd update "$CLAIMED_BEAD_ID" \
  --set-metadata 'gc.outcome=pass' \
  --set-metadata 'gc.publish_outcome=noop' \
  --set-metadata 'gc.publish_mode=disabled' \
  --set-metadata 'gc.build_outcome=pass' \
  --set-metadata 'gc.final_report=<final report path>' \
  --set-metadata 'gc.artifact_root=<artifact root>'
bd close "$CLAIMED_BEAD_ID" --reason 'Publishing disabled; build-basic result approved.'
```

Close only after the push, PR creation, or no-op publish result is recorded.

## Overlapping worktrees: file a follow-up bead, never a silent no-op

If the publish/finalize drain finds overlapping or duplicate-content
worktrees among the implementation convoy's source anchors, do not attempt an
automated N-way merge and do not open a PR from one — auto-merging under
detected ambiguity has real blast radius (wrong file selection landing
unreviewed) with no human review point (af-1c3yy). Recording only the no-op
publish result and moving on leaves a fully-approved, all-REQs-covered result
sitting unmerged with nothing surfacing it to a human or the Mayor.

Record the standard no-op publish outcome above, and in the same step file a
follow-up bead so the unmerged-but-approved result is always visible as
ready/open work:

```bash
FOLLOWUP_ID=$(gc bd create \
  --title "Unmerged approved build result pending de-duplication: <workflow-root-id>" \
  --type task \
  --priority 1 \
  --notes "Workflow root: <workflow-root-id>
Overlapping/duplicate-content worktrees: <worktree paths>
Final report: <gc.build.final_report_path>
Review report / code-review-context: <path, if recorded>
Reason: publish/finalize detected overlapping or duplicate-content worktrees
and refused an automated N-way merge. This build's requirements are approved
and covered, but the result is unmerged. A human or the Mayor must pick the
canonical file set and land it via PR. Do not auto-merge or auto-PR (af-1c3yy)."
  --json | jq -r '.id // .[0].id')
bd update "<workflow-root-id>" --set-metadata "gc.publish_followup_bead_id=$FOLLOWUP_ID"
```

Reference the follow-up bead id in the no-op close reason (e.g. `bd close
"$CLAIMED_BEAD_ID" --reason "Publishing disabled; overlapping worktrees; filed
$FOLLOWUP_ID for human de-duplication."`). Do not attempt the merge or PR
yourself here — filing the bead is the entire remediation for this fallback.

For a same-session implementation (`gc.var.drain_policy=same-session`), the
workflow root owns one `gc.shared_worktree`, `gc.work_branch`, and
`gc.work_base_branch` prepared before the drain. The review stage has already
consumed that path. Publish that one branch exactly once through the Factory
adapter instead of pushing each source anchor:

```bash
FACTORY_ROOT="${FACTORY_ROOT:-/home/benja/agent-factory}"
"$FACTORY_ROOT/bin/factory-shared-drain-workspace" publish \
  "<workflow-root-id>" "<implementation-convoy-id>" "{{push}}" "{{open_pr}}"
```

Treat adapter results `published`, `pushed`, and `noop` as successful publish
actions and record the returned commit/PR evidence on the workflow root and
publish result artifact. The adapter reuses an existing open PR or root
`gc.pr_url`; it must never create one PR per source anchor. Do not remove the
worktree here: `cleanup-shared-worktree` is the scope teardown and runs after
this step, including when an earlier pipeline member failed.

For `drain_policy=separate`, keep the existing per-item publisher behavior
unchanged and do not call the shared-worktree adapter.
