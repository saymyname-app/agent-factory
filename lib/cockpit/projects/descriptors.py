"""Reads project descriptors (spec af-oohx2x .12, T04/T05 -- the cockpit's
alias for the extended Project Planning Profile, CONTEXT.md: Projet). Pure
JSON reads over ``config/project-descriptors/*.json``, one project per file,
so a new project appears to the cockpit the moment its descriptor is
committed -- no cockpit code names a project (AC1).

The cockpit is a reader, not the validator: ``bin/project-planning-profile
describe``/``list`` is the authority that refuses a malformed descriptor at
commit/CI time (T04). This loader trusts a descriptor already accepted by
that gate and only checks the one shape it depends on (contract, project_id,
display_name) so a genuinely broken file is skipped rather than crashing the
whole "Projets" section.
"""
import json
from pathlib import Path

DESCRIPTOR_CONTRACT = "agent-factory-project-descriptor/v1"


def load_descriptors(descriptors_dir):
    """Every well-formed descriptor under ``descriptors_dir``, sorted by
    ``project_id`` for a deterministic render order."""
    directory = Path(descriptors_dir)
    if not directory.is_dir():
        return []
    descriptors = []
    for file in sorted(directory.glob("*.json")):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        if data.get("contract") != DESCRIPTOR_CONTRACT:
            continue
        project_id = data.get("project_id")
        display_name = data.get("display_name")
        if not (isinstance(project_id, str) and project_id) or not (
            isinstance(display_name, str) and display_name
        ):
            continue
        descriptors.append(
            {
                "project_id": project_id,
                "display_name": display_name,
                "rigs": list(data.get("rigs") or []),
                "knowledge_repo": data.get("knowledge_repo") or "",
                "roadmap_path": data.get("roadmap_path") or "",
                "rituals_status_command": data.get("rituals_status_command") or "",
                "promotion_branch": dict(data.get("promotion_branch") or {}),
            }
        )
    descriptors.sort(key=lambda d: d["project_id"])
    return descriptors
