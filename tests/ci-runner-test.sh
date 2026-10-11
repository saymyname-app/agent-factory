#!/usr/bin/env bash
# ci: every-run — it reads docs/DELIVERY.md to hold what an agent runs before a pull request: a change to that document alone must run it
#
# af-r1ymfm: Factory CI on the host's own runner (docs/OPERATIONS.md, "Factory
# CI on the host's own runner"; docs/SECURITY.md, same title). What is held
# here, without GitHub, Podman or root:
#   - the workflow goes to that runner only on the repository variable, as
#     one lot, and its first step there is the isolation probe;
#   - the service keeps the share of the PC Benjamin gave it and the job's
#     container gets nothing of the host;
#   - the broker hands one configuration per job, on the pipe only, and an
#     empty line when GitHub gives none;
#   - the runner's loop gives the configuration to the container on its
#     standard input, never on a command line;
#   - pause, resume and status say what bin/factory-doctor reads.

set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
CI="$ROOT/.github/workflows/ci.yml"
UNIT="$ROOT/config/ci-runner/factory-ci-runner.service"
LOOP="$ROOT/config/ci-runner/runner-loop"
RUNNER="$ROOT/bin/ci-runner"
fail() { echo "FAIL: $*" >&2; exit 1; }
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT

# --- the workflow ---------------------------------------------------------
grep -qF "runs-on: \${{ vars.FACTORY_CI_RUNNER == 'self-hosted' && 'factory-ci' || 'ubuntu-latest' }}" "$CI" \
  || fail "$CI: runs-on must be GitHub's runner unless the variable says self-hosted"
grep -qF "LOTS: \${{ vars.FACTORY_CI_RUNNER == 'self-hosted' && '1' || '4' }}" "$CI" \
  || fail "$CI: one lot on the host's runner (it takes one job at a time: more lots wait on each other for ever)"
grep -qF "fromJSON(vars.FACTORY_CI_RUNNER == 'self-hosted' && '[1]' ||" "$CI" \
  || fail "$CI: the matrix on the host's runner must be lot 1 alone"
probe_line=$(grep -n 'config/ci-runner/isolation-probe.sh' "$CI" | head -1 | cut -d: -f1)
tests_line=$(grep -n '^ *bin/ci-run-tests --shard' "$CI" | head -1 | cut -d: -f1)
[ -n "$probe_line" ] && [ "$probe_line" -lt "$tests_line" ] || fail "$CI: the isolation probe must run before the tests"
grep -qF "if: runner.environment == 'self-hosted'" <<<"$(grep -B2 'config/ci-runner/isolation-probe.sh' "$CI")" \
  || fail "$CI: the isolation probe runs on the host's runner only"
echo "ok   the workflow goes to the host's runner on the variable only, as one lot, probe first"

# --- the service ----------------------------------------------------------
grep -qxF 'Delegate=yes' "$UNIT" || fail "$UNIT lost Delegate=yes: Podman would move the job out of the service, and of every limit of it"
for line in 'User=factory-ci' 'AllowedCPUs=4-11' 'MemoryMax=4G' 'MemorySwapMax=512M' 'Nice=10' 'CPUWeight=20'; do
  grep -qxF "$line" "$UNIT" || fail "$UNIT lost '$line' (the share of the PC Benjamin gave CI, 2026-10-08; 8 cores since 2026-10-09)"
done
grep -qF 'if [ "$cores" -le 8 ]; then' "$ROOT/config/ci-runner/isolation-probe.sh" \
  || fail "the isolation probe no longer holds the job to the 8 cores of $UNIT"
grep -q '^IPAddressDeny=.*10\.0\.0\.0/8.*172\.16\.0\.0/12.*192\.168\.0\.0/16.*100\.64\.0\.0/10' "$UNIT" \
  || fail "$UNIT no longer closes the private networks to the job"
if grep -qE '^(User|Group)=root|^SupplementaryGroups=' "$UNIT"; then fail "$UNIT gives the runner root or an extra group"; fi
echo "ok   the service keeps 8 cores, 4 GB, low priority, and closes the private networks; the probe counts the cores"

