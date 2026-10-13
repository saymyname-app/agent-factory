#!/usr/bin/env python3
"""Require a fresh ticket declaration for changed Playwright references."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

CONTRACT = "agent-factory-visual-changes/v1"
DECLARATION = "design-bench/visual-changes.json"
SNAPSHOT_DIR = "design-bench/bench.spec.mjs-snapshots/"


def git(repo, *args, allow_missing=False):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if result.returncode and not allow_missing:
        raise ValueError(result.stderr.strip() or "git a échoué")
    return None if result.returncode else result.stdout


def declarations(repo, ref):
    raw = git(repo, "show", f"{ref}:{DECLARATION}", allow_missing=True)
    if raw is None:
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get("contract") != CONTRACT or not isinstance(data.get("entries"), list):
        raise ValueError(f"{DECLARATION} : contrat invalide")
    found = {}
    for entry in data["entries"]:
        if not isinstance(entry, dict) or any(not isinstance(entry.get(key), str) or not entry[key].strip()
                                              for key in ("path", "ticket", "intent")):
            raise ValueError(f"{DECLARATION} : entrée incomplète")
        path = entry["path"]
        if not path.startswith(SNAPSHOT_DIR) or not path.endswith(".png") or path in found:
            raise ValueError(f"{DECLARATION} : chemin invalide ou répété : {path}")
        found[path] = entry
    return found


def check(repo, base, head):
    before, after = declarations(repo, base), declarations(repo, head)
    diff = git(repo, "diff", "--name-status", "--no-renames", base, head, "--", SNAPSHOT_DIR)
    changed = []
    for line in diff.splitlines():
        status, path = line.split("\t", 1)
        if path.endswith(".png") and status != "A" and (path not in after or after[path] == before.get(path)):
            changed.append(path)
    if changed:
        raise ValueError("changement visuel non déclaré pour ce ticket : " + ", ".join(changed))
    print(json.dumps({"contract": CONTRACT, "changed_references": len(diff.splitlines()), "verdict": "pass"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args()
    try:
        check(args.repo, args.base, args.head)
    except (ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
