# Runbook — arrêter et redémarrer l'usine proprement

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

---

## 1. Avant de couper — capturer la preuve « avant »

Sans ces chiffres, vous ne pourrez rien prouver au redémarrage.

```bash
cd /home/benja/agent-factory
./bin/mayor-campaign status          # un ERROR ici = boucle morte, pas repos
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

### 2.1 Bloquer la campagne — en premier

Sinon la sentinelle peut réveiller un agent en plein arrêt.

```bash
./bin/mayor-campaign block --mayor \
  --kind admin --owner Benjamin \
  --cause "<pourquoi, et qui l'a autorisé>" \
  --action "<ce qui se passe à la fin de la fenêtre>"
```

**Piège** : `--mayor` est obligatoire. C'est un garde « transition délibérée »,
pas une revendication d'identité — l'auteur réel se déclare dans `--cause`.
Nommez-y explicitement qui demande et qui autorise : le Mayor lit ce champ et
peut prendre une recommandation du PO pour une décision de Benjamin.

**Piège corrigé le 2026-09-16** : avant le correctif, une fois le contrôleur
arrêté, ce blocage `admin` était écrasé par un diagnostic `source_failure`
(« Le contrôleur ou sa capacité à travailler n'est pas confirmé »). Une fenêtre
planifiée et une panne réelle se lisaient à l'identique. Le blocage `admin`
survit désormais avec sa cause, son propriétaire et son action.

### 2.2 Drainer les agents, suspendre la cité

```bash
gc stop        # endort les sessions (reason: city-stop) ET désenregistre la cité
gc suspend
gc session list      # toutes doivent être « asleep »
./bin/factory-cockpit stop
```

### 2.3 Piège majeur — le GC Dolt n'est *pas* une opération à froid

`gc maintenance dolt-gc` tourne **à l'intérieur du superviseur**. Or `gc stop`
désenregistre la cité, donc après l'étape 2.2 la commande répond
`supervisor not running (controller-down)`.

→ Faites le GC Dolt **avant** `gc stop`, ou **après** le redémarrage (§5).
Mieux : laissez la boucle hebdomadaire s'en charger (voir §7).

### 2.4 Arrêter Dolt en lui laissant le temps de vider son journal

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

### 2.5 Seulement maintenant, couper la VM

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

Dans cet ordre :

```bash
gc supervisor start
gc resume            # la cité était suspendue
gc start             # ré-enregistre et adopte les sessions
./bin/factory-cockpit start
./bin/mayor-campaign resume --mayor
```

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
./bin/mayor-campaign status # state=running, failure_count=0, candidat cohérent
gc doctor 2>&1 | tail -1    # comparer au chiffre de la §1 et expliquer chaque écart
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8383   # 200
```

Puis recomptez les beads exactement comme en §1 et comparez **store par store**.

- Les **ouvertes** doivent être identiques.
- Les **fermées** peuvent avoir augmenté de quelques unités : des beads
  `order-tracking` se ferment pendant l'arrêt/redémarrage. C'est normal.
- Une **baisse**, où que ce soit, n'est jamais normale : arrêtez-vous et
  cherchez avant de relancer la campagne.

Si quelque chose ne revient pas, réparez-le **avant** de continuer.

---

## 5. Pour mémoire — ce qui n'a pas besoin de cette procédure

- La sauvegarde hors machine des stores est continue : le pack
  `core/jsonl-archive` exporte et pousse vers le dépôt privé
  `benjamin-hurand/agent-factory-archive` toutes les 15 minutes.
- `factory-guard` sauvegarde seul ce qui n'existe que sur cette machine, y
  compris l'arbre de travail, vers `refs/factory-guard/snapshots/<utc>`.
- La compaction Dolt tourne toute seule chaque semaine depuis le 2026-09-16.

---

## 6. Si la cité ne revient pas

1. `gc supervisor status` — le superviseur d'abord, toujours.
2. `gc doctor` — lisez les `✗` avant les `⚠`.
3. `./bin/factory-guard` — il répare seul la dérive de branche et la sauvegarde.
4. Les stores Dolt sont dans `.beads/dolt` ; la restauration hors ligne est
   décrite dans `OPERATIONS.md` (Backup / restore).
5. Le store legacy retiré le 2026-09-16 est conservé, non supprimé, dans
   `.beads/embeddeddolt.retired-20260916`, avec une archive vérifiée dans
   `~/factory-cold-backups/`.

---

## 7. Réglages posés le 2026-09-16

| Réglage | Avant | Après | Pourquoi |
|---|---|---|---|
| `.wslconfig` `processors` | absent | `12` | le guest pouvait saturer les 24 cœurs et étouffer Windows |
| `.wslconfig` `memory` | `10GB` | `8GB` | pic réel observé ~3,7 Go ; Windows n'avait aucune réserve |
| `[maintenance.dolt] enabled` | absent | `true` | la compaction n'arrivait que si un humain la remarquait |
| `core/jsonl-archive` remote | absent | dépôt privé | les exports ne quittaient jamais la machine |
