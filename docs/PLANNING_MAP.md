# Planning Map tool (A6b, W03)

## Status and purpose

`bin/planning-map` implements four of the wayfinding operations documented
in `docs/agents/issue-tracker.md` as one small stateless tool over `bd`, so
they are never hand-typed differently by two sessions:

- `create-ticket` creates a correctly shaped child ticket of a Planning Map
  Bead: parented to the map, labels *set* (not inherited from the parent --
  `bd create --parent` inherits by default, which would tag every ticket
  `wayfinder:map`) to a single `wayfinder:<type>` label, and metadata
  carrying `gc.plane: planning`.
- `check` reports whether a map is labelled `wayfinder:map`, whether every
  child is shaped the same way (parent, a `wayfinder:<type>` label, the
  planning plane), and how many children are still open. It names every
  malformed child and its problems; the map is `finished` only when it is
  labelled correctly, every child is shaped correctly, and no child is open.
- `close` closes the map with a reason. `close --abandon` additionally
  closes every still-open child with that same reason, so abandoning a map
  needs no separate command.
- `update` replaces the map's description only when its current description
  still matches what the caller last read (compare-and-set) -- plain
  `bd update --body-file` has no such check and is last-writer-wins, so a
  sibling session's decision line could otherwise be silently overwritten.

Claim, resolve, comment and blocking dependencies stay native `bd` commands
(see `docs/agents/issue-tracker.md`); this tool does not wrap them, and
there is no pause or resume.

## Run it

```bash
# Create a child ticket of a map.
bin/planning-map create-ticket --map af-0aiero --type research \
  --title "Which store backs the map?" --body-file question.md

# Check a map's shape and completion.
bin/planning-map check --map af-0aiero

# Close a finished map.
bin/planning-map close --map af-0aiero --reason "Spec approved; map done"

# Abandon a map, closing its open children with the same reason.
bin/planning-map close --map af-0aiero --abandon \
  --reason "Superseded by a later Planning Run"

# Safely update a map's description (refuses if it changed since your read).
bin/planning-map update --map af-0aiero \
  --expected-description-file map-as-i-read-it.md \
  --body-file map-with-my-decision.md
```

Every subcommand prints one JSON object with `"ok": true|false`; a refused
`update` or a failed `bd` call prints `"ok": false` with an `"error"` and
exits non-zero.

## Testing

`tests/planning-map-test.py` drives the tool's command line against the
stateful fake `bd` in `tests/fixtures/planning-map/bd` (backed by a JSON
file named by `PLANNING_MAP_BD_STATE`, so a test can create/close beads and
then assert what a later `check`/`close` sees) and asserts on its JSON
output and the beads it leaves behind. It never touches the live Beads
database. Override `BD_BIN` to point the tool at a different `bd`.
