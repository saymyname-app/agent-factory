# Agentic Software Factory

This context defines the language used to describe the project-agnostic system that turns human intent into verified software outcomes. English terms are canonical in code and durable documentation; French aliases support conversation and localized interfaces without creating a second domain model.

## End-to-end system

**Software Factory**:
The complete socio-technical system that shapes intent, manages and orchestrates work, executes changes, verifies outcomes, and exposes operator interfaces.
_French conversational alias_: usine logicielle agentique, la Factory; **usine** (visible dans le cockpit)
_Avoid_: City, Gas City, orchestrator, harness

**Cockpit**:
The operator interface for observing and steering the Software Factory across product, work, agent, and operational views.
_French conversational alias_: cockpit, interface de pilotage
_Avoid_: control plane, orchestrator, Product Cockpit, Factory Cockpit

**Operator Request**:
An open condition that only the operator can move forward, because it needs a decision at the operator's tier or a physical action on the operator's side; it is not information. A problem the Factory handles itself (such as a Mayor-first escalation not yet promoted) is not an Operator Request. A notification is only the delivery of a request to the operator's phone.
_French conversational alias_: demande opérateur, ce qui t'attend
_Avoid_: alert, todo, notification

**Operator Language**:
The single natural language, set once in `config/operator.toml`'s `language` field for every project, in which all Cockpit-facing and pushed text must be written; read through `bin/operator-config language` rather than re-parsed by callers.
_French conversational alias_: langue de l'opérateur
_Avoid_: locale, i18n, per-project UI language

**Cockpit Lexicon**:
The fixed starting set of domain words the Cockpit may show at the interface without translation, held as this glossary's own conversational aliases (each marked "visible dans le cockpit" where its canonical term is defined above or below) rather than as a second list anywhere else in code or docs; growing it is a pull request on this file. Starting lexicon: usine, projet, agent, ticket, PR, tests automatiques (CI), Spec, carte de planification, graphe de tickets, proposition, rituel, décision.
_French conversational alias_: lexique du cockpit
_Avoid_: UI copy list, second glossary, translation table

**Operator Action**:
A pure-code, traced gesture Benjamin performs from the Cockpit without spending agent tokens -- acknowledging or deferring an Operator Request, answering a NEEDS BENJAMIN with a prepared option, accepting or rejecting a proposal, and the like -- always recorded on the source Bead so the Factory, the PC, and the iPhone agree on what happened.
_French conversational alias_: action opérateur (visible dans le cockpit)
_Avoid_: agent action, API call, unrecorded Bead update

**Proposal**:
An improvement idea an agent or an order records through the proposal door (`bin/proposal-door`) instead of starting work on it; it carries one of two classes chosen by its producer at creation (ADR-0029). A `maintenance` proposal corrects an observed defect of the Factory without changing what the operator sees or must do nor a method rule: the door turns it into one bug bead authorized by ADR-0029 that the Mayor dispatches, and the Cockpit shows it only in its health zone and journal. A `decision` proposal changes what the operator sees or must do, a method rule, a spend, a consent, personal data, an irreversible effect or a product behaviour: it is an Operator Request, carries exactly one recommended option with its reason, and the operator accepts, rejects or defers it. In doubt the class is `decision`; a maintenance bead that turns out to touch the operator's tier is stopped and reconverted, never pursued.
_French conversational alias_: proposition (visible dans le cockpit) ; proposition de maintenance, proposition de décision
_Avoid_: improvement ticket, self-improvement, idea backlog, auto-filed work

**Freshness**:
Whether a value shown by the Cockpit may be presented as current: fresh when it was read successfully within its Validity window, stale when only an older last known value exists, which is never presented as current, and unknown when it was never read or its source is failing.
_French conversational alias_: fraîcheur (à jour, périmée, inconnue)
_Avoid_: live, real-time, cached

