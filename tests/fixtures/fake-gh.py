#!/usr/bin/env python3
"""Fake `gh` for the sandbox harness (P10, af-ygibh). See fake-gc.py."""
import sys

sys.stderr.write(
    "fake gh: no canned response configured for: gh %s\n"
    "put a more specific `gh` stub earlier on PATH for this test.\n"
    % " ".join(sys.argv[1:])
)
sys.exit(1)