run_line=$(grep -n '"\$PODMAN" run ' "$LOOP" | cut -d: -f1)
[ -n "$run_line" ] || fail "$LOOP no longer starts the job with podman run"
run=$(sed -n "${run_line},$((run_line + 3))p" "$LOOP")
grep -qF -- '--network slirp4netns:allow_host_loopback=false' <<<"$run" || fail "$LOOP: the job could reach the host's 127.0.0.1"
grep -qF -- '--cgroups=disabled' <<<"$run" || fail "$LOOP: the job would leave the service's limits"
grep -qF -- '--rm' <<<"$run" || fail "$LOOP: the job's container is not thrown away"
if grep -qE -- '(^| )(-v|--volume|--mount|--privileged|--pid|--userns|--security-opt|--cap-add|--device)( |=|$)' <<<"$run"; then
  fail "$LOOP mounts something of the host into the job or widens its rights: $run"
fi
if grep -qw sudo <<<"$(grep -v '^#' "$ROOT/config/ci-runner/Containerfile")"; then fail "the image installs sudo"; fi
echo "ok   the job's container is thrown away, mounts nothing of the host, has no way to its 127.0.0.1"

# --- an install that changes nothing of the recipe builds no image --------
# (af-uw246a: a build makes calls of wsl.exe from Windows hang.) The lines
# of root-install that copy the recipe, run here on two folders.
INSTALL="$ROOT/config/ci-runner/root-install"
copy=$(sed -n '/for recipe in Containerfile entrypoint.sh; do/,/^    done/p' "$INSTALL")
[ -n "$copy" ] || fail "$INSTALL no longer copies the recipe file by file"
if grep -qE 'install .*\$HERE/(Containerfile|entrypoint\.sh)' "$INSTALL"; then
  fail "$INSTALL copies the recipe whether it changed or not: every install would build the image again"
fi
mkdir "$T/here" "$T/lib"
echo one > "$T/here/Containerfile"; echo two > "$T/here/entrypoint.sh"
cp -p "$T/here/Containerfile" "$T/here/entrypoint.sh" "$T/lib/"
touch -d "2026-01-01 00:00" "$T/lib/Containerfile" "$T/lib/entrypoint.sh"
echo three > "$T/here/entrypoint.sh"
( HERE="$T/here" LIB="$T/lib"; eval "$copy" )
[ "$(date -r "$T/lib/Containerfile" +%Y)" = 2026 ] && [ "$(date -r "$T/lib/Containerfile" +%m%d)" = 0101 ] \
  || fail "an unchanged Containerfile lost its date: the image would be built again"
[ "$(cat "$T/lib/entrypoint.sh")" = three ] && [ "$(date -r "$T/lib/entrypoint.sh" +%m%d)" != 0101 ] \
  || fail "a changed entrypoint.sh was not installed with a new date"
echo "ok   an install copies the recipe only when it changed, so only then is the image built again"

# --- the weekly build keeps to the hours Benjamin chose --------------------
# (af-uw246a, 2026-10-09: 05:00-07:00.) A fake Podman whose image has the age
# the case gives, a fake clock, one turn of the loop: was a build started?
grep -qxF 'BUILD_HOURS=${FACTORY_CI_RUNNER_BUILD_HOURS:-5-7}' "$LOOP" \
  || fail "$LOOP: the weekly build of the image left the hours Benjamin chose (05:00-07:00, 2026-10-09)"
grep -qxF 'IMAGE_HARD_MAX_AGE_DAYS=${FACTORY_CI_RUNNER_IMAGE_HARD_MAX_AGE_DAYS:-14}' "$LOOP" \
  || fail "$LOOP: an image too old must be built at any hour after 14 days"
