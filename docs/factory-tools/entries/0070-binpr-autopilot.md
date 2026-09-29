## `./bin/pr-autopilot` — fusion et réveil de livraison

Toutes les trois minutes, ce robot sans modèle arme les PR éligibles, puis
recopie la preuve des PR fusionnées sur leur bead (`merge_result`, SHA, numéro
et branche cible). Un rattrapage historique reste volontairement silencieux :
le Mayor n'est réveillé que si `mergedAt` date d'au plus une heure, ou si un
bead encore `open`/`in_progress` attend réellement ce travail (`blocks` ou
`gc.waiting_on`). Le message unique part de l'identité explicite
`pr-autopilot`, jamais de `human`; un passage ultérieur voit `merge_result` et
ne le renvoie pas. La fenêtre peut être ajustée par
`PR_AUTOPILOT_RECONCILE_WAKE_WINDOW_SECONDS` pour l'exploitation ou les tests.

Ainsi, le rattrapage complète les preuves sans réveiller le Mayor pour des
fusions anciennes, tandis qu'une livraison récente ou bloquante réveille le
Mayor immédiatement.

---

