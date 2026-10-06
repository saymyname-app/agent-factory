"""Stylesheet of the "Page projet" (spec af-oohx2x .49), taken from the
validated prototype origin/prototype/c01-project-page (variantes 1
"Tableau" and 3 "Bande", ``topbar``, ``summary``) with the prototype's own
class names. Only ever concatenated after cockpit.ui.base.tokens.CSS,
which carries the tokens and the shared components (chips, stepper,
zones); the home screen's "Projets" zone is styled there too.
"""

CSS = """
.brand{min-width:0}
.brand a.back{font-size:var(--fs-s);color:var(--accent);text-decoration:none;white-space:nowrap}
.brand h1{overflow-wrap:anywhere}
.zone{margin-top:22px}
.zone-h{display:flex;align-items:baseline;justify-content:space-between;gap:10px;margin-bottom:10px;flex-wrap:wrap}
.zone-h h2{font-size:var(--fs-l)}
.panel{background:var(--surface);border:1px solid var(--line);border-radius:var(--r)}
.summary-row{display:flex;flex-wrap:wrap;gap:6px 16px;align-items:center;background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:10px 14px;font-size:var(--fs-s)}
.summary-row .sep{width:1px;height:16px;background:var(--line)}
.history-link{font-size:var(--fs-s);color:var(--accent);text-decoration:none}

/* ---------- view selector: both views are in the page, one shows ---------- */
.cockpit-pp-view-selector{display:inline-flex;gap:4px;background:var(--surface-2);border-radius:10px;padding:3px}
.cockpit-pp-view-btn{border:0;background:transparent;border-radius:7px;padding:5px 12px;font-size:var(--fs-s);font-weight:600;color:var(--ink-2)}
.cockpit-pp-view-btn[aria-pressed="true"]{background:var(--surface);color:var(--ink);box-shadow:var(--shadow)}
.cockpit-pp-view{display:none}
.cockpit-project-page[data-view="tableau"] .cockpit-pp-view-tableau{display:block}
.cockpit-project-page[data-view="bande"] .cockpit-pp-view-bande{display:block}

/* ---------- variante 1 : Tableau (colonnes par étape) ---------- */
.v1 .pipe-scroll{overflow-x:auto;border:1px solid var(--line);border-radius:var(--r);background:var(--surface)}
.v1 .board{display:grid;grid-template-columns:repeat(var(--n,7),minmax(168px,1fr));min-width:calc(var(--n,7) * 168px)}
.v1 .board > div{padding:10px 12px;border-top:1px solid var(--line);border-left:1px solid var(--line);font-size:var(--fs-s)}
.v1 .board > .bh{border-top:0}
.v1 .board > .first{border-left:0}
.v1 .bh{font-size:var(--fs-xs);color:var(--muted);text-transform:uppercase;letter-spacing:.06em;font-weight:600;background:var(--surface-2);display:flex;justify-content:space-between;align-items:center}
.v1 .bh .n{font-family:var(--mono);color:var(--ink-2)}
.v1 .card{display:grid;gap:6px;justify-items:start;background:var(--surface-2);border-radius:8px;padding:9px 10px;margin-bottom:8px;border:1px solid transparent}
.v1 .card.urgent-b{border-color:var(--urgent)}
.v1 .card .n{font-weight:700;font-size:var(--fs-s)}
.v1 .card .s{font-size:var(--fs-xs);color:var(--ink-2)}
.v1 .card .chip{white-space:normal}

/* ---------- variante 3 : Bande (liste continue, repère d'étape par chantier) ---------- */
.v3 .strip{display:grid;gap:10px}
.v3 .s-item{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:12px 14px;display:grid;gap:8px}
.v3 .s-item .top{display:flex;justify-content:space-between;align-items:baseline;gap:10px}
.v3 .s-item .n{font-weight:700;font-size:var(--fs-m)}
.v3 .s-item .s{font-size:var(--fs-s);color:var(--ink-2)}
.v3 .stepnames{display:flex;justify-content:space-between;font-size:10.5px;color:var(--muted);margin-top:-4px}
.v3 .stepnames span.on{color:var(--accent);font-weight:600}
@container app (min-width: 900px){
  .v3 .strip{grid-template-columns:1fr 1fr}
}

/* ---------- travail hors chantier, historique ---------- */
.cockpit-pp-hc-item{display:flex;gap:10px;align-items:baseline;padding:10px 14px;border-top:1px solid var(--line);font-size:var(--fs-s)}
.cockpit-pp-hc-item:first-child{border-top:0}
.cockpit-historique{margin-top:22px}
.cockpit-historique h2{font-size:var(--fs-l);margin-bottom:10px}
.cockpit-historique-status{color:var(--muted);font-size:var(--fs-s)}
.cockpit-historique-list{background:var(--surface);border:1px solid var(--line);border-radius:var(--r)}
.cockpit-historique-row{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;padding:10px 14px;border-top:1px solid var(--line);font-size:var(--fs-s)}
.cockpit-historique-row:first-child{border-top:0}
.cockpit-historique-titre{font-weight:600}
.cockpit-historique-detail{color:var(--ink-2)}
"""
