"""What the criterion tests of the destination « Journal » share (F, the
Prototype Fold of the Journal reference, af-njwz8v; Spec af-fgcw0d, user
stories 76, 124, 157, 158 and 175, Testing Decisions 1, 5 and 8). Not a
test file: the criterion test files of the destination load it.

It reuses what the destination « Vue d’ensemble » already shares
(home_destination.py: the launch tree, the measure of a page in a headless
Chromium, what makes a page unreadable, the deviations from the anchors
and the tokens of a reference) and adds:

- `journey`: what the page the launched cockpit serves shows after the
  steps a person takes on it, one after the other -- open a tab, choose a
  filter, write in the search field, unfold a part -- read in a headless
  Chromium by journal_journey.js;
- the reference: the events and the technical logs the Validated Prototype
  freezes (prototype/cockpit-b-zones-20261012 at 632deea,
  prototypes/c01-complete/frozen-panorama-journal), written out once here,
  the values the cases check being these;
- what the cases assert of the destination: the navigation with « Journal »
  open, the tabs and which one is open, which events a page shows.

Nothing here reads the code of the cockpit: the launcher is an entry point
of the profile, the page is read where the browser renders it.
"""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import (  # noqa: E402,F401
    BROWSER_TIMEOUT, COLOUR_SCHEMES, FRAME_HEIGHT, NAVIGATION, LaunchTree, anchor_deviations, fetch, find_browser,
    measure, measure_until, problems, says, text_of, token_deviations,
)

# --- the reference -------------------------------------------------------------

# The events of the journal the reference shows on journal-content (and on
# journal-long, journal-narrow, journal-light, journal-stale and
# journal-offline, drawn the same), in its order: (the line above the
# title -- its time, its source, its category --, the title, its
# consequence, its link, what its « Détail et source » holds).
EVENTS = [
    ("14:48 (Paris) · Usine · Proposition", "Deux améliorations proposées après une revue",
     "Tu peux choisir les problèmes à faire préparer.", "Voir les propositions",
     "La revue regroupe les incidents par cause. Aucun travail lancé sans décision."),
    ("14:42 (Paris) · Usine · Changement", "Le cockpit est prêt à essayer",
     "Un résultat attend ton avis.", "Voir le résultat",
     "Dossier courant, essai disponible. Prêt à juger ne signifie pas accepté ni fusionné."),
    ("14:36 (Paris) · Notes · Bug", "Une recherche sur des notes longues échoue",
     "Le défaut a été enregistré ; la correction reste à préparer.", "Voir le projet",
     "Défaut d’exemple, regroupé avec les signalements de même cause."),
    ("14:20 (Paris) · Notes · Décision", "Le format CSV a été choisi",
     "L’usine peut poursuivre la préparation de l’export.", "Voir le projet",
     "Choix enregistré explicitement. Aucun déploiement produit impliqué."),
    ("18:10 (Paris) · Portfolio · Changement", "La présentation a été fusionnée",
     "Le changement est intégré ; sa publication n’est pas attestée ici.", "Voir le projet",
     "Fusion et mise en production sont deux faits distincts."),
    ("16:05 (Paris) · Usine · Événement", "La connexion au superviseur a été rétablie",
     "Les lectures ont repris après 3 minutes d’interruption.", "Voir les connexions",
     "Événement technique ayant affecté la fraîcheur du cockpit. Les appels et logs détaillés restent dans les runs."),
]
TITLES = [event[1] for event in EVENTS]
# What the « Détail et source » of each event of the reference says of its
# source: an example, which changes nothing in production.
SYNTHETIC_SOURCE = "Événement synthétique · aucune action de production."
# The day each event is listed under: the first four the day of the dataset
# (2026-10-12), the last two the day before. The reference, drawn on that
# day, names them « Aujourd’hui » and « Hier »; a cockpit read on a later
# day names them by their date.
DAYS = (("Aujourd’hui", "Hier"), ("12/10/2026", "11/10/2026"))

