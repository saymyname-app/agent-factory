# Project-agnostic Agent Factory refactor — Spec

| Field | Value |
| --- | --- |
| Planning Artifact ID | `spec-agent-factory-project-agnostic-refactor` |
| State | `APPROVED_SPEC` |
| Planning Run | `agent-factory-autonomy-frontier-2026-09-22` |
| Shared Understanding | Confirmed by Benjamin on 2026-09-23 (Q1–Q56) |
| Approved by | Benjamin on 2026-09-23; cockpit-canary revision explicitly approved the same day |
| Content digest | `sha256:9ce47e19172505d26fd7d0ba8696bad29896e7614b0dc5c15a2f19061064b9fa` |
| Digest scope | UTF-8 bytes from `## Problem Statement` through end of file, with LF line endings |
| Method baseline | Matt Pocock `/to-spec` at `c55ee46073ed923f86ce59a5eb3b6d895095d1b7` |
| Approval effect | Benjamin's explicit approval changes this same artifact to `APPROVED_SPEC`; it does not create another document |

This is a temporary Planning Artifact. Its identity remains stable across approved revisions; its digest identifies exact content. It is frozen during delivery and may expire after its convoy closes. Durable truth belongs in code, tests, the domain glossary, and qualifying ADRs.

## Problem Statement

The current Agent Factory can deliver software, but its intent-and-design path is entangled with legacy SayMyName assumptions, a duplicated Release Contract, inherited agent contexts and policies, and a planning topology that is not yet a coherent part of Gas City. Benjamin cannot yet take an arbitrary project from intent to a verified outcome through one project-agnostic method while preserving decisions across sessions and operator surfaces, keeping planning work non-executable, and adapting autonomy to evidence.

The refactor must improve confidence and maintainability first. More autonomy and throughput are valuable only inside a verified envelope. The target must not preserve legacy Factory choices merely because they already exist, and it must not replace one opaque orchestration layer with another.

## Solution

Reconstruct the Software Factory around Matt Pocock's observable workflow contracts: exhaustive Shared Understanding, prototype detours for runnable unknowns, one canonical Spec, approved vertical-slice decomposition with explicit dependencies, fresh implementation context per slice, incremental public-behavior TDD, and independent review.

Integrate that method into one Gas City topology. A Planning Run owns intent and design; simple work may stay in one interactive session, while complex work uses a durable Planning Graph of non-executable Planning Beads and disposable decision sessions. The Spec and Ticket Graph Draft are temporary Planning Artifacts with stable identities and content digests. After explicit approvals, one deterministic Mayor-owned write door publishes the Delivery Work Graph and convoy atomically. The Mayor then coordinates delivery without redesigning it.

Make autonomy project- and work-class-aware. Project Planning Profiles bind authoritative Project Knowledge, rigs, checks, risk thresholds, and allowed autonomy while common safety principles remain non-overridable. Deterministic observations remain zero-token. Human decisions remain mandatory for semantic approval, sensitive effects, and unproven acceptance classes. Every deviation from the Method Baseline is registered and retained, replaced, or removed from evidence.

## Observable Acceptance Criteria

