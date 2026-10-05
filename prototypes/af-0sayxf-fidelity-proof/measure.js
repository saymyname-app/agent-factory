#!/usr/bin/env node
/* PROTOTYPE JETABLE (af-0sayxf.18) -- moyens 2 et 3, dans un vrai navigateur :
   structure (arbre d'accessibilite), styles calcules + positions sur des
   ancres nommees, police reellement utilisee, difference de pixels.
   Prerequis : serve.py tourne. Ecrit out/measure.json et out/*.png.
   Usage : node prototypes/af-0sayxf-fidelity-proof/measure.js            */
const fs = require('fs');
const path = require('path');
const PW = process.env.PW || '/home/benja/.npm/_npx/705bc6b22212b352/node_modules/playwright-core';
const { chromium } = require(PW);
const OUT = path.join(__dirname, 'out');

const SIDES = {
  proto: { url: 'http://127.0.0.1:18174/prototype.html#d', hide: '#proto,#toastwrap,.frame-note{display:none!important}' },
  deliv: { url: 'http://127.0.0.1:18173/', hide: '' },
  // Temoin : le prototype avec 5 petits defauts semes (voir MUTATIONS dans serve.py).
  mutant: { url: 'http://127.0.0.1:18174/mutant.html#d', hide: '#proto,#toastwrap,.frame-note{display:none!important}' },
};
const VIEWPORTS = { pc: { width: 1280, height: 800 }, phone: { width: 390, height: 844 } };
// Table d'ancres ECRITE A LA MAIN : rien dans le prototype ni dans le livre ne
// dit quel element correspond a quel element (noms de classes differents).
const ANCHORS = {
  'page':                { proto: 'body',                    deliv: 'body' },
  'entete':              { proto: 'header.topbar',           deliv: 'header.cockpit-headline' },
  'marque (h1)':         { proto: 'header.topbar h1',        deliv: 'h1' },
  'ligne d\'etat':       { proto: '.status',                 deliv: 'header.cockpit-headline' },
  'boite de reception':  { proto: '.inbox',                  deliv: 'section.cockpit-requests' },
  'titre Ce qui t\'attend': { proto: '#inbox-list h2',       deliv: '.cockpit-requests h2' },
  'ligne de demande':    { proto: '#inbox-list .li',         deliv: 'li.cockpit-request' },
  'demande : quoi':      { proto: '#inbox-list .li .q',      deliv: '.cockpit-request-quoi' },
  'demande : niveau':    { proto: '#inbox-detail .lvl',      deliv: '.cockpit-request-level' },
  'panneau de detail':   { proto: '#inbox-detail',           deliv: '.cockpit-request-detail-pane' },
  'bouton d\'action':    { proto: '#inbox-detail .btn:not(.back)', deliv: 'button.cockpit-action' },
  'heure':               { proto: '#inbox-list time',        deliv: 'time' },
  'zone Projets':        { proto: '.projects',               deliv: '.cockpit-projects' },
  'carte projet':        { proto: '.proj',                   deliv: '.cockpit-project' },
  'bascule de theme':    { proto: '#theme',                  deliv: '[data-action="theme"]' },
};
const PROPS = ['font-family', 'font-size', 'font-weight', 'line-height', 'color', 'background-color',
  'border-radius', 'padding', 'display', 'box-shadow'];

