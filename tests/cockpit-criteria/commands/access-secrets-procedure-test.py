#!/usr/bin/env python3
"""Criterion test 2 of I « Accès HTTPS sur la VM, veille de silence et
procédure de réglages opérateur » (af-cp4fzd; Spec af-fgcw0d, user stories
61 and 98, Implementation Decision « Accès hôte » : « Adapter URL, chemins
privés et lecture expiration au nœud VM […] Aucune valeur de secret dans les
assets, journaux ou prompts. », Testing Decisions 1, 4 and 8).

The case launches the real cockpit with the launcher of the profile,
bin/project-launch, on health-content: the launch has no Pushover secrets
file, and its heartbeat has a ping address -- a secret -- written for this
launch (`heartbeat`), whose value the case knows.

- The section « Santé de l'usine » of GET /usine says the Pushover secret
  is absent.
- The section « Accès » links to the procedure of the settings that ask
  Benjamin's hand on the VM: it opens, says Pushover, the heartbeat and the
  access through Tailscale, the VM, and no Windows path.
- The value of the secret is in no page, no reading, no technical log of
  the cockpit, not in the procedure and not in the log of the launch.

False if the value of a secret shows in a page, a log or a prompt.
"""

from __future__ import annotations

import re
import sys
import time
import unittest
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from acces_vm import declare, launch_logs, page, section, text_of  # noqa: E402
from home_destination import LaunchTree  # noqa: E402
from pour_moi import read_json, wait_for  # noqa: E402

# The secret of the launch: the ping address of the heartbeat, a value
# nothing else says.
SECRET = "c0ffee42-secret-de-recette-9d1b"
# Nobody answers there: the ping fails, the value stays a secret.
PING_URL = f"http://127.0.0.1:9/ping/{SECRET}"
ABSENT = re.compile(r"(?i)(?:pushover|notifications)[^.]*\bsecrets?\b[^.]*\babsents?\b")
# A path of the Windows host, as the old procedure wrote them.
WINDOWS_PATH = re.compile(r"(?i)\b[a-z]:\\|/mnt/[a-z]/|\\\\wsl|%[a-z]+%|\bAppData\b|\bC:/")
# What the cockpit serves: its pages, its readings, its technical logs.
SERVED = ("/", "/usine", "/journal", "/journal?vue=logs", "/journal?vue=sources", "/runs", "/projets",
          "/api/status", "/api/health", "/api/requests", "/api/notifications", "/api/journal")
# Long enough for the heartbeat to be tried on fresh readings, and its
# failure written where the cockpit writes.
TRIED_SECONDS = 8


class AccessSecretsProcedure(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    # --- Criterion 2 ------------------------------------------------------------

    def test_a_missing_secret_shows_in_health_without_any_value_and_the_vm_procedure_opens_from_access(self):
        # The criterion names the health, the procedure reached from « Accès »
        # and no secret value anywhere: one criterion observed whole.
        commit = declare(self.tree, "acces-secrets", "health-content",
                         heartbeat={"ping_url": PING_URL, "interval_seconds": 2})
        address = self.tree.launch("acces-secrets", commit)
        fresh = wait_for(lambda: read_json(address, "/api/status"),
                         lambda status: all(status.get(n, {}).get("freshness") == "fresh" for n in ("gc", "beads")),
                         20)
        self.assertEqual(("fresh", "fresh"), (fresh["gc"]["freshness"], fresh["beads"]["freshness"]),
                         "the main sources never read fresh")
        time.sleep(TRIED_SECONDS)
        status, usine = page(address, "/usine")
        self.assertEqual(200, status, "GET /usine is not served")
        self.assert_the_missing_secret_shows_in_health(usine)
        procedure = self.assert_the_vm_procedure_opens_from_access(address, usine)
        self.assert_no_secret_value_anywhere(address, procedure)

    def assert_the_missing_secret_shows_in_health(self, usine: str) -> None:
        health = section(self, usine, "Santé de l'usine")["text"]
        self.assertRegex(health, ABSENT, f"the health does not say the Pushover secret absent: {health}")
        self.assertEqual([], WINDOWS_PATH.findall(health), f"the health names a Windows path: {health}")

    def assert_the_vm_procedure_opens_from_access(self, address: str, usine: str) -> str:
        """The procedure the section « Accès » links to, as served: its text."""
        acces = section(self, usine, "Accès")
        self.assertEqual([], WINDOWS_PATH.findall(acces["text"]), f"« Accès » names a Windows path: {acces['text']}")
        links = [link for link in acces["links"] if re.search(r"(?i)proc[ée]dure", link["text"])]
        self.assertEqual(1, len(links), f"« Accès » does not link to one procedure: {acces['links']}")
        target = urllib.parse.urlsplit(urllib.parse.urljoin(address + "/usine", links[0]["href"]))
        self.assertEqual(urllib.parse.urlsplit(address).netloc, target.netloc,
                         f"the procedure is not served by the cockpit: {links[0]['href']}")
        status, source = page(address, target.path + (f"?{target.query}" if target.query else ""))
        self.assertEqual(200, status, f"the procedure {links[0]['href']} does not open")
        text = text_of(source)
        for said in ("Pushover", "Tailscale", "VM"):
            self.assertIn(said, text, f"the procedure does not say {said}")
        self.assertRegex(text, r"(?i)heartbeat|healthchecks|usine muette", "the procedure does not say the heartbeat")
        self.assertEqual([], WINDOWS_PATH.findall(text), "the procedure names a Windows path")
        return text

    def assert_no_secret_value_anywhere(self, address: str, procedure: str) -> None:
        shown = {path: body for path in SERVED for status, body in [page(address, path)]}
        self.assertEqual([], [path for path, body in shown.items() if SECRET in body],
                         "the value of a secret shows in what the cockpit serves")
        self.assertNotIn(SECRET, procedure, "the value of a secret shows in the procedure")
        logs = launch_logs(self.tree)
        self.assertEqual(1, len(logs), "the log of the launch is not found")
        self.assertNotIn(SECRET, logs[0], "the value of a secret shows in the log of the launch")


if __name__ == "__main__":
    unittest.main()
