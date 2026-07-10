#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path


def run(root: Path) -> dict:
    cases = []
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run(
            ["python3", "skills/templates/synthetic-e2e-runner/scripts/run_synthetic_e2e.py", "--out-dir", tmp],
            cwd=root,
            text=True,
            capture_output=True,
        )
        data = {}
        try:
            data = json.loads(proc.stdout)
        except Exception:
            pass
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
            "one_line_request": proc.returncode == 0 and data.get("decision") == "pass",
            "long_prd": proc.returncode == 0 and data.get("decision") == "pass",
            "bugfix": proc.returncode == 0 and data.get("decision") == "pass",
            "frontend_change": case_results["frontend_happy_path"],
            "cross_repo_api": case_results["happy_path_case"],
            "data_migration": case_results["data_migration_blocked_path"],
            "release_readiness": case_results["release_readiness_blocked_path"] and case_results["release_readiness_happy_path"] and case_results["release_followup_chain_path"],
            "code_review": proc.returncode == 0 and data.get("decision") == "pass",
        }
        cases.append({
            "case": "synthetic-e2e",
            "returncode": proc.returncode,
            "schema": data.get("schema"),
            "decision": data.get("decision"),
            "case_results": case_results,
            "scenario_results": scenario_results,
            "blocked_case_passed": case_results["blocked_case"],
            "happy_path_case_passed": case_results["happy_path_case"],
            "frontend_happy_path_passed": case_results["frontend_happy_path"],
            "data_migration_blocked_path_passed": case_results["data_migration_blocked_path"],
            "release_readiness_blocked_path_passed": case_results["release_readiness_blocked_path"],
            "release_readiness_happy_path_passed": case_results["release_readiness_happy_path"],
            "release_followup_chain_path_passed": case_results["release_followup_chain_path"],
            "passed": proc.returncode == 0 and data.get("schema") == "codex-synthetic-e2e-run-v1" and data.get("decision") == "pass" and all(case_results.values()) and all(scenario_results.values()),
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
    args = parser.parse_args()
    result = run(Path(args.root))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
