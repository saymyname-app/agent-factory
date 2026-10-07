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
"""
import json
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
                "recorded_by": "delivery-test-reviewer-fx"}))
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


def finish(env, repo, convoy, ticket, tip, base, branch, records=None, sections=None, green=True):
    """The exit « terminé » of the author at `tip`: the TDD proven there,
    the demonstration captured, the records of the Handoff sealed, the
    Handoff and the exit recorded. `records` adds to, or replaces, the
    records of the code (those bin/ticket-exit computes). With `green`
    false the author leaves without its green: what a control must refuse."""
    red, demonstration = prove_tdd(env, repo, convoy, ticket, tip, base, green=green)
    capture(env, repo, convoy, ticket, "handoff_records", tip)
    with tempfile.TemporaryDirectory(prefix="ticket-proofs-") as holder:
        state(env, "set-handoff", convoy, ticket, "--file", _json_file(holder, {
            "sections": sections or SECTIONS, "partial": False, "commit": tip, "records": {
                "exit": "finished", "branch": branch, "head": tip, "base": base, "red_proof": red,
                "demonstration_proof": demonstration, "deferral_markers": [], **(records or {})}}))
    state(env, "set-exit", convoy, ticket, "--exit", "finished")
