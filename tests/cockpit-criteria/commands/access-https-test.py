#!/usr/bin/env python3
"""Criterion test 1 of I « Accès HTTPS sur la VM, veille de silence et
procédure de réglages opérateur » (af-cp4fzd; Spec af-fgcw0d, user story 93,
Implementation Decision « Accès hôte » : « Loopback, Tailscale Serve tailnet
seul, HTTPS, identité autorisée, POST/Origin/SameSite conservés. L'API
superviseur reste non exposée. […] aucun nouveau destinataire ni accès
public », Testing Decisions 1, 3 and 8).

The case launches the real cockpit with the launcher of the profile,
bin/project-launch, on health-content behind the synthetic identity proxy
(`https_identity_proxy`), as Tailscale Serve is in front of the cockpit in
service. The section « Accès » of GET /usine gives the HTTPS address of the
cockpit; through it:

- the operator's identity (synthetic@example.ts.net) is served the
  cockpit: its pages and its readings;
- another member of the tailnet, and a client outside the tailnet, are
  refused: no page, no reading;
- a POST without Origin, by the operator, with the session cookie the
  cockpit gave over HTTPS, is refused, whatever it asks -- a gesture, a
  reading of a section again, a check of the health again --, while the
  same POST with the cockpit's own Origin is taken;
- the API of the supervisor is not reached.

False if an access is public (a client outside the tailnet, an address
that is not the host's own), a new recipient is let in, or a POST without
Origin is accepted.
"""

from __future__ import annotations

import ipaddress
import re
import sys
import unittest
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from acces_vm import BENJAMIN, declare, page, section, text_of, through_https  # noqa: E402
from home_destination import LaunchTree  # noqa: E402

# Another member of the tailnet: not the operator.
OTHER = "autre@example.ts.net"
HTTPS_ADDRESS = re.compile(r"https://[^\s<>\"«»]+")
REFUSED = (401, 403)
# What every page of the cockpit says, in its navigation, and a refusal never
# does.
COCKPIT_PAGE = "Vue d’ensemble"
READINGS = ("/api/status", "/api/requests", "/api/health")
PAGES = ("/", "/usine")
# The POSTs a page of the cockpit sends: a gesture, a section read again,
# the health checked again.
POSTS = (
    ("/api/actions/acquitter", "application/json", b'{"bead_id": "af-x1y2z"}'),
    ("/api/usine/reverifier", "application/x-www-form-urlencoded", b"section=connexions"),
    ("/api/health/recheck", "application/x-www-form-urlencoded", b""),
)
# What the supervisor's API answers on (docs/COCKPIT.md).
SUPERVISOR_API = ("/v0/cities", "/v0/city/factory/status")


