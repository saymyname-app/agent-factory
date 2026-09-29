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
"""
import re
import subprocess
import sys
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

    if FAILURES:
        print(f"\nFAIL: {len(FAILURES)} fake tool shape(s) diverge from the real tool", file=sys.stderr)
        sys.exit(1)
    print("\nPASS: every checked fake command shape matches the installed real tool")


if __name__ == "__main__":
    main()
