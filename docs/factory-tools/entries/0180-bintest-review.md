## `./bin/test-review` — un test de critère observe-t-il vraiment son critère ?

> **Remplacé par ADR-0030 L3** : le flux ne lance plus cette relecture ; la
> revue de code (`./bin/code-review`) lit les tests de critère. Retiré en L7.

Un **relecteur**, pas l'auteur, répond (Spec af-wf4w5r §5 « Relecture avant
gel », §8, T13). Entre le rouge prouvé et le gel, une session neuve du rôle
relecteur, en lecture seule, répond à une seule question par test de
critère : observe-t-il son critère, et échouerait-il sur l'observation qui
le rend faux ? Un test qui ne vérifie qu'un statut 200 est refusé. Ne
concerne qu'un ticket d'un convoi qui porte la **marque du nouveau flux**.

```bash
./bin/test-review review <convoi> <ticket> --repo <worktree>      # l'auteur, après tdd-step red
./bin/test-review show <convoi> <ticket>                          # les passes, la demande ouverte, l'arrêt
./bin/test-review settle <convoi>                                 # plus lancé par convoy-advance depuis ADR-0030 L3
./bin/test-review brief <convoi> <ticket>                         # la session relecteur (formule mol-test-review)
./bin/test-review record <convoi> <ticket> --verdict-file <f>     # la session relecteur
```

- **Sans verdict favorable, pas de gel** : `./bin/tdd-step freeze` refuse
  tant que chaque test de critère n'a pas passé la relecture, au même commit
  et sur les mêmes empreintes de fichiers. Sans gel, le code ne commence pas.
- **Un refus** : le relecteur donne une raison par test refusé. Le ticket
  retourne **une fois** à son auteur, qui corrige ses tests, les fait
  reprouver rouges et redemande la relecture.
- **Second refus** : le ticket est arrêté. Il apparaît **une seule fois**
  dans `./bin/escalation-door list`, avec le test et la raison.
- **Relecture plantée ou sans sortie** : elle n'est pas passée. Une relance,
  puis le ticket est arrêté et remonte de la même façon. Le délai d'un
  lancement est `test_review.timeout_seconds` dans
  `config/delivery-flow.json` (1800 s, valeur sans base mesurée).
- **Le verdict est calculé par du code** : le relecteur donne un état par
  test (`favorable` ou `unfavorable` avec sa raison), jamais un verdict
  global. Il ne reçoit que les critères du ticket et les tests ; rien
  d'autre de l'auteur.
- **Sans session d'auteur** : la relance, l'arrêt et la remontée sont aussi
  faits par `./bin/convoy-advance`, à partir du tracker seul.
- **Ne jamais dispatcher `mol-test-review` à la main** ni écrire
  `gc.flow.test_review` : seul `./bin/test-review` le fait, par
  `./bin/dispatch-door` et `./bin/convoy-state`.
- **Sorties de `review`** : 0 tests relus favorablement ; 2 refus, retour à
  l'auteur ; 5 ticket arrêté ; 6 pas encore de verdict, relancer la même
  commande ; 1 refus ou échec ; 4 « pas un convoi du nouveau flux ».
- **Limites** : rien ne lève encore un arrêt. Un test amendé après le gel
  n'est pas relu ici : la revue de code du ticket le relit
  (`./bin/code-review`).

Détail : `docs/TEST_REVIEW.md`.
