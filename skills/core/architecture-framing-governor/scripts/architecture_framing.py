#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "codex-architecture-framing-v1"
FRAMING_TERMS = {
    "new_service": ["new service", "new repo", "new repository", "new project", "新服务", "新工程", "新仓库", "独立服务"],
    "frontend": ["ui", "frontend", "page", "button", "menu", "页面", "按钮", "菜单", "前端"],
    "api": ["api", "endpoint", "route", "接口", "调用", "服务"],
    "mq": ["mq", "topic", "queue", "consumer", "producer", "消息", "队列", "消费", "生产"],
    "scheduled": ["cron", "schedule", "job", "task", "定时", "任务", "手搓"],
    "data": ["database", "table", "field", "schema", "migration", "数据", "表", "字段", "迁移", "状态"],
}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def load_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def blob(*values: Any) -> str:
    return json.dumps(values, ensure_ascii=False).lower()


def has_signal(text: str, names: list[str]) -> bool:
    return any(name.lower() in text or name in text for name in names)


def load_project_understanding(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    base = path if path.is_dir() else path.parent
    result: dict[str, Any] = {}
    for name in ["repository_analysis", "api_surface", "code_index", "baseline"]:
        file = base / f"{name}.json"
        if file.exists():
            result[name] = load_json(file)
    return result


def project_context(project_understanding: dict[str, Any]) -> dict[str, Any]:
    repo = project_understanding.get("repository_analysis", {})
    api = project_understanding.get("api_surface", {})
    index = project_understanding.get("code_index", {})
    baseline = project_understanding.get("baseline", {})
    project = str(repo.get("project") or api.get("project") or baseline.get("project") or "needs_confirmation")
    repo_root = str(index.get("repo_root") or baseline.get("repo_root") or repo.get("repo_root") or "")
    entrypoints = [str(item) for item in as_list(repo.get("entrypoint_hints"))]
    files = [str(item.get("path")) for item in as_list(index.get("files")) if isinstance(item, dict) and item.get("path")]
    routes = [item for item in as_list(api.get("routes")) if isinstance(item, dict)]
    return {"project": project, "repo_root": repo_root, "entrypoints": entrypoints, "files": files, "routes": routes}


def source_entrypoints(spec: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in as_list(spec.get("entrypoints")):
        value = json.dumps(item, ensure_ascii=False) if isinstance(item, dict) else str(item)
        rows.append({"kind": classify_entrypoint(value), "trigger": value, "source": "spec.entrypoints"})
    for item in as_list(spec.get("source_trace")):
        value = str(item.get("text") or item.get("line") or item.get("content") or "") if isinstance(item, dict) else str(item)
        if any(token in value for token in ["入口", "Entry", "entry", "触发"]):
            rows.append({"kind": classify_entrypoint(value), "trigger": value.split(":", 1)[-1].split("：", 1)[-1].strip(), "source": "spec.source_trace"})
    return rows


def classify_entrypoint(value: str) -> str:
    lower = value.lower()
    if has_signal(lower, FRAMING_TERMS["frontend"]):
        return "frontend_action"
    if has_signal(lower, FRAMING_TERMS["mq"]):
        return "mq_consumer"
    if has_signal(lower, FRAMING_TERMS["scheduled"]):
        return "scheduled_or_manual_task"
    if has_signal(lower, FRAMING_TERMS["api"]):
        return "api"
    return "business_entrypoint"


def impact_areas(spec: dict[str, Any]) -> set[str]:
    return {str(item.get("area") or "") for item in as_list(spec.get("impact_surface")) if isinstance(item, dict) and item.get("area")}


def design(spec: dict[str, Any], domain_model: dict[str, Any] | None = None, project_understanding: dict[str, Any] | None = None) -> dict[str, Any]:
    domain_model = domain_model or {}
    ctx = project_context(project_understanding or {})
    text = blob(spec, domain_model, project_understanding)
    impacts = impact_areas(spec)
    signals = {name: has_signal(text, terms) or name in impacts for name, terms in FRAMING_TERMS.items()}
    new_service = bool(signals["new_service"])
    owner_repo = ctx["project"]
    owner_known = owner_repo != "needs_confirmation"
    entrypoints = source_entrypoints(spec)
    if not entrypoints:
        entrypoints = [{"kind": "business_entrypoint", "trigger": "needs_confirmation", "source": "inferred_missing"}]
    dependency_edges = []
    if signals["api"]:
        route = next((f"{item.get('method', '')} {item.get('route', '')}".strip() for item in ctx["routes"] if item.get("route")), "api contract needs_confirmation")
        dependency_edges.append({"from": "api_provider_needs_confirmation", "to": owner_repo, "contract": route, "degree": 1, "change": "confirm provider/consumer before technical design"})
    if signals["mq"]:
        dependency_edges.append({"from": "mq_producer_needs_confirmation", "to": "mq_consumer_needs_confirmation", "contract": "topic_or_queue needs_confirmation", "degree": 1, "change": "confirm topic, payload, retry, dead-letter"})
    if not dependency_edges:
        dependency_edges.append({"from": owner_repo, "to": owner_repo, "contract": "internal owner boundary", "degree": 0, "change": "owner-scoped change"})
    max_degree = max(int(edge.get("degree") or 0) for edge in dependency_edges)
    blockers: list[dict[str, str]] = []
    if not owner_known:
        blockers.append({"source": "owner_repo", "message": "Owner repository/system is not confirmed by project understanding."})
    if entrypoints[0]["trigger"] == "needs_confirmation":
        blockers.append({"source": "runtime_entrypoints", "message": "Runtime entrypoint trigger is missing."})
    if new_service and not owner_known:
        blockers.append({"source": "new_service", "message": "New-service decision requires rejected existing owners and repository bootstrap evidence."})
    if signals["data"] and not as_list(spec.get("business_objects")):
        blockers.append({"source": "data_ownership", "message": "Data impact exists but business object/data owner is not confirmed."})
    decision_type = "new_service_required" if new_service else "modify_existing_system"
    return {
        "schema": SCHEMA,
        "doc_id": spec.get("doc_id"),
        "title": spec.get("title"),
        "decision": "block" if blockers else "pass",
        "system_boundary": {
            "decision_type": decision_type,
            "owner_repo": owner_repo,
            "owner_repo_path": ctx["repo_root"],
            "new_service_decision": {
                "required": new_service,
                "creation_reason": "new-service signal detected in requirement" if new_service else "existing owner boundary is preferred",
                "rejected_existing_owners": [] if not new_service else ["needs_confirmation"],
            },
        },
        "repo_responsibilities": [
            {"repo": owner_repo, "role": "modify" if owner_known else "confirm_only", "responsibility": "own changed behavior after boundary confirmation"},
        ],
        "runtime_entrypoints": entrypoints,
        "dependency_graph": {
            "degree": max_degree,
            "classification": "owner_only" if max_degree == 0 else "one_degree" if max_degree == 1 else "multi_degree",
            "edges": dependency_edges,
        },
        "provider_consumer": [{"provider": edge["from"], "consumer": edge["to"], "contract": edge["contract"]} for edge in dependency_edges],
        "data_ownership": [
            {
                "business_object": str(item.get("name") if isinstance(item, dict) else item),
                "owner_repo": owner_repo,
                "write_authority": owner_repo,
                "confirmation_required": not owner_known,
            }
            for item in (as_list(spec.get("business_objects")) or as_list(domain_model.get("business_objects")))
        ],
        "release_order": [{"order": 1, "repo": owner_repo, "reason": "owner boundary deploys first unless provider/consumer contract changes"}],
        "rollback_boundary": [{"repo": owner_repo, "rollback": "revert owner repo artifact; handle data/contract rollback only if specialty design requires it"}],
        "technical_design_inputs": {
            "must_consume": ["architecture_framing.json"],
            "specialty_designs": [
                name
                for name, enabled in [
                    ("ui_ue_design.json", signals["frontend"]),
                    ("api_contract_design.json", signals["api"]),
                    ("data_model_design.json", signals["data"]),
                    ("observability_design.json", True),
                ]
                if enabled
            ],
        },
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate pre-technical architecture framing")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--domain-model-design")
    parser.add_argument("--project-understanding")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = design(
        load_json(Path(args.spec)),
        load_json(Path(args.domain_model_design)) if args.domain_model_design else {},
        load_project_understanding(Path(args.project_understanding)) if args.project_understanding else {},
    )
    write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("decision") == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
