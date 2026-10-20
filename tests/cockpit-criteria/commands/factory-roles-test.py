#!/usr/bin/env python3
"""Criterion test 3 of G1 « Usine — observation, fraîcheur et rôles réels »
(af-wrxrmg; Spec af-fgcw0d, user stories 161 and 162, Testing Decisions 1
and 8): the roles of the destination Usine and the descending drawing of
the delivery flow, on the dataset health-content. How the page renders on
the other datasets of the criterion is in factory-layout-*-test.py.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on health-content -- at a commit where the dataset says
other names and figures than the prototype's, where the Factory's own
configuration says other ones (config/provider-policy.json,
config/delivery-flow.json, city.toml), or where the host holds what the
provider failover observed (.gc/provider-state.json) -- and reads the page GET /usine as a
headless Chromium renders it, before and after a role of the drawing was
selected, by a click or by the keyboard (usine_page.py). The detail of
the role selected is the part that holds its heading (`<h3>`).

The configuration the cases expect is that of the Factory's files at the
start commit of the ticket: the author on Claude Opus 5.5 at medium effort,
two author sessions at most; the reviewer on Codex GPT-5.6 Sol, then Claude
as fallback, one session; the evaluator on Claude Opus 5.5 with no
fallback.

The reference (prototype/cockpit-b-zones-20261012 at 632deea,
prototypes/c01-complete/frozen-panorama-factory/states/health-content.html)
draws its sections in this order, and its flow downwards: the deterministic
controller, the author, the reviewer and the evaluator, the integration,
the owner's judgment.

False if a name or a figure of the prototype is shown as the real
configuration, if the page does not follow a change of the configuration,
if the configuration is not told apart from what is observed -- the
availability the failover observed, or that none was --, if a role of the
drawing cannot be selected, or if the sections or the flow are not in the
order of the reference.
"""

from __future__ import annotations

import json
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from usine_page import (  # noqa: E402
    GPT_5_6, OPUS_5_5, PAGE, LaunchTree, anchors_by_name, in_order, measure, observed, reconfigure, replaced, says,
    section_titled, section_titles,
)

FLOW = "flow-down-1"
# The sections of the reference's state health-content, in its order.
REFERENCE_SECTIONS = ["Machine d’exécution", "Connexions", "Fournisseurs et accès API", "Agents dans le workflow",
                      "Suspension, reprise et arrêt", "Nettoyer les espaces inutilisés"]


def json_edit(change):
    """An edit of a JSON file: `change` alters the document it is given."""
    def edit(text: str) -> str:
        document = json.loads(text)
        change(document)
        return json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    return edit


def in_flow(frame: dict, control: dict) -> bool:
    by_name = anchors_by_name(frame)
    anchor = control["anchor"]
    return anchor == FLOW or (anchor in by_name and FLOW in by_name[anchor]["chain"])


def selected(control: dict) -> bool:
    state = control["state"]
    return state["pressed"] == "true" or state["selected"] == "true" or state["current"] not in (None, "false")


