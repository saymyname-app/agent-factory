# Delivery V1

## Status and authority

GitHub is authoritative for branches, commits, pull requests, checks and merges. Beads is authoritative for executable work, dependencies and gates. Gas City provides dispatch through existing formulas and provider configuration. V1 has one writer per rig (since 2026-09-18 the worker pools are capped — `[[patches.agent]]` in `city.toml` — at 1 session per rig, 2 for the city pool; the load test af-48sx3 measures it); concurrent worktrees and multiple writers remain TARGET, not PROVEN.

The configured writer provider inherits `builtin:codex` and appends `-m gpt-5.6-sol`. M2 observed and proved that effective model on a real writer session. Mechanical decisions such as exit codes, diffs, SHAs, PR state and check conclusions are L0 deterministic work.

## Provider routing

- **PROVEN primary — Codex/Sol:** `codex` remains the workspace default and the
  only normal writer. Use it for Backend/Frontend implementation and keep the
  one-writer-per-rig rule.
- **CONFIGURED secondary — Claude:** the explicit `claude` provider inherits
  Gas City `v1.4.1`'s `builtin:claude`, pins the host CLI to `2.1.236`, selects
  `sonnet-5`, and defaults to `permission_mode = "unrestricted"` (`city.toml`;
  `factory-guard` treats `plan` as broken: it strands unattended agents). The
  standalone `claude-reviewer` template was retired 2026-09-28 (O14, F15): no
  formula or prompt ever dispatched it, and the dispatch door has no path for
  an ad-hoc named reviewer session outside a rig's fixed `sling_target`. L3
  independent review for GUARDED-tier risk comes from `build-basic`'s own
  plan-review/review steps or the on-demand `ux-reviewer`, not a standalone
  reviewer pool.
- **EXPERIMENTAL local candidate — OpenCode/Ollama:** Gas City already provides
  `builtin:opencode`, and OpenCode supports Ollama through its standard
  OpenAI-compatible provider plus denyable edit/shell permissions. Do not add a
  `local-*` provider until WSL-to-Ollama transport and repository read-only
  behavior are both proven. Even then, limit it initially to summaries, triage,
  documentation exploration and mechanical assistance; never use it as the
  authoritative security writer or reviewer.

The local lane may replace paid inference only for those low-risk L0/L1 classes
after its Gas City canary passes. A direct Windows-model response is not proof
of a usable factory lane.

## Profiles

| Profile | Selection | Required path | LLM level | Gate |
|---|---|---|---|---|
| FAST | Documentation, formatting, or another small reversible low-risk change | one writer; task-specific deterministic validation; branch and PR; merge only when required deterministic gates pass | L0 plus at most one L2 writer | no independent LLM reviewer by default |
| STANDARD | Normal feature or bug with bounded impact | one strong writer; task tests; GitHub CI/checks defined by the target rig; PR; review only when change risk or repository policy requires it | L2; L3 only when justified | required checks and existing human/repository review policy |
| GUARDED | Production, secrets, irreversible/data/security operations, or substantive product decisions | prepare all reversible work automatically; create a Beads gate only on the dependent path; keep unrelated ready work dispatchable | minimum sufficient L0-L3 | explicit human or supported GitHub/Beads gate at the exact risky transition |

L4 multi-agent execution is not a delivery profile and requires a concrete, measured decomposition benefit. A paid reviewer is never added merely because a PR exists.

## Existing primitives

- `gc sling` routes a bead directly or through an existing formula. `mol-do-work` is the proven minimal one-writer lifecycle; it does not provide worktree isolation.
- Gas City packs/formulas/orders supply workflow compilation, dispatch and maintenance. Do not wrap them in a proprietary runner.
- `bd dep` represents prerequisites. `bd gate create` supports `human`, `timer`, `gh:run`, and `gh:pr`; `bd ready` is blocker-aware.
- `gc github pr` supplies GitHub PR monitoring where configured. GitHub remains authoritative for actual PR/check/merge state.
- Provider inheritance supplies the pinned writer model; profile selection does not silently replace it.

## Review synthesis — redundancy filtering

