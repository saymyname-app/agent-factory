#!/usr/bin/env node
// Test command of the second project of the Delivery Fixture City
// (descriptor.json, launch.test_command; T35, af-f62cxt).
//
//     harness.js TEST REPORT
//
// Runs one criterion test and writes a JUnit XML report of it, one `testcase`
// per test, where an assertion failure (`failure`) is distinct from any other
// exception (`error`, with its type): what bin/tdd-step reads. TEST is a test
// file, optionally followed by `::name`. A test file is a CommonJS module
// that exports its tests by name, each a function (it may be async) that
// throws when the test fails. The criterion tests reach the launched product
// at the address given in PRODUCT_ADDRESS.
//
// Frozen harness path: a change to this file after the freeze of a ticket's
// criterion tests is refused by the green step without an amendment.
'use strict';

const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

function escape(text) {
  return String(text).replace(/[<>&"]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c]));
}

function testcase(name, verdict) {
  const open = `<testcase classname="" name="${escape(name)}"`;
  if (!verdict) return `${open}/>`;
  const type = verdict.tag === 'error' ? ` type="${escape(verdict.type)}"` : '';
  return `${open}><${verdict.tag}${type} message="${escape(verdict.message)}"/></testcase>`;
}

function verdictOf(error) {
  const message = error && error.message !== undefined ? error.message : error;
  if (error instanceof assert.AssertionError) return { tag: 'failure', message };
  return { tag: 'error', type: (error && error.name) || 'Error', message };
}

async function main(argv) {
  if (argv.length !== 2) {
    process.stderr.write('usage: harness.js TEST REPORT\n');
    return 2;
  }
  const [testId, report] = argv;
  const separator = testId.indexOf('::');
  const file = separator < 0 ? testId : testId.slice(0, separator);
  const selector = separator < 0 ? '' : testId.slice(separator + 2);
  const cases = [];
  let green = true;
  try {
    const tests = require(path.resolve(file));
    const names = selector ? [selector] : Object.keys(tests);
    for (const name of names) {
      if (typeof tests[name] !== 'function') throw new ReferenceError(`no test named ${name} in ${file}`);
      try {
        await tests[name]();
        cases.push(testcase(name));
      } catch (error) {
        green = false;
        cases.push(testcase(name, verdictOf(error)));
      }
    }
  } catch (error) { // the test file itself cannot be loaded
    green = false;
    cases.push(testcase(selector || file, { ...verdictOf(error), tag: 'error', type: (error && error.name) || 'Error' }));
  }
  fs.writeFileSync(report, `<?xml version="1.0" encoding="utf-8"?>\n<testsuite name="${escape(testId)}" tests="${cases.length}">`
    + `${cases.join('')}</testsuite>\n`);
  return green && cases.length > 0 ? 0 : 1;
}

main(process.argv.slice(2)).then((code) => { process.exitCode = code; });
