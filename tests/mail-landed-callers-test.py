#!/usr/bin/env python3
"""A Python tool that bounds a `gc mail send` by a timeout reads the mail back
before it calls it lost (af-hlg74k, docs/DEFECT_CLASSES.md S.mail-landed).
Scripts are named here without their directory: this file only reads them.

On 2026-11-24 `gc mail send --notify` took about 27 s against factory-observe's
20 s on every pass: the mail was in the recipient's box, the route was called
failed three passes in a row and the order factory-watchdog failed five times
in three hours. Resending under the same --dedup key (af-usvfdb) cannot
confirm a send that is slow every time. A file of bin/ or lib/ that sends mail
under a timeout sends it with --dedup and calls `mail_landed`
(lib/mail_landed.py), or is listed below with the reason it does not.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEND = re.compile(r"""["']mail["'],\s*["']send["']""")
TIMEOUT = re.compile(r"\btimeout=")
# Not a lost mail: a timed-out wake counts as sent and keeps its cooldown,
# by choice (tests/idle-ready-work-wake-test.py); af-oj3rnv weighs reading
# it back instead.
COUNTED_SENT = {"idle-ready-work-wake"}


def python_tools() -> list[Path]:
    files = sorted((ROOT / "lib").glob("*.py"))
    for path in sorted((ROOT / "bin").iterdir()):
        if path.is_file():
            try:
                first = path.read_text(encoding="utf-8").split("\n", 1)[0]
            except UnicodeDecodeError:
                continue
            if "python" in first:
                files.append(path)
    return files


def offends(text: str) -> bool:
    return bool(SEND.search(text)) and bool(TIMEOUT.search(text)) and "mail_landed(" not in text


class MailLandedCallers(unittest.TestCase):
    def test_every_timed_mail_send_reads_its_mail_back(self):
        offenders = [
            path.name for path in python_tools()
            if path.name not in COUNTED_SENT and offends(path.read_text(encoding="utf-8"))
        ]
        self.assertEqual([], offenders)

    def test_the_check_sees_a_timed_send_that_does_not_read_back(self):
        timed = 'bounded_run([GC, "mail", "send", "mayor"], timeout=20)'
        self.assertTrue(offends(timed))
        self.assertFalse(offends(timed + "\nmail_landed(GC, key)"))
        self.assertFalse(offends('run([GC, "mail", "send", "mayor"])'))


if __name__ == "__main__":
    unittest.main()
