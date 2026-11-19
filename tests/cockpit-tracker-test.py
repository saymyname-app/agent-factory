"""The cockpit's one reader of Beads (af-q55qqx.9).

On 19/11/2026 the running cockpit kept seven to ten ``bd list`` at once and
starved Dolt, itself and the Factory. These tests hold what replaced its
four pollers: one ``bd`` at a time whatever the pages and gestures ask, a
page that never runs ``bd``, requests made together served by one cycle,
the history read once in slices then incrementally, and every derived
value dated by the oldest read it was made from.
"""
import json
import os
import socket
import stat
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from cockpit.core.clock import SystemClock  # noqa: E402
from cockpit.core.readmodel import ReadModel  # noqa: E402
from cockpit.core.tracker import RETRY_SECONDS, TrackerReader, TrackerSnapshot  # noqa: E402

VALIDITY = {"beads": 300, "projets": 300, "journal": 300, "runs": 300}


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def now(self):
        return self.t


class FakeRead:
    """``read_beads_json`` as the reader calls it: records each call and how
    many ran at once."""

    def __init__(self, delay=0.0):
        self.calls = []
        self.delay = delay
        self.fail = False
        self.running = 0
        self.max_running = 0
        self.lock = threading.Lock()
        self.open = [{"id": "af-1", "status": "open", "metadata": {}}]
        self.flagged = [{"id": "af-2", "status": "closed", "metadata": {"gc.needs_benjamin": "q"}}]
        self.history = [{"id": "af-3", "status": "closed", "metadata": {"gc.graph_digest": "d"}}]
        self.changed = []

    def __call__(self, args, bd_bin="bd", timeout=0):
        with self.lock:
            self.running += 1
            self.max_running = max(self.max_running, self.running)
            self.calls.append(list(args))
        try:
            if self.delay:
                time.sleep(self.delay)
            if self.fail:
                raise RuntimeError("bd down")
            if args == ["list"]:
                return list(self.open)
            if "--has-metadata-key" in args and "gc.needs_benjamin" in args:
                return list(self.flagged)
            if "--updated-before" in args:
                if getattr(self, "fail_slices", False):
                    raise RuntimeError("i/o timeout")
                return list(self.history)
            if "--updated-after" in args and "--include-ephemeral" not in args:
                return list(self.changed)
            if "--updated-after" in args:
                return []
            return []
        finally:
            with self.lock:
                self.running -= 1


def reader_with(fake, clock=None, **kw):
    clock = clock or FakeClock()
    model = ReadModel(clock, validity_seconds=VALIDITY)
    for name in VALIDITY:
        model.register(name)
    reader = TrackerReader(model, read=fake, history_days=6, slice_days=3, **kw)
    sources = {
        "beads": reader.add("beads", lambda t: [b["id"] for b in t.open() + t.flagged()]),
        "projets": reader.add("projets", lambda t: sorted(b["id"] for b in t.with_key("gc.graph_digest")),
                              history=True),
    }
    return reader, model, sources, clock


