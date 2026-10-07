## `./bin/spec-integration` — où vont les tickets terminés d'une Spec ?

Dans la branche d'intégration de la Spec, un par un, jamais vers la branche
protégée (Spec af-wf4w5r §4 et §8, T18). Pour un convoi qui porte la
**marque du nouveau flux** seulement.

```bash
./bin/spec-integration open  <convoi> --repo <dépôt du projet> --protected <branche protégée>
./bin/spec-integration merge <convoi> --repo <dépôt du projet> --profile <descripteur.json> [--limit 1]
```

- **`open`** : crée `integration/<id de la Spec>` à la pointe de la branche
  protégée et l'enregistre sur le convoi. La porte de publication l'appelle
  dès que le convoi est marqué ; un convoi sans marque n'a pas de branche.
- **`merge`** : fusionne chaque ticket que son auteur a terminé à la pointe
  de sa branche, dans l'ordre du convoi, jamais deux à la fois. La branche
  d'intégration reprend d'abord la branche protégée. La commande de
  régression du profil tourne sur chaque résultat fusionné ; son relevé est
  une pièce du magasin de preuves (`merged_tests`), liée au commit du
  résultat. `./bin/convoy-advance` l'appelle à chaque passe, un ticket à la
  fois.
- **Pas de fusion sans revue de code favorable** : un ticket terminé n'est
  fusionné que si sa revue (`./bin/code-review`) est favorable à la pointe de
  sa branche. Sans revue, avec une revue en cours ou restée sans sortie, ou
  avec un Blocking Finding sans verdict favorable, il reste dans `waiting`
  avec la raison.
- **Conflit, ou tests rouges sur le résultat** : rien n'est fusionné ni
  poussé, le ticket retourne à son auteur. Aucun agent ne résout à sa place.
- **Commit ajouté après un verdict** (revue de code ou Ticket Evaluation) :
  fusion refusée, verdicts marqués invalides, une reprise comptée ; ils se
  rejouent sur la nouvelle pointe.
- **Sorties** : 0 fait ; 1 refus, ou un ticket refusé ; 3 état sans règle ;
  4 « pas un convoi du nouveau flux ».
- **Limites** : les autres conditions de la porte de fin de ticket ne sont
  pas encore exigées avant la fusion (T19) ; la session neuve de l'auteur d'un
  ticket retourné n'est pas démarrée ici (T20) ; un seul dépôt par convoi.

Détail : `docs/SPEC_INTEGRATION.md`.

---

