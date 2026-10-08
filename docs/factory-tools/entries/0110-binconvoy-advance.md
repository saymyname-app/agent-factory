## `./bin/convoy-advance` — qui démarre les tickets d'un convoi du nouveau flux ?

Du code, pas le Mayor (Spec af-wf4w5r §0 règle 3, T04). Pour un convoi qui
porte la **marque du nouveau flux** (`docs/CONVOY_STATE.md`), une passe démarre
chaque ticket ouvert, jamais démarré, dont tous les bloqueurs sont fermés, tant
qu'il reste une place sous le plafond N. Chaque démarrage passe par
`bin/dispatch-door --convoy`, qui l'enregistre. Un convoi sans marque n'est pas
touché : il reste avancé par le Mayor.

```bash
./bin/convoy-advance --all          # une passe sur tous les convois marqués ouverts
./bin/convoy-advance <convoi>       # une passe sur un convoi
./bin/convoy-advance --check-only   # sortie 0 s'il existe un convoi marqué ouvert
```

- **Personne ne la lance à la main** : l'ordre `orders/convoy-advance.toml` la
  lance à chaque tick du contrôleur (toutes les 20 à 30 secondes), seulement
  s'il existe un convoi marqué ouvert.
- **Plafond N** : `max_sessions` dans `config/delivery-flow.json`, un seul
  réglage pour toute l'usine, partagé entre les Specs. Comptent : chaque session
  vivante d'un rôle de livraison (auteur, relecteur, Evaluator) et chaque ticket
  démarré qu'aucune session n'a encore pris.
