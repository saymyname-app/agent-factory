#!/usr/bin/env python3
"""Read and write the durable state of a "new flow" convoy (T33, af-p4d6ec).

Spec af-wf4w5r §0 rule 2: the state of a delivery lives in the tracker, never
in a session. This command is the only reader and writer of that state for a
convoy that carries the new-flow mark: the mark of the convoy and of its
tickets, the Spec the convoy delivers (T09, read only), a ticket's kind and
demonstration line (T05), its Declared Scope (T11, read only), the user
stories a vertical_slice covers and whether it establishes the project's launch
recipe (T06) or is the Prototype Fold (T36), its acceptance criteria (T10,
read only), its branch and Ticket Exit, its verdicts (each tied to a
commit), its counters, its evidence fingerprints and its gate records, the
steps of its TDD and its stop (T10), the review of its criterion tests
before the freeze (T13), its code review and the model each delivery role
ran on (T14), its Ticket Evaluation on the launched product (T15), its
Ticket Handoff and its parking (T11), the result of the mechanical fidelity
check against the Validated Prototype and the Planning Exceptions that name
an anchor (T16), the
integration branch of the convoy's Spec and what the merge command did of a
ticket (T18), the single correction round of a ticket and the overrides of
the operator on a stopped one (T17), the fingerprint of its acceptance
criteria frozen with the approved graph, the reference of the Validated
Prototype the publication door posed in an interface ticket (read only) and
the record of the ticket-end gate, written with the closing of the ticket
(T19), the convoy's open factory incident, the manual lifecycle of the
convoy: the mark puts it out of Gas City's automatic closing, and a marked
convoy found closed is one closed outside the acceptance and abandon
commands (T22), the red of its integration branch with the one repair
that restores it (T21), and, for the end of the Spec (T23): the final state
of each deviation and « non fait » of a Ticket Handoff, the Planning
Exception that names them, the repair that restores them, and the record of
the end-of-Spec gate, its three mechanical verdicts tied to one commit of
the integration branch; the Outcome Evaluation of the convoy on the
assembled product at that commit, the fingerprints of its pieces, the
classification of each finding « hors ticket » of a Ticket Handoff and the
repairs drafted then published for them (T24); and the end code review of
the Spec on the assembled diff (T25): its request, its rounds, each tied to
the commit of the gate it read, the repair drafted for each of its Blocking
Findings, its stop, and the tip the last round of the end was counted for.
No other script
invents a `gc.flow.*` field: a missing field is added here.

    convoy-state list            (open marked convoys; under `closed_outside`,
                                  those closed outside acceptance or abandon)
    convoy-state show CONVOY [--repo DIR]
    convoy-state ticket TICKET [--bead-json -]
    convoy-state mark CONVOY [--demonstration-line TICKET=LINE ...] [--user-stories TICKET=N,N ...]
                             [--establishes-launch-recipe TICKET] [--prototype-fold TICKET]
    convoy-state set-branch   CONVOY TICKET --branch NAME
    convoy-state set-session  CONVOY TICKET --session NAME
    convoy-state set-exit     CONVOY TICKET --exit EXIT
    convoy-state set-verdict  CONVOY TICKET --kind KIND --state STATE --commit SHA
    convoy-state set-counter  CONVOY [--ticket TICKET] --counter NAME --value N
    convoy-state bump-counter CONVOY [--ticket TICKET] --counter NAME [--counter NAME]
    convoy-state add-evidence CONVOY TICKET --piece NAME --digest sha256:HEX --commit SHA
                              (TICKET is CONVOY for a piece of the end of the Spec)
    convoy-state record-gate  CONVOY TICKET --gate GATE [--commit SHA]
    convoy-state close-ticket CONVOY TICKET --commit SHA --file PATH
    convoy-state set-tdd      CONVOY TICKET --step STEP --commit SHA [--base SHA] [--reason TEXT]
    convoy-state stop-ticket  CONVOY TICKET --reason REASON --detail LINE
    convoy-state stop-raised  CONVOY TICKET
    convoy-state open-test-review   CONVOY TICKET --commit SHA --file PATH
    convoy-state launch-test-review CONVOY TICKET --bead BEAD
    convoy-state record-test-review CONVOY TICKET --file PATH
    convoy-state set-model    CONVOY TICKET --role ROLE --agent NAME --provider NAME --model NAME
    convoy-state open-code-review    CONVOY TICKET --kind review|judgement --commit SHA --base SHA [--file PATH]
    convoy-state launch-code-review  CONVOY TICKET --bead BEAD
    convoy-state record-code-review  CONVOY TICKET --file PATH
    convoy-state respond-code-review CONVOY TICKET --file PATH
    convoy-state open-evaluation    CONVOY TICKET --commit SHA --file PATH
    convoy-state launch-evaluation  CONVOY TICKET --bead BEAD
    convoy-state record-evaluation  CONVOY TICKET --file PATH
    convoy-state record-startup     CONVOY TICKET --commit SHA (--piece NAME --file PATH | --detail LINE)
    convoy-state release-evaluation CONVOY TICKET --state-file PATH [--state-file PATH] [--withdraw]
    convoy-state set-handoff  CONVOY TICKET --file PATH
    convoy-state park         CONVOY TICKET --cause CAUSE --detail LINE
    convoy-state set-fidelity CONVOY TICKET --commit SHA --piece NAME --file PATH
    convoy-state raise-planning-exception CONVOY TICKET --kind KIND --summary LINE [--anchor NAME ...] [--item ID ...]
                                          [--accept-option LETTER]
    convoy-state set-item-repair CONVOY TICKET --repair TICKET
    convoy-state record-blocking-red CONVOY TICKET --control LINE
    convoy-state clear-blocking-red  CONVOY TICKET
    convoy-state set-integration CONVOY --branch NAME --protected NAME --base SHA
    convoy-state set-merge    CONVOY TICKET --outcome OUTCOME --ticket-commit SHA --integration SHA [--commit SHA]
    convoy-state invalidate-verdicts CONVOY TICKET --tip SHA --kind KIND [--kind KIND]
    convoy-state open-correction   CONVOY TICKET --commit SHA
    convoy-state launch-correction CONVOY TICKET --bead BEAD
    convoy-state override-finding  CONVOY TICKET --finding ID --approver NAME --words TEXT
    convoy-state record-incident CONVOY --bead BEAD [--signature sha256:HEX]
    convoy-state clear-incident  CONVOY
    convoy-state record-integration-red CONVOY --commit SHA --integration SHA --protected SHA --control LINE [--detail LINE]
                                        [--check regression|fidelity] [--end-round]
    convoy-state set-integration-repair CONVOY --ticket TICKET
    convoy-state clear-integration-red  CONVOY
    convoy-state record-spec-end CONVOY --commit SHA --protected SHA --file PATH
    convoy-state record-evidence-pack CONVOY --commit SHA --digest sha256:HEX --path DIR (--conforming | --non-conforming)
                                      [--inadmissible N]
    convoy-state open-end-review        CONVOY --commit SHA --file PATH
    convoy-state launch-end-review      CONVOY --bead BEAD
    convoy-state record-end-review      CONVOY --file PATH
    convoy-state set-end-review-repair  CONVOY --finding ID (--ticket TICKET | --refused LINE)
    convoy-state stop-end-review        CONVOY --reason REASON --detail LINE
    convoy-state end-review-stop-raised CONVOY --bead BEAD
    convoy-state end-stop-raised  CONVOY --bead BEAD
    convoy-state record-delivered CONVOY --commit SHA --pack-digest sha256:HEX
    convoy-state acceptance-requested     CONVOY --bead BEAD
    convoy-state acceptance-launch-failed CONVOY --commit SHA --detail LINE
    convoy-state set-acceptance-repair    CONVOY --ticket TICKET
    convoy-state record-proposition-verdict CONVOY --proposition ID --verdict avant|plus_tard|sans_suite --approver NAME --words TEXT
    convoy-state set-verdict-proposal     CONVOY --proposition ID --bead BEAD
    convoy-state record-owner-answer      CONVOY --response accepted|findings|abandoned --approver NAME
                                          [--words TEXT --commit SHA --pack-digest DIGEST] [--file PATH] [--reason LINE]
                                          [--repo DIR]
    convoy-state set-owner-repair         CONVOY --finding N --ticket TICKET
    convoy-state set-owner-proposal       CONVOY --finding N --bead BEAD
    convoy-state resolve-owner-exception  CONVOY --approver NAME --words TEXT
    convoy-state open-outcome-evaluation    CONVOY --commit SHA --file PATH
    convoy-state launch-outcome-evaluation  CONVOY --bead BEAD
    convoy-state record-outcome-evaluation  CONVOY --file PATH
    convoy-state release-outcome-evaluation CONVOY --state-file PATH [--state-file PATH] [--withdraw]
    convoy-state stop-outcome-evaluation    CONVOY (--commit SHA --reason REASON --detail LINE | --raised)
    convoy-state classify-finding   CONVOY TICKET --item out_of_ticket.N --as repaired|proposal|dismissed
                                    --recorded-by SESSION [--reason LINE] [--file PATH]
    convoy-state set-outcome-repair CONVOY --repair TICKET (--story N | --ticket TICKET --item out_of_ticket.N)

Every answer is one JSON object on stdout. Exit status: 0 done; 1 refused or
could not run (nothing written); 3 `show` or `ticket` found an "état sans
règle" (the state is still printed, the incoherent field never as a default
value); 4 the convoy, or the ticket asked by `ticket`, does not carry the
mark ("pas un convoi du nouveau flux": nothing is read further, nothing is
written).

`ticket` says whether one ticket carries the mark; with `--bead-json -` it
reads the bead from stdin, as `gc bd show --json` printed it, instead of
reading the tracker again (what bin/dispatch-door does before a dispatch).

A verdict is valid only while its commit is the tip of the ticket's branch
in `--repo` (default: the current directory): a commit added after it makes
it invalid, a commit that is not on the branch at all is an "état sans
règle". `invalidate-verdicts` writes that on the verdicts the merge command
found outdated, and counts one resume for it -- none when the commit is the
one of the correction round, which `open-correction` already counted.

The bound of the resumes of a ticket (K) is read in the one place the
bounds of the flow are set: `bounds.resumes` of config/delivery-flow.json,
under FACTORY_ROOT (default: the repository of this script), and in the
Factory's own file when that root sets no bounds. The bound of the repair
rounds of the end of a Spec, `bounds.end_rounds`, is read there too, by the
write that would count a round. Closed lists and stored keys:
docs/CONVOY_STATE.md.
"""

from __future__ import annotations

import argparse
import fcntl
import functools
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

# The two names serve annotations only, which are never evaluated here
# (`from __future__ import annotations`): importing `typing` on each of the
# thousands of starts of this command would be paid for nothing (af-xhryl7).
TYPE_CHECKING = False
if TYPE_CHECKING:
    from typing import Any, Iterator


PROGRAM = "convoy-state"
GC_BIN = os.environ.get("GC_BIN", "gc")
BIN = Path(__file__).resolve().parents[1] / "bin"  # this module is in lib/
# The city is named to gc on every call: left to find it by itself, gc 1.4.1
# starts one more command before each read, and the same `bd show` takes 2.5
# times longer (af-2o6oyl). Same root as bin/convoy-advance.
CITY = Path(os.environ.get("FACTORY_ROOT") or BIN.parent)
# Where the bounds of the flow are set (Spec §8): one file, read by every
# command that applies one of them.
SETTINGS = "config/delivery-flow.json"

MARK = "new-flow/v1"
PREFIX = "gc.flow."
KEY_MARK = PREFIX + "mark"
# Gas City's own label for a convoy under manual lifecycle (`gc convoy create
# --owned`): `gc convoy check`, which the order convoy-parent-sweep runs,
# leaves a convoy that carries it open once all its tickets are closed (tried
# on gc 1.4.1 in an isolated city, 2026-10-08). A marked convoy closes only by
# code, on the operator's words (Spec §9).
LABEL_MANUAL_LIFECYCLE = "owned"
KEY_DEMONSTRATION = PREFIX + "demonstration_line"
KEY_USER_STORIES = PREFIX + "user_stories"
KEY_LAUNCH_RECIPE = PREFIX + "establishes_launch_recipe"
KEY_PROTOTYPE_FOLD = PREFIX + "prototype_fold"
# The kind is the one entry-contract field the publication door has always
# written (`gc.ticket_kind`); this command reads it, and never writes it.
KEY_KIND = "gc.ticket_kind"
# The Spec a convoy delivers is written by the publication door too
# (`gc.spec_id`); the evidence store is filed under it (T09). Read only.
KEY_SPEC = "gc.spec_id"
KEY_SPEC_DIGEST = "gc.spec_digest"
# The Declared Scope of a ticket is written by the publication door as well
# (`gc.scope_paths`, comma-separated paths); it orders tickets and bounds
# nothing (Spec §2). Read only.
KEY_SCOPE = "gc.scope_paths"
KEY_BRANCH = PREFIX + "branch"
KEY_EXIT = PREFIX + "exit"
VERDICT_PREFIX = PREFIX + "verdict."
COUNTER_PREFIX = PREFIX + "counter."
EVIDENCE_PREFIX = PREFIX + "evidence."
GATE_PREFIX = PREFIX + "gate."
TDD_PREFIX = PREFIX + "tdd."
KEY_STOP = PREFIX + "stop"
KEY_TEST_REVIEW = PREFIX + "test_review"
KEY_HANDOFF = PREFIX + "handoff"
KEY_PARK = PREFIX + "park"
KEY_INCIDENT = PREFIX + "incident"
KEY_INTEGRATION = PREFIX + "integration"
KEY_INTEGRATION_RED = PREFIX + "integration_red"
KEY_MERGE = PREFIX + "merge"
KEY_SESSION = PREFIX + "session"
KEY_CODE_REVIEW = PREFIX + "code_review"
KEY_MODELS = PREFIX + "models"
KEY_EVALUATION = PREFIX + "evaluation"
KEY_FIDELITY = PREFIX + "fidelity"
KEY_PLANNING_EXCEPTIONS = PREFIX + "planning_exceptions"
# The red control the author of a ticket says blocks it technically (T40):
# what the `repair` its exit asks for cites, read by the patch door.
KEY_BLOCKING_RED = PREFIX + "blocking_red"
KEY_CORRECTION = PREFIX + "correction"
KEY_OVERRIDES = PREFIX + "overrides"
KEY_CRITERIA = PREFIX + "criteria"
KEY_RESUME = PREFIX + "resume"
KEY_PARK_LIFTS = PREFIX + "park_lifts"
KEY_GROUPED_REQUEST = PREFIX + "grouped_request"
KEY_SPEC_END = PREFIX + "spec_end"
KEY_END_REVIEW = PREFIX + "end_review"
KEY_END_ROUND = PREFIX + "end_round"
KEY_EVIDENCE_PACK = PREFIX + "evidence_pack"
KEY_END_STOP = PREFIX + "end_stop"
KEY_DELIVERED = PREFIX + "delivered"
KEY_ACCEPTANCE = PREFIX + "acceptance"
# Benjamin's judgement of the Outcome (T29, Spec §11): his verdict on each
# proposition and each of his answers, oldest first, with his words.
KEY_JUDGEMENT = PREFIX + "judgement"
OWNER_VERDICTS = ("avant", "plus_tard", "sans_suite")
OWNER_VERDICT_NAMES = {"avant": "à faire avant d'accepter", "plus_tard": "plus tard", "sans_suite": "sans suite"}
OWNER_RESPONSES = ("accepted", "findings", "abandoned")
OWNER_FINAL_RESPONSES = ("accepted", "abandoned")
# What follows Benjamin's answer (T30, Spec §9, §11). After « accepté », code
# takes the protected branch up and replays the mechanical controls; green,
# the one merge into the protected branch is noted with the commit he judged
# (the promotion); red or in conflict, his acceptance is voided -- it stays
# in the judgement, with the control that voided it -- and the Outcome goes
# back to the end of the Spec. The convoy is then closed by command, on his
# words: accepted after its merge, abandoned without any.
KEY_PROMOTION = PREFIX + "promotion"
KEY_CLOSED = PREFIX + "closed"
VOID_CAUSES = ("regression", "fidelity", "start", "conflict")
CLOSINGS = {"accepted": "accepté", "abandoned": "abandonné"}
OWNER_ROUTES = ("repair", "planning_exception", "later")
# What an Owner Finding cites to be a repair (Spec §11): the story or the anchor.
OWNER_CITED_KINDS = ("user_story", "anchor")
OWNER_REPAIR_FIELDS = ("title", "what_it_delivers", "demonstration_line", "acceptance_criteria")
KEY_OUTCOME_EVALUATION = PREFIX + "outcome_evaluation"
KEY_FINDINGS = PREFIX + "findings"
# Written by the publication door (bin/ticket-graph-publish): the digest of
# the approved graph the ticket was last published under. Read only here.
KEY_GRAPH_DIGEST = "gc.graph_digest"
# What bin/escalation-door writes on a bead when the operator answers a
# request (`repondre`); a Planning Exception is resolved by that answer. Read only.
KEY_NEEDS_BENJAMIN = "gc.needs_benjamin"
KEY_RESPONSE_OPTION = "gc.escalation_response_option"
KEY_RESPONSE_AT = "gc.escalation_response_at"
# The key Gas City and bin/ticket-exit read the session of a bead under.
KEY_SESSION_NAME = "gc.session_name"

TICKET_KINDS = ("vertical_slice", "prefactoring", "repair")
KINDS_WITH_DEMONSTRATION = ("vertical_slice", "repair")
KIND_COVERING_STORIES = "vertical_slice"
EXITS = ("finished", "planning_exception", "operator_request", "technically_blocked", "interrupted")
VERDICT_KINDS = ("test_review", "code_review", "evaluation", "fidelity")
VERDICT_STATES = ("favorable", "unfavorable")
TICKET_COUNTERS = ("resumes", "correction_rounds")
CONVOY_COUNTERS = ("end_rounds",)
GATES = ("dispatch", "ticket_end", "withdrawn")
CLOSING_GATES = ("ticket_end", "withdrawn")
GATE_TICKET_END = "ticket_end"
# The ticket-end gate (T19, Spec §9): a closed, versioned list of nine
# conditions. bin/ticket-end computes each verdict; its record is written
# here, with the closing of the ticket, and only when the nine pass.
TICKET_END_VERSION = "ticket-end/v1"
TICKET_END_CONDITIONS = (
    "criteria", "handoff", "evaluation", "fidelity", "deferral", "merge", "evidence", "tdd", "review")
TICKET_END_PASS = "pass"
# The pointer the publication door poses in an interface ticket (T36).
PROTOTYPE_HEADING = "## validated prototype"
PROTOTYPE_FIELDS = {"branche": "branch", "commit": "commit", "chemin": "path", "états": "states"}
# The steps bin/tdd-step proves (Spec §5), each tied to a commit.
# The end-of-Spec gate (T23, Spec §9, points 1 to 3): its closed list of
# mechanical conditions, versioned. bin/spec-end computes the verdicts; a
# record that is not this list, all passing, is refused.
SPEC_END_VERSION = "spec-end/v4"
# A record written under an earlier list (T23's, T24's, T25's) is still read:
# the gate holds it for outdated and replays everything.
SPEC_END_VERSIONS = ("spec-end/v1", "spec-end/v2", "spec-end/v3", SPEC_END_VERSION)
SPEC_END_CONDITIONS = ("registry", "tests", "fidelity")
SPEC_END_PASS = "pass"
SPEC_END_RECORDS = ("tests", "fidelity")
# The Evidence Pack (T27, Spec §10): the page bin/evidence-pack generated,
# tied to one commit of the integration branch.
EVIDENCE_PACK_VERSION = "evidence-pack/v1"
# The end code review of the Spec (T25, Spec §6, « Fin de Spec »): one run on
# the whole assembled diff, replayed in full on each new tip. An output that
# is not complete is not a passed review: its launch gave no result.
END_REVIEW_OUTCOMES = ("favorable", "unfavorable", "incomplete")
END_REVIEW_INCOMPLETE = "incomplete"
END_REVIEW_MAX_LAUNCHES = 2
END_REVIEW_STOPS = ("end_review_no_result", "end_review_repair_refused")
END_REVIEW_SOURCE = "end_review"
# What refuses a tip of the integration branch at the end of a Spec (Spec §8,
# « toutes sources ») and so counts one round of repair: a mechanical red
# (the regression command, the fidelity), the end code review, the Outcome
# Evaluation (a story not observed, a finding « hors ticket » to repair).
OUTCOME_SOURCE = "outcome_evaluation"
END_ROUND_SOURCES = ("regression", "fidelity", END_REVIEW_SOURCE, OUTCOME_SOURCE)
# Why the rounds of repair of the end stop and hand over to the operator
# (Spec §8): the bound is consumed, or -- early -- a round did not reduce
# the number of stories not observed, or one story was refused twice.
END_STOP_EXHAUSTED = "end_rounds_exhausted"
END_STOP_NOT_REDUCED = "stories_not_reduced"
END_STOP_TWICE = "story_refused_twice"
END_STOPS = (END_STOP_EXHAUSTED, END_STOP_NOT_REDUCED, END_STOP_TWICE)
PACK_PAGE = "index.html"
END_CITATION_SOURCES = ("spec", "ticket", "repo_rule")
END_EXTENT_COUNTS = ("files", "commits", "insertions", "deletions")
# What a repair drafted by the end reviewer may restore (Spec §2): a red
# control is restored by a repair that code writes, never by a drafted one.
DRAFT_RESTORES = ("user_story", "anchor", "spec_line", "repo_rule")
MAX_MISSING_NAMED = 20
# What is red on the integration branch: the regression command (T21), or
# the mechanical fidelity the end-of-Spec gate measures (T23).
RED_CHECKS = ("regression", "fidelity")
# A tracked element (Spec §9, « éléments suivis »): a deviation or a « non
# fait » an author declared in its Ticket Handoff. It ends repaired or
# accepted by Benjamin, and code alone reads which.
ITEM_SECTIONS = ("deviations", "not_done")
# The findings « hors ticket » of a Ticket Handoff, classified by the
# Evaluator of the end (T24, Spec §9), and the states code reads for them.
FINDING_SECTION = "out_of_ticket"
FINDING_CLASSES = ("repaired", "proposal", "dismissed")
FINDING_UNCLASSIFIED = "non classé"
FINDING_TO_REPAIR = "à réparer"
FINDING_REPAIRED = "réparé"
FINDING_PROPOSAL = "proposition pour Benjamin"
FINDING_DISMISSED = "écarté"
# What a `repair` may restore: the kinds bin/ticket-graph-publish knows.
RESTORES_KINDS = ("user_story", "anchor", "spec_line", "repo_rule", "red_check")
REPAIR_DRAFT_FIELDS = ("title", "what_it_delivers", "restores", "demonstration_line", "acceptance_criteria")
REPAIR_CRITERION_FIELDS = ("entry_point", "observable", "false_if")
# The Outcome Evaluation (T24, Spec §7): the same states as a Ticket
# Evaluation, one per numbered user story; its two non-blocking sections.
OUTCOME_OUTCOMES = ("favorable", "repair", "planning_exception", "environment_outage")
OUTCOME_SECTIONS = ("exploration", "fidelity_deviations")
OUTCOME_STOPS = ("outcome_evaluation_no_result", "outcome_evaluation_outage", "story_unobservable")
ITEM_OPEN = "ouvert"
ITEM_REPAIRED = "réparé"
ITEM_ACCEPTED = "accepté par Benjamin"
TDD_STEPS = ("red", "freeze", "green", "amendment", "prefactoring")
TDD_STEPS_WITH_BASE = ("red", "prefactoring")
KIND_WITHOUT_RED = "prefactoring"
STOP_TEST_REVIEW_REFUSED = "test_review_refused"
STOP_REASONS = ("criterion_already_green", "amendment_exhausted", STOP_TEST_REVIEW_REFUSED, "test_review_no_result",
                "code_review_no_result", "evaluation_no_result", "evaluation_outage", "still_refused")
# The correction round of a ticket (T17, Spec §8): one for its code review
# and its Ticket Evaluation together, worked by one fresh author session. A
# ticket still refused after it is stopped (`still_refused`); on a stopped
# ticket the operator may override a Blocking Finding of the review, never a
# criterion that was not observed.
CORRECTION_MAX_ROUNDS = 1
CORRECTION_MAX_LAUNCHES = 1
OVERRIDE_RECORDED = "dérogation enregistrée"
# The review of the criterion tests between red and freeze (Spec §5, §8): a
# refusal returns once to the author, the second one stops the ticket; a
# review that gives no result is launched once more, no further.
TEST_REVIEW_MAX_REFUSALS = 2
TEST_REVIEW_MAX_LAUNCHES = 2
# The code review of a ticket (T14, Spec §6). A round is the review itself,
# or the judgement a second reviewer session gives of the answers to its
# Blocking Findings.
CODE_REVIEW_KINDS = ("review", "judgement")
CODE_REVIEW_MAX_LAUNCHES = 2
REVIEW_AXES = ("standards", "spec")
# What a Blocking Finding may cite (Spec §6): a line of the Spec, of the
# ticket, or a written rule of the repository.
CITATION_SOURCES = ("spec", "ticket", "repo_rule")
QUESTION_KINDS = ("internal_test", "amended_test")
QUESTION_ANSWERS = ("oui", "non")
# The axis of a Blocking Finding made by code of a closed question answered « non ».
AXIS_TESTS = "tests"
FINDING_RESPONSES = ("fixed", "contested")
MODEL_ROLES = ("author", "reviewer", "evaluator")
# The Ticket Evaluation of the launched product (T15, Spec §7): one state per
# acceptance criterion and for the demonstration line, each with a captured
# piece of evidence; the Evaluator gives no verdict, code computes it. An
# « inobservable » says what made it so: the criterion, or the environment.
EVALUATION_KINDS = ("evaluation", "startup")
EVALUATION_STATES = ("observed", "not_observed", "unobservable")
UNOBSERVABLE_CAUSES = ("criterion", "environment")
EVALUATION_OUTCOMES = ("favorable", "return_to_author", "planning_exception", "environment_outage")
EVALUATION_MAX_LAUNCHES = 2
KIND_WITHOUT_EVALUATOR = "prefactoring"
ADDRESS_RE = re.compile(r"^http://127\.0\.0\.1:[0-9]{1,5}$")
MAX_FINDING_LINE = 600
ACCEPTANCE_HEADING = "## acceptance criteria"
# The Ticket Handoff (Spec §5): four sections written by the author, each
# with content or the word for "nothing", and the records written by code.
HANDOFF_SECTIONS = ("done", "deviations", "not_done", "out_of_ticket")
HANDOFF_NOTHING = "aucun"
# The piece of the evidence store bin/ticket-exit seals the records in.
HANDOFF_RECORDS_PIECE = "handoff_records"
# Why a ticket and its descendants are parked: a Ticket Exit (Spec §5), or
# the bound of the resumes of a ticket (Spec §8, T20).
PARK_EXHAUSTED = "resumes_exhausted"
PARK_CAUSES = ("planning_exception", "operator_request", PARK_EXHAUSTED)
# Spec §8, K: the resumes of a ticket, every cause together; at the last one
# the ticket is parked with its descendants. The value is a setting
# (`bounds.resumes` of config/delivery-flow.json, `resumes_max`).
BOUND_RESUMES = "resumes"
BOUND_END_ROUNDS = "end_rounds"
# Why code sends a ticket back to a fresh author session (T20): its session
# was interrupted, the merge returned it, the repair it waited for is closed,
# or the request that parked it was answered. The correction round and a
# commit after a verdict are counted where they are written.
RESUME_CAUSES = ("interrupted", "returned", "unblocked", "answered")
RESUME_MAX_LAUNCHES = 1
# What bin/spec-integration did of a ticket (Spec §4): merged into the
# integration branch, or returned to its author by a conflict or by red tests
# on the merged result. A merge and a red name the commit that was tested.
MERGE_OUTCOMES = ("merged", "conflict", "red")
MERGE_OUTCOMES_WITH_COMMIT = ("merged", "red")

# The mechanical fidelity check against the Validated Prototype (T16, Spec
# §3): what a deviation is, and the three states of a result. A deviation is
# never lifted by its author: only a resolved Planning Exception that names
# the anchor turns it « accepté par Benjamin ».
DEVIATION_KINDS = ("absent", "structure", "style", "token")
DEVIATION_KIND_WITHOUT_ANCHOR = "token"
FIDELITY_GREEN = "vert"
FIDELITY_RED = "rouge"
FIDELITY_ACCEPTED = "accepté par Benjamin"
DEVIATION_OPEN = "ouvert"
PLANNING_EXCEPTION_KINDS = ("semantic", "topology")

EXIT_REFUSED = 1
EXIT_UNRULED = 3
EXIT_NOT_NEW_FLOW = 4

NOT_NEW_FLOW = "pas un convoi du nouveau flux"
UNRULED = "état sans règle"

COMMIT_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
# A piece name ends a tracker metadata key, and bd refuses any key outside
# [a-zA-Z_][a-zA-Z0-9_.]* (observed on bd 1.2.2): no hyphen.
PIECE_RE = re.compile(r"^[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*$")
BRANCH_RE = re.compile(r"^[^\s~^:?*\[\\]+$")
# A user story is named by its number in the Spec ("1. As a ...").
STORY_RE = re.compile(r"^[1-9][0-9]*$")
BEAD_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*-[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)*$")
ANCHOR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
ITEM_RE = re.compile(r"^(?:deviations|not_done)\.[1-9][0-9]*$")
FINDING_ITEM_RE = re.compile(r"^out_of_ticket\.[1-9][0-9]*$")
OPTION_LETTER_RE = re.compile(r"^[a-z]$")
CRITERION_RE = re.compile(r"^\s*-\s+\[[ xX]\]\s+(.*\S)\s*$")
QUESTION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
FINDING_ID_RE = re.compile(r"^F[1-9][0-9]*\.[1-9][0-9]*$")


class Refusal(RuntimeError):
    """A write that is refused, or a read that cannot be made: nothing is written."""


class NotNewFlow(RuntimeError):
    """The convoy does not carry the new-flow mark."""


# --- tracker -----------------------------------------------------------------


def run_gc(args: list[str]) -> str:
    try:
        proc = subprocess.run([GC_BIN, "--city", str(CITY), *args], capture_output=True, text=True)
    except OSError as exc:
        raise Refusal(f"impossible de lancer {GC_BIN} : {exc}") from exc
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}"
        raise Refusal(f"gc {' '.join(args[:3])} a échoué : {detail}")
    return proc.stdout


def load_convoy(convoy_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """The convoy bead and its tracked tickets, in one tracker read."""
    out = run_gc(["bd", "show", convoy_id, "--json"])
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        raise Refusal(f"gc bd show {convoy_id} a rendu un JSON illisible : {exc}") from exc
    if isinstance(data, list):
        data = data[0] if data else None
    if not isinstance(data, dict):
        raise Refusal(f"bead introuvable : {convoy_id}")
    if data.get("issue_type") != "convoy":
        raise Refusal(f"{convoy_id} n'est pas un convoi (type {data.get('issue_type')!r})")
    tickets = [
        dep for dep in data.get("dependencies") or []
        if isinstance(dep, dict) and dep.get("dependency_type") == "tracks"
    ]
    return data, tickets


def metadata_of(bead: dict[str, Any]) -> dict[str, Any]:
    metadata = bead.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def require_marked(convoy: dict[str, Any]) -> None:
    mark = metadata_of(convoy).get(KEY_MARK)
    if mark is None:
        raise NotNewFlow(convoy["id"])
    if mark != MARK:
        raise Refusal(f"{UNRULED} : le convoi {convoy['id']} porte une marque inconnue ({mark!r})")
    never_reopened(convoy)


def never_reopened(convoy: dict[str, Any]) -> None:
    """Every write of the flow passes here: none follows the closing of a
    convoy on Benjamin's words (Spec §11)."""
    closed = stored_or_none(metadata_of(convoy).get(KEY_CLOSED), closed_record)
    if closed is not None:
        raise Refusal(
            f"l'Outcome du convoi {convoy['id']} est {CLOSINGS[closed['how']]} et son convoi est fermé : rien ne le rouvre, "
            "ni lui ni ses tickets ; un défaut ou un souhait trouvé après entre comme travail nouveau, par un Planning Run")


def write_metadata(bead_id: str, values: dict[str, Any], labels: tuple[str, ...] = ()) -> None:
    """One tracker write. A key whose value is None is removed in it."""
    args = ["bd", "update", bead_id]
    for key, value in values.items():
        args += ["--unset-metadata", key] if value is None else ["--set-metadata", f"{key}={value}"]
    for label in labels:
        args += ["--add-label", label]
    run_gc(args)


def labels_of(bead: dict[str, Any]) -> list[Any]:
    labels = bead.get("labels")
    return labels if isinstance(labels, list) else []


@contextmanager
def convoy_lock(convoy_id: str) -> Iterator[None]:
    """Serialise every read-validate-write on one convoy: a counter bump is a
    read-modify-write, and a reviewer and an Evaluator write the same ticket
    in parallel."""
    lock_dir = Path(os.environ.get("CONVOY_STATE_LOCK_DIR") or os.environ.get("XDG_RUNTIME_DIR") or "/tmp")
    lock_dir.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^A-Za-z0-9._-]", "_", convoy_id)
    with (lock_dir / f"agent-factory-convoy-state-{safe_id}.lock").open("w") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def encode(record: dict[str, Any]) -> str:
    return json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


@functools.lru_cache(maxsize=None)
def flow_bound(name: str) -> int:
    """One bound of the flow (Spec §8), read where they are all set: `bounds`
    of config/delivery-flow.json under FACTORY_ROOT, and in the Factory's own
    file when that root sets none (a synthetic city that sets no bound runs
    under the Factory's)."""
    bounds = None
    for root in dict.fromkeys((Path(os.environ.get("FACTORY_ROOT") or BIN.parent), BIN.parent)):
        try:
            data = json.loads((root / SETTINGS).read_text(encoding="utf-8"))
        except FileNotFoundError:
            continue
        except (OSError, json.JSONDecodeError) as exc:
            raise Refusal(f"{SETTINGS} illisible : {exc}") from exc
        if isinstance(data, dict) and "bounds" in data:
            bounds = data["bounds"]
            break
    if not isinstance(bounds, dict):
        raise Refusal(f"aucune borne (bounds) dans {SETTINGS} : les bornes du flux s'y règlent, et nulle part ailleurs")
    value = bounds.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise Refusal(f"bounds.{name} absent ou invalide dans {SETTINGS} : {value!r} (attendu : un entier d'au moins 1)")
    return value


def resumes_max() -> int:
    return flow_bound(BOUND_RESUMES)


# --- validation shared by writes and reads -----------------------------------


def one_of(value: Any, allowed: tuple[str, ...], name: str) -> str:
    if value not in allowed:
        raise Refusal(f"{name} hors de la liste fermée : {value!r} (attendu : {', '.join(allowed)})")
    return value


def valid_commit(value: Any, name: str = "commit") -> str:
    if not isinstance(value, str) or not COMMIT_RE.match(value):
        raise Refusal(f"{name} absent ou mal formé : {value!r} (attendu : le SHA complet d'un commit)")
    return value


def valid_digest(value: Any) -> str:
    if not isinstance(value, str) or not DIGEST_RE.match(value):
        raise Refusal(f"digest absent ou mal formé : {value!r} (attendu : sha256:<64 hex>)")
    return value


def counter_value(raw: Any, name: str) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        raise Refusal(f"compteur {name} incohérent : {raw!r} n'est pas un entier positif ou nul")
    return raw


def check_ticket_counters(counters: dict[str, int]) -> None:
    # Spec §8: a correction round counts among the K resumes.
    if counters["correction_rounds"] > counters["resumes"]:
        raise Refusal(
            f"compteurs incohérents : correction_rounds ({counters['correction_rounds']}) "
            f"dépasse resumes ({counters['resumes']}), or un tour de correction compte parmi les reprises"
        )


def valid_kind(value: Any) -> str:
    if value is None:
        raise Refusal(f"genre absent (attendu : {', '.join(TICKET_KINDS)} ; aucun genre par défaut)")
    return one_of(value, TICKET_KINDS, "genre")


def valid_demonstration_line(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or "\n" in value:
        raise Refusal(f"ligne de démonstration absente ou mal formée : {value!r} (attendu : une ligne non vide)")
    return value


def valid_user_stories(value: Any) -> list[str]:
    """The numbers of the user stories a vertical_slice covers, as given."""
    if (
        not isinstance(value, list) or not value
        or any(not isinstance(story, str) or not STORY_RE.match(story) for story in value)
        or len(set(value)) != len(value)
    ):
        raise Refusal(
            f"user stories couvertes absentes ou mal formées : {value!r} "
            "(attendu : au moins un numéro de user story de la Spec, chacun une seule fois)"
        )
    return value


def check_demonstration_line(kind: str, line: Any) -> None:
    """Spec §2: a slice and a repair carry a demonstration line; a
    prefactoring changes no behavior, so it has nothing to demonstrate."""
    if kind in KINDS_WITH_DEMONSTRATION:
        if line is None:
            raise Refusal(f"{kind} sans ligne de démonstration")
        valid_demonstration_line(line)
    elif line is not None:
        raise Refusal("un prefactoring ne porte pas de ligne de démonstration : il ne change aucun comportement")


def check_user_stories(kind: str, stories: Any) -> None:
    """Spec §2: a vertical_slice covers at least one user story. A
    prefactoring names the slice it unblocks and a repair what it restores:
    neither covers a story."""
    if kind == KIND_COVERING_STORIES:
        if stories is None:
            raise Refusal(f"{kind} sans user story couverte")
        valid_user_stories(stories)
    elif stories is not None:
        raise Refusal(f"un {kind} ne porte pas de user stories couvertes : seule une vertical_slice en couvre")


def check_launch_recipe(kind: str, raw: Any) -> None:
    """Spec §2: a project without a launch recipe has it established by its
    first slice. The stored value is the boolean the tracker makes of `true`."""
    if raw is not True:
        raise Refusal(f"valeur inconnue : {raw!r} (attendu : true, sur la tranche qui établit la recette de lancement)")
    if kind != KIND_COVERING_STORIES:
        raise Refusal(f"un {kind} n'établit pas la recette de lancement : seule une vertical_slice le fait")


def check_prototype_fold(kind: str, raw: Any) -> None:
    """Spec §3: the Prototype Fold is an ordinary vertical_slice. The stored
    value is the boolean the tracker makes of `true`."""
    if raw is not True:
        raise Refusal(f"valeur inconnue : {raw!r} (attendu : true, sur la tranche qui est le Prototype Fold)")
    if kind != KIND_COVERING_STORIES:
        raise Refusal(f"un {kind} n'est pas un Prototype Fold : seule une vertical_slice l'est")


# What a vertical_slice may be besides a slice, frozen with the approved
# graph: stored key, rendered name, its check, and what a refusal calls it.
SLICE_FLAGS = (
    (KEY_LAUNCH_RECIPE, "establishes_launch_recipe", check_launch_recipe, "établir la recette de lancement"),
    (KEY_PROTOTYPE_FOLD, "prototype_fold", check_prototype_fold, "être le Prototype Fold"),
)


def stored_user_stories(raw: Any) -> list[str]:
    return valid_user_stories(stored_record(raw, ("stories",))["stories"])


def stored_record(raw: Any, required: tuple[str, ...], optional: tuple[str, ...] = ()) -> dict[str, Any]:
    """A record this command wrote: a JSON object with exactly the known fields."""
    if not isinstance(raw, str):
        raise Refusal(f"valeur illisible : {raw!r}")
    try:
        record = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise Refusal(f"valeur illisible : {raw!r}") from exc
    if not isinstance(record, dict):
        raise Refusal(f"valeur illisible : {raw!r}")
    missing = [field for field in required if field not in record]
    unknown = [field for field in record if field not in required + optional]
    if missing or unknown:
        raise Refusal(f"champs manquants {missing} ou inconnus {unknown} dans {raw!r}")
    return record


def acceptance_criteria(description: Any) -> list[str]:
    """The acceptance criteria of a ticket, in order: the checkbox lines
    under "## Acceptance criteria" of its description. The criterion -> test
    table of bin/tdd-step numbers them from 1."""
    criteria, inside = [], False
    for line in description.splitlines() if isinstance(description, str) else []:
        if line.startswith("## "):
            inside = line.strip().lower() == ACCEPTANCE_HEADING
            continue
        match = CRITERION_RE.match(line)
        if inside and match:
            criteria.append(match.group(1))
    return criteria


def criteria_digest(criteria: list[str]) -> str:
    """The fingerprint of the acceptance criteria of a ticket, in order."""
    return "sha256:" + hashlib.sha256(json.dumps(criteria, ensure_ascii=False).encode("utf-8")).hexdigest()


def criteria_record(raw: Any) -> dict[str, Any]:
    """The acceptance criteria as `mark` froze them with the approved graph:
    their fingerprint and the digest of the graph the ticket was published
    under (None when the publication door wrote none)."""
    record = stored_record(raw, ("digest", "graph_digest", "at"))
    valid_digest(record["digest"])
    if record["graph_digest"] is not None and not isinstance(record["graph_digest"], str):
        raise Refusal(f"digest du graphe mal formé : {record['graph_digest']!r}")
    return record


def frozen_criteria(ticket: dict[str, Any]) -> dict[str, Any]:
    """What `mark` freezes of a ticket's criteria: read on the ticket as the
    publication door has just written it."""
    graph_digest = metadata_of(ticket).get(KEY_GRAPH_DIGEST)
    return {"digest": criteria_digest(acceptance_criteria(ticket.get("description"))),
            "graph_digest": graph_digest if isinstance(graph_digest, str) and graph_digest else None, "at": now()}


def validated_prototype(description: Any) -> dict[str, Any] | None:
    """The reference of the Validated Prototype the publication door posed
    in an interface ticket (T36): branch, commit, path, states. None when
    the ticket carries no such section: it touches no screen."""
    fields: dict[str, str] = {}
    inside = found = False
    for line in description.splitlines() if isinstance(description, str) else []:
        if line.startswith("## "):
            inside = line.strip().lower() == PROTOTYPE_HEADING
            found = found or inside
            continue
        match = re.match(r"^\s*-\s+([^:]+?)\s+:\s+(.*\S)\s*$", line) if inside else None
        if match and match.group(1) in PROTOTYPE_FIELDS:
            fields[PROTOTYPE_FIELDS[match.group(1)]] = match.group(2).strip("`")
    if not found:
        return None
    missing = [name for name in PROTOTYPE_FIELDS.values() if name not in fields]
    if missing:
        raise Refusal(f"référence du Validated Prototype incomplète dans le ticket (champs absents : {', '.join(missing)})")
    valid_commit(fields["commit"], "commit du Validated Prototype")
    valid_branch(fields["branch"], "branche du Validated Prototype")
    states = [state.strip() for state in fields["states"].split(",") if state.strip()]
    if not states or not fields["path"].strip("/"):
        raise Refusal("référence du Validated Prototype sans chemin ou sans état")
    return {"branch": fields["branch"], "commit": fields["commit"], "path": fields["path"].strip("/"), "states": states}


def ticket_end_conditions(value: Any) -> list[dict[str, Any]]:
    """The nine verdicts of the ticket-end gate, in the order of its closed
    list, every one passing: the only record that closes a ticket."""
    if not isinstance(value, list) or len(value) != len(TICKET_END_CONDITIONS):
        raise Refusal(
            f"relevé de la porte de fin de ticket sans ses neuf verdicts (attendu : {', '.join(TICKET_END_CONDITIONS)})")
    conditions = []
    for number, (name, entry) in enumerate(zip(TICKET_END_CONDITIONS, value), start=1):
        if not isinstance(entry, dict) or set(entry) != {"number", "name", "verdict", "detail"}:
            raise Refusal(f"verdict de la condition {number} mal formé : {entry!r} (attendu : number, name, verdict, detail)")
        if entry["number"] != number or entry["name"] != name:
            raise Refusal(f"condition {number} attendue : {name} ; reçu : {entry['number']!r} {entry['name']!r}")
        if entry["verdict"] != TICKET_END_PASS:
            raise Refusal(
                f"condition {number} ({name}) non réunie ({entry['verdict']!r}) : la porte ne ferme un ticket que "
                "sur ses neuf conditions réunies")
        conditions.append({"number": number, "name": name, "verdict": TICKET_END_PASS,
                           "detail": single_line(entry["detail"], f"précision de la condition {number}")})
    return conditions


def ticket_end_record(raw: Any) -> dict[str, Any]:
    """The record of the ticket-end gate: the commit of the ticket that was
    merged, the version of the list and its nine verdicts."""
    record = stored_record(raw, ("at", "commit", "version", "conditions"))
    valid_commit(record["commit"])
    if record["version"] != TICKET_END_VERSION:
        raise Refusal(f"version de la liste de conditions inconnue : {record['version']!r} (attendu : {TICKET_END_VERSION})")
    record["conditions"] = ticket_end_conditions(record["conditions"])
    return record


def single_line(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\n" in value:
        raise Refusal(f"{name} absente ou mal formée : {value!r} (attendu : une ligne non vide)")
    return value.strip()


def tdd_record(step: str, raw: Any) -> dict[str, Any]:
    """One proven step of a ticket's TDD: the commit it was proven at, the
    start commit of a red or a prefactoring, the reason of an amendment."""
    one_of(step, TDD_STEPS, "étape du TDD")
    record = stored_record(raw, ("commit", "at"), ("base", "reason"))
    valid_commit(record["commit"])
    if (step in TDD_STEPS_WITH_BASE) != ("base" in record):
        raise Refusal(f"étape {step} : commit de départ {'absent' if step in TDD_STEPS_WITH_BASE else 'inattendu'}")
    if "base" in record:
        valid_commit(record["base"], "commit de départ")
    if (step == "amendment") != ("reason" in record):
        raise Refusal(f"étape {step} : raison {'absente' if step == 'amendment' else 'inattendue'}")
    if "reason" in record:
        single_line(record["reason"], "raison de l'amendement")
    return record


def stop_record(raw: Any) -> dict[str, Any]:
    """Why a script stopped the ticket (Spec §5): its work does not go on."""
    record = stored_record(raw, ("reason", "detail", "at"), ("raised",))
    one_of(record["reason"], STOP_REASONS, "raison d'arrêt")
    single_line(record["detail"], "précision de l'arrêt")
    if "raised" in record:
        single_line(record["raised"], "heure de la remontée de l'arrêt")
    return record


def review_fingerprints(value: Any) -> dict[str, str]:
    """What a review of criterion tests is bound to: the fingerprint of each
    file the freeze will seal."""
    if not isinstance(value, dict) or not value:
        raise Refusal(f"empreintes des tests absentes ou mal formées : {value!r} (attendu : chemin → sha256:<64 hex>)")
    for path, digest in value.items():
        if not isinstance(path, str) or not path.strip():
            raise Refusal(f"empreintes des tests : chemin mal formé : {path!r}")
        valid_digest(digest)
    return value


def review_criteria(value: Any, files: dict[str, str]) -> dict[str, list[str]]:
    """The criterion -> test table under review; every test sits in a file
    that has a fingerprint."""
    if not isinstance(value, dict) or not value:
        raise Refusal(f"table critère → test absente ou mal formée : {value!r}")
    for number, ids in value.items():
        if not isinstance(number, str) or not STORY_RE.match(number):
            raise Refusal(f"numéro de critère mal formé : {number!r}")
        if not isinstance(ids, list) or not ids or any(not isinstance(i, str) or not i.strip() for i in ids):
            raise Refusal(f"critère {number} sans test à relire")
        for test_id in ids:
            if test_id.partition("::")[0] not in files:
                raise Refusal(f"test sans empreinte de son fichier : {test_id}")
    return value


def review_tests(criteria: dict[str, list[str]]) -> list[str]:
    return list(dict.fromkeys(test_id for number in sorted(criteria, key=int) for test_id in criteria[number]))


def review_request(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"commit", "files", "criteria", "launches", "at"}:
        raise Refusal(f"demande de relecture mal formée : {value!r}")
    valid_commit(value["commit"], "commit de la relecture")
    review_criteria(value["criteria"], review_fingerprints(value["files"]))
    launches = value["launches"]
    if not isinstance(launches, list) or len(launches) > TEST_REVIEW_MAX_LAUNCHES:
        raise Refusal(f"lancements de relecture mal formés : {launches!r}")
    for launch in launches:
        if not isinstance(launch, dict) or set(launch) != {"bead", "at"} or not isinstance(launch["bead"], str) \
                or not BEAD_ID_RE.match(launch["bead"]):
            raise Refusal(f"lancement de relecture mal formé : {launch!r}")
    return value


def review_round(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"commit", "files", "verdict", "tests", "recorded_by", "at"}:
        raise Refusal(f"passe de relecture mal formée : {value!r}")
    valid_commit(value["commit"], "commit de la relecture")
    review_fingerprints(value["files"])
    one_of(value["verdict"], VERDICT_STATES, "verdict de relecture")
    tests = value["tests"]
    if not isinstance(tests, dict) or not tests:
        raise Refusal(f"passe de relecture sans réponse par test : {tests!r}")
    for test_id, answer in tests.items():
        if not isinstance(answer, dict) or answer.get("state") not in VERDICT_STATES or set(answer) - {"state", "reason"}:
            raise Refusal(f"réponse de relecture mal formée pour {test_id} : {answer!r}")
        if (answer["state"] == "unfavorable") != ("reason" in answer):
            raise Refusal(f"réponse de relecture pour {test_id} : raison absente d'un refus, ou donnée sans refus")
    if (value["verdict"] == "unfavorable") != any(a["state"] == "unfavorable" for a in tests.values()):
        raise Refusal("verdict de relecture qui n'est pas celui de ses réponses")
    return value


def test_review_record(raw: Any) -> dict[str, Any]:
    """The review of a ticket's criterion tests before the freeze (T13): the
    passes a reviewer recorded, each bound to a commit and to the
    fingerprints of the tests it read, and the request that is open."""
    record = stored_record(raw, ("rounds",), ("request",))
    if not isinstance(record["rounds"], list):
        raise Refusal(f"passes de relecture mal formées : {record['rounds']!r}")
    for value in record["rounds"]:
        review_round(value)
    if "request" in record:
        review_request(record["request"])
    return record


def review_refusals(record: dict[str, Any]) -> int:
    return sum(1 for value in record["rounds"] if value["verdict"] == "unfavorable")


def normalized_model(model: str) -> str:
    return re.sub(r"[^a-z0-9]", "", model.lower())


def models_record(raw: Any) -> dict[str, Any]:
    """The agent, provider and model each delivery role ran on for this
    ticket (T14, Spec §6: the reviewer has another model than the author)."""
    record = stored_record(raw, (), MODEL_ROLES)
    for role, entry in record.items():
        if not isinstance(entry, dict) or set(entry) != {"agent", "provider", "model", "at"}:
            raise Refusal(f"relevé du rôle {role} mal formé : {entry!r}")
        for name in ("agent", "provider", "model"):
            single_line(entry[name], f"valeur {name} du rôle {role}")
    return record


def review_models(value: Any) -> dict[str, Any]:
    """The models a round of the code review is given under: never left out,
    `same_model` is null when one of the two is not recorded."""
    if not isinstance(value, dict) or set(value) != {"author", "reviewer", "same_model"}:
        raise Refusal(f"modèles de la revue mal formés : {value!r}")
    for role in ("author", "reviewer"):
        if value[role] is not None:
            single_line(value[role], f"modèle du rôle {role}")
    known = value["author"] is not None and value["reviewer"] is not None
    if (value["same_model"] is None) == known or not isinstance(value["same_model"], (bool, type(None))):
        raise Refusal(f"mention des modèles incohérente : {value!r}")
    return value


def review_questions(value: Any) -> list[dict[str, str]]:
    """The closed questions a code review answers about the tests (Spec §6,
    « troisième vérification »): asked by code, one answer each."""
    if not isinstance(value, list):
        raise Refusal(f"questions fermées mal formées : {value!r}")
    for question in value:
        if not isinstance(question, dict) or set(question) != {"id", "kind", "subject", "text"} \
                or not isinstance(question["id"], str) or not QUESTION_ID_RE.match(question["id"]):
            raise Refusal(f"question fermée mal formée : {question!r}")
        one_of(question["kind"], QUESTION_KINDS, "genre de question fermée")
        single_line(question["subject"], "sujet de la question fermée")
        single_line(question["text"], "question fermée")
    if len({question["id"] for question in value}) != len(value):
        raise Refusal("questions fermées : un identifiant est donné deux fois")
    return value


def citation_of(finding: dict[str, Any]) -> tuple[dict[str, str] | None, str | None]:
    """The citation a finding gives, and why it does not hold when it does
    not (Spec §6: a finding blocks only if it cites a line of the Spec, of
    the ticket or a written rule of the repository)."""
    citation = finding.get("citation")
    if citation is None:
        return None, "constat sans citation d'une ligne de la Spec, du ticket ou d'une règle écrite du dépôt"
    wanted = ", ".join(CITATION_SOURCES)
    if not isinstance(citation, dict) or set(citation) - {"source", "quote", "path"}:
        return None, f"citation mal formée : attendu source ({wanted}), quote et, pour repo_rule, path"
    source, quote, path = citation.get("source"), citation.get("quote"), citation.get("path")
    if source not in CITATION_SOURCES:
        return None, f"citation d'une source hors de la liste fermée : {source!r} (attendu : {wanted})"
    if not isinstance(quote, str) or not quote.strip():
        return None, "citation sans la ligne citée (quote)"
    if (source == "repo_rule") != (isinstance(path, str) and bool(path.strip())):
        return None, "citation mal formée : path nomme le fichier d'une règle écrite du dépôt, et seulement elle"
    kept = {"source": source, "quote": " ".join(quote.split())[:MAX_FINDING_LINE]}
    if source == "repo_rule":
        kept["path"] = path.strip()
    refused = finding.get("citation_refused")
    if refused is not None:
        return kept, " ".join(str(refused).split())[:MAX_FINDING_LINE] or "citation refusée"
    return kept, None


def review_finding(value: Any) -> dict[str, Any]:
    """One Review Finding as stored. A Blocking Finding carries its
    citation, or the closed question whose answer « non » made it."""
    if not isinstance(value, dict) or not {"id", "axis", "blocking", "summary"} <= set(value) \
            or set(value) - {"id", "axis", "blocking", "summary", "citation", "demoted", "question"}:
        raise Refusal(f"constat de revue mal formé : {value!r}")
    if not isinstance(value["id"], str) or not FINDING_ID_RE.match(value["id"]):
        raise Refusal(f"identifiant de constat mal formé : {value['id']!r}")
    one_of(value["axis"], (*REVIEW_AXES, AXIS_TESTS), "axe de revue")
    single_line(value["summary"], "résumé du constat")
    if not isinstance(value["blocking"], bool):
        raise Refusal(f"constat {value['id']} : blocking mal formé : {value['blocking']!r}")
    if "citation" in value and citation_of({"citation": value["citation"]})[1] is not None:
        raise Refusal(f"constat {value['id']} : citation mal formée")
    if value["blocking"] and ("demoted" in value or not ("citation" in value or "question" in value)):
        raise Refusal(f"constat {value['id']} : bloquant sans citation ni question fermée")
    return value


def blocking_ids(round_: dict[str, Any]) -> list[str]:
    """The Blocking Findings of a review round."""
    return [finding["id"] for finding in round_.get("findings", []) if finding["blocking"]]


def code_review_request(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"kind", "commit", "base", "questions", "launches", "models", "at"}:
        raise Refusal(f"demande de revue de code mal formée : {value!r}")
    one_of(value["kind"], CODE_REVIEW_KINDS, "genre de revue")
    valid_commit(value["commit"], "commit de la revue")
    valid_commit(value["base"], "commit de départ de la revue")
    review_questions(value["questions"])
    review_models(value["models"])
    launches = value["launches"]
    if not isinstance(launches, list) or len(launches) > CODE_REVIEW_MAX_LAUNCHES:
        raise Refusal(f"lancements de revue mal formés : {launches!r}")
    for launch in launches:
        if not isinstance(launch, dict) or set(launch) != {"bead", "at"} or not isinstance(launch["bead"], str) \
                or not BEAD_ID_RE.match(launch["bead"]):
            raise Refusal(f"lancement de revue mal formé : {launch!r}")
    return value


def code_review_round(value: Any) -> dict[str, Any]:
    common = {"kind", "commit", "base", "verdict", "models", "recorded_by", "at"}
    if not isinstance(value, dict) or not common <= set(value):
        raise Refusal(f"passe de revue de code mal formée : {value!r}")
    kind = one_of(value["kind"], CODE_REVIEW_KINDS, "genre de revue")
    own = {"findings", "answers", "responses"} if kind == "review" else {"judgements"}
    required = own - {"responses"}
    if set(value) - common - own or not required <= set(value):
        raise Refusal(f"passe de revue de code mal formée : {value!r}")
    valid_commit(value["commit"], "commit de la revue")
    valid_commit(value["base"], "commit de départ de la revue")
    one_of(value["verdict"], VERDICT_STATES, "verdict de revue")
    review_models(value["models"])
    single_line(value["recorded_by"], "session du relecteur")
    if kind == "judgement":
        judgements = value["judgements"]
        if not isinstance(judgements, dict) or not judgements:
            raise Refusal(f"jugement sans réponse par constat : {judgements!r}")
        for finding_id, answer in judgements.items():
            if not isinstance(answer, dict) or answer.get("state") not in VERDICT_STATES or set(answer) - {"state", "reason"} \
                    or (answer["state"] == "unfavorable") != ("reason" in answer):
                raise Refusal(f"jugement mal formé pour {finding_id} : {answer!r}")
        refused = any(answer["state"] == "unfavorable" for answer in judgements.values())
    else:
        if not isinstance(value["findings"], list) or not isinstance(value["answers"], dict):
            raise Refusal(f"passe de revue de code mal formée : {value!r}")
        for finding in value["findings"]:
            review_finding(finding)
        for question_id, answer in value["answers"].items():
            if not isinstance(answer, dict) or answer.get("answer") not in QUESTION_ANSWERS \
                    or set(answer) - {"answer", "reason"} or (answer["answer"] == "non") != ("reason" in answer):
                raise Refusal(f"réponse mal formée à la question {question_id} : {answer!r}")
        responses = value.get("responses", {})
        if not isinstance(responses, dict) or set(responses) - set(blocking_ids(value)):
            raise Refusal(f"réponses aux constats mal formées : {responses!r}")
        for finding_id, response in responses.items():
            given = response.get("response") if isinstance(response, dict) else None
            if given not in FINDING_RESPONSES or set(response) != {"response", "at", "commit" if given == "fixed" else "reason"}:
                raise Refusal(f"réponse mal formée au constat {finding_id} : {response!r}")
        refused = bool(blocking_ids(value))
    if (value["verdict"] == "unfavorable") != refused:
        raise Refusal("verdict de revue qui n'est pas celui de ses constats")
    return value


def code_review_record(raw: Any) -> dict[str, Any]:
    """The code review of a ticket (T14): the rounds reviewer sessions
    recorded, each bound to the commit it judged, and the request that is
    open. A judgement round follows the review round it judges."""
    record = stored_record(raw, ("rounds",), ("request",))
    if not isinstance(record["rounds"], list):
        raise Refusal(f"passes de revue de code mal formées : {record['rounds']!r}")
    previous = None
    for value in record["rounds"]:
        code_review_round(value)
        if value["kind"] == "judgement" and (
                previous is None or previous["kind"] != "review" or previous["verdict"] != "unfavorable"
                or set(value["judgements"]) != set(blocking_ids(previous))):
            raise Refusal("jugement qui ne suit pas la revue défavorable qu'il juge")
        previous = value
    if "request" in record:
        code_review_request(record["request"])
    return record


def code_review_state(record: dict[str, Any]) -> dict[str, Any]:
    """What the code review says of the ticket now: the verdict of its last
    round, the commit it judged, and the Blocking Findings that have no
    favorable verdict (Spec §6: code refuses the merge while there is one)."""
    last = record["rounds"][-1] if record["rounds"] else None
    if last is None:
        return {"verdict": None, "commit": None, "unsettled": []}
    if last["kind"] == "review":
        unsettled = blocking_ids(last)
    else:
        unsettled = [finding_id for finding_id, answer in last["judgements"].items() if answer["state"] == "unfavorable"]
    return {"verdict": last["verdict"], "commit": last["commit"], "unsettled": unsettled}


def code_review_rendered(raw: Any) -> dict[str, Any]:
    record = code_review_record(raw)
    return {**record, "state": code_review_state(record)}


def evaluation_roles(value: Any) -> dict[str, Any]:
    """The providers the author and the Evaluator of a ticket ran on (Spec
    §7): never left out, `same_provider` is null when one is not recorded."""
    if not isinstance(value, dict) or set(value) != {"author", "evaluator", "same_provider", "other_declared"}:
        raise Refusal(f"relevé des rôles de l'évaluation mal formé : {value!r}")
    for role in ("author", "evaluator"):
        entry = value[role]
        if entry is not None and (not isinstance(entry, dict) or set(entry) != {"provider", "supplier"}
                                  or any(not isinstance(v, str) or not v.strip() for v in entry.values())):
            raise Refusal(f"relevé du rôle {role} de l'évaluation mal formé : {entry!r}")
    same = value["same_provider"]
    if same is not None and not isinstance(same, bool):
        raise Refusal(f"relevé des rôles de l'évaluation mal formé : same_provider {same!r}")
    if (same is None) != (value["author"] is None or value["evaluator"] is None):
        raise Refusal("relevé des rôles de l'évaluation incohérent : same_provider ne dit pas ce que disent ses rôles")
    other = value["other_declared"]
    if not isinstance(other, list) or any(not isinstance(name, str) or not name.strip() for name in other):
        raise Refusal(f"relevé des rôles de l'évaluation mal formé : other_declared {other!r}")
    return value


def evaluation_environment(value: Any, launched: bool) -> list[dict[str, Any]]:
    """The launched products an evaluation is made on: one per dataset, each
    at its own address, with the launch record of bin/project-launch while
    it runs (`launched`)."""
    fields = {"dataset", "address"} | ({"state_file"} if launched else set())
    if not isinstance(value, list) or not value:
        raise Refusal(f"environnement d'évaluation absent ou mal formé : {value!r}")
    for entry in value:
        if not isinstance(entry, dict) or set(entry) != fields:
            raise Refusal(f"environnement d'évaluation mal formé : {entry!r}")
        if not isinstance(entry["address"], str) or not ADDRESS_RE.match(entry["address"]):
            raise Refusal(f"adresse du produit lancé mal formée : {entry['address']!r}")
        if entry["dataset"] is not None and (not isinstance(entry["dataset"], str) or not entry["dataset"].strip()):
            raise Refusal(f"jeu de données du produit lancé mal formé : {entry['dataset']!r}")
        if launched:
            single_line(entry["state_file"], "relevé de lancement")
    if len({entry["address"] for entry in value}) != len(value):
        raise Refusal("environnement d'évaluation mal formé : deux produits lancés à la même adresse")
    return value


def evaluation_criteria(value: Any) -> list[str]:
    if not isinstance(value, list) or not value or any(not isinstance(text, str) or not text.strip() for text in value):
        raise Refusal(f"critères de l'évaluation absents ou mal formés : {value!r}")
    return value


def evaluation_launches(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) > EVALUATION_MAX_LAUNCHES:
        raise Refusal(f"lancements d'évaluation mal formés : {value!r}")
    for launch in value:
        if not isinstance(launch, dict) or set(launch) != {"bead", "at"} or not isinstance(launch["bead"], str) \
                or not BEAD_ID_RE.match(launch["bead"]):
            raise Refusal(f"lancement d'évaluation mal formé : {launch!r}")
    return value


def evaluation_request(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"commit", "criteria", "demonstration_line", "roles", "environment",
                                                      "launches", "at"}:
        raise Refusal(f"demande d'évaluation mal formée : {value!r}")
    valid_commit(value["commit"], "commit de l'évaluation")
    evaluation_criteria(value["criteria"])
    valid_demonstration_line(value["demonstration_line"])
    evaluation_roles(value["roles"])
    evaluation_environment(value["environment"], launched=True)
    evaluation_launches(value["launches"])
    return value


def evaluation_item(value: Any, what: str) -> dict[str, Any]:
    """One state of an evaluation: « observé », « non observé » or
    « inobservable », always with the piece of evidence it rests on."""
    if not isinstance(value, dict) or not {"text", "state", "evidence"} <= set(value) \
            or set(value) - {"number", "text", "state", "evidence", "reason", "cause"}:
        raise Refusal(f"état d'évaluation mal formé pour {what} : {value!r}")
    state = one_of(value["state"], EVALUATION_STATES, f"état de {what}")
    if not isinstance(value["evidence"], str) or not PIECE_RE.match(value["evidence"]):
        raise Refusal(f"{what} : état sans pièce de preuve : {value['evidence']!r}")
    if (state != "observed") != ("reason" in value):
        raise Refusal(f"{what} : raison absente d'un état qui n'est pas « observé », ou donnée avec « observé »")
    if (state == "unobservable") != ("cause" in value):
        raise Refusal(f"{what} : cause absente d'un « inobservable », ou donnée avec un autre état")
    if "cause" in value:
        one_of(value["cause"], UNOBSERVABLE_CAUSES, f"cause de l'inobservable de {what}")
    return value


def evaluation_items(round_: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Every state of an evaluation round, named: the criteria in order,
    then the demonstration line."""
    named = [(f"critère {item['number']}", item) for item in round_["criteria"]]
    return named + [("ligne de démonstration", round_["demonstration_line"])]


def evaluation_outcome(items: list[tuple[str, dict[str, Any]]]) -> str:
    """Spec §7: what code makes of the states. Favorable only when every
    state is « observé ». An « inobservable » by the criterion goes back to
    the Planning Run, a « non observé » to the author; when the environment
    alone hid something, it is an outage, not a refusal."""
    states = [item for _, item in items]
    if any(item["state"] == "unobservable" and item["cause"] == "criterion" for item in states):
        return "planning_exception"
    if any(item["state"] == "not_observed" for item in states):
        return "return_to_author"
    if any(item["state"] == "unobservable" for item in states):
        return "environment_outage"
    return "favorable"


def verdict_of_outcome(outcome: str) -> str | None:
    """An outage is neither an agreement nor a refusal: it gives no verdict."""
    return {"favorable": "favorable", "environment_outage": None}.get(outcome, "unfavorable")


def evaluation_round(value: Any) -> dict[str, Any]:
    common = {"kind", "commit", "outcome", "verdict", "at"}
    if not isinstance(value, dict) or not common <= set(value):
        raise Refusal(f"passe d'évaluation mal formée : {value!r}")
    kind = one_of(value["kind"], EVALUATION_KINDS, "genre d'évaluation")
    valid_commit(value["commit"], "commit de l'évaluation")
    outcome = one_of(value["outcome"], EVALUATION_OUTCOMES, "issue de l'évaluation")
    if value["verdict"] != verdict_of_outcome(outcome):
        raise Refusal("verdict d'évaluation qui n'est pas celui de son issue")
    if kind == "startup":
        # A prefactoring: no Evaluator session, code checked that the product
        # starts and that its probe answers (Spec §7).
        if set(value) - common - {"started", "evidence", "environment", "detail"} or not isinstance(value.get("started"), bool):
            raise Refusal(f"contrôle de démarrage mal formé : {value!r}")
        if value["started"]:
            if not isinstance(value.get("evidence"), str) or not PIECE_RE.match(value["evidence"]) or "detail" in value:
                raise Refusal(f"contrôle de démarrage sans pièce de preuve : {value!r}")
            evaluation_environment(value.get("environment"), launched=False)
        else:
            single_line(value.get("detail"), "précision du démarrage manqué")
            if "evidence" in value or "environment" in value:
                raise Refusal(f"contrôle de démarrage mal formé : {value!r}")
        if outcome != ("favorable" if value["started"] else "return_to_author"):
            raise Refusal("issue du contrôle de démarrage qui n'est pas celle de son résultat")
        return value
    if set(value) != common | {"criteria", "demonstration_line", "roles", "environment", "recorded_by"}:
        raise Refusal(f"passe d'évaluation mal formée : {value!r}")
    if not isinstance(value["criteria"], list) or not value["criteria"]:
        raise Refusal(f"passe d'évaluation sans état par critère : {value['criteria']!r}")
    for position, item in enumerate(value["criteria"], start=1):
        if evaluation_item(item, f"critère {position}").get("number") != position:
            raise Refusal(f"critère {position} : numéro absent ou hors de l'ordre des critères")
    if "number" in evaluation_item(value["demonstration_line"], "ligne de démonstration"):
        raise Refusal("ligne de démonstration : numéro inattendu")
    evaluation_roles(value["roles"])
    evaluation_environment(value["environment"], launched=False)
    single_line(value["recorded_by"], "session de l'Evaluator")
    if outcome != evaluation_outcome(evaluation_items(value)):
        raise Refusal("issue d'évaluation qui n'est pas celle de ses états")
    return value


def evaluation_record(raw: Any) -> dict[str, Any]:
    """The Ticket Evaluation of a ticket (T15): the rounds recorded, each
    bound to the commit of the launched product, the request that is open,
    and the launch records of the products still to stop (`live`)."""
    record = stored_record(raw, ("rounds",), ("request", "live"))
    if not isinstance(record["rounds"], list):
        raise Refusal(f"passes d'évaluation mal formées : {record['rounds']!r}")
    for value in record["rounds"]:
        evaluation_round(value)
    if "request" in record:
        evaluation_request(record["request"])
    if "live" in record:
        live = record["live"]
        if not isinstance(live, list) or not live or any(not isinstance(path, str) or not path.strip() for path in live):
            raise Refusal(f"produits lancés à arrêter mal formés : {live!r}")
    return record


def evaluation_state(record: dict[str, Any]) -> dict[str, Any]:
    """What the evaluation says of the ticket now: the issue of its last
    round, the commit it was made at, and each state that is not « observé »."""
    last = record["rounds"][-1] if record["rounds"] else None
    state: dict[str, Any] = {"verdict": None, "outcome": None, "commit": None, "not_observed": [], "unobservable": []}
    if last is None:
        return state
    state.update(verdict=last["verdict"], outcome=last["outcome"], commit=last["commit"])
    if last["kind"] == "startup":
        if not last["started"]:
            state["not_observed"] = ["démarrage du produit"]
        return state
    for name, item in evaluation_items(last):
        if item["state"] == "not_observed":
            state["not_observed"].append(name)
        elif item["state"] == "unobservable":
            state["unobservable"].append({"what": name, "cause": item["cause"]})
    return state


def evaluation_rendered(raw: Any) -> dict[str, Any]:
    record = evaluation_record(raw)
    return {**record, "state": evaluation_state(record)}


def handoff_section(name: str, value: Any, partial: bool) -> None:
    """One section of a Ticket Handoff: content, or the word for "nothing";
    never empty, never left out, unless the Handoff is a partial one."""
    if value is None:
        if partial:
            return
        raise Refusal(f"rubrique {name} absente : ni contenu ni « {HANDOFF_NOTHING} »")
    if value == HANDOFF_NOTHING:
        return
    if not isinstance(value, list) or not value:
        raise Refusal(
            f"rubrique {name} mal formée : {value!r} (attendu : une liste non vide, ou « {HANDOFF_NOTHING} »)")
    for item in value:
        if name == "not_done" and isinstance(item, dict):
            paths = item.get("paths", [])
            if set(item) - {"what", "paths"} or not isinstance(paths, list) or any(
                    not isinstance(path, str) or not path.strip() for path in paths):
                raise Refusal(f"rubrique {name} : élément mal formé : {item!r} (attendu : what, et paths en option)")
            item = item.get("what")
        if not isinstance(item, str) or not item.strip() or "\n" in item:
            raise Refusal(f"rubrique {name} : élément absent ou mal formé : {item!r} (attendu : une ligne non vide)")


def handoff_record(raw: Any, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    """A Ticket Handoff: the four sections of the author and the records of
    the code, tied to the commit they were taken at. A complete Handoff has
    every section and its records; a partial one (an interrupted session)
    says so. With `evidence` (the ticket's stored fingerprints, at a write),
    the records must be the ones bin/ticket-exit sealed at that commit; a
    read does not ask it, since a new exit replaces the piece first."""
    record = stored_record(raw, ("sections", "partial", "commit", "at"), ("records",))
    partial = record["partial"]
    if not isinstance(partial, bool):
        raise Refusal(f"champ partial mal formé : {partial!r} (attendu : true ou false)")
    valid_commit(record["commit"], "commit du Handoff")
    sections = record["sections"]
    if not isinstance(sections, dict) or set(sections) - set(HANDOFF_SECTIONS):
        raise Refusal(f"rubriques inconnues dans le Handoff (attendu : {', '.join(HANDOFF_SECTIONS)})")
    for name in HANDOFF_SECTIONS:
        handoff_section(name, sections.get(name), partial)
    if "records" not in record:
        if not partial:
            raise Refusal("Handoff sans relevés : ils sont écrits par du code, à chaque sortie")
    elif not isinstance(record["records"], dict):
        raise Refusal(f"relevés mal formés : {record['records']!r}")
    elif evidence is not None:
        sealed = evidence.get(HANDOFF_RECORDS_PIECE)
        if not isinstance(sealed, dict) or sealed.get("commit") != record["commit"]:
            raise Refusal(
                f"relevés sans pièce {HANDOFF_RECORDS_PIECE} au commit du Handoff : "
                "ils sont écrits par du code (bin/ticket-exit), jamais fournis")
    return record


def names_of(value: Any, what: str) -> list[str]:
    if not isinstance(value, list) or not value or any(
            not isinstance(name, str) or not name.strip() or "\n" in name for name in value) or len(set(value)) != len(value):
        raise Refusal(f"{what} : liste absente, vide ou mal formée ({value!r})")
    return value


def fidelity_record(raw: Any, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """The result of the mechanical fidelity check of a ticket (T16): the
    commit it compared, the screens, per prototyped state the viewports and
    the anchors it compared, and every deviation, named by state, viewport,
    anchor and property. The verdict is the one the deviations give. With
    `metadata` (at a write), the full record must be a piece of the evidence
    store captured at that commit: the result is written by code."""
    record = stored_record(raw, ("commit", "verdict", "piece", "screens", "states", "deviations", "at"))
    commit = valid_commit(record["commit"], "commit du contrôle de fidélité")
    names_of(record["screens"], "écrans comparés")
    states = record["states"]
    if not isinstance(states, dict) or not states:
        raise Refusal("contrôle de fidélité sans état comparé : un résultat porte sur au moins un état prototypé")
    for state, compared in states.items():
        if not isinstance(compared, dict) or set(compared) != {"viewports", "anchors"}:
            raise Refusal(f"état {state} mal formé : {compared!r} (attendu : viewports, anchors)")
        names_of(compared["viewports"], f"état {state}, tailles d'écran comparées")
        names_of(compared["anchors"], f"état {state}, ancres comparées")
    deviations = record["deviations"]
    if not isinstance(deviations, list):
        raise Refusal(f"écarts mal formés : {deviations!r}")
    for deviation in deviations:
        if not isinstance(deviation, dict) or set(deviation) != {"state", "viewport", "anchor", "kind", "property"}:
            raise Refusal(f"écart mal formé : {deviation!r} (attendu : state, viewport, anchor, kind, property)")
        kind = one_of(deviation["kind"], DEVIATION_KINDS, "genre d'écart")
        if deviation["state"] not in states:
            raise Refusal(f"écart sur un état non comparé : {deviation['state']!r}")
        single_line(deviation["property"], "propriété de l'écart")
        located = (deviation["viewport"], deviation["anchor"])
        if kind == DEVIATION_KIND_WITHOUT_ANCHOR:
            if located != (None, None):
                raise Refusal(f"écart de token mal formé : {deviation!r} (un token se lit sur les sources, sans ancre)")
        elif any(not isinstance(name, str) or not name for name in located):
            raise Refusal(f"écart sans ancre ou sans taille d'écran : {deviation!r}")
    expected = "unfavorable" if deviations else "favorable"
    if record["verdict"] != expected:
        raise Refusal(f"verdict de fidélité incohérent : {record['verdict']!r} avec {len(deviations)} écart(s)")
    if not isinstance(record["piece"], str) or not PIECE_RE.match(record["piece"]):
        raise Refusal(f"pièce du relevé de fidélité absente ou mal formée : {record['piece']!r}")
    if metadata is not None:
        problem = evidence_at(metadata, record["piece"], commit)
        if problem:
            raise Refusal(f"relevé de fidélité sans pièce de preuve : {problem} ; il est écrit par bin/prototype-fidelity")
    return record


def planning_exceptions_record(raw: Any) -> list[dict[str, Any]]:
    """The Planning Exceptions raised on a ticket (Spec §3, §5), oldest
    first: the question, the anchors whose deviation it asks to accept and
    the option of the request that accepts it, and the answer once a later
    one was raised (the answer of the last one is read on the ticket). One
    raised at the end of the Spec (T23) names tracked elements of the Ticket
    Handoff instead (`items`), and carries the `repair` code published once
    the operator asked for one."""
    entries = stored_record(raw, ("entries",))["entries"]
    if not isinstance(entries, list) or not entries:
        raise Refusal(f"Planning Exceptions mal formées : {entries!r}")
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) - {"resolution", "items", "repair"} != {
                "kind", "summary", "anchors", "accept_option", "prior_response_at", "at"}:
            raise Refusal(f"Planning Exception mal formée : {entry!r}")
        one_of(entry["kind"], PLANNING_EXCEPTION_KINDS, "genre de Planning Exception")
        single_line(entry["summary"], "résumé de la Planning Exception")
        anchors, option = entry["anchors"], entry["accept_option"]
        if not isinstance(anchors, list) or any(not isinstance(a, str) or not ANCHOR_RE.match(a) for a in anchors):
            raise Refusal(f"ancres de la Planning Exception mal formées : {anchors!r}")
        items = entry.get("items", [])
        if not isinstance(items, list) or ("items" in entry and not items) or len(set(map(str, items))) != len(items) \
                or any(not isinstance(item, str) or not ITEM_RE.match(item) for item in items):
            raise Refusal(f"éléments suivis de la Planning Exception mal formés : {items!r}")
        if bool(anchors or items) != (option is not None) or (option is not None and not (
                isinstance(option, str) and OPTION_LETTER_RE.match(option))):
            raise Refusal(
                f"Planning Exception mal formée : ancres {anchors!r}, éléments suivis {items!r}, option d'acceptation "
                f"{option!r} (l'option qui accepte l'écart va avec les ancres ou les éléments qu'elle nomme)")
        resolution = entry.get("resolution")
        if resolution is not None and not (
                isinstance(resolution, dict) and set(resolution) == {"option", "at"}
                and all(isinstance(value, str) and value for value in resolution.values())):
            raise Refusal(f"réponse de Planning Exception mal formée : {resolution!r}")
        if "repair" in entry and not (
                isinstance(entry["repair"], str) and BEAD_ID_RE.match(entry["repair"]) and items and resolution
                and resolution["option"] != option):
            raise Refusal(
                f"repair de Planning Exception mal formé : {entry['repair']!r} (il suit une réponse de l'opérateur "
                "qui demande la réparation des éléments nommés)")
    return entries


def live_resolution(entry: dict[str, Any], metadata: dict[str, Any]) -> dict[str, str] | None:
    """The operator's answer to the last Planning Exception, as the
    escalation door wrote it on the ticket: an answer given since it was
    raised, with no request left open."""
    option, at = metadata.get(KEY_RESPONSE_OPTION), metadata.get(KEY_RESPONSE_AT)
    if metadata.get(KEY_NEEDS_BENJAMIN) != "none" or not isinstance(at, str) or not isinstance(option, str):
        return None
    if at == entry["prior_response_at"] or at < entry["at"]:
        return None
    return {"option": option, "at": at}


def planning_exceptions_rendered(entries: list[dict[str, Any]], metadata: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for index, entry in enumerate(entries):
        resolution = entry.get("resolution")
        if resolution is None and index == len(entries) - 1:
            resolution = live_resolution(entry, metadata)
        rendered = {key: value for key, value in entry.items() if key not in ("resolution", "prior_response_at")}
        rendered["state"] = "resolved" if resolution else "open"
        rendered["response"] = resolution
        rendered["accepted"] = (bool(resolution) and bool(entry["anchors"] or entry.get("items"))
                                and resolution["option"] == entry["accept_option"])
        out.append(rendered)
    return out


def tracked_items(ticket: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """The tracked elements of a rendered ticket (Spec §9, « éléments
    suivis »): each deviation and each « non fait » of its Ticket Handoff,
    with the state code reads for it. « accepté par Benjamin »: the last
    Planning Exception that names it since that Handoff was answered by the
    option that accepts it. « réparé »: the operator answered otherwise, and
    the repair code published for it is a `repair` of the convoy closed by
    the ticket-end gate. Anything else is « ouvert »: no command sets an
    element aside."""
    handoff, raised = ticket.get("handoff"), ticket.get("planning_exceptions")
    sections = handoff.get("sections") if isinstance(handoff, dict) else None
    if not isinstance(sections, dict):
        return []
    raised = raised if isinstance(raised, list) else []
    out = []
    for section in ITEM_SECTIONS:
        content = sections.get(section)
        for number, item in enumerate(content if isinstance(content, list) else [], start=1):
            item_id = f"{section}.{number}"
            rendered: dict[str, Any] = {
                "id": item_id, "section": section, "number": number,
                "text": item.get("what") if isinstance(item, dict) else item,
                "state": ITEM_OPEN, "request": None, "repair": None,
            }
            # A Handoff rendered again (a resumed ticket) starts its
            # elements over: only what was asked since counts.
            named = [entry for entry in raised if item_id in entry.get("items", []) and entry["at"] >= handoff["at"]]
            if named:
                entry = named[-1]
                rendered["request"] = {"state": entry["state"], "at": entry["at"], "response": entry["response"],
                                       "accepted": entry["accepted"]}
                if entry["accepted"]:
                    rendered["state"] = ITEM_ACCEPTED
                elif entry["state"] == "resolved":
                    rendered["repair"] = entry.get("repair")
                    repair = by_id.get(str(entry.get("repair")))
                    if (repair is not None and repair.get("kind") == "repair" and repair.get("status") == "closed"
                            and "at" in (repair.get("gates") or {}).get(GATE_TICKET_END, {})):
                        rendered["state"] = ITEM_REPAIRED
            out.append(rendered)
    return out


def fidelity_rendered(record: dict[str, Any], accepted_anchors: list[str]) -> dict[str, Any]:
    """The result with its computed state: green without deviation; else red,
    unless a resolved Planning Exception names the anchor of each one."""
    deviations = [
        {**deviation, "status": FIDELITY_ACCEPTED if deviation["anchor"] in accepted_anchors else DEVIATION_OPEN}
        for deviation in record["deviations"]
    ]
    if not deviations:
        state = FIDELITY_GREEN
    elif all(deviation["status"] == FIDELITY_ACCEPTED for deviation in deviations):
        state = FIDELITY_ACCEPTED
    else:
        state = FIDELITY_RED
    return {**record, "deviations": deviations, "state": state}


def correction_record(raw: Any) -> dict[str, Any]:
    """The correction round of a ticket (T17): the commit both verdicts were
    given at, what each of them refused there, and the author session it was
    sent to."""
    record = stored_record(raw, ("commit", "blocking_findings", "not_observed", "launches", "at"))
    valid_commit(record["commit"], "commit du tour de correction")
    findings, not_observed, launches = record["blocking_findings"], record["not_observed"], record["launches"]
    if not isinstance(findings, list) or any(not isinstance(name, str) or not FINDING_ID_RE.match(name) for name in findings):
        raise Refusal(f"Blocking Findings du tour de correction mal formés : {findings!r}")
    if not isinstance(not_observed, list) or any(not isinstance(name, str) or not name.strip() for name in not_observed):
        raise Refusal(f"états non observés du tour de correction mal formés : {not_observed!r}")
    if not findings and not not_observed:
        raise Refusal("tour de correction sans rien à corriger")
    if not isinstance(launches, list) or len(launches) > CORRECTION_MAX_LAUNCHES:
        raise Refusal(f"lancements du tour de correction mal formés : {launches!r}")
    for launch in launches:
        if not isinstance(launch, dict) or set(launch) != {"bead", "at"} or not isinstance(launch["bead"], str) \
                or not BEAD_ID_RE.match(launch["bead"]):
            raise Refusal(f"lancement du tour de correction mal formé : {launch!r}")
    return record


def overrides_record(raw: Any) -> list[dict[str, Any]]:
    """The overrides of the operator on the Blocking Findings of a stopped
    ticket (T17, Spec §8), oldest first: one per finding, with their words."""
    record = stored_record(raw, ("entries",))
    entries = record["entries"]
    if not isinstance(entries, list) or not entries:
        raise Refusal(f"dérogations mal formées : {entries!r}")
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"finding", "approver", "words", "commit", "at"}:
            raise Refusal(f"dérogation mal formée : {entry!r}")
        if not isinstance(entry["finding"], str) or not FINDING_ID_RE.match(entry["finding"]) or entry["finding"] in seen:
            raise Refusal(f"dérogation sur un constat mal formé ou donné deux fois : {entry['finding']!r}")
        seen.add(entry["finding"])
        single_line(entry["approver"], "approbateur de la dérogation")
        if not isinstance(entry["words"], str) or not entry["words"].strip():
            raise Refusal(f"dérogation sans les mots de l'approbateur : {entry['words']!r}")
        valid_commit(entry["commit"], "commit de la revue dérogée")
    return entries


def overrides_rendered(raw: Any) -> list[dict[str, Any]]:
    return [{**entry, "state": OVERRIDE_RECORDED} for entry in overrides_record(raw)]


def park_record(raw: Any) -> dict[str, Any]:
    """Why a ticket is parked (Spec §5): the cause, and the ticket whose
    Ticket Exit parked it (itself, or the one it descends from)."""
    record = stored_record(raw, ("cause", "origin", "detail", "at"))
    one_of(record["cause"], PARK_CAUSES, "cause de parcage")
    if not isinstance(record["origin"], str) or not BEAD_ID_RE.match(record["origin"]):
        raise Refusal(f"ticket d'origine du parcage absent ou mal formé : {record['origin']!r}")
    single_line(record["detail"], "précision du parcage")
    return record


def operator_answer(metadata: dict[str, Any], since: str) -> dict[str, str] | None:
    """The answer the operator gave to the request a bead carries
    (bin/escalation-door repondre), when it was given after `since` and the
    request is no longer open. None otherwise."""
    option, at = metadata.get(KEY_RESPONSE_OPTION), metadata.get(KEY_RESPONSE_AT)
    if metadata.get(KEY_NEEDS_BENJAMIN) not in (None, "none"):
        return None
    if not isinstance(option, str) or not isinstance(at, str) or at < since:
        return None
    return {"option": option, "at": at}


def park_rendered(record: dict[str, Any], ticket_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
    """The parking with the answer given to the request of the ticket that
    was asked: the one whose exit parked it, never those behind it."""
    answer = operator_answer(metadata, record["at"]) if record["origin"] == ticket_id else None
    return {**record, "answer": answer}


def launches_of(launches: Any, what: str) -> list[dict[str, Any]]:
    if not isinstance(launches, list) or any(
            not isinstance(launch, dict) or set(launch) != {"bead", "at"} or not isinstance(launch["bead"], str)
            or not BEAD_ID_RE.match(launch["bead"]) for launch in launches):
        raise Refusal(f"lancements {what} mal formés : {launches!r}")
    return launches


def resume_record(raw: Any) -> dict[str, Any]:
    """The resumes code opened on a ticket (T20), oldest first: why, the
    fact that asked for it (`ref`), the session and the Ticket Exit it
    replaces, and the fresh author session it was sent to."""
    record = stored_record(raw, ("entries",))
    entries = record["entries"]
    if not isinstance(entries, list) or not entries:
        raise Refusal(f"reprises mal formées : {entries!r}")
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"cause", "ref", "session", "exit", "launches", "at"}:
            raise Refusal(f"reprise mal formée : {entry!r}")
        one_of(entry["cause"], RESUME_CAUSES, "cause de reprise")
        single_line(entry["ref"], "repère de la reprise")
        if entry["session"] is not None:
            single_line(entry["session"], "session")
        if entry["exit"] is not None and (not isinstance(entry["exit"], dict) or set(entry["exit"]) != {"exit", "at"}):
            raise Refusal(f"sortie remplacée par la reprise mal formée : {entry['exit']!r}")
        if len(launches_of(entry["launches"], "de la reprise")) > RESUME_MAX_LAUNCHES:
            raise Refusal(f"plus d'une session pour une reprise : {entry['launches']!r}")
    return record


def park_lifts_record(raw: Any) -> list[dict[str, Any]]:
    """The parkings lifted on a ticket (T20), oldest first: what parked it,
    the request that was answered, the option taken, and the count of its
    resumes at that moment -- the bound is counted from the last lift of an
    exhausted ticket."""
    entries = stored_record(raw, ("entries",))["entries"]
    if not isinstance(entries, list) or not entries:
        raise Refusal(f"parcages levés mal formés : {entries!r}")
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"cause", "detail", "parked_at", "request", "option", "resumes", "at"}:
            raise Refusal(f"parcage levé mal formé : {entry!r}")
        one_of(entry["cause"], PARK_CAUSES, "cause de parcage")
        if not isinstance(entry["request"], str) or not BEAD_ID_RE.match(entry["request"]):
            raise Refusal(f"bead de la demande absent ou mal formé : {entry['request']!r}")
        if entry["option"] is not None:
            option_letter(entry["option"])
        counter_value(entry["resumes"], "resumes")
    return entries


def option_letter(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z]", value):
        raise Refusal(f"option de la demande absente ou mal formée : {value!r} (attendu : une lettre)")
    return value


def resumes_left(metadata: dict[str, Any]) -> int:
    """How many resumes the ticket may still take before it is parked."""
    resumes = counter_value(metadata.get(COUNTER_PREFIX + "resumes"), "resumes")
    lifts = park_lifts_record(metadata[KEY_PARK_LIFTS]) if KEY_PARK_LIFTS in metadata else []
    since = max((lift["resumes"] for lift in lifts if lift["cause"] == PARK_EXHAUSTED), default=0)
    return max(0, resumes_max() - (resumes - since))


def grouped_request_record(raw: Any) -> dict[str, Any]:
    """The one request of a convoy in which nothing but parked tickets is
    left (T20): the bead that carries it and, once it reached the escalation
    door, the signature of the parkings it names, the option that lifts and
    the tickets that option lifts."""
    record = stored_record(raw, ("bead", "at"), ("signature", "lift_option", "lifts"))
    if not isinstance(record["bead"], str) or not BEAD_ID_RE.match(record["bead"]):
        raise Refusal(f"bead de la demande groupée absent ou mal formé : {record['bead']!r}")
    if "signature" in record:
        valid_digest(record["signature"])
    if ("lift_option" in record) != ("lifts" in record):
        raise Refusal("demande groupée : l'option qui lève et les tickets qu'elle lève vont ensemble")
    if "lifts" in record:
        option_letter(record["lift_option"])
        lifts = record["lifts"]
        if not isinstance(lifts, list) or not lifts or any(
                not isinstance(name, str) or not BEAD_ID_RE.match(name) for name in lifts):
            raise Refusal(f"tickets levés par la demande groupée mal formés : {lifts!r}")
    return record


def valid_branch(value: Any, name: str) -> str:
    if not isinstance(value, str) or not BRANCH_RE.match(value):
        raise Refusal(f"{name} absente ou mal formée : {value!r}")
    return value


def integration_record(raw: Any) -> dict[str, Any]:
    """The integration branch of the convoy's Spec (Spec §4): its name, the
    protected branch it takes up, and the commit of that branch it left from."""
    record = stored_record(raw, ("branch", "protected", "base", "at"))
    valid_branch(record["branch"], "branche d'intégration")
    valid_branch(record["protected"], "branche protégée")
    valid_commit(record["base"], "commit de départ de la branche d'intégration")
    return record


def blocking_red_record(raw: Any) -> dict[str, Any]:
    """The red control the author of a ticket named when it left
    « bloqué technique » (T40): one line, as its `repair` cites it."""
    record = stored_record(raw, ("control", "at"))
    single_line(record["control"], "contrôle rouge")
    return record


def integration_red_record(raw: Any) -> dict[str, Any]:
    """The red of the convoy's integration branch (Spec §8): the control
    that is red, quoted, the commit it was red on, the tips of the
    integration and of the protected branches then, and the one repair
    ticket that restores it once code has published it."""
    record = stored_record(raw, ("control", "commit", "integration", "protected", "at"), ("detail", "repair", "check"))
    if "check" in record:
        one_of(record["check"], RED_CHECKS, "contrôle rouge (check)")
    single_line(record["control"], "contrôle rouge")
    valid_commit(record["commit"], "commit du contrôle rouge")
    valid_commit(record["integration"], "pointe de la branche d'intégration")
    valid_commit(record["protected"], "pointe de la branche protégée")
    if "detail" in record:
        single_line(record["detail"], "détail du contrôle rouge")
    if "repair" in record and (not isinstance(record["repair"], str) or not BEAD_ID_RE.match(record["repair"])):
        raise Refusal(f"ticket repair du rouge absent ou mal formé : {record['repair']!r}")
    return record


def spec_end_conditions(value: Any) -> list[dict[str, Any]]:
    """The three verdicts of the end-of-Spec gate, in the order of its list,
    all passing, each with the one line that says what was read."""
    if not isinstance(value, list) or len(value) != len(SPEC_END_CONDITIONS):
        raise Refusal(
            f"relevé de la porte de fin de Spec mal formé : {len(SPEC_END_CONDITIONS)} verdicts attendus, dans l'ordre "
            f"de la liste {SPEC_END_VERSION} ({', '.join(SPEC_END_CONDITIONS)})")
    conditions = []
    for number, (name, entry) in enumerate(zip(SPEC_END_CONDITIONS, value), start=1):
        if not isinstance(entry, dict) or set(entry) != {"number", "name", "verdict", "detail"} \
                or (entry["number"], entry["name"]) != (number, name):
            raise Refusal(f"verdict {number} du relevé mal formé : {entry!r} (attendu : number, name {name!r}, verdict, detail)")
        if entry["verdict"] != SPEC_END_PASS:
            raise Refusal(
                f"condition {number} ({name}) non réunie : verdict {entry['verdict']!r} ; la porte de fin de Spec "
                "n'enregistre que trois verdicts verts")
        conditions.append({**entry, "detail": single_line(entry["detail"], f"détail de la condition {number}")})
    return conditions


def spec_end_record(raw: Any) -> dict[str, Any]:
    """The record of the end-of-Spec gate (T23, Spec §9): the one commit of
    the integration branch its three verdicts are tied to, the tip of the
    protected branch that commit holds, the version of the list, the
    verdicts and what the controls read."""
    record = stored_record(raw, ("commit", "protected", "version", "conditions", "at"), ("records",))
    valid_commit(record["commit"], "commit du relevé de la porte de fin de Spec")
    valid_commit(record["protected"], "pointe de la branche protégée")
    if record["version"] not in SPEC_END_VERSIONS:
        raise Refusal(f"version de la liste de conditions inconnue : {record['version']!r} (attendu : {SPEC_END_VERSION})")
    record["conditions"] = spec_end_conditions(record["conditions"])
    records = record.get("records", {})
    if not isinstance(records, dict) or set(records) - set(SPEC_END_RECORDS) or any(
            not isinstance(value, dict) for value in records.values()):
        raise Refusal(f"relevés de la porte de fin de Spec mal formés (attendu : {', '.join(SPEC_END_RECORDS)})")
    return record


def evidence_pack_record(raw: Any) -> dict[str, Any]:
    """The Evidence Pack code generated (T27, Spec §10): the commit of the
    integration branch it is tied to, the fingerprint of its page, where it
    was written, whether every condition of the end of the Spec it reports
    was met, and how many pieces it could not take from the evidence store."""
    record = stored_record(raw, ("commit", "digest", "path", "conforming", "inadmissible", "version", "at"))
    valid_commit(record["commit"], "commit de l'Evidence Pack")
    valid_digest(record["digest"])
    if not isinstance(record["path"], str) or not record["path"].startswith("/") or single_line(
            record["path"], "dossier de l'Evidence Pack") != record["path"]:
        raise Refusal(f"dossier de l'Evidence Pack absent ou mal formé (un chemin absolu, sur une ligne) : {record['path']!r}")
    if not isinstance(record["conforming"], bool):
        raise Refusal(f"conformité de l'Evidence Pack mal formée : {record['conforming']!r}")
    count = record["inadmissible"]
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise Refusal(f"nombre de pièces irrecevables de l'Evidence Pack mal formé : {count!r}")
    if record["version"] != EVIDENCE_PACK_VERSION:
        raise Refusal(f"version de l'Evidence Pack inconnue : {record['version']!r} (attendu : {EVIDENCE_PACK_VERSION})")
    return record


def end_citation_of(finding: dict[str, Any]) -> tuple[dict[str, str] | None, str | None]:
    """The citation a finding of the end review gives, and why it does not
    hold when it does not: the rule of the review of a ticket (Spec §6), a
    line of a ticket naming the ticket of the convoy it is a line of."""
    citation = finding.get("citation")
    ticket = citation.get("ticket") if isinstance(citation, dict) else None
    if isinstance(citation, dict) and (citation.get("source") == "ticket") != (
            isinstance(ticket, str) and bool(BEAD_ID_RE.match(ticket))):
        return None, "citation mal formée : ticket nomme le ticket du convoi dont la ligne est citée, et seulement lui"
    plain = {**finding, "citation": {name: value for name, value in citation.items() if name != "ticket"}} \
        if isinstance(citation, dict) else finding
    kept, reason = citation_of(plain)
    if kept is not None and kept["source"] == "ticket":
        kept["ticket"] = ticket
    return kept, reason


def end_repair_draft(value: Any, where: str) -> tuple[dict[str, Any] | None, str | None]:
    """The `repair` the end reviewer drafts for one Blocking Finding (Spec
    §6: written by the reviewer, never published by it), and what is wrong
    with it when it is not one."""
    try:
        draft = repair_draft(value, f"{where} : repair rédigé")
    except Refusal as exc:
        return None, str(exc)
    if draft["restores"]["kind"] not in DRAFT_RESTORES:
        return None, (f"{where} : repair rédigé, restores mal formé (attendu : kind parmi {', '.join(DRAFT_RESTORES)}, "
                      "et ref, une ligne qui cite ce qu'il rétablit)")
    return draft, None


def end_extent(value: Any) -> dict[str, Any]:
    """The extent of the diff an end review reads: the whole diff of the
    integration branch against the protected branch, counted by code."""
    if not isinstance(value, dict) or set(value) != {*END_EXTENT_COUNTS, "digest"} or any(
            isinstance(value[name], bool) or not isinstance(value[name], int) or value[name] < 0
            for name in END_EXTENT_COUNTS):
        raise Refusal(f"étendue de la revue de fin mal formée : {value!r} (attendu : {', '.join(END_EXTENT_COUNTS)}, digest)")
    valid_digest(value["digest"])
    return value


def end_models(value: Any) -> dict[str, Any]:
    """The models an end review is given under: the model of each author of
    the convoy, the reviewer's, and whether the reviewer runs on one of
    them -- null when one of them is not recorded."""
    if not isinstance(value, dict) or set(value) != {"authors", "reviewer", "same_model"} \
            or not isinstance(value["authors"], list) or not isinstance(value["same_model"], (bool, type(None))):
        raise Refusal(f"modèles de la revue de fin mal formés : {value!r}")
    for model in value["authors"]:
        single_line(model, "modèle d'un auteur")
    if value["reviewer"] is not None:
        single_line(value["reviewer"], "modèle du relecteur")
    elif value["same_model"] is not None:
        raise Refusal(f"mention des modèles incohérente : {value!r}")
    return value


def end_coverage(value: Any) -> dict[str, Any]:
    """What an end review says it read: the axes of the skill it ran and
    the files of the diff it covered, those left out named."""
    if not isinstance(value, dict) or not {"axes", "files", "missing"} <= set(value) \
            or set(value) - {"axes", "files", "missing", "missing_count"} \
            or not isinstance(value["axes"], list) or set(value["axes"]) - set(REVIEW_AXES) \
            or isinstance(value["files"], bool) or not isinstance(value["files"], int) or value["files"] < 0 \
            or not isinstance(value["missing"], list) or any(not isinstance(path, str) for path in value["missing"]):
        raise Refusal(f"coverage mal formé : {value!r} (attendu : axes parmi {', '.join(REVIEW_AXES)}, files, missing)")
    return value


def end_review_complete(coverage: dict[str, Any], extent: dict[str, Any]) -> bool:
    return set(coverage["axes"]) == set(REVIEW_AXES) and not coverage["missing"] \
        and not coverage.get("missing_count") and coverage["files"] == extent["files"]


def end_finding(value: Any) -> dict[str, Any]:
    """One finding of the end review as stored. A Blocking Finding carries
    its citation and the repair its reviewer drafted, then the ticket code
    published from it, or why the patch door refused it."""
    known = {"id", "axis", "blocking", "summary", "citation", "demoted", "repair_draft", "repair", "repair_refused"}
    if not isinstance(value, dict) or not {"id", "axis", "blocking", "summary"} <= set(value) or set(value) - known:
        raise Refusal(f"constat de revue de fin mal formé : {value!r}")
    if not isinstance(value["id"], str) or not FINDING_ID_RE.match(value["id"]):
        raise Refusal(f"identifiant de constat mal formé : {value['id']!r}")
    one_of(value["axis"], REVIEW_AXES, "axe de revue")
    single_line(value["summary"], "résumé du constat")
    if not isinstance(value["blocking"], bool):
        raise Refusal(f"constat {value['id']} : blocking mal formé : {value['blocking']!r}")
    if "citation" in value and end_citation_of({"citation": value["citation"]})[1] is not None:
        raise Refusal(f"constat {value['id']} : citation mal formée")
    if value["blocking"]:
        if "demoted" in value or "citation" not in value or end_repair_draft(value.get("repair_draft"), value["id"])[1]:
            raise Refusal(f"constat {value['id']} : bloquant sans citation ou sans repair rédigé")
        if "repair" in value and "repair_refused" in value:
            raise Refusal(f"constat {value['id']} : repair publié et repair refusé à la fois")
        if "repair" in value and (not isinstance(value["repair"], str) or not BEAD_ID_RE.match(value["repair"])):
            raise Refusal(f"constat {value['id']} : ticket repair mal formé : {value['repair']!r}")
        if "repair_refused" in value:
            single_line(value["repair_refused"], "refus du repair rédigé")
    elif {"repair_draft", "repair", "repair_refused"} & set(value):
        raise Refusal(f"constat {value['id']} : repair sur un constat qui ne bloque pas")
    return value


def end_launches(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) > END_REVIEW_MAX_LAUNCHES:
        raise Refusal(f"lancements de la revue de fin mal formés : {value!r}")
    for launch in value:
        if not isinstance(launch, dict) or not {"bead", "at"} <= set(launch) or set(launch) - {"bead", "at", "result"} \
                or not isinstance(launch["bead"], str) or not BEAD_ID_RE.match(launch["bead"]) \
                or launch.get("result", END_REVIEW_INCOMPLETE) != END_REVIEW_INCOMPLETE:
            raise Refusal(f"lancement de la revue de fin mal formé : {launch!r}")
    return value


def end_review_record(raw: Any) -> dict[str, Any]:
    """The end code review of the Spec (T25): the rounds reviewer sessions
    recorded, each bound to the commit of the end-of-Spec gate it read and
    to the tip of the protected branch that commit holds, the request that
    is open, and the stop of a review that gave no result."""
    record = stored_record(raw, ("rounds",), ("request", "stop"))
    if not isinstance(record["rounds"], list):
        raise Refusal(f"passes de la revue de fin mal formées : {record['rounds']!r}")
    for value in record["rounds"]:
        common = {"commit", "base", "outcome", "findings", "coverage", "extent", "models", "recorded_by",
                  "launched_at", "duration_seconds", "at"}
        if not isinstance(value, dict) or set(value) != common:
            raise Refusal(f"passe de la revue de fin mal formée : {value!r}")
        valid_commit(value["commit"], "commit de la revue de fin")
        valid_commit(value["base"], "pointe de la branche protégée de la revue de fin")
        outcome = one_of(value["outcome"], END_REVIEW_OUTCOMES, "issue de la revue de fin")
        end_models(value["models"])
        single_line(value["recorded_by"], "session du relecteur")
        if not isinstance(value["findings"], list):
            raise Refusal(f"constats de la revue de fin mal formés : {value['findings']!r}")
        for finding in value["findings"]:
            end_finding(finding)
        complete = end_review_complete(end_coverage(value["coverage"]), end_extent(value["extent"]))
        blocked = any(finding["blocking"] for finding in value["findings"])
        expected = END_REVIEW_INCOMPLETE if not complete else "unfavorable" if blocked else "favorable"
        if outcome != expected:
            raise Refusal("issue de la revue de fin qui n'est pas celle de ses constats et de son étendue")
        duration = value["duration_seconds"]
        if isinstance(duration, bool) or not isinstance(duration, int) or duration < 0:
            raise Refusal(f"durée de la revue de fin mal formée : {duration!r}")
    if "request" in record:
        request = record["request"]
        if not isinstance(request, dict) or set(request) != {"commit", "base", "extent", "launches", "models", "at"}:
            raise Refusal(f"demande de revue de fin mal formée : {request!r}")
        valid_commit(request["commit"], "commit de la revue de fin")
        valid_commit(request["base"], "pointe de la branche protégée de la revue de fin")
        end_extent(request["extent"])
        end_models(request["models"])
        end_launches(request["launches"])
    if "stop" in record:
        stop = record["stop"]
        if not isinstance(stop, dict) or not {"reason", "detail", "commit", "at"} <= set(stop) \
                or set(stop) - {"reason", "detail", "commit", "at", "bead", "raised"} or ("bead" in stop) != ("raised" in stop):
            raise Refusal(f"arrêt de la revue de fin mal formé : {stop!r}")
        one_of(stop["reason"], END_REVIEW_STOPS, "raison de l'arrêt de la revue de fin")
        single_line(stop["detail"], "détail de l'arrêt de la revue de fin")
        valid_commit(stop["commit"], "commit de l'arrêt de la revue de fin")
    return record


def end_review_state(record: dict[str, Any]) -> dict[str, Any]:
    """What the end review says now: the outcome of its last round, the
    commit that round read, and its Blocking Findings. A round says nothing
    of another commit than its own: the gate reads the commit."""
    last = record["rounds"][-1] if record["rounds"] else None
    if last is None:
        return {"commit": None, "outcome": None, "unsettled": []}
    unsettled = [] if last["outcome"] == END_REVIEW_INCOMPLETE else blocking_ids(last)
    return {"commit": last["commit"], "outcome": last["outcome"], "unsettled": unsettled}


# What a round of the end keeps of the Outcome Evaluations of its lot, for
# the early stop (Spec §8): the stories not observed at its tip, those not
# observed at the tip of the round before, and every story refused at an
# earlier counted tip.
END_ROUND_STORIES = ("not_observed", "previous_not_observed", "refused_before")


def end_round_record(raw: Any) -> dict[str, Any]:
    """The tip of the integration branch the last round of the end of the
    Spec was counted for, and the source that counted it: several sources
    that refuse the same tip are one round (Spec §8: one counter, every
    source)."""
    record = stored_record(raw, ("commit", "source", "at"), END_ROUND_STORIES)
    valid_commit(record["commit"], "commit du tour de fin")
    single_line(record["source"], "source du tour de fin")
    for name in END_ROUND_STORIES:
        if name in record:
            story_numbers(record[name], f"user stories du tour de fin ({name})")
    return record


def story_numbers(value: Any, what: str) -> list[int]:
    if not isinstance(value, list) or any(isinstance(n, bool) or not isinstance(n, int) or n < 1 for n in value) \
            or sorted(set(value)) != value:
        raise Refusal(f"{what} mal formées : {value!r} (attendu : des numéros de user story, croissants, chacun une fois)")
    return value


def end_stop_record(raw: Any) -> dict[str, Any]:
    """The stop of the repair rounds of the end of a Spec (T26, Spec §8):
    why, the tip that was refused when it was written, the source that
    refused it, the rounds counted then, and -- once the « non conforme »
    request reached the operator -- the bead it sits on and the Evidence
    Pack it carries."""
    record = stored_record(raw, ("reason", "detail", "commit", "source", "rounds", "at"), ("request",))
    one_of(record["reason"], END_STOPS, "raison d'arrêt des tours de fin")
    single_line(record["detail"], "précision de l'arrêt des tours de fin")
    valid_commit(record["commit"], "commit de l'arrêt des tours de fin")
    one_of(record["source"], END_ROUND_SOURCES, "source de l'arrêt des tours de fin")
    counter_value(record["rounds"], "end_rounds")
    if "request" in record:
        request = record["request"]
        if not isinstance(request, dict) or set(request) != {"bead", "commit", "digest", "page", "at"} \
                or not isinstance(request["bead"], str) or not BEAD_ID_RE.match(request["bead"]) \
                or not isinstance(request["page"], str) or not request["page"].startswith("/"):
            raise Refusal(f"demande « non conforme » mal formée : {request!r}")
        valid_commit(request["commit"], "commit de l'Evidence Pack de la demande")
        valid_digest(request["digest"])
    return record


def delivered_record(raw: Any) -> dict[str, Any]:
    """The Delivered Outcome of a convoy (T26, Spec §9): the one commit of
    the integration branch every condition of the end of the Spec was met
    on, the tip of the protected branch that commit holds, the fingerprint
    of the Evidence Pack generated there and the version of the list."""
    record = stored_record(raw, ("commit", "protected", "pack", "version", "at"))
    valid_commit(record["commit"], "commit du Delivered Outcome")
    valid_commit(record["protected"], "pointe de la branche protégée")
    valid_digest(record["pack"])
    if record["version"] != SPEC_END_VERSION:
        raise Refusal(f"version de la liste de conditions inconnue : {record['version']!r} (attendu : {SPEC_END_VERSION})")
    return record


def acceptance_record(raw: Any) -> dict[str, Any]:
    """What the acceptance of a convoy holds before Benjamin's answer (T28,
    Spec §11), tied to the one commit of the Evidence Pack he judges: the
    Acceptance Request that reached him -- the bead the escalation door
    wrote it on and the page of the dossier -- and the outage of an
    Acceptance Session whose product did not start, with the `repair` code
    published for it."""
    record = stored_record(raw, ("commit", "at"), ("pack", "request", "panne"))
    valid_commit(record["commit"], "commit du dossier")
    if "pack" in record:
        valid_digest(record["pack"])
    if "request" in record:
        request = record["request"]
        if not isinstance(request, dict) or sorted(request) != ["at", "bead", "page"] \
                or not isinstance(request["bead"], str) or not BEAD_ID_RE.match(request["bead"]):
            raise Refusal(f"Acceptance Request mal formée : {request!r}")
        single_line(request["page"], "page de l'Evidence Pack")
    if "panne" in record:
        panne = record["panne"]
        if not isinstance(panne, dict) or not {"at", "detail"} <= set(panne) <= {"at", "detail", "ticket"}:
            raise Refusal(f"panne de l'Acceptance Session mal formée : {panne!r}")
        single_line(panne["detail"], "panne de l'Acceptance Session")
        if "ticket" in panne and (not isinstance(panne["ticket"], str) or not BEAD_ID_RE.match(panne["ticket"])):
            raise Refusal(f"repair de la panne mal formé : {panne['ticket']!r}")
    return record
def restores_record(value: Any, what: str) -> dict[str, str]:
    """What a `repair` restores, cited (Spec §2): one of the kinds the patch
    door knows, and the line that cites it."""
    if not isinstance(value, dict) or set(value) != {"kind", "ref"}:
        raise Refusal(
            f"{what} sans citation de ce qu'il rétablit (attendu : restores avec kind parmi {', '.join(RESTORES_KINDS)}, "
            "et ref qui le cite)")
    one_of(value["kind"], RESTORES_KINDS, f"genre de ce que rétablit {what}")
    return {"kind": value["kind"], "ref": single_line(value["ref"], f"citation de ce que rétablit {what}")}


def repair_draft(value: Any, what: str) -> dict[str, Any]:
    """A `repair` an agent of the end of the Spec drafted, not published
    (Spec §2, §7): what the patch door is given once code publishes it."""
    if not isinstance(value, dict) or set(value) != set(REPAIR_DRAFT_FIELDS):
        raise Refusal(f"{what} mal formé (attendu : {', '.join(REPAIR_DRAFT_FIELDS)})")
    draft: dict[str, Any] = {name: single_line(value[name], f"{name} de {what}")
                             for name in ("title", "what_it_delivers", "demonstration_line")}
    draft["restores"] = restores_record(value["restores"], what)
    criteria = value["acceptance_criteria"]
    if not isinstance(criteria, list) or not criteria:
        raise Refusal(f"{what} sans critère d'acceptation")
    draft["acceptance_criteria"] = []
    for criterion in criteria:
        if not isinstance(criterion, dict) or set(criterion) != set(REPAIR_CRITERION_FIELDS):
            raise Refusal(f"critère de {what} mal formé (attendu : {', '.join(REPAIR_CRITERION_FIELDS)}) : {criterion!r}")
        draft["acceptance_criteria"].append(
            {name: single_line(criterion[name], f"{name} d'un critère de {what}") for name in REPAIR_CRITERION_FIELDS})
    return draft


def cited_story(restores: dict[str, str]) -> str | None:
    """The number of the one user story a citation names, as the patch door
    reads it: exactly one number in the reference."""
    numbers = [str(int(number)) for number in re.findall(r"[0-9]+", restores["ref"])]
    return numbers[0] if restores["kind"] == "user_story" and len(numbers) == 1 else None


def findings_record(raw: Any) -> list[dict[str, Any]]:
    """The classifications the Evaluator of the end gave the findings « hors
    ticket » of a Ticket Handoff (T24, Spec §7, §9): « repaired » always
    with the citation of what it restores and the drafted `repair`,
    « dismissed » always with its reason, « proposal » kept for the operator."""
    entries = stored_record(raw, ("entries",))["entries"]
    if not isinstance(entries, list) or not entries:
        raise Refusal(f"classements de constats hors ticket mal formés : {entries!r}")
    seen = set()
    for entry in entries:
        common = {"item", "handoff_at", "classification", "commit", "recorded_by", "at"}
        if not isinstance(entry, dict) or not common <= set(entry) or set(entry) - common - {"reason", "draft", "repair"}:
            raise Refusal(f"classement de constat hors ticket mal formé : {entry!r}")
        if not isinstance(entry["item"], str) or not FINDING_ITEM_RE.match(entry["item"]) or entry["item"] in seen:
            raise Refusal(f"constat hors ticket mal nommé, ou classé deux fois : {entry['item']!r}")
        seen.add(entry["item"])
        classification = one_of(entry["classification"], FINDING_CLASSES, "classement de constat hors ticket")
        valid_commit(entry["commit"], "commit du classement")
        single_line(entry["recorded_by"], "session de l'Evaluator")
        if "reason" in entry:
            single_line(entry["reason"], "raison du classement")
        if classification == "dismissed" and "reason" not in entry:
            raise Refusal(f"constat {entry['item']} écarté sans raison")
        if (classification == "repaired") != ("draft" in entry):
            raise Refusal(f"constat {entry['item']} : un repair rédigé va avec le classement « repaired », et avec lui seul")
        if "draft" in entry:
            repair_draft(entry["draft"], f"le repair du constat {entry['item']}")
        if "repair" in entry and not (
                classification == "repaired" and isinstance(entry["repair"], str) and BEAD_ID_RE.match(entry["repair"])):
            raise Refusal(f"repair du constat {entry['item']} mal formé : {entry['repair']!r}")
    return entries


def findings_rendered(ticket: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """The findings « hors ticket » of a rendered ticket (Spec §9,
    « éléments suivis ») with the state code reads for each: « non classé »
    until the Evaluator of the end classified it since that Handoff;
    « proposition pour Benjamin » and « écarté » are final; a finding
    classified « repaired » is « à réparer » until the `repair` code
    published for it is closed by the ticket-end gate, « réparé » then."""
    handoff, classified = ticket.get("handoff"), ticket.get("finding_classifications")
    sections = handoff.get("sections") if isinstance(handoff, dict) else None
    if not isinstance(sections, dict) or "at" in (ticket.get("gates") or {}).get("withdrawn", {}):
        return []
    known = {entry["item"]: entry for entry in classified if entry["handoff_at"] == handoff["at"]} \
        if isinstance(classified, list) else {}
    content = sections.get(FINDING_SECTION)
    out = []
    for number, text in enumerate(content if isinstance(content, list) else [], start=1):
        item = f"{FINDING_SECTION}.{number}"
        rendered: dict[str, Any] = {"id": f"{ticket['id']}:{item}", "ticket": ticket["id"], "item": item, "number": number,
                                    "text": text, "state": FINDING_UNCLASSIFIED, "classification": None}
        entry = known.get(item)
        if entry:
            rendered.update({key: entry[key] for key in ("classification", "reason", "draft", "repair", "commit",
                                                         "recorded_by", "at") if key in entry})
            if entry["classification"] == "proposal":
                rendered["state"] = FINDING_PROPOSAL
            elif entry["classification"] == "dismissed":
                rendered["state"] = FINDING_DISMISSED
            else:
                repair = by_id.get(str(entry.get("repair")))
                closed = (repair is not None and repair.get("kind") == "repair" and repair.get("status") == "closed"
                          and "at" in (repair.get("gates") or {}).get(GATE_TICKET_END, {}))
                rendered["state"] = FINDING_REPAIRED if closed else FINDING_TO_REPAIR
        out.append(rendered)
    return out


def outcome_roles(value: Any) -> dict[str, Any]:
    """The suppliers the authors of the convoy's tickets and the Evaluator of
    the end ran on (Spec §7): `same_provider` is null when one is not
    recorded, true when the Evaluator ran on the supplier of an author."""
    if not isinstance(value, dict) or set(value) != {"authors", "evaluator", "same_provider", "other_declared"}:
        raise Refusal(f"relevé des rôles de l'Outcome Evaluation mal formé : {value!r}")
    entries = [value["evaluator"], *(value["authors"] if isinstance(value["authors"], list) else [None, None])]
    if not isinstance(value["authors"], list) or any(
            entry is not None and (not isinstance(entry, dict) or set(entry) != {"provider", "supplier"}
                                   or any(not isinstance(v, str) or not v.strip() for v in entry.values()))
            for entry in entries) or None in value["authors"]:
        raise Refusal(f"relevé des rôles de l'Outcome Evaluation mal formé : {value!r}")
    same, other = value["same_provider"], value["other_declared"]
    if (same is not None and not isinstance(same, bool)) or (same is None) != (
            value["evaluator"] is None or not value["authors"]):
        raise Refusal("relevé des rôles de l'Outcome Evaluation incohérent : same_provider ne dit pas ce que disent ses rôles")
    if not isinstance(other, list) or any(not isinstance(name, str) or not name.strip() for name in other):
        raise Refusal(f"relevé des rôles de l'Outcome Evaluation mal formé : other_declared {other!r}")
    return value


def outcome_stories(value: Any) -> list[dict[str, Any]]:
    """The numbered user stories of the Spec an Outcome Evaluation walks."""
    if not isinstance(value, list) or not value:
        raise Refusal(f"user stories de l'Outcome Evaluation absentes ou mal formées : {value!r}")
    for story in value:
        if not isinstance(story, dict) or set(story) != {"number", "text"} or isinstance(story["number"], bool) \
                or not isinstance(story["number"], int) or story["number"] < 1:
            raise Refusal(f"user story de l'Outcome Evaluation mal formée : {story!r}")
        single_line(story["text"], f"texte de la user story {story['number']}")
    if len({story["number"] for story in value}) != len(value):
        raise Refusal("user stories de l'Outcome Evaluation mal formées : un numéro y figure deux fois")
    return value


def outcome_notes(value: Any, name: str) -> Any:
    """A non-blocking section of an Outcome Evaluation (Spec §7): its lines,
    each with the piece that shows it when there is one, or the word for
    "nothing"; never left out."""
    if value == HANDOFF_NOTHING:
        return value
    if not isinstance(value, list) or not value:
        raise Refusal(f"rubrique {name} absente ou mal formée : {value!r} (attendu : une liste non vide, ou « {HANDOFF_NOTHING} »)")
    for note in value:
        if not isinstance(note, dict) or not {"text"} <= set(note) or set(note) - {"text", "evidence"}:
            raise Refusal(f"rubrique {name} : élément mal formé : {note!r} (attendu : text, et evidence en option)")
        single_line(note["text"], f"élément de la rubrique {name}")
        if "evidence" in note and (not isinstance(note["evidence"], str) or not PIECE_RE.match(note["evidence"])):
            raise Refusal(f"rubrique {name} : pièce de preuve mal nommée : {note['evidence']!r}")
    return value


def outcome_request(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"commit", "stories", "roles", "environment", "launches", "at"}:
        raise Refusal(f"demande d'Outcome Evaluation mal formée : {value!r}")
    valid_commit(value["commit"], "commit de l'Outcome Evaluation")
    outcome_stories(value["stories"])
    outcome_roles(value["roles"])
    evaluation_environment(value["environment"], launched=True)
    evaluation_launches(value["launches"])
    return value


def outcome_of_stories(stories: list[dict[str, Any]]) -> str:
    """Spec §7, the same form of verdict as a Ticket Evaluation: favorable
    only when every story is « observé ». A story that cannot be observed by
    itself goes back to the Planning Run, a « non observé » to a `repair`;
    when the environment alone hid something, it is an outage."""
    if any(story["state"] == "unobservable" and story["cause"] == "criterion" for story in stories):
        return "planning_exception"
    if any(story["state"] == "not_observed" for story in stories):
        return "repair"
    if any(story["state"] == "unobservable" for story in stories):
        return "environment_outage"
    return "favorable"


def outcome_round(value: Any) -> dict[str, Any]:
    fields = {"commit", "stories", "exploration", "fidelity_deviations", "repairs", "contradictions", "outcome", "verdict",
              "roles", "environment", "recorded_by", "at"}
    if not isinstance(value, dict) or set(value) != fields:
        raise Refusal(f"passe d'Outcome Evaluation mal formée : {value!r}")
    valid_commit(value["commit"], "commit de l'Outcome Evaluation")
    if not isinstance(value["stories"], list) or not value["stories"]:
        raise Refusal(f"passe d'Outcome Evaluation sans état par user story : {value['stories']!r}")
    for story in value["stories"]:
        number = story.get("number") if isinstance(story, dict) else None
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            raise Refusal(f"user story sans numéro dans une passe d'Outcome Evaluation : {story!r}")
        evaluation_item(story, f"user story {number}")
    numbers = [story["number"] for story in value["stories"]]
    if len(set(numbers)) != len(numbers):
        raise Refusal("passe d'Outcome Evaluation mal formée : deux états pour une user story")
    for name in OUTCOME_SECTIONS:
        outcome_notes(value[name], name)
    not_observed = {story["number"] for story in value["stories"] if story["state"] == "not_observed"}
    repairs = value["repairs"]
    if not isinstance(repairs, list) or {entry.get("story") if isinstance(entry, dict) else None
                                         for entry in repairs} != not_observed or len(repairs) != len(not_observed):
        raise Refusal("passe d'Outcome Evaluation mal formée : un repair rédigé par user story « non observée », et aucun autre")
    for entry in repairs:
        if set(entry) - {"story", "draft", "repair"} or "draft" not in entry:
            raise Refusal(f"repair rédigé mal formé : {entry!r}")
        draft = repair_draft(entry["draft"], f"le repair de la user story {entry['story']}")
        if cited_story(draft["restores"]) != str(entry["story"]):
            raise Refusal(f"le repair de la user story {entry['story']} ne la cite pas (restores : {draft['restores']!r})")
        if "repair" in entry and (not isinstance(entry["repair"], str) or not BEAD_ID_RE.match(entry["repair"])):
            raise Refusal(f"repair publié de la user story {entry['story']} mal formé : {entry['repair']!r}")
    contradictions = value["contradictions"]
    if not isinstance(contradictions, list):
        raise Refusal(f"contradictions mal formées : {contradictions!r}")
    for entry in contradictions:
        if not isinstance(entry, dict) or set(entry) != {"story", "tickets"} or entry["story"] not in not_observed \
                or not isinstance(entry["tickets"], list) or not entry["tickets"] or any(
                    not isinstance(ticket, dict) or set(ticket) != {"id", "commit", "at"} for ticket in entry["tickets"]):
            raise Refusal(f"contradiction mal formée : {entry!r}")
    outcome = one_of(value["outcome"], OUTCOME_OUTCOMES, "issue de l'Outcome Evaluation")
    if outcome != outcome_of_stories(value["stories"]) or value["verdict"] != verdict_of_outcome(outcome):
        raise Refusal("issue ou verdict d'Outcome Evaluation qui n'est pas celui de ses états")
    outcome_roles(value["roles"])
    evaluation_environment(value["environment"], launched=False)
    single_line(value["recorded_by"], "session de l'Evaluator")
    return value


def outcome_evaluation_record(raw: Any) -> dict[str, Any]:
    """The Outcome Evaluation of a convoy (T24, Spec §7): the rounds
    recorded, each bound to the commit the end-of-Spec gate rendered its
    mechanical verdicts on, the request that is open, the launch records of
    the products still to stop (`live`), and what stopped it at a commit
    (`stop`: no result, an environment that failed twice, a story that
    cannot be observed)."""
    record = stored_record(raw, ("rounds",), ("request", "live", "stop"))
    if not isinstance(record["rounds"], list):
        raise Refusal(f"passes d'Outcome Evaluation mal formées : {record['rounds']!r}")
    for value in record["rounds"]:
        outcome_round(value)
    if "request" in record:
        outcome_request(record["request"])
    if "live" in record:
        live = record["live"]
        if not isinstance(live, list) or not live or any(not isinstance(path, str) or not path.strip() for path in live):
            raise Refusal(f"produits lancés à arrêter mal formés : {live!r}")
    if "stop" in record:
        stop = record["stop"]
        if not isinstance(stop, dict) or not {"reason", "detail", "commit", "at"} <= set(stop) \
                or set(stop) - {"reason", "detail", "commit", "at", "raised"}:
            raise Refusal(f"arrêt de l'Outcome Evaluation mal formé : {stop!r}")
        one_of(stop["reason"], OUTCOME_STOPS, "raison d'arrêt de l'Outcome Evaluation")
        single_line(stop["detail"], "précision de l'arrêt")
        valid_commit(stop["commit"], "commit de l'arrêt")
    return record


def outcome_state(record: dict[str, Any]) -> dict[str, Any]:
    """What the Outcome Evaluation says of the convoy now: the issue of its
    last round, its commit, each story that is not « observé », the repairs
    drafted for them and the contradictions with the tickets that cover them."""
    last = record["rounds"][-1] if record["rounds"] else None
    state: dict[str, Any] = {"verdict": None, "outcome": None, "commit": None, "not_observed": [], "unobservable": [],
                             "repairs": [], "contradictions": []}
    if last is None:
        return state
    state.update(verdict=last["verdict"], outcome=last["outcome"], commit=last["commit"],
                 repairs=[{"story": entry["story"], "repair": entry.get("repair")} for entry in last["repairs"]],
                 contradictions=last["contradictions"])
    for story in last["stories"]:
        if story["state"] == "not_observed":
            state["not_observed"].append(story["number"])
        elif story["state"] == "unobservable":
            state["unobservable"].append({"what": story["number"], "cause": story["cause"]})
    return state


def outcome_evaluation_rendered(raw: Any) -> dict[str, Any]:
    record = outcome_evaluation_record(raw)
    return {**record, "state": outcome_state(record)}


def merge_record(raw: Any) -> dict[str, Any]:
    """What the merge command did of a ticket: the tip of the ticket it took,
    the tip of the integration branch it merged it on, and the commit of the
    merged result when there is one."""
    record = stored_record(raw, ("outcome", "ticket_commit", "integration", "at"), ("commit",))
    outcome = one_of(record["outcome"], MERGE_OUTCOMES, "issue de fusion")
    valid_commit(record["ticket_commit"], "pointe du ticket")
    valid_commit(record["integration"], "pointe de la branche d'intégration")
    if (outcome in MERGE_OUTCOMES_WITH_COMMIT) != ("commit" in record):
        raise Refusal(
            f"issue {outcome} : commit du résultat fusionné "
            f"{'absent' if outcome in MERGE_OUTCOMES_WITH_COMMIT else 'inattendu'}")
    if "commit" in record:
        valid_commit(record["commit"], "commit du résultat fusionné")
    return record


def session_record(raw: Any) -> dict[str, Any]:
    """The author session that took the ticket (T12)."""
    record = stored_record(raw, ("name", "at"))
    single_line(record["name"], "session")
    return record


def verdict_record(raw: Any) -> dict[str, Any]:
    """A verdict: its state and the commit it judged; and, once a commit was
    added after it, the tip that made it invalid (Spec §8)."""
    record = stored_record(raw, ("state", "commit", "at"), ("invalidated",))
    one_of(record["state"], VERDICT_STATES, "état de verdict")
    valid_commit(record["commit"])
    if "invalidated" in record:
        invalidated = record["invalidated"]
        if not isinstance(invalidated, dict) or set(invalidated) != {"tip", "at"}:
            raise Refusal(f"invalidation mal formée : {invalidated!r}")
        valid_commit(invalidated["tip"], "pointe qui invalide le verdict")
    return record


def incident_record(raw: Any) -> dict[str, Any]:
    """The convoy's open factory incident: the bead that carries it and, once
    it reached the escalation door, the signature of the anomalies it names."""
    record = stored_record(raw, ("bead", "at"), ("signature",))
    if not isinstance(record["bead"], str) or not BEAD_ID_RE.match(record["bead"]):
        raise Refusal(f"bead d'incident absent ou mal formé : {record['bead']!r}")
    if "signature" in record:
        valid_digest(record["signature"])
    return record


# --- list --------------------------------------------------------------------


def closing_of(convoy: dict[str, Any]) -> dict[str, Any] | None:
    """The closing of a convoy by command, from its bead: the record of
    close-convoy, when it is the one the judgement of the convoy calls for
    -- the answer that ends it, and for « accepté » its merge. None for a
    convoy closed outside the two commands, whatever it carries."""
    metadata = metadata_of(convoy)
    closed = stored_or_none(metadata.get(KEY_CLOSED), closed_record)
    judgement = stored_or_none(metadata.get(KEY_JUDGEMENT), judgement_record)
    last = final_answer(judgement) if judgement else None
    if closed is None or last is None or closed["how"] != last["response"]:
        return None
    promotion = stored_or_none(metadata.get(KEY_PROMOTION), promotion_record)
    if (closed["how"] == "accepted") != (promotion is not None and promotion["judged"] == last["commit"]):
        return None
    return closed


def cmd_list(args: argparse.Namespace) -> int:
    """The open convoys that carry the mark, and apart those found closed:
    no command closes a marked convoy yet, so each was closed outside the
    acceptance and abandon commands. What the advance command walks."""
    out = run_gc(["bd", "list", "--all", "--type", "convoy", "--has-metadata-key", KEY_MARK, "--limit", "0", "--json"])
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        raise Refusal(f"gc bd list a rendu un JSON illisible : {exc}") from exc
    if not isinstance(data, list):
        raise Refusal(f"gc bd list a rendu autre chose qu'une liste : {data!r}")
    marked = [bead for bead in data if isinstance(bead, dict) and KEY_MARK in metadata_of(bead)]
    convoys = sorted(bead["id"] for bead in marked if bead.get("status") != "closed")
    by_command = sorted(bead["id"] for bead in marked if bead.get("status") == "closed" and closing_of(bead) is not None)
    closed_outside = sorted(bead["id"] for bead in marked if bead.get("status") == "closed" and bead["id"] not in by_command)
    print(json.dumps({"ok": True, "convoys": convoys, "closed": by_command, "closed_outside": closed_outside},
                     indent=2, sort_keys=True, ensure_ascii=False))
    return 0


# --- show --------------------------------------------------------------------


class Repo:
    """The Git repository holding the ticket branches, opened only if a
    verdict has to be tied to a branch tip."""

    def __init__(self, path: str):
        self.path = path
        self._is_repo: bool | None = None

    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")}
        return subprocess.run(["git", "-C", self.path, *args], capture_output=True, text=True, env=env)

    def is_repo(self) -> bool:
        if self._is_repo is None:
            try:
                self._is_repo = self.git("rev-parse", "--git-dir").returncode == 0
            except OSError:
                self._is_repo = False
        return self._is_repo

    def tip(self, branch: str) -> str | None:
        for ref in (f"refs/heads/{branch}", f"refs/remotes/origin/{branch}"):
            proc = self.git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
            if proc.returncode == 0:
                return proc.stdout.strip()
        return None

    def is_ancestor(self, commit: str, tip: str) -> bool:
        return self.git("merge-base", "--is-ancestor", commit, tip).returncode == 0


def red_checks_rendered(convoy: dict[str, Any], tickets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The red controls the convoy carries a record of, each under the name
    a `repair` cites to restore it (`restores.kind: red_check`, T40): the
    red of its integration branch, the outage of its Acceptance Session,
    the control the author of a ticket named when it left « bloqué
    technique », and the registry of the end-of-Spec gate, red on the
    tracked elements of a ticket the operator asked to have repaired."""
    found: list[dict[str, Any]] = []
    red = convoy.get("integration_red")
    if isinstance(red, dict) and "control" in red:
        found.append({"name": red["control"], "source": "integration", "check": red.get("check", RED_CHECKS[0])})
    acceptance = convoy.get("acceptance")
    if isinstance(acceptance, dict) and "panne" in acceptance:
        found.append({
            "name": f"lancement du produit par la recette du profil au commit {acceptance['commit'][:12]} "
                    "(Acceptance Session)",
            "source": "acceptance_session"})
    for ticket in tickets:
        blocking = ticket.get("blocking_red")
        if isinstance(blocking, dict) and "control" in blocking:
            found.append({"name": blocking["control"], "source": "technically_blocked", "ticket": ticket["id"]})
        asked = [item["id"] for item in ticket.get("tracked_items") or []
                 if (item.get("request") or {}).get("state") == "resolved" and not item["request"].get("accepted")]
        if asked:
            found.append({
                "name": f"registre de la porte de fin de Spec : éléments du ticket {ticket['id']} sans état final "
                        f"({', '.join(asked)})",
                "source": "tracked_items", "ticket": ticket["id"]})
    return found


def render_counters(metadata: dict[str, Any], names: tuple[str, ...], unruled: list[dict[str, str]]) -> dict[str, Any]:
    counters: dict[str, Any] = {}
    coherent = True
    for name in names:
        key = COUNTER_PREFIX + name
        try:
            if key not in metadata:
                raise Refusal(f"compteur {name} absent : il n'a jamais été posé par la marque")
            counters[name] = counter_value(metadata[key], name)
        except Refusal as exc:
            coherent = False
            counters[name] = {"unruled": str(exc), "raw": metadata.get(key)}
            unruled.append({"field": key, "reason": str(exc)})
    if coherent and names == TICKET_COUNTERS:
        try:
            check_ticket_counters(counters)
        except Refusal as exc:
            unruled.append({"field": COUNTER_PREFIX + "correction_rounds", "reason": str(exc)})
    return counters


def verdict_is_valid(kind: str, commit: str, branch: str | None, tip: str | None, repo: Repo) -> bool:
    """Spec §8 "commit après verdict": a verdict holds only for the exact tip
    of the ticket's branch. Refuses when the commit cannot be placed on it."""
    if not repo.is_repo():
        raise Refusal(f"--repo {repo.path} n'est pas un dépôt Git : verdict {kind} impossible à relier à sa branche")
    if not branch:
        raise Refusal(f"verdict {kind} sans branche de ticket enregistrée")
    if tip is None:
        raise Refusal(f"verdict {kind} : branche du ticket introuvable dans le dépôt ({branch})")
    if commit == tip:
        return True
    if repo.is_ancestor(commit, tip):
        return False
    raise Refusal(f"verdict {kind} lié au commit {commit}, absent de la branche {branch}")


def render_ticket(ticket: dict[str, Any], repo: Repo) -> dict[str, Any]:
    metadata = metadata_of(ticket)
    status = ticket.get("status")
    unruled: list[dict[str, str]] = []

    def flag(field: str, reason: str) -> None:
        unruled.append({"field": field, "reason": reason})

    out: dict[str, Any] = {"id": ticket.get("id"), "title": ticket.get("title"), "status": status}

    mark = metadata.get(KEY_MARK)
    out["mark"] = mark
    if mark is None:
        flag(KEY_MARK, "ticket sans marque dans un convoi marqué : il n'est pas entré par la commande d'état")
    elif mark != MARK:
        flag(KEY_MARK, f"marque inconnue : {mark!r}")

    kind = metadata.get(KEY_KIND)
    line = metadata.get(KEY_DEMONSTRATION)
    out["kind"], out["demonstration_line"] = kind, line
    # The covered user stories, or None; a stored value this command did not
    # write is never rendered as stories.
    stories = None
    out["user_stories"] = None
    out["criteria"] = acceptance_criteria(ticket.get("description"))
    # The criteria as `mark` froze them with the approved graph (T19): the
    # ticket-end gate reads whether the ones on the ticket are still those.
    out["criteria_frozen"] = None
    if KEY_CRITERIA in metadata:
        try:
            graph_digest = metadata.get(KEY_GRAPH_DIGEST)
            frozen = criteria_record(metadata[KEY_CRITERIA])
            frozen["current"] = criteria_digest(out["criteria"])
            frozen["current_graph_digest"] = graph_digest if isinstance(graph_digest, str) and graph_digest else None
            frozen["identical"] = (
                frozen["current"] == frozen["digest"] and frozen["current_graph_digest"] == frozen["graph_digest"])
            out["criteria_frozen"] = frozen
        except Refusal as exc:
            out["criteria_frozen"] = {"unruled": f"{KEY_CRITERIA} : {exc}", "raw": metadata[KEY_CRITERIA]}
            flag(KEY_CRITERIA, out["criteria_frozen"]["unruled"])
    # An interface ticket carries the reference of the Validated Prototype,
    # posed by the publication door (T36): its fidelity is checked (T19).
    try:
        out["validated_prototype"] = validated_prototype(ticket.get("description"))
    except Refusal as exc:
        out["validated_prototype"] = {"unruled": str(exc)}
        flag("description", str(exc))
    out["interface"] = out["validated_prototype"] is not None
    scope = metadata.get(KEY_SCOPE)
    out["declared_scope"] = [path for path in scope.split(",") if path] if isinstance(scope, str) and scope else None
    for key, name, _, _ in SLICE_FLAGS:
        out[name] = metadata.get(key) is True
    if KEY_USER_STORIES in metadata:
        try:
            stories = out["user_stories"] = stored_user_stories(metadata[KEY_USER_STORIES])
        except Refusal as exc:
            out["user_stories"] = {"unruled": str(exc), "raw": metadata[KEY_USER_STORIES]}
            flag(KEY_USER_STORIES, f"{KEY_USER_STORIES} : {exc}")
    try:
        valid_kind(kind)
    except Refusal as exc:
        # No default: an unknown kind is not rendered as a kind.
        out["kind"] = None if kind is None else {"unruled": str(exc), "raw": kind}
        flag(KEY_KIND, str(exc))
    else:
        try:
            check_demonstration_line(kind, line)
        except Refusal as exc:
            if line is not None:
                out["demonstration_line"] = {"unruled": str(exc), "raw": line}
            flag(KEY_DEMONSTRATION, str(exc))
        try:
            check_user_stories(kind, stories)
        except Refusal as exc:
            flag(KEY_USER_STORIES, str(exc))
        for key, name, check, _ in SLICE_FLAGS:
            if key in metadata:
                try:
                    check(kind, metadata[key])
                except Refusal as exc:
                    out[name] = {"unruled": str(exc), "raw": metadata[key]}
                    flag(key, f"{key} : {exc}")

    branch = metadata.get(KEY_BRANCH)
    if branch is not None and not (isinstance(branch, str) and BRANCH_RE.match(branch)):
        flag(KEY_BRANCH, f"branche mal formée : {branch!r}")
        branch = None
    out["branch"] = branch
    tip = repo.tip(branch) if branch and repo.is_repo() else None
    out["tip"] = tip

    out["exit"] = None
    if KEY_EXIT in metadata:
        try:
            record = stored_record(metadata[KEY_EXIT], ("exit", "at"))
            one_of(record["exit"], EXITS, "sortie de ticket")
            out["exit"] = record
        except Refusal as exc:
            out["exit"] = {"unruled": str(exc), "raw": metadata[KEY_EXIT]}
            flag(KEY_EXIT, str(exc))

    verdicts: dict[str, Any] = {}
    evidence: dict[str, Any] = {}
    gates: dict[str, Any] = {}
    tdd: dict[str, Any] = {}
    groups = ((VERDICT_PREFIX, verdicts), (EVIDENCE_PREFIX, evidence), (GATE_PREFIX, gates), (TDD_PREFIX, tdd))
    for key in sorted(metadata):
        if not key.startswith(PREFIX) or key in (
            KEY_MARK, KEY_DEMONSTRATION, KEY_USER_STORIES, KEY_LAUNCH_RECIPE, KEY_PROTOTYPE_FOLD, KEY_BRANCH, KEY_EXIT,
            KEY_STOP, KEY_HANDOFF, KEY_PARK, KEY_MERGE, KEY_SESSION, KEY_TEST_REVIEW, KEY_CODE_REVIEW, KEY_MODELS,
            KEY_EVALUATION, KEY_FIDELITY, KEY_PLANNING_EXCEPTIONS, KEY_CORRECTION, KEY_OVERRIDES, KEY_CRITERIA,
            KEY_RESUME, KEY_PARK_LIFTS, KEY_FINDINGS, KEY_BLOCKING_RED,
        ):
            continue
        raw = metadata[key]
        group, name = next(((target, key[len(prefix):]) for prefix, target in groups if key.startswith(prefix)), (None, ""))
        try:
            if group is verdicts:
                one_of(name, VERDICT_KINDS, "genre de verdict")
                record = verdict_record(raw)
                try:
                    # An invalidated verdict stays invalid until it is replayed.
                    record["valid"] = (
                        verdict_is_valid(name, record["commit"], branch, tip, repo) and "invalidated" not in record)
                except Refusal as exc:
                    # No default: neither valid nor invalid, the reason instead.
                    record["unruled"] = f"{key} : {exc}"
                    flag(key, record["unruled"])
                verdicts[name] = record
            elif group is evidence:
                record = stored_record(raw, ("digest", "commit", "at"))
                valid_digest(record["digest"])
                valid_commit(record["commit"])
                evidence[name] = record
            elif group is gates:
                one_of(name, GATES, "porte")
                if name == GATE_TICKET_END:
                    # Its record is the nine verdicts and the version of the
                    # list: anything less was not written by the gate.
                    record = ticket_end_record(raw)
                else:
                    record = stored_record(raw, ("at",), ("commit",))
                    if "commit" in record:
                        valid_commit(record.get("commit"))
                gates[name] = record
            elif group is tdd:
                tdd[name] = tdd_record(name, raw)
            elif key.startswith(COUNTER_PREFIX):
                one_of(key[len(COUNTER_PREFIX):], TICKET_COUNTERS, "compteur de ticket")
            else:
                raise Refusal("champ inconnu de la commande d'état, écrit hors d'elle")
        except Refusal as exc:
            reason = f"{key} : {exc}"
            if group is not None:
                group[name] = {"unruled": reason, "raw": raw}
            flag(key, reason)
    out["verdicts"] = verdicts
    out["counters"] = render_counters(metadata, TICKET_COUNTERS, unruled)
    out["evidence"] = evidence
    out["gates"] = gates
    out["tdd"] = tdd
    out["stop"] = None
    if KEY_STOP in metadata:
        try:
            out["stop"] = stop_record(metadata[KEY_STOP])
        except Refusal as exc:
            # Still a stop: an unreadable one is never rendered as no stop.
            out["stop"] = {"unruled": f"{KEY_STOP} : {exc}", "raw": metadata[KEY_STOP]}
            flag(KEY_STOP, out["stop"]["unruled"])
    # The Ticket Handoff, the parking, the merge, the author session, the
    # review of the criterion tests, the code review, the Ticket Evaluation
    # the models per role and the correction round, each None when the ticket
    # has none; an unreadable one is never rendered as none.
    for name, key, read in (
        ("correction", KEY_CORRECTION, correction_record),
        ("test_review", KEY_TEST_REVIEW, test_review_record),
        ("code_review", KEY_CODE_REVIEW, code_review_rendered),
        ("evaluation", KEY_EVALUATION, evaluation_rendered),
        ("models", KEY_MODELS, models_record),
        ("handoff", KEY_HANDOFF, handoff_record),
        ("park", KEY_PARK, lambda raw: park_rendered(park_record(raw), ticket["id"], metadata)),
        ("merge", KEY_MERGE, merge_record),
        ("session", KEY_SESSION, session_record),
        ("resume", KEY_RESUME, resume_record),
        ("finding_classifications", KEY_FINDINGS, findings_record),
        ("blocking_red", KEY_BLOCKING_RED, blocking_red_record),
    ):
        out[name] = None
        if key in metadata:
            try:
                out[name] = read(metadata[key])
            except Refusal as exc:
                out[name] = {"unruled": f"{key} : {exc}", "raw": metadata[key]}
                flag(key, out[name]["unruled"])

    # The Planning Exceptions raised on the ticket and the anchors whose
    # deviation a resolved one accepts; then the fidelity result, whose state
    # is computed from them (T16). None, or an empty list, when there is none.
    out["planning_exceptions"], out["accepted_anchors"], out["fidelity"] = [], [], None
    if KEY_PLANNING_EXCEPTIONS in metadata:
        try:
            raised = planning_exceptions_rendered(planning_exceptions_record(metadata[KEY_PLANNING_EXCEPTIONS]), metadata)
            out["planning_exceptions"] = raised
            out["accepted_anchors"] = sorted({anchor for entry in raised if entry["accepted"] for anchor in entry["anchors"]})
        except Refusal as exc:
            out["planning_exceptions"] = {"unruled": f"{KEY_PLANNING_EXCEPTIONS} : {exc}", "raw": metadata[KEY_PLANNING_EXCEPTIONS]}
            flag(KEY_PLANNING_EXCEPTIONS, out["planning_exceptions"]["unruled"])
    if KEY_FIDELITY in metadata:
        try:
            out["fidelity"] = fidelity_rendered(fidelity_record(metadata[KEY_FIDELITY]), out["accepted_anchors"])
        except Refusal as exc:
            out["fidelity"] = {"unruled": f"{KEY_FIDELITY} : {exc}", "raw": metadata[KEY_FIDELITY]}
            flag(KEY_FIDELITY, out["fidelity"]["unruled"])

    # The overrides of the operator (T17): an empty list when there is none.
    out["overrides"] = []
    if KEY_OVERRIDES in metadata:
        try:
            out["overrides"] = overrides_rendered(metadata[KEY_OVERRIDES])
        except Refusal as exc:
            out["overrides"] = {"unruled": f"{KEY_OVERRIDES} : {exc}", "raw": metadata[KEY_OVERRIDES]}
            flag(KEY_OVERRIDES, out["overrides"]["unruled"])

    # The parkings lifted (T20), an empty list when there is none, and the
    # resumes the ticket may still take before it is parked (Spec §8, K).
    out["park_lifts"] = []
    if KEY_PARK_LIFTS in metadata:
        try:
            out["park_lifts"] = park_lifts_record(metadata[KEY_PARK_LIFTS])
        except Refusal as exc:
            out["park_lifts"] = {"unruled": f"{KEY_PARK_LIFTS} : {exc}", "raw": metadata[KEY_PARK_LIFTS]}
            flag(KEY_PARK_LIFTS, out["park_lifts"]["unruled"])
    try:
        out["resumes_left"] = resumes_left(metadata)
    except Refusal:
        # The counter or the lifts are already flagged: no default.
        out["resumes_left"] = None

    def has_gate(name: str) -> bool:
        return "at" in gates.get(name, {})

    if status == "closed" and not any(has_gate(gate) for gate in CLOSING_GATES):
        flag("status", "ticket fermé sans relevé de porte (ni porte de fin de ticket, ni retrait du graphe) : fermé hors porte")
    if status == "in_progress" and not has_gate("dispatch"):
        flag("status", "ticket démarré sans relevé de la porte de dispatch : démarré hors porte")

    out["unruled"] = unruled
    if unruled:
        out["signal"] = UNRULED
    return out


def cmd_show(args: argparse.Namespace) -> int:
    convoy, tickets = load_convoy(args.convoy)
    metadata = metadata_of(convoy)
    mark = metadata.get(KEY_MARK)
    if mark is None:
        raise NotNewFlow(args.convoy)
    # The resumes each ticket has left are counted against the bound: a
    # bound that cannot be read is a refusal, never a default.
    resumes_max()

    convoy_unruled: list[dict[str, str]] = []
    if mark != MARK:
        convoy_unruled.append({"field": KEY_MARK, "reason": f"marque inconnue : {mark!r}"})
    closing = closing_of(convoy)
    if KEY_CLOSED in metadata_of(convoy) and convoy.get("status") != "closed":
        convoy_unruled.append({"field": "status", "reason": (
            "convoi rouvert hors commande après sa fermeture sur les mots de l'approbateur : rien ne rouvre un Outcome "
            "accepté ou abandonné")})
    if convoy.get("status") == "closed" and closing is None:
        said = convoy.get("close_reason")
        convoy_unruled.append({"field": "status", "reason": (
            "convoi fermé hors commande (ni acceptation ni abandon enregistré)"
            + (f" ; raison portée : {said}" if isinstance(said, str) and said else "")
        )})
    incident: dict[str, Any] | None = None
    if KEY_INCIDENT in metadata:
        try:
            incident = incident_record(metadata[KEY_INCIDENT])
        except Refusal as exc:
            incident = {"unruled": f"{KEY_INCIDENT} : {exc}", "raw": metadata[KEY_INCIDENT]}
            convoy_unruled.append({"field": KEY_INCIDENT, "reason": incident["unruled"]})
    integration: dict[str, Any] | None = None
    if KEY_INTEGRATION in metadata:
        try:
            integration = integration_record(metadata[KEY_INTEGRATION])
        except Refusal as exc:
            integration = {"unruled": f"{KEY_INTEGRATION} : {exc}", "raw": metadata[KEY_INTEGRATION]}
            convoy_unruled.append({"field": KEY_INTEGRATION, "reason": integration["unruled"]})
    integration_red: dict[str, Any] | None = None
    if KEY_INTEGRATION_RED in metadata:
        try:
            integration_red = integration_red_record(metadata[KEY_INTEGRATION_RED])
        except Refusal as exc:
            integration_red = {"unruled": f"{KEY_INTEGRATION_RED} : {exc}", "raw": metadata[KEY_INTEGRATION_RED]}
            convoy_unruled.append({"field": KEY_INTEGRATION_RED, "reason": integration_red["unruled"]})
    grouped_request: dict[str, Any] | None = None
    if KEY_GROUPED_REQUEST in metadata:
        try:
            grouped_request = grouped_request_record(metadata[KEY_GROUPED_REQUEST])
        except Refusal as exc:
            grouped_request = {"unruled": f"{KEY_GROUPED_REQUEST} : {exc}", "raw": metadata[KEY_GROUPED_REQUEST]}
            convoy_unruled.append({"field": KEY_GROUPED_REQUEST, "reason": grouped_request["unruled"]})
    spec_end: dict[str, Any] | None = None
    if KEY_SPEC_END in metadata:
        try:
            spec_end = spec_end_record(metadata[KEY_SPEC_END])
        except Refusal as exc:
            spec_end = {"unruled": f"{KEY_SPEC_END} : {exc}", "raw": metadata[KEY_SPEC_END]}
            convoy_unruled.append({"field": KEY_SPEC_END, "reason": spec_end["unruled"]})
    outcome_evaluation: dict[str, Any] | None = None
    if KEY_OUTCOME_EVALUATION in metadata:
        try:
            outcome_evaluation = outcome_evaluation_rendered(metadata[KEY_OUTCOME_EVALUATION])
        except Refusal as exc:
            outcome_evaluation = {"unruled": f"{KEY_OUTCOME_EVALUATION} : {exc}", "raw": metadata[KEY_OUTCOME_EVALUATION]}
            convoy_unruled.append({"field": KEY_OUTCOME_EVALUATION, "reason": outcome_evaluation["unruled"]})
    end_review: dict[str, Any] | None = None
    if KEY_END_REVIEW in metadata:
        try:
            end_review = end_review_record(metadata[KEY_END_REVIEW])
            end_review["state"] = end_review_state(end_review)
        except Refusal as exc:
            end_review = {"unruled": f"{KEY_END_REVIEW} : {exc}", "raw": metadata[KEY_END_REVIEW]}
            convoy_unruled.append({"field": KEY_END_REVIEW, "reason": end_review["unruled"]})
    end_round: dict[str, Any] | None = None
    if KEY_END_ROUND in metadata:
        try:
            end_round = end_round_record(metadata[KEY_END_ROUND])
        except Refusal as exc:
            end_round = {"unruled": f"{KEY_END_ROUND} : {exc}", "raw": metadata[KEY_END_ROUND]}
            convoy_unruled.append({"field": KEY_END_ROUND, "reason": end_round["unruled"]})
    evidence_pack: dict[str, Any] | None = None
    if KEY_EVIDENCE_PACK in metadata:
        try:
            evidence_pack = evidence_pack_record(metadata[KEY_EVIDENCE_PACK])
        except Refusal as exc:
            evidence_pack = {"unruled": f"{KEY_EVIDENCE_PACK} : {exc}", "raw": metadata[KEY_EVIDENCE_PACK]}
            convoy_unruled.append({"field": KEY_EVIDENCE_PACK, "reason": evidence_pack["unruled"]})
    end_stop: dict[str, Any] | None = None
    if KEY_END_STOP in metadata:
        try:
            end_stop = end_stop_record(metadata[KEY_END_STOP])
        except Refusal as exc:
            end_stop = {"unruled": f"{KEY_END_STOP} : {exc}", "raw": metadata[KEY_END_STOP]}
            convoy_unruled.append({"field": KEY_END_STOP, "reason": end_stop["unruled"]})
    judgement: dict[str, Any] | None = None
    if KEY_JUDGEMENT in metadata:
        try:
            judgement = judgement_record(metadata[KEY_JUDGEMENT])
        except Refusal as exc:
            judgement = {"unruled": f"{KEY_JUDGEMENT} : {exc}", "raw": metadata[KEY_JUDGEMENT]}
            convoy_unruled.append({"field": KEY_JUDGEMENT, "reason": judgement["unruled"]})
    promotion: dict[str, Any] | None = None
    if KEY_PROMOTION in metadata:
        try:
            promotion = promotion_record(metadata[KEY_PROMOTION])
        except Refusal as exc:
            promotion = {"unruled": f"{KEY_PROMOTION} : {exc}", "raw": metadata[KEY_PROMOTION]}
            convoy_unruled.append({"field": KEY_PROMOTION, "reason": promotion["unruled"]})
    delivered: dict[str, Any] | None = None
    if KEY_DELIVERED in metadata:
        try:
            delivered = delivered_record(metadata[KEY_DELIVERED])
        except Refusal as exc:
            delivered = {"unruled": f"{KEY_DELIVERED} : {exc}", "raw": metadata[KEY_DELIVERED]}
            convoy_unruled.append({"field": KEY_DELIVERED, "reason": delivered["unruled"]})
    acceptance: dict[str, Any] | None = None
    if KEY_ACCEPTANCE in metadata:
        try:
            acceptance = acceptance_record(metadata[KEY_ACCEPTANCE])
        except Refusal as exc:
            acceptance = {"unruled": f"{KEY_ACCEPTANCE} : {exc}", "raw": metadata[KEY_ACCEPTANCE]}
            convoy_unruled.append({"field": KEY_ACCEPTANCE, "reason": acceptance["unruled"]})
    # The fingerprints of the pieces captured on the assembled product (T24).
    evidence: dict[str, Any] = {}
    for key in sorted(metadata):
        known = (KEY_MARK, KEY_INCIDENT, KEY_INTEGRATION, KEY_INTEGRATION_RED, KEY_GROUPED_REQUEST, KEY_SPEC_END,
                 KEY_OUTCOME_EVALUATION, KEY_END_REVIEW, KEY_END_ROUND, KEY_EVIDENCE_PACK, KEY_END_STOP, KEY_DELIVERED,
                 KEY_ACCEPTANCE, KEY_JUDGEMENT, KEY_PROMOTION, KEY_CLOSED, *(COUNTER_PREFIX + name for name in CONVOY_COUNTERS))
        if key.startswith(EVIDENCE_PREFIX):
            name = key[len(EVIDENCE_PREFIX):]
            try:
                evidence[name] = stored_record(metadata[key], ("digest", "commit", "at"))
                valid_digest(evidence[name]["digest"])
                valid_commit(evidence[name]["commit"])
            except Refusal as exc:
                evidence[name] = {"unruled": f"{key} : {exc}", "raw": metadata[key]}
                convoy_unruled.append({"field": key, "reason": evidence[name]["unruled"]})
        elif key.startswith(PREFIX) and key not in known:
            convoy_unruled.append({"field": key, "reason": f"{key} : champ inconnu de la commande d'état, écrit hors d'elle"})
    spec = metadata.get(KEY_SPEC)
    spec_digest = metadata.get(KEY_SPEC_DIGEST)
    convoy_out: dict[str, Any] = {
        "id": convoy["id"], "title": convoy.get("title"), "status": convoy.get("status"), "mark": mark,
        "spec": spec if isinstance(spec, str) and spec else None,
        "spec_digest": spec_digest if isinstance(spec_digest, str) and DIGEST_RE.match(spec_digest) else None,
        "counters": render_counters(metadata, CONVOY_COUNTERS, convoy_unruled),
        "incident": incident,
        "integration": integration,
        "integration_red": integration_red,
        "grouped_request": grouped_request,
        "spec_end": spec_end,
        "end_review": end_review,
        "end_round": end_round,
        "end_stop": end_stop,
        "delivered": delivered,
        "acceptance": acceptance,
        "judgement": judgement,
        "promotion": promotion,
        "closed": closing if convoy.get("status") == "closed" else None,
        # Delivered and Accepted are two states (Spec §9): an Outcome is
        # Accepted once merged and its convoy closed on Benjamin's words.
        "outcome": (closing["how"] if closing is not None and convoy.get("status") == "closed" else
                    "delivered" if isinstance(delivered, dict) and "unruled" not in delivered else None),
        "evidence_pack": evidence_pack,
        "outcome_evaluation": outcome_evaluation,
        "evidence": evidence,
        "unruled": convoy_unruled,
    }
    if convoy_unruled:
        convoy_out["signal"] = UNRULED

    repo = Repo(args.repo)
    rendered = [render_ticket(ticket, repo) for ticket in tickets]
    # The tracked elements of each Ticket Handoff and their final state
    # (T23): a repair is read on the ticket of the convoy that carries it.
    by_id = {ticket["id"]: ticket for ticket in rendered}
    for ticket in rendered:
        ticket["tracked_items"] = tracked_items(ticket, by_id)
        # The findings « hors ticket » of that Handoff and their state (T24).
        ticket["findings"] = findings_rendered(ticket, by_id)
    convoy_out["red_checks"] = red_checks_rendered(convoy_out, rendered)
    unruled = bool(convoy_unruled) or any(ticket["unruled"] for ticket in rendered)
    answer: dict[str, Any] = {"ok": True, "new_flow": True, "unruled": unruled, "convoy": convoy_out, "tickets": rendered}
    if unruled:
        answer["message"] = UNRULED
    print(json.dumps(answer, indent=2, sort_keys=True, ensure_ascii=False))
    return EXIT_UNRULED if unruled else 0


def cmd_ticket(args: argparse.Namespace) -> int:
    """Whether one ticket carries the mark, without naming its convoy."""
    if args.bead_json not in (None, "-"):
        raise Refusal(f"--bead-json n'accepte que « - » (le bead lu sur l'entrée standard) : {args.bead_json!r}")
    out = sys.stdin.read() if args.bead_json == "-" else run_gc(["bd", "show", args.ticket, "--json"])
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        raise Refusal(f"bead {args.ticket} illisible : {exc}") from exc
    if isinstance(data, list):
        data = data[0] if data else None
    if not isinstance(data, dict) or data.get("id") not in (None, args.ticket):
        raise Refusal(f"bead introuvable : {args.ticket}")
    mark = metadata_of(data).get(KEY_MARK)
    answer: dict[str, Any] = {"ok": mark is not None, "new_flow": mark is not None, "ticket": args.ticket}
    status = 0
    if mark is None:
        answer["message"] = f"{args.ticket} : pas un ticket du nouveau flux"
        status = EXIT_NOT_NEW_FLOW
    else:
        answer["mark"] = mark
        if mark != MARK:
            answer.update(unruled=True, message=f"{UNRULED} : marque inconnue : {mark!r}")
            status = EXIT_UNRULED
    print(json.dumps(answer, indent=2, sort_keys=True, ensure_ascii=False))
    return status


# --- writes ------------------------------------------------------------------


def done(convoy_id: str, bead_id: str, written: dict[str, Any]) -> int:
    print(json.dumps({"ok": True, "convoy": convoy_id, "bead": bead_id, "written": written},
                     indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def marked_ticket(convoy_id: str, ticket_id: str | None) -> dict[str, Any]:
    """The named ticket of a marked convoy; refuses anything else."""
    convoy, tickets = load_convoy(convoy_id)
    require_marked(convoy)
    return marked_ticket_among(tickets, convoy_id, ticket_id)


def marked_ticket_among(tickets: list[dict[str, Any]], convoy_id: str, ticket_id: str | None) -> dict[str, Any]:
    if not ticket_id:
        raise Refusal("ticket absent : cette écriture porte sur un ticket du convoi")
    for ticket in tickets:
        if ticket.get("id") == ticket_id:
            if metadata_of(ticket).get(KEY_MARK) != MARK:
                raise Refusal(f"{UNRULED} : le ticket {ticket_id} ne porte pas la marque du nouveau flux")
            return ticket
    raise Refusal(f"le ticket {ticket_id} n'appartient pas au convoi {convoy_id}")


def entries_by_ticket(
    entries: list[str], tickets: list[dict[str, Any]], convoy_id: str, option: str, shape: str, twice: str,
) -> dict[str, str]:
    """The `TICKET=VALUE` entries of one repeatable option of `mark`, by ticket id."""
    tracked = {ticket.get("id") for ticket in tickets}
    values: dict[str, str] = {}
    for entry in entries:
        ticket_id, sep, value = entry.partition("=")
        if not sep or not ticket_id:
            raise Refusal(f"{option} mal formé : {entry!r} (attendu : {shape})")
        if ticket_id not in tracked:
            raise Refusal(f"le ticket {ticket_id} n'appartient pas au convoi {convoy_id}")
        if ticket_id in values:
            raise Refusal(f"{twice} pour le ticket {ticket_id}")
        values[ticket_id] = value
    return values


def demonstration_lines(entries: list[str], tickets: list[dict[str, Any]], convoy_id: str) -> dict[str, str]:
    """The `--demonstration-line TICKET=LINE` entries, by ticket id."""
    lines = entries_by_ticket(
        entries, tickets, convoy_id, "--demonstration-line", "TICKET=LIGNE", "deux lignes de démonstration")
    return {ticket_id: valid_demonstration_line(line) for ticket_id, line in lines.items()}


def user_stories(entries: list[str], tickets: list[dict[str, Any]], convoy_id: str) -> dict[str, list[str]]:
    """The `--user-stories TICKET=N,N` entries, by ticket id."""
    stories = entries_by_ticket(
        entries, tickets, convoy_id, "--user-stories", "TICKET=N,N", "deux listes de user stories")
    return {ticket_id: valid_user_stories(value.split(",")) for ticket_id, value in stories.items()}


def cmd_mark(args: argparse.Namespace) -> int:
    convoy, tickets = load_convoy(args.convoy)
    never_reopened(convoy)
    lines = demonstration_lines(args.demonstration_line, tickets, args.convoy)
    stories = user_stories(args.user_stories, tickets, args.convoy)
    tracked = {ticket.get("id") for ticket in tickets}
    named = {KEY_LAUNCH_RECIPE: args.establishes_launch_recipe, KEY_PROTOTYPE_FOLD: args.prototype_fold}
    for ticket_id in [*args.establishes_launch_recipe, *args.prototype_fold]:
        if ticket_id not in tracked:
            raise Refusal(f"le ticket {ticket_id} n'appartient pas au convoi {args.convoy}")
    establishing = set(args.establishes_launch_recipe) | {
        ticket["id"] for ticket in tickets if KEY_LAUNCH_RECIPE in metadata_of(ticket)
    }
    if len(establishing) > 1:
        raise Refusal(
            f"plusieurs tickets établissent la recette de lancement ({', '.join(sorted(establishing))}) : "
            "une seule tranche l'établit, la première du graphe"
        )
    writes: list[tuple[str, dict[str, Any], tuple[str, ...]]] = []
    for bead, counters in [*((ticket, TICKET_COUNTERS) for ticket in tickets), (convoy, CONVOY_COUNTERS)]:
        metadata = metadata_of(bead)
        mark = metadata.get(KEY_MARK)
        if mark not in (None, MARK):
            raise Refusal(f"{UNRULED} : {bead['id']} porte une marque inconnue ({mark!r})")
        values: dict[str, Any] = {}
        if bead is not convoy:
            # A ticket is marked with its entry fields or not at all: a marked
            # slice without its demonstration line would be an "état sans règle".
            stored, given = metadata.get(KEY_DEMONSTRATION), lines.get(bead["id"])
            if stored is not None and given is not None and stored != given:
                raise Refusal(
                    f"le ticket {bead['id']} porte déjà une ligne de démonstration ({stored!r}) : "
                    "elle est gelée avec le graphe approuvé et ne se réécrit pas"
                )
            try:
                kind = valid_kind(metadata.get(KEY_KIND))
                check_demonstration_line(kind, stored if stored is not None else given)
                covered = stored_user_stories(metadata[KEY_USER_STORIES]) if KEY_USER_STORIES in metadata else None
                wanted = stories.get(bead["id"])
                if covered is not None and wanted is not None and covered != wanted:
                    raise Refusal(
                        f"il porte déjà ses user stories couvertes ({', '.join(covered)}) : "
                        "elles sont gelées avec le graphe approuvé et ne se réécrivent pas"
                    )
                check_user_stories(kind, covered if covered is not None else wanted)
            except Refusal as exc:
                raise Refusal(f"ticket {bead['id']} : {exc}") from exc
            if stored is None and given is not None:
                values[KEY_DEMONSTRATION] = given
            if covered is None and wanted is not None:
                values[KEY_USER_STORIES] = encode({"stories": wanted})
            try:
                for key, _, check, said in SLICE_FLAGS:
                    if key in metadata:
                        check(kind, metadata[key])
                    elif bead["id"] in named[key]:
                        if mark is not None:
                            raise Refusal(
                                f"il porte déjà la marque sans {said} : ce champ est "
                                "gelé avec le graphe approuvé et ne se réécrit pas"
                            )
                        check(kind, True)
                        values[key] = "true"
            except Refusal as exc:
                raise Refusal(f"ticket {bead['id']} : {exc}") from exc
            # The criteria are frozen with the approved graph (Spec §2): at
            # the mark, and again only when the publication door has since
            # published the ticket under another approved digest (a patch).
            frozen = frozen_criteria(bead)
            if KEY_CRITERIA in metadata:
                try:
                    stale = criteria_record(metadata[KEY_CRITERIA])["graph_digest"] != frozen["graph_digest"]
                except Refusal as exc:
                    raise Refusal(f"ticket {bead['id']} : {KEY_CRITERIA} : {exc}") from exc
            else:
                stale = True
            if stale and bead.get("status") != "closed":
                values[KEY_CRITERIA] = encode(frozen)
        if mark is None:
            # Counters start at an explicit 0: a counter that is absent later
            # is an "état sans règle", never read as a default.
            values[KEY_MARK] = MARK
            values.update({COUNTER_PREFIX + name: 0 for name in counters if COUNTER_PREFIX + name not in metadata})
        # The manual lifecycle goes in the same write as the convoy's mark: a
        # marked convoy is never one the convoy sweep could close.
        labels = (LABEL_MANUAL_LIFECYCLE,) if bead is convoy and LABEL_MANUAL_LIFECYCLE not in labels_of(bead) else ()
        if values or labels:
            writes.append((bead["id"], values, labels))
    # Tickets first, the convoy last: the convoy's mark is what makes this a
    # new-flow convoy, so an interrupted marking leaves an unmarked convoy.
    for bead_id, values, labels in writes:
        write_metadata(bead_id, values, labels)
    print(json.dumps({"ok": True, "convoy": args.convoy, "mark": MARK, "marked": [bead_id for bead_id, _, _ in writes]},
                     indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def cmd_set_branch(args: argparse.Namespace) -> int:
    marked_ticket(args.convoy, args.ticket)
    if not isinstance(args.branch, str) or not BRANCH_RE.match(args.branch):
        raise Refusal(f"branche absente ou mal formée : {args.branch!r}")
    values = {KEY_BRANCH: args.branch}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def cmd_set_session(args: argparse.Namespace) -> int:
    """The author session that takes a ticket (T12): one session works one
    ticket. The same write puts the ticket in progress under that session."""
    convoy, tickets = load_convoy(args.convoy)
    require_marked(convoy)
    ticket = marked_ticket_among(tickets, args.convoy, args.ticket)
    name = single_line(args.session, "session")
    metadata = metadata_of(ticket)
    if ticket.get("status") == "closed" or any(GATE_PREFIX + gate in metadata for gate in CLOSING_GATES):
        raise Refusal(f"le ticket {args.ticket} est fermé : aucune session ne le prend")
    if GATE_PREFIX + "dispatch" not in metadata:
        raise Refusal(f"le ticket {args.ticket} n'a pas été démarré par la porte de dispatch : aucune session ne le prend")
    for other in tickets:
        if other.get("id") == args.ticket or KEY_SESSION not in metadata_of(other):
            continue
        try:
            taken = session_record(metadata_of(other)[KEY_SESSION])["name"]
        except Refusal:
            continue
        if taken == name:
            raise Refusal(
                f"la session {name} a déjà pris le ticket {other.get('id')} : une session neuve par ticket")
    current = None
    if KEY_SESSION in metadata:
        try:
            current = session_record(metadata[KEY_SESSION])
        except Refusal:
            current = None
    if current and current["name"] == name and ticket.get("status") == "in_progress":
        return done(args.convoy, args.ticket, {})
    values = {KEY_SESSION: encode({"name": name, "at": now()}), KEY_SESSION_NAME: name}
    update = ["bd", "update", args.ticket, "--status", "in_progress"]
    for key, value in values.items():
        update += ["--set-metadata", f"{key}={value}"]
    run_gc(update)
    return done(args.convoy, args.ticket, {**values, "status": "in_progress"})


def cmd_set_exit(args: argparse.Namespace) -> int:
    marked_ticket(args.convoy, args.ticket)
    one_of(args.exit, EXITS, "sortie de ticket")
    values = {KEY_EXIT: encode({"exit": args.exit, "at": now()})}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def cmd_set_verdict(args: argparse.Namespace) -> int:
    marked_ticket(args.convoy, args.ticket)
    one_of(args.kind, VERDICT_KINDS, "genre de verdict")
    one_of(args.state, VERDICT_STATES, "état de verdict")
    valid_commit(args.commit, "commit du verdict")
    values = {VERDICT_PREFIX + args.kind: encode({"state": args.state, "commit": args.commit, "at": now()})}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def counter_target(args: argparse.Namespace) -> tuple[dict[str, Any], tuple[str, ...]]:
    """The bead a counter write lands on, and the counters that bead owns."""
    names = args.counter if isinstance(args.counter, list) else [args.counter]
    if not names or any(name is None for name in names):
        raise Refusal("compteur absent : --counter est obligatoire")
    if args.ticket:
        bead, allowed, scope = marked_ticket(args.convoy, args.ticket), TICKET_COUNTERS, "compteur de ticket"
    else:
        convoy, _ = load_convoy(args.convoy)
        require_marked(convoy)
        bead, allowed, scope = convoy, CONVOY_COUNTERS, "compteur de convoi"
    for name in names:
        one_of(name, allowed, scope)
    return bead, allowed


def write_counters(args: argparse.Namespace, bead: dict[str, Any], allowed: tuple[str, ...], changes: dict[str, int]) -> int:
    metadata = metadata_of(bead)
    counters = {name: counter_value(metadata.get(COUNTER_PREFIX + name), name) for name in allowed}
    counters.update(changes)
    if allowed == TICKET_COUNTERS:
        check_ticket_counters(counters)
    values = {COUNTER_PREFIX + name: counters[name] for name in changes}
    write_metadata(bead["id"], values)
    return done(args.convoy, bead["id"], values)


def cmd_set_counter(args: argparse.Namespace) -> int:
    bead, allowed = counter_target(args)
    if not isinstance(args.value, str) or not re.fullmatch(r"\d+", args.value):
        raise Refusal(f"valeur de compteur refusée : {args.value!r} n'est pas un entier positif ou nul")
    return write_counters(args, bead, allowed, {args.counter: int(args.value)})


def cmd_bump_counter(args: argparse.Namespace) -> int:
    bead, allowed = counter_target(args)
    metadata = metadata_of(bead)
    changes = {
        name: counter_value(metadata.get(COUNTER_PREFIX + name), name) + 1
        for name in dict.fromkeys(args.counter)
    }
    return write_counters(args, bead, allowed, changes)


def cmd_add_evidence(args: argparse.Namespace) -> int:
    if args.ticket == args.convoy:
        # A piece of the end of the Spec (the Outcome Evaluation, T24) is
        # captured on the assembled product: it belongs to the convoy.
        require_marked(load_convoy(args.convoy)[0])
    else:
        marked_ticket(args.convoy, args.ticket)
    if not isinstance(args.piece, str) or not PIECE_RE.match(args.piece):
        raise Refusal(f"nom de pièce absent ou mal formé : {args.piece!r} (lettres, chiffres, _ et . seulement)")
    valid_digest(args.digest)
    valid_commit(args.commit, "commit de la pièce")
    values = {EVIDENCE_PREFIX + args.piece: encode({"digest": args.digest, "commit": args.commit, "at": now()})}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def cmd_record_gate(args: argparse.Namespace) -> int:
    marked_ticket(args.convoy, args.ticket)
    one_of(args.gate, GATES, "porte")
    if args.gate == GATE_TICKET_END:
        raise Refusal(
            "le relevé de la porte de fin de ticket s'écrit avec la fermeture du ticket, ses neuf verdicts et la "
            "version de la liste : close-ticket, appelé par bin/ticket-end")
    record: dict[str, Any] = {"at": now()}
    if args.commit is not None:
        record["commit"] = valid_commit(args.commit, f"commit du relevé de porte {args.gate}")
    values = {GATE_PREFIX + args.gate: encode(record)}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def cmd_close_ticket(args: argparse.Namespace) -> int:
    """The ticket-end gate closes a ticket (T19, Spec §9): its record -- the
    commit of the ticket that was merged, the version of the list, the nine
    verdicts -- and the closed status go in one tracker write, so a ticket
    is never closed without its record nor recorded without being closed.
    The verdicts are computed by bin/ticket-end; a list that is not the nine
    conditions, all passing, is refused."""
    ticket = marked_ticket(args.convoy, args.ticket)
    metadata = metadata_of(ticket)
    if ticket.get("status") == "closed" or any(GATE_PREFIX + gate in metadata for gate in CLOSING_GATES):
        raise Refusal(f"le ticket {args.ticket} est déjà fermé, ou porte déjà un relevé de fermeture")
    commit = valid_commit(args.commit, "commit du relevé de la porte de fin de ticket")
    given = json_argument(args.file, "relevé de la porte de fin de ticket")
    unknown = sorted(set(given) - {"version", "conditions"})
    if unknown:
        raise Refusal(f"champs inconnus dans le relevé de la porte : {', '.join(unknown)}")
    if given.get("version") != TICKET_END_VERSION:
        raise Refusal(
            f"version de la liste de conditions inconnue : {given.get('version')!r} (attendu : {TICKET_END_VERSION})")
    record = {"at": now(), "commit": commit, "version": TICKET_END_VERSION,
              "conditions": ticket_end_conditions(given.get("conditions"))}
    values = {GATE_PREFIX + GATE_TICKET_END: encode(record)}
    update = ["bd", "update", args.ticket, "--status", "closed"]
    for key, value in values.items():
        update += ["--set-metadata", f"{key}={value}"]
    run_gc(update)
    print(json.dumps({"ok": True, "convoy": args.convoy, "bead": args.ticket, "closed": True, "written": values},
                     indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def cmd_set_tdd(args: argparse.Namespace) -> int:
    """Record one proven step of a ticket's TDD. The order of the steps is
    held here, under the lock: bin/tdd-step proves a step, this refuses one
    that does not follow."""
    ticket = marked_ticket(args.convoy, args.ticket)
    metadata = metadata_of(ticket)
    step = one_of(args.step, TDD_STEPS, "étape du TDD")
    commit = valid_commit(args.commit, f"commit de l'étape {step}")
    if KEY_STOP in metadata:
        raise Refusal(f"ticket arrêté : aucune étape ne s'enregistre sur {args.ticket} tant que l'arrêt n'est pas levé")
    kind = valid_kind(metadata.get(KEY_KIND))
    if (step == "prefactoring") != (kind == KIND_WITHOUT_RED):
        raise Refusal(f"l'étape {step} ne s'enregistre pas sur un ticket {kind}")
    known = {name: tdd_record(name, metadata[TDD_PREFIX + name]) for name in TDD_STEPS if TDD_PREFIX + name in metadata}
    record: dict[str, Any] = {"commit": commit, "at": now()}
    if step in TDD_STEPS_WITH_BASE:
        record["base"] = valid_commit(args.base, f"commit de départ de l'étape {step}")
    elif args.base is not None:
        raise Refusal(f"--base n'a pas de sens pour l'étape {step}")
    if step == "amendment":
        record["reason"] = single_line(args.reason, "raison de l'amendement")
    elif args.reason is not None:
        raise Refusal(f"--reason n'a pas de sens pour l'étape {step}")

    amended_at = known.get("amendment", {}).get("commit")
    if step == "freeze" and known.get("red", {}).get("commit") != commit:
        raise Refusal(f"gel sans preuve du rouge au même commit ({commit}) : le gel suit l'étape rouge")
    if step in ("red", "freeze") and "freeze" in known and amended_at != commit:
        raise Refusal(
            f"les tests de {args.ticket} sont gelés : un nouveau {'rouge' if step == 'red' else 'gel'} "
            "ne s'enregistre qu'au commit de l'amendement"
        )
    if step == "freeze" and amended_at != commit:
        # Spec §5: the criterion tests are read by a reviewer between red and
        # freeze. An amended test is read by the code review instead (§6).
        require_favorable_test_review(metadata, commit)
    if step == "amendment":
        if "freeze" not in known:
            raise Refusal("amendement sans gel : il n'y a aucun test gelé à amender")
        if "amendment" in known:
            raise Refusal(f"un seul amendement par ticket : {args.ticket} en porte déjà un (commit {amended_at})")
    if step == "green" and "freeze" not in known:
        raise Refusal("vert sans gel : le vert se prouve sur des tests gelés")
    values = {TDD_PREFIX + step: encode(record)}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def require_favorable_test_review(metadata: dict[str, Any], commit: str) -> None:
    """The freeze of a ticket's criterion tests follows a favorable review
    of those tests, given at the same commit, with no other review open."""
    refusal = "gel sans verdict favorable de la relecture des tests de critère (bin/test-review)"
    if KEY_TEST_REVIEW not in metadata:
        raise Refusal(f"{refusal} : aucune relecture n'est enregistrée")
    try:
        record = test_review_record(metadata[KEY_TEST_REVIEW])
    except Refusal as exc:
        raise Refusal(f"{refusal} : relecture illisible ({exc})") from exc
    if "request" in record:
        raise Refusal(f"{refusal} : une relecture est demandée et n'a pas rendu son verdict")
    last = record["rounds"][-1] if record["rounds"] else None
    if last is None or last["verdict"] != "favorable":
        raise Refusal(f"{refusal} : la dernière relecture refuse au moins un test")
    if last["commit"] != commit:
        raise Refusal(f"{refusal} : la relecture porte sur le commit {last['commit']}, le gel sur {commit}")


def review_target(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """The ticket a review write lands on, its metadata and its review
    record so far."""
    ticket = marked_ticket(args.convoy, args.ticket)
    metadata = metadata_of(ticket)
    if KEY_STOP in metadata:
        raise Refusal(f"ticket arrêté : aucune relecture ne s'enregistre sur {args.ticket} tant que l'arrêt n'est pas levé")
    record = test_review_record(metadata[KEY_TEST_REVIEW]) if KEY_TEST_REVIEW in metadata else {"rounds": []}
    return ticket, metadata, record


def json_argument(path: Any, what: str) -> dict[str, Any]:
    try:
        given = json.loads(Path(path or "").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise Refusal(f"{what} illisible (--file {path!r}) : {exc}") from exc
    if not isinstance(given, dict):
        raise Refusal(f"{what} mal formé : un objet JSON est attendu")
    return given


def cmd_open_test_review(args: argparse.Namespace) -> int:
    """Open the review of a ticket's criterion tests (T13): the tests proven
    red at `--commit`, with the fingerprints the freeze will seal. The same
    request again writes nothing; tests a reviewer refused are not reviewed
    again unchanged."""
    _, metadata, record = review_target(args)
    commit = valid_commit(args.commit, "commit de la relecture")
    kind = valid_kind(metadata.get(KEY_KIND))
    if kind == KIND_WITHOUT_RED:
        raise Refusal(f"un {kind} n'a pas de tests de critère à relire : il n'a pas d'étape rouge")
    known = {name: tdd_record(name, metadata[TDD_PREFIX + name]) for name in TDD_STEPS if TDD_PREFIX + name in metadata}
    if "freeze" in known:
        raise Refusal(f"les tests de {args.ticket} sont gelés : la relecture précède le gel")
    if known.get("red", {}).get("commit") != commit:
        raise Refusal(f"relecture sans preuve du rouge au même commit ({commit}) : elle suit l'étape rouge")
    given = json_argument(args.file, "demande de relecture")
    unknown = sorted(set(given) - {"files", "criteria"})
    if unknown:
        raise Refusal(f"champs inconnus dans la demande de relecture : {', '.join(unknown)}")
    files = review_fingerprints(given.get("files"))
    criteria = review_criteria(given.get("criteria"), files)
    request = record.get("request")
    if request and (request["commit"], request["files"], request["criteria"]) == (commit, files, criteria):
        return done(args.convoy, args.ticket, {})
    for value in record["rounds"]:
        if value["files"] != files:
            continue
        if value["verdict"] == "unfavorable":
            raise Refusal(
                f"les tests refusés par la relecture n'ont pas changé ({args.ticket}) : "
                "un test refusé est corrigé avant d'être relu")
        if value["commit"] == commit and value is record["rounds"][-1]:
            raise Refusal(f"ces tests sont déjà relus favorablement au commit {commit} : il reste à les geler")
    record["request"] = {"commit": commit, "files": files, "criteria": criteria, "launches": [], "at": now()}
    values = {KEY_TEST_REVIEW: encode(record)}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def cmd_launch_test_review(args: argparse.Namespace) -> int:
    """Record that a reviewer session was sent the open review: the first
    launch, then one relaunch when the first gave no result."""
    _, _, record = review_target(args)
    request = record.get("request")
    if not request:
        raise Refusal(f"aucune relecture n'est demandée sur {args.ticket} : rien à lancer")
    if not isinstance(args.bead, str) or not BEAD_ID_RE.match(args.bead):
        raise Refusal(f"bead de relecture absent ou mal formé : {args.bead!r}")
    if len(request["launches"]) >= TEST_REVIEW_MAX_LAUNCHES:
        raise Refusal(
            f"une seule relance par relecture : {args.ticket} en a déjà lancé {len(request['launches'])} "
            "sans résultat")
    request["launches"].append({"bead": args.bead, "at": now()})
    values = {KEY_TEST_REVIEW: encode(record)}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def cmd_record_test_review(args: argparse.Namespace) -> int:
    """Record the answers of a reviewer to the open review, one per
    criterion test, and compute the verdict. A second refusal stops the
    ticket in the same tracker write (Spec §8: one return to the author)."""
    _, _, record = review_target(args)
    request = record.get("request")
    if not request:
        raise Refusal(f"aucune relecture n'est demandée sur {args.ticket} : un verdict répond à une demande ouverte")
    given = json_argument(args.file, "verdict de relecture")
    problems = [f"champ inconnu : {name}" for name in sorted(set(given) - {"commit", "files", "tests", "recorded_by"})]
    if given.get("commit") != request["commit"]:
        problems.append(f"le verdict porte sur le commit {given.get('commit')!r}, la demande sur {request['commit']}")
    if given.get("files") != request["files"]:
        problems.append("le verdict porte sur d'autres empreintes de tests que la demande")
    recorded_by = given.get("recorded_by")
    if not isinstance(recorded_by, str) or not recorded_by.strip() or "\n" in recorded_by:
        problems.append(f"session du relecteur absente ou mal formée : {recorded_by!r}")
    answers = given.get("tests") if isinstance(given.get("tests"), dict) else {}
    expected = review_tests(request["criteria"])
    problems += [f"test inconnu de la demande : {test_id}" for test_id in sorted(set(answers) - set(expected))]
    tests: dict[str, dict[str, str]] = {}
    for test_id in expected:
        answer = answers.get(test_id)
        state = answer.get("state") if isinstance(answer, dict) else None
        reason = " ".join(str(answer.get("reason") or "").split()) if isinstance(answer, dict) else ""
        if answer is None:
            problems.append(f"pas de verdict pour le test {test_id}")
        elif state not in VERDICT_STATES:
            problems.append(f"état hors de la liste fermée pour {test_id} : {state!r} (attendu : {', '.join(VERDICT_STATES)})")
        elif state == "unfavorable" and not reason:
            problems.append(f"refus sans raison pour {test_id}")
        else:
            tests[test_id] = {"state": state, "reason": reason} if state == "unfavorable" else {"state": state}
    if problems:
        raise Refusal("verdict de relecture hors contrat : " + " ; ".join(problems))
    refused = [test_id for test_id in expected if tests[test_id]["state"] == "unfavorable"]
    verdict = "unfavorable" if refused else "favorable"
    record["rounds"].append({
        "commit": request["commit"], "files": request["files"], "verdict": verdict, "tests": tests,
        "recorded_by": recorded_by.strip(), "at": now()})
    del record["request"]
    refusals = review_refusals(record)
    values = {KEY_TEST_REVIEW: encode(record)}
    stopped = bool(refused) and refusals >= TEST_REVIEW_MAX_REFUSALS
    if stopped:
        detail = f"second refus de la relecture des tests de critère : {', '.join(refused)}"
        values[KEY_STOP] = encode({"reason": STOP_TEST_REVIEW_REFUSED, "detail": detail, "at": now()})
    write_metadata(args.ticket, values)
    print(json.dumps({"ok": True, "convoy": args.convoy, "bead": args.ticket, "verdict": verdict, "refused": refused,
                      "refusals": refusals, "stopped": stopped, "written": values},
                     indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def cmd_set_model(args: argparse.Namespace) -> int:
    """Record the agent, provider and model a delivery role runs on for this
    ticket (T14): what says whether the reviewer differs from the author."""
    ticket = marked_ticket(args.convoy, args.ticket)
    metadata = metadata_of(ticket)
    role = one_of(args.role, MODEL_ROLES, "rôle de livraison")
    entry = {name: single_line(getattr(args, name), f"valeur --{name} (agent, fournisseur ou modèle du rôle {role})")
             for name in ("agent", "provider", "model")}
    record = models_record(metadata[KEY_MODELS]) if KEY_MODELS in metadata else {}
    known = record.get(role)
    if known and {name: known[name] for name in entry} == entry:
        return done(args.convoy, args.ticket, {})
    record[role] = {**entry, "at": now()}
    values = {KEY_MODELS: encode(record)}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def code_review_target(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    """The metadata of the ticket a code-review write lands on, and its
    code review so far."""
    metadata = metadata_of(marked_ticket(args.convoy, args.ticket))
    if KEY_STOP in metadata:
        raise Refusal(f"ticket arrêté : aucune revue ne s'enregistre sur {args.ticket} tant que l'arrêt n'est pas levé")
    record = code_review_record(metadata[KEY_CODE_REVIEW]) if KEY_CODE_REVIEW in metadata else {"rounds": []}
    return metadata, record


def models_of_review(metadata: dict[str, Any]) -> dict[str, Any]:
    known = models_record(metadata[KEY_MODELS]) if KEY_MODELS in metadata else {}
    author, reviewer = ((known.get(role) or {}).get("model") for role in ("author", "reviewer"))
    same = None if author is None or reviewer is None else normalized_model(author) == normalized_model(reviewer)
    return {"author": author, "reviewer": reviewer, "same_model": same}


def cmd_open_code_review(args: argparse.Namespace) -> int:
    """Open a round of the code review of a ticket (T14, Spec §6) at the
    commit its author finished at: the review itself, or the judgement of
    the answers given to its Blocking Findings. The same request again
    writes nothing."""
    metadata, record = code_review_target(args)
    kind = one_of(args.kind, CODE_REVIEW_KINDS, "genre de revue")
    commit = valid_commit(args.commit, "commit de la revue")
    base = valid_commit(args.base, "commit de départ de la revue")
    finished = KEY_EXIT in metadata and stored_record(metadata[KEY_EXIT], ("exit", "at"))["exit"] == "finished"
    if not finished:
        raise Refusal(f"le ticket {args.ticket} n'est pas terminé : la revue de code suit la sortie « terminé »")
    handoff = handoff_record(metadata[KEY_HANDOFF]) if KEY_HANDOFF in metadata else None
    if handoff is None or handoff["partial"] or handoff["commit"] != commit:
        raise Refusal(
            f"le Ticket Handoff de {args.ticket} n'est pas complet au commit {commit} : la revue porte sur le commit "
            "où l'auteur a terminé")
    questions: list[dict[str, str]] = []
    if args.file is not None:
        given = json_argument(args.file, "questions fermées de la revue")
        unknown = sorted(set(given) - {"questions"})
        if unknown:
            raise Refusal(f"champs inconnus dans les questions fermées : {', '.join(unknown)}")
        questions = review_questions(given.get("questions"))
    models = models_of_review(metadata)
    request = record.get("request")
    wanted = (kind, commit, base, questions)
    if request and tuple(request[name] for name in ("kind", "commit", "base", "questions")) == wanted:
        if request["models"] == models:
            return done(args.convoy, args.ticket, {})
        # The same review, sent to a reviewer of another model: its launches stay counted.
        request["models"] = models
    else:
        last = record["rounds"][-1] if record["rounds"] else None
        if last and last["verdict"] == "unfavorable":
            if last["kind"] == "judgement":
                raise Refusal(
                    f"le ticket {args.ticket} est encore refusé après son tour de correction : aucune revue ne s'ouvre")
            waiting = ", ".join(blocking_ids(last))
            if kind == "review":
                raise Refusal(
                    f"des Blocking Findings attendent leur réponse et leur jugement ({waiting}) : "
                    "aucune autre revue ne s'ouvre avant")
            unanswered = [finding_id for finding_id in blocking_ids(last) if finding_id not in last.get("responses", {})]
            if unanswered:
                raise Refusal(
                    f"Blocking Finding sans réponse ({', '.join(unanswered)}) : chaque constat reçoit « corrigé » ou "
                    "« contesté » avant son jugement")
            if base != last["commit"]:
                raise Refusal(
                    f"le jugement porte sur la correction faite depuis le commit revu ({last['commit']}), non depuis {base}")
            if questions:
                raise Refusal("un jugement ne pose pas de questions fermées : il juge la liste des Blocking Findings")
        elif kind == "judgement":
            raise Refusal(f"aucun Blocking Finding à juger sur {args.ticket} : le jugement suit une revue défavorable")
        elif last and last["commit"] == commit:
            raise Refusal(f"le ticket {args.ticket} est déjà revu favorablement au commit {commit}")
        record["request"] = {"kind": kind, "commit": commit, "base": base, "questions": questions, "launches": [],
                             "models": models, "at": now()}
    values = {KEY_CODE_REVIEW: encode(record)}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def cmd_launch_code_review(args: argparse.Namespace) -> int:
    """Record that a reviewer session was sent the open round: the first
    launch, then one relaunch when the first gave no result (Spec §6)."""
    _, record = code_review_target(args)
    request = record.get("request")
    if not request:
        raise Refusal(f"aucune revue de code n'est demandée sur {args.ticket} : rien à lancer")
    if not isinstance(args.bead, str) or not BEAD_ID_RE.match(args.bead):
        raise Refusal(f"bead de revue absent ou mal formé : {args.bead!r}")
    if len(request["launches"]) >= CODE_REVIEW_MAX_LAUNCHES:
        raise Refusal(
            f"une seule relance par revue : {args.ticket} en a déjà lancé {len(request['launches'])} sans résultat")
    request["launches"].append({"bead": args.bead, "at": now()})
    values = {KEY_CODE_REVIEW: encode(record)}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def given_findings(given: dict[str, Any], number: int, problems: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """The findings a reviewer hands in, as they are stored: a finding given
    as blocking whose citation does not hold is recorded as non-blocking,
    with the reason (Spec §6)."""
    findings: list[dict[str, Any]] = []
    demoted: list[dict[str, str]] = []
    raw = given.get("findings", [])
    if not isinstance(raw, list):
        problems.append("findings mal formé : une liste de constats est attendue")
        raw = []
    for position, finding in enumerate(raw, start=1):
        where = f"constat {position}"
        if not isinstance(finding, dict):
            problems.append(f"{where} mal formé : un objet est attendu")
            continue
        unknown = sorted(set(finding) - {"axis", "blocking", "summary", "citation", "citation_refused"})
        if unknown:
            problems.append(f"{where} : champs inconnus : {', '.join(unknown)}")
        if finding.get("axis") not in REVIEW_AXES:
            problems.append(f"{where} : axe hors de la liste fermée : {finding.get('axis')!r} (attendu : {', '.join(REVIEW_AXES)})")
        summary = finding.get("summary")
        if not isinstance(summary, str) or not summary.strip() or "\n" in summary or len(summary) > MAX_FINDING_LINE:
            problems.append(f"{where} : résumé absent ou mal formé (attendu : une ligne non vide d'au plus {MAX_FINDING_LINE} caractères)")
            summary = ""
        if not isinstance(finding.get("blocking"), bool):
            problems.append(f"{where} : blocking mal formé : {finding.get('blocking')!r} (attendu : true ou false)")
        stored: dict[str, Any] = {"id": f"F{number}.{position}", "axis": finding.get("axis"),
                                  "blocking": finding.get("blocking") is True, "summary": summary.strip()}
        citation, reason = citation_of(finding)
        if citation is not None:
            stored["citation"] = citation
        if stored["blocking"] and reason is not None:
            stored["blocking"] = False
            stored["demoted"] = f"refusé comme bloquant : {reason}"
            demoted.append({"id": stored["id"], "reason": stored["demoted"]})
        findings.append(stored)
    return findings, demoted


def cmd_record_code_review(args: argparse.Namespace) -> int:
    """Record what a reviewer session hands in for the open round, and
    compute the verdict (T14, Spec §6). A review: its findings, each
    blocking only with a citation that holds, and one answer per closed
    question, a « non » being a Blocking Finding. A judgement: one state per
    Blocking Finding of the review it judges. The verdict of the family
    `code_review` is written in the same tracker write."""
    _, record = code_review_target(args)
    request = record.get("request")
    if not request:
        raise Refusal(f"aucune revue de code n'est demandée sur {args.ticket} : un verdict répond à une demande ouverte")
    given = json_argument(args.file, "revue de code")
    review = request["kind"] == "review"
    known = {"commit", "recorded_by"} | ({"findings", "answers"} if review else {"judgements"})
    problems = [
        "le verdict est calculé par du code, jamais donné par le relecteur" if name == "verdict"
        else f"champ inconnu : {name}" for name in sorted(set(given) - known)]
    if given.get("commit") != request["commit"]:
        problems.append(f"la revue rendue porte sur le commit {given.get('commit')!r}, la demande sur {request['commit']}")
    recorded_by = given.get("recorded_by")
    if not isinstance(recorded_by, str) or not recorded_by.strip() or "\n" in recorded_by:
        problems.append(f"session du relecteur absente ou mal formée : {recorded_by!r}")
    round_: dict[str, Any] = {"kind": request["kind"], "commit": request["commit"], "base": request["base"]}
    demoted: list[dict[str, str]] = []
    if review:
        number = len(record["rounds"]) + 1
        findings, demoted = given_findings(given, number, problems)
        answers = given.get("answers") if isinstance(given.get("answers"), dict) else {}
        questions = {question["id"]: question for question in request["questions"]}
        problems += [f"réponse à une question qui n'est pas posée : {name}" for name in sorted(set(answers) - set(questions))]
        kept: dict[str, dict[str, str]] = {}
        for question_id, question in questions.items():
            answer = answers.get(question_id)
            said = answer.get("answer") if isinstance(answer, dict) else None
            reason = " ".join(str(answer.get("reason") or "").split()) if isinstance(answer, dict) else ""
            if answer is None:
                problems.append(f"pas de réponse à la question {question_id}")
            elif said not in QUESTION_ANSWERS:
                problems.append(f"réponse hors de la liste fermée à {question_id} : {said!r} (attendu : {', '.join(QUESTION_ANSWERS)})")
            elif said == "non" and not reason:
                problems.append(f"réponse « non » sans raison à la question {question_id}")
            elif said == "non":
                kept[question_id] = {"answer": said, "reason": reason}
                # Spec §6: a « non » is a Blocking Finding.
                findings.append({
                    "id": f"F{number}.{len(findings) + 1}", "axis": AXIS_TESTS, "blocking": True,
                    "summary": f"{question['text']} — non : {reason}"[:MAX_FINDING_LINE], "question": question_id})
            else:
                kept[question_id] = {"answer": said}
        round_.update(findings=findings, answers=kept)
        refused = [finding["id"] for finding in findings if finding["blocking"]]
    else:
        reviewed = record["rounds"][-1]
        if isinstance(recorded_by, str) and recorded_by.strip() == reviewed["recorded_by"]:
            # Spec §6: a second reviewer session judges the answers.
            problems.append(
                f"le jugement est rendu par la session qui a fait la revue ({reviewed['recorded_by']}) : "
                "une seconde session relecteur juge les réponses")
        expected = blocking_ids(reviewed)
        judgements = given.get("judgements") if isinstance(given.get("judgements"), dict) else {}
        problems += [f"{name} n'est pas un Blocking Finding de la revue jugée" for name in sorted(set(judgements) - set(expected))]
        kept = {}
        for finding_id in expected:
            answer = judgements.get(finding_id)
            state = answer.get("state") if isinstance(answer, dict) else None
            reason = " ".join(str(answer.get("reason") or "").split()) if isinstance(answer, dict) else ""
            if answer is None:
                problems.append(f"pas de jugement pour le constat {finding_id}")
            elif state not in VERDICT_STATES:
                problems.append(f"état hors de la liste fermée pour {finding_id} : {state!r} (attendu : {', '.join(VERDICT_STATES)})")
            elif state == "unfavorable" and not reason:
                problems.append(f"jugement défavorable sans raison pour {finding_id}")
            else:
                kept[finding_id] = {"state": state, "reason": reason} if state == "unfavorable" else {"state": state}
        round_["judgements"] = kept
        refused = [finding_id for finding_id in expected if kept.get(finding_id, {}).get("state") == "unfavorable"]
    if problems:
        raise Refusal("revue de code hors contrat : " + " ; ".join(problems))
    verdict = "unfavorable" if refused else "favorable"
    at = now()
    round_.update(verdict=verdict, models=request["models"], recorded_by=recorded_by.strip(), at=at)
    record["rounds"].append(code_review_round(round_))
    del record["request"]
    values = {KEY_CODE_REVIEW: encode(record),
              VERDICT_PREFIX + "code_review": encode({"state": verdict, "commit": request["commit"], "at": at})}
    write_metadata(args.ticket, values)
    print(json.dumps({"ok": True, "convoy": args.convoy, "bead": args.ticket, "kind": request["kind"], "verdict": verdict,
                      "blocking": refused, "demoted": demoted, "findings": len(round_.get("findings", [])),
                      "written": values}, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def cmd_respond_code_review(args: argparse.Namespace) -> int:
    """Record the answer of the author to each Blocking Finding of the last
    review: « corrigé » with the commit of the correction, or « contesté »
    with a reason (Spec §6). The list is closed: every Blocking Finding, and
    nothing else. A second reviewer session judges it."""
    _, record = code_review_target(args)
    last = record["rounds"][-1] if record["rounds"] else None
    if last is None or last["kind"] != "review" or last["verdict"] != "unfavorable":
        raise Refusal(f"aucun Blocking Finding n'attend de réponse sur {args.ticket}")
    if "request" in record:
        raise Refusal(f"le jugement de ces réponses est demandé sur {args.ticket} : elles ne se réécrivent plus")
    given = json_argument(args.file, "réponses aux constats")
    responses = given.get("responses")
    problems = [f"champ inconnu : {name}" for name in sorted(set(given) - {"responses"})]
    if not isinstance(responses, dict):
        problems.append("responses mal formé : un objet constat → réponse est attendu")
        responses = {}
    expected = blocking_ids(last)
    problems += [f"{name} n'est pas un Blocking Finding de cette revue" for name in sorted(set(responses) - set(expected))]
    at = now()
    kept: dict[str, dict[str, str]] = {}
    for finding_id in expected:
        response = responses.get(finding_id)
        said = response.get("response") if isinstance(response, dict) else None
        if response is None:
            problems.append(f"pas de réponse au constat {finding_id}")
        elif said not in FINDING_RESPONSES:
            problems.append(f"réponse hors de la liste fermée pour {finding_id} : {said!r} (attendu : {', '.join(FINDING_RESPONSES)})")
        elif said == "fixed":
            commit = response.get("commit")
            if not isinstance(commit, str) or not COMMIT_RE.match(commit) or commit == last["commit"]:
                problems.append(
                    f"{finding_id} « corrigé » sans le commit de la correction (un SHA complet, autre que le commit revu) : {commit!r}")
            else:
                kept[finding_id] = {"response": said, "commit": commit, "at": at}
        else:
            reason = " ".join(str(response.get("reason") or "").split())[:MAX_FINDING_LINE]
            if not reason:
                problems.append(f"{finding_id} « contesté » sans raison")
            else:
                kept[finding_id] = {"response": said, "reason": reason, "at": at}
    if problems:
        raise Refusal("réponses hors contrat : " + " ; ".join(problems))
    last["responses"] = kept
    values = {KEY_CODE_REVIEW: encode(record)}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def evaluation_target(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """The ticket an evaluation write lands on, its metadata, and its
    Ticket Evaluation so far."""
    ticket = marked_ticket(args.convoy, args.ticket)
    metadata = metadata_of(ticket)
    if KEY_STOP in metadata:
        raise Refusal(f"ticket arrêté : aucune évaluation ne s'enregistre sur {args.ticket} tant que l'arrêt n'est pas levé")
    record = evaluation_record(metadata[KEY_EVALUATION]) if KEY_EVALUATION in metadata else {"rounds": []}
    return ticket, metadata, record


def finished_at(metadata: dict[str, Any], ticket_id: str, commit: str) -> None:
    """An evaluation is of the commit the author finished at."""
    finished = KEY_EXIT in metadata and stored_record(metadata[KEY_EXIT], ("exit", "at"))["exit"] == "finished"
    if not finished:
        raise Refusal(f"le ticket {ticket_id} n'est pas terminé : l'évaluation suit la sortie « terminé »")
    handoff = handoff_record(metadata[KEY_HANDOFF]) if KEY_HANDOFF in metadata else None
    if handoff is None or handoff["partial"] or handoff["commit"] != commit:
        raise Refusal(
            f"le Ticket Handoff de {ticket_id} n'est pas complet au commit {commit} : l'évaluation porte sur le commit "
            "où l'auteur a terminé")


def evidence_at(metadata: dict[str, Any], piece: Any, commit: str) -> str | None:
    """Why `piece` is not a piece of evidence of the ticket captured at
    `commit`, or None when it is one."""
    if not isinstance(piece, str) or not PIECE_RE.match(piece):
        return f"aucune pièce de preuve nommée ({piece!r})"
    raw = metadata.get(EVIDENCE_PREFIX + piece)
    if raw is None:
        return f"la pièce {piece} n'a pas d'empreinte sur le ticket : elle n'a pas été capturée (bin/evidence-capture)"
    fingerprint = stored_record(raw, ("digest", "commit", "at"))
    if fingerprint["commit"] != commit:
        return f"la pièce {piece} a été capturée au commit {fingerprint['commit']}, non au commit évalué {commit}"
    return None


def cmd_open_evaluation(args: argparse.Namespace) -> int:
    """Open the Ticket Evaluation of a ticket (T15, Spec §7) at the commit
    its author finished at, on the products code launched from a clean copy
    of that commit. The criteria and the demonstration line are read here,
    on the approved ticket: nobody hands them in. The same request again
    writes nothing; one at the same commit on other products keeps its
    launches."""
    ticket, metadata, record = evaluation_target(args)
    commit = valid_commit(args.commit, "commit de l'évaluation")
    kind = valid_kind(metadata.get(KEY_KIND))
    if kind == KIND_WITHOUT_EVALUATOR:
        raise Refusal(
            f"le ticket {args.ticket} est un {kind} : aucune session d'Evaluator, du code vérifie que le produit démarre "
            "(record-startup)")
    finished_at(metadata, args.ticket, commit)
    criteria = acceptance_criteria(ticket.get("description"))
    if not criteria:
        raise Refusal(f"le ticket {args.ticket} n'a aucun critère d'acceptation sous « ## Acceptance criteria » : rien à évaluer")
    line = valid_demonstration_line(metadata.get(KEY_DEMONSTRATION))
    given = json_argument(args.file, "demande d'évaluation")
    unknown = sorted(set(given) - {"roles", "environment"})
    if unknown:
        raise Refusal(f"champs inconnus dans la demande d'évaluation : {', '.join(unknown)}")
    roles = evaluation_roles(given.get("roles"))
    environment = evaluation_environment(given.get("environment"), launched=True)
    last = record["rounds"][-1] if record["rounds"] else None
    if last and last["commit"] == commit and last["verdict"] is not None:
        raise Refusal(f"le ticket {args.ticket} est déjà évalué au commit {commit} ({last['outcome']})")
    request = record.get("request")
    wanted = {"commit": commit, "criteria": criteria, "demonstration_line": line}
    if request and {name: request[name] for name in wanted} == wanted:
        if request["roles"] == roles and request["environment"] == environment:
            return done(args.convoy, args.ticket, {})
        # The same evaluation on products launched again: its launches stay counted.
        request.update(roles=roles, environment=environment)
    else:
        record["request"] = {**wanted, "roles": roles, "environment": environment, "launches": [], "at": now()}
    record["live"] = list(dict.fromkeys(
        [entry["state_file"] for entry in environment] + record.get("live", [])))
    values = {KEY_EVALUATION: encode(evaluation_record(encode(record)))}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def cmd_launch_evaluation(args: argparse.Namespace) -> int:
    """Record that an Evaluator session was sent the open evaluation: the
    first launch, then one relaunch when the first gave no result."""
    _, _, record = evaluation_target(args)
    request = record.get("request")
    if not request:
        raise Refusal(f"aucune évaluation n'est demandée sur {args.ticket} : rien à lancer")
    if not isinstance(args.bead, str) or not BEAD_ID_RE.match(args.bead):
        raise Refusal(f"bead d'évaluation absent ou mal formé : {args.bead!r}")
    if len(request["launches"]) >= EVALUATION_MAX_LAUNCHES:
        raise Refusal(
            f"une seule relance par évaluation : {args.ticket} en a déjà lancé {len(request['launches'])} sans résultat")
    request["launches"].append({"bead": args.bead, "at": now()})
    values = {KEY_EVALUATION: encode(record)}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def given_state(given: Any, what: str, text: str, metadata: dict[str, Any], commit: str, problems: list[str]) -> dict[str, Any]:
    """One state an Evaluator hands in, as it is stored; what is wrong with
    it goes to `problems`."""
    stored: dict[str, Any] = {"text": text, "state": None, "evidence": None}
    if not isinstance(given, dict):
        problems.append(f"{what} : aucun état rendu")
        return stored
    unknown = sorted(set(given) - {"number", "text", "state", "evidence", "reason", "cause"})
    if unknown:
        problems.append(f"{what} : champs inconnus : {', '.join(unknown)}")
    if given.get("text") != text:
        # Spec §7: the Evaluator neither waives nor rewords a criterion.
        problems.append(
            f"{what} reformulé : le texte rendu n'est pas celui du ticket approuvé ({given.get('text')!r} au lieu de {text!r})")
    state = given.get("state")
    if state not in EVALUATION_STATES:
        problems.append(f"{what} : état hors de la liste fermée : {state!r} (attendu : {', '.join(EVALUATION_STATES)})")
        return stored
    stored["state"] = state
    refusal = evidence_at(metadata, given.get("evidence"), commit)
    if refusal:
        problems.append(f"{what} : état sans Evidence Record valide : {refusal}")
    else:
        stored["evidence"] = given["evidence"]
    reason = " ".join(str(given.get("reason") or "").split())[:MAX_FINDING_LINE]
    if state != "observed":
        if not reason:
            problems.append(f"{what} : « {state} » sans raison")
        stored["reason"] = reason
    elif reason:
        problems.append(f"{what} : une raison ne se donne pas avec « observed »")
    if state == "unobservable":
        if given.get("cause") not in UNOBSERVABLE_CAUSES:
            problems.append(
                f"{what} : « unobservable » sans cause dans la liste fermée : {given.get('cause')!r} "
                f"(attendu : {', '.join(UNOBSERVABLE_CAUSES)})")
        stored["cause"] = given.get("cause")
    elif "cause" in given:
        problems.append(f"{what} : une cause ne se donne qu'avec « unobservable »")
    return stored


def cmd_record_evaluation(args: argparse.Namespace) -> int:
    """Record what an Evaluator session hands in for the open evaluation,
    and compute the verdict (T15, Spec §7): one state per approved criterion
    and one for the demonstration line, each with a captured piece of
    evidence. The verdict of the family `evaluation` is written in the same
    tracker write; an outage of the environment writes none."""
    ticket, metadata, record = evaluation_target(args)
    request = record.get("request")
    if not request:
        raise Refusal(f"aucune évaluation n'est demandée sur {args.ticket} : des états répondent à une demande ouverte")
    given = json_argument(args.file, "évaluation")
    problems = [
        "le verdict est calculé par du code, jamais donné par l'Evaluator" if name in ("verdict", "outcome")
        else f"champ inconnu : {name}"
        for name in sorted(set(given) - {"commit", "criteria", "demonstration_line", "recorded_by"})]
    if given.get("commit") != request["commit"]:
        problems.append(f"l'évaluation rendue porte sur le commit {given.get('commit')!r}, la demande sur {request['commit']}")
    recorded_by = given.get("recorded_by")
    if not isinstance(recorded_by, str) or not recorded_by.strip() or "\n" in recorded_by:
        problems.append(f"session de l'Evaluator absente ou mal formée : {recorded_by!r}")
    # Spec §9, condition 1: the criteria evaluated are those of the approved ticket.
    approved = acceptance_criteria(ticket.get("description"))
    if approved != request["criteria"] or metadata.get(KEY_DEMONSTRATION) != request["demonstration_line"]:
        problems.append(
            "les critères ou la ligne de démonstration du ticket ne sont plus ceux de la demande d'évaluation : "
            "ils sont gelés avec le graphe approuvé")
    handed = given.get("criteria")
    if not isinstance(handed, list):
        problems.append("criteria mal formé : une liste d'états, un par critère, est attendue")
        handed = []
    by_number: dict[Any, Any] = {}
    for item in handed:
        number = item.get("number") if isinstance(item, dict) else None
        if isinstance(number, bool) or not isinstance(number, int) or not 1 <= number <= len(request["criteria"]):
            problems.append(f"état rendu pour un critère que le ticket approuvé n'a pas : {number!r}")
        elif number in by_number:
            problems.append(f"critère {number} : deux états rendus")
        else:
            by_number[number] = item
    criteria = []
    for number, text in enumerate(request["criteria"], start=1):
        if number not in by_number:
            problems.append(f"critère {number} retiré : aucun état rendu pour « {text} »")
            continue
        criteria.append({"number": number, **given_state(
            by_number[number], f"critère {number}", text, metadata, request["commit"], problems)})
    line = given_state(given.get("demonstration_line"), "ligne de démonstration", request["demonstration_line"],
                       metadata, request["commit"], problems)
    if problems:
        raise Refusal("évaluation hors contrat : " + " ; ".join(problems))
    at = now()
    round_: dict[str, Any] = {
        "kind": "evaluation", "commit": request["commit"], "criteria": criteria, "demonstration_line": line,
        "roles": request["roles"],
        "environment": [{"dataset": entry["dataset"], "address": entry["address"]} for entry in request["environment"]],
        "recorded_by": recorded_by.strip(), "at": at}
    round_["outcome"] = evaluation_outcome(evaluation_items(round_))
    round_["verdict"] = verdict_of_outcome(round_["outcome"])
    record["rounds"].append(evaluation_round(round_))
    del record["request"]
    values = {KEY_EVALUATION: encode(record)}
    if round_["verdict"] is not None:
        values[VERDICT_PREFIX + "evaluation"] = encode({"state": round_["verdict"], "commit": request["commit"], "at": at})
    write_metadata(args.ticket, values)
    print(json.dumps({"ok": True, "convoy": args.convoy, "bead": args.ticket, "kind": "evaluation",
                      "outcome": round_["outcome"], "verdict": round_["verdict"], "state": evaluation_state(record),
                      "written": values}, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def cmd_record_startup(args: argparse.Namespace) -> int:
    """Record what code saw when it launched the product from a clean copy
    of `--commit` (T15, Spec §7). For a prefactoring it stands for the
    evaluation: no Evaluator session, the product started and its probe
    answered (`--piece`, the captured answer, and the launched products in
    `--file`). On any ticket, the product did not start (`--detail`):
    nothing can be observed on it. The verdict `evaluation` is written in
    the same write."""
    _, metadata, record = evaluation_target(args)
    commit = valid_commit(args.commit, "commit du contrôle de démarrage")
    kind = valid_kind(metadata.get(KEY_KIND))
    if kind != KIND_WITHOUT_EVALUATOR and args.piece is not None:
        raise Refusal(
            f"le ticket {args.ticket} est un {kind} : son évaluation est faite par une session d'Evaluator, "
            "un produit qui démarre ne vaut évaluation que pour un prefactoring")
    finished_at(metadata, args.ticket, commit)
    at = now()
    round_: dict[str, Any] = {"kind": "startup", "commit": commit, "at": at}
    if args.piece is not None:
        if args.detail is not None:
            raise Refusal("--piece et --detail s'excluent : le produit a démarré, ou non")
        refusal = evidence_at(metadata, args.piece, commit)
        if refusal:
            raise Refusal(f"contrôle de démarrage sans Evidence Record valide : {refusal}")
        given = json_argument(args.file, "environnement du contrôle de démarrage")
        round_.update(started=True, evidence=args.piece, outcome="favorable",
                      environment=evaluation_environment(given.get("environment"), launched=False))
    else:
        round_.update(started=False, detail=single_line(args.detail, "précision du démarrage manqué"),
                      outcome="return_to_author")
    round_["verdict"] = verdict_of_outcome(round_["outcome"])
    record["rounds"].append(evaluation_round(round_))
    # An evaluation that was open is over: there is no product to use.
    record.pop("request", None)
    values = {KEY_EVALUATION: encode(record),
              VERDICT_PREFIX + "evaluation": encode({"state": round_["verdict"], "commit": commit, "at": at})}
    write_metadata(args.ticket, values)
    print(json.dumps({"ok": True, "convoy": args.convoy, "bead": args.ticket, "kind": "startup",
                      "outcome": round_["outcome"], "verdict": round_["verdict"], "written": values},
                     indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def cmd_release_evaluation(args: argparse.Namespace) -> int:
    """Record that the launched products of an evaluation were stopped by
    code: `--state-file` (repeatable) names each launch record that is
    gone. A product an open evaluation still runs on is not released,
    unless the ticket is stopped (its evaluation does not go on) or the
    evaluation is withdrawn with it (`--withdraw`: the ticket is no longer
    to be evaluated at that commit, and nothing can be observed any more)."""
    ticket = marked_ticket(args.convoy, args.ticket)
    metadata = metadata_of(ticket)
    record = evaluation_record(metadata[KEY_EVALUATION]) if KEY_EVALUATION in metadata else {"rounds": []}
    live = record.get("live", [])
    if not args.state_file:
        raise Refusal("relevé de lancement absent : --state-file nomme chaque produit arrêté")
    unknown = [path for path in args.state_file if path not in live]
    if unknown:
        raise Refusal(f"produit lancé inconnu de l'évaluation de {args.ticket} : {', '.join(unknown)}")
    used = {entry["state_file"] for entry in (record.get("request") or {}).get("environment", [])}
    held = [path for path in args.state_file if path in used]
    if held and args.withdraw:
        del record["request"]
    elif held and KEY_STOP not in metadata:
        raise Refusal(f"une évaluation est ouverte sur ce produit lancé : il ne se libère pas ({', '.join(held)})")
    left = [path for path in live if path not in args.state_file]
    record.pop("live", None)
    if left:
        record["live"] = left
    values = {KEY_EVALUATION: encode(record)}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def cmd_stop_ticket(args: argparse.Namespace) -> int:
    ticket = marked_ticket(args.convoy, args.ticket)
    if KEY_STOP in metadata_of(ticket):
        raise Refusal(f"le ticket {args.ticket} est déjà arrêté")
    record = {"reason": one_of(args.reason, STOP_REASONS, "raison d'arrêt"),
              "detail": single_line(args.detail, "précision de l'arrêt"), "at": now()}
    values = {KEY_STOP: encode(record)}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def cmd_stop_raised(args: argparse.Namespace) -> int:
    """Record that the stop of a ticket reached the operator through the
    escalation door: the code that stopped it raises it once, whatever the
    number of passes. The same record again writes nothing."""
    ticket = marked_ticket(args.convoy, args.ticket)
    metadata = metadata_of(ticket)
    if KEY_STOP not in metadata:
        raise Refusal(f"le ticket {args.ticket} n'est pas arrêté : aucun arrêt à remonter")
    record = stop_record(metadata[KEY_STOP])
    if "raised" in record:
        return done(args.convoy, args.ticket, {})
    values = {KEY_STOP: encode({**record, "raised": now()})}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def cmd_set_handoff(args: argparse.Namespace) -> int:
    """Record the Ticket Handoff of a ticket, as bin/ticket-exit built it:
    the sections of the author, validated, and the records of the code."""
    ticket = marked_ticket(args.convoy, args.ticket)
    try:
        given = json.loads(Path(args.file or "").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise Refusal(f"Handoff illisible (--file {args.file!r}) : {exc}") from exc
    if not isinstance(given, dict) or "at" in given:
        raise Refusal("Handoff mal formé : un objet JSON sans champ « at » est attendu")
    evidence = {
        key[len(EVIDENCE_PREFIX):]: stored_record(raw, ("digest", "commit", "at"))
        for key, raw in metadata_of(ticket).items() if key.startswith(EVIDENCE_PREFIX)
    }
    record = handoff_record(encode({**given, "at": now()}), evidence)
    values = {KEY_HANDOFF: encode(record)}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def cmd_set_fidelity(args: argparse.Namespace) -> int:
    """Record the result of the mechanical fidelity check of a ticket, as
    bin/prototype-fidelity measured it at `--commit`: what it compared and
    every deviation. The verdict is computed here and written with it, in
    one tracker write; the full record must be a piece of the evidence store
    at that commit."""
    ticket = marked_ticket(args.convoy, args.ticket)
    given = json_argument(args.file, "résultat du contrôle de fidélité")
    unknown = sorted(set(given) - {"screens", "states", "deviations"})
    if unknown:
        raise Refusal(
            f"champs inattendus dans le résultat du contrôle de fidélité : {', '.join(unknown)} "
            "(le verdict est calculé ici, à partir des écarts, jamais fourni)")
    commit = valid_commit(args.commit)
    at = now()
    verdict = "unfavorable" if given.get("deviations") else "favorable"
    record = fidelity_record(encode({
        "commit": commit, "verdict": verdict, "piece": args.piece, "screens": given.get("screens"),
        "states": given.get("states"), "deviations": given.get("deviations"), "at": at,
    }), metadata_of(ticket))
    values = {KEY_FIDELITY: encode(record),
              VERDICT_PREFIX + "fidelity": encode({"state": verdict, "commit": commit, "at": at})}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def cmd_raise_planning_exception(args: argparse.Namespace) -> int:
    """Record the Planning Exception a ticket raises (bin/ticket-exit, before
    the request reaches the operator), with the anchors whose deviation from
    the Validated Prototype it asks to accept and the option of the request
    that accepts it; or the one the end-of-Spec gate raises (bin/spec-end,
    T23) for tracked elements of the Ticket Handoff left without a final
    state (`--item`, a deviation or a « non fait » of that Handoff). The
    answer is the operator's, through the escalation door: nothing here
    resolves one. The answer given to the previous one is kept with it; the
    same exception again writes nothing, another one replaces the one that
    was still open."""
    ticket = marked_ticket(args.convoy, args.ticket)
    metadata = metadata_of(ticket)
    anchors = list(args.anchor)
    for anchor in anchors:
        if not ANCHOR_RE.match(anchor):
            raise Refusal(f"nom d'ancre mal formé : {anchor!r}")
    if len(set(anchors)) != len(anchors):
        raise Refusal(f"ancre nommée deux fois : {anchors!r}")
    items = list(args.item)
    if len(set(items)) != len(items):
        raise Refusal(f"élément suivi nommé deux fois : {items!r}")
    if items:
        sections = handoff_record(metadata[KEY_HANDOFF])["sections"] if KEY_HANDOFF in metadata else {}
        for item in items:
            if not ITEM_RE.match(item):
                raise Refusal(f"élément suivi mal formé : {item!r} (attendu : deviations.N ou not_done.N)")
            section, number = item.split(".")
            content = sections.get(section)
            if not isinstance(content, list) or int(number) > len(content):
                raise Refusal(f"le Ticket Handoff de {args.ticket} ne porte pas l'élément {item}")
    entry = {
        "kind": one_of(args.kind, PLANNING_EXCEPTION_KINDS, "genre de Planning Exception"),
        "summary": single_line(args.summary, "résumé de la Planning Exception"),
        "anchors": anchors, "accept_option": args.accept_option,
        **({"items": items} if items else {}),
    }
    entries = planning_exceptions_record(metadata[KEY_PLANNING_EXCEPTIONS]) if KEY_PLANNING_EXCEPTIONS in metadata else []
    if entries and "resolution" not in entries[-1]:
        resolution = live_resolution(entries[-1], metadata)
        asked = {key: entries[-1][key] for key in ("kind", "summary", "anchors", "accept_option", "items")
                 if key in entries[-1]}
        if resolution:
            entries[-1]["resolution"] = resolution
        elif asked == entry:
            return done(args.convoy, args.ticket, {})
        else:
            entries.pop()
    prior = metadata.get(KEY_RESPONSE_AT)
    entries.append({**entry, "prior_response_at": prior if isinstance(prior, str) else None, "at": now()})
    values = {KEY_PLANNING_EXCEPTIONS: encode({"entries": planning_exceptions_record(encode({"entries": entries}))})}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def cmd_record_blocking_red(args: argparse.Namespace) -> int:
    """Record the red control the author of a ticket says blocks it
    technically (bin/ticket-exit, T40), before the `repair` that cites it
    goes through the patch door: a red control a repair restores is one the
    convoy carries a record of. The same control again writes nothing;
    another one replaces it."""
    convoy, tickets = load_convoy(args.convoy)
    require_marked(convoy)
    ticket = marked_ticket_among(tickets, args.convoy, args.ticket)
    control = single_line(args.control, "contrôle rouge")
    metadata = metadata_of(ticket)
    if KEY_BLOCKING_RED in metadata and blocking_red_record(metadata[KEY_BLOCKING_RED])["control"] == control:
        return done(args.convoy, args.ticket, {})
    values = {KEY_BLOCKING_RED: encode(blocking_red_record(encode({"control": control, "at": now()})))}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def cmd_clear_blocking_red(args: argparse.Namespace) -> int:
    """Withdraw that record: the patch door refused the repair that cites it."""
    convoy, tickets = load_convoy(args.convoy)
    require_marked(convoy)
    ticket = marked_ticket_among(tickets, args.convoy, args.ticket)
    if KEY_BLOCKING_RED not in metadata_of(ticket):
        return done(args.convoy, args.ticket, {})
    run_gc(["bd", "update", args.ticket, "--unset-metadata", KEY_BLOCKING_RED])
    return done(args.convoy, args.ticket, {KEY_BLOCKING_RED: None})


def cmd_set_item_repair(args: argparse.Namespace) -> int:
    """Name the repair code published for the tracked elements of a Ticket
    Handoff (bin/convoy-advance, T23), once the operator answered their
    Planning Exception by another option than the one that accepts them. The
    answer is frozen on the exception with the repair. Nothing here says an
    element is repaired: `show` reads it once the ticket-end gate has closed
    that repair."""
    convoy, tickets = load_convoy(args.convoy)
    require_marked(convoy)
    ticket = marked_ticket_among(tickets, args.convoy, args.ticket)
    metadata = metadata_of(ticket)
    entries = planning_exceptions_record(metadata[KEY_PLANNING_EXCEPTIONS]) if KEY_PLANNING_EXCEPTIONS in metadata else []
    last = entries[-1] if entries else {}
    if not last.get("items"):
        raise Refusal(
            f"la dernière Planning Exception de {args.ticket} ne nomme aucun élément suivi : aucun repair ne s'y rattache")
    resolution = last.get("resolution") or live_resolution(last, metadata)
    if not resolution:
        raise Refusal(
            f"la Planning Exception de {args.ticket} sur {', '.join(last['items'])} n'a pas de réponse de l'opérateur : "
            "un repair ne se publie qu'à sa demande")
    if resolution["option"] == last["accept_option"]:
        raise Refusal(
            f"l'opérateur a accepté {', '.join(last['items'])} de {args.ticket} (option {resolution['option']}) : "
            "aucun repair ne s'y rattache")
    repair = marked_ticket_among(tickets, args.convoy, args.repair)
    if metadata_of(repair).get(KEY_KIND) != "repair":
        raise Refusal(f"le ticket {args.repair} n'est pas un repair : seul un repair rétablit un élément suivi")
    if last.get("repair") == args.repair:
        return done(args.convoy, args.ticket, {})
    if "repair" in last:
        raise Refusal(
            f"les éléments {', '.join(last['items'])} de {args.ticket} ont déjà leur repair ({last['repair']}) : "
            "un seul repair par demande")
    entries[-1] = {**last, "resolution": resolution, "repair": args.repair}
    values = {KEY_PLANNING_EXCEPTIONS: encode({"entries": planning_exceptions_record(encode({"entries": entries}))})}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def blockers_of(ticket_id: str) -> list[str]:
    """The beads a ticket waits for (`blocks` edges), read on the ticket."""
    out = run_gc(["bd", "show", ticket_id, "--json"])
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        raise Refusal(f"gc bd show {ticket_id} a rendu un JSON illisible : {exc}") from exc
    bead = data[0] if isinstance(data, list) and data else data
    if not isinstance(bead, dict):
        raise Refusal(f"bead introuvable : {ticket_id}")
    return [
        dep.get("id") for dep in bead.get("dependencies") or []
        if isinstance(dep, dict) and dep.get("dependency_type") == "blocks"
    ]


def waiting_for(tickets: list[dict[str, Any]], ticket_id: str) -> list[str]:
    """The ticket, then every ticket of the convoy that waits for it,
    directly or through others, read on the `blocks` edges."""
    waits_for = {other["id"]: blockers_of(other["id"]) for other in tickets if other["id"] != ticket_id}
    found, frontier = [ticket_id], [ticket_id]
    while frontier:
        current = frontier.pop()
        for other, blockers in waits_for.items():
            if current in blockers and other not in found:
                found.append(other)
                frontier.append(other)
    return found


def cmd_park(args: argparse.Namespace) -> int:
    """Park a ticket and every ticket of the convoy that waits for it,
    directly or not (Spec §5: a Planning Exception or an operator request
    parks the ticket and its descendants; Spec §8: so does the third resume
    of a ticket). The other tickets are untouched."""
    ticket = marked_ticket(args.convoy, args.ticket)
    cause = one_of(args.cause, PARK_CAUSES, "cause de parcage")
    detail = single_line(args.detail, "précision du parcage")
    if ticket.get("status") == "closed":
        raise Refusal(f"le ticket {args.ticket} est fermé : un ticket fermé ne se parque pas")
    if KEY_PARK in metadata_of(ticket):
        raise Refusal(f"le ticket {args.ticket} est déjà parqué")
    if cause == PARK_EXHAUSTED and resumes_left(metadata_of(ticket)) > 0:
        raise Refusal(
            f"le ticket {args.ticket} n'a pas épuisé ses reprises ({resumes_max()}, toutes causes confondues) : "
            "il ne se parque pas pour cette cause")
    _, tickets = load_convoy(args.convoy)
    parked = waiting_for(tickets, args.ticket)
    by_id = {other["id"]: other for other in tickets}
    value = encode({"cause": cause, "origin": args.ticket, "detail": detail, "at": now()})
    written = []
    # The descendants first, the ticket last: an interrupted parking leaves
    # the ticket unparked, and the same command completes it.
    for bead_id in reversed(parked):
        other = by_id[bead_id]
        if other.get("status") == "closed" or (bead_id != args.ticket and KEY_PARK in metadata_of(other)):
            continue
        write_metadata(bead_id, {KEY_PARK: value})
        written.append(bead_id)
    print(json.dumps({"ok": True, "convoy": args.convoy, "bead": args.ticket, "cause": cause,
                      "parked": sorted(written)}, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def cmd_lift_park(args: argparse.Namespace) -> int:
    """Lift the parking a ticket caused (T20): on itself and on every ticket
    parked behind it, once the request `--request` was answered. A ticket
    that still waits for another parked one is parked behind that one
    instead. The lift is kept on the ticket, with the count of its resumes:
    an exhausted ticket takes its resumes again from there."""
    convoy, tickets = load_convoy(args.convoy)
    require_marked(convoy)
    ticket = marked_ticket_among(tickets, args.convoy, args.ticket)
    metadata = metadata_of(ticket)
    if KEY_PARK not in metadata:
        raise Refusal(f"le ticket {args.ticket} n'est pas parqué : rien à lever")
    park = park_record(metadata[KEY_PARK])
    if park["origin"] != args.ticket:
        raise Refusal(
            f"le ticket {args.ticket} est parqué par {park['origin']} : un parcage se lève sur le ticket qui l'a causé")
    if not isinstance(args.request, str) or not BEAD_ID_RE.match(args.request):
        raise Refusal(f"bead de la demande absent ou mal formé : {args.request!r} (--request)")
    option = option_letter(args.option) if args.option is not None else None
    lifts = park_lifts_record(metadata[KEY_PARK_LIFTS]) if KEY_PARK_LIFTS in metadata else []
    resumes = counter_value(metadata.get(COUNTER_PREFIX + "resumes"), "resumes")
    lifts.append({"cause": park["cause"], "detail": park["detail"], "parked_at": park["at"], "request": args.request,
                  "option": option, "resumes": resumes, "at": now()})
    # Each other ticket that still parks, with those that wait for it.
    still_parked: dict[str, str] = {}
    for other in tickets:
        other_park = metadata_of(other).get(KEY_PARK)
        if other["id"] == args.ticket or other_park is None or other.get("status") == "closed":
            continue
        if park_record(other_park)["origin"] == other["id"]:
            for behind in waiting_for(tickets, other["id"]):
                still_parked.setdefault(behind, other_park)
    lifted = []
    # Those behind first, the ticket last: an interrupted lift leaves the
    # ticket parked, and the same command completes it.
    for other in tickets:
        other_park = metadata_of(other).get(KEY_PARK)
        if other["id"] == args.ticket or other_park is None or park_record(other_park)["origin"] != args.ticket:
            continue
        if other["id"] in still_parked:
            write_metadata(other["id"], {KEY_PARK: still_parked[other["id"]]})
            continue
        run_gc(["bd", "update", other["id"], "--unset-metadata", KEY_PARK])
        lifted.append(other["id"])
    run_gc(["bd", "update", args.ticket, "--set-metadata", f"{KEY_PARK_LIFTS}={encode({'entries': lifts})}",
            "--unset-metadata", KEY_PARK])
    lifted.append(args.ticket)
    print(json.dumps({"ok": True, "convoy": args.convoy, "bead": args.ticket, "cause": park["cause"],
                      "lifted": sorted(lifted)}, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def cmd_open_resume(args: argparse.Namespace) -> int:
    """Count one resume of a ticket and record it (T20, Spec §8): code sends
    the ticket back to a fresh author session, on the same branch. The
    resume, the counter and the removal of the Ticket Exit it replaces go in
    one tracker write. The same fact (`--cause`, `--ref`) again writes
    nothing. Refused on a ticket that is stopped, parked, closed, or that
    has no resume left: that one is parked."""
    ticket = marked_ticket(args.convoy, args.ticket)
    metadata = metadata_of(ticket)
    cause = one_of(args.cause, RESUME_CAUSES, "cause de reprise")
    ref = single_line(args.ref, "repère de la reprise")
    if ticket.get("status") == "closed" or any(GATE_PREFIX + gate in metadata for gate in CLOSING_GATES):
        raise Refusal(f"le ticket {args.ticket} est fermé : il ne se reprend pas")
    if GATE_PREFIX + "dispatch" not in metadata:
        raise Refusal(f"le ticket {args.ticket} n'a pas été démarré par la porte de dispatch : rien à reprendre")
    if KEY_STOP in metadata:
        raise Refusal(f"ticket arrêté : {args.ticket} ne se reprend pas")
    if KEY_PARK in metadata:
        raise Refusal(f"ticket parqué : {args.ticket} ne se reprend pas tant que son parcage n'est pas levé")
    entries = resume_record(metadata[KEY_RESUME])["entries"] if KEY_RESUME in metadata else []
    if entries and (entries[-1]["cause"], entries[-1]["ref"]) == (cause, ref):
        return done(args.convoy, args.ticket, {})
    if resumes_left(metadata) == 0:
        raise Refusal(
            f"reprises épuisées : le ticket {args.ticket} a pris ses {resumes_max()} reprises, toutes causes confondues ; "
            "il se parque avec ses descendants")
    counters = {name: counter_value(metadata.get(COUNTER_PREFIX + name), name) for name in TICKET_COUNTERS}
    counters["resumes"] += 1
    check_ticket_counters(counters)
    session = session_record(metadata[KEY_SESSION])["name"] if KEY_SESSION in metadata else None
    replaced = stored_record(metadata[KEY_EXIT], ("exit", "at")) if KEY_EXIT in metadata else None
    entries.append({"cause": cause, "ref": ref, "session": session, "exit": replaced, "launches": [], "at": now()})
    values: dict[str, Any] = {KEY_RESUME: encode({"entries": entries}), COUNTER_PREFIX + "resumes": counters["resumes"]}
    update = ["bd", "update", args.ticket]
    for key, value in values.items():
        update += ["--set-metadata", f"{key}={value}"]
    if replaced is not None:
        # A resumed ticket is at work again: it exits again.
        update += ["--unset-metadata", KEY_EXIT]
    run_gc(update)
    return done(args.convoy, args.ticket, {**values, **({KEY_EXIT: None} if replaced is not None else {})})


def cmd_launch_resume(args: argparse.Namespace) -> int:
    """Record the fresh author session the last resume was sent to: one per
    resume."""
    metadata = metadata_of(marked_ticket(args.convoy, args.ticket))
    if KEY_RESUME not in metadata:
        raise Refusal(f"aucune reprise n'est ouverte sur {args.ticket} : rien à lancer")
    if KEY_STOP in metadata or KEY_PARK in metadata:
        raise Refusal(f"ticket arrêté ou parqué : aucune session de reprise ne se lance sur {args.ticket}")
    record = resume_record(metadata[KEY_RESUME])
    if not isinstance(args.bead, str) or not BEAD_ID_RE.match(args.bead):
        raise Refusal(f"bead de la reprise absent ou mal formé : {args.bead!r}")
    last = record["entries"][-1]
    if len(last["launches"]) >= RESUME_MAX_LAUNCHES:
        raise Refusal(
            f"une seule session par reprise : celle de {args.ticket} est déjà lancée ({last['launches'][0]['bead']})")
    last["launches"].append({"bead": args.bead, "at": now()})
    values = {KEY_RESUME: encode(record)}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def cmd_set_integration(args: argparse.Namespace) -> int:
    """Record the integration branch of the convoy's Spec, once: the branch
    bin/spec-integration opened, the protected branch and the commit it left
    from. The same record again writes nothing; another one is refused."""
    convoy, _ = load_convoy(args.convoy)
    require_marked(convoy)
    given = {
        "branch": valid_branch(args.branch, "branche d'intégration"),
        "protected": valid_branch(args.protected, "branche protégée"),
        "base": valid_commit(args.base, "commit de départ de la branche d'intégration"),
    }
    stored = metadata_of(convoy).get(KEY_INTEGRATION)
    if stored is not None:
        known = integration_record(stored)
        if {name: known[name] for name in given} != given:
            raise Refusal(
                f"le convoi {args.convoy} porte déjà sa branche d'intégration ({known['branch']}, partie de "
                f"{known['base']} sur {known['protected']}) : elle ne se réécrit pas")
        return done(args.convoy, args.convoy, {})
    values = {KEY_INTEGRATION: encode({**given, "at": now()})}
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


def cmd_set_merge(args: argparse.Namespace) -> int:
    """Record what bin/spec-integration did of a ticket."""
    convoy, _ = load_convoy(args.convoy)
    require_marked(convoy)
    ticket = marked_ticket(args.convoy, args.ticket)
    if KEY_INTEGRATION not in metadata_of(convoy):
        raise Refusal(f"le convoi {args.convoy} n'a pas de branche d'intégration enregistrée : rien ne s'y fusionne")
    if ticket.get("status") == "closed":
        raise Refusal(f"le ticket {args.ticket} est fermé : rien ne s'en fusionne plus")
    record: dict[str, Any] = {
        "outcome": args.outcome, "ticket_commit": args.ticket_commit, "integration": args.integration, "at": now()}
    if args.commit is not None:
        record["commit"] = args.commit
    values = {KEY_MERGE: encode(merge_record(encode(record)))}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def cmd_invalidate_verdicts(args: argparse.Namespace) -> int:
    """Spec §8, « commit après verdict »: write on the named verdicts that
    the tip `--tip`, added after them, made them invalid, and count one
    resume for it, in one tracker write. A verdict already invalidated is
    left as it is and counts nothing more. Verdicts given at the commit of
    the correction round count nothing either: the commit that outdates
    them is that round, which `open-correction` counted among the resumes.
    Nor do verdicts given at the commit the merge returned, once code has
    resumed the ticket for that return (T20): `open-resume` counted it."""
    ticket = marked_ticket(args.convoy, args.ticket)
    metadata = metadata_of(ticket)
    tip = valid_commit(args.tip, "pointe de la branche du ticket")
    corrected = correction_record(metadata[KEY_CORRECTION])["commit"] if KEY_CORRECTION in metadata else None
    returned = None
    if KEY_MERGE in metadata and KEY_RESUME in metadata:
        merge = merge_record(metadata[KEY_MERGE])
        if merge["outcome"] != "merged" and any(
                entry["cause"] == "returned" and entry["at"] >= merge["at"]
                for entry in resume_record(metadata[KEY_RESUME])["entries"]):
            returned = merge["ticket_commit"]
    judged: set[str] = set()
    if not args.kind:
        raise Refusal("genre de verdict absent : --kind nomme chaque verdict à invalider")
    values: dict[str, Any] = {}
    for kind in dict.fromkeys(args.kind):
        one_of(kind, VERDICT_KINDS, "genre de verdict")
        key = VERDICT_PREFIX + kind
        if key not in metadata:
            raise Refusal(f"le ticket {args.ticket} ne porte pas de verdict {kind} : rien à invalider")
        record = verdict_record(metadata[key])
        if record["commit"] == tip:
            raise Refusal(f"le verdict {kind} porte sur la pointe {tip} : aucun commit ne lui a été ajouté")
        if "invalidated" not in record:
            values[key] = encode({**record, "invalidated": {"tip": tip, "at": now()}})
            judged.add(record["commit"])
    invalidated = [key[len(VERDICT_PREFIX):] for key in values]
    if values:
        if judged != {corrected} and judged != {returned}:
            # It counts as a resume (K), not as the correction round.
            resumes = counter_value(metadata.get(COUNTER_PREFIX + "resumes"), "resumes")
            values[COUNTER_PREFIX + "resumes"] = resumes + 1
        write_metadata(args.ticket, values)
    print(json.dumps({"ok": True, "convoy": args.convoy, "bead": args.ticket, "invalidated": invalidated,
                      "written": values}, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def cmd_open_correction(args: argparse.Namespace) -> int:
    """Open the correction round of a ticket (T17, Spec §8) at the commit
    its code review and its Ticket Evaluation both answered at: what each of
    them refused goes to one fresh author session. There is one round per
    ticket, and it counts among the resumes: the round and the two counters
    go in one tracker write. The same round again writes nothing."""
    metadata = metadata_of(marked_ticket(args.convoy, args.ticket))
    commit = valid_commit(args.commit, "commit du tour de correction")
    if KEY_STOP in metadata:
        raise Refusal(f"ticket arrêté : aucun tour de correction ne s'ouvre sur {args.ticket}")
    if KEY_PARK in metadata:
        raise Refusal(f"ticket parqué : aucun tour de correction ne s'ouvre sur {args.ticket}")
    counters = {name: counter_value(metadata.get(COUNTER_PREFIX + name), name) for name in TICKET_COUNTERS}
    if KEY_CORRECTION in metadata:
        if correction_record(metadata[KEY_CORRECTION])["commit"] == commit:
            return done(args.convoy, args.ticket, {})
    if KEY_CORRECTION in metadata or counters["correction_rounds"] >= CORRECTION_MAX_ROUNDS:
        raise Refusal(
            f"le ticket {args.ticket} a déjà pris son tour de correction : un seul tour de correction par ticket, "
            "revue de code et Ticket Evaluation confondues")
    finished_at(metadata, args.ticket, commit)
    # One session receives every finding: both have answered at that commit.
    review = code_review_record(metadata[KEY_CODE_REVIEW]) if KEY_CODE_REVIEW in metadata else {"rounds": []}
    reviewed = review["rounds"][-1] if review["rounds"] else None
    if "request" in review or reviewed is None or reviewed["commit"] != commit:
        raise Refusal(
            f"la revue de code de {args.ticket} n'a pas rendu son verdict au commit {commit} : une seule session "
            "d'auteur reçoit tous les constats, ceux de la revue compris")
    evaluation = evaluation_record(metadata[KEY_EVALUATION]) if KEY_EVALUATION in metadata else {"rounds": []}
    evaluated = evaluation["rounds"][-1] if evaluation["rounds"] else None
    if "request" in evaluation or evaluated is None or evaluated["commit"] != commit \
            or evaluated["outcome"] not in ("favorable", "return_to_author"):
        raise Refusal(
            f"la Ticket Evaluation de {args.ticket} n'a pas rendu ses états au commit {commit} : une seule session "
            "d'auteur reçoit tous les constats, ceux de l'évaluation compris")
    findings: list[str] = []
    if reviewed["verdict"] == "unfavorable":
        if reviewed["kind"] != "review":
            raise Refusal(
                f"les réponses aux Blocking Findings de {args.ticket} sont déjà jugées défavorablement : "
                "il n'y a plus de tour de correction à ouvrir")
        findings = blocking_ids(reviewed)
    not_observed = evaluation_state(evaluation)["not_observed"] if evaluated["outcome"] == "return_to_author" else []
    if not findings and not not_observed:
        raise Refusal(f"rien à corriger sur {args.ticket} au commit {commit} : ni Blocking Finding, ni état non observé")
    counters = {name: value + 1 for name, value in counters.items()}
    check_ticket_counters(counters)
    record = {"commit": commit, "blocking_findings": findings, "not_observed": not_observed, "launches": [], "at": now()}
    values: dict[str, Any] = {KEY_CORRECTION: encode(record),
                              **{COUNTER_PREFIX + name: value for name, value in counters.items()}}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def cmd_launch_correction(args: argparse.Namespace) -> int:
    """Record the author session the correction round was sent to: one
    fresh session receives every finding, and there is no second one."""
    metadata = metadata_of(marked_ticket(args.convoy, args.ticket))
    if KEY_CORRECTION not in metadata:
        raise Refusal(f"aucun tour de correction n'est ouvert sur {args.ticket} : rien à lancer")
    if KEY_STOP in metadata:
        raise Refusal(f"ticket arrêté : aucune session de correction ne se lance sur {args.ticket}")
    record = correction_record(metadata[KEY_CORRECTION])
    if not isinstance(args.bead, str) or not BEAD_ID_RE.match(args.bead):
        raise Refusal(f"bead du tour de correction absent ou mal formé : {args.bead!r}")
    if len(record["launches"]) >= CORRECTION_MAX_LAUNCHES:
        raise Refusal(
            f"une seule session de correction par ticket : {args.ticket} a déjà la sienne ({record['launches'][0]['bead']})")
    record["launches"].append({"bead": args.bead, "at": now()})
    values = {KEY_CORRECTION: encode(record)}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def cmd_override_finding(args: argparse.Namespace) -> int:
    """Record that the operator overrides a Blocking Finding of the code
    review of a stopped ticket, with their words (T17, Spec §8). Only a
    Blocking Finding left without a favorable verdict can be overridden: a
    criterion that was not observed never is. That `--approver` is the
    declared human approver of the project is the refusal of the caller,
    bin/correction-round, which reads the project."""
    metadata = metadata_of(marked_ticket(args.convoy, args.ticket))
    finding = args.finding
    review = code_review_record(metadata[KEY_CODE_REVIEW]) if KEY_CODE_REVIEW in metadata else {"rounds": []}
    unsettled = code_review_state(review)["unsettled"]
    if not isinstance(finding, str) or not FINDING_ID_RE.match(finding):
        raise Refusal(
            f"{finding!r} n'est pas un Blocking Finding de la revue de code : seul un Blocking Finding de revue reçoit "
            "une dérogation ; un critère non observé ne se dispense jamais, il passe par une Planning Exception "
            "(bin/planning-exception)")
    if KEY_STOP not in metadata:
        raise Refusal(f"le ticket {args.ticket} n'est pas arrêté : une dérogation ne se donne que sur un ticket arrêté")
    if finding not in unsettled:
        raise Refusal(
            f"{finding} n'est pas un Blocking Finding resté sans verdict favorable sur {args.ticket} "
            f"(restants : {', '.join(unsettled) or 'aucun'})")
    if not isinstance(args.approver, str) or not args.approver.strip() or "\n" in args.approver:
        raise Refusal(f"approbateur de la dérogation absent ou mal formé : {args.approver!r}")
    if not isinstance(args.words, str) or not args.words.strip():
        raise Refusal("dérogation sans mots : les mots de l'approbateur sont enregistrés avec elle, non vides")
    approver, words = args.approver.strip(), args.words.strip()
    entries = overrides_record(metadata[KEY_OVERRIDES]) if KEY_OVERRIDES in metadata else []
    known = next((entry for entry in entries if entry["finding"] == finding), None)
    if known:
        if (known["approver"], known["words"]) == (approver, words):
            return done(args.convoy, args.ticket, {})
        raise Refusal(f"le constat {finding} porte déjà une dérogation de {known['approver']} : elle ne se réécrit pas")
    entries.append({"finding": finding, "approver": approver, "words": words, "commit": review["rounds"][-1]["commit"],
                    "at": now()})
    values = {KEY_OVERRIDES: encode({"entries": entries})}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def convoy_with_a_mark(convoy_id: str) -> dict[str, Any]:
    """An incident is recorded on any convoy that carries a mark, an unknown
    one included: an unknown mark is itself an "état sans règle" to report."""
    convoy, _ = load_convoy(convoy_id)
    if KEY_MARK not in metadata_of(convoy):
        raise NotNewFlow(convoy_id)
    return convoy


def cmd_record_incident(args: argparse.Namespace) -> int:
    convoy_with_a_mark(args.convoy)
    record: dict[str, Any] = {"bead": args.bead, "at": now()}
    if args.signature is not None:
        record["signature"] = args.signature
    values = {KEY_INCIDENT: encode(incident_record(encode(record)))}
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


def cmd_clear_incident(args: argparse.Namespace) -> int:
    convoy_with_a_mark(args.convoy)
    run_gc(["bd", "update", args.convoy, "--unset-metadata", KEY_INCIDENT])
    return done(args.convoy, args.convoy, {KEY_INCIDENT: None})


def cmd_record_integration_red(args: argparse.Namespace) -> int:
    """Record that the integration branch of the convoy is red (Spec §8):
    the control, quoted, and where it was red. The same red again -- same
    control, same commit -- writes nothing, so a red seen by several passes
    stays one red. A branch found red elsewhere while it is red (its tips
    moved) updates the record and keeps its repair: one repair per red. A
    branch found red once that repair is closed has no repair any more."""
    convoy, tickets = load_convoy(args.convoy)
    require_marked(convoy)
    metadata = metadata_of(convoy)
    if KEY_INTEGRATION not in metadata:
        raise Refusal(f"le convoi {args.convoy} n'a pas de branche d'intégration enregistrée : elle ne peut pas être rouge")
    record: dict[str, Any] = {
        "control": single_line(args.control, "contrôle rouge"),
        "commit": valid_commit(args.commit, "commit du contrôle rouge"),
        "integration": valid_commit(args.integration, "pointe de la branche d'intégration"),
        "protected": valid_commit(args.protected, "pointe de la branche protégée"),
    }
    if args.detail is not None:
        record["detail"] = single_line(args.detail, "détail du contrôle rouge")
    if args.check is not None:
        record["check"] = one_of(args.check, RED_CHECKS, "contrôle rouge (--check)")
    if KEY_INTEGRATION_RED in metadata:
        known = integration_red_record(metadata[KEY_INTEGRATION_RED])
        repair = next((ticket for ticket in tickets if ticket.get("id") == known.get("repair")), None)
        repaired = repair is not None and repair.get("status") == "closed"
        if (known["control"], known["commit"]) == (record["control"], record["commit"]) and not repaired:
            return done(args.convoy, args.convoy, {})
        if "repair" in known and not repaired:
            record["repair"] = known["repair"]
    at = now()
    values: dict[str, Any] = {KEY_INTEGRATION_RED: encode(integration_red_record(encode({**record, "at": at})))}
    if args.end_round:
        # A mechanical red of the end of the Spec counts one round (Spec §9),
        # in the write that records it: counted once, like the red -- or,
        # the rounds consumed, it stops them (T26).
        values.update(end_refusal_values(metadata, record["commit"], record.get("check", RED_CHECKS[0]), at,
                                         record["control"], once_per_tip=False))
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


def cmd_record_spec_end(args: argparse.Namespace) -> int:
    """The end-of-Spec gate records its three verdicts (T23, Spec §9): one
    commit of the integration branch for the three, and the tip of the
    protected branch that commit holds. The verdicts are computed by
    bin/spec-end; a list that is not the three conditions, all passing, is
    refused, as is a convoy with a ticket left open or closed outside its
    gate, or whose integration branch is red. One commit more outdates the
    record: nothing rewrites it but a fresh run of the gate."""
    convoy, tickets = load_convoy(args.convoy)
    require_marked(convoy)
    metadata = metadata_of(convoy)
    if KEY_INTEGRATION not in metadata:
        raise Refusal(f"le convoi {args.convoy} n'a pas de branche d'intégration : aucun commit auquel lier les verdicts")
    if KEY_INTEGRATION_RED in metadata:
        raise Refusal(f"la branche d'intégration du convoi {args.convoy} est rouge : aucun verdict de fin de Spec ne s'y enregistre")
    left = [str(ticket.get("id")) for ticket in tickets
            if ticket.get("status") != "closed" or not any(GATE_PREFIX + gate in metadata_of(ticket) for gate in CLOSING_GATES)]
    if left or not tickets:
        raise Refusal(
            f"le convoi {args.convoy} a des tickets ouverts ou fermés hors porte ({', '.join(left) or 'aucun ticket'}) : "
            "la porte de fin de Spec se déclenche quand tous sont fermés")
    given = json_argument(args.file, "relevé de la porte de fin de Spec")
    unknown = sorted(set(given) - {"version", "conditions", "records"})
    if unknown:
        raise Refusal(f"champs inconnus dans le relevé de la porte : {', '.join(unknown)}")
    if given.get("version") != SPEC_END_VERSION:
        raise Refusal(f"version de la liste de conditions inconnue : {given.get('version')!r} (attendu : {SPEC_END_VERSION})")
    record = {**given, "commit": args.commit, "protected": args.protected, "at": now()}
    values: dict[str, Any] = {KEY_SPEC_END: encode(spec_end_record(encode(record)))}
    if KEY_DELIVERED in metadata and (
            stored_or_none(metadata[KEY_DELIVERED], delivered_record) or {}).get("commit") != record["commit"]:
        # One commit more outdates every verdict of the end: the Outcome is
        # no longer Delivered at the commit the gate renders them on (T26).
        values[KEY_DELIVERED] = None
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


def stored_or_none(raw: Any, reader: Any) -> dict[str, Any] | None:
    try:
        return reader(raw)
    except Refusal:
        return None


def cmd_end_stop_raised(args: argparse.Namespace) -> int:
    """Record that the « non conforme » request of a convoy whose rounds of
    the end are stopped reached the operator (T26, Spec §8, §11): the bead
    the escalation door wrote it on, and the Evidence Pack it carries --
    the one recorded on the convoy, generated since the stop, whose header
    says « non conforme ». Once: the same request again writes nothing."""
    convoy, _ = load_convoy(args.convoy)
    require_marked(convoy)
    metadata = metadata_of(convoy)
    if not isinstance(args.bead, str) or not BEAD_ID_RE.match(args.bead):
        raise Refusal(f"bead de la demande « non conforme » absent ou mal formé : {args.bead!r}")
    if KEY_END_STOP not in metadata:
        raise Refusal(f"les tours de fin du convoi {args.convoy} ne sont pas arrêtés : aucune demande « non conforme » à noter")
    stop = end_stop_record(metadata[KEY_END_STOP])
    if "request" in stop:
        if stop["request"]["bead"] == args.bead:
            return done(args.convoy, args.convoy, {})
        raise Refusal(f"la demande « non conforme » du convoi {args.convoy} est déjà remontée ({stop['request']['bead']})")
    pack = evidence_pack_record(metadata[KEY_EVIDENCE_PACK]) if KEY_EVIDENCE_PACK in metadata else None
    if pack is None or pack["at"] < stop["at"]:
        raise Refusal(
            f"aucun Evidence Pack n'est généré pour le convoi {args.convoy} depuis l'arrêt de ses tours de fin : la demande "
            "« non conforme » porte le lien de ce dossier")
    if pack["conforming"]:
        raise Refusal(
            f"l'Evidence Pack du convoi {args.convoy} est conforme : la demande « non conforme » porte un dossier dont "
            "l'en-tête dit « non conforme »")
    stop["request"] = {"bead": args.bead, "commit": pack["commit"], "digest": pack["digest"],
                       "page": f"{pack['path'].rstrip('/')}/{PACK_PAGE}", "at": now()}
    values = {KEY_END_STOP: encode(end_stop_record(encode(stop)))}
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


def cmd_record_delivered(args: argparse.Namespace) -> int:
    """The end-of-Spec gate records that the Outcome of the convoy is
    Delivered (T26, Spec §9): every condition of its list met on one commit,
    Evidence Pack included. bin/spec-end decides it; what is refused here is
    a record the tracker contradicts -- a ticket left open, a red
    integration branch, stopped rounds, or, at that commit, mechanical
    verdicts, an Outcome Evaluation, findings « hors ticket », an end
    review or an Evidence Pack that is not the green one. The same record
    again writes nothing."""
    convoy, tickets = load_convoy(args.convoy)
    require_marked(convoy)
    metadata = metadata_of(convoy)
    commit = valid_commit(args.commit, "commit du Delivered Outcome")
    digest = valid_digest(args.pack_digest)
    reasons = []
    left = [str(ticket.get("id")) for ticket in tickets
            if ticket.get("status") != "closed" or not any(GATE_PREFIX + gate in metadata_of(ticket) for gate in CLOSING_GATES)]
    if left or not tickets:
        reasons.append(f"tickets ouverts ou fermés hors porte ({', '.join(left) or 'aucun ticket'})")
    if KEY_INTEGRATION_RED in metadata:
        reasons.append("branche d'intégration rouge")
    if KEY_END_STOP in metadata:
        reasons.append("tours de réparation de fin arrêtés (demande « non conforme »)")
    gate = stored_or_none(metadata.get(KEY_SPEC_END), spec_end_record)
    if gate is None or gate["version"] != SPEC_END_VERSION or gate["commit"] != commit:
        reasons.append(f"les trois verdicts mécaniques ({SPEC_END_VERSION}) ne sont pas enregistrés à ce commit")
    evaluation = stored_or_none(metadata.get(KEY_OUTCOME_EVALUATION), outcome_evaluation_record)
    last = evaluation["rounds"][-1] if evaluation and evaluation["rounds"] else None
    if last is None or "request" in evaluation or last["commit"] != commit or last["verdict"] != "favorable":
        reasons.append("l'Outcome Evaluation n'est pas favorable à ce commit")
    open_findings = unclassified_findings(tickets) + findings_to_repair(tickets)
    if open_findings:
        reasons.append(f"constat(s) hors ticket sans état final ({', '.join(open_findings)})")
    review = stored_or_none(metadata.get(KEY_END_REVIEW), end_review_record)
    state = end_review_state(review) if review else None
    if state is None or "request" in review or state["commit"] != commit or state["outcome"] != "favorable":
        reasons.append("la revue de code de fin n'est pas favorable à ce commit")
    pack = stored_or_none(metadata.get(KEY_EVIDENCE_PACK), evidence_pack_record)
    if pack is None or pack["commit"] != commit or pack["digest"] != digest or not pack["conforming"] or pack["inadmissible"]:
        reasons.append("l'Evidence Pack enregistré n'est pas le dossier conforme et complet de ce commit")
    reasons += owner_findings_open(metadata, tickets)
    if reasons:
        raise Refusal(
            f"le convoi {args.convoy} n'est pas Delivered au commit {commit[:12]} : " + " ; ".join(reasons)
            + " ; un Delivered Outcome a chaque condition de fin de Spec verte, dossier compris")
    record = {"commit": commit, "protected": gate["protected"], "pack": digest, "version": SPEC_END_VERSION, "at": now()}
    known = stored_or_none(metadata.get(KEY_DELIVERED), delivered_record)
    if known and {**known, "at": record["at"]} == record:
        return done(args.convoy, args.convoy, {})
    values = {KEY_DELIVERED: encode(delivered_record(encode(record)))}
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


def judged_dossier(convoy_id: str, metadata: dict[str, Any]) -> dict[str, Any] | None:
    """The dossier Benjamin judges (T28, Spec §11): the Evidence Pack of
    the Delivered Outcome, or the one the « non conforme » request of
    stopped rounds carries. None when the convoy has neither."""
    delivered = stored_or_none(metadata.get(KEY_DELIVERED), delivered_record)
    if delivered is not None:
        return {"commit": delivered["commit"], "pack": delivered["pack"]}
    stop = stored_or_none(metadata.get(KEY_END_STOP), end_stop_record)
    if stop is not None and "request" in stop:
        return {"commit": stop["request"]["commit"], "pack": stop["request"]["digest"]}
    return None


def acceptance_of(metadata: dict[str, Any], dossier: dict[str, Any]) -> dict[str, Any]:
    """The acceptance record of that dossier: the one written on it, or a
    new one -- what was noted on another commit went with that commit."""
    known = acceptance_record(metadata[KEY_ACCEPTANCE]) if KEY_ACCEPTANCE in metadata else None
    if known is not None and known["commit"] == dossier["commit"]:
        return known
    return {"commit": dossier["commit"], "pack": dossier["pack"], "at": now()}


def cmd_acceptance_requested(args: argparse.Namespace) -> int:
    """Record that the Acceptance Request of a Delivered Outcome reached
    the operator (T28, Spec §11): the bead the escalation door wrote it on
    and the page of the Evidence Pack it links. One request per Delivered
    Outcome: the same one again writes nothing, another bead is refused."""
    convoy, _ = load_convoy(args.convoy)
    require_marked(convoy)
    metadata = metadata_of(convoy)
    if not isinstance(args.bead, str) or not BEAD_ID_RE.match(args.bead):
        raise Refusal(f"bead de l'Acceptance Request absent ou mal formé : {args.bead!r}")
    delivered = stored_or_none(metadata.get(KEY_DELIVERED), delivered_record)
    if delivered is None:
        raise Refusal(f"le convoi {args.convoy} n'est pas Delivered : aucune Acceptance Request à noter")
    pack = stored_or_none(metadata.get(KEY_EVIDENCE_PACK), evidence_pack_record)
    if pack is None or pack["commit"] != delivered["commit"] or pack["digest"] != delivered["pack"]:
        raise Refusal(
            f"l'Evidence Pack enregistré sur le convoi {args.convoy} n'est pas celui de son Delivered Outcome : "
            "l'Acceptance Request porte le lien de ce dossier")
    record = acceptance_of(metadata, {"commit": delivered["commit"], "pack": delivered["pack"]})
    if "request" in record:
        if record["request"]["bead"] == args.bead:
            return done(args.convoy, args.convoy, {})
        raise Refusal(f"l'Acceptance Request du convoi {args.convoy} est déjà remontée ({record['request']['bead']})")
    record["request"] = {"bead": args.bead, "page": f"{pack['path'].rstrip('/')}/{PACK_PAGE}", "at": now()}
    values = {KEY_ACCEPTANCE: encode(acceptance_record(encode(record)))}
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


def cmd_acceptance_launch_failed(args: argparse.Namespace) -> int:
    """Record the outage of an Acceptance Session (T28, Spec §11): the
    product did not start at the commit of the dossier Benjamin was to
    judge. An outage is no judgment: nothing else of the convoy changes,
    and code publishes one `repair` for it. The same outage again writes
    nothing."""
    convoy, _ = load_convoy(args.convoy)
    require_marked(convoy)
    metadata = metadata_of(convoy)
    commit = valid_commit(args.commit, "commit du dossier")
    detail = single_line(args.detail, "panne de l'Acceptance Session")
    dossier = judged_dossier(args.convoy, metadata)
    if dossier is None or dossier["commit"] != commit:
        raise Refusal(
            f"le commit {commit[:12]} n'est pas celui du dossier que Benjamin juge sur le convoi {args.convoy} : "
            "une panne d'Acceptance Session se note au commit de ce dossier")
    record = acceptance_of(metadata, dossier)
    if "panne" in record:
        return done(args.convoy, args.convoy, {})
    record["panne"] = {"detail": detail, "at": now()}
    values = {KEY_ACCEPTANCE: encode(acceptance_record(encode(record)))}
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


def cmd_set_acceptance_repair(args: argparse.Namespace) -> int:
    """Name the repair ticket code published for the outage of an
    Acceptance Session: a tracked ticket of the convoy, of kind `repair`.
    One repair per outage."""
    convoy, tickets = load_convoy(args.convoy)
    require_marked(convoy)
    metadata = metadata_of(convoy)
    record = acceptance_record(metadata[KEY_ACCEPTANCE]) if KEY_ACCEPTANCE in metadata else None
    if record is None or "panne" not in record:
        raise Refusal(f"aucune panne d'Acceptance Session n'est notée sur le convoi {args.convoy} : aucun repair ne s'y rattache")
    ticket = marked_ticket_among(tickets, args.convoy, args.ticket)
    if metadata_of(ticket).get(KEY_KIND) != "repair":
        raise Refusal(f"le ticket {args.ticket} n'est pas un repair : seul un repair rétablit un produit qui ne démarre pas")
    if record["panne"].get("ticket") == args.ticket:
        return done(args.convoy, args.convoy, {})
    if "ticket" in record["panne"]:
        raise Refusal(
            f"la panne de l'Acceptance Session a déjà son repair ({record['panne']['ticket']}) : un seul repair par panne")
    record["panne"]["ticket"] = args.ticket
    values = {KEY_ACCEPTANCE: encode(acceptance_record(encode(record)))}
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


# --- Benjamin's judgement: verdicts on the propositions, answers, Owner Findings (T29) ---


def owner_words(value: Any, what: str) -> str:
    """The operator's own words, kept as given."""
    if not isinstance(value, str) or not value.strip():
        raise Refusal(f"{what} sans les mots de l'approbateur (--words), non vides")
    return value.strip()


def owner_finding_record(value: Any) -> dict[str, Any]:
    """One Owner Finding of an answer « constats rendus » and the route code
    gave it (Spec §11)."""
    if not isinstance(value, dict) or not {"text", "route"} <= set(value) \
            or not set(value) <= {"text", "route", "cites", "draft", "ticket", "proposal", "proposition"}:
        raise Refusal(f"Owner Finding mal formé : {value!r}")
    single_line(value["text"], "texte de l'Owner Finding")
    route = one_of(value["route"], OWNER_ROUTES, "route de l'Owner Finding")
    if "cites" in value:
        cites = value["cites"]
        if not isinstance(cites, dict) or set(cites) != {"kind", "ref"} or not isinstance(cites["kind"], str):
            raise Refusal(f"citation de l'Owner Finding mal formée : {cites!r}")
        single_line(cites["ref"], "citation de l'Owner Finding")
    if (route == "repair") != ("draft" in value) or ("ticket" in value and route != "repair") \
            or ("proposal" in value and route != "later"):
        raise Refusal(f"Owner Finding dont la route ({route}) contredit ce qu'il porte : {sorted(value)}")
    if "draft" in value:
        draft = repair_draft(value["draft"], "le repair de l'Owner Finding")
        if draft["restores"]["kind"] not in OWNER_CITED_KINDS:
            raise Refusal("le repair d'un Owner Finding rétablit la story ou l'ancre que le constat cite")
    for name in ("ticket", "proposal"):
        if name in value and (not isinstance(value[name], str) or not BEAD_ID_RE.match(value[name])):
            raise Refusal(f"{name} de l'Owner Finding mal formé : {value[name]!r}")
    if "proposition" in value:
        single_line(value["proposition"], "proposition de l'Owner Finding")
    return value


def judgement_record(raw: Any) -> dict[str, Any]:
    """Benjamin's judgement of the Outcome of a convoy (T29, Spec §11): his
    verdict on each proposition, and each of his answers, oldest first --
    his words, the commit and the fingerprint of the dossier he judged, and
    for « constats rendus » each Owner Finding with its route. Nothing
    follows an accepted or an abandoned Outcome."""
    record = stored_record(raw, ("verdicts", "answers"))
    if not isinstance(record["verdicts"], list) or not isinstance(record["answers"], list):
        raise Refusal(f"jugement mal formé : {raw!r}")
    seen = set()
    for verdict in record["verdicts"]:
        required = {"proposition", "verdict", "approver", "words", "commit", "at"}
        if not isinstance(verdict, dict) or not required <= set(verdict) <= required | {"proposal", "answer"}:
            raise Refusal(f"verdict de proposition mal formé : {verdict!r}")
        single_line(verdict["proposition"], "proposition")
        one_of(verdict["verdict"], OWNER_VERDICTS, "verdict de proposition")
        single_line(verdict["approver"], "approbateur")
        owner_words(verdict["words"], "verdict")
        valid_commit(verdict["commit"], "commit du dossier")
        if verdict["proposition"] in seen:
            raise Refusal(f"deux verdicts sur la proposition {verdict['proposition']}")
        seen.add(verdict["proposition"])
        if "proposal" in verdict and (verdict["verdict"] != "plus_tard" or not isinstance(verdict["proposal"], str)
                                      or not BEAD_ID_RE.match(verdict["proposal"])):
            raise Refusal(f"proposition créée mal formée ou hors d'un verdict « plus tard » : {verdict!r}")
        if "answer" in verdict and (verdict["verdict"] != "avant" or type(verdict["answer"]) is not int
                                    or not 1 <= verdict["answer"] <= len(record["answers"])):
            raise Refusal(f"renvoi d'un verdict à une réponse inconnue : {verdict!r}")
    for index, answer in enumerate(record["answers"]):
        required = {"response", "approver", "commit", "pack", "at"}
        if not isinstance(answer, dict) or not required <= set(answer) \
                or not set(answer) <= required | {"words", "reason", "findings", "exception", "voided"}:
            raise Refusal(f"réponse de l'approbateur mal formée : {answer!r}")
        response = one_of(answer["response"], OWNER_RESPONSES, "réponse de l'approbateur")
        single_line(answer["approver"], "approbateur")
        valid_commit(answer["commit"], "commit du dossier")
        valid_digest(answer["pack"])
        if "voided" in answer:
            voided = answer["voided"]
            if response != "accepted" or not isinstance(voided, dict) or set(voided) != {"cause", "at"}:
                raise Refusal(f"acceptation annulée mal formée : {answer!r}")
            one_of(voided["cause"], VOID_CAUSES, "cause de l'annulation")
        elif response in OWNER_FINAL_RESPONSES and index != len(record["answers"]) - 1:
            raise Refusal("une réponse suit un Outcome accepté ou abandonné : rien ne le rouvre")
        if (response == "abandoned") != ("reason" in answer) or (response == "findings") != ("findings" in answer) \
                or ("exception" in answer and response != "findings") or (response != "abandoned" and "words" not in answer):
            raise Refusal(f"réponse « {response} » dont les champs ne sont pas les siens : {sorted(answer)}")
        if "words" in answer:
            owner_words(answer["words"], "réponse")
        if "reason" in answer:
            single_line(answer["reason"], "raison de l'abandon")
        if "findings" in answer:
            if not isinstance(answer["findings"], list) or not answer["findings"]:
                raise Refusal("« constats rendus » sans aucun constat")
            for finding in answer["findings"]:
                owner_finding_record(finding)
            excepted = [number for number, finding in enumerate(answer["findings"], start=1)
                        if finding["route"] == "planning_exception"]
            exception = answer.get("exception")
            if bool(excepted) != (exception is not None):
                raise Refusal("la Planning Exception du lot ne couvre pas les constats qui en relèvent")
            if exception is not None:
                if not isinstance(exception, dict) or not {"findings", "at"} <= set(exception) <= {"findings", "at", "resolved", "spec_digest"} \
                        or exception["findings"] != excepted \
                        or ("spec_digest" in exception and not (isinstance(exception["spec_digest"], str)
                                                                and DIGEST_RE.match(exception["spec_digest"]))):
                    raise Refusal(f"Planning Exception du lot mal formée : {exception!r}")
                resolved = exception.get("resolved")
                if resolved is not None:
                    if not isinstance(resolved, dict) or set(resolved) != {"approver", "words", "at"}:
                        raise Refusal(f"résolution de la Planning Exception du lot mal formée : {resolved!r}")
                    single_line(resolved["approver"], "approbateur")
                    owner_words(resolved["words"], "résolution")
    return record


def judgement_of(metadata: dict[str, Any]) -> dict[str, Any]:
    return judgement_record(metadata[KEY_JUDGEMENT]) if KEY_JUDGEMENT in metadata else {"verdicts": [], "answers": []}


def final_answer(judgement: dict[str, Any]) -> dict[str, Any] | None:
    """The answer that ends the judgement of an Outcome: the last one, when
    it is « accepté » or « abandonné » and no red replay voided it."""
    last = judgement["answers"][-1] if judgement["answers"] else None
    return last if last is not None and last["response"] in OWNER_FINAL_RESPONSES and "voided" not in last else None


def promotion_record(raw: Any) -> dict[str, Any]:
    """The promotion of an accepted Outcome (T30, Spec §9): the commit
    Benjamin judged, the tip of the integration branch that was merged (the
    same, or the one that took the protected branch up), the tip the
    protected branch had before, and the one merge it received."""
    record = stored_record(raw, ("judged", "merged", "protected", "tip", "at"))
    for name, what in (("judged", "commit jugé"), ("merged", "commit de la fusion"),
                       ("protected", "pointe de la branche protégée avant la fusion"),
                       ("tip", "pointe fusionnée de la branche d'intégration")):
        valid_commit(record[name], what)
    return record


def closed_record(raw: Any) -> dict[str, Any]:
    """The closing of a convoy by command (T30, Spec §9): accepted or
    abandoned, with Benjamin's words -- his acceptance, or the reason of the
    abandon -- and who said them."""
    record = stored_record(raw, ("how", "said", "approver", "at"))
    one_of(record["how"], tuple(CLOSINGS), "fermeture du convoi")
    single_line(record["said"], "mots de la fermeture")
    single_line(record["approver"], "approbateur")
    return record


def owner_answer_of(metadata: dict[str, Any]) -> dict[str, Any] | None:
    """Benjamin's last answer on a convoy, from the metadata of its bead; None
    without one, or on a record this command would not have written. For
    the readers that hold a bead and run no command (the cockpit)."""
    judgement = stored_or_none(metadata.get(KEY_JUDGEMENT), judgement_record)
    return judgement["answers"][-1] if judgement and judgement["answers"] else None


def propositions_of(tickets: list[dict[str, Any]]) -> dict[str, str]:
    """Each « proposition pour Benjamin » of the convoy and its text: the
    findings « hors ticket » the Evaluator of the end kept as a proposal."""
    known: dict[str, str] = {}
    for ticket in tickets:
        handoff, content = handoff_findings(ticket)
        metadata = metadata_of(ticket)
        if not handoff or KEY_FINDINGS not in metadata:
            continue
        for entry in findings_record(metadata[KEY_FINDINGS]):
            number = int(entry["item"].rsplit(".", 1)[1])
            if entry["handoff_at"] == handoff["at"] and entry["classification"] == "proposal" and number <= len(content):
                known[f"{ticket['id']}:{entry['item']}"] = content[number - 1]
    return known


def owner_findings_open(metadata: dict[str, Any], tickets: list[dict[str, Any]]) -> list[str]:
    """What the last « constats rendus » still holds the Outcome out of
    Delivered for: a returned finding whose `repair` is not published, and
    the Planning Exception of the batch while it is open."""
    judgement = stored_or_none(metadata.get(KEY_JUDGEMENT), judgement_record)
    last = judgement["answers"][-1] if judgement and judgement["answers"] else None
    if last is None or last["response"] != "findings":
        return []
    known = {str(ticket.get("id")) for ticket in tickets}
    reasons = []
    unpublished = [str(number) for number, finding in enumerate(last["findings"], start=1)
                   if finding["route"] == "repair" and finding.get("ticket") not in known]
    if unpublished:
        reasons.append(f"constat(s) rendu(s) par l'approbateur sans repair publié (n° {', '.join(unpublished)})")
    if "exception" in last and "resolved" not in last["exception"]:
        reasons.append("Planning Exception du lot de constats rendus encore ouverte")
    return reasons


def not_reopened(convoy_id: str, judgement: dict[str, Any]) -> None:
    last = final_answer(judgement)
    if last is not None:
        said = "accepté" if last["response"] == "accepted" else "abandonné"
        raise Refusal(
            f"l'Outcome du convoi {convoy_id} est {said} : rien ne le rouvre ; un défaut ou un souhait trouvé après "
            "entre comme travail nouveau, par un Planning Run")


def judged_delivered(convoy_id: str, metadata: dict[str, Any], what: str) -> dict[str, Any]:
    delivered = stored_or_none(metadata.get(KEY_DELIVERED), delivered_record)
    if delivered is None:
        raise Refusal(f"le convoi {convoy_id} n'est pas Delivered : {what} ne s'enregistre que sur un Delivered Outcome")
    return delivered


def cmd_record_proposition_verdict(args: argparse.Namespace) -> int:
    """Record Benjamin's verdict on one « proposition » of the Delivered
    Outcome (T29, Spec §11): à faire avant d'accepter, plus tard, sans
    suite. A verdict may change until code acted on it. That `--approver`
    is the declared human approver is the refusal of the caller,
    bin/owner-answer."""
    convoy, tickets = load_convoy(args.convoy)
    require_marked(convoy)
    metadata = metadata_of(convoy)
    judgement = judgement_of(metadata)
    not_reopened(args.convoy, judgement)
    delivered = judged_delivered(args.convoy, metadata, "un verdict")
    verdict = one_of(args.verdict, OWNER_VERDICTS, "verdict de proposition")
    approver = single_line(args.approver, "approbateur")
    words = owner_words(args.words, "verdict")
    if args.proposition not in propositions_of(tickets):
        raise Refusal(
            f"{args.proposition!r} n'est pas une proposition du convoi {args.convoy} : un verdict porte sur un constat "
            "hors ticket gardé comme « proposition pour Benjamin »")
    known = next((entry for entry in judgement["verdicts"] if entry["proposition"] == args.proposition), None)
    if known is not None:
        if known["verdict"] == verdict:
            return done(args.convoy, args.convoy, {})
        if "proposal" in known or "answer" in known:
            raise Refusal(
                f"le verdict « {OWNER_VERDICT_NAMES[known['verdict']]} » de la proposition {args.proposition} a déjà "
                "eu sa suite : il ne se change plus")
        judgement["verdicts"].remove(known)
    judgement["verdicts"].append({"proposition": args.proposition, "verdict": verdict, "approver": approver, "words": words,
                                  "commit": delivered["commit"], "at": now()})
    values = {KEY_JUDGEMENT: encode(judgement_record(encode(judgement)))}
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


def cmd_set_verdict_proposal(args: argparse.Namespace) -> int:
    """Name the proposition the door created for a verdict « plus tard »."""
    convoy, _ = load_convoy(args.convoy)
    require_marked(convoy)
    judgement = judgement_of(metadata_of(convoy))
    known = next((entry for entry in judgement["verdicts"] if entry["proposition"] == args.proposition), None)
    if known is None or known["verdict"] != "plus_tard":
        raise Refusal(f"la proposition {args.proposition!r} n'a pas de verdict « plus tard » sur le convoi {args.convoy}")
    if known.get("proposal") == args.bead:
        return done(args.convoy, args.convoy, {})
    if "proposal" in known:
        raise Refusal(f"le verdict « plus tard » de {args.proposition} a déjà sa proposition ({known['proposal']})")
    known["proposal"] = args.bead
    values = {KEY_JUDGEMENT: encode(judgement_record(encode(judgement)))}
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


def routed_owner_finding(given: Any, number: int, spec: dict[str, Any], repo: str | None = None) -> dict[str, Any]:
    """The route of one Owner Finding, by code (Spec §11): « plus tard » is
    a proposition; a finding that cites a story of the Spec or an anchor of
    a prototyped state of its Validated Prototype (T40, read in `repo`) is
    a `repair`; anything else asks for what the Spec does not require, and
    is a Planning Exception -- never a repair. A prototype that cannot be
    read routes nothing: the answer is refused."""
    what = f"le constat n° {number}"
    if not isinstance(given, dict) or "text" not in given or not set(given) <= {"text", "cites", "repair", "later"}:
        raise Refusal(f"{what} est mal formé (attendu : text, et au besoin cites, repair, later) : {given!r}")
    finding: dict[str, Any] = {"text": single_line(given["text"], f"texte de {what}")}
    if given.get("later") not in (None, False, True):
        raise Refusal(f"{what} : later vaut true ou false, pas {given['later']!r}")
    cites = given.get("cites")
    if cites is not None:
        if not isinstance(cites, dict) or set(cites) != {"kind", "ref"} or not isinstance(cites["kind"], str):
            raise Refusal(f"{what} : citation mal formée (attendu : kind et ref) : {cites!r}")
        finding["cites"] = {"kind": cites["kind"], "ref": single_line(cites["ref"], f"citation de {what}")}
    if given.get("later"):
        if "repair" in given:
            raise Refusal(f"{what} est « plus tard » et porte un repair : un souhait hors de cet Outcome est une proposition")
        return {**finding, "route": "later"}
    held = False
    if cites is not None and finding["cites"]["kind"] == "anchor":
        held = finding["cites"]["ref"].strip("`") in prototype_anchors(spec, repo)
    elif cites is not None and finding["cites"]["kind"] in OWNER_CITED_KINDS:
        try:
            check_citation(finding["cites"], spec, what)
            held = True
        except Refusal:
            held = False
    if not held:
        return {**finding, "route": "planning_exception"}
    repair = given.get("repair")
    if not isinstance(repair, dict) or set(repair) != set(OWNER_REPAIR_FIELDS):
        raise Refusal(
            f"{what} cite {finding['cites']['ref']!r} sans son repair rédigé : un constat qui cite la story ou l'ancre "
            f"porte le repair à publier (repair, avec {', '.join(OWNER_REPAIR_FIELDS)})")
    return {**finding, "route": "repair", "draft": repair_draft({**repair, "restores": finding["cites"]}, f"le repair de {what}")}


def cmd_record_owner_answer(args: argparse.Namespace) -> int:
    """Record Benjamin's answer to the Outcome he judged (T29, Spec §11),
    with his words, the commit and the fingerprint of the dossier.
    « accepted » is refused while a proposition has no verdict or is to do
    before accepting; it closes and merges nothing. « findings » routes each
    Owner Finding by code, withdraws Delivered and the Acceptance Request,
    and starts the rounds of the end again from zero. « abandoned » takes a
    one-line reason. Nothing follows an accepted or an abandoned Outcome.
    That `--approver` is the declared human approver, that the commit is
    still the tip and that the dossier still holds are the refusals of the
    caller, bin/owner-answer, which reads the project and its repository."""
    convoy, tickets = load_convoy(args.convoy)
    require_marked(convoy)
    metadata = metadata_of(convoy)
    judgement = judgement_of(metadata)
    response = one_of(args.response, OWNER_RESPONSES, "réponse de l'approbateur")
    approver = single_line(args.approver, "approbateur")
    not_reopened(args.convoy, judgement)
    values: dict[str, Any] = {}
    if response == "abandoned":
        dossier = judged_dossier(args.convoy, metadata)
        if dossier is None:
            raise Refusal(
                f"le convoi {args.convoy} n'est pas Delivered et ne porte aucune demande « non conforme » : "
                "il n'y a rien à quoi répondre « abandonné »")
        if not isinstance(args.reason, str) or not args.reason.strip():
            raise Refusal("« abandonné » sans raison : l'abandon s'enregistre avec une raison d'une ligne (--reason)")
        answer: dict[str, Any] = {"response": response, "approver": approver, "commit": dossier["commit"],
                                  "pack": dossier["pack"], "reason": single_line(args.reason, "raison de l'abandon"),
                                  "at": now()}
    else:
        said = "« accepté »" if response == "accepted" else "« constats rendus »"
        delivered = judged_delivered(args.convoy, metadata, said)
        commit = valid_commit(args.commit, "commit du dossier")
        digest = valid_digest(args.pack_digest)
        if commit != delivered["commit"]:
            raise Refusal(
                f"le commit {commit[:12]} n'est pas celui du dossier que Benjamin juge sur le convoi {args.convoy} "
                f"(Delivered au commit {delivered['commit'][:12]}) : {said} se lie au commit jugé")
        if digest != delivered["pack"]:
            raise Refusal(
                f"l'empreinte {digest} n'est pas celle du dossier du Delivered Outcome du convoi {args.convoy} : "
                f"{said} se lie au dossier jugé")
        answer = {"response": response, "approver": approver, "words": owner_words(args.words, said), "commit": commit,
                  "pack": digest, "at": now()}
        known = propositions_of(tickets)
        verdicts = {entry["proposition"]: entry for entry in judgement["verdicts"] if entry["proposition"] in known}
        before = [entry for entry in verdicts.values() if entry["verdict"] == "avant" and "answer" not in entry]
        if response == "accepted":
            pending = [proposition for proposition in known if proposition not in verdicts]
            if pending:
                raise Refusal(
                    f"proposition(s) sans verdict ({', '.join(pending)}) : chaque proposition reçoit son verdict "
                    "(à faire avant d'accepter, plus tard, sans suite) avant « accepté »")
            if before:
                raise Refusal(
                    f"proposition(s) « à faire avant d'accepter » ({', '.join(entry['proposition'] for entry in before)}) : "
                    "elles se rendent avec les constats (« constats rendus ») ; « accepté » vient après")
        else:
            given = json_argument(args.file, "constats rendus").get("findings") if args.file is not None else []
            if not isinstance(given, list):
                raise Refusal(f"constats rendus mal formés (attendu : findings, une liste) : {given!r}")
            if not given and not before:
                raise Refusal(
                    "« constats rendus » sans aucun constat : la réponse porte au moins un Owner Finding (--file), ou une "
                    "proposition « à faire avant d'accepter »")
            spec = spec_of(convoy)
            findings = [routed_owner_finding(finding, number, spec, args.repo)
                        for number, finding in enumerate(given, start=1)]
            for entry in before:
                # A proposition to do first is asked by Benjamin, not by the Spec.
                findings.append({"text": single_line(" ".join(known[entry["proposition"]].split()), "texte de la proposition"),
                                 "route": "planning_exception", "proposition": entry["proposition"]})
                entry["answer"] = len(judgement["answers"]) + 1
            answer["findings"] = findings
            excepted = [number for number, finding in enumerate(findings, start=1) if finding["route"] == "planning_exception"]
            if excepted:
                # One Planning Exception per batch: each such finding joins it.
                # ... raised against the approved Spec the graph is published
                # from: it is resolved once that Spec is amended (T40).
                raised_on = metadata.get(KEY_SPEC_DIGEST)
                answer["exception"] = {"findings": excepted, "at": answer["at"],
                                       **({"spec_digest": raised_on} if isinstance(raised_on, str)
                                          and DIGEST_RE.match(raised_on) else {})}
            # Nothing closes; the Outcome goes back to delivery, and the
            # rounds of the end start again from zero for this batch.
            values.update({KEY_DELIVERED: None, COUNTER_PREFIX + BOUND_END_ROUNDS: 0})
            values.update({key: None for key in (KEY_ACCEPTANCE, KEY_END_ROUND) if key in metadata})
    judgement["answers"].append(answer)
    values[KEY_JUDGEMENT] = encode(judgement_record(encode(judgement)))
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


def accepted_answer(convoy_id: str, metadata: dict[str, Any], what: str) -> dict[str, Any]:
    last = final_answer(judgement_of(metadata))
    if last is None or last["response"] != "accepted":
        raise Refusal(f"aucun « accepté » de l'approbateur ne tient sur le convoi {convoy_id} : {what}")
    return last


def cmd_record_promotion(args: argparse.Namespace) -> int:
    """Note the one merge of an accepted Outcome into the protected branch
    (T30, Spec §9), with the commit Benjamin judged: the two commits the
    dossier reads. Refused without an « accepté » that stands for that
    commit, and recorded once. That the merge exists and holds the judged
    commit is the proof of the caller, bin/outcome-promote, which made it."""
    convoy, _ = load_convoy(args.convoy)
    require_marked(convoy)
    metadata = metadata_of(convoy)
    answer = accepted_answer(args.convoy, metadata, "rien ne se fusionne vers la branche protégée")
    if KEY_PROMOTION in metadata:
        raise Refusal(f"la fusion de l'Outcome du convoi {args.convoy} vers la branche protégée est déjà enregistrée")
    judged = valid_commit(args.judged, "commit jugé")
    if judged != answer["commit"]:
        raise Refusal(
            f"le commit {judged[:12]} n'est pas celui que Benjamin a accepté sur le convoi {args.convoy} "
            f"({answer['commit'][:12]}) : la fusion se lie au commit jugé")
    record = {"judged": judged, "merged": args.merged, "protected": args.protected, "tip": args.tip, "at": now()}
    values = {KEY_PROMOTION: encode(promotion_record(encode(record)))}
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


def cmd_void_acceptance(args: argparse.Namespace) -> int:
    """After « accepté », the replay of the mechanical controls on the
    protected branch taken up was red, or the two branches conflict (T30,
    Spec §9): nothing is merged and the acceptance no longer stands. It
    stays in the judgement with the control that voided it; Delivered and
    the Acceptance Request are withdrawn and the rounds of the end start
    again from zero, as after « constats rendus », so the Outcome passes the
    end of the Spec again and Benjamin judges it again."""
    convoy, _ = load_convoy(args.convoy)
    require_marked(convoy)
    metadata = metadata_of(convoy)
    accepted_answer(args.convoy, metadata, "il n'y a pas d'acceptation à annuler")
    if KEY_PROMOTION in metadata:
        raise Refusal(f"l'Outcome du convoi {args.convoy} est déjà fusionné vers la branche protégée : son acceptation tient")
    cause = one_of(args.cause, VOID_CAUSES, "cause de l'annulation (--cause)")
    judgement = judgement_of(metadata)
    judgement["answers"][-1]["voided"] = {"cause": cause, "at": now()}
    values: dict[str, Any] = {KEY_JUDGEMENT: encode(judgement_record(encode(judgement))),
                              KEY_DELIVERED: None, COUNTER_PREFIX + BOUND_END_ROUNDS: 0}
    values.update({key: None for key in (KEY_ACCEPTANCE, KEY_END_ROUND) if key in metadata})
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


def cmd_close_convoy(args: argparse.Namespace) -> int:
    """Close a marked convoy on Benjamin's words (T30, Spec §9): accepted,
    once its Outcome is merged into the protected branch; abandoned, without
    any merge. The closed status and the record of the closing go in one
    tracker write. Nothing else closes a marked convoy, and nothing reopens
    one closed here."""
    convoy, _ = load_convoy(args.convoy)
    require_marked(convoy)
    metadata = metadata_of(convoy)
    last = final_answer(judgement_of(metadata))
    if last is None:
        raise Refusal(
            f"ni « accepté » ni « abandonné » ne tient sur le convoi {args.convoy} : un convoi ne se ferme que sur "
            "l'une de ces deux réponses de l'approbateur")
    if convoy.get("status") == "closed":
        raise Refusal(f"le convoi {args.convoy} est fermé hors commande : cette fermeture se signale, elle ne se régularise pas")
    if last["response"] == "accepted":
        promotion = stored_or_none(metadata.get(KEY_PROMOTION), promotion_record)
        if promotion is None or promotion["judged"] != last["commit"]:
            raise Refusal(
                f"l'Outcome accepté du convoi {args.convoy} n'est pas fusionné vers la branche protégée : "
                "la fermeture suit la fusion")
    elif KEY_PROMOTION in metadata:
        raise Refusal(f"le convoi {args.convoy} est abandonné et porte une fusion : état sans règle")
    record = {"how": last["response"], "said": last["words"] if last["response"] == "accepted" else last["reason"],
              "approver": last["approver"], "at": now()}
    values = {KEY_CLOSED: encode(closed_record(encode(record)))}
    update = ["bd", "update", args.convoy, "--status", "closed"]
    for key, value in values.items():
        update += ["--set-metadata", f"{key}={value}"]
    run_gc(update)
    print(json.dumps({"ok": True, "convoy": args.convoy, "bead": args.convoy, "closed": True, "how": record["how"],
                      "written": values}, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def last_owner_findings(convoy_id: str, judgement: dict[str, Any], number: Any, route: str) -> dict[str, Any]:
    last = judgement["answers"][-1] if judgement["answers"] else None
    if last is None or last["response"] != "findings":
        raise Refusal(f"la dernière réponse enregistrée sur le convoi {convoy_id} n'est pas « constats rendus »")
    if not isinstance(number, str) or not re.fullmatch(r"[1-9][0-9]*", number) or int(number) > len(last["findings"]):
        raise Refusal(f"constat inconnu : {number!r} (le lot en porte {len(last['findings'])})")
    finding = last["findings"][int(number) - 1]
    if finding["route"] != route:
        raise Refusal(f"le constat n° {number} n'a pas la route {route} (route : {finding['route']})")
    return finding


def cmd_set_owner_repair(args: argparse.Namespace) -> int:
    """Name the repair ticket code published for an Owner Finding that
    cites a story or an anchor: a tracked ticket of the convoy, of kind
    `repair`. One repair per finding."""
    convoy, tickets = load_convoy(args.convoy)
    require_marked(convoy)
    judgement = judgement_of(metadata_of(convoy))
    finding = last_owner_findings(args.convoy, judgement, args.finding, "repair")
    ticket = marked_ticket_among(tickets, args.convoy, args.ticket)
    if metadata_of(ticket).get(KEY_KIND) != "repair":
        raise Refusal(f"le ticket {args.ticket} n'est pas un repair : un constat qui cite la story ou l'ancre se répare")
    if finding.get("ticket") == args.ticket:
        return done(args.convoy, args.convoy, {})
    if "ticket" in finding:
        raise Refusal(f"le constat n° {args.finding} a déjà son repair ({finding['ticket']}) : un seul repair par constat")
    finding["ticket"] = args.ticket
    values = {KEY_JUDGEMENT: encode(judgement_record(encode(judgement)))}
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


def cmd_set_owner_proposal(args: argparse.Namespace) -> int:
    """Name the proposition the door created for an Owner Finding « plus tard »."""
    convoy, _ = load_convoy(args.convoy)
    require_marked(convoy)
    judgement = judgement_of(metadata_of(convoy))
    finding = last_owner_findings(args.convoy, judgement, args.finding, "later")
    if finding.get("proposal") == args.bead:
        return done(args.convoy, args.convoy, {})
    if "proposal" in finding:
        raise Refusal(f"le constat n° {args.finding} a déjà sa proposition ({finding['proposal']})")
    finding["proposal"] = args.bead
    values = {KEY_JUDGEMENT: encode(judgement_record(encode(judgement)))}
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


def cmd_resolve_owner_exception(args: argparse.Namespace) -> int:
    """Record that the Planning Exception of the last batch of returned
    findings is resolved, on the operator's words, once the Spec is amended
    and its graph revised (Spec §11): refused while the convoy is still
    published from the approved Spec it was raised against (T40) -- the
    patch door writes the digest of the newly approved Spec on the convoy.
    Until then the Outcome is not Delivered again."""
    convoy, _ = load_convoy(args.convoy)
    require_marked(convoy)
    metadata = metadata_of(convoy)
    judgement = judgement_of(metadata)
    last = judgement["answers"][-1] if judgement["answers"] else None
    if last is None or "exception" not in last:
        raise Refusal(f"aucune Planning Exception de lot n'est ouverte sur le convoi {args.convoy}")
    approver = single_line(args.approver, "approbateur")
    words = owner_words(args.words, "résolution")
    if "resolved" in last["exception"]:
        return done(args.convoy, args.convoy, {})
    raised_on = last["exception"].get("spec_digest")
    if raised_on is not None and metadata.get(KEY_SPEC_DIGEST) == raised_on:
        spec_id = metadata.get(KEY_SPEC)
        raise Refusal(
            f"la Spec {spec_id} n'a pas été amendée depuis que la Planning Exception du lot a été levée : le convoi "
            f"{args.convoy} est toujours publié depuis sa version approuvée d'alors ({raised_on}) ; la Planning Exception "
            "se résout une fois la Spec amendée approuvée (bin/spec-approve) et le graphe révisé publié depuis elle "
            "(bin/ticket-graph-publish bd-patch)")
    last["exception"]["resolved"] = {"approver": approver, "words": words, "at": now()}
    values = {KEY_JUDGEMENT: encode(judgement_record(encode(judgement)))}
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


def cmd_record_evidence_pack(args: argparse.Namespace) -> int:
    """bin/evidence-pack records the page it generated (T27, Spec §10): the
    commit of the integration branch it is tied to, its fingerprint and
    where it is. Nothing compares it to the branches here: bin/evidence-pack
    check says whether it still holds. The same pack again writes nothing."""
    convoy, _ = load_convoy(args.convoy)
    require_marked(convoy)
    metadata = metadata_of(convoy)
    if KEY_INTEGRATION not in metadata:
        raise Refusal(f"le convoi {args.convoy} n'a pas de branche d'intégration : aucun commit auquel lier l'Evidence Pack")
    if args.conforming is None:
        raise Refusal("conformité de l'Evidence Pack absente : --conforming ou --non-conforming")
    try:
        inadmissible = int(args.inadmissible)
    except (TypeError, ValueError) as exc:
        raise Refusal(f"nombre de pièces irrecevables de l'Evidence Pack mal formé : {args.inadmissible!r}") from exc
    record = {"commit": args.commit, "digest": args.digest, "path": args.path, "conforming": args.conforming,
              "inadmissible": inadmissible, "version": EVIDENCE_PACK_VERSION, "at": now()}
    record = evidence_pack_record(encode(record))
    if KEY_EVIDENCE_PACK in metadata:
        try:
            known = evidence_pack_record(metadata[KEY_EVIDENCE_PACK])
        except Refusal:
            known = None
        if known and {**known, "at": record["at"]} == record:
            return done(args.convoy, args.convoy, {})
    values = {KEY_EVIDENCE_PACK: encode(record)}
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


# --- the end code review of the Spec, on the assembled diff (T25) ---------------------


def end_review_target(convoy_id: str) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """The convoy an end-review write lands on, its tickets, its metadata
    and its end review so far."""
    convoy, tickets = load_convoy(convoy_id)
    require_marked(convoy)
    metadata = metadata_of(convoy)
    record = end_review_record(metadata[KEY_END_REVIEW]) if KEY_END_REVIEW in metadata else {"rounds": []}
    return convoy, tickets, metadata, record


def end_review_models(tickets: list[dict[str, Any]], reviewer: str | None) -> dict[str, Any]:
    """Spec §6: the reviewer is of another model than the author; when they
    are identical, or one is not known, it is said, never left out."""
    authors: list[str] = []
    unknown = False
    for ticket in tickets:
        metadata = metadata_of(ticket)
        if GATE_PREFIX + "withdrawn" in metadata:
            continue
        model = ((models_record(metadata[KEY_MODELS]) if KEY_MODELS in metadata else {}).get("author") or {}).get("model")
        if model is None:
            unknown = True
        elif model not in authors:
            authors.append(model)
    if reviewer is None:
        same = None
    elif any(normalized_model(model) == normalized_model(reviewer) for model in authors):
        same = True
    else:
        same = None if unknown else False
    return {"authors": sorted(authors), "reviewer": reviewer, "same_model": same}


def cmd_open_end_review(args: argparse.Namespace) -> int:
    """Open the end code review of the Spec (T25, Spec §6, §9 point 4) on
    the commit the end-of-Spec gate rendered its three mechanical verdicts
    on: the diff under review is the whole one, from the tip of the
    protected branch that commit holds. The same request again writes
    nothing; a request left on an earlier commit is replaced, and no round
    of an earlier commit stands for this one."""
    _, tickets, metadata, record = end_review_target(args.convoy)
    commit = valid_commit(args.commit, "commit de la revue de fin")
    gate = spec_end_record(metadata[KEY_SPEC_END]) if KEY_SPEC_END in metadata else None
    if gate is None or gate["commit"] != commit or KEY_INTEGRATION_RED in metadata:
        raise Refusal(
            f"les trois verdicts mécaniques de la porte de fin de Spec ne sont pas rendus au commit {commit} "
            f"({'rendus au commit ' + gate['commit'] if gate else 'jamais rendus'}"
            f"{', branche d’intégration rouge' if KEY_INTEGRATION_RED in metadata else ''}) : la revue de fin "
            "porte sur le commit de la porte")
    given = json_argument(args.file, "demande de revue de fin")
    unknown = sorted(set(given) - {"extent", "reviewer"})
    if unknown:
        raise Refusal(f"champs inconnus dans la demande de revue de fin : {', '.join(unknown)}")
    extent = end_extent(given.get("extent"))
    reviewer = given.get("reviewer")
    if reviewer is not None:
        if not isinstance(reviewer, dict) or set(reviewer) != {"agent", "provider", "model"}:
            raise Refusal(f"relecteur de la revue de fin mal formé : {reviewer!r} (attendu : agent, provider, model)")
        reviewer = single_line(reviewer["model"], "modèle du relecteur")
    models = end_review_models(tickets, reviewer)
    stop = record.get("stop")
    if stop and stop["commit"] == commit:
        raise Refusal(
            f"la revue de fin est arrêtée au commit {commit} ({stop['reason']}) : aucune autre ne s'ouvre sur cette pointe")
    if any(round_["commit"] == commit and round_["outcome"] != END_REVIEW_INCOMPLETE for round_ in record["rounds"]):
        raise Refusal(f"le diff assemblé est déjà revue au commit {commit} : la revue de fin est rejouée sur une nouvelle pointe")
    request = record.get("request")
    if request and (request["commit"], request["base"], request["extent"]) == (commit, gate["protected"], extent):
        if request["models"] == models:
            return done(args.convoy, args.convoy, {})
        request["models"] = models
    else:
        record["request"] = {"commit": commit, "base": gate["protected"], "extent": extent, "launches": [],
                             "models": models, "at": now()}
        record.pop("stop", None)
    values = {KEY_END_REVIEW: encode(end_review_record(encode(record)))}
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


def cmd_launch_end_review(args: argparse.Namespace) -> int:
    """Record that a reviewer session was sent the open end review: the
    first launch, then one relaunch when the first gave no result."""
    _, _, _, record = end_review_target(args.convoy)
    request = record.get("request")
    if not request or "stop" in record:
        raise Refusal(f"aucune revue de fin n'est demandée sur le convoi {args.convoy} : rien à lancer")
    if not isinstance(args.bead, str) or not BEAD_ID_RE.match(args.bead):
        raise Refusal(f"bead de revue absent ou mal formé : {args.bead!r}")
    if len(request["launches"]) >= END_REVIEW_MAX_LAUNCHES:
        raise Refusal(
            f"une seule relance par revue de fin : le convoi {args.convoy} en a déjà lancé {len(request['launches'])} "
            "sans résultat")
    launch: dict[str, Any] = {"bead": args.bead, "at": now()}
    incomplete = sum(1 for round_ in record["rounds"]
                     if round_["commit"] == request["commit"] and round_["outcome"] == END_REVIEW_INCOMPLETE)
    if incomplete > sum(1 for known in request["launches"] if "result" in known):
        # Its session already handed in an incomplete output, before this
        # launch was written: it gave no result.
        launch["result"] = END_REVIEW_INCOMPLETE
    request["launches"].append(launch)
    values = {KEY_END_REVIEW: encode(record)}
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


def end_refusal_values(metadata: dict[str, Any], commit: str, source: str, at: str, detail: str,
                       not_observed: list[int] | None = None, once_per_tip: bool = True) -> dict[str, Any]:
    """What a refusal of the tip `commit` at the end of the Spec writes
    (T26, Spec §8: at most `bounds.end_rounds` rounds of repair, every
    source of findings together -- one counter). Either one round counted,
    once per tip whichever source refuses it first, or the stop of the
    rounds, and then no round: the bound is consumed, or, on what an
    Outcome Evaluation did not observe (`not_observed`), a story is refused
    a second time or the round before did not reduce their number. Nothing
    on a convoy whose rounds are already stopped. A Delivered Outcome does
    not survive a refusal."""
    if KEY_END_STOP in metadata:
        return {}
    counted = end_round_record(metadata[KEY_END_ROUND]) if KEY_END_ROUND in metadata else None
    same = once_per_tip and counted is not None and counted["commit"] == commit
    if same:
        previous, refused = counted.get("previous_not_observed", []), counted.get("refused_before", [])
    elif counted:
        previous = counted.get("not_observed", [])
        refused = sorted({*counted.get("refused_before", []), *previous})
    else:
        previous, refused = [], []
    counter = COUNTER_PREFIX + "end_rounds"
    rounds = counter_value(metadata.get(counter), "end_rounds")
    stop: tuple[str, str] | None = None
    twice = sorted(set(not_observed or []) & set(refused))
    if twice:
        stop = (END_STOP_TWICE, f"user story {', '.join(map(str, twice))} refusée deux fois par l'Outcome Evaluation : "
                                "arrêt avant un tour de plus")
    elif not_observed and previous and len(not_observed) >= len(previous):
        stop = (END_STOP_NOT_REDUCED, (
            f"le tour de réparation n'a pas réduit le nombre de user stories non observées ({len(previous)} avant, "
            f"{len(not_observed)} après) : arrêt avant un tour de plus"))
    elif not same:
        bound = flow_bound(BOUND_END_ROUNDS)
        if rounds >= bound:
            stop = (END_STOP_EXHAUSTED, f"{rounds} tour(s) de réparation consommé(s) (borne : {bound}), et la fin de Spec "
                                        f"est encore refusée : {detail}")
    withdrawn = {KEY_DELIVERED: None} if KEY_DELIVERED in metadata else {}
    if stop:
        return {**withdrawn, KEY_END_STOP: encode(end_stop_record(encode({
            "reason": stop[0], "detail": single_line(" ".join(stop[1].split())[:MAX_FINDING_LINE], "précision de l'arrêt"),
            "commit": commit, "source": source, "rounds": rounds, "at": at})))}
    if same:
        if not_observed is None or counted.get("not_observed") == not_observed:
            return {}
        return {KEY_END_ROUND: encode(end_round_record(encode({**counted, "not_observed": not_observed})))}
    record: dict[str, Any] = {"commit": commit, "source": source, "at": at}
    if previous:
        record["previous_not_observed"] = previous
    if refused:
        record["refused_before"] = refused
    if not_observed is not None:
        record["not_observed"] = not_observed
    return {**withdrawn, counter: rounds + 1, KEY_END_ROUND: encode(end_round_record(encode(record)))}


def cmd_record_end_review(args: argparse.Namespace) -> int:
    """Record what a reviewer session hands in for the open end review, and
    compute its outcome (T25, Spec §6). A finding blocks only with a
    citation that holds, as in the review of a ticket; a Blocking Finding
    comes with the `repair` its reviewer drafted. An output that does not
    cover the two axes and every file of the diff is incomplete: it is
    recorded, gives no verdict, and its launch gave no result. An
    unfavorable review counts one round of the end, in the same write, or
    stops the rounds when they are consumed (T26)."""
    _, _, metadata, record = end_review_target(args.convoy)
    request = record.get("request")
    if not request:
        raise Refusal(f"aucune revue de fin n'est demandée sur le convoi {args.convoy} : une revue répond à une demande ouverte")
    if "stop" in record:
        raise Refusal(f"la revue de fin du convoi {args.convoy} est arrêtée ({record['stop']['reason']}) : rien ne s'y enregistre")
    given = json_argument(args.file, "revue de fin")
    problems = [
        "l'issue est calculée par du code, jamais donnée par le relecteur" if name in ("verdict", "outcome")
        else f"champ inconnu : {name}"
        for name in sorted(set(given) - {"commit", "recorded_by", "findings", "coverage"})]
    if given.get("commit") != request["commit"]:
        problems.append(f"la revue rendue porte sur le commit {given.get('commit')!r}, la demande sur {request['commit']}")
    recorded_by = given.get("recorded_by")
    if not isinstance(recorded_by, str) or not recorded_by.strip() or "\n" in recorded_by:
        problems.append(f"session du relecteur absente ou mal formée : {recorded_by!r}")
    try:
        coverage = end_coverage(given.get("coverage"))
    except Refusal as exc:
        problems.append(str(exc))
        coverage = None
    number = len(record["rounds"]) + 1
    raw = given.get("findings", [])
    if not isinstance(raw, list):
        problems.append("findings mal formé : une liste de constats est attendue")
        raw = []
    drafts = [finding.get("repair") if isinstance(finding, dict) else None for finding in raw]
    plain = [{name: value for name, value in finding.items() if name not in ("repair", "citation")}
             if isinstance(finding, dict) else finding for finding in raw]
    findings, _ = given_findings({"findings": plain}, number, problems)
    demoted: list[dict[str, str]] = []
    for finding, source, draft in zip(findings, raw, drafts):
        citation, reason = end_citation_of(source) if isinstance(source, dict) else (None, "constat mal formé")
        finding.pop("demoted", None)
        if citation is not None:
            finding["citation"] = citation
        finding["blocking"] = isinstance(source, dict) and source.get("blocking") is True
        if finding["blocking"] and reason is not None:
            finding["blocking"] = False
            finding["demoted"] = f"refusé comme bloquant : {reason}"
            demoted.append({"id": finding["id"], "reason": finding["demoted"]})
        elif finding["blocking"]:
            # Spec §6: a Blocking Finding of the end becomes a repair its reviewer drafted.
            if draft is None:
                problems.append(f"constat {finding['id']} : Blocking Finding sans repair rédigé (champ repair)")
                continue
            written, wrong = end_repair_draft(draft, f"constat {finding['id']}")
            if wrong:
                problems.append(wrong)
            else:
                finding["repair_draft"] = written
    if problems:
        raise Refusal("revue de fin hors contrat : " + " ; ".join(problems))
    complete = end_review_complete(coverage, request["extent"])
    blocking = [finding["id"] for finding in findings if finding["blocking"]]
    outcome = END_REVIEW_INCOMPLETE if not complete else "unfavorable" if blocking else "favorable"
    at = now()
    # The time the review took: from its launch, or from the request when
    # the session answered before its launch was written.
    launched = request["launches"][-1]["at"] if request["launches"] else request["at"]
    duration = max(0, int(time.mktime(time.strptime(at, "%Y-%m-%dT%H:%M:%SZ"))
                          - time.mktime(time.strptime(launched, "%Y-%m-%dT%H:%M:%SZ"))))
    record["rounds"].append({
        "commit": request["commit"], "base": request["base"], "outcome": outcome, "findings": findings,
        "coverage": coverage, "extent": request["extent"], "models": request["models"],
        "recorded_by": recorded_by.strip(), "launched_at": launched, "duration_seconds": duration, "at": at})
    if complete:
        del record["request"]
    elif request["launches"]:
        # An incomplete output is not a passed review: its launch gave no result.
        request["launches"][-1]["result"] = END_REVIEW_INCOMPLETE
    values: dict[str, Any] = {KEY_END_REVIEW: encode(end_review_record(encode(record)))}
    if outcome == "unfavorable":
        values.update(end_refusal_values(
            metadata, request["commit"], END_REVIEW_SOURCE, at,
            f"Blocking Finding de la revue de fin ({', '.join(blocking)}) au commit {request['commit'][:12]}"))
    write_metadata(args.convoy, values)
    print(json.dumps({"ok": True, "convoy": args.convoy, "bead": args.convoy, "outcome": outcome, "complete": complete,
                      "blocking": blocking if complete else [], "demoted": demoted, "findings": len(findings),
                      "duration_seconds": duration, "written": values}, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def cmd_set_end_review_repair(args: argparse.Namespace) -> int:
    """Name, on a Blocking Finding of the last end review, the `repair` code
    published from the draft of the reviewer through the patch door -- or
    why that door refused the draft. Written once per finding."""
    _, tickets, _, record = end_review_target(args.convoy)
    last = record["rounds"][-1] if record["rounds"] else None
    finding = next((entry for entry in (last or {}).get("findings", [])
                    if entry["id"] == args.finding and entry["blocking"]), None)
    if last is None or last["outcome"] != "unfavorable" or finding is None:
        raise Refusal(f"{args.finding!r} n'est pas un Blocking Finding de la dernière revue de fin du convoi {args.convoy}")
    if (args.ticket is None) == (args.refused is None):
        raise Refusal("--ticket ou --refused : le repair publié, ou la raison pour laquelle la porte de patch l'a refusé")
    if args.ticket is not None:
        wanted = ("repair", args.ticket)
        repair = next((ticket for ticket in tickets if ticket.get("id") == args.ticket), None)
        if repair is None:
            raise Refusal(f"le ticket {args.ticket} n'appartient pas au convoi {args.convoy}")
        if metadata_of(repair).get(KEY_KIND) != "repair":
            raise Refusal(f"le ticket {args.ticket} n'est pas un repair")
    else:
        wanted = ("repair_refused", single_line(args.refused, "raison du refus (--refused)")[:MAX_FINDING_LINE])
    if finding.get(wanted[0]) == wanted[1]:
        return done(args.convoy, args.convoy, {})
    if "repair" in finding or "repair_refused" in finding:
        raise Refusal(f"le constat {args.finding} a déjà son repair ({finding.get('repair') or 'refusé par la porte de patch'})")
    finding[wanted[0]] = wanted[1]
    values = {KEY_END_REVIEW: encode(end_review_record(encode(record)))}
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


def cmd_stop_end_review(args: argparse.Namespace) -> int:
    """Stop the end review on its commit: its two launches gave no result,
    or the patch door refused a repair its reviewer drafted. Nothing more is
    launched on that commit; the gate goes on refusing."""
    _, _, _, record = end_review_target(args.convoy)
    reason = one_of(args.reason, END_REVIEW_STOPS, "raison de l'arrêt de la revue de fin")
    detail = single_line(args.detail, "détail de l'arrêt (--detail)")
    request, last = record.get("request"), record["rounds"][-1] if record["rounds"] else None
    commit = request["commit"] if request else last["commit"] if last else None
    if commit is None:
        raise Refusal(f"aucune revue de fin n'a été demandée sur le convoi {args.convoy} : rien à arrêter")
    if "stop" in record:
        if (record["stop"]["reason"], record["stop"]["commit"]) == (reason, commit):
            return done(args.convoy, args.convoy, {})
        raise Refusal(f"la revue de fin du convoi {args.convoy} est déjà arrêtée ({record['stop']['reason']})")
    record["stop"] = {"reason": reason, "detail": detail, "commit": commit, "at": now()}
    values = {KEY_END_REVIEW: encode(end_review_record(encode(record)))}
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


def cmd_end_review_stop_raised(args: argparse.Namespace) -> int:
    """Record that the stop of the end review reached the operator, on the
    bead that carries the request."""
    _, _, _, record = end_review_target(args.convoy)
    if "stop" not in record:
        raise Refusal(f"la revue de fin du convoi {args.convoy} n'est pas arrêtée : aucune remontée à enregistrer")
    if not isinstance(args.bead, str) or not BEAD_ID_RE.match(args.bead):
        raise Refusal(f"bead de la demande absent ou mal formé : {args.bead!r}")
    if "raised" in record["stop"]:
        return done(args.convoy, args.convoy, {})
    record["stop"].update(bead=args.bead, raised=now())
    values = {KEY_END_REVIEW: encode(end_review_record(encode(record)))}
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


def cmd_set_integration_repair(args: argparse.Namespace) -> int:
    """Name the repair ticket code published for the red of the integration
    branch: a tracked ticket of the convoy, of kind `repair`. One repair per
    red: another one is refused while the first is open."""
    convoy, tickets = load_convoy(args.convoy)
    require_marked(convoy)
    metadata = metadata_of(convoy)
    if KEY_INTEGRATION_RED not in metadata:
        raise Refusal(f"la branche d'intégration du convoi {args.convoy} n'est pas rouge : aucun repair ne s'y rattache")
    record = integration_red_record(metadata[KEY_INTEGRATION_RED])
    ticket = marked_ticket_among(tickets, args.convoy, args.ticket)
    if metadata_of(ticket).get(KEY_KIND) != "repair":
        raise Refusal(f"le ticket {args.ticket} n'est pas un repair : seul un repair rétablit un contrôle rouge")
    if record.get("repair") == args.ticket:
        return done(args.convoy, args.convoy, {})
    known = next((other for other in tickets if other.get("id") == record.get("repair")), None)
    if "repair" in record and (known is None or known.get("status") != "closed"):
        raise Refusal(
            f"le rouge de la branche d'intégration a déjà son repair ({record['repair']}), encore ouvert : "
            "un seul repair par rouge")
    values = {KEY_INTEGRATION_RED: encode(integration_red_record(encode({**record, "repair": args.ticket})))}
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


def cmd_clear_integration_red(args: argparse.Namespace) -> int:
    convoy, _ = load_convoy(args.convoy)
    require_marked(convoy)
    run_gc(["bd", "update", args.convoy, "--unset-metadata", KEY_INTEGRATION_RED])
    return done(args.convoy, args.convoy, {KEY_INTEGRATION_RED: None})


def cmd_record_grouped_request(args: argparse.Namespace) -> int:
    convoy_with_a_mark(args.convoy)
    record: dict[str, Any] = {"bead": args.bead, "at": now()}
    if args.signature is not None:
        record["signature"] = args.signature
    if args.lift_option is not None:
        record["lift_option"] = args.lift_option
    if args.lifts:
        record["lifts"] = list(dict.fromkeys(args.lifts))
    values = {KEY_GROUPED_REQUEST: encode(grouped_request_record(encode(record)))}
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


def cmd_clear_grouped_request(args: argparse.Namespace) -> int:
    convoy_with_a_mark(args.convoy)
    run_gc(["bd", "update", args.convoy, "--unset-metadata", KEY_GROUPED_REQUEST])
    return done(args.convoy, args.convoy, {KEY_GROUPED_REQUEST: None})


# --- the Outcome Evaluation and the findings « hors ticket » (T24) ----------------


def spec_of(convoy: dict[str, Any]) -> dict[str, Any]:
    """The Spec the convoy delivers, as the reader `bin/spec-approve` holds
    it to (`outline`): its numbered user stories, and its text. Nobody hands
    them in."""
    spec_id = metadata_of(convoy).get(KEY_SPEC)
    if not isinstance(spec_id, str) or not BEAD_ID_RE.match(spec_id):
        raise Refusal(f"le convoi {convoy['id']} ne nomme pas sa Spec ({spec_id!r}) : ses user stories sont introuvables")
    try:
        bead = json.loads(run_gc(["bd", "show", spec_id, "--json"]))
    except json.JSONDecodeError as exc:
        raise Refusal(f"gc bd show {spec_id} a rendu un JSON illisible : {exc}") from exc
    bead = bead[0] if isinstance(bead, list) and bead else bead
    text = bead.get("description") if isinstance(bead, dict) else None
    if not isinstance(text, str) or not text.strip():
        raise Refusal(f"la Spec {spec_id} est introuvable ou vide : ses user stories sont introuvables")
    reader = os.environ.get("SPEC_APPROVE_BIN") or str(BIN / "spec-approve")
    try:
        proc = subprocess.run([reader, "outline"], input=text, capture_output=True, text=True)
        outline = json.loads(proc.stdout)
    except (OSError, json.JSONDecodeError) as exc:
        raise Refusal(f"lecture de la Spec {spec_id} impossible ({Path(reader).name} outline) : {exc}") from exc
    if proc.returncode != 0 or not isinstance(outline, dict) or not outline.get("ok"):
        raise Refusal(f"la Spec {spec_id} n'a pas de user stories numérotées lisibles : "
                      f"{outline.get('error') if isinstance(outline, dict) else proc.stderr.strip()}")
    stories = [{"number": int(story["number"]), "text": " ".join(str(story["text"]).split())}
               for story in outline["user_stories"]]
    prototypes = outline.get("validated_prototypes") or [
        reference for reference in [outline.get("validated_prototype")] if reference]
    return {"id": spec_id, "text": text, "stories": outcome_stories(stories), "prototypes": prototypes}


def prototype_anchors(spec: dict[str, Any], repo: str | None) -> set[str]:
    """The named anchors of every prototyped state of the Validated
    Prototypes the Spec names (T40), read at the commit of each reference in
    the repository of the project: what a citation of an anchor is checked
    against. Empty when the Spec names no Validated Prototype. One
    definition of an anchor: the reader of bin/prototype-conformance."""
    prototypes = spec.get("prototypes") or []
    if not prototypes:
        return set()
    if not repo:
        raise Refusal(
            f"une ancre du Validated Prototype de la Spec {spec['id']} est citée et le dépôt du projet n'est pas donné "
            "(--repo) : la citation ne peut pas être vérifiée")
    reader = os.environ.get("PROTOTYPE_CONFORMANCE_BIN") or str(BIN / "prototype-conformance")
    names: set[str] = set()
    for reference in prototypes:
        argv = [reader, "anchors", "--repo", str(repo), "--commit", str(reference.get("commit")),
                "--path", str(reference.get("path")), "--branch", str(reference.get("branch")),
                "--states", ",".join(str(state) for state in reference.get("states") or [])]
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, stdin=subprocess.DEVNULL)
            answer = json.loads(proc.stdout)
        except (OSError, json.JSONDecodeError) as exc:
            raise Refusal(f"lecture des ancres du Validated Prototype impossible ({Path(reader).name} anchors) : {exc}") from exc
        if proc.returncode != 0 or not isinstance(answer, dict) or not isinstance(answer.get("anchors"), dict):
            raise Refusal(
                f"les ancres du Validated Prototype {reference.get('path')} de la Spec {spec['id']} sont illisibles : "
                f"{answer.get('error') if isinstance(answer, dict) else proc.stderr.strip()}")
        names.update(name for state in answer["anchors"].values() for name in state)
    return names


def outcome_target(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """The convoy an Outcome Evaluation write lands on, its tickets, its
    metadata and its Outcome Evaluation so far."""
    convoy, tickets = load_convoy(args.convoy)
    require_marked(convoy)
    metadata = metadata_of(convoy)
    record = outcome_evaluation_record(metadata[KEY_OUTCOME_EVALUATION]) if KEY_OUTCOME_EVALUATION in metadata \
        else {"rounds": []}
    return convoy, tickets, metadata, record


def handoff_findings(ticket: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    """The Ticket Handoff of a ticket of the convoy and its findings « hors
    ticket »; none for a ticket withdrawn from the graph."""
    metadata = metadata_of(ticket)
    if KEY_HANDOFF not in metadata or GATE_PREFIX + "withdrawn" in metadata:
        return None, []
    handoff = handoff_record(metadata[KEY_HANDOFF])
    content = handoff["sections"].get(FINDING_SECTION)
    return handoff, content if isinstance(content, list) else []


def unclassified_findings(tickets: list[dict[str, Any]]) -> list[str]:
    """Each finding « hors ticket » of the convoy the Evaluator of the end
    has not classified since the Handoff that declares it."""
    left = []
    for ticket in tickets:
        handoff, content = handoff_findings(ticket)
        metadata = metadata_of(ticket)
        known = {entry["item"] for entry in findings_record(metadata[KEY_FINDINGS])
                 if entry["handoff_at"] == handoff["at"]} if handoff and KEY_FINDINGS in metadata else set()
        left += [f"{ticket['id']}:{FINDING_SECTION}.{number}" for number in range(1, len(content) + 1)
                 if f"{FINDING_SECTION}.{number}" not in known]
    return left


def findings_to_repair(tickets: list[dict[str, Any]]) -> list[str]:
    """Each finding « hors ticket » of the convoy classified « repaired »
    whose `repair` the ticket-end gate has not closed: what the end of the
    Spec still refuses, beside the stories not observed."""
    by_id = {str(ticket.get("id")): ticket for ticket in tickets}
    left = []
    for ticket in tickets:
        handoff, content = handoff_findings(ticket)
        metadata = metadata_of(ticket)
        if not handoff or KEY_FINDINGS not in metadata:
            continue
        for entry in findings_record(metadata[KEY_FINDINGS]):
            number = int(entry["item"].rsplit(".", 1)[1])
            if entry["handoff_at"] != handoff["at"] or entry["classification"] != "repaired" or number > len(content):
                continue
            repair = by_id.get(str(entry.get("repair")))
            if repair is None or repair.get("status") != "closed" or GATE_PREFIX + GATE_TICKET_END not in metadata_of(repair):
                left.append(f"{ticket['id']}:{entry['item']}")
    return left


def check_citation(restores: dict[str, str], spec: dict[str, Any], what: str) -> None:
    """Spec §0 rule 6: a citation names something the Spec holds. A user
    story is one of its numbered ones; a line of the Spec is in its text."""
    if restores["kind"] == "user_story" and cited_story(restores) not in {str(story["number"]) for story in spec["stories"]}:
        raise Refusal(
            f"{what} cite une user story absente de la Spec {spec['id']} (restores.ref : « {restores['ref']} » ; attendu : "
            "le numéro d'une seule de ses user stories)")
    if restores["kind"] == "spec_line" and restores["ref"] not in " ".join(spec["text"].split()):
        raise Refusal(f"{what} cite une ligne absente de la Spec {spec['id']} (restores.ref : « {restores['ref']} »)")


def cmd_open_outcome_evaluation(args: argparse.Namespace) -> int:
    """Open the Outcome Evaluation of a convoy (T24, Spec §7, §9 point 4) at
    the commit the end-of-Spec gate rendered its mechanical verdicts on, on
    the products code launched from a clean copy of that commit. The user
    stories are read here, in the Spec: nobody hands them in. The same
    request again writes nothing; one at the same commit on other products
    keeps its launches."""
    convoy, tickets, metadata, record = outcome_target(args)
    commit = valid_commit(args.commit, "commit de l'Outcome Evaluation")
    gate = spec_end_record(metadata[KEY_SPEC_END]) if KEY_SPEC_END in metadata else None
    if gate is None or gate["commit"] != commit:
        raise Refusal(
            f"la porte de fin de Spec n'a pas rendu ses verdicts mécaniques au commit {commit} "
            f"({'aucun relevé' if gate is None else 'relevé au commit ' + gate['commit']}) : l'Outcome Evaluation porte "
            "sur le commit de la porte")
    if KEY_INTEGRATION_RED in metadata or any(ticket.get("status") != "closed" for ticket in tickets):
        raise Refusal(f"le convoi {args.convoy} a un ticket ouvert ou une branche d'intégration rouge : "
                      "l'Outcome Evaluation suit les verdicts mécaniques de fin de Spec")
    stop = record.get("stop")
    if stop and stop["commit"] == commit:
        raise Refusal(f"l'Outcome Evaluation du convoi {args.convoy} est arrêtée au commit {commit} ({stop['reason']})")
    given = json_argument(args.file, "demande d'Outcome Evaluation")
    unknown = sorted(set(given) - {"roles", "environment"})
    if unknown:
        raise Refusal(f"champs inconnus dans la demande d'Outcome Evaluation : {', '.join(unknown)}")
    roles = outcome_roles(given.get("roles"))
    environment = evaluation_environment(given.get("environment"), launched=True)
    last = record["rounds"][-1] if record["rounds"] else None
    if last and last["commit"] == commit and last["verdict"] is not None:
        raise Refusal(f"le convoi {args.convoy} a déjà son Outcome Evaluation au commit {commit} ({last['outcome']})")
    stories = spec_of(convoy)["stories"]
    request = record.get("request")
    wanted = {"commit": commit, "stories": stories}
    if request and {name: request[name] for name in wanted} == wanted:
        if request["roles"] == roles and request["environment"] == environment:
            return done(args.convoy, args.convoy, {})
        request.update(roles=roles, environment=environment)
    else:
        record["request"] = {**wanted, "roles": roles, "environment": environment, "launches": [], "at": now()}
    record.pop("stop", None)
    record["live"] = list(dict.fromkeys([entry["state_file"] for entry in environment] + record.get("live", [])))
    values = {KEY_OUTCOME_EVALUATION: encode(outcome_evaluation_record(encode(record)))}
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


def cmd_launch_outcome_evaluation(args: argparse.Namespace) -> int:
    """Record that an Evaluator session was sent the open Outcome
    Evaluation: the first launch, then one relaunch."""
    _, _, _, record = outcome_target(args)
    request = record.get("request")
    if not request:
        raise Refusal(f"aucune Outcome Evaluation n'est demandée sur {args.convoy} : rien à lancer")
    if not isinstance(args.bead, str) or not BEAD_ID_RE.match(args.bead):
        raise Refusal(f"bead d'évaluation absent ou mal formé : {args.bead!r}")
    if len(request["launches"]) >= EVALUATION_MAX_LAUNCHES:
        raise Refusal(
            f"une seule relance par évaluation : {args.convoy} en a déjà lancé {len(request['launches'])} sans résultat")
    request["launches"].append({"bead": args.bead, "at": now()})
    values = {KEY_OUTCOME_EVALUATION: encode(record)}
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


def cmd_classify_finding(args: argparse.Namespace) -> int:
    """The Evaluator of the end classifies one finding « hors ticket » of a
    Ticket Handoff (T24, Spec §0 rule 6, §9): `repaired`, with the citation
    of what it restores and the `repair` it drafts (`--file`), refused
    without them; `dismissed`, refused without its reason; `proposal`, kept
    for the operator. Only while an Outcome Evaluation is open; classified
    again while it is open, the last classification stands, unless code has
    already published its repair."""
    convoy, tickets, _, record = outcome_target(args)
    request = record.get("request")
    if not request:
        raise Refusal(f"aucune Outcome Evaluation n'est ouverte sur {args.convoy} : un constat hors ticket est classé "
                      "par l'Evaluator de fin, pendant son évaluation")
    ticket = marked_ticket_among(tickets, args.convoy, args.ticket)
    metadata = metadata_of(ticket)
    handoff, content = handoff_findings(ticket)
    if not isinstance(args.item, str) or not FINDING_ITEM_RE.match(args.item) or handoff is None \
            or int(args.item.split(".")[1]) > len(content):
        raise Refusal(f"le Ticket Handoff de {args.ticket} ne porte pas le constat hors ticket {args.item!r}")
    classification = one_of(args.classification, FINDING_CLASSES, "classement du constat hors ticket")
    entry: dict[str, Any] = {"item": args.item, "handoff_at": handoff["at"], "classification": classification,
                             "commit": request["commit"],
                             "recorded_by": single_line(args.recorded_by, "session de l'Evaluator"), "at": now()}
    if args.reason is not None:
        entry["reason"] = single_line(args.reason, "raison du classement")
    what = f"le constat {args.item} du ticket {args.ticket}"
    if classification == "dismissed" and "reason" not in entry:
        raise Refusal(f"{what} est écarté sans raison : un constat ne s'écarte qu'avec sa raison (--reason)")
    if classification == "repaired":
        given = json_argument(args.file, "repair rédigé") if args.file is not None else {}
        if not isinstance(given.get("restores"), dict):
            raise Refusal(
                f"{what} est classé « repaired » sans citation de ce qu'il rétablit : un classement « réparé » cite une user "
                f"story, une ancre, une ligne de la Spec, une règle écrite du dépôt ou un contrôle rouge (restores, dans --file)")
        entry["draft"] = repair_draft(given, f"le repair de {what}")
        check_citation(entry["draft"]["restores"], spec_of(convoy), f"le repair de {what}")
    elif args.file is not None:
        raise Refusal(f"{what} : un repair ne se rédige que pour un classement « repaired »")
    entries = [known for known in (findings_record(metadata[KEY_FINDINGS]) if KEY_FINDINGS in metadata else [])
               if known["handoff_at"] == handoff["at"]]
    known = next((other for other in entries if other["item"] == args.item), None)
    if known and "repair" in known:
        raise Refusal(f"{what} a déjà son repair publié ({known['repair']}) : son classement ne change plus")
    entries = [other for other in entries if other["item"] != args.item] + [entry]
    entries.sort(key=lambda other: int(other["item"].split(".")[1]))
    values = {KEY_FINDINGS: encode({"entries": findings_record(encode({"entries": entries}))})}
    write_metadata(args.ticket, values)
    return done(args.convoy, args.ticket, values)


def given_notes(given: Any, name: str, metadata: dict[str, Any], commit: str, problems: list[str]) -> Any:
    """A non-blocking section as it is stored; what is wrong with it goes to `problems`."""
    if given == HANDOFF_NOTHING:
        return given
    if not isinstance(given, list) or not given:
        problems.append(f"rubrique {name} absente : ni contenu ni « {HANDOFF_NOTHING} »")
        return HANDOFF_NOTHING
    stored = []
    for note in given:
        note = {"text": note} if isinstance(note, str) else note
        text = " ".join(str(note.get("text") or "").split())[:MAX_FINDING_LINE] if isinstance(note, dict) else ""
        if not text or set(note) - {"text", "evidence"}:
            problems.append(f"rubrique {name} : élément mal formé : {note!r} (attendu : text, et evidence en option)")
            continue
        entry = {"text": text}
        if "evidence" in note:
            refusal = evidence_at(metadata, note["evidence"], commit)
            if refusal:
                problems.append(f"rubrique {name} : {refusal}")
                continue
            entry["evidence"] = note["evidence"]
        stored.append(entry)
    return stored or HANDOFF_NOTHING


def contradictions_of(stories: list[dict[str, Any]], tickets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Spec §10 rubric 8, user story 63: a story « non observée » on the
    assembled product while every ticket that covers it had all its
    criteria « observés » by its Ticket Evaluation contradicts a ticket's
    proof. Written by code, never by the Evaluator."""
    found = []
    for story in stories:
        if story["state"] != "not_observed":
            continue
        covering = []
        for ticket in tickets:
            metadata = metadata_of(ticket)
            if GATE_PREFIX + "withdrawn" in metadata or KEY_USER_STORIES not in metadata \
                    or str(story["number"]) not in stored_user_stories(metadata[KEY_USER_STORIES]):
                continue
            rounds = evaluation_record(metadata[KEY_EVALUATION])["rounds"] if KEY_EVALUATION in metadata else []
            last = rounds[-1] if rounds else None
            observed = last is not None and last["kind"] == "evaluation" and last["outcome"] == "favorable"
            covering.append((ticket["id"], last if observed else None))
        if covering and all(last is not None for _, last in covering):
            found.append({"story": story["number"],
                          "tickets": [{"id": ticket_id, "commit": last["commit"], "at": last["at"]}
                                      for ticket_id, last in covering]})
    return found


def cmd_record_outcome_evaluation(args: argparse.Namespace) -> int:
    """Record what the Evaluator of the end hands in for the open Outcome
    Evaluation, and compute the verdict (T24, Spec §7): one state per
    numbered user story of the Spec, each with a piece captured at the
    commit of the gate; the free exploration and the list of fidelity
    deviations, which change nothing to the verdict; one drafted `repair`
    per story « non observée », that cites it. Refused while a finding
    « hors ticket » is left unclassified. A story « non observée » whose
    covering tickets were all « observés » is written as a contradiction."""
    convoy, tickets, metadata, record = outcome_target(args)
    request = record.get("request")
    if not request:
        raise Refusal(f"aucune Outcome Evaluation n'est demandée sur {args.convoy} : des états répondent à une demande ouverte")
    commit = request["commit"]
    given = json_argument(args.file, "Outcome Evaluation")
    problems = [
        "le verdict est calculé par du code, jamais donné par l'Evaluator" if name in ("verdict", "outcome")
        else "une contradiction est inscrite par du code, jamais rendue par l'Evaluator" if name == "contradictions"
        else f"champ inconnu : {name}"
        for name in sorted(set(given) - {"commit", "stories", "repairs", "recorded_by", *OUTCOME_SECTIONS})]
    if given.get("commit") != commit:
        problems.append(f"l'évaluation rendue porte sur le commit {given.get('commit')!r}, la porte de fin de Spec sur {commit}")
    recorded_by = given.get("recorded_by")
    if not isinstance(recorded_by, str) or not recorded_by.strip() or "\n" in recorded_by:
        problems.append(f"session de l'Evaluator absente ou mal formée : {recorded_by!r}")
    spec = spec_of(convoy)
    if spec["stories"] != request["stories"]:
        problems.append("les user stories de la Spec ne sont plus celles de la demande d'évaluation : elles sont gelées "
                        "avec la Spec approuvée")
    handed = given.get("stories")
    if not isinstance(handed, list):
        problems.append("stories mal formé : une liste d'états, un par user story numérotée, est attendue")
        handed = []
    wanted = {story["number"]: story["text"] for story in request["stories"]}
    by_number: dict[Any, Any] = {}
    for item in handed:
        number = item.get("number") if isinstance(item, dict) else None
        if isinstance(number, bool) or number not in wanted:
            problems.append(f"état rendu pour une user story que la Spec n'a pas : {number!r}")
        elif number in by_number:
            problems.append(f"user story {number} : deux états rendus")
        else:
            by_number[number] = item
    stories = []
    for number, text in wanted.items():
        if number not in by_number:
            problems.append(f"user story {number} sans état : aucun état rendu pour « {text} »")
            continue
        stories.append({"number": number, **given_state(by_number[number], f"user story {number}", text, metadata, commit,
                                                        problems)})
    notes = {name: given_notes(given.get(name), name, metadata, commit, problems) for name in OUTCOME_SECTIONS}
    drafts = given.get("repairs", [])
    if not isinstance(drafts, list):
        problems.append("repairs mal formé : une liste de repairs rédigés est attendue")
        drafts = []
    repairs: dict[int, dict[str, Any]] = {}
    not_observed = [story["number"] for story in stories if story["state"] == "not_observed"]
    for draft in drafts:
        number = draft.get("story") if isinstance(draft, dict) else None
        try:
            if number not in not_observed or number in repairs:
                raise Refusal(f"repair rédigé pour {number!r} : un repair se rédige une fois, pour une user story rendue "
                              "« not_observed »")
            body = repair_draft({key: value for key, value in draft.items() if key != "story"},
                                f"le repair de la user story {number}")
            if cited_story(body["restores"]) != str(number):
                raise Refusal(f"le repair rédigé pour la user story {number} ne la cite pas (restores : {body['restores']!r} ; "
                              f"attendu : kind user_story, et ref qui porte son seul numéro)")
            repairs[number] = body
        except Refusal as exc:
            problems.append(str(exc))
    problems += [f"user story {number} « not_observed » sans repair rédigé qui la cite" for number in not_observed
                 if number not in repairs and not any(isinstance(d, dict) and d.get("story") == number for d in drafts)]
    left = unclassified_findings(tickets)
    if left:
        problems.append(f"constat(s) hors ticket non classé(s) : {', '.join(left)} ; chaque constat est classé avant que "
                        "l'évaluation soit rendue")
    if problems:
        raise Refusal("Outcome Evaluation hors contrat : " + " ; ".join(problems))
    round_: dict[str, Any] = {
        "commit": commit, "stories": stories, **notes,
        "repairs": [{"story": number, "draft": repairs[number]} for number in not_observed],
        "contradictions": contradictions_of(stories, tickets), "roles": request["roles"],
        "environment": [{"dataset": entry["dataset"], "address": entry["address"]} for entry in request["environment"]],
        "recorded_by": recorded_by.strip(), "at": now()}
    round_["outcome"] = outcome_of_stories(stories)
    round_["verdict"] = verdict_of_outcome(round_["outcome"])
    record["rounds"].append(outcome_round(round_))
    del record["request"]
    values: dict[str, Any] = {KEY_OUTCOME_EVALUATION: encode(record)}
    to_repair = findings_to_repair(tickets)
    if not_observed or to_repair:
        # A tip the Evaluator of the end refuses counts one round of the
        # end, in the same write, or stops the rounds (T26, Spec §8).
        named = [f"user story {number} non observée" for number in not_observed] + [
            f"constat hors ticket {finding} à réparer" for finding in to_repair]
        values.update(end_refusal_values(
            metadata, commit, OUTCOME_SOURCE, round_["at"],
            f"{' ; '.join(named)}, sur le produit assemblé au commit {commit[:12]}", not_observed=sorted(not_observed)))
    write_metadata(args.convoy, values)
    print(json.dumps({"ok": True, "convoy": args.convoy, "bead": args.convoy, "outcome": round_["outcome"],
                      "verdict": round_["verdict"], "state": outcome_state(record), "written": values},
                     indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def cmd_release_outcome_evaluation(args: argparse.Namespace) -> int:
    """Record that the launched products of an Outcome Evaluation were
    stopped by code (`--state-file`, repeatable). A product an open
    evaluation still runs on is not released, unless the evaluation is
    withdrawn with it (`--withdraw`: the commit of the gate moved, nothing
    can be observed there any more)."""
    _, _, _, record = outcome_target(args)
    live = record.get("live", [])
    if not args.state_file:
        raise Refusal("relevé de lancement absent : --state-file nomme chaque produit arrêté")
    unknown = [path for path in args.state_file if path not in live]
    if unknown:
        raise Refusal(f"produit lancé inconnu de l'Outcome Evaluation de {args.convoy} : {', '.join(unknown)}")
    used = {entry["state_file"] for entry in (record.get("request") or {}).get("environment", [])}
    held = [path for path in args.state_file if path in used]
    if held and args.withdraw:
        del record["request"]
    elif held:
        raise Refusal(f"une Outcome Evaluation est ouverte sur ce produit lancé : il ne se libère pas ({', '.join(held)})")
    left = [path for path in live if path not in args.state_file]
    record.pop("live", None)
    if left:
        record["live"] = left
    values = {KEY_OUTCOME_EVALUATION: encode(record)}
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


def cmd_stop_outcome_evaluation(args: argparse.Namespace) -> int:
    """Record that the Outcome Evaluation of a convoy does not go on at a
    commit (`--reason`, `--detail`): it gave no result, relaunch included,
    its environment failed twice, or a story cannot be observed. The open
    request ends with it. `--raised` records that the escalation door put it
    on the operator's list. A gate that renders its verdicts on another
    commit starts a new evaluation."""
    _, _, _, record = outcome_target(args)
    stop = record.get("stop")
    if args.raised:
        if not stop:
            raise Refusal(f"l'Outcome Evaluation du convoi {args.convoy} n'est pas arrêtée : aucune remontée à noter")
        if "raised" in stop:
            return done(args.convoy, args.convoy, {})
        stop["raised"] = now()
    else:
        commit = valid_commit(args.commit, "commit de l'arrêt")
        if stop and stop["commit"] == commit:
            raise Refusal(f"l'Outcome Evaluation du convoi {args.convoy} est déjà arrêtée au commit {commit}")
        record["stop"] = {"reason": one_of(args.reason, OUTCOME_STOPS, "raison d'arrêt de l'Outcome Evaluation"),
                          "detail": single_line(args.detail, "précision de l'arrêt"), "commit": commit, "at": now()}
        record.pop("request", None)
    values = {KEY_OUTCOME_EVALUATION: encode(outcome_evaluation_record(encode(record)))}
    write_metadata(args.convoy, values)
    return done(args.convoy, args.convoy, values)


def cmd_set_outcome_repair(args: argparse.Namespace) -> int:
    """Name the `repair` code published through the patch door
    (bin/convoy-advance) for what the Evaluator of the end drafted: the one
    of a story « non observée » of the last Outcome Evaluation (`--story`),
    or the one of a finding « hors ticket » classified « repaired »
    (`--ticket`, `--item`). Nothing here says a finding is repaired: `show`
    reads it once the ticket-end gate has closed that repair."""
    _, tickets, _, record = outcome_target(args)
    repair = marked_ticket_among(tickets, args.convoy, args.repair)
    if metadata_of(repair).get(KEY_KIND) != "repair":
        raise Refusal(f"le ticket {args.repair} n'est pas un repair")
    if (args.story is None) == (args.ticket is None and args.item is None):
        raise Refusal("--story, ou --ticket et --item : un repair publié se rattache à une user story ou à un constat hors ticket")
    if args.story is not None:
        last = record["rounds"][-1] if record["rounds"] else {"repairs": []}
        entry = next((entry for entry in last["repairs"] if str(entry["story"]) == str(args.story)), None)
        if entry is None:
            raise Refusal(f"la dernière Outcome Evaluation de {args.convoy} n'a rédigé aucun repair pour la user story {args.story}")
        target, values_of = args.convoy, lambda: {KEY_OUTCOME_EVALUATION: encode(outcome_evaluation_record(encode(record)))}
        what = f"la user story {args.story}"
    else:
        ticket = marked_ticket_among(tickets, args.convoy, args.ticket)
        entries = findings_record(metadata_of(ticket)[KEY_FINDINGS]) if KEY_FINDINGS in metadata_of(ticket) else []
        entry = next((entry for entry in entries if entry["item"] == args.item and entry["classification"] == "repaired"), None)
        if entry is None:
            raise Refusal(f"le constat {args.item!r} du ticket {args.ticket} n'est pas classé « repaired » : aucun repair ne s'y rattache")
        target, values_of = args.ticket, lambda: {KEY_FINDINGS: encode({"entries": findings_record(encode({"entries": entries}))})}
        what = f"le constat {args.item} du ticket {args.ticket}"
    if entry.get("repair") == args.repair:
        return done(args.convoy, target, {})
    if "repair" in entry:
        raise Refusal(f"{what} a déjà son repair ({entry['repair']}) : un seul repair par élément")
    entry["repair"] = args.repair
    values = values_of()
    write_metadata(target, values)
    return done(args.convoy, target, values)


# --- command line ------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=PROGRAM, description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def command(name: str, handler: Any, ticket: bool = True) -> argparse.ArgumentParser:
        p = sub.add_parser(name)
        p.add_argument("convoy")
        if ticket:
            p.add_argument("ticket")
        p.set_defaults(handler=handler)
        return p

    # Closed lists and required values are checked by the handlers, not by
    # argparse: a refusal is one JSON answer, and it is made under the lock,
    # after the mark has been read.
    sub.add_parser("list").set_defaults(handler=cmd_list)
    p = command("show", cmd_show, ticket=False)
    p.add_argument("--repo", default=".")
    p = command("mark", cmd_mark, ticket=False)
    p.add_argument("--demonstration-line", action="append", default=[])
    p.add_argument("--user-stories", action="append", default=[])
    p.add_argument("--establishes-launch-recipe", action="append", default=[])
    p.add_argument("--prototype-fold", action="append", default=[])
    command("set-branch", cmd_set_branch).add_argument("--branch")
    command("set-session", cmd_set_session).add_argument("--session")
    command("set-exit", cmd_set_exit).add_argument("--exit")
    p = command("set-verdict", cmd_set_verdict)
    p.add_argument("--kind")
    p.add_argument("--state")
    p.add_argument("--commit")
    p = command("set-counter", cmd_set_counter, ticket=False)
    p.add_argument("--ticket")
    p.add_argument("--counter")
    p.add_argument("--value")
    p = command("bump-counter", cmd_bump_counter, ticket=False)
    p.add_argument("--ticket")
    p.add_argument("--counter", action="append", default=[])
    p = command("add-evidence", cmd_add_evidence)
    p.add_argument("--piece")
    p.add_argument("--digest")
    p.add_argument("--commit")
    p = command("record-gate", cmd_record_gate)
    p.add_argument("--gate")
    p.add_argument("--commit")
    p = command("close-ticket", cmd_close_ticket)
    p.add_argument("--commit")
    p.add_argument("--file")
    p = command("set-tdd", cmd_set_tdd)
    p.add_argument("--step")
    p.add_argument("--commit")
    p.add_argument("--base")
    p.add_argument("--reason")
    p = command("stop-ticket", cmd_stop_ticket)
    p.add_argument("--reason")
    p.add_argument("--detail")
    command("stop-raised", cmd_stop_raised)
    p = command("open-test-review", cmd_open_test_review)
    p.add_argument("--commit")
    p.add_argument("--file")
    command("launch-test-review", cmd_launch_test_review).add_argument("--bead")
    command("record-test-review", cmd_record_test_review).add_argument("--file")
    command("set-handoff", cmd_set_handoff).add_argument("--file")
    p = command("set-model", cmd_set_model)
    p.add_argument("--role")
    p.add_argument("--agent")
    p.add_argument("--provider")
    p.add_argument("--model")
    p = command("open-code-review", cmd_open_code_review)
    p.add_argument("--kind")
    p.add_argument("--commit")
    p.add_argument("--base")
    p.add_argument("--file")
    command("launch-code-review", cmd_launch_code_review).add_argument("--bead")
    command("record-code-review", cmd_record_code_review).add_argument("--file")
    command("respond-code-review", cmd_respond_code_review).add_argument("--file")
    p = command("open-evaluation", cmd_open_evaluation)
    p.add_argument("--commit")
    p.add_argument("--file")
    command("launch-evaluation", cmd_launch_evaluation).add_argument("--bead")
    command("record-evaluation", cmd_record_evaluation).add_argument("--file")
    p = command("record-startup", cmd_record_startup)
    p.add_argument("--commit")
    p.add_argument("--piece")
    p.add_argument("--detail")
    p.add_argument("--file")
    p = command("release-evaluation", cmd_release_evaluation)
    p.add_argument("--state-file", action="append", default=[])
    p.add_argument("--withdraw", action="store_true")
    p = command("park", cmd_park)
    p.add_argument("--cause")
    p.add_argument("--detail")
    p = command("lift-park", cmd_lift_park)
    p.add_argument("--request")
    p.add_argument("--option")
    p = command("open-resume", cmd_open_resume)
    p.add_argument("--cause")
    p.add_argument("--ref")
    command("launch-resume", cmd_launch_resume).add_argument("--bead")
    p = command("set-fidelity", cmd_set_fidelity)
    p.add_argument("--commit")
    p.add_argument("--piece")
    p.add_argument("--file")
    p = command("raise-planning-exception", cmd_raise_planning_exception)
    p.add_argument("--kind")
    p.add_argument("--summary")
    p.add_argument("--anchor", action="append", default=[])
    p.add_argument("--item", action="append", default=[])
    p.add_argument("--accept-option")
    command("set-item-repair", cmd_set_item_repair).add_argument("--repair")
    command("record-blocking-red", cmd_record_blocking_red).add_argument("--control")
    command("clear-blocking-red", cmd_clear_blocking_red)
    p = command("set-integration", cmd_set_integration, ticket=False)
    p.add_argument("--branch")
    p.add_argument("--protected")
    p.add_argument("--base")
    p = command("set-merge", cmd_set_merge)
    p.add_argument("--outcome")
    p.add_argument("--ticket-commit")
    p.add_argument("--integration")
    p.add_argument("--commit")
    p = command("invalidate-verdicts", cmd_invalidate_verdicts)
    p.add_argument("--tip")
    p.add_argument("--kind", action="append", default=[])
    command("open-correction", cmd_open_correction).add_argument("--commit")
    command("launch-correction", cmd_launch_correction).add_argument("--bead")
    p = command("override-finding", cmd_override_finding)
    p.add_argument("--finding")
    p.add_argument("--approver")
    p.add_argument("--words")
    p = command("record-incident", cmd_record_incident, ticket=False)
    p.add_argument("--bead")
    p.add_argument("--signature")
    command("clear-incident", cmd_clear_incident, ticket=False)
    p = command("record-grouped-request", cmd_record_grouped_request, ticket=False)
    p.add_argument("--bead")
    p.add_argument("--signature")
    p.add_argument("--lift-option")
    p.add_argument("--lifts", action="append", default=[])
    command("clear-grouped-request", cmd_clear_grouped_request, ticket=False)
    p = command("record-integration-red", cmd_record_integration_red, ticket=False)
    p.add_argument("--commit")
    p.add_argument("--integration")
    p.add_argument("--protected")
    p.add_argument("--control")
    p.add_argument("--detail")
    p.add_argument("--check")
    p.add_argument("--end-round", action="store_true")
    p = command("record-spec-end", cmd_record_spec_end, ticket=False)
    p.add_argument("--commit")
    p.add_argument("--protected")
    p.add_argument("--file")
    p = command("record-evidence-pack", cmd_record_evidence_pack, ticket=False)
    p.add_argument("--commit")
    p.add_argument("--digest")
    p.add_argument("--path")
    p.add_argument("--conforming", dest="conforming", action="store_true", default=None)
    p.add_argument("--non-conforming", dest="conforming", action="store_false")
    p.add_argument("--inadmissible", default=0)
    p = command("open-outcome-evaluation", cmd_open_outcome_evaluation, ticket=False)
    p.add_argument("--commit")
    p.add_argument("--file")
    command("launch-outcome-evaluation", cmd_launch_outcome_evaluation, ticket=False).add_argument("--bead")
    command("record-outcome-evaluation", cmd_record_outcome_evaluation, ticket=False).add_argument("--file")
    p = command("release-outcome-evaluation", cmd_release_outcome_evaluation, ticket=False)
    p.add_argument("--state-file", action="append", default=[])
    p.add_argument("--withdraw", action="store_true")
    p = command("stop-outcome-evaluation", cmd_stop_outcome_evaluation, ticket=False)
    p.add_argument("--commit")
    p.add_argument("--reason")
    p.add_argument("--detail")
    p.add_argument("--raised", action="store_true")
    p = command("classify-finding", cmd_classify_finding)
    p.add_argument("--item")
    p.add_argument("--as", dest="classification")
    p.add_argument("--reason")
    p.add_argument("--file")
    p.add_argument("--recorded-by")
    p = command("set-outcome-repair", cmd_set_outcome_repair, ticket=False)
    p.add_argument("--repair")
    p.add_argument("--story")
    p.add_argument("--ticket")
    p.add_argument("--item")
    command("set-integration-repair", cmd_set_integration_repair, ticket=False).add_argument("--ticket")
    p = command("open-end-review", cmd_open_end_review, ticket=False)
    p.add_argument("--commit")
    p.add_argument("--file")
    command("launch-end-review", cmd_launch_end_review, ticket=False).add_argument("--bead")
    command("record-end-review", cmd_record_end_review, ticket=False).add_argument("--file")
    p = command("set-end-review-repair", cmd_set_end_review_repair, ticket=False)
    p.add_argument("--finding")
    p.add_argument("--ticket")
    p.add_argument("--refused")
    p = command("stop-end-review", cmd_stop_end_review, ticket=False)
    p.add_argument("--reason")
    p.add_argument("--detail")
    command("end-review-stop-raised", cmd_end_review_stop_raised, ticket=False).add_argument("--bead")
    command("end-stop-raised", cmd_end_stop_raised, ticket=False).add_argument("--bead")
    p = command("record-delivered", cmd_record_delivered, ticket=False)
    p.add_argument("--commit")
    p.add_argument("--pack-digest")
    command("acceptance-requested", cmd_acceptance_requested, ticket=False).add_argument("--bead")
    p = command("acceptance-launch-failed", cmd_acceptance_launch_failed, ticket=False)
    p.add_argument("--commit")
    p.add_argument("--detail")
    command("set-acceptance-repair", cmd_set_acceptance_repair, ticket=False).add_argument("--ticket")
    p = command("record-proposition-verdict", cmd_record_proposition_verdict, ticket=False)
    p.add_argument("--proposition")
    p.add_argument("--verdict")
    p.add_argument("--approver")
    p.add_argument("--words")
    p = command("set-verdict-proposal", cmd_set_verdict_proposal, ticket=False)
    p.add_argument("--proposition")
    p.add_argument("--bead")
    p = command("record-owner-answer", cmd_record_owner_answer, ticket=False)
    p.add_argument("--response")
    p.add_argument("--approver")
    p.add_argument("--words")
    p.add_argument("--commit")
    p.add_argument("--pack-digest")
    p.add_argument("--file")
    p.add_argument("--reason")
    p.add_argument("--repo")
    p = command("record-promotion", cmd_record_promotion, ticket=False)
    p.add_argument("--judged")
    p.add_argument("--merged")
    p.add_argument("--protected")
    p.add_argument("--tip")
    command("void-acceptance", cmd_void_acceptance, ticket=False).add_argument("--cause")
    command("close-convoy", cmd_close_convoy, ticket=False)
    p = command("set-owner-repair", cmd_set_owner_repair, ticket=False)
    p.add_argument("--finding")
    p.add_argument("--ticket")
    p = command("set-owner-proposal", cmd_set_owner_proposal, ticket=False)
    p.add_argument("--finding")
    p.add_argument("--bead")
    p = command("resolve-owner-exception", cmd_resolve_owner_exception, ticket=False)
    p.add_argument("--approver")
    p.add_argument("--words")
    command("clear-integration-red", cmd_clear_integration_red, ticket=False)
    p = sub.add_parser("ticket")
    p.add_argument("ticket")
    p.add_argument("--bead-json")
    p.set_defaults(handler=cmd_ticket)
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.handler in (cmd_list, cmd_show, cmd_ticket):
            return args.handler(args)
        with convoy_lock(args.convoy):
            return args.handler(args)
    except NotNewFlow as exc:
        print(json.dumps({
            "ok": False, "new_flow": False, "convoy": str(exc),
            "message": f"{exc} : {NOT_NEW_FLOW} ; rien n'est écrit",
        }, indent=2, sort_keys=True, ensure_ascii=False))
        return EXIT_NOT_NEW_FLOW
    except Refusal as exc:
        print(json.dumps({"ok": False, "error": f"refus : {exc}"}, indent=2, sort_keys=True, ensure_ascii=False))
        return EXIT_REFUSED


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
