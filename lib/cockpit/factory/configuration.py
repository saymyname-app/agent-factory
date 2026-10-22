"""The roles of the Factory as its own files configure them (G1, af-wrxrmg;
Spec af-fgcw0d, user stories 161 and 162).

    read_configuration(root, now) -> {"roles", "flow", "bounds", "other_roles",
                                      "pools", "in_service", "availability",
                                      "unreadable"}

Every name and figure comes from the files of the Factory at ``root``, never
from an example:

- ``config/delivery-roles.json``: the three delivery roles and their agent;
- ``config/provider-policy.json``: the chain of providers of each agent (the
  first is the one configured, the next ones its fallbacks), what each
  provider and its pool are called, and the pools themselves (``pools``:
  the quota each provider draws on);
- ``city.toml``: the model each provider runs (``--model`` or ``-m`` in its
  ``args_append``) and its reasoning effort (``option_defaults.effort``);
- ``config/delivery-flow.json``: the steps of the delivery flow and the role
  of each, the ceilings of sessions and the bounds of the flow.

Two files ``bin/provider-failover`` writes on the host, and which may be
absent, are not configuration but what is observed, and are returned apart:

- ``city.provider.toml``: which provider is in service for each agent now
  (``in_service``, None when there is no such file);
- ``.gc/provider-state.json``: what the failover detected of each pool and
  provider -- a quota exhausted or low, an error, until when, a provider
  disabled -- read at ``now`` as ``bin/provider-failover status`` reads it
  (``availability``: ``{"at": its last tick, "pools": {pool: status},
  "providers": {provider: status}}``, a status being ``{"state":
  available|exhausted|low|error|disabled, "until", "reason", "recorded"}``;
  None when there is no such file). « available » means no limit was
  detected, not that a quota was measured; ``recorded`` is False when the
  file holds nothing of that pool (nor, for a provider, of it disabled):
  the failover then observed nothing of it, and « available » is only its
  default.

A file that cannot be read leaves its part out and is named in
``unreadable``: nothing is guessed in its place.
"""
import json
import time
import tomllib
from pathlib import Path

import provider_failover

ROOT = Path(__file__).resolve().parents[3]
ROLES_FILE = "config/delivery-roles.json"
POLICY_FILE = "config/provider-policy.json"
CITY_FILE = "city.toml"
FLOW_FILE = "config/delivery-flow.json"
IN_SERVICE_FILE = "city.provider.toml"
STATE_FILE = ".gc/provider-state.json"
SOURCES = (ROLES_FILE, POLICY_FILE, CITY_FILE, FLOW_FILE)

ROLE_LABELS = {"author": "Auteur livraison", "reviewer": "Relecteur livraison", "evaluator": "Évaluateur livraison"}
# The ceiling of sessions of each role, in config/delivery-flow.json.
CEILINGS = {"author": "max_sessions", "reviewer": "max_reviewer_sessions", "evaluator": "max_evaluator_sessions"}
# The steps of the delivery flow that a role runs, in the order a ticket
# meets them, under the key config/delivery-flow.json gives each, and in
# parallel when they share a stage.
FLOW_STEPS = (
    (("start", "Écrire les tests puis le code"),),
    (("code_review", "Revue du code"), ("evaluation", "Évaluer le ticket")),
    (("end_review", "Revue finale"), ("outcome_evaluation", "Évaluer le résultat")),
)


def _read(root, name, parse):
    try:
        with open(Path(root) / name, "rb") as handle:
            return parse(handle)
    except (OSError, ValueError, tomllib.TOMLDecodeError):
        return None


def _model_of(provider):
    """The model id a provider of city.toml passes its command, or None."""
    args = list(provider.get("args_append") or [])
    for flag in ("--model", "-m"):
        if flag in args[:-1]:
            return args[args.index(flag) + 1]
    return None


