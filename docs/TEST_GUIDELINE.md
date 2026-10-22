# Test guideline (Spec CI01, af-q9urgr §3)

## Status and purpose

This is the one document that says how a test is written here. The test
method of a ticket, the author formula, the maintenance formula and the
review of the tests refer to it; none of them restates it. Its six points
name no tool and no file of this repository, so that they read the same in
any project; the figures of point 5 are those of the Spec, written here.
What is particular to this repository is in the last two sections.

It applies to the Factory's own repository. It is not yet applied to the
other projects the Factory delivers (af-8cfygl): the formulas test which
repository a ticket is on before they send an agent here.

Intent (Benjamin, his words, live chat, 2026-10-09, about 23:10 Paris): « il
faut reflechir comment réduire structurellement les temps de CI, tout en
conservant la qualité […] verifier si les tests ecrits sont tous bien faits
dans les meilleures pratiques. » And, on the size of the answer (live chat
/to-spec, 2026-10-10, about 03:45 Paris): « je suis solo dev pas une
entreprise il faut pas que j'overengineer ». The Spec that carries this
guideline was approved by « J'approuve la spec. » (live chat /to-spec,
2026-10-10, 03:57 Paris).
Mechanism (agent interpretation): six written points, of which code holds
one figure only, the ceiling of seconds per test file. It does not mean that
a test is removed, that a verification is dropped, or that a test never seen
red is a useless one: « never red in CI » proves nothing about a test.

Words: a **case** (cas) is one test method or function, the unit that passes
or fails; a **level** (étage) is how far from the code a case observes; the
**decor** (décor) is everything a case needs in place before its own
gesture. `GLOSSARY.md` holds the three.

## The six points

### 1. Public interface

The public interface of a tool is its commands and their arguments. A test
observes a tool through them and through what the tool leaves behind: exit
code, text, files, state of the tracker. It does not enter the code.

A test may call the commands **in the same process, through the tool's entry
function**: the same arguments as on the command line, the same observations.
The internal functions stay forbidden: a test that calls one is not a test of
the tool.

For each tool, **one pass and one refusal stay launched as a real process**:
they prove that the command line is wired to the entry function.

### 2. Level

There are three levels, from the lowest:

| Level | What a case does |
|---|---|
| low | calls the entry function of one tool in the test's own process |
| command line | launches one tool as a real process |
| whole journey | chains several tools from one end of a flow to the other |

Each refusal and each pass is proven **once, at the lowest level where it
can be observed**. The level above proves the **transmission** only: one
case per link between two tools, showing that what the lower tool answers
reaches the upper one. It does not replay the lower tool's refusals.

A red seen at an upper level with no red at the lower one means a case is
missing below: **add it below**, where the fault is, before or with the fix.

### 3. Whole journeys

The whole journeys of a repository are a **closed list**, written in this
document. An author does not add one alone: an addition is decided in the
testing section of a Spec, and the list is extended in the same change.

### 4. Decor

The decor common to the cases of a file is **built once per file, then
copied for each case**. What was built by real launches the first time is
restored, not replayed.

- **The values a case verifies stay written in the case.** A reader sees in
  the case what is given and what is expected, without opening the decor.
- **Existing shared helpers first.** A new helper is written only when none
  of the repository's does the job.

A copied decor keeps each case a real proof only under these rules:

- A case never sees what another case left. Every case starts from an empty
  working directory plus a restored copy; a stored copy is never modified
  once written. What a decor step returns is plain data, and a mutable value
  is copied on each return.
- Restoring a copy wipes the working directory. A step that is restored may
  therefore be reached only before the case has done anything else: work
  done before it would be lost in silence.
- A state that holds a live process (a launched product, a server, a port, a
  lock held) or a value compared with the clock is never stored: it is
  rebuilt for real in each case.
- The key of a stored copy covers every argument that changes the result.
  Other arguments, another copy.
- Assertions stay in the cases and in the helpers where they were; a decor
  step does not absorb them.
- Stopping the processes of a case stays the case's own cleanup, and runs
  before the next case wipes the directory.
- A case passes alone, and in any order.

### 5. Duration

Reference marks, per case, on average over a file. They are guidance for the
author and the reviewer; no code checks them:

| Level | Per case |
|---|---|
| low | 0.2 s |
| command line | 3 s |
| whole journey | 20 s |

**Ceiling: 120 seconds per test file.** Above it the file is cut in two.
This one figure is held by code (below).

The figures change on a word of the owner of the project or by a Spec. No
review of them is scheduled.

### 6. Review of the tests