mkdir "$T/wbin" "$T/wrun"
cat > "$T/wbin/podman" <<'EOF'
#!/bin/bash
case "$1" in
  image)
    case "$2" in
      inspect) echo $(( $(date +%s) - FAKE_IMAGE_AGE_DAYS * 86400 - 60 )) ;;
      exists) exit 0 ;;
    esac ;;
  build) echo build >> "$FAKE_WLOG"; exit "${FAKE_BUILD_FAILS:-0}" ;;
  run) IFS= read -r _; echo run >> "$FAKE_WLOG"; date +%s%N > "$FAKE_WPID.since"
       sleep "${FAKE_RUN_SECONDS:-1.5}" & echo $! > "$FAKE_WPID"; wait ;;
  exec) case "${FAKE_JOB_RUNS:-0}" in
          1) echo busy ;; 0) echo idle ;;
          # The job arrives 2.5 s after the container started.
          # The loop's own look, run for real on this machine's processes.
          real) shift 2; exec "$@" ;;
          late) [ $(( ($(date +%s%N) - $(cat "$FAKE_WPID.since")) / 1000000 )) -ge 2500 ] && echo busy || echo idle ;;
          *) exit 125 ;;
        esac ;;
  kill) echo kill >> "$FAKE_WLOG"; kill "$(cat "$FAKE_WPID")" 2>/dev/null ;;
esac
exit 0
EOF
cat > "$T/wbin/curl" <<'EOF'
#!/bin/bash
echo '{"tag_name":"v9.9.9"}'
EOF
chmod +x "$T/wbin/podman" "$T/wbin/curl"
export FAKE_WLOG="$T/wlog" FAKE_WPID="$T/wpid"
one_turn() { # <age in days> <hour> -> the builds started
  : > "$FAKE_WLOG"
  PATH="$T/wbin:$PATH" FAKE_IMAGE_AGE_DAYS=$1 FACTORY_CI_RUNNER_HOUR=$2 FACTORY_CI_RUNNER_PODMAN="$T/wbin/podman" \
    FACTORY_CI_RUNNER_LIB="$T/nolib" FACTORY_CI_RUNNER_RUN_DIR="$T/wrun" FACTORY_CI_RUNNER_MAX_TURNS=1 \
    FACTORY_CI_RUNNER_LOOP_PAUSE=0.1 bash "$LOOP" > "$T/wloop.out" 2>&1
  grep -c build "$FAKE_WLOG" || true
}
[ "$(one_turn 8 14)" = 0 ] || fail "an image 8 days old was built at 14:00: outside 05:00-07:00 the old image serves"
[ "$(one_turn 8 4)" = 0 ]  || fail "an image 8 days old was built at 04:00, before the hours"
[ "$(one_turn 8 7)" = 0 ]  || fail "an image 8 days old was built at 07:00: the end of the hours is not in them"
[ "$(one_turn 8 5)" = 1 ]  || fail "an image 8 days old was not built at 05:00"
[ "$(one_turn 8 6)" = 1 ]  || fail "an image 8 days old was not built at 06:00"
[ "$(one_turn 1 5)" = 0 ]  || fail "an image one day old was built"
[ "$(one_turn 15 14)" = 1 ] || fail "an image 15 days old was not built at 14:00: past 14 days any hour is good"
echo "ok   an image that is only old is built between 05:00 and 07:00, at any hour past 14 days"

