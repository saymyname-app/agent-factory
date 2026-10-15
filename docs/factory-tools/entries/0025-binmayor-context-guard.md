## `./bin/mayor-context-guard` — la conversation du Mayor a-t-elle trop grossi ?

Filet de la règle « Handoff » du prompt du Mayor (af-3ewcxf : une conversation
a atteint 365k tokens). L0, zéro token, lancé par `orders/mayor-context-guard.toml`
toutes les 10 min.

```bash
./bin/mayor-context-guard --check   # une ligne JSON : la décision, sans rien toucher
```

Il lit la session `mayor` (`gc session list --json`, champ `session_key` = id
de conversation Claude), puis son transcript
`~/.claude/projects/<work_dir>/<session_key>.jsonl` : tokens de contexte = usage
du dernier message assistant (`input` + `cache_read` + `cache_creation`), âge =
premier horodatage. Au-delà de **150k tokens** (`MAYOR_CONTEXT_GUARD_TOKENS`) ou
**8 h** (`MAYOR_CONTEXT_GUARD_MAX_AGE_HOURS`), et seulement entre deux tours
(dernier `stop_reason` = `end_turn`) et sans personne attaché, il lance
`gc session reset mayor` (conversation neuve, même bead, alias et courrier) puis
envoie au Mayor un mail `HANDOFF:` (champs OPEN_MAIL/OPEN_DECISIONS/IN_FLIGHT/NEXT
marqués inconnus). Un reset en échec n'est pas enregistré et sort en 1 (l'ordre
échoue, la passe suivante réessaie).
Une seule rotation par conversation (`.gc/runtime/mayor-context-guard-state.json`),
journal dans `var/mayor-context-guard.log`, jamais une autre session.

Pourquoi pas `gc handoff --target mayor` ni `max_session_age` : tous deux
redémarrent la session selon son `wake_mode`, et le Mayor a celui par défaut
(`resume`) — il reprendrait la même conversation trop longue. `gc session reset`
est la primitive documentée de redémarrage à neuf.

---
