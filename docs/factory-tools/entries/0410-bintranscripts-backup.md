## `./bin/transcripts-backup` — garder les transcripts au-delà de leur purge

Claude Code efface un transcript 30 jours après sa dernière modification
(`cleanupPeriodDays` par défaut). Le 17/11/2026, le plus ancien de
factory-vm datait du 15/10. Le tableau hebdomadaire, les analyses et les
preuves de livraison les lisent (af-q55qqx.2, plan J2). L0, zéro token,
lancé chaque nuit à 03:15 par `orders/transcripts-backup.toml`.

```bash
./bin/transcripts-backup --dry-run   # ce qui serait copié, sans rien écrire
```

- Copie seulement les `*.jsonl` de `~/.claude/projects` et
  `~/.codex/sessions` vers `~/factory-archive/transcripts/{claude-projects,codex-sessions}`,
  jamais les identifiants voisins (`.credentials.json`, `auth.json`) ni un
  autre fichier. L'archive est en 0700, sur le même hôte que sa source.
- Une copie ne part pas avec sa source purgée ; elle reste 90 jours après sa
  dernière modification (`TRANSCRIPTS_BACKUP_RETENTION_DAYS`), puis part.
  Une source plus ancienne n'est pas copiée.
- Sous 10 Go libres (`TRANSCRIPTS_BACKUP_MIN_FREE_GB`), refuse, le dit et
  sort en 1 : l'ordre échoue et se voit.
- Un transcript peut contenir ce qu'une commande a affiché : la copie
  n'expose rien de plus que sa source, au même propriétaire.

---
