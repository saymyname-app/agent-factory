// PROTOTYPE af-gdt9kt.9 : captures de contrôle. Usage : node shots.js <chemin du module playwright>
const path = require('path');
const { chromium } = require(process.argv[2] || 'playwright');
(async () => {
  const browser = await chromium.launch();
  const out = path.join(__dirname, 'screenshots');
  const url = 'file://' + path.join(__dirname, 'index.html');
  const errors = [];
  for (const [name, width] of [['page-1600', 1600], ['page-390', 390]]) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    page.on('console', m => { if (m.type() === 'error') errors.push(name + ': ' + m.text()); });
    page.on('pageerror', e => errors.push(name + ': ' + e.message));
    for (const p of ['a', 'b', 'c']) {
      await page.goto(url + '#' + p);
      await page.reload();
      await page.waitForTimeout(700);
      await page.screenshot({ path: path.join(out, p + '-' + name + '.png'), fullPage: true });
      const report = await page.evaluate(() => ({
        overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        ratios: [...document.querySelectorAll('.fiche:not([hidden]) .ratios span')].map(s => s.textContent),
        clipped: [...document.querySelectorAll('.sm *')].filter(e => e.children.length === 0 && e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).textOverflow !== 'ellipsis' && e.clientWidth > 0).slice(0, 8).map(e => e.className + ' | ' + e.textContent.slice(0, 40)),
      }));
      console.log(JSON.stringify({ prop: p, view: name, ...report }));
    }
    await page.close();
  }
  console.log(JSON.stringify({ errors }));
  await browser.close();
})();
