## `gc doctor` — la santé de la cité

```bash
gc doctor              # rapport
gc doctor --fix        # répare ce qui est réparable seul (hooks, liens)
```

Lisez les `✗` avant les `⚠`. Plusieurs warnings sont **consultatifs et
s'auto-résolvent** — la rétention `order-tracking` est purgée par un watchdog,
et un rig sur une branche de feature est normal pendant qu'il travaille.

**N'appliquez pas** le hint `rig:*:root-branch` qui suggère
`git checkout dev` : ces rigs sont des racines vives avec du travail en cours.
