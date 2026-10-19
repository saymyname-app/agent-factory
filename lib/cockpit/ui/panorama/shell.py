"""The shell of B/Panorama (Validated Prototype prototype/cockpit-b-zones-20261012
at 632deea; Spec af-2zseit, user stories 124, 147 and 175).

    render_shell(destination, main, waiting=2, live="● En marche · 2 agents")

returns the navigation B and the destination's ``main``, to be passed to
:func:`cockpit.ui.base.page.render_document` with :data:`CSS`. The entry of
the destination open is a button marked ``aria-current="page"``; every
other one is a button that opens its address (a form of its own, no
script), so a destination is reached from any other one. The parts carry
the anchors of the reference (``data-anchor``), numbered by :class:`Anchors`
as the frozen pages number them: those of the shell first, then those of
``main``.

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


def render_shell(destination, main, waiting=None, live=None, anchors=None, own_main=False):
    """The navigation B, then the destination in ``<main>``. ``main``: its
    HTML, or a function that draws it with the numbering of the page, once
    the shell has numbered its own parts. ``waiting``: how many requests
    wait for the operator, shown on « Vue d’ensemble » (None: unknown,
    nothing shown); ``live``: the state of the factory, one line.
    ``own_main``: ``main`` is a ``<main>`` of its own, with the anchors of
    its own reference (the Runs pages), placed beside the navigation as it
    is."""
    anchors = anchors or Anchors()
    shell = (anchors("shell-nav"), anchors("brand"), anchors("div"), anchors("strong"), anchors("small"),
             anchors("live"))
    nav = anchors("nav")
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
            entries.append(open_button(href, html.escape(label) + badge, anchors("button"), escaped=True))
    main_html = main(anchors) if callable(main) else main
    main_part = main_html if own_main else '<main class="pn-main" %s>%s</main>' % (anchors("main"), main_html)
    return (
        '<div class="pn-layout">'
        '<aside class="pn-shell" %s>'
        '<header class="pn-brand" %s><div %s><strong %s>Cockpit</strong><small %s>Usine + projets</small></div>'
        '<span class="pn-live" %s>%s</span></header>'
        '<nav aria-label="Destinations" %s>%s</nav>'
        "</aside>"
        "%s"
        "</div>"
    ) % (
        *shell, html.escape(live or "● État actuel inconnu"), nav, "".join(entries), main_part,
    )


def open_button(href, label, anchor, css_class="", escaped=False):
    """A button that opens ``href``: the button of a form of its own sent
    by GET -- Enter or a click opens the address, with no script.
    ``escaped``: ``label`` is already HTML."""
    return '<form class="pn-open" method="get" action="%s"><button type="submit"%s %s>%s</button></form>' % (
        html.escape(href), ' class="%s"' % css_class if css_class else "", anchor,
        label if escaped else html.escape(label))


def render_not_folded(label):
    """The main part of a destination whose Prototype Fold is not done yet:
    it says so, rather than a page that would look like the destination."""
    return (
        '<div class="pn-head"><h1>%s</h1></div>'
        '<section class="pn-panel"><h2>Destination pas encore raccordée</h2>'
        "<p>Cette page du cockpit n’est pas encore servie ici. Les autres destinations restent accessibles "
        "depuis la navigation.</p></section>"
    ) % html.escape(label)


# The tokens of the reference under its names and with its values (--bg,
# --surface, --line, --ink, --muted, --accent, --ok, --warn), light when the
# browser prefers it, dark otherwise. They follow the variant D stylesheet
# of the document, which names some of them too, so these are the ones the
# page holds. The others are the shell's own: --pn-muted-text and
# --pn-warn-text, the muted and the warning text, darker in the light theme
# where the reference's are under 4.5:1 on --bg; --pn-control-line, the box
# of a control, 3:1 at least on the surface and the background where --line
# is not. The type of the page is the reference's: 15 px system-ui, normal
# leading, a paragraph at 1.5. The shell's layout: the navigation beside the
# destination, above it under 800 px. A rule of a destination reuses these
# tokens.
CSS = """
:root{
  color-scheme:light;
  --bg:#f3f5f9; --surface:#fff; --line:#dbe0e8; --ink:#17202e; --muted:#657185; --accent:#415fce;
  --ok:#1c7954; --warn:#97691e;
  --pn-surface-2:#E6EBFB; --pn-accent-ink:#FFFFFF; --pn-muted-text:#566175; --pn-warn-text:#85590F;
  --pn-control-line:#788396;
}
@media (prefers-color-scheme: dark){
  :root{
    color-scheme:dark;
    --bg:#0d1015; --surface:#161b23; --line:#2a3240; --ink:#ecedf3; --muted:#9aa6b9; --accent:#99aaff;
    --ok:#55c89d; --warn:#efc778;
    --pn-surface-2:#222D46; --pn-accent-ink:#101526; --pn-muted-text:#9aa6b9; --pn-warn-text:#efc778;
    --pn-control-line:#707C91;
  }
}
body{padding:0;background:var(--bg);color:var(--ink);font:15px system-ui}
.pn-main p{line-height:1.5}
.pn-open{display:contents}
.stage{max-width:none}
.pn-layout{display:grid;grid-template-columns:190px minmax(0,1fr);min-height:100vh}
.pn-shell{border-right:1px solid var(--line);padding:26px 14px}
.pn-brand{display:block;padding:0 8px 12px}
.pn-brand strong{display:block;font-size:23px}
.pn-brand small{display:block;margin:8px 0;font-size:12px;letter-spacing:1px;text-transform:uppercase;color:var(--pn-muted-text)}
.pn-live{display:block;margin:20px 0;font-size:13px;color:var(--ok)}
.pn-shell nav{display:flex;flex-direction:column;gap:6px}
.pn-shell nav button{display:flex;align-items:center;gap:6px;text-align:left;font:inherit;
  color:var(--pn-muted-text);background:none;border:1px solid transparent;border-radius:8px;padding:10px 14px;
  text-decoration:none;cursor:pointer}
.pn-shell nav button:hover{border-color:var(--accent);color:var(--ink)}
.pn-shell nav .pn-selected{background:var(--pn-surface-2);color:var(--ink)}
.pn-badge{background:var(--accent);color:var(--pn-accent-ink);border-radius:12px;padding:2px 7px;font-size:11px;font-weight:700}
.pn-badge:empty{display:none}
.pn-main{padding:32px 32px 60px;min-width:0}
.pn-main :is(a,button,summary,[tabindex]):focus-visible,.pn-shell button:focus-visible{
  outline:2px solid var(--accent);outline-offset:3px}
.pn-head h1{font-size:27px;margin:0 0 6px}
.pn-panel{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:22px;margin-bottom:20px}
.pn-panel h2{font-size:19px;margin:0 0 12px}
.pn-panel p{line-height:1.5;margin:0;overflow-wrap:anywhere}
@media (max-width:800px){
  .pn-layout{grid-template-columns:minmax(0,1fr);min-height:0}
  .pn-shell{border-right:0;border-bottom:1px solid var(--line);padding:16px}
  .pn-brand{padding:0;display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:4px 12px}
  .pn-brand strong{display:inline;font-size:20px}
  .pn-brand small{display:inline;margin:0 0 0 8px;font-size:11px}
  .pn-live{margin:6px 0 12px;font-size:12px}
  .pn-shell nav{flex-direction:row;flex-wrap:wrap;gap:4px}
  .pn-shell nav button{padding:8px 10px}
  .pn-main{padding:20px 12px 48px}
  .pn-head h1{font-size:24px}
  .pn-panel{padding:18px}
}
"""
