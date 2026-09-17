#!/usr/bin/env python3
"""Automatic provider failover (af-ogyq, ADR-0018).

The acceptance criterion: a reproducible exhaustion scenario shows the factory
falls back to another profile instead of stopping; only total exhaustion parks
work, and that park resumes on its own at quota reset -- never by asking
Benjamin. The detection fixtures are the exact messages seen on this host.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

import provider_failover as pf  # noqa: E402

NOW = datetime(2026, 9, 16, 10, 40, tzinfo=timezone.utc).timestamp()  # 12:40 Paris

CODEX_WALL = (
    "■ You've hit your usage limit. Visit https://chatgpt.com/codex/settings/usage to\n"
    "purchase more credits or try again at Sep 21st, 2026 7:22 AM.\n\n"
    "› Ask Codex to do anything\n"
)
CLAUDE_WALL = "Agent terminated early due to an API error: You've hit your session limit · resets 6:50pm (Europe/Paris)\n"
CODEX_LOW = "⚠ Heads up, you have less than 5% of your weekly limit left. Run /status for a\n  breakdown.\n"
CODEX_LOW_25 = "⚠ Heads up, you have less than 25% of your weekly limit left.\n"
AUTH_ERROR = "Agent terminated: authentication failed (401 Unauthorized). Check your API key.\n"
NETWORK_ERROR = "Error: connect ECONNREFUSED 127.0.0.1:443\n"
SERVER_ERROR = "API error: 529 Overloaded — the server is temporarily overloaded, please retry.\n"


def policy():
    return pf.validate_policy(json.loads((ROOT / "config" / "provider-policy.json").read_text(encoding="utf-8")))


def at(text):
    return pf.iso(datetime.fromisoformat(text).timestamp())


class Detection(unittest.TestCase):
    def test_codex_wall_with_its_stated_reset(self):
        found = pf.detect(CODEX_WALL, NOW, "Europe/Paris")
        self.assertEqual("exhausted", found["kind"])
        # 7:22 AM in Paris (CEST) on the 21st is 05:22 UTC.
        self.assertEqual("2026-09-21T05:22:00Z", pf.iso(found["until"]))

    def test_claude_wall_resets_at_the_next_occurrence_in_its_own_zone(self):
        found = pf.detect(CLAUDE_WALL, NOW, "UTC")
        self.assertEqual("2026-09-16T16:50:00Z", pf.iso(found["until"]))  # 18:50 Paris
        later = datetime(2026, 9, 16, 17, 0, tzinfo=timezone.utc).timestamp()  # 19:00 Paris
        self.assertEqual("2026-09-17T16:50:00Z", pf.iso(pf.detect(CLAUDE_WALL, later)["until"]))

    def test_other_reset_phrasings(self):
        self.assertEqual(NOW + 2 * 3600, pf.parse_reset("try again in 2 hours", NOW, "UTC"))
        self.assertEqual(NOW + 45 * 60, pf.parse_reset("try again in 45 minutes", NOW, "UTC"))
        self.assertEqual(1789600000.0, pf.parse_reset("Claude AI usage limit reached|1789600000", NOW, "UTC"))
        weekly = pf.parse_reset("You've hit your weekly limit · resets Sep 22, 9am (Europe/Paris)", NOW, "UTC")
        self.assertEqual("2026-09-22T07:00:00Z", pf.iso(weekly))

    def test_a_wall_without_a_reset_is_still_a_wall(self):
        found = pf.detect("Credit balance is too low\n", NOW)
        self.assertEqual(("exhausted", None), (found["kind"], found["until"]))

    def test_early_warning(self):
        self.assertEqual({"kind": "low", "percent": 5}, {k: pf.detect(CODEX_LOW, NOW)[k] for k in ("kind", "percent")})
        self.assertEqual(25, pf.detect(CODEX_LOW_25, NOW)["percent"])

    def test_history_is_not_state(self):
        """A wall that scrolled away, or whose reset is past, is ignored."""
        scrolled = CODEX_WALL + "\n".join(f"• working on step {i}" for i in range(30))
        self.assertIsNone(pf.detect(scrolled, NOW))
        after_reset = datetime(2026, 9, 22, tzinfo=timezone.utc).timestamp()
        self.assertIsNone(pf.detect(CODEX_WALL, after_reset))
        self.assertIsNone(pf.detect("All tests pass. Rate limits look fine.\n", NOW))

    def test_non_quota_provider_failures_are_labelled_distinctly(self):
        """af-s6fqv: ADR-0018's own known limit -- a provider failing for a
        reason other than quota used to be invisible, degrading into a
        generic liveness stall. These must be labelled provider_error, never
        confused with a quota wall (which has a known, self-healing reset)."""
        auth = pf.detect(AUTH_ERROR, NOW)
        self.assertEqual(("provider_error", "auth"), (auth["kind"], auth["category"]))
        network = pf.detect(NETWORK_ERROR, NOW)
        self.assertEqual(("provider_error", "network"), (network["kind"], network["category"]))
        server = pf.detect(SERVER_ERROR, NOW)
        self.assertEqual(("provider_error", "server"), (server["kind"], server["category"]))

    def test_a_quota_wall_is_never_relabelled_as_a_generic_error(self):
        """Quota patterns are checked first: a message that happens to also
        contain a number must not be misclassified as a server error."""
        self.assertEqual("exhausted", pf.detect(CODEX_WALL, NOW)["kind"])


class Resolution(unittest.TestCase):
    def setUp(self):
        self.policy = policy()
        self.state = pf.empty_state()

    def exhaust(self, pool, until="2026-09-21T05:22:00+00:00"):
        pf.record_detection(self.state, self.policy, pool,
                            {"kind": "exhausted", "until": datetime.fromisoformat(until).timestamp(),
                             "evidence": "test"}, NOW)

    def error(self, pool, category="network"):
        pf.record_detection(self.state, self.policy, pool,
                            {"kind": "provider_error", "category": category, "evidence": "test"}, NOW)

    def pick(self, target="workspace"):
        return pf.resolve(self.policy, self.state, NOW)[target]

    def test_the_repository_policy_is_valid_and_complete(self):
        agents = {p.name for p in (ROOT / "agents").iterdir() if (p / "agent.toml").exists()}
        self.assertEqual(agents | {"workspace"}, set(self.policy["targets"]))

    def test_preferred_when_nothing_is_wrong(self):
        self.assertEqual(("codex", "preferred"), (self.pick()["provider"], self.pick()["reason"]))

    def test_codex_out_falls_back_to_claude_instead_of_stopping(self):
        self.exhaust("openai")
        self.assertEqual(("claude-standard", "fallback"), (self.pick()["provider"], self.pick()["reason"]))
        self.assertEqual("claude-standard", self.pick("mayor")["provider"])
        # The UX reviewer keeps independence from Claude writers: Spark first.
        self.assertEqual("codex-spark", self.pick("ux-reviewer")["provider"])

    def test_a_provider_error_fails_over_like_exhaustion(self):
        """af-s6fqv: a non-quota failure (auth/network/5xx) must still move
        the target off the broken provider -- being labelled distinctly is
        for the human/PO reading state, not an excuse to stop failing over."""
        self.error("openai", category="auth")
        entries = {e["provider"]: e["state"] for e in self.pick()["chain"]}
        self.assertEqual("error", entries["codex"])
        self.assertEqual(("claude-standard", "fallback"), (self.pick()["provider"], self.pick()["reason"]))

    def test_a_provider_error_backs_off_and_reports_a_next_reset(self):
        self.error("openai")
        self.error("openai-spark")
        self.error("anthropic")
        pick = self.pick()
        self.assertEqual((None, "all_unavailable"), (pick["provider"], pick["reason"]))
        self.assertIsNotNone(pick["next_reset"])  # even without a stated quota reset

    def test_one_claude_limit_takes_every_claude_profile_with_it(self):
        self.exhaust("anthropic")
        entries = {e["provider"]: e["state"] for e in self.pick("claude-reviewer")["chain"]}
        self.assertEqual({"claude": "exhausted", "claude-standard": "exhausted", "codex": "available"}, entries)
        self.assertEqual("codex", self.pick("claude-reviewer")["provider"])

    def test_total_exhaustion_names_the_earliest_reset(self):
        self.exhaust("openai", "2026-09-21T05:22:00+00:00")
        self.exhaust("openai-spark", "2026-09-17T00:00:00+00:00")
        self.exhaust("anthropic", "2026-09-16T16:50:00+00:00")
        pick = self.pick()
        self.assertEqual((None, "all_unavailable", "2026-09-16T16:50:00Z"),
                         (pick["provider"], pick["reason"], pick["next_reset"]))

    def test_it_comes_back_by_itself_at_reset(self):
        self.exhaust("openai", "2026-09-16T11:00:00+00:00")
        self.assertEqual("claude-standard", self.pick()["provider"])
        after = datetime(2026, 9, 16, 11, 1, tzinfo=timezone.utc).timestamp()
        self.assertEqual("codex", pf.resolve(self.policy, self.state, after)["workspace"]["provider"])

    def test_unknown_reset_backs_off(self):
        wall = {"kind": "exhausted", "until": None, "evidence": "x"}
        spans = []
        for _ in range(5):
            pf.record_detection(self.state, self.policy, "openai", dict(wall), NOW)
            spans.append((pf.epoch(self.state["pools"]["openai"]["until"]) - NOW) / 60)
            self.state["pools"]["openai"]["until"] = pf.iso(NOW - 1)  # expire, then hit again
        self.assertEqual([60, 120, 240, 480, 480], spans)

    def test_a_low_pool_is_used_only_when_nothing_healthier_is_left(self):
        pf.record_detection(self.state, self.policy, "openai", {"kind": "low", "percent": 5, "evidence": "x"}, NOW)
        self.assertEqual("claude-standard", self.pick()["provider"])
        self.exhaust("anthropic")
        pf.record_detection(self.state, self.policy, "openai-spark",
                            {"kind": "exhausted", "until": NOW + 3600, "evidence": "x"}, NOW)
        self.assertEqual("codex", self.pick()["provider"])  # low beats nothing
        # 25% left is not low under the default 5% threshold.
        fresh = pf.empty_state()
        self.assertFalse(pf.record_detection(fresh, self.policy, "openai",
                                             {"kind": "low", "percent": 25, "evidence": "x"}, NOW))

    def test_manual_controls_outrank_detection(self):
        pf.apply_control(self.state, self.policy, "mark",
                         {"pool": "openai", "until": "2026-09-21T05:22:00Z", "reason": "vu à l'écran"}, NOW, "Benjamin")
        # A later detection with another reset does not overwrite a human mark.
        self.assertFalse(pf.record_detection(self.state, self.policy, "openai",
                                             {"kind": "exhausted", "until": NOW + 60, "evidence": "x"}, NOW))
        self.assertEqual("Benjamin", self.state["pools"]["openai"]["by"])
        pf.apply_control(self.state, self.policy, "clear", {"pool": "openai"}, NOW, "Benjamin")
        self.assertEqual("codex", self.pick()["provider"])

    def test_disable_force_and_reorder(self):
        pf.apply_control(self.state, self.policy, "disable", {"provider": "codex"}, NOW, "B")
        self.assertEqual("claude-standard", self.pick()["provider"])
        pf.apply_control(self.state, self.policy, "chain",
                         {"target": "workspace", "chain": ["codex-spark", "claude"]}, NOW, "B")
        self.assertEqual("codex-spark", self.pick()["provider"])
        pf.apply_control(self.state, self.policy, "force", {"target": "workspace", "provider": "codex"}, NOW, "B")
        forced = self.pick()
        self.assertEqual(("codex", "forced"), (forced["provider"], forced["reason"]))
        self.assertIn("disabled", forced["warning"])  # forcing a disabled one is allowed, and said
        pf.apply_control(self.state, self.policy, "force", {"target": "workspace", "provider": "auto"}, NOW, "B")
        pf.apply_control(self.state, self.policy, "chain", {"target": "workspace", "chain": "default"}, NOW, "B")
        pf.apply_control(self.state, self.policy, "enable", {"provider": "codex"}, NOW, "B")
        self.assertEqual("codex", self.pick()["provider"])
        self.assertEqual(6, len(self.state["history"]))

    def test_manual_mode_shows_detections_but_does_not_act(self):
        self.exhaust("openai")
        pf.apply_control(self.state, self.policy, "auto", {"enabled": False}, NOW, "B")
        self.assertEqual("codex", self.pick()["provider"])
        # ...while a human mark still applies in manual mode.
        pf.apply_control(self.state, self.policy, "mark", {"pool": "openai", "minutes": 30}, NOW, "B")
        self.assertEqual("claude-standard", self.pick()["provider"])

    def test_invalid_controls_are_refused(self):
        for action, args in [
            ("mark", {"pool": "nope", "minutes": 5}),
            ("mark", {"pool": "openai"}),
            ("mark", {"pool": "openai", "until": "2020-01-01T00:00:00Z"}),
            ("disable", {"provider": "gpt-9"}),
            ("force", {"target": "nobody", "provider": "codex"}),
            ("chain", {"target": "workspace", "chain": ["codex", "codex"]}),
            ("chain", {"target": "workspace", "chain": ["unknown"]}),
            ("explode", {}),
        ]:
            with self.subTest(action=action, args=args):
                with self.assertRaises(pf.PolicyError):
                    pf.apply_control(self.state, self.policy, action, args, NOW, "B")

    def test_damaged_state_degrades_to_defaults(self):
        state = pf.normalize_state({"auto": True, "disabled": {"gpt-9": {}}, "forced": {"mayor": "gpt-9"},
                                    "chains": {"workspace": ["codex", "codex"]}, "pools": "junk"},
                                   self.policy)
        self.assertEqual(({}, {}, {}, {}), (state["disabled"], state["forced"], state["chains"], state["pools"]))
        self.assertEqual(pf.empty_state()["contract"], pf.normalize_state("garbage", self.policy)["contract"])

    def test_overlay(self):
        self.exhaust("openai")
        text, effective = pf.render_overlay(self.policy, pf.resolve(self.policy, self.state, NOW), {})
        self.assertIn('[workspace]\nprovider = "claude-standard"', text)
        self.assertIn('[[patches.agent]]\nname = "mayor"\nprovider = "claude-standard"', text)
        self.assertEqual("codex-spark", effective["ux-reviewer"])
        # Nothing available: keep what was running rather than silently falling
        # back to whatever city.toml happens to say.
        for pool in self.policy["pools"]:
            self.exhaust(pool)
        _, kept = pf.render_overlay(self.policy, pf.resolve(self.policy, self.state, NOW), effective)
        self.assertEqual(effective, kept)

    def test_session_targets(self):
        p = self.policy
        self.assertEqual("mayor", pf.target_of({"template": "mayor", "provider": "claude-standard"}, p))
        self.assertEqual("workspace", pf.target_of({"template": "saymyname-backend/claude", "provider": "claude-standard"}, p))
        self.assertIsNone(pf.target_of({"template": "core.control-dispatcher"}, p))


class ModelStaleness(unittest.TestCase):
    """af-a1t44 (ADR-0018 part 2): pure logic only, no I/O."""

    CATALOG = {
        "contract": "agent-factory-model-catalog/v1",
        "providers": {
            "codex": {"recommended": ["gpt-5.6-sol"]},
            "claude-cheap": {"recommended": ["haiku"]},
        },
    }

    def test_the_repository_catalog_is_valid(self):
        catalog = json.loads((ROOT / "config" / "model-catalog.json").read_text(encoding="utf-8"))
        pf.validate_catalog(catalog)

    def test_catalog_needs_a_non_empty_recommended_list_per_provider(self):
        with self.assertRaises(pf.PolicyError):
            pf.validate_catalog({"contract": pf.CATALOG_CONTRACT, "providers": {"codex": {"recommended": []}}})
        with self.assertRaises(pf.PolicyError):
            pf.validate_catalog({"contract": "wrong/v1", "providers": {}})

    def test_configured_model_from_claude_option_defaults(self):
        self.assertEqual("sonnet-5", pf.configured_model(
            {"option_defaults": {"model": "sonnet-5", "effort": "high"}}))

    def test_configured_model_from_codex_args_append(self):
        self.assertEqual("gpt-5.6-sol", pf.configured_model(
            {"args_append": ["-m", "gpt-5.6-sol"]}))

    def test_configured_model_absent_is_none_not_an_error(self):
        self.assertIsNone(pf.configured_model({"base": "builtin:codex"}))
        self.assertIsNone(pf.configured_model({}))

    def test_a_deliberately_outdated_model_id_is_flagged(self):
        configured = {"codex": "gpt-5.6-sol", "claude-cheap": "haiku-legacy-2024"}
        stale = pf.stale_models(configured, self.CATALOG["providers"])
        self.assertEqual([{"provider": "claude-cheap", "configured": "haiku-legacy-2024",
                           "recommended": ["haiku"]}], stale)

    def test_a_current_model_id_is_never_flagged(self):
        configured = {"codex": "gpt-5.6-sol", "claude-cheap": "haiku"}
        self.assertEqual([], pf.stale_models(configured, self.CATALOG["providers"]))

    def test_a_provider_the_catalog_does_not_know_is_skipped_not_guessed_at(self):
        configured = {"codex-spark": "gpt-5.3-codex-spark"}
        self.assertEqual([], pf.stale_models(configured, self.CATALOG["providers"]))


STUB_GC = r'''#!/usr/bin/env python3
import json, os, sys
d = os.environ["PF_FIXTURE"]
args = sys.argv[1:]
with open(os.path.join(d, "calls.log"), "a") as log:
    log.write(" ".join(args) + "\n")
if args[:3] == ["session", "list", "--json"]:
    print(open(os.path.join(d, "sessions.json")).read()); sys.exit(0)
if args[:2] == ["session", "peek"]:
    path = os.path.join(d, "panes", args[2] + ".txt")
    print(open(path).read() if os.path.exists(path) else ""); sys.exit(0)
if args[:2] == ["bd", "show"]:
    print(open(os.path.join(d, "coord.json")).read()); sys.exit(0)
if args[:2] == ["bd", "create"]:
    counter = os.path.join(d, "bead_counter")
    n = int(open(counter).read()) + 1 if os.path.exists(counter) else 1
    open(counter, "w").write(str(n))
    print(json.dumps({"id": "af-stale%d" % n})); sys.exit(0)
if args[:1] in (["reload"], ["session"], ["mail"]):
    print("ok"); sys.exit(0)
sys.exit(0)
'''

STUB_CAMPAIGN = r'''#!/usr/bin/env python3
import json, os, sys
d = os.environ["PF_FIXTURE"]
with open(os.path.join(d, "campaign.log"), "a") as log:
    log.write(" ".join(sys.argv[1:]) + "\n")
coord = os.path.join(d, "coord.json")
value = json.load(open(coord))
meta = value[0]["metadata"]
if sys.argv[1] == "block":
    a = sys.argv
    meta.update({"gc.campaign_state": "blocked", "gc.campaign_block_kind": a[a.index("--kind") + 1],
                 "gc.campaign_cause": a[a.index("--cause") + 1]})
elif sys.argv[1] == "resume":
    meta.update({"gc.campaign_state": "active", "gc.campaign_block_kind": "", "gc.campaign_cause": ""})
json.dump(value, open(coord, "w"))
'''


class EndToEnd(unittest.TestCase):
    """bin/provider-failover against a stub city: the acceptance scenario."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        (self.d / "panes").mkdir()
        for name, body in (("gc", STUB_GC), ("mayor-campaign", STUB_CAMPAIGN)):
            path = self.d / name
            path.write_text(body, encoding="utf-8")
            path.chmod(0o755)
        self.sessions([
            {"id": "af-w1", "alias": "saymyname-backend/codex-1", "template": "saymyname-backend/codex",
             "state": "active", "provider": "codex"},
            {"id": "af-m", "alias": "mayor", "template": "mayor", "state": "active", "provider": "codex"},
            {"id": "af-d", "alias": "core.control-dispatcher", "template": "core.control-dispatcher", "state": "active"},
        ])
        (self.d / "coord.json").write_text(json.dumps([{"id": "af-1vr4", "metadata": {
            "gc.campaign_mode": "automatic", "gc.campaign_state": "active"}}]), encoding="utf-8")
        self.env = {
            **os.environ,
            "PF_FIXTURE": str(self.d),
            "GC_BIN": str(self.d / "gc"),
            "CAMPAIGN_BIN": str(self.d / "mayor-campaign"),
            "PROVIDER_STATE_FILE": str(self.d / "state.json"),
            "PROVIDER_OVERLAY_FILE": str(self.d / "city.provider.toml"),
            "PROVIDER_NOW": str(NOW),
            "PROVIDER_LOCAL_TZ": "Europe/Paris",
            "FACTORY_ROOT": str(self.d),
            "PROVIDER_POLICY_FILE": str(ROOT / "config" / "provider-policy.json"),
        }

    def tearDown(self):
        self.tmp.cleanup()

    def sessions(self, value):
        (self.d / "sessions.json").write_text(json.dumps(value), encoding="utf-8")

    def pane(self, session_id, text):
        (self.d / "panes" / f"{session_id}.txt").write_text(text, encoding="utf-8")

    def run_tool(self, *args, check=True, **env):
        return subprocess.run([sys.executable, str(ROOT / "bin" / "provider-failover"), *args],
                              env={**self.env, **env}, text=True, capture_output=True, check=check)

    def calls(self, name="calls.log"):
        path = self.d / name
        return path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    def overlay(self):
        return (self.d / "city.provider.toml").read_text(encoding="utf-8")

    def test_codex_wall_switches_restarts_the_stuck_session_and_keeps_working(self):
        self.pane("af-w1", CODEX_WALL)
        out = self.run_tool("tick").stdout
        self.assertIn('provider = "claude-standard"', self.overlay())
        self.assertIn("reload", self.calls())
        self.assertIn("session reset af-w1", self.calls())
        self.assertIn("restarted saymyname-backend/codex-1: codex → claude-standard", out)
        state = json.loads((self.d / "state.json").read_text(encoding="utf-8"))
        self.assertEqual("2026-09-21T05:22:00Z", state["pools"]["openai"]["until"])
        # Work continues: the campaign is not touched.
        self.assertEqual([], self.calls("campaign.log"))
        # A second tick with nothing new changes nothing.
        before = len(self.calls())
        self.pane("af-w1", "")
        self.run_tool("tick")
        self.assertNotIn("reload", self.calls()[before:])
        # The deterministic dispatcher is never peeked.
        self.assertFalse(any(c == "session peek af-d" for c in self.calls()))

    def test_total_exhaustion_parks_then_resumes_on_its_own(self):
        self.pane("af-w1", CODEX_WALL)
        self.pane("af-m", CLAUDE_WALL)
        self.sessions([
            {"id": "af-w1", "template": "saymyname-backend/codex", "state": "active", "provider": "codex"},
            {"id": "af-m", "template": "mayor", "state": "active", "provider": "claude-standard"},
            {"id": "af-s", "template": "saymyname-frontend/spark", "state": "active", "provider": "codex-spark"},
        ])
        self.pane("af-s", "You've hit your usage limit. try again in 3 hours\n")
        self.run_tool("tick")
        parked = self.calls("campaign.log")
        self.assertEqual(1, len(parked))
        self.assertIn("block --mayor --kind limit --owner Mayor", parked[0])
        self.assertIn("[provider-failover]", parked[0])
        self.assertIn("reprise automatique vers 2026-09-16T13:40:00Z", parked[0])  # earliest: spark, 3h
        # Never a human decision: no needs_benjamin, owner is the Mayor.
        self.assertNotIn("Benjamin", parked[0].split("--action")[0])
        # Ticking again while still exhausted does not park twice.
        self.run_tool("tick")
        self.assertEqual(1, len(self.calls("campaign.log")))
        # Three hours later Spark is back: the campaign resumes by itself.
        for sid in ("af-w1", "af-m", "af-s"):
            self.pane(sid, "")
        later = datetime(2026, 9, 16, 13, 41, tzinfo=timezone.utc).timestamp()
        self.run_tool("tick", PROVIDER_NOW=str(later))
        self.assertEqual("resume --mayor", self.calls("campaign.log")[-1])
        self.assertIn('provider = "codex-spark"', self.overlay())

    def test_panes_are_read_from_tmux_without_calling_gc(self):
        """gc session peek cost 8 s a call; tmux answers in milliseconds."""
        tmux = self.d / "tmux"
        tmux.write_text(
            "#!/usr/bin/env bash\n"
            'echo "$*" >> "$PF_FIXTURE/tmux.log"\n'
            'target=""; while [ $# -gt 0 ]; do [ "$1" = -t ] && target="$2"; shift; done\n'
            '[ "$target" = "=codex-1:" ] || exit 1\n'
            "cat \"$PF_FIXTURE/panes/af-w1.txt\"\n", encoding="utf-8")
        tmux.chmod(0o755)
        self.sessions([
            {"id": "af-w1", "session_name": "codex-1", "template": "saymyname-backend/codex",
             "state": "active", "provider": "codex"},
            {"id": "af-m", "session_name": "gone", "template": "mayor", "state": "active", "provider": "codex"},
        ])
        self.pane("af-w1", CODEX_WALL)
        self.run_tool("tick", PROVIDER_TMUX_BIN=str(tmux), PROVIDER_TMUX_SOCKET="agent-factory")
        self.assertIn('provider = "claude-standard"', self.overlay())
        log = (self.d / "tmux.log").read_text(encoding="utf-8")
        self.assertIn("-L agent-factory capture-pane -p -J -t =codex-1:", log)
        # tmux answered for af-w1: no gc peek for it...
        self.assertNotIn("session peek af-w1", self.calls())
        # ...and a session tmux does not know falls back to gc.
        self.assertIn("session peek af-m", self.calls())

    def test_a_healthy_tick_does_not_read_the_campaign(self):
        """Store reads are slow under load: only decide when there is a decision."""
        self.run_tool("tick")
        self.assertFalse(any(c.startswith("bd show") for c in self.calls()))
        before = len(self.calls())
        self.run_tool("status", "--json")
        self.assertEqual(before, len(self.calls()), "status must not call gc")

    def test_a_block_we_did_not_set_is_never_lifted(self):
        coord = [{"id": "af-1vr4", "metadata": {
            "gc.campaign_mode": "automatic", "gc.campaign_state": "blocked",
            "gc.campaign_block_kind": "limit", "gc.campaign_cause": "Limite posée par le Mayor"}}]
        (self.d / "coord.json").write_text(json.dumps(coord), encoding="utf-8")
        # Even believing it parked something, it lifts only its own marker.
        (self.d / "state.json").write_text(json.dumps({"parked": True}), encoding="utf-8")
        self.run_tool("tick")
        self.assertEqual([], self.calls("campaign.log"))
        self.assertFalse(json.loads((self.d / "state.json").read_text())["parked"])

    def test_cockpit_controls_through_the_cli(self):
        result = json.loads(self.run_tool(
            "set", "--action", "mark", "--by", "Benjamin (cockpit)",
            "--args", json.dumps({"pool": "openai", "minutes": 90, "reason": "limite vue sur le site"})).stdout)
        self.assertTrue(result["ok"])
        self.assertEqual("claude-standard", result["status"]["targets"]["workspace"]["provider"])
        self.assertEqual("manual", result["status"]["pools"]["openai"]["source"])
        self.assertIn('provider = "claude-standard"', self.overlay())
        bad = self.run_tool("set", "--action", "mark", "--args", '{"pool":"openai"}', check=False)
        self.assertEqual(2, bad.returncode)
        self.assertFalse(json.loads(bad.stdout)["ok"])
        self.run_tool("tick")  # the snapshot of live sessions comes from a tick
        status = json.loads(self.run_tool("status", "--json").stdout)
        self.assertEqual("agent-factory-provider-status/v1", status["contract"])
        self.assertEqual({"workspace", "mayor", "claude-reviewer", "ux-reviewer"}, set(status["targets"]))
        self.assertIn("manual:mark", [h["event"] for h in status["history"]])
        self.assertEqual({"af-w1", "af-m"}, {s["id"] for s in status["sessions"]})

    def test_a_missing_or_corrupt_state_never_breaks_the_overlay(self):
        (self.d / "state.json").write_text("{not json", encoding="utf-8")
        self.run_tool("apply", "--no-reload")
        self.assertIn('[workspace]\nprovider = "codex"', self.overlay())

    def test_apply_regenerates_a_deleted_overlay(self):
        self.run_tool("apply", "--no-reload")
        (self.d / "city.provider.toml").unlink()
        self.assertIn("written", self.run_tool("apply", "--no-reload").stdout)
        self.assertTrue((self.d / "city.provider.toml").exists())