# The tabs of the destination, and the categories of its useful events.
TABS = ["Événements utiles", "Logs techniques", "Sources disponibles"]
CATEGORIES = ["Tout", "Bugs", "Propositions", "Changements", "Décisions", "Événements"]

# The technical logs the reference shows on journal-logs, in its order:
# (time, title, what it means, its raw event as received).
LOGS = [
    ("14:36 (Paris)", "Vérification échouée",
     "La vérification de régression n’a pas réussi. Le résultat reste à corriger.",
     "ci.completed outcome=failure job=regression exit=1"),
    ("14:35 (Paris)", "Nouvelle session auteur",
     "Une nouvelle session reprend le même travail avec son contexte de départ.",
     "session.started role=author reason=context_refresh"),
    ("14:34 (Paris)", "Résultat prêt à juger",
     "Les vérifications requises ont terminé ; ton jugement est attendu.",
     "outcome.delivered evidence=current"),
    ("14:30 (Paris)", "Lecture du superviseur interrompue",
     "La dernière valeur est conservée comme périmée.",
     "source.read_failed source=supervisor timeout_ms=5000"),
    ("14:25 (Paris)", "Nettoyage terminé",
     "Les espaces sans travail actif identifiés ont été retirés.",
     "maintenance.completed gesture=clean-worktrees removed=3"),
    ("14:20 (Paris)", "Notification remise au service",
     "Le service a accepté l’envoi ; la lecture sur le téléphone n’est pas connue.",
     "notification.accepted channel=push"),
    ("14:10 (Paris)", "Événement non reconnu",
     "Le type reçu ne possède pas encore de libellé. Le contenu brut reste accessible.",
     'source=example event=unmapped_demo payload={"sample":true}'),
]
LOG_TITLES = [log[1] for log in LOGS]
# The sources of the technical logs, as their filters name them, and the
# title of each log under its source (« Autres »: what no source claims).
SOURCES = ["CI", "Agents", "Livraison", "Connexions", "Maintenance", "Notifications"]
LOG_FILTERS = ["Tous", *SOURCES, "Autres"]
LOGS_BY_SOURCE = dict(zip([*SOURCES, "Autres"], LOG_TITLES))
LOG_SEARCH = "Rechercher dans les logs"
FIXED_LABELS = "Libellés fixes par type d’événement ; aucun appel de modèle."


def outline(text: str) -> list[tuple[str, str, str | None, str, str]]:
    """The anchors a case writes as an outline, one per line in the order
    of the page -- « name element line-height [font-family] », indented
    under the anchor that holds it, two spaces a level, in system-ui when
    the line names no type --, as (anchor, element, the anchor that holds
    it, font-family, line-height)."""
    anchors, holders = [], []
    for line in text.strip("\n").split("\n"):
        depth = (len(line) - len(line.lstrip(" "))) // 2
        name, tag, leading, *family = line.split()
        del holders[depth:]
        anchors.append((name, tag, holders[-1] if holders else None, family[0] if family else "system-ui", leading))
        holders.append(name)
    return anchors


# Every anchor of the frozen page of each state, in the order of the page:
# the anchor, the element that draws it, its line-height and, when it is
# not system-ui, its type, indented under the anchor that holds it. Read
# from the frozen pages (states/<state>.html) as headless Chromium renders
# them at 1440 and 390 px in the dark and the light theme -- the four
# renderings agree --; the states drawn the same share one outline. The
# logs are those of journal-logs, the tab « Logs techniques » open.

