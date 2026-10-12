"""Controller observations of launch recipes; no author report or verdict."""
import hashlib
import json
import socket
import subprocess
from pathlib import Path


def command(argv):
    proc = subprocess.run([str(v) for v in argv], capture_output=True, text=True, timeout=90)
    return {"command": [str(v) for v in argv], "exit_code": proc.returncode,
            "output": proc.stdout, "stderr": proc.stderr}


def connects(port):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=1):
            return True
    except OSError:
        return False


def listeners():
    # Observe existing local listeners, never send a mutation to a real service.
    ports = set()
    for row in Path('/proc/net/tcp').read_text().splitlines()[1:]:
        fields = row.split()
        host, port = fields[1].split(':')
        if fields[3] == '0A' and host in ('0100007F', '00000000'):
            port = int(port, 16)
            if connects(port):
                ports.add(port)
    return ports


def alive(pid):
    try:
        return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0] != 'Z'
    except FileNotFoundError:
        return False



def processes_in(worktree):
    found = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            cwd = (proc / 'cwd').readlink()
            argv = (proc / 'cmdline').read_bytes().split(b'\0')
            belongs = str(cwd).startswith(str(worktree) + '/') or str(cwd) == str(worktree)
            belongs = belongs or any(arg.decode(errors='replace').startswith(str(worktree) + '/') for arg in argv)
            if belongs and alive(int(proc.name)):
                found.append(int(proc.name))
        except (OSError, ProcessLookupError):
            continue
    return sorted(found)


def observe(bin_dir, repo, profile, commit, launch_state, references):
    """Exercise public commands from an independent clean copy at the ticket tip.

    The existing launched product supplies the evaluation identity and a clean
    author-equivalent Git context. An additional product is disposable for stop.
    Outputs retain failed observations; the independent Evaluator judges them.
    """
    primary = json.loads(Path(launch_state).read_text())
    tree = Path(primary['worktree'])
    declared = json.loads(Path(profile).read_text())['launch']
    result = {'commit': commit, 'dataset': primary['dataset'], 'references': [],
              'screens': declared.get('screens', []), 'entry_points': declared.get('entry_points', [])}
    before = listeners()
    # Keep the trial record beside the preparation: a killed observation is
    # reaped on the next pass, never confused with a reusable dataset product.
    state = Path(launch_state).with_suffix('.trial')
    if state.exists():
        raise ValueError('an interrupted lifecycle trial still needs cleanup')
    argv = [bin_dir / 'project-launch', '--repo-root', repo, 'start', profile,
            '--commit', commit, '--dataset', primary['dataset'], '--state-file', state]
    started = command(argv)
    lifecycle = {'start': started, 'existing_ports_before': sorted(before)}
    result['lifecycle'] = lifecycle
    try:
        if state.exists():
            trial = json.loads(state.read_text())
            lifecycle.update(address=trial['address'], commit=trial['commit'], pid=trial['pid'])
            lifecycle['port_open_before_stop'] = connects(trial['port'])
            lifecycle['processes_before_stop'] = processes_in(trial['worktree'])
            lifecycle['stop'] = command([bin_dir / 'project-launch', 'stop', '--state-file', state])
            lifecycle['process_alive_after_stop'] = alive(trial['pid'])
            lifecycle['processes_after_stop'] = sorted(set(processes_in(trial['worktree'])) |
                {pid for pid in lifecycle['processes_before_stop'] if alive(pid)})
            lifecycle['port_open_after_stop'] = connects(trial['port'])
    finally:
        if state.exists():
            command([bin_dir / 'project-launch', 'stop', '--state-file', state])
    lifecycle['existing_ports_after'] = sorted(p for p in before if connects(p))
    lifecycle['lost_existing_ports'] = sorted(before - set(lifecycle['existing_ports_after']))
    # Read only published reference identities; do not consult private planning
    # profiles, author reports, source diffs or the author's dirty checkout.
    for reference in references:
        ref = {k: reference[k] for k in ('commit', 'path', 'states')}
        ref['anchors'] = command([bin_dir / 'prototype-conformance', 'anchors', '--repo', tree,
                                  '--commit', ref['commit'], '--path', ref['path'],
                                  '--states', ','.join(ref['states'])])
        manifest = command(['git', '-C', tree, 'show', f"{ref['commit']}:{ref['path']}/validated-prototype.json"])
        ref['datasets'] = []
        try:
            states = {s['id']: s for s in json.loads(manifest['output'])['states']}
            for name in ref['states']:
                source = subprocess.run(['git', '-C', str(tree), 'show',
                    f"{ref['commit']}:{ref['path']}/{states[name]['dataset']}"], capture_output=True, timeout=10)
                path = (tree / declared['datasets'][name]).resolve()
                if not path.is_relative_to(tree.resolve()):
                    raise ValueError('dataset outside clean checkout')
                actual = path.read_bytes()
                ref['datasets'].append({'state': name, 'source_read': source.returncode == 0,
                    'reference_digest': hashlib.sha256(source.stdout).hexdigest(),
                    'launched_digest': hashlib.sha256(actual).hexdigest(),
                    'identical': source.returncode == 0 and source.stdout == actual})
        except (ValueError, OSError, KeyError, TypeError) as exc:
            ref['error'] = str(exc)
        result['references'].append(ref)
    return result