1. A new operator can install an independent Factory from Git on the supported Windows-plus-Ubuntu-WSL host and use a concise README to register and start a project without SayMyName-specific assumptions.
2. Each project has one Project Planning Profile that identifies its authoritative Project Knowledge, Work Graph, participating rigs, checks, risk thresholds, and autonomy policy without copying the full Factory configuration into each rig.
3. An agent scoped to one project cannot read another project's files by default; explicitly declared cross-project work can access only its named participants.
4. A simple request can complete Shared Understanding and produce a Spec in one Planning Session without mandatory Wayfinder ceremony.
5. A request that exceeds one healthy session is promoted before material decision loss into a Wayfinding Run whose Planning Map and Planning Decision Beads preserve decisions without requiring Benjamin to repeat them.
6. Planning Beads carry positive `plane=planning` routing metadata and can never be selected for delivery. Delivery Beads carry positive `plane=delivery` metadata and are ineligible until validation and convoy attachment succeed.
7. Independent Planning Decision Beads may progress concurrently; one decision is claimed and resolved once, and concurrent map updates do not lose resolutions or duplicate child closure.
8. Pausing a Planning Run releases active sessions while retaining its map, decisions, and evidence. Resuming refreshes only time-sensitive facts. Abandoning closes it without publishing delivery work.
9. When the Planning Map declares the route clear and no open decision children remain, `to-spec` is invoked without a second fog audit.
10. `to-spec` synthesizes one readable Spec without another interview. The artifact has a stable identity and reproducible content digest and contains behavior, boundaries, decisions, acceptance evidence, provenance, experiments, and non-objectives.
11. Benjamin's explicit approval changes the same Spec to Approved Spec and closes the Planning Map. No Release Contract or second prose artifact repeats it.
12. If synthesis exposes a real contradiction, lost traceability, undecided behavior, or new test seam, the affected question returns to the Planning Graph instead of being invented in the Spec.
13. `to-tickets` runs exactly once per approved decomposition or later approved graph revision, creates a temporary structured Ticket Graph Draft, and presents vertical-slice granularity and blocker edges for the applicable approval gate.
14. The deterministic publication door either atomically creates all approved Vertical Slice Beads, edges, Spec references, execution contracts, routing metadata, and convoy, or creates none. It validates but never interprets or re-slices the draft.
15. Every published slice is independently demonstrable or verifiable, sized for a fresh implementation context, and contains the autonomous execution contract needed without loading the full planning history.
16. Dependency edges make a slice eligible only after each prerequisite's required tests and review pass and its code is integrated into the project's configured working branch; unrelated eligible slices can continue in parallel.
17. One implementer performs small red/green cycles against agreed public-behavior seams, followed by deterministic checks and an initially mandatory independent review of Spec fidelity and non-automated design quality.
18. A bounded technical repair stays within its affected slice and retains failure evidence. A semantic or topology change emits a Planning Exception and parks only the affected delivery subgraph.
19. Resolving a Planning Exception either clarifies and resumes the existing slice or creates immutable revised Planning Artifacts and a validated patch to unfinished Delivery Beads through the same authoritative decomposition mechanism.
20. A multi-slice outcome receives one independent assembled-diff review focused on cross-slice architecture and Spec drift; a single-slice outcome does not duplicate its ticket review.
21. A cross-repository outcome is not Delivered until exact participating revisions are assembled in isolation and their end-to-end behavior passes.
22. A result is reported as Delivered only after implementation and required technical evidence are complete. It is reported as Accepted only after project-owner confirmation or predefined sufficient evidence for a proven class.
23. Reversible code may integrate before outcome acceptance, but production, external publication, real sending, spending, unrecoverable destruction, and widening personal-data access remain blocked on an explicit human decision.
24. Rejection after integration repairs a mismatch with the Approved Spec as targeted delivery work, returns a changed desired behavior to planning, and safely neutralizes an actively dangerous change without defaulting to whole-outcome rollback.
25. Ordinary monitoring uses deterministic observations and consumes no model tokens while state is unchanged. An agent wakes only for a new fact requiring judgment or repair.
26. Provider/model routing never selects Astra or Fable and never exceeds medium reasoning effort. Quality, rework, elapsed time, and tokens are measured separately by comparable work class.
27. The exact Gas City allocation of formulas, sessions, agents, orders, skills, and deterministic code is selected through prototypes, not asserted by this Spec; each chosen arrangement preserves Planning Run identity across supported providers and operator surfaces.
28. After direct cutover, all new planning uses the new path. A defect suspends only affected Planning Runs and is repaired forward; the legacy planning path is never reactivated.
29. Delivery work already started under the old workflow may finish, and a planned interruption is allowed when later migration safety or efficiency requires it.
30. The single Adaptation Register contains every material deviation, added gate, experiment, its baseline, reason, signal, cost, review point, and retain/replace/remove outcome.
31. After the minimum new planning kernel is operable and new planning has cut over, a cockpit rebuilt from operator needs—not from the legacy interface architecture—serves as the first non-critical live canary. Independent deterministic fixture-City tests remain the Factory's oracle.

