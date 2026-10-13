# Récidive des standards du projet

`bin/convoy-advance` appelle `bin/project-standards recurrence --rig <rig>` après
les revues de code. La commande relit les constats bloquants de revue et
les constats écran de l’Evaluator déjà enregistrés
dans Beads. Deux passes de revue distinctes citant la même ligne d'un même
fichier de standard du rig ouvrent une seule tâche de cause racine sur le plan
de planification, y compris si les constats viennent de deux convois. Les
constats non bloquants, rétrogradés ou citant la Spec ou le ticket ne comptent
pas. La tâche nomme les deux sources et suit le circuit de planification
délégué ; elle n'est pas un ticket de livraison publié à la main.

La tâche demande une règle de code si un outil peut refuser l'écart, sinon une
précision sans changement de sens. Un changement de sens attend l'accord de
Benjamin à l'Acceptance Session avant de s'appliquer.
