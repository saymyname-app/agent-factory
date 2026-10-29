# Registre des catégories de défauts

Intent (Benjamin, ses mots, 22/10/2026 13:12 Paris) : « qu'on trouve une
méthode, là, maintenant, pour que ça n'arrive plus, que tous ces
problèmes-là ne puissent récidiver et ne réarriver sous une autre forme.
Enfin, il faut qu'on puisse prévoir. » ; puis, relayé le 25/10 15:13 Paris :
« Reponds pour moi que je suis Ok pour tes recommandations pour toutes
decisions à prendre. »
Mechanism (interprétation de l'agent, af-npz9v1.25) : la méthode cible
minimale de l'étude B (`research/2026-10-22-causes-racines-incidents.md`,
§ 6). Un correctif d'usine nomme sa catégorie, cherche les autres
occurrences de la même catégorie et les corrige, et pose ou complète le
contrôle automatique qui attrapera la suivante. Ce registre ne crée aucune
porte de Benjamin et n'autorise aucun refactor sans défaut (ADR-0017).

Du 15 au 22/10/2026, environ 70 réparations de l'usine se ramènent à trois
catégories, revenues chacune 5 à 7 fois : chaque correctif réparait l'endroit
observé et écrivait le reste « hors périmètre ». Les correctifs qui n'ont pas
récidivé sont ceux qui ont posé un contrôle de toute la catégorie (#619,
#688, #690, #692).

## Qui lit ce registre

- `bin/factory-fix-preflight --class <code>` : affiche l'invariant et les
  occurrences ouvertes, lance les commandes du champ `Contrôle`, refuse une
  catégorie absente d'ici (le correctif crée alors son entrée dans sa
  branche).
