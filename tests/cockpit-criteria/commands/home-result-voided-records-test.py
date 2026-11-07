#!/usr/bin/env python3
"""Criterion test 3 of A2 « Essai et Avis » (af-ocz64w; Spec af-fgcw0d,
user stories 118 and 123, Implementation Decisions 3 and 7 of af-2zseit
kept, Testing Decisions 1, 2 and 8), on the records of D01: an acceptance
voided after a conflict.

The records are produced as Testing Decisions 2 says: the reference driver
of the Fixture City walks one convoy to its Delivered Outcome (the harness
FixtureCityWalk of tests/convoy-stops-fixture-city-test.py, walked once and
restored); Benjamin's verdict and his « accepté » are recorded by
bin/owner-answer; the protected branch then receives a commit from
elsewhere in conflict with the convoy, and the next pass of the order merges
nothing and voids the acceptance, as
tests/owner-answer-promotion-fixture-city-test.py walks it. The tracker
the commands wrote is the tracker of a cockpit the launcher of the profile,
bin/project-launch, starts (pour_moi.serve_tracker), walked in a headless
Chromium (result_trial.walk).

The acceptance voided is signalled to Benjamin -- in « Ce qui t’attend »,
where what waits for him is listed, and on the result -- with its cause and
the new judgement it needs; it is said accepted nowhere: neither on the
result, nor on the line of its project, nor in the result the cockpit serves.

False if the voided acceptance stays effective, or is not signalled.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree  # noqa: E402
from pour_moi import serve_tracker  # noqa: E402
from result_trial import last, read_json, result_of, shown, walk  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]


def load(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_").removesuffix(".py"), str(ROOT / "tests" / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


stops = load("convoy-stops-fixture-city-test.py")
# The walk of a protected branch moved in conflict after « accepté ».
promotion = load("owner-answer-promotion-fixture-city-test.py")
# bin/owner-answer, the entry point of the profile that records the answer.
OWNER = ROOT / "bin" / "owner-answer"
APPROVER = "benjamin"


class HomeResultVoidedRecords(stops.FixtureCityWalk):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()
        super().tearDownClass()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def owner_ok(self, command: str, *args) -> dict:
        proc = self.tool(OWNER, command, self.convoy, "--repo", self.repo, "--approved-by", APPROVER, *args)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    # --- Criterion 3 ------------------------------------------------------------

    def test_an_acceptance_voided_after_a_conflict_is_signalled_and_no_longer_effective(self):
        delivered = self.walk_to_delivered(inject="proposition")
        shown_city = self.shown()
        integration = shown_city["convoy"]["integration"]["branch"]
        for ticket in shown_city["tickets"]:
            for found in ticket.get("findings") or []:
                if found["classification"] == "proposal":
                    self.owner_ok("verdict", "--proposition", found["id"], "--verdict", "sans suite", "--words", "Vu.")
        self.owner_ok("record", "--response", "accepté", "--words", "Accepté, c'est ce que je voulais.",
                      "--commit", delivered["commit"], "--pack-digest", delivered["pack"])
        [written] = subprocess.run(
            ("git", "-C", str(self.repo), "diff", "--name-only", "--diff-filter=A", "main", integration),
            text=True, capture_output=True, check=True).stdout.split()[:1]
        promotion.PromotionOnTheFixtureCity.commit_to_main(self, written, "écrit ailleurs, autrement\n")
        self.driver("advance")
        answer = self.shown()["convoy"]["judgement"]["answers"][-1]
        self.assertEqual(("accepted", "conflict"), (answer["response"], answer["voided"]["cause"]),
                         "the pass did not void the acceptance")

        tracker = json.loads(self.tracker.read_text(encoding="utf-8"))
        address = serve_tracker(self.tree, tracker["beads"])
        page = last(walk(address, []))
        text = shown(page)
        # Signalled where what waits for him is listed, with its cause.
        waiting = [request["quoi"] + " " + (request.get("pourquoi") or "")
                   for request in read_json(address, "/api/requests")["requests"]]
        self.assertEqual(1, len([line for line in waiting if re.search(r"(?i)acceptation annulée", line)]),
                         f"the voided acceptance is not signalled among what waits for him: {waiting}")
        self.assertRegex(text, r"(?i)acceptation annulée", "the result does not say the acceptance voided")
        self.assertRegex(text, r"(?i)conflit", "the cause of the voiding is not said")
        self.assertRegex(text, r"(?i)nouveau jugement", "the new judgement it needs is not said")
        # Said accepted nowhere.
        self.assertNotRegex(text, r"\bAccepté\b|Tu as accepté|fusion est en attente",
                            "the voided acceptance is still shown effective")
        _, result = result_of(address)
        self.assertNotIn(result["issue"], ("accepted", "merging", "merged"), "the voided acceptance is served effective")


if __name__ == "__main__":
    unittest.main()
