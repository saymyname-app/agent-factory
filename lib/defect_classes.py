#!/usr/bin/env python3
"""The register of defect classes, docs/DEFECT_CLASSES.md, read by the tools
that hold the method of study B (af-npz9v1.25,
docs/research/2026-10-22-causes-racines-incidents.md, § 6).

    defect_classes.py check-pr-body [--registry FILE] [--branch NAME] [--github-repo OWNER/NAME] < body
    defect_classes.py maintenance-branches
    defect_classes.py count --since YYYY-MM-DD [--repo DIR]
    defect_classes.py count --by-rule --since YYYY-MM-DD [--repo DIR] [--baseline FILE]

From 15 to 22/10/2026, about 70 Factory fixes fell into three classes, each
back 5 to 7 times: every fix repaired the place it was seen and wrote the rest
« hors périmètre ». The fixes that never came back are those that put a check
on the whole class.

- `load` reads the register: one `## CODE — title` heading per class, with
  the fields `Invariant`, `Contrôle`, `Occurrences` and `Ouvertes`, and an
  optional `Règles` list: the concrete rules of the class, each with a stable
  id `<CODE>.<slug>`, a checkable sentence and its single passage point.
- `check-pr-body` names what the body of a maintenance pull request lacks
  against the lines `docs/DELIVERY.md` (« Where else? ») defines, the one
  source of that form; `bin/pr-autopilot` does not arm a fix without them,
  and the CI job « Maintenance form » is red without them (af-56yoam.2,
  decision D2). Both read the maintenance branches from
  `MAINTENANCE_BRANCHES` here. A rule already fixed by a merged pull request
  (the baseline, then the `Règle :` lines merged since) comes back only as
  « prévue (<bead>) » or as « glissement » through the rule's passage point.
- `count` counts the merged pull requests of each class since a date, from
  those same lines: the measure of whether the method works. A class that
  comes back while it has a check means the check is incomplete.
- `count --by-rule` counts, per rule and per month (Paris), the first fixes,
  the planned repeats and the slips (af-56yoam.1). A family groups 3 to 30
  different rules, so a count by family never says whether a rule comes back
  (analysis of 152 PRs, 23/11/2026). The pull requests of the baseline
  (docs/defect-rules-baseline.tsv) are read from it; a later one from its
  `Règle :` line: « prévue » on that line marks a planned repeat, a rule
  already fixed by an earlier merged PR is a slip, otherwise a first fix.
- `d1` gives decision D1 (af-56yoam.5): the share of slips among the fix
  pull requests of a period, and the slips on a closed rule (« Fermée le
  JJ/MM/AAAA par #N. » after its passage in the register) merged after the
  day it was closed.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from bounded_process import run as bounded_run

REGISTRY = Path(__file__).resolve().parents[1] / "docs" / "DEFECT_CLASSES.md"
BASELINE = Path(__file__).resolve().parents[1] / "docs" / "defect-rules-baseline.tsv"
FIELDS = ("Invariant", "Contrôle", "Occurrences", "Ouvertes")
NO_CLASS = "aucune"
HEADING = re.compile(r"^## ([A-Z][A-Z0-9]*) — (.+)$")
FIELD = re.compile(r"^- ([^:]+?) : (.*)$")
RULES_FIELD = re.compile(r"^- Règles :\s*$")
RULE = re.compile(r"^  - `([A-Z][A-Z0-9]*\.[a-z0-9][a-z0-9-]*)` : (.*)$")
PASSAGE = re.compile(r"\s*Passage\s*:\s*")
# The commands a `Contrôle` field names, between backticks.
COMMAND = re.compile(r"`((?:python3|bash|sh) [^`]+)`")
PR_LINES = {
    "category": re.compile(r"^\W*Catégorie\W*:\s*(\S.*)$", re.M | re.I),
    "elsewhere": re.compile(r"^\W*Où ailleurs\W*:\s*(\S.*)$", re.M | re.I),
    "check": re.compile(r"^\W*Contrôle de catégorie\W*:\s*(\S.*)$", re.M | re.I),
    "rule": re.compile(r"^\W*Règle\W*:\s*(\S.*)$", re.M | re.I),
    "passage": re.compile(r"^\W*Point de passage\W*:\s*(\S.*)$", re.M | re.I),
}
PR_LABELS = {"category": "Catégorie :", "elsewhere": "Où ailleurs :", "check": "Contrôle de catégorie :",
             "rule": "Règle :", "passage": "Point de passage :"}
# The branches of a maintenance pull request of the Factory: a fix, or a
# do-work ticket of this repository. bin/pr-autopilot (maintenance_form_gate)
# and the CI job « Maintenance form » read this one list.
MAINTENANCE_BRANCHES = ("fix/", "do-work/")
# « Où ailleurs : `<command>` → <result> »: a command between backticks, then
# a result after the arrow. Whether the command lists the callers of the
# decision point is for review (af-56yoam.3), not for this check.
ELSEWHERE_FORM = re.compile(r"`[^`]+`.*?(?:→|->)\s*\S")
PLANNED = re.compile(r"pr[ée]vue\s*\(\s*[^)\s]+\s*\)", re.I)
SLIP = re.compile(r"glissement", re.I)
NATURES = ("premiere", "prevue", "glissement")
# A rule `<CODE>.autre` holds the isolated defects of a family: never a slip.
ISOLATED = ".autre"
PARIS = ZoneInfo("Europe/Paris")
# Decision D1, frozen on 23/11/2026 (Benjamin, 19:41 Paris, « Fait », to the
# proposal to apply its new form if the blind judge agreed at 70 % or more;
# comment of 19:50 on af-56yoam): the share of slips among the fix pull
# requests (baseline rows other than `aucune`, then the `Règle :` lines) is at
# most 30 % from 01/12 to 20/12/2026, against 86/140 = 61 % from 01/11 to
# 23/11; and zero slip on a closed rule. Review on 21/12/2026 (af-56yoam.4).
# Stop criterion (Benjamin, 24/11/2026 00:06 Paris, « Oui, ajoute-le »): at the
# review, a share still above 45 %, or more than one refusal of the gate in
# three judged unjustified, withdraws the required check « Maintenance form ».
D1 = {"review": "2026-12-21", "bead": "af-56yoam.4", "period": ["2026-12-01", "2026-12-20"],
      "target_share": 0.30, "reference": ["2026-11-01", "2026-11-23"],
      "stop": {"share_above": 0.45, "unjustified_refusals_above": "1/3"}}
# « Fermée le JJ/MM/AAAA par #N. » after a rule's passage: its single passage
# point was delivered by that pull request. Any later slip on it reopens it.
CLOSED = re.compile(r"\s*Fermée le (\d{2})/(\d{2})/(\d{4}) par #(\d+)\.?\s*$", re.I)


class RegistryError(Exception):
    pass


def load(path: Path = REGISTRY) -> dict[str, dict]:
    """Every class of the register by its code; refuses a class that lacks a
    field, so that a check never reads half an entry. `rules` holds the
    concrete rules of the class, empty for an entry written before them."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RegistryError(f"registre illisible : {path} : {exc}") from exc
    classes: dict[str, dict] = {}
    current: dict | None = None
    field: str | None = None
    rule: dict | None = None
    for line in lines:
        heading = HEADING.match(line)
        if heading:
            current = {"code": heading.group(1), "title": heading.group(2).strip(), "rules": {}}
            classes[current["code"]] = current
            field = rule = None
            continue
        if line.startswith("#"):
            current = field = rule = None
            continue
        if current is None:
            continue
        if RULES_FIELD.match(line):
            field, rule = "Règles", None
            continue
        if field == "Règles":
            item = RULE.match(line)
            if item:
                rule = {"id": item.group(1), "text": item.group(2).strip()}
                if rule["id"] in current["rules"]:
                    raise RegistryError(f"règle {rule['id']} en double dans {path}")
                current["rules"][rule["id"]] = rule
                continue
            if rule and line.startswith("    ") and line.strip():
                rule["text"] += " " + line.strip()
                continue
            field = rule = None
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
        for rule_id, item in entry["rules"].items():
            if not rule_id.startswith(code + "."):
                raise RegistryError(f"règle {rule_id} rangée sous la catégorie {code} dans {path}")
            sentence, *passage = PASSAGE.split(item.pop("text"), maxsplit=1)
            if not passage or not sentence.strip() or not passage[0].strip():
                raise RegistryError(f"règle {rule_id} sans sa phrase ou son « Passage : » dans {path}")
            passage, closed = passage[0], CLOSED.search(passage[0])
            if closed:
                passage = passage[:closed.start()]
                day, month, year, pr = closed.groups()
                item["closed"] = {"date": f"{year}-{month}-{day}", "pr": int(pr)}
            elif re.search(r"fermée le", passage, re.I):
                raise RegistryError(f"règle {rule_id} : « Fermée le JJ/MM/AAAA par #N. » attendu dans {path}")
            passage = passage.strip().rstrip(".")
            if closed and passage.lower().startswith("aucun"):
                raise RegistryError(f"règle {rule_id} fermée sans point de passage dans {path}")
            item.update(family=code, rule=sentence.strip(), passage=passage)
    return classes


