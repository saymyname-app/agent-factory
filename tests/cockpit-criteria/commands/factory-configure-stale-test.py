#!/usr/bin/env python3
"""Criterion test 3 of G2 « Usine — réglages et nettoyage par les portes
existantes » (af-f8nlhr; Spec af-fgcw0d, user story 174, and of af-2zseit
the decision 8: « après une issue incertaine relire la source avant toute
répétition, sans masquer un succès déjà enregistré »; Testing Decisions 1, 3
and 8): the settings of a role when the configuration read is stale, then
when a setting had an uncertain outcome.

The setting is the one of criterion 1 (factory-configure-test.py): the
reviewer of delivery on Claude Opus 5.5 · effort élevé · lecture seule first,
through the door provider-failover (set). Each case launches the real
cockpit with the launcher of the profile, bin/project-launch, on the Usine of health-content
(usine_reglages.serve_usine):

- the configuration read goes stale: a check of a section of the page stays
  current eight seconds (`usine_check_validity_seconds`), not five minutes;
- the setting has an uncertain outcome: the door writes its record, then
  never answers (`records-then-expires`).

The page GET /usine?role=reviewer is read where a headless Chromium renders
it, « Revérifier maintenant » of the section « Agents dans le workflow »
reads the configuration again, and the setting is sent as the browser sends
it (pour_moi.Operator).

False if a setting goes on a stale configuration, or is sent again to its
door before the configuration was read again, or if what the door recorded
is hidden once it was.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree  # noqa: E402
from usine_reglages import (  # noqa: E402
    DOOR_SECONDS, PAGE, Operator, frame_control, in_service, measure, measure_until, recheck_of, says_in_one_sentence,
    section_titled, serve_usine,
)

REVIEWER = PAGE + "?role=reviewer"
SETTING = {"role": "reviewer", "principal": "claude-readonly", "confirm": True}
OPUS_5_5 = re.compile(r"opus[\s-]*5[.,]5", re.I)
AGENTS = "Agents dans le workflow"
VALIDITY_SECONDS = 8


def configure(frame: dict) -> dict | None:
    return frame_control(frame, "Configurer")


class FactoryConfigureStale(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_refused(self, answer, reason: str) -> None:
        self.assertEqual("", answer.broken, f"the request broke: {answer}")
        self.assertIsNotNone(answer.status, f"no HTTP answer: {answer}")
        self.assertGreaterEqual(answer.status, 400, f"the setting went: {answer}")
        self.assertNotEqual(500, answer.status, f"the cockpit broke: {answer}")
        self.assertIsInstance(answer.body, dict, f"the answer is no readable error: {answer}")
        self.assertRegex(answer.error(), reason, f"the refusal does not say why: {answer}")

    def rechecked(self, address: str) -> dict:
        """The page after « Revérifier maintenant » of the section of the
        roles was activated."""
        frame = measure(address, REVIEWER)[0]
        section, _ = section_titled(self, frame, AGENTS)
        control = recheck_of(self, frame, section)
        after = measure(address, REVIEWER, click=control["name"])[0]["after"]
        self.assertTrue(after["found"], f"« {control['name']} » is not on the page")
        return after

    def test_a_stale_configuration_disables_the_setting_with_its_reason_and_refuses_it_until_read_again(self):
        address = serve_usine(self.tree, check_validity=VALIDITY_SECONDS)
        fresh = measure(address, REVIEWER)[0]
        self.assertIsNotNone(configure(fresh), "the reviewer has no control « Configurer »")
        self.assertFalse(configure(fresh)["disabled"], "the setting cannot be made on a configuration just read")

        stale = measure_until(address, lambda frames: (configure(frames[0]) or {}).get("disabled") is True,
                              seconds=VALIDITY_SECONDS + 20, path=REVIEWER)[0]
        self.assertTrue((configure(stale) or {}).get("disabled"), "the setting is still offered on a stale configuration")
        _, agents = section_titled(self, stale, AGENTS)
        self.assertTrue(says_in_one_sentence(agents, r"indisponible|désactivé", r"périmé", r"configuration|réglage"),
                        f"no sentence says the setting is unavailable because the configuration is stale: « {agents} »")

        answer = Operator(address).gesture("regler", SETTING)
        self.assert_refused(answer, r"(?i)périmé")

        after = self.rechecked(address)
        self.assertFalse((configure(after) or {"disabled": True})["disabled"],
                         "the setting is not offered again once the configuration was read again")
        _, agents = section_titled(self, after, AGENTS)
        self.assertNotRegex(in_service(agents), OPUS_5_5, f"the setting refused was applied: « {agents} »")

    def test_an_uncertain_setting_is_not_sent_again_before_a_reading_and_its_record_is_then_shown(self):
        address = serve_usine(self.tree, doors={"provider-failover": "records-then-expires"})
        operator = Operator(address)
        answer = operator.gesture("regler", SETTING)
        self.assert_refused(answer, r"(?i)expir|incertain")

        blocked = measure(address, REVIEWER)[0]
        self.assertTrue((configure(blocked) or {}).get("disabled"),
                        "the setting is offered again before the configuration was read again")
        _, agents = section_titled(self, blocked, AGENTS)
        self.assertTrue(says_in_one_sentence(agents, r"incertain", r"revérifi|reli|relu|relecture"),
                        f"no sentence says the outcome is uncertain and asks a reading: « {agents} »")

        again = operator.gesture("regler", SETTING)
        self.assert_refused(again, r"(?i)revérifi|reli|relu|relecture")
        self.assertLess(again.seconds, DOOR_SECONDS - 1, f"the setting was sent to its door again: {again}")

        after = self.rechecked(address)
        _, agents = section_titled(self, after, AGENTS)
        self.assertRegex(in_service(agents), OPUS_5_5,
                         f"the setting the door recorded is hidden once the configuration was read again: « {agents} »")


if __name__ == "__main__":
    unittest.main()
