#!/usr/bin/env python3
"""bin/factory-weekly computes the FACTORY_OBJECTIVE.md table from live
records, deduplicated and attributed, and says what it cannot measure
(af-q55qqx.2). Fakes stand for gh and gc; transcripts and events are files."""
import gzip
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "..", "bin", "factory-weekly")
WEIGHTS = os.path.join(HERE, "..", "config", "token-cost-weights.json")

FAKE_GH = """#!/usr/bin/env python3
import json, sys
repo = sys.argv[sys.argv.index("-R") + 1]
print(json.dumps({
  "o/factory": [{"number": n, "title": "fix", "headRefName": "fix/x", "mergedAt": "2026-11-1%dT10:00:00Z" % n} for n in (0, 1, 2)],
  "o/Product-back": [
    {"number": 7, "title": "slice", "headRefName": "do-work/smb-abc12", "mergedAt": "2026-11-10T12:00:00Z"},
    {"number": 8, "title": "slice (smb-def34)", "headRefName": "feat/y", "mergedAt": "2026-11-12T12:00:00Z"},
    {"number": 9, "title": "late", "headRefName": "do-work/smb-abc12", "mergedAt": "2026-11-16T12:00:00Z"}],
}.get(repo, [])))
"""

FAKE_GC = """#!/usr/bin/env python3
import json, sys
created = {"smb-abc12": "2026-11-10T02:00:00Z", "smb-def34": "2026-11-08T08:00:00Z"}
bead = sys.argv[3]
if bead not in created:
    sys.exit(1)
print(json.dumps([{"id": bead, "created_at": created[bead]}]))
"""


