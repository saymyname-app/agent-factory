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
