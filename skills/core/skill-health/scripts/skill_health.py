#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import py_compile
from pathlib import Path
from typing import Any


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    data: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()
    return data


def check(root: Path) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    readme = (root / "README.md").read_text(encoding="utf-8") if (root / "README.md").exists() else ""
    roadmap = (root / "docs/open-source-roadmap.md").read_text(encoding="utf-8") if (root / "docs/open-source-roadmap.md").exists() else ""
    skills = sorted(root.glob("skills/*/*/SKILL.md"))
    for skill in skills:
        rel = skill.relative_to(root).as_posix()
        skill_dir = skill.parent.relative_to(root).as_posix()
        fm = parse_frontmatter(skill.read_text(encoding="utf-8"))
        if not fm.get("name") or not fm.get("description"):
            blockers.append({"source": rel, "message": "name and description frontmatter are required"})
        if fm.get("name") and fm["name"] not in rel:
            warnings.append({"source": rel, "message": "frontmatter name differs from folder path", "name": fm["name"]})
        name = fm.get("name", "")
        if rel not in readme and skill_dir not in readme and name not in readme:
            warnings.append({"source": rel, "message": "skill is not listed in README"})
        scripts = list(skill.parent.glob("scripts/*.py"))
        for script in scripts:
            try:
                py_compile.compile(str(script), doraise=True)
            except Exception as exc:
                blockers.append({"source": script.relative_to(root).as_posix(), "message": f"python compile failed: {exc}"})
    if "`done`" not in roadmap:
        warnings.append({"source": "docs/open-source-roadmap.md", "message": "roadmap has no done markers"})
    if not list((root / "tests").glob("test_*.py")):
        blockers.append({"source": "tests", "message": "test files are required"})
    return {
        "schema": "codex-skill-health-v1",
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "skill_count": len(skills),
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check skill repository health")
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    result = check(Path(args.root))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