**Validity window**:
The maximum age, set per source, beyond which a value shown by the Cockpit is no longer fresh.
_French conversational alias_: délai de validité
_Avoid_: TTL, refresh rate

**Heartbeat**:
A content-free periodic signal the Cockpit sends to an outside watcher, whose silence reveals that the Cockpit, the Software Factory, or its host is down.
_French conversational alias_: heartbeat, dead man's switch
_Avoid_: health check, ping alone, keepalive

**Clean stop**:
An operator-triggered stop of the Software Factory that starts no new work and lets in-flight work reach a resume point without losing anything, so that a restart resumes the same work.
_French conversational alias_: arrêt propre
_Avoid_: shutdown, drain (a Gas City mechanism), pause

## Lifecycle

**Intent & Design Workflow**:
The collaborative workflow that turns an initial intent into explicit product, system, program, and slicing decisions suitable for approval.
_French conversational alias_: cadrage et conception
_Avoid_: upfront, intake, planning alone, Wayfinder

**Shared Understanding**:
The confirmed human-agent agreement about intent, outcomes, constraints, decisions, and material unknowns; it is a state of agreement, not a document.
_French conversational alias_: compréhension partagée
_Avoid_: spec, PRD, Release Contract

**Spec**:
The temporary canonical coordination artifact synthesized from resolved planning decisions for one bounded multi-session outcome, including its intended behavior, boundaries, material decisions, and acceptance evidence. It is stored as a readable Planning Artifact with stable identity and content digest, frozen during delivery, and may expire after the convoy closes; durable domain and architecture knowledge belongs in the glossary and ADRs, while delivered behavior belongs in code and tests.
_French conversational alias_: spécification; **Spec** (visible dans le cockpit)
_Avoid_: permanent system documentation, SDD source of truth, Release Contract

**Approved Spec**:
A Spec whose Shared Understanding has been confirmed and which therefore authorizes decomposition and delivery for that outcome; approval is a state of the same temporary artifact, not a second document or a prose-review ceremony.
_French conversational alias_: spécification approuvée
_Avoid_: Release Contract, approved summary

**Planning Run**:
A bounded, independently resumable instance of the Intent & Design Workflow, chartered by `/wayfinder`. Charting that finds no fog takes the No-fog exit and finishes in the same session; charting that finds fog, or that outgrows one session, continues as a Wayfinding Run spanning disposable decision sessions whose continuity is anchored by a Planning Graph.
_French conversational alias_: session de cadrage, parcours de planification
_Avoid_: Mayor, campaign, delivery run, chat when durability is implied

**Planning Session**:
One agent conversation used within a Planning Run, either to charter it, to resolve a particular Wayfinding decision, or to reach the No-fog exit. Its end does not end the Planning Run.
_French conversational alias_: conversation de planification
_Avoid_: Planning Run, Planning Graph

**No-fog exit**:
The way a Planning Run ends when `/wayfinder`'s charting finds no fog: Benjamin's exact words and the date (Paris time) are recorded as evidence in place of a Planning Graph, and the run finishes in the same session as an Unmapped Planning Run.
_French conversational alias_: sortie sans brouillard
_Avoid_: self-declared flag, skipping the map

**Unmapped Planning Run**:
A Planning Run that reached its Destination through the No-fog exit instead of a Planning Graph; its Spec carries the No-fog exit's evidence in place of a linked Planning Map Bead. If it later surfaces fog or outgrows one session, it resumes `/wayfinder` at map creation rather than spanning several sessions unmapped.
_French conversational alias_: cadrage sans carte
_Avoid_: Wayfinding Run

**Planning Run Reservation**:
The human's commitment that the next Planning Run to be approved and published is a named one; any other Planning Run is refused at Spec approval while the reservation is active. A reservation may name a following one, which becomes active once the first is published.
_French conversational alias_: réservation de cadrage
_Avoid_: lock, queue, priority

