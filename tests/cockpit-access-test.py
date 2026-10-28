"""Access-reliability tests for T25 (af-tzk0s4 — spec af-oohx2x §"Accès et
sécurité (.2, .9)", §"Faire confiance à l'affichage" .69).

Same precedent as tests/cockpit-heartbeat-test.py and
tests/cockpit-notify-test.py: :mod:`cockpit.access.tailscale` and
:mod:`cockpit.ui.base.page`'s disconnected-banner rendering have no CLI or
HTTP surface of their own (the HTTP wiring into the live home page is a
later ticket's job — out of this ticket's declared scope,
lib/cockpit/core/server.py), so this test drives their public functions
directly, with a fake ``tailscale status --json`` responder standing in
for the real binary and a fixed clock standing in for wall time. No test
here reaches a real Tailscale binary, Beads, or the network.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from cockpit.access.guard import (  # noqa: E402
    REFUSED_IDENTITY,
    REFUSED_METHOD,
    REFUSED_ORIGIN,
    ActionGuard,
)
from cockpit.access.tailscale import (  # noqa: E402
    WARNING_WINDOW_SECONDS,
    build_key_expiry_request,
    build_key_expiry_request_from_status,
    key_expiry_epoch,
    read_status,
)
from cockpit.requests.model import A_FAIRE  # noqa: E402
from cockpit.ui.base.page import (  # noqa: E402
    DISCONNECT_AFTER_SECONDS,
    GREYED_CLASS,
    render_disconnected_banner,
    render_home,
)


class FakeCompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def fake_run(stdout, returncode=0):
    def _run(cmd, **kwargs):
        return FakeCompletedProcess(returncode=returncode, stdout=stdout)

    return _run


def status_with_expiry(iso_expiry):
    return {"Self": {"KeyExpiry": iso_expiry, "Online": True}}


class TailscaleKeyExpiryTest(unittest.TestCase):
    # ------------------------------------------------------------------
    # AC2 — the J-14 "À faire" request for the Tailscale key's expiry.
    # ------------------------------------------------------------------
    def test_key_expiring_within_fourteen_days_is_an_a_faire_request(self):
        now = 1_000_000.0
        expiry = now + (10 * 24 * 3600)  # 10 days out — inside J-14
        request = build_key_expiry_request(expiry, now)

        self.assertIsNotNone(request)
        self.assertEqual(A_FAIRE, request.niveau)
        self.assertIn("clé Tailscale", request.quoi)
        self.assertIn("expire", request.quoi)
        self.assertTrue(request.que_faire, "que_faire must be non-empty")
        self.assertTrue(any(o["recommande"] for o in request.que_faire))

    def test_key_expiring_exactly_at_the_j14_boundary_is_a_request(self):
        now = 1_000_000.0
        expiry = now + WARNING_WINDOW_SECONDS  # exactly J-14
        request = build_key_expiry_request(expiry, now)
        self.assertIsNotNone(request)

    def test_key_expiring_well_beyond_fourteen_days_is_no_request_yet(self):
        now = 1_000_000.0
        expiry = now + (15 * 24 * 3600)
        self.assertIsNone(build_key_expiry_request(expiry, now))

    def test_no_expiry_known_produces_no_request(self):
        self.assertIsNone(build_key_expiry_request(None, 1_000_000.0))

    def test_key_that_never_expires_produces_no_request(self):
        # Tailscale's own sentinel for "expiry disabled".
        status = status_with_expiry("0001-01-01T00:00:00Z")
        self.assertIsNone(key_expiry_epoch(status))
        self.assertIsNone(build_key_expiry_request_from_status(status, 1_000_000.0))

    def test_reads_expiry_from_a_fake_tailscale_status_json(self):
        # 2026-10-10T00:00:00Z as epoch seconds.
        status_json = '{"Self": {"KeyExpiry": "2026-10-10T00:00:00Z"}}'
        status = read_status(tailscale_bin="tailscale", run=fake_run(status_json))
        self.assertIsNotNone(status)
        epoch = key_expiry_epoch(status)
        self.assertIsNotNone(epoch)

        # Just inside the window: "now" five days before expiry.
        request = build_key_expiry_request(epoch, epoch - 5 * 24 * 3600, lien="https://cockpit.local/acces")
        self.assertIsNotNone(request)
        self.assertEqual("https://cockpit.local/acces", request.lien)

    def test_a_failing_or_missing_tailscale_binary_reads_as_none_not_a_crash(self):
        self.assertIsNone(read_status(tailscale_bin="tailscale", run=fake_run("", returncode=1)))
        self.assertIsNone(read_status(tailscale_bin="tailscale", run=fake_run("not json")))

        def _raising_run(cmd, **kwargs):
            raise OSError("no such binary")

        self.assertIsNone(read_status(tailscale_bin="tailscale", run=_raising_run))

    def test_malformed_status_payload_produces_no_request(self):
        self.assertIsNone(key_expiry_epoch(None))
        self.assertIsNone(key_expiry_epoch({}))
        self.assertIsNone(key_expiry_epoch({"Self": "not-a-dict"}))
        self.assertIsNone(key_expiry_epoch({"Self": {"KeyExpiry": ""}}))


class DisconnectedBannerTest(unittest.TestCase):
    # ------------------------------------------------------------------
    # AC3 — "Déconnecté du cockpit depuis HH:MM" banner + greyed values
    # when the page stops receiving updates.
    # ------------------------------------------------------------------
    def test_connected_state_renders_a_hidden_placeholder(self):
        html_out = render_disconnected_banner(disconnected_since=None)
        self.assertIn("hidden", html_out)
        self.assertIn('data-state="connected"', html_out)
        self.assertNotIn("Déconnecté", html_out)

    def test_disconnected_state_renders_the_french_banner_with_the_time(self):
        # 2026-09-30 08:05:00 Paris (epoch computed via the PARIS tz used
        # by the module itself, exercised indirectly through formatting).
        from datetime import datetime
        from zoneinfo import ZoneInfo

        paris = ZoneInfo("Europe/Paris")
        when = datetime(2026, 9, 30, 8, 5, 0, tzinfo=paris)
        epoch = when.timestamp()

        html_out = render_disconnected_banner(disconnected_since=epoch)
        self.assertIn("Déconnecté du cockpit depuis 08:05", html_out)
        self.assertIn('data-state="disconnected"', html_out)
        self.assertNotIn("hidden", html_out)

    def test_render_home_embeds_the_banner_placeholder_and_the_poll_script(self):
        html_out = render_home("Tout est à jour à 08:00 (Paris)", [])
        self.assertIn("cockpit-disconnected-banner", html_out)
        self.assertIn("/api/status", html_out)
        self.assertIn(GREYED_CLASS, html_out)
        # The client-side threshold is present so a reviewer (and this
        # test) can see exactly what "stopped receiving updates" means —
        # no magic number hidden only in prose.
        self.assertIn(str(DISCONNECT_AFTER_SECONDS), html_out)

    def test_render_home_with_disconnected_since_shows_the_banner_up_front(self):
        html_out = render_home("Tout est à jour à 08:00 (Paris)", [], disconnected_since=1_700_000_000.0)
        self.assertIn("Déconnecté du cockpit depuis", html_out)
        # The banner markup appears before the freshness headline — "above
        # everything" (spec .69).
        banner_pos = html_out.index('id="cockpit-disconnected-banner"')
        headline_pos = html_out.index('class="fresh cockpit-headline"')
        self.assertLess(banner_pos, headline_pos)


# The operator, the origin of the cockpit behind Serve, and a token (I,
# af-cp4fzd).
OPERATOR = "benjamin@example.ts.net"
COCKPIT_ORIGIN = "https://usine.example.ts.net"


class ReaderGuardTest(unittest.TestCase):
    """Who may read the cockpit through Tailscale Serve (I, af-cp4fzd; Spec
    af-fgcw0d « Accès hôte » : « identité autorisée […] aucun nouveau
    destinataire »)."""

    def setUp(self):
        self.guard = ActionGuard(OPERATOR, COCKPIT_ORIGIN, "jeton")

    def test_the_operator_behind_serve_reads(self):
        self.assertTrue(self.guard.check_reader({"Tailscale-User-Login": OPERATOR}))

    def test_another_member_of_the_tailnet_is_refused(self):
        result = self.guard.check_reader({"Tailscale-User-Login": "autre@example.ts.net"})
        self.assertEqual((False, REFUSED_IDENTITY), (result.allowed, result.reason))

    def test_a_request_of_the_host_itself_reads(self):
        # Without the header of Serve, the request came from loopback.
        self.assertTrue(self.guard.check_reader({}))


class PagePostGuardTest(unittest.TestCase):
    """The POSTs a page sends that are no Operator Action -- a section read
    again, the health checked again (I, af-cp4fzd; Spec af-fgcw0d « Accès
    hôte » : « POST/Origin/SameSite conservés »)."""

    def setUp(self):
        self.guard = ActionGuard(OPERATOR, COCKPIT_ORIGIN, "jeton")

    def check(self, method="POST", **headers):
        result = self.guard.check_page_post(method, {"Tailscale-User-Login": OPERATOR, **headers})
        return result.allowed, result.reason

    def test_with_the_origin_of_the_cockpit_it_is_taken(self):
        self.assertEqual((True, ""), self.check(Origin=COCKPIT_ORIGIN))

    def test_without_origin_it_is_refused(self):
        self.assertEqual((False, REFUSED_ORIGIN), self.check())

    def test_from_another_origin_it_is_refused(self):
        self.assertEqual((False, REFUSED_ORIGIN), self.check(Origin="https://ailleurs.example"))

    def test_another_method_is_refused(self):
        self.assertEqual((False, REFUSED_METHOD), self.check("GET", Origin=COCKPIT_ORIGIN))

    def test_another_member_of_the_tailnet_is_refused_even_with_the_origin(self):
        result = self.guard.check_page_post("POST", {"Tailscale-User-Login": "autre@example.ts.net",
                                                     "Origin": COCKPIT_ORIGIN})
        self.assertEqual((False, REFUSED_IDENTITY), (result.allowed, result.reason))


if __name__ == "__main__":
    unittest.main()