## User Stories

1. As a project owner, I want to explain an outcome in product language, so that I do not need to operate Factory internals.
2. As a project owner, I want exhaustive Shared Understanding before decomposition, so that delivery implements the intended outcome rather than a plausible substitute.
3. As a project owner, I want to approve one canonical Spec, so that I do not reconcile duplicate contracts.
4. As a project owner, I want only genuine semantic deltas or unresolved choices brought back to me, so that routine synthesis does not consume my attention.
5. As a project owner, I want explicit control over sensitive or irreversible effects, so that autonomy cannot silently widen real-world consequences.
6. As a project owner, I want Delivered and Accepted to remain distinct, so that merged code is not mistaken for validated behavior.
7. As a project owner, I want early and risky outcomes to require my behavior acceptance, so that evidence earns autonomy rather than assumptions granting it.
8. As a project owner, I want proven work classes to use predefined acceptance evidence, so that mature routine work does not wait unnecessarily.
9. As an operator, I want simple work to stay simple, so that the planning method does not impose multi-session ceremony by default.
10. As an operator, I want complex work promoted automatically to durable wayfinding, so that I do not diagnose context exhaustion myself.
11. As an operator, I want to pause, resume, or abandon a Planning Run, so that interruptions neither lose decisions nor publish accidental work.
12. As an operator, I want to resume the same Planning Run from Codex, Claude Code, or the Cockpit without copying a transcript, so that surface choice does not fragment intent.
13. As an operator, I want unchanged monitoring to cost zero model tokens, so that visibility does not consume the planning budget.
14. As an operator, I want a deliberately high but adjustable concurrency ceiling, so that the actual machine pressure—not legacy caps—sets throughput.
15. As a planner, I want one durable Planning Map for multi-session work, so that fog, resolved decisions, and evidence remain navigable.
16. As a planner, I want one decision per disposable child session, so that fresh context improves reasoning without losing continuity.
17. As a planner, I want independent decisions and research to run concurrently, so that elapsed time falls without creating multiple canonical writers.
18. As a planner, I want runnable unknowns routed through prototypes, so that architecture is based on observed mechanics rather than guesses.
19. As a planner, I want one canonical writer for the Spec and Ticket Graph Draft, so that conflicting artifact versions cannot both become authoritative.
20. As a planner, I want exact decision provenance in the Spec, so that synthesis can be checked without replaying the interview.
21. As a planner, I want a structured Ticket Graph Draft before publication, so that slice boundaries and dependencies can be reviewed without creating executable work.
22. As a planner, I want topology changes to return to the Planning Run, so that delivery workers cannot become a second decomposition authority.
23. As a Mayor, I want one validated atomic publication door, so that I can materialize an approved graph without interpreting it.
24. As a Mayor, I want positive work-plane selectors, so that planning work cannot leak into execution through exclusion-list mistakes.
25. As a Mayor, I want to park only the subgraph affected by a Planning Exception, so that unrelated delivery continues.
26. As a Mayor, I want dependency readiness tied to verified integration, so that downstream work never starts from an unavailable prerequisite.
27. As an implementer, I want a self-contained Vertical Slice Bead and fresh context, so that I can deliver without loading the entire Planning Run.
28. As an implementer, I want pre-agreed public test seams, so that red/green cycles prove behavior instead of internal structure.
29. As an implementer, I want bounded repair attempts and preserved failure evidence, so that repeated failure becomes actionable rather than hidden churn.
30. As an independent reviewer, I want the exact ticket diff and its Spec trace, so that I can assess fidelity and design without sharing the author's assumptions.
31. As an outcome reviewer, I want the exact assembled multi-ticket diff, so that I can detect emergent coupling and cross-ticket drift once without repeating ticket review.
32. As a project maintainer, I want Factory Knowledge separated from Project Knowledge, so that reusable method stays generic and domain rules stay with their project.
33. As a project maintainer, I want legacy rules treated as archive evidence, so that old choices do not silently become target policy.
34. As a project maintainer, I want each project to select its checks and autonomy inside common safety principles, so that maturity and risk shape the workflow without weakening people/data boundaries.
35. As a project maintainer, I want cross-repository revisions verified together, so that individually green components are not mistaken for an interoperable outcome.
36. As a future adopter, I want a Git-distributed, per-operator Factory with a concise setup tutorial, so that I can run my own City without depending on Benjamin's environment.
37. As a Factory designer, I want every adaptation measured against Matt's Method Baseline, so that added complexity must demonstrate value.
38. As a Factory designer, I want gates to retire or return by predefined evidence, so that autonomy evolves without silently discarding safeguards.
39. As a Factory designer, I want comparable simple and complex canaries after activation, so that aggregate metrics do not hide regressions by work class.
40. As a Factory designer, I want direct cutover and fix-forward repair, so that the legacy path cannot become an indefinite fallback.

