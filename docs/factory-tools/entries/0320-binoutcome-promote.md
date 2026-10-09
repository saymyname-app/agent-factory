## `./bin/outcome-promote` — ce que le code fait une fois que tu as répondu « accepté » ou « abandonné »

**La fusion unique et la fermeture du convoi** (Spec af-wf4w5r §9 et §11,
T30). Tu n'as **rien à lancer** : dès que ta réponse est enregistrée par
`./bin/owner-answer`, la passe suivante de `./bin/convoy-advance` lance
cette commande. Aucun agent ne peut la lancer : `run` est refusé à toute
session d'agent.

```bash
./bin/outcome-promote check <convoi>   # ce que run ferait : merge, close ou nothing ; n'écrit rien
./bin/outcome-promote run   <convoi>   # ce que l'ordre de l'usine lance ; refusé à une session d'agent
```

- **Avant « accepté »**, rien du convoi n'est dans la branche protégée :
  tout est sur la branche d'intégration.
- **« accepté »** : la branche d'intégration est fusionnée dans la branche
  protégée par **un seul commit de fusion**. Le relevé garde les deux
  commits — celui que tu as jugé et celui de la fusion
  (`./bin/convoy-state show`, `promotion`) — et une page `fusion.html` les
  note à côté du dossier que tu as jugé, qui ne change pas d'un octet. Les
  preuves de la Spec sont purgées, le convoi est fermé sur tes mots, sa
  Spec et son brouillon de graphe sont fermés.
- **Si la branche protégée a bougé depuis ton jugement**, le code la
  reprend d'abord dans la branche d'intégration et rejoue **seulement les
  contrôles mécaniques** : commande de régression, fidélité au Validated
  Prototype, démarrage du produit. Verts : la fusion se fait, et le relevé
  dit que la pointe fusionnée est ton commit plus cette reprise.
- **Rouges, ou les deux branches sont en conflit** : **rien n'est
  fusionné** et **ton acceptation est annulée** (elle reste au relevé, avec
  la cause). Un `repair` est publié, puis toute la porte de fin de Spec
  repasse et tu reçois une **nouvelle Acceptance Request** : tu juges de
  nouveau.
- **« abandonné »** : rien n'est fusionné ; le convoi est fermé avec ta
  raison ; la branche d'intégration reste où elle est, comme source.
- **Rien ne rouvre** un convoi fermé ainsi, ni lui ni ses tickets : toute
  écriture y est refusée. Un défaut ou un souhait trouvé après entre comme
  travail nouveau, par un Planning Run.
- **Un convoi fermé autrement** (à la main), même avec ta réponse, reste un
  « état sans règle » signalé sur ta liste.
- **Sorties** : 0 fait, ou rien à faire ; 1 refus, ou rouge (`error`
  commence par « refus : », `red` nomme le contrôle) ; 3 état sans règle ;
  4 convoi sans marque.
- **Limites** : sur un dépôt avec remote, la fusion est une **poussée
  directe** vers la branche protégée (gardée par un bail sur sa pointe),
  pas une pull request — si une protection de branche la refuse, l'Outcome
  reste accepté et non fusionné, chaque passe réessaie et le dit, rien
  d'autre ne te prévient ; sans remote, un répertoire de travail qui a la
  branche protégée extraite n'est pas rafraîchi ; **rien ne te prévient
  qu'une acceptation est annulée**, tu reçois seulement la nouvelle demande
  après le `repair` ; un rejeu coupé par le délai de l'ordre après la
  reprise fusionne à la passe suivante sans rejouer la fidélité ni le
  démarrage ; les dossiers ne sont jamais purgés ; aucun vrai convoi n'a
  encore été fusionné ainsi.

Détail : `docs/OUTCOME_PROMOTE.md`.

---
