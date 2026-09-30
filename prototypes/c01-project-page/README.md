# PROTOTYPE JETABLE — page projet du Cockpit V2 (T21, C01)

Branche jamais mergée. Question : à quoi ressemble la page d'un projet, avec
ses chantiers par étape, sur PC et sur iPhone ? Principe déjà acquis
(af-arlph5.11) : chantiers par étape (variante C), lien depuis chaque projet —
ce prototype explore trois façons de présenter ce principe pour la page dédiée
d'un projet (pas l'accueil) :

1. **Tableau** — colonnes par étape (Cadrage → Promu), une carte par chantier
   dans sa colonne. Lecture large, comparaison directe entre étapes.
2. **Groupes verticaux** — une section par étape, empilées, chantiers listés
   dedans. Lecture haut en bas, sans défilement horizontal.
3. **Bande** — liste continue triée par avancement, chaque chantier porte sa
   propre barre d'étapes inline. Le plus compact des trois.

Ouvrir `index.html` dans un navigateur : bascule entre les trois variantes
(← →, ou #1 #2 #3 dans l'URL), deux projets synthétiques (SayMyName, Usine —
Usine masque l'étape Promu car sa branche protégée est déjà `main`), thème
clair/sombre, cadre iPhone. Données 100 % synthétiques. Base visuelle : tokens
validés du prototype `prototype/c01-home-screen` (variante D).

Le choix de Benjamin (mot pour mot, avec l'heure de Paris) vit sur le NEEDS
BENJAMIN de af-1al0t1, pas ici.
