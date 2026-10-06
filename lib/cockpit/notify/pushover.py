"""The single send adapter (spec af-oohx2x: "un seul adaptateur d'envoi
(Pushover, E2E). Changer de canal = changer l'adaptateur").

End-to-end encryption as Pushover's API documents it (pushover.net/api,
"End-to-End Encryption", read 2026-10-06). ``encrypted=1`` is sent and
each of ``title`` and ``message`` is encrypted on its own:

1. GZIP the plaintext;
2. a random 16-byte IV;
3. AES-256-CBC, PKCS7 padding, with the 256-bit key and that IV;
4. HMAC-SHA256 over IV + ciphertext, same key;
5. Base64 of IV + ciphertext + HMAC.

The key is the 64-character hex string the Pushover app shows. The first
version of this adapter sent AES-GCM in a ``ciphertext`` field the API
does not have, with a base64 key: no push could have arrived. Its tests
passed because they only ever drove a fake adapter.

AES goes through the ``openssl`` binary, exactly as the API's own example
does, so the cockpit needs no Python package for it. Without a valid key
this adapter refuses to send plaintext through a channel the spec says
must be end-to-end encrypted.
"""
import base64
import gzip
import hashlib
import hmac
import os
import re
import subprocess
import urllib.parse
import urllib.request

PUSHOVER_URL = "https://api.pushover.net/1/messages.json"

_KEY_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class PushoverError(Exception):
    pass


def valid_e2e_key(key):
    return isinstance(key, str) and bool(_KEY_RE.match(key))


def encrypt_field(key_hex, plaintext, openssl_bin="openssl"):
    """One field, encrypted as the API expects it."""
    key = bytes.fromhex(key_hex)
    iv = os.urandom(16)
    try:
        completed = subprocess.run(
            [openssl_bin, "enc", "-aes-256-cbc", "-K", key_hex, "-iv", iv.hex()],
            input=gzip.compress(plaintext.encode("utf-8")),
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PushoverError("chiffrement impossible : %s" % exc)
    if completed.returncode != 0:
        raise PushoverError("chiffrement impossible : openssl a échoué")
    ciphertext = completed.stdout
    mac = hmac.new(key, iv + ciphertext, hashlib.sha256).digest()
    return base64.b64encode(iv + ciphertext + mac).decode("ascii")


def default_post(url, form, timeout=10):
    """Raises on any non-2xx response or network failure (``urlopen``
    raises on a 4xx/5xx by itself) -- the caller records that as a failed
    send."""
    data = urllib.parse.urlencode(form).encode("utf-8")
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status >= 300:
            raise PushoverError("Pushover a répondu %s" % resp.status)


class PushoverAdapter:
    """``post`` and ``url`` are injectable so a test can point the real
    adapter at a fake Pushover server; production uses :func:`default_post`
    and :data:`PUSHOVER_URL`."""

    def __init__(self, secrets_loader, post=default_post, url=PUSHOVER_URL):
        self._secrets_loader = secrets_loader
        self._post = post
        self._url = url

    def e2e_available(self):
        secrets = self._secrets_loader()
        return bool(secrets and valid_e2e_key(secrets.get("e2e_key")))

    def send(self, title, message, priority):
        if priority not in (0, 1):
            raise PushoverError(
                "priorité Pushover invalide : %r (jamais 2 ni critical)" % (priority,)
            )
        secrets = self._secrets_loader()
        if not secrets:
            raise PushoverError("secrets Pushover manquants ou invalides")
        key = secrets.get("e2e_key")
        if not valid_e2e_key(key):
            raise PushoverError("clé E2E absente ou invalide — envoi refusé (canal doit être E2E)")
        form = {
            "token": secrets["token"],
            "user": secrets["user_key"],
            "priority": priority,
            "title": encrypt_field(key, title),
            "message": encrypt_field(key, message),
            "encrypted": 1,
        }
        self._post(self._url, form)
