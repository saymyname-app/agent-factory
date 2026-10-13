// PROTOTYPE af-gdt9kt.9 : produit la version gelée (Validated Prototype) de la proposition B, clair et sombre.
// Usage : node freeze.js <chemin du module playwright>
// Lit index.html (page d'exploration), écrit validated/ (pages statiques, sans script) et screenshots-validated/.
const fs = require('fs');
const path = require('path');
const { chromium } = require(process.argv[2] || 'playwright');

const HERE = __dirname;
const OUT = path.join(HERE, 'validated');
const SHOTS = path.join(HERE, 'screenshots-validated');
const FIXED_TIME = '2026-10-13T10:00:00Z';
const PEOPLE = ['Maëlle Garnier', 'Octave Lemaire', 'Inès Bouvier', 'Théo Marchand', 'Capucine Roy', 'Soren Keller', 'Yasmine Haddad', 'Lucien Perrot', 'Agathe Morel', 'Noé Fabre', 'Jade Collin', 'Basile Renaud'];
const STATES = [
  { id: 'accueil', sel: '#accueil .col-narrow .sm', title: 'Accueil', data: { organisation: 'Chorale de Riverside', parcours: { etat: 'Continuer', attribut: 'Prénom', progression: 62, revisions_dues: 3 }, administrateur: true } },
  { id: 'quiz-question', sel: '#quiz .col-narrow .sm', title: 'Entraînement, question', data: { format: 'QCM', question: 'Quel est son prénom ?', choix: ['Maëlle', 'Capucine', 'Agathe', 'Jade'], choisi: 'Agathe', badges: ['Nouveau', 'Facile'] } },
  { id: 'quiz-resultat', sel: '#quiz .col-wide .sm', title: 'Entraînement, résultat', data: { format: 'QCM', question: 'Quel est son prénom ?', choix: ['Maëlle', 'Capucine', 'Agathe', 'Jade'], choisi: 'Capucine', bonne_reponse: 'Capucine', juste: true } },
  { id: 'trombinoscope', sel: '#trombi .col-narrow .sm', title: 'Trombinoscope', data: { total: 48, affiches: PEOPLE, suivis: [0, 2, 4, 7, 10].map(i => PEOPLE[i]), filtres_actifs: 2 } },
  { id: 'admin-membres', sel: '#admin .col-narrow .sm', title: 'Admin, membres et invitations', data: { membres: 12, actifs: 11, invitations_en_cours: 2, lien_de_groupe: { actif: true, role: 'Membre', validite: '7 jours', utilisations: 'Illimité', pin: true }, lignes: [['Maëlle Garnier', 'Admin', 'Actif'], ['Octave Lemaire', 'Membre', 'Actif'], ['Inès Bouvier', 'Contributeur', 'Actif'], ['Théo Marchand', 'Membre', 'Invité'], ['Soren Keller', 'Membre', 'Actif']] } },
];

function frozenCss() {
  const src = fs.readFileSync(path.join(HERE, 'saymyname-design-propositions.html'), 'utf8');
  let css = src.slice(src.indexOf('/* ============ Les trois propositions'), src.indexOf('</style>'));
  css = css.replace(/\/\* ============[^\n]*\n/, '');
  css = css.replace(/\[data-prop="[ac]"\][^{]*\{[^}]*\}\n?/g, '');
  const grab = re => { const m = css.match(re); if (!m) throw new Error('bloc introuvable ' + re); css = css.replace(m[0], ''); return m[1]; };
  const dark = grab(/\[data-prop="b"\]\[data-mode="sombre"\] \.sm\{([^}]*)\}\n?/);
  const darkRules = [];
  css = css.replace(/\[data-prop="b"\]\[data-mode="sombre"\] (\.sm[^{]*\{[^}]*\})\n?/g, (_, r) => { darkRules.push(r); return ''; });
  const light = grab(/\[data-prop="b"\] \.sm\{([^}]*)\}\n?/);
  css = css.replace(/\[data-prop="b"\] /g, '');
  css = css.replace(/\[data-reduced="1"\][^{]*\{[^}]*\}\n?/g, '');
  css = css.replace(/@container screen \(min-width:900px\)/g, '@media (min-width:900px)');
  css = css.replace('.sm{container:screen/inline-size;', '.sm{');
  if (/data-prop|data-mode|@container/.test(css)) throw new Error('reste de variante dans le CSS gelé');
  return '/* Version gelée de la proposition B (af-gdt9kt.9). Tokens sur :root, sombre par le réglage de l\'appareil. */\n'
    + ':root{color-scheme:light dark;' + light + '}\n'
    + '@media (prefers-color-scheme: dark){\n:root{' + dark + '}\n' + darkRules.join('\n') + '\n}\n'
    + '[hidden]{display:none!important}\nbody{margin:0;background:var(--p-bg)}\n.sm{min-height:100vh}\n' + css;
}

