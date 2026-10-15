## Oracle public d'une City fixture

`./bin/fixture-city-oracle run <scenario> --operator <adapter>
--publication-door <adapter>` exerce un intent synthétique uniquement par les
surfaces publiques de l'opérateur et de la porte de publication. Il recalcule
les digests, vérifie les Work Planes positifs, le convoy, les arêtes, les
révisions Git réellement assemblées, leur compatibilité publique et la
distinction Delivered/Accepted. Les adapters sont confinés par Bubblewrap sans
réseau ni accès au domicile hôte. Une injection `after-stage` doit laisser zéro
graphe, bead delivery ou convoy. Le résultat JSON est déterministe et ne dépend
pas du Cockpit V1. Contrat complet : `FIXTURE_CITY_ORACLE.md`.

`./bin/fixture-city-oracle run <scenario> --delivery-driver <driver>` fait
parcourir le flux de livraison à un ticket d'un convoi marqué et observe son
état public après chaque événement : publié, démarré, rouge, gel, code,
revue, évaluation, fusion, fermé par la porte de fin de ticket. Un ticket
fermé hors porte fait échouer l'oracle.

Pendant ce parcours l'oracle enregistre lui-même les commandes du flux
exécutées : le driver les lance depuis le répertoire reçu dans
`FIXTURE_CITY_FLOW_BIN`, rien de ce qu'il déclare n'est utilisé. Chaque état
de l'étape d'auteur (rouge, gel, vert, Handoff, terminé) doit avoir été
écrit par sa porte (`tdd-step`, `ticket-exit exit`) ; un état écrit hors de sa porte, ou un ticket
fermé sans être passé par les portes de l'auteur, fait échouer l'oracle
(T37). Le résultat nomme les commandes vues (`interfaces.flow`) et le nombre
de tickets passés par toutes les portes (`author_gates`).

Avec `expect.outcome: "delivered"` et `expect.repairs` (T26), le parcours
continue jusqu'à la fin de Spec : l'oracle compte les tickets de réparation
publiés par le flux, fait parcourir chacun jusqu'à la porte de fin de ticket,
puis exige Delivered enregistré sur la pointe de la branche d'intégration,
`bin/spec-end check` vert, un compteur de tours de fin égal au nombre de
réparations, aucun arrêt et aucune demande sur la liste de l'opérateur. Il
échoue si Delivered est vu alors qu'une condition manque.
