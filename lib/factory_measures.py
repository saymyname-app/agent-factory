#!/usr/bin/env python3
"""Pure logic for B09 measures: lost decisions, escaped defects, human
rework, maintainability, elapsed time and tokens, kept separate by
comparable work class (docs/FACTORY_OBSERVE.md).

Same discipline as lib/factory_observe.py and P06's role-qualification
manifest: a measures document is a caller-supplied JSON record, validated
against one schema, then read by a pure aggregator. No I/O here; the caller
(bin/factory-observe) owns file reads and writes.

Keeping every metric namespaced under its own work class -- never summed or
blended across classes -- is the mechanism, not a policy note: `aggregate_by_class`
returns one independent dict per class, so a bug that merged two classes'
numbers would show up immediately as a key or value mismatch in the caller's
own dict, not as a silent average.
"""

from __future__ import annotations

from typing import Any

MEASURES_CONTRACT = "agent-factory-observe-measures/v1"
MEASURE_KEYS = (
    "lost_decisions",
    "escaped_defects",
    "human_rework",
    "maintainability",
    "elapsed_seconds",
    "tokens",
)


class MeasuresError(ValueError):
    pass


def validate_measures(value: Any) -> dict[str, Any]:
    """Validate a measures document: `{"contract", "work_classes": {name: {key: number, ...}}}`.

    Every declared work class must carry every metric key with a numeric,
    non-boolean value -- a class missing a key would silently read as zero
    downstream, which is exactly the cross-contamination this schema exists
    to prevent.
    """
    if not isinstance(value, dict) or value.get("contract") != MEASURES_CONTRACT:
        raise MeasuresError(f"measures document must declare contract {MEASURES_CONTRACT!r}")
    work_classes = value.get("work_classes")
    if not isinstance(work_classes, dict) or not work_classes:
        raise MeasuresError("work_classes must be a non-empty object")
    for class_name, metrics in work_classes.items():
        if not isinstance(class_name, str) or not class_name.strip():
            raise MeasuresError("each work class name must be non-empty text")
        if not isinstance(metrics, dict):
            raise MeasuresError(f"{class_name}: metrics must be an object")
        missing = set(MEASURE_KEYS) - metrics.keys()
        if missing:
            raise MeasuresError(f"{class_name}: missing measure keys: {sorted(missing)}")
        extra = metrics.keys() - set(MEASURE_KEYS)
        if extra:
            raise MeasuresError(f"{class_name}: unknown measure keys: {sorted(extra)}")
        for key in MEASURE_KEYS:
            metric = metrics[key]
            if not isinstance(metric, (int, float)) or isinstance(metric, bool):
                raise MeasuresError(f"{class_name}.{key}: must be a number")
    return value


def aggregate_by_class(measures: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Return one independent metrics dict per work class, unmodified and
    unmerged -- the identity projection that proves separation holds: no
    metric from one class ever appears, blended or otherwise, under another.
    """
    return {
        class_name: {key: metrics[key] for key in MEASURE_KEYS}
        for class_name, metrics in measures["work_classes"].items()
    }


def compare_classes(measures: dict[str, Any], class_a: str, class_b: str) -> dict[str, Any]:
    """Per-metric delta between two work classes -- for a caller that wants
    to show "class A costs more lost decisions than class B" without ever
    summing the two into one number.
    """
    by_class = aggregate_by_class(measures)
    if class_a not in by_class:
        raise MeasuresError(f"unknown work class: {class_a}")
    if class_b not in by_class:
        raise MeasuresError(f"unknown work class: {class_b}")
    return {
        key: by_class[class_a][key] - by_class[class_b][key]
        for key in MEASURE_KEYS
    }
