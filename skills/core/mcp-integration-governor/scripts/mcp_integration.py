#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-mcp-integration-v1"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def review(root: Path) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    frontend = read(root / "examples/scenarios/frontend-change/requirement.md").lower()
    workflow = read(root / "docs/workflow-guide.md").lower()
    pr_template = read(root / ".github/pull_request_template.md").lower()
    if "browser" not in frontend and "chrome devtools" not in frontend:
        warnings.append({"source": "frontend-change", "message": "frontend scenario should mention browser or Chrome DevTools evidence"})
    for term in ["boundary", "evidence", "fallback"]:
        if term not in workflow:
            warnings.append({"source": "docs/workflow-guide.md", "message": f"MCP/workflow guidance should mention {term}"})
    if "issue" not in pr_template or "evidence" not in pr_template:
        blockers.append({"source": ".github/pull_request_template.md", "message": "GitHub contribution flow needs issue and evidence fields"})
    return {
        "schema": SCHEMA,
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Review MCP integration guidance readiness")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    output = review(Path(args.root))
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
