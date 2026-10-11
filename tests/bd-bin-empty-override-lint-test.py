#!/usr/bin/env python3
"""Lint: a tool must not read an empty BD_BIN as its `bd`.

Gas City 1.5 runs an order's check and exec with `BD_BIN` set and empty.
`os.environ.get("BD_BIN", "bd")` keeps the empty value, so the tool runs
'' instead of bd: PermissionError, exit 1. For a `condition` order that
exit reads as "condition: not met": the order stops firing with no
`order.failed` (bin/mail-reply-reap, af-vhvmsi; five more tools, af-d130xt).

The forms that hold: `os.environ.get("BD_BIN") or "bd"` in Python,
`${BD_BIN:-bd}` in Bash. The forms refused here are the ones an empty value
defeats: a default given to `.get` / `getenv`, and `${BD_BIN-bd}` without
the colon.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNED = ("bin", "lib", "orders", "formulas")

OFFENDER_RE = re.compile(
    r"""(?:\.get|getenv)\(\s*["']BD_BIN["']\s*,"""  # .get("BD_BIN", <default>)
    r"""|\$\{BD_BIN-"""                              # ${BD_BIN-<default>}
)


def main():
    offenders = []
    for top in SCANNED:
        for path in sorted((ROOT / top).rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if OFFENDER_RE.search(line):
                    offenders.append((path.relative_to(ROOT), lineno, line.strip()))

    if offenders:
        print(f"FAIL: {len(offenders)} site(s) read an empty BD_BIN as their bd "
              '(write os.environ.get("BD_BIN") or "bd", or ${BD_BIN:-bd}):', file=sys.stderr)
        for relpath, lineno, snippet in offenders:
            print(f"  {relpath}:{lineno}: {snippet}", file=sys.stderr)
        sys.exit(1)

    print("PASS: no tool reads an empty BD_BIN as its bd")


if __name__ == "__main__":
    main()