**Planning Graph**:
The non-executable graph of a Planning Map Bead, its Planning Decision Beads, and their dependency edges that anchors a multi-session Wayfinding Run.
_French conversational alias_: graphe de planification
_Avoid_: Delivery Work Graph, implementation convoy, session tree

**Planning Map Bead**:
The root and low-resolution index of a Wayfinding Run: its Destination, standing notes, a pointer to each decision made, the fog not yet specified, and what is ruled out of scope, without restating any decision's detail.
_French conversational alias_: Bead carte Wayfinder; **carte de planification** (visible dans le cockpit)
_Avoid_: Spec, implementation epic, conversation transcript

**Destination**:
What reaching the end of a Wayfinding Run looks like (a Spec to hand off, a decision to lock, or a change made in place); it fixes the run's scope and every Planning Decision Bead is judged against it.
_French conversational alias_: destination
_Avoid_: goal, epic, outcome when scope is meant

**Out of Scope**:
Work consciously ruled beyond a Wayfinding Run's Destination; it is recorded on the Planning Map Bead with its reason and never graduates into a Planning Decision Bead.
_French conversational alias_: hors périmètre
_Avoid_: fog, backlog, later

**Planning Decision Bead**:
A non-executable child of a Planning Map Bead that resolves one research, grilling, prototype, or task question and records its resolution plus linked evidence.
_French conversational alias_: Bead de décision de planification
_Avoid_: implementation ticket, Vertical Slice, agent session

**Ticket Graph Draft**:
The temporary, non-executable, structured Planning Artifact containing proposed Vertical Slices, acceptance criteria, target rigs, and blocking edges that `to-tickets` presents for approval before atomic publication. It stays frozen with the Spec during delivery and is closed with it when the convoy closes.
_French conversational alias_: brouillon du graphe de tickets; **graphe de tickets** (visible dans le cockpit)
_Avoid_: delivery Bead, convoy, Delivery Work Graph, second decomposition

**Planning Artifact**:
A temporary, never-routed planning-plane Bead owned by a Planning Run, such as a Spec or a Ticket Graph Draft, identified by a stable ID and a content digest frozen at approval. Planning Artifacts coordinate multi-session work but are not permanent system documentation.
_French conversational alias_: artefact de planification
_Avoid_: delivery Bead, durable product documentation, source of truth after delivery

**Method Baseline**:
The faithful reference workflow and observable contracts reproduced before deliberate adaptation, used as the comparison point for prototypes, canaries, and measurements.
_French conversational alias_: méthode de référence, baseline méthodologique
_Avoid_: implementation topology, copied infrastructure, best-effort inspiration

**Adaptation Register**:
The single durable record of differences from the Method Baseline and added workflow controls, including why each exists, its test evidence, and its retain, replace, or remove decision.
_French conversational alias_: registre des adaptations
_Avoid_: separate deviation and experiment registers, changelog

**Factory Knowledge**:
The reusable method, safety principles, and operating rules of the Software Factory that apply across projects.
_French conversational alias_: connaissances de l'usine
_Avoid_: project domain context, legacy archive

**Project Knowledge**:
The domain language, product and architecture decisions, and repository-specific rules for one project using the Software Factory.
_French conversational alias_: connaissances du projet
_Avoid_: Factory Knowledge, City-wide defaults

**Project Planning Profile**:
The project-scoped configuration that binds a planning methodology to its authoritative domain sources, Work Graph, participating rigs, and genuine rig-local extensions.
_French conversational alias_: profil de planification du projet
_Alias_: descripteur de projet
_Avoid_: repository-wide duplicate, City-wide global defaults, product specification

**Delivery Workflow**:
The workflow that turns an Approved Spec into a verified software outcome.
_French conversational alias_: flux de livraison
_Avoid_: Factory, City, implementation

**Delivered Outcome**:
An outcome whose implementation and required technical verification are complete, awaiting the project owner's behavior acceptance unless its work class has predefined sufficient evidence.
_French conversational alias_: résultat livré
_Avoid_: Accepted Outcome, closed Bead alone

