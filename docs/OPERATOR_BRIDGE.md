# Codex operator bridge

This is the human contract for using Codex as the product-facing control surface
for Agent Factory. It covers desktop Codex, CLI Codex, and remote/mobile Codex.

## Product promise

Benjamin can enter through Codex, speak about a product rather than Factory
machinery, and receive a concise authoritative answer or route bounded work to
the Mayor. GitHub does not need to be open on the phone: Codex uses the host's
local repository, shell, authenticated tools, and approval flow.

This bridge does not create a second orchestrator or execution system. New
ideas enter through the Planning Run flow; Gas City and the Mayor alone
coordinate executable work and dependencies, and GitHub proves code delivery.

## Simplest operating protocol

### Desktop or CLI on BenForge

Open the Agent Factory project in Codex with working folder
`/home/benja/agent-factory`. From PowerShell, the deterministic entry is:

```powershell
wsl -d Ubuntu-24.04 -u benja --cd /home/benja/agent-factory
codex
```

The option is two ASCII hyphens: `--cd`, not an em dash.

### Phone

Use Codex Remote to connect to host **BenForge**, then open or resume the task
whose working folder is `/home/benja/agent-factory`. BenForge, its network, and
the Codex desktop app must remain available. The remote session uses the host's
files and tools; it does not copy the Factory onto the phone.

### Factory workspace

For Factory engineering, use the local Codex project rooted at
`C:\Dev\Projects\AgentFactory`. It is a small Windows bridge to the canonical WSL
repository, not a clone. Its commands enter
`/home/benja/agent-factory` explicitly.

Use the upstream Gas City dashboard at port `8372` when detailed sessions,
runs, events, or full transcripts are needed; it makes no model call. The
Cockpit V1 human view, its phone access and the SayMyName preview are retired
(code and docs in Git history, untrusted); Cockpit V2 is the
Planning Run C01.

### Speak in intent, not commands

Examples:

- `Où en est SayMyName ?`
- `Montre-moi seulement le résumé produit.`
- `Explique les détails de l'usine, sans rien modifier.`
- `Discutons de cette idée; ne l'enregistre pas encore.`
- `Enregistre cette décision et propose la prochaine priorité.`
- `Ouvre un Planning Run pour cette idée, sans rien lancer.`
- `Propose cette idée comme prochaine priorité; ne touche pas au travail en cours.`
- `Montre-moi seulement les Planning Runs en cours.`
- `Fais réaliser ce bug par la Factory et préviens-moi quand il est livré.`
- `Diagnostique la Factory en lecture seule.`

Codex must make the action level explicit when ambiguity would change state.

## Action levels

| Level | Meaning | Default behavior |
|---|---|---|
| OBSERVE | Status, diagnosis, explanation | Read-only; no issue, edit, message, or process change |
| DISCUSS | Explore options or make a decision | No mutation unless the user asks to record the result |
| RECORD | Persist an approved decision or work item | Bounded documentation/Beads update with evidence |
| EXECUTE | Deliver a feature, bug fix, or operational change | Route product work through the Mayor/Beads; validate and report delivery evidence |
| ADMIN | Host, credentials, production, public access, spend, destructive recovery | Requires explicit scope and preserves approval/security boundaries |

“Full access” is a capability of the connected host, not standing authority.
Codex uses the least access needed for the stated intent. Availability of a
credential or tool never authorizes secret disclosure, public exposure,
production mutation, spending, irreversible action, or unrelated work.

## Sending mail from the operator path

If a task requires notifying the Mayor or another agent, send it with
`bin/operator-mail <to> -s <subject> -m <message>`, never a raw
`gc mail send`. Raw `gc mail send` from this shell has no live gc session to
attribute the message to and silently resolves the sender to `human` — which
reads as Benjamin himself. `bin/operator-mail` always sends as an explicit
agent identity (`config/operator.toml` `mail_alias`, default `po-agent`) and
self-identifies in the body. Per the Mayor's own prompt, every mail — whatever
its sender — is treated as an agent's request, not a standing order:
Benjamin's decisions reach the Factory only through an approved Spec and its
published ticket graph.

## Project status contract

For `Où en est <projet> ?`, Codex reads that project's own repository and the
live Beads/GitHub state, then answers in plain language:

1. **Current:** the outcome being built, or idle.
2. **Last delivered:** the last merged outcome and its evidence.
3. **Next:** the approved next outcome, if any.
4. **Needs Benjamin:** only a real decision or intervention.
5. **Risk:** only when a verified inconsistency or blocker exists.

Raw issues, agents, sessions, Formula steps, logs, and infrastructure details
stay hidden unless requested or needed to explain a verified risk. New work
enters through the Planning Run flow (`docs/PLANNING_RUN.md`: `/wayfinder`,
`/to-spec`, `spec-approve`, `/to-tickets`, `ticket-graph-publish`); the Mayor
executes approved ticket graphs.

## How Codex resolves context

1. Root `AGENTS.md` defines Factory-wide behavior and points here.
2. `docs/CONTEXT_INDEX.md` selects the minimum durable contract.
3. The target project's nearest `AGENTS.md` and repository docs define its stack, tests, and local safety rules.
4. The relevant Bead defines the current outcome, dependency, scope, and evidence contract.
5. Live Gas City, Git, GitHub, and runtime observations establish what is true now.

This order lets the bridge adapt to SayMyName or a future rig without copying
the full Factory history into every prompt. A new project is ready only when it
has a registered rig, a concise project `AGENTS.md`, authoritative build/test
commands, and a registered Project Planning Profile (`PROJECT_PLANNING_PROFILE.md`).

## Self-improvement protocol

After bounded work, Codex classifies discoveries:

- ephemeral state or task evidence → Beads;
- stable project-specific rule → nearest project documentation or `AGENTS.md`;
- stable Factory-wide rule or architecture → Factory docs and, when structural, an ADR;
- a repeated preventable failure → deterministic validation plus the smallest durable rule that prevents recurrence.

Codex may repair stale documentation as part of an explicitly requested change,
but it does not silently grant itself new authority or rewrite policy from model
memory. Keep instruction files concise; details belong behind the context index.
A new Codex session is the verification boundary after `AGENTS.md` changes.

## Read-only bridge health check

Use this when connection or context is doubtful:

```bash
pwd
git status --short --branch
gc status
```

Expected: the canonical path is `/home/benja/agent-factory`, Git identity is
unambiguous, and Gas City answers. Operational recovery is documented in
`OPERATIONS.md`; security boundaries are in `SECURITY.md`.

## Current decision

The native Codex local/remote path is the accepted bridge; Cockpit V2
(Planning Run C01) replaces the retired private cockpit. A custom ChatGPT plugin, MCP server, or public dashboard is
deferred until a concrete missing capability is demonstrated. Notifications may
be added as a thin product event projection; they must not become a second state
store or require polling the entire backlog.
