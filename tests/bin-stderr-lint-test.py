#!/usr/bin/env python3
"""Lint: bin/ scripts must not drop the stderr of a failed gc/bd/gh call.

A failed gc/bd/gh call whose stderr is redirected to /dev/null (or merged
and discarded) and whose exit status is also discarded (`|| true`, or
Python `check=False` with no captured output) fails silently: nobody sees
why, and no bead/log records it. That exact shape broke pr-autopilot on
2026-09-28 (af-4ruvv) and is the reason af-kiy7lm hardens the fakes and
adds this lint together -- a fake cannot catch a bug a human only notices
by reading dropped stderr.

This does not flag every `2>/dev/null` in bin/: capturing stdout while
discarding diagnostic stderr, with the exit status (or emptiness of the
captured output) checked by the caller, is a normal and common idiom in
this codebase (existence/dedup queries that treat "no output" as "not
found", a safe default). The narrow, always-wrong shape this flags is
BOTH the exit status AND the diagnostic text discarded at once, so a
failure is invisible in every direction.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "bin"

TOOL_WORD = r"\b(?:gc|bd|gh)\b"

# Bash: a gc/bd/gh invocation whose stderr is silenced (2>/dev/null, or
# 2>&1 immediately followed by a redirect of the merged stream to
# /dev/null) and whose own exit status is also thrown away with `|| true`
# on the same logical (semicolon-joined, backslash-continued) statement.
BASH_OFFENDER_RE = re.compile(
    TOOL_WORD + r"[^\n;]*?"
    r"(?:2>/dev/null|>/dev/null[^\n;]*?2>&1|2>&1[^\n;]*?>/dev/null)"
    r"[^\n;]*?\|\|\s*true\b"
)

# Python: a subprocess call naming gc/bd/gh with check=False and neither
# capture_output=True nor an explicit stdout=/stderr= pipe in the same
# call -- so a failure's diagnostic text is not even available to log.
PY_CALL_RE = re.compile(r"subprocess\.(?:run|call|check_call|check_output|Popen)\(", re.MULTILINE)


def find_bash_offenders(path: Path, text: str):
    offenders = []
    # Join backslash-continued lines so a statement split across lines is
    # still seen as one logical line by BASH_OFFENDER_RE.
    joined = re.sub(r"\\\n[ \t]*", " ", text)
    for lineno, line in enumerate(joined.splitlines(), start=1):
        if BASH_OFFENDER_RE.search(line):
            offenders.append((lineno, line.strip()))
    return offenders


def matching_paren(text: str, open_idx: int) -> int:
    depth = 0
    i = open_idx
    while i < len(text):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def find_python_offenders(path: Path, text: str):
    offenders = []
    for m in PY_CALL_RE.finditer(text):
        open_idx = m.end() - 1
        close_idx = matching_paren(text, open_idx)
        if close_idx == -1:
            continue
        call_text = text[m.start():close_idx + 1]
        if not re.search(TOOL_WORD, call_text):
            continue
        if "check=False" not in call_text:
            continue
        if "capture_output" in call_text or "stderr=" in call_text:
            continue
        lineno = text.count("\n", 0, m.start()) + 1
        offenders.append((lineno, call_text.splitlines()[0].strip()))
    return offenders


def main():
    offenders = []
    for path in sorted(BIN.iterdir()):
        if not path.is_file():
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        first_line = text.splitlines()[0] if text else ""
        if "python" in first_line:
            for lineno, snippet in find_python_offenders(path, text):
                offenders.append((path.relative_to(ROOT), lineno, snippet))
        else:
            for lineno, snippet in find_bash_offenders(path, text):
                offenders.append((path.relative_to(ROOT), lineno, snippet))

    if offenders:
        print(f"FAIL: {len(offenders)} bin/ site(s) drop gc/bd/gh stderr on failure:", file=sys.stderr)
        for relpath, lineno, snippet in offenders:
            print(f"  {relpath}:{lineno}: {snippet}", file=sys.stderr)
        sys.exit(1)

    print("PASS: no bin/ script drops the stderr of a failed gc/bd/gh call")


if __name__ == "__main__":
    main()
