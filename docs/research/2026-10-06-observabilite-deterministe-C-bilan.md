# C — Bilan : observabilité déterministe cible vs existante (Agent Factory)

Intent (Benjamin, his words, 2026-10-06) : « Il faut faire un bilan de l'observabilité déterministe (code) cible et ce qu'on a. Il faut la cible la meilleure possible en s'inspirant méthodiquement de recherche internet. Et il faut comparer à ce qu'on a ensuite, indépendamment. »
Mechanism (agent interpretation) : trois pièces produites par trois passes étanches. **A** = cible construite par recherche internet sans accès au dépôt (`2026-10-06-observabilite-deterministe-A-cible.md`). **B** = inventaire du code et du câblage live à `c0fbf72`, sans lecture de A (`…-B-inventaire.md`). **C** (ce document) = comparaison faite après coup, capacité par capacité, puis croisée avec les causes d'incidents déjà enregistrées (`SayMyName/knowledge/incident-reviews.md`, revues du 2026-09-29 et du 2026-10-01). Ce bilan ne décide aucune route : il est une entrée pour une map `/wayfinder`.

Jargon : **CÂBLÉ** = déclenché automatiquement dans la cité qui tourne ; **MANUEL** = existe, à invoquer ; **INACTIF** = code présent et testé, mais inopérant en live (secret absent, aucun appelant) ; **condition** = assertion typée sur un objet (`type/status/reason/since`) ; **PSI** = Pressure Stall Information, temps que les tâches passent à attendre une ressource.

---

## 1. Verdict en cinq lignes

1. **Sur 24 capacités Essentielles, 5 sont couvertes, 11 partielles, 8 absentes ou inactives.** Les 19 Recommandées/Avancées sont à 1 couverte, 9 partielles, 9 absentes.
2. **Ce qu'on a est fort là où la cible parle de *gardes*** : réconciliation tracker ↔ GitHub par niveau toutes les 5 min, preuve de livraison vérifiée via `gh` sur la tête exacte, porte unique d'escalade, tests CI pour chaque garde. C'est le cœur de T17, T20, T23, T24, T41.
3. **Ce qu'on n'a pas, c'est la *télémétrie*** : aucune métrique calculée (latence, files, saturation, SLO, DORA), aucune trace par ordre/agent, coût figé depuis le 01/10 et non tarifé, aucune mesure hôte continue. T06-T12, T15, T33-T35 sont vides.
4. **La chaîne d'alerte n'est pas fiable aujourd'hui** : dead man's switch (heartbeat Healthchecks) et push iPhone inactifs, 7 gates `human` ouvertes depuis 12 h sans jamais atteindre NEEDS BENJAMIN, alertes dupliquées. Le monitoring ne sait pas qu'il est muet.
5. **Le trou structurel est le modèle d'état** : les gardes posent des drapeaux une fois (`*_flagged_at`) et re-dérivent tout à chaque passe ; il n'y a ni cycle de vie ni conditions typées hors des convois marqués (0 ouvert). C'est exactement la cause **D** de la revue du 2026-10-01, la plus fréquente, jamais attaquée en classe.

---

## 2. Comparaison capacité par capacité

Statut : **COUVERT** (mécanisme câblé et testé qui fait l'essentiel), **PARTIEL** (une partie, ou câblé mais à périmètre réduit), **ABSENT**, **INACTIF** (présent mais inopérant en live). Niveau : E = Essentiel, R = Recommandé, A = Avancé (de A).

### 2.1 Événements & état

| Cible | Niv. | Existant (B) | Statut | Écart précis |
|---|---|---|---|---|
| T01 Journal d'événements append-only | E | E01 `events.jsonl` upstream (seq, type, ts, actor, subject, payload ; rotation 14 j) | PARTIEL | Les transitions **de l'usine** (escalade ouverte/effacée, drapeau de garde, verdict) vivent dans des clés Beads **écrasables** (`gc.escalation_cleared_at` remplace la précédente) : pas d'historique rejouable au niveau Factory. |
| T02 Schéma d'événement large | E | E01 ; les gardes écrivent des mails texte `ACTION/STATE/EVIDENCE/NEXT` et des beads | PARTIEL | Pas de dimensions normalisées (rôle, modèle, fournisseur, tentative, raison d'arrêt) ; le mail est « notification, pas état ». |
| T03 Machine d'états + conditions par objet | E | E06 `convoy-state` (« état sans règle », exit 3) **pour les seuls convois marqués** ; ailleurs drapeaux `*_flagged_at`, `*_reported_at`, `*_nudged_at` | ABSENT (hors convois marqués) | Aucun objet (ordre, ticket, PR, escalade) ne porte `phase` + conditions ; chaque garde réinvente « déjà vu ? » avec sa propre clé. **Cause D.** |
| T04 Index de visibilité | R | `gc events --type/--since`, `gc bd list --json`, cockpit `/api/*` | PARTIEL | Pas de requête croisée ordre × ticket × PR × session. |
| T05 Horodatage double + fuseau | R | ISO avec offset dans `events.jsonl` ; logs texte en UTC ; cockpit affiche Paris | PARTIEL | Pas d'`ObservedTimestamp` ; mélange UTC/Paris dans les beads et logs. |

