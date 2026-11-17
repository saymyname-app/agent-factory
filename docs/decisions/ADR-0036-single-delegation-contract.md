# ADR-0036 : un seul contrat de délégation ; Benjamin garde une liste fermée, les agents décident le reste et le disent une fois par jour

- Statut : Accepté
- Date : 2026-11-16
- Autorité : Benjamin, session Claude Code Windows 1e93b356 « Analyse totale de l'usine », 16/11/2026 entre 16:38 et 16:50 Paris ; consigné sur `af-q55qqx`, décision 9
- Portée : `agents/mayor/prompt.template.md` (rôle, propositions de classe `decision`, rapport groupé), toute session qui écrit au nom de Benjamin (`--actor`, `--by`, `--approved-by`, `--words`)
- Remplace : « agents propose, Benjamin decides » (prompt du Mayor, 25/09/2026) et les cinq délégations successives que relève le §4 du rapport (16/10, 17/10, 22/10, 25/10 « pour toutes décisions », 31/10)
- Garde : la liste fermée et les invariants anti-arrêt de l'ADR-0016 ; les deux classes de l'ADR-0029 ; l'arbitrage du Mayor de l'ADR-0035

Intent (Benjamin, ses mots, 16/11/2026) : « Oui, un ADR unique », option
du rapport : « un ADR qui remplace “agents propose, Benjamin decides” et tes
5 délégations successives ». Contenu tranché dans `af-q55qqx` : reviennent à
Benjamin l'intention produit, les seuils de la cible, B1 et les Outcomes, et
la liste fermée de l'ADR-0016 ; tout le reste est délégué, avec l'agent qui
décide enregistré et un rapport groupé une fois par jour ; un geste au nom
de Benjamin n'est accepté que s'il est authentifié.

Mechanism (interprétation agent) : les points 1 à 5 ci-dessous. Le code des
portes (`escalation-door`, `proposal-door`) est adapté à l'étape J3 du
plan (ADR-0037, `af-q55qqx.1`) : le point 1 est le champ `motif` de
`escalation-door benjamin` (hors liste, la demande va au Mayor) ; le point 3
est écrit par `escalation-door repondre` pour tout acteur autre que Benjamin.

## Contexte

Le rapport du 16/11 (§3 F5, §4) mesure deux défauts opposés. D'un côté,
202 escalades, dont environ 7 relevaient de la liste fermée de l'ADR-0016 ;
11 approbations sur 11 en « recommandé » depuis le 31/10 : l'accord de
Benjamin était devenu un tampon. De l'autre, des décisions enregistrées
sous son nom alors qu'il dormait (`af-yowfs9`, 12/10), parce que
`--actor benjamin` est déclaratif. Les cinq délégations successives, chacune
écrite dans un document différent, n'ont corrigé ni l'un ni l'autre.

## Décision

1. **Ce qui revient à Benjamin, et rien d'autre :**
   - l'intention produit ;
   - les seuils de `FACTORY_OBJECTIVE.md` ;
   - B1 (tester lui-même le produit) et l'acceptation des Outcomes ;
   - la liste fermée de l'ADR-0016 : élargir l'exposition de données
     personnelles réelles, détruire au-delà de toute récupération, sortir du
     système (dépense, tiers, publication), un effet qu'on ne peut pas
     défaire par un revert et une migration réversible ; et les actes
     ADMIN (hôte, accès, secrets, production).
2. **Tout le reste est décidé par un agent**, sans attendre Benjamin : choix
   techniques, écarts techniques, retraits ou découpages de tickets,
   réparations, propositions de classe `decision` hors de la liste du
   point 1. Le Mayor décide pour l'exploitation de l'usine et ses
   propositions ; la session opérateur décide pour la planification
   (`docs/PLANNING_DELEGATION.md`). Une décision qui ne sait pas dans quelle
   case elle tombe va à Benjamin.
3. **L'agent qui décide est enregistré**, sur le Bead concerné : métadonnée
   `gc.decided_by=<identité réelle de la session>` et un commentaire qui
   commence par `Décision déléguée (ADR-0036) :`, avec ce qui est décidé,
   pourquoi, et comment revenir en arrière. Pour une proposition :
   `bin/proposal-door accepter|rejeter|reporter … <identité de l'agent>`.
4. **Un rapport groupé une fois par jour.** Au premier tour après 08:00
   Paris, s'il n'existe pas encore pour la date, le Mayor écrit un Bead
   fermé `Rapport des décisions déléguées — JJ/MM/AAAA`, label
   `delegation-report` : chaque `Décision déléguée (ADR-0036)` des
   dernières 24 h (quoi, qui, retour arrière), puis les demandes ouvertes
   pour Benjamin. Benjamin peut renverser toute décision du rapport ; ce
   renversement est une révision ordinaire. La notification sur mobile
   viendra avec J3.
5. **Aucun geste au nom de Benjamin sans authentification.** Un
   `--actor benjamin`, `--by benjamin`, `--approved-by benjamin` ou des
   `--words` attribués à Benjamin ne sont acceptés que s'ils citent un
   message vérifiable de lui : identifiant d'une session ou d'un message de
   chat en direct, commentaire GitHub de son compte, ou geste du Cockpit
   sous son identité. Sans cette référence, l'acteur enregistré est
   l'agent. Un accord général, une recommandation ou une phrase ancienne ne
   valent pas réponse à une décision précise. Les portes le vérifieront par
   code à J3 (référence obligatoire) et J11 (identité par rôle).

## Ce qui est retiré

Une règle ajoutée en retire une (`FACTORY_OBJECTIVE.md`, principe 5). Ce
contrat retire :

- la phrase « agents propose, Benjamin decides » du prompt du Mayor ;
- « Benjamin decides » pour toute proposition de classe `decision` (ADR-0029)
  hors de la liste du point 1 ;
- les cinq délégations successives comme sources d'autorité : leurs
  décisions déjà prises restent valables, mais une nouvelle décision se
  fonde sur ce seul ADR.

## Conséquences

- Ce qui atteint Benjamin se réduit à la liste du point 1, cible : au plus
  une sollicitation par jour (`FACTORY_OBJECTIVE.md`, principe 3).
- Il voit tout ce qui a été décidé sans lui, une fois par jour, et peut le
  renverser.
- Risque accepté : un agent décidera parfois autrement que lui. La parade
  est le retour arrière enregistré, comme dans l'ADR-0016.
- Retour arrière : revert de la PR de cet ADR ; les décisions déjà prises
  sous ce contrat restent tracées sur leurs Beads.
