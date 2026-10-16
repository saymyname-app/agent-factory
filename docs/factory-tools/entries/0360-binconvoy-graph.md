## `./bin/convoy-graph` — où en est le convoi d'une Spec ?

**La forme vivante du convoi d'une Spec, en lecture seule.** Il répond à ce
qu'un opérateur demande d'un convoi qui tourne, d'une lecture du tracker et
d'une des sessions : les sessions réellement actives, les tickets prêts à
démarrer, le chemin critique du travail restant et la largeur par niveau.

```bash
./bin/convoy-graph af-2zseit          # texte
./bin/convoy-graph af-2zseit --json   # un objet JSON
```

- **Sessions** : `gc session list`, pas `gc status`. `gc status` affiche
  « stopped » pour un emplacement de pool alors que des sessions de son
  modèle tournent ; un agent en a conclu à tort « agents arrêtés »
  (2026-10-15). Chaque session active nomme le ticket qu'elle porte.
- **Dépendances** : `gc.blocked_by` de chaque ticket (clés de ticket). Un
  bloqueur livré ou retiré ne retient plus ; une clé qu'aucun ticket de la
  Spec ne porte retient, et elle est nommée.
- **Prêt** : ouvert, non retiré, jamais démarré (ni porte `dispatch` ni
  sortie), plus rien à attendre — la frontière d'où part
  `bin/convoy-advance`, avant son plafond de sessions.
- **Chemin critique et niveaux** : ceux du travail restant (ni fermé ni
  retiré), calculés par `lib/ticket_graph.py`, le code de la borne de chemin
  critique de la relecture de graphe (ADR-0031). Niveau 1 : n'attend rien ;
  la largeur d'un niveau dit combien d'auteurs il peut occuper à la fois.
- **Sorties** : 0 ; 1 si le tracker ou les sessions ne se lisent pas, ou si
  aucun ticket ne porte la Spec ; 2, usage. N'écrit rien.
- **Limites** : un instantané, pas une surveillance ; le plafond N de
  `bin/convoy-advance` et ses arrêts (rouge d'intégration, Planning
  Exceptions) ne sont pas appliqués ici : `docs/CONVOY_ADVANCE.md`.

Preuve : `tests/convoy-graph-test.py`.
