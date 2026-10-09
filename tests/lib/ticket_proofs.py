"""What the author of a ticket leaves at its exit « terminé », filed the way
the scripts of the flow file it (T19, af-iefuud).

The ticket-end gate (bin/ticket-end) reads every proof in the evidence store
(bin/evidence-capture verify) and on the durable state of the convoy
(bin/convoy-state): a fingerprint written by hand with a made-up digest is
not a piece. A suite whose subject is another command (the merge, the code
review, the correction round, the advance pass) still needs tickets a merge
accepts; these helpers give it one without walking bin/tdd-step,
bin/demonstrate and bin/ticket-exit: each piece is filed and sealed by the
real capture tool at the commit it proves, each step recorded by the real
state command, in the order those scripts follow.

Usage (plain module on a path-inserted directory, like sandbox.py):

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "lib"))
    import ticket_proofs

    ticket_proofs.finish(env, repo, convoy, ticket, tip, base, branch)

Asked twice for the same thing (af-97io9q). A suite asks `finish` for the
same finished ticket in most of its tests: 80 calls for 12 distinct requests
in tests/spec-integration-test.py, 2.3 s and about 25 processes a call. The
first request of a process is walked through the real tools as above; what
they wrote for it (the steps and fingerprints on the ticket, the sealed
pieces in the store, the lines of the fake tracker's write log) is kept, and
the same request on a ticket in the same state gets a copy of it. A copy is
therefore always something the real tools wrote and sealed, never a piece
made by hand. Two things make requests repeat, and both are set here:

  - the commits made in the environment of a test carry one fixed date
    (below), so the same files on the same parent are the same commit in
    every test of a file;
  - a store that has no seal key yet receives the key of the store the
    pieces were sealed in, so their seals hold where they are copied.

Anything that differs (another commit, another section, a ticket that
already carries a step or a piece, a store sealed with another key) is a
request of its own and is walked for real, and so is every request outside
the fake tracker of a suite (no CONVOY_STATE_FAKE_TRACKER, as in a trial on
a real city) or without a store of its own (no EVIDENCE_STORE_DIR).
TICKET_PROOFS_NO_COPY=1 walks every request for real.

From a shell trial (tests/*-isolated-city-test.sh), in its environment:

    python3 tests/lib/ticket_proofs.py finish CONVOY TICKET TIP --repo DIR --base SHA --branch NAME [--done TEXT] [--subject TEXT]
    python3 tests/lib/ticket_proofs.py capture CONVOY TICKET PIECE COMMIT --repo DIR
"""
import argparse
import json
import os
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
STATE_TOOL = ROOT / "bin" / "convoy-state"
CAPTURE_TOOL = ROOT / "bin" / "evidence-capture"

DIGEST = "sha256:" + "ab" * 32
SECTIONS = {"done": ["Critère 1 observé sur GET /."], "deviations": "aucun", "not_done": "aucun",
            "out_of_ticket": "aucun"}
TEST_ID = "tests/test_critere.py::Critere::test_observable"
SEAL_KEY_FILE = ".seal-key"  # bin/evidence-capture

