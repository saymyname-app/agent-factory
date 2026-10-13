import { defineConfig } from '@playwright/test';
import fs from 'node:fs';

const config = JSON.parse(fs.readFileSync('design-bench/bench.config.json', 'utf8'));
if (!Array.isArray(config.screens) || !config.screens.length) {
  throw new Error('design: aucun écran de référence configuré');
}
for (const screen of config.screens) {
  if (!/^[a-z0-9-]+$/.test(screen.id) || !screen.path?.startsWith('/') ||
      typeof screen.readySelector !== 'string' || !screen.readySelector.trim()) {
    throw new Error('design: écran de référence invalide');
  }
}
export default defineConfig({
  testDir: '.',
  testMatch: 'bench.spec.mjs',
  workers: 1,
  retries: 0,
  reporter: 'list',
  use: { browserName: 'chromium', baseURL: config.baseURL },
  webServer: {
    command: process.env.DESIGN_PREVIEW_COMMAND || 'npm run preview -- --host 127.0.0.1 --port 4173',
    cwd: '..',
    url: config.baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 60000
  }
});
