# SayMyName — durable objective

**Status: SET** by Benjamin on 2026-09-16, in conversation.

This file is the first entry of the decision basis in `DESIGN_GOVERNANCE.md`.
It states what SayMyName must become, above and outliving any single version.

**Written by Benjamin alone.** No agent, no PO, no Mayor may write, reword,
summarise or extend the statement below. A decision that would contradict it is
not a decision: it is an escalation. This is the ceiling that bounds `L3`
autonomy — the factory owns the route, Benjamin owns the destination.

## Statement

> SayMyName doit faire qu'au moment où la personne est en face, son nom vienne
> tout seul : sans écran, parmi les gens qu'on a choisi de retenir, et sans que
> l'effort pour y arriver se voie.

Benjamin's words, verbatim, 2026-09-16.

## What each clause settles

PO text, not part of the statement. It records how the clauses are applied, so
that agents do not have to re-derive the reading every time.

| clause | what it settles on its own |
| --- | --- |
| **au moment où la personne est en face** | The value moment is outside the app, so recall in the real situation is what *proves* the product. Engagement is not off-target — spaced practice does not work without return, and neither does the business — but it is **instrumental**: steer on return, validate on recall. Any release criterion that measures return must be paired with one that measures recall, so the product cannot pass on the metric while failing the objective. See `Engagement and return` below. |
| **son nom vienne tout seul** | Fluency is the outcome, not availability. A correct answer retrieved slowly, or after a hint, is a partial result, not a pass. |
| **sans écran** | Consulting the phone during the interaction is a product failure, not a fallback feature. In-app lookup may exist for preparation and review; it may never be the primary path at the moment of the encounter, and nothing may push a notification into that moment. |
| **parmi les gens qu'on a choisi de retenir** | No automatic selection, no imposed memorisation. The learner chooses who and what. This is also what keeps SayMyName from drifting into a contact manager or a CRM. |
| **sans que l'effort pour y arriver se voie** | Selections, mistakes, progress and practice are private to the learner — including from an organization administrator. It says nothing about whether a *person* is visible inside an organization or a group: that is a separate, explicitly granted exposure with its own recorded decisions. |

The last clause replaced an earlier wording ("sans jamais exposer ces personnes
à quelqu'un d'autre") which, read literally, contradicted behaviour already
decided and shipped — organizations publish approved fields to workspace
members, participative groups let admitted members see one another, a
trombinoscope is a shared view by design. The privacy promise belongs to the
learner's effort, not to the people: knowing someone's name was never the
sensitive part; having had to train for it is.

## Engagement and return

PO text, recorded 2026-09-16 after Benjamin raised the Duolingo comparison.

Return is a legitimate and necessary success criterion. Spaced retrieval
practice requires the learner to come back, and a consumer product with no
retention has no business. `PRODUCT_STRATEGY.md` already carries this as a
business objective: a cohort that "s'active, revient et rapporte une utilité".

The distinction that matters for SayMyName, and the reason engagement cannot be
the *only* criterion:

- For a product whose practice happens in the app, engagement and value
  coincide — time in the app *is* the product being used. That is Duolingo's
  situation, and also the textbook case of a metric detaching from its value:
  a streak can be maintained without learning anything.
- SayMyName's value moment is **outside** the app, in front of a person. Time
  in the app is preparation, not the outcome. So return is a leading indicator
  worth optimising, and recall at the encounter is the lagging one that decides
  whether the optimisation meant anything.

Practical rule for release criteria: **steer on return, validate on recall.**
Every criterion that measures return is paired with one that measures recall —
correct retrieval after a delay, without a hint, and where it can be collected,
the learner's own report that they said the name right. A version may not be
declared reached on return alone.

What this forbids is narrow and specific: mechanisms that raise return while
detaching it from recall — streak anxiety, notification pressure, rewards for
opening rather than for retrieving. Those are the things "sans écran" is
pointed at. It does not forbid making the product one people want to come back
to; wanting to come back is how the practice happens at all.

## Non-goals

Carried from `PRODUCT_STRATEGY.md#evidence-and-claim-boundaries` and binding
today, objective or not. SayMyName must not claim, and must not be steered
toward claiming, that it improves general intelligence, prevents cognitive
decline, treats social anxiety, or makes someone socially skilled. It must not
retain everything, and it must not become a reason to consult the phone during
a real interaction.

## How this is used

- It is read before `DECISIONS.md`, `PRODUCT_STRATEGY.md`, and the release
  contract's criteria, and it wins on conflict.
- Once ADR-0015 is implemented, this statement moves into the release
  contract's `objective.statement` field, which carries the same human-only
  rule. This file is the interim home, not a second source of truth: when the
  field exists, this file points at it and stops holding the text.
- Changing it is Benjamin's act alone, and it re-derives the work that rested
  on the previous wording rather than silently reinterpreting it.
