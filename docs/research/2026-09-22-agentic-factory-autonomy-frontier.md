# Frontière d'autonomie d'une software factory agentique solo

**Evidence as of:** 2026-09-22

**Décision visée:** où placer l'intervention humaine dans le flux SayMyName, de l'intention au déploiement.

**Contexte d'application:** produit solo, codebases brownfield Backend/Frontend, Factory locale Gas City + Beads/Dolt + GitHub, stade `pre_production`, données personnelles réelles confinées à la base locale.

## Verdict

La recommandation initiale — compréhension partagée approfondie, puis approbation d'un contrat consolidé, puis autonomie jusqu'au résultat sauf décision sensible ou irréversible — est **une bonne base, mais elle est trop large pour devenir la règle générale aujourd'hui**.

La meilleure synthèse des sources récentes pour SayMyName est plutôt :

> **Benjamin reste propriétaire du quoi, du pourquoi, des critères de réussite et de la validation du résultat. L'agent peut devenir autonome sur le comment, mais dans des tranches verticales bornées, observables et réversibles. La profondeur des revues humaines diminue seulement après preuve locale de fiabilité; elle remonte dès que le risque, la nouveauté ou l'incertitude augmentent.**

La frontière recommandée n'est donc ni « humain à chaque étape » ni « un seul feu vert puis lights-off ». C'est une **autonomie progressive avec trois points d'ancrage humains** :

1. **avant la fabrication**, validation du contrat produit et, pour un changement important, des frontières d'architecture et de programme;
2. **pendant la fabrication**, revue adaptative aux frontières des premières tranches ou des tranches risquées;
3. **après la fabrication**, validation du comportement utilisateur et de l'acceptation avant toute exposition réelle ou déploiement.

Pour les petits changements familiers, entièrement réversibles et couverts par des oracles déterministes, ces trois ancrages peuvent se contracter en une seule demande et une validation rapide du résultat. Pour une évolution importante, une migration, un flux de données personnelles ou une nouvelle architecture, ils ne doivent pas être supprimés.

## Ce que les sources établissent — et ce qu'elles n'établissent pas

Il n'existe pas, dans les sources consultées, d'essai contrôlé comparant plusieurs frontières d'autonomie sur des projets solo brownfield à long terme. Les prescriptions les plus précises viennent surtout de retours d'expérience first-party. Il faut donc distinguer :

- **Preuve observationnelle:** l'étude Anthropic de juin 2026 analyse environ 400 000 sessions Claude Code. Dans une session typique, les humains prennent la majorité des décisions de planification (« quoi faire »), Claude la majorité des décisions d'exécution (« comment »); davantage d'expertise de domaine est associé à davantage de succès. C'est le signal empirique le plus large, mais il ne prouve pas causalement qu'un gate particulier est optimal.
- **Retours d'expérience:** HumanLayer décrit l'échec de sa propre expérimentation « lights-off »; OpenAI décrit au contraire une équipe ayant atteint l'implémentation, la revue et le merge autonomes dans un repository greenfield construit dès le départ pour les agents; Matt Pocock décrit son workflow personnel; Cursor et Anthropic publient leurs pratiques et données internes de sécurité. Ils prouvent que ces modes existent et relatent leurs conditions, pas qu'ils se généralisent.
- **Artefacts exécutables:** Sandcastle encode des pipelines séparant planification, implémentation, revue et merge, avec branches/sandboxes isolées. C'est une preuve du design du workflow, pas une mesure de sa qualité à long terme.
- **Inférence pour SayMyName:** la recommandation ci-dessous est la combinaison prudente de ces signaux avec le contexte du projet. Elle reste à valider par des métriques locales.

## Comparaison des positions first-party

