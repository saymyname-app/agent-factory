"""The two sources the Analyses read besides those the cockpit already reads
(the runs, the journal and the requests): the results whose merge the
delivery flow proved, and what GitHub answers for the declared repository.

- ``read_results``: every convoy the delivery flow marked (``gc.flow.mark``,
  docs/CONVOY_STATE.md) that carries the proof of its merge
  (``gc.flow.promotion``), whatever its status, with the delivery of its
  result and Benjamin's judgement (``gc.flow.delivered``,
  ``gc.flow.judgement``). No run nor entry of the journal holds them: a run
  is a ticket, and the journal its resolutions;
- ``read_github``: the workflow runs of the repository created since a
  day, and its pull requests closed since then, as the GitHub REST API
  answers them through ``gh api``, page after page.

Nothing is collected for the cockpit alone: both are read where the flow
and GitHub already write them.
"""
import json
import subprocess
from datetime import datetime, timezone

from cockpit.core.beads_source import read_beads_json

MARK = "gc.flow.mark"
PROMOTION = "gc.flow.promotion"
READ_TIMEOUT_SECONDS = 20
# The largest page the REST API gives; every page is read.
PAGE = 100
# A bound on the pages of one read, far above what a solo repository makes
# in eight days: past it, the read fails rather than count part of them.
MAX_PAGES = 50


class GithubUnreadable(RuntimeError):
    """GitHub did not answer what the Analyses read."""


def read_results(bd_bin="bd", timeout=READ_TIMEOUT_SECONDS):
    """The convoys whose merge the delivery flow proved, closed ones too."""
    beads = read_beads_json(["list", "--all", "--limit", "0", "--has-metadata-key", MARK], bd_bin=bd_bin,
                            timeout=timeout)
    return [bead for bead in beads if isinstance(bead, dict) and (bead.get("metadata") or {}).get(PROMOTION)]


def read_github(gh_bin, repository, since, timeout=READ_TIMEOUT_SECONDS):
    """``{"repository", "workflow_runs", "pull_requests"}``: every workflow
    run of ``repository`` created since the epoch ``since``, and every pull
    request of it closed since then. Raises GithubUnreadable when GitHub
    does not answer, or answers something else."""
    day = datetime.fromtimestamp(since, tz=timezone.utc).strftime("%Y-%m-%d")
    runs = []
    for page in range(1, MAX_PAGES + 1):
        answer = _api(gh_bin, timeout, "repos/%s/actions/runs" % repository, per_page=PAGE, page=page,
                      created=">=" + day)
        if not isinstance(answer, dict) or not isinstance(answer.get("workflow_runs"), list):
            raise GithubUnreadable("GitHub a répondu sans les exécutions attendues")
        runs += answer["workflow_runs"]
        if len(answer["workflow_runs"]) < PAGE:
            break
    else:
        raise GithubUnreadable("GitHub a répondu plus de %d pages d’exécutions" % MAX_PAGES)
    # The closed pull requests, the last updated first: one merged since
    # ``since`` was updated since then, so the pages stop at the first
    # pull request updated before.
    pulls = []
    for page in range(1, MAX_PAGES + 1):
        answer = _api(gh_bin, timeout, "repos/%s/pulls" % repository, state="closed", per_page=PAGE, page=page,
                      sort="updated", direction="desc")
        if not isinstance(answer, list):
            raise GithubUnreadable("GitHub a répondu sans les PR attendues")
        pulls += answer
        updated = [_epoch(pull.get("updated_at")) for pull in answer if isinstance(pull, dict)]
        if len(answer) < PAGE or any(at is not None and at < since for at in updated):
            break
    else:
        raise GithubUnreadable("GitHub a répondu plus de %d pages de PR" % MAX_PAGES)
    return {"repository": repository, "workflow_runs": runs, "pull_requests": pulls}


def _epoch(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).timestamp()


def _api(gh_bin, timeout, path, **fields):
    argv = [gh_bin, "api", "-X", "GET", path]
    for name, value in fields.items():
        argv += ["-f", "%s=%s" % (name, value)]
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=True)
        return json.loads(completed.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise GithubUnreadable("GitHub n’a pas répondu") from exc
