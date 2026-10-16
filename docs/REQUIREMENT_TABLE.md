# Table exigence → mécanisme → preuve

Une exigence du flux de livraison a un mécanisme qui la vérifie, ou elle
n'est pas écrite (Spec af-wf4w5r §9, user story 77). Cette table est celle de
la Spec approuvée, avec, pour chaque ligne, les commandes de l'usine qui
tiennent le mécanisme. Elle vaut pour les convois qui portent la marque du
nouveau flux ; un convoi sans marque suit `DELIVERY.md` comme avant.

`./bin/method-check table` la relit à chaque run de la CI de l'usine
(`tests/method-check-test.py`) et échoue, en nommant la ligne, si :

- le mécanisme est vide, ou ne nomme aucune commande (`bin/<nom>`) ;
- une commande nommée n'est pas un fichier exécutable de `bin/` — une
  commande renommée ou retirée rend donc rouge la ligne qui la cite ;
- la preuve est vide.

Ajouter une exigence, c'est ajouter une ligne : sans mécanisme, la pull
request est rouge. Le contrôle lit les noms de commande, pas ce que font les
commandes : qu'une commande tienne bien l'exigence de sa ligne reste prouvé
par ses propres tests et par le document cité.

| Exigence | Mécanisme | Preuve produite |
| --- | --- | --- |
| Ticket démontrable sur le produit | Porte de publication `bin/ticket-graph-publish` (contrat d'entrée) et relecteur de graphe `bin/graph-review` — `ENTRY_CONTRACT.md`, `GRAPH_REVIEW.md` | Verdict par ticket lié au digest du brouillon |
| Critères observables et gelés | Porte de publication `bin/ticket-graph-publish` ; empreinte des critères posée avec la marque par `bin/convoy-state mark`, relue par `bin/ticket-end` — `TICKET_END.md` | Condition 1 de la porte de fin de ticket |
| Rouge avant le code | Script de l'étape rouge `bin/tdd-step red` — `TDD_STEP.md` | Résultat par test au commit de départ |
| Tests non affaiblis | Gel, registre d'empreintes et amendement borné de `bin/tdd-step` (`freeze`, `green`, `amend`) ; tests de critère lus par la revue de code (ADR-0030 L3) — `TDD_STEP.md`, `CODE_REVIEW.md` | Empreintes, diff d'amendement |
| Test par interface publique | Preuve du seam (boîte noire ou règle d'import) de `bin/tdd-step`, relue par `bin/ticket-end` — `TDD_STEP.md` | Relevé du script |
| Le produit marche | Ticket Evaluation `bin/ticket-evaluation`, Outcome Evaluation `bin/outcome-evaluation`, pièces prises par `bin/evidence-capture` — `TICKET_EVALUATION.md`, `OUTCOME_EVALUATION.md` | État et Evidence Record par critère et par story |
| Fidélité au prototype | Contrôles mécaniques sur tokens et ancres de `bin/prototype-fidelity` ; version figée contrôlée par `bin/prototype-conformance` — `PROTOTYPE_FIDELITY.md`, `VALIDATED_PROTOTYPE.md` | Relevé par ancre et par état |
| Code conforme à la Spec | Revue par un relecteur distinct : `bin/code-review` par ticket, `bin/spec-end-review` en fin de Spec — `CODE_REVIEW.md`, `SPEC_END_REVIEW.md` | Verdict par Blocking Finding |
| Rien de reporté en silence | Ticket Handoff validé et détecteur de report de `bin/ticket-exit` ; condition 5 de `bin/ticket-end` ; éléments suivis relus par `bin/spec-end` — `TICKET_EXIT.md`, `SPEC_END.md` | Éléments suivis et leur état final |
| Assemblé de bout en bout | Fusion sérielle testée `bin/spec-integration merge` et porte de fin de Spec `bin/spec-end` — `SPEC_INTEGRATION.md`, `SPEC_END.md` | Verdict de chaque condition |
| Méthode de Matt inchangée | Comparaison au tag `bin/upstream-skills-check compare`, lancée en CI par `bin/ci-run-tests` — `UPSTREAM_SKILLS.md` | Résultat de CI |
| Acceptation liée à ce qui a été jugé | Outil d'enregistrement `bin/owner-answer` ; fusion liée au commit jugé par `bin/outcome-promote` — `OWNER_ANSWER.md`, `OUTCOME_PROMOTE.md` | Mots, commit, empreinte du dossier |
| Aucun agent ne décide du flux | Démarrage marqué par la porte de dispatch `bin/dispatch-door` (relevé `dispatch` sur le ticket) ; garde de `bin/convoy-state show` qui détecte un démarrage hors porte ; fermeture reconnue à son relevé de porte, écrit par `bin/ticket-end` ; arrêt sur état inconnu par `bin/convoy-advance` — `CONVOY_STATE.md`, `CONVOY_ADVANCE.md` | Relevé de la garde, anomalies au dossier |

Le second contrôle du même outil, `./bin/method-check register`, tient
l'autre moitié de la promesse : chaque écart avec la méthode de Matt Pocock
listé en §16 de la Spec a son entrée dans `ADAPTATION_REGISTER.md`, avec sa
raison et sa base de comparaison v1.3.1.
