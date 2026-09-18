#!/usr/bin/env python3
"""Versioned product-release contract, transitions, and campaign selection.

This module is deliberately pure: it reads no live state, writes no files, and
never invokes a model.  Git owns release truth; callers only validate or project
an already loaded value.
"""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


CONTRACT = "agent-factory-product-release/v1"
SCHEMA_VERSION = 1
RELEASE_STATES = ("intake", "draft", "approved", "executing", "frozen")
EVIDENCE_STATES = {
    "proven", "partial", "unverified", "absent", "out_of_version", "decision_required", "assumed",
}
EVIDENCE_KINDS = {"ui", "api", "data", "test", "document", "bead", "github", "scan"}
WORK_STATES = {
    "candidate", "materialized", "active", "blocked", "delivered", "cancelled", "paused",
    "superseded_pending",
}
BLOCK_KINDS = {"decision", "admin", "limit", "durable_failure", "dependency"}
ORIGIN_KINDS = {"greenfield", "takeover", "migration"}
TAKEOVER_ORIGIN_KINDS = {"takeover", "migration"}
SOURCE_KINDS = {"repository", "document", "system", "database", "conversation"}
SOURCE_ACCESS = {"read", "read_write", "none"}
CONFLICT_RESOLUTIONS = {"pending", "keep_target", "adapt_target", "mix"}
DISCOVERY_METHODS = {"deterministic_scan", "model_assisted", "human_statement"}
DISCOVERY_AREAS = {
    "stack", "routes", "data", "tests", "ci", "docs", "issues", "history", "deployment",
}
AUTONOMY_LEVELS = {"L0", "L1", "L2", "L3"}
RESERVED_CLASSES = {
    "outcome", "identity_and_consent", "irreversible", "money", "authority", "legal",
}
INTAKE_STATES = {"not_started", "discovering", "drafting", "awaiting_human", "complete"}
QUESTION_ADMITTED_BY = {"reserved", "leverage"}
QUESTION_STATUSES = {"pending", "asked", "answered", "dropped_over_budget", "withdrawn"}
QUESTION_BUDGET_ON_EXHAUSTED = {"proceed_on_assumptions", "stop_and_ask"}
ASSUMPTION_CONFIDENCES = {"high", "medium", "low"}
ASSUMPTION_STATUSES = {"standing", "confirmed", "refuted", "promoted_decision"}
REVIEW_STATES = {"unreviewed", "reviewed_ok", "needs_rework"}
REVIEW_TIERS = {"static", "model", "human_e2e"}
STOP_REASONS = {
    "release_target_proven", "all_remaining_blocked_by_decision", "blocked_decision",
    "blocked_admin", "blocked_limit", "blocked_durable_failure", "blocked_dependency",
    "independence_unknown", "no_proven_independent_work", "release_not_executable",
    "intake_incomplete", "provider_quota_exhausted", "no_progress",
}
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9.-]{0,95}$")
VERSION_PATTERN = re.compile(r"^V[1-9][0-9]*$")


class ReleaseContractError(ValueError):
    """A release value cannot safely drive a product projection or campaign."""


