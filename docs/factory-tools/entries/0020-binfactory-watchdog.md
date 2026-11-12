## `./bin/factory-watchdog` — la surveillance qui page, pas seulement qui observe

Plusieurs signaux peuvent rester muets sans que rien ne casse visiblement
(incident du 2026-09-16, `git show 987d497:legacy/docs/INCIDENT_2026-09-16-silent-campaign-stall.md`, af-539b0) :

```bash
./bin/factory-watchdog                # par défaut : vérifie ET page (mail + bead)
./bin/factory-watchdog --check-only   # ne touche à rien, sort non-zéro si problème
```

| Contrôle | Ce qu'il fait |
|---|---|
| `gates` | une « Gate: human » ouverte depuis plus de 30 min (réglable) est re-signalée au Mayor, pas seulement laissée dans la file — sauf si l'attente est déjà une demande active dans la liste de l'opérateur (`gc.needs_benjamin` sur le bead que la porte bloque, ou sur le convoi qui le suit) : elle est alors affichée, jamais paginée (af-brjmv6) |
| `prs` | une PR du dépôt Factory en `CONFLICTING`, ou dont aucun contrôle CI n'a jamais démarré, après 30 min — distincte d'une PR qui attend simplement son tour |
| `workflows` | un bead molécule/workflow fermé `CLOSED` avec `gc.outcome` ≠ `pass` (le cas `on_fail=abort_scope` : chaque étape en aval passe `outcome=skipped` en silence) — sauf le workflow d'une formule du nouveau flux, nommée dans `config/delivery-flow.json` : son résultat est lu par `bin/convoy-advance`, qui reprend, relance ou arrête le ticket lui-même (af-yzo8fo.2) ; sauf aussi un échec dont le ticket du nouveau flux porte déjà un arrêt (`gc.flow.stop`) ou une reprise (`gc.flow.resume`), retrouvé par le convoi d'entrée du workflow : le code l'a déjà lu et traité, même pour une formule retirée de ce fichier (af-it6qbk) |
| `gh-auth` | `gh auth status` échoue (token WSL périmé/invalide) — neuf scripts en dépendent (`reversibility-check`, `factory-guard`, `pr-autopilot`, `factory-do-work-workspace`, `factory-gh-rollup`, `factory-delivery-guard`, `deliver-close`, `factory-watchdog`, `factory-main-gate`) et échouaient chacun silencieusement de son côté (af-539b0, 2026-09-18) ; **un seul** bead partagé nommant les neuf scripts, **un seul** mail au Mayor par cooldown, et auto-résolu dès que `gh auth` revient — jamais un bead par script, jamais un par passage |
| `tickets` | un ticket démarré et non fermé d'un convoi marqué que personne ne fait avancer : aucune session vivante ne travaille pour son état courant (une session ne compte que si elle a démarré après la dernière sortie ou le dernier arrêt du ticket), aucun lancement de lui fait depuis n'est ouvert (correction, reprise, évaluation, revue), ni lui ni la demande groupée du convoi qui le couvre n'est dans la liste de l'opérateur (la demande groupée couvre les tickets que lève son option, ou, avant la porte, les tickets parqués sans réponse ; la demande portée par le convoi lui-même — fin de Spec, acceptation — n'en couvre aucun), il n'attend pas ses bloqueurs, et rien n'a été enregistré pour lui depuis 30 min de silence réel (`TICKET_STALL_MINUTES_DEFAULT`, réglable par `FACTORY_WATCHDOG_TICKET_MINUTES`). Une passe `convoy-advance` en cours qui a démarré dans ces 30 min peut encore le faire avancer (ses tests de fusion) : elle le retient, au plus le budget mesuré d'une passe (`pass_seconds`, `lib/test_budgets.py`) ; la passe inscrit son début à côté de son verrou (`lib/advance_pass.py`). T02R (18/10, #673) et T02R2 (19/10, #687) sont restés ainsi des heures sans que rien ne le signale (af-1fvzns) ; R16 et R19 du convoi af-strhoy encore ~8 h le 11/11, l'une derrière une session d'auteur vivante mais oisive après sa sortie, l'autre derrière la demande de fin de Spec du convoi (af-xgd1rd). Le Mayor ne touche pas aux convois marqués : l'alerte va dans la liste de l'opérateur comme un « Incident d'usine » (`bin/escalation-door benjamin`, comme l'« état sans règle » de `docs/CONVOY_ADVANCE.md`), un bead par ticket, retiré et fermé dès que le ticket bouge de nouveau. La réparation est une maintenance de l'usine, jamais un ticket avancé à la main. `tests/convoy-advance-test.py` (`test_no_pass_leaves_a_ticket_without_a_next_step_*`) fait passer chaque fin de travail d'auteur par la vraie passe et vérifie que cette règle ne signale rien une fois l'état stable |

Le contrôle `tickets` lit la demande groupée du convoi, ses tickets en jeu et
leurs lancements en un seul `gc bd show ID... --json` par convoi. Il ne relit
jamais chaque bead séparément : sur un convoi de 20 tickets, cette
amplification épuisait les 180 secondes de l'order avant que le watchdog
puisse rendre son verdict (`af-1tv5yy`).

Le watchdog possède aussi son groupe de processus et un budget interne de
150 secondes (`FACTORY_WATCHDOG_BUDGET_SECONDS`, pour le test déterministe),
mesuré contre un passage live de 47 secondes le 02/11/2026. Il garde ainsi
plus de trois fois cette durée tout en laissant 30 secondes au contrôleur de
l'order pour recueillir une erreur précise et tuer le groupe avant sa propre
limite de 180 secondes. Un enfant bloqué rend donc `factory-watchdog: internal
budget exceeded` ; il ne survit pas au passage et ne devient pas un vague
`context deadline exceeded` du contrôleur (`af-ll4hju`).

Sous une forte charge (load 15m ~34), un passage sain peut dépasser ce budget
sans qu'aucun appel soit bloqué : chaque lecture de `gc` est seulement plus
lente. L'observation live tourne en dernier, bornée par le temps restant moins
5 secondes. Un passage coupé par le budget, ou dont l'observation n'a pas tenu
dans ce temps, ne perd rien : le passage suivant relit le même état et renvoie
ce que `factory-observe` garde en attente. Il est donc reporté (sortie 0, avec
`pass deferred (n of 3 in a row, loadavg …)`), et seuls trois passages coupés
de suite sortent 2 (`FACTORY_WATCHDOG_DEFER_LIMIT`). Le compte est tenu dans
`.gc/runtime/factory-watchdog-deferred-passes` et remis à zéro par un passage
qui finit (`af-onrwp8`).

**Observe et page seulement** (ADR-0016 §7) : il ne résout jamais une porte,
ne fusionne ni ne ferme jamais une PR, et ne rouvre jamais un workflow. Chaque
signalement devient au plus un mail au Mayor (`gc mail send mayor --notify`,
relancé sur un délai de repli, jamais à chaque passage) et, pour les portes et
PR, un bead qui survit au passage suivant. Les règles pures sont dans
`lib/factory_watchdog.py`.

Les signalements n'écrivent plus dans un fichier signal local : depuis le
retrait du Cockpit V1 rien ne lisait `.gc/runtime/factory-watchdog-signals.json`,
et O06 (Factory operations v2) a retiré cet écrivain (`factory-watchdog`,
`on-order-failed`, `on-session-stranded`) ainsi que
`lib/factory_watchdog.py`'s `merge_signals`.

**Quand le lancer** : il tourne seul via son order (`orders/factory-watchdog.toml`,
5 min, bien en-dessous de l'heure qui a coûté 4h20 le 2026-09-16-17).

---
