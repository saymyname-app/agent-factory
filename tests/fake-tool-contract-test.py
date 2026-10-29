#!/usr/bin/env python3
"""Fakes must refuse what the real tool refuses (af-kiy7lm).

Every test in this suite runs against fakes of gc/bd/gh instead of the real
tools (P10, af-ygibh). A fake that accepts a command shape the real tool
rejects turns a broken script green: four safety nets broke silently this
way (af-sa2i1: `gc bd create --set-metadata`, a flag `bd create` has never
had; af-4ruvv/af-1isbx: order/close-path regressions a too-permissive fake
would also have missed; and `gh pr update-branch`, absent from the gh 2.45
installed on this host, see tests/gh-unsupported-subcommand-guard-test.sh).

This test extracts every (subcommand, flag) shape the declared-scope fakes
under tests/fixtures actually accept. On a Factory host it calibrates the
behavior oracle and command shapes against the installed real tools. In CI,
whose runner deliberately has no gc/bd/Dolt runtime, it replays every fake
against that same closed oracle. A new fake or scenario must be declared
before either mode passes.

A shape the real tool accepts can still mean something else than the fake
makes of it (T48, af-1zxao6: `bd create --deps blocks:<id>` makes <id> wait
for the new issue, and the fake stored nothing, so a door that posed every
edge backwards stayed green). So the stateful fake `bd` of the publication
door is also run beside the real `bd`, in a disposable city that shares
nothing with the live Factory: the same dependency commands, then the same
question -- which issue waits for which.
"""
import errno
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"

FAILURES = []

FAKE_TOOL_NAME = re.compile(r"(?:^|[-_])(bd|gc)(?:[-_.]|$)")

# Mutable tracker doubles replay the blocked-close case below. Every other
# executable bd/gc double is a narrow read/transport seam; its dated exception
# says why the stateful cases do not apply. All of them still replay the
# kernel argument-size case. The inventory is closed: a new executable fake
# must choose one side before this control passes.
MUTABLE_TRACKER_FAKES = {
    "cockpit/actions/fake-bd",
    "cockpit/operator-actions/fake-bd",
    "cockpit/synthetic-city/bd",
    "convoy-state/gc",
    "escalation-door/gc",
    "planning-map/bd",
    "planning-run-lifecycle/bd",
    "proposal-door/fake-gc",
    "spec-approve/bd",
    "ticket-graph-publish/bd-bead-mode",
    "ticket-graph-publish/gc",
}
DATED_BEHAVIOR_EXCEPTIONS = {
    "cockpit/core/fake-bd": "2026-10-29: read-only canned list responses; it accepts no write",
    "cockpit/core/fake-gc-supervisor-cli": "2026-10-29: supervisor/status transport only; it accepts no tracker write",
    "cockpit/health/fake-bd-health": "2026-10-29: read-only health polling; it accepts no write",
    "cockpit/operator-actions/fake-gc-bin": "2026-10-29: order-run transport only; it accepts no tracker write",
    "cockpit/requests/fake-bd": "2026-10-29: read-only request polling; it accepts no write",
    "cockpit/requests/silent-bd": "2026-10-29: deliberately never answers; it models an unreadable tracker",
    "cockpit/synthetic-city/gc": "2026-10-29: transparent proxy; its mutable tracker is synthetic-city/bd",
    "deliver-close/gc": "2026-10-29: write recorder only; it owns no tracker state",
    "fake-bd.py": "2026-10-29: refusal sentinel; it accepts no command",
    "fake-gc.py": "2026-10-29: refusal sentinel; it accepts no command",
    "idle-ready-work-wake/bd": "2026-10-29: read-only ready-work probe; it accepts no write",
    "idle-ready-work-wake/gc": "2026-10-29: session/mail transport only; it accepts no tracker write",
    "mail-reply-reap/bd": "2026-10-29: guarded-close recorder with no tracker graph to query",
    "planning-run-lifecycle/dispatch-gc": "2026-10-29: dispatch recorder; the lifecycle tracker is the sibling bd",
    "planning-run-lifecycle/gc": "2026-10-29: mail recorder; the lifecycle tracker is the sibling bd",
    "shared-drain/fake-gc.py": "2026-10-29: metadata/convoy transport; it accepts no status or dependency write",
}


