#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
DIRS = ["human/specs", "human/designs", "human/releases", "machine/specs", "machine/designs", "machine/reviews", "machine/releases", "baseline", "indexes"]
MACHINE_ARTIFACTS = {
    "spec": ("machine/specs", ".spec.json"),
    "design": ("machine/designs", ".design.json"),
    "review": ("machine/reviews", ".review.json"),
    "release": ("machine/releases", ".release.json"),
}


def load_docs_config_module() -> Any:
    candidates = [
        Path(__file__).resolve().parents[1] / "scripts/docs_config.py",
        ROOT / "scripts/docs_config.py",
        ROOT.parent / "scripts/docs_config.py",
    ]
    path = next((candidate for candidate in candidates if candidate.exists()), candidates[0])
    spec = importlib.util.spec_from_file_location("docs_config", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def write_text_if_missing(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        path.write_text(text, encoding="utf-8")


def normalize_doc_language(language: str = "en") -> str:
    return "zh" if str(language).lower() in {"zh", "cn", "chinese", "中文"} else "en"


def markdown_template(doc_id: str, title: str, kind: str, language: str = "en") -> str:
    if normalize_doc_language(language) == "zh":
        kind_label = {"spec": "需求说明", "design": "技术设计", "release": "发布准备"}.get(kind, kind)
        heading = title or doc_id
        return (
            f"# {heading} {kind_label}\n\n"
            f"- 文档编号：`{doc_id}`\n"
            "- 状态：已初始化，等待同步交付产物\n"
            "- 来源：docs-governor\n\n"
            "## 摘要\n\n"
            "当前只有文档骨架；请在生成需求、设计、计划、评审产物后执行 docs-governor sync。\n\n"
            "## 追踪关系\n\n"
            "- 需求、设计、评审、发布证据必须通过同一个文档编号关联。\n"
        )
    heading = title or doc_id
    return (
        f"# {heading} {kind}\n\n"
        f"- doc_id: `{doc_id}`\n"
        "- status: initialized\n"
        "- source: docs-governor\n\n"
        "## Summary\n\n"
        "Pending delivery artifact sync.\n\n"
        "## Traceability\n\n"
        "- Requirement, design, review, and release evidence must remain linked by doc_id.\n"
    )


def placeholder_artifact(doc_id: str, artifact_type: str) -> dict[str, Any]:
    return {
        "schema": "codex-docs-machine-placeholder-v1",
        "doc_id": doc_id,
        "artifact_type": artifact_type,
        "status": "initialized",
        "source": "docs-governor",
        "rule": "Replace this placeholder through docs-governor sync after delivery artifacts are generated.",
    }


def materialize_doc_files(docs_root: Path, doc_id: str, title: str = "", language: str = "en") -> dict[str, list[str]]:
    human_paths = {
        "spec": docs_root / "human/specs" / f"{doc_id}.md",
        "design": docs_root / "human/designs" / f"{doc_id}.md",
        "release": docs_root / "human/releases" / f"{doc_id}.md",
    }
    machine_paths = {
        name: docs_root / directory / f"{doc_id}{suffix}"
        for name, (directory, suffix) in MACHINE_ARTIFACTS.items()
    }
    for name, path in human_paths.items():
        write_text_if_missing(path, markdown_template(doc_id, title, name, language))
    for name, path in machine_paths.items():
        if not path.exists() or not path.read_text(encoding="utf-8").strip():
            write_json(path, placeholder_artifact(doc_id, name))
    return {
        "human_docs": [str(path.relative_to(docs_root)) for path in human_paths.values()],
        "machine_artifacts": [str(path.relative_to(docs_root)) for path in machine_paths.values()],
    }


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def text(value: Any, default: str = "TBD") -> str:
    if value in (None, "", [], {}):
        return default
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return ", ".join(text(item, default) for item in value) or default
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


ZH_DEFAULT_PHRASES = {
    "target module to be confirmed": "待确认目标模块",
    "existing entrypoint to be confirmed": "待确认现有入口",
    "existing producer": "现有生产方",
    "preserve existing contracts": "保持现有契约",
    "preserve existing permission and validation behavior": "保持现有权限与校验行为",
    "keep owner boundary narrow": "保持责任边界收敛",
    "preserve backward compatibility": "保持向后兼容",
    "support rollback by reverting owner repo": "支持通过回滚责任仓库恢复",
    "target-repo owns the initial change boundary for this requirement and must preserve existing upstream/downstream contracts.": "target-repo 承担该需求的初始变更边界，并必须保持现有上下游契约。",
    "Minimal scoped change": "最小范围变更",
    "New abstraction or contract": "新增抽象或契约",
    "Single owner repository change": "单一责任仓库变更",
    "Cross-repository contract change": "跨仓契约变更",
    "Implement inside the current owner module using existing contracts.": "在当前责任模块内复用现有契约实现。",
    "Introduce a new abstraction/API to isolate the behavior.": "引入新的抽象或 API 隔离该行为。",
    "Implement in the current owner repo and preserve external contracts.": "在当前责任仓库内实现，并保持对外契约不变。",
    "Change producer and consumer contracts across repositories.": "同时调整跨仓生产方和消费方契约。",
    "Default to smallest safe change until code inspection proves abstraction is needed.": "默认采用最小安全变更，除非代码检查证明必须抽象。",
    "Default to smallest owner-boundary change until code inspection requires cross-repo work.": "默认控制在最小责任边界内，除非代码检查证明需要跨仓改造。",
    "May need revision after architecture review": "架构评审后可能需要修订",
    "May be revised after repo routing": "仓库路由后可能需要修订",
    "revert scoped change": "回滚范围内变更",
    "revert contract and consumers": "回滚契约和消费方",
    "revert target-repo": "回滚目标仓库",
    "ordered rollback consumer then producer": "按顺序先回滚消费方再回滚生产方",
    "start with owner-repo scoped architecture": "先采用责任仓库内架构",
    "cross-repo contract change": "跨仓契约变更",
    "minimize coupling and release risk": "降低耦合和发布风险",
    "Read 待确认目标模块 and adjacent tests before editing.": "修改前阅读待确认目标模块及相邻测试。",
    "Confirm 待确认目标模块 scope against reviewed design.": "按已评审设计确认待确认目标模块范围。",
    "Run validation for 待确认目标模块 and mapped acceptance checks.": "运行待确认目标模块校验和已映射的验收检查。",
    "Capture command logs and acceptance evidence for 待确认目标模块.": "采集待确认目标模块的命令日志和验收证据。",
    "Verify rollback path for 待确认目标模块.": "验证待确认目标模块的回滚路径。",
    "inspected-files: 待确认目标模块": "已检查文件：待确认目标模块",
    "scope-confirmation for 待确认目标模块": "待确认目标模块范围确认",
    "git diff for 待确认目标模块": "待确认目标模块 git diff",
    "rollback verification for 待确认目标模块": "待确认目标模块回滚验证",
    "待确认目标模块 behavior and dependencies understood": "已理解待确认目标模块行为和依赖",
    "scope still matches architecture responsibilities": "范围仍匹配架构职责",
    "diff only touches 待确认目标模块": "diff 仅触达待确认目标模块",
    "required tests pass": "必需测试通过",
    "evidence artifacts are attached to delivery": "证据产物已附加到交付记录",
    "rollback owner and steps are known": "已明确回滚责任方和步骤",
    "prepare data": "准备测试数据",
    "execute affected behavior": "执行受影响行为",
    "verify expected result": "验证预期结果",
    "unauthorized role cannot access changed behavior": "未授权角色不能访问变更后的行为",
    "restricted role": "受限角色",
    "attempt changed behavior": "尝试执行变更后的行为",
    "access denied or hidden": "访问被拒绝或入口不可见",
    "permission": "权限测试",
    "permission test evidence": "权限测试证据",
    "Acceptance criteria pass.": "验收标准通过。",
    "Validation failure": "校验失败",
    "Dependency unavailable": "依赖不可用",
    "expected behavior": "预期行为",
    "request data": "请求数据",
    "updated behavior": "更新后的行为",
    "Use existing contracts and avoid duplicating upstream business rules.": "复用现有契约，避免重复实现上游业务规则。",
    "No API impact confirmed yet": "尚未确认 API 影响",
    "preserve existing consumers unless design updates contract": "除非设计更新契约，否则保持现有消费方不受影响",
    "review route consumers before implementation": "实现前检查路由消费方",
    "no API request expected": "预计无 API 请求变更",
    "no API response change expected": "预计无 API 响应变更",
    "no API error contract change expected": "预计无 API 错误契约变更",
    "read through target module to be confirmed": "通过待确认目标模块读取",
    "write through target module to be confirmed only if requirement changes state": "仅在需求涉及状态变更时，通过待确认目标模块写入",
    "none unless design update requires it": "除非设计更新要求，否则无需迁移",
    "preserve existing permission boundary": "保持现有权限边界",
    "unauthorized user cannot access changed behavior": "未授权用户不能访问变更后的行为",
    "missing/invalid input": "缺失或非法输入",
    "return validation error or preserve existing fallback": "返回校验错误或保持现有兜底行为",
    "confirm if UI is affected": "确认是否影响 UI",
    "existing entry": "现有入口",
    "preserve role visibility": "保持角色可见性",
    "browser evidence if UI changed": "如 UI 变更需提供浏览器证据",
    "target-repo internal contract": "目标仓库内部契约",
    "confirm only unless implementation proves contract change is required": "仅确认影响，除非实现证明必须修改契约",
    "preserve existing failure behavior": "保持现有失败处理行为",
    "existing deploy artifact": "现有部署制品",
    "none unless configuration design adds it": "除非配置设计新增，否则无配置变更",
    "standard deployment restart only": "仅标准部署重启",
    "revert commit, redeploy previous artifact": "回滚提交并重新部署上一版本制品",
    "none unless data design changes": "除非数据设计变化，否则无数据风险",
    "functional_test": "功能测试",
    "permission_negative_test": "权限反向测试",
    "export_evidence": "导出证据",
    "test evidence": "测试证据",
}


def translate_default_zh_phrase(value: str) -> str:
    rendered = value
    for source, target in sorted(ZH_DEFAULT_PHRASES.items(), key=lambda item: len(item[0]), reverse=True):
        rendered = rendered.replace(source, target)
    return rendered


def zh_text(value: Any, default: str = "待补充") -> str:
    if value in (None, "", [], {}):
        return default
    if isinstance(value, bool):
        return "是" if value else "否"
    rendered = text(value, default)
    replacements = {
        "unknown": "未知",
        "draft": "草稿",
        "ready": "就绪",
        "ready_for_design": "可进入设计",
        "needs_completion": "需要补齐",
        "needs_revision": "需要修订",
        "pass": "通过",
        "block": "阻塞",
        "low": "低",
        "medium": "中",
        "high": "高",
        "read": "阅读",
        "confirm": "确认",
        "edit": "修改",
        "test": "测试",
        "evidence": "证据",
        "rollback": "回滚",
        "functional": "功能测试",
        "positive": "正向用例",
        "negative": "反向用例",
        "modify": "修改",
        "false": "否",
        "true": "是",
        "TBD": default,
    }
    return replacements.get(rendered, translate_default_zh_phrase(rendered))


def bullet_lines(items: list[str], empty: str = "TBD") -> str:
    compact = [item for item in items if item]
    if not compact:
        return f"- {empty}"
    return "\n".join(item if item.lstrip().startswith("- ") else f"- {item}" for item in compact)


def section_paragraph(title: str, lines: list[str], empty: str) -> str:
    return f"### {title}\n\n{bullet_lines(lines, empty)}"


def summarize_dict_item(item: dict[str, Any], fields: list[str], language: str = "en") -> str:
    values = [str(item.get(field)) for field in fields if item.get(field) not in (None, "", [], {})]
    if values:
        return "；".join(values) if language == "zh" else "; ".join(values)
    return zh_text(item, "待补充") if language == "zh" else text(item)


def render_scope(spec: dict[str, Any], fallback: str, language: str = "en") -> str:
    scope = spec.get("scope")
    if not isinstance(scope, dict):
        return fallback
    lines: list[str] = []
    labels = {
        "in_scope": "范围内" if language == "zh" else "In scope",
        "out_of_scope": "范围外" if language == "zh" else "Out of scope",
        "assumptions": "假设" if language == "zh" else "Assumptions",
        "non_goals": "非目标" if language == "zh" else "Non-goals",
    }
    for key in ["in_scope", "out_of_scope", "assumptions", "non_goals"]:
        values = [str(item) for item in as_list(scope.get(key))]
        if values:
            lines.append(f"- {labels[key]}：{', '.join(values)}" if language == "zh" else f"- {labels[key]}: {', '.join(values)}")
    return "\n".join(lines) if lines else f"- {fallback}"


def render_acceptance(spec: dict[str, Any], language: str = "en") -> str:
    lines: list[str] = []
    for item in as_list(spec.get("acceptance_criteria")):
        if not isinstance(item, dict):
            continue
        evidence = ", ".join(str(value) for value in as_list(item.get("evidence_required"))) or ("待补充" if language == "zh" else "TBD")
        if language == "zh":
            evidence = ", ".join(zh_text(value) for value in as_list(item.get("evidence_required"))) or "待补充"
            lines.append(f"`{text(item.get('id'))}` {text(item.get('criteria'))}（类型：{zh_text(item.get('type'), '用例')}；证据：{evidence}）")
        else:
            lines.append(f"`{text(item.get('id'))}` {text(item.get('criteria'))} ({text(item.get('type'), 'case')}; evidence: {evidence})")
    return bullet_lines(lines, "未同步到验收标准。" if language == "zh" else "No acceptance criteria were synced.")


def render_business_rules(spec: dict[str, Any]) -> str:
    lines = [f"`{text(item.get('id'))}` {text(item.get('rule'))}" for item in as_list(spec.get("business_rules")) if isinstance(item, dict)]
    return bullet_lines(lines, "No explicit business rules were synced.")


def render_requirement_clarification(spec: dict[str, Any]) -> str:
    confirmed: list[str] = []
    for item in as_list(spec.get("business_rules")):
        if isinstance(item, dict):
            confirmed.append(f"{text(item.get('id'))}: {text(item.get('rule'))}")
    permission = spec.get("permission_scope") if isinstance(spec.get("permission_scope"), dict) else {}
    actors = ", ".join(str(item) for item in as_list(permission.get("actors")))
    if actors:
        confirmed.append(f"Actors/roles identified: {actors}")
    if permission.get("negative_cases_required") is True:
        confirmed.append("Negative permission cases are required.")

    assumptions: list[str] = []
    scope = spec.get("scope") if isinstance(spec.get("scope"), dict) else {}
    assumptions.extend(str(item) for item in as_list(scope.get("assumptions")))
    assumptions.extend(str(item) for item in as_list(spec.get("assumptions")))

    questions: list[str] = []
    for item in as_list(spec.get("open_questions")):
        if isinstance(item, dict):
            questions.append(text(item.get("question") or item.get("summary") or item))
        else:
            questions.append(text(item))

    decision = str(spec.get("decision") or "")
    blocked = bool(questions) or decision in {"needs_clarification", "blocked"}
    return (
        "### Clarification Status\n\n"
        f"- Status: {'blocked pending answer' if blocked else 'no blocking clarification recorded'}\n"
        f"- Design can proceed: {'no' if blocked else 'yes'}\n\n"
        "### Confirmed Understanding\n\n"
        f"{bullet_lines(confirmed, 'No confirmed business rules beyond the requirement text.')}\n\n"
        "### Pending Questions\n\n"
        f"{bullet_lines(questions, 'None recorded.')}\n\n"
        "### Working Assumptions\n\n"
        f"{bullet_lines(assumptions, 'None recorded.')}"
    )


def render_requirement_clarification_zh(spec: dict[str, Any]) -> str:
    english = render_requirement_clarification(spec)
    replacements = {
        "### Clarification Status": "### 澄清状态",
        "Status: blocked pending answer": "状态：等待答复，暂时阻塞",
        "Status: no blocking clarification recorded": "状态：未记录阻塞性澄清问题",
        "Design can proceed: no": "是否允许进入设计：否",
        "Design can proceed: yes": "是否允许进入设计：是",
        "### Confirmed Understanding": "### 已确认理解",
        "No confirmed business rules beyond the requirement text.": "除需求原文外，未记录更多已确认业务规则。",
        "### Pending Questions": "### 待澄清问题",
        "None recorded.": "未记录。",
        "### Working Assumptions": "### 工作假设",
    }
    for source, target in replacements.items():
        english = english.replace(source, target)
    english = english.replace("Actors/roles identified:", "已识别角色：")
    english = english.replace("Negative permission cases are required.", "需要覆盖权限反向用例。")
    english = english.replace("BR-", "业务规则-")
    return english


def render_open_questions(*documents: dict[str, Any], language: str = "en") -> str:
    lines: list[str] = []
    for data in documents:
        for item in as_list(data.get("open_questions")):
            if isinstance(item, dict):
                lines.append(text(item.get("question") or item.get("summary") or item))
            else:
                lines.append(text(item))
    return bullet_lines(lines, "未记录。" if language == "zh" else "None recorded.")


def render_clarification_log(spec: dict[str, Any], language: str = "en") -> str:
    rows: list[str] = []
    for index, item in enumerate(as_list(spec.get("clarification_log")), start=1):
        if isinstance(item, dict):
            rows.append(
                f"| C-{index} | {text(item.get('question') or item.get('summary'))} | "
                f"{text(item.get('answer'), 'unanswered')} | {text(item.get('status'), 'open')} | {text(item.get('impact'), 'scope/design')} |"
            )
    if not rows:
        if language == "zh":
            return "未记录澄清问题；当前文档基于需求原文、验收标准和已识别业务规则生成。"
        return "No clarification log was recorded; this document is based on the source requirement, acceptance criteria, and detected business rules."
    header = "| 编号 | 问题 | 答案 | 状态 | 影响范围 |\n|---|---|---|---|---|" if language == "zh" else "| ID | Question | Answer | Status | Impact |\n|---|---|---|---|---|"
    return header + "\n" + "\n".join(rows)


def render_decision_records(*documents: dict[str, Any], language: str = "en") -> str:
    rows: list[str] = []
    for data in documents:
        for item in as_list(data.get("decision_records")):
            if isinstance(item, dict):
                if language == "zh":
                    rows.append(f"- 决策：{text(item.get('decision'))}；备选：{text(item.get('alternatives'))}；理由：{text(item.get('reason'))}；回滚考虑：{text(item.get('rollback'), '见回滚策略')}")
                else:
                    rows.append(f"- Decision: {text(item.get('decision'))}; alternatives: {text(item.get('alternatives'))}; reason: {text(item.get('reason'))}; rollback: {text(item.get('rollback'), 'see rollback strategy')}")
    if not rows:
        return "- 未记录决策记录；需在设计评审前补齐关键决策。" if language == "zh" else "- No decision records were synced; key decisions should be completed before design review."
    return "\n".join(rows)


def render_requirement_trace_mermaid(spec: dict[str, Any], language: str = "en") -> str:
    reqs = [item for item in as_list(spec.get("requirements")) if isinstance(item, dict)]
    acs = [item for item in as_list(spec.get("acceptance_criteria")) if isinstance(item, dict)]
    if not reqs or not acs:
        return "缺少需求或验收标准，无法生成追踪图。" if language == "zh" else "Requirement or acceptance data is missing, so the traceability diagram cannot be generated."
    lines = ["```mermaid", "flowchart LR"]
    for req in reqs[:6]:
        req_id = text(req.get("id"), "REQ")
        lines.append(f'  {req_id}["{req_id}: {text(req.get("summary"), "requirement")[:60]}"]')
    for ac in acs[:8]:
        ac_id = text(ac.get("id"), "AC")
        lines.append(f'  {ac_id}["{ac_id}: {text(ac.get("criteria"), "acceptance")[:60]}"]')
    first_req = text(reqs[0].get("id"), "REQ")
    for ac in acs[:8]:
        lines.append(f'  {first_req} --> {text(ac.get("id"), "AC")}')
    lines.append("```")
    return "\n".join(lines)


def render_process_mermaid(technical: dict[str, Any], language: str = "en") -> str:
    flows = [item for item in as_list(technical.get("process_flow")) if isinstance(item, dict)]
    if not flows:
        return "缺少业务流程，无法生成流程图。" if language == "zh" else "Process flow data is missing, so the flow diagram cannot be generated."
    lines = ["```mermaid", "flowchart TD"]
    counter = 0
    for flow in flows[:3]:
        previous = ""
        for step in as_list(flow.get("steps"))[:8]:
            if not isinstance(step, dict):
                continue
            counter += 1
            node = f"S{counter}"
            label = f"{text(step.get('actor'), 'actor')}: {text(step.get('action'), 'action')}"[:70]
            lines.append(f'  {node}["{label}"]')
            if previous:
                lines.append(f"  {previous} --> {node}")
            previous = node
    lines.append("```")
    return "\n".join(lines) if counter else ("缺少流程步骤，无法生成流程图。" if language == "zh" else "Process steps are missing, so the flow diagram cannot be generated.")


def render_architecture_mermaid(architecture: dict[str, Any], language: str = "en") -> str:
    deps = [item for item in as_list(architecture.get("cross_repo_dependency_graph")) if isinstance(item, dict)]
    if not deps:
        return "缺少跨仓或模块依赖信息，无法生成关系图。" if language == "zh" else "Dependency graph data is missing, so the architecture diagram cannot be generated."
    lines = ["```mermaid", "flowchart LR"]
    for item in deps[:8]:
        source = text(item.get("from"), "source").replace("/", "_").replace("-", "_")
        target = text(item.get("to"), "target").replace("/", "_").replace("-", "_")
        label = text(item.get("contract"), "contract")[:50]
        lines.append(f'  {source} -->|"{label}"| {target}')
    lines.append("```")
    return "\n".join(lines)


def render_release_mermaid(delivery_plan: dict[str, Any], language: str = "en") -> str:
    release = delivery_plan.get("release_plan") if isinstance(delivery_plan.get("release_plan"), dict) else {}
    rollback = delivery_plan.get("rollback_plan") if isinstance(delivery_plan.get("rollback_plan"), dict) else {}
    release_order = [str(item) for item in as_list(release.get("release_order"))]
    rollback_order = [str(item) for item in as_list(rollback.get("rollback_order"))]
    if not release_order and not rollback_order:
        return "缺少发布或回滚顺序，无法生成顺序图。" if language == "zh" else "Release or rollback order is missing, so the sequence diagram cannot be generated."
    lines = ["```mermaid", "sequenceDiagram", "  participant Operator", "  participant Delivery"]
    for repo in release_order:
        lines.append(f"  Operator->>Delivery: release {repo}")
    for repo in rollback_order:
        lines.append(f"  Delivery-->>Operator: rollback {repo}")
    lines.append("```")
    return "\n".join(lines)


def render_process_flows(technical: dict[str, Any], language: str = "en") -> str:
    sections: list[str] = []
    for flow in as_list(technical.get("process_flow")):
        if not isinstance(flow, dict):
            continue
        steps = []
        for step in as_list(flow.get("steps")):
            if isinstance(step, dict):
                if language == "zh":
                    steps.append(f"  - {zh_text(step.get('step'))}. {zh_text(step.get('actor'))}：{zh_text(step.get('action'))} -> {zh_text(step.get('output'))}")
                else:
                    steps.append(f"  - {text(step.get('step'))}. {text(step.get('actor'))}: {text(step.get('action'))} -> {text(step.get('output'))}")
        if language == "zh":
            sections.append(
                f"### {zh_text(flow.get('flow_name'), '流程')}\n\n"
                f"- 参与方：{', '.join(str(item) for item in as_list(flow.get('actors'))) or '待补充'}\n"
                f"- 成功状态：{zh_text(flow.get('success_end_state'))}\n"
                f"- 失败状态：{', '.join(str(item) for item in as_list(flow.get('failure_end_states'))) or '待补充'}\n\n"
                + ("\n".join(steps) if steps else "- 步骤：待补充")
            )
        else:
            sections.append(
                f"### {text(flow.get('flow_name'), 'Process')}\n\n"
                f"- Actors: {', '.join(str(item) for item in as_list(flow.get('actors'))) or 'TBD'}\n"
                f"- Success state: {text(flow.get('success_end_state'))}\n"
                f"- Failure states: {', '.join(str(item) for item in as_list(flow.get('failure_end_states'))) or 'TBD'}\n\n"
                + ("\n".join(steps) if steps else "- Steps: TBD")
            )
    return "\n\n".join(sections) if sections else ("### 流程\n\n- 待补充" if language == "zh" else "### Process\n\n- TBD")


def render_named_items(items: list[Any], fields: list[str], empty: str, language: str = "en") -> str:
    en_labels = {
        "page_or_route": "page/route",
        "user_goal": "user goal",
        "entry_point": "entry point",
        "permission_visibility": "permission visibility",
        "acceptance_evidence": "acceptance evidence",
        "old_consumer_impact": "consumer impact",
        "failure_handling": "failure handling",
        "data_risk": "data risk",
    }
    zh_labels = {
        "existing_behavior": "现有行为",
        "code_entrypoints": "代码入口",
        "known_constraints": "已知约束",
        "reuse_points": "可复用点",
        "system_context": "系统上下文",
        "repo_entrypoints": "仓库入口",
        "upstream_downstream": "上下游",
        "constraints": "约束",
        "module": "模块",
        "responsibility": "职责",
        "input": "输入",
        "output": "输出",
        "coupling_control": "耦合控制",
        "contract": "契约",
        "compatibility": "兼容性",
        "old_consumer_impact": "存量消费方影响",
        "name": "名称",
        "request": "请求",
        "response": "响应",
        "error_response": "错误响应",
        "read_rule": "读取规则",
        "write_rule": "写入规则",
        "migration": "迁移",
        "role": "角色",
        "rule": "规则",
        "negative_case": "反向用例",
        "case": "场景",
        "handling": "处理方式",
        "page_or_route": "页面/路由",
        "user_goal": "用户目标",
        "entry_point": "入口",
        "permission_visibility": "权限可见性",
        "acceptance_evidence": "验收证据",
        "from": "来源",
        "to": "目标",
        "change": "变更",
        "step": "步骤",
        "actor": "参与方",
        "action": "动作",
        "failure_handling": "失败处理",
        "repo": "仓库",
        "artifact": "制品",
        "order": "顺序",
        "config_change": "配置变更",
        "restart_required": "是否重启",
        "steps": "步骤",
        "data_risk": "数据风险",
        "acceptance_id": "验收项",
        "design_refs": "设计引用",
        "evidence_required": "所需证据",
        "type": "类型",
        "evidence": "证据",
        "signal": "信号",
        "owner": "负责人",
        "trigger": "触发条件",
    }
    labels = zh_labels if language == "zh" else en_labels
    lines: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        values = [
            f"{labels.get(field, field)}：{zh_text(item.get(field))}" if language == "zh" else f"{labels.get(field, field)}: {text(item.get(field))}"
            for field in fields
            if item.get(field) not in (None, "", [], {})
        ]
        if values:
            lines.append("；".join(values) if language == "zh" else "; ".join(values))
    return bullet_lines(lines, empty)


def render_delivery_tasks(delivery_plan: dict[str, Any], language: str = "en") -> str:
    sections: list[str] = []
    for repo in as_list(delivery_plan.get("repo_tasks")):
        if not isinstance(repo, dict):
            continue
        allowed_files = ", ".join(str(item) for item in as_list(repo.get("allowed_files"))) or ("尚未收敛" if language == "zh" else "not narrowed yet")
        read_first = ", ".join(str(item) for item in as_list(repo.get("read_first"))) or ("尚未绑定" if language == "zh" else "not bound yet")
        tests = ", ".join(str(item) for item in as_list(repo.get("test_commands"))) or ("尚未绑定" if language == "zh" else "not bound yet")
        git_prep = repo.get("git_preparation") if isinstance(repo.get("git_preparation"), dict) else {}
        git_steps = ", ".join(str(item) for item in as_list(git_prep.get("required_before_edit"))) or ("尚未绑定" if language == "zh" else "not bound yet")
        if language == "zh":
            lines = [
                f"### 仓库 `{text(repo.get('repo'))}`",
                "",
                f"- 角色：`{zh_text(repo.get('role'))}`",
                f"- 职责：{zh_text(repo.get('responsibility'))}",
                f"- 修改前必须阅读：{read_first}",
                f"- 允许修改文件：{allowed_files}",
                f"- 测试命令：{tests}",
                f"- Git 准备动作：{git_steps}",
                "",
            ]
        else:
            lines = [
                f"### Repo `{text(repo.get('repo'))}`",
                "",
                f"- Role: `{text(repo.get('role'))}`",
                f"- Responsibility: {text(repo.get('responsibility'))}",
                f"- Read first: {read_first}",
                f"- Allowed files: {allowed_files}",
                f"- Test commands: {tests}",
                f"- Git preparation: {git_steps}",
                "",
            ]
        for task in as_list(repo.get("tasks"))[:6]:
            if isinstance(task, dict):
                if language == "zh":
                    evidence = ", ".join(zh_text(item) for item in as_list(task.get("evidence_to_collect"))) or "待补充"
                else:
                    evidence = ", ".join(str(item) for item in as_list(task.get("evidence_to_collect"))) or "TBD"
                files_to_edit = ", ".join(str(item) for item in as_list(task.get("files_to_edit"))) or ("无" if language == "zh" else "none")
                exit_criteria = ", ".join(zh_text(item) for item in as_list(task.get("exit_criteria"))) if language == "zh" else ", ".join(str(item) for item in as_list(task.get("exit_criteria")))
                exit_criteria = exit_criteria or ("待补充" if language == "zh" else "TBD")
                if language == "zh":
                    lines.append(
                        f"- `{zh_text(task.get('phase'))}` {zh_text(task.get('summary'))}；"
                        f"修改文件：{files_to_edit}；证据：{evidence}；退出标准：{exit_criteria}"
                    )
                else:
                    lines.append(
                        f"- `{text(task.get('phase'))}` {text(task.get('summary'))}; "
                        f"edit files: {files_to_edit}; evidence: {evidence}; exit: {exit_criteria}"
                    )
        sections.append("\n".join(lines))
    return "\n\n".join(sections) if sections else ("- 未同步到仓库任务。" if language == "zh" else "- No repo tasks were synced.")


def render_test_cases(test_design: dict[str, Any], language: str = "en") -> str:
    cases = [item for item in as_list(test_design.get("test_cases")) if isinstance(item, dict)]
    if not cases:
        return "- 未同步到测试用例；技术设计完成后必须生成 `test_design.json`。" if language == "zh" else "- No test cases were synced; `test_design.json` is required after technical design."
    sections: list[str] = []
    for case in cases:
        steps = as_list(case.get("steps"))
        evidence = as_list(case.get("evidence_required"))
        if language == "zh":
            sections.append(
                f"### `{text(case.get('id'))}` {zh_text(case.get('title'))}\n\n"
                f"- 关联验收：{zh_text(case.get('acceptance_id'), '未绑定')}\n"
                f"- 类型：{zh_text(case.get('type'))}\n"
                f"- 前置条件：{', '.join(zh_text(item) for item in as_list(case.get('preconditions'))) or '无'}\n"
                f"- 执行步骤：{', '.join(zh_text(item) for item in steps) or '待补充'}\n"
                f"- 预期结果：{zh_text(case.get('expected_result'))}\n"
                f"- 所需证据：{', '.join(zh_text(item) for item in evidence) or '待补充'}"
            )
        else:
            sections.append(
                f"### `{text(case.get('id'))}` {text(case.get('title'))}\n\n"
                f"- Acceptance: {text(case.get('acceptance_id'), 'unmapped')}\n"
                f"- Type: {text(case.get('type'))}\n"
                f"- Preconditions: {', '.join(text(item) for item in as_list(case.get('preconditions'))) or 'none'}\n"
                f"- Steps: {', '.join(text(item) for item in steps) or 'TBD'}\n"
                f"- Expected result: {text(case.get('expected_result'))}\n"
                f"- Evidence required: {', '.join(text(item) for item in evidence) or 'TBD'}"
            )
    return "\n\n".join(sections)


def render_solution_options(technical: dict[str, Any], architecture: dict[str, Any], language: str = "en") -> str:
    label_option = "方案" if language == "zh" else "Option"
    label_selected = "选中方案" if language == "zh" else "Selected"
    sections: list[str] = []
    selected_technical = technical.get("selected_solution") if isinstance(technical.get("selected_solution"), dict) else {}
    selected_arch = architecture.get("selected_architecture") if isinstance(architecture.get("selected_architecture"), dict) else {}
    for title, options, selected in [
        ("技术方案对比" if language == "zh" else "Technical Options", as_list(technical.get("solution_options")), selected_technical),
        ("架构方案对比" if language == "zh" else "Architecture Options", as_list(architecture.get("architecture_options")), selected_arch),
    ]:
        lines = [f"### {title}", ""]
        for item in options:
            if isinstance(item, dict):
                if language == "zh":
                    lines.append(
                        f"- {label_option} `{text(item.get('option_id'))}` {zh_text(item.get('name'))}："
                        f"{zh_text(item.get('description'))}；风险：{zh_text(item.get('risk_level'))}；回滚：{zh_text(item.get('rollback_strategy'))}"
                    )
                else:
                    lines.append(f"- {label_option} `{text(item.get('option_id'))}` {text(item.get('name'))}: {text(item.get('description'))}; risk: {text(item.get('risk_level'))}; rollback: {text(item.get('rollback_strategy'))}")
        if language == "zh":
            lines.append(f"- {label_selected}：`{text(selected.get('selected_option_id'))}`；理由：{zh_text(selected.get('selection_reason'))}；取舍：{zh_text(selected.get('tradeoffs'))}")
        else:
            lines.append(f"- {label_selected}: `{text(selected.get('selected_option_id'))}`; reason: {text(selected.get('selection_reason'))}; tradeoffs: {text(selected.get('tradeoffs'))}")
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def render_blockers(*documents: dict[str, Any]) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for data in documents:
        for item in as_list(data.get("blockers")) + as_list(data.get("open_gates")):
            if isinstance(item, dict):
                source = text(item.get("source") or item.get("area"), "gate")
                message = text(item.get("message") or item.get("suggestion") or item)
            else:
                source = "gate"
                message = text(item)
            key = f"{source}: {message}"
            if key not in seen:
                seen.add(key)
                lines.append(key)
    return bullet_lines(lines[:10], "None.")


def render_review_context(spec: dict[str, Any], language: str = "en") -> str:
    summary = spec.get("requirement_summary") or spec.get("summary") or spec.get("title")
    acceptance_count = len([item for item in as_list(spec.get("acceptance_criteria")) if isinstance(item, dict)])
    question_count = len(as_list(spec.get("open_questions")))
    if language == "zh":
        return (
            f"- 需求核心：{zh_text(summary, '未同步到需求摘要')}\n"
            f"- 验收规模：当前同步到 {acceptance_count} 条验收标准，需要逐条绑定设计、测试和证据。\n"
            f"- 澄清状态：当前记录 {question_count} 个未决问题；若存在未决问题，设计只能作为草案，不能直接进入实现。\n"
            "- 阅读方式：先确认范围和澄清结论，再看验收标准与追踪图，最后检查证据引用是否完整。"
        )
    return (
        f"- Requirement core: {text(summary, 'requirement summary was not synced')}\n"
        f"- Acceptance size: {acceptance_count} acceptance criteria were synced and must map to design, tests, and evidence.\n"
        f"- Clarification state: {question_count} open questions are recorded; unresolved questions keep the design in draft.\n"
        "- Review path: verify scope and clarification first, then acceptance traceability, then evidence references."
    )


def render_design_review_context(technical: dict[str, Any], architecture: dict[str, Any], delivery_plan: dict[str, Any], language: str = "en") -> str:
    module_count = len(as_list(technical.get("module_decomposition")))
    contract_count = len(as_list(technical.get("api_contracts")))
    repo_count = len(as_list(delivery_plan.get("repo_tasks")))
    dependency_count = len(as_list(architecture.get("cross_repo_dependency_graph")))
    if language == "zh":
        return (
            f"- 设计覆盖：当前同步到 {module_count} 个模块、{contract_count} 个接口/契约、{dependency_count} 条跨仓或模块依赖。\n"
            f"- 实施边界：交付计划覆盖 {repo_count} 个仓库；每个仓库都必须先完成 Git 准备、阅读入口文件、再按允许文件范围修改。\n"
            "- 评审重点：优先检查方案选择理由、兼容性影响、权限/数据/异常场景，以及测试证据是否能覆盖每条验收标准。\n"
            "- 实现约束：若允许修改文件、测试命令或回滚策略缺失，本设计只能用于评审，不能作为开工许可。"
        )
    return (
        f"- Design coverage: {module_count} modules, {contract_count} contracts, and {dependency_count} dependencies were synced.\n"
        f"- Implementation boundary: {repo_count} repositories are covered; each requires Git preparation, read-first files, and narrowed edit scope.\n"
        "- Review focus: validate option rationale, compatibility impact, permission/data/edge cases, and evidence coverage.\n"
        "- Edit constraint: missing allowed files, tests, or rollback strategy means this is review material, not edit approval."
    )


def render_release_review_context(status: dict[str, Any], delivery_plan: dict[str, Any], language: str = "en") -> str:
    repo_count = len(as_list(delivery_plan.get("repo_tasks")))
    implementation_missing = len(as_list(status.get("implementation_missing")))
    release_missing = len(as_list(status.get("release_missing")))
    if language == "zh":
        return (
            f"- 发布范围：当前交付计划涉及 {repo_count} 个仓库或执行单元。\n"
            f"- 实现前缺口：{implementation_missing} 项；发布前缺口：{release_missing} 项。\n"
            "- 放行原则：只有设计评审、交付计划评审、实现完成、测试证据、代码评审和回滚策略均可追溯时，才允许进入发布。\n"
            "- 失败处理：任何验证失败都必须回到对应仓库任务或回滚步骤，不能只记录为人工观察项。"
        )
    return (
        f"- Release scope: {repo_count} repositories or execution units are in the delivery plan.\n"
        f"- Missing gates: {implementation_missing} before implementation and {release_missing} before release.\n"
        "- Approval rule: release needs traceable design review, plan review, implementation, tests, code review, and rollback evidence.\n"
        "- Failure handling: failed validation must map back to a repo task or rollback step, not only manual observation."
    )


def render_next_action(status: dict[str, Any], delivery_review: dict[str, Any]) -> str:
    primary = status.get("primary_next_action") if isinstance(status.get("primary_next_action"), dict) else {}
    for value in [primary.get("summary"), status.get("next_command")]:
        if value:
            return text(value)
    blockers = as_list(delivery_review.get("blockers"))
    if blockers and isinstance(blockers[0], dict):
        return text(blockers[0].get("suggestion") or blockers[0].get("message"))
    return "Resolve listed blockers before implementation or release."


def render_evidence_refs(artifact_dir: Path) -> str:
    refs = [
        "spec.json",
        "technical_design.json",
        "architecture_design.json",
        "delivery_plan.json",
        "design_architecture_review.json",
        "delivery_plan_review.json",
        "delivery_status.json",
    ]
    lines = [f"- `{name}`" for name in refs if (artifact_dir / name).exists()]
    return "\n".join(lines) if lines else "- No machine artifacts were synced."


def render_synced_human_docs_zh(doc_id: str, title: str, artifact_dir: Path) -> dict[str, str]:
    requirement = artifact_dir / "requirement.normalized.txt"
    spec = read_json(artifact_dir / "spec.json")
    technical = read_json(artifact_dir / "technical_design.json")
    architecture = read_json(artifact_dir / "architecture_design.json")
    test_design = read_json(artifact_dir / "test_design.json")
    delivery_plan = read_json(artifact_dir / "delivery_plan.json")
    design_review = read_json(artifact_dir / "design_architecture_review.json")
    delivery_review = read_json(artifact_dir / "delivery_plan_review.json")
    status = read_json(artifact_dir / "delivery_status.json")
    requirement_text = requirement.read_text(encoding="utf-8") if requirement.exists() else ""
    heading = title or str(spec.get("title") or doc_id)
    return {
        "spec": (
            f"# {heading} 需求说明\n\n"
            "## 一、摘要\n\n"
            f"- 文档编号：`{doc_id}`\n"
            f"- 当前结论：`{zh_text(spec.get('decision'), '未知')}`\n"
            f"- 是否涉及权限敏感场景：{zh_text((spec.get('permission_scope') or {}).get('sensitive'), '未知')}\n"
            "- 本文面向需求评审、技术设计和交付计划使用，机器可读依据见证据引用章节。\n\n"
            "### 阅读与评审重点\n\n"
            f"{render_review_context(spec, 'zh')}\n\n"
            "## 二、背景与目标\n\n"
            f"{section_paragraph('业务背景', [text(spec.get('requirement_summary') or spec.get('summary') or heading)], '未同步到业务背景。')}\n\n"
            f"{section_paragraph('用户场景', [summarize_dict_item(item, ['actor', 'trigger', 'expected_outcome'], 'zh') for item in as_list(spec.get('user_scenarios')) if isinstance(item, dict)] + [text(item) for item in as_list(spec.get('user_scenarios')) if not isinstance(item, dict)], '未记录用户场景。')}\n\n"
            f"{section_paragraph('业务目标', [text(item.get('objective') or item.get('summary') or item) for item in as_list(spec.get('business_objectives')) if isinstance(item, dict)] + [text(item) for item in as_list(spec.get('business_objectives')) if not isinstance(item, dict)], '未记录业务目标。')}\n\n"
            "## 三、范围与非目标\n\n"
            f"{render_scope(spec, text(spec.get('summary') or heading), 'zh')}\n\n"
            "## 四、需求澄清\n\n"
            f"{render_requirement_clarification_zh(spec)}\n\n"
            "### 澄清记录\n\n"
            f"{render_clarification_log(spec, 'zh')}\n\n"
            "## 五、需求原文\n\n"
            f"{requirement_text.strip() or '未同步到需求原文。'}\n\n"
            "## 六、验收标准\n\n"
            f"{render_acceptance(spec, 'zh')}\n\n"
            "## 七、业务规则解释\n\n"
            f"{render_business_rules(spec)}\n\n"
            "## 八、需求到验收追踪图\n\n"
            f"{render_requirement_trace_mermaid(spec, 'zh')}\n\n"
            "## 九、未决问题\n\n"
            f"{render_open_questions(spec, language='zh')}\n\n"
            "## 十、证据引用\n\n"
            "- `spec.json`：结构化需求、范围、验收标准和开放问题。\n"
            "- `requirement.normalized.txt`：归一化后的需求原文。\n\n"
            f"{render_evidence_refs(artifact_dir)}\n"
        ),
        "design": (
            f"# {heading} 技术设计\n\n"
            "## 一、摘要\n\n"
            f"- 文档编号：`{doc_id}`\n"
            f"- 技术设计状态：`{zh_text(technical.get('decision'), '草稿')}`\n"
            f"- 架构设计状态：`{zh_text(architecture.get('decision'), '草稿')}`\n"
            f"- 交付计划状态：`{zh_text(delivery_plan.get('decision'), '草稿')}`\n"
            "- 本文用于设计评审和实施前检查，关键结论均应能追溯到 machine artifacts。\n\n"
            "### 阅读与评审重点\n\n"
            f"{render_design_review_context(technical, architecture, delivery_plan, 'zh')}\n\n"
            "## 二、现状问题与设计目标\n\n"
            f"{render_named_items([technical.get('current_state_analysis')], ['existing_behavior', 'code_entrypoints', 'known_constraints', 'reuse_points'], '未同步到现状分析。', 'zh')}\n\n"
            f"{render_named_items([architecture.get('current_architecture')], ['system_context', 'repo_entrypoints', 'upstream_downstream', 'constraints'], '未同步到当前架构分析。', 'zh')}\n\n"
            f"{section_paragraph('设计目标', [text(item.get('behavior') or item.get('summary') or item) for item in as_list(technical.get('target_behavior')) if isinstance(item, dict)], '未同步到目标行为。')}\n\n"
            f"{section_paragraph('非目标', [str(item) for item in as_list((technical.get('design_scope') or {}).get('non_goals'))], '未记录非目标。')}\n\n"
            "## 三、方案对比与选择\n\n"
            f"{render_solution_options(technical, architecture, 'zh')}\n\n"
            "## 四、决策记录\n\n"
            f"{render_decision_records(architecture, technical, language='zh')}\n\n"
            "## 五、业务流程\n\n"
            f"{render_process_flows(technical, 'zh')}\n\n"
            "### 流程图\n\n"
            f"{render_process_mermaid(technical, 'zh')}\n\n"
            "## 六、模块与接口设计\n\n"
            f"{render_named_items(as_list(technical.get('module_decomposition')), ['module', 'responsibility', 'input', 'output', 'coupling_control'], '未同步到模块设计。', 'zh')}\n\n"
            f"{render_named_items(as_list(technical.get('api_contracts')), ['contract', 'compatibility', 'old_consumer_impact'], '未同步到接口影响。', 'zh')}\n\n"
            f"{render_named_items(as_list(technical.get('interface_examples')), ['name', 'request', 'response', 'error_response'], '未同步到接口示例。', 'zh')}\n\n"
            "## 七、数据、权限、页面与异常场景\n\n"
            f"{render_named_items(as_list(technical.get('data_design')), ['read_rule', 'write_rule', 'migration'], '未同步到数据设计。', 'zh')}\n\n"
            f"{render_named_items(as_list(technical.get('permission_model')), ['role', 'rule', 'negative_case'], '未同步到权限规则。', 'zh')}\n\n"
            f"{render_named_items(as_list(technical.get('exception_and_edge_cases')), ['case', 'handling'], '未同步到异常场景。', 'zh')}\n\n"
            f"{render_named_items(as_list(technical.get('ui_ue_design')), ['page_or_route', 'user_goal', 'entry_point', 'permission_visibility', 'acceptance_evidence'], '未同步到页面影响。', 'zh')}\n\n"
            "## 八、架构与运维影响\n\n"
            f"{render_named_items(as_list(architecture.get('cross_repo_dependency_graph')), ['from', 'to', 'contract', 'change'], '未同步到跨仓依赖图。', 'zh')}\n\n"
            "### 模块/仓库关系图\n\n"
            f"{render_architecture_mermaid(architecture, 'zh')}\n\n"
            f"{render_named_items(as_list(architecture.get('integration_sequence')), ['step', 'actor', 'action', 'failure_handling'], '未同步到集成顺序。', 'zh')}\n\n"
            f"{render_named_items(as_list(architecture.get('deployment_impact_matrix')), ['repo', 'artifact', 'order', 'config_change', 'restart_required'], '未同步到发布影响矩阵。', 'zh')}\n\n"
            f"{render_named_items(as_list(architecture.get('rollback_strategy')), ['repo', 'steps', 'data_risk'], '未同步到回滚策略。', 'zh')}\n\n"
            "## 九、交付执行计划\n\n"
            f"{render_delivery_tasks(delivery_plan, 'zh')}\n\n"
            "## 十、需求追踪关系\n\n"
            "- 追踪关系：每个设计决策必须能回到 `spec.json` 的验收标准，并向前关联到 `test_design.json` 测试用例、`delivery_plan.json` 任务和发布证据。\n"
            "- 如果任一验收标准缺少设计引用、测试用例或交付证据责任人，评审时应阻止进入实现。\n\n"
            "## 十一、测试与验收证据\n\n"
            f"{render_named_items(as_list(technical.get('acceptance_mapping')), ['acceptance_id', 'design_refs', 'evidence_required'], '未同步到验收证据映射。', 'zh')}\n\n"
            f"{render_named_items(as_list(technical.get('test_strategy')), ['case', 'type', 'evidence'], '未同步到测试策略。', 'zh')}\n\n"
            "### 测试用例\n\n"
            f"{render_test_cases(test_design, 'zh')}\n\n"
            "## 十二、风险与未过门禁\n\n"
            f"{render_blockers(delivery_plan, architecture)}\n\n"
            "## 十三、证据引用\n\n"
            "- `technical_design.json`：技术设计、接口、数据、权限和测试映射。\n"
            "- `architecture_design.json`：架构边界、跨仓依赖、部署和回滚策略。\n"
            "- `delivery_plan.json`：实施顺序、文件范围、证据和回滚检查。\n\n"
            f"{render_evidence_refs(artifact_dir)}\n"
        ),
        "release": (
            f"# {heading} 发布准备\n\n"
            "## 一、摘要\n\n"
            f"- 文档编号：`{doc_id}`\n"
            f"- 当前下一阶段：`{zh_text(status.get('next_stage'), '未知')}`\n"
            f"- 是否允许实现：`{zh_text(status.get('can_implement'), '否')}`\n"
            f"- 是否允许发布：`{zh_text(status.get('can_release'), '否')}`\n"
            "- 本文用于实现前、发布前和上线后观察检查。\n\n"
            "### 阅读与评审重点\n\n"
            f"{render_release_review_context(status, delivery_plan, 'zh')}\n\n"
            "## 二、发布前检查\n\n"
            "### 实现前必须补齐\n\n"
            f"{bullet_lines([str(item) for item in as_list(status.get('implementation_missing'))], '未同步到实现前缺口。')}\n\n"
            "### 发布前必须补齐\n\n"
            f"{bullet_lines([str(item) for item in as_list(status.get('release_missing'))], '未同步到发布前缺口。')}\n\n"
            "## 三、执行步骤\n\n"
            f"{render_delivery_tasks(delivery_plan, 'zh')}\n\n"
            "## 四、发布与回滚顺序图\n\n"
            f"{render_release_mermaid(delivery_plan, 'zh')}\n\n"
            "## 五、验证步骤\n\n"
            f"{render_named_items(as_list(technical.get('acceptance_mapping')), ['acceptance_id', 'evidence_required'], '未同步到验收验证步骤。', 'zh')}\n\n"
            f"{render_named_items(as_list(technical.get('test_strategy')), ['case', 'type', 'evidence'], '未同步到测试验证步骤。', 'zh')}\n\n"
            "## 六、需求追踪关系\n\n"
            "- 追踪关系：发布验证必须把 `spec.json` 验收标准、`test_design.json` 测试用例、`delivery_plan_review.json` 门禁和回滚证据串联起来。\n"
            "- 任一验收标准没有执行证据或回滚责任人时，发布必须保持阻塞。\n\n"
            "### 测试用例\n\n"
            f"{render_test_cases(test_design, 'zh')}\n\n"
            "## 七、回滚步骤\n\n"
            f"{render_named_items(as_list(architecture.get('rollback_strategy')), ['repo', 'steps', 'data_risk'], '未同步到回滚步骤。', 'zh')}\n\n"
            "## 八、评审结论\n\n"
            f"- 设计评审：`{zh_text(design_review.get('decision'), '未知')}`\n"
            f"- 交付计划评审：`{zh_text(delivery_review.get('decision'), '未知')}`\n\n"
            "## 九、风险处置与阻塞项\n\n"
            f"{render_blockers(design_review, delivery_review, status)}\n\n"
            "## 十、上线后观察\n\n"
            f"{render_named_items(as_list(architecture.get('observability')), ['signal', 'owner'], '未同步到观察指标。', 'zh')}\n\n"
            f"{render_named_items(as_list(architecture.get('monitoring_alerts')), ['signal', 'owner', 'trigger', 'action'], '未同步到告警策略。', 'zh')}\n\n"
            "## 十一、下一步动作\n\n"
            f"- {render_next_action(status, delivery_review)}\n\n"
            "## 十二、证据引用\n\n"
            "- `delivery_status.json`：当前阶段、允许实现/发布状态和缺口。\n"
            "- `delivery_plan_review.json`：交付计划评审结论。\n"
            "- `design_architecture_review.json`：设计评审结论。\n\n"
            f"{render_evidence_refs(artifact_dir)}\n"
        ),
    }


def render_synced_human_docs(doc_id: str, title: str, artifact_dir: Path) -> dict[str, str]:
    requirement = artifact_dir / "requirement.normalized.txt"
    spec = read_json(artifact_dir / "spec.json")
    technical = read_json(artifact_dir / "technical_design.json")
    architecture = read_json(artifact_dir / "architecture_design.json")
    test_design = read_json(artifact_dir / "test_design.json")
    delivery_plan = read_json(artifact_dir / "delivery_plan.json")
    design_review = read_json(artifact_dir / "design_architecture_review.json")
    delivery_review = read_json(artifact_dir / "delivery_plan_review.json")
    status = read_json(artifact_dir / "delivery_status.json")
    requirement_text = requirement.read_text(encoding="utf-8") if requirement.exists() else ""
    heading = title or str(spec.get("title") or doc_id)
    return {
        "spec": (
            f"# {heading} Spec\n\n"
            "## Executive Summary\n\n"
            f"- Doc ID: `{doc_id}`\n"
            f"- Current decision: `{text(spec.get('decision'), 'unknown')}`\n"
            f"- Permission sensitivity: {text((spec.get('permission_scope') or {}).get('sensitive'), 'unknown')}\n\n"
            "## Review Focus\n\n"
            f"{render_review_context(spec, 'en')}\n\n"
            "## Background And Goals\n\n"
            f"{section_paragraph('Business Background', [text(spec.get('requirement_summary') or spec.get('summary') or heading)], 'Business background was not synced.')}\n\n"
            f"{section_paragraph('User Scenarios', [text(item.get('scenario') or item.get('summary') or item) for item in as_list(spec.get('user_scenarios')) if isinstance(item, dict)] + [text(item) for item in as_list(spec.get('user_scenarios')) if not isinstance(item, dict)], 'No user scenarios were recorded.')}\n\n"
            f"{section_paragraph('Business Objectives', [text(item.get('objective') or item.get('summary') or item) for item in as_list(spec.get('business_objectives')) if isinstance(item, dict)] + [text(item) for item in as_list(spec.get('business_objectives')) if not isinstance(item, dict)], 'No business objectives were recorded.')}\n\n"
            "## Scope\n\n"
            f"{render_scope(spec, text(spec.get('summary') or heading))}\n\n"
            "## Requirement Clarification\n\n"
            f"{render_requirement_clarification(spec)}\n\n"
            "### Clarification Log\n\n"
            f"{render_clarification_log(spec, 'en')}\n\n"
            "## Requirement Source\n\n"
            f"{requirement_text.strip() or 'Requirement text not synced.'}\n\n"
            "## Acceptance Criteria\n\n"
            f"{render_acceptance(spec)}\n\n"
            "## Business Rules\n\n"
            f"{render_business_rules(spec)}\n\n"
            "## Open Questions\n\n"
            f"{render_open_questions(spec)}\n\n"
            "## Requirement Traceability Diagram\n\n"
            f"{render_requirement_trace_mermaid(spec, 'en')}\n\n"
            "## Evidence References\n\n"
            "- `spec.json`: structured requirement, scope, acceptance criteria, and open questions.\n"
            "- `requirement.normalized.txt`: normalized requirement source.\n\n"
            f"{render_evidence_refs(artifact_dir)}\n"
        ),
        "design": (
            f"# {heading} Design\n\n"
            "## Executive Summary\n\n"
            f"- Doc ID: `{doc_id}`\n"
            f"- Technical decision: `{text(technical.get('decision'), 'draft')}`\n"
            f"- Architecture decision: `{text(architecture.get('decision'), 'draft')}`\n"
            f"- Delivery plan decision: `{text(delivery_plan.get('decision'), 'draft')}`\n\n"
            "## Review Focus\n\n"
            f"{render_design_review_context(technical, architecture, delivery_plan, 'en')}\n\n"
            "## Current State, Problem, And Goals\n\n"
            f"{render_named_items([technical.get('current_state_analysis')], ['existing_behavior', 'code_entrypoints', 'known_constraints', 'reuse_points'], 'No current-state analysis was synced.')}\n\n"
            f"{render_named_items([architecture.get('current_architecture')], ['system_context', 'repo_entrypoints', 'upstream_downstream', 'constraints'], 'No current architecture analysis was synced.')}\n\n"
            f"{section_paragraph('Design Goals', [text(item.get('behavior') or item.get('summary') or item) for item in as_list(technical.get('target_behavior')) if isinstance(item, dict)], 'No target behavior was synced.')}\n\n"
            f"{section_paragraph('Non Goals', [str(item) for item in as_list((technical.get('design_scope') or {}).get('non_goals'))], 'No non-goals were recorded.')}\n\n"
            "## Options And Decision\n\n"
            f"{render_solution_options(technical, architecture, 'en')}\n\n"
            "## Decision Records\n\n"
            f"{render_decision_records(architecture, technical, language='en')}\n\n"
            "## Process Flow\n\n"
            f"{render_process_flows(technical)}\n\n"
            "### Flow Diagram\n\n"
            f"{render_process_mermaid(technical, 'en')}\n\n"
            "## Module And Contract Design\n\n"
            f"{render_named_items(as_list(technical.get('module_decomposition')), ['module', 'responsibility', 'input', 'output', 'coupling_control'], 'No module design was synced.')}\n\n"
            f"{render_named_items(as_list(technical.get('api_contracts')), ['contract', 'compatibility', 'old_consumer_impact'], 'No API contract changes were confirmed.')}\n\n"
            f"{render_named_items(as_list(technical.get('interface_examples')), ['name', 'request', 'response', 'error_response'], 'No interface examples were synced.')}\n\n"
            "## Data And UI Impact\n\n"
            f"{render_named_items(as_list(technical.get('data_design')), ['read_rule', 'write_rule', 'migration'], 'No data design was synced.')}\n\n"
            f"{render_named_items(as_list(technical.get('permission_model')), ['role', 'rule', 'negative_case'], 'No permission rules were synced.')}\n\n"
            f"{render_named_items(as_list(technical.get('exception_and_edge_cases')), ['case', 'handling'], 'No exception scenarios were synced.')}\n\n"
            f"{render_named_items(as_list(technical.get('ui_ue_design')), ['page_or_route', 'user_goal', 'entry_point', 'permission_visibility', 'acceptance_evidence'], 'No UI impact was confirmed.')}\n\n"
            "## Architecture And Operations\n\n"
            f"{render_named_items(as_list(architecture.get('cross_repo_dependency_graph')), ['from', 'to', 'contract', 'change'], 'No dependency graph was synced.')}\n\n"
            "### Module / Repository Diagram\n\n"
            f"{render_architecture_mermaid(architecture, 'en')}\n\n"
            f"{render_named_items(as_list(architecture.get('integration_sequence')), ['step', 'actor', 'action', 'failure_handling'], 'No integration sequence was synced.')}\n\n"
            f"{render_named_items(as_list(architecture.get('deployment_impact_matrix')), ['repo', 'artifact', 'order', 'config_change', 'restart_required'], 'No deployment impact matrix was synced.')}\n\n"
            f"{render_named_items(as_list(architecture.get('rollback_strategy')), ['repo', 'steps', 'data_risk'], 'No rollback strategy was synced.')}\n\n"
            "## Delivery Plan\n\n"
            f"{render_delivery_tasks(delivery_plan)}\n\n"
            "## Requirement Traceability\n\n"
            "- Traceability: every design decision must map back to `spec.json` acceptance criteria and forward to `test_design.json` test cases, `delivery_plan.json` tasks, and release evidence.\n"
            "- Reviewers should reject implementation if an acceptance criterion has no design reference, test case, or delivery evidence owner.\n\n"
            "## Test And Acceptance Evidence\n\n"
            f"{render_named_items(as_list(technical.get('acceptance_mapping')), ['acceptance_id', 'design_refs', 'evidence_required'], 'No acceptance evidence mapping was synced.')}\n\n"
            f"{render_named_items(as_list(technical.get('test_strategy')), ['case', 'type', 'evidence'], 'No test strategy was synced.')}\n\n"
            "### Test Cases\n\n"
            f"{render_test_cases(test_design, 'en')}\n\n"
            "## Risks And Open Gates\n\n"
            f"{render_blockers(delivery_plan, architecture)}\n\n"
            "## Evidence References\n\n"
            "- `technical_design.json`: technical design, API/data/permission/test mapping.\n"
            "- `architecture_design.json`: architecture boundaries, dependency graph, deployment, rollback.\n"
            "- `delivery_plan.json`: implementation sequence, file scope, evidence, rollback checks.\n\n"
            f"{render_evidence_refs(artifact_dir)}\n"
        ),
        "release": (
            f"# {heading} Release\n\n"
            "## Executive Summary\n\n"
            f"- Doc ID: `{doc_id}`\n"
            f"- Next stage: `{text(status.get('next_stage'), 'unknown')}`\n"
            f"- Implementation allowed: `{text(status.get('can_implement'), 'false')}`\n"
            f"- Release allowed: `{text(status.get('can_release'), 'false')}`\n\n"
            "## Review Focus\n\n"
            f"{render_release_review_context(status, delivery_plan, 'en')}\n\n"
            "## Missing Readiness\n\n"
            "### Before Implementation\n\n"
            f"{bullet_lines([str(item) for item in as_list(status.get('implementation_missing'))], 'No implementation gaps were synced.')}\n\n"
            "### Before Release\n\n"
            f"{bullet_lines([str(item) for item in as_list(status.get('release_missing'))], 'No release gaps were synced.')}\n\n"
            "## Execution Steps\n\n"
            f"{render_delivery_tasks(delivery_plan)}\n\n"
            "## Release And Rollback Sequence\n\n"
            f"{render_release_mermaid(delivery_plan, 'en')}\n\n"
            "## Validation Steps\n\n"
            f"{render_named_items(as_list(technical.get('acceptance_mapping')), ['acceptance_id', 'evidence_required'], 'No acceptance validation steps were synced.')}\n\n"
            f"{render_named_items(as_list(technical.get('test_strategy')), ['case', 'type', 'evidence'], 'No test validation steps were synced.')}\n\n"
            "## Requirement Traceability\n\n"
            "- Traceability: release validation must connect `spec.json` acceptance criteria, `test_design.json` cases, `delivery_plan_review.json` gates, and rollback evidence before any production release.\n"
            "- A release remains blocked when any acceptance criterion lacks execution evidence or rollback ownership.\n\n"
            "### Test Cases\n\n"
            f"{render_test_cases(test_design, 'en')}\n\n"
            "## Rollback Steps\n\n"
            f"{render_named_items(as_list(architecture.get('rollback_strategy')), ['repo', 'steps', 'data_risk'], 'No rollback steps were synced.')}\n\n"
            "## Review Decisions\n\n"
            f"- Design review: `{text(design_review.get('decision'), 'unknown')}`\n"
            f"- Delivery plan review: `{text(delivery_review.get('decision'), 'unknown')}`\n\n"
            "## Blockers\n\n"
            f"{render_blockers(design_review, delivery_review, status)}\n\n"
            "## Next Action\n\n"
            f"- {render_next_action(status, delivery_review)}\n\n"
            "## Post Release Observation\n\n"
            f"{render_named_items(as_list(architecture.get('observability')), ['signal', 'owner'], 'No observation signals were synced.')}\n\n"
            f"{render_named_items(as_list(architecture.get('monitoring_alerts')), ['signal', 'owner', 'trigger', 'action'], 'No monitoring alerts were synced.')}\n\n"
            "## Evidence References\n\n"
            "- `delivery_status.json`: current stage, implementation/release readiness, missing gates.\n"
            "- `delivery_plan_review.json`: delivery plan review result.\n"
            "- `design_architecture_review.json`: design review result.\n\n"
            f"{render_evidence_refs(artifact_dir)}\n"
        ),
    }


def sync(docs_root: Path, doc_id: str, artifact_dir: Path, title: str = "", git_url: str = "", doc_language: str = "en") -> dict[str, Any]:
    docs_root = docs_root.expanduser().resolve()
    artifact_dir = artifact_dir.expanduser().resolve()
    language = normalize_doc_language(doc_language)
    manifest = init(docs_root, doc_id, git_url=git_url, title=title, doc_language=language)
    human_docs = render_synced_human_docs_zh(doc_id, title, artifact_dir) if language == "zh" else render_synced_human_docs(doc_id, title, artifact_dir)
    human_targets = {
        "spec": docs_root / manifest["human_docs"]["spec"],
        "design": docs_root / manifest["human_docs"]["design"],
        "release": docs_root / manifest["human_docs"]["release"],
    }
    for name, content in human_docs.items():
        human_targets[name].parent.mkdir(parents=True, exist_ok=True)
        human_targets[name].write_text(content, encoding="utf-8")

    bundles = {
        "spec": ["spec.json"],
        "design": ["technical_design.json", "architecture_design.json", "test_design.json", "delivery_plan.json"],
        "review": ["design_architecture_review.json", "delivery_plan_review.json", "delivery_status.json"],
        "release": ["implementation_completion_gate.json", "code_review_gate.json", "test_evidence_gate.json", "release_gate.json"],
    }
    synced_machine: list[str] = []
    for name, files in bundles.items():
        target = docs_root / manifest["machine_artifacts"][name]
        payload: dict[str, Any] = {
            "schema": "codex-docs-machine-bundle-v1",
            "doc_id": doc_id,
            "artifact_type": name,
            "source_artifact_dir": str(artifact_dir),
            "artifacts": {},
        }
        for filename in files:
            source = artifact_dir / filename
            if source.exists():
                payload["artifacts"][filename] = read_json(source)
        if payload["artifacts"]:
            write_json(target, payload)
            synced_machine.append(str(target.relative_to(docs_root)))

    raw_dir = docs_root / "machine/raw" / doc_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    copied_raw: list[str] = []
    for source in sorted(artifact_dir.glob("*.json")):
        dest = raw_dir / source.name
        shutil.copy2(source, dest)
        copied_raw.append(str(dest.relative_to(docs_root)))

    manifest["synced_from"] = str(artifact_dir)
    manifest["synced_human_docs"] = [str(path.relative_to(docs_root)) for path in human_targets.values()]
    manifest["synced_machine_artifacts"] = synced_machine
    manifest["raw_artifacts"] = copied_raw
    write_json(docs_root / "indexes" / f"{doc_id}.manifest.json", manifest)
    return {
        "schema": "codex-docs-governor-sync-v1",
        "decision": "pass",
        "doc_id": doc_id,
        "docs_root": str(docs_root),
        "artifact_dir": str(artifact_dir),
        "doc_language": language,
        "manifest": str(docs_root / "indexes" / f"{doc_id}.manifest.json"),
        "human_docs": manifest["synced_human_docs"],
        "machine_artifacts": manifest["synced_machine_artifacts"],
        "raw_artifacts": copied_raw,
        "blockers": [],
    }


def configure(docs_root: Path, git_url: str = "") -> dict[str, Any]:
    docs_root = docs_root.expanduser().resolve()
    docs_root.mkdir(parents=True, exist_ok=True)
    git_initialized = False
    if not is_git_repo(docs_root):
        proc = subprocess.run(["git", "init"], cwd=docs_root, text=True, capture_output=True)
        git_initialized = proc.returncode == 0
    remote_configured = False
    remote_warning = ""
    if git_url:
        proc = subprocess.run(["git", "remote", "get-url", "origin"], cwd=docs_root, text=True, capture_output=True)
        current = proc.stdout.strip() if proc.returncode == 0 else ""
        if current and current != git_url:
            remote_warning = f"origin already configured as {current}"
        elif not current:
            add = subprocess.run(["git", "remote", "add", "origin", git_url], cwd=docs_root, text=True, capture_output=True)
            remote_configured = add.returncode == 0
        else:
            remote_configured = True
    config_data = load_docs_config_module().save(ROOT, docs_root, git_url)
    return {
        "schema": "codex-docs-workspace-config-v1",
        "decision": "pass" if not remote_warning else "block",
        "docs_root": str(docs_root),
        "git_url": git_url,
        "git_initialized": git_initialized,
        "remote_configured": remote_configured,
        "config": str(ROOT / ".codex-engineering-docs.json"),
        "blockers": [{"source": "git_remote", "message": remote_warning}] if remote_warning else [],
        "next_action": "Run docs-governor init for each new doc_id without repeating the docs remote.",
    }


def init(docs_root: Path, doc_id: str, git_url: str = "", title: str = "", doc_language: str = "en") -> dict[str, Any]:
    for directory in DIRS:
        (docs_root / directory).mkdir(parents=True, exist_ok=True)
    config = configure(docs_root, git_url)
    language = normalize_doc_language(doc_language)
    materialized = materialize_doc_files(docs_root, doc_id, title, language)
    manifest = {
        "schema": "codex-docs-governor-v1",
        "doc_id": doc_id,
        "title": title,
        "doc_language": language,
        "docs_root": str(docs_root.expanduser().resolve()),
        "git_initialized": config.get("git_initialized", False),
        "workspace_config": config.get("schema", ""),
        "human_docs": {
            "spec": f"human/specs/{doc_id}.md",
            "design": f"human/designs/{doc_id}.md",
            "release": f"human/releases/{doc_id}.md",
        },
        "machine_artifacts": {
            "spec": f"machine/specs/{doc_id}.spec.json",
            "design": f"machine/designs/{doc_id}.design.json",
            "review": f"machine/reviews/{doc_id}.review.json",
            "release": f"machine/releases/{doc_id}.release.json",
        },
        "materialized": materialized,
        "rule": "Commit docs changes on a branch and merge through normal review; do not store local absolute paths or secrets.",
    }
    write_json(docs_root / "indexes" / f"{doc_id}.manifest.json", manifest)
    return manifest


def is_git_repo(path: Path) -> bool:
    proc = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=path, text=True, capture_output=True)
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def validate(docs_root: Path, doc_id: str, require_git: bool = False) -> dict[str, Any]:
    manifest_path = docs_root / "indexes" / f"{doc_id}.manifest.json"
    blockers: list[dict[str, str]] = []
    for directory in DIRS:
        if not (docs_root / directory).is_dir():
            blockers.append({"source": directory, "message": "required docs directory missing"})
    if not manifest_path.exists():
        blockers.append({"source": "manifest", "message": "doc manifest missing"})
    else:
        manifest = read_json(manifest_path)
        for group in ["human_docs", "machine_artifacts"]:
            values = manifest.get(group) if isinstance(manifest.get(group), dict) else {}
            for name, rel_path in values.items():
                target = docs_root / str(rel_path)
                if not target.exists():
                    blockers.append({"source": f"{group}.{name}", "message": "manifest file missing"})
                elif not target.read_text(encoding="utf-8").strip():
                    blockers.append({"source": f"{group}.{name}", "message": "manifest file is empty"})
    if require_git:
        if not docs_root.exists():
            blockers.append({"source": "docs_root", "message": "docs root missing"})
        elif not is_git_repo(docs_root):
            blockers.append({"source": "docs_git", "message": "docs root must be a git repository"})
    return {
        "schema": "codex-docs-governor-validation-v1",
        "decision": "block" if blockers else "pass",
        "blockers": blockers,
        "manifest": str(manifest_path),
        "git_required": require_git,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize or validate delivery docs structure")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_configure = sub.add_parser("configure")
    p_configure.add_argument("--docs-root", required=True)
    p_configure.add_argument("--git-url", default="")
    p_sync = sub.add_parser("sync")
    p_sync.add_argument("--docs-root", required=True)
    p_sync.add_argument("--doc-id", required=True)
    p_sync.add_argument("--artifact-dir", required=True)
    p_sync.add_argument("--title", default="")
    p_sync.add_argument("--git-url", default="")
    p_sync.add_argument("--doc-language", choices=["en", "zh"], default="en")
    for cmd in ["init", "validate"]:
        p = sub.add_parser(cmd)
        p.add_argument("--docs-root", required=True)
        p.add_argument("--doc-id", required=True)
        p.add_argument("--title", default="")
        p.add_argument("--git-url", default="")
        p.add_argument("--doc-language", choices=["en", "zh"], default="en")
        p.add_argument("--require-git", action="store_true")
    args = parser.parse_args()
    if args.cmd == "configure":
        result = configure(Path(args.docs_root), args.git_url)
    elif args.cmd == "init":
        result = init(Path(args.docs_root), args.doc_id, args.git_url, args.title, args.doc_language)
    elif args.cmd == "sync":
        result = sync(Path(args.docs_root), args.doc_id, Path(args.artifact_dir), args.title, args.git_url, args.doc_language)
    else:
        result = validate(Path(args.docs_root), args.doc_id, args.require_git)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("decision") != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
