"""Materialise the Delivery Fixture City's Validated Prototype on its
prototype branch (T07, af-tvda3w).

A Validated Prototype lives on a prototype branch that is never merged
(spec af-wf4w5r section 3), and `bin/spec-approve` reads it from the remote
repository at the commit the Spec names. The fixture's frozen prototype is
tracked under tests/fixtures/delivery-fixture-city/prototype/ so CI has it;
`materialize` turns that directory into one orphan commit on the branch
`prototype/delivery-fixture-city` of a bare repository a test uses as the
remote. Identity and dates are fixed, so the same files always give the same
commit: FROZEN_COMMIT is the one the fixture Spec names.

Usage (plain module on a path-inserted directory, like sandbox.py):

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "lib"))
    from fixture_prototype import materialize

    commit = materialize(tmp / "remote.git")
"""
import os
import pathlib
import shutil
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
PROTOTYPE_PATH = "tests/fixtures/delivery-fixture-city/prototype"
PROTOTYPE_SOURCE = ROOT / PROTOTYPE_PATH
BRANCH = "prototype/delivery-fixture-city"
FROZEN_COMMIT = "dfdd34f50623661f6644524b6489342cdbbdee19"

_FIXED_DATE = "2026-01-01T00:00:00+00:00"


def _git(cwd, *args):
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(cwd),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_AUTHOR_NAME": "Delivery Fixture City",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_AUTHOR_DATE": _FIXED_DATE,
        "GIT_COMMITTER_NAME": "Delivery Fixture City",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_DATE": _FIXED_DATE,
    }
    return subprocess.run(
        ("git", *args), cwd=cwd, env=env, text=True, capture_output=True, check=True,
    ).stdout.strip()


def materialize(remote, source=PROTOTYPE_SOURCE):
    """Create (or extend) the bare repository `remote` with BRANCH holding
    `source` at PROTOTYPE_PATH as one orphan commit; return that commit."""
    remote = pathlib.Path(remote)
    if not remote.exists():
        remote.mkdir(parents=True)
        _git(remote, "init", "--quiet", "--bare", "--object-format=sha1", ".")
    work = pathlib.Path(tempfile.mkdtemp(prefix="fixture-prototype-"))
    try:
        _git(work, "init", "--quiet", "--object-format=sha1", ".")
        _git(work, "config", "core.autocrlf", "false")
        _git(work, "config", "core.fileMode", "false")
        _git(work, "checkout", "--quiet", "--orphan", BRANCH)
        target = work / PROTOTYPE_PATH
        target.parent.mkdir(parents=True)
        shutil.copytree(source, target)
        for path in sorted(target.rglob("*")):
            if path.is_file():
                _git(
                    work, "update-index", "--add", "--cacheinfo",
                    "100644," + _git(work, "hash-object", "-w", str(path)) + "," + path.relative_to(work).as_posix(),
                )
        _git(work, "commit", "--quiet", "-m", "Validated Prototype: Delivery Fixture City")
        commit = _git(work, "rev-parse", "HEAD")
        _git(work, "push", "--quiet", "--force", str(remote), f"HEAD:refs/heads/{BRANCH}")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return commit


if __name__ == "__main__":
    import sys

    print(materialize(sys.argv[1]))
