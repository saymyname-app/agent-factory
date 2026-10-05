# PROTOTYPE JETABLE — preuve de fidélité au prototype (af-0sayxf.18)

Branche jamais fusionnée. Question : sur le Cockpit V2 (prototype validé
`prototype/c01-home-screen` variante D contre l'accueil servi par `main`), que
détectent sans humain (1) un contrôle mécanique des tokens, (2) une comparaison
de structure et de styles calculés, (3) une différence de pixels, (4) un agent
qui regarde les deux rendus ?

La décision vit dans le commentaire de résolution de af-0sayxf.18, pas ici.
Données synthétiques uniquement.

## Lancer

    python3 prototypes/af-0sayxf-fidelity-proof/serve.py &      # cockpit de main sur faux gc/bd (18173) + prototype (18174)
    python3 prototypes/af-0sayxf-fidelity-proof/check1_tokens.py delivered   # moyen 1, cockpit livré
    python3 prototypes/af-0sayxf-fidelity-proof/check1_tokens.py mutant      # moyen 1, témoin
    node prototypes/af-0sayxf-fidelity-proof/measure.js          # moyens 2 et 3

`serve.py` ne touche ni gc ni bd réels. `measure.js` utilise le `playwright-core`
du cache npx (variable `PW` pour un autre chemin) et le Chromium de
`~/.cache/ms-playwright` ; il lui faut `libnss3 libnspr4 libasound2t64`.

## Contenu

- `serve.py` : lance les deux côtés ; fabrique `out/mutant.html`, le prototype
  avec 5 petits défauts semés (liste `MUTATIONS`), témoin « presque fidèle ».
- `check1_tokens.py` : tokens, polices chargées, classes sans règle, sur les sources.
- `measure.js` : arbre d'accessibilité, styles calculés et positions sur une table
  d'ancres écrite à la main, police réellement dessinée (CDP), différence de pixels.
- `out/` : résultats du passage du 2026-10-05 (`check1-*.json`, `measure.json`,
  captures `shot-*`, `full-*`, différences `diff-*`).

Le moyen 4 (agent qui regarde) a été passé à la main : trois sous-agents en
contexte neuf, chacun ne recevant que quatre captures. Leurs réponses sont
résumées dans le commentaire de résolution.