def rules(classes: dict[str, dict]) -> dict[str, dict]:
    """Every concrete rule of the register by its id."""
    return {rule_id: rule for entry in classes.values() for rule_id, rule in entry["rules"].items()}


def pr_category(body: str) -> str | None:
    found = PR_LINES["category"].search(body or "")
    # `**Catégorie :** P`: the emphasis closes after the colon.
    return found.group(1).strip().lstrip("*` ") if found else None


def category_code(value: str) -> str:
    """`P`, `P — processus…` or `aucune — …`: the code alone."""
    return re.split(r"[\s—–,;:(-]", value.strip(), maxsplit=1)[0].strip("`*")


def pr_rule(body: str) -> tuple[str, str] | None:
    """The `Règle :` line: (the id, or `aucune`; the rest of the line)."""
    found = PR_LINES["rule"].search(body or "")
    if not found:
        return None
    value = found.group(1).strip().lstrip("*` ")
    head = re.split(r"[\s—–,;(]", value, maxsplit=1)[0].strip("`*.")
    return head, value[len(head):]


def is_maintenance_branch(branch: str) -> bool:
    return branch.startswith(MAINTENANCE_BRANCHES)


def check_pr_body(body: str, classes: dict[str, dict], fixed=frozenset()) -> list[str]:
    """What the body of a maintenance pull request lacks, empty when complete.
    `fixed`: the rules that already have a merged fix, or a function that
    returns them, called only when a plain `Règle : <id>` needs the answer."""
    problems = []
    known = rules(classes)
    rule = pr_rule(body)
    if rule and rule[0].lower() != NO_CLASS and rule[0] not in known:
        problems.append(f"règle « {rule[0]} » absente de docs/DEFECT_CLASSES.md (identifiants : "
                        f"<CATÉGORIE>.<règle> du champ « Règles » de chaque catégorie, ou <CATÉGORIE>.autre)")
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
    elsewhere = PR_LINES["elsewhere"].search(body or "")
    if elsewhere and not ELSEWHERE_FORM.search(elsewhere.group(1)):
        problems.append(f"ligne « {PR_LABELS['elsewhere']} » sans « `<commande>` → <résultat> » : la commande, "
                        "entre accents graves, liste les appelants du point de décision ; son résultat suit « → »")
    if rule is None:
        problems.append(f"ligne « {PR_LABELS['rule']} » absente (la règle corrigée : <CATÉGORIE>.<règle> du "
                        "registre, ou <CATÉGORIE>.autre pour un défaut isolé)")
    elif rule[0].lower() == NO_CLASS:
        problems.append(f"« {PR_LABELS['rule']} {NO_CLASS} » sur une PR qui corrige un défaut : nommer la règle, "
                        "ou <CATÉGORIE>.autre pour un défaut isolé")
    elif rule[0] in known:
        problems += repeat_problems(body, known[rule[0]], rule[1], fixed)
    return problems