`review-synthesizer` (and any bead that merges output from more than one
reviewer, e.g. `design-implementation-reviewer` + `design-test-risk-reviewer`
+ `gap-analyst` on the same change) runs the vendor pack's generic role
prompt, which executes exactly the claimed bead's description — there is no
built-in deduplication of agreeing reviewer findings at the framework level.
Research on multi-agent debate (S²-MAD, 2025) shows filtering out redundant,
agreeing exchanges before synthesis cuts token cost up to 94.5% with under
2% performance loss, by keeping only findings that differ from what's
already been said rather than re-stating consensus.

Whoever authors a review-synthesis bead description for this Factory (Mayor,
design-author, or a formula) must therefore say so explicitly in that
description, since the generic role prompt won't do it on its own:

- Merge inputs by **distinct finding**, not by reviewer — when two or more
  reviewers report the same issue, keep it once with a note of which
  reviewers agreed, not each reviewer's full restatement.
- Only carry forward a reviewer's finding verbatim when it *disagrees* with
  or adds to what another reviewer already said; summarize agreement in one
  line instead.
- The synthesized verdict is the deliverable; raw per-reviewer transcripts
  stay in their own beads/mail for audit, not duplicated into the synthesis
  output.

## External Evidence Gate

This gate adapts Compound Engineering's [`ce-plan` Phase 1.2 research-intent
triage](https://github.com/EveryInc/compound-engineering-plugin/blob/44d65ad64a0ac8e542eabee31ce031a7aeb41b28/skills/ce-plan/references/research.md#12-decide-on-external-research)
at official commit `44d65ad64a0ac8e542eabee31ce031a7aeb41b28`: explicit external requests,
intent classification, then local-pattern, risk, and uncertainty signals. This
is a pinned policy reference, not an imported pack or delegated decision.

The Mayor owns the judgment to **RUN**, **SKIP**, or mark external research
**UNAVAILABLE**. Record that judgment and its rationale in the work Bead before
it affects implementation. Deterministic signals may identify potentially
stale, version-sensitive, security-sensitive, or disputed claims, but they are
advisory: they do not launch research, establish truth, or replace the Mayor's
judgment.

- **RUN** when an unresolved external fact is material to a decision and cannot
  be established from the repository, configured runtime, deterministic tools,
  or already-recorded authoritative evidence.
- **SKIP** for trivial deterministic work and when local source, tests, runtime
  inspection, Beads, Git, or GitHub can answer the question authoritatively.
- **UNAVAILABLE** when load-bearing evidence cannot be obtained without
  speculation, prohibited disclosure, or an inaccessible source. Name the
  missing evidence and the affected decision; narrow the claim, retain the
  relevant gate, or escalate instead of presenting an unsupported conclusion.

Research reuses upstream `mol-polecat-report` as a report-only route and stores
the resulting Research Brief, or a durable link to it, in Beads notes. It does
not authorize source changes. The research worker may mutate only workflow and
Bead records needed to run and record the report. It must baseline Git HEAD and
working-tree status before research and recheck both afterward; it must not edit
files, create branches, push, comment, or otherwise mutate external systems.
Use one researcher by default. Fan out to two or three researchers only when
the Mayor records distinct, independent evidence axes and why parallel work has
measured value; do not duplicate the same query. No custom research service,
formula, broad methodology pack, or provider route is implied by this policy.

Each run uses the reusable [Research Brief template](RESEARCH_BRIEF.md). Prefer
dated primary official sources, identify the exact relevant product/runtime
version, and explain why every finding applies to the current decision.
Separate **TARGET**, **CONFIGURED**, **OBSERVED**, and **PROVEN** claims. Record
risks and unknowns, confidence with a reason, and the evidence's concrete impact
on the decision. Secondary sources may help discovery but cannot silently
replace available primary evidence for a load-bearing claim.

## Selection and completion contract

Choose the lowest-risk sufficient profile when creating the work bead and record the profile as a label (`delivery:fast`, `delivery:standard`, or `delivery:guarded`). The bead description names the repository, allowed scope, required deterministic validations and the merge authority. Risk escalation changes the profile before the risky step; it does not broaden the original authorization.

A delivery is complete only when the bead notes record the effective agent/session and model when an LLM ran, branch, commit SHA, PR URL/number, required checks and their conclusions, merge/final state, and deterministic validation. Closing a Bead never substitutes for GitHub merge evidence. For PR-backed work, `closed` is itself guarded: only `bin/deliver-close` may atomically close after recording `merge_result=merged`, `merged_sha`, `merged_target`, the six ADR-0016 proof fields, and a successful required workflow run whose `gc.ci_head_sha` equals `gc.pr_head` (ADR-0026).

For GUARDED work, create the gate against only the bead that performs the protected transition:

```bash
gate_id=$(bd gate create --type human --blocks <dependent-bead> \
  --reason "Exact decision or irreversible transition requiring Benjamin" \
  --json | jq -r '.id')
bd ready --explain
```

The gate must state the decision and evidence required. Continue any independent ready beads. Resolve the gate only after the named authority decides; do not encode secrets in its reason or notes.

## Closed-loop delivery — how work reaches `dev`

**The loop is closed to `dev` as of 2026-09-15.** Rig pull requests targeting
`dev` merge themselves when their required status check passes; `main` stays a
human decision. The merge actor is GitHub, armed by a deterministic local
script, so closing the loop costs zero model tokens.

The section above names the merge *condition* ("merge only when required
deterministic gates pass") but not the *actor*. This section names the actor and
records what was verified about the machinery underneath.

### The wired path

1. A work session implements on a branch and the `publisher` role opens a PR
   against the rig's `dev`. It records `gc.delivery_contract=pr-ci-merged-v1`
   and `gc.delivery_status=waiting`; the work bead remains `in_progress`.
2. `bin/pr-autopilot` (registered as `orders/pr-autopilot.toml`, cooldown 3 min)
   arms GitHub auto-merge (`--auto --squash --delete-branch`) on every open,
   non-draft PR targeting `dev`.
3. GitHub merges the PR itself the moment the required check goes green —
   `Maven verify` (ruleset `22629508`) or `Tests and build` (ruleset
   `22629678`). Nothing polls; no session waits on CI.
4. On its next pass, `pr-autopilot` loads the complete Beads history explicitly
   (`gc bd list --all --limit 0`), matches bead `gc.work_branch` to the PR
   `headRefName`, and calls `bin/deliver-close`. The door independently reads
   the merged PR and the latest configured required workflow run for the exact
   PR head. One atomic Beads write records `merge_result`, merge SHA/target,
   PR identity, `gc.required_ci_workflow`, `gc.ci_run_id`,
   `gc.ci_head_sha`, `gc.ci_conclusion=success`, and closes the work bead.
   Missing/red CI, a different CI head, an unmerged PR, or mismatched recorded
   branch/base/URL leaves the bead open and dependencies unreleased. A first successful finalization sends one compact
   `ACTION/STATE/EVIDENCE/NEXT` wake to the Mayor only when GitHub's `mergedAt`
   is at most one hour old, or an `open`/`in_progress` bead actively waits on
   the delivered bead through a `blocks` dependency or `gc.waiting_on`.
   Historical backfills still receive delivery metadata through the same door but remain silent when
   nobody is waiting. The sender is explicitly `pr-autopilot`, never `human`,
   and the `merge_result` stamp makes later passes silent.
5. A PR whose required check **failed** is never armed. It is raised as a P1
   bug bead in the rig instead, so a red build becomes ready work rather than a
   silently open PR.

Repository settings changed to support this: `allow_auto_merge=true` and
`delete_branch_on_merge=true` on `saymyname-app/Say-my-name-back` and
`saymyname-app/Say-my-name-front`. `saymyname-app/agent-factory` has since been
added to the autopilot's rig table (see *Production stays gated* below).

### Reading delivery state

A PR-backed bead is delivered only when it is closed with coherent merge and
exact-head CI proof. `merge_result=merged` alone, `closed` alone, or a green run
for another head is insufficient. `lib/factory_delivery_proof.py` owns this
pure predicate; `factory-waiting-guard`, `factory-delivery-guard`,
`factory-guard` and `pr-autopilot` use it, so a legacy false close cannot clear
a named wait. Explicit no-op, blocked, abandoned, and generic non-PR closes
retain their prior terminal semantics.

*Amendment 2026-09-27:* the scoped Mayor readiness lane (`mayor-campaign`),
which also rechecked approved-graph tickets with this predicate, left with the
campaign (ADR-0025 and ADR-0026 amendments). The Mayor now releases the next
approved-graph ticket itself when it is woken.

### Multi-repo / cross-rig delivery proof (af-kidv)

ADR-0016's six delivery-proof fields (`gc.delivery_status`, `gc.work_outcome`,
`gc.github_repo`, `gc.pr_number`, `gc.pr_head`, `gc.merge_commit`) fit exactly
one (repo, PR) pair per bead. A goal that ships as more than one pull request
across rigs cannot record all of them on itself. `af-7700` (personal CSV
import) is the worked example: it shipped as backend PR #39
(`saymyname-backend`) and frontend PR #50 (`saymyname-frontend`), both merged.

The convention, made explicit rather than left as a per-goal judgment call:

- The goal bead's own six fields record exactly one pair — call it the
  *primary* delivery. `af-7700` mirrors its backend child's pair (PR #39).
  Which pair is primary is not load-bearing; it is whichever pair the goal
  bead's own work session produced directly.
- Every rig's contribution, primary included, ships through its own
  `gc.goal=<goal-id>`-linked child execution bead (`smb-esa3`, `smf-2q6` for
  `af-7700`), each closed independently through `bin/deliver-close` with its
  own complete, GitHub-verified six-field proof. This was already required
  practice before this was written down — mol-do-work/mol-polecat-commit
  always close the execution bead they were dispatched with, never the goal
  bead directly — it just was not named as *the* rule for the cross-rig case,
  and nothing enumerated the full set back for a reader.
- The goal bead's own fields are **not** the complete delivery footprint for
  a cross-rig goal — they are one pair among possibly several. Never infer
  "this goal shipped exactly one PR" from the goal bead alone.
- To get the complete, deterministic list instead of manually tracking down
  each rig's child bead: `bin/goal-delivery-pairs <goal-id>` (or
  `--json`). It unions the goal bead's own six fields (when closed and
  delivered) with every closed, `gc.delivery_status=merged` bead carrying
  `gc.goal=<goal-id>` across the city and every registered rig, deduped by
  (repo, PR number) — the goal's own fields legitimately mirror one child's
  and must count once, not as an extra delivery.

