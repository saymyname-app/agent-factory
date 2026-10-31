# ADR-0035 : au plafond des tours de correction, le Mayor arbitre ; le compteur seul ne demande rien à Benjamin

- Statut : Accepté
- Date : 2026-10-28
- Autorité : Benjamin, chat central Codex « Reprendre le pilotage Factory » (01a1822b), 2026-10-28, relayé par Codex et consigné sur `af-npz9v1` (commentaire 29a9a693) ; mise en œuvre `af-npz9v1.40`
- Portée : `bin/correction-round` (arrêt au plafond, `grant --arbitrated`, `escalate`, consigne du tour), `lib/convoy_state.py` (`grant-correction --arbitrated`, `ARBITRATED_ROUNDS_MAX`), `agents/mayor/prompt.template.md`
- Précise : ADR-0033 (deux tours), ADR-0034 (tour exceptionnel, inchangé)

Intent (Benjamin, ses mots, 2026-10-28) : « J'aimerais qu'il ne faille plus
mon accord pour dépasser la limite de corrections. » ; « Ça, je veux que,
finalement, ça soit une décision automatique qui soit prise par toi ou, je
ne sais qui, qui peut avoir la capacité de prendre cette décision
automatiquement. »

Mechanism (interprétation agent ; précisée par la revue de Codex du
2026-10-28 14:49 Paris : pas de remontée humaine due au compteur ou au
délai seul, une borne aux relances aveugles, motif et cible traçables) :
au plafond, l'arbitre est le Mayor, par les portes existantes.

## Contexte

Un ticket encore refusé après son dernier tour (`bounds.correction_rounds`,
2) s'arrêtait `still_refused`, et `bin/correction-round` posait aussitôt
une demande à Benjamin : dérogation, tour exceptionnel (ADR-0034), Planning
Exception ou arrêt. BR (`af-eyc5ah`) le 28/10 : deux constats précis, liés,
corrigeables en un tour ; la décision n'avait rien d'un choix de produit,
mais elle attendait Benjamin.

## Décision

1. **Au plafond, le Mayor est réveillé, pas Benjamin.** L'arrêt au plafond
   (`still_refused`, un tour pris, aucun restant) envoie un mail au Mayor
   (`gc mail send mayor`) avec l'arrêt, les refus à la pointe, les tours
   arbitrés restants et les commandes. Pas `escalation-door mayor` : son
   sweep remonte à Benjamin après 2 h, une remontée due au seul délai.
   `bin/convoy-state stop-raised` l'enregistre ; un mail qui échoue est
   rejoué par la passe suivante. Les autres arrêts (avant tout tour) restent
   des demandes à l'opérateur, comme avant.
2. **Le Mayor peut accorder un tour arbitré**, un à la fois :
   `bin/correction-round grant CONVOI TICKET --arbitrated --approved-by <son acteur> --words "<motif>" --target <refus>...`.
   Refusé, sans rien écrire : par l'approbateur humain déclaré (un tour
   arbitré est une décision d'agent, jamais un accord humain ; l'humain
   garde `--exceptional`) ; sans motif ; sans cible, ou avec une cible qui
   n'est pas un refus à la pointe (Blocking Finding non soldé, état non
   observé) ; tant qu'une décision posée à l'opérateur par `escalate` est
   ouverte et sans réponse (seule l'ancienne demande due au compteur cède) ;
   sur un ticket qui n'est pas arrêté au plafond ; quand aucun
   tour ne s'ouvrirait (même pointe, session terminée sans corriger) ;
   au-delà de `ARBITRATED_ROUNDS_MAX` (2) tours arbitrés par ticket, la
   borne des relances aveugles. Le tour est gardé sous `grants` avec
   `arbitrated: true`, son motif et ses cibles ; la consigne de l'auteur
   (`brief.round`) les redit.
3. **À la borne, ou quand aucun tour ne s'ouvrirait, le Mayor diagnostique**
   et décide dans son périmètre : laisser le ticket arrêté, faire réparer
   une cause d'usine, replanifier. Un nombre de refus qui baisse est un
   signal de progrès, pas une preuve qu'un refus restant se corrige : le
   motif le dit.
4. **Benjamin n'est sollicité que pour une décision qui est la sienne** :
   `bin/correction-round escalate CONVOI TICKET --why "<décision>"` pose la
   demande d'avant (dérogation, tour exceptionnel tant qu'il est possible,
   Planning Exception, arrêt), avec ces mots comme raison. Ni le compteur
   ni le délai ne la posent.

Revue de code, Ticket Evaluation, critères et preuves sont inchangés : un
tour arbitré ne passe outre rien, il donne un tour de plus à l'auteur.

## Conséquences

- Un ticket au plafond peut coûter jusqu'à deux tours de plus sans
  Benjamin, chacun motivé et ciblé.
- Un ticket que le Mayor ne traite pas reste arrêté, visible, sans
  remontée automatique : c'est le prix de « pas de demande due au délai ».
- Le Mayor reçoit une décision de plus ; ses consignes la décrivent.

Revenir en arrière : remettre la demande à l'opérateur dans `raise_stop`
et retirer `grant --arbitrated`, en gardant la lecture de `arbitrated` et
`targets` dans `grants` (`correction_record`) et leur compte dans la borne.
Un revert intégral ramènerait le validateur aux seules clés d'avant : un
tour arbitré déjà écrit rendrait le ticket illisible.

## Preuve

`tests/correction-round-test.py` : un ticket arrêté au plafond réveille le
Mayor une fois et ne pose aucune demande ; le Mayor accorde deux tours
motivés et ciblés, refusés à l'approbateur humain, sans cible juste ou sans
motif, puis un troisième est refusé ; `escalate` pose la demande avec la
raison du Mayor.
