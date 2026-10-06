"""Freshness and Validity window (GLOSSARY.md), the cockpit's trust model.

A value the cockpit shows is FRESH (read within its source's Validity
window), STALE (an older last-known value exists, never presented as
current) or UNKNOWN (never read, or the source is failing). Spec
(af-oohx2x, Implementation Decisions): SSE gc 2 min, Beads 5 min, GitHub
10 min, rituals 1 h.
"""

FRESH = "fresh"
STALE = "stale"
UNKNOWN = "unknown"

VALIDITY_WINDOWS_SECONDS = {
    "gc": 120,
    "beads": 300,
    "github": 600,
    "rituals": 3600,
    "git": 600,
    # Computed from Beads: same window as Beads itself.
    "projets": 300,
}


def validity_window_for(source):
    try:
        return VALIDITY_WINDOWS_SECONDS[source]
    except KeyError:
        raise ValueError(
            "cockpit: no Validity window declared for source %r — add one "
            "to VALIDITY_WINDOWS_SECONDS instead of guessing" % (source,)
        )


def classify(read_at, now, validity_seconds, complete=True, failing_after_seconds=None):
    """Classify a reading taken at ``read_at`` (epoch seconds, or None).

    ``complete`` is False for a read that happened but cannot be trusted as
    current (gc's status answered while its event stream was silent): it
    never counts as a fresh snapshot — it classifies as STALE even though
    a read just happened.

    A source unread for longer than its Validity window plus
    ``failing_after_seconds`` (default: another full Validity window) is
    considered failing and reported UNKNOWN, same as never having been read
    (GLOSSARY.md Freshness: "unknown ... or its source is failing") — the
    fresh -> stale -> unknown progression a single source goes through as
    it stops responding.
    """
    if read_at is None:
        return UNKNOWN
    if failing_after_seconds is None:
        failing_after_seconds = validity_seconds
    age = max(0, now - read_at)
    if complete and age <= validity_seconds:
        return FRESH
    if age <= validity_seconds + failing_after_seconds:
        return STALE
    return UNKNOWN
