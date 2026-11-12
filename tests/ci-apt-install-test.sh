#!/usr/bin/env bash
#
# af-xcdibe: an outage of the Ubuntu package source no longer turns a Factory
# CI check red. On 2026-11-11 the four runs of PR #859 failed on `apt-get
# install bubblewrap`, « Temporary failure resolving
# azure.archive.ubuntu.com », over more than an hour, with nothing wrong in
# the change. bin/ci-apt-install falls back to the main archive, then to the
# copy kept in config/ci-apt-kept/.
#
# Category control (docs/DEFECT_CLASSES.md, S): every apt-get of the
# workflows goes through bin/ci-apt-install, and every kept copy matches its
# SHA256SUMS.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
TOOL="$REPO_ROOT/bin/ci-apt-install"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

# A fake apt-get: logs each call, and answers from the files under $TMP/down
# (a source named there does not answer). A call with Dir::Etc::SourceParts
# reads the fallback copy, and logs the hosts that copy names.
mkdir -p "$TMP/bin"
cat >"$TMP/bin/apt-get" <<'EOF'
#!/usr/bin/env bash
source=runner parts=
for a in "$@"; do
  case "$a" in Dir::Etc::SourceParts=*) source=fallback parts=${a#*=} ;; esac
done
hosts=
[ -n "$parts" ] && hosts=$(grep -ho '://[a-z.]*/' "$parts"/* | sort -u | tr '\n' ' ')
echo "apt-get $source ${*: -1} hosts=$hosts" >>"$FAKE_LOG"
[ ! -e "$FAKE_DOWN/$source" ]
EOF
cat >"$TMP/bin/dpkg" <<'EOF'
#!/usr/bin/env bash
[ "$1" = --print-architecture ] && { echo amd64; exit 0; }
echo "dpkg $*" >>"$FAKE_LOG"
EOF
chmod +x "$TMP/bin/apt-get" "$TMP/bin/dpkg"

# Each case: the runner's sources (GitHub's Azure mirror) and a kept copy.
setup() {
  rm -rf "$TMP/case"
  mkdir -p "$TMP/case/etc/sources.list.d" "$TMP/case/kept" "$TMP/case/down"
  printf 'Types: deb\nURIs: http://azure.archive.ubuntu.com/ubuntu/\nSuites: noble\n' \
    >"$TMP/case/etc/sources.list.d/ubuntu.sources"
  echo deb >"$TMP/case/kept/bubblewrap_1.0_amd64.deb"
  (cd "$TMP/case/kept" && sha256sum bubblewrap_1.0_amd64.deb >SHA256SUMS)
  : >"$TMP/case/log"
}
run() {
  PATH="$TMP/bin:$PATH" FAKE_LOG="$TMP/case/log" FAKE_DOWN="$TMP/case/down" \
    CI_APT_SUDO= CI_APT_ETC="$TMP/case/etc" CI_APT_KEPT_DIR="$TMP/case/kept" \
    "$TOOL" "$@" >"$TMP/case/out" 2>&1
}

setup
run bubblewrap || fail "a source that answers: $(cat "$TMP/case/out")"
grep -q 'apt-get runner bubblewrap' "$TMP/case/log" || fail "the runner's sources were not used: $(cat "$TMP/case/log")"
grep -q 'fallback\|dpkg' "$TMP/case/log" && fail "fell back while the runner's sources answered"
echo "ok   the runner's sources answer: installed from them, nothing else tried"

setup
touch "$TMP/case/down/runner"
run bubblewrap || fail "mirror down, archive up: $(cat "$TMP/case/out")"
grep -q 'apt-get fallback bubblewrap hosts=://archive.ubuntu.com/ $' "$TMP/case/log" \
  || fail "the fallback did not read the main archive alone: $(cat "$TMP/case/log")"
grep -q 'azure' "$TMP/case/etc/sources.list.d/ubuntu.sources" || fail "the runner's own sources file was modified"
grep -q dpkg "$TMP/case/log" && fail "the kept copy was used while the main archive answered"
echo "ok   the runner's mirror is down: installed from archive.ubuntu.com, the runner's files untouched"

setup
touch "$TMP/case/down/runner" "$TMP/case/down/fallback"
run bubblewrap || fail "both sources down, a kept copy: $(cat "$TMP/case/out")"
grep -q "dpkg -i $TMP/case/kept/bubblewrap_1.0_amd64.deb" "$TMP/case/log" \
  || fail "the kept copy was not installed: $(cat "$TMP/case/log")"
echo "ok   no source answers: installed from the kept copy"

setup
touch "$TMP/case/down/runner" "$TMP/case/down/fallback"
echo tampered >"$TMP/case/kept/bubblewrap_1.0_amd64.deb"
run bubblewrap && fail "a kept copy that does not match its SHA256SUMS was accepted"
grep -q dpkg "$TMP/case/log" && fail "a tampered kept copy was installed"
grep -q 'does not match its SHA256SUMS' "$TMP/case/out" || fail "no word of the checksum: $(cat "$TMP/case/out")"
echo "ok   a kept copy that does not match its SHA256SUMS is refused"

setup
touch "$TMP/case/down/runner" "$TMP/case/down/fallback"
run bubblewrap apparmor && fail "a package with no kept copy passed while no source answered"
grep -q '::error::.*keeps no amd64 copy of: apparmor\..*not the change' "$TMP/case/out" \
  || fail "the error does not name the package and the source: $(cat "$TMP/case/out")"
grep -q dpkg "$TMP/case/log" && fail "installed half of what was asked"
echo "ok   no source and no kept copy: red, naming the package and the package source"

# The category: every apt-get of the workflows goes through the tool.
raw=$(grep -nE '(^|[^-])apt-get( |$)|apt install' "$REPO_ROOT"/.github/workflows/*.yml || true)
[ -z "$raw" ] || fail "an apt-get in a workflow bypasses bin/ci-apt-install (af-xcdibe):
$raw"
echo "ok   no workflow calls apt-get outside bin/ci-apt-install"

# Every kept copy is the package its name says, and matches its checksum.
KEPT="$REPO_ROOT/config/ci-apt-kept"
(cd "$KEPT" && sha256sum -c --quiet SHA256SUMS) || fail "config/ci-apt-kept/ does not match its SHA256SUMS"
for d in "$KEPT"/*.deb; do
  grep -qF "  ${d##*/}" "$KEPT/SHA256SUMS" || fail "${d##*/} has no line in SHA256SUMS"
  if command -v dpkg-deb >/dev/null; then
    name=${d##*/}
    [ "$(dpkg-deb -f "$d" Package)_$(dpkg-deb -f "$d" Version)_$(dpkg-deb -f "$d" Architecture).deb" = "$name" ] \
      || fail "$name is not the package its name says"
  fi
done
echo "ok   every kept copy matches its SHA256SUMS and its name"

echo "OK ci-apt-install: an outage of the package source is not a red check"