## Implementation Decisions

### Method and authority

- Confidence and maintainability are optimized before autonomy and throughput. Measures prioritize lost decisions, escaped defects, human rework, and maintainability, then elapsed time and tokens per accepted outcome. [Q1, Q33]
- The scope is the project-agnostic Software Factory and its contracts with projects. Product code changes require a demonstrated need and separate authority. [Q2]
- Matt's method and observable contracts are the Method Baseline. Sandcastle topology, tracker, and provider assumptions are not copied. [Q13]
- Gas City, Beads/Dolt, and one Mayor remain the working architectural presumption, subject to falsification by prototypes. [Q6]
- The Mayor is the unique delivery orchestration authority, not the whole Factory or the only planning context. Operator surfaces are adapters, never another orchestrator. [Q11]
- Universal safety principles govern people and data; autonomy and gates vary with project state, maturity, risk, novelty, oracle quality, reversibility, and observed evidence. [Q4, Q38, Q39, Q50]

### Intent and design

- `grill-with-docs` is the provisional normal entry. Work that exceeds one healthy session promotes to Wayfinder; real simple and complex requests compare this with Wayfinder-first. [Q7]
- In-session questions need no Bead. Multi-session research, grilling, prototypes, and prerequisite decisions use Planning Decision Beads. Implementation surprises return to planning only when they change intent, scope, approved behavior, acceptance, or topology. [Q8]
- A Wayfinding Run consists of one Planning Map Bead and non-executable Planning Decision Beads. Each session claims and resolves one child, records evidence there, updates the map, and closes. [Q17, Q21, Q25, Q31]
- Fog belongs to the Planning Map. Normal upstream resolution rules determine when the route is clear; no second fog audit is introduced. [Q21]
- Planning and Delivery Beads share one authoritative Beads/Dolt Work Graph and are separated by mandatory positive Work Plane metadata. [Q20]
- Planning Run continuity lives in the Planning Graph and linked evidence, not in retained chat sessions or transcript mirroring. [Q28, Q29, Q31]
- Pausing, resuming, and abandoning follow the observable behaviors in the acceptance criteria. [Q36]

### Canonical artifacts and decomposition

- The adapted `to-spec` output is the sole canonical Spec. Explicit post-synthesis approval changes its state to Approved Spec and closes the Planning Map; no separate Release Contract exists. [Q9, Q12, Q21]
- The Spec and Ticket Graph Draft are temporary Planning Artifacts with stable identity and content digest. They are referenced—not copied wholesale—from Planning and Delivery Beads, frozen during delivery, and allowed to expire after convoy closure. [Q19]
- The Planning Run owns exactly one `to-tickets` decomposition authority. It produces vertical slices and explicit dependency edges in a temporary draft. [Q10, Q18]
- Human approval of granularity and blockers is retained during calibration and for new or risky classes. A class may lose this gate only through comparable canary evidence and regains it on regression. [Q14]
- A deterministic Mayor-owned write door atomically publishes the approved slices, edges, Spec trace, execution contracts, and convoy. It validates shape and invariants but never reinterprets the draft. [Q18]
- The Matt path joins the Delivery Workflow at the convoy continuation boundary. Existing `planning-base` remains available only to methodologies that genuinely use separate requirement and plan artifacts. [Q16]

