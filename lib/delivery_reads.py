"""Shared delivery reads; callers keep their own Refusal type and root.

The list-only bead readers of acceptance-session and owner-answer have a
stricter contract and do not use read_bead.
"""
from __future__ import annotations

import json
import re
import subprocess
import tomllib
from pathlib import Path
from typing import Any


RIGS_SECTION_RE = re.compile(r"^## Target rigs[ \t]*\n+([^\n#]*)$", re.MULTILINE)
RIG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def read_bead(bead_id: str, gc_bin: str, refusal: type[Exception]) -> dict[str, Any]:
    """Read one bead, preserving the delivery commands' errors and JSON shapes."""
    try:
        proc = subprocess.run([gc_bin, "bd", "show", bead_id, "--json"], capture_output=True,
                              text=True, stdin=subprocess.DEVNULL)
    except OSError as exc:
        raise refusal(f"impossible de lancer {Path(gc_bin).name} : {exc}") from exc
    if proc.returncode != 0:
        detail = " ".join((proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}").split())
        detail = detail if len(detail) <= 300 else detail[:299] + "…"
        raise refusal(f"gc bd show {bead_id} a échoué : {detail}")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise refusal(f"gc bd show {bead_id} a rendu un JSON illisible : {exc}") from exc
    bead = data[0] if isinstance(data, list) and data else data
    if not isinstance(bead, dict):
        raise refusal(f"bead introuvable : {bead_id}")
    return bead


def ticket_rig(description: Any, projects: Path) -> str | None:
    """The single configured rig under Target rigs, or None."""
    match = RIGS_SECTION_RE.search(description if isinstance(description, str) else "")
    rigs = [rig.strip() for rig in match.group(1).split(",") if rig.strip()] if match else []
    if len(rigs) != 1 or not RIG_RE.match(rigs[0]) or not (projects / f"{rigs[0]}.toml").is_file():
        return None
    return rigs[0]


def rig_repository(rig: str, root: Path, refusal: type[Exception]) -> Path:
    """Resolve the configured repository relative to the caller's Factory root."""
    try:
        rig_dir = tomllib.loads((root / "config" / "projects" / f"{rig}.toml").read_text(encoding="utf-8")).get("rig_dir")
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise refusal(f"config/projects/{rig}.toml illisible : {exc}") from exc
    if not isinstance(rig_dir, str) or not rig_dir:
        raise refusal(f"config/projects/{rig}.toml ne déclare pas rig_dir")
    return (root / rig_dir).resolve()
