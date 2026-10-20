## `./bin/prototype-fidelity` — l'écran livré est-il fidèle au prototype que Benjamin a validé ?

Du code compare, état par état, la page livrée **servie à sa vraie adresse**
à la version figée du prototype (Validated Prototype), sans humain (Spec
af-wf4w5r §3, §7, §9, T16). Un écart mesurable est rouge et nommé ; il
n'arrive jamais jusqu'à Benjamin sans l'être.

```bash
./bin/prototype-fidelity check <descriptor.json> --prototype <dossier> --commit <sha> [--repo-root <dépôt du produit>]   # tous les écrans (fin de Spec)
./bin/prototype-fidelity check <descriptor.json> --prototype <dossier> --commit <sha> \
    --convoy <convoi> --ticket <ticket> [--screen <écran>]                                                              # un ticket : son écran seulement
./bin/prototype-fidelity calibrate --prototype <dossier> [--states <état,état>]                                        # le prototype comparé à lui-même
```

- **Étalonnage** (`calibrate`, af-u8cbl0) : le prototype est placé des deux côtés de la comparaison, et
  le résultat doit être 0 écart. Un thème que l'outil n'atteint pas (« non mesurable ») ou une mesure
  instable le rend rouge. `bin/spec-approve` le lance avant d'approuver la Spec, et refuse tant qu'il
  reste un écart : c'est un défaut de l'outil, à corriger par la maintenance de l'usine.

- **Ce qui bloque** : un token du prototype absent ou changé (lu sur les
  sources), une ancre du prototype absente du livré, un autre élément, un
  autre emboîtement, un autre nombre d'occurrences, ou une autre valeur de
  style calculé sur une ancre (police, taille, graisse, interligne,
  couleurs, rayon, marges intérieures, affichage, ombre), à chaque taille
  d'écran et chaque thème de référence du prototype.
- **Sortie** : 0 vert (ou tout écart « accepté par Benjamin »), 1 rouge
  avec l'état, la taille d'écran, l'ancre et la propriété de chaque écart,
  2 refus, 4 convoi sans la marque du nouveau flux.
- **Jamais vert sur ce qui n'a pas été comparé** : un état prototypé que le
  profil ne sert sur aucun écran, un produit qui ne démarre pas, un
  navigateur sans mesure : refus, pas un vert.
- **Avec un ticket** : le relevé complet est une pièce scellée du magasin
  de preuves ; les captures côte à côte et l'image de différence de chaque
  état sont enregistrées par `./bin/evidence-capture comparison`, les deux
  côtés rendus à ce moment-là ; le résultat est écrit sur le ticket par
  `./bin/convoy-state set-fidelity`, lié au commit.
- **Les captures ne bloquent jamais** : le nombre de pixels différents est
  noté, aucun seuil n'existe. Elles servent aux yeux de Benjamin.
- **Un écart voulu** ne se lève pas ici, et pas par l'auteur : l'auteur
  sort par `./bin/ticket-exit exit … --exit planning_exception --anchor
  <ancre>`, après avoir écrit l'écart et son ancre sous « Écarts » dans son
  compte rendu (sinon refus) ; la demande propose à Benjamin « Accepter l'écart sur l'ancre
  … » ; sa réponse par `./bin/escalation-door repondre` fait lire l'écart
  « accepté par Benjamin ». Toute autre réponse le laisse rouge. Un écart
  de token se répare.
- **Écrans** : déclarés dans le profil du projet (`launch.screens` : nom,
  chemin servi, états prototypés).
- **Limites** : le lien ticket → écran n'est pas enregistré à la
  publication (l'appelant nomme l'écran) ; l'appel avant la fusion d'un
  ticket est fait par `./bin/ticket-end`, celui de fin de Spec par
  `./bin/spec-end` ; le texte affiché n'est pas
  comparé ; un produit qui interdit d'être encadré ne se mesure pas.

Détail : `docs/PROTOTYPE_FIDELITY.md`.
