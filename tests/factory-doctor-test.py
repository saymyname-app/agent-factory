#!/usr/bin/env python3
"""factory-doctor must separate what we can fix from what we cannot.

The whole point of the tool is that nobody has to re-investigate `gc doctor`'s
34 permanent formula warnings ever again. That only holds if the classification
is right, so this pins the three verdicts and, above all, the case that broke
on the very first run: `gc doctor`'s own fix_hint contains the phrase
"parent/child conflicts", a naive path regex reads "/child" out of it, and one
stray non-cache "path" was enough to flip an upstream-only warning back to
ACTIONABLE — re-creating exactly the noise the tool exists to remove.
"""
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_loader(
    "factory_doctor",
    importlib.machinery.SourceFileLoader("factory_doctor", str(ROOT / "bin" / "factory-doctor")),
)
fd = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fd)

CACHE = "/home/benja/.gc/cache/repos/90e142/gascity/formulas"
REAL_FIX_HINT = (
    'replace deprecated contract = "graph.v2" with [requires] formula_compiler '
    '= ">=2.0.0"; enable [daemon] formula_v2 or lower requirements; fix invalid '
    "requirements and parent/child conflicts"
)


def check(name="c", severity="blocking", message="", fix_hint="", details=None):
    out = {"name": name, "status": "warning", "severity": severity, "message": message}
    if fix_hint:
        out["fix_hint"] = fix_hint
    if details:
        out["details"] = details
    return out


class Classification(unittest.TestCase):
    def test_advisory_severity_is_never_actionable(self):
        self.assertEqual("ADVISORY", fd.classify(check(
            severity="advisory",
            message="≥501 closed order-tracking beads: watchdog will prune",
        )))
        # Even when it cites a path right here in the factory.
        self.assertEqual("ADVISORY", fd.classify(check(
            severity="advisory",
            fix_hint='git -C "%s/rigs/saymyname-frontend" checkout dev' % fd.ROOT,
        )))

    def test_evidence_entirely_in_the_pack_cache_is_upstream(self):
        self.assertEqual("UPSTREAM", fd.classify(check(
            message="34 formula requirement warning(s)",
            details=['warning city formula "build-base" (%s/build-base.formula.toml):'
                     ' deprecated contract' % CACHE,
                     'warning city formula "build-basic" (%s/build-basic.formula.toml):'
                     ' deprecated contract' % CACHE],
        )))

    def test_the_parent_slash_child_phrase_is_not_a_path(self):
        """The regression that shipped in the first version.

        "parent/child conflicts" is prose. Reading "/child" out of it made the
        one warning this tool was written for classify as ACTIONABLE.
        """
        self.assertEqual([], fd.evidence_paths(check(fix_hint=REAL_FIX_HINT)),
                         "a mid-word slash must not be read as a path")
        self.assertEqual("UPSTREAM", fd.classify(check(
            message="34 formula requirement warning(s)",
            fix_hint=REAL_FIX_HINT,
            details=['warning city formula "build-base" (%s/build-base.formula.toml):'
                     ' deprecated contract' % CACHE],
        )))

    def test_evidence_in_this_repo_is_actionable(self):
        self.assertEqual("ACTIONABLE", fd.classify(check(
            message="missing runtime file %s/bin/pr-autopilot" % fd.ROOT,
        )))

    def test_mixed_evidence_stays_actionable(self):
        """One foot in this repo means somebody here must look."""
        self.assertEqual("ACTIONABLE", fd.classify(check(
            details=["upstream (%s/build-base.formula.toml)" % CACHE,
                     "ours (%s/city.toml)" % fd.ROOT],
        )))

    def test_a_check_that_did_not_answer_is_not_a_failure(self):
        """Timed out means "no answer", not "broken here".

        On 2026-09-16 `order-firing-current` timed out once at load 13 and was
        clean on the next three runs at load 21 — `gc order history` takes ~9s
        against a 15s budget on a busy host. Calling that ACTIONABLE would make
        this tool flap, and a tool that cries wolf gets ignored, which is the
        exact failure it exists to prevent.
        """
        c = check(name="order-firing-current",
                  message="order history lookup timed out after 15s",
                  fix_hint="check beads/Dolt connectivity, then rerun gc doctor")
        self.assertEqual("UNKNOWN", fd.classify(c))

    def test_a_blocking_problem_citing_no_path_is_actionable(self):
        """Never silently drop something just because it named no file."""
        self.assertEqual("ACTIONABLE", fd.classify(check(
            name="config-invariants",
            message="provider 'codex' does not resolve",
            fix_hint="restore the provider profile in city.toml",
        )))

    def test_upstream_classification_is_derived_not_curated(self):
        """No ignore-list: the same check flips verdict with its evidence.

        If upstream ever fixes those formulas the warning stops appearing, and
        if it ever starts citing a file in this repo it becomes ACTIONABLE with
        no one editing anything. A suppression list is what goes stale.
        """
        upstream = check(name="formula-requirements",
                         details=["(%s/x.formula.toml)" % CACHE])
        ours = check(name="formula-requirements",
                     details=["(%s/config/x.formula.toml)" % fd.ROOT])
        self.assertEqual("UPSTREAM", fd.classify(upstream))
        self.assertEqual("ACTIONABLE", fd.classify(ours))
        src = (ROOT / "bin" / "factory-doctor").read_text(encoding="utf-8")
        self.assertNotIn("formula-requirements", src,
                         "nothing may be muted by name")