def _required_text(value: Any, field: str, *, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ReleaseContractError(f"{field} doit être un texte non vide.")
    result = value.strip()
    if pattern and not pattern.fullmatch(result):
        raise ReleaseContractError(f"{field} a un format invalide.")
    return result


def _datetime_text(value: Any, field: str) -> str:
    text = _required_text(value, field)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReleaseContractError(f"{field} doit être une date-heure ISO 8601.") from exc
    return text


def _list(value: Any, field: str, *, nonempty: bool = True) -> list[Any]:
    if not isinstance(value, list) or (nonempty and not value):
        raise ReleaseContractError(f"{field} doit être une liste{' non vide' if nonempty else ''}.")
    return value


def _ids(value: Any, field: str, allowed: set[str] | None = None) -> list[str]:
    result = [
        _required_text(item, f"{field}[]", pattern=ID_PATTERN)
        for item in _list(value, field, nonempty=False)
    ]
    if len(result) != len(set(result)):
        raise ReleaseContractError(f"{field} contient un doublon.")
    if allowed is not None and not set(result).issubset(allowed):
        raise ReleaseContractError(f"{field} contient une référence inconnue.")
    return result


def _validate_evidence(value: Any, field: str, *, nonempty: bool = True) -> list[dict[str, Any]]:
    evidence = _list(value, field, nonempty=nonempty)
    for index, item in enumerate(evidence):
        prefix = f"{field}[{index}]"
        if not isinstance(item, dict):
            raise ReleaseContractError(f"{prefix} doit être un objet.")
        if set(item) != {"kind", "ref", "status"}:
            raise ReleaseContractError(f"{prefix} doit contenir exactement kind, ref et status.")
        if item.get("kind") not in EVIDENCE_KINDS:
            raise ReleaseContractError(f"{prefix}.kind est inconnu.")
        _required_text(item.get("ref"), f"{prefix}.ref")
        if item.get("status") not in EVIDENCE_STATES:
            raise ReleaseContractError(f"{prefix}.status est inconnu.")
    return evidence


def _validate_review(value: Any, field: str) -> dict[str, Any]:
    allowed = {"state", "tier", "reviewed_at", "reviewed_by", "ref", "notes"}
    if not isinstance(value, dict) or set(value) != allowed:
        raise ReleaseContractError(
            f"{field} doit contenir exactement state, tier, reviewed_at, reviewed_by, ref et notes."
        )
    if value.get("state") not in REVIEW_STATES:
        raise ReleaseContractError(f"{field}.state est inconnu.")
    tier = value.get("tier")
    if tier is not None and tier not in REVIEW_TIERS:
        raise ReleaseContractError(f"{field}.tier est inconnu.")
    reviewed_at = value.get("reviewed_at")
    if reviewed_at is not None:
        _datetime_text(reviewed_at, f"{field}.reviewed_at")
    reviewed_by = value.get("reviewed_by")
    if reviewed_by is not None:
        _required_text(reviewed_by, f"{field}.reviewed_by")
    _validate_evidence(value.get("ref"), f"{field}.ref", nonempty=False)
    if not isinstance(value.get("notes"), str):
        raise ReleaseContractError(f"{field}.notes doit être un texte.")
    return value


def _validate_scoped_blocks(
    value: Any, field: str, *, require_evidence: bool = True, origin_kind: str | None = None,
) -> tuple[list[dict[str, Any]], set[str]]:
    items = _list(value, field, nonempty=False)
    seen: set[str] = set()
    for index, item in enumerate(items):
        prefix = f"{field}[{index}]"
        if not isinstance(item, dict):
            raise ReleaseContractError(f"{prefix} doit être un objet.")
        item_id = _required_text(item.get("id"), f"{prefix}.id", pattern=ID_PATTERN)
        if item_id in seen:
            raise ReleaseContractError(f"Identifiant dupliqué dans {field}: {item_id}.")
        seen.add(item_id)
        _required_text(item.get("title"), f"{prefix}.title")
        _required_text(item.get("description"), f"{prefix}.description")
        if item.get("status") not in EVIDENCE_STATES:
            raise ReleaseContractError(f"{prefix}.status est inconnu.")
        evidence: list[dict[str, Any]] = []
        if require_evidence:
            evidence = _validate_evidence(item.get("evidence"), f"{prefix}.evidence")
        review = item.get("review")
        if review is not None:
            _validate_review(review, f"{prefix}.review")

        # ADR-0021 fail-closed rule: a block whose evidence includes a
        # discovery-sourced (scan) item, on a takeover/migration-origin release,
        # was mechanically discovered rather than delivered by the Factory and
        # must carry a review object -- a missing review key is not "no opinion
        # yet", it is the exact gap ADR-0021 exists to close.
        is_discovery_sourced = any(entry.get("kind") == "scan" for entry in evidence)
        requires_review = origin_kind in TAKEOVER_ORIGIN_KINDS and is_discovery_sourced
        if requires_review and review is None:
            raise ReleaseContractError(
                f"{prefix} est issu d'une reprise (origin.kind={origin_kind}) avec une preuve de "
                "type scan: review est requis, même à l'état unreviewed (ADR-0021)."
            )
        if item.get("status") == "proven" and review is not None and review.get("state") == "unreviewed":
            raise ReleaseContractError(
                f"{prefix} ne peut pas être proven tant que review.state vaut unreviewed "
                "(ADR-0021: bloc issu d'une reprise, non revu par la Factory)."
            )
    return items, seen


def _validate_objective(value: Any) -> dict[str, Any]:
    allowed = {"statement", "set_by", "set_at", "supersedes"}
    required = {"statement", "set_by", "set_at"}
    if not isinstance(value, dict) or not required.issubset(value) or set(value) - allowed:
        raise ReleaseContractError("objective a des champs manquants ou inconnus.")
    _required_text(value.get("statement"), "objective.statement")
    _required_text(value.get("set_by"), "objective.set_by")
    _datetime_text(value.get("set_at"), "objective.set_at")
    supersedes = value.get("supersedes")
    if supersedes is not None:
        _required_text(supersedes, "objective.supersedes")
    return value


def _validate_origin(value: Any) -> dict[str, Any]:
    allowed = {"kind", "statement", "sources", "discovery", "conflicts"}
    required = {"kind", "statement", "sources", "discovery"}
    if not isinstance(value, dict) or not required.issubset(value) or set(value) - allowed:
        raise ReleaseContractError("origin a des champs manquants ou inconnus.")
    if value.get("kind") not in ORIGIN_KINDS:
        raise ReleaseContractError("origin.kind est inconnu.")
    _required_text(value.get("statement"), "origin.statement")

    sources = _list(value.get("sources"), "origin.sources", nonempty=False)
    for index, source in enumerate(sources):
        prefix = f"origin.sources[{index}]"
        source_allowed = {"kind", "ref", "access"}
        source_required = {"kind", "ref"}
        if not isinstance(source, dict) or not source_required.issubset(source) or set(source) - source_allowed:
            raise ReleaseContractError(f"{prefix} a des champs manquants ou inconnus.")
        if source.get("kind") not in SOURCE_KINDS:
            raise ReleaseContractError(f"{prefix}.kind est inconnu.")
        _required_text(source.get("ref"), f"{prefix}.ref")
        access = source.get("access")
        if access is not None and access not in SOURCE_ACCESS:
            raise ReleaseContractError(f"{prefix}.access est inconnu.")

    conflicts = _list(value.get("conflicts", []), "origin.conflicts", nonempty=False)
    seen_conflict_ids: set[str] = set()
    for index, conflict in enumerate(conflicts):
        prefix = f"origin.conflicts[{index}]"
        conflict_allowed = {
            "id", "summary", "code_evidence", "intent_ref", "decision_id", "resolution", "resolution_detail",
        }
        conflict_required = {"id", "summary", "code_evidence", "intent_ref", "decision_id", "resolution"}
        if not isinstance(conflict, dict) or not conflict_required.issubset(conflict) or (
            set(conflict) - conflict_allowed
        ):
            raise ReleaseContractError(f"{prefix} a des champs manquants ou inconnus.")
        conflict_id = _required_text(conflict.get("id"), f"{prefix}.id", pattern=ID_PATTERN)
        if conflict_id in seen_conflict_ids:
            raise ReleaseContractError(f"origin.conflicts contient un identifiant dupliqué: {conflict_id}.")
        seen_conflict_ids.add(conflict_id)
        _required_text(conflict.get("summary"), f"{prefix}.summary")
        _validate_evidence(conflict.get("code_evidence"), f"{prefix}.code_evidence")
        _required_text(conflict.get("intent_ref"), f"{prefix}.intent_ref")
        _required_text(conflict.get("decision_id"), f"{prefix}.decision_id", pattern=ID_PATTERN)
        if conflict.get("resolution") not in CONFLICT_RESOLUTIONS:
            raise ReleaseContractError(f"{prefix}.resolution est inconnu.")
        if conflict["resolution"] == "mix" and not conflict.get("resolution_detail"):
            raise ReleaseContractError(
                f"{prefix}.resolution_detail est requis quand resolution vaut mix."
            )

    discovery = value.get("discovery")
    discovery_allowed = {"generated_at", "method", "findings"}
    if not isinstance(discovery, dict) or set(discovery) != discovery_allowed:
        raise ReleaseContractError(
            "origin.discovery doit contenir exactement generated_at, method et findings."
        )
    _datetime_text(discovery.get("generated_at"), "origin.discovery.generated_at")
    if discovery.get("method") not in DISCOVERY_METHODS:
        raise ReleaseContractError("origin.discovery.method est inconnu.")
    findings = _list(discovery.get("findings"), "origin.discovery.findings", nonempty=False)
    seen_finding_ids: set[str] = set()
    for index, finding in enumerate(findings):
        prefix = f"origin.discovery.findings[{index}]"
        if not isinstance(finding, dict) or set(finding) != {"id", "area", "summary", "evidence"}:
            raise ReleaseContractError(f"{prefix} doit contenir exactement id, area, summary et evidence.")
        finding_id = _required_text(finding.get("id"), f"{prefix}.id", pattern=ID_PATTERN)
        if finding_id in seen_finding_ids:
            raise ReleaseContractError(
                f"origin.discovery.findings contient un identifiant dupliqué: {finding_id}."
            )
        seen_finding_ids.add(finding_id)
        if finding.get("area") not in DISCOVERY_AREAS:
            raise ReleaseContractError(f"{prefix}.area est inconnu.")
        _required_text(finding.get("summary"), f"{prefix}.summary")
        _validate_evidence(finding.get("evidence"), f"{prefix}.evidence")

    return value


def _validate_autonomy(value: Any) -> dict[str, Any]:
    allowed = {
        "level", "label", "granted_by", "granted_at", "reserved_questions",
        "version_transition_requires_human", "escalations",
    }
    required = {"level", "label", "granted_by", "granted_at", "reserved_questions"}
    if not isinstance(value, dict) or not required.issubset(value) or set(value) - allowed:
        raise ReleaseContractError("autonomy a des champs manquants ou inconnus.")
    if value.get("level") not in AUTONOMY_LEVELS:
        raise ReleaseContractError("autonomy.level est inconnu.")
    _required_text(value.get("label"), "autonomy.label")
    _required_text(value.get("granted_by"), "autonomy.granted_by")
    _datetime_text(value.get("granted_at"), "autonomy.granted_at")

    reserved_questions = _list(value.get("reserved_questions"), "autonomy.reserved_questions", nonempty=False)
    for item in reserved_questions:
        if item not in RESERVED_CLASSES:
            raise ReleaseContractError("autonomy.reserved_questions contient une classe réservée inconnue.")
    if len(reserved_questions) != len(set(reserved_questions)):
        raise ReleaseContractError("autonomy.reserved_questions contient un doublon.")
    if set(reserved_questions) != RESERVED_CLASSES:
        raise ReleaseContractError(
            "autonomy.reserved_questions doit toujours contenir l'ensemble complet des classes "
            "réservées: un niveau d'autonomie peut élargir les questions posées, jamais réduire "
            "l'ensemble réservé."
        )

    version_transition_requires_human = value.get("version_transition_requires_human", True)
    if version_transition_requires_human is not True:
        raise ReleaseContractError(
            "autonomy.version_transition_requires_human doit rester vrai à tout niveau "
            "d'autonomie, y compris L3: figer une version est irréversible."
        )

    escalations = value.get("escalations")
    if escalations is not None:
        for index, item in enumerate(_list(escalations, "autonomy.escalations", nonempty=False)):
            _required_text(item, f"autonomy.escalations[{index}]")
    return value


def _validate_intake(value: Any) -> dict[str, Any]:
    allowed = {"state", "question_budget", "questions", "exit_criteria", "completed_at"}
    required = {"state", "question_budget", "questions", "exit_criteria"}
    if not isinstance(value, dict) or not required.issubset(value) or set(value) - allowed:
        raise ReleaseContractError("intake a des champs manquants ou inconnus.")
    if value.get("state") not in INTAKE_STATES:
        raise ReleaseContractError("intake.state est inconnu.")
    completed_at = value.get("completed_at")
    if completed_at is not None:
        _datetime_text(completed_at, "intake.completed_at")

    budget = value.get("question_budget")
    budget_allowed = {"max_first_pass", "max_per_iteration", "spent", "exhausted", "on_exhausted"}
    budget_required = {"max_first_pass", "max_per_iteration", "spent", "exhausted"}
    if not isinstance(budget, dict) or not budget_required.issubset(budget) or set(budget) - budget_allowed:
        raise ReleaseContractError("intake.question_budget a des champs manquants ou inconnus.")
    for field in ("max_first_pass", "max_per_iteration", "spent"):
        item = budget.get(field)
        if not isinstance(item, int) or isinstance(item, bool) or item < 0:
            raise ReleaseContractError(f"intake.question_budget.{field} doit être un entier positif ou nul.")
    if not isinstance(budget.get("exhausted"), bool):
        raise ReleaseContractError("intake.question_budget.exhausted doit être un booléen.")
    on_exhausted = budget.get("on_exhausted")
    if on_exhausted is not None and on_exhausted not in QUESTION_BUDGET_ON_EXHAUSTED:
        raise ReleaseContractError("intake.question_budget.on_exhausted est inconnu.")

    questions = _list(value.get("questions"), "intake.questions", nonempty=False)
    seen_question_ids: set[str] = set()
    for index, question in enumerate(questions):
        prefix = f"intake.questions[{index}]"
        if not isinstance(question, dict):
            raise ReleaseContractError(f"{prefix} doit être un objet.")
        question_allowed = {
            "id", "kind", "prompt", "admitted_by", "status", "leverage_refs",
            "asked_at", "answer", "answer_ref", "produced_decision_id", "produced_assumption_id",
        }
        question_required = {"id", "kind", "prompt", "admitted_by", "status"}
        if not question_required.issubset(question) or set(question) - question_allowed:
            raise ReleaseContractError(f"{prefix} a des champs manquants ou inconnus.")
        question_id = _required_text(question.get("id"), f"{prefix}.id", pattern=ID_PATTERN)
        if question_id in seen_question_ids:
            raise ReleaseContractError(f"intake.questions contient un identifiant dupliqué: {question_id}.")
        seen_question_ids.add(question_id)
        if question.get("kind") not in RESERVED_CLASSES:
            raise ReleaseContractError(f"{prefix}.kind est inconnu.")
        _required_text(question.get("prompt"), f"{prefix}.prompt")
        if question.get("admitted_by") not in QUESTION_ADMITTED_BY:
            raise ReleaseContractError(f"{prefix}.admitted_by est inconnu.")
        if question.get("status") not in QUESTION_STATUSES:
            raise ReleaseContractError(f"{prefix}.status est inconnu.")
        leverage_refs = question.get("leverage_refs")
        if question["admitted_by"] == "leverage" and not leverage_refs:
            raise ReleaseContractError(
                f"{prefix}.leverage_refs est requis quand admitted_by vaut leverage."
            )
        if leverage_refs is not None:
            _ids(leverage_refs, f"{prefix}.leverage_refs")
        asked_at = question.get("asked_at")
        if asked_at is not None:
            _datetime_text(asked_at, f"{prefix}.asked_at")
        answer = question.get("answer")
        if answer is not None:
            _required_text(answer, f"{prefix}.answer")
        answer_ref = question.get("answer_ref")
        if answer_ref is not None:
            _required_text(answer_ref, f"{prefix}.answer_ref")
        for ref_field in ("produced_decision_id", "produced_assumption_id"):
            ref_value = question.get(ref_field)
            if ref_value is not None:
                _required_text(ref_value, f"{prefix}.{ref_field}", pattern=ID_PATTERN)

    exit_criteria = _list(value.get("exit_criteria"), "intake.exit_criteria")
    seen_exit_ids: set[str] = set()
    for index, criterion in enumerate(exit_criteria):
        prefix = f"intake.exit_criteria[{index}]"
        exit_allowed = {"id", "statement", "satisfied", "detail"}
        exit_required = {"id", "statement", "satisfied"}
        if not isinstance(criterion, dict) or not exit_required.issubset(criterion) or (
            set(criterion) - exit_allowed
        ):
            raise ReleaseContractError(f"{prefix} a des champs manquants ou inconnus.")
        exit_id = _required_text(criterion.get("id"), f"{prefix}.id", pattern=ID_PATTERN)
        if exit_id in seen_exit_ids:
            raise ReleaseContractError(f"intake.exit_criteria contient un identifiant dupliqué: {exit_id}.")
        seen_exit_ids.add(exit_id)
        _required_text(criterion.get("statement"), f"{prefix}.statement")
        if not isinstance(criterion.get("satisfied"), bool):
            raise ReleaseContractError(f"{prefix}.satisfied doit être un booléen.")
        detail = criterion.get("detail")
        if detail is not None and not isinstance(detail, str):
            raise ReleaseContractError(f"{prefix}.detail doit être un texte.")

    return value


def _validate_assumptions(value: Any) -> tuple[list[dict[str, Any]], set[str]]:
    items = _list(value, "assumptions", nonempty=False)
    seen: set[str] = set()
    for index, item in enumerate(items):
        prefix = f"assumptions[{index}]"
        allowed = {
            "id", "title", "statement", "rationale", "confidence", "status",
            "scope_refs", "invalidated_by", "promoted_decision_id",
        }
        required = {
            "id", "title", "statement", "rationale", "confidence", "status",
            "scope_refs", "invalidated_by",
        }
        if not isinstance(item, dict) or not required.issubset(item) or set(item) - allowed:
            raise ReleaseContractError(f"{prefix} a des champs manquants ou inconnus.")
        item_id = _required_text(item.get("id"), f"{prefix}.id", pattern=ID_PATTERN)
        if item_id in seen:
            raise ReleaseContractError(f"assumptions contient un identifiant dupliqué: {item_id}.")
        seen.add(item_id)
        _required_text(item.get("title"), f"{prefix}.title")
        _required_text(item.get("statement"), f"{prefix}.statement")
        _required_text(item.get("rationale"), f"{prefix}.rationale")
        if item.get("confidence") not in ASSUMPTION_CONFIDENCES:
            raise ReleaseContractError(f"{prefix}.confidence est inconnu.")
        if item.get("status") not in ASSUMPTION_STATUSES:
            raise ReleaseContractError(f"{prefix}.status est inconnu.")
        _ids(item.get("scope_refs"), f"{prefix}.scope_refs")
        _validate_evidence(item.get("invalidated_by"), f"{prefix}.invalidated_by", nonempty=False)
        promoted = item.get("promoted_decision_id")
        if promoted is not None:
            _required_text(promoted, f"{prefix}.promoted_decision_id", pattern=ID_PATTERN)
    return items, seen


def _validate_budget(value: Any) -> dict[str, Any]:
    allowed = {"max_consecutive_no_progress", "spent", "provider_fallback", "stop_reason"}
    required = {"max_consecutive_no_progress", "spent"}
    if not isinstance(value, dict) or not required.issubset(value) or set(value) - allowed:
        raise ReleaseContractError("budget a des champs manquants ou inconnus.")
    max_no_progress = value.get("max_consecutive_no_progress")
    if not isinstance(max_no_progress, int) or isinstance(max_no_progress, bool) or max_no_progress < 1:
        raise ReleaseContractError("budget.max_consecutive_no_progress doit être un entier positif.")

    provider_fallback = value.get("provider_fallback")
    if provider_fallback is not None:
        for index, item in enumerate(_list(provider_fallback, "budget.provider_fallback", nonempty=False)):
            _required_text(item, f"budget.provider_fallback[{index}]")

    spent = value.get("spent")
    spent_allowed = {"delivery_tokens", "clarification_tokens", "consecutive_no_progress", "wall_clock_minutes"}
    spent_required = {"delivery_tokens", "clarification_tokens", "consecutive_no_progress"}
    if not isinstance(spent, dict) or not spent_required.issubset(spent) or set(spent) - spent_allowed:
        raise ReleaseContractError("budget.spent a des champs manquants ou inconnus.")
    for field in ("delivery_tokens", "clarification_tokens", "consecutive_no_progress"):
        item = spent.get(field)
        if not isinstance(item, int) or isinstance(item, bool) or item < 0:
            raise ReleaseContractError(f"budget.spent.{field} doit être un entier positif ou nul.")
    wall_clock = spent.get("wall_clock_minutes")
    if wall_clock is not None and (
        not isinstance(wall_clock, int) or isinstance(wall_clock, bool) or wall_clock < 0
    ):
        raise ReleaseContractError("budget.spent.wall_clock_minutes doit être un entier positif ou nul.")

    stop_reason = value.get("stop_reason")
    if stop_reason is not None and stop_reason not in STOP_REASONS:
        raise ReleaseContractError("budget.stop_reason est inconnu.")
    return value


def _validate_graph(
    nodes: Any, criterion_ids: set[str], decision_ids: set[str], assumption_ids: set[str],
) -> tuple[list[dict[str, Any]], set[str]]:
    values = _list(nodes, "work_graph")
    ids: set[str] = set()
    dedupe: set[str] = set()
    for index, node in enumerate(values):
        prefix = f"work_graph[{index}]"
        if not isinstance(node, dict):
            raise ReleaseContractError(f"{prefix} doit être un objet.")
        node_id = _required_text(node.get("id"), f"{prefix}.id", pattern=ID_PATTERN)
        dedupe_key = _required_text(node.get("dedupe_key"), f"{prefix}.dedupe_key", pattern=ID_PATTERN)
        if node_id in ids or dedupe_key in dedupe:
            raise ReleaseContractError("Le graphe de travail contient un ID ou une clé de déduplication en double.")
        ids.add(node_id)
        dedupe.add(dedupe_key)
        _required_text(node.get("title"), f"{prefix}.title")
        if node.get("kind") not in {"product", "factory"}:
            raise ReleaseContractError(f"{prefix}.kind doit être product ou factory.")
        if node.get("state") not in WORK_STATES:
            raise ReleaseContractError(f"{prefix}.state est inconnu.")
        if node.get("independence") not in {"proven", "unknown"}:
            raise ReleaseContractError(f"{prefix}.independence doit être proven ou unknown.")
        if not isinstance(node.get("order"), int) or isinstance(node.get("order"), bool) or node["order"] < 1:
            raise ReleaseContractError(f"{prefix}.order doit être un entier positif.")
        _ids(node.get("criterion_refs"), f"{prefix}.criterion_refs", criterion_ids)
        if not node.get("criterion_refs"):
            raise ReleaseContractError(f"{prefix} doit être traçable vers au moins un critère.")
        assumption_refs = node.get("assumption_refs")
        if assumption_refs is not None:
            _ids(assumption_refs, f"{prefix}.assumption_refs", assumption_ids)
        introduced_in_revision = node.get("introduced_in_revision")
        if introduced_in_revision is not None and (
            not isinstance(introduced_in_revision, int) or isinstance(introduced_in_revision, bool)
            or introduced_in_revision < 1
        ):
            raise ReleaseContractError(f"{prefix}.introduced_in_revision doit être un entier positif.")
        blocker = node.get("blocker")
        if blocker is not None:
            if not isinstance(blocker, dict) or set(blocker) - {"kind", "decision_id", "cause", "owner", "action"}:
                raise ReleaseContractError(f"{prefix}.blocker est invalide.")
            if blocker.get("kind") not in BLOCK_KINDS:
                raise ReleaseContractError(f"{prefix}.blocker.kind est inconnu.")
            for field in ("cause", "owner", "action"):
                _required_text(blocker.get(field), f"{prefix}.blocker.{field}")
            decision_id = blocker.get("decision_id")
            if blocker["kind"] == "decision":
                if decision_id not in decision_ids:
                    raise ReleaseContractError(f"{prefix}.blocker.decision_id est inconnu.")
            elif decision_id is not None:
                raise ReleaseContractError(f"{prefix}.blocker.decision_id est réservé aux décisions.")
    for index, node in enumerate(values):
        _ids(node.get("depends_on"), f"work_graph[{index}].depends_on", ids)
        if node["id"] in node.get("depends_on", []):
            raise ReleaseContractError("Un travail ne peut pas dépendre de lui-même.")

    visiting: set[str] = set()
    visited: set[str] = set()
    by_id = {node["id"]: node for node in values}

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise ReleaseContractError("Le graphe de travail contient un cycle.")
        if node_id in visited:
            return
        visiting.add(node_id)
        for dependency in by_id[node_id].get("depends_on", []):
            visit(dependency)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in by_id:
        visit(node_id)
    return values, ids


def validate_release_contract(value: Any) -> dict[str, Any]:
    """Validate semantic invariants that JSON Schema alone cannot express."""
    if not isinstance(value, dict):
        raise ReleaseContractError("Le contrat de release doit être un objet.")
    required = {
        "$schema", "contract", "schema_version", "product", "version", "title", "state",
        "revision", "objective", "origin", "autonomy", "intake", "assumptions", "budget",
        "maturity", "capabilities", "journeys", "included", "excluded", "dependencies",
        "decisions", "criteria", "work_graph", "factory_improvements", "next_version",
    }
    if not required.issubset(value):
        missing = ", ".join(sorted(required - set(value)))
        raise ReleaseContractError(f"Contrat de release incomplet: {missing}.")
    if value.get("contract") != CONTRACT or value.get("schema_version") != SCHEMA_VERSION:
        raise ReleaseContractError("Version du contrat de release non prise en charge.")
    _required_text(value.get("product"), "product", pattern=re.compile(r"^[a-z0-9-]+$"))
    _required_text(value.get("version"), "version", pattern=VERSION_PATTERN)
    _required_text(value.get("title"), "title")
    if value.get("state") not in RELEASE_STATES:
        raise ReleaseContractError("État de release inconnu.")
    next_version = value.get("next_version")
    if next_version is not None:
        next_version = _required_text(next_version, "next_version", pattern=VERSION_PATTERN)
        if int(next_version[1:]) <= int(value["version"][1:]):
            raise ReleaseContractError("next_version doit être postérieure à la version courante.")

    revision = value.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        raise ReleaseContractError("revision doit être un entier positif.")

    _validate_objective(value.get("objective"))
    origin = _validate_origin(value.get("origin"))
    _validate_autonomy(value.get("autonomy"))
    _validate_intake(value.get("intake"))
    assumptions, assumption_ids = _validate_assumptions(value.get("assumptions"))
    _validate_budget(value.get("budget"))

    maturity = value.get("maturity")
    if not isinstance(maturity, dict) or set(maturity) != {"level", "label", "criteria"}:
        raise ReleaseContractError("La maturité doit contenir exactement level, label et criteria.")
    if maturity.get("level") not in {
        "intake", "not_ready", "partial", "release_ready", "production_autonomous",
    }:
        raise ReleaseContractError("Niveau de maturité inconnu.")
    _required_text(maturity.get("label"), "maturity.label")
    maturity_criteria = _ids(maturity.get("criteria"), "maturity.criteria")

    origin_kind = origin.get("kind")
    capabilities, capability_ids = _validate_scoped_blocks(
        value.get("capabilities"), "capabilities", origin_kind=origin_kind,
    )
    journeys, journey_ids = _validate_scoped_blocks(
        value.get("journeys"), "journeys", origin_kind=origin_kind,
    )
    for index, journey in enumerate(journeys):
        _ids(journey.get("capability_refs"), f"journeys[{index}].capability_refs", capability_ids)
        if not journey.get("capability_refs"):
            raise ReleaseContractError("Chaque parcours doit référencer une capacité.")

    for field in ("included", "excluded"):
        items, _ = _validate_scoped_blocks(value.get(field), field, origin_kind=origin_kind)
        for index, item in enumerate(items):
            if item.get("kind") not in {"product", "factory"}:
                raise ReleaseContractError(f"{field}[{index}].kind est invalide.")
    dependencies, dependency_ids = _validate_scoped_blocks(
        value.get("dependencies"), "dependencies", origin_kind=origin_kind,
    )
    for index, item in enumerate(dependencies):
        if item.get("required_for") is None:
            raise ReleaseContractError(f"dependencies[{index}].required_for manque.")
        _ids(item["required_for"], f"dependencies[{index}].required_for", capability_ids | journey_ids)

    decisions = _list(value.get("decisions"), "decisions", nonempty=False)
    decision_ids: set[str] = set()
    for index, item in enumerate(decisions):
        prefix = f"decisions[{index}]"
        if not isinstance(item, dict):
            raise ReleaseContractError(f"{prefix} doit être un objet.")
        decision_id = _required_text(item.get("id"), f"{prefix}.id", pattern=ID_PATTERN)
        if decision_id in decision_ids:
            raise ReleaseContractError(f"Décision dupliquée: {decision_id}.")
        decision_ids.add(decision_id)
        _required_text(item.get("title"), f"{prefix}.title")
        _required_text(item.get("source_ref"), f"{prefix}.source_ref")
        if item.get("status") not in {"accepted", "decision_required", "superseded"}:
            raise ReleaseContractError(f"{prefix}.status est inconnu.")
        if item.get("risk") not in {"low", "high"}:
            raise ReleaseContractError(f"{prefix}.risk est inconnu.")
        if not isinstance(item.get("revision"), int) or item["revision"] < 1:
            raise ReleaseContractError(f"{prefix}.revision doit être positive.")
        reserved_class = item.get("reserved_class")
        if reserved_class is not None and reserved_class not in RESERVED_CLASSES:
            raise ReleaseContractError(f"{prefix}.reserved_class est inconnu.")
        origin_question_id = item.get("origin_question_id")
        if origin_question_id is not None:
            _required_text(origin_question_id, f"{prefix}.origin_question_id", pattern=ID_PATTERN)
        _ids(item.get("capability_refs"), f"{prefix}.capability_refs", capability_ids)
        _ids(item.get("dependency_refs"), f"{prefix}.dependency_refs", dependency_ids)
        options = _list(item.get("options", []), f"{prefix}.options", nonempty=False)
        option_ids: set[str] = set()
        for option_index, option in enumerate(options):
            if not isinstance(option, dict) or set(option) != {"id", "label"}:
                raise ReleaseContractError(f"{prefix}.options[{option_index}] est invalide.")
            option_id = _required_text(option.get("id"), f"{prefix}.options[{option_index}].id", pattern=ID_PATTERN)
            _required_text(option.get("label"), f"{prefix}.options[{option_index}].label")
            if option_id in option_ids:
                raise ReleaseContractError(f"Option dupliquée dans {prefix}.")
            option_ids.add(option_id)

    criteria, criterion_ids = _validate_scoped_blocks(
        value.get("criteria"), "criteria", origin_kind=origin_kind,
    )
    if not set(maturity_criteria).issubset(criterion_ids):
        raise ReleaseContractError("maturity.criteria contient une référence inconnue.")
    for index, item in enumerate(criteria):
        _ids(item.get("capability_refs"), f"criteria[{index}].capability_refs", capability_ids)
        _ids(item.get("journey_refs"), f"criteria[{index}].journey_refs", journey_ids)
        if not item.get("capability_refs") and not item.get("journey_refs"):
            raise ReleaseContractError("Chaque critère doit être lié à une capacité ou un parcours.")
        _required_text(item.get("acceptance"), f"criteria[{index}].acceptance")

    work_graph, work_graph_ids = _validate_graph(
        value.get("work_graph"), criterion_ids, decision_ids, assumption_ids,
    )

    improvements, _ = _validate_scoped_blocks(
        value.get("factory_improvements"), "factory_improvements", origin_kind=origin_kind,
    )
    for index, item in enumerate(improvements):
        if item.get("kind") != "factory":
            raise ReleaseContractError(f"factory_improvements[{index}] doit porter le badge Factory.")
        work_ref = item.get("work_ref")
        if work_ref is not None:
            _required_text(work_ref, f"factory_improvements[{index}].work_ref", pattern=ID_PATTERN)
    if any(item.get("work_ref") == "af-cm1l" for item in capabilities):
        raise ReleaseContractError("af-cm1l est une amélioration Factory, jamais une capacité produit V1.")

    # Cross-checks deferred until every id pool (decisions, questions, criteria,
    # work_graph, assumptions) has been parsed.
    question_ids = {question["id"] for question in value["intake"]["questions"]}
    for index, conflict in enumerate(origin.get("conflicts", [])):
        if conflict["decision_id"] not in decision_ids:
            raise ReleaseContractError(f"origin.conflicts[{index}].decision_id est inconnu.")
    for index, question in enumerate(value["intake"]["questions"]):
        prefix = f"intake.questions[{index}]"
        produced_decision_id = question.get("produced_decision_id")
        if produced_decision_id is not None and produced_decision_id not in decision_ids:
            raise ReleaseContractError(f"{prefix}.produced_decision_id est inconnu.")
        produced_assumption_id = question.get("produced_assumption_id")
        if produced_assumption_id is not None and produced_assumption_id not in assumption_ids:
            raise ReleaseContractError(f"{prefix}.produced_assumption_id est inconnu.")
        if question.get("admitted_by") == "leverage":
            _ids(
                question["leverage_refs"], f"{prefix}.leverage_refs",
                criterion_ids | work_graph_ids,
            )
    for index, item in enumerate(decisions):
        origin_question_id = item.get("origin_question_id")
        if origin_question_id is not None and origin_question_id not in question_ids:
            raise ReleaseContractError(f"decisions[{index}].origin_question_id est inconnu.")
    scope_ref_pool = capability_ids | journey_ids | criterion_ids | work_graph_ids
    for index, item in enumerate(assumptions):
        _ids(item.get("scope_refs"), f"assumptions[{index}].scope_refs", scope_ref_pool)
        promoted = item.get("promoted_decision_id")
        if promoted is not None and promoted not in decision_ids:
            raise ReleaseContractError(f"assumptions[{index}].promoted_decision_id est inconnu.")

    return value


def load_release_contract(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseContractError(f"Contrat de release illisible: {exc}") from exc
    return validate_release_contract(value)


def transition_release(value: dict[str, Any], target_state: str) -> dict[str, Any]:
    """Return an idempotent, fail-closed release-state transition."""
    validate_release_contract(value)
    if target_state not in RELEASE_STATES:
        raise ReleaseContractError(f"Transition vers un état inconnu: {target_state}.")
    current = value["state"]
    if current == target_state:
        return copy.deepcopy(value)
    if current == "frozen":
        raise ReleaseContractError("Une release frozen est immuable.")
    if current == "intake" and target_state == "draft" and value["intake"]["state"] != "complete":
        raise ReleaseContractError(
            "intake.state doit être complete avant la transition intake -> draft."
        )
    next_state = {
        "intake": "draft",
        "draft": "approved",
        "approved": "executing",
        "executing": "frozen",
    }[current]
    if target_state != next_state:
        raise ReleaseContractError(f"Transition interdite: {current} → {target_state}.")
    result = copy.deepcopy(value)
    result["state"] = target_state
    return validate_release_contract(result)


def start_next_version(value: dict[str, Any], next_version: str) -> dict[str, Any]:
    """Freeze the current release before any later version can start."""
    validate_release_contract(value)
    wanted = _required_text(next_version, "next_version", pattern=VERSION_PATTERN)
    if value.get("next_version") != wanted:
        raise ReleaseContractError("La version suivante ne correspond pas au contrat approuvé.")
    if value["state"] not in {"executing", "frozen"}:
        raise ReleaseContractError("Une version suivante exige une release courante executing ou frozen.")
    frozen = transition_release(value, "frozen") if value["state"] != "frozen" else copy.deepcopy(value)
    return {"frozen_release": frozen, "next_version": wanted}


def select_campaign_work(value: dict[str, Any]) -> dict[str, Any]:
    """Select exactly one proven independent release node, or explain the stop."""
    validate_release_contract(value)
    if value["state"] not in {"approved", "executing"}:
        return {
            "selected": None,
            "reason": "release_not_executable",
            "owner": "PO",
            "action": "Faire approuver puis activer la release dans Git avant toute campagne.",
        }
    nodes = value["work_graph"]
    by_id = {item["id"]: item for item in nodes}
    active_dedupe = {
        item["dedupe_key"] for item in nodes
        if item["state"] in {"materialized", "active", "delivered"}
    }
    candidates = []
    unknown = []
    for item in sorted(nodes, key=lambda node: (node["order"], node["id"])):
        if item["kind"] != "product" or item["state"] != "candidate" or item.get("blocker"):
            continue
        if item["dedupe_key"] in active_dedupe:
            continue
        dependencies = [by_id[dependency] for dependency in item.get("depends_on", [])]
        if not all(dependency["state"] == "delivered" for dependency in dependencies):
            continue
        if item["independence"] != "proven":
            unknown.append(item)
            continue
        candidates.append(item)
    if candidates:
        selected = candidates[0]
        return {
            "selected": {
                "id": selected["id"],
                "work_ref": selected.get("work_ref"),
                "title": selected["title"],
                "criterion_refs": list(selected["criterion_refs"]),
                "dedupe_key": selected["dedupe_key"],
            },
            "reason": "proven_independent_work",
            "owner": "Mayor",
            "action": "Matérialiser uniquement ce premier travail traçable, sans réordonner la file.",
        }
    if unknown:
        return {
            "selected": None,
            "reason": "independence_unknown",
            "owner": "Mayor",
            "action": "Prouver l’indépendance du sous-graphe avant toute matérialisation.",
        }
    blockers = [item["blocker"] for item in nodes if item["state"] == "blocked" and item.get("blocker")]
    if blockers:
        blocker = sorted(blockers, key=lambda item: (item["kind"], item["cause"]))[0]
        return {
            "selected": None,
            "reason": f"blocked_{blocker['kind']}",
            "owner": blocker["owner"],
            "action": blocker["action"],
            "cause": blocker["cause"],
            "decision_id": blocker.get("decision_id"),
        }
    if all(item["status"] == "proven" for item in value["criteria"]):
        return {
            "selected": None,
            "reason": "release_target_proven",
            "owner": "none",
            "action": "Figer les preuves de la release; ne matérialiser aucun travail supplémentaire.",
        }
    return {
        "selected": None,
        "reason": "no_proven_independent_work",
        "owner": "Mayor",
        "action": "Conserver l’arrêt et enregistrer la preuve ou dépendance manquante.",
    }


def project_release(value: dict[str, Any]) -> dict[str, Any]:
    """Project the selected version for deterministic human surfaces."""
    validate_release_contract(value)
    status_labels = {
        "proven": "Prouvé", "partial": "Partiel", "unverified": "Non vérifié",
        "absent": "Absent", "out_of_version": "Hors version",
        "decision_required": "Décision requise", "assumed": "Supposé",
    }
    state_labels = {
        "intake": "Intake", "draft": "Brouillon", "approved": "Approuvée",
        "executing": "En exécution", "frozen": "Figée",
    }
    result = copy.deepcopy(value)
    result.pop("$schema", None)
    result["state_label"] = state_labels[value["state"]]
    result["truth_state"] = value["state"]
    result["operational_state"] = value["state"]
    result["operational_state_label"] = state_labels[value["state"]]
    for field in (
        "capabilities", "journeys", "included", "excluded", "dependencies",
        "criteria", "factory_improvements",
    ):
        for item in result[field]:
            item["status_label"] = status_labels[item["status"]]
    result["campaign"] = select_campaign_work(value)
    decisions = [item for item in value["decisions"] if item["status"] == "decision_required"]
    result["intervention"] = (
        {
            "decision_id": decisions[0]["id"],
            "title": decisions[0]["title"],
            "risk": decisions[0]["risk"],
            "deep_link": f"#view=project&releaseDecision={decisions[0]['id']}",
        }
        if decisions else None
    )
    result["model_calls"] = 0
    return result


def project_target_doc(value: dict[str, Any]) -> dict[str, Any]:
    """Project ADR-0015 §6 derived interactive documentation.

    Pure and deterministic: reads only the already-validated release
    contract, never live state and never a model. One work_graph carries
    every view below by filtering/overlaying, rather than a new graph type
    per concern.
    """
    validate_release_contract(value)

    chain_edges: list[dict[str, str]] = []
    for journey in value["journeys"]:
        for capability_id in journey["capability_refs"]:
            chain_edges.append({"kind": "journey_to_capability", "from": journey["id"], "to": capability_id})
    for criterion in value["criteria"]:
        for capability_id in criterion.get("capability_refs", []):
            chain_edges.append({"kind": "capability_to_criterion", "from": capability_id, "to": criterion["id"]})
        for journey_id in criterion.get("journey_refs", []):
            chain_edges.append({"kind": "journey_to_criterion", "from": journey_id, "to": criterion["id"]})
    for node in value["work_graph"]:
        for criterion_id in node["criterion_refs"]:
            chain_edges.append({"kind": "criterion_to_work", "from": criterion_id, "to": node["id"]})

    work_graph_edges = [
        {"from": dependency, "to": node["id"]}
        for node in value["work_graph"]
        for dependency in node.get("depends_on", [])
    ]

    blocked_nodes = [node for node in value["work_graph"] if node["state"] == "blocked" and node.get("blocker")]
    blocked_ids = {node["id"] for node in blocked_nodes}
    blocker_subgraph = {
        "nodes": [
            {
                "id": node["id"],
                "title": node["title"],
                "criterion_refs": list(node["criterion_refs"]),
                "blocker": node["blocker"],
            }
            for node in blocked_nodes
        ],
        "edges": [
            edge for edge in work_graph_edges
            if edge["from"] in blocked_ids or edge["to"] in blocked_ids
        ],
    }

    return {
        "product": value["product"],
        "version": value["version"],
        "chain": {
            "journeys": [{"id": item["id"], "title": item["title"]} for item in value["journeys"]],
            "capabilities": [{"id": item["id"], "title": item["title"]} for item in value["capabilities"]],
            "criteria": [
                {"id": item["id"], "title": item["title"], "acceptance": item["acceptance"]}
                for item in value["criteria"]
            ],
            "edges": chain_edges,
        },
        "work_graph": {
            "nodes": [
                {
                    "id": node["id"],
                    "title": node["title"],
                    "kind": node["kind"],
                    "state": node["state"],
                    "order": node["order"],
                    "work_ref": node.get("work_ref"),
                    "criterion_refs": list(node["criterion_refs"]),
                    "assumption_refs": list(node.get("assumption_refs") or []),
                }
                for node in value["work_graph"]
            ],
            "edges": work_graph_edges,
        },
        "assumption_overlay": [
            {
                "id": item["id"],
                "title": item["title"],
                "status": item["status"],
                "confidence": item["confidence"],
                "scope_refs": list(item["scope_refs"]),
            }
            for item in value["assumptions"]
        ],
        "blocker_subgraph": blocker_subgraph,
        "work_ref_index": {node["id"]: node.get("work_ref") for node in value["work_graph"]},
        "model_calls": 0,
    }


def project_operational_release(
    release: dict[str, Any], campaign: dict[str, Any],
) -> dict[str, Any]:
    """Overlay runtime execution state without changing versioned Git truth."""
    if not isinstance(release, dict) or release.get("contract") != CONTRACT:
        raise ReleaseContractError("Projection de release invalide.")
    if not isinstance(campaign, dict) or not isinstance(campaign.get("enabled"), bool):
        raise ReleaseContractError("Projection de campagne invalide.")
    result = copy.deepcopy(release)
    truth_state = result.get("truth_state") or result.get("state")
    if truth_state not in RELEASE_STATES:
        raise ReleaseContractError("État Git de release invalide.")
    operational = truth_state
    if campaign["enabled"]:
        if truth_state in {"intake", "draft"}:
            raise ReleaseContractError("Une campagne ne peut pas exécuter une release Git intake ou draft.")
        if truth_state in {"approved", "executing"}:
            operational = "executing"
    labels = {
        "intake": "Intake Git", "draft": "Brouillon Git", "approved": "Approuvée · campagne non activée",
        "executing": "En exécution par la campagne", "frozen": "Figée",
    }
    result["truth_state"] = truth_state
    result["operational_state"] = operational
    result["operational_state_label"] = labels[operational]
    return result
