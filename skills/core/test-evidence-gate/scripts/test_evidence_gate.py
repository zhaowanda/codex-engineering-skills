#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def truthy_pass(data: dict[str, Any]) -> bool:
    return data.get("pass") is True or data.get("decision") in {"pass", "ready", "approved"}


def count_executed_cases(test_evidence: dict[str, Any]) -> int:
    candidates = [
        test_evidence.get("executed_cases"),
        test_evidence.get("passed_cases"),
        test_evidence.get("case_results"),
        test_evidence.get("manual_cases"),
        test_evidence.get("automated_cases"),
    ]
    count = 0
    for value in candidates:
        for item in as_list(value):
            if isinstance(item, dict):
                status = str(item.get("status") or item.get("result") or "passed").lower()
                if status not in {"skipped", "not_run", "not run", "pending", "todo"}:
                    count += 1
            elif item:
                count += 1
    explicit_count = test_evidence.get("executed_case_count")
    if isinstance(explicit_count, int):
        count = max(count, explicit_count)
    return count


def has_real_test_evidence(test_evidence: dict[str, Any], ci_evidence: dict[str, Any], frontend: dict[str, Any]) -> bool:
    if count_executed_cases(test_evidence) > 0:
        return True
    searchable = json.dumps(
        {
            "test": test_evidence,
            "ci": ci_evidence,
            "frontend": frontend,
        },
        ensure_ascii=False,
    ).lower()
    evidence_terms = [
        "command",
        "api",
        "curl",
        "postman",
        "pytest",
        "jest",
        "vitest",
        "junit",
        "screenshot",
        "devtools",
        "network",
        "console",
        "trace",
        "artifact",
        "report",
    ]
    return any(term in searchable for term in evidence_terms)


def command_count(ci_evidence: dict[str, Any], key: str) -> int:
    return len(as_list(ci_evidence.get(key)))


