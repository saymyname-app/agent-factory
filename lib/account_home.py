"""The home of the account, read from the password database, not from $HOME.

Gas City runs the exec check of a formula step (`[steps.check.check]`) with
HOME set to the city root, to keep the check out of the controller's home
(gastownhall/gascity, internal/convergence/condition.go). A tool that check
reaches and that finds the account's state under $HOME looks under the city
root, where nothing is: the work tree of a ticket (af-r35155), the evidence
store (af-i4d833). Every Factory tool finds the account's state from here;
tests/account-home-lint-test.py refuses the other forms (af-e84s74).

A test isolates a tool by the tool's own override (EVIDENCE_STORE_DIR,
TICKET_AUTHOR_WORKTREES_DIR, ...), not by HOME, which this ignores.
"""

from __future__ import annotations

import os
import pwd
from pathlib import Path


def account_home() -> Path:
    try:
        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    except KeyError:  # a uid without an entry, as in a bare container
        return Path.home()