# journal-content, journal-long, journal-narrow, journal-light
CONTENT_ANCHORS = outline("""
shell-nav-1 aside normal
  brand-1 header normal
    div-1 div normal
      strong-1 strong normal
      small-1 small normal
    live-1 span normal
  nav-1 nav normal
    button-1 button normal
      badge-count-1 span normal
    button-2 button normal
    button-3 button normal
    selected-1 button normal
    button-4 button normal
    button-5 button normal
    button-6 button normal
main-1 main normal
  h1-1 h1 normal
  page-lead-1 p 24px
  filter-row-1 div normal
    primary-1 button normal
    button-7 button normal
    button-8 button normal
  filter-row-2 div normal
    primary-2 button normal
    button-9 button normal
    button-10 button normal
    button-11 button normal
    button-12 button normal
    button-13 button normal
  timeline-date-1 h2 normal
  timeline-1 div normal
    timeline-item-1 article normal
      small-2 small normal
      h3-1 h3 normal
      p-1 p 21px
      link-1 button normal
      details-1 details normal
        summary-1 summary normal
        p-2 p 21px
        small-3 small normal
    timeline-item-2 article normal
      small-4 small normal
      h3-2 h3 normal
      p-3 p 21px
      link-2 button normal
      details-2 details normal
        summary-2 summary normal
        p-4 p 21px
        small-5 small normal
    timeline-item-3 article normal
      small-6 small normal
      h3-3 h3 normal
      p-5 p 21px
      link-3 button normal
      details-3 details normal
        summary-3 summary normal
        p-6 p 21px
        small-7 small normal
    timeline-item-4 article normal
      small-8 small normal
      h3-4 h3 normal
      p-7 p 21px
      link-4 button normal
      details-4 details normal
        summary-4 summary normal
        p-8 p 21px
        small-9 small normal
  timeline-date-2 h2 normal
  timeline-2 div normal
    timeline-item-5 article normal
      small-10 small normal
      h3-5 h3 normal
      p-9 p 21px
      link-5 button normal
      details-5 details normal
        summary-5 summary normal
        p-10 p 21px
        small-11 small normal
    timeline-item-6 article normal
      small-12 small normal
      h3-6 h3 normal
      p-11 p 21px
      link-6 button normal
      details-6 details normal
        summary-6 summary normal
        p-12 p 21px
        small-13 small normal
""")

# journal-empty
EMPTY_ANCHORS = outline("""
shell-nav-1 aside normal
  brand-1 header normal
    div-1 div normal
      strong-1 strong normal
      small-1 small normal
    live-1 span normal
  nav-1 nav normal
    button-1 button normal
      badge-count-1 span normal
    button-2 button normal
    button-3 button normal
    selected-1 button normal
    button-4 button normal
    button-5 button normal
    button-6 button normal
main-1 main normal
  h1-1 h1 normal
  page-lead-1 p 24px
  filter-row-1 div normal
    primary-1 button normal
    button-7 button normal
    button-8 button normal
  filter-row-2 div normal
    primary-2 button normal
    button-9 button normal
    button-10 button normal
    button-11 button normal
    button-12 button normal
    button-13 button normal
  panel-1 section normal
    h2-1 h2 normal
    p-1 p 22.5px
""")

# journal-loading
LOADING_ANCHORS = outline("""
shell-nav-1 aside normal
  brand-1 header normal
    div-1 div normal
      strong-1 strong normal
      small-1 small normal
    live-1 span normal
  nav-1 nav normal
    button-1 button normal
      badge-count-1 span normal
    button-2 button normal
    button-3 button normal
    selected-1 button normal
    button-4 button normal
    button-5 button normal
    button-6 button normal
main-1 main normal
  h1-1 h1 normal
  page-lead-1 p 24px
  filter-row-1 div normal
    primary-1 button normal
    button-7 button normal
    button-8 button normal
  filter-row-2 div normal
    primary-2 button normal
    button-9 button normal
    button-10 button normal
    button-11 button normal
    button-12 button normal
    button-13 button normal
  panel-1 section normal
    h2-1 h2 normal
    skeleton-1 div normal
    skeleton-2 div normal
    skeleton-3 div normal
""")

