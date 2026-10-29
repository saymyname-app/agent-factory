"""The settings of a role of delivery from the page Usine (G2, af-f8nlhr; Spec
af-fgcw0d, user stories 163 and 164, and the choice « Usine » of af-2zseit:
« L'édition soutenue par une porte montre valeur actuelle, nouvelle valeur,
portée, conséquences, confirmation puis relecture … Modèle/effort/chaîne non
supportés : préparer une proposition, ne pas simuler un succès. Secours
inter-provider soumis à l'adoption du rôle et aux mécanismes provider-failover
existants ; aucune écriture brute de configuration contournant leur
contrôle. »).

    offered(configuration, role_key)             -> the choices of the editor
    plan(configuration, role_key, principal, effort="", fallback="")
                                                 -> what that choice changes
    apply(failover_bin, plan, timeout)           -> what the door reads back
    propose(proposal_door_bin, plan, language, timeout) -> the proposal's words

The one setting a door supports is which provider of the role's own chain
it runs on first, the next ones its fallbacks: every provider of that chain,
config/provider-policy.json, passed the trial of adoption of the role
(bin/role-adoption-trial), and ``bin/provider-failover set --action chain``
orders it. Any other change is prepared as a proposal through
bin/proposal-door, and changes nothing: another provider first -- another
model --, or added as a fallback, is not in the chain because it was not
tried for the role; another effort is set by no door (a provider runs at the
effort city.toml gives it).

A setting changes which provider the role's next sessions start on; the
sessions already open keep theirs. ``apply`` returns what the door read
back after writing (its own status of the role), never what was asked: a
reading that does not show the setting is an uncertain outcome.

A door that does not answer in ``timeout`` is an uncertain outcome
(:class:`cockpit.actions.registry.ActionUncertain`); one that refuses is an
:class:`cockpit.actions.registry.ActionError` carrying its words.
"""
import json
import subprocess

from cockpit.actions.registry import ActionError, ActionUncertain, expired

# The efforts the editor offers, as the page says them in a sentence.
EFFORTS = {"low": "faible", "medium": "moyen", "high": "élevé", "xhigh": "très élevé"}
UNREAD_BACK = ("La porte a répondu, mais sa relecture ne montre pas le réglage demandé. Son issue est "
               "incertaine ; revérifie la configuration avant de réessayer.")


def _role(configuration, role_key):
    role = next((r for r in configuration["roles"] if r["key"] == role_key), None)
    if role is None or role["configured"] is None:
        raise ActionError("Ce rôle n’est pas dans la configuration lue.")
    return role


def order_of(configuration, role):
    """The names of the providers the role runs on, in order: the one an
    operator set through the door, else its configured chain."""
    configured = [role["configured"]["name"], *(p["name"] for p in role["fallbacks"])]
    return list(configuration["orders"].get(role["agent"]) or configured)


def offered(configuration, role_key):
    """The choices of the editor of ``role_key``: ``providers``, to run on
    first -- those of its order, each ``supported``, then the other
    providers of the same access (read only or not), each not tried for the
    role --; ``efforts``, each ``{"key", "words", "current"}``, the current
    one the effort of the provider in front; ``fallbacks``, the providers of
    the same access its order does not hold, to add after it (none is
    supported)."""
    role = _role(configuration, role_key)
    providers = configuration["providers"]
    order = order_of(configuration, role)
    chain = [providers[name] for name in order if name in providers]
    others = [p for name, p in providers.items()
              if name not in order and p["read_only"] == role["configured"]["read_only"]]
    effort = providers[order[0]]["effort"] if order and order[0] in providers else None
    return {
        "providers": ([dict(p, supported=True, current=index == 0) for index, p in enumerate(chain)]
                      + [dict(p, supported=False, current=False) for p in others]),
        "efforts": [{"key": key, "words": words, "current": key == effort} for key, words in EFFORTS.items()],
        "fallbacks": others,
    }


def _sentence(words):
    """``words`` with its first letter upper case, the others as they are."""
    return words[:1].upper() + words[1:]


def _say_order(providers, order, effort=None):
    first = providers[order[0]]["label"]
    if effort:
        first = "%s, passé à l’effort %s" % (first, EFFORTS[effort])
    rest = [providers[name]["label"] for name in order[1:]]
    if not rest:
        return "%s, sans secours" % first
    return "%s, puis %s en secours" % (first, " puis ".join(rest))