### Production stays gated

In the SayMyName rigs, `dev -> main` is not automated and must not be:
`pr-autopilot` arms only PRs targeting a rig's `dev`. Promotion to production
remains a GUARDED transition requiring Benjamin.

The Factory's own repository is different, by Benjamin's standing
authorization of 2026-09-16: `agent-factory` has one long-lived branch, `main`,
and `pr-autopilot` arms its green PRs too (`bin/pr-autopilot`, rig table entry
`.|saymyname-app/agent-factory|main`). `main` there is the running factory,
not a product production branch.

### Historical note — why this needed building

`mol-refinery-patrol.toml` implements an equivalent loop upstream (its `direct`
strategy fast-forward merges, verifies `origin/$TARGET`, then closes the bead
with `merge_result=merged`). It lives in the **Gastown example pack**
(`examples/gastown/packs/gastown/formulas/`), which this city does not import,
and is absent from `gc formula list`. Its `mr`/`pr` strategy closes the bead at
"Pull request ready" anyway, so importing it would not have given close-on-merge
for PR-based delivery.

The imported role set (`gascity/roles`, `sha:3b3b89f2011e06d84459aa7bea1552382f13930a`)
ends at `publisher` — "authorized pushes, PR creation, and publication
surfaces". Grep count is zero for `gh pr merge`, merge-conditioned `bd close`
and `merge_result` across `publish`, `review`, `implement`, `do-work` and
`build-basic`. No bead carried `merge_strategy` or `pr_number` metadata, which
is why `pr-autopilot` links PR to bead by branch name instead.

