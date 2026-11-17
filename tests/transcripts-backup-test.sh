#!/usr/bin/env bash
# bin/transcripts-backup keeps the transcripts past their tools' purge, copies
# no credential, and keeps its archive bounded (af-q55qqx.2).
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
tool=$here/bin/transcripts-backup
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }

export HOME=$tmp/home TRANSCRIPTS_BACKUP_ACCOUNT_HOME=$tmp/home
mkdir -p "$HOME"
dest=$tmp/archive/transcripts
export TRANSCRIPTS_BACKUP_DEST=$dest TRANSCRIPTS_BACKUP_MIN_FREE_GB=0
mkdir -p "$HOME/.claude/projects/p" "$HOME/.codex/sessions/2026/11/09"
echo '{"a":1}' > "$HOME/.claude/projects/p/s1.jsonl"
echo '{"b":1}' > "$HOME/.codex/sessions/2026/11/09/rollout.jsonl"
echo secret > "$HOME/.claude/.credentials.json"
echo secret > "$HOME/.codex/auth.json"
echo secret > "$HOME/.claude/projects/p/notes.txt"
echo '{"old":1}' > "$HOME/.codex/sessions/2026/11/09/old.jsonl"
touch -d '200 days ago' "$HOME/.codex/sessions/2026/11/09/old.jsonl"

"$tool" >/dev/null
[[ -f $dest/claude-projects/p/s1.jsonl ]] || fail "a Claude transcript is not copied"
[[ -f $dest/codex-sessions/2026/11/09/rollout.jsonl ]] || fail "a Codex transcript is not copied"
[[ ! -e $dest/codex-sessions/2026/11/09/old.jsonl ]] || fail "a transcript older than the retention is copied"
if grep -rq secret "$tmp/archive"; then fail "a non-transcript file is copied"; fi
[[ $(stat -c %a "$dest") == 700 && $(stat -c %a "$tmp/archive") == 700 ]] || fail "the archive is readable by others"

# The tool purges its source: the copy stays.
rm "$HOME/.claude/projects/p/s1.jsonl"
"$tool" >/dev/null
[[ -f $dest/claude-projects/p/s1.jsonl ]] || fail "the copy went with its purged source"

# Bounded: a copy unchanged for longer than the retention goes.
touch -d '100 days ago' "$dest/claude-projects/p/s1.jsonl"
out=$("$tool")
[[ ! -e $dest/claude-projects/p/s1.jsonl ]] || fail "an expired copy is kept"
[[ $out == *"1 expired after 90 days"* ]] || fail "the expiry is not reported: $out"

# A disk too full refuses, says so and copies nothing.
echo '{"c":1}' > "$HOME/.claude/projects/p/s2.jsonl"
if TRANSCRIPTS_BACKUP_MIN_FREE_GB=999999999 "$tool" 2>/dev/null; then fail "a full disk is not refused"; fi
[[ ! -e $dest/claude-projects/p/s2.jsonl ]] || fail "a refused run copied"

if "$tool" --bogus 2>/dev/null; then fail "an unknown option is accepted"; fi
echo "transcripts-backup-test: OK"
