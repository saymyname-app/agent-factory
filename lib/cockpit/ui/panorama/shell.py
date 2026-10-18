"""The shell of B/Panorama (Validated Prototype prototype/cockpit-b-zones-20261012
at 632deea; Spec af-2zseit, user stories 124, 147 and 175).

    render_shell(destination, main_html, waiting=2, live="● En marche · 2 agents")

returns the navigation B and the destination's ``main``, to be passed to
:func:`cockpit.ui.base.page.render_document` with :data:`CSS`. The entry of
the destination open is a button marked ``aria-current="page"``; every
other one is a link to its address, so a destination is reached from any
other one. The parts carry the anchors of the reference (``data-anchor``),
numbered by :class:`Anchors` as the frozen pages number them.

Nothing here reads a source: what waits and the state of the factory are
the caller's (``waiting`` None: unknown).
"""
import html
import re

HOME = "home"
# The destinations of the navigation B, in its order: key, label, address.
NAVIGATION = (
    (HOME, "Vue d’ensemble", "/"),
    ("projets", "Projets", "/projets"),
    ("runs", "Runs", "/runs"),
    ("journal", "Journal", "/journal"),
    ("usine", "Usine", "/usine"),
    ("rituels", "Rituels", "/rituels"),
    ("analyses", "Analyses", "/analyses"),
)


def anchor_slug(label):
    """The name the frozen pages give a part named by its label: lower case,
    every run of other characters than a-z and 0-9 one dash (« comparés »
    is ``compar-s``)."""
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")


class Anchors:
    """Numbers the anchors of one page, by name, in the order they are
    drawn: ``anchors("row")`` is ``data-anchor="row-1"``, then ``row-2``."""

    def __init__(self):
        self._counts = {}

    def __call__(self, name):
        self._counts[name] = self._counts.get(name, 0) + 1
        return 'data-anchor="%s-%d"' % (html.escape(name), self._counts[name])


def render_shell(destination, main_html, waiting=None, live=None, anchors=None):
    """The navigation B, then ``main_html`` in ``<main>``. ``waiting``: how
    many requests wait for the operator, shown on « Vue d’ensemble » (None:
    unknown, nothing shown); ``live``: the state of the factory, one line.
    ``anchors``: the numbering of the page, when ``main_html`` was drawn
    with it already."""
    anchors = anchors or Anchors()
    entries = []
    for key, label, href in NAVIGATION:
        badge = ""
        if key == HOME:
            badge = '<span class="pn-badge" %s>%s</span>' % (
                anchors("badge-count"), "" if waiting is None else int(waiting))
        if key == destination:
            entries.append('<button type="button" class="pn-selected" aria-current="page" %s>%s%s</button>'
                           % (anchors("selected"), html.escape(label), badge))
        else:
            entries.append('<a href="%s" %s>%s%s</a>' % (href, anchors("a"), html.escape(label), badge))
    return (
        '<div class="pn-layout">'
        '<aside class="pn-shell" %s>'
        '<header class="pn-brand" %s><div><strong>Cockpit</strong><small>Usine + projets</small></div>'
        '<span class="pn-live" %s>%s</span></header>'
        '<nav aria-label="Destinations" %s>%s</nav>'
        "</aside>"
        '<main class="pn-main" %s>%s</main>'
        "</div>"
    ) % (
        anchors("shell-nav"), anchors("brand"), anchors("live"),
        html.escape(live or "● État actuel inconnu"), anchors("nav"), "".join(entries),
        anchors("main"), main_html,
    )


def render_not_folded(label):
    """The main part of a destination whose Prototype Fold is not done yet:
    it says so, rather than a page that would look like the destination."""
    return (
        '<div class="pn-head"><h1>%s</h1></div>'
        '<section class="pn-panel"><h2>Destination pas encore raccordée</h2>'
        "<p>Cette page du cockpit n’est pas encore servie ici. Les autres destinations restent accessibles "
        "depuis la navigation.</p></section>"
    ) % html.escape(label)


