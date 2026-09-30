#!/usr/bin/env python3

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "planning-map"
FAKE_BD = ROOT / "tests" / "fixtures" / "planning-map" / "bd"


class PlanningMapTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_path = Path(self.tmp.name) / "state.json"

    def invoke(self, *args, check=False):
        env = {
            **os.environ,
            "BD_BIN": str(FAKE_BD),
            "PLANNING_MAP_BD_STATE": str(self.state_path),
        }
        return subprocess.run(
            (str(TOOL), *args), env=env, text=True, capture_output=True, check=check,
        )

    def seed(self, beads, next_id=1):
        self.state_path.write_text(json.dumps({"beads": beads, "next_id": next_id}))

    def bead(self, **kwargs):
        base = {
            "labels": [],
            "metadata": {},
            "parent": None,
            "status": "open",
            "title": "",
            "description": "",
        }
        base.update(kwargs)
        return base

    def current_state(self):
        return json.loads(self.state_path.read_text())

    # --- create-ticket ---------------------------------------------------

    def test_create_ticket_carries_parent_single_label_and_planning_plane(self):
        self.seed({"map-1": self.bead(id="map-1", labels=["wayfinder:map"])})

        result = self.invoke(
            "create-ticket", "--map", "map-1", "--type", "research",
            "--title", "Which store backs the map?", "--body", "## Question\n\nWhich?\n",
            check=True,
        )
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        new_id = payload["id"]

        state = self.current_state()
        created = state["beads"][new_id]
        self.assertEqual(created["parent"], "map-1")
        self.assertEqual(created["labels"], ["wayfinder:research"])
        self.assertEqual(created["metadata"], {"gc.plane": "planning"})
        self.assertEqual(created["description"], "## Question\n\nWhich?\n")

    # --- check -------------------------------------------------------------

    def test_check_reports_finished_only_when_shaped_and_no_open_children(self):
        self.seed({
            "map-1": self.bead(id="map-1", labels=["wayfinder:map"]),
            "map-1.1": self.bead(
                id="map-1.1", parent="map-1", status="closed",
                labels=["wayfinder:research"], metadata={"gc.plane": "planning"},
            ),
        })

        result = self.invoke("check", "--map", "map-1", check=True)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["finished"])
        self.assertEqual(payload["open_children"], [])
        self.assertEqual(payload["malformed"], [])

    def test_check_names_each_wrongly_shaped_ticket_and_reports_unfinished(self):
        self.seed({
            "map-1": self.bead(id="map-1", labels=["wayfinder:map"]),
            "map-1.1": self.bead(
                id="map-1.1", parent="map-1", status="closed",
                labels=["wayfinder:research"], metadata={"gc.plane": "planning"},
            ),
            "map-1.2": self.bead(
                id="map-1.2", parent="map-1", status="closed",
                labels=["some-other-label"], metadata={"gc.plane": "delivery"},
            ),
            "map-1.3": self.bead(
                id="map-1.3", parent="map-1", status="open",
                labels=["wayfinder:task"], metadata={"gc.plane": "planning"},
            ),
        })

        result = self.invoke("check", "--map", "map-1", check=True)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["finished"])
        self.assertEqual(payload["open_children"], ["map-1.3"])
        malformed_ids = {entry["id"] for entry in payload["malformed"]}
        self.assertEqual(malformed_ids, {"map-1.2"})
        self.assertTrue(payload["malformed"][0]["problems"])

    def test_check_reports_map_not_labelled_wayfinder_map(self):
        self.seed({"map-1": self.bead(id="map-1", labels=["some-other-label"])})

        result = self.invoke("check", "--map", "map-1", check=True)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["labelled_map"])
        self.assertFalse(payload["finished"])

    # --- close ---------------------------------------------------------

    def test_close_closes_only_the_map(self):
        self.seed({
            "map-1": self.bead(id="map-1", labels=["wayfinder:map"]),
            "map-1.1": self.bead(
                id="map-1.1", parent="map-1", status="closed",
                labels=["wayfinder:research"], metadata={"gc.plane": "planning"},
            ),
        })

        result = self.invoke("close", "--map", "map-1", "--reason", "done", check=True)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["closed_children"], [])

        state = self.current_state()
        self.assertEqual(state["beads"]["map-1"]["status"], "closed")
        self.assertEqual(state["beads"]["map-1"]["close_reason"], "done")

    def test_close_abandon_closes_the_map_and_its_open_tickets_with_the_given_reason(self):
        self.seed({
            "map-1": self.bead(id="map-1", labels=["wayfinder:map"]),
            "map-1.1": self.bead(
                id="map-1.1", parent="map-1", status="open",
                labels=["wayfinder:research"], metadata={"gc.plane": "planning"},
            ),
            "map-1.2": self.bead(
                id="map-1.2", parent="map-1", status="closed",
                labels=["wayfinder:task"], metadata={"gc.plane": "planning"},
            ),
        })

        result = self.invoke(
            "close", "--map", "map-1", "--reason", "superseded", "--abandon", check=True,
        )
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["closed_children"], ["map-1.1"])

        state = self.current_state()
        self.assertEqual(state["beads"]["map-1"]["status"], "closed")
        self.assertEqual(state["beads"]["map-1"]["close_reason"], "superseded")
        self.assertEqual(state["beads"]["map-1.1"]["status"], "closed")
        self.assertEqual(state["beads"]["map-1.1"]["close_reason"], "superseded")
        # already-closed sibling is left alone, not re-closed with the new reason
        self.assertNotIn("close_reason", state["beads"]["map-1.2"])

    # --- update (compare-and-set) -----------------------------------------

    def test_update_writes_when_description_matches_the_callers_read(self):
        self.seed({"map-1": self.bead(id="map-1", labels=["wayfinder:map"], description="old\n")})

        result = self.invoke(
            "update", "--map", "map-1",
            "--expected-description", "old\n",
            "--body", "old\n\n- new decision\n",
            check=True,
        )
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])

        state = self.current_state()
        self.assertEqual(state["beads"]["map-1"]["description"], "old\n\n- new decision\n")

    def test_update_refuses_when_description_changed_since_the_callers_read(self):
        self.seed({"map-1": self.bead(id="map-1", labels=["wayfinder:map"], description="changed-by-sibling\n")})

        result = self.invoke(
            "update", "--map", "map-1",
            "--expected-description", "old\n",
            "--body", "old\n\n- new decision\n",
        )
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])

        state = self.current_state()
        self.assertEqual(state["beads"]["map-1"]["description"], "changed-by-sibling\n")


if __name__ == "__main__":
    unittest.main()
