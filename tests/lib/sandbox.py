"""Shared sandbox harness (P10, af-ygibh) -- Python counterpart to
tests/lib/sandbox.sh. See that file's header for the incidents (af-ize6u,
and an orphaned tmux server that held the live escalation-door flock for
40+ min, root-caused 2026-09-28) this exists to stop happening again.

Usage (tests run standalone as `python3 tests/foo-test.py`, so this is a
plain module on a path-inserted directory, not a package import):

    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "lib"))
    from sandbox import Sandbox

    with Sandbox() as sb:
        subprocess.run(["gc", "bd", "list"], env=sb.env, ...)   # fake gc

    with Sandbox(real_gc=True) as sb:
        subprocess.run(["gc", "--city", sb.city, "bd", "list"], env=sb.env)

A test that opts into real_gc=True must still never point a gc/bd call at
anything but sb.city -- opting in is for testing real gc/bd behavior against
a disposable city, not for reaching the live one.
"""
import os
import pathlib
import shutil
import subprocess
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
FIXTURES = ROOT / "tests" / "fixtures"

_LEAK_ENV = (
    "GC_DOLT_HOST", "GC_DOLT_PORT", "GC_DOLT_DATABASE", "GC_DOLT_PROJECT_ID", "GC_DOLT_USER",
    "GC_SESSION_ID", "GC_SESSION_NAME", "GC_ALIAS", "GC_AGENT",
    "GC_BEAD_ID", "GC_ROOT_BEAD_ID", "GC_CONTINUATION_GROUP",
    "GC_CITY_RUNTIME_DIR", "GC_DIR",
    "GC_TRIGGER_BEAD_ID", "GC_TRIGGER_WORK_BEAD_ID",
    "GC_TRIGGER_BEAD_STORE_REF", "GC_TRIGGER_WORK_STORE_REF",
)


class Sandbox:
    def __init__(self, real_gc=False):
        self.real_gc = real_gc
        self.dir = pathlib.Path(tempfile.mkdtemp(prefix="af-sandbox."))
        self.city = self.dir / "city"
        self.home = self.dir / "home"
        self.tmux_dir = self.dir / "tmux"
        self.stub_bin = self.dir / "stubbin"
        for p in (self.city, self.home, self.tmux_dir, self.stub_bin):
            p.mkdir(parents=True, exist_ok=True)

        fakes = ("codex", "claude") if real_gc else ("gc", "bd", "gh", "codex", "claude")
        for name in fakes:
            src = FIXTURES / ("fake-%s.py" % name)
            dst = self.stub_bin / name
            shutil.copy(src, dst)
            dst.chmod(0o755)

        env = dict(os.environ)
        for key in _LEAK_ENV:
            env.pop(key, None)
        env["HOME"] = str(self.home)
        env["TMUX_TMPDIR"] = str(self.tmux_dir)
        env["GC_CITY"] = str(self.city)
        env["GC_CITY_PATH"] = str(self.city)
        env["GC_BEADS_SCOPE_ROOT"] = str(self.city)
        env["PATH"] = str(self.stub_bin) + os.pathsep + env.get("PATH", "")
        self.env = env

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.cleanup()
        return False

    def cleanup(self):
        for sock_dir in self.tmux_dir.glob("tmux-*"):
            for sock in sock_dir.glob("*"):
                subprocess.run(["tmux", "-S", str(sock), "kill-server"],
                                capture_output=True)
        subprocess.run(["pkill", "-f", "--", str(self.dir)], capture_output=True)
        for _ in range(10):
            found = subprocess.run(["pgrep", "-f", "--", str(self.dir)],
                                    capture_output=True)
            if found.returncode != 0:
                break
            time.sleep(0.3)
        subprocess.run(["pkill", "-9", "-f", "--", str(self.dir)], capture_output=True)
        if os.environ.get("KEEP_SANDBOX") == "1":
            print("sandbox preserved at %s" % self.dir)
        else:
            shutil.rmtree(self.dir, ignore_errors=True)
