#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


AREA_PATTERNS = {
    "api": [r"controller", r"route", r"endpoint", r"@.*mapping", r"router\.", r"/api/"],
    "database": [r"select ", r"insert ", r"update ", r"delete ", r"migration", r"\.sql", r"schema"],
    "configuration": [r"\.ya?ml", r"\.properties", r"\.env", r"config", r"secret", r"token", r"callback"],
    "permission": [r"permission", r"role", r"tenant", r"auth", r"authorize"],
    "performance": [r"for\s*\(", r"while\s*\(", r"batch", r"export", r"report", r"cache"],
    "frontend": [r"\.vue", r"\.tsx?", r"\.jsx?", r"component", r"page", r"button"],
    "tests": [r"test", r"spec"],
    "docs": [r"\.md", r"docs/"],
}


def changed_files(diff: str) -> list[str]:
    result = []
    for line in diff.splitlines():
        if line.startswith("+++ b/") or line.startswith("--- a/"):
            path = line[6:]
            if path != "/dev/null":
                result.append(path)
    return sorted(set(result))


def analyze(diff: str) -> dict[str, Any]:
    lower = diff.lower()
    files = changed_files(diff)
    areas: list[str] = []
    evidence_required: list[str] = []
    for area, patterns in AREA_PATTERNS.items():
        if any(re.search(pattern, lower) for pattern in patterns) or any(re.search(pattern, file.lower()) for file in files for pattern in patterns):
            areas.append(area)
    if "api" in areas:
        evidence_required.append("api_timing_or_contract_test")
    if "database" in areas:
        evidence_required.append("sql_explain_or_migration_test")
    if "configuration" in areas:
        evidence_required.append("configuration_readiness")
    if "permission" in areas:
        evidence_required.append("permission_negative_test")
    if "performance" in areas:
        evidence_required.append("performance_evidence")
    if "frontend" in areas:
        evidence_required.append("frontend_acceptance")
    return {
        "schema": "codex-diff-impact-v1",
        "decision": "pass",
        "blockers": [],
        "changed_files": files,
        "impact_areas": sorted(set(areas)),
        "evidence_required": sorted(set(evidence_required)),
        "risk_level": "high" if {"database", "permission", "configuration"} & set(areas) else "medium" if areas else "low",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze git diff impact")
    parser.add_argument("--diff-file", required=True)
    parser.add_argument("--out")
    args = parser.parse_args()
    result = analyze(Path(args.diff_file).read_text(encoding="utf-8", errors="ignore"))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
