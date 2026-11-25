"""Did a `gc mail send --dedup <key>` land, whatever its sender answered?

A loaded host creates the message bead and then overruns the send's timeout
in the --notify wake: on 24/11/2026 `gc mail send --notify` took about 27 s
against factory-observe's 20 s, every resend timed out the same way, and the
route was called failed three passes in a row while its mail was in the
recipient's box (af-hlg74k). Resending under the same --dedup key
(af-usvfdb) cannot confirm a send that is slow every time; reading the
message back can. gc stamps the key on the bead (`mail.dedup_key`).

A timed-out send is lost only when this read finds no message with its key.
A read that fails or times out says nothing: the caller keeps the send
unconfirmed, as before.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from bounded_process import run as bounded_run

DEDUP_METADATA = "mail.dedup_key"
# Measured: a gc read costs about 4 s whatever it returns, and 15 s under a
# load of 15 (af-ufug19); this one took 2.6 to 3.7 s on 24/11/2026.
READ_TIMEOUT_SECONDS = 15.0


def mail_landed(gc_bin: str, dedup: str, *, timeout: float = READ_TIMEOUT_SECONDS, city: str | Path | None = None) -> bool:
    """True when a message carrying `dedup` exists, read, archived or not."""
    command = [gc_bin]
    if city:
        command += ["--city", str(city)]
    command += [
        "bd", "list", "--type", "message", "--all",
        "--metadata-field", f"{DEDUP_METADATA}={dedup}", "--limit", "0", "--json",
    ]
    try:
        result = bounded_run(
            command, cwd=str(city) if city else None,
            text=True, capture_output=True, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if result.returncode != 0:
        return False
    try:
        issues: Any = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return False
    # The key is checked again here: a reader that ignored the filter would
    # list every message, and any of them would count as this one.
    return isinstance(issues, list) and any(
        isinstance(issue, dict)
        and isinstance(issue.get("metadata"), dict)
        and issue["metadata"].get(DEDUP_METADATA) == dedup
        for issue in issues
    )
