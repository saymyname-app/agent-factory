## `./bin/evidence-pack` — où est le dossier que tu juges, et tient-il encore ?

**L'Evidence Pack généré par du code** (Spec af-wf4w5r §10, §9 point 6, T27).
En fin de Spec, tu juges le produit lancé avec une seule page à côté : le
dossier. Du code l'assemble **à partir des pièces enregistrées et de rien
d'autre** ; aucun agent n'en écrit un mot, et la commande ne prend aucun
texte de qui l'appelle. Ne concerne qu'un convoi qui porte la **marque du
nouveau flux**.

```bash
./bin/evidence-pack generate <convoi> --repo <dépôt du projet>   # écrit la page et l'enregistre sur le convoi
./bin/evidence-pack check    <convoi> --repo <dépôt du projet>   # le dossier enregistré tient-il encore ? n'écrit rien
```

- **Où est la page** : `generate` répond `page`, le chemin d'un
  `index.html` sous `~/.local/state/agent-factory-evidence-packs/<spec>/<convoi>/<commit>/`
  (`EVIDENCE_PACK_DIR`). Page statique : elle s'ouvre dans un navigateur,
  sans script, avec ses pièces à côté d'elle.
- **Ce qu'elle porte**, dans l'ordre de la Spec : 1 en-tête (Spec et
  digest, branche, commit, verdict de chaque condition de fin de Spec) ;
  2 **ce qui demande tes yeux** (propositions, écarts de fidélité, captures
  côte à côte et image de différence, remarques d'exploration, mentions
  « même fournisseur ou même modèle que l'auteur ») ; 3 **ce qui n'a PAS été
  vérifié** ; 4 par user story ; 5 par ticket ; 6 éléments suivis ; 7 hors
  graphe initial (repairs, Planning Exceptions, dérogations, tes réponses) ;
  8 relevés (fichiers hors Declared Scope, modèles, durée, tours de fin,
  contradictions) ; 9 preuves TDD et constats de revue.
- **« Ce qui n'a PAS été vérifié » est obligatoire** : états d'écran non
  prototypés lus dans la Spec, critères du socle sans mécanisme et limites
  connues des contrôles lus dans `config/evidence-pack.json`. Si la rubrique
  ne peut pas être remplie, **la génération est refusée** et rien n'est
  écrit.
- **Une condition rouge ne refuse pas la page** : elle est produite avec
  « Dossier non conforme » en en-tête et le verdict de chaque condition.
- **Un commit de plus le périme** : `check` répond `à jour`, `absent`,
  `périmé` (un commit de plus, ou un relevé qui a changé depuis), `altéré`
  (page ou pièce réécrite à la main) ou `incomplet` (pièce refusée par le
  magasin de preuves). La porte de fin de Spec lit cette réponse comme sa
  dernière condition et refuse sans dossier complet à jour.
- **Deux générations sur le même état** donnent la même page, octet pour
  octet : elle ne porte aucune heure de génération.
- **Sorties** : 0 fait, ou dossier à jour ; 1 refus, ou dossier qui ne tient
  pas ; 3 état sans règle ; 4 convoi sans marque.
- **Limites** : les captures côte à côte sont celles du dernier contrôle de
  fidélité de chaque ticket d'écran, à son commit — aucune n'est refaite au
  commit du dossier, et la page le dit ; l'en-tête ne porte pas l'adresse
  d'un produit lancé (rien ne le lance à la génération) ; la rubrique
  « Depuis ton dernier jugement » viendra avec l'enregistrement de
  l'acceptation ; aucun vrai convoi n'a encore de dossier.

Détail : `docs/EVIDENCE_PACK.md`.

---
