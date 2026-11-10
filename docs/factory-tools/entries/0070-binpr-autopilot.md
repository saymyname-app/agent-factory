## `./bin/pr-autopilot` — fusion et réveil de livraison

Toutes les trois minutes, ce robot sans modèle arme les PR éligibles, puis
recopie la preuve des PR fusionnées sur leur bead (`merge_result`, SHA, numéro
et branche cible). Un rattrapage historique reste volontairement silencieux :
le Mayor n'est réveillé que si un bead encore `open`/`in_progress` attend
réellement ce travail (`blocks` ou `gc.waiting_on`) ; une fusion que rien
n'attend, même récente, ne le réveille plus (af-yzo8fo.3 : 8 réveils en 42
heures répondus « rien à avancer »). Le message unique part de l'identité
explicite `pr-autopilot`, jamais de `human`; un passage ultérieur voit
`merge_result` et ne le renvoie pas.

Ainsi, le rattrapage complète les preuves sans réveiller le Mayor pour des
fusions anciennes, tandis qu'une livraison récente ou bloquante réveille le
Mayor immédiatement.

Le robot ne touche qu'aux PR ouvertes depuis une branche du dépôt lui-même par
un des comptes GitHub de l'opérateur (`config/operator.toml`,
`github_logins`). La PR d'un fork ou d'un autre auteur est laissée à un
humain : ni armée, ni fusionnée, ni relancée, ni étiquetée, ni transformée en
bead. Liste vide : rien n'est armé et le passage compte une erreur
(af-996mmd, `docs/DELIVERY.md`, « Outside authors are left to a human »).

Chaque appel `gh`/`gc` est borné, et rien de nouveau ne démarre après 90
secondes (`PR_AUTOPILOT_BUDGET_SECONDS`) ; passé l'arrêt dur de 100 secondes,
aucun appel n'est plus lancé. Le passage entier est en plus arrêté à 105
secondes (`PR_AUTOPILOT_STOP_SECONDS`, + 5 s de kill), 10 secondes sous le
délai de 120 secondes de son ordre : sous une forte charge (load 15m ~30), un
passage sain peut l'atteindre sans appel bloqué. Un passage ainsi coupé ne
perd rien, le suivant relit tout trois minutes plus tard ; il est donc reporté
(sortie 0, avec `pass deferred (n of 3 in a row, loadavg …)`), et seuls trois
passages coupés de suite sortent 2 (`PR_AUTOPILOT_DEFER_LIMIT`). Le compte est
tenu dans `.gc/runtime/pr-autopilot-deferred-passes` et remis à zéro par un
passage qui finit (`af-pmbhlh`).

---

