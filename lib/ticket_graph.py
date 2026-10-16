"""The shape of a ticket graph: the longest chain of blocked_by, the links
another chain already implies, and the levels of the graph.

One computation for the graph review's critical-path bound (bin/graph-review,
af-i4w79r, ADR-0031) and for the live view of a convoy (bin/convoy-graph).
`waits` maps each ticket key to the keys it waits for, every one of them a
key of `waits`; a cycle (refused at publication) ends the chain where it
loops."""

from __future__ import annotations


def chains(waits: dict[str, list[str]]) -> dict[str, list[str]]:
    """For each ticket, the longest chain of blocked_by that ends with it."""
    chain: dict[str, list[str]] = {}

    def longest(key: str) -> list[str]:
        if key not in chain:
            chain[key] = [key]  # a cycle ends here
            chain[key] = max((longest(b) for b in waits[key]), key=len, default=[]) + [key]
        return chain[key]

    return {key: longest(key) for key in waits}


def critical_path(waits: dict[str, list[str]]) -> list[str]:
    """The longest chain of the graph; the first one in the order of
    `waits` when several are as long."""
    found = chains(waits)
    return max((found[key] for key in waits), key=len, default=[])


def implied_links(waits: dict[str, list[str]]) -> list[tuple[str, str]]:
    """The links (blocker, ticket) another chain already implies:
    transitively redundant."""
    def reaches(start: str, goal: str, skip: str) -> bool:
        stack, seen = [b for b in waits[start] if b != skip], set()
        while stack:
            current = stack.pop()
            if current == goal:
                return True
            if current not in seen:
                seen.add(current)
                stack.extend(waits[current])
        return False

    return [(b, key) for key, blockers in waits.items() for b in blockers if reaches(key, b, b)]


def levels(waits: dict[str, list[str]]) -> dict[int, list[str]]:
    """The tickets per level: level 1 waits for nothing, level n for at
    least one ticket of level n-1. The number of levels is the length of
    the critical path; the size of a level is how many authors it can keep
    busy at once."""
    by_level: dict[int, list[str]] = {}
    for key, chain in chains(waits).items():
        by_level.setdefault(len(chain), []).append(key)
    return dict(sorted(by_level.items()))
