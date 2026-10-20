"""What the criterion tests of the destination « Analyses » share (D,
af-ten1sp; Spec af-fgcw0d, user stories 124, 148, 149, 150 and 175, Testing
Decisions 1, 5 and 8). Not a test file: the criterion test files of the
destination load it.

- `SOURCES`: a dataset of the isolated cockpit whose Analyses read real
  records -- the results, the tickets and the decisions of the delivery
  flow, and what GitHub answers for the CI and the pull requests of the
  declared repository -- at a fixed time, the Monday 12/10/2026 at noon
  (Paris), so that the seven days of the page are the 06/10 to the 12/10;
- `declare`: a commit of the tree under test where the profile declares
  more datasets, from which the launcher of the profile starts the cockpit;
- `served`: the page the launched cockpit serves at one address, read over
  HTTP: the text of each anchor, the points of its daily chart, the views
  its tabs open.

Nothing here reads the code of the cockpit: the launcher is an entry point
of the profile, and the page is read as the cockpit serves it.
"""

from __future__ import annotations

import copy
import json
import re
from html.parser import HTMLParser

from home_destination import PROFILE, LaunchTree, fetch, git

# The dataset of the Analyses on real records. Every value the page shows
# is computed by the cockpit from these records: none of them is written
# here. Over the seven days 06/10 -> 12/10 (Paris):
#
# - results whose merge is proven (`merged`): Export des notes (06/10),
#   Recherche plein texte (08/10), Reprise des sessions (11/10), Page
#   Portfolio (12/10); one merged before the period, one delivered and not
#   yet judged;
# - from publication to proven merge: 130, 260, 80 and 240 minutes -- the
#   work and checks up to the delivery 90, 180, 60 and 100, the wait for
#   the judgement 30, 60, 15 and 120, the merge 10, 20, 5 and 20;
# - tickets merged into the integration branch: 2, 1, 3, 0, 0, 1, 2 a day;
#   one refused by a conflict, one before the period;
# - pull requests merged: 1, 0, 2, 0, 0, 1, 1 a day; one closed unmerged,
#   one before the period;
# - CI runs: succeeded 2, 1, 3, 0, 0, 2, 1 a day, 13 completed in all; one
#   still running, one before the period;
# - decisions asked of Benjamin: three open, one answered.
SOURCES = {
    "generated_at": "2026-10-12T12:00:00+02:00",
    "synthetic": True,
    "ui": {"id": "analysis-sources", "page": "analysis"},
    "visible_text": "Analyses",
    "flow": {
        "results": [
            {"title": "Export des notes", "project": "Notes", "published": "2026-10-06T09:00:00+02:00",
             "delivered": "2026-10-06T10:30:00+02:00", "accepted": "2026-10-06T11:00:00+02:00",
             "merged": "2026-10-06T11:10:00+02:00"},
            {"title": "Recherche plein texte", "project": "Notes", "published": "2026-10-08T14:00:00+02:00",
             "delivered": "2026-10-08T17:00:00+02:00", "accepted": "2026-10-08T18:00:00+02:00",
             "merged": "2026-10-08T18:20:00+02:00"},
            {"title": "Reprise des sessions", "project": "Usine", "published": "2026-10-11T08:00:00+02:00",
             "delivered": "2026-10-11T09:00:00+02:00", "accepted": "2026-10-11T09:15:00+02:00",
             "merged": "2026-10-11T09:20:00+02:00"},
            {"title": "Page Portfolio", "project": "Portfolio", "published": "2026-10-12T07:00:00+02:00",
             "delivered": "2026-10-12T08:40:00+02:00", "accepted": "2026-10-12T10:40:00+02:00",
             "merged": "2026-10-12T11:00:00+02:00"},
            {"title": "Ancienne livraison", "project": "Notes", "published": "2026-09-30T09:00:00+02:00",
             "delivered": "2026-10-01T09:00:00+02:00", "accepted": "2026-10-02T09:00:00+02:00",
             "merged": "2026-10-02T10:00:00+02:00"},
            {"title": "Résultat à juger", "project": "Usine", "published": "2026-10-10T09:00:00+02:00",
             "delivered": "2026-10-10T15:00:00+02:00", "accepted": None, "merged": None},
        ],
        "tickets": [
            {"title": "Lire les notes", "project": "Notes", "dispatched": "2026-10-06T08:00:00+02:00",
             "merge": {"outcome": "merged", "at": "2026-10-06T09:40:00+02:00"}},
            {"title": "Écrire l’export", "project": "Notes", "dispatched": "2026-10-06T08:10:00+02:00",
             "merge": {"outcome": "merged", "at": "2026-10-06T10:00:00+02:00"}},
            {"title": "Tester l’export", "project": "Notes", "dispatched": "2026-10-07T09:00:00+02:00",
             "merge": {"outcome": "merged", "at": "2026-10-07T11:00:00+02:00"}},
            {"title": "Index de recherche", "project": "Notes", "dispatched": "2026-10-08T09:00:00+02:00",
             "merge": {"outcome": "merged", "at": "2026-10-08T12:00:00+02:00"}},
            {"title": "Requêtes de recherche", "project": "Notes", "dispatched": "2026-10-08T10:00:00+02:00",
             "merge": {"outcome": "merged", "at": "2026-10-08T15:00:00+02:00"}},
            {"title": "Résultats de recherche", "project": "Notes", "dispatched": "2026-10-08T11:00:00+02:00",
             "merge": {"outcome": "merged", "at": "2026-10-08T16:30:00+02:00"}},
            {"title": "Colonnes du tableau", "project": "Notes", "dispatched": "2026-10-09T09:00:00+02:00",
             "merge": {"outcome": "conflict", "at": "2026-10-09T11:00:00+02:00"}},
            {"title": "Reprendre une session", "project": "Usine", "dispatched": "2026-10-11T07:00:00+02:00",
             "merge": {"outcome": "merged", "at": "2026-10-11T08:30:00+02:00"}},
            {"title": "En-tête du portfolio", "project": "Portfolio", "dispatched": "2026-10-12T06:00:00+02:00",
             "merge": {"outcome": "merged", "at": "2026-10-12T07:30:00+02:00"}},
            {"title": "Galerie du portfolio", "project": "Portfolio", "dispatched": "2026-10-12T06:30:00+02:00",
             "merge": {"outcome": "merged", "at": "2026-10-12T08:00:00+02:00"}},
            {"title": "Ancien ticket", "project": "Notes", "dispatched": "2026-10-05T09:00:00+02:00",
             "merge": {"outcome": "merged", "at": "2026-10-05T10:00:00+02:00"}},
        ],
        "decisions": [
            {"title": "Choisir le format d’export", "project": "Notes", "asked": "2026-10-08T10:00:00+02:00",
             "answered": None},
            {"title": "Valider la reprise", "project": "Usine", "asked": "2026-10-10T16:00:00+02:00",
             "answered": None},
            {"title": "Nommer la page", "project": "Portfolio", "asked": "2026-10-11T11:00:00+02:00",
             "answered": None},
            {"title": "Ordre des colonnes", "project": "Notes", "asked": "2026-10-12T08:00:00+02:00",
             "answered": "2026-10-12T09:00:00+02:00"},
        ],
    },
    "github": {
        "repository": "saymyname-app/agent-factory",
        "pull_requests": [
            {"number": 99, "title": "Ancienne PR", "merged_at": "2026-10-04T10:00:00+02:00"},
            {"number": 101, "title": "Export des notes", "merged_at": "2026-10-06T11:10:00+02:00"},
            {"number": 102, "title": "Essai abandonné", "merged_at": None},
            {"number": 103, "title": "Index de recherche", "merged_at": "2026-10-08T12:05:00+02:00"},
            {"number": 104, "title": "Recherche plein texte", "merged_at": "2026-10-08T18:20:00+02:00"},
            {"number": 105, "title": "Reprise des sessions", "merged_at": "2026-10-11T09:20:00+02:00"},
            {"number": 106, "title": "Page Portfolio", "merged_at": "2026-10-12T11:00:00+02:00"},
        ],
        "workflow_runs": [
            {"id": 900, "name": "CI", "status": "completed", "conclusion": "failure",
             "created_at": "2026-10-03T10:00:00+02:00"},
            {"id": 901, "name": "CI", "status": "completed", "conclusion": "success",
             "created_at": "2026-10-06T09:00:00+02:00"},
            {"id": 902, "name": "CI", "status": "completed", "conclusion": "success",
             "created_at": "2026-10-06T10:00:00+02:00"},
            {"id": 903, "name": "CI", "status": "completed", "conclusion": "failure",
             "created_at": "2026-10-06T11:00:00+02:00"},
            {"id": 904, "name": "CI", "status": "completed", "conclusion": "success",
             "created_at": "2026-10-07T10:00:00+02:00"},
            {"id": 905, "name": "CI", "status": "completed", "conclusion": "success",
             "created_at": "2026-10-08T09:00:00+02:00"},
            {"id": 906, "name": "CI", "status": "completed", "conclusion": "success",
             "created_at": "2026-10-08T10:00:00+02:00"},
            {"id": 907, "name": "CI", "status": "completed", "conclusion": "success",
             "created_at": "2026-10-08T11:00:00+02:00"},
            {"id": 908, "name": "CI", "status": "completed", "conclusion": "failure",
             "created_at": "2026-10-08T12:00:00+02:00"},
            {"id": 909, "name": "CI", "status": "completed", "conclusion": "failure",
             "created_at": "2026-10-10T10:00:00+02:00"},
            {"id": 910, "name": "CI", "status": "completed", "conclusion": "success",
             "created_at": "2026-10-11T09:00:00+02:00"},
            {"id": 911, "name": "CI", "status": "completed", "conclusion": "success",
             "created_at": "2026-10-11T10:00:00+02:00"},
            {"id": 912, "name": "CI", "status": "completed", "conclusion": "success",
             "created_at": "2026-10-12T09:00:00+02:00"},
            {"id": 913, "name": "CI", "status": "completed", "conclusion": "failure",
             "created_at": "2026-10-12T10:00:00+02:00"},
            {"id": 914, "name": "CI", "status": "in_progress", "conclusion": None,
             "created_at": "2026-10-12T11:50:00+02:00"},
        ],
    },
}