def repeat_problems(body: str, rule: dict, rest: str, fixed) -> list[str]:
    """A rule already fixed by a merged pull request comes back « prévue
    (<bead>) », named by an earlier « où ailleurs », or as a « glissement »
    whose fix goes through the rule's single passage point: the one the
    register declares, or the one this pull request writes into its register."""
    rule_id = rule["id"]
    if PLANNED.search(rest):
        return []
    if re.search(r"pr[ée]vue", rest, re.I):
        return [f"« {rule_id} — prévue » sans son bead : « Règle : {rule_id} — prévue (<bead>) »"]
    if not SLIP.search(rest):
        if rule_id.endswith(ISOLATED) or rule_id not in (fixed() if callable(fixed) else fixed):
            return []
        return [f"règle {rule_id} déjà corrigée par une PR fusionnée : « Règle : {rule_id} — prévue (<bead>) » "
                "si un « où ailleurs » antérieur a nommé ce site, sinon « — glissement » et « Point de passage : »"]
    if rule_id.endswith(ISOLATED):
        return []
    found = PR_LINES["passage"].search(body or "")
    if not found:
        return [f"glissement de {rule_id} sans ligne « {PR_LABELS['passage']} <fonction ou fichier> » : "
                "le correctif passe par le point de passage unique de la règle"]
    value = found.group(1).strip()
    named = re.findall(r"`([^`]+)`", value) or [value.strip("*. ")]
    declared = rule["passage"]
    if declared.lower().startswith("aucun") or not all(name and name in declared for name in named):
        return [f"point de passage « {value} » absent de celui de {rule_id} dans docs/DEFECT_CLASSES.md "
                f"(« {declared} ») : nommer ce point, ou écrire dans le registre, dans cette PR, le point de "
                "passage que le correctif crée ou déplace"]
    return []