# A runner that only waits is stopped when the image comes due; one that
# serves a job is not; a build that failed is not tried again at once.
waiting_runner() { # <job: 0 none, 1 one runs, x the look fails, real the loop's own look> <build fails: 0|1> <hour> <seconds before a new try> -> what the fake Podman was asked, two turns
  : > "$FAKE_WLOG"; rm -f "$T/wrun/handoff"; mkfifo "$T/wrun/handoff"
  # One configuration per opening of the pipe by the loop, as the broker does.
  ( for _ in 1 2 3; do echo CONFIG > "$T/wrun/handoff"; sleep 0.3; done ) 2>/dev/null &
  feeder=$!
  PATH="$T/wbin:$PATH" FAKE_IMAGE_AGE_DAYS=8 FAKE_JOB_RUNS=$1 FAKE_BUILD_FAILS=$2 FACTORY_CI_RUNNER_HOUR=$3 \
    FACTORY_CI_RUNNER_BUILD_RETRY_SECONDS=$4 \
    FACTORY_CI_RUNNER_PODMAN="$T/wbin/podman" FACTORY_CI_RUNNER_LIB="$T/nolib" FACTORY_CI_RUNNER_RUN_DIR="$T/wrun" \
    FACTORY_CI_RUNNER_MAX_TURNS=2 FACTORY_CI_RUNNER_LOOP_PAUSE=0.1 FACTORY_CI_RUNNER_WATCH_PAUSE=0.1 \
    FACTORY_CI_RUNNER_DUE_CHECK_TICKS=3 timeout 20 bash "$LOOP" > "$T/wloop.out" 2>&1 || true
  kill "$feeder" 2>/dev/null || true; wait "$feeder" 2>/dev/null || true
  tr '\n' ' ' < "$FAKE_WLOG"
}
# The image stays due (the fake never gets younger) and a new try is allowed
# at once: the waiting runner is stopped, the image is built, twice over.
got=$(waiting_runner 0 0 5 0)
[ "$got" = "build run kill build run kill " ] || fail "in the hours, a runner that only waits must be stopped for the build: got '$got'"
grep -q 'the runner only waits: stopping it to build' "$T/wloop.out" || fail "the loop did not say why it stopped the waiting runner"
got=$(waiting_runner 1 0 5 0)
[ "$got" = "build run build run " ] || fail "a runner that serves a job must never be stopped for a build: got '$got'"
got=$(waiting_runner x 0 5 0)
[ "$got" = "build run build run " ] || fail "a look into the container that fails must stop nothing: got '$got'"
got=$(waiting_runner 0 1 5 3600)
[ "$got" = "build run run " ] || fail "a failed build must be tried once, then the old image serves without a new try within the hour: got '$got'"
got=$(waiting_runner 0 0 14 0)
[ "$got" = "run run " ] || fail "outside the hours a waiting runner must be left alone: got '$got'"
echo "ok   in the hours a runner that only waits is stopped for the build, one that serves a job never; a failed build waits an hour"

# The longest a job may run counts from the job, not from the container
# (af-rqovxb, 2026-10-09: a runner that had waited 1 h 41 lost its job after
# 18 minutes, and the pull request was rejected for it).
if grep -qF -- '--timeout' <<<"$run"; then fail "$LOOP: a limit on the container counts the wait for a job as the job's time"; fi
got=$(FACTORY_CI_RUNNER_JOB_MAX_SECONDS=0 waiting_runner 1 0 14 0)
[ "$got" = "run kill run kill " ] || fail "a job past its limit must be killed: got '$got'"
grep -q 'the job ran for more than 0 s: killing its container' "$T/wloop.out" || fail "the loop did not say why it killed the job"
got=$(FACTORY_CI_RUNNER_JOB_MAX_SECONDS=0 waiting_runner 0 0 14 0)
[ "$got" = "run run " ] || fail "a runner that only waits must never be killed by the job's limit: got '$got'"
got=$(FACTORY_CI_RUNNER_JOB_MAX_SECONDS=0 waiting_runner x 0 14 0)
[ "$got" = "run run " ] || fail "a look into the container that fails must not kill the job: got '$got'"
# A container 4 s old whose job took the last 1.5 s, limit 3 s.
got=$(FACTORY_CI_RUNNER_JOB_MAX_SECONDS=3 FAKE_RUN_SECONDS=4 waiting_runner late 0 14 0)
[ "$got" = "run run " ] || fail "a job that started after a wait must get its whole limit: got '$got'"
echo "ok   the job's limit counts from the job: a wait is never killed, nor a job for the wait before it"

# The look itself, not a fake's word for it (af-7i1q2r, 2026-10-09: it matched
# the shell that ran it, every runner read as busy, and a job 9 minutes old
# was killed 2 h after its container started). The fake Podman runs what the
# loop asks of the container on this machine's processes; the process a job
# starts has a name of this test's own, since the test can itself run in a job.
grep -qxF 'WORKER=${FACTORY_CI_RUNNER_WORKER:-Runner.Worker}' "$LOOP" \
  || fail "$LOOP no longer looks for Runner.Worker, the process GitHub's runner starts for a job"
