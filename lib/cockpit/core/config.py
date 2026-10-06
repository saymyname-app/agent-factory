"""Cockpit process configuration, read from the environment.

Kept as plain env vars (no config file yet) so a test can point the process
at fake sources and shrunk Validity windows without writing a temp file.
"""
import os

from cockpit.core.freshness import VALIDITY_WINDOWS_SECONDS
from cockpit.core.gc_client import (
    RECONNECT_SECONDS,
    STATUS_POLL_SECONDS,
    STREAM_SILENCE_SECONDS,
)
from cockpit.requests.sources.readability import ILLISIBLE_THRESHOLD_SECONDS
from cockpit.notify.pushover import PUSHOVER_URL
from cockpit.health.engine import (
    FACTORY_STALLED_AFTER_SECONDS,
    SUPERVISOR_UNREACHABLE_AFTER_SECONDS,
)

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
        # Unset: the supervisor's own city list names it (gc_client).
        self.gc_city = env.get("COCKPIT_GC_CITY") or None
        self.gc_status_poll_seconds = float(
            env.get("COCKPIT_GC_STATUS_POLL_SECONDS", str(STATUS_POLL_SECONDS))
        )
        self.gc_stream_silence_seconds = float(
            env.get("COCKPIT_GC_STREAM_SILENCE_SECONDS", str(STREAM_SILENCE_SECONDS))
        )
        self.gc_reconnect_seconds = float(
            env.get("COCKPIT_GC_RECONNECT_SECONDS", str(RECONNECT_SECONDS))
        )
        self.bd_bin = env.get("COCKPIT_BD_BIN", "bd")
        self.beads_poll_seconds = float(env.get("COCKPIT_BEADS_POLL_SECONDS", "20"))
        # "Projets" zone: the declared projects (one descriptor file each)
        # and how often their chantiers are recomputed from Beads.
        self.descriptors_dir = env.get(
            "COCKPIT_DESCRIPTORS_DIR", os.path.join(_REPO_ROOT, "config", "project-descriptors")
        )
        self.projects_poll_seconds = float(env.get("COCKPIT_PROJECTS_POLL_SECONDS", "30"))
        self.journal_poll_seconds = float(env.get("COCKPIT_JOURNAL_POLL_SECONDS", "60"))
        # spec .17: a source unreadable for longer than this is itself a request.
        self.illisible_after_seconds = float(
            env.get("COCKPIT_ILLISIBLE_SECONDS", str(ILLISIBLE_THRESHOLD_SECONDS))
        )
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
        # Notifications and heartbeat (spec §"Notifications", §"Heartbeat et
        # usine muette"). Both secret files live outside the repository, on
        # the Windows side; unset or unreadable, nothing is sent or pinged
        # and the health zone says so (spec .98).
        self.pushover_secrets_file = env.get("COCKPIT_PUSHOVER_SECRETS_FILE", "")
        self.pushover_url = env.get("COCKPIT_PUSHOVER_URL", PUSHOVER_URL)
        self.notify_state_file = env.get("COCKPIT_NOTIFY_STATE_FILE") or os.path.join(
            os.path.dirname(self.pid_file), "cockpit-notify-state.json"
        )
        self.notify_tick_seconds = float(env.get("COCKPIT_NOTIFY_TICK_SECONDS", "30"))
        # The address a push links back to: the ts.net URL once Tailscale
        # Serve exposes the cockpit; the local origin until then.
        self.public_url = env.get("COCKPIT_PUBLIC_URL") or self.allowed_origin
        self.heartbeat_url_file = env.get("COCKPIT_HEARTBEAT_URL_FILE", "")
        self.heartbeat_tick_seconds = float(env.get("COCKPIT_HEARTBEAT_TICK_SECONDS", "30"))
        self.heartbeat_interval_seconds = float(env.get("COCKPIT_HEARTBEAT_INTERVAL_SECONDS", "300"))
        self.validity_seconds = dict(VALIDITY_WINDOWS_SECONDS)
        for source in list(self.validity_seconds):
            override = env.get("COCKPIT_VALIDITY_%s_SECONDS" % source.upper())
            if override is not None:
                self.validity_seconds[source] = float(override)

        # Health zone (spec .66-.69, T16): reading how far the live root is
        # behind its promotion branch, and the two fixed alert thresholds.
        self.git_bin = env.get("COCKPIT_GIT_BIN", "git")
        # Opt-in, unlike the other sources: an unset COCKPIT_REPO_DIR means
        # "no version-behind polling" rather than defaulting to the live
        # root, which would make every process (tests included) reach the
        # real origin remote over the network (Testing Decisions: "la CI
        # n'a ni ... ni GitHub" — T11's same "only wire sources we have
        # fakes for" precedent).
        self.repo_dir = env.get("COCKPIT_REPO_DIR")
        self.git_remote = env.get("COCKPIT_GIT_REMOTE", "origin")
        self.git_branch = env.get("COCKPIT_GIT_BRANCH", "main")
        self.git_poll_seconds = float(env.get("COCKPIT_GIT_POLL_SECONDS", "60"))
        self.supervisor_unreachable_after_seconds = float(
            env.get(
                "COCKPIT_HEALTH_SUPERVISOR_UNREACHABLE_SECONDS",
                str(SUPERVISOR_UNREACHABLE_AFTER_SECONDS),
            )
        )
        self.factory_stalled_after_seconds = float(
            env.get(
                "COCKPIT_HEALTH_FACTORY_STALLED_SECONDS",
                str(FACTORY_STALLED_AFTER_SECONDS),
            )
        )


def _default_pid_file(env):
    root = env.get("FACTORY_ROOT", "/home/benja/agent-factory")
    return os.path.join(root, ".gc", "runtime", "cockpit.pid")


def _default_origin(host, port):
    return "http://%s:%d" % (host, port)
