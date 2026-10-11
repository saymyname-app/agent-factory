# Runbook — arrêter et redémarrer l'usine proprement

> Systèmes retirés (Cockpit V1, ntfy, campagne, file/statut/preview produit,
> contrat de release, axes d'amélioration) : code et documents retirés, gardés par l'historique
> Git (non fiable, voir `decisions/PRE_REFACTOR.md`).

Procédure exécutée et vérifiée le 2026-09-16 sur la cité `agent-factory`.
Chaque piège décrit ici a réellement été rencontré pendant cette fenêtre : ce
n'est pas une procédure théorique.

**Critère de réussite** : ce n'est pas « ça a redémarré », c'est « rien n'a été
perdu ». La §4 est la seule partie non négociable.

---

## 0. Quand faut-il vraiment arrêter ?

La plupart des opérations n'exigent **aucun** arrêt. N'ouvrez une fenêtre que
pour ce qui suit :

| Opération | Arrêt nécessaire ? |
|---|---|
| `%USERPROFILE%\.wslconfig` (plafonds CPU/RAM) | **Oui** — plus `wsl --shutdown` |
| Retirer un store Dolt legacy (`.beads/embeddeddolt`) | **Oui** — rien ne doit tenir de handle |
| `gc doctor --fix` (hooks, instructions-file) | Non, à chaud |
| GC/compaction Dolt (`gc maintenance dolt-gc`) | **Non** — voir le piège §2.3 |
| Sauvegarde hors machine, commits, PR | Non, à chaud |
| Balayage de rétention (`gc order sweep-tracking`) | Non, à chaud |

Groupez tout ce qui exige l'arrêt dans **une seule** fenêtre.

**Rien de tout ça ci-dessus ne passe par le cockpit** : un arrêt complet
(WSL, Dolt, la VM) reste une procédure de ce runbook, jamais un geste
cockpit (spec af-oohx2x §"Arrêt propre et redémarrage" : « gc stop complet
reste au runbook seulement »). Le cockpit couvre un cas plus étroit : mettre
l'usine en pause (`gc suspend` / `gc resume`, rien d'autre) sans rien couper
côté PC, WSL ou Dolt, pour éteindre le PC ou jouer sans perdre de travail
(T23 af-s5e3yo, T24 af-j2mkpa — `lib/cockpit/stop/driver.py`).

- **Bouton « Arrêter proprement l'usine »** : suspend la cité (jamais `gc
  stop`, jamais `gc stop --force`), suit l'arrêt jusqu'à « Arrêtée
  proprement à HH:MM » avec un bilan de 0 perte, et propose « Forcer l'arrêt
  » seulement après 30 min sans aucune progression (jamais de bascule
  automatique).
- **Bouton « Redémarrer »** : appelle `gc resume`, rien d'autre, puis prouve
  la reprise — « Reprise vérifiée à HH:MM » quand chaque travail d'avant
  l'arrêt est repris sans réattribution, sinon « Reprise avec écarts » avec
  la liste (demande À faire dans « Ce qui t'attend »).
- Le bouton d'arrêt s'affiche d'abord en **mode essai** (texte : « ceci est
  l'essai réel de l'arrêt propre ») ; il ne devient un bouton normal qu'après
  une trace persistée d'un essai réel réussi (un arrêt propre suivi d'une
  reprise vérifiée), déclenché par Benjamin depuis le cockpit.
- Les deux boutons ne remplacent la §2/§3 ci-dessous que pour ce cas précis
  (pause sans toucher WSL/Dolt/la VM) ; tout le reste de ce runbook — GC Dolt,
  arrêt de la VM, redémarrage complet, preuve d'intégrité — reste manuel.

---

## 1. Avant de couper — capturer la preuve « avant »

Sans ces chiffres, vous ne pourrez rien prouver au redémarrage.

```bash
cd /home/benja/agent-factory
./bin/factory-guard                  # doit finir par « healthy »
gc doctor 2>&1 | tail -1             # notez le nombre de warnings
for r in . rigs/saymyname-backend rigs/saymyname-frontend; do
  (cd "$r" && echo "$r open=$(gc bd list --status open | grep -c .) closed=$(gc bd list --status closed | grep -c .)")