def fixed_rules(baseline: dict[int, dict], prs: list[dict], known: dict) -> set[str]:
    """The rules with a merged fix: those of the baseline, and those that the
    `Règle :` line of a pull request merged since names."""
    done = {row["rule"] for row in baseline.values() if row["nature"] in NATURES}
    for pr in prs:
        found = pr["number"] not in baseline and pr_rule(pr.get("body") or "")
        if found and found[0] in known:
            done.add(found[0])
    return done


def merged_since(since: str, repo: Path, name: str | None = None) -> list[dict]:
    gh = os.environ.get("GH_BIN") or "gh"
    argv = [gh, "pr", "list", *(["-R", name] if name else []), "--state", "merged", "--limit", "1000",
            "--search", f"merged:>={since}", "--json", "number,title,body,mergedAt"]
    proc = bounded_run(argv, cwd=repo, text=True, capture_output=True, timeout=120)
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


def load_baseline(path: Path = BASELINE, known: dict | None = None) -> dict[int, dict]:
    """The reclassified pull requests by number: date (Paris), rule or
    `aucune`, nature, short evidence. Refuses a rule the register does not
    hold, or a nature outside `NATURES`."""
    try:
        with path.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader((line for line in fh if not line.startswith("#")), delimiter="\t"))
    except OSError as exc:
        raise RegistryError(f"base de référence illisible : {path} : {exc}") from exc
    baseline = {}
    for row in rows:
        number, rule, nature = int(row["pr"]), row["regle"], row["nature"]
        if rule == NO_CLASS:
            if nature != "-":
                raise RegistryError(f"#{number} : « {NO_CLASS} » a pour nature « - », pas « {nature} »")
        elif nature not in NATURES:
            raise RegistryError(f"#{number} : nature « {nature} » (attendu : {', '.join(NATURES)})")
        elif known is not None and rule not in known:
            raise RegistryError(f"#{number} : règle « {rule} » absente de docs/DEFECT_CLASSES.md")
        baseline[number] = {"pr": number, "date": row["date"], "rule": rule, "nature": nature,
                            "evidence": row.get("preuve") or ""}
    return baseline


def paris_date(merged_at: str) -> str:
    return datetime.fromisoformat(merged_at.replace("Z", "+00:00")).astimezone(PARIS).strftime("%Y-%m-%d")


def by_rule(prs: list[dict], baseline: dict[int, dict], known: dict, since: str = "") -> dict:
    """Per rule and per Paris month since a date: first fixes, planned repeats
    and slips. The baseline answers for its pull requests, and all of it says
    which rules were already fixed; a later pull request is read from its
    `Règle :` line, in merge order. A rule `<CODE>.autre` is never a slip."""
    seen = {row["rule"] for row in baseline.values() if row["nature"] in NATURES}
    rows = {number: dict(row, month=row["date"][:7]) for number, row in baseline.items() if row["date"] >= since}
    unclassified = []
    for pr in sorted((p for p in prs if p["number"] not in baseline), key=lambda p: (p.get("mergedAt") or "", p["number"])):
        found = pr_rule(pr.get("body") or "")
        if not found or (found[0] != NO_CLASS and found[0] not in known):
            unclassified.append(pr["number"])
            continue
        rule, rest = found
        day = paris_date(pr["mergedAt"])
        if rule == NO_CLASS:
            rows[pr["number"]] = {"pr": pr["number"], "rule": rule, "nature": "-", "date": day, "month": day[:7]}
            continue
        nature = ("prevue" if re.search(r"pr[ée]vue", rest, re.I) else
                  "glissement" if rule in seen and not rule.endswith(ISOLATED) else "premiere")
        rows[pr["number"]] = {"pr": pr["number"], "rule": rule, "nature": nature, "date": day, "month": day[:7]}
        seen.add(rule)
    table: dict[str, dict[str, dict[str, int]]] = {}
    months: dict[str, dict[str, int]] = {}
    slips: dict[str, list[int]] = {}
    for row in sorted(rows.values(), key=lambda r: r["pr"]):
        if row["nature"] not in NATURES:
            continue
        cell = table.setdefault(row["rule"], {}).setdefault(row["month"], dict.fromkeys(NATURES, 0))
        cell[row["nature"]] += 1
        months.setdefault(row["month"], dict.fromkeys(NATURES, 0))[row["nature"]] += 1
        if row["nature"] == "glissement":
            slips.setdefault(row["rule"], []).append(row["pr"])
    return {"rules": dict(sorted(table.items())), "months": dict(sorted(months.items())),
            "slips": dict(sorted(slips.items(), key=lambda kv: (-len(kv[1]), kv[0]))),
            "fixes": [{k: row[k] for k in ("pr", "date", "rule", "nature")}
                      for row in sorted(rows.values(), key=lambda r: r["pr"]) if row["nature"] in NATURES],
            "no_defect": sorted(n for n, r in rows.items() if r["rule"] == NO_CLASS),
            "unclassified": sorted(unclassified)}


