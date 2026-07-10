#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EVIDENCE_FILE_MAP = {
    "frontend_acceptance": "frontend_acceptance.json",
    "configuration_readiness": "configuration_readiness.json",
    "performance_evidence": "performance_design_review.json",
    "permission_negative_test": "test_execution_evidence.json",
    "api_timing_or_contract_test": "test_execution_evidence.json",
    "api_contract_or_timing_test": "test_execution_evidence.json",
    "api_contract_evidence": "test_execution_evidence.json",
    "sql_explain_or_migration_test": "test_execution_evidence.json",
    "data_model_evidence": "test_execution_evidence.json",
    "mq_interaction_evidence": "test_execution_evidence.json",
    "cache_consistency_evidence": "test_execution_evidence.json",
    "transaction_idempotency_evidence": "test_execution_evidence.json",
    "post_release_observation": "post_release_observation.json",
}

FOLLOWUP_EVIDENCE = {
    "api_contract": "api_contract_evidence",
    "data_model": "data_model_evidence",
    "mq_interaction": "mq_interaction_evidence",
    "cache_consistency": "cache_consistency_evidence",
    "transaction_idempotency": "transaction_idempotency_evidence",
    "permission_data_scope": "permission_negative_test",
    "frontend_acceptance": "frontend_acceptance",
    "configuration": "configuration_readiness",
    "observability": "post_release_observation",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def classify_log(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    if any(term in text for term in ["failed", "error", "traceback", "exception"]):
        status = "failed"
    elif any(term in text for term in ["passed", "success", "ok"]):
        status = "passed"
    else:
        status = "unknown"
    return {"path": str(path), "status": status}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def implementation_followup_requirements(artifact_dir: Path) -> list[dict[str, str]]:
    implementation = load_json(artifact_dir / "implementation_completion_gate.json")
    result: list[dict[str, str]] = []
    for item in as_list(implementation.get("evidence_followups")):
        if not isinstance(item, dict):
            continue
        surface = str(item.get("surface") or "")
        evidence = FOLLOWUP_EVIDENCE.get(surface)
        if evidence:
            result.append({"surface": surface, "evidence": evidence})
    return result


def collect(diff_impact: dict[str, Any], command_logs: list[Path], artifact_dir: Path) -> dict[str, Any]:
    logs = [classify_log(path) for path in command_logs]
    existing = {path.name for path in artifact_dir.glob("*.json")} if artifact_dir.exists() else set()
    required_evidence = [str(item) for item in as_list(diff_impact.get("evidence_required")) if item]
    followup_requirements = implementation_followup_requirements(artifact_dir)
    required_evidence.extend(item["evidence"] for item in followup_requirements)
    missing = []
    found = []
    evidence_file_expectations = []
    for evidence in sorted(set(required_evidence)):
        expected_file = EVIDENCE_FILE_MAP.get(evidence, "")
        if expected_file:
            evidence_file_expectations.append({"evidence": evidence, "artifact": expected_file})
        if expected_file and expected_file in existing:
            found.append(f"{evidence}:{expected_file}")
        if expected_file and expected_file not in existing:
            missing.append(f"{evidence}:{expected_file}")
    failed_logs = [item for item in logs if item["status"] == "failed"]
    unknown_logs = [item for item in logs if item["status"] == "unknown"]
    return {
        "schema": "codex-evidence-gap-summary-v1",
        "decision": "block" if missing or failed_logs or unknown_logs else "pass",
        "impact_areas": diff_impact.get("impact_areas", []),
        "required_evidence": sorted(set(required_evidence)),
        "evidence_file_expectations": evidence_file_expectations,
        "found_evidence": sorted(set(found)),
        "missing_evidence": sorted(set(missing)),
        "implementation_followup_requirements": followup_requirements,
        "command_logs": logs,
        "failed_logs": failed_logs,
        "unknown_logs": unknown_logs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect evidence gaps from diff impact and logs")
    parser.add_argument("--diff-impact", required=True)
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--command-log", action="append", default=[])
    parser.add_argument("--out")
    args = parser.parse_args()
    result = collect(load_json(Path(args.diff_impact)), [Path(item) for item in args.command_log], Path(args.artifact_dir))
    out = Path(args.out) if args.out else Path(args.artifact_dir) / "evidence_gap_summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