### 2.2 Métriques & SLO

| Cible | Niv. | Existant | Statut | Écart |
|---|---|---|---|---|
| T06 Signaux dorés par file | E | `gc doctor` (`backlog-depth`, `fork-rate`), cockpit (`ready 79 / in_progress 4`) | ABSENT | Aucune latence, aucun taux d'erreur, aucune saturation (slots/N) calculés ou historisés. |
| T07 Temps par étape du cycle de vie | E | — | ABSENT | Rien ne mesure « prêt → démarré » ni « en cours → fermé » ; le stall #373 (01:16-03:06) n'a sonné nulle part. |
| T08 SLI/SLO d'usine | R | A5 « 24 h sans `order.failed` » (critère informel, cassé deux fois) | ABSENT | Aucun indicateur défini ni calculé par code. |
| T09 Burn-rate multi-fenêtre | A | — | ABSENT | Dépend de T08. |
| T10 DORA | R | E47 `rituals-status` compte les PR mergées (seuil 20) | ABSENT | Pas de lead time, taux d'échec, temps de récupération. |

### 2.3 Traces agent / LLM

| Cible | Niv. | Existant | Statut | Écart |
|---|---|---|---|---|
| T11 Trace par ordre, spans | E | E55 traces upstream texte (90 + 387 + 52 Mo, sans rotation) | ABSENT | Aucun span ; impossible de reconstituer « ce que l'agent a fait » autrement qu'en lisant son résumé. **Cause E** (agent conclut sans preuve). |
| T12 Attributs GenAI normalisés | E | — | ABSENT | Pas de `gen_ai.*` ; la bascule fournisseur (E33) n'est pas comparable d'un fournisseur à l'autre. |
| T13 Compteurs de boucle + raison d'arrêt | E | E17 loop-guard (>10 cycles/h ⇒ suspension), `gc.flow.counter.*` (convois marqués), `max_sessions` | PARTIEL | Pas d'énumération de la raison d'arrêt d'un ordre ; les relances internes à un prompt restent invisibles. |
| T14 Résultats d'outils = vérité | E | E08 `evidence-capture` (scellé HMAC, lié au commit) ; E10 `deliver-close` via `gh` | PARTIEL | E08 est **MANUEL, aucun appelant automatique** ; « l'agent décide ce qu'il capture ». |
| T15 Export OTLP | R | — | ABSENT | — |
| T16 Évaluation comme observabilité | A | E58 `graph-review` (verdicts liés au digest), rôle Evaluator (D01, en cours) | PARTIEL | Pas de score attaché à une trace ni d'historique. |

### 2.4 Cohérence & invariants

| Cible | Niv. | Existant | Statut | Écart |
|---|---|---|---|---|
| T17 Réconciliateur par niveau | E | E13 `factory-guard` 5 min (16 sections, relit tout), E24 `pr-autopilot` 3 min, E18-E21 | **COUVERT** | Forme : résultats en drapeaux et mails, pas en conditions (voir T03). Périmètre runtime ↔ tracker plus mince (E16, E19). |
| T18 Invariants vérifiés en continu | E | E11/E12 « fermé shipped ⇒ 6 champs + CI verte sur la tête », E14(3) faux succès, E21, E13 `invariants` | PARTIEL | Manquent : « convoi fermé ⇒ acceptation produit enregistrée » (C01 fermé 25/25 sans produit, **causes A/B**) ; « ticket `done` ⇒ relecture indépendante présente » ; « ordre en cours ⇒ session vivante » (partiel via `session-boot`). |
| T19 Timeouts typés | E | `timeout` par order (start-to-close), E37 idle 15 min (≈ schedule-to-start), E19 15 min sans progrès (≈ heartbeat) | PARTIEL | Pas de classification à l'échéance : un `order.failed` à 60 s ne dit pas saturation / plantage / boucle. **Cause F** (5 timeouts inexpliqués). |
| T20 Heartbeats et orphelins | E | E16, E17, E39, reaper upstream, E13 `session-boot` | **COUVERT** | — |
| T21 Dead man's switch | E | E51 heartbeat Healthchecks (5 min si gc et Beads frais) ; E36 archive > 24 h | **INACTIF** | Secrets absents : aucun ping ne part ; un arrêt total de l'usine ne serait vu par personne. Le `supervisor.log` et `usage.jsonl` figés le prouvent (voir T43). |
| T22 Réparations idempotentes et journalisées | R | drapeaux « une fois », E44 log avec undo, E12 backfill borné | **COUVERT** | — |

