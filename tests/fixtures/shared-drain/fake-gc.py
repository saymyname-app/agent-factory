#!/usr/bin/env python3
"""Tiny gc surface for factory-shared-drain-workspace-test.sh."""

import json
import os
from pathlib import Path
import sys


state = Path(os.environ["FAKE_GC_STATE"])
args = sys.argv[1:]


def bead_path(bead_id: str) -> Path:
    return state / "beads" / f"{bead_id}.json"


def load_bead(bead_id: str) -> dict:
    data = json.loads(bead_path(bead_id).read_text())
    return data[0] if isinstance(data, list) else data


def save_bead(bead: dict) -> None:
    bead_path(bead["id"]).write_text(json.dumps([bead], sort_keys=True))


if len(args) >= 4 and args[:2] == ["bd", "show"] and args[3] == "--json":
    print(bead_path(args[2]).read_text())
    raise SystemExit(0)

if len(args) >= 3 and args[:2] == ["bd", "update"]:
    bead = load_bead(args[2])
    metadata = bead.setdefault("metadata", {})
    index = 3
    while index < len(args):
        flag = args[index]
        if flag == "--set-metadata":
            key, value = args[index + 1].split("=", 1)
            metadata[key] = value
            index += 2
        elif flag == "--unset-metadata":
            metadata.pop(args[index + 1], None)
            index += 2
        else:
            raise SystemExit(f"unsupported fake gc update argument: {flag}")
    save_bead(bead)
    print(json.dumps({"ok": True, "id": bead["id"]}))
    raise SystemExit(0)

if len(args) == 4 and args[:2] == ["convoy", "status"] and args[3] == "--json":
    convoy = json.loads((state / "convoy.json").read_text())
    if convoy["convoy"]["id"] != args[2]:
        raise SystemExit(f"unknown convoy: {args[2]}")
    print(json.dumps(convoy))
    raise SystemExit(0)

raise SystemExit(f"unsupported fake gc invocation: {' '.join(args)}")
