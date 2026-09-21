Release the worktree owned by a build-basic same-session implementation after
the `build-pipeline` scope reaches a terminal outcome. This is a teardown step:
run it whether the body passed or failed.

1. Read this claimed step's `gc.root_bead_id`, then resolve the implementation
   convoy from root metadata `gc.build.implementation_convoy_id` (fallback
   `gc.input_convoy_id`).
2. Run:

   ```bash
   FACTORY_ROOT="${FACTORY_ROOT:-/home/benja/agent-factory}"
   "$FACTORY_ROOT/bin/factory-shared-drain-workspace" cleanup \
     "<workflow-root-id>" "<implementation-convoy-id>"
   ```

3. A result of `removed` or `already-clean` is success. A result of
   `preserved` is also a successful safety teardown: the adapter found dirty
   recovery work and deliberately left it in place instead of deleting it.
   Record that exact path and reason in the close notes so `factory-guard` and
   a later operator can recover it.

Never remove an arbitrary directory and never use `rm -rf` as a fallback. The
adapter only removes the deterministic registered worktree and clears
`work_dir` from anchors that still point to it. Close this teardown step with
`gc.outcome=pass` after recording the adapter result.
