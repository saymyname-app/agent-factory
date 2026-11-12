#!/usr/bin/env python3
"""Maintenance towards a convoy's integration branch (af-wpzic4, af-41i8d0).

Intent (Benjamin, his words, 12/11/2026 18:35 Paris): « Oui, autorise », to
« J'autorise la maintenance vers la branche d'intégration pour le code de
test du convoi ? ». Mechanism (agent interpretation, docs/DELIVERY.md,
"Maintenance towards an integration branch"): a maintenance pull request
may target ``integration/<spec>`` instead of the protected branch only when

* its bead is a ``maintenance`` bead whose ``gc.authorized_by`` names the
  decision af-wpzic4 and whose ``gc.work_base_branch`` is that branch;
* every file it changes is test/harness code (``tests/``,
  ``lib/synthetic_city.py``, ``bin/cockpit-isolated``; the fake tools live
  under ``tests/``) that the convoy itself changed, and that main cannot
  reach: the file differs between the protected branch and the integration
  branch, and the integration branch changed it since they diverged.

Any other code is delivered on the protected branch only. This module is the
one place that rule is written; bin/factory-do-work-workspace (before
opening the PR), bin/pr-autopilot (before merging it), bin/deliver-close and
bin/factory-delivery-guard (on the merged target) call it. Rollback: remove
the rule from docs/DELIVERY.md and the integration case below refuses again.

CLI (exit 0 accepted, 1 refused with one reason per line, 2 unusable input):

  integration_maintenance.py target --target <branch> [--repo <owner/repo>]
                             [--projects <config/projects dir>] < bead.json
      Whether a delivery of this bead may land on <branch>: the repo's
      protected branch always (when the repo is registered), an
      integration branch only on the conditions above, nothing else.
  integration_maintenance.py files --git <dir> --protected <ref>
                             --base <ref> --head <ref>
      Whether every file <head> changes against <base> may be repaired on
      the integration branch; prints the « Cible » line on success.
  integration_maintenance.py scan [--projects <dir>] < beads.json
      Closed beads whose recorded merged_target the target rule refuses,
      as <id>\\x1f<target>\\x1f<reason>\\x1f<already_flagged 0|1>.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

AUTHORITY = "af-wpzic4"
MAINTENANCE_LABEL = "maintenance"
INTEGRATION_RE = re.compile(r"^integration/[A-Za-z0-9][A-Za-z0-9._-]*$")
HARNESS_PREFIXES = ("tests/",)
HARNESS_FILES = ("lib/synthetic_city.py", "bin/cockpit-isolated")
FLAGGED_AT_KEY = "gc.delivery_proof_flagged_at"
DEFAULT_PROJECTS = Path(__file__).resolve().parent.parent / "config" / "projects"


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _bead(value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        value = value[0] if value else {}
    return value if isinstance(value, dict) else {}


def is_integration_branch(branch: str) -> bool:
    return bool(INTEGRATION_RE.match(branch))


def is_harness_path(path: str) -> bool:
    return path.startswith(HARNESS_PREFIXES) or path in HARNESS_FILES


def protected_branches(projects: Path) -> dict[str, str]:
    """repo -> protected branch, from config/projects/*.toml."""
    out: dict[str, str] = {}
    for file in sorted(projects.glob("*.toml")):
        try:
            data = tomllib.loads(file.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            continue
        repo, branch = _text(data.get("repo")), _text(data.get("protected_branch"))
        if repo and branch:
            out[repo] = branch
    return out


def authorization_refusals(bead: dict[str, Any], target: str) -> list[str]:
    metadata = bead.get("metadata") if isinstance(bead.get("metadata"), dict) else {}
    labels = bead.get("labels") if isinstance(bead.get("labels"), list) else []
    refusals = []
    if MAINTENANCE_LABEL not in labels:
        refusals.append(f"le bead n'a pas le label {MAINTENANCE_LABEL}")
    if not re.search(rf"(^|[^A-Za-z0-9-]){re.escape(AUTHORITY)}([^A-Za-z0-9]|$)",
                     _text(metadata.get("gc.authorized_by"))):
        refusals.append(f"gc.authorized_by ne nomme pas la décision {AUTHORITY}")
    base = _text(metadata.get("gc.work_base_branch"))
    if base != target:
        refusals.append(f"gc.work_base_branch={base or '(absent)'} n'est pas {target}")
    return refusals


def target_refusals(bead: dict[str, Any], target: str, protected: str) -> list[str]:
    """Why a delivery of `bead` may not land on `target` (empty: it may).
    `protected` is the repo's protected branch, "" for a repo not registered."""
    if not target:
        return ["aucune cible de fusion"]
    if protected and target == protected:
        return []
    if is_integration_branch(target):
        return [f"cible {target} : {reason}" for reason in authorization_refusals(bead, target)]
    if protected:
        return [f"cible {target} : ni la branche protégée {protected} ni une branche integration/<spec>"]
    return []


def _git(repo: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, check=False)


def file_refusals(repo: str, protected: str, base: str, head: str) -> tuple[list[str], list[str]]:
    """(refusals, changed files) for a PR from `head` into `base`."""
    diff = _git(repo, "diff", "--name-only", f"{base}...{head}")
    fork = _git(repo, "merge-base", protected, base)
    if diff.returncode or fork.returncode:
        raise RuntimeError((diff.stderr or fork.stderr).strip() or "git a échoué")
    changed = [line for line in diff.stdout.splitlines() if line]
    fork_point = fork.stdout.strip()
    refusals = []
    for path in changed:
        if not is_harness_path(path):
            refusals.append(f"{path} : hors code de test/harnais (tests/, {', '.join(HARNESS_FILES)})")
        elif _git(repo, "diff", "--quiet", fork_point, base, "--", path).returncode == 0:
            refusals.append(f"{path} : le convoi ne l'a pas modifié ; se corrige sur {protected}")
        elif _git(repo, "diff", "--quiet", protected, base, "--", path).returncode == 0:
            refusals.append(f"{path} : identique sur {protected}, que main peut atteindre")
    return refusals, changed


def cible_line(base: str, changed: list[str]) -> str:
    branch = base.removeprefix("origin/")
    return f"Cible : {branch} — code de test changé par le convoi ({', '.join(changed)} ; " \
           f"diff main ↔ {branch} non vide sur chacun)"


def _read_stdin_json() -> Any:
    raw = sys.stdin.read()
    return json.loads(raw) if raw.strip() else []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="integration_maintenance.py")
    sub = parser.add_subparsers(dest="command", required=True)
    target = sub.add_parser("target")
    target.add_argument("--target", required=True)
    target.add_argument("--repo", default="")
    target.add_argument("--projects", default=str(DEFAULT_PROJECTS))
    files = sub.add_parser("files")
    for name in ("--git", "--protected", "--base", "--head"):
        files.add_argument(name, required=True)
    scan = sub.add_parser("scan")
    scan.add_argument("--projects", default=str(DEFAULT_PROJECTS))
    args = parser.parse_args(argv)

    if args.command == "files":
        try:
            refusals, changed = file_refusals(args.git, args.protected, args.base, args.head)
        except RuntimeError as exc:
            print(f"integration_maintenance: {exc}", file=sys.stderr)
            return 2
        if refusals or not changed:
            print("\n".join(refusals or ["aucun fichier changé"]))
            return 1
        print(cible_line(args.base, changed))
        return 0

    try:
        payload = _read_stdin_json()
    except json.JSONDecodeError:
        print("integration_maintenance: JSON illisible sur l'entrée", file=sys.stderr)
        return 2
    protected = protected_branches(Path(args.projects))
    if args.command == "target":
        refusals = target_refusals(_bead(payload), args.target, protected.get(args.repo, ""))
        if refusals:
            print("\n".join(refusals))
            return 1
        return 0

    beads = payload if isinstance(payload, list) else [payload]
    for bead in beads:
        if not isinstance(bead, dict) or _text(bead.get("status")) != "closed":
            continue
        metadata = bead.get("metadata") if isinstance(bead.get("metadata"), dict) else {}
        merged_target = _text(metadata.get("merged_target"))
        if not merged_target:
            continue
        refusals = target_refusals(bead, merged_target, protected.get(_text(metadata.get("gc.github_repo")), ""))
        if refusals:
            print("\x1f".join([_text(bead.get("id")), merged_target, "; ".join(refusals),
                               "1" if _text(metadata.get(FLAGGED_AT_KEY)) else "0"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
