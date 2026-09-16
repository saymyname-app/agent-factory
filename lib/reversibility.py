#!/usr/bin/env python3
"""Reversibility by default for schema changes (ADR-0019, af-l463).

ADR-0016 keeps escalation test 4 -- "cannot be undone inside the release" --
as part of the safety floor, and asks for it to fire less often by making
reversible changes the default. That only works if irreversibility is visible
before a merge rather than discovered after one.

It was not. docs/DELIVERY.md classifies Flyway changes as GUARDED, while the
merge actor arms every green pull request to `dev` -- migrations included.
Of the backend's eleven migrations, five would have been worth a second look:
two dropped columns (V4, V9), one deleted rows (V6), one rewrote a whole column
(V7) and one renamed columns (V8). V6 even explained itself in prose, which no
tool could read.

This module reads a unified diff and classifies every *new* migration. A writer
answers a finding with one comment line in the migration:

  -- rollback: db/rollback/R12__restore_x.sql   a companion script, added in the same PR
  -- reversible: <why>                           accepted for data rewrites and renames only
  -- irreversible: <why>                         an explicit test-4 escalation

Rules, per statement, after comments are stripped:

  schema_loss   DROP TABLE|SCHEMA|DATABASE|TYPE, ALTER ... DROP [COLUMN] x, TRUNCATE
  data_loss     DELETE
  data_rewrite  UPDATE, ALTER ... MODIFY [COLUMN], ALTER ... ALTER COLUMN ... TYPE
  rename        RENAME TABLE, ALTER ... RENAME, ALTER ... CHANGE [COLUMN]

  loss classes need `rollback:` or `irreversible:`;
  rewrite/rename also accept `reversible:`.

Editing or deleting a migration that already exists rewrites applied history
(Flyway checksums) and is never accepted.

Deliberately not mechanical: whether a behaviour change needs a flag. That
stays a review checklist item in docs/DELIVERY.md, and is stated as such.
"""
from __future__ import annotations

import re
from typing import Any

MIGRATION = re.compile(r"(^|/)db/migration/[^/]+\.sql$", re.I)
ROLLBACK_DIR = re.compile(r"(^|/)db/rollback/[^/]+\.sql$", re.I)

LOSS = {"schema_loss", "data_loss"}
SOFT = {"data_rewrite", "rename"}

# ALTER TABLE ... DROP <x>: these are recreatable schema objects, not data.
_DROP_SCHEMA_OBJECT = re.compile(
    r"^\s*drop\s+(index|constraint|foreign\s+key|primary\s+key|check|default|key|partition)\b", re.I)

_DECL = re.compile(r"^\s*--\s*(rollback|reversible|irreversible)\s*:\s*(.+?)\s*$", re.I | re.M)


def strip_sql_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    return "\n".join(line.split("--", 1)[0] for line in sql.splitlines())


def statements(sql: str) -> list[str]:
    return [s.strip() for s in strip_sql_comments(sql).split(";") if s.strip()]


def _alter_clauses(statement: str) -> list[str]:
    """The comma-separated action list of an ALTER TABLE statement."""
    m = re.match(r"^\s*alter\s+table\s+\S+\s+(.*)$", statement, re.I | re.S)
    if not m:
        return []
    parts, depth, current = [], 0, []
    for ch in m.group(1):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return [p.strip() for p in parts if p.strip()]


def classify_statement(statement: str) -> list[str]:
    s = " ".join(statement.split())
    low = s.lower()
    found: list[str] = []
    if re.match(r"^drop\s+(table|schema|database|type)\b", low):
        found.append("schema_loss")
    elif low.startswith("truncate"):
        found.append("schema_loss")
    elif low.startswith("delete"):
        found.append("data_loss")
    elif low.startswith("update"):
        found.append("data_rewrite")
    elif re.match(r"^rename\s+table\b", low):
        found.append("rename")
    elif low.startswith("alter table"):
        for clause in _alter_clauses(s):
            c = clause.lower()
            if c.startswith("drop"):
                if not _DROP_SCHEMA_OBJECT.match(c):
                    found.append("schema_loss")
            elif re.match(r"^(rename|change)\b", c):
                found.append("rename")
            elif re.match(r"^modify\b", c) or re.match(r"^alter\s+(column\s+)?\S+\s+(set\s+data\s+)?type\b", c):
                found.append("data_rewrite")
    return sorted(set(found))