### Delivery, review, and acceptance

- Each ticket uses a fresh context. One implementer writes a failing public-behavior test and minimal implementation in repeated red/green cycles at approved seams. A separate test author is an experiment, not the default. [Q47]
- Deterministic checks run on every ticket. Initially one independent reviewer covers both Spec fidelity and non-automated design quality; selective skipping is allowed only for predefined proven low-risk classes with sampling and regression tracking. [Q48]
- A multi-ticket outcome receives one independent assembled-diff review for unique interaction risks. Single-ticket outcomes receive no duplicate final model review. [Q51]
- Technical repair stays within a bounded ticket attempt budget derived from evidence; semantic or topology change follows the Planning Exception path. [Q22, Q53]
- Dependency readiness requires prerequisite verification and integration into the configured working branch. [Q54]
- Reversible ticket code may merge before outcome acceptance. Delivered and Accepted remain distinct, and sensitive effects require explicit human decision. [Q49, Q50, Q52]
- Cross-repository outcomes require isolated verification of the exact participating revisions. Acceptance rejection is handled according to whether it is a Spec mismatch, changed intent, or active danger. [Q55, Q56]

### Knowledge, portability, and operations

- Target Factory Knowledge and Project Knowledge are designed from validated current decisions. The existing corpus is a read-only legacy archive consulted only for concrete recurring problems or recoverable solutions. [Q27, Q35]
- The Project Planning Profile points to authoritative project sources, its Work Graph, participating rigs, genuine local extensions, checks, thresholds, and autonomy without copying them into Factory Knowledge. [Q15, Q35, Q38]
- The initial distribution is Git-only and per operator. Supported host scope is Benjamin's Windows machine with Ubuntu under WSL. Shared multi-user service, managed upgrades, and other host claims require later evidence. [Q37, Q41, Q42]
- Project access is denied across projects by default and explicitly granted for declared cross-project outcomes. Existing rig organization is not accepted as proof; the boundary must be prototyped. [Q43]
- Monitoring is deterministic and zero-token while nothing changes. Planning concurrency starts high and is reduced only from observed machine pressure. [Q30, Q44]
- Model roles are capability-defined and provider-independent. Astra and Fable are prohibited, medium is the maximum reasoning effort, and provider switches must preserve Planning Run identity. [Q24, Q28, Q46]
- New planning cuts over directly once operable and is repaired forward. Existing delivery may finish; affected planning pauses during outage while independent delivery continues. [Q3, Q34, Q40, Q45]
- Bootstrap is selective reconstruction: quarantine the legacy planning path and cockpit as read-only evidence, retain Gas City, Beads/Dolt, GitHub, and the current Delivery Workflow only as freshly justified substrate, build the minimum new planning kernel beside them, then use the rebuilt cockpit as the first live canary after cutover. The legacy cockpit is a catalogue of lessons, not the target design. [Benjamin, 2026-09-23]

## Lifecycle and State Transitions

