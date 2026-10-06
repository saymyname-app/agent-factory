# Cible d'observabilité déterministe pour une usine logicielle multi-agents

Document de recherche indépendant (aucune lecture du dépôt ni du code de la Factory).
Rédigé le 2026-10-06. Toutes les dates d'accès aux sources = 2026-10-06.

**Système visé (description neutre).** Un opérateur seul fait tourner une « usine » :
un orchestrateur LLM et des rôles ouvriers (auteur, relecteur, évaluateur) livrent du
code dans des dépôts produits. Le travail est un graphe de tickets (« beads »,
dépendances, frontière prête), regroupés en « convois » par spec approuvée. Le code
arrive par branches Git, PR GitHub, CI. Le tout tourne sur un PC personnel sous WSL
(aussi PC de jeu). Un runtime planifie des sessions (« ordres »), gère quotas et
bascule entre fournisseurs LLM, et escalade vers l'humain par une porte unique.
Principe : **le code décide et enregistre l'état ; les agents LLM n'écrivent jamais
l'état de coordination.**

**Observabilité déterministe (définition retenue).** Tout ce que du *code* (jamais un
LLM) capture, stocke, vérifie et expose sur la santé, la progression et la justesse de
l'usine : événements structurés, métriques, traces, invariants, pistes d'audit,
preuves d'achèvement, alertes, SLO, support de post-incident, coûts/quotas,
reproductibilité.

---

## 1. Méthode

### 1.1 Démarche

| Étape | Contenu |
| --- | --- |
| Axes | 8 axes imposés : fondations, agents LLM, moteurs de workflow, delivery/CI, cohérence, humain/escalade, coût/quotas, hôte local. |
| Recherche | WebSearch (mode standard) pour localiser les pages ; WebFetch sur chaque source primaire pour vérifier le contenu réellement affirmé. |
| Critère de confiance | **A** = source primaire officielle (spécification, doc éditeur, livre Google SRE, dépôt de référence). **B** = littérature praticienne reconnue (Fowler, Honeycomb, Grafana, PagerDuty). **C** = source secondaire ou non vérifiée directement (marquée « non vérifié »). Aucune capacité ne repose uniquement sur du C. |
| Ce qui n'a pas pu être vérifié | (1) Le Google Doc original de Rob Ewaschuk « My Philosophy on Alerting » (mur de connexion) : son contenu est repris via le chapitre 6 du SRE Book dont il est l'auteur. (2) La page « gen-ai-agent-spans.md » du dépôt OTel GenAI (404 au chemin essayé) : le README du dépôt et la page `/docs/specs/semconv/gen-ai/` ont été lus ; le statut de stabilité des conventions GenAI n'est **pas** confirmé par une source primaire (une source secondaire affirme une stabilisation en juin 2026 — non vérifié). (3) Deux pages GitHub Docs (workflow-runs) ont renvoyé 404 ; remplacées par la page « limits » et l'API Check Runs, vérifiées. |

### 1.2 Sources consultées (résumé ; liste complète en §5)

| Axe | Sources primaires lues (A) | Compléments (B) |
| --- | --- | --- |
| 1 Fondations | SRE Book ch. 6 (Monitoring Distributed Systems), ch. 15 (Postmortem Culture), Part III (hiérarchie Dickerson) ; SRE Workbook ch. 5 (Alerting on SLOs) ; OTel Logs Data Model ; OTel Semconv CI/CD | Grafana (méthode RED), Honeycomb (événements larges) |
| 2 Agents LLM | Dépôt OTel semantic-conventions-genai (README) ; OpenAI Agents SDK tracing ; Anthropic « Building effective agents » | Comparatifs Langfuse/Phoenix/LangSmith (C) |
| 3 Workflows | Temporal (observability, activity timeouts/heartbeats) ; Airflow metrics ; Argo Workflows metrics ; GitHub Actions limits ; GitHub Check Runs API | Fowler, Event Sourcing |
| 4 Delivery | DORA « four keys » (page datée 2026-01-05) ; SLSA v1.0 provenance et v1.1 levels ; GitHub Artifact Attestations | — |
| 5 Cohérence | Kubernetes API Conventions (spec/status, conditions, level-based) ; Principles of Chaos ; runbook Watchdog (prometheus-operator) ; healthchecks.io docs | — |
| 6 Humain | SRE Book ch. 6 (questions avant de pager) ; PagerDuty Alerting Principles ; PagerDuty Postmortems ; Etsy Debriefing Facilitation Guide | — |
| 7 Coût/quotas | Anthropic rate limits (en-têtes, 429, spend cap) ; OpenAI rate limits (en-têtes, backoff) | FinOps Foundation (C, presse) |
| 8 Hôte | Linux PSI (docs.kernel.org) ; Microsoft Learn `.wslconfig` (mis à jour 2026-09-16) | — |

---

## 2. Principes (10)

