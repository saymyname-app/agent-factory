#!/usr/bin/env python3
# ci: local-only — requires the installed gc/bd/gh runtime, not just the fakes
"""Fakes must refuse what the real tool refuses (af-kiy7lm).

Every test in this suite runs against fakes of gc/bd/gh instead of the real
tools (P10, af-ygibh). A fake that accepts a command shape the real tool
rejects turns a broken script green: four safety nets broke silently this
way (af-sa2i1: `gc bd create --set-metadata`, a flag `bd create` has never
had; af-4ruvv/af-1isbx: order/close-path regressions a too-permissive fake
would also have missed; and `gh pr update-branch`, absent from the gh 2.45
installed on this host, see tests/gh-unsupported-subcommand-guard-test.sh).

This test extracts every (subcommand, flag) shape the declared-scope fakes
under tests/fixtures actually accept, then checks each shape against the
installed real tool's own --help/usage text. It is local-only because it
needs the real gc/bd/gh binaries on PATH, which CI runners do not have.

A shape the real tool accepts can still mean something else than the fake
makes of it (T48, af-1zxao6: `bd create --deps blocks:<id>` makes <id> wait
for the new issue, and the fake stored nothing, so a door that posed every
edge backwards stayed green). So the stateful fake `bd` of the publication
door is also run beside the real `bd`, in a disposable city that shares
nothing with the live Factory: the same dependency commands, then the same
question -- which issue waits for which.
"""
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
PUBLISH_FAKE_BD = FIXTURES / "ticket-graph-publish" / "bd-bead-mode"


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


def check_bd_dependency_direction():
    """The fake `bd` of the publication door and the real one pose each
    dependency the same way round."""
    trial = Path(tempfile.mkdtemp(prefix="af-1zxao6-fake-bd-contract."))
    try:
        # Nothing of the live Factory may reach this city.
        env = {k: v for k, v in os.environ.items()
               if not re.match(r"^(GC_|BEADS_|BD_BIN$|GH_BIN$|FACTORY_ROOT$)", k)}
        env.update(HOME=str(trial / "home"), TMUX_TMPDIR=str(trial / "tmux"))
        for directory in ("home", "tmux"):
            (trial / directory).mkdir()
        city = trial / "city"
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
        fake_env = {**env, "TICKET_GRAPH_BD_STATE": str(trial / "fake-beads.json")}
        for shape, (create_args, followups) in DEPENDENCY_SHAPES.items():
            try:
                real = dependency_edges(["bd"], env, city, create_args, followups)
                fake = dependency_edges([str(PUBLISH_FAKE_BD)], fake_env, trial, create_args, followups)
            except RuntimeError as exc:
                fail(f"ticket-graph-publish/bd-bead-mode, `bd {shape}`: {exc}")
                continue
            if real != fake:
                fail(f"ticket-graph-publish/bd-bead-mode, `bd {shape}`: the real bd shows the edges {real} "
                     f"(issue that waits, the other, type) and the fake shows {fake}")
            else:
                print(f"  bd {shape}: {real}")
    finally:
        # The city's managed Dolt server outlives `gc init`; its command line
        # carries the trial directory, and nothing else does.
        subprocess.run(["pkill", "-f", "--", str(trial) + "/"], capture_output=True)
        subprocess.run(["sleep", "1"])
        subprocess.run(["pkill", "-9", "-f", "--", str(trial) + "/"], capture_output=True)
        shutil.rmtree(trial, ignore_errors=True)


def main():
    print("Recording installed real tool versions:")
    print(" ", real_version("gc", "version"))
    print(" ", real_version("bd", "--version"))
    print(" ", real_version("gh", "--version"))
    print(" ", real_version("codex", "--version"))
    print(" ", real_version("claude", "--version"))
    print()

    for name in ("gc", "bd", "gh"):
        if not (ROOT / "tests" / "fixtures" / f"fake-{name}.py").exists():
            fail(f"missing base fixture fake-{name}.py")

    check_fake("shared-drain/fake-gc.py bd-shapes",
                "shared-drain/fake-gc.py",
                lambda n, tokens, flags: (
                    check_bd_shape(n, tokens, flags) if tokens[0] == "bd"
                    else check_convoy_shape(n, tokens, flags)
                ))
    check_fake("shared-drain/fake-gh.py", "shared-drain/fake-gh.py", check_gh_pr_shape)

    print("\nDependency direction, real bd beside the publication door's fake:")
    check_bd_dependency_direction()

    if FAILURES:
        print(f"\nFAIL: {len(FAILURES)} fake tool shape(s) diverge from the real tool", file=sys.stderr)
        sys.exit(1)
    print("\nPASS: every checked fake command shape matches the installed real tool")


if __name__ == "__main__":
    main()
