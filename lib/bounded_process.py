"""Run a command in its own process group and kill the group on timeout, or
when the caller dies first.

The group is a session of its own, so the caller can kill it whole at its
deadline. That same session survived the caller: on 10/11/2026 the order
convoy-advance killed its pass at 90 min, and the Cockpit regression that
pass had started ran on alone, wrote a green piece four minutes later and no
merge was recorded (af-8cfygl). A guard now watches each group: a small
shell, in a session of its own, reading a pipe whose only writer is the
caller. The caller writes « done » when it lets the group go; if the pipe
closes without it, the caller is gone however it ended (SIGKILL included)
and the guard kills the group.
"""
from __future__ import annotations

import os
import signal
import subprocess
from typing import Any

# $1 is the group. A line other than « done », or end of file, kills it.
# No `--` before the group: dash (/bin/sh on Ubuntu) refuses it.
GUARD_SCRIPT = 'IFS= read -r line; [ "$line" = done ] || kill -KILL "-$1" 2>/dev/null'
GUARD_NAME = "bounded-process-guard"


def _kill_group(process: subprocess.Popen[Any]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def guard(process: subprocess.Popen[Any]) -> None:
    """Tie the group of `process` (a session leader) to the life of the
    caller, until `release(process)`."""
    read_end, write_end = os.pipe()
    try:
        watcher = subprocess.Popen(["/bin/sh", "-c", GUARD_SCRIPT, GUARD_NAME, str(process.pid)],
                                   stdin=read_end, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   start_new_session=True)
    except OSError:
        os.close(write_end)
        return
    finally:
        os.close(read_end)
    process.bounded_guard = (watcher, write_end)  # type: ignore[attr-defined]


def release(process: subprocess.Popen[Any]) -> None:
    """The caller lets the group go: its guard leaves without killing it."""
    held = getattr(process, "bounded_guard", None)
    if not held:
        return
    process.bounded_guard = None  # type: ignore[attr-defined]
    watcher, write_end = held
    try:
        os.write(write_end, b"done\n")
    except OSError:
        pass
    finally:
        os.close(write_end)
    try:
        watcher.wait(timeout=5)
    except subprocess.TimeoutExpired:
        watcher.kill()
        watcher.wait()


def popen(*popenargs: Any, **kwargs: Any) -> subprocess.Popen[Any]:
    """`subprocess.Popen` in a session of its own whose group dies with the
    caller. The caller kills the group when it is done with it (`kill_group`)
    or lets it go (`release`)."""
    kwargs["start_new_session"] = True
    process = subprocess.Popen(*popenargs, **kwargs)
    guard(process)
    return process


def kill_group(process: subprocess.Popen[Any]) -> None:
    """Kill the whole group of `process`, then drop its guard."""
    _kill_group(process)
    release(process)


def run(*popenargs: Any, input: Any = None, capture_output: bool = False,
        timeout: float | None = None, check: bool = False, **kwargs: Any) -> subprocess.CompletedProcess[Any]:
    """The ``subprocess.run`` contract, with one owned process group."""
    if input is not None:
        if kwargs.get("stdin") is not None:
            raise ValueError("stdin and input arguments may not both be used")
        kwargs["stdin"] = subprocess.PIPE
    if capture_output:
        if kwargs.get("stdout") is not None or kwargs.get("stderr") is not None:
            raise ValueError("stdout and stderr arguments may not be used with capture_output")
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE

    with popen(*popenargs, **kwargs) as process:
        try:
            stdout, stderr = process.communicate(input, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            kill_group(process)
            exc.stdout, exc.stderr = process.communicate()
            raise
        except BaseException:
            kill_group(process)
            process.wait()
            raise
        finally:
            release(process)
        returncode = process.poll()
        if check and returncode:
            raise subprocess.CalledProcessError(returncode, process.args, output=stdout, stderr=stderr)
    return subprocess.CompletedProcess(process.args, returncode, stdout, stderr)
