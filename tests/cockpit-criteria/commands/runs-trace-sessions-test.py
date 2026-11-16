#!/usr/bin/env python3
"""Criterion test 1 of C2a « Runs — sessions, configuration et prompts
collectés » (af-k2rbw1; Spec af-fgcw0d, user stories 130, 137 and 145,
Testing Decisions 1, 5, 7 and 8): the sessions of a job, state
job-sessions, and the context of the last session of each agent on its
lane.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset job-sessions, and reads GET /runs/job --
the job « Réaliser » of « Recherche dans les notes », under the frise of
its run -- as a headless Chromium renders it, then over HTTP the page the
browser was on, or on a dataset the case declares from it.

The section « Sessions du job » lists each session that worked the job,
in the order they ran, each with its identifier, its start and end from the
trigger of the run, its model and the context observed in it; the lane of
an agent shows the context of the last session of that agent observed in
the run, the history of the job keeps the values of each session. Choosing
a session of the history shows its own configuration and its own prompts.
A session whose start or end the supervisor did not record says it not
collected.

False if the history of a job shows the values of its last session for an
earlier one, if choosing an earlier session keeps the prompts of the last,
if a reload loses the session chosen, if an agent with no session observed
gets a context, or if a start or an end nothing recorded is taken from
another time.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from project_destination import dataset_of, launch_declared  # noqa: E402
from runs_destination import LaunchTree, lanes, observe, section  # noqa: E402
from runs_trace import head_says, percent, raw_texts  # noqa: E402


class RunsTraceSessions(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def history(self, reading: dict) -> str:
        found = section(reading, "Sessions du job")
        self.assertIsNotNone(found, "the detail has no section « Sessions du job »")
        self.assertEqual("details", found["tag"], "the history of the sessions does not fold")
        return found["content"]

    def test_job_sessions_lists_each_session_with_its_id_its_times_its_model_and_its_context(self):
        reading, = observe(self.tree.launch("job-sessions"), "/runs/job")[0]
        self.assertIn("Réaliser", head_says(reading), "the detail is not that of the job « Réaliser »")
        found = section(reading, "Sessions du job")
        self.assertIsNotNone(found, "the detail has no section « Sessions du job »")
        self.assertTrue(found["open"], "job-sessions does not open the history of the sessions")
        said = self.history(reading)
        self.assertNotIn("non collecté", said, f"the sessions of the job are said not collected: « {said} »")
        self.assertEqual(1, said.count("demo-search-alex-1"), f"the first session is not listed once: « {said} »")
        self.assertEqual(1, said.count("demo-search-alex-2"), f"the last session is not listed once: « {said} »")
        first, last = said.index("demo-search-alex-1"), said.index("demo-search-alex-2")
        self.assertLess(first, last, "the sessions are not listed in the order they ran")
        # Each session, its own values, as the supervisor recorded them: the
        # first from +3 min 10 s to +4 min 37 s (context 27 %), the second
        # from +4 min 37 s to +6 min 5 s (context 7 %), both on gpt-6.1-sol.
        earlier, later = said[first:last], said[last:]
        for phrase in ("+3 min 10 s", "+4 min 37 s", "gpt-6.1-sol"):
            self.assertIn(phrase, earlier, f"the first session does not say « {phrase} »: « {earlier} »")
        self.assertRegex(earlier, percent(27), f"the first session does not say its context: « {earlier} »")
        self.assertNotRegex(earlier, percent(7), "the first session shows the context of the last")
        for phrase in ("+4 min 37 s", "+6 min 5 s", "gpt-6.1-sol"):
            self.assertIn(phrase, later, f"the last session does not say « {phrase} »: « {later} »")
        self.assertRegex(later, percent(7), f"the last session does not say its context: « {later} »")
        self.assertNotRegex(later, percent(27), "the last session shows the context of the first")

    def test_a_lane_shows_the_context_of_the_last_session_of_its_agent(self):
        reading, = observe(self.tree.launch("job-sessions"), "/runs/job")[0]
        by_who = {lane["name"].split()[0]: lane["name"] for lane in lanes(reading) if lane["name"]}
        self.assertEqual(["Benjamin", "Code", "Alex", "Léa", "Noé"], list(by_who),
                         "the frise of the run is not whole beside the detail")
        alex = by_who["Alex"]
        self.assertIn("dernière session", alex, f"the lane of Alex says no last session: « {alex} »")
        self.assertRegex(alex, percent(7), f"the lane of Alex does not say the context of his last session: « {alex} »")
        self.assertNotRegex(alex, percent(27), "the lane of Alex shows the context of an earlier session")
        self.assertIn("gpt-6.1-sol", alex, f"the lane of Alex does not say the model he runs on: « {alex} »")
        self.assertRegex(by_who["Léa"], percent(3), f"the lane of Léa does not say her context: « {by_who['Léa']} »")
        # No session of Noé was observed: his context is not known.
        noe = by_who["Noé"]
        self.assertIn("non collecté", noe, f"the lane of Noé gives a context no session showed: « {noe} »")
        self.assertNotRegex(noe, r"\d\s%", f"the lane of Noé gives a context no session showed: « {noe} »")

    def test_choosing_an_earlier_session_shows_its_own_configuration_and_prompts_and_a_reload_keeps_it(self):
        address = self.tree.launch("job-sessions")
        shown, chosen, reloaded = observe(address, "/runs/job", steps=(
            {"click": "demo-search-alex-1", "within": "session-history"},
            {"reload": True},
        ))[0]
        # By default, the last session of the job.
        configured = section(shown, "Configuration")
        self.assertIsNotNone(configured, "the detail has no section « Configuration »")
        self.assertIn("demo-search-alex-2", configured["content"], "the configuration shown is not that of the last session")
        last = "\n".join(raw_texts(address, shown["href"]))
        self.assertIn("Version : exemple synthétique\n", last, "the prompts shown are not those sent to the last session")
        self.assertTrue(chosen["step"]["found"], "no control to choose the session demo-search-alex-1 in the history")
        for reading in (chosen, reloaded):
            configured = section(reading, "Configuration")
            self.assertIsNotNone(configured, "the detail has no section « Configuration » once a session is chosen")
            self.assertIn("demo-search-alex-1", configured["content"], "the configuration is not that of the session chosen")
            self.assertNotIn("demo-search-alex-2", configured["content"], "the configuration of the last session stays shown")
            self.assertRegex(configured["content"], percent(27), "the configuration does not say the context "
                                                                   "of the session chosen")
            sent = "\n".join(raw_texts(address, reading["href"]))
            # The user prompt of each session names the session it was sent
            # to; both were sent the same system prompt.
            self.assertIn("Version : exemple synthétique, première session", sent,
                          "the prompts shown are not those sent to the session chosen")
            self.assertNotIn("Version : exemple synthétique\n", sent,
                             "the session chosen shows the prompts of the last session")
            self.assertIn("# Auteur\n\n# Mission\nRéaliser sur le périmètre approuvé.", sent,
                          "the system prompt sent to the session chosen is not shown")

    def test_a_session_whose_end_the_supervisor_did_not_record_says_it_not_collected(self):
        # job-sessions, but the supervisor recorded the stop of neither
        # session of « Réaliser »: the first did not end when the second
        # began, the second did not end with the job.
        dataset = dataset_of(self.tree, "job-sessions")
        run = next(run for run in dataset["fixtures"]["runs"] if run["id"] == "search")
        build = next(job for job in run["jobs"] if job["id"] == "build")
        for session in build.get("sessions") or []:
            session.pop("end", None)
        reading, = observe(launch_declared(self.tree, "job-sessions-no-end", dataset), "/runs/job")[0]
        said = self.history(reading)
        self.assertIn("demo-search-alex-1", said, f"the first session is not listed: « {said} »")
        self.assertIn("demo-search-alex-2", said, f"the last session is not listed: « {said} »")
        first, last = said.index("demo-search-alex-1"), said.index("demo-search-alex-2")
        earlier, later = said[first:last], said[last:]
        self.assertIn("+3 min 10 s", earlier, f"the first session does not say its start: « {earlier} »")
        self.assertIn("non collecté", earlier, f"the end of the first session is not said not collected: « {earlier} »")
        self.assertNotIn("+4 min 37 s", earlier, "the first session ends where the next one began")
        self.assertIn("+4 min 37 s", later, f"the last session does not say its start: « {later} »")
        self.assertIn("non collecté", later, f"the end of the last session is not said not collected: « {later} »")
        self.assertNotIn("+6 min 5 s", later, "the last session ends where the job ended")

    def test_a_session_whose_start_the_supervisor_did_not_record_says_it_not_collected(self):
        # job-sessions, but the supervisor recorded neither the creation nor
        # the waking of the first session of « Réaliser »: its start is not
        # the start of the job (+3 min 10 s), nor its claim.
        dataset = dataset_of(self.tree, "job-sessions")
        run = next(run for run in dataset["fixtures"]["runs"] if run["id"] == "search")
        build = next(job for job in run["jobs"] if job["id"] == "build")
        build["sessions"][0].pop("start")
        reading, = observe(launch_declared(self.tree, "job-sessions-no-start", dataset), "/runs/job")[0]
        said = self.history(reading)
        self.assertEqual(1, said.count("demo-search-alex-1"), f"the first session is not listed once: « {said} »")
        self.assertEqual(1, said.count("demo-search-alex-2"), f"the last session is not listed once: « {said} »")
        first, last = said.index("demo-search-alex-1"), said.index("demo-search-alex-2")
        earlier = said[first:last] if first < last else said[first:]
        later = said[last:first] if last < first else said[last:]
        self.assertIn("non collecté", earlier, f"the start of the first session is not said not collected: « {earlier} »")
        self.assertNotIn("+3 min 10 s", earlier, "the first session begins when the job began")
        self.assertIn("+4 min 37 s", earlier, f"the first session does not say its end: « {earlier} »")
        # The last session keeps what was recorded of it.
        for phrase in ("+4 min 37 s", "+6 min 5 s"):
            self.assertIn(phrase, later, f"the last session does not say « {phrase} »: « {later} »")
        self.assertNotIn("non collecté", later, f"a time recorded of the last session is said not collected: « {later} »")


if __name__ == "__main__":
    unittest.main()
