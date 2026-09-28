# ADR-0028 : router une surprise sémantique de livraison par une Planning Exception

- Statut : Accepté
- Date : 2026-09-24
- Autorité : ticket B08 du Ticket Graph Draft approuvé
- Portée : refactor project-agnostic de la Factory, Delivery Workflow

## Contexte

Q18 fixe une seule autorité `to-tickets` : la Planning Run possède l'unique
passe de décomposition, et tout changement ultérieur de split, merge ou
topologie de dépendance y retourne. Q22 anticipe le cas où un worker de
livraison rencontre une question sur l'intent, le comportement ou la
topologie approuvés en cours de tranche : il doit lever un signal structuré
plutôt que redessiner le travail lui-même, faute de quoi la livraison devient
une seconde autorité de décomposition. Avant B08, aucun mécanisme durable
n'existe pour ce signal ; `bin/ticket-graph-publish` sait publier un graphe
une fois, mais ne sait pas patcher le travail non terminé d'un graphe déjà
publié.

## Décision

1. `bin/planning-exception` est le point d'entrée du signal. `classify`
   distingue une réparation technique bornée (reste dans la tranche
   approuvée, jamais de Planning Exception) d'une surprise sémantique ou de
   topologie (`raise` obligatoire) — voir la distinction Q22/Q53 dans le
   grilling checkpoint.
2. `raise` crée exactement une Planning Decision non exécutable
   (`plane=planning`, `delivery_routable=false`, comme `wayfinding-run`) et
   ne met en pause que le bead affecté et ses descendants transitifs dans
   l'instantané du Delivery Work Graph fourni — jamais le graphe entier. La
   frontière éligible non liée continue sans interruption.
3. Un second `raise` sur un bead déjà couvert par une Planning Decision
   ouverte est détecté comme doublon : aucune seconde décision n'est créée,
   et l'événement est enregistré dans l'historique du registre — l'évidence
   de classification et d'escalade en double exigée par B08 vit dans
   `docs/ADAPTATION_REGISTER.md` (AR-003), sourcée sur cette preuve de test.
4. `resolve --kind tactical` lève la pause sans toucher à aucun artifact : une
   clarification ne change ni la Spec ni le Ticket Graph Draft.
5. `resolve --kind behavioral|topology` exige un draft déjà révisé et validé
   en amont (la Planning Run le produit, pas cet outil) et le fait passer par
   `bin/ticket-graph-publish patch` — la même porte déterministe que la
   publication initiale, jamais une seconde. `patch` refuse de toucher un
   ticket déjà livré (status `closed`) ; il ne crée de nouveaux Beads que pour
   la portée réellement nouvelle et met à jour les tickets non terminés en
   place, en conservant leurs IDs.
6. Si `ticket-graph-publish patch` échoue, `resolve` échoue aussi : la
   décision reste ouverte et le sous-graphe reste en pause. Rien n'applique
   un patch partiel.

## Conséquences selon ADR-0017

1. **Vérifié** — `tests/planning-exception-test.py` prouve la distinction
   réparation/surprise, la mise en pause scoped aux descendants, la détection
   de doublon, la reprise tactique sans patch, et le routage
   comportemental/topologique par `ticket-graph-publish patch` (succès et
   échec). `tests/ticket-graph-publish-test.py` prouve que `patch` refuse un
   ticket fermé et ne crée que la portée nouvelle.
2. **Autonomie accrue** — un worker de livraison peut signaler une surprise et
   continuer le travail non lié sans attendre une intervention manuelle pour
   isoler le sous-graphe affecté.
3. **Optimisation** — la mise en pause scoped évite d'arrêter toute la
   frontière éligible pour une question qui ne concerne qu'un sous-graphe.
4. **Documentation** — cette ADR, `docs/ADAPTATION_REGISTER.md` (AR-003) et
   `CONTEXT.md` (glossaire *Planning Exception*) décrivent le mécanisme.

## Amendement — décision 8 (t6-planning-doors, 2026-09-28)

