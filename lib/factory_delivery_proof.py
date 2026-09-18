#!/usr/bin/env python3
"""Delivery-proof completeness: was a closed delivery Bead actually documented?

ADR-0016 section 5.3 invariant 2 says closing a delivery bead without its six
proof fields (gc.delivery_status, gc.work_outcome, gc.github_repo,
gc.pr_number, gc.pr_head, gc.merge_commit) must be rejected, never silent.
bin/deliver-close is the sanctioned path and enforces this on the way in. On
2026-09-16 delivery bead af-7700 was closed with a raw `gc bd close` instead,
bypassing deliver-close entirely, and sat with none of the six fields for
about half a day before anyone noticed -- because nothing checked the way
*out*, only the door bin/deliver-close itself guards.

This module is the way-out check: given the beads already fetched by
`gc bd list --all --status closed --label-any product-goal --json` (the same
label factory_cockpit.py already uses to mean "delivery/goal outcome", see
lib/factory_cockpit.py's PRODUCT_MARKERS), it finds closed delivery beads
missing (or holding an invalid) proof field.

A closed product-goal bead whose gc.work_outcome explicitly says the goal was
NOT shipped (cancelled, descoped, a no-op, ...) is not a delivery that needs
proof and must not be flagged -- only a bead that looks like or claims to be a
merged delivery is in scope.

CLI: reads a JSON bead array on stdin (as `gc bd list --json` produces) and
prints one line per incomplete bead, fields separated by ASCII unit separator
0x1F rather than a tab — a tab is bash `read`'s own IFS-whitespace character,
which silently collapses adjacent delimiters and drops empty fields (exactly
the repo/pr-number fields that are legitimately empty here):

    <id>\x1f<missing,comma,separated>\x1f<github_repo-or-empty>\x1f<pr_number-or-empty>\x1f<already_flagged 0|1>

`bin/factory-guard` (or a standalone caller) drives the rest: verifying
repo+pr via `gh pr view` and either backfilling the six fields from that
verified evidence, or flagging the bead for a human once, idempotently.

Adjacent gap (af-1xz1g): af-x45xw was closed with gc.outcome=pass and its
own gc.pr_url on 2026-09-18 while that PR was still OPEN and CI was red --
a raw close that bypassed bin/deliver-close entirely. It carried none of
the `product-goal` label the check above requires, so the check above never
saw it. --mode claimed-shipped is the sibling check for that shape: any
CLOSED bead, regardless of label, carrying gc.outcome=pass or
gc.work_outcome=shipped plus a gc.pr_url, that does NOT already carry the
six proof fields validated (nothing more to verify there -- either
deliver-close wrote them, or the check above already backfilled them from
verified evidence). It parses owner/repo and PR number out of gc.pr_url and
prints one line per bead in scope, again 0x1F-separated:

    <id>\x1f<github_repo>\x1f<pr_number>\x1f<already_flagged 0|1>

The caller verifies with the same `gh pr view` path and flags
(gc.delivery_proof_flagged_at) exactly once whatever does not verify as
merged. Reopening a flagged bead stays a human/Mayor call.
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any

PROOF_FIELDS = (
    "gc.delivery_status",
    "gc.work_outcome",
    "gc.github_repo",
    "gc.pr_number",
    "gc.pr_head",
    "gc.merge_commit",
)

# The label factory_cockpit.py already treats as "this bead is a product
# delivery/goal outcome" (lib/factory_cockpit.py product_markers / the
# --label-any query it issues). Reusing it means this check finds exactly the
# beads the rest of the Factory already calls delivery beads, not a new
# taxonomy invented here.
DELIVERY_LABEL = "product-goal"

# work_outcome values that mean "this closed goal was deliberately not
# shipped" -- these are not delivery beads awaiting proof, and must never be
# flagged, or every legitimately-cancelled goal becomes permanent noise.
NON_SHIPPED_OUTCOMES = {"no-op", "cancelled", "dropped", "wont-fix", "descoped", "none", "not-shipped"}

REPO_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9-]{0,37}[A-Za-z0-9])?/[A-Za-z0-9._-]{1,100}$")
PR_NUMBER_RE = re.compile(r"^[1-9][0-9]*$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
PR_URL_RE = re.compile(
    r"^https?://github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?/[A-Za-z0-9._-]{1,100})/pull/([1-9][0-9]*)/?$"
)

FLAGGED_AT_KEY = "gc.delivery_proof_flagged_at"
FLAGGED_MISSING_KEY = "gc.delivery_proof_missing"


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _valid_repo(value: Any) -> bool:
    return bool(REPO_RE.match(_text(value)))


def _valid_pr_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value > 0
    return bool(PR_NUMBER_RE.match(_text(value)))


def _valid_sha(value: Any) -> bool:
    return bool(SHA_RE.match(_text(value)))


def missing_proof_fields(metadata: dict[str, Any]) -> list[str]:
    """Return the subset of the six proof fields that are absent or invalid."""
    missing = []
    if _text(metadata.get("gc.delivery_status")) != "merged":
        missing.append("gc.delivery_status")
    if _text(metadata.get("gc.work_outcome")) != "shipped":
        missing.append("gc.work_outcome")
    if not _valid_repo(metadata.get("gc.github_repo")):
        missing.append("gc.github_repo")
    if not _valid_pr_number(metadata.get("gc.pr_number")):
        missing.append("gc.pr_number")
    if not _valid_sha(metadata.get("gc.pr_head")):
        missing.append("gc.pr_head")
    if not _valid_sha(metadata.get("gc.merge_commit")):
        missing.append("gc.merge_commit")
    return missing


def is_delivery_bead(bead: dict[str, Any]) -> bool:
    if not isinstance(bead, dict):
        return False
    if _text(bead.get("status")) != "closed":
        return False
    labels = bead.get("labels") or []
    if not isinstance(labels, list) or DELIVERY_LABEL not in labels:
        return False
    metadata = bead.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    outcome = _text(metadata.get("gc.work_outcome")).lower()
    if outcome in NON_SHIPPED_OUTCOMES:
        return False
    return True


def assess_bead(bead: dict[str, Any]) -> dict[str, Any] | None:
    """Return an incompleteness report for one bead, or None if it is fine
    (either not a delivery bead in scope, or fully documented)."""
    if not is_delivery_bead(bead):
        return None
    metadata = bead.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    missing = missing_proof_fields(metadata)
    if not missing:
        return None
    repo = _text(metadata.get("gc.github_repo"))
    pr_number_raw = metadata.get("gc.pr_number")
    pr_number = ""
    if isinstance(pr_number_raw, int) and pr_number_raw > 0:
        pr_number = str(pr_number_raw)
    elif _valid_pr_number(pr_number_raw):
        pr_number = _text(pr_number_raw)
    verifiable = bool(repo and _valid_repo(repo) and pr_number)
    return {
        "id": _text(bead.get("id")),
        "title": _text(bead.get("title")),
        "missing": missing,
        "github_repo": repo if _valid_repo(repo) else "",
        "pr_number": pr_number,
        "verifiable": verifiable,
        "already_flagged": bool(_text(metadata.get(FLAGGED_AT_KEY))),
    }


def find_incomplete(beads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reports = []
    for bead in beads:
        report = assess_bead(bead)
        if report is not None:
            reports.append(report)
    return reports


def _parse_pr_url(value: Any) -> tuple[str, str] | None:
    match = PR_URL_RE.match(_text(value))
    if not match:
        return None
    return match.group(1), match.group(2)


def _claims_shipped(metadata: dict[str, Any]) -> bool:
    return (
        _text(metadata.get("gc.outcome")).lower() == "pass"
        or _text(metadata.get("gc.work_outcome")).lower() == "shipped"
    )


def is_claimed_shipped_bead(bead: dict[str, Any]) -> bool:
    """A closed bead (any label, not just product-goal) that claims a shipped
    outcome via gc.outcome=pass or gc.work_outcome=shipped and names its own
    gc.pr_url, but does not already carry the six verified ADR-0016 proof
    fields -- the af-x45xw shape (af-1xz1g)."""
    if not isinstance(bead, dict):
        return False
    if _text(bead.get("status")) != "closed":
        return False
    metadata = bead.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    if not _claims_shipped(metadata):
        return False
    if _parse_pr_url(metadata.get("gc.pr_url")) is None:
        return False
    if not missing_proof_fields(metadata):
        return False  # already fully proven -- nothing new to verify here
    return True


def assess_claimed_shipped_bead(bead: dict[str, Any]) -> dict[str, Any] | None:
    if not is_claimed_shipped_bead(bead):
        return None
    metadata = bead.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    repo, pr_number = _parse_pr_url(metadata.get("gc.pr_url"))  # type: ignore[misc]
    return {
        "id": _text(bead.get("id")),
        "title": _text(bead.get("title")),
        "github_repo": repo,
        "pr_number": pr_number,
        "already_flagged": bool(_text(metadata.get(FLAGGED_AT_KEY))),
    }


def find_claimed_shipped(beads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reports = []
    for bead in beads:
        report = assess_claimed_shipped_bead(bead)
        if report is not None:
            reports.append(report)
    return reports


def main() -> int:
    mode = "delivery"
    args = sys.argv[1:]
    if args:
        if len(args) == 2 and args[0] == "--mode":
            mode = args[1]
        else:
            print(f"factory_delivery_proof: unrecognized arguments: {args}", file=sys.stderr)
            return 2
    if mode not in ("delivery", "claimed-shipped"):
        print(f"factory_delivery_proof: unknown --mode {mode!r}", file=sys.stderr)
        return 2

    raw = sys.stdin.read()
    try:
        value = json.loads(raw) if raw.strip() else []
    except json.JSONDecodeError:
        print("delivery-proof beads payload unreadable (invalid JSON)", file=sys.stderr)
        return 1
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        print("delivery-proof beads payload unreadable (not a list)", file=sys.stderr)
        return 1

    if mode == "delivery":
        for report in find_incomplete(value):
            print("\x1f".join([
                report["id"],
                ",".join(report["missing"]),
                report["github_repo"],
                report["pr_number"],
                "1" if report["already_flagged"] else "0",
            ]))
    else:
        for report in find_claimed_shipped(value):
            print("\x1f".join([
                report["id"],
                report["github_repo"],
                report["pr_number"],
                "1" if report["already_flagged"] else "0",
            ]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
