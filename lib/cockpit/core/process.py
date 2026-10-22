"""Wires the read model, the sources, and the HTTP server into one process.

``run_foreground`` is what ``bin/cockpit run`` calls: it blocks until
SIGTERM/SIGINT, then frees the port, asks every poller to end and returns
within ``SHUTDOWN_BUDGET_SECONDS`` (see ``shut_down``). A source going
quiet (gc suspended, city stopped) never raises out of here — see the
individual pollers.
"""
import os
import signal
import sys
import threading
import time
from datetime import datetime

from cockpit.access.guard import ActionGuard, new_session_token
from cockpit.actions.registry import build_action_handlers
from cockpit.core.beads_source import read_operator_beads
from cockpit.core.clock import ShiftedClock, SystemClock
from cockpit.core.freshness import UNKNOWN
from cockpit.core.gc_client import GcSsePoller
from cockpit.core.polling_source import PollingSource
from cockpit.core.readmodel import ReadModel
from cockpit.core.server import make_server
from cockpit.health.git_source import count_commits_behind
from cockpit.access.tailscale import build_key_expiry_request, key_expiry_epoch, read_status
from cockpit.notify.service import HeartbeatService, NotifyService, Ticker
from cockpit.notify.state_store import JsonFileStateStore
from cockpit.stop.driver import StopDriver
from cockpit.stop.gc_city import GcCityReader
from cockpit.projects.depots import read_depots, read_rig_repos
from cockpit.projects.descriptors import load_descriptors
from cockpit.projects.source import READ_TIMEOUT_SECONDS as PROJECTS_READ_TIMEOUT_SECONDS, read_projects
from cockpit.requests.assemble import assemble_from_snapshot
from cockpit.requests.defects import DefectCounter
from cockpit.requests.journal import read_journal
from cockpit.runs.workflows import read_workflow_beads

# github/rituals sources are in the Validity window table (spec .3) for the
# tickets that will wire up their producers; T11 builds the seam and wires
# only the two sources it has fakes for (gc, beads) so headline/AC3 can
# reach "tout est à jour" without depending on unbuilt producers. T16 adds
# "git" for the health zone's version-behind signal (spec .66) the same
# way, opt-in via config.repo_dir (see Config.repo_dir).
SOURCE_DISPLAY_NAMES = {
    "gc": "superviseur",
    "beads": "tickets",
}

# How long a stopping process waits for reads and ticks in flight, all of
# them together. `bin/cockpit stop` waits longer than this before it kills.
SHUTDOWN_BUDGET_SECONDS = 5.0