- `bin/pr-autopilot` : n'arme pas la fusion d'une PR de maintenance de
  l'usine (branche `fix/…` ou `do-work/…`) sans ses trois lignes
  `Catégorie :`, `Où ailleurs :`, `Contrôle de catégorie :`
  (`docs/DELIVERY.md`, « Maintenance de l'usine »).
- `python3 lib/defect_classes.py count --since <date>` : les PR fusionnées
  de chaque catégorie depuis une date, lues sur ces mêmes lignes. C'est la
  mesure de la méthode : une catégorie qui revient alors qu'elle a un
  contrôle signale un contrôle incomplet, on complète le contrôle et on
  rouvre l'entrée ici, pas un ticket.

## Format

Une catégorie par titre `## CODE — titre`, et quatre champs, chacun sur une
ligne `- Champ : valeur` (la suite d'une valeur longue est indentée de deux
espaces) :

- `Invariant` : la règle en une phrase ;
- `Contrôle` : le test ou lint qui tient la catégorie, chaque commande entre
  accents graves (`python3 …`, `bash …`), ou `aucun — <pourquoi>` ;
- `Occurrences` : les PR connues de la catégorie ;
- `Ouvertes` : les occurrences encore présentes dans le code et leurs Beads,
  ou `aucune connue`.

`tests/defect-classes-test.py` refuse une entrée incomplète. Une catégorie
nouvelle s'ajoute ici, dans la PR du correctif qui la découvre.

## P — Processus ou durée sans propriétaire ni budget mesuré

- Invariant : Tout ce qu'un outil lance meurt avec lui, quelle que soit la
  façon dont il finit ; tout délai vient d'une mesure.
- Contrôle : `python3 tests/project-launch-test.py`,
  `python3 tests/test-budgets-test.py` — partiel : le premier tient le
  lanceur des produits (`bin/project-launch`, son gardien et son balayage),
  pas les autres façons de lancer un programme ; le second tient les délais
  des tests d'un ticket et de l'ordre convoy-advance
  (`config/test-budgets.json`, étude C T3), dont l'exclusion d'un run rouge
  des mesures, pas les autres délais écrits à la main. Le lint « un seul
  lanceur borné » est planifié (af-npz9v1.26).
- Occurrences : #624, #628, #629, #630, #631, #636, #647, #657, #658, #661,
  #667, #694, #696, #705, #706, #708, #710, #713, #721 ; copies orphelines du
  22/10 (sans PR) ; af-kky570 ; af-npz9v1.46.
- Ouvertes : `subprocess.run(..., timeout=)` sans arrêt du groupe dans
  `bin/tdd-step`, `bin/ticket-author`, `bin/fixture-city-oracle`,
  `lib/evaluation_observations.py`, `bin/provider-failover` (étude B § 4.1,
  af-npz9v1.26) ; une vingtaine de délais écrits à la main (étude C) ;
  af-30zwwu.

## I — Impasse d'état : un arrêt ou une attente sans sortie codée

- Invariant : Chaque arrêt, chaque parcage et chaque option proposée à
  Benjamin a un chemin de code qui fait bouger le ticket, ou dit « reste à
  Benjamin, par telle porte ».
- Contrôle : `python3 tests/convoy-state-test.py ConvoyStateTest.test_a_stopped_unfavorable_judgement_from_an_older_contract_is_invalidated_and_rejudged`,
  `python3 tests/code-review-test.py CodeReviewTest.test_an_unfavorable_judgement_from_the_previous_contract_is_rejudged_once_at_the_same_tip`
  — partiel : ils tiennent la sortie codée d'un arrêt `still_refused` quand
  le contrat de jugement change, au niveau de la porte d'état puis de sa
  transmission par `settle` ; le test « chaque arrêt × chaque option » reste
  planifié (af-npz9v1.27).
- Occurrences : #635, #637, #650, #653, #662, #666, #672, #673, #679, #682,
  #687, #702, #704, #709, #711, #712, #718 ; af-npz9v1.44.
- Ouvertes : `evaluation_outage`, `criterion_already_green`,
  `outcome_evaluation_no_result`, `outcome_evaluation_outage`,
  `story_unobservable` sans reprise dans `lib/convoy_state.py` (étude B
  § 4.2, af-npz9v1.27).

## D — Doublure, instrument ou vue partielle qui ne se comporte pas comme le réel

- Invariant : Un faux outil refuse ce que le vrai refuse ; un instrument qui
  juge est étalonné sur un cas connu avant de servir ; on juge l'état
  résultant, jamais un morceau.
- Contrôle : `python3 tests/account-home-lint-test.py` — partiel : il tient
  le dossier personnel (#690). `tests/fake-tool-contract-test.py` compare la
  forme des commandes des faux déclarés, local seulement ; le contrôle de
  comportement des faux est planifié (af-npz9v1.28).
- Occurrences : #566, #618, #641, #648, #656, #664, #665, #669, #671, #674,
  #675, #676, #680, #689, #690, #692, #699, #700, #714, #715.
- Ouvertes : 38 faux exécutables sous `tests/fixtures/`, un seul comparé au
  vrai sur son comportement ; relecture de code non reproductible (étude B
  § 4.3, af-npz9v1.28).

## R — Une même règle tenue à deux endroits qui divergent

- Invariant : Une règle, une fonction : un écrivain et son lecteur, ou deux
  outils, lisent la règle au même endroit.
- Contrôle : `bash tests/operator-bd-test.sh` — partiel : il tient l'identité
  `po-agent/<session>` entre l'écrivain opérateur et `factory-orphan-sweep` ;
  les autres paires connues restent sans lint commun (af-npz9v1.29).
- Occurrences : #620, #625, #659, #660, #681, #685, #686, #693, #695, #703,
  #716 ; af-npz9v1.42.
- Ouvertes : `wanted_round` (`bin/code-review`) et `open-code-review`
  (`lib/convoy_state.py`) ; la preuve du rouge lue par `ticket-end` et
  `tdd-step` ; les « jeux nommés » de `ticket-evaluation` et `ticket-end`
  (étude B § 4.4).

## S — Signal faux ou manquant

- Invariant : Une alerte dit vrai et une situation qui demande quelqu'un
  produit une alerte.
- Contrôle : `bash tests/on-order-failed-test.sh` — partiel : il tient la
  frontière entre un report explicite (sortie 75, rejoué sans alerte) et une
  vraie panne répétée (bead et page Mayor) ; le contrôle 9 du gardien (#688)
  couvre les tickets que personne ne bouge, pas les autres signaux.
- Occurrences : #651, #679, #688, #717.
- Ouvertes : aucune connue.

## A — Autre

- Invariant : Aucun invariant commun : une PR rangée ici dit pourquoi elle
  n'entre dans aucune autre catégorie ; trois PR de même cause font une
  catégorie nouvelle.
- Contrôle : aucun — catégorie de tri.
- Occurrences : #619, #622, #639, #655, #677 ; tests nocturnes #634, #663,
  #670, #707.
- Ouvertes : aucune connue.