| # | Principe | Formulation opérationnelle pour l'usine | Source |
| --- | --- | --- | --- |
| P1 | **Le monitoring est le socle** de la fiabilité ; sans lui on « vole à l'aveugle ». | Aucune autre amélioration (réponse aux incidents, tests, capacité) ne tient sans télémétrie code-first. | SRE Book, Part III (hiérarchie de Dickerson) |
| P2 | **Symptômes d'abord, causes ensuite.** Alerter sur ce que l'utilisateur (ici l'opérateur) subit ; les causes servent au diagnostic. | Pager sur « convoi bloqué depuis X h », pas sur « un process a disparu ». | SRE Book ch. 6 (Ewaschuk) |
| P3 | **Quatre signaux dorés** : latence, trafic, erreurs, saturation — et saturation « presque problématique » mérite déjà une alerte. | Les appliquer à chaque file : ordres, tickets, PR, appels LLM. | SRE Book ch. 6 |
| P4 | **Chaque page doit être urgente, actionnable, visible par l'humain, non ignorable.** « Un alerte non testée équivaut à pas d'alerte. » | Toute alerte a un runbook et un test. | SRE Book ch. 6 ; PagerDuty Alerting Principles |
| P5 | **Alerter sur le taux de combustion du budget d'erreur** (multi-fenêtre, multi-burn-rate) plutôt que sur des seuils bruts. | Précision / rappel / délai de détection / délai de reset comme critères. | SRE Workbook ch. 5 |
| P6 | **État = journal d'événements rejouable** (event sourcing / event history). On peut reconstruire l'état à tout instant et auditer. | Le runtime écrit une histoire d'événements append-only ; les vues (dashboard, tracker) en dérivent. | Fowler, Event Sourcing ; Temporal Observability |
| P7 | **Observé ≠ désiré ; réconcilier en continu, par niveau et non par front.** Le statut porte des *conditions* typées (`type/status/reason/message/lastTransitionTime/observedGeneration`). | Un réconciliateur compare tracker, GitHub, runtime ; les écarts deviennent des conditions `Drifted=True`. | Kubernetes API Conventions |
| P8 | **Les événements larges et structurés sont la base** ; corréler logs↔traces par `TraceId/SpanId`. | Un événement par unité de travail avec des dizaines d'attributs, pas des lignes de texte. | OTel Logs Data Model ; Honeycomb |
| P9 | **La vérité de terrain vient de l'environnement, pas du modèle.** Un agent progresse par retours d'outils ; les conditions d'arrêt sont codées. | « Done » n'est accepté que sur preuve machine (CI verte, PR mergée, artefact attesté). | Anthropic, Building Effective Agents ; OpenAI Agents SDK Tracing |
| P10 | **Prouver la provenance de ce qui est livré** (attestation signée build→artefact) et mesurer la livraison (DORA). | Chaque livraison porte une attestation ; les 4 clés DORA + taux de retouche sont calculés par code. | SLSA v1.x ; GitHub Artifact Attestations ; DORA |

---

## 3. Cible par capacité

Jargon : **SLI** = indicateur de niveau de service (mesure) ; **SLO** = objectif sur
cet indicateur ; **budget d'erreur** = 1 − SLO, ce qu'on peut « dépenser » ;
**burn rate** = vitesse de consommation du budget ; **span** = segment temporel d'une
trace ; **condition** = assertion typée sur l'état observé ; **dead man's switch** =
alerte sur l'*absence* d'un signal attendu ; **PSI** = Pressure Stall Information
(temps passé par les tâches à attendre une ressource).

Niveaux : **E** = Essentiel (sans quoi les pannes historiques se reproduisent),
**R** = Recommandé, **A** = Avancé.

### 3.1 Événements & état

| ID | Capacité | Ce que le code doit capturer / vérifier / exposer | Pourquoi (risque couvert) | Niv. | Source(s) |
| --- | --- | --- | --- | --- | --- |
| T01 | **Journal d'événements append-only du runtime** | Chaque transition (ordre créé/démarré/terminé/expiré, ticket changé d'état, convoi ouvert/fermé, escalade ouverte/résolue, bascule de fournisseur) écrite comme un événement immuable : horodatage source, horodatage d'observation, type, identifiants (ordre, ticket, convoi, PR, session), acteur (code/humain, jamais LLM), payload structuré. Rejeu possible pour reconstruire l'état courant. | Dérive d'état et « fermé sans preuve » : l'histoire est la source d'audit ; les vues n'ont plus d'autorité. | E | Fowler, Event Sourcing ; Temporal Observability (Event History) ; OTel Logs Data Model (`Timestamp` vs `ObservedTimestamp`) |
| T02 | **Schéma d'événement large et structuré** | Un enregistrement par unité de travail avec des attributs riches (rôle, modèle, fournisseur, ticket, convoi, dépôt, branche, PR, tentative n°, raison d'arrêt). `SeverityNumber` normalisé, `EventName`, `TraceId/SpanId` pour corréler avec les traces. | Diagnostic par découpage (slice) sur n'importe quelle dimension sans réinstrumenter. | E | OTel Logs Data Model ; Honeycomb, Structured Events |
| T03 | **Machine d'états explicite + conditions par objet** | Pour ordre, ticket, convoi, PR : un `phase` (énuméré) et une liste de conditions `{type, status ∈ {True,False,Unknown}, reason, message, lastTransitionTime, observedGeneration}`. Transitions interdites rejetées par le code. | Un état « Done » sans condition `Accepted=True` ou `Merged=True` devient détectable mécaniquement. | E | Kubernetes API Conventions (conditions) |
| T04 | **Index de visibilité interrogeable** | Lister/filtrer/compter les exécutions (ordres, sessions) par attributs de recherche (ticket, convoi, rôle, fournisseur, statut) sans toucher la base applicative ; requête type SQL. | Répondre vite à « qu'est-ce qui tourne ? depuis quand ? pour qui ? » lors d'un incident. | R | Temporal Observability (Visibility, Search Attributes) |
| T05 | **Horodatages double source + fuseau** | `Timestamp` (origine) et `ObservedTimestamp` (collecte) distincts ; stockage en UTC, affichage converti (Paris). | Reconstituer une chronologie fiable quand l'hôte est saturé (collecte retardée). | R | OTel Logs Data Model |

