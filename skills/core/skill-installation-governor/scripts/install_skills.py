#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


SCHEMA = "codex-skill-installation-v1"
LAYERS = ("core", "templates")


def discover(source: Path, layers: list[str]) -> list[Path]:
    skills: list[Path] = []
    for layer in layers:
        root = source / "skills" / layer
        if root.exists():
            skills.extend(sorted(path.parent for path in root.glob("*/SKILL.md")))
    return skills


def relative_skill(path: Path, source: Path) -> Path:
    return path.relative_to(source / "skills")


def install(source: Path, target: Path, layers: list[str], dry_run: bool = False, force: bool = False) -> dict[str, Any]:
    source = source.resolve()
    skills = discover(source, layers)
    blockers: list[dict[str, Any]] = []
    copied: list[str] = []
    planned: list[str] = []
    if not skills:
        blockers.append({"source": "skills", "message": "no skills found to install"})
    if target.exists() and any(target.iterdir()) and not force and not dry_run:
        blockers.append({"source": str(target), "message": "target is non-empty; use --force to overwrite"})
    for skill in skills:
        rel = relative_skill(skill, source)
        planned.append(rel.as_posix())
        if not (skill / "SKILL.md").exists():
            blockers.append({"source": rel.as_posix(), "message": "SKILL.md missing"})
    if blockers:
        return result("block", target, planned, copied, blockers)
    if not dry_run:
        target.mkdir(parents=True, exist_ok=True)
        for skill in skills:
            rel = relative_skill(skill, source)
            dest = target / rel
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(skill, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
            copied.append(rel.as_posix())
    return result("plan" if dry_run else "pass", target, planned, copied, [])


def result(decision: str, target: Path, planned: list[str], copied: list[str], blockers: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "decision": decision,
        "target": str(target),
        "planned_count": len(planned),
        "copied_count": len(copied),
        "planned_skills": planned,
        "copied_skills": copied,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Install open-core Codex engineering skills")
    parser.add_argument("--source", default=".")
    parser.add_argument("--target", required=True)
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