class TrackerReaderTest(unittest.TestCase):
    def test_a_cycle_reads_the_open_beads_then_the_history_in_slices_then_incrementally(self):
        fake = FakeRead()
        reader, model, sources, _ = reader_with(fake)
        reader._cycle([])
        self.assertTrue(reader.results["beads"])
        self.assertEqual(fake.calls[0], ["list"])
        self.assertIn("gc.needs_benjamin", fake.calls[1])
        slices = [c for c in fake.calls if "--updated-before" in c]
        self.assertEqual(len(slices), 1, "one slice per cycle, the open reads keep their rhythm")
        # Until the history is whole, a view that needs it is not published.
        self.assertIsNone(model.snapshot()["projets"]["read_at"])
        reader._cycle([])  # second slice
        reader._cycle([])  # the first incremental read, then the views
        self.assertEqual(len([c for c in fake.calls if "--updated-before" in c]), 2)
        incremental = [c for c in fake.calls if "--updated-after" in c and "--updated-before" not in c]
        self.assertEqual(len(incremental), 2, "one read of what changed, one of the ended sessions")
        self.assertEqual(model.snapshot()["projets"]["value"], ["af-3"])
        self.assertEqual(model.snapshot()["beads"]["value"], ["af-1", "af-2"])
        # The reads by metadata key over the whole history ran into Dolt's
        # own timeout on 19/11/2026: only the open question is read so.
        keyed = [c for c in fake.calls
                 if "--has-metadata-key" in c and "gc.needs_benjamin" not in c and "--updated-after" not in c]
        self.assertEqual(keyed, [])

    def test_no_more_than_one_bd_at_a_time_whatever_the_pages_ask(self):
        fake = FakeRead(delay=0.02)
        reader, model, sources, _ = reader_with(fake, open_seconds=0.05, history_seconds=0.05)
        sources["beads"].start()
        try:
            asked = [threading.Thread(target=sources[name].poll_now) for name in ("beads", "projets") * 10]
            for thread in asked:
                thread.start()
            for thread in asked:
                thread.join(10)
            time.sleep(0.3)
        finally:
            sources["beads"].request_stop()
            self.assertTrue(sources["beads"].join(5))
        self.assertGreater(len(fake.calls), 4)
        self.assertEqual(fake.max_running, 1)

    def test_requests_made_together_share_one_cycle(self):
        fake = FakeRead(delay=0.05)
        reader, model, sources, _ = reader_with(fake, open_seconds=3600, history_seconds=3600)
        sources["beads"].start()
        try:
            time.sleep(0.6)  # the first cycles: open reads, slices, history
            before = fake.calls.count(["list"])
            asked = [threading.Thread(target=sources["beads"].poll_now) for _ in range(12)]
            for thread in asked:
                thread.start()
            for thread in asked:
                thread.join(10)
            # « revérifier » asks every source in turn: served by the same cycle.
            self.assertTrue(sources["projets"].poll_now())
        finally:
            sources["beads"].request_stop()
            sources["beads"].join(5)
        self.assertLessEqual(fake.calls.count(["list"]) - before, 2)

    def test_a_cycle_asked_before_the_history_is_whole_publishes_every_view(self):
        # The re-read after an action (server: REREAD_AFTER_ACTION_SECONDS)
        # asks every view of Beads: one asked during the first reading of
        # the history must not come back without them.
        fake = FakeRead()
        reader, model, sources, _ = reader_with(fake, open_seconds=3600, history_seconds=3600)
        self.assertTrue(sources["projets"].poll_now())
        self.assertEqual(model.snapshot()["projets"]["value"], ["af-3"])

    def test_a_failed_read_is_said_and_asked_again_ever_less_often(self):
        fake = FakeRead()
        fake.fail = True
        mono = [0.0]
        reader, model, sources, _ = reader_with(fake, open_seconds=30, history_seconds=30, mono=lambda: mono[0])
        self.assertFalse(sources["beads"].poll_now())
        self.assertIsNotNone(model.snapshot()["beads"]["failed_at"])
        opens = []
        for _ in range(12):  # one second at a time
            mono[0] += 1
            reader._cycle([])
            opens.append(fake.calls.count(["list"]))
        # Asked again after 2 s, then 4 s, then 8 s: never every 2 s again.
        self.assertEqual([opens.index(n) + 1 for n in sorted(set(opens))][1:], [2, 6])
        self.assertEqual(reader._retry("open", 30), RETRY_SECONDS, "never longer than RETRY_SECONDS")

    def test_a_view_is_dated_by_the_oldest_read_it_was_made_from(self):
        fake = FakeRead()
        mono = [0.0]
        clock = FakeClock()
        reader, model, sources, _ = reader_with(fake, clock=clock, open_seconds=30, history_seconds=600,
                                                mono=lambda: mono[0])
        for _ in range(3):  # open reads, two slices, the history
            reader._cycle([None])
        history_read_at = model.snapshot()["projets"]["read_at"]
        mono[0] += 100
        clock.t += 100
        reader._cycle([None])  # fresh open reads only: the history is 100 s old
        snapshot = model.snapshot()
        self.assertEqual(snapshot["projets"]["read_at"], history_read_at)
        # The tickets too: who still asks Benjamin is known as of that history.
        self.assertEqual(snapshot["beads"]["read_at"], history_read_at)
        mono[0] += 600
        clock.t += 600
        reader._cycle([None])  # the open beads, the history, the beads asking Benjamin: all read now
        snapshot = model.snapshot()
        self.assertEqual(snapshot["beads"]["read_at"], clock.t)
        self.assertEqual(snapshot["projets"]["read_at"], clock.t)

    def test_a_view_whose_beads_did_not_change_is_dated_anew_not_derived_again(self):
        fake = FakeRead()
        mono = [0.0]
        clock = FakeClock()
        reader, model, sources, _ = reader_with(fake, clock=clock, mono=lambda: mono[0])
        derived = []
        reader.add("journal", lambda t: derived.append(1) or len(derived), history=True)
        for _ in range(3):
            reader._cycle([None])
        self.assertEqual(len(derived), 1, "derived once per cycle, not once per read")
        mono[0] += 100
        clock.t += 100
        reader._cycle([None])
        self.assertEqual(len(derived), 1)
        self.assertEqual(model.snapshot()["journal"]["read_at"], clock.t - 100,
                         "the history it comes from was read 100 s ago")
        fake.open = fake.open + [{"id": "af-9", "status": "open", "metadata": {}}]
        reader._cycle([None])
        self.assertEqual(len(derived), 2)

    def test_the_beads_asking_benjamin_are_read_whole_seldom_and_kept_current_by_the_history(self):
        # The read of every bead carrying gc.needs_benjamin took 22 s on
        # 19/11/2026: once every cycle, it kept a bd running at all times.
        fake = FakeRead()
        mono = [0.0]
        reader, model, sources, _ = reader_with(fake, open_seconds=30, history_seconds=120, flagged_seconds=600,
                                                mono=lambda: mono[0])
        flagged = lambda: sum(1 for c in fake.calls if "gc.needs_benjamin" in c)  # noqa: E731
        for _ in range(4):
            reader._cycle([])
        self.assertEqual(flagged(), 1)
        self.assertEqual(model.snapshot()["beads"]["value"], ["af-1", "af-2"])
        # Benjamin answered af-2 (the key leaves it), a new question on af-7:
        # both written, so both read again by the history.
        fake.changed = [{"id": "af-2", "status": "closed", "metadata": {}, "updated_at": "2026-11-19T12:00:00Z"},
                        {"id": "af-7", "status": "closed", "metadata": {"gc.needs_benjamin": "q"},
                         "updated_at": "2026-11-19T12:00:00Z"}]
        for _ in range(10):  # five minutes
            mono[0] += 30
            reader._cycle([])
        self.assertEqual(flagged(), 1, "not read whole again before its rhythm")
        self.assertEqual(model.snapshot()["beads"]["value"], ["af-1", "af-7"])
        mono[0] += 600
        reader._cycle([])
        self.assertEqual(flagged(), 2)

    def test_the_tickets_are_read_again_while_a_long_first_history_reading_goes_on(self):
        # 19/11/2026: the first reading of the history took 11 min under
        # load; the tickets must not wait for all of it.
        fake = FakeRead()
        fake.fail_slices = True
        mono = [0.0]
        reader, model, sources, _ = reader_with(fake, open_seconds=30, mono=lambda: mono[0])
        for _ in range(10):
            reader._cycle([])
            mono[0] += 30
        self.assertGreaterEqual(fake.calls.count(["list"]), 4)
        self.assertEqual(model.snapshot()["beads"]["read_at"] is None, False)

    def test_the_tickets_stay_current_while_a_long_first_history_reading_goes_on(self):
        fake = FakeRead()
        fake.fail_slices = True
        mono = [0.0]
        clock = FakeClock()
        reader, model, sources, _ = reader_with(fake, clock=clock, open_seconds=30, flagged_seconds=600,
                                                mono=lambda: mono[0])
        for _ in range(20):  # ten minutes without a whole history
            reader._cycle([])
            mono[0] += 30
            clock.t += 30
        self.assertLessEqual(clock.t - model.snapshot()["beads"]["read_at"], 90,
                             "the tickets are dated by a read of the beads asking Benjamin minutes old")

    def test_the_ended_sessions_are_read_on_the_rhythm_of_the_beads_asking_benjamin(self):
        fake = FakeRead()
        mono = [0.0]
        reader, model, sources, _ = reader_with(fake, history_seconds=120, flagged_seconds=600, mono=lambda: mono[0])
        sessions = lambda: sum(1 for c in fake.calls if "--include-ephemeral" in c)  # noqa: E731
        for _ in range(4):
            reader._cycle([])
        self.assertEqual(sessions(), 1)
        for _ in range(4):  # eight minutes: four readings of the history
            mono[0] += 120
            reader._cycle([])
        self.assertEqual(sessions(), 1)
        mono[0] += 120
        reader._cycle([])
        self.assertEqual(sessions(), 2)

    def test_the_freshest_copy_of_a_bead_wins(self):
        snapshot = TrackerSnapshot(
            [{"id": "a", "status": "open", "metadata": {"k": "new"}}], [],
            {"a": {"id": "a", "status": "open", "metadata": {"k": "old"}},
             "b": {"id": "b", "status": "closed", "metadata": {"k": "x"}}},
            {"s": {"id": "s", "issue_type": "session", "metadata": {"k": "y"}}})
        self.assertEqual({b["id"]: b["metadata"]["k"] for b in snapshot.with_key("k")}, {"a": "new", "b": "x"})
        self.assertEqual(len(snapshot.with_key("k", ephemeral=True)), 3)


