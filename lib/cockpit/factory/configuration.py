"""The roles of the Factory as its own files configure them (G1, af-wrxrmg;
Spec af-fgcw0d, user stories 161 and 162).

    read_configuration(root) -> {"roles", "flow", "bounds", "other_roles",
                                 "in_service", "unreadable"}

Every name and figure comes from the files of the Factory at ``root``, never
from an example:

- ``config/delivery-roles.json``: the three delivery roles and their agent;
- ``config/provider-policy.json``: the chain of providers of each agent (the
  first is the one configured, the next ones its fallbacks), and what each
  provider and its pool are called;
- ``city.toml``: the model each provider runs (``--model`` or ``-m`` in its
  ``args_append``) and its reasoning effort (``option_defaults.effort``);
- ``config/delivery-flow.json``: the steps of the delivery flow and the role
  of each, the ceilings of sessions and the bounds of the flow.

``city.provider.toml``, which ``bin/provider-failover`` writes on the host and
which may be absent, is not configuration: it says which provider is in
service for each agent now, and is returned apart (``in_service``, None when
there is no such file).

A file that cannot be read leaves its part out and is named in
``unreadable``: nothing is guessed in its place.
"""
import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROLES_FILE = "config/delivery-roles.json"
POLICY_FILE = "config/provider-policy.json"
CITY_FILE = "city.toml"
FLOW_FILE = "config/delivery-flow.json"
IN_SERVICE_FILE = "city.provider.toml"
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


def read_configuration(root=ROOT):
    roles_doc = _read(root, ROLES_FILE, json.load)
    policy = _read(root, POLICY_FILE, json.load)
    city = _read(root, CITY_FILE, tomllib.load)
    flow = _read(root, FLOW_FILE, json.load)
    in_service_doc = _read(root, IN_SERVICE_FILE, tomllib.load)
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

    return {
        "roles": roles,
        "flow": steps,
        "bounds": (flow or {}).get("bounds"),
        "other_roles": other_roles,
        "in_service": in_service,
        "unreadable": unreadable,
    }
