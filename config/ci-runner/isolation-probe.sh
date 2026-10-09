#!/bin/bash
#
# What a job of the host's own runner must NOT be able to do, tried from
# inside the job (docs/SECURITY.md, "Factory CI on the host's own runner",
# af-r1ymfm). .github/workflows/ci.yml runs it first on that runner; every
# line must end "refused". It proves the box the runner puts a job in; it is
# not the box (a pull request can edit its own workflow).

set -u
bad=0
refused() { printf 'ok   refused: %s\n' "$1"; }
reached() { printf 'FAIL reached: %s\n' "$1"; bad=1; }

# The operator's files. Every home but the job's own: the operator's holds
# the live Factory, its runtime state (.gc, Beads) and his tokens.
others=$(ls -A /home 2>/dev/null | grep -vx "$(id -un)" || true)
if [ -n "$others" ]; then reached "/home holds: $others"; else refused "any home but the job's own"; fi
# The Windows disks, the runner's own state on the host, the container
# engines' sockets.
for path in /mnt/c /mnt/c/Users /mnt/wsl /var/lib/factory-ci /run/factory-ci-runner \
            /run/user/1000 /var/run/docker.sock /run/podman/podman.sock; do
  if ls -d "$path" >/dev/null 2>&1; then reached "$path exists in the job"; else refused "$path"; fi
done

# Root.
if command -v sudo >/dev/null 2>&1; then reached "sudo is installed"; else refused "sudo (not installed)"; fi
if [ "$(id -u)" = 0 ]; then reached "the job runs as root"; else refused "root (the job is $(id -un))"; fi
if su -c true root </dev/null >/dev/null 2>&1; then reached "su to root"; else refused "su to root"; fi

# The host's local services: Beads' Dolt server, the supervisor and its
# dashboard, the Cockpit, on the job's 127.0.0.1 and on the address that
# would lead to the host's.
gateway=$(ip route 2>/dev/null | awk '/^default/ {print $3; exit}')
for host in 127.0.0.1 ${gateway:-10.0.2.2} host.containers.internal host.docker.internal; do
  for port in 8372 8173 44632 22 3306; do
    if timeout 4 bash -c "exec 3<>/dev/tcp/$host/$port" 2>/dev/null; then
      reached "$host:$port answers"
    else
      refused "$host:$port"
    fi
  done
done

# The private networks around the host. A refusal here is the service's
# address filter or an empty address: both are fine; an answer is not.
for target in 192.168.0.1:80 192.168.1.1:80 192.168.1.1:53 172.17.0.1:22 100.100.100.100:53; do
  if timeout 4 bash -c "exec 3<>/dev/tcp/${target%:*}/${target#*:}" 2>/dev/null; then
    reached "$target answers"
  else
    refused "$target"
  fi
done

# The share of the PC: the job sees the cores it was given, not the host's.
cores=$(nproc)
if [ "$cores" -le 8 ]; then printf 'ok   %s cores for the job\n' "$cores"; else reached "$cores cores: the service's limit does not hold"; fi

if [ "$bad" = 0 ]; then echo "PASS: the job cannot reach the host"; else echo "FAIL: see the lines above" >&2; fi
exit "$bad"
