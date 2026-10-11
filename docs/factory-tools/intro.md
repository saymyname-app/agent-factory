# Outils d'usine — ce qu'ils font, quand les lancer

> Systèmes retirés (Cockpit V1, ntfy, campagne, file/statut/preview produit,
> contrat de release, axes d'amélioration) : code et documents retirés, gardés par l'historique
> Git (non fiable, voir `decisions/PRE_REFACTOR.md`).

Trois scripts `bin/` protègent et décrivent l'usine elle-même. Ils sont **L0,
déterministes, zéro token** : aucun appel de modèle. Vous pouvez les lancer
librement.

Pour la procédure d'arrêt/redémarrage complète, voir
`RUNBOOK_STOP_AND_RESTART.md`.

---

