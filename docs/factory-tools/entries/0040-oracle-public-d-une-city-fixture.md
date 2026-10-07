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

