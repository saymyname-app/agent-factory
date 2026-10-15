## `./bin/factory-metrics` — les chiffres d'une journée de l'usine

Une ligne JSON par jour dans `var/factory-metrics.jsonl` (af-lw581v). L0, zéro
token, lancé chaque nuit à 00:30 par `orders/factory-metrics.toml` pour la
veille (jour calendaire local). Lecture seule partout ailleurs.

```bash
./bin/factory-metrics --print                  # hier, sur la sortie seulement, sans rien ajouter
./bin/factory-metrics --day 2026-10-14 --print # un jour donné
```

| Champ | Source |
|---|---|
| `tickets_merged`, `merged_tickets` | tickets dont `gc.flow.merge` vaut `merged` avec un `at` dans la journée (`gc bd list`, magasin HQ) |
| `attempts_per_ticket`, `attempts_mean` | 1 + `gc.flow.counter.resumes` de chaque ticket fusionné (les rondes de correction y sont comptées) |
| `tokens_total` | usage (entrée, sortie, cache lu et créé) des messages assistant de la journée, dédoublonnés par id, dans `~/.claude/projects/*/*.jsonl` — **toutes** les sessions, pas seulement le travail des tickets |
| `tokens_per_merged_ticket` | `tokens_total / tickets_merged` : un ratio de la journée, pas une attribution par ticket |
| `order_runs`, `order_failure_rate` | événements `order.completed` / `order.failed` de la journée dans `.gc/events.jsonl` ; taux = échecs / (réussites + échecs), par ordre et au total |
| `sessions_over_150k` | transcripts dont le plus grand contexte d'un tour de la journée (entrée + cache lu + cache créé) dépasse 150 000 |
| `evaluation_duration_seconds` | toujours `null` : une ronde de `gc.flow.evaluation` ne garde que sa fin (`at`), la demande qui portait le début est effacée à l'enregistrement |

Un champ dont la source manque (ou qui n'a pas de sens ce jour-là, par exemple
aucun ticket fusionné) vaut `null` et figure dans `unavailable`, sa cause dans
`unavailable_reasons` — jamais un zéro inventé.

---
