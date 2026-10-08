## `./bin/outcome-evaluation` — le produit assemblé fait-il ce que la Spec demande, story par story ?

**L'Outcome Evaluation et le classement des constats hors ticket** (Spec
af-wf4w5r §7 et §9 points 4 et 5, T24). Dans un convoi qui porte la **marque
du nouveau flux**, une fois les trois verdicts mécaniques de `./bin/spec-end`
verts sur un commit, un Evaluator de fin — contexte neuf, boîte noire, rôle en
lecture seule — utilise le produit assemblé lancé par du code à ce commit. Il
rend **un état et une preuve par user story numérotée** ; **le verdict est
calculé par du code**.

```bash
./bin/outcome-evaluation show    <convoi>   # états, preuves, repairs rédigés, contradictions ; n'écrit rien
./bin/outcome-evaluation verdict <convoi>   # le verdict calculé et ses raisons ; n'écrit rien
```

- **Verdict** : favorable seulement si chaque story est « observée avec
  preuve » au commit de la porte. Une story manquante ou sans preuve valide
  fait refuser l'enregistrement.
- **Story « non observée »** : l'Evaluator rédige un `repair` qui cite la
  story et ne le publie pas ; `./bin/convoy-advance` le publie par la porte
  de patch. **Story inobservable** : l'évaluation s'arrête et une question
  t'est posée (`./bin/escalation-door list`).
- **Constats hors ticket** : chacun est classé « réparé » (citation de ce
  qu'il rétablit et repair rédigé obligatoires), « proposition pour
  Benjamin » (gardé pour le dossier) ou « écarté » (raison obligatoire). Un
  constat non classé fait refuser la porte de fin de Spec, qui le nomme.
- **Contradiction** : une story « non observée » dont tous les tickets
  couvrants étaient « observés » est inscrite par du code (`show`,
  `contradictions`).
- **Exploration libre et écarts de fidélité** : enregistrés, sans effet sur
  le verdict.
- **Arrêts** : aucun résultat après une relance, environnement en panne,
  story inobservable — une demande t'est adressée, une fois.
- **Sorties** : 0 fait ; 1 refus ; 3 état sans règle ; 4 convoi sans marque.
- **Tours de fin bornés** (T26) : une évaluation qui laisse une user story
  non observée, ou un constat hors ticket à réparer, compte un tour de fin
  (`counters.end_rounds`, borne 2, compteur commun aux rouges mécaniques et
  à la revue de fin). Les tours s'arrêtent **avant le deuxième** si le tour
  précédent n'a pas réduit le nombre de user stories non observées, ou si
  une user story déjà refusée l'est de nouveau ; sinon à la borne. Arrêtés,
  les `repair` rédigés ne sont plus publiés et tu reçois une demande « non
  conforme » avec le lien du dossier (`./bin/convoy-advance`).
- **Limites** : l'arrêt anticipé ne lit que les user stories non observées,
  pas les constats hors ticket ; aucun essai avec
  une vraie session d'Evaluator ; le dossier n'est pas généré ici.

Détail : `docs/OUTCOME_EVALUATION.md`.

---

