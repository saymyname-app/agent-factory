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
