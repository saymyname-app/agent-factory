# Prototype jetable de reprise du cockpit

Intent (Benjamin, ses mots, 2026-10-11) : « faire des prototypes avec la skill pour les interfaces ».
Mechanism (agent interpretation) : trois structures sur les mêmes données synthétiques et le style du cockpit actuel, dans un serveur isolé qui n'appelle aucun service réel.

Depuis la racine du worktree : `python3 prototypes/c01-reprise/serve.py`.
URL : http://127.0.0.1:8184/?variant=A — A/B/C par barre flottante ou flèches clavier.
Routes : `/` et `/projet/usine` ; accueil / projet / résultat à juger par la navigation.
États : prêt, urgent, corrections, accepté en attente de fusion, abandonné, inconnu, vide.
Aucune action ne quitte le navigateur ; aucun prototype validé pour la livraison à ce stade.
Ctrl+C arrête ce serveur. Il n'est ni branché à factory-boot ni au cockpit 8173.

Analyse : `docs/research/2026-10-11-reprise-cockpit-c01-d01.md`.
Preuve ciblée : `stage-observation.json`, record Delivered valide que le calcul actuel classe Livraison/bloqué.

Vérification navigateur : Edge sans fenêtre, captures 1440 px et 390 px de 3 surfaces × 3 variantes ; aucun débordement horizontal ni erreur JavaScript ; URL et clavier, 6 scénarios supplémentaires, transition simulée vers accepté contrôlés. Capture sombre A accueil incluse. Les autres vues sombres et un appareil iPhone réel ne sont pas vérifiés ici.