def declarations(sql: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for kind, value in _DECL.findall(sql):
        out.setdefault(kind.lower(), value.strip())
    return out


def parse_diff(diff: str) -> list[dict[str, Any]]:
    """Files of a unified diff: path, status (added/modified/deleted/renamed), added text."""
    files: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            m = re.match(r"^diff --git a/(.+?) b/(.+)$", line)
            current = {"path": m.group(2) if m else line[11:], "old_path": m.group(1) if m else None,
                       "status": "modified", "added": []}
            files.append(current)
            continue
        if current is None:
            continue
        if line.startswith("new file mode"):
            current["status"] = "added"
        elif line.startswith("deleted file mode"):
            current["status"] = "deleted"
        elif line.startswith("rename from "):
            current["status"] = "renamed"
        elif line.startswith("+++ ") or line.startswith("--- "):
            continue
        elif line.startswith("+"):
            current["added"].append(line[1:])
    for f in files:
        f["text"] = "\n".join(f.pop("added"))
    return files


def assess(diff: str) -> dict[str, Any]:
    files = parse_diff(diff)
    present = {f["path"] for f in files if f["status"] in {"added", "modified", "renamed"}}
    findings: list[dict[str, Any]] = []
    for f in files:
        path = f["path"]
        touches_migration = MIGRATION.search(path) or (f.get("old_path") and MIGRATION.search(f["old_path"]))
        if not touches_migration:
            continue
        if f["status"] != "added":
            findings.append({
                "file": path, "verdict": "history_rewrite", "classes": [],
                "detail": (f"migration {f['status']}: an applied Flyway migration must never change "
                           "(its checksum is recorded); add a new V-migration instead"),
            })
            continue
        classes = sorted({c for st in statements(f["text"]) for c in classify_statement(st)})
        decl = declarations(f["text"])
        if not classes:
            findings.append({"file": path, "verdict": "ok", "classes": [], "detail": "additive only"})
            continue
        if "irreversible" in decl:
            findings.append({"file": path, "verdict": "irreversible", "classes": classes,
                             "detail": decl["irreversible"]})
            continue
        rollback = decl.get("rollback")
        if rollback:
            name = rollback.split()[0]
            if any(p.endswith(name) for p in present if ROLLBACK_DIR.search(p)):
                findings.append({"file": path, "verdict": "ok", "classes": classes,
                                 "detail": f"rollback provided: {name}"})
            else:
                findings.append({"file": path, "verdict": "needs_declaration", "classes": classes,
                                 "detail": (f"declares rollback {name!r} but no such file under "
                                            "db/rollback/ is added in this change")})
            continue
        if "reversible" in decl and not (set(classes) & LOSS):
            findings.append({"file": path, "verdict": "ok", "classes": classes,
                             "detail": f"declared reversible: {decl['reversible']}"})
            continue
        needs = ("`-- rollback: db/rollback/<file>.sql` (added in this change) or `-- irreversible: <why>`"
                 if set(classes) & LOSS else
                 "`-- reversible: <why>`, `-- rollback: db/rollback/<file>.sql` or `-- irreversible: <why>`")
        findings.append({"file": path, "verdict": "needs_declaration", "classes": classes,
                         "detail": f"{', '.join(classes)} without a declaration; add {needs}"})

    order = {"ok": 0, "needs_declaration": 1, "history_rewrite": 2, "irreversible": 3}
    verdict = max((f["verdict"] for f in findings), key=lambda v: order[v], default="ok")
    return {
        "contract": "agent-factory-reversibility/v1",
        "verdict": verdict,
        "migrations": len(findings),
        "findings": findings,
    }


EXIT = {"ok": 0, "needs_declaration": 3, "history_rewrite": 3, "irreversible": 4}


def render_comment(result: dict[str, Any]) -> str:
    """The PR comment: what was found and exactly what to do next."""
    head = {
        "needs_declaration": "### ⏸ Réversibilité : déclaration requise avant fusion",
        "history_rewrite": "### ⛔ Réversibilité : une migration déjà appliquée a été modifiée",
        "irreversible": "### 🛑 Réversibilité : changement déclaré irréversible — décision humaine requise",
    }[result["verdict"]]
    lines = [head, "",
             "_pr-autopilot n'arme pas la fusion automatique de cette PR "
             "(ADR-0019, test d'escalade 4 de l'ADR-0016)._", ""]
    for f in result["findings"]:
        if f["verdict"] == "ok":
            continue
        classes = f" ({', '.join(f['classes'])})" if f["classes"] else ""
        lines.append(f"- `{f['file']}` — **{f['verdict']}**{classes} : {f['detail']}")
    lines += ["", {
        "needs_declaration": ("Pour lever le blocage : rendre la migration réversible (motif expand/contract), "
                              "ou ajouter en tête l'une des déclarations indiquées. Le contrôle repasse "
                              "à chaque nouveau commit."),
        "history_rewrite": "Pour lever le blocage : restaurer la migration existante et ajouter une nouvelle migration V.",
        "irreversible": ("Cette PR ne sera pas fusionnée automatiquement. Le Mayor la met en attente et "
                         "soumet la décision à Benjamin avec la raison déclarée ; seule une fusion humaine "
                         "l'intègre."),
    }[result["verdict"]], "", "Référence : `docs/DELIVERY.md` › Réversibilité par défaut."]
    return "\n".join(lines)
