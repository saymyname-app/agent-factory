# Cockpit V2 — read model and freshness (T11, af-0b6ffa)

The Cockpit is a pure-code process, separate from `gc`, that runs in WSL
and listens on `127.0.0.1` only (Spec af-oohx2x, "Accès et sécurité"). This
ticket builds its core read-model seam: the process itself, the Freshness
model, and the startup wiring. The screens built on this base (Accueil,
"Ce qui t'attend", page projet, …) are other C01 tickets.

See GLOSSARY.md for the canonical definitions of **Cockpit**, **Freshness**,
and **Validity window**.

## Layout

- `lib/cockpit/core/` — the read model and process, framework-agnostic:
  - `clock.py` — `SystemClock`; every other module takes a clock object
    instead of calling `time.time()` directly.
  - `freshness.py` — `classify()`: fresh / stale / unknown given a read
    time, now, a source's Validity window, and whether the last read was
    complete (a gc status read while its event stream is silent never counts as
    complete).
  - `readmodel.py` — `ReadModel`: the one held-up-to-date copy. The page
    only ever reads this, never a source directly.
  - `gc_client.py` — subscribes to the gc supervisor's SSE stream
    (`127.0.0.1:8372/v0/city/<city>/events/stream`); reconnects with backoff, never crashes the
    process.
  - `beads_source.py`, `polling_source.py` — Beads (and future GitHub/
    rituals) sources, each read on its own rhythm.
  - `server.py` — the HTTP process itself; refuses to bind anywhere but
    `127.0.0.1`.
  - `process.py`, `config.py` — wires it all together; config from env vars.
- `lib/cockpit/ui/base/` — the variant D stylesheet and page skeleton
  every screen builds on (see "Home screen" below).
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
that was never read (GLOSSARY.md Freshness: "never read, or its source is
failing") — this is the fresh → stale → unknown progression a single
source goes through as it stops responding.

Only `gc` and `beads` are wired up by this ticket; `github` and `rituals`
are declared in `freshness.VALIDITY_WINDOWS_SECONDS` for the tickets that
build their producers.

## Testing

`tests/cockpit-core-test.py` is the seam: it starts the real `bin/cockpit`
process against a fake gc (`tests/fixtures/cockpit/core/fake_gc.py` — HTTP
`/v0/cities`, `/v0/city/<city>/status`, `.../beads/ready`, SSE
`.../events/stream`) and a fake `bd`
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

## gc source, as the real supervisor answers (af-mjfvwx)

The cockpit first subscribed to `/events`, which on the real supervisor is
the HTML dashboard: the `gc` source was never read, the headline could
never say "Tout est à jour", and the reconnect loop left one
`supervisor.request` event per second in gc's event log. The test fake
answered an API the real gc does not have, so the tests were green.

`lib/cockpit/core/gc_client.py` now reads what gc 1.4.1 serves:

| Read | Endpoint | Gives |
|---|---|---|
| city name | `/v0/cities` (or `COCKPIT_GC_CITY`) | which city to read |
| liveness, progress | `/v0/city/<city>/events/stream` (SSE, heartbeat ~15 s) | stream alive; `last_progress_at` on `bead.closed` / `session.*` |
| values | `/v0/city/<city>/status`, every `COCKPIT_GC_STATUS_POLL_SECONDS` (30) and after a session/city event | `suspended`, `agents_running`, `work`, `partial_errors` |
| delivery work ready | `/v0/city/<city>/beads/ready` | `delivery_ready`: a ready bead with `gc.plane=delivery` |

A read is complete only while the stream was heard within
`COCKPIT_GC_STREAM_SILENCE_SECONDS` (45). A `partial: true` status keeps the
fields it delivered and adds the health line « L'usine répond, mais une
partie de son état est illisible. » (agent interpretation of spec .14, not
a decision of Benjamin's: before, any partial read made the whole source
unknown).

`tests/fixtures/cockpit/core/fake_gc.py` answers like the real one (HTML on
`/events` and `/status` included). `tests/cockpit-fake-gc-contract-test.py`
(local-only) compares the fake with the installed supervisor, endpoint by
endpoint; run it before changing either side.

## Home screen, as the validated prototype shows it (af-mjfvwx)

The first delivery carried only the prototype's 12 colour tokens: the page
served was an unstyled bullet list with every request unfolded.
`GET /` is now variant D of `origin/prototype/c01-home-screen`
(`prototypes/c01-home-screen/index.html`, `renderD`):

- `ui/base/tokens.py` — the prototype's stylesheet (tokens, shared
  components, variant D layout) with the prototype's own class names, and
  the `<link>` that loads Atkinson Hyperlegible Next / Mono.
