# SayMyName legacy cutover boundary and M6 rollback

Moved from `docs/OPERATIONS.md` (O15, 2026-09-28): dead sections describing
the one-time SayMyName legacy-automation cutover and its temporary rollback
procedure. Untrusted historical record — not re-validated against current
Factory state.

## Legacy cutover boundary

The cutover occurred at `2026-09-12T16:38:00Z`. The Windows repo at
`/mnt/c/Dev/Projects/SayMyName/Automation` is not a Gas City rig. Its GitHub
repository is archived and its Scheduled Task `SayMyName-LocalCodexRunner`
remains installed but disabled. The archived repository is the reversible
write barrier for the former GitHub queue; do not unarchive it for ordinary
history access.

Preserve `.runner/state`, receipts, recovery receipts, logs and historical
worktree registrations for audit/rollback. Do not clean the dirty Windows
checkout, prune worktrees, delete the task, edit `config/runner.json`, or rotate
secrets merely as part of decommissioning.

New work procedure:

```bash
gc bd create "<bounded backend task>" --rig saymyname-backend --labels delivery:standard
gc bd create "<bounded frontend task>" --rig saymyname-frontend --labels delivery:standard
```

Create only actually ready tasks; never bulk-copy Linear Done/Todo history.

## Temporary M6 rollback

Rollback is an emergency choice, not a routine retry:

1. prove no Backend/Frontend Bead is assigned or in progress and no application
   PR has ambiguous ownership;
2. suspend both new paths with `gc rig suspend saymyname-backend` and
   `gc rig suspend saymyname-frontend`;
3. re-check that the legacy ledgers and queue contain no in-flight item;
4. unarchive `saymyname-app/Say-my-name-automation` in GitHub;
5. verify the retained task still has URI `\\SayMyName-LocalCodexRunner`, source
   `SayMyNameAutomationPhase4`, the expected script/config paths, and remains
   disabled;
6. run the legacy manager's `Status`, then `Resume` only after those proofs;
7. never resume either Gas City rig while the legacy dispatcher is enabled.

To return to the new path, pause the managed Scheduled Task first, prove its
process has exited and no queue item is in flight, archive Automation again,
then resume both rigs. Do not test rollback by enabling both systems.