def slip_share(fixes: list[dict], start: str, end: str) -> dict:
    """The slips among the fix pull requests merged from `start` to `end`
    (Paris dates, both included); `share` is None without a fix."""
    window = [f for f in fixes if start <= f["date"] <= end]
    slips = sum(f["nature"] == "glissement" for f in window)
    return {"start": start, "end": end, "slips": slips, "fixes": len(window),
            "share": round(slips / len(window), 3) if window else None}


def closed_slips(fixes: list[dict], known: dict) -> list[dict]:
    """Every slip on a closed rule merged after the day it was closed."""
    return [{"rule": f["rule"], "pr": f["pr"], "date": f["date"], "closed": known[f["rule"]]["closed"]}
            for f in fixes if f["nature"] == "glissement" and known.get(f["rule"], {}).get("closed")
            and f["date"] > known[f["rule"]]["closed"]["date"]]


def d1(fixes: list[dict], known: dict, until: str = "9999-12-31") -> dict:
    """Decision D1 with its figures: the share of slips of the reference and
    of the period (cut at `until`), the closed rules and the slips on them."""
    start, end = D1["period"]
    return dict(D1, reference_share=slip_share(fixes, *D1["reference"]),
                period_share=slip_share(fixes, start, min(end, until)),
                closed_rules={rule_id: rule["closed"] for rule_id, rule in sorted(known.items()) if rule.get("closed")},
                closed_slips=closed_slips(fixes, known))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="defect_classes.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    sub = parser.add_subparsers(dest="command", required=True)
    checking = sub.add_parser("check-pr-body", help="the lines a maintenance PR body (stdin) lacks")
    checking.add_argument("--branch", help="the PR's head branch: a branch that is not a maintenance branch passes")
    checking.add_argument("--github-repo", help="OWNER/NAME whose merged PRs say which rules are already fixed")
    checking.add_argument("--baseline", type=Path, default=BASELINE)
    sub.add_parser("maintenance-branches", help="the branch prefixes of a maintenance PR, one per line")
    counting = sub.add_parser("count", help="merged PRs by class (or by rule) since a date")
    counting.add_argument("--since", required=True)
    counting.add_argument("--repo", type=Path, default=Path("."))
    counting.add_argument("--by-rule", action="store_true", help="first fixes, planned repeats and slips per rule and month")
    counting.add_argument("--baseline", type=Path, default=BASELINE)
    args = parser.parse_args(argv)
    if args.command == "maintenance-branches":
        print("\n".join(MAINTENANCE_BRANCHES))
        return 0
    if args.command == "check-pr-body" and args.branch is not None and not is_maintenance_branch(args.branch):
        print(f"branche « {args.branch} » : pas une PR de maintenance ({', '.join(MAINTENANCE_BRANCHES)}), "
              "rien à vérifier", file=sys.stderr)
        return 0
    try:
        classes = load(args.registry)
        if args.command == "check-pr-body":
            known = rules(classes)

            def fixed() -> set[str]:
                baseline = load_baseline(args.baseline, known)
                since = max(row["date"] for row in baseline.values())
                return fixed_rules(baseline, merged_since(since, Path("."), args.github_repo), known)

            problems = check_pr_body(sys.stdin.read(), classes, fixed)
            print("\n".join(problems))
            return 1 if problems else 0
        prs = merged_since(args.since, args.repo)
        if args.by_rule:
            known = rules(classes)
            baseline = load_baseline(args.baseline, known)
            counted = by_rule(prs, baseline, known, args.since)
            # D1 reads the whole baseline, whatever --since cuts from the table.
            decision = d1(by_rule(prs, baseline, known)["fixes"], known)
            print(json.dumps({"since": args.since, "d1": decision, **counted},
                             indent=2, ensure_ascii=False))
            return 0
        print(json.dumps({"since": args.since, **count(prs, classes)}, indent=2, ensure_ascii=False))
        return 0
    except (RegistryError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        print(f"refus : {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
