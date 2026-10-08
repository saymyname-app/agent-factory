## `./bin/proposal-door` — la porte unique des propositions

Toute proposition d'amélioration passe par cette porte (T07) : jamais de
`gc bd create -l proposal` à la main. Elle refuse l'écriture (aucun bead)
si un champ manque, dépasse 140 caractères sur une ligne ou n'est pas dans
la langue de l'opérateur.

```bash
./bin/proposal-door create '<json>'            # quoi, pourquoi, que_faire[], langue, classe
./bin/proposal-door accepter <bead> <acteur>   # -> à planifier
./bin/proposal-door rejeter <bead> <raison> <acteur>
./bin/proposal-door reporter <bead> <heure> <acteur>
./bin/proposal-door reconvertir <bead> <raison> '<que_faire json>' <acteur>
./bin/proposal-door compte [--classe maintenance|decision|sans_champs]
./bin/proposal-door list   [--classe ...]      # "<bead>\t<classe>\t<état>\t<quoi>"
```

**Deux classes** (ADR-0029, Benjamin 2026-10-07 : « oui pour R1 »), choisies
par le producteur à la création ; en cas de doute, `decision` :

| Classe | Ce que c'est | Ce que fait la porte | Où le Cockpit le montre |
|---|---|---|---|
| `maintenance` | corrige un défaut constaté de l'usine sans changer ce que l'opérateur voit ou doit faire, ni une règle de méthode (ordres, gardes, formules, tests, docs, filtres, seuils) | crée un bead bug (`gc.authorized_by=ADR-0029`, `gc.source=proposal-door`, label `maintenance`), le relie à la proposition, passe la proposition en `prise_en_charge` (tracé) et envoie un mail au Mayor, qui le dispatche par `factory-work-dispatch` | zone santé (« L'usine corrige seule N défaut(s) … ») et journal ; jamais dans « Ce qui t'attend » |
| `decision` | change ce que l'opérateur voit ou doit faire, une règle de méthode, une dépense, un consentement, une donnée personnelle, un effet irréversible, un comportement produit | exige exactement une option `recommande: true` avec sa `raison`, sinon refus | « Ce qui t'attend », Quand tu veux |

Une proposition sans champs (créée avant la porte) n'est jamais réécrite :
le Cockpit la signale en zone santé « à reformuler par la porte ou à
fermer ». Un bead `maintenance` qui, en cours de travail, touche un
comportement visible de l'opérateur est **arrêté, jamais poursuivi** :
`reconvertir` ferme le bead bug et refait de la proposition une `decision`
(ADR-0029 point 6). ADR-0017 reste vrai : la porte n'autorise que la
correction du défaut constaté, jamais un refactor ou un audit.

Pourquoi : le 2026-10-07, sur 8 propositions ouvertes dans le Cockpit, 5
étaient des filtres d'ordres ou de gardes que l'autorisation de maintenance
du 2026-09-16 couvrait déjà, et 4 étaient périmées. Benjamin arbitrait des
décisions qui n'étaient pas de son niveau.

Tests : `tests/proposal-door-test.py` (la porte sur un faux `gc`),
`tests/proposal-classes-contract-test.py` (la vraie porte puis le vrai
Cockpit sur les mêmes beads).

---
