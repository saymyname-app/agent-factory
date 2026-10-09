## `./bin/ticket-exit` — comment un auteur termine-t-il son ticket ?

Par un appel structuré, jamais par du texte libre (Spec af-wf4w5r §5, T11).
Pour un ticket d'un convoi qui porte la **marque du nouveau flux**, chaque
sortie a une destination fixée par du code, et le compte rendu du ticket
(Ticket Handoff) est écrit dans le tracker.

```bash
./bin/ticket-exit exit <convoi> <ticket> --exit finished --repo <worktree> --handoff <compte rendu.json>
./bin/ticket-exit exit <convoi> <ticket> --exit planning_exception --repo <worktree> --handoff <compte rendu.json> --kind semantic|topology --summary "<la question>"
./bin/ticket-exit exit <convoi> <ticket> --exit operator_request --request <demande.json>
./bin/ticket-exit exit <convoi> <ticket> --exit technically_blocked --repair <ticket repair.json>
./bin/ticket-exit exit <convoi> <ticket> --exit interrupted --repo <worktree> [--handoff <partiel.json>]
./bin/ticket-exit read <convoi> <ticket>
./bin/ticket-exit deferral <convoi> <ticket> --repo <worktree>
```

- **Terminé** : refusé, pour un `vertical_slice` ou un `repair`, sans la
  preuve de démonstration capturée sur le produit lancé au commit de tête
  (`./bin/ticket-author demonstrate`) ; refusé sans les quatre rubriques du compte rendu (Fait,
  Écarts, Non fait, Constats hors ticket), chacune avec du contenu ou
  « aucun » ; refusé aussi tant que le diff du ticket porte un marqueur de
  report (TODO, FIXME, « not wired », « à brancher ») qu'aucun « non fait »
  ne déclare avec son fichier.
- **Planning Exception** et **demande opérateur** : le ticket et tous ceux
  qui l'attendent sont parqués ; la demande apparaît dans
  `./bin/escalation-door list`. Les tickets sans lien continuent de démarrer.
- **Planning Exception, le compte rendu d'abord** : refusée sans un compte
  rendu qui a ses quatre rubriques (le refus nomme celle qui manque, rien
  n'est écrit) ; le compte rendu est enregistré avant elle. Si elle nomme
  une ancre du prototype (`--anchor`), la rubrique « Écarts » doit
  mentionner cette ancre, sinon refus.
- **Bloqué technique** : un ticket `repair` est créé par du code et publié
  par la porte de patch ; il bloque le ticket, rien n'est parqué.
- **Interrompu** : la branche est poussée, un compte rendu partiel est
  enregistré. Une session terminée sans sortie est lue comme « interrompu ».
- **Relevés** : commits, fichiers touchés hors Declared Scope, preuve du
  rouge, marqueurs de report. L'auteur ne peut pas les fournir : ils sont
  calculés par le script et scellés dans le magasin de preuves.
- **`read`** : le ticket tel que son auteur le reçoit, avec le compte rendu
  de chaque bloqueur direct fermé.
- **Sorties** : 0 fait ; 1 refus ; 4 « pas un convoi du nouveau flux ».
- **Limite** : le détecteur est un filet par marqueurs ; un report écrit
  sans l'un de ces mots lui échappe. Reprendre un ticket ou lever un parcage
  n'est pas dans cette commande.

Détail : `docs/TICKET_EXIT.md`.

---