class AccessHttps(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def https_address(self, address: str) -> str:
        """The HTTPS address the section « Accès » of GET /usine gives."""
        status, source = page(address, "/usine")
        self.assertEqual(200, status, "GET /usine is not served on the host")
        acces = section(self, source, "Accès")
        found = HTTPS_ADDRESS.findall(acces["text"]) + [
            link["href"] for link in acces["links"] if link["href"].startswith("https://")]
        self.assertTrue(found, f"the section « Accès » gives no HTTPS address: {acces['text']}")
        return found[0].rstrip(".,;:)")

    # --- Criterion 1 ------------------------------------------------------------

    def test_through_https_the_operator_is_served_others_and_a_post_without_origin_refused(self):
        # The criterion names the GET of the operator, the GET of another
        # identity and the POST without Origin, with the supervisor not
        # exposed: one criterion observed whole.
        commit = declare(self.tree, "acces-https", "health-content", https_identity_proxy=True)
        address = self.tree.launch("acces-https", commit)
        url = self.https_address(address)
        self.assert_private(address, url)
        cookie = self.assert_the_operator_is_served(url)
        self.assert_others_are_refused(url)
        self.assert_a_post_without_origin_is_refused(url, cookie)
        self.assert_the_supervisor_is_not_exposed(url)

    def assert_private(self, address: str, url: str) -> None:
        """No public address: the cockpit and its HTTPS address are the host's
        own, and nothing is served outside the tailnet."""
        for served in (address, url):
            host = urllib.parse.urlsplit(served).hostname
            self.assertTrue(ipaddress.ip_address(host).is_loopback, f"{served} is not an address of the host alone")
        for path in PAGES + READINGS:
            answer = through_https(self, url, path, login=None)
            self.assertIn(answer.status, REFUSED, f"GET {path} from outside the tailnet is served: {answer}")
            self.assertNotIn(COCKPIT_PAGE, text_of(answer.body), f"GET {path} from outside the tailnet shows the cockpit")

    def assert_the_operator_is_served(self, url: str) -> str:
        """The operator is served every page and reading; returns the session
        cookie the cockpit gave, SameSite=Strict."""
        cookie = ""
        for path in PAGES:
            answer = through_https(self, url, path, login=BENJAMIN)
            self.assertEqual(200, answer.status, f"GET {path} is not served to the operator: {answer}")
            self.assertIn(COCKPIT_PAGE, text_of(answer.body), f"GET {path} through HTTPS does not show the cockpit")
            given = answer.headers.get("set-cookie") or ""
            if given:
                self.assertRegex(given, r"(?i)samesite=strict", f"the session cookie is not SameSite=Strict: {given}")
                cookie = given.split(";", 1)[0]
        self.assertTrue(cookie, "the cockpit gives no session cookie over HTTPS")
        for path in READINGS:
            answer = through_https(self, url, path, login=BENJAMIN)
            self.assertEqual(200, answer.status, f"GET {path} is not served to the operator: {answer}")
        return cookie

    def assert_others_are_refused(self, url: str) -> None:
        """Another member of the tailnet is not a new recipient: no page, no
        reading."""
        for path in PAGES + READINGS:
            answer = through_https(self, url, path, login=OTHER)
            self.assertIn(answer.status, REFUSED, f"GET {path} is served to {OTHER}: {answer}")
            self.assertNotIn(COCKPIT_PAGE, text_of(answer.body), f"GET {path} shows the cockpit to {OTHER}")
            self.assertNotIn('"freshness"', answer.body, f"GET {path} gives a reading to {OTHER}")

    def assert_a_post_without_origin_is_refused(self, url: str, cookie: str) -> None:
        """Each POST a page sends is refused without Origin, by the operator
        with the cookie of the session; with the cockpit's Origin the same
        reading of a section again is taken."""
        for path, kind, body in POSTS:
            answer = through_https(self, url, path, login=BENJAMIN, method="POST", data=body,
                                   headers={"Content-Type": kind, "Cookie": cookie})
            self.assertEqual(403, answer.status, f"POST {path} without Origin is not refused: {answer}")
        reread = POSTS[1]
        answer = through_https(self, url, reread[0], login=BENJAMIN, method="POST", data=reread[2],
                               headers={"Content-Type": reread[1], "Cookie": cookie, "Origin": url})
        self.assertIn(answer.status, (200, 303), f"POST {reread[0]} with the cockpit's Origin is not taken: {answer}")
        answer = through_https(self, url, reread[0], login=BENJAMIN, method="POST", data=reread[2],
                               headers={"Content-Type": reread[1], "Cookie": cookie,
                                        "Origin": "https://ailleurs.example"})
        self.assertEqual(403, answer.status, f"POST {reread[0]} from another Origin is not refused: {answer}")

    def assert_the_supervisor_is_not_exposed(self, url: str) -> None:
        for path in SUPERVISOR_API:
            answer = through_https(self, url, path, login=BENJAMIN)
            self.assertNotEqual(200, answer.status, f"the supervisor's API answers through HTTPS at {path}: {answer}")


if __name__ == "__main__":
    unittest.main()
