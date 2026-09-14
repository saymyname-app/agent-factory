# Reusable product cockpit contract

The SayMyName cockpit is the first configured product, not a one-off UI. A new
Factory product adopts the same separation of concerns with one JSON
configuration under `config/products/`, validated against
`config/product-cockpit.schema.json`.

## Required product package

1. A product strategy document containing `Product thesis`, `Product roadmap`,
   and `Human decisions still required` sections.
2. An append-only decision log with an `Accepted` section.
3. A PO workspace with a concise `AGENTS.md` that defines OBSERVE, DISCUSS,
   RECORD, EXECUTE and ADMIN authority.
4. A deterministic product-status command and product-candidate queue command.
5. A capability graph whose nodes point to roadmap outcomes and whose edges
   describe conceptual dependencies.
6. A Gas City rig and Mayor-owned delivery contract. The PO never becomes a
   second dispatcher.
7. A reviewed view/feature inventory and a code-first design-governance contract
   with automatic, PO, and Benjamin + PO approval tiers.
8. Enterprise objectives and open decisions separated from Product and Project
   decisions, plus a configured delivery workflow graph.

Set `FACTORY_COCKPIT_PRODUCT_CONFIG` to the absolute path of the selected JSON
before starting a dedicated cockpit instance. Strategy and decision paths must
remain inside the Factory repository; the PO workspace may be a bridge folder.

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
- Add fixture tests for the new product memory, graph and queue projection.
- Keep automatic refresh deterministic and model-free. PO and Mayor calls occur
  only after a visible human send.
- Keep the listener on loopback. For phone access, use authenticated tailnet
  Serve on a dedicated HTTPS port; never enable Funnel implicitly.
- Version stable context in Git, live execution in Beads/Gas City, and delivery
  proof in GitHub. Conversation history is helpful evidence, not authority.
