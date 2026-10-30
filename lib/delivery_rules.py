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


def evaluation_proven_by_test(round_: dict, previous_rounds: list[dict], lifts: list[dict]) -> list[str]:
    """Items the current evaluation may count proven by their criterion test.

    The immediately preceding evaluation must have raised the Planning
    Exception at the same commit, and the answered lift must carry the exact
    item and text between that refusal and this round.
    """
    previous = next((entry for entry in reversed(previous_rounds)
                     if entry.get("kind", "evaluation") == "evaluation"), None)
    if not previous or previous.get("outcome") != "planning_exception" \
            or previous.get("commit") != round_.get("commit"):
        return []

    def items(entry):
        named = [(f"critère {item.get('number')}", item) for item in entry.get("criteria", [])]
        return named + [("ligne de démonstration", entry.get("demonstration_line") or {})]

    before = dict(items(previous))
    valid = []
    for name, item in items(round_):
        source = before.get(name) or {}
        exact = {"what": name, "text": item.get("text")}
        if (item.get("state"), item.get("cause")) != ("unobservable", "criterion") \
                or (source.get("state"), source.get("cause"), source.get("text")) != (
                    "unobservable", "criterion", item.get("text")):
            continue
        if any(lift.get("cause") == "planning_exception"
               and lift.get("option") == PROVEN_BY_TEST_OPTION
               and previous.get("at", "") <= lift.get("parked_at", "") <= lift.get("at", "") <= round_.get("at", "")
               and exact in lift.get("proven_by_test", []) for lift in lifts):
            valid.append(name)
    return valid
