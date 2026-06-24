#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any


SCHEMA = "codex-compatibility-review-v1"
SCHEMA_RE = re.compile(r"codex-[a-z0-9-]+-v\d+")


def current_inventory(root: Path) -> dict[str, list[str]]:
    skills = sorted(path.parent.name for path in (root / "skills").glob("*/*/SKILL.md"))
    schemas = sorted(set(SCHEMA_RE.findall("\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in (root / "skills").glob("**/*.py")))))
    cli_text = (root / "scripts/codex_eng.py").read_text(encoding="utf-8", errors="ignore") if (root / "scripts/codex_eng.py").exists() else ""
    commands = sorted(set(re.findall(r'"([a-z0-9-]+)": \["python3"', cli_text)))
    return {"skills": skills, "schemas": schemas, "commands": commands}


def git_show(root: Path, ref: str, path: str) -> str:
    proc = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=root, text=True, capture_output=True)
    return proc.stdout if proc.returncode == 0 else ""


def base_inventory(root: Path, ref: str) -> dict[str, list[str]]:
    files = subprocess.run(["git", "ls-tree", "-r", "--name-only", ref], cwd=root, text=True, capture_output=True)
    names = files.stdout.splitlines() if files.returncode == 0 else []
    skills = sorted(Path(name).parent.name for name in names if name.endswith("/SKILL.md") and name.startswith("skills/"))
    schemas: set[str] = set()
    for name in names:
        if name.startswith("skills/") and name.endswith(".py"):
            schemas.update(SCHEMA_RE.findall(git_show(root, ref, name)))
    cli_text = git_show(root, ref, "scripts/codex_eng.py")
    commands = sorted(set(re.findall(r'"([a-z0-9-]+)": \["python3"', cli_text)))
    return {"skills": skills, "schemas": sorted(schemas), "commands": commands}


def review(root: Path, base_ref: str = "HEAD") -> dict[str, Any]:
    current = current_inventory(root)
    base = base_inventory(root, base_ref)
    warnings: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    if base["skills"]:
        removed_skills = sorted(set(base["skills"]) - set(current["skills"]))
        removed_schemas = sorted(set(base["schemas"]) - set(current["schemas"]))
        removed_commands = sorted(set(base["commands"]) - set(current["commands"]))
        for source, values in [("skills", removed_skills), ("schemas", removed_schemas), ("commands", removed_commands)]:
            if values:
                warnings.append({"source": source, "message": "compatibility removals detected", "items": values})
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8", errors="ignore").lower() if (root / "CHANGELOG.md").exists() else ""
    if warnings and "migration" not in changelog:
        blockers.append({"source": "CHANGELOG.md", "message": "compatibility warnings require migration notes"})
    return {
        "schema": SCHEMA,
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "base_ref": base_ref,
        "current_counts": {key: len(value) for key, value in current.items()},
        "base_counts": {key: len(value) for key, value in base.items()},
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Review compatibility risks")
    parser.add_argument("--root", default=".")
    parser.add_argument("--base-ref", default="HEAD")
    args = parser.parse_args()
    output = review(Path(args.root), args.base_ref)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
