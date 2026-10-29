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
- `bin/cockpit` — the CLI: `run` (foreground), `start`/`stop`/`restart`/
  `status` (background, pidfile-tracked, idempotent — `start` is a no-op if
  already running). To load new code, `bin/cockpit restart`: see "Process
  lifecycle" below.
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

## Process lifecycle: start, stop, restart (2026-10-08)

**To restart the Cockpit, run `bin/cockpit restart`** — never `stop` then
`start` by hand. On the live host, tell Benjamin first: the page he has
open answers nothing for about a second.

What each command guarantees, whatever the exit code of the one before:

| Command | Exit 0 means | Otherwise |
|---|---|---|
| `start` | the process it just launched is listening (`started (pid N)`), or one was already running | non-zero, no pid file, the new process killed if it was still there; stderr gives the last line the process wrote (`OSError: [Errno 98] Address already in use`) and the log path |
| `stop` | no cockpit process is left and the port is free | non-zero only if the process survived SIGKILL; the pid file is then kept, because it is still true |
| `restart` | `stop` then `start` both succeeded | `stop`'s failure, without starting; or `start`'s |
| `status` | the pid file names a live `cockpit run` | 1 |

- **When SIGTERM is not enough.** `stop` waits `COCKPIT_STOP_WAIT_SECONDS`
  (15 s), then sends SIGUSR1 — the process writes every thread's stack to
  `cockpit.log` — and SIGKILL, and says so on stderr (`stopped (killed)`).
  Killing is safe: the cockpit's state files are written whole and renamed,
  and what it reads lives elsewhere. A cockpit left alive would keep the
  port and make the next start fail.
- **"Started" is the new process's own word.** `start` hands `run` a pipe;
  `run` writes to it once its socket listens. Something answering on the
  port proves nothing — it can be the previous process.
- **A pid is not the cockpit.** The pid file outlives a WSL restart, after
  which its number can belong to anything. `status`, `stop` and `start`
  read `/proc/<pid>/cmdline` and only treat a `…/bin/cockpit run` as the
  cockpit; anything else is a stale file, removed, never signalled.
- **A stopping process frees the port first**, then asks every source
  reader to end, then waits for all of them together for at most 5 s
  (`process.shut_down`, `SHUTDOWN_BUDGET_SECONDS`). A reader still busy
  then ends with the process and is named in the log.
- `cockpit.log` now dates each life of the process: `pid N listening since
  …`, `stopping at …`, `stopped in 0.4s` (`… without waiting for: beads`
  when a reader was cut).

Why (2026-10-08, 01:24 Paris): `stop` gave up after 10 s, removed the pid
file and left the process holding the port; `start` then connected to that
old process, printed `started`, and its own child died on `Address already
in use`. The stop was slow because of one call: closing the supervisor's
event stream from another thread waits for the read in progress, that is
for gc's next frame — its heartbeat, every 15 s on a quiet city. Measured
on the live sources: 2 s to 12.5 s per stop before, 0.3 s to 1.3 s after
(`gc_client._end_read` shuts the connection down instead). By day the
stream is busy and the same stop passed.

`tests/cockpit-core-test.py` (`CockpitCliLifecycleTest`) holds this through
the CLI: a supervisor silent for 30 s, a restart on the same port, a start
while an orphan holds the port, a process deaf to SIGTERM, a pid file
naming another process.

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

Every partial error shows the line. From 2026-10-08 to 2026-10-11 an error
on `store health:` (gc's own measure of its store on disk) was left out,
because gc 1.4.1 failed that measure on every read (af-jew53p); gc 1.5.0
counts without loading the beads, the measure answers, and the exception was
removed with the upgrade (af-w82f07).

`tests/fixtures/cockpit/core/fake_gc.py` answers like the real one (HTML on
`/events` and `/status` included). `tests/cockpit-fake-gc-contract-test.py`
(local-only) compares the fake with the installed supervisor, endpoint by
endpoint; run it before changing either side.

## « Vue d’ensemble »: the home of B/Panorama (T02, af-0gonc9)

`GET /` is the destination « Vue d’ensemble » of the Validated Prototype
B/Panorama (`prototype/cockpit-b-zones-20261012` at 632deea,
`prototypes/c01-complete/frozen-panorama-home`; Spec af-2zseit), drawn from
the read model, never from the frozen page:

- `ui/panorama/shell.py` — the shell every page of the cockpit is now
  served in: the navigation B (Vue d’ensemble, Projets, Runs, Journal,
  Usine, Rituels, Analyses) beside the page on a PC, above it under 800 px,
  light or dark as the browser prefers. The destination open is a button
  marked `aria-current="page"`, every other one a button that opens its
  address (a form of its own sent by GET: Enter or a click, no script);
  « Vue d’ensemble » carries how many requests wait. Its parts carry the
  anchors of the reference (`data-anchor`), the generic ones too
  (`div-1`, `strong-1`, `button-3`), numbered by `Anchors` as the frozen
  pages number them -- the shell's first, then those of the destination,
  which `render_shell` draws with the same numbering -- so each Prototype
  Fold draws its destination inside it. Its stylesheet follows the variant
  D one and declares the reference's tokens under its names and with its
  values (`--bg`, `--surface`, `--line`, `--ink`, `--muted`, `--accent`,
  `--ok`, `--warn`, light and dark), and its type: 15 px `system-ui`,
  normal leading, a paragraph at 1.5. `/journal` and `/projet/<key>` are served in it, and
  `/projets`: the declared projects, each with its « Page projet » (the
  « Projets » zone of the home screen), until the Fold of « Projets »;
  `/runs`, `/runs/run`, `/usine`, `/rituels` and `/analyses` are served in
  it by direct build (sections below); `/runs/job` answers, in it, that
  the destination is not served here yet. The shell's own tokens: `--pn-control-line`, the box of a
  control, at 3:1 at least on the surface and the background in both
  themes, where the reference's `--line` is not; `--pn-muted-text` and
  `--pn-warn-text`, the muted and the warning text, darker in the light
  theme, where the reference's `--muted` and `--warn` are under 4.5:1 on
  `--bg`.
- `ui/home/overview.py` — `overview_view` reads the state of the
  destination from the snapshot and the requests; `render_overview` draws
  it. Loading while the tracker has not answered and no read of it ended,
  « Cette vue est indisponible » with « Réessayer » (`POST /api/health/recheck`)
  once a read of it failed (`ReadModel.fail`, from the poller; a `bd` call
  fails after `COCKPIT_BEADS_READ_TIMEOUT_SECONDS`, 10 s);
  « Rien à afficher ici » when nothing waits and nothing is declared;
  otherwise four indicators (« Décisions à prendre » counts the requests;
  the three others are what the tracker keeps as said of them, or « Non
  collecté »), the activity of seven days (the daily volumes of its three
  series the tracker keeps as said under « Activité sur 7 jours », one
  line a day and a series, « PR fusionnées · Lundi : 1 », drawn as the
  reference draws them, each series told apart by its dashes as well as
  its colour -- a token at 3:1 at least on the surface in both themes --,
  and said in a table a screen reader reads; without them, an empty grid
  and the volumes said not collected), the last runs (the cards the
  tracker carries under `gc.run_card`, drawn in their frame as the
  reference draws them -- workflow, status, title, step, a lane per
  participant with a bar per job, axis, start, duration --, the frame as
  tall as its cards; a card opens Runs, the reuse of the Runs card itself
  and the opening of its run are T44's; without one, the frame says the
  cockpit reads none), « Ce qui t’attend » beside the result
  open under it, and the projects, those something waits for first. An
  indicator and a project's card are links (to `/analyses`, to the
  requests, to `/projet/<key>`), so the keyboard opens them as a click
  does; the line of the request open carries `aria-current` and an
  accent mark, not only its background. Selecting a request scrolls to
  its detail under « Détails techniques et actions » and moves the focus
  there.
  A supervisor or tracker reading that is no longer current keeps the
  last values under « Lecture périmée · état actuel inconnu. »
- The result open is the result of a chantier as the records of the D01
  flow give it (A1, af-c662qx; `projects/outcome.py`, below): the first one
  to judge, else the first active one, else the last one ended; without
  one, the first request and the way to its detail. No record a
  demonstration dataset writes (`gc.result_dossier`) is read. A result to
  judge (to judge, its dossier outdated, its trial down) shows the title
  of its request of acceptance, the title of its Spec, then, above its bar,
  its dossier: the two parts that open its page, « Ce qui reste à
  vérifier » -- for the Factory's own project (« Usine »), the recette of
  the cockpit first, each proof said present or missing (a verified
  restart is the stop driver's `essai_reussi`; the alert and the days of
  real use have no source and are said missing), then the rubric « Ce qui
  n'a PAS été vérifié » of its dossier page, or that the page could not be
  read --, its other rubrics, « Version et sources » (the version, the
  fingerprint and the Spec the records give, when the page leaves it
  out), and its reports (rubrics named « Compte rendu … »). An outdated
  dossier or a trial down is said above it. A result judged shows « Suivi
  du résultat »: its issue, and under « Historique et preuves » when it
  was ready, when the answer was recorded, the proof of the merge (« Fusion
  confirmée · résultat jugé … → commit fusionné … ») or « Aucune preuve de
  fusion à ce stade. », the reason of an abandon. A project's card says its
  current chantier -- its last one ended when none is active -- at the
  issue of its result when it has one, else at the stage of its
  `gc.project_card`, else at its computed stage. No door is wired to
  Essai, Avis or a resource that opens on this destination (A2): Essai and
  Avis are drawn unavailable under every result, judged or not, and the
  bar says why (not wired yet on a result to judge; of no use on a result
  already judged; unsure on a result unknown or inconsistent); nothing
  shows a command done that no door recorded. A chantier whose Outcome is
  to judge offers no « Accepter » on the page of its project nor in « Ce
  qui t’attend »: its chip leads to its result on the home page
  (`#pn-result`), and its request is the Acceptance Request the escalation
  door writes on the convoy -- `cockpit.projects.actions` refuses the
  cockpit's own acceptance of a convoy of the new flow.
- The zones of variant D that no destination of Panorama holds yet -- the
  inbox with its actions, the projects with their chantiers, the stop,
  the access and the health zones -- are kept, whole and working, folded
  under « Détails techniques et actions » (`ui/base/page.py`
  `render_home_zones`); selecting a request opens its detail there. They
  leave it as the Folds of their destinations take them.

`tests/cockpit-criteria/commands/home-destination-*-test.py` launch the
real cockpit on each of the 10 home states of the reference and read the
page in a headless Chromium at 1440 and 390 px, light and dark -- every
anchor of the reference with its element, its enclosing anchor, its
font-family and line-height, and the tokens of the page, the values
written in the cases (an outline of anchors per state, read from the
frozen pages); the cards of « Derniers runs », read in the document of
their frame; a focus a person sees (drawn at 3:1 at least) and the local
scroll kept. `home-result-states-test.py`, `home-d01-records-test.py` and
`home-recette-test.py` (A1) hold the result states, the records of the
D01 commands read back on the home and the project page, and the recette.

**The Outcome of a chantier** (`projects/outcome.py`, A1; « résultat » on
the screens). `read_outcome` reads, on a convoy that carries the new-flow
mark, the Delivered Outcome, its Evidence Pack, the acceptance, the
judgement, the promotion and the closing through
`convoy_state.outcome_records_of` -- the reader of `bin/convoy-state`, which
validates each record as `show` does (`docs/CONVOY_STATE.md`); the cockpit
reads no `gc.flow.*` key itself -- and gives one issue the home, the
project page, its chantiers and its history all say:

| The records say | Issue |
|---|---|
| one of them cannot be read, or is not one `bin/convoy-state` would have written | Inconnu |
| the answer « accepté » or « abandonné » names another commit or dossier fingerprint than the Delivered Outcome; the commit judged of the promotion is not the commit of the answer | Incohérence |
| closed as accepted, a promotion recorded | Fusionné (history: the commit judged → the commit merged) |
| closed as accepted, no promotion; abandoned with a promotion; a promotion with no acceptance in force | Incohérence |
| an answer « abandonné », or closed as abandoned | Abandonné (nothing merged, its reason) |
| an acceptance in force and a promotion, the convoy open | Fusion en cours |
| an acceptance voided (conflict, red check) | Acceptation annulée |
| an acceptance in force | Accepté (the merge pending) |
| « constats rendus » | Constats rendus |
| a result delivered and no answer since: the request of the acceptance says the trial failed | Essai en panne |
| the same, the dossier of another version or fingerprint | Dossier périmé |
| the same, otherwise | À juger -- « à toi de jouer », never « bloqué » for its closed tickets |
| none of these yet | its tickets give its stage; a convoy of the new flow whose tickets are all closed is not « bloqué » |

A merged or abandoned closed convoy goes to the history of its project. A
closed ticket is never counted as a merge of the result. The page of the
dossier is read by `projects/source.py` in the folder its record names
(`path`, the folder of the Evidence Pack; `read_pack_sections` opens its
`index.html`: one rubric per `<section id="rubrique-N">`).

