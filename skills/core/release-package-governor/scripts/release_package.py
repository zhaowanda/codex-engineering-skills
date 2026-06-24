#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "codex-release-package-v1"
REQUIRED_PATHS = [
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    ".github/workflows/validate.yml",
    "docs",
    "skills",
    "prompts",
    "examples",
    "tests",
    "scripts",
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def project_version(root: Path) -> str:
    match = re.search(r"(?m)^version\s*=\s*['\"]([^'\"]+)['\"]", read(root / "pyproject.toml"))
    return match.group(1) if match else ""


def review(root: Path) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    missing = [path for path in REQUIRED_PATHS if not (root / path).exists()]
    for path in missing:
        blockers.append({"source": path, "message": "required release package path is missing"})
    version = project_version(root)
    changelog = read(root / "CHANGELOG.md")
    if not version:
        blockers.append({"source": "pyproject.toml", "message": "project version is required"})
    elif version not in changelog:
        blockers.append({"source": "CHANGELOG.md", "message": "changelog entry for project version is missing", "version": version})
    manifest = {
        "version": version,
        "tag": f"v{version}" if version else "",
        "required_paths": REQUIRED_PATHS,
        "skill_count": len(list((root / "skills").glob("*/*/SKILL.md"))),
        "test_count": len(list((root / "tests").glob("test_*.py"))),
        "dry_run": True,
    }
    if manifest["skill_count"] == 0:
        blockers.append({"source": "skills", "message": "release package has no skills"})
    if manifest["test_count"] == 0:
        warnings.append({"source": "tests", "message": "release package has no tests"})
    return {
        "schema": SCHEMA,
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "manifest": manifest,
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Review release package readiness")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    output = review(Path(args.root))
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
