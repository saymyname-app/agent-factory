"""Shared helpers for the "other" request sources (T15) — kept here
instead of importing ``requests/builder.py``'s private ``_parse_iso``,
which is out of this ticket's declared scope."""
from datetime import datetime, timezone


def parse_iso(value):
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def copy_prompt_option(prompt_label):
    """The only ``que_faire`` shape these fixed-phrase types ever offer:
    a link (carried on the request's own ``lien``) plus a prompt to copy
    — never an execute button, because approving a Spec, approving or
    publishing a graph etc. are decisions of Benjamin's own level (spec
    .37) and the cockpit has no button for them anywhere (T13/T14's
    ``cockpit.actions.registry`` only ever registers acquitter, reporter,
    répondre, accepter/rejeter/reporter une proposition, relancer,
    continuer — none of them execute an approval)."""
    return [
        {
            "lettre": "a",
            "option": prompt_label,
            "consequence": "Rien ne change dans l'usine avant que tu agisses avec un agent.",
            "recommande": False,
            "raison": "",
        }
    ]
