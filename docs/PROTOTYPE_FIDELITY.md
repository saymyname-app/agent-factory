# Mechanical fidelity to the Validated Prototype (T16, Spec af-wf4w5r §3, §7, §9)

## Status and purpose

`bin/prototype-fidelity` compares a delivered screen to its **Validated
Prototype** (`docs/VALIDATED_PROTOTYPE.md`), state by state, by code. It is
the blocking half of the fidelity proof Benjamin chose (Spec §3,
« combinaison B »): tokens on the sources, structure and computed styles on
every anchor. It also joins, without ever blocking on them, side-by-side
captures and an image of the difference, both sides rendered at the moment
of the comparison: no capture made earlier is ever compared.

```bash
# every prototyped state of every screen of the profile (the end of a Spec)
./bin/prototype-fidelity check <descriptor.json> --prototype <dir> --commit <sha> [--repo-root <product repo>] [--states empty,content]

# one ticket of a new-flow convoy: its screen only, the result written on the ticket
./bin/prototype-fidelity check <descriptor.json> --prototype <dir> --commit <sha> \
    --convoy af-convoy --ticket af-t1 [--screen accueil]
```

`--prototype` is the directory of the frozen prototype, the one
`bin/prototype-conformance` checks. `--states` names the states the Spec
lists as « prototypé » (default: every state of the prototype).

Every answer is one JSON object on stdout.

| Exit | Meaning |
|---|---|
| 0 | green (`"result": "vert"`), or every deviation accepted by Benjamin (`"accepté par Benjamin"`) |
| 1 | red (`"result": "rouge"`): at least one open deviation, each named |
| 2 | refused (`{"ok": false, "error": "refus : …"}`): something could not be compared; nothing is written on the ticket. `written` lists the pieces already filed when a later step refused |
| 4 | the convoy does not carry the mark: « pas un convoi du nouveau flux »; nothing is run or written |

## What is compared

For each prototyped state, the product is launched by `bin/project-launch`
from a clean copy of `--commit`, on the dataset that carries the name of the
state, and the page of its screen is read **at its real address** (the path
the profile declares). The page of the prototype is served from the frozen
directory by a throwaway server on this host. The states are compared one
after the other: the product of a state is stopped before that of the next
is launched, so a single copy of the product runs at a time (af-6xjghg).

| Control | Read on | A deviation is |
|---|---|---|
| Tokens (`kind: token`) | the sources of the page, without a browser: its `<style>` blocks and the style sheets it links from its own address. A token is a custom property declared on `:root`, `html` or a `[data-theme…]` selector; one declared for the dark theme (`… (dark)`) is another token | a token of the prototype the delivered page lacks or gives another value |
| Presence (`kind: absent`) | every element carrying the prototype's `anchor_attribute`, in a headless Chromium | an anchor of the prototype absent from the delivered page |
| Structure (`kind: structure`) | the same | another element (`tag`), another enclosing anchor (`parent`), another number of `occurrences` |
| Computed styles (`kind: style`) | `getComputedStyle` on each anchor | another computed value of `font-family`, `font-size`, `font-weight`, `line-height`, `color`, `background-color`, `border-radius`, `padding`, `display`, `box-shadow` |

The browser controls run at every reference viewport of the prototype's
manifest and in every reference theme (`light`, `dark`: the preferred colour
scheme of the browser). A rendering is named by its viewport (`desktop`), and
`desktop@dark` for the dark theme.

The answer carries, per state, one record per anchor and per rendering
(`records`: `anchor`, `viewport`, `verdict` — `identique`, `écart`,
`absente` — and its `deviations`), the tokens compared (`tokens`), and
`deviations`, the flat list: `state`, `viewport`, `anchor`, `kind`,
`property`, the two values, and `status`. An anchor only the delivered page
has is a note (`anchors_only_delivered`), like a token only it declares:
nothing of the prototype is missing there.

