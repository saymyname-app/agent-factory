## `./bin/owner-answer` — enregistrer ta réponse à un Delivered Outcome

**Ta réponse et la route de chaque Owner Finding** (Spec af-wf4w5r §11,
T29). Quand tu as jugé le produit dans l'Acceptance Session
(`./bin/acceptance-session open`), c'est **le seul outil** qui enregistre ce
que tu réponds. Toi seul réponds : `--approved-by` doit être le
`human_approver` de `config/projects/<rig>.toml`. Un refus n'écrit rien.

```bash
./bin/owner-answer verdict <convoi> --proposition <ticket>:out_of_ticket.N --verdict "à faire avant d'accepter"|"plus tard"|"sans suite" --approved-by <toi> --words "<tes mots>"
./bin/owner-answer record  <convoi> --response accepté --approved-by <toi> --words "<tes mots>" --commit <commit du dossier> --pack-digest <empreinte>
./bin/owner-answer record  <convoi> --response "constats rendus" --approved-by <toi> --words "<tes mots>" --commit <commit> --pack-digest <empreinte> --findings <fichier.json>
./bin/owner-answer record  <convoi> --response abandonné --approved-by <toi> --reason "<une ligne>"
./bin/owner-answer resolve-exception <convoi> --approved-by <toi> --words "<tes mots>"
```

- **Comment t'en servir** : tu dis ta réponse à ta session opérateur, avec
  tes mots ; elle lance la commande avec le `commit` et le `digest` que
  `./bin/acceptance-session open` a rendus.
- **D'abord un verdict par proposition** du dossier (rubrique 2) :
  « sans suite » ; « plus tard » (du code crée une proposition par
  `./bin/proposal-door`, elle ne bloque pas) ; « à faire avant d'accepter »
  (bloque « accepté » tant que tu ne l'as pas rendue avec tes constats).
- **« accepté »** porte sur l'Outcome entier, à un commit : tes mots, le
  commit et l'empreinte du dossier. Refusé si le commit n'est pas celui du
  dossier ou n'est plus la pointe de la branche d'intégration, si
  l'empreinte n'est pas la sienne, si le dossier est périmé, si une
  proposition n'a pas de verdict. **Il ne ferme et ne fusionne rien** (T30).
- **« constats rendus »** : un fichier
  `{"findings": [{"text", "cites"?: {"kind", "ref"}, "repair"?: {…}, "later"?: true}]}`.
  **Le code route chaque constat**, pas l'agent : il cite une user story
  que la Spec porte, ou une ancre → un `repair` (rédigé avec le constat,
  obligatoire), publié par la passe suivante de `./bin/convoy-advance` ;
  `later` → une proposition, hors de cet Outcome ; **tout le reste → la
  Planning Exception unique du lot, jamais un `repair`** (tu demandes ce que
  la Spec n'exige pas). L'Outcome n'est plus Delivered, la demande quitte ta
  liste, les tours de fin repartent de zéro ; une fois les `repair` livrés,
  toute la porte de fin de Spec repasse et un **nouveau dossier** arrive,
  qui s'ouvre sur la rubrique 0 « Depuis ton dernier jugement ».
- **« abandonné »** exige une raison d'une ligne.
- **« refusé » n'est pas une réponse**, et il n'y a **aucune acceptation
  partielle** : les deux sont refusés avec la raison.
- **Rien ne rouvre** un Outcome accepté ou abandonné : un défaut ou un
  souhait trouvé après entre comme travail nouveau, par un Planning Run.
- **`resolve-exception`** : tu dis que la Planning Exception du lot est
  résolue (Spec amendée et graphe révisé, ou souhait abandonné) ; d'ici là
  la fin de Spec attend.
- **Cockpit** : sur un convoi du nouveau flux, le bouton « Accepter » est
  refusé et renvoie ici ; l'étape « Accepté » se lit dans ta réponse
  enregistrée.
- **Sorties** : 0 fait ; 1 refus (`error` commence par « refus : », état
  sans règle compris) ; 4 convoi sans marque.
- **Limites** : rien n'est fermé ni fusionné sur « accepté » ou
  « abandonné » (T30) ; la Planning Exception du lot est enregistrée et
  retient la fin de Spec, mais le Planning Run qui amende la Spec se fait à
  la main — aucun code ne le lance, rien ne prévient le Mayor, et
  `resolve-exception` te croit sur parole ; l'issue d'une demande
  « non conforme » n'est toujours lue par rien (seul « abandonné »
  s'enregistre sur ce dossier) ; rien n'empêche techniquement un agent
  d'inventer tes mots ou de passer ton nom — le relevé le rend visible
  après coup ; une citation `anchor` n'est pas vérifiée contre le Validated
  Prototype ; le routage lit la citation, pas le sens — un constat qui cite
  une story existante en demandant plus est routé en `repair` ; si la porte
  des propositions échoue après l'écriture, la réponse est enregistrée et
  la proposition manque ; aucun vrai convoi n'a encore reçu de réponse.

Détail : `docs/OWNER_ANSWER.md`.

---
