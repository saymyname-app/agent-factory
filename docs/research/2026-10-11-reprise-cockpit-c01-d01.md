# Reprendre le cockpit après C01 et D01

Intent (Benjamin, ses mots, 2026-10-11) : « revoir si on a dévié de la spec, ce que faire implementer la spec telle quelle va faire, et comment reprendre le travail de là » ; « faire des prototypes avec la skill pour les interfaces ».
Mechanism (agent interpretation) : comparer les engagements C01, leurs amendements enregistrés et le code actuel ; proposer une reprise incrémentale et trois variantes jetables. Ce document ne modifie ni une Spec approuvée, ni un graphe exécutable, ni le cockpit en service.

## Conclusion

Conserver le cockpit assemblé. Ne pas republier les 25 tickets C01. L’intention — comprendre et agir sans agent, suivre les projets, être prévenu — reste valable. Le contrat d’étapes et d’acceptation C01 est dépassé par D01 ; plusieurs décisions ultérieures ont aussi remplacé des exigences. La reprise doit traiter les écarts actuels et les parcours qui manquent, avec une nouvelle Spec approuvée si le comportement change.

## Sources et limites

Observation du 11 octobre 2026, vers 15:10–15:20 (Paris). Racine exécutée, origin/main et GitHub main concordaient sur `7da4dfa2d5cfeb359445f84cf0d5af2568bf6106`.

- Spec C01 : `gc bd show af-oohx2x`, approuvée le 30 septembre ; carte `af-arlph5` ; brouillon `af-i67vl0` ; convoi `af-f71cgu` fermé automatiquement parce que tous ses enfants étaient fermés.
- Assemblage manuel : `af-mjfvwx`, description et commentaires, passation du 8 octobre puis décisions du 10 octobre. La session précédente a laissé le travail ouvert, pas accepté.
- Contrats et code : `docs/COCKPIT.md`, `docs/OWNER_ANSWER.md`, `docs/OUTCOME_PROMOTE.md`, `docs/PLANNING_RUN.md`, `docs/agents/issue-tracker.md`, `lib/cockpit/**` et profil `config/project-descriptors/agent-factory.json`.
- D01 : Spec `af-wf4w5r`, vérification finale `docs/verification/D01-verification-finale.md`, notamment D2.10 et US80.
- Production locale, lectures HTTP sans mutation : accueil 8173, `/api/status`, `/api/projects`, `/api/requests`, `/api/health`.
- Prototypes antérieurs : `origin/prototype/c01-home-screen` (accueil D retenu), `origin/prototype/c01-project-page` (Tableau/Bande conservés par l’assemblage).

L’audit est une comparaison de contrats et une inspection du code, avec observations locales ciblées. Ce n’est pas une nouvelle recette exhaustive des 107 stories. Les notifications reçues et validations de fidélité sont attestées par les commentaires des sessions précédentes ; pas réessayées ici. Aucun arrêt réel ni changement de réglage tiers effectué.

## Pourquoi la première livraison a déçu

`docs/COCKPIT.md` et la passation d’assemblage documentent quatre ruptures :

1. T11 interrogeait `/events`, une page HTML sur le vrai superviseur, tandis que le faux outil répondait comme une API. Tests verts, source jamais lue en service.
2. L’accueil n’avait repris que les douze couleurs du prototype, avec une liste non structurée. Le code fusionné ne prouvait pas la fidélité à l’interface validée.
3. Projets, page projet, journal, notifications et heartbeat existaient comme modules testés, sans appel dans le processus. Le raccordement a été fait ensuite.
4. L’adaptateur Pushover ne suivait pas le format du vrai service ; son faux adaptateur ne pouvait pas le détecter.

Verdict : bugs d’intégration et preuves trop éloignées du produit. La classe à corriger est le passage module → processus → outil réel → parcours utilisateur. D01 ajoute des preuves et évaluations sur le produit assemblé ; son efficacité sur un premier vrai chantier reste à montrer. Ces nouvelles portes ne réparent pas rétroactivement une Spec ancienne.

## Écarts et conséquences d’une reprise littérale

