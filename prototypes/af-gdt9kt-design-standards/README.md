# Propositions de standards de design pour SayMyName, sur de vrais écrans

Prototype jetable du ticket af-gdt9kt.9, carte af-gdt9kt (« Standards de design
et de code garantis par l'usine, sans designer ni relecture humaine »).
Branche `prototype/af-gdt9kt-design-standards`, jamais fusionnée.

Intent (Benjamin, ses mots, 2026-10-12) : « Le design UI UX m'importe à l'oeil
mais aussi aux performances. » ; « Le theme actuel est tres bancale, et il
faudrait le refacto proprement avant release, comme pour une app qui démarre. »
Mechanism (interprétation de l'agent) : trois propositions complètes (couleurs,
typographie, espacement, forme, mouvement), chacune rendue sur quatre écrans à
390 et 1440 px, avec ses conséquences à l'œil et en performance et une
recommandation. C'est la forme du parcours de choix décidé sur af-gdt9kt.6.

## Question

À quoi ressemble, pour Benjamin, le choix des standards de design d'un produit ?
Il choisit une proposition ou dit ce qu'il veut changer.

- A · Net : clair, police de l'appareil, traits fins, fondus de 120 ms.
- B · Chaleureux : violet et jaune, formes rondes, police Figtree, rebonds de
  260 ms. Recommandation de départ.
- C · Nuit : bleu nuit et vert citron, titres en Bricolage Grotesque,
  glissements de 180 ms.

## Ouvrir

Ouvrir `index.html` dans un navigateur (double-clic, aucun serveur). Flèches
gauche et droite pour changer de proposition ; `#a`, `#b`, `#c` dans l'adresse.
La case « Simuler réduire les animations » montre la version sans mouvement.

`saymyname-design-propositions.html` est le même contenu sans l'enveloppe
`<html>` : c'est le fichier publié comme page Artifact privée.

## Ce que le prototype respecte

- Écrans repris de SayMyName : accueil d'un membre, quiz en cours de partie,
  trombinoscope, admin « Membres & invitations ». Blocs et libellés lus dans le
  Frontend le 2026-10-13. Les libellés en anglais de l'app sont montrés en
  français.
- Données synthétiques : noms, adresses (`example.test`) et portraits dessinés
  sont inventés. Aucune photo, aucune personne réelle.
- Aucune destination ajoutée ni retirée par rapport à l'app : seuls la forme et
  l'emplacement des commandes changent.
- Le thème actuel (néon, particules, flou) n'est pas la référence (Q9 de la
  carte).

## Limites

- Les conséquences en performance sont des ordres de grandeur tirés de ce que
  chaque proposition charge et dessine. Aucune mesure de poids n'existe pour
  SayMyName aujourd'hui.
- Les contrastes sont calculés dans la page à partir des couleurs réelles.
- Les écrans sont rendus par un script : ce n'est pas encore la version gelée
  (Validated Prototype, `docs/VALIDATED_PROTOTYPE.md`), qui ne garde que la
  proposition choisie en pages statiques.
- Code de prototype : ni tests ni gestion d'erreurs. À réécrire à la livraison.
