# Codex operator bridge

This is the human contract for using Codex as the product-facing control surface
for Agent Factory. It covers desktop Codex, CLI Codex, and remote/mobile Codex.

## Product promise

Benjamin can enter through Codex, speak about a product rather than Factory
machinery, and receive a concise authoritative answer or route bounded work to
the Mayor. GitHub does not need to be open on the phone: Codex uses the host's
local repository, shell, authenticated tools, and approval flow.

This bridge does not create a second orchestrator or execution system. A small
ordered product-candidate view may store deferred ideas in Beads, but Gas City
and the Mayor alone coordinate executable work and dependencies, and GitHub
proves code delivery.

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

### SayMyName PO cockpit

For normal SayMyName product work, open the local Codex project whose primary
folder is `C:\Dev\Projects\SayMyName`. This is the single PO cockpit: it exposes
the Backend and Frontend Windows repositories, local MySQL/Flyway helpers, and
the Factory through explicit WSL commands. Its canonical instructions and
configuration live in `docs/products/saymyname/` and are synchronized into the
Windows workspace.

The Factory project remains the direct engineering/operations entrance. The PO
cockpit is the default human entrance when Benjamin wants to discuss the product,
record a decision, choose a priority, or have the Mayor route delivery.

### Factory workspace and human cockpit

For Factory engineering, use the local Codex project rooted at
`C:\Dev\Projects\AgentFactory`. It is a small Windows bridge to the canonical WSL
repository, not a clone. Its commands enter
`/home/benja/agent-factory` explicitly.

Open the human decision cockpit with:

```bash
./bin/factory-cockpit open
```

The browser opens `http://127.0.0.1:8383`. It shows understandable Mayor and
agent objectives, evidence-based phase/step progress, elapsed time, signal age,
filtered product Beads, future candidates, the last delivery, deterministic
decision aids, and any Benjamin decision. Automatic monitoring performs zero
model calls. Search, pause, copy-summary, tooltips and the integrated glossary
remain local.

Benjamin may also type an explicit question or non-interrupting follow-up to the
persistent Mayor. Sending may consume model tokens and is visibly labelled as
such. It does not create a second orchestrator: the cockpit cannot interrupt,
dispatch, retry, merge, or recover work. Use the upstream Gas City dashboard at
port `8372` only when detailed sessions, runs, events, or full transcripts are
actually needed.

The **Mon PO** view embeds a persistent, authenticated local Codex conversation
with the same SayMyName PO contract as the dedicated workspace. A decision card
can prefill that conversation, Benjamin can DISCUSS without mutation or RECORD
an approved answer, and the Codex thread identifier remains visible for opening
or resuming the underlying discussion. Full host access is available to inspect
the product and Factory, but it does not widen authority: only an explicit
EXECUTE request may be handed to the Mayor.

The cockpit keeps governance domains explicit: Enterprise covers customers,
testers, channel, buyer and pricing; Product covers user value and behavior;
Project covers views, design and delivery choices. The design loop is code-first
and risk-tiered; Figma is an optional exploration/handoff tool, never a second
product or implementation truth store.

For private phone access, run once from Ubuntu:

```bash
./bin/factory-cockpit phone-enable
./bin/factory-cockpit phone-status
```

Open the reported HTTPS address on a phone connected to Benjamin's Tailscale
tailnet. The cockpit stays bound to loopback; Tailscale Serve terminates HTTPS
and does not expose it publicly. Automatic views still make zero model calls.

### Speak in intent, not commands

Examples:

- `Où en est SayMyName ?`
- `Montre-moi seulement le résumé produit.`
- `Explique les détails de l'usine, sans rien modifier.`
- `Discutons de cette idée; ne l'enregistre pas encore.`
- `Enregistre cette décision et propose la prochaine priorité.`
- `Ajoute cette idée à la file sans la lancer.`
- `Mets cette idée en premier; ne touche pas au travail en cours.`
- `Montre-moi seulement la file produit.`
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

## Product-first status contract

For a normal `Où en est SayMyName ?`, Codex runs:

```bash
./bin/saymyname-product-status
```

It returns, in plain language:

1. **Current:** the product outcome being built, or idle.
2. **Last delivered:** the last merged outcome and its evidence.
3. **Next:** the approved next product outcome, if any.
4. **Needs Benjamin:** only a real decision or intervention.
5. **Risk:** only when a verified inconsistency or blocker exists.

Raw issues, agents, sessions, Formula steps, logs, and infrastructure details
stay hidden unless requested or needed to explain a verified risk. If an
authoritative source disagrees, Codex fails closed and names the source to fix
instead of inventing a clean summary.

## Product candidate queue

For future SayMyName outcomes, Codex uses:

```bash
./bin/saymyname-product-queue list
```

The list is a separate, low-token view from current delivery status. Under
RECORD authority the PO may add, reorder, mark urgency, pause, resume, or cancel
deferred candidates. These candidates never become worker-ready. Under EXECUTE
authority, the PO hands the selected outcome once to the Mayor; the Mayor alone
creates and links executable work. Exact commands and state semantics are in
`PRODUCT_QUEUE.md`.

## How Codex resolves context

1. Root `AGENTS.md` defines Factory-wide behavior and points here.
2. `docs/CONTEXT_INDEX.md` selects the minimum durable contract.
3. The target project's nearest `AGENTS.md` and repository docs define its stack, tests, and local safety rules.
4. The relevant Bead defines the current outcome, dependency, scope, and evidence contract.
5. Live Gas City, Git, GitHub, and runtime observations establish what is true now.

This order lets the bridge adapt to SayMyName or a future rig without copying
the full Factory history into every prompt. A new project is ready only when it
has a registered rig, a concise project `AGENTS.md`, authoritative build/test
commands, and a product-status projection or explicit fallback. Its cockpit
adapter is a validated `config/products/<slug>.json`; the reproducible onboarding
checklist is in `PRODUCT_COCKPIT_TEMPLATE.md`.

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
./bin/saymyname-product-status
```

Expected: the canonical path is `/home/benja/agent-factory`, Git identity is
unambiguous, Gas City answers, and product status either prints a complete
snapshot or a precise recovery error. Operational recovery is documented in
`OPERATIONS.md`; security boundaries are in `SECURITY.md`.

## Current decision

The native Codex local/remote path plus the private product cockpit is the
accepted bridge. A custom ChatGPT plugin, MCP server, or public dashboard is
deferred until a concrete missing capability is demonstrated. Notifications may
be added as a thin product event projection; they must not become a second state
store or require polling the entire backlog.
