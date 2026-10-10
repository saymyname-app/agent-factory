#!/usr/bin/env bash
# Sourced by a demonstration or a trial that must leave the Git repository of
# the live Factory as it found it (af-pw867q, T53).
#
# Comparing every reference before and after the run cannot say who moved
# one: another work tree, a fetch or the pruning of a merged branch moves the
# references of that repository during any run. What is watched here is what
# the run itself writes: every Git process started after
# `live_root_refs_watch` carries, in its environment only, a
# reference-transaction hook that logs each reference it creates, moves or
# deletes, with the repository it did it in. Nothing is written in the
# watched repository, and a process of another session does not carry the
# hook.
#
#   live_root_refs_watch HOLDER     start watching; HOLDER is a directory the
#                                   caller owns. Fails when the watch does not
#                                   see a reference written by a probe.
#   live_root_refs_written REPO     one line per reference of REPO's
#                                   repository (branch, tag or any other,
#                                   whatever the work tree) this run created
#                                   or moved (« set ») or deleted since the
#                                   watch started.

live_root_refs_watch() {
  local holder=$1 count=${GIT_CONFIG_COUNT:-0}
  mkdir -p "$holder/hooks" || return 1
  holder=$(cd "$holder" && pwd -P) || return 1
  : > "$holder/writes"
  cat > "$holder/hooks/reference-transaction" <<HOOK
#!/bin/sh
# Written by tests/lib/live-root-refs.sh: one line per committed reference
# update, « repository old new reference ».
[ "\$1" = committed ] || exit 0
repository=\$(cd "\$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" 2>/dev/null && pwd -P) || exit 0
while read -r old new ref; do
  printf '%s %s %s %s\n' "\$repository" "\$old" "\$new" "\$ref"
done >> "$holder/writes"
exit 0
HOOK
  chmod +x "$holder/hooks/reference-transaction"
  # The environment wins over the configuration of any repository or work
  # tree, and reaches only the processes this shell starts.
  export "GIT_CONFIG_KEY_$count=core.hooksPath" "GIT_CONFIG_VALUE_$count=$holder/hooks"
  export GIT_CONFIG_COUNT=$((count + 1))
  LIVE_ROOT_REFS_WRITES="$holder/writes"
  # A watch that sees nothing proves nothing: a probe repository must show.
  git init -q "$holder/probe" \
    && git -C "$holder/probe" -c user.name=probe -c user.email=probe@example.invalid commit -q --allow-empty -m probe \
    && grep -q "^$holder/probe/.git " "$holder/writes"
}

live_root_refs_written() {
  local repository where old new ref zero=0000000000000000000000000000000000000000
  repository=$(cd "$(git -C "$1" rev-parse --path-format=absolute --git-common-dir)" && pwd -P) || return 1
  while read -r where old new ref; do
    [ "$where" = "$repository" ] || continue
    case "$ref" in refs/*) ;; *) continue ;; esac
    # Git gives no old value for a forced update: created and moved read the
    # same. A deletion is two transactions (packed, then loose): one line.
    if [ "$new" = "$zero" ]; then echo "deleted $ref"
    else echo "set $ref to $new"; fi
  done < "$LIVE_ROOT_REFS_WRITES" | uniq
}
