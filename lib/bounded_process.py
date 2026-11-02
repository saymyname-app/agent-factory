"""Run a command in its own process group and kill the group on timeout."""
from __future__ import annotations

import os
import signal
import subprocess
from typing import Any


def _kill_group(process: subprocess.Popen[Any]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


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
    kwargs["start_new_session"] = True

    with subprocess.Popen(*popenargs, **kwargs) as process:
        try:
            stdout, stderr = process.communicate(input, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            _kill_group(process)
            exc.stdout, exc.stderr = process.communicate()
            raise
        except BaseException:
            _kill_group(process)
            process.wait()
            raise
        returncode = process.poll()
        if check and returncode:
            raise subprocess.CalledProcessError(returncode, process.args, output=stdout, stderr=stderr)
    return subprocess.CompletedProcess(process.args, returncode, stdout, stderr)