1. `REQUESTED → UNDERSTANDING`: create a bounded Planning Run and load its Project Planning Profile.
2. `UNDERSTANDING → SIMPLE_SYNTHESIS`: the route fits one healthy session and Shared Understanding is confirmed.
3. `UNDERSTANDING → WAYFINDING`: the route exceeds one healthy session; create a Planning Map and decision frontier.
4. `WAYFINDING → WAYFINDING`: resolve one child, record evidence, update the map, and graduate newly specifiable fog into children.
5. `WAYFINDING → SPEC_AWAITING_APPROVAL`: the map is clear and no open children remain; synthesize one Spec without another interview.
6. `SPEC_AWAITING_APPROVAL → APPROVED_SPEC`: Benjamin explicitly approves this exact digest; close the Planning Map.
7. `SPEC_AWAITING_APPROVAL → WAYFINDING`: synthesis exposes a contradiction, missing trace, undecided behavior, or new test seam.
8. `APPROVED_SPEC → TICKET_GRAPH_DRAFT`: `to-tickets` proposes self-contained vertical slices and dependency edges.
9. `TICKET_GRAPH_DRAFT → DELIVERY_GRAPH_PUBLISHED`: applicable approval passes and the atomic write door creates the slices and convoy.
10. `DELIVERY_GRAPH_PUBLISHED → DELIVERING`: the Mayor dispatches only eligible delivery-plane work; each ticket uses fresh context, TDD, checks, review, and integration.
11. `DELIVERING → PLANNING_EXCEPTION`: semantic or topology surprise parks only the affected subgraph and creates a planning-plane decision.
12. `PLANNING_EXCEPTION → DELIVERING`: clarification resumes the existing slice, or an immutable revised Spec/draft patches unfinished delivery work after validation.
13. `DELIVERING → DELIVERED_OUTCOME`: all required ticket, integration, assembled-diff, and cross-repository evidence passes.
14. `DELIVERED_OUTCOME → ACCEPTED_OUTCOME`: the owner accepts behavior or proven-class evidence is sufficient.
15. `DELIVERED_OUTCOME → REPAIR_OR_REPLAN`: rejection is classified as Spec mismatch, changed desired behavior, or active danger.

At any pre-publication state, `PAUSED` retains durable planning state and releases sessions; `ABANDONED` closes without delivery publication. After cutover, an outage suspends affected Planning Runs and repairs the new path; it never transitions back to the legacy planner.

## Testing Decisions

### Primary seam

The highest practical seam is one isolated fixture City exercised through its public operator and deterministic write-door interfaces. A scenario begins with a project intent and observes only externally meaningful outputs: Planning Run and Work Plane states, artifact identity/digest, approval transitions, published graph/convoy, Git integration evidence, Delivered/Accepted distinction, and visible escalation. It does not assert prompt wording, internal agent steps, or a specific formula/session allocation.

This seam is proposed by this synthesis and therefore requires Benjamin's explicit approval with the Spec.

### Required behavioral coverage

- Simple Planning Run, multi-session Wayfinding Run, pause/resume/abandon, and cross-surface/provider resumption without repeated decisions.
- One-writer artifact behavior, reproducible digest, freeze during delivery, immutable revision on behavioral change, and expiry after closure.
- Positive routing: planning work is never dispatchable; only validated convoy-attached delivery work enters the Ready Frontier.
- Atomic Ticket Graph Draft publication, exact edge preservation, rejection of partial or semantically interpreted publication, and revision through the sole decomposition authority.
- Concurrent independent decision claims and map updates without lost writes or double resolution.
- Planning Exception classification, affected-subgraph parking, unrelated progress, tactical resume, and semantic patching.
- TDD at public seams, deterministic checks, independent ticket review, selective-review qualification/restoration, assembled-diff review, and bounded repair evidence.
- Dependency readiness after verified integration, exact multi-repository assembly, and Delivered versus Accepted transitions.
- Project-default filesystem isolation, explicit cross-project grant, sensitive-effect human gates, and zero-token unchanged monitoring.
- Direct cutover, affected-run outage suspension, fix-forward recovery, and absence of legacy-planner fallback.

### Prior art and test quality

The repository already uses Python unit/contract tests and shell end-to-end fixture tests around CLI doors, formulas, routing guards, worktrees, delivery evidence, provider failover, liveness, and the Cockpit. Extend those styles where they express public contracts. Add a broader fixture-City acceptance harness only where existing seams cannot observe the end-to-end lifecycle.

A good test asserts public behavior or a durable contract, fails before the behavior exists, remains provider-independent where the role contract is provider-independent, and does not lock in a candidate Gas City wiring. Prototype results must distinguish TARGET, CONFIGURED, OBSERVED, and PROVEN.

## Experiments and Initial Adaptation Register Entries

These entries must be created in the single Adaptation Register during decomposition/implementation; this table is their planning contract, not a second register.

