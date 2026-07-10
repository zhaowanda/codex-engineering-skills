#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ACTIVE = {"open", "fix_required"}


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


def active_findings(data: dict[str, Any], severe_only: bool = False) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in as_list(data.get("findings")):
        if not isinstance(item, dict):
            continue
        if item.get("status", "open") not in ACTIVE:
            continue
        if severe_only and item.get("severity") not in {"blocker", "high"}:
            continue
        result.append(item)
    return result


def has_execution_evidence(evidence: dict[str, dict[str, Any]], evidence_type: str) -> bool:
    searchable = json.dumps({
        "tests": evidence.get("test_execution_evidence", {}),
        "ci": evidence.get("ci_execution_evidence", {}),
        "frontend": evidence.get("frontend_acceptance", {}),
        "security": evidence.get("data_security_review", {}),
        "performance": evidence.get("performance_diff_review", {}) or evidence.get("performance_design_review", {}),
        "config": evidence.get("configuration_readiness", {}),
    }, ensure_ascii=False).lower()
    aliases = {
        "sql_explain": ["sql_explain", "explain"],
        "query_count": ["query_count"],
        "api_timing": ["api_timing", "p95", "latency", "timing"],
        "frontend_bundle": ["bundle", "build size", "chunk"],
        "devtools_trace": ["devtools", "lighthouse", "trace", "network", "console"],
        "export_volume": ["export_volume", "sample_runtime", "export", "report", "rows"],
        "mq_throughput": ["mq", "throughput", "consumer lag", "dlq"],
        "external_timeout": ["timeout", "retry", "degrade"],
        "performance_validation_evidence": ["performance", "timing", "devtools"],
        "frontend_acceptance": ["devtools", "frontend_acceptance", "console", "network", "screenshot"],
        "regression_execution": ["regression", "test_execution"],
        "security_redaction": ["log", "redaction", "secret", "masking"],
    }
    terms = aliases.get(evidence_type, [evidence_type])
    return any(term.lower() in searchable for term in terms)


def has_artifact_evidence(evidence: dict[str, dict[str, Any]], artifact_name: str) -> bool:
    name = artifact_name.removesuffix(".json")
    data = evidence.get(name, {})
    if not data:
        return False
    decision = str(data.get("decision") or data.get("status") or "").lower()
    if decision in {"block", "blocked", "fail", "failed", "no_go"}:
        return False
    if data.get("pass") is False:
        return False
    return True


def gap_item_resolved(evidence: dict[str, dict[str, Any]], item_text: str) -> bool:
    if ":" in item_text:
        evidence_type, artifact_name = item_text.split(":", 1)
        return has_artifact_evidence(evidence, artifact_name) or has_execution_evidence(evidence, evidence_type)
    return has_artifact_evidence(evidence, item_text) or has_execution_evidence(evidence, item_text)


