# Lots de PR, relecture, CI et « berger » : comment font les autres

Ticket af-8km43c.12 de la carte af-8km43c, 2026-10-10, lectures terminées à 02:18 (Paris). Sous-agent de la session po-agent/24d9240f. Branche jamais fusionnée `research/af-8km43c-lots-ailleurs`. Lecture seule : rien changé, rien lancé.

Demande (Benjamin, ses mots, 2026-10-10) : « Comment font les autres software factory pour gérer les lots de PR avec review et CI et github sheperd etc ».
Question ouverte de la carte : sur un lot rouge, l'agent en lecture seule de la marche 2 peut-il corriger lui-même ?

## Résumé

1. Aucune source lue ne décrit une file de fusion dont le processeur corrige le code d'un lot rouge sous des bornes écrites. Les files (Zuul, GitHub, Mergify, Graphite, Trunk, Shopify) éjectent ou coupent le lot ; elles ne réparent jamais.
2. Le pack Gas City de l'usine l'interdit en toutes lettres au Refinery : « FORBIDDEN: Writing code to fix failures. You are a merge processor. » Un rouge dû à la branche retourne au vivier d'ouvriers avec un motif.
3. Seule exception lue : le README de Gas Town (l'ancêtre) dit que les MR en échec sont « either fixed inline or re-dispatched », sans aucune borne écrite.
4. Là où un agent répare, c'est l'agent attaché à UNE PR, avant la file : Stripe (2 tours de CI au plus, puis un humain), OpenAI (boucle jusqu'à satisfaction des relecteurs agents, escalade « only when judgment is required »), Claude Code auto-fix (pousse une correction « if one is clear », sinon demande).
5. Deux équipes abandonnent la porte au lieu de réparer dedans : Cursor (rôle d'intégrateur retiré, taux d'erreur accepté, passe de correction sur une branche « green ») et Yegge sur Wyvern (août 2026 : lots de dix + bissection abandonnés, tout entre, main reste rouge, les agents diagnostiquent en essaim).
6. « Shepherd » n'est pas un rôle de Gas Town ni de Gas City (mot absent du glossaire). C'est un nom de compétence communautaire pour « suivre une PR jusqu'à la fusion » ; le seul produit de première main équivalent est l'auto-fix de Claude Code.
7. Bornes écrites trouvées chez ceux qui laissent réparer : 2 tours de CI (Stripe), 3 cycles de réparation et 1 seul rejeu d'un job suspect (compétence `shepherd`), tests d'un code qu'on n'a pas écrit = demander d'abord (compétence `pr-shepherd`), sortie du périmètre = veto d'un juge (Spotify).
8. Tests instables : rejouer (OpenAI, Mergify, Chromium), tolérer N échecs de suite avant d'éjecter (Shopify : 3), comparer avec et sans le changement (Chromium), ouvrir un ticket (Stripe, Refinery).

## Vocabulaire

| Mot | Sens ici |
|---|---|
| Usine à agents | équipe ou système où des agents IA écrivent le code et ouvrent les PR, avec peu ou pas d'écriture humaine |
| File de fusion (merge queue) | robot qui teste « main + les PR en attente » avant de les faire entrer dans main |
| Lot (batch) | plusieurs PR testées ensemble par un seul run de CI |
| Spéculation | lancer en parallèle la CI de plusieurs états futurs possibles de main, en pariant que ceux de devant passeront |
| Bissection | couper un lot rouge en deux et retester chaque moitié pour isoler la PR fautive |
| Éjection | sortir une PR de la file ; elle retourne à son auteur |
| Test instable (flaky) | test qui échoue ou passe sans que le code ait changé |
| Refinery | dans Gas Town et le pack `gastown` de Gas City : l'agent qui tient la file de fusion d'un dépôt |
| Polecat | ouvrier éphémère de Gas Town : il code une tâche, pousse sa branche, disparaît |
| Witness | agent de surveillance de Gas Town : récupère les tâches orphelines, détecte les ouvriers bloqués ; n'écrit pas de code |
| Bead | ticket de Beads, le suivi de tâches de Gas Town / Gas City |
| Berger (shepherd, babysit) | agent ou compétence qui suit UNE PR après son ouverture : CI, commentaires de relecture, relances, jusqu'à ce qu'elle soit prête à fusionner |
| Juge | second modèle qui relit le diff d'un agent contre la consigne et peut opposer un veto |
| Tour de CI | un push suivi d'un run de CI |

## 1. Usines à agents

| Usine | Formation du lot | Relecture | CI avant / après fusion | Rouge | Réparation par un agent, bornes | Tests instables | Source |
|---|---|---|---|---|---|---|---|
| Pack `gastown` de Gas City (Refinery) | Aucun lot : une branche à la fois, rebasée sur la cible qui vient de bouger (« Sequential Rebase Protocol ») | Aucune relecture du code : il est même interdit au Refinery de lire le code de l'ouvrier pour le comprendre | Avant : commandes configurées (setup, typecheck, lint, build, test) sur la branche rebasée. Après : rien de décrit | Diagnostic « branch regression or pre-existing on target? ». Dû à la branche : bead rouvert avec `rejection_reason`, renvoyé au vivier de polecats, branche supprimée. Conflit de rebase : rebase annulé, renvoi, branche gardée | **Interdite** : « **FORBIDDEN**: Writing code to fix failures. You are a merge processor. » Seule latitude, dans le prompt et pas dans la formule : sur conflit, « Abort and reject to pool, or attempt trivial resolution ». Aucun plafond d'essais écrit | Le mot n'apparaît pas. Un échec déjà présent sur la cible : chercher un doublon, sinon ouvrir un bug P1, puis fusionner quand même ; « NEVER fix it yourself » | [formule](https://github.com/gastownhall/gascity-packs/blob/520e95cb22992a8a1017f7a60da267f203497c7e/gastown/formulas/mol-refinery-patrol.toml) (étape `handle-failures`), [prompt](https://github.com/gastownhall/gascity-packs/blob/520e95cb22992a8a1017f7a60da267f203497c7e/gastown/agents/refinery/prompt.template.md) |
| Gas Town (README) | « Refinery batches pending MRs » | Non décrite dans le README | Avant : « Runs verification gates on the merged stack ». Après : rien | « If red: bisects to isolate the failing MR, merges the good ones » ; « Bors-style merge queue — polecats never push directly to main » | **Oui, sans borne écrite** : « Failed MRs are isolated and either fixed inline or re-dispatched. » | Non décrit | [README](https://github.com/gastownhall/gastown/blob/649b832b7672bc7a2dbef26f5983aba6198b819b/README.md) (sections « Refinery » et « Merge Queue (Refinery) ») |
| Yegge, Wyvern / Wheelhouse (août 2026) | D'abord lots de dix avec bissection. Puis « Land Rush » : quand la file atteint 100, tout entre d'un coup | Par agents : « Fable design, Opus implementation, Fable review ». Humains : « in the short term, yes, keep reviewing agent code » | Avant : une porte de build d'environ 30 min. Après le Land Rush : main « generally stayed red » | La bissection bloquait tout : « We would get caught up in bisection loops and nothing would make forward progress. » Remplacée par « swarm diagnosis (_not_ bisection) » | Oui, sur main rouge, par des agents en essaim. Aucune borne écrite. Le texte dit qui diagnostique, pas qui écrit la correction | Non décrit | [essai](https://yegge.ai/essays/the-shape-of-things-to-come/) |
| Stripe, Minions | Aucun lot décrit : une PR par exécution | Humaine, obligatoire : « human-reviewed, but containing no human-written code » | Avant le push : lint local en boucle (moins de 5 s). Puis CI sélective sur plus de trois millions de tests. Après fusion : non décrit | Les correctifs automatiques des tests s'appliquent seuls ; un échec sans correctif retourne à l'agent | **Oui, l'agent auteur, 2 tours de CI au plus** : « we only have at most two rounds of CI » ; après le second push, « we send the branch back to its human operator for manual scrutiny » | Ticket automatique : « when our CI systems detect flaky tests, we create automated tickets that prompt users to fix the problem with a minion » | [partie 1](https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents), [partie 2](https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents-part-2) |
| OpenAI, « harness engineering » | Aucun lot : PR courtes, portes minimales | Par agents : « Humans may review pull requests, but aren’t required to. » | Avant : « minimal blocking merge gates ». Après : tâches de nettoyage régulières qui ouvrent des PR de refactorisation | Corrigé après coup : « corrections are cheap, and waiting is expensive » | **Oui, l'agent auteur, sans plafond chiffré** : il boucle « until all agent reviewers are satisfied », sait « Detect and remediate build failures », « Escalate to a human only when judgment is required », puis « Merge the change ». Les agents « often squash and merge their own pull requests » | Rejoués : « Test flakes are often addressed with follow-up runs rather than blocking progress indefinitely. » | [billet](https://openai.com/index/harness-engineering/) |
| Spotify, agent de fond (« Honk ») | Aucun lot : une PR par dépôt, par migration | Humaine, par l'équipe propriétaire (les PR sont fusionnées par les équipes) ; avant cela un juge LLM | Avant d'ouvrir la PR : vérificateurs déterministes, puis juge. « If one of the verifiers fails, the PR isn’t opened ». Réagir à la CI de la PR : seulement en projet (« enabling it to act on CI checks in GitHub pull requests ») | La PR n'est pas ouverte | Avant la PR seulement. Borne = le périmètre : le juge oppose son veto à un quart des sessions, d'abord pour sortie de consigne, par exemple « refactoring code or disabling flaky tests » ; l'agent se corrige alors une fois sur deux | Désactiver un test instable est cité comme une faute de l'agent | [partie 1](https://engineering.atspotify.com/2025/11/spotifys-background-coding-agent-part-1), [partie 3](https://engineering.atspotify.com/2025/12/feedback-loops-background-coding-agents-part-3) |
| Cursor, agents longue durée | Aucun lot, aucune porte : des centaines d'ouvriers poussent sur la même branche | Rôles planificateur / ouvrier ; un juge décidait de continuer, retiré ensuite | Non décrite. Exiger des commits 100 % corrects « caused major serialization and slowdowns » | Taux d'erreur accepté : « The error rate remains small and constant. » | Rôle d'intégrateur (« quality control and conflict resolution ») **retiré** : « created more bottlenecks than it solved ». Réparation diffuse par les autres agents, avec l'effet « Many agents would pile on and trample each other trying to fix the same issue. » Proposé : une branche « green » où un agent fait « a quick fixup pass before release » | Non décrit | [scaling agents](https://cursor.com/blog/scaling-agents), [self-driving codebases](https://cursor.com/blog/self-driving-codebases) |
| StrongDM | Non décrit | Interdite aux humains : « Code **must not be** reviewed by humans » | Remplacée par des scénarios tenus hors du dépôt, notés en probabilité (« satisfaction ») | Non décrit | Non décrit. Borne implicite : l'agent qui code ne voit pas les scénarios, car « A test, stored in the codebase, can be lazily rewritten to match the code. » | Non décrit | [site](https://factory.strongdm.ai/) |

Constat (lu) : aucune usine à agents de cette liste ne documente des lots de PR, sauf Gas Town et Wyvern, tous deux de Yegge. Les autres ont assez de machines pour tester chaque PR seule.

## 2. Les « bergers » : agents qui suivent une PR

| Outil | Ce qu'il suit | Ce qu'il corrige seul | Bornes écrites | Fusion | Source |
|---|---|---|---|---|---|
| Claude Code, auto-fix (première main, Anthropic) | Événements GitHub d'une PR : échec de CI, commentaire de relecture | « Claude investigates and pushes a fix if one is clear » | Demande ambiguë ou « architecturally significant » : il demande avant d'agir. Ne voit pas les conflits (GitHub n'émet pas d'événement). Exige l'application GitHub de Claude sur le dépôt. Aucun plafond d'essais écrit | Non décrite | [doc](https://code.claude.com/docs/en/claude-code-on-the-web) |
| GitHub Copilot, agent cloud (première main, GitHub) | Sa propre PR | Les changements qu'on lui demande dans la PR | Ne pousse que sur sa branche `copilot/` ; « cannot approve or merge a pull request » ; celui qui a demandé la PR ne peut pas l'approuver ; les workflows ne partent pas avant relecture, par défaut ; session de 59 min au plus | Jamais par lui | [risques](https://docs.github.com/en/copilot/concepts/agents/cloud-agent/risks-and-mitigations), [présentation](https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent) |
| Compétence `shepherd` (chrisbanes, communautaire) | PR ou MR ouvertes | « narrow formatting, lint, compile, or test failures » | Escalade pour « a failure that remains after three repair cycles » ; un job suspect est rejoué « once without code changes » ; « Never merge without explicit authority. » | Seulement sur autorisation | [SKILL.md](https://github.com/chrisbanes/skills/blob/main/skills/shepherd/SKILL.md) |
| Compétence `pr-shepherd` (metaswarm, communautaire) | Une PR, sondée toutes les 60 s | Lint, format, types, « Test failures in code YOU wrote » | « Test failures in code you didn't write » : approbation demandée d'abord ; pause à 4 h | Par l'utilisateur | [SKILL.md](https://github.com/dsifry/metaswarm/blob/main/skills/pr-shepherd/SKILL.md) |
| Gas Town / Gas City | — | — | Le mot « shepherd » est absent du glossaire de Gas Town. Le rôle voisin, Witness, « oversees Polecats and the Refinery » et n'écrit pas de code (« You do NOT implement code. ») | — | [glossaire](https://github.com/gastownhall/gastown/blob/649b832b7672bc7a2dbef26f5983aba6198b819b/docs/glossary.md), [prompt Witness](https://github.com/gastownhall/gascity-packs/blob/520e95cb22992a8a1017f7a60da267f203497c7e/gastown/agents/witness/prompt.template.md) |

Ce que « shepherd » recouvre : pas de sens établi. Ni GitHub, ni Anthropic, ni OpenAI, ni Gas Town n'emploient le mot pour un rôle. Il désigne, dans des compétences communautaires de 2026, la boucle « surveiller la CI et les commentaires d'UNE PR, corriger ce qui est étroit, relancer, s'arrêter à la porte de fusion ». Synonymes rencontrés : « babysit », « auto-fix ». Dans l'usine, cette boucle existe déjà en partie : `bin/pr-autopilot` suit les PR et ouvre un bead sur une PR rouge (note « main vert ou rouge », ligne « Qui répare »).

## 3. Files de fusion à grande échelle

Bors-ng, Prow Tide et les rollups de Rust sont dans la note « lots par script » ; Google, Meta et le jardinier de Chromium dans « main vert ou rouge ». Seul le nouveau figure ici.

| File | Formation du lot | Relecture | CI avant / après | Lot rouge | Réparation par agent | Tests instables | Source |
|---|---|---|---|---|---|---|---|
| Zuul (OpenStack) | Pas de lot : chaque changement est testé avec ceux de devant, en parallèle, dans une fenêtre (20 au départ, plancher 3) | Hors sujet (Gerrit) | Tout avant ; rien après | Le fautif sort ; ceux de derrière sont retestés sans lui. La fenêtre est divisée par deux à chaque échec, augmentée de un à chaque fusion | Aucune | Pas de mécanisme dédié : une file par projet pour qu'un projet instable ne ralentisse pas les autres | [gating](https://zuul-ci.org/docs/zuul/latest/gating.html), [options](https://zuul-ci.org/docs/zuul/latest/config/pipeline.html) |
| Uber SubmitQueue (2025) | Pas de lot : spéculation, avec un seuil de probabilité en dessous duquel un build n'est pas lancé. Les lots sont cités comme travail futur | Hors sujet | Tout avant | Seuls les changements dont le build passe entrent | Aucune | Non traité dans l'article | [arXiv 2501.03440](https://arxiv.org/abs/2501.03440) |
| Shopify | Lots de 8 ; la CI tourne sur 3 lots d'avance, sur une « predictive branch » | Avant l'entrée en file | Avant, sur la branche prédictive | Pas de bissection décrite : la première PR en échec sort | Aucune | Tolérance : on n'éjecte que « on the fourth consecutive failure » ; un vrai défaut se propage aux runs suivants, un test instable non | [billet](https://shopify.engineering/successfully-merging-work-1000-developers) |
| GitHub merge queue | Un build par entrée, cumulatif. Les tailles de groupe min et max règlent combien entrent ensemble, pas combien sont testées ensemble : « Merge limits do not combine `merge_group` builds. » | Selon les règles de la branche | Avant, sur l'événement `merge_group` | La PR en échec sort, la branche temporaire est refaite sans elle | Aucune | Délai d'attente des contrôles ; option pour laisser passer une entrée en échec si le groupe suivant est vert | [doc](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue) |
| Mergify | `batch_size` + attente maximale | Hors file | Avant, sur une PR brouillon de lot | Lot coupé jusqu'à isoler la fautive ; nombre de coupes plafonné (`batch_max_failure_resolution_attempts`) | Aucune | Rejeu automatique : `max_checks_retries`, 0 par défaut, recrée la PR de lot ; `skip_intermediate_results` laisse passer un échec intermédiaire si le lot suivant est vert | [lots](https://docs.mergify.com/merge-queue/batches/), [rejeux](https://docs.mergify.com/changelog/2026-03-18-automatic-ci-retries-in-merge-queue/) |
| Graphite | Lots de piles de PR (bêta privée) | Hors file | Avant | Deux stratégies : tester chaque pile du lot en parallèle (défaut), ou bissection (« fewer CI runs ») | Aucune | Mise en garde seulement : un échec instable éjecte et relance les runs de derrière | [doc](https://graphite.com/docs/merge-queue-optimizations.md) |
| Trunk | Lot formé quand la taille cible est atteinte ou le délai écoulé | Hors file | Avant | Bissection par moitiés ; taux de lots rouges conseillé « <10% » | Aucune | « Pending failure depth » : attendre le résultat des lots suivants avant de déclarer un lot rouge, pour éviter une bissection sur un échec passager | [doc](https://docs.trunk.io/merge-queue/optimizations/batching) |
| Chromium CQ | Pas de lot | Gerrit | Avant | Le changement n'entre pas | Aucune | Trois passes : avec le changement ; rejeu des tests en échec ; rejeu **sans** le changement. Rouge seulement si échec deux fois avec et succès sans : « it's assumed that the test is broken/flaky on tip of tree » | [doc CQ](https://chromium.googlesource.com/chromium/src/+/main/docs/infra/cq.md) |

## 4. Ce que cela dit pour l'usine

### 4.1 Qui laisse un agent corriger, et où

| Où la correction a lieu | Qui | Bornes écrites | Qui relit la correction |
|---|---|---|---|
| Sur la PR, avant la file, par l'agent auteur | Stripe, OpenAI, Claude Code auto-fix, compétences `shepherd` | 2 tours de CI (Stripe) ; 3 cycles (`shepherd`) ; « if one is clear » (Claude) ; jugement requis = humain (OpenAI) | Humain (Stripe) ; agents relecteurs (OpenAI) |
| Dans la file, par le processeur de fusion | Gas Town, d'après son README seulement | aucune | non dit |
| Dans la file, interdit | Pack `gastown` de Gas City ; toutes les files de la section 3 | sans objet | sans objet |
| Après l'entrée, sur main ou une branche rouge | Yegge (Wyvern), Cursor | aucune | agents |

Lu : aucune source ne décrit « l'agent qui désigne le suspect d'un lot rouge écrit aussi la correction », avec des bornes. Le cas le plus proche, le Refinery du pack que l'usine importe, sépare les deux exprès : il diagnostique (branche ou cible ?) et il lui est interdit d'écrire.

### 4.2 Pour la marche 2 (déductions de l'agent, pas des sources)

| Si l'agent de la marche 2 corrige dans le lot | Effet |
|---|---|
| Le lot contient du code qu'aucune PR d'origine ne porte | la preuve « batterie verte sur le lot qui contient la tête de la PR » (note « lots par script », condition 3) ne décrit plus ce qui est entré |
| La correction n'a ni ticket ni auteur | l'auteur de la PR fautive n'apprend rien ; la classe de défaut n'est pas corrigée |
| Il faut de toute façon une batterie de plus | écarter le suspect coûte une batterie ; corriger puis reprouver en coûte une aussi : sur un seul runner, corriger dans le lot ne gagne aucun run |
| L'agent peut rendre le lot vert en touchant le test | risque nommé par StrongDM (tests réécrits) et Spotify (tests instables désactivés) |

Forme qui tient les bornes lues ailleurs, si Benjamin veut qu'un agent corrige : la correction ne se fait pas dans le lot. Le script écarte le suspect (le lot repart sans lui, sans attendre) ; un agent pousse la correction sur la branche de la PR écartée, comme le fait déjà l'auteur. Bornes reprises des sources : un seul essai par PR écartée (Stripe en accorde deux tours, rejeu compris) ; interdiction de modifier ou désactiver un test (Spotify, StrongDM) ; correction étroite seulement, sinon retour à l'auteur (Claude Code, `shepherd`) ; la PR corrigée repasse l'étage court et rentre dans un lot suivant, donc la batterie relit la correction (aucune source ne dispense la correction de la CI). C'est le chemin « re-dispatched » de Gas Town, pas « fixed inline ».

Ce que les sources ne tranchent pas : si cette correction doit venir de l'agent auteur (contexte de la tâche) ou d'un agent neuf (contexte du lot rouge). Stripe et OpenAI gardent l'auteur ; le Refinery supprime la branche et renvoie au vivier, donc à un ouvrier neuf.

### 4.3 Tests instables

La règle retenue (« un fichier de test rouge est rejoué une fois ») est du côté strict : Shopify tolère 3 échecs de suite, Mergify laisse régler le nombre de rejeux, Chromium rejoue et compare sans le changement. Deux idées peu chères lues ailleurs et absentes de la carte :

| Idée | Chez qui | Ce que cela donnerait ici |
|---|---|---|
| Distinguer « rouge dû au lot » de « rouge déjà présent sur main » avant de chercher un suspect | Refinery (« pre-existing on target »), Chromium (« without patch ») | la marche 1 du script lit le dernier run de main : si le même fichier y est rouge, le lot n'est pas coupable |
| Ouvrir un ticket à chaque rejeu qui passe | Stripe, Refinery (bug P1, doublon cherché d'abord) | le rejeu ne masque pas l'instabilité ; verdict « sous-produit normal → automatisé » |

### 4.4 Relecture

Trois régimes lus : humain obligatoire (Stripe, Spotify, Copilot), agents seuls (OpenAI, Yegge, StrongDM), personne à la porte (Refinery, Cursor). Aucun ne place la relecture au niveau du lot : elle se fait par PR, avant la file. Un lot ne change donc rien à la relecture de l'usine.

## Non vérifié

- Les citations des pages Stripe, Spotify, Cursor, StrongDM, Yegge, Zuul, Shopify, GitHub, Mergify, Graphite, Trunk, Chromium, Copilot et des deux compétences `shepherd` ont été lues à travers l'outil de lecture web, qui passe la page par un petit modèle : elles peuvent être tronquées. Relues dans le texte brut : la formule et les prompts du pack `gastown`, le README de Gas Town, le billet d'OpenAI, la doc auto-fix de Claude Code.
- Gas Town « fixed inline » : lu dans le README seulement. Le code Go du Refinery de Gas Town et ses éventuelles bornes n'ont pas été lus. Le README (lots + bissection) et le pack Gas City (une branche à la fois, écriture interdite) décrivent deux Refinery différents ; lequel reflète l'usage réel de Yegge aujourd'hui n'est pas établi.
- L'essai de Yegge décrit Wyvern / Wheelhouse, pas Gas City. La longueur exacte du texte et sa date précise (seulement « août 2026 ») n'ont pas été vérifiées.
- Spotify : « relecture humaine » est déduit de « teams across Spotify have merged » ; l'article ne dit pas si une fusion automatique existe.
- Uber : seul le résumé et un extrait de la version HTML ont été lus ; l'article de 2019 (EuroSys) reste non lu.
- GitHub merge queue : le libellé exact de l'option qui laisse passer une entrée en échec n'a pas été recopié.
- Mergify : la page dédiée aux tests instables a renvoyé 404 ; le défaut `max_checks_retries = 0` vient d'un résumé de recherche du journal des changements, pas de la page de référence.
- Graphite : la page de doc sur les lots a renvoyé 404 ; lu sur la page « optimizations ».
- Non cherchés faute de temps : Devin, Factory.ai, Ramp, Amp, Aviator, l'outil de fusion de Meta.
- `gc --help` (binaire local) ne liste aucune commande `refinery` ni `merge-queue` ; l'aide des sous-commandes `gc github` et `gc converge` n'a pas été ouverte.
- Section 4.2 : arithmétique et forme proposée sont des déductions de l'agent ; rien n'a été essayé.
