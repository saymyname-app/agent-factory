"""The runs of the cockpit (cockpit.runs, cockpit.ui.runs): a run read from
a ticket bead as the delivery flow leaves it, its status, its lanes, and
the pages /runs and /runs/run that draw them."""
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from cockpit.runs.derive import runs_from_beads  # noqa: E402
from cockpit.ui.runs.page import duration, render_run_page, render_runs_page  # noqa: E402


def ts(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()


def iso(text):
    return text


def bead(bead_id, status="in_progress", closed_at=None, **meta):
    metadata = {"gc.ticket_id": bead_id.upper(), "gc.spec_id": "af-spec",
                "gc.flow.gate.dispatch": json.dumps({"at": "2026-10-19T10:00:00Z"}),
                "gc.flow.models": json.dumps({
                    "author": {"agent": "delivery-author", "at": "2026-10-19T10:01:00Z", "model": "claude-opus-5-5"},
                    "reviewer": {"agent": "delivery-reviewer", "at": "2026-10-19T10:30:00Z", "model": "gpt-5.6-sol"},
                })}
    metadata.update({k.replace("__", "."): (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in meta.items()})
    out = {"id": bead_id, "status": status, "title": "%s — Une page" % bead_id.upper(), "metadata": metadata,
           "updated_at": "2026-10-19T12:00:00Z"}
    if closed_at:
        out["closed_at"] = closed_at
    return out


NOW = ts("2026-10-19T11:00:00Z")


class RunsTest(unittest.TestCase):
    def one(self, b):
        runs = runs_from_beads([b], NOW)
        self.assertEqual(len(runs), 1)
        return runs[0]

    def test_a_bead_no_agent_ran_on_is_no_run(self):
        self.assertEqual(runs_from_beads([{"id": "af-x", "status": "open", "metadata": {}}], NOW), [])

    def test_an_author_at_work_is_a_run_in_progress_up_to_now(self):
        run = self.one(bead("af-a"))
        self.assertEqual((run["status"], run["tone"]), ("En cours", "live"))
        self.assertIn("Auteur", run["step"])
        self.assertEqual(run["elapsed"], 3600)
        author = next(lane for lane in run["lanes"] if lane["name"] == "Auteur")
        self.assertEqual(author["jobs"], [(60, 3600)])
        self.assertEqual([lane["name"] for lane in run["lanes"][:2]], ["Humain", "Code"])

    def test_a_question_without_answer_waits_for_benjamin(self):
        run = self.one(bead("af-b", gc__flow__stop={"at": "2026-10-19T10:40:00Z", "reason": "still_refused",
                                                     "detail": "encore refusé"},
                            gc__escalation_horodatage="2026-10-19T10:41:00Z",
                            gc__escalation_pourquoi="Un ticket n'a qu'un tour"))
        self.assertEqual((run["status"], run["tone"]), ("Ta décision", "wait"))
        human = run["lanes"][0]
        self.assertEqual(human["jobs"], [(2460, 3600)])
        self.assertTrue(any("Question à Benjamin" in e["text"] for e in run["events"]))

    def test_an_answered_stop_is_stopped(self):
        run = self.one(bead("af-c", gc__flow__stop={"at": "2026-10-19T10:40:00Z", "detail": "encore refusé"},
                            gc__escalation_horodatage="2026-10-19T10:41:00Z",
                            gc__escalation_response_at="2026-10-19T10:50:00Z",
                            gc__escalation_response_option="b"))
        self.assertEqual(run["status"], "Arrêté")
        self.assertTrue(any(e["text"] == "Réponse de Benjamin : option b" for e in run["events"]))

    def test_merged_and_withdrawn_runs_are_finished(self):
        merged = self.one(bead("af-d", status="closed", closed_at="2026-10-19T10:55:00Z",
                               gc__flow__merge={"at": "2026-10-19T10:54:00Z", "outcome": "merged"}))
        self.assertEqual((merged["status"], merged["state"], merged["elapsed"]), ("Fusionné", "done", 3300))
        withdrawn = self.one(bead("af-e", status="closed", closed_at="2026-10-19T10:55:00Z",
                                  gc__flow__gate__withdrawn={"at": "2026-10-19T10:44:00Z"}))
        self.assertEqual(withdrawn["status"], "Abandonné")

    def test_review_rounds_and_evaluation_are_events(self):
        run = self.one(bead("af-f", gc__flow__code_review={"rounds": [
            {"at": "2026-10-19T10:45:00Z", "findings": [{"id": "F1.1", "blocking": True}, {"id": "F1.2"}]}]}))
        self.assertTrue(any(e["text"] == "Revue de code : 1 bloquant(s) F1.1" for e in run["events"]))
        reviewer = next(lane for lane in run["lanes"] if lane["name"] == "Relecteur")
        self.assertEqual(reviewer["jobs"], [(1800, 2700)])

    def test_the_list_filters_and_links_each_run(self):
        runs = runs_from_beads([bead("af-a"), bead("af-d", status="closed", closed_at="2026-10-19T10:55:00Z",
                                                  gc__flow__merge={"at": "2026-10-19T10:54:00Z", "outcome": "merged"})],
                               NOW)
        page = render_runs_page(runs, "en-cours")
        self.assertIn('href="/runs/run?id=af-a"', page)
        self.assertNotIn('href="/runs/run?id=af-d"', page)
        self.assertIn('href="/runs/run?id=af-d"', render_runs_page(runs, "termines"))
        self.assertIn("tracker injoignable", render_runs_page(None, "tous", error=True))

    def test_the_run_page_draws_its_lanes_and_events(self):
        run = self.one(bead("af-a"))
        page = render_run_page(run)
        self.assertIn("Frise du run", page)
        self.assertIn("Auteur · claude-opus-5-5", page)
        self.assertIn("Ticket lancé", page)
        self.assertIn("Run introuvable", render_run_page(None))

    def test_durations_read_at_a_glance(self):
        self.assertEqual(duration(492), "8 min 12 s")
        self.assertEqual(duration(22140), "6 h 09 min")
        self.assertEqual(duration(3 * 86400 + 4 * 3600), "3 j 4 h")


if __name__ == "__main__":
    unittest.main()
