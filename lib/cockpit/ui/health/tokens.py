"""Extra CSS for the "Zone santé de l'usine" section — variant D visual
tokens (spec af-oohx2x "Base visuelle"), reusing the color/radius/font
custom properties already declared by cockpit.ui.base.tokens.CSS (this
stylesheet is only ever concatenated after that one — see
cockpit.ui.base.page.render_home's extra_css).
"""

CSS = """
.cockpit-health {
  margin-top: 16px;
  border: 1px solid var(--line);
  border-radius: var(--r);
  background: var(--surface);
  padding: 12px 16px;
}
.cockpit-health h2 { font-size: var(--fs-l); margin: 0 0 8px; }
.cockpit-health-ok { color: var(--ok); font-size: var(--fs-s); margin: 0; }
.cockpit-health ul { list-style: none; margin: 8px 0 0; padding: 0; display: grid; gap: 6px; }
.cockpit-health li { font-size: var(--fs-s); }
.cockpit-health li[data-kind="bad"] { color: var(--urgent); }
.cockpit-health li[data-kind="warn"] { color: var(--normal); }
.cockpit-health .cockpit-health-checked {
  font-size: var(--fs-xs); color: var(--muted); margin: 8px 0 0;
}
.cockpit-health .recheck {
  border: 1px solid var(--line); background: var(--surface-2); border-radius: 999px;
  padding: 2px 10px; font-size: var(--fs-xs); margin-top: 10px;
}
"""