# The same records, with no CI the cockpit can read: GitHub answers nothing.
WITHOUT_CI = {key: value for key, value in copy.deepcopy(SOURCES).items() if key != "github"}
WITHOUT_CI["ui"]["id"] = "analysis-sources-without-ci"

# The seven days of the page for these datasets, oldest first.
DAYS = ["06/10", "07/10", "08/10", "09/10", "10/10", "11/10", "12/10"]

# The four views of the Analyses, as their tabs name them, each the view of
# one indicator: what the page asks at its address, and the heading it shows.
VIEWS = {
    "Résultats": "Résultats fusionnés",
    "Délais": "Où passe le temps ?",
    "Vérifications": "Vérifications CI réussies",
    "Activité": "Décisions ouvertes",
}
# The labels of what the method of an indicator states, in its details.
METHOD = ("Population", "Période", "Sources", "Horodatage", "Calcul")


def declare(tree: LaunchTree, datasets: dict[str, dict]) -> str:
    """A commit where the profile declares each of `datasets` (name ->
    content) beside its own. The tree stays at that commit: the launcher
    reads the profile in the tree, and launches the commit it is given --
    the datasets of the profile are those of the first commit."""
    profile_path = tree.repo / PROFILE
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    for name, content in datasets.items():
        relative = f"config/cockpit-datasets/{name}.json"
        (tree.repo / relative).write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
        profile["launch"]["datasets"][name] = relative
    profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    git(tree.repo, "add", "--all", "--force")
    git(tree.repo, "commit", "--quiet", "--message", "the datasets of the Analyses on real records")
    return git(tree.repo, "rev-parse", "HEAD")


