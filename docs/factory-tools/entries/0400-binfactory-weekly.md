## `./bin/factory-weekly` — le tableau hebdomadaire de la cible

Les seuils de `FACTORY_OBJECTIVE.md` qui ont une source vivante, pour une
semaine ISO (lundi 00:00 → lundi 00:00, Paris), calculés par du code
(af-q55qqx.2, plan J2). L0, zéro token, lecture seule hors de sa sortie.
Lancé chaque lundi à 06:30 par `orders/factory-weekly.toml`, qui écrit
`var/weekly/<semaine>.json` (contrat `agent-factory-weekly-measure/v1`, lu
par le Cockpit) et `var/weekly/<semaine>.md` (le tableau).

```bash
./bin/factory-weekly                     # la dernière semaine complète, en tableau
./bin/factory-weekly --week 2026-W46 --json
```

| Mesure | Source |
|---|---|
| `slices_per_working_day` | PR fusionnées sur la branche produit (`promotion_branch.from`, `dev`) des rigs de chaque descripteur de projet autre que l'usine (`gh`), divisées par les jours lundi–vendredi |
| `lead_time_median_hours`, `lead_time_p85_hours` | création du bead → fusion de ces PR ; le bead est le premier id connu (préfixes de `.beads/routes.jsonl`) de la branche, puis du titre |
| `maintenance_share` | PR de l'usine fusionnées sur `main` / toutes les PR fusionnées |
| `human_requests_max_per_day` | courriers `NEEDS BENJAMIN:` d'`escalation-door` vers `human` (`mail.sent` de `.gc/events.jsonl` et des archives que gc a tournées depuis le début de la semaine, dédoublonnés par `seq`), pire jour de Paris ; une relance compte, elle le sollicite |
| `product_cost_share` | tokens des transcripts Claude (`~/.claude/projects`, dédoublonnés par id de message) et Codex (`~/.codex/sessions`, événements `token_count`, Mayor compris), pondérés par `config/token-cost-weights.json` ; un transcript est du produit quand il nomme plus souvent les chemins, dépôts et ids de beads du produit que ceux de l'usine |

Pas `.gc/usage.jsonl` : Gas City (amont) l'écrit « au moins une fois » par
fait, avec une `idempotency_key` que son propre lecteur `gc costs`
dédoublonne (2 400 lignes répétées au 17/11/2026, 48 495 faits distincts).
Il ne voit pas les sessions que gc n'ingère pas (le Mayor sur Codex depuis le
15/09/2026, les sessions interactives) et ne sait pas séparer produit et
usine (ses `run_id` sont des wisps purgés). Lire ce fichier, c'est
dédoublonner par `idempotency_key`, jamais compter ses lignes.

Récidives par règle (af-56yoam.1, sans seuil du tableau) : pour le mois de
la semaine (Paris), `observed.rule_recurrence` donne les glissements, les
répétitions prévues et les premières corrections par règle concrète de
`docs/DEFECT_CLASSES.md`, lues par `lib/defect_classes.py` dans
`docs/defect-rules-baseline.tsv` puis sur la ligne `Règle :` des PR plus
récentes. Il les juge contre l'objectif D1 tel que figé le 23/11/2026
(af-56yoam.5), sous `observed.rule_recurrence.d1` :

- `period_share` : la part des glissements parmi les PR de correction (les
  lignes de la base hors `aucune`, puis les lignes `Règle :`) du 01/12 au
  20/12/2026, coupée à la fin de la semaine ; objectif au plus 30 % ;
  `reference_share` : 86/140 = 61 % du 01/11 au 23/11/2026 ;
- `closed_rules` et `closed_slips` : les règles marquées « Fermée le
  JJ/MM/AAAA par #N. » dans le registre (point de passage unique livré) et
  chaque glissement sur l'une d'elles fusionné après le jour de sa
  fermeture ; objectif 0 ;
- `gate_refusals` : les PR dont le contrôle « Maintenance form » a échoué au
  moins une fois depuis le 01/12 (dates de création des exécutions, UTC de
  GitHub) ; dire lesquels étaient injustifiés reste un jugement de la revue ;
- la revue du 21/12/2026 (af-56yoam.4) et son critère d'arrêt (Benjamin,
  24/11/2026) : une part encore au-dessus de 45 %, ou plus d'un refus sur
  trois injustifié, retire la porte obligatoire.

Une PR sans ligne ni place dans la base est comptée « sans règle ».

Une mesure sans source vaut `null`, état `unmeasured`, avec sa raison ;
`not_measured` nomme ce que l'outil ne calcule pas (âge des branches
d'intégration, demandes hors liste fermée, défauts échappés, sessions du PC
Windows).

---
