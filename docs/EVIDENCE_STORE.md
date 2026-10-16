# Evidence capture and evidence store (T09, Spec af-wf4w5r §9)

## Status and purpose

An **Evidence Record** is one piece of evidence tied to a commit. No agent
writes one: `bin/evidence-capture` runs the command, or drives the browser,
itself, and records what it got. The piece goes into the Factory's **evidence
store**, outside any Git history, filed by Spec and by ticket; its fingerprint
goes on the ticket in the tracker through `bin/convoy-state add-evidence`
(`docs/CONVOY_STATE.md`). A piece of the end of the Spec, captured on the
assembled product by the Evaluator of the end (T24,
`docs/OUTCOME_EVALUATION.md`), names the convoy in the place of the ticket
(`evidence-capture command CONVOY CONVOY …`): it is filed under
`<store>/<spec id>/<convoy id>/` and its fingerprint goes on the convoy. A
piece the tool did not produce is refused by `verify`.

The tool applies to a convoy that carries the new-flow mark only. On any
other convoy it answers « pas un convoi du nouveau flux » (exit 4): nothing
is run, nothing is written.

```bash
# a command: its argv, its real output, its exit code, the time and the commit
./bin/evidence-capture command af-convoy af-t1 --piece demo.tests --repo rigs/product -- python3 -m pytest -q

# a command against the product launched by bin/project-launch (its address and commit are recorded)
./bin/project-launch start <descriptor.json> --commit <sha> --dataset content --state-file /tmp/launch.json
./bin/evidence-capture command af-convoy af-t1 --piece demo.sonde --launch-state /tmp/launch.json -- curl -s http://127.0.0.1:<port>/health

# a screenshot of one address of that launched product
./bin/evidence-capture screenshot af-convoy af-t1 --piece demo.page --launch-state /tmp/launch.json --path /

# the same address beside a reference page served on this host, and the image of their difference (bin/prototype-fidelity)
./bin/evidence-capture comparison af-convoy af-t1 --piece fidelity.content.desktop --launch-state /tmp/launch.json --path / \
    --reference-url http://127.0.0.1:<port>/states/content.html [--window-size 1280x800] [--color-scheme light|dark]

./bin/evidence-capture verify af-convoy af-t1 [--piece demo.page]   # the gates, before they accept a piece
./bin/evidence-capture show af-convoy af-t1 [--piece merged_tests]  # read a piece: verify, then its record
./bin/evidence-capture purge --spec af-spec                         # after promotion, by code
```

Every answer is one JSON object on stdout.

| Exit | Meaning |
|---|---|
| 0 | done |
| 1 | refused: nothing was written, nothing is left in the store (`{"ok": false, "error": "refus : …"}`) |
| 4 | the convoy does not carry the mark: « pas un convoi du nouveau flux » |

The exit code of the captured command is data, recorded in the piece: a
command that fails is captured and the tool exits 0.

`command --expect-exit <code>` files the piece only if the command exits
with that code. Any other exit is a refusal (exit 1) whose answer carries
`exit_code` and `output`, and nothing is written. It is what a script that
proves a step uses, so that only its passing report becomes a piece:
`bin/tdd-step` runs each of its checks this way (`docs/TDD_STEP.md`, pieces
`tdd_red`, `tdd_freeze`, `tdd_green`, `tdd_amendment`, `tdd_prefactoring`).
`bin/ticket-author demonstrate` captures the demonstration line of a ticket
on the product it launched (piece `demonstration`, `docs/TICKET_AUTHOR.md`).
`bin/ticket-exit` seals the records of a Ticket Handoff the same way (piece
`handoff_records`, `docs/TICKET_EXIT.md`). `bin/spec-integration` captures
the tests it runs on a merged result without `--expect-exit` (piece
`merged_tests`, `docs/SPEC_INTEGRATION.md`): a red run is a piece too, tied
to the commit that was tested and never pushed.

## The store

