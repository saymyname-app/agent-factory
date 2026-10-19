#!/usr/bin/env python3
"""bin/role-adoption-trial reads what a Codex session loaded (af-npz9v1.12).

Benjamin, 2026-10-17 (« Essayer un autre fournisseur »): the code reviewer
runs on Codex so that its review is independent of the author's model. The
trial only understood Claude Code's transcript and refused every other base
(« no observer for provider base »). These cases give it a synthetic Codex
rollout (~/.codex/sessions/.../rollout-*.jsonl, the format of codex-cli
0.155) and check what it reads: the session found by its work directory, the
final answer, the skill list, a skill opened through the shell, and a write
refused by the read-only sandbox."""

import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("role_adoption_trial", str(ROOT / "bin" / "role-adoption-trial"))
spec = importlib.util.spec_from_loader(loader.name, loader)
trial = importlib.util.module_from_spec(spec)
loader.exec_module(trial)


def item(kind, payload):
    return {"timestamp": "2026-10-17T10:00:00.000Z", "type": kind, "payload": payload}


def message(role, text):
    kind = "output_text" if role == "assistant" else "input_text"
    return item("response_item", {"type": "message", "role": role, "content": [{"type": kind, "text": text}]})


def call(call_id, code, output):
    return [item("response_item", {"type": "custom_tool_call", "call_id": call_id, "name": "exec", "input": code}),
            item("response_item", {"type": "custom_tool_call_output", "call_id": call_id,
                                   "output": [{"type": "input_text", "text": "Script completed\nOutput:\n"},
                                              {"type": "input_text", "text": output}]})]


class CodexTranscriptTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.home = self.tmp / "codex"
        self.work = self.tmp / "city" / ".gc" / "agents" / "delivery-reviewer"
        self.skills = self.work / ".agents" / "skills"
        (self.skills / "code-review").mkdir(parents=True)
        (self.skills / "code-review" / "SKILL.md").write_text("---\nname: code-review\n---\nvendored\n")
        self.since = time.time() - 1

    def rollout(self, cwd, entries, name="rollout-2026-10-17T12-00-00-x.jsonl"):
        folder = self.home / "sessions" / "2026" / "10" / "17"
        folder.mkdir(parents=True, exist_ok=True)
        meta = item("session_meta", {"id": name, "cwd": str(cwd)})
        (folder / name).write_text("".join(json.dumps(e) + "\n" for e in [meta, *entries]))

    def listing(self):
        return message("developer", "<skills_instructions>\n## Skills\n### Skill roots\n"
                       "- `r0` = `/home/x/.codex/skills/.system`\n"
                       f"- `r1` = `{self.skills}`\n"
                       "### Available skills\n"
                       "- imagegen: Generate images. (file: r0/imagegen/SKILL.md)\n"
                       "- code-review: Review code: with care. (file: r1/code-review/SKILL.md)\n"
                       "- github:gh-fix-ci: Fix CI. (file: r0/gh-fix-ci/SKILL.md)\n"
                       "</skills_instructions>")

    def transcript(self):
        return trial.CodexTranscript(self.home, self.work, self.since)

    def test_the_answer_of_the_session_of_this_work_directory_is_read(self):
        self.rollout(self.work, [message("user", "say TRIAL-DONE-1"), message("assistant", "TRIAL-DONE-1")])
        self.rollout(self.tmp / "elsewhere", [message("assistant", "TRIAL-DONE-2")], name="rollout-other.jsonl")
        self.assertTrue(self.transcript().said("TRIAL-DONE-1"))
        self.assertFalse(self.transcript().said("TRIAL-DONE-2"), "a session of another directory is not this role's")

    def test_the_user_prompt_is_not_an_answer(self):
        self.rollout(self.work, [message("user", "reply TRIAL-DONE-1")])
        self.assertFalse(self.transcript().said("TRIAL-DONE-1"))

    def test_the_skill_list_is_read_with_plugin_names(self):
        self.rollout(self.work, [self.listing()])
        self.assertEqual(self.transcript().skill_listing(), ["imagegen", "code-review", "github:gh-fix-ci"])

    def test_a_session_restarted_in_the_same_directory_does_not_list_its_skills_twice(self):
        # gc drains a Codex session on its first start (config drift) and wakes it again.
        self.rollout(self.work, [self.listing()], name="rollout-2026-10-17T12-00-00-a.jsonl")
        self.rollout(self.work, [self.listing()], name="rollout-2026-10-17T12-00-30-b.jsonl")
        self.assertEqual(self.transcript().skill_listing().count("code-review"), 1)

    def test_a_skill_opened_through_the_shell_is_a_launch_and_its_file_the_listed_one(self):
        path = self.skills / "code-review" / "SKILL.md"
        self.rollout(self.work, [self.listing(),
                                 *call("c1", f'await tools.exec_command({{cmd:"cat {path}"}})', path.read_text())])
        transcript = self.transcript()
        attempts = transcript.review_attempts(["code-review", "security-review", "review"])
        self.assertEqual([(a["skill"], a["launched"]) for a in attempts],
                         [("code-review", True), ("security-review", False), ("review", False)])
        self.assertIn("not in the session's skill list", attempts[1]["result"])
        self.assertEqual(transcript.skill_base_dirs(), [str(self.skills / "code-review")])

    def test_a_listed_skill_not_opened_is_not_a_launch(self):
        self.rollout(self.work, [self.listing()])
        attempts = self.transcript().review_attempts(["code-review"])
        self.assertEqual(attempts[0]["launched"], False)
        self.assertEqual(self.transcript().skill_base_dirs(), [])

    def test_a_write_refused_by_the_sandbox_is_seen_as_a_shell_call(self):
        self.rollout(self.work, [*call("c2", 'await tools.exec_command({cmd:"echo trial > /repo/T.txt"})',
                                       "/bin/bash: line 1: /repo/T.txt: Read-only file system\n"),
                                 *call("c3", 'await tools.apply_patch("*** Begin Patch\\n*** Add File: /repo/W.txt\\n+trial\\n*** End Patch")',
                                       "Script error:\nExit code: 1\nOutput:\nFailed to write file /repo/W.txt\n")])
        calls = self.transcript().tool_calls()
        self.assertEqual([c["tool"] for c in calls], ["Bash", "Write"])
        self.assertIn("/repo/T.txt", calls[0]["input"]["command"])
        self.assertIn("Read-only file system", calls[0]["result"])
        self.assertIn("/repo/W.txt", calls[1]["input"]["file_path"])
        # codex-cli 0.155 says only « Failed to write file » when the sandbox refuses apply_patch.
        self.assertTrue(all(trial.write_refused(c) for c in calls))

    def test_a_rollout_older_than_the_trial_is_ignored(self):
        self.rollout(self.work, [message("assistant", "TRIAL-DONE-OLD")])
        self.since = time.time() + 60
        self.assertFalse(self.transcript().said("TRIAL-DONE-OLD"))


