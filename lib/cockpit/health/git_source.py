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
