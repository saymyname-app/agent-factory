# Product candidate queue

The product queue is the small, ordered inbox between Benjamin's PO conversation
and the Mayor. It remembers useful outcomes that are not ready to execute yet,
without turning the PO into an orchestrator or exposing Factory noise.

## Mental model

- A **candidate** says what product result may be worth doing and why.
- An **execution Bead** is the Mayor's scoped, dependency-aware unit of work.
- Candidates are Beads with `status=deferred`; they never appear in `bd ready`.
- The first non-paused candidate is eligible. Reordering never interrupts work
  that the Mayor has already materialized.
- Order answers “what should be considered next?”. Urgency is an independent
  signal; changing urgency does not silently change order.

This is a projection over Beads, not another database, scheduler, or worker
queue. The CLI serializes mutations with a host-local lock and rejects missing,
duplicate, or malformed queue ranks instead of guessing.

## SayMyName commands

Run from `/home/benja/agent-factory`:

```bash
./bin/saymyname-product-queue list
./bin/saymyname-product-queue add --title "Make quiz feedback easier to understand" \
  --why "Learners need to know why an answer was wrong" \
  --acceptance "A learner can understand the correction without admin help"
./bin/saymyname-product-queue move af-abc 1
./bin/saymyname-product-queue urgency af-abc urgent
./bin/saymyname-product-queue pause af-abc "Waiting for customer evidence"
./bin/saymyname-product-queue resume af-abc
./bin/saymyname-product-queue cancel af-abc "No longer aligned with V1"
```

The generic entry point is `bin/product-queue`; set
`PRODUCT_QUEUE_PRODUCT=<slug>` and optionally
`PRODUCT_QUEUE_DEFAULT_GOAL=<bead-id>`. `list --json` and `next --json` are the
stable low-token projections for other tools.

The Factory cockpit Roadmap may expose these same operations under an explicit
human RECORD interaction. Its server invokes `bin/saymyname-product-queue` with
an allowlisted argument vector; it does not reproduce locking, ranks, rollback or
audit behavior. Cancellation requires a separate confirmation, pause requires a
reason, and successful writes reread the command's JSON projection immediately.
The active delivery outcome is shown separately and is never a reorder target.
The candidate whose goal is `none` is displayed as a non-product Factory campaign
rather than being blended into the product roadmap.

## Human protocol

Benjamin can speak naturally:

- “Ajoute cette idée à la fin de la file, sans la lancer.”
- “Mets `af-abc` en premier, mais ne coupe pas le travail en cours.”
- “Marque-la urgente sans changer l'ordre.”
- “Mets cette idée en pause jusqu'à ma décision.”
- “Montre-moi seulement la file produit.”
- “Lance le prochain résultat.”

The PO may add, clarify, reorder, mark urgency, pause, resume, or cancel product
candidates when Benjamin asks to record that state. This is RECORD authority,
not execution authority. A DISCUSS request never mutates the queue.

For EXECUTE, the PO hands the desired result to the Mayor once. The Mayor:

1. reads `./bin/saymyname-product-queue next --json`;
2. confirms capacity and refines scope, acceptance, rig, dependencies, and the
   delivery profile;
3. creates the separate executable Bead through the normal Factory workflow;
4. runs `./bin/saymyname-product-queue materialize <candidate> <execution-bead> --mayor`;
5. owns dispatch through verified delivery and closure.

`materialize` accepts only the first eligible candidate, verifies that the
execution Bead exists and is open or in progress, records the link, and closes
the candidate. The `--mayor` switch is an explicit policy guard and audit cue;
the durable PO/Mayor instruction boundary remains the authority control.

## Stored fields

Candidates have labels `product-queue` and `product:<slug>` plus these metadata:

| Field | Meaning |
|---|---|
| `gc.queue_product` | Product slug |
| `gc.queue_state` | `queued` or `paused` while active |
| `gc.queue_rank` | Exact order, normalized in steps of 1000 |
| `gc.queue_urgency` | `normal`, `urgent`, or `critical` |
| `gc.queue_goal` | Durable product goal, or `none` |
| `gc.materialized_bead` | Execution Bead after Mayor materialization |

Cancellation and materialization close the candidate but retain its Beads
history. Dependencies are not improvised at candidate level; the Mayor records
them on the executable work after scope is understood.
