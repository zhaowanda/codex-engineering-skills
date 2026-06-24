#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-roadmap-review-v1"


def skill_names(root: Path) -> list[str]:
    return sorted(path.parent.name for path in (root / "skills").glob("*/*/SKILL.md"))


def review(root: Path) -> dict[str, Any]:
    roadmap = (root / "docs/open-source-roadmap.md").read_text(encoding="utf-8", errors="ignore") if (root / "docs/open-source-roadmap.md").exists() else ""
    readme = (root / "README.md").read_text(encoding="utf-8", errors="ignore") if (root / "README.md").exists() else ""
    catalog = (root / "docs/skill-catalog.md").read_text(encoding="utf-8", errors="ignore") if (root / "docs/skill-catalog.md").exists() else ""
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not roadmap:
        blockers.append({"source": "docs/open-source-roadmap.md", "message": "roadmap is required"})
    if "`done`" not in roadmap:
        blockers.append({"source": "docs/open-source-roadmap.md", "message": "roadmap must include done markers"})
    missing = [name for name in skill_names(root) if name not in roadmap and name not in readme and name not in catalog]
    if missing:
        blockers.append({"source": "skills", "message": "skills missing from roadmap/readme/catalog", "skills": missing})
    if "## v1.1" in roadmap and "Open issues and forward-testing improvements." in roadmap:
        warnings.append({"source": "docs/open-source-roadmap.md", "message": "v1.1 contains generic placeholder item"})
    return {
        "schema": SCHEMA,
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "skill_count": len(skill_names(root)),
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Review roadmap consistency")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    output = review(Path(args.root))
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
