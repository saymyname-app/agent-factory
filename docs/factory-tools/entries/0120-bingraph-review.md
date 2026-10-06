## `./bin/graph-review` — qui relit un graphe de tickets avant l'approbation de Benjamin ?

Un **relecteur de graphe** : une session neuve du rôle relecteur, en lecture
seule, qui n'a pas écrit le graphe (Spec af-wf4w5r §2, T08). Il ne concerne
qu'un brouillon qui déclare le contrat du nouveau flux (`flow_contract:
new-flow/v1`, `docs/ENTRY_CONTRACT.md`) ; tout autre brouillon est publié
comme avant (sortie 4, « pas un brouillon du nouveau flux »).

```bash
./bin/graph-review review <brouillon> --author-model <modèle>   # lance une passe et attend le verdict
./bin/graph-review remaining <brouillon> --text                # les refus restants, à trancher par Benjamin
./bin/graph-review decide <brouillon> --ticket T07 --decision publish|rework \
  --approved-by <approbateur> --project <projet> --words "<ses mots>"
./bin/graph-review check <brouillon>                           # ce que demande la porte de publication
./bin/graph-review show <brouillon>                            # toutes les passes, demandes et décisions
```

- **Qui la lance** : la session `/to-tickets`, avant l'approbation du
  brouillon, avec le modèle sur lequel elle tourne (`--author-model`).
- **Ce que rend une passe** : un verdict par ticket (démontrable seul,
  critères observables et falsifiables, taille tenable, tickets de même
  surface ordonnés, périmètre déclaré qui inclut les fichiers de branchement)
  et un verdict de graphe (aucune story orpheline, point d'assemblage non
  confisqué, Prototype Fold présent et premier). Le relecteur répond à des
  questions fermées ; le code calcule les verdicts et les lie au digest du
  brouillon.
- **Deux passes, pas trois** : une passe, les corrections avec Benjamin, une
  seule seconde passe. Une troisième demande est refusée (sortie 5) et rend
  la liste des refus restants.
- **Benjamin tranche** : chaque refus restant reçoit sa décision, ticket par
  ticket (`--graph` pour un refus sur le graphe), avec ses mots :
  `publish` (« publier tel quel ») ou `rework` (« à reprendre »). Seul
  l'approbateur humain déclaré du projet est accepté, et jamais sans mots.
- **Ce que la porte de publication refuse** (`./bin/ticket-graph-publish
  bd-publish`, rien n'est écrit) : aucune relecture ; un brouillon modifié
  depuis sa relecture ; une première passe qui refuse ; un refus restant sans
  décision, ou tranché `rework`.
- **Même modèle que l'auteur** : la relecture a lieu mais elle est signalée
  partout (`same_model: true`, « relecture non indépendante… »), jamais en
  silence. Tant que le rôle relecteur n'est essayé que sur Claude, un graphe
  écrit par une session Claude est signalé ainsi.
- **Sorties** : 0 fait ; 1 refus ou impossible, rien n'est écrit ; 4 pas un
  brouillon du nouveau flux ; 5 troisième passe refusée.
- **Ne jamais dispatcher `mol-graph-review` à la main** ni écrire les champs
  `gc.graph_review.*` du brouillon : cette commande est leur seul lecteur et
  leur seul écrivain.

Détail : `docs/GRAPH_REVIEW.md`.

---
