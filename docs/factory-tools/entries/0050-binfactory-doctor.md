## `./bin/factory-doctor` — « y a-t-il quelque chose que je puisse réparer ? »

`gc doctor` rapporte sur toute la pile, la nôtre **et ses dépendances**. Ce
script relit sa sortie JSON et trie chaque problème par son **origine réelle**,
pour que le signal ne se noie pas dans ce qui ne nous appartient pas.

```bash
./bin/factory-doctor          # seulement ce qui est actionnable ici
./bin/factory-doctor --all    # détaille aussi ce qui est écarté, et pourquoi
./bin/factory-doctor --json
```

Quatre verdicts, **tous redérivés des preuves à chaque exécution** :

| Verdict | Signification |
|---|---|
| `ACTIONABLE` | problème bloquant dont les preuves sont dans ce dépôt — **le seul qui fait sortir en non-zéro** |
| `DID NOT ANSWER` | le contrôle a expiré. Il n'a pas échoué : il n'a pas répondu. Toujours affiché, jamais compté comme une panne. À poursuivre **seulement s'il persiste** |
| `UPSTREAM` | bloquant, mais tous les chemins cités sont dans le cache de packs : pas réparable d'ici |
| `ADVISORY` | la sévérité consultative de `gc doctor` — auto-résolutif ou attendu |

**Rien n'est masqué par son nom, et il n'y a aucune liste d'exceptions à
entretenir** — c'est précisément ce genre de liste qui se périme et rend
aveugle. Si l'amont corrige un jour ses formules, le warning cesse simplement
d'apparaître ; s'il se met à citer un fichier de ce dépôt, il repasse
`ACTIONABLE` tout seul, sans que personne n'édite quoi que ce soit.

Comme seul `ACTIONABLE` sort en non-zéro, ce script est sûr à câbler dans un
contrôle automatique.

### Pourquoi il existe : les 34 warnings de formules

Enquête du 2026-09-16, faite une fois pour ne plus jamais être refaite :

- Les **34** warnings `formula-requirements` sont **une seule et même cause** :
  `contract = "graph.v2"`, déprécié.
- **Aucun n'est dans ce dépôt.** Tous sont dans les formules du pack `gascity`,
  en lecture seule sous `~/.gc/cache/repos/`.
- **Mettre le pack à jour n'y changerait rien** : la branche `main` de
  `gastownhall/gascity-packs` porte encore la forme dépréciée, 88 occurrences,
  et notre copie épinglée en est identique.
- `daemon.formula_v2` est **déjà** à `true` de notre côté. Rien n'est cassé.

Il n'y a donc rien à corriger ici, et rien à attendre d'une mise à jour. Le seul
levier restant est de le signaler à l'amont. En attendant, le tri les écarte
pour qu'ils cessent de coûter une enquête à chaque session.

### `order-firing-current` intermittent : bruit de bord, pas une panne

Mesuré le 2026-09-16 : `gc doctor --json` prend 19 à 26s par exécution ici
(jusqu'à 105s sous 6 `gc order check` concurrents), et `order-firing-current`
lit « last fired » à la minute près. Pour un ordre au rythme d'1 minute, ce
budget est plus petit que le temps de scan du contrôle lui-même — un ordre
parfaitement sain peut se faire lire à « 1m depuis le dernier tir, attendu
toutes les 1m » et déclencher `(overdue)` par pur effet de bord, avant de
redevenir propre au cycle suivant.

Douze exécutions de `gc doctor --json` coup sur coup contre l'usine réelle :
9 en warning, 3 propres. Dans les 9, **chaque** ordre signalé `(overdue)`
avait un intervalle attendu d'1 minute (`dolt-health`, `beads-health`,
`gate-sweep`, `order-tracking-sweep`, `mayor-campaign`), jamais deux fois le
même ordre d'affilée, et jamais plus de 2× son propre budget (le pire :
« 2m depuis, attendu 1m »). Aucun ordre à intervalle plus long n'a jamais été
signalé — pas même ceux frôlant leur échéance (`jsonl-export` à « 14m/15m »
propre à un tir, « 15m/15m » propre au suivant). Un vrai ordre bloqué
s'annonce par un grand multiple de son propre intervalle, pas un frôlement
d'un cycle (`mol-dog-backup` à 273min sur un budget de 360min/6h n'est
jamais signalé).

`bin/factory-doctor` reclasse donc ce cas précis en `DID NOT ANSWER` :
seulement quand tous les ordres marqués `(overdue)` ont un intervalle attendu
≤ 2 minutes et sont à moins de 2,5× ce budget — sinon (intervalle plus long,
ou dépassement massif), le contrôle reste `ACTIONABLE`. Voir
`order_firing_is_boundary_noise()` dans `bin/factory-doctor` et les tests
associés dans `tests/factory-doctor-test.py`.