def write(path, text, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.chmod(path, mode)


def assistant(msg_id, at, out, cwd_hint):
    return json.dumps({"type": "assistant", "timestamp": at, "cwd": cwd_hint,
                       "message": {"id": msg_id, "usage": {"input_tokens": 10, "output_tokens": out,
                                                           "cache_read_input_tokens": 100, "cache_creation_input_tokens": 0}}})


class FactoryWeeklyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.root = os.path.join(self.tmp.name, "root")
        write(os.path.join(root, "config/project-descriptors/agent-factory.json"),
              json.dumps({"project_id": "agent-factory", "knowledge_repo": "o/factory", "rigs": ["agent-factory"]}))
        write(os.path.join(root, "config/project-descriptors/product.json"),
              json.dumps({"project_id": "product", "rigs": ["product-backend"],
                          "promotion_branch": {"product-backend": {"from": "dev", "to": "main"}}}))
        write(os.path.join(root, "config/token-cost-weights.json"), Path(WEIGHTS).read_text(encoding="utf-8"))
        rig = os.path.join(root, "rigs/product-backend")
        os.makedirs(rig)
        subprocess.run(["git", "init", "-q", rig], check=True)
        subprocess.run(["git", "-C", rig, "remote", "add", "origin", "https://github.com/o/Product-back.git"], check=True)
        write(os.path.join(root, ".beads/routes.jsonl"), '{"prefix":"af","path":"."}\n{"prefix":"smb","path":"rigs/product-backend"}\n')
        events = [
            {"type": "mail.sent", "ts": "2026-11-11T09:00:00+01:00", "payload": {"message": {"to": "human", "subject": "NEEDS BENJAMIN: af-1"}}},
            {"type": "mail.sent", "ts": "2026-11-11T22:00:00+01:00", "payload": {"message": {"to": "human", "subject": "NEEDS BENJAMIN: af-2"}}},
            {"type": "mail.sent", "ts": "2026-11-12T09:00:00+01:00", "payload": {"message": {"to": "human", "subject": "NEEDS BENJAMIN: af-3"}}},
            {"type": "mail.sent", "ts": "2026-11-12T10:00:00+01:00", "payload": {"message": {"to": "mayor", "subject": "NEEDS BENJAMIN: af-4"}}},
            {"type": "mail.sent", "ts": "2026-11-12T11:00:00+01:00", "payload": {"message": {"to": "human", "subject": "ESCALATION: reaper"}}},
            {"type": "mail.sent", "ts": "2026-11-17T09:00:00+01:00", "payload": {"message": {"to": "human", "subject": "NEEDS BENJAMIN: af-5"}}},
        ]
        for seq, e in enumerate(events, 1):
            e["seq"] = seq
        write(os.path.join(root, ".gc/events.jsonl"), "".join(json.dumps(e) + "\n" for e in events))
        # Rotated during the week: one request of its own, and the first live one again (same seq).
        rotated = [{"type": "mail.sent", "seq": 0, "ts": "2026-11-10T09:00:00+01:00",
                    "payload": {"message": {"to": "human", "subject": "NEEDS BENJAMIN: af-0"}}}, events[0]]
        with gzip.open(os.path.join(root, ".gc/events.jsonl.archive-20261111T000000Z-seq-0-1.gz"), "wt") as fh:
            fh.write("".join(json.dumps(e) + "\n" for e in rotated))
        bins = os.path.join(self.tmp.name, "bin")
        write(os.path.join(bins, "gh"), FAKE_GH, 0o755)
        write(os.path.join(bins, "gc"), FAKE_GC, 0o755)
        claude = self.claude = os.path.join(self.tmp.name, "claude")
        # Product session: one message written twice (resumed transcript) counts once.
        write(os.path.join(claude, "p/a.jsonl"), "\n".join([
            assistant("m1", "2026-11-10T10:00:00Z", 100, "/x/rigs/product-backend/src"),
            assistant("m1", "2026-11-10T10:00:00Z", 100, "/x/rigs/product-backend/src"),
            assistant("m0", "2026-11-01T10:00:00Z", 999999, "/x/rigs/product-backend/src")]) + "\n")
        # A shared agent folder: the product bead it works on names the side.
        write(os.path.join(claude, "g/c.jsonl"), assistant("m3", "2026-11-12T10:00:00Z", 100, "/h/.gc/agents/author smb-zz123 smb-zz123") + "\n")
        write(os.path.join(claude, "f/b.jsonl"), assistant("m2", "2026-11-11T10:00:00Z", 100, "/h/agent-factory/bin/x") + "\n")
        codex = self.codex = os.path.join(self.tmp.name, "codex")
        write(os.path.join(codex, "2026/11/11/r.jsonl"), "\n".join([
            json.dumps({"type": "session_meta", "payload": {"cwd": "/h/agent-factory-maint/w"}}),
            json.dumps({"timestamp": "2026-11-11T10:00:00Z", "type": "event_msg", "payload": {"type": "token_count", "info": {
                "last_token_usage": {"input_tokens": 110, "cached_input_tokens": 100, "output_tokens": 20}}}})]) + "\n")
        self.env = dict(os.environ, FACTORY_ROOT=root, GC_BIN=os.path.join(bins, "gc"), GH_BIN=os.path.join(bins, "gh"),
                        FACTORY_WEEKLY_CLAUDE=claude, FACTORY_WEEKLY_CODEX=codex)

    def tearDown(self):
        self.tmp.cleanup()

    def weekly(self, *args):
        run = subprocess.run([TOOL, *args], env=self.env, capture_output=True, text=True, timeout=60)
        self.assertEqual(0, run.returncode, run.stderr)
        return run.stdout

    def test_the_week_is_measured_from_its_own_records(self):
        out = json.loads(self.weekly("--week", "2026-W46", "--json"))
        self.assertEqual("agent-factory-weekly-measure/v1", out["contract"])
        m = out["measures"]
        # 2 product merges in the week (the 16/11 one is the next week), 5 working days.
        self.assertEqual(0.4, m["slices_per_working_day"]["value"])
        self.assertEqual("ko", m["slices_per_working_day"]["status"])
        # Bead from the branch (10 h), then from the title (100 h).
        self.assertEqual(10, m["lead_time_median_hours"]["value"])
        self.assertEqual(100, m["lead_time_p85_hours"]["value"])
        self.assertEqual("ko", m["lead_time_p85_hours"]["status"])
        self.assertEqual(0.6, m["maintenance_share"]["value"])
        # Two requests to the human on 11/11 (Paris); the mayor's and the reaper's are not requests;
        # the rotated archive adds 10/11 and repeats nothing.
        self.assertEqual(2, m["human_requests_max_per_day"]["value"])
        self.assertEqual(4, m["human_requests_max_per_day"]["detail"]["requests"])
        self.assertEqual(1, m["human_requests_max_per_day"]["detail"]["per_day"]["2026-11-10"])
        # Product: 10 + 5*100 + 0.1*100 = 520 once (the duplicate and the 01/11 message left out),
        # plus 520 named by its product bead id. Factory: Claude 520 + Codex 10 + 0.1*100 + 5*20 = 640.
        self.assertEqual(1040, m["product_cost_share"]["detail"]["product"])
        self.assertEqual(640, m["product_cost_share"]["detail"]["factory"])
        self.assertEqual(round(1040 / 1680, 2), m["product_cost_share"]["value"])

    def test_a_measure_without_a_source_is_named_not_zero(self):
        out = json.loads(self.weekly("--week", "2026-W40", "--json"))
        lead = out["measures"]["lead_time_median_hours"]
        self.assertIsNone(lead["value"])
        self.assertEqual("unmeasured", lead["status"])
        self.assertIn("no product pull request", lead["reason"])
        self.assertEqual("unmeasured", out["measures"]["product_cost_share"]["status"])
        self.assertIn("windows_sessions", out["not_measured"])

    def test_write_keeps_the_table_and_the_contract(self):
        table = self.weekly("--week", "2026-W46", "--write")
        self.assertIn("| Part maintenance des PR | <= 30% | 60% | KO |", table)
        folder = os.path.join(self.root, "var/weekly")
        self.assertEqual(table, Path(folder, "2026-W46.md").read_text(encoding="utf-8"))
        self.assertEqual("2026-W46", json.loads(Path(folder, "2026-W46.json").read_text(encoding="utf-8"))["week"])

    def test_the_mayor_cost_is_observed_per_day(self):
        # af-yzo8fo: the Mayor's weighted cost, read for the Sonnet trial against the Opus weeks.
        # The Mayor is the live-root session whose transcript opens on « # Mayor »; its
        # subagents count with it; another live-root session does not.
        folder = os.path.join(self.claude, re.sub(r"[^A-Za-z0-9]", "-", self.root))
        head = json.dumps({"type": "user", "message": {"content": "# Mayor\n"}})
        write(os.path.join(folder, "s1.jsonl"), head + "\n" + assistant("m10", "2026-11-11T10:00:00Z", 100, "/h") + "\n")
        write(os.path.join(folder, "s1/subagents/a.jsonl"), assistant("m11", "2026-11-12T10:00:00Z", 100, "/h") + "\n")
        write(os.path.join(folder, "s2.jsonl"), assistant("m12", "2026-11-12T10:00:00Z", 100, "/h") + "\n")
        out = json.loads(self.weekly("--week", "2026-W46", "--json"))
        mayor = out["observed"]["mayor_cost"]
        self.assertEqual(1040, mayor["total"])
        self.assertEqual({"2026-11-11": 520, "2026-11-12": 520}, mayor["per_day"])
        self.assertIn("Coût du Mayor", self.weekly("--week", "2026-W46"))

    def test_the_slips_of_the_month_are_shown_by_rule_against_d1(self):
        # af-56yoam.1: the baseline answers for the PRs it holds; the fake's three
        # Factory PRs have no « Règle : » line and are counted unclassified.
        sys.path.insert(0, os.path.join(HERE, "..", "lib"))
        import defect_classes
        baseline = defect_classes.load_baseline()
        november = sum(1 for row in baseline.values() if row["nature"] == "glissement" and row["date"][:7] == "2026-11")
        out = json.loads(self.weekly("--week", "2026-W46", "--json"))
        r = out["observed"]["rule_recurrence"]
        self.assertEqual(("2026-11", november, 3), (r["month"], r["slips"], r["unclassified"]))
        self.assertEqual(november, sum(r["slips_by_rule"].values()))
        # af-56yoam.5: D1 is the slip share (61 % in November, at most 30 %) and zero slip on a closed rule.
        self.assertEqual((0.61, 0.61, 0.3), (r["slip_share"], r["d1"]["reference_share"], r["d1"]["max_slip_share"]))
        self.assertEqual(("ko", []), (r["status"], r["closed_slips"]))
        table = self.weekly("--week", "2026-W46")
        self.assertIn(f"Récidives par règle (11/2026, Paris, af-56yoam) : {november} glissements", table)
        self.assertIn("part des glissements dans les PR de défaut 61 %, au plus 30 % du 01/12 au 20/12", table)
        self.assertIn("Revue le 21/12/2026 (af-56yoam.4)", table)

    def test_the_recurrence_is_unmeasured_not_fatal_when_gh_cannot_list_bodies(self):
        gh = os.path.join(self.tmp.name, "bin", "gh")
        write(gh, FAKE_GH.replace("import json, sys\n", "import json, sys\nif 'body' in ' '.join(sys.argv): sys.exit(1)\n"), 0o755)
        out = json.loads(self.weekly("--week", "2026-W46", "--json"))
        self.assertEqual("unmeasured", out["observed"]["rule_recurrence"]["status"])
        self.assertEqual(0.6, out["measures"]["maintenance_share"]["value"])
        self.assertIn("Récidives par règle (11/2026) : non mesuré", self.weekly("--week", "2026-W46"))

    def test_a_malformed_week_is_refused_before_anything_is_read(self):
        run = subprocess.run([TOOL, "--week", "46"], env=self.env, capture_output=True, text=True)
        self.assertEqual(2, run.returncode)


if __name__ == "__main__":
    unittest.main()
