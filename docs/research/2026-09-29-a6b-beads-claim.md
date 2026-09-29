# Research: concurrent claims and map updates in Beads (A6b, af-0aiero.2)

Date: 2026-09-29. Ticket: `af-0aiero.2` (map `af-0aiero`, "A6b — wire the upstream wayfinder into the Planning Run").

## Question

With the Factory's `bd` 1.2.2, what happens when two operator sessions claim the same planning bead at the
same time, using `bd update <id> --assignee <x>` or `bd update <id> --claim`? Does the actor name matter?
What does upstream `wayfinder` expect, and what does upstream issue #476 say? Is there a lost-update risk
when two sessions rewrite the map's "Decisions so far" with `bd update --body-file`, and does `bd` offer an
append or a compare-and-set?

## Answer (short)

| Write used as the claim | Two different actors | Same actor (e.g. both `po-agent`) |
|---|---|---|
| `bd update <id> --claim` | **Second is rejected**: `Error claiming <id>: issue already claimed by <first>`, exit 1. Holds when both fire in parallel. | **Both succeed** (exit 0). The claim is idempotent per actor, so it cannot tell two sessions apart. |
| `bd update <id> --assignee <x> [--status in_progress]` | **Last writer wins silently** (exit 0 for both, assignee = second). | Both succeed; nothing to detect. |

- Map body (`--body-file` / `--description`): a full-field replace, **last writer wins silently**. No
  compare-and-set, no version check, no `--append-description` in 1.2.2.
- Append-style writes that exist: `bd comments add` (one INSERT per comment, cannot collide) and
  `--append-notes` / `bd note` (append to the *notes* field, but computed read-then-write in the CLI, so a
  small race window remains).
- Consequence for the Factory: claim with `--claim` **and** a per-session actor; record map decisions as
  append-only writes (comments), not by rewriting the description.

## Sources and version

- Installed binary: `bd version` -> `bd version 1.2.2 (6c124203e: HEAD@6c124203e771)`, `/usr/local/bin/bd`.
- Source: https://github.com/steveyegge/beads, commit `6c124203e771433a3550c348771a5b5e27fd3c21`
  (tag `v1.2.2`, "chore(release): bump version to 1.2.2", 2026-08-15). All file/line references below are
  at this commit.
- Factory backend: `bd context` -> `type: dolt`, `mode: server`, `database: hq`, `server: 127.0.0.1:44632`;
  `bd config get dolt.auto-commit` -> `on`.
- Upstream wayfinder: `mattpocock/skills` clone at `c55ee46073ed923f86ce59a5eb3b6d895095d1b7`
  (2026-09-18), file `skills/engineering/wayfinder/SKILL.md`.
- Upstream issue: https://github.com/mattpocock/skills/issues/476 (read with `gh issue view 476 -R mattpocock/skills`).

## 1. `bd update --claim` is a real compare-and-set

`internal/storage/issueops/claim.go`, `ClaimIssueInTx` (lines 21-109):

- One conditional SQL statement (lines 50-60):
  `UPDATE issues SET assignee = ?, status = 'in_progress', ... WHERE id = ? AND status = 'open' AND (assignee = '' OR assignee IS NULL OR assignee = ?)`.
  The database decides; there is no application-side read-then-write gap.
- If 0 rows changed (lines 71-93):
  - current assignee == actor and status `in_progress` -> **success, no-op** (comment lines 84-86:
    idempotent, "supports agent retry workflows");
  - another assignee -> `storage.ErrAlreadyClaimed` ("issue already claimed by X");
  - otherwise (e.g. `in_progress` with no assignee, `blocked`, `closed`) -> `storage.ErrNotClaimable`.
- On success a `claimed` event is recorded (line 104). `DoltStore.ClaimIssue`
  (`internal/storage/dolt/issues.go`, around lines 204-241) wraps it in one SQL transaction plus `DOLT_COMMIT`.
