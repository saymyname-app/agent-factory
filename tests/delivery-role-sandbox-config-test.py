#!/usr/bin/env python3
"""A read-only role cannot write what an unconfined session executes or reads
as instructions (af-q55qqx, F7 of the 16/11/2026 analysis; class C of
docs/DEFECT_CLASSES.md).

The real bin/delivery-role-sandbox runs /bin/sh in place of the provider, in
a HOME and a city made for the test, and tries to write each surface. The
provider's own state, the tracker and the session's work directory stay
writable: a session that cannot write them does not run.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SANDBOX = ROOT / "bin" / "delivery-role-sandbox"

PROBE = r"""
for p in "$@"; do
  if (mkdir -p "$(dirname "$p")" && printf 'x' >> "$p") 2>/dev/null; then echo "W $p"; else echo "R $p"; fi
done
"""


class SandboxConfigTest(unittest.TestCase):
    def setUp(self):
        if not shutil.which("bwrap"):
            self.skipTest("Bubblewrap required")
        # Not under /tmp: the sandbox mounts its own /tmp over it.
        cache = Path.home() / ".cache"
        cache.mkdir(parents=True, exist_ok=True)
        self.tmp = Path(tempfile.mkdtemp(dir=cache, prefix="role-sandbox-config."))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = self.tmp / "home"
        self.claude = self.home / ".claude"
        self.codex = self.home / ".codex"
        self.city = self.home / "city"
        self.work = self.city / ".gc" / "agents" / "delivery-reviewer"
        for d in (self.claude / "projects" / "-home-benja-agent-factory" / "memory",
                  self.claude / "plugins", self.codex / "sessions",
                  self.city / ".gc" / "scripts", self.city / ".gc" / "worktrees" / "w1",
                  self.city / ".gc" / "agents" / "factory-worker" / ".claude",
                  self.city / ".beads" / "formulas", self.work):
            d.mkdir(parents=True)
        self.claude_json = self.claude / ".claude.json"
        self.claude_json.write_text('{"mcpServers": {}}')
        for f in (self.claude / "settings.json", self.claude / ".credentials.json",
                  self.codex / "config.toml", self.city / ".gc" / "settings.json",
                  self.city / ".gc" / "events.jsonl", self.city / ".beads" / "config.yaml"):
            f.write_text("")
        self.env = {"PATH": os.environ["PATH"], "HOME": str(self.home),
                    "CLAUDE_CONFIG_DIR": str(self.claude), "GC_CITY": str(self.city),
                    "EVALUATION_CAPACITY_STATE_DIR": str(self.home / ".local/state/capacity"),
                    "DELIVERY_ROLE_SANDBOX_EXEC": "/bin/sh"}

    def run_probe(self, paths, *, script=PROBE):
        proc = subprocess.run([str(SANDBOX), "-c", script, "probe", *map(str, paths)],
                              cwd=self.work, env=self.env, capture_output=True, text=True,
                              timeout=30)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return {line[2:]: line[0] for line in proc.stdout.splitlines()}

    def test_unconfined_surfaces_are_refused(self):
        refused = [
            self.claude / "settings.json", self.claude / "settings.local.json",
            self.claude / "CLAUDE.md", self.claude / "hooks" / "evil.sh",
            self.claude / "agents" / "evil.md", self.claude / "commands" / "evil.md",
            self.claude / "skills" / "evil" / "SKILL.md", self.claude / "plugins" / "evil",
            self.claude / "projects" / "-home-benja-agent-factory" / "memory" / "MEMORY.md",
            self.claude / "projects" / "-home-benja-other" / "x.jsonl",
            self.codex / "config.toml", self.codex / "hooks.json", self.codex / "AGENTS.md",
            self.codex / "AGENTS.override.md", self.codex / "rules" / "evil.rules",
            self.city / ".gc" / "settings.json", self.city / ".gc" / "scripts" / "evil.sh",
            self.city / ".gc" / "agents" / "factory-worker" / ".claude" / "settings.json",
            self.city / ".gc" / "worktrees" / "w1" / "code.py",
            self.city / ".beads" / "formulas" / "evil.toml", self.city / ".beads" / "config.yaml",
        ]
        result = self.run_probe(refused)
        self.assertEqual({str(p): "R" for p in refused}, result)

    def test_session_state_stays_writable(self):
        own = self.claude / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(self.work))
        writable = [self.work / "draft.md", own / "session.jsonl",
                    self.claude / "history.jsonl", self.claude / ".credentials.json",
                    self.codex / "sessions" / "s.jsonl", self.city / ".gc" / "events.jsonl",
                    self.city / ".beads" / "interactions.jsonl"]
        result = self.run_probe(writable)
        self.assertEqual({str(p): "W" for p in writable}, result)

    def test_claude_json_is_a_private_copy(self):
        script = 'printf "{\\"mcpServers\\": {\\"evil\\": {}}}" > "$1" && cat "$1"'
        proc = subprocess.run([str(SANDBOX), "-c", script, "probe", str(self.claude_json)],
                              cwd=self.work, env=self.env, capture_output=True, text=True,
                              timeout=30)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("evil", json.loads(proc.stdout)["mcpServers"])
        self.assertEqual({}, json.loads(self.claude_json.read_text())["mcpServers"])

    def test_placeholders_say_nothing_configured(self):
        self.run_probe([])
        self.assertEqual({}, json.loads((self.claude / "settings.local.json").read_text()))
        self.assertEqual({"hooks": {}}, json.loads((self.codex / "hooks.json").read_text()))
        self.assertEqual("", (self.codex / "AGENTS.override.md").read_text())

    def test_a_codex_agents_md_without_override_refuses_to_start(self):
        (self.codex / "AGENTS.md").write_text("real instructions")
        proc = subprocess.run([str(SANDBOX), "-c", "true"], cwd=self.work, env=self.env,
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(2, proc.returncode)
        self.assertIn("AGENTS.override.md", proc.stderr)
        self.assertFalse((self.codex / "AGENTS.override.md").exists())


if __name__ == "__main__":
    unittest.main()
