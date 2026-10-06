"""Extra CSS for the "Projets" section -- variant D visual tokens (spec
af-oohx2x "Base visuelle"; prototype variant D, branch
prototype/c01-home-screen), reusing the color/radius/font custom properties
already declared by cockpit.ui.base.tokens.CSS (only ever concatenated
after that one -- see cockpit.ui.base.page.render_home's extra_css)."""

CSS = """
/* The home screen's "Projets" zone is styled by cockpit.ui.base.tokens
   (variant D); what follows is the project page only. */
/* T22 (af-9tfjsc): "Page projet" (spec .49) -- cockpit.ui.projects.project_page */
.cockpit-project-page { margin-top: 16px; }
.cockpit-pp-header { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.cockpit-pp-back { font-size: var(--fs-s); color: var(--accent); text-decoration: none; }
.cockpit-pp-header h1 { font-size: var(--fs-l); margin: 0; }
.cockpit-pp-view-selector { display: inline-flex; gap: 4px; margin: 10px 0; }
.cockpit-pp-view-btn {
  border: 1px solid var(--line); background: var(--surface); border-radius: 999px;
  padding: 4px 12px; font-size: var(--fs-xs); font-weight: 600;
}
.cockpit-pp-zone { margin-top: 14px; }
.cockpit-pp-zone-h { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }
.cockpit-pp-zone-h h2 { font-size: var(--fs-l); margin: 0; }
.cockpit-pp-historique-link { font-size: var(--fs-s); color: var(--accent); text-decoration: none; }
.cockpit-pp-empty { color: var(--muted); font-size: var(--fs-s); }

/* Both views are always rendered server-side; only one shows at a time,
   driven by the root's data-view attribute (project_page.VIEW_SCRIPT). */
.cockpit-pp-view { display: none; }
.cockpit-project-page[data-view="tableau"] .cockpit-pp-view-tableau { display: block; }
.cockpit-project-page[data-view="bande"] .cockpit-pp-view-bande { display: block; }

.cockpit-pp-board { display: grid; grid-template-columns: repeat(7, minmax(140px, 1fr)); gap: 0; overflow-x: auto; border: 1px solid var(--line); border-radius: var(--r); background: var(--surface); }
.cockpit-pp-col { border-left: 1px solid var(--line); padding: 8px 10px; }
.cockpit-pp-col:first-child { border-left: none; }
.cockpit-pp-col-h { font-size: var(--fs-xs); color: var(--muted); text-transform: uppercase; letter-spacing: .06em; font-weight: 600; display: flex; justify-content: space-between; }
.cockpit-pp-card { background: var(--surface-2); border-radius: 8px; padding: 8px 9px; margin-top: 8px; display: grid; gap: 4px; }
.cockpit-pp-card-n { font-weight: 700; font-size: var(--fs-s); }
.cockpit-pp-card-s { font-size: var(--fs-xs); color: var(--ink-2); }

.cockpit-pp-strip { display: grid; gap: 10px; margin-top: 10px; }
.cockpit-pp-strip-item { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r); padding: 10px 12px; display: grid; gap: 6px; }
.cockpit-pp-strip-n { font-weight: 700; }
.cockpit-pp-strip-s { font-size: var(--fs-xs); color: var(--ink-2); }

.cockpit-pp-hors-chantier { margin-top: 16px; border: 1px solid var(--line); border-radius: var(--r); background: var(--surface); padding: 12px 16px; }
.cockpit-pp-hors-chantier h2 { font-size: var(--fs-l); margin: 0 0 8px; }
.cockpit-pp-hc-status { color: var(--muted); font-size: var(--fs-s); margin: 0; }
.cockpit-pp-hc-list { display: grid; gap: 8px; }
.cockpit-pp-hc-item { display: flex; gap: 8px; align-items: baseline; }
.cockpit-pp-hc-kind { font-size: var(--fs-xs); color: var(--accent); background: var(--accent-soft); border-radius: 999px; padding: 1px 8px; }
"""
