# Proposal — token-efficient, provider-agnostic orchestration

Status: **proposal, not yet approved**. Written by Claude (acting PO/Tech Lead)
on 2026-09-15 at Benjamin's request, after taking over Mayor piloting from a
quota-exhausted Codex. Nothing below is implemented except the items marked
`[DONE]`. Benjamin reviews this before the rest is built.

## 0. What Benjamin asked for

- Kill obvious waste now (zombie sessions, oversized reasoning effort).
- Real model choice, at the right place, for both Codex and Claude — able to
  switch pilot provider "from time to time," so both must share everything
  that matters.
- Follow actual 2026 best practice for agent-factory orchestration, not just
  intuition — researched, not guessed.
- Track cost without spending tokens to track it.
- Place GPT-5.3-Codex-Spark somewhere useful, smartly, without bloating the
  system.
- Give the Mayor a way to use durable context cheaply instead of
  re-discovering the Factory every session, and drive its per-session token
  footprint down hard while keeping quality.
- Design end-to-end autonomy toward a *release contract* (V1 for SayMyName,
  but the Factory itself must stay project-agnostic: whatever goal/scope a
  project's PO is given, the same machinery should drive it to a documented,
  validated result).
- Minimize required human decisions, but bias towards asking rather than
  guessing wrong — my judgment call on where that line sits, below.
- Do the "if I built this from zero" pass, without being anchored to what
  already exists, then decide what to actually change.

## 1. What current best practice actually says (researched 2026-09-15)