**Accepted Outcome**:
A Delivered Outcome accepted by the project owner's recorded words at a named commit and then merged, or whose proven work class has met predefined acceptance evidence. The work-class clause has no use for an Outcome born of a Planning Run: only the owner's words accept it.
_French conversational alias_: résultat accepté
_Avoid_: merely merged code, Delivered Outcome, "refused" (the three answers to a Delivered Outcome are accepted, findings returned, abandoned)

**Direct Delivery**:
Delivery of an Approved Spec by one operator session that Benjamin orchestrates, with subagents, outside any convoy and through the same pull-request gate. A preference of his, not a gate (`docs/PLANNING_RUN.md`).
_French conversational alias_: livraison directe
_Avoid_: vibe coding, bypass, hors usine

**Vertical Slice**:
A bounded increment that crosses the layers necessary to produce behavior demonstrable on its own on the launched product, through to the point where the product serves it.
_French conversational alias_: tranche verticale
_Avoid_: layer task, frontend ticket, backend ticket, behavior verified only by a test on an internal function

**Chantier**:
The canonical term for Outcome: one Planning Run and the Delivery Work Graph convoy it produced, tracked as a single unit from Cadrage through Spec, Graphe, Livraison, Livré, Accepté, and (where applicable) Promu. Delivered Outcome and Accepted Outcome name two of its states.
_French conversational alias_: chantier (visible dans le cockpit)
_Avoid_: Project (a Rig grouping), ticket, convoy alone

## Delivery (Spec af-wf4w5r, Planning Run D01)

**Declared Scope**:
The optional file paths a ticket declares so the publication door can put overlapping tickets in series. It never bounds what the author may touch.
_French conversational alias_: périmètre déclaré
_Avoid_: scope alone, "hors périmètre" (reserved for Out of Scope)

**Validated Prototype**:
The frozen version of a chosen interface prototype that the project owner confirmed, referenced by commit in the Spec, and the target of the fidelity proof until acceptance.
_French conversational alias_: prototype validé
_Avoid_: prototype alone, maquette, "variante D"

**Prototype Fold**:
The Vertical Slice that folds a Validated Prototype into the real code, serving all its prototyped states at the real address before any other interface ticket.
_French conversational alias_: repli du prototype
_Avoid_: promoting the prototype file as is

