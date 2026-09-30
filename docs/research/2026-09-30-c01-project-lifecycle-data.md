# C01 research — per-project lifecycle data (design → production)

Ticket: af-arlph5.4 (map af-arlph5, C01 Cockpit V2). Question: what data
exists today, per project, to place a project on the path wayfinder map →
Spec → Ticket Graph → convoy → delivered on the integration branch →
`dev`→`main` promotion → deployment/production, and where it lives. Scope:
the Factory and SayMyName. Collected read-only on 2026-09-30 (Paris).

Legend: **MR** = machine-readable (typed field a tool can query);
**prose** = only in Markdown/free text; **none** = no source exists.

## 1. Stage-by-stage inventory

| Stage | Where it lives | Form | Factory | SayMyName |
|---|---|---|---|---|
| Wayfinder map | Beads, planning plane: `issue_type=epic`, label `wayfinder:map`, `gc.plane=planning`; children = decision tickets (`wayfinder:<type>`), `blocks` deps | MR (status, children, deps); Destination/Decisions are prose in the description | af-0aiero (A6b, closed), af-arlph5 (C01, open) | none since the refactor |
| Older maps | `docs/planning/<run>/planning-map.json` (contract `agent-factory-wayfinding-run/v1`) | MR file, retired path | factory-operations-v2 | none |
| Spec | Beads planning bead (title `Spec — …`, `issue_type=task`) with metadata `spec_state`, `planning_map`, `planning_run_target`, `approved_digest`, `approved_by`, `approved_evidence` | MR (state + link to map); content is prose | af-3s8prq | none |
| Spec (old path) | `docs/planning/<run>/spec/*.json` (contract `agent-factory-planning-run-spec/v1`, `state: APPROVED_SPEC`) | MR file | A5, A6, A6b | none |
| Ticket Graph | `docs/planning/<run>/ticket-graph-draft.yaml` (per-ticket `target_rigs`), `publish-result.json` (convoy id, ticket ids, digests) | MR file in the Factory repo | 4 runs | none |
| Convoy | Beads delivery plane: `issue_type=convoy`, `gc.plane=delivery`, label `approved-ticket-graph`, metadata `gc.spec_id`, `gc.spec_digest`, `gc.graph_digest`, `gc.artifact_id`; status open/closed, `close_reason` "convoy autoclose: all children closed" | MR | 4 delivery convoys: af-vclsw, af-ly65d, af-59qjgh (closed), af-dsygc (A6, open) | 0 |
| Ticket delivered (merged on protected branch) | Delivery bead metadata: `gc.dispatch_rig`, `gc.github_repo`, `gc.delivery_status=merged`, `gc.pr_number`, `gc.pr_url`, `gc.merge_commit`, `gc.ci_conclusion`, `gc.required_ci_workflow`; GitHub PR merged into the protected branch | MR (Beads + GitHub) | 70/78 delivery beads `merged`, all on `saymyname-app/agent-factory` | 0 delivery-plane beads; GitHub shows last merges into `dev`: back #60, front #62 (2026-09-28) |
| `dev` → `main` promotion | GitHub branches only | MR (git compare) | n/a: the Factory has one protected branch `main` (no `dev`) | back: `main` has 3 commits (last 2024-08-05) and **no common ancestor with `dev`**; front: `dev` is 104 commits ahead of `main` (1 commit, 2024-07-26). No PR ever merged into `main` on either |
| Deployment / production | — | **none** | GitHub: 0 environments, 0 releases; workflows are CI only (Factory CI, Backend CI, Frontend CI, Frontend e2e smoke) with no deploy job; deployments API unreadable with the current token (HTTP 403) | same; roadmap C says "done when the release scope is on `main`" — production is not defined anywhere |
| Release scope | SayMyName `knowledge/roadmap.md` horizons A/B/C and `state.md` | prose | roadmap steps A1-A7 | B1/B2/C in prose; 27 `parked-pre-refactor` beads (status `deferred`) incl. legacy `product-goal` beads with `gc.product_state` |

## 2. What ties a stage to a project today

