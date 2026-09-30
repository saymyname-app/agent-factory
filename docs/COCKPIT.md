# Cockpit V2 — read model and freshness (T11, af-0b6ffa)

The Cockpit is a pure-code process, separate from `gc`, that runs in WSL
and listens on `127.0.0.1` only (Spec af-oohx2x, "Accès et sécurité"). This
ticket builds its core read-model seam: the process itself, the Freshness
model, and the startup wiring. The screens built on this base (Accueil,
"Ce qui t'attend", page projet, …) are other C01 tickets.

See CONTEXT.md for the canonical definitions of **Cockpit**, **Freshness**,
and **Validity window**.

## Layout

- `lib/cockpit/core/` — the read model and process, framework-agnostic:
  - `clock.py` — `SystemClock`; every other module takes a clock object
    instead of calling `time.time()` directly.
  - `freshness.py` — `classify()`: fresh / stale / unknown given a read
    time, now, a source's Validity window, and whether the last read was
    complete (a gc `partial: true` response never counts as complete).
  - `readmodel.py` — `ReadModel`: the one held-up-to-date copy. The page
    only ever reads this, never a source directly.
  - `gc_client.py` — subscribes to the gc supervisor's SSE stream
    (`127.0.0.1:8372/events`); reconnects with backoff, never crashes the
    process.
  - `beads_source.py`, `polling_source.py` — Beads (and future GitHub/
    rituals) sources, each read on its own rhythm.
  - `server.py` — the HTTP process itself; refuses to bind anywhere but
    `127.0.0.1`.
  - `process.py`, `config.py` — wires it all together; config from env vars.
- `lib/cockpit/ui/base/` — the variant D visual base (tokens + the
  freshness-headline page) every later screen builds on.
- `bin/cockpit` — the CLI: `run` (foreground), `start`/`stop`/`status`
  (background, pidfile-tracked, idempotent — `start` is a no-op if already
  running).
- `bin/factory-boot` — starts the cockpit if it is not already running,
  ahead of the suspended-city early exit, so it keeps reading and showing
  status through a suspended or stopped city.

## Validity windows (spec .3)

| Source  | Validity window |
|---------|------------------|
| gc (SSE)| 2 min |
| Beads   | 5 min |
| GitHub  | 10 min |
| rituals | 1 h |

A source unread for longer than its Validity window plus another full
window is considered **failing** and reported `unknown`, same as a source
that was never read (CONTEXT.md Freshness: "never read, or its source is
failing") — this is the fresh → stale → unknown progression a single
source goes through as it stops responding.

Only `gc` and `beads` are wired up by this ticket; `github` and `rituals`
are declared in `freshness.VALIDITY_WINDOWS_SECONDS` for the tickets that
build their producers.

## Testing

`tests/cockpit-core-test.py` is the seam: it starts the real `bin/cockpit`
process against a fake gc (`tests/fixtures/cockpit/core/fake_gc.py` — HTTP
`/status` + SSE `/events`) and a fake `bd`
(`tests/fixtures/cockpit/core/fake-bd`), then drives it over plain HTTP —
never an internal function. It covers: serving what the page receives,
the fresh → stale → unknown progression over real elapsed time (Validity
windows are shrinkable via `COCKPIT_VALIDITY_<SOURCE>_SECONDS` env vars so
the test doesn't wait real minutes), the "Tout est à jour" / "Périmé ou
inconnu" headline, refusing to bind off `127.0.0.1`, surviving a simulated
city stop, and `bin/factory-boot`'s idempotent cockpit launch.