**Seam**:
A public boundary where a test observes behavior without entering the code (Matt Pocock's sense), agreed during planning.
_French conversational alias_: seam
_Avoid_: internal function, a boundary the author picks while writing the test

**Criterion Test**:
The executable form of one acceptance criterion of a ticket, written before the code, proven red at the start commit, then frozen.
_French conversational alias_: test de critère
_Avoid_: test d'acceptation, test E2E

**Test Case**:
One test method or function: the unit that passes or fails alone, and that a before/after comparison counts by name. A test file holds several.
_French conversational alias_: cas
_Avoid_: test alone (a file or a case?), scenario

**Test Level**:
How far from the code a Test Case observes a tool: low (the entry function, in the test's own process), command line (one tool as a real process), whole journey (several tools chained from one end of a flow to the other). A pass or a refusal is proven once, at the lowest level where it can be observed; the level above proves the transmission only (`docs/TEST_GUIDELINE.md`).
_French conversational alias_: étage
_Avoid_: layer, unit/integration/E2E, pyramid

**Test Decor**:
Everything a Test Case needs in place before its own gesture (repository, tracker state, files, published graph). Built once per test file, then copied for each case; the values a case verifies stay written in the case.
_French conversational alias_: décor
_Avoid_: fixture (here: the files under `tests/fixtures/`), setup, context

**Ticket Exit**:
The structured, tool-called way a worker ends a ticket: finished, Planning Exception, operator request, technically blocked, or interrupted.
_French conversational alias_: sortie de ticket
_Avoid_: free-text status, final message

**Ticket Handoff**:
The structured record a worker leaves on its ticket in the tracker: done, deviations, not done, findings outside the ticket, plus statements computed by code.
_French conversational alias_: compte rendu de ticket
_Avoid_: notes, commentaire, follow-up

**Evaluator**:
A fresh, read-only session that uses the launched product and returns observations with evidence; it never reads the diff and never writes a global verdict.
_French conversational alias_: évaluateur
_Avoid_: QA, testeur, validateur, relecteur (reserved for who reads code or a graph)

**Ticket Evaluation**:
The Evaluator's observation of one ticket's demonstration line and criteria on the launched product, before that ticket merges.
_French conversational alias_: évaluation de ticket
_Avoid_: QA pass, review

**Outcome Evaluation**:
The Evaluator's observation of every numbered user story of the Spec on the assembled product, at the end of the Spec and before acceptance.
_French conversational alias_: évaluation du résultat
_Avoid_: final QA, acceptance

**Review Finding**:
A deviation raised by the code reviewer on one axis, with or without a cited source.
_French conversational alias_: constat de revue
_Avoid_: commentaire, remarque, issue, bug

**Blocking Finding**:
A Review Finding that cites a line of the Spec, of the ticket, or a written rule of the repository; it prevents the merge until it has a favorable verdict.
_French conversational alias_: constat bloquant
_Avoid_: commentaire, remarque, issue, bug

**Evidence Record**:
One piece of evidence recorded by the capture tool or a Factory script, tied to a commit, never written by an agent.
_French conversational alias_: preuve
_Avoid_: capture alone, log

**Evidence Pack**:
The document generated by code from Evidence Records, tied to a commit, that the project owner judges at acceptance.
_French conversational alias_: dossier de preuves
_Avoid_: rapport, résumé, description de PR

**Acceptance Request**:
The request the escalation door sends the project owner when a Delivered Outcome is ready, with the link to its Evidence Pack.
_French conversational alias_: demande d'acceptation
_Avoid_: notification, PR

**Acceptance Session**:
The session in which the project owner judges the launched product and its Evidence Pack.
_French conversational alias_: session d'acceptation
_Avoid_: revue, QA, démo

**Owner Finding**:
A finding the project owner returns at acceptance, structured and routed by code. Distinct from a worker's finding outside its ticket.
_French conversational alias_: constat du propriétaire
_Avoid_: retour, feedback, bug

## Durable work

**Work Graph**:
The durable graph of work items and their dependency relationships.
_French conversational alias_: graphe de travail
_Avoid_: queue, backlog, memory, ticket graph

**Delivery Work Graph**:
The approved executable Work Graph published once by `to-tickets` as Vertical Slice Beads and dependency edges, then executed without semantic redesign: by the Mayor, or by code (`bin/convoy-advance`) when its convoy carries the new-flow mark.
_French conversational alias_: graphe de livraison
_Avoid_: Planning Graph, Ticket Graph Draft, queue

**Work Plane**:
The mandatory routing classification of a Bead. Planning-plane Beads are durable but non-routable; delivery-plane Beads are routable only after validation and convoy attachment.
_French conversational alias_: plan de travail
_Avoid_: priority, Bead type, workflow phase inferred from status

**Ready Frontier**:
The Work Graph items whose blockers are resolved and which are eligible to be claimed.
_French conversational alias_: frontière éligible
_Avoid_: queue, backlog

**Bead**:
The canonical durable work item stored and tracked by Beads.
_French conversational alias_: Bead
_Avoid_: ticket, task, issue when referring to a persisted Bead

**Decision Bead**:
A Bead whose resolution is a durable decision needed by other planning work; ordinary questions inside one grilling session are not Decision Beads.
_French conversational alias_: Bead de décision; **décision** (visible dans le cockpit)
_Avoid_: implementation ticket, every question

**Planning Exception**:
A structured signal that delivery has encountered a question about approved intent, behavior, or work topology requiring the affected work to return to its Planning Run.
_French conversational alias_: exception de planification
_Avoid_: operational retry, worker-owned redesign

## Orchestration and execution

**Orchestration**:
The coordination of durable work through agents, workflows, routing, gates, and recovery.
_French conversational alias_: orchestration
_Avoid_: work management, runtime, Cockpit

**Mayor**:
The Factory's operations authority. It materializes and advances authorized delivery work of the convoys that do not carry the new-flow mark, without redefining product intent; it never advances, closes or modifies the tickets of a new-flow convoy, which code advances.
_French conversational alias_: Maire
_Avoid_: Product Owner, Cockpit, Gas City

**City**:
A Gas City orchestration workspace that groups registered projects and its configured factory runtime.
_French conversational alias_: ville Gas City
_Avoid_: Software Factory, repository, project

**Rig**:
A project directory registered with a City as a target for agent work.
_French conversational alias_: projet enregistré, rig
_Avoid_: repository when registration is not implied, Software Factory

**Rig file**:
The existing per-Rig registration file under `config/projects/` that declares one Rig's connection to the City; distinct from a Project Planning Profile, which one or more Rig files point to.
_French conversational alias_: fichier de rig
_Avoid_: Project Planning Profile, project descriptor

**Project**:
The unit a Software Factory operator plans and ships toward, identified by a `project_id` and declared once by a Project Planning Profile; exactly one Project owns each Rig.
_French conversational alias_: projet (visible dans le cockpit)
_Avoid_: Rig alone, City

**Roadmap Step**:
One entry of a Project's structured roadmap file (id, title, "done when" condition, order, and to-do / in-progress / done status), referenced by `planning_run_target` when a Planning Run targets it.
_French conversational alias_: étape de roadmap
_Avoid_: milestone, Planning Run, Chantier

**Fixture City Oracle**:
The hermetic public-behavior harness that starts from synthetic project intent
and verifies Planning Run, Work Plane, artifact, publication, integration, and
outcome behavior without depending on a candidate Gas City topology or Cockpit.
_French conversational alias_: oracle de City fixture
_Avoid_: production City, Cockpit test, orchestration implementation

**Agent Harness**:
The instructions, tools, context, feedback loops, and checks that shape how an agent role performs its work.
_French conversational alias_: environnement agentique, harness
_Avoid_: Software Factory, orchestrator, agent

## Project standards

**Standard**:
A rule a project commits to hold on every delivery, enforced either by a tool or by a written rule a reviewer can cite. A check is the mechanism that holds a Standard, not the Standard itself. Taste is judged on a Validated Prototype until it becomes a written or configured rule.
_French conversational alias_: standard
_Avoid_: baseline, guideline, convention, best practice, check

**Code Standard**:
A Standard about code patterns, boundaries, file layout, or writing form.
_French conversational alias_: standard de code

**Design Standard**:
A Standard about visual design, interaction, motion, or accessibility.
_French conversational alias_: standard de design

**Project Standards**:
The Standards owned by a project and kept in each of its rig repositories.
_French conversational alias_: standards du projet

**Default Standards**:
A stack-specific starting set copied from the Factory into a rig; the copy belongs to the project and does not inherit later changes.
_French conversational alias_: standards par défaut

**Derogation**:
Benjamin's recorded permission for a Standard to differ at one named place, with his words, the Paris date and an end. It does not change the Standard everywhere.
_French conversational alias_: dérogation
_Avoid_: Planning Exception

**Frozen List**:
The snapshot of pre-existing violations when Standards are activated on an existing rig; its entries may only decrease unless a named exception passes the ratchet.
_French conversational alias_: liste figée

**Ratchet**:
The check that prevents a Frozen List from growing at delivery.
_French conversational alias_: cliquet

**Never-Frozen Rule**:
A rule whose violations are corrected at activation instead of entering a Frozen List, especially likely bugs.
_French conversational alias_: règle jamais figée
