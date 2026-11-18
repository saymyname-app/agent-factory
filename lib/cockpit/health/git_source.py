"""Reads how many commits the live root is behind its promotion branch
(spec .66: "l'usine tourne une version en retard de N commits"). A thin
subprocess wrapper, like core/beads_source.py, so a test can point
``git_bin``/``repo_dir`` at a disposable fixture repo instead of the live
root (AGENTS.md: never edited in the live root; never a test that reaches
it).
"""
import subprocess


def count_commits_behind(repo_dir, remote="origin", branch="main", git_bin="git", timeout=10):
    """Commits reachable from ``<remote>/<branch>`` that HEAD does not have.

    A plain ``rev-list`` against the local remote-tracking ref would read a
    stale answer forever — that ref only moves on an explicit fetch, so this
    fetches first (spec .4: "git fetch périodique, sans token"; this poller
    is that periodic fetch)."""
    subprocess.run(
        [git_bin, "-C", repo_dir, "fetch", "--quiet", remote, branch],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
    )
    completed = subprocess.run(
        [git_bin, "-C", repo_dir, "rev-list", "--count", "HEAD..%s/%s" % (remote, branch)],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
    )
    return int(completed.stdout.strip())


def head_revision(repo_dir, git_bin="git", timeout=10):
    """The commit checked out in ``repo_dir``, or None when it cannot be read.

    Read once at start, it is the revision this process runs: the live root
    moves on, the process keeps what it imported until restarted
    (af-q55qqx.7)."""
    if not repo_dir:
        return None
    import bounded_process  # lib/, on the path bin/cockpit sets

    try:
        completed = bounded_process.run(
            [git_bin, "-C", repo_dir, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip() or None