```
<store>/.seal-key                      the key that seals every record (mode 0600, created at the first capture)
<store>/<spec id>/<ticket id>/<piece>.json     the Evidence Record
<store>/<spec id>/<ticket id>/<piece>.png      the image of a screenshot piece, or the two sides of a comparison piece
<store>/<spec id>/<ticket id>/<piece>--difference.png   the image of the difference of a comparison piece
```

`<store>` is `EVIDENCE_STORE_DIR`, default `~/.local/state/agent-factory-evidence`
(`~/.local/state` is what `bin/delivery-role-sandbox` leaves writable to a
read-only role, so the Evaluator captures there too). The Spec is the one the
convoy names (`gc.spec_id`, read through `bin/convoy-state show`, field
`convoy.spec`).

**Outside Git history.** A capture is refused when the store is inside a Git
work tree or a `.git` directory, ignored paths included: no piece can reach
the history of the product or of the Factory. Synthetic data only: the tool
records whatever the command prints, so a command that prints a secret puts it
in the store.

A piece name is made of letters, digits, `_` and `.` (the alphabet of a
tracker metadata key). Capturing a piece again under the same name replaces
it, in the store and in the tracker.

## What a record holds

| Field | Command piece | Screenshot piece |
|---|---|---|
| `contract` | `agent-factory-evidence-record/v1` | same |
| `kind` | `command` | `screenshot` |
| `spec`, `convoy`, `ticket`, `piece` | where it is filed | same |
| `at` | UTC time of the capture | same |
| `commit` | HEAD of `--repo`, or the commit of the launched product | the commit of the launched product |
| `address` | the launched product's address with `--launch-state`, else `null` | the address captured |
| `command`, `exit_code` | the argv run and its exit code | — |
| `output` | stdout and stderr together, as produced by the run | — |
| `output_digest`, `output_bytes`, `output_truncated` | fingerprint and size of the full output; above 1 MB the record keeps its first and last 500 kB | — |
| `image`, `image_digest` | — | the image file beside the record, and its fingerprint |
| `http_status`, `window_size` | — | what the address answered before the capture; the window (`--window-size`, default `1280x800`) |
| `seal` | HMAC-SHA256 of every other field under the store's key | same |

The fingerprint written in the tracker is the SHA-256 of the record file, with
the record's commit. The record carries the image's fingerprint, so the one
fingerprint of the tracker covers both files.

## What a capture refuses

Before anything is run: a piece name outside the alphabet; no command after
`--`; a store inside a Git work tree; a convoy without the mark (exit 4), a
convoy that names no Spec, a ticket the convoy does not track or that does
not carry the mark; `--repo` that is not a repository with a commit, or whose
tracked files differ from HEAD (the output would be tied to no commit;
untracked files are ignored); a launch record that is not the file written by
`bin/project-launch start --state-file`.

`command` never takes its output from the caller: no option carries one (an
unknown option is an argparse error, exit 2), and the command runs with no
standard input. A command that cannot be started, that does not finish
within `--timeout` seconds (default 600), or that does not exit with the
code given by `--expect-exit`, leaves no piece.

`screenshot` captures an address of the launched product only: `--path` is a
path under the address of the launch record, never another host. It is
refused when the product does not answer (a browser pointed at a stopped
product would capture its own error page), when no Chromium is found, and
when the browser writes no PNG image.

`comparison` (T16, `docs/PROTOTYPE_FIDELITY.md`) captures the address of the
launched product and a **reference page** at the same moment, with the same
browser, at the same size and colour scheme, and files one piece of kind
`comparison`: `address` and `reference` (the two addresses), `image` (the two
captures side by side, the reference on the left), `difference` (a differing
pixel in red on the faded reference; a pixel one side does not have
differs), each with its fingerprint, `differing_pixels` and `pixels`,
`http_status`, `window_size`, `color_scheme`. The count is data: the tool
judges nothing from it and has no threshold. It refuses, before any capture,
a reference that is not a page served on this host
(`http://127.0.0.1:<port>/…`), one that does not answer 200, a colour scheme
outside `light` / `dark`, and everything `screenshot` refuses.

