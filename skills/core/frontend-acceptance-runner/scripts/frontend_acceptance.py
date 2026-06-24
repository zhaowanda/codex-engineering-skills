#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-frontend-acceptance-v1"
PAGE_TYPES = {"list", "form", "detail", "export", "dashboard", "custom"}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def boolish(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.lower() in {"true", "pass", "passed", "ready", "ok", "yes"}
    return False


def template(page_type: str, target_url: str) -> dict[str, Any]:
    if page_type not in PAGE_TYPES:
        raise ValueError(f"page_type must be one of: {', '.join(sorted(PAGE_TYPES))}")
    checks: dict[str, Any] = {
        "schema": SCHEMA,
        "target_url": target_url,
        "page_type": page_type,
        "pass": False,
        "environment": "",
        "browser": "",
        "viewport_evidence": [],
        "page_load": {
            "loaded": False,
            "final_url": "",
            "title": "",
            "load_time_ms": None,
        },
        "dom_evidence": [],
        "interaction_evidence": [],
        "screenshot_evidence": [],
        "network_requests": [],
        "failed_requests": [],
        "console_errors": [],
        "permission_checks": [],
        "responsive_checks": [],
        "custom_checks": [],
        "waivers": [],
        "notes": "",
    }
    if page_type == "list":
        checks["list_checks"] = {
            "filters_checked": [],
            "columns_checked": [],
            "pagination_checked": False,
            "empty_state_checked": False,
            "row_actions_checked": [],
        }
    elif page_type == "form":
        checks["form_checks"] = {
            "fields_checked": [],
            "validation_checked": [],
            "submit_checked": False,
            "success_state_checked": False,
            "failure_state_checked": False,
        }
    elif page_type == "detail":
        checks["detail_checks"] = {
            "fields_checked": [],
            "status_checked": False,
            "related_data_checked": [],
            "actions_checked": [],
        }
    elif page_type == "export":
        checks["export_checks"] = {
            "trigger_checked": False,
            "output_evidence": [],
            "row_count_checked": False,
            "file_format_checked": False,
        }
    elif page_type == "dashboard":
        checks["dashboard_checks"] = {
            "cards_checked": [],
            "charts_checked": [],
            "refresh_checked": False,
            "loading_state_checked": False,
        }
    return checks


def waiver_reasons(evidence: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in as_list(evidence.get("waivers")):
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "")
        reason = str(item.get("reason") or "")
        if key and reason:
            result[key] = reason
    return result


def has_visual_or_dom_proof(evidence: dict[str, Any]) -> bool:
    return bool(
        as_list(evidence.get("dom_evidence"))
        or as_list(evidence.get("interaction_evidence"))
        or as_list(evidence.get("screenshot_evidence"))
    )


def validate_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    waivers = waiver_reasons(evidence)
    page_type = str(evidence.get("page_type") or "")

    if evidence.get("schema") != SCHEMA:
        blockers.append({"source": "schema", "message": f"schema must be {SCHEMA}"})
    if page_type not in PAGE_TYPES:
        blockers.append({"source": "page_type", "message": "page_type is missing or unsupported"})
    if not evidence.get("target_url"):
        blockers.append({"source": "target_url", "message": "target_url is required"})

    page_load = evidence.get("page_load") if isinstance(evidence.get("page_load"), dict) else {}
    if not boolish(page_load.get("loaded")):
        blockers.append({"source": "page_load", "message": "page load evidence is missing or not loaded"})
    if not has_visual_or_dom_proof(evidence):
        blockers.append({"source": "evidence", "message": "DOM, interaction, or screenshot proof is required"})

    console_errors = as_list(evidence.get("console_errors"))
    if console_errors:
        blockers.append({"source": "console", "message": "console errors exist", "count": len(console_errors)})

    failed_requests = as_list(evidence.get("failed_requests"))
    if failed_requests and "failed_requests" not in waivers:
        blockers.append({"source": "network", "message": "failed network requests exist", "count": len(failed_requests)})
    elif failed_requests:
        warnings.append({"source": "network", "message": "failed network requests waived", "count": len(failed_requests)})

    permission_checks = as_list(evidence.get("permission_checks"))
    permission_required = boolish(evidence.get("permission_required")) or bool(permission_checks)
    if permission_required:
        if not permission_checks:
            blockers.append({"source": "permission", "message": "permission checks are required but missing"})
        else:
            failed_permission = [item for item in permission_checks if isinstance(item, dict) and not boolish(item.get("pass"))]
            if failed_permission:
                blockers.append({"source": "permission", "message": "permission checks failed", "count": len(failed_permission)})

    responsive_required = boolish(evidence.get("responsive_required"))
    if responsive_required and not as_list(evidence.get("responsive_checks")) and not as_list(evidence.get("viewport_evidence")):
        blockers.append({"source": "responsive", "message": "responsive or viewport evidence is required"})

    if page_type == "form":
        form = evidence.get("form_checks") if isinstance(evidence.get("form_checks"), dict) else {}
        if not as_list(form.get("validation_checked")):
            blockers.append({"source": "form", "message": "form validation evidence is required"})
        if not boolish(form.get("submit_checked")):
            blockers.append({"source": "form", "message": "form submit evidence is required"})
    elif page_type == "export":
        export = evidence.get("export_checks") if isinstance(evidence.get("export_checks"), dict) else {}
        if not boolish(export.get("trigger_checked")):
            blockers.append({"source": "export", "message": "export trigger evidence is required"})
        if not as_list(export.get("output_evidence")):
            blockers.append({"source": "export", "message": "export output evidence is required"})
    elif page_type == "list":
        list_checks = evidence.get("list_checks") if isinstance(evidence.get("list_checks"), dict) else {}
        if not as_list(list_checks.get("columns_checked")):
            warnings.append({"source": "list", "message": "list column evidence is missing"})
        if not as_list(list_checks.get("filters_checked")):
            warnings.append({"source": "list", "message": "list filter evidence is missing"})

    declared_pass = boolish(evidence.get("pass")) or boolish(evidence.get("decision"))
    if declared_pass and blockers:
        blockers.append({"source": "decision", "message": "pass is not allowed while blockers exist"})

    decision = "block" if blockers else "pass"
    return {
        "schema": SCHEMA,
        "decision": decision,
        "pass": decision == "pass",
        "blockers": blockers,
        "warnings": warnings,
        "evidence_summary": {
            "page_type": page_type,
            "target_url": evidence.get("target_url"),
            "dom_evidence_count": len(as_list(evidence.get("dom_evidence"))),
            "interaction_evidence_count": len(as_list(evidence.get("interaction_evidence"))),
            "screenshot_evidence_count": len(as_list(evidence.get("screenshot_evidence"))),
            "failed_request_count": len(failed_requests),
            "console_error_count": len(console_errors),
            "permission_check_count": len(permission_checks),
            "responsive_check_count": len(as_list(evidence.get("responsive_checks"))) + len(as_list(evidence.get("viewport_evidence"))),
        },
        "next_action": "Fix frontend acceptance blockers and rerun validation." if blockers else "Attach frontend_acceptance.json to test and release evidence.",
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or validate frontend acceptance evidence")
    subparsers = parser.add_subparsers(dest="command", required=True)

    template_parser = subparsers.add_parser("template", help="create frontend_acceptance.json template")
    template_parser.add_argument("--page-type", required=True, choices=sorted(PAGE_TYPES))
    template_parser.add_argument("--target-url", required=True)
    template_parser.add_argument("--artifact-dir", required=True)
    template_parser.add_argument("--out")

    validate_parser = subparsers.add_parser("validate", help="validate frontend acceptance evidence")
    validate_parser.add_argument("--file", required=True)
    validate_parser.add_argument("--out")

    args = parser.parse_args()
    if args.command == "template":
        result = template(args.page_type, args.target_url)
        out = Path(args.out) if args.out else Path(args.artifact_dir) / "frontend_acceptance.json"
        write_json(out, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    evidence = load_json(Path(args.file))
    result = validate_evidence(evidence)
    if args.out:
        write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
