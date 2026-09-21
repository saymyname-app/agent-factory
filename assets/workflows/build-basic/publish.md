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