- CLI: `cmd/bd/update.go` lines 371-378 print `Error claiming <id>: <err>` and skip the issue; when no issue
  was updated the command returns `SilentExit()`, exit code 1 (`cmd/bd/errors.go` lines 119-120). The
  proxied-server path behaves the same through the domain layer (`internal/storage/domain/issue.go`
  lines 377-405; `cmd/bd/update_proxied_server.go` lines 92-97 and `os.Exit(1)`).

Note: `--claim` only succeeds from `status = open`. A bead already moved to `in_progress` by a plain
`--status` write can no longer be claimed by anyone else (T3b below).

## 2. `--assignee`, `--status`, `--body-file` are unconditional writes

- `cmd/bd/update.go` lines 107-119 put `assignee` / `description` into a plain update map, applied by
  `issueStore.UpdateIssue` (line 423).
- `internal/storage/issueops/update.go` line 221: `UPDATE %s SET %s WHERE id = ?`, with no condition on the
  previous value and no version or `updated_at` check.
- `bd update --help` lists no if-match / expected-version flag; the only append flag is `--append-notes`
  ("Append to existing notes (with newline separator)").
- `--append-notes` and `bd note` (`cmd/bd/note.go`: "Shorthand for 'bd update <id> --append-notes'") build
  `existing notes + newline + new` **in the CLI** from the issue read at the start of the command
  (`cmd/bd/update.go` lines 413-420; `cmd/bd/update_proxied_server.go` lines 161-167), then write the whole
  field. A concurrent append landing between that read and the write can be lost.
- `bd comments add` inserts a new row (`internal/storage/issueops/comment*.go`,
  `INSERT INTO ... (id, issue_id, author, text, created_at)`): appends cannot collide.

## 3. Experiment on the live HQ database

Six throwaway beads created by `po-agent` with `--metadata '{"gc.plane":"planning"}'`, titles
"TEST a6b claim race ...", ids `af-sufs4e af-9d3rn5 af-ze9a2a af-8g23l6 af-l43vex af-9hrckz`; all closed
afterwards with reason "research experiment". Run from `/home/benja/agent-factory` on 2026-09-29.

