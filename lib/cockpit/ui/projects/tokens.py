"""Extra CSS for the "Projets" section -- variant D visual tokens (spec
af-oohx2x "Base visuelle"; prototype variant D, branch
prototype/c01-home-screen), reusing the color/radius/font custom properties
already declared by cockpit.ui.base.tokens.CSS (only ever concatenated
after that one -- see cockpit.ui.base.page.render_home's extra_css)."""

CSS = """
.cockpit-projects {
  margin-top: 16px;
  border: 1px solid var(--line);
  border-radius: var(--r);
  background: var(--surface);
  padding: 12px 16px;
}
.cockpit-projects h2 { font-size: var(--fs-l); margin: 0 0 8px; }
.cockpit-projects-status { color: var(--muted); font-size: var(--fs-s); margin: 0; }
.cockpit-projects-list { display: grid; gap: 14px; }
.cockpit-project { border-top: 1px solid var(--line); padding-top: 10px; }
.cockpit-project:first-child { border-top: none; padding-top: 0; }
.cockpit-project-h {
  display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap;
}
.cockpit-project-h h3 { font-size: var(--fs-m); margin: 0; }
.cockpit-project-roadmap { font-size: var(--fs-xs); color: var(--muted); }
.cockpit-project-roadmap[data-state="unknown"] { color: var(--normal); }
.cockpit-project-defect { font-size: var(--fs-xs); color: var(--urgent); }
.cockpit-project-empty { font-size: var(--fs-s); color: var(--muted); margin: 6px 0 0; }
.cockpit-project-chantiers { display: grid; gap: 8px; margin-top: 8px; }
.cockpit-chantier {
  display: grid; grid-template-columns: 1fr auto; gap: 2px 8px; align-items: center;
}
.cockpit-chantier-n { font-size: var(--fs-s); font-weight: 600; }
.cockpit-chantier-s { font-size: var(--fs-xs); color: var(--muted); grid-column: 1 / -1; }
.cockpit-stepper { display: flex; gap: 3px; grid-column: 1 / -1; }
.cockpit-stepper span {
  width: 16px; height: 5px; border-radius: 999px; background: var(--line);
}
.cockpit-stepper span.done { background: var(--ok); }
.cockpit-stepper span.cur { background: var(--accent); }
.cockpit-project-sans .cockpit-project-h h3 { color: var(--urgent); }
"""
