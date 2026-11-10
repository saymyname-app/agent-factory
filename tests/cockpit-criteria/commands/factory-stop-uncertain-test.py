#!/usr/bin/env python3
"""Criterion test 1 of R15 « Arrêt et reprise soumis à l'issue incertaine
commune » (af-0ilk7e; Blocking Finding F1.24 of the end review on
96b3429f0dee; Spec af-fgcw0d, user stories 122 and 174, Implementation
Decision 6 : « L'expiration et l'issue incertaine d'une commande […] sont
corrigées dans le mécanisme commun d'exécution des actions, une seule
fois, avant les lots qui ajoutent des gestes d'écriture (… arrêt/reprise) »,
Testing Decisions 1, 4 and 8): « Demander la suspension » on a supervisor
that does not answer, POST /api/actions/arreter twice in a row.

The case launches the real cockpit with the launcher of the profile,
bin/project-launch, on health-content with a synthetic supervisor the case
writes (usine_arret.serve_stop): a session at work on a ticket, the
supervisor reading as in service, but answering no write -- it records each
one it receives, applies none and never answers it (`unanswered_writes`), as
a supervisor that stops answering between a reading and a command. The
gesture is sent as the browser sends it from a page the cockpit served,
behind the identity proxy of the host (usine_arret.Operator); what the
cockpit asked of the supervisor is what it recorded (usine_arret.written).

False if the second POST reaches the supervisor again before the source was
read again (a second write recorded), if the first answer is no readable
uncertain outcome, or if the gesture stays refused once the supervisor was
read again.
"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree  # noqa: E402
from usine_arret import Operator, serve_stop, wait_for, written  # noqa: E402

AUTHOR = {"session": "auteur-recus", "role": "Auteur", "ticket": "tk-recus", "title": "Trier les reçus du mois"}
ASK = {"confirm": True}
SUSPENDED_WRITE = ("PATCH", "", {"suspended": True})
# How long the cockpit may take to read its supervisor again after an
# uncertain outcome: it reads it every second in a launch.
REREAD_SECONDS = 25


class FactoryStopUncertain(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        # A tree of its own: serve_stop commits the dataset of the case in it.
        self.tree = LaunchTree()

    def tearDown(self) -> None:
        self.tree.remove()

    def assert_readable_uncertain(self, answer) -> None:
        """An HTTP answer, an error that is no crash of the cockpit, and an
        error in words that says the outcome is uncertain."""
        self.assertEqual("", answer.broken, f"the request broke: {answer}")
        self.assertIsNotNone(answer.status, f"no HTTP answer: {answer}")
        self.assertGreaterEqual(answer.status, 400, f"a stop the supervisor did not answer is said done: {answer}")
        self.assertNotEqual(500, answer.status, f"the cockpit broke on a supervisor that did not answer: {answer}")
        self.assertIsInstance(answer.body, dict, f"the answer is no readable error: {answer}")
        self.assertRegex(answer.error(), r"(?i)incertain", f"the error does not say the outcome is uncertain: {answer}")
        self.assertNotRegex(answer.error(), r"Traceback|StopUncertain|Errno|timed out",
                            f"the error is not readable: {answer}")

    def test_a_stop_the_supervisor_did_not_answer_is_uncertain_then_not_sent_again_before_it_is_read_again(self):
        address, writes = serve_stop(self.tree, "health-content", {"work": [AUTHOR], "unanswered_writes": True})
        operator = Operator(address)

        first = operator.gesture("arreter", ASK)
        self.assertEqual([SUSPENDED_WRITE], written(writes), "the suspension was not asked of the supervisor, once")
        self.assert_readable_uncertain(first)

        # At once, the same gesture: refused, and nothing written again.
        second = operator.gesture("arreter", ASK)
        self.assertEqual([SUSPENDED_WRITE], written(writes),
                         "the second POST reached the supervisor again before it was read again")
        self.assertEqual("", second.broken, f"the request broke: {second}")
        self.assertIsNotNone(second.status, f"no HTTP answer: {second}")
        self.assertGreaterEqual(second.status, 400, f"the second POST is said done: {second}")
        self.assertNotEqual(500, second.status, f"the cockpit broke: {second}")
        self.assertIsInstance(second.body, dict, f"the answer is no readable error: {second}")
        self.assertTrue(second.error().strip(), f"the gesture refused says nothing: {second}")

        # Once the supervisor was read again -- still running, the stop never
        # applied --, the gesture goes again, and is uncertain again.
        tried = time.monotonic()
        again = wait_for(lambda: operator.gesture("arreter", ASK), lambda _: len(written(writes)) >= 2,
                         REREAD_SECONDS, interval=1)
        self.assertEqual([SUSPENDED_WRITE, SUSPENDED_WRITE], written(writes),
                         f"the gesture stays refused {time.monotonic() - tried:.0f} s after the uncertain outcome, "
                         f"the supervisor read again since: {again}")
        self.assert_readable_uncertain(again)


if __name__ == "__main__":
    unittest.main()
