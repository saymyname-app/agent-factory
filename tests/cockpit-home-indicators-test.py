"""The indicators of the home of the launched cockpit (K2, af-unu7jp; code
review F1.3), read at GET /: an indicator without its source is said
unavailable with its reason, as in the Analyses, even when the factory
holds nothing else to show -- the home says « Rien à afficher ici » only
when no indicator lacks its source.

Each case starts the cockpit process (bin/cockpit run) on the fake sources
of tests/cockpit-analyses-test.py and reads the home it serves. The
indicators beside requests, runs and results are proven on the datasets of
the profile by tests/cockpit-criteria/commands/home-indicators-test.py."""
import importlib.util
import time
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location("cockpit_analyses_test",
                                               Path(__file__).resolve().parent / "cockpit-analyses-test.py")
cockpit_analyses_test = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cockpit_analyses_test)
FIXTURES = cockpit_analyses_test.FIXTURES

NOTHING = "Rien à afficher ici"
NO_REPOSITORY = "Vérifications CI réussies indisponible aucun dépôt GitHub n’est déclaré pour la CI du cockpit"


class HomeIndicatorsOfTheLaunchedCockpitTest(cockpit_analyses_test.AnalysesOfTheLaunchedCockpitTest):
    def home(self, condition, seconds=10):
        """The text of the home, on one line, once its first reading is done
        and `condition(text)` holds."""
        deadline, text = time.monotonic() + seconds, ""
        while time.monotonic() < deadline:
            try:
                text = self.page_at("/")
            except OSError:
                text = ""
            if "Vérifié à" in text and condition(text):
                return text
            time.sleep(0.1)
        self.fail("the home never held: « %s »" % text)

    def page_at(self, path):
        body = cockpit_analyses_test.re.sub(r"<(script|style)\b.*?</\1>", " ", self.get(path),
                                            flags=cockpit_analyses_test.re.S)
        return " ".join(cockpit_analyses_test.html.unescape(cockpit_analyses_test.re.sub(r"<[^>]+>", " ", body))
                        .split())

    def test_with_nothing_else_to_show_the_home_says_the_ci_unavailable_and_why(self):
        self.start(settings={})
        text = self.home(lambda text: NOTHING in text or NO_REPOSITORY in text)
        self.assertNotIn(NOTHING, text, "the home hides an indicator without its source as if it had nothing to show")
        self.assertIn(NO_REPOSITORY, text)

    def test_with_every_source_and_nothing_in_them_the_home_has_nothing_to_show(self):
        self.write_github("saymyname-app/notes", [], [])
        self.start(settings={"github_repo": "saymyname-app/notes", "gh_bin": str(FIXTURES / "github" / "fake-gh")})
        self.until_fresh_then("github", "fresh")
        text = self.home(lambda text: NOTHING in text or "Vérifications CI réussies" in text)
        self.assertIn(NOTHING, text)


# The cases of the Analyses run in their own file.
for _name in [name for name in vars(cockpit_analyses_test.AnalysesOfTheLaunchedCockpitTest) if name.startswith("test_")]:
    setattr(HomeIndicatorsOfTheLaunchedCockpitTest, _name, None)


if __name__ == "__main__":
    unittest.main()
