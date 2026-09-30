"""Renders the freshness headline (spec .64) over the variant D base.

Pure function of a :class:`~cockpit.core.readmodel.ReadModel` snapshot — no
I/O, so it is exercised directly by tests without an HTTP round trip.
"""
import html

from cockpit.ui.base.tokens import CSS


def render_home(headline_text, stale_rows, requests_section_html=""):
    """``stale_rows``: the same names :meth:`ReadModel.stale_or_unknown`
    returns, each resolved to its display name and freshness state.
    ``requests_section_html`` (T12, af-is5e97): the pre-rendered "Ce qui
    t'attend" section HTML, injected below the freshness headline; the
    empty default keeps every caller that predates it unchanged."""
    all_fresh = not stale_rows
    items = "".join(
        '<li data-freshness="%s">%s</li>'
        % (html.escape(row["freshness"]), html.escape(row["display_name"]))
        for row in stale_rows
    )
    stale_list = (
        '<ul class="cockpit-stale-list">%s</ul>' % items if stale_rows else ""
    )
    return (
        "<!doctype html>\n"
        '<html lang="fr">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Cockpit</title>\n"
        "<style>%s</style>\n"
        "</head>\n"
        "<body>\n"
        '<header class="cockpit-headline" data-ok="%s">%s</header>\n'
        "%s\n"
        "%s\n"
        "</body>\n"
        "</html>\n"
    ) % (
        CSS,
        "true" if all_fresh else "false",
        html.escape(headline_text),
        stale_list,
        requests_section_html,
    )