def build(config, clock=None):
    """Returns (server, pollers) — nothing is started yet."""
    if clock is None and config.clock_start:
        clock = ShiftedClock(datetime.fromisoformat(config.clock_start).timestamp())
    clock = clock or SystemClock()
    read_model = ReadModel(clock, validity_seconds=config.validity_seconds)
    for name, display_name in SOURCE_DISPLAY_NAMES.items():
        read_model.register(name, display_name=display_name)

    pollers = [
        GcSsePoller(
            read_model,
            config.gc_base_url,
            city=config.gc_city,
            status_poll_seconds=config.gc_status_poll_seconds,
            stream_silence_seconds=config.gc_stream_silence_seconds,
            reconnect_seconds=config.gc_reconnect_seconds,
        )
    ]
    if config.bd_bin:
        pollers.append(
            PollingSource(
                read_model,
                "beads",
                lambda: read_operator_beads(bd_bin=config.bd_bin, timeout=config.beads_read_timeout_seconds),
                config.beads_poll_seconds,
            )
        )
        read_model.register("projets", display_name="projets")
        pollers.append(
            PollingSource(
                read_model,
                "projets",
                lambda: read_projects(
                    config.descriptors_dir,
                    bd_bin=config.bd_bin,
                    timeout=max(PROJECTS_READ_TIMEOUT_SECONDS, config.beads_read_timeout_seconds),
                    clones_dir=config.clones_dir,
                    rig_repos=read_rig_repos(config.rig_files_dir),
                    git_bin=config.git_bin,
                ),
                config.projects_poll_seconds,
            )
        )
        read_model.register("journal", display_name="journal")
        pollers.append(
            PollingSource(
                read_model,
                "journal",
                lambda: read_journal(bd_bin=config.bd_bin),
                config.journal_poll_seconds,
            )
        )
        read_model.register("runs", display_name="runs")
        pollers.append(PollingSource(read_model, "runs", lambda: read_workflow_beads(bd_bin=config.bd_bin),
                                     config.journal_poll_seconds))
    if config.repo_dir:
        read_model.register("git", display_name="version de l'usine")
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
        illisible_after_seconds=config.illisible_after_seconds,
        factory_root=config.factory_root,
        factory_check_validity_seconds=config.factory_check_validity_seconds,
    )
    server.runs_view = config.runs_view
    server.descriptors_dir = config.descriptors_dir

    # Clean stop (T23, T24) -- read side only (af-mjfvwx 7a): the driver keeps
    # its state and its tick; the reader it is handed cannot suspend, resume
    # or stop anything, and no stop action is registered.
    def held_work():
        """``{session_id: ticket id}`` as the tickets record it; ``None``
        while the tickets are not read."""
        row = read_model.snapshot().get("beads")
        if row is None or row["value"] is None or row["freshness"] == UNKNOWN:
            return None
        held = {}
        for bead in row["value"]:
            if not isinstance(bead, dict) or bead.get("status") != "in_progress":
                continue
            session_id = (bead.get("metadata") or {}).get("gc.session_id")
            if session_id and bead.get("id"):
                held[session_id] = bead["id"]
        return held

    city_reader = GcCityReader(config.gc_base_url, city=config.gc_city, held_work=held_work)
    read_model.register("sessions", display_name="agents au travail")
    pollers.append(PollingSource(read_model, "sessions", city_reader.status, config.sessions_poll_seconds))

    def photo():
        """The driver's « photo »: every non-closed ticket and who holds it."""
        beads = (read_model.snapshot().get("beads") or {}).get("value") or []
        return {
            "beads": {
                # Who holds a ticket is the session the factory recorded on it;
                # a delivery ticket has no assignee field of its own.
                b["id"]: {
                    "status": b.get("status"),
                    "assignee": (b.get("metadata") or {}).get("gc.session_name") or b.get("assignee"),
                }
                for b in beads
                if isinstance(b, dict) and b.get("id")
            }
        }

    stop_driver = StopDriver(city_reader, photo, clock, JsonFileStateStore(config.stop_state_file))
    pollers.append(Ticker(stop_driver.tick, config.stop_tick_seconds))

    # Project repositories (T19, T20): roadmap step and commits ahead, read in
    # clones the cockpit owns -- only where a clones directory is named.
    if config.clones_dir:
        read_model.register("depots", display_name="dépôts des projets")
        pollers.append(
            PollingSource(
                read_model,
                "depots",
                lambda: read_depots(
                    load_descriptors(config.descriptors_dir),
                    read_rig_repos(config.rig_files_dir),
                    config.clones_dir,
                    url_template=config.repo_url_template,
                    git_bin=config.git_bin,
                ),
                config.depots_poll_seconds,
            )
        )

    # Access (T25): the Tailscale key's expiry, only where a client is named.
    if config.tailscale_bin:
        read_model.register("tailscale", display_name="accès Tailscale")

        def read_tailscale():
            status = read_status(tailscale_bin=config.tailscale_bin)
            if status is None:
                raise ValueError("tailscale ne répond pas")
            return {"key_expiry": key_expiry_epoch(status), "backend_state": status.get("BackendState")}

        pollers.append(PollingSource(read_model, "tailscale", read_tailscale, config.tailscale_poll_seconds))

    def extra_requests(snapshot, now):
        """Requests the cockpit's own parts raise (spec: « l'arrêt n'avance
        plus », « reprise avec écarts », clé Tailscale à J-14)."""
        requests = list(stop_driver.pending_requests())
        tailscale = snapshot.get("tailscale")
        if tailscale is not None and tailscale["value"] is not None and tailscale["freshness"] != UNKNOWN:
            request = build_key_expiry_request(tailscale["value"]["key_expiry"], now)
            if request is not None:
                requests.append(request)
        return requests

    server.stop_driver = stop_driver
    server.benjamin_login = config.benjamin_login
    server.rituals_file = config.rituals_file
    server.extra_requests = extra_requests

    # Notifications and heartbeat (T17, T18): each a policy with tick() as
    # its interface, ticked here on its own thread.
    notify_defects = DefectCounter()  # its own: the page's count is the page's

    def current_requests():
        snapshot = read_model.snapshot()
        now = read_model.now()
        requests, _, beads_known = assemble_from_snapshot(
            snapshot, now, notify_defects, config.illisible_after_seconds,
            extra_requests=extra_requests(snapshot, now),
        )
        # Whole only once the projects are read too: a push names its
        # project as the page does.
        projets = snapshot.get("projets")
        return requests, beads_known and (projets is None or projets["freshness"] != UNKNOWN)

    notify = NotifyService(
        config.pushover_secrets_file,
        config.notify_state_file,
        clock,
        config.public_url,
        current_requests,
        pushover_url=config.pushover_url,
    )
    heartbeat = HeartbeatService(
        read_model, clock, config.heartbeat_url_file, config.heartbeat_interval_seconds,
        state_provider=stop_driver.state,
    )
    server.notify = notify
    server.heartbeat = heartbeat
    server.action_handlers["notifier_test"] = lambda payload: notify.send_test()
    pollers.append(Ticker(notify.tick, config.notify_tick_seconds))
    pollers.append(Ticker(heartbeat.tick, config.heartbeat_tick_seconds))
    return server, pollers


