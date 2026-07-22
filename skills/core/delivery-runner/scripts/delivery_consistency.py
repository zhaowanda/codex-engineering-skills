#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "codex-delivery-final-consistency-v1"
BAD_TEMPLATE_TERMS = {"需求标题", "requirement title"}
DOMAIN_LEAK_TERMS = {"播放器资源", "播放器生命周期", "player resources", "player lifecycle"}
PERSISTENCE_REQUIRED_TERMS = {
    "审批记录", "审批状态", "审批结果", "实例号", "失败原因", "回调", "建单", "结算单",
    "批次", "落库", "记录表", "状态机",
    "approval record", "approval status", "failure reason", "callback", "retry count", "settlement",
    "idempotency key", "state machine",
}
EXTERNAL_PROVIDER_API_PATTERNS = {"/open-apis/", "external_access_token", "provider_access_token"}
BLOCKING_DECISIONS = {"block", "blocked", "no_go", "fail", "failed", "request_changes", "needs_revision"}
PASS_DECISIONS = {"pass", "ready", "approved", "approve", "warn"}
CORE_GATE_FILES = {
    "design_review": "design_architecture_review.json",
    "docs_quality": "docs_quality.json",
    "implementation": "implementation_completion_gate.json",
    "post_change": "post_change_implementation_report.json",
    "review": "code_review_gate.json",
    "test": "test_evidence_gate.json",
    "frontend_acceptance": "frontend_acceptance_validation.json",
}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def load_json(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        return {}, "missing"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, f"invalid_json: {exc}"
    return (data if isinstance(data, dict) else {}), "" if isinstance(data, dict) else "json_root_not_object"


def decision_of(data: dict[str, Any]) -> str:
    return str(data.get("decision") or data.get("status") or "").strip().lower()


def walk(value: Any, path: str = "") -> list[tuple[str, Any]]:
    rows = [(path, value)]
    if isinstance(value, dict):
        for key, child in value.items():
            rows.extend(walk(child, f"{path}.{key}" if path else str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            rows.extend(walk(child, f"{path}[{index}]"))
    return rows


def contains_bad_template_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    lowered = value.lower()
    return any(term.lower() in lowered for term in BAD_TEMPLATE_TERMS)


def contains_domain_leak(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    lowered = value.lower()
    return any(term.lower() in lowered for term in DOMAIN_LEAK_TERMS)


def has_any_term(text: str, terms: set[str]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered or term in text for term in terms)


def is_external_provider_contract(value: str) -> bool:
    lowered = value.lower()
    return any(pattern in lowered for pattern in EXTERNAL_PROVIDER_API_PATTERNS)


def strip_non_trigger_explanation(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: strip_non_trigger_explanation(item)
            for key, item in value.items()
            if key not in {"not_applicable_reason"}
        }
    if isinstance(value, list):
        return [strip_non_trigger_explanation(item) for item in value]
    return value


def requirement_text(artifact_dir: Path) -> str:
    parts: list[str] = []
    for relative in ["requirement.normalized.txt", "requirement.clarified.txt", "../input/requirement.md", "../input/requirement.normalized.txt"]:
        path = artifact_dir / relative
        if path.exists():
            parts.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parts)


def fixed_quoted_phrases(text: str) -> list[str]:
    phrases: list[str] = []
    for pattern in [
        r"固定(?:为|展示|文案)[：:]\s*[`“\"]([^`”\"]{6,120})[`”\"]",
        r"展示说明文案[：:]\s*[`“\"]([^`”\"]{6,120})[`”\"]",
        r"must (?:display|show)[^`'\"]*[`'\"]([^`'\"]{6,120})[`'\"]",
    ]:
        for match in re.finditer(pattern, text, flags=re.I):
            phrase = match.group(1).strip()
            if phrase and phrase not in phrases:
                phrases.append(phrase)
    return phrases


def implementation_text(artifact_dir: Path) -> str:
    parts: list[str] = []
    for relative in ["implementation_scope.diff", "implementation_summary.txt"]:
        path = artifact_dir / relative
        if path.exists():
            parts.append(path.read_text(encoding="utf-8", errors="ignore"))
    completion, _ = load_json(artifact_dir / "implementation_completion_gate.json")
    if completion:
        parts.append(json.dumps(completion, ensure_ascii=False))
    return "\n".join(parts)


def acceptance_items(spec: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in as_list(spec.get("acceptance_criteria")) if isinstance(item, dict)]


def collect_acceptance_refs(value: Any) -> set[str]:
    refs: set[str] = set()
    for path, item in walk(value):
        key = path.rsplit(".", 1)[-1].lower()
        if key in {"acceptance", "acceptance_id", "acceptance_ref", "acceptance_refs", "acceptance_ids", "ac_id", "ac_ids"}:
            if isinstance(item, str) and item.strip():
                refs.add(item.strip())
                continue
            for ref in as_list(item):
                if isinstance(ref, str) and ref.strip():
                    refs.add(ref.strip())
    return refs


def gate_blockers(artifact_dir: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    blockers: list[dict[str, Any]] = []
    decisions: dict[str, str] = {}
    for gate, filename in CORE_GATE_FILES.items():
        data, error = load_json(artifact_dir / filename)
        if error:
            if (artifact_dir / filename).exists():
                blockers.append({"source": gate, "message": error, "artifact": filename})
            continue
        decision = decision_of(data)
        decisions[gate] = decision
        if decision in BLOCKING_DECISIONS:
            blockers.append({"source": gate, "message": f"blocking decision: {decision}", "artifact": filename})
        for key in ["blockers", "active_blockers", "missing_evidence"]:
            if data.get(key):
                blockers.append({"source": gate, "message": f"{key} must be empty for final consistency", "artifact": filename, "count": len(as_list(data.get(key)))})
    return blockers, decisions


def validate(artifact_dir: Path) -> dict[str, Any]:
    artifact_dir = artifact_dir.expanduser().resolve()
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    invalid_json: list[str] = []
    for path in sorted(artifact_dir.rglob("*.json")):
        _, error = load_json(path)
        if error:
            invalid_json.append(str(path.relative_to(artifact_dir)))
    if invalid_json:
        blockers.append({"source": "json_validity", "message": "JSON artifacts must be valid single JSON documents", "artifacts": invalid_json})

    spec, spec_error = load_json(artifact_dir / "spec.json")
    if spec_error:
        blockers.append({"source": "spec", "message": spec_error, "artifact": "spec.json"})
    for filename in ["spec.json", "technical_design.json", "architecture_design.json", "delivery_plan.json", "test_design.json", "ui_ue_design.json", "runtime_sequence_evidence.json"]:
        data, error = load_json(artifact_dir / filename)
        if error:
            continue
        bad = [
            path for path, value in walk(data)
            if contains_bad_template_text(value)
            and not path.endswith(("source_lines", "source_text", "raw_text", "requirement_text"))
        ]
        if bad:
            blockers.append({"source": "semantic_quality", "message": "template heading text leaked into semantic artifact fields", "artifact": filename, "fields": bad[:20], "count": len(bad)})
        leaks = [
            path for path, value in walk(data)
            if contains_domain_leak(value)
            and not path.endswith(("source_lines", "source_text", "raw_text", "requirement_text"))
        ]
        if leaks:
            blockers.append({"source": "semantic_quality", "message": "cross-domain terms leaked into semantic artifact fields", "artifact": filename, "fields": leaks[:20], "count": len(leaks)})

    technical, _ = load_json(artifact_dir / "technical_design.json")
    architecture, _ = load_json(artifact_dir / "architecture_design.json")
    design_blob = json.dumps(strip_non_trigger_explanation({"spec": spec, "technical": technical, "architecture": architecture}), ensure_ascii=False)
    if has_any_term(design_blob, PERSISTENCE_REQUIRED_TERMS):
        applicability = {
            str(item.get("area", "")).lower(): str(item.get("status", "")).lower()
            for item in as_list(technical.get("impact_applicability"))
            if isinstance(item, dict)
        }
        data_model_raw = technical.get("data_model_design")
        data_model = data_model_raw if isinstance(data_model_raw, dict) else {}
        if applicability.get("data") in {"excluded", "not_applicable"} or data_model.get("applicable") is False:
            blockers.append({"source": "semantic_quality", "message": "design claims no persistence impact while requirement contains records, states, callbacks, retries, idempotency, or query semantics"})
    bad_provider_contracts = [
        item for item in as_list(technical.get("api_contracts"))
        if isinstance(item, dict)
        and is_external_provider_contract(str(item.get("endpoint") or item.get("contract") or ""))
    ]
    if bad_provider_contracts:
        blockers.append({"source": "semantic_quality", "message": "external provider API is used as a local system API contract", "contracts": bad_provider_contracts[:10]})

    gate_issues, decisions = gate_blockers(artifact_dir)
    blockers.extend(gate_issues)

    req_text = requirement_text(artifact_dir)
    impl_text = implementation_text(artifact_dir)
    missing_phrases = [phrase for phrase in fixed_quoted_phrases(req_text) if phrase not in impl_text]
    if missing_phrases:
        blockers.append({"source": "acceptance_contract", "message": "fixed requirement phrase is not present in implementation evidence", "phrases": missing_phrases})

    acs = acceptance_items(spec)
    ac_ids = {str(item.get("id") or "").strip() for item in acs if str(item.get("id") or "").strip()}
    if ac_ids:
        linked_refs = set()
        for filename in [
            "technical_design.json",
            "architecture_design.json",
            "delivery_plan.json",
            "test_design.json",
            "traceability_matrix.json",
            "implementation_completion_gate.json",
            "post_implementation_traceability_matrix.json",
            "test_execution_evidence.json",
            "frontend_acceptance.json",
            "frontend_acceptance_validation.json",
        ]:
            data, error = load_json(artifact_dir / filename)
            if not error:
                linked_refs.update(collect_acceptance_refs(data))
        missing_refs = sorted(ac_id for ac_id in ac_ids if ac_id not in linked_refs)
        if missing_refs:
            blockers.append({"source": "acceptance_traceability", "message": "acceptance criteria are not referenced by design/plan/test/evidence artifacts", "acceptance_ids": missing_refs})
    else:
        warnings.append({"source": "acceptance_traceability", "message": "spec has no structured acceptance criteria"})

    state, state_error = load_json(artifact_dir / "delivery_state.json")
    if not state_error and blockers:
        current = str(state.get("current_stage") or "")
        status = str(state.get("status") or "")
        if current in {"done", "release"} or status in {"pass", "ready", "complete", "synced"}:
            blockers.append({"source": "delivery_state", "message": "delivery state cannot be ready/done while consistency blockers exist", "current_stage": current, "status": status})

    post_change, _ = load_json(artifact_dir / "post_change_implementation_report.json")
    raw_index_req = post_change.get("project_skill_index_requirements")
    index_req: dict[str, Any] = raw_index_req if isinstance(raw_index_req, dict) else {}
    if post_change and not index_req:
        blockers.append({"source": "project_skill_index_sync", "message": "post-change report must include project_skill_index_requirements"})
    elif index_req.get("required") and index_req.get("status") not in {"satisfied", "waived"}:
        blockers.append({"source": "project_skill_index_sync", "message": "required project skill index sync is not satisfied or waived", "status": index_req.get("status")})

    return {
        "schema": SCHEMA,
        "decision": "block" if blockers else "pass",
        "artifact_dir": str(artifact_dir),
        "blockers": blockers,
        "warnings": warnings,
        "summary": {
            "invalid_json_count": len(invalid_json),
            "acceptance_count": len(acs),
            "gate_decisions": decisions,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate final delivery consistency")
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--out")
    args = parser.parse_args()
    result = validate(Path(args.artifact_dir))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
