# C01 "Cockpit V2" — decisions log (grilling with Benjamin)

Working log of the C01 Planning Run (SayMyName roadmap A7, reservation
`C01`). Times Europe/Paris. One session, four rounds (2026-09-29
afternoon, from 14:20), so a simple Planning Session (no Wayfinding map). Inputs in
this folder: `facts.md` (2026-09-29, read-only live facts). Cockpit V1 and
the old ntfy code in `legacy/` were read as evidence only (untrusted).

## Origin

- 2026-09-25 (SayMyName decision 6): « Je veux continuer à avoir un système
  de notifications ntfy. Mais son utilisation devra être revue en même temps
  que le cockpit ».
- 2026-09-25 (decision 11): ritual reminders become a Cockpit V2 / ntfy
  notification.
- 2026-09-28 (decision 18, A5): NEEDS BENJAMIN list and proposal count shown
  at operator session start as an interim, to move into the cockpit.
- 2026-09-29 (decision 23): « a, on lance le planning run C01 en /handoff »
  — C01 before B1; graph published only after A6 closes.

## Round 1 — 2026-09-29

Intent (Benjamin, his words): « Q1 ok, Q2 Il était trop bruyant et pas
fiable, il ne me disait pas clairement quoi faire, la plupart des sections
étaient obsolètes, il était pas comprehensible par moi du coup je demandais
directement à un agent, mais surtout le bruit et la fiabilité, Q3 a mais
j'aurais voulu qu'il soit un tableau de bord fiable aussi ... , Q4 ok, Q5 a:
mes horaires de nuit ne sont pas fixes donc A, et puis les notifs ne me
reveillent pas par défaut, ce sont mes reglages de telephone (mode silence
par exemple) qui determine ca et je fais ce que je veux, Q6 j'ai dis
qu'actuellement je passe toujours pas un agent mais c'est justement car je
n'ai rien pour faire sans agent, si on peut me permettre d'agir facilement
sans agent tout en gardant une trace alors c'est good, je dois pouvoir aussi
passer par un agent sans friction si je le veux, Q7 ok mais la base doit
etre agent agnostic mais je dois pouvoir y consulter l'avancée des projets
et comprendre ce dont j'ai besoin, donc le cockpit doit pouvoir me donner
des infos projets.. peut etre un fichier profile ou un truc du genre »

Mechanism (PO interpretation):
1. Q1 — proposals af-6675l (P13), af-elhn7 (P06), af-87f9u (P07), af-i3prh
   (A6) closed as covered by A6; af-75gtq stays open until A6's P22 proof;
   af-sqrri (duplicate notification bursts) and af-pgm3y (stale re-fires)
   become C01 requirements. Stale `[ci]` bead af-rqjsup closed.
2. Q2 — why Cockpit V1 failed (noise, unreliability, stale sections, no
   "what to do", needed an agent to translate) becomes C01's acceptance
   criteria.
3. Q3 — push first (the phone tells him when he is needed) AND a dashboard
   he can trust, on one screen.
4. Q4 — three levels: urgent / normal / not on the phone.
5. Q5 — no quiet hours in the Factory; his phone settings filter.
6. Q6 — simple actions without an agent, each leaving a trace; "continue
   with an agent" always one step away. Does NOT mean approving a Spec or a
   graph in one click.
7. Q7 — the cockpit shows project progress and what each project needs,
   without the Factory naming any project. « agent agnostic » read as: no
   dependency on one agent provider (Codex/Claude); project-agnosticism
   comes from SayMyName decision 5. Mechanism: a per-project manifest
   (his « fichier profile »).

## Round 2 — 2026-09-29

Intent (Benjamin): « Q8: OK Q9: B (ca n'empeche pas qu'on peut commencer
par le pc, sauf si on prefere un vertical slice qui contient le mobile, je
ne sais pas, je te laisse choisir) Q10: OK Q11: A Q12: ok Q13: ok Q14: ok
mais quand je parlais de bruit ce n'etait pas que les notifs, c'était aussi
les informations données sur l'interface Q15: oui Q16: oui »

Mechanism (PO interpretation):
1. Q8 — reliable = no stored copy of state: each block re-reads its live
   source when shown, displays source + check time, or "unknown: <source>
   unreachable", never an old value; a test compares each block with its
   source.
2. Q9 — PC + iPhone through Tailscale (private network already on both
   devices; nothing public). PO choice (delegated by « je te laisse
   choisir »): the first slice is a vertical slice that includes the
   phone, because the risky unknowns are mobile (iOS push latency,
   Tailscale serving the page).
3. Q10 — actions without an agent: acknowledge/snooze an alert; answer a
   NEEDS BENJAMIN decision when the agent prepared options (a/b/c + "other
   → agent"); accept / reject (with reason) / defer a proposal; resume a
   session or order the Factory paused. NOT without an agent: approving a
   Spec or graph; anything owner-tier (spend, exposure, irreversible).
4. Q11 — "continue with an agent" copies a provider-neutral ready prompt
   (what happens, ids, question). Launching a session directly is later.
5. Q12 — manifest file in each project's own repo (name, code repos,
   roadmap, state, display language); the Factory holds one pointer line
   per project; the Factory has its own manifest.
6. Q13 — ntfy.sh hosted, free, new secret topic kept out of git; payload =
   level, event class, project, cockpit link only.
7. Q14 — one notification when a condition starts; nothing while it stays
   open; again only on level increase or recurrence after resolution;
   "resolved" only for urgent; no digest. Benjamin's precision: noise also
   means the screen's content (→ Q17).