## Main-landing gate — `main` cannot go red silently anymore

**As of 2026-09-16, `git push` to `main` in `saymyname-app/agent-factory`
runs the guarded local test suite first and refuses the push if it fails**
(`bin/factory-main-gate`, installed as `.githooks/pre-push`, ADR-0020).

This closes a real gap: commit `8d92c13` landed directly on `main` and broke
referential integrity between `legacy/docs/products/saymyname/DECISIONS.md` and
`config/products/saymyname.json`'s `decision_refs` — a check
`legacy/tests/factory-cockpit-test.py` already had. Nothing forced that suite to run
before the commit reached `main`; Factory CI (which also runs `on: push` to
`main`, see `.github/workflows/ci.yml`) only reported it after the fact, and
both CI and the live cockpit stayed broken for hours before it was noticed.
This repository cannot use GitHub branch protection or a required check —
private repo, no GitHub Pro, `403` on the branches API — so a local gate is
the available mechanism, not a fallback choice.

The gate reads its test list straight out of `.github/workflows/ci.yml`
(every `python`/`bash tests/*.py|*.sh` line under the `Tests` job), so it can
never drift from CI's own list the way that list once drifted from the tests
directory (ADR-0017, `tests/ci-registration-test.sh`).

**It does not touch the automated delivery loop.** `bin/pr-autopilot` lands
merges with `gh pr merge` — a GitHub-side API call, never a local `git push`
— so this hook never runs on that path. Rig PRs into `dev` are unaffected;
they are still gated purely by their own required GitHub CI checks as
described above. Only a `git push` that includes `refs/heads/main` in this
repository is gated, and only by the same tests CI already runs.

