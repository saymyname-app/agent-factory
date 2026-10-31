"""The procedure of the settings that ask the operator's hand on the VM, and
the local settings it has the operator write (I, af-cp4fzd; Spec af-fgcw0d,
user stories 61 and 98: « une procédure courte adaptée à la VM pour les
réglages Pushover, heartbeat et accès qui nécessitent mon action »).

:func:`cockpit.ui.access.procedure.render_procedure` is a pure function: it
is called here with what a host says of itself, and its text read. The
local settings file is read by :class:`cockpit.core.config.Config`, given a
plain environment. Neither reaches a secret of the host, the network or a
process.
"""
import html
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from cockpit.core.config import Config  # noqa: E402
from cockpit.ui.access.procedure import render_procedure  # noqa: E402

SETTINGS = {
    "local_config": "/home/factory/agent-factory/.gc/runtime/cockpit-local.json",
    "pushover_file": "", "pushover_ready": False,
    "heartbeat_file": "", "heartbeat_ready": False,
    "public_url": "", "port": 8765, "supervisor_port": 8372,
}


def text(settings):
    source = render_procedure({**SETTINGS, **settings})
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", source)).split())


def step(settings, title):
    """The text of the step whose title starts with `title`."""
    said = text(settings)
    start = said.index(title)
    following = [said.index(other, start + 1) for other in ("2. ", "3. ", "4. ") if other in said[start + 1:]]
    return said[start:min(following)] if following else said[start:]


class ProcedureStatesTest(unittest.TestCase):
    """A secret is « en place » only when the cockpit can read it (F1.11)."""

    def test_a_secret_read_is_in_place(self):
        said = step({"pushover_file": "/home/factory/.config/agent-factory/pushover.json",
                     "pushover_ready": True}, "1. Notifications")
        self.assertIn("En place sur cette VM", said)

    def test_a_path_set_whose_file_is_absent_or_invalid_is_not_in_place(self):
        said = step({"heartbeat_file": "/home/factory/.config/agent-factory/heartbeat-url",
                     "heartbeat_ready": False}, "2. Signal de vie")
        self.assertNotIn("En place", said)
        self.assertIn("/home/factory/.config/agent-factory/heartbeat-url", said)
        self.assertRegex(said, r"absent ou invalide")

    def test_a_secret_unset_is_not_in_place(self):
        said = step({}, "1. Notifications")
        self.assertIn("Pas encore en place", said)


class ProcedureServeTest(unittest.TestCase):
    """The command of Tailscale Serve is given whole: no port left to guess
    (F1.10)."""

    def test_the_serve_command_names_the_ports_of_this_host(self):
        said = step({}, "3. Accès")
        self.assertIn("serve --target-port 8765 --gc-port 8372", said)
        self.assertNotIn("<port", said)


class LocalSettingsPathsTest(unittest.TestCase):
    """The paths the procedure has the operator write in the local settings
    file, `~/…` included, are the files the cockpit reads (F1.6)."""

    def test_a_path_from_the_home_is_read_in_the_home(self):
        with tempfile.TemporaryDirectory() as home:
            local = Path(home, "cockpit-local.json")
            local.write_text(json.dumps({
                "pushover_secrets_file": "~/.config/agent-factory/pushover.json",
                "heartbeat_url_file": "~/.config/agent-factory/heartbeat-url",
            }))
            config = Config({"HOME": home, "COCKPIT_LOCAL_CONFIG": str(local)})
            self.assertEqual(
                (f"{home}/.config/agent-factory/pushover.json", f"{home}/.config/agent-factory/heartbeat-url"),
                (config.pushover_secrets_file, config.heartbeat_url_file))


if __name__ == "__main__":
    unittest.main()