- `ui/base/page.py` `render_home` — brand, then one status line: the
  factory's state (`ui/health/page.py` `render_status_line`: « En marche ·
  N agents au travail · … », « Suspendue », or « État de l'usine inconnu »
  when the supervisor was not read) and the freshness headline with
  « Revérifier ».
- `ui/home/page.py` — « Ce qui t'attend » as a short list plus one detail
  per request. On a PC the selected detail sits beside the list; under
  900 px the detail replaces the list and « Retour à la liste » brings it
  back. The selection lives in the URL fragment (`#d-<id>`).
- In the detail: each prepared option of a NEEDS BENJAMIN is the two-step
  answer button (`repondre`); a proposal gets « Accepter » and « Refuser »
  with a reason. These controls were handled by the server and the page
  script since T14 but rendered nowhere.
- `ui/health/page.py` `render_health_zone` — « Santé de l'usine » under
  the inbox.

Sources are named in the operator's words: « superviseur », « tickets »,
« version de l'usine ». A stale headline reads « 2 sources pas à jour :
tickets (inconnu), superviseur (périmé) ».

Known gaps against the prototype, for later slices of af-mjfvwx: the
« Projets » zone, the theme switch (the page follows the system theme).
« Reporter » opens a menu in place of the action row, as in the
prototype: 1 h, 4 h, demain 09:00, or a free date and time (sent as
`custom_epoch`; the earlier select offered « heure libre » without any
way to give the hour, so the server refused it).

`tests/cockpit-requests-test.py` (`test_home_is_the_variant_d_inbox`,
`test_status_line_never_guesses_the_factory_state`) checks the page
through the process's HTTP surface. Fidelity itself is judged by Benjamin
on captures (PC 1440 px and iPhone 390 px, light and dark) taken from the
real process on the real sources, next to the prototype's.

## « Projets » on the home screen (af-mjfvwx)

T19/T20 built `lib/cockpit/projects/**` and `ui/projects/page.py` and tested
their pure functions; no process imported them. They now have a running
caller:

- `projects/source.py` `read_projects` is the read model's `projets`
  source (every `COCKPIT_PROJECTS_POLL_SECONDS`, 30 s; Validity window
  5 min, like Beads): descriptors from `COCKPIT_DESCRIPTORS_DIR`
  (`config/project-descriptors/`), non-closed beads, every bead carrying
  `gc.graph_digest`, and the children of each open map. A failed `bd` call
  fails the whole read: the zone then says « Inconnu : projets illisibles »,
  never an empty list.
- `GET /` shows the zone under the inbox (`ui/projects/page.py`, the
  prototype's markup); `GET /api/projects` is its JSON twin.
- « Problème remonté » and « À toi de jouer » are one click from where
  Benjamin acts: the request carrying the question, or — on a Livré
  chantier — its acceptance panel in place, with « Accepter »
  (`POST /api/actions/accepter_chantier`, two-step, traced on the convoy)
  and « Pas bon → agent » (`pas_bon_vers_agent`, a prompt to copy).

Two rules the real data needed:

- A convoy bead without `gc.graph_digest` is gc's own "input convoy", not
  a chantier.
- A convoy without `gc.project_id` is placed under the project declaring
  the rig its tickets are dispatched to (`gc.dispatch_rig`; spec « Données
  de projet » : « projet déduit du rig »). With neither, it is listed under
  « Sans projet ».

Not wired yet (later slices of af-mjfvwx): the roadmap step and « dev a N
commits d'avance » (they need the cockpit's own clones; until then an
accepted chantier is treated as finished for every project), and
Livré-non-Accepté as a « Quand tu veux » request (`projects/demandes.py`).

`tests/cockpit-home-projects-test.py` drives all of the above through the
process's HTTP surface.

## Project page (af-mjfvwx)

`GET /projet/<project_id>` serves `ui/projects/project_page.py` (T22, until
now imported only by its test), in the markup of
`origin/prototype/c01-project-page`. Benjamin's choice (af-1al0t1,
2026-09-30): a selector between « Tableau » (variante 1, one column per
stage) and « Bande » (variante 3, one list, a stepper per chantier). Both
are in the page; the selector flips which one shows and the device
remembers it. Agent choices, reversible: Tableau first, Bande first under
900 px.

- Top bar: « ← Accueil », the project's name, the freshness headline with
  « Revérifier » (which returns to this page). Then « N chantiers actifs ·
  N à toi de jouer · … · Historique du projet → ».
- A project with no promotion branch has no Promu column and no Promu step
  (spec .41).
- Chips lead to the home screen: `/#d-<id>` opens the request, `/#acc-<id>`
  opens the acceptance panel of a Livré chantier.