Emergency bypass is the standard git escape hatch, `git push --no-verify` —
this is a local convenience gate, not a security boundary. See ADR-0020 for
the full decision record and `tests/factory-main-gate-test.sh` for the proof
that it actually blocks a broken push and never blocks anything else.

## Real-PII containment — CI structural backstop (af-6eqc)

The dev DB currently holds real person data (the "invariant de confinement"
in the pre-refactor `legacy/docs/products/saymyname/DESIGN_GOVERNANCE.md`,
untrusted). Removing that is a separate, non-urgent piece of
work (af-hq2j, a synthetic dataset with the same shape). Until it ships,
this is a **containment** guard against a real identifier landing in a
tracked data file — it does not eliminate the underlying problem, it
contains it.

The local, exact-match layer (`bin/factory-pii-guard`, formerly installed in
`.githooks/pre-push` and surfaced in `bin/factory-guard`'s periodic report)
was retired 2026-09-28 (O14, Benjamin Q4.3); the written rule against real
person data stays in the SayMyName repo's own `knowledge/real-person-data.md`.
What remains is the structural backstop:

**CI, both rigs, zero secrets (`bin/factory-provenance-guard`, run from each
rig's GitHub Actions workflow).** CI cannot hold a real-identifier list at
all — putting one in a GitHub Actions secret would itself hand real PII to
a third party, which is exactly what this guards against. So it does not
attempt exact-value matching. Instead it requires that any data file under a
fixture/seed/test-resource path (`fixtures?/`, `seeds?/`, `test-resources?/`,
`testdata/`, `test-data/`, or Maven's `.../test/resources/`, any depth) carry
a provenance marker proving it came from the synthetic generator (af-hq2j): a
`PROVENANCE.md` manifest in the same directory with a line
`<filename>: synthetic-provenance af-hq2j sha256:<hex>`, where the hash is
the file's own sha256. The hash binds the attestation to the file's exact
current content — a filename+keyword line by itself is not proof, so a data
file swapped in after the manifest entry was written (or an entry never
actually backed by the generator) fails the same way an unmarked file does.
An unmarked or stale-attestation data file in one of those paths fails the
build — it is either real data that should never have landed there, or a
synthetic file someone forgot to record (or re-record after editing).

Its coverage is narrower than "any real data" and the two boundaries that
matter are both hard-coded in `bin/factory-provenance-guard`. **Path:** only
the fixture/seed/test-resource directory names above, at any depth — a data
file anywhere else in the tree (application code paths, docs, top-level data
directories that aren't named one of those) is not looked at by this guard
at all. **File type:** only these extensions —
`.json .csv .sql .yaml .yml .xml .properties .tsv`. Anything else under a
watched directory, including images and other binary formats
(`.jpg .jpeg .png .heic .pdf`, …), is invisible to its regex and is never
asked for a `PROVENANCE.md` entry. This is why real-person photos (Oxyl dev
data) produced no signal for a year: they are binary files, so the extension
filter never selects them even when they sit under a watched path.
Distinguishing real photo data from synthetic photo data is separate,
future work (see the guard candidate referenced from af-ox44d); today,
binary files of any kind are outside what this guard claims to contain.

This is not a security boundary against a determined actor; it is a CI
convenience gate that catches the mistake before it merges. See
`bin/factory-provenance-guard` for the exact mechanism.

## Réversibilité par défaut

Règle (ADR-0019, ADR-0016 §7) : un changement doit pouvoir être défait dans la
release. C'est la forme normale d'un changement, pas l'exception — et c'est ce
qui fait que le test d'escalade 4 (« impossible à défaire ») se déclenche
rarement.

### Migrations Flyway — ce que fait le rédacteur

Avant d'ouvrir la PR, depuis le rig :

```bash
/home/benja/agent-factory/bin/reversibility-check --git . --base origin/dev
```

Chaque **nouvelle** migration est classée, instruction par instruction :

| Classe | Exemples | Déclaration acceptée |
|---|---|---|
| perte de schéma | `DROP TABLE`, `DROP COLUMN`, `TRUNCATE` | `rollback:` ou `irreversible:` |
| perte de données | `DELETE` | `rollback:` ou `irreversible:` |
| réécriture | `UPDATE`, `MODIFY`, `ALTER COLUMN … TYPE` | `reversible:`, `rollback:` ou `irreversible:` |
| renommage | `RENAME`, `CHANGE COLUMN` | `reversible:`, `rollback:` ou `irreversible:` |

Additif (`CREATE`, `ADD COLUMN`, `INSERT`, index, contraintes) : rien à déclarer.
Supprimer un index ou une contrainte n'est pas une perte.

Les déclarations sont une ligne de commentaire dans la migration :

```sql
-- rollback: R12__restore_note.sql
-- reversible: backfill d'une colonne dérivée, recalculée à chaque écriture
-- irreversible: effacement RGPD de la table historique, aucune copie ne doit subsister
```

- `rollback:` nomme un script placé dans `src/main/resources/db/rollback/`,
  **ajouté dans la même PR**. Flyway ne l'exécute jamais (il est hors de
  `db/migration`) : il sert au retour arrière manuel.
- `reversible:` n'est accepté que pour une réécriture ou un renommage. Une
  suppression demande un chemin de retour, pas une assurance.
- `irreversible:` est une **escalade volontaire** (test 4) : la PR ne sera
  fusionnée que par un humain.
- **Ne jamais modifier ni supprimer une migration existante** : Flyway a
  enregistré sa somme de contrôle. Ajouter une nouvelle migration.

Préférer la forme réversible (expand/contract) :

- **supprimer une colonne** : la release N cesse de la lire et de l'écrire ; la
  release N+1 la supprime, avec un rollback ou une copie de sauvegarde ;
- **renommer** : ajouter la nouvelle colonne, copier, basculer la lecture ;
  supprimer l'ancienne plus tard ;
- **réécrire des valeurs** : copier l'ancienne valeur dans une colonne ou une
  table de sauvegarde dans la même migration ; le rollback la restaure ;
- **supprimer des lignes** : les copier d'abord dans une table d'archive.

### Ce que fait le robot de fusion

`bin/pr-autopilot` passe le contrôle sur chaque PR ouverte, une fois par commit :

| Verdict | Effet |
|---|---|
| ok | armée comme avant |
| déclaration requise / historique réécrit | non armée (désarmée si elle l'était), étiquette `reversibility-declaration-needed`, explication postée une fois ; libérée au commit suivant si c'est corrigé |
| irréversible déclaré | idem, étiquette `irreversible-change`, escalade au Mayor (test 4) ; **jamais fusionnée par l'automatisation** |
| contrôle impossible | non armée ce passage (échec fermé) |

**Tranché (Benjamin, 2026-09-16) :** GUARDED ne s'applique qu'aux migrations
Flyway **non additives** (perte de schéma, perte de données, réécriture,
renommage — le tableau ci-dessus). Une migration **additive** (`CREATE`,
`ADD COLUMN`, `INSERT`, index, contraintes — rien à déclarer) continue de
fusionner automatiquement dès `-Pit verify` vert, comme avant ADR-0019 et comme
`bin/pr-autopilot` le fait déjà aujourd'hui. Le code n'a pas changé ; c'est ce
document qui était en retard sur le comportement réel.

### Changements de comportement — point de revue (non mécanique)

Aucun rig n'a de mécanisme de feature flag, et un diff ne dit pas si un
comportement change. Le relecteur vérifie donc :

- aucun comportement **destructif par défaut** (suppression, envoi, écrasement)
  sans confirmation explicite de l'utilisateur ;
- un changement visible par l'utilisateur est défaisable par un simple revert du
  commit, **ou** la PR dit précisément comment revenir en arrière ;
- sinon, la PR le déclare et c'est une escalade (test 4).

## Observed and proven baseline

- **PROVEN FAST:** M2 bead `af-v7a` used one Codex/Sol writer, deterministic diff validation, commit `77f206a85ab97352aa2e6f9bd2a4f2e653db6d69`, PR #9 and merge `43614760bce9a855a6aeecbfb38090461a905e70`.
- **OBSERVED GitHub (M2, historical):** at M2 this private repository had no Actions workflows and PR #9/#16 reported an empty check rollup. It has since gained `.github/workflows/ci.yml` (`Factory CI`), the required workflow `lib/protected_rigs.sh` names for this repository. Repository rulesets and branch protection are unavailable on the current GitHub plan (API HTTP 403).
- **PROVEN scoped GUARDED gate:** gate `af-q4v` blocked only `af-wisp-2o0m`; independent `af-wisp-r31o` remained visible in `bd ready --include-ephemeral`. After resolution, the guarded bead became ready. All probe artifacts were closed.
- **CONFIGURED STANDARD contract:** target rigs must declare their own deterministic tests and GitHub CI/check requirements before STANDARD delivery is claimed. The Agent Factory repository runs `Factory CI` on its pull requests.

These classifications are deliberately separate: the three contracts are durable and usable, FAST and gate isolation are proven, while target-repository CI remains to be observed during rig onboarding.

## Contrôles `exec` des builds GUARDED

Les contrôles `exec` déclarés par les formules sont résolus par Gas City depuis
la racine du rig cible. Les scripts restent pourtant la propriété du pack
épinglé : les recopier à la main les désynchroniserait au prochain re-pin, et
un script factice qui retourne toujours vrai ferait passer un build sans le
valider.

`bin/factory-build-gates` lit `gc formula list --rig <rig> --json` pour chaque
rig, déduplique les chemins réellement actifs, et matérialise les scripts du
pack résolu pour ce rig. Gas City refuse un lien symbolique présenté comme
contrôle si sa cible sort du confinement du rig : chaque chemin `exec` est donc
une copie locale régulière. Le validateur Python appelé par le contrôle reste,
lui, un lien suivi vers le pack afin de résoudre les schémas voisins ; il n'est
pas lui-même soumis au résolveur `exec`. Copies et dépendance sont suivies par
`.gc/scripts/.factory-build-gates.json`. Cette résolution par rig évite de
réutiliser silencieusement le pack par défaut si un rig a sa propre version.
`factory-boot` le fait avant le démarrage du
contrôleur ; `factory-guard` vérifie et répare ensuite une disparition après un
re-clone ou un artefact géré périmé après un re-pin. `--check-only` ne modifie rien et
sort non-zéro en nommant chaque couple rig/chemin une seule fois. Un fichier
réel déjà présent, ou un artefact géré modifié hors de l'outil, n'est jamais
écrasé silencieusement.

Preuve attendue avant de considérer une réparation comme livrée : un build
trivial complet se termine avec `gc.outcome=pass` dans chaque rig, et un
artefact volontairement invalide est refusé avec les erreurs structurées du
validateur. Vérifier seulement que le chemin existe ne prouve pas que le
contrôle s'exécute.

`build-basic` place en plus toute sa chaîne — préparation, exigences, plan,
décomposition, implémentation, synthèse, revue, finalisation et publication —
dans une portée Gas City `build-pipeline`. Chaque étape porte
`gc.on_fail=abort_scope`. Une fermeture dure d'un contrôle (`gc.outcome=fail`,
par exemple `gc.failure_reason=control_dispatch_error`) ferme donc la portée en
échec et ferme les étapes suivantes avec `gc.outcome=skipped` avant qu'un agent
puisse les réclamer ; le finaliseur ferme ensuite la racine en échec. Une
dépendance graph.v2 attend seulement la fermeture de son prédécesseur, pas son
succès : retirer cette portée réintroduirait l'exécution coûteuse des producteurs
et des boucles de revue après un gate en échec. Le test
`tests/build-basic-fail-fast-test.py` verrouille l'enveloppe complète, y compris
les deux variantes de drain et les étapes héritées recopiées localement pour ne
pas perdre leur prompt. Le test local
`tests/build-basic-fail-fast-runtime-test.sh` instancie en plus un graphe dans
une ville isolée, injecte `control_dispatch_error`, exécute les contrôles réels
et prouve que les descendants de revue sont fermés `skipped`, qu'aucune seconde
itération n'apparaît et que la racine se ferme `fail` en deux passes bornées.
La métadonnée portée par l'hôte d'une expansion n'est
pas transmise aux étapes générées : le fork local
`build-basic-review-scoped.formula.toml` place donc aussi la préparation, le
contrôle de boucle et la cible finale de la revue dans `build-pipeline`. Sans
cette seconde protection, une boucle de revue imbriquée déjà matérialisée
pourrait rester exécutable malgré l'échec d'un gate antérieur.

### Drain partagé : un worktree, une branche, une PR

Pour `build-basic --var drain_policy=same-session`, Gas City garantit l'ordre
du drain (`single_lane=true`) et ferme les éléments suivants en `skipped` dès
qu'un élément échoue (`on_item_failure=skip_remaining`). Le contrôleur ne crée
cependant pas le dépôt de travail : `do-work-item` exige à juste titre un
`work_dir` déjà publié sur son source anchor et refuse toute lecture de source
sans lui.

La couche Factory comble uniquement ce raccord. Avant le premier item,
`prepare-shared-worktree` appelle `bin/factory-shared-drain-workspace prepare` :
une branche `build-basic/<workflow-root-id>` et un seul worktree sous
`<rig>/.gc/worktrees/` sont créés, puis leur chemin absolu est écrit sur tous
les source anchors du convoy. Chaque item travaille et commit séquentiellement
sur cette même histoire ; le second voit donc les commits du premier. La revue
lit ce worktree comme source de vérité. L'étape de publication pousse la branche
une fois et crée ou réutilise une seule PR, jamais une PR par item.

Après succès ou échec de la portée, `cleanup-shared-worktree` est un teardown :
il retire le worktree enregistré et efface les `work_dir` correspondants. Il ne
supprime jamais un worktree sale ; dans ce cas il conserve les éléments de
récupération et enregistre `preserved_dirty`. Une branche locale propre reste
récupérable même si `push=false`, mais aucun worktree ne reste pour épingler une
branche fusionnée. Le mode `drain_policy=separate` demeure inchangé : chaque
item continue d'utiliser le cycle Gas City `do-work`.

Preuve déterministe : `tests/factory-shared-drain-workspace-test.sh` construit
un dépôt et un convoy jetables de deux items dépendants, vérifie le chemin
partagé, l'ascendance des deux commits, le contrat de saut sur échec, l'unique
PR, le retrait du worktree et l'absence de changement du drain séparé. Ce
raccord supprime les reprises manuelles après l'erreur « source anchor has no
work_dir metadata » et remplace jusqu'à N worktrees/PR par un seul pour N items,
sans coût modèle supplémentaire pour le cycle Git.
