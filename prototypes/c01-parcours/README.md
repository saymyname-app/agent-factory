# Parcours de jugement dans le cockpit actuel

Intent (Benjamin, ses mots, 2026-10-11) : « Ok, fais les prototypes des parcours manquants dans le cockpit actuel : résultat à juger, dossier et essai, constats rendus et suivi de la fusion. » Décision précédente : « On garde Comme on a […] c'est une boite de reception ».
Mechanism (agent interpretation) : conserver les rendus actuels de l’accueil, de la boîte de réception et des projets ; varier seulement le détail du résultat, sur des données synthétiques et un serveur isolé. Aucune validation de Spec ni implémentation du flux d’écriture.

## Question

Quelle présentation du détail permet de passer du résultat au dossier et à l’essai, de préparer ses constats puis de comprendre leur suite et la fusion, sans changer la boîte de réception ?

- A : onglets Résultat / Dossier / Essai / Mes constats / Suivi ; recommandation de départ pour limiter le changement.
- B : rail d’étapes, une étape visible à la fois ; guide davantage l’usage.
- C : sections dépliables, dossier et journal dans un seul détail ; permet de garder plusieurs passages ouverts.

L’accueil lui-même ne change pas de variante. Les couleurs, le header, les positions et les composants de base viennent du vrai cockpit. Les données et l’intérieur du détail sont des propositions de parcours, pas du produit accepté.

## Ouvrir

Depuis la racine du worktree : `python3 prototypes/c01-parcours/serve.py`.

URL : `http://127.0.0.1:8185/?variant=A&scene=ready&view=result`.
Flèches de la barre flottante ou clavier pour A/B/C. Le clavier laisse les champs de texte tranquilles.
Le sélecteur du bandeau PROTOTYPE permet de rejoindre directement chaque état. Cliquer une demande ouvre son détail ; sur téléphone, Retour à la liste rétablit la liste.

Pour explorer normalement : résultat → dossier → ouvrir l’essai → changer le jeu de données → fermer l’essai → écrire ses mots → donner un verdict sur la proposition du dossier → préparer le prompt. L’outil « Simuler l’enregistrement » du bandeau du prototype joue ensuite l’enregistrement de la réponse. Depuis Projets, « Suivre le résultat » permet de retrouver la suite après disparition de la demande.

## Contrats respectés et choix proposés

- `docs/ACCEPTANCE_SESSION.md` : le produit est celui du dossier courant ; tous les jeux de données sont synthétiques. Une panne de lancement n’est pas un jugement. Un dossier périmé ne permet pas d’essai.
- `docs/OWNER_ANSWER.md` : mots exacts, commit et empreinte du dossier ; trois réponses, aucune acceptation partielle. Chaque proposition demande un verdict. « À faire avant d’accepter » empêche de préparer une acceptation.
- Le cockpit ne reçoit aucun nouveau bouton d’acceptation directe. Le brouillon et le prompt proposent le passage vers la session d’agent ; seul le bandeau du prototype simule l’enregistrement. Cette proposition d’interface reste à juger. Le prompt est marqué synthétique, ne doit pas être exécuté et ne lance aucune session.
- Les constats restent en brouillon et en mémoire jusqu’à la simulation. Leur association à un parcours, un nouveau besoin ou une idée plus tard aide à préparer le contexte ; elle ne remplace pas le classement du code ni la préparation des références et réparations par l’agent.
- `docs/OUTCOME_PROMOTE.md` : acceptation ≠ fusion. Fusion confirmée seulement avec une preuve séparée. Conflit/rejeu rouge → acceptation annulée, aucune fusion, nouveau dossier et jugement ultérieur. Un abandon ne fusionne rien.
- La demande disparaît de la boîte de réception dès que rien ne demande une action à Benjamin ; le suivi demeure dans Projets. C’est une proposition de projection du flux dans l’interface, pas une modification déjà approuvée de la Spec.

## Inventaire des états

Chaque URL peut porter `?variant=A|B|C&scene=<état>` ; `view` choisit un passage dans le détail.

