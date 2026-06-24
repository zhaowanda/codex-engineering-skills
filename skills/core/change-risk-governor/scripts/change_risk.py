#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-change-risk-v1"
HIGH_AREAS = {"database", "permission", "configuration", "performance"}
CRITICAL_TERMS = ["drop table", "truncate", "delete from", "password", "secret", "private key", "auth", "authorization", "production"]


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


def text_blob(*items: Any) -> str:
    return json.dumps(items, ensure_ascii=False).lower()


def repo_count(plan: dict[str, Any]) -> int:
    repos = set()
    for task in as_list(plan.get("repo_tasks")):
        if isinstance(task, dict):
            repo = task.get("repo") or task.get("project")
            role = task.get("role") or task.get("change_type")
            if repo and role == "modify":
                repos.add(str(repo))
    return len(repos)


def classify(artifact_dir: Path) -> dict[str, Any]:
    diff_impact = load_json(artifact_dir / "diff_impact.json")
    plan = load_json(artifact_dir / "delivery_plan.json")
    config = load_json(artifact_dir / "configuration_readiness.json")
    security = load_json(artifact_dir / "data_security_review.json")
    performance = load_json(artifact_dir / "performance_diff_review.json") or load_json(artifact_dir / "performance_design_review.json")
    traceability = load_json(artifact_dir / "traceability_matrix.json")
    implementation = load_json(artifact_dir / "implementation_completion_gate.json")
    diff_text = ""
    diff_path = artifact_dir / "change.diff"
    if diff_path.exists():
        diff_text = diff_path.read_text(encoding="utf-8", errors="ignore")

    areas = set(str(item) for item in as_list(diff_impact.get("impact_areas")) if item)
    evidence_required = set(str(item) for item in as_list(diff_impact.get("evidence_required")) if item)
    signals: list[dict[str, Any]] = []
    score = 0

    if areas & HIGH_AREAS:
        score += 30
        signals.append({"source": "diff_impact", "message": "high-risk impact areas detected", "areas": sorted(areas & HIGH_AREAS)})
    if "frontend" in areas:
        score += 10
        evidence_required.add("frontend_acceptance")
    if "api" in areas:
        score += 10
        evidence_required.add("api_contract_or_timing_test")
    modified_repos = repo_count(plan)
    if modified_repos > 1:
        score += 20
        signals.append({"source": "delivery_plan", "message": "multi-repository change", "repo_count": modified_repos})
        evidence_required.add("integration_test")
    if as_list(config.get("blockers")) or config.get("decision") in {"blocked", "block"}:
        score += 25
        signals.append({"source": "configuration_readiness", "message": "configuration blockers or unresolved readiness"})
        evidence_required.add("configuration_readiness")
    if security.get("decision") in {"needs_review", "block", "blocked"} or as_list(security.get("controls_required")):
        score += 25
        signals.append({"source": "data_security_review", "message": "security controls required"})
        evidence_required.add("data_security_review")
    if performance.get("decision") in {"needs_evidence", "block", "blocked"} or as_list(performance.get("evidence_plan")):
        score += 15
        signals.append({"source": "performance_review", "message": "performance evidence required"})
        evidence_required.add("performance_evidence")
    if traceability.get("decision") == "block":
        score += 30
        signals.append({"source": "traceability_matrix", "message": "traceability blockers exist"})
        evidence_required.add("traceability_matrix")
    if implementation.get("decision") == "block":
        score += 20
        signals.append({"source": "implementation_completion_gate", "message": "implementation completion is blocked"})

    blob = text_blob(diff_impact, plan, config, security, performance, traceability, implementation, diff_text)
    critical_hits = [term for term in CRITICAL_TERMS if term in blob]
    if critical_hits:
        score += 40
        signals.append({"source": "critical_terms", "message": "critical risk terms detected", "terms": sorted(set(critical_hits))})

    if not areas and not plan and not implementation:
        score += 10
        signals.append({"source": "evidence", "message": "risk classification has limited input evidence"})

    if score >= 80:
        risk_level = "critical"
        control_level = "high_risk_change"
    elif score >= 45:
        risk_level = "high"
        control_level = "heavyweight"
    elif score >= 15:
        risk_level = "medium"
        control_level = "standard"
    else:
        risk_level = "low"
        control_level = "lightweight"

    mandatory_gates = ["code_review_gate", "test_evidence_gate"]
    if risk_level in {"medium", "high", "critical"}:
        mandatory_gates.extend(["implementation_completion_gate", "traceability_matrix"])
    if risk_level in {"high", "critical"}:
        mandatory_gates.extend(["release_change", "environment_promotion", "rollback_plan"])
    if risk_level == "critical":
        mandatory_gates.extend(["explicit_approval", "post_release_observation"])

    blockers: list[dict[str, Any]] = []
    if risk_level in {"high", "critical"} and not plan:
        blockers.append({"source": "delivery_plan", "message": "high-risk changes require delivery_plan.json"})
    if risk_level in {"high", "critical"} and traceability.get("decision") == "block":
        blockers.append({"source": "traceability_matrix", "message": "high-risk changes cannot proceed with traceability blockers"})

    return {
        "schema": SCHEMA,
        "decision": "block" if blockers else "pass",
        "risk_level": risk_level,
        "control_level": control_level,
        "score": score,
        "impact_areas": sorted(areas),
        "signals": signals,
        "mandatory_gates": sorted(set(mandatory_gates)),
        "evidence_required": sorted(evidence_required),
        "blockers": blockers,
        "next_action": "Resolve risk blockers before release planning." if blockers else f"Run {control_level} controls before release.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify engineering change risk")
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--out")
    args = parser.parse_args()
    result = classify(Path(args.artifact_dir))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
