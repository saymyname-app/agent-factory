#!/usr/bin/env node
// Second synthetic launchable product of the Delivery Fixture City (T35,
// af-f62cxt): another language than the first one (tests/fixtures/
// delivery-fixture-city/app.py) and no web page -- a JSON API served with the
// Node.js standard library only, so the same launcher (bin/project-launch)
// starts, health-probes and stops it from its profile alone:
//
//   GET /health  -> {"status": "ok"}
//   GET /items   -> the named synthetic dataset given with --dataset: its
//                   state, its fixed "generated_at" time and its items, so two
//                   launches on the same dataset answer byte-identical bodies.
'use strict';

const fs = require('node:fs');
const http = require('node:http');

function itemsBody(dataset) {
  return {
    state: String(dataset.state ?? ''),
    generated_at: String(dataset.generated_at ?? ''),
    items: Array.isArray(dataset.items) ? dataset.items.map(String) : [],
  };
}

function respond(response, status, body) {
  const payload = Buffer.from(JSON.stringify(body), 'utf8');
  response.writeHead(status, { 'Content-Type': 'application/json', 'Content-Length': payload.length });
  response.end(payload);
}

function handler(dataset) {
  return (request, response) => {
    const path = request.url.split('?', 1)[0];
    if (request.method === 'GET' && path === '/health') {
      respond(response, 200, { status: 'ok' });
    } else if (request.method === 'GET' && path === '/items') {
      respond(response, 200, itemsBody(dataset));
    } else {
      respond(response, 404, { status: 'not-found' });
    }
  };
}

function option(argv, name) {
  const index = argv.indexOf(name);
  if (index < 0 || index + 1 >= argv.length) {
    process.stderr.write(`usage: server.js --port PORT --dataset FILE (missing ${name})\n`);
    process.exit(2);
  }
  return argv[index + 1];
}

function main(argv) {
  const port = Number(option(argv, '--port'));
  const dataset = JSON.parse(fs.readFileSync(option(argv, '--dataset'), 'utf8'));
  http.createServer(handler(dataset)).listen(port, '127.0.0.1');
}

module.exports = { itemsBody };

if (require.main === module) {
  main(process.argv.slice(2));
}