| Surface | C01 d’origine | État après décisions et D01 | Conséquence et verdict |
|---|---|---|---|
| Acceptation | Story 30, clic « Accepter » ; Livré = convoi fermé | D01 : dossier lié au commit, session d’essai, mots de Benjamin ; le convoi reste ouvert avant acceptation et fusion | Refaire l’ancien clic contournerait le contrat de jugement. Évolution décidée, à reprendre dans la future Spec. |
| Étapes | Convoi ouvert = Livraison ; fermé = Livré | `projects/stage.py` garde cette règle. Il lit le jugement D01 uniquement dans la branche « fermé » | Bug d’adaptation : un résultat D01 prêt à juger peut rester « Livraison / bloqué ». Lire les états du flux, pas la fermeture seule. |
| Progression | « tickets mergés » et PR pour chaque enfant | D01 intègre les tickets sur une branche de résultat puis fusionne une fois après jugement | Compteurs et libellés anciens deviennent ambigus ; lire intégration, évaluation et résultat du flux. |
| Fusion/promotion | Commits `gc.merge_commit` des tickets atteignables depuis la branche de promotion | D01 conserve sa fusion finale dans le record de promotion du chantier | `projects/promu.py` lit encore les commits par ticket. Risque d’inconnu ou de preuve inadaptée ; inspection, pas reproduction de ce cas. Utiliser la preuve finale pour les chantiers D01, préserver le cas ancien. |
| Anomalies | Convoi fermé avec enfant « non mergé » | `projects/anomalies.py` assimile « enfant non fermé » et « non mergé » | Fermeture n’est pas preuve Git ; les abandons D01 ne fusionnent rien légitimement. Revoir la règle selon l’issue du chantier avant de la réutiliser. |
| Anciens résultats | Tous les Livrés non Acceptés demandent un clic | Décision du 7 octobre : pas de demande sans objet à juger ; historique « livré avant le flux d’acceptation » | Régression si rétabli. Ne pas inventer leur acceptation. |
| Rituels | Demandes « Quand tu veux » et roadmaps avec lecteur de rituels | « pas de rituels finalement », 6 octobre ; PR 414 fermée | Écart décidé. Ne pas rebrancher cette tranche. |
| Propositions | Toutes les propositions ouvertes attendent Benjamin | ADR-0029 : maintenance traitée par l’usine ; décision seule dans l’attente | Écart décidé. Revenir au texte C01 ferait revenir les tâches de maintenance dans la boîte de réception. |
| Texte des escalades | Story 78 : producteur et lecteur refusent le même texte incompréhensible | Porte de proposition partage le contrôle du cockpit ; `escalation-door benjamin` ne le partage pas encore, écart documenté | Bug de contrat : un texte accepté peut tomber sur le repli dans l’écran. Réparer la classe producteur/lecteur, sans réécrire les textes avec une IA. |
| Arrêt/reprise | Stories 80–92, bouton après preuve réelle | Processus raccordé en lecture seule ; aucune action d’arrêt enregistrée ; essai réel 7b reporté après D01 | Non réalisé, pas un bouton à réactiver. Les corrections T08–T10 précèdent la refonte : revalider leur pertinence avec les nouveaux rôles. Observer une suspension nécessite une fenêtre explicite. |
| Roadmap | Étape courante structurée et correcte | Le cockpit lit fraîchement A5 « en cours » ; D01 y reste aussi « en cours ». SayMyName n’a pas de roadmap lisible | Donnée obsolète, pas panne de lecture. Actualiser au dépôt propriétaire ; garder « inconnue » pour SayMyName. L’API projets brute n’inclut pas les compléments dépôts, mais l’accueil les affiche. |
| Healthchecks | DOWN prioritaire et UP désactivé | Passation : DOWN/UP reçus ; derniers réglages connus Normal + UP actif | Écart de réglage à revérifier avec Benjamin, pas déclaration de panne actuelle. |
| Qualité des actions | Retour tracé et erreurs visibles | Retour immédiat raccordé ; ticket `af-fksj2c` ouvert : timeout d’un sous-processus pouvant traverser le gestionnaire HTTP | Bug produit probable déjà suivi ; reproduction et correction à reprendre dans la tranche actions, sans doublon. |
| Recette de lancement | Non exigée par C01 | D01 exige le bloc `launch` ; le profil réel agent-factory n’en possède toujours pas | Préalable bloquant du nouveau flux. Recette isolée, commit précis, données synthétiques ; pas le processus 8173 ni les secrets de service. |
| Validation finale | 7 jours consécutifs, aucun faux affichage frais, notifications sans doublon, arrêt/reprise réel, alerte silence | C01 et son graphe sont fermés, mais l’essai arrêt/reprise et le jugement d’usage ne sont pas établis | Clôture administrative ≠ acceptation. Conserver les critères encore pertinents, les rendre explicites dans la reprise. |

Preuve ciblée du défaut d’étape : `prototypes/c01-reprise/stage-observation.json`. Record `gc.flow.delivered` validé par le parseur officiel (commit, protected, pack, version, date), convoi ouvert. Résultat du calcul actuel : `Livraison`, `bloque`, aucun lien d’action. Cela prouve la règle de calcul ; pas un incident déjà observé sur un chantier réel D01.

## Sort des anciens tickets

Les 25 tickets sont fermés. T21 était un prototype ; les 24 autres portent une PR fusionnée. Ne pas les rouvrir comme une file de travail actuelle.