def gate(artifact_dir: Path) -> dict[str, Any]:
    evidence_names = [
        "implementation_completion_gate",
        "code_review",
        "code_design_quality",
        "write_guard_audit",
        "data_security_review",
        "performance_diff_review",
        "performance_design_review",
        "test_execution_evidence",
        "ci_execution_evidence",
        "frontend_acceptance",
        "configuration_readiness",
        "evidence_gap_summary",
    ]
    evidence = {name: load_json(artifact_dir / f"{name}.json") for name in evidence_names}
    active_blockers: list[Any] = []
    active_concerns: list[Any] = []
    accepted_risks: list[Any] = []
    missing_evidence: list[str] = []
    evidence_summary: list[dict[str, Any]] = []
    release_blockers: list[str] = []

    write_guard = evidence["write_guard_audit"]
    if write_guard:
        if write_guard.get("decision") != "ready":
            active_blockers.append({"source": "write_guard_audit", "message": "workspace write audit is not ready"})
        evidence_summary.append({"area": "write_guard_audit", "decision": write_guard.get("decision"), "changed_files": len(as_list(write_guard.get("changed_files")))})
    else:
        missing_evidence.append("write_guard_audit.json")

    for name in ["code_review", "code_design_quality", "data_security_review"]:
        data = evidence[name]
        if not data:
            missing_evidence.append(f"{name}.json")
            continue
        severe = active_findings(data, severe_only=True)
        concerns = [item for item in active_findings(data) if item.get("severity") == "medium"]
        active_blockers.extend({"source": name, **item} for item in severe)
        active_concerns.extend({"source": name, **item} for item in concerns)
        accepted_risks.extend({"source": name, **item} for item in active_findings(data) if item.get("status") in {"accepted_risk", "waived"})
        release_blockers.extend(str(item) for item in as_list(data.get("release_blockers")))
        evidence_summary.append({"area": name, "decision": data.get("decision") or data.get("review_decision"), "active_blockers": len(severe), "active_concerns": len(concerns)})

    performance = evidence["performance_diff_review"] or evidence["performance_design_review"]
    if performance:
        if performance.get("decision") in {"block", "blocked"}:
            active_blockers.append({"source": "performance", "message": "performance review is blocked"})
        elif performance.get("decision") in {"needs_evidence", "needs_revision", "request_changes"}:
            active_concerns.append({"source": "performance", "message": "performance evidence is incomplete"})
        release_blockers.extend(str(item) for item in as_list(performance.get("release_blockers")))
        missing_perf_evidence: list[str] = []
        for item in as_list(performance.get("evidence_plan")):
            if not isinstance(item, dict):
                continue
            for evidence_type in as_list(item.get("evidence_types")):
                if evidence_type and not has_execution_evidence(evidence, str(evidence_type)):
                    missing_perf_evidence.append(str(evidence_type))
        if missing_perf_evidence:
            active_concerns.append({"source": "performance", "message": "performance evidence plan is not fully bound", "missing_evidence_types": sorted(set(missing_perf_evidence))})
        evidence_summary.append({"area": "performance", "decision": performance.get("decision"), "risk_level": performance.get("risk_level")})
    else:
        missing_evidence.append("performance review")

    tests = evidence["test_execution_evidence"]
    if tests:
        if tests.get("failed_cases") or tests.get("untested_blockers"):
            active_blockers.append({"source": "test_execution", "message": "failed_cases or untested_blockers exist"})
        if tests.get("untested_non_blockers"):
            active_concerns.append({"source": "test_execution", "message": "untested_non_blockers exist"})
        evidence_summary.append({"area": "test_execution", "failed": len(as_list(tests.get("failed_cases"))), "untested_blockers": len(as_list(tests.get("untested_blockers")))})
    else:
        missing_evidence.append("test_execution_evidence.json")

    ci = evidence["ci_execution_evidence"]
    if ci:
        if ci.get("failed_commands"):
            active_blockers.append({"source": "ci", "message": "CI failed commands exist"})
        if ci.get("unknown_commands"):
            active_concerns.append({"source": "ci", "message": "CI has unknown command results"})
        evidence_summary.append({"area": "ci", "failed": len(as_list(ci.get("failed_commands"))), "unknown": len(as_list(ci.get("unknown_commands")))})
    else:
        missing_evidence.append("ci_execution_evidence.json")

    frontend = evidence["frontend_acceptance"]
    if frontend:
        if frontend.get("pass") is not True and frontend.get("decision") not in {"pass", "ready"}:
            active_blockers.append({"source": "frontend_acceptance", "message": "frontend acceptance did not pass"})
        evidence_summary.append({"area": "frontend_acceptance", "pass": frontend.get("pass"), "decision": frontend.get("decision")})

    config = evidence["configuration_readiness"]
    if config:
        if config.get("decision") in {"blocked", "block"}:
            active_blockers.append({"source": "configuration", "message": "configuration readiness is blocked"})
        elif config.get("decision") in {"needs_review", "needs_revision", "request_changes"}:
            active_concerns.append({"source": "configuration", "message": "configuration readiness needs review"})
        evidence_summary.append({"area": "configuration", "decision": config.get("decision")})

    implementation = evidence["implementation_completion_gate"]
    implementation_followups = as_list(implementation.get("evidence_followups")) if implementation else []
    if implementation:
        if implementation.get("decision") == "block":
            active_blockers.append({"source": "implementation_completion_gate", "message": "implementation completion is blocked"})
        evidence_summary.append({"area": "implementation_completion_gate", "decision": implementation.get("decision"), "followups": len(implementation_followups)})
    if implementation_followups and not evidence["evidence_gap_summary"]:
        missing_evidence.append("evidence_gap_summary.json")
        active_concerns.append({"source": "implementation_completion_gate", "message": "implementation evidence follow-ups require evidence_gap_summary"})

    gap = evidence["evidence_gap_summary"]
    if gap:
        if gap.get("decision") == "block":
            active_blockers.append({"source": "evidence_gap_summary", "message": "evidence gap summary blocks review"})
        if implementation_followups:
            expected_surfaces = sorted({str(item.get("surface")) for item in implementation_followups if isinstance(item, dict) and item.get("surface")})
            covered_surfaces = {
                str(item.get("surface"))
                for item in as_list(gap.get("implementation_followup_requirements"))
                if isinstance(item, dict) and item.get("surface")
            }
            missing_surfaces = [surface for surface in expected_surfaces if surface not in covered_surfaces]
            if missing_surfaces:
                active_concerns.append({"source": "evidence_gap_summary", "message": "evidence gap summary does not cover implementation follow-ups", "missing_surfaces": missing_surfaces})
        unresolved: list[str] = []
        for item in as_list(gap.get("missing_evidence")):
            item_text = str(item)
            if not gap_item_resolved(evidence, item_text):
                unresolved.append(item_text)
        if unresolved:
            missing_evidence.extend(sorted(set(unresolved)))
            active_concerns.append({"source": "evidence_gap_summary", "message": "automatic evidence gaps are unresolved", "missing_evidence": sorted(set(unresolved))})
        evidence_summary.append({"area": "evidence_gap_summary", "decision": gap.get("decision"), "missing": len(as_list(gap.get("missing_evidence"))), "unresolved": len(unresolved)})

    if active_blockers or release_blockers:
        decision = "block"
    elif active_concerns or missing_evidence:
        decision = "request_changes"
    else:
        decision = "approve"
    return {
        "schema": "codex-code-review-gate-v1",
        "decision": decision,
        "active_blockers": active_blockers,
        "active_concerns": active_concerns,
        "accepted_risks": accepted_risks,
        "missing_evidence": sorted(set(missing_evidence)),
        "evidence_summary": evidence_summary,
        "required_rework": [item.get("message", str(item)) for item in active_blockers + active_concerns if isinstance(item, dict)],
        "release_blockers": sorted(set(release_blockers)),
    }