# journal-error
ERROR_ANCHORS = outline("""
shell-nav-1 aside normal
  brand-1 header normal
    div-1 div normal
      strong-1 strong normal
      small-1 small normal
    live-1 span normal
  nav-1 nav normal
    button-1 button normal
      badge-count-1 span normal
    button-2 button normal
    button-3 button normal
    selected-1 button normal
    button-4 button normal
    button-5 button normal
    button-6 button normal
main-1 main normal
  h1-1 h1 normal
  page-lead-1 p 24px
  filter-row-1 div normal
    primary-1 button normal
    button-7 button normal
    button-8 button normal
  filter-row-2 div normal
    primary-2 button normal
    button-9 button normal
    button-10 button normal
    button-11 button normal
    button-12 button normal
    button-13 button normal
  error-1 section normal
    h2-1 h2 normal
    p-1 p 22.5px
    button-14 button normal
""")

# journal-stale, journal-offline
STALE_ANCHORS = outline("""
shell-nav-1 aside normal
  brand-1 header normal
    div-1 div normal
      strong-1 strong normal
      small-1 small normal
    live-1 span normal
  nav-1 nav normal
    button-1 button normal
      badge-count-1 span normal
    button-2 button normal
    button-3 button normal
    selected-1 button normal
    button-4 button normal
    button-5 button normal
    button-6 button normal
main-1 main normal
  notice-1 div normal
  h1-1 h1 normal
  page-lead-1 p 24px
  filter-row-1 div normal
    primary-1 button normal
    button-7 button normal
    button-8 button normal
  filter-row-2 div normal
    primary-2 button normal
    button-9 button normal
    button-10 button normal
    button-11 button normal
    button-12 button normal
    button-13 button normal
  timeline-date-1 h2 normal
  timeline-1 div normal
    timeline-item-1 article normal
      small-2 small normal
      h3-1 h3 normal
      p-1 p 21px
      link-1 button normal
      details-1 details normal
        summary-1 summary normal
        p-2 p 21px
        small-3 small normal
    timeline-item-2 article normal
      small-4 small normal
      h3-2 h3 normal
      p-3 p 21px
      link-2 button normal
      details-2 details normal
        summary-2 summary normal
        p-4 p 21px
        small-5 small normal
    timeline-item-3 article normal
      small-6 small normal
      h3-3 h3 normal
      p-5 p 21px
      link-3 button normal
      details-3 details normal
        summary-3 summary normal
        p-6 p 21px
        small-7 small normal
    timeline-item-4 article normal
      small-8 small normal
      h3-4 h3 normal
      p-7 p 21px
      link-4 button normal
      details-4 details normal
        summary-4 summary normal
        p-8 p 21px
        small-9 small normal
  timeline-date-2 h2 normal
  timeline-2 div normal
    timeline-item-5 article normal
      small-10 small normal
      h3-5 h3 normal
      p-9 p 21px
      link-5 button normal
      details-5 details normal
        summary-5 summary normal
        p-10 p 21px
        small-11 small normal
    timeline-item-6 article normal
      small-12 small normal
      h3-6 h3 normal
      p-11 p 21px
      link-6 button normal
      details-6 details normal
        summary-6 summary normal
        p-12 p 21px
        small-13 small normal
""")