| Source | Ce qu'elle soutient directement | Nature du signal | Applicabilité à SayMyName |
|---|---|---|---|
| [Matt Pocock — AI Coding Workflow](https://www.ai.engineer/talks/-QFHIoCo-Ko-ai-coding-workflow) | Interview « Grill Me » avant PRD, issues en tranches verticales, TDD et boucles de feedback pendant l'implémentation, contexte frais pour la revue, humain responsable de la QA et de la code review. | Retour de pratique / conférence, date de publication non indiquée sur la page. | Forte pour un développeur solo; pas une étude comparative. |
| [Matt Pocock — Software Fundamentals Matter More Than Ever](https://ai.engineer/talks/v4F1gFy-hqg-software-fundamentals-for-ai-coding) | Compréhension partagée et langage commun avant le plan; le modèle est un programmeur tactique, l'humain reste le designer stratégique; interfaces conçues humainement, feedback et TDD fréquents. | Retour de pratique / conférence. | Forte pour la propriété du design, sans définir tous les gates opérationnels. |
| [Sandcastle](https://github.com/mattpocock/sandcastle) et son [template planner + review](https://github.com/mattpocock/sandcastle/tree/main/src/templates/parallel-planner-with-review) | Isolation, branches distinctes, une itération bornée; template officiel `plan -> parallel implement -> review -> merge`; supports Beads. | Artefact logiciel first-party, observé sur `main` le 2026-09-22. | Forte pour la mécanique d'exécution; ne décide pas qui, humain ou agent, doit approuver. |
| [Dex Horthy / HumanLayer — Why Software Factories Fail](https://github.com/humanlayer/advanced-context-engineering-for-coding-agents/blob/main/wsff.md) | Retour d'échec d'une factory lights-off; réintroduit la revue humaine du code et concentre l'effort en amont sur Product Requirements, System Architecture, Program Design et Vertical Slices; recommande de revoir 1–3 tranches à la fois et d'ajuster l'intensité selon la taille. | Postmortem et prescription first-party, juillet 2026. | Très forte : brownfield, long terme et maintenabilité ressemblent davantage à SayMyName qu'à un prototype jetable. |
| [HumanLayer — Advanced Context Engineering](https://www.humanlayer.dev/blog/advanced-context-engineering) | Flux research/plan/implement, plan précis avec vérification par phase, revue humaine à fort levier sur recherche et plan; avertit qu'une mauvaise recherche contamine le plan puis beaucoup de code. | Retour de pratique first-party, 2025-08-29. | Forte pour la forme du travail, mais le cas est une équipe et non un fondateur solo. |
| [OpenAI — Harness engineering](https://openai.com/index/harness-engineering/) | Dans un repository agent-first, les humains priorisent, traduisent le feedback en critères et valident les résultats; les agents peuvent ensuite implémenter, vérifier, répondre aux reviews et merger, en n'escaladant que le jugement. OpenAI avertit que cela dépend fortement de la structure et de l'outillage spécifiques du repository. | Retour d'expérience first-party, 2026-02-11. | Signal favorable à une autonomie élevée, mais transférabilité moyenne/faible : équipe, greenfield, investissement massif dans le harness, produit interne/alpha. |
| [OpenAI — Symphony](https://openai.com/index/open-source-codex-orchestration-symphony/) | Les humains revoient les résultats plutôt que les sessions; pour migrations/features complexes, un agent produit d'abord un plan, puis seulement une fois l'humain satisfait il génère un DAG dont les tâches débloquées s'exécutent seules. Les travaux ambigus ou à fort jugement restent interactifs. | Retour first-party et spécification OSS, 2026-04-27. | Très forte pour le Mayor et Beads : plan approuvé, exécution par graphe, revue de livrables; le cas reste celui d'un harness agent-first mûr. |
| [Anthropic — Agentic coding and persistent returns to expertise](https://www.anthropic.com/research/claude-code-expertise) | Sur ~400 000 sessions, les humains font typiquement le planning et Claude l'exécution; l'expertise de domaine reste corrélée au succès. | Étude observationnelle first-party, 2026-06-16. | Forte pour séparer « quoi » et « comment »; ne mesure pas la maintenabilité différée. |
| [Cursor — Best practices for coding with agents](https://cursor.com/blog/agent-best-practices) | Pour les changements non triviaux : recherche, questions, plan révisable, approbation avant build; revue dédiée après génération; les petites tâches peuvent sauter le plan. | Guide first-party, 2026-01-09. | Forte comme défaut gradué par taille; probablement orientée usage interactif plutôt que factory nocturne. |
| [Cursor — Long-running agents](https://cursor.com/blog/long-running-agents) | Sur les tâches longues, une hypothèse initiale légèrement fausse amplifie les erreurs; l'agent propose donc un plan et attend son approbation avant l'exécution, puis utilise plusieurs agents pour vérifier le travail. Cursor rapporte des PR plus grandes avec un taux de merge comparable, sans publier ici de mesure de maintenabilité différée. | Research preview first-party, 2026-02-12. | Forte pour le gate upfront des tâches longues; prudence sur les conclusions qualité. |
| [Cursor — Governing agent autonomy with Auto-review](https://cursor.com/blog/agent-autonomy-auto-review) | L'autonomie doit être un continuum contextuel, pas un interrupteur global; laisser passer le faible risque, ralentir aux frontières significatives; tenter d'abord une voie plus sûre avant d'interrompre l'humain. | Retour de production sécurité, 2026-06-11; 6 122 cas labellisés, environ 7% des chats entraînant une interruption au moment publié. | Forte pour le principe d'escalade par effet; elle traite surtout la sécurité d'actions, pas la maintenabilité du code. |
| [Anthropic — Claude Code auto mode](https://www.anthropic.com/engineering/claude-code-auto-mode) et [sandboxing](https://www.anthropic.com/engineering/claude-code-sandboxing) | Les approbations systématiques causent de la fatigue; préférer sandbox, frontières explicites et contrôle contextuel des actions risquées. Anthropic rapporte 93% d'approbation des prompts dans son échantillon et une réduction de 84% des prompts avec sandboxing. | Données et architecture sécurité first-party, 2025-10-20 et 2026-03-25. | Forte pour les permissions d'outils; ne justifie pas l'autonomie de décision produit/architecture. |

## Frontière recommandée, phase par phase

| Phase | Rôle de Benjamin | Autonomie agentique recommandée | Gate |
|---|---|---|---|
| **Intent / shared understanding** | Exprime le problème, répond aux décisions que les faits ne peuvent trancher, confirme la synthèse. | Explorer les faits, interroger, expliciter les hypothèses, produire l'arbre de décisions. | **Obligatoire** pour tout outcome nouveau ou ambigu. Aucun code avant confirmation. |
| **Product design** | Possède le résultat utilisateur, les non-objectifs, les compromis métier et les critères observables. | Proposer options, mocks, scénarios, risques et recommandation depuis la base durable. | **Obligatoire** si le comportement utilisateur, la portée ou les critères changent; contractable pour correction évidente. |
| **System design** | Valide les frontières durables qui déterminent couplage, sécurité, données et évolutivité. | Rechercher le système existant et proposer une option réversible conforme aux invariants. | **Obligatoire au départ** pour toute nouvelle frontière de service, schéma, permission ou intégration; ensuite délégable aux patterns prouvés. |
| **Program design** | Contrôle initialement interfaces, types, responsabilités et sens des dépendances sur les changements significatifs. | Détailler call flows, API internes, tests comportementaux et alternatives. | **Obligatoire** pour gros changement ou module critique; revue légère/échantillonnée pour un pattern déjà prouvé. |
| **Vertical slicing** | Confirme que chaque tranche donne un résultat testable et que l'ordre réduit le risque. | Produire le graphe de dépendances, redécouper localement sans changer le contrat. | Validation du découpage initial; pas de nouvelle approbation pour un redécoupage plus petit dans les mêmes frontières. |
| **Implementation** | N'intervient pas sur les décisions tactiques ordinaires. | Autonome par tranche dans worktree/sandbox, avec tests comportementaux/TDD lorsque l'oracle existe, lint/typecheck, inspection runtime et budget de tentatives. | Pas de gate par commande. Pause uniquement sur déclencheur explicite ci-dessous. |
| **Review** | Conserve la compréhension du système. Examine le comportement et, selon le risque, le design/code. | Review agent indépendant et contrôles déterministes sur chaque tranche; correction autonome des constats objectifs. | **Humain adaptatif** : revue de chaque première tranche et de tout code critique; échantillonnage possible après historique vert mesuré. |
| **Merge** | N'approuve pas chaque merge faible risque si le contrat et les gates sont satisfaits. | Peut ouvrir, réparer et merger les PR réversibles après preuves et reviews. | Auto-merge seulement pour classes explicitement qualifiées; sinon revue humaine. |
| **Deploy / release** | Valide le résultat utilisateur; autorise toute entrée en pilote/production ou exposition externe. | Déploiement automatique en environnement isolé, smoke tests, preview et rollback préparé. | **Obligatoire** avant exposition de vraies personnes/données, publication, envoi, dépense ou production. |

### Conséquence pour la Q4

La réponse à valider devrait être reformulée ainsi :

> **Benjamin participe à une phase de compréhension partagée et valide un contrat consolidé. Ensuite, le Mayor exécute de façon autonome par tranches verticales. Au début de la refonte et pour les changements significatifs, Benjamin revoit aussi les frontières d'architecture/programme et les premières tranches, puis valide le comportement final. Ces revues deviennent échantillonnées ou disparaissent pour les classes faibles et prouvées; elles reviennent automatiquement quand un signal de risque apparaît.**

Autrement dit, la validation consolidée upfront est conservée, mais elle n'achète pas immédiatement une autonomie lights-off générale. Elle ouvre une **enveloppe d'autonomie locale**.

## Escalades : jugement, risque et sortie du contrat

Un agent ne doit pas demander l'autorisation pour chaque action. Il doit d'abord réduire l'action, choisir une voie sûre ou continuer ailleurs. Il escalade lorsqu'au moins un des cas suivants est vrai :

1. **Intent incertain:** deux interprétations plausibles changent le résultat utilisateur, les non-objectifs ou les critères de réussite.
2. **Sortie de contrat:** la solution exige d'élargir la portée, de modifier une frontière approuvée, de renoncer à un critère ou d'introduire une dépendance durable non prévue.
3. **Jugement non mécanisable:** choix d'architecture/program design dont le coût n'apparaîtra qu'à long terme et qui n'est pas réglé par un invariant ou un précédent approuvé.
4. **Effet sensible:** élargissement de l'accès aux données personnelles, secret/permission, argent, publication/envoi réel, production, destruction non récupérable ou migration non réversible.
5. **Preuve insuffisante:** impossibilité de créer un oracle crédible, résultat runtime ambigu, contrôles contradictoires ou absence d'accès à l'environnement nécessaire.
6. **Boucle en échec:** budget de tentatives consommé, même échec répété, agent confus ou correction qui grossit continuellement la tranche.
7. **Dérive détectée:** review indépendante, test utilisateur, incident ou métrique indiquant que la tranche passe les tests mais dégrade le comportement ou la maintenabilité.

Les cas 1–3 sont les ajouts importants par rapport aux quatre tests d'effet actuels de SayMyName. Ils ne doivent pas nécessairement réveiller Benjamin à chaque occurrence : le PO/Mayor peut trancher si la base durable contient déjà une décision applicable. Mais **aucun agent ne doit inventer silencieusement le sens, le contrat ou une nouvelle architecture simplement parce que l'action reste réversible**.

## Facteurs qui déplacent la frontière

La frontière se déplace vers **plus d'autonomie** lorsque :

- le travail répète un pattern déjà livré et documenté;
- des tests comportementaux, contrats, types, règles architecturales et previews donnent un verdict rapide et fiable;
- la tranche est petite, isolée, réversible et sans effet externe;
- les dernières tranches comparables ont passé review et production sans rework significatif;
- le repository est lisible par l'agent et les invariants sont exécutables.

Elle se déplace vers **plus de revue humaine** lorsque :

- le domaine, le flux utilisateur ou l'architecture est nouveau;
- le coût d'une mauvaise décision se manifeste après des semaines/mois plutôt que dans les tests;
- le changement traverse plusieurs couches, tenants ou frontières de données;
- l'oracle est subjectif (utilisabilité, cohérence produit, maintenabilité) ou absent;
- le code est brownfield, incohérent, peu testé ou mal documenté;
- l'effet est externe, difficilement réversible, sécuritaire ou lié à de vraies données;
- la Factory ou le modèle vient de changer et n'a pas encore été recalibré.

## Adoption progressive proposée

1. **Calibration:** pendant les premières tranches de la refonte, Benjamin valide le contrat, les frontières d'architecture/programme, lit les changements importants et valide le résultat. Capturer les causes de rework.
2. **Qualification par classe:** déclarer des classes comme « auto-exécutables » seulement après plusieurs succès comparables. Mesurer au minimum : rework humain, défauts échappés, rollback, dérive architecturale, temps jusqu'à preuve, et fidélité aux critères.
3. **Réduction des gates:** retirer la revue humaine de code sur les classes faibles et déterministes; garder review agent + CI + validation de résultat. L'auto-merge devient une propriété d'une classe prouvée, jamais un réglage global.
4. **Audit et ratchet:** chaque écart répétitif devient documentation, test, invariant ou outil; revue périodique de l'entropie. Une nouvelle frontière ou une rupture de série verte remet temporairement la classe en revue renforcée.

## Risques, inconnues et niveau de confiance

- **Risque principal:** confondre réussite immédiate des tests et maintenabilité. C'est précisément la limite signalée par HumanLayer, et les sources OpenAI ne démontrent pas encore une qualité pluriannuelle.
- **Risque inverse:** multiplier les approbations de faible valeur. Cursor et Anthropic montrent que les prompts systématiques créent de la fatigue et que les frontières contextuelles/sandboxées préservent mieux l'attention.
- **Inconnue:** aucune source ne donne le seuil empirique exact permettant à SayMyName de passer d'une revue exhaustive à un échantillonnage. Ce seuil doit venir de données locales.
- **Confiance: moyenne-haute** sur le principe « humain quoi/pourquoi + agent comment dans une enveloppe vérifiable »; **moyenne** sur la cadence précise des gates, faute d'étude causale et parce que les cas publiés divergent fortement.

## Décision suggérée

**Conserver** la recommandation Q4 comme direction, mais la préciser par une rampe de confiance :

- contrat consolidé humain avant exécution;
- autonomie agentique par tranche verticale;
- revue humaine d'architecture/programme et des premières tranches pour changements significatifs;
- validation humaine du comportement final;
- gates allégés uniquement par classe de travail après preuve locale;
- escalade non seulement sur l'irréversible/sensible, mais aussi sur la sortie de contrat et le jugement durable non couvert.

Cette position suit davantage le consensus applicable à un solo brownfield que le modèle OpenAI le plus autonome, tout en laissant une voie explicite pour atteindre ce niveau plus tard si le harness de SayMyName produit les mêmes conditions de preuve.

## Hypothèse de routage de la planification à vérifier

Le point d'entrée recommandé est provisoirement `grill-with-docs`, avec promotion vers Wayfinder lorsque le design tree ne tient plus confortablement dans une session saine. Wayfinder n'est pas le point d'entrée universel : son propre routeur le réserve aux efforts vastes et brumeux, même si son étape de charting possède une sortie rapide lorsque la voie est déjà claire.

Benjamin reste dubitatif sur ce choix : commencer systématiquement par Wayfinder pourrait peut-être mieux détecter une complexité initialement invisible. Ce doute est conservé comme une hypothèse à tester, pas comme une seconde règle concurrente.

La recommandation sera considérée comme confirmée si, sur des demandes réelles simples et complexes :

- `grill-with-docs` termine directement les demandes simples sans cérémonial inutile ;
- les demandes complexes sont promues vers Wayfinder avant compaction, perte de décisions ou dégradation visible du raisonnement ;
- la promotion conserve la destination, les décisions déjà prises et les termes du domaine sans réinterrogation substantielle ;
- aucun travail nécessitant plusieurs sessions n'est lancé prématurément vers `to-spec` ou l'implémentation.

Elle sera réexaminée si la promotion arrive régulièrement trop tard, perd du contexte, ou demande à Benjamin de diagnostiquer lui-même qu'un effort dépasse une session. Le candidat alternatif sera alors un point d'entrée Wayfinder systématique, mesuré sur les mêmes cas pour quantifier son surcoût sur les demandes simples.

**Source primaire :** [Wayfinder — sortie sans map lorsque la voie tient dans une session](https://github.com/mattpocock/skills/blob/c55ee46073ed923f86ce59a5eb3b6d895095d1b7/skills/engineering/wayfinder/SKILL.md#L273-L284) ; [Ask Matt — `grill-with-docs` comme entrée normale et Wayfinder réservé aux efforts trop grands](https://github.com/mattpocock/skills/blob/c55ee46073ed923f86ce59a5eb3b6d895095d1b7/skills/engineering/ask-matt/SKILL.md#L205-L231).

## Décision de session : une Spec approuvée, sans Release Contract distinct

Le résultat adapté de `to-spec` devient l'artefact canonique d'un outcome borné. La confirmation du Shared Understanding pendant le grilling autorise la même Spec à passer à l'état approuvé; Benjamin n'a pas à relire une synthèse générale qui n'introduit aucune information nouvelle. Une intervention humaine supplémentaire n'est requise que si la synthèse révèle une décision nouvelle, une perte de traçabilité, une contradiction ou un test seam non encore décidé.

Il n'existe donc pas de Release Contract distinct qui reformule la Spec. `to-tickets` part de l'Approved Spec, puis le Mayor matérialise les Beads. Si une release doit regrouper plusieurs Specs, son éventuel manifeste reste un index minimal de références et d'état, sans recopier leurs décisions, critères ou Work Graphs.

Cette décision cible la refonte et remet en cause ADR-0014; elle ne modifie pas encore le contrat JSON ni le runtime existants. Leur remplacement devra être matérialisé ultérieurement par une décision structurelle qui explicite la migration et la compatibilité.

**Source primaire :** [`to-spec` synthétise sans nouvel entretien et ne demande qu'une confirmation ciblée des test seams](https://github.com/mattpocock/skills/blob/c55ee46073ed923f86ce59a5eb3b6d895095d1b7/skills/engineering/to-spec/SKILL.md#L197-L209).

## Disclosure check

- [x] Les requêtes et extraits ne contiennent ni secret, ni credential, ni code privé, ni donnée client.
- [x] Les faits propres à SayMyName cités ici proviennent uniquement de sa documentation durable locale; aucune donnée de la base n'a été consultée.
