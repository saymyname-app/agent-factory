# D01 « Delivery Workflow » — dossier de vérification finale

Ticket T32 (af-m23wru), Spec af-wf4w5r §14. Dossier assemblé par code (`gen_dossier.py`) à partir des pièces
rendues par les sessions vérificatrices : aucun état n'est écrit ou reformulé par la session opérateur.

**D01 n'est déclaré livré que par les mots de Benjamin.** Ce dossier ne le déclare pas.

## 1. Ce qui a été vérifié, et où

- Commit jugé (passe 2) : `main` `b9dfb77761197d526336e5f093faadcc1ca525b0`.
- Passe 1 : `main` `2053cc01897ff049949bf4eb340cf876e156dce1` (2026-10-09). Elle a donné 16 tickets de réparation (T37 à T52), tous fermés et sur `main` avant la passe 2.
- Pièces brutes (hors Git, sur l'hôte) : `/home/benja/t32-verification` (`pass1/`, `pass2/`, `recheck/`, `repairs/`, `window/`, `ruleset/`).
- Journal des gestes et des décisions : commentaires du bead af-m23wru.

## 2. Résumé

| Point de la Spec §14 | Résultat |
|---|---|
| 1. Assemblé | Oracle : 7 scénarios à sortie 0 sur 8 ; autres : one-ticket-closed-by-hand (exit=1). Voir §3 et §4. |
| 2. Revu contre la Spec | 263 lignes : 222 réalisée, 36 partielle, 4 réalisée autrement, 1 absente. Voir §6 et §9. |
| 3. Table exigence → mécanisme → preuve | `bin/method-check table` et `register` : voir §5. |
| 4. Aucun reste | 41 lignes non « réalisées » : chacune a une décision de Benjamin citée, ou attend sa décision. Voir §6. |
| 5. Ce qui n'a pas été vérifié | Voir §10. |

### Limites connues de D01 : où les lire

Tout ce qui est connu et n'est pas « réalisé » est écrit dans ce dossier, à quatre endroits :

- §6 : les lignes de la Spec non « réalisées », le constat de la session vérificatrice et la décision de Benjamin ;
- §7 : les écarts des tickets de réparation, acceptés ou réparés ;
- §10 : ce qui n'a pas été vérifié ;
- §12 : ce que les auteurs des réparations ont eux-mêmes déclaré « Non fait », « Écarts » et « Constats hors ticket » dans leurs PR.

## 3. Parcours de bout en bout sur la Fixture City (oracle)

`bin/fixture-city-oracle run <scénario> --delivery-driver tests/fixtures/fixture-city/delivery-driver`, au commit `b9dfb77`.

| Scénario | Sortie | Durée | Charge de l'hôte |
|---|---|---|---|
| outcome-accepted | 0 | 301s | 18.87 |
| outcome-abandoned | 0 | 126s | 11.45 |
| story-repaired-delivered | 0 | 163s | 5.46 |
| three-failures-parked | 0 | 72s | 4.30 |
| one-ticket-end-to-end | 0 | 63s | 5.48 |
| one-ticket-second-project | 0 | 47s | 6.55 |
| one-ticket-missing-condition | 0 | 47s | 5.76 |
| one-ticket-closed-by-hand | 1 | 20s | 5.58 |

`one-ticket-closed-by-hand` sort 1 par construction : le scénario ferme un ticket hors de sa porte et attend que le convoi s'arrête (même résultat à la passe 1).
Le scénario `outcome-accepted` va de la publication à l'Accepted Outcome.

## 4. Portes réellement exécutées pendant le parcours

Méthode : le parcours est rejoué avec deux relais (`python3`, `bash`) en tête de `PATH` qui notent chaque commande lancée (`tools/doors.sh`). Rien n'est modifié dans le dépôt.

| Commande changée par D01 | Exécutée par le parcours (passe 2) | Passe 1 |
|---|---|---|
| `bin/acceptance-session` | oui | oui |
| `bin/ci-minutes` | non | non |
| `bin/ci-run-tests` | non | non |
| `bin/ci-runner` | non | non |
| `bin/ci-test-seconds` | non | non |
| `bin/cockpit` | non | non |
| `bin/code-review` | oui | oui |
| `bin/convoy-advance` | oui | oui |
| `bin/convoy-state` | oui | oui |
| `bin/correction-round` | oui | oui |
| `bin/deliver-close` | non | non |
| `bin/delivery-role-sandbox` | non | non |
| `bin/dispatch-door` | oui | oui |
| `bin/escalation-door` | oui | oui |
| `bin/evidence-capture` | oui | oui |
| `bin/evidence-pack` | oui | oui |
| `bin/factory-boot` | non | non |
| `bin/factory-do-work-workspace` | non | non |
| `bin/factory-doctor` | non | non |
| `bin/factory-guard` | non | non |
| `bin/factory-revive` | non | non |
| `bin/fixture-city-oracle` | oui | oui |
| `bin/graph-review` | oui | oui |
| `bin/local-only-tests` | non | non |
| `bin/method-check` | non | non |
| `bin/operator-text-check` | non | non |
| `bin/outcome-evaluation` | oui | oui |
| `bin/outcome-promote` | oui | oui |
| `bin/overlap-conflict-log` | non | non |
| `bin/owner-answer` | oui | oui |
| `bin/planning-artifacts-close` | oui | oui |
| `bin/pr-autopilot` | non | non |
| `bin/project-launch` | oui | oui |
| `bin/project-planning-profile` | oui | oui |
| `bin/project-roadmap` | non | non |
| `bin/proposal-door` | non | non |
| `bin/prototype-conformance` | oui | non |
| `bin/prototype-fidelity` | oui | oui |
| `bin/rituals-status` | non | non |
| `bin/role-adoption-trial` | non | non |
| `bin/spec-approve` | oui | oui |
| `bin/spec-end` | oui | oui |
| `bin/spec-end-review` | oui | oui |
| `bin/spec-integration` | oui | oui |
| `bin/tdd-step` | oui | non |
| `bin/test-review` | oui | non |
| `bin/ticket-author` | oui | non |
| `bin/ticket-end` | oui | oui |
| `bin/ticket-evaluation` | oui | oui |
| `bin/ticket-exit` | oui | non |
| `bin/ticket-graph-publish` | oui | oui |
| `bin/upstream-skills-check` | non | non |

Les commandes « non » sont des outils de l'usine ou de l'ancien flux (CI, Cockpit, garde, démarrage, essais d'adoption) : elles ne font pas partie du parcours d'un convoi marqué. Elles ne sont donc pas prouvées par l'oracle (voir §10).

Sous-commandes exécutées, tous scénarios confondus (nombre d'appels) :

| Commande | Sous-commande | Appels |
|---|---|---|
| acceptance-session | close | 12 |
| acceptance-session | open | 3 |
| code-review | brief | 36 |
| code-review | record | 36 |
| code-review | settle | 72 |
| code-review | show | 72 |
| convoy-advance |  | 45 |
| convoy-advance | fx-convoy | 75 |
| convoy-state | acceptance-requested | 12 |
| convoy-state | add-evidence | 448 |
| convoy-state | close-convoy | 8 |
| convoy-state | close-ticket | 32 |
| convoy-state | launch-code-review | 36 |
| convoy-state | launch-end-review | 28 |
| convoy-state | launch-evaluation | 36 |
| convoy-state | launch-outcome-evaluation | 28 |
| convoy-state | launch-resume | 8 |
| convoy-state | launch-test-review | 36 |
| convoy-state | list | 220 |
| convoy-state | mark | 31 |
| convoy-state | open-code-review | 36 |
| convoy-state | open-end-review | 28 |
| convoy-state | open-evaluation | 36 |
| convoy-state | open-outcome-evaluation | 28 |
| convoy-state | open-resume | 12 |
| convoy-state | open-test-review | 36 |
| convoy-state | park | 4 |
| convoy-state | record-code-review | 36 |
| convoy-state | record-delivered | 16 |
| convoy-state | record-end-review | 28 |
| convoy-state | record-evaluation | 36 |
| convoy-state | record-evidence-pack | 12 |
| convoy-state | record-gate | 30 |
| convoy-state | record-grouped-request | 8 |
| convoy-state | record-outcome-evaluation | 28 |
| convoy-state | record-owner-answer | 8 |
| convoy-state | record-promotion | 4 |
| convoy-state | record-spec-end | 28 |
| convoy-state | record-test-review | 36 |
| convoy-state | release-evaluation | 28 |
| convoy-state | release-outcome-evaluation | 20 |
| convoy-state | set-branch | 40 |
| convoy-state | set-exit | 36 |
| convoy-state | set-fidelity | 24 |
| convoy-state | set-handoff | 36 |
| convoy-state | set-integration | 28 |
| convoy-state | set-merge | 32 |
| convoy-state | set-outcome-repair | 8 |
| convoy-state | set-session | 48 |
| convoy-state | set-tdd | 108 |
| convoy-state | show | 5933 |
| convoy-state | ticket | 36 |
| correction-round | settle | 72 |
| dispatch-door | fx-rig | 24 |
| escalation-door | benjamin | 8 |
| escalation-door | clear | 4 |
| escalation-door | list | 47 |
| evidence-capture | command | 352 |
| evidence-capture | comparison | 96 |
| evidence-capture | purge | 4 |
| evidence-capture | verify | 719 |
| evidence-pack | check | 58 |
| evidence-pack | generate | 12 |
| evidence-pack | promoted | 4 |
| fixture-city-oracle | run | 14 |
| graph-review | brief | 6 |
| graph-review | check | 8 |
| graph-review | record | 6 |
| graph-review | request | 6 |
| operator-config | language | 36 |
| outcome-evaluation | brief | 28 |
| outcome-evaluation | record | 28 |
| outcome-evaluation | settle | 52 |
| outcome-evaluation | verdict | 160 |
| outcome-promote | run | 16 |
| owner-answer | record | 6 |
| planning-artifacts-close |  | 8 |
| planning-run-reservation | check | 16 |
| project-launch | start | 332 |
| project-launch | stop | 324 |
| project-planning-profile | describe | 100 |
| project-planning-profile | human-approver | 32 |
| prototype-conformance | check | 8 |
| prototype-fidelity | check | 48 |
| prototype-fidelity | measure | 18 |
| provider-failover | status | 53 |
| spec-approve | bd-approve | 6 |
| spec-approve | outline | 132 |
| spec-end | check | 147 |
| spec-end | run | 56 |
| spec-end-review | brief | 28 |
| spec-end-review | record | 28 |
| spec-end-review | settle | 44 |
| spec-integration | merge | 72 |
| spec-integration | open | 23 |
| spec-integration | take-up | 28 |
| spec-integration | tests | 32 |
| tdd-step | check | 108 |
| tdd-step | freeze | 27 |
| tdd-step | green | 27 |
| tdd-step | red | 27 |
| test-review | brief | 36 |
| test-review | record | 36 |
| test-review | review | 27 |
| ticket-author | demonstrate | 27 |
| ticket-author | start | 36 |
| ticket-end | check | 51 |
| ticket-end | fidelity | 24 |
| ticket-end | settle | 32 |
| ticket-evaluation | brief | 36 |
| ticket-evaluation | record | 36 |
| ticket-evaluation | settle | 96 |
| ticket-exit | exit | 27 |
| ticket-exit | records | 36 |
| ticket-graph-publish | bd-patch | 8 |
| ticket-graph-publish | bd-publish | 6 |

## 5. Table exigence → mécanisme → preuve

La table est versionnée dans `docs/REQUIREMENT_TABLE.md` ; `bin/method-check` la contrôle.

```
method-check table: 13 exigences, chacune avec son mécanisme et sa preuve.
method-check register: 51 écarts, chacun avec son entrée, sa raison et sa base.
```

## 6. Lignes non « réalisées » et ce qui en est fait

Règle (Spec §14, point 4) : toute ligne non « réalisée » a un ticket de réparation fermé puis revérifié, ou une décision de Benjamin enregistrée avec ses mots.

| Ligne | État (passe 2) | Constat de la session vérificatrice | Passe 1 | Suite |
|---|---|---|---|---|
| US07 | partielle | La session neuve et le verdict par ticket existent et bloquent la publication. En revanche, le code n'interdit pas de lancer la revue après l'approbation du graphe ; le test principal initialise même un brouillon déjà approuvé avant sa revue. | réalisée | Acceptée par Benjamin comme limite connue (« Pour 2 on accepte les limites connues , on les notes en wiki », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| US09 | partielle | Les besoins déclarés sont typés et doivent être levés. Rien ne vérifie toutefois qu'un besoin connu n'a pas été omis : operator_needs: [] passe même si un secret, accès ou coût connu n'a pas été déclaré. | partielle | Acceptée par Benjamin comme limite connue (« Pour 2 on accepte les limites connues , on les notes en wiki », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| US14 | réalisée autrement | Il n’existe pas de confirmation séparée du prototype. Le résultat est obtenu par l’approbation unique de la Spec figée qui contient sa référence complète. | réalisée autrement | Acceptée par Benjamin sur le constat de la passe 1 (« ok pour tes recos, rédige les 11 tickets », 2026-10-09 vers 15:00). |
| US15 | partielle | L’inventaire est strictement vérifié lorsqu’une section Validated Prototype existe. Toutefois, bin/spec-approve:485-493 ne reconnaît une interface que par le marqueur textuel [interface] ; une Spec d’interface non marquée peut donc être approuvée sans prototype ni inventaire. | réalisée | Acceptée par Benjamin comme limite connue (« Pour 2 on accepte les limites connues , on les notes en wiki », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| US16 | partielle | La référence complète est bien recopiée pour les tickets reconnus comme interface. Mais bin/ticket-graph-publish:916-925 dépend notamment des user stories marquées [interface] ; un ticket d’interface non marqué peut ne recevoir aucun pointeur. | réalisée | Acceptée par Benjamin comme limite connue (« Pour 2 on accepte les limites connues , on les notes en wiki », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| US17 | partielle | Le Fold et ses dépendances sont imposés pour les tickets reconnus comme interface, et la fidélité vérifie les vraies adresses. Cependant, avec un seul prototype et aucun ticket reconnu comme interface, bin/ticket-graph-publish:984-1000 autorise l’absence de Fold ; la reconnaissance dépend du marqueur [interface]. | réalisée | Acceptée par Benjamin comme limite connue (« Pour 2 on accepte les limites connues , on les notes en wiki », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| US18 | partielle | Les contrôles demandés bloquent effectivement un ticket d’interface identifié et la fin de Spec. Un ticket d’écran qui n’a pas été reconnu comme interface est toutefois déclaré sans objet par bin/ticket-end:363-365 et échappe au contrôle. | réalisée | Acceptée par Benjamin comme limite connue (« Pour 2 on accepte les limites connues , on les notes en wiki », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| US19 | partielle | La liste et les images sont bien non bloquantes et apparaissent dans le dossier. Mais le brief de l’Evaluator ne fournit que branche, commit, chemin et états du prototype à bin/outcome-evaluation:728-739, sans URL rendue ni capture de référence ; la session chargée de relever les écarts à l’œil ne dispose donc pas d’un moyen explicite de voir le prototype. | réalisée | Acceptée par Benjamin comme limite connue (« Pour 2 on accepte les limites connues , on les notes en wiki », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| US28 | partielle | La règle et la Planning Exception sont branchées, et la revue peut bloquer une contradiction avec la Spec. En revanche, le brief de revue ne reçoit pas les autres tickets : aucun contrôle ne détecte mécaniquement un changement de comportement fixé uniquement par un ticket frère. | réalisée | Acceptée par Benjamin comme limite connue (« Pour 2 on accepte les limites connues , on les notes en wiki », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| US36 | partielle | La revue est confiée à un rôle distinct, cloisonné en lecture seule, et la fusion attend son résultat. En revanche, le flux accepte explicitement le même modèle que l'auteur et ne fait qu'enregistrer cette absence d'indépendance. | partielle | Acceptée par Benjamin sur le constat de la passe 1 (« ok pour tes recos, rédige les 11 tickets », 2026-10-09 vers 15:00). |
| US37 | partielle | Le brief exclut le handoff, les messages de commit et les raisons d'amendement, et contient les sources prévues. Toutefois, le sandbox donne accès au dépôt entier et la formule autorise le skill à y rechercher d'autres éléments : la restriction « ne lire que » n'est donc pas imposée mécaniquement. | réalisée | Acceptée par Benjamin comme limite connue (« Pour 2 on accepte les limites connues , on les notes en wiki », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| US53 | partielle | L’arrêt sur rouge est effectif, avec la seule exception du repair. En revanche, à deux Planning Exceptions, le code laisse explicitement continuer les tickets au travail et lance leurs reprises ; le convoi ne s’arrête donc pas entièrement. | partielle | Acceptée par Benjamin sur le constat de la passe 1 (« ok pour tes recos, rédige les 11 tickets », 2026-10-09 vers 15:00). |
| US66 | partielle | Le mécanisme est une consigne rendue dans la sortie de la commande, sans rôle ni porte qui puisse empêcher une session de la violer. L’essai avec une vraie session est optionnel et passe sans lancer de modèle lorsque ACCEPTANCE_SESSION_TRIAL_SESSION n’est pas positionné. | réalisée | Acceptée par Benjamin comme limite connue (« Pour 2 on accepte les limites connues , on les notes en wiki », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| US69 | partielle | Le routage est bien fait par du code, mais il ne vérifie pas que le comportement demandé est réellement exigé par la story ou l’ancre citée. Un constat de goût peut citer une story existante et être routé en réparation au lieu de passer par une Planning Exception. | partielle | Acceptée par Benjamin comme limite connue (« Pour 2 on accepte les limites connues , on les notes en wiki », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| US80 | absente | Aucun code ne relivre Cockpit V2 par le nouveau flux et aucun artefact de code n'enregistre un jugement de Benjamin. La fixture existante démontre seulement que l'ancien brouillon n'est pas publiable. | absente | Notée comme reportée par la Spec (cas de validation Cockpit V2, après D01) : « ok pour tes recos, rédige les 11 tickets », 2026-10-09 vers 15:00. |
| US81 | partielle | Le parcours assemblé de bout en bout existe. Aucun mécanisme branché dans le flux ne produit toutefois la revue complète de tout le diff contre cette Spec, un état pour chaque user story et décision, puis la preuve d'absence de reste. | partielle | Notée comme reportée par la Spec (c'est la présente vérification finale, tenue par une session opérateur) : « ok pour tes recos, rédige les 11 tickets », 2026-10-09 vers 15:00. |
| US84 | partielle | Le démarrage par le Mayor est techniquement refusé et une fermeture manuelle devient ensuite un incident. Aucun garde de code n'empêche cependant le Mayor d'écrire directement un statut, des métadonnées, une dépendance ou une fermeture dans le tracker ; ces actions ne sont bornées que par son prompt puis détectées après coup. | partielle | Acceptée par Benjamin sur le constat de la passe 1 (« ok pour tes recos, rédige les 11 tickets », 2026-10-09 vers 15:00). |
| D1.3 | partielle | implement est lu intact et wayfinder, to-spec et to-tickets restent interdits à l'invocation implicite. Aucun prompt ni aucune formule du flux ne référence implement-spec : la seconde skill réservée à l'humain n'est donc pas prise en charge comme exigé. | partielle | Acceptée par Benjamin sur le constat de la passe 1 (« ok pour tes recos, rédige les 11 tickets », 2026-10-09 vers 15:00). |
| D1.6 | partielle | Le dépôt ne contient plus resolving-merge-conflicts et possède GLOSSARY.md à sa racine. Aucun code ni test n'impose cependant un GLOSSARY.md dans chaque projet ; un seul fichier GLOSSARY.md est suivi dans ce commit. | partielle | Acceptée par Benjamin sur le constat de la passe 1 (« ok pour tes recos, rédige les 11 tickets », 2026-10-09 vers 15:00). |
| D2.9 | partielle | La levée préalable des besoins déclarés est mécanique. Il manque un mécanisme qui confronte operator_needs à la planification pour détecter un secret, accès, projet ou coût connu mais omis. | partielle | Acceptée par Benjamin comme limite connue (« Pour 2 on accepte les limites connues , on les notes en wiki », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| D2.10 | partielle | La porte accepte et ordonne correctement une première tranche censée établir la recette. Mais le vrai flux auteur exige déjà un bloc launch valide pour connaître le périmètre, la commande de test et les données avant l'étape rouge ; aucun bootstrap ne permet à une tranche de partir d'un profil sans recette. | réalisée | Limite acceptée par Benjamin ; l'écriture de la recette de lancement du projet agent-factory est inscrite au chantier Cockpit V2, bead af-mjfvwx (« Pour 3 on accepte la limite et on inscrit l'ecriture de la recette de lancement du projet au cockpit V2 », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| D2.12 | partielle | Les questions, les deux passes et les décisions de Benjamin existent. Le même modèle que l'auteur n'est toutefois pas refusé, seulement signalé à bin/graph-review:206, et le code n'impose pas que la revue précède l'approbation du brouillon. | partielle | Acceptée par Benjamin sur le constat de la passe 1 (« j'approuve le brouillon, publie ; accepter pour D2.12 et D11.2 », 2026-10-09 15:06). |
| D3.1 | réalisée autrement | Toutes les propriétés statiques de la version figée et de sa branche sont contrôlées. La confirmation n’est pas un acte distinct : elle est réalisée par l’approbation humaine de la Spec qui porte cette version. | partielle | Acceptée par Benjamin comme limite connue (« Pour 2 on accepte les limites connues , on les notes en wiki », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| D3.4 | partielle | La couverture visible, les régions HTML prédéfinies et l’absence d’une ancre dans le livré sont contrôlées. Le code ne connaît toutefois aucune liste des « sortes de composant » : hors REGION_ELEMENTS, il ne peut pas prouver qu’un attribut nommé existe sur chaque type de composant. | partielle | Acceptée par Benjamin comme limite connue (« Pour 2 on accepte les limites connues , on les notes en wiki », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| D3.6 | partielle | Le second passage par spec-approve est branché et bloquant. Aucun skill, formule ou ordre de la session prototype n’appelle prototype-conformance avant que la version figée soit montrée à Benjamin. | réalisée | Acceptée par Benjamin comme limite connue (« Pour 2 on accepte les limites connues , on les notes en wiki », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| D3.7 | partielle | Le mécanisme réalise toutes les propriétés du Fold pour les tickets identifiés comme interface. Mais bin/ticket-graph-publish:984-1000 n’exige aucun Fold pour un prototype unique sans ticket reconnu comme interface, reconnaissance qui dépend notamment du marqueur [interface]. | partielle | Acceptée par Benjamin comme limite connue (« Pour 2 on accepte les limites connues , on les notes en wiki », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| D3.8 | partielle | Les contrôles mécaniques, les captures contemporaines, l’image de différence sans seuil et la liste non notée sont présents. La partie « écarts d’un agent en contexte neuf » reste incomplète : le brief lui donne seulement une référence Git du prototype, sans rendu ou URL de référence lui permettant la comparaison visuelle demandée. | réalisée | Acceptée par Benjamin comme limite connue (« Pour 2 on accepte les limites connues , on les notes en wiki », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| D5.1 | partielle | Les quatre conduites sont présentes et branchées, et le Declared Scope ne bloque pas les fichiers nécessaires. Toutefois, comme pour US28, aucun contrôle ne fournit au relecteur tous les tickets frères permettant de détecter mécaniquement tout comportement fixé ailleurs. | réalisée | Acceptée par Benjamin comme limite connue (« Pour 2 on accepte les limites connues , on les notes en wiki », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| D5.20 | partielle | La rubrique Fait est obligatoire et la démonstration est prouvée séparément. Aucun schéma ni contrôle de la formule n'exige toutefois une entrée par critère ni que done explique comment voir la ligne de démonstration. | réalisée | Acceptée par Benjamin comme limite connue (« Pour 2 on accepte les limites connues , on les notes en wiki », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| D5.24 | réalisée autrement | Tous les relevés demandés sont produits par le code. Les tests du résultat fusionné ne sont pas ajoutés rétroactivement au Handoff : ils sont obtenus autrement, comme pièce de preuve merged_tests séparée, puis exigés par la porte ticket-end. | réalisée autrement | Acceptée par Benjamin sur le constat de la passe 1 (« ok pour tes recos, rédige les 11 tickets », 2026-10-09 vers 15:00). |
| D8.13 | partielle | Le caractère non mesuré est déclaré et plusieurs bornes sont configurables. Cependant le tour de correction, l’amendement et le nombre de refus de test restent codés en constantes, et aucun mécanisme ni test ne mesure ces valeurs dans le cas de validation. | partielle | Notée comme reportée par la Spec (bornes à mesurer sur le cas de validation) : « ok pour tes recos, rédige les 11 tickets », 2026-10-09 vers 15:00. |
| D9.2 | partielle | Le magasin, son classement, les empreintes et la purge après promotion sont réalisés. En revanche, bin/project-launch:148 exige seulement un jeu de données nommé et déclaré : le code ne vérifie ni sa provenance ni son contenu synthétique. | partielle | Acceptée par Benjamin sur le constat de la passe 1 (« ok pour tes recos, rédige les 11 tickets », 2026-10-09 vers 15:00). |
| D9.7 | partielle | Le chemin vert mécanique est présent et branché. La condition n’exige toutefois pas strictement des contrôles verts : un résultat rouge dont tous les écarts ont été acceptés par Planning Exception devient « accepté par Benjamin » et passe également. | partielle | Acceptée par Benjamin sur le constat de la passe 1 (« ok pour tes recos, rédige les 11 tickets », 2026-10-09 vers 15:00). |
| D9.23 | partielle | Le rejeu, la fusion, l’enregistrement des deux commits et le retour par repair existent lorsque la branche protégée a avancé. Si elle n’a pas avancé, le code fusionne directement sans rejouer après l’acceptation les tests, le démarrage et la fidélité, alors que la ligne ne prévoit pas cette dispense. | réalisée | Acceptée par Benjamin comme limite connue (« Pour 2 on accepte les limites connues , on les notes en wiki », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| D10.3 | partielle | L’en-tête couvre tous les champs demandés sauf une adresse du produit effectivement lancé pour le jugement : il annonce au contraire que le produit sera lancé plus tard par l’Acceptance Session. Les éventuelles adresses affichées sont celles de l’Outcome Evaluation déjà arrêtée, et un dossier non conforme antérieur à cette évaluation n’en porte aucune. | réalisée | Acceptée par Benjamin comme limite connue (« Pour 2 on accepte les limites connues , on les notes en wiki », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| D11.2 | partielle | Le lancement, l’arrêt et le traitement d’une panne sont codés et reliés. En revanche, ouvrir le produit dans un navigateur, y naviguer, rédiger puis enregistrer les constats n’est orchestré par aucun rôle ou formule; seules des consignes sont retournées à la session. | partielle | Acceptée par Benjamin sur le constat de la passe 1 (« j'approuve le brouillon, publie ; accepter pour D2.12 et D11.2 », 2026-10-09 15:06). |
| D11.7 | partielle | Le code valide l’existence de la story ou de l’ancre citée, mais pas que le comportement demandé est réellement exigé par elle. Une citation valide mais sans rapport avec le constat suffit donc à obtenir la route réparation. | partielle | Acceptée par Benjamin comme limite connue (« Pour 2 on accepte les limites connues , on les notes en wiki », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| D11.8 | partielle | La Planning Exception unique et la vérification de la Spec amendée et du graphe révisé existent. Toutefois, la décision repose sur la seule validité de la citation: un nouveau comportement peut citer une story existante et contourner cette route. | partielle | Acceptée par Benjamin comme limite connue (« Pour 2 on accepte les limites connues , on les notes en wiki », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| D11.11 | partielle | Les trois issues sont affichées et enregistrées sur la porte, et « accepté » est absent. Mais relancer et retourner à la planification n’ont aucune suite codée, et même l’option abandon de record ne ferme pas le convoi; le stop reste en place. | réalisée | Acceptée par Benjamin comme limite connue (« Pour 2 on accepte les limites connues , on les notes en wiki », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| D12.8 | réalisée autrement | Le flux dispose toujours de k et le consomme, mais le profil n'est pas obligé de le déclarer : l'absence est réalisée autrement par le défaut mécanique 3. | réalisée | Acceptée par Benjamin comme limite connue (« Pour 2 on accepte les limites connues , on les notes en wiki », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| D13.15 | partielle | Les extensions de spec-approve et de la porte de publication sont présentes et branchées. En revanche, le code final ne permet pas d'établir que chaque ticket D01 dépendant d'un mécanisme Gas City a historiquement commencé par un essai réel, ni n'impose cet ordre temporel. | partielle | Notée comme reportée par la Spec : « ok pour tes recos, rédige les 11 tickets », 2026-10-09 vers 15:00. |

### Décisions de Benjamin citées

- **2026-10-09 vers 15:00 (Paris), chat live** — « ok pour tes recos, rédige les 11 tickets » — en réponse à la recommandation de la session opérateur po-agent/64db146a, sur les constats de la passe 1 : accepter US36, US53, US84, D0.3, D9.2, D9.7, D1.3, D1.6, US14, D5.24 ; noter comme reportées par la Spec US80, D8.13, US81, D13.15.
- **2026-10-09 15:06 (Paris), chat live** — « j'approuve le brouillon, publie ; accepter pour D2.12 et D11.2 » — approbation du brouillon des réparations T37 à T47 et acceptation de D2.12 et D11.2, sur les constats de la passe 1.
- **2026-10-09 16:48 (Paris), chat live** — « j'approuve T48 et T49, publie ; reste sur le PC » — approbation du brouillon des réparations T48 et T49.
- **2026-10-09 18:16 (Paris), chat live** — « Oui j'accepte les 2 » — en réponse à la recommandation d'accepter les deux écarts de T46 (critères 3 et 5), déclarés par l'auteur dans la PR 478.
- **2026-10-09 21:38 (Paris), chat live** — « ok pour tes recommandations » — en réponse à trois recommandations de la session opérateur po-agent/736b05c5 : accepter l'écart de T38 critère 1 ; réparer T40 critère 4 par T52 ; approuver le texte de T50, T51 et T52.
- **2026-10-10 vers 00:22 (Paris), chat live** — « ok recommandation. » — en réponse à la question « Geler la liste des réparations à T52 ? » : plus de réparation sauf parcours complet cassé ; les autres écarts sont inscrits ici et tranchés par lui en une fois.
- **2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée, chat live** — « Répare 1. Pour 2 on accepte les limites connues , on les notes en wiki. Pour 3 on accepte la limite et on inscrit l'ecriture de la recette de lancement du projet au cockpit V2. Le 4: les 3 ecarts sur des réparations, j'accepte tes recommandations. Et D01 est considéré livré dès qu'on a fait toutes ces bricoles. Il ne faut qu'il reste plus rien latent avec D01, tout ce qui est connu est mémorisé / noté en limite / mémorisé pour la suite. » — en réponse au lot de fin présenté à 10:05 par la session opérateur po-agent/736b05c5, en quatre points : (1) T49, quatre essais hors CI rouges sur main et photographie de sécurité affaiblie ; (2) les 25 lignes sans décision hors D2.10 ; (3) D2.10 ; (4) T43 critère 1, T44 critère 2, changement de bin/spec-approve par T52. Lecture de la session opérateur : la déclaration « livré » est sous condition, elle vaut une fois ces points faits.

### Comparaison des deux passes

- Non « réalisées » à la passe 1 : 41. À la passe 2 : 41.
- Devenues « réalisées » entre les deux passes (18) : D0.3, D12.2, D12.6, D12.9, D2.2, D3.9, D4.2, D5.13, D5.3, D5.9, D6.2, D7.5, D8.3, D8.8, US20, US24, US42, US75.
- Non « réalisées » aux deux passes (23) : D1.3, D1.6, D11.2, D11.7, D11.8, D13.15, D2.12, D2.9, D3.1, D3.4, D3.7, D5.24, D8.13, D9.2, D9.7, US09, US14, US36, US53, US69, US80, US81, US84.
- « Réalisées » à la passe 1, plus à la passe 2 (18) : D10.3, D11.11, D12.8, D2.10, D3.6, D3.8, D5.1, D5.20, D9.23, US07, US15, US16, US17, US18, US19, US28, US37, US66. Ce sont d'autres sessions, sur le même texte : deux lectures indépendantes ne trouvent pas les mêmes écarts.

## 7. Tickets de réparation (T37 à T52) et leur revérification

Chaque réparation a été revérifiée après sa fusion par une session Codex neuve, en lecture seule (`tools/recheck.sh`, pièces `recheck/T<n>.json`).

| Ticket | Bead | Commit revérifié | Démonstration | Critères | Régression relevée | Suite |
|---|---|---|---|---|---|---|
| T37 | af-fg8lhx | `40a72ce` | tenu | 1 : tenu ; 2 : tenu ; 3 : tenu ; 4 : tenu | rien | Rien. |
| T38 | af-8o4jcp | `20ee4b2` | non tenu | 1 : non tenu ; 2 : tenu ; 3 : tenu ; 4 : non tenu ; 5 : tenu | rien | Critère 1 : écart déclaré par l'auteur (PR 480), accepté par Benjamin (« ok pour tes recommandations », 2026-10-09 21:38). Critère 4 : réparé par T50. |
| T39 | af-ea93m9 | `d73348a` | tenu | 1 : tenu ; 2 : tenu ; 3 : tenu | rien | Rien. |
| T40 | af-o6tu3z | `78c6912` | non tenu | 1 : tenu ; 2 : tenu ; 3 : tenu ; 4 : non tenu | rien | Critère 4 : réparé par T52. |
| T41 | af-rqgtpi | `9c6a405` | non tenu | 1 : tenu ; 2 : tenu ; 3 : non tenu | rien | Critère 3 : réparé par T51. |
| T42 | af-rc0ozs | `b0707aa` | non vérifiable en lecture seule | 1 : non vérifiable en lecture seule ; 2 : tenu ; 3 : tenu ; 4 : non vérifiable en lecture seule | rien | Critères 1 et 4 : l'essai tests/fresh-sessions-isolated-city-test.sh sort 0 au commit jugé (essais hors CI ci-dessous). |
| T43 | af-kwodm8 | `48fa1ae` | non tenu | 1 : non tenu ; 2 : tenu ; 3 : tenu | rien | Critère 1 : écart déclaré par l'auteur (PR 484), accepté par Benjamin (« Le 4: les 3 ecarts sur des réparations, j'accepte tes recommandations », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| T44 | af-m1iibk | `005ef19` | non tenu | 1 : tenu ; 2 : non tenu ; 3 : tenu | rien | Critère 2 : écart en partie déclaré par l'auteur (PR 487), accepté par Benjamin (« Le 4: les 3 ecarts sur des réparations, j'accepte tes recommandations », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |
| T45 | af-7y457s | `4710a11` | tenu | 1 : tenu ; 2 : tenu ; 3 : tenu | rien | Rien. |
| T46 | af-lb9zkz | `40a72ce` | tenu | 1 : tenu ; 2 : tenu ; 3 : non tenu ; 4 : tenu ; 5 : non tenu | rien | Critères 3 et 5 : écarts déclarés par l'auteur (PR 478), acceptés par Benjamin (« Oui j'accepte les 2 », 2026-10-09 18:16). |
| T47 | af-i2lckq | `01ec3d8` | tenu | 1 : tenu ; 2 : tenu ; 3 : tenu | rien | Rien. |
| T48 | af-1zxao6 | `6122051` | non vérifiable en lecture seule | 1 : non vérifiable en lecture seule ; 2 : non vérifiable en lecture seule ; 3 : tenu ; 4 : tenu | rien | Critères 1 et 2 : l'essai tests/ticket-graph-publish-patch-edges-real-tracker-test.sh sort 0 au commit jugé (essais hors CI ci-dessous). |
| T49 | af-xcfup7 | `b9dfb77` | non vérifiable en lecture seule | 1 : non vérifiable en lecture seule ; 2 : non vérifiable en lecture seule ; 3 : non vérifiable en lecture seule ; 4 : tenu | tests/prototype-fidelity-demonstration-test.sh:65 — la photographie de sécurité remplace `rev-list --all --count` par le seul `rev-parse HEAD`; l’assertion de la ligne 216 ne détecte donc plus l’ajout ou la suppression d’un ref non-HEAD dans le dépôt de l’usine, ce qui affaiblit la preuve que l’essai n’a pas modifié la racine live. | Critères 1 à 3 non tenus au commit jugé : quatre essais rouges depuis la racine (ci-dessous). Régression relevée, non déclarée par l'auteur. Réparation décidée par Benjamin (« Répare 1 », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée) : un seul ticket groupé, T53, pas encore publié à la date de ce dossier. |
| T50 | af-yorkna | `4adf396` | tenu | 1 : tenu ; 2 : tenu | rien | Rien. |
| T51 | af-6h09r6 | `484a329` | tenu | 1 : tenu ; 2 : tenu | rien | Rien. |
| T52 | af-ezqgma | `96d338a` | tenu | 1 : tenu ; 2 : tenu | rien | Écart déclaré par l'auteur (PR 499) : bin/spec-approve approuve de nouveau une Spec déjà approuvée dont le texte a changé. Accepté par Benjamin (« Le 4: les 3 ecarts sur des réparations, j'accepte tes recommandations », 2026-10-10, entre 10:05 et 11:59 (Paris), heure exacte non relevée). |

### Essais hors CI (local-only) au commit jugé

Ils rendent l'état des critères « non vérifiable en lecture seule » de T42, T48 et T49.

```
local-only exit=1 6448s load=4.30
```

Rejeu, un par un et depuis la racine de l'usine, des essais en échec depuis le worktree (`tools/pass2-rerun.sh`, sorties dans `pass2/local-only-rerun/`) :

`racine f18f4567eaced82a4bbaad8cf5e43b16d26f13a6 (commit jugé b9dfb77761197d526336e5f093faadcc1ca525b0) load 3.74 6.08 9.34 2026-10-10T09:29:10+02:00`

| Essai | Sortie | Durée | Charge | Dernière ligne |
|---|---|---|---|---|
| backup-freshness-order-test.sh | 0 | 63s | 3.74 | PASS: backup-freshness pages the Mayor for a stale archive with bead activity, and stays quiet otherwise |
| code-review-isolated-city-test.sh | 1 | 45s | 3.49 | } |
| factory-orphan-sweep-order-test.sh | 0 | 53s | 3.89 | PASS: factory-orphan-sweep keeps po-agent/* and planning-plane claims, releases genuinely orphaned delivery claims, keeps a claim intact during a city |
| factory-session-loop-guard-order-test.sh | 0 | 1s | 3.96 | PASS: city-local factory-session-loop-guard Order is discoverable and deterministic |
| factory-watchdog-order-test.sh | 0 | 0s | 3.96 | PASS: city-local factory-watchdog Order is discoverable and deterministic |
| local-only-tests-order-test.sh | 0 | 65s | 3.96 | PASS: local-only-tests files a bead and pages the Mayor on a failing local-only test |
| orders-validate-test.sh | 0 | 9s | 3.45 | PASS: every orders/*.toml (19) validates through gc order show |
| second-project-isolated-city-test.sh | 1 | 486s | 3.55 | FAIL: the ticket was not written by one author session (3) |
| spec-integration-demonstration-test.sh | 1 | 167s | 16.46 | } |
| ticket-end-isolated-city-test.sh | 0 | 390s | 5.96 | PASS: a ticket whose nine conditions hold was closed by the ticket-end gate, by the order; the same walk with a condition missing stayed open and the |
| ticket-evaluation-isolated-city-test.sh | 1 | 51s | 18.91 | } |

- Sept essais ne sont rouges que depuis un worktree et verts depuis la racine : six essais d'ordres (chemin de l'usine écrit en dur dans les ordres, déclaré par l'auteur de T49 dans la PR 496) et `ticket-end-isolated-city`.
- Quatre essais restent rouges depuis la racine, hôte à une charge de 3 à 19. Trois (`code-review-isolated-city`, `spec-integration-demonstration`, `ticket-evaluation-isolated-city`) s'arrêtent sur le refus livré par T42 : « une session neuve par relecture, revue ou évaluation » ; leur harnais rend deux relectures sous le même nom de session. Le quatrième (`second-project-isolated-city`) va jusqu'à la fermeture du ticket par sa porte, neuf conditions tenues, puis échoue sur son dernier contrôle : trois sessions d'auteur relevées au lieu d'une.
- L'auteur de T49 a relevé ces quatre essais à sortie 0 dans la PR 496 ; ses commits vont du 2026-10-09 23:03 au 2026-10-10 02:52 (Paris), T42 a fusionné à 01:14. Les essais local-only ne tournent pas en CI : aucune CI ne pouvait voir cette rencontre entre T42 et T49.
- Conséquence : la ligne de démonstration de T49 (« bin/local-only-tests sort 0 sur main ») et ses critères 1 à 3 ne sont pas tenus au commit jugé. L'ordre de nuit `local-only-tests` (04:00) ouvrira de lui-même un ticket et appellera le Mayor sur ces quatre échecs.

### Batterie complète de tests au commit jugé

Lancée à la main dans le worktree (`bin/ci-run-tests --jobs 12`, toujours complète), en compensation de la règle « PR à jour avec main » levée pendant le lot (§11).

```
battery exit=0 1423s load=4.04
  tests/reversibility-test.py                                            OK      1s
  tests/prototype-conformance-test.py                                    OK      3s
  tests/factory-guard-dirty-tree-test.sh                                 OK     22s
  tests/owner-exception-amended-spec-fixture-city-test.py                OK    153s
  tests/factory-guard-live-root-sync-test.sh                             OK     40s
  tests/outcome-promote-test.py                                          OK    262s
  tests/factory-guard-exec-bit-test.sh                                   OK     66s
  tests/convoy-advance-test.py                                           OK   1085s
  tests/convoy-stops-fixture-city-test.py                                OK   1143s
  tests/fixture-city-oracle-test.py                                      OK   1423s

ci-run-tests: ran 171 test(s), 0 failure(s)
```

## 8. Sessions vérificatrices

- Toutes les sessions vérificatrices sont des sessions `codex exec -s read-only` neuves, modèle `gpt-5.6-sol`, une par tâche.
- Auteurs de D01, d'après les lignes Co-Authored-By des commits `d31c6403^..b9dfb77` : Claude Opus 5.5 <noreply@anthropic.com> (106 commits) ; Claude Fable 5.1 <noreply@anthropic.com> (4 commits) ; Claude Sonnet 5 <noreply@anthropic.com> (1 commits).
- Aucune session vérificatrice n'a écrit de ticket de D01 : elles sont créées pour une lecture, en lecture seule, puis terminées.
- Les sessions opérateur (po-agent/64db146a, po-agent/736b05c5 puis po-agent/d46f42c1) sont du modèle des auteurs (Claude Opus 5.5) : elles ont lancé, assemblé et consigné, sans rendre d'état.
- Écart de forme avec la Spec §14 point 2 (« une session relecteur ») : la revue est faite par 9 sessions, une par bloc de lignes, pour que chacune lise la Spec entière et son bloc sans dépasser un contexte sain.

### Revue, passe 2

| Tâche | Session | Modèle | Début | Fin |
|---|---|---|---|---|
| B1-contrat-entree | 01a123ff-e9ff-75e2-bbba-9f90c051c26c | gpt-5.6-sol | 2026-10-10T06:08:56+02:00 | 2026-10-10T06:14:58+02:00 |
| B2-prototype | 01a123ff-e9c2-7f11-b814-c9a8a58e06a3 | gpt-5.6-sol | 2026-10-10T06:08:56+02:00 | 2026-10-10T06:15:29+02:00 |
| B4-revue-evaluation | 01a12405-ea95-7fd0-b9a1-4d22caf98a67 | gpt-5.6-sol | 2026-10-10T06:15:29+02:00 | 2026-10-10T06:20:25+02:00 |
| B3-travail-ticket | 01a12405-7181-7842-b2e9-65fd8fce10df | gpt-5.6-sol | 2026-10-10T06:14:58+02:00 | 2026-10-10T06:21:46+02:00 |
| B6-fin-de-spec | 01a1240b-ab81-7f63-b265-d48abe4d6e2c | gpt-5.6-sol | 2026-10-10T06:21:46+02:00 | 2026-10-10T06:26:46+02:00 |
| B5-fusion-fin-ticket | 01a1240a-6d5c-73c0-8cc6-9afb1912912f | gpt-5.6-sol | 2026-10-10T06:20:25+02:00 | 2026-10-10T06:26:58+02:00 |
| B7-acceptation | 01a12410-3f93-7b51-aa53-8049bc80f122 | gpt-5.6-sol | 2026-10-10T06:26:46+02:00 | 2026-10-10T06:29:46+02:00 |
| B8-methode-orchestration | 01a12410-6e2b-7d01-988c-5407df17a332 | gpt-5.6-sol | 2026-10-10T06:26:58+02:00 | 2026-10-10T06:32:54+02:00 |
| B9-usine-table | 01a12412-fe30-7c71-96ea-d235a402690e | gpt-5.6-sol | 2026-10-10T06:29:46+02:00 | 2026-10-10T06:38:30+02:00 |

### Revue, passe 1

| Tâche | Session | Modèle | Début | Fin |
|---|---|---|---|---|
| B1-contrat-entree | 01a12099-edda-73b2-8d5a-936d73b492e5 | gpt-5.6-sol | 2026-10-09T14:18:41+02:00 | 2026-10-09T14:24:54+02:00 |
| B2-prototype | 01a12099-edee-79a3-8ba5-98a4b512a262 | gpt-5.6-sol | 2026-10-09T14:18:41+02:00 | 2026-10-09T14:26:46+02:00 |
| B3-travail-ticket | 01a1209f-a0f3-7c31-8f3b-adb1dc0b74d8 | gpt-5.6-sol | 2026-10-09T14:24:54+02:00 | 2026-10-09T14:33:50+02:00 |
| B4-revue-evaluation | 01a120a1-5680-7720-b7c6-da93bfc325fe | gpt-5.6-sol | 2026-10-09T14:26:46+02:00 | 2026-10-09T14:37:30+02:00 |
| B5-fusion-fin-ticket | 01a120a7-cdef-7fd3-9251-9120845feb38 | gpt-5.6-sol | 2026-10-09T14:33:50+02:00 | 2026-10-09T14:43:52+02:00 |
| B6-fin-de-spec | 01a120ab-2ad0-7323-8d14-54109a6da6c8 | gpt-5.6-sol | 2026-10-09T14:37:30+02:00 | 2026-10-09T14:44:28+02:00 |
| B7-acceptation | 01a120b0-fe08-7ed1-a462-91398e85edab | gpt-5.6-sol | 2026-10-09T14:43:52+02:00 | 2026-10-09T14:48:00+02:00 |
| B8-methode-orchestration | 01a120b1-8c33-7600-bb57-25d949bd3610 | gpt-5.6-sol | 2026-10-09T14:44:28+02:00 | 2026-10-09T14:54:57+02:00 |
| B9-usine-table | 01a120b4-c80f-70c3-8a14-43cd8ccb99ac | gpt-5.6-sol | 2026-10-09T14:48:00+02:00 | 2026-10-09T14:56:46+02:00 |

### Revérification des réparations

| Tâche | Session | Modèle | Début | Fin |
|---|---|---|---|---|
| T37 | 01a12161-39af-77c1-8745-51ccc737c558 | gpt-5.6-sol | 2026-10-09T17:56:20+02:00 | 2026-10-09T17:59:35+02:00 |
| T46 | 01a12164-356d-7bd3-9343-93b5a10599b7 | gpt-5.6-sol | 2026-10-09T17:59:37+02:00 | 2026-10-09T18:02:59+02:00 |
| T38 | 01a121a2-e049-7860-bcb7-03f2fd23e805 | gpt-5.6-sol | 2026-10-09T19:08:03+02:00 | 2026-10-09T19:10:52+02:00 |
| T41 | 01a121de-5335-7d43-991d-b4ee0575fed6 | gpt-5.6-sol | 2026-10-09T20:12:58+02:00 | 2026-10-09T20:15:25+02:00 |
| T40 | 01a12217-d071-77e2-a90b-d41183467f04 | gpt-5.6-sol | 2026-10-09T21:15:46+02:00 | 2026-10-09T21:18:09+02:00 |
| T47 | 01a12245-4b09-74e2-bed1-c03df7d6aac1 | gpt-5.6-sol | 2026-10-09T22:05:27+02:00 | 2026-10-09T22:07:17+02:00 |
| T43 | 01a1226a-e3db-7dc1-bd11-10bbadd6c28b | gpt-5.6-sol | 2026-10-09T22:46:30+02:00 | 2026-10-09T22:48:51+02:00 |
| T44 | 01a1228c-0f27-7b33-8c9f-07d27482ea4a | gpt-5.6-sol | 2026-10-09T23:22:43+02:00 | 2026-10-09T23:25:50+02:00 |
| T45 | 01a122b1-a8ca-7b03-8d77-8028865ffe13 | gpt-5.6-sol | 2026-10-10T00:03:48+02:00 | 2026-10-10T00:05:52+02:00 |
| T48 | 01a122d0-d236-7c43-a8c3-c23d47e2b843 | gpt-5.6-sol | 2026-10-10T00:37:50+02:00 | 2026-10-10T00:39:59+02:00 |
| T42 | 01a122f5-d798-7c31-b7cf-d8f5cabd6bea | gpt-5.6-sol | 2026-10-10T01:18:16+02:00 | 2026-10-10T01:20:46+02:00 |
| T39 | 01a1232c-c5d7-78d2-b56d-9c31cea9d425 | gpt-5.6-sol | 2026-10-10T02:18:15+02:00 | 2026-10-10T02:20:12+02:00 |
| T50 | 01a1236c-c563-7283-8d3f-007484ab570f | gpt-5.6-sol | 2026-10-10T03:28:11+02:00 | 2026-10-10T03:29:35+02:00 |
| T52 | 01a123cb-59c7-7fa1-81f3-55e16d8c99a8 | gpt-5.6-sol | 2026-10-10T05:11:29+02:00 | 2026-10-10T05:14:55+02:00 |
| T51 | 01a123e6-849e-7761-973b-3340d0746082 | gpt-5.6-sol | 2026-10-10T05:41:11+02:00 | 2026-10-10T05:43:08+02:00 |
| T49 | 01a123ff-826c-7fa3-bba3-c51a11649d49 | gpt-5.6-sol | 2026-10-10T06:08:29+02:00 | 2026-10-10T06:11:47+02:00 |

## 9. Les 263 lignes : état et preuve

84 user stories et 179 décisions des sections 0 à 13 de la Spec. Colonnes recopiées des sorties des sessions (passe 2).

| Ligne | État | Mécanisme (endroit du code) | Appelant dans le flux | Test |
|---|---|---|---|---|
| US01 | réalisée | bin/ticket-graph-publish:602 — refuse toute vertical_slice ou repair sans demonstration_line | bin/ticket-graph-publish:2006 — bd-publish applique le contrat avant toute écriture | tests/ticket-graph-publish-entry-contract-test.py |
| US02 | réalisée | bin/ticket-graph-publish:292 — limite les genres à vertical_slice, prefactoring et repair ; bin/ticket-graph-publish:595 refuse l'absence sans appliquer de défaut | bin/ticket-graph-publish:2012 — la publication appelle ce contrôle | tests/ticket-graph-publish-entry-contract-test.py |
| US03 | réalisée | bin/ticket-graph-publish:364 — détecte les mentions de test, fichier et fonction interne ; bin/ticket-graph-publish:710 refuse les critères concernés | bin/ticket-graph-publish:2012 — bd-publish exécute le contrôle d'entrée | tests/ticket-graph-publish-entry-contract-test.py |
| US04 | réalisée | bin/ticket-graph-publish:1027 — calcule la couverture de toutes les stories et refuse chaque orpheline | bin/ticket-graph-publish:2016 — la publication construit le graphe puis appelle graph_refusals | tests/ticket-graph-publish-coverage-test.py |
| US05 | réalisée | bin/ticket-graph-publish:660 — exige une liste non vide de user_stories sur chaque vertical_slice | bin/ticket-graph-publish:2012 — le contrat par ticket est appliqué à la publication | tests/ticket-graph-publish-coverage-test.py |
| US06 | réalisée | bin/ticket-graph-publish:1072 — génère Spec et digest, stories, tickets frères, prototype pertinent et seams ; bin/ticket-graph-publish:2070 les ajoute au texte publié | bin/ticket-graph-publish:2021 — bd-publish fournit ce générateur à graph_plan | tests/ticket-graph-publish-coverage-test.py |
| US07 | partielle | bin/graph-review:402 — fournit les questions fermées par ticket ; bin/graph-review:507 route une session neuve vers le rôle reviewer | docs/PLANNING_RUN.md:75 — le flux prescrit graph-review avant l'approbation ; bin/ticket-graph-publish:2020 ne vérifie ensuite que l'existence du verdict | tests/graph-review-test.py |
| US08 | réalisée | bin/graph-review:217 — expose les refus de seconde passe ; bin/graph-review:357 borne à deux passes ; bin/graph-review:552 enregistre les mots de Benjamin ticket par ticket | docs/PLANNING_RUN.md:77 — le flux fait lancer review, remaining puis decide | tests/graph-review-test.py |
| US09 | partielle | bin/ticket-graph-publish:789 — exige operator_needs et refuse chaque besoin déclaré non levé ; bin/ticket-graph-publish:2510 enregistre sa levée par l'approbateur | bin/ticket-graph-publish:2013 — bd-publish applique le contrôle ; bin/ticket-graph-publish:2396 l'applique aussi aux patches | tests/ticket-graph-publish-coverage-test.py |
| US10 | réalisée | bin/spec-approve:262 — exige des user stories numérotées ; bin/spec-approve:480 exige une référence complète pour les stories [interface] | bin/spec-approve:570 — bd-approve appelle check_entry_contract avant d'écrire l'approbation | tests/spec-approve-test.py |
| US11 | réalisée | bin/ticket-graph-publish:385 — impose entry_point, observable et false_if à chaque critère | bin/ticket-graph-publish:710 — le contrôle parcourt tous les critères de chaque ticket publié | tests/ticket-graph-publish-entry-contract-test.py |
| US12 | réalisée | bin/ticket-graph-publish:2299 — bd-patch réapplique le contrat d'entrée aux tickets du patch et les contrôles au graphe résultant | bin/ticket-graph-publish:2379 — le chemin réel de patch appelle entry_contract_refusals avant toute écriture | tests/ticket-graph-publish-coverage-test.py |
| US13 | réalisée | bin/project-planning-profile:303 — valide la recette, les points d'entrée et les autres déclarations launch du profil | bin/project-launch:189 — lance le projet avec launch.recipe et sa sonde ; bin/tdd-step:432 consomme les points d'entrée | tests/project-planning-profile-test.py |
| US14 | réalisée autrement | bin/spec-approve:561-586 — l’approbation réservée à l’approbateur humain valide le contenu complet de la Spec, contrôle le prototype référencé et gèle son commit dans approved_digest | bin/spec-approve:570-573 — la commande bd-approve appelle le contrat d’entrée avant d’enregistrer l’approbation | tests/spec-approve-test.py:595-640 |
| US15 | partielle | bin/spec-approve:306-359 — contrôle l’inventaire par écran, les statuts prototypé/non prototypé et les six états de contrôle | bin/spec-approve:494-500 — chaque section Validated Prototype est contrôlée pendant bd-approve | tests/spec-approve-test.py:451-491 |
| US16 | partielle | bin/ticket-graph-publish:1072-1120 — construit dans le ticket la référence avec branche, commit, chemin, états et Prototype Fold | bin/ticket-graph-publish:2076 — la publication appelle pointer_sections pour matérialiser les pointeurs du ticket | tests/ticket-graph-publish-prototype-fold-test.py:200-218 |
| US17 | partielle | bin/ticket-graph-publish:932-1017 — exige un unique Prototype Fold vertical_slice et fait attendre les autres tickets d’interface ; bin/prototype-fidelity:402-424 refuse la promotion brute du prototype | bin/ticket-graph-publish:2007-2018 — la porte de publication applique graph_refusals ; bin/convoy-advance:2164-2175 — mesure puis ferme le Fold avant les tickets dépendants | tests/ticket-graph-publish-prototype-fold-test.py:104-189; tests/prototype-fidelity-test.py:307-329 |
| US18 | partielle | bin/prototype-fidelity:541-607 — compare tokens, structure et styles calculés par ancre ; bin/ticket-end:363-380 et bin/spec-end:892-905 — rendent les écarts ouverts bloquants | bin/convoy-advance:2071-2090 — déclenche la fidélité avant fusion ; bin/convoy-advance:2176-2180 — déclenche ensuite la porte de fin de Spec | tests/prototype-fidelity-test.py:233-300; tests/ticket-end-test.py:593-642; tests/spec-end-test.py:759-797 |
| US19 | partielle | lib/convoy_state.py:6374-6396 — enregistre une liste d’écarts sans note et non bloquante ; bin/evidence-capture:643-684 — produit côte à côte et différence ; bin/evidence-pack:551-565 — les présente à Benjamin | bin/convoy-advance:2181-2195 — enchaîne Outcome Evaluation puis Evidence Pack dans le flux réel | tests/outcome-evaluation-test.py:690-713; tests/evidence-pack-test.py:280-303; tests/prototype-fidelity-test.py:333-363 |
| US20 | réalisée | bin/ticket-exit:639-662 — exige que chaque ancre déviante figure dans le Handoff et enregistre la Planning Exception ; bin/ticket-exit:827-835 — écrit le Handoff avant l’exception et l’escalade | formulas/mol-ticket-author.formula.toml:120-130 — ordonne à l’auteur d’utiliser cette sortie et de nommer l’écart sous « Écarts » | tests/ticket-exit-test.py:610-676; tests/prototype-fidelity-test.py:468-518 |
| US21 | réalisée | bin/ticket-author:366 — refuse qu'une session ayant déjà pris un autre ticket soit réutilisée ; bin/ticket-author:423 — crée ou reprend le worktree propre au ticket sur sa branche | formulas/mol-ticket-author.formula.toml:75 — la première étape appelle ticket-author start ; bin/convoy-advance:1818 — démarre cette formule par la porte de dispatch | tests/ticket-author-test.py:325, tests/ticket-author-test.py:363 |
| US22 | réalisée | bin/tdd-step:515 — exige une table complète critère-vers-tests ; bin/tdd-step:662 — refuse toute modification hors du périmètre de test avant le rouge | formulas/mol-ticket-author.formula.toml:165 — ordonne d'écrire tous les tests avant le code puis appelle tdd-step red à la ligne 172 | tests/tdd-step-test.py:351, tests/tdd-step-test.py:393 |
| US23 | réalisée | bin/tdd-step:580 — exécute chaque test de critère contre le commit de départ et exige un rouge recevable ; bin/tdd-step:674 — empreinte table, tests, harnais et configuration lors du gel | formulas/mol-ticket-author.formula.toml:171 — appelle tdd-step red ; formulas/mol-ticket-author.formula.toml:190 — appelle ensuite tdd-step freeze après la revue | tests/tdd-step-test.py:313, tests/tdd-step-test.py:341, tests/tdd-step-test.py:538 |
| US24 | réalisée | bin/test-review:360 — lance chaque relecture dans une session du rôle reviewer par la porte de dispatch ; bin/test-review:626 — ne transmet que les critères, tests et l'unique question définie à la ligne 81 | formulas/mol-ticket-author.formula.toml:180 — impose la relecture avant le gel et appelle test-review review à la ligne 187 ; bin/convoy-advance:2150 — règle les relectures pendantes | tests/test-review-test.py:282, tests/test-review-test.py:552, tests/test-review-test.py:677 |
| US25 | réalisée | bin/tdd-step:787 — exige une raison, refuse un second amendement, rejoue le rouge et calcule le diff ; bin/tdd-step:933 — enregistre l'amendement puis le nouveau rouge et le nouveau gel | formulas/mol-ticket-author.formula.toml:247 — désigne tdd-step amend comme unique chemin | tests/tdd-step-test.py:751, tests/tdd-step-test.py:773 |
| US26 | réalisée | bin/tdd-step:642 — détecte chaque test déjà vert et arrête le ticket avec criterion_already_green ; bin/ticket-exit:586 — fournit la remontée structurée Planning Exception | formulas/mol-ticket-author.formula.toml:176 — indique qu'un vert initial doit sortir immédiatement par planning_exception | tests/tdd-step-test.py:366, tests/ticket-exit-test.py:543 |
| US27 | réalisée | formulas/mol-ticket-author.formula.toml:238 — définit l'intention et la démonstration, non la liste de fichiers, comme limite ; bin/ticket-author:498 — lance le produit et refuse une démonstration non observée | formulas/mol-ticket-author.formula.toml:253 — fait prouver le code après branchement ; formulas/mol-ticket-author.formula.toml:298 — appelle ensuite ticket-author demonstrate | tests/ticket-author-test.py:452, tests/ticket-author-isolated-city-test.sh:406 |
| US28 | partielle | formulas/mol-ticket-author.formula.toml:242 — interdit à l'auteur de changer un comportement fixé par la Spec ou un autre ticket et impose planning_exception ; bin/code-review:794 — la revue reçoit la Spec et le ticket courant | formulas/mol-ticket-author.formula.toml:120 — route ce cas vers ticket-exit planning_exception ; bin/convoy-advance:2153 — lance la revue de code avant fusion | tests/code-review-test.py:405, tests/ticket-exit-test.py:543 |
| US29 | réalisée | bin/ticket-author:498 — lance le produit au HEAD propre, capture la commande ou la capture d'écran et refuse si l'observation échoue ; bin/ticket-author:610 — exige cette preuve au commit de pointe | formulas/mol-ticket-author.formula.toml:292 — demande à l'auteur de voir lui-même la ligne puis appelle demonstrate à la ligne 298 | tests/ticket-author-test.py:452, tests/ticket-exit-test.py:420 |
| US30 | réalisée | bin/ticket-exit:83 — ferme la liste des sorties à finished, planning_exception, operator_request, technically_blocked et interrupted ; bin/ticket-exit:790 — valide et enregistre la sortie structurée | formulas/mol-ticket-author.formula.toml:120 — impose une Ticket Exit à toute interruption du chemin normal ; formulas/mol-ticket-author.formula.toml:325 — termine la séquence par cette sortie | tests/ticket-exit-test.py:842, tests/ticket-exit-test.py:543, tests/ticket-exit-test.py:718, tests/ticket-exit-test.py:755, tests/ticket-exit-test.py:924 |
| US31 | réalisée | bin/ticket-end:300 — contrôle Handoff complet, commit exact et relevés scellés ; bin/spec-integration:500 — refuse de rendre le ticket fusionnable sans Handoff complet à la pointe | bin/spec-integration:729 — appelle la porte ticket-end avant chaque fusion ; bin/convoy-advance:2169 — appelle spec-integration | tests/ticket-end-test.py:471, tests/ticket-end-test.py:657, tests/ticket-exit-test.py:301 |
| US32 | réalisée | bin/ticket-exit:100 — reconnaît TODO, FIXME, not wired et à brancher ; bin/ticket-exit:391 — rapproche chaque marqueur ajouté des chemins déclarés sous not_done et refuse les non appariés | bin/ticket-exit:416 — exécute le détecteur lors de la construction des relevés d'une sortie ; formulas/mol-ticket-author.formula.toml:343 — appelle cette sortie | tests/ticket-exit-test.py:462, tests/ticket-exit-test.py:479 |
| US33 | réalisée | bin/ticket-exit:906 — joint au ticket les Handoffs de ses bloqueurs directs fermés uniquement | formulas/mol-ticket-author.formula.toml:91 — l'étape workspace appelle ticket-exit read avant le travail | tests/ticket-exit-test.py:817, tests/ticket-exit-test.py:833 |
| US34 | réalisée | agents/delivery-author/overlay/.claude/guards/author-subagent-guard:18 — autorise seulement Explore et Plan et bloque tout sous-agent capable d'écrire ; agents/delivery-author/overlay/.claude/settings.json:3 — branche le garde avant Agent, Task et Workflow | bin/dispatch-door:293 — refuse de lancer le rôle auteur sans essai d'adoption valide ; config/role-adoption-trials.json:44 — consigne le refus réel du sous-agent écrivain et le passage du lecteur | tests/author-subagent-guard-test.py:32, tests/author-subagent-guard-test.py:39, tests/author-subagent-guard-test.py:57 |
| US35 | réalisée | bin/tdd-step:817 — choisit le commit avant, interdit de toucher les tests existants et exécute la commande de régression avant puis après | formulas/mol-ticket-author.formula.toml:157 — retire l'étape rouge au prefactoring ; formulas/mol-ticket-author.formula.toml:257 — appelle tdd-step prefactoring | tests/tdd-step-test.py:866, tests/tdd-step-test.py:883 |
| US36 | partielle | agents/delivery-reviewer/agent.toml:1 — rôle relecteur distinct et lecture seule ; config/provider-policy.json:71 — auteur et relecteur utilisent actuellement deux profils du même modèle claude-opus-5-5 | bin/convoy-advance:2153 — déclenche le règlement de la revue avant la fusion | tests/code-review-test.py:460 |
| US37 | partielle | bin/code-review:814 — extrait les relevés en supprimant la prose de l'auteur ; bin/code-review:834 — construit le brief borné ; formulas/mol-code-review.formula.toml:51 — énumère les sources autorisées | bin/code-review:583 — lance la formule mol-code-review depuis le flux de revue | tests/code-review-test.py:557; tests/code-review-test.py:580 |
| US38 | réalisée | lib/convoy_state.py:3776 — démote tout constat bloquant dont la citation Spec, ticket ou règle du dépôt n'est pas valide | bin/code-review:933 — valide puis enregistre la sortie de la revue dans l'état du convoi | tests/code-review-test.py:510 |
| US39 | réalisée | lib/convoy_state.py:3903 — exige une réponse corrigé ou contesté pour chaque Blocking Finding ; lib/convoy_state.py:3868 — exige ensuite le jugement fermé d'une seconde session | bin/correction-round:466 — ouvre le tour d'auteur ; bin/code-review:493 — ouvre la ronde de jugement | tests/correction-round-test.py:399 |
| US40 | réalisée | agents/delivery-evaluator/agent.toml:8 — sélectionne une évaluation neuve ; bin/delivery-role-sandbox:21 — impose la lecture seule ; formulas/mol-ticket-evaluation.formula.toml:63 — impose l'usage du produit lancé | bin/convoy-advance:2156 — déclenche Ticket Evaluation avant fusion | tests/ticket-evaluation-test.py:1108 |
| US41 | réalisée | lib/convoy_state.py:4051 — valide un état et une preuve pour chaque critère ; lib/convoy_state.py:4093 — refuse un verdict fourni par l'Evaluator et calcule le résultat | bin/ticket-evaluation:944 — enregistre la sortie structurée de l'Evaluator | tests/ticket-evaluation-test.py:636; tests/ticket-evaluation-test.py:717 |
| US42 | réalisée | bin/project-launch:180 — crée un worktree détaché propre, choisit un port libre et injecte le jeu de données synthétiques nommé | bin/ticket-evaluation:455 — lance un produit propre pour chaque environnement déclaré puis l'arrête après évaluation | tests/ticket-evaluation-test.py:508; tests/ticket-evaluation-test.py:530; tests/ticket-evaluation-test.py:553 |
| US43 | réalisée | bin/convoy-advance:2148 — lance revue et Ticket Evaluation dans la même passe ; bin/correction-round:547 — agrège leurs refus dans un seul brief d'auteur | bin/convoy-advance:2161 — règle ensuite un unique tour de correction | tests/convoy-advance-test.py:1246 |
| US44 | réalisée | bin/correction-round:423 — arrête le ticket encore refusé et construit un seul élément opérateur ; bin/correction-round:466 — interdit un second tour | bin/convoy-advance:2052 — applique le règlement du tour de correction avant toute fusion | tests/convoy-advance-test.py:1268; tests/correction-round-test.py:672 |
| US45 | réalisée | lib/convoy_state.py:4778 — enregistre les mots de Benjamin pour une dérogation de revue et refuse toute dérogation de critère ; bin/correction-round:610 — expose la commande contrôlée | bin/spec-integration:442 — ne reconnaît l'override que pour les Blocking Findings de revue | tests/correction-round-test.py:737; tests/correction-round-test.py:790 |
| US46 | réalisée | bin/code-review:629 — traite l'absence de résultat comme une revue non passée ; bin/code-review:720 — autorise une relance puis arrête le ticket | bin/convoy-advance:2010 — règle les demandes de revue et propage leur arrêt | tests/convoy-advance-test.py:1138 |
| US47 | réalisée | bin/spec-integration:701 — sérialise les fusions par verrou de convoi ; bin/spec-integration:612 — capture les tests sur le commit fusionné avant de déplacer la branche d’intégration | bin/convoy-advance:2169 — la passe appelle merge_finished, qui lance bin/spec-integration merge avec une limite d’un ticket | tests/convoy-advance-test.py:907 |
| US48 | réalisée | formulas/mol-ticket-resume.formula.toml:83 — la reprise « returned » impose à l’auteur de fusionner origin/$INTEGRATION dans sa branche, résoudre ou corriger, puis committer | bin/convoy-advance:914 — détecte le retour de fusion ; bin/convoy-advance:925 — route une session neuve d’auteur avec la formule de reprise | tests/spec-integration-test.py:703 ; tests/convoy-advance-test.py:1722 |
| US49 | réalisée | bin/evidence-capture:503 — scelle la pièce, la range et écrit son empreinte et son commit dans le tracker ; bin/evidence-capture:691 — refuse toute pièce non scellée ou incohérente | bin/ticket-end:210 — vérifie le magasin par bin/evidence-capture verify ; bin/ticket-end:419 — la condition 7 refuse l’ensemble si une pièce n’est pas recevable | tests/evidence-capture-test.py:510 |
| US50 | réalisée | bin/spec-integration:512 — invalide les verdicts devenus antérieurs à la pointe ; lib/convoy_state.py:4657 — inscrit l’invalidation et compte la reprise | bin/spec-integration:721 — contrôle chaque ticket avant fusion et appelle invalidate lorsqu’un verdict est périmé ; bin/convoy-advance:2169 — lance cette fusion | tests/spec-integration-test.py:626 |
| US51 | réalisée | bin/ticket-end:62 — définit la liste fermée ticket-end/v1 de neuf conditions ; lib/convoy_state.py:3386 — ferme atomiquement seulement avec cette version et neuf verdicts passants | bin/convoy-advance:2173 — appelle bin/ticket-end settle après la fusion | tests/convoy-advance-test.py:979 ; tests/ticket-end-test.py:537 |
| US52 | réalisée | bin/convoy-advance:1006 — compte la reprise et parque le ticket à la troisième ; lib/convoy_state.py:4465 — parque aussi ses descendants ; bin/convoy-advance:1088 — construit la demande groupée | bin/convoy-advance:1869 — règle les reprises ; bin/convoy-advance:1905 — émet la demande opérateur lorsque seuls des tickets parqués subsistent | tests/convoy-advance-test.py:1738 ; tests/convoy-advance-test.py:1790 |
| US53 | partielle | bin/convoy-advance:1839 — sous intégration rouge, seul le repair peut démarrer ou reprendre ; bin/convoy-advance:1863 — avec deux Planning Exceptions, seuls les nouveaux démarrages sont retenus | bin/convoy-advance:2128 — advance_convoy est exécuté pour chaque convoi à chaque passe | tests/convoy-advance-test.py:1940 ; tests/convoy-advance-test.py:2061 |
| US54 | réalisée | bin/convoy-advance:1074 — détecte qu’il ne reste que des origines parquées ; bin/convoy-advance:1139 — enregistre et envoie une seule demande groupée idempotente | bin/convoy-advance:1905 — appelle settle_grouped_request après les démarrages, reprises et parcages | tests/convoy-advance-test.py:1790 |
| US55 | réalisée | lib/convoy_state.py:3232 — le marquage du nouveau flux ajoute le label Gas City « owned », puis lib/convoy_state.py:5568 ferme uniquement sur réponse humaine enregistrée | bin/ticket-graph-publish:2036 — la publication marque le convoi ; bin/convoy-advance:2140 suit ensuite l’acceptation ou l’abandon | tests/convoy-manual-lifecycle-isolated-city-test.sh:236 |
| US56 | réalisée | bin/spec-end:658 — invalide tous les verdicts si leur commit n’est plus l’unique pointe d’intégration ou ne contient plus la pointe protégée | bin/convoy-advance:2178 — lance la porte lorsque tous les tickets sont fermés | tests/spec-end-test.py:512 |
| US57 | réalisée | bin/outcome-evaluation:742 — fournit toutes les stories numérotées et les produits assemblés lancés ; lib/convoy_state.py:6469 exige un état pour chacune | bin/convoy-advance:2183 — déclenche le règlement de l’Outcome Evaluation après les verdicts mécaniques | tests/outcome-evaluation-test.py:281 |
| US58 | réalisée | bin/spec-end-review:365 — calcule tout le diff entre la branche protégée et le commit assemblé et en impose la couverture complète | bin/convoy-advance:2188 — déclenche la revue de fin sur le commit de la porte | tests/spec-end-review-test.py:186 |
| US59 | réalisée | lib/convoy_state.py:1554 — calcule « ouvert », « réparé » ou « accepté par Benjamin » pour chaque écart et non fait ; bin/spec-end:318 refuse tout état non final | bin/convoy-advance:2178 — fait lire ce registre par la porte de fin de Spec | tests/spec-end-test.py:607; tests/spec-end-test.py:655 |
| US60 | réalisée | lib/convoy_state.py:2214 — calcule l’état final des constats hors ticket ; lib/convoy_state.py:6343 limite leur classement à repaired, proposal ou dismissed et exige une raison pour dismissed | bin/outcome-evaluation:841 — expose la commande de classement à l’Evaluator de fin, appelée dans le flux par bin/convoy-advance:2183 | tests/outcome-evaluation-test.py:566; tests/outcome-evaluation-test.py:589; tests/outcome-evaluation-test.py:596 |
| US61 | réalisée | lib/convoy_state.py:5857 — compte un unique compteur de tours pour les rouges mécaniques, l’Outcome Evaluation et la revue de fin ; config/delivery-flow.json:8 fixe la borne à 2 | bin/convoy-advance:2183 — traite les sources de refus puis bin/convoy-advance:2200 émet la demande non conforme à l’arrêt | tests/convoy-stops-fixture-city-test.py:997 |
| US62 | réalisée | bin/evidence-pack:1038 — assemble déterministement la page depuis l’état et les pièces enregistrées ; bin/evidence-pack:569 rend obligatoire la rubrique « Ce qui n’a PAS été vérifié » | bin/convoy-advance:1725 — appelle la génération par code lorsque les six conditions précédentes sont vertes | tests/evidence-pack-test.py:209; tests/evidence-pack-test.py:221; tests/evidence-pack-test.py:245 |
| US63 | réalisée | lib/convoy_state.py:6399 — calcule les contradictions entre une story non observée en fin et les évaluations favorables de tous ses tickets couvrants ; bin/evidence-pack:883 les inscrit au dossier | bin/outcome-evaluation:880 — enregistre l’évaluation via la commande d’état, elle-même déclenchée par bin/convoy-advance:2183 | tests/outcome-evaluation-test.py:459; tests/evidence-pack-test.py:351 |
| US64 | réalisée | bin/convoy-advance:1350-1366,1408-1418 — construit l’Acceptance Request avec le lien du dossier, l’envoie par escalation-door et enregistre son émission | bin/convoy-advance:2204-2209 — la passe réelle règle l’acceptation après le Delivered Outcome | tests/convoy-stops-fixture-city-test.py:1168 |
| US65 | réalisée | bin/acceptance-session:269-298,339-367,373-417 — vérifie le dossier à jour puis lance, par code, chaque jeu synthétique depuis une copie du commit du dossier | docs/ACCEPTANCE_SESSION.md:121-130 — le protocole opérateur du flux fait exécuter acceptance-session open puis close | tests/acceptance-session-test.py:204 |
| US66 | partielle | bin/acceptance-session:77-83,409-414 — remet à la session des règles interdisant résumé et recommandation | docs/ACCEPTANCE_SESSION.md:121-130 — la session opérateur reçoit ces règles en exécutant open | tests/acceptance-session-real-session-test.sh:1 |
| US67 | réalisée | bin/owner-answer:425-474 — accepte exactement accepté, constats rendus ou abandonné et enregistre la réponse; lib/convoy_state.py:5420-5511 — lie la réponse au commit et à l’empreinte du dossier | docs/ACCEPTANCE_SESSION.md:124-129 — la session d’acceptation doit exécuter owner-answer avec les valeurs rendues par open | tests/owner-answer-test.py:139,263,499 |
| US68 | réalisée | lib/convoy_state.py:5465-5477 — refuse accepté lorsqu’une proposition manque de verdict ou porte le verdict à faire avant d’accepter | bin/owner-answer:396-422,425-474 — les commandes verdict et record sont l’interface d’acceptation documentée | tests/owner-answer-test.py:130,246 |
| US69 | partielle | lib/convoy_state.py:5379-5417 — calcule une route repair, planning_exception ou later à partir du drapeau later et de la citation | bin/owner-answer:425-459 — transmet les constats à record-owner-answer; bin/convoy-advance:1428-1450 — publie ensuite repairs et propositions | tests/owner-answer-test.py:263 |
| US70 | réalisée | lib/convoy_state.py:5504-5507 — retire Delivered, efface le tour final et remet le compteur à zéro; bin/convoy-advance:2172-2209 — refait porte de ticket, fin de Spec, évaluations et dossier | orders/convoy-advance.toml:63-64 — l’ordre périodique exécute la passe complète | tests/convoy-stops-fixture-city-test.py:1346 |
| US71 | réalisée | bin/convoy-advance:1394-1456 — un Delivered Outcome reste en attente sans lecture d’horloge; bin/outcome-promote:423-436 — refuse toute fusion ou fermeture sans réponse finale | orders/convoy-advance.toml:63-64 — les passes périodiques ne produisent aucune réponse à la place de Benjamin | tests/convoy-stops-fixture-city-test.py:1184 |
| US72 | réalisée | bin/outcome-promote:440-496 — exige un accepté, reprend la branche protégée si nécessaire, rejoue les contrôles mécaniques et ne fusionne qu’après leur succès | bin/convoy-advance:1462-1496,2137-2143 — la passe appelle outcome-promote avant toute autre suite après la réponse | tests/outcome-promote-test.py:107,161,178 |
| US73 | réalisée | bin/owner-answer:222-231 — refuse toute nouvelle réponse sur un Outcome fermé; lib/convoy_state.py:5310-5316,5568-5601 — interdit la réouverture et ferme atomiquement après promotion | bin/convoy-advance:1835-1838 — une passe rencontrant le convoi fermé le rend tel quel sans le rouvrir | tests/outcome-promote-test.py:265,276 |
| US74 | réalisée | bin/upstream-skills-check:69-82,91-145 — lit le pin unique, récupère le tag et compare récursivement les octets de skills/ | .github/workflows/ci.yml:142-163 — la CI découvre et exécute automatiquement le test qui appelle compare | tests/upstream-skills-check-compare-test.sh:42-119 |
| US75 | réalisée | config/delivery-roles.json:6-24; bin/role-adoption-trial:201-224,515-558 — définit la distribution minimale de chaque rôle et vérifie les skills chargés et lancés | bin/dispatch-door:293-301 — refuse le dispatch d'un rôle si l'essai de sa distribution courante ne passe pas | tests/dispatch-door-role-test.sh:134-184 |
| US76 | réalisée | bin/role-adoption-trial:134-146,182-195 — lie un essai réussi au rôle, au fournisseur et à l'empreinte complète de sa distribution | bin/dispatch-door:293-301 — résout le fournisseur effectif puis exige l'essai correspondant avant tout dispatch | tests/dispatch-door-role-test.sh:116-142 |
| US77 | réalisée | bin/method-check:77-115 — exige pour chaque ligne une exigence, un mécanisme nommant une commande exécutable et une preuve | .github/workflows/ci.yml:142-163 — exécute automatiquement le test enregistré sur chaque lot de CI | tests/method-check-test.py:189-249 |
| US78 | réalisée | bin/method-check:145-184 — exige une entrée AR existante, une raison dans son champ But et la baseline v1.3.1 pour chaque écart déclaré | .github/workflows/ci.yml:142-163 — exécute automatiquement le contrôle par son test enregistré | tests/method-check-test.py:42-117,259-307 |
| US79 | réalisée | bin/tdd-step:734-784; bin/spec-integration:612-658 — lit le profil du projet pour lancer ses tests gelés puis sa régression sur le résultat fusionné, sans branchement par langage | bin/convoy-advance:2148-2175 — enchaîne revue, évaluation, fusion et porte de fin pour les tickets du profil | tests/second-project-isolated-city-test.sh:548-629 |
| US80 | absente | tests/ticket-graph-publish-new-flow-real-tracker-test.sh:165-180 — la seule prise en charge du brouillon Cockpit V2 vérifie au contraire que sa publication est refusée | aucun | tests/ticket-graph-publish-new-flow-real-tracker-test.sh:165-180 |
| US81 | partielle | bin/fixture-city-oracle:7-22,52-69 — observe un flux assemblé jusqu'à la fermeture, au Delivered Outcome puis à l'acceptation ou l'abandon | aucun | tests/fixture-city-oracle-test.py:335-360 |
| US82 | réalisée | bin/convoy-advance:2112-2130,1825-1901 — calcule les places libres, ignore les tickets bloqués et démarre les tickets prêts via dispatch-door sous le plafond N | orders/convoy-advance.toml:59-64 — l'ordre périodique exécute convoy-advance --all | tests/convoy-advance-isolated-city-test.sh:11-28 |
| US83 | réalisée | bin/convoy-advance:774-845,1825-1834 — crée et escalade un incident unique puis retourne avant tout nouveau démarrage tant qu'un état sans règle demeure | orders/convoy-advance.toml:59-64 — chaque passe de l'ordre traite les anomalies des convois marqués | tests/convoy-advance-test.py:464-538 |
| US84 | partielle | bin/dispatch-door:320-330; agents/mayor/prompt.template.md:79-119 — interdit au Mayor de démarrer un ticket marqué et lui ordonne de ne pas modifier le graphe | orders/convoy-advance.toml:59-64 — le véritable avancement appartient à l'ordre, tandis que dispatch-door filtre les demandes des sessions d'agent | tests/convoy-stop-mayor-isolated-city-test.sh:334-370 |
| D0.1 | réalisée | bin/convoy-advance:2112-2209 — le code choisit les démarrages, règle revues et évaluations, fusionne, calcule les portes de fin et route les arrêts | orders/convoy-advance.toml:59-64 — l'ordre du contrôleur lance toute la passe | tests/convoy-stops-fixture-city-test.py:690-810 |
| D0.2 | réalisée | lib/convoy_state.py:2-41; agents/delivery-author/agent.toml:12-20 — conserve l'état gc.flow dans le tracker et limite chaque session au workflow durable qui lui est routé | bin/convoy-advance:2115-2130,2148-2197 — recharge l'état durable à chaque passe et lance les rôles par les portes prévues | tests/fresh-sessions-isolated-city-test.sh:415-479 |
| D0.3 | réalisée | bin/convoy-advance:1825-1901,2112-2209; bin/dispatch-door:320-330 — le contrôleur avance seul le graphe et refuse les démarrages demandés par une session d'agent | orders/convoy-advance.toml:59-64 — l'ordre périodique remplace le Mayor dans la boucle d'avancement | tests/convoy-stop-mayor-isolated-city-test.sh:334-370 |
| D0.4 | réalisée | formulas/mol-ticket-author.formula.toml:61-70,133-139,211-217,317-323,358-364; assets/scripts/checks/ticket-author-check.sh:1-17 — la formule impose la séquence et Gas City exécute un contrôle scripté à chaque étape | bin/convoy-advance:1818-1822 — démarre le ticket sur la formule mol-ticket-author via dispatch-door | tests/ticket-author-isolated-city-test.sh:12-23 |
| D0.5 | réalisée | bin/convoy-advance:774-845,1825-1834 — enregistre l'anomalie, l'envoie par escalation-door, arrête les démarrages puis retire l'incident après retour à un état valide | orders/convoy-advance.toml:59-64 — la passe périodique détecte l'état inconnu et reprend seule après réparation | tests/convoy-advance-test.py:466-538 |
| D0.6 | réalisée | bin/outcome-evaluation:803-826,862-946; lib/convoy_state.py:6324-6359; bin/tdd-step:734-784; bin/spec-integration:612-658 — valide les preuves et citations, calcule le verdict et rejoue les tests gelés au vert puis après fusion | bin/convoy-advance:2148-2197 — règle revues, évaluations, fusion, Outcome Evaluation et portes de fin dans la passe réelle | tests/outcome-evaluation-test.py:457-574 |
| D0.7 | réalisée | config/delivery-roles.json:6-24; bin/ticket-exit:100-106,391-413,459-463 — ne définit aucun rôle propriétaire et limite volontairement le détecteur de report aux marqueurs ajoutés | formulas/mol-ticket-author.formula.toml:325-355 — la sortie réelle du ticket appelle ticket-exit, qui applique ce filet | tests/ticket-exit-test.py:453-523 |
| D1.1 | réalisée | bin/upstream-skills-check:55-82,91-145 — lit l'unique baseline v1.3.1/24fe0ef et compare toute la copie vendored au tag | .github/workflows/ci.yml:142-163 — la CI découvre le test qui exécute la comparaison réelle | tests/upstream-skills-check-compare-test.sh:42-119 |
| D1.2 | réalisée | bin/role-adoption-trial:198-227; formulas/mol-ticket-author.formula.toml:165-173,235-236; formulas/mol-code-review.formula.toml:63-76 — vérifie les copies simples inchangées et fait appeler ou lire les skills par les étapes | bin/convoy-advance:1818-1822,2148-2158 — route les formules d'auteur, de relecture et d'évaluation du flux | tests/dispatch-door-role-test.sh:214-222 |
| D1.3 | partielle | formulas/mol-ticket-author.formula.toml:235-236; agents/delivery-author/prompt.template.md:3-7 — la formule et le prompt font lire implement intact | bin/convoy-advance:1818-1822 — démarre l'auteur sur cette formule | tests/upstream-skills-check-compare-test.sh:95-108 |
| D1.4 | réalisée | config/delivery-roles.json:6-24; bin/role-adoption-trial:201-224 — fixe et vérifie exactement les skills et lectures de l'auteur, du relecteur et de l'Evaluator | bin/dispatch-door:293-301 — impose la distribution essayée avant de lancer chaque rôle | tests/dispatch-door-role-test.sh:134-184,214-222 |
| D1.5 | réalisée | bin/role-adoption-trial:515-558 — exige une seule occurrence de code-review et compare l'empreinte du fichier effectivement chargé à la copie vendored | bin/dispatch-door:293-301 — refuse le rôle si l'essai de masquage ne tient plus pour sa distribution courante | tests/dispatch-door-role-test.sh:144-184 |
| D1.6 | partielle | GLOSSARY.md:1-3; tests/upstream-skills-check-compare-test.sh:91-93 — le glossaire de l'usine porte le nouveau nom et le contrôle exige la disparition de resolving-merge-conflicts | .github/workflows/ci.yml:142-163 — la CI exécute le contrôle de disparition de la skill | tests/upstream-skills-check-compare-test.sh:91-93 |
| D1.7 | réalisée | bin/upstream-skills-check:72-145; bin/role-adoption-trial:182-227,515-558 — contrôle l'identité au tag, le chargement par fournisseur, le masquage et les skills de revue lancées | .github/workflows/ci.yml:142-163; bin/dispatch-door:293-301 — la CI compare l'upstream et la porte impose l'essai courant avant dispatch | tests/upstream-skills-check-compare-test.sh:42-119; tests/dispatch-door-role-test.sh:116-184 |
| D2.1 | réalisée | bin/ticket-graph-publish:292 — énumère exactement les trois genres ; bin/ticket-graph-publish:595 applique leurs obligations sans défaut | bin/ticket-graph-publish:2012 — la publication new-flow appelle ce contrôle | tests/ticket-graph-publish-entry-contract-test.py |
| D2.2 | réalisée | bin/ticket-graph-publish:630 — valide restores et sa citation ; bin/ticket-graph-publish:2162 autorise sans approbation seulement l'ajout d'un repair ; bin/convoy-advance:1265 publie les repairs produits ou rédigés par le flux | bin/convoy-advance:1839 — une branche rouge déclenche son repair ; bin/ticket-exit:848 publie celui d'un blocage technique ; bin/convoy-advance:1560 et bin/convoy-advance:1644 publient ceux de l'Evaluator et du relecteur de fin | tests/ticket-graph-publish-new-flow-real-tracker-test.sh ; tests/convoy-stops-fixture-city-test.py |
| D2.3 | réalisée | bin/ticket-graph-publish:602 — traite demonstration_line comme champ distinct ; bin/graph-review:81 contrôle qu'elle est démontrable seule par le vrai point d'entrée | bin/ticket-author:498 — l'auteur lance le produit et capture la démonstration ; formulas/mol-graph-review.formula.toml:57 fait juger son observabilité | tests/ticket-author-test.py |
| D2.4 | réalisée | bin/ticket-graph-publish:385 — impose les trois champs publics et refuse les mentions internes ; bin/ticket-graph-publish:1902 lie le brouillon entier à son digest approuvé | bin/ticket-graph-publish:2012 — bd-publish applique les contrôles ; bin/ticket-graph-publish:2391 empêche aussi un patch de modifier les champs gelés | tests/ticket-graph-publish-entry-contract-test.py |
| D2.5 | réalisée | bin/ticket-graph-publish:1072 — construit tous les pointeurs à partir de la Spec, du graphe et du profil ; bin/ticket-graph-publish:2075 les rend dans le ticket | bin/ticket-graph-publish:2021 — la publication branche ce rendu dans graph_plan ; bin/ticket-graph-publish:2432 le recalcule après patch | tests/ticket-graph-publish-coverage-test.py |
| D2.6 | réalisée | bin/ticket-graph-publish:1027 — refuse les stories orphelines | bin/ticket-graph-publish:2400 — bd-patch reconstitue le graphe complet résultant puis rappelle graph_refusals à bin/ticket-graph-publish:2413 | tests/ticket-graph-publish-coverage-test.py |
| D2.7 | réalisée | bin/ticket-graph-publish:112 — rend scope.paths facultatif ; bin/ticket-graph-publish:213 sérialise les recouvrements ; bin/graph-review:176 ajoute le contrôle des fichiers de branchement seulement quand un scope existe | bin/ticket-graph-publish:2023 — la publication ajoute les arêtes ; formulas/mol-ticket-author.formula.toml:238 dit à l'auteur que le scope ne borne pas ses modifications | tests/ticket-graph-publish-coverage-test.py |
| D2.8 | réalisée | bin/graph-review:88 — impose le contrôle assembly_point_not_confiscated ; formulas/mol-graph-review.formula.toml:82 définit qu'un ticket établissant un point partagé doit être ordonné en premier | docs/PLANNING_RUN.md:75 — la session /to-tickets fait lancer graph-review ; bin/ticket-graph-publish:2020 refuse sans verdict valable | tests/graph-review-test.py |
| D2.9 | partielle | bin/ticket-graph-publish:789 — rend operator_needs obligatoire et refuse tout besoin déclaré qui n'est pas levé | bin/ticket-graph-publish:2013 — publication initiale ; bin/ticket-graph-publish:2396 — publication par patch | tests/ticket-graph-publish-coverage-test.py |
| D2.10 | partielle | bin/ticket-graph-publish:1039 — refuse un projet sans launch sauf si une première vertical_slice déclare establishes_launch_recipe ; bin/project-planning-profile:303 valide ensuite le bloc launch | bin/ticket-graph-publish:2010 — la publication lit le profil ; formulas/mol-ticket-author.formula.toml:172 lance toutefois tdd-step red avec ce même profil dès la première tranche | tests/ticket-graph-publish-coverage-test.py |
| D2.11 | réalisée | bin/spec-approve:262 — lit les stories numérotées ; bin/spec-approve:284 valide la référence ; bin/spec-approve:425 vérifie branche, commit distant, chemin et conformité | bin/spec-approve:570 — bd-approve appelle l'ensemble avant d'enregistrer le digest | tests/spec-approve-test.py |
| D2.12 | partielle | bin/graph-review:357 — ouvre au plus deux passes liées au digest et mémorise auteur et relecteur ; bin/graph-review:402 impose les verdicts fermés par ticket et sur le graphe | docs/PLANNING_RUN.md:75 — le flux demande la revue ; bin/ticket-graph-publish:2020 appelle sa porte check | tests/graph-review-test.py |
| D2.13 | réalisée | bin/ticket-graph-publish:301 — maintient une liste fermée de champs et refuse les inconnus ; bin/ticket-graph-publish:1160 rend le ticket sans contrat d'exécution recopié | bin/ticket-graph-publish:2012 — contrôle avant publication ; bin/ticket-graph-publish:2021 — rendu du ticket publié | tests/ticket-graph-publish-entry-contract-test.py |
| D3.1 | réalisée autrement | bin/prototype-conformance:147-264 — impose variante unique, absence de barre, états adressables, encodage, viewports et thèmes ; bin/prototype-conformance:441-469 — impose une branche prototype jamais fusionnée | bin/spec-approve:425-476 — extrait le commit distant puis appelle prototype-conformance avant l’approbation humaine de bin/spec-approve:561-586 | tests/prototype-conformance-test.py:57-70; tests/prototype-conformance-test.py:127-168; tests/prototype-conformance-test.py:269-298 |
| D3.2 | réalisée | bin/spec-approve:284-303 — exige branche, commit complet, chemin et liste des états ; bin/spec-approve:575-583 — gèle le contenu dans approved_digest | bin/spec-approve:494-500 — lit et contrôle chaque référence pendant bd-approve | tests/spec-approve-test.py:419-450; tests/spec-approve-test.py:627-640 |
| D3.3 | réalisée | bin/spec-approve:306-359 — vérifie chaque écran, les statuts prototypé/non prototypé et les six états présents ou sans objet avec raison | bin/spec-approve:494-496 — applique le contrôle à chaque prototype référencé | tests/spec-approve-test.py:451-491 |
| D3.4 | partielle | bin/prototype-conformance:267-385 — exige que tout élément visible soit couvert et que certaines régions HTML aient leur propre ancre ; bin/prototype-fidelity:541-566 — compare les noms et rend une ancre livrée absente déviante | bin/spec-approve:457-476 — contrôle le prototype ; bin/convoy-advance:2071-2090 — contrôle ensuite le livré avant fusion | tests/prototype-conformance-test.py:73-82; tests/prototype-conformance-test.py:181-229; tests/prototype-fidelity-test.py:233-243 |
| D3.5 | réalisée | bin/prototype-conformance:388-421 — exige un JSON distinct par état avec heure ISO fixée ; bin/project-planning-profile:368-445 — exige les datasets de lancement et rattache chaque état d’écran à l’un d’eux | bin/spec-approve:457-476 — contrôle les fichiers ; bin/prototype-fidelity:677-723 — charge le profil et lance le produit sur chaque état sélectionné | tests/prototype-conformance-test.py:108-125; tests/project-planning-profile-test.py:260-282; tests/prototype-fidelity-test.py:196-229 |
| D3.6 | partielle | bin/prototype-conformance:61-61 — définit les six propriétés ; bin/prototype-conformance:531-560 — les exécute toutes | bin/spec-approve:457-476 — spec-approve appelle bien le contrôle ; aucun appelant du flux de session prototype avant présentation | tests/prototype-conformance-test.py:57-310; tests/spec-approve-test.py:478-503 |
| D3.7 | partielle | bin/ticket-graph-publish:932-1017 — impose un Fold vertical_slice unique et les dépendances ; bin/prototype-fidelity:677-739 — sert et compare tous les états ; bin/prototype-fidelity:402-424 — refuse les fichiers promus tels quels | bin/ticket-graph-publish:2007-2018 — applique la porte du graphe ; bin/convoy-advance:2164-2175 — mesure le Fold avant fusion et fermeture | tests/ticket-graph-publish-prototype-fold-test.py:104-189; tests/prototype-fidelity-test.py:196-229; tests/prototype-fidelity-test.py:307-329 |
| D3.8 | partielle | bin/prototype-fidelity:450-472 et bin/prototype-fidelity:541-607 — compare tokens, structure et styles ; bin/evidence-capture:643-684 — capture les deux côtés au même instant sans seuil ; lib/convoy_state.py:6374-6396 — limite la liste d’agent à text et evidence | bin/convoy-advance:2164-2185 — déclenche fidélité puis Evaluator ; bin/evidence-pack:551-565 — assemble les écarts et comparaisons | tests/prototype-fidelity-test.py:196-280; tests/prototype-fidelity-test.py:333-383; tests/outcome-evaluation-test.py:690-713 |
| D3.9 | réalisée | bin/ticket-exit:586-627 — transforme la contradiction en Planning Exception adressée à l’opérateur ; bin/ticket-exit:639-662 — exige préalablement l’écart dans le Handoff | formulas/mol-ticket-author.formula.toml:120-130 — prescrit Planning Exception pour une contradiction avec la Spec et --anchor pour un écart au prototype | tests/ticket-exit-test.py:568-590; tests/ticket-exit-test.py:610-676 |
| D3.10 | réalisée | skills/engineering/prototype/SKILL.md:10-17 — dirige les questions de logique vers LOGIC.md ; skills/engineering/prototype/LOGIC.md:1-67 — contient le processus Matt du prototype de logique ; bin/ticket-end:363-365 — déclare la fidélité sans objet sans référence d’interface | skills/engineering/wayfinder/SKILL.md:73-80 — le ticket Prototype appelle le skill prototype | tests/upstream-skills-check-compare-test.sh:95-108; tests/ticket-end-test.py:647-653 |
| D3.11 | réalisée | bin/outcome-promote:423-496 — après la réponse acceptée, promeut puis ferme le convoi ; bin/convoy-advance:1835-1838 — un convoi fermé n’est plus repris | bin/convoy-advance:2137-2143 — traite la promotion avant toute autre étape et interrompt la passe | tests/outcome-promote-test.py:107-159 |
| D4.1 | réalisée | bin/ticket-graph-publish:2037 — ouvre une branche d'intégration par Spec ; bin/outcome-promote:430 — exige une réponse accepted puis crée une unique fusion vers la branche protégée aux lignes 487-494 | bin/convoy-advance:1462 — appelle outcome-promote après la réponse de Benjamin ; orders/convoy-advance.toml:59 — exécute convoy-advance périodiquement | tests/spec-integration-test.py:415, tests/outcome-promote-test.py:107 |
| D4.2 | réalisée | bin/ticket-author:423 — attribue session et worktree par ticket ; bin/convoy-advance:669 — lit toutes les sessions vivantes de l'usine et bin/convoy-advance:684 compte auteurs, reviewers et evaluators sous le même plafond | bin/convoy-advance:2112 — calcule globalement les places libres avant d'avancer tous les convois ; config/delivery-flow.json:4 — fixe N à 2 | tests/convoy-advance-test.py:248, tests/convoy-advance-test.py:276, tests/convoy-advance-test.py:286, tests/convoy-advance-test.py:340 |
| D4.3 | réalisée | bin/ticket-graph-publish:125 — valide les bloqueurs et refuse les cycles ; bin/ticket-graph-publish:213 — ajoute déterministement une arête quand deux Declared Scopes non ordonnés se recouvrent | bin/ticket-graph-publish:2023 — applique ces arêtes avant la publication du graphe ; bin/convoy-advance:1887 — ne démarre ensuite que les tickets sans bloqueur ouvert | tests/ticket-graph-publish-coverage-test.py:594, tests/ticket-graph-publish-coverage-test.py:1113 |
| D4.4 | réalisée | bin/spec-integration:567 — reprend et teste la branche protégée ; bin/spec-integration:612 — capture les tests du résultat fusionné ; bin/spec-integration:626 — retourne conflits et rouges à l'auteur du ticket courant ; bin/spec-end:872 — refait la reprise avant la vérification finale | bin/convoy-advance:1925 — appelle spec-integration avec une limite d'un ticket par passe ; bin/convoy-advance:2169 — place cette fusion dans le flux réel | tests/spec-integration-test.py:393, tests/spec-integration-test.py:703, tests/spec-integration-test.py:765, tests/spec-integration-test.py:821, tests/spec-end-test.py:512 |
| D4.5 | réalisée | bin/convoy-advance:1825 — parcourt le graphe, filtre parcages, plafond et bloqueurs, puis démarre les tickets prêts ; bin/dispatch-door:320 — refuse tout démarrage du nouveau flux demandé par une session d'agent | orders/convoy-advance.toml:59 — l'ordre conditionnel exécute convoy-advance --all --stopped-ok chaque minute | tests/convoy-advance-test.py:350, tests/convoy-advance-test.py:676, tests/convoy-advance-test.py:682 |
| D5.1 | partielle | formulas/mol-ticket-author.formula.toml:238 — pose l'intention comme limite, exige le branchement et classe Planning Exception, défaut bloquant et constat hors ticket ; bin/ticket-exit:790 — réalise les sorties et destinations correspondantes | formulas/mol-ticket-author.formula.toml:120 — impose ces sorties dans la séquence auteur ; bin/convoy-advance:1818 — démarre cette formule | tests/ticket-author-isolated-city-test.sh:406, tests/ticket-exit-test.py:543, tests/ticket-exit-test.py:924 |
| D5.2 | réalisée | bin/tdd-step:515 — impose la table complète ; bin/tdd-step:580 — lance le produit de départ et vérifie chaque rouge ; bin/tdd-step:662 — borne le diff au périmètre de test ; bin/tdd-step:884 — capture la preuve | formulas/mol-ticket-author.formula.toml:165 — fait écrire tous les tests avant le code et appelle tdd-step red à la ligne 172 | tests/tdd-step-test.py:313, tests/tdd-step-test.py:351, tests/tdd-step-test.py:393, tests/tdd-step-test.py:400, tests/tdd-step-test.py:437 |
| D5.3 | réalisée | bin/test-review:81 — fixe l'unique question ; bin/test-review:360 — lance une nouvelle session reviewer ; bin/test-review:533 — autorise un retour puis bin/test-review:478 arrête après le second échec | formulas/mol-ticket-author.formula.toml:180 — appelle la revue avant le gel ; bin/convoy-advance:2150 — règle les sessions pendantes | tests/test-review-test.py:324, tests/test-review-test.py:353, tests/test-review-test.py:552, tests/test-review-test.py:754 |
| D5.4 | réalisée | bin/tdd-step:674 — gèle table, tests et frozen_harness_paths dans le magasin extérieur ; bin/tdd-step:734 — recharge ce registre, refuse tout changement et exécute les mêmes identifiants k fois sans skip | formulas/mol-ticket-author.formula.toml:190 — appelle freeze après revue ; formulas/mol-ticket-author.formula.toml:255 — appelle green | tests/tdd-step-test.py:538, tests/tdd-step-test.py:622, tests/tdd-step-test.py:636, tests/tdd-step-test.py:665, tests/tdd-step-test.py:680 |
| D5.5 | réalisée | bin/tdd-step:787 — valide raison, borne unique, nouveau rouge et diff ; bin/tdd-step:933 — enregistre l'écart puis regèle automatiquement | formulas/mol-ticket-author.formula.toml:247 — rend tdd-step amend seul chemin autorisé | tests/tdd-step-test.py:751, tests/tdd-step-test.py:773, tests/tdd-step-test.py:834 |
| D5.6 | réalisée | bin/tdd-step:556 — applique la règle d'import aux seams concernés ; bin/tdd-step:580 — associe chaque test à un seam et exige le point d'entrée en boîte noire ; bin/code-review:864 — transmet les seams déclarés et les questions sur les tests internes | formulas/mol-ticket-author.formula.toml:172 — appelle le contrôle rouge ; bin/convoy-advance:2153 — appelle la revue de code | tests/tdd-step-test.py:458, tests/tdd-step-test.py:472, tests/tdd-step-test.py:493, tests/code-review-test.py:605 |
| D5.7 | réalisée | bin/tdd-step:611 — refuse les erreurs non déclarées et exige normalement un échec d'assertion ; bin/tdd-step:633 — autorise les types d'erreur du profil et l'échec de lancement de la tranche qui établit la recette | formulas/mol-ticket-author.formula.toml:172 — appelle tdd-step red avec le profil et le commit de départ | tests/tdd-step-test.py:331, tests/tdd-step-test.py:408, tests/tdd-step-test.py:422 |
| D5.8 | réalisée | formulas/mol-ticket-author.formula.toml:235 — ordonne à l'auteur de suivre le skill tdd ; config/role-adoption-trials.json:8 — atteste que ce skill est chargé dans le rôle auteur | bin/dispatch-door:293 — n'autorise le rôle auteur que sous un essai d'adoption valide ; bin/convoy-advance:1818 — lance ce rôle | aucun |
| D5.9 | réalisée | bin/tdd-step:817 — sélectionne le régime prefactoring, trouve ou exige un commit de caractérisation, protège les tests existants et exécute la régression avant/après | formulas/mol-ticket-author.formula.toml:157 — saute le rouge et exige la caractérisation si nécessaire ; formulas/mol-ticket-author.formula.toml:257 — appelle le contrôle | tests/tdd-step-test.py:866, tests/tdd-step-test.py:883, tests/tdd-step-test.py:906, tests/tdd-step-test.py:923 |
| D5.10 | réalisée | bin/tdd-step:535 — refuse un ticket sans critères ou un critère sans test ; bin/ticket-evaluation:688 — transforme un critère intrinsèquement inobservable en Planning Exception sans dispense | formulas/mol-ticket-author.formula.toml:172 — contrôle chaque critère au rouge ; bin/convoy-advance:2156 — règle l'évaluation du ticket | tests/tdd-step-test.py:351, tests/ticket-evaluation-test.py:773 |
| D5.11 | réalisée | bin/ticket-author:498 — lance le produit au commit de pointe et capture l'observation ; bin/ticket-exit:464 — refuse finished sans preuve de démonstration valide à ce HEAD | formulas/mol-ticket-author.formula.toml:292 — exige l'observation par l'auteur et appelle demonstrate à la ligne 298 | tests/ticket-author-test.py:452, tests/ticket-exit-test.py:420, tests/ticket-exit-test.py:425 |
| D5.12 | réalisée | agents/delivery-author/overlay/.claude/guards/author-subagent-guard:22 — bloque tous les sous-agents sauf Explore et Plan ; agents/delivery-author/overlay/.claude/settings.json:3 — installe ce contrôle en PreToolUse | bin/dispatch-door:300 — exige l'essai d'adoption du rôle ; config/role-adoption-trials.json:44 — enregistre écrivain refusé et lecteur autorisé | tests/author-subagent-guard-test.py:32, tests/author-subagent-guard-test.py:39 |
| D5.13 | réalisée | formulas/mol-ticket-author.formula.toml:102 — dit explicitement qu'un écart ou un Non fait d'un ticket frère est un fait, jamais une convention | formulas/mol-ticket-author.formula.toml:91 — fait lire les Handoffs des bloqueurs au début de la formule auteur | aucun |
| D5.14 | réalisée | bin/ticket-exit:790 — enregistre finished seulement avec Handoff et preuves ; bin/spec-integration:470 — attend revue et évaluation favorables avant fusion | bin/convoy-advance:2153 — règle revue et évaluation, puis fusionne à la ligne 2169 ; formulas/mol-ticket-author.formula.toml:343 — produit la sortie finished | tests/fixture-city-oracle-test.py:284, tests/convoy-advance-test.py:1106 |
| D5.15 | réalisée | bin/ticket-exit:586 — construit une demande Planning Exception pour une question sémantique ou topologique ; bin/ticket-exit:665 — la remet à Benjamin et bin/ticket-exit:672 parque le ticket et ses descendants | formulas/mol-ticket-author.formula.toml:120 — dirige les questions d'intention vers cette sortie | tests/ticket-exit-test.py:543, tests/ticket-exit-test.py:590 |
| D5.16 | réalisée | bin/ticket-exit:568 — exige une demande opérateur structurée ; bin/ticket-exit:665 — l'envoie à la porte Benjamin et bin/ticket-exit:672 parque la sous-arborescence | formulas/mol-ticket-author.formula.toml:123 — prescrit operator_request lorsque seul l'opérateur peut répondre | tests/ticket-exit-test.py:718, tests/ticket-exit-test.py:728 |
| D5.17 | réalisée | bin/ticket-exit:679 — valide la description minimale du repair ; bin/ticket-exit:703 — publie ce repair par la porte de patch et l'ajoute comme bloqueur du ticket | formulas/mol-ticket-author.formula.toml:124 — prescrit technically_blocked pour un défaut externe bloquant ; bin/convoy-advance:1887 — laisse avancer les tickets sans ce bloqueur | tests/ticket-exit-test.py:924 |
| D5.18 | réalisée | bin/ticket-exit:476 — exige que la branche interrompue soit poussée et enregistre un Handoff partiel ; bin/convoy-advance:925 — relance une session auteur neuve sur le même ticket et sa branche | formulas/mol-ticket-author.formula.toml:125 — prescrit interrupted ; bin/convoy-advance:1869 — règle les reprises avant les nouveaux démarrages | tests/ticket-exit-test.py:755, tests/convoy-advance-test.py:1460 |
| D5.19 | réalisée | bin/ticket-exit:870 — rend interrupted lorsqu'une session assignée a disparu sans sortie déclarée ; bin/convoy-advance:889 — détecte cette interruption et prépare la reprise | bin/convoy-advance:1869 — règle automatiquement les reprises dans chaque passe | tests/ticket-exit-test.py:790, tests/convoy-advance-test.py:1477 |
| D5.20 | partielle | bin/ticket-exit:288 — exige une rubrique done non vide ou « aucun » ; bin/ticket-author:498 — capture séparément la ligne de démonstration | formulas/mol-ticket-author.formula.toml:338 — demande les quatre rubriques avant ticket-exit finished | tests/ticket-exit-test.py:307, tests/ticket-exit-test.py:326, tests/ticket-exit-test.py:442 |
| D5.21 | réalisée | bin/ticket-exit:288 — réserve et valide la rubrique deviations comme texte auteur ; formulas/mol-ticket-author.formula.toml:102 — définit un Écart comme ce qui a été livré autrement que demandé | formulas/mol-ticket-author.formula.toml:338 — exige cette rubrique au Handoff ; bin/ticket-exit:639 — exige en outre qu'une déviation de prototype nomme son ancre avant Planning Exception | tests/ticket-exit-test.py:326, tests/ticket-exit-test.py:649 |
| D5.22 | réalisée | bin/ticket-exit:288 — exige la rubrique not_done et accepte des entrées structurées what/paths ; formulas/mol-ticket-author.formula.toml:102 — la définit comme ce que le ticket a laissé de côté | formulas/mol-ticket-author.formula.toml:338 — exige cette rubrique ; bin/ticket-exit:391 — l'utilise pour justifier les marqueurs de report | tests/ticket-exit-test.py:307, tests/ticket-exit-test.py:473, tests/ticket-exit-test.py:479 |
| D5.23 | réalisée | bin/ticket-exit:288 — exige la rubrique out_of_ticket comme contenu auteur ; formulas/mol-ticket-author.formula.toml:248 — ordonne d'y consigner un défaut vu ailleurs sans le modifier | formulas/mol-ticket-author.formula.toml:338 — exige la rubrique avant finished | tests/ticket-exit-test.py:307, tests/ticket-exit-test.py:326 |
| D5.24 | réalisée autrement | bin/ticket-exit:416 — écrit dans handoff.records les commits, fichiers hors portée, rouge et marqueurs ; bin/spec-integration:612 — écrit après la remise une pièce scellée distincte merged_tests liée au commit fusionné | formulas/mol-ticket-author.formula.toml:343 — produit les relevés disponibles à la sortie ; bin/convoy-advance:2169 — déclenche ensuite la fusion et sa pièce merged_tests | tests/ticket-exit-test.py:357, tests/ticket-exit-test.py:373, tests/spec-integration-test.py:393, tests/ticket-end-test.py:505 |
| D5.25 | réalisée | bin/ticket-exit:906 — transmet le Handoff complet aux dépendants directs une fois le bloqueur fermé ; bin/code-review:814 — ne transmet au relecteur que les relevés scripts, sans sections auteur ; bin/ticket-evaluation:864 — exclut explicitement Handoff, diff et dépôt du brief Evaluator | formulas/mol-ticket-author.formula.toml:94 — fait lire les Handoffs des bloqueurs ; formulas/mol-code-review.formula.toml:45 et formulas/mol-ticket-evaluation.formula.toml:46 — chargent les briefs restreints | tests/ticket-exit-test.py:817, tests/code-review-test.py:580, tests/ticket-evaluation-test.py:894 |
| D6.1 | réalisée | bin/code-review:493 — ouvre la revue du diff d'un ticket ; bin/spec-end-review:365 — construit la revue finale du diff assemblé contre la branche protégée | bin/convoy-advance:2153 — revue par ticket ; bin/convoy-advance:2187 — revue de fin de Spec | tests/code-review-test.py:460; tests/spec-end-review-test.py:186 |
| D6.2 | réalisée | bin/code-review:429 — exige le vert au commit ; bin/code-review:561 — relève le modèle du relecteur ; bin/code-review:416 — consigne explicitement un modèle identique ; formulas/mol-code-review.formula.toml:63 — appelle le skill code-review sur les axes Standards et Spec | bin/convoy-advance:2010 — déclenche la revue après reprise de la pointe d'intégration | tests/code-review-test.py:473; tests/code-review-test.py:487 |
| D6.3 | réalisée | lib/convoy_state.py:3776 — vérifie les citations bloquantes et démote les autres ; formulas/mol-code-review.formula.toml:89 — conserve les smells comme non bloquants | bin/code-review:933 — fait passer tout enregistrement de revue par cette validation | tests/code-review-test.py:510; tests/code-review-test.py:527 |
| D6.4 | réalisée | bin/code-review:457 — fabrique les questions fermées sur les seams et les tests amendés ; lib/convoy_state.py:3843 — transforme toute réponse « non » en Blocking Finding | bin/code-review:834 — place ces questions dans le brief de la revue | tests/code-review-test.py:605 |
| D6.5 | réalisée | lib/convoy_state.py:3903 — exige corrigé ou contesté par constat ; lib/convoy_state.py:3868 — exige le jugement de la seconde session ; bin/spec-integration:393 — refuse la fusion sans verdict favorable | bin/correction-round:466 — lance l'auteur neuf ; bin/code-review:493 — lance ensuite le jugement | tests/correction-round-test.py:399; tests/correction-round-test.py:609 |
| D6.6 | réalisée | bin/code-review:629 — expire une demande sans résultat ; bin/code-review:720 — relance une fois puis arrête ; config/delivery-flow.json:20 — fixe le délai maximal de l'étape | bin/convoy-advance:2010 — exécute périodiquement ce règlement | tests/convoy-advance-test.py:1138; tests/spec-end-review-test.py:392 |
| D6.7 | réalisée | bin/spec-end-review:365 — prend tout le diff assemblé ; bin/spec-end-review:404 — invalide toute revue d'une ancienne pointe ; bin/spec-end-review:561 — convertit chaque Blocking Finding en brouillon de repair | bin/convoy-advance:2181 — lance Outcome Evaluation puis la revue finale dans la même passe | tests/spec-end-review-test.py:186; tests/spec-end-review-test.py:271; tests/spec-end-review-test.py:493 |
| D7.1 | réalisée | config/delivery-roles.json:19 — définit Evaluator séparément du reviewer ; agents/delivery-evaluator/agent.toml:8 — demande un contexte neuf et lecture seule ; bin/ticket-evaluation:377 — choisit un fournisseur distinct ou consigne l'identité | bin/convoy-advance:2034 — déclenche Ticket Evaluation ; bin/convoy-advance:1587 — déclenche Outcome Evaluation | tests/ticket-evaluation-test.py:917; tests/ticket-evaluation-test.py:931; tests/ticket-evaluation-test.py:943 |
| D7.2 | réalisée | bin/ticket-evaluation:509 — ouvre l'évaluation seulement pour une tranche ou un repair fini et vert ; lib/convoy_state.py:3989 — fige critères et démonstration ; bin/ticket-evaluation:717 — remplace l'Evaluator d'un prefactoring par un contrôle de démarrage | bin/convoy-advance:2034 — règle l'évaluation avant l'intégration | tests/ticket-evaluation-test.py:835; tests/ticket-evaluation-test.py:977; tests/ticket-evaluation-test.py:1118 |
| D7.3 | réalisée | lib/convoy_state.py:4051 — exige les états fermés et leurs preuves sans reformulation ; lib/convoy_state.py:4093 — refuse tout verdict soumis et le calcule | bin/ticket-evaluation:944 — vérifie puis enregistre la fiche de critères | tests/ticket-evaluation-test.py:597; tests/ticket-evaluation-test.py:636; tests/ticket-evaluation-test.py:663 |
| D7.4 | réalisée | bin/ticket-evaluation:509 — distingue non observé, inobservable par le critère et panne d'environnement ; bin/correction-round:352 — réunit les non-observés pour l'auteur | bin/convoy-advance:2034 — route le résultat de l'évaluation ; bin/convoy-advance:2161 — ouvre le tour de correction quand nécessaire | tests/ticket-evaluation-test.py:757; tests/ticket-evaluation-test.py:773; tests/ticket-evaluation-test.py:796 |
| D7.5 | réalisée | bin/project-launch:93 — crée la copie Git propre ; bin/project-launch:180 — applique recette, port libre et jeu synthétique ; bin/project-launch:245 — arrête et nettoie le lancement | bin/ticket-evaluation:455 — prépare chaque produit évalué et bin/ticket-evaluation:488 — l'arrête | tests/ticket-evaluation-test.py:508; tests/ticket-evaluation-test.py:530; tests/ticket-evaluation-test.py:580 |
| D7.6 | réalisée | bin/ticket-end:663 — sélectionne les écrans touchés et vérifie leurs ancres ; bin/spec-end:462 — vérifie toutes les ancres et tous les états en fin de Spec | bin/convoy-advance:2071 — lance la fidélité avant fusion ; bin/convoy-advance:2164 — applique sa porte dans la passe de ticket | tests/prototype-fidelity-test.py:196; tests/prototype-fidelity-test.py:398; tests/convoy-advance-test.py:1055 |
| D7.7 | réalisée | lib/convoy_state.py:6260 — ouvre l'évaluation sur toutes les user stories numérotées ; lib/convoy_state.py:6425 — exige preuves, exploration, écarts et classifications ; lib/convoy_state.py:6324 — exige un repair pour une story non observée ou un constat classé réparé | bin/convoy-advance:1587 — règle Outcome Evaluation au commit mécanique ; bin/convoy-advance:1560 — publie ses repairs | tests/outcome-evaluation-test.py:281; tests/outcome-evaluation-test.py:459; tests/outcome-evaluation-test.py:566; tests/outcome-evaluation-test.py:692 |
| D8.1 | réalisée | lib/convoy_state.py:385 — borne commune à un tour ; bin/correction-round:490 — ouvre un unique tour après réponse de la revue et de l’évaluation ; bin/correction-round:455 — arrête et remonte le ticket encore refusé | bin/convoy-advance:2161 — appelle correction-round settle après les deux contrôles | tests/correction-round-test.py:399 |
| D8.2 | réalisée | lib/convoy_state.py:391 — fixe deux refus au total, donc un seul retour à l’auteur ; bin/test-review:428 — le second refus devient un arrêt remonté | bin/convoy-advance:1993 — appelle test-review settle ; bin/convoy-advance:2150 — le branche dans la passe réelle | tests/test-review-test.py:282 ; tests/test-review-test.py:353 |
| D8.3 | réalisée | bin/tdd-step:787 — autorise un amendement avec nouveau rouge et nouveau gel ; bin/tdd-step:794 — un second amendement déclenche amendment_exhausted et arrête le ticket | bin/convoy-advance:1974 — remonte les arrêts d’amendement ; bin/convoy-advance:2144 — exécute ce règlement dans la passe | tests/tdd-step-test.py:751 ; tests/tdd-step-test.py:773 |
| D8.4 | réalisée | config/delivery-flow.json:6 — règle K à 3 ; bin/convoy-advance:1006 — additionne les causes et parque à la troisième reprise avec les descendants | bin/convoy-advance:1869 — règle toutes les reprises ; bin/convoy-advance:1905 — déclenche ensuite la demande groupée d’opérateur | tests/convoy-advance-test.py:1738 ; tests/convoy-advance-test.py:1763 |
| D8.5 | réalisée | config/delivery-flow.json:7 — fixe la borne à 2 ; bin/convoy-advance:1863 — interdit tout nouveau démarrage lorsque cette borne est atteinte | bin/convoy-advance:2128 — applique la borne dans advance_convoy à chaque passe | tests/convoy-advance-test.py:2061 |
| D8.6 | réalisée | bin/convoy-advance:1331 — publie par code un repair unique pour le rouge ; bin/convoy-advance:1839 — ne laisse démarrer ou reprendre que ce repair ; bin/spec-integration:737 — bloque les autres fusions sous rouge | bin/convoy-advance:1843 — appelle settle_red dès la passe ; bin/convoy-advance:2169 — la fusion relit ensuite cet état | tests/convoy-advance-test.py:1940 ; tests/convoy-advance-test.py:1958 |
| D8.7 | réalisée | lib/convoy_state.py:5857 — utilise un compteur commun à toutes les sources et la borne end_rounds ; bin/convoy-advance:1768 — produit la demande « non conforme » lorsque les tours sont arrêtés | bin/convoy-advance:2200 — appelle settle_non_conforme à chaque passe | tests/convoy-stops-fixture-city-test.py:904 |
| D8.8 | réalisée | bin/project-planning-profile:95 — fixe k=3 par défaut et permet sa configuration ; bin/tdd-step:745 — exécute chaque test k fois et classe tout résultat mixte comme instable | formulas/mol-ticket-author.formula.toml:124 — l’étape verte de l’auteur lance bin/tdd-step green | tests/tdd-step-test.py:622 ; tests/tdd-step-test.py:728 |
| D8.9 | réalisée | lib/convoy_state.py:4749 — l’ouverture du tour incrémente atomiquement correction_rounds et resumes | bin/correction-round:501 — ouvre le tour depuis le règlement réel ; bin/convoy-advance:2161 — appelle ce règlement | tests/correction-round-test.py:559 |
| D8.10 | réalisée | lib/convoy_state.py:4657 — invalide les verdicts sur une ancienne pointe et compte une reprise, sauf si le tour de correction ou le retour de fusion l’a déjà comptée | bin/spec-integration:512 — appelle invalidate-verdicts avant toute fusion ; bin/convoy-advance:2169 — lance ce contrôle dans le flux | tests/spec-integration-test.py:626 ; tests/correction-round-test.py:571 |
| D8.11 | réalisée | bin/correction-round:610 — n’autorise la dérogation que sur un Blocking Finding, par l’approbateur déclaré et avec ses mots ; bin/ticket-evaluation:688 — transforme un critère inobservable en Planning Exception et parcage | bin/correction-round:423 — la remontée du ticket arrêté présente cette commande à Benjamin ; bin/ticket-end:493 — la porte reconnaît la dérogation enregistrée | tests/correction-round-test.py:399 ; tests/ticket-end-test.py:567 |
| D8.12 | réalisée | lib/convoy_state.py:5882 — arrête si une story a déjà été refusée ; lib/convoy_state.py:5886 — arrête si le nombre de stories non observées ne diminue pas | bin/convoy-advance:1768 — transforme ces arrêts anticipés en demande « non conforme » ; bin/convoy-advance:2200 — l’appelle dans la passe | tests/convoy-stops-fixture-city-test.py:950 ; tests/convoy-stops-fixture-city-test.py:969 |
| D8.13 | partielle | config/delivery-flow.json:3 — déclare plusieurs valeurs sans base mesurée et configure K, Planning Exceptions et tours de fin ; lib/convoy_state.py:385 — conserve toutefois les bornes de correction et de retour de test comme constantes | bin/convoy-advance:2116 — charge les réglages du flux ; bin/project-planning-profile:364 — charge k depuis le profil | aucun |
| D9.1 | réalisée | bin/evidence-capture:559 — inscrit type, heure, commit et adresse ; bin/evidence-capture:566 — exécute réellement la commande et conserve sa sortie ; bin/evidence-capture:691 — vérifie le scellé | bin/ticket-end:220 — vérifie les pièces par l’outil ; les scripts du flux appellent evidence-capture lors des étapes TDD, évaluation, démonstration et fusion | tests/evidence-capture-test.py:165 ; tests/evidence-capture-test.py:510 |
| D9.2 | partielle | bin/evidence-capture:137 — place le magasin hors Git ; bin/evidence-capture:517 — range par Spec puis ticket et écrit l’empreinte ; bin/outcome-promote:401 — purge après promotion | bin/convoy-advance:2140 — appelle outcome-promote dans le flux ; bin/outcome-promote:403 — appelle evidence-capture purge après promotion | tests/evidence-capture-test.py:575 ; tests/evidence-capture-test.py:601 ; tests/outcome-promote-test.py:144 |
| D9.3 | réalisée | bin/ticket-end:62 — définit la liste fermée et versionnée ; bin/ticket-end:196 — refuse toute fermeture depuis une session d’agent ; lib/convoy_state.py:3386 — remplace la fermeture simple par l’écriture atomique du relevé complet | bin/convoy-advance:2173 — l’ordre d’avancement appelle ticket-end settle | tests/ticket-end-test.py:396 ; tests/ticket-end-test.py:724 ; tests/ticket-end-test.py:537 |
| D9.4 | réalisée | bin/ticket-end:280 — compare le digest courant au digest gelé avec le graphe et vérifie que les textes évalués sont identiques | bin/ticket-end:516 — évalue cette condition dans la liste fermée ; bin/convoy-advance:2173 — appelle la porte | tests/ticket-end-test.py:464 |
| D9.5 | réalisée | bin/ticket-end:300 — exige un Handoff complet à la pointe, une preuve rouge scellée et une démonstration scellée ; le prefactoring exige sa preuve de régression | bin/ticket-end:516 — exécute la condition 2 ; bin/convoy-advance:2173 — appelle la porte après fusion | tests/ticket-end-test.py:471 ; tests/ticket-end-test.py:427 |
| D9.6 | réalisée | bin/ticket-end:327 — exige un verdict favorable à la pointe et chaque critère plus la démonstration en état observed avec preuve ; bin/ticket-end:344 — exige le démarrage capturé pour un prefactoring | bin/ticket-end:516 — exécute la condition 3 ; bin/convoy-advance:2173 — appelle la porte | tests/ticket-end-test.py:478 ; tests/ticket-end-test.py:427 |
| D9.7 | partielle | bin/ticket-end:363 — exige un contrôle de fidélité à la pointe pour les tickets d’interface ; bin/ticket-end:85 — considère passants « vert » mais aussi « accepté par Benjamin » | bin/convoy-advance:2166 — lance le contrôle avant fusion ; bin/ticket-end:516 — lit son résultat dans la condition 4 | tests/ticket-end-test.py:595 |
| D9.8 | réalisée | bin/ticket-end:383 — lit le relevé de marqueurs du Handoff à la pointe et refuse tout marqueur non déclaré | bin/ticket-end:516 — exécute la condition 5 ; bin/convoy-advance:2173 — appelle la porte | tests/ticket-end-test.py:491 |
| D9.9 | réalisée | bin/ticket-end:396 — vérifie le commit du ticket fusionné, son accessibilité depuis la branche d’intégration et la pièce merged_tests verte sur le commit résultant | bin/spec-integration:612 — produit merged_tests sur le résultat ; bin/convoy-advance:2173 — exécute ensuite la porte | tests/ticket-end-test.py:500 ; tests/ticket-end-test.py:505 ; tests/convoy-advance-test.py:907 |
| D9.10 | réalisée | bin/ticket-end:419 — vérifie toutes les pièces et exige que les preuves de l’état fusionné portent la pointe exacte ; bin/ticket-end:401 — exige que cette pointe soit le ticket_commit fusionné | bin/ticket-end:516 — exécute la condition 7 ; bin/convoy-advance:2173 — appelle la porte | tests/ticket-end-test.py:396 ; tests/ticket-end-test.py:518 |
| D9.11 | réalisée | bin/ticket-end:440 — vérifie les pièces rouge, gel et vert, exige le vert à la pointe et contrôle seam_mode dans le rapport rouge | bin/ticket-end:516 — exécute la condition 8 ; bin/convoy-advance:2173 — appelle la porte | tests/ticket-end-test.py:525 ; tests/tdd-step-test.py:622 |
| D9.12 | réalisée | bin/ticket-end:478 — exige une revue favorable à la pointe ou une dérogation enregistrée pour chaque Blocking Finding restant | bin/correction-round:627 — enregistre la dérogation autorisée ; bin/ticket-end:516 — évalue la condition 9 dans la porte | tests/ticket-end-test.py:567 ; tests/ticket-end-test.py:582 |
| D9.13 | réalisée | lib/convoy_state.py:2861 — signale toute fermeture sans ticket_end ni withdrawn ; bin/ticket-graph-publish:2211 — exige une Planning Exception résolue et recalcule le graphe avant retrait | bin/ticket-graph-publish:2439 — ferme les retraits validés avec la porte withdrawn ; bin/convoy-advance:2135 — arrête le flux sur un état sans règle | tests/ticket-graph-publish-coverage-test.py:1020 ; tests/ticket-graph-publish-coverage-test.py:1028 ; tests/ticket-end-test.py:763 |
| D9.14 | réalisée | lib/convoy_state.py:1554 — calcule les états ouvert, réparé ou accepté par Benjamin des écarts et non-faits ; lib/convoy_state.py:6324 — limite les constats hors ticket à repaired, proposal ou dismissed avec raison | bin/convoy-advance:1536 — publie les repairs demandés pour les éléments suivis ; bin/outcome-evaluation:742 — donne au seul Evaluator de fin les commandes de classement ; bin/convoy-advance:2183 — lance cette évaluation | tests/spec-end-test.py:607 ; tests/spec-end-test.py:655 ; tests/outcome-evaluation-test.py:566 ; tests/outcome-evaluation-test.py:589 ; tests/outcome-evaluation-test.py:596 |
| D9.15 | réalisée | bin/spec-end:824 — exécute la porte sur une pointe après reprise de la branche protégée ; bin/spec-end:658 périme tout relevé qui ne correspond plus à cette pointe | bin/convoy-advance:1612 — n’appelle la porte que lorsque tous les tickets sont fermés et que l’intégration n’est pas rouge | tests/convoy-advance-test.py:2207; tests/spec-end-test.py:512 |
| D9.16 | réalisée | bin/spec-end:318 — contrôle tickets fermés par porte ou retirés, absence de parcage, états finaux des écarts et non faits, et absence de Planning Exception ouverte | bin/spec-end:843 — cette condition est évaluée en premier lors du run appelé par bin/convoy-advance:1626 | tests/spec-end-test.py:580; tests/spec-end-test.py:589; tests/spec-end-test.py:598; tests/spec-end-test.py:607 |
| D9.17 | réalisée | bin/spec-end:872 — appelle la reprise de la branche protégée et la commande de régression, puis n’enregistre la condition 2 qu’avec un code de sortie nul | bin/convoy-advance:1626 — exécute bin/spec-end run dans la vraie passe d’avancement | tests/spec-end-test.py:512; tests/spec-end-test.py:726 |
| D9.18 | réalisée | bin/spec-end:526 — agrège tous les prototypes et contrôle toutes les ancres de leurs états prototypés ; bin/spec-end:892 applique ce contrôle sur la même pointe | bin/convoy-advance:1626 — passe le profil du projet à la porte de fin de Spec | tests/spec-end-test.py:759 |
| D9.19 | réalisée | bin/convoy-advance:2183 — lance l’Outcome Evaluation puis bin/convoy-advance:2188 lance la revue de fin dans la même passe, sur le même commit | orders/convoy-advance.toml:64 — l’ordre périodique exécute la passe d’avancement | tests/convoy-advance-test.py:2435 |
| D9.20 | réalisée | bin/spec-end:611 — lit le verdict de l’Outcome Evaluation puis refuse les constats non classés ou encore ouverts avant de passer la condition 5 | bin/spec-end:774 — compose les conditions finales lors du run appelé par bin/convoy-advance | tests/outcome-evaluation-test.py:643; tests/outcome-evaluation-test.py:673 |
| D9.21 | réalisée | bin/spec-end:640 — exige un dossier au même commit, dont la page, les pièces, l’empreinte et l’état enregistré sont encore valides | bin/convoy-advance:1715 — génère le dossier lorsque seule cette condition échoue, puis relance la porte à bin/convoy-advance:2197 | tests/evidence-pack-test.py:490; tests/evidence-pack-test.py:505; tests/evidence-pack-test.py:626 |
| D9.22 | réalisée | lib/convoy_state.py:5568 — autorise exactement les fermetures accepted après promotion et abandoned sans promotion | bin/outcome-promote:387 — ferme le convoi sur la réponse enregistrée, via bin/convoy-advance:2140 | tests/convoy-close-test.py:212; tests/convoy-close-test.py:237 |
| D9.23 | partielle | bin/outcome-promote:462 — si la branche protégée a avancé, reprend sa pointe, appelle bin/spec-end replay pour tests et fidélité, puis vérifie le démarrage à bin/outcome-promote:484 ; les rouges annulent l’acceptation à bin/outcome-promote:346 | bin/convoy-advance:1462 — appelle outcome-promote après la réponse de Benjamin | tests/outcome-promote-test.py:161; tests/outcome-promote-test.py:178; tests/outcome-promote-test.py:188 |
| D9.24 | réalisée | bin/method-check:77-115 — contrôle chaque ligne de la table et refuse une exigence, un mécanisme, une commande d'usine ou une preuve absents | .github/workflows/ci.yml:142-163 — la CI découvre et exécute automatiquement les tests, dont celui de method-check | tests/method-check-test.py:190-249 |
| D9.25 | réalisée | bin/ticket-graph-publish:582-713 — impose genre, ligne de démonstration et critères observables ; bin/ticket-graph-publish:1141-1157 — exige une relecture liée au digest courant | bin/ticket-graph-publish:1967-2039 — bd-publish applique le contrat d'entrée et appelle graph_review_of avant toute publication | tests/graph-review-test.py:229-255,371-409 |
| D9.26 | réalisée | lib/convoy_state.py:752-788,3214-3226 — calcule et gèle l'empreinte ordonnée des critères avec le digest du graphe ; bin/ticket-end:280-297 — condition 1 compare critères et digests | bin/convoy-advance:2093-2103,2173-2175 — appelle automatiquement la porte de fin de ticket | tests/ticket-end-test.py:464-470 |
| D9.27 | réalisée | bin/tdd-step:580-659 — lance chaque test de critère contre le commit de départ et enregistre résultat, seam, base et commit | formulas/mol-ticket-author.formula.toml:172-174 — l'étape rouge de la formule auteur lance tdd-step red | tests/tdd-step-test.py:313-366 |
| D9.28 | réalisée | bin/tdd-step:674-702,734-814 — gèle les empreintes de la table, des tests et du harness, refuse leur modification et borne l'amendement à un seul avec nouveau rouge et diff | formulas/mol-ticket-author.formula.toml:187-191,255-257 — la formule enchaîne relecture, gel puis vert ; l'amendement reste la commande bornée du même flux | tests/tdd-step-test.py:538-610,622-719,751-855 |
| D9.29 | réalisée | bin/tdd-step:556-577,580-630 — contrôle soit la règle d'import vers un point d'entrée, soit les appels réellement observés par le recorder boîte noire | formulas/mol-ticket-author.formula.toml:172-174 — l'étape rouge passe obligatoirement par ce contrôle | tests/tdd-step-test.py:437-493 |
| D9.30 | réalisée | bin/ticket-evaluation:944-1025 — valide les Evidence Records et calcule l'état par critère ; bin/outcome-evaluation:870-940 — fait de même par user story sur le produit assemblé | bin/convoy-advance:2034-2049,2156-2158,2181-2185 — déclenche Ticket Evaluation puis Outcome Evaluation dans le flux | tests/ticket-evaluation-test.py:467-508,553-717; tests/outcome-evaluation-test.py:281-401,459-510 |
| D9.31 | réalisée | bin/prototype-fidelity:450-472,541-607 — compare tokens, structure et styles calculés pour chaque ancre, état et viewport ; bin/prototype-fidelity:742-759 — refuse un état sans relevé et enregistre le résultat | bin/convoy-advance:2071-2084,2164-2168 — déclenche le contrôle des tickets d'interface avant fusion | tests/prototype-fidelity-test.py:196-240,282-292 |
| D9.32 | réalisée | bin/code-review:83-103,933-969 — impose le rôle relecteur en lecture seule, valide les citations et enregistre les Blocking Findings ; config/delivery-roles.json:13-23 — sépare reviewer et evaluator | bin/convoy-advance:2010-2018,2153-2155 — lance la revue de code avant fusion via son rôle et sa formule | tests/code-review-test.py:460-487,543-621,700-712,942-952 |
| D9.33 | réalisée | bin/ticket-exit:288-326,372-463 — valide le Handoff et détecte les marqueurs de report dans les lignes ajoutées ; lib/convoy_state.py:3044-3052 et bin/spec-end:320-379 — rendent les éléments suivis et exigent leur état final | formulas/mol-ticket-author.formula.toml:325-344 — la sortie structurée de la formule appelle ticket-exit ; bin/convoy-advance:2178-2180 appelle ensuite la porte de fin de Spec | tests/ticket-exit-test.py:462-510; tests/spec-end-test.py:648-702 |
| D9.34 | réalisée | bin/convoy-advance:1925-1939 — fusionne un ticket à la fois avec une limite de 1 ; bin/spec-end:103-123,675-726 — rend un verdict explicite pour chacune des sept conditions | bin/convoy-advance:2169-2197 — enchaîne fusion, fins de ticket, fin de Spec, évaluations, revue et Evidence Pack | tests/fixture-city-oracle-test.py:284-311,430-460; tests/spec-integration-test.py:765-794; tests/spec-end-test.py:512-536 |
| D9.35 | réalisée | bin/upstream-skills-check:72-145 — compare octet par octet skills/ au tag épinglé et refuse tout fichier modifié, ajouté ou retiré | .github/workflows/ci.yml:142-163 — la CI découvre et lance automatiquement le test de comparaison | tests/upstream-skills-check-compare-test.sh:42-72,110-119 |
| D9.36 | réalisée | bin/owner-answer:425-470 — n'accepte que les réponses fermées, exige les mots et vérifie commit et empreinte du dossier avant enregistrement | bin/convoy-advance:1462-1478 — consomme la réponse enregistrée pour promouvoir ou fermer exactement l'Outcome jugé | tests/owner-answer-test.py:139-216 |
| D9.37 | réalisée | bin/dispatch-door:383-395 — pose la marque et le relevé de dispatch ; lib/convoy_state.py:2858-2868 — détecte démarrage ou fermeture hors porte ; bin/convoy-advance:812-854 — arrête et signale l'état sans règle | orders/convoy-advance.toml:59-64 — l'ordre appelle convoy-advance ; bin/convoy-advance:1818-1822,1828-1834 — tous les départs passent par la porte et l'anomalie stoppe le convoi | tests/convoy-advance-test.py:466-527,616-625; tests/dispatch-door-guard-test.sh:140-181 |
| D10.1 | réalisée | bin/evidence-pack:1002 — rend une page statique depuis des lignes fixes et des valeurs enregistrées ; bin/evidence-pack:1121 vérifie commit, empreinte, pièces et état courant | bin/convoy-advance:1725 — appelle evidence-pack generate dans le flux | tests/evidence-pack-test.py:143; tests/evidence-pack-test.py:194; tests/evidence-pack-test.py:439 |
| D10.2 | réalisée | bin/evidence-pack:957 — construit la rubrique 0 depuis le dernier lot de constats rendus, avec route, action effectuée et preuve | bin/evidence-pack:1008 — insère cette rubrique avant l’en-tête lorsqu’un jugement précédent contient des constats | tests/owner-answer-test.py:480 |
| D10.3 | partielle | bin/evidence-pack:441 — rend Spec, digests, branche, commit, branche protégée et verdict détaillé de chaque condition ; bin/evidence-pack:455 indique qu’aucun produit n’est lancé par le dossier et ne liste que les anciennes adresses de l’Outcome Evaluation lorsqu’elles existent | bin/evidence-pack:1003 — place cet en-tête en rubrique 1 lors de la génération appelée par bin/convoy-advance:1725 | aucun |
| D10.4 | réalisée | bin/evidence-pack:551 — rassemble propositions, écarts de fidélité, comparaisons côte à côte avec différence, exploration et mentions d’indépendance | bin/evidence-pack:1003 — produit la rubrique 2 dans tout dossier généré par le flux | tests/evidence-pack-test.py:280 |
| D10.5 | réalisée | bin/evidence-pack:569 — énumère états non prototypés, critères du socle sans mécanisme, limites connues et manques propres à la livraison | bin/evidence-pack:1003 — produit obligatoirement la rubrique 3 ; bin/evidence-pack:227 refuse une configuration vide | tests/evidence-pack-test.py:221; tests/evidence-pack-test.py:245; tests/evidence-pack-test.py:264 |
| D10.6 | réalisée | bin/evidence-pack:627 — produit un article par user story avec état, tickets couvrants et Evidence Record | bin/evidence-pack:1003 — insère ces articles en rubrique 4 | tests/evidence-pack-test.py:143 |
| D10.7 | réalisée | bin/evidence-pack:703 — rend par ticket la ligne de démonstration, la preuve auteur, les états et preuves par critère, les refus, reprises et verdicts de porte | bin/evidence-pack:1004 — rend chaque ticket en rubrique 5 | tests/evidence-pack-test.py:143 |
| D10.8 | réalisée | bin/evidence-pack:743 — liste chaque écart, non fait et constat hors ticket avec son état calculé et son éventuel repair | bin/evidence-pack:1005 — place ces éléments en rubrique 6 | tests/evidence-pack-test.py:351; tests/outcome-evaluation-test.py:589 |
| D10.9 | réalisée | bin/evidence-pack:783 — rend les tickets repair, Planning Exceptions, dérogations avec mots de Benjamin, autres réponses et arrêts remontés | bin/evidence-pack:1005 — insère cette vue en rubrique 7 | tests/evidence-pack-test.py:351 |
| D10.10 | réalisée | bin/evidence-pack:850 — rend fichiers hors Declared Scope, modèles par rôle, durée, tours de fin et contradictions ticket/Outcome | bin/evidence-pack:1005 — place ces relevés en rubrique 8 | tests/evidence-pack-test.py:351; tests/evidence-pack-test.py:401 |
| D10.11 | réalisée | bin/evidence-pack:922 — rend pour chaque ticket les étapes TDD, la relecture des tests et toutes les rondes de revue ; bin/evidence-pack:945 ajoute la revue de fin entière | bin/evidence-pack:1005 — produit la rubrique 9 dans chaque dossier | aucun |
| D11.1 | réalisée | bin/convoy-advance:1350-1366,1408-1418 — envoie par escalation-door une demande bloquante nommée Acceptance Request avec le lien de l’Evidence Pack | bin/convoy-advance:2204-2209 — déclenche ce règlement après la porte de fin de Spec | tests/convoy-stops-fixture-city-test.py:1168 |
| D11.2 | partielle | bin/acceptance-session:339-367,373-440 — lance le produit au commit du dossier, gère la panne et arrête les produits; bin/acceptance-session:77-83 — remet seulement des consignes à l’agent | docs/ACCEPTANCE_SESSION.md:121-130 — le protocole opérateur fait exécuter open, owner-answer ou record, puis close | tests/acceptance-session-test.py:204,227,298; tests/acceptance-session-real-session-test.sh:1 |
| D11.3 | réalisée | bin/owner-answer:425-474 — borne les réponses; lib/convoy_state.py:5439-5511 — enregistre accepté, constats rendus ou abandonné et remet l’Outcome en livraison après constats | docs/ACCEPTANCE_SESSION.md:124-129 — la session utilise cette commande pour la réponse au Delivered Outcome | tests/owner-answer-test.py:139,263,499,514 |
| D11.4 | réalisée | bin/owner-answer:254-267,295-323,425-459 — vérifie l’approbateur déclaré, la pointe, le commit et l’empreinte du dossier avant l’écriture unique dans gc.flow.judgement | docs/ACCEPTANCE_SESSION.md:124-129 — owner-answer est la commande prescrite pour enregistrer le jugement | tests/owner-answer-test.py:139,158,173,191,202 |
| D11.5 | réalisée | bin/owner-answer:85-91,396-422 — expose exactement les verdicts avant, plus tard et sans suite; lib/convoy_state.py:5465-5477 — les rend obligatoires avant accepté | docs/ACCEPTANCE_SESSION.md:124-127 — le protocole exige ces verdicts avant la réponse finale | tests/owner-answer-test.py:130,229,246 |
| D11.6 | réalisée | lib/convoy_state.py:5379-5417 — affecte par code une route fermée à chaque Owner Finding | bin/owner-answer:425-459 — la réponse « constats rendus » appelle ce routage lors de son enregistrement | tests/owner-answer-test.py:263 |
| D11.7 | partielle | lib/convoy_state.py:5401-5417 — vérifie que la citation désigne une story existante ou une ancre du prototype et exige alors un brouillon de repair | bin/convoy-advance:1430-1438 — publie le repair ainsi rédigé par la porte de patch | tests/owner-answer-test.py:263,346 |
| D11.8 | partielle | lib/convoy_state.py:5410-5417,5495-5503 — route les constats sans citation reconnue vers une Planning Exception unique; lib/convoy_state.py:5671-5714 — exige ensuite Spec amendée et graphe republié | bin/owner-answer:425-459,477-482 — enregistre le lot et sa résolution par les commandes du protocole d’acceptation | tests/owner-answer-test.py:263,377,390 |
| D11.9 | réalisée | lib/convoy_state.py:5397-5400 — route later sans repair; bin/owner-answer:352-380 — crée par code la proposition correspondante | bin/convoy-advance:1441-1450 — réessaie automatiquement la création si la porte des propositions avait échoué | tests/owner-answer-test.py:229,263,532 |
| D11.10 | réalisée | lib/convoy_state.py:5504-5507 — remet les tours de fin à zéro pour le nouveau lot; bin/convoy-advance:2172-2209 — refait toute la chaîne jusqu’au nouveau dossier | orders/convoy-advance.toml:63-64 — l’ordre récurrent avance automatiquement le repair et toutes les portes suivantes | tests/convoy-stops-fixture-city-test.py:1346 |
| D11.11 | partielle | bin/convoy-advance:1746-1799 — produit la même page et une demande à trois options; bin/acceptance-session:448-469 — refuse accepté et transmet l’option choisie à escalation-door | docs/ACCEPTANCE_SESSION.md:128-130 — la session doit exécuter record pour une demande non conforme; aucun code du flux ne consomme ensuite cette réponse | tests/acceptance-session-test.py:350,359,368 |
| D11.12 | réalisée | bin/convoy-advance:1394-1456 — attend indéfiniment une réponse explicite; bin/owner-answer:222-231 et lib/convoy_state.py:5310-5316 — refusent toute réouverture après l’acceptation fermée | orders/convoy-advance.toml:63-64 — les passes périodiques respectent ces deux gardes | tests/convoy-stops-fixture-city-test.py:1184; tests/outcome-promote-test.py:265,276 |
| D12.1 | réalisée | bin/project-planning-profile:79 — exige recipe, entry_points et health_probe dans tout bloc launch ; bin/project-planning-profile:317 les valide | bin/project-launch:189 — exécute la recette et sonde la santé ; bin/tdd-step:432 utilise les points d'entrée | tests/project-planning-profile-test.py |
| D12.2 | réalisée | bin/project-planning-profile:368 — exige au moins un jeu de données synthétique nommé | bin/project-launch:148 — refuse un lancement sans dataset puis injecte son chemin dans la recette | tests/project-launch-test.py |
| D12.3 | réalisée | bin/project-planning-profile:343 — exige un test_perimeter non vide | bin/tdd-step:668 — l'étape rouge refuse toute modification hors de ce périmètre | tests/tdd-step-test.py |
| D12.4 | réalisée | bin/project-planning-profile:350 — exige frozen_harness_paths ; bin/tdd-step:688 calcule et enregistre leur empreinte avec celles des tests | formulas/mol-ticket-author.formula.toml:190 — la formule appelle tdd-step freeze après la revue des tests | tests/tdd-step-test.py |
| D12.5 | réalisée | bin/project-planning-profile:359 — exige test_command ; bin/tdd-step:334 exige les substitutions par test et rapport ; bin/tdd-step:400 lit le JUnit et distingue failure d'error | formulas/mol-ticket-author.formula.toml:172 — l'étape rouge appelle tdd-step avec le profil | tests/tdd-step-test.py |
| D12.6 | réalisée | bin/project-planning-profile:462 — exige exactement seams ou seam_mode et limite les modes à black_box/import_rule | bin/tdd-step:367 — choisit le seam de chaque test puis applique son mode | tests/tdd-step-test.py |
| D12.7 | réalisée | bin/project-planning-profile:360 — exige regression_command | bin/tdd-step:817 — le régime prefactoring exécute cette commande avant et après | tests/tdd-step-test.py |
| D12.8 | réalisée autrement | bin/project-planning-profile:95 — définit DEFAULT_K=3 ; bin/project-planning-profile:364 normalise k avec cette valeur quand il n'est pas déclaré | bin/tdd-step:750 — l'étape verte exécute chaque test launch.k fois | tests/project-planning-profile-test.py ; tests/tdd-step-test.py |
| D12.9 | réalisée | bin/project-planning-profile:516 — valide l'équivalent des ancres d'une interface non web contre ses points d'entrée, ou une non-applicabilité motivée | bin/ticket-graph-publish:2010 — la publication fait décrire et valider le profil complet avant d'accepter le graphe | tests/fixture-second-project-test.py |
| D13.1 | réalisée | bin/convoy-advance:1818-1822,1890-1901 — sélectionne et démarre les tickets prêts via dispatch-door sous le plafond partagé | orders/convoy-advance.toml:59-64 — l'ordre périodique lance convoy-advance --all ; agents/mayor/prompt.template.md:263-271 réserve explicitement les formules auteur à convoy-advance, jamais au Mayor | tests/convoy-advance-test.py:450-456,466-477; tests/convoy-advance-isolated-city-test.sh |
| D13.2 | réalisée | lib/convoy_state.py:2861-2868 — transforme les incohérences en état sans règle ; bin/convoy-advance:1828-1834 — retourne immédiatement sans démarrer de ticket | orders/convoy-advance.toml:59-64 — chaque passe de l'ordre traverse ce contrôle | tests/convoy-advance-test.py:466-539 |
| D13.3 | réalisée | config/delivery-roles.json:13-23 — déclare reviewer et evaluator en lecture seule ; config/delivery-flow.json:14-49 — associe leurs formules autorisées ; agents/delivery-reviewer/agent.toml:1-19 et agents/delivery-evaluator/agent.toml:1-17 — configurent les agents | bin/convoy-advance:2010-2042,2150-2158,2183-2188 — route revues et évaluations vers ces formules et rôles via dispatch-door | tests/code-review-test.py:460-487; tests/ticket-evaluation-test.py:1108-1114; tests/outcome-evaluation-test.py:396-420 |
| D13.4 | réalisée | bin/ticket-exit:790-864 — valide la sortie, construit et enregistre le Handoff avant de poser l'état de sortie | formulas/mol-ticket-author.formula.toml:325-344 — l'étape finale de l'auteur appelle ticket-exit exit | tests/ticket-exit-test.py:301-326,462-510,568-590 |
| D13.5 | réalisée | bin/evidence-capture:503-556,566-570 — capture commande ou image, scelle le relevé et écrit son empreinte dans l'état | formulas/mol-ticket-evaluation.formula.toml:63-83 et formulas/mol-outcome-evaluation.formula.toml:66-86 — les Evaluators doivent capturer chaque observation avec cet outil | tests/evidence-capture-test.py:165-200,322-340,476-490 |
| D13.6 | réalisée | bin/evidence-capture:137-178,503-550 — utilise un magasin d'état hors Git, scelle les pièces et lie leur empreinte au tracker | bin/evidence-pack:253-290 — relit et vérifie les pièces du magasin ; les formules d'évaluation y déposent leurs observations | tests/evidence-capture-test.py:183-190,475-490,575-597 |
| D13.7 | réalisée | bin/tdd-step:580-702,734-784 — implémente rouge, gel et vert avec preuves et empreintes | formulas/mol-ticket-author.formula.toml:172-191,245-257 — la formule auteur exécute ces trois étapes dans l'ordre | tests/tdd-step-test.py:313-366,538-719 |
| D13.8 | réalisée | bin/ticket-exit:372-413 — inspecte les lignes ajoutées pour TODO, FIXME et marqueurs équivalents, puis les rapproche des « non faits » déclarés | bin/ticket-exit:416-463,790-864 — la sortie terminée lance le détecteur et refuse un marqueur non déclaré | tests/ticket-exit-test.py:462-510 |
| D13.9 | réalisée | bin/convoy-advance:1925-1939 — appelle spec-integration avec --limit 1 ; bin/spec-integration:687 — commande de fusion contrôlée | bin/convoy-advance:2169-2171 — une seule fusion est tentée par convoi et par passe | tests/spec-integration-test.py:765-803 |
| D13.10 | réalisée | bin/ticket-end:274-420,548-578 — évalue et enregistre neuf conditions ; bin/spec-end:103-123,675-726 — évalue les sept conditions versionnées de fin de Spec | bin/convoy-advance:2173-2180 — appelle successivement les deux portes | tests/ticket-end-test.py:464-537; tests/spec-end-test.py:512-590 |
| D13.11 | réalisée | bin/evidence-pack:227-290,1002-1020,1038-1099 — vérifie les pièces, rend les rubriques statiques et enregistre page, commit et digest | bin/convoy-advance:2191-2197 — génère le pack lorsque toutes les conditions antérieures de fin sont réunies | tests/evidence-pack-test.py:143-160,221-260,557-570 |
| D13.12 | réalisée | bin/project-launch:58-61,93-107,121-213 — crée une copie détachée propre, choisit un port libre et lance le produit sur un jeu nommé | bin/ticket-evaluation:455-488, bin/outcome-evaluation:440-471 et bin/acceptance-session:339-414 — lancent le produit à la demande pour les évaluations et l'acceptation | tests/project-launch-test.py:138-163,193-218 |
| D13.13 | réalisée | bin/owner-answer:425-474 — enregistre accepté, constats rendus ou abandonné et lie la réponse au dossier | bin/convoy-advance:1462-1478 — reprend automatiquement le flux à partir de la réponse finale enregistrée | tests/owner-answer-test.py:139-225,514-530 |
| D13.14 | réalisée | bin/prototype-fidelity:450-607,677-782 — mesure tokens, ancres, structure et styles ; bin/prototype-conformance:424-560 — contrôle variante, états, encodage, viewports, ancres, datasets et référence Git | bin/convoy-advance:2071-2084 — appelle la fidélité ; bin/spec-approve:425-500,570-573 — appelle la conformité avant approbation | tests/prototype-fidelity-test.py:196-240,282-300; tests/prototype-conformance-test.py:57-122,181-225,269-274; tests/spec-approve-test.py:478-488 |
| D13.15 | partielle | bin/spec-approve:262-359,425-500 — étend l'approbation aux stories numérotées, à l'inventaire et au prototype ; bin/ticket-graph-publish:1967-2021,2299-2414 — applique le contrat d'entrée à la publication et aux patches | bin/spec-approve:503-573 — bd-approve appelle le nouveau contrat ; bin/ticket-graph-publish:1967-2039,2456-2467 — bd-publish et bd-patch l'appliquent au vrai flux | tests/spec-approve-test.py:405-488; tests/ticket-graph-publish-entry-contract-test.py:178-216,426-440; tests/ticket-graph-publish-coverage-test.py:725-760,828-843 |

### Ce que les sessions disent ne pas avoir pu vérifier, ligne par ligne

| Ligne | Non vérifié |
|---|---|
| US07 | une session réelle de relecteur n'a pas été lancée pendant cette relecture |
| US09 | l'exhaustivité sémantique des besoins connus n'est pas vérifiable par ce code |
| US14 | La réalité du choix visuel et de la confirmation par Benjamin ne peut pas être vérifiée dans le code. |
| US17 | Le service effectif dans un navigateur n’a pas été exécuté. |
| US18 | Les mesures dans un vrai navigateur n’ont pas été exécutées. |
| US19 | Une vraie session d’Evaluator et son accès visuel au prototype n’ont pas pu être vérifiés. |
| US21 | Session Gas City réelle et tests cités non rejoués, conformément à la contrainte de lecture seule. |
| US22 | Tests cités non exécutés. |
| US23 | Tests cités non exécutés. |
| US24 | Session de relecteur réelle et tests cités non rejoués. |
| US25 | Tests cités non exécutés. |
| US26 | L'enchaînement complet dans une session auteur réelle et les tests cités n'ont pas été rejoués. |
| US27 | Démonstration réelle du produit et tests cités non rejoués. |
| US28 | Respect de l'instruction par une session auteur réelle ; tests cités non exécutés. |
| US29 | Observation humaine ou navigateur réel non rejoué ; tests cités non exécutés. |
| US30 | Tests cités non exécutés. |
| US31 | Tests cités non exécutés. |
| US32 | Tests cités non exécutés. |
| US33 | Tests cités non exécutés. |
| US34 | Nouvelle session auteur réelle non lancée ; tests cités non exécutés. |
| US35 | Tests cités non exécutés. |
| US36 | Le lancement d'une session relecteur réelle et son modèle effectif n'ont pas été rejoués. |
| US37 | Les fichiers effectivement consultés par une session relecteur réelle ne sont pas observables ici. |
| US40 | L'utilisation interactive du produit par une session Evaluator réelle n'a pas été rejouée. |
| US42 | Le démarrage d'un produit réel n'a pas été exécuté. |
| US48 | l’exécution effective de la consigne par une vraie session d’auteur Gas City |
| US55 | essai Gas City non rejoué, conformément à la consigne de lecture seule |
| US56 | tests cités non exécutés |
| US57 | aucune session Evaluator ni aucun produit réel lancé pendant cette relecture |
| US58 | aucune session relecteur réelle lancée |
| US59 | tests cités non exécutés |
| US60 | session Evaluator réelle non lancée |
| US61 | tests cités non exécutés |
| US62 | tests cités non exécutés |
| US63 | tests cités non exécutés |
| US66 | Le respect effectif de ces règles par une vraie session d’agent à ce commit |
| US74 | La comparaison réseau au dépôt upstream n'a pas été réexécutée. |
| US75 | Les sessions réelles consignées dans config/role-adoption-trials.json n'ont pas été relancées. |
| US76 | Les essais réels par fournisseur n'ont pas été relancés. |
| US79 | L'essai local-only en cité Gas City n'a pas été réexécuté. |
| US80 | Un éventuel jugement externe de Benjamin n'est pas présent dans le code de ce commit. |
| US81 | La vérification finale T32 menée hors du commit et son éventuelle conclusion restent externes au code jugé. |
| US82 | L'essai local-only en cité Gas City n'a pas été réexécuté. |
| US84 | L'essai local-only avec une vraie session Mayor n'a pas été réexécuté. |
| D0.2 | L'essai local-only de sessions réelles n'a pas été réexécuté. |
| D0.3 | Le comportement d'une vraie session Mayor consigné par l'essai local-only n'a pas été rejoué. |
| D0.4 | L'essai local-only de la formule dans Gas City n'a pas été réexécuté. |
| D1.1 | Le clone réseau du tag upstream n'a pas été réexécuté. |
| D1.4 | Les relevés de sessions réelles n'ont pas été régénérés. |
| D1.5 | L'essai réel de masquage consigné dans config/role-adoption-trials.json n'a pas été relancé. |
| D1.6 | La présence de glossaires dans d'éventuels dépôts de projets externes à ce checkout. |
| D1.7 | Les comparaisons réseau et sessions réelles d'adoption n'ont pas été réexécutées. |
| D2.7 | la qualité du jugement d'un relecteur réel sur les fichiers de branchement n'a pas été rejouée |
| D2.8 | le jugement sémantique d'un relecteur réel sur un graphe concret n'a pas été rejoué |
| D2.9 | l'exhaustivité des besoins connus |
| D2.11 | aucun dépôt distant réel n'a été interrogé pendant cette relecture |
| D2.12 | une session réelle et son contexte n'ont pas été lancés |
| D3.1 | Le fait que Benjamin ait réellement vu et choisi la variante avant l’approbation n’est pas vérifiable dans le code. |
| D3.5 | Le lancement réel du produit n’a pas été exécuté. |
| D3.6 | Une invocation manuelle éventuelle par un agent de prototype n’est pas démontrée par le flux. |
| D3.7 | Le service effectif des écrans dans un navigateur n’a pas été exécuté. |
| D3.8 | Une comparaison visuelle effective par une session neuve n’a pas pu être vérifiée. |
| D3.9 | La décision humaine finale de Benjamin n’est pas vérifiable statiquement. |
| D3.10 | La correspondance avec la source distante de Matt n’a pas été revalidée sur le réseau. |
| D4.1 | Dépôt distant et tests cités non rejoués. |
| D4.2 | Concurrence réelle de plusieurs Specs non rejouée ; tests cités non exécutés. |
| D4.3 | Tests cités non exécutés. |
| D4.4 | Concurrence Git et tests cités non rejoués. |
| D4.5 | Ordonnanceur Gas City réel non observé ; tests cités non exécutés. |
| D5.1 | Respect des consignes sémantiques par une session auteur réelle ; tests cités non exécutés. |
| D5.2 | Tests cités non exécutés. |
| D5.3 | Sessions réelles de reviewer non lancées ; tests cités non exécutés. |
| D5.4 | Tests cités non exécutés. |
| D5.5 | Tests cités non exécutés. |
| D5.6 | Tests cités non exécutés. |
| D5.7 | Tests cités non exécutés. |
| D5.8 | Respect effectif du cycle interne par l'agent, volontairement non prouvé mécaniquement. |
| D5.9 | Tests cités non exécutés. |
| D5.10 | Tests cités non exécutés. |
| D5.11 | Observation humaine ou navigateur réel non rejoué ; tests cités non exécutés. |
| D5.12 | Nouvelle session auteur réelle non lancée ; tests cités non exécutés. |
| D5.13 | Respect de cette règle par une session auteur réelle. |
| D5.14 | Cycle Gas City complet et tests cités non rejoués. |
| D5.15 | Réponse réelle de Benjamin et tests cités non rejoués. |
| D5.16 | Réception humaine réelle et tests cités non rejoués. |
| D5.17 | Publication réelle dans Beads et tests cités non rejoués. |
| D5.18 | Reprise réelle d'une session Gas City et tests cités non rejoués. |
| D5.19 | Mort réelle d'une session Gas City et tests cités non rejoués. |
| D5.20 | Sémantique du texte libre fourni par un auteur réel ; tests cités non exécutés. |
| D5.21 | Véracité sémantique d'un texte auteur réel ; tests cités non exécutés. |
| D5.22 | Exhaustivité sémantique du texte auteur ; tests cités non exécutés. |
| D5.23 | Exhaustivité et véracité du texte auteur ; tests cités non exécutés. |
| D5.24 | Production réelle des Evidence Packs et tests cités non rejoués. |
| D5.25 | Sessions réelles des trois rôles non lancées ; tests cités non exécutés. |
| D6.2 | L'exécution effective du skill Matt par une session réelle n'a pas été rejouée. |
| D7.1 | La fraîcheur effective du contexte et le fournisseur d'une session réelle n'ont pas été rejoués. |
| D7.5 | Le lancement concret de la recette n'a pas été exécuté. |
| D7.6 | Le rendu dans un navigateur réel n'a pas été rejoué. |
| D7.7 | L'exploration libre d'un produit réel par une session Evaluator n'a pas été rejouée. |
| D8.13 | la mesure future sur le cas de validation |
| D9.1 | aucun navigateur réel n’a été lancé dans cette relecture seule ; les tests utilisent le navigateur fixture |
| D9.2 | la nature réellement synthétique des jeux de données déclarés |
| D9.7 | aucun test de ticket-end n’observe explicitement cette voie d’acceptation non verte |
| D9.15 | tests cités non exécutés |
| D9.16 | tests cités non exécutés |
| D9.17 | commande de régression réelle non exécutée |
| D9.18 | navigateur et contrôle de fidélité non exécutés |
| D9.19 | chevauchement temporel de deux sessions réelles non observé |
| D9.20 | tests cités non exécutés |
| D9.21 | tests cités non exécutés |
| D9.22 | tests cités non exécutés |
| D9.23 | tests cités non exécutés |
| D9.24 | résultat d'un run CI réel à ce commit non rejoué |
| D9.25 | session réelle du relecteur de graphe non rejouée |
| D9.30 | sessions réelles d'Evaluator non rejouées |
| D9.31 | contrôle navigateur réel non exécuté |
| D9.32 | session réelle du relecteur et indépendance effective du modèle non rejouées |
| D9.34 | cité Gas City réelle non rejouée |
| D9.35 | comparaison réseau et résultat CI réels à ce commit non rejoués |
| D9.36 | réponse humaine réelle non effectuée |
| D9.37 | ordre d'une cité Gas City active non observé |
| D10.1 | tests cités non exécutés |
| D10.2 | tests cités non exécutés |
| D10.3 | adresse d’une Acceptance Session réelle non vérifiée ; aucun test ne l’asserte dans l’en-tête |
| D10.4 | captures et rendu navigateur non inspectés visuellement |
| D10.5 | tests cités non exécutés |
| D10.6 | tests cités non exécutés |
| D10.7 | tests cités non exécutés |
| D10.8 | tests cités non exécutés |
| D10.9 | tests cités non exécutés |
| D10.10 | tests cités non exécutés |
| D10.11 | aucun test ciblé de l’exhaustivité de cette rubrique n’a été trouvé |
| D11.2 | La navigation et le comportement d’une vraie session d’agent; l’essai réel est optionnel et n’a pas été exécuté |
| D12.9 | l'utilisation d'une interface non web réelle n'a pas été rejouée |
| D13.1 | ordre et Mayor réels non observés |
| D13.3 | sessions Gas City réelles de ces rôles non rejouées |
| D13.5 | capture navigateur réelle non exécutée |
| D13.12 | produit réel et son navigateur non lancés pendant cette relecture |
| D13.13 | geste réel de l'approbateur humain non effectué |
| D13.14 | contrôles navigateur et dépôt distant réels non exécutés |
| D13.15 | ordre historique des travaux de chaque ticket D01 et essais réels initiaux en cité Gas City |

## 10. Ce qui n'a PAS été vérifié

- Les sessions d'agent réelles du flux : aucun auteur, relecteur ou Evaluator réel n'a travaillé un ticket ; l'oracle joue ces rôles par son pilote de référence, et les essais « vraie session » (acceptance-session, spec-end-review, partie 2 de graph-review) tournent sans leur variable d'environnement, donc sans modèle.
- L'essai tests/convoy-stop-mayor-isolated-city-test.sh (vraie session du Mayor à chaque lancement) : exclu des essais hors CI, non lancé.
- bin/spec-approve bd-approve et bin/graph-review decide avec les mots réels de Benjamin : le parcours de l'oracle les appelle sur des données synthétiques ; aucune approbation réelle d'une Spec ou d'un graphe par le nouveau flux n'a eu lieu.
- La trace des portes ne voit pas un script bash lancé par un autre script bash sans passer par PATH : une commande peut avoir été exécutée sans y figurer ; l'inverse n'est pas possible.
- Les commandes changées par D01 que le parcours n'exécute pas (§4, colonne « non ») : elles n'ont que leurs propres tests.
- D9.2 : le caractère synthétique d'un jeu de données n'est prouvable par aucun code ; seule sa déclaration est vérifiée.
- US80 et D8.13 : le cas de validation Cockpit V2 et la mesure des bornes viennent après D01 (Spec §14).
- Un hôte au repos : la passe 2 a tourné pendant que le runner de CI et des workers travaillaient ; la charge au moment de chaque lancement est notée dans les pièces.
- La stabilité de la revue : deux passes par des sessions différentes ne rendent pas les mêmes lignes non « réalisées » (§6, comparaison). Une troisième lecture en trouverait probablement d'autres ; elle n'a pas été faite (borne annoncée à Benjamin : deux passes).
- Les lignes que chaque session dit ne pas avoir pu vérifier en lecture seule : tableau à la fin du §9.

## 11. Gestes hors du chemin normal pendant la vérification

- 2026-10-09 17:05 et 17:49 : PR 479 (T37) et PR 478 (T46) fusionnées à la main par `gh pr merge --squash`, CI verte sur leur tête exacte, fusion automatique armée et non servie par GitHub. Mots de Benjamin : « je donne mon accord explicit , sortir du chemin de livraison qu'on est justement entrain de refacto je ne trouve pas ca si terrible. » Défaut corrigé depuis (PR 482).
- 2026-10-09 17:10 à 2026-10-10 vers 04:00 : veille de fusion du lot (`tools/merge-watch.sh`), même condition que la fusion automatique ; arrêtée d'elle-même.
- 2026-10-09 17:36 à 17:55 : fenêtre d'arrêt (runbook suivi en entier), WSL de 12 à 20 processeurs. Mots de Benjamin : « ok pour 20 processeurs, je n'utilise pas le PC ». Preuve d'intégrité dans `window/`. Le Cockpit n'a pas été relancé par la séquence manuelle ; relancé le 2026-10-10 à 00:54 ; runbook corrigé (PR 492 et 497).
- 2026-10-10 00:36 à 06:08 : règle GitHub « PR à jour avec main avant fusion » levée par `./bin/enable-strict-main-protection --rollback`, puis remise. Mots de Benjamin : « A oui ». Le contrôle « Tests » est resté exigé sur chaque PR. Compensation : batterie complète au commit jugé (§7).
- 2026-10-10 06:09 : premier lancement de l'oracle de la passe 2 sans `--delivery-driver` (erreur de la session opérateur) : sortie 1 en 0 s, rien de jugé ; sorties gardées dans `pass2/oracle-sans-pilote`, oracle relancé avec le pilote de référence.
- Les essais hors CI de la passe 2 ont été lancés depuis le worktree au commit jugé, avec `ESCALATION_DOOR_BIN=/bin/true` : un échec n'appelle pas le Mayor (lancement opérateur, pas l'ordre de nuit) ; aucun ticket n'a été créé (vérifié). Les onze essais en échec ont été rejoués depuis la racine de l'usine, alors au commit f18f456 : le commit jugé plus les PR 498 et 500, sans rapport avec D01.

## 12. Ce que les auteurs des réparations ont déclaré dans leurs PR

Rubriques « Non fait », « Écarts » et « Constats hors ticket » des PR des tickets T37 à T52, recopiées telles quelles (`gh pr view <n> --json body`, relevé du 2026-10-10). Aucune n'est jugée ici ; celles qu'une session vérificatrice a reprises sont au §7.

### PR 478 — `do-work/af-lb9zkz`

**Non fait**

- Aucun passage par le Fixture City Oracle n'a été ajouté : la Fixture City ne porte qu'un Validated Prototype ; les quatre critères sont prouvés par la ligne de commande de chaque porte (seam 2).
- `bd-approve` sur deux Validated Prototypes tous deux présents sur le dépôt distant et conformes n'a pas de test de passage (l'outil de fixture ne matérialise qu'une branche) ; sont testés : la lecture des deux références (`outline`), le refus du second sans inventaire, le refus du second absent du dépôt distant, le refus de deux chemins identiques.

**Écarts**

- **Ancre de région qui englobe la page.** Le critère dit « une ancre contient tous les éléments visibles de la page : refus ». Livré : refus, sauf pour l'ancre propre d'un élément de région (par exemple `<main>`) dont chaque élément visible a une ancre plus proche. Sans cette exception, une page dont tout le contenu est dans `<main>` serait irréfutable : `<main>` doit porter sa propre ancre (même critère) et la porterait sur toute la page. Une ancre de page posée sur `<body>` ou un `<div>` est refusée, avec ou sans ancres plus fines dedans. Une page d'un seul élément visible n'est pas jugée.
- **Référence facultative sur `prototype-conformance check`.** `--branch --commit --remote --protected` se donnent ensemble ou pas du tout ; sans eux la commande rend les six relevés d'avant (les tests existants passent sans changement). `spec-approve` les passe toujours.
- **Variante perdante non jugée tant qu'un état n'a pas d'adresse** : c'est alors l'échec de `states`, et aucune page ne se distingue d'une variante perdante.
- **Forme de la Spec à plusieurs prototypes** : la Spec §3 ne fixe pas comment en nommer plusieurs. Choisi : une section `## Validated Prototype : <nom>` par prototype supplémentaire ; un prototype s'identifie par son chemin.
- **Rattachement d'un ticket à son prototype** : champ de brouillon `prototype: <chemin>`, aucun nouveau champ dans le tracker ; sur `bd-patch`, le prototype d'un ticket déjà publié se lit dans la référence posée dans sa description, et le champ n'est pas gelé à part.
- **Prototype sans Fold** : avec plusieurs prototypes, un prototype sans Fold est refusé dès que le graphe porte un ticket d'interface, même si aucun ticket ne lui est rattaché ; avec un seul prototype, la règle d'avant est inchangée (pas de Fold exigé sans ticket d'interface).
- **« Fichier servi »** (fidélité) : la page de chaque état comparé et les fichiers qu'elle lie à sa propre adresse (`href` de `<link>`, `src`). Le manifeste et les jeux de données du prototype ne comptent pas : le produit est lancé sur les mêmes données d'exemple.

**Constats hors ticket**

- `bin/graph-review` garde le contrôle `prototype_fold_present_and_first`, formulé pour un seul Fold ; non touché ici (contrôle d'un agent relecteur, hors des critères du ticket).
- `bin/prototype-fidelity` et `bin/prototype-conformance` lisent chacun le manifeste par leur propre code.
- **Deux suites `ci: local-only` rouges sur `main` depuis #474** (bead af-b2kym7) : `tests/prototype-fidelity-demonstration-test.sh` (« the trial convoy could not be marked ») et `tests/ticket-graph-publish-new-flow-real-tracker-test.sh` (« the conformant draft was refused », publié mais non marqué). `lib/convoy_state.py` nomme à `gc` la cité du dépôt du script ; dans une cité d'essai au `HOME` isolé cette config ne se charge pas (`city.provider.toml` absent d'un worktree, puis packs non en cache). La CI ne lance pas ces suites. Non corrigé ici.

- **Le runner de CI de l'hôte tue des jobs jeunes** (bead af-7i1q2r) : le `Tests` rouge de cette PR sur f5987da (run 37939318451) n'est pas un test en échec. `runner-loop` a tué le conteneur 8 min 44 s après le début du job (« the job ran for more than 7200 s »), 2 h 01 après le démarrage du conteneur : son regard `sh -c 'pgrep -f Runner.Worker …'` trouve toujours sa propre ligne de commande et répond « busy » dès la première minute, donc la limite de #477 compte encore depuis le conteneur. Aucun test de ce changement n'a été jugé par ce run. Non corrigé ici ; le correctif demande une installation root (ADMIN).

### PR 479 — `do-work/af-fg8lhx`

**Non fait**

- `tests/acceptance-session-real-session-test.sh` (essai d'adoption hors CI, qui utilise le même pilote avec une vraie session de modèle) n'a pas été rejoué avec `ACCEPTANCE_SESSION_TRIAL_SESSION=1` : il dépense une session réelle.

**Écarts**

- Le résultat des parcours qui sortent 0 gagne deux champs (`interfaces.flow`, `author_gates`) : leur `oracle_digest` change, y compris pour `one-ticket-missing-condition`. Pour ce scénario de refus, `closed`, `ticket_end`, `lifecycle`, `observations` et la condition manquante sont identiques à avant ; seuls ces deux champs et l'empreinte diffèrent. `one-ticket-closed-by-hand` est identique octet pour octet (sortie 1, même message).
- `interfaces.flow` liste les commandes que le pilote exécute par le répertoire remis par l'oracle. Les commandes que `bin/convoy-advance` appelle lui-même (`ticket-end`, `code-review`, `ticket-evaluation`, …) n'y figurent pas : elles ne sont pas des portes de l'auteur et l'oracle les lit déjà par leur état.
- Le critère du ticket parcouru change : pour qu'un vrai `tdd-step red` soit rouge au commit de départ, le ticket de la fixture fait nommer le jeu de données par `/health` (champ `dataset`), sur les deux projets. La page d'accueil et le Validated Prototype ne changent pas. Le test de critère du ticket de réparation interroge `GET /items`, que le pilote déclare comme point d'entrée du profil pour les scénarios publiés par la porte.
- Scénario `three-failures-parked` : la session d'auteur qui échoue prend maintenant son ticket par `ticket-author start` (elle écrivait sa session par `convoy-state set-session`). Le ticket malade a donc une branche et un worktree ; le résultat du scénario est le même.
- Le pilote n'importe plus `tests/lib/ticket_proofs.py` ; ce module reste inchangé pour les autres suites.

**Constats hors ticket**

aucun

### PR 480 — `do-work/af-8o4jcp`

**Non fait**

aucun

**Écarts**

- « L'enregistrement du profil » : `bin/project-planning-profile register` lit le Planning Profile, qui ne porte pas de bloc `launch`. Le refus du profil sans jeu de données est donc porté par `describe`, `list` et par chaque outil qui charge le descripteur, pas par `register`.
- La règle d'import (`launch.import_rule`) reste déclarée une fois par profil : tous les seams en mode règle d'import partagent la même règle. `red_error_types` reste aussi commun à tous les seams.
- `seam_mode` reste accepté comme forme courte (un seul seam sur tout le périmètre) : les profils existants ne changent pas. Un profil déclare exactement l'un de `seam_mode` et `seams`.
- `bin/tdd-step` ne refuse pas lui-même l'absence de `--dataset` : il la transmet à `bin/project-launch`, qui refuse ; `tdd-step` refuse alors à son tour (« le produit n'est pas en bonne santé … ») en citant la raison. Seule exception inchangée : au rouge d'un ticket qui établit la recette de lancement, l'échec du lancement est attendu.

**Constats hors ticket**

- `bin/outcome-evaluation` (ligne 445) et `bin/outcome-promote` (ligne 326) gardent un repli « aucun jeu de données » (`or [None]`). Il n'est plus atteignable — le profil est refusé avant, et `bin/project-launch` refuse sans `--dataset` — mais le code mort reste.
- Les messages de refus de `bin/project-launch` et de `bin/project-planning-profile` sont en anglais ; ceux des outils qui les relaient à Benjamin sont en français.

### PR 483 — `do-work/af-rqgtpi`

**Non fait**

aucun

**Écarts**

- Le Handoff d'une sortie « Planning Exception » a ses quatre rubriques mais reste enregistré `partial: true` : les portes qui suivent (`bin/ticket-end`, `bin/code-review`, `bin/ticket-evaluation`, `bin/spec-integration`, `bin/correction-round`) lisent `partial: false` au commit de tête comme le compte rendu d'un ticket terminé ; un ticket parqué ne doit pas être lu ainsi.
- Conséquence du Handoff obligatoire : la sortie « Planning Exception » exige maintenant `--repo`, donc un travail commité sur la branche du ticket (règle déjà en vigueur pour tout Handoff). Les trois autres appelants de cette sortie dans les tests (`tests/ticket-author-test.py`, `tests/prototype-fidelity-test.py`, `tests/ticket-author-isolated-city-test.sh`) passent désormais un Handoff ; la formule `mol-ticket-author` le dit à l'auteur.
- « Mentionne l'ancre » est lu comme : le nom de l'ancre apparaît, entier, dans une ligne de la rubrique « Écarts » (`fixture-items-bis` ne vaut pas `fixture-items`).

**Constats hors ticket**

- `bin/ticket-exit` : pour `operator_request`, la demande part et le ticket est parqué avant que le Handoff partiel soit écrit ; un refus des relevés à ce moment laisse la demande posée sans Handoff (la réponse dit ce qui a été écrit, le même appel le complète). Non touché ici : la Spec n'ordonne que la Planning Exception.

### PR 484 — `do-work/af-kwodm8`

**Non fait**

- Le critère 3 (texte de la formule) n'a aucun test, comme le ticket le prévoit : il se vérifie par lecture à la revérification de T32.
- Pas d'essai en cité isolée : le ticket ne dépend d'aucun mécanisme de Gas City (seul le texte de deux étapes de la formule change) ; la formule modifiée a seulement été relue par un parseur TOML.

**Écarts**

- « La commande de régression n'exécute aucun test » est constaté sur les fichiers, pas sur l'exécution : une `regression_command` est opaque et ne rend aucun compte de tests. Le contrôle est donc « aucun fichier du périmètre de test au commit de départ, harnais gelé mis à part » (Spec §5 : « tests de caractérisation d'abord s'il n'y en a aucun »). Un périmètre qui contient un fichier que la commande n'exécute pas n'est pas vu. C'est ce qui a fait échouer la CI : un cache de bytecode committé dans le périmètre comptait comme un test.
- Des tests de caractérisation ajoutés dans le même commit que le changement sont refusés (rien ne prouve qu'ils passaient avant) : le ticket ne décrit que le cas du commit séparé.

**Constats hors ticket**

- Cinq autres suites copient la fixture entière sans écarter `__pycache__` (`tests/fixture-second-project-test.py`, `tests/ticket-author-test.py`, `tests/test-review-test.py`, `tests/ticket-exit-test.py`, `tests/prototype-fidelity-test.py`) : elles passent aujourd'hui, mais leur dépôt d'essai dépend de ce que les autres suites ont laissé dans la fixture. Non corrigé ici.

### PR 485 — `do-work/af-o6tu3z`

**Non fait**

- Le classement « repaired » d'un constat hors ticket (`bin/convoy-state classify-finding`) et le repair rédigé par le relecteur de fin (`bin/spec-end-review`) ne lisent toujours contre leur source, au moment de l'enregistrement, que `user_story` et `spec_line`. Une ancre, une règle ou un contrôle rouge cité là n'est refusé qu'à la publication du repair par la porte de patch. Rien n'est publié comme réparation sans vérification, mais le refus arrive une passe plus tard.
- Le critère « après une nouvelle approbation de la Spec amendée et un patch du graphe : résolue » est prouvé en deux moitiés, pas en un seul parcours : la porte de patch écrit le digest de la Spec amendée sur le convoi (`test_an_approved_patch_writes_the_digest_of_the_amended_spec_on_the_convoy`), et `resolve-exception` passe quand ce digest a changé (`tests/owner-answer-test.py`, où le digest est posé sur le convoi par le test). Aucune fixture ne porte à la fois un convoi publié par la porte et un Outcome Delivered.

**Écarts**

- **Champ ajouté à `bin/convoy-state`** : `gc.flow.blocking_red` sur le ticket (`record-blocking-red`, `clear-blocking-red`). Sans lui, la sortie « bloqué technique » de `bin/ticket-exit` (T11) dont le repair cite un contrôle rouge aurait été refusée par la porte : rien n'enregistrait ce rouge. La sortie l'enregistre avant le patch et le retire si la porte refuse. Limite : ce rouge est celui que l'auteur déclare, aucun code ne le constate.
- **`convoy.red_checks`** est ajouté à `bin/convoy-state show` (dérivé à chaque lecture, stocké nulle part) : rouge de la branche d'intégration, panne de l'Acceptance Session, rouge d'un bloqué technique, éléments suivis à réparer.
- **Repair d'un rouge de fidélité** : il citait `anchor` avec le texte du contrôle, ce qui n'est le nom d'aucune ancre. Il cite maintenant `red_check` avec le contrôle enregistré, et reste un ticket d'interface (la porte le reconnaît au `check: fidelity` du rouge).
- **Repair des éléments suivis** : sa citation nomme les identifiants des éléments (`deviations.1`), plus leur texte ; le texte reste dans « ce qu'il livre ».
- **Formats fixés ici**, la Spec ne les donnant pas : `anchor` = le nom d'une seule ancre ; `repo_rule` = `<chemin> : <règle mot pour mot>`. Les formules `mol-end-review` et `mol-outcome-evaluation` le disent aux agents.
- **Digest comparé** : celui que le convoi porte (`gc.spec_digest`, écrit par la porte de patch depuis la Spec approuvée), pas `approved_digest` lu sur le bead de la Spec. Il ne change que lorsque la Spec amendée est approuvée **et** le graphe révisé publié, ce que demande la Spec §11. Une Planning Exception sans digest (levée avant ce ticket, ou convoi sans `gc.spec_digest`) se résout sur les mots seuls, comme avant.
- **Prototype illisible** (commit absent du dépôt et de `origin`) : la porte refuse le repair, et `owner-answer record` refuse la réponse entière plutôt que de router le constat en Planning Exception sur une citation qu'il n'a pas pu lire.
- **Première publication** (`bd-publish`) : les mêmes contrôles s'y appliquent ; `repo_rule` est lu à la pointe de la branche protégée (la branche d'intégration n'existe pas encore) et un `red_check` y est toujours refusé (pas encore de convoi).
- Hors des chemins de scope, pour le câblage : `bin/prototype-conformance`, `bin/owner-answer`, `bin/convoy-advance`, `bin/ticket-exit`, le faux `gc` des tests de publication (`--unset-metadata`, comme le vrai).

**Constats hors ticket**

- `tests/spec-end-review-test.py` rédige un repair `repo_rule` dont `ref` est la règle seule, sans fichier : `bin/spec-end-review record` l'accepte, et la porte de patch le refusera désormais à la publication. Le relecteur a pourtant le chemin dans `citation.path` ; `spec-end-review` pourrait composer ou exiger `<chemin> : <règle>` dès l'enregistrement.
- `docs/OWNER_ANSWER.md` (« Limits ») : rien n'empêche toujours un agent de passer le nom de Benjamin dans `--approved-by` ; inchangé par ce ticket.

### PR 486 — `do-work/af-i2lckq`

**Non fait**

aucun

**Écarts**

- Le ticket ne nommait que `security-review`. L'essai réel a montré une seconde source de skills de revue (les plugins du compte claude.ai) ; elle est fermée dans ce ticket pour le relecteur et l'Evaluator, parce que le critère « aucun skill de revue ne se lance » chez l'Evaluator était faux sans cela.
- `check` refuse aussi un relevé qui ne dit pas quels skills de revue se sont lancés. Les trois relevés versionnés le disent.

**Constats hors ticket**

- Le relevé de l'auteur date du 2026-10-06 et reste valide (son empreinte n'a pas changé, son overlay coupait déjà la synchronisation). Il n'a pas été refait, conformément au ticket.
- La liste « skills de revue listés » repose sur la présence de « review » dans le nom du skill : un skill de revue nommé autrement ne serait pas vu comme tel par l'essai.
- Les rôles hors livraison (`factory-worker`, Mayor) reçoivent toujours les plugins du compte claude.ai (plus de 130 skills listés par session), ce qui pèse sur le contexte de chaque session.

### PR 487 — `do-work/af-m1iibk`

**Non fait**

- Tant que la branche d'intégration est rouge (seule sa réparation est reprise), un ticket `behind` n'est pas rendu à son auteur : la revue reste refusée (rapportée sous `code_review.behind`) jusqu'au retour au vert.
- `bin/ticket-evaluation` n'a pas de contrôle propre de la pointe d'intégration : la Ticket Evaluation est tenue hors de l'ancienne pointe par la reprise de la sortie « terminé », faite avant elle dans la même passe. Dans le cas ci-dessus (branche rouge), elle peut donc encore partir sur l'ancienne pointe.

- Aucun scénario ajouté à la Fixture City Oracle : le cycle (refus, retour à l'auteur, compteur) est prouvé par les tests de ligne de commande sur faux tracker et dépôt git réel (`tests/code-review-test.py`, `tests/convoy-advance-test.py`), pas par un parcours de la Fixture City.

**Écarts**

- Le refus porte sur l'envoi d'un relecteur, pas sur une revue déjà envoyée : une revue en cours quand la branche d'intégration avance est attendue (`pending`), son verdict reste recevable ; la fusion traite ensuite le conflit ou le rouge comme avant (cause `returned`). Choix fait pour ne pas consommer une reprise (K=3) sur chaque ticket en revue à chaque fusion d'un frère.
- La reprise `behind` est comptée même quand le plafond N de sessions est atteint (la session part à une passe suivante), à la différence des autres causes : c'est ce qui retient la revue et la Ticket Evaluation.
- Le tour de jugement (après correction) est soumis à la même règle que la revue : une correction faite sans reprendre la pointe coûte une reprise de plus.

**Constats hors ticket**

- Avec K=3 reprises toutes causes, un ticket terminé pendant que plusieurs frères fusionnent peut épuiser ses reprises sur la seule cause `behind` et être parqué. À observer sur la Fixture City ; non traité ici.

### PR 488 — `do-work/af-7y457s`

**Non fait**

aucun

**Écarts**

- Pas d'essai en cité isolée (`gas_city_first`) : le ticket ne dépend d'aucun mécanisme de Gas City nouveau. La remontée passe par `bin/escalation-door benjamin` et `bin/convoy-state stop-raised`, déjà employés tels quels par `bin/code-review`, `bin/test-review`, `bin/ticket-evaluation` et `bin/correction-round`.
- La demande propose deux options (« Faire reprendre ce ticket ou ses tests de critère par une Planning Exception », « Laisser le ticket arrêté ») ; aucune ne lève l'arrêt par code : la Spec ne fixe pas de levée pour cet arrêt, et les autres arrêts de ticket n'en ont pas non plus (`docs/FACTORY_TOOLS.md` : « rien ne lève encore un arrêt »).

**Constats hors ticket**

- L'arrêt `criterion_already_green` (critère déjà vert au départ, user story 26 : « arrête le ticket et remonte ») est inscrit par `bin/tdd-step red` de la même façon et n'est remonté par personne non plus : aucun outil n'appelle `stop-raised` pour cette raison. Même défaut que celui de ce ticket, non corrigé ici (hors de la ligne de démonstration de T45). La réparation serait une entrée de plus dans `TDD_STOPS` de `bin/convoy-advance`, avec son texte de demande.
- `Convoy.not_started()` de `bin/convoy-advance` ne regarde pas l'arrêt : un ticket arrêté sans avoir été démarré par la porte serait démarré. Le cas ne se produit pas aujourd'hui (`bin/tdd-step` ne tourne que dans la session d'un ticket démarré), non vérifié au-delà de la lecture du code.

### PR 489 — `do-work/af-1zxao6`

**Non fait**

- Les arêtes déjà posées à l'envers dans le tracker live (patch af-o8g4mo : T39 attend T40, T40 attend T46) ne sont pas réparées par cette PR : c'est une écriture dans la cité live, hors de ce ticket. Tout ticket ajouté par patch avant cette fusion avec un `blocked_by` non vide est à relire de la même façon.

**Écarts**

- Dans l'essai réel, la passe de `bin/convoy-advance` tourne dans une cité sans agent ni contrôleur : la porte de dispatch refuse les tickets qui pouvaient démarrer (RA compris, `refused`), elle n'en démarre aucun. Ce que l'essai prouve est la décision de la passe sur le ticket bloqué (laissé en attente « bloqué par RA », jamais présenté à la porte), pas un démarrage réel de RA.
- Le faux `bd` ne retient toujours pas les arêtes `blocks` de la transaction `create --graph` (publication d'un graphe neuf) : les retenir changerait ce que voient les suites existantes du nouveau flux, hors de ce ticket.

**Constats hors ticket**

- **Ancien flux, ticket ajouté par patch et convoi.** La porte crée ce ticket avec `--deps tracks:<convoi>` : sur bd 1.2.2 c'est le ticket qui « suit » le convoi, pas le convoi qui suit le ticket (relevé de l'essai : `arêtes tracks de B : [convoi] ; du convoi : [A]`). Le convoi de l'ancien flux ne liste donc pas le ticket ajouté parmi ce qu'il suit. Le nouveau flux pose déjà l'arête dans le bon sens (`bd dep add <convoi> <ticket> --type tracks`). Non corrigé ici : comportement de l'ancien flux, à décider à part.
- **`bin/convoy-state` et la cité visée.** Appelé par la porte sans `FACTORY_ROOT`, `bin/convoy-state` lance `gc --city <racine de l'outil>`. Mon essai, lancé depuis un worktree, a d'abord échoué là-dessus (`city.provider.toml` absent) ; il exporte maintenant `FACTORY_ROOT=<cité jetable>`. `tests/ticket-graph-publish-new-flow-real-tracker-test.sh` ne pose pas `FACTORY_ROOT` : je ne l'ai pas relancé, donc je ne sais pas s'il passe encore, ni quelle cité il atteint quand il est lancé depuis la racine live.

### PR 490 — `do-work/af-rc0ozs`

**Non fait**

aucun

**Écarts**

- Le jugement rendu par la session qui a fait la revue était refusé par un contrôle propre à `record-code-review` (« une seconde session relecteur juge les réponses »). Ce contrôle est retiré : le refus général de la session qui a déjà servi le couvre. Le jugement reste refusé, avec le message général (« une session neuve par relecture, revue ou évaluation »), et son lancement est désormais compté sans résultat.
- Les harnais de tests existants enregistraient plusieurs relectures d'un même convoi sous un seul nom de session : chacun donne maintenant un nom propre à chaque enregistrement.

**Constats hors ticket**

- Les enregistrements au niveau du convoi (`bin/spec-end-review`, `bin/outcome-evaluation`) ne sont pas couverts par le refus : le critère nomme trois portes.
- Les autres essais en cité isolée construisent leurs propres agents `trial-*`, avec leurs propres plafonds : ils ne prouvent rien sur la configuration livrée.
- Relecteur et Evaluator restent plafonnés à une session : une relecture attend que la session précédente soit partie. Une session qui ne part jamais tient la place jusqu'à `idle_timeout` (2 h), au-delà de `timeout_seconds` (1800 s / 3600 s) : la relecture suivante serait alors comptée sans résultat.
- L'essai d'adoption du rôle Evaluator (`bin/role-adoption-trial run`) échouait sur cet hôte indépendamment de ce ticket : les plugins Claude installés dans `/home/benja/.claude` faisaient lister à la session des skills de revue (`engineering:code-review`, `design:accessibility-review`, …) et lui laissaient lancer `code-review` (133 skills listés). Benjamin a choisi (réponse b sur af-rc0ozs, 2026-10-09) que le fournisseur en lecture seule ignore les plugins de l'hôte : c'est T47 (af-i2lckq, PR #486, fusionnée). Cette branche reprend `main` après cette fusion et rejoue les essais sur la distribution de T42 : relecteur réussi le 2026-10-09T20:09:56Z (9 skills listés, `code-review` seul lancé), Evaluator réussi le 2026-10-09T20:11:46Z (8 skills listés, aucune revue lancée), auteur réussi le 2026-10-09T16:46:19Z ; `bin/role-adoption-trial status` : trois `ok`, relevés dans `config/role-adoption-trials.json`.

### PR 491 — `do-work/af-ea93m9`

**Non fait**

aucun

**Écarts**

- Le ticket nomme `bin/ticket-graph-publish` comme seul chemin de scope ; `bin/ticket-exit` et
  `bin/convoy-advance` sont modifiés d'une ligne chacun (liste vide dans la révision de `repair` qu'ils
  construisent), au titre du contrat de branchement. Ces révisions ne déclarent aucun besoin : un `repair`
  mécanique qui aurait besoin de l'opérateur passe par l'escalade, pas par ce brouillon.
- Fixtures de brouillon au contrat complétées par `operator_needs: []` (brouillon de la Fixture City,
  brouillon du relecteur de graphe, pilote de la Fixture City, essai `spec-end-review`).

**Constats hors ticket**

- `tests/ticket-graph-publish-new-flow-real-tracker-test.sh`, lancé depuis un worktree : après la publication
  du brouillon conforme, la pose de la marque échoue (`gc bd: loading config: loading fragment
  "city.provider.toml": open <worktree>/city.provider.toml: no such file or directory`) et l'essai s'arrête sur
  « the conformant draft was refused ». La publication n'exporte pas `FACTORY_ROOT` vers la cité jetable, donc
  `bin/convoy-state` lit la racine de l'outil ; le fichier n'existe que dans la racine live. Sans rapport avec
  ce ticket ; relève de T49 (af-xcfup7, en cours). Un premier lancement avait échoué plus tôt, à `gc init`, sous
  forte charge de la machine (non reproduit à la main).

### PR 494 — `do-work/af-yorkna`

**Non fait**

aucun

**Écarts**

aucun

**Constats hors ticket**

aucun

### PR 495 — `do-work/af-6h09r6`

**Non fait**

aucun

**Écarts**

- La comparaison est entière des deux côtés : `page.fixture` et `page:fixture` ne nomment plus `fixture` (avant, seul « - » ou « _ » à gauche l'empêchait). Le ticket ne décrit que le côté droit ; c'est la même règle « le nom apparaît, entier ».
- Un nom d'ancre suivi d'un « . » ou d'un « : » collé à la suite de la phrase sans espace (`fixture.Ensuite`) n'est plus lu comme l'ancre `fixture` : rien ne le distingue d'une autre ancre.

**Constats hors ticket**

- `bin/convoy-state` accepte un nom d'ancre qui finit par « . » ou « : » (`fixture.`). Dans une phrase, un tel nom ne se distingue pas de `fixture` suivie d'une ponctuation : une Planning Exception qui nomme `fixture` est acceptée si « Écarts » ne cite que l'ancre `fixture.`. Non corrigé ici (la forme des noms d'ancre est fixée ailleurs).

### PR 496 — `do-work/af-xcfup7`

**Non fait**

- `bin/local-only-tests` n'a pas été lancé en entier d'un seul trait depuis `main` : la ligne de démonstration (sortie 0 sur `main`) ne s'observe qu'après fusion, au premier lancement de nuit (04:00) ou à la main. Chaque fichier qu'il lance a été lancé seul, résultats ci-dessus.
- Le critère « sur un hôte au repos » n'a pas pu être tenu : l'hôte n'a jamais été au repos (charge 7 à 43). Les cinq essais sortent 0 sous cette charge.

**Écarts**

- Le `timeout` de l'ordre est `6h`, alors que l'essai Gas City a porté sur `3h` (même forme de durée, survie au-delà de 300 s prouvée) : la mesure de la nuit entière (plus de deux heures sous charge) est venue après l'essai.
- `acceptance-session-real-session`, `spec-end-review-real-session` et la partie 2 de `graph-review` ne sont pas dans la liste d'exclusions : sans leur variable d'environnement ils ne lancent aucune session de modèle, le disent et sortent 0. Ils tournent donc la nuit sans leur partie réelle. Seul `convoy-stop-mayor-isolated-city` est exclu (vraie session du Mayor à chaque lancement).
- Trois essais hors des douze nommés ont été réparés ou adaptés (`graph-review`, `cockpit-fake-gc-contract`, `local-only-tests-order`) : sans cela `bin/local-only-tests` ne sort pas 0.

**Constats hors ticket**

- `bin/local-only-tests` ne prend pas le verrou de batterie : la nuit peut tourner en même temps qu'une batterie de CI sur le même hôte.
- `bin/role-adoption-trial` laisse `~/.local/share/af-role-trial` en place entre deux lancements ; `spec-end-review-real-session` (avec session réelle) et `convoy-stop-mayor-isolated-city` refusent de démarrer tant qu'il existe.
- Les essais d'ordre (`backup-freshness`, `factory-orphan-sweep`, `factory-session-loop-guard`, `factory-watchdog`, `local-only-tests`) échouent depuis tout work tree : chemin de l'usine écrit en dur dans les ordres.
- `test-review-isolated-city`, sous charge : un même bead de relecture a été pris par deux sessions de relecteur du pool (vu deux fois). L'essai ne le compte plus comme un lancement ; la double prise elle-même, côté Gas City, n'est pas expliquée.
- L'hôte porte en permanence une charge de 10 à 55 (runner de CI et workers) ; les essais en cité isolée y prennent 8 à 19 minutes chacun.

### PR 499 — `do-work/af-ezqgma`

**Non fait**

aucun

**Écarts**

- Changement de comportement de `bin/spec-approve` : une `APPROVED_SPEC` dont le texte a changé est approuvée de nouveau (avant : toujours refusée). C'est ce qu'exige la ligne de démonstration du ticket et la Spec §11 ; la réapprobation passe par les mêmes contrôles qu'une première approbation (Reservation comprise) et ne referme pas la carte.
- Le test unitaire existant de `tests/owner-answer-test.py` (`amended_spec_published`) pose toujours `gc.spec_digest` à la main : il reste un test unitaire de la porte ; la preuve du critère est le nouveau parcours.
- La Spec du pilote de la Fixture City (`story-not-observed`) nomme maintenant la branche `prototype/delivery-fixture-city` au lieu de `main@base`, que `bin/spec-approve` refuse.
- Dans le parcours, le texte de la Spec est amendé par `bd update --description` et le brouillon révisé (déjà approuvé) est déposé dans le tracker par le test, comme le laisse un Planning Run : ce ne sont ni `gc.spec_digest` ni l'approbation de la Spec.

**Constats hors ticket**

- `tests/ticket-graph-publish-coverage-test.py` (`amend_spec` / `spec_bead`) écrit l'approbation de la Spec à la main.
- `tests/evidence-pack-test.py` pose `gc.spec_digest` à la main dans son état de départ.
- L'entrée du catalogue `bin/owner-answer` disait encore que `resolve-exception` valait aussi pour un « souhait abandonné », ce qui n'est plus vrai depuis T40 : corrigé ici.