worker="Job$RANDOM.Worker" # 15 characters at most: the kernel keeps no more of a process's name
got=$(FACTORY_CI_RUNNER_WORKER=$worker FACTORY_CI_RUNNER_JOB_MAX_SECONDS=0 waiting_runner real 0 14 0)
[ "$got" = "run run " ] || fail "the loop's own look read a runner that only waits as serving a job, and the job's limit killed it: got '$got'"
got=$(FACTORY_CI_RUNNER_WORKER=$worker waiting_runner real 0 5 0)
[ "$got" = "build run kill build run kill " ] || fail "the loop's own look did not read a waiting runner as waiting: it was not stopped for the build: got '$got'"
printf '#!/bin/bash\ntrap '"'"'kill $! 2>/dev/null; exit'"'"' TERM EXIT\nsleep 60 & wait\n' > "$T/wbin/$worker"
chmod +x "$T/wbin/$worker"
"$T/wbin/$worker" & job=$!
for _ in $(seq 50); do [ "$(cat "/proc/$job/comm" 2>/dev/null)" = "$worker" ] && break; sleep 0.1; done
got=$(FACTORY_CI_RUNNER_WORKER=$worker FACTORY_CI_RUNNER_JOB_MAX_SECONDS=0 waiting_runner real 0 14 0)
got_due=$(FACTORY_CI_RUNNER_WORKER=$worker waiting_runner real 0 5 0)
kill "$job" 2>/dev/null || true; wait "$job" 2>/dev/null || true
[ "$got" = "run kill run kill " ] || fail "the loop's own look did not see the job's process: a job past its limit was not killed: got '$got'"
[ "$got_due" = "build run build run " ] || fail "the loop's own look did not see the job's process: a runner serving a job was stopped for a build: got '$got_due'"
echo "ok   the loop's own look, on real processes: a runner that only waits reads as waiting, one whose job runs as serving it"

# --- the broker and the loop, end to end with a fake GitHub and Podman ----
mkdir "$T/bin" "$T/run" "$T/state"
cat > "$T/bin/gh" <<'EOF'
#!/bin/bash
echo "gh $*" >> "$FAKE_LOG"
case "$*" in
  "repo view"*) echo "acme/factory" ;;
  *"select(.busy"*) echo "${FAKE_BUSY:-1}" ;;
  *generate-jitconfig*)
    n=$(cat "$FAKE_COUNT" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "$FAKE_COUNT"
    if [ "$n" = 2 ]; then exit 1; fi
    echo "SECRET-CONFIG-$n" ;;
  *"actions/runners"*DELETE*|*DELETE*"actions/runners"*) ;;
  *"actions/runners"*) echo 41 ;;
esac
EOF
cat > "$T/bin/podman" <<'EOF'
#!/bin/bash
case "$1" in
  image) [ "$2" = inspect ] && date +%s; exit 0 ;;
  run) IFS= read -r config; echo "podman-run argv: $*" >> "$FAKE_LOG"; echo "podman-run stdin: $config" >> "$FAKE_PODMAN_STDIN" ;;
esac
exit 0
EOF
chmod +x "$T/bin/gh" "$T/bin/podman"
export FAKE_LOG="$T/log" FAKE_COUNT="$T/count" FAKE_PODMAN_STDIN="$T/stdin"
: > "$FAKE_LOG"

FACTORY_ROOT="$ROOT" FACTORY_CI_RUNNER_RUN_DIR="$T/run" FACTORY_CI_RUNNER_GH="$T/bin/gh" \
  FACTORY_CI_RUNNER_BROKER_TURNS=3 FACTORY_CI_RUNNER_BROKER_PAUSE=0.2 "$RUNNER" broker > "$T/broker.out" 2>&1 &
