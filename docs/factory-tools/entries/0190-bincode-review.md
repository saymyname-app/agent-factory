## `./bin/code-review` — qui relit le code d'un ticket avant sa fusion ?

Un **relecteur**, jamais l'auteur (Spec af-wf4w5r §6, §8, T14). Dès qu'un
ticket est terminé et vert à la pointe de sa branche, le flux envoie son
diff commité à une session neuve du rôle relecteur, en lecture seule, qui
appelle le `code-review` de Matt inchangé. Ne concerne qu'un ticket d'un
convoi qui porte la **marque du nouveau flux**.

```bash
./bin/code-review show <convoi> <ticket>                      # les passes, la demande ouverte, le verdict, les modèles
./bin/code-review settle <convoi>                             # lancé par ./bin/convoy-advance à chaque passe
./bin/code-review brief <convoi> <ticket>                     # la session relecteur (formule mol-code-review)
./bin/code-review record <convoi> <ticket> --file <f>         # la session relecteur
./bin/code-review respond <convoi> <ticket> --file <f>        # la session neuve d'auteur, après un refus
```

- **Sans verdict favorable, pas de fusion** : `./bin/spec-integration merge`
  laisse le ticket dans `waiting` tant que sa revue n'est pas favorable à la
  pointe. Une revue absente, en cours, plantée ou sans sortie ne vaut pas
  accord.
- **Un constat ne bloque que s'il cite** une ligne de la Spec, du ticket ou
  une règle écrite du dépôt, et que la ligne citée s'y trouve. Un constat de
  goût donné comme bloquant est enregistré **non bloquant**, avec la raison.
- **Questions fermées sur les tests** : posées par du code (fichier de test
  hors des tests de critère gelés : passe-t-il par un seam listé ? test de
  critère amendé : observe-t-il encore son critère ?). Un « non » est un
  Blocking Finding.
- **Chaque Blocking Finding** reçoit « corrigé » (avec le commit) ou
  « contesté » (avec la raison) par `respond` ; une **seconde** session
  relecteur juge cette liste fermée contre le diff de correction.
- **Ce que reçoit le relecteur** (`brief`) : le diff, la Spec, le ticket, les
  standards du dépôt, les relevés des scripts. Ni le Handoff, ni la prose de
  l'auteur (sujets de commit et raison d'amendement retirés).
- **Modèles par rôle** : le modèle de l'auteur et celui du relecteur sont
  inscrits sur le ticket. S'ils sont identiques, ou si l'un n'est pas connu,
  la mention est enregistrée avec la revue, jamais omise.
- **Revue plantée ou sans sortie** : une relance, puis le ticket est arrêté
  et apparaît **une seule fois** dans `./bin/escalation-door list`. Le délai
  d'un lancement est `code_review.timeout_seconds` dans
  `config/delivery-flow.json` (3600 s, valeur sans base mesurée).
- **Le verdict est calculé par du code** : le relecteur ne rend jamais de
  verdict global.
- **Ne jamais dispatcher `mol-code-review` à la main** ni écrire
  `gc.flow.code_review` : seul `./bin/code-review` le fait, par
  `./bin/dispatch-door` et `./bin/convoy-state`.
- **Limites** : rien ne lève encore un arrêt ; la session neuve d'auteur qui
  corrige, son tour unique et l'arrêt d'un ticket encore refusé sont tenus
  par `./bin/correction-round`.

Détail : `docs/CODE_REVIEW.md`.

---