**Never green on what was not compared.** The command refuses (exit 2) when:
a state named by `--states` is not a state of the prototype; a prototyped
state is served by no screen of the profile; the profile declares no screen;
the prototype declares a theme the browser cannot render; the product does
not start on the dataset of a state; a page does not answer; the browser
returns no measure; or the prototype shows no anchor in a state.

**Never the prototype promoted as is (T46, af-lb9zkz).** Before a state is
compared, the command refuses (exit 2, nothing written or filed) a delivered
page of a compared state, or a file that page links from its own address
(`href` of a `<link>`, `src` of any element, same origin), whose sha256 is
that of a file of the prototype directory: « prototype promu tel quel »,
naming the served path, the state and the prototype file. The manifest
`validated-prototype.json` and the datasets it names are not counted: the
product is launched on the same example data.

## Screens

The profile declares the screens (`launch.screens`,
`docs/PROJECT_PLANNING_PROFILE.md`): a name, the path the product serves it
at, and its prototyped states. With a ticket named, only the screens it
touches are compared: `--screen` (repeatable), required when the profile
declares several. Without a ticket every screen is compared, which is what
the end of a Spec asks.

## A named ticket: captures and record

With `--convoy` and `--ticket`, on a convoy that carries the new-flow mark:

1. the measure is run by `bin/evidence-capture command`, so its record is a
   sealed piece of the evidence store (`fidelity`) at the commit of the
   launched product (`docs/EVIDENCE_STORE.md`). The full measure runs to
   megabytes on a real screen, beyond what the store keeps of an output
   (1 MB): it is written to a file of the work directory, and the piece seals
   its path, size and SHA-256 (af-2cpwkh). The command reads that file back
   only when it matches the sealed fingerprint, and refuses a record the
   store truncated, or a file that differs from it;
2. one comparison piece per state and rendering is filed by
   `bin/evidence-capture comparison` (`fidelity.<state>.<viewport>`): the two
   pages side by side, the prototype on the left, and the image of their
   difference. The number of differing pixels is recorded; **no threshold
   exists**, and it changes neither the result nor the exit code;
3. the result is written on the ticket by `bin/convoy-state set-fidelity`
   (`docs/CONVOY_STATE.md`): the commit, the screens, per state the
   viewports and anchors compared, every deviation — past 100, the first
   100, their count and the anchors of all (af-m0hvif) —, and the verdict
   `gc.flow.verdict.fidelity` at that commit, in one tracker write. Like any
   verdict it stops being valid when a commit is added to the branch.

## A deviation is never lifted by its author

The command has no option that accepts, waives or ignores a deviation. A
deviation declared in the Ticket Handoff stays red. It reads « accepté par
Benjamin » only through a resolved Planning Exception that names its anchor
(Spec §3, §9):

1. the author exits by `bin/ticket-exit exit … --exit planning_exception
   --anchor <name>` (`docs/TICKET_EXIT.md`), with a Ticket Handoff whose
   « Écarts » mentions that anchor (refused otherwise): the request that reaches the
   operator offers, beside the two usual options, « Accepter l'écart sur
   l'ancre <name> », and the Planning Exception is written on the ticket
   with its anchors and the letter of that option;
2. the operator answers through `bin/escalation-door repondre <ticket>
   <lettre>`;
3. `bin/convoy-state show` then renders the anchors as `accepted_anchors`,
   the deviations on them as `"status": "accepté par Benjamin"`, and
   `fidelity.state` as `accepté par Benjamin` once every deviation is.
   Another answer, an answer given before the exception was raised, or an
   exception that names another anchor, leaves it `rouge`.

The stored verdict stays `unfavorable`: the deviation is still one, and it
is the computed `fidelity.state` a gate reads. A token deviation has no
anchor: it is repaired, never accepted.

## Limits

- The ticket → screen link is not recorded at publication: the caller names
  the screen (`--screen`). For a ticket, the caller is `bin/ticket-end
  fidelity`, run by `bin/convoy-advance` before the merge: it extracts the
  Validated Prototype the ticket names and compares every screen of the
  profile that serves one of its states (`docs/TICKET_END.md`). At the end
  of a Spec the caller is `bin/spec-end run` (T23, `docs/SPEC_END.md`): no
  ticket and no `--screen`, every screen of the profile on the states each
  Validated Prototype of the convoy lists, at the tip of the integration
  branch; nothing is filed in the evidence store there.