## « Pour moi » au premier plan, gestes confirmés, commandes qui n'échouent plus en silence (B, af-4uzgzm ; BR, af-eyc5ah)

Spec af-fgcw0d, user stories 6, 27, 29, 34, 73, 75, 76, 79, 122 et 175 ;
Validated Prototype `prototype/cockpit-b-zones-20261012` à 632deea, états
result-request et result-confirmation. Cette section est écrite pour
Benjamin, qui se sert de ces gestes lui-même (ADR-0017, condition 4).

**Ce que tu y gagnes** (ADR-0017, condition 3 : temps humain et jetons).
Avant B, « Ce qui t’attend » était replié sous « Détails techniques et
actions », aucune demande ni bouton « Relancer » n’existait pour une session
mise en pause par l’usine, une proposition ne se reportait qu’à une heure
écrite en mots (qui ne la cachait pas), et une commande qui ne répondait pas
laissait le geste sans réponse. Relancer une session en pause passait donc
par une session d’agent : une demande écrite, le contexte relu par l’agent,
puis la vérification de ce qu’il a fait.

| Geste | Avant B | Avec B |
|---|---|---|
| Ouvrir une demande et voir ses gestes | 1 clic de plus (déplier la zone technique) | 1 clic sur la ligne |
| Relancer un ordre en pause | une PR qui retirait son nom de `[orders] skip` de `city.toml`, sa CI et un rechargement de la cité (#701), ou depuis le 23/10 une commande `bin/order-pause resume` tapée par un agent | 2 clics (armer, « Confirmer ») et aucun jeton ; la pause levée est relue à la source en moins de 20 s (`TRACED_SECONDS`) |
| Relancer une session en pause | une session d’agent : quelques minutes de ton temps et les jetons d’une session (estimation, non mesurée : de l’ordre de 20 000 à 50 000 jetons pour relire le contexte) | 2 clics (armer, « Confirmer ») et aucun jeton ; l’écriture à la source est relue en moins de 20 s (mesuré par les tests de critère, `TRACED_SECONDS`) |
| Reporter une proposition jusqu’à une heure | impossible sans agent : l’heure écrite en mots ne la cachait pas | 2 clics, la proposition est cachée jusqu’à l’heure choisie |
| Une commande qui ne répond pas | le geste restait sans réponse, et le répéter risquait un doublon | une erreur lisible en 15 s au plus (`COCKPIT_ACTION_TIMEOUT_SECONDS`), puis une relecture de la source avant tout nouvel essai |
| L’usine se tait | rien ne le disait sur l’accueil | une demande Urgent « Usine muette » après 15 min de silence |

**Pour moi est la boîte de décision de la Vue d’ensemble.** « Ce qui
t’attend » n’est plus replié sous « Détails techniques et actions » : chaque
ligne ouvre sa demande à côté de la liste, là où s’ouvre le résultat d’un
chantier (`lib/cockpit/ui/home/pour_moi.py`). La demande propre au résultat
(sa demande d’acceptation) ouvre le résultat. Une demande ouverte dit de quoi
il s’agit, son titre, pourquoi elle t’attend, les options préparées, puis sa
barre de gestes :

| Demande | Gestes |
|---|---|
| une question (NEEDS BENJAMIN) | ses options, chacune la réponse (armée, puis « Confirmer ? ») ; Continuer avec un agent ; Acquitter (Urgent) ; Reporter |
| une proposition de classe décision | Accepter ; Refuser, avec la raison écrite dans son champ ; Reporter → « Dans 1 h », « Dans 4 h », « Demain 09:00 », chacun armé puis confirmé ; Continuer avec un agent |
| une session mise en pause par l’usine (`[session-loop] <session>`, `gc.source=factory-session-loop-guard`, `lib/cockpit/requests/sources/paused_sessions.py`) | Relancer (armé, puis confirmé : `factory-session-loop-guard resume`, tracé sur sa fiche, « Relance demandée » au journal) ; Reporter |
| un ordre en pause (« Un ordre de l’usine est en pause » : la fiche ouverte de `bin/order-pause pause`, `gc.order_pause=<ordre>`, `lib/cockpit/requests/sources/paused_orders.py`) ; le nom de l’ordre, qui l’a mis en pause et ses mots sont dans les détails | Relancer (armé, puis confirmé : `bin/order-pause resume <ordre> --by benjamin --words "relance depuis le cockpit"`, qui ferme la fiche de la pause ; « Relance demandée » au journal) ; Reporter |
| « Usine muette » | Vérifier l’usine (la page Usine) ; Revérifier maintenant |

Chaque geste qui modifie l’usine se fait en deux temps
(`cockpit.ui.actions.render`) : un premier clic l’arme, « Confirmer ? », un
second l’envoie. Une proposition reportée passe par `bin/proposal-door
reporter` avec l’heure que le cockpit a calculée (ISO, heure de Paris) :
`gc.proposal_report_until` la cache jusqu’à cette heure, comme
`gc.cockpit_defer_until` cache toute autre demande ; une heure écrite en
mots libres ne cache rien.

**Un ordre se relance par sa porte.** Depuis le 23/10, une pause d’ordre
est une fiche du suivi posée par `bin/order-pause` (af-npz9v1.15, #724) ;
BR la lit et la lève par cette porte, jamais par `gc order run`, qui
lancerait l’ordre hors de son échéance sans lever la pause. Un ordre retiré
par `[orders] skip` de `city.toml` reste ta décision de config : le cockpit
n’en lit aucune demande, et la porte ne le touche pas. Le cockpit trouve la
porte par `COCKPIT_ORDER_PAUSE_BIN` (par défaut `bin/order-pause` du dépôt).

Sur une lecture qui n’est plus à jour, les gestes sont dessinés et
indisponibles (« Lecture périmée : les gestes reviennent à la prochaine
lecture. »). Tant que le suivi des tickets est illisible, la boîte dit
« Inconnu : illisible depuis HH:MM » et liste ce qui ne vient pas de lui.

**Texte principal en français, détails repliés.** Une ligne et une demande
ouverte disent le français du cockpit. Le texte d’un producteur passe le
contrôle de `cockpit.text.validate` : pas d’identifiant, pas de terme
interne, une ligne de 140 caractères au plus, et dans la langue de
l’opérateur. Les termes internes sont ceux que `GLOSSARY.md` met hors du
cockpit (ligne « _Never shown in the cockpit_ » du Cockpit Lexicon) : le
glossaire est le seul vocabulaire, aucune liste n’est recopiée dans le
code. La langue est celle que donne `bin/operator-config language` (« fr »
aujourd’hui) ; une phrase est refusée quand elle tient autant ou plus de
mots grammaticaux d’une autre langue (anglais, espagnol, allemand, italien,
portugais) que de la sienne, ou, à partir de cinq mots, aucun des siens
(`speaks`). Le cockpit trouve le glossaire par `COCKPIT_GLOSSARY_FILE` et
la porte des réglages par `COCKPIT_OPERATOR_CONFIG_BIN` (par défaut ceux du
dépôt) ; s’il ne peut lire l’un ou l’autre, chaque champ est remplacé et le
motif le dit, rien n’est montré sans contrôle. Un champ refusé est remplacé par sa phrase de repli et le
défaut du producteur est compté ; les portes (`bin/proposal-door`, par
`bin/operator-text-check`) appliquent le même contrôle avant d’écrire. Un
titre écrit hors de ce contrat est redit en entier après le libellé du
cockpit (« Texte écrit : « … » ») seulement s’il est dans la langue de l’opérateur et ne porte ni
identifiant ni terme interne (`speaks_plainly`) ; sinon les mots du
producteur ne sont que dans les détails repliés. Les « Détails » repliés de
chaque demande donnent son identifiant, sa nature, pourquoi un champ a été
remplacé, les mots du producteur tels qu’écrits, la source précise et les
liens où elle vit (la page de son projet, la page Usine, le journal).

**Signal non reconnu** (user story 76) : une fiche ouverte du suivi des
tickets qu’un producteur de l’usine a déposée (`gc.source`) et que le
cockpit ne sait pas lire, qui n’est d’aucune forme qu’il lit (question,
proposition, session en pause) et qui n’a alerté personne (ni
`gc.needs_benjamin`, ni `gc.escalation_mayor_paged_at` : une alerte d’abord
adressée au Maire reste au Maire), n’est pas une demande opérateur : elle
informe, elle n’attend ni décision ni geste de l’opérateur (GLOSSARY.md,
« Operator Request »). Pour moi la montre à part de ses demandes, sous
« À savoir · signaux non reconnus » : « Signal non reconnu venant de
<producteur> », sans niveau, sans geste, hors du compte des décisions
(`lib/cockpit/requests/sources/unknown_signal.py`,
`cockpit.ui.home.pour_moi.render_signals`). Le nom du producteur n’y est dit
que s’il passe le même contrôle (`speaks_plainly`) ; sinon (« disk-watch » a
la forme d’un identifiant) elle dit « Signal non reconnu venant d’une source
nommée dans les détails ». Son identifiant, son producteur, son titre et sa
description, tels qu’écrits, sont dans son repli sous « Texte brut », jamais
en texte principal : le cockpit n’invente aucun sens.

**Usine muette** (`lib/cockpit/requests/sources/silence.py`) : le heartbeat
ne part que tant que le superviseur et le suivi des tickets sont lus à jour ;
dès que l’un d’eux se tait plus longtemps que `COCKPIT_SILENCE_ALERT_SECONDS`
(900 s, le délai d’alerte du heartbeat), le cockpit lève une demande Urgent
« Usine muette » qui nomme les sources et depuis quand. Elle part quand les
deux sont de nouveau lus à jour ; elle est envoyée comme toute demande
Urgent. Elle s’affiche même quand le suivi des tickets n’a jamais été lu
(home-loading, home-error), hors des parties que la référence numérote.

**Une commande qui expire** (af-fksj2c, `cockpit.actions.registry`,
`cockpit.actions.uncertain`) : une porte qui ne répond pas dans
`COCKPIT_ACTION_TIMEOUT_SECONDS` (15 s) est arrêtée. Le POST répond 504 avec
une erreur lisible (« La commande n’a pas répondu en N s : elle a expiré.
Son issue est incertaine ; le cockpit relit la source avant tout nouvel
essai. ») et `incertain: true`, et le suivi des tickets est relu aussitôt.
Sa cible est marquée incertaine : un nouveau geste sur elle répond 409 tant
que le suivi n’a pas été relu après la marque ; ensuite, si la demande
n’attend plus — la commande avait fait son travail —, 409 pour de bon (« Le
geste précédent a été enregistré à la source … ») et la page montre le
succès lu ; si elle attend encore, le geste part. Tant qu’un geste serait
refusé, la page le dessine indisponible avec la même raison, même quand la
relecture a échoué (`UncertainOutcomes.pending`). Il en va de même quand la
porte a fait son travail et que ce que le cockpit fait après elle échoue —
écrire la trace d’une relance, relire la réponse qu’`escalation-door` a
écrite (`FollowUpFailed`) : le geste est fait, il n’est donc pas refusé
comme si rien n’était parti ; le POST répond 502 avec `incertain: true`
(« La commande a été exécutée, mais la suite n’a pas pu être enregistrée :
… ») et un second clic n’envoie rien avant relecture. La cible d’une
relance est résolue avant que sa porte parte. Une erreur imprévue d’un
geste répond 500 avec une phrase lisible au lieu de casser la requête. La
page montre l’erreur sur la demande et se relit.

## Home screen, as the validated prototype shows it (af-mjfvwx)

Since T02 (above), this variant D is folded under « Détails techniques et
actions » of « Vue d’ensemble ».

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
  (`POST /api/actions/accepter_chantier`, two-step, traced on the convoy;
  refused on a convoy of the new flow, see « A delivered chantier asks for
  acceptance only with something to judge » below)
  and « Pas bon → agent » (`pas_bon_vers_agent`, a prompt to copy).

Two rules the real data needed:

- A convoy bead without `gc.graph_digest` is gc's own "input convoy", not
  a chantier.
- A convoy without `gc.project_id` is placed under the project declaring
  the rig its tickets are dispatched to (`gc.dispatch_rig`; spec « Données
  de projet » : « projet déduit du rig »). With neither, it is listed under
  « Sans projet ».

Since then: Livré-non-Accepté is a « Quand tu veux » request, and the
roadmap step and « dev a N commits d'avance » are read (see « Project
repositories » below). Promu is computed too (« Promu » below).

`tests/cockpit-home-projects-test.py` drives all of the above through the
process's HTTP surface.

## A delivered chantier asks for acceptance only with something to judge (2026-10-07)

Intent (Benjamin, his words, 2026-10-07): « on me demande d'accepter un truc
je n'ai aucune idée de ce que c'est exactement, ce que je dois faire en
tant qu'humain. […] Soit on rend l'humain vraiment utile en le guidant,
soit on le skip » ; then, on the proposal to drop the request for chantiers
delivered before D01 and to send C01 back to its seven-day criteria:
« ok fait tout ca ».
Mechanism (agent interpretation), in `lib/cockpit/projects/stage.py`:

| Closed convoy, not accepted | What the Cockpit does |
|---|---|
| carries the new-flow mark (`gc.flow.mark`, `bin/convoy-state`) | asks, as before: « Livré, non accepté » |
| carries `gc.cockpit_acceptance_note` (one line: what to look at) | asks, and shows that line as « Pourquoi ça t'attend » |
| neither | asks nothing: « Livré avant le flux d'acceptation : rien à accepter », in the project's historique |

Why: a convoy with neither was delivered by the flow that merged each
ticket to the protected branch as it went and closed by itself; no Evidence
Pack exists and the button changed a label only. It is not accepted in
Benjamin's name (no `gc.cockpit_chantier_accepted` is written), and nothing
changes for a convoy of the Delivery Workflow. A note the main-text control
refuses (`text/validate.py`) falls back to the fixed phrase.

**A convoy of the new flow is not accepted by the click (T29, Spec
af-wf4w5r §11).** For a convoy that carries `gc.flow.mark`:

- `accepter_chantier` is **refused and writes nothing**, with a French
  message that sends Benjamin to the Acceptance Session: its acceptance is
  his answer recorded by `bin/owner-answer`, with his words, the commit and
  the fingerprint of the dossier (`docs/OWNER_ANSWER.md`) — three things
  the click does not know. A convoy that cannot be read is refused too.
- the stage « Accepté » is read from that recorded answer
  (`convoy_state.owner_answer_of`: the last answer of `gc.flow.judgement`
  is `accepted`), in `stage.py` and for Promu (`promu.py`), **not** from
  `gc.cockpit_chantier_accepted`, which is ignored there.

A convoy without the mark is unchanged: the click writes
`gc.cockpit_chantier_accepted` and the stage reads it. Limit: the panel
still shows « Accepter » on a closed marked convoy with no recorded answer;
the click is refused. `tests/cockpit-chantiers-test.py` covers both.

Set a note: `gc bd update <convoy> --set-metadata
"gc.cockpit_acceptance_note=<one line, plain French, 140 characters>"`.
C01's convoy carries one, drawn from its Spec's end criteria (seven
consecutive days of real use).

Consequence to know: a convoy still delivered by the old flow after this
change (D01's own convoy does not carry the mark) will ask nothing when it
closes, unless it is given a note. To undo: drop the `nothing_to_judge`
branch in `stage.py`.

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
own repository — the slice that gives the cockpit its clones).

A signal the cockpit cannot read (`requests/sources/unknown_signal.py`) is
information, not an Operator Request: Pour moi shows it apart, uncounted,
and `/api/requests` does not list it.

`tests/cockpit-other-requests-test.py` covers all of the above through the
process's HTTP surface.

## One text contract for the proposal door and the inbox (2026-10-07)

Intent (Benjamin, his words, 2026-10-07): « le producteur proposal-door et
le lecteur Cockpit partagent un même contrat de champs ».
Mechanism (agent interpretation): one function,
`cockpit.text.validate.request_violations` (`lib/cockpit/text/validate.py`),
decides whether `quoi`, `pourquoi` and `que_faire` display as written. The
inbox calls it before showing a request; `bin/proposal-door create` calls it
through `bin/operator-text-check` before writing one, and refuses the write
with the reason. It does not loosen the main text (spec .73), and it does
not rewrite any existing proposal.

| Cause of a refusal | Example | Where the producer reads it |
|---|---|---|
| an identifier | `af-th4gdf`, `#300`, `pr-autopilot`, `idle-ready-work-wake` | stderr of `proposal-door create` |
| an internal term outside the Cockpit Lexicon | bead, convoi, Mayor, order | same |
| more than one line, or more than 140 characters | | same |
| a missing field, an option without its consequence | | same |

Why: four proposals (af-os9sh2, af-vnv59w, af-1ai5e3, af-vws964) passed the
door, which only checked presence, one line and 140 characters, and were
then shown « incomplète : champ … manquant » with every field present in
Beads — the inbox had replaced each field holding an identifier or an
internal term by its fixed repli. Options without `recommande`/`raison`,
straight apostrophes, non-ASCII letters, length and the read model's cache
were not the cause.

A request written before the door checked, or by a producer that does not
go through it, still shows its repli as main text; the folded « Détails »
of the request now give, per replaced field, the reason (« Refusé ») and
the text exactly as written (« Texte écrit »). `GET /api/requests` carries
the same as `motifs` and `texte_origine`.

Identifiers and evidence have their own place: the optional `details`
field of `proposal-door create` (one line, 1000 characters, stored as
`gc.proposal_details`), shown as « Précisions » in the same folded details
and never checked. The Mayor prompt (« Improvements are proposals ») used to
tell producers to put bead/PR ids in `pourquoi` or a `consequence`; it now
sends them to `details`.

`bin/upstream-skills-check` put its reference file's path in `pourquoi`;
the path now goes in `details` (a path under another directory could hold
an identifier-shaped segment and be refused).

Check a text by hand: `bin/operator-text-check '{"quoi": …, "pourquoi": …,
"que_faire": [...]}'` (exit 0 = displays as written; exit 1 = reasons on
stderr). `tests/proposal-cockpit-contract-test.py` creates proposals
through the door and reads them through the Cockpit process; its fixture
`tests/fixtures/cockpit/requests/refused-proposals.json` holds the four
cases as Beads holds them.

Known gap: `bin/escalation-door benjamin` does not run this control yet
(its own 2 h promotion text names the Mayor and the bead, so the control
would refuse it): a NEEDS BENJAMIN can still reach the inbox as a repli.

To undo: remove the `cockpit_can_display` call in `bin/proposal-door`.

## After an action, the list is right at once (2026-10-07)

Intent (Benjamin, his words, 2026-10-07): « l'item reste tout pareil dans
la liste, et je peux même re accepter. […] Il faut afficher l'item dans le
bon état ensuite, ou l'enlever. »
Mechanism (agent interpretation): the action was written, but the page
reads the read model, which only saw it at the next regular read (20 s for
Beads, 30 s for the projects), and the page did not reload either. Now
`POST /api/actions/<action>` re-reads the bead-backed sources (`beads`,
`projets`, `journal`) before it answers, and says so (`rafraichi`). The
page script (`ui/actions/render.py`, `settle`) then, for every action that
writes: says a refusal instead of staying silent; on success writes the
result on the request, removes its controls, and reloads when `rafraichi`
is true -- the reloaded list shows the request gone or in its new state.
When the re-read did not finish within 8 s, the request stays marked as
handled until the next regular read. It does not change what any action
writes, nor the exit-at-source rule.

Shown at the click (Benjamin, his words, 2026-10-07: « il faut qu'il y ait
un peu d'optimistic UI, car là le bouton et l'item restent longtemps comme
si on avait pas cliqué … pareil pour l'item projets »). Mechanism (agent
interpretation): `mark` greys the request, its row in the list and the
chantier's row in « Projets », switches their controls off and writes the
expected result followed by « · enregistrement… », before the server
answers (its re-read takes seconds). The answer confirms the text and
reloads, or -- a refusal, a lost connection -- puts everything back and
says so. Nothing is shown as recorded before the server said so.

`continuer`, `pas_bon_vers_agent` and `notifier_test` write nothing on a
bead and trigger no re-read. To undo: drop the `rafraichi` line in
`core/server.py`.

## Which proposal waits on Benjamin (ADR-0029)

Intent (Benjamin, his words, 2026-10-07): « oui pour R1, enregistre la
décision et lance la puce » — R1: two classes of proposal at creation,
`maintenance` (orders, guards, tests, docs) and `decision` (behaviour,
method, spend, what he sees); the `maintenance` class is not shown to him.
Mechanism (agent interpretation): `requests/proposals.py` is the one
reading of a `proposal` bead's class, shared by the inbox and the health
zone, so a proposal is never in both and never in neither:

| `gc.proposal_classe` | Where it shows | Why |
|---|---|---|
| `decision` | « Ce qui t'attend », Quand tu veux, with its « Recommandé » option | ADR-0029 point 3 |
| `maintenance` | health zone, one line « L'usine corrige seule N défaut(s) qu'elle a constaté(s) depuis … » (kind `ok`: information, not a problem — the zone stays « ok ») ; the journal when the door takes it over or reconverts it | ADR-0029 point 2 |
| absent, fields present (the door wrote it before the class existed — the proposals open on 2026-10-07) | « Ce qui t'attend », as before | still Benjamin's to treat; in doubt, `decision` (point 6) |
| absent, no `gc.proposal_*` field at all (never written by the door) | health zone, « N proposition(s) sans champs lisibles : à reformuler par la porte des propositions, ou à fermer » (kind `warn`) ; no longer a request | ADR-0029 point 4 |

A maintenance proposal in state `prise_en_charge` (the door filed its bug
bead) or `ouverte` is counted in the health line; `a_planifier`,
`rejetee` and `resolue` leave it. An unknown class value reads as
`decision`: a producer's mistake must reach the operator, never vanish.

`tests/cockpit-requests-test.py` (inbox side) and
`tests/cockpit-health-test.py` (health side) cover this through HTTP.

The producer side is `bin/proposal-door create` (the same ADR): `classe`
is mandatory; a `decision` must carry exactly one `recommande: true`
option with its `raison` or the door refuses the write; a `maintenance`
proposal makes the door file one bug bead (`gc.authorized_by=ADR-0029`,
`gc.source=proposal-door`, `gc.proposal_id`, label `maintenance`, type
bug), relate the two, set the proposal to `prise_en_charge`
(`gc.proposal_bug`, trace « PROPOSITION PRISE EN CHARGE par proposal-door
— ticket … ») and mail the Mayor, who dispatches it with
`bin/factory-work-dispatch` — never `escalation-door mayor`, whose sweep
would promote the bead to Benjamin after two hours. `bin/proposal-door
reconvertir` (point 6) closes that bead and makes the proposal a
`decision` again with new options. `compte --classe` and `list --classe`
read the same class rule as the Cockpit (`maintenance`, `decision`,
`sans_champs`). The orders that produce proposals declare their class:
`bin/upstream-skills-check` and `bin/overlap-conflict-log` both file a
`decision` with a recommendation (a re-pin and dynamic leases are method
rules); `bin/escalation-door` and `bin/dispatch-door` create no proposal
(the first counts them, the second refuses to dispatch one).
`tests/proposal-classes-contract-test.py` runs the real door and the real
Cockpit on the same fake tracker, one proposal of each class.

## Journal of resolved requests (af-mjfvwx)

`GET /journal` (linked under « Ce qui t'attend ») and `GET /api/journal`
serve `ui/journal/` (T15, until now imported only by its test). Each entry
says what was asked, how it was resolved, when (Paris time), by whom, and
by which way (spec .18); a bead resolved twice has two entries (spec .19).
The cockpit keeps no copy: `requests/journal.py` `read_journal` is the
read model's `journal` source (every `COCKPIT_JOURNAL_POLL_SECONDS`, 60 s)
and re-reads the traces; a read fails after
`COCKPIT_JOURNAL_READ_TIMEOUT_SECONDS` (20 s), which the isolated recipe
raises to a day with the tracker's, so that a journal being read stays so.

What the tracker really holds, checked 2026-10-06 — T15 had assumed Beads
comments, which are empty on a bead Benjamin answered:

| Trace | Written by | In the bead's notes | Dated by |
|---|---|---|---|
| answer to a NEEDS BENJAMIN | `bin/escalation-door repondre` | `RÉPONSE: <lettre> — <option>` | `gc.escalation_response_at` (latest answer only) |
| decision cleared without an answer | `bin/escalation-door clear` | `DECISION CLEARED: …` | `gc.escalation_cleared_at` (latest clearance; absent before 2026-10-06) |
| proposal accepted / rejected | `bin/proposal-door` | `PROPOSITION ACCEPTÉE par …` / `PROPOSITION REJETÉE par … — <raison>` | `gc.proposal_response_at` |
| proposal resolved by a merged delivery | `bin/proposal-door resoudre` (called by `bin/deliver-close`, `bin/upstream-skills-check`, or by hand) | `PROPOSITION RÉSOLUE par … — <preuve>` | `gc.proposal_response_at` |
| maintenance proposal taken over by the factory / reconverted into a decision (ADR-0029) | `bin/proposal-door` | `PROPOSITION PRISE EN CHARGE par … — ticket <bead>` / `PROPOSITION RECONVERTIE en décision par … — <raison>` | `gc.proposal_response_at` |
| relance, chantier accepté | `cockpit.actions.trace` | `Cockpit: <quoi> sur <cible> (…) — <quand>, par <acteur>` | the note itself |

The question an entry answers is the `NEEDS BENJAMIN: …` / `PROPOSITION: …`
note before it. An entry no trace dates shows « date inconnue » and comes
after the dated ones.

### Proposition résolue par une livraison fusionnée

Intent (Benjamin, his words, 2026-10-07): « les propositions sont la main
de Benjamin (accepter/rejeter) ; une fermeture automatique n'est légitime
que sur preuve de merge référençant explicitement la proposition ».

Mechanism (agent interpretation): a proposal has a fourth state,
`gc.proposal_state=resolue`, reached only through `bin/proposal-door
resoudre <bead> <preuve> <acteur>`. The door refuses a proof that names
neither a PR number nor a commit sha, refuses a bead that is not labelled
`proposal`, and refuses a proposal already accepted, rejected or resolved —
Benjamin's decision is never overridden by a delivery. The proof is kept
on the bead (`gc.proposal_resolved_by`) and in its notes; a resolved
proposal leaves « Ce qui t'attend » at the source and enters the journal as
« proposition résolue par une livraison — <preuve> ». Two producers call
it from code:

- `bin/deliver-close`, after a verified merge close (so also every
  `pr-autopilot` reconciliation): every still-pending proposal the merged
  PR names in its title, body, a commit message, or in
  `gc.resolves_proposal` on the delivered bead, with the proof
  `PR #<n> (<repo>, merge <sha>)`. A PR that names no proposal resolves
  none; a prefix match (`af-prop1` in `af-prop10`) is not a mention.
- `bin/upstream-skills-check`, on each daily run: every pending proposal
  it filed for a `mattpocock/skills` tag at or before the pinned baseline
  tag, with the pin as proof (last commit touching
  `docs/UPSTREAM_SKILLS.md`, and its PR number). Such a tag is never
  proposed again.

Why (2026-10-07): af-3yo0we and af-yc2ly0 (tags v1.2.3 and v1.3.1, pinned
by PR #385), af-1ai5e3 (fixed by PR #376) and af-r2y2w9 (fixed by PR #340,
named in its title) stayed « pending » in « Ce qui t'attend » for days
after their fix had merged: nothing closed a proposal when the delivery
that answered it landed. A PR that fixes a proposal without naming it
(PR #376's shape) is resolved by hand with the same door, proof in hand.

Intent (Benjamin, his words, 2026-10-06): « affiche tel quel ». Mechanism
(agent interpretation): the journal shows each text exactly as its
producer wrote it, without the main-text control (`text/validate.py`) the
inbox applies — a record of what happened, where that control hid nearly
every entry written before it existed. It does not loosen the inbox.

Known gap: an answer older than the bead's latest one, and a clearance
made before the door dated it, carry no date.

`tests/cockpit-journal-test.py` covers the page through HTTP, with beads
carrying notes and metadata as the doors leave them.

## Notifications and heartbeat, running (af-mjfvwx)

T17 (`notify/`) and T18 (`heartbeat/`) each built a policy with `tick()`
as its whole interface, tested with a fake clock, and left the thread that
ticks it to a later ticket. `notify/service.py` is that caller:
`Ticker` (the thread), `NotifyService`, `HeartbeatService`;
`core/process.py` starts them.

**The Pushover adapter was not the API's.** It sent AES-GCM in a
`ciphertext` field with a base64 key; pushover.net/api ("End-to-End
Encryption", read 2026-10-06) wants `encrypted=1` and each of `title` /
`message` as base64(IV + AES-256-CBC(gzip(text)) + HMAC-SHA256), with the
64-character hex key the Pushover app shows. No push could have arrived;
its tests only ever drove a fake adapter. `notify/pushover.py` now follows
the documented scheme (through `openssl`, as the API's own example does).
It has not been tried against the real service: that is the manual step of
the mobile slice.

| Setting | Meaning |
|---|---|
| `COCKPIT_PUSHOVER_SECRETS_FILE` | JSON `{token, user_key, e2e_key}`, outside the repository (written by `bin/cockpit-setup-wizard pushover-secrets`) |
| `COCKPIT_HEARTBEAT_URL_FILE` | the Healthchecks.io ping URL of the « Usine muette » check (`heartbeat-secret`) |
| `COCKPIT_PUBLIC_URL` | the address a push links back to (the ts.net URL) |
| `COCKPIT_NOTIFY_STATE_FILE` | what was already sent, kept across a restart (default: beside the pid file) |

Unset or unreadable, nothing is sent and nothing is pinged, and the health
zone says « Notifications iPhone inactives : … » / « Alerte « Usine
muette » inactive : … » (spec .98). Nothing makes the cockpit reach
Pushover or Healthchecks.io by default.

- The notify policy runs on the same list as « Ce qui t'attend »
  (`requests/assemble.py` `assemble_from_snapshot`), and only while that
  list is whole: with the tickets unreadable no request is taken for
  resolved, so no « Urgent résolue » is sent for a dead source.
- A send the channel refuses is retried; the request shows « notification
  non livrée » (spec .59); after 15 min the health zone says « Canal de
  notification en panne ».
- The heartbeat pings only while the supervisor and the tickets are read
  fresh. It is not paused by a clean stop yet (the stop driver is not
  wired).
- `/journal` carries « Journal des envois » (request, level, time,
  accepted or failed — in memory, last 200) and « Envoyer une notification
  de test » (`POST /api/actions/notifier_test`, Benjamin's identity
  required). `GET /api/notifications` is its JSON twin.

`tests/fixtures/cockpit/notify/fake_pushover.py` answers as the API
documents and decrypts with the documented scheme;
`tests/cockpit-notifications-test.py` runs the real process with its real
adapter and emitter against it.

## Local settings file (af-mjfvwx)

Intent (Benjamin, his words, 2026-10-06): « ok pour l'emplacement ».
Mechanism (agent interpretation): one local, unversioned JSON file tells
the cockpit where the two secret files are — it does NOT hold a secret
itself, and nothing in the repository names his account.

On the VM (I, af-cp4fzd; Spec af-fgcw0d, user story 98), the secret files
are private files of the account that runs the cockpit, outside every
repository, readable by that account alone (`bin/cockpit-setup-wizard`
writes them `0600`, and makes a file that was already there `0600` before
writing in it); the procedure linked from « Accès » (below) proposes
`~/.config/agent-factory/`. A path of the file that starts with `~/` is
read in the home of that account (`HOME`). The Windows profile of
af-mjfvwx (`C:\Users\<lui>\.agent-factory-cockpit\`, read through
`/mnt/c`) is no longer where they live: the cockpit runs on the VM, which
has no such path.

`cockpit-local.json`, beside the pid file (`.gc/runtime/` on the live
root; `COCKPIT_LOCAL_CONFIG` to put it elsewhere):

```json
{
  "pushover_secrets_file": "/home/<compte>/.config/agent-factory/pushover.json",
  "heartbeat_url_file": "/home/<compte>/.config/agent-factory/heartbeat-url",
  "public_url": "https://<machine>.<tailnet>.ts.net",
  "benjamin_login": "<login Tailscale>",
  "allowed_origin": "https://<machine>.<tailnet>.ts.net"
}
```

Every key is optional; an environment variable of the same meaning
(`COCKPIT_PUSHOVER_SECRETS_FILE`, …) wins. Absent or malformed, the file is
ignored: no push, no ping, read-only. A test never sees the live one: each
gives the process its own pid file, so its own (absent) settings file.

## Stop zone, read-only, and access zone (af-mjfvwx, slice 7a)

Intent (Benjamin, his words, 2026-10-06): « ok pour les deux temps, ok
tailscale ». Mechanism (agent interpretation): the Clean stop goes in two
steps. **7a, this one: nothing in the cockpit can stop the factory.** 7b —
suspending, resuming, the button in « mode essai » and his real trial —
waits for his word, at a time no delivery is running. It does NOT mean the
stop path is delivered.

What was found: `stop/driver.py` (T23/T24) had only ever run against a
Python object, and the shape it expects is not the one gc serves.

- `stop/gc_city.py` `GcCityReader` gives the driver that shape from gc's
  real `/v0/city/<city>/status` and `/sessions` (an agent counts as work in
  flight while it is `running` with an `active_bead`). Its `suspend`,
  `resume` and `force_stop_sessions` raise `StopUnavailable`. Which of gc's
  `session/<id>/stop|kill|suspend` keeps the work assigned (« arrêt forcé »)
  is not documented and has not been identified.
- `core/process.py` runs the driver (state kept in
  `COCKPIT_STOP_STATE_FILE`, tick every 15 s) and reads the agents at work
  as the read model's `sessions` source. **No stop action is registered.**
- `GET /` shows « Arrêt propre de l'usine »: the state, the work a stop
  would wait for (ticket title, last sign of life — spec .81, .82), and
  « L'arrêt depuis le cockpit n'est pas encore disponible : il attend ton
  essai réel. » `ui/stop/render.py` renders the controls only with
  `enabled=True`, which nothing passes yet.
- The heartbeat pauses only while the driver's state is
  `arretee_proprement` (spec .88).
- The driver's own requests (« l'arrêt n'avance plus », « reprise avec
  écarts ») and the Tailscale key at J-14 enter « Ce qui t'attend » as
  `extra_requests` of `requests/assemble.py`.
- « Accès »: who may act (`benjamin_login`, else « Lecture seule ») and
  until when the Tailscale key is valid (`access/tailscale.py`, read hourly
  as the `tailscale` source). Tailscale is read only where
  `tailscale_bin` is set (local settings file, or `COCKPIT_TAILSCALE_BIN`).

`tests/cockpit-stop-access-test.py` covers this through HTTP, including
that every plausible stop action answers 404.

## Access on the VM: HTTPS, identity, procedure (I, af-cp4fzd)

Intent (Spec af-fgcw0d, user stories 61, 93 and 98, decision « Accès hôte
» : « Loopback, Tailscale Serve tailnet seul, HTTPS, identité autorisée,
POST/Origin/SameSite conservés. L'API superviseur reste non exposée. »).
Mechanism (agent interpretation):

- **A reader is the operator, or the host itself.** Behind Tailscale Serve
  every request carries `Tailscale-User-Login`. One that is not
  `benjamin_login` is refused, 403, before anything is read or served:
  pages, readings and POSTs alike (`ActionGuard.check_reader`). A request
  without that header did not come through Serve: it came from the host
  itself, the cockpit listening on loopback only.
- **Every POST a page sends carries the cockpit's Origin.** The Operator
  Actions keep their four checks; the other POSTs of a page,
  `/api/usine/reverifier` and `/api/health/recheck`, which write nothing,
  are refused without the cockpit's own Origin, or from another identity
  behind Serve (`ActionGuard.check_page_post`).
- **« Accès » gives the address** the cockpit is opened at from the PC and
  the iPhone (`public_url`, when it is an HTTPS one; « Adresse HTTPS non
  configurée » otherwise), and links to **the procedure of the VM
  settings**, `GET /usine/procedure` (`ui/access/procedure.py`): Pushover,
  the heartbeat (the check « Usine muette », period 5 min and grace 10 min,
  an alert within fifteen minutes) and the access through Tailscale Serve,
  each with the command of `bin/cockpit-setup-wizard` that writes it and
  whether it is in place on this host: a secret is « en place » only when
  the cockpit reads its file, read again each time the page opens; a path
  set whose file is absent or invalid is said so. The command of Serve
  names the ports of this host, the cockpit's and the supervisor's (the
  port of `COCKPIT_GC_BASE_URL`). It names paths, never what a secret file
  holds, and no Windows path.
- The health zone already says a missing secret file (« Notifications
  iPhone inactives : le fichier de secrets est absent ou invalide »),
  without its value.

The real proof -- the iPhone, a VM that falls silent live -- is a human
trial after Delivered (Spec af-fgcw0d, Testing Decisions 4).

## Project repositories: roadmap step, commits ahead (af-mjfvwx)

T19/T20 built `projects/roadmap.py` and `projects/promotion.py` against a
clone a test had made; nothing made the cockpit's clones or called them.
`projects/depots.py` does both, as the read model's `depots` source
(every `COCKPIT_DEPOTS_POLL_SECONDS`, 10 min):

- one clone per repository under `clones_dir`, made with
  `git clone --no-checkout` and only ever fetched — no file of a project
  is written anywhere, nothing is pushed (spec « lecture seule »);
- each project's current Roadmap Step, every step and the date of the
  last change of the roadmap, from `roadmap_path` on the default branch of
  its `knowledge_repo` (descriptor), and its release plan, `release.toml`
  beside it (E, af-8rbceu: read, absent or unreadable, with why);
- « <rig> : dev a N commits d'avance » for each rig with a
  `promotion_branch`, from the rig's repository (`config/projects/<rig>.toml`,
  `repo`).

One project's roadmap being unreadable (its structured roadmap not written
yet) shows « Roadmap inconnue » for that project only. With every
repository unreachable the source is unknown and the headline says so.

**Off by default.** No repository is cloned or fetched unless a clones
directory is named: `clones_dir` in the local settings file, or
`COCKPIT_CLONES_DIR`. `COCKPIT_REPO_URL_TEMPLATE` (default
`https://github.com/%s.git`) lets a test point at throwaway local
repositories; git's own credentials are used, the cockpit holds no token.

Health zone (`projects/anomalies.py` `health_lines`, spec .47, .48): a
closed chantier with a ticket not merged; a roadmap step marked done while
a chantier that targets it is still open; a chantier targeting a step
still to do.

Not wired: « rituel dû » — the status command of a project's rituals is a
script of its repository, which the cockpit would have to run from a
checkout; that is a decision of its own.

`tests/cockpit-depots-test.py` covers this through HTTP against real git
repositories made on the spot.

## Promu (af-mjfvwx)

T20 built the git question (`promotion.compute_promu`) and the stage
computation that takes its answers; nothing asked the question for the
real convoys, so an accepted chantier counted as finished for every
project. `projects/promu.py` asks it inside the `projets` read: for each
accepted convoy, the merge commits its tickets recorded
(`gc.merge_commit`), checked against the promotion branch of the rig each
ticket went to (`gc.dispatch_rig`), in the clones the `depots` source
keeps fetched. It neither clones nor fetches.

| What the clone says | Chantier | « Ce qui t'attend » |
|---|---|---|
| every merge commit is on the promotion branch | Promu, in the project's history | — |
| at least one is not | Accepté : en attente de promotion, « à toi de jouer » | « … est accepté, pas encore promu. » (Quand tu veux) |
| cannot tell (no clones directory, clone not made yet, commit unknown to the clone, no merge commit recorded) | Accepté : promotion inconnue | — |

Unknown never asks anything of Benjamin (spec .62). A convoy none of whose
tickets went to a rig with a promotion branch is untouched: Accepté is its
last stage (spec .41).

Limit: a commit counts as promoted when it is an ancestor of the promotion
branch. A promotion made by squashing `dev` into `main` leaves the merge
commits unreachable; such a chantier stays « en attente de promotion ».

## Work in flight, as the factory records it (af-mjfvwx)

Slice 7a read « which agent is on which ticket » from `active_bead` in
gc's session list, and its fake supplied that field. The real list does
not: on the live host a worker delivering a ticket had none, so the stop
zone said « Aucun travail en vol » over a worker at work. The ticket is
what says it — an `in_progress` bead carries `gc.session_id` and
`gc.session_name`. `stop/gc_city.py` now joins the running sessions with
the tickets the read model holds (`held_work`); with the tickets not read
the work in flight is unknown, never empty. The driver's « photo » names
the holder the same way.

This is also why the write side of the Clean stop cannot be built from
documentation alone: what gc's session list shows while a city is
suspended, and after it resumes, has to be observed on a real suspension
before a fake can answer like it.

## Isolated launch: the cockpit at a commit, on a named dataset (T01R2 af-6a98ip, T01R4 af-u2fa7b; Factory tooling since af-wv3qu2)

Spec af-2zseit, user story 126 and Implementation Decision 5: an author, the
Evaluator and the Acceptance Session launch the cockpit of the commit they
judge, on synthetic data, without touching the city in service. The
Factory's profile (`config/project-descriptors/agent-factory.json`, block
`launch`, `docs/PROJECT_PLANNING_PROFILE.md`) declares how; nothing is typed
by hand.

Intent (Benjamin, his words, 2026-10-15 01:43 Paris): « Pas de T01R5 tant
que l'évaluation n'est pas limitée aux datasets du ticket et que les outils
d'usine ne sont pas sortis de T01. »
Mechanism (agent interpretation, af-wv3qu2): what the live root runs or
reads to launch and judge the cockpit -- the launcher, the profile and its
`launch` block, the recipe `bin/cockpit-isolated`, `lib/synthetic_city.py`,
the datasets, the fake supervisor it starts, the regression command -- is
Factory tooling on `main`, delivered by Factory maintenance. A cockpit
ticket carries the cockpit's code and its criterion tests only, and judges
them with the tooling of `main`; it no longer establishes the launch recipe.

```bash
./bin/project-launch start config/project-descriptors/agent-factory.json \
    --commit <sha> --dataset home-content --state-file /tmp/cockpit-launch.json
curl -s "$(jq -r .address /tmp/cockpit-launch.json)/api/status" | jq '.gc.value.city'   # "home-content"
./bin/project-launch stop --state-file /tmp/cockpit-launch.json
```

`bin/project-launch` checks the commit out into a clean copy, picks a free
port of 127.0.0.1 and runs the recipe there: `bin/cockpit-isolated --port
<port> --dataset <file>`, which becomes the real `bin/cockpit run` of that
copy. What it gives the cockpit to read:

| Source | In the isolated launch |
|---|---|
| supervisor | a synthetic one, `tests/fixtures/cockpit/core/fake_gc.py`, the fake `tests/cockpit-fake-gc-contract-test.py` holds to the installed supervisor; what it answers is what the dataset says (below). It takes the two writes of a clean stop the installed supervisor publishes (`/openapi.json`): `PATCH /v0/city/<city>` `{"suspended": true|false}` and `POST /v0/city/<city>/session/<id>/stop`, each answered `{"status": "ok"}`, and keeps every write it receives (`writes`), any other one answered 404 (af-npz9v1.21). `bin/cockpit-isolated` makes it answer too what the installed one keeps of each session the dataset says (`GET /v0/city/<city>/session/<id>`, the session as listed; `…/transcript?format=raw`, `{"id", "format": "raw", "messages"}`; a 404 for a session it keeps nothing of; `GET /v0/city/<city>/events?type=session.woke` and `session.stopped`, when it woke and stopped each one, the latest first), and send the sessions the dataset dispatches once the cockpit is up |
| clean stop | its state starts empty, in the home of the launch (`COCKPIT_STOP_STATE_FILE`), read every second. A dataset that says `"host_restarted_during_stop": true` starts it as a host restarted during a stop leaves it: a stop asked ten minutes before the launch, the tickets of the tracker of the launch as its photo. The driver then reads the supervisor: unsuspended, as after a reboot, « Arrêt interrompu » with the tickets whose assignment changed; still suspended, the stop goes on. Thirty minutes without progress are not simulated here: the driver measures them on the cockpit's clock (af-npz9v1.21) |
| tracker | `tests/fixtures/cockpit/synthetic-city/bd`, which answers the beads written for this launch from the dataset as `tests/fixtures/cockpit/requests/fake-bd` does -- hiding the closed ones from a plain `list` as `bd` does --, and writes what the doors and the gestures write there (`update`, `create`, `show`), in the home of the launch only |
| declared projects | one descriptor per project the dataset names, written for this launch; no file of the repository |
| doors that change the Factory (`gc order run`, escalation door, proposal door, loop guard, `bin/order-pause`) | the real doors of the commit, run on the tracker of the launch through a synthetic `gc` (`tests/fixtures/cockpit/synthetic-city/gc`: `gc bd` is that tracker; a mail, the waking of a session, the run of an order are taken and change nothing else); the cockpit gives up on a door after 5 s (`COCKPIT_ACTION_TIMEOUT_SECONDS`). A dataset may say how a door answers (`doors`: `proposal-door`, `escalation-door`, `loop-guard`, `order-pause`, `provider-failover`, `factory-maintain`, `operator-config` or `gc`, each `expires` -- it never answers, and writes nothing -- or `records-then-expires` -- it writes its record, then never answers); `bin/cockpit-isolated` refuses any other |
| settings and upkeep of the Factory (G2, af-npz9v1.20) | the real doors of the commit, each on what the launch holds: `provider-failover` (`COCKPIT_PROVIDER_FAILOVER_BIN`) works in the Factory tree of the launch (`$HOME/factory`, the page Usine's `COCKPIT_FACTORY_ROOT`: every file of the commit by a link, but `city.provider.toml` and `.gc/provider-state.json`, copied when the commit holds them), so a setting is read back where it was written; it reads no tmux session, and its reload is taken by the synthetic `gc`; `factory-maintain` (`COCKPIT_FACTORY_MAINTAIN_BIN`) works on throwaway Git repositories of the launch -- a clone of a bare origin (its `FACTORY_ROOT`) with a branch merged and pushed (`merged`) and one not pushed (`unpushed`), and under `$HOME/.local/share/agent-factory-runtime-worktrees` a worktree merged and pushed (`af-merged`, the candidate) and three it keeps: a local change (`af-modified`), a commit not pushed (`af-unpushed`, escalated on the tracker of the launch), work under way (`af-active`) --, never on the copy of the commit, whose refs are those of the repository it comes from; `gc` is the synthetic one and `gh` answers nothing, so no branch is proved merged by GitHub; `operator-config` (`COCKPIT_OPERATOR_CONFIG_BIN`) reads config/operator.toml of the commit |
| silence of the main sources | said « Usine muette » after 20 s (`COCKPIT_SILENCE_ALERT_SECONDS`): a state that falls silent (home-stale, home-offline) is first seen as it is drawn |
| local settings, secrets, notifications, heartbeat, project clones, Tailscale | none: a temporary HOME and no local settings file |
| a heartbeat (I, af-cp4fzd) | a dataset that says `"heartbeat": {"ping_url": "<http(s) address>", "interval_seconds": <n>}` gives the cockpit that address as its heartbeat secret, written in a private file of the temporary HOME (`COCKPIT_HEARTBEAT_URL_FILE`), at that pace (`COCKPIT_HEARTBEAT_INTERVAL_SECONDS`, the five minutes of service), ticked four times as often; anything else is refused |
| Tailscale Serve in front of the cockpit | a dataset that says `"https_identity_proxy": true` puts a synthetic identity proxy in front of it (`tests/fixtures/cockpit/synthetic-city/identity_proxy.py`, af-npz9v1.22): HTTPS on 127.0.0.1 with a certificate made for the launch, its address and the authority to trust in the cockpit's environment (`COCKPIT_TRIAL_HTTPS_URL`, `COCKPIT_TRIAL_HTTPS_CA`), its origin and the address « Accès » gives the cockpit's own (`COCKPIT_ALLOWED_ORIGIN`, `COCKPIT_PUBLIC_URL`). Who connects is said in `X-Synthetic-Tailnet-Login`: without it, 403 (not on the tailnet), the refusal naming that header (I, af-cp4fzd); with it, the request goes to the cockpit alone with `Tailscale-User-Login` and `Tailscale-User-Name` set from it, every `Tailscale-User-*` the client sent removed. Benjamin's login is `synthetic@example.ts.net` (`COCKPIT_BENJAMIN_LOGIN`). Nothing of the tailnet is used |

`home-gestes` carries such a tracker: a proposal, a session the loop guard
paused, a question and the pause of the order `convoy-advance` as
`bin/order-pause` records it, with the escalation door that expires. On it the
gestures of « Ce qui t’attend » are confirmed and read back at their source,
and an answer to the question expires (B, af-4uzgzm, then BR, af-eyc5ah: its demonstration line;
for Benjamin, « Le jeu home-gestes » below says it in French).

Le jeu `home-gestes` (pour Benjamin) : un suivi des tickets tel que les
portes l’écrivent — une proposition, une session mise en pause par l’usine,
une question et l’ordre `convoy-advance` mis en pause —, la porte des
questions ne répondant jamais. On y refuse une proposition avec sa raison,
on relance la session et l’ordre, et une réponse à la question expire, puis
la source est relue.

No controller and no tracker is started. A dataset that is not marked
`"synthetic": true`, carries no `generated_at`, names no state, or whose
content the rules below cannot read, is refused before anything starts: the
launch fails and leaves no process.

The process the launcher holds is the cockpit itself, so `stop` ends it by
its own clean stop. The synthetic supervisor runs beside it and ends when
the cockpit does, whatever ended it; it removes the temporary HOME. Of the
environment of the launcher the cockpit keeps one variable, the mark
`bin/project-launch` gives its launch (`FACTORY_LAUNCH_ID`): the launcher
stops the processes that carry it, and the controller of an evaluation
attests the product by it -- the process that listens on the port must
carry it. Without it the Evaluator received « identité du produit lancé non
vérifiable » (af-u2fa7b, Ticket Evaluation at 5a2e6fb);
`tests/cockpit-isolated-recipe-test.py` holds it.

**State from the dataset.** `lib/synthetic_city.py` (`from_dataset`) is the
one place where a dataset becomes sources: it reads the content of the named
dataset and returns what the supervisor, the tracker and the declared
projects answer. Nothing is canned: a value a source answers is written in
the dataset, so a dataset edited at another commit is served as edited. The
cockpit reads those sources as it reads the real ones.

A Runs dataset carries `fixtures` (lanes, runs, jobs). A Panorama dataset
carries the text of one screen (`visible_text`), how the state is set
(`ui`) and, when the screen has parts that unfold, what each says open
(`folded`: its label, its lines; for an event of the journal, its title and the lines it holds folded), and, when it has a drawing, what its
marks say (`drawn`: its heading, its lines -- the titles of the points of a
chart), which the text of a page leaves out. Its screen is known by the first line of the page, and read in two
ways:

- what the cockpit has a record for is read into that record: a request, a
  project and its chantier, a ritual, an event of the journal;
- every other section of the screen is **kept as said**: one open bead per
  section, under its heading, labelled `said`, whose description is the
  lines of the section in their order. The cockpit has no source yet for
  the measures of the machine, the connections, the configuration of the
  roles, the steps of a stop, the clean-up, the indicators or the analyses:
  the tracker holds what the
  dataset says of each until the ticket of that screen reads it into records
  of its own.

| The dataset says | The sources answer | Seen at |
|---|---|---|
| the state it is: `ui.id` (Panorama), `state` (Runs) | the supervisor's city bears that name | `GET /api/status`, `gc.value.city` |
| « Vue d’ensemble »: « Décisions à prendre N », then N lines under « Ce qui t’attend », each with « projet · nature » | one open bead per line that asks the operator (title, project, nature, the fixed time of the dataset) | `beads.value`; `GET /api/requests` |
| « Vue d’ensemble »: the dossier open under those lines (« projet · sujet », its title, what it shows), and the state of the result when `ui.state` names one (`ready`, `dossier`, `outdated`, `outage`, `accepted`, `merging`, `merged`, `abandoned`, `findings`, `returned`, `repairing`, `conflict`; none is a result to judge), and what the result says of itself (`result`: its commits, the times of its records, the words of the answer, the reason of an abandon -- required for `abandoned` -- unsaid, those of the reference) | the records the D01 commands write on the convoy of its chantier (A1): the new-flow mark, the result delivered, its dossier, the request of the acceptance and, by state, the answer, the promotion, the closing; the request of its project the page lists becomes the convoy's while the result waits for a judgement, and is gone once answered; the title of its Spec is what the dossier first says; the page of its dossier, one rubric per part that unfolds (« Ce qui reste à vérifier » as « Ce qui n'a PAS été vérifié »), its lines in `folded`, written in the home of the launch (`SyntheticCity.files`) -- the parts that open and the bar are the cockpit's own. `request` and `confirmation` open a decision: their dossier stays one open bead `synthetic-dossier` | `beads.value`; `GET /` |
| a tracker the commands of the flow wrote (`tracker`: `{"beads": {id: bead}}`, as the fake `gc` of `tests/fixtures/convoy-state` holds it), with `ui.id`; the descriptors of its projects (`projects`, optional) and where their knowledge repositories are (`repos`, optional: `{knowledge_repo: absolute path of a Git repository on this host}`) | its beads, as they are; each descriptor declared as it is, and one project per other `gc.project_id` the beads name, under that key; each knowledge repository read through a link to it in the home of the launch | `beads.value`; `depots.value`; `GET /`; `GET /projet/<key>` |
| « Vue d’ensemble »: the cards under « Projets » (name, « chantier · étape », then the figures of the card) | one declared project per name; one open chantier per project, under its title, whose description is the stage and the other lines of the card, and whose `gc.project_card` is the stage, the figures and, last, the line of the release | `projets.value.projects`; `GET /api/projects`; `beads.value`; `GET /` |
| « Vue d’ensemble »: the four indicators | one bead kept as said per indicator (value, period) | `beads.value` |
| a drawing of the screen: `drawn` under « Activité sur 7 jours », one line a day and a series | one bead kept as said under that heading, whose description is those lines | `beads.value`; `GET /` |
| « Vue d’ensemble »: `runs`, the cards under « Derniers runs » (workflow, status and its tone, title, step, start, elapsed seconds, lanes with the start and end of each job) | one bead `synthetic-run-card-N` per card, under the title of its run, whose `gc.run_card` is the card | `beads.value`; `GET /` |
| the page of a project (« ← Projets »): its name, what is said above the first section; « CHANTIER ACTUEL »; « Derniers changements »; « Prochaine release » and « PROCHAIN JALON » (a target, its gains, what remains, its decisions, its milestone, its estimate -- unavailable and why, or a range and its conditions), with what they show folded (`release`: the proof of each gain by its title, each change of the target, and for a range what it rests on: `comparables`, `hypotheses`, `computed_at`); « ROADMAP » (a heading, then each step and its status) | the project is declared; one bead under its name (purpose, stage, indicators); its open chantier; « Derniers changements » kept as said; its knowledge repository `synthetic/<key>`, a Git repository of the launch committed at the fixed time of the dataset, holding `roadmap.toml` and, when the page shows a target, `release.toml` (`lib/cockpit/projects/release.py`) | `projets.value.projects`, `GET /projet/<key>`; `beads.value`; `depots.value` |
| « Journal »: each event, « HH:MM (Paris) · projet · nature » or « HH:MM (Paris) · source », under « Aujourd’hui » or « Hier », its title and what follows | one bead of type `event` per event, as `bd create --type event` writes it: its title, its nature or source as `event_kind`, as label and as `gc.journal_event`, its project (declared), `created_at` the day of the dataset or the day before at that time, its line « Voir … » as `gc.journal_link`, the other lines as its description (the labels « Détail et source », « Événement brut » and the note under the logs are the page's); what `folded` says under its title as `gc.journal_folded` | `beads.value`; `projets.value.projects`; `GET /api/journal` `entries`: one entry per event, its title as `quoi`, its `created_at` as `quand`, its nature or source as `voie`, newest first (`lib/cockpit/ui/journal/entries.py`, T01R6 af-ltchro) |
| « Usine »: « Machine d’exécution », « Connexions », « Fournisseurs et accès API », « Agents dans le workflow », « Auteur livraison », « Autres rôles », « Suspension, reprise et arrêt », « Nettoyer les espaces inutilisés », « Ressources et libellés longs » | one bead kept as said per section | `beads.value` |
| a suspended Factory: `ui.setup` sets `shutdownState='suspended'` | a suspended city | `gc.value.suspended` is true |
| « Rituels »: each ritual (a line in capitals says how it is launched, then its title) | one bead per ritual under its title: how it is launched, what it is for, when it last ran | `beads.value` |
| the page of a ritual (« ← Rituels », its title, « projet · … ») | one bead under the title of the ritual, its project declared; its steps and what the step it is at shows | `beads.value` |
| « Analyses »: « Résultats fusionnés » or « Où passe le temps ? »; a merged result (« projet · hier ») | one bead kept as said for the view; the project of each merged result is declared | `beads.value`; `projets.value.projects` |
| nothing read yet: `ui.state` is `loading` | a supervisor that never answers, and a tracker whose read never ends (the cockpit waits a day for it, `COCKPIT_BEADS_READ_TIMEOUT_SECONDS` and `COCKPIT_JOURNAL_READ_TIMEOUT_SECONDS`) | every source `unknown`, without value, `beads.failed_at` empty; `GET /` says it is reading, however late it is looked at |
| nothing readable: `ui.state` is `error` | a supervisor that never answers, and a tracker whose read fails | every source `unknown`, without value, `beads.failed_at` set; `GET /` says the view is unavailable as soon as the first read failed |
| a reading that is no longer current: `ui.state` is `stale` or `offline`, or `ui.stale` is true (Runs) | a supervisor that is read once, then answers no more | `gc.freshness` and `sessions.freshness` leave `fresh` within seconds (a 2 s Validity window instead of 2 min), the last `gc.value` and `sessions.value` kept |
| the runs of a Runs state, each « Livraison D01 » or « Maintenance » | a workflow as the tracker holds one (C1, af-lzti7w): a « Livraison D01 » is a convoy carrying the new-flow mark, under the title of the run, written by `benjamin` for the project `agent-factory` (the datasets name none), its ticket (same `gc.graph_digest`; `gc.flow.merge` when the run says « Fusionné », `gc.flow.gate.withdrawn` when « Abandonné »), the workflow root `mol-ticket-author` run on an input convoy that tracks the ticket, and, when an agent of the run is a « Relect… » or an « Évaluat… », the workflow root `mol-code-review` or `mol-ticket-evaluation` run on an input convoy that tracks the bead the dispatch door writes to launch it (`gc.dispatched_via`, its description naming the convoy and the ticket); a « Maintenance » is a workflow root `mol-do-work` run on the work Benjamin asked for, under the title of the run; closed at the end of the run, open while it has none; the day of `generated_at` at the run's `started` (Paris) is its start | `runs.value`; `GET /runs` |
| the jobs of a run | one step per job, of the workflow root of its agent's role (the author's for Benjamin's and the code's), under its name, from its start to its end (open without one): a job of the lane `human` a plain step routed to `benjamin`, of the lane `code` a `check` (`gc.outcome` pass once closed), of an agent lane a `ralph` whose closing runs a check (`gc.check_mode`), claimed by an attempt of the session of that agent (`gc.logical_bead_id`, `gc.claimed_at`, `gc.outcome` pass once closed); its prompt as description, its result as close reason | `runs.value`; `GET /runs/run`, `GET /runs/job` |
| the agent lanes | one session per job of an agent (`synthetic-session-<lane>-<run>-<job>`): its `agent_name` the name of the lane, its `template` and `provider` the two halves of its role (« Relectrice · Claude »), running on the open job it holds | `sessions.value.agents`, `sessions.value.sessions`, `gc.value.agents_running` |
| the sessions a job says (`sessions`: each its `name`, its `start` and `end` from the trigger, and as the supervisor lists it its `provider`, `model`, `effort`, `permission_mode`, `context_pct`, `context_window`, `work_dir`; its `transcript`, records in the provider's own format) (C2a, af-k2rbw1) | in place of the one session of the job: each listed by the supervisor as it ran it, created at its start, its effort and permission mode under `options`, working the attempt of the job (`active_bead`) while it runs only, as the installed supervisor lists it; its waking (at its start), the attempt it took (`execution.step_started`, at the start of the job) and its stop (at its `end`; none without one) in the supervisor's log; the attempt claimed at the start of the job under the name of the last (gc keeps the session that took over); what its provider recorded served as its transcript; an empty list, a job no session is recorded for (no attempt) | the trace of the sessions; `GET /runs/job` |
| a session a job says sent once the cockpit is up (`dispatched`: `after_seconds` from the launch, `running_seconds`, `recorded_while_running`) | nothing of it until then, as for a ticket not yet dispatched; then its waking in the log, listed at work for `running_seconds` with only its first `recorded_while_running` records served, then its stop in the log, all its records served, listed no more (the installed supervisor lists only the sessions it runs) -- with `running_seconds` 0, a session that woke and stopped between two readings | the collection at the waking and stop of the sessions |
| where the cockpit keeps its trace of the sessions (`session_trace`, an absolute path) | `COCKPIT_TRACE_FILE`; else in the home of the launch, removed with it | the projection a case reads, and keeps from one launch to the next |
| what the flow declared for each role of a run (`declared`: `{role: {agent, provider, model, at}}`) | written on its ticket as the flow writes it (`gc.flow.models`) | the configuration declared in `GET /runs/job` |
| what a Runs state selects: `ui.filter`, `ui.run`, `ui.selected_job`, `ui.selected_event`, `ui.detail` | the filter, the run, the job, the event and the state of the detail (the sections it opens, the prompts it shows raw) a page opens when its address names none (`COCKPIT_RUNS_VIEW`) | `GET /runs`, `GET /runs/run`, `GET /runs/job` |
| the moment a Runs state shows (the latest `started` + `elapsed` of an open run) | the clock of the cockpit starts there and runs on (`COCKPIT_CLOCK_START`) | the horizon of the open runs, `read_at` |

The key of a project the dataset only names is its name without accents, in
lower case, with dashes between words (« Notes » is `notes`). A screen no
rule reads, a page with « Décisions à prendre » whose list does not hold
that many lines, a project card without its chantier, an event or a ritual
without a title, a `ui.state` that names the state of a result on a page
that opens no dossier, or a Runs state whose fixtures cannot be read, is
refused, as is a `folded` that is not a label and its lines for each part
or that names a part the dossier does not unfold, and a `drawn` that names a
heading the screen does not show. Each refusal, and that of
a file that is no dataset at all, is proven once by
`tests/cockpit-isolated-recipe-test.py`, at the recipe.

What is left out, and why:

- the theme and the width a state is looked at with (`ui.theme`,
  `ui.width`): they belong to the browser that looks, no source answers
  them. `home-light` and `home-narrow` are served the state of
  `home-content`; the same holds for each screen;
- in what a Runs state selects, an event (`ui.selected_event`) that is
  not among the events the job holds: the fixtures hold of a job only its
  start, its end, the session that claimed it and the check its closing
  ran, the tool calls the prototype draws are not collected yet (C2b); the
  Runs datasets carry the same fixtures, byte for byte -- but for the
  sessions and the declarations of the run « Recherche dans les notes »
  in the five states of the trace (below) -- and are served the same
  workflows;
- the lines of a page above its first section (title, subtitle, tabs, the
  banner of a reading that is no longer current, « Rien à afficher ici »)
  and the sections that hold links only (« Ressources du projet »);
  « Activité sur 7 jours » holds only what its `drawn` says, « Derniers
  runs » only what its `runs` says;

The criterion tests of the cockpit (its T01 ticket) launch the 95 states
and hold the list of those that are served the same tracker and projects:
nine groups, each for one of the reasons above or because nothing is shown
or read (`*-empty`, `*-loading`, `*-error`); the 41 other states are served
a state of their own. The stage of a chantier and
the state of a result are served as said, not as the records of the
Delivery Workflow: those are produced by its public commands (Spec
af-2zseit, Testing Decisions 2), below.
The ticket that delivers a screen reads its sections into records and
changes the lines of the table above.

**Datasets.** One per state of the seven Validated Prototypes of the Spec:
the 76 Panorama states and the 19 Runs states, under
`config/cockpit-datasets/<state>.json`. Each file is the dataset of
the frozen prototype, byte for byte (Panorama at `632deea`, Runs at
`d8cb462`, in the private prototype repository), but for the sessions
and declarations of « Recherche dans les notes » in `job-sessions`,
`job-configuration`, `job-system-prompt`, `job-user-prompt-rendered` and
`job-user-prompt-raw` (C2a, af-k2rbw1: what the prototype drew as example
values, written as the sources the cockpit reads), for the `folded` of
the `home-*` states that open a result: the parts of « Ce qui t’attend »
that unfold, copied from the frozen state drawn (`states/<state>.html`),
since the prototype's dataset keeps only the text of the page (T02R,
af-vbb4ol: « Compte rendu long » and its eighteen findings), and for the
`drawn` of the seven `home-*` states that show the activity chart: the
titles of its 21 points, copied from the frozen state drawn (T02R2,
af-r2c0tx), and for the `runs` of those seven states: the three cards of
the frame « Derniers runs », copied from the frozen state drawn, a bar's
place and width given back in seconds of its run (T02R2, after its code
review). A state is launched with
`--dataset <state>`.

**Screens.** `launch.screens` gives each screen of the Spec its address and
its states, which is what `bin/prototype-fidelity` compares:

| Screen (`name`) | Address | States |
|---|---|---|
| `vue-ensemble` | `/` | `home-*`, `result-*` (24) |
| `projets` | `/projet/notes` | `projects-*`, `release-expanded`, `release-estimate`, `project-missing` (6) |
| `journal` | `/journal` | `journal-*` (10) |
| `usine` | `/usine` | `health-*`, `factory-*` (18) |
| `rituels` | `/rituels` | `rituals-*`, `ritual-*`, `release-confirm`, `release-review`, `release-report`, `release-saved` (14) |
| `analyses` | `/analyses` | `analysis-*` (4) |
| `runs-liste` | `/runs` | `runs-*` (3) |
| `run-frise` | `/runs/run` | `run-*` (5) |
| `job-detail` | `/runs/job` | `job-*` (11) |

Beside the states of the screens, the profile declares `journal-demonstration`:
the useful events of `journal-content` and the technical logs of
`journal-logs` on one launch, so that the demonstration line of the Journal
Fold (F, af-njwz8v) is observed on one cockpit; it is no state of a reference.

`/`, `/journal` and `/projet/notes` (the page of the project the six states
of that screen are about) are served today; the other addresses are declared
for the tickets that deliver those screens, and answer 404 until then.

**The public commands of the Delivery Workflow.** Beside its `http` entry
points the profile declares, as entry points of kind `command` (`path` the
command, `method` its subcommand), the commands that produce the records
the cockpit reads of a judged result: `bin/acceptance-session open` and
`close`, `bin/owner-answer verdict` and `record`, `bin/outcome-promote run`.
What the cockpit shows of those records (Testing Decisions 2) is proven by
the cockpit's tickets, not here.

**Criterion tests.** The profile declares two seams under
`tests/cockpit-criteria/`: `http/` (black box: the test reaches the launched
cockpit at `PRODUCT_ADDRESS` and nothing else) and `commands/` (import rule:
the test runs in the tree of the product and goes through `bin/project-launch`,
`bin/project-planning-profile`, `bin/prototype-conformance`,
`bin/acceptance-session`, `bin/owner-answer` or `bin/outcome-promote`). The
test command is the JUnit harness of the Delivery Fixture City
(`tests/fixtures/delivery-fixture-city/tests/harness.py`); it is a frozen
harness path, with the two decors the recipe reads (the fake supervisor and
the fake tracker). `tests/cockpit-criteria/regression.py` is the regression
command: every `tests/cockpit-*-test.py` CI runs, plus the tests of the
launcher and of the profile. The criterion tests themselves, and the CI
file that runs those of `commands/`, come with the cockpit's tickets.

Limits.

- What the recipe reads under `tests/` (the fake supervisor
  `tests/fixtures/cockpit/core/fake_gc.py` and the fake tracker
  `tests/fixtures/cockpit/requests/fake-bd`, both frozen harness paths)
  cannot be changed by a ticket once its tests are frozen: `bin/tdd-step`
  runs the criterion tests of the `commands/` seam in the tree of the
  product with the whole `tests/` directory of the freeze commit put in its
  place. This is why the datasets are under `config/`, and why what a
  dataset says goes through what those two fakes already answer.
- The tools of the flow read the profile, and run `bin/project-launch`, in
  the Factory root they run from, not in the branch of the ticket. This is
  why the launch tooling is on `main` (af-wv3qu2): a change to it goes
  through Factory maintenance, never through a cockpit ticket. The recipe
  itself (`bin/cockpit-isolated`, `lib/synthetic_city.py`, the fakes) runs
  from the copy of the commit judged, so a ticket branched from `main`
  carries the same.
- The Validated Prototypes are private: their commits exist in the
  repository of the delivering host only; a test that reads them is left
  out where they cannot be read, CI included.
- `tests/cockpit-criteria/http/` holds no test yet: the first ticket that
  writes one adds the run that launches the product for it.

## « Runs »: one run per complete workflow (C1, af-lzti7w)

Intent (Benjamin, his words, 2026-10-12): « voir les workflows qui sont
lancés et qui ont été lancés » ; « Oui, un run par workflow complet » ;
« une lane par agent avec le contexte de sa dernière session, l’historique
des sessions dans les jobs, et les traits colorés par type d’événement avec
le détail au clic ».
Mechanism (agent interpretation): the Prototype Fold of the Runs reference
(Spec af-fgcw0d, ticket C1) on the Runs page built directly on 2026-10-19;
the collection of sessions, prompts, events and usage is C2a and C2b's.

`GET /runs` lists the runs (`?filtre=tous|en-cours|termines`), `GET
/runs/run?id=<run>` draws one, `GET /runs/job?run=<run>&job=<job>&event=<n>`
draws it with the detail of a job under its frise and one of its events
open -- in the address, so a reload keeps them. `lib/cockpit/runs/workflows.py`
reads a run from the facts the code already recorded:

| A run | Read from |
|---|---|
| a D01 delivery | a convoy carrying `gc.flow.mark` and the tickets of its graph (`gc.graph_digest`); its jobs are the steps of the workflow roots (`gc.kind=workflow`) whose input convoy (`gc.input_convoy_id`) tracks one of those tickets -- or tracks the bead `bin/dispatch-door` wrote to launch a code review, a Ticket Evaluation, a correction round or a resume (`gc.dispatched_via`), whose description names its `convoy:` and its `ticket:` --, and the facts of each ticket the flow launched (`gc.flow.tdd.*`, a question to Benjamin, the merge) as points |
| a delivery of the old flow | a ticket an agent was launched on (`gc.flow.models`) whose convoy carries no mark, read as `lib/cockpit/runs/derive.py` reads it |
| any other workflow | its root and its steps, under the title of the bead it was run on when the tracker holds it: « Maintenance » (`mol-do-work`), « Planification » (`mol-planning-*`, `mol-graph-review`), « Ancien flux » (`mol-polecat-*`), else « Workflow » |

A run says what triggered it and its project, on its card and above its
frise: a D01, « Graphe publié · Spec <spec> par <who wrote the convoy> » and
the convoy's `gc.project_id`; another workflow, the bead it was run on
(« <title> (<id>) par <its author> ») and the rig the work was dispatched
to (`gc.dispatch_rig`); a delivery of the old flow, « Lancement de
<ticket> » and its rig. What the tracker does not hold is said « non
enregistré ».

A job is a step (`gc.root_bead_id`: a plain step, which bears no `gc.kind`,
or one of kind ralph, retry, task or check; the specs, scopes, finalizers
and cleanups are the engine's plumbing): routed to `benjamin`, the lane
Humain; a check, the lane Code; else the lane of the agent whose session
claimed it -- the step's own `gc.session_name`, or that of its attempts
(`gc.logical_bead_id`) --, its `agent_name` as the supervisor lists it, so a
new session of the same agent keeps its lane and two agents of the same
role keep one each. Its start is its first claim, its end its closing; an
open job lasts up to now, and the clock moves only that horizon. Status:
« Fusionné » (a ticket merged), « Abandonné » (every ticket withdrawn),
« Terminé » (the root closed), « Ta décision » (a job of Benjamin open),
« En cours »; a run ended in a success is ticked « ✓ », one ended without
(« Abandonné », « Fermé » sans fusion) crossed « ✕ » and drawn muted. The
lanes Humain and Code are drawn even without a job. When a source the run
is drawn from -- its workflow beads (`runs`) or the supervisor's sessions
(`sessions`) -- is no longer current, the run says « Lecture périmée » with
the moment it was last observed.

The events of a job are what the tracker recorded of it: its start and its
end (« autre », grey), each session that claimed it, at its claim
(« session », purple), a check step run and its outcome, or the outcome of
the check each attempt's closing ran (`gc.check_mode`, `gc.outcome` passed
or refused: « contrôle », green). Tool calls are not collected yet (C2b):
no event is drawn turquoise. The detail of a job says, of each section that
has no source yet (controls, usage, outputs), that it is not collected; an
event opened says its text whole. Its configuration, sessions and prompts
are those of the trace of the sessions (below).

### The trace of the sessions (C2a, af-k2rbw1)

Intent (Benjamin, his words, 2026-10-12): « l’historique des sessions dans
les jobs ». Mechanism (agent interpretation): the sessions, the
configuration in effect and the prompts sent are collected from the
supervisor, which sends the sessions their work and records when it woke
and stopped each one, into a projection of the cockpit's own, since the
supervisor does not keep them for ever. The Factory has no point of its
own where a session is sent its prompts: gc wakes the session and sends
them.

At each reading of the sessions (`sessions`, every 15 s: no reading of its
own), the cockpit reads the supervisor's log of the sessions it woke and
stopped, and of the beads each took, since the last event it read (`GET
/v0/city/<city>/events?type=session.woke`, `session.stopped`,
`execution.step_started`: the bead its `subject`, the session its
`session_id`; on a first
reading, the latest 50 of each), and records in a private file
(`COCKPIT_TRACE_FILE`, by default `cockpit-session-trace.jsonl` beside its
pid file, 0600, appended only) each of those moments, then, of each session
listed or named by that log (`GET /v0/city/<city>/session/<id>`: the
supervisor keeps a session it stopped and no longer lists), its identity,
provider, model, effort and permission mode, context observed and its
window, work directory, creation, the bead it works while it runs (a
session kept once stopped says none: only the log says the bead of a
session past, 2026-10-28) -- and, the first time,
at most every minute while it runs, and once more when it stopped, what its
provider recorded (`GET
/v0/city/<city>/session/<id>/transcript?format=raw`): the system prompt
where the provider records it (Codex, `session_meta`; Claude Code does not:
it is said not collected), each user prompt as typed (Codex, `event_msg`
UserMessage; Claude Code, a `user` record of text), with its version
(`sha256:` and twelve digits of its exact text), and the names of the tools
it called. A session that woke and stopped between two readings is so
collected, and what a session was sent after it was last read. Nothing else
is read: what tools were given and printed, reasoning, environment, tokens.
A record already written is not written again -- another cockpit reading
the same log adds nothing --, a session that could not be read keeps its
moments out until it is, and a record of the provider older than the
session belongs to an earlier one its trace replays
(`lib/cockpit/runs/trace.py`). On the live host (2026-10-22, under load) a
first collection took 18 s for 40 sessions, the next ones 1.5 s.

The sessions of a job are those the tracker records (its claims) and those
the trace saw working it or one of its attempts, or the log says took one
(the tracker keeps the name of one session per bead), each from its claim -- or
its creation, for a session that took over -- to when the supervisor
stopped it; an end it did not record is said « non collecté » (« en
cours » for the last session of a job that runs). The detail
of an agent's job says, for the session chosen (by default the last;
`&session=<name>`): « Configuration effective » as observed, then
« Configuration déclarée » for the role of its workflow (`gc.flow.models`
on the ticket); « Sessions du job », each a link that shows its own
configuration and prompts, the one shown marked « Affichée »; « Prompts
envoyés », each rendered or raw
(`Rendu`, `Brut`), the raw text being the text sent. What nothing observed
is said « non collecté », never taken from the declaration or the job --
the mission of a session among them, which no source reports. The
lane of an agent says the context and model of its last session in the
run; a job of an agent no session is recorded for is drawn on the lane of
the one agent of its workflow, its detail saying that no session is
recorded. Sections open and prompts shown raw are kept in the address
(`&ouvert=…`, `&brut=…`). Tests:
`tests/cockpit-criteria/commands/runs-trace-*-test.py`.

The frise is drawn on a track of 720 px, scrolled in its box on a narrower
screen. A job is a box at its start, as wide as its time and at least as
wide as its name (wrapped beyond 240 px), its duration and its events need
-- each event a target of 24 × 24 px --, the bar at its top keeping its real
duration; two boxes of a lane that would overlap are drawn on two rows.
This corrects the reference, whose short jobs had their names cut and whose
event traits were 3 px wide (Spec af-fgcw0d, Testing Decisions 5, user
story 175).

The source `runs`
reads `bd list --all --limit 0 --has-metadata-key <key>` for `gc.kind`,
`gc.root_bead_id`, `gc.flow.mark`, `gc.synthetic`, `gc.flow.models` and
`gc.dispatched_via`, merged by id, on the journal's rhythm; the Vue d'ensemble, Projets, Journal,
Usine and Analyses still read the deliveries of tickets from it, as before
(`runs_from_beads`). The card of a run is `run_card`
(`lib/cockpit/ui/runs/page.py`), the one the overview is to reuse (K).
Tests: `tests/cockpit-criteria/commands/runs-destination-*-test.py` (the
`readable` ones: every Runs state, dark and light, at 1440 and 390 px,
held to the readability `problems` of `home_destination.py`),
`tests/cockpit-runs-test.py`.

## « Usine »: machine, connections, roles (G1, af-wrxrmg)

`GET /usine?role=<author|reviewer|evaluator>` (`lib/cockpit/ui/factory/page.py`),
the Prototype Fold of the reference « Usine, configuration et maintenance »
(Spec af-fgcw0d, user stories 63, 65, 160–162). Four sections, each shown
as it was **last checked** (`lib/cockpit/factory/checks.py`), with the time
of that check to the second and its own « Revérifier maintenant » button:

- « Machine d’exécution »: the machine the cockpit runs on (host, system,
  cores, time in service from `/proc/uptime`, load, memory, disk of the
  home), read when checked;
- « Connexions »: every source of the read model with its state, its
  latency -- how long its last complete read took, timed by its poller
  (`PollingSource`, the status read of `GcSsePoller`; `latency` in each row
  of the read model) -- and when it was read. Whether a source is still
  current is read now: one no longer current is greyed « Périmé · vu il y a
  … » with its last latency; one failing since its last reading (unknown,
  `cockpit.core.freshness`) is greyed « Inconnu — la source ne répond plus ·
  vu il y a … », without a latency; one never read is « inconnu — la source
  ne répond pas », never 0 and never a failure. The notifications say
  whether they are configured; their delivery is not measured, so they are
  never drawn as a connection verified;
- « Fournisseurs et accès API »: each pool of quota of
  `config/provider-policy.json`, the providers drawn on it, and what the
  provider failover observed of it in `.gc/provider-state.json` (read as
  `bin/provider-failover status` reads it: « Quota épuisé jusqu’à … »,
  « Quota bas », « En erreur », or « Aucune limite détectée », which
  measures no quota, for a pool the file records); « Aucun relevé du
  repli », greyed, for a pool the file holds nothing of; « Disponibilité non
  observée » where the host holds no such file. No key is shown;
- « Agents dans le workflow »: the roles as the Factory's files configure
  them (`lib/cockpit/factory/configuration.py`: `config/delivery-roles.json`,
  the chains of `config/provider-policy.json` -- the first provider is the
  one configured, the others its fallbacks --, the model and effort of each
  provider in `city.toml`, the ceilings and bounds of
  `config/delivery-flow.json`), drawn as the descending flow of delivery
  (deterministic controller, the steps each role runs, integration, the
  owner's judgment). A step is a link that opens the detail of its role:
  configuration first, then what is observed apart -- the provider in
  service from `city.provider.toml` when the host has one, the availability
  the failover observed of each provider of its chain (a provider disabled
  says it, with its reason), the sessions of that role at work -- greyed
  « périmé, vu il y a … » once the sessions are no longer current, and
  unknown, without a count, once their source fails. The bounds of the flow
  shown are its resumes, open planning exceptions, end rounds and
  correction rounds. The other
  targets of the policy are listed outside the flow. A file that cannot be
  read is named, nothing is guessed.

The Factory's files are read under `COCKPIT_FACTORY_ROOT` (default: the tree
the cockpit runs from).

`POST /api/usine/reverifier` (form `section=machine|connexions|fournisseurs|agents`,
`role=`) checks that section again -- the connections after every source was
read again now -- and only that one, then answers 303 back to the page; it
writes nothing. Viewing the page never checks a section again: a check older
than five minutes (`COCKPIT_VALIDITY_USINE_SECONDS`) is kept, greyed
« périmé, vu il y a … », until its « Revérifier maintenant ». Then come the health zone, and the panels « Suspension, reprise et
arrêt » (with the stop and access zones the home already had) and
« Nettoyer les espaces inutilisés », whose commands stay disabled until
their tickets wire them (G2, H); the role detail's « Configurer » too.
Nothing on the page is a value of the dataset: in an isolated launch the
machine and the configuration are those of the tree launched. Tests:
`tests/cockpit-factory-page-test.py`, and the criterion tests
`tests/cockpit-criteria/commands/factory-*-test.py`.

## « Projets » in Panorama (direct build, 2026-10-19; Prototype Fold E, af-8rbceu)

`GET /projets` (`lib/cockpit/ui/projects/panorama.py`): a card per declared
project -- what waits for Benjamin, the current chantier, open chantiers,
runs merged in 7 days and runs open (a run belongs to the project its
ticket was dispatched to, `gc.dispatch_rig`). The whole card is one link to
the page of the project, by a click or the keyboard; its accessible name
starts « Page projet » and says the line.

`GET /projet/<id>` is the Prototype Fold of the reference « Projet, release
et historique » (`lib/cockpit/ui/projects/fold.py`; Spec af-fgcw0d, stories
46, 103, 152 to 156): the way back, the name and state of the project,
three counts, then « Prochaine release », « Chantier actuel », « Roadmap »,
« Derniers changements » and « Ressources du projet », numbered with the
anchors of the reference; under them, the chantiers by stage, the work
outside a chantier and the historique the page already drew (A1 reads the
Outcome into them; E does not change that reader). The label of a section
the reference writes small (« CHANTIER ACTUEL », « ROADMAP ») is held in a
heading, so a navigation by headings reaches it; the label keeps the
element and the anchor of the reference. Each « Voir la preuve » is named
by its gain (« Voir la preuve : <gain> »).

- **Release plan (cadrage).** Read, never written (writing it is the ritual
  « Préparer la prochaine release »), from `release.toml` beside the
  structured roadmap in the knowledge repository of the project
  (`lib/cockpit/projects/release.py` holds the format): the revisable
  target, the gains verified each with its proof, the criteria that remain,
  the decisions open, deferred or included, the next milestone and how it
  is verified, the history of the target kept apart from the gains. A
  range is shown only conditional -- its conditions, its hypotheses, the
  comparable results it rests on, the date it was computed, and exactly the
  criteria that remain; otherwise « Estimation non disponible » and why. No
  global percentage, no date of delivery. A project without a release plan
  says « Cadrage et preuves non collectés. Aucun avancement déduit. » and
  where the plan lacks (the repository and the file, or that the project
  declares no knowledge repository).
- **Roadmap.** Every step of the structured roadmap, its status, the
  repository and file it comes from and the date of its last change. A step
  « En cours » whose chantier is closed (the Specs that target it, by
  `planning_run_target`, and the convoys published from them, by
  `gc.spec_id`, all closed), or one of whose results is merged (a convoy
  that records its promotion, or whose tickets all recorded the merge of
  their PR, `gc.merge_commit`; one PR merged among tickets still at work is
  a chantier under way), is flagged « Incohérent »
  (`roadmap.roadmap_rows`; the Specs that target a step are read open or
  closed, `source.read_targeting_beads`). A Spec closed without successor,
  its reason recorded, reaches the historique the same way.
- **Chantiers not read.** While the tracker is being read the page says so
  (« Lecture des chantiers en cours »), and « Lecture des chantiers
  impossible » when it fails; the counts are « — · inconnu », never 0, and
  no chantier is said absent. The release plan and the roadmap, read from
  the repository, are shown all the same. The page waits at most
  `FIRST_READING_WAIT_SECONDS` for the first reading of the projects and of
  their repositories.

Tests: `tests/cockpit-home-projects-test.py` (`GET /projets` and the page of
a project, through the running process), and the criterion tests of E
(`tests/cockpit-criteria/commands/projects-{release,roadmap,recette}-test.py`).

## « Journal » in Panorama (F, af-njwz8v: the Prototype Fold of the Journal reference)

`GET /journal` (`lib/cockpit/ui/journal/panorama.py`) follows the Journal
reference (prototypes/c01-complete/frozen-panorama-journal at 632deea) in its
ten states, at its own address, its parts carrying the reference's anchors.
Three tabs, each a button of a form sent by GET (no script):

- **Événements utiles** (`?vue=utiles`, the default): one timeline by day
  (Paris) of the requests answered or cleared -- each drawn as the journal
  always drew it (what, when, by whom, which way, details) --, the
  deliveries of the runs (launched, stopped, merged) with their link, and
  the events held for the journal whose nature is a category: each with
  its time, its project and its category, its title, its consequence (its
  description), its link (`gc.journal_link`: « Voir le projet » opens the
  page of its project, « Voir les connexions » `/usine`, « Voir le
  résultat » and « Voir les propositions » `/`) and, folded, its detail and
  its source (`gc.journal_folded`, a JSON list of lines). Categories
  `?categorie=tout|bugs|propositions|changements|decisions|evenements`
  (natures Bug, Proposition, Changement, Décision, Événement; the answered
  requests are Décisions or Propositions, the deliveries Changements, the
  cleared requests Événements). The former `?filtre=` still names its
  category. An event of a nature no rule knows keeps its place, said
  « Signal non reconnu venant de <project> » (or « d’une source inconnue »),
  its nature, title and words folded, unchanged, and is under « Tout » only.
  The notification sends follow, folded.
- **Logs techniques** (`?vue=logs`): the events of the technical sources
  (natures `ci`, `agents`, `delivery`/`livraison`, `connections`/`connexions`,
  `maintenance`, `notifications`), each with its time and source, its title,
  what it means and, folded, its raw event (`gc.journal_folded`), plus the
  events of an unknown nature under « Autres », « Événement non reconnu ».
  Filter `?source=tous|ci|agents|livraison|connexions|maintenance|notifications|autres`,
  search `?q=` (the title, the meaning, the source and the raw event, case
  ignored).
- **Sources disponibles** (`?vue=sources`): each source of the logs,
  « raccordée » when the factory declares it connected -- a bead whose
  `gc.journal_source` names it, read with the journal, also in `GET
  /api/journal` under `sources` -- or the cockpit read logs of it; a
  connected source that sent nothing yet stays « raccordée — aucun log
  reçu ». « absente » otherwise, « inconnue » while the journal is being
  read or cannot be.

Labels are fixed by the type of the event; no model reads or writes them.
Every text of an event is read through `cockpit.text.redact`: a secret (a
token of a known shape, the value of a field named as one) and a private
reasoning (`reasoning`, `thinking`) are replaced where they are written,
so neither a page nor `GET /api/journal` holds one. A field is `name=value`
or `name: value`, its name quoted or not (a JSON key); its value a quoted
text, an object or a list to its closing bracket, else the word that
follows, and an unquoted reasoning to the end of its line. Neither the
read nor the page calls a model: `tests/cockpit-journal-test.py` launches
the cockpit with every way out to one recorded (a proxy, the providers'
addresses, their commands) and sees none taken. A journal never read
says « Lecture en cours… », one whose read failed « Cette vue est
indisponible » (never an empty journal), and a journal read while it or the
supervisor no longer answers keeps its events under the notice « État actuel
inconnu · dernières données conservées. Actions indisponibles. ». Tests:
`tests/cockpit-journal-test.py` (through the running process), the
criterion tests `tests/cockpit-criteria/commands/journal-destination-*-test.py`.

## « Analyses » (direct build, 2026-10-19)

`GET /analyses?vue=resultats|delais|verifications|activite&periode=7|30`
(`lib/cockpit/ui/analyses/page.py`): runs merged per day and which;
median lead time from dispatch to merge and median wait for a decision;
code reviews (with or without blocking findings), evaluations and fidelity
measures per day; runs launched, stops and Benjamin's decisions per day.
Every number comes from the runs (now the 200 most recently updated; the
Runs page draws 48) and the journal; each view says its definition. GitHub
CI is not read yet. Test: `tests/cockpit-analyses-test.py`.

## « Rituels » (direct build, 2026-10-20)

`GET /rituels` (`lib/cockpit/ui/rituals/page.py`), carried over from T41's
fold (af-r4hrt7, commit 8ef15917, never merged) with only what has a real
source: the catalogue of the Spec (the next release's framing, the reviews
of incidents, architecture and quality / AI Slop, the diagnostic of the
Factory), each what it is for and how it is launched, and when it last ran
read at each view from the rituals file (`COCKPIT_RITUALS_FILE`, by default
`docs/rituals.toml`, the file `bin/rituals-status` reads): a ritual whose
id starts with a card's key (`architecture:factory`) gives that card its
last run, or that it is paused, why and when it resumes, and its threshold.
A card the file names nothing for says « non renseigné »; an unreadable
file, « inconnu ». Whether a ritual is due (merged PRs counted through
`gh`), launching a ritual and the pages of a ritual under way (T41's
`gc.ritual_operation`, which no door writes) are left out, not drawn with
example values. Test: `tests/cockpit-rituals-panorama-test.py`.
