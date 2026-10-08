## `./bin/ci-runner` — la CI de l'usine tourne-t-elle sur le PC, et le runner est-il debout ?

**Le côté opérateur du runner auto-hébergé** (af-r1ymfm). Un *runner* est la
machine qui exécute les jobs de GitHub Actions ; celui-ci est le PC lui-même,
donc 0 minute facturée. Chaque job tourne dans un conteneur jetable, sous un
utilisateur Linux sans droits (`factory-ci`), limité à 4 cœurs et 4 Go.

```bash
./bin/ci-runner status            # services, où vont les runs, runner vu par GitHub, runs en attente
./bin/ci-runner pause             # plus de nouveau job (celui en cours se termine)
./bin/ci-runner pause --now       # tue aussi le job en cours : son run finit rouge
./bin/ci-runner resume
./bin/ci-runner mode github       # renvoie la CI sur les runners GitHub, facturés
./bin/ci-runner mode self-hosted  # la ramène sur le PC
```

- **Pause** : c'est le geste de l'opérateur (un jeu, par exemple) ; personne
  ne reprend à sa place, et `./bin/factory-doctor` la classe ADVISORY.
- **Runner arrêté** : les PR attendent, `Tests` reste « en file » ;
  `./bin/factory-doctor` le signale ACTIONABLE avec la réparation.
- **`mode github`** dépense des minutes facturées : décision de Benjamin,
  jamais automatique.
- **`install`, `remove`, `broker`** : installation et service ; la moitié
  root est `config/ci-runner/root-install`.
- **Ce que le script ne fait jamais** : afficher, journaliser ou stocker une
  configuration de runner.

Détail : `docs/OPERATIONS.md`, « Factory CI on the host's own runner » ;
frontière de confiance : `docs/SECURITY.md`, même titre.

---
