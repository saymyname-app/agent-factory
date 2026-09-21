#!/usr/bin/env python3
"""Tiny gh PR surface for factory-shared-drain-workspace-test.sh."""

import json
import os
from pathlib import Path
import sys


state = Path(os.environ["FAKE_GC_STATE"])
args = sys.argv[1:]
pr_path = state / "pr.json"
count_path = state / "pr-create-count"

if args[:2] == ["pr", "list"]:
    if pr_path.exists():
        print(json.dumps([json.loads(pr_path.read_text())]))
    else:
        print("[]")
    raise SystemExit(0)

if args[:2] == ["pr", "create"]:
    count = int(count_path.read_text()) if count_path.exists() else 0
    count_path.write_text(str(count + 1))
    result = {"url": "https://example.invalid/pull/1"}
    pr_path.write_text(json.dumps(result))
    print(result["url"])
    raise SystemExit(0)

raise SystemExit(f"unsupported fake gh invocation: {' '.join(args)}")
