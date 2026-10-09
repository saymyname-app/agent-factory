# Validated Prototype (T07, af-tvda3w; spec af-wf4w5r section 3)

## Status and purpose

A **Validated Prototype** (`GLOSSARY.md`) is the frozen version of the
prototype variant Benjamin chose. It lives on its never-merged prototype
branch (`docs/PLANNING_RUN.md`, "Research and prototype tickets"); the Spec
names it by branch, commit, path and states, and that reference is frozen
with the Spec's digest. `bin/prototype-conformance` is the mechanical check
of its six properties and, given the reference, of its branch (T46,
af-lb9zkz). It runs twice: by the agent of the prototype session
before showing Benjamin the frozen version, then by `bin/spec-approve
bd-approve` on the commit the Spec names (`docs/SPEC_APPROVE.md`).

```bash
./bin/prototype-conformance check --prototype <dir> [--states empty,content] \
  [--branch prototype/<map>-<topic> --commit <sha> --remote <url or path> --protected main]
```

Exit 0 and `"ok": true` when every record holds, exit 1 otherwise. The
JSON output carries one record per property (`property`, `ok`,
`failures`). `--states` names the states a Spec lists as prototyped: each
must be a state of the prototype. Failure messages are in French
(Operator Language): `bin/spec-approve` quotes them in its refusal.

`--branch`, `--commit`, `--remote` and `--protected` (T46) are given
together -- only some of the four is an error (exit 1, JSON `error`) -- and
add a seventh record, `reference`, to the six properties (see "The
reference"). Without them the output is the six records.

The delivered screen is compared to this frozen version, state by state, by
`bin/prototype-fidelity` (`docs/PROTOTYPE_FIDELITY.md`): the anchors named
here are what it measures.

## The anchors a citation is read against (T40, af-o6tu3z)

```bash
./bin/prototype-conformance anchors --repo <project repository> --commit <sha> \
  --path <chemin> [--branch prototype/<map>-<topic>] [--states empty,content]
```

Reads the frozen version at the commit of its reference, in the repository
of the project (the commit is fetched from `origin` on `--branch` when the
repository does not hold it), and prints the named anchors of each state,
in document order: `{"ok": true, "anchors": {"empty": ["…"], …}}`.
`--states` keeps the states a Spec lists as prototyped. Exit 1 with `error`
when the prototype cannot be read. It is the one definition of « an anchor
of the Validated Prototype » for the two callers that check a citation of
kind `anchor`: the publication doors (`docs/ENTRY_CONTRACT.md`) and the
route of an Owner Finding (`docs/OWNER_ANSWER.md`).

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
| `variant` | `variant` names the one winning variant, no page keeps the variant command bar, and every page file of the directory is the page of a state | `variants` is declared; a page or an address carries `?variant=` or a `prototype-switcher` / `variant-switcher` marker; a page file (`.html`, `.htm`, `.xhtml`, anywhere under the directory) that no state of the manifest references -- a losing variant, named in the failure (T46; not judged while a state has no address: that is the `states` failure) |
| `states` | every state has a unique id and its own address, and the address opens a page inside the directory | a state has no address; two states share one; the address opens no page; a state named by `--states` is not declared |
| `encoding` | `encoding` is declared and every page is encoded in it and declares it with `<meta charset>` | no `encoding`; a page without `<meta charset>` or declaring another one |
| `viewports_themes` | `viewports` (name, positive width and height) and `themes` each declare at least one reference | either list is missing or empty |
| `anchors` | on every page, each visible element (an element holding text, or an image, form control, media or `svg` element) sits inside an element carrying `anchor_attribute` with a name; each region element that renders -- `header`, `nav`, `main`, `aside`, `footer`, `form`, `table`, `dialog` -- carries its own named anchor; no anchor holds the whole page (T46) | a visible element outside every anchor; an anchor attribute without a name; a page with no anchor; a region element without an anchor of its own; one anchor holding every visible element of a page that has at least two -- each naming the state(s) and the element |
| `datasets` | every state has its own dataset file, a JSON object whose `fixed_time_field` holds an ISO 8601 time | a state declares no dataset; the file is missing or shared; the time is absent |

One anchor around the whole page says nothing of where an element sits, so
it is refused. The exception is the own anchor of a region element: it may
span the page when every visible element it holds has a nearer anchor
(`<main data-anchor="page">` around content that all sits in finer anchors).

## The reference (T46, af-lb9zkz)

A Validated Prototype lives on its prototype branch, never merged (Spec
§3). With `--branch B --commit C --remote R --protected P`, the record
`reference` fails when:

- `B` does not start with `prototype/`;
- `C` is not found in the remote `R` (a URL or a local repository path);
- `C` is reachable from the protected branch `P` of the remote: the
  prototype branch was merged.

A protected branch the remote does not hold has merged nothing.

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
`tests/spec-approve-test.py` reports. It conforms to the T46 rules
unchanged, on the same frozen commit.

## Acceptance mapping

| Acceptance criterion | How the tool and tests check it |
| --- | --- |
| On the fixture's Validated Prototype: exit 0 and one record per property. | `test_fixture_prototype_passes_with_one_record_per_property` in `tests/prototype-conformance-test.py`. |
| False if it passes with a visible element outside every anchor, a prototyped state without address, or a missing state dataset. | `test_fails_when_a_visible_element_is_outside_every_anchor`, `test_fails_when_a_prototyped_state_has_no_address`, `test_fails_when_a_state_dataset_is_missing`, and one refusal test per other property, each on an edited copy of the fixture prototype. |
| T46: a losing variant's page, a region without its own anchor, an anchor holding the page, a reference that is no `prototype/` branch or whose commit the protected branch reaches. | `test_fails_when_the_directory_holds_a_page_the_manifest_does_not_reference`, `test_fails_when_a_region_element_has_no_anchor_of_its_own`, `test_fails_when_one_anchor_holds_every_visible_element_of_a_state`, `test_passes_when_each_region_has_its_own_anchor_even_if_main_holds_the_page`, `test_fails_when_the_branch_is_not_a_prototype_branch`, `test_fails_when_the_commit_is_reachable_from_the_protected_branch_of_the_remote`, `test_refuses_a_reference_given_in_part`, in `tests/prototype-conformance-test.py`. |
