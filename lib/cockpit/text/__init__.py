"""Operator Language text control (spec af-oohx2x, "Compréhensible sans IA").

Two sources of French, zero tokens at render time: fixed phrases in code
for machine events, and fields written by the producing agent in the
Operator Language. :mod:`cockpit.text.validate` is the pure-code control on
the second kind — no identifier pattern, no internal term outside the
Cockpit Lexicon, a maximum line length, required fields present.
"""