- **Project = rig, not product.** `config/projects/*.toml` has one file per
  repo/rig (`agent-factory`, `saymyname-backend`, `saymyname-frontend`) with
  `rig_dir`, `repo`, `protected_branch`, `required_ci`, `required_check`,
  `sling_target`, `formulas`. Nothing groups backend + frontend into
  "SayMyName", and nothing points to a project repo, roadmap or stage
  (confirmed in `po/c01-cockpit:docs/planning/c01-cockpit/facts.md`,
  "Platform facts").
- **Planning plane has no project key.** Map and Spec beads carry
  `gc.plane=planning` and, for the Spec, `planning_run_target` (a run name
  such as `A6b`, not a project). The only per-project hint is `target_rigs`
  in the Ticket Graph draft file / `planning-session.json`.
- **Delivery plane is per rig.** Delivery beads carry `gc.dispatch_rig` and
  `gc.github_repo`, so rig → `config/projects/<rig>.toml` → repo/branch is
  joinable. 25 early delivery beads have `gc.github_repo` but no
  `gc.dispatch_rig`; 4 have neither.
- **Convoys have no rig/project field**; a convoy's project is only derivable
  from its children's `gc.dispatch_rig`.
- **Planning Run Reservation** (`config/planning-run-reservation.json`) is
  city-wide (one reserved run, `reserved_for: C01`), not per project.
- **SayMyName project repo** (`C:\Dev\Projects\SayMyName`) is not a rig; its
  `roadmap.md`/`state.md` hold the only project-level stage view, in prose,
  and state.md says live state is never there.

## 3. Traps for a cockpit reader

- `issue_type=spec` (70 beads) are formula **step specs** (`gc.spec_for`,
  `gc.step_ref`), not Planning Specs. Planning Specs are `issue_type=task`
  with `spec_state` metadata.
- Legacy product/release model (retired, untrusted): labels `product:saymyname`,
  `product-goal`, `release:post-v1`; metadata `gc.product_state`,
  `gc.release_product`, `gc.release_version` (af-hho5.4); release contract
  files moved to `legacy/config/releases/` (`saymyname-v1.json`). Not to be
  read as current stage data.
- The Beads DB mixes ~3.5k `session` beads and ~1.4k `agent:bd.dog-*`
  maintenance beads with work beads; any stage query must filter on
  `gc.plane`.
- GitHub timestamps are UTC (e.g. convoy af-59qjgh `closed_at`
  2026-09-30T04:41Z = 06:41 Paris).

## 4. Stages with no data source

1. **Deployment / production**: no environment, release, tag, deploy
   workflow or config field in any of the three repos or in the Factory
   config. (Deployments API not readable with the current token; with 0
   environments and no deploy job, none is expected — INFERRED.)
2. **Project grouping**: no machine-readable "SayMyName = back + front +
   project repo" entity.
3. **`dev` → `main` promotion record**: only derivable by git compare; never
   happened (backend branches share no history).
4. **SayMyName on the new planning path**: no map, Spec, graph or convoy
   yet (roadmap B2 is where the first one would appear).
5. **Project-level current stage**: only prose in the SayMyName repo.

## Sources

- Factory `config/projects/{agent-factory,saymyname-backend,saymyname-frontend}.toml`,
  `config/planning-run-reservation.json`, `docs/agents/issue-tracker.md`,
  `CONTEXT.md` (Spec, Planning Map Bead, Work Plane), `bin/ticket-graph-publish`,
  `docs/planning/{a6b-wayfinder-wiring,factory-operations-v2,parallel-delivery}/`,
  `legacy/config/releases/`, branch `po/c01-cockpit`
  `docs/planning/c01-cockpit/facts.md` — at `origin/main` 2026-09-30.
- Beads (`bd show --json` af-0aiero, af-3s8prq, af-59qjgh, af-jlxbek,
  af-arlph5; `bd list --all --json` aggregate of 6349 beads by type, plane,
  metadata keys, labels).
- GitHub via `gh api`: `repos/<r>`, `branches`, `releases`, `tags`,
  `deployments` (403), `environments`, `actions/workflows` and workflow
  files, `compare/main...dev`, `commits?sha=main`, `rulesets`, `gh pr list`
  for `saymyname-app/{agent-factory,Say-my-name-back,Say-my-name-front}`.
- SayMyName project repo `knowledge/roadmap.md`, `knowledge/state.md`,
  `knowledge/factory-notes.md`.
