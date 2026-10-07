# Validated Prototype (T07, af-tvda3w; spec af-wf4w5r section 3)

## Status and purpose

A **Validated Prototype** (`GLOSSARY.md`) is the frozen version of the
prototype variant Benjamin chose. It lives on its never-merged prototype
branch (`docs/PLANNING_RUN.md`, "Research and prototype tickets"); the Spec
names it by branch, commit, path and states, and that reference is frozen
with the Spec's digest. `bin/prototype-conformance` is the mechanical check
of its six properties. It runs twice: by the agent of the prototype session
before showing Benjamin the frozen version, then by `bin/spec-approve
bd-approve` on the commit the Spec names (`docs/SPEC_APPROVE.md`).

```bash
./bin/prototype-conformance check --prototype <dir> [--states empty,content]
```

Exit 0 and `"ok": true` when the six properties hold, exit 1 otherwise. The
JSON output carries one record per property (`property`, `ok`,
`failures`). `--states` names the states a Spec lists as prototyped: each
must be a state of the prototype. Failure messages are in French
(Operator Language): `bin/spec-approve` quotes them in its refusal.

The delivered screen is compared to this frozen version, state by state, by
`bin/prototype-fidelity` (`docs/PROTOTYPE_FIDELITY.md`): the anchors named
here are what it measures.

## The frozen version

A directory holding static pages, datasets and one manifest,
`validated-prototype.json`:

```json
{
  "contract": "agent-factory-validated-prototype/v1",
  "variant": "A",
  "encoding": "utf-8",
  "anchor_attribute": "data-anchor",
  "fixed_time_field": "generated_at",
  "viewports": [{"name": "desktop", "width": 1280, "height": 800}],
  "themes": ["light"],
  "states": [
    {"id": "empty", "address": "states/empty.html", "dataset": "data/empty.json"}
  ]
}
```

Pages are static HTML: the check reads the page source, it does not run
scripts, so a state rendered by a script is not seen.

## The six properties

| Property | Holds when | Fails when (examples) |
| --- | --- | --- |
| `variant` | `variant` names the one winning variant and no page keeps the variant command bar | `variants` is declared; a page or an address carries `?variant=` or a `prototype-switcher` / `variant-switcher` marker |
| `states` | every state has a unique id and its own address, and the address opens a page inside the directory | a state has no address; two states share one; the address opens no page; a state named by `--states` is not declared |
| `encoding` | `encoding` is declared and every page is encoded in it and declares it with `<meta charset>` | no `encoding`; a page without `<meta charset>` or declaring another one |
| `viewports_themes` | `viewports` (name, positive width and height) and `themes` each declare at least one reference | either list is missing or empty |
| `anchors` | on every page, each visible element (an element holding text, or an image, form control, media or `svg` element) sits inside an element carrying `anchor_attribute` with a name | a visible element outside every anchor; an anchor attribute without a name; a page with no anchor |
| `datasets` | every state has its own dataset file, a JSON object whose `fixed_time_field` holds an ISO 8601 time | a state declares no dataset; the file is missing or shared; the time is absent |

## Fixture

The Delivery Fixture City carries a Validated Prototype at
`tests/fixtures/delivery-fixture-city/prototype/` (states `empty` and
`content`, the same anchors as the product's `/` page). CI has no prototype
branch to read, so `tests/lib/fixture_prototype.py` materialises that
directory as one orphan commit on `prototype/delivery-fixture-city` in a
bare repository a test uses as the remote. Identity and dates are fixed, so
the commit is always `FROZEN_COMMIT`, the one the fixture Spec
(`tests/fixtures/delivery-fixture-city/spec.md`) names: editing the frozen
files changes the commit and the fixture Spec no longer matches, which
`tests/spec-approve-test.py` reports.

## Acceptance mapping

| Acceptance criterion | How the tool and tests check it |
| --- | --- |
| On the fixture's Validated Prototype: exit 0 and one record per property. | `test_fixture_prototype_passes_with_one_record_per_property` in `tests/prototype-conformance-test.py`. |
| False if it passes with a visible element outside every anchor, a prototyped state without address, or a missing state dataset. | `test_fails_when_a_visible_element_is_outside_every_anchor`, `test_fails_when_a_prototyped_state_has_no_address`, `test_fails_when_a_state_dataset_is_missing`, and one refusal test per other property, each on an edited copy of the fixture prototype. |