- **Formule de démarrage** : `start.formula` dans le même fichier, aujourd'hui
  `mol-ticket-author` (la formule de l'auteur, `docs/TICKET_AUTHOR.md`). À
  `null`, la commande refuse de démarrer quoi que ce soit (sortie 1).
- **Formule de reprise** : `resume.formula` dans le même fichier, aujourd'hui
  `mol-ticket-resume`. Sans ce réglage, un ticket à reprendre est refusé par
  la passe, nommé sous `refused` (sortie 1).
- **Sorties** : 0 passe faite ; 1 refus (réglage, tracker, porte de dispatch
  qui refuse un ticket ou une reprise, nommé sous `refused`, incident ou
  demande groupée impossible à lever) ;
  3 « état sans règle » : rien n'est démarré dans ce convoi ; 4 « pas un convoi
  du nouveau flux ».
- **Convoi arrêté (« état sans règle »)** : un ticket démarré ou fermé hors de
  sa porte, une preuve sans empreinte, un compteur incohérent. La passe ne
  démarre plus rien dans ce convoi et lève **un seul** incident d'usine : la
  ligne « Incident d'usine : <ticket> — <raison> » apparaît dans
  `./bin/escalation-door list`. Réparer, c'est remettre le tracker dans un état
  valide (`./bin/convoy-state show <convoi>` dit ce qui cloche), **jamais**
  avancer ou fermer un ticket à la main. Dès que l'état est valide, la passe
  suivante reprend le convoi, retire l'incident et ferme son bead toute seule.
- **Revue de code avant la fusion** : la même passe envoie le diff de chaque
  ticket terminé et vert à une session du rôle relecteur
  (`./bin/code-review settle`), relance une fois une revue restée sans
  résultat, puis arrête le ticket et le fait remonter dans
  `./bin/escalation-door list`. Rien ne fusionne sans verdict favorable.
- **Évaluation sur le produit lancé avant la fusion** : la même passe lance
  le produit de chaque ticket terminé et vert depuis une copie propre de sa
  branche et l'envoie à une session du rôle Evaluator
  (`./bin/ticket-evaluation settle`) ; pour un `prefactoring`, elle vérifie
  elle-même que le produit démarre. Les produits lancés restent debout
  entre deux passes et sont arrêtés par une passe suivante.
- **Un seul tour de correction, puis l'arrêt** : quand la revue et
  l'évaluation ont toutes deux répondu et que l'une refuse, la même passe
  envoie tous leurs constats à une seule session neuve d'auteur
  (`./bin/correction-round settle`). Encore refusé après ce tour, le ticket
  est arrêté sans fusionner et remonte une fois dans
  `./bin/escalation-door list`.
- **Fermeture par la porte de fin de ticket** : la passe qui fusionne un
  ticket le ferme si ses neuf conditions sont réunies
  (`./bin/ticket-end settle`) ; avant la fusion, elle mesure la fidélité
  d'un ticket d'interface (`./bin/ticket-end fidelity`). Un ticket laissé
  ouvert est listé avec la condition qui manque.
- **Reprises comptées, parcage à la troisième** (T20) : à chaque passe, un
  ticket dont l'auteur doit le reprendre part vers **une** session neuve
  d'auteur, sur la même branche, sur un bead « Reprise — <ticket> ». Causes :
  `interrupted` (sortie « interrompu », ou session terminée sans sortie),
  `returned` (la fusion a rendu le ticket : conflit ou rouge), `unblocked`
  (son `repair` est fermé), `answered` (la demande qui le parquait a sa
  réponse). Chaque reprise est comptée et prend une place sous N. À la
  troisième, toutes causes confondues (celles-ci, le tour de correction, un
  commit après verdict), le ticket est parqué avec ceux qui l'attendent et
  n'est pas relancé ; les autres continuent. Listes `resumed`, `parked`,
  `lifted` dans la réponse.
- **Une seule demande groupée** (T20) : quand il ne reste dans un convoi que
  des tickets parqués, la passe lève **une** ligne pour le convoi dans
  `./bin/escalation-door list`, sur un bead « Demande groupée : convoi … »
  qui nomme chaque ticket parqué et sa cause — jamais une par ticket. Répondre `a`
  relance les tickets aux reprises épuisées (trois reprises de nouveau) ;
  `b` les laisse parqués, la demande ne revient pas.
- **Lever un parcage, c'est répondre** : `./bin/escalation-door repondre` sur
  la demande du ticket (demande opérateur : toute réponse ; Planning
  Exception : seulement l'option qui accepte l'écart) ou sur la demande
  groupée. La passe suivante lève le parcage et reprend le ticket. **Ne
  jamais reprendre ou déparquer un ticket à la main**, ni dispatcher
  `mol-ticket-resume`.
- **Pas repris** : un ticket arrêté ; un ticket dont la session du tour de
  correction est morte sans fermer son bead ; un ticket que la porte de fin
  de ticket laisse en attente (fidélité rouge, condition manquante).
- **Le convoi s'arrête de lui-même dans deux cas** (T21), lus dans `stop` :
  **branche d'intégration rouge** — plus aucun ticket ne démarre ni ne
  fusionne ; la passe publie un seul ticket `repair` qui cite le contrôle
  rouge, par la porte de patch, et ce `repair` est le seul ticket qu'elle
  démarre ; dès que le contrôle est vert (`repair` fusionné, ou branche
  protégée réparée), `./bin/spec-integration` retire le rouge et tout
  repart ; **deux Planning Exceptions ouvertes sur la Spec** — plus aucun
  nouveau ticket ne démarre, ceux en cours finissent ; y répondre
  (`./bin/escalation-door repondre`) relance les démarrages. **Ne jamais
  lever un rouge ni créer un `repair` à la main.**
- **Les bornes se règlent à un seul endroit** : `bounds` de
  `config/delivery-flow.json` — `resumes` (K, 3), `open_planning_exceptions`
  (2). Changer une valeur change le comportement à la passe suivante ; une
  valeur absente ou mal formée est un refus. k (exécutions au vert) se règle
  par projet, dans son profil (`launch.k`).
- **Relecture des tests restée sans résultat** : la même passe la relance une
  fois, puis arrête le ticket et le fait remonter dans
  `./bin/escalation-door list` (`./bin/test-review settle`), sans qu'aucune
  session d'auteur ait à vivre.
- **Seule cette commande démarre un ticket d'un convoi marqué** :
  `./bin/dispatch-door` le refuse sans `--convoy` et le refuse à toute session
  d'agent, Mayor compris.
- **Ne jamais lancer `gc convoy control <ticket>`** : le dispatcher de contrôle
  de Gas City ne démarre pas les tickets d'un convoi, il ferme le bead qu'on lui
  donne s'il n'est pas un bead de contrôle (essai du 2026-10-06, Gas City 1.4.1).

Détail : `docs/CONVOY_ADVANCE.md`.

---