def _provider(name, policy, city):
    declared = (policy.get("providers") or {}).get(name) or {}
    pool = (policy.get("pools") or {}).get(declared.get("pool")) or {}
    built = ((city or {}).get("providers") or {}).get(name) or {}
    return {
        "name": name,
        "label": declared.get("label") or name,
        "pool": pool.get("label") or declared.get("pool"),
        "model": _model_of(built) if city is not None else None,
        "effort": (built.get("option_defaults") or {}).get("effort") if city is not None else None,
        "read_only": name.endswith("-readonly"),
    }


def _availability(policy, state_doc, now):
    """What the failover observed of each pool and provider at ``now``, or
    None when it wrote nothing here or the policy cannot be read."""
    if state_doc is None or not isinstance(policy, dict):
        return None
    try:
        provider_failover.validate_policy(policy)
    except provider_failover.PolicyError:
        return None
    state = provider_failover.normalize_state(state_doc, policy)

    def status(found, recorded):
        return {"state": found.get("state"), "until": provider_failover.epoch(found.get("until")),
                "reason": found.get("reason") or found.get("evidence"), "recorded": recorded}

    def pool_recorded(pool):
        return bool(state["pools"].get(pool))

    return {
        "at": provider_failover.epoch(state.get("sessions_at")),
        "pools": {name: status(provider_failover.pool_status(state, policy, name, now), pool_recorded(name))
                  for name in policy["pools"]},
        "providers": {name: status(provider_failover.provider_status(state, policy, name, now),
                                   bool(state["disabled"].get(name)) or pool_recorded(declared["pool"]))
                      for name, declared in policy["providers"].items()},
    }


def read_configuration(root=ROOT, now=None):
    roles_doc = _read(root, ROLES_FILE, json.load)
    policy = _read(root, POLICY_FILE, json.load)
    city = _read(root, CITY_FILE, tomllib.load)
    flow = _read(root, FLOW_FILE, json.load)
    in_service_doc = _read(root, IN_SERVICE_FILE, tomllib.load)
    state_doc = _read(root, STATE_FILE, json.load)
    unreadable = [name for name, doc in zip(SOURCES, (roles_doc, policy, city, flow)) if doc is None]

    targets = (policy or {}).get("targets") or {}
    roles = []
    for key, declared in ((roles_doc or {}).get("roles") or {}).items():
        agent = declared.get("agent")
        chain = [_provider(name, policy, city) for name in (targets.get(agent) or {}).get("chain") or []]
        ceiling = (flow or {}).get(CEILINGS.get(key, ""))
        roles.append({
            "key": key,
            "label": ROLE_LABELS.get(key, key),
            "agent": agent,
            "configured": chain[0] if chain else None,
            "fallbacks": chain[1:],
            "max_sessions": ceiling if isinstance(ceiling, int) else None,
        })
    delivery_agents = {role["agent"] for role in roles}
    other_roles = [
        {"agent": agent, "label": target.get("label") or agent,
         "configured": _provider((target.get("chain") or [None])[0], policy, city) if target.get("chain") else None}
        for agent, target in targets.items() if agent not in delivery_agents and agent != "workspace"
    ]

    steps = []
    for stage in FLOW_STEPS:
        present = [{"key": key, "label": label, "role": flow[key]["role"]}
                   for key, label in stage if isinstance((flow or {}).get(key), dict) and flow[key].get("role")]
        if present:
            steps.append(present)

    in_service = None
    if in_service_doc is not None:
        in_service = {patch.get("name"): patch.get("provider")
                      for patch in (in_service_doc.get("patches") or {}).get("agent") or [] if patch.get("provider")}

    pools = []
    for key, pool in ((policy or {}).get("pools") or {}).items():
        drawn = [declared.get("label") or name for name, declared in ((policy or {}).get("providers") or {}).items()
                 if declared.get("pool") == key]
        pools.append({"key": key, "label": pool.get("label") or key, "note": pool.get("note"), "providers": drawn})

    return {
        "roles": roles,
        "flow": steps,
        "bounds": (flow or {}).get("bounds"),
        "other_roles": other_roles,
        "pools": pools,
        "in_service": in_service,
        "availability": _availability(policy, state_doc, time.time() if now is None else now),
        "unreadable": unreadable,
    }