class FactoryRoles(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def select(self, address: str, role: str, keys: bool = False) -> str:
        """Selects in the drawing of the flow the first role whose name says
        `role` -- clicked, or focused and Enter pressed with `keys` -- and
        returns the text of its detail, once its selection is drawn."""
        frame = measure(address, PAGE)[0]
        self.assertIn(FLOW, anchors_by_name(frame), "the page has no drawing of the flow")
        roles = [control for control in frame["controls"] if role in control["name"] and in_flow(frame, control)]
        self.assertTrue(roles, f"no role « {role} » can be selected in the drawing of the flow")
        name = roles[0]["name"]
        after = measure(address, PAGE, click=name, keys=keys)[0]["after"]
        self.assertTrue(after["found"], f"« {name} » is not on the page")
        now = [control for control in after["controls"] if control["name"] == name]
        self.assertTrue(now and selected(now[0]), f"« {name} » is not drawn selected once activated")
        by_name = anchors_by_name(after)
        headings = [anchor for anchor in after["anchors"]
                    if anchor["tag"] == "h3" and role in says(after, anchor["name"]) and anchor["chain"]]
        self.assertTrue(headings, f"no detail headed « {role} » once « {name} » is selected")
        holder = headings[0]["chain"][0]
        self.assertIn(holder, by_name)
        return says(after, holder)

    def test_the_roles_and_their_flow_are_those_of_the_configuration_not_the_prototype(self):
        # The dataset says the prototype's names and figures; at this commit
        # it says ones no configuration of the Factory holds.
        commit = self.tree.reword("health-content", {
            "Opus 5.5": "Modèle-de-prototype",
            "2 sessions maximum": "97 sessions maximum",
            "Relire les tests": "Étape-de-prototype",
            "lue le 12 octobre": "lue le 31 février",
        })
        address = self.tree.launch("health-content", commit)
        frame = measure(address, PAGE)[0]
        self.assertIn(FLOW, anchors_by_name(frame), "the page has no drawing of the flow")
        flow = says(frame, FLOW)
        self.assertIn("déterministe", flow, "the drawing does not tell the deterministic controller apart")
        roles = [control["name"] for control in frame["controls"] if in_flow(frame, control)]
        for role in ("Auteur", "Relecteur", "Évaluateur"):
            self.assertTrue([name for name in roles if role in name],
                            f"the drawing has no role « {role} » to select: {roles}")
        downwards = [flow.find(said) for said in ("déterministe", "Auteur", "Relecteur", "Évaluateur", "Intégration",
                                                  "jugement")]
        self.assertNotIn(-1, downwards, f"the drawing does not show every step of the flow: « {flow} »")
        self.assertEqual(sorted(downwards), downwards, f"the drawing is not in the order of the flow: « {flow} »")
        self.assertEqual([], in_order(REFERENCE_SECTIONS, section_titles(frame)),
                         "sections of the reference missing or out of its order")
        _, agents = section_titled(self, frame, "Agents dans le workflow")
        self.assertRegex(agents, GPT_5_6, "the reviewer is not shown on the model its configuration names")
        self.assertRegex(agents, OPUS_5_5, "the author is not shown on the model its configuration names")
        self.assertIn("Relecteur UX", agents, "the roles outside the flow are not shown")
        self.assertEqual([], [said for said in ("Modèle-de-prototype", "97 sessions", "Étape-de-prototype",
                                                "31 février") if said in frame["text"]],
                         "a name or a figure of the dataset is shown as the configuration")

    def test_selecting_the_reviewer_shows_its_configuration_apart_from_what_is_observed(self):
        address = self.tree.launch("health-content")
        detail = self.select(address, "Relecteur")
        self.assertRegex(detail, GPT_5_6, "the reviewer's configured model is not said")
        self.assertRegex(detail, r"(?i)claude|opus", "the reviewer's fallback is not said")
        self.assertRegex(detail, r"\b(1|une) session", "the reviewer's limit of sessions is not said")
        self.assertIn("configur", detail.lower(), "the detail does not say what is configured")
        self.assertLess(-1, detail.lower().find("configuration"))
        self.assertLess(detail.lower().find("configuration"), detail.lower().find("observé"),
                        "the detail does not say what is configured, then what is observed apart")
        self.assertIn("Disponibilité observée non observée sur cet hôte", detail,
                      "the launched tree holds no state of the failover, and the detail does not say so")

    def test_selecting_the_evaluator_by_the_keyboard_shows_its_configuration(self):
        address = self.tree.launch("health-content")
        detail = self.select(address, "Évaluateur", keys=True)
        self.assertRegex(detail, OPUS_5_5, "the evaluator's configured model is not said")
        self.assertIn("aucun secours", detail.lower(), "the evaluator has no fallback, and it is not said")
        self.assertIn("Disponibilité observée", detail, "the detail does not say the availability observed, apart")

    def test_what_the_failover_observed_is_the_availability_shown_apart_from_the_configuration(self):
        # The host's failover detected that the Anthropic pool is exhausted
        # for ten hours more.
        until = datetime.fromtimestamp(time.time() + 10 * 3600, tz=timezone.utc)
        commit = observed(self.tree, {".gc/provider-state.json": json.dumps({
            "contract": "agent-factory-provider-state/v1",
            "pools": {"anthropic": {"status": "exhausted", "source": "detected",
                                    "until": until.strftime("%Y-%m-%dT%H:%M:%SZ")}},
        })})
        address = self.tree.launch("health-content", commit)
        frame = measure(address, PAGE)[0]
        _, providers = section_titled(self, frame, "Fournisseurs et accès API")
        self.assertRegex(providers, r"Anthropic[^·]*· Claude.*Quota épuisé jusqu’à \d{2}:\d{2}",
                         "the pool the failover found exhausted is not said exhausted")
        self.assertRegex(providers, r"OpenAI.*Aucune limite détectée", "the pool the failover found nothing of is "
                         "not said so")
        detail = self.select(address, "Évaluateur")
        self.assertRegex(detail, OPUS_5_5, "the evaluator's configured model is not said")
        self.assertRegex(detail, r"Disponibilité observée Claude Opus 5\.5 : quota épuisé jusqu’à \d{2}:\d{2}",
                         "the evaluator's provider is not said exhausted, as the failover observed")

    def test_a_change_of_the_configuration_is_what_the_page_says(self):
        def flow(document):
            document["max_sessions"] = 6
            document["max_reviewer_sessions"] = 3
            document["bounds"]["end_rounds"] = 5

        def policy(document):
            document["targets"]["delivery-reviewer"]["chain"] = ["claude-readonly", "codex-readonly"]

        commit = reconfigure(self.tree, {
            "config/delivery-flow.json": json_edit(flow),
            "config/provider-policy.json": json_edit(policy),
            "city.toml": replaced('effort = "medium"', 'effort = "low"'),
        })
        address = self.tree.launch("health-content", commit)
        author = self.select(address, "Auteur")
        self.assertRegex(author, r"\b(6|six) sessions", "the authors' limit of sessions configured is not said")
        self.assertRegex(author, r"\b(5|cinq) tours de fin", "the end rounds configured are not said")
        self.assertRegex(author, r"(?i)\b(faible|bas|low)\b", "the author's effort configured is not said")
        reviewer = self.select(address, "Relecteur")
        self.assertRegex(reviewer, OPUS_5_5, "the reviewer's model, first of its chain, is not said")
        self.assertRegex(reviewer, GPT_5_6, "the reviewer's fallback, second of its chain, is not said")
        self.assertLess(OPUS_5_5.search(reviewer).start(), GPT_5_6.search(reviewer).start(),
                        "the reviewer's chain is not said in its order")
        self.assertRegex(reviewer, r"\b(3|trois) sessions", "the reviewer's limit of sessions configured is not said")


if __name__ == "__main__":
    unittest.main()
