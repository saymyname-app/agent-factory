# Reusable product cockpit contract

The SayMyName cockpit is the first configured product, not a one-off UI. A new
Factory product adopts the same separation of concerns with one JSON
configuration under `config/products/`, validated against
`config/product-cockpit.schema.json`.

**Step-by-step instructions: `docs/ADD_A_PRODUCT.md`.** A complete working
reference pack ships as `config/products/example.json` plus
`docs/products/example/`; `tests/factory-cockpit-genericity-test.py` proves the
core carries no product identity of its own.

## Required product package

1. A product strategy document containing `Product thesis`, `Product roadmap`,
   and `Human decisions still required` sections.
2. An append-only decision log with an `Accepted` section.
3. A PO workspace with a concise `AGENTS.md` that defines OBSERVE, DISCUSS,
   RECORD, EXECUTE and ADMIN authority.
4. A deterministic product-status command and product-candidate queue command.
5. Capability and journey graphs whose nodes point to roadmap outcomes,
   configured source sections and related decisions. Reverse links must be
   projected beside each decision and validated before display.
6. A Gas City rig and Mayor-owned delivery contract. The PO never becomes a
   second dispatcher.
7. A reviewed view/feature inventory and a code-first design-governance contract
   with automatic, PO, and Benjamin + PO approval tiers.
8. Enterprise objectives and open decisions separated from Product and Project
   decisions, plus a configured delivery workflow graph.
9. One on-demand persistent PO thread per decision, independently reopenable,
   with local token telemetry and a copyable Codex thread identifier.
10. A product-only interactive reference view and guarded dev preview controls;
    Factory internals stay in a secondary `More / Factory` area.
11. A first-class roadmap that combines Git-versioned outcomes with delivered
    evidence, immutable active work, the authoritative candidate queue, decision
    gates, and separately identified non-product Factory campaigns.
12. Optional `decision_blockers` mappings from stable work references to durable
    open-decision titles when coordination text should open one exact decision.

`config/cockpit.json` names the served pack (`{"active_product": "<slug>"}`).
Set `FACTORY_COCKPIT_PRODUCT_CONFIG` to the absolute path of another pack to
override that selection for one cockpit instance. Strategy and decision paths
must remain inside the Factory repository; the PO workspace may be a bridge
folder.

Schema version 4 adds a required `north_star` sentence and an optional
`preview` block (`bin/<slug>-preview`, loopback URL, declared components); a
product without that block simply has no preview panel. It requires every
product-reference entry to declare one or more
repository-relative Markdown `sources`, each with exact `sections`. A reference
ID is the reusable link target for capability, journey, roadmap and decision
projections. Startup rejects path traversal, absolute source paths, dangling
graph IDs and unresolved decision or roadmap links. A missing, empty or invalid
source is shown as a source error; the cockpit never substitutes filename or
configuration summary text for the document body.

Each `decision_blockers` entry contains one `work_ref` and one `decision_ref`.
Today treats `gc.needs_benjamin` as an effective blocker when present, but only
attaches a decision target when the coordination text names a configured work
reference and exactly one currently open durable decision has the configured
title. Missing, closed, or ambiguous targets stay visible as unlinked blocker
text; the cockpit never guesses from prose.

Reference Markdown is parsed into inert headings, paragraphs, lists, tables and
code blocks. The browser builds DOM nodes with `textContent`; it does not inject
source HTML. Active HTML, unsafe schemes, external file access and links outside
the configured source allowlist are rejected. Stable section anchors, a table of
contents, search, configured paths, modification timestamps and content hashes
provide navigation and freshness provenance without model calls.

`queue_command` remains the read projection. `queue_mutation_command` points to
the existing bounded product-queue wrapper and is never a shell template. The
HTTP bridge accepts only `add`, `move`, `urgency`, `pause`, `resume` and confirmed
`cancel`, maps typed fields to an argument vector, then rereads the queue and
invalidates the snapshot cache. It cannot call `materialize`, dispatch, interrupt,
merge or arbitrary commands. Tests must use isolated Beads fixtures or command
stubs and must never reorder the live queue.

## Context hierarchy

```text
Benjamin -> PO -> strategy / decisions / roadmap
                    |
                    v explicit EXECUTE handoff only
                  Mayor -> Beads / workflows -> agents -> GitHub evidence
```

The PO session has the host capabilities configured for its workspace. This is
not standing authority: discussion is read-only, recording is limited to an
explicit human decision, and delivery is handed to the Mayor only after an
explicit EXECUTE request.

## Reuse checklist

- Copy and adapt the product JSON; never add product-specific conditionals to
  the generic HTTP or UI layer when configuration can express the difference.
- Add fixture tests for the new product memory, reference parser, graph and queue
  projection, including traversal, active content, lock/conflict and forbidden
  execution paths.
- Keep automatic refresh deterministic and model-free. PO and Mayor calls occur
  only after a visible human send.
- Keep Today, Product, Roadmap, Decisions, PO and Board in that priority order.
  Enterprise decisions stay directly reachable but secondary and collapsed;
  ignore/snooze is a reversible browser preference and never a durable decision
  mutation.
- Keep the listener on loopback. For phone access, use authenticated tailnet
  Serve on a dedicated HTTPS port; never enable Funnel implicitly.
- Version stable context in Git, live execution in Beads/Gas City, and delivery
  proof in GitHub. Conversation history is helpful evidence, not authority.
