"""Tailscale key-expiry reader and the J-14 Operator Request it produces
(spec af-oohx2x §"Accès et sécurité (.2, .9)": "Clé Tailscale : expiration
par défaut gardée ; date lue par le statut Tailscale, demande À faire à
J-14."), ticket T25 (af-tzk0s4).

Reads only ``tailscale status --json`` (never Beads, never gc) so the
setup wizard and the access guard share the exact same status-reading
seam a test can fake -- no second parser of the same JSON, per the
project's "don't invent a second format" rule.
"""
import json
import subprocess
from datetime import datetime, timezone

from cockpit.requests.model import A_FAIRE, DEFAULT_PROJECT, OperatorRequest

# tailscale's sentinel for "this node's key does not expire" (zero time).
_NO_EXPIRY_SENTINEL = "0001-01-01T00:00:00Z"

WARNING_WINDOW_SECONDS = 14 * 24 * 3600  # J-14

TYPE_TAILSCALE_EXPIRY = "tailscale_key_expiry"

REQUEST_ID = "tailscale-key-expiry"

QUE_FAIRE = [
    {
        "lettre": "a",
        "option": "Renouveler la clé Tailscale (tailscale up, ou ré-authentifier l'appareil)",
        "consequence": "L'accès au cockpit depuis l'iPhone et le PC continue sans coupure",
        "recommande": True,
        "raison": "évite une coupure d'accès au cockpit",
    }
]

POURQUOI = "Après expiration, le cockpit devient inaccessible depuis l'iPhone et le PC"


def read_status(tailscale_bin="tailscale", run=subprocess.run):
    """Runs ``<tailscale_bin> status --json`` and returns the parsed JSON,
    or ``None`` on any failure (missing binary, non-zero exit, bad JSON) --
    never raises, same contract as the rest of the access/notify/heartbeat
    seams (a missing/failing tool becomes "no data", not a crash).

    ``run`` is injectable so a test never shells out to the real
    ``tailscale`` binary -- it points at a small fake CLI instead.
    """
    try:
        result = run(
            [tailscale_bin, "status", "--json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except ValueError:
        return None


def key_expiry_epoch(status):
    """Extracts ``Self.KeyExpiry`` from a ``tailscale status --json``
    payload as epoch seconds, or ``None`` when the status is missing,
    malformed, or the node's key never expires (the sentinel date)."""
    if not isinstance(status, dict):
        return None
    self_node = status.get("Self")
    if not isinstance(self_node, dict):
        return None
    raw = self_node.get("KeyExpiry")
    if not raw or raw == _NO_EXPIRY_SENTINEL:
        return None
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _format_date(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%d/%m/%Y")


def build_key_expiry_request(expiry_epoch, now, request_id=REQUEST_ID, lien=""):
    """Returns an "À faire" :class:`OperatorRequest` when the Tailscale
    key expires within the J-14 warning window (spec: "demande À faire à
    J-14"), or ``None`` otherwise (key unknown, never expires, or still
    more than 14 days away)."""
    if expiry_epoch is None:
        return None
    if expiry_epoch - now > WARNING_WINDOW_SECONDS:
        return None
    quoi = "La clé Tailscale expire le %s — renouvelle-la avant l'expiration" % _format_date(expiry_epoch)
    return OperatorRequest(
        id=request_id,
        type=TYPE_TAILSCALE_EXPIRY,
        niveau=A_FAIRE,
        quoi=quoi,
        pourquoi=POURQUOI,
        que_faire=[dict(option) for option in QUE_FAIRE],
        projet=DEFAULT_PROJECT,
        depuis_quand=now,
        verifie_a=now,
        lien=lien,
    )


def build_key_expiry_request_from_status(status, now, request_id=REQUEST_ID, lien=""):
    """Convenience wrapper combining :func:`key_expiry_epoch` and
    :func:`build_key_expiry_request` for a caller that only has the raw
    ``tailscale status --json`` payload."""
    return build_key_expiry_request(key_expiry_epoch(status), now, request_id=request_id, lien=lien)
