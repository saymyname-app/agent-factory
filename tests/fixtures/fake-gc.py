#!/usr/bin/env python3
"""Fake `gc` for the sandbox harness (P10, af-ygibh).

Refuses every call by default, loudly, instead of silently doing nothing: a
test that forgets to put a scenario-specific stub earlier on PATH should see
a clear "no canned response" failure, not a false green from a no-op that
happened to exit 0.
"""
import sys

sys.stderr.write(
    "fake gc: no canned response configured for: gc %s\n"
    "put a more specific `gc` stub earlier on PATH for this test.\n"
    % " ".join(sys.argv[1:])
)
sys.exit(1)
