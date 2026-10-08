## `./bin/ticket-end` — pourquoi ce ticket n'est-il pas fermé ?

**La porte de fin de ticket** (Spec af-wf4w5r §9, T19). Dans un convoi qui
porte la **marque du nouveau flux**, un ticket ne se ferme que par cette
porte : une liste fermée et versionnée de **neuf conditions**. Une PR
fusionnée et une CI verte ne ferment rien, et l'auteur ne ferme jamais son
ticket.

```bash
./bin/ticket-end check <convoi> <ticket> --repo <dépôt du projet>                  # les neuf verdicts ; n'écrit rien
./bin/ticket-end check <convoi> <ticket> --repo <dépôt du projet> --before-merge   # ce que la fusion exige
./bin/ticket-end settle <convoi> --repo <dépôt du projet>                          # lancé par ./bin/convoy-advance après la fusion
./bin/ticket-end fidelity <convoi> --repo <dépôt du projet> --profile <profil>     # lancé par ./bin/convoy-advance avant la fusion
```

- **Les neuf conditions** (liste `ticket-end/v1`), lues à la pointe de la
  branche du ticket : 1 critères identiques au digest approuvé ; 2 Handoff
  valide avec preuve du rouge et de démonstration ; 3 Ticket Evaluation
  favorable (prefactoring : le produit démarre) ; 4 fidélité verte si le
  ticket touche un écran ; 5 détecteur de report passé ; 6 fusionné dans la
  branche d'intégration, tests verts sur le résultat ; 7 preuves scellées,
  liées à la pointe fusionnée ; 8 preuve TDD enregistrée ; 9 revue favorable
  ou dérogation enregistrée.
- **Pour savoir ce qui manque** : `check` nomme chaque condition non réunie
  et dit ce qui a été lu. Rien n'est écrit lors d'un refus.
- **Avant la fusion** : `./bin/spec-integration merge` ne fusionne un ticket
  que si les conditions 1 à 5 et 7 à 9 sont réunies ; sinon le ticket attend,
  avec le texte de la porte. La condition 6 se vérifie après.
- **Fermeture** : la passe qui fusionne un ticket le ferme si les neuf
  conditions sont réunies. Le relevé de la porte (commit fusionné, version
  de la liste, neuf verdicts) et le statut fermé sont écrits ensemble ; il se
  lit sous `gates.ticket_end` dans `./bin/convoy-state show`.
- **Ticket d'interface** : avant la fusion, la passe lance le contrôle de
  fidélité sur le commit qui fusionne, contre le Validated Prototype que le
  ticket nomme.
- **Ne jamais fermer à la main un ticket d'un convoi marqué** (`gc bd
  close`, `./bin/deliver-close`) : `./bin/deliver-close` le refuse, et une
  fermeture hors porte arrête le convoi (incident d'usine). `close` et
  `settle` sont refusés à toute session d'agent.
- **Un convoi sans marque** garde `./bin/deliver-close`, sans changement.
- **Limites** : une fidélité rouge, comme toute condition manquante, laisse
  le ticket en attente : les reprises de `./bin/convoy-advance` ne couvrent
  pas un ticket que la porte laisse ouvert (`docs/CONVOY_ADVANCE.md`) ; un
  contrôle de fidélité par passe ; la fin de Spec est à T23.

Détail : `docs/TICKET_END.md`.

---

