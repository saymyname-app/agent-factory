## `./bin/factory-resources` — la capacité de l'hôte

Répond à « l'usine a-t-elle de quoi travailler, et laisse-t-elle vivre
Windows ? ».

```bash
./bin/factory-resources
```

Il lit la mémoire et le swap du guest, le plafond CPU déclaré dans
`%USERPROFILE%\.wslconfig`, et les plus gros consommateurs de mémoire.

**Quand le lancer** : quand la machine rame, avant d'augmenter la concurrence
des agents, et après toute modification de `.wslconfig`. C'est lui qui prouve
qu'un plafond a bien été pris en compte.

Les plafonds actuels et leur justification sont dans
`RUNBOOK_STOP_AND_RESTART.md` §7. Modifier `.wslconfig` exige un
`wsl --shutdown` pour prendre effet.

---

