# Évaluation de la file de fusion GitHub — af-t3tm88

Intent (Benjamin, ses mots, 2026-10-12) : « Traitons » le suivi `af-t3tm88`
signalé dans la rétrospective comme une évaluation incomplète.
Mechanism (interprétation agent) : terminer la lecture des preuves disponibles,
corriger la documentation et protéger le déclencheur CI existant. Ce travail
ne change aucun ruleset et ne vaut pas acceptation définitive de l'essai.

## Verdict au 12 octobre 2026

La fusion par la file fonctionne sur les 13 PR #539 à #551. Pour chacune,
le commit fusionné est celui du run `merge_group` vert. Aucun de ces 13 runs
ne chevauche le suivant : le gain de débit de plusieurs PR simultanées reste
non mesuré. Aucun groupe rouge n'existe dans cet échantillon : le comportement
de `pr-autopilot` après éviction pour échec reste non éprouvé en réel.

La recommandation est de conserver l'essai, sans lui attribuer un gain de
vitesse non mesuré. La décision de conservation définitive reste à Benjamin
(le contrat de l'item distingue essai et conservation). Le propriétaire de
l'item lit les prochaines observations depuis GitHub ; Benjamin n'a pas à
relayer l'état des PR.

## Configuration lue en direct

Ruleset `AF-main-protection` (23626687), dépôt public `saymyname-app/agent-factory` :
`merge_queue`, SQUASH, 5 builds simultanés au maximum, groupes de 1 à 5,
ALLGREEN, timeout des checks 60 minutes, attente minimum 30 minutes (minimum
de groupe à 1). Check obligatoire `Tests`; strict up-to-date désactivé.

`bin/pr-autopilot` utilise déjà `gh pr merge --auto --squash --delete-branch`.
La commande entre dans la file lorsqu'elle est requise ; aucune option
`--admin` n'est utilisée. Les restrictions auteur/fork, migration et profil
de projet restent actives. La logique BEHIND reste dans l'outil partagé :
aucune suppression globale ni changement des dépôts produit.

## Mesures

Toutes les heures ci-dessous sont Europe/Paris. La durée est celle entre
`createdAt` et `updatedAt` du run terminé, pas une mesure CPU ni le délai
total de la PR. Source : `gh run list --limit 100`, filtré sur `merge_group`,
et `gh pr list --state merged --limit 30`; correspondance des SHA vérifiée.

| PR | Run créé (Paris) | PR fusionnée (Paris) | Durée observée du run | Preuve CI |
|---|---|---|---|---|
| [#539](https://github.com/saymyname-app/agent-factory/pull/539) | 11/10 20:04:38 | 11/10 20:11:38 | 392 s | [38162286176](https://github.com/saymyname-app/agent-factory/actions/runs/38162286176) |
| [#540](https://github.com/saymyname-app/agent-factory/pull/540) | 11/10 20:22:51 | 11/10 20:30:33 | 430 s | [38163562463](https://github.com/saymyname-app/agent-factory/actions/runs/38163562463) |
| [#541](https://github.com/saymyname-app/agent-factory/pull/541) | 11/10 21:01:18 | 11/10 21:08:57 | 427 s | [38166252825](https://github.com/saymyname-app/agent-factory/actions/runs/38166252825) |
| [#542](https://github.com/saymyname-app/agent-factory/pull/542) | 11/10 22:30:10 | 11/10 22:37:25 | 416 s | [38172470520](https://github.com/saymyname-app/agent-factory/actions/runs/38172470520) |
| [#543](https://github.com/saymyname-app/agent-factory/pull/543) | 11/10 23:47:53 | 11/10 23:55:02 | 404 s | [38177840221](https://github.com/saymyname-app/agent-factory/actions/runs/38177840221) |
| [#544](https://github.com/saymyname-app/agent-factory/pull/544) | 12/10 02:50:51 | 12/10 02:58:08 | 405 s | [38189576691](https://github.com/saymyname-app/agent-factory/actions/runs/38189576691) |
| [#545](https://github.com/saymyname-app/agent-factory/pull/545) | 12/10 07:17:55 | 12/10 07:25:12 | 415 s | [38207329424](https://github.com/saymyname-app/agent-factory/actions/runs/38207329424) |
| [#546](https://github.com/saymyname-app/agent-factory/pull/546) | 12/10 07:40:03 | 12/10 07:47:29 | 414 s | [38208935358](https://github.com/saymyname-app/agent-factory/actions/runs/38208935358) |
| [#547](https://github.com/saymyname-app/agent-factory/pull/547) | 12/10 08:09:35 | 12/10 08:16:28 | 405 s | [38211183633](https://github.com/saymyname-app/agent-factory/actions/runs/38211183633) |
| [#548](https://github.com/saymyname-app/agent-factory/pull/548) | 12/10 08:56:22 | 12/10 09:03:43 | 421 s | [38215031956](https://github.com/saymyname-app/agent-factory/actions/runs/38215031956) |
| [#549](https://github.com/saymyname-app/agent-factory/pull/549) | 12/10 12:21:50 | 12/10 12:28:17 | 369 s | [38235847538](https://github.com/saymyname-app/agent-factory/actions/runs/38235847538) |
| [#550](https://github.com/saymyname-app/agent-factory/pull/550) | 12/10 12:59:16 | 12/10 13:06:16 | 398 s | [38239742197](https://github.com/saymyname-app/agent-factory/actions/runs/38239742197) |
| [#551](https://github.com/saymyname-app/agent-factory/pull/551) | 12/10 14:55:12 | 12/10 15:02:55 | 436 s | [38252101041](https://github.com/saymyname-app/agent-factory/actions/runs/38252101041) |

Sur ces 13 groupes verts : médiane 414 s,
minimum 369 s, maximum 436 s. Une PR isolée paie
ce deuxième run après son run `pull_request`. La référence précédente
« environ 90 minutes pour 8 PR » est historique (`bd comments af-t3tm88`),
sur une autre configuration et charge : elle ne prouve pas une accélération
actuelle, et aucune comparaison avant/après à charge égale n'est disponible.

## Ce que les preuves ne disent pas

- Débit à plusieurs PR : aucun chevauchement observé. Ne pas créer des PR
  sans utilité ni scinder une livraison uniquement pour produire un chiffre.
- Éviction d'un groupe rouge : non observée. L'outil lit les checks de la
  tête de PR, pas explicitement les événements de sortie de file. Sa règle
  « retry once » concerne le run de cette tête, pas une preuve de limitation
  des réinsertions après un échec de groupe. Risque à vérifier, pas incident
  reproduit ; ne pas injecter un échec dans la file de la Factory en activité.
- La preuve de fermeture `deliver-close` reste fondée sur le run de la tête
  de PR et le commit fusionné. La protection GitHub ajoute le contrôle du
  groupe ; aucune nouvelle affirmation de preuve interne n'est ajoutée.
- `bin/enable-strict-main-protection` appartient au mode antérieur : le
  relancer n'est pas la procédure de retour de la file. Son rollback retire
  strict, il ne retire pas le ruleset merge_queue.

Fin de l'évaluation complète : conservation ou retrait décidé par Benjamin,
observation de plusieurs PR présentes ensemble avec délai mesuré, et verdict
sur l'éviction rouge (observation réelle ou reproduction isolée explicitement
distinguée). Jusqu'alors l'item reste ouvert avec ces limites, pas « tout prouvé ».

## Contrôle ajouté

`tests/ci-workflow-cost-test.sh` refuse un workflow sans déclencheur
`merge_group`, sans `checks_requested`, sans branche `main`, ou sans groupe
de concurrence distinct par run hors PR. Ces contrôles protègent le câblage
existant ; ils ne simulent pas la sémantique GitHub ni l'éviction rouge.

## Références primaires

- [Configuration et fonctionnement de la file](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue) : les limites de groupe ne combinent pas les builds ; les groupes rouges sont retirés.
- [Commande gh pr merge](https://cli.github.com/manual/gh_pr_merge) : passage par la file requise, `--admin` la contournerait.
- Sources locales : `.github/workflows/ci.yml`, `bin/pr-autopilot`,
  `bin/enable-strict-main-protection`, `docs/DELIVERY.md`.
