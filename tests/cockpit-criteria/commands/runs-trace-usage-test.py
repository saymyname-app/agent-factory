#!/usr/bin/env python3
"""Criterion test 1 of C2b « Runs — événements, contrôles, sorties, usage et
historique durable » (af-ofz29f; Spec af-fgcw0d, user story 141, Testing
Decisions 1, 7 and 8): the usage of a job in tokens and cost, states
job-usage and job-usage-unavailable.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on job-usage-unavailable or on a dataset the case
declares from job-usage or job-usage-unavailable: the sessions of a job
the case writes, each with what its provider recorded of its usage, in the
provider's own format -- Codex the usage of the session so far at each
turn, its cache read part of what it was given and its reasoning part of
what it printed; Claude Code the usage of each message, repeated on each
record of the message. The case reads GET /runs/job -- the job the state
selects, or another opened from the frise -- as a headless Chromium renders
it, and the table of its usage as the cockpit serves it.

The section « Tokens et coût » gives each category the provider records
and the total it records, the cost not collected when no price is, and
says whether the usage is complete; the head of the run gives the tokens
known of the run.

False if a count missing is shown as zero, if categories that overlap are
added into the total, if what a session replays or a message repeats is
counted again, if the whole usage of a session is counted for each job it
worked, or if a usage partial or still growing is said complete.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from project_destination import dataset_of, launch_declared  # noqa: E402
from runs_destination import LaunchTree, observe, section, text  # noqa: E402
from runs_job_trace import (claude_message, claude_result, claude_user, codex_start, codex_usage,  # noqa: E402
                            job_of, number, tokens, usage_table)

SYSTEM = "# Auteur\n\n# Mission\nRéaliser sur le périmètre approuvé."


class RunsTraceUsage(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def usage(self, reading: dict) -> str:
        found = section(reading, "Tokens et coût")
        self.assertIsNotNone(found, "the detail has no section « Tokens et coût »")
        return " ".join(found["content"].split())

    def assert_row(self, table: dict, label: str, value: int) -> None:
        self.assertIn(label, table, f"the usage has no row « {label} »: {table}")
        self.assertRegex(table[label][0] if table[label] else "", number(value),
                         f"the row « {label} » does not say {value}: {table[label]}")

    def test_job_usage_gives_each_codex_category_and_the_total_codex_records_never_their_sum(self):
        dataset = dataset_of(self.tree, "job-usage")
        first = (codex_start("demo-search-alex-1", "12:13:10.000", SYSTEM, "# Tâche\nRéaliser.")
                 + codex_usage([("12:13:20.000", tokens(20000, 15000, 1500, 400)),
                                ("12:14:30.000", tokens(31554, 24000, 2537, 673))]))
        # The second session replays at its head what the first recorded,
        # its usage included, then counts its own from zero.
        second = (first + codex_start("demo-search-alex-2", "12:14:37.000", SYSTEM, "# Tâche\nRéaliser, suite.")
                  + codex_usage([("12:14:50.000", tokens(9000, 8000, 1000, 200)),
                                 ("12:15:50.000", tokens(18446, 16616, 2000, 300))]))
        job_of(dataset, "search", "build")["sessions"] = [
            {"name": "demo-search-alex-1", "provider": "codex", "start": 190, "end": 277, "transcript": first},
            {"name": "demo-search-alex-2", "provider": "codex", "start": 277, "end": 365, "transcript": second},
        ]
        address = launch_declared(self.tree, "job-usage-codex", dataset)
        reading, = observe(address, "/runs/job")[0]
        table = usage_table(address, reading["href"])
        # The last count of each session, added: 31 554 + 18 446 given, of
        # which 24 000 + 16 616 read from the cache; 2 537 + 2 000 printed,
        # of which 673 + 300 of reasoning; nothing written to the cache.
        for label, value in (("Entrée", 50000), ("Cache lu", 40616), ("Cache écrit", 0), ("Sortie", 4537),
                             ("Raisonnement", 973)):
            self.assert_row(table, label, value)
        # The total Codex records, 34 091 + 20 446: not the five rows
        # added (96 126), nor the first session counted again through the
        # second (88 628).
        self.assert_row(table, "Total", 54537)
        said = self.usage(reading)
        self.assertIn("complet", said, f"the usage of two sessions counted to their end is not said complete: « {said} »")
        self.assertNotIn("partiel", said, f"a complete usage is said partial: « {said} »")
        self.assertIn("non collecté", " ".join(table["Total"]).lower(), f"the cost is not said not collected: {table}")
        for currency in ("€", "$", "USD", "EUR"):
            self.assertNotIn(currency, said, f"a cost no price was collected for is given: « {said} »")
        # The head of the run: the tokens known of its sessions, the other
        # jobs of the run having no usage recorded.
        head = text(reading, "run-summary")
        self.assertRegex(head, number(54537), f"the head of the run does not give the tokens known: « {head} »")
        self.assertIn("partiel", head, f"the head of the run does not say its usage partial: « {head} »")

    def test_a_session_that_worked_two_jobs_counts_for_each_only_what_it_used_while_it_worked_it(self):
        dataset = dataset_of(self.tree, "job-usage")
        # One session of Alex works « Préparer les tests » (+42 s to +2 min
        # 2 s), then « Réaliser » (+3 min 10 s to +6 min 5 s), as an author
        # session works the steps of its ticket.
        shared = (codex_start("demo-search-alex-1", "12:10:42.000", SYSTEM, "# Tâche\nPréparer les tests.")
                  + codex_usage([("12:10:50.000", tokens(3800, 3000, 200, 50)),
                                 ("12:11:50.000", tokens(8500, 7000, 500, 100)),
                                 ("12:13:30.000", tokens(14000, 11000, 1000, 300)),
                                 ("12:15:50.000", tokens(22800, 18000, 1200, 350))]))
        session = {"name": "demo-search-alex-1", "provider": "codex", "start": 42, "end": 365, "transcript": shared}
        job_of(dataset, "search", "tests")["sessions"] = [session]
        job_of(dataset, "search", "build")["sessions"] = [session]
        address = launch_declared(self.tree, "job-usage-shared", dataset)
        build, tests = observe(address, "/runs/job", steps=({"click": "Préparer les tests", "within": "chart"},))[0]
        self.assertTrue(tests["step"]["found"], "no job « Préparer les tests » to open on the frise")
        # « Préparer les tests »: what the session used up to its end,
        # 8 500 given and 500 printed.
        table = usage_table(address, tests["href"])
        self.assert_row(table, "Entrée", 8500)
        self.assert_row(table, "Total", 9000)
        # « Réaliser »: what it used since, 22 800 - 8 500 given and
        # 1 200 - 500 printed -- never the 24 000 of the whole session.
        table = usage_table(address, build["href"])
        self.assert_row(table, "Entrée", 14300)
        self.assert_row(table, "Sortie", 700)
        self.assert_row(table, "Total", 15000)
        # The run counts the session once.
        head = text(build, "run-summary")
        self.assertRegex(head, number(24000), f"the head of the run does not count the session once: « {head} »")

    def test_a_claude_code_session_counts_each_message_once_in_the_categories_of_claude(self):
        dataset = dataset_of(self.tree, "job-usage")
        name = "demo-search-lea-1"
        # Two messages, each written by Claude Code as two records that both
        # repeat its usage.
        first_usage = {"input_tokens": 2, "cache_creation_input_tokens": 2715, "cache_read_input_tokens": 28583,
                       "output_tokens": 2697, "output_tokens_details": {"thinking_tokens": 53}}
        second_usage = {"input_tokens": 5, "cache_creation_input_tokens": 1200, "cache_read_input_tokens": 31298,
                        "output_tokens": 803, "output_tokens_details": {"thinking_tokens": 20}}
        transcript = ([claude_user(name, "12:16:10.000", "# Tâche\nRelire le code.")]
                      + claude_message(name, "12:16:20.000", "msg_lea_1", first_usage, [
                          {"type": "thinking", "thinking": ""},
                          {"type": "tool_use", "id": "toolu_lea_1", "name": "Read", "input": {"file_path": "notes/search.py"}}])
                      + [claude_result(name, "12:16:30.000", "toolu_lea_1")]
                      + claude_message(name, "12:17:00.000", "msg_lea_2", second_usage, [
                          {"type": "thinking", "thinking": ""}, {"type": "text", "text": "Relu."}]))
        job_of(dataset, "search", "code-review")["sessions"] = [
            {"name": name, "provider": "claude", "start": 365, "end": 430, "transcript": transcript}]
        address = launch_declared(self.tree, "job-usage-claude", dataset)
        _, review = observe(address, "/runs/job", steps=({"click": "Revue du code", "within": "chart"},))[0]
        self.assertTrue(review["step"]["found"], "no job « Revue du code » to open on the frise")
        table = usage_table(address, review["href"])
        # Each message once: 2 + 5 given beside 2 715 + 1 200 written to and
        # 28 583 + 31 298 read from the cache, 2 697 + 803 printed of which
        # 53 + 20 of reasoning. Claude's categories do not overlap: its
        # total is theirs added, 67 303 -- not 134 606, each message twice.
        for label, value in (("Entrée", 7), ("Cache écrit", 3915), ("Cache lu", 59881), ("Sortie", 3500),
                             ("Raisonnement", 73), ("Total", 67303)):
            self.assert_row(table, label, value)

    def test_a_usage_missing_for_a_session_is_said_not_collected_never_zero_and_a_running_one_partial(self):
        dataset = dataset_of(self.tree, "job-usage-unavailable")
        # « Essayer la tâche » (from +6 min 10 s, still worked): its first
        # session stopped at +6 min 40 s with no usage recorded; the second
        # still runs, its usage counted once so far.
        running = (codex_start("demo-cockpit-noe-2", "13:06:40.000", SYSTEM, "# Tâche\nEssayer la tâche.")
                   + codex_usage([("13:07:00.000", tokens(5000, 4000, 300, 80))]))
        job_of(dataset, "cockpit", "evaluation")["sessions"] = [
            {"name": "demo-cockpit-noe-1", "provider": "codex", "start": 370, "end": 400,
             "transcript": codex_start("demo-cockpit-noe-1", "13:06:10.000", SYSTEM, "# Tâche\nEssayer la tâche.")},
            {"name": "demo-cockpit-noe-2", "provider": "codex", "start": 400, "transcript": running},
        ]
        address = launch_declared(self.tree, "job-usage-partial", dataset)
        reading, = observe(address, "/runs/job")[0]
        table = usage_table(address, reading["href"])
        self.assert_row(table, "Total", 5300)
        said = self.usage(reading)
        self.assertIn("partiel", said, f"a usage missing a session and still growing is not said partial: « {said} »")
        self.assertNotIn("complet", said, f"a partial usage is said complete: « {said} »")
        missing = said[said.find("demo-cockpit-noe-1"):said.find("demo-cockpit-noe-2")]
        self.assertIn("demo-cockpit-noe-1", missing, f"the usage does not name the session it misses: « {said} »")
        self.assertIn("non collecté", missing, f"the session with no usage is not said not collected: « {missing} »")
        self.assertNotRegex(missing, number(0), f"the session with no usage is counted zero: « {missing} »")
        self.assertIn("en cours", said[said.find("demo-cockpit-noe-2"):],
                      f"the session still running is not said running: « {said} »")
        # job-usage-unavailable as it is: nothing recorded, nothing counted.
        self.tree.stop_all()
        address = self.tree.launch("job-usage-unavailable")
        reading, = observe(address, "/runs/job")[0]
        said = self.usage(reading)
        self.assertEqual({}, usage_table(address, reading["href"]), "a job with no usage recorded draws a table of counts")
        self.assertIn("non collecté", said.lower(), f"the usage is not said not collected: « {said} »")
        self.assertNotRegex(said, r"\d", f"a job with no usage recorded shows a count: « {said} »")


if __name__ == "__main__":
    unittest.main()
