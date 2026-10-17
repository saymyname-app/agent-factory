## `./bin/delivery-seat-release` — libérer le siège d'un vérificateur qui a servi

**Ferme une session de relecteur ou d'Evaluator qui a rendu son travail et
garde le seul siège de son rôle pendant que du travail d'un autre flux
attend** (af-epkrcv). Gas City 1.5.0 garde ce siège chaud pour le travail en
attente et annule son drain-ack ; la requête de travail du rôle ne lui offre
plus rien (une session par revue, `docs/CODE_REVIEW.md`). Sans cette
fermeture, le siège restait tenu jusqu'à `idle_timeout` (2 h) et les
lancements en attente expiraient sans résultat (17/10, T59).

```bash
./bin/delivery-seat-release --check-only   # nomme les sièges, ne ferme rien
./bin/delivery-seat-release                # ferme (ordre delivery-seat-release, toutes les 2 min)
```

- **Fermée** : session active de `delivery-reviewer` ou `delivery-evaluator`,
  qui a déjà eu des beads assignés, tous fermés, alors que du
  travail prêt, non assigné, routé vers son rôle attend dans un autre flux.
- **Laissée** : une session qui n'a jamais servi (celle que Gas City démarre
  pour le travail en attente), une session au travail, une session dont le
  propre flux a le travail prêt, et tout autre modèle de session.
- **Sorties** : 0 ; 1 si la liste des sessions ou le tracker ne se lit pas
  (rien n'est fermé) ; 2, usage. Chaque fermeture : une ligne de
  `var/delivery-seat-release.log`.
- **Réversible** : la session fermée ne tenait aucun travail ; Gas City en
  démarre une neuve pour le travail en attente.

Preuve : `tests/delivery-seat-release-test.sh` ; l'ordre : `tests/delivery-seat-release-order-test.sh` (local-only).