- A state is launched on the dataset of the same name; the profile has no
  other mapping.
- Text content is not compared: both sides render the same synthetic
  dataset, and a difference shows in the captures.
- A product that forbids being framed (`X-Frame-Options`, `frame-ancestors`)
  cannot be measured this way: the measure fails and the command refuses.
- A theme switched by an attribute instead of the preferred colour scheme is
  not rendered as dark by the browser.
- The answer of the operator is read from what `bin/escalation-door` wrote
  on the ticket. The door is the operator's; a process that calls it in his
  name is not detected here.
- The images are decoded and drawn in pure Python, which is slow: the
  local-only demonstration (six checks, 24 comparisons at 1280x800 and
  390x844, the isolated city included) took 4 min 10 s on 2026-10-07.

## Proof

`tests/prototype-fidelity-test.py` drives the command line on a fake tracker
state, a copy of the Delivery Fixture City launched by the real
`bin/project-launch`, and a fake browser that fetches the pages it is given
(`tests/fixtures/prototype-fidelity/browser`): one test per pass, per red
and per refusal, each refusal re-reading the tracker and the evidence store.
The Planning Exception goes through the real `bin/ticket-exit` and
`bin/escalation-door`. `tests/convoy-state-test.py`,
`tests/evidence-capture-test.py`, `tests/ticket-exit-test.py` and
`tests/project-planning-profile-test.py` cover what each of those tools
gained. `tests/prototype-fidelity-demonstration-test.sh` (local-only)
replays the demonstration line on the real `gc`/`bd` in a disposable city
with the real Chromium.

## Acceptance mapping

| Acceptance criterion | Tests |
|---|---|
| Conforming fixture: exit 0 and one record per anchor and prototyped state | `test_conforming_fixture_is_green_with_one_record_per_anchor_and_prototyped_state`, `test_both_sides_are_rendered_at_comparison_time_for_every_state_and_viewport` |
| Anchor absent, token changed, computed style different: non-zero exit, anchor, state and property named; never green on a state it did not compare | `test_anchor_absent_from_the_delivered_page_is_red_and_names_anchor_and_state`, `test_changed_token_is_red_and_names_token_and_state`, `test_computed_style_differing_on_an_anchor_is_red_and_names_anchor_state_and_property`, `test_structure_differing_on_an_anchor_is_red_and_named`, `test_never_green_on_a_state_it_did_not_compare` |
| Side-by-side captures and a difference image per state, Evidence Records of the capture tool; no pixel threshold | `test_named_ticket_files_side_by_side_and_difference_captures_per_state`, `test_no_pixel_threshold_fails_the_command` |
| A named ticket: only the anchors of its screen; the result on the ticket by the state command, tied to the commit | `test_named_ticket_compares_only_the_anchors_of_the_screen_it_touches`, `test_named_ticket_records_the_result_on_the_ticket_tied_to_the_commit`, `test_red_result_is_recorded_on_the_ticket_with_the_anchor_state_and_property` |
| A deviation declared in the Handoff stays red; a resolved Planning Exception that names the anchor turns it « accepté par Benjamin »; no author command lifts the red | `test_deviation_declared_in_the_handoff_stays_red`, `test_resolved_planning_exception_naming_the_anchor_turns_it_accepted_by_benjamin`, `test_planning_exception_answered_otherwise_or_naming_another_anchor_leaves_it_red`, `test_no_option_of_the_command_lifts_a_red` |
| T46: a delivered file with the digest of a prototype file is refused and named, before anything is filed | `test_delivered_file_with_the_digest_of_a_prototype_file_is_refused_and_named`, `test_named_ticket_serving_a_prototype_file_as_is_is_refused_before_anything_is_filed` |
