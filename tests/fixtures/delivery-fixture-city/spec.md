Spec synthétique de la Delivery Fixture City (T07, af-tvda3w). Données de test seulement.

## Problem Statement

Un visiteur de la Fixture City ne voit pas l'état du jeu de données servi.

## Solution

Une page d'accueil qui affiche l'état, l'heure de génération et les éléments du jeu de données.

## User Stories

1. As a visiteur, I want voir l'état du jeu de données sur la page d'accueil, so that je sache ce qui est servi. [interface]
2. As a visiteur, I want voir la liste des éléments sur la page d'accueil, so that je puisse les lire. [interface]
3. As an exploitant, I want une sonde de santé, so that je sache que le produit répond.

## Validated Prototype

- branche : `prototype/delivery-fixture-city`
- commit : `dfdd34f50623661f6644524b6489342cdbbdee19`
- chemin : `tests/fixtures/delivery-fixture-city/prototype`
- états : `empty`, `content`

### Écran : accueil

| État | Statut | Détail |
| --- | --- | --- |
| vide | prototypé | empty |
| contenu | prototypé | content |
| chargement | sans objet | la page est rendue en une seule réponse du serveur |
| erreur | non prototypé | |
| contenu long | non prototypé | |
| écran étroit | non prototypé | |
| thème sombre | sans objet | la fixture n'a qu'un thème clair |

## Implementation Decisions

La page d'accueil porte les ancres du Validated Prototype.

## Testing Decisions

Fixture City Oracle et ligne de commande des portes.

## Out of Scope

Tout le reste.