If the tracker refuses the fingerprint, the store keeps what it had: the new
files are removed.

**Browser.** `EVIDENCE_CAPTURE_BROWSER` names it; otherwise
`chrome-headless-shell` on `PATH` or in the Playwright cache
(`~/.cache/ms-playwright`, or `PLAYWRIGHT_BROWSERS_PATH`), then a `chromium` /
`google-chrome` binary. Tried on Chromium 1243 under WSL (2026-10-06):
`chrome-headless-shell --headless --screenshot=<file> <url>` writes the image
and exits; the full `chrome --headless` never exits on a fresh profile, and is
refused after 60 s. Each capture runs on its own throwaway profile and leaves
no browser process behind.

## What `verify` refuses

`verify CONVOY TICKET --piece NAME` checks one piece; without `--piece`, every
piece of the ticket (those the tracker names and those the store holds). It
fails, naming each reason, when:

- the tracker holds no fingerprint for the piece, or the store holds no file;
- the file of the store no longer matches the fingerprint of the tracker;
- the piece was not produced by the tool: no seal, or a seal that does not
  match its content — even when its fingerprint was written in the tracker by
  hand (`bin/convoy-state add-evidence`);
- a genuine piece was copied under another Spec, convoy, ticket or name;
- the record's commit is not the commit of the tracker's fingerprint;
- the image of a screenshot piece, or either image of a comparison piece, is
  missing or was replaced;
- (whole ticket) a file sits in the ticket's folder that no capture filed.

`verify` writes nothing. A ticket without any piece verifies: which pieces a
ticket must hold is the business of the gate that calls it. Its answer names
the folder it read (`path`).

## Reading a piece: `show`

`show CONVOY TICKET [--piece NAME]` is `verify` followed by each record as
filed, the real output of a command included: what an operator runs to read
`merged_tests` or a demonstration. It takes the convoy, never the Spec: the
Spec is read on the convoy, and the store is filed under
`<store>/<spec id>/<ticket id>/` (a piece of the end of the Spec: the convoy
twice). With no piece in that folder it refuses and names the folder; given
something other than a convoy and one of its tickets, its refusal says how
the store is filed (af-rt5a4h: `show <spec> <convoy>` once answered nothing
while the pieces sat under the Spec's folder). `show` writes nothing.

## Purge

`purge --spec SPEC` removes the folder of that Spec and answers how many
pieces it held; every other Spec, and the seal key, stay. The fingerprints
stay in the tracker: after a purge `verify` reports the pieces as absent from
the store. Spec §9 keeps the pieces until promotion; the code that promotes is
the caller: `bin/outcome-promote`, once the accepted Outcome is merged and
noted in its dossier, before it closes the convoy (T30,
`docs/OUTCOME_PROMOTE.md`). An abandoned Outcome is not purged.

## Limits

- The tool chooses nothing: the agent decides what to capture (Spec §9,
  assumed limit).
- The seal proves a record went through the tool on this host. It is a guard
  on the honest path, not against the account that owns the store: a process
  running as the same Unix user can read `.seal-key`. A forged piece is then
  visible only by replaying the capture.
- A piece is tied to the commit, not to the cleanliness of what the command
  reads outside the repository (network, other directories).
- Retention has no timer: nothing is purged until `purge` is called.

## Proof

`tests/evidence-capture-test.py` drives the command line on a fake tracker
state (`tests/fixtures/convoy-state/gc`), the Delivery Fixture City launched
by the real `bin/project-launch`, and a fake browser that fetches the page it
is given (`tests/fixtures/evidence-capture/browser`): one test per pass and
per refusal, each refusal re-reading the tracker and the store to prove
nothing was written. `tests/evidence-capture-demonstration-test.sh`
(local-only) replays the demonstration line on the real `gc`/`bd` in a
disposable city with the real Chromium.