def shut_down(server, pollers, budget_seconds=SHUTDOWN_BUDGET_SECONDS, log=None):
    """Ends a cockpit that has stopped serving.

    The port first: the next process may need it at once. Then every poller
    is asked to end before any is waited for, and all of them share one
    budget -- waited for one after the other, 5 s each, eleven of them could
    hold a stopping process (and its port) for most of a minute. They are
    daemon threads reading sources: one still busy when the budget runs out
    ends with the process, and is named in the log."""
    log = log or sys.stderr
    started = time.monotonic()
    server.server_close()
    for poller in pollers:
        poller.request_stop()
    deadline = started + budget_seconds
    late = [
        getattr(poller, "source", None) or type(poller).__name__
        for poller in pollers
        if not poller.join(deadline - time.monotonic())
    ]
    print(
        "cockpit: stopped in %.1fs%s"
        % (time.monotonic() - started, " without waiting for: " + ", ".join(late) if late else ""),
        file=log,
        flush=True,
    )


def _wait_first_readings(read_model, seconds):
    """Until each source was read once, or failed, or ``seconds`` passed:
    the isolated cockpit answers its first page with what its sources
    hold, not with a reading under way (``seconds`` 0 in service: the
    cockpit answers at once)."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        rows = read_model.snapshot().values()
        if all(row["read_at"] is not None or row["failed_at"] is not None for row in rows):
            return
        time.sleep(0.1)


def run_foreground(config, clock=None, ready_callback=None):
    server, pollers = build(config, clock=clock)
    print("cockpit: pid %d listening since %s" % (os.getpid(), time.strftime("%Y-%m-%d %H:%M:%S%z")),
          file=sys.stderr, flush=True)
    for poller in pollers:
        poller.start()
    _wait_first_readings(server.read_model, config.first_read_seconds)

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
        print("cockpit: stopping at %s" % time.strftime("%Y-%m-%d %H:%M:%S%z"), file=sys.stderr, flush=True)
        shut_down(server, pollers)
    return 0


def main(argv=None):
    from cockpit.core.config import Config

    config = Config()
    return run_foreground(config)


if __name__ == "__main__":
    sys.exit(main())
