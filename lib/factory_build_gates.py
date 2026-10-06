#!/usr/bin/env python3
"""Keep formula exec-check paths materialised from the resolved pack.

Gas City resolves an exec check relative to the target rig. Pack assets are
not copied into that rig automatically, so a formula can compile correctly and
still fail before the check starts. This module discovers the formula sources
that Gas City actually resolved, deduplicates their exec-check paths, and
materialises containment-safe per-rig copies plus their tracked dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tomllib
from typing import Any


MANAGED_PREFIX = ".gc/scripts/"
MANIFEST_RELATIVE = ".gc/scripts/.factory-build-gates.json"
# Name of the city root's own store in reports; a rig cannot be named so.
CITY_STORE = "(city root)"
MANIFEST_VERSION = 1


class BuildGateError(RuntimeError):
    """The resolved formula/check configuration could not be inspected."""


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise BuildGateError(f"cannot read {path}: {exc}") from exc


def configured_rigs(root: Path) -> list[tuple[str, Path]]:
    city = _load_toml(root / "city.toml")
    rigs: list[tuple[str, Path]] = []
    for raw in city.get("rigs", []):
        if not isinstance(raw, dict) or not raw.get("name"):
            continue
        name = str(raw["name"])
        configured_path = raw.get("path")
        path = Path(str(configured_path)) if configured_path else root / "rigs" / name
        if not path.is_absolute():
            path = root / path
        rigs.append((name, path))
    return rigs


def resolved_formulas(root: Path, gc_bin: str, rig_name: str | None) -> list[tuple[str, Path]]:
    # Formula layers are resolved in rig context. Querying only at city scope
    # can silently materialise every rig from the default pack even when one
    # rig pins a different pack version or contributes rig-local formulas.
    # The city scope (no rig) is queried only for the city root's own store.
    command = [gc_bin, "formula", "list", "--city", str(root)]
    if rig_name is not None:
        command += ["--rig", rig_name]
    command.append("--json")
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BuildGateError(f"cannot run {' '.join(command)}: {exc}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise BuildGateError(f"gc formula list failed ({completed.returncode}): {detail}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise BuildGateError(f"gc formula list returned invalid JSON: {exc}") from exc

    formulas = payload.get("formulas", []) if isinstance(payload, dict) else []
    result: list[tuple[str, Path]] = []
    for raw in formulas:
        if not isinstance(raw, dict) or not raw.get("name") or not raw.get("source"):
            continue
        result.append((str(raw["name"]), Path(str(raw["source"]))))
    if not result:
        raise BuildGateError("gc formula list returned no resolved formulas")
    return result


def _exec_check_paths(value: Any, inside_check: bool = False) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        if inside_check and value.get("mode") == "exec" and isinstance(value.get("path"), str):
            found.add(value["path"])
        for key, child in value.items():
            found.update(_exec_check_paths(child, inside_check or key == "check"))
    elif isinstance(value, list):
        for child in value:
            found.update(_exec_check_paths(child, inside_check))
    return found


def formula_check_paths(
    formulas: list[tuple[str, Path]],
) -> tuple[dict[str, set[str]], dict[str, set[Path]], set[Path], set[str]]:
    """Return references, pack sources, pack dirs, and link-only dependencies."""
    references: dict[str, set[str]] = {}
    sources: dict[str, set[Path]] = {}
    pack_script_dirs: set[Path] = set()
    link_dependencies: set[str] = set()
    for name, source in formulas:
        pack_scripts = source.parent.parent / "assets" / "scripts"
        if pack_scripts.is_dir():
            pack_script_dirs.add(pack_scripts)
        for check_path in _exec_check_paths(_load_toml(source)):
            references.setdefault(check_path, set()).add(name)
            if check_path.startswith(MANAGED_PREFIX):
                candidate = pack_scripts / check_path.removeprefix(MANAGED_PREFIX)
                if candidate.is_file():
                    sources.setdefault(check_path, set()).add(candidate)

    # A city-owned formula can override a pack formula while continuing to use
    # the pack's check contract. In that case its source has no adjacent
    # assets/ directory, so resolve the same relative asset from the other
    # active pack layers returned by `gc formula list`.
    for check_path in references:
        if not check_path.startswith(MANAGED_PREFIX) or sources.get(check_path):
            continue
        suffix = check_path.removeprefix(MANAGED_PREFIX)
        for script_dir in pack_script_dirs:
            candidate = script_dir / suffix
            if candidate.is_file():
                sources.setdefault(check_path, set()).add(candidate)

    # The pack's build-artifact shell gate executes this validator through
    # "$SCRIPT_DIR/../validate_build_artifact.py". Because the shell gate is
    # invoked from its rig-local copy, the companion must be materialised at
    # the corresponding rig-local path as well; copying only the shell script
    # would turn the old lstat failure into a later "validator not found".
    build_gate = ".gc/scripts/checks/build-artifact-valid.sh"
    validator = ".gc/scripts/validate_build_artifact.py"
    if build_gate in references:
        references[validator] = {
            f"{name} (build-artifact-valid dependency)" for name in references[build_gate]
        }
        link_dependencies.add(validator)
        for script_dir in pack_script_dirs:
            candidate = script_dir / "validate_build_artifact.py"
            if candidate.is_file():
                sources.setdefault(validator, set()).add(candidate)

    return references, sources, pack_script_dirs, link_dependencies


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_path(rig_root: Path) -> Path:
    return rig_root / MANIFEST_RELATIVE


def _load_manifest(rig_root: Path) -> dict[str, dict[str, Any]]:
    path = _manifest_path(rig_root)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildGateError(f"cannot read managed-copy manifest {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("version") != MANIFEST_VERSION:
        raise BuildGateError(f"managed-copy manifest {path} has an unsupported format")
    files = payload.get("files")
    if not isinstance(files, dict) or not all(
        isinstance(key, str) and isinstance(value, dict) for key, value in files.items()
    ):
        raise BuildGateError(f"managed-copy manifest {path} has an invalid files map")
    return files


def _write_manifest(rig_root: Path, files: dict[str, dict[str, Any]]) -> None:
    path = _manifest_path(rig_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    payload = {"version": MANIFEST_VERSION, "files": files}
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists() or temporary.is_symlink():
            temporary.unlink()


def _source_record(source: Path, strategy: str) -> dict[str, Any]:
    return {
        "source": str(source.resolve()),
        "sha256": _sha256(source),
        "mode": stat.S_IMODE(source.stat().st_mode),
        "strategy": strategy,
    }


def _is_pack_asset_symlink(target: Path, check_path: str) -> bool:
    if not target.is_symlink():
        return False
    try:
        linked = Path(os.readlink(target))
    except OSError:
        return False
    if not linked.is_absolute():
        linked = target.parent / linked
    resolved_parts = linked.resolve(strict=False).parts
    suffix_parts = Path(check_path.removeprefix(MANAGED_PREFIX)).parts
    expected_tail = ("assets", "scripts", *suffix_parts)
    return len(resolved_parts) >= len(expected_tail) and tuple(
        resolved_parts[-len(expected_tail) :]
    ) == expected_tail


def _same_symlink(target: Path, source: Path) -> bool:
    if not target.is_symlink():
        return False
    try:
        linked = Path(os.readlink(target))
    except OSError:
        return False
    if not linked.is_absolute():
        linked = target.parent / linked
    return linked.resolve(strict=False) == source.resolve(strict=False)


def _replace_file(target: Path, source: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.factory-build-gates-{os.getpid()}")
    try:
        if temporary.exists() or temporary.is_symlink():
            temporary.unlink()
        shutil.copy2(source, temporary)
        os.replace(temporary, target)
    finally:
        if temporary.exists() or temporary.is_symlink():
            temporary.unlink()


def _replace_symlink(target: Path, source: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.factory-build-gates-{os.getpid()}")
    try:
        if temporary.exists() or temporary.is_symlink():
            temporary.unlink()
        os.symlink(str(source.resolve()), temporary)
        os.replace(temporary, target)
    finally:
        if temporary.exists() or temporary.is_symlink():
            temporary.unlink()


def reconcile(root: Path, gc_bin: str, check_only: bool) -> tuple[list[str], list[str], int, int]:
    rigs = configured_rigs(root)
    fixes: list[str] = []
    problems: list[str] = []
    unique_paths: set[str] = set()

    # A work bead of the city itself lives in the city root's store, and Gas
    # City runs its exec checks from there. The city root is not a rig, so it
    # is reconciled as one more store, for the checks the city owns
    # (assets/scripts/ beside its formulas/) and nothing else: pack gates are
    # for rigs.
    city_scripts = root / "assets" / "scripts"
    stores: list[tuple[str, Path, str | None]] = [(name, path, name) for name, path in rigs]
    if city_scripts.is_dir():
        stores.append((CITY_STORE, root, None))

    for rig_name, rig_root, scope in stores:
        if not rig_root.is_dir():
            problems.append(f"rig '{rig_name}' root is missing: {rig_root}")
            continue

        formulas = resolved_formulas(root, gc_bin, scope)
        references, direct_sources, pack_script_dirs, link_dependencies = formula_check_paths(
            formulas
        )
        if scope is None:
            references = {
                check_path: names
                for check_path, names in references.items()
                if any(city_scripts in source.parents for source in direct_sources.get(check_path, ()))
            }
        unique_paths.update(references)
        try:
            managed_files = _load_manifest(rig_root)
        except BuildGateError as exc:
            problems.append(f"rig '{rig_name}' {exc}")
            continue
        manifest_changed = False
        for check_path in sorted(references):
            formula_names = ", ".join(sorted(references[check_path]))
            target = Path(check_path)
            if not target.is_absolute():
                target = rig_root / target

            if not check_path.startswith(MANAGED_PREFIX):
                if not target.is_file() or not os.access(target, os.X_OK):
                    problems.append(
                        f"rig '{rig_name}' missing executable {check_path} "
                        f"(formulas: {formula_names})"
                    )
                continue

            candidates = set(direct_sources.get(check_path, set()))
            if not candidates:
                suffix = check_path.removeprefix(MANAGED_PREFIX)
                candidates = {
                    path / suffix for path in pack_script_dirs if (path / suffix).is_file()
                }
            executable = sorted(path for path in candidates if os.access(path, os.X_OK))
            if not executable:
                problems.append(
                    f"rig '{rig_name}' cannot resolve pack source for {check_path} "
                    f"(formulas: {formula_names})"
                )
                continue
            candidate_digests = {_sha256(path) for path in executable}
            if len(candidate_digests) > 1:
                problems.append(
                    f"rig '{rig_name}' resolved conflicting pack sources for {check_path}: "
                    + ", ".join(str(path) for path in executable)
                )
                continue
            source = executable[0]
            strategy = "symlink" if check_path in link_dependencies else "copy"
            source_record = _source_record(source, strategy)
            managed_record = managed_files.get(check_path)

            # build-artifact-valid.sh locates its Python validator beside the
            # shell gate. The validator in turn locates schemas relative to
            # its real pack path, so this dependency must remain a link to the
            # pack. It is not a formula check path and is therefore not passed
            # through Gas City's containment resolver; the formula-facing
            # shell gate itself is always a regular file copy below.
            if strategy == "symlink":
                if _same_symlink(target, source):
                    if managed_record == source_record:
                        continue
                    if check_only:
                        problems.append(
                            f"rig '{rig_name}' unmanaged dependency {check_path}; "
                            "target is correct but no current refresh record exists"
                        )
                        continue
                    managed_files[check_path] = source_record
                    manifest_changed = True
                    fixes.append(
                        f"rig '{rig_name}' adopted dependency link {check_path} "
                        "into refresh manifest"
                    )
                    continue

                if target.is_symlink():
                    if not _is_pack_asset_symlink(target, check_path):
                        problems.append(
                            f"rig '{rig_name}' cannot link dependency {check_path}: "
                            f"{target} is a rig-owned symlink"
                        )
                        continue
                elif target.is_file():
                    if managed_record is None:
                        problems.append(
                            f"rig '{rig_name}' cannot link dependency {check_path}: "
                            f"{target} is a rig-owned file"
                        )
                        continue
                    try:
                        target_digest = _sha256(target)
                    except OSError as exc:
                        problems.append(
                            f"rig '{rig_name}' cannot inspect dependency {check_path}: {exc}"
                        )
                        continue
                    if (
                        target_digest != managed_record.get("sha256")
                        and target_digest != source_record["sha256"]
                    ):
                        problems.append(
                            f"rig '{rig_name}' cannot refresh dependency {check_path}: "
                            "managed copy was modified outside factory-build-gates"
                        )
                        continue
                elif target.exists():
                    problems.append(
                        f"rig '{rig_name}' cannot link dependency {check_path}: "
                        f"{target} exists and is not a file"
                    )
                    continue

                if check_only:
                    state = "stale" if target.exists() or target.is_symlink() else "missing"
                    problems.append(
                        f"rig '{rig_name}' {state} dependency {check_path} "
                        f"(formulas: {formula_names})"
                    )
                    continue
                try:
                    _replace_symlink(target, source)
                except OSError as exc:
                    problems.append(
                        f"rig '{rig_name}' cannot link dependency {check_path}: {exc}"
                    )
                    continue
                managed_files[check_path] = source_record
                manifest_changed = True
                fixes.append(f"rig '{rig_name}' linked dependency {check_path} -> {source}")
                continue

            if target.is_symlink():
                if not _is_pack_asset_symlink(target, check_path):
                    problems.append(
                        f"rig '{rig_name}' cannot materialise {check_path}: "
                        f"{target} is a rig-owned symlink"
                    )
                    continue
                if check_only:
                    problems.append(
                        f"rig '{rig_name}' symlinked {check_path}; Gas City rejects "
                        f"pack targets outside rig containment (formulas: {formula_names})"
                    )
                    continue
            elif target.is_file():
                try:
                    target_digest = _sha256(target)
                    target_mode = stat.S_IMODE(target.stat().st_mode)
                except OSError as exc:
                    problems.append(f"rig '{rig_name}' cannot inspect {check_path}: {exc}")
                    continue

                if managed_record is None:
                    if target_digest != source_record["sha256"]:
                        problems.append(
                            f"rig '{rig_name}' cannot materialise {check_path}: "
                            f"{target} is a rig-owned file"
                        )
                        continue
                    if check_only:
                        problems.append(
                            f"rig '{rig_name}' unmanaged {check_path}; content matches "
                            "the pack but no refresh manifest exists"
                        )
                        continue
                else:
                    installed_digest = managed_record.get("sha256")
                    if (
                        target_digest != installed_digest
                        and target_digest != source_record["sha256"]
                    ):
                        problems.append(
                            f"rig '{rig_name}' cannot refresh {check_path}: managed "
                            "copy was modified outside factory-build-gates"
                        )
                        continue

                file_current = (
                    target_digest == source_record["sha256"]
                    and target_mode == source_record["mode"]
                )
                record_current = managed_record == source_record
                if file_current and record_current:
                    continue
                if check_only:
                    state = "stale" if managed_record is not None else "unmanaged"
                    problems.append(
                        f"rig '{rig_name}' {state} {check_path} "
                        f"(formulas: {formula_names})"
                    )
                    continue
                if file_current:
                    managed_files[check_path] = source_record
                    manifest_changed = True
                    fixes.append(
                        f"rig '{rig_name}' adopted existing {check_path} into refresh manifest"
                    )
                    continue
            elif target.exists():
                problems.append(
                    f"rig '{rig_name}' cannot materialise {check_path}: "
                    f"{target} exists and is not a regular file"
                )
                continue

            if check_only:
                state = "stale" if target.exists() or target.is_symlink() else "missing"
                problems.append(
                    f"rig '{rig_name}' {state} {check_path} "
                    f"(formulas: {formula_names})"
                )
                continue

            try:
                _replace_file(target, source)
            except OSError as exc:
                problems.append(f"rig '{rig_name}' cannot materialise {check_path}: {exc}")
                continue
            managed_files[check_path] = source_record
            manifest_changed = True
            fixes.append(f"rig '{rig_name}' materialised {check_path} from {source}")

        if manifest_changed and not check_only:
            try:
                _write_manifest(rig_root, managed_files)
            except OSError as exc:
                problems.append(
                    f"rig '{rig_name}' cannot write {_manifest_path(rig_root)}: {exc}"
                )

    return fixes, problems, len(rigs), len(unique_paths)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check or repair per-rig exec-check paths used by resolved formulas."
    )
    parser.add_argument("--check-only", action="store_true", help="report drift without writing")
    parser.add_argument("--root", help="city root (default: FACTORY_ROOT or repository root)")
    args = parser.parse_args(argv)

    default_root = Path(__file__).resolve().parents[1]
    root = Path(args.root or os.environ.get("FACTORY_ROOT", default_root)).resolve()
    gc_bin = os.environ.get("GC_BIN", "gc")
    try:
        fixes, problems, rig_count, path_count = reconcile(root, gc_bin, args.check_only)
    except BuildGateError as exc:
        print(f"! build-gates — {exc}")
        return 1

    for fix in fixes:
        print(f"FIXED: {fix}")
    for problem in problems:
        print(f"! build-gates — {problem}")
    if problems:
        return 1
    print(
        f"✓ build-gates — {path_count} managed gate path(s) "
        f"ready in {rig_count} configured rig(s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
