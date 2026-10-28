"""Cleaning the unused work spaces from the page Usine, through the door
factory-maintain (G2, af-f8nlhr; Spec af-fgcw0d, user story 166, and the
choice « Maintenance » of af-2zseit).

    preview(maintain_bin, timeout)            -> {"candidates": [...], "kept": [...]}
    clean(maintain_bin, confirmed, timeout)   -> [{"name", "outcome", "reason"}, ...]

``preview`` is the door's own dry run (``clean-worktrees --dry-run``): each
worktree it looked at, by the name of its folder, either a candidate --
merged and pushed, no local change -- or kept with the door's reason:
``local-changes``, ``not-merged`` (work under way), ``unpushed`` (commits
that exist only here: the door escalates them, never removes them),
``detached``. The cockpit decides nothing of it.

``clean`` takes the candidates the operator confirmed. It reads the scope
again first: if the candidates are no longer exactly those, nothing runs
and :class:`ScopeChanged` carries the scope read now, for a new
confirmation -- a scope never grows, nor shrinks, in silence. Otherwise the
door runs on those names only (``--only``), so a worktree that became a
candidate in between is not touched; each element then has its result:
``removed``, ``not-removed`` (the door could not), or ``kept`` with its
reason, as the preview just read said.

A door that does not answer in ``timeout`` is an uncertain outcome
(:class:`cockpit.actions.registry.ActionUncertain`); a door that refuses is
an :class:`cockpit.actions.registry.ActionError` carrying its words.
"""
import os
import re
import subprocess

from cockpit.actions.registry import ActionError, expired

LINE = re.compile(r"^(would remove|removed|would escalate|escalated|would keep|kept|not removed): (\S+)(?: \((.*)\))?$")
KEPT_REASONS = ("local-changes", "not-merged", "detached")


class ScopeChanged(ActionError):
    """The candidates read now are not the ones confirmed: ``scope`` is the
    preview read now."""

    status = 409

    def __init__(self, message, scope):
        super().__init__(message)
        self.scope = scope


def _door(maintain_bin, args, timeout):
    try:
        done = subprocess.run([maintain_bin, "clean-worktrees", *args], capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        raise expired(timeout)
    except OSError as exc:
        raise ActionError("commande introuvable : %s" % exc)
    if done.returncode != 0:
        raise ActionError((done.stderr or done.stdout or "échec du nettoyage").strip())
    return [found.groups() for found in map(LINE.match, done.stdout.splitlines()) if found]


def _reason(kind, detail):
    if kind.endswith("escalate") or kind == "escalated":
        return "unpushed"
    return detail if detail in KEPT_REASONS else "kept"


def preview(maintain_bin, timeout):
    candidates, kept = [], []
    for kind, path, detail in _door(maintain_bin, ["--dry-run"], timeout):
        name = os.path.basename(path)
        if kind == "would remove":
            candidates.append({"name": name})
        else:
            kept.append({"name": name, "reason": _reason(kind, detail)})
    return {"candidates": candidates, "kept": kept}


def clean(maintain_bin, confirmed, timeout):
    now = preview(maintain_bin, timeout)
    names = [element["name"] for element in now["candidates"]]
    if sorted(names) != sorted(set(confirmed or [])):
        raise ScopeChanged(
            "Le périmètre a changé depuis l’aperçu : %s. Rien n’a été retiré ; examine le nouveau périmètre et "
            "confirme-le." % _count(len(names), "espace terminé à retirer", "espaces terminés à retirer"), now)
    results = []
    if names:
        args = [arg for name in names for arg in ("--only", name)]
        done = {os.path.basename(path): kind for kind, path, _ in _door(maintain_bin, args, timeout)}
        results = [{"name": name, "outcome": "removed" if done.get(name) == "removed" else "not-removed",
                    "reason": None} for name in names]
    return results + [{"name": element["name"], "outcome": "kept", "reason": element["reason"]}
                      for element in now["kept"]]


def _count(count, one, many):
    if count == 0:
        return "plus aucun " + one
    return "%d %s" % (count, one if count == 1 else many)
