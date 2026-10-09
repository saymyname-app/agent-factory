## `./bin/spec-end` — la Spec est-elle vérifiée, et sinon que manque-t-il ?

**La porte de fin de Spec** (Spec af-wf4w5r §9 et §8, T23, T24, T25, T27 et T26). Dans un
convoi qui porte la **marque du nouveau flux**, des tickets tous fermés ne
font pas une Spec vérifiée : du code rend **trois verdicts mécaniques, tous
liés au même commit** de la branche d'intégration, la branche protégée
reprise. Aucun agent ne les rend. Sur ce même commit, elle lit ensuite
l'Outcome Evaluation et les constats hors ticket (`./bin/outcome-evaluation`),
et la revue de code de fin (`./bin/spec-end-review`).

```bash
./bin/spec-end check <convoi> --repo <dépôt du projet>                      # où en est la fin de Spec ; n'écrit rien
./bin/spec-end run   <convoi> --repo <dépôt du projet> --profile <profil>   # la porte ; lancée par ./bin/convoy-advance
```

- **Les sept conditions** (liste `spec-end/v4`), dans l'ordre : 1 registre
  (tickets fermés par la porte de fin de ticket ou retirés, aucun parqué ;
  chaque écart et chaque « non fait » d'un Ticket Handoff « réparé » ou
  « accepté par Benjamin » ; aucune Planning Exception ouverte) ; 2 tests
  verts sur la pointe, branche protégée reprise ; 3 fidélité mécanique verte
  sur toutes les ancres de tous les états prototypés ; 4 Outcome Evaluation
  (chaque user story numérotée « observée avec preuve » sur le produit
  assemblé, aucun constat hors ticket non classé) ; 5 constats hors ticket
  tous dans un état final ; 6 revue de code de fin complète et favorable sur
  tout le diff assemblé, à ce commit précis ; 7 Evidence Pack généré par du
  code, complet et à jour, à ce commit (`./bin/evidence-pack`). Une condition non réunie arrête
  la porte : les suivantes ne sont pas lancées — sauf la revue de fin, faite
  en parallèle de l'Outcome Evaluation et lue quoi que disent 4 et 5. Seuls
  les verdicts 1 à 3 sont enregistrés ; 4 à 7 sont relus à chaque appel. La
  porte ne génère pas le dossier : `./bin/convoy-advance` le fait générer
  quand il ne manque que lui.
- **Pour savoir ce qui manque** : `check` nomme chaque condition non réunie
  et dit ce qui a été lu.
- **Un écart ou un « non fait » sans état final** : la porte le nomme et te
  pose une question, une fois par ticket (`./bin/escalation-door list`).
  Réponds par `./bin/escalation-door repondre <ticket> a` (faire réparer :
  du code publie un ticket `repair`) ou `b` (accepter tel quel). **Aucune
  commande n'écarte un élément** : il finit réparé ou accepté par toi.
- **Tests rouges ou fidélité rouge** : c'est le rouge de la branche
  d'intégration ; un tour de fin est compté (`counters.end_rounds`) et
  `./bin/convoy-advance` publie le seul `repair`. La porte rejoue tout une
  fois ce `repair` fusionné et fermé.
- **Deux tours de réparation, pas plus** (T26) : les tours de fin sont un
  seul compteur pour toutes les sources (tests ou fidélité rouges, revue de
  fin, Outcome Evaluation), borné par `bounds.end_rounds` de
  `config/delivery-flow.json` (2, sans base mesurée). Un rouge trouvé une
  fois les tours consommés est enregistré **avec l'arrêt des tours**, sans
  tour de plus et sans `repair` : la condition rouge le dit, et tu reçois
  une demande « non conforme » (`./bin/convoy-advance`). Sous ce rouge, la
  porte refuse en disant qu'elle attend cette demande.
- **Delivered** (T26) : quand les sept conditions sont vertes sur la même
  pointe, dossier compris, `run` l'enregistre sur le convoi
  (`convoy.delivered` dans `./bin/convoy-state show`) et répond
  `"delivered": true` ; `check` le dit aussi, tant que rien n'a bougé.
  Jamais avec une condition rouge, sans dossier, sur un dossier généré
  pendant qu'une condition était rouge, ni pour un commit de plus.
  **Delivered est un état du convoi, pas une acceptation** : rien n'est
  fusionné dans la branche protégée, rien n'est fermé, rien n'est accepté à
  ta place.
- **Un commit de plus annule tout** : les verdicts sont enregistrés avec
  leur commit (`convoy.spec_end` dans `./bin/convoy-state show`). Dès que la
  branche d'intégration ou la branche protégée bouge, `check` les dit
  « périmés » et la porte rejoue tout.
- **Sorties** : 0 sept conditions réunies sur la pointe actuelle ; 1 refus ou
  condition non réunie ; 3 état sans règle ; 4 convoi sans marque. `run` est
  refusé à toute session d'agent.
- **Limites** : la porte tourne dans la passe de l'ordre (délai de 300 s,
  non mesuré sur un vrai projet) ; pas de pièce scellée pour les tests et la
  fidélité de fin (leur relevé est sur le convoi) ; la porte vérifie, elle
  n'accepte rien et ne ferme rien (ta réponse : `./bin/owner-answer` ; la
  fusion et la fermeture : `./bin/outcome-promote`, qui appelle ici
  `replay` — les seuls contrôles mécaniques, sans tour de fin compté —
  quand la branche protégée a bougé depuis ton jugement) ; une fois les
  tours arrêtés, aucune commande ne les relance
  encore, quelle que soit ta réponse à la demande « non conforme » ; sous
  un rouge de fin, `check` montre les conditions 2 à 7 « non lancé » au lieu
  de nommer celle qui est rouge (lis `end_stop` et
  `./bin/convoy-state show`).

Détail : `docs/SPEC_END.md`.

---

