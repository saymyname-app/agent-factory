# Design skills vendored by the Factory

The approved Spec **af-t5cgg7** pins three upstream repositories in
[`design-skills.json`](../design-skills.json). That manifest is the single
source of their exact commits, selected skill paths and licence paths.
`design-skills/` holds only those selected skills. The prototype-only
`variant` is available to an operator; delivery formulas never call it.

`bin/design-skills-check compare` fetches each pinned upstream commit and
compares every selected file, each licence, and the pinned impeccable tag.
It refuses missing, extra or changed files. CI runs the same comparison on
each PR. Updates are deliberate and reviewed at the end of the first
delivered interface Spec; they never follow upstream automatically.

The impeccable copy contains Markdown only. Its `scripts/` subtree, hooks
and binary are absent. Its SKILL.md has the exact extra note in
[`ENGINE_ABSENT_NOTE.md`](design-skills/ENGINE_ABSENT_NOTE.md) immediately
after the frontmatter. The note is the sole allowed modification to that
file, verified by the comparator. No engine is installed or run as part of
this delivery.

The role distribution uses the copies from this folder. A formula calls a
design skill only for an interface ticket, and each role receives only its
assigned skills. `interface-review` depends on `better-interface`, which
depends on six `better-*` domain skills; those copies are included at the
same Krehel pin. `variant` is reserved to operator prototype sessions.

An opinion from any of these skills is evidence. A delivery refusal needs
a verified citation to the project's written standard or approved Spec,
under `docs/CODE_REVIEW.md`. The first delivered interface Spec tests their
actual usefulness from recorded findings; no separate measurement tool is
introduced.

## Delivery role routing

The role manifest uses `design:<name>` for a copy from `design-skills/`;
ordinary paths still resolve from Matt’s `skills/`. Author receives the
text of impeccable, better-writing and apple-design. Reviewer receives
interface-review, review-animations, and the six better-interface
dependencies. Evaluator receives better-accessibility, better-interface,
and those six dependencies. `variant` is reserved for the operator.

The author and reviewer briefs expose `interface`; the Evaluator uses its
existing `screen_checks`. Formulas invoke design skills only for interface
tickets, and animation skills only where the approved ticket has animation.
The role adoption trial must pass again after the distribution changes.

The pinned sources of `interface-review` and `review-animations` each set
`disable-model-invocation: true`. Only the reviewer's role copies change that
single frontmatter value to `false`, so its formula can invoke them. The
distribution check compares every byte of the role copy against the pinned
source with exactly that declared substitution. No other source changes.
