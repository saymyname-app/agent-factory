## `./bin/test-cases-compare` — mêmes cas, mêmes vérifications, avant et après ?

**La preuve d'un fichier de test accéléré ou descendu d'un étage** (CI01,
Spec af-q9urgr §1) : le nom de chaque cas et son nombre de vérifications,
comparés entre deux états du fichier. Rien n'est lancé ni écrit : les
sources sont seulement lues.

```bash
./bin/test-cases-compare --before origin/main:tests/x-test.py --after tests/x-test.py
# un fichier coupé en deux : --after deux fois
./bin/test-cases-compare --before origin/main:tests/x-test.py --after tests/x-test.py --after tests/x-suite-test.py
```

- **Source** : un fichier, ou `RÉVISION:chemin` lu par `git show` depuis le
  dossier courant. Plusieurs sources d'un même côté sont lues comme un seul
  ensemble de cas.
- **Cas** : une méthode `test*` d'une classe du fichier, nommée
  `Classe.méthode`, méthodes héritées d'une classe du même fichier comprises.
  Ce qui tourne autour des cas est comparé de la même façon sous son nom
  (`Classe.setUp`, `setUpClass`, `tearDown`, `tearDownClass`).
- **Vérifications** : les `assert`, et les appels d'une méthode `assert*` ou
  `fail`, dans le corps du cas et dans chaque aide du même fichier qu'il
  nomme (méthodes par `self`, `cls` ou `super()`, fonctions du module). Une
  aide qui perd une vérification fait donc baisser chaque cas qui s'en sert.
- **Sorties** : 0, une ligne (`N cas, V vérifications avant, V après sur les
  mêmes cas : identiques`, ou `aucun cas ni vérification en moins` s'il y en
  a en plus), puis une ligne par cas nouveau, par cas qui a des vérifications
  en plus, et une pour les cas sans vérification comptée ; 1, une raison en
  français par ligne sur stderr, chacune avec son cas : cas disparu, cas
  renommé, vérifications en moins, cas qui ne tournerait plus comme avant
  (bases de sa classe changées, décorateur ou `skipTest` ajouté), cas
  présent deux fois ; 2, usage, source illisible, ou aucun cas avant.
- **Où sa sortie va** : dans la pull request qui accélère le fichier, avec
  les secondes avant et après.
- **Limites** : les vérifications sont comptées, pas exécutées. Le contrôle
  ne lit pas ce qu'une vérification vérifie, ni si elle est atteinte (code
  après un `return`, sous `if False`, décorateur qui n'appelle pas ce qu'il
  enveloppe, cas retiré par une affectation `test_x = None`, fonction
  `test*` hors d'une classe) ; ce qu'un cas atteint dans un autre module
  n'est pas suivi, y compris l'autre moitié d'un fichier coupé en deux ;
  seuls les fichiers Python sont lus. Il ne voit pas un décor partagé qui
  fuit d'un cas à l'autre : cela se relit, et se rejoue dans l'ordre inverse.

Tests : `tests/test-cases-compare-test.py`.

---
