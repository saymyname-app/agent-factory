## `./bin/order-pause` — mettre en pause et reprendre un ordre, sans PR

**Met en pause, reprend et montre un ordre de l'usine (`orders/*.toml`),
tracé à la source, réversible, sans PR ni édition de la racine live**
(af-npz9v1.15). Intent (Benjamin, ses mots, 23/10/2026 16:07 Paris) :
« Construisons la porte ou les portes dont on a besoin en premier » ; c'est la
porte que le ticket B (af-4uzgzm, histoire 29 : relancer un ordre que l'usine
a mis en pause) appelle depuis le Cockpit. **Gain** : avant, une pause était la
ligne `[orders] skip` de `city.toml`, soit une PR, sa CI et un rechargement de
la cité par geste (#691 pour mettre `convoy-advance` en pause, #701 pour le
reprendre) ; maintenant une commande, effective à la prochaine échéance de
l'ordre.

```bash
./bin/order-pause pause convoy-advance --by mayor --words "pause : intégration rouge" --reason "af-xxxx"
./bin/order-pause show                 # ce qui est en pause, depuis quand (Paris), par qui, ses mots
./bin/order-pause show --all --json    # chaque ordre : paused / active / skipped (pour le Cockpit)
./bin/order-pause resume convoy-advance --by benjamin --words "relance"   # le retour arrière
```

- **Mécanisme** : une pause est un bead `order-pause` du suivi, ouvert tant
  qu'elle dure (`gc.order_pause`, `_by`, `_words`, `_at` en UTC, `_reason`) ;
  la reprise le ferme avec `gc.order_resume_by/_words/_at`. Rien n'est
  effacé. Chaque ordre de `orders/*.toml` a pour `exec` `bin/order-pause gate
  <ordre> -- <sa commande>` : le contrôleur lance la porte, qui lit le suivi
  de la cité qui l'exécute ; en pause, elle dit pourquoi et ne lance rien
  (sortie 0, donc pas d'`order.failed`) ; sinon elle `exec` la commande, qui
  garde son code de sortie et son délai. Le `check` d'un ordre `condition`
  tourne toujours (une lecture).
- **Si le suivi ne répond pas** (ou au-delà de 20 s), l'ordre est lancé : une
  pause n'arrête jamais un ordre de santé quand le suivi est justement en panne.
- **Refus (sortie 2, rien n'est écrit)** : ordre inconnu (pas de
  `orders/<ordre>.toml`, la liste est donnée) ; ordre retiré par `[orders]
  skip` de `city.toml` (décision de config de Benjamin, que la porte ne touche
  pas : `show` le signale) ; ordre dont l'`exec` ne passe pas par `gate` ;
  `--by` ou `--words` absent. Les ordres du pack gc (`dolt-health`…) ne sont
  pas dans `orders/` : seule la ligne `skip` les retire.
- **Idempotent** : une pause déjà posée, une reprise d'un ordre en service,
  n'écrivent rien (sortie 0). **Sorties** : 0 ; 1 le suivi ne se lit pas ou
  refuse l'écriture ; 2 refus.
- **Écarté** : la ligne `skip` dans un fragment local inclus par `city.toml`
  (comme `city.provider.toml`) — vérifié sur gc 1.5.0, un fragment qui
  déclare `[orders]` remplace la table entière (`skip` et `overrides` de
  `city.toml` disparaissent) et un fragment absent empêche la cité de se
  charger ; `.gc/site.toml` n'est pas lu pour les ordres ; il n'existe ni
  `[[patches.order]]` ni commande `gc order` pour suspendre. Un état dans un
  fichier local aurait échappé au suivi que lit le Cockpit.
- **Cockpit d'essai** : `bin/cockpit-isolated` donne au cockpit la vraie
  porte, sur le suivi du lancement (`COCKPIT_ORDER_PAUSE_BIN`) ; un jeu de
  données peut dire `"doors": {"order-pause": "expires"}` ou
  `"records-then-expires"`. Le profil `agent-factory` la déclare point
  d'entrée (`pause`, `resume`, `show`).

Preuve : `tests/order-pause-test.py` ; sur le vrai suivi et le vrai `gc order
run`, dans une cité jetable : `tests/order-pause-real-tracker-test.sh`
(local-only) ; dans le Cockpit d'essai : `tests/cockpit-isolated-doors-test.py`.