The reviewer of the tests asks, of each case, one more question:

> Is this criterion already proven at a lower level? If so, does this case
> prove anything other than the transmission?

A case that proves again, higher, what a lower case already proves, and
nothing more than the transmission another case already shows, is a
**double**. A double refuses the test: the author removes the case, or
writes what it proves that the lower one does not. A case that is the only
proof of its criterion is never removed: its author writes what it proves
more.

## Known limits

- The rule of point 2, « a red above obliges a case below », is held by no
  code.
- A change made outside a ticket has no reviewer of the tests: only this
  guideline and the ceiling apply to it.
- The ceiling is checked on recorded durations, so its verdict moves only
  when they are refreshed: the change that adds a slow file stays green
  until then.
- A file that left the list of files known to be above the ceiling, and
  goes above it again, could be written back into that list without the
  check seeing it: the names of the first day stay accepted. Refusing that
  line is the reviewer's job; no code does it.

## In this repository: the whole journeys

The closed list of point 3, as read in `tests/` on 2026-10-10 (agent's
reading of what each file does, not a decision of Benjamin on any of them).

In the battery:

| File | The journey |
|---|---|
| `tests/planning-run-lifecycle-test.py` | a finished map, the approval of its Spec, the publication of its graph into a convoy |
| `tests/fixture-city-oracle-test.py`, and the six files that hold the rest of its cases and load its harness: `tests/fixture-city-oracle-one-ticket-test.py`, `tests/fixture-city-oracle-repaired-delivered-test.py`, `tests/fixture-city-oracle-nothing-goes-wrong-test.py`, `tests/fixture-city-oracle-parked-test.py`, `tests/fixture-city-oracle-parked-answer-author-gates-test.py`, `tests/fixture-city-oracle-accepted-answer-test.py` | a candidate planning path from a synthetic intent to Delivered and Accepted |
| `tests/convoy-stops-fixture-city-test.py`, and the two files that hold the rest of its cases and load its harness: `tests/acceptance-fixture-city-test.py`, `tests/owner-answer-promotion-fixture-city-test.py` | a published graph advanced pass after pass to its stops, to the end of its Spec, and to the answer of the owner |
| `tests/cockpit-criteria-test.py`, through the criterion tests of the cockpit it runs that launch it: `tests/cockpit-criteria/commands/isolated-launch-test.py` and `tests/cockpit-criteria/commands/home-destination-{states,fidelity,layout}-test.py` (with `home_destination.py` and `home_destination_measure.js`, their harness) | the cockpit launched by `bin/project-launch` on a dataset of its profile, then read over HTTP and, for a Prototype Fold, in a headless Chromium. Decided by the testing section of Spec af-2zseit (Testing Decisions 1, « Démarrer le vrai processus sur sources synthétiques conformes aux interfaces réelles, piloter HTTP et navigateur », and 5); added to this list by T02R2 (af-r2c0tx), after its code review (F1.1) |
| `tests/cockpit-criteria/commands/home-result-states-test.py`, `tests/cockpit-criteria/commands/home-recette-test.py` and `tests/cockpit-criteria/commands/home-d01-records-test.py` (the criterion tests of A1, run by `tests/cockpit-criteria-test.py`; the last loads the harness `FixtureCityWalk` of `tests/convoy-stops-fixture-city-test.py`) | the cockpit launched by `bin/project-launch` on a dataset of its profile and read in a headless Chromium and over HTTP; for the last, first the records of a convoy produced by the public D01 commands (`bin/acceptance-session`, `bin/owner-answer`, `bin/outcome-promote`) on the Fixture City walked to its Delivered Outcome, carried as the tracker of that dataset. Decided by the testing section of Spec af-fgcw0d (Testing Decisions 1, « Démarrer le vrai processus sur sources synthétiques conformes aux interfaces réelles, piloter HTTP et navigateur », 2, « Produire les records par les commandes publiques existantes d'acceptation, jugement et promotion ; vérifier ensuite les mêmes records dans le cockpit », and 8, its seams); added to this list by A1 (af-c662qx), after its code review (F1.2) |
| `tests/cockpit-criteria/commands/projects-release-test.py`, `tests/cockpit-criteria/commands/projects-roadmap-test.py` and `tests/cockpit-criteria/commands/projects-recette-test.py` (the criterion tests of E, run by `tests/cockpit-criteria-test.py`, with `project_destination.py`, their harness beside `home_destination.py`) | the cockpit launched by `bin/project-launch` on a dataset of its profile -- or on a dataset a case declares, holding a tracker and the knowledge repositories of the projects, Git repositories committed at a date the case writes -- and read in a headless Chromium and over HTTP: `/projets`, then the page of a project with its release, its roadmap and its historique. Decided by the testing section of Spec af-fgcw0d (Testing Decisions 1, « Démarrer le vrai processus sur sources synthétiques conformes aux interfaces réelles, piloter HTTP et navigateur », 5 and 8, its seams); added to this list by E (af-8rbceu), after its code review (F1.2) |
| `tests/cockpit-criteria/commands/pour-moi-visible-test.py`, `tests/cockpit-criteria/commands/pour-moi-gestures-test.py`, `tests/cockpit-criteria/commands/action-expiry-test.py` and `tests/cockpit-criteria/commands/usine-muette-test.py` (the criterion tests of B, run by `tests/cockpit-criteria-test.py`, with `pour_moi.py` and `pour_moi_walk.js`, their harness) | the cockpit launched by `bin/project-launch` on a dataset of its profile -- or on a tracker as the doors of the Factory write it, its doors acting on it, expiring, or expiring once their record is written --, read over HTTP and in a headless Chromium behind an identity proxy, where a gesture is armed, confirmed and read back at its source. Decided by the testing section of Spec af-fgcw0d (Testing Decisions 1, « vérifier ce qui est rendu, les actions disponibles, leurs réponses et traces », 3, « acquittement/report/raison/confirmations … erreurs/timeout », and 8, its seams); added to this list by B (af-4uzgzm) |

Outside the battery (marked `# ci: local-only`, run on the host against the
real runtime; they cost CI nothing):

| Files | The journey |
|---|---|
| `tests/*-isolated-city-test.sh` (13) | the adoption trial of one mechanism in a disposable city, with a real controller |
| `tests/*-real-tracker-test.sh` (5) | what a fake tracker assumes, replayed on the real one |
| `tests/*-demonstration-test.sh` (3) | the demonstration line of a ticket on the real tracker, and a real browser where it needs one |
| `tests/*-real-session-test.sh` (2) | one real model session held to what a command hands it |

`bin/local-only-tests` runs them nightly. A test whose host cannot run it
exits 77 with a `SKIP: <reason, bead>` line, decided by a cheap, precise probe
(`tests/lib/capture-browser.sh` for the capture browser): the runner names it
SKIPPED, not failed, on every run and in the bead of a failing run; exit 77
without a `SKIP:` line counts as a failure. Any other
failure of the probe lets the test run, so a real regression stays red.

## In this repository: the ceiling held by code

`bin/ci-test-ceiling check` reads the seconds each test file took in a real
Factory CI run (`config/ci-test-seconds.tsv`, written by
`bin/ci-test-seconds`). It measures nothing itself.
`tests/ci-test-ceiling-test.py` runs it on the repository, so a pull request
that breaks the rule is red in CI.

| What it finds | Verdict |
|---|---|
| a test file above 120 s | refused, by name, with its seconds |
| the same, with a line `# ci: over-ceiling — <reason>` in the file | accepted: a written exception |
| that line without a reason: none, the template `<reason>` left as it is, or under 10 characters | refused |
| recorded seconds that cannot be read, hold no duration, or hold a line that is neither a comment nor `<path><TAB><seconds>` | refused, naming the line |
| a file above 120 s named in `config/ci-test-ceiling-known.txt` | accepted: it was above when the control was introduced |
| a line added to that list | refused: the list may only name the 20 files that were above on 2026-10-10 (held in the command itself) |
| a line of that list whose file is no longer above 120 s | refused: the line leaves (`bin/ci-test-ceiling prune`) |

**When it turns red.** The verdict depends on two files only, the recorded
seconds and the known list. It therefore moves only in the pull request that
changes one of them, which in practice is the one that refreshes the seconds
(`bin/ci-test-seconds`, then `bin/ci-test-ceiling prune`, same pull request).
A test file that got faster, or slower, turns no other pull request red:
until the seconds are refreshed, the control still reads the old figure.
The refresh is where a file that crossed the ceiling is seen, and where the
list shrinks.

Speeding a file up with the same cases and the same verifications is proven
by `bin/test-cases-compare`
(`./bin/test-cases-compare --before origin/main:tests/x-test.py --after tests/x-test.py`),
not by this control.

Limits of the control: it reads what CI recorded, on a host whose load moves
the seconds (a file near 120 s can cross at a refresh without having
changed); a file never measured is not checked; a written exception needs
ten characters that are not the template, and whether its reason is a good
one is what the code review reads.
