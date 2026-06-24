#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-test-design-v1"


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


def text_of(*values: Any) -> str:
    return json.dumps(values, ensure_ascii=False).lower()


def render(spec: dict[str, Any], technical: dict[str, Any], architecture: dict[str, Any]) -> dict[str, Any]:
    acceptance = [item for item in as_list(spec.get("acceptance_criteria")) if isinstance(item, dict)]
    requirements = [item for item in as_list(spec.get("requirements")) if isinstance(item, dict)]
    signals = text_of(spec, technical, architecture)
    cases: list[dict[str, Any]] = []
    for idx, ac in enumerate(acceptance or [{"id": "AC-1", "criteria": spec.get("requirement_summary", "")}]):
        cases.append({
            "id": f"TC-{idx + 1}",
            "acceptance_id": str(ac.get("id") or f"AC-{idx + 1}"),
            "type": "functional",
            "title": str(ac.get("criteria") or ac.get("summary") or "verify acceptance criterion"),
            "preconditions": [],
            "steps": ["prepare data", "execute affected behavior", "verify expected result"],
            "expected_result": str(ac.get("criteria") or "acceptance criterion is satisfied"),
            "evidence_required": as_list(ac.get("evidence_required")) or ["test execution evidence"],
        })
    if any(term in signals for term in ["permission", "role", "tenant", "权限", "角色", "租户"]):
        cases.append({"id": "TC-PERM-1", "acceptance_id": "", "type": "permission", "title": "unauthorized role cannot access changed behavior", "preconditions": ["restricted role"], "steps": ["attempt changed behavior"], "expected_result": "access denied or hidden", "evidence_required": ["permission test evidence"]})
    if len(as_list(architecture.get("repo_responsibilities"))) > 1 or "cross" in signals:
        cases.append({"id": "TC-INT-1", "acceptance_id": "", "type": "integration", "title": "cross-component integration remains compatible", "preconditions": ["all changed components deployed"], "steps": ["execute end-to-end flow"], "expected_result": "contracts remain compatible", "evidence_required": ["integration test evidence"]})
    if any(term in signals for term in ["ui", "page", "route", "frontend", "browser"]):
        cases.append({"id": "TC-UI-1", "acceptance_id": "", "type": "frontend", "title": "browser acceptance for changed UI", "preconditions": ["frontend app running"], "steps": ["open changed route", "perform interaction", "check console and network"], "expected_result": "UI behaves correctly with no console/network failures", "evidence_required": ["frontend_acceptance.json"]})
    return {
        "schema": SCHEMA,
        "doc_id": spec.get("doc_id") or technical.get("doc_id") or architecture.get("doc_id"),
        "title": spec.get("title") or technical.get("title") or architecture.get("title"),
        "requirement_count": len(requirements),
        "acceptance_count": len(acceptance),
        "test_cases": cases,
        "regression_scope": [{"area": "affected behavior", "reason": "changed requirement path"}],
        "integration_scope": [case for case in cases if case["type"] == "integration"],
        "frontend_scope": [case for case in cases if case["type"] == "frontend"],
        "permission_scope": [case for case in cases if case["type"] == "permission"],
        "evidence_required": sorted({e for case in cases for e in as_list(case.get("evidence_required"))}),
        "open_risks": [],
    }


def validate_design(data: dict[str, Any]) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if data.get("schema") != SCHEMA:
        blockers.append({"source": "schema", "message": f"schema must be {SCHEMA}"})
    cases = [item for item in as_list(data.get("test_cases")) if isinstance(item, dict)]
    if not cases:
        blockers.append({"source": "test_cases", "message": "at least one test case is required"})
    acceptance_count = int(data.get("acceptance_count") or 0)
    mapped = {case.get("acceptance_id") for case in cases if case.get("acceptance_id")}
    if acceptance_count and len(mapped) < acceptance_count:
        blockers.append({"source": "traceability", "message": "not every acceptance criterion has a mapped test", "mapped": len(mapped), "acceptance_count": acceptance_count})
    for idx, case in enumerate(cases):
        for key in ["id", "type", "title", "steps", "expected_result", "evidence_required"]:
            if not case.get(key):
                blockers.append({"source": f"test_cases[{idx}].{key}", "message": f"{key} is required"})
    if not data.get("regression_scope"):
        warnings.append({"source": "regression_scope", "message": "regression scope is recommended"})
    decision = "block" if blockers else "pass"
    return {"schema": "codex-test-design-validation-v1", "decision": decision, "blockers": blockers, "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser(description="Render or validate test design")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_render = sub.add_parser("render")
    p_render.add_argument("--spec", required=True)
    p_render.add_argument("--technical-design", required=True)
    p_render.add_argument("--architecture-design", required=True)
    p_render.add_argument("--out", required=True)
    p_val = sub.add_parser("validate")
    p_val.add_argument("--file", required=True)
    p_val.add_argument("--out")
    args = parser.parse_args()
    if args.cmd == "render":
        result = render(load_json(Path(args.spec)), load_json(Path(args.technical_design)), load_json(Path(args.architecture_design)))
        write_json(Path(args.out), result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    result = validate_design(load_json(Path(args.file)))
    if args.out:
        write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