broker=$!
for _ in $(seq 1 50); do [ -p "$T/run/handoff" ] && break; sleep 0.1; done
[ -p "$T/run/handoff" ] || fail "the broker did not create the hand-off pipe: $(cat "$T/broker.out")"
FACTORY_CI_RUNNER_RUN_DIR="$T/run" FACTORY_CI_RUNNER_PODMAN="$T/bin/podman" FACTORY_CI_RUNNER_MAX_TURNS=3 \
  FACTORY_CI_RUNNER_LOOP_PAUSE=0.2 FACTORY_CI_RUNNER_EMPTY_PAUSE=0.2 bash "$LOOP" > "$T/loop.out" 2>&1 &
loop=$!
for _ in $(seq 1 150); do kill -0 "$loop" 2>/dev/null || break; sleep 0.2; done
kill "$loop" "$broker" 2>/dev/null || true; wait "$loop" "$broker" 2>/dev/null || true

[ "$(cat "$T/count")" = 3 ] || fail "the broker asked GitHub for $(cat "$T/count") configuration(s) for 3 turns of the loop: one per job, never in advance"
[ "$(grep -c '' "$T/stdin")" = 2 ] || fail "2 of 3 hand-offs carried a configuration, the loop started $(grep -c '' "$T/stdin" 2>/dev/null) container(s): $(cat "$T/loop.out")"
grep -qx 'podman-run stdin: SECRET-CONFIG-1' "$T/stdin" && grep -qx 'podman-run stdin: SECRET-CONFIG-3' "$T/stdin" \
  || fail "the container did not receive the configuration on its standard input"
grep -q 'handed nothing over' "$T/loop.out" || fail "the loop did not say that GitHub gave nothing on the second turn"
if grep -q 'SECRET-CONFIG' "$T/log" "$T/loop.out" "$T/broker.out"; then
  fail "a runner configuration reached a command line or a log"
fi
[ "$(stat -c %a "$T/run/handoff")" = 640 ] || fail "the hand-off pipe is not 640"
grep -q 'DELETE.*actions/runners/41\|actions/runners/41.*DELETE' "$T/log" || fail "the broker left an offline runner of ours registered"
echo "ok   one configuration per job, on the pipe and the container's standard input only; none when GitHub gives none"

# --- status, pause, resume ------------------------------------------------
cat > "$T/bin/systemctl" <<'EOF'
#!/bin/bash
echo "systemctl $*" >> "$FAKE_LOG"
user=0; [ "$1" = --user ] && { user=1; shift; }
case "$1" in
  is-active) if [ "$user" = 1 ]; then cat "$FAKE_BROKER"; else cat "$FAKE_SERVICE"; fi ;;
  cat) if [ "$user" = 1 ]; then [ "$(cat "$FAKE_BROKER")" != absent ]; else [ "$(cat "$FAKE_SERVICE")" != absent ]; fi ;;
  stop) echo inactive > "$FAKE_BROKER" ;;
  start) echo active > "$FAKE_BROKER" ;;
esac
EOF
chmod +x "$T/bin/systemctl"
export FAKE_BROKER="$T/broker.state" FAKE_SERVICE="$T/service.state"
ci_runner() {
  FACTORY_ROOT="$ROOT" FACTORY_CI_RUNNER_RUN_DIR="$T/run" FACTORY_CI_RUNNER_STATE_DIR="$T/state" \
    FACTORY_CI_RUNNER_GH="$T/bin/gh" FACTORY_CI_RUNNER_SYSTEMCTL="$T/bin/systemctl" "$RUNNER" "$@"
}
verdict() { ci_runner status --local --json | jq -r .verdict; }

echo absent > "$FAKE_SERVICE"; echo absent > "$FAKE_BROKER"
[ "$(verdict)" = absent ] || fail "no runner installed must read 'absent', got $(verdict)"
echo active > "$FAKE_SERVICE"; echo active > "$FAKE_BROKER"
[ "$(verdict)" = ok ] || fail "service and broker active must read 'ok', got $(verdict)"
echo failed > "$FAKE_SERVICE"
[ "$(verdict)" = down ] || fail "a failed service must read 'down', got $(verdict)"
ci_runner status --local --json | jq -e '.fix_hint | test("mode github")' >/dev/null || fail "a runner down must name the way back to GitHub's runners"
echo active > "$FAKE_SERVICE"; echo inactive > "$FAKE_BROKER"
[ "$(verdict)" = down ] || fail "a stopped broker must read 'down', got $(verdict)"

