"""Persists the notify engine's dedup state across a cockpit restart
(spec af-oohx2x §"Notifications": "état « envoyé » persisté (survit au
redémarrage du cockpit)"). A plain JSON file -- the engine's whole state
is a handful of timestamps per open request, nowhere near needing a real
database.
"""
import json
import os


class JsonFileStateStore:
    def __init__(self, path):
        self._path = path

    def load(self):
        try:
            with open(self._path) as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def save(self, state):
        directory = os.path.dirname(self._path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        tmp_path = self._path + ".tmp"
        with open(tmp_path, "w") as fh:
            json.dump(state, fh)
        os.replace(tmp_path, self._path)


class InMemoryStateStore:
    """A test constructs one of these fresh per case; a real cockpit
    process always passes a :class:`JsonFileStateStore` instead (wiring
    into ``cockpit.core.process`` is a later ticket's job, same precedent
    as the T18 heartbeat emitter)."""

    def __init__(self, initial=None):
        self._state = dict(initial or {})

    def load(self):
        return dict(self._state)

    def save(self, state):
        self._state = dict(state)