# The tokens of the reference, light when the browser prefers it, dark
# otherwise (--pn-control-line, the box of a control: 3:1 at least on the
# surface and the background, where --pn-line is not); the shell's layout: the navigation beside the destination,
# above it under 800 px. A rule of a destination reuses these tokens.
CSS = """
:root{
  color-scheme:light;
  --pn-bg:#F3F5F9; --pn-surface:#FFFFFF; --pn-surface-2:#E6EBFB; --pn-line:#D2D8E2; --pn-ink:#17202E;
  --pn-muted:#566175; --pn-accent:#3653C2; --pn-accent-ink:#FFFFFF; --pn-ok:#17704C; --pn-warn:#85590F;
  --pn-control-line:#788396;
}
@media (prefers-color-scheme: dark){
  :root{
    color-scheme:dark;
    --pn-bg:#0D1015; --pn-surface:#161B23; --pn-surface-2:#222D46; --pn-line:#2A3240; --pn-ink:#ECEDF3;
    --pn-muted:#9AA6B9; --pn-accent:#99AAFF; --pn-accent-ink:#101526; --pn-ok:#55C89D; --pn-warn:#EFC778;
    --pn-control-line:#707C91;
  }
}
body{padding:0;background:var(--pn-bg);color:var(--pn-ink);font-size:15px}
.stage{max-width:none}
.pn-layout{display:grid;grid-template-columns:190px minmax(0,1fr);min-height:100vh}
.pn-shell{border-right:1px solid var(--pn-line);padding:26px 14px}
.pn-brand{display:block;padding:0 8px 12px}
.pn-brand strong{display:block;font-size:23px}
.pn-brand small{display:block;margin:8px 0;font-size:12px;letter-spacing:1px;text-transform:uppercase;color:var(--pn-muted)}
.pn-live{display:block;margin:20px 0;font-size:13px;color:var(--pn-ok)}
.pn-shell nav{display:flex;flex-direction:column;gap:6px}
.pn-shell nav a,.pn-shell nav button{display:flex;align-items:center;gap:6px;text-align:left;font:inherit;
  color:var(--pn-muted);background:none;border:1px solid transparent;border-radius:8px;padding:10px 14px;
  text-decoration:none;cursor:pointer}
.pn-shell nav a:hover{border-color:var(--pn-accent);color:var(--pn-ink)}
.pn-shell nav .pn-selected{background:var(--pn-surface-2);color:var(--pn-ink)}
.pn-badge{background:var(--pn-accent);color:var(--pn-accent-ink);border-radius:12px;padding:2px 7px;font-size:11px;font-weight:700}
.pn-badge:empty{display:none}
.pn-main{padding:32px 32px 60px;min-width:0}
.pn-main :is(a,button,summary,[tabindex]):focus-visible,.pn-shell :is(a,button):focus-visible{
  outline:2px solid var(--pn-accent);outline-offset:3px}
.pn-head h1{font-size:27px;margin:0 0 6px}
.pn-panel{background:var(--pn-surface);border:1px solid var(--pn-line);border-radius:10px;padding:22px;margin-bottom:20px}
.pn-panel h2{font-size:19px;margin:0 0 12px}
.pn-panel p{line-height:1.5;margin:0;overflow-wrap:anywhere}
@media (max-width:800px){
  .pn-layout{grid-template-columns:minmax(0,1fr);min-height:0}
  .pn-shell{border-right:0;border-bottom:1px solid var(--pn-line);padding:16px}
  .pn-brand{padding:0;display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:4px 12px}
  .pn-brand strong{display:inline;font-size:20px}
  .pn-brand small{display:inline;margin:0 0 0 8px;font-size:11px}
  .pn-live{margin:6px 0 12px;font-size:12px}
  .pn-shell nav{flex-direction:row;flex-wrap:wrap;gap:4px}
  .pn-shell nav a,.pn-shell nav button{padding:8px 10px}
  .pn-main{padding:20px 12px 48px}
  .pn-head h1{font-size:24px}
  .pn-panel{padding:18px}
}
"""
