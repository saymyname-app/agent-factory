# ADR-0034 : revue ciblée après le premier passage, pas de jugement de fidélité visuelle, tour exceptionnel

- Statut : Accepté
- Date : 2026-10-23
- Autorité : Benjamin en conversation (2026-10-23, 16:07 Paris, chat Claude Code Windows) ; mise en œuvre `af-npz9v1.14`
- Portée : `bin/code-review` (questions fermées, périmètre ciblé, `show`), `formulas/mol-code-review.formula.toml`, `lib/convoy_state.py` (`open-code-review`, `record-code-review`, `grant-correction`), `bin/correction-round` (`grant --exceptional`, demande d'arrêt, consigne du tour)
- Précise : ADR-0033 (deux tours de correction) ; aligne la revue sur ADR-0032 (fidélité non bloquante)

Intent (Benjamin, ses mots, 2026-10-23 16:07 Paris) : « 3. ok pour ta
recommandation D1. » et « 4. je suis la recommandation que tu me donneras
pour ca, fait le choix parfait pour moi stp. »

Mechanism (interprétation agent, la recommandation retenue) : trois
changements. (1) La revue ne juge plus la fidélité visuelle au prototype, ni
dans la lecture des tests de critère, ni dans la question fermée
`amended_test`. (2) La première revue d'un ticket reste complète ; toute
revue suivante est ciblée : elle ne bloque que sur les constats non soldés
de la revue précédente et sur les lignes du ticket changées depuis la pointe
relue ; le reste est enregistré non bloquant, marqué pour la passe de fin.
(3) Au plafond des tours, l'approbateur humain déclaré peut accorder un
tour exceptionnel, une fois par ticket.

## Contexte

**Fidélité jugée par la revue.** ADR-0032 a retiré la fidélité visuelle de
ce qui bloque un ticket, mais la question fermée `amended_test` (« le test
de critère amendé observe-t-il encore son critère ? ») faisait juger au
relecteur la part « Rendu fidèle à la référence » d'un critère, et un « non »
devient un Blocking Finding par code. Cas réels : D « Analyses »
(`af-ten1sp`) F3.7 le 22/10 ; G1 (`af-wrxrmg`) F1.12 le 21/10, passé outre
par Benjamin.

**Revue rejouée en entier.** Au 2e tour, D a reçu 4 constats nouveaux : 2
déjà présents au premier passage et manqués, 1 créé par la correction, 1
contraire à ADR-0032. C1 (`af-lzti7w`) le 21/10 : 5 constats nouveaux, dont
un présent au commit déjà accepté. Une revue rejouée sur tout le diff trouve
du nouveau d'un passage à l'autre, et un défaut manqué au premier passage
consomme le dernier tour du ticket. ADR-0033 avait prévu de décider la
variante « seconde revue ciblée » sur cette mesure.

**Plafond sans issue.** `correction-round grant` refusait tout tour au-delà
de `bounds.correction_rounds` (2) : au plafond, il ne restait que la
dérogation constat par constat ou la Planning Exception.

## Décision

1. **Fidélité visuelle hors de la revue.** La formule `mol-code-review` dit
   au relecteur de ne jamais juger la fidélité visuelle au prototype : la
   part d'un critère qui demande que l'écran ressemble à sa référence est
   laissée de côté ; seul le reste est jugé (comportement, clavier,
   débordement, focus, valeurs affichées). Le texte de la question
   `amended_test`, écrit par `bin/code-review`, le redit. La fidélité reste
   mesurée par `bin/prototype-fidelity`, pour information (ADR-0032).
2. **Revue ciblée après le premier passage.** La première revue d'un ticket
   est complète. Toute revue suivante — après un tour de correction, après
   une revue favorable suivie de commits (reprise), après une revue
   défavorable dépassée (af-s31cvi), ou sur la pointe d'un ticket dont les
   constats ont reçu une dérogation (#718) — porte un périmètre calculé par
   `bin/code-review` et vérifié par `bin/convoy-state open-code-review` :
   - `from` : la pointe jugée par la dernière revue ;
   - `unsettled` : les Blocking Findings que cette revue laisse non soldés,
     moins ceux qui ont reçu une dérogation (une dérogation solde un
     constat) ;
   - `changed` : les lignes du ticket changées depuis `from`, c'est-à-dire
     les lignes ajoutées ou modifiées à la fois dans le diff propre du
     ticket (depuis la base de fusion avec la branche d'intégration, comme
     `bin/ticket-exit` lit « les lignes propres du ticket », #714) et dans le
     diff `from..pointe`. Les commits d'intégration repris par la branche
     ne sont donc pas des lignes du ticket.

   Le relecteur reçoit tout le diff, comme avant. Un constat ne peut
   bloquer que s'il redonne un constat de `unsettled` (`carries`) ou pointe
   une ligne de `changed` (`location`), en plus de la règle de citation.
   Un constat donné bloquant hors de ce périmètre est enregistré non
   bloquant, avec la raison sous `demoted` et `finishing_pass: true` ;
   `bin/code-review show` les liste sous `finishing_pass`. Les questions
   fermées d'une revue ciblée ne portent que sur les fichiers de `changed`.
   Le jugement des réponses (`judgement`) ne juge que la liste fermée.
   Amendement af-npz9v1.43 (2026-10-29) : il reçoit aussi le diff original
   `base...commit` et le périmètre de la revue ciblée. Il solde une
   contestation quand le comportement existait déjà dans la base et que le
   ticket ne l'a ni changé sémantiquement ni mis en interaction ; un
   comportement introduit par le ticket ou une vraie interaction avec le
   contexte hérité reste défavorable.
   Amendement af-npz9v1.44 (2026-10-29) : les entrées et consignes de ce
   jugement portent la version déterministe `code-review-attribution/v2`.
   Un jugement défavorable rendu sous une version antérieure est invalidé et
   rejoué exactement une fois à la même pointe sous la version courante, sans
   nouveau tour auteur. Son éventuel arrêt `still_refused` est levé par la
   même écriture codée ; la session neuve et la borne de deux lancements
   restent celles de toute demande de jugement. Un jugement défavorable déjà
   courant reste terminal.
3. **Tour exceptionnel.**
   `bin/correction-round grant CONVOI TICKET --approved-by <approbateur> --words "…" --exceptional`
   accorde un tour au-delà de la borne, seulement :
   - par l'approbateur humain déclaré du projet
     (`bin/project-planning-profile human-approver`), avec ses mots ;
   - sur un ticket arrêté `still_refused` au plafond (sans `--exceptional`,
     le refus le signale ; avec, un ticket qui a encore un tour est
     refusé) ;
   - quand un tour s'ouvrirait : l'auteur a terminé à la pointe et un
     contrôle y refuse le ticket (une session de correction terminée sans
     corriger laisse le tour au même commit, où aucun autre ne s'ouvre) ;
   - une fois par ticket : un second est refusé, « un seul tour
     exceptionnel par ticket ».

   L'arrêt est levé et gardé sous `grants` du tour avec `exceptional: true` ;
   la borne de ce ticket devient `bounds.correction_rounds + 1` ; `settle`
   ouvre le tour suivant comme les autres. La demande d'arrêt envoyée à
   Benjamin propose cette option tant qu'elle est possible.

## Conséquences

- **Compromis assumé** : un défaut manqué au premier passage n'arrête plus
  le ticket ; il part en non bloquant, marqué pour la passe de fin. La revue
  de fin du diff assemblé (`bin/spec-end-review`) relit tout le diff de la
  Spec et peut encore le bloquer à ce moment-là.
- Une ligne changée n'est qu'une attribution provisoire : si elle enveloppe
  un comportement hérité, le jugement de la contestation relit le diff du
  ticket contre sa base avant de maintenir ou solder le constat.
- Le relecteur doit localiser ses constats (`location`) ou les rattacher
  (`carries`) dans une revue ciblée ; un constat bloquant sans l'un ni
  l'autre ne bloque pas. Code borne le périmètre ; il ne vérifie pas qu'un
  constat rattaché à une ligne en parle vraiment (même limite que la
  citation).
- Un écart visuel ne bloque plus nulle part dans la revue ; il reste dans
  la mesure de fidélité jointe pour la passe de finition (ADR-0032).
- Un ticket difficile peut coûter un tour de plus, sur décision humaine
  tracée, une seule fois.

Revenir en arrière : revert de la PR de `af-npz9v1.14`. Les enregistrements
déjà écrits restent lisibles (`scope`, `carries`, `location`,
`finishing_pass`, `exceptional` sont des champs facultatifs) ; seul le code
qui les lit disparaît.

## Preuve

`tests/code-review-test.py` : une revue suivante ne bloque que sur le
constat redonné et la ligne changée, garde le reste pour la passe de fin ;
les commits d'intégration repris ne sont pas des lignes du ticket ; une
dérogation solde le constat ; la première revue n'accepte pas de périmètre ;
la question `amended_test` exclut la fidélité visuelle ; un ancien jugement
défavorable arrêté à la pointe est invalidé puis rejugé une fois sous le
contrat courant, dont le verdict redevient terminal.
`tests/correction-round-test.py` : un ticket arrêté au plafond reçoit un
tour exceptionnel de son approbateur, puis aucun second ; refusé à un ticket
qui a encore un tour, et quand la session de correction s'est terminée sans
corriger.
