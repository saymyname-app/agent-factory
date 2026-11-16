# Objectif de l'usine

Intent (Benjamin, ses mots, 16/11/2026 entre 16:38 et 16:50 Paris) : « Oui
telle quelle », à la question « Valides-tu la cible chiffrée (§8) ? ».
Source : Bead `af-q55qqx`, décision 4 ; rapport intégral en commentaire de
ce Bead.
Mechanism (interprétation agent) : le §8 du rapport « L'usine Agent Factory :
bilan complet » est recopié ci-dessous sans changement de fond. Seul le titre
de la première section ne dit plus « à valider par toi », puisque Benjamin
l'a validée. « Tu » désigne Benjamin.

Ce fichier appartient à Benjamin (ADR-0036) : un agent ne change ni un
seuil ni une phrase de fond. Un agent peut seulement y transcrire une
décision de Benjamin, avec ses mots et leur source. Les autres décisions de
l'usine s'y rapportent : le plan J0 → J14 et ses points de bascule sont dans
`docs/decisions/ADR-0037-short-lane-default-and-d01-strangler.md`.

## Principes (tes mots convertis en seuils, validés le 16/11/2026)

1. **Le produit d'abord** : au moins une tranche SayMyName fusionnée sur `dev` par jour ouvré tant qu'il reste du backlog ; au moins 50 % du coût mensuel sur le produit (aujourd'hui environ 9 %).
2. **Petits lots** : une tranche fait moins d'une journée ; délai bead → `dev` de 24 h en médiane et 72 h au 85e centile ; **aucune branche d'intégration de plus de 2 jours**.
3. **Autonome pendant que tu dors** : 0 arrêt global ; au plus 1 sollicitation par jour, 100 % dans la liste fermée de l'ADR-0016 ou portant sur l'intention produit ; notification sur mobile ; chaque geste humain authentifié.
4. **La qualité à la fin** : aucune porte ne dit « pass » sans mesure ; au plus 1 défaut échappé (trouvé par B1, l'e2e ou un ticket suivant) pour 5 tranches ; taux d'échec des changements calculé par du code.
5. **Sobriété** : machinerie locale (bin + lib hors produit) sous 15 000 lignes à 8 semaines (environ 68 700 aujourd'hui) ; chaque règle ajoutée en retire une ; la maintenance ne dépasse pas 30 % des PR.
6. **Prévisible** : un tableau hebdomadaire calculé par du code (DORA, coût par tranche, latence humaine depuis la première demande, récidive par classe de défaut).
7. **Sûre** : une identité par rôle (jamais le compte propriétaire), toutes les sessions confinées, aucun dépôt public portant du contexte de données personnelles.
8. **Parallèle quand c'est utile** : 2 à 4 worktrees sur des tâches indépendantes, avec une PSI sur 5 min sous 30 à 50 %.
9. **Multi-projets** : une seconde usine seulement après 4 semaines consécutives au-dessus de ces seuils. Cela donne enfin un seuil chiffré à af-ujld6l.

## Architecture minimale

```
Bead prêt ─▶ worktree ─▶ session auteur (TDD : test rouge prouvé par code)
         ─▶ CI du dépôt (régression, lints déterministes : glossaire, parcours, imports)
         ─▶ 1 revue neuve d'un AUTRE fournisseur, bornée spec+sécurité+données, "skip style"
         ─▶ PR ─▶ merge queue ─▶ auto-fusion sur dev
         ─▶ e2e "le produit répond" (GET 200 par route, empreinte différente par jeu)
dev → main (promotion) : humaine. Pas de branche d'intégration longue, pas de juge sur diff cumulé.
Déclenchement par événement (bead.closed) + filet toutes les 10 min ; tests longs en job détaché.
Chaque process de test dans un scope systemd tuable en bloc.
```

## Ton rôle

- Fixer l'**intention produit** et les seuils de la cible.
- Faire B1 (tester l'app toi-même), puis accepter les Outcomes.
- Garder les actes réservés par l'ADR-0016 : données personnelles, destruction, administration, dépense, publication.
- **Rien d'autre.** Les décisions techniques (écarts techniques, retraits de tickets, réparations) sont déléguées par écrit, avec l'acteur agent enregistré, et un rapport groupé une fois par jour à heure fixe.

## Rôle du Cockpit

Le Cockpit **cesse d'être le banc d'essai** de l'usine (c'est la Fixture City qui joue ce rôle). Il devient **ton outil de pilotage** :

- une boîte « Pour moi » ;
- les notifications ;
- l'état vrai des projets, avec « fusionné » seulement quand c'est prouvé ;
- le tableau hebdomadaire.

Il lit un contrat versionné, pas les métadonnées internes `gc.flow.*`. Il tourne sous systemd, avec une sonde externe.