# Read by every git a test starts with a copy of this environment.
for _name in ("GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
    os.environ.setdefault(_name, "2026-01-01T00:00:00+00:00")

# request -> what the real tools wrote for it, in this process.
_FINISHED = {}


def _run(env, *argv):
    proc = subprocess.run([str(part) for part in argv], env=env, text=True, capture_output=True)
    if proc.returncode != 0:
        raise AssertionError(f"{' '.join(str(part) for part in argv)}\n{proc.stdout}{proc.stderr}")
    return proc.stdout


def state(env, *args):
    return json.loads(_run(env, STATE_TOOL, *args))


def capture(env, repo, convoy, ticket, piece, commit, report=None):
    """One piece filed by the real capture tool at `commit`: taken in a
    throwaway work tree of `repo`, removed afterwards, so the repository is
    left as it was. `report` is what the captured command prints, as the
    script of a step prints its own."""
    printed = json.dumps(report if report is not None else {"vu": piece}, ensure_ascii=False)
    with tempfile.TemporaryDirectory(prefix="ticket-proofs-") as holder:
        tree = pathlib.Path(holder) / "tree"
        _run(env, "git", "-C", repo, "worktree", "add", "-q", "--detach", tree, commit)
        try:
            return json.loads(_run(env, CAPTURE_TOOL, "command", convoy, ticket, "--piece", piece, "--repo", tree,
                                   "--expect-exit", "0", "--", "printf", "%s", printed))
        finally:
            _run(env, "git", "-C", repo, "worktree", "remove", "--force", tree)


def _ticket(env, repo, convoy, ticket):
    shown = state(env, "show", convoy, "--repo", repo)
    return next(entry for entry in shown["tickets"] if entry["id"] == ticket)


def _json_file(holder, content):
    path = pathlib.Path(holder) / "given.json"
    path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    return path


def prove_red(env, repo, convoy, ticket, commit, base):
    """The red step of a slice proven at `commit`: its sealed report, then
    the step (bin/tdd-step red)."""
    capture(env, repo, convoy, ticket, "tdd_red", commit, {
        "verdict": "red", "base": base, "seam_mode": "black_box",
        "tests": [{"id": TEST_ID, "outcome": "failed", "entry_points": ["GET /"]}]})
    state(env, "set-tdd", convoy, ticket, "--step", "red", "--commit", commit, "--base", base)


def prove_freeze(env, repo, convoy, ticket):
    """The criterion tests of a slice read favorably by their reviewer at
    the red commit (bin/test-review), then frozen there (bin/tdd-step
    freeze), each with what the ticket does not carry yet."""
    shown = _ticket(env, repo, convoy, ticket)
    known, filed = shown.get("tdd") or {}, shown.get("evidence") or {}
    red = known["red"]["commit"]
    if not known.get("freeze"):
        files = {"tests/test_critere.py": DIGEST}
        with tempfile.TemporaryDirectory(prefix="ticket-proofs-") as holder:
            state(env, "open-test-review", convoy, ticket, "--commit", red, "--file",
                  _json_file(holder, {"files": files, "criteria": {"1": [TEST_ID]}}))
            state(env, "record-test-review", convoy, ticket, "--file", _json_file(holder, {
                "commit": red, "files": files, "tests": {TEST_ID: {"state": "favorable"}},
                "recorded_by": f"delivery-test-reviewer-{ticket}"}))
        state(env, "set-tdd", convoy, ticket, "--step", "freeze", "--commit", red)
    frozen = (known.get("freeze") or {}).get("commit") or red
    if "tdd_freeze" not in filed:
        capture(env, repo, convoy, ticket, "tdd_freeze", frozen, {"frozen": frozen})
    return frozen


def prove_tdd(env, repo, convoy, ticket, tip, base, green=True):
    """The TDD of a ticket proven up to `tip`, each step with its sealed
    report: for a prefactoring the unchanged regression at the tip; for a
    slice whatever the ticket does not carry yet of the red (at the tip
    when no red is recorded), the favorable review of its criterion tests,
    the freeze and the piece of an amendment, then, unless `green` is false,
    the green at the tip and the demonstration. Returns the red proof and
    the demonstration proof the Handoff carries."""
    shown = _ticket(env, repo, convoy, ticket)
    known, filed = shown.get("tdd") or {}, shown.get("evidence") or {}
    if shown.get("kind") == "prefactoring":
        start = (known.get("prefactoring") or {}).get("base") or base
        capture(env, repo, convoy, ticket, "tdd_prefactoring", tip, {"verdict": "unchanged", "regression": [
            {"commit": start, "exit_code": 0}, {"commit": tip, "exit_code": 0}]})
        state(env, "set-tdd", convoy, ticket, "--step", "prefactoring", "--commit", tip, "--base", start)
        return {"step": "prefactoring", "base": start, "commit": tip, "piece": "tdd_prefactoring"}, None
    red = (known.get("red") or {}).get("commit") or tip
    start = (known.get("red") or {}).get("base") or base
    if not known.get("red"):
        prove_red(env, repo, convoy, ticket, red, start)
    elif "tdd_red" not in filed:
        capture(env, repo, convoy, ticket, "tdd_red", red, {
            "verdict": "red", "base": start, "seam_mode": "black_box",
            "tests": [{"id": TEST_ID, "outcome": "failed", "entry_points": ["GET /"]}]})
    frozen = prove_freeze(env, repo, convoy, ticket)
    if known.get("amendment") and "tdd_amendment" not in filed:
        capture(env, repo, convoy, ticket, "tdd_amendment", known["amendment"]["commit"], {"amended": True})
    proof = {"step": "red", "base": start, "commit": red, "piece": "tdd_red"}
    if not green:
        return proof, None
    capture(env, repo, convoy, ticket, "tdd_green", tip, {"verdict": "green", "k": 3, "frozen": frozen,
                                                         "seam_mode": "black_box"})
    state(env, "set-tdd", convoy, ticket, "--step", "green", "--commit", tip)
    capture(env, repo, convoy, ticket, "demonstration", tip)
    return proof, {"piece": "demonstration", "commit": tip, "kind": "command", "address": None}


def _timeless(value, piece=False):
    """`value` without the hours its writer stamped, and for the fingerprint
    of a piece without its digest, which covers such an hour: two walks of
    the same steps differ by nothing else."""
    if isinstance(value, str) and value[:1] in ("{", "["):
        try:
            value = json.loads(value)
        except ValueError:
            return value
    if isinstance(value, dict):
        return {key: _timeless(entry, piece) for key, entry in value.items()
                if key != "at" and not (piece and key == "digest")}
    if isinstance(value, list):
        return [_timeless(entry, piece) for entry in value]
    return value


def _beads(env):
    return json.loads(pathlib.Path(env["CONVOY_STATE_FAKE_TRACKER"]).read_text(encoding="utf-8"))["beads"]


def _store_files(store):
    return {path.relative_to(store).as_posix(): path.read_bytes()
            for path in sorted(store.rglob("*")) if path.is_file()} if store.is_dir() else {}


def _request(env, convoy, ticket, tip, base, branch, records, sections, green):
    """What a finished ticket depends on: what is asked, and the ticket as
    it stands (the steps and pieces it already carries are not redone)."""
    beads = _beads(env)
    bead = beads.get(ticket) or {}
    carried = {key: _timeless(entry, key.startswith("gc.flow.evidence."))
               for key, entry in (bead.get("metadata") or {}).items()}
    spec = ((beads.get(convoy) or {}).get("metadata") or {}).get("gc.spec_id")
    return json.dumps([convoy, spec, ticket, tip, base, branch, green, records, sections,
                       {**bead, "metadata": carried}], sort_keys=True, ensure_ascii=False, default=str)


def _copy_finished(env, ticket, request):
    """Give the ticket what the real tools wrote for the same request
    earlier in this process. False when nothing fits: the caller walks it."""
    store = pathlib.Path(env["EVIDENCE_STORE_DIR"])
    key_file = store / SEAL_KEY_FILE
    key = key_file.read_bytes() if key_file.is_file() else None
    for kept in _FINISHED.get(request, ()):
        if key not in (None, kept["key"]):
            continue
        for name, content in {SEAL_KEY_FILE: kept["key"], **kept["files"]}.items():
            target = store / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            if name == SEAL_KEY_FILE:
                target.chmod(0o600)
        tracker = pathlib.Path(env["CONVOY_STATE_FAKE_TRACKER"])
        state = json.loads(tracker.read_text(encoding="utf-8"))
        state["beads"][ticket].setdefault("metadata", {}).update(kept["metadata"])
        tracker.write_text(json.dumps(state), encoding="utf-8")
        if kept["writes"] and env.get("CONVOY_STATE_FAKE_WRITE_LOG"):
            with open(env["CONVOY_STATE_FAKE_WRITE_LOG"], "a", encoding="utf-8") as log:
                log.write(kept["writes"])
        return True
    return False


def finish(env, repo, convoy, ticket, tip, base, branch, records=None, sections=None, green=True):
    """The exit « terminé » of the author at `tip`: the TDD proven there,
    the demonstration captured, the records of the Handoff sealed, the
    Handoff and the exit recorded. `records` adds to, or replaces, the
    records of the code (those bin/ticket-exit computes). With `green`
    false the author leaves without its green: what a control must refuse.
    The same request on a ticket in the same state is walked once per
    process and copied afterwards (see the head of this module)."""
    # A copy needs the fake tracker of a suite and a store of its own: a
    # trial on a real city walks every request.
    if (not env.get("EVIDENCE_STORE_DIR") or not env.get("CONVOY_STATE_FAKE_TRACKER")
            or env.get("TICKET_PROOFS_NO_COPY") or os.environ.get("TICKET_PROOFS_NO_COPY")):
        return _walk_finish(env, repo, convoy, ticket, tip, base, branch, records, sections, green)
    request = _request(env, convoy, ticket, tip, base, branch, records, sections, green)
    if _copy_finished(env, ticket, request):
        return None
    store = pathlib.Path(env["EVIDENCE_STORE_DIR"])
    log = pathlib.Path(env.get("CONVOY_STATE_FAKE_WRITE_LOG") or os.devnull)
    beads, files = _beads(env), _store_files(store)
    logged = log.read_text(encoding="utf-8") if log.is_file() else ""
    _walk_finish(env, repo, convoy, ticket, tip, base, branch, records, sections, green)
    after, filed = _beads(env), _store_files(store)
    before, now = beads.pop(ticket), after.pop(ticket)
    was, has = before.pop("metadata", None) or {}, now.pop("metadata", None) or {}
    written = log.read_text(encoding="utf-8") if log.is_file() else ""
    # Kept only when the walk did what a copy can give back: keys added or
    # changed on this ticket, files added or changed in the store, lines
    # added to the write log.
    if (beads == after and before == now and set(was) <= set(has) and set(files) <= set(filed)
            and written.startswith(logged) and SEAL_KEY_FILE in filed):
        _FINISHED.setdefault(request, []).append({
            "key": filed.pop(SEAL_KEY_FILE),
            "files": {name: content for name, content in filed.items() if files.get(name) != content},
            "metadata": {key: entry for key, entry in has.items() if was.get(key) != entry},
            "writes": written[len(logged):]})
    return None


def _walk_finish(env, repo, convoy, ticket, tip, base, branch, records=None, sections=None, green=True):
    red, demonstration = prove_tdd(env, repo, convoy, ticket, tip, base, green=green)
    capture(env, repo, convoy, ticket, "handoff_records", tip)
    with tempfile.TemporaryDirectory(prefix="ticket-proofs-") as holder:
        state(env, "set-handoff", convoy, ticket, "--file", _json_file(holder, {
            "sections": sections or SECTIONS, "partial": False, "commit": tip, "records": {
                "exit": "finished", "branch": branch, "head": tip, "base": base, "red_proof": red,
                "demonstration_proof": demonstration, "deferral_markers": [], **(records or {})}}))
    state(env, "set-exit", convoy, ticket, "--exit", "finished")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="ticket_proofs")
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("finish")
    for name in ("convoy", "ticket", "tip"):
        command.add_argument(name)
    for name in ("--repo", "--base", "--branch"):
        command.add_argument(name, required=True)
    command.add_argument("--done", help="the one item of the section « done » of the Handoff")
    command.add_argument("--subject", help="the subject of the commit, in the records of the Handoff")
    command = sub.add_parser("capture")
    for name in ("convoy", "ticket", "piece", "commit"):
        command.add_argument(name)
    command.add_argument("--repo", required=True)
    args = parser.parse_args(argv)
    env = dict(os.environ)
    if args.command == "capture":
        capture(env, args.repo, args.convoy, args.ticket, args.piece, args.commit)
        return 0
    finish(env, args.repo, args.convoy, args.ticket, args.tip, args.base, args.branch,
           records={"commits": [{"commit": args.tip, "subject": args.subject}]} if args.subject else None,
           sections={**SECTIONS, "done": [args.done]} if args.done else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
