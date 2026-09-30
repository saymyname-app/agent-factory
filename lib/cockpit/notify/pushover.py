"""The single send adapter (spec af-oohx2x: "un seul adaptateur d'envoi
(Pushover, E2E). Changer de canal = changer l'adaptateur"). This is the
real one, exercised only during the manual Pushover setup step (spec
§"Étapes à la main de Benjamin") -- every automated test in
tests/cockpit-notify-test.py drives
:class:`~cockpit.notify.engine.NotificationEngine` against a fake adapter
that records instead (Testing Decisions: "aucun test n'atteint [...]
Pushover").

E2E: Pushover's end-to-end encryption scheme encrypts title+message with
the app's 32-byte E2E key (AES-256-GCM, a random 12-byte nonce prefixed to
the ciphertext, the whole thing base64-encoded into a single
``ciphertext`` form field replacing plain ``title``/``message``). Without
an E2E key configured, this adapter refuses to send plaintext through a
channel the spec says must be E2E -- see :meth:`PushoverAdapter.send`.
"""
import base64
import json
import os
import urllib.parse
import urllib.request

PUSHOVER_URL = "https://api.pushover.net/1/messages.json"


class PushoverError(Exception):
    pass


def _encrypt(e2e_key, title, message):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = base64.b64decode(e2e_key)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    plaintext = json.dumps({"title": title, "message": message}).encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def default_post(url, form, timeout=10):
    """Raises on any non-2xx response or network failure -- the caller
    (:class:`PushoverAdapter`) is the one that turns that into a recorded
    failure."""
    data = urllib.parse.urlencode(form).encode("utf-8")
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status >= 300:
            raise PushoverError("Pushover a répondu %s" % resp.status)


class PushoverAdapter:
    """``post`` is injectable so a manual smoke test can swap in a logger
    without touching the network; production always uses
    :func:`default_post`."""

    def __init__(self, secrets_loader, post=default_post):
        self._secrets_loader = secrets_loader
        self._post = post

    def e2e_available(self):
        secrets = self._secrets_loader()
        return bool(secrets and secrets.get("e2e_key"))

    def send(self, title, message, priority):
        if priority not in (0, 1):
            raise PushoverError(
                "priorité Pushover invalide : %r (jamais 2 ni critical)" % (priority,)
            )
        secrets = self._secrets_loader()
        if not secrets:
            raise PushoverError("secrets Pushover manquants ou invalides")
        form = {"token": secrets["token"], "user": secrets["user_key"], "priority": priority}
        if not secrets.get("e2e_key"):
            raise PushoverError("clé E2E manquante — envoi refusé (canal doit être E2E)")
        form["ciphertext"] = _encrypt(secrets["e2e_key"], title, message)
        self._post(PUSHOVER_URL, form)
