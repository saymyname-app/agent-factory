"""Variant D visual tokens, extracted verbatim from the validated prototype
(prototype/c01-home-screen, spec af-oohx2x "Base visuelle"). Every cockpit
screen must be built against these — do not invent new colors here.
"""

CSS = """
:root {
  --bg:#F2F4F8; --surface:#FFFFFF; --surface-2:#EAEEF4; --ink:#151B26; --ink-2:#465063; --muted:#687286;
  --line:#D8DDE6; --accent:#2B4CC0; --accent-soft:#E3E8FA;
  --urgent:#C22D25; --normal:#AD6208; --info:#5A6679; --ok:#1F7B4B;
  --r:10px; --fs-xs:12.5px; --fs-s:14px; --fs-m:16px; --fs-l:19px; --fs-xl:24px;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg:#0D1015; --surface:#161A21; --surface-2:#1D222B; --ink:#E6E9EF; --ink-2:#B6BDCA; --muted:#8A93A4;
    --line:#2A313D; --accent:#8FA3FF; --accent-soft:#1E2644;
    --urgent:#FF6F63; --normal:#F0A33A; --info:#9BA5B7; --ok:#4DC48B;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: "Atkinson Hyperlegible Next", "Atkinson Hyperlegible", system-ui, sans-serif;
  font-size: var(--fs-m);
}
.cockpit-headline {
  padding: 12px 16px;
  border-bottom: 1px solid var(--line);
  background: var(--surface);
  font-size: var(--fs-l);
}
.cockpit-headline[data-ok="true"] { color: var(--ok); }
.cockpit-headline[data-ok="false"] { color: var(--normal); }
.cockpit-stale-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.cockpit-stale-list li {
  padding: 8px 16px;
  border-bottom: 1px solid var(--line);
  background: var(--surface-2);
  color: var(--ink-2);
  font-size: var(--fs-s);
}
time.cockpit-time { font-family: "Atkinson Hyperlegible Next Mono", ui-monospace, monospace; }
/* Out-of-scope touch (T13, af-cx20q9 -- declared scope lib/cockpit/ui/actions/**):
   Operator Action controls and the greyed "reportee" state (spec .23). */
li.cockpit-request[data-reportee="true"] { opacity: 0.55; }
.cockpit-actions { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.cockpit-action {
  border: 1px solid var(--line);
  background: var(--surface-2);
  color: var(--ink);
  border-radius: var(--r);
  padding: 6px 10px;
  font-size: var(--fs-s);
  cursor: pointer;
}
.cockpit-action-tokens { color: var(--normal); }
.cockpit-actions-explication { font-size: var(--fs-xs); color: var(--muted); margin: 4px 0 0; }
.cockpit-undo-toast {
  position: fixed;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--ink);
  color: var(--bg);
  border-radius: var(--r);
  padding: 8px 12px;
  font-size: var(--fs-s);
  display: flex;
  gap: 8px;
  align-items: center;
  z-index: 10;
}
.cockpit-undo-toast button { background: transparent; color: var(--accent-soft); border: none; cursor: pointer; }
"""