# --- the page, read over HTTP ----------------------------------------------------

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
# « Exécutions CI réussies · 08/10 : 3 »: one point of a daily chart.
POINT = re.compile(r"^(?P<series>.+?) · (?P<day>.*?(?P<date>\d\d/\d\d).*?) : (?P<value>\d+)$")


class _Page(HTMLParser):
    """The text of each anchor of a page, its links, and the points of the
    charts of daily volumes it draws."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, str | None, dict]] = []
        self.texts: dict[str, list[str]] = {}
        self.links: dict[str, list[tuple[str, str]]] = {}
        self.charts: list[dict] = []
        self.body: list[str] = []
        self._link: tuple[str, list[str]] | None = None
        self._title: list[str] | None = None
        self._in_body = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "body":
            self._in_body = True
        if tag in VOID:
            return
        anchor = attributes.get("data-anchor")
        if anchor:
            self.texts.setdefault(anchor, [])
        self.stack.append((tag, anchor, attributes))
        if tag == "svg" and (attributes.get("aria-label") or "").startswith("Volumes quotidiens"):
            self.charts.append({"label": attributes["aria-label"], "points": [], "text": []})
        if tag == "a" and attributes.get("href") is not None:
            self._link = (attributes["href"], [])
        if tag == "title" and any(t == "svg" for t, _, _ in self.stack[:-1]):
            self._title = []

    def handle_endtag(self, tag):
        if tag == "title" and self._title is not None:
            if self.charts and self._in_chart():
                self.charts[-1]["points"].append(" ".join("".join(self._title).split()))
            self._title = None
        if tag == "a" and self._link is not None:
            href, words = self._link
            text = " ".join(" ".join(words).split())
            for _, anchor, _ in self.stack:
                if anchor:
                    self.links.setdefault(anchor, []).append((text, href))
            self._link = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def _in_chart(self) -> bool:
        return any(t == "svg" and (a.get("aria-label") or "").startswith("Volumes quotidiens")
                   for t, _, a in self.stack)

    def handle_data(self, data):
        if self._title is not None:
            self._title.append(data)
            return
        if not self._in_body or any(t in ("script", "style") for t, _, _ in self.stack):
            return
        self.body.append(data)
        for _, anchor, _ in self.stack:
            if anchor:
                self.texts[anchor].append(data)
        if self._link is not None:
            self._link[1].append(data)
        if self.charts and self._in_chart():
            self.charts[-1]["text"].append(data)


class Page:
    """A page the cockpit serves, read over HTTP."""

    def __init__(self, address: str, path: str) -> None:
        self.address, self.path = address, path
        status, _, html = fetch(address + path)
        self.status = status
        parsed = _Page()
        parsed.feed(html)
        self._texts = {name: " ".join(" ".join(chunks).split()) for name, chunks in parsed.texts.items()}
        self._links = parsed.links
        self.charts = parsed.charts
        self.text = " ".join(" ".join(parsed.body).split())

    def says(self, anchor: str) -> str:
        """The text of the anchor, on one line; '' when the page has none."""
        return self._texts.get(anchor, "")

    def anchors(self) -> set[str]:
        return set(self._texts)

    def links(self, anchor: str) -> dict[str, str]:
        """The links inside the anchor: their text -> where they lead."""
        return dict(self._links.get(anchor, []))

    def series(self) -> dict[str, list[tuple[str, int]]]:
        """The series of the chart of daily volumes: series -> [(dd/mm,
        value)], in the order drawn; {} when the page draws no such chart."""
        found: dict[str, list[tuple[str, int]]] = {}
        for chart in self.charts:
            for point in chart["points"]:
                matched = POINT.match(point)
                if matched:
                    found.setdefault(matched["series"], []).append((matched["date"], int(matched["value"])))
        return found

    def chart_text(self) -> str:
        """What the chart of daily volumes says: its label, its axes and
        legend inside it, the titles of its points."""
        return " ".join(" ".join([chart["label"], *chart["text"], *chart["points"]]).split()
                        for chart in self.charts)

    def method(self) -> dict[str, str]:
        """What the method of the indicator states, by label (`METHOD`):
        « Population : … », « Période : … » …, read in the page."""
        labels = "|".join(METHOD + ("Raison",))
        found = {}
        for matched in re.finditer(rf"\b({labels}) : (.+?)(?=\s(?:{labels}) : |$)", self.text):
            found.setdefault(matched.group(1), matched.group(2).strip())
        return found


def served(address: str, view: str | None = None) -> Page:
    """The page « Analyses » of the cockpit at `address`, on the view whose
    tab is named `view` (« Délais »…), followed from the tab of its first
    page; the first page when None."""
    page = Page(address, "/analyses")
    if view is None:
        return page
    href = page.links("metric-tabs-1").get(view)
    if href is None:
        raise AssertionError(f"the Analyses have no tab « {view} » leading to its view: "
                             f"{page.links('metric-tabs-1')}")
    return Page(address, href if href.startswith("/") else "/analyses" + href)