| État | Ce qu’il permet de juger |
|---|---|
| ready | Attente lisible et accès au résultat |
| dossier | Dossier consultable, limites, proposition et preuves exemples |
| trial | Version du dossier, choix entre deux jeux synthétiques, fermeture de l’essai |
| findings | Mots exacts en brouillon, jugement préparé et prompt neutre |
| returned | Réponse enregistrée dans la simulation ; aucune fusion |
| repairing | Texte du constat conservé, correction et nouveau dossier attendus |
| new-result | Dossier 2 avec « Depuis ton dernier jugement » et preuve exemple de correction |
| accepted | Acceptation enregistrée, fusion encore absente |
| merging | Fusion en préparation, pas encore confirmée |
| merged | Preuve séparée de fusion et historique |
| outdated | Dossier ancien, essai/jugement indisponibles |
| outage | Panne de lancement, réparation attendue, pas de jugement inventé |
| conflict | Acceptation annulée, aucune fusion, correction et nouveau jugement attendus |
| abandoned | Raison et historique ; rien fusionné |

Le dossier affiché est un extrait synthétique. Il ne remplace pas les neuf rubriques du vrai Evidence Pack. Les pièces consultables sont des exemples, pas des preuves d’une livraison réelle. Les traces d’heure et de commit sont également synthétiques.

## Sources de l’interface

Base vérifiée : `f65d23e2929cb7abf8de911f0b6ba85478da1290` (main et racine live concordaient au début de ce passage).
`generate.py` appelle les vrais `render_home`, `render_requests_section` et `render_projects_section` avec les vrais types `OperatorRequest`, `Project` et `Chantier`, puis retire tous les scripts de production et les liens externes. Seuls le détail du résultat et son état de chantier sont remplacés par le prototype.

La route isolée est `/`, comme le cockpit actuel ; elle accepte les paramètres de variante et d’état. Aucun fichier de `lib/cockpit/` n’a été modifié. Le serveur n’a aucune commande POST, et sa politique navigateur interdit les connexions sortantes et l’envoi de formulaire. Aucun Beads, gc, GitHub, secret, notification, vrai lancement ou modèle n’est appelé.

Les sources CSS/JS restent séparées pour pouvoir régénérer : `python3 prototypes/c01-parcours/generate.py`. `index.html` est également autonome et peut être ouvert localement. Le prototype n’est pas branché au démarrage de l’usine et ne peut afficher sa barre dans le processus cockpit de production.

## Vérification du prototype

Edge sans fenêtre : trois variantes × quatorze états × deux largeurs (1440/390), soit 84 combinaisons. 48 captures conservées, dont accueil clair/sombre des trois variantes aux deux largeurs. Aucun débordement horizontal ni erreur JavaScript. Mots conservés lors d’un changement de variante, clavier dans les champs, choix de jeu de données, fermeture d’essai, verdict bloquant, constats → suivi, accepté sans fusion, acceptation annulée sans fusion et accès depuis Projets vérifiés. Aucun appel autre que GET vers le serveur du prototype. Résultat : `qa.json`.

Ce n’est ni un essai iPhone réel ni une preuve du flux D01. La validation du choix et la conformité du prototype figé restent à faire après le retour de Benjamin.

## Capture et reprise

Branche privée jamais fusionnée : `prototype/c01-parcours-20261011`.
Suivi : `af-9mq6x2`, lié à l’assemblage `af-mjfvwx`.
Verdict actuel : trois variantes consultables, aucune retenue pour les nouveaux parcours. La boîte de réception actuelle, elle, reste la structure choisie.

Après choix : enregistrer les mots de Benjamin, figer uniquement les parcours retenus avec leurs états et ancres, contrôler la conformité du prototype avant confirmation, puis référencer ce prototype dans la Spec de reprise. Ne pas transformer ce code jetable en implémentation de production.
Pour quitter l’essai : arrêter uniquement le serveur 8185. Le cockpit 8173 et l’usine n’ont pas été modifiés.

## Révision : alléger l’interface

Intent (Benjamin, ses mots, 2026-10-11) : « dans toutes les propositions il y a trop de texte, trop de detail trop de contenu. Il faut me simplifier la vie surtout, l’interface doit etre simple. »
Mechanism (agent interpretation) : réduire le détail visible à une phrase et aux actions utiles ; dossier, preuves et historique sur demande ; retirer le classement manuel des constats. Cette demande ne valide aucune variante ni ne supprime les garde-fous du jugement.

A : trois onglets. B : une action à la fois sans rail ni étapes administratives. C : accès directs et avis dépliable. Le texte du prompt est masqué jusqu’à une consultation explicite. Les mots exacts, le verdict sur chaque proposition, l’abandon motivé et l’acceptation distincte de la fusion restent requis. Le verdict manquant est demandé au moment de continuer ; les constats ne sont plus à classer par Benjamin. Aucune écriture réelle.

Les captures et QA de la première révision sont historiques ; la vérification de cette simplification est dans qa-simple.json et screenshots-simple/.