def data_refs_required(test_design: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for case in as_list(test_design.get("test_cases")):
        if isinstance(case, dict):
            refs.update(str(item) for item in as_list(case.get("test_data_refs")) if item)
    return refs


def data_refs_in_plan(test_data_plan: dict[str, Any]) -> set[str]:
    return {str(item.get("id")) for item in as_list(test_data_plan.get("datasets")) if isinstance(item, dict) and item.get("id")}


def executed_case_data_refs(test_evidence: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for item in as_list(test_evidence.get("executed_cases")) + as_list(test_evidence.get("passed_cases")) + as_list(test_evidence.get("case_results")):
        if not isinstance(item, dict):
            continue
        case_id = str(item.get("id") or item.get("case_id") or item.get("name") or "")
        if case_id:
            result[case_id] = [str(ref) for ref in as_list(item.get("dataset_ids") or item.get("test_data_refs")) if ref]
    return result


def evaluate(
    artifact_dir: Path,
    require_frontend: bool = False,
    min_executed_cases: int = 1,
) -> dict[str, Any]:
    test_evidence = load_json(artifact_dir / "test_execution_evidence.json")
    ci_evidence = load_json(artifact_dir / "ci_execution_evidence.json")
    frontend = load_json(artifact_dir / "frontend_acceptance.json")
    test_design = load_json(artifact_dir / "test_design.json")
    test_data_plan = load_json(artifact_dir / "test_data_plan.json")

    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if not test_evidence:
        blockers.append({"source": "test_execution_evidence", "message": "test_execution_evidence.json is missing or invalid"})
    else:
        executed_count = count_executed_cases(test_evidence)
        if executed_count < min_executed_cases:
            blockers.append(
                {
                    "source": "test_execution_evidence",
                    "message": "executed test case count is below threshold",
                    "executed_case_count": executed_count,
                    "min_executed_cases": min_executed_cases,
                }
            )
        if not has_real_test_evidence(test_evidence, ci_evidence, frontend):
            blockers.append({"source": "test_execution_evidence", "message": "no real execution evidence found"})
        if as_list(test_evidence.get("failed_cases")):
            blockers.append({"source": "test_execution_evidence", "message": "failed test cases exist", "count": len(as_list(test_evidence.get("failed_cases")))})
        if as_list(test_evidence.get("untested_blockers")):
            blockers.append({"source": "test_execution_evidence", "message": "untested blockers exist", "count": len(as_list(test_evidence.get("untested_blockers")))})
        if as_list(test_evidence.get("untested_non_blockers")):
            warnings.append({"source": "test_execution_evidence", "message": "untested non-blocking cases exist", "count": len(as_list(test_evidence.get("untested_non_blockers")))})

    required_data_refs = data_refs_required(test_design)
    if required_data_refs:
        if not test_data_plan:
            blockers.append({"source": "test_data_plan", "message": "test_data_plan.json is required because test_design.json declares test_data_refs"})
        else:
            if test_data_plan.get("decision") == "block":
                blockers.append({"source": "test_data_plan", "message": "test data plan decision is block"})
            planned_refs = data_refs_in_plan(test_data_plan)
            missing_refs = sorted(required_data_refs - planned_refs)
            if missing_refs:
                blockers.append({"source": "test_data_plan", "message": "test data refs missing from plan", "missing_refs": missing_refs})
        if test_evidence:
            refs_by_case = executed_case_data_refs(test_evidence)
            for case in as_list(test_design.get("test_cases")):
                if not isinstance(case, dict):
                    continue
                case_id = str(case.get("id") or "")
                refs = [str(ref) for ref in as_list(case.get("test_data_refs")) if ref]
                if not case_id or not refs:
                    continue
                executed_refs = refs_by_case.get(case_id, [])
                if not executed_refs:
                    blockers.append({"source": "test_execution_evidence", "message": "executed case is missing dataset linkage", "case_id": case_id})
                elif not set(refs).issubset(set(executed_refs)):
                    blockers.append({"source": "test_execution_evidence", "message": "executed case dataset linkage does not cover required refs", "case_id": case_id, "required_refs": refs, "actual_refs": executed_refs})

    if not ci_evidence:
        warnings.append({"source": "ci_execution_evidence", "message": "ci_execution_evidence.json is missing"})
    else:
        if ci_evidence.get("mode") == "plan":
            blockers.append({"source": "ci_execution_evidence", "message": "CI evidence is plan-only and was not executed"})
        if command_count(ci_evidence, "failed_commands"):
            blockers.append({"source": "ci_execution_evidence", "message": "failed CI commands exist", "count": command_count(ci_evidence, "failed_commands")})
        if command_count(ci_evidence, "unknown_commands"):
            blockers.append({"source": "ci_execution_evidence", "message": "unknown CI command results exist", "count": command_count(ci_evidence, "unknown_commands")})
        if command_count(ci_evidence, "manual_review_required"):
            blockers.append({"source": "ci_execution_evidence", "message": "CI commands require manual review", "count": command_count(ci_evidence, "manual_review_required")})

    if require_frontend:
        if not frontend:
            blockers.append({"source": "frontend_acceptance", "message": "frontend acceptance is required but missing"})
        elif not truthy_pass(frontend):
            blockers.append({"source": "frontend_acceptance", "message": "frontend acceptance did not pass"})
        else:
            console_errors = as_list(frontend.get("console_errors"))
            failed_requests = as_list(frontend.get("failed_requests"))
            if console_errors or failed_requests:
                blockers.append(
                    {
                        "source": "frontend_acceptance",
                        "message": "frontend acceptance has console errors or failed requests",
                        "console_errors": len(console_errors),
                        "failed_requests": len(failed_requests),
                    }
                )
    elif frontend and not truthy_pass(frontend):
        warnings.append({"source": "frontend_acceptance", "message": "frontend acceptance exists but did not pass"})

    executed_count = count_executed_cases(test_evidence)
    evidence_summary = {
        "test_execution_evidence_present": bool(test_evidence),
        "ci_execution_evidence_present": bool(ci_evidence),
        "frontend_acceptance_present": bool(frontend),
        "test_design_present": bool(test_design),
        "test_data_plan_present": bool(test_data_plan),
        "required_test_data_ref_count": len(data_refs_required(test_design)),
        "executed_case_count": executed_count,
        "failed_case_count": len(as_list(test_evidence.get("failed_cases"))) if test_evidence else 0,
        "untested_blocker_count": len(as_list(test_evidence.get("untested_blockers"))) if test_evidence else 0,
        "ci_failed_command_count": command_count(ci_evidence, "failed_commands") if ci_evidence else 0,
        "ci_unknown_command_count": command_count(ci_evidence, "unknown_commands") if ci_evidence else 0,
        "frontend_required": require_frontend,
    }
    decision = "block" if blockers else "pass"
    next_action = (
        "Fix blockers and rerun test evidence gate."
        if blockers
        else "Bind this artifact into release evidence and advance delivery state explicitly."
    )
    return {
        "schema": "codex-test-evidence-gate-v1",
        "decision": decision,
        "blockers": blockers,
        "warnings": warnings,
        "evidence_summary": evidence_summary,
        "next_action": next_action,
    }


def validate(data: dict[str, Any]) -> tuple[bool, list[str]]:
    issues: list[str] = []
    required = ["schema", "decision", "blockers", "warnings", "evidence_summary", "next_action"]
    for key in required:
        if key not in data:
            issues.append(f"missing {key}")
    if data.get("schema") != "codex-test-evidence-gate-v1":
        issues.append("schema must be codex-test-evidence-gate-v1")
    if data.get("decision") not in {"pass", "block"}:
        issues.append("decision must be pass/block")
    if data.get("decision") == "pass" and data.get("blockers"):
        issues.append("pass is not allowed with blockers")
    if data.get("decision") == "block" and not data.get("blockers"):
        issues.append("block must include blockers")
    return not issues, issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate real test and CI execution evidence")
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--require-frontend", action="store_true")
    parser.add_argument("--min-executed-cases", type=int, default=1)
    parser.add_argument("--out")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    result = evaluate(
        artifact_dir=Path(args.artifact_dir),
        require_frontend=args.require_frontend,
        min_executed_cases=args.min_executed_cases,
    )
    if args.out:
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.validate:
        valid, issues = validate(result)
        if not valid:
            print(json.dumps({"schema": "codex-test-evidence-gate-validation-v1", "valid": valid, "issues": issues}, ensure_ascii=False, indent=2))
            return 1
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
