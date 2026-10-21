"""Roadmap step and « dev a N commits d'avance », through the running
process (af-mjfvwx; spec af-oohx2x §"Données de projet", .39, .42, .48).

T19/T20 built the roadmap and promotion readers against a clone a test
had made; nothing made the cockpit's clones or called the readers. Here
the real ``bin/cockpit`` clones throwaway local repositories (the "faux
clone git de projet" of the Testing Decisions: real git, no network) and
the test reads only ``GET /``, ``GET /projet/<id>`` and the JSON twins.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "core"
ACTIONS_FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "actions"
COCKPIT_BIN = ROOT / "bin" / "cockpit"

sys.path.insert(0, str(CORE_FIXTURES))

from fake_gc import FakeGc  # noqa: E402

WAIT_SECONDS = 30
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}

ROADMAP = (
    '[[step]]\nid = "A1"\ntitle = "Un"\ndone_when = "x"\norder = 1\nstatus = "done"\n'
    '[[step]]\nid = "A2"\ntitle = "Bêta privée"\ndone_when = "y"\norder = 2\nstatus = "in_progress"\n'
    '[[step]]\nid = "A3"\ntitle = "Trois"\ndone_when = "z"\norder = 3\nstatus = "todo"\n'
)


def git(cwd, *args):
    return subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True, env={**os.environ, **GIT_ENV},
    ).stdout


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_port(host, port, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise TimeoutError("nothing listening on %s:%d after %ss" % (host, port, timeout))


def wait_until(predicate, timeout=WAIT_SECONDS, interval=0.1):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval)
    raise AssertionError("condition not met within %ss (last=%r)" % (timeout, last))


class Origins:
    """Throwaway "origin" repositories, addressed as ``owner/name``."""

    def __init__(self, root):
        self.root = root

    def path(self, repo):
        return self.root / (repo + ".git")

    def create(self, repo):
        path = self.path(repo)
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "--quiet", "--bare", str(path)], check=True, capture_output=True)
        git(path, "symbolic-ref", "HEAD", "refs/heads/main")
        return path

    def commit(self, repo, branch, files, base=None):
        """One commit on ``branch`` of ``repo`` (``files``: name -> text)."""
        work = self.root / ("work-%d" % len(list(self.root.glob("work-*"))))
        subprocess.run(["git", "clone", "--quiet", str(self.path(repo)), str(work)], check=True, capture_output=True)
        refs = git(work, "branch", "-r")
        if ("origin/" + branch) in refs:
            git(work, "checkout", "--quiet", "-B", branch, "origin/" + branch)
        elif base and ("origin/" + base) in refs:
            git(work, "checkout", "--quiet", "-B", branch, "origin/" + base)
        else:
            git(work, "checkout", "--quiet", "-B", branch)
        for name, text in files.items():
            (work / name).write_text(text)
        git(work, "add", "-A")
        git(work, "commit", "--quiet", "-m", "commit")
        git(work, "push", "--quiet", "origin", "HEAD:refs/heads/" + branch)

    def sha(self, repo, branch):
        return git(self.path(repo), "rev-parse", "refs/heads/" + branch).strip()

    def promote(self, repo, source, target):
        """What a promotion does on origin: ``target`` moves up to ``source``."""
        git(self.path(repo), "update-ref", "refs/heads/" + target, self.sha(repo, source))

    def refs(self):
        return {
            str(p.relative_to(self.root)): git(p, "for-each-ref", "--format=%(refname) %(objectname)")
            for p in sorted(self.root.glob("org/*.git"))
        }


class DepotsTest(unittest.TestCase):
    def setUp(self):
        self.fake_gc = FakeGc().start()
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.port = free_port()
        self.proc = None
        self.origins = Origins(self.dir / "origins")
        self.clones = self.dir / "clones"

        # "demo": a structured roadmap, one rig promoted from dev to main, dev 3 commits ahead.
        self.origins.create("org/demo-knowledge")
        self.origins.commit("org/demo-knowledge", "main", {"roadmap.toml": ROADMAP})
        self.origins.create("org/demo-back")
        self.origins.commit("org/demo-back", "main", {"a.txt": "a"})
        for i in range(3):
            self.origins.commit("org/demo-back", "dev", {"d%d.txt" % i: "d"}, base="main")
        # "brut": a knowledge repository with no structured roadmap yet.
        self.origins.create("org/brut-knowledge")
        self.origins.commit("org/brut-knowledge", "main", {"roadmap.md": "prose"})

        descriptors = self.dir / "descriptors"
        descriptors.mkdir()
        for project_id, name, repo, rigs, promotion in (
            ("demo", "Démo", "org/demo-knowledge", ["demo-back"], {"demo-back": {"from": "dev", "to": "main"}}),
            ("brut", "Brut", "org/brut-knowledge", ["brut-rig"], {}),
        ):
            (descriptors / (project_id + ".json")).write_text(json.dumps({
                "contract": "agent-factory-project-descriptor/v1", "project_id": project_id, "display_name": name,
                "rigs": rigs, "knowledge_repo": repo, "roadmap_path": "roadmap.toml",
                "rituals_status_command": "", "promotion_branch": promotion,
            }))
        rig_files = self.dir / "rig-files"
        rig_files.mkdir()
        (rig_files / "demo-back.toml").write_text('repo = "org/demo-back"\nprotected_branch = "dev"\n')
        self.descriptors, self.rig_files = descriptors, rig_files

        self.state_file = self.dir / "beads.json"
        self.state_file.write_text(json.dumps([
            # A chantier in delivery that targets a roadmap step already marked done (spec .48).
            {"id": "af-conv1", "title": "Export des listes", "status": "open", "issue_type": "convoy",
             "labels": ["approved-ticket-graph"], "notes": "",
             "metadata": {"gc.graph_digest": "sha256:a", "gc.project_id": "demo", "planning_run_target": "A1"}},
            {"id": "af-tk1", "title": "t", "status": "open", "issue_type": "task",
             "labels": ["approved-ticket-graph", "delivery-plane"], "notes": "",
             "metadata": {"gc.graph_digest": "sha256:a", "gc.dispatch_rig": "demo-back"}},
        ]))

    def tearDown(self):
        if self.proc is not None:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=5)
            self.proc.stdout.close()
            self.proc.stderr.close()
        self.fake_gc.stop()
        self.tmp.cleanup()

    def start_cockpit(self, with_clones=True):
        env = dict(os.environ)
        env.update(
            {
                "COCKPIT_HOST": "127.0.0.1",
                "COCKPIT_PORT": str(self.port),
                "COCKPIT_GC_BASE_URL": self.fake_gc.base_url,
                "COCKPIT_GC_STATUS_POLL_SECONDS": "0.1",
                "COCKPIT_GC_RECONNECT_SECONDS": "0.1",
                "COCKPIT_SESSIONS_POLL_SECONDS": "0.2",
                "COCKPIT_BD_BIN": str(ACTIONS_FIXTURES / "fake-bd"),
                "COCKPIT_PID_FILE": str(self.dir / "cockpit.pid"),
                "COCKPIT_BEADS_POLL_SECONDS": "0.2",
                "COCKPIT_PROJECTS_POLL_SECONDS": "0.2",
                "COCKPIT_JOURNAL_POLL_SECONDS": "0.2",
                "COCKPIT_DESCRIPTORS_DIR": str(self.descriptors),
                "COCKPIT_RIG_FILES_DIR": str(self.rig_files),
                "COCKPIT_REPO_URL_TEMPLATE": "file://" + str(self.origins.root) + "/%s.git",
                "COCKPIT_DEPOTS_POLL_SECONDS": "0.4",
                "FAKE_BD_STATE_FILE": str(self.state_file),
                "FAKE_BD_CALLS_FILE": str(self.dir / "calls.jsonl"),
                "FAKE_BD_FAIL_FLAG_FILE": str(self.dir / "fail"),
            }
        )
        if with_clones:
            env["COCKPIT_CLONES_DIR"] = str(self.clones)
        else:
            env.pop("COCKPIT_CLONES_DIR", None)
        self.proc = subprocess.Popen(
            [sys.executable, str(COCKPIT_BIN), "run"],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        wait_for_port("127.0.0.1", self.port)

    def get(self, path):
        with urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.port, path), timeout=5) as resp:
            raw = resp.read().decode("utf-8")
            if resp.headers.get("Content-Type", "").startswith("application/json"):
                return json.loads(raw)
            return raw

    def project_block(self, body, project_id):
        start = body.index('data-project="%s"' % project_id)
        end = body.find('<div class="proj cockpit-project', start)
        return body[start:end if end != -1 else body.index("</section>", start)]

    # ------------------------------------------------------------------
    def test_roadmap_step_and_commits_ahead_are_read_from_the_cockpits_own_clones(self):
        origin_refs = self.origins.refs()
        self.start_cockpit()
        body = wait_until(lambda: self.get("/") if "Roadmap : Bêta privée" in self.get("/") else None)

        demo = self.project_block(body, "demo")
        self.assertIn("Roadmap : Bêta privée", demo)
        self.assertIn("demo-back : dev a 3 commits d'avance", demo)
        # A project whose structured roadmap is not written: unknown, never a blank or a guess.
        brut = self.project_block(body, "brut")
        self.assertIn("Roadmap inconnue", brut)
        self.assertNotIn("commits d", brut, "no promotion branch declared: no gap shown")
        wait_until(lambda: "Tout est à jour à" in self.get("/"))

        page = self.get("/projet/demo")
        # The page of the project shows its whole roadmap (E, af-8rbceu).
        self.assertRegex(page, r"ROADMAP</small><h2[^>]*>Bêta privée</h2>")
        self.assertIn("demo-back : dev a 3 commits d'avance", page)
        self.assertIn("Roadmap inconnue", self.get("/projet/brut"))

        # The clones are the cockpit's own, with nothing checked out in them (AC5).
        for repo in ("org__demo-knowledge", "org__demo-back", "org__brut-knowledge"):
            clone = self.clones / repo
            self.assertTrue((clone / ".git").is_dir(), repo)
            self.assertEqual([".git"], sorted(p.name for p in clone.iterdir()), "nothing checked out in " + repo)

        # A later commit on origin shows without anyone touching the clone.
        self.origins.commit("org/demo-knowledge", "main", {"roadmap.toml": ROADMAP.replace('"in_progress"', '"done"')})
        self.origins.commit("org/demo-back", "dev", {"d9.txt": "d"})
        wait_until(lambda: "Roadmap : Trois" in self.get("/"))
        wait_until(lambda: "dev a 4 commits d'avance" in self.get("/"))

        # Read-only on the project repositories: only the test itself moved a ref.
        after = self.origins.refs()
        self.assertEqual(set(origin_refs), set(after))
        self.assertEqual(origin_refs["org/brut-knowledge.git"], after["org/brut-knowledge.git"])
        for repo, refs in after.items():
            self.assertNotIn("refs/remotes", refs, "nothing pushed into " + repo)

    def test_roadmap_incoherence_is_a_health_line(self):
        self.start_cockpit()
        texts = wait_until(
            lambda: [t for t in (line["text"] for line in self.get("/api/health")["lines"]) if "Roadmap" in t]
        )
        self.assertEqual(
            ["Roadmap : l'étape A1 est marquée faite alors que le chantier « Export des listes » est encore ouvert."],
            texts,
        )
        self.assertNotIn("af-conv1", " ".join(texts))

    def test_unreachable_repositories_are_unknown_then_read_again(self):
        hidden = self.dir / "origins-hidden"
        self.origins.root.rename(hidden)
        self.start_cockpit()
        time.sleep(1.5)
        body = self.get("/")
        self.assertIn("Roadmap inconnue", self.project_block(body, "demo"))
        self.assertNotIn("Roadmap : ", body)
        self.assertIn("dépôts des projets (inconnu)", body)
        hidden.rename(self.origins.root)
        wait_until(lambda: "Roadmap : Bêta privée" in self.get("/"))

    def test_without_a_clones_directory_no_repository_is_touched(self):
        self.start_cockpit(with_clones=False)
        wait_until(lambda: self.get("/api/projects")["state"] == "filled")
        time.sleep(1.0)
        body = self.get("/")
        self.assertNotIn("Roadmap", body)
        self.assertNotIn("depots", self.get("/api/status"))
        self.assertFalse(self.clones.exists())

    # ------------------------------------------------------------------
    # Promu (spec "Calcul d'étape des chantiers", row 7)
    def accepted_chantier(self, merge_commit):
        """An accepted chantier of "demo" whose one ticket was merged on
        the rig that promotes from dev to main."""
        beads = json.loads(self.state_file.read_text())
        beads += [
            {"id": "af-conv2", "title": "Fiches contacts", "status": "closed", "issue_type": "convoy",
             "labels": ["approved-ticket-graph"], "notes": "",
             "metadata": {"gc.graph_digest": "sha256:b", "gc.project_id": "demo",
                          "gc.cockpit_chantier_accepted": "true"}},
            {"id": "af-tk2", "title": "t", "status": "closed", "issue_type": "task",
             "labels": ["approved-ticket-graph", "delivery-plane"], "notes": "",
             "metadata": {"gc.graph_digest": "sha256:b", "gc.dispatch_rig": "demo-back",
                          "gc.merge_commit": merge_commit}},
        ]
        self.state_file.write_text(json.dumps(beads))

    def test_accepted_chantier_waits_for_promotion_then_is_promu(self):
        self.accepted_chantier(self.origins.sha("org/demo-back", "dev"))
        self.start_cockpit()
        body = wait_until(lambda: self.get("/") if "Accepté : en attente de promotion" in self.get("/") else None)
        self.assertIn("Fiches contacts", self.project_block(body, "demo"))
        self.assertIn("Le chantier Fiches contacts est accepté, pas encore promu.", body)

        # Benjamin promotes dev to main, outside the cockpit.
        self.origins.promote("org/demo-back", "dev", "main")
        wait_until(lambda: "pas encore promu" not in self.get("/"))
        body = self.get("/")
        self.assertNotIn("en attente de promotion", body)
        self.assertNotIn("Fiches contacts", self.project_block(body, "demo"), "a promoted chantier is finished")
        wait_until(lambda: "dev a 0 commits d'avance" in self.get("/"))
        page = self.get("/projet/demo")
        self.assertGreater(page.rindex("Fiches contacts"), page.rindex("Historique"), "it is in the project's history")

    def test_promotion_that_cannot_be_read_is_unknown_and_asks_nothing(self):
        self.accepted_chantier("0" * 40)  # a commit the clone does not know
        self.start_cockpit()
        wait_until(lambda: "demo-back : dev a 3 commits d'avance" in self.get("/"))
        time.sleep(1.0)
        body = self.get("/")
        self.assertIn("Accepté : promotion inconnue", self.project_block(body, "demo"))
        self.assertNotIn("pas encore promu", body)
        self.assertNotIn("en attente de promotion", body)

    def test_without_clones_an_accepted_chantier_is_unknown_not_finished(self):
        self.accepted_chantier(self.origins.sha("org/demo-back", "dev"))
        self.start_cockpit(with_clones=False)
        body = wait_until(lambda: self.get("/") if "Accepté : promotion inconnue" in self.get("/") else None)
        self.assertNotIn("pas encore promu", body)


if __name__ == "__main__":
    unittest.main()
