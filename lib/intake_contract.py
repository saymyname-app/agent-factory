#!/usr/bin/env python3
"""ADR-0015 intake, run as a program instead of by a human writing JSON.

Implements the deterministic halves of Intake protocol v2
(``docs/decisions/ADR-0015-project-intake-and-target-contract.md``):

- Pass 1 (deterministic discovery, 0 model calls) for both ``origin.kind``
  values: a real filesystem scan for ``takeover``, an explicit empty finding
  set for ``greenfield``.
- The reserved-question set every new project must ask (ADR-0015 §3),
  independent of leverage-test judgment, which stays the calling agent's job.
- Pass 4 (exit, deterministically checked): the six computed conditions
  ADR-0015 §2 lists for ``intake.state`` to become ``complete``.

This module does not call a model and does not decide the leverage test or
draft capabilities/journeys/criteria prose — that is Pass 2, and it stays the
job of the agent running the ``mol-intake`` formula step, guided by the
checklist in ADR-0015's Intake protocol v2. This module only builds the parts
that do not need judgment, and validates the parts that do, reusing
``lib/product_release.py`` unchanged.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from product_release import DISCOVERY_AREAS, RESERVED_CLASSES

# Reserved question prompts, one per ADR-0015 §3 class. `outcome` and
# `authority` are asked of every new project regardless of its pitch, because
# "what does done mean" and "who may approve on the human's behalf" cannot be
# derived from a one-line pitch or a repository scan. The other four are
# asked only when the pitch or discovery findings actually touch them --
# detecting that requires reading the pitch, so it stays the caller's job
# (see `mandatory_reserved_classes` vs. the full `RESERVED_CLASSES` set).
RESERVED_PROMPTS: dict[str, str] = {
    "outcome": "What does \"done\" mean for this version -- the release's own definition of success?",
    "identity_and_consent": (
        "Does this version widen who can see real personal data, or change navigation, invitation, "
        "or consent? If so, describe the change."
    ),
    "irreversible": (
        "Does this version touch production data, a destructive migration, public publication, or "
        "anything else not undoable? If so, describe it."
    ),
    "money": "Does this version involve pricing, spend, purchase, or a contractual commitment?",
    "authority": "Who may approve work on your behalf, and what autonomy level (L0-L3) do you grant?",
    "legal": "Are there licensing, regulatory, or contractual constraints this version must respect?",
}

# Always asked for a brand-new project: nothing in a one-line pitch can
# answer "what does done mean" or "who decides", so these two never wait on
# a leverage-test judgment call the way the other four reserved classes do.
MANDATORY_RESERVED_CLASSES = ("outcome", "authority")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _finding(finding_id: str, area: str, summary: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    return {"id": finding_id, "area": area, "summary": summary, "evidence": evidence}


def deterministic_scan(repo_root: Path, *, origin_kind: str) -> dict[str, Any]:
    """Pass 1: read what already exists. 0 model calls, by construction.

    For ``greenfield`` this returns the "empty-but-explicit" finding set
    ADR-0015 §2 Pass 1 requires: the discovery object is fully formed, its
    method is ``deterministic_scan``, and ``findings`` is an empty list, not
    an absent or null one.
    """
    if origin_kind not in {"greenfield", "takeover"}:
        raise ValueError(f"unsupported origin.kind for a deterministic scan: {origin_kind!r}")

    generated_at = utc_now()
    if origin_kind == "greenfield":
        return {"generated_at": generated_at, "method": "deterministic_scan", "findings": []}

    findings: list[dict[str, Any]] = []
    scanners = {
        "stack": _scan_stack,
        "routes": _scan_routes,
        "data": _scan_data,
        "tests": _scan_tests,
        "ci": _scan_ci,
        "docs": _scan_docs,
        "issues": _scan_issues,
        "history": _scan_history,
        "deployment": _scan_deployment,
    }
    assert set(scanners) == DISCOVERY_AREAS, "scanner coverage must match product_release.DISCOVERY_AREAS"
    counter = 0
    for area, scanner in scanners.items():
        for summary, evidence in scanner(repo_root):
            counter += 1
            findings.append(_finding(f"scan-{area}-{counter}", area, summary, evidence))
    return {"generated_at": generated_at, "method": "deterministic_scan", "findings": findings}


def _rel(repo_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _code_evidence(repo_root: Path, path: Path, status: str = "unverified") -> list[dict[str, Any]]:
    return [{"kind": "scan", "ref": _rel(repo_root, path), "status": status}]


def _scan_stack(repo_root: Path):
    markers = {
        "package.json": "Node/JavaScript project (package.json present).",
        "pyproject.toml": "Python project (pyproject.toml present).",
        "requirements.txt": "Python project (requirements.txt present).",
        "go.mod": "Go project (go.mod present).",
        "Cargo.toml": "Rust project (Cargo.toml present).",
        "Gemfile": "Ruby project (Gemfile present).",
        "pom.xml": "Java/Maven project (pom.xml present).",
        "build.gradle": "Java/Gradle project (build.gradle present).",
    }
    for name, summary in markers.items():
        path = repo_root / name
        if path.is_file():
            yield summary, _code_evidence(repo_root, path)


def _scan_routes(repo_root: Path):
    route_dirs = ["routes", "app/routes", "src/routes", "pages", "app/api", "src/api", "controllers"]
    for rel in route_dirs:
        path = repo_root / rel
        if path.is_dir():
            count = sum(1 for _ in path.rglob("*") if _.is_file())
            yield (
                f"Route-shaped directory {rel} present with {count} file(s).",
                _code_evidence(repo_root, path),
            )


def _scan_data(repo_root: Path):
    data_dirs = ["migrations", "db/migrations", "prisma", "schema"]
    for rel in data_dirs:
        path = repo_root / rel
        if path.is_dir():
            count = sum(1 for _ in path.rglob("*") if _.is_file())
            yield (
                f"Data/migration directory {rel} present with {count} file(s).",
                _code_evidence(repo_root, path),
            )


def _scan_tests(repo_root: Path):
    test_dirs = ["tests", "test", "spec", "__tests__"]
    for rel in test_dirs:
        path = repo_root / rel
        if path.is_dir():
            count = sum(1 for _ in path.rglob("*") if _.is_file())
            if count:
                yield (
                    f"Test directory {rel} present with {count} file(s).",
                    _code_evidence(repo_root, path),
                )


def _scan_ci(repo_root: Path):
    ci_paths = [".github/workflows", ".gitlab-ci.yml", ".circleci/config.yml"]
    for rel in ci_paths:
        path = repo_root / rel
        if path.exists():
            yield f"CI configuration present at {rel}.", _code_evidence(repo_root, path)


def _scan_docs(repo_root: Path):
    doc_paths = ["README.md", "docs", "AGENTS.md", "CLAUDE.md"]
    for rel in doc_paths:
        path = repo_root / rel
        if path.exists():
            yield f"Documentation artifact present at {rel}.", _code_evidence(repo_root, path)


def _scan_issues(repo_root: Path):
    result = _run_git(repo_root, ["remote", "get-url", "origin"])
    if result:
        yield f"Git remote configured ({result}); issue tracker location is that remote's host.", [
            {"kind": "scan", "ref": "git remote get-url origin", "status": "unverified"}
        ]


def _scan_history(repo_root: Path):
    count = _run_git(repo_root, ["rev-list", "--count", "HEAD"])
    if count:
        yield (
            f"Repository has {count.strip()} commit(s) of history.",
            [{"kind": "scan", "ref": "git rev-list --count HEAD", "status": "unverified"}],
        )


def _scan_deployment(repo_root: Path):
    deploy_paths = ["Dockerfile", "docker-compose.yml", "k8s", ".github/workflows/deploy.yml", "terraform"]
    for rel in deploy_paths:
        path = repo_root / rel
        if path.exists():
            yield f"Deployment artifact present at {rel}.", _code_evidence(repo_root, path)


def _run_git(repo_root: Path, args: list[str]) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def reserved_questions(classes: list[str], *, prefix: str = "q") -> list[dict[str, Any]]:
    """Build ``intake.questions`` entries for the given reserved classes.

    Every entry is ``admitted_by: "reserved"`` per ADR-0015 §3: reserved
    questions are always asked, never suppressed by the question budget, and
    can never be answered by an assumption.
    """
    unknown = set(classes) - RESERVED_CLASSES
    if unknown:
        raise ValueError(f"not a reserved class: {sorted(unknown)}")
    questions = []
    for index, kind in enumerate(classes, start=1):
        questions.append({
            "id": f"{prefix}-{kind.replace('_', '-')}",
            "kind": kind,
            "prompt": RESERVED_PROMPTS[kind],
            "admitted_by": "reserved",
            "status": "pending",
        })
    return questions


def build_intake_skeleton(
    *,
    product: str,
    title: str,
    pitch: str,
    pitch_author: str,
    origin_kind: str,
    discovery: dict[str, Any],
    extra_reserved_classes: list[str] | None = None,
) -> dict[str, Any]:
    """Assemble a minimal, schema-valid `intake`-state release contract.

    Populates every field `validate_release_contract` requires with the
    smallest honest value: empty capability/journey/criteria/work_graph
    lists (Pass 2 -- drafting them is judgment, done by the calling agent),
    the mandatory reserved questions plus any the caller has determined
    apply (Pass 3 admission is mechanical for these two classes, judgment
    for the rest), and `intake.state = "awaiting_human"` because the
    questions above have not been answered yet.
    """
    classes = list(MANDATORY_RESERVED_CLASSES) + [
        item for item in (extra_reserved_classes or []) if item not in MANDATORY_RESERVED_CLASSES
    ]
    questions = reserved_questions(classes)
    now = utc_now()

    # `work_graph` and `criteria` may not be empty (product_release.py rejects
    # an empty work_graph outright), and Pass 2 always drafts "a first
    # work_graph" per ADR-0015 -- even at `intake` there is exactly one node:
    # resolving intake itself, which is Factory-kind work, not a product
    # capability. Real capabilities/journeys/criteria are Pass 2's job and
    # stay empty until the calling agent drafts them.
    intake_capability_id = "intake-in-progress"
    intake_criterion_id = "intake-target-defined"
    capabilities = [{
        "id": intake_capability_id,
        "title": "Intake in progress",
        "description": "Placeholder capability for the intake phase itself -- Pass 2 replaces this with the drafted product capabilities.",
        "status": "unverified",
        "evidence": [{"kind": "document", "ref": "intake:objective.statement", "status": "unverified"}],
    }]
    criteria = [{
        "id": intake_criterion_id,
        "title": "Intake target defined",
        "description": "The release's target -- capabilities, journeys, and success criteria -- is drafted and confirmed.",
        "status": "unverified",
        "evidence": [{"kind": "document", "ref": "intake:objective.statement", "status": "unverified"}],
        "capability_refs": [intake_capability_id],
        "journey_refs": [],
        "acceptance": (
            "Every reserved intake question has status=answered with an answer_ref, and Pass 2 "
            "drafting has produced a confirmed capabilities/journeys/criteria/work_graph set."
        ),
    }]
    work_graph = [{
        "id": "intake-resolve",
        "dedupe_key": "intake-resolve",
        "title": "Resolve intake: answer reserved questions and draft the V1 target",
        "kind": "factory",
        "state": "candidate",
        "independence": "unknown",
        "order": 1,
        "criterion_refs": [intake_criterion_id],
        "depends_on": [],
    }]
    return {
        "$schema": "../product-release.schema.json",
        "contract": "agent-factory-product-release/v1",
        "schema_version": 1,
        "product": product,
        "version": "V1",
        "title": title,
        "state": "intake",
        "revision": 1,
        "objective": {
            "statement": pitch,
            "set_by": pitch_author,
            "set_at": now,
        },
        "origin": {
            "kind": origin_kind,
            "statement": pitch,
            "sources": [],
            "discovery": discovery,
        },
        "autonomy": {
            "level": "L1",
            "label": "Assisted · pending explicit grant (reserved authority question unanswered)",
            "granted_by": "factory:intake-default",
            "granted_at": now,
            "reserved_questions": sorted(RESERVED_CLASSES),
        },
        "intake": {
            "state": "awaiting_human",
            "question_budget": {
                "max_first_pass": 5,
                "max_per_iteration": 2,
                "spent": len(questions),
                "exhausted": len(questions) >= 5,
                "on_exhausted": "proceed_on_assumptions",
            },
            "questions": questions,
            "exit_criteria": [
                {
                    "id": "intake-questions-answered",
                    "statement": "Every reserved intake question has status=answered with an answer_ref.",
                    "satisfied": False,
                },
            ],
        },
        "assumptions": [],
        "budget": {
            "max_consecutive_no_progress": 3,
            "spent": {"delivery_tokens": 0, "clarification_tokens": 0, "consecutive_no_progress": 0},
        },
        "maturity": {"level": "intake", "label": "Intake in progress · no target drafted yet", "criteria": []},
        "capabilities": capabilities,
        "journeys": [],
        "included": [],
        "excluded": [],
        "dependencies": [],
        "decisions": [],
        "criteria": criteria,
        "work_graph": work_graph,
        "factory_improvements": [],
        "next_version": None,
    }


def check_intake_exit(contract: dict[str, Any]) -> tuple[bool, list[str]]:
    """Pass 4, ADR-0015 §2: the six computed conditions for `intake.state = complete`.

    Returns ``(complete, reasons)`` where ``reasons`` lists every unmet
    condition; an empty list means all six hold. Does not mutate the
    contract or call `validate_release_contract` (callers should run that
    separately -- condition 6 delegates to it).
    """
    reasons: list[str] = []
    criteria = contract.get("criteria", [])
    criterion_ids = {item["id"] for item in criteria}
    work_graph = contract.get("work_graph", [])

    if any(not item.get("acceptance", "").strip() for item in criteria):
        reasons.append("1: every criteria[] item must have a non-empty human-observable acceptance")

    referenced_by_work = set()
    for node in work_graph:
        refs = node.get("criterion_refs", [])
        if not refs:
            reasons.append(f"2: work_graph node {node.get('id')} references no criterion")
        referenced_by_work.update(refs)
    unreferenced = criterion_ids - referenced_by_work
    if unreferenced:
        reasons.append(f"2: criteria not referenced by any work_graph node: {sorted(unreferenced)}")

    reserved_qs = [q for q in contract.get("intake", {}).get("questions", []) if q.get("admitted_by") == "reserved"]
    unanswered_reserved = [
        q["id"] for q in reserved_qs
        if q.get("status") != "answered" or not q.get("answer_ref")
    ]
    if unanswered_reserved:
        reasons.append(f"3: reserved questions without status=answered + answer_ref: {unanswered_reserved}")

    maturity_criteria = contract.get("maturity", {}).get("criteria", [])
    if not set(maturity_criteria).issubset(criterion_ids):
        reasons.append("4: maturity.criteria references a criterion that does not exist")

    first_order_ids = {node["id"] for node in work_graph if not node.get("depends_on")}
    low_confidence_blocking = [
        item["id"] for item in contract.get("assumptions", [])
        if item.get("confidence") == "low"
        and item.get("status") == "standing"
        and set(item.get("scope_refs", [])) & first_order_ids
    ]
    if low_confidence_blocking:
        reasons.append(
            f"5: low-confidence assumptions still standing against first-order work: {low_confidence_blocking}"
        )

    return (not reasons, reasons)