echo active > "$FAKE_BROKER"
ci_runner pause >/dev/null
[ "$(verdict)" = paused ] || fail "after pause the verdict must be 'paused', got $(verdict)"
[ ! -e "$T/run/stop-now" ] || fail "pause without --now must let the running job end"
ci_runner resume >/dev/null
FAKE_BUSY=0 ci_runner pause >/dev/null
[ -e "$T/run/stop-now" ] || fail "pause must stop a runner that only waits: it would take the next job"
ci_runner resume >/dev/null
ci_runner pause --now >/dev/null
[ -e "$T/run/stop-now" ] || fail "pause --now must tell the loop to kill the running job"
ci_runner resume >/dev/null
[ ! -e "$T/run/stop-now" ] && [ "$(verdict)" = ok ] || fail "resume must clear the pause, got $(verdict)"
echo "ok   status says absent, ok, down or paused; pause --now stops the job, resume clears it"

# --- `mode` alone: what an agent asks before a pull request ---------------
# (docs/DELIVERY.md, "What to run before a pull request": Benjamin, 2026-10-08, « A. »)
cat > "$T/bin/gh-mode" <<'EOF'
#!/bin/bash
case "$*" in
  "repo view"*) echo "acme/factory" ;;
  *actions/variables/FACTORY_CI_RUNNER*) [ "$FAKE_MODE" = error ] && exit 1; echo "$FAKE_MODE" ;;
esac
EOF
chmod +x "$T/bin/gh-mode"
mode() { FAKE_MODE=$1 FACTORY_ROOT="$ROOT" FACTORY_CI_RUNNER_GH="$T/bin/gh-mode" "$RUNNER" mode; }
[ "$(mode self-hosted)" = self-hosted ] || fail "mode must print self-hosted when the variable says so"
[ "$(mode '')" = github ] || fail "mode must print github when the variable is not set"
[ "$(mode error)" = github ] || fail "mode must print github when GitHub gives no clear answer: in doubt the whole battery runs"
FORMULA="$ROOT/formulas/mol-do-work.formula.toml"
# Since the repository is public a red run is billed nothing on GitHub's
# runners either (Benjamin, 2026-10-11, « oui »): the light check is the rule
# and the formula no longer sends a delivery through the whole battery.
grep -qF 'bin/ci-run-tests --rule-checks --changed-since' "$FORMULA" || fail "$FORMULA lost the rule checks and touched tests before a pull request"
if grep -qF 'bin/ci-run-tests --jobs 4' "$FORMULA"; then fail "$FORMULA still asks for the whole battery before a pull request: 14 minutes on the host for a red that is billed nothing"; fi
grep -qF '| The same | GitHub'"'"'s runners on a private repository: billed. Not the case today | The whole battery' "$ROOT/docs/DELIVERY.md" || fail "docs/DELIVERY.md no longer says when the whole battery comes back: where a red run is billed"
echo "ok   before a pull request: the rule checks and the touched tests; the whole battery only where a red run is billed"

# --- the loop obeys stop-now ----------------------------------------------
: > "$T/run/stop-now"; : > "$T/stdin"
FACTORY_CI_RUNNER_RUN_DIR="$T/run" FACTORY_CI_RUNNER_PODMAN="$T/bin/podman" FACTORY_CI_RUNNER_MAX_TURNS=2 \
  FACTORY_CI_RUNNER_LOOP_PAUSE=0.1 bash "$LOOP" > "$T/loop2.out" 2>&1
[ ! -s "$T/stdin" ] || fail "the loop started a job while stop-now was set"
echo "ok   nothing starts while the runner is stopped by hand"

printf 'PASS: Factory CI on the host runs one boxed job at a time, on the variable only\n'