| Adaptation or experiment | Baseline / purpose | Observable signal and review point | Retain, replace, or remove rule |
| --- | --- | --- | --- |
| Gas City orchestration of Matt's method | Matt does not prescribe Gas City; preserve one Factory topology | Prototype simple and Wayfinding Runs through the convoy boundary | Retain only if method contracts and decision continuity survive without duplicate authority |
| Planning Artifacts instead of issue-tracker Spec publication | `/to-spec` publishes to a tracker; Q19 requires temporary identity/digest artifacts | Reproducibility, traceability, freeze and expiry canaries | Retain if Beads remain concise and exact content remains recoverable |
| Explicit Spec approval | Manual skill use implies handoff; automation needs an observable boundary | Material misunderstandings caught versus delay | Removal requires Benjamin's later decision; replace with automatic handoff only if approved |
| Ticket Graph Draft approval | Matt explicitly reviews granularity and blockers | Decomposition drift and downstream rework by work class | Remove for a qualified class; restore on regression |
| Optional Spec integrity check | Extra calibration control | Distinct defects caught and token/time cost | Remove if redundant; never make it another fog audit |
| Durable Planning Graph and two Work Planes | Multi-session Gas City adaptation | Lost decisions, accidental dispatch, resumption success | Retain smallest representation that prevents planning/delivery confusion |
| Shared-map collision protection | Upstream write order lacks concurrency guard | Concurrent claim/update stress test and issue reproduction | Keep the smallest mechanism preventing lost updates/double resolution |
| Provider/model role qualification | Provider-independent method and constrained budget | Simple/complex outcome quality, continuity, time, tokens | Choose lowest-cost role mapping meeting acceptance; requalify on regression |
| High initial concurrency | Do not inherit legacy caps | Host pressure, failures, latency, completion quality | Reduce only from observed pressure; Benjamin may adjust |
| Decision-session retention | Brief diagnostic retention after durable resolution | Recovery value versus resource/privacy cost | Reduce toward zero if graph/evidence suffice |
| Cross-surface conversation view | Continuity is required; mirrored transcript is optional | Native availability, zero model calls, maintenance cost | Keep only if native and cheap; otherwise link active session and resume from graph |
| Structured Planning Exception | Matt has no equivalent durable graph repair signal | Correct classification, unnecessary interruption, duplicate escalation | Retain only if real semantic surprises route cleanly |
| One combined independent ticket reviewer | Matt uses two independent review axes | Unique findings, escaped defects, token cost | Split or replace if combined review misses material issues |
| Selective model-review exemption | Matt reviews every ticket | Yield/cost for comparable low-risk classes plus sampled skips | Permit only predefined proven classes; restore on defects/rework |
| Whole-outcome assembled-diff review | Added cross-ticket interaction gate | Unique findings versus duplicate comments and tokens | Retain only if it catches interaction risks cost-effectively |
| Project-owner acceptance gate | Human validates early/new/risky outcomes | Behavior defects/rework caught versus delay | Replace only for proven classes with predefined evidence; restore on regression |
| Project filesystem isolation | Rig boundaries are not proof | Attempted cross-project reads in isolated and explicit multi-project cases | Retain a verified enforcement mechanism; do not claim unsupported isolation |
| Direct cutover and fix forward | Migration adaptation, not Matt workflow | Outage recovery and absence of legacy fallback | Retain unless new evidence exposes an unrecoverable target-path defect |
| Zero-token monitoring | Added operating constraint | Model calls while unchanged and missed actionable changes | Retain if unchanged state costs zero and meaningful change still wakes judgment |

## Constraints

- Preserve all common safety principles for people and data. Project configuration cannot silently disable them.
- Never expose secrets, widen personal-data access, publish or send externally, spend money, mutate production, or perform unrecoverable destruction without explicit human authority.
- Keep one authoritative Beads/Dolt Work Graph and one delivery Mayor. Do not add a second tracker or orchestrator.
- Keep one canonical Spec and one Ticket Graph Draft writer at a time. Do not create a Release Contract projection for the Matt path without later compatibility evidence.
- Do not use Astra or Fable; never exceed medium reasoning effort.
- Initial support is Benjamin's Windows/Ubuntu-WSL host. Claims for other hosts require verification.
- New target rules require current justification. Similarity to legacy behavior is not justification.
- Already-created delivery work may complete during reconstruction; new planning does not return to the old path after cutover.