# journal-logs
LOGS_ANCHORS = outline("""
shell-nav-1 aside normal
  brand-1 header normal
    div-1 div normal
      strong-1 strong normal
      small-1 small normal
    live-1 span normal
  nav-1 nav normal
    button-1 button normal
      badge-count-1 span normal
    button-2 button normal
    button-3 button normal
    selected-1 button normal
    button-4 button normal
    button-5 button normal
    button-6 button normal
main-1 main normal
  h1-1 h1 normal
  filter-row-1 div normal
    button-7 button normal
    button-8 button normal
    button-9 button normal
  filter-row-2 div normal
    primary-1 button normal
    button-10 button normal
    button-11 button normal
    button-12 button normal
    button-13 button normal
    button-14 button normal
    button-15 button normal
    button-16 button normal
  log-search-1 input normal
  panel-1 section normal
    small-2 small normal
    h3-1 h3 normal
    p-1 p 22.5px
    details-1 details normal
      summary-1 summary normal
      raw-event-1 pre 19.2px monospace
  panel-2 section normal
    small-3 small normal
    h3-2 h3 normal
    p-2 p 22.5px
    details-2 details normal
      summary-2 summary normal
      raw-event-2 pre 19.2px monospace
  panel-3 section normal
    small-4 small normal
    h3-3 h3 normal
    p-3 p 22.5px
    details-3 details normal
      summary-3 summary normal
      raw-event-3 pre 19.2px monospace
  panel-4 section normal
    small-5 small normal
    h3-4 h3 normal
    p-4 p 22.5px
    details-4 details normal
      summary-4 summary normal
      raw-event-4 pre 19.2px monospace
  panel-5 section normal
    small-6 small normal
    h3-5 h3 normal
    p-5 p 22.5px
    details-5 details normal
      summary-5 summary normal
      raw-event-5 pre 19.2px monospace
  panel-6 section normal
    small-7 small normal
    h3-6 h3 normal
    p-6 p 22.5px
    details-6 details normal
      summary-6 summary normal
      raw-event-6 pre 19.2px monospace
  panel-7 section normal
    small-8 small normal
    h3-7 h3 normal
    p-7 p 22.5px
    details-7 details normal
      summary-7 summary normal
      raw-event-7 pre 19.2px monospace
  readonly-note-1 p 18px
""")

# The tokens of the reference, the same in its ten states: their names and
# their values, in the dark and the light theme.
TOKENS = {
    "dark": {"--bg": "#0d1015", "--surface": "#161b23", "--line": "#2a3240", "--ink": "#ecedf3",
             "--muted": "#9aa6b9", "--accent": "#99aaff", "--ok": "#55c89d", "--warn": "#efc778"},
    "light": {"--bg": "#f3f5f9", "--surface": "#fff", "--line": "#dbe0e8", "--ink": "#17202e",
              "--muted": "#657185", "--accent": "#415fce", "--ok": "#1c7954", "--warn": "#97691e"},
}

# --- a journey in the browser ------------------------------------------------------

