#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


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


GENERIC_CONTRACT_FILES = {
    "package.json",
    "package-lock.json",
    "vue.config.js",
    "babel.config.js",
    "readme.md",
}


def is_business_route(route: dict[str, Any]) -> bool:
    route_path = str(route.get("route") or "").strip()
    file = str(route.get("file") or "").strip()
    if not route_path or route_path in {"/", "*"}:
        return False
    name = Path(file.lower()).name
    if name in GENERIC_CONTRACT_FILES:
        return False
    if file.lower().endswith((".md", ".json", ".yml", ".yaml", ".config.js", ".config.ts")):
        return False
    return True


def route_ref(route: dict[str, Any]) -> str:
    return f"{route.get('method', '')} {route.get('route', '')} ({route.get('file', '')})".strip()


def load_project_understanding(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    base = path if path.is_dir() else path.parent
    if not base.exists():
        return {}
    result: dict[str, Any] = {}
    bundle_file = base / "evidence_bundle.json"
    if bundle_file.exists():
        result["evidence_bundle"] = load_json(bundle_file)
        for name in ["repository_analysis", "dependency_surface"]:
            file = base / f"{name}.json"
            if file.exists():
                result[name] = load_json(file)
        return result
    for name in ["repository_analysis", "api_surface", "config_surface", "dependency_surface", "code_index", "baseline", "baseline_quality"]:
        file = base / f"{name}.json"
        if file.exists():
            result[name] = load_json(file)
    return result


def project_context(project_understanding: dict[str, Any]) -> dict[str, Any]:
    bundle = project_understanding.get("evidence_bundle", {})
    repo = project_understanding.get("repository_analysis", {})
    index = project_understanding.get("code_index", {})
    baseline = project_understanding.get("baseline", {})
    api = project_understanding.get("api_surface", {})
    deps = project_understanding.get("dependency_surface", {})
    project = str(bundle.get("project") or repo.get("project") or baseline.get("project") or api.get("project") or "target-repo")
    repo_path = str(bundle.get("repo_root") or index.get("repo_root") or baseline.get("repo_root") or repo.get("repo_root") or "")
    modules = [str(item.get("module")) for item in as_list(baseline.get("module_hints")) if isinstance(item, dict) and item.get("module")]
    if not modules:
        modules = [str(item) for item in as_list(repo.get("top_level_directories"))]
    modules = [item for item in modules if item not in {".github", ".git", "tests", "__pycache__"}] or modules
    routes = [item for item in as_list(api.get("routes")) if isinstance(item, dict) and is_business_route(item)]
    if bundle:
        anchors = [item for item in as_list(bundle.get("confirmed_anchors")) if isinstance(item, dict) and item.get("path")]
        modules = sorted({str(Path(str(item["path"])).parent) for item in anchors})
        routes = [{"method": "", "route": str(contract), "file": "evidence_bundle.json"} for contract in as_list(bundle.get("contracts"))]
    tests = [str(item) for item in as_list(deps.get("test_command_hints"))] or [str(item) for item in as_list(repo.get("test_hints"))]
    return {"project": project, "repo_path": repo_path, "modules": modules, "routes": routes, "tests": tests}


def option_score_summary(options: list[dict[str, Any]], matrix: list[dict[str, Any]]) -> dict[str, Any]:
    scores = {str(option["option_id"]): 0 for option in options if option.get("option_id")}
    for row in matrix:
        weight = int(row.get("weight") or 1)
        for option_id, score in (row.get("scores") or {}).items():
            if option_id in scores:
                scores[option_id] += weight * int(score)
    max_score = max(scores.values()) if scores else 1
    normalized = {key: round(value * 100 / max_score) for key, value in scores.items()}
    normalized["scoring_rule"] = "Architecture scores are weighted from ownership, contract, release, observability, and rollback evidence."
    return normalized


def selected_from_scores(score_summary: dict[str, Any]) -> str:
    numeric = {key: value for key, value in score_summary.items() if key != "scoring_rule" and isinstance(value, int | float)}
    return max(numeric, key=numeric.get) if numeric else ""


def architecture_option_name(option_id: str, owner_repo: str) -> str:
    if option_id == "A1":
        return f"以 `{owner_repo}` 为单一责任边界推进"
    if option_id == "A2":
        return "以生产方/消费方契约为架构边界推进"
    if option_id == "A3":
        return "以数据口径和发布顺序为优先边界推进"
    return option_id


def architecture_selection_reason(selected_id: str, owner_repo: str, owner_module: str, summary: str, options: list[dict[str, Any]]) -> str:
    selected = next((item for item in options if item.get("option_id") == selected_id), {})
    selected_name = str(selected.get("name") or selected_id)
    if selected_id == "A1":
        return (
            f"选择 {selected_id}（{selected_name}），因为当前需求「{summary}」的主要变更可以由 `{owner_repo}` 和 `{owner_module}` 承担，"
            "暂未看到必须先调整跨仓契约或数据发布顺序的证据。该架构发布顺序最短，回滚责任最清晰。"
        )
    if selected_id == "A2":
        return (
            f"选择 {selected_id}（{selected_name}），因为当前需求「{summary}」需要生产方和消费方共同稳定契约，"
            "必须先冻结接口语义、兼容策略和集成验证，再进入实现。"
        )
    if selected_id == "A3":
        return (
            f"选择 {selected_id}（{selected_name}），因为当前需求「{summary}」受数据口径、历史记录或迁移/回滚策略主导，"
            "需要先完成数据兼容证据和发布顺序设计。"
        )
    if "权限" in selected_name:
        return (
            f"选择 {selected_id}（{selected_name}），因为当前需求「{summary}」需要把前端入口、后端鉴权、角色/租户数据和负向证据作为同一架构边界，"
            "否则只调整单侧实现会留下越权或验收不可证明风险。"
        )
    if "子域" in selected_name:
        return (
            f"选择 {selected_id}（{selected_name}），因为当前需求「{summary}」包含多个业务子域，"
            "按子域分阶段绑定责任、证据和回滚点，比单一责任边界更利于评审、发布观察和问题定位。"
        )
    if "灰度" in selected_name or "兼容" in selected_name:
        return (
            f"选择 {selected_id}（{selected_name}），因为当前需求「{summary}」需要保护旧消费方或降低一次性切换风险，"
            "应通过兼容字段、灰度开关和新旧契约证据控制发布。"
        )
    return f"选择 {selected_id}（{selected_name}），因为它最符合当前架构证据。"


def architecture_rejected_reason(option: dict[str, Any], selected_score: Any, option_score: Any) -> str:
    option_id = str(option.get("option_id"))
    name = str(option.get("name") or option_id)
    if "契约" in name or "消费方" in name:
        return (
            f"暂不选择 {option_id}（{name}）：当前证据还不足以证明必须扩大到生产方/消费方协同发布；"
            "若代码检查发现契约字段、响应语义或多个消费方必须同步变化，再切换到该架构。"
            f"本轮评分 {option_score}，低于选中方案 {selected_score}。"
        )
    if "数据" in name:
        return (
            f"暂不选择 {option_id}（{name}）：当前证据还不足以证明数据迁移、历史数据或回滚数据风险是主导约束；"
            "若实现前发现字段口径或旧数据会影响验收，再切换到该架构。"
            f"本轮评分 {option_score}，低于选中方案 {selected_score}。"
        )
    if "权限" in name:
        return (
            f"暂不选择 {option_id}（{name}）：当前证据还不足以证明权限链路需要成为架构主边界；"
            "若前端入口、后端鉴权、角色数据范围必须协同发布，再切换到该架构。"
            f"本轮评分 {option_score}，低于选中方案 {selected_score}。"
        )
    if "子域" in name:
        return (
            f"暂不选择 {option_id}（{name}）：当前证据下仍可先保持单一责任边界；"
            "若多个子域需要不同发布、验证或回滚节奏，再切换到该架构。"
            f"本轮评分 {option_score}，低于选中方案 {selected_score}。"
        )
    return f"暂不选择 {option_id}（{name}）：当前证据下发布协同、兼容或回滚成本高于选中方案。本轮评分 {option_score}，低于选中方案 {selected_score}。"


def next_arch_option_id(options: list[dict[str, Any]]) -> str:
    return f"A{len(options) + 1}"


def arch_option_ids_matching(options: list[dict[str, Any]], *needles: str) -> set[str]:
    matched: set[str] = set()
    for option in options:
        option_id = str(option.get("option_id") or "")
        name = str(option.get("name") or "")
        if option_id and any(needle in name for needle in needles):
            matched.add(option_id)
    return matched


def arch_winner_from_scores(scores: dict[str, int]) -> str:
    return max(scores, key=scores.get) if scores else ""


def build_architecture_options(
    owner_repo: str,
    owner_module: str,
    producer: str,
    route_contract: str,
    breakdown: list[dict[str, Any]],
    technical: dict[str, Any],
    summary: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    impacts = {str(value) for item in breakdown for value in as_list(item.get("impact_areas"))}
    impacts.update(
        str(item.get("area"))
        for item in as_list(technical.get("impact_applicability"))
        if isinstance(item, dict) and item.get("area") and item.get("status") == "required"
    )
    technical_selected = (technical.get("selected_solution") or {}).get("selected_option_id")
    selected_technical_option = next(
        (option for option in as_list(technical.get("solution_options")) if isinstance(option, dict) and option.get("option_id") == technical_selected),
        {},
    )
    options: list[dict[str, Any]] = [
        {
            "option_id": "A1",
            "name": architecture_option_name("A1", owner_repo),
            "description": f"将架构责任收敛在 `{owner_repo}`，由 `{owner_module}` 承接 {len(breakdown)} 个业务切片的实现和验证。",
            "when_to_choose": [f"`{owner_repo}` 持有选中技术方案 {technical_selected or 'unknown'} 的主要责任", "跨仓契约不需要破坏性变化"],
            "owner_repos": [owner_repo],
            "confirm_only_repos": [producer] if producer != owner_repo else ["none"],
            "integration_impact": f"验证既有依赖 `{route_contract or owner_repo + ' internal contract'}`，不新增跨仓集成顺序。",
            "deployment_impact": f"`{owner_module}` 相关测试通过后发布 `{owner_repo}`。",
            "rollback_complexity": "low",
            "pros": ["责任边界清晰", "发布路径短", "回滚保持在责任仓库内"],
            "cons": ["共享业务规则后续可能仍需抽取", "责任模块需要承接所有选中业务切片"],
            "risk_level": "low" if len(breakdown) <= 3 else "medium",
            "risk_controls": ["repo responsibility review", "allowed_files bound to module topology", "acceptance evidence per business slice"],
            "validation": "owner repo tests plus mapped acceptance evidence",
            "performance_impact": "limited to owner repo unless technical option adds remote calls or data migration",
            "rollback_strategy": f"revert `{owner_repo}` changes and redeploy previous artifact",
        },
        {
            "option_id": "A2",
            "name": architecture_option_name("A2", owner_repo),
            "description": f"当生产方和消费方行为必须一起变化时，将 `{route_contract or '受影响契约'}` 作为显式架构边界。",
            "when_to_choose": ["生产方持有事实源规则", "多个消费方或仓库需要相同行为"],
            "owner_repos": [producer, owner_repo] if producer != owner_repo else [owner_repo, "consumer-repo"],
            "confirm_only_repos": [owner_repo] if producer != owner_repo else ["provider/consumer owners"],
            "integration_impact": "需要冻结契约、完成兼容性测试，并按生产方/消费方顺序验证。",
            "deployment_impact": "生产方先提供兼容发布，消费方再依赖新契约行为。",
            "rollback_complexity": "medium",
            "pros": ["跨仓契约清晰", "多个消费方共享规则时更稳"],
            "cons": ["发布协同成本更高", "兼容和回滚负担更重"],
            "risk_level": "medium",
            "risk_controls": ["contract freeze point", "consumer compatibility evidence", "ordered rollback plan"],
            "validation": "contract, provider, consumer, and regression evidence",
            "performance_impact": "review payload/query/latency impact across the boundary",
            "rollback_strategy": "rollback consumers before provider if compatibility fails",
        },
    ]
    if "data" in impacts:
        options.append({
            "option_id": next_arch_option_id(options),
            "name": architecture_option_name("A3", owner_repo),
            "description": "把数据归属、迁移/无需迁移证据和回滚安全作为主导架构边界。",
            "when_to_choose": ["字段语义变化影响正确性", "历史记录、空值或默认值会影响验收"],
            "owner_repos": [owner_repo],
            "confirm_only_repos": ["数据 owner 或 DBA 评审"],
            "integration_impact": "代码发布需要与迁移/回填或无需迁移证明协同。",
            "deployment_impact": "全量发布前必须先具备数据兼容证据。",
            "rollback_complexity": "medium",
            "pros": ["数据正确性边界明确", "实现前先评审回滚数据风险"],
            "cons": ["发布准备更慢", "需要更强的数据证据"],
            "risk_level": "medium",
            "risk_controls": ["migration strategy", "old-data regression evidence", "rollback data-risk review"],
            "validation": "data compatibility and regression evidence",
            "performance_impact": "review query/filter/index changes",
            "rollback_strategy": "rollback code first and follow data rollback/migration policy",
        })
    if "permission" in impacts or "权限测试" in impacts:
        options.append({
            "option_id": next_arch_option_id(options),
            "name": "以前后端权限闭环为架构边界推进",
            "description": "将前端入口可见性、后端鉴权、角色/租户数据范围和负向权限证据作为同一个架构边界管理。",
            "when_to_choose": ["权限或数据范围是验收的一部分", "只调整前端入口可见性不足以降低越权风险"],
            "owner_repos": [owner_repo],
            "confirm_only_repos": [producer] if producer != owner_repo else ["权限/账号 owner"],
            "integration_impact": "需要权限账号、角色数据和后端鉴权证据配合验证。",
            "deployment_impact": "发布前必须先完成权限正反向验收和账号数据准备。",
            "rollback_complexity": "medium",
            "pros": ["越权风险边界清楚", "前后端权限语义一致"],
            "cons": ["需要额外账号和数据准备", "权限回归范围更大"],
            "risk_level": "medium",
            "risk_controls": ["permission negative evidence", "role fixture review", "server authorization confirmation"],
            "validation": "permission positive/negative and regression evidence",
            "performance_impact": "review permission lookup cost only if authorization path changes",
            "rollback_strategy": "rollback UI visibility and authorization changes together",
        })
    technical_has_subdomain = any("子域" in str(option.get("name") or "") for option in as_list(technical.get("solution_options")) if isinstance(option, dict))
    if (len(breakdown) >= 5 and len(impacts & {"ui", "api", "data", "permission", "权限测试", "business_flow"}) >= 3) or technical_has_subdomain:
        options.append({
            "option_id": next_arch_option_id(options),
            "name": "按业务子域分阶段发布架构",
            "description": f"将 {max(len(breakdown), len(as_list(technical.get('acceptance_mapping'))))} 个业务切片/验收点拆成若干子域，按页面、接口、数据、权限或批量流程分别绑定责任、证据和回滚点。",
            "when_to_choose": ["一个需求包含多个业务子域", "一次性单模块发布会让验收、观测或回滚定位困难"],
            "owner_repos": [owner_repo],
            "confirm_only_repos": [producer] if producer != owner_repo else ["测试/发布 owner"],
            "integration_impact": "每个子域需要独立追踪验收证据，跨子域依赖需要在发布计划中排序。",
            "deployment_impact": "允许按子域分阶段发布；若不能分阶段，则至少按子域准备回滚说明。",
            "rollback_complexity": "medium",
            "pros": ["复杂需求可分块评审和验证", "问题定位和回滚责任更清晰"],
            "cons": ["交付计划更复杂", "需要维护子域级追踪关系"],
            "risk_level": "medium",
            "risk_controls": ["subdomain delivery plan", "per-domain evidence", "staged rollback note"],
            "validation": "per-domain acceptance and regression evidence",
            "performance_impact": "review each subdomain's query/render cost separately",
            "rollback_strategy": "rollback affected subdomain first when coupling allows; otherwise revert full requirement branch",
        })
    if route_contract and len(options) < 5:
        options.append({
            "option_id": next_arch_option_id(options),
            "name": "向后兼容灰度契约架构",
            "description": "在不破坏旧消费方的前提下，用兼容字段、双读/兜底或灰度开关承接契约变化。",
            "when_to_choose": ["接口语义需要变化但旧消费方不能同步发布", "需要降低一次性切换风险"],
            "owner_repos": [producer, owner_repo] if producer != owner_repo else [owner_repo],
            "confirm_only_repos": ["old consumers"],
            "integration_impact": "需要同时验证旧契约、新契约和灰度切换路径。",
            "deployment_impact": "先发布兼容生产方，再逐步切换消费方。",
            "rollback_complexity": "medium",
            "pros": ["旧消费方风险低", "支持灰度和快速回退"],
            "cons": ["短期兼容逻辑增加复杂度", "需要更多契约测试"],
            "risk_level": "medium",
            "risk_controls": ["dual contract tests", "gray switch rollback", "old consumer evidence"],
            "validation": "old/new contract and gray release evidence",
            "performance_impact": "review dual-read or compatibility branch cost",
            "rollback_strategy": "turn off gray switch first, then rollback producer/consumer if needed",
        })
    option_ids = [str(option["option_id"]) for option in options]
    contract_option_ids = arch_option_ids_matching(options, "契约")
    data_option_ids = arch_option_ids_matching(options, "数据")
    permission_option_ids = arch_option_ids_matching(options, "权限")
    subdomain_option_ids = arch_option_ids_matching(options, "子域")
    gray_option_ids = arch_option_ids_matching(options, "灰度", "兼容")
    high_risk_impacts = impacts & {"ui", "api", "data", "permission", "权限测试", "business_flow"}
    technical_selected_subdomain = "子域" in str(selected_technical_option.get("name") or "")
    complex_multi_surface = (len(breakdown) >= 5 and len(high_risk_impacts) >= 3) or technical_selected_subdomain
    matrix: list[dict[str, Any]] = []

    scores = {oid: (3 if oid == "A1" and complex_multi_surface else 5 if oid == "A1" else 4 if oid in data_option_ids else 3) for oid in option_ids}
    matrix.append({"criterion": "责任清晰度", "weight": 5, "scores": scores, "winner": arch_winner_from_scores(scores), "reason": f"A1 将责任收敛在 `{owner_repo}` 和 `{owner_module}`；专项架构只有在对应风险成为主导时才优先。"})

    scores = {
        oid: (
            5 if oid in contract_option_ids and route_contract else
            3 if oid == "A1" and complex_multi_surface else
            4 if oid == "A1" else
            3
        )
        for oid in option_ids
    }
    matrix.append({"criterion": "契约风险", "weight": 5, "scores": scores, "winner": arch_winner_from_scores(scores), "reason": "只有路由、生产方契约或旧消费方兼容是主导风险时，契约架构才优先。"})

    scores = {
        oid: (
            5 if oid in data_option_ids and "data" in impacts else
            4 if oid == "A1" else
            3
        )
        for oid in option_ids
    }
    matrix.append({"criterion": "数据安全性", "weight": 4, "scores": scores, "winner": arch_winner_from_scores(scores), "reason": "字段、历史数据或迁移语义主导正确性时，数据优先架构才优先。"})

    if permission_option_ids:
        scores = {oid: (5 if oid in permission_option_ids else 4 if oid == "A1" else 3) for oid in option_ids}
        matrix.append({"criterion": "权限闭环完整性", "weight": 5, "scores": scores, "winner": arch_winner_from_scores(scores), "reason": "权限需求必须比较前端入口、后端鉴权、角色/租户数据和负向证据是否同边界管理。"})

    if subdomain_option_ids:
        scores = {oid: (5 if oid in subdomain_option_ids else 3 if oid == "A1" and complex_multi_surface else 4 if oid == "A1" else 3) for oid in option_ids}
        matrix.append({"criterion": "子域发布可控性", "weight": 5 if complex_multi_surface else 4, "scores": scores, "winner": arch_winner_from_scores(scores), "reason": "多个业务切片需要比较是否按子域分阶段发布、观测和回滚。"})

    if gray_option_ids:
        scores = {oid: (5 if oid in gray_option_ids else 4 if oid in contract_option_ids else 3) for oid in option_ids}
        matrix.append({"criterion": "灰度兼容能力", "weight": 4, "scores": scores, "winner": arch_winner_from_scores(scores), "reason": "旧消费方不能同步发布时，需要显式比较兼容字段、双路径和灰度回退能力。"})

    scores = {oid: (3 if oid == "A1" and complex_multi_surface else 5 if oid == "A1" else 4 if oid in gray_option_ids or oid in subdomain_option_ids else 3) for oid in option_ids}
    matrix.append({"criterion": "发布协同", "weight": 4, "scores": scores, "winner": arch_winner_from_scores(scores), "reason": "单责任仓发布顺序最短；灰度兼容可降低跨方同步发布压力。"})

    scores = {oid: (3 if oid == "A1" and complex_multi_surface else 5 if oid == "A1" else 4 if oid in gray_option_ids or oid in subdomain_option_ids else 3) for oid in option_ids}
    matrix.append({"criterion": "回滚可控性", "weight": 4, "scores": scores, "winner": arch_winner_from_scores(scores), "reason": "除非数据、契约、权限或子域风险成为主导约束，A1 的回滚链路最短。"})
    score_summary = option_score_summary(options, matrix)
    selected_id = selected_from_scores(score_summary)
    selected = {
        "selected_option_id": selected_id,
        "selection_reason": architecture_selection_reason(selected_id, owner_repo, owner_module, summary, options),
        "decision_criteria": [str(row["criterion"]) for row in matrix],
        "tradeoffs": [f"接受的取舍：{next((option['cons'][0] for option in options if option['option_id'] == selected_id), '架构风险需要持续监控')}", "如果代码检查改变契约归属、数据归属或发布顺序假设，需要回到候选架构重新评审"],
        "rejected_alternative_reasoning": [
            {"option_id": option["option_id"], "reason": architecture_rejected_reason(option, score_summary.get(selected_id), score_summary.get(option["option_id"]))}
            for option in options
            if option["option_id"] != selected_id
        ],
    }
    return options, matrix, score_summary, selected


def render(spec: dict[str, Any], technical: dict[str, Any], project_understanding: dict[str, Any] | None = None, architecture_framing: dict[str, Any] | None = None) -> dict[str, Any]:
    architecture_framing = architecture_framing or {}
    ctx = project_context(project_understanding or {})
    doc_id = str(spec.get("doc_id") or technical.get("doc_id") or "")
    title = str(spec.get("title") or technical.get("title") or "")
    summary = str(spec.get("requirement_summary") or title)
    reqs = [item for item in as_list(spec.get("requirements")) if isinstance(item, dict)]
    req_id = str(reqs[0].get("id") if reqs else "REQ-1")
    framing_boundary = architecture_framing.get("system_boundary") if isinstance(architecture_framing.get("system_boundary"), dict) else {}
    owner_repo = str(framing_boundary.get("owner_repo") or ctx["project"])
    repo_path = ctx["repo_path"]
    breakdown = [item for item in as_list(technical.get("requirement_breakdown")) if isinstance(item, dict)] or [
        {"id": str(item.get("id") or req_id), "summary": str(item.get("summary") or summary), "impact_areas": ["behavior"]}
        for item in reqs
        if isinstance(item, dict)
    ] or [{"id": req_id, "summary": summary, "impact_areas": ["behavior"]}]
    entrypoint_confidence = technical.get("code_entrypoint_confidence") if isinstance(technical.get("code_entrypoint_confidence"), dict) else {}
    tech_modules = [
        str(item.get("module"))
        for item in as_list(technical.get("module_decomposition"))
        if isinstance(item, dict) and item.get("module")
    ]
    owner_module = tech_modules[0] if tech_modules else (ctx["modules"][0] if ctx["modules"] else "target module to be confirmed")
    route_contract = ""
    producer = owner_repo
    technical_contracts = [
        item for item in as_list(technical.get("api_contracts"))
        if isinstance(item, dict) and item.get("contract") and "No API impact confirmed" not in str(item.get("contract"))
    ]
    if technical_contracts:
        route_contract = str(technical_contracts[0].get("contract") or "")
        producer = owner_repo
    applicability = {str(item.get("area")): str(item.get("status")) for item in as_list(spec.get("impact_applicability")) if isinstance(item, dict)}
    impact_areas = {area for area, status in applicability.items() if status == "required"} if applicability else {str(item.get("area")) for item in as_list(spec.get("impact_surface")) if isinstance(item, dict)}
    readiness_gaps = [item for item in as_list(spec.get("expert_readiness_gaps")) if isinstance(item, dict)]
    technical_understanding_gate = technical.get("requirements_understanding_gate") if isinstance(technical.get("requirements_understanding_gate"), dict) else {}
    spec_understanding = spec.get("requirements_understanding") if isinstance(spec.get("requirements_understanding"), dict) else {}
    design_allowed = bool(spec.get("design_allowed", technical_understanding_gate.get("design_allowed", spec_understanding.get("design_allowed", True))))
    implementation_allowed = bool(spec.get("implementation_allowed", technical_understanding_gate.get("implementation_allowed", spec_understanding.get("implementation_allowed", design_allowed))))
    requirements_understanding_gate = {
        "decision": technical_understanding_gate.get("decision") or spec_understanding.get("decision") or ("pass" if design_allowed else "needs_clarification"),
        "design_allowed": design_allowed,
        "implementation_allowed": implementation_allowed and design_allowed,
        "understanding_confidence": spec.get("understanding_confidence") or technical_understanding_gate.get("understanding_confidence") or spec_understanding.get("confidence") or ("high" if design_allowed else "low"),
        "business_intent": spec.get("business_intent") or technical_understanding_gate.get("business_intent") or spec_understanding.get("business_intent") or "",
        "business_flow": spec.get("business_flow") or technical_understanding_gate.get("business_flow") or spec_understanding.get("business_flow") or [],
        "business_flow_model": spec.get("business_flow_model") or technical_understanding_gate.get("business_flow_model") or spec_understanding.get("business_flow_model") or {},
        "business_closure_model": spec.get("business_closure_model") or technical_understanding_gate.get("business_closure_model") or spec_understanding.get("business_closure_model") or {},
        "entrypoints": spec.get("entrypoints") or technical_understanding_gate.get("entrypoints") or spec_understanding.get("entrypoints") or [],
        "current_business_state": spec.get("current_business_state") or technical_understanding_gate.get("current_business_state") or spec_understanding.get("current_business_state") or {},
        "current_state_evidence": spec.get("current_state_evidence") or technical_understanding_gate.get("current_state_evidence") or spec_understanding.get("current_state_evidence") or [],
        "evidence_match_table": spec.get("evidence_match_table") or technical_understanding_gate.get("evidence_match_table") or spec_understanding.get("evidence_match_table") or [],
        "state_machine": spec.get("state_machine") or technical_understanding_gate.get("state_machine") or spec_understanding.get("state_machine") or {},
        "business_goal_quality": spec.get("business_goal_quality") or technical_understanding_gate.get("business_goal_quality") or spec_understanding.get("business_goal_quality") or {},
        "repo_impact_map": spec.get("repo_impact_map") or technical_understanding_gate.get("repo_impact_map") or spec_understanding.get("repo_impact_map") or {},
        "dependency_chain": spec.get("dependency_chain") or technical_understanding_gate.get("dependency_chain") or spec_understanding.get("dependency_chain") or {},
        "runtime_dependency_graph": spec.get("runtime_dependency_graph") or technical_understanding_gate.get("runtime_dependency_graph") or spec_understanding.get("runtime_dependency_graph") or {},
        "trigger_conditions": spec.get("trigger_conditions") or technical_understanding_gate.get("trigger_conditions") or spec_understanding.get("trigger_conditions") or [],
        "preconditions": spec.get("preconditions") or technical_understanding_gate.get("preconditions") or spec_understanding.get("preconditions") or [],
        "postconditions": spec.get("postconditions") or technical_understanding_gate.get("postconditions") or spec_understanding.get("postconditions") or [],
        "blockers": as_list(technical_understanding_gate.get("blockers")) or as_list(spec_understanding.get("blockers")),
        "ambiguities": as_list(technical_understanding_gate.get("ambiguities")) or as_list(spec.get("ambiguities")),
        "required_action": "resolve requirement clarification questions before architecture can be treated as delivery-ready" if not design_allowed else "none",
    }
    if not design_allowed:
        architecture_confidence = "low"
    elif readiness_gaps or not repo_path or entrypoint_confidence.get("level") in {"low", "medium"}:
        architecture_confidence = "medium"
    else:
        architecture_confidence = "high"
    architecture_options, architecture_fit_matrix, architecture_score_summary, selected_architecture = build_architecture_options(owner_repo, owner_module, producer, route_contract, breakdown, technical, summary)
    technical_modules = [item for item in as_list(technical.get("module_decomposition")) if isinstance(item, dict) and item.get("module")]
    module_topology = [{
        "repo": owner_repo,
        "module": str(item.get("module")),
        "responsibility": str(item.get("responsibility") or summary),
        "depends_on": as_list(item.get("dependencies")) or ["existing API/config dependencies"],
        "boundary_rule": "keep change inside confirmed source modules unless reviewed evidence expands scope",
        "change_type": "modify",
        "requirement_breakdown_id": item.get("requirement_breakdown_id"),
        "entrypoint_confidence": entrypoint_confidence.get("level"),
    } for item in technical_modules]
    result = {
        "schema": "codex-architecture-design-v1",
        "decision": "pass" if design_allowed else "block",
        "blockers": requirements_understanding_gate.get("blockers", []),
        "doc_id": doc_id,
        "title": title,
        "requirements_understanding_gate": requirements_understanding_gate,
        "business_closure_model": requirements_understanding_gate["business_closure_model"],
        "state_machine": requirements_understanding_gate["state_machine"],
        "business_goal_quality": requirements_understanding_gate["business_goal_quality"],
        "repo_impact_map": requirements_understanding_gate["repo_impact_map"],
        "dependency_chain": requirements_understanding_gate["dependency_chain"],
        "runtime_dependency_graph": requirements_understanding_gate["runtime_dependency_graph"],
        "architecture_scope": {"in_scope": as_list((spec.get("scope") or {}).get("in_scope")) or [summary], "out_of_scope": as_list((spec.get("scope") or {}).get("out_of_scope")), "assumptions": as_list((spec.get("scope") or {}).get("assumptions")), "decision_drivers": ["low coupling", "clear ownership", "rollback safety"]},
        "current_architecture": {
            "system_context": f"{owner_repo} 承担本需求的初始变更边界；主入口 `{owner_module}` 的置信度为 {entrypoint_confidence.get('level', 'unknown')}。",
            "repo_entrypoints": [owner_module, route_contract or "existing entrypoint to be confirmed"],
            "upstream_downstream": [f"{route_contract or 'existing producer'} -> {owner_repo}"],
            "constraints": ["keep owner boundary narrow", "preserve backward compatibility", "support rollback by reverting owner repo"],
        },
        "requirement_breakdown": breakdown,
        "code_entrypoint_confidence": entrypoint_confidence,
        "source_location_evidence": technical.get("source_location_evidence") or {},
        "architecture_options": architecture_options,
        "architecture_fit_matrix": architecture_fit_matrix,
        "architecture_score_summary": architecture_score_summary,
        "selected_architecture": selected_architecture,
        "architecture_decision_confidence": {"level": architecture_confidence, "reason": "Requirement understanding is not sufficient for architecture delivery." if not design_allowed else "Repo routing, requirement gaps, or weak code entrypoint confidence remain." if architecture_confidence != "high" else "Repo owner is routed and code entrypoint confidence is high.", "confidence_reducers": requirements_understanding_gate["blockers"] + requirements_understanding_gate["ambiguities"] + readiness_gaps + ([] if repo_path else [{"source": "repo_path", "message": "owner repo path is not routed", "severity": "high"}]) + ([{"source": "code_entrypoint_confidence", "message": f"entrypoint confidence is {entrypoint_confidence.get('level')}", "severity": "high" if entrypoint_confidence.get("level") == "low" else "medium"}] if entrypoint_confidence.get("level") in {"low", "medium"} else [])},
        "architecture_invariants": [
            {"invariant": "One repository owns each write authority.", "verification": "repo_responsibilities and data_ownership agree"},
            {"invariant": "Cross-repo contract changes require freeze and integration evidence.", "verification": "cross_repo_contracts and integration_sequence are reviewed"},
            {"invariant": "Rollback order is explicit for every modified repo.", "verification": "rollback_strategy covers repo_responsibilities with role=modify"},
        ],
        "expert_review_checklist": [
            {"item": "Architecture option comparison includes ownership, release, contract, and extensibility tradeoffs.", "status": "ready"},
            {"item": "High-risk impacts have matching security/data/performance/release boundaries.", "status": "review" if impact_areas & {"data", "security", "performance", "config"} else "ready"},
            {"item": "Cross-repo dependencies are explicitly represented or waived.", "status": "ready"},
            {"item": "Repo path is known before delivery planning.", "status": "ready" if repo_path else "review"},
            {"item": "Requirement understanding allows architecture delivery planning.", "status": "ready" if design_allowed else "blocked"},
        ],
        "architecture_traceability_matrix": [
            {"requirement_id": str(item.get("id") or req_id), "requirement_breakdown_refs": [row.get("id") for row in breakdown], "component_boundary_refs": [f"{owner_repo} owns change"], "module_topology_refs": [owner_module], "data_flow_refs": [f"{route_contract or 'existing source'}->{owner_repo}"], "integration_sequence_refs": ["load/execute affected behavior"], "contract_refs": [route_contract or "preserve existing contracts"], "selected_architecture_option_id": selected_architecture.get("selected_option_id"), "decision_reason": selected_architecture.get("selection_reason")}
            for item in reqs
        ] or [{"requirement_id": req_id, "requirement_breakdown_refs": [row.get("id") for row in breakdown], "component_boundary_refs": [f"{owner_repo} owns change"], "module_topology_refs": [owner_module], "data_flow_refs": [f"{route_contract or 'existing source'}->{owner_repo}"], "integration_sequence_refs": ["load/execute affected behavior"], "contract_refs": [route_contract or "preserve existing contracts"], "selected_architecture_option_id": selected_architecture.get("selected_option_id"), "decision_reason": selected_architecture.get("selection_reason")}],
        "component_boundaries": [{"component": owner_repo, "role": "owner", "exclusion": "do not move unrelated responsibilities"}],
        "module_topology": module_topology or [{"repo": owner_repo, "module": owner_module, "responsibility": str(item.get("summary") or summary), "depends_on": ["existing API/config dependencies"], "boundary_rule": "keep change inside owner module unless this slice requires contract change", "change_type": "modify", "requirement_breakdown_id": item.get("id"), "entrypoint_confidence": entrypoint_confidence.get("level")} for item in breakdown],
        "repo_responsibilities": [{"repo": owner_repo, "repo_path": repo_path, "role": "modify", "responsibility": summary, "requirement_breakdown_refs": [item.get("id") for item in breakdown], "owner_tasks": [str(item.get("summary") or summary) for item in breakdown]}],
        "cross_repo_contracts": [{"producer": producer, "consumer": owner_repo, "contract": route_contract or f"{owner_repo} internal contract", "compatibility": "backward compatible", "failure_mode": "fallback/error state"}],
        "cross_repo_dependency_graph": [{"from": producer, "to": owner_repo, "contract": route_contract or f"{owner_repo} internal contract", "change": "confirm only unless implementation proves contract change is required"}],
        "data_flow": [{"source": route_contract or "existing source", "target": owner_repo, "rule": f"{item.get('id')}: read/write only through owner boundary", "requirement_breakdown_id": item.get("id")} for item in breakdown],
        "data_ownership": [{"business_object": str(item.get("summary") or summary or title or doc_id), "owner_repo": owner_repo, "write_authority": owner_module, "consistency_rule": "preserve existing consistency unless data design says otherwise", "requirement_breakdown_id": item.get("id")} for item in breakdown],
        "integration_sequence": [{"step": idx, "actor": owner_repo, "action": str(item.get("summary") or summary), "failure_handling": "preserve existing failure behavior", "requirement_breakdown_id": item.get("id")} for idx, item in enumerate(breakdown, start=1)],
        "failure_isolation": [{"failure": "upstream dependency unavailable or returns old shape", "isolation": "preserve existing fallback/error behavior", "user_impact": "no broader repository failure"}],
        "security_and_permission": [{"control": "preserve existing auth/data-scope checks", "impact": "review before implementation"}],
        "observability": [{"signal": "error logs and business success metric", "owner": owner_repo}],
        "monitoring_alerts": [{"signal": "error rate or failed acceptance path", "owner": owner_repo, "trigger": "increase after release", "action": "rollback or hotfix"}],
        "deployment_topology": [{"repo": owner_repo, "artifact": "existing deploy artifact", "environment": "standard promotion"}],
        "deployment_impact": [{"order": f"{owner_repo} first", "config": "none unless configuration design adds it"}],
        "deployment_impact_matrix": [{"repo": owner_repo, "artifact": "existing deploy artifact", "order": 1, "config_change": "none unless configuration design adds it", "restart_required": "standard deployment restart only"}],
        "migration_strategy": [{"migration_type": "none by default", "forward_action": "deploy changed repo", "backward_compatibility": "preserve existing contracts", "rollback_action": "revert changed repo"}],
        "gray_release_strategy": [{"strategy": "standard rollout", "fallback": "rollback"}],
        "rollback_strategy": [{"repo": owner_repo, "steps": ["revert commit", "redeploy previous artifact"], "data_risk": "none unless data design changes"}],
        "decision_records": [{"decision": "start with owner-repo scoped architecture", "alternatives": ["cross-repo contract change"], "reason": "minimize coupling and release risk"}],
        "architecture_risks": [] if repo_path else [{"risk": "owner repo not yet routed", "mitigation": "fill repo_path and rerun delivery plan before git/edit"}],
    }
    if architecture_framing:
        result["architecture_framing_ref"] = "architecture_framing.json"
        result["architecture_framing"] = architecture_framing
        result["component_boundaries"] = [
            {"component": item.get("repo"), "role": item.get("role"), "exclusion": "respect pre-technical architecture framing"}
            for item in as_list(architecture_framing.get("repo_responsibilities"))
            if isinstance(item, dict)
        ] or result["component_boundaries"]
        result["cross_repo_dependency_graph"] = as_list((architecture_framing.get("dependency_graph") or {}).get("edges")) or result["cross_repo_dependency_graph"]
        framed_ownership = as_list(architecture_framing.get("data_ownership"))
        if framed_ownership:
            result["data_ownership"] = [
                {**item, "consistency_rule": item.get("consistency_rule") or "preserve existing owner consistency; no data ownership change"}
                for item in framed_ownership
                if isinstance(item, dict)
            ]
        result["expert_review_checklist"].append({
            "item": "Architecture design refines pre-technical architecture framing.",
            "status": "ready" if architecture_framing.get("decision") == "pass" else "blocked",
        })
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Render architecture design from spec and technical design")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--technical-design", required=True)
    parser.add_argument("--project-understanding")
    parser.add_argument("--architecture-framing")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = render(
        load_json(Path(args.spec)),
        load_json(Path(args.technical_design)),
        load_project_understanding(Path(args.project_understanding)) if args.project_understanding else None,
        load_json(Path(args.architecture_framing)) if args.architecture_framing else {},
    )
    write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
