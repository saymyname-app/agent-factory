#!/usr/bin/env python3
"""Lint: a tool finds the account's state from lib/account_home.py, not $HOME.

Gas City runs the exec check of a formula step with HOME set to the city
root (gastownhall/gascity, internal/convergence/condition.go). A tool that
check reaches and that resolves a path from $HOME looks under the city root:
the gate of mol-ticket-author missed the work tree (af-r35155, #566), then
the evidence store (af-i4d833, #671), each fixed once, at the caller. The
class is held here (af-e84s74): in bin/, lib/ and assets/scripts/, a read
of HOME is refused outside the files named below, each with its verdict on
why no Gas City check runs it. A new tool writes
`from account_home import account_home`; a file that no longer reads HOME
leaves the list. Same principle as tests/bd-bin-empty-override-lint-test.py.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNED = ("bin", "lib", "assets/scripts")

PYTHON_RE = re.compile(
    r"""Path\.home\(\)|expanduser\(|(?:environ\[|environ\.get\(|getenv\()\s*["']HOME["']""")
SHELL_RE = re.compile(r"""\$HOME\b|\$\{HOME\b""")

# Verdict per tool: where it runs, and so which HOME it sees. An order's
# check and exec inherit the supervisor's environment (HOME = the account);
# only a formula step's exec check gets HOME = the city root.
# The one formula check of the Factory is assets/scripts/checks/
# ticket-author-check.sh: bin/ticket-author check, which reads through
# bin/convoy-state and bin/evidence-capture verify. None of the files below
# is reached from it (checked 2026-10-20, af-e84s74).
NOT_UNDER_A_CHECK = {
    "lib/account_home.py": "the one resolution: the password database, $HOME only for a uid without an entry",
    "bin/acceptance-session": "the Acceptance session runs it, with the account's HOME",
    "bin/ci-runner": "installed by hand or by bin/factory-host-install, for a user unit of the account",
    "bin/delivery-role-sandbox": "wraps a role session and binds the HOME that session runs with, on purpose",
    "bin/evidence-pack": "bin/convoy-advance (order exec, the supervisor's HOME) and the Spec-end tools of a session",
    "bin/factory-do-work-workspace": "the workspace step of mol-do-work, run by the worker session",
    "bin/factory-guard": "its order exec and sessions, with the account's HOME",
    "bin/factory-host-install": "run by hand; it checks that HOME is the account's, on purpose",
    "bin/factory-maintain": "the clean-worktrees order exec and by hand",
    "bin/factory-metrics": "its order exec",
    "bin/factory-revive": "run by hand or by its user unit",
    "bin/factory-shared-drain-workspace": "the steps of the build-basic workflow, run by a session",
    "bin/mayor-context-guard": "its order exec",
    "bin/outcome-evaluation": "the mol-outcome-evaluation session and bin/convoy-advance (order exec)",
    "bin/provider-failover": "orders and sessions; bin/ticket-author calls it in start (a session), never in check",
    "bin/role-adoption-trial": "run by hand; it hands the account's HOME to its isolated trial city",
    "bin/ticket-evaluation": "the Evaluator session and bin/convoy-advance (order exec)",
    "lib/evaluation_capacity.py": "imported by bin/ticket-evaluation and bin/outcome-evaluation only",
}


def is_python(path, text):
    return path.suffix == ".py" or text.startswith("#!") and "python" in text.split("\n", 1)[0]


def main():
    offenders, seen = [], set()
    for top in SCANNED:
        for path in sorted((ROOT / top).rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            pattern = PYTHON_RE if is_python(path, text) else SHELL_RE
            relpath = path.relative_to(ROOT).as_posix()
            for lineno, line in enumerate(text.splitlines(), start=1):
                if line.lstrip().startswith("#") or not pattern.search(line):
                    continue
                seen.add(relpath)
                if relpath not in NOT_UNDER_A_CHECK:
                    offenders.append((relpath, lineno, line.strip()))

    stale = sorted(set(NOT_UNDER_A_CHECK) - seen)
    if offenders or stale:
        if offenders:
            print(f"FAIL: {len(offenders)} site(s) resolve a path from $HOME, which a Gas City check sets "
                  "to the city root (use account_home() of lib/account_home.py):", file=sys.stderr)
            for relpath, lineno, snippet in offenders:
                print(f"  {relpath}:{lineno}: {snippet}", file=sys.stderr)
        for relpath in stale:
            print(f"FAIL: {relpath} no longer reads HOME: remove it from NOT_UNDER_A_CHECK", file=sys.stderr)
        sys.exit(1)

    print("PASS: no tool a Gas City check can reach resolves a path from $HOME")


if __name__ == "__main__":
    main()