def plan(configuration, role_key, principal, effort="", fallback=""):
    """What choosing ``principal`` first for ``role_key``, at ``effort``
    (a key of EFFORTS; empty: the provider's own) and with ``fallback``
    added after its order (empty: none) changes. ``supported``: the door
    orders the role's providers so; otherwise ``quoi`` is what a proposal
    would ask."""
    role = _role(configuration, role_key)
    providers = configuration["providers"]
    if principal not in providers:
        raise ActionError("Fournisseur inconnu de la configuration lue : %s." % principal)
    if effort and effort not in EFFORTS:
        raise ActionError("Effort inconnu : %s." % effort)
    current = order_of(configuration, role)
    new = [principal] + [name for name in current if name != principal]
    if fallback:
        if fallback not in providers:
            raise ActionError("Fournisseur inconnu de la configuration lue : %s." % fallback)
        if fallback in new:
            raise ActionError("%s est déjà dans l’ordre de ce rôle." % providers[fallback]["label"])
        new.append(fallback)
    effort = effort if effort and effort != providers[principal]["effort"] else ""
    label, chosen = role["label"], providers[principal]["label"]
    untried = [name for name in new if name not in current]
    supported = not untried and not effort
    asked = []
    if principal != current[0]:
        asked.append("sur %s" % chosen)
    if effort:
        asked.append("à l’effort %s" % EFFORTS[effort])
    if fallback:
        asked.append("avec %s en secours" % providers[fallback]["label"])
    if not supported:
        why = ["%s n’a pas passé l’essai d’adoption du rôle %s" % (providers[name]["label"], label.lower())
               for name in untried]
        if effort:
            why.append("aucune porte ne règle l’effort d’un fournisseur : l’effort %s demande un fournisseur "
                       "déclaré à cet effort et essayé pour le rôle" % EFFORTS[effort])
        consequences = ("Rien ne change maintenant : une proposition est préparée pour toi. %s ; cet essai, puis la "
                        "validation de l’ordre de ses fournisseurs, viennent avant tout changement."
                        % _sentence(" ; ".join(why)))
    elif new == current:
        consequences = "Rien ne change : %s est déjà en tête." % chosen
    else:
        consequences = ("Les prochaines sessions du rôle %s démarrent sur %s ; %s." % (
            label.lower(), chosen,
            "%s devient son secours" % " puis ".join(providers[name]["label"] for name in new[1:])
            if len(new) > 1 else "il n’a pas de secours"))
    return {
        "role": role_key, "label": label, "agent": role["agent"], "principal": principal, "effort": effort,
        "fallback": fallback, "current": current, "new": new, "supported": supported,
        "changes": new != current or bool(effort),
        "current_text": _say_order(providers, current), "new_text": _say_order(providers, new, effort),
        "chosen": chosen, "consequences": consequences,
        "quoi": "Passer le rôle %s %s" % (label.lower(), ", ".join(asked)) if asked else "",
    }


def _door(args, timeout):
    try:
        done = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise expired(timeout)
    except OSError as exc:
        raise ActionError("commande introuvable : %s" % exc)
    return done


def apply(failover_bin, planned, timeout):
    """Orders the role's providers as ``planned`` through the door, then
    returns its reading of the role: ``{"provider", "order"}``."""
    if not planned["supported"]:
        raise ActionError("Ce changement n’est pris en charge par aucune porte : prépare-le comme proposition.")
    done = _door([failover_bin, "set", "--action", "chain", "--by", "cockpit",
                  "--args", json.dumps({"target": planned["agent"], "chain": planned["new"]})], timeout)
    try:
        answer = json.loads(done.stdout or "{}")
    except ValueError:
        answer = {}
    if done.returncode != 0 or answer.get("ok") is not True:
        raise ActionError(answer.get("error") or (done.stderr or done.stdout or "réglage refusé").strip())
    target = ((answer.get("status") or {}).get("targets") or {}).get(planned["agent"]) or {}
    order = [entry.get("provider") for entry in target.get("chain") or []]
    if order != planned["new"]:
        raise ActionUncertain(UNREAD_BACK)
    return {"provider": target.get("provider"), "order": order}


def propose(proposal_door_bin, planned, language, timeout):
    """Prepares the change ``planned`` as a proposal of class decision
    through the door of proposals; returns its « quoi »."""
    quoi = planned["quoi"]
    body = {
        "quoi": quoi,
        "pourquoi": "Demandé depuis l’Usine : aucune porte ne fait ce changement, il attend ta décision.",
        "que_faire": [
            {"option": "Faire l’essai d’adoption du rôle sur ce fournisseur, puis valider son ordre",
             "consequence": "le rôle pourra tourner dessus une fois l’essai réussi",
             "recommande": True, "raison": "un rôle ne tourne que sur un fournisseur essayé pour lui"},
            {"option": "Garder la configuration actuelle", "consequence": "rien ne change"},
        ],
        "langue": language,
        "classe": "decision",
        "details": "role=%s agent=%s demande=%s effort=%s secours=%s ordre_actuel=%s" % (
            planned["role"], planned["agent"], planned["principal"], planned["effort"] or "-",
            planned["fallback"] or "-", ",".join(planned["current"])),
    }
    done = _door([proposal_door_bin, "create", json.dumps(body, ensure_ascii=False)], timeout)
    if done.returncode != 0:
        raise ActionError((done.stderr or done.stdout or "proposition refusée").strip())
    return quoi