| Test | Commands | Observed |
|---|---|---|
| T1 `--claim`, different actors, sequential | `bd --actor sessA update A --claim`, then `bd --actor sessB update A --claim` | exit 0, then exit 1 with `Error claiming af-sufs4e: issue already claimed by sessA`; final assignee `sessA` |
| T2 `--claim`, same actor twice | `bd --actor po-agent update B --claim` x2 | exit 0 and exit 0, both print `Updated issue` |
| T3 plain `--assignee` as first write | `--assignee sessA --status in_progress`, then `--assignee sessB --status in_progress` | both exit 0; final assignee `sessB` (sessA silently overwritten) |
| T3b `--claim` after T3 | `bd --actor sessC update C --claim` | exit 1, `issue already claimed by sessB` |
| T4 `--claim` fired in parallel | two background `--claim` (raceA, raceB) | raceA exit 0; raceB exit 1 `issue already claimed by raceA`; final `raceA` |
| T5 description read-modify-write | both sessions read "Decisions so far:", each adds its own line, writes with `--body-file` | both exit 0; final description holds only `- decision from session 2` (session 1's line lost, no error) |
| T6 8 parallel `--append-notes` | 8 background `bd update E --append-notes note-i` | 8 of 8 kept in this run (race window exists in code, not hit) |
| T7 8 parallel `comments add` | 8 background `bd comments add F comment-i` | 8 of 8 kept |

## 4. Upstream wayfinder expectation

`skills/engineering/wayfinder/SKILL.md` at `c55ee46`:

- Line 67: a session claims a ticket by assigning it to the dev driving the map, first, before any work,
  so concurrent sessions skip it; the assignee *is* the claim.
- Line 69: the frontier is the open, unblocked, **unclaimed** children.
- Line 123: "Claim it: assign it to yourself before any work."
- Line 128: expect other sessions to be editing the tracker concurrently.
- Line 105: never resolve more than one ticket per session, except research tickets.
- Tracker docs define the claim as a single assign write: GitHub `gh issue edit <n> --add-assignee @me`,
  "the session's first write" (`setup-matt-pocock-skills/issue-tracker-github.md` line 44); GitLab
  `glab issue update <n> --assignee @me` (`issue-tracker-gitlab.md` line 45); local `Status: claimed`
  (`issue-tracker-local.md` line 29).
- No lock, no re-verify step, no rule for map-body concurrency: step 4 says to append a context pointer to
  the map's Decisions-so-far without saying how.

## 5. Upstream issue #476 (verified)

https://github.com/mattpocock/skills/issues/476, titled "wayfinder: claim protocol fails under concurrent
sessions (double-resolution + map lost-update), and one-ticket-per-session is easy to violate". Author
`mattiasthalen`, opened 2026-07-08 21:46 (Paris), state **OPEN**, one comment (`xg-gh-25`,
2026-07-09 04:13 Paris). Summary:

- **Failure 1, double resolution.** In a real multi-session run on a GitHub tracker, two sessions resolved
  the same research ticket, posting resolutions one second apart. One session ran as a bot identity that
  never showed an assignee; and sessions driven by one human all assign the *same* user, so a session
  cannot tell its own claim from another's. The skill has a read-to-claim window and a long
  claim-to-resolve window with no re-check.
- **Collateral, map lost update.** Decisions-so-far is kept by rewriting the whole map body; a session
  rewrote it from a stale snapshot and erased another session's fresh decision line, unnoticed until a
  human looked.
- **Reporter's fixes:** claim = assignee plus a claim comment carrying a session id; re-fetch and verify
  before posting a resolution; for the map, re-fetch before each edit, touch only your own lines, re-read
  after, or move Decisions-so-far to per-decision comments on the map.
- **Failure 2:** after resolving one ticket, a session claimed the next on an ambiguous follow-up; the
  reporter proposes an explicit "session is spent" terminal step.
- The commenter frames both as missing compare-and-set / optimistic locking and notes GitHub issues have
  no conditional writes.
- The skill at `c55ee46` (2026-09-18) does not contain these fixes (grep finds no re-fetch/verify or
  "spent" rule), so the issue is unaddressed upstream as of that commit.

## 6. Consequences for the Factory

1. **Claim with `bd update <id> --claim`, never with `--assignee`.** Beads provides the atomic claim that
   GitHub lacks (what the #476 commenter asks for). Treat exit 1 / "already claimed" as "skip, take another
   ticket"; never fall back to `--assignee`.
2. **One actor per session**, e.g. `--actor po-agent/<session-id>` (or `BEADS_ACTOR`). With a shared
   `po-agent`, `--claim` succeeds for every session (T2): the same-user ambiguity #476 describes.
3. **Do not set `--status in_progress` without `--claim`**: it leaves a bead no one can `--claim`
   (ErrNotClaimable) and gives no reliable owner.
4. **Map "Decisions so far": no concurrent description rewrites.** `--body-file` is last-writer-wins with no
   error (T5). Options, safest first: (a) one decision = one `bd comments add <map>` (append-only, T7), the
   description rebuilt from comments by a single writer; (b) serialise map-body edits through one owner
   (the Planning Run orchestrator); (c) at minimum re-read just before writing and re-read after to detect a
   clobber (narrows the window, does not close it).
5. `--append-notes` / `bd note` are append-shaped but not atomic: fine under low contention, not a lock.

## UNVERIFIED

- Whether Dolt's transaction merge would raise a conflict (instead of a silent overwrite) if two
  `UpdateIssue` transactions on the same cell overlapped exactly in time. The CLI reads before opening its
  write transaction, so the practical outcome is last-writer-wins (T5); the exact-overlap case was not
  tested nor checked against Dolt docs.
- `bd merge-slot` ("Manage merge-slot gates for serialized conflict resolution") and `bd batch` ("Run
  multiple write operations in a single database transaction"), both from `bd --help`, might serve as a
  map-edit lock; not investigated.
- The `--append-notes` lost update is inferred from code; not reproduced (8/8 kept in T6).
