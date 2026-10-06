## `./bin/evidence-capture` — d'où vient une preuve ?

D'un outil, jamais d'un agent (Spec af-wf4w5r §9, T09). Une preuve (Evidence
Record) est une pièce que l'outil enregistre lui-même : il exécute la
commande, ou pilote le navigateur, et note ce qu'il a obtenu, avec l'heure et
le commit. La pièce va dans le **magasin de preuves**, hors de tout dépôt Git,
rangée par Spec et par ticket ; son empreinte est inscrite sur le ticket dans
le tracker. Seulement pour un convoi qui porte la **marque du nouveau flux**.

```bash
./bin/evidence-capture command <convoi> <ticket> --piece <nom> --repo <dépôt> -- <commande…>
./bin/evidence-capture screenshot <convoi> <ticket> --piece <nom> --launch-state <relevé de project-launch> --path /
./bin/evidence-capture verify <convoi> <ticket> [--piece <nom>]
./bin/evidence-capture purge --spec <spec>
```

- **Mode commande** : la pièce contient la commande, sa sortie réelle, son
  code de sortie, l'heure et le commit. Aucune option ne permet de fournir la
  sortie : elle vient de l'exécution. Refus si le dépôt a des modifications
  non commitées.
- **Mode capture d'écran** : une adresse du produit lancé par
  `./bin/project-launch` seulement. La pièce contient l'image, l'adresse,
  l'heure et le commit lancé. Refus si le produit ne répond pas.
- **`verify`** échoue si le fichier du magasin ne correspond plus à
  l'empreinte du tracker, ou si la pièce n'a pas été produite par l'outil
  (fichier écrit à la main, même avec son empreinte inscrite dans le tracker).
- **`purge --spec`** retire les pièces de cette Spec et d'aucune autre ; à
  appeler après la promotion.
- **Où est le magasin** : `~/.local/state/agent-factory-evidence`
  (`EVIDENCE_STORE_DIR` pour le déplacer). L'outil refuse un magasin placé
  dans un dépôt Git.
- **Sorties** : 0 fait ; 1 refus, rien n'est écrit ; 4 « pas un convoi du
  nouveau flux ».
- **Navigateur** : `chrome-headless-shell` (cache Playwright), ou celui que
  nomme `EVIDENCE_CAPTURE_BROWSER`.
- **Limite** : l'agent choisit quoi capturer ; le scellé d'une pièce protège
  le chemin honnête, pas contre un processus du même compte Unix.

Détail : `docs/EVIDENCE_STORE.md`.

---

