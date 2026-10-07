# Spec integration branch and serial merge (T18, T14, Spec af-wf4w5r §4, §6 and §8)

## Status and purpose

A convoy that carries the **new-flow mark** delivers its Spec on one
integration branch. `bin/spec-integration` opens that branch when the convoy
is published and merges the tickets into it, one at a time, with tests on
each merged result. No ticket opens a pull request toward the protected
branch, and the protected branch receives nothing: its one merge comes after
the acceptance (T30). A convoy without the mark is not touched (exit 4).

```bash
./bin/spec-integration open  af-convoy --repo <project repository> --protected main
./bin/spec-integration merge af-convoy --repo <project repository> --profile <descriptor.json> [--limit 1] [--timeout 600]
```

Who calls it: `bin/ticket-graph-publish bd-publish` calls `open` once the
convoy is marked (`docs/ENTRY_CONTRACT.md`); `bin/convoy-advance` calls
`merge --limit 1` on each of its passes for a convoy that has a finished
ticket (`docs/CONVOY_ADVANCE.md`). No agent decides when a ticket is merged.

Every answer is one JSON object on stdout.

| Exit | Meaning |
|---|---|
| 0 | done: what was merged or returned to its author is listed, possibly nothing |
| 1 | refused (`{"ok": false, "error": "refus : …"}`), or a ticket was refused (listed under `refused`) |
| 3 | the convoy is in an « état sans règle » (`bin/convoy-state show`): nothing is merged |
| 4 | the convoy does not carry the mark: « pas un convoi du nouveau flux » |

## The branches

The integration branch is `integration/<spec id>`, the Spec being the one
the convoy names (`gc.spec_id`). When the repository has a remote `origin`,
the protected and the integration branches are read there, after a fetch,
and the integration branch is pushed there; a repository without that remote
uses its local branches. A ticket branch is read as `bin/convoy-state` reads
it: the local branch first, then `origin/<branch>`.

Nothing is ever checked out in the repository itself: the merges of a pass
are made in a work tree of their own (`SPEC_INTEGRATION_WORK_DIR`, default
under `$XDG_RUNTIME_DIR` or `/tmp`), removed at the end of the pass; one left
by an interrupted pass is removed by the next. The merge commits are authored
by « Agent Factory ».

## `open`

Creates the branch at the tip of the protected branch and records it on the
convoy through `bin/convoy-state set-integration` (branch, protected branch,
commit it left from). Opening it again changes nothing. A branch of that
name that exists without being recorded is taken as it is when it holds no
commit the protected branch lacks (an `open` interrupted before its record);
otherwise it is refused: it was not opened by this command. Refused too: a
convoy that names no Spec, a protected branch the repository does not have.

## `merge`

One pass reads the convoy through `bin/convoy-state show` and takes its
tickets in the convoy's order. A ticket is **ready** when its author has
finished at the tip of its branch — Ticket Exit `finished`, and a complete
Ticket Handoff taken at that very tip — and its **code review is favorable
at that tip** (below). The other tickets are left alone;
those worth a word are listed under `waiting` with the reason (parked,
stopped, an unfavorable verdict, a verdict to replay, an author still at
work, a code review that is absent, open or unfavorable, a ticket already
returned to its author).

**No merge without a favorable code review** (T14, Spec §6,
`docs/CODE_REVIEW.md`). A finished ticket is merged only when the last
round of its code review (`code_review.state` of `bin/convoy-state show`)
is favorable, was given at the tip, no round is open, and the verdict
`code_review` is favorable and valid at the tip. A ticket with no review, a
review still running or left without output, a Blocking Finding without a
favorable verdict (named in the reason), or a favorable verdict written
without the review it comes from, stays under `waiting`: nothing of it is
merged, nothing is written.

Passes on one convoy are serialised by a lock (`SPEC_INTEGRATION_LOCK_DIR`):
two merges are never made at once, and each merge is made on the result of
the one before. `--limit N` merges at most N tickets in the pass.

For the ready tickets, in order:

1. **The integration branch takes up the protected branch**, once per pass,
   when it does not already hold its tip. The takeover is a merge commit of
   its own, tested by the same command, and pushed before any ticket is
   merged. A takeover in conflict, or red, is refused for the whole pass: no
   ticket is merged, nothing is pushed, no ticket is blamed.
