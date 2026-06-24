#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "codex-version-release-v1"
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def pyproject_version(root: Path) -> str:
    text = read(root / "pyproject.toml")
    match = re.search(r"(?m)^version\s*=\s*['\"]([^'\"]+)['\"]", text)
    return match.group(1) if match else ""


def review(root: Path, version: str = "") -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    project_version = pyproject_version(root)
    target = version or project_version
    changelog = read(root / "CHANGELOG.md")
    if not target:
        blockers.append({"source": "version", "message": "release version is required"})
    elif not SEMVER.match(target):
        blockers.append({"source": "version", "message": "version must follow SemVer", "version": target})
    if version and project_version and version != project_version:
        blockers.append({"source": "pyproject", "message": "requested version differs from pyproject version", "requested": version, "pyproject": project_version})
    if not changelog:
        blockers.append({"source": "CHANGELOG.md", "message": "CHANGELOG.md is required"})
    elif target and target not in changelog:
        blockers.append({"source": "CHANGELOG.md", "message": "changelog entry for version is missing", "version": target})
    lower = changelog.lower()
    if "breaking" in lower and "migration" not in lower:
        blockers.append({"source": "CHANGELOG.md", "message": "breaking changes require migration notes"})
    if "release notes" not in lower:
        warnings.append({"source": "CHANGELOG.md", "message": "release notes section is recommended"})
    return {
        "schema": SCHEMA,
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "version": target,
        "pyproject_version": project_version,
        "tag": f"v{target}" if target else "",
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Review version release readiness")
    parser.add_argument("--root", default=".")
    parser.add_argument("--version", default="")
    args = parser.parse_args()
    output = review(Path(args.root), args.version)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