FIXTURE_CITY_TOML = '''
[providers.codex]
base = "builtin:codex"
args_append = ["-m", "gpt-5.6-sol"]

[providers.codex-spark]
base = "builtin:codex"
args_append = ["-m", "gpt-5.3-codex-spark"]

[providers.claude]
base = "builtin:claude"
[providers.claude.option_defaults]
model = "sonnet-5"

[providers.claude-standard]
base = "builtin:claude"
[providers.claude-standard.option_defaults]
model = "sonnet-5"

[providers.claude-cheap]
base = "builtin:claude"
[providers.claude-cheap.option_defaults]
model = "haiku-legacy-2024"
'''

FIXTURE_CATALOG = json.dumps({
    "contract": "agent-factory-model-catalog/v1",
    "providers": {
        "codex": {"recommended": ["gpt-5.6-sol"]},
        "codex-spark": {"recommended": ["gpt-5.3-codex-spark"]},
        "claude": {"recommended": ["sonnet-5"]},
        "claude-standard": {"recommended": ["sonnet-5"]},
        "claude-cheap": {"recommended": ["haiku"]},
    },
})


class ModelStalenessCLI(unittest.TestCase):
    """bin/provider-failover check-models -- af-a1t44 acceptance scenario.

    A deliberately-outdated model id (claude-cheap: "haiku-legacy-2024" against
    a catalog that recommends "haiku") must get flagged, not silently ignored;
    nothing in this path may switch a model itself.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        gc_path = self.d / "gc"
        gc_path.write_text(STUB_GC, encoding="utf-8")
        gc_path.chmod(0o755)
        (self.d / "city.toml").write_text(FIXTURE_CITY_TOML, encoding="utf-8")
        (self.d / "model-catalog.json").write_text(FIXTURE_CATALOG, encoding="utf-8")
        self.env = {
            **os.environ,
            "PF_FIXTURE": str(self.d),
            "GC_BIN": str(gc_path),
            "FACTORY_ROOT": str(self.d),
            "PROVIDER_POLICY_FILE": str(ROOT / "config" / "provider-policy.json"),
            "PROVIDER_STATE_FILE": str(self.d / "state.json"),
            "CITY_TOML_FILE": str(self.d / "city.toml"),
            "MODEL_CATALOG_FILE": str(self.d / "model-catalog.json"),
            "PROVIDER_NOW": str(NOW),
        }

    def tearDown(self):
        self.tmp.cleanup()

    def run_tool(self, *args, check=True, **env):
        return subprocess.run([sys.executable, str(ROOT / "bin" / "provider-failover"), *args],
                              env={**self.env, **env}, text=True, capture_output=True, check=check)

    def calls(self):
        path = self.d / "calls.log"
        return path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    def test_a_deliberately_outdated_model_id_is_flagged_not_silently_ignored(self):
        out = self.run_tool("check-models").stdout
        self.assertIn("stale: claude-cheap configured=haiku-legacy-2024", out)
        self.assertIn("bead filed:", out)
        self.assertTrue(any(c.startswith("bd create") for c in self.calls()))
        self.assertTrue(any(c.startswith("mail send mayor") for c in self.calls()))
        state = json.loads((self.d / "state.json").read_text(encoding="utf-8"))
        self.assertIn("claude-cheap=haiku-legacy-2024", state["model_staleness"]["signature"])
        self.assertTrue(state["model_staleness"]["bead"])

    def test_a_current_model_id_is_not_flagged(self):
        (self.d / "city.toml").write_text(
            FIXTURE_CITY_TOML.replace("haiku-legacy-2024", "haiku"), encoding="utf-8")
        out = self.run_tool("check-models").stdout
        self.assertIn("every configured model id matches the catalog", out)
        self.assertFalse(any(c.startswith("bd create") for c in self.calls()))

    def test_the_same_drift_is_not_refiled_the_next_day(self):
        first = self.run_tool("check-models").stdout
        self.assertIn("bead filed:", first)
        second = self.run_tool("check-models").stdout
        self.assertIn("already flagged:", second)
        self.assertEqual(1, sum(1 for c in self.calls() if c.startswith("bd create")))

    def test_a_resolved_drift_is_reflagged_if_it_recurs_differently(self):
        self.run_tool("check-models")
        (self.d / "city.toml").write_text(
            FIXTURE_CITY_TOML.replace("haiku-legacy-2024", "haiku-legacy-2025"), encoding="utf-8")
        out = self.run_tool("check-models").stdout
        self.assertIn("bead filed:", out)
        self.assertEqual(2, sum(1 for c in self.calls() if c.startswith("bd create")))

    def test_it_never_writes_city_toml_or_the_catalog(self):
        before_city = (self.d / "city.toml").read_text(encoding="utf-8")
        before_catalog = (self.d / "model-catalog.json").read_text(encoding="utf-8")
        self.run_tool("check-models")
        self.assertEqual(before_city, (self.d / "city.toml").read_text(encoding="utf-8"))
        self.assertEqual(before_catalog, (self.d / "model-catalog.json").read_text(encoding="utf-8"))

    def test_dry_run_never_files_a_bead_or_writes_state(self):
        out = self.run_tool("check-models", "--dry-run").stdout
        self.assertIn("dry-run: would file a bead", out)
        self.assertFalse(any(c.startswith("bd create") for c in self.calls()))
        self.assertFalse((self.d / "state.json").exists())

    def test_runs_on_a_daily_cooldown_not_per_tick(self):
        order = (ROOT / "orders" / "model-staleness-check.toml").read_text(encoding="utf-8")
        self.assertIn('trigger = "cooldown"', order)
        self.assertIn('interval = "24h"', order)
        self.assertIn("check-models", order)


if __name__ == "__main__":
    unittest.main(verbosity=1)
