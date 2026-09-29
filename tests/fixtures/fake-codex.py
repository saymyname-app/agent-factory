#!/usr/bin/env python3
"""Fake `codex` for the sandbox harness (P10, af-ygibh).

Inert on purpose: `gc mail send --notify` (via escalation-door) starts the
configured named provider session on demand even with the reconciler off,
and without a stub that session execs the REAL codex CLI under a tmux
server -- a live, untorn-down process (live incident: an orphaned session
held the live escalation-door flock for 40+ min, root-caused 2026-09-28).
"""
import sys

sys.exit(0)
