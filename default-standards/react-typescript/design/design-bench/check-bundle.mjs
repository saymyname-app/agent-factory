#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const config = JSON.parse(fs.readFileSync('design-bench/bench.config.json', 'utf8'));
const { directory, maxBytes } = config.bundle ?? {};
if (!Number.isInteger(maxBytes) || maxBytes <= 0) {
  console.error('design: budget du bundle non configuré');
  process.exit(1);
}
if (!directory || path.isAbsolute(directory) || directory.split(/[\\/]/).includes('..')) {
  console.error('design: chemin du bundle invalide');
  process.exit(1);
}
function assets(dir) {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
    const file = path.join(dir, entry.name);
    return entry.isDirectory() ? assets(file) : /\.(js|css)$/.test(file) ? [file] : [];
  });
}
const files = assets(directory);
if (!files.length) {
  console.error('design: aucun asset JS/CSS construit pour le budget');
  process.exit(1);
}
const bytes = files.reduce((sum, file) => sum + fs.statSync(file).size, 0);
if (bytes > maxBytes) {
  console.error(`design: budget bundle dépassé : ${bytes} > ${maxBytes} octets`);
  process.exit(1);
}
console.log(`design: bundle ${bytes}/${maxBytes} octets`);