- **Orchestrator-worker / supervisor pattern is the 2026 default** for
  production multi-agent systems: one capable model plans and supervises,
  cheaper task-specific models execute the individual steps. Reported cost
  reduction from this split alone: 40–60%. ([beam.ai](https://beam.ai/agentic-insights/multi-agent-orchestration-patterns-production), [digitalapplied.com](https://www.digitalapplied.com/blog/multi-agent-orchestration-5-patterns-that-work))
  → The Factory already has this shape (Mayor = supervisor, pool
  workers/review agents = workers). The gap is that today every Codex worker
  runs at the *same* reasoning tier as the supervisor (`xhigh`), which
  defeats the pattern's whole cost argument.
- **Context compaction must be proactive, not a last resort.** Waiting until
  a session is context-full degrades reasoning quality even before the limit
  is hit; the convergent practice is to compact — summarize the work so far,
  keep a short verbatim tail, start a fresh window — at a fixed budget
  (roughly 5–20k tokens for simple workloads, 50–100k for complex ones), as a
  routine part of long-horizon execution. ([harnez.ai](https://harnez.ai/posts/prompting-agents-at-scale/), [Medium — Pankaj](https://medium.com/@pankaj_pandey/compaction-how-long-running-agents-beat-the-context-rot-problem-fc12d4cdeb7b))
  → Gas City already has the right *mechanism* for this (`gc handoff`: mail a
  structured summary to your next incarnation, then restart). The gap is
  discipline: the live Mayor session ran 31 invocations over ~32h without
  ever calling it, even though its own prompt says to.
- **Human-in-the-loop by deliberate decision boundary, not full autonomy.**
  2026 production systems keep humans on specification, policy, security, and
  genuinely high-stakes/irreversible calls (e.g. production deploys); agents
  triage and propose everywhere else and escalate only real ambiguity or high
  stakes. ([augmentcode.com](https://www.augmentcode.com/guides/autonomous-engineering-loop), [testmuai.com](https://www.testmuai.com/blog/agentic-software-factory-enterprises-need/))
  → This already matches the Factory's Enterprise/Product/Project decision
  tiers and the "Benjamin + PO" approval gate. The gap exposed this session
  was purely the *cockpit's failure to surface* a pending decision — not the
  governance model itself, which is sound.

## 2. Model/provider routing — proposed matrix

Current Anthropic list pricing (per 1M tokens, input/output, September 2026 —
cross-checked across multiple pricing trackers, treat as directional not
exact): Haiku 4.5 ≈ $1/$5, Sonnet 5 ≈ $2–3/$10–15, Opus 5 ≈ $5/$25, Fable 5.1
≈ $10/$50. ([cloudzero.com](https://www.cloudzero.com/blog/claude-pricing/), [finout.io](https://www.finout.io/blog/anthropic-api-pricing))
Cache hits bill at ~10% of input price — this matters more than raw
reasoning-tier choice for a session that re-reads the same durable docs
repeatedly, which is exactly the Mayor's usage pattern.

GPT-5.3-Codex-Spark: real, current OpenAI model. Model id for CLI/config use
is literally `gpt-5.3-codex-spark`. It is the fast sibling of GPT-5.3-Codex —
128k context, 1000+ tok/s on Cerebras hardware, text-only, ChatGPT Pro
exclusive, purpose-built for **low-latency interactive iteration**, not
necessarily for unattended deep reasoning. ([OpenAI](https://openai.com/index/introducing-gpt-5-3-codex-spark/), [Cerebras](https://www.cerebras.ai/blog/openai-codexspark), [codex.danielvaughan.com](https://codex.danielvaughan.com/2026/05/07/codex-cli-model-routing-may-2026-gpt55-gpt54-spark-decision-framework/))
Important nuance: its win is **wall-clock and iteration friction**, not
necessarily $/token — and because it rides Benjamin's existing ChatGPT Pro
allocation that isn't otherwise being spent, using it for eligible work is
close to free at the margin right now. That is the actual argument for using
it, not "it's cheap per token" (unverified).

| Role | Today | Proposed | Why |
|---|---|---|---|
| Mayor (supervisor/orchestrator) | Claude Sonnet 5, effort `high` | **Keep.** Same, but with the compaction discipline in §3. | Sonnet 5 is the right cost/judgment point for planning+dispatch; Opus 5 only if Sonnet-tier quality proves insufficient on a specific class of decision (canary before switching, per the Factory's own existing cost policy). |
| Codex pool workers — GUARDED work (schema, security, architecture, production) | `gpt-5.6-sol`, effort `xhigh` | **Keep xhigh.** | Matches the Factory's own already-stated policy; don't touch the tier where mistakes are expensive. |
| Codex pool workers — STANDARD bounded feature work | `gpt-5.6-sol`, effort `xhigh` | **Drop to `high`** (canary first on one low-risk STANDARD slice, compare quality/retries/wall-clock, per the Factory's own existing `gc.routing_recommendation` note that was never acted on). | This is the bulk of volume; xhigh here is very likely paying reasoning-tier premium for work that doesn't need it. |
| Codex pool workers — FAST tier: docs, mechanical/bounded edits, deterministic fixes, formatting, test-only maintenance | `gpt-5.6-sol`, effort `xhigh` | **`gpt-5.3-codex-spark`**, when a worker session is doing genuinely bounded mechanical work and speed matters (fewer retries, faster iteration on review feedback). | Rides the unused Pro allocation; not proven for unattended judgment-heavy work, so keep it scoped to FAST-tier per `DELIVERY.md`'s own existing FAST/STANDARD/GUARDED split — don't default every worker to it. |
| Claude review agents (`claude-reviewer`, design/risk reviewers) | Sonnet 5, effort `high` | **Keep.** | Review is a judgment task; Haiku is a false economy here until proven otherwise by canary. |
| Any high-volume, low-judgment Claude task (e.g. mechanical doc sync, deterministic checks a script *could* do but currently runs through a model) | Sonnet 5 | **Prefer moving to L0 deterministic tooling first; Haiku 4.5 only if it must stay a model call.** | Matches the Factory's own cost policy ladder (L0 > L1 > L2 > L3 > L4) — the cheapest fix for a "task doesn't need a smart model" problem is usually "it shouldn't be a model call at all." |

**Provider switching ("codex et claude doivent tout partager"):** the two
providers cannot and should not share raw conversation/session memory —
that's vendor-specific and ephemeral by design, and trying to bridge it would
itself burn tokens translating context between formats. The correct shared
layer already exists: **Beads/Dolt (executable work + state), Git/GitHub
(code + history), and the versioned docs (product/decision truth)**. Every
session, regardless of provider, is expected to derive its understanding from
that layer fresh, never from inherited chat memory (`AGENTS.md` already says
this explicitly). The one concrete gap found and fixed this session: the
Mayor's own prompt template never told it to consult the cheap
`docs/CONTEXT_INDEX.md` pointer before acting — so it was "sharing" by
re-discovery instead of by reading the actual shared substrate. `[DONE]` —
fixed directly (see §5).

## 3. Mayor session economy — proposed protocol

Today: one Mayor session lived ~32h and 31 invocations before I restarted it,
never self-handing-off despite its own prompt instructing it to. Proposal:

1. **Compact proactively, on a budget, not on discomfort.** Add an explicit
   numeric guideline to the Mayor prompt: hand off after finishing each
   bounded outcome, and don't let a single incarnation's fresh (non-cached)
   conversation exceed roughly 40–60k tokens even mid-outcome. This mirrors
   the researched 50–100k ceiling for complex agentic work, kept
   conservative because the Mayor's job is breadth (dispatch/monitor), not a
   single deep task.
2. **The handoff mail is the "sufficient context alongside."** `gc handoff
   "<subject>" "<message>"` already does exactly the researched pattern —
   summarize + fresh window — Gas City just needs the Mayor to actually use
   it on a schedule instead of only when killed externally.
3. **Bootstrap via the index, not exploration.** `[DONE]` — see §5.
4. Net effect: shorter sessions, cheaper reads dominated by cache hits (10%
   of input price) against a small, current index instead of either (a) one
   session growing without bound, or (b) every fresh session re-paying full
   Explore-agent discovery cost.

## 4. Cost visibility without spending tokens

`gc costs` is already a **deterministic local computation** over Dolt-stored
telemetry (no model calls) — it's just missing a pricing table, which is why
every row shows `EST_USD 0.0000`/"unpriced." Fix: add a static, versioned
pricing reference (e.g. `config/model_pricing.json`, hand-maintained, updated
when prices change) mapping each model id in use to its published
input/output/cache rates, and wire it into the existing cost command's
existing (zero-token) computation. This gives real cost visibility as a pure
data/config change — no new token spend, ever, by construction.

## 5. Changes already made this session `[DONE]`

- `agents/mayor/prompt.template.md`: added a "Start here" section pointing
  every Mayor incarnation at `docs/CONTEXT_INDEX.md` before any exploration,
  explicitly discouraging Explore-agent fan-out for anything the index
  already routes.
- `city.toml`: `permission_mode` for the Claude provider fixed from `"plan"`
  (which silently stranded any Claude-piloted agent waiting for an approval
  nobody was watching for) to `"unrestricted"`.
- `agents/mayor/agent.toml`: created, `provider = "claude"`, so the Mayor
  role runs on Claude while Codex's quota is exhausted.
- `docs/products/saymyname/DECISIONS.md`: corrected the provenance of the
  administered-CSV approval entry to reflect what Benjamin actually
  confirmed, rather than a self-authorizing "PO delegates to itself" framing
  a prior session had written.
- Checked for "zombie" sessions flagged by `gc costs`' large-wall-time/
  zero-invocation rows — **correction to my earlier read**: `gc session
  list`/`tmux` show these are not live processes right now (only
  `codex-1`, `core.control-dispatcher`, and `mayor` are actually running);
  those rows are historical completed runs, not current waste. Nothing to
  kill today. Worth revisiting if `gc costs` ever conflates historical and
  live rows in a way that's actually misleading operationally.

## 6. Open items needing Benjamin's decision before implementation

1. **Approve or amend the routing matrix in §2** — this changes what gets
   spent where, including moving some Codex work to Spark (rides unused Pro
   quota, but unattended-quality on Spark for pool-worker use isn't yet
   canaried).
2. **Approve the Mayor session-budget number in §3** (proposed: ~40–60k
   fresh tokens per incarnation, hand off between bounded outcomes) — or a
   different number.
3. **Codex worker effort drop (xhigh → high for STANDARD tier)** — safe to
   canary once Codex quota returns (~2026-09-21); not actionable before then
   since Codex is currently inert. No action needed from Benjamin now beyond
   confirming the plan; I'll canary it when Codex resumes rather than ask
   again.
4. **Pricing table (§4)** — I can populate and wire this now; flagging here
   only because it touches `gc costs` output Benjamin may already be reading
   in the cockpit.

## 7. What I would *not* change (kept from "if I built this from zero")

- Beads/Dolt + Git/GitHub as the durable shared truth layer, with Gas City
  observed state as the live layer — this is the correct foundation
  regardless of which LLM providers sit on top; nothing in current
  literature suggests a better substrate for this shape of problem.
- The supervisor(Mayor)/worker split and the Enterprise/Product/Project
  decision-tier gate — both match 2026 production practice as researched
  above.
- One active controller per City — still correct; the risk this exists to
  prevent (two orchestrators racing on the same state) is real and the fix
  (Gas City's own invariant) is standard practice, not something to relax
  for convenience.

## Sources

- [Beam.ai — 6 Multi-Agent Orchestration Patterns for Production (2026)](https://beam.ai/agentic-insights/multi-agent-orchestration-patterns-production)
- [DigitalApplied — Multi-Agent Orchestration: 5 Patterns That Work in 2026](https://www.digitalapplied.com/blog/multi-agent-orchestration-5-patterns-that-work)
- [harnez.ai — Prompting agents at scale: context windows, compaction, and thread management](https://harnez.ai/posts/prompting-agents-at-scale/)
- [Medium (Pankaj) — Compaction: How Long-Running Agents Beat the Context Rot Problem](https://medium.com/@pankaj_pandey/compaction-how-long-running-agents-beat-the-context-rot-problem-fc12d4cdeb7b)
- [Augment Code — From Assisted to Autonomous: How Far Can the Engineering Loop Close?](https://www.augmentcode.com/guides/autonomous-engineering-loop)
- [TestμAI — The Agentic Software Factory Enterprises Actually Need](https://www.testmuai.com/blog/agentic-software-factory-enterprises-need/)
- [OpenAI — Introducing GPT-5.3-Codex-Spark](https://openai.com/index/introducing-gpt-5-3-codex-spark/)
- [Cerebras — Introducing OpenAI GPT-5.3-Codex-Spark](https://www.cerebras.ai/blog/openai-codexspark)
- [codex.danielvaughan.com — Codex CLI Model Routing in May 2026](https://codex.danielvaughan.com/2026/05/07/codex-cli-model-routing-may-2026-gpt55-gpt54-spark-decision-framework/)
- [CloudZero — Claude pricing in 2026](https://www.cloudzero.com/blog/claude-pricing/)
- [Finout — Anthropic API Pricing in 2026](https://www.finout.io/blog/anthropic-api-pricing)