## Out of Scope

- Refactoring SayMyName Backend or Frontend product behavior without a demonstrated dependency.
- Implementing this Spec, running `to-tickets`, publishing delivery Beads, or choosing migration slices in the current Planning Run step.
- Selecting the exact Gas City formula, session-template, agent, order, provider, model, lock, retention, or Cockpit wiring before the specified prototypes.
- Rewriting upstream `planning-base` for methodologies that genuinely use separate requirements and plan artifacts.
- Reusing the legacy cockpit's information architecture, screens, or implementation as the design baseline for the rebuilt cockpit.
- Bulk migration or audit of legacy contexts, memories, rules, ADRs, provider policy, or documentation.
- A shared multi-user Factory service, managed updates, release channels, support commitments, or professional cross-platform compatibility.
- Production deployment, public hosting, real user/data exposure, spend, or other ADMIN effects.
- A pre-cutover simple-plus-complex pilot gate. Prototypes resolve technical unknowns; live canaries begin after direct activation.
- Requiring transcript mirroring between operator surfaces when durable decision continuity is sufficient.
- Defining a universal numeric repair budget, review-skip threshold, or concurrency limit before measurements exist.

## Provenance and Decision Trace

This Spec introduces no new product or architecture decision. It synthesizes the confirmed Shared Understanding and makes one required `/to-spec` proposal: the primary external-behavior test seam described above.

| Source | Contribution |
| --- | --- |
| Grilling checkpoint, Q1–Q56, confirmed 2026-09-23 | Authoritative validated decisions, unresolved technical experiments, terminology, and lifecycle constraints |
| `CONTEXT.md` | Canonical domain vocabulary |
| Autonomy-frontier research, evidence as of 2026-09-22 | Evidence for adaptive human/agent boundaries and Spec-without-Release-Contract decision |
| Agentic TDD/review research, 2026-09-23 | Pinned Matt workflow facts and limits of evidence for test-author/reviewer topology |
| Matt Pocock `/to-spec` at pinned commit | Synthesis-only process, template, public-behavior test seam guidance, and no-path/no-snippet discipline |
| Current repository observation | Existing Gas City planning roles/formulas are legacy evidence; current tests demonstrate CLI, fixture, contract, routing, and end-to-end test styles |
| Benjamin's cockpit-canary approval, 2026-09-23 | Selective reconstruction, legacy planning/cockpit quarantine, independent fixture oracle, and cockpit V2 as the first live canary after minimum-kernel cutover |

Decision coverage: Q1–Q16 are represented in Method and authority plus Canonical artifacts; Q17–Q32 in Intent and design, Lifecycle, and Experiments; Q33–Q46 in Knowledge, portability, operations, Constraints, and direct-cutover criteria; Q47–Q56 in Delivery, Testing, and acceptance transitions. Exact wording and reversals remain in the checkpoint; this Spec is the canonical bounded coordination artifact, not a replacement archive for the interview evidence.

## Further Notes

- Approval must name this Planning Artifact ID and exact digest. Approval changes metadata state only; any semantic edit produces a new digest and requires approval of that revision.
- The content digest is intentionally scoped below the metadata table so updating the digest/state fields is not self-referential.
- The Adaptation Register becomes durable Factory Knowledge only when its entries are instantiated with implementation evidence; this Spec merely requires them.
- No contradiction or genuinely new design decision was found during synthesis. The exact Q11 wiring remains deliberately unresolved and is testable through the listed prototypes.
- After initial approval, Benjamin explicitly approved one bounded migration/canary clarification: build and cut over the minimum new planning kernel before rebuilding the cockpit as the first non-critical live outcome; keep independent fixture tests as the Factory oracle and treat the legacy cockpit as read-only evidence.
