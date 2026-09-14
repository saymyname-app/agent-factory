"""Offline distribution and onboarding; upstream Gas City owns runtime orchestration."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PINNED = {"gc": "1.4.1", "bd": "1.2.2", "dolt": "2.1.7"}
REQUIREMENTS = {
    "vision": "Vision, users, problem, success measure",
    "release": "First release scope and explicit exclusions",
    "journeys": "Journeys, errors, permissions and acceptance",
    "domain": "Business entities, relationships and data lifecycle",
    "technical": "Architecture, build, CI and delivery constraints",
    "inventory": "Observed existing implementation or greenfield baseline",
    "backlog": "Release outcomes, dependencies and testable acceptance",
    "operations": "Release checks, deployment, rollback and support",
    "authority": "PO mandate, decision boundaries and execution authority",
}
CORE = [
    "bin/factory-portable", "lib/factory_portable.py",
    "bin/product-queue", "lib/factory_cockpit.py",
    "ui/factory-cockpit/index.html", "ui/factory-cockpit/app.js",
    "ui/factory-cockpit/styles.css", "config/product-cockpit.schema.json",
    "pack.toml", "agents/mayor/prompt.template.md",
]
PORTABLE_DOCS = ["INSTALL.md", "ONBOARDING.md", "AGENTS.md", "DELIVERY.md"]
PLACEHOLDER = re.compile(r"\b(TODO|TBD|UNKNOWN)\b", re.I)


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def slug(value):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", value):
        raise ValueError("Use a lowercase slug of at most 63 letters, digits or hyphens.")
    return value


def fresh_destination(value):
    raw = Path(value).expanduser().absolute()
    if raw.exists() or raw.is_symlink():
        raise ValueError("Destination already exists; no overwrite or in-place migration is supported.")
    path = raw.resolve()
    for parent in [path.parent, *path.parents]:
        if (parent / "city.toml").exists() or ((parent / ".gc").exists() and (parent / "pack.toml").exists()):
            raise ValueError("Destination must be outside any existing Factory.")
    if path == ROOT or ROOT in path.parents:
        raise ValueError("Destination must be outside the source distribution.")
    if not path.parent.is_dir():
        raise ValueError("Create the destination parent directory first.")
    return path


def export(destination):
    target = fresh_destination(destination)
    # Validate the complete allowlist before creating any destination.
    sources = {name: ROOT / name for name in CORE}
    for name in PORTABLE_DOCS:
        sources["docs/portable/" + name] = ROOT / "docs/portable" / name
    sources["AGENTS.md"] = ROOT / "docs/portable/AGENTS.md"
    sources["README.md"] = ROOT / "docs/portable/INSTALL.md"
    for name, source in sources.items():
        if source.is_symlink() or ROOT not in source.resolve().parents or not source.is_file():
            raise ValueError("Invalid distribution source: " + name)
    with tempfile.TemporaryDirectory(prefix=".factory-export-", dir=target.parent) as tmp:
        stage = Path(tmp) / "payload"
        stage.mkdir()
        manifest = {}
        for name, source in sources.items():
            data = source.read_bytes()
            dest = stage / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            if name.startswith("bin/"):
                dest.chmod(0o755)
            manifest[name] = hashlib.sha256(data).hexdigest()
        write(stage / ".gitignore", ".local/\n.gc/\n.beads/\n.dolt/\nrigs/\n__pycache__/\n*.py[cod]\n.env*\n*.secret\ncity.toml\nconfig/products/\n")
        write(stage / "distribution.json", {"schema_version": 1, "files": manifest, "runtime": PINNED})
        stage.rename(target)
    return {"export": str(target), "runtime_started": False, "files": len(manifest)}


def profile(args):
    target = ROOT / ".local" / "profile.json"
    if target.exists():
        raise ValueError("Local profile already exists. Edit it explicitly; never overwrite implicitly.")
    for value in [args.po_model, args.writer_model]:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}", value):
            raise ValueError("Invalid model identifier.")
    data = {"schema_version": 1, "operator": args.operator, "provider": "codex",
            "po_model": args.po_model, "writer_model": args.writer_model,
            "sandbox": "workspace-write"}
    write(target, data)
    target.chmod(0o600)
    return {"profile": str(target), "credentials": "Use provider and GitHub login; never store credentials in this file."}


def load_profile():
    data = json.loads((ROOT / ".local/profile.json").read_text())
    if data.get("schema_version") != 1 or data.get("provider") != "codex":
        raise ValueError("V1 supports the Codex PO bridge; other runtime providers need a qualified adapter.")
    return data


def doctor():
    checks = []
    for tool in ["git", "python3", "gh", "tmux", "jq", "gc", "bd", "dolt", "codex"]:
        executable = shutil.which(tool)
        item = {"tool": tool, "available": bool(executable)}
        if executable and tool in PINNED:
            result = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=10)
            versions = re.findall(r"(?<![\d.])\d+\.\d+\.\d+(?![\d.])", result.stdout + result.stderr)
            item["pinned_version_matches"] = result.returncode == 0 and PINNED[tool] in versions
        checks.append(item)
    return {"checks": checks, "ready": all(x["available"] and x.get("pinned_version_matches", True) for x in checks),
            "authentication": "not probed", "runtime_started": False}


def bootstrap_plan():
    load_profile()
    if (ROOT / ".gc").exists() or (ROOT / "city.toml").exists():
        raise ValueError("Runtime already exists. This command is only for a fresh exported installation.")
    return {"commands": [
        shlex.join(["gc", "init", "--template", "gascity", "--providers", "codex",
                    "--default-provider", "codex", "--skip-provider-readiness",
                    "--no-start", "--preserve-existing", str(ROOT)]),
        "gc doctor",
    ], "next": "Review generated city.toml; apply your local writer model before starting. Follow docs/portable/INSTALL.md.",
    "executed": False}


def inventory(repo):
    repo = Path(repo).expanduser().resolve()
    if not repo.is_dir():
        raise ValueError("Import source must be an existing local Git checkout.")
    def git(*args):
        result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=20,
                                env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
        if result.returncode:
            raise ValueError("Could not inspect Git checkout.")
        return result.stdout.strip()
    if Path(git("rev-parse", "--show-toplevel")).resolve() != repo:
        raise ValueError("Import each repository root explicitly.")
    # Never record remote URLs, file contents or diffs (may contain credentials).
    return {"path": str(repo), "head": git("rev-parse", "HEAD"),
            "branch": git("branch", "--show-current"),
            "dirty": bool(git("status", "--porcelain")),
            "tracked_files": len(git("ls-files").splitlines()),
            "scope": "Git metadata only; build, runtime, documentation and product intent remain unverified"}


def project(args):
    name = slug(args.slug)
    if args.mode == "import" and not args.repo:
        raise ValueError("Import requires at least one --repo local checkout.")
    if args.mode == "new" and args.repo:
        raise ValueError("Use import for existing repositories.")
    local = load_profile()
    sources = [inventory(repo) for repo in args.repo]
    target = ROOT / "docs/products" / name
    config_path = ROOT / "config/products" / (name + ".json")
    if target.exists() or config_path.exists():
        raise ValueError("Product already exists; resume its onboarding instead.")
    if target.parent.is_symlink() or config_path.parent.is_symlink():
        raise ValueError("Product directories must not be symlinks.")
    docs = {
        "PRODUCT_CONTEXT.md": "# Product context\n\nTODO: vision, users, domain, constraints and evidence.\n",
        "PRODUCT_STRATEGY.md": "# Product strategy\n\n## Product thesis\n\nTODO\n\n## Product roadmap\n\nTODO: first release and exclusions.\n\n## Human decisions still required\n\nTODO\n",
        "DECISIONS.md": "# Decision log\n\n## Accepted\n\nNo accepted decisions yet. Append dated decisions with authority and evidence.\n",
        "PROJECT_INVENTORY.md": "# Project inventory\n\nTODO: observed, proven, missing and contradictory capabilities; source and timestamp for each.\n",
        "DESIGN_GOVERNANCE.md": "# Design governance\n\nReuse established patterns within the approved scope. PO reviews new compositions.\nHuman decides material changes to scope, privacy, purchase, branding and irreversible journeys.\n",
        "RELEASE.md": "# First release\n\nTODO: included and excluded outcomes, acceptance, dependency order, verification, deployment, rollback, support and success measurement.\n",
        "MANDATE.md": "# PO preparation mandate\n\nThe project onboarding request authorizes investigation and documentation in this project dossier.\nResolve facts from evidence and record reversible decisions within accepted scope.\nAsk the human for material product, cost, access or irreversible decisions.\nThis preparation mandate does not authorize delivery or deployment.\nExecution requires a bounded campaign mandate recorded with scope, limits and stop conditions.\n",
    }
    for filename, content in docs.items():
        write(target / filename, content)
    write(target / "IMPORT.json", {"mode": args.mode, "sources": sources})
    write(target / "readiness.json", {
        "schema_version": 1, "slug": name, "mode": args.mode,
        "requirements": {key: {"status": "missing", "evidence": [], "reviewed_by": "", "rationale": ""}
                         for key in REQUIREMENTS},
        "decisions": [], "po_review": {"reviewer": "", "summary": "", "evidence_digest": ""},
        "delivery_authorized": False,
    })
    instructions = (ROOT / "docs/portable/ONBOARDING.md").read_text()
    write(target / "AGENTS.md", "# Product Owner — " + args.name + "\n\n" + instructions)
    prefix = "docs/products/" + name + "/"
    config = {
        "schema_version": 1, "slug": name, "name": args.name, "operator_name": local["operator"],
        "strategy": prefix + "PRODUCT_STRATEGY.md", "decisions": prefix + "DECISIONS.md",
        "project_inventory": prefix + "PROJECT_INVENTORY.md", "design_governance": prefix + "DESIGN_GOVERNANCE.md",
        "po_workspace": str(target), "po_add_dirs": [str(ROOT)], "po_model": local["po_model"],
        "po_sandbox": "workspace-write", "preview_command": [],
        "queue_command": [shutil.which("env") or "/usr/bin/env", "PRODUCT_QUEUE_PRODUCT=" + name, str(ROOT / "bin/product-queue"), "list", "--json"],
        "capabilities": [], "relations": [], "business_objectives": [], "product_reference": [],
        "view_inventory": [], "delivery_workflow": [],
        "north_star": "To define during onboarding",
    }
    write(config_path, config)
    return {"project": name, "mode": args.mode, "dossier": str(target), "ready": False,
            "next": "Open this dossier with your PO and ask it to complete onboarding through the first release.",
            "source_repositories_modified": False, "runtime_started": False}


def readiness(name):
    target = ROOT / "docs/products" / slug(name)
    data = json.loads((target / "readiness.json").read_text())
    if data.get("schema_version") != 1 or data.get("slug") != name:
        raise ValueError("Invalid readiness document.")
    problems, material = [], {}
    requirements = data.get("requirements", {})
    for key, title in REQUIREMENTS.items():
        item = requirements.get(key, {})
        if item.get("status") != "defined" or not item.get("reviewed_by", "").strip() or not item.get("rationale", "").strip():
            problems.append(key + ": missing definition/review")
        evidence = item.get("evidence", [])
        if not isinstance(evidence, list) or not evidence:
            problems.append(key + ": missing evidence")
            continue
        for ref in evidence:
            if not isinstance(ref, str):
                problems.append(key + ": invalid evidence")
                continue
            path = (target / ref).resolve()
            if target.resolve() not in path.parents or not path.is_file():
                problems.append(key + ": evidence must be a local dossier file")
                continue
            text = path.read_text(encoding="utf-8")
            if not text.strip() or PLACEHOLDER.search(text):
                problems.append(key + ": unfinished evidence " + ref)
            material[ref] = hashlib.sha256(text.encode()).hexdigest()
    decisions = data.get("decisions", [])
    if not isinstance(decisions, list):
        raise ValueError("Decisions must be a list.")
    for decision in decisions:
        if decision.get("status") not in {"accepted", "deferred", "open"}:
            problems.append("invalid decision status")
        if decision.get("blocks_release", True) and decision.get("status") != "accepted":
            problems.append("blocking decision: " + str(decision.get("id", "unnamed")))
        if decision.get("status") == "accepted" and not (decision.get("authority") and decision.get("evidence")):
            problems.append("accepted decision lacks authority/evidence")
    # Changes to definitions, decisions or evidence invalidate the PO sign-off.
    digest = hashlib.sha256(json.dumps({"requirements": requirements, "decisions": decisions, "files": material},
                                      sort_keys=True).encode()).hexdigest()
    review = data.get("po_review", {})
    if not review.get("reviewer") or not review.get("summary") or review.get("evidence_digest") != digest:
        problems.append("PO final review missing or stale")
    return {"project": name, "definition_ready": not problems, "blocking": problems,
            "evidence_digest": digest, "delivery_authorized": False,
            "authority_note": "Definition readiness never grants execution. Mayor must verify a separate bounded campaign mandate."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("export"); p.add_argument("destination")
    p = sub.add_parser("profile")
    p.add_argument("--operator", required=True); p.add_argument("--po-model", required=True); p.add_argument("--writer-model", required=True)
    sub.add_parser("doctor"); sub.add_parser("bootstrap-plan")
    p = sub.add_parser("project")
    p.add_argument("--mode", choices=["new", "import"], required=True)
    p.add_argument("--slug", required=True); p.add_argument("--name", required=True)
    p.add_argument("--repo", action="append", default=[])
    p = sub.add_parser("readiness"); p.add_argument("slug")
    args = parser.parse_args()
    try:
        if args.command == "export": result = export(args.destination)
        elif args.command == "profile": result = profile(args)
        elif args.command == "doctor": result = doctor()
        elif args.command == "bootstrap-plan": result = bootstrap_plan()
        elif args.command == "project": result = project(args)
        else: result = readiness(args.slug)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if result.get("ready") is False and args.command == "doctor": sys.exit(2)
        if result.get("definition_ready") is False: sys.exit(2)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        parser.exit(1, "factory-portable: " + str(exc) + "\n")