(async () => {
  fs.rmSync(OUT, { recursive: true, force: true });
  fs.rmSync(SHOTS, { recursive: true, force: true });
  fs.mkdirSync(path.join(OUT, 'states'), { recursive: true });
  fs.mkdirSync(path.join(OUT, 'data'), { recursive: true });
  fs.mkdirSync(SHOTS, { recursive: true });
  const css = frozenCss();
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
  await page.goto('file://' + path.join(HERE, 'index.html') + '#b');
  await page.waitForTimeout(500);
  for (const s of STATES) {
    const html = await page.evaluate(sel => {
      const el = document.querySelector(sel).cloneNode(true);
      el.querySelectorAll('svg.ic').forEach(svg => {
        const sym = document.querySelector(svg.querySelector('use').getAttribute('href'));
        svg.setAttribute('viewBox', sym.getAttribute('viewBox'));
        svg.innerHTML = sym.innerHTML;
      });
      el.querySelector('main').setAttribute('data-anchor', 'page');
      const toggle = el.querySelector('.menu-toggle');
      if (toggle) toggle.setAttribute('data-anchor', 'ouvrir-menu');
      el.querySelectorAll('[data-noop]').forEach(a => a.removeAttribute('data-noop'));
      el.querySelectorAll('[data-act],[data-n]').forEach(a => { a.removeAttribute('data-act'); a.removeAttribute('data-n'); });
      return el.outerHTML;
    }, s.sel);
    fs.writeFileSync(path.join(OUT, 'states', s.id + '.html'),
      '<!doctype html>\n<html lang="fr">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
      + '<title>SayMyName · ' + s.title + '</title>\n'
      + '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Figtree:wght@400..800&amp;display=swap">\n'
      + '<style>\n' + css + '</style>\n</head>\n<body>\n' + html + '\n</body>\n</html>\n');
    fs.writeFileSync(path.join(OUT, 'data', s.id + '.json'), JSON.stringify(Object.assign({ state: s.id, generated_at: FIXED_TIME, synthetic: true }, s.data), null, 2) + '\n');
  }
  await page.close();
  const manifest = {
    contract: 'agent-factory-validated-prototype/v1',
    variant: 'B',
    encoding: 'utf-8',
    anchor_attribute: 'data-anchor',
    fixed_time_field: 'generated_at',
    viewports: [{ name: 'mobile', width: 390, height: 844 }, { name: 'desktop', width: 1440, height: 900 }],
    themes: ['light', 'dark'],
    states: STATES.map(s => ({ id: s.id, address: 'states/' + s.id + '.html', dataset: 'data/' + s.id + '.json' })),
  };
  fs.writeFileSync(path.join(OUT, 'validated-prototype.json'), JSON.stringify(manifest, null, 2) + '\n');

  const errors = [];
  for (const vp of manifest.viewports) for (const theme of manifest.themes) {
    const p = await browser.newPage({ viewport: { width: vp.width, height: vp.height }, colorScheme: theme });
    p.on('pageerror', e => errors.push(e.message));
    for (const s of STATES) {
      await p.goto('file://' + path.join(OUT, 'states', s.id + '.html'));
      await p.waitForTimeout(400);
      const over = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      if (over > 0) errors.push(s.id + ' ' + vp.name + ' ' + theme + ' déborde de ' + over + ' px');
      await p.screenshot({ path: path.join(SHOTS, s.id + '-' + vp.name + '-' + theme + '.png'), fullPage: true });
    }
    await p.close();
  }
  await browser.close();
  console.log(JSON.stringify({ states: STATES.length, errors }));
})();
