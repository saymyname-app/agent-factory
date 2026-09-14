# ADR-0007: Human decision center and explicit Mayor channel

- Status: Accepted
- Date: 2026-09-14

## Context

The token-free cockpit from ADR-0006 made live activity understandable, but the
operator still had to interpret several sources, open a separate terminal to ask
the Mayor a question, and know which Beads represented product work rather than
Factory machinery.

## Decision

Extend the loopback cockpit into a small human decision center. Its refresh path
remains deterministic and read-only: it projects product-marked Beads from the
City and registered rigs, removes sessions, workflows, convoys, gates, synthetic
work and maintenance, and derives explainable advice from explicit local rules.
It also provides search, status filters, source explanations, glossary/tooltips,
freshness, pause/manual refresh, and a copyable human summary.

Add one deliberately narrow write route for messages typed by Benjamin to the
persistent Mayor session. It calls `gc session submit mayor` with normal or
follow-up intent only. It never exposes interrupt, dispatch, retry, merge, or
recovery controls. The route is loopback/same-origin, requires a cockpit header,
accepts bounded JSON text, rate-limits sends, and labels every message as coming
from the cockpit. The UI warns before use that a Mayor message may consume model
tokens. It shows only recent cockpit-origin exchanges, never the whole transcript
or system prompts.

## Consequences

- Reading and refreshing the cockpit still performs zero model calls.
- Sending a Mayor message is an explicit operator action and may consume tokens.
- The Mayor remains the sole product-work orchestrator; advice buttons only fill
  the message box and never act automatically.
- Beads is the truth for work, Gas City for execution, and GitHub for delivery.
- Port `8383` remains loopback-only; remote publication is still out of scope.
- ADR-0006 remains valid for the monitoring path; its statement that the entire
  cockpit has no write route is superseded only by this bounded Mayor channel.
