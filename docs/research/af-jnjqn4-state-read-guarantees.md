# What the per-call re-read of the convoy state and the locks guarantee today

Research for Planning Decision Bead af-jnjqn4.2 (map af-jnjqn4, « Les outils du
flux de livraison lisent l'état sans relancer de commandes »), 2026-10-09.

Question: what do the per-call re-read of the state and the locks guarantee
today, that a library call (a tool reading the state in its own process
through `lib/convoy_state.py` instead of starting `bin/convoy-state`) would
have to keep for behaviour to stay identical?

Facts only. No design is proposed and nothing here says go or stop: that is
af-jnjqn4.3. Every line number is read on tree `889e854` (origin/main,
2026-10-09). Nothing was run except one 15-line Python check of two standard
library behaviours, in `/tmp` (section 10). "Kept free / kept at a cost / lost"
is said for one case only: a tool that calls the module in its own process
for a **read**; where the answer differs for an in-process **write**, it is
said apart.

## Summary

| # | Guarantee today | Evidence | In-process read |
|---|---|---|---|
| G1 | Every write on a convoy is one read-validate-write under an exclusive lock per convoy; the read is made after the lock is taken | `lib/convoy_state.py:516-529`, `:5989-5995`, `:2953-2957`; `docs/CONVOY_STATE.md:772-774`; `tests/convoy-state-test.py:285-293` | Kept free (a read never took it). For an in-process write: kept at a cost (section 1) |
| G2 | A read takes no lock and never waits for a writer | `lib/convoy_state.py:5992-5993` | Kept free |
| G3 | Each `show` is a new tracker read and a new Git read: nothing is carried from one call to the next | `lib/convoy_state.py:2753-2754`, `:468-470`, `:2899-2900`, `:2454-2459` | Kept free if the function is called again at each site; lost at any site where a kept object replaces the call |
| G4 | One pass at a time Factory-wide for the count of free places and the starts; the state is read after the lock is taken | `bin/convoy-advance:1612-1622`, `:1871-1889`; `docs/CONVOY_ADVANCE.md:73-77` | Kept free (the lock is in the tool, not in the state command) |
| G5 | Each handed-over tool decides under its own lock, from a state it reads after taking that lock | section 3 | Kept free if the read stays inside the lock, in the tool |
| G6 | A pass decides the rest from what it wrote (17 re-reads) | `bin/convoy-advance:363-365` and section 4 | Kept free if each site still reads; each is a deliberate read, not a side effect of starting a command |
| G7 | No script but the state command reads or writes a `gc.flow.*` key | `docs/CONVOY_STATE.md:5-10`; `lib/convoy_state.py:4-6`, `:40-41` | Kept free in substance (same code), at a cost in the written contract: three documents and two test headers name the command |
| G8 | Settings and the tracker binary are read anew at each command start | `lib/convoy_state.py:167`, `:540-562` | Kept at a cost: frozen for the life of the calling process instead of one command (section 6) |
| G9 | The state command finds the city from its working directory | `lib/convoy_state.py:459`, `:470`; `bin/dispatch-door:164-167`; `bin/convoy-advance:294-296` | Kept at a cost: the caller's own working directory decides |
| G10 | The answer is one JSON object on the child's stdout and an exit status 0/1/3/4; a crash of the state code is an unreadable answer for the caller, never an exception in it | `lib/convoy_state.py:116-121`, `:5996-6004`; `bin/convoy-advance:301-306`, `:377-382` | Kept at a cost: no function returns the state (section 8); the exception classes are not the callers' |
| G11 | A test of a tool is a test of its command line on a fake tracker state | Spec af-wf4w5r, Testing Decisions, seam 2; `tests/convoy-state-test.py:2-5`; `tests/convoy-advance-test.py:8` | Kept free for the tools' own command lines; the fake tracker is reached through `GC_BIN`, read at import (section 9) |

## 1. The convoy lock (G1, G2)

**What the code does.** `convoy_lock` (`lib/convoy_state.py:516-529`) opens
`agent-factory-convoy-state-<convoy>.lock` in `CONVOY_STATE_LOCK_DIR`, else
`XDG_RUNTIME_DIR`, else `/tmp` (`:521`, read at each call, not at import) and
takes `fcntl.flock(..., LOCK_EX)` on it (`:525`), blocking, with no timeout;
it releases it in a `finally` (`:529`). Its docstring: "Serialise every
read-validate-write on one convoy: a counter bump is a read-modify-write, and
a reviewer and an Evaluator write the same ticket in parallel" (`:518-520`).

It has one call site: `main` (`:5989-5995`). `list`, `show` and `ticket`
return before it (`:5992-5993`); every other handler runs inside it (`:5994-5995`).
So the lock is taken by every write and by no read, and it is held by the
`convoy-state` child for the length of one handler, never by the tool that
started the child.

Inside the lock each write handler reads the convoy again before it
validates: e.g. `marked_ticket` calls `load_convoy` (`:2953-2957`), and
`load_convoy` is one `gc bd show <convoy> --json` (`:468-470`). The comment
at `:5790-5792` says the refusals themselves are made there: "a refusal is one
JSON answer, and it is made under the lock, after the mark has been read".
`docs/CONVOY_STATE.md:198` relies on it for the TDD steps: "The order of the
steps is held here, under the lock".

**What it protects against.** Two processes that write the same convoy at
once: a reviewer session running `bin/code-review record` and an Evaluator
session running `bin/ticket-evaluation record` on the same ticket, or two
`bump-counter` on the same counter. Without the lock both read the counter at
2 and both write 3. `tests/convoy-state-test.py:285-293` proves it: eight
`bump-counter` commands in parallel, the counter reads 8.
`docs/CONVOY_STATE.md:772-774` states it.

**What it does not protect.** A reader is never excluded (G2): `show` can
run between two tracker writes of one handler. Several handlers make more than
one tracker write (`lift-park`: `:4326` then `:4328`), so a read can see the
first without the second. This is today's behaviour, not a loss.

**In-process.**

- *Read*: kept free. A read never took the lock, so reading in the tool's
  process changes nothing to it, and G2 (a read never waits) is kept too.
- *Write* (only if the scope goes that far; the map leaves it open): kept at
  a cost. Three facts bear on that cost:
  1. The lock is taken in `main` only (`:5994`), not in the handlers. A
     caller that reached a `cmd_*` handler without going through `main` would
     write with no lock.
  2. The handler must still make its own read after the lock is taken. A
     write validated against a state the tool read earlier (to save a read)
     is no longer a read-validate-write under the lock: the 2-then-3 scenario
     above comes back.
  3. `flock` is tied to the open file, and `convoy_lock` opens the file anew
     at each call (`:524`): a second `convoy_lock` on the same convoy in the
     same process waits for the first for ever. Checked on this host
     (section 10). Today no such nesting can happen: the lock has one call
     site and each holder is its own process.
- The time the lock is held does not change: one handler.

## 2. The Factory-wide advance lock, and what runs outside it (G4)

**What the code does.** `advance_lock` (`bin/convoy-advance:1612-1622`): one
file `agent-factory-convoy-advance.lock` in `CONVOY_ADVANCE_LOCK_DIR`, else
`XDG_RUNTIME_DIR`, else `/tmp`; `LOCK_EX`, blocking. Docstring: "One pass at a
time, Factory-wide: N is shared between the convoys" (`:1614`).

Inside it (`one_pass`, `:1873-1889`): the first read of every convoy
(`Convoy(...)`, `:1874`, `:1878`), the settings (`:1875`), the list of marked
convoys (`:1876`), the live sessions and the count of free places
(`:1879-1883`), then `advance_convoy` for each convoy (`:1886-1889`), which
holds: the incident (`:1635`), the repair of a red (`:1646`), the item and
outcome repairs (`:1652`, `:1656`), the lifts (`:1661`), the resumes (`:1672`),
the starts through `bin/dispatch-door` (`:1699`), the grouped request
(`:1708`). Nine of the 17 re-reads of section 4 are in functions called here
(873, 890, 895, 899, 950, 1218, 1363, 1390, 1707); the eight others run
outside the lock (1280, 1293, 1302, 1427, 1513, 1518, 1585, 1602).

Outside it (`:1891-1957`), per convoy, in this order: `settle_test_reviews`
(`:1898`), `settle_code_reviews` (`:1901`), `settle_evaluations` (`:1904`),
`settle_corrections` (`:1909`), `check_fidelity` (`:1914`), `merge_finished`
(`:1917`), `settle_ticket_end` (`:1921`), `settle_spec_end` (`:1926`),
`settle_outcome_evaluation` (`:1931`), `settle_end_review` (`:1936`),
`settle_evidence_pack` (`:1941`, then `settle_spec_end` again `:1945`),
`settle_non_conforme` (`:1948`), `settle_acceptance` (`:1955`). The comment at
`:1891-1892` gives the reason: "the tests on a merged result take the time
they take, and bin/spec-integration holds its own lock per convoy".

**What it protects against.** Two passes at once (the order's tick while a
pass started by hand or by the previous tick still runs): both read 1 free
place under N and both start a ticket, 2 sessions for 1 place.
`docs/CONVOY_ADVANCE.md:73-77`: "Passes are serialised Factory-wide by a lock
[...] so two of them never count the same free place". The second pass waits,
then builds its `Convoy` objects after it holds the lock (`:1873-1874`): it
counts from the state the first one left, where "a started ticket carries its
`dispatch` gate record" (`docs/CONVOY_ADVANCE.md:73-75`).

**What it does not protect.** Everything from `:1893` on. Two passes can be in
that second half at once, on the same convoy. What keeps them apart there is
the lock of each handed-over tool (section 3), not this one.

**A fact about the second half.** From `:1898` to `:1921` the pass asks
"is a settlement worth running?" (`test_reviews_due`, `code_reviews_due`,
`evaluations_due`, `corrections_due`, `fidelity_due`, `finished_unmerged`,
`merged_open`; `:430-558`) on the `Convoy` object as the first half left it:
there is no `convoy.load()` between those seven steps, although each of the
tools they start may write. The object is a filter only; the tool it hands
over to reads the convoy itself. The first re-read of the second half is
`:1427`, and only if this pass closed a ticket.

**In-process.** Kept free. The lock is taken by `bin/convoy-advance` itself,
around code of its own; whether that code reads the state by a child or by a
call does not touch it.

## 3. The per-tool launch, merge and gate locks (G5)

| Tool | Lock | Key | Directory | Held around | First act inside |
|---|---|---|---|---|---|
| `bin/test-review` | `ticket_lock` `:346-357` | ticket | `CONVOY_STATE_LOCK_DIR` | `settle_ticket` `:479` | `ticket_of(...)`: reads the convoy `:480` (`show` at `:224`) |
| `bin/code-review` | `ticket_lock` `:527-537` | ticket | `CONVOY_STATE_LOCK_DIR` | `settle_ticket` `:660` | `convoy.load()` `:661` |
| `bin/ticket-evaluation` | `ticket_lock` `:563-573` | ticket | `CONVOY_STATE_LOCK_DIR` | `settle_ticket` `:741` | `convoy.load()` `:742` |
| `bin/correction-round` | `ticket_lock` `:369-379` | ticket | `CONVOY_STATE_LOCK_DIR` | `settle_ticket` `:473` | `convoy.load()` `:474` |
| `bin/spec-integration` | `integration_lock` `:308-317` | convoy | `SPEC_INTEGRATION_LOCK_DIR` | `cmd_merge` `:701`, `cmd_take_up` `:819` | `read_state` `:702`, again after the fetch `:709` ("Read again once the remote is fetched: the tips are the current ones", `:708`) |
| `bin/spec-end` | `gate_lock` `:733-743` | convoy | `SPEC_END_LOCK_DIR` | `cmd_run` `:820` | `read_state` `:821` |
| `bin/outcome-evaluation` | `convoy_lock` `:496-506` | convoy | `CONVOY_STATE_LOCK_DIR` | `cmd_settle` `:707` | `convoy.load()` `:708` |
| `bin/spec-end-review` | `review_lock` `:417-427` | convoy | `CONVOY_STATE_LOCK_DIR` | `settle` `:590` | `convoy.load()` `:591` |

Each is a file of its own name (`agent-factory-<tool>-<id>.lock`): none is the
convoy-state lock, even where the directory variable is the same. All are
`flock(LOCK_EX)`, blocking, without timeout.

No `flock` was found in `bin/ticket-end`, `bin/evidence-pack`,
`bin/ticket-exit`, `bin/tdd-step`, `bin/ticket-author`,
`bin/prototype-fidelity`, `bin/evidence-capture`, `bin/acceptance-session`,
`bin/dispatch-door`, `bin/ticket-graph-publish`,
`bin/planning-artifacts-close`, `bin/deliver-close`. `bin/ticket-end settle`
reads the convoy once (`:602`) and has no lock of its own; what is exclusive
in it is the `close-ticket` write, under the convoy lock (G1).

**What they protect against.** Their docstrings: "One decision at a time on
the review of a ticket: the author's `review` and the pass of
bin/convoy-advance never launch it twice" (`bin/test-review:347-348`); "One
merge at a time on the integration branch of a convoy"
(`bin/spec-integration:309`); "One run of the gate at a time on a convoy"
(`bin/spec-end:734`). Scenario: two passes in their second half (section 2), or
a pass and an agent session, both run `code-review settle` on a ticket whose
review is not sent yet. Without the lock both read "no launch" and both send a
reviewer session. With it, the second waits, then reads the launch the first
one recorded and does nothing: "A second call on the same state does nothing"
(`bin/code-review:658-659`, same sentence in `bin/test-review:478`,
`bin/ticket-evaluation:739-740`, `bin/correction-round:471-472`,
`bin/spec-end-review:589`).

**The guarantee is the pair**: the lock, and the read made *after* it is
taken. Every row of the table reads the convoy as its first act inside the
lock. `bin/outcome-evaluation` shows it most plainly: it builds its `Convoy`
(a first read) at `:703`, before the lock, then reads again at `:708` once
inside.

**In-process.** Kept free for a read: the lock and the read after it are both
in the tool, and the read takes no lock. What it costs is only the rule that
the read stays where it is, inside the lock: a state handed in by the caller
(the pass giving its `Convoy` object to the tool to save the tool's read) is a
state read before the lock was taken, and the two-reviewers scenario comes
back. That would be a change of scope the map has not decided (« How far
"in-process" goes »).

Not verified: the whole graph of which tool lock is held while which other is
taken. The tools start one another (`bin/spec-end` starts
`bin/spec-integration`, `bin/outcome-evaluation`, `bin/evidence-pack`;
`bin/outcome-evaluation` and `bin/evidence-pack` start `bin/spec-end`;
`bin/spec-integration` starts `bin/ticket-end`), each as a command; which
subcommand, and under which lock, was not traced.

## 4. `Convoy.load` in `bin/convoy-advance`: the constructor and the 17 re-reads (G6)

**What one load is** (`:363-413`). Two tracker reads that are not the same
snapshot: `read_bead(convoy_id)`, a `gc --city ROOT bd show` in the pass's
own process, for the tracked tickets and each one's rig (`:367-371`); then
`convoy-state show <convoy> --repo <repo>` as a child (`:377`), which makes
its own `gc bd show` (`lib/convoy_state.py:2754`, `:470`) and reads Git for
each ticket (`:2899-2900`). `self.rigs` comes from the first, `self.tickets`
from the second. Docstring: "Read the convoy again: a pass that parked, lifted
or resumed decides the rest from what it wrote" (`:364-365`).

**First reads**: `Convoy.__init__` (`:359-361`), called at `:1874` (the convoy
named on the command line) and `:1878` (each marked convoy), both under the
advance lock.

**The 17 re-reads** (`convoy.load()`), counted on the file: lines 873, 890,
895, 899, 950, 1218, 1280, 1293, 1302, 1363, 1390, 1427, 1513, 1518, 1585,
1602, 1707. "Own write": a `convoy-state` write the pass itself started
(`state_write`, `:764-770`). "Handed-over": a write made by another tool the
pass started.

| Line | In | Follows | Class |
|---|---|---|---|
| 873 | `settle_resumes` | `park` (`:856`, via `park_exhausted` `:872`) | own write |
| 890 | `settle_resumes` | `open-resume` (`:889`); the next line reads `resumes_left` from it (`:891-892`) | own write |
| 895 | `settle_resumes` | `park` (`:894`) | own write |
| 899 | `settle_resumes` | `launch_resume` (`:897`): `bin/dispatch-door` routes the resume bead (`:841-844`), then `launch-resume` (`:850`) | own write, after a handed-over tool |
| 950 | `settle_lifts` | `lift-park` for each lift (`:945`). Runs whenever `lifts` is not empty (`:949`), also when every lift was refused (`:947-948`) | own write; nothing when all were refused |
| 1218 | `settle_red` | `bin/ticket-graph-publish bd-patch` adds the repair to the convoy (`:1194`, via `:1216`), then `set-integration-repair` (`:1217`) | handed-over, then own write |
| 1280 | `settle_acceptance`, first line of its `try`, unconditional | nothing of this function. The read before it is `:1585` (unconditional) or `:1602`; between them and `:1280` the pass writes nothing, unless `settle_non_conforme` raised after `bin/evidence-pack generate` had written (`:1591-1601`, caught at `:1603`) | nothing (handed-over in that one failure path) |
| 1293 | `settle_acceptance` | `bin/escalation-door` (`:1291`), then `acceptance-requested` (`:1292`) | own write |
| 1302 | `settle_acceptance` | patch door (`:1299`), then `set-acceptance-repair` (`:1301`) | handed-over, then own write |
| 1363 | `settle_item_repairs` | patch door (`:1354`) and `set-item-repair` (`:1358`), if one succeeded (`:1362`) | handed-over, then own write |
| 1390 | `settle_outcome_repairs` | patch door (`:1383`) and `set-outcome-repair` (`:1385`), if one succeeded (`:1389`) | handed-over, then own write |
| 1427 | `settle_spec_end` | `bin/ticket-end settle` closed a ticket in this pass (`:1426`; comment "what this pass closed"). First re-read after the seven hand-overs of `:1898-1921` | handed-over |
| 1513 | `settle_end_review` | `bin/spec-end-review settle` (`:1493`) returned repairs due; comment `:1510-1512`: what it recorded "may have stopped the rounds of the end". Also the first read after `bin/spec-end run` (`:1433`) and `bin/outcome-evaluation settle` (`:1407`) | handed-over |
| 1518 | `settle_end_review` | `publish_end_review_repairs` (`:1516`): patch door (`:1461`) and `set-end-review-repair` (`:1467`, `:1473`), if one succeeded (`:1517`) | handed-over, then own write |
| 1585 | `settle_non_conforme`, first line of its `try`, unconditional | whatever `bin/spec-end run`, `bin/outcome-evaluation settle`, `bin/spec-end-review settle`, `bin/evidence-pack generate` wrote in this pass; nothing when none ran | handed-over, or nothing |
| 1602 | `settle_non_conforme` | `bin/evidence-pack generate` (`:1591`), `bin/escalation-door` (`:1600`), `end-stop-raised` (`:1601`) | handed-over, then own write |
| 1707 | `advance_convoy` | runs if the pass started, resumed, parked or lifted (`:1706`). A start is `bin/dispatch-door --convoy` (`:1699`), which records the `dispatch` gate (`bin/dispatch-door:393-395`). Resumes, parkings and lifts were each re-read already (873-950) | handed-over (starts); nothing new otherwise |

Count by class: 5 follow an own write alone (873, 890, 895, 950, 1293); 7
follow a handed-over tool and then an own write (899, 1218, 1302, 1363, 1390,
1518, 1602); 4 follow a handed-over tool alone (1427, 1513, 1585, 1707); 1
follows nothing in the normal path (1280). Two of them (950, 1707) and 1585
also run in cases where nothing was written since the last read.

**What each protects against.** Not another process: the pass's own next
decision. Line 890 is the plainest: the pass opens a resume, reads again, and
parks the ticket if that resume was its last (`:891-896`); from the object
read before, `resumes_left` would still say 1 and the ticket would be sent a
fourth time. Line 1513: the review just recorded may have stopped the rounds
of the end, and then no repair is published (`:1514-1515`).

They also catch, as a side effect, what any other process wrote meanwhile (an
agent session's `ticket-exit`, the operator's answer). No comment in the file
claims that as a purpose.

**In-process.** Kept free, on one condition that is a fact about the code:
the re-read is an explicit call in the pass (`convoy.load()`), not a
consequence of starting a command. Replacing the child by a call leaves the 17
sites as they are. What a library makes *possible*, and the command made
expensive enough to avoid, is to keep one loaded state across those sites;
each site where that happened would lose the guarantee of its row.

The two-snapshot shape of a load (`read_bead` then `show`) is today's
behaviour; a single read for both would be a different behaviour (a ticket
added between the two reads is today seen by `show` and absent from `rigs`).

## 5. "The only reader and writer", and why each handed-over tool re-reads (G7)

**The rule.** `docs/CONVOY_STATE.md:5-10`: "`bin/convoy-state` is the only
reader and writer of the durable state of a convoy that carries the new-flow
mark. The state lives in the tracker (bead metadata under `gc.flow.*`), never
in a session. Every other script of the Delivery Workflow goes through this
command; none writes a `gc.flow.*` key itself. A field that is missing is
added here". Same in the module: "This command is the only reader and writer
of that state" (`lib/convoy_state.py:4-6`), "No other script invents a
`gc.flow.*` field" (`:40-41`). It rests on Spec af-wf4w5r §0 rule 2: « L'état
vit dans le tracker et le magasin de preuves, jamais dans le contexte d'une
session. Aucune session ne « tient le fil » d'un convoi. »

`docs/CONVOY_STATE.md:12-15` already says where the code is: "The code is
`lib/convoy_state.py`; `bin/convoy-state` is its entry point and holds nothing
else" (af-xhryl7). `bin/convoy-state` is its only importer (`:21`).

**What the rule guarantees.** One place renders and validates every field.
`show` flags a `gc.flow.*` key it does not know as written outside the command
(`lib/convoy_state.py:2872-2873`), and an unreadable record as an « état sans
règle » (`:2773-2856`), which stops the convoy (`bin/convoy-advance:1638-1641`).
Scenario: a script that parsed `gc.flow.counter.resumes` itself would take a
malformed value for 0 and resume a ticket that is out of resumes; through the
command it gets exit 3 and the convoy is stopped.

**Why each handed-over tool re-reads.** Four facts, each from the code:

1. Each is its own process, started with a convoy id and paths as arguments
   (`bin/convoy-advance:1740-1741`, `:1767`, `:1783`, `:1800`, `:1820`,
   `:1841-1842`, `:1861`, `:1433-1434`, `:1407-1408`, `:1493`, `:1532`); no
   state is passed to it. A state can only reach it by a read.
2. Each is also a command others start: an author session runs
   `bin/test-review review` ("the author's `review` and the pass [...] never
   launch it twice", `bin/test-review:347-348`), and
   `formulas/mol-ticket-resume.formula.toml:62` runs `bin/convoy-state show`
   from an agent session. What the pass knows is not what these callers know.
3. Each decides under its own lock from a read made after the lock is taken
   (section 3).
4. Each reads again after its own writes: `bin/code-review` opens a round then
   `convoy.load()` (`:674-676`); `bin/test-review` stops the ticket then reads
   it (`:494-495`); `bin/spec-integration` reads again after the fetch
   (`:707-709`); `bin/spec-end` reads the counters a refusal left (`:746-751`).

**In-process.** In substance kept free: a tool that imports the module runs
the same rendering and validation code; no second reader exists. In the
written contract, kept at a cost: these texts name the *command* as the
boundary and would no longer be true as written: `docs/CONVOY_STATE.md:5-10`
("goes through this command"), `lib/convoy_state.py:4-6`,
`docs/CONVOY_ADVANCE.md:48-52`, `bin/dispatch-door:164` ("bin/convoy-state
finds the city from its working directory"), `tests/convoy-state-test.py:2-5`
and `tests/convoy-advance-test.py:8` ("Only command lines are exercised"). The
map already lists what they become as not yet specified.

The four reasons above are untouched by where the read runs: the tool still
reads by itself, in its own process, after its own lock.

## 6. What is frozen at import, and what a long-lived process would see stale (G8, G9)

In `lib/convoy_state.py`:

| What | Where | Read when | Stale for |
|---|---|---|---|
| `GC_BIN` | `:167` | import | the life of the importing process |
| `BIN` (the Factory's `bin/`, from the module's path) | `:168` | import | never changes |
| `flow_bound(name)`, the bounds of `config/delivery-flow.json` | `:540-562`, `functools.lru_cache(maxsize=None)` | first call for each name | the life of the process, once a value was returned. A refusal is not kept (an exception is not cached; checked, section 10) |
| `FACTORY_ROOT` | `:547`, inside `flow_bound` | first call for each name | same as the bound |
| `CONVOY_STATE_LOCK_DIR`, `XDG_RUNTIME_DIR` | `:521` | each lock | not frozen |
| `SPEC_APPROVE_BIN` | `:5329` | each `spec_of` | not frozen |
| Git environment (`GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE` removed) | `:2443` | each Git call | not frozen |
| The working directory: `gc` is started with no `--city` and no `cwd` (`:459`); `--repo` defaults to `.` (`:5795`) | | each call | not frozen, but it is the caller's |

**Today** each of these lives for one command: a child reads its environment
and the settings file when it starts, and dies. `show` reads the bound of the
resumes at every call (`resumes_max()`, `:2761`: "a bound that cannot be read
is a refusal, never a default"), so a change of `bounds.resumes` is seen by
the very next read, in the middle of a pass.

**What the callers already freeze.** `bin/convoy-advance` reads `ROOT` and
`GC_BIN` at its own import (`:200-201`) and its settings once per pass
(`load_settings`, `:1875`, `:607-633`); it is itself a process per pass (the
order starts it, `orders/convoy-advance.toml`: `exec`, `timeout = "300s"`).
The handed-over Python tools do the same (`GC_BIN` at import in
`bin/code-review:66`, `bin/test-review:64`, `bin/ticket-evaluation:59`,
`bin/correction-round:61`, `bin/outcome-evaluation:64`,
`bin/spec-end-review:63`).

**In-process: kept at a cost.**

- *Bounds.* A tool that imports the module keeps the first value of each
  bound for its whole run. For `bin/convoy-advance` that is one pass instead
  of one `show`. Scenario: the operator lowers `bounds.resumes` while a pass
  runs; today the next `show` of that pass counts `resumes_left` on the new
  bound, in-process the pass finishes on the old one and the next pass takes
  the new. The cost of keeping today's behaviour exactly is to empty or drop
  that cache at each read.
- *`GC_BIN`.* Identical as long as the importing process has the same
  environment as the child it would have started. `bin/convoy-advance` passes
  its environment to its children unchanged (`run`, `:294-296`: no `env`), so
  for it the value is the same. `bin/dispatch-door` passes `GC_BIN` explicitly
  (`:166`), but it is bash and cannot import the module.
- *Working directory (G9).* `bin/convoy-advance` starts every child with
  `cwd=ROOT` (`:296`); `bin/dispatch-door` does `cd "$ROOT"` first (`:164-167`).
  The module's `gc` calls carry no `--city` (`:459`, `:470`), where the pass's
  own carry `--city ROOT` (`:310`). In-process, the module's `gc` runs in the
  tool's own working directory: the same city only if the tool was started in
  `ROOT`. The handed-over tools set no `cwd` for their children
  (`bin/code-review:146-148`) and inherit `ROOT` from the pass; started by
  hand from elsewhere they already depend on where they are started.
- A process that would live longer than one pass (none exists today) would in
  addition keep `GC_BIN` and every bound for its whole life.

## 7. The existing path that avoids a second read: `ticket --bead-json -`

`cmd_ticket` (`lib/convoy_state.py:2916-2941`): with `--bead-json -` it reads
the bead from stdin "as `gc bd show --json` printed it, instead of reading the
tracker again" (`:123-125`, `:2920`); any other value is refused (`:2918-2919`);
the bead's id must be the one asked or absent (`:2927`). It answers whether
the bead carries the mark: 0 marked, 4 no mark, 3 a mark it does not know
(`:2929-2941`).

Two callers, both bash:

- `bin/dispatch-door:311` reads the bead once, uses it for its own label
  checks (`:313-318`), then pipes it to `convoy_state ticket "$BEAD_ID"
  --bead-json -` (`:322`). Its header: "The mark is read by bin/convoy-state
  from the bead this door has already read, so a bead without the mark is
  dispatched exactly as before, with no further read" (`:84-86`).
- `bin/deliver-close:211-215`: "The mark is read by bin/convoy-state, on the
  bead already in hand (no second tracker read)".

What this precedent shows, as facts: (a) the command already accepts a state
read by its caller instead of reading it itself, for one question (the mark)
that needs no lock and no Git; (b) it saves the tracker read, not the start of
the command: a `convoy-state` child still runs; (c) the rule of section 5
holds in it, since the mark is still read by the module's code; (d) `show` has
no such option: `cmd_show` always calls `load_convoy` (`:2754`).

The ticket body says "the two existing ways"; one mechanism was found, with
these two callers. If a second mechanism was meant, it was not found.

In-process: `cmd_ticket` reads `sys.stdin` itself (`:2920`) and prints
(`:2940`); a caller in the same process has no stdin to give it.

## 8. `cmd_show` read in full: does a function return the show state without printing? (G10)

No. `cmd_show` (`lib/convoy_state.py:2753-2913`) is one function that:

1. reads the convoy (`:2754`) and refuses an unmarked one by raising
   `NotNewFlow` (`:2756-2758`);
2. reads the bound of the resumes (`:2761`);
3. renders the twelve convoy-level records, each in its own `try`, an
   unreadable one becoming an `unruled` entry (`:2763-2856`);
4. renders the evidence and flags unknown `gc.flow.*` keys (`:2857-2873`);
5. builds `convoy_out` (`:2874-2897`);
6. renders each ticket against the Git repository (`Repo(args.repo)`,
   `render_ticket`, `:2899-2900`), then its tracked items and findings
   (`:2903-2907`);
7. builds `answer` (`:2909-2911`), **prints it** (`:2912`) and returns the
   exit status, 3 or 0 (`:2913`).

The dictionary `answer` exists only as a local of that function. The pieces
that do return values are below it: `load_convoy` (`:468`), `render_ticket`
(`:2502`), `render_counters` (`:2465`), `tracked_items`, `findings_rendered`,
the `*_record` readers. None returns the whole state. The same holds for
`cmd_list` (prints at `:2426`) and `cmd_ticket` (`:2940`).

What a caller in the same process would meet, as facts:

- `cmd_show` takes an `argparse.Namespace` (`args.convoy`, `args.repo`); the
  default of `--repo`, `.`, is set by the parser (`:5795`), not by the function.
- The outcomes that are exit statuses today: `NotNewFlow` → 4 and `Refusal` → 1
  are turned into a JSON answer and a status only in `main` (`:5996-6004`);
  3 is the return value of `cmd_show` with the state printed (`:2913`,
  `:116-119`). Called directly, `cmd_show` raises the first two.
- `bin/convoy-advance` has its own `Refusal` and `NotNewFlow` classes
  (`:279-284`), as do the other tools; its `except Refusal` (`:2010`) does not
  catch the module's. Its `NotNewFlow` carries the JSON text of convoy-state's
  answer (`:284`, `:380`, `:2008`), not a convoy id as the module's does
  (`:2758`, `:5998`).
- Isolation: an unexpected exception in the state code (not a `Refusal`) is
  today a traceback on the child's stderr and an empty stdout, which the pass
  reads as "a rendu une réponse illisible" and turns into its own `Refusal`
  (`:301-306`), exit 1 with a JSON answer (`:2010-2012`). In-process the same
  exception would rise in the tool itself.
- The pass prints its own single JSON object on stdout (`:1989`): a state
  function that prints, called in-process, writes into that same stream.

## 9. What Spec af-wf4w5r says about the seam (G11)

`bd show af-wf4w5r`, « Testing Decisions »:

> Un bon test ici observe le comportement d'une porte ou du flux par son
> interface publique (ligne de commande, état du tracker, état des branches),
> jamais ses fonctions internes ni le texte d'une formule ou d'un prompt.

> Seams, confirmés par Benjamin le 2026-10-06 (« Oui aux deux ») : [...]
> 2. **Ligne de commande de chaque porte, sur un faux état du tracker** (modèle
> existant : tests de spec-approve, de la porte de fermeture actuelle, de la
> porte de publication) : un test par refus et par passage, qui relit l'état
> après pour prouver que rien n'a été écrit lors d'un refus. Portes concernées :
> publication (contrat d'entrée), spec-approve (nouveaux refus), sortie de
> ticket et Handoff, outil de capture, scripts rouge / gel / vert, détecteur de
> report, fin de ticket, fin de Spec, génération de l'Evidence Pack,
> enregistrement de l'acceptation, contrôles de fidélité et de conformité du
> prototype.

> Aucun seam nouveau. Les sessions d'agent ne sont pas testées en CI : seules
> leurs entrées et sorties, qui passent par les portes du seam 2, le sont.

And in its TDD section: « Preuve mécanique du seam obligatoire : boîte noire,
ou règle d'import vérifiée par script. Un test interne à un seam non listé est
un écart jugé par la revue. »

Facts that follow from the text and the tests:

- The seam is the command line of each *gate*. The list of gates names neither
  the state command nor the advance command; their tests place themselves
  under it all the same: `tests/convoy-state-test.py:2-5` ("Testing Decisions
  seam 2 [...] Only the command line is exercised") and
  `tests/convoy-advance-test.py:2-3`, `:8` ("Only command lines are
  exercised").
- The seam says how a tool is *tested*. It does not say how one tool reaches
  another: nothing in « Testing Decisions » requires a gate to start the state
  command rather than call its code. Where that is written is
  `docs/CONVOY_STATE.md:5-10` (section 5).
- "Qui relit l'état après" is done by the tests through the command
  (`self.show()`, `tests/convoy-state-test.py:293`).
- The tests reach the fake tracker by the environment given to each command
  they start: `GC_BIN` (`tests/convoy-state-test.py:41`), the lock directories
  (`:44`; `tests/convoy-advance-test.py:98-99`, `:784`, `:2046`). A tool that
  reads the state in-process is still started by its test as a command, with
  that environment: the module is then imported inside that command and reads
  `GC_BIN` there. Kept free, as long as the tests keep starting the tools.
- No test imports `lib/convoy_state.py`; `bin/convoy-state:21` is the only
  import in the tree.

## 10. Checks run, and what was not verified

**Run** (Python 3.12.3 on the Factory host, files in `/tmp` only):

- A second `fcntl.flock(LOCK_EX)` taken in the same process through another
  `open()` of the same file does not succeed while the first is held
  (`LOCK_NB` raised `BlockingIOError`). Without `LOCK_NB`, as in
  `convoy_lock`, it would wait for ever.
- `functools.lru_cache` does not keep an exception: the function is called
  again at the next call.

**Not verified:**

- Nothing of the Factory was run: no test, no pass, no `bd` or `gc` write.
  Every scenario of two processes above is read from the code and the
  comments, not reproduced. The only one a test of the repository proves is
  the counter bumps (`tests/convoy-state-test.py:285-293`).
- The 52 processes and 3.7 re-reads per pass of the map: not this ticket
  (af-jnjqn4.1), not reproduced.
- Whether two passes do overlap in their second half on the live Factory
  (section 2): the code allows it; how often the controller's tick meets a
  running pass was not measured.
- The lock order between the tools that start one another (section 3).
- What happens to a `convoy-state` child, and to the lock it holds, when the
  order's 300 s timeout stops the pass that started it: not looked at.
- The tools not named in the ticket body were read only for their locks and
  their reads of the state (`grep`), not in full: `bin/ticket-end`,
  `bin/evidence-pack`, `bin/ticket-exit`, `bin/tdd-step`, `bin/ticket-author`,
  `bin/prototype-fidelity`, `bin/evidence-capture`, `bin/acceptance-session`,
  `bin/ticket-graph-publish`, `bin/planning-artifacts-close`.
- "The two existing ways to avoid a second read" (section 7): one mechanism
  found, two callers.

## Sources

All in the Factory repository at `889e854`, and the tracker:

- `lib/convoy_state.py`, `bin/convoy-state`, `bin/convoy-advance` (read in full
  for the parts cited; `bin/convoy-advance` in full).
- `bin/test-review`, `bin/code-review`, `bin/ticket-evaluation`,
  `bin/correction-round`, `bin/spec-integration`, `bin/spec-end`,
  `bin/outcome-evaluation`, `bin/spec-end-review`, `bin/dispatch-door`,
  `bin/deliver-close`, `bin/ticket-end` (the lines cited).
- `docs/CONVOY_STATE.md`, `docs/CONVOY_ADVANCE.md`, `orders/convoy-advance.toml`,
  `formulas/mol-ticket-resume.formula.toml`.
- `tests/convoy-state-test.py`, `tests/convoy-advance-test.py` (headers, set-up,
  the concurrency test).
- `bd show af-jnjqn4`, `bd show af-jnjqn4.2`, `bd show af-wf4w5r` (2026-10-09).
