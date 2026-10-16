## `./bin/ticket-author` — qui tient la séquence d'un ticket du nouveau flux ?

Des scripts, jamais la parole de l'agent (Spec af-wf4w5r §0 règle 4, §4, §5,
T12). Un ticket d'un convoi qui porte la **marque du nouveau flux** est
travaillé par une session auteur neuve, dans son worktree, sur une branche
partie de la branche d'intégration de la Spec. La formule
`mol-ticket-author` enchaîne cinq étapes ; à chaque fermeture d'étape, Gas
City lance un contrôle, et c'est lui qui laisse démarrer la suivante.

```bash
./bin/ticket-author locate <ticket>
./bin/ticket-author start <convoi> <ticket>
./bin/ticket-author demonstrate <convoi> <ticket> --repo <worktree> --profile <profil> --dataset <jeu> -- <commande>
./bin/ticket-author gate <convoi> <ticket> --step workspace|red|code|demonstration|exit
./bin/ticket-author release <convoi> <ticket>
```

- **Personne ne lance la formule à la main** : `./bin/convoy-advance` démarre
  chaque ticket prêt (`start.formula` dans `config/delivery-flow.json`).
- **Étapes et contrôles** : prise du ticket (worktree, branche, session) ;
  rouge prouvé puis tests gelés (sans relecture : la revue de code les lit,
  ADR-0030 L3) ; tests verts à la pointe de la branche ; ligne
  de démonstration capturée sur le produit lancé, au commit de tête ; sortie
  de ticket enregistrée.
- **Contrôle refusé** : l'étape revient à la session avec le motif. Au bout
  de trois refus, la séquence échoue et les étapes restantes sont sautées :
  le code ne démarre jamais sans rouge prouvé.
- **Démonstration** : `demonstrate` lance le produit par son vrai point
  d'entrée et capture ce que l'auteur demande ; un commit de plus demande une
  nouvelle capture. Sans cette preuve, la sortie « terminé » est refusée.
- **Scope** : le Declared Scope ne borne rien. Un fichier touché hors scope
  est inscrit par du code dans les relevés du compte rendu.
- **Sous-agents** : une session auteur ne peut lancer que des sous-agents de
  lecture (`Explore`, `Plan`) ; tout autre lancement est bloqué par un hook.
  `./bin/role-adoption-trial run --role author` le prouve sur une session
  réelle. Limite : un sous-agent de lecture garde un shell.
- **Sorties** : 0 fait ou étape prouvée ; 1 refus ; 4 « pas un convoi du
  nouveau flux ».
- **Ticket arrêté** (critère déjà vert, second refus de la relecture des
  tests, relecture sans résultat) : chaque contrôle le refuse, la séquence
  échoue et rien n'en est fusionné.
- **Pas ici** : la revue de code (`./bin/code-review`) et la Ticket
  Evaluation sur le produit lancé (`./bin/ticket-evaluation`), que le flux
  envoie après la sortie « terminé » ; la porte de fin de ticket
  (`./bin/ticket-end`) ; la reprise d'un ticket, envoyée par
  `./bin/convoy-advance` à une session neuve sur la formule
  `mol-ticket-resume`, qui prend le ticket par le même `start`
  (`docs/CONVOY_ADVANCE.md`).

Détail : `docs/TICKET_AUTHOR.md`.

---
