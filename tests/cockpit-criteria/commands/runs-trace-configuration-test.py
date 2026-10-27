#!/usr/bin/env python3
"""Criterion test 1 of C2a « Runs — sessions, configuration et prompts
collectés » (af-k2rbw1; Spec af-fgcw0d, user stories 138 and 145, Testing
Decisions 1, 5, 7 and 8): the configuration of the agent of a job, state
job-configuration.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset job-configuration, and reads GET
/runs/job -- the job « Réaliser » of « Recherche dans les notes », or another
job of that run clicked in its frise -- as a headless Chromium renders it.

The section « Configuration de l’agent » says first the configuration in
effect, as observed for the session -- provider, model, effort, tools,
environment, mission, session, context --, then, apart, the configuration
declared for the role of the job when its session took it. A value nothing
observed is said not collected, even when the declared one is known -- the
mission of a session, which the supervisor does not report, among them.

False if the declared configuration is shown as the one in effect, a value
nothing observed is given one (the name of the job for the mission), or a
session is attributed to a job no session was recorded for.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from runs_destination import LaunchTree, observe, section  # noqa: E402
from runs_trace import head_says, percent  # noqa: E402


class RunsTraceConfiguration(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def parts(self, reading: dict, effective: str, declared: str) -> tuple[str, str]:
        """What the section « Configuration de l’agent » says from the title
        `effective` of the configuration in effect, then from the title
        `declared` of the configuration declared."""
        found = section(reading, "Configuration")
        self.assertIsNotNone(found, "the detail has no section « Configuration »")
        said = found["content"]
        self.assertIn(effective, said, f"the configuration in effect is not said apart: « {said} »")
        self.assertIn(declared, said, f"the configuration declared is not said apart: « {said} »")
        self.assertLess(said.index(effective), said.index(declared),
                        "the configuration declared comes before the one in effect")
        return said[said.index(effective):said.index(declared)], said[said.index(declared):]

    def test_job_configuration_says_what_the_last_session_ran_with_apart_from_what_was_declared(self):
        reading, = observe(self.tree.launch("job-configuration"), "/runs/job")[0]
        self.assertIn("Réaliser", head_says(reading), "the detail is not that of the job « Réaliser »")
        self.assertTrue(section(reading, "Configuration")["open"], "job-configuration does not open the configuration")
        effective, declared = self.parts(reading, "Configuration effective", "Configuration déclarée")
        # The last session of « Réaliser », demo-search-alex-2, as the
        # supervisor reported it: codex, gpt-6.1-sol, the effort high, the
        # tools it called, its context 7 %.
        for phrase in ("codex", "gpt-6.1-sol", "high", "read · rg · exec · write", "demo-search-alex-2"):
            self.assertIn(phrase, effective, f"the configuration in effect does not say « {phrase} »: « {effective} »")
        self.assertRegex(effective, percent(7), f"the configuration in effect does not say its context: « {effective} »")
        # No source reports the mission of a session: it is not taken from
        # the name of the job.
        mission = re.compile(r"Mission\s*" + "non collecté")
        self.assertRegex(effective, mission, f"the mission nothing reported is not said not collected: « {effective} »")
        self.assertNotIn("Réaliser", effective, "the name of the job is shown as the mission in effect")
        self.assertNotIn("non collecté", mission.sub("", effective), f"a value observed is said not collected: « {effective} »")
        # Declared when the session took the ticket: the agent of the role,
        # its provider and its model -- and nothing a session showed.
        for phrase in ("delivery-author", "codex", "gpt-6.1-sol"):
            self.assertIn(phrase, declared, f"the configuration declared does not say « {phrase} »: « {declared} »")
        self.assertNotRegex(declared, percent(7), "the context observed is said declared")
        self.assertNotIn("demo-search-alex-2", declared, "the session observed is said declared")

    def test_a_value_the_supervisor_did_not_report_stays_not_collected_beside_the_declared_one(self):
        _, reading = observe(self.tree.launch("job-configuration"), "/runs/job", steps=(
            {"click": "Revue du code", "within": "chart"},
        ))[0]
        self.assertTrue(reading["step"]["found"], "no job « Revue du code » to click in the frise")
        self.assertIn("Revue du code", head_says(reading), "the detail is not that of the job « Revue du code »")
        effective, declared = self.parts(reading, "Configuration effective", "Configuration déclarée")
        self.assertIn("demo-search-lea-1", effective, f"the session of the job is not said: « {effective} »")
        self.assertIn("claude", effective, f"the provider observed is not said: « {effective} »")
        self.assertRegex(effective, percent(3), f"the context observed is not said: « {effective} »")
        # Neither its model nor its effort was reported for the session: the
        # declared model does not become the one in effect.
        self.assertIn("non collecté", effective, f"the model nothing reported is not said not collected: « {effective} »")
        self.assertNotIn("claude-opus-5-5", effective, "the model declared is shown as the one in effect")
        self.assertNotIn("gpt-6.1-sol", effective, "the model of another agent is shown as the one in effect")
        for phrase in ("delivery-reviewer", "claude-opus-5-5"):
            self.assertIn(phrase, declared, f"the configuration declared does not say « {phrase} »: « {declared} »")

    def test_a_job_no_session_was_recorded_for_is_attributed_none(self):
        _, review, tests = observe(self.tree.launch("job-configuration"), "/runs/job", steps=(
            {"click": "Revue du code", "within": "chart"},
            {"click": "Relire les tests", "within": "chart"},
        ))[0]
        # Léa worked « Revue du code » in a session of hers...
        self.assertTrue(review["step"]["found"], "no job « Revue du code » to click in the frise")
        worked = section(review, "Sessions du job")
        self.assertIsNotNone(worked, "the detail has no section « Sessions du job »")
        self.assertIn("demo-search-lea-1", worked["content"], "the session that worked « Revue du code » is not said")
        # ...which is not the one of « Relire les tests », no session was
        # recorded for.
        self.assertTrue(tests["step"]["found"], "no job « Relire les tests » to click in the frise")
        self.assertIn("Relire les tests", head_says(tests), "the detail is not that of the job « Relire les tests »")
        sessions = section(tests, "Sessions du job")
        self.assertIsNotNone(sessions, "the detail has no section « Sessions du job »")
        self.assertIn("non collecté", sessions["content"], "the job no session was recorded for says a session")
        configured = section(tests, "Configuration")
        self.assertIsNotNone(configured, "the detail has no section « Configuration »")
        for said in (sessions["content"], configured["content"]):
            self.assertNotIn("demo-search-lea", said, "a session of the agent is attributed to a job "
                                                       "no session was recorded for")
            self.assertNotRegex(said, percent(3), "the context of another job is attributed to this one")

if __name__ == "__main__":
    unittest.main()