### 2.5 Preuve de livraison

| Cible | Niv. | Existant | Statut | Écart |
|---|---|---|---|---|
| T23 « Done » machine | E | E10 + E11 + E12 (PR fusionnée ∧ workflow requis réussi sur la tête exacte, écrit en un seul `gc bd update`) | **COUVERT** (code) / PARTIEL (contrat) | Le code vérifie « mergée + CI » ; le contrat des tickets promettait relecture indépendante et captures : **personne ne les vérifie** (**cause A**). |
| T24 PR et CI comme signaux | E | E24, E14(2), E26 rollup | **COUVERT** | — |
| T25 Provenance / attestation | A | E57 ne couvre que les fixtures PII | ABSENT | — |
| T26 Acceptation produit enregistrée | E | Glossaire « Delivered ≠ Accepted » ; cockpit `accepter_chantier` trace l'acte | PARTIEL | Aucune porte n'empêche la fermeture d'un convoi sans `Accepted` (**cause B**). |
| T27 Télémétrie CI/CD normalisée | R | — | ABSENT | — |

### 2.6 Alerting & escalade humaine

| Cible | Niv. | Existant | Statut | Écart |
|---|---|---|---|---|
| T28 Politique de page codée | E | E30 deux classes (`benjamin` / `mayor` + promotion 2 h), champs bornés | PARTIEL | Pas d'urgence graduée ; **trou D8** : une gate `human` est re-signalée au Mayor puis `clear`ée, et n'atteint jamais NEEDS BENJAMIN (7 ouvertes depuis 03:49 Paris ; proposition `af-os9sh2` le nomme). 8 des 17 beads d'alerte du 01/10 étaient des doublons. |
| T29 Porte d'escalade instrumentée | E | E30 horodatages `paged_at / cleared_at`, `repondre`, `list` | PARTIEL | Pas de SLI « temps d'attente d'une décision » ; pas d'événement « lue » / « appliquée ». |
| T30 Registre des pages revu | R | beads `gc.source=<garde>` ; rituel `incidents` (SayMyName) | PARTIEL | Pas de marquage faux positif ni de retrait des alertes jamais actionnées. |

### 2.7 Coût & quotas

| Cible | Niv. | Existant | Statut | Écart |
|---|---|---|---|---|
| T31 En-têtes de quota | E | E33 lit les **écrans tmux** des sessions pour détecter un mur | PARTIEL (fragile) | Aucune lecture d'en-tête `ratelimit-*` ; détection a posteriori par texte. |
| T32 Classification des 429 / plafond | E | E33 bascule sur épuisement ; `exhaustion_gate` ⇒ NEEDS BENJAMIN | ABSENT | Pas de distinction débit / plafond de dépense ; pas de backoff borné codé. |
| T33 Tokens → coût | E | E34 `usage.jsonl` upstream | **INACTIF** | Dernière écriture 2026-10-01 12:02 Paris malgré 44 `session.woke`/24 h ; tout `UNPRICED`, `EST_USD 0`. Classé **UPSTREAM** pour la cause, **nôtre** pour la non-détection. |
| T34 Réconciliation facturation | R | — | ABSENT | — |

### 2.8 Hôte (WSL)

| Cible | Niv. | Existant | Statut | Écart |
|---|---|---|---|---|
| T35 PSI | E | E23 diffère un dispatch si `MemAvailable` < 1,5 GiB ; E13 imprime `loadavg` si lent | PARTIEL | Mémoire seule ; pas de CPU/IO ; aucune valeur attachée aux événements d'ordre. À l'inspection : `loadavg` 9,88 sur 12 vCPU, 5 `order.failed`/24 h, aucun lien enregistré. **Cause F.** |
| T36 Limites WSL surveillées | R | E35 `factory-resources` (lit `.wslconfig`, seuils) | PARTIEL | MANUEL, sans test, sans order. |
| T37 Mode hôte dégradé | A | E23 (mémoire) | PARTIEL | Pas de réduction de concurrence ni d'allongement de timeout sous charge CPU. |

