#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-contribution-governance-v1"
REQUIRED_TERMS = ["test", "privacy scan", "skill health", "pull request", "issue", "private data"]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def review(root: Path) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    text = read(root / "CONTRIBUTING.md")
    lower = text.lower()
    if not text:
        blockers.append({"source": "CONTRIBUTING.md", "message": "CONTRIBUTING.md is required"})
    for term in REQUIRED_TERMS:
        if text and term not in lower:
            blockers.append({"source": "CONTRIBUTING.md", "message": f"missing contribution topic: {term}"})
    required_files = [
        ".github/pull_request_template.md",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        ".github/workflows/validate.yml",
    ]
    for file in required_files:
        if not (root / file).exists():
            blockers.append({"source": file, "message": "required contribution support file is missing"})
    if text and "review" not in lower:
        warnings.append({"source": "CONTRIBUTING.md", "message": "review expectations should be explicit"})
    return {
        "schema": SCHEMA,
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "blockers": blockers,
        "warnings": warnings,
        "support_files_checked": required_files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Review open-source contribution readiness")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    output = review(Path(args.root))
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
