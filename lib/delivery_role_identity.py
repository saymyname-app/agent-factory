"""The agent, provider and model a delivery role runs on right now, as
configured (T14, af-96cusm; Spec af-wf4w5r §6: the reviewer of a ticket has
another model than its author, and identical models are said, never left
out).

The role's agent comes from config/delivery-roles.json, the provider
bin/provider-failover gives that agent from its `status --json`, and the
model from that provider's `--model` in city.toml, else from
config/model-catalog.json. It is the configured model, not one observed in a
session. bin/ticket-author records it for the author when a session takes a
ticket, bin/code-review for the reviewer when a review is sent.

`role_supplier` says who supplies that provider (T15, af-higj9z; Spec §7:
the Evaluator runs on another supplier than the author when one is
declared): the `pool` of the provider in config/provider-policy.json --
two profiles of one account are one supplier -- and the other suppliers the
role's chain declares, with whether one of their providers is available.
"""

from __future__ import annotations

import json
import os
import subprocess
import tomllib
from pathlib import Path


def role_identity(root: Path, role: str) -> dict[str, str]:
    """`{agent, provider, model}` of the role; LookupError says what is unknown."""
    try:
        agent = json.loads((root / "config" / "delivery-roles.json").read_text(encoding="utf-8"))["roles"][role]["agent"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise LookupError(f"le rôle {role} n'est pas lisible dans config/delivery-roles.json ({exc!r})") from exc
    failover = os.environ.get("DELIVERY_ROLE_PROVIDER_FAILOVER_BIN") or str(root / "bin" / "provider-failover")
    try:
        status = subprocess.run([failover, "status", "--json"], capture_output=True, text=True, stdin=subprocess.DEVNULL)
        target = json.loads(status.stdout)["targets"][agent]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise LookupError(f"le fournisseur du rôle {role} ({agent}) est inconnu de {failover} ({exc!r})") from exc
    provider = str(target.get("effective") or target.get("provider") or "").strip() if isinstance(target, dict) else ""
    if not provider:
        raise LookupError(f"aucun fournisseur n'est donné au rôle {role} ({agent})")
    model = ""
    try:
        profile = (tomllib.loads((root / "city.toml").read_text(encoding="utf-8")).get("providers") or {}).get(provider) or {}
        args = [str(item) for item in profile.get("args_append") or []]
        if "--model" in args[:-1]:
            model = args[args.index("--model") + 1]
    except (OSError, ValueError):
        pass
    if not model:
        try:
            catalog = json.loads((root / "config" / "model-catalog.json").read_text(encoding="utf-8"))
            model = str((catalog["providers"][provider]["recommended"] or [""])[0])
        except (OSError, ValueError, KeyError, TypeError, IndexError):
            pass
    if not model.strip():
        raise LookupError(
            f"le modèle du fournisseur {provider} du rôle {role} est inconnu (city.toml, config/model-catalog.json)")
    return {"agent": agent, "provider": provider, "model": model.strip()}


def supplier_of(root: Path, provider: str) -> str:
    """Who supplies a provider profile: its pool, else the profile itself."""
    try:
        policy = json.loads((root / "config" / "provider-policy.json").read_text(encoding="utf-8"))
        pool = policy["providers"][provider]["pool"]
    except (OSError, ValueError, KeyError, TypeError):
        return provider
    return pool.strip() if isinstance(pool, str) and pool.strip() else provider


def role_supplier(root: Path, role: str) -> dict[str, object]:
    """`{provider, supplier, declared}` of the role now: `declared` maps each
    supplier of the role's chain to whether one of its providers is
    available. LookupError says what is unknown."""
    identity = role_identity(root, role)
    failover = os.environ.get("DELIVERY_ROLE_PROVIDER_FAILOVER_BIN") or str(root / "bin" / "provider-failover")
    declared: dict[str, bool] = {}
    try:
        status = subprocess.run([failover, "status", "--json"], capture_output=True, text=True, stdin=subprocess.DEVNULL)
        chain = json.loads(status.stdout)["targets"][identity["agent"]].get("chain") or []
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        chain = []
    for entry in chain if isinstance(chain, list) else []:
        name = entry.get("provider") if isinstance(entry, dict) else entry
        if not isinstance(name, str) or not name:
            continue
        pool = entry.get("pool") if isinstance(entry, dict) else None
        supplier = pool.strip() if isinstance(pool, str) and pool.strip() else supplier_of(root, name)
        available = not isinstance(entry, dict) or entry.get("state", "available") == "available"
        declared[supplier] = declared.get(supplier, False) or available
    return {"provider": identity["provider"], "supplier": supplier_of(root, identity["provider"]), "declared": declared}
