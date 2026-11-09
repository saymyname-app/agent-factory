#!/usr/bin/env python3
"""Every write that closes a bead in bin/ and lib/ is named here with what it
closes (af-epwkmn, docs/DEFECT_CLASSES.md R).

On 2026-11-09 bin/factory-delivery-guard closed R10 (af-30ix43), a ticket of
a new-flow convoy, because it read `gc.authorized_by` as a link to the bead
a merge delivers: only the ticket-end gate or the withdrawal closes such a
ticket (bin/convoy-state), and bin/deliver-close already held that rule. One
rule, two closers, and the second one did not read it. A closer added or
moved without being named here fails, so whoever writes it says whether it
closes only a bead it owns, or reads the gate rule of the bead it closes.
"""

from __future__ import annotations

import re
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# A tracker write that closes a bead: `--status closed` / `--status=closed`
# (shell or argv list), or `bd close` with an id. `list --status closed` is
# a read, and a comment closes nothing.
CLOSE = re.compile(
    r"""--status[= ]closed\b|["']--status["'],\s*["']closed["']|["']bd["'],\s*["']close["']"""
    r"""|run_bd\(\[\s*["']close["']|\bbd close\s+["$]""")
READ = re.compile(r"\blist\b")

# path -> (number of close writes, what they close and why that is allowed).
# The bin/ entries are named without their directory: this file only reads
# the scripts, and a path to one reads as running it (tests/sandbox-isolation-check-test.sh).
BIN_CLOSERS: dict[str, tuple[int, str]] = {
    "deliver-close": (1, "a delivery bead, after convoy-state says it is not a new-flow ticket"),
    "factory-delivery-guard": (2, "the one bead a delivered workflow's input convoy tracks, and that "
                                  "convoy, after convoy-state says the bead is not a new-flow ticket"),
    "outcome-promote": (1, "the open tickets of an abandoned convoy, after record-gate withdrawn"),
    "ticket-graph-publish": (3, "a withdrawn ticket after record-gate withdrawn; merges/supersedes of "
                                "an old-flow graph only (the new-flow ticket fields refuse them)"),
    "convoy-advance": (4, "its own beads: an incident, a resume or a draft it created"),
    "code-review": (1, "its own review bead the dispatch door refused"),
    "correction-round": (1, "its own correction bead the dispatch door refused"),
    "ticket-evaluation": (1, "its own evaluation bead the dispatch door refused"),
    "outcome-evaluation": (1, "its own evaluation bead the dispatch door refused"),
    "spec-end-review": (2, "its own end-review or request bead a door refused"),
    "ticket-exit": (1, "its own revision draft the patch door refused"),
    "evaluation-launch-cancel": (1, "the evaluation launch bead it cancels"),
    "factory-watchdog": (3, "its own incident beads, once recovered"),
    "factory-session-loop-guard": (2, "its own incident beads, once recovered"),
    "pr-autopilot": (2, "its own stuck/CI-failure beads, once the PR recovered"),
    "provider-failover": (1, "its own provider-exhaustion bead"),
    "order-pause": (1, "its own pause record"),
    "mail-reply-reap": (2, "mail beads answered"),
    "planning-map": (1, "a planning-map issue"),
    "planning-artifacts-close": (1, "the planning artifact of a closed convoy"),
    "proposal-door": (1, "the maintenance bead of a proposal reconverted into a decision"),
}
CLOSERS: dict[str, tuple[int, str]] = {
    "lib/convoy_state.py": (3, "the gates themselves: close-ticket, withdraw-ticket, close-convoy, "
                               "each with its record in the same write"),
    **{f"bin/{name}": entry for name, entry in BIN_CLOSERS.items()},
}


def close_writes() -> Counter:
    found: Counter = Counter()
    for path in sorted([*ROOT.joinpath("bin").iterdir(), *ROOT.joinpath("lib").rglob("*")]):
        if not path.is_file() or path.suffix in (".md", ".json", ".toml", ".tsv", ".txt"):
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        for line in text.splitlines():
            if not line.strip().startswith("#") and CLOSE.search(line) and not READ.search(line):
                found[str(path.relative_to(ROOT))] += 1
    return found


class BeadCloseWritersTest(unittest.TestCase):
    def test_every_close_write_is_named_with_what_it_closes(self):
        found = close_writes()
        unnamed = {path: count for path, count in found.items() if path not in CLOSERS}
        changed = {path: (count, CLOSERS[path][0]) for path, count in found.items()
                   if path in CLOSERS and count != CLOSERS[path][0]}
        gone = sorted(set(CLOSERS) - set(found))
        self.assertEqual(
            ({}, {}, []), (unnamed, changed, gone),
            "a write that closes a bead changed: name it in CLOSERS with what it closes. A ticket of a "
            "new-flow convoy closes only through its gates (bin/convoy-state); ask it as bin/deliver-close "
            "does before closing a bead that is not your own (unnamed, (found, named), gone)")

    def test_the_lint_sees_each_form_of_close_and_not_a_read(self):
        for line in ('gc bd update "$b" --status=closed', 'run(["bd", "update", t, "--status", "closed"])',
                     'run([GC_BIN, "bd", "close", bead_id])', '"$GC_BIN" bd close "$id"',
                     'run_bd(["close", issue["id"]])'):
            self.assertRegex(line, CLOSE)
        self.assertRegex('gc bd list --all --status closed', READ)


if __name__ == "__main__":
    unittest.main()
