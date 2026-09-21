Use the built-in Gas City shared-session implementation drain.

Drain the approved decomposition in one shared worktree with the inherited
artifact root, context path, implementation target, iteration limit, push flag,
and open PR flag. Store the implementation summary path and outcome on the
workflow root bead.

`prepare-shared-worktree` is the required predecessor. Before the first source
read, verify the current `gc.drain_member_id` source anchor has `work_dir`, that
the path is a registered git worktree distinct from the launcher checkout, and
that it matches the workflow root's `gc.shared_worktree`. Keep every item on
that same branch, commit each successful item before closing its source anchor,
and never create or select a per-item worktree. Core's `single_lane=true`
ordering is the only writer lane: do not spawn parallel implementation work.
On an item failure, preserve the worktree evidence and let
`on_item_failure=skip_remaining` close the later manifest rows; do not execute
or manually reopen skipped source anchors.

Close this step only after implementation reports a clean result or an explicit
failure artifact.
