# Autopsie C01 — Cockpit V2 (lecture seule, 2026-10-01)

Sources : Beads (`bd show`), `git show main:…` (HEAD `112c286`), `gh pr view`. Heures en Paris.

## 1. Résumé en 5 lignes

- Le convoi `af-f71cgu` (25 tickets) a duré **10 h 47** : publié 30/09 17:55, fermé 01/10 04:42, par « convoy autoclose: all children closed ».
- **Assemblage** : le serveur servi (`lib/cockpit/core/server.py`) n'expose que `GET /` + 3 API + les actions. `/` = ligne de fraîcheur + « Ce qui t'attend » + zone santé. Les sorties de **8 tickets sur 14 tickets cockpit** (T15, T17, T18, T19, T20, T22, T23, T24 ; T25 en partie) ne sont importées par aucun code servi (seulement par leurs tests).
- **Fidélité** : seule la palette (`:root`) du prototype a traversé la chaîne. Page servie ≈ 26 règles CSS contre 279 dans le prototype ; 15 des 27 classes émises par l'accueil n'ont aucune règle CSS ; la police n'est jamais chargée.
- **Contrôles** : 13 PR cockpit vérifiées = corps de 17 caractères (`do-work: af-…`), 0 revue, 0 capture, un seul check (`Tests`), fusion automatique 6–10 min après ouverture.
- **Acceptation** : aucune avant fermeture. La Spec la reporte à « 7 jours d'usage réel ».

## 2. FAITS

