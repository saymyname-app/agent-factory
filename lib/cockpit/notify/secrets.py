"""Reads the Pushover secrets (app token, user key, E2E key) from the
single out-of-repo file on the Windows side (spec af-oohx2x
§"Notifications": "jeton d'app, clé utilisateur et clé E2E dans un seul
fichier hors dépôt côté Windows, lu par le cockpit via /mnt/c").

Never raises: a missing, unreadable, or malformed file returns ``None`` so
an absent or invalid secret surfaces as a health issue (AC6) instead of
crashing the notify engine -- the same contract as
:func:`cockpit.heartbeat.emitter.read_url_from_file`.
"""
import json

REQUIRED_KEYS = ("token", "user_key", "e2e_key")


def read_secrets_from_file(path):
    if not path:
        return None
    try:
        with open(path) as fh:
            raw = fh.read()
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    secrets = {key: data.get(key) for key in REQUIRED_KEYS}
    if not all(isinstance(value, str) and value for value in secrets.values()):
        return None
    return secrets
