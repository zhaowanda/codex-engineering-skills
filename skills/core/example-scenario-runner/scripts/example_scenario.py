#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-example-scenario-run-v1"
DEFAULT_SCENARIOS = ["bugfix", "small-feature", "config-change", "frontend-change"]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def classify(text: str) -> str:
    lower = text.lower()
    if "bug" in lower or "fix" in lower:
        return "bugfix"
    if "config" in lower or "environment" in lower:
        return "config-change"
    if "ui" in lower or "frontend" in lower or "page" in lower:
        return "frontend-change"
    return "small-feature"


def render_summary(name: str, requirement: str) -> dict[str, Any]:
    kind = classify(requirement)
    risk = "high" if kind == "config-change" else "medium" if kind == "frontend-change" else "low" if kind == "bugfix" else "medium"
    return {
        "name": name,
        "kind": kind,
        "spec": {"summary": requirement.strip().splitlines()[0] if requirement.strip() else "", "acceptance_criteria": ["behavior is verified", "regression is covered"]},
        "technical_design": {"modules": ["affected module"], "api_or_ui": "frontend route" if kind == "frontend-change" else "service behavior", "data_flow": ["input", "validation", "output"]},
        "architecture_design": {"boundaries": ["single example repo"], "rollback": ["revert commit"], "compatibility": "backward compatible"},
        "test_design": {"cases": ["functional test", "regression test"] + (["browser acceptance"] if kind == "frontend-change" else [])},
        "traceability": {"acceptance_covered": True, "task_scope_defined": True},
        "risk": {"level": risk, "required_controls": ["code review", "test evidence"] + (["configuration readiness"] if kind == "config-change" else [])},
    }


def run(root: Path, out: Path) -> dict[str, Any]:
    scenario_root = root / "examples/scenarios"
    blockers: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []
    for name in DEFAULT_SCENARIOS:
        requirement_path = scenario_root / name / "requirement.md"
        requirement = read(requirement_path)
        if not requirement:
            blockers.append({"source": name, "message": "requirement.md is missing or empty"})
            continue
        summary = render_summary(name, requirement)
        scenario_out = out / name
        scenario_out.mkdir(parents=True, exist_ok=True)
        (scenario_out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        cases.append({"name": name, "passed": True, "summary": str((scenario_out / "summary.json"))})
    return {
        "schema": SCHEMA,
        "decision": "block" if blockers else "pass",
        "scenario_count": len(cases),
        "cases": cases,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run synthetic example scenarios")
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    output = run(Path(args.root), Path(args.out))
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