def fake_bd_gc_executables():
    return {
        str(path.relative_to(FIXTURES))
        for path in FIXTURES.rglob("*")
        if path.is_file() and os.access(path, os.X_OK) and FAKE_TOOL_NAME.search(path.name)
    }


def fail(msg):
    FAILURES.append(msg)
    print("FAIL:", msg, file=sys.stderr)


def real_help(*argv):
    """Return combined stdout+stderr of `argv --help`, exit code ignored.

    gh prints unknown-subcommand help to stdout with the *parent* command's
    usage; bd/gc print flag help to stdout for a valid subcommand. Either
    way the real tool's own text is what we diff fake-accepted shapes
    against.
    """
    proc = subprocess.run(
        list(argv) + ["--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout + proc.stderr


def real_version(binary, *version_argv):
    proc = subprocess.run(
        [binary, *version_argv], capture_output=True, text=True, check=False
    )
    return (proc.stdout + proc.stderr).strip().splitlines()[0] if (proc.stdout + proc.stderr).strip() else "<no output>"


# --- extract (subcommand-path, flags) shapes from a fake's source -------

SUBCOMMAND_RE = re.compile(r'args\[:(\d)\]\s*==\s*\[((?:"[^"]*",?\s*)+)\]')
FLAG_LITERAL_RE = re.compile(r'"(--[a-zA-Z][\w-]*)"')


def extract_shapes(source_path: Path):
    """Return a list of (subcommand_tokens, flags_in_block) tuples.

    Each match of `args[:N] == ["tok1", "tok2", ...]` starts a shape; the
    flags recognized for that shape are every `"--flag"` string literal
    appearing between that match and the next top-level shape match (or
    EOF), which is where each fake's branch-specific flag parsing lives.
    """
    text = source_path.read_text()
    matches = list(SUBCOMMAND_RE.finditer(text))
    shapes = []
    for i, m in enumerate(matches):
        tokens = re.findall(r'"([^"]*)"', m.group(2))
        block_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[m.end():block_end]
        flags = sorted(set(FLAG_LITERAL_RE.findall(block)))
        shapes.append((tokens, flags))
    return shapes


def check_bd_shape(fake_name, tokens, flags):
    # tokens like ["bd", "show"] (gc's `bd` passthrough) -> real help is
    # `bd <subcommand> --help`.
    subcommand = tokens[1]
    help_text = real_help("bd", subcommand)
    if "Usage:" not in help_text and "unknown command" in help_text.lower():
        fail(f"{fake_name}: real bd has no subcommand {subcommand!r} "
             f"(accepted by fake shape {tokens})")
        return
    for flag in flags:
        if flag not in help_text:
            fail(f"{fake_name}: real `bd {subcommand} --help` does not "
                 f"mention {flag!r} (accepted by fake shape {tokens})")


def check_convoy_shape(fake_name, tokens, flags):
    help_text = real_help("gc", "convoy", "status")
    for flag in flags:
        if flag not in help_text:
            fail(f"{fake_name}: real `gc convoy status --help` does not "
                 f"mention {flag!r} (accepted by fake shape {tokens})")


def check_gh_pr_shape(fake_name, tokens, flags):
    subcommand = tokens[1]
    help_text = real_help("gh", "pr")
    if not re.search(rf'^\s*{re.escape(subcommand)}:', help_text, re.MULTILINE):
        fail(f"{fake_name}: real `gh pr --help` does not list "
             f"{subcommand!r} as a subcommand (accepted by fake shape {tokens})")
        return
    if flags:
        sub_help = real_help("gh", "pr", subcommand)
        for flag in flags:
            if flag not in sub_help:
                fail(f"{fake_name}: real `gh pr {subcommand} --help` does "
                     f"not mention {flag!r} (accepted by fake shape {tokens})")


def check_fake(fake_name, relpath, checker):
    path = FIXTURES / relpath
    if not path.exists():
        fail(f"{fake_name}: fixture missing at {relpath}")
        return
    shapes = extract_shapes(path)
    if not shapes:
        print(f"OK {fake_name}: no accepted command shapes (refuses everything)")
        return
    for tokens, flags in shapes:
        checker(fake_name, tokens, flags)
    print(f"OK {fake_name}: checked {len(shapes)} accepted shape(s)")


def check_fake_inventory():
    found = fake_bd_gc_executables()
    declared = MUTABLE_TRACKER_FAKES | set(DATED_BEHAVIOR_EXCEPTIONS)
    for path in sorted(found - declared):
        fail(f"{path}: executable bd/gc fake has no behavior scenarios or dated exception")
    for path in sorted(declared - found):
        fail(f"{path}: declared bd/gc fake is missing or no longer executable")
    print(f"OK inventory: {len(found)} executable bd/gc fakes are declared")


def rejects_large_argument(command):
    """Return whether exec refused one argument at Linux MAX_ARG_STRLEN."""
    try:
        subprocess.run(
            [*command, "x" * 131_072],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError as exc:
        return exc.errno == errno.E2BIG
    return False


def check_argument_size_contract(real_runtime):
    """Calibrate the kernel boundary, with real tools when they are installed."""
    calibration = ("bd", "gc") if real_runtime else (sys.executable,)
    for real in calibration:
        if rejects_large_argument([real]):
            continue
        fail(f"{real}: calibration did not refuse a 131072-byte argument with E2BIG")
        return
    source = "real bd/gc" if real_runtime else "the CI runner kernel"
    print(f"OK calibration: {source} refuses a 131072-byte argument with E2BIG")
    for relpath in sorted(fake_bd_gc_executables()):
        if rejects_large_argument([str(FIXTURES / relpath)]):
            print(f"  argument size: {relpath}")
        else:
            fail(f"{relpath}: accepted an argument the real tool cannot exec")


# Each way the fake `bd` of the publication door accepts to pose a
# dependency between a new issue and an older one: the arguments of
# `bd create` for the new issue, then the `bd dep` commands that follow.
DEPENDENCY_SHAPES = {
    "create --deps <old>": (["--deps", "{old}"], []),
    "create --deps blocks:<old>": (["--deps", "blocks:{old}"], []),
    "create --deps depends-on:<old>": (["--deps", "depends-on:{old}"], []),
    "create --deps blocked-by:<old>": (["--deps", "blocked-by:{old}"], []),
    "create --deps tracks:<old>": (["--deps", "tracks:{old}"], []),
    "dep add <new> <old>": ([], [["dep", "add", "{new}", "{old}"]]),
    "dep add <new> <old> --type tracks": ([], [["dep", "add", "{new}", "{old}", "--type", "tracks"]]),
    "dep add then dep remove <new> <old>": ([], [["dep", "add", "{new}", "{old}"], ["dep", "remove", "{new}", "{old}"]]),
}
EXPECTED_DEPENDENCY_EDGES = {
    "create --deps <old>": [("new", "old", "blocks")],
    "create --deps blocks:<old>": [("old", "new", "blocks")],
    "create --deps depends-on:<old>": [("new", "old", "blocks")],
    "create --deps blocked-by:<old>": [("new", "old", "blocks")],
    "create --deps tracks:<old>": [("new", "old", "tracks")],
    "dep add <new> <old>": [("new", "old", "blocks")],
    "dep add <new> <old> --type tracks": [("new", "old", "tracks")],
    "dep add then dep remove <new> <old>": [],
}
PUBLISH_FAKE_BD = FIXTURES / "ticket-graph-publish" / "bd-bead-mode"
LIFECYCLE_FAKE_BD = FIXTURES / "planning-run-lifecycle" / "bd"


def isolated_env(trial):
    env = {
        key: value for key, value in os.environ.items()
        if not re.match(r"^(GC_|BEADS_|BD_BIN$|GH_BIN$|FACTORY_ROOT$)", key)
    }
    env.update(HOME=str(trial / "home"), TMUX_TMPDIR=str(trial / "tmux"))
    for directory in ("home", "tmux"):
        (trial / directory).mkdir(exist_ok=True)
    return env


def seeded_beads():
    blocker = {
        "id": "blocker", "title": "blocker", "description": "", "status": "open",
        "issue_type": "task", "labels": [], "metadata": {}, "parent": None,
    }
    blocked = {
        "id": "blocked", "title": "blocked", "description": "", "status": "open",
        "issue_type": "task", "labels": [], "metadata": {}, "parent": None,
        "waits_for": ["blocker"], "blocks": ["blocker"],
        "dependencies": [{"id": "blocker", "status": "open", "dependency_type": "blocks"}],
    }
    return blocker, blocked


def blocked_close_cases(trial, base_env):
    """Build each mutable fake's own store and return observable close cases."""
    cases = []
    blocker, blocked = seeded_beads()

    def list_store(name, relpath, commands, supports_close):
        root = trial / name
        root.mkdir()
        state = root / "beads.json"
        env = {**base_env, "FAKE_BD_STATE_FILE": str(state), "FAKE_BD_CALLS_FILE": str(root / "calls.jsonl")}

        def reset():
            state.write_text(json.dumps([blocker, blocked]), encoding="utf-8")

        def status():
            return next(bead["status"] for bead in json.loads(state.read_text()) if bead["id"] == "blocked")

        def unblock():
            beads = json.loads(state.read_text())
            next(bead for bead in beads if bead["id"] == "blocker")["status"] = "closed"
            state.write_text(json.dumps(beads), encoding="utf-8")

        cases.append((relpath, commands, env, reset, unblock, status, supports_close))

    list_store("cockpit-actions", "cockpit/actions/fake-bd", [("update", "blocked", "--status", "closed")], False)
    list_store("cockpit-operator-actions", "cockpit/operator-actions/fake-bd",
               [("update", "blocked", "--status", "closed")], False)
    list_store("cockpit-synthetic", "cockpit/synthetic-city/bd",
               [("update", "blocked", "--status", "closed")], True)

    def dict_store(name, relpath, env_name, commands, extra_env=None):
        root = trial / name
        root.mkdir()
        state = root / "beads.json"
        env = {**base_env, env_name: str(state), **(extra_env or {})}

        def reset():
            state.write_text(json.dumps({"beads": {"blocker": blocker, "blocked": blocked}, "next_id": 3}),
                             encoding="utf-8")

        def status():
            return json.loads(state.read_text())["beads"]["blocked"]["status"]

        def unblock():
            data = json.loads(state.read_text())
            data["beads"]["blocker"]["status"] = "closed"
            state.write_text(json.dumps(data), encoding="utf-8")

        cases.append((relpath, commands, env, reset, unblock, status, True))

    dict_store("planning-map", "planning-map/bd", "PLANNING_MAP_BD_STATE",
               [("close", "blocked", "--reason", "contract")])
    dict_store("planning-run", "planning-run-lifecycle/bd", "PLANNING_RUN_LIFECYCLE_BD_STATE",
               [("close", "blocked", "--reason", "contract")])
    dict_store("spec-approve", "spec-approve/bd", "SPEC_APPROVE_BD_STATE",
               [("close", "blocked", "--reason", "contract")])
    dict_store("ticket-graph-bd", "ticket-graph-publish/bd-bead-mode", "TICKET_GRAPH_BD_STATE",
               [("update", "blocked", "--status", "closed")])
    dict_store("convoy-state", "convoy-state/gc", "CONVOY_STATE_FAKE_TRACKER",
               [("bd", "update", "blocked", "--status", "closed"),
                ("bd", "close", "blocked", "--reason", "contract")])
    dict_store("ticket-graph-gc", "ticket-graph-publish/gc", "TICKET_GRAPH_BD_STATE",
               [("bd", "update", "blocked", "--status", "closed"),
                ("bd", "close", "blocked", "--reason", "contract")],
               {"TICKET_GRAPH_GC_LOG": str(trial / "ticket-graph-gc.log")})

    def file_store(name, relpath, prefix, commands):
        root = trial / name
        root.mkdir()
        bead_dir = root / "beads"
        bead_dir.mkdir()
        env = {**base_env, f"{prefix}_BEAD_DIR": str(bead_dir), f"{prefix}_CALL_LOG": str(root / "calls.log")}
        if prefix == "PD":
            next_ids = root / "next-ids"
            next_ids.write_text("unused\n", encoding="utf-8")
            env["PD_NEXT_ID_FILE"] = str(next_ids)

        def reset():
            (bead_dir / "blocker.json").write_text(json.dumps(blocker), encoding="utf-8")
            (bead_dir / "blocked.json").write_text(json.dumps(blocked), encoding="utf-8")

        def status():
            return json.loads((bead_dir / "blocked.json").read_text())["status"]

        def unblock():
            data = json.loads((bead_dir / "blocker.json").read_text())
            data["status"] = "closed"
            (bead_dir / "blocker.json").write_text(json.dumps(data), encoding="utf-8")

        cases.append((relpath, commands, env, reset, unblock, status, True))

    file_store("escalation", "escalation-door/gc", "ED",
               [("bd", "update", "blocked", "--status", "closed")])
    file_store("proposal", "proposal-door/fake-gc", "PD",
               [("bd", "update", "blocked", "--status", "closed"),
                ("bd", "close", "blocked", "--reason", "contract")])
    return cases


def dependency_edges(bd, env, cwd, create_args, followups):
    """Pose one dependency shape with this `bd` and return the edges the
    tracker then shows, as (issue that waits or tracks, the other, type)."""
    def run(*argv):
        proc = subprocess.run([*bd, *argv], env=env, cwd=cwd, text=True, capture_output=True)
        if proc.returncode != 0:
            raise RuntimeError(f"{' '.join(argv)}: {proc.stderr.strip() or proc.stdout.strip()}")
        return proc.stdout.strip()

    old = run("create", "--title", "old issue", "--type", "task", "--silent")
    names = {"old": old}
    new = run("create", "--title", "new issue", "--type", "task",
              *(arg.format(**names) for arg in create_args), "--silent")
    names["new"] = new
    for followup in followups:
        run(*(arg.format(**names) for arg in followup))
    role = {old: "old", new: "new"}
    return sorted(
        (role[holder], role.get(dep.get("id"), "?"), dep.get("dependency_type"))
        for holder in (old, new)
        for dep in json.loads(run("show", holder, "--json"))[0].get("dependencies") or []
    )


def issue_status(bd, env, cwd, issue_id):
    proc = subprocess.run([*bd, "show", issue_id, "--json"], env=env, cwd=cwd,
                          text=True, capture_output=True, check=True)
    return json.loads(proc.stdout)[0]["status"]


def calibrate_blocked_close(env, city):
    """Prove the real tracker refuses both public ways to close blocked work."""
    def run(*args, check=True):
        return subprocess.run(["bd", *args], env=env, cwd=city, text=True, capture_output=True, check=check)

    blocker = run("create", "--title", "blocker", "--type", "task", "--silent").stdout.strip()
    blocked = run("create", "--title", "blocked", "--type", "task", "--silent").stdout.strip()
    run("dep", "add", blocked, blocker)
    for close in (("update", blocked, "--status", "closed"),
                  ("close", blocked, "--reason", "contract")):
        proc = run(*close, check=False)
        if proc.returncode == 0 or issue_status(["bd"], env, city, blocked) != "open":
            fail(f"real bd calibration: `bd {' '.join(close)}` did not refuse and preserve blocked work")
            return False
    print("OK calibration: real bd refuses update/close of blocked work without --force")
    return True


def check_bd_behavior(real_runtime):
    """Calibrate the oracle when possible, then replay every relevant fake."""
    trial = Path(tempfile.mkdtemp(prefix="af-1zxao6-fake-bd-contract."))
    city_started = False
    try:
        # Nothing of the live Factory may reach this city.
        env = isolated_env(trial)
        city = trial / "city"
        if real_runtime:
            for setup in (
                ["dolt", "config", "--global", "--add", "user.name", "fake-bd contract trial"],
                ["dolt", "config", "--global", "--add", "user.email", "trial@example.invalid"],
                ["gc", "init", "--template", "minimal", "--default-provider", "codex", "--skip-provider-readiness",
                 "--no-start", "--yes", "--name", "af-1zxao6-fake-bd-contract", str(city)],
            ):
                proc = subprocess.run(setup, env=env, text=True, capture_output=True)
                if proc.returncode != 0:
                    fail(f"the disposable city of the bd dependency check could not be made ({' '.join(setup[:2])}): "
                         f"{proc.stderr.strip()[-300:]}")
                    return
            city_started = True
            if not calibrate_blocked_close(env, city):
                return
        else:
            print("OK CI oracle: blocked close must fail and preserve open status")

        for relpath, commands, fake_env, reset, unblock, status, supports_close in blocked_close_cases(trial, env):
            for command in commands:
                reset()
                proc = subprocess.run([str(FIXTURES / relpath), *command], env=fake_env, cwd=trial,
                                      text=True, capture_output=True, check=False)
                if proc.returncode == 0 or status() != "open":
                    fail(f"{relpath}: `{' '.join(command)}` closed or accepted closing blocked work")
                else:
                    print(f"  blocked close: {relpath} ({' '.join(command[:2])})")
                if supports_close:
                    reset()
                    unblock()
                    proc = subprocess.run([str(FIXTURES / relpath), *command], env=fake_env, cwd=trial,
                                          text=True, capture_output=True, check=False)
                    if proc.returncode != 0 or status() != "closed":
                        fail(f"{relpath}: `{' '.join(command)}` did not close work after its blocker closed")

        dependency_fakes = (
            ("ticket-graph-publish/bd-bead-mode", PUBLISH_FAKE_BD,
             {**env, "TICKET_GRAPH_BD_STATE": str(trial / "ticket-graph-dependencies.json")}),
            ("planning-run-lifecycle/bd", LIFECYCLE_FAKE_BD,
             {**env, "PLANNING_RUN_LIFECYCLE_BD_STATE": str(trial / "lifecycle-dependencies.json")}),
        )
        for shape, (create_args, followups) in DEPENDENCY_SHAPES.items():
            real = EXPECTED_DEPENDENCY_EDGES[shape]
            if real_runtime:
                try:
                    observed = dependency_edges(["bd"], env, city, create_args, followups)
                except RuntimeError as exc:
                    fail(f"real bd calibration, `bd {shape}`: {exc}")
                    continue
                if observed != real:
                    fail(f"real bd changed `bd {shape}` from oracle {real} to {observed}; recalibrate deliberately")
                    continue
            for fake_name, fake_path, fake_env in dependency_fakes:
                try:
                    fake = dependency_edges([str(fake_path)], fake_env, trial, create_args, followups)
                except RuntimeError as exc:
                    fail(f"{fake_name}, `bd {shape}`: {exc}")
                    continue
                if real != fake:
                    fail(f"{fake_name}, `bd {shape}`: real edges {real}, fake edges {fake}")
                else:
                    print(f"  dependency: {fake_name}, bd {shape}: {real}")
    finally:
        # The city's managed Dolt server outlives `gc init`; its command line
        # carries the trial directory, and nothing else does.
        if city_started:
            subprocess.run(["pkill", "-f", "--", str(trial) + "/"], capture_output=True)
            subprocess.run(["sleep", "1"])
            subprocess.run(["pkill", "-9", "-f", "--", str(trial) + "/"], capture_output=True)
        shutil.rmtree(trial, ignore_errors=True)


def main():
    real_runtime = all(shutil.which(binary) for binary in ("gc", "bd", "dolt"))
    if real_runtime:
        print("Recording installed real tool versions:")
        for binary, version_args in (("gc", ("version",)), ("bd", ("--version",)),
                                     ("gh", ("--version",)), ("codex", ("--version",)),
                                     ("claude", ("--version",))):
            if shutil.which(binary):
                print(" ", real_version(binary, *version_args))
        print()
    else:
        print("CI mode: real gc/bd/Dolt runtime unavailable; replaying the calibrated oracle")

    for name in ("gc", "bd", "gh"):
        if not (ROOT / "tests" / "fixtures" / f"fake-{name}.py").exists():
            fail(f"missing base fixture fake-{name}.py")

    check_fake_inventory()
    check_argument_size_contract(real_runtime)

    if real_runtime and shutil.which("gh"):
        check_fake("shared-drain/fake-gc.py bd-shapes",
                    "shared-drain/fake-gc.py",
                    lambda n, tokens, flags: (
                        check_bd_shape(n, tokens, flags) if tokens[0] == "bd"
                        else check_convoy_shape(n, tokens, flags)
                    ))
        check_fake("shared-drain/fake-gh.py", "shared-drain/fake-gh.py", check_gh_pr_shape)

    print("\nBehavior oracle replayed by the mutable fakes:")
    check_bd_behavior(real_runtime)

    if FAILURES:
        print(f"\nFAIL: {len(FAILURES)} fake tool shape(s) diverge from the real tool", file=sys.stderr)
        sys.exit(1)
    print("\nPASS: every declared fake matches the calibrated real-tool behavior oracle")


if __name__ == "__main__":
    main()