| Tickets | À conserver | À reprendre |
|---|---|---|
| T01–T05 | Langue, lexique, descripteurs, clé projet, gouvernance ajout/retrait projet | Actualité des roadmaps ; ne pas restaurer les rituels. |
| T06–T07 | Portes de décision/proposition, traces | Contrat de texte des escalades ; classes ADR-0029. |
| T08–T10 | Historique des préalables à l’arrêt | Preuve sous nouveaux auteurs/relecteurs/évaluateurs, sans supposer l’ancien worker encore autorité. |
| T11–T16 | Processus, cache de lecture, accueil D, actions, journal, santé raccordés | États D01, parcours depuis l’attente, erreurs HTTP ; contrôler le produit assemblé. |
| T17–T18 | Notifications/heartbeat raccordés, réception réelle attestée | Réglages Healthchecks et preuve de priorité ; garder zéro token. |
| T19–T20 | Projets/chantiers, historique, clones en lecture seule | Lire les records D01 pour livraison, jugement, fusion, abandon ; séparer lecture et vérité du contenu. |
| T21–T22 | Prototype de page projet et page Tableau/Bande | Nouveaux états et navigation vers le résultat à juger. |
| T23–T24 | Pilote et zone de lecture | Écriture/arrêt forcé/reprise encore non prouvés ; chantier à part. |
| T25 | Accès privé, contrôles d’identité, déconnexion | Régression ciblée quand les actions changent ; pas de nouvel accès public. |

Story 20 (« nouveautés de la Spec par rapport à la carte ») a été explicitement sortie de V1 dans le graphe approuvé. Ne pas la considérer comme oubli de livraison.

## Reprise proposée

Chaque tranche doit être utile seule et pouvoir tenir environ une journée. Ce sont des candidates à la future découpe, pas des tickets déjà approuvés.

1. **Préparer la preuve de livraison** : recette `launch` agent-factory, produit isolé au commit demandé, données synthétiques nommées ; prouver qu’aucun chemin n’appelle les vrais services. Préalable au flux D01, à livrer comme maintenance bornée si son bootstrap bloque.
2. **Rendre l’état du travail juste** : lecteur D01 commun aux écrans ; résultats prêts à juger, constats rendus, corrections, acceptation en attente de fusion, fusion effectuée, abandon. Ancien flux gardé comme historique. Preuve : parcours HTTP avec les records que les portes réelles produisent.
3. **Rendre la décision actionnable** : attente → dossier → session d’essai du commit → retour vers le suivi ; supprimer toute impasse de clic Accepter pour D01. Ajuster le contrat de texte des escalades et l’erreur timeout déjà suivie si cela tient dans la tranche, sinon séparément.
4. **Rendre le contexte projet utile** : page projet, roadmap actualisée, progression expliquée avec états D01, historique. La roadmap SayMyName est un travail du dépôt propriétaire, pas du code Factory inventant son avancement.
5. **Arrêt/reprise** : tranche indépendante après relevé du comportement réel dans une fenêtre autorisée. Ne pas l’utiliser comme dépendance de toute l’interface ; bouton reste indisponible avant preuve.
6. **Usage réel** : les sept jours décidés par C01 constituent la recette restante, avec le périmètre amendé. Aucun nouvel outil de mesure : journaux existants, captures, preuves du flux et jugement de Benjamin.

La décision du 10 octobre sur US80 de D01 dit que l’assemblage manuel ne remplace pas la preuve du nouveau flux, mais n’impose pas de refaire C01. Un premier vrai chantier de reprise est un candidat utile pour cette preuve, pas une décision déjà prise par Benjamin.

## Prototypes pour trancher la reprise

Trois structures, mêmes données synthétiques et style du cockpit actuel, sur les routes isolées `/` et `/projet/usine`. `?variant=A|B|C`, barre flottante et flèches clavier. Trois surfaces : accueil, page projet, résultat à juger. Scénarios : résultat prêt, décision bloquante, corrections après constats, accepté en attente de fusion, abandon, source illisible, rien à faire.

- **A — Boîte de réception** : prolonge D ; liste et détail, projets dessous ; projet en tableau. Coût de changement le plus faible. Premier choix proposé si l’organisation actuelle te convient.
- **B — Vue par chantiers** : réalisation / ton intervention / décisions hors chantier ; jugement en trois étapes. Rend la relation attente-travail visible, plus dense sur téléphone.
- **C — Une décision à la fois** : action prioritaire très visible, autres attentes en colonne ; projet centré sur le chantier qui demande une suite. Plus calme, avec un risque de moins voir les attentes secondaires.

Les boutons d’acceptation, constats et abandon du prototype simulent les transitions pour explorer l’interface. Ils ne proposent pas de remplacer `owner-answer` par un clic sans mots, commit et empreinte du dossier. L’écran d’essai ne simule pas le vrai produit à évaluer : il compare seulement l’organisation du parcours.

Aucun choix validé à ce stade. Après choix : conserver les mots de Benjamin dans Beads, figer le prototype choisi avec ses états, contrôler sa conformité, puis préparer la Spec avec les références figées exigées par D01. `/wayfinder`, `/to-spec` et `/to-tickets` restent à invocation de Benjamin ; cet audit ne les rejoue pas.

## Conditions de reprise

- Ne pas redispatcher C01 ni réveiller le Maire avec l’ancien graphe.
- Conserver la Spec historique ; nouvelle cible limitée aux écarts et parcours retenus.
- Pas de nouvelle dépendance front, modèle, API d’écriture ou service tiers pour les prototypes.
- Toute acceptation reste liée au produit et au dossier jugés, jamais à une simple fermeture ou couleur verte.
- Retour arrière du prototype : arrêter son serveur 8184 ; production et données réelles n’ont pas été touchées.
