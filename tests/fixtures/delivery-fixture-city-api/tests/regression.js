#!/usr/bin/env node
// Regression command declared by descriptor.json's launch.regression_command.
//
// A `prefactoring` ticket on this fixture project has this run before and
// after its change by bin/tdd-step, and the merge runs it on the merged
// result: every run must exit 0. It characterises what GET /items answers on
// the `content` dataset: its state, its time and its items.
'use strict';

const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const PRODUCT = path.resolve(__dirname, '..');
const EXPECTED = { state: 'content', generated_at: '2026-01-01T00:00:00Z', items: ['alpha', 'beta', 'gamma'] };

const { itemsBody } = require(path.join(PRODUCT, 'server.js'));
const body = itemsBody(JSON.parse(fs.readFileSync(path.join(PRODUCT, 'datasets', 'content.json'), 'utf8')));
let missing = 0;
for (const [field, expected] of Object.entries(EXPECTED)) {
  try {
    assert.deepStrictEqual(body[field], expected);
  } catch {
    missing += 1;
    process.stderr.write(`regression: GET /items no longer answers ${field} = ${JSON.stringify(expected)}\n`);
  }
}
process.exitCode = missing ? 1 : 0;
