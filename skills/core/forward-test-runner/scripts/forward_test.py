#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def load_synthetic_runner() -> Any:
    return load_module("forward_synthetic_e2e_runner", ROOT / "skills/templates/synthetic-e2e-runner/scripts/run_synthetic_e2e.py")


def requirement_shape_results(root: Path) -> dict[str, object]:
    governor = load_module("forward_spec_governor", root / "skills/core/spec-governor/scripts/spec_governor.py")
    one_line = governor.normalize("REQ-FWD-ONE", "Task confirmation", "Optimize task confirmation.")
    long_prd = governor.normalize(
        "REQ-FWD-PRD",
        "Task confirmation",
        "\n".join([
            "Goal: reduce user support tickets by 20 percent.",
            "Metric: support tickets decrease by 20 percent.",
            "Flow: user submits a task and receives a confirmation.",
            "Entrypoint: user submits the task form.",
            "Requirement: completed tasks show Task received.",
            "Acceptance: a completed task shows Task received.",
        ]),
    )
    vague_bugfix = governor.normalize("REQ-FWD-BUG-BLOCK", "Task bug", "Fix the task confirmation bug.")
    resolved_bugfix = governor.normalize(
        "REQ-FWD-BUG-READY",
        "Task bug correction",
        "\n".join([
            "Defect: completed tasks show an empty confirmation message.",
            "Goal: reduce user tickets caused by an empty task confirmation by 20 percent.",
            "Metric: task-confirmation tickets decrease by 20 percent.",
            "Current: completed tasks show an empty confirmation message.",
            "Flow: user submits a task and receives the completed-task confirmation.",
            "Entrypoint: user submits the task form.",
            "Observed: the confirmation message is empty.",
            "Expected: the confirmation message shows Task received.",
            "Reproduction: submit a valid task and wait for completion.",
            "Requirement: completed tasks show Task received.",
            "Acceptance: after a valid task completes, the confirmation shows Task received.",
        ]),
    )
    return {
        "one_line_request": one_line.get("decision") == "blocked" and one_line.get("design_allowed") is False,
        "long_prd": long_prd.get("decision") == "ready_for_design" and long_prd.get("design_allowed") is True,
        "bugfix": (
            vague_bugfix.get("decision") == "blocked"
            and vague_bugfix.get("design_allowed") is False
            and resolved_bugfix.get("decision") == "ready_for_design"
            and resolved_bugfix.get("design_allowed") is True
            and resolved_bugfix.get("lane") == "bugfix"
        ),
        "details": {
            "one_line_decision": one_line.get("decision"),
            "long_prd_decision": long_prd.get("decision"),
            "vague_bugfix_decision": vague_bugfix.get("decision"),
            "resolved_bugfix_decision": resolved_bugfix.get("decision"),
        },
    }


def run(root: Path, pure_mode: bool = False) -> dict:
    cases = []
    requirement_shapes = requirement_shape_results(root)
    synthetic_runner = load_synthetic_runner()
    with tempfile.TemporaryDirectory() as tmp:
        data = synthetic_runner.run(Path(tmp), pure_mode=pure_mode)
        synthetic_cases = data.get("cases", []) if isinstance(data.get("cases"), list) else []
        case_map = {item.get("case"): item for item in synthetic_cases if isinstance(item, dict)}
        required_cases = [
            "blocked_case",
            "happy_path_case",
            "frontend_happy_path",
            "data_migration_blocked_path",
            "release_readiness_blocked_path",
            "release_readiness_happy_path",
            "release_followup_chain_path",
        ]
        case_results = {name: bool(case_map.get(name, {}).get("passed")) for name in required_cases}
        scenario_results = {
            "one_line_request": bool(requirement_shapes["one_line_request"]),
            "long_prd": bool(requirement_shapes["long_prd"]),
            "bugfix": bool(requirement_shapes["bugfix"]),
            "frontend_change": case_results["frontend_happy_path"],
            "cross_repo_api": case_results["happy_path_case"],
            "data_migration": case_results["data_migration_blocked_path"],
            "release_readiness": case_results["release_readiness_blocked_path"] and case_results["release_readiness_happy_path"] and case_results["release_followup_chain_path"],
            "code_review": case_results["release_followup_chain_path"],
        }
        cases.append({
            "case": "synthetic-e2e",
            "returncode": 0 if data.get("decision") == "pass" else 1,
            "schema": data.get("schema"),
            "decision": data.get("decision"),
            "case_results": case_results,
            "scenario_results": scenario_results,
            "requirement_shape_results": requirement_shapes,
            "blocked_case_passed": case_results["blocked_case"],
            "happy_path_case_passed": case_results["happy_path_case"],
            "frontend_happy_path_passed": case_results["frontend_happy_path"],
            "data_migration_blocked_path_passed": case_results["data_migration_blocked_path"],
            "release_readiness_blocked_path_passed": case_results["release_readiness_blocked_path"],
            "release_readiness_happy_path_passed": case_results["release_readiness_happy_path"],
            "release_followup_chain_path_passed": case_results["release_followup_chain_path"],
            "passed": data.get("schema") == "codex-synthetic-e2e-run-v1" and data.get("decision") == "pass" and all(case_results.values()) and all(scenario_results.values()),
        })
    blockers = [{"source": item["case"], "message": "forward test failed"} for item in cases if not item["passed"]]
    return {
        "schema": "codex-forward-test-run-v1",
        "decision": "block" if blockers else "pass",
        "cases": cases,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run forward tests")
    parser.add_argument("--root", required=True)
    parser.add_argument("--pure-mode", action="store_true")
    args = parser.parse_args()
    result = run(Path(args.root), pure_mode=args.pure_mode)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
