## `./bin/factory-revive` — relancer un superviseur que personne n'a arrêté exprès

**Un arrêt non demandé est relancé en 7 minutes au plus** (af-v9t5vz). Le
2026-10-08 à 04:27 (Paris), le script d'essai d'un ouvrier a lancé `gc
supervisor stop` sur l'usine vivante. systemd a vu un arrêt propre (code 0)
et n'a rien relancé, `bin/factory-boot` ne tourne qu'à l'ouverture de session
Windows, et tous les orders sont morts avec le superviseur : l'usine est
restée arrêtée 56 minutes.

```bash
./bin/factory-revive check       # verdict seul, ne touche à rien (sort 1 si arrêt non demandé)
./bin/factory-revive run         # ce que le minuteur appelle
./bin/factory-revive install     # écrit et active le minuteur systemd utilisateur (une fois, sur accord de l'opérateur)
./bin/factory-revive uninstall   # le retire
```

Ce qui distingue un arrêt non demandé d'un arrêt délibéré : l'arrêt délibéré
du runbook (§2) commence par `gc stop`, qui retire la cité de la liste du
superviseur (`~/.gc/cities.toml`).

| État constaté | Ce que fait `run` |
|---|---|
| le superviseur répond | rien |
| superviseur arrêté, cité absente de la liste | rien : arrêt délibéré (une ligne au journal, une seule) |
| superviseur arrêté, cité encore dans la liste, toujours vrai 45 s plus tard | `bin/factory-boot`, puis un ticket `maintenance` et une escalade « Mayor d'abord » par `bin/escalation-door` (promue à Benjamin au bout de 2 h si rien n'est élucidé) |
| `factory-boot` n'a pas ramené le superviseur | sort 1, nouvel essai au passage suivant |

- **Délai** : minuteur toutes les 5 min + 45 s de confirmation + le temps de
  `factory-boot` (environ 1 min), soit 7 minutes au plus.
- **Ne défait jamais un arrêt délibéré** : il ne relance que par
  `factory-boot`, qui laisse suspendue une cité suspendue ; il n'arrête, ne
  suspend et ne désenregistre rien.
- **Pourquoi un minuteur systemd et pas un order** : un order tourne dans le
  superviseur, donc pas quand il est arrêté.
- **Ce qu'il ne voit pas** : un `gc stop` de la cité vivante lancé par erreur
  (il ressemble à un arrêt délibéré), et une usine qui tourne mais n'avance
  pas (c'est le rôle de `factory-watchdog` et de la ligne « Usine à l'arrêt ? »
  du cockpit). Si le minuteur lui-même ne tourne pas, il reste l'alerte
  externe « Usine muette » du cockpit.
- **Journal** : `.gc/runtime/factory-revive.log`.

Le même correctif fait démarrer le superviseur par son unité systemd dans
`bin/factory-boot` quand elle est installée, au lieu de `gc supervisor
start` : ce dernier lance un superviseur hors de l'unité, que `gc start`
réactive ensuite et qui redémarre alors en échec toutes les 5 secondes.

Côté tests : aucun test n'arrête une cité ou un superviseur autrement que par
`isolated_city_stop` (`tests/lib/isolated-city.sh`), qui refuse si `GC_HOME`
n'est pas dans le répertoire de l'essai. Le même fichier efface ce répertoire
(`isolated_city_remove`) : il réessaie en tuant les processus dont le
répertoire courant ou l'environnement y pointe encore, faute de quoi un essai
réussi échouait sur « Directory not empty » (af-foq4t7).

Tests : `tests/factory-revive-test.sh`, `tests/factory-boot-supervisor-test.sh`,
`tests/isolated-city-stop-guard-test.sh`. Runbook :
`docs/RUNBOOK_STOP_AND_RESTART.md` §3.

---
