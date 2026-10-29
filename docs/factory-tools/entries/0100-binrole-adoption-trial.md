## `./bin/role-adoption-trial` — un rôle de livraison reçoit-il bien ses skills, et rien d'autre ?

L'usine a trois rôles de livraison (`config/delivery-roles.json`, Spec
af-wf4w5r §1) :

| Rôle | Agent | Skills de Matt reçus | Lecture seule |
|---|---|---|---|
| auteur | `delivery-author` | `tdd`, `codebase-design` (lit `implement`) | non |
| relecteur | `delivery-reviewer` | `code-review`, seul skill de revue qu'il peut lancer | oui |
| Evaluator | `delivery-evaluator` | aucun | oui |

Ce qu'une session reçoit vraiment dépend de Gas City et du CLI du
fournisseur : cela ne se lit pas dans un fichier, cela s'essaie. `run` monte
une **cité isolée** (son propre `GC_HOME`, son port de superviseur, jamais la
cité live, sans Mayor ni pool `bd.dog` étranger à l'essai), ouvre une session
réelle par rôle et par fournisseur déclaré, et
relève : les skills chargés (lus dans le transcript de la session), l'empreinte
du `code-review` chargé par le relecteur, le résultat d'une demande de lancer
`code-review`, `security-review` et `review` faite à chaque rôle, et le résultat
d'une demande d'écrire, de committer et de pousser faite à un rôle en lecture
seule.

Règle des skills de revue (user story 75, T47) : le relecteur lance son
`code-review` et rien d'autre ; l'auteur et l'Evaluator n'en lancent aucun. Un
skill de revue listé ou lancé en plus fait échouer l'essai. Deux réglages
tiennent cette règle chez les trois rôles : `CLAUDE_CODE_DISABLE_BUNDLED_SKILLS=1`
(`agents/<agent>/agent.toml`) retire les skills intégrés à Claude Code, dont
`security-review` ; `syncClaudeAiPlugins` et `syncClaudeAiSkills` à `false`
(`agents/<agent>/overlay/.claude/settings.local.json`) retirent les plugins et
skills du compte claude.ai, dont un autre `code-review`.

```bash
./bin/role-adoption-trial status                # chaque rôle × fournisseur déclaré : essai valide ou non
./bin/role-adoption-trial run                   # essai réel (~1 min par rôle, consomme du quota), écrit le relevé
./bin/role-adoption-trial run --role reviewer   # un seul rôle
./bin/role-adoption-trial verify-distribution   # les copies par rôle = la distribution, octet pour octet
```

- **Relevé** : `config/role-adoption-trials.json`, versionné. Il se committe par
  PR depuis un worktree ; ne jamais l'éditer à la main, relancer l'essai.
- **`check`** (lu par `bin/dispatch-door --role`) ne se fie pas au seul
  `passed` du relevé : il relit les lancements relevés et refuse, en nommant le
  skill, un relevé où un skill de revue hors du rôle s'est lancé, où le
  `code-review` du relecteur ne s'est pas lancé, ou qui ne dit pas ce qui s'est
  lancé.
- **Empreinte** : un essai vaut pour un rôle, un fournisseur et une empreinte
  (entrée du rôle, tous les fichiers de `agents/<agent>/`, profil du fournisseur
  dans `city.toml`, `bin/delivery-role-sandbox`). Changer l'un d'eux annule
  l'essai : `tests/dispatch-door-role-test.sh` passe au rouge et
  `bin/dispatch-door --role <rôle>` refuse, jusqu'au nouvel essai.
- **Fournisseurs déclarés** d'un rôle : la chaîne de la cible de son agent dans
  `config/provider-policy.json`. N'y ajouter un fournisseur qu'avec son essai.
  Claude Code et Codex sont observables : l'observateur Codex lit le rollout
  de la session, sa liste de skills, les `SKILL.md` ouverts et les refus du
  sandbox. Avec Codex CLI 0.165, l'essai livre ses instructions par
  `gc session nudge --delivery immediate` : le prompt est bien reçu, mais le
  CLI n'expose pas la transition `busy` brève que `session submit` attend pour
  confirmer la livraison. L'essai tolère donc ce retour non nul et exige à la
  place son oracle fort, le nonce de fin lu dans le rollout. La cité isolée
  ajoute à ses seules commandes Codex `--dangerously-bypass-hook-trust` pour
  les hooks Gas City/versionnés qu'elle vient de construire, et une surcharge
  `-c projects."<workdir isolé>".trust_level="trusted"` pour le dialogue
  « Trust this folder? » de Codex 0.165. Ces deux confiances valent uniquement
  pour l'invocation d'essai : elles ne modifient ni `~/.codex/config.toml`, ni
  les profils live. Un profil sans observateur échoue et la porte tient le rôle
  hors de ce profil.
- **Stabilité de session** : `active` et `awake` sont tous deux des états
  utilisables. Au premier démarrage Codex, Gas City matérialise ses hooks après
  avoir pris l'empreinte de configuration puis draine la session avant la
  création d'un thread fournisseur. Après cette unique transition vers
  `asleep`, l'essai fait `gc session reset` dans sa cité isolée : un redémarrage
  frais sur le même bead et alias, sans tentative de reprendre un thread qui
  n'existe pas. Le premier état `active` ou `awake` suivant autorise le probe.
  Sans ce drain observé, la minute de stabilité historique reste requise ; un
  autre `asleep` déclenche un réveil normal.
- **Lecture seule** : le relecteur et l'Evaluator tournent sur un profil
  `*-readonly`, lancé par `bin/delivery-role-sandbox` (Bubblewrap : tout en
  lecture seule sauf le répertoire de travail de la session, l'état du
  fournisseur, `.gc/` et `.beads/` ; aucun identifiant de push).
- **Dossier de l'essai** : `~/.local/share/af-role-trial` par défaut, effacé à
  chaque essai. Le garder court (chemins de sockets) et stable : Claude Code
  refuse de démarrer sans surveillance dans un dossier jamais approuvé.

Sortie de `run` et `status` : `0` tout est réussi · `1` au moins un échec ·
`2` l'essai n'a pas pu être mené.

---

