#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-test-data-plan-v1"
SENSITIVE_TERMS = {"production", "prod", "real customer", "customer pii", "真实客户", "生产", "真实数据", "身份证", "银行卡", "password", "secret", "token"}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def needs_role(case: dict[str, Any]) -> bool:
    searchable = json.dumps(case, ensure_ascii=False).lower()
    return any(term in searchable for term in ["permission", "role", "tenant", "unauthorized", "权限", "角色", "租户"])


def dataset_for_case(case: dict[str, Any]) -> dict[str, Any]:
    case_id = str(case.get("id") or "TC")
    case_type = str(case.get("type") or "functional")
    strategy = case.get("data_setup_strategy") if isinstance(case.get("data_setup_strategy"), dict) else {}
    roles = ["authorized-user", "restricted-user"] if needs_role(case) else []
    strategy_accounts = [item for item in as_list(strategy.get("accounts")) if isinstance(item, dict)]
    accounts = strategy_accounts or [{"role": role, "source": "synthetic fixture"} for role in roles]
    environment = []
    if case_type in {"frontend", "integration"}:
        environment.append({"name": "test environment", "requirement": "changed service and dependencies are available"})
    strategy_records = [item for item in as_list(strategy.get("records")) if isinstance(item, dict)]
    strategy_cleanup = as_list(strategy.get("cleanup"))
    setup_methods = [str(item) for item in as_list(strategy.get("setup_methods")) if item]
    return {
        "id": str(strategy.get("dataset_ref") or f"TD-{case_id}"),
        "case_ids": [case_id],
        "data_classification": "synthetic",
        "setup_method": "+".join(setup_methods) if setup_methods else "fixture_or_factory",
        "records": strategy_records or [{"name": f"{case_id} representative record", "source": "synthetic fixture", "state": "ready before execution"}],
        "accounts": accounts,
        "roles": roles or [str(item.get("role")) for item in accounts if item.get("role")],
        "tenants": ["synthetic-tenant"] if "tenant" in json.dumps(case, ensure_ascii=False).lower() else [],
        "environment": environment,
        "cleanup": [{"method": str(item), "owner": "test runner"} for item in strategy_cleanup] or [{"method": "delete synthetic fixture data", "owner": "test runner"}],
        "privacy_controls": as_list(strategy.get("privacy")) or ["synthetic-only metadata", "no live identifiers", "safe to commit as fixture metadata"],
        "notes": [f"Supports {case_id}: {case.get('title', '')}"],
    }


def render(test_design: dict[str, Any]) -> dict[str, Any]:
    cases = [item for item in as_list(test_design.get("test_cases")) if isinstance(item, dict)]
    datasets = [dataset_for_case(case) for case in cases]
    gate = test_design.get("requirements_understanding_gate") if isinstance(test_design.get("requirements_understanding_gate"), dict) else {}
    result = {
        "schema": SCHEMA,
        "doc_id": test_design.get("doc_id"),
        "title": test_design.get("title"),
        "source_test_design_decision": test_design.get("decision", ""),
        "requirements_understanding_gate": gate,
        "test_case_count": len(cases),
        "datasets": datasets,
        "case_data_matrix": [{"case_id": case.get("id"), "dataset_ids": [dataset.get("id")]} for case, dataset in zip(cases, datasets)],
        "global_rules": {
            "allowed_data": ["synthetic", "anonymized"],
            "forbidden_data": ["production", "real customer data", "secrets", "tokens", "payment card numbers"],
            "cleanup_required": True,
        },
        "decision": "pass",
        "blockers": [],
    }
    validation = validate_plan(result)
    result["decision"] = validation["decision"]
    result["blockers"] = validation["blockers"]
    result["warnings"] = validation["warnings"]
    return result


def contains_sensitive_value(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False).lower()
    return any(term in text for term in SENSITIVE_TERMS)


def permission_signal_text(dataset: dict[str, Any]) -> str:
    values: list[str] = []
    for key in ["records", "environment", "notes", "tenants"]:
        values.extend(str(item) for item in as_list(dataset.get(key)))
    return " ".join(values).lower()


def validate_plan(data: dict[str, Any]) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if data.get("schema") != SCHEMA:
        blockers.append({"source": "schema", "message": f"schema must be {SCHEMA}"})
    if data.get("source_test_design_decision") == "block":
        blockers.append({"source": "test_design", "message": "test data plan cannot pass while source test design is blocked"})
    gate = data.get("requirements_understanding_gate") if isinstance(data.get("requirements_understanding_gate"), dict) else {}
    if gate.get("design_allowed") is False or gate.get("implementation_allowed") is False:
        blockers.append({"source": "requirements_understanding_gate", "message": "requirement understanding blocks executable test data planning", "gate": gate})
    datasets = [item for item in as_list(data.get("datasets")) if isinstance(item, dict)]
    if not datasets:
        blockers.append({"source": "datasets", "message": "at least one dataset is required"})
    seen_cases: set[str] = set()
    for idx, dataset in enumerate(datasets):
        source = f"datasets[{idx}]"
        dataset_id = str(dataset.get("id") or "")
        case_ids = [str(item) for item in as_list(dataset.get("case_ids")) if item]
        seen_cases.update(case_ids)
        if not dataset_id:
            blockers.append({"source": source, "message": "dataset id is required"})
        if not case_ids:
            blockers.append({"source": source, "message": "case_ids are required"})
        if not dataset.get("setup_method"):
            blockers.append({"source": source, "message": "setup_method is required"})
        if not as_list(dataset.get("cleanup")):
            blockers.append({"source": source, "message": "cleanup is required"})
        classification = str(dataset.get("data_classification") or "").lower()
        if classification not in {"synthetic", "anonymized"}:
            blockers.append({"source": source, "message": "data_classification must be synthetic or anonymized", "classification": classification})
        if contains_sensitive_value(dataset):
            blockers.append({"source": source, "message": "dataset contains forbidden sensitive or production-data terms"})
        searchable = permission_signal_text(dataset)
        if any(term in searchable for term in ["permission", "unauthorized", "role", "tenant"]) and not (as_list(dataset.get("roles")) or as_list(dataset.get("accounts"))):
            blockers.append({"source": source, "message": "permission/tenant dataset requires roles or accounts"})
    matrix = [item for item in as_list(data.get("case_data_matrix")) if isinstance(item, dict)]
    for idx, row in enumerate(matrix):
        case_id = str(row.get("case_id") or "")
        if case_id and not as_list(row.get("dataset_ids")):
            blockers.append({"source": f"case_data_matrix[{idx}]", "message": "dataset_ids are required for mapped cases"})
    if matrix:
        mapped = {str(item.get("case_id")) for item in matrix if item.get("case_id")}
        missing = sorted(mapped - seen_cases)
        if missing:
            blockers.append({"source": "case_data_matrix", "message": "matrix references cases not covered by datasets", "case_ids": missing})
    else:
        warnings.append({"source": "case_data_matrix", "message": "case_data_matrix is recommended"})
    return {
        "schema": "codex-test-data-plan-validation-v1",
        "decision": "block" if blockers else "pass",
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render or validate test data plan")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_render = sub.add_parser("render")
    p_render.add_argument("--test-design", required=True)
    p_render.add_argument("--out", required=True)
    p_validate = sub.add_parser("validate")
    p_validate.add_argument("--file", required=True)
    p_validate.add_argument("--out")
    args = parser.parse_args()
    if args.cmd == "render":
        result = render(load_json(Path(args.test_design)))
        write_json(Path(args.out), result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["decision"] == "pass" else 1
    result = validate_plan(load_json(Path(args.file)))
    if args.out:
        write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
