# Runbook — l'usine vous a réveillé (ou vous vous réveillez et voulez vérifier), pas de session PO ouverte

Ce document répond à une seule situation : un push a atterri sur votre
téléphone (ou vous ouvrez le cockpit sans raison précise) et vous n'avez ni
session PO ouverte, ni envie de lire l'audit complet à 4h du matin. Il donne
le strict nécessaire pour savoir si c'est grave, et quoi faire si oui.

Pour la procédure complète d'arrêt/redémarrage : `RUNBOOK_STOP_AND_RESTART.md`.
Pour ce que chaque outil cité ici fait exactement : `FACTORY_TOOLS.md`.

---

## 0. Le push vous a déjà dit pourquoi

Depuis le 2026-09-17 (PR #70), un push ntfy.sh arrive sur votre téléphone
quand : une décision vous attend (`gc.needs_benjamin`), la campagne est
bloquée pour une raison qui n'est ni une fenêtre admin ni une limite de
fournisseur, ou le garde-fou a un avertissement. Un push qui redevient
« tout va bien » (all-clear) veut dire que c'est déjà résolu — ne rouvrez
rien, rendormez-vous.

Si vous ouvrez le cockpit sans avoir reçu de push : c'est probablement une
vérification volontaire, pas une urgence. Passez quand même par le
diagnostic ci-dessous, il prend 30 secondes.

---

## 1. Diagnostic en trois commandes

Depuis un téléphone ou un PC, dans un terminal WSL (`wsl -d Ubuntu-24.04`) :

```bash
cd /home/benja/agent-factory
./bin/mayor-campaign status   # un ERROR ici = boucle de réveil MORTE, pas au repos
./bin/factory-guard --check-only
gc doctor 2>&1 | tail -1
```

- `mayor-campaign status` avec `"state":"running"` et `"failure_count":0` :
  la campagne est vivante. Le reste de ce document ne s'applique
  probablement pas.
- `factory-guard --check-only` qui finit par `healthy` : rien à réparer.
- `gc doctor` : ne comptez que les `✗` (échecs), pas les `⚠` (avertissements,
  souvent consultatifs — voir `FACTORY_TOOLS.md` pour le tri déjà fait).

Si les trois sont propres et que vous avez quand même reçu un push : ouvrez
le cockpit (`http://127.0.0.1:8383` ou son URL téléphone) et lisez le
panneau « Aujourd'hui » — la cause y est affichée en une phrase.

---

## 2. Tableau de décision par symptôme

| Ce que vous observez | Ce que c'est | Quoi faire maintenant |
|---|---|---|
| `mayor-campaign status` répond `ERROR` ou ne répond pas | la boucle de réveil est morte (pas un repos) | passez à la §3 |
| Cockpit inaccessible, `curl http://127.0.0.1:8383` ne répond pas | le PC a redémarré (Windows ne relance pas WSL tout seul — D9, ADMIN, pas encore automatisé) | `RUNBOOK_STOP_AND_RESTART.md` §3 (redémarrage), ou attendez le matin si rien d'urgent ne dépend du cockpit cette nuit |
| Campagne bloquée, cause = fenêtre `admin` ou limite fournisseur (`limit`) | délibéré ou auto-résolutif | **rien à faire** — un fournisseur épuisé revient seul à la réinitialisation du quota (`./bin/provider-failover status` pour voir quand) |
| Campagne bloquée, cause = `decision` (`gc.needs_benjamin`) | une vraie décision vous attend | lisez la cause dans le cockpit ou `gc bd show <bead>` ; si ça peut attendre le matin, ça peut attendre — la campagne continue sur le reste (ADR-0016 : une décision produit ne met en pause que le produit, jamais l'échelle d'inactivité) |
| Campagne bloquée, cause = `durable_failure` (3 échecs consécutifs du sentinelle) | le mécanisme lui-même est peut-être cassé | plus sérieux que les autres lignes — regardez `gc.campaign_last_error` sur le bead de coordination (`af-1vr4`) ; si ce n'est pas clair, ça peut attendre le matin, mais notez-le, ce n'est pas un cas auto-résolutif |
| Un ordre échoue en boucle (`gc events --type order.failed`) | depuis le 2026-09-17 (`bin/on-order-failed`), un bead est déjà filé et le Mayor déjà mailé après 5 échecs en 3h | **rien à faire à 4h du matin** — c'est exactement pour ça que ce mécanisme existe désormais ; regardez-le le matin |
| Une session s'est arrêtée sans drainer proprement (`session.stranded`) | depuis le 2026-09-17 (`bin/on-session-stranded`), ses beads en cours sont déjà rouverts automatiquement | **rien à faire** |
| Une PR reste `DIRTY`/bloquée plusieurs passages | depuis le 2026-09-17 (`bin/pr-autopilot`), un bead est filé après le deuxième passage stagnant | **rien à faire à 4h du matin** — regardez le matin |

La ligne à retenir : la plupart des pannes qui réveillaient quelqu'un avant
le 2026-09-17 se réparent maintenant seules, ou se contentent de déposer un
bead que le Mayor traitera de lui-même. Ce qui reste vraiment à vous, la nuit,
tient sur une seule ligne : **la boucle de réveil elle-même est morte**, ou
**Windows a redémarré et rien n'est revenu**.

---

## 3. La boucle de réveil est morte : quoi faire

```bash
gc supervisor status        # le superviseur d'abord, toujours
gc doctor
./bin/factory-guard         # répare seul la dérive de branche et la sauvegarde
```

Si le superviseur tourne mais que la sentinelle ne l'est pas :

```bash
gc order list | grep mayor-campaign   # doit tourner toutes les minutes
./bin/mayor-campaign sentinel          # relance-la à la main, zéro token
```

Si ça ne repart pas après ça, c'est un cas pour une vraie session PO le matin,
pas pour un geste de plus à 4h du matin. Notez ce que vous avez déjà essayé
(pour ne pas le refaire), et rendormez-vous.

---

## 4. Ce qu'il ne faut jamais faire à 4h du matin, fatigué

- `wsl --unregister` — supprime la distribution. Il n'y a pas de retour en
  arrière.
- Éditer `city.provider.toml` à la main — c'est un fichier **généré** ; vos
  changements disparaîtront et rien ne préviendra personne.
- `bd init --force` ou `bd init --reinit-local` — peut créer un store Dolt
  parasite (`OPERATIONS.md`, section « Split-store »).
- `git checkout` dans `/home/benja/agent-factory` (la racine vive) — c'est le
  runtime en cours d'exécution, pas juste un dossier de code. Utilisez un
  `git worktree`.
- Forcer un redémarrage Dolt (`pkill -KILL dolt` ou équivalent) — coupe la
  purge de son journal en plein vol. `RUNBOOK_STOP_AND_RESTART.md` §2.4
  explique la bonne séquence (`SIGTERM`, jamais `SIGKILL`).
- Fusionner une PR à la main parce que ça semble plus rapide — `pr-autopilot`
  s'en charge tout seul dès que la vérification requise passe ; une fusion
  manuelle contourne la revue de réversibilité.

Si un de ces gestes vous semble nécessaire à 4h du matin, c'est le signal
qu'il faut attendre une vraie session plutôt que de continuer seul.

---

## 5. Si tout est vert mais que ça vous inquiète quand même

Ouvrez le cockpit, lisez le panneau « Aujourd'hui », fermez-le. La Factory
est conçue depuis les vagues 0-2 de l'audit du 2026-09-17 pour ne jamais
rester silencieusement bloquée : chaque échec chronique se dépose désormais
en bead et se mail lui-même, sans vous attendre. S'il n'y a pas de push sur
votre téléphone, il n'y a probablement rien qui a besoin de vous cette nuit.