8. Q15 — every item: what / why it waits for you / what to do, in plain
   French; codes only in details; language from the manifest or
   `config/operator.toml`.
9. Q16 — interim: SayMyName `AGENTS.md` session start now runs
   `escalation-door list` (SayMyName commit c6c35db); removed by C01.

## Round 3 — 2026-09-29

Intent (Benjamin): « Q17 à Q23 : ok, partout comme tu recommandes sauf pour
Q22: je suis d'accord avec ta liste mais concernant le "ne remplace pas
github ni l'interface des beads" que veux tu dire par là ? … J'aurais voulu
avoir un kanban ou autre pour suivre les beads / tickets ou autre, j'aurais
aimé suivre le travail sur un projet via le cockpit, voir ce qui a été
fait, ce qui reste à faire etc. » then, on options a/b/c: « a, avec titres
français fournis par la planification ».

Mechanism (PO interpretation):
1. Q17 — home screen in three zones: "What waits for you" (actions only;
   explicit "nothing waits for you, checked HH:MM"), "Project progress"
   (one card per project), "Factory health" (one line). One line per
   condition (same dedup key as notifications); resolved items leave the
   home screen for a journal page; technical details folded.
2. Q18 — signal table (see planning-session.json); the cockpit adds no new
   escalation ladder, it surfaces the existing one (Mayor first, NEEDS
   BENJAMIN after 2 h).
3. Q19 — cockpit and notifications are pure code: zero model tokens.
4. Q20 — listen on localhost and the tailnet only; Tailscale identity of
   the device/account goes into the trace; no extra code.
5. Q21 — remove from session start: NEEDS BENJAMIN list, proposal count,
   ritual line — each only after its replacement is proven.
6. Q22 — non-objectives accepted. "Does not replace GitHub/Beads" means no
   editing, commenting, code review or history search in the cockpit; it
   links out. Kanban option a: a READ-ONLY kanban per project (roadmap,
   current graph in columns to do / in progress / in PR / done, previous
   graphs folded as history); changes go through "continue with an agent";
   only approved-graph tickets, bugs and proposals are shown (no molecules,
   mails, wisps). Ticket display titles in the operator's language are
   provided by planning (a graph field), not translated at display time.
7. Q23 — A7 done = graph delivered and closed + 3 days of real use: every
   NEEDS BENJAMIN reached the phone, zero duplicate notification, zero
   false or stale screen line, and Benjamin did not need to ask an agent
   "where are we" (his judgement).

## Round 4 — 2026-09-29

Intent (Benjamin): « Q24 à Q26 ok, lance le router »

Mechanism (PO interpretation):
1. Q24 — one roadmap (SayMyName's, which holds the Factory's A steps); the
   Factory card shows its convoys, kanban and health, no roadmap of its own.
2. Q25 — a small Windows-side watcher (pure code) checks a Factory
   heartbeat; after 30 min of silence it sends one "Factory silent since
   HH:MM" notification and one "back" notification; PC off = nothing sent.
3. Q26 — host-side steps done by Benjamin, guided, at the mobile slice:
   ntfy app subscribed to the new topic; Tailscale always-on on the iPhone;
   `tailscale serve` on Windows publishing the cockpit to the tailnet only
   (never `funnel`).

## Round 5 — 2026-09-29 (after Spec and graph approval)

Intent (Benjamin): « j'approuve le plan de tickets C01 mais pourquoi
absolument attendre A6 et attendre demain ? j'ai pas le temps d'attendre
aussi est ce que l'UI UX est pris en compte dans ces tickets dans
l'implementation de l'usine ? par exemple , on a pas fait de prototype etc.
Aussi j'ai eu ce hint avec un test que je viens de faire sur saymyname: le
site vitrine que l'usine avait faite pour l'app saymyname est absolument
horriblement moche. » then, on the PO's options: « A oui, B oui ».

Mechanism (PO interpretation):
1. A — publish C01 now, without waiting for A6 to close. Amends SayMyName
   decision 23. Reason: A6's last batch merged 14:04, so the 2 workers are
   idle and P22's 24 h window proves little without work; C01 gives it
   real parallel load. Accepted consequence: if a C01 merge breaks `main`
   or makes an order fail, P22's window restarts.
2. B — UI/UX gate. (a) K00: a throwaway clickable HTML prototype of the
   cockpit (home in 3 zones, a project page with the kanban, answering an
   option), synthetic data, made by the PO with Benjamin and approved by
   him on PC and iPhone; it fixes the visual baseline (type, colours,
   spacing, dark mode). (b) Every ticket that renders UI waits for K00 and
   shows phone-width and desktop-width screenshots in its PR; the reviewer
   compares them with the prototype and escalates visible deviations.
   (c) General rule for any project: a ticket that renders UI requires an
   operator-approved prototype ticket among its blockers and screenshots in
   its PR (enforced at publish). Class: SayMyName's showcase site was
   delivered with no prototype, no design baseline, no visual acceptance.
3. Planning method gap (PO finding, not yet decided): this run used the
   `grilling` skill and a read-only fact agent, not Matt Pocock's
   `wayfinder` (not installed; Factory `wayfinding-run` only keeps a
   decision map). No research or prototype step exists in the Planning Run
   flow. For C01: K00 is the prototype; a sourced research on ntfy / iOS /
   `tailscale serve` runs now (research.md). For the method: a proposal
   bead, Benjamin decides.
