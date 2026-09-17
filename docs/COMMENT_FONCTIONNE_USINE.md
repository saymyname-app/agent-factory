# Comment fonctionne l'usine — vue d'ensemble en français

Tous les autres documents de `docs/` sont en anglais, écrits pour les agents
qui y travaillent. Celui-ci est pour vous, Benjamin : une vue d'ensemble en
français, du principe général jusqu'aux mécanismes concrets, sans supposer
que vous avez déjà lu le reste.

Pour le détail opérationnel outil par outil : `FACTORY_TOOLS.md`. Pour
l'arrêt/redémarrage : `RUNBOOK_STOP_AND_RESTART.md`. Pour une panne la nuit :
`RUNBOOK_4H_DU_MATIN.md`. Pour retrouver le bon document selon la question :
`CONTEXT_INDEX.md`.

---

## 1. En une phrase

L'usine (« Agent Factory ») est un programme qui fait travailler des agents
IA (Claude, Codex) sur du code, en boucle, sans que vous ayez à leur donner
d'instructions à chaque étape — vous fixez des objectifs et des limites, elle
enchaîne le travail toute seule, et elle est censée vous prévenir seulement
quand une vraie décision vous revient.

Elle tourne sur votre PC, dans une machine virtuelle Linux (WSL), dans le
dossier `/home/benja/agent-factory`.

---

## 2. Le vocabulaire de base