class Collection(unittest.TestCase):
    def test_collect_finds_checks_at_any_nesting_depth(self):
        payload = {"results": [{"name": "a", "status": "ok"},
                               {"rig": {"results": [{"name": "b", "status": "warning",
                                                     "severity": "blocking"}]}}]}
        names = sorted(c["name"] for c in fd.collect(payload))
        self.assertEqual(["a", "b"], names)


class ExitStatus(unittest.TestCase):
    """Only an ACTIONABLE finding may fail; otherwise nobody can wire this up."""

    def setUp(self):
        # Never write a stub into the repo: it would dirty the working tree
        # on every run, and factory-guard would dutifully snapshot it.
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _run(self, checks):
        stub = pathlib.Path(self._tmp.name)
        gc = stub / "gc"
        gc.write_text(
            "#!/usr/bin/env bash\ncat <<'JSON'\n%s\nJSON\n"
            % json.dumps({"results": checks}), encoding="utf-8")
        gc.chmod(0o755)
        env = dict(os.environ, PATH="%s:%s" % (stub, os.environ["PATH"]))
        return subprocess.run([sys.executable, str(ROOT / "bin" / "factory-doctor"), "--all"],
                              capture_output=True, text=True, env=env)

    def test_upstream_and_advisory_alone_exit_zero(self):
        r = self._run([
            check(name="formula-requirements", details=["(%s/x.toml)" % CACHE]),
            check(name="fork-rate", severity="advisory", message="high fork rate"),
        ])
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("nothing actionable here", r.stdout)
        self.assertIn("UPSTREAM", r.stdout)

    def test_a_timeout_is_always_shown_but_never_fails_the_run(self):
        r = self._run([check(name="order-firing-current",
                             message="order history lookup timed out after 15s")])
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("DID NOT ANSWER", r.stdout)
        self.assertIn("order-firing-current", r.stdout)
        # Never hidden behind --all: a persistent one must be visible by default.
        plain = subprocess.run(
            [sys.executable, str(ROOT / "bin" / "factory-doctor")],
            capture_output=True, text=True,
            env=dict(os.environ, PATH="%s:%s" % (self._tmp.name, os.environ["PATH"])))
        self.assertIn("DID NOT ANSWER", plain.stdout)

    def test_an_actionable_finding_exits_non_zero(self):
        r = self._run([check(name="runtime-files", message="missing bin/pr-autopilot")])
        self.assertEqual(1, r.returncode)
        self.assertIn("ACTIONABLE", r.stdout)

    def test_unparseable_output_is_an_error_not_a_clean_bill(self):
        stub = pathlib.Path(self._tmp.name)
        gc = stub / "gc"
        gc.write_text("#!/usr/bin/env bash\necho 'not json'\nexit 3\n", encoding="utf-8")
        gc.chmod(0o755)
        env = dict(os.environ, PATH="%s:%s" % (stub, os.environ["PATH"]))
        r = subprocess.run([sys.executable, str(ROOT / "bin" / "factory-doctor")],
                           capture_output=True, text=True, env=env)
        self.assertEqual(2, r.returncode)
        self.assertNotIn("nothing actionable", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