Intent (Benjamin, 2026-09-28, "Q6.3 oui mais je ne me souviens plus", source
2026-09-25 23:09 : « on a ajouté ces scripts orders au compte-goutte avec les
incidents … rechercher ce qui se fait, les bonnes pratiques, et remettre en
question ce qu'on a pour soit regrouper, ajouter, modifier ou supprimer des
orders »): le Mayor peut resliceer un graphe publié sans repasser par une
Planning Run tant que l'outil déterministe prouve que les critères
d'acceptation ne changent pas ; sinon la question va sur la liste NEEDS
BENJAMIN. Chaque patch — reslice ou révision complète — laisse la trace de
qui l'a fait et pourquoi. Un ticket que le worker se scinde lui-même reste
traçable jusqu'à son origine.

Mechanism (implémentation) :

1. `bin/ticket-graph-publish patch` prend `--author` et `--reason`
   (obligatoires) et les écrit sur le convoy (`gc.patch_author`,
   `gc.patch_reason`, note `PATCH by <author>: <reason>`), qu'il s'agisse
   d'un reslice ou d'une révision complète.
2. `--reslice` marque un reslice du Mayor sans nouvelle Planning Run. Pour
   chaque ticket non terminé que le patch touche, l'outil compare les
   critères d'acceptation déjà publiés (extraits du texte de la Bead, seule
   source de vérité) à ceux du draft ; toute différence refuse tout le patch
   avant la moindre écriture et l'escalade via `escalation-door benjamin`
   sur le convoy (liste NEEDS BENJAMIN). Sans `--reslice` (draft révisé et
   réapprouvé par une Planning Run), les critères d'acceptation peuvent
   changer librement, comme avant cet amendement.
3. Un ticket peut déclarer `merges: [<id>, ...]` : les tickets listés,
   forcément non terminés (`patch` refuse un ticket déjà `closed`, comme au
   §5 ci-dessus), sont fermés et marqués `gc.merged_into=<id résultant>`.
   Un ticket peut déclarer `supersedes: <id>` : le ticket remplacé, non
   terminé, est fermé et marqué `gc.superseded_by=<nouvel id>`. `reorder`
   n'est pas un champ séparé : changer `blocked_by` d'un ticket non terminé
   déjà publié fait que `patch` réconcilie ses dépendances (`bd dep
   add`/`bd dep remove`) contre l'instantané `gc.blocked_by` qu'il maintient
   lui-même sur chaque Bead.
4. Un ticket créé par le patch peut déclarer `split_from: <id>` : la Bead
   créée porte `gc.split_from=<id>`, pour qu'un self-split de worker reste
   traçable jusqu'à son origine sans mécanisme séparé.

## Reprise et limites

- `planning-exception` ne lit ni n'écrit Beads directement : il opère sur un
  registre JSON verrouillé (même patron de concurrence que `wayfinding-run`)
  et un instantané de graphe fourni par l'appelant. L'intégration avec un
  Delivery Work Graph Beads réel (traduire `bd dep list`/`bd list` en
  instantané) reste un câblage ultérieur, hors scope de ce ticket.
- La classification `--kind` est explicite (le worker choisit
  `repair`/`semantic`/`topology`), pas une classification automatique par
  contenu libre — Q22 ne demande pas de NLP.
- Ce mécanisme est une adaptation expérimentale (AR-003), pas une
  fonctionnalité Sandcastle : il est retenu seulement si de vraies surprises
  sémantiques s'y routent proprement, sans interruption inutile ni double
  escalade.

## Liens

- Approved Spec `spec-agent-factory-project-agnostic-refactor` (AC18–19,
  User Story 22, transitions de cycle de vie 11–12).
- `docs/research/2026-09-22-agent-factory-refactor-grilling-checkpoint.md`,
  items 22 et 53.
- ADR-0025 — publication atomique et scope exclusif d'un graphe approuvé.
- `bin/planning-exception` et `tests/planning-exception-test.py`.
- `bin/ticket-graph-publish` (mode `patch`) et `tests/ticket-graph-publish-test.py`.
- `docs/ADAPTATION_REGISTER.md`, AR-003.
