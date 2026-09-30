# Agentic Software Factory

This context defines the language used to describe the project-agnostic system that turns human intent into verified software outcomes. English terms are canonical in code and durable documentation; French aliases support conversation and localized interfaces without creating a second domain model.

## End-to-end system

**Software Factory**:
The complete socio-technical system that shapes intent, manages and orchestrates work, executes changes, verifies outcomes, and exposes operator interfaces.
_French conversational alias_: usine logicielle agentique, la Factory
_Avoid_: City, Gas City, orchestrator, harness

**Cockpit**:
The operator interface for observing and steering the Software Factory across product, work, agent, and operational views.
_French conversational alias_: cockpit, interface de pilotage
_Avoid_: control plane, orchestrator, Product Cockpit, Factory Cockpit

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
_French conversational alias_: spécification
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
_French conversational alias_: Bead carte Wayfinder
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
_French conversational alias_: brouillon du graphe de tickets
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
A Delivered Outcome whose behavior the project owner has confirmed or whose proven work class has met predefined acceptance evidence.
_French conversational alias_: résultat accepté
_Avoid_: merely merged code, Delivered Outcome

**Vertical Slice**:
A bounded increment that crosses the layers necessary to produce independently demonstrable or verifiable behavior.
_French conversational alias_: tranche verticale
_Avoid_: layer task, frontend ticket, backend ticket

## Durable work

**Work Graph**:
The durable graph of work items and their dependency relationships.
_French conversational alias_: graphe de travail
_Avoid_: queue, backlog, memory, ticket graph

**Delivery Work Graph**:
The approved executable Work Graph published once by `to-tickets` as Vertical Slice Beads and dependency edges, then executed without semantic redesign by the Mayor.
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
_French conversational alias_: Bead de décision
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
The orchestration authority that materializes and advances authorized delivery work without redefining product intent.
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