### A. Planification
- Carte `af-arlph5` (15 décisions, fermée « Spec approved »). Prototype unique : `af-arlph5.11`, branche `origin/prototype/c01-home-screen`, `prototypes/c01-home-screen/index.html` (48 925 octets, variantes A/B/C/D) + README. **Aucune capture image sur la branche.**
- Choix de Benjamin (verbatim, `af-arlph5.11`) : « Je prefere la liste "Ce qui t'attends" de C avec la partie "Projets" de A. […] doit me permettre d'acceder en 1 clic là où je dois agir si besoin. » puis « 1 oui, 2 ok, 3 ok, 4 oui mais […], 5 oui ».
- Spec `af-oohx2x` (50 821 car., approuvée « et japprouve la spec » 16:21). Référence au prototype = **prose + nom de branche + 12 lignes de tokens `:root`** (§ « Base visuelle »), plus « Tout ticket UI compare ses captures PC et iPhone à la variante D ». Ni structure HTML, ni CSS de composants, ni image, ni lien de fichier.
- Spec, « Testing Decisions » : captures vs variante D = « Hors test automatique, par jugement de Benjamin ».
- Graphe `af-i67vl0` (approuvé « j'approuve le graphe » 17:55). Intent cité : « les vérifications visuelles ne sont présentes que pendant la plannification lors des prototypes de wayfinder, pas lors de l'implementation qui doit être autonome ». Mechanism (agent) : « Le worker joint des captures PC et iPhone, le relecteur indépendant les compare à la variante D. »

### B. Tickets
- 25 tickets, tous `closed`, cible `factory-worker`, formule `mol-do-work`. T01–T10 = préalables usine/producteurs (PR 348–357, 371). Cockpit : T11 #355, T12 #359, T13 #361, T14 #363, T15 #369, T16 #360, T17 #362, T18 #358, T19 #373, T20 #379, T22 #380, T23 #370, T24 #372, T25 #367. T21 (prototype page projet) : aucune PR.
- Tous étiquetés `vertical_slice`, mais le **scope déclaré** est un découpage par dossier : T11 = `lib/cockpit/core/**` + `ui/base/**` ; T19 = `lib/cockpit/projects/**` + `ui/projects/**` ; T22 = `lib/cockpit/ui/project-page/**`. **Seul T11 possède `server.py`/`process.py`** (le point d'assemblage).
- Corps type (T12, T19, T22) : « What to build » en prose, critères « Un test montre… », puis « Captures PC et iPhone, claires et sombres, jointes au PR et comparées à la variante D par le relecteur ». Le prototype n'apparaît que dans le contrat global : « le prototype de l'accueil (variante D) est sur la branche prototype/c01-home-screen ». Aucun ticket ne cite un ticket frère, un gabarit commun ni un système de composants.
- **Aucun ticket d'assemblage, de navigation, d'intégration ou d'acceptation finale** parmi les 25.
- T21 : démarré 17:57, parqué `blocked` 18:05, choix de Benjamin 21:55 (« je veux pouvoir switcher entre la vue tableau (choix 1) et la vue bande (choix 3) »). `docs/planning/c01-cockpit-v2/**` n'existe pas sur main.

### C. Résultat
- Code : `bin/cockpit` → `core/process.py` → `core/server.py` ; 6 443 lignes Python dans `lib/cockpit/`, **aucun fichier .html/.css/.js** (HTML et CSS en chaînes Python). Un processus tourne (`cockpit: running (pid 1182)`).
- Routes servies : `/`, `/api/status`, `/api/requests`, `/api/health`, `POST /api/health/recheck`, `POST /api/actions/*`. Tout le reste = 404.

| Ticket | Module construit | Importé par le code servi ? |
|---|---|---|
| T11, T12, T13, T14, T16 | core, requests, actions, health | oui |
| T15 | `requests/sources/*` (Spec/graphe à approuver, rituels, HITL), `ui/journal` | non |
| T17 | `notify/*` (Pushover), `ui/notify` | non |
| T18 | `heartbeat/emitter.py` | non |
| T19, T20 | `projects/*`, `ui/projects/page.py` (section Projets, bouton Accepter) | non |
| T22 | `ui/projects/project_page.py` ; lien `/projet/<id>` sans route | non |
| T23, T24 | `stop/driver.py`, `ui/stop` | non |
| T25 | `access/tailscale.py` (bannière « Déconnecté » servie) | partiel |

- Le non-câblage est **écrit dans le code** : `project_page.py` : « Wiring a real `/projet/<id>` HTTP route […] is deferred past this ticket's declared scope, the same precedent T19/T20/T21 set » ; `ui/notify/render.py` : « the T18 heartbeat emitter is the precedent for "built but not wired" » ; `requests/sources/__init__.py` : « is the wiring ticket's job » ; idem `stop/driver.py`, `notify/engine.py`, `docs/COCKPIT.md` (« left to a later ticket »). T13/T14 ont câblé en marquant « Out-of-scope touch ».
- Écarts visuels (prototype D → `/` servi) :

| Prototype variante D | Livré |
|---|---|
| `header.topbar` (marque), ligne d'état santé + fraîcheur | un `<header class="cockpit-headline">` texte |
| `.inbox` : liste courte + détail à côté (PC), feuille (iPhone) | `<ul><li>` avec chaque demande dépliée ; pas de liste/détail |
| zone « Projets » : cartes, stepper, puces « À toi de jouer » cliquables | absente de `/` |
| 279 règles CSS | ~26 ; non stylées : `cockpit-requests`, `cockpit-request-level`, `-quoi`, `-pourquoi`, `-meta`, `cockpit-option`, `cockpit-option-recommande`… |
| police chargée (`<link>` Google Fonts) | `font-family` nommée, aucun chargement |
| bascule de thème | `prefers-color-scheme` seul |

- `ui/projects/tokens.py` (CSS Projets + page projet, ~50 règles) n'est injecté dans aucune page servie.

### D. Processus
- 13 PR lues : `reviews=0`, `reviewDecision=''`, `image_refs=0`, auteur et fusion `benjamin-hurand` (pr-autopilot). Seuls commentaires : rejets autopilot (CI rouge, conflit) sur #360, #372, #373.
- Tests : T11/T12/T13/T14/T16 passent par le seam HTTP (processus réel sur faux gc/bd). T15, T17, T18, T19, T20, T22, T23 **importent des fonctions internes** (`from cockpit.ui.projects.page import render_projects_section`…), alors que le contrat dit « Aucun test n'appelle une fonction interne ». Aucun test HTTP ne mentionne la section Projets.
- CI = un job `Tests` (`bin/ci-run-tests`). Aucune vérification de scope, de capture ni de contrat de test.
- `mol-do-work` : lire, implémenter, PR, finaliser ; **aucune étape de revue**. `docs/DELIVERY.md` : « The standalone `claude-reviewer` template was retired 2026-09-28 […] no formula or prompt ever dispatched it » ; profil STANDARD : « review only when change risk or repository policy requires it ».
- Remontées pendant le convoi (26 beads hors tickets) : uniquement mécaniques (`[ci]`, `[autopilot] PR stuck`, `[on-order-failed]`, 4 propositions outillage). **Aucune Planning Exception, aucun NEEDS BENJAMIN sur le câblage manquant** (hors choix T21).

### E. Acceptation
- Fermeture du convoi = autoclose ; Spec et graphe fermés par l'order `planning-artifacts-close` (« Convoy … closed »). Rien ne vérifie le produit.
- La Spec place l'acceptation après : « N = 7 jours consécutifs d'usage réel ». L'étape « Accepté » est un clic dans le cockpit — bouton construit par T20, non câblé.

## 3. Cause → effet

| # | Maillon | Cause (fait) | Effet (fait) |
|---|---|---|---|
| 1 | Artefact de planification | Le prototype reste sur une branche jamais fusionnée, sans capture ; la Spec n'en transporte que 12 lignes de tokens + prose | Seule la palette arrive dans `ui/base/tokens.py` |
| 2 | Découpage | Scopes par dossier ; `server.py` dans le seul T11 ; aucun ticket d'assemblage | 8 tickets (+ T25 en partie) livrent des modules sans appelant |
| 3 | Entrée worker | Critères = « Un test montre… » ; cible visuelle = une ligne identique partout, renvoyant à une branche | Un test sur fonction de rendu satisfait le ticket |
| 4 | Comportement worker | « declared_scope » + précédent T18 ; le report est noté en docstring, jamais remonté | « built but not wired » devient la norme dès T18 (fusionné 20:02), cité comme précédent par T17, T23, T22 |
| 5 | Revue | Le graphe confie la fidélité à un « relecteur indépendant » qui n'existe dans aucune formule | 0 revue, 0 capture sur 13 PR |
| 6 | Portes | CI = tests seuls ; autopilot fusionne sur vert | Vert ≠ servi ; fusion en 6–10 min |
| 7 | Acceptation | Autoclose à « tous les enfants fermés » ; jugement humain reporté après clôture | Convoi, Spec et graphe fermés sans que l'app ait été regardée |

## 4. INFÉRENCES (les miennes)

- La phrase de Benjamin sur les vérifications visuelles a été traduite en mécanisme reposant sur un relecteur inexistant : le contrôle visuel a disparu sans que personne ne le décide.
- La règle `declared_scope` a agi contre l'assemblage : câbler exigeait une « out-of-scope touch », deux workers l'ont faite, les suivants ont suivi le précédent inverse.
- L'étiquette `vertical_slice` était nominale : une tranche verticale traverserait jusqu'à la route servie.
- Les tests HTTP de T11–T16 montrent que le seam prévu fonctionnait ; il n'a simplement pas été exigé ticket par ticket.

## 5. NON VÉRIFIÉ

- Si un worker a ouvert le prototype ou lancé l'app (transcripts de session non lus). Indice seulement : les tokens de `tokens.py` sont identiques au bloc de la Spec.
- Rendu réel à l'écran (app non lancée, aucune capture existante) : écarts déduits du code.
- Les 12 PR non lues (348–354, 356–358, 371) : hors cockpit UI, sauf #358 (T18).
- Fidélité de `project_page.py` au prototype `prototype/c01-project-page` (non comparée ; de toute façon non servie).
- Ce que sert exactement le processus pid 1182 (version du code chargée non contrôlée).
