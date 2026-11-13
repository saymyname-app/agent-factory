#!/usr/bin/env python3
"""Category L (af-asymry): a work ticket a tool reopens without launching it
again loses its route and its session, so only its next launch takes it.

On 2026-11-11 the worker launched for af-fv8ca4 took af-8fk8nz instead:
`escalation-door repondre` had reopened it with gc.routed_to=factory-worker
and the session of its last launch, and resumed it on the wrong branch.
Every write that reopens a bead goes through lib/work_route_release.sh, or
is named below with why it reopens no launched work."""

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "lib" / "work_route_release.sh"

# path -> ((a text of the reopening write, why it reopens no launched work), ...)
NOT_WORK = {
    "bin/pr-autopilot": (
        ("--title '$title'",
         "flag_stuck reopens its own « PR stuck » bead, filed by pr-autopilot and never launched"),
        ("is still refused for merged PR",
         "flag_unproven_merge reopens its own « merged without delivery proof » bead, "
         "filed by pr-autopilot and never launched (af-65mbq2)"),
    ),
}

REOPEN = re.compile(r"""--status[= ]["']?(open\b|\$|"\$)""")
RELEASED = ("WORK_ROUTE_RELEASE_ARGS", "REOPEN_ARGS")


def shell_writes(text):
    """Each command of a shell text, its continuation lines joined."""
    command = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        command += " " + stripped
        if stripped.endswith("\\"):
            command = command[:-1]
            continue
        yield command
        command = ""
    if command:
        yield command


def reopening_writes(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    found = []
    for command in shell_writes(text):
        if " update " in command and REOPEN.search(command) and "list " not in command:
            found.append(command.strip())
    # REOPEN_ARGS is the reopen of escalation-door, used by name in its writes.
    for match in re.finditer(r"^REOPEN_ARGS=\((.*?)\)$", text, re.M | re.S):
        found.append("REOPEN_ARGS=(" + match.group(1) + ")")
    return found


def offenders(root):
    bad = []
    for path in sorted(list((root / "bin").iterdir()) + list((root / "formulas").glob("*.toml"))):
        if not path.is_file():
            continue
        rel = str(path.relative_to(root))
        # A local array set from the release (a formula step keeps its route).
        aliases = re.findall(r"(\w+)=\(\"\$\{WORK_ROUTE_RELEASE_ARGS\[@\]\}\"\)",
                             path.read_text(encoding="utf-8", errors="replace"))
        released = RELEASED + tuple("${%s[@]}" % name for name in aliases)
        for command in reopening_writes(path):
            if command.startswith("REOPEN_ARGS=("):
                if "WORK_ROUTE_RELEASE_ARGS" not in command:
                    bad.append(f"{rel}: {command}")
                continue
            if any(name in command for name in released):
                continue
            if any(text in command for text, _why in NOT_WORK.get(rel, ())):
                continue
            bad.append(f"{rel}: {command[:160]}")
    return bad


class WorkRouteReleaseTest(unittest.TestCase):
    def test_every_reopen_of_a_bead_releases_its_route_or_says_why_not(self):
        self.assertEqual([], offenders(ROOT))

    def test_a_reopen_without_the_release_is_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp)
            (fake / "bin").mkdir()
            (fake / "formulas").mkdir()
            (fake / "bin" / "tool").write_text(
                '#!/usr/bin/env bash\n'
                'gc bd update "$id" --status open \\\n'
                '  --append-notes "reopened"\n'
                'gc bd update "$id" --status open "${WORK_ROUTE_RELEASE_ARGS[@]}"\n'
                'gc bd list --status open --json\n'
            )

            bad = offenders(fake)

        self.assertEqual(1, len(bad), bad)
        self.assertIn('bin/tool: gc bd update "$id" --status open', bad[0])

    def test_the_release_removes_the_route_and_the_session(self):
        out = subprocess.run(
            ["bash", "-c", '. "$1"; printf "%s\\n" "${WORK_ROUTE_RELEASE_ARGS[@]}"', "-", str(RELEASE)],
            check=True, capture_output=True, text=True,
        ).stdout.split()

        self.assertEqual(
            ["--unset-metadata", "gc.routed_to", "--unset-metadata", "gc.session_id",
             "--unset-metadata", "gc.session_name"],
            out,
        )


if __name__ == "__main__":
    unittest.main()
