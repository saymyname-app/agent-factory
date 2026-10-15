"""Project-specific, approved simple expectations for Evaluator briefs.

The Factory profile is outside the author's worktree. Each entry cites the
validated source and the frozen criterion/story it clarifies. This module
does not infer expectations from prose or the author's diff.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")


def planned(profile: dict[str, Any], scope: str, subjects: list[dict[str, Any]],
            datasets: list[str], commit: str, owner: str | None = None) -> list[dict[str, Any]]:
    """Resolve only entries naming an exact frozen subject; keep gaps visible.

    A project may have no typed comparisons. Once it declares one for a
    subject, malformed, missing and contradictory expectations remain in the
    brief as planning gaps and cannot be silently waived by an Evaluator.
    """
    raw = profile.get("validated_expectations", [])
    if not isinstance(raw, list):
        return [{"number": item["number"], "commit": commit,
                 "gap": "validated_expectations is not a list"} for item in subjects]
    by_number = {item["number"]: item["text"] for item in subjects}
    result: list[dict[str, Any]] = []
    seen: dict[tuple[int, str, str], Any] = {}
    for index, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            result.extend({"id": index, "number": subject["number"], "commit": commit,
                           "gap": "validated expectation is not an object"} for subject in subjects)
            continue
        if item.get("scope") != scope:
            if item.get("scope") not in ("ticket", "outcome") and item.get("owner") in (None, owner) and item.get("number") in by_number:
                result.append({"id": index, "number": item["number"], "commit": commit,
                               "gap": "validated expectation has no known scope"})
            continue
        if item.get("owner") not in (None, owner):
            continue
        number, text, dataset = item.get("number"), item.get("text"), item.get("dataset")
        if isinstance(number, bool) or number not in by_number or by_number[number] != text:
            # Numbers are local to a ticket/Spec. A mismatch is a planning
            # gap only when the entry names this exact owner.
            if item.get("owner") != owner or number not in by_number:
                continue
            result.append({"id": index, "number": number, "dataset": dataset,
                           "commit": commit, "gap": "source does not name the frozen criterion"})
            continue
        entry = {"id": index, "number": number, "text": text, "dataset": dataset,
                 "commit": commit, "source": item.get("source"), "expected": item.get("expected"),
                 "observation": item.get("observation")}
        source = item.get("source")
        observation = item.get("observation")
        if dataset not in datasets:
            entry["gap"] = "dataset is not declared by the project"
        elif not isinstance(source, dict) or not isinstance(source.get("reference"), str) or not source["reference"].strip() \
                or not isinstance(source.get("digest"), str) or not DIGEST.fullmatch(source["digest"]):
            entry["gap"] = "validated source or its digest is missing"
        elif "expected" not in item or type(item["expected"]) not in (bool, int, float, str):
            entry["gap"] = "validated expected value is missing or not simple"
        elif not isinstance(observation, dict) or not isinstance(observation.get("path"), str) \
                or not observation["path"].startswith("/") or observation["path"].startswith("//") \
                or not isinstance(observation.get("pointer"), str) or not observation["pointer"].startswith("/"):
            entry["gap"] = "observable HTTP path or JSON pointer is missing"
        else:
            key = (number, dataset, observation["path"] + "#" + observation["pointer"])
            if key in seen and (type(seen[key]) is not type(item["expected"]) or seen[key] != item["expected"]):
                entry["gap"] = "validated sources contradict each other"
                for prior in result:
                    if prior.get("number") == number and prior.get("dataset") == dataset \
                            and prior.get("observation") == observation:
                        prior["gap"] = entry["gap"]
            seen[key] = item["expected"]
        result.append(entry)
    return result


def observed_value(record: dict[str, Any], address: str, observation: dict[str, str], fetch_code: str) -> Any:
    """Read a sealed capture of the declared URL, never an Evaluator claim."""
    command = record.get("command")
    if record.get("kind") != "command" or record.get("address") != address \
            or record.get("exit_code") != 0 or record.get("output_truncated") is not False \
            or command != [sys.executable, "-c", fetch_code, address + observation["path"]]:
        raise ValueError("capture is not the declared product URL and complete response")
    output = record.get("output")
    if not isinstance(output, str):
        raise ValueError("capture has no text output")
    # The documented capture.page command prints the HTTP status first.
    _, separator, body = output.partition("\n")
    if not separator:
        raise ValueError("capture has no response body")
    value: Any = json.loads(body)
    for token in observation["pointer"].split("/")[1:]:
        token = token.replace("~1", "/").replace("~0", "~")
        value = value[int(token)] if isinstance(value, list) else value[token]
    if type(value) not in (bool, int, float, str):
        raise ValueError("observed value is not a simple scalar")
    return value


def same_simple_value(actual: Any, expected: Any) -> bool:
    return type(actual) is type(expected) and actual == expected


def sealed_record(capture_tool: str, convoy: str, ticket: str, piece: str,
                  commit: str, addresses: list[str]) -> dict[str, Any]:
    result = subprocess.run([capture_tool, "verify", convoy, ticket, "--piece", piece],
                            capture_output=True, text=True)
    if result.returncode:
        raise ValueError(f"Evidence Record {piece} is not sealed: {result.stdout}{result.stderr}")
    answer = json.loads(result.stdout)
    path = next(item["path"] for item in answer["pieces"] if item["piece"] == piece)
    record = json.loads(Path(path).read_text(encoding="utf-8"))
    if record.get("commit") != commit or record.get("address") not in addresses:
        raise ValueError(f"Evidence Record {piece} is not from this evaluation's product and commit")
    return record


def enforce(entries: list[dict[str, Any]], given: dict[str, Any], field: str,
            verify: Callable[[str, str], dict[str, Any]], fetch_code: str) -> tuple[dict[str, Any], list[int]]:
    """Compare sealed captures and replace favorable claims that contradict them.

    ``verify`` owns the existing Evidence Record checks (commit, product
    address, seal). The Evaluator supplies piece names, never observed values.
    """
    comparisons = given.pop("comparisons", [])
    if not isinstance(comparisons, list):
        raise ValueError("comparisons must be a list")
    by_id: dict[int, str] = {}
    for item in comparisons:
        if not isinstance(item, dict) or type(item.get("id")) is not int \
                or not isinstance(item.get("evidence"), str) or item["id"] in by_id:
            raise ValueError("comparison id or evidence is missing or repeated")
        by_id[item["id"]] = item["evidence"]
    subjects = {item.get("number"): item for item in given.get(field, []) if isinstance(item, dict)}
    gaps = {entry.get("number") for entry in entries if entry.get("gap")}
    failures: list[int] = []
    for entry in entries:
        subject = subjects.get(entry.get("number"))
        if not isinstance(subject, dict):
            continue  # the existing state gate rejects omitted subjects
        if entry.get("gap"):
            subject.update(state="unobservable", cause="criterion",
                           reason=f"attente validée indisponible : {entry['gap']}")
            continue
        if entry["number"] in gaps:
            by_id.pop(entry["id"], None)
            continue
        piece = by_id.pop(entry["id"], None)
        if piece is None:
            raise ValueError(f"comparison {entry['id']} has no sealed evidence")
        record = verify(piece, entry["dataset"])
        try:
            actual = observed_value(record, record["address"], entry["observation"], fetch_code)
        except (ValueError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            failures.append(entry["id"])
            subject.update(state="not_observed", evidence=piece,
                           reason=f"point observable {entry['observation']['path']} illisible : {exc}")
            subject.pop("cause", None)
            continue
        if not same_simple_value(actual, entry["expected"]):
            failures.append(entry["id"])
            subject.update(state="not_observed", evidence=piece,
                           reason=f"attendu {entry['expected']!r} selon {entry['source']['reference']}, "
                                  f"servi {actual!r} sur {entry['dataset']} au commit {entry['commit']}")
            subject.pop("cause", None)
    if by_id:
        raise ValueError(f"comparison(s) not declared in approved profile: {sorted(by_id)}")
    return given, failures
