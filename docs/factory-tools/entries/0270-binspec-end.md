## `./bin/spec-end` — la Spec est-elle vérifiée, et sinon que manque-t-il ?

**La porte de fin de Spec** (Spec af-wf4w5r §9, points 1 à 4, T23, T25). Dans un
convoi qui porte la **marque du nouveau flux**, des tickets tous fermés ne
font pas une Spec vérifiée : du code rend **trois verdicts mécaniques, tous
liés au même commit** de la branche d'intégration, la branche protégée
reprise. Aucun agent ne les rend. Sur ce même commit, elle lit une
quatrième condition qu'elle ne rend pas : la revue de code de fin
(`./bin/spec-end-review`).

```bash
./bin/spec-end check <convoi> --repo <dépôt du projet>                      # où en est la fin de Spec ; n'écrit rien
./bin/spec-end run   <convoi> --repo <dépôt du projet> --profile <profil>   # la porte ; lancée par ./bin/convoy-advance
```

- **Les quatre conditions** (liste `spec-end/v2`), dans l'ordre : 1 registre
  (tickets fermés par la porte de fin de ticket ou retirés, aucun parqué ;
  chaque écart et chaque « non fait » d'un Ticket Handoff « réparé » ou
  « accepté par Benjamin » ; aucune Planning Exception ouverte) ; 2 tests
  verts sur la pointe, branche protégée reprise ; 3 fidélité mécanique verte
  sur toutes les ancres de tous les états prototypés ; 4 revue de code de
  fin complète et favorable sur tout le diff assemblé, à ce commit précis.
  Une condition non réunie arrête la porte : les suivantes ne sont pas
  lancées. Les trois premières sont enregistrées dès qu'elles sont vertes,
  la quatrième encore manquante.
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
- **Un commit de plus annule tout** : les verdicts sont enregistrés avec
  leur commit (`convoy.spec_end` dans `./bin/convoy-state show`). Dès que la
  branche d'intégration ou la branche protégée bouge, `check` les dit
  « périmés » et la porte rejoue tout.
- **Sorties** : 0 les quatre conditions réunies sur la pointe actuelle ; 1 refus ou
  condition non réunie ; 3 état sans règle ; 4 convoi sans marque. `run` est
  refusé à toute session d'agent.
- **Limites** : la porte tourne dans la passe de l'ordre (délai de 300 s,
  non mesuré sur un vrai projet) ; pas de pièce scellée pour les tests et la
  fidélité de fin (leur relevé est sur le convoi) ; la porte vérifie, elle
  n'accepte rien et ne ferme rien ; le compteur de tours n'est pas encore
  comparé à une borne.

Détail : `docs/SPEC_END.md`.

---

