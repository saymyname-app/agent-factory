#!/usr/bin/env python3
"""Criterion test 1 of C2a « Runs — sessions, configuration et prompts
collectés » (af-k2rbw1; Spec af-fgcw0d, user stories 139, 145 and 175,
Testing Decisions 1, 5, 7 and 8): the prompts sent to a session, states
job-system-prompt, job-user-prompt-rendered and job-user-prompt-raw.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset that carries the name of its state, and
reads GET /runs/job -- the job « Réaliser » of « Recherche dans les notes »,
or another job of that run clicked in its frise -- as a headless Chromium
renders it, and over HTTP the page the browser was on.

The section « Prompts envoyés » lists the system prompt and the user prompt
the session was sent, each with its version, rendered or raw: the raw text
is the text sent, exactly. A prompt no trace recorded is said not
collected, never rebuilt from the job.

False if a prompt shown is not the text sent, its version is not said, the
raw text is not shown raw, or a prompt missing is drawn from the
description of the job. A session chosen in the history is marked by more
than a colour.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from runs_destination import LaunchTree, observe, observe_themes, section, unreadable  # noqa: E402
from runs_trace import head_says, history_links, line, prompts, raw_texts  # noqa: E402


class RunsTracePrompts(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def one(self, reading: dict, kind: str) -> dict:
        listed = prompts(reading)
        self.assertEqual(1, len(listed.get(kind, [])), f"not one « {kind} » in « Prompts envoyés »: {listed}")
        return listed[kind][0]

    def assert_sent(self, address: str, reading: dict, text: str, version: str) -> None:
        """The page the browser is on holds `text`, exactly as it was sent,
        and says its `version`."""
        self.assertIn(text, raw_texts(address, reading["href"]),
                      f"the text sent is not on the page as it was sent: {text[:40]!r}")
        self.assertIn(version, section(reading, "Prompts envoyés")["content"], f"the version of the prompt is not said: {version}")

    def test_job_system_prompt_shows_the_system_prompt_sent_rendered_then_raw(self):
        # What demo-search-alex-2 was sent as its system prompt, and its
        # version: the first twelve digits of the SHA-256 of that text.
        sent = ("# Auteur\n\n# Mission\nRéaliser sur le périmètre approuvé.\n\n# Règles\n"
                "- Utiliser les points d’entrée publics et les sources disponibles.\n"
                "- Conserver les mots du propriétaire ; ne pas inventer une preuve.\n"
                "- Signaler une donnée absente ou une limite.\n"
                "- Rendre un résultat lié à la version observée.")
        address = self.tree.launch("job-system-prompt")
        rendered, raw = observe(address, "/runs/job", steps=({"click": "Brut", "within": "inspector-sections"},))[0]
        self.assertIn("Réaliser", head_says(rendered), "the detail is not that of the job « Réaliser »")
        listed = section(rendered, "Prompts envoyés")
        self.assertIsNotNone(listed, "the detail has no section « Prompts envoyés »")
        self.assertTrue(listed["open"], "job-system-prompt does not open the prompts sent")
        self.assertNotIn("non collecté", listed["content"], "the prompts sent are said not collected")
        self.assertIn("demo-search-alex-2", listed["content"], "the prompts do not say the session they were sent to")
        system = self.one(rendered, "Prompt système")
        self.assertTrue(system["open"], "job-system-prompt does not open the system prompt")
        for phrase in ("Auteur", "Réaliser sur le périmètre approuvé.",
                       "Utiliser les points d’entrée publics et les sources disponibles."):
            self.assertIn(phrase, system["text"], f"the system prompt rendered does not say « {phrase} »")
        self.assertNotIn("# Mission", system["text"], "the system prompt is drawn raw where it is rendered")
        self.assertEqual("", system["raw"], "the raw text is drawn beside the rendered one")
        self.assert_sent(address, rendered, sent, "sha256:b71a0f18acad")
        self.assertTrue(raw["step"]["found"], "no control « Brut » for the system prompt")
        self.assertEqual(line(sent), self.one(raw, "Prompt système")["raw"], "the raw system prompt is not the text sent")

    def test_job_user_prompt_rendered_shows_the_user_prompt_sent_rendered(self):
        # What demo-search-alex-2 was sent as its user prompt, and its version.
        sent = ("# Tâche\nImplémenter le périmètre approuvé du cockpit en conservant la boîte de réception. "
                "Utiliser les sources D01 existantes. Ne pas changer les portes de jugement. "
                "Fournir les preuves des critères au commit de sortie.\n\n"
                "# Contexte transmis\nWorkflow : Recherche dans les notes\nJob : Réaliser\nVersion : exemple synthétique\n\n"
                "# Résultat attendu\nUne observation et ses pièces, ou une limite explicite.")
        address = self.tree.launch("job-user-prompt-rendered")
        reading, = observe(address, "/runs/job")[0]
        user = self.one(reading, "Prompt utilisateur")
        self.assertTrue(user["open"], "job-user-prompt-rendered does not open the user prompt")
        for phrase in ("Tâche", "Contexte transmis", "Workflow : Recherche dans les notes", "Résultat attendu"):
            self.assertIn(phrase, user["text"], f"the user prompt rendered does not say « {phrase} »")
        self.assertNotIn("# Tâche", user["text"], "the user prompt is drawn raw where it is rendered")
        self.assertEqual("", user["raw"], "the raw text is drawn beside the rendered one")
        self.assert_sent(address, reading, sent, "sha256:de74c319c517")

    def test_job_user_prompt_raw_shows_the_user_prompt_sent_raw(self):
        # What demo-search-alex-2 was sent as its user prompt, and its version.
        sent = ("# Tâche\nImplémenter le périmètre approuvé du cockpit en conservant la boîte de réception. "
                "Utiliser les sources D01 existantes. Ne pas changer les portes de jugement. "
                "Fournir les preuves des critères au commit de sortie.\n\n"
                "# Contexte transmis\nWorkflow : Recherche dans les notes\nJob : Réaliser\nVersion : exemple synthétique\n\n"
                "# Résultat attendu\nUne observation et ses pièces, ou une limite explicite.")
        address = self.tree.launch("job-user-prompt-raw")
        reading, = observe(address, "/runs/job")[0]
        user = self.one(reading, "Prompt utilisateur")
        self.assertTrue(user["open"], "job-user-prompt-raw does not open the user prompt")
        self.assertEqual(line(sent), user["raw"], "the raw user prompt drawn is not the text sent")
        self.assert_sent(address, reading, sent, "sha256:de74c319c517")
        # What the first session was sent, which its trace replays at the
        # head of that of the last.
        self.assertNotIn("Version : exemple synthétique, première session", "\n".join(raw_texts(address, reading["href"])),
                         "the last session shows the prompt of an earlier one")

    def test_a_prompt_no_trace_recorded_is_said_not_collected_and_not_rebuilt(self):
        system = "# Auteur\n\n# Mission\nRéaliser sur le périmètre approuvé."
        # The description of the job « Revue du code », which no prompt sent
        # to its session is.
        description = "Relire le diff de la tâche à sa pointe courante."
        address = self.tree.launch("job-system-prompt")
        built, reading = observe(address, "/runs/job", steps=({"click": "Revue du code", "within": "chart"},))[0]
        # The prompts sent to the session of « Réaliser » were recorded...
        self.assertIn(system, "\n".join(raw_texts(address, built["href"])), "the system prompt sent is not shown")
        # ...none sent to the session of « Revue du code », though it ran.
        self.assertTrue(reading["step"]["found"], "no job « Revue du code » to click in the frise")
        self.assertIn("Revue du code", head_says(reading), "the detail is not that of the job « Revue du code »")
        self.assertIn("demo-search-lea-1", section(reading, "Sessions du job")["content"],
                      "the session that worked « Revue du code » is not said")
        listed = section(reading, "Prompts envoyés")
        self.assertIsNotNone(listed, "the detail has no section « Prompts envoyés »")
        self.assertIn("non collecté", listed["content"], "a prompt no trace recorded is not said not collected")
        self.assertNotIn(description, listed["content"], "a prompt missing is rebuilt from the job")
        self.assertEqual({}, prompts(reading), "a prompt is drawn that no trace recorded")
        self.assertNotIn(system, "\n".join(raw_texts(address, reading["href"])),
                         "the prompt of another session is shown for this one")

    def test_a_session_and_the_raw_text_are_chosen_from_the_keyboard_readable_on_a_desktop_and_a_phone(self):
        system = ("# Auteur\n\n# Mission\nRéaliser sur le périmètre approuvé.\n\n# Règles\n"
                  "- Utiliser les points d’entrée publics et les sources disponibles.\n"
                  "- Conserver les mots du propriétaire ; ne pas inventer une preuve.\n"
                  "- Signaler une donnée absente ou une limite.\n"
                  "- Rendre un résultat lié à la version observée.")
        by_theme = observe_themes(self.tree.launch("job-system-prompt"), "/runs/job", steps=(
            {"click": "demo-search-alex-1", "within": "session-history", "keys": True},
            {"click": "Brut", "within": "inspector-sections", "keys": True},
        ))
        for frames in by_theme.values():
            for _, chosen, raw in frames:
                self.assertTrue(chosen["step"]["found"] and raw["step"]["found"],
                                f"no control to choose a session or the raw text at {chosen['width']} px")
                self.assertIn("demo-search-alex-1", section(chosen, "Configuration")["content"],
                              f"the keyboard does not choose the session at {chosen['width']} px")
                # The session shown says so in words, not by the colour of
                # its border alone.
                links = history_links(chosen)
                self.assertIn("affichée", links.get("demo-search-alex-1", "").lower(),
                              f"the session chosen is not marked but by a colour at {chosen['width']} px: {links}")
                self.assertNotIn("affichée", links.get("demo-search-alex-2", "").lower(),
                                 f"a session not chosen is marked shown at {chosen['width']} px: {links}")
                self.assertEqual(line(system), self.one(raw, "Prompt système")["raw"],
                                 f"the keyboard does not show the raw text at {raw['width']} px")
        self.assertEqual({}, unreadable(by_theme, ("chart", "detail")), "the prompts of a session are not readable")


if __name__ == "__main__":
    unittest.main()