2. **The ticket is merged** (`git merge --no-ff`) on the current tip.
3. **The tests run on the merged result**: the `regression_command` of the
   project's profile (`--profile`, `docs/PROJECT_PLANNING_PROFILE.md`), run
   from the root of the work tree by `bin/evidence-capture command`. The
   record is the piece `merged_tests` of the ticket, tied to the commit of
   the merged result (`docs/EVIDENCE_STORE.md`).
4. **Green**: the integration branch moves to the merged result, and only
   from the tip the merge was made on. The ticket carries `merge.outcome:
   merged` with that commit.

| Outcome | What is written | What happens to the branches |
|---|---|---|
| `merged` | `merge` on the ticket (`merged`, ticket tip, integration tip before, commit of the result), piece `merged_tests` at that commit | the integration branch moves to the result |
| `returned`, cause `conflict` | `merge` (`conflict`, ticket tip, integration tip) | nothing: the merge is aborted, the conflicting files are named in the answer |
| `returned`, cause `red` | `merge` (`red`, ticket tip, integration tip, commit of the tested result), piece `merged_tests` with its non-zero exit code | nothing is pushed: the integration branch stays on its green tip |
| `refused` | the outdated verdicts are marked invalid, one resume is counted | nothing |

**Returned to its author.** A conflict or a red belongs to the ticket being
merged. Nothing here resolves a conflict or repairs a test: the ticket waits
for a new commit of its author, who takes up the integration tip in a fresh
session. It is not tried again until its tip has changed and its author has
finished again at the new tip.

**A commit added after a verdict** (Spec §8). When the branch of a ticket
has a commit newer than the commit its code review or its Ticket Evaluation
judged, the merge of that ticket is refused: `bin/convoy-state
invalidate-verdicts` marks each outdated verdict invalid, with the tip that
outdated it, and counts one resume (K) — not the correction round — in the
same tracker write. The next passes count nothing more and list the ticket
under `waiting` until the verdicts are replayed on the new tip
(`set-verdict` writes a fresh one). A verdict that is merely unfavorable
merges nothing and invalidates nothing.

A profile without `regression_command` is refused when a ticket is ready: no
test, no merge. A pass with no ready ticket does not read the profile.

## Limits

- **Of the conditions of the ticket-end gate, only the code review is
  required here** (condition 9, without Benjamin's recorded override, which
  is T17's). A ticket with no Ticket Evaluation recorded is merged once it
  is reviewed; a recorded evaluation verdict must be favorable and valid.
  The ticket-end gate (T19) makes the merge command refuse while its
  conditions 1 to 5, 7 and 8 are not met.
- **Starting the fresh author session of a returned ticket is not in this
  command.** The return is recorded (`merge` on the ticket, listed by the
  pass); resuming a ticket is T20's, and the start formula is T12's (`docs/TICKET_AUTHOR.md`).
- **The tests on a merged result are the profile's regression command**, the
  one whole-suite command a profile declares. The frozen criterion tests of
  the merged tickets are replayed only as far as that command runs them.
- **One repository per convoy.** The publication door refuses a new-flow
  graph that targets several rigs.
- A red integration branch does not stop the convoy yet, and no `repair` is
  created for a red takeover (T21).
- A frozen harness file changed on the integration branch by another
  ticket's merge is still seen by `bin/tdd-step green` as modified
  (`docs/TDD_STEP.md`, Limits) when an author takes up the integration tip.
- The order that runs `bin/convoy-advance` has a 300 s timeout; a test run
  on a merged result may take up to `--timeout` (600 s). A pass killed by
  the controller has pushed nothing; its work tree is removed by the next.

## Proof

`tests/spec-integration-test.py` drives the command lines on a fake tracker
state, against a copy of the Delivery Fixture City in a throwaway repository
with its own remote; the tests on a merged result are run and sealed by the
real `bin/evidence-capture`. One test per pass and per refusal, each refusal
re-reading the tracker, the evidence store and every branch of the remote.
`tests/ticket-graph-publish-integration-branch-test.py` covers the
publication door, `tests/convoy-advance-test.py` the pass that merges,
`tests/convoy-state-test.py` the three records. On the real `gc`/`bd`, in a
disposable city (local-only): `tests/spec-integration-demonstration-test.sh`
(the demonstration line), `tests/convoy-state-real-tracker-test.sh` and
`tests/ticket-graph-publish-new-flow-real-tracker-test.sh`.
