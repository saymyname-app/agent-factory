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
