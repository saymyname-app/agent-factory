# Add a product to the Factory cockpit

The cockpit core is product-agnostic: `lib/factory_cockpit.py` and
`ui/factory-cockpit/*` name no product. A product is **data** — one
configuration file, one release contract, one documentation folder, and the two
deterministic commands the Factory already expects. Adding a product changes no
core file. `config/products/example.json` is a complete, working reference pack;
copy it.

## 1. Declare the pack

Create `config/products/<slug>.json` (`schema_version: 4`, validated by
`config/product-cockpit.schema.json` and by `load_product_config`):

| Field | Meaning |
| --- | --- |
| `slug`, `name` | Machine identity and the human name shown everywhere in the UI. |
| `north_star` | One sentence. The cockpit's business view shows it verbatim. |
| `strategy`, `decisions`, `project_inventory`, `design_governance` | Repository-relative Markdown, inside the Factory repo. |
| `release_contract` | `config/releases/<slug>-v1.json`. Its `product` must equal `slug`. |
| `status_command`, `queue_command`, `queue_mutation_command` | Must be `bin/<slug>-product-status` and `bin/<slug>-product-queue` — the core refuses anything else. |
| `po_workspace`, `po_add_dirs`, `inventory_watch` | Where the PO session runs and what makes the inventory stale. |
| `capabilities`, `relations`, `journeys`, `business_objectives`, `view_inventory`, `delivery_workflow`, `product_reference` | The projected graphs. Every `source_refs` must name a `product_reference` id, every `decision_refs` a decision title that really exists in the decision log, and every `roadmap` an existing roadmap position. |
| `decision_blockers` | Optional map from a stable work reference to one open decision title. |
| `preview` | Optional. Omit it and the preview panel disappears instead of breaking. |

## 2. Write the documentation folder

`docs/products/<slug>/` must contain the four documents the config points at.
The core reads them by **section name**, so the strategy needs a
`Product thesis` section and a `Product roadmap` section whose numbered list is
the ordered outcome list. The decision log needs an `Accepted` section
(`### YYYY-MM-DD — Title` entries) and an `Open` section with `### Enterprise`,
`### Product` and `### Project` sub-sections holding `- **Title** — detail`
bullets. Every section named in `product_reference[].sources[].sections` must
exist and be non-empty; startup fails loudly otherwise.

## 3. Declare an optional local preview

```json
"preview": {
  "command": ["bin/<slug>-preview"],
  "browser_url": "http://127.0.0.1:5173/",
  "version_policy": "what the wrapper guarantees about versions",
  "components": [
    {"id": "frontend", "label": "Frontend", "command": "npm run dev"}
  ]
}
```

The wrapper is product-owned and must print `STATE=`, `BROWSER_URL=`, and
`<ID>_SHA=` / `<ID>_HEALTH=` lines for each declared component id. The core only
runs `bin/<slug>-preview` with `status`, `start`, `stop` or `restart`, refuses
any other executable, and refuses a preview URL that is not on loopback.

## 4. Select the product

`config/cockpit.json` names the served pack:

```json
{"schema_version": 1, "active_product": "saymyname"}
```

Per process, `FACTORY_COCKPIT_PRODUCT_CONFIG=/abs/path/to/pack.json` overrides
it — that is how a second cockpit instance serves a second product.

## 5. Prove it

```bash
python3 tests/factory-cockpit-test.py
python3 tests/factory-cockpit-blocker-test.py
python3 tests/factory-cockpit-genericity-test.py
```

`factory-cockpit-genericity-test.py` loads the `example` pack through the same
core and asserts the resulting snapshot contains no trace of the shipped
product's identity. If you ever need to add a product string to the core to make
a pack work, the pack contract is missing a field — extend the contract, not the
core.
