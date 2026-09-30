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

## Heartbeat (T18, af-a57xhe)

`lib/cockpit/heartbeat/emitter.py` — `HeartbeatEmitter` pings an external
"Usine muette" check (Healthchecks.io, spec af-oohx2x) every 5 min, but
only once `ReadModel.all_fresh()` says the main sources have read fresh; a
missing secret file or a failing ping becomes a health issue instead of a
crash. It pauses only for `CLEANLY_STOPPED` (Clean stop, requested by
Benjamin — spec "Heartbeat et usine muette": never at a Windows reboot),
via a `state_provider` callable so this module does not depend on the
Clean stop driver (T23) to be tested. `tick()`/`health_issues()` are the
whole public interface; process wiring (secret file location, thread
scheduling, the health zone display) is left to the tickets that build
those.

`tests/cockpit-heartbeat-test.py` drives the emitter directly with a fake
clock and a fake pinger (no HTTP/CLI surface of its own yet), covering:
one ping per 5 min while sources are fresh, no ping while one is not, a
missing secret and a failing ping each showing up in `health_issues()`,
and pausing in no state other than `CLEANLY_STOPPED`.

## Clean stop / restart (T23, af-s5e3yo)

`lib/cockpit/stop/driver.py` — `StopDriver`: Clean stop by suspending the
city (`gc.suspend()`, the PATCH `suspended=true`) and restart by `gc
resume()`, rien d'autre — never `gc stop` / `gc stop --force` (those stay
at the runbook). Seven states: `en_marche`, `arret_en_cours`,
`arretee_proprement` (`CLEANLY_STOPPED`, imported from
`cockpit.heartbeat.emitter` so the T18 pause condition and this driver
can never drift apart), `redemarrage`, `reprise_verifiee`,
`reprise_avec_ecarts`, `arret_force`, `arret_interrompu`. A "photo"
(`snapshot_fn`) is taken at `request_stop()` and compared against a fresh
read once the city is suspended with no live session (`bilan()` — empty
is "0 perte") and again after `resume()` (`reprise_verifiee` vs.
`reprise_avec_ecarts` if any bead comes back under a different assignee).
30 min without progress (no session event, no closed step) surfaces a
pending "l'arrêt n'avance plus" request (`lib/cockpit/stop/requests.py`)
offering a forced stop — never an automatic switch. State persists
through the same `state_store` seam as the T17 notify engine
(`cockpit.notify.state_store`), so a cockpit restart mid-stop resumes the
same state; if that restart's first tick finds the city still not
suspended, nothing could have kept the stop moving while the cockpit was
down, so the driver reports `arret_interrompu` instead of silently
continuing as if nothing happened.

`lib/cockpit/ui/stop/render.py` renders the zone with the stop button
`hidden` — the spec keeps it hidden until the three prior factory
corrections are delivered and a real trial succeeds, so nothing here
should be read as "ready to show" (a later ticket removes `hidden`).

`tests/cockpit-stop-test.py` drives `StopDriver` directly against
`tests/fixtures/cockpit/stop/fake_gc_city.py` (a fake exposing only
`status`/`suspend`/`resume`/`force_stop_sessions`, whose `stop`/
`stop_force` raise if ever called), covering: the full En marche → Arrêt
en cours → Arrêtée proprement sequence with a 0-perte bilan and state
surviving a simulated cockpit restart; the no-progress request after 30
min with no automatic forced stop, and a forced stop that keeps the bead
assigned; "usine arrêtée par toi" instead of a false alarm, the heartbeat
pausing only once `arretee_proprement` is reached, and a simulated PC
reboot mid-stop giving `arret_interrompu` with écarts; that the driver
never calls `stop`/`stop_force` and only ever touches the city; and both
resume outcomes (`reprise_verifiee` / `reprise_avec_ecarts`). Process
wiring (poller thread, the button's hidden condition, the "Ce qui
t'attend" feed) is left to a later ticket, same precedent as T17/T18.
