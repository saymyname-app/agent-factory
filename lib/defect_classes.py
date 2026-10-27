#!/usr/bin/env python3
"""The register of defect classes, docs/DEFECT_CLASSES.md, read by the tools
that hold the method of study B (af-npz9v1.25,
docs/research/2026-10-22-causes-racines-incidents.md, § 6).

    defect_classes.py check-pr-body [--registry FILE] < body
    defect_classes.py count --since YYYY-MM-DD [--repo DIR]

From 15 to 22/10/2026, about 70 Factory fixes fell into three classes, each
back 5 to 7 times: every fix repaired the place it was seen and wrote the rest
« hors périmètre ». The fixes that never came back are those that put a check
on the whole class.

- `load` reads the register: one `## CODE — title` heading per class, with
  the fields `Invariant`, `Contrôle`, `Occurrences` and `Ouvertes`.
- `check-pr-body` names the lines a maintenance pull request lacks
  (`Catégorie :` a code of the register, `Où ailleurs :`, `Contrôle de
  catégorie :`); `bin/pr-autopilot` does not arm a fix without them. A
  change that fixes no defect writes `Catégorie : aucune — <why>`.
- `count` counts the merged pull requests of each class since a date, from
  those same lines: the measure of whether the method works. A class that
  comes back while it has a check means the check is incomplete.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REGISTRY = Path(__file__).resolve().parents[1] / "docs" / "DEFECT_CLASSES.md"
FIELDS = ("Invariant", "Contrôle", "Occurrences", "Ouvertes")
NO_CLASS = "aucune"
HEADING = re.compile(r"^## ([A-Z][A-Z0-9]*) — (.+)$")
FIELD = re.compile(r"^- ([^:]+?) : (.*)$")
# The commands a `Contrôle` field names, between backticks.
COMMAND = re.compile(r"`((?:python3|bash|sh) [^`]+)`")
PR_LINES = {
    "category": re.compile(r"^\W*Catégorie\W*:\s*(\S.*)$", re.M | re.I),
    "elsewhere": re.compile(r"^\W*Où ailleurs\W*:\s*(\S.*)$", re.M | re.I),
    "check": re.compile(r"^\W*Contrôle de catégorie\W*:\s*(\S.*)$", re.M | re.I),
}
PR_LABELS = {"category": "Catégorie :", "elsewhere": "Où ailleurs :", "check": "Contrôle de catégorie :"}


class RegistryError(Exception):
    pass


def load(path: Path = REGISTRY) -> dict[str, dict]:
    """Every class of the register by its code; refuses a class that lacks a
    field, so that a check never reads half an entry."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RegistryError(f"registre illisible : {path} : {exc}") from exc
    classes: dict[str, dict] = {}
    current: dict | None = None
    field: str | None = None
    for line in lines:
        heading = HEADING.match(line)
        if heading:
            current = {"code": heading.group(1), "title": heading.group(2).strip()}
            classes[current["code"]] = current
            field = None
            continue
        if line.startswith("#"):
            current = field = None
            continue
        if current is None:
            continue
        item = FIELD.match(line)
        if item and item.group(1) in FIELDS:
            field = item.group(1)
            current[field] = item.group(2).strip()
        elif field and line.startswith("  ") and line.strip():
            current[field] += " " + line.strip()
        elif not line.strip():
            field = None
    if not classes:
        raise RegistryError(f"registre sans catégorie : {path}")
    for code, entry in classes.items():
        missing = [name for name in FIELDS if not entry.get(name)]
        if missing:
            raise RegistryError(f"catégorie {code} incomplète dans {path} : {', '.join(missing)}")
        entry["commands"] = COMMAND.findall(entry["Contrôle"])
    return classes


def pr_category(body: str) -> str | None:
    found = PR_LINES["category"].search(body or "")
    # `**Catégorie :** P`: the emphasis closes after the colon.
    return found.group(1).strip().lstrip("*` ") if found else None


def category_code(value: str) -> str:
    """`P`, `P — processus…` or `aucune — …`: the code alone."""
    return re.split(r"[\s—–,;:(-]", value.strip(), maxsplit=1)[0].strip("`*")


def check_pr_body(body: str, classes: dict[str, dict]) -> list[str]:
    """What the body of a maintenance pull request lacks, empty when complete."""
    problems = []
    category = pr_category(body)
    if category is None:
        problems.append(f"ligne « {PR_LABELS['category']} » absente")
    else:
        code = category_code(category)
        if code.lower() == NO_CLASS:
            if len(category.split(None, 1)) < 2:
                problems.append(f"« {PR_LABELS['category']} {NO_CLASS} » sans sa raison")
            return problems
        if code not in classes:
            problems.append(f"catégorie « {code} » absente de docs/DEFECT_CLASSES.md (codes : "
                            f"{', '.join(sorted(classes))}, ou « {NO_CLASS} — <raison> »)")
    for key in ("elsewhere", "check"):
        if not PR_LINES[key].search(body or ""):
            problems.append(f"ligne « {PR_LABELS[key]} » absente")
    return problems


def merged_since(since: str, repo: Path) -> list[dict]:
    gh = os.environ.get("GH_BIN") or "gh"
    argv = [gh, "pr", "list", "--state", "merged", "--limit", "500", "--search", f"merged:>={since}",
            "--json", "number,title,body,mergedAt"]
    proc = subprocess.run(argv, cwd=repo, text=True, capture_output=True, timeout=120)
    if proc.returncode:
        raise RegistryError(f"gh pr list a échoué : {(proc.stderr or proc.stdout).strip()[:300]}")
    return json.loads(proc.stdout or "[]")


def count(prs: list[dict], classes: dict[str, dict]) -> dict:
    """The merged pull requests of each class, and those that name none."""
    by_class: dict[str, list[int]] = {code: [] for code in classes}
    none, untagged = [], []
    for pr in sorted(prs, key=lambda p: p.get("number") or 0):
        category = pr_category(pr.get("body") or "")
        code = category_code(category) if category else None
        if code in by_class:
            by_class[code].append(pr["number"])
        elif code and code.lower() == NO_CLASS:
            none.append(pr["number"])
        else:
            untagged.append(pr["number"])
    return {"by_class": by_class, "no_defect": none, "untagged": untagged}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="defect_classes.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check-pr-body", help="the lines a maintenance PR body (stdin) lacks")
    counting = sub.add_parser("count", help="merged PRs by class since a date")
    counting.add_argument("--since", required=True)
    counting.add_argument("--repo", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    try:
        classes = load(args.registry)
        if args.command == "check-pr-body":
            problems = check_pr_body(sys.stdin.read(), classes)
            print("\n".join(problems))
            return 1 if problems else 0
        print(json.dumps({"since": args.since, **count(merged_since(args.since, args.repo), classes)},
                         indent=2, ensure_ascii=False))
        return 0
    except (RegistryError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"refus : {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