done
du -sh .beads/dolt
```

`factory-guard` doit être **healthy avant** de couper. S'il signale du travail
qui n'existe que sur cette machine, laissez-le le sauvegarder d'abord.

---

## 2. Arrêt ordonné

L'ordre compte. Chaque étape empêche la suivante de mal se passer.

### 2.1 Drainer les agents, suspendre la cité

```bash
gc stop        # endort les sessions (reason: city-stop) ET désenregistre la cité
gc suspend
gc session list      # toutes doivent être « asleep »
```

`gc stop` **en premier**, toujours : c'est lui qui retire la cité de la liste
du superviseur, et c'est à cela que `bin/factory-revive` reconnaît un arrêt
délibéré. Un `gc supervisor stop` lancé sans ce `gc stop` est traité comme un
arrêt que personne n'a demandé, et défait en 7 minutes au plus (§3).

### 2.2 Piège majeur — le GC Dolt n'est *pas* une opération à froid

`gc maintenance dolt-gc` tourne **à l'intérieur du superviseur**. Or `gc stop`
désenregistre la cité, donc après l'étape 2.2 la commande répond
`supervisor not running (controller-down)`.

→ Faites le GC Dolt **avant** `gc stop`, ou **après** le redémarrage (§5).
Mieux : laissez la boucle hebdomadaire s'en charger (voir §7).

### 2.3 Arrêter Dolt en lui laissant le temps de vider son journal

C'est le point sensible du « sans perte significative ».

```bash
gc supervisor stop
sleep 2
pgrep -x dolt && pkill -TERM -x dolt     # SIGTERM, jamais SIGKILL
for i in $(seq 1 20); do pgrep -x dolt >/dev/null || break; sleep 1; done
pgrep -a dolt                             # doit être vide
lsof +D .beads 2>/dev/null | grep -v COMMAND   # doit être vide
```

**Observé le 2026-09-16** : la sortie propre de Dolt a fait passer `.beads/dolt`
de 511 Mo à 379 Mo à elle seule. Un `SIGKILL` aurait perdu ce compactage et
laissé un journal à rejouer.

### 2.4 Seulement maintenant, couper la VM

```powershell
# depuis PowerShell, côté Windows
Copy-Item "$env:USERPROFILE\.wslconfig" "$env:USERPROFILE\.wslconfig.before-<date>"
# ... éditer ...
wsl --shutdown
```

`wsl --shutdown` coupe **toutes** les distributions WSL, y compris celle de
Docker Desktop. C'est un impact attendu, pas un incident.

---

## 3. Redémarrage

Dans cet ordre, qui est celui de `./bin/factory-boot` :

```bash
./bin/provider-failover apply --no-reload           # city.provider.toml doit exister avant de démarrer
systemctl --user start gascity-supervisor.service   # sans effet s'il tourne déjà ; pas « gc supervisor start »
gc supervisor status                                # doit répondre « Supervisor is running »
./bin/factory-build-gates                           # contrôles de formule de chaque rig, avant le contrôleur
./bin/cockpit start                                 # processus séparé de gc : aucune autre commande ne le relance
gc resume                                           # la cité était suspendue
gc start                                            # ré-enregistre et adopte les sessions
```

**Le superviseur démarre par son unité systemd**, pas par `gc supervisor
start`, dès que l'unité est installée (`systemctl --user cat
gascity-supervisor.service` répond). `gc supervisor start` en lance un hors
de l'unité ; l'unité, que `gc start` active ensuite, trouve la place prise et
échoue en boucle toutes les 5 secondes (2026-10-08 : 84 démarrages échoués en
7 minutes), et le superviseur qui tourne n'a pas l'environnement de l'unité :
c'est l'état de la §6 point 1. Sans unité installée, et seulement là :
`gc supervisor start`.

**`./bin/factory-build-gates`** remet dans chaque rig les contrôles de
formule gérés, avant que le contrôleur puisse lancer un workflow ; idempotent.
Il est nécessaire après un re-clone de rig ou un changement de version d'un
pack fait pendant la fenêtre. Non vérifié : qu'un `wsl --shutdown` seul le
rende nécessaire.

**Cette séquence est liée à `bin/factory-boot`** par
`tests/runbook-restart-sequence-test.sh` : le test lance `factory-boot` dans
un bac à sable, relève les commandes qu'il exécute, et échoue si l'une d'elles
manque au bloc ci-dessus ou n'y est pas à la même place. Une étape ajoutée à
`factory-boot` s'ajoute donc ici dans le même changement. Seul `gc resume`
est propre à la séquence manuelle : `factory-boot` ne reprend jamais une cité
suspendue.

**Le Cockpit ne revient pas tout seul** (2026-10-09 : après la fenêtre
planifiée de 17:36 à 17:55, heure de Paris, il est resté arrêté jusqu'à ce
que Benjamin le remarque). C'est un processus séparé de `gc` : `wsl
--shutdown` le coupe, et ni le superviseur ni `gc start` ne le relancent.
`./bin/cockpit start` est idempotent, sans effet si une instance tourne déjà ;
`factory-boot` le fait à son étape « 2b. Cockpit ».

**Après un redémarrage non planifié** (reboot Windows, coupure) : ces mêmes
étapes sont rejouées, de façon idempotente, par `./bin/factory-boot`, que la
tâche planifiée Windows « Good Morning Agent Factory » lance à l'ouverture de
session. Il ne défait jamais un arrêt délibéré : une cité suspendue reste
suspendue. Journal :
`.gc/runtime/factory-boot.log`. Après une fenêtre **planifiée**, suivez la
séquence manuelle ci-dessus, et non `gc resume` suivi de `./bin/factory-boot` :
ce que fait `factory-boot` sur une cité désenregistrée par `gc stop` puis
suspendue n'a jamais été essayé (af-8j6lsz, 2026-10-10), et ne s'essaie que
dans une fenêtre d'arrêt.

**Arrêt que personne n'a demandé** (2026-10-08 : le script d'essai d'un
ouvrier a lancé `gc supervisor stop` sur l'usine vivante, arrêtée 56 minutes) :
`./bin/factory-revive`, appelé toutes les 5 minutes par un minuteur systemd
utilisateur (`factory-revive.timer`, posé une fois par `./bin/factory-revive
install` ; `systemctl --user list-timers` le montre), relance par `factory-boot` un
superviseur arrêté alors que la cité est encore enregistrée, puis ouvre un
ticket et une escalade « Mayor d'abord ». Délai : 7 minutes au plus. Il ne
fait rien après un `gc stop` (arrêt délibéré, §2.1) et ne reprend jamais une
cité suspendue. Journal : `.gc/runtime/factory-revive.log`. Détail :
`FACTORY_TOOLS.md` (`./bin/factory-revive`).

**Racine vivante en retard** : `factory-guard` avance désormais lui-même la
racine (fast-forward seul, arbre suivi propre, branche épinglée) quand des PR
fusionnés n'y tournent pas encore — plus besoin de `git pull` à la main.
`factory-guard` est un order : superviseur arrêté, il ne tourne pas, et le
code fusionné pendant l'arrêt n'atteint pas la racine. Rien à faire à la
main : son premier passage après la relance (5 minutes au plus) rattrape le
retard, et `factory-revive` borne la durée de l'arrêt.

**Piège** : `gc reload` ne suffit pas pour tout. Certaines sections de
`city.toml` — `[maintenance.dolt]` notamment — ne sont lues qu'au **démarrage du
contrôleur**. `gc reload` répond alors « No config changes detected » et le
réglage reste inactif. Il faut un `gc stop && gc start`.

---

## 4. Preuve d'intégrité — la partie non négociable

Un redémarrage n'est pas un succès tant que ceci n'est pas vérifié.

```bash
./bin/factory-resources     # doit montrer le plafond CPU déclaré
./bin/factory-guard         # doit finir par « healthy »
gc doctor 2>&1 | tail -1    # comparer au chiffre de la §1 et expliquer chaque écart
./bin/cockpit status        # doit répondre « cockpit: running (pid …) »
```

Puis recomptez les beads exactement comme en §1 et comparez **store par store**.

- Les **ouvertes** doivent être identiques.
- Les **fermées** peuvent avoir augmenté de quelques unités : des beads
  `order-tracking` se ferment pendant l'arrêt/redémarrage. C'est normal.
- Une **baisse**, où que ce soit, n'est jamais normale : arrêtez-vous et
  cherchez avant de relancer l'usine.

Si quelque chose ne revient pas, réparez-le **avant** de continuer.

---

## 5. Pour mémoire — ce qui n'a pas besoin de cette procédure

- La sauvegarde hors machine des stores est continue : le pack
  `core/jsonl-archive` exporte et pousse vers le dépôt privé
  `saymyname-app/agent-factory-archive` toutes les 15 minutes.
- `factory-guard` sauvegarde seul ce qui n'existe que sur cette machine, y
  compris l'arbre de travail, vers `refs/factory-guard/snapshots/<utc>` du
  remote `backup` (le dépôt privé d'archive), ou d'`origin` sans ce remote.
- La compaction Dolt tourne toute seule chaque semaine depuis le 2026-09-16.

---

## 6. Si la cité ne revient pas

1. `gc supervisor status` — le superviseur d'abord, toujours. S'il répond
   alors que `systemctl --user status gascity-supervisor` affiche
   `activating (auto-restart)`, un superviseur tourne **hors** de son unité
   (lancé par `gc supervisor start`) et l'unité échoue en boucle à côté de
   lui, toutes les 5 secondes (vu le 2026-10-08). L'usine fonctionne, mais ce
   superviseur n'a pas l'environnement de l'unité. Remède, geste ADMIN :
   tuer ce seul processus par son numéro, à un instant sans order en cours ;
   l'unité reprend la place en 5 secondes et réadopte les sessions (fait le
   2026-10-08 à 05:34, aucun agent interrompu). `factory-boot` ne crée plus
   cet état : il démarre le superviseur par son unité quand elle est
   installée, et la séquence manuelle de la §3 fait de même.
2. `gc doctor` — lisez les `✗` avant les `⚠`.
3. `./bin/factory-guard` — il répare seul la dérive de branche et la sauvegarde.
4. Les stores Dolt sont dans `.beads/dolt` ; la restauration hors ligne est
   décrite dans `OPERATIONS.md` (Backup / restore).
5. Le store legacy retiré le 2026-09-16 est conservé, non supprimé, dans
   `.beads/embeddeddolt.retired-20260916`, avec une archive vérifiée dans
   `~/factory-archive/factory-cold-backups/`.

---

## 7. Réglages posés le 2026-09-16

| Réglage | Avant | Après | Pourquoi |
|---|---|---|---|
| `.wslconfig` `processors` | absent | `12` | le guest pouvait saturer les 24 cœurs et étouffer Windows |
| `.wslconfig` `memory` | `10GB` | `8GB` | pic réel observé ~3,7 Go ; Windows n'avait aucune réserve |
| `[maintenance.dolt] enabled` | absent | `true` | la compaction n'arrivait que si un humain la remarquait |
| `core/jsonl-archive` remote | absent | dépôt privé | les exports ne quittaient jamais la machine |
| `include = ["city.provider.toml"]` | absent | présent | le fournisseur de chaque cible est choisi automatiquement (ADR-0018) |
