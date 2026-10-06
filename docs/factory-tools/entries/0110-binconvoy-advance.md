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
- **Formule de démarrage** : `start.formula` dans le même fichier. Tant qu'elle
  vaut `null`, la commande refuse de démarrer quoi que ce soit (sortie 1).
- **Sorties** : 0 passe faite ; 1 refus (réglage, tracker, ou porte de dispatch
  qui refuse un ticket, nommé sous `refused`) ; 3 « état sans règle » : rien
  n'est démarré dans ce convoi ; 4 « pas un convoi du nouveau flux ».
- **Ne jamais lancer `gc convoy control <ticket>`** : le dispatcher de contrôle
  de Gas City ne démarre pas les tickets d'un convoi, il ferme le bead qu'on lui
  donne s'il n'est pas un bead de contrôle (essai du 2026-10-06, Gas City 1.4.1).

Détail : `docs/CONVOY_ADVANCE.md`.

---