### 3.2 Métriques & SLO

| ID | Capacité | Ce que le code doit capturer / vérifier / exposer | Pourquoi (risque couvert) | Niv. | Source(s) |
| --- | --- | --- | --- | --- | --- |
| T06 | **Signaux dorés par file de travail** | Pour chaque file (ordres planifiés, tickets prêts, PR ouvertes, appels LLM) : latence (attente en file, durée d'exécution ; distinguer succès/échec), trafic (débit), erreurs (explicites : échec ; implicites : timeout, résultat non conforme), saturation (slots occupés / slots max). | Couverture minimale « décente » ; la saturation précède les timeouts observés historiquement. | E | SRE Book ch. 6 ; Grafana, RED Method ; Argo Workflows Metrics (`queue_depth_gauge`, `queue_latency`, `workers_busy_count`) |
| T07 | **Temps par étape du cycle de vie** | Durée passée par ordre/ticket dans chaque état (planifié → en file → en cours → terminé), histogrammes ; compte des éléments par état (gauges). | Détecter la « famine » (tâches prêtes jamais démarrées) et les goulots. | E | Airflow Metrics (timers Scheduled/Queued/Running, « tasks starving », pool slots) |
| T08 | **SLI/SLO d'usine** | Définir et calculer par code au moins : taux d'ordres terminés sans timeout ; taux de tickets passés « done » avec preuve ; délai de prise en charge d'une escalade ; taux de PR mergées sans intervention manuelle. Budget d'erreur mensuel. | Donne un langage objectif à « ça marche mal » ; pilote l'alerting (T26). | R | SRE Workbook ch. 5 ; SRE Book ch. 6 |
| T09 | **Alertes multi-fenêtre multi-burn-rate** | Sur chaque SLO : fenêtres longue/courte (1 h/5 min à 14,4×, 6 h/30 min à 6×, 3 j/6 h à 1×), page vs ticket selon la sévérité ; critères précision/rappel/détection/reset documentés. Adapter pour faible trafic (agrégation, trafic synthétique). | Éviter à la fois le bruit (seuils bruts) et les alertes qui restent levées après résolution. | A | SRE Workbook ch. 5 |
| T10 | **Métriques de livraison (DORA)** | Calculées depuis Git/GitHub par code : fréquence de déploiement/merge, lead time (commit → mergé/déployé), taux d'échec de changement (revert/hotfix), temps de récupération d'un déploiement raté, taux de retouche (déploiements non planifiés suite à incident). | Mesurer la valeur produite, pas l'activité des agents ; détecter la dégradation de stabilité. | R | DORA, « DORA's software delivery metrics: the four keys » (2026-01-05) |

### 3.3 Traces agent / LLM

| ID | Capacité | Ce que le code doit capturer / vérifier / exposer | Pourquoi (risque couvert) | Niv. | Source(s) |
| --- | --- | --- | --- | --- | --- |
| T11 | **Trace par ordre, spans hiérarchiques** | Un trace par ordre/session ; spans `invoke_agent` (par rôle), `chat`/inférence (par appel modèle), `execute_tool` (par appel d'outil), spans de garde-fou et de passation (handoff). Parent-enfant explicite. | Reconstituer *ce que l'agent a réellement fait* sans se fier à son résumé. | E | OTel semantic-conventions-genai (README : `gen_ai.operation.name` ∈ {chat, execute_tool, invoke_agent, create_agent}) ; OpenAI Agents SDK Tracing (`agent_span`, `generation_span`, `function_span`, `guardrail_span`, `handoff_span`) |
| T12 | **Attributs GenAI normalisés** | Sur chaque span : `gen_ai.provider.name`, `gen_ai.request.model`, `gen_ai.response.model`, `gen_ai.agent.id/name`, `gen_ai.tool.name`, `gen_ai.conversation.id`, `gen_ai.usage.input_tokens/output_tokens`, `error.type`. Métriques `gen_ai.client.token.usage` et `gen_ai.client.operation.duration`. | Comparabilité entre fournisseurs lors des bascules ; base du coût (T30). **Statut de stabilité des conventions non vérifié** (voir §1). | E | OTel semantic-conventions-genai (README) ; opentelemetry.io/docs/specs/semconv/gen-ai (redirection) |
| T13 | **Compteurs de boucle et conditions d'arrêt** | Par ordre : nombre d'itérations, d'appels d'outils, de relances ; borne max codée ; raison d'arrêt énumérée (`completed`, `max_iterations`, `timeout`, `escalated`, `provider_error`). | Boucles de retry cachées dans les prompts : le code compte, le prompt ne compte pas. | E | Anthropic, Building Effective Agents (« stopping conditions, maximum number of iterations ») |
| T14 | **Capture des résultats d'outils comme vérité de terrain** | Les sorties d'outils (tests, lint, git, gh) sont enregistrées brutes (ou résumées par code, jamais par LLM) et liées au span. | « Done sans preuve » : la preuve est le résultat d'outil, pas la phrase de l'agent. | E | Anthropic, Building Effective Agents (« ground truth from the environment ») |
| T15 | **Export vers un backend de traces standard** | Export OTLP vers un outil (auto-hébergé ou SaaS) capable de vues hiérarchiques, coûts par trace, évaluation. | Dette d'outillage évitée ; comparaison dans le temps. | R | OpenAI Agents SDK Tracing (export vers Langfuse/Phoenix/OTel collector) ; comparatifs (C) |
| T16 | **Évaluation comme observabilité** | Scores d'évaluation (tests réussis, revue acceptée, règles déterministes) attachés aux traces ; files d'annotation humaine pour les cas douteux. | Mesurer la qualité des sorties dans le temps, pas seulement leur existence. | A | Anthropic (tests itératifs en workbench) ; comparatifs Langfuse/Phoenix (C) |

### 3.4 Cohérence & invariants

| ID | Capacité | Ce que le code doit capturer / vérifier / exposer | Pourquoi (risque couvert) | Niv. | Source(s) |
| --- | --- | --- | --- | --- | --- |
| T17 | **Réconciliateur tracker ↔ GitHub ↔ runtime** | Boucle périodique *par niveau* (lit l'état courant complet, jamais les seuls deltas) : pour chaque ticket/PR/session, compare l'état déclaré et l'état observé ; écrit des conditions `Drifted` avec `reason` ; idempotent. | Dérive d'état historique ; les événements manqués ne cassent pas la convergence. | E | Kubernetes API Conventions (level-based vs edge-based ; conditions) |
| T18 | **Invariants codés et vérifiés en continu** | Exemples : « un ticket `done` a une PR mergée référencée » ; « une PR mergée a une CI verte sur le SHA mergé » ; « un convoi fermé a une acceptation produit enregistrée » ; « un ordre en cours a une session vivante ». Violations → événement + condition. | Convois fermés sans assemblage ; PR « mergées » non vérifiées. | E | Kubernetes API Conventions ; SRE Book ch. 6 (white-box) |
| T19 | **Détection de travail bloqué (timeouts typés)** | Pour chaque ordre/activité : *schedule-to-start* (temps en file avant prise), *start-to-close* (durée d'exécution), *schedule-to-close* (durée totale avec retries), *heartbeat* (silence max). Dépassement = événement typé + condition. | Distinguer « personne ne prend le travail » (saturation) de « l'agent a planté » (worker) de « ça boucle » (retries). | E | Temporal, Detecting Activity Failures |
| T20 | **Heartbeats des sessions et sessions orphelines** | Chaque session émet un battement ; le scheduler compte « sessions sans battement tuées », « orphelins adoptés/nettoyés », « tués de l'extérieur ». | Orphelins tenant des ressources ; décision codée de les arrêter, avec trace. | E | Airflow Metrics (« task instances without heartbeats killed », « orphaned tasks cleared/adopted ») ; Temporal (Heartbeat Timeout) |
| T21 | **Dead man's switch de la chaîne d'alerte** | Une alerte « Watchdog » toujours levée, routée vers un service externe indépendant qui alerte si elle *cesse* d'arriver ; idem pour les tâches périodiques (ping succès/start/fail avec période + délai de grâce). | Le monitoring ne peut pas surveiller sa propre mort ; un scheduler arrêté se détecte par l'absence. | E | prometheus-operator runbook Watchdog ; healthchecks.io docs |
| T22 | **Idempotence et reprise des réconciliateurs** | Chaque action de réparation est idempotente, journalisée (T01), bornée (pas de boucle de réparation infinie), et pose une condition. | Éviter que la « réparation automatique » devienne elle-même une boucle cachée. | R | Kubernetes API Conventions (apply conditions même si `Unknown`) ; Fowler (replay) |

### 3.5 Preuve de livraison

| ID | Capacité | Ce que le code doit capturer / vérifier / exposer | Pourquoi (risque couvert) | Niv. | Source(s) |
| --- | --- | --- | --- | --- | --- |
| T23 | **Définition machine de « done »** | « Done » = conjonction vérifiée par code : PR mergée (API GitHub), check runs `completed/success` sur le SHA, revue approuvée, lien ticket↔PR↔SHA enregistré. Aucune transition `done` acceptée depuis un message d'agent. | Claim « done » sans preuve. | E | GitHub Check Runs API (status/conclusion) ; Anthropic (ground truth) |
| T24 | **État des PR et CI comme signaux** | Pour chaque PR : âge, temps sans activité, statut des checks (`queued/in_progress/completed` ; conclusions `success/failure/timed_out/cancelled/action_required/stale`), conflits, re-runs. Limites connues : job 6 h (runners hébergés), run 35 j, file 24 h (self-hosted). | PR bloquées ; CI dans un état `stale` ou `timed_out` passant pour « en cours ». | E | GitHub Check Runs API ; GitHub Actions Limits |
| T25 | **Provenance et attestation d'artefact** | Attestation in-toto/SLSA signée (Sigstore) liant artefact (digest) → workflow, dépôt, SHA, déclencheur ; vérification `gh attestation verify` dans la porte d'acceptation. Objectif Build L2 (L3 via workflow réutilisable). | Prouver que ce qui est livré vient bien de la chaîne attendue ; audit a posteriori. | A | SLSA v1.0 Provenance, v1.1 Levels (v1.2 courante) ; GitHub Artifact Attestations |
| T26 | **Acceptation produit enregistrée** | La fermeture d'un convoi exige un événement `Accepted` émis par un humain via la porte (ou par un test d'acceptation codé), référençant la version assemblée. | Convoi « 25/25 » fermé sans produit assemblé/accepté. | E | SRE Book ch. 6 (black-box : tester le comportement visible) ; Kubernetes conditions |
| T27 | **Télémétrie CI/CD normalisée** | Spans/métriques `cicd.pipeline.run.duration`, `.active`, `.errors`, `cicd.worker.count`, `cicd.system.errors`, attributs `vcs.*` ; statut « Release Candidate » des conventions. | Unifier CI et runtime dans le même backend de traces. | R | OTel Semconv CI/CD |

### 3.6 Alerting & escalade humaine

| ID | Capacité | Ce que le code doit capturer / vérifier / exposer | Pourquoi (risque couvert) | Niv. | Source(s) |
| --- | --- | --- | --- | --- | --- |
| T28 | **Politique de page codée** | Chaque alerte déclare : urgence (page immédiate / heures ouvrées / ticket / notification), symptôme couvert, runbook, test. Une alerte sans action humaine requise devient notification. | Fatigue d'alerte pour un opérateur seul ; alertes ignorées par habitude. | E | SRE Book ch. 6 (questions avant de pager) ; PagerDuty Alerting Principles |
| T29 | **Porte d'escalade instrumentée** | Événements : escalade ouverte (type, ticket, raison énumérée, contexte joint), notifiée, lue, décidée, appliquée ; SLI « temps d'attente d'une décision » ; file des décisions en attente exposée. | Décisions perdues ; agents qui contournent la porte ; mesure de la charge humaine. | E | SRE Workbook ch. 5 (détection/reset) ; PagerDuty (alerte = action humaine requise) |
| T30 | **Registre de toutes les pages** | Journal des pages (heure, cause, action, faux positif ?) revu périodiquement ; suppression des alertes jamais actionnées. | Hygiène : garder le système « aussi simple que possible ». | R | SRE Book ch. 6 (simplicité, retirer les signaux inutilisés) ; PagerDuty |

### 3.7 Coût & quotas

| ID | Capacité | Ce que le code doit capturer / vérifier / exposer | Pourquoi (risque couvert) | Niv. | Source(s) |
| --- | --- | --- | --- | --- | --- |
| T31 | **Lecture des en-têtes de quota à chaque réponse** | Anthropic : `anthropic-ratelimit-{requests,tokens,input-tokens,output-tokens}-{limit,remaining,reset}`, `retry-after`, `anthropic-workspace-id`. OpenAI : `x-ratelimit-{limit,remaining,reset}-{requests,tokens}`, `x-ratelimit-*-project-tokens`, `Retry-After`. Exposer comme gauges par fournisseur/modèle. | Anticiper la saturation de quota avant les 429 ; décider la bascule par code. | E | Anthropic Rate Limits ; OpenAI Rate Limits |
| T32 | **Classification des 429 et plafonds de dépense** | Distinguer 429 avec `retry-after` (limite de débit, réessayer) vs 429 `enforced_spend_limit_reached` sans `retry-after` (plafond mensuel : ne pas réessayer, escalader) vs 400 « specified API usage limits » (plafond fixé par l'organisation). Backoff exponentiel avec jitter, borné en tentatives et en durée. | Boucles de retry inutiles sur un plafond ; coût caché des relances. | E | Anthropic Rate Limits (spend cap, codes) ; OpenAI Rate Limits (backoff) |
| T33 | **Comptabilité tokens → coût par ordre/ticket/convoi** | Depuis `gen_ai.usage.*` et les champs de réponse (`input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `output_tokens`) : coût estimé par span, agrégé par ticket, convoi, rôle, fournisseur ; taux de cache. Budget par convoi avec alerte à seuil. | Visibilité « unit economics » : coût d'un ticket livré ; dérives d'un rôle bavard. | E | OTel GenAI (`gen_ai.usage.input_tokens/output_tokens`) ; Anthropic Rate Limits (cache-aware ITPM, formule total_input_tokens) ; FinOps Foundation (C) |
| T34 | **Réconciliation avec la facturation du fournisseur** | Comparer périodiquement le coût estimé local au coût facturé (console/API d'usage quand disponible ; l'Admin API Anthropic nécessite un plan Team/Enterprise — non accessible à un compte individuel). Écart → condition. | Détecter des appels non tracés (fuite d'instrumentation). | R | Anthropic Rate Limits (page Usage) ; Elastic « Anthropic Metrics » (C, décrit les endpoints Admin) |

### 3.8 Hôte (WSL / Windows)

| ID | Capacité | Ce que le code doit capturer / vérifier / exposer | Pourquoi (risque couvert) | Niv. | Source(s) |
| --- | --- | --- | --- | --- | --- |
| T35 | **PSI comme signal de saturation** | Échantillonner `/proc/pressure/{cpu,memory,io}` (lignes `some`/`full`, `avg10/avg60/avg300`, `total`) ; déclencheurs kernel (seuil + fenêtre, `poll()`) pour notification immédiate. Attacher la valeur PSI courante à chaque événement d'ordre (début/fin/timeout). | Corréler les timeouts d'ordres à la charge hôte (jeu) *au moment* de l'échec, plutôt qu'au load average. | E | Linux kernel docs, PSI |
| T36 | **Limites WSL connues et surveillées** | Lire `.wslconfig` (`memory` défaut 50 % RAM, `processors`, `swap` 25 %, `autoMemoryReclaim`, `vmIdleTimeout`) ; exposer mémoire/CPU alloués vs utilisés dans la VM ; alerter sur swap actif. | Les ordres meurent quand la VM est à sa borne alors que Windows semble libre. | R | Microsoft Learn, WSL config (2026-09-16) |
| T37 | **Mode « hôte dégradé » codé** | Quand PSI `full` dépasse un seuil soutenu : le scheduler réduit la concurrence, allonge les timeouts ou met en pause les ordres non critiques ; l'événement de dégradation est journalisé. | Transformer un diagnostic manuel (« c'est le jeu ? ») en décision automatique, traçable, réversible. | A | Linux PSI (cas d'usage : load shedding, pause de tâches batch) ; SRE Book ch. 6 (saturation) |

### 3.9 Post-incident

| ID | Capacité | Ce que le code doit capturer / vérifier / exposer | Pourquoi (risque couvert) | Niv. | Source(s) |
| --- | --- | --- | --- | --- | --- |
| T38 | **Déclencheurs de post-mortem codés** | Un incident est ouvert automatiquement quand : intervention humaine de réparation, perte de travail, dépassement de seuil de résolution, défaillance du monitoring (détection manuelle). Métadonnées : début, détection, mitigation, résolution, sévérité. | Ne pas dépendre de la mémoire de l'opérateur pour déclencher l'analyse. | R | SRE Book ch. 15 (Postmortem Culture) |
| T39 | **Chronologie auto-générée** | Export de la fenêtre d'incident depuis T01/T11 : événements, spans, alertes, décisions humaines, valeurs PSI, quotas — en un document relu par l'humain. | Réduire « l'archéologie » ; rendre la revue sans blâme factuelle. | R | SRE Book ch. 15 ; PagerDuty Postmortems ; Etsy Debriefing Facilitation Guide |
| T40 | **Suivi des actions correctives** | Actions avec propriétaire, échéance, lien vers la classe de défaut ; vérification automatique de clôture (le ticket d'action existe et est fermé). | Causes connues non closes qui se répètent. | R | SRE Book ch. 15 (action items appropriés, revus) |

### 3.10 Validation de l'observabilité elle-même

| ID | Capacité | Ce que le code doit capturer / vérifier / exposer | Pourquoi (risque couvert) | Niv. | Source(s) |
| --- | --- | --- | --- | --- | --- |
| T41 | **Tests d'alertes** | Chaque règle d'alerte a un test (jeu de données synthétique → l'alerte se lève puis se résout) ; cas « pas de données » testé. | « Une alerte non testée = pas d'alerte. » | E | PagerDuty Alerting Principles |
| T42 | **Injection de pannes contrôlée** | Expériences automatisées à faible rayon d'action : tuer une session, retarder GitHub, simuler un 429, saturer la VM ; hypothèse d'état stable mesurée avant/après ; vérifier que la détection (T17–T21) se déclenche. | Valider que les invariants et les détecteurs fonctionnent avant l'incident réel. | A | Principles of Chaos Engineering (2019) |
| T43 | **Couverture d'instrumentation** | Vérifier par code que chaque appel fournisseur, chaque ordre, chaque transition d'état produit son événement/span (comparaison compteurs ↔ facturation T34, spans orphelins, événements sans trace). | Trous d'instrumentation = angles morts silencieux. | R | OTel Logs Data Model (corrélation) ; Temporal (métriques SDK vs service) |

---

## 4. Anti-patterns documentés

| Anti-pattern | Pourquoi c'est un problème | Ce que dit la source | Source |
| --- | --- | --- | --- |
| Alerter sur les causes plutôt que les symptômes | Bruit, alertes non actionnables, vrais impacts manqués | « What's broken ? » (symptôme) vs « Why ? » (cause) : distinction la plus importante pour un monitoring à fort signal | SRE Book ch. 6 |
| Pager sur ce qui n'exige pas d'action humaine | Fatigue d'alerte ; l'opérateur seul finit par ignorer | Une alerte = quelque chose qui exige une action humaine ; le reste est notification | PagerDuty Alerting Principles |
| Alertes jamais testées | Faux sentiment de couverture | « An untested alert is equivalent to not having an alert at all » | PagerDuty Alerting Principles |
| Seuils bruts à fenêtre courte | Faux positifs sur pics brefs ; mauvais temps de reset | Évolution en six étapes jusqu'au multi-fenêtre multi-burn-rate | SRE Workbook ch. 5 |
| Garder des règles rarement exercées et des signaux inutilisés | Complexité qui masque les vraies pannes | Concevoir « avec un œil sur la simplicité » ; retirer ce qui n'est pas utilisé | SRE Book ch. 6 |
| Réconciliation par fronts (événements) seulement | Un événement manqué laisse l'état faux pour toujours | Le système doit être *level-based* : agir sur l'état courant, pas sur les transitions | Kubernetes API Conventions |
| Inférer l'état au lieu de l'exposer en conditions | Chaque consommateur réinvente la logique, de façon divergente | Les conditions existent « pour exprimer explicitement » ce qui compte plutôt que de le déduire | Kubernetes API Conventions |
| Laisser le monitoring surveiller sa propre panne | Panne silencieuse du scheduler ou de la chaîne d'alerte | Watchdog toujours levé + service externe qui alerte sur l'absence | prometheus-operator Watchdog ; healthchecks.io |
| Retry automatique sur un plafond de dépense | Boucle inutile, coûts d'infrastructure, incident masqué | Le 429 de plafond n'a pas de `retry-after` ; les retries échouent jusqu'à la reprise | Anthropic Rate Limits |
| Retry sans borne ni jitter | Tempêtes de relances synchronisées | Backoff exponentiel avec jitter, borné en tentatives et en temps total | OpenAI Rate Limits |
| Compter sur l'auto-évaluation de l'agent | Erreurs qui se composent ; « done » déclaratif | Vérité de terrain depuis l'environnement à chaque pas ; conditions d'arrêt codées ; garde-fous | Anthropic, Building Effective Agents |
| Post-mortem avec blâme | Information cachée, pas d'apprentissage systémique | Supposer la bonne foi ; corriger les systèmes, pas les personnes | SRE Book ch. 15 ; Etsy Debriefing Guide |
| Supposer que « rate limit = TPM combiné » | Sous-estime la capacité réelle ; mauvaise bascule | Pour la plupart des modèles Anthropic, les tokens lus en cache ne comptent pas dans l'ITPM | Anthropic Rate Limits |
| Utiliser le load average pour « l'hôte est saturé » | Ne mesure pas l'attente réelle des tâches ; mauvaise corrélation | PSI mesure le temps *stalled* par ressource avec fenêtres 10 s/60 s/300 s | Linux PSI |

---

## 5. Références

Toutes consultées le 2026-10-06. Confiance : A = primaire officielle, B = praticien reconnu, C = secondaire / non vérifié.

### Fondations et SRE
- [A] Google, *Site Reliability Engineering*, ch. 6 « Monitoring Distributed Systems » (Rob Ewaschuk, éd. Betsy Beyer), 2016 — https://sre.google/sre-book/monitoring-distributed-systems/
- [A] Google, *SRE Book*, Part III « Practices » (Service Reliability Hierarchy, Mikey Dickerson), 2016 — https://sre.google/sre-book/part-III-practices/
- [A] Google, *SRE Book*, ch. 15 « Postmortem Culture: Learning from Failure », 2016 — https://sre.google/sre-book/postmortem-culture/
- [A] Google, *The Site Reliability Workbook*, ch. 5 « Alerting on SLOs », 2018 — https://sre.google/workbook/alerting-on-slos/
- [C — non vérifié] Rob Ewaschuk, « My Philosophy on Alerting », 2014 (Google Doc, mur de connexion ; contenu repris dans SRE Book ch. 6) — https://docs.google.com/document/d/199PqyG3UsyXlwieHaqbGiWVa8eMWi8zzAn0YfcApr8Q/edit
- [B] Grafana Labs, Tom Wilkie, « The RED Method: How to Instrument Your Services », 2018 — https://grafana.com/blog/2018/08/02/the-red-method-how-to-instrument-your-services/
- [B] Honeycomb, « Structured Events Are the Basis of Observability » (Authors' Cut) — https://honeycomb.io/blog/structured-events-basis-observability
- [A] OpenTelemetry, *Logs Data Model* (specification) — https://opentelemetry.io/docs/specs/otel/logs/data-model/
- [A] OpenTelemetry, *Semantic Conventions for CI/CD* (statut Release Candidate) — https://opentelemetry.io/docs/specs/semconv/cicd/

### Agents LLM
- [A] OpenTelemetry, dépôt *semantic-conventions-genai* (README ; attributs `gen_ai.*`, opérations chat / execute_tool / invoke_agent / create_agent ; statut de stabilité non affirmé) — https://github.com/open-telemetry/semantic-conventions-genai
- [A] OpenTelemetry, page `gen-ai` des semconv (redirection vers le dépôt ci-dessus) — https://opentelemetry.io/docs/specs/semconv/gen-ai/
- [C — non vérifié] Page `docs/gen-ai-agent-spans.md` du dépôt : 404 au chemin essayé le 2026-10-06.
- [C] OpenTelemetry blog, « Inside the LLM Call: GenAI Observability with OpenTelemetry », 2026 (non lu en détail) — https://opentelemetry.io/blog/2026/genai-observability/
- [A] OpenAI, *Agents SDK — Tracing* (spans agent/generation/function/guardrail/handoff, export OTel) — https://openai.github.io/openai-agents-python/tracing/
- [A] Anthropic, « Building effective agents », 2024-12-19 — https://www.anthropic.com/research/building-effective-agents
- [C] Comparatifs Langfuse / Arize Phoenix / LangSmith (ZenML, MLflow, divers) — utilisés uniquement pour la notion de types d'observations (Agent/Tool/Generation/Guardrail) ; ex. https://www.zenml.io/blog/langfuse-vs-phoenix
- [C] Google/Kaggle, whitepaper « Agents » (Wiesinger, Marlow, Vuskovic, 2024) — non lu directement ; cité via résumés — https://archive.org/details/google-ai-agents-whitepaper

### Moteurs de workflow et CI
- [A] Temporal, « Observability » (Event History, Visibility, metrics SDK/service, OTel interceptors) — https://docs.temporal.io/evaluate/features/observability
- [A] Temporal, « Detecting Activity failures » (Schedule-To-Start, Start-To-Close, Schedule-To-Close, Heartbeat) — https://docs.temporal.io/encyclopedia/detecting-activity-failures
- [B] Martin Fowler, « Event Sourcing », 2005-12-12 — https://martinfowler.com/eaaDev/EventSourcing.html
- [A] Apache Airflow 3.x, « Metrics » (heartbeats, zombies, orphaned tasks, pool slots, starving) — https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/logging-monitoring/metrics.html
- [A] Argo Workflows, « Metrics » (queue depth/latency, workers busy, error_count, is_leader) — https://argo-workflows.readthedocs.io/en/latest/metrics/
- [A] GitHub Docs, « Limits for GitHub Actions » (job 6 h / 5 j, run 35 j, file 24 h, concurrence) — https://docs.github.com/en/actions/reference/limits
- [A] GitHub REST API, « Check Runs » (status, conclusion, output, external_id) — https://docs.github.com/en/rest/checks/runs
- [C — 404] GitHub Docs « workflow-runs » (deux chemins essayés, 404 le 2026-10-06).

### Delivery et provenance
- [A] DORA, « DORA's software delivery metrics: the four keys » (page datée 2026-01-05) — https://dora.dev/guides/dora-metrics-four-keys/
- [A] DORA, « History of DORA metrics » — https://dora.dev/guides/dora-metrics/history/
- [A] SLSA, Specification v1.0 « Provenance » (retirée ; v1.2 courante) — https://slsa.dev/spec/v1.0/provenance
- [A] SLSA, Specification v1.1 « Levels » (retirée ; v1.2 courante) — https://slsa.dev/spec/v1.1/levels
- [A] GitHub Docs, « Artifact attestations » (SLSA v1.0 Build L2 par défaut, L3 via workflow réutilisable, Sigstore, `gh attestation verify`) — https://docs.github.com/en/actions/concepts/security/artifact-attestations

### Cohérence, chaos, dead man's switch
- [A] Kubernetes, « API Conventions » (spec/status, conditions, level-based) — https://github.com/kubernetes/community/blob/master/contributors/devel/sig-architecture/api-conventions.md
- [A] Principles of Chaos Engineering (mise à jour mars 2019) — https://principlesofchaos.org/
- [A] prometheus-operator runbooks, « Watchdog » — https://runbooks.prometheus-operator.dev/runbooks/general/watchdog/
- [A] Healthchecks.io, documentation (ping success/start/fail, période, délai de grâce) — https://healthchecks.io/docs/

### Humain, alerting, post-incident
- [A] PagerDuty, Incident Response — « Alerting Principles » — https://response.pagerduty.com/oncall/alerting_principles/
- [A] PagerDuty, Postmortems documentation — https://postmortems.pagerduty.com/
- [A] Etsy, « Debriefing Facilitation Guide » (CC-BY-SA-4.0) — https://github.com/etsy/DebriefingFacilitationGuide

### Coût et quotas
- [A] Anthropic, Claude Platform — « Rate limits » (en-têtes `anthropic-ratelimit-*`, `retry-after`, spend cap, `enforced_spend_limit_reached`, ITPM cache-aware) — https://platform.claude.com/docs/en/api/rate-limits
- [A] OpenAI, « Rate limits » (en-têtes `x-ratelimit-*`, backoff avec jitter, spend limits) — https://developers.openai.com/api/docs/guides/rate-limits
- [C] Elastic, intégration « Anthropic Metrics » (décrit les endpoints Admin API usage_report / cost_report / rate_limits ; plan Team/Enterprise requis) — https://www.elastic.co/docs/reference/integrations/anthropic_metrics
- [C] FinOps Foundation / presse (FinOps for AI, Tokenomics Foundation) — https://thenewstack.io/finops-foundation-launches-new-finops-for-ai-certification/

### Hôte
- [A] Linux kernel documentation, « PSI — Pressure Stall Information » — https://docs.kernel.org/accounting/psi.html
- [A] Microsoft Learn, « Advanced settings configuration in WSL » (`.wslconfig` : memory, processors, swap, autoMemoryReclaim ; mis à jour 2026-09-16) — https://learn.microsoft.com/en-us/windows/wsl/wsl-config

---

## Annexe — ordre de mise en œuvre suggéré (dérivé des niveaux)

| Vague | Capacités | Pannes historiques couvertes |
| --- | --- | --- |
| 1 (Essentiel, état) | T01, T02, T03, T13, T14, T23, T26 | « done » sans preuve ; convoi fermé sans acceptation ; retries cachés |
| 2 (Essentiel, détection) | T17, T18, T19, T20, T21, T06, T07 | dérive d'état ; PR bloquées ; orphelins ; scheduler mort |
| 3 (Essentiel, humain/coût/hôte) | T28, T29, T31, T32, T33, T35, T41 | fatigue d'alerte ; 429 mal gérés ; timeouts sous charge hôte |
| 4 (Recommandé) | T04, T05, T08, T10, T15, T22, T24, T27, T30, T34, T36, T38, T39, T40, T43 | mesure de la valeur ; post-incident outillé |
| 5 (Avancé) | T09, T11-T12 (si non faits en 1), T16, T25, T37, T42 | SLO fins ; provenance ; chaos contrôlé |

Cette annexe est une interprétation (ordre), pas une source.