FAKE_BD = r'''#!/usr/bin/env python3
"""bd that sleeps, and records any call made while another runs."""
import json, os, sys, time
state = os.environ["FAKE_BD_DIR"]
lock = os.path.join(state, "running")
try:
    os.mkdir(lock)
except FileExistsError:
    open(os.path.join(state, "overlap"), "a").write(" ".join(sys.argv[1:]) + "\n")
    lock = None
try:
    open(os.path.join(state, "calls"), "a").write(" ".join(sys.argv[1:]) + "\n")
    time.sleep(0.05)
    print("[]")
finally:
    if lock:
        os.rmdir(lock)
'''


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TrackerProcessTest(unittest.TestCase):
    """The cockpit as it runs: its pages loaded side by side never start a
    second ``bd``."""

    def test_pages_loaded_together_never_run_two_bd_at_once(self):
        from cockpit.core.config import Config
        from cockpit.core.process import build, shut_down

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bd = tmp / "bd"
            bd.write_text(FAKE_BD)
            bd.chmod(bd.stat().st_mode | stat.S_IEXEC)
            (tmp / "descriptors").mkdir()
            port = free_port()
            env = {
                "FAKE_BD_DIR": str(tmp), "COCKPIT_BD_BIN": str(bd), "COCKPIT_PORT": str(port),
                "COCKPIT_GC_BASE_URL": "http://127.0.0.1:%d" % free_port(), "COCKPIT_HOME": str(tmp),
                "COCKPIT_PID_FILE": str(tmp / "cockpit.pid"), "COCKPIT_DESCRIPTORS_DIR": str(tmp / "descriptors"),
                "COCKPIT_BEADS_POLL_SECONDS": "0.1", "COCKPIT_TRACKER_HISTORY_SECONDS": "0.1",
                "COCKPIT_TRACE_FILE": str(tmp / "trace.jsonl"), "EVIDENCE_STORE_DIR": str(tmp / "evidence"),
                "COCKPIT_STOP_STATE_FILE": str(tmp / "stop.json"), "COCKPIT_NOTIFY_STATE_FILE": str(tmp / "n.json"),
                "COCKPIT_ESSAI_PORT": "0", "PATH": os.environ.get("PATH", ""),
            }
            os.environ["FAKE_BD_DIR"] = str(tmp)
            server, pollers = build(Config(env), clock=SystemClock())
            serving = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
            try:
                for poller in pollers:
                    poller.start()
                serving.start()
                pages = ["/", "/projets", "/journal", "/analyses", "/api/status", "/api/journal"] * 4

                def load(path):
                    try:
                        urllib.request.urlopen("http://127.0.0.1:%d%s" % (port, path), timeout=20).read()
                    except Exception:
                        pass

                loads = [threading.Thread(target=load, args=(p,)) for p in pages]
                loads += [threading.Thread(target=p.poll_now) for p in pollers
                          if getattr(p, "source", None) in ("beads", "projets", "journal", "runs")]
                for thread in loads:
                    thread.start()
                for thread in loads:
                    thread.join(30)
                time.sleep(1.0)
            finally:
                server.shutdown()
                shut_down(server, pollers)
            calls = (tmp / "calls").read_text().splitlines()
            self.assertGreater(len(calls), 5)
            self.assertFalse((tmp / "overlap").exists(),
                             "two bd at once: %s" % ((tmp / "overlap").read_text() if (tmp / "overlap").exists() else ""))
            self.assertFalse([c for c in calls if "--has-metadata-key" in c and "--updated-after" not in c
                              and "gc.needs_benjamin" not in c], "a keyed read of the whole history")


if __name__ == "__main__":
    unittest.main()
