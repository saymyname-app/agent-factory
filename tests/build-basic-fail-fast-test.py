#!/usr/bin/env python3
"""Regression contract for build-basic's top-level fail-fast scope."""

from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]
FORMULA = ROOT / "formulas" / "build-basic.formula.toml"
REVIEW_EXPANSION = ROOT / "formulas" / "build-basic-review-scoped.formula.toml"

PIPELINE = [
    "prepare",
    "requirements",
    "plan",
    "plan-review",
    "decompose",
    "implement",
    "implement-same-session",
    "summarize-implementation",
    "review",
    "finalize",
    "publish",
]


def main() -> None:
    with FORMULA.open("rb") as handle:
        formula = tomllib.load(handle)
    with REVIEW_EXPANSION.open("rb") as handle:
        review_expansion = tomllib.load(handle)

    steps = {step["id"]: step for step in formula["steps"]}
    assert len(steps) == len(formula["steps"]), "duplicate step id"

    body = steps.get("build-pipeline")
    assert body is not None, "build-basic lost its fail-fast scope body"
    assert body.get("needs") == PIPELINE, (
        "scope body must sink every top-level pipeline stage in execution order"
    )
    assert body.get("metadata") == {
        "gc.kind": "scope",
        "gc.scope_name": "build-pipeline",
        "gc.scope_role": "body",
    }

    for step_id in PIPELINE:
        step = steps.get(step_id)
        assert step is not None, (
            f"{step_id} must be overridden locally; an inherited unscoped stage "
            "would bypass fail-fast"
        )
        metadata = step.get("metadata", {})
        assert metadata.get("gc.scope_ref") == "build-pipeline", step_id
        assert metadata.get("gc.scope_role") == "member", step_id
        assert metadata.get("gc.on_fail") == "abort_scope", step_id

    # The incident failed at the requirements control. Every artifact producer
    # and review stage after it must be in the same aborted scope, so Gas City's
    # ReconcileClosedScopeMember path closes it skipped before it can be claimed.
    downstream = PIPELINE[PIPELINE.index("requirements") + 1 :]
    assert {steps[step_id]["metadata"]["gc.scope_ref"] for step_id in downstream} == {
        "build-pipeline"
    }
    assert "review" in downstream

    # Expansion-host metadata is not propagated by Gas City's compiler.  The
    # generated setup, loop control, and final target must therefore opt into
    # the outer scope in the local expansion itself.  In particular, closing
    # the loop control skipped prevents the controller from materializing a
    # second review iteration after an earlier hard gate failure.
    assert review_expansion.get("type") == "expansion"
    assert review_expansion.get("formula") == "build-basic-review-scoped"
    expansion_steps = {step["id"]: step for step in review_expansion["template"]}
    assert set(expansion_steps) == {
        "{target}.setup-build-basic-review",
        "{target}.build-basic-review-loop",
        "{target}",
    }
    review_loop = expansion_steps["{target}.build-basic-review-loop"]
    assert review_loop.get("children"), "review loop lost its generated lanes"
    assert review_loop.get("check", {}).get("max_attempts") == 6, (
        "review loop must remain a ralph control whose descendants are swept on abort"
    )
    for step_id, step in expansion_steps.items():
        metadata = step.get("metadata", {})
        assert metadata.get("gc.scope_ref") == "build-pipeline", step_id
        assert metadata.get("gc.scope_role") == "member", step_id
        assert metadata.get("gc.on_fail") == "abort_scope", step_id

    print(
        "ok: build-basic hard gate aborts every downstream stage and review control"
    )


if __name__ == "__main__":
    main()
