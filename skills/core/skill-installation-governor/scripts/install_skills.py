#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Any


SCHEMA = "codex-skill-installation-v1"
LAYERS = ("core", "templates")
RUNTIME_SCRIPTS = ("scripts/docs_config.py",)


def default_target() -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return codex_home / "skills" / "codex-engineering-skills"


def discover(source: Path, layers: list[str]) -> list[Path]:
    skills: list[Path] = []
    for layer in layers:
        root = source / "skills" / layer
        if root.exists():
            skills.extend(sorted(path.parent for path in root.glob("*/SKILL.md")))
    return skills


def relative_skill(path: Path, source: Path) -> Path:
    return path.relative_to(source / "skills")


def installed_skill_name(path: Path) -> str:
    return path.name


def runtime_script_destinations(target: Path, rel_script: str) -> list[Path]:
    name = Path(rel_script).name
    destinations: list[Path] = [target / "scripts" / name]
    if target.parent.name == "skills":
        destinations.append(target.parent.parent / "scripts" / name)
    return list(dict.fromkeys(destinations))


def install(source: Path, target: Path, layers: list[str], dry_run: bool = False, force: bool = False) -> dict[str, Any]:
    source = source.resolve()
    skills = discover(source, layers)
    blockers: list[dict[str, Any]] = []
    copied: list[str] = []
    copied_runtime_scripts: list[str] = []
    planned: list[str] = []
    planned_runtime_scripts: list[str] = []
    if not skills:
        blockers.append({"source": "skills", "message": "no skills found to install"})
    if target.exists() and any(target.iterdir()) and not force and not dry_run:
        blockers.append({"source": str(target), "message": "target is non-empty; use --force to overwrite"})
    for skill in skills:
        rel = relative_skill(skill, source)
        planned.append(rel.as_posix())
        if not (skill / "SKILL.md").exists():
            blockers.append({"source": rel.as_posix(), "message": "SKILL.md missing"})
    for rel_script in RUNTIME_SCRIPTS:
        source_script = source / rel_script
        planned_runtime_scripts.append(rel_script)
        if not source_script.exists():
            blockers.append({"source": rel_script, "message": "runtime support script missing"})
    names = [installed_skill_name(skill) for skill in skills]
    duplicate_names = sorted({name for name in names if names.count(name) > 1})
    for name in duplicate_names:
        blockers.append({"source": name, "message": "duplicate installed skill name"})
    if blockers:
        return result("block", target, planned, copied, planned_runtime_scripts, copied_runtime_scripts, blockers)
    if not dry_run:
        if target.exists() and force:
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)
        for skill in skills:
            rel = relative_skill(skill, source)
            dest = target / installed_skill_name(skill)
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(skill, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
            copied.append(rel.as_posix())
        for rel_script in RUNTIME_SCRIPTS:
            for dest in runtime_script_destinations(target, rel_script):
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / rel_script, dest)
                try:
                    label = dest.relative_to(target).as_posix()
                except ValueError:
                    label = dest.relative_to(target.parent.parent).as_posix()
                if label not in copied_runtime_scripts:
                    copied_runtime_scripts.append(label)
    return result("plan" if dry_run else "pass", target, planned, copied, planned_runtime_scripts, copied_runtime_scripts, [])


def result(
    decision: str,
    target: Path,
    planned: list[str],
    copied: list[str],
    planned_runtime_scripts: list[str],
    copied_runtime_scripts: list[str],
    blockers: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "decision": decision,
        "target": display_path(target),
        "planned_count": len(planned),
        "copied_count": len(copied),
        "planned_skills": planned,
        "copied_skills": copied,
        "planned_runtime_scripts": planned_runtime_scripts,
        "copied_runtime_scripts": copied_runtime_scripts,
        "blockers": blockers,
    }


def display_path(path: Path) -> str:
    try:
        return "~/" + path.expanduser().resolve().relative_to(Path.home()).as_posix()
    except Exception:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install open-core Codex engineering skills")
    parser.add_argument("--source", default=".")
    parser.add_argument("--target", default=str(default_target()))
    parser.add_argument("--layers", default="core,templates")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    layers = [item.strip() for item in args.layers.split(",") if item.strip()]
    output = install(Path(args.source), Path(args.target), layers, dry_run=args.dry_run, force=args.force)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
