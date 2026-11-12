"""Rules shared by delivery-flow writers and readers."""

from __future__ import annotations

import re


TDD_EVIDENCE_PIECES = {
    "red": "tdd_red",
    "freeze": "tdd_freeze",
    "green": "tdd_green",
    "amendment": "tdd_amendment",
    "prefactoring": "tdd_prefactoring",
}

# The answer to an evaluation's Planning Exception that judges its
# unobservable item proven by the frozen criterion test.
PROVEN_BY_TEST_OPTION = "a"
# The option of that request that has it evaluated again on the products
# launched again, judging nothing proven (af-npz9v1.38). Benjamin, 28/10/2026
# 01:20 Paris, relayed from the central chat: « Oui aux deux recommandations : fais ajouter puis utiliser l’option de réévaluation réelle pour les trois tickets, et accorde le tour de correction exceptionnel. Coordonne tout et vérifie que ça repart. »
REEVALUATE_OPTION = "c"
# The stops the Ticket Evaluation of a ticket writes (bin/convoy-state).
EVALUATION_STOPS = ("evaluation_no_result", "evaluation_outage")

# The written rules of how a test is written: a repair that restores one of
# them moves a proof, it changes no behavior (af-oa2ci4).
TEST_RULE_PATHS = ("docs/TEST_GUIDELINE.md",)


def moves_a_proof(ticket: dict) -> bool:
    """Whether a ticket, as bin/convoy-state shows it, is a repair whose
    Blocking Finding is about where or how a proof is written -- it restores
    a rule of TEST_RULE_PATHS -- and not about a behavior. Its criteria can
    hold at the start commit: the black-box proof replaces the one the rule
    forbids (af-oa2ci4)."""
    restores = ticket.get("restores") or {}
    if ticket.get("kind") != "repair" or restores.get("kind") != "repo_rule":
        return False
    path, separator, _ = str(restores.get("ref") or "").partition(" : ")
    return bool(separator) and path.strip() in TEST_RULE_PATHS


# bin/tdd-step red runs a criterion test that passes at the start commit
# again, up to the profile's k runs, and calls it green only if it passed at
# each one: a single lucky pass of a test red 7 times out of 8 had stopped
# R23 (af-ujme6p) « déjà vert » (af-batj8g). The detail of the stop it
# writes says so with these words; a stop without them was decided on one
# run, and bin/convoy-advance resumes it once (cause red_replayed).
GREEN_AT_EVERY_RUN = "à chacune de ses"


def green_seen_once(stop: dict) -> bool:
    """Whether a ticket's stop is an all-green stop written by a red that
    ran each test once, before the replay above (af-batj8g)."""
    return stop.get("reason") == "criterion_already_green" \
        and GREEN_AT_EVERY_RUN not in str(stop.get("detail") or "")


def answer_lifts_planning_exception(ticket: dict) -> bool:
    """Whether the operator's answer to the Planning Exception that parks a
    ticket, as bin/convoy-state shows it, lifts that parking: the last one a
    Ticket Exit raised is accepted, or the one the Ticket Evaluation of a
    finished ticket raised (no entry under `planning_exceptions`, Benjamin,
    21/10/2026, af-ten1sp) is answered proven by its test or evaluated
    again. Any other answer leaves the question to the Planning Run: the
    ticket stays parked until Benjamin decides there (af-hnh16e)."""
    answer = (ticket.get("park") or {}).get("answer") or {}
    exceptions = ticket.get("planning_exceptions") or []
    accepted = bool(exceptions) and isinstance(exceptions, list) and bool(exceptions[-1].get("accepted"))
    evaluated = ((ticket.get("exit") or {}).get("exit") == "finished"
                 and ((ticket.get("evaluation") or {}).get("state") or {}).get("outcome") == "planning_exception")
    return accepted or (evaluated and answer.get("option") in (PROVEN_BY_TEST_OPTION, REEVALUATE_OPTION))


def technical_repairs(ticket: dict) -> list[str]:
    """The Factory-maintenance links bound to the ticket's current request,
    as bin/convoy-state shows it: its parking by its own operator request,
    or its evaluation stop."""
    record = ticket.get("technical_repairs")
    park, exit_record = ticket.get("park") or {}, ticket.get("exit") or {}
    stop = ticket.get("stop") or {}
    if not isinstance(record, dict):
        return []
    current_parking = park.get("cause") == "operator_request" and exit_record.get("exit") == "operator_request" \
        and record.get("parked_at") == park.get("at") and record.get("exit_at") == exit_record.get("at")
    current_stop = stop.get("reason") in EVALUATION_STOPS and record.get("stop_at") == stop.get("at")
    if not current_parking and not current_stop:
        return []
    entries = record.get("entries")
    return [entry["id"] for entry in entries] if isinstance(entries, list) else []


def review_replay_due(last: dict, tip: str, correction_commit: str | None,
                      unsettled, overridden) -> bool:
    """Whether an unfavorable review is replaced by a full review at a later tip."""
    if last["commit"] == tip:
        return False
    if last["kind"] == "review":
        return not last.get("responses") and correction_commit is None
    return correction_commit == last["commit"] or set(unsettled) <= set(overridden)


def tdd_evidence_piece(tdd: dict, step: str) -> str:
    """The sealed piece that proves a TDD step, including an amended red."""
    amendment = tdd.get("amendment") or {}
    if (step == "red" and amendment.get("commit")
            and amendment.get("commit") == (tdd.get("red") or {}).get("commit")):
        return TDD_EVIDENCE_PIECES["amendment"]
    return TDD_EVIDENCE_PIECES[step]


def names_in_texts(candidates, texts) -> list[str]:
    """Candidates named as whole identifiers in any of the given texts."""
    texts = list(texts)
    return [name for name in candidates
            if any(re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", text) for text in texts)]


def evaluation_proven_by_test(round_: dict, previous_rounds: list[dict], lifts: list[dict],
                              green_commit: str | None = None) -> list[str]:
    """Items the current evaluation may count proven by their criterion test.

    The answered lift must carry the exact item and text of the latest
    Planning Exception. At a later commit, the frozen criterion tests must
    be green again at that exact commit; a historical verdict alone is not
    proof of the new tip.
    """
    evaluations = [entry for entry in previous_rounds if entry.get("kind", "evaluation") == "evaluation"]
    previous = evaluations[-1] if evaluations else None
    if previous and previous.get("outcome") == "planning_exception" \
            and previous.get("commit") == round_.get("commit"):
        source_round = previous
    elif green_commit == round_.get("commit"):
        source_round = next((entry for entry in reversed(evaluations)
                             if entry.get("outcome") == "planning_exception"), None)
    else:
        source_round = None
    if source_round is None:
        return []

    def items(entry):
        named = [(f"critère {item.get('number')}", item) for item in entry.get("criteria", [])]
        return named + [("ligne de démonstration", entry.get("demonstration_line") or {})]

    before = dict(items(source_round))
    valid = []
    for name, item in items(round_):
        source_item = before.get(name) or {}
        exact = {"what": name, "text": item.get("text")}
        if (item.get("state"), item.get("cause")) != ("unobservable", "criterion") \
                or (source_item.get("state"), source_item.get("cause"), source_item.get("text")) != (
                    "unobservable", "criterion", item.get("text")):
            continue
        if any(lift.get("cause") == "planning_exception"
               and lift.get("option") == PROVEN_BY_TEST_OPTION
               and source_round.get("at", "") <= lift.get("parked_at", "") <= lift.get("at", "") <= round_.get("at", "")
               and exact in lift.get("proven_by_test", []) for lift in lifts):
            valid.append(name)
    return valid
