## `./bin/ticket-evaluation` — qui vérifie que le produit marche, avant la fusion d'un ticket ?

Un **Evaluator**, jamais l'auteur (Spec af-wf4w5r §7, §8, T15). Dès qu'un
ticket est terminé et vert à la pointe de sa branche, le flux lance le
produit **depuis une copie propre de cette pointe** (port isolé, jeux de
données synthétiques) et l'envoie à une session neuve du rôle Evaluator, en
lecture seule, qui l'utilise en boîte noire. Ne concerne qu'un ticket d'un
convoi qui porte la **marque du nouveau flux**.

```bash
./bin/ticket-evaluation show <convoi> <ticket>                 # les passes, la demande ouverte, les rôles, les produits encore lancés
./bin/ticket-evaluation verdict <convoi> <ticket>              # le verdict, recalculé : favorable ou non, et pourquoi
./bin/ticket-evaluation settle <convoi>                        # lancé par ./bin/convoy-advance à chaque passe
./bin/ticket-evaluation brief <convoi> <ticket>                # la session Evaluator (formule mol-ticket-evaluation)
./bin/ticket-evaluation record <convoi> <ticket> --file <f>    # la session Evaluator
```

- **Sans évaluation favorable, pas de fusion** : `./bin/spec-integration
  merge` laisse le ticket dans `waiting` tant que son évaluation n'est pas
  favorable à la pointe. Une évaluation absente, en cours ou sans résultat
  ne vaut pas accord.
- **Un état pour la ligne de démonstration** (ADR-0030 L4 : les tests de
  critère gelés prouvent les critères ; seul un critère qu'une attente
  validée compare garde un état) : « observé » (`observed`), « non
  observé » (`not_observed`) ou « inobservable » (`unobservable`), avec une
  **preuve capturée** par `./bin/evidence-capture` sur le produit lancé. Un
  état sans preuve valide, une preuve prise ailleurs que sur ce produit, une
  ligne reformulée : refusés.
- **Le verdict est calculé par du code** : l'Evaluator ne rend jamais de
  verdict global. Favorable seulement si tout est « observé » avec preuve
  au commit de tête.
  - « non observé » : défavorable, retour à l'auteur.
  - « inobservable » par le critère : Planning Exception — une demande dans
    `./bin/escalation-door list`, le ticket et ceux qui l'attendent sont
    parqués. Un critère ne se dispense jamais, sauf par l'option `a` de
    cette demande : l'élément est jugé prouvé par son test de critère et
    l'évaluation suivante le compte (af-ten1sp). L'option `c` la lève sans
    rien juger prouvé : l'évaluation est refaite sur les produits relancés,
    pour un inobservable que l'usine a causé (af-npz9v1.38).
  - « inobservable » par l'environnement : panne, non comptée comme refus ;
    l'évaluation est refaite une fois, puis le ticket est arrêté.
- **Ce que reçoit l'Evaluator** (`brief`) : la ligne de démonstration, les
  seuls critères qu'une attente validée compare, les adresses des produits
  lancés. Ni le Handoff, ni le
  diff, ni le dépôt.
- **`prefactoring`** : aucune session d'Evaluator. Du code lance le
  produit, capture la réponse de sa sonde, et enregistre qu'il démarre.
- **Fournisseur de l'Evaluator** : inscrit sur le ticket avec celui de
  l'auteur. S'il est le même, la mention « même fournisseur que l'auteur »
  est enregistrée, jamais omise. Si un autre fournisseur est déclaré et
  disponible pour le rôle, l'évaluation n'est pas lancée sur celui de
  l'auteur (`./bin/provider-failover` règle le rôle).
- **Évaluation sans résultat** : une relance, puis le ticket est arrêté et
  apparaît **une seule fois** dans `./bin/escalation-door list`. Le délai
  d'un lancement est `evaluation.timeout_seconds` dans
  `config/delivery-flow.json` (3600 s, valeur sans base mesurée).
- **Produits lancés** : une fois par jeu de données nommé du profil ; un
  profil qui n'en nomme aucun est refusé et rien n'est lancé. Ils restent
  debout entre deux passes, le temps de l'évaluation, puis du code les
  arrête. `show` liste ceux qui tournent encore (`live`).
- **Ne jamais dispatcher `mol-ticket-evaluation` à la main** ni écrire
  `gc.flow.evaluation` : seul `./bin/ticket-evaluation` le fait, par
  `./bin/dispatch-door` et `./bin/convoy-state`.
- **Limites** : rien ne lève encore un arrêt ; la session neuve d'auteur
  après un « non observé » et son tour unique sont tenus par
  `./bin/correction-round` ; les contrôles de
  fidélité d'un ticket qui touche un écran sont `./bin/prototype-fidelity`.

Détail : `docs/TICKET_EVALUATION.md`.

---

