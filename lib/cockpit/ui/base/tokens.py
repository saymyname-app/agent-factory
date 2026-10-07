"""Variant D stylesheet, taken from the validated prototype
(origin/prototype/c01-home-screen, prototypes/c01-home-screen/index.html;
spec af-oohx2x "Base visuelle"): its tokens, its shared components and the
layout of its variant D ("liste de C + Projets de A"). Class names are the
prototype's own, so a rule here can be compared with the prototype line for
line. Do not invent colors here; a new component reuses these tokens.
"""

FONTS_HEAD = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    "family=Atkinson+Hyperlegible+Next:wght@400;500;600;700&"
    'family=Atkinson+Hyperlegible+Mono:wght@400;600&display=swap">\n'
)

CSS = """
:root{
  --bg:#F2F4F8; --surface:#FFFFFF; --surface-2:#EAEEF4; --ink:#151B26; --ink-2:#465063; --muted:#687286;
  --line:#D8DDE6; --accent:#2B4CC0; --accent-ink:#FFFFFF; --accent-soft:#E3E8FA;
  --urgent:#C22D25; --urgent-soft:#FBE6E4; --normal:#AD6208; --normal-soft:#FAEDD6;
  --info:#5A6679; --info-soft:#E8ECF2; --ok:#1F7B4B; --ok-soft:#DFF1E6;
  --shadow:0 1px 2px rgba(20,30,50,.06),0 4px 14px rgba(20,30,50,.06);
  --font:"Atkinson Hyperlegible Next",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --mono:"Atkinson Hyperlegible Mono",ui-monospace,"SF Mono",Consolas,monospace;
  --r:10px; --fs-xs:12.5px; --fs-s:14px; --fs-m:16px; --fs-l:19px; --fs-xl:24px;
}
@media (prefers-color-scheme: dark){
  :root{
    color-scheme:dark;
    --bg:#0D1015; --surface:#161A21; --surface-2:#1D222B; --ink:#E6E9EF; --ink-2:#B6BDCA; --muted:#8A93A4;
    --line:#2A313D; --accent:#8FA3FF; --accent-ink:#0D1015; --accent-soft:#1E2644;
    --urgent:#FF6F63; --urgent-soft:#3A1B19; --normal:#F0A33A; --normal-soft:#35270F;
    --info:#9BA5B7; --info-soft:#222833; --ok:#4DC48B; --ok-soft:#15301F;
    --shadow:0 1px 2px rgba(0,0,0,.4),0 4px 14px rgba(0,0,0,.25);
  }
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);font-size:var(--fs-m);line-height:1.45;padding-inline:16px;padding-block:0 48px}
h1,h2,h3{margin:0;text-wrap:balance;font-weight:700}
p{margin:0}
button,select,input{font:inherit;color:inherit}
button{cursor:pointer}
button:focus-visible,summary:focus-visible,select:focus-visible,input:focus-visible,a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.mono,time{font-family:var(--mono);font-variant-numeric:tabular-nums}
.muted{color:var(--muted)}
.stage{max-width:1280px;margin-inline:auto}
.app{container-type:inline-size;container-name:app}

/* ---------- shared components ---------- */
.topbar{display:flex;align-items:baseline;justify-content:space-between;gap:12px;flex-wrap:wrap;padding-block:18px 10px}
.brand{display:flex;align-items:baseline;gap:10px}
.brand h1{font-size:var(--fs-l);letter-spacing:-.01em}
.brand .who{font-size:var(--fs-xs);color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
.fresh{display:inline-flex;align-items:center;gap:8px;font-size:var(--fs-s);color:var(--ink-2);flex-wrap:wrap}
.fresh .dot{width:8px;height:8px;border-radius:50%;background:var(--ok);flex:none}
.fresh.warn .dot{background:var(--normal)}
.fresh form{display:inline-flex;margin:0}
.recheck{border:1px solid var(--line);background:var(--surface);border-radius:999px;padding:2px 10px;font-size:var(--fs-xs)}
.banner{border-radius:var(--r);padding:10px 14px;font-size:var(--fs-s);margin-block:6px 10px;display:flex;gap:10px;align-items:flex-start}
.banner.off{background:var(--urgent);color:#fff}
.lvl{display:inline-flex;align-items:center;gap:6px;font-size:var(--fs-xs);font-weight:600;letter-spacing:.02em;white-space:nowrap}
.lvl i{width:10px;height:10px;border-radius:50%;display:inline-block;flex:none}
.lvl.urgent{color:var(--urgent)} .lvl.urgent i{background:var(--urgent)}
.lvl.normal{color:var(--normal)} .lvl.normal i{background:var(--normal)}
.lvl.info{color:var(--info)} .lvl.info i{border:2px solid var(--info)}
.lvl.ok{color:var(--ok)} .lvl.ok i{background:var(--ok)}
.meta{font-size:var(--fs-xs);color:var(--muted);display:flex;flex-wrap:wrap;gap:4px 10px}
.meta b{color:var(--ink-2);font-weight:600}
.lbl{font-size:var(--fs-xs);text-transform:uppercase;letter-spacing:.07em;color:var(--muted);font-weight:600}
.why{color:var(--ink-2)}
.todo{font-weight:600}
.incomplete{display:inline-block;font-size:var(--fs-xs);background:var(--normal-soft);color:var(--normal);border-radius:6px;padding:1px 7px;font-weight:600}
.chip{display:inline-flex;align-items:center;gap:6px;font-size:var(--fs-xs);border-radius:999px;padding:2px 9px;background:var(--surface-2);color:var(--ink-2);font-weight:600;white-space:nowrap}
.chip.atoi{background:var(--accent-soft);color:var(--accent)}
.chip.probleme{background:var(--normal-soft);color:var(--normal)}
.chip.bloque{background:var(--urgent-soft);color:var(--urgent)}
.chip.ack{background:var(--surface-2);color:var(--muted)}
.acts{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.btn{border:1px solid var(--line);background:var(--surface);border-radius:8px;padding:7px 12px;font-size:var(--fs-s);font-weight:600;min-height:38px;text-decoration:none;display:inline-flex;align-items:center;gap:6px}
.btn:hover{border-color:var(--ink-2)}
.btn.primary{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}
.btn.ghost{border-color:transparent;background:transparent;color:var(--accent);padding-inline:6px}
.btn.opt{text-align:left;display:flex;gap:10px;align-items:baseline;width:100%}
div.btn.opt{cursor:default}
div.btn.opt:hover{border-color:var(--line)}
.btn.opt .k{font-family:var(--mono);color:var(--accent)}
.btn.opt .ot{display:grid;gap:3px;justify-items:start}
.cockpit-action-tokens{flex-wrap:wrap;text-align:left;gap:2px 6px}
.btn small{font-weight:400;font-size:var(--fs-xs);color:var(--muted)}
.oc{font-size:var(--fs-xs);font-weight:400;color:var(--ink-2);line-height:1.4}
.hint{margin:0;font-size:var(--fs-xs);color:var(--muted)}
.btn[disabled]{opacity:.45;cursor:not-allowed}
.cockpit-armed{background:var(--accent-soft);border-color:var(--accent)}
.cockpit-armed-note{font-size:var(--fs-xs);font-weight:600;color:var(--accent)}
.cockpit-done{opacity:.6}
.cockpit-done [aria-disabled=true]{pointer-events:none;cursor:default}
.cockpit-done-note{opacity:1;margin:8px 0}
.field{border:1px solid var(--line);background:var(--surface);border-radius:8px;padding:6px 10px;font-size:var(--fs-s);min-height:38px}
.inline{display:inline-flex;gap:6px;align-items:center;flex-wrap:wrap}
details.more{font-size:var(--fs-s)}
details.more summary{color:var(--muted);cursor:pointer;font-size:var(--fs-xs);list-style:none;display:inline-flex;gap:6px;align-items:center}
details.more summary::-webkit-details-marker{display:none}
details.more summary::before{content:"\\25B8";font-size:10px}
details.more[open] summary::before{content:"\\25BE"}
.det{display:grid;gap:6px;margin-top:8px;padding:10px 12px;background:var(--surface-2);border-radius:8px;font-size:var(--fs-xs);color:var(--ink-2)}
.det .row{display:grid;grid-template-columns:92px 1fr;gap:10px}
.det .row span:first-child{color:var(--muted)}
.det code{font-family:var(--mono);font-size:12px;overflow-wrap:anywhere}
.snoozemenu{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:var(--fs-s)}
[hidden]{display:none !important}
.stale-val{opacity:.55}
.unknown{font-size:var(--fs-s);color:var(--normal);background:var(--normal-soft);border-radius:8px;padding:8px 12px}
.empty{display:flex;gap:10px;align-items:center;padding:18px;border:1px dashed var(--line);border-radius:var(--r);color:var(--ink-2)}
.empty .dot{width:10px;height:10px;border-radius:50%;background:var(--ok);flex:none}
.toast,.cockpit-undo-toast{position:fixed;left:50%;bottom:calc(20px + env(safe-area-inset-bottom,0px));transform:translateX(-50%);background:var(--ink);color:var(--bg);border-radius:10px;padding:10px 16px;font-size:var(--fs-s);max-width:min(92vw,520px);z-index:60;box-shadow:var(--shadow);display:flex;gap:10px;align-items:center}
.cockpit-undo-toast button{background:transparent;color:inherit;border:0;text-decoration:underline;font-weight:600}

/* ---------- inbox: short list + detail beside it (PC), sheet (iPhone) ---------- */
.vc .status{display:flex;flex-wrap:wrap;gap:6px 16px;align-items:center;background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:10px 14px;font-size:var(--fs-s)}
.vc .status .sep{width:1px;height:16px;background:var(--line)}
.vc .inbox{display:grid;gap:14px;margin-top:14px}
.vc .list{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);overflow:hidden}
.vc .list h2{font-size:var(--fs-m);padding:12px 14px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between}
.vc .li{display:grid;grid-template-columns:auto 1fr auto;gap:10px;align-items:start;width:100%;text-align:left;border:0;border-top:1px solid var(--line);background:transparent;padding:11px 14px;font-size:var(--fs-s);color:inherit;text-decoration:none}
.vc .li:first-of-type{border-top:0}
.vc .li[aria-current="true"]{background:var(--accent-soft)}
.vc .li[data-reportee="true"]{opacity:.55}
.vc .li .q{font-weight:600;line-height:1.35}
.vc .li .p{font-size:var(--fs-xs);color:var(--muted);margin-top:2px}
.vc .li time{font-size:var(--fs-xs);color:var(--muted)}
.vc .list-foot{padding:10px 14px;border-top:1px solid var(--line);font-size:var(--fs-xs)}
.vc .list-foot a{color:var(--accent);text-decoration:none}
.vc .detail{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:18px 20px;display:none;gap:14px;align-content:start}
.vc .detail .quoi{font-size:var(--fs-xl);line-height:1.25;font-weight:700;letter-spacing:-.01em}
.vc .detail .sec{display:grid;gap:4px}
.vc .detail .opts{display:grid;gap:8px}
.vc .back{display:none}
.vc.sheet .list{display:none}
.vc.sheet .detail.on{display:grid}
.vc.sheet .back{display:inline-flex;justify-self:start}
@container app (min-width: 900px){
  .vc .inbox{grid-template-columns:minmax(300px,.9fr) minmax(0,1.3fr)}
  .vc .inbox.solo{grid-template-columns:minmax(0,1fr)}
  .vc .detail.on{display:grid}
  .vc.sheet .list{display:block}
  .vc .back,.vc.sheet .back{display:none}
}

/* ---------- zones under the inbox ---------- */
.va .zone{margin-top:22px}
.va .zone-h{display:flex;align-items:baseline;justify-content:space-between;gap:10px;margin-bottom:10px}
.va .zone-h h2{font-size:var(--fs-l)}
.va .health{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:12px 16px}
.va .hlist{display:grid;gap:6px;font-size:var(--fs-s)}
.va .hl{display:flex;gap:10px;align-items:baseline}
.va .hl > .lvl:empty{width:10px;flex:none}
.va .health .hint{margin-top:8px}
.va .health .acts{margin-top:10px}

/* ---------- "Projets": one block per project, a stepper per chantier ---------- */
.va .projects{display:grid;gap:0;background:var(--surface);border:1px solid var(--line);border-radius:var(--r)}
.va .proj{padding:12px 16px;border-top:1px solid var(--line)}
.va .proj:first-child{border-top:0}
.va .proj-h{display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap}
.va .proj-h h3{font-size:var(--fs-m)}
.va .ch{display:grid;grid-template-columns:1fr auto;gap:4px 12px;padding-block:9px;border-top:1px dashed var(--line)}
.va .ch .n{font-weight:600}
.va .ch .s,.va .proj > .s{font-size:var(--fs-s);color:var(--ink-2)}
.va .proj > p.s{padding-block:9px;border-top:1px dashed var(--line);color:var(--muted)}
.va .ch .stepper{grid-column:1 / -1}
.stepper{display:flex;gap:3px;align-items:center}
.stepper span{height:6px;flex:1;border-radius:3px;background:var(--line);min-width:10px}
.stepper span.done{background:var(--ink-2)}
.stepper span.cur{background:var(--accent)}
.chip.go{border:0;cursor:pointer;font:inherit;font-size:var(--fs-xs);font-weight:600;text-decoration:none}
.chip.go::after{content:" \\2192"}
.chip.go:hover{filter:brightness(.95);text-decoration:underline}
.accpanel{grid-column:1 / -1;display:grid;gap:8px;background:var(--accent-soft);border-radius:8px;padding:10px 12px;font-size:var(--fs-s)}
.cockpit-project-sans h3{color:var(--urgent)}

/* ---------- "Déconnecté du cockpit depuis HH:MM" (spec .69) ---------- */
.cockpit-disconnected-banner{position:sticky;top:0;z-index:20;margin-inline:-16px;padding:10px 16px;background:var(--urgent);color:#fff;font-size:var(--fs-s);font-weight:700;text-align:center}
body.cockpit-greyed > *:not(.cockpit-disconnected-banner){opacity:.55;filter:grayscale(1)}
"""