JOURNEY_SCRIPT = (Path(__file__).with_name("journal_journey.js")).read_text(encoding="utf-8")
JOURNEY_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>parcours</title></head>
<body style="margin:0">
<div id="frames"></div>
<pre id="journey"></pre>
<script>%s</script>
</body></html>
"""
JOURNEY_RE = re.compile(r'<pre id="journey">(.*?)</pre>', re.S)


class _JourneyPage(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = (JOURNEY_PAGE % JOURNEY_SCRIPT).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


_server_lock = threading.Lock()
_server: ThreadingHTTPServer | None = None


def _journey_url() -> str:
    global _server
    with _server_lock:
        if _server is None:
            _server = ThreadingHTTPServer(("127.0.0.1", 0), _JourneyPage)
            threading.Thread(target=_server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{_server.server_address[1]}/journey.html"


def click(name: str) -> dict:
    """A step: the control a person sees whose name is `name` (or starts
    with it) is activated."""
    return {"click": name}


def write(field: str, words: str) -> dict:
    """A step: `words` are written in the field named `field`, then sent."""
    return {"type": field, "text": words}


def journey(address: str, path: str = "/journal", steps: tuple = (), *, theme: str = "dark",
            width: int = 1440) -> dict:
    """What the page at `address` + `path` shows, `width` px wide in
    `theme`, once the `steps` were taken on it one after the other (see
    journal_journey.js for what the record holds)."""
    query = urllib.parse.urlencode({"target": address + path, "width": width, "height": FRAME_HEIGHT,
                                    "steps": json.dumps(list(steps), ensure_ascii=False)})
    work = tempfile.mkdtemp(prefix="cockpit-journal-browser-")
    argv = [
        find_browser(), "--headless", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={work}/profile",
        "--disable-web-security", "--disable-site-isolation-trials",
        f"--window-size={width + 20},{FRAME_HEIGHT + 20}",
        f"--blink-settings=preferredColorScheme={COLOUR_SCHEMES[theme]}",
        "--virtual-time-budget=60000", "--dump-dom", f"{_journey_url()}?{query}",
    ]
    proc = None
    try:
        with open(Path(work) / "dom.html", "wb") as out, open(Path(work) / "browser.log", "wb") as log:
            proc = subprocess.Popen(argv, cwd=work, stdin=subprocess.DEVNULL, stdout=out, stderr=log,
                                    start_new_session=True)
            proc.wait(timeout=BROWSER_TIMEOUT)
        dom = (Path(work) / "dom.html").read_text(encoding="utf-8", errors="replace")
    finally:
        if proc is not None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
        shutil.rmtree(work, ignore_errors=True)
    found = JOURNEY_RE.search(dom)
    read = json.loads(html.unescape(found.group(1))) if found and found.group(1).strip() else None
    if not isinstance(read, dict) or read.get("ok") is not True:
        raise RuntimeError(f"the browser read nothing on {address}{path} after {steps}: {read}")
    return read["page"]


# --- what the criterion tests assert --------------------------------------------

def shown(page: dict, titles: list[str]) -> list[str]:
    """Those of `titles` the page shows, in the order of `titles`."""
    return [title for title in titles if title in page["text"]]


def assert_found(case, page: dict) -> None:
    """Each step of the journey found its control or its field."""
    case.assertEqual([True] * len(page["steps"]), page["steps"],
                     "a control or a field of the journey is not on the page")


def assert_journal(case, frame: dict) -> None:
    """A page measured (home_destination.measure) is the destination
    « Journal », served at its own address: the navigation B with
    « Journal » as the destination open."""
    case.assertEqual("/journal", frame["path"], "the journal is not served at its own address")
    labels = [entry["label"].rstrip("0123456789 ") for entry in frame["nav"]]
    case.assertEqual(NAVIGATION, labels, "the navigation B is not the reference's")
    case.assertEqual(["Journal"], [label for label, entry in zip(labels, frame["nav"]) if entry["current"]],
                     "the navigation does not say the journal is open")


def is_open(control: dict) -> bool:
    """The control says, to a screen reader as to the eye, that it is the
    one open (aria-current, aria-selected or aria-pressed)."""
    return any(control["state"].get(key) not in (None, "false") for key in ("current", "selected", "pressed"))


def assert_open(case, page: dict, names: list[str], opened: str) -> None:
    """Among the controls `names` (the tabs, the filters), each is on the
    page once, and `opened` alone says it is the one open."""
    controls = {name: [c for c in page["controls"] if c["name"] == name] for name in names}
    case.assertEqual({name: 1 for name in names}, {name: len(found) for name, found in controls.items()},
                     f"the controls {names} are not each on the page once")
    case.assertEqual([opened], [name for name, found in controls.items() if is_open(found[0])],
                     f"« {opened} » is not the one said open")


def anchor_says(case, page: dict, anchor: str, *phrases: str, folded: bool = False) -> None:
    """Each phrase is said inside the anchor `anchor` of a journey's page:
    in what it shows, or, with `folded`, in what it holds folded too."""
    found = page["anchors"].get(anchor)
    case.assertIsNotNone(found, f"the page has no part {anchor}")
    text = found["content" if folded else "text"]
    case.assertEqual([], [phrase for phrase in phrases if phrase not in text],
                     f"{anchor} does not say it; it says « {text} »")


def state_of(page: dict, source: str) -> str | None:
    """What the page says of the source `source`: « raccordée », « absente »
    or « inconnue », read in the shortest part of the page that names the
    source and one of these; None when no part does."""
    words = re.compile(r"\b(raccordée|absente|inconnue|ne répond pas)\b", re.I)
    named = re.compile(rf"(?<![\w-]){re.escape(source)}(?![\w-])")
    blocks = sorted((block for block in page["blocks"] if named.search(block) and words.search(block)), key=len)
    if not blocks:
        return None
    said = words.search(blocks[0]).group(1).lower()
    return "inconnue" if said == "ne répond pas" else said
