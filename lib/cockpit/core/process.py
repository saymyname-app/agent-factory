"""Wires the read model, the sources, and the HTTP server into one process.

``run_foreground`` is what ``bin/cockpit run`` calls: it blocks until
SIGTERM/SIGINT, then shuts every poller and the HTTP server down and
returns cleanly. A source going quiet (gc suspended, city stopped) never
raises out of here — see the individual pollers.
"""
import signal
import sys
import threading

from cockpit.access.guard import ActionGuard, new_session_token
from cockpit.actions.registry import build_action_handlers
from cockpit.core.beads_source import read_operator_beads
from cockpit.core.clock import SystemClock
from cockpit.core.gc_client import GcSsePoller
from cockpit.core.polling_source import PollingSource
from cockpit.core.readmodel import ReadModel
from cockpit.core.server import make_server
from cockpit.health.git_source import count_commits_behind

# github/rituals sources are in the Validity window table (spec .3) for the
# tickets that will wire up their producers; T11 builds the seam and wires
# only the two sources it has fakes for (gc, beads) so headline/AC3 can
# reach "tout est à jour" without depending on unbuilt producers. T16 adds
# "git" for the health zone's version-behind signal (spec .66) the same
# way, opt-in via config.repo_dir (see Config.repo_dir).
SOURCE_DISPLAY_NAMES = {
    "gc": "usine (gc)",
    "beads": "Beads",
}


def build(config, clock=None):
    """Returns (server, pollers) — nothing is started yet."""
    clock = clock or SystemClock()
    read_model = ReadModel(clock, validity_seconds=config.validity_seconds)
    for name, display_name in SOURCE_DISPLAY_NAMES.items():
        read_model.register(name, display_name=display_name)

    pollers = [GcSsePoller(read_model, config.gc_base_url)]
    if config.bd_bin:
        pollers.append(
            PollingSource(
                read_model,
                "beads",
                lambda: read_operator_beads(bd_bin=config.bd_bin),
                config.beads_poll_seconds,
            )
        )
    if config.repo_dir:
        read_model.register("git", display_name="dépôt (git)")
        pollers.append(
            PollingSource(
                read_model,
                "git",
                lambda: count_commits_behind(
                    config.repo_dir,
                    remote=config.git_remote,
                    branch=config.git_branch,
                    git_bin=config.git_bin,
                ),
                config.git_poll_seconds,
            )
        )
    # Out-of-scope touch (T13, af-cx20q9 -- declared scope
    # lib/cockpit/actions/**, lib/cockpit/access/**): the actions and
    # the guard that gates them only reach the HTTP surface once wired
    # in here, next to every other source.
    session_token = new_session_token()
    action_guard = ActionGuard(config.benjamin_login, config.allowed_origin, session_token)
    # Out-of-scope touch (T14, af-peh3yy -- declared scope
    # lib/cockpit/actions/**, lib/cockpit/ui/actions/**): répondre,
    # accepter/rejeter/reporter une proposition, and relancer need the
    # escalation-door/proposal-door/loop-guard/gc binaries wired through
    # from config, the same as bd_bin already is.
    action_handlers = build_action_handlers(
        config.bd_bin,
        clock,
        escalation_door_bin=config.escalation_door_bin,
        proposal_door_bin=config.proposal_door_bin,
        loop_guard_bin=config.loop_guard_bin,
        gc_bin=config.gc_bin,
    )
    server = make_server(
        read_model,
        host=config.host,
        port=config.port,
        action_guard=action_guard,
        action_handlers=action_handlers,
        session_token=session_token,
        pollers=pollers,
        supervisor_unreachable_after_seconds=config.supervisor_unreachable_after_seconds,
        factory_stalled_after_seconds=config.factory_stalled_after_seconds,
    )
    return server, pollers


def run_foreground(config, clock=None, ready_callback=None):
    server, pollers = build(config, clock=clock)
    for poller in pollers:
        poller.start()

    stop_requested = []

    def _handle_stop(signum, frame):
        # server.shutdown() blocks until serve_forever()'s loop notices and
        # exits — calling it from this handler, which runs on the same
        # thread serve_forever() is blocked in, would deadlock. Run it on
        # its own thread instead.
        stop_requested.append(signum)
        threading.Thread(target=server.shutdown, daemon=True).start()

    previous_term = signal.signal(signal.SIGTERM, _handle_stop)
    previous_int = signal.signal(signal.SIGINT, _handle_stop)
    try:
        if ready_callback:
            ready_callback(server)
        server.serve_forever(poll_interval=0.2)
    finally:
        signal.signal(signal.SIGTERM, previous_term)
        signal.signal(signal.SIGINT, previous_int)
        for poller in pollers:
            poller.stop()
        server.server_close()
    return 0


def main(argv=None):
    from cockpit.core.config import Config

    config = Config()
    return run_foreground(config)


if __name__ == "__main__":
    sys.exit(main())
