#!/usr/bin/env python3
"""Fake `bd` for the sandbox harness (P10, af-ygibh). See fake-gc.py."""
import sys

sys.stderr.write(
    "fake bd: no canned response configured for: bd %s\n"
    "put a more specific `bd` stub earlier on PATH for this test.\n"
    % " ".join(sys.argv[1:])
)
sys.exit(1)