@unittest.skipUnless(shutil.which("bwrap"), "bwrap is not installed")
class SandboxTest(unittest.TestCase):
    def test_the_user_skills_of_codex_are_hidden_from_a_read_only_role(self):
        # Codex reads ~/.agents/skills on top of the role's own copies: seen
        # on the first real trial, it listed tdd, codebase-design and
        # ponytail-review to the reviewer.
        home = Path(tempfile.mkdtemp())
        (home / ".agents" / "skills" / "tdd").mkdir(parents=True)
        (home / ".agents" / "skills" / "tdd" / "SKILL.md").write_text("---\nname: tdd\n---\n")
        (home / ".agents" / "AGENTS.md").write_text("kept\n")
        proc = subprocess.run([str(ROOT / "bin" / "delivery-role-sandbox"), "-A", str(home / ".agents" / "skills"), str(home / ".agents")],
                              env={"PATH": os.environ["PATH"], "HOME": str(home), "DELIVERY_ROLE_SANDBOX_EXEC": "/bin/ls"},
                              cwd=home, capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("tdd", proc.stdout)
        self.assertIn("AGENTS.md", proc.stdout)


class DistributionTest(unittest.TestCase):
    def test_the_reviewer_copy_of_interface_review_is_invocable_by_codex_too(self):
        # Codex honours agents/openai.yaml (allow_implicit_invocation), not
        # disable-model-invocation: the first real trial did not list
        # interface-review. The reviewer's adaptation covers both flags.
        copy = ROOT / "agents" / "delivery-reviewer" / "skills" / "interface-review" / "agents" / "openai.yaml"
        self.assertIn("allow_implicit_invocation: true", copy.read_text())
        self.assertEqual(trial.distribution_problems(trial.load_roles()), [])


class ObserverTest(unittest.TestCase):
    def test_each_base_has_its_observer_and_an_unknown_one_none(self):
        self.assertIs(trial.observer_class({"base": "builtin:claude"}), trial.ClaudeTranscript)
        self.assertIs(trial.observer_class({"base": "builtin:codex"}), trial.CodexTranscript)
        self.assertIsNone(trial.observer_class({"base": "builtin:gemini"}))


if __name__ == "__main__":
    unittest.main()
