Prepare the repository lifecycle that Gas City's core shared drain deliberately
does not own. This is infrastructure setup only; do not read or edit product
source in this step.

1. Read this claimed step's `gc.root_bead_id`, then read the workflow root.
2. Resolve the implementation convoy from root metadata
   `gc.build.implementation_convoy_id` (fallback `gc.input_convoy_id`). Both
   values must agree when both are present.
3. Run the deterministic Factory adapter:

   ```bash
   FACTORY_ROOT="${FACTORY_ROOT:-/home/benja/agent-factory}"
   "$FACTORY_ROOT/bin/factory-shared-drain-workspace" prepare \
     "<workflow-root-id>" "<implementation-convoy-id>"
   ```

4. Verify the adapter reports `status=prepared`, the path is an absolute
   registered git worktree distinct from the launcher checkout, and every
   source anchor in the convoy has that exact same `work_dir`. Verify the root
   records `gc.work_branch` and `gc.work_base_branch`.

Do not create a worktree per item and do not set `work_dir` on a synthetic
drain-unit convoy. If preparation fails, close this step with `gc.outcome=fail`;
the enclosing `build-pipeline` scope will skip the drain and every later stage.
Close with `gc.outcome=pass` only after all source anchors resolve the shared
path. The following `implement-same-session` step is not eligible before this
step closes successfully.
