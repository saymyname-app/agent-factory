"""Cockpit process configuration, read from the environment.

Kept as plain env vars (no config file yet) so a test can point the process
at fake sources and shrunk Validity windows without writing a temp file.
"""
import os

from cockpit.core.freshness import VALIDITY_WINDOWS_SECONDS

DEFAULT_PORT = 8173
DEFAULT_GC_BASE_URL = "http://127.0.0.1:8372"

# Out-of-scope touch (T14, af-peh3yy -- declared scope lib/cockpit/actions/**,
# lib/cockpit/ui/actions/**): répondre/accepter/rejeter/reporter une
# proposition/relancer each shell out to one door -- this is the repo root
# those doors' default paths live under, computed from this file's own
# location rather than a hardcoded path so a worktree (this one included)
# naturally finds `bin/escalation-door` etc. next to itself; every default
# is still overridable by env, and the tests override every one of them to
# point at fakes.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class Config:
    def __init__(self, env=None):
        env = os.environ if env is None else env
        self.host = env.get("COCKPIT_HOST", "127.0.0.1")
        self.port = int(env.get("COCKPIT_PORT", DEFAULT_PORT))
        self.gc_base_url = env.get("COCKPIT_GC_BASE_URL", DEFAULT_GC_BASE_URL)
        self.bd_bin = env.get("COCKPIT_BD_BIN", "bd")
        self.beads_poll_seconds = float(env.get("COCKPIT_BEADS_POLL_SECONDS", "20"))
        self.pid_file = env.get("COCKPIT_PID_FILE") or _default_pid_file(env)
        # Out-of-scope touch (T13, af-cx20q9 -- declared scope
        # lib/cockpit/access/**, lib/cockpit/actions/**): the access
        # guard needs Benjamin's Tailscale login and the origin the
        # cockpit itself serves from (spec .9 "Accès et sécurité").
        # Empty by default -- with no configured login every Operator
        # Action is refused rather than silently open (fail closed).
        self.benjamin_login = env.get("COCKPIT_BENJAMIN_LOGIN", "")
        self.allowed_origin = env.get("COCKPIT_ALLOWED_ORIGIN") or _default_origin(self.host, self.port)
        # Out-of-scope touch (T14, af-peh3yy -- declared scope
        # lib/cockpit/actions/**, lib/cockpit/ui/actions/**): répondre,
        # accepter/rejeter/reporter une proposition, and relancer each
        # shell out to one door/binary -- configurable the same way
        # COCKPIT_BD_BIN already is, so a test can point every one at a
        # fake.
        self.escalation_door_bin = env.get(
            "COCKPIT_ESCALATION_DOOR_BIN", os.path.join(_REPO_ROOT, "bin", "escalation-door")
        )
        self.proposal_door_bin = env.get(
            "COCKPIT_PROPOSAL_DOOR_BIN", os.path.join(_REPO_ROOT, "bin", "proposal-door")
        )
        self.loop_guard_bin = env.get(
            "COCKPIT_LOOP_GUARD_BIN", os.path.join(_REPO_ROOT, "bin", "factory-session-loop-guard")
        )
        self.gc_bin = env.get("COCKPIT_GC_BIN", "gc")
        self.validity_seconds = dict(VALIDITY_WINDOWS_SECONDS)
        for source in list(self.validity_seconds):
            override = env.get("COCKPIT_VALIDITY_%s_SECONDS" % source.upper())
            if override is not None:
                self.validity_seconds[source] = float(override)


def _default_pid_file(env):
    root = env.get("FACTORY_ROOT", "/home/benja/agent-factory")
    return os.path.join(root, ".gc", "runtime", "cockpit.pid")


def _default_origin(host, port):
    return "http://%s:%d" % (host, port)
