"""Each project's rituals, as its own status command reports them (spec
af-oohx2x point ouvert 2: "chaque descripteur de projet pointe vers la
lecture pur code du statut de ses rituels ... Un rituel dû = Demande
opérateur Quand tu veux, écran seul, sans push").

T15 built the request (:mod:`cockpit.requests.sources.rituals`) for a
parsed status nobody produced. This module produces it, as one read for
the read model's "rituals" source.

The command is a file of the project's knowledge repository. It is run
from an export of that repository's default branch -- a plain directory
the cockpit owns, rewritten from its clone before each run -- never from
the clone (which keeps nothing checked out) and never from anyone's
working copy. The cockpit runs the status command only; it never runs a
ritual.

What a status command prints, either of:

- one line per ritual, ``DUE <id> — <detail>``, ``ok <id> — ...`` or
  ``wait <id> — ...``;
- JSON, a list of ``{"id", "status"}`` with status ``due``, ``ok`` or
  ``paused``.

Anything else (a non-zero exit, no recognisable ritual) is that project's
"illisible", never an empty list taken for "nothing is due".
"""
import json
import os
import re
import shlex
import shutil
import subprocess
import tarfile

from cockpit.projects import promotion
from cockpit.projects.depots import GIT_LOCK, REPO_URL_TEMPLATE, clone_path, ensure_clone
from cockpit.projects.roadmap import RoadmapReadError, default_branch

STATUS_TIMEOUT_SECONDS = 180
_LINE = re.compile(r"^(DUE|ok|wait)\s+(\S+)\s*(?:[—–-]\s*(.*))?$")
_JSON_STATUSES = ("due", "ok", "paused")


class RitualsReadError(Exception):
    """This project's ritual status could not be read."""


def export_tree(clone, dest, git_bin="git", timeout=120):
    """Rewrites ``dest`` with the files of the clone's default branch as
    they are on origin."""
    branch = default_branch(clone, git_bin=git_bin)
    tmp = dest + ".tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    archive = tmp + ".tar"
    try:
        completed = subprocess.run(
            [git_bin, "-C", str(clone), "archive", "--format=tar", "-o", archive, "origin/%s" % branch],
            capture_output=True, text=True, timeout=timeout,
        )
        if completed.returncode != 0:
            raise RitualsReadError(completed.stderr.strip() or "git archive failed")
        with tarfile.open(archive) as tar:
            tar.extractall(tmp, filter="data")
    except (OSError, subprocess.TimeoutExpired, tarfile.TarError) as exc:
        raise RitualsReadError(str(exc)) from exc
    finally:
        if os.path.exists(archive):
            os.remove(archive)
    shutil.rmtree(dest, ignore_errors=True)
    os.replace(tmp, dest)
    return dest


def _argv(export_dir, command):
    """The command line for ``command`` (the descriptor's
    ``rituals_status_command``): its first word must be a file of the
    export. A file git does not mark executable is run through its own
    ``#!`` line, as it would be were it marked."""
    parts = shlex.split(command)
    if not parts:
        raise RitualsReadError("no status command")
    root = os.path.realpath(export_dir)
    path = os.path.realpath(os.path.join(root, parts[0]))
    if not path.startswith(root + os.sep) or not os.path.isfile(path):
        raise RitualsReadError("%s is not a file of the repository" % parts[0])
    if os.access(path, os.X_OK):
        return [path] + parts[1:]
    with open(path, "rb") as fh:
        first = fh.readline(256).decode("utf-8", "replace").strip()
    if not first.startswith("#!"):
        raise RitualsReadError("%s is not executable" % parts[0])
    return shlex.split(first[2:]) + [path] + parts[1:]


def parse_status(stdout):
    """``[{"id", "due", "detail"}]`` from what a status command printed."""
    text = (stdout or "").strip()
    if text[:1] in ("[", "{"):
        try:
            data = json.loads(text)
        except ValueError:
            data = None
        if data is not None:
            items = data if isinstance(data, list) else [data]
            out = [
                {"id": str(item["id"]), "due": item["status"] == "due", "detail": ""}
                for item in items
                if isinstance(item, dict) and item.get("id") and item.get("status") in _JSON_STATUSES
            ]
            if not out:
                raise RitualsReadError("no ritual in the status command's JSON")
            return out
    out = []
    for line in text.splitlines():
        match = _LINE.match(line.strip())
        if match:
            out.append({"id": match.group(2), "due": match.group(1) == "DUE", "detail": (match.group(3) or "").strip()})
    if not out:
        raise RitualsReadError("no ritual in the status command's output")
    return out


def run_status(export_dir, command, timeout=STATUS_TIMEOUT_SECONDS):
    argv = _argv(export_dir, command)
    try:
        completed = subprocess.run(argv, cwd=export_dir, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RitualsReadError(str(exc)) from exc
    if completed.returncode != 0:
        raise RitualsReadError("status command exited %d" % completed.returncode)
    return parse_status(completed.stdout)


def read_rituels(
    descriptors, clones_dir, exports_dir, url_template=REPO_URL_TEMPLATE, git_bin="git",
    timeout=STATUS_TIMEOUT_SECONDS,
):
    """One read. Returns ``{"rituels": [{"id", "titre", "due", "detail",
    "projet", "reportable"}], "illisibles": [display names]}``. Raises
    only when no project's status could be read at all."""
    rituels, illisibles = [], []
    attempts = 0
    for descriptor in descriptors:
        command = descriptor.get("rituals_status_command")
        repo = descriptor.get("knowledge_repo")
        if not command or not repo:
            continue
        attempts += 1
        project_id = descriptor["project_id"]
        try:
            with GIT_LOCK:
                clone = ensure_clone(clones_dir, repo, url_template, git_bin)
                promotion.fetch(clone, git_bin=git_bin, timeout=60)
                export = export_tree(clone, clone_path(exports_dir, repo), git_bin=git_bin)
            for ritual in run_status(export, command, timeout=timeout):
                rituels.append({
                    "id": "rituel:%s:%s" % (project_id, ritual["id"]),
                    "titre": ritual["id"],
                    "due": ritual["due"],
                    "detail": ritual["detail"],
                    "projet": project_id,
                    # No bead to carry a "later": Reporter is not offered.
                    "reportable": False,
                })
        except (RitualsReadError, RoadmapReadError):
            illisibles.append(descriptor.get("display_name") or project_id)
    if attempts and len(illisibles) == attempts:
        raise RitualsReadError("aucun statut de rituels lisible")
    return {"rituels": rituels, "illisibles": illisibles}


def health_lines(row):
    """One health-zone line per project whose rituals could not be read."""
    if row is None or row.get("value") is None or row.get("freshness") == "unknown":
        return []
    return [
        {"kind": "warn", "text": "Rituels de %s : statut illisible." % name}
        for name in row["value"].get("illisibles") or []
    ]
