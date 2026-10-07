## `./bin/correction-round` — que se passe-t-il quand la revue ou l'évaluation refuse un ticket ?

**Un seul tour de correction, puis l'arrêt** (Spec af-wf4w5r §8, T17). La
revue de code et la Ticket Evaluation d'un ticket terminé tournent en
parallèle sur la même pointe. Quand les deux ont répondu et qu'au moins
l'une refuse, le flux envoie **tous leurs constats à une seule session neuve
d'auteur**. Ne concerne qu'un ticket d'un convoi qui porte la **marque du
nouveau flux**.

```bash
./bin/correction-round show <convoi> <ticket>      # le tour, les dérogations, l'arrêt, les compteurs
./bin/correction-round override <convoi> <ticket> --finding F1.1 --approved-by <approbateur> --words "…"   # Benjamin, sur un ticket arrêté
./bin/correction-round settle <convoi>             # lancé par ./bin/convoy-advance à chaque passe
./bin/correction-round brief <convoi> <ticket>     # la session d'auteur du tour (formule mol-ticket-correction)
```

- **Un tour par ticket**, commun à la revue et à l'évaluation. Il compte
  dans les reprises du ticket (`resumes` et `correction_rounds` dans
  `./bin/convoy-state show`).
- **Une seule session** : tant que l'une des deux n'a pas répondu, aucune
  session ne démarre. Son `brief` contient les Blocking Findings de la
  revue et ce que l'évaluation n'a pas observé.
- **Encore refusé après ce tour, le ticket s'arrête** (`still_refused`) :
  aucun second tour, rien ne fusionne, et le ticket apparaît **une seule
  fois** dans `./bin/escalation-door list`, que la revue, l'évaluation ou
  les deux l'aient refusé.
- **Dérogation** (`override`) : sur un ticket arrêté, l'approbateur humain
  déclaré du projet (`human_approver` de `config/projects/<projet>.toml`)
  peut passer outre **un Blocking Finding de la revue**, avec ses mots, non
  vides. Elle est ensuite lue « dérogation enregistrée ». Refusée de
  quiconque d'autre, sans mots, ou sur un ticket qui n'est pas arrêté.
- **Un critère non observé ne se dispense jamais** : `override --criterion`
  est refusé, et le message renvoie à la Planning Exception
  (`./bin/planning-exception`).
- **La dérogation ne lève rien seule** : le ticket reste arrêté et rien ne
  fusionne ; la porte de fin de ticket (T19) la lira.
- **Ne jamais dispatcher `mol-ticket-correction` à la main** ni écrire
  `gc.flow.correction` ou `gc.flow.overrides` : seul
  `./bin/correction-round` le fait, par `./bin/dispatch-door` et
  `./bin/convoy-state`.
- **Limites** : aucun délai sur la session de correction (une session morte
  sans fermer son bead laisse le ticket en attente ; la reprise est à T20) ;
  rien ne lève encore un arrêt.

Détail : `docs/CORRECTION_ROUND.md`.

---

