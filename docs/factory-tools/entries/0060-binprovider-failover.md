## `./bin/provider-failover` — quel modèle fait tourner l'usine

Quand un quota GPT ou Claude est atteint, l'usine **bascule seule** sur le
fournisseur suivant, et **revient seule** quand le quota se réinitialise. Plus
personne n'a à éditer `city.toml` ni à se souvenir de « revenir à Codex ».
Détails et règles : `decisions/ADR-0018-automatic-provider-failover.md`.

**Réglages manuels** (réversibles, zéro token) :

```bash
./bin/provider-failover status                    # qui tourne sur quoi, et pourquoi
./bin/provider-failover tick --dry-run            # ce que ferait le prochain passage
./bin/provider-failover set --action mark --by <qui> \
    --args '{"pool":"anthropic","until":"2026-09-16T16:50:00Z"}'
./bin/provider-failover set --action clear --by <qui> --args '{"pool":"anthropic"}'
./bin/provider-failover apply                     # régénère city.provider.toml
```

Trois fichiers, un seul écrivain :

| Fichier | Rôle | Versionné |
|---|---|---|
| `config/provider-policy.json` | pools, fournisseurs, chaîne de repli par cible | oui |
| `.gc/provider-state.json` | limites détectées, réglages manuels, historique | non |
| `city.provider.toml` | surcouche **générée**, incluse par `city.toml` | non |

**Ne jamais éditer `city.provider.toml` à la main**, ni le fournisseur dans
`city.toml` (ce n'est plus qu'une valeur de secours). **Ne jamais supprimer**
`city.provider.toml` : sans lui la config ne charge plus — le garde-fou le
régénère, mais autant ne pas lui en donner l'occasion.

Un quota s'applique à un **pool** : les trois profils Claude partagent le même
compte, donc une limite Claude les épuise tous. Les quatre profils Codex
(`codex` Sol, `codex-astra`, `codex-astra-readonly`,
`codex-luna`) partagent le pool OpenAI Standard ; aucun ne configure
`service_tier=fast` ou `priority`.

Profils primaires (af-npz9v1.51) : travail courant et auteur de ticket sur
GPT-6.1 Sol/medium ; relecteur de code significatif sur GPT-6 Astra/high en
lecture seule ; revue UX difficile sur GPT-6 Astra/high. Luna/high est un
profil explicite pour une classe simple future, mais n'est assigné à aucun
rôle : l'Evaluator reste sur Claude lecture seule afin d'être d'un autre
fournisseur que l'auteur Sol. L'auteur Sol et le relecteur Astra restent de
modèles distincts. Les chaînes modifiées gardent leur repli Claude antérieur.

Si **aucun** fournisseur ne reste pour aucun pool (épuisement total, O08,
af-harft), `bin/dispatch-door` (et donc `bin/factory-work-dispatch`) refuse
tout nouveau dispatch avec une raison explicite tant que
`./bin/provider-failover status --json` lit `total_exhaustion.active`. Le
`tick` périodique dépose alors **une seule** ligne NEEDS BENJAMIN (un bead
dédié, via `escalation-door benjamin`) ; dès qu'un fournisseur redevient
disponible, le même `tick` referme ce bead et efface l'état tout seul — le
dispatch reprend au prochain appel sans intervention humaine.

La tâche planifiée `provider-failover` tourne toutes les 2 min (~1 s, < 1 s de
CPU : les écrans sont lus via tmux, pas via `gc session peek` qui coûtait 8 s).

### L'ouvrier du dépôt Factory

Pour une modification ordinaire du dépôt `agent-factory`, le Mayor lance :

```bash
./bin/factory-work-dispatch af-xxxxx
./bin/factory-work-dispatch af-repair --technical-request af-convoi af-ticket
# réparation déjà routée ou livrée : enregistrer le lien sans la redispatcher
./bin/factory-work-dispatch af-repair --technical-request af-convoi af-ticket --link-only
```

Cette porte choisit elle-même `factory-worker`, `mol-do-work` et
`--reassign`. Elle ne propose volontairement aucun choix de cible :
`workspace` est la **classe de fournisseur** pilotée par le repli automatique,
pas un agent Gas City, et `bd.dog` ne fait que la maintenance Dolt. L'ouvrier
Factory ne fixe aucun fournisseur dans son `agent.toml`; il prend donc celui
que `provider-failover` a résolu pour `workspace` (GPT-6.1 Sol/medium
aujourd'hui, puis le repli configuré si nécessaire). `--technical-request` est l'entrée autorisée
qui lie un défaut de l'usine au parcage exact qu'il répare ; la levée et la
reprise restent ensuite la propriété de `convoy-advance`.

Au plus deux sessions `factory-worker`, chacune dans son worktree isolé,
peuvent être actives sur ce rig. Leur protocole réclame
chaque étape avec `gc hook --claim --json`, puis réclame immédiatement la
suite du même groupe avant de se drainer. Ainsi le worktree, l'implémentation
et l'ouverture de PR restent dans la même session logique; une cible de
maintenance ne peut plus être sélectionnée par cette porte. Le bead de travail
reste `in_progress` mais sans assignee entre les étapes : sinon le hook le
reprendrait avant l'étape suivante du graphe. Pour annuler ce
choix, revenir sur le rôle, la porte et leur documentation : la politique de
fournisseurs reste indépendante.

---