### 2.9 Post-incident

| Cible | Niv. | Existant | Statut | Écart |
|---|---|---|---|---|
| T38 Déclencheurs de post-mortem | R | Rituel `incidents` (5 bugs ⇒ DUE, **DUE aujourd'hui**) ; E07 incident pour convois marqués | PARTIEL | Un produit livré en pièces sans bead est invisible (angle mort noté le 01/10). |
| T39 Chronologie auto-générée | R | `gc events --since` à la main | ABSENT | — |
| T40 Suivi des actions correctives | R | E31 propositions (8 en attente) ; colonne « déjà attaqué par » écrite à la main | PARTIEL | Aucune vérification codée qu'une cause nommée a un ticket et qu'il est fermé (**cause C** « non close » depuis le 29/09). |

### 2.10 Validation de l'observabilité

| Cible | Niv. | Existant | Statut | Écart |
|---|---|---|---|---|
| T41 Tests d'alertes | E | un test CI par garde (122 fichiers, pre-push, `factory-main-gate`) | **COUVERT** | Mais 11 tests `local-only` hors de la batterie nocturne (D13), dont les essais contre le vrai `gc`. |
| T42 Injection de pannes | A | tests en cité isolée (local-only) | PARTIEL | Pas d'expérience contre la cité qui tourne. |
| T43 Couverture d'instrumentation | R | — | ABSENT | Preuve par l'exemple : `usage.jsonl` figé 5 jours et personne ne l'a vu. |

---

## 3. Lecture transversale

### 3.1 Décompte

| Niveau | Capacités | COUVERT | PARTIEL | ABSENT / INACTIF |
|---|---|---|---|---|
| Essentiel | 24 | 5 (T17, T20, T23, T24, T41) | 11 | 8 (T03, T06, T07, T11, T12, T21, T32, T33) |
| Recommandé | 14 | 1 (T22) | 6 (T04, T05, T30, T36, T38, T40) | 7 (T08, T10, T15, T27, T34, T39, T43) |
| Avancé | 5 | 0 | 3 (T16, T37, T42) | 2 (T09, T25) |

### 3.2 Forme de l'écart

| Famille cible | Existant | Diagnostic |
|---|---|---|
| Gardes / réconciliation / preuve de livraison | Dense, câblé, testé | Point fort. Le modèle « code décide, LLM n'écrit pas l'état » est réel ici. |
| Modèle d'état (cycle de vie, conditions) | Drapeaux une fois, re-dérivation à chaque passe | Dette structurelle : chaque garde porte sa propre mémoire ; doublons et silences (cause D). |
| Télémétrie (métriques, traces, coût) | Quasi nulle ; upstream en texte libre et figé | On ne sait pas mesurer l'usine ; on sait seulement la fouiller. |
| Chaîne d'alerte | Porte unique correcte, mais sortie vers l'humain inactive et trou `human` gate | Les alertes existent et n'arrivent pas. |
| Hôte | Mémoire seule, manuel | Hypothèse « c'est le jeu » jamais mesurée au moment de l'échec. |
| Post-incident | Rituel humain, pas d'automate | Les causes connues reviennent (C) parce que rien ne vérifie leur clôture. |

### 3.3 Croisement avec les causes d'incidents enregistrées

| Cause (revue 2026-10-01) | Capacités cibles qui la couvriraient | État |
|---|---|---|
| A — critère écrit vérifié par personne | T18 (invariant « relecture présente »), T23 (contrat), T14 | PARTIEL : seul « mergé + CI » est vérifié |
| B — découpé par module, pas d'assemblage | T26 (acceptation bloquante), T18 | PARTIEL : acte tracé, pas bloquant |
| C — fakes divergent des vrais outils | T41/T42 (essais contre le vrai `gc`), T43 | PARTIEL : 11 tests réels hors batterie |
| D — état re-dérivé, pas de cycle de vie (**la plus fréquente**) | T03, T01, T28/T29 | ABSENT |
| E — agent conclut sans preuve | T11, T14 | ABSENT / MANUEL |
| F — budgets de temps (timeouts inexpliqués) | T19, T35, T07 | PARTIEL / ABSENT |
| G — racine vive partagée | T17 (`live-root-sync`), hooks E28 | COUVERT |

Les deux causes les plus lourdes (A+B) et la plus fréquente (D) tombent toutes dans les zones ABSENT/PARTIEL de la cible. La cible n'est donc pas théorique : elle recouvre les pannes déjà subies.

---

## 4. Ce que dit l'inventaire en plus de la cible (dérives doc ↔ code à traiter dans la même map)

Reprises de B §5, classées par verdict opérateur (sous-produit normal ⇒ automatiser ; bug ⇒ corriger la classe) :

| Dérive | Verdict | Classe à corriger |
|---|---|---|
| D1 `factory-doctor` ACTIONABLE sur 2 formules locales + 4 classes, exit non-zéro ; doc dit « sûr à câbler » | bug | Heuristique « cache ⇒ upstream » insuffisante ; outil non câblable tant qu'il est rouge à vide |
| D4 4 lignes santé cockpit sans producteur | bug de livraison (cause A) | Aucun invariant « chaque consommateur de clé a un producteur » |
| D5 traces 90/387/52 Mo, `rotate-logs` jamais lancé, pas d'order | sous-produit | Automatiser la rotation (geste déjà sur liste blanche) |
| D6 Serve Tailscale absent, heartbeat/push inactifs ; doc dit « running » | **NEEDS BENJAMIN** (secrets = ADMIN) | T21 ; tant que non fait, l'usine est muette vers l'extérieur |
| D7 `factory-observe` (B09) jamais exécuté, aucun appelant | décision de map | Soit câbler un producteur d'instantané, soit le déclasser de `kernel` |
| D8 gates `human` hors NEEDS BENJAMIN (proposition `af-os9sh2`) | bug | T28 : la porte doit couvrir toute attente humaine, quel que soit son type de bead |
| D9 `usage.jsonl` figé | UPSTREAM (cause) + bug nôtre (T43) | Détecter la mort d'un flux attendu |
| D13 11 tests local-only hors batterie nocturne | sous-produit | Découverte par marqueur `# ci: local-only` au lieu d'une liste codée en dur |
| D2, D3, D10, D11, D12, D14 | dérives de doc | Corrigées dans la map ou par un ticket de doc unique |

---

## 5. Première tranche recommandée (proposition, non décidée)

Ordre choisi par rapport coût / causes couvertes, en restant dans le flux Planning Run (map `/wayfinder` → spec → tickets) :

1. **Rendre la chaîne d'alerte vraie** (T21, T28) : activer heartbeat + push (secrets, Benjamin), fermer le trou des gates `human` dans `escalation-door`/`factory-watchdog`, dédupliquer par objet. Petit, bloque tout le reste : sans ça, aucune amélioration n'est vue.
2. **Un modèle d'état partagé pour les gardes** (T03, T01) : un module unique « conditions par objet » (`type/status/reason/since`) remplaçant les clés `*_flagged_at` éparses, avec journal append-only des transitions. Attaque la cause D en classe.
3. **Timeouts typés + PSI attaché aux ordres** (T19, T35, T07) : à chaque `order.fired/failed`, enregistrer schedule-to-start, durée, et PSI cpu/mem/io courants. Rend la cause F diagnosticable en une requête.
4. **Détection de flux mort** (T43) : « un flux attendu (usage, heartbeat contrôleur, archive) n'a pas écrit depuis X » comme section de `factory-guard`. Aurait vu D9 le 2 octobre.
5. Ensuite seulement : métriques et SLO (T06-T08), traces agent (T11-T14), coût (T33), acceptation bloquante (T26).

Hors tranche, à classer : T25 attestation SLSA, T09 burn-rate, T15 OTLP, T27, T34, T37, T39, T42 — Avancé ou dépendant des précédents.

---

## 6. Limites de ce bilan

- A n'a pas vérifié la stabilité des conventions OTel GenAI (page 404) ; T12 est à confirmer avant implémentation.
- B n'a pas exécuté les tests, n'a pas lu les CI des rigs produit, ni la tâche de logon Windows ; les scripts ont été lus par en-têtes et grep des écritures, pas ligne à ligne.
- La comparaison est faite par une seule passe (ce document) ; les statuts COUVERT reposent sur B, pas sur une démonstration en cité isolée.
- Aucune route n'est décidée ici ; les causes A-G citées sont celles de la revue du 2026-10-01, elles-mêmes « not decided by Benjamin at the time of writing ».
