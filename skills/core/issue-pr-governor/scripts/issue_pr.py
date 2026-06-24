#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-issue-pr-governance-v1"
PR_REQUIRED = {
    "linked_issue": ["linked issue", "fixes #", "closes #", "related issue"],
    "scope": ["scope", "change scope"],
    "tests": ["tests", "test evidence"],
    "evidence": ["evidence", "validation"],
    "risk": ["risk", "risks"],
    "rollback": ["rollback", "revert"],
    "release_notes": ["release notes", "changelog"],
}
BUG_REQUIRED = ["reproduction", "expected", "actual", "environment"]
FEATURE_REQUIRED = ["problem", "proposed", "acceptance", "alternatives", "compatibility"]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def has_any(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return any(term in lower for term in terms)


def review_pr(path: Path) -> dict[str, Any]:
    text = read_text(path)
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not text.strip():
        blockers.append({"source": str(path), "message": "PR template is missing or empty"})
    for area, terms in PR_REQUIRED.items():
        if not has_any(text, terms):
            blockers.append({"source": area, "message": f"PR template missing {area}"})
    if "<!--" not in text:
        warnings.append({"source": "guidance", "message": "PR template should include comments or examples for contributors"})
    return result(blockers, warnings, {"pr_file": str(path)})


def review_issue_templates(root: Path) -> dict[str, Any]:
    bug = read_text(root / ".github/ISSUE_TEMPLATE/bug_report.yml")
    feature = read_text(root / ".github/ISSUE_TEMPLATE/feature_request.yml")
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not bug:
        blockers.append({"source": "bug_report", "message": "bug report template is missing"})
    if not feature:
        blockers.append({"source": "feature_request", "message": "feature request template is missing"})
    for term in BUG_REQUIRED:
        if bug and term not in bug.lower():
            blockers.append({"source": "bug_report", "message": f"bug report template missing {term}"})
    for term in FEATURE_REQUIRED:
        if feature and term not in feature.lower():
            blockers.append({"source": "feature_request", "message": f"feature request template missing {term}"})
    return result(blockers, warnings, {"root": str(root)})


def result(blockers: list[dict[str, Any]], warnings: list[dict[str, Any]], meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "decision": "block" if blockers else "warn" if warnings else "pass",
        **meta,
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Review issue and PR governance templates")
    parser.add_argument("--pr-file")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    if args.pr_file:
        output = review_pr(Path(args.pr_file))
    else:
        output = review_issue_templates(Path(args.root))
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
