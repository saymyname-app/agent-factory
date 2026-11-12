#!/usr/bin/env python3
"""The door locks of the isolated cockpit, `bin/cockpit-isolated`
(af-33j358; docs/DEFECT_CLASSES.md, D).

`bin/proposal-door` and `bin/escalation-door` take a lock on the host by
default (`${XDG_RUNTIME_DIR:-/tmp}/agent-factory-<door>.lock`). Launches side
by side, the criterion classes of a convoy, then waited on one another beyond
the 5 s the cockpit gives a door, and R16 of af-strhoy could not be green.
Each launch holds its own locks, under its temporary HOME, and a door that
falls back on the runtime directory finds the launch's; a lock the launcher
gives explicitly is kept.

The recipe is observed as bin/project-launch runs it: a real process, whose
environment the cockpit it becomes carries.
"""

import os
import socket
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "bin" / "cockpit-isolated"
DATASET = ROOT / "config" / "cockpit-datasets" / "home-content.json"
# The lock each door takes on the host when nothing else is given.
HOST_LOCKS = {
    "PROPOSAL_DOOR_LOCK_FILE": "agent-factory-proposal-door.lock",
    "ESCALATION_DOOR_LOCK_FILE": "agent-factory-escalation-door.lock",
}


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class DoorLocks(unittest.TestCase):

    def launch(self, **given):
        """The environment of the cockpit the recipe serves, once it answers;
        `given` are the lock variables of the launcher, none when empty."""
        port = free_port()
        env = {**os.environ, **{name: given.get(name, "") for name in HOST_LOCKS}}
        proc = subprocess.Popen([sys.executable, str(RECIPE), "--port", str(port), "--dataset", str(DATASET)],
                                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(proc.wait, 30)
        self.addCleanup(proc.terminate)
        deadline = time.monotonic() + 30
        while True:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=2) as response:
                    if response.status == 200:
                        break
            except (urllib.error.URLError, ConnectionError, OSError):
                pass
            self.assertLess(time.monotonic(), deadline, "the cockpit never answered")
            time.sleep(0.2)
        pairs = Path(f"/proc/{proc.pid}/environ").read_bytes().decode().split("\0")
        return dict(pair.split("=", 1) for pair in pairs if "=" in pair)

    def test_two_launches_side_by_side_each_hold_their_own_door_locks(self):
        first, second = self.launch(), self.launch()
        for variable, host in HOST_LOCKS.items():
            self.assertNotEqual(first[variable], second[variable], f"two launches share {variable}")
            for env in (first, second):
                self.assertTrue(env[variable].startswith(env["HOME"] + os.sep),
                                f"{variable}={env[variable]} is not under the launch's HOME {env['HOME']}")
                self.assertNotEqual(host, Path(env[variable]).name)
        for env in (first, second):
            self.assertEqual(os.path.join(env["HOME"], "run"), env["XDG_RUNTIME_DIR"])

    def test_a_door_lock_the_launcher_gives_is_kept(self):
        env = self.launch(PROPOSAL_DOOR_LOCK_FILE="/somewhere/given.lock")
        self.assertEqual("/somewhere/given.lock", env["PROPOSAL_DOOR_LOCK_FILE"])
        self.assertTrue(env["ESCALATION_DOOR_LOCK_FILE"].startswith(env["HOME"] + os.sep))


if __name__ == "__main__":
    unittest.main()
