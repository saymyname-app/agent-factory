## `./bin/acceptance-session` — lancer le produit que tu juges, puis l'arrêter

**L'Acceptance Request et l'Acceptance Session** (Spec af-wf4w5r §11, T28).
Quand un convoi qui porte la **marque du nouveau flux** est Delivered,
`./bin/convoy-advance` t'envoie **une** demande : dans
`./bin/escalation-door list`, la ligne
`<convoi> — Acceptance Request — convoi <convoi> : un Delivered Outcome attend votre jugement — dossier : <chemin de la page>`.
Elle porte le lien du dossier, une seule option (« Ouvrir l'Acceptance
Session ») et **aucune recommandation**. Du code, et aucun agent, lance
ensuite le produit que tu juges et l'arrête.

```bash
./bin/acceptance-session open   <convoi> [--repo <dépôt du projet>] [--profile <profil>]   # lance le produit au commit du dossier
./bin/acceptance-session close  <convoi>                                                   # l'arrête, répond une fois chaque port libéré
./bin/acceptance-session record <convoi> --response relancer|planification|abandon         # issue d'une demande « non conforme »
```

- **Comment t'en servir** : ouvre la page du dossier dans un navigateur,
  demande à ta session opérateur d'exécuter `open`, ouvre l'adresse rendue
  (`address`, et `products` : une adresse par jeu de données synthétiques du
  profil), juge, puis `close`.
- **Ce que `open` lance** : le produit depuis une copie propre du commit du
  dossier, par la recette du profil du projet (`./bin/project-launch`), une
  fois par jeu de données déclaré, chacun sur son port — tous, ou aucun.
  Même commande pour le dossier d'un Delivered Outcome et pour celui d'une
  demande « non conforme » (T26) ; dans ce second cas la réponse porte les
  trois `issues`.
- **Refus de `open`** : rien à juger (convoi ni Delivered ni porteur d'une
  demande « non conforme ») ; session déjà ouverte sur ce convoi ; dossier
  qui n'est pas « à jour » selon `./bin/evidence-pack check`, ou qui n'est
  plus celui de la demande (la prochaine passe en génère un nouveau) ;
  aucun profil ou aucune recette de lancement ; état sans règle.
- **Une panne n'est pas un jugement** : si le produit ne démarre pas, `open`
  le dit (`outage: true`), n'ouvre aucune session et note la panne sur le
  convoi ; la **passe suivante** de `./bin/convoy-advance` publie un
  `repair` qui rétablit le démarrage. Tant que le produit réparé n'a pas son
  propre dossier, `open` à ce commit est refusé et nomme ce `repair`.
- **Ce que l'agent de la session fait et ne fait pas** : `open` lui rend
  ses `rules` avec l'adresse — ouvrir le produit et y naviguer à ta demande,
  rédiger tes constats **avec tes mots**, donner le lien du dossier **sans
  le résumer**, **ne jamais recommander** une réponse ni dire si le produit
  mérite d'être accepté, fermer par `close`.
- **Aucun délai ne répond à ta place** : rien n'accepte, ne fusionne ni ne
  ferme sur une horloge ; un Delivered Outcome le reste jusqu'à ta réponse.
- **`record`** ne vaut que pour une demande « non conforme » : il remet à
  `./bin/escalation-door repondre` l'issue que tu as choisie (relancer un
  tour, retourner à la planification, abandonner). « accepté » y est
  refusé, et rien n'est enregistré.
- **Sorties** : 0 fait ; 1 refus ou panne (`error` commence par
  « refus : ») ; 3 état sans règle ; 4 convoi sans marque.
- **Limites** : tes trois réponses à un Delivered Outcome (accepté,
  constats rendus, abandonné) s'enregistreront par une autre commande
  (T29), et répondre à l'option de l'Acceptance Request sur la porte ne
  déclenche rien ; l'issue d'une demande « non conforme » est enregistrée
  mais rien ne la lit encore (T29) ; le `repair` d'une panne est publié par
  la passe suivante, pas par `open`, et **aucun** n'est publié tant que les
  tours de fin sont arrêtés ; le journal de lancement d'un produit qui ne
  démarre pas n'est pas conservé (une ligne de précision sur la panne) ; le
  relevé de la session est un état local de l'hôte
  (`~/.local/state/agent-factory-acceptance-session`,
  `ACCEPTANCE_SESSION_STATE_DIR`), pas un champ du tracker ; les règles
  sont remises à l'agent, aucun code ne l'empêche de les enfreindre ; aucun
  vrai convoi n'a encore atteint l'acceptation.

Détail : `docs/ACCEPTANCE_SESSION.md`.

---