| Terme | Ce que c'est |
|---|---|
| **Gas City** (`gc`) | le logiciel qui fait tourner l'usine : il démarre les agents, leur donne du travail, surveille qu'ils avancent. C'est le moteur. |
| **Bead** (`bd`) | une unité de travail — un ticket, en plus structuré : statut, priorité, métadonnées, dépendances. Tout ce que l'usine fait est un bead avant, pendant et après. |
| **Dolt** | la base de données qui stocke les beads. C'est une base SQL versionnée comme du code (elle a des commits, des branches). |
| **Formule** | la « recette » qu'un agent suit pour un type de travail donné — par exemple « corrige ce bug, ouvre une branche, ouvre une PR ». Une formule est une suite d'étapes écrites en texte, que l'agent lit et exécute. |
| **Ordre** (`order`) | une tâche automatique qui se déclenche seule, soit à intervalle fixe (toutes les 3 minutes, par exemple), soit sur un événement précis (« un ordre vient d'échouer »). La plupart des ordres ne coûtent aucun token : ce sont des scripts déterministes, pas des appels à un modèle. |
| **Session** | un agent en train de tourner, avec sa propre fenêtre de contexte, en train de suivre une formule sur un bead donné. |
| **Le Mayor** | l'agent particulier qui pilote la campagne produit : c'est lui qui décide quel prochain résultat produit livrer, qui répond aux décisions qu'on lui pose, et qui diagnostique quand quelque chose ne va pas. |
| **La campagne** | la boucle qui enchaîne les résultats produit sans intervention humaine : dès qu'un résultat est livré, elle passe au suivant. |
| **Rig** | un dépôt de code que l'usine gère (par exemple `saymyname-backend`, `saymyname-frontend`). L'usine elle-même (`agent-factory`) est aussi un rig, un peu particulier (voir §7). |

---

## 3. La boucle principale : la campagne

Le cœur de l'usine est une boucle très simple dans son principe :

1. Y a-t-il un résultat produit éligible à livrer (une fonctionnalité, un
   correctif priorisé) ? Si oui, le Mayor le prend, crée le travail
   nécessaire, et suit sa livraison jusqu'à la fusion sur `dev`.
2. Sinon, y a-t-il un travail d'entretien de l'usine elle-même prêt à
   prendre ? (voir « l'échelle d'inactivité » ci-dessous)
3. Sinon, l'usine se repose — ce qui est un état normal, pas une panne.

Une **sentinelle** (`./bin/mayor-campaign sentinel`) tourne toutes les
minutes, sans modèle, et regarde où en est cette boucle. Si une action est
due, elle envoie un mail au Mayor pour qu'il la traite à sa prochaine
session. Ce mail est renvoyé jusqu'à trois fois si rien ne se passe, puis
l'usine considère que quelque chose est cassé et le signale (voir §6).

### L'échelle d'inactivité

« Rien à livrer côté produit » n'est pas la même chose que « rien à faire ».
Quand la file produit est vide, la sentinelle descend une échelle :

1. un bead d'entretien de l'usine déjà prêt et priorisé — un à la fois ;
2. un candidat déjà mis en file d'attente pour la « campagne Factory »
   (des améliorations de l'usine elle-même, décidées à l'avance) ;
3. une passe de durcissement des tests, au plus toutes les 12 heures ;
4. du ménage dans la documentation et le backlog, au plus toutes les 24
   heures ;

puis seulement là, elle se repose. Les fondations de cette échelle et des
échelons prévus mais pas encore remplis (les « axes » d'amélioration
permanents, l'entretien perpétuel) sont dans
`decisions/ADR-0016-standing-delegation-and-non-stop-campaign.md` ; leur
contenu concret est en cours (voir la file `goal=none`, §5).

---

## 4. Comment le travail se fait concrètement

Quand un agent reçoit du travail, il ne réinvente rien : il suit une
**formule**. Une formule décrit une suite d'étapes, chacune avec des
instructions précises (souvent des commandes shell à exécuter). Par exemple,
la formule la plus utilisée aujourd'hui (`mol-do-work`) dit : lis le bead,
fais le changement, vérifie-le, commite, ferme le bead avec sa preuve.

Une formule plus lourde (`mol-scoped-work`) isole le travail dans son propre
`git worktree`, ouvre une branche, une Pull Request sur GitHub, et attend que
la CI passe avant de considérer le travail terminé.

**Rien ne se fusionne sur `main` ou `dev` sans passer par une Pull Request et
sa vérification automatique (CI).** C'est une règle absolue de l'usine
(`AGENTS.md`) : même un agent autonome ne pousse jamais directement sur une
branche protégée.

Une fois la PR ouverte, un robot déterministe (`pr-autopilot`) arme la
fusion automatique de GitHub dès que la vérification requise (tests, build)
passe au vert. Personne n'attend, personne ne clique « merge » à la main.

---

## 5. Ce que vous voyez : le cockpit

`./bin/factory-cockpit open` ouvre une page web locale
(`http://127.0.0.1:8383`) qui répond à « où en est l'usine, là,
maintenant ? » sans jamais appeler de modèle pour l'afficher — c'est du
calcul déterministe sur l'état réel (beads, PR, ordres).

Le panneau « Aujourd'hui » montre l'activité du jour, les décisions en
attente, les avertissements du garde-fou. La file `goal=none` (menu
Factory/Produit) liste les chantiers d'amélioration de l'usine déjà décidés,
en attente que le Mayor les matérialise en travail exécutable — vous pouvez
la consulter avec `./bin/saymyname-product-queue list`.

Un accès téléphone existe (`./bin/factory-cockpit phone-enable`), et depuis
le 2026-09-17 un push arrive directement sur votre téléphone (via ntfy.sh)
quand une décision vous attend ou qu'un problème réel est détecté — voir
`RUNBOOK_4H_DU_MATIN.md`.

---

## 6. Comment l'usine se protège, et quand elle vous prévient

Trois couches, du plus mécanique au plus visible :

1. **`factory-guard`** — tourne en continu, répare seul ce qui peut l'être
   (une dérive de branche, un fichier de configuration généré disparu), et
   sauvegarde tout travail qui n'existerait que sur cette machine.
2. **`factory-watchdog`** et les ordres qui réagissent à un événement précis
   (un ordre qui échoue en boucle, une session qui meurt sans finir
   proprement) — ils dépassent la simple observation : ils déposent un bead
   et préviennent le Mayor par mail.
3. **Le contrat d'escalade unique** — une seule règle pour toute décision qui
   vous revient vraiment : `gc.needs_benjamin` est posé sur le bead
   concerné, un mail vous est envoyé, et la cause est visible dans le
   cockpit. Toujours les trois ensemble, jamais un seul. Une escalade
   n'arrête jamais le reste de la campagne : le Mayor continue sur ce qui
   reste éligible pendant que la décision attend.

Un signalement local (un ordre qui échoue, une PR bloquée) ne se lit **jamais**
comme un arrêt de toute la campagne — seule une vraie décision, une fenêtre
de maintenance, une limite de fournisseur épuisée ou une panne durable du
mécanisme lui-même la mettent en pause.

---

## 7. Deux dépôts un peu différents

L'usine gère trois dépôts Git : `saymyname-backend`, `saymyname-frontend`
(le produit), et `agent-factory` elle-même (l'usine qui les fait tourner).

Les deux premiers ont une branche `dev` (où la fusion automatique arrive) et
une branche `main` (la production, jamais automatisée — c'est vous qui
décidez du passage `dev → main`).

`agent-factory` n'a qu'une seule branche longue, `main` : ses propres
correctifs et améliorations y fusionnent automatiquement dès que leur test
passe, exactement comme sur `dev` pour le produit. C'est une décision
délibérée (2026-09-16) : sans ça, les correctifs de l'usine s'empilaient sans
jamais fusionner.

---

## 8. Pourquoi c'est construit comme ça — bref historique

Trois nuits de pannes silencieuses (2026-09-15/16) ont montré la même leçon
sous plusieurs formes : un système peut sembler « en bonne santé » (tous les
composants répondent) tout en étant complètement à l'arrêt (rien n'avance
depuis des heures) — santé et vivacité sont deux questions différentes. De là
sont nés le garde-fou de vivacité, le watchdog, le contrat d'escalade unique,
et le push téléphone.

Un audit complet du 2026-09-17 (`FACTORY_AUDIT_2026-09-17.md`) a ensuite
recensé méthodiquement tout ce qui restait silencieux ou dangereux dans le
mécanisme (une formule qui poussait directement sur `main`, des échecs
d'ordres jamais lus, des sessions mortes dont le travail restait bloqué pour
toujours) et a produit le plan en vagues qui a corrigé la plupart de ces
points le même jour — c'est ce plan que vous voyez avancer dans les PR
récentes du dépôt.

---

## 9. Pour aller plus loin

- Le détail de chaque outil (`factory-guard`, `factory-watchdog`,
  `mayor-campaign`, `provider-failover`, `factory-doctor`,
  `reversibility-check`) : `FACTORY_TOOLS.md`.
- Les décisions structurantes (pourquoi telle règle existe) : `decisions/`,
  indexées par sujet dans `CONTEXT_INDEX.md`.
- L'état produit SayMyName précisément : `./bin/saymyname-product-status`.
- Une panne qui vous réveille la nuit : `RUNBOOK_4H_DU_MATIN.md`.