def validate(data: dict[str, Any]) -> tuple[bool, list[str]]:
    issues: list[str] = []
    required = ["schema", "decision", "active_blockers", "active_concerns", "accepted_risks", "missing_evidence", "evidence_summary", "required_rework", "release_blockers"]
    for key in required:
        if key not in data:
            issues.append(f"missing {key}")
    if data.get("schema") != "codex-code-review-gate-v1":
        issues.append("schema must be codex-code-review-gate-v1")
    if data.get("decision") not in {"approve", "request_changes", "block"}:
        issues.append("decision must be approve/request_changes/block")
    if data.get("decision") == "approve" and (data.get("active_blockers") or data.get("active_concerns") or data.get("missing_evidence") or data.get("release_blockers")):
        issues.append("approve is not allowed with blockers, concerns, missing evidence, or release blockers")
    return not issues, issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate code review gate evidence")
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--out")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    result = gate(Path(args.artifact_dir))
    if args.out:
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.validate:
        valid, issues = validate(result)
        if not valid:
            print(json.dumps({"schema": "codex-code-review-gate-validation-v1", "valid": valid, "issues": issues}, ensure_ascii=False, indent=2))
            return 1
    return 0 if result["decision"] == "approve" else 1


if __name__ == "__main__":
    raise SystemExit(main())
