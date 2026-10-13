import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';

const config = JSON.parse(fs.readFileSync('design-bench/bench.config.json', 'utf8'));
const widths = [390, 1440];
const themes = ['light', 'dark'];
async function assertTheme(page, theme) {
  await expect.poll(() => page.evaluate(() => getComputedStyle(document.documentElement).colorScheme)).toBe(theme);
  const roles = await page.evaluate(value => {
    const root = document.documentElement;
    const read = () => {
      const style = getComputedStyle(root);
      return [style.getPropertyValue('--color-background').trim(), style.getPropertyValue('--color-text').trim()];
    };
    const selected = read();
    root.dataset.theme = value === 'dark' ? 'light' : 'dark';
    const opposite = read();
    root.dataset.theme = value;
    return { selected, opposite };
  }, theme);
  for (let index = 0; index < 2; index++) {
    expect(roles.selected[index], 'rôle de thème absent').not.toBe('');
    expect(roles.selected[index], 'rôle clair/sombre identique').not.toBe(roles.opposite[index]);
  }
}

for (const screen of config.screens) {
  for (const width of widths) {
    for (const theme of themes) {
      test(`${screen.id} ${width}px ${theme}`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.addInitScript(value => {
          const applyTheme = () => { if (document.documentElement) document.documentElement.dataset.theme = value; };
          applyTheme();
          new MutationObserver(applyTheme).observe(document, { childList: true });
          window.__designMotionViolations = [];
          const original = Element.prototype.animate;
          Element.prototype.animate = function (frames, options) {
            const duration = typeof options === 'number' ? options : options?.duration;
            if (matchMedia('(prefers-reduced-motion: reduce)').matches &&
                (duration === 'auto' || Number(duration) > 0)) window.__designMotionViolations.push(this.tagName.toLowerCase());
            return original.call(this, frames, options);
          };
        }, theme);
        await page.goto(screen.path);
        await page.locator(screen.readySelector).waitFor({ state: 'visible' });
        await assertTheme(page, theme);
        await page.evaluate(() => document.fonts.ready);
        const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze();
        expect(audit.violations.map(v => `${v.id}: ${v.nodes.map(n => n.target.join(' ')).join(', ')}`)).toEqual([]);
        await expect(page).toHaveScreenshot(`${screen.id}-${width}-${theme}.png`, { fullPage: true, animations: 'disabled' });
        await page.emulateMedia({ reducedMotion: 'reduce' });
        await page.reload();
        await page.locator(screen.readySelector).waitFor({ state: 'visible' });
        await assertTheme(page, theme);
        const moving = await page.evaluate(() => [...document.querySelectorAll('*')].filter(element => {
          const style = getComputedStyle(element);
          const durations = `${style.animationDuration},${style.transitionDuration}`.split(',');
          return durations.some(value => parseFloat(value) > 0);
        }).slice(0, 5).map(element => element.tagName.toLowerCase())
          .concat(window.__designMotionViolations)
          .concat(document.getAnimations({ subtree: true }).filter(animation =>
            animation.playState === 'running' && animation.effect?.getComputedTiming().duration > 0)
            .map(() => 'web-animation')));
        expect(moving, 'mouvement actif avec préférence réduire').toEqual([]);
        await page.goto(`${screen.path}${screen.path.includes('?') ? '&' : '?'}lang=zz`);
        await page.locator(screen.readySelector).waitFor({ state: 'visible' });
        await assertTheme(page, theme);
        const untranslated = await page.evaluate(() => {
          const selector = 'script,style,[data-user-content]';
          const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
          const values = [];
          while (walker.nextNode()) {
            const node = walker.currentNode;
            if (node.parentElement?.closest(selector)) continue;
            const value = node.textContent.trim();
            if (value && !/^\[zz:[^\]]+\]$/.test(value)) values.push(value);
          }
          for (const element of document.querySelectorAll('[alt],[title],[placeholder],[aria-label],[aria-description],[aria-valuetext],[label],input[value]')) {
            if (element.closest('[data-user-content]')) continue;
            for (const name of ['alt', 'title', 'placeholder', 'aria-label', 'aria-description', 'aria-valuetext', 'label', 'value']) {
              if (name === 'value' && !(element instanceof HTMLInputElement && ['button', 'submit', 'reset'].includes(element.type))) continue;
              const value = element.getAttribute(name);
              if (value && !/^\[zz:[^\]]+\]$/.test(value)) values.push(value);
            }
          }
          return values.slice(0, 10);
        });
        expect(untranslated, 'texte produit non traduit en fausse langue').toEqual([]);
      });
    }
  }
}
