#!/usr/bin/env python3
"""Black-box comparison of pinned design-skill copies against local upstream repos."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin/design-skills-check"


def run(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True)


def git(path, *args):
    result = run("git", *args, cwd=path)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


with tempfile.TemporaryDirectory(prefix="af-design-skills-check-") as tmp:
    base = Path(tmp)
    upstream = base / "sources" / "sample"
    upstream.mkdir(parents=True)
    git(upstream, "init", "-q")
    git(upstream, "config", "user.name", "Fixture")
    git(upstream, "config", "user.email", "fixture@example.test")
    (upstream / "LICENSE").write_text("Fixture licence\n")
    skill = upstream / "skills" / "sample"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: sample\n---\n\nFollow the design brief.\n")
    (skill / "reference.md").write_text("Use the project's theme.\n")
    (skill / "scripts").mkdir()
    (skill / "scripts" / "engine").write_text("never copy me\n")
    git(upstream, "add", ".")
    git(upstream, "commit", "-qm", "fixture")
    commit = git(upstream, "rev-parse", "HEAD")

    vendor = base / "vendor"
    local_skill = vendor / "sample"
    local_skill.mkdir(parents=True)
    note = base / "note.md"
    note.write_text("Factory adaptation: engine absent; use prose only.\n\n")
    original = (skill / "SKILL.md").read_text()
    marker = "---\n\n"
    assert marker in original
    (local_skill / "SKILL.md").write_text(original.replace(marker, marker + note.read_text(), 1))
    shutil.copy2(skill / "reference.md", local_skill / "reference.md")
    license_copy = base / "LICENSES" / "sample.txt"
    license_copy.parent.mkdir()
    shutil.copy2(upstream / "LICENSE", license_copy)
    manifest = base / "manifest.json"
    manifest.write_text(json.dumps({
        "upstreams": {"sample": {"repo": str(upstream), "commit": commit,
                                  "license": "LICENSES/sample.txt"}},
        "skills": [{"upstream": "sample", "source": "skills/sample",
                    "destination": "sample", "exclude": ["scripts"],
                    "note": "note.md"}],
    }))
    env = os.environ | {"DESIGN_SKILLS_CHECK_MANIFEST": str(manifest),
                        "DESIGN_SKILLS_CHECK_VENDOR_ROOT": str(vendor),
                        "DESIGN_SKILLS_CHECK_SOURCE_ROOT": str(base / "sources")}

    def check():
        return subprocess.run([str(CLI), "compare"], env=env, text=True, capture_output=True)

    result = check()
    assert result.returncode == 0, result.stdout + result.stderr
    assert commit in result.stdout
    assert not (local_skill / "scripts").exists(), "the engine must stay absent"

    (local_skill / "reference.md").write_text("drift\n")
    result = check()
    assert result.returncode != 0 and "reference.md" in result.stderr
    shutil.copy2(skill / "reference.md", local_skill / "reference.md")

    (local_skill / "extra.md").write_text("untracked addition\n")
    result = check()
    assert result.returncode != 0 and "extra.md" in result.stderr
    (local_skill / "extra.md").unlink()

    rogue = vendor / "rogue"
    rogue.mkdir()
    (rogue / "SKILL.md").write_text("unselected skill\n")
    result = check()
    assert result.returncode != 0 and "rogue" in result.stderr
    shutil.rmtree(rogue)

    license_copy.unlink()
    result = check()
    assert result.returncode != 0 and "LICENSES/sample.txt" in result.stderr

live = run(str(CLI), "compare")
assert live.returncode == 0, live.stdout + live.stderr

print("PASS: pinned design-skill subset, adapted note, drift and licence checks")