- « Travail hors chantier » (`projects/hors_chantier.py`) and
  « Historique » (terminé, abandonné) come from the same `projets` read
  (`projects/source.py` `project_page_data`).
- An id no descriptor declares is a 404 saying « Projet inconnu ». An
  unreadable `projets` source says « Inconnu : projets illisibles ».

Known gap against the prototype: a chantier's age (« depuis 3 j ») is not
shown — no bead field dates the entry into a stage.

`ui/base/page.py` `render_document` is the skeleton both pages share
(stylesheet, font, « Déconnecté » banner, scripts).
`tests/cockpit-home-projects-test.py` covers the page through HTTP.

## Every kind of request in « Ce qui t'attend » (af-mjfvwx)

`requests/assemble.py` `assemble_requests` is the one list the page and
`GET /api/requests` share. Besides NEEDS BENJAMIN and proposals
(`requests/builder.py`) it now calls what T15 and T20 built and nothing
served:

| Kind | Level | From | In its detail |
|---|---|---|---|
| Spec to approve, ticket graph to approve (`requests/sources/specs_and_graphs.py`) | À faire | Beads | a prompt to copy — never an approve control (spec .37) |
| Ready HITL card ticket (`requests/sources/hitl.py`) | Quand tu veux | Beads | read-only option |
| Delivered chantier not accepted, accepted not promoted (`projects/demandes.py`) | Quand tu veux | `projets` | « Accepter » (two-step) and « Pas bon → agent » as the options themselves |
| Source unreadable for more than 15 min (`requests/sources/readability.py`, `COCKPIT_ILLISIBLE_SECONDS`) | À faire | the read model's own read times | « Revérifier maintenant » |

- One request per source object: a Spec carrying a NEEDS BENJAMIN is that
  question, not a second row.
- Reporter hides a Spec / graph / HITL request through the same trace as
  an escalation. It is not offered on a chantier or a source request,
  where no trace on a bead could hide anything.
- A request shows its project's displayed name (« Usine »), not its key.
- With Beads unknown the list still shows what does not come from Beads
  (the unreadable-source request among them) under the « Inconnu :
  illisible » notice, and `/api/requests` says `state: "unknown"`.

Not wired yet: « rituel dû » (each project's status command lives in its
own repository — the slice that gives the cockpit its clones),
and `requests/sources/unknown_signal.py` (no source hands the cockpit an
unrecognised signal today).

`tests/cockpit-other-requests-test.py` covers all of the above through the
process's HTTP surface.

## Journal of resolved requests (af-mjfvwx)

`GET /journal` (linked under « Ce qui t'attend ») and `GET /api/journal`
serve `ui/journal/` (T15, until now imported only by its test). Each entry
says what was asked, how it was resolved, when (Paris time), by whom, and
by which way (spec .18); a bead resolved twice has two entries (spec .19).
The cockpit keeps no copy: `requests/journal.py` `read_journal` is the
read model's `journal` source (every `COCKPIT_JOURNAL_POLL_SECONDS`, 60 s)
and re-reads the traces.

What the tracker really holds, checked 2026-10-06 — T15 had assumed Beads
comments, which are empty on a bead Benjamin answered:

| Trace | Written by | In the bead's notes | Dated by |
|---|---|---|---|
| answer to a NEEDS BENJAMIN | `bin/escalation-door repondre` | `RÉPONSE: <lettre> — <option>` | `gc.escalation_response_at` (latest answer only) |
| decision cleared without an answer | `bin/escalation-door clear` | `DECISION CLEARED: …` | `gc.escalation_cleared_at` (latest clearance; absent before 2026-10-06) |
| proposal accepted / rejected | `bin/proposal-door` | `PROPOSITION ACCEPTÉE par …` / `PROPOSITION REJETÉE par … — <raison>` | `gc.proposal_response_at` |
| relance, chantier accepté | `cockpit.actions.trace` | `Cockpit: <quoi> sur <cible> (…) — <quand>, par <acteur>` | the note itself |

The question an entry answers is the `NEEDS BENJAMIN: …` / `PROPOSITION: …`
note before it. An entry no trace dates shows « date inconnue » and comes
after the dated ones.

Intent (Benjamin, his words, 2026-10-06): « affiche tel quel ». Mechanism
(agent interpretation): the journal shows each text exactly as its
producer wrote it, without the main-text control (`text/validate.py`) the
inbox applies — a record of what happened, where that control hid nearly
every entry written before it existed. It does not loosen the inbox.

Known gap: an answer older than the bead's latest one, and a clearance
made before the door dated it, carry no date.

`tests/cockpit-journal-test.py` covers the page through HTTP, with beads
carrying notes and metadata as the doors leave them.
