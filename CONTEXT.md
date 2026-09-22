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

**Release Contract**:
The canonical approved artifact that records the intended outcome, boundaries, acceptance evidence, material decisions, and authorized delivery envelope.
_French conversational alias_: contrat de livraison
_Avoid_: PRD, spec, brief

**Delivery Workflow**:
The workflow that turns an approved Release Contract into a verified software outcome.
_French conversational alias_: flux de livraison
_Avoid_: Factory, City, implementation

**Vertical Slice**:
A bounded increment that crosses the layers necessary to produce independently demonstrable or verifiable behavior.
_French conversational alias_: tranche verticale
_Avoid_: layer task, frontend ticket, backend ticket

## Durable work

**Work Graph**:
The durable graph of work items and their dependency relationships.
_French conversational alias_: graphe de travail
_Avoid_: queue, backlog, memory, ticket graph

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

**Agent Harness**:
The instructions, tools, context, feedback loops, and checks that shape how an agent role performs its work.
_French conversational alias_: environnement agentique, harness
_Avoid_: Software Factory, orchestrator, agent