async function capture(browser, side, vp, opts = {}) {
  const ctx = await browser.newContext({ viewport: VIEWPORTS[vp], colorScheme: 'light', deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  await page.goto(SIDES[side].url, { waitUntil: 'networkidle' });
  if (opts.scenario) await page.selectOption('#scen', opts.scenario);
  if (SIDES[side].hide) await page.addStyleTag({ content: SIDES[side].hide });
  await page.evaluate(() => document.fonts.ready);
  const tag = `${side}-${vp}${opts.scenario ? '-' + opts.scenario : ''}${opts.suffix || ''}`;
  const shot = await page.screenshot({ path: path.join(OUT, `shot-${tag}.png`) });
  await page.screenshot({ path: path.join(OUT, `full-${tag}.png`), fullPage: true });
  const res = { tag, shot };
  if (!opts.shotOnly) {
    res.aria = await page.locator('body').ariaSnapshot();
    res.fontsLoaded = await page.evaluate(() => [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family + ' ' + f.weight));
    res.overflowX = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    const cdp = await ctx.newCDPSession(page);
    await cdp.send('DOM.enable'); await cdp.send('CSS.enable');
    const { root } = await cdp.send('DOM.getDocument');
    res.anchors = {};
    for (const [name, sel] of Object.entries(ANCHORS)) {
      const s = sel[side] || sel.proto;
      const info = await page.evaluate(([s, props]) => {
        const el = document.querySelector(s); if (!el) return null;
        const cs = getComputedStyle(el), b = el.getBoundingClientRect();
        const o = { box: [Math.round(b.x), Math.round(b.y), Math.round(b.width), Math.round(b.height)], visible: b.width > 0 && b.height > 0 };
        for (const p of props) o[p] = cs.getPropertyValue(p);
        return o;
      }, [s, PROPS]);
      if (info) {
        try {
          const { nodeId } = await cdp.send('DOM.querySelector', { nodeId: root.nodeId, selector: s });
          const pf = await cdp.send('CSS.getPlatformFontsForNode', { nodeId });
          info.renderedFont = pf.fonts.sort((a, b) => b.glyphCount - a.glyphCount).map(f => f.familyName)[0] || null;
        } catch (e) { info.renderedFont = 'n/a'; }
      }
      res.anchors[name] = info;
    }
  }
  await ctx.close();
  return res;
}

async function pixelDiff(browser, a, b, name) {
  const page = await browser.newPage();
  const r = await page.evaluate(async ([a, b]) => {
    const load = src => new Promise(ok => { const i = new Image(); i.onload = () => ok(i); i.src = 'data:image/png;base64,' + src; });
    const [ia, ib] = [await load(a), await load(b)];
    const w = Math.min(ia.width, ib.width), h = Math.min(ia.height, ib.height);
    const mk = im => { const c = document.createElement('canvas'); c.width = w; c.height = h; const x = c.getContext('2d'); x.drawImage(im, 0, 0); return x.getImageData(0, 0, w, h); };
    const da = mk(ia), db = mk(ib);
    const c = document.createElement('canvas'); c.width = w; c.height = h; const x = c.getContext('2d'); const out = x.createImageData(w, h);
    let n = 0;
    for (let i = 0; i < da.data.length; i += 4) {
      const d = Math.max(Math.abs(da.data[i] - db.data[i]), Math.abs(da.data[i + 1] - db.data[i + 1]), Math.abs(da.data[i + 2] - db.data[i + 2]));
      const g = (da.data[i] + da.data[i + 1] + da.data[i + 2]) / 3;
      if (d > 24) { n++; out.data[i] = 226; out.data[i + 1] = 45; out.data[i + 2] = 37; }
      else { const f = 255 - (255 - g) * 0.25; out.data[i] = out.data[i + 1] = out.data[i + 2] = f; }
      out.data[i + 3] = 255;
    }
    x.putImageData(out, 0, 0);
    return { ratio: n / (w * h), png: c.toDataURL('image/png').split(',')[1] };
  }, [a.toString('base64'), b.toString('base64')]);
  fs.writeFileSync(path.join(OUT, `diff-${name}.png`), Buffer.from(r.png, 'base64'));
  await page.close();
  return Math.round(r.ratio * 10000) / 100;
}

function compareAnchors(p, d) {
  const rows = [];
  for (const name of Object.keys(ANCHORS)) {
    const a = p.anchors[name], b = d.anchors[name];
    if (!a || !b) { rows.push({ anchor: name, verdict: !a && !b ? 'absent des deux' : (!b ? 'ABSENT DU LIVRE' : 'absent du prototype') }); continue; }
    const deltas = [];
    for (const k of [...PROPS, 'renderedFont']) if (a[k] !== b[k]) deltas.push({ prop: k, proto: a[k], deliv: b[k] });
    if (Math.abs(a.box[2] - b.box[2]) > 4 || Math.abs(a.box[3] - b.box[3]) > 4) deltas.push({ prop: 'taille (l x h)', proto: a.box[2] + ' x ' + a.box[3], deliv: b.box[2] + ' x ' + b.box[3] });
    rows.push({ anchor: name, verdict: deltas.length ? deltas.length + ' ecart(s)' : 'identique', deltas });
  }
  return rows;
}
const ariaLines = s => s.split('\n').map(l => l.trim().replace(/^- /, '')).filter(Boolean);
const roleOnly = l => l.replace(/"[^"]*"/g, '""').replace(/: .*/, '');

(async () => {
  const browser = await chromium.launch();
  const out = { viewports: {}, pixel: {} };
  for (const vp of Object.keys(VIEWPORTS)) {
    const p = await capture(browser, 'proto', vp), d = await capture(browser, 'deliv', vp);
    const m = await capture(browser, 'mutant', vp);
    const pl = ariaLines(p.aria), ml = ariaLines(m.aria);
    out.mutant = out.mutant || {};
    out.mutant[vp] = {
      anchors: compareAnchors(p, m),
      ariaOnlyInProto: pl.filter(l => !ml.includes(l)), ariaOnlyInMutant: ml.filter(l => !pl.includes(l)),
      pixel: await pixelDiff(browser, p.shot, m.shot, `${vp}-proto-vs-mutant`),
    };
    const count = arr => arr.reduce((m, r) => (m[r] = (m[r] || 0) + 1, m), {});
    const pr = count(ariaLines(p.aria).map(roleOnly)), dr = count(ariaLines(d.aria).map(roleOnly));
    out.viewports[vp] = {
      anchors: compareAnchors(p, d),
      fontsLoaded: { proto: p.fontsLoaded, deliv: d.fontsLoaded },
      overflowX: { proto: p.overflowX, deliv: d.overflowX },
      aria: { proto: p.aria, deliv: d.aria, roleCounts: { proto: pr, deliv: dr } },
    };
    out.pixel[vp] = { 'prototype vs livre': await pixelDiff(browser, p.shot, d.shot, `${vp}-proto-vs-deliv`) };
    const p2 = await capture(browser, 'proto', vp, { shotOnly: true, suffix: '-bis' });
    out.pixel[vp]['temoin : prototype vs prototype (meme page, 2 captures)'] = await pixelDiff(browser, p.shot, p2.shot, `${vp}-proto-vs-proto`);
    const p3 = await capture(browser, 'proto', vp, { shotOnly: true, scenario: 'silent' });
    out.pixel[vp]['temoin : prototype vs prototype, autre scenario de donnees'] = await pixelDiff(browser, p.shot, p3.shot, `${vp}-proto-vs-proto-data`);
  }
  await browser.close();
  fs.writeFileSync(path.join(OUT, 'measure.json'), JSON.stringify(out, null, 1));
  for (const vp of Object.keys(out.viewports)) {
    console.log('== ' + vp, JSON.stringify(out.pixel[vp]));
    for (const r of out.viewports[vp].anchors) console.log('  ' + r.anchor.padEnd(26) + r.verdict + (r.deltas && r.deltas.length ? ' : ' + r.deltas.map(x => x.prop).join(', ') : ''));
    const mu = out.mutant[vp];
    console.log('-- temoin mutant ' + vp + ' pixel=' + mu.pixel + '%  aria- ' + JSON.stringify(mu.ariaOnlyInProto) + ' aria+ ' + JSON.stringify(mu.ariaOnlyInMutant));
    for (const r of mu.anchors) if (r.deltas && r.deltas.length) console.log('  ' + r.anchor.padEnd(26) + r.deltas.map(x => `${x.prop}: ${x.proto} -> ${x.deliv}`).join(' | '));
  }
})().catch(e => { console.error(e); process.exit(1); });
