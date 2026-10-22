"""What the criterion tests of the trace of the jobs share (C2a, af-k2rbw1;
Spec af-fgcw0d, user stories 130, 137, 138, 139, 145 and 175, Testing
Decisions 1, 5, 7 and 8). Not a test file: the criterion test files of the
trace load it, beside runs_destination.py.

What the datasets of the trace hold -- the job « Réaliser » of the run
« Recherche dans les notes » (started at 14:10, Paris), the D01 delivery
whose ticket the dispatch door dispatched in the synthetic city, and the
sessions sent its work -- is written here once, as the values the cases
verify:

- « Réaliser » (Alex, the author, +3 min 10 s → +6 min 5 s) had two
  sessions: demo-search-alex-1 (+3 min 10 s → +4 min 37 s, context observed
  27 %) and demo-search-alex-2 (+4 min 37 s → +6 min 5 s, context observed
  7 %), both on the provider codex, the model gpt-6.1-sol, the effort high,
  the tools read · rg · exec · write. Each was sent the same system prompt,
  SYSTEM_PROMPT, and its own user prompt: USER_PROMPT_1, USER_PROMPT_2. The
  trace of the second replays the records of the first at its head (it
  resumed the conversation). What the Factory declared for the author when
  its session took the ticket: the agent delivery-author on codex, the
  model gpt-6.1-sol.
- « Revue du code » (Léa, the reviewer, +6 min 5 s → +7 min 10 s) had one
  session, demo-search-lea-1, on claude, context observed 3 %: the
  supervisor reported neither its model nor its effort, and no prompt sent
  to it was recorded. What the Factory declared for the reviewer: the agent
  delivery-reviewer on claude, the model claude-opus-5-5.
- « Relire les tests » (Léa, +2 min 2 s → +2 min 57 s): no session is
  attributed to it.
- Noé: no session of his was observed.
- In what was recorded of demo-search-alex-2 are a secret and a private
  reasoning (SECRETS) that no collection keeps.

Nothing here reads the code of the cockpit: the page is read where the
browser renders it, or over HTTP as the cockpit serves it.
"""

from __future__ import annotations

import html
import re

from home_destination import fetch
from runs_destination import anchor, section

SYSTEM_PROMPT = (
    "# Auteur\n\n# Mission\nRéaliser sur le périmètre approuvé.\n\n# Règles\n"
    "- Utiliser les points d’entrée publics et les sources disponibles.\n"
    "- Conserver les mots du propriétaire ; ne pas inventer une preuve.\n"
    "- Signaler une donnée absente ou une limite.\n"
    "- Rendre un résultat lié à la version observée."
)
USER_PROMPT_2 = (
    "# Tâche\nImplémenter le périmètre approuvé du cockpit en conservant la boîte de réception. "
    "Utiliser les sources D01 existantes. Ne pas changer les portes de jugement. "
    "Fournir les preuves des critères au commit de sortie.\n\n"
    "# Contexte transmis\nWorkflow : Recherche dans les notes\nJob : Réaliser\nVersion : exemple synthétique\n\n"
    "# Résultat attendu\nUne observation et ses pièces, ou une limite explicite."
)
USER_PROMPT_1 = USER_PROMPT_2.replace("Version : exemple synthétique", "Version : exemple synthétique, première session")
# The version of each text sent: the first twelve digits of its SHA-256,
# written here as computed once from the texts above.
VERSIONS = {SYSTEM_PROMPT: "sha256:b71a0f18acad", USER_PROMPT_2: "sha256:de74c319c517",
            USER_PROMPT_1: "sha256:7f33c8e8d200"}
# In the trace of demo-search-alex-2, never collected: the value of a key
# in its environment, a token a tool printed, a private reasoning.
SECRETS = ("sk-proj-SYNTHETIQUE-ne-pas-collecter", "ghp_SYNTHETIQUEnepascollecter0000000000",
           "RAISONNEMENT-PRIVE-de-la-session")
NOT_COLLECTED = "non collecté"
# The addresses the cockpit serves that could carry what a collection kept.
SERVED = ("/runs", "/runs/run", "/runs/job", "/api/status", "/api/journal", "/api/health", "/api/requests",
          "/api/notifications")


def percent(value: int) -> re.Pattern:
    """« 7 % » and not the end of « 27 % »."""
    return re.compile(rf"(?<!\d){value}\s%")


def prompts(reading: dict) -> dict[str, list[dict]]:
    """The prompts listed in the section « Prompts envoyés » of the detail,
    by their kind (« Prompt système », « Prompt utilisateur »), in the order
    of the page: each its title, whether it is open, its rendered text, its
    whole text, and its raw text as drawn (`raw`, '' when the raw text is
    not shown)."""
    found = {}
    listed = section(reading, "Prompts envoyés")
    if listed is None:
        return found
    for block in reading["anchors"]:
        if block["tag"] != "details" or listed["name"] not in block["chain"]:
            continue
        title = next((a["content"] for a in reading["anchors"]
                      if a["tag"] == "summary" and a["chain"][:1] == [block["name"]]), "")
        kind = next((name for name in ("Prompt système", "Prompt utilisateur") if title.startswith(name)), None)
        if kind is None:
            continue
        raw = next((a for a in reading["anchors"] if a["tag"] == "pre" and block["name"] in a["chain"]), None)
        found.setdefault(kind, []).append({
            "title": title, "open": block["open"], "text": block["text"], "content": block["content"],
            "raw": raw["text"] if raw and raw["drawn"] else "",
        })
    return found


def line(text: str) -> str:
    """A text on one line, as the browser draws a raw text that wraps."""
    return " ".join(text.split())


def raw_texts(address: str, path: str) -> list[str]:
    """The texts of the page at `path` the cockpit serves as they are, in
    <pre> elements: the raw prompts, each exactly as it was sent."""
    code, _, body = fetch(address + path)
    assert code == 200, f"{path} answered {code}"
    return [html.unescape(found) for found in re.findall(r"<pre\b[^>]*>(.*?)</pre>", body, re.S)]


def served_text(address: str, path: str) -> str:
    code, _, body = fetch(address + path)
    assert code == 200, f"{path} answered {code}"
    return html.unescape(body)


def head_says(reading: dict) -> str:
    found = anchor(reading, "inspector-head")
    return found["text"] if found else ""
