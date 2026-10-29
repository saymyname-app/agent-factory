"""Cleaning the unused work spaces from the page Usine, through the door
factory-maintain (G2, af-f8nlhr; Spec af-fgcw0d, user story 166, and the
choice « Maintenance » of af-2zseit).

    preview(maintain_bin, timeout)            -> {"candidates": [...], "kept": [...]}
    clean(maintain_bin, confirmed, timeout)   -> [{"name", "sha", "outcome", "reason"}, ...]

``preview`` is the door's own dry run (``clean-worktrees --dry-run``): each
worktree it looked at, by the name of its folder and the commit it is at,
either a candidate -- pushed, no local change, and ``merged`` or ``idle``
(not merged, untouched past the door's idle days) as the door says why -- or
kept with the door's reason: ``local-changes``, ``not-merged`` (work under
way), ``unpushed`` (commits that exist only here: the door escalates them,
never removes them), ``detached``. The cockpit decides nothing of it.

``clean`` takes the candidates the operator confirmed, each ``{"name",
"sha"}`` as the preview read it. It reads the scope again first: if the
candidates are no longer exactly those -- a worktree gone or come, or another
one at the same name --, nothing runs and :class:`ScopeChanged` carries the
scope read now, for a new confirmation: a scope never grows, nor shrinks, in
silence. Otherwise the door runs on those worktrees only, each at its commit
(``--only <name>@<sha>``), so one replaced in between is kept (``changed``);
each element then has its result: ``removed``, ``not-removed`` (the door
could not), or ``kept`` with its reason, as the preview just read said --
``unpushed-unreported`` when the door could not escalate it.

A door that does not answer in ``timeout`` is an uncertain outcome
(:class:`cockpit.actions.registry.ActionUncertain`); a door that refuses is
an :class:`cockpit.actions.registry.ActionError` carrying its words.
"""
import os
import re
import subprocess

from cockpit.actions.registry import ActionError, expired

LINE = re.compile(r"^(would remove|removed|would escalate|escalated|not escalated|would keep|kept|not removed): "
                  r"(\S+)(?: \((.*)\))?$")
SHA = re.compile(r"\bsha=([0-9a-f]+)")
KEPT_REASONS = ("local-changes", "not-merged", "detached", "changed")


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


def _sha(detail):
    found = SHA.search(detail or "")
    return found.group(1) if found else None


def _reason(kind, detail):
    if kind == "not escalated":
        return "unpushed-unreported"
    if kind.endswith("escalate") or kind == "escalated":
        return "unpushed"
    return detail if detail in KEPT_REASONS else "kept"


def preview(maintain_bin, timeout):
    candidates, kept = [], []
    for kind, path, detail in _door(maintain_bin, ["--dry-run"], timeout):
        name = os.path.basename(path)
        if kind == "would remove":
            candidates.append({"name": name, "sha": _sha(detail),
                               "why": "idle" if (detail or "").endswith(", idle") else "merged"})
        else:
            kept.append({"name": name, "reason": _reason(kind, detail)})
    return {"candidates": candidates, "kept": kept}


def _identity(element):
    if not isinstance(element, dict):
        return None
    return (element.get("name"), element.get("sha"))


def clean(maintain_bin, confirmed, timeout):
    now = preview(maintain_bin, timeout)
    read = sorted((_identity(element) for element in now["candidates"]), key=str)
    if not isinstance(confirmed, list) or sorted(map(_identity, confirmed), key=str) != read:
        raise ScopeChanged(
            "Le périmètre a changé depuis l’aperçu : %s. Rien n’a été retiré ; examine le nouveau périmètre et "
            "confirme-le." % _count(len(read), "espace terminé à retirer", "espaces terminés à retirer"), now)
    results = []
    if read:
        args = [arg for name, sha in read for arg in ("--only", "%s@%s" % (name, sha))]
        done = {os.path.basename(path): (kind, detail) for kind, path, detail in _door(maintain_bin, args, timeout)}
        for name, sha in read:
            kind, detail = done.get(name, ("", ""))
            if kind == "removed":
                results.append({"name": name, "sha": sha, "outcome": "removed", "reason": None})
            elif kind in ("kept", "escalated", "not escalated"):
                results.append({"name": name, "sha": sha, "outcome": "kept", "reason": _reason(kind, detail)})
            else:
                results.append({"name": name, "sha": sha, "outcome": "not-removed", "reason": None})
    return results + [{"name": element["name"], "sha": None, "outcome": "kept", "reason": element["reason"]}
                      for element in now["kept"]]


def _count(count, one, many):
    if count == 0:
        return "plus aucun " + one
    return "%d %s" % (count, one if count == 1 else many)
