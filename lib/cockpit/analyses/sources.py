"""The two sources the Analyses read besides the requests: the records of
the delivery flow and what GitHub answers for the declared repository.

- ``read_flow``: every bead the delivery flow marked (``gc.flow.mark``,
  docs/CONVOY_STATE.md), whatever its status: a convoy carries the delivery
  of its result, Benjamin's judgement and the proof of its merge
  (``gc.flow.delivered``, ``gc.flow.judgement``, ``gc.flow.promotion``), a
  ticket its dispatch and its merge into the integration branch
  (``gc.flow.gate.dispatch``, ``gc.flow.merge``);
- ``read_github``: the workflow runs of the repository created since a
  day, and its last closed pull requests, as the GitHub REST API answers
  them through ``gh api``.

Nothing is collected for the cockpit alone: both are read where the flow
and GitHub already write them.
"""
import json
import subprocess
from datetime import datetime, timezone

from cockpit.core.beads_source import read_beads_json

MARK = "gc.flow.mark"
READ_TIMEOUT_SECONDS = 20
# One page of the REST API: the runs of the last days and the last closed
# pull requests of a solo repository fit in it; the method says so.
PAGE = 100


class GithubUnreadable(RuntimeError):
    """GitHub did not answer what the Analyses read."""


def read_flow(bd_bin="bd", timeout=READ_TIMEOUT_SECONDS):
    """The convoys and tickets the delivery flow marked, closed ones too."""
    beads = read_beads_json(["list", "--all", "--limit", "0", "--has-metadata-key", MARK], bd_bin=bd_bin,
                            timeout=timeout)
    return [bead for bead in beads if isinstance(bead, dict)]


def read_github(gh_bin, repository, since, timeout=READ_TIMEOUT_SECONDS):
    """``{"repository", "workflow_runs", "pull_requests"}``: the workflow runs
    of ``repository`` created since the epoch ``since``, and its last closed
    pull requests. Raises GithubUnreadable when GitHub does not answer, or
    answers something else."""
    day = datetime.fromtimestamp(since, tz=timezone.utc).strftime("%Y-%m-%d")
    runs = _api(gh_bin, timeout, "repos/%s/actions/runs" % repository, per_page=PAGE, created=">=" + day)
    pulls = _api(gh_bin, timeout, "repos/%s/pulls" % repository, state="closed", per_page=PAGE, sort="updated",
                 direction="desc")
    if not isinstance(runs, dict) or not isinstance(runs.get("workflow_runs"), list) or not isinstance(pulls, list):
        raise GithubUnreadable("GitHub a répondu sans les exécutions ou les PR attendues")
    return {"repository": repository, "workflow_runs": runs["workflow_runs"], "pull_requests": pulls}


def _api(gh_bin, timeout, path, **fields):
    argv = [gh_bin, "api", "-X", "GET", path]
    for name, value in fields.items():
        argv += ["-f", "%s=%s" % (name, value)]
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=True)
        return json.loads(completed.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise GithubUnreadable("GitHub n’a pas répondu") from exc
