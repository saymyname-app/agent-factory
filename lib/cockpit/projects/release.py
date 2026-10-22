"""The release plan of a project (cadrage), as the page of the project reads
it (E, af-8rbceu; Spec af-fgcw0d, user stories 153 to 156, decisions 5 and
« Projet et release »).

    plan = parse_release(text)      # raises ReleaseError
    estimate = estimate_of(plan)

The release plan is versioned in the knowledge repository of the project,
beside its structured roadmap: ``release.toml`` in the directory of the
descriptor's ``roadmap_path`` (:func:`release_path`). The cockpit reads it
and never writes it -- writing it belongs to the ritual « Préparer la
prochaine release ». Its shape, every field a text unless said otherwise::

    target = "Permettre à un nouvel utilisateur de …"   # the revisable target
    status = "proposition"                               # optional

    [[gain]]                     # a criterion verified, with its proof
    title = "Créer et retrouver une note"
    proof = "Parcours essayé le …, résultat conforme."

    [[remaining]]                # a criterion still to reach
    title = "Exporter les notes au format choisi"

    [[decision]]                 # state: open, deferred or included
    question = "Le partage de notes est-il nécessaire dès cette release ?"
    state = "open"

    [milestone]                  # the next milestone and how it is verified
    title = "Faire essayer le parcours complet à trois utilisateurs"
    check = "Trois essais documentés ; blocages et réussites observés."
    state = "À préparer · réalisation non lancée"   # optional

    [estimate]                   # optional; a range, or why there is none
    range = "1 à 3 semaines"
    conditions = "Pour les deux critères restants uniquement, si …"
    hypotheses = "Capacité stable, aucun blocage externe connu."
    comparables = 12             # integer: comparable results it rests on
    criteria = 2                 # integer: how many criteria it covers
    computed_at = "2026-10-12T12:00:00+02:00"
    # or: unavailable = "Historique comparable insuffisant."

    [[history]]                  # each change of the target, oldest first
    change = "Cible initiale proposée · parcours individuel"

A range is shown only conditional: its conditions, its hypotheses, the
comparable results it rests on and the date it was computed are all
written, and it covers exactly the criteria that remain -- a scope that
changed since leaves it to recompute. Otherwise the estimate is said
unavailable, with why. No global percentage and no date of delivery are
ever drawn from the plan: counting criteria does not weigh them.
"""
import posixpath
import tomllib
from datetime import datetime
from zoneinfo import ZoneInfo

RELEASE_FILE = "release.toml"
DECISION_STATES = ("open", "deferred", "included")
PARIS = ZoneInfo("Europe/Paris")


class ReleaseError(ValueError):
    """The release plan cannot be read: what is wrong, in French."""


def release_path(roadmap_path):
    """Where the release plan of a project is, in its knowledge repository:
    beside its structured roadmap."""
    return posixpath.join(posixpath.dirname(roadmap_path or ""), RELEASE_FILE)


def _text(table, key, where, required=True):
    value = table.get(key)
    if value is None and not required:
        return ""
    if not isinstance(value, str) or not value.strip():
        raise ReleaseError("%s : « %s » doit être un texte non vide" % (where, key))
    return value.strip()


def _entries(data, key):
    entries = data.get(key, [])
    if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
        raise ReleaseError("« %s » doit être une liste de tables [[%s]]" % (key, key))
    return entries


def parse_release(text):
    """The release plan written in ``text``, as plain data: ``target``,
    ``status``, ``gains`` [{title, proof}], ``remaining`` [titles],
    ``decisions`` [{question, state, note}], ``milestone`` {title, check,
    state} or None, ``estimate`` (the table as written, or None),
    ``history`` [changes]. Raises :class:`ReleaseError`."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ReleaseError("TOML illisible : %s" % exc) from exc
    plan = {
        "target": _text(data, "target", "cadrage"),
        "status": _text(data, "status", "cadrage", required=False),
        "gains": [{"title": _text(g, "title", "acquis"), "proof": _text(g, "proof", "acquis")}
                  for g in _entries(data, "gain")],
        "remaining": [_text(r, "title", "critère restant") for r in _entries(data, "remaining")],
        "decisions": [],
        "milestone": None,
        "estimate": None,
        "history": [_text(h, "change", "historique") for h in _entries(data, "history")],
    }
    for decision in _entries(data, "decision"):
        state = decision.get("state", "open")
        if state not in DECISION_STATES:
            raise ReleaseError("décision : « state » doit être l’un de %s" % ", ".join(DECISION_STATES))
        plan["decisions"].append({"question": _text(decision, "question", "décision"), "state": state,
                                  "note": _text(decision, "note", "décision", required=False)})
    milestone = data.get("milestone")
    if milestone is not None:
        if not isinstance(milestone, dict):
            raise ReleaseError("« milestone » doit être une table")
        plan["milestone"] = {"title": _text(milestone, "title", "jalon"), "check": _text(milestone, "check", "jalon"),
                             "state": _text(milestone, "state", "jalon", required=False)}
    estimate = data.get("estimate")
    if estimate is not None:
        if not isinstance(estimate, dict):
            raise ReleaseError("« estimate » doit être une table")
        plan["estimate"] = dict(estimate)
    return plan


def _paris(at):
    try:
        moment = datetime.fromisoformat(at)
    except (TypeError, ValueError):
        return None
    if moment.tzinfo is None:
        return None
    return moment.astimezone(PARIS).strftime("%d/%m/%Y à %H:%M")


def estimate_of(plan):
    """What the page says of the estimate of ``plan``: ``{"shown": True,
    "range", "conditions", "hypotheses", "comparables", "computed"}`` for a
    conditional range, else ``{"shown": False, "reason"}``."""
    estimate = plan.get("estimate") or {}
    if not estimate.get("range"):
        reason = estimate.get("unavailable")
        return {"shown": False, "reason": reason.strip() if isinstance(reason, str) and reason.strip()
                else "Aucune estimation calculée pour cette cible."}
    comparables, criteria = estimate.get("comparables"), estimate.get("criteria")
    computed = _paris(estimate.get("computed_at"))
    missing = [name for name, ok in (
        ("conditions", isinstance(estimate.get("conditions"), str) and estimate["conditions"].strip()),
        ("hypothèses", isinstance(estimate.get("hypotheses"), str) and estimate["hypotheses"].strip()),
        ("données comparables", isinstance(comparables, int) and not isinstance(comparables, bool) and comparables > 0),
        ("date de calcul", computed),
        ("périmètre couvert", isinstance(criteria, int) and not isinstance(criteria, bool)),
    ) if not ok]
    if missing:
        return {"shown": False, "reason": "Fourchette écartée : %s non écrits dans le cadrage." % ", ".join(missing)}
    if criteria != len(plan.get("remaining") or []):
        return {"shown": False, "reason": "Le périmètre a changé depuis le calcul : estimation à recalculer."}
    return {"shown": True, "range": str(estimate["range"]).strip(), "conditions": estimate["conditions"].strip(),
            "hypotheses": estimate["hypotheses"].strip(), "comparables": comparables, "computed": computed}
