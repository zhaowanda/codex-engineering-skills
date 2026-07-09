#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
DIRS = ["human/specs", "human/designs", "human/tests", "human/releases", "machine/specs", "machine/designs", "machine/reviews", "machine/releases", "baseline", "indexes"]
MACHINE_ARTIFACTS = {
    "spec": ("machine/specs", ".spec.json"),
    "design": ("machine/designs", ".design.json"),
    "review": ("machine/reviews", ".review.json"),
    "release": ("machine/releases", ".release.json"),
}
EXPERT_SUPPLEMENTAL_ARTIFACTS = [
    "runtime_sequence_evidence.json",
]


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


def load_docs_i18n_module() -> Any:
    path = Path(__file__).resolve().parent / "docs_i18n.py"
    spec = importlib.util.spec_from_file_location("docs_i18n", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def load_doc_model_module() -> Any:
    path = Path(__file__).resolve().parent / "doc_model.py"
    spec = importlib.util.spec_from_file_location("doc_model", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


DOCS_I18N = load_docs_i18n_module()
DOC_MODEL = load_doc_model_module()


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
        kind_label = {"spec": "需求说明", "design": "技术设计", "test": "测试设计", "release": "发布准备"}.get(kind, kind)
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
        "test": docs_root / "human/tests" / f"{doc_id}.md",
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


def human_value(value: Any, language: str = "en", default: str | None = None) -> str:
    return DOCS_I18N.render_value(value, language, default)


def clean_joined_text(value: str, language: str = "en") -> str:
    rendered = value.strip()
    if language == "zh":
        replacements = {
            "。;": "；",
            ".;": "；",
            "。,": "；",
            ".,": "；",
            "；,": "；",
            ",,": "，",
        }
        for source, target in replacements.items():
            rendered = rendered.replace(source, target)
        rendered = re.sub(r"\s*；\s*", "；", rendered)
        rendered = re.sub(r"；{2,}", "；", rendered)
        return rendered.strip("； ")
    rendered = rendered.replace(".;", ";").replace(".,", ";")
    return re.sub(r"\s+", " ", rendered).strip()


def render_readable_value(value: Any, language: str = "en") -> str:
    if value in (None, "", [], {}):
        return ""
    def render_one(item: Any) -> str:
        if language == "zh":
            protected, placeholders = protect_code_tokens(text(item, ""))
            return restore_code_tokens(clean_joined_text(human_value(protected, language, ""), language), placeholders)
        return clean_joined_text(human_value(item, language, ""), language)

    if isinstance(value, list):
        items = [
            render_one(item)
            for item in value
            if item not in (None, "", [], {})
        ]
        items = [item for item in items if item]
        if not items:
            return ""
        if len(items) == 1:
            return items[0]
        return "\n" + "\n".join(f"  - {item}" for item in items)
    return render_one(value)


def contains_command_token(value: Any) -> bool:
    if isinstance(value, str):
        return bool(re.search(r"\b(?:npm|pnpm|yarn)\s+run\b|\bmvn\s+", value))
    if isinstance(value, list):
        return any(contains_command_token(item) for item in value)
    if isinstance(value, dict):
        return any(contains_command_token(item) for item in value.values())
    return False


ZH_DEFAULT_PHRASES = {
    "target module to be confirmed": "需结合代码核对的责任模块",
    "existing entrypoint to be confirmed": "需结合代码核对的现有入口",
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
    "Read 待确认目标模块 and adjacent tests before editing.": "修改前阅读责任模块及相邻测试。",
    "Confirm 待确认目标模块 scope against reviewed design.": "按已评审设计核对责任模块范围。",
    "Run validation for 待确认目标模块 and mapped acceptance checks.": "运行责任模块校验和已映射的验收检查。",
    "Capture command logs and acceptance evidence for 待确认目标模块.": "采集责任模块的命令日志和验收证据。",
    "Verify rollback path for 待确认目标模块.": "验证责任模块的回滚路径。",
    "inspected-files: 待确认目标模块": "已检查文件：责任模块",
    "scope-confirmation for 待确认目标模块": "责任模块范围核对",
    "git diff for 待确认目标模块": "责任模块 git diff",
    "rollback verification for 待确认目标模块": "责任模块回滚验证",
    "待确认目标模块 behavior and dependencies understood": "已理解责任模块行为和依赖",
    "scope still matches architecture responsibilities": "范围仍匹配架构职责",
    "diff only touches 待确认目标模块": "diff 仅触达责任模块",
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
    "read through target module to be confirmed": "通过责任模块读取",
    "write through target module to be confirmed only if requirement changes state": "仅在需求涉及状态变更时，通过责任模块写入",
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
    "npm run build:test evidence": "npm run build:test 证据",
    "test evidence": "测试证据",
    "Read": "阅读",
    "minimal": "影响极小",
    "depends on implementation": "取决于实现",
    "explicit contract": "契约清晰",
    "coordination and compatibility risk": "协同和兼容性风险",
    "contract, integration, and regression tests": "契约、集成和回归测试",
    "depends on new calls": "取决于新增调用",
    "rollback simplicity": "回滚简单性",
    "test surface": "测试面",
    "contract safety": "契约安全",
    "ownership": "责任归属",
    "compatibility": "兼容性",
    "release coordination": "发布协同",
    "contract risk": "契约风险",
    "Deploy": "发布",
    " only; confirm no provider rollout is needed.": "；确认无需生产方发布。",
    "revert ": "回滚 ",
    "Existing owner module can satisfy acceptance criteria": "现有责任模块可满足验收标准",
    "No confirmed contract or schema change is required": "无需已确认的契约或结构变更",
    "Add the smallest behavior change inside the owner module": "在责任模块内加入最小行为变更",
    "Keep existing validation, permission, and error paths intact": "保持现有校验、权限和错误路径不变",
    "low coupling": "低耦合",
    "small blast radius": "影响面小",
    "simple rollback": "回滚简单",
    "depends on existing boundaries": "依赖现有边界",
    "may need revision if code inspection reveals missing extension point": "如果代码检查发现缺少扩展点，可能需要修订",
    "edit permit limits changed files": "编辑许可限制变更文件范围",
    "regression tests cover existing behavior": "回归测试覆盖既有行为",
    "compatibility evidence before API/data change": "API 或数据变更前必须提供兼容性证据",
    "unit/integration/browser evidence as applicable": "按影响范围提供单元、集成或浏览器证据",
    "minimal; no extra dependency call by default": "影响极小；默认不增加额外依赖调用",
    "single owner artifact rollout": "单一责任制品发布",
    "Multiple modules need the behavior": "多个模块需要该行为",
    "Existing owner boundary would duplicate rules or hide a contract change": "现有责任边界会导致规则重复或隐藏契约变更",
    "Define new abstraction or contract": "定义新的抽象或契约",
    "Migrate owner module to call the new boundary": "迁移责任模块调用新边界",
    "Add contract and regression tests for old and new paths": "为新旧路径补充契约测试和回归测试",
    "clear extension point": "扩展点清晰",
    "better long-term reuse when repeated changes are expected": "适合预期存在重复变更时的长期复用",
    "larger change and migration risk": "变更范围和迁移风险更大",
    "more integration and rollback coordination": "需要更多集成和回滚协同",
    "contract freeze before consumers change": "消费方变更前冻结契约",
    "compatibility matrix for old consumers": "为旧消费方建立兼容性矩阵",
    "ordered rollback plan": "有序回滚计划",
    "contract and regression tests": "契约测试和回归测试",
    "contract test evidence": "契约测试证据",
    "regression test evidence": "回归测试证据",
    "depends on implementation; review additional calls, queries, and serialization cost": "取决于实现；需评估新增调用、查询和序列化成本",
    "may require coordinated provider/consumer rollout": "可能需要生产方和消费方协同发布",
    "revert contract and consumers in dependency order": "按依赖顺序回滚契约和消费方",
    "correctness": "正确性",
    "blast_radius": "影响面",
    "contract_clarity": "契约清晰度",
    "test_surface": "测试面",
    "future_extensibility": "未来扩展性",
    "Both can satisfy acceptance if contracts are understood.": "在契约已理解的前提下，两者都可满足验收。",
    "Scoped owner-module change touches fewer surfaces.": "责任模块内的小范围变更触达面更少。",
    "New abstraction is clearer when repeated extension is proven.": "当确认需要重复扩展时，新抽象更清晰。",
    "Single owner rollback is simpler.": "单一责任方回滚更简单。",
    "Smaller test surface unless architecture requires cross-boundary change.": "除非架构要求跨边界变更，否则测试面更小。",
    "Abstraction is better only when future changes are likely.": "只有未来变更概率较高时，抽象才更合适。",
    "Weighted qualitative score; higher is preferred unless code inspection invalidates assumptions.": "加权定性评分；除非代码检查推翻假设，否则分数越高越优先。",
    "Default to smallest safe change because it has lower blast radius, simpler rollback, and adequate correctness until code inspection proves abstraction is needed.": "默认选择最小安全变更，因为它影响面更小、回滚更简单，并且在代码检查证明需要抽象前具备足够正确性。",
    "Less future extensibility than a new abstraction": "未来扩展性弱于新增抽象",
    "Higher coordination, contract, and rollback cost unless code inspection proves the extension point is required.": "除非代码检查证明必须引入扩展点，否则协同、契约和回滚成本更高。",
    "Owner repo can satisfy the requirement": "责任仓库可满足需求",
    "Producer/consumer contracts can remain compatible": "生产方/消费方契约可保持兼容",
    "Rollback should stay single-repo": "回滚应保持单仓库范围",
    "No new cross-repo integration sequence unless code inspection proves a contract change.": "除非代码检查证明需要契约变更，否则不新增跨仓集成顺序。",
    "lower release coordination": "发布协同成本更低",
    "requires owner confirmation": "需要责任方确认",
    "less extensible if this behavior becomes shared": "如果该行为后续共享，扩展性较弱",
    "repo responsibility review": "仓库职责评审",
    "contract compatibility confirmation": "契约兼容性确认",
    "single-repo rollback evidence": "单仓库回滚证据",
    "repo tests and acceptance evidence": "仓库测试和验收证据",
    "minimal; no new remote call by default": "影响极小；默认不新增远程调用",
    "Provider contract must change": "生产方契约必须变更",
    "Multiple consumers need the same behavior": "多个消费方需要相同行为",
    "Single owner repo would duplicate source-of-truth logic": "单一责任仓库会重复实现事实源逻辑",
    "Requires contract freeze, provider-consumer integration tests, and ordered merge/release.": "需要契约冻结、生产方/消费方集成测试，以及有序合并和发布。",
    "Deploy provider before consumers or use backward-compatible dual-read/dual-write strategy.": "先发布生产方再发布消费方，或采用向后兼容的双读/双写策略。",
    "better shared ownership when multiple consumers are affected": "多个消费方受影响时共享责任更清晰",
    "requires integration evidence before release": "发布前需要集成证据",
    "cross_repo_execution_graph": "跨仓执行图",
    "contract freeze point": "契约冻结点",
    "consumer compatibility test": "消费方兼容性测试",
    "depends on new calls and payload shape; review latency and serialization cost": "取决于新增调用和报文结构；需评估延迟和序列化成本",
    "data correctness is explicit": "数据正确性更明确",
    "rollback risk is reviewed before implementation": "实现前完成回滚风险评审",
    "ownership_clarity": "责任清晰度",
    "release_coordination": "发布协同",
    "contract_risk": "契约风险",
    "A1 starts from known owner boundary.": "A1 从已知责任边界出发。",
    "A1 avoids multi-repo ordered release.": "A1 避免多仓有序发布。",
    "Preserving existing contracts is safer by default.": "默认保持现有契约更稳妥。",
    "A1 rollback is a single repo revert.": "A1 回滚是单仓库 revert。",
    "A1 回滚是单仓库 revert。": "A1 回滚是单仓库回滚。",
    "A2 is stronger when repeated shared behavior is expected.": "当预期存在重复共享行为时，A2 更强。",
    "Weighted qualitative score; higher is preferred unless repo analysis proves contract change is required.": "加权定性评分；除非仓库分析证明必须变更契约，否则分数越高越优先。",
    "Default to smallest owner-boundary change because it scores better on ownership clarity, release coordination, contract risk, and rollback.": "默认选择最小责任边界变更，因为它在责任清晰度、发布协同、契约风险和回滚方面得分更高。",
    "Less future extensibility than a shared contract change": "未来扩展性弱于共享契约变更",
    "Cross-repository contract work adds compatibility, integration, and release-order risk unless the existing owner boundary cannot satisfy the requirement.": "除非现有责任边界无法满足需求，否则跨仓契约变更会增加兼容性、集成和发布顺序风险。",
    "Owner-module implementation for ": "在现有责任模块内完成：",
    "Contract-aware service/API adjustment": "通过既有接口/服务契约承接业务规则",
    "Data-model explicit handling": "先明确字段、默认值和历史数据口径",
    "Single-owner architecture in ": "以单一责任仓库推进：",
    "Provider-consumer contract architecture": "以生产方/消费方契约为架构边界推进",
    "Data-first release architecture": "以数据口径和发布顺序为优先边界推进",
    "User-visible behavior matches:": "验证：",
    "regression coverage for": "回归验证：",
    "cross-component integration remains compatible": "跨组件/跨仓集成契约保持兼容",
    "browser acceptance for changed UI": "浏览器验收：变更页面交互和展示符合预期",
    "integration test evidence": "集成测试证据",
    "regression evidence": "回归测试证据",
    "acceptance_fit": "验收适配度",
    "contract_safety": "契约安全性",
    "data_correctness": "数据正确性",
    "testability": "测试可证明性",
    "rollback_control": "回滚可控性",
    "ownership_clarity": "责任清晰度",
    "data_safety": "数据安全性",
    "bind allowed_files to selected entrypoints": "将允许修改文件限制在已选责任入口内",
    "map every acceptance criterion to evidence": "每条验收标准都绑定到证据",
    "re-run design review if inspection finds a different owner": "如果代码检查发现责任入口不同，重新进行设计评审",
    "Run mapped tests for": "运行已映射测试：",
    "and acceptance evidence": "并采集验收证据",
    "bounded to existing flow unless data/API slice adds extra queries or calls": "默认限制在现有流程内；若数据/API 切片新增查询或调用则需单独评估",
    "changes in": "变更：",
    "and redeploy previous artifact": "并重新部署上一版本制品",
    "single owner module rollout": "单一责任模块发布",
    "contract compatibility matrix": "契约兼容性矩阵",
    "old-consumer regression evidence": "旧消费方回归证据",
    "ordered rollback if provider and consumer both change": "生产方和消费方都变更时按依赖顺序回滚",
    "contract, integration, and regression evidence": "契约、集成和回归证据",
    "review route/query latency and payload growth": "评估路由/查询延迟和报文增长",
    "rollback consumers before provider if a contract change is deployed": "如果发布了契约变更，先回滚消费方再回滚生产方",
    "may require provider/consumer coordination": "可能需要生产方/消费方协同",
    "migration plan or explicit no-migration proof": "迁移方案或无需迁移证明",
    "old-data regression evidence": "历史数据回归证据",
    "rollback data-risk review": "数据回滚风险评审",
    "data compatibility and regression evidence": "数据兼容性和回归证据",
    "review added query/filter/index cost": "评估新增查询、筛选或索引成本",
    "may require data/config release step": "可能需要数据或配置发布步骤",
    "permission negative evidence": "权限反向证据",
    "role/data-scope fixture": "角色/数据范围测试数据",
    "server-side authorization confirmation": "服务端鉴权确认",
    "permission positive and negative evidence": "权限正向和反向证据",
    "no material performance impact unless permission lookup changes": "除非权限查询路径变化，否则无显著性能影响",
    "contract compatibility evidence": "契约兼容性证据",
    "browser acceptance evidence": "浏览器验收证据",
    "integration regression evidence": "集成回归证据",
    "contract, browser, and integration evidence": "契约、浏览器和集成证据",
    "review query/filter and render cost together": "同时评估查询/筛选和渲染成本",
    "rollback frontend first, then backend contract change if compatibility fails": "兼容失败时先回滚前端，再回滚后端契约变更",
    "may require backend-compatible release before frontend rollout": "可能需要后端兼容发布后再发布前端",
    "subdomain traceability matrix": "子域追踪矩阵",
    "per-domain acceptance evidence": "子域级验收证据",
    "per-domain rollback note": "子域级回滚说明",
    "per-subdomain functional and regression evidence": "子域级功能和回归证据",
    "review each subdomain independently": "逐个子域评估",
    "can be staged by subdomain when release policy allows": "发布策略允许时可按子域分阶段发布",
    "owner repo tests plus mapped acceptance evidence": "责任仓库测试和已映射验收证据",
    "allowed_files bound to module topology": "允许修改文件绑定到模块拓扑",
    "acceptance evidence per business slice": "每个业务切片的验收证据",
    "limited to owner repo unless technical option adds remote calls or data migration": "默认限制在责任仓库内；若技术方案新增远程调用或数据迁移则需单独评估",
    "consumer compatibility evidence": "消费方兼容性证据",
    "contract, provider, consumer, and regression evidence": "契约、生产方、消费方和回归证据",
    "review payload/query/latency impact across the boundary": "评估跨边界报文、查询和延迟影响",
    "rollback consumers before provider if compatibility fails": "兼容失败时先回滚消费方再回滚生产方",
    "migration strategy": "迁移策略",
    "data compatibility and regression evidence": "数据兼容性和回归证据",
    "role fixture review": "角色测试数据评审",
    "server authorization confirmation": "服务端鉴权确认",
    "permission positive/negative and regression evidence": "权限正反向和回归证据",
    "review permission lookup cost only if authorization path changes": "仅在鉴权路径变化时评估权限查询成本",
    "subdomain delivery plan": "子域交付计划",
    "staged rollback note": "分阶段回滚说明",
    "per-domain acceptance and regression evidence": "子域级验收和回归证据",
    "review each subdomain's query/render cost separately": "分别评估每个子域的查询和渲染成本",
    "dual contract tests": "双契约测试",
    "gray switch rollback": "灰度开关回滚",
    "old consumer evidence": "旧消费方证据",
    "old/new contract and gray release evidence": "新旧契约和灰度发布证据",
    "review dual-read or compatibility branch cost": "评估双读或兼容分支成本",
    "turn off gray switch first, then rollback producer/consumer if needed": "先关闭灰度开关，必要时再回滚生产方/消费方",
    "Scores are weighted from requirement-specific criteria; selected option should match the highest total unless the design records an explicit exception.": "评分按需求特定维度加权；除非设计明确记录例外，通常选择总分最高方案。",
    "Architecture scores are weighted from ownership, contract, release, observability, and rollback evidence.": "架构评分按责任归属、契约、发布、可观测性和回滚证据加权。",
    "confirm fields touched by this slice": "确认该切片涉及的字段",
    "no field change confirmed": "未确认字段变更",
    "confirm existing route or contract for this slice": "确认该切片对应的既有路由或契约",
    "no API change confirmed": "未确认 API 变更",
    "preserve existing permission boundary": "保持现有权限边界",
    "preserve existing permission; add negative case if role/data scope changes": "保持现有权限边界；如角色或数据范围变化则补充反向用例",
    "preserve existing 权限测试; add negative case if role/data scope changes": "保持现有权限边界；如角色或数据范围变化则补充反向用例",
    "Business objective is missing; design may optimize the wrong outcome.": "缺少业务目标，设计可能优化到错误结果。",
    "Acceptance is inferred rather than explicitly provided.": "验收标准为推断结果，需确认是否明确来自需求。",
    "High-impact requirement should declare explicit delivery or product risks.": "高影响需求应明确交付或产品风险。",
    "API impact should state backward compatibility or consumer migration constraints.": "API 影响应说明向后兼容或消费方迁移约束。",
    "revise design or collect evidence": "修订设计或补充证据",
    "review query/filter/index changes": "评估查询、筛选和索引变化",
    "rollback code first and follow data rollback/migration policy": "先回滚代码，再按数据回滚或迁移策略处理",
    "rollback UI visibility and authorization changes together": "同时回滚 UI 可见性和鉴权变更",
    "per-domain evidence": "子域级证据",
    "rollback affected subdomain first when coupling allows; otherwise revert full requirement branch": "耦合允许时优先回滚受影响子域；否则回滚整个需求分支",
    "rollback affected subdomain first when coupling allows; otherwise 回滚 full requirement branch": "耦合允许时优先回滚受影响子域；否则回滚整个需求分支",
    "none": "无",
    "provider/consumer owners": "生产方/消费方负责人",
    "consumer-repo": "消费方仓库",
    "strategy_summary": "测试策略摘要",
    "Validate acceptance criteria for": "验证验收标准：",
    "detailed cases belong in test_design.json.": "详细用例见 test_design.json。",
    "fixture_or_factory": "测试夹具/工厂方法",
    "upload_fixture_file": "上传合成文件",
    "sql_seed": "SQL 种子数据",
    "synthetic fixture": "合成测试数据",
    "synthetic file": "合成测试文件",
    "authorized-user": "授权用户",
    "restricted-user": "受限用户",
    "UI:": "页面路径：",
    "API:": "接口路径：",
    "DATA:": "数据路径：",
    "PERMISSION:": "权限路径：",
    "INTEGRATION:": "集成路径：",
    "BUSINESS:": "业务路径：",
    " -> ": " -> ",
}


def translate_default_zh_phrase(value: str) -> str:
    rendered = value
    for source, target in sorted(ZH_DEFAULT_PHRASES.items(), key=lambda item: len(item[0]), reverse=True):
        rendered = rendered.replace(source, target)
    return rendered


def protect_code_tokens(value: str) -> tuple[str, dict[str, str]]:
    placeholders: dict[str, str] = {}

    def replace_code(match: re.Match[str]) -> str:
        key = f"__CODE_{len(placeholders)}__"
        placeholders[key] = match.group(0)
        return key

    pattern = r"`[^`]+`|(?:npm|pnpm|yarn)\s+run\s+[A-Za-z0-9:_./-]+|mvn\s+[A-Za-z0-9_./:=\-\s]+?(?=$|[；;,，。])"
    return re.sub(pattern, replace_code, str(value or "")), placeholders


def restore_code_tokens(value: str, placeholders: dict[str, str]) -> str:
    rendered = value
    for key, original in placeholders.items():
        rendered = rendered.replace(key, original)
    return rendered


def zh_text_preserving_code(value: str, default: str = "待补充") -> str:
    protected, placeholders = protect_code_tokens(str(value or ""))
    rendered = zh_text(protected, default)
    return restore_code_tokens(rendered, placeholders)


def zh_text(value: Any, default: str = "待补充") -> str:
    if value in (None, "", [], {}):
        return default
    if isinstance(value, bool):
        return "是" if value else "否"
    rendered = text(value, default)
    rendered, placeholders = protect_code_tokens(rendered)
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
        "regression": "回归测试",
        "frontend": "前端验收",
        "integration": "集成测试",
        "api_test": "接口测试",
        "fixture_or_factory": "测试夹具/工厂方法",
        "upload_fixture_file": "上传合成文件",
        "sql_seed": "SQL 种子数据",
        "synthetic fixture": "合成测试数据",
        "synthetic file": "合成测试文件",
        "synthetic": "合成数据",
        "authorized-user": "授权用户",
        "restricted-user": "受限用户",
        "UI:": "页面路径：",
        "API:": "接口路径：",
        "DATA:": "数据路径：",
        "PERMISSION:": "权限路径：",
        "INTEGRATION:": "集成路径：",
        "BUSINESS:": "业务路径：",
        "positive": "正向用例",
        "negative": "反向用例",
        "modify": "修改",
        "false": "否",
        "true": "是",
        "TBD": default,
        "待确认目标模块": "需结合代码核对的责任模块",
        "target module to be confirmed": "需结合代码核对的责任模块",
        "before implementation": "实施前",
        "primary code entrypoint is generic or weakly matched; inspect project manually before implementation": "主代码入口匹配较弱，实施前需人工核对项目代码",
        "inspect matched feature modules and update design before implementation": "实施前核对匹配到的功能模块并更新设计",
        "write through": "通过",
        "only if this slice changes state": "仅在该子需求改变状态时写入",
        "unless this slice changes schema/data backfill": "除非该子需求改变表结构或数据回填",
        "code rollback plus schema/data rollback plan if migration is applied": "如执行迁移，需配套代码回滚和结构/数据回滚方案",
        "code rollback plus data compatibility/compensation plan": "代码回滚，并配套数据兼容或补偿方案",
        "code rollback plus data 兼容性/compensation plan": "代码回滚，并配套数据兼容或补偿方案",
        "no-migration evidence": "无迁移证据",
        "owns code changes": "负责代码变更",
    }
    rendered = translate_default_zh_phrase(rendered)
    for source, target in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        rendered = rendered.replace(source, target)
    return restore_code_tokens(DOCS_I18N.translate_text(rendered, "zh"), placeholders)


def zh_inline_list(value: Any, default: str = "待补充") -> str:
    values = as_list(value)
    if not values:
        return default
    rendered: list[str] = []
    for item in values:
        if isinstance(item, dict):
            option = item.get("option_id") or item.get("id") or item.get("name")
            reason = item.get("reason") or item.get("summary") or item.get("message")
            if option and reason:
                rendered.append(f"`{text(option)}`：{zh_text(reason)}")
            else:
                rendered.append(zh_text(item))
        else:
            rendered.append(zh_text(item))
    return "；".join(item for item in rendered if item) or default


def zh_option_name(item: dict[str, Any], option_kind: str) -> str:
    option_id = text(item.get("option_id"), "")
    name = str(item.get("name") or "")
    if name.startswith("Owner-module implementation for "):
        return f"在现有责任模块内完成：{name.removeprefix('Owner-module implementation for ')}"
    if name == "Contract-aware service/API adjustment":
        return "通过既有接口/服务契约承接业务规则"
    if name == "Data-model explicit handling":
        return "先明确字段、默认值和历史数据口径"
    if name.startswith("Single-owner architecture in "):
        return f"以 `{name.removeprefix('Single-owner architecture in ')}` 为单一责任边界推进"
    if name == "Provider-consumer contract architecture":
        return "以生产方/消费方契约为架构边界推进"
    if name == "Data-first release architecture":
        return "以数据口径和发布顺序为优先边界推进"
    if option_kind == "technical" and option_id == "T1" and name:
        return zh_text(name)
    if option_kind == "architecture" and option_id == "A1" and name:
        return zh_text(name)
    return zh_text(name)


def zh_decision_reason(selected: dict[str, Any], options: list[Any], option_kind: str) -> str:
    selected_id = text(selected.get("selected_option_id"), "")
    raw = str(selected.get("selection_reason") or "")
    selected_option = next((item for item in options if isinstance(item, dict) and item.get("option_id") == selected_id), {})
    selected_name = zh_option_name(selected_option, option_kind) if isinstance(selected_option, dict) else selected_id
    if raw.startswith("Weighted comparison selects"):
        owner = raw.split(" for `", 1)[1].split("`", 1)[0] if " for `" in raw else ""
        summary = raw.rsplit(" for: ", 1)[-1].rstrip(".") if " for: " in raw else ""
        return (
            f"选择 {selected_id}（{selected_name}），因为当前证据显示 `{owner or '责任入口'}` 是最清晰的实现边界，"
            f"「{summary or '本需求'}」可以在现有模块内闭环，不需要先扩大接口、数据模型或跨仓契约。"
            "该选择测试路径最短，回滚也最容易控制。"
        )
    if raw.startswith("Weighted architecture comparison selects"):
        owner = raw.split(" for `", 1)[1].split("`", 1)[0] if " for `" in raw else ""
        summary = raw.rsplit(" for: ", 1)[-1].rstrip(".") if " for: " in raw else ""
        return (
            f"选择 {selected_id}（{selected_name}），因为当前需求「{summary or '本需求'}」的主要责任可以收敛在 `{owner or '责任仓库'}`，"
            "暂未看到必须先扩大为跨仓契约或数据优先发布的证据。该架构发布顺序更短，回滚责任更清晰。"
        )
    return zh_text(raw)


def zh_rejected_reason(value: Any, options: list[Any]) -> str:
    if isinstance(value, dict):
        option_id = text(value.get("option_id"), "")
        raw = str(value.get("reason") or "")
        option = next((item for item in options if isinstance(item, dict) and item.get("option_id") == option_id), {})
        name = zh_option_name(option, "technical") if isinstance(option, dict) else option_id
        if "Rejected for this pass" in raw:
            if option_id in {"T2", "A2"}:
                return f"`{option_id}`：暂不选择{name}，因为当前证据还不足以证明必须扩大到接口/契约或生产方/消费方协同；若代码检查发现契约字段、响应语义或多个消费方必须同步变化，再切换到该方案。"
            if option_id in {"T3", "A3"}:
                return f"`{option_id}`：暂不选择{name}，因为当前证据还不足以证明数据口径、历史数据或迁移/回滚风险是主导约束；若实现前发现这些因素会影响验收，再切换到该方案。"
            return f"`{option_id}`：暂不选择{name}，因为当前证据下交付边界、测试或回滚成本高于选中方案。"
        if option_id and raw:
            return f"`{option_id}`：{zh_text(raw)}"
    return zh_text(value)


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
        return "；".join(zh_text(value) for value in values) if language == "zh" else "; ".join(values)
    return zh_text(item, "待补充") if language == "zh" else text(item)


def clean_acceptance_text(value: Any, language: str = "en") -> str:
    rendered = text(value, "acceptance")
    for prefix in ["User-visible behavior matches:", "user-visible behavior matches:"]:
        if rendered.startswith(prefix):
            rendered = rendered[len(prefix):].strip()
    if language == "zh" and rendered.startswith("需求："):
        rendered = rendered[len("需求："):].strip()
    return zh_text_preserving_code(rendered) if language == "zh" else rendered


def clean_test_title(value: Any, language: str = "en") -> str:
    rendered = clean_acceptance_text(value, language)
    if language == "zh":
        rendered = rendered.replace("验证： 验证：", "验证：").replace("验证：验证：", "验证：")
        rendered = rendered.replace("回归验证： 验证：", "回归验证：").replace("回归验证：验证：", "回归验证：")
        rendered = rendered.replace("验证： ", "验证：").replace("回归验证： ", "回归验证：")
        rendered = rendered.replace("未授权角色不能访问变更后的行为", "未授权角色不能访问或触发本次变更行为")
    return rendered.strip()


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
            lines.append(f"`{text(item.get('id'))}` {clean_acceptance_text(item.get('criteria'), 'zh')}（类型：{zh_text(item.get('type'), '用例')}；证据：{evidence}）")
        else:
            lines.append(f"`{text(item.get('id'))}` {clean_acceptance_text(item.get('criteria'), 'en')} ({text(item.get('type'), 'case')}; evidence: {evidence})")
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
        lines.append(f'  {ac_id}["{ac_id}: {clean_acceptance_text(ac.get("criteria"), language)[:60]}"]')
    first_req = text(reqs[0].get("id"), "REQ")
    for ac in acs[:8]:
        lines.append(f'  {first_req} --> {text(ac.get("id"), "AC")}')
    lines.append("```")
    return "\n".join(lines)


def mermaid_flow_label(value: Any, language: str = "en", limit: int = 90) -> str:
    rendered = human_value(value, language, "")
    cleaned = (
        rendered.replace("\n", " ")
        .replace('"', "'")
        .replace("；", "，")
        .replace(";", ",")
        .replace("|", "/")
    )
    return cleaned[: max(limit - 3, 1)] + "..." if len(cleaned) > limit else cleaned


def render_process_mermaid(technical: dict[str, Any], language: str = "en") -> str:
    flows = [item for item in as_list(technical.get("process_flow")) if isinstance(item, dict)]
    if not flows:
        return "缺少业务流程，无法生成流程图。" if language == "zh" else "Process flow data is missing, so the flow diagram cannot be generated."
    start_label = "开始" if language == "zh" else "Start"
    success_label = "成功" if language == "zh" else "Success"
    failure_label = "异常/失败" if language == "zh" else "Exception/Failure"
    success_state_label = "成功状态" if language == "zh" else "success state"
    failure_state_label = "失败状态" if language == "zh" else "failure state"
    lines = [
        "```mermaid",
        "flowchart TD",
        "  classDef startEnd fill:#ecfdf5,stroke:#16a34a,color:#14532d,stroke-width:1px;",
        "  classDef action fill:#eff6ff,stroke:#2563eb,color:#172554,stroke-width:1px;",
        "  classDef failure fill:#fff7ed,stroke:#f97316,color:#7c2d12,stroke-width:1px;",
    ]
    counter = 0
    for flow_index, flow in enumerate(flows[:4], start=1):
        flow_name = human_value(flow.get("flow_name"), language, f"Flow {flow_index}")
        actors = ", ".join(human_value(actor, language, "") for actor in as_list(flow.get("actors")) if human_value(actor, language, ""))
        success_state = human_value(flow.get("success_end_state"), language, success_label)
        failure_states = ", ".join(human_value(item, language, "") for item in as_list(flow.get("failure_end_states")) if human_value(item, language, "")) or failure_label
        subgraph = mermaid_flow_label(f"{flow_index}. {flow_name}", language, 40)
        lines.append(f'  subgraph F{flow_index}["{subgraph}"]')
        lines.append("    direction LR")
        lines.append(f'    F{flow_index}_START((" {start_label} ")):::startEnd')
        previous = f"F{flow_index}_START"
        for step in as_list(flow.get("steps"))[:8]:
            if not isinstance(step, dict):
                continue
            counter += 1
            node = f"F{flow_index}_S{counter}"
            actor = human_value(step.get("actor"), language, actors or ("参与方" if language == "zh" else "actor"))
            action = human_value(step.get("action"), language, "action")
            output = human_value(step.get("output"), language, "")
            action_summary = mermaid_flow_label(action, language, 34)
            output_summary = mermaid_flow_label(output, language, 24)
            output_suffix = f"<br/>=> {output_summary}" if output_summary and "达到该子需求" not in output_summary else ""
            label = f"{mermaid_flow_label(actor, language, 16)}<br/>{action_summary}{output_suffix}"
            lines.append(f'    {node}["{label}"]:::action')
            if previous:
                lines.append(f"    {previous} --> {node}")
            previous = node
        ok_node = f"F{flow_index}_OK"
        fail_node = f"F{flow_index}_FAIL"
        lines.append(f'    {ok_node}(("{mermaid_flow_label(success_label + ": " + success_state, language, 42)}")):::startEnd')
        lines.append(f'    {fail_node}["{mermaid_flow_label(failure_label + ": " + failure_states, language, 42)}"]:::failure')
        if previous:
            lines.append(f"    {previous} --> {ok_node}")
            lines.append(f"    {previous} -.-> {fail_node}")
        lines.append("  end")
    lines.append("```")
    return "\n".join(lines) if counter else ("缺少流程步骤，无法生成流程图。" if language == "zh" else "Process steps are missing, so the flow diagram cannot be generated.")


def render_architecture_mermaid(
    architecture: dict[str, Any],
    language: str = "en",
    runtime_evidence: dict[str, Any] | None = None,
) -> str:
    runtime_evidence = runtime_evidence if isinstance(runtime_evidence, dict) else {}
    interactions = [item for item in as_list(runtime_evidence.get("interactions")) if isinstance(item, dict)]
    if interactions:
        frontend = runtime_evidence.get("frontend") if isinstance(runtime_evidence.get("frontend"), dict) else {}
        backend = runtime_evidence.get("backend") if isinstance(runtime_evidence.get("backend"), dict) else {}
        downstreams = [item for item in as_list(runtime_evidence.get("downstreams")) if isinstance(item, dict)]
        downstream = runtime_evidence.get("downstream") if isinstance(runtime_evidence.get("downstream"), dict) else {}
        if downstream and not downstreams:
            downstreams = [downstream]
        frontend_label = "<br/>".join(
            item
            for item in [
                human_value(frontend.get("repo"), language, ""),
                human_value(frontend.get("page"), language, ""),
                human_value(frontend.get("route"), language, ""),
            ]
            if item
        ) or ("前端" if language == "zh" else "Frontend")
        backend_label = "<br/>".join(
            item
            for item in [
                human_value(backend.get("repo"), language, ""),
                human_value(backend.get("service") or backend.get("controller"), language, ""),
            ]
            if item
        ) or ("后端" if language == "zh" else "Backend")
        lines = [
            "```mermaid",
            "flowchart LR",
            "  classDef frontend fill:#eff6ff,stroke:#2563eb,color:#172554,stroke-width:1px;",
            "  classDef backend fill:#ecfdf5,stroke:#16a34a,color:#14532d,stroke-width:1px;",
            "  classDef api fill:#f8fafc,stroke:#64748b,color:#0f172a,stroke-width:1px;",
            "  classDef downstream fill:#fff7ed,stroke:#f97316,color:#7c2d12,stroke-width:1px;",
            f'  F["{mermaid_flow_label(frontend_label, language, 84)}"]:::frontend',
            f'  B["{mermaid_flow_label(backend_label, language, 84)}"]:::backend',
        ]
        api_seen: list[str] = []
        for item in interactions[:10]:
            method = human_value(item.get("method"), language, "")
            api = human_value(item.get("api"), language, "")
            contract = " ".join(part for part in [method, api] if part)
            if contract and contract not in api_seen:
                api_seen.append(contract)
        for index, api in enumerate(api_seen[:10], start=1):
            api_id = f"A{index}"
            lines.append(f'  {api_id}["{mermaid_flow_label(api, language, 180)}"]:::api')
            lines.append(f"  F -->|{'调用' if language == 'zh' else 'calls'}| {api_id}")
            lines.append(f"  {api_id} -->|{'承接' if language == 'zh' else 'handled by'}| B")
        downstream_aliases: dict[str, str] = {}
        for index, item in enumerate(downstreams[:8], start=1):
            alias = f"DS{index}"
            label = "<br/>".join(
                part
                for part in [
                    human_value(item.get("name") or item.get("service") or item.get("repo"), language, ""),
                    human_value(item.get("repo"), language, ""),
                ]
                if part
            )
            if not label:
                continue
            lines.append(f'  {alias}["{mermaid_flow_label(label, language, 72)}"]:::downstream')
            for key in [item.get("key"), item.get("id"), item.get("name"), item.get("service"), item.get("repo")]:
                rendered = human_value(key, language, "")
                if rendered:
                    downstream_aliases[rendered] = alias
        for item in interactions[:10]:
            for call in [call for call in as_list(item.get("calls") or item.get("downstream_calls") or item.get("backend_calls")) if isinstance(call, dict)]:
                source = human_value(call.get("from") or call.get("source"), language, "")
                target = human_value(call.get("to") or call.get("target"), language, "")
                source_alias = "B" if source in {"", "backend", "后端", human_value(backend.get("repo"), language, ""), human_value(backend.get("service"), language, "")} else downstream_aliases.get(source, "")
                target_alias = "B" if target in {"backend", "后端", human_value(backend.get("repo"), language, ""), human_value(backend.get("service"), language, "")} else downstream_aliases.get(target, "")
                if source_alias and target_alias:
                    lines.append(f"  {source_alias} -->|{mermaid_flow_label(human_value(call.get('action') or call.get('request'), language, '调用'), language, 36)}| {target_alias}")
        lines.append("```")
        return "\n".join(lines)
    deps = [item for item in as_list(architecture.get("cross_repo_dependency_graph")) if isinstance(item, dict)]
    deploys = [item for item in as_list(architecture.get("deployment_impact_matrix")) if isinstance(item, dict)]
    rollbacks = [item for item in as_list(architecture.get("rollback_strategy")) if isinstance(item, dict)]
    if not deps and not deploys:
        return "缺少跨仓或模块依赖信息，无法生成关系图。" if language == "zh" else "Dependency graph data is missing, so the architecture diagram cannot be generated."
    repo_names = []
    for item in deps:
        for key in ["from", "to"]:
            repo = human_value(item.get(key), language, "")
            if repo and repo not in repo_names:
                repo_names.append(repo)
    for item in deploys:
        repo = human_value(item.get("repo"), language, "")
        if repo and repo not in repo_names:
            repo_names.append(repo)
    rollback_repos = {human_value(item.get("repo"), language, "") for item in rollbacks}

    def node_id(prefix: str, value: str, index: int) -> str:
        safe = re.sub(r"[^A-Za-z0-9_]", "_", value)[:28]
        return f"{prefix}{index}_{safe or 'node'}"

    repo_ids = {repo: node_id("R", repo, index) for index, repo in enumerate(repo_names, start=1)}
    lines = [
        "```mermaid",
        "flowchart LR",
        "  classDef owner fill:#eff6ff,stroke:#2563eb,color:#172554,stroke-width:1px;",
        "  classDef contract fill:#f8fafc,stroke:#64748b,color:#0f172a,stroke-width:1px;",
        "  classDef deploy fill:#ecfdf5,stroke:#16a34a,color:#14532d,stroke-width:1px;",
        "  classDef risk fill:#fff7ed,stroke:#f97316,color:#7c2d12,stroke-width:1px;",
    ]
    boundary = "变更仓库/工程边界" if language == "zh" else "Changed repository / engineering boundary"
    lines.append(f'  subgraph B["{boundary}"]')
    for repo in repo_names[:10]:
        rollback_note = "，可回滚" if language == "zh" and repo in rollback_repos else (", rollback known" if repo in rollback_repos else "")
        lines.append(f'    {repo_ids[repo]}["{mermaid_flow_label(repo + rollback_note, language, 36)}"]:::owner')
    lines.append("  end")
    for index, item in enumerate(deps[:10], start=1):
        source = human_value(item.get("from"), language, "")
        target = human_value(item.get("to"), language, "")
        contract = human_value(item.get("contract"), language, "contract")
        change = human_value(item.get("change"), language, "")
        source_id = repo_ids.get(source)
        target_id = repo_ids.get(target)
        if not source_id or not target_id:
            continue
        contract_id = f"C{index}"
        contract_label = mermaid_flow_label(contract, language, 42)
        change_label = mermaid_flow_label(change or ("契约/接口确认" if language == "zh" else "contract check"), language, 36)
        lines.append(f'  {contract_id}["{contract_label}"]:::contract')
        if source == target:
            lines.append(f"  {source_id} -->|内部契约| {contract_id}")
            impact_label = "影响确认" if language == "zh" else "impact check"
            lines.append(f"  {contract_id} -->|{impact_label}| {target_id}")
        else:
            lines.append(f"  {source_id} -->|提供/调用| {contract_id}")
            lines.append(f"  {contract_id} -->|{change_label}| {target_id}")
    for index, item in enumerate(deploys[:8], start=1):
        repo = human_value(item.get("repo"), language, "")
        repo_id = repo_ids.get(repo)
        if not repo_id:
            continue
        artifact = mermaid_flow_label(human_value(item.get("artifact"), language, "artifact"), language, 34)
        order = human_value(item.get("order"), language, str(index))
        deploy_id = f"D{index}"
        deploy_label = f"{'发布' if language == 'zh' else 'deploy'} #{order}<br/>{artifact}"
        lines.append(f'  {deploy_id}["{deploy_label}"]:::deploy')
        lines.append(f"  {repo_id} --> {deploy_id}")
    lines.append("```")
    return "\n".join(lines)


def render_runtime_sequence_evidence(runtime_evidence: dict[str, Any], language: str = "en") -> str:
    if not isinstance(runtime_evidence, dict) or not runtime_evidence:
        return ""
    actor = human_value(runtime_evidence.get("actor"), language, "Actor" if language != "zh" else "业务操作人")
    frontend = runtime_evidence.get("frontend") if isinstance(runtime_evidence.get("frontend"), dict) else {}
    backend = runtime_evidence.get("backend") if isinstance(runtime_evidence.get("backend"), dict) else {}
    downstream = runtime_evidence.get("downstream") if isinstance(runtime_evidence.get("downstream"), dict) else {}
    interactions = [item for item in as_list(runtime_evidence.get("interactions")) if isinstance(item, dict)]
    if not interactions:
        return ""

    frontend_repo = human_value(frontend.get("repo"), language, "")
    frontend_page = human_value(frontend.get("page"), language, "")
    frontend_route = human_value(frontend.get("route"), language, "")
    backend_repo = human_value(backend.get("repo"), language, "")
    backend_service = human_value(backend.get("service"), language, "")
    backend_controller = human_value(backend.get("controller"), language, "")
    downstream_name = human_value(downstream.get("name"), language, "")
    models = [item for item in as_list(runtime_evidence.get("data_models")) if isinstance(item, dict)]
    table_names = [human_value(item.get("table"), language, "") for item in models if human_value(item.get("table"), language, "")]
    downstreams = [item for item in as_list(runtime_evidence.get("downstreams")) if isinstance(item, dict)]
    if downstream and not downstreams:
        downstreams = [downstream]

    frontend_bits = [item for item in [frontend_page, frontend_route, frontend_repo] if item]
    backend_bits = [item for item in [backend_service or backend_controller, backend_repo] if item]
    frontend_label = "<br/>".join(frontend_bits[:3]) or ("浏览器/前端" if language == "zh" else "Browser / frontend")
    backend_label = "<br/>".join(backend_bits[:2]) or ("后端服务需确认" if language == "zh" else "Backend service TBD")
    downstream_label = downstream_name or human_value(downstream.get("repo"), language, "")
    downstream_aliases: dict[str, str] = {}
    downstream_participants: list[tuple[str, str]] = []
    for index, item in enumerate(downstreams[:8], start=1):
        key = human_value(item.get("key") or item.get("id") or item.get("name") or item.get("repo"), language, "")
        label_parts = [
            human_value(item.get("name") or item.get("service") or item.get("repo"), language, ""),
            human_value(item.get("repo"), language, ""),
        ]
        label = "<br/>".join(part for part in label_parts if part)
        if not label:
            continue
        alias = f"D{index}"
        if key:
            downstream_aliases[key] = alias
        repo = human_value(item.get("repo"), language, "")
        name = human_value(item.get("name"), language, "")
        service = human_value(item.get("service"), language, "")
        for alternate in [repo, name, service]:
            if alternate:
                downstream_aliases.setdefault(alternate, alias)
        downstream_participants.append((alias, label))

    lines = ["```mermaid", "sequenceDiagram", "  autonumber"]
    lines.append(f"  actor A as {mermaid_flow_label(actor, language, 32)}")
    lines.append(f"  participant B as {mermaid_flow_label(frontend_label, language, 96)}")
    lines.append(f"  participant C as {mermaid_flow_label(backend_label, language, 96)}")
    if table_names:
        db_label = ("数据库表<br/>" if language == "zh" else "Database tables<br/>") + "<br/>".join(table_names[:4])
        lines.append(f"  participant DB as {mermaid_flow_label(db_label, language, 120)}")
    if downstream_participants:
        for alias, label in downstream_participants:
            lines.append(f"  participant {alias} as {mermaid_flow_label(label, language, 72)}")
    elif downstream_label:
        lines.append(f"  participant D as {mermaid_flow_label(downstream_label, language, 40)}")

    failure_label = "异常/校验失败" if language == "zh" else "exception / validation failure"
    success_note = "页面刷新或提示操作结果" if language == "zh" else "refresh UI or show result"
    for index, item in enumerate(interactions[:8], start=1):
        scenario = human_value(item.get("scenario") or item.get("requirement_breakdown_id"), language, f"Step {index}")
        trigger = human_value(item.get("trigger"), language, "")
        method = human_value(item.get("method"), language, "")
        api = human_value(item.get("api"), language, "")
        request = human_value(item.get("request"), language, "")
        response = human_value(item.get("response"), language, "")
        backend_action = human_value(item.get("backend_action"), language, "")
        downstream_action = human_value(item.get("downstream_action"), language, "")
        calls = [call for call in as_list(item.get("calls") or item.get("downstream_calls") or item.get("backend_calls")) if isinstance(call, dict)]
        data_ops = [
            human_value(value, language, "")
            for value in as_list(item.get("data_operations") or item.get("data_impact") or item.get("persistence"))
            if human_value(value, language, "")
        ]
        failure = human_value(item.get("failure"), language, "")

        trigger_label = " / ".join(part for part in [scenario, trigger] if part)
        api_label = " ".join(part for part in [method, api] if part)
        if request:
            api_label = f"{api_label}，{request}" if api_label else request
        response_label = response or success_note
        lines.append(f"  A->>B: {mermaid_flow_label(trigger_label, language, 120)}")
        lines.append(f"  B->>C: {mermaid_flow_label(api_label or ('请求后端接口' if language == 'zh' else 'request backend API'), language, 360)}")
        if backend_action:
            lines.append(f"  activate C")
            lines.append(f"  Note over C: {mermaid_flow_label(backend_action, language, 140)}")
        if calls:
            for call in calls[:8]:
                source_key = human_value(call.get("from") or call.get("source"), language, "")
                target_key = human_value(call.get("to") or call.get("target"), language, "")
                source_alias = downstream_aliases.get(source_key, "C" if source_key in {"", "backend", "后端", backend_repo, backend_service, backend_controller} else source_key)
                target_alias = downstream_aliases.get(target_key, "C" if target_key in {"backend", "后端", backend_repo, backend_service, backend_controller} else target_key)
                if not re.match(r"^[A-Za-z][A-Za-z0-9_]*$", source_alias or "") or not re.match(r"^[A-Za-z][A-Za-z0-9_]*$", target_alias or ""):
                    continue
                action = human_value(call.get("action") or call.get("request"), language, "")
                call_response = human_value(call.get("response"), language, "")
                mode = human_value(call.get("mode"), language, "")
                suffix = f" [{mode}]" if mode else ""
                lines.append(f"  {source_alias}->>{target_alias}: {mermaid_flow_label(action or ('调用下游服务' if language == 'zh' else 'call downstream service'), language, 120)}{suffix}")
                if call_response:
                    lines.append(f"  {target_alias}-->>{source_alias}: {mermaid_flow_label(call_response, language, 80)}")
        elif downstream_participants and downstream_action:
            first_downstream_alias = downstream_participants[0][0]
            lines.append(f"  C->>{first_downstream_alias}: {mermaid_flow_label(downstream_action, language, 96)}")
            lines.append(f"  {first_downstream_alias}-->>C: {mermaid_flow_label('返回处理结果' if language == 'zh' else 'return processing result', language, 40)}")
        elif downstream_label and downstream_action:
            lines.append(f"  C->>D: {mermaid_flow_label(downstream_action, language, 64)}")
            lines.append(f"  D-->>C: {mermaid_flow_label('返回处理结果' if language == 'zh' else 'return processing result', language, 40)}")
        if table_names:
            if data_ops:
                for op in data_ops[:3]:
                    lines.append(f"  C->>DB: {mermaid_flow_label(op, language, 110)}")
            else:
                lines.append(f"  C->>DB: {mermaid_flow_label('按数据模型读写相关表' if language == 'zh' else 'read/write mapped tables per data model', language, 80)}")
            lines.append(f"  DB-->>C: {mermaid_flow_label('返回查询/写入结果' if language == 'zh' else 'return query/write result', language, 40)}")
        lines.append(f"  C-->>B: {mermaid_flow_label(response_label, language, 64)}")
        if backend_action:
            lines.append(f"  deactivate C")
        lines.append(f"  B-->>A: {mermaid_flow_label(success_note, language, 46)}")
        if failure:
            lines.append(f"  opt {failure_label}")
            lines.append(f"    C--xB: {mermaid_flow_label(failure, language, 64)}")
            lines.append(f"    B--xA: {mermaid_flow_label('展示校验/错误提示，保留当前输入' if language == 'zh' else 'show error and preserve input', language, 54)}")
            lines.append("  end")
    if len(interactions) > 8:
        omitted = len(interactions) - 8
        note = f"另有 {omitted} 条源码证据链路未在图中展开" if language == "zh" else f"{omitted} additional source-backed interactions are omitted"
        lines.append(f"  Note over A,C: {note}")
    lines.append("```")
    return "\n".join(lines)


def render_system_sequence_mermaid(
    technical: dict[str, Any],
    language: str = "en",
    architecture: dict[str, Any] | None = None,
    runtime_evidence: dict[str, Any] | None = None,
) -> str:
    evidence_diagram = render_runtime_sequence_evidence(runtime_evidence or {}, language)
    if evidence_diagram:
        return evidence_diagram
    architecture = architecture if isinstance(architecture, dict) else {}
    deps = [item for item in as_list(architecture.get("cross_repo_dependency_graph")) if isinstance(item, dict)]
    contract_deps = [
        item
        for item in deps
        if human_value(item.get("from"), language, "") and human_value(item.get("to"), language, "") and human_value(item.get("contract"), language, "")
    ]
    integration_steps = [item for item in as_list(architecture.get("integration_sequence")) if isinstance(item, dict)]
    deploys = [item for item in as_list(architecture.get("deployment_impact_matrix")) if isinstance(item, dict)]
    deploy_repos = [human_value(item.get("repo"), language, "") for item in deploys if human_value(item.get("repo"), language, "")]
    if contract_deps or len(set(deploy_repos)) > 1:
        first_dep = contract_deps[0] if contract_deps else {}
        source_repo = human_value(first_dep.get("from"), language, "") or next((repo for repo in deploy_repos if repo), "")
        target_repo = human_value(first_dep.get("to"), language, "")
        contract = human_value(first_dep.get("contract"), language, "")
        change = mermaid_flow_label(human_value(first_dep.get("change"), language, ""), language, 44)
        actor_label = "业务参与方" if language == "zh" else "Actor"
        browser_label = f"浏览器/前端<br/>{source_repo}" if language == "zh" else f"Browser/Frontend<br/>{source_repo}"
        if target_repo and target_repo != source_repo:
            backend_label = f"后端服务<br/>{target_repo}" if language == "zh" else f"Backend service<br/>{target_repo}"
        else:
            backend_label = "后端接口/既有契约<br/>需确认真实服务" if language == "zh" else "Backend API / existing contract<br/>service TBD"
        contract_label = mermaid_flow_label(contract or ("待确认接口契约" if language == "zh" else "contract TBD"), language, 56)
        trigger_label = "触发页面操作" if language == "zh" else "trigger page action"
        request_label = f"请求/复用 {contract_label}" if language == "zh" else f"request/reuse {contract_label}"
        success_label = change or ("返回兼容结果" if language == "zh" else "compatible response")
        frontend_success = "更新页面反馈" if language == "zh" else "update page feedback"
        backend_failure = "超时/错误/兼容失败" if language == "zh" else "timeout/error/compatibility failure"
        frontend_failure = "提示错误或保持既有行为" if language == "zh" else "show error or preserve existing behavior"
        lines = ["```mermaid", "sequenceDiagram", "  autonumber"]
        lines.append(f"  actor A as {actor_label}")
        lines.append(f"  participant B as {mermaid_flow_label(browser_label, language, 48)}")
        lines.append(f"  participant C as {mermaid_flow_label(backend_label, language, 48)}")
        runtime_steps = integration_steps[:6] or [{"action": trigger_label, "requirement_breakdown_id": ""}]
        for step in runtime_steps:
            action = human_value(step.get("action"), language, trigger_label)
            brk = human_value(step.get("requirement_breakdown_id"), language, "")
            prefix = f"{brk}: " if brk else ""
            lines.append(f"  A->>B: {mermaid_flow_label(prefix + action, language, 62)}")
            lines.append(f"  B->>C: {mermaid_flow_label((prefix + request_label), language, 64)}")
            lines.append(f"  C-->>B: {mermaid_flow_label((prefix + (success_label or ('返回兼容结果' if language == 'zh' else 'compatible response'))), language, 58)}")
            lines.append(f"  B-->>A: {mermaid_flow_label((prefix + frontend_success), language, 48)}")
        if len(integration_steps) > len(runtime_steps):
            omitted = len(integration_steps) - len(runtime_steps)
            note = f"另有 {omitted} 个业务子域按相同调用链路处理" if language == "zh" else f"{omitted} additional business slices follow the same call chain"
            lines.append(f"  Note over A,C: {note}")
        mq_items = [item for item in as_list(technical.get("mq_interactions")) if isinstance(item, dict) and item.get("applicable") is True]
        if mq_items:
            mq = mq_items[0]
            topic = human_value(mq.get("topic_or_queue"), language, "MQ")
            consumer = human_value(mq.get("consumer"), language, "consumer")
            lines.append(f"  participant M as MQ<br/>{mermaid_flow_label(topic, language, 32)}")
            lines.append(f"  participant D as {mermaid_flow_label(consumer, language, 32)}")
            lines.append(f"  C->>M: {'发布消息' if language == 'zh' else 'publish message'}")
            lines.append(f"  M-->>D: {'投递消息' if language == 'zh' else 'deliver message'}")
            lines.append(f"  D-->>M: {'消费确认' if language == 'zh' else 'ack'}")
        lines.append(f"  alt {'异常/降级' if language == 'zh' else 'exception/fallback'}")
        lines.append(f"    C--xB: {backend_failure}")
        lines.append(f"    B--xA: {frontend_failure}")
        lines.append(f"  else {'正常链路' if language == 'zh' else 'normal path'}")
        lines.append(f"    Note over A,C: {'按上述业务子域逐项返回并更新页面' if language == 'zh' else 'Each business slice returns and updates the page as shown above'}")
        lines.append("  end")
        if len(set(deploy_repos)) > 1:
            release_label = "发布顺序" if language == "zh" else "Release order"
            lines.append(f"  opt {release_label}")
            for item in deploys[:8]:
                repo = human_value(item.get("repo"), language, "")
                order = human_value(item.get("order"), language, "")
                if repo:
                    lines.append(f"    Note over B,C: #{order} {mermaid_flow_label(repo, language, 24)} / {mermaid_flow_label(human_value(item.get('artifact'), language, 'artifact'), language, 32)}")
            lines.append("  end")
        lines.append("```")
        return "\n".join(lines)
    if architecture and (deps or deploys):
        repo = next((repo for repo in deploy_repos if repo), "")
        if not repo and deps:
            repo = human_value(deps[0].get("from") or deps[0].get("to"), language, "")
        if repo:
            message = (
                "当前架构证据显示该需求属于单仓/单工程变更，未形成跨工程运行时调用时序；实现前重点确认内部契约、发布制品和回滚边界。"
                if language == "zh"
                else "Architecture evidence indicates a single-repository change with no cross-engineering runtime sequence; confirm internal contract, deploy artifact, and rollback boundary before implementation."
            )
            return "\n".join(
                [
                    f"- {message}",
                    "",
                    "```mermaid",
                    "sequenceDiagram",
                    f"  participant R1 as {mermaid_flow_label(repo, language, 36)}",
                    f"  Note over R1: {mermaid_flow_label(message, language, 96)}",
                    "```",
                ]
            )

    sequence = technical.get("system_interaction_sequence") if isinstance(technical.get("system_interaction_sequence"), dict) else {}
    if sequence.get("applicable") is not True:
        reason = text(sequence.get("not_applicable_reason") or sequence.get("reason"), "未涉及多系统交互" if language == "zh" else "no multi-system interaction")
        return f"- {reason}"
    participant_names = [human_value(item, language, "") for item in as_list(sequence.get("participants")) if human_value(item, language, "")]
    steps: list[dict[str, str]] = []
    for item in as_list(sequence.get("sequence")):
        if isinstance(item, dict):
            source = human_value(item.get("from") or item.get("source"), language, "")
            target = human_value(item.get("to") or item.get("target"), language, "")
            action = human_value(item.get("action") or item.get("step"), language, "")
            mode = human_value(item.get("mode"), language, "")
            success = human_value(item.get("success"), language, "")
            failure = human_value(item.get("failure"), language, "")
            for participant in [source, target]:
                if participant and participant not in participant_names:
                    participant_names.append(participant)
            steps.append({"source": source, "target": target, "action": action, "mode": mode, "success": success, "failure": failure})
        else:
            steps.append({"source": "", "target": "", "action": human_value(item, language, ""), "mode": "", "success": "", "failure": ""})
    steps = [item for item in steps if item.get("action")]
    if not participant_names or not steps:
        return "缺少参与方或时序步骤，无法生成时序图。" if language == "zh" else "Participants or sequence steps are missing, so the sequence diagram cannot be generated."

    def display_participant(value: str) -> str:
        rendered = value.strip()
        replacements = {
            "用户或客户端": "用户/客户端",
            "需结合代码核对的责任模块": "待确认责任模块",
            "target module to be confirmed": "Owner module TBD",
            "existing contract": "Existing contract",
        }
        for source, target in replacements.items():
            rendered = rendered.replace(source, target)
        return rendered

    display_names = []
    for participant in participant_names[:8]:
        rendered = display_participant(participant)
        if rendered and rendered not in display_names:
            display_names.append(rendered)
    aliases = {participant: f"P{index + 1}" for index, participant in enumerate(display_names)}

    def participant_alias(name: str, fallback_index: int) -> str:
        display_name = display_participant(name)
        if display_name in aliases:
            return aliases[display_name]
        fallback = display_names[fallback_index % len(display_names)]
        return aliases[fallback]

    def mermaid_label(value: str, limit: int = 72) -> str:
        cleaned = value.replace("\n", " ").replace('"', "'").replace("；", "，").replace(";", ",")
        cleaned = re.sub(r"。，", "，", cleaned)
        cleaned = re.sub(r"，+", "，", cleaned)
        cleaned = cleaned.strip(" ，")
        return cleaned[: max(limit - 3, 1)] + "..." if len(cleaned) > limit else cleaned

    def note_span(alias_values: list[str]) -> str:
        if len(alias_values) <= 1:
            return alias_values[0]
        return f"{alias_values[0]},{alias_values[-1]}"

    success_label = "正常返回" if language == "zh" else "Normal response"
    failure_label = "异常或降级" if language == "zh" else "Exception or fallback"
    retry_label = "超时与重试" if language == "zh" else "Timeout and retry"
    consistency_label = "幂等与一致性" if language == "zh" else "Idempotency and consistency"

    lines = ["```mermaid", "sequenceDiagram", "  autonumber"]
    for participant, alias in aliases.items():
        lines.append(f"  participant {alias} as {mermaid_label(participant, 32)}")

    first_source = participant_alias(steps[0].get("source", ""), 0)
    last_target = participant_alias(steps[-1].get("target", ""), len(steps))
    for index, step in enumerate(steps[:10]):
        source = participant_alias(step.get("source", ""), index)
        target = participant_alias(step.get("target", ""), index + 1)
        mode = f" [{step['mode']}]" if step.get("mode") else ""
        action = mermaid_label(step.get("action", ""), 54)
        lines.append(f"  {source}->>{target}: {action}{mode}")
    response_steps = [
        {
            "source": participant_alias(step.get("source", ""), index),
            "target": participant_alias(step.get("target", ""), index + 1),
            "success": mermaid_label(step.get("success", ""), 42),
            "failure": mermaid_label(step.get("failure", ""), 48),
        }
        for index, step in enumerate(steps[:10])
    ]
    if any(item["success"] or item["failure"] for item in response_steps):
        lines.append(f"  alt {success_label}")
        for item in reversed(response_steps):
            lines.append(f"    {item['target']}-->>{item['source']}: {item['success'] or ('处理完成' if language == 'zh' else 'completed')}")
        if any(item["failure"] for item in response_steps):
            lines.append(f"  else {failure_label}")
            for item in reversed(response_steps):
                if item["failure"]:
                    lines.append(f"    {item['target']}--x{item['source']}: {item['failure']}")
        lines.append("  end")
    if sequence.get("timeout_retry") or sequence.get("idempotency") or sequence.get("consistency"):
        source = first_source
        target = last_target
        timeout_note = mermaid_label(human_value(sequence.get("timeout_retry"), language, ""), 72)
        consistency_note = mermaid_label(
            "，".join(
                human_value(value, language, "")
                for value in [sequence.get("idempotency"), sequence.get("consistency")]
                if human_value(value, language, "")
            ),
            86,
        )
        if timeout_note:
            lines.append(f"  opt {retry_label}")
            lines.append(f"    Note over {source},{target}: {timeout_note}")
            lines.append("  end")
        if consistency_note:
            lines.append(f"  opt {consistency_label}")
            lines.append(f"    Note over {note_span(list(aliases.values()))}: {consistency_note}")
            lines.append("  end")
    lines.append("```")
    return "\n".join(lines)


def render_engineering_sequence_summary(
    architecture: dict[str, Any],
    language: str = "en",
    runtime_evidence: dict[str, Any] | None = None,
) -> str:
    runtime_evidence = runtime_evidence if isinstance(runtime_evidence, dict) else {}
    interactions = [item for item in as_list(runtime_evidence.get("interactions")) if isinstance(item, dict)]
    if interactions:
        frontend = runtime_evidence.get("frontend") if isinstance(runtime_evidence.get("frontend"), dict) else {}
        backend = runtime_evidence.get("backend") if isinstance(runtime_evidence.get("backend"), dict) else {}
        repos = []
        for item in [frontend.get("repo"), backend.get("repo")]:
            repo = human_value(item, language, "")
            if repo and repo not in repos:
                repos.append(repo)
        apis = []
        for item in interactions:
            method = human_value(item.get("method"), language, "")
            api = human_value(item.get("api"), language, "")
            contract = " ".join(part for part in [method, api] if part)
            if contract and contract not in apis:
                apis.append(contract)
        route = human_value(frontend.get("route"), language, "")
        page = human_value(frontend.get("page"), language, "")
        if language == "zh":
            return "\n".join(
                [
                    "- 时序口径：以下图优先使用源码/项目证据，表达用户在浏览器里的真实操作、前端请求、后端工程和已确认的下游处理。",
                    f"- 前端入口：{page or '未同步页面'}{('（' + route + '）') if route else ''}。",
                    f"- 涉及工程：{', '.join(repos) if repos else '未同步到工程信息'}。",
                    f"- 前端调用接口：{', '.join(apis[:8]) if apis else '未同步到接口信息'}。",
                ]
            )
        return "\n".join(
            [
                "- Sequence scope: the diagram uses source/project evidence for the real browser action, frontend request, backend owner, and confirmed downstream processing.",
                f"- Frontend entry: {page or 'not synced'}{(' (' + route + ')') if route else ''}.",
                f"- Engineering units: {', '.join(repos) if repos else 'not synced'}.",
                f"- Frontend APIs: {', '.join(apis[:8]) if apis else 'not synced'}.",
            ]
        )
    deps = [item for item in as_list(architecture.get("cross_repo_dependency_graph")) if isinstance(item, dict)]
    deploys = [item for item in as_list(architecture.get("deployment_impact_matrix")) if isinstance(item, dict)]
    if not deps and not deploys:
        return ""
    repos = []
    contracts = []
    for item in deps:
        for key in ["from", "to"]:
            repo = human_value(item.get(key), language, "")
            if repo and repo not in repos:
                repos.append(repo)
        contract = human_value(item.get("contract"), language, "")
        if contract and contract not in contracts:
            contracts.append(contract)
    for item in deploys:
        repo = human_value(item.get("repo"), language, "")
        if repo and repo not in repos:
            repos.append(repo)
    if language == "zh":
        lines = [
            "- 时序口径：以下图表达运行时触发链路，包含 Actor、浏览器/前端、后端接口/既有契约，以及已确认的下游服务或 MQ。",
            f"- 涉及工程：{', '.join(repos) if repos else '未同步到工程信息'}。",
            f"- 复用或影响的契约：{', '.join(contracts) if contracts else '未同步到契约信息'}。",
        ]
        if len(set(repos)) <= 1 and contracts:
            lines.append("- 交互判断：虽然只修改一个工程，但复用了既有契约，因此仍需要展示工程到契约的调用/兼容确认时序。")
        return "\n".join(lines)
    lines = [
        "- Sequence scope: this diagram shows the runtime trigger path, including actor, browser/frontend, backend API or existing contract, and confirmed downstream services or MQ.",
        f"- Engineering units: {', '.join(repos) if repos else 'not synced'}.",
        f"- Reused or impacted contracts: {', '.join(contracts) if contracts else 'not synced'}.",
    ]
    if len(set(repos)) <= 1 and contracts:
        lines.append("- Interaction rule: even with one changed repository, reused contracts must be shown as contract interaction and compatibility confirmation.")
    return "\n".join(lines)


def render_expert_technical_sections(
    technical: dict[str, Any],
    language: str = "en",
    architecture: dict[str, Any] | None = None,
    runtime_evidence: dict[str, Any] | None = None,
    suppress_runtime_data_model: bool = False,
) -> str:
    lang = "zh" if language == "zh" else "en"
    sections: list[str] = []
    for section in DOC_MODEL.expert_design_sections(technical):
        if suppress_runtime_data_model and section.get("section_key") == "data_model_schema":
            continue
        parts = [f"### {DOCS_I18N.section_title(section['section_key'], lang)}"]
        engineering_summary = (
            render_engineering_sequence_summary(architecture or {}, lang, runtime_evidence or {})
            if section.get("diagram") == "system_sequence"
            else ""
        )
        if engineering_summary:
            parts.append(engineering_summary)
        else:
            for group in as_list(section.get("groups")):
                if not isinstance(group, dict):
                    continue
                parts.append(
                    render_named_items(
                        as_list(group.get("items")),
                        as_list(group.get("fields")),
                        DOCS_I18N.fallback(str(group.get("fallback_key")), lang),
                        lang,
                    )
                )
        if section.get("diagram") == "system_sequence":
            parts.append(render_system_sequence_mermaid(technical, lang, architecture, runtime_evidence))
        sections.append("\n\n".join(parts))
    return "\n\n".join(sections)


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
                    output = zh_text(step.get("output"))
                    if output == "expected behavior for this sub-requirement":
                        output = "达到该子需求的预期业务结果"
                    steps.append(f"  - {zh_text(step.get('step'))}. {zh_text(step.get('actor'))}：{zh_text(step.get('action'))} -> {output}")
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
    lines: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        values = [
            f"{DOCS_I18N.label(field, 'zh')}：{render_readable_value(item.get(field), 'zh') if contains_command_token(item.get(field)) else human_value(item.get(field), 'zh')}" if language == "zh" else f"{DOCS_I18N.label(field, 'en')}: {human_value(item.get(field), 'en')}"
            for field in fields
            if item.get(field) not in (None, "", [], {})
        ]
        if values:
            separator = "；" if language == "zh" else "; "
            joined = separator.join(values)
            if len(values) >= 4 or len(joined) > 240:
                lead = values[0]
                children = "\n".join(f"  - {value}" for value in values[1:])
                lines.append(f"{lead}\n{children}" if children else lead)
            else:
                lines.append(joined)
    return bullet_lines(lines, empty)


def render_requirement_breakdown_table(technical: dict[str, Any], language: str = "en") -> str:
    rows = [item for item in as_list(technical.get("requirement_breakdown")) if isinstance(item, dict)]
    if not rows:
        return "- 未同步到子需求设计矩阵。" if language == "zh" else "- No sub-requirement design matrix was synced."
    if language == "zh":
        lines = ["| 子需求 | 行为变化 | 影响面 | 字段影响 | 接口影响 | 权限影响 |", "|---|---|---|---|---|---|"]
        for item in rows:
            lines.append(
                f"| `{text(item.get('id'))}` {zh_text(item.get('summary'))} | "
                f"{zh_text(item.get('behavior_change'))} | {zh_text(item.get('impact_areas'))} | "
                f"{zh_text(item.get('field_impact'))} | {zh_text(item.get('api_impact'))} | {zh_text(item.get('permission_impact'))} |"
            )
        return "\n".join(lines)
    lines = ["| Slice | Behavior Change | Impact Areas | Field Impact | API Impact | Permission Impact |", "|---|---|---|---|---|---|"]
    for item in rows:
        lines.append(
            f"| `{text(item.get('id'))}` {text(item.get('summary'))} | "
            f"{text(item.get('behavior_change'))} | {text(item.get('impact_areas'))} | "
            f"{text(item.get('field_impact'))} | {text(item.get('api_impact'))} | {text(item.get('permission_impact'))} |"
        )
    return "\n".join(lines)


def render_entrypoint_confidence(technical: dict[str, Any], language: str = "en") -> str:
    confidence = technical.get("code_entrypoint_confidence") if isinstance(technical.get("code_entrypoint_confidence"), dict) else {}
    if not confidence:
        return "- 未同步到代码入口置信度。" if language == "zh" else "- No code entrypoint confidence was synced."
    ranked = []
    for item in as_list(confidence.get("ranked_candidates"))[:5]:
        if isinstance(item, dict):
            evidence = item.get("evidence")
            evidence_text = zh_text(evidence, "无证据") if language == "zh" and evidence not in (None, "", [], {}) else text(evidence, "no evidence") if evidence not in (None, "", [], {}) else ("无证据" if language == "zh" else "no evidence")
            path_text = zh_text(item.get("path")) if language == "zh" else text(item.get("path"))
            ranked.append(f"`{path_text}` score={text(item.get('score'), '0')} evidence={evidence_text}")
    if language == "zh":
        return (
            f"- 置信度：`{zh_text(confidence.get('level'))}`\n"
            f"- 主入口：`{zh_text(confidence.get('selected_entrypoint'))}`\n"
            f"- 命中证据：{zh_text(confidence.get('evidence'))}\n"
            f"- 低置信原因：{zh_text(confidence.get('blocker'), '无')}\n"
            f"- 候选入口：{'; '.join(ranked) or '未同步'}"
        )
    return (
        f"- Confidence: `{text(confidence.get('level'))}`\n"
        f"- Primary entrypoint: `{text(confidence.get('selected_entrypoint'))}`\n"
        f"- Evidence: {text(confidence.get('evidence'))}\n"
        f"- Low-confidence reason: {text(confidence.get('blocker'), 'none')}\n"
        f"- Ranked candidates: {'; '.join(ranked) or 'not synced'}"
    )


def render_field_api_permission_impact(technical: dict[str, Any], language: str = "en") -> str:
    rows = [item for item in as_list(technical.get("field_api_permission_impact")) if isinstance(item, dict)]
    if not rows:
        return "- 未同步到字段/接口/权限影响表。" if language == "zh" else "- No field/API/permission impact table was synced."
    if language == "zh":
        lines = ["| 子需求 | 责任入口 | 字段 | 接口 | 权限 | 入口置信度 |", "|---|---|---|---|---|---|"]
        for item in rows:
            lines.append(
                f"| `{text(item.get('requirement_breakdown_id'))}` {zh_text(item.get('summary'))} | "
                f"`{zh_text(item.get('owner_entrypoint'))}` | {zh_text(item.get('field_impact'))} | "
                f"{zh_text(item.get('api_impact'))} | {zh_text(item.get('permission_impact'))} | {zh_text(item.get('entrypoint_confidence'))} |"
            )
        return "\n".join(lines)
    lines = ["| Slice | Owner Entrypoint | Field | API | Permission | Confidence |", "|---|---|---|---|---|---|"]
    for item in rows:
        lines.append(
            f"| `{text(item.get('requirement_breakdown_id'))}` {text(item.get('summary'))} | "
            f"`{text(item.get('owner_entrypoint'))}` | {text(item.get('field_impact'))} | "
            f"{text(item.get('api_impact'))} | {text(item.get('permission_impact'))} | {text(item.get('entrypoint_confidence'))} |"
        )
    return "\n".join(lines)


def render_low_confidence_items(technical: dict[str, Any], architecture: dict[str, Any], language: str = "en") -> str:
    rows = [item for item in as_list(technical.get("low_confidence_items")) if isinstance(item, dict)]
    arch_conf = architecture.get("architecture_decision_confidence") if isinstance(architecture.get("architecture_decision_confidence"), dict) else {}
    for item in as_list(arch_conf.get("confidence_reducers")):
        if isinstance(item, dict):
            rows.append({"item": item.get("source"), "level": item.get("severity"), "reason": item.get("message"), "required_action": "revise design or collect evidence"})
    if not rows:
        return "- 当前未记录低置信度需确认项。" if language == "zh" else "- No low-confidence confirmation items are recorded."
    if language == "zh":
        return bullet_lines([
            f"`{zh_text(item.get('item'))}`：等级={zh_text(item.get('level'))}；原因={zh_text(item.get('reason'))}；动作={zh_text(item.get('required_action'))}"
            for item in rows
        ], "当前未记录低置信度需确认项。")
    return bullet_lines([
        f"`{text(item.get('item'))}`: level={text(item.get('level'))}; reason={text(item.get('reason'))}; action={text(item.get('required_action'))}"
        for item in rows
    ], "No low-confidence confirmation items are recorded.")


def render_problem_analysis(technical: dict[str, Any], language: str = "en", runtime_evidence: dict[str, Any] | None = None) -> str:
    problem = technical.get("problem_analysis") if isinstance(technical.get("problem_analysis"), dict) else {}
    current = technical.get("current_state_analysis") if isinstance(technical.get("current_state_analysis"), dict) else {}
    data = {**current, **problem}
    runtime_evidence = runtime_evidence if isinstance(runtime_evidence, dict) else {}
    interactions = [item for item in as_list(runtime_evidence.get("interactions")) if isinstance(item, dict)]
    if interactions:
        frontend = runtime_evidence.get("frontend") if isinstance(runtime_evidence.get("frontend"), dict) else {}
        backend = runtime_evidence.get("backend") if isinstance(runtime_evidence.get("backend"), dict) else {}
        frontend_entry = " / ".join(
            item
            for item in [
                human_value(frontend.get("repo"), language, ""),
                human_value(frontend.get("page"), language, ""),
                human_value(frontend.get("route"), language, ""),
            ]
            if item
        )
        backend_entry = " / ".join(
            item
            for item in [
                human_value(backend.get("repo"), language, ""),
                human_value(backend.get("controller"), language, ""),
                human_value(backend.get("service"), language, ""),
            ]
            if item
        )
        triggers = human_value(frontend.get("entry_menu_or_button"), language, "")
        apis = []
        scenarios = []
        for item in interactions:
            scenario = human_value(item.get("scenario"), language, "")
            if scenario:
                scenarios.append(scenario)
            method = human_value(item.get("method"), language, "")
            api = human_value(item.get("api"), language, "")
            value = " ".join(part for part in [method, api] if part)
            if value and value not in apis:
                apis.append(value)
        scenario_gaps = []
        for item in interactions[:8]:
            scenario = human_value(item.get("scenario"), language, "")
            request = human_value(item.get("request"), language, "")
            response = human_value(item.get("response"), language, "")
            failure = human_value(item.get("failure"), language, "")
            gap = human_value(item.get("current_gap") or item.get("gap") or item.get("problem"), language, "")
            if not gap:
                if request and response:
                    gap = f"当前链路需要验证 `{request}` 是否能稳定产生 `{response}`"
                elif response:
                    gap = f"当前链路需要补齐或校准 `{response}`"
                elif failure:
                    gap = f"当前链路需要明确 `{failure}` 的前后端处理边界"
            if scenario and gap:
                scenario_gaps.append(f"{scenario}：{gap}")
        if language == "zh":
            sections = [
                ("当前真实行为", f"运营人员通过 {frontend_entry or '前端页面'} 触发续期结算、结算单和续期池操作，前端调用 operate 后端接口完成查询、试算、生成结算单和移出续期池。"),
                ("用户触发点", triggers),
                ("代码入口", f"前端：{frontend_entry or '未同步'}；后端：{backend_entry or '未同步'}"),
                ("关键接口", ", ".join(apis[:10])),
                ("业务问题", data.get("business_problem")),
                ("现有流程缺口", scenario_gaps or data.get("process_gap")),
                ("本次目标", data.get("design_goals")),
                ("成功标准", data.get("success_criteria")),
            ]
            return "\n".join(
                f"- {label}：{render_readable_value(value, language).replace('npm run build:测试', 'npm run build:test')}"
                for label, value in sections
                if value not in (None, "", [], {})
            )
        sections = [
            ("Current real behavior", f"Operators use {frontend_entry or 'the frontend page'} to trigger renewal settlement, settlement order, and renewal pool actions; the frontend calls operate backend APIs for queries, trials, order creation, and renewal-pool exclusion."),
            ("User triggers", triggers),
            ("Code entrypoints", f"Frontend: {frontend_entry or 'not synced'}; backend: {backend_entry or 'not synced'}"),
            ("Key APIs", ", ".join(apis[:10])),
            ("Business problem", data.get("business_problem")),
            ("Process gap", scenario_gaps or data.get("process_gap")),
            ("Design goals", data.get("design_goals")),
            ("Success criteria", data.get("success_criteria")),
        ]
        return "\n".join(f"- {label}: {render_readable_value(value, language)}" for label, value in sections if value not in (None, "", [], {}))
    if not data:
        return "- 未同步到现状问题分析。" if language == "zh" else "- No problem analysis was synced."
    if language == "zh":
        sections = [
            ("当前行为", data.get("current_behavior") or data.get("existing_behavior")),
            ("业务问题", data.get("business_problem")),
            ("现有流程缺口", data.get("process_gap")),
            ("代码入口", data.get("code_entrypoints")),
            ("约束", data.get("constraints") or data.get("known_constraints")),
            ("本次目标", data.get("design_goals")),
            ("非目标", data.get("non_goals")),
            ("成功标准", data.get("success_criteria")),
        ]
        return "\n".join(f"- {label}：{render_readable_value(value, language)}" for label, value in sections if value not in (None, "", [], {})) or "- 未同步到现状问题分析。"
    sections = [
        ("Current behavior", data.get("current_behavior") or data.get("existing_behavior")),
        ("Business problem", data.get("business_problem")),
        ("Process gap", data.get("process_gap")),
        ("Code entrypoints", data.get("code_entrypoints")),
        ("Constraints", data.get("constraints") or data.get("known_constraints")),
        ("Design goals", data.get("design_goals")),
        ("Non-goals", data.get("non_goals")),
        ("Success criteria", data.get("success_criteria")),
    ]
    return "\n".join(f"- {label}: {render_readable_value(value, language)}" for label, value in sections if value not in (None, "", [], {})) or "- No problem analysis was synced."


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
    doc_title = zh_text(test_design.get("title"), "本需求") if language == "zh" else text(test_design.get("title"), "this requirement")
    for case in cases:
        steps = as_list(case.get("steps"))
        evidence = as_list(case.get("evidence_required"))
        execution = as_list(case.get("execution_path"))
        assertions = as_list(case.get("assertion_points"))
        semantic_refs = case.get("semantic_refs") if isinstance(case.get("semantic_refs"), dict) else {}
        data_strategy = case.get("data_setup_strategy") if isinstance(case.get("data_setup_strategy"), dict) else {}
        setup_methods = as_list(data_strategy.get("setup_methods"))
        data_records = as_list(data_strategy.get("records"))
        accounts = as_list(data_strategy.get("accounts"))
        cleanup = as_list(data_strategy.get("cleanup"))
        if language == "zh":
            title = clean_test_title(case.get("title"), "zh")
            if title in {"标准", "验收标准", "验证：标准"}:
                title = f"验证：{doc_title}"
            reason_title = re.sub(r"^(验证：|回归验证：)", "", title).strip()
            record_text = "；".join(summarize_dict_item(item, ["name", "state", "source"], "zh") if isinstance(item, dict) else zh_text(item) for item in data_records)
            account_text = "；".join(summarize_dict_item(item, ["role", "purpose"], "zh") if isinstance(item, dict) else zh_text(item) for item in accounts)
            semantic_text = "；".join(
                f"{label}：{', '.join(zh_text(item) for item in as_list(semantic_refs.get(key)))}"
                for key, label in [
                    ("ui_refs", "页面"),
                    ("api_refs", "接口"),
                    ("data_refs", "数据"),
                    ("permission_refs", "权限"),
                ]
                if as_list(semantic_refs.get(key))
            )
            sections.append(
                f"### `{text(case.get('id'))}` {title}\n\n"
                f"- 关联验收：{zh_text(case.get('acceptance_id'), '未绑定')}\n"
                f"- 类型：{zh_text(case.get('type'))}\n"
                f"- 为什么测：该用例用于证明「{reason_title or title}」是否能在真实业务入口、接口/数据语义和验收证据之间闭环。\n"
                f"- 项目语义依据：{semantic_text or '未同步到项目语义依据'}\n"
                f"- 前置条件：{', '.join(zh_text(item) for item in as_list(case.get('preconditions'))) or '无'}\n"
                f"- 怎么造数：{', '.join(zh_text(item) for item in setup_methods) or '待补充'}；数据记录：{record_text or '待补充'}；账号角色：{account_text or '无'}\n"
                f"- 怎么执行：{'; '.join(zh_text(item) for item in execution) or '待补充'}；详细步骤：{'; '.join(zh_text(item) for item in steps) or '待补充'}\n"
                f"- 怎么判定通过：{'; '.join(zh_text(item) for item in assertions) or '待补充'}\n"
                f"- 预期结果：{zh_text(case.get('expected_result'))}\n"
                f"- 清理要求：{'; '.join(zh_text(item) for item in cleanup) or ', '.join(zh_text(item) for item in as_list(case.get('cleanup_expectations'))) or '待补充'}\n"
                f"- 所需证据：{', '.join(zh_text(item) for item in evidence) or '待补充'}"
            )
        else:
            record_text = "; ".join(summarize_dict_item(item, ["name", "state", "source"], "en") if isinstance(item, dict) else text(item) for item in data_records)
            account_text = "; ".join(summarize_dict_item(item, ["role", "purpose"], "en") if isinstance(item, dict) else text(item) for item in accounts)
            semantic_text = "; ".join(
                f"{label}: {', '.join(text(item) for item in as_list(semantic_refs.get(key)))}"
                for key, label in [
                    ("ui_refs", "UI"),
                    ("api_refs", "API"),
                    ("data_refs", "Data"),
                    ("permission_refs", "Permission"),
                ]
                if as_list(semantic_refs.get(key))
            )
            sections.append(
                f"### `{text(case.get('id'))}` {text(case.get('title'))}\n\n"
                f"- Acceptance: {text(case.get('acceptance_id'), 'unmapped')}\n"
                f"- Type: {text(case.get('type'))}\n"
                f"- Why test: this case proves the acceptance behavior through the mapped business entry, contract/data semantics, and evidence path.\n"
                f"- Semantic refs: {semantic_text or 'not synced'}\n"
                f"- Preconditions: {', '.join(text(item) for item in as_list(case.get('preconditions'))) or 'none'}\n"
                f"- How to prepare data: {', '.join(text(item) for item in setup_methods) or 'TBD'}; records: {record_text or 'TBD'}; accounts/roles: {account_text or 'none'}\n"
                f"- How to execute: {'; '.join(text(item) for item in execution) or 'TBD'}; steps: {'; '.join(text(item) for item in steps) or 'TBD'}\n"
                f"- How to pass: {'; '.join(text(item) for item in assertions) or 'TBD'}\n"
                f"- Expected result: {text(case.get('expected_result'))}\n"
                f"- Cleanup: {'; '.join(text(item) for item in cleanup) or ', '.join(text(item) for item in as_list(case.get('cleanup_expectations'))) or 'TBD'}\n"
                f"- Evidence required: {', '.join(text(item) for item in evidence) or 'TBD'}"
            )
    return "\n\n".join(sections)


def render_test_data_plan(test_data_plan: dict[str, Any], language: str = "en") -> str:
    datasets = [item for item in as_list(test_data_plan.get("datasets")) if isinstance(item, dict)]
    if not datasets:
        return "- 未同步到测试数据计划；有测试用例时应生成 `test_data_plan.json`。" if language == "zh" else "- No test data plan was synced; `test_data_plan.json` is expected when test cases exist."
    sections: list[str] = []
    for dataset in datasets:
        setup = zh_text(dataset.get("setup_method")) if language == "zh" else text(dataset.get("setup_method"))
        cases = ", ".join(text(item) for item in as_list(dataset.get("case_ids"))) or ("未绑定" if language == "zh" else "unmapped")
        cleanup = ", ".join(summarize_dict_item(item, ["method", "owner"], language) if isinstance(item, dict) else (zh_text(item) if language == "zh" else text(item)) for item in as_list(dataset.get("cleanup")))
        accounts = ", ".join(summarize_dict_item(item, ["role", "source"], language) if isinstance(item, dict) else (zh_text(item) if language == "zh" else text(item)) for item in as_list(dataset.get("accounts")))
        roles = ", ".join(zh_text(item) for item in as_list(dataset.get("roles"))) if language == "zh" else ", ".join(text(item) for item in as_list(dataset.get("roles")))
        privacy = ", ".join(zh_text(item) for item in as_list(dataset.get("privacy_controls"))) if language == "zh" else ", ".join(text(item) for item in as_list(dataset.get("privacy_controls")))
        if language == "zh":
            sections.append(
                f"### `{text(dataset.get('id'))}`\n\n"
                f"- 关联用例：{cases}\n"
                f"- 数据级别：{zh_text(dataset.get('data_classification'))}\n"
                f"- 准备方式：{setup}\n"
                f"- 账号/角色：{accounts or roles or '无'}\n"
                f"- 清理要求：{cleanup or '待补充'}\n"
                f"- 隐私控制：{privacy or '待补充'}"
            )
        else:
            sections.append(
                f"### `{text(dataset.get('id'))}`\n\n"
                f"- Cases: {cases}\n"
                f"- Classification: {text(dataset.get('data_classification'))}\n"
                f"- Setup: {setup}\n"
                f"- Accounts/roles: {accounts or roles or 'none'}\n"
                f"- Cleanup: {cleanup or 'TBD'}\n"
                f"- Privacy controls: {privacy or 'TBD'}"
            )
    return "\n\n".join(sections)


def render_solution_options(technical: dict[str, Any], architecture: dict[str, Any], language: str = "en") -> str:
    def option_coverage_summary(options: list[Any], option_kind: str) -> list[str]:
        dict_options = [item for item in options if isinstance(item, dict)]
        count = len(dict_options)
        names = " ".join(str(item.get("name") or "") for item in dict_options)
        triggers: list[str] = []
        if any(token in names for token in ["接口", "契约", "service/API", "contract"]):
            triggers.append("接口/契约")
        if any(token in names for token in ["字段", "数据", "Data"]):
            triggers.append("数据口径")
        if "权限" in names:
            triggers.append("权限闭环")
        if "前后端" in names:
            triggers.append("前后端协同")
        if "子域" in names:
            triggers.append("多业务子域")
        if any(token in names for token in ["灰度", "兼容", "backward"]):
            triggers.append("灰度兼容")
        if option_kind == "technical":
            base = "责任入口"
        else:
            base = "架构责任边界"
        if language == "zh":
            lines = [
                f"- 本节候选方案共 {count} 个，不按固定二选一/三选一生成，而是从{base}、需求影响面和交付风险动态展开。",
                f"- 触发的专项比较面：{('、'.join(triggers)) if triggers else '未发现需要独立展开的专项影响面'}。",
                "- 阅读顺序：先看每个候选方案的适用条件、实施/发布影响和风险控制，再看后续加权矩阵和决策结论。",
            ]
        else:
            lines = [
                f"- This section has {count} candidate options. Options are generated dynamically from the owner boundary, impact surface, and delivery risk rather than a fixed two/three-option template.",
                f"- Specialized comparison surfaces: {', '.join(triggers) if triggers else 'none detected beyond the base owner boundary'}.",
                "- Read each option's applicability, implementation/release impact, and risk controls before the weighted matrix and final decision.",
            ]
        return lines

    def render_option_detail(item: dict[str, Any], option_kind: str) -> list[str]:
        if language == "zh":
            detail_lines = [
                f"#### 方案 `{text(item.get('option_id'))}`：{zh_option_name(item, option_kind)}",
                "",
                f"- 描述：{zh_text(item.get('description'))}",
                f"- 适用条件：{zh_text(item.get('when_to_choose'))}",
                f"- 优势：{zh_text(item.get('pros'))}",
                f"- 劣势：{zh_text(item.get('cons'))}",
                f"- 风险等级：{zh_text(item.get('risk_level'))}",
                f"- 风险控制：{zh_text(item.get('risk_controls'))}",
                f"- 验证方式：{zh_text(item.get('validation'))}",
                f"- 性能影响：{zh_text(item.get('performance_impact'))}",
                f"- 回滚策略：{zh_text(item.get('rollback_strategy'))}",
            ]
            if option_kind == "technical":
                detail_lines.extend([
                    f"- 实施轮廓：{zh_text(item.get('implementation_outline'))}",
                    f"- 测试证据：{zh_text(item.get('test_evidence'))}",
                    f"- 上线影响：{zh_text(item.get('rollout_impact'))}",
                ])
            else:
                detail_lines.extend([
                    f"- 责任仓库：{zh_text(item.get('owner_repos'))}",
                    f"- 仅确认仓库：{zh_text(item.get('confirm_only_repos'), '无')}",
                    f"- 集成影响：{zh_text(item.get('integration_impact'))}",
                    f"- 部署影响：{zh_text(item.get('deployment_impact'))}",
                    f"- 回滚复杂度：{zh_text(item.get('rollback_complexity'))}",
                ])
            return detail_lines

        detail_lines = [
            f"#### Option `{text(item.get('option_id'))}`: {text(item.get('name'))}",
            "",
            f"- Description: {text(item.get('description'))}",
            f"- When to choose: {text(item.get('when_to_choose'))}",
            f"- Pros: {text(item.get('pros'))}",
            f"- Cons: {text(item.get('cons'))}",
            f"- Risk level: {text(item.get('risk_level'))}",
            f"- Risk controls: {text(item.get('risk_controls'))}",
            f"- Validation: {text(item.get('validation'))}",
            f"- Performance impact: {text(item.get('performance_impact'))}",
            f"- Rollback strategy: {text(item.get('rollback_strategy'))}",
        ]
        if option_kind == "technical":
            detail_lines.extend([
                f"- Implementation outline: {text(item.get('implementation_outline'))}",
                f"- Test evidence: {text(item.get('test_evidence'))}",
                f"- Rollout impact: {text(item.get('rollout_impact'))}",
            ])
        else:
            detail_lines.extend([
                f"- Owner repos: {text(item.get('owner_repos'))}",
                f"- Confirm-only repos: {text(item.get('confirm_only_repos'), 'none')}",
                f"- Integration impact: {text(item.get('integration_impact'))}",
                f"- Deployment impact: {text(item.get('deployment_impact'))}",
                f"- Rollback complexity: {text(item.get('rollback_complexity'))}",
            ])
        return detail_lines

    def render_matrix(matrix: list[Any], score_summary: dict[str, Any]) -> list[str]:
        if language == "zh":
            lines = ["", "#### 加权对比矩阵", ""]
            if matrix:
                lines.extend(["| 维度 | 权重 | 评分 | 优胜 | 理由 |", "|---|---:|---|---|---|"])
                for row in matrix:
                    if not isinstance(row, dict):
                        continue
                    scores = row.get("scores") if isinstance(row.get("scores"), dict) else {}
                    score_text = "；".join(f"{key}={value}" for key, value in scores.items())
                    lines.append(f"| {zh_text(row.get('criterion'))} | {text(row.get('weight'), '0')} | {score_text or '待补充'} | {zh_text(row.get('winner'))} | {zh_text(row.get('reason'))} |")
            else:
                lines.append("- 未同步到加权对比矩阵。")
            lines.extend(["", "#### 评分汇总", ""])
            if score_summary:
                score_lines = []
                for key, value in score_summary.items():
                    if key == "scoring_rule":
                        continue
                    score_lines.append(f"`{key}`={value}")
                lines.append(f"- 分数：{', '.join(score_lines) or '待补充'}")
                lines.append(f"- 评分规则：{zh_text(score_summary.get('scoring_rule'))}")
            else:
                lines.append("- 未同步到评分汇总。")
            return lines

        lines = ["", "#### Weighted Comparison Matrix", ""]
        if matrix:
            lines.extend(["| Criterion | Weight | Scores | Winner | Reason |", "|---|---:|---|---|---|"])
            for row in matrix:
                if not isinstance(row, dict):
                    continue
                scores = row.get("scores") if isinstance(row.get("scores"), dict) else {}
                score_text = "; ".join(f"{key}={value}" for key, value in scores.items())
                lines.append(f"| {text(row.get('criterion'))} | {text(row.get('weight'), '0')} | {score_text or 'TBD'} | {text(row.get('winner'))} | {text(row.get('reason'))} |")
        else:
            lines.append("- No weighted comparison matrix was synced.")
        lines.extend(["", "#### Score Summary", ""])
        if score_summary:
            score_lines = []
            for key, value in score_summary.items():
                if key == "scoring_rule":
                    continue
                score_lines.append(f"`{key}`={value}")
            lines.append(f"- Scores: {', '.join(score_lines) or 'TBD'}")
            lines.append(f"- Scoring rule: {text(score_summary.get('scoring_rule'))}")
        else:
            lines.append("- No score summary was synced.")
        return lines

    sections: list[str] = []
    selected_technical = technical.get("selected_solution") if isinstance(technical.get("selected_solution"), dict) else {}
    selected_arch = architecture.get("selected_architecture") if isinstance(architecture.get("selected_architecture"), dict) else {}
    for option_title, comparison_title, decision_title, options, selected, option_kind, matrix, score_summary in [
        (
            "技术候选方案详述" if language == "zh" else "Technical Candidate Options",
            "技术方案加权对比" if language == "zh" else "Technical Weighted Comparison",
            "技术决策结论" if language == "zh" else "Technical Decision",
            as_list(technical.get("solution_options")),
            selected_technical,
            "technical",
            as_list(technical.get("option_comparison_matrix")),
            technical.get("option_score_summary") if isinstance(technical.get("option_score_summary"), dict) else {},
        ),
        (
            "架构候选方案详述" if language == "zh" else "Architecture Candidate Options",
            "架构方案加权对比" if language == "zh" else "Architecture Weighted Comparison",
            "架构决策结论" if language == "zh" else "Architecture Decision",
            as_list(architecture.get("architecture_options")),
            selected_arch,
            "architecture",
            as_list(architecture.get("architecture_fit_matrix")),
            architecture.get("architecture_score_summary") if isinstance(architecture.get("architecture_score_summary"), dict) else {},
        ),
    ]:
        lines = [f"### {option_title}", ""]
        lines.extend(option_coverage_summary(options, option_kind))
        lines.append("")
        for item in options:
            if isinstance(item, dict):
                lines.extend(render_option_detail(item, option_kind))
                lines.append("")
        lines.extend(["", f"### {comparison_title}", ""])
        lines.extend(render_matrix(matrix, score_summary))
        lines.append("")
        if language == "zh":
            lines.append(f"### {decision_title}")
            lines.append("")
            lines.append(f"- 选中：`{text(selected.get('selected_option_id'))}`")
            lines.append(f"- 选择理由：{zh_decision_reason(selected, options, option_kind)}")
            lines.append(f"- 决策标准：{zh_inline_list(selected.get('decision_criteria'))}")
            lines.append(f"- 取舍：{zh_inline_list(selected.get('tradeoffs'))}")
            rejected = as_list(selected.get("rejected_alternative_reasoning"))
            lines.append(f"- 被拒方案理由：{'；'.join(zh_rejected_reason(item, options) for item in rejected) if rejected else '无'}")
        else:
            lines.append(f"### {decision_title}")
            lines.append("")
            lines.append(f"- Selected: `{text(selected.get('selected_option_id'))}`")
            lines.append(f"- Selection reason: {text(selected.get('selection_reason'))}")
            lines.append(f"- Decision criteria: {text(selected.get('decision_criteria'))}")
            lines.append(f"- Tradeoffs: {text(selected.get('tradeoffs'))}")
            lines.append(f"- Rejected alternative reasoning: {text(selected.get('rejected_alternative_reasoning'))}")
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def render_blockers(*documents: dict[str, Any], language: str = "en") -> str:
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
    empty = "无未过门禁。" if language == "zh" else "None."
    return bullet_lines(lines[:10], empty)


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


def render_spec_review_narrative(spec: dict[str, Any], language: str = "en") -> str:
    summary = spec.get("requirement_summary") or spec.get("summary") or spec.get("title") or "本需求"
    scope = spec.get("scope") if isinstance(spec.get("scope"), dict) else {}
    in_scope = "、".join(zh_text(item) for item in as_list(scope.get("in_scope"))) or zh_text(summary)
    out_scope = "、".join(zh_text(item) for item in as_list(scope.get("out_of_scope"))) or "未声明额外范围外事项，评审时仍需确认是否存在隐含排除项"
    acceptance = [clean_acceptance_text(item.get("criteria"), "zh") for item in as_list(spec.get("acceptance_criteria")) if isinstance(item, dict)]
    acceptance_text = "；".join(acceptance) or "未同步到明确验收标准"
    questions = [zh_text(item.get("question") or item.get("summary") or item) if isinstance(item, dict) else zh_text(item) for item in as_list(spec.get("open_questions"))]
    question_text = "；".join(questions) or "当前没有记录阻塞性澄清问题"
    if language == "zh":
        return (
            f"本需求的评审重点不是只确认标题是否正确，而是确认“{zh_text(summary)}”在业务流程、页面/接口行为、权限边界和验收证据之间是否形成闭环。"
            f"当前纳入范围的内容包括：{in_scope}。范围外或暂不处理的内容为：{out_scope}。如果评审过程中发现这些边界与真实业务预期不一致，需要先回到需求澄清，而不是直接进入实现。\n\n"
            f"验收标准需要作为后续技术设计、测试设计和发布证据的共同锚点。当前同步到的验收口径为：{acceptance_text}。"
            "设计评审时应逐条检查每个验收项是否能在模块设计、接口/页面行为、测试用例和证据文件中找到对应引用；缺少任一环节时，本需求只能视为未完成交付准备。\n\n"
            f"澄清状态方面，{question_text}。即使没有阻塞性问题，也仍需在实现前确认需求原文、验收口径和交付边界没有被过度解释；"
            "特别是涉及权限、数据筛选、状态口径、默认展示和回滚影响的内容，应在技术设计和测试设计中继续保留可追溯证据。\n\n"
            "进入设计或实现前，评审人应重点确认三件事：第一，需求是否只描述了期望结果，还是已经隐含了实现方式；第二，验收标准是否足够观察和复现，"
            "能否转换为明确测试用例；第三，后续交付是否需要额外的配置、数据准备、权限账号、发布窗口或回滚动作。"
            "这些内容如果没有在需求阶段说明清楚，也必须在设计、测试和发布文档中被显式承接，避免实现完成后才发现验收口径不一致。"
        )
    return (
        f"This requirement should be reviewed as a traceable delivery scope, not only as a title: {text(summary)}. "
        f"In scope: {text(scope.get('in_scope') or summary)}. Out of scope: {text(scope.get('out_of_scope') or 'not explicitly declared')}. "
        f"Acceptance criteria: {text(acceptance)}. Clarification state: {text(questions or 'no blocking questions recorded')}."
    )


def render_design_review_context(
    technical: dict[str, Any],
    architecture: dict[str, Any],
    delivery_plan: dict[str, Any],
    language: str = "en",
    runtime_evidence: dict[str, Any] | None = None,
) -> str:
    runtime_evidence = runtime_evidence if isinstance(runtime_evidence, dict) else {}
    runtime_interactions = [item for item in as_list(runtime_evidence.get("interactions")) if isinstance(item, dict)]
    module_count = len(as_list(runtime_evidence.get("data_models"))) or len(as_list(technical.get("module_decomposition")))
    contract_count = len({human_value(item.get("api"), language, "") for item in runtime_interactions if human_value(item.get("api"), language, "")}) or len(as_list(technical.get("api_contracts")))
    runtime_repos = {
        human_value((runtime_evidence.get("frontend") or {}).get("repo"), language, ""),
        human_value((runtime_evidence.get("backend") or {}).get("repo"), language, ""),
    } - {""}
    repo_count = len(as_list(delivery_plan.get("repo_tasks")))
    repo_count = max(repo_count, len(runtime_repos))
    dependency_count = len(as_list(architecture.get("cross_repo_dependency_graph")))
    if runtime_interactions and len(runtime_repos) > 1:
        dependency_count = max(dependency_count, 1)
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


def render_runtime_evidence_context(runtime_evidence: dict[str, Any], language: str = "en") -> str:
    if not isinstance(runtime_evidence, dict) or not runtime_evidence:
        return ""
    frontend = runtime_evidence.get("frontend") if isinstance(runtime_evidence.get("frontend"), dict) else {}
    backend = runtime_evidence.get("backend") if isinstance(runtime_evidence.get("backend"), dict) else {}
    interactions = [item for item in as_list(runtime_evidence.get("interactions")) if isinstance(item, dict)]
    if not frontend and not backend and not interactions:
        return ""
    actor = human_value(runtime_evidence.get("actor"), language, "")
    frontend_entry = " / ".join(
        item
        for item in [
            human_value(frontend.get("repo"), language, ""),
            human_value(frontend.get("page"), language, ""),
            human_value(frontend.get("route"), language, ""),
        ]
        if item
    )
    trigger = human_value(frontend.get("entry_menu_or_button"), language, "")
    backend_entry = " / ".join(
        item
        for item in [
            human_value(backend.get("repo"), language, ""),
            human_value(backend.get("controller"), language, ""),
            human_value(backend.get("service"), language, ""),
        ]
        if item
    )
    apis = []
    for item in interactions:
        method = human_value(item.get("method"), language, "")
        api = human_value(item.get("api"), language, "")
        value = " ".join(part for part in [method, api] if part)
        if value and value not in apis:
            apis.append(value)
    if language == "zh":
        lines = ["### 源码证据校准", ""]
        if actor:
            lines.append(f"- 操作角色：{actor}")
        if frontend_entry:
            lines.append(f"- 前端入口：{frontend_entry}")
        if trigger:
            lines.append(f"- 用户触发：{trigger}")
        if backend_entry:
            lines.append(f"- 后端责任：{backend_entry}")
        if apis:
            lines.append(f"- 关键接口：{', '.join(apis[:10])}")
        lines.append("- 说明：以上信息来自本地工程证据 artifact；与自动生成的架构草稿不一致时，以该证据作为本轮文档时序和接口边界的校准依据。")
        return "\n".join(lines)
    lines = ["### Source Evidence Calibration", ""]
    if actor:
        lines.append(f"- Actor: {actor}")
    if frontend_entry:
        lines.append(f"- Frontend entry: {frontend_entry}")
    if trigger:
        lines.append(f"- User trigger: {trigger}")
    if backend_entry:
        lines.append(f"- Backend owner: {backend_entry}")
    if apis:
        lines.append(f"- Key APIs: {', '.join(apis[:10])}")
    lines.append("- Note: this comes from local source evidence artifacts and calibrates sequence/API boundaries when generated architecture drafts are broader or stale.")
    return "\n".join(lines)


def render_current_architecture_context(
    architecture: dict[str, Any],
    runtime_evidence: dict[str, Any],
    language: str = "en",
) -> str:
    if isinstance(runtime_evidence, dict) and runtime_evidence.get("interactions"):
        frontend = runtime_evidence.get("frontend") if isinstance(runtime_evidence.get("frontend"), dict) else {}
        backend = runtime_evidence.get("backend") if isinstance(runtime_evidence.get("backend"), dict) else {}
        interactions = [item for item in as_list(runtime_evidence.get("interactions")) if isinstance(item, dict)]
        frontend_entry = " / ".join(
            item
            for item in [
                human_value(frontend.get("repo"), language, ""),
                human_value(frontend.get("page"), language, ""),
                human_value(frontend.get("route"), language, ""),
            ]
            if item
        )
        backend_entry = " / ".join(
            item
            for item in [
                human_value(backend.get("repo"), language, ""),
                human_value(backend.get("controller"), language, ""),
                human_value(backend.get("service"), language, ""),
            ]
            if item
        )
        scenarios = [human_value(item.get("scenario"), language, "") for item in interactions if human_value(item.get("scenario"), language, "")]
        apis = []
        for item in interactions:
            method = human_value(item.get("method"), language, "")
            api = human_value(item.get("api"), language, "")
            value = " ".join(part for part in [method, api] if part)
            if value and value not in apis:
                apis.append(value)
        if language == "zh":
            lines = [
                "- 系统上下文：本需求不是纯前端模板变更，运行时链路为运营人员在浏览器页面触发操作，前端调用 operate 后端接口，由后端结算/续期服务处理。",
                f"  - 前端入口：{frontend_entry or '未同步前端入口'}",
                f"  - 后端责任：{backend_entry or '未同步后端责任'}",
                f"  - 业务链路：{'; '.join(scenarios[:6]) if scenarios else '未同步业务链路'}",
                f"  - 关键接口：{', '.join(apis[:10]) if apis else '未同步接口'}",
            ]
            return "\n".join(lines)
        lines = [
            "- System context: this is not a frontend-only template change; the runtime path starts from an operator action in the browser, then calls operate backend APIs handled by settlement/renewal services.",
            f"  - Frontend entry: {frontend_entry or 'not synced'}",
            f"  - Backend owner: {backend_entry or 'not synced'}",
            f"  - Business flow: {'; '.join(scenarios[:6]) if scenarios else 'not synced'}",
            f"  - Key APIs: {', '.join(apis[:10]) if apis else 'not synced'}",
        ]
        return "\n".join(lines)
    return render_named_items(
        [architecture.get("current_architecture")],
        ["system_context", "repo_entrypoints", "upstream_downstream", "constraints"],
        "未同步到当前架构分析。" if language == "zh" else "No current architecture analysis was synced.",
        language,
    )


def render_new_service_design(architecture: dict[str, Any], language: str = "en") -> str:
    design = architecture.get("new_service_design") if isinstance(architecture.get("new_service_design"), dict) else {}
    if not design:
        return ""

    def value(key: str) -> str:
        return render_readable_value(design.get(key), language)

    def nested(key: str, fields: list[str]) -> str:
        item = design.get(key)
        if not isinstance(item, dict):
            return render_readable_value(item, language)
        parts = []
        for field in fields:
            rendered = render_readable_value(item.get(field), language)
            if rendered:
                label = DOCS_I18N.label(field, language)
                parts.append(f"{label}={rendered}")
        return "；".join(parts) if language == "zh" else "; ".join(parts)

    if language == "zh":
        rows = [
            ("为什么新起工程", value("creation_reason")),
            ("现有系统适配分析", nested("existing_system_fit_analysis", ["reuse_candidates", "rejected_existing_owners", "decision"])),
            ("职责边界", value("responsibility_boundary")),
            ("非职责边界", value("non_responsibilities")),
            ("技术栈", nested("technology_stack", ["language", "framework", "database", "build"])),
            ("工程骨架", nested("repository_bootstrap", ["repo_name", "default_branch", "scaffold", "owned_directories", "initial_files"])),
            ("模块结构", nested("module_structure", ["api", "domain", "repository", "config"])),
            ("接口契约", nested("api_contracts", ["provider", "consumers", "contracts"])),
            ("CI/CD 基线", nested("ci_cd_baseline", ["build", "test", "package", "deploy", "quality_gates"])),
            ("配置模型", nested("configuration_model", ["environments", "config_sources", "secret_handling", "restart_policy"])),
            ("部署模型", nested("deployment_model", ["artifact", "runtime", "network_entry", "dependency_order", "capacity_baseline"])),
            ("观测基线", nested("observability_baseline", ["logs", "metrics", "traces", "alerts", "dashboards"])),
            ("安全基线", nested("security_baseline", ["authn", "authz", "tenant_scope", "audit", "data_protection"])),
            ("维护 ownership", nested("maintenance_ownership", ["owning_team", "oncall", "runbook", "upgrade_policy"])),
            ("迁移/切流", nested("rollout_migration", ["strategy", "compatibility_window", "cutover", "validation"])),
            ("回滚策略", nested("rollback_strategy", ["code", "config", "data", "traffic"])),
        ]
        lines = ["### 新工程/新服务设计"]
        lines.extend(f"- {label}：{text}" for label, text in rows if text)
        return "\n".join(lines)

    rows = [
        ("Why New Service", value("creation_reason")),
        ("Existing System Fit", nested("existing_system_fit_analysis", ["reuse_candidates", "rejected_existing_owners", "decision"])),
        ("Responsibility Boundary", value("responsibility_boundary")),
        ("Non-Responsibilities", value("non_responsibilities")),
        ("Technology Stack", nested("technology_stack", ["language", "framework", "database", "build"])),
        ("Repository Bootstrap", nested("repository_bootstrap", ["repo_name", "default_branch", "scaffold", "owned_directories", "initial_files"])),
        ("Module Structure", nested("module_structure", ["api", "domain", "repository", "config"])),
        ("API Contracts", nested("api_contracts", ["provider", "consumers", "contracts"])),
        ("CI/CD Baseline", nested("ci_cd_baseline", ["build", "test", "package", "deploy", "quality_gates"])),
        ("Configuration Model", nested("configuration_model", ["environments", "config_sources", "secret_handling", "restart_policy"])),
        ("Deployment Model", nested("deployment_model", ["artifact", "runtime", "network_entry", "dependency_order", "capacity_baseline"])),
        ("Observability Baseline", nested("observability_baseline", ["logs", "metrics", "traces", "alerts", "dashboards"])),
        ("Security Baseline", nested("security_baseline", ["authn", "authz", "tenant_scope", "audit", "data_protection"])),
        ("Maintenance Ownership", nested("maintenance_ownership", ["owning_team", "oncall", "runbook", "upgrade_policy"])),
        ("Rollout / Migration", nested("rollout_migration", ["strategy", "compatibility_window", "cutover", "validation"])),
        ("Rollback Strategy", nested("rollback_strategy", ["code", "config", "data", "traffic"])),
    ]
    lines = ["### New Service / New Repository Design"]
    lines.extend(f"- {label}: {text}" for label, text in rows if text)
    return "\n".join(lines)


def render_dependency_graph_items(architecture: dict[str, Any], runtime_evidence: dict[str, Any], language: str = "en") -> str:
    runtime_evidence = runtime_evidence if isinstance(runtime_evidence, dict) else {}
    interactions = [item for item in as_list(runtime_evidence.get("interactions")) if isinstance(item, dict)]
    if interactions:
        frontend = runtime_evidence.get("frontend") if isinstance(runtime_evidence.get("frontend"), dict) else {}
        backend = runtime_evidence.get("backend") if isinstance(runtime_evidence.get("backend"), dict) else {}
        frontend_name = " / ".join(
            item
            for item in [
                human_value(frontend.get("repo"), language, ""),
                human_value(frontend.get("page"), language, ""),
            ]
            if item
        ) or ("前端" if language == "zh" else "Frontend")
        backend_name = " / ".join(
            item
            for item in [
                human_value(backend.get("repo"), language, ""),
                human_value(backend.get("service") or backend.get("controller"), language, ""),
            ]
            if item
        ) or ("后端" if language == "zh" else "Backend")
        lines = []
        seen: set[str] = set()
        for item in interactions[:10]:
            method = human_value(item.get("method"), language, "")
            api = human_value(item.get("api"), language, "")
            contract = " ".join(part for part in [method, api] if part)
            if not contract or contract in seen:
                continue
            seen.add(contract)
            if language == "zh":
                lines.append(f"- 来源：{frontend_name}\n  - 契约/API：{contract}\n  - 目标：{backend_name}\n  - 变更：按当前需求校准页面触发、接口参数、响应字段和后端处理口径")
            else:
                lines.append(f"- From: {frontend_name}\n  - Contract/API: {contract}\n  - To: {backend_name}\n  - Change: calibrate trigger, request, response, and backend handling for this requirement")
        downstream_lines = []
        downstreams = [item for item in as_list(runtime_evidence.get("downstreams")) if isinstance(item, dict)]
        for item in interactions[:10]:
            for call in [call for call in as_list(item.get("calls") or item.get("downstream_calls") or item.get("backend_calls")) if isinstance(call, dict)]:
                source = human_value(call.get("from") or call.get("source") or "backend", language, "")
                target = human_value(call.get("to") or call.get("target"), language, "")
                action = human_value(call.get("action") or call.get("request"), language, "")
                target_label = target
                for downstream in downstreams:
                    keys = [human_value(downstream.get(key), language, "") for key in ["key", "id", "name", "service", "repo"]]
                    if target in keys:
                        target_label = " / ".join(part for part in [human_value(downstream.get("name") or downstream.get("service"), language, ""), human_value(downstream.get("repo"), language, "")] if part)
                        break
                if target_label:
                    label = f"- 下游：{source} -> {target_label}；触发：{action}" if language == "zh" else f"- Downstream: {source} -> {target_label}; trigger: {action}"
                    if label not in downstream_lines:
                        downstream_lines.append(label)
        return "\n".join(lines + downstream_lines) if lines or downstream_lines else ("- 未同步到跨仓依赖图。" if language == "zh" else "- No dependency graph was synced.")
    return render_named_items(
        as_list(architecture.get("cross_repo_dependency_graph")),
        ["from", "to", "contract", "change"],
        "未同步到跨仓依赖图。" if language == "zh" else "No dependency graph was synced.",
        language,
    )


def render_runtime_api_contracts(runtime_evidence: dict[str, Any], language: str = "en") -> str:
    runtime_evidence = runtime_evidence if isinstance(runtime_evidence, dict) else {}
    contracts = [item for item in as_list(runtime_evidence.get("api_contracts")) if isinstance(item, dict)]
    if not contracts:
        interactions = [item for item in as_list(runtime_evidence.get("interactions")) if isinstance(item, dict)]
        for item in interactions:
            method = human_value(item.get("method"), language, "")
            api = human_value(item.get("api"), language, "")
            if not api:
                continue
            contracts.append(
                {
                    "name": human_value(item.get("scenario"), language, ""),
                    "method": method,
                    "path": api,
                    "request": human_value(item.get("request"), language, ""),
                    "response": human_value(item.get("response"), language, ""),
                    "error": human_value(item.get("failure"), language, ""),
                }
            )
    if not contracts:
        return ""

    def field_lines(values: Any, empty: str) -> str:
        rows = []
        for field in as_list(values):
            if isinstance(field, dict):
                name = human_value(field.get("name"), language, "")
                typ = human_value(field.get("type"), language, "")
                required = field.get("required")
                meaning = human_value(field.get("meaning") or field.get("description"), language, "")
                default = human_value(field.get("default"), language, "")
                enum = human_value(field.get("enum"), language, "")
                parts = [f"`{name}`" if name else ""]
                if typ:
                    parts.append(typ)
                if required is not None:
                    parts.append(("必填" if required else "可选") if language == "zh" else ("required" if required else "optional"))
                if default:
                    parts.append(("默认=" if language == "zh" else "default=") + default)
                if enum:
                    parts.append(("枚举=" if language == "zh" else "enum=") + enum)
                if meaning:
                    parts.append(meaning)
                value = "；".join(part for part in parts if part) if language == "zh" else "; ".join(part for part in parts if part)
                if value:
                    rows.append(f"  - {value}")
            else:
                value = human_value(field, language, "")
                if value:
                    rows.append(f"  - {value}")
        return "\n".join(rows) if rows else f"  - {empty}"

    sections = ["### API 契约设计" if language == "zh" else "### API Contract Design"]
    for index, item in enumerate(contracts[:12], start=1):
        name = human_value(item.get("name") or item.get("scenario"), language, f"API {index}")
        method = human_value(item.get("method"), language, "")
        path = human_value(item.get("path") or item.get("api"), language, "")
        controller = human_value(item.get("controller"), language, "")
        service = human_value(item.get("service"), language, "")
        caller = human_value(item.get("frontend_caller") or item.get("caller"), language, "")
        request_dto = human_value(item.get("request_dto"), language, "")
        response_vo = human_value(item.get("response_vo"), language, "")
        compatibility = human_value(item.get("compatibility"), language, "")
        notes = human_value(item.get("notes"), language, "")
        sections.append(f"\n#### {index}. {name}")
        if path:
            sections.append(f"- API：`{method} {path}`" if language == "zh" else f"- API: `{method} {path}`")
        if caller:
            sections.append(f"- 前端调用：{caller}" if language == "zh" else f"- Frontend caller: {caller}")
        if controller or service:
            owner = " -> ".join(part for part in [controller, service] if part)
            sections.append(f"- 后端承接：{owner}" if language == "zh" else f"- Backend owner: {owner}")
        if request_dto:
            sections.append(f"- 请求 DTO：`{request_dto}`" if language == "zh" else f"- Request DTO: `{request_dto}`")
        sections.append("- 入参：" if language == "zh" else "- Request fields:")
        sections.append(field_lines(item.get("request_fields") or item.get("request"), "无明确入参" if language == "zh" else "no explicit fields"))
        if response_vo:
            sections.append(f"- 响应 VO：`{response_vo}`" if language == "zh" else f"- Response VO: `{response_vo}`")
        sections.append("- 出参：" if language == "zh" else "- Response fields:")
        sections.append(field_lines(item.get("response_fields") or item.get("response"), "无明确出参" if language == "zh" else "no explicit fields"))
        errors = item.get("error_semantics") if item.get("error_semantics") is not None else item.get("error")
        sections.append("- 错误语义：" if language == "zh" else "- Error semantics:")
        sections.append(field_lines(errors, "沿用 ResultVo code/message 和页面既有错误提示" if language == "zh" else "preserve existing ResultVo code/message handling"))
        if compatibility:
            sections.append(f"- 兼容性：{compatibility}" if language == "zh" else f"- Compatibility: {compatibility}")
        if notes:
            sections.append(f"- 备注：{notes}" if language == "zh" else f"- Notes: {notes}")
    return "\n".join(sections)


def render_runtime_data_model(runtime_evidence: dict[str, Any], language: str = "en") -> str:
    runtime_evidence = runtime_evidence if isinstance(runtime_evidence, dict) else {}
    models = [
        item
        for item in as_list(
            runtime_evidence.get("data_models")
            or runtime_evidence.get("table_models")
            or runtime_evidence.get("entities")
        )
        if isinstance(item, dict)
    ]
    contracts = [item for item in as_list(runtime_evidence.get("api_contracts")) if isinstance(item, dict)]
    if not models and not contracts:
        return ""

    def field_line(field: Any) -> str:
        if isinstance(field, dict):
            name = human_value(field.get("name"), language, "")
            column = human_value(field.get("column"), language, "")
            typ = human_value(field.get("type"), language, "")
            nullable = field.get("nullable")
            meaning = human_value(field.get("meaning") or field.get("description"), language, "")
            source = human_value(field.get("source"), language, "")
            required_by = human_value(field.get("required_by"), language, "")
            parts = []
            if name:
                parts.append(f"`{name}`")
            if column and column != name:
                parts.append(f"column=`{column}`")
            if typ:
                parts.append(typ)
            if nullable is not None:
                parts.append(("可空" if nullable else "非空") if language == "zh" else ("nullable" if nullable else "not null"))
            if meaning:
                parts.append(meaning)
            if source:
                parts.append(("证据=" if language == "zh" else "evidence=") + source)
            if required_by:
                parts.append(("用于=" if language == "zh" else "used by=") + required_by)
            separator = "；" if language == "zh" else "; "
            return separator.join(parts)
        return human_value(field, language, "")

    if language == "zh":
        lines = ["### 数据模型与表结构"]
        if models:
            lines.append("- 数据模型口径：以下表/实体来自运行时证据或源码注解；未在证据中出现的字段不在文档中臆造。")
            for index, model in enumerate(models[:12], start=1):
                entity = human_value(model.get("entity") or model.get("class") or model.get("name"), language, f"模型 {index}")
                table = human_value(model.get("table"), language, "")
                owner = human_value(model.get("owner") or model.get("repo") or model.get("module"), language, "")
                operation = human_value(model.get("operation") or model.get("read_write"), language, "")
                migration = human_value(model.get("migration") or model.get("schema_change"), language, "")
                evidence = human_value(model.get("evidence"), language, "")
                lines.append(f"\n#### {index}. {entity}")
                if table:
                    lines.append(f"- 表名：`{table}`")
                if owner:
                    lines.append(f"- 责任模块：{owner}")
                if operation:
                    lines.append(f"- 读写规则：{operation}")
                fields = [field_line(field) for field in as_list(model.get("fields"))]
                fields = [field for field in fields if field]
                lines.append("- 关键字段：")
                lines.extend(f"  - {field}" for field in fields[:18]) if fields else lines.append("  - 证据未同步到字段清单，实施前必须补源码或 DDL 证据。")
                if migration:
                    lines.append(f"- 结构/迁移影响：{migration}")
                if evidence:
                    lines.append(f"- 证据来源：{evidence}")
        if contracts:
            dto_names = []
            vo_names = []
            for item in contracts:
                request_dto = human_value(item.get("request_dto"), language, "")
                response_vo = human_value(item.get("response_vo"), language, "")
                if request_dto and request_dto not in dto_names:
                    dto_names.append(request_dto)
                if response_vo and response_vo not in vo_names:
                    vo_names.append(response_vo)
            if dto_names or vo_names:
                lines.append("\n#### DTO/VO 边界")
                if dto_names:
                    lines.append(f"- 入参模型：{', '.join(f'`{item}`' for item in dto_names[:12])}")
                if vo_names:
                    lines.append(f"- 出参模型：{', '.join(f'`{item}`' for item in vo_names[:12])}")
                lines.append("- 设计约束：API 契约字段必须能映射到上述实体、查询 DTO 或响应 VO；若实现发现新增字段需要落库，必须补充 DDL、默认值、历史数据回填和回滚策略。")
        return "\n".join(lines)

    lines = ["### Data Model And Table Schema"]
    if models:
        lines.append("- Data-model scope: tables/entities below come from runtime evidence or source annotations; fields not present in evidence are not invented.")
        for index, model in enumerate(models[:12], start=1):
            entity = human_value(model.get("entity") or model.get("class") or model.get("name"), language, f"Model {index}")
            table = human_value(model.get("table"), language, "")
            owner = human_value(model.get("owner") or model.get("repo") or model.get("module"), language, "")
            operation = human_value(model.get("operation") or model.get("read_write"), language, "")
            migration = human_value(model.get("migration") or model.get("schema_change"), language, "")
            evidence = human_value(model.get("evidence"), language, "")
            lines.append(f"\n#### {index}. {entity}")
            if table:
                lines.append(f"- Table: `{table}`")
            if owner:
                lines.append(f"- Owner: {owner}")
            if operation:
                lines.append(f"- Read/write rule: {operation}")
            fields = [field_line(field) for field in as_list(model.get("fields"))]
            fields = [field for field in fields if field]
            lines.append("- Key fields:")
            lines.extend(f"  - {field}" for field in fields[:18]) if fields else lines.append("  - Field evidence was not synced; source or DDL evidence is required before implementation.")
            if migration:
                lines.append(f"- Schema/migration impact: {migration}")
            if evidence:
                lines.append(f"- Evidence: {evidence}")
    if contracts:
        dto_names = []
        vo_names = []
        for item in contracts:
            request_dto = human_value(item.get("request_dto"), language, "")
            response_vo = human_value(item.get("response_vo"), language, "")
            if request_dto and request_dto not in dto_names:
                dto_names.append(request_dto)
            if response_vo and response_vo not in vo_names:
                vo_names.append(response_vo)
        if dto_names or vo_names:
            lines.append("\n#### DTO/VO Boundary")
            if dto_names:
                lines.append(f"- Request models: {', '.join(f'`{item}`' for item in dto_names[:12])}")
            if vo_names:
                lines.append(f"- Response models: {', '.join(f'`{item}`' for item in vo_names[:12])}")
            lines.append("- Design constraint: API fields must map to these entities, query DTOs, or response VOs; if implementation requires persistence changes, add DDL, defaults, backfill, and rollback strategy.")
    return "\n".join(lines)


def render_runtime_exception_cases(runtime_evidence: dict[str, Any], language: str = "en") -> str:
    runtime_evidence = runtime_evidence if isinstance(runtime_evidence, dict) else {}
    rows: list[tuple[str, str]] = []
    for item in as_list(runtime_evidence.get("interactions")):
        if not isinstance(item, dict):
            continue
        scenario = human_value(item.get("scenario") or item.get("api"), language, "")
        failure = human_value(item.get("failure"), language, "")
        if scenario and failure:
            rows.append((scenario, failure))
    for item in as_list(runtime_evidence.get("api_contracts")):
        if not isinstance(item, dict):
            continue
        name = human_value(item.get("name") or item.get("path"), language, "")
        for error in as_list(item.get("error_semantics")):
            error_text = human_value(error, language, "")
            if name and error_text:
                rows.append((name, error_text))
    if not rows:
        return ""
    seen: set[tuple[str, str]] = set()
    unique_rows = []
    for row in rows:
        if row in seen:
            continue
        seen.add(row)
        unique_rows.append(row)
    if language == "zh":
        lines = ["### 异常与边界场景"]
        for scenario, handling in unique_rows[:16]:
            lines.append(f"- 场景：{scenario}；处理方式：{handling}")
        lines.append("- 设计约束：前端校验只能提升交互体验，后端仍需保留参数校验、状态校验和 ResultVo code/message 错误语义。")
        return "\n".join(lines)
    lines = ["### Exception And Edge Cases"]
    for scenario, handling in unique_rows[:16]:
        lines.append(f"- Scenario: {scenario}; handling: {handling}")
    lines.append("- Design constraint: frontend validation improves interaction only; backend must retain parameter/status validation and ResultVo code/message semantics.")
    return "\n".join(lines)


def render_runtime_data_access(runtime_evidence: dict[str, Any], language: str = "en") -> str:
    runtime_evidence = runtime_evidence if isinstance(runtime_evidence, dict) else {}
    models = [
        item
        for item in as_list(
            runtime_evidence.get("data_models")
            or runtime_evidence.get("table_models")
            or runtime_evidence.get("entities")
        )
        if isinstance(item, dict)
    ]
    if not models:
        return ""
    if language == "zh":
        lines = ["### 数据读写摘要"]
        for model in models[:10]:
            entity = human_value(model.get("entity") or model.get("class") or model.get("name"), language, "数据模型")
            table = human_value(model.get("table"), language, "")
            operation = human_value(model.get("operation") or model.get("read_write"), language, "")
            migration = human_value(model.get("migration") or model.get("schema_change"), language, "")
            lines.append(f"- `{table or entity}`：{operation or '读写规则未同步'}")
            if migration:
                lines.append(f"  - 结构影响：{migration}")
        return "\n".join(lines)
    lines = ["### Data Access Summary"]
    for model in models[:10]:
        entity = human_value(model.get("entity") or model.get("class") or model.get("name"), language, "data model")
        table = human_value(model.get("table"), language, "")
        operation = human_value(model.get("operation") or model.get("read_write"), language, "")
        migration = human_value(model.get("migration") or model.get("schema_change"), language, "")
        lines.append(f"- `{table or entity}`: {operation or 'read/write rule not synced'}")
        if migration:
            lines.append(f"  - Schema impact: {migration}")
    return "\n".join(lines)


def render_runtime_permission_model(runtime_evidence: dict[str, Any], language: str = "en") -> str:
    runtime_evidence = runtime_evidence if isinstance(runtime_evidence, dict) else {}
    permissions = [item for item in as_list(runtime_evidence.get("permissions")) if isinstance(item, dict)]
    frontend = runtime_evidence.get("frontend") if isinstance(runtime_evidence.get("frontend"), dict) else {}
    interactions = [item for item in as_list(runtime_evidence.get("interactions")) if isinstance(item, dict)]
    if not permissions and not frontend and not interactions:
        return ""
    if language == "zh":
        lines = ["### 权限与可见性"]
        if permissions:
            for item in permissions[:10]:
                role = human_value(item.get("role"), language, "用户")
                rule = human_value(item.get("rule"), language, "")
                negative = human_value(item.get("negative_case"), language, "")
                lines.append(f"- 角色：{role}；规则：{rule or '沿用现有菜单、按钮和后端接口权限'}")
                if negative:
                    lines.append(f"  - 反向用例：{negative}")
        else:
            page = " / ".join(
                part
                for part in [
                    human_value(frontend.get("page"), language, ""),
                    human_value(frontend.get("route"), language, ""),
                ]
                if part
            )
            triggers = [human_value(item.get("trigger"), language, "") for item in interactions if human_value(item.get("trigger"), language, "")]
            lines.append(f"- 页面边界：{page or '当前页面'} 沿用现有菜单/按钮权限。")
            lines.append(f"- 按钮边界：{'; '.join(triggers[:6]) if triggers else '当前操作'}需要保持未授权不可见或不可提交。")
            lines.append("- 后端边界：接口不得只依赖前端可见性；原因必填、续期池状态和租户范围仍需后端校验。")
            lines.append("- 反向用例：无权限账号不能访问页面入口、不能触发批量不续期/单个移出不续期，越权租户数据不能出现在查询结果中。")
        return "\n".join(lines)
    lines = ["### Permission And Visibility"]
    if permissions:
        for item in permissions[:10]:
            role = human_value(item.get("role"), language, "user")
            rule = human_value(item.get("rule"), language, "")
            negative = human_value(item.get("negative_case"), language, "")
            lines.append(f"- Role: {role}; rule: {rule or 'preserve existing menu, button, and backend API permissions'}")
            if negative:
                lines.append(f"  - Negative case: {negative}")
    else:
        page = " / ".join(
            part
            for part in [
                human_value(frontend.get("page"), language, ""),
                human_value(frontend.get("route"), language, ""),
            ]
            if part
        )
        triggers = [human_value(item.get("trigger"), language, "") for item in interactions if human_value(item.get("trigger"), language, "")]
        lines.append(f"- Page boundary: {page or 'current page'} preserves existing menu/button permissions.")
        lines.append(f"- Button boundary: {'; '.join(triggers[:6]) if triggers else 'current operations'} must remain hidden or blocked for unauthorized users.")
        lines.append("- Backend boundary: APIs must not rely on frontend visibility only; reason-required, renewal-pool status, and tenant scope checks remain backend responsibilities.")
        lines.append("- Negative case: unauthorized accounts cannot enter the page, trigger exclusion actions, or see out-of-scope tenant data.")
    return "\n".join(lines)


def render_runtime_module_design(runtime_evidence: dict[str, Any], language: str = "en") -> str:
    runtime_evidence = runtime_evidence if isinstance(runtime_evidence, dict) else {}
    contracts = [item for item in as_list(runtime_evidence.get("api_contracts")) if isinstance(item, dict)]
    if not contracts:
        return ""
    frontend = runtime_evidence.get("frontend") if isinstance(runtime_evidence.get("frontend"), dict) else {}
    backend = runtime_evidence.get("backend") if isinstance(runtime_evidence.get("backend"), dict) else {}
    frontend_entry = " / ".join(
        item
        for item in [
            human_value(frontend.get("repo"), language, ""),
            human_value(frontend.get("page"), language, ""),
            human_value(frontend.get("route"), language, ""),
        ]
        if item
    )
    backend_entry = " / ".join(
        item
        for item in [
            human_value(backend.get("repo"), language, ""),
            human_value(backend.get("service") or backend.get("controller"), language, ""),
        ]
        if item
    )
    api_names = [human_value(item.get("name"), language, "") for item in contracts if human_value(item.get("name"), language, "")]
    if language == "zh":
        lines = ["### 模块职责划分"]
        lines.append(f"- 前端模块：{frontend_entry or '未同步前端入口'}")
        lines.append("  - 职责：承载运营人员在设备置换结算页面的查询、试算、生成续期结算单、批量不续期和单个移出不续期操作。")
        lines.append("  - 输入：页面筛选条件、分页参数、设备号、原因码和原因说明。")
        lines.append("  - 输出：列表刷新、汇总刷新、弹窗关闭、成功/失败提示和结算单列表切换。")
        lines.append(f"- 后端模块：{backend_entry or '未同步后端责任'}")
        lines.append(f"  - 职责：承接 {', '.join(api_names[:8])} 等接口，统一处理续期池、结算单、试算快照和订单履约透视规则。")
        lines.append("  - 输入：ReplacementSettlementQueryDto、ReplacementSettlementOrderQueryDto、RenewPoolManualExcludeDto 等请求 DTO。")
        lines.append("  - 输出：ReplacementSettlementItemVo、ReplacementSettlementOrderVo、ReplacementSettlementSummaryVo、ReplacementSettlementTrialVo 或 ResultVo<String>。")
        lines.append("  - 耦合控制：前端只组装筛选和交互状态，金额、续期池状态、结算单生成和原因落库由后端作为事实来源。")
        return "\n".join(lines)
    lines = ["### Module Responsibility Split"]
    lines.append(f"- Frontend module: {frontend_entry or 'not synced'}")
    lines.append("  - Responsibility: page query, trial, renewal order creation, batch exclusion, and single exclusion interactions.")
    lines.append("  - Input: filters, pagination, device numbers, reason code, and reason text.")
    lines.append("  - Output: table/summary refresh, dialog close, success/error messages, and order-list navigation.")
    lines.append(f"- Backend module: {backend_entry or 'not synced'}")
    lines.append(f"  - Responsibility: own {', '.join(api_names[:8])} and enforce renewal pool, settlement order, trial snapshot, and order-pivot rules.")
    lines.append("  - Input: request DTOs such as ReplacementSettlementQueryDto, ReplacementSettlementOrderQueryDto, and RenewPoolManualExcludeDto.")
    lines.append("  - Output: settlement item/order/summary/trial VOs or ResultVo<String>.")
    lines.append("  - Coupling control: frontend owns interaction state; backend remains the source of truth for amount, status, order creation, and exclusion persistence.")
    return "\n".join(lines)


def render_runtime_ui_impact(runtime_evidence: dict[str, Any], language: str = "en") -> str:
    runtime_evidence = runtime_evidence if isinstance(runtime_evidence, dict) else {}
    frontend = runtime_evidence.get("frontend") if isinstance(runtime_evidence.get("frontend"), dict) else {}
    interactions = [item for item in as_list(runtime_evidence.get("interactions")) if isinstance(item, dict)]
    if not frontend and not interactions:
        return ""
    page = " / ".join(
        item
        for item in [
            human_value(frontend.get("page"), language, ""),
            human_value(frontend.get("route"), language, ""),
        ]
        if item
    )
    triggers = [human_value(item.get("trigger"), language, "") for item in interactions if human_value(item.get("trigger"), language, "")]
    if language == "zh":
        lines = ["### 页面与交互影响"]
        lines.append(f"- 页面/路由：{page or '未同步页面'}")
        lines.append(f"- 用户入口：{human_value(frontend.get('entry_menu_or_button'), language, '') or '未同步入口'}")
        lines.append(f"- 触发动作：{'；'.join(triggers[:8]) if triggers else '未同步触发动作'}")
        lines.append("- 权限可见性：沿用现有菜单/按钮权限；若新增按钮或导入入口，需要补充未授权不可见或不可提交的反向用例。")
        lines.append("- 验收证据：需要覆盖筛选后试算、生成续期结算单、批量不续期、单个移出不续期、错误提示和刷新结果。")
        return "\n".join(lines)
    lines = ["### UI Interaction Impact"]
    lines.append(f"- Page/route: {page or 'not synced'}")
    lines.append(f"- User entry: {human_value(frontend.get('entry_menu_or_button'), language, '') or 'not synced'}")
    lines.append(f"- Triggers: {'; '.join(triggers[:8]) if triggers else 'not synced'}")
    lines.append("- Permission visibility: preserve existing menu/button permissions; new entries need negative authorization evidence.")
    lines.append("- Acceptance evidence: cover filtered trial, renewal order creation, batch exclusion, single exclusion, error messages, and refresh result.")
    return "\n".join(lines)


def runtime_interaction_id(item: dict[str, Any], fallback_index: int) -> str:
    scenario = human_value(item.get("scenario") or item.get("requirement_breakdown_id"), "en", "")
    matched = re.search(r"\b(BRK-\d+)\b", scenario)
    return matched.group(1) if matched else f"BRK-{fallback_index}"


def runtime_interaction_acceptance_ids(item: dict[str, Any], language: str = "en") -> list[str]:
    ids: list[str] = []
    for key in ["acceptance_ids", "acceptance_id", "ac_ids", "ac_id", "acceptance_refs"]:
        for value in as_list(item.get(key)):
            rendered = human_value(value, language, "")
            if rendered and rendered not in ids:
                ids.append(rendered)
    return ids


def runtime_text_score(left: str, right: str) -> int:
    left_tokens = set(re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", left.lower()))
    right_tokens = set(re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", right.lower()))
    stop = set("的一是在和与或及时后前中按可不")
    left_tokens = {item for item in left_tokens if item not in stop and len(item.strip()) > 0}
    right_tokens = {item for item in right_tokens if item not in stop and len(item.strip()) > 0}
    return len(left_tokens & right_tokens)


def infer_runtime_acceptance_maps(
    spec: dict[str, Any],
    grouped: dict[str, list[dict[str, Any]]],
    language: str = "en",
) -> tuple[dict[str, list[str]], dict[str, str]]:
    acceptance = [item for item in as_list(spec.get("acceptance_criteria")) if isinstance(item, dict)]
    ac_ids = [human_value(item.get("id"), language, "") for item in acceptance if human_value(item.get("id"), language, "")]
    brk_to_acs: dict[str, list[str]] = {brk: [] for brk in grouped}
    ac_to_brk: dict[str, str] = {}

    for brk, items in grouped.items():
        for item in items:
            for ac_id in runtime_interaction_acceptance_ids(item, language):
                if ac_id and ac_id not in brk_to_acs[brk]:
                    brk_to_acs[brk].append(ac_id)
                    ac_to_brk.setdefault(ac_id, brk)

    for ac_id in ac_ids:
        if ac_id in ac_to_brk:
            continue
        ac_match = re.search(r"(\d+)", ac_id)
        if ac_match:
            numeric_brk = f"BRK-{ac_match.group(1)}"
            if numeric_brk in grouped:
                brk_to_acs[numeric_brk].append(ac_id)
                ac_to_brk[ac_id] = numeric_brk
                continue

        ac_item = next((item for item in acceptance if human_value(item.get("id"), language, "") == ac_id), {})
        ac_text = human_value(ac_item.get("criteria") or ac_item.get("summary"), language, "")
        best_brk = ""
        best_score = 0
        for brk, items in grouped.items():
            brk_text = " ".join(
                human_value(value, language, "")
                for item in items
                for value in [
                    item.get("scenario"),
                    item.get("trigger"),
                    item.get("request"),
                    item.get("response"),
                    item.get("backend_action"),
                    item.get("failure"),
                ]
            )
            score = runtime_text_score(ac_text, brk_text)
            if score > best_score:
                best_score = score
                best_brk = brk
        if best_brk and best_score >= 2:
            brk_to_acs[best_brk].append(ac_id)
            ac_to_brk[ac_id] = best_brk

    for brk in list(brk_to_acs):
        deduped: list[str] = []
        for ac_id in brk_to_acs[brk]:
            if ac_id not in deduped:
                deduped.append(ac_id)
        brk_to_acs[brk] = deduped
    return brk_to_acs, ac_to_brk


def runtime_item_api(item: dict[str, Any], language: str = "en") -> str:
    return " ".join(
        part
        for part in [
            human_value(item.get("method"), language, ""),
            human_value(item.get("api"), language, ""),
        ]
        if part
    )


def runtime_contract_by_api(runtime_evidence: dict[str, Any], language: str = "en") -> dict[str, dict[str, Any]]:
    contracts: dict[str, dict[str, Any]] = {}
    for item in as_list(runtime_evidence.get("api_contracts")):
        if not isinstance(item, dict):
            continue
        method = human_value(item.get("method"), language, "")
        path = human_value(item.get("path") or item.get("api"), language, "")
        api = " ".join(part for part in [method, path] if part)
        if api:
            contracts[api] = item
    return contracts


def runtime_model_field_names(models: list[dict[str, Any]], language: str = "en") -> list[str]:
    names: list[str] = []
    for model in models:
        for field in as_list(model.get("fields")):
            if isinstance(field, dict):
                name = human_value(field.get("name") or field.get("column"), language, "")
            else:
                name = human_value(field, language, "")
            if name and name not in names:
                names.append(name)
    return names


def runtime_gap_sentence(item: dict[str, Any], ac_ids: list[str], language: str = "en") -> str:
    explicit = human_value(item.get("current_gap") or item.get("gap") or item.get("problem"), language, "")
    if explicit:
        return explicit
    request = human_value(item.get("request"), language, "")
    response = human_value(item.get("response"), language, "")
    failure = human_value(item.get("failure"), language, "")
    ac_text = ", ".join(ac_ids) if ac_ids else ("mapped acceptance criteria" if language != "zh" else "已映射验收项")
    if language == "zh":
        if request and response:
            return f"现有链路必须证明请求口径 `{request}` 能产生 `{response}`，否则无法满足 {ac_text}。"
        if failure:
            return f"现有链路必须明确 `{failure}` 的前端拦截与后端兜底，否则无法满足 {ac_text}。"
        return f"当前证据只定位到交互入口，仍需补充该子域的现状差距证据以支撑 {ac_text}。"
    if request and response:
        return f"The current path must prove that `{request}` produces `{response}`; otherwise it does not satisfy {ac_text}."
    if failure:
        return f"The current path must define frontend and backend handling for `{failure}` to satisfy {ac_text}."
    return f"Evidence identifies the entrypoint, but the current-state gap for this slice still needs source-backed detail for {ac_text}."


def runtime_frontend_action(item: dict[str, Any], frontend_file: str, api_text: str, language: str = "en") -> str:
    functions = [
        human_value(value, language, "")
        for value in as_list(item.get("frontend_functions") or item.get("frontend_methods") or item.get("frontend_handlers"))
        if human_value(value, language, "")
    ]
    request = human_value(item.get("request"), language, "")
    response = human_value(item.get("response"), language, "")
    bindings = [
        human_value(value, language, "")
        for value in as_list(item.get("field_bindings") or item.get("frontend_field_bindings") or item.get("ui_bindings"))
        if human_value(value, language, "")
    ]
    validation = [
        human_value(value, language, "")
        for value in as_list(item.get("frontend_validation") or item.get("validation_rules"))
        if human_value(value, language, "")
    ]
    if language == "zh":
        target = f"`{frontend_file}`" if frontend_file else "前端入口"
        parts = [f"在 {target} 处理用户动作"]
        if functions:
            parts.append("涉及函数：" + "、".join(f"`{name}`" for name in functions[:8]))
        if bindings:
            parts.append("字段/控件绑定：" + "；".join(bindings[:6]))
        if request:
            parts.append(f"按 `{request}` 组装请求参数")
        if validation:
            parts.append("前端校验：" + "；".join(validation[:4]))
        parts.append(f"调用接口：{api_text}")
        if response:
            parts.append(f"成功后按 `{response}` 刷新页面状态")
        return "；".join(parts) + "。"
    target = f"`{frontend_file}`" if frontend_file else "frontend entry"
    parts = [f"Update {target} for the user action"]
    if functions:
        parts.append("functions: " + ", ".join(f"`{name}`" for name in functions[:8]))
    if bindings:
        parts.append("field/control binding: " + "; ".join(bindings[:6]))
    if request:
        parts.append(f"build request as `{request}`")
    if validation:
        parts.append("frontend validation: " + "; ".join(validation[:4]))
    parts.append(f"call {api_text}")
    if response:
        parts.append(f"refresh UI as `{response}`")
    return "; ".join(parts) + "."


def runtime_backend_action(item: dict[str, Any], backend_owner: str, backend_actions: list[str], language: str = "en") -> str:
    methods = [
        human_value(value, language, "")
        for value in as_list(item.get("backend_methods") or item.get("service_methods") or item.get("controller_methods"))
        if human_value(value, language, "")
    ]
    rules = [
        human_value(value, language, "")
        for value in as_list(item.get("backend_rules") or item.get("query_rules") or item.get("write_rules"))
        if human_value(value, language, "")
    ]
    if language == "zh":
        parts = [f"由 `{backend_owner or '后端责任模块'}` 承接"]
        if methods:
            parts.append("涉及方法：" + "、".join(f"`{name}`" for name in methods[:8]))
        parts.append("关键处理：" + ("；".join(backend_actions) if backend_actions else "按接口契约处理业务规则"))
        if rules:
            parts.append("实现规则：" + "；".join(rules[:6]))
        return "；".join(parts) + "。"
    parts = [f"`{backend_owner or 'backend owner'}` handles the slice"]
    if methods:
        parts.append("methods: " + ", ".join(f"`{name}`" for name in methods[:8]))
    parts.append("; ".join(backend_actions) if backend_actions else "business rules per API contract")
    if rules:
        parts.append("rules: " + "; ".join(rules[:6]))
    return "; ".join(parts) + "."


def runtime_data_impact_sentence(models: list[dict[str, Any]], item: dict[str, Any], language: str = "en") -> str:
    item_tables = [
        human_value(value, language, "")
        for value in as_list(item.get("tables") or item.get("data_tables") or item.get("affected_tables"))
        if human_value(value, language, "")
    ]
    model_tables = [human_value(model.get("table"), language, "") for model in models if human_value(model.get("table"), language, "")]
    tables = item_tables or model_tables[:6]
    data_ops = [
        human_value(value, language, "")
        for value in as_list(item.get("data_operations") or item.get("data_impact") or item.get("persistence"))
        if human_value(value, language, "")
    ]
    field_names = runtime_model_field_names(models, language)[:8]
    if language == "zh":
        table_text = ", ".join(f"`{name}`" for name in tables) if tables else "未同步表结构"
        op_text = "；".join(data_ops) if data_ops else "按数据模型章节的字段规则读写"
        field_text = "；关键字段：" + "、".join(f"`{name}`" for name in field_names) if field_names else ""
        return f"涉及表 {table_text}；{op_text}{field_text}；不在无证据情况下新增物理字段。"
    table_text = ", ".join(f"`{name}`" for name in tables) if tables else "not synced"
    op_text = "; ".join(data_ops) if data_ops else "read/write per the data-model section"
    field_text = "; key fields: " + ", ".join(f"`{name}`" for name in field_names) if field_names else ""
    return f"Tables {table_text}; {op_text}{field_text}; do not add physical fields without evidence."


def runtime_acceptance_assertion(criteria: str, related: list[dict[str, Any]], models: list[dict[str, Any]], language: str = "en") -> str:
    text_value = criteria.lower()
    if "npm run build" in text_value or "mvn " in text_value or "compile" in text_value:
        if language == "zh":
            commands = re.findall(r"`([^`]*(?:npm run build[^`]*|mvn [^`]*)[^`]*)`", criteria)
            command_text = "、".join(f"`{command}`" for command in commands) if commands else "`npm run build:test`、`mvn -pl operate-provider -DskipTests compile`"
            return f"执行并记录构建命令 {command_text} 的退出码和关键日志；失败时记录环境原因、失败阶段和可复现命令"
        commands = re.findall(r"`([^`]*(?:npm run build[^`]*|mvn [^`]*)[^`]*)`", criteria)
        command_text = ", ".join(f"`{command}`" for command in commands) if commands else "`npm run build:test`, `mvn -pl operate-provider -DskipTests compile`"
        return f"run {command_text}, record exit code and key logs; on failure record environment cause, failed phase, and reproduction command"
    explicit = [
        human_value(value, language, "")
        for flow in related
        for value in as_list(flow.get("assertions") or flow.get("acceptance_assertions") or flow.get("test_assertions"))
        if human_value(value, language, "")
    ]
    if explicit:
        return "；".join(dict.fromkeys(explicit)) if language == "zh" else "; ".join(dict.fromkeys(explicit))
    field_names = runtime_model_field_names(models, language)
    fields = [name for name in field_names if name and (name.lower() in text_value or name.replace("_", "").lower() in text_value)]
    api_text = "；".join(runtime_item_api(flow, language) for flow in related if runtime_item_api(flow, language))
    failure_text = "；".join(human_value(flow.get("failure"), language, "") for flow in related if human_value(flow.get("failure"), language, ""))
    request_text = "；".join(human_value(flow.get("request"), language, "") for flow in related if human_value(flow.get("request"), language, ""))
    response_text = "；".join(human_value(flow.get("response"), language, "") for flow in related if human_value(flow.get("response"), language, ""))
    assertions: list[str] = []
    if language == "zh":
        if api_text:
            assertions.append(f"接口 `{api_text}` 按测试动作被调用")
        if request_text:
            assertions.append(f"请求参数包含并生效：{request_text}")
        if response_text:
            assertions.append(f"响应/页面结果符合：{response_text}")
        if fields:
            assertions.append("关键字段可核对：" + "、".join(f"`{field}`" for field in fields[:6]))
        if any(term in criteria for term in ["不展示", "隐藏", "不返回", "排除"]):
            assertions.append("结果集中不得出现被排除状态或数据")
        if any(term in criteria for term in ["排序", "升序", "降序"]):
            assertions.append("返回列表顺序与验收要求一致")
        if any(term in criteria for term in ["必填", "不可提交", "未选择", "未填写"]):
            assertions.append("前端阻止无效提交，后端绕过前端调用时仍返回失败")
        if any(term in criteria for term in ["写入", "落库", "记录"]):
            assertions.append("数据库字段写入后可按主键或业务键查询核对")
        if failure_text:
            assertions.append(f"异常路径符合边界：{failure_text}")
        return "；".join(dict.fromkeys(assertions[:7])) or "需补充该验收项的具体断言，不能只写页面/API/落库均满足。"
    if api_text:
        assertions.append(f"`{api_text}` is called")
    if request_text:
        assertions.append(f"request parameters apply: {request_text}")
    if response_text:
        assertions.append(f"response/UI result matches: {response_text}")
    if fields:
        assertions.append("verify fields " + ", ".join(f"`{field}`" for field in fields[:6]))
    if any(term in text_value for term in ["hide", "exclude", "not show", "not return"]):
        assertions.append("excluded statuses or data are absent")
    if "sort" in text_value or "ascending" in text_value or "descending" in text_value:
        assertions.append("ordering matches the acceptance requirement")
    if any(term in text_value for term in ["required", "cannot submit", "must fill"]):
        assertions.append("frontend blocks invalid submit and backend rejects bypass calls")
    if failure_text:
        assertions.append(f"exception path matches: {failure_text}")
    return "; ".join(dict.fromkeys(assertions[:7])) or "add concrete assertions for this AC; generic UI/API/persistence proof is not enough"


def runtime_related_for_acceptance(related: list[dict[str, Any]], ac_id: str, language: str = "en") -> list[dict[str, Any]]:
    matched = [flow for flow in related if ac_id in runtime_interaction_acceptance_ids(flow, language)]
    return matched or related


def render_runtime_subrequirement_design(spec: dict[str, Any], runtime_evidence: dict[str, Any], language: str = "en") -> str:
    runtime_evidence = runtime_evidence if isinstance(runtime_evidence, dict) else {}
    interactions = [item for item in as_list(runtime_evidence.get("interactions")) if isinstance(item, dict)]
    if not interactions:
        return ""
    frontend = runtime_evidence.get("frontend") if isinstance(runtime_evidence.get("frontend"), dict) else {}
    backend = runtime_evidence.get("backend") if isinstance(runtime_evidence.get("backend"), dict) else {}
    models = [item for item in as_list(runtime_evidence.get("data_models")) if isinstance(item, dict)]
    acceptance = [item for item in as_list(spec.get("acceptance_criteria")) if isinstance(item, dict)]
    ac_by_id = {human_value(item.get("id"), language, ""): human_value(item.get("criteria"), language, "") for item in acceptance}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for index, item in enumerate(interactions, start=1):
        grouped.setdefault(runtime_interaction_id(item, index), []).append(item)
    ac_map, _ = infer_runtime_acceptance_maps(spec, grouped, language)
    frontend_entry = " / ".join(
        part
        for part in [
            human_value(frontend.get("repo"), language, ""),
            human_value(frontend.get("page"), language, ""),
            human_value(frontend.get("route"), language, ""),
        ]
        if part
    )
    frontend_file = human_value(frontend.get("source_file") or frontend.get("file"), language, "")
    backend_owner = " / ".join(
        part
        for part in [
            human_value(backend.get("repo"), language, ""),
            human_value(backend.get("controller"), language, ""),
            human_value(backend.get("service"), language, ""),
        ]
        if part
    )
    table_names = [human_value(item.get("table"), language, "") for item in models if human_value(item.get("table"), language, "")]
    contract_map = runtime_contract_by_api(runtime_evidence, language)
    if language == "zh":
        lines = ["### 子需求落地设计"]
        lines.append("- 口径：本节按业务子域组织，每个子域同时回答现状、差距、改动、实现方式和验收证明。")
        for brk_id, items in grouped.items():
            scenario_names = [human_value(item.get("scenario"), language, "") for item in items if human_value(item.get("scenario"), language, "")]
            title = scenario_names[0] if scenario_names else brk_id
            title = re.sub(rf"^{re.escape(brk_id)}\s*", "", title).strip() or brk_id
            apis = []
            triggers = []
            backend_actions = []
            failures = []
            responses = []
            for item in items:
                api = " ".join(part for part in [human_value(item.get("method"), language, ""), human_value(item.get("api"), language, "")] if part)
                if api and api not in apis:
                    apis.append(api)
                trigger = human_value(item.get("trigger"), language, "")
                if trigger and trigger not in triggers:
                    triggers.append(trigger)
                action = human_value(item.get("backend_action"), language, "")
                if action and action not in backend_actions:
                    backend_actions.append(action)
                failure = human_value(item.get("failure"), language, "")
                if failure and failure not in failures:
                    failures.append(failure)
                response = human_value(item.get("response"), language, "")
                if response and response not in responses:
                    responses.append(response)
            ac_ids = ac_map.get(brk_id, [])
            ac_text = "；".join(f"{ac_id}: {ac_by_id.get(ac_id, '')}" for ac_id in ac_ids if ac_by_id.get(ac_id))
            representative = items[0]
            api_text = ", ".join(f"`{api}`" for api in apis) if apis else "未同步接口"
            contract_names = []
            for api in apis:
                contract = contract_map.get(api, {})
                name = human_value(contract.get("name"), language, "")
                request_dto = human_value(contract.get("request_dto"), language, "")
                response_vo = human_value(contract.get("response_vo"), language, "")
                detail = " / ".join(part for part in [name, request_dto, response_vo] if part)
                if detail:
                    contract_names.append(detail)
            assertions = [
                runtime_acceptance_assertion(ac_by_id.get(ac_id, ""), runtime_related_for_acceptance(items, ac_id, language), models, language)
                for ac_id in ac_ids
                if ac_by_id.get(ac_id)
            ]
            lines.append(f"\n#### {brk_id} {title}")
            lines.append(f"- 当前现状：运营人员在 `{frontend_entry or '前端页面'}` 触发：{'；'.join(triggers) or '当前操作'}。")
            lines.append(f"- 现状差距：{runtime_gap_sentence(representative, ac_ids, language)}")
            lines.append(f"- 目标调整：{'；'.join(responses) or title}。")
            lines.append(f"- 前端做法：{runtime_frontend_action(representative, frontend_file, api_text, language)}")
            lines.append(f"- 后端做法：{runtime_backend_action(representative, backend_owner, backend_actions, language)}")
            if contract_names:
                lines.append(f"- 契约绑定：{'；'.join(contract_names[:4])}。")
            lines.append(f"- 数据影响：{runtime_data_impact_sentence(models, representative, language)}")
            lines.append(f"- 异常边界：{'；'.join(failures) or '保留既有错误语义和页面提示'}。")
            lines.append(f"- 验收证明：{ac_text or '需补充验收标准映射'}")
            if assertions:
                lines.append(f"- 关键断言：{'；'.join(assertions)}")
        return "\n".join(lines)
    lines = ["### Sub-Requirement Implementation Design"]
    lines.append("- Scope: each business slice states current behavior, gap, change, implementation, and acceptance proof.")
    for brk_id, items in grouped.items():
        title = human_value(items[0].get("scenario"), language, brk_id)
        title = re.sub(rf"^{re.escape(brk_id)}\s*", "", title).strip() or brk_id
        apis = []
        triggers = []
        backend_actions = []
        failures = []
        responses = []
        for item in items:
            api = " ".join(part for part in [human_value(item.get("method"), language, ""), human_value(item.get("api"), language, "")] if part)
            if api and api not in apis:
                apis.append(api)
            trigger = human_value(item.get("trigger"), language, "")
            if trigger and trigger not in triggers:
                triggers.append(trigger)
            action = human_value(item.get("backend_action"), language, "")
            if action and action not in backend_actions:
                backend_actions.append(action)
            failure = human_value(item.get("failure"), language, "")
            if failure and failure not in failures:
                failures.append(failure)
            response = human_value(item.get("response"), language, "")
            if response and response not in responses:
                responses.append(response)
        ac_ids = ac_map.get(brk_id, [])
        ac_text = "; ".join(f"{ac_id}: {ac_by_id.get(ac_id, '')}" for ac_id in ac_ids if ac_by_id.get(ac_id))
        representative = items[0]
        api_text = ", ".join(f"`{api}`" for api in apis) if apis else "synced APIs"
        contract_names = []
        for api in apis:
            contract = contract_map.get(api, {})
            name = human_value(contract.get("name"), language, "")
            request_dto = human_value(contract.get("request_dto"), language, "")
            response_vo = human_value(contract.get("response_vo"), language, "")
            detail = " / ".join(part for part in [name, request_dto, response_vo] if part)
            if detail:
                contract_names.append(detail)
        assertions = [
            runtime_acceptance_assertion(ac_by_id.get(ac_id, ""), runtime_related_for_acceptance(items, ac_id, language), models, language)
            for ac_id in ac_ids
            if ac_by_id.get(ac_id)
        ]
        lines.append(f"\n#### {brk_id} {title}")
        lines.append(f"- Current behavior: user triggers {'; '.join(triggers) or 'current operation'} from `{frontend_entry or 'frontend entry'}`.")
        lines.append(f"- Gap: {runtime_gap_sentence(representative, ac_ids, language)}")
        lines.append(f"- Target change: {'; '.join(responses) or title}.")
        lines.append(f"- Frontend approach: {runtime_frontend_action(representative, frontend_file, api_text, language)}")
        lines.append(f"- Backend approach: {runtime_backend_action(representative, backend_owner, backend_actions, language)}")
        if contract_names:
            lines.append(f"- Contract binding: {'; '.join(contract_names[:4])}.")
        lines.append(f"- Data impact: {runtime_data_impact_sentence(models, representative, language)}")
        lines.append(f"- Exception boundary: {'; '.join(failures) or 'preserve existing error semantics'}.")
        lines.append(f"- Acceptance proof: {ac_text or 'acceptance mapping required'}")
        if assertions:
            lines.append(f"- Key assertions: {'; '.join(assertions)}")
    return "\n".join(lines)


def render_runtime_process_flows(runtime_evidence: dict[str, Any], language: str = "en") -> str:
    runtime_evidence = runtime_evidence if isinstance(runtime_evidence, dict) else {}
    interactions = [item for item in as_list(runtime_evidence.get("interactions")) if isinstance(item, dict)]
    if not interactions:
        return ""
    if language == "zh":
        lines = ["### 真实业务流程"]
        for index, item in enumerate(interactions[:10], start=1):
            lines.append(f"\n#### {index}. {human_value(item.get('scenario'), language, f'流程 {index}')}")
            lines.append(f"- 用户动作：{human_value(item.get('trigger'), language, '未同步触发动作')}")
            api = " ".join(part for part in [human_value(item.get("method"), language, ""), human_value(item.get("api"), language, "")] if part)
            lines.append(f"- 前端请求：{api or '未同步接口'}；{human_value(item.get('request'), language, '未同步请求参数')}")
            lines.append(f"- 后端处理：{human_value(item.get('backend_action'), language, '未同步后端处理')}")
            lines.append(f"- 正常结果：{human_value(item.get('response'), language, '页面刷新或提示成功')}")
            lines.append(f"- 异常结果：{human_value(item.get('failure'), language, '保留既有错误处理')}")
        return "\n".join(lines)
    lines = ["### Real Business Flow"]
    for index, item in enumerate(interactions[:10], start=1):
        api = " ".join(part for part in [human_value(item.get("method"), language, ""), human_value(item.get("api"), language, "")] if part)
        lines.append(f"\n#### {index}. {human_value(item.get('scenario'), language, f'Flow {index}')}")
        lines.append(f"- User action: {human_value(item.get('trigger'), language, 'not synced')}")
        lines.append(f"- Frontend request: {api or 'not synced'}; {human_value(item.get('request'), language, 'request not synced')}")
        lines.append(f"- Backend handling: {human_value(item.get('backend_action'), language, 'not synced')}")
        lines.append(f"- Normal result: {human_value(item.get('response'), language, 'refresh or success message')}")
        lines.append(f"- Exception result: {human_value(item.get('failure'), language, 'preserve existing error handling')}")
    return "\n".join(lines)


def render_runtime_process_mermaid(runtime_evidence: dict[str, Any], language: str = "en") -> str:
    runtime_evidence = runtime_evidence if isinstance(runtime_evidence, dict) else {}
    interactions = [item for item in as_list(runtime_evidence.get("interactions")) if isinstance(item, dict)]
    if not interactions:
        return ""
    lines = [
        "```mermaid",
        "flowchart TD",
        "  classDef actor fill:#eff6ff,stroke:#2563eb,color:#172554,stroke-width:1px;",
        "  classDef api fill:#f8fafc,stroke:#64748b,color:#0f172a,stroke-width:1px;",
        "  classDef backend fill:#ecfdf5,stroke:#16a34a,color:#14532d,stroke-width:1px;",
        "  classDef failure fill:#fff7ed,stroke:#f97316,color:#7c2d12,stroke-width:1px;",
    ]
    for index, item in enumerate(interactions[:8], start=1):
        trigger = mermaid_flow_label(human_value(item.get("trigger"), language, ""), language, 42)
        api = mermaid_flow_label(" ".join(part for part in [human_value(item.get("method"), language, ""), human_value(item.get("api"), language, "")] if part), language, 58)
        action = mermaid_flow_label(human_value(item.get("backend_action"), language, ""), language, 58)
        response = mermaid_flow_label(human_value(item.get("response"), language, ""), language, 44)
        failure = mermaid_flow_label(human_value(item.get("failure"), language, ""), language, 44)
        lines.append(f'  U{index}["{trigger or ("用户操作" if language == "zh" else "User action")}"]:::actor')
        lines.append(f'  A{index}["{api or ("调用接口" if language == "zh" else "API call")}"]:::api')
        lines.append(f'  B{index}["{action or ("后端处理" if language == "zh" else "Backend handling")}"]:::backend')
        lines.append(f'  R{index}["{response or ("刷新页面" if language == "zh" else "Refresh UI")}"]:::actor')
        lines.append(f"  U{index} --> A{index} --> B{index} --> R{index}")
        if failure:
            lines.append(f'  E{index}["{failure}"]:::failure')
            lines.append(f"  B{index} -.-> E{index}")
    lines.append("```")
    return "\n".join(lines)


def render_runtime_acceptance_proof(spec: dict[str, Any], runtime_evidence: dict[str, Any], language: str = "en") -> str:
    runtime_evidence = runtime_evidence if isinstance(runtime_evidence, dict) else {}
    acceptance = [item for item in as_list(spec.get("acceptance_criteria")) if isinstance(item, dict)]
    interactions = [item for item in as_list(runtime_evidence.get("interactions")) if isinstance(item, dict)]
    models = [item for item in as_list(runtime_evidence.get("data_models")) if isinstance(item, dict)]
    if not acceptance:
        return ""
    scenario_by_brk: dict[str, list[dict[str, Any]]] = {}
    for index, item in enumerate(interactions, start=1):
        scenario_by_brk.setdefault(runtime_interaction_id(item, index), []).append(item)
    _, ac_to_brk = infer_runtime_acceptance_maps(spec, scenario_by_brk, language)
    if language == "zh":
        lines = ["| 验收项 | 对应子域 | 需要证明什么 | 测试输入/动作 | 断言 |", "|---|---|---|---|---|"]
        for item in acceptance:
            ac_id = human_value(item.get("id"), language, "")
            criteria = clean_acceptance_text(item.get("criteria"), language)
            brk = ac_to_brk.get(ac_id, "")
            related = runtime_related_for_acceptance(scenario_by_brk.get(brk, []), ac_id, language)
            triggers = "；".join(human_value(flow.get("trigger"), language, "") for flow in related if human_value(flow.get("trigger"), language, "")) or "按验收场景操作"
            apis = "；".join(
                " ".join(part for part in [human_value(flow.get("method"), language, ""), human_value(flow.get("api"), language, "")] if part)
                for flow in related
            ) or "按对应接口验证"
            assertion = runtime_acceptance_assertion(criteria, related, models, language)
            lines.append(f"| `{ac_id}` | `{brk or '未绑定'}` | {criteria} | {triggers}；接口：{apis} | {assertion} |")
        return "\n".join(lines)
    lines = ["| AC | Slice | Proof Target | Input / Action | Assertions |", "|---|---|---|---|---|"]
    for item in acceptance:
        ac_id = human_value(item.get("id"), language, "")
        criteria = clean_acceptance_text(item.get("criteria"), language)
        brk = ac_to_brk.get(ac_id, "")
        related = runtime_related_for_acceptance(scenario_by_brk.get(brk, []), ac_id, language)
        triggers = "; ".join(human_value(flow.get("trigger"), language, "") for flow in related if human_value(flow.get("trigger"), language, "")) or "run acceptance scenario"
        apis = "; ".join(
            " ".join(part for part in [human_value(flow.get("method"), language, ""), human_value(flow.get("api"), language, "")] if part)
            for flow in related
        ) or "verify mapped API"
        assertion = runtime_acceptance_assertion(criteria, related, models, language)
        lines.append(f"| `{ac_id}` | `{brk or 'unmapped'}` | {criteria} | {triggers}; API: {apis} | {assertion} |")
    return "\n".join(lines)


def render_runtime_entrypoint_confidence(runtime_evidence: dict[str, Any], language: str = "en") -> str:
    runtime_evidence = runtime_evidence if isinstance(runtime_evidence, dict) else {}
    if not runtime_evidence.get("interactions"):
        return ""
    frontend = runtime_evidence.get("frontend") if isinstance(runtime_evidence.get("frontend"), dict) else {}
    backend = runtime_evidence.get("backend") if isinstance(runtime_evidence.get("backend"), dict) else {}
    frontend_file = human_value(frontend.get("source_file") or frontend.get("file"), language, "")
    backend_files = [human_value(item, language, "") for item in as_list(backend.get("source_files") or backend.get("files")) if human_value(item, language, "")]
    frontend_entry = " / ".join(
        item
        for item in [
            human_value(frontend.get("repo"), language, ""),
            human_value(frontend.get("page"), language, ""),
            human_value(frontend.get("route"), language, ""),
        ]
        if item
    )
    backend_entry = " / ".join(
        item
        for item in [
            human_value(backend.get("repo"), language, ""),
            human_value(backend.get("controller"), language, ""),
            human_value(backend.get("service"), language, ""),
        ]
        if item
    )
    if language == "zh":
        lines = [
            "- 置信度：`高`",
            "- 来源：运行时证据已覆盖自动代码入口低置信结果。",
            f"- 前端入口：{frontend_entry or '未同步'}",
        ]
        if frontend_file:
            lines.append(f"- 前端源码：`{frontend_file}`")
        lines.append(f"- 后端入口：{backend_entry or '未同步'}")
        if backend_files:
            lines.append("- 后端源码：" + "、".join(f"`{item}`" for item in backend_files[:8]))
        return "\n".join(lines)
    lines = [
        "- Confidence: `high`",
        "- Source: runtime evidence overrides lower-confidence automatic entrypoint hints.",
        f"- Frontend entry: {frontend_entry or 'not synced'}",
    ]
    if frontend_file:
        lines.append(f"- Frontend source: `{frontend_file}`")
    lines.append(f"- Backend entry: {backend_entry or 'not synced'}")
    if backend_files:
        lines.append("- Backend sources: " + ", ".join(f"`{item}`" for item in backend_files[:8]))
    return "\n".join(lines)


def render_runtime_field_api_permission_impact(runtime_evidence: dict[str, Any], language: str = "en") -> str:
    runtime_evidence = runtime_evidence if isinstance(runtime_evidence, dict) else {}
    interactions = [item for item in as_list(runtime_evidence.get("interactions")) if isinstance(item, dict)]
    if not interactions:
        return ""
    frontend = runtime_evidence.get("frontend") if isinstance(runtime_evidence.get("frontend"), dict) else {}
    frontend_entry = " / ".join(
        item
        for item in [
            human_value(frontend.get("page"), language, ""),
            human_value(frontend.get("route"), language, ""),
        ]
        if item
    )
    if language == "zh":
        lines = ["| 子域 | 责任入口 | 字段/数据影响 | 接口影响 | 权限影响 |", "|---|---|---|---|---|"]
        for index, item in enumerate(interactions[:10], start=1):
            brk = runtime_interaction_id(item, index)
            scenario = human_value(item.get("scenario"), language, brk)
            api = " ".join(part for part in [human_value(item.get("method"), language, ""), human_value(item.get("api"), language, "")] if part)
            request = human_value(item.get("request"), language, "")
            response = human_value(item.get("response"), language, "")
            data = response or request or "按数据模型章节校准字段读写"
            permission = "沿用现有菜单/按钮权限；后端保留租户范围、原因必填和状态校验"
            lines.append(f"| `{brk}` {scenario} | {frontend_entry or '前端页面'} / 后端服务 | {data} | `{api or '未同步接口'}` | {permission} |")
        return "\n".join(lines)
    lines = ["| Slice | Owner | Field/Data Impact | API Impact | Permission Impact |", "|---|---|---|---|---|"]
    for index, item in enumerate(interactions[:10], start=1):
        brk = runtime_interaction_id(item, index)
        scenario = human_value(item.get("scenario"), language, brk)
        api = " ".join(part for part in [human_value(item.get("method"), language, ""), human_value(item.get("api"), language, "")] if part)
        request = human_value(item.get("request"), language, "")
        response = human_value(item.get("response"), language, "")
        data = response or request or "calibrate fields per data-model section"
        permission = "preserve existing menu/button permissions; backend retains tenant, reason-required, and status checks"
        lines.append(f"| `{brk}` {scenario} | {frontend_entry or 'frontend'} / backend service | {data} | `{api or 'not synced'}` | {permission} |")
    return "\n".join(lines)


def render_runtime_decision_summary(runtime_evidence: dict[str, Any], language: str = "en") -> str:
    runtime_evidence = runtime_evidence if isinstance(runtime_evidence, dict) else {}
    interactions = [item for item in as_list(runtime_evidence.get("interactions")) if isinstance(item, dict)]
    if not interactions:
        return ""
    frontend = runtime_evidence.get("frontend") if isinstance(runtime_evidence.get("frontend"), dict) else {}
    backend = runtime_evidence.get("backend") if isinstance(runtime_evidence.get("backend"), dict) else {}
    frontend_file = human_value(frontend.get("source_file") or frontend.get("file"), language, "")
    backend_files = [human_value(item, language, "") for item in as_list(backend.get("source_files") or backend.get("files")) if human_value(item, language, "")]
    api_count = len({human_value(item.get("api"), language, "") for item in interactions if human_value(item.get("api"), language, "")})
    options = [item for item in as_list(runtime_evidence.get("solution_options") or runtime_evidence.get("runtime_options")) if isinstance(item, dict)]
    if not options:
        options = [
            {
                "id": "R1",
                "name": "最小前后端适配，复用现有表和接口",
                "approach": "按业务子域在现有前端页面、后端 controller/service 和既有数据表内补齐展示、筛选、排序、原因校验和刷新逻辑。",
                "pros": ["改动边界最小", "复用既有事实源", "回滚路径清晰"],
                "cons": ["需要把每条子域规则落到现有方法内", "若既有字段不足，实施中仍需补充 DDL 评审"],
                "risk": "中低：主要风险是筛选/排序/原因校验口径遗漏。",
                "decision": "selected",
            },
            {
                "id": "R2",
                "name": "后端新增专用字段或专用接口",
                "approach": "为续期月份、筛选结果或不续期原因新增更显式的后端字段/API，再由前端消费。",
                "pros": ["接口语义更直观", "前端适配简单"],
                "cons": ["可能引入 DDL、回填和兼容成本", "需要额外迁移与回滚方案"],
                "risk": "中：数据迁移和存量消费方兼容风险高于复用方案。",
                "decision": "rejected",
            },
            {
                "id": "R3",
                "name": "纯前端展示修补",
                "approach": "只在页面侧补列、隐藏状态、调整按钮和本地筛选，不改变后端事实源。",
                "pros": ["开发快", "后端发布成本低"],
                "cons": ["无法保证金额、状态、原因落库和筛选条件的事实一致性", "绕过前端时不满足验收"],
                "risk": "高：结算和权限类规则不能只依赖前端。",
                "decision": "rejected",
            },
            {
                "id": "R4",
                "name": "结算/续期模型重构",
                "approach": "重构续期池、结算单、结算明细和续期记录之间的模型边界。",
                "pros": ["长期模型更统一", "可减少未来类似需求的重复适配"],
                "cons": ["范围过大", "测试、迁移、发布和回滚成本显著增加"],
                "risk": "高：超出本需求验收所需范围。",
                "decision": "rejected",
            },
        ]
    if language == "zh":
        lines = ["### 候选方案详述"]
        lines.append(f"- 方案数量：{len(options)} 个；按当前需求影响面动态展开，不固定为二选一或三选一。")
        lines.append(f"- 前端责任边界：`{frontend_file or '未同步前端文件'}`。")
        lines.append("- 后端责任边界：" + ("、".join(f"`{item}`" for item in backend_files[:6]) if backend_files else "后端 controller/service 按接口契约承接业务规则。"))
        lines.append(f"- 接口边界：本需求涉及 {api_count} 个已识别 API，按 API 契约章节逐项保持兼容。")
        for option in options:
            option_id = human_value(option.get("id") or option.get("option_id"), language, "")
            name = human_value(option.get("name"), language, option_id or "方案")
            lines.append(f"\n#### 方案 `{option_id or name}`：{name}")
            lines.append(f"- 做法：{human_value(option.get('approach') or option.get('description'), language, '未同步方案做法')}")
            lines.append(f"- 适用条件：{human_value(option.get('when') or option.get('when_to_choose') or option.get('applicability'), language, '按当前需求证据判断')}")
            lines.append(f"- 优点：{human_value(option.get('pros'), language, '待补充')}")
            lines.append(f"- 缺点：{human_value(option.get('cons'), language, '待补充')}")
            lines.append(f"- 风险：{human_value(option.get('risk') or option.get('risk_level'), language, '待补充')}")
            decision = human_value(option.get("decision"), language, "")
            if decision:
                lines.append(f"- 初步结论：{decision}")
        lines.extend([
            "",
            "### 方案对比与选择",
            "| 方案 | 范围 | 数据一致性 | 兼容/迁移风险 | 回滚复杂度 | 结论 |",
            "|---|---|---|---|---|---|",
        ])
        for option in options:
            option_id = human_value(option.get("id") or option.get("option_id"), language, "")
            name = human_value(option.get("name"), language, option_id or "方案")
            decision = human_value(option.get("decision"), language, "")
            if option_id == "R1" or decision.lower() == "selected":
                lines.append(f"| `{option_id or name}` | 前后端和既有数据表内闭环 | 高：后端保持事实源 | 低到中 | 低 | 选择：满足验收且范围最小 |")
            elif option_id == "R3":
                lines.append(f"| `{option_id}` | 前端局部 | 低：绕过前端不可控 | 中 | 低 | 不选：结算/权限/落库规则不能只靠前端 |")
            elif option_id == "R4":
                lines.append(f"| `{option_id}` | 跨模型重构 | 高 | 高 | 高 | 不选：超出本次验收范围 |")
            else:
                lines.append(f"| `{option_id or name}` | 后端接口/字段扩展 | 中到高 | 中到高 | 中 | 暂不选：只有既有字段不足时才升级 |")
        lines.extend([
            "",
            "### 决策结论",
            "- 选中：`R1` 最小前后端适配，复用现有表和接口。",
            "- 选择理由：续期月份、状态过滤、原因落库和筛选条件都需要以后端为事实源，但当前证据显示既有接口、DTO/VO 和数据表已能承接主要规则；优先在现有页面与 service 内补齐字段、查询、排序、校验和刷新。",
            "- 拒绝纯前端修补：无法保证绕过前端时的原因必填、状态过滤和数据一致性。",
            "- 拒绝大范围重构：当前需求不要求重塑续期/结算模型，重构会显著增加迁移、测试和回滚成本。",
        ])
        return "\n".join(lines)
    lines = ["### Candidate Options"]
    lines.append(f"- Option count: {len(options)}; generated from the current evidence rather than a fixed two/three-option template.")
    lines.append(f"- Frontend boundary: `{frontend_file or 'not synced'}`.")
    lines.append("- Backend boundary: " + (", ".join(f"`{item}`" for item in backend_files[:6]) if backend_files else "backend controllers/services own business rules per API contract."))
    lines.append(f"- API boundary: {api_count} identified APIs remain compatible per the API contract section.")
    for option in options:
        option_id = human_value(option.get("id") or option.get("option_id"), language, "")
        name = human_value(option.get("name"), language, option_id or "Option")
        lines.append(f"\n#### Option `{option_id or name}`: {name}")
        lines.append(f"- Approach: {human_value(option.get('approach') or option.get('description'), language, 'not synced')}")
        lines.append(f"- Applicability: {human_value(option.get('when') or option.get('when_to_choose') or option.get('applicability'), language, 'based on current evidence')}")
        lines.append(f"- Pros: {human_value(option.get('pros'), language, 'TBD')}")
        lines.append(f"- Cons: {human_value(option.get('cons'), language, 'TBD')}")
        lines.append(f"- Risk: {human_value(option.get('risk') or option.get('risk_level'), language, 'TBD')}")
    lines.extend([
        "",
        "### Comparison And Decision",
        "- Selected: `R1` minimal frontend/backend adaptation using existing tables and APIs.",
        "- Reason: backend remains the source of truth while current contracts and tables can carry the required behavior with the smallest release and rollback scope.",
        "- Rejected frontend-only patch: it cannot enforce reason-required, status filtering, or persistence when clients bypass the UI.",
        "- Rejected model rewrite: it exceeds the acceptance scope and increases migration, testing, and rollback cost.",
    ])
    return "\n".join(lines)


def render_runtime_decision_record(runtime_evidence: dict[str, Any], language: str = "en") -> str:
    runtime_evidence = runtime_evidence if isinstance(runtime_evidence, dict) else {}
    if not runtime_evidence.get("interactions"):
        return ""
    if language == "zh":
        return "\n".join(
            [
                "- 决策：按业务子域拆分交付，前端页面、后端接口和数据模型分别绑定到源码证据。",
                "- 回滚考虑：前端和后端分别回滚；出现 DDL/回填时追加数据回滚脚本。",
            ]
        )
    return "\n".join(
        [
            "- Decision: split by business slice and bind frontend page, backend API, and data model to source evidence.",
            "- Rollback: revert frontend and backend changes separately; add data rollback scripts if DDL/backfill is introduced.",
        ]
    )


def render_runtime_architecture_operations(runtime_evidence: dict[str, Any], language: str = "en") -> str:
    runtime_evidence = runtime_evidence if isinstance(runtime_evidence, dict) else {}
    interactions = [item for item in as_list(runtime_evidence.get("interactions")) if isinstance(item, dict)]
    if not interactions:
        return ""
    frontend = runtime_evidence.get("frontend") if isinstance(runtime_evidence.get("frontend"), dict) else {}
    backend = runtime_evidence.get("backend") if isinstance(runtime_evidence.get("backend"), dict) else {}
    frontend_repo = human_value(frontend.get("repo"), language, "")
    backend_repo = human_value(backend.get("repo"), language, "")
    apis = []
    for item in interactions:
        api = " ".join(part for part in [human_value(item.get("method"), language, ""), human_value(item.get("api"), language, "")] if part)
        if api and api not in apis:
            apis.append(api)
    if language == "zh":
        lines = ["### 集成、发布与回滚口径"]
        lines.append(f"- 集成边界：`{frontend_repo or '前端'}` 通过已列 API 调用 `{backend_repo or '后端'}`；本轮证据未显示 MQ 或额外下游系统。")
        lines.append(f"- API 清单：{', '.join(f'`{api}`' for api in apis[:10])}")
        lines.append("- 发布顺序：先确认后端接口/数据口径，再发布前端页面；若后端无需改动，必须在实现证据中说明现有接口已满足。")
        lines.append("- 回滚口径：前端回滚页面改动，后端回滚 controller/service 改动；若实际新增 DDL/回填，必须补数据回滚脚本。")
        return "\n".join(lines)
    lines = ["### Integration, Release, And Rollback Scope"]
    lines.append(f"- Integration boundary: `{frontend_repo or 'frontend'}` calls `{backend_repo or 'backend'}` through listed APIs; no MQ or additional downstream is confirmed.")
    lines.append(f"- APIs: {', '.join(f'`{api}`' for api in apis[:10])}")
    lines.append("- Release order: confirm backend API/data semantics first, then release frontend adaptation; if backend does not change, implementation evidence must prove existing APIs already satisfy the target.")
    lines.append("- Rollback: revert frontend page changes and backend controller/service changes; DDL/backfill requires paired rollback scripts.")
    return "\n".join(lines)


def render_runtime_delivery_tasks(delivery_plan: dict[str, Any], runtime_evidence: dict[str, Any], language: str = "en") -> str:
    runtime_evidence = runtime_evidence if isinstance(runtime_evidence, dict) else {}
    frontend = runtime_evidence.get("frontend") if isinstance(runtime_evidence.get("frontend"), dict) else {}
    backend = runtime_evidence.get("backend") if isinstance(runtime_evidence.get("backend"), dict) else {}
    frontend_repo = human_value(frontend.get("repo"), language, "")
    frontend_file = human_value(frontend.get("source_file") or frontend.get("file"), language, "")
    backend_repo = human_value(backend.get("repo"), language, "")
    backend_files = [human_value(item, language, "") for item in as_list(backend.get("source_files") or backend.get("files")) if human_value(item, language, "")]
    if not frontend_file and not backend_files:
        return ""
    interactions = [item for item in as_list(runtime_evidence.get("interactions")) if isinstance(item, dict)]
    if language == "zh":
        lines = []
        if frontend_file:
            lines.extend(
                [
                    f"### 仓库 `{frontend_repo or '前端仓库'}`",
                    "",
                    f"- 修改前必须阅读：`{frontend_file}`",
                    f"- 允许修改文件：`{frontend_file}` 及同目录内已存在的局部测试/类型文件；若需要跨目录改动，必须更新交付计划。",
                    "- 核心任务：校准页面列、筛选参数、按钮/弹窗校验、接口调用和成功后刷新。",
                    "- 需要覆盖的用户动作：" + ("；".join(human_value(item.get("trigger"), language, "") for item in interactions if human_value(item.get("trigger"), language, "")) or "未同步"),
                    "- 测试命令：`npm run build:test` 或项目实际可用的等价构建命令。",
                    "",
                ]
            )
        if backend_files:
            lines.extend(
                [
                    f"### 仓库 `{backend_repo or '后端仓库'}`",
                    "",
                    "- 修改前必须阅读：" + "、".join(f"`{item}`" for item in backend_files),
                    "- 允许修改文件：上述 controller/service/DTO/VO 及其直接测试；若新增 Mapper/SQL/迁移，必须补充数据回滚说明。",
                    "- 核心任务：校准状态过滤、月份推导、筛选条件透传、原因必填和续期池写入语义。",
                    "- 测试命令：`mvn -pl operate-provider -DskipTests compile`，并补充相关 service/API 测试或说明环境阻塞。",
                    "",
                ]
            )
        lines.append("- 交付顺序：先后端契约/数据口径，后前端页面适配；若后端确认无需改动，需在证据中说明接口已满足目标。")
        lines.append("- 回滚策略：前端回滚页面提交；后端回滚接口/服务提交；若引入 DDL 或回填，必须执行配套数据回滚或兼容脚本。")
        return "\n".join(lines)
    lines = []
    if frontend_file:
        lines.extend(
            [
                f"### Repo `{frontend_repo or 'frontend repo'}`",
                "",
                f"- Read first: `{frontend_file}`",
                f"- Allowed files: `{frontend_file}` and existing local tests/types in the same area; update the plan before cross-directory edits.",
                "- Core tasks: calibrate table columns, filter params, button/dialog validation, API calls, and refresh behavior.",
                "- Test command: `npm run build:test` or the project-equivalent build command.",
                "",
            ]
        )
    if backend_files:
        lines.extend(
            [
                f"### Repo `{backend_repo or 'backend repo'}`",
                "",
                "- Read first: " + ", ".join(f"`{item}`" for item in backend_files),
                "- Allowed files: listed controller/service/DTO/VO and direct tests; mapper/SQL/migration changes need data rollback notes.",
                "- Core tasks: calibrate status filtering, month derivation, filter propagation, reason-required checks, and renewal-pool writes.",
                "- Test command: `mvn -pl operate-provider -DskipTests compile`, plus relevant service/API tests or environment blocker notes.",
                "",
            ]
        )
    lines.append("- Delivery order: backend contract/data semantics first, frontend adaptation second; if backend does not change, evidence must prove the existing API already satisfies the target.")
    lines.append("- Rollback: revert frontend page commit and backend API/service commit; DDL/backfill requires paired rollback or compatibility script.")
    return "\n".join(lines)


def apply_runtime_evidence_overrides(value: Any, runtime_evidence: dict[str, Any], language: str = "en") -> Any:
    if not isinstance(runtime_evidence, dict) or not runtime_evidence.get("interactions"):
        return value
    frontend = runtime_evidence.get("frontend") if isinstance(runtime_evidence.get("frontend"), dict) else {}
    backend = runtime_evidence.get("backend") if isinstance(runtime_evidence.get("backend"), dict) else {}
    frontend_entry = " / ".join(
        item
        for item in [
            human_value(frontend.get("repo"), language, ""),
            human_value(frontend.get("page"), language, ""),
            human_value(frontend.get("route"), language, ""),
        ]
        if item
    )
    backend_entry = " / ".join(
        item
        for item in [
            human_value(backend.get("repo"), language, ""),
            human_value(backend.get("controller"), language, ""),
            human_value(backend.get("service"), language, ""),
        ]
        if item
    )
    frontend_owner = " / ".join(
        item
        for item in [
            human_value(frontend.get("repo"), language, ""),
            human_value(frontend.get("page"), language, ""),
        ]
        if item
    )
    backend_owner = " / ".join(
        item
        for item in [
            human_value(backend.get("repo"), language, ""),
            human_value(backend.get("service") or backend.get("controller"), language, ""),
        ]
        if item
    )
    combined_owner = "；".join(item for item in [frontend_owner, backend_owner] if item)
    api_values = []
    for item in [child for child in as_list(runtime_evidence.get("interactions")) if isinstance(child, dict)]:
        method = human_value(item.get("method"), language, "")
        api = human_value(item.get("api"), language, "")
        api_value = " ".join(part for part in [method, api] if part)
        if api_value and api_value not in api_values:
            api_values.append(api_value)
    api_family = "；".join(api_values[:3])
    if len(api_values) > 3:
        api_family += "；..."
    if not combined_owner:
        return value

    def replace_item(item: Any) -> Any:
        if isinstance(item, dict):
            return {key: replace_item(child) for key, child in item.items()}
        if isinstance(item, list):
            return [replace_item(child) for child in item]
        if isinstance(item, str):
            rendered = item
            replacements = {
                "target-repo": frontend_owner or combined_owner,
                "target module to be confirmed": combined_owner,
                "需结合代码核对的责任模块": combined_owner,
                "相关接口/服务": backend_owner or combined_owner,
                "mapped route/service": backend_owner or combined_owner,
                "/device/orderPivot (src/views/device/replacementSettlement.vue)": api_family or backend_owner or combined_owner,
                "/device/orderPivot": api_family or backend_owner or combined_owner,
            }
            for source, target in replacements.items():
                rendered = rendered.replace(source, target)
            return rendered
        return item

    return replace_item(value)


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


def render_next_action(status: dict[str, Any], delivery_review: dict[str, Any], language: str = "en") -> str:
    primary = status.get("primary_next_action") if isinstance(status.get("primary_next_action"), dict) else {}
    for value in [primary.get("summary"), status.get("next_command")]:
        if value:
            return zh_text(value) if language == "zh" else text(value)
    blockers = as_list(delivery_review.get("blockers"))
    if blockers and isinstance(blockers[0], dict):
        value = blockers[0].get("suggestion") or blockers[0].get("message")
        return zh_text(value) if language == "zh" else text(value)
    if language == "zh":
        return "实现或发布前先处理上述阻塞项。"
    return "Resolve listed blockers before implementation or release."


def render_evidence_refs(artifact_dir: Path) -> str:
    refs = [
        "spec.json",
        "technical_design.json",
        "architecture_design.json",
        "runtime_sequence_evidence.json",
        "delivery_plan.json",
        "design_architecture_review.json",
        "delivery_plan_review.json",
        "delivery_status.json",
    ]
    lines = [f"- `{name}`" for name in refs if (artifact_dir / name).exists()]
    return "\n".join(lines) if lines else "- No machine artifacts were synced."


def inherit_expert_supplemental_artifacts(docs_root: Path, doc_id: str, artifact_dir: Path) -> list[dict[str, str]]:
    raw_dir = docs_root / "machine/raw" / doc_id
    inherited: list[dict[str, str]] = []
    if not raw_dir.exists():
        return inherited
    artifact_dir.mkdir(parents=True, exist_ok=True)
    for filename in EXPERT_SUPPLEMENTAL_ARTIFACTS:
        source = raw_dir / filename
        target = artifact_dir / filename
        if not source.exists() or target.exists():
            continue
        try:
            payload = read_json(source)
        except Exception:
            continue
        if filename == "runtime_sequence_evidence.json" and not as_list(payload.get("interactions")):
            continue
        shutil.copy2(source, target)
        inherited.append({
            "artifact": filename,
            "source": str(source),
            "target": str(target),
            "reason": "preserve source-backed expert runtime evidence during artifact rerun",
        })
    return inherited


def first_text(*values: Any) -> str:
    for value in values:
        rendered = text(value, "").strip()
        if rendered:
            return rendered
    return ""


def project_understanding_path(artifact_dir: Path, name: str) -> Path:
    return artifact_dir / "project_understanding" / name


def project_name_from_artifacts(artifact_dir: Path) -> str:
    for name in ["code_index.json", "api_surface.json", "repository_analysis.json"]:
        data = read_json(project_understanding_path(artifact_dir, name))
        project = first_text(data.get("project"))
        if project:
            return project
    return ""


def code_index_files_by_path(artifact_dir: Path) -> dict[str, dict[str, Any]]:
    code_index = read_json(project_understanding_path(artifact_dir, "code_index.json"))
    return {
        text(item.get("path"), ""): item
        for item in as_list(code_index.get("files"))
        if isinstance(item, dict) and text(item.get("path"), "")
    }


def repo_root_from_code_index(artifact_dir: Path) -> Path | None:
    code_index = read_json(project_understanding_path(artifact_dir, "code_index.json"))
    repo_root = first_text(code_index.get("repo_root"))
    if not repo_root:
        return None
    path = Path(repo_root)
    return path if path.exists() else None


def source_file_text(artifact_dir: Path, rel_path: str, limit: int = 50000) -> str:
    repo_root = repo_root_from_code_index(artifact_dir)
    if not repo_root or not rel_path:
        return ""
    path = repo_root / rel_path
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except Exception:
        return ""


def selected_owner_entrypoints(technical: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    current = technical.get("current_state_analysis") if isinstance(technical.get("current_state_analysis"), dict) else {}
    candidates.extend(text(item, "") for item in as_list(current.get("code_entrypoints")))
    for item in as_list(technical.get("field_api_permission_impact")):
        if isinstance(item, dict):
            candidates.append(text(item.get("owner_entrypoint"), ""))
    for item in as_list(technical.get("module_decomposition")):
        if isinstance(item, dict):
            candidates.append(text(item.get("module"), ""))
    compact: list[str] = []
    for item in candidates:
        if item and item not in compact:
            compact.append(item)
    return compact


def parse_contract_method_path(contract: str) -> tuple[str, str]:
    raw = contract or ""
    method = ""
    mapping = re.search(r"@(Get|Post|Put|Delete|Patch)Mapping", raw)
    if mapping:
        method = {"Get": "GET", "Post": "POST", "Put": "PUT", "Delete": "DELETE", "Patch": "PATCH"}[mapping.group(1)]
    route_match = re.search(r'["\']([^"\']*/[^"\']*)["\']', raw)
    if route_match:
        return method, route_match.group(1)
    method_path = re.match(r"\s*(GET|POST|PUT|DELETE|PATCH)\s+(\S+)", raw, re.I)
    if method_path:
        return method_path.group(1).upper(), method_path.group(2)
    route = raw.split("(", 1)[0].strip() if "(" in raw and raw.strip().startswith("/") else raw.strip()
    return method, route


def contract_source_file(contract: str) -> str:
    match = re.search(r"\(([^()]+\.(?:java|py|vue|js|jsx|ts|tsx))\)", contract or "")
    return match.group(1) if match else ""


def normalized_route_label(raw: str) -> str:
    method, route = parse_contract_method_path(raw)
    if method and route:
        return f"{method} {route}"
    return route


def is_backend_entrypoint(entrypoint: str, has_http_contract: bool = False) -> bool:
    lowered = entrypoint.lower()
    return (
        lowered.endswith(".java")
        or lowered.endswith(".py") and (has_http_contract or lowered.endswith("main.py") or "/api/" in lowered or "/routes/" in lowered)
        or "controller/" in lowered
        or "service/" in lowered
    )


def is_frontend_entrypoint(entrypoint: str) -> bool:
    lowered = entrypoint.lower()
    return lowered.endswith((".vue", ".js", ".jsx", ".ts", ".tsx")) and not lowered.endswith(".d.ts")


def route_for_entrypoint(artifact_dir: Path, entrypoint: str) -> str:
    api_surface = read_json(project_understanding_path(artifact_dir, "api_surface.json"))
    routes = [item for item in as_list(api_surface.get("routes")) if isinstance(item, dict)]
    direct = [item for item in routes if text(item.get("file"), "") == entrypoint]
    for item in direct:
        route = first_text(item.get("route"))
        if route and route != "/":
            return route
    for item in direct:
        route = first_text(item.get("route"))
        if route:
            return route
    return ""


def source_symbols_for_entrypoint(artifact_dir: Path, entrypoint: str, limit: int = 8) -> list[str]:
    files = code_index_files_by_path(artifact_dir)
    item = files.get(entrypoint) or {}
    symbols = [text(value, "") for value in as_list(item.get("symbols")) if text(value, "")]
    source = source_file_text(artifact_dir, entrypoint)
    if source:
        symbols.extend(re.findall(r"\b(?:function\s+|const\s+|let\s+|var\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*[:=]\s*(?:async\s*)?\([^)]*\)\s*=>", source))
        symbols.extend(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*\{", source))
        symbols.extend(re.findall(r"\b(public|private|protected)\s+[A-Za-z0-9_<>, ?]+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", source))
    compact: list[str] = []
    for value in symbols:
        symbol = value[1] if isinstance(value, tuple) else value
        if symbol and symbol not in compact and symbol not in {"if", "for", "while", "switch", "catch"}:
            compact.append(symbol)
    return compact[:limit]


def source_table_hints(artifact_dir: Path, entrypoints: list[str]) -> list[dict[str, Any]]:
    tables: list[str] = []
    for entrypoint in entrypoints:
        source = source_file_text(artifact_dir, entrypoint)
        tables.extend(re.findall(r"@TableName\(\s*\"([^\"]+)\"", source))
        tables.extend(re.findall(r"\b([a-z][a-z0-9]+(?:_[a-z0-9]+){2,})\b", source))
    compact: list[str] = []
    for table in tables:
        if table not in compact and any(term in table for term in ["obd_", "device", "renew", "order", "settlement", "batch", "menu", "track"]):
            compact.append(table)
    return [{"table": table, "operation": "需结合源码确认读写语义"} for table in compact[:8]]


def actor_from_spec(spec: dict[str, Any]) -> str:
    actors = [text(item, "") for item in as_list(spec.get("actors")) if text(item, "")]
    if actors:
        return "业务操作人" if actors[0].lower() in {"user", "actor"} else actors[0]
    personas = [item for item in as_list(spec.get("personas")) if isinstance(item, dict)]
    for item in personas:
        actor = text(item.get("actor"), "")
        if actor:
            return "业务操作人" if actor.lower() in {"user", "actor"} else actor
    return "业务操作人"


def acceptance_ids_for_summary(spec: dict[str, Any], summary: str) -> list[str]:
    result: list[str] = []
    for item in as_list(spec.get("acceptance_criteria")):
        if not isinstance(item, dict):
            continue
        criteria = text(item.get("criteria"), "")
        ac_id = text(item.get("id"), "")
        if ac_id and (not summary or summary in criteria or criteria in summary):
            result.append(ac_id)
    if not result:
        first = next((text(item.get("id"), "") for item in as_list(spec.get("acceptance_criteria")) if isinstance(item, dict) and text(item.get("id"), "")), "")
        if first:
            result.append(first)
    return result


def synthesize_runtime_sequence_evidence(artifact_dir: Path, doc_id: str = "") -> tuple[dict[str, Any], list[str]]:
    spec = read_json(artifact_dir / "spec.json")
    technical = read_json(artifact_dir / "technical_design.json")
    project = project_name_from_artifacts(artifact_dir)
    indexed_files = code_index_files_by_path(artifact_dir)
    if not project or not indexed_files:
        return {}, ["project understanding code index is required for source-backed runtime evidence"]
    owner_entrypoints = selected_owner_entrypoints(technical)
    primary_entrypoint = owner_entrypoints[0] if owner_entrypoints else ""
    if primary_entrypoint and primary_entrypoint not in indexed_files and not route_for_entrypoint(artifact_dir, primary_entrypoint):
        return {}, [f"primary entrypoint is not present in code index: {primary_entrypoint}"]
    current = technical.get("current_state_analysis") if isinstance(technical.get("current_state_analysis"), dict) else {}
    ui = next((item for item in as_list(technical.get("ui_ue_design")) if isinstance(item, dict)), {})
    page_or_route = first_text(ui.get("page_or_route"), route_for_entrypoint(artifact_dir, primary_entrypoint))
    api_contracts = [item for item in as_list(technical.get("api_contracts")) if isinstance(item, dict)]
    has_http_contract = any(parse_contract_method_path(text(item.get("contract"), ""))[0] for item in api_contracts)
    backend_owner_entrypoints = [entrypoint for entrypoint in owner_entrypoints if is_backend_entrypoint(entrypoint, has_http_contract)]
    frontend_owner_entrypoints = [entrypoint for entrypoint in owner_entrypoints if is_frontend_entrypoint(entrypoint)]
    contracts_by_brk = {text(item.get("requirement_breakdown_id"), ""): item for item in api_contracts}
    module_by_brk = {
        text(item.get("requirement_breakdown_id"), ""): item
        for item in as_list(technical.get("module_decomposition"))
        if isinstance(item, dict)
    }
    interactions: list[dict[str, Any]] = []
    for index, item in enumerate([child for child in as_list(technical.get("requirement_breakdown")) if isinstance(child, dict)], start=1):
        brk = text(item.get("id"), f"BRK-{index}")
        summary = text(item.get("summary") or item.get("behavior_change"), "")
        module = module_by_brk.get(brk, {})
        contract = contracts_by_brk.get(brk, {})
        contract_text = text(contract.get("contract"), "")
        method, api = parse_contract_method_path(contract_text)
        contract_file = contract_source_file(contract_text)
        entrypoint = first_text(
            contract_file if contract_file in indexed_files else "",
            module.get("module"),
            primary_entrypoint,
        )
        if not api and entrypoint:
            api = route_for_entrypoint(artifact_dir, entrypoint)
        symbols = source_symbols_for_entrypoint(artifact_dir, entrypoint)
        entry_is_backend = is_backend_entrypoint(entrypoint, bool(method))
        trigger = first_text(ui.get("entry_point"), ui.get("user_goal"), summary)
        if trigger == "existing entry" and entry_is_backend:
            trigger = f"调用 {method + ' ' if method else ''}{api or entrypoint}，执行「{summary}」"
        elif trigger == "existing entry":
            trigger = f"打开 {page_or_route or entrypoint} 并执行「{summary}」"
        interaction = {
            "scenario": f"{brk} {summary}".strip(),
            "trigger": trigger,
            "current_gap": text(current.get("process_gap") or current.get("business_problem"), ""),
            "frontend_functions": symbols if not entry_is_backend else [],
            "field_bindings": [text(value, "") for value in as_list(ui.get("field_rules")) if text(value, "")],
            "method": method,
            "api": api,
            "request": text(module.get("input"), ""),
            "backend_methods": symbols if entry_is_backend else [],
            "backend_rules": [text(module.get("responsibility") or summary, "")],
            "data_operations": [],
            "backend_action": " -> ".join(symbols[:2]) if entry_is_backend and symbols else "",
            "response": text(module.get("output"), ""),
            "failure": "保留现有错误处理和权限边界，具体异常码需结合实现确认",
            "acceptance_assertions": [summary] if summary else [],
            "acceptance_ids": acceptance_ids_for_summary(spec, summary),
        }
        if not any(interaction.get(key) for key in ["api", "frontend_functions", "backend_methods", "trigger"]):
            continue
        interactions.append({key: value for key, value in interaction.items() if value not in (None, "", [], {})})
    if not interactions:
        return {}, ["no_interactions_inferred"]
    data_models = source_table_hints(artifact_dir, owner_entrypoints)
    frontend_route = page_or_route
    if frontend_route.startswith("@"):
        frontend_route = normalized_route_label(frontend_route)
    primary_frontend_entrypoint = frontend_owner_entrypoints[0] if frontend_owner_entrypoints else ""
    primary_backend_entrypoint = backend_owner_entrypoints[0] if backend_owner_entrypoints else ""
    frontend = {
        "repo": project,
        "page": text(ui.get("user_goal") or spec.get("title") or spec.get("requirement_summary"), ""),
        "route": frontend_route if primary_frontend_entrypoint else "",
        "entry_menu_or_button": text(ui.get("entry_point") if ui.get("entry_point") != "existing entry" else ui.get("user_goal"), "") if primary_frontend_entrypoint else "",
        "source_file": primary_frontend_entrypoint,
    }
    backend = {
        "repo": project if primary_backend_entrypoint else "",
        "controller": primary_backend_entrypoint if "controller/" in primary_backend_entrypoint.lower() else "",
        "service": primary_backend_entrypoint if "service/" in primary_backend_entrypoint.lower() else "",
        "source_files": backend_owner_entrypoints[:8],
    }
    evidence = {
        "schema": "codex-runtime-sequence-evidence-v1",
        "doc_id": doc_id,
        "source": "docs-governor synthesized from spec, technical design, api surface, and code index",
        "confidence": "medium",
        "actor": actor_from_spec(spec),
        "frontend": {key: value for key, value in frontend.items() if value},
        "backend": {key: value for key, value in backend.items() if value},
        "data_models": data_models,
        "api_contracts": [
            {"method": parse_contract_method_path(text(item.get("contract"), ""))[0], "path": parse_contract_method_path(text(item.get("contract"), ""))[1], "source": text(item.get("contract"), "")}
            for item in api_contracts
        ],
        "interactions": interactions,
    }
    return evidence, []


def ensure_runtime_sequence_evidence(artifact_dir: Path, doc_id: str = "") -> dict[str, Any]:
    target = artifact_dir / "runtime_sequence_evidence.json"
    if target.exists():
        return {"generated": False, "path": str(target), "reason": "already exists"}
    evidence, warnings = synthesize_runtime_sequence_evidence(artifact_dir, doc_id)
    if evidence.get("interactions"):
        write_json(target, evidence)
        return {"generated": True, "path": str(target), "warnings": warnings}
    return {"generated": False, "warnings": warnings or ["insufficient source-backed runtime evidence"]}


def render_synced_human_docs_zh(doc_id: str, title: str, artifact_dir: Path) -> dict[str, str]:
    requirement = artifact_dir / "requirement.normalized.txt"
    spec = read_json(artifact_dir / "spec.json")
    technical = read_json(artifact_dir / "technical_design.json")
    architecture = read_json(artifact_dir / "architecture_design.json")
    test_design = read_json(artifact_dir / "test_design.json")
    test_data_plan = read_json(artifact_dir / "test_data_plan.json")
    delivery_plan = read_json(artifact_dir / "delivery_plan.json")
    design_review = read_json(artifact_dir / "design_architecture_review.json")
    delivery_review = read_json(artifact_dir / "delivery_plan_review.json")
    status = read_json(artifact_dir / "delivery_status.json")
    runtime_evidence = read_json(artifact_dir / "runtime_sequence_evidence.json")
    technical = apply_runtime_evidence_overrides(technical, runtime_evidence, "zh")
    architecture = apply_runtime_evidence_overrides(architecture, runtime_evidence, "zh")
    delivery_plan = apply_runtime_evidence_overrides(delivery_plan, runtime_evidence, "zh")
    requirement_text = requirement.read_text(encoding="utf-8") if requirement.exists() else ""
    heading = title or str(spec.get("title") or doc_id)
    zh_user_scenarios = [
        summarize_dict_item(item, ["actor", "trigger", "expected_outcome"], "zh")
        for item in as_list(spec.get("user_scenarios"))
        if isinstance(item, dict)
    ] + [text(item) for item in as_list(spec.get("user_scenarios")) if not isinstance(item, dict)]
    zh_business_objectives = [
        text(item.get("objective") or item.get("summary") or item)
        for item in as_list(spec.get("business_objectives"))
        if isinstance(item, dict)
    ] + [text(item) for item in as_list(spec.get("business_objectives")) if not isinstance(item, dict)]
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
            f"{render_spec_review_narrative(spec, 'zh')}\n\n"
            "## 二、背景与目标\n\n"
            f"{section_paragraph('业务背景', [text(spec.get('requirement_summary') or spec.get('summary') or heading)], '未同步到业务背景。')}\n\n"
            f"{section_paragraph('用户场景', zh_user_scenarios, '未记录用户场景。')}\n\n"
            f"{section_paragraph('业务目标', zh_business_objectives, '未记录业务目标。')}\n\n"
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
            f"{render_design_review_context(technical, architecture, delivery_plan, 'zh', runtime_evidence)}\n\n"
            f"{render_runtime_evidence_context(runtime_evidence, 'zh')}\n\n"
            "## 二、现状问题与设计目标\n\n"
            f"{render_problem_analysis(technical, 'zh', runtime_evidence)}\n\n"
            f"{render_current_architecture_context(architecture, runtime_evidence, 'zh')}\n\n"
            "## 三、子需求设计矩阵\n\n"
            f"{render_runtime_subrequirement_design(spec, runtime_evidence, 'zh') or render_requirement_breakdown_table(technical, 'zh')}\n\n"
            "### 代码入口置信度\n\n"
            f"{render_runtime_entrypoint_confidence(runtime_evidence, 'zh') or render_entrypoint_confidence(technical, 'zh')}\n\n"
            "### 字段/接口/权限影响表\n\n"
            f"{render_runtime_field_api_permission_impact(runtime_evidence, 'zh') or render_field_api_permission_impact(technical, 'zh')}\n\n"
            "### 低置信度需确认项\n\n"
            f"{'- 无：运行时证据已覆盖入口、接口、表结构和交互链路；若实现发现证据不符，需要回到本节补充确认项。' if runtime_evidence.get('interactions') else render_low_confidence_items(technical, architecture, 'zh')}\n\n"
            "## 四、候选方案、对比与决策\n\n"
            f"{render_runtime_decision_summary(runtime_evidence, 'zh') or render_solution_options(technical, architecture, 'zh')}\n\n"
            "## 五、决策记录\n\n"
            f"{render_runtime_decision_record(runtime_evidence, 'zh') or render_decision_records(architecture, technical, language='zh')}\n\n"
            "## 六、业务流程\n\n"
            f"{render_runtime_process_flows(runtime_evidence, 'zh') or render_process_flows(technical, 'zh')}\n\n"
            "### 流程图\n\n"
            f"{render_runtime_process_mermaid(runtime_evidence, 'zh') or render_process_mermaid(technical, 'zh')}\n\n"
            "## 七、模块与接口设计\n\n"
            f"{render_runtime_module_design(runtime_evidence, 'zh') or render_named_items(as_list(technical.get('module_decomposition')), ['module', 'responsibility', 'input', 'output', 'coupling_control'], '未同步到模块设计。', 'zh')}\n\n"
            f"{render_runtime_api_contracts(runtime_evidence, 'zh') or render_named_items(as_list(technical.get('api_contracts')), ['contract', 'compatibility', 'old_consumer_impact'], '未同步到接口影响。', 'zh')}\n\n"
            f"{'' if render_runtime_api_contracts(runtime_evidence, 'zh') else render_named_items(as_list(technical.get('interface_examples')), ['name', 'request', 'response', 'error_response'], '未同步到接口示例。', 'zh')}\n\n"
            "## 八、数据、权限、页面与异常场景\n\n"
            f"{render_runtime_data_access(runtime_evidence, 'zh') or render_named_items(as_list(technical.get('data_design')), ['read_rule', 'write_rule', 'migration'], '未同步到数据设计。', 'zh')}\n\n"
            f"{render_expert_technical_sections(technical, 'zh', architecture, runtime_evidence, suppress_runtime_data_model=bool(render_runtime_data_model(runtime_evidence, 'zh')))}\n\n"
            f"{render_runtime_data_model(runtime_evidence, 'zh')}\n\n"
            f"{render_runtime_permission_model(runtime_evidence, 'zh') or render_named_items(as_list(technical.get('permission_model')), ['role', 'rule', 'negative_case'], '未同步到权限规则。', 'zh')}\n\n"
            f"{render_runtime_exception_cases(runtime_evidence, 'zh') or render_named_items(as_list(technical.get('exception_and_edge_cases')), ['case', 'handling'], '未同步到异常场景。', 'zh')}\n\n"
            f"{render_runtime_ui_impact(runtime_evidence, 'zh') or render_named_items(as_list(technical.get('ui_ue_design')), ['page_or_route', 'user_goal', 'entry_point', 'permission_visibility', 'acceptance_evidence'], '未同步到页面影响。', 'zh')}\n\n"
            "## 九、架构与运维影响\n\n"
            f"{render_new_service_design(architecture, 'zh')}\n\n"
            f"{render_dependency_graph_items(architecture, runtime_evidence, 'zh')}\n\n"
            "### 模块/仓库关系图\n\n"
            f"{render_architecture_mermaid(architecture, 'zh', runtime_evidence)}\n\n"
            f"{render_runtime_architecture_operations(runtime_evidence, 'zh') or render_named_items(as_list(architecture.get('integration_sequence')), ['step', 'actor', 'action', 'failure_handling'], '未同步到集成顺序。', 'zh')}\n\n"
            f"{'' if runtime_evidence.get('interactions') else render_named_items(as_list(architecture.get('deployment_impact_matrix')), ['repo', 'artifact', 'order', 'config_change', 'restart_required'], '未同步到发布影响矩阵。', 'zh')}\n\n"
            f"{'' if runtime_evidence.get('interactions') else render_named_items(as_list(architecture.get('rollback_strategy')), ['repo', 'steps', 'data_risk'], '未同步到回滚策略。', 'zh')}\n\n"
            "## 十、交付执行计划\n\n"
            f"{render_runtime_delivery_tasks(delivery_plan, runtime_evidence, 'zh') or render_delivery_tasks(delivery_plan, 'zh')}\n\n"
            "## 十一、需求追踪关系\n\n"
            "- 追踪关系：每个设计决策必须能回到 `spec.json` 的验收标准，并向前关联到 `test_design.json` 测试用例、`delivery_plan.json` 任务和发布证据。\n"
            "- 如果任一验收标准缺少设计引用、测试用例或交付证据责任人，评审时应阻止进入实现。\n\n"
            "## 十二、测试策略摘要\n\n"
            f"- 本节只保留验收证据映射和测试策略摘要；详细测试用例维护在 `human/tests/{doc_id}.md` 与 `test_design.json`。\n\n"
            f"{render_runtime_acceptance_proof(spec, runtime_evidence, 'zh')}\n\n"
            f"{'' if runtime_evidence.get('interactions') else render_named_items(as_list(technical.get('acceptance_mapping')), ['acceptance_id', 'design_refs', 'evidence_required'], '未同步到验收证据映射。', 'zh')}\n\n"
            f"{'' if runtime_evidence.get('interactions') else render_named_items(as_list(technical.get('test_strategy')), ['summary', 'type', 'evidence'], '未同步到测试策略。', 'zh')}\n\n"
            "## 十三、风险与未过门禁\n\n"
            f"{render_blockers(delivery_plan, architecture, language='zh')}\n\n"
            "## 十四、证据引用\n\n"
            "- `technical_design.json`：技术设计、接口、数据、权限和测试映射。\n"
            "- `architecture_design.json`：架构边界、跨仓依赖、部署和回滚策略。\n"
            "- `test_design.json`：详细测试用例、回归范围和验收证据要求。\n"
            "- `delivery_plan.json`：实施顺序、文件范围、证据和回滚检查。\n\n"
            f"{render_evidence_refs(artifact_dir)}\n"
        ),
        "test": (
            f"# {heading} 测试设计\n\n"
            "## 一、摘要\n\n"
            f"- 文档编号：`{doc_id}`\n"
            f"- 测试设计状态：`{zh_text(test_design.get('decision'), '草稿')}`\n"
            f"- 测试用例数：`{zh_text(len(as_list(test_design.get('test_cases'))), '0')}`\n"
            "- 本文承载详细测试用例；技术设计只保留测试策略摘要和证据映射。\n\n"
            "## 二、验收证据映射\n\n"
            f"{render_named_items(as_list(technical.get('acceptance_mapping')), ['acceptance_id', 'design_refs', 'evidence_required'], '未同步到验收证据映射。', 'zh')}\n\n"
            "## 三、测试策略摘要\n\n"
            f"{render_named_items(as_list(technical.get('test_strategy')), ['summary', 'type', 'evidence'], '未同步到测试策略。', 'zh')}\n\n"
            "## 四、测试用例\n\n"
            f"{render_test_cases(test_design, 'zh')}\n\n"
            "## 五、测试数据准备\n\n"
            f"{render_test_data_plan(test_data_plan, 'zh')}\n\n"
            "## 六、回归、集成、前端与权限范围\n\n"
            f"### 回归范围\n\n{render_named_items(as_list(test_design.get('regression_scope')), ['area', 'reason'], '未同步到回归范围。', 'zh')}\n\n"
            f"### 集成范围\n\n{render_named_items(as_list(test_design.get('integration_scope')), ['id', 'title', 'evidence_required'], '未同步到集成范围。', 'zh')}\n\n"
            f"### 前端范围\n\n{render_named_items(as_list(test_design.get('frontend_scope')), ['id', 'title', 'evidence_required'], '未同步到前端范围。', 'zh')}\n\n"
            f"### 权限范围\n\n{render_named_items(as_list(test_design.get('permission_scope')), ['id', 'title', 'evidence_required'], '未同步到权限范围。', 'zh')}\n\n"
            "## 七、证据要求\n\n"
            f"{bullet_lines([zh_text(item) for item in as_list(test_design.get('evidence_required'))], '未同步到证据要求。')}\n\n"
            "## 八、追踪关系\n\n"
            "- 追踪关系：每个测试用例必须回到 `spec.json` 验收标准，并向前关联到 `test_data_plan.json`、`test_evidence_gate.json`、CI 记录、前端验收或发布证据。\n"
            "- 未映射到验收标准的权限、集成、前端用例必须说明风险来源和证据要求。\n\n"
            "## 九、证据引用\n\n"
            "- `test_design.json`：测试设计、用例、回归范围和证据要求。\n"
            "- `test_data_plan.json`：测试数据准备、账号角色、清理要求和隐私控制。\n"
            "- `test_evidence_gate.json`：真实测试与 CI 证据门禁结论。\n"
            "- `frontend_acceptance.json`：前端浏览器验收证据，如适用。\n\n"
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
            f"{render_named_items(as_list(technical.get('test_strategy')), ['summary', 'type', 'evidence'], '未同步到测试验证步骤。', 'zh')}\n\n"
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
            f"- {render_next_action(status, delivery_review, 'zh')}\n\n"
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
    test_data_plan = read_json(artifact_dir / "test_data_plan.json")
    delivery_plan = read_json(artifact_dir / "delivery_plan.json")
    design_review = read_json(artifact_dir / "design_architecture_review.json")
    delivery_review = read_json(artifact_dir / "delivery_plan_review.json")
    status = read_json(artifact_dir / "delivery_status.json")
    runtime_evidence = read_json(artifact_dir / "runtime_sequence_evidence.json")
    technical = apply_runtime_evidence_overrides(technical, runtime_evidence, "en")
    architecture = apply_runtime_evidence_overrides(architecture, runtime_evidence, "en")
    delivery_plan = apply_runtime_evidence_overrides(delivery_plan, runtime_evidence, "en")
    requirement_text = requirement.read_text(encoding="utf-8") if requirement.exists() else ""
    heading = title or str(spec.get("title") or doc_id)
    user_scenarios = [
        text(item.get("scenario") or item.get("summary") or item)
        for item in as_list(spec.get("user_scenarios"))
        if isinstance(item, dict)
    ] + [text(item) for item in as_list(spec.get("user_scenarios")) if not isinstance(item, dict)]
    business_objectives = [
        text(item.get("objective") or item.get("summary") or item)
        for item in as_list(spec.get("business_objectives"))
        if isinstance(item, dict)
    ] + [text(item) for item in as_list(spec.get("business_objectives")) if not isinstance(item, dict)]
    return {
        "spec": (
            f"# {heading} Spec\n\n"
            "## Executive Summary\n\n"
            f"- Doc ID: `{doc_id}`\n"
            f"- Current decision: `{text(spec.get('decision'), 'unknown')}`\n"
            f"- Permission sensitivity: {text((spec.get('permission_scope') or {}).get('sensitive'), 'unknown')}\n\n"
            "## Review Focus\n\n"
            f"{render_review_context(spec, 'en')}\n\n"
            f"{render_spec_review_narrative(spec, 'en')}\n\n"
            "## Background And Goals\n\n"
            f"{section_paragraph('Business Background', [text(spec.get('requirement_summary') or spec.get('summary') or heading)], 'Business background was not synced.')}\n\n"
            f"{section_paragraph('User Scenarios', user_scenarios, 'No user scenarios were recorded.')}\n\n"
            f"{section_paragraph('Business Objectives', business_objectives, 'No business objectives were recorded.')}\n\n"
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
            f"{render_design_review_context(technical, architecture, delivery_plan, 'en', runtime_evidence)}\n\n"
            f"{render_runtime_evidence_context(runtime_evidence, 'en')}\n\n"
            "## Current State, Problem, And Goals\n\n"
            f"{render_problem_analysis(technical, 'en', runtime_evidence)}\n\n"
            f"{render_current_architecture_context(architecture, runtime_evidence, 'en')}\n\n"
            "## Sub-Requirement Design Matrix\n\n"
            f"{render_runtime_subrequirement_design(spec, runtime_evidence, 'en') or render_requirement_breakdown_table(technical, 'en')}\n\n"
            "### Code Entrypoint Confidence\n\n"
            f"{render_runtime_entrypoint_confidence(runtime_evidence, 'en') or render_entrypoint_confidence(technical, 'en')}\n\n"
            "### Field / API / Permission Impact\n\n"
            f"{render_runtime_field_api_permission_impact(runtime_evidence, 'en') or render_field_api_permission_impact(technical, 'en')}\n\n"
            "### Low-Confidence Confirmation Items\n\n"
            f"{'- None: runtime evidence covers entrypoints, APIs, table schema, and interaction chains; implementation mismatches must be added here.' if runtime_evidence.get('interactions') else render_low_confidence_items(technical, architecture, 'en')}\n\n"
            "## Candidate Options, Comparison, And Decision\n\n"
            f"{render_runtime_decision_summary(runtime_evidence, 'en') or render_solution_options(technical, architecture, 'en')}\n\n"
            "## Decision Records\n\n"
            f"{render_runtime_decision_record(runtime_evidence, 'en') or render_decision_records(architecture, technical, language='en')}\n\n"
            "## Process Flow\n\n"
            f"{render_runtime_process_flows(runtime_evidence, 'en') or render_process_flows(technical)}\n\n"
            "### Flow Diagram\n\n"
            f"{render_runtime_process_mermaid(runtime_evidence, 'en') or render_process_mermaid(technical, 'en')}\n\n"
            "## Module And Contract Design\n\n"
            f"{render_runtime_module_design(runtime_evidence, 'en') or render_named_items(as_list(technical.get('module_decomposition')), ['module', 'responsibility', 'input', 'output', 'coupling_control'], 'No module design was synced.')}\n\n"
            f"{render_runtime_api_contracts(runtime_evidence, 'en') or render_named_items(as_list(technical.get('api_contracts')), ['contract', 'compatibility', 'old_consumer_impact'], 'No API contract changes were confirmed.')}\n\n"
            f"{'' if render_runtime_api_contracts(runtime_evidence, 'en') else render_named_items(as_list(technical.get('interface_examples')), ['name', 'request', 'response', 'error_response'], 'No interface examples were synced.')}\n\n"
            "## Data And UI Impact\n\n"
            f"{render_runtime_data_access(runtime_evidence, 'en') or render_named_items(as_list(technical.get('data_design')), ['read_rule', 'write_rule', 'migration'], 'No data design was synced.')}\n\n"
            f"{render_expert_technical_sections(technical, 'en', architecture, runtime_evidence, suppress_runtime_data_model=bool(render_runtime_data_model(runtime_evidence, 'en')))}\n\n"
            f"{render_runtime_data_model(runtime_evidence, 'en')}\n\n"
            f"{render_runtime_permission_model(runtime_evidence, 'en') or render_named_items(as_list(technical.get('permission_model')), ['role', 'rule', 'negative_case'], 'No permission rules were synced.')}\n\n"
            f"{render_runtime_exception_cases(runtime_evidence, 'en') or render_named_items(as_list(technical.get('exception_and_edge_cases')), ['case', 'handling'], 'No exception scenarios were synced.')}\n\n"
            f"{render_runtime_ui_impact(runtime_evidence, 'en') or render_named_items(as_list(technical.get('ui_ue_design')), ['page_or_route', 'user_goal', 'entry_point', 'permission_visibility', 'acceptance_evidence'], 'No UI impact was confirmed.')}\n\n"
            "## Architecture And Operations\n\n"
            f"{render_new_service_design(architecture, 'en')}\n\n"
            f"{render_dependency_graph_items(architecture, runtime_evidence, 'en')}\n\n"
            "### Module / Repository Diagram\n\n"
            f"{render_architecture_mermaid(architecture, 'en', runtime_evidence)}\n\n"
            f"{render_runtime_architecture_operations(runtime_evidence, 'en') or render_named_items(as_list(architecture.get('integration_sequence')), ['step', 'actor', 'action', 'failure_handling'], 'No integration sequence was synced.')}\n\n"
            f"{'' if runtime_evidence.get('interactions') else render_named_items(as_list(architecture.get('deployment_impact_matrix')), ['repo', 'artifact', 'order', 'config_change', 'restart_required'], 'No deployment impact matrix was synced.')}\n\n"
            f"{'' if runtime_evidence.get('interactions') else render_named_items(as_list(architecture.get('rollback_strategy')), ['repo', 'steps', 'data_risk'], 'No rollback strategy was synced.')}\n\n"
            "## Delivery Plan\n\n"
            f"{render_runtime_delivery_tasks(delivery_plan, runtime_evidence, 'en') or render_delivery_tasks(delivery_plan)}\n\n"
            "## Requirement Traceability\n\n"
            "- Traceability: every design decision must map back to `spec.json` acceptance criteria and forward to `test_design.json` test cases, `delivery_plan.json` tasks, and release evidence.\n"
            "- Reviewers should reject implementation if an acceptance criterion has no design reference, test case, or delivery evidence owner.\n\n"
            "## Test Strategy Summary\n\n"
            f"- This section keeps only acceptance evidence mapping and test strategy summary. Detailed test cases live in `human/tests/{doc_id}.md` and `test_design.json`.\n\n"
            f"{render_runtime_acceptance_proof(spec, runtime_evidence, 'en')}\n\n"
            f"{'' if runtime_evidence.get('interactions') else render_named_items(as_list(technical.get('acceptance_mapping')), ['acceptance_id', 'design_refs', 'evidence_required'], 'No acceptance evidence mapping was synced.')}\n\n"
            f"{'' if runtime_evidence.get('interactions') else render_named_items(as_list(technical.get('test_strategy')), ['summary', 'type', 'evidence'], 'No test strategy was synced.')}\n\n"
            "## Risks And Open Gates\n\n"
            f"{render_blockers(delivery_plan, architecture)}\n\n"
            "## Evidence References\n\n"
            "- `technical_design.json`: technical design, API/data/permission/test mapping.\n"
            "- `architecture_design.json`: architecture boundaries, dependency graph, deployment, rollback.\n"
            "- `test_design.json`: detailed test cases, regression scope, and evidence requirements.\n"
            "- `delivery_plan.json`: implementation sequence, file scope, evidence, rollback checks.\n\n"
            f"{render_evidence_refs(artifact_dir)}\n"
        ),
        "test": (
            f"# {heading} Test Design\n\n"
            "## Executive Summary\n\n"
            f"- Doc ID: `{doc_id}`\n"
            f"- Test design decision: `{text(test_design.get('decision'), 'draft')}`\n"
            f"- Test case count: `{len(as_list(test_design.get('test_cases')))}`\n"
            "- This document owns detailed test cases. The technical design keeps only the test strategy summary and evidence mapping.\n\n"
            "## Acceptance Evidence Mapping\n\n"
            f"{render_named_items(as_list(technical.get('acceptance_mapping')), ['acceptance_id', 'design_refs', 'evidence_required'], 'No acceptance evidence mapping was synced.')}\n\n"
            "## Test Strategy Summary\n\n"
            f"{render_named_items(as_list(technical.get('test_strategy')), ['summary', 'type', 'evidence'], 'No test strategy was synced.')}\n\n"
            "## Test Cases\n\n"
            f"{render_test_cases(test_design, 'en')}\n\n"
            "## Test Data Preparation\n\n"
            f"{render_test_data_plan(test_data_plan, 'en')}\n\n"
            "## Regression, Integration, Frontend, And Permission Scope\n\n"
            f"### Regression Scope\n\n{render_named_items(as_list(test_design.get('regression_scope')), ['area', 'reason'], 'No regression scope was synced.')}\n\n"
            f"### Integration Scope\n\n{render_named_items(as_list(test_design.get('integration_scope')), ['id', 'title', 'evidence_required'], 'No integration scope was synced.')}\n\n"
            f"### Frontend Scope\n\n{render_named_items(as_list(test_design.get('frontend_scope')), ['id', 'title', 'evidence_required'], 'No frontend scope was synced.')}\n\n"
            f"### Permission Scope\n\n{render_named_items(as_list(test_design.get('permission_scope')), ['id', 'title', 'evidence_required'], 'No permission scope was synced.')}\n\n"
            "## Evidence Requirements\n\n"
            f"{bullet_lines([text(item) for item in as_list(test_design.get('evidence_required'))], 'No evidence requirements were synced.')}\n\n"
            "## Traceability\n\n"
            "- Traceability: every test case must map back to `spec.json` acceptance criteria and forward to `test_data_plan.json`, `test_evidence_gate.json`, CI records, frontend acceptance, or release evidence.\n"
            "- Permission, integration, and frontend cases without direct acceptance IDs must explain their risk source and evidence requirement.\n\n"
            "## Evidence References\n\n"
            "- `test_design.json`: test design, cases, regression scope, and evidence requirements.\n"
            "- `test_data_plan.json`: test data setup, accounts/roles, cleanup expectations, and privacy controls.\n"
            "- `test_evidence_gate.json`: real test and CI evidence gate result.\n"
            "- `frontend_acceptance.json`: browser acceptance evidence when applicable.\n\n"
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
            f"{render_named_items(as_list(technical.get('test_strategy')), ['summary', 'type', 'evidence'], 'No test validation steps were synced.')}\n\n"
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
    inherited_supplemental_artifacts = inherit_expert_supplemental_artifacts(docs_root, doc_id, artifact_dir)
    generated_runtime_evidence = ensure_runtime_sequence_evidence(artifact_dir, doc_id)
    human_docs = render_synced_human_docs_zh(doc_id, title, artifact_dir) if language == "zh" else render_synced_human_docs(doc_id, title, artifact_dir)
    human_targets = {
        "spec": docs_root / manifest["human_docs"]["spec"],
        "design": docs_root / manifest["human_docs"]["design"],
        "test": docs_root / manifest["human_docs"]["test"],
        "release": docs_root / manifest["human_docs"]["release"],
    }
    for name, content in human_docs.items():
        human_targets[name].parent.mkdir(parents=True, exist_ok=True)
        human_targets[name].write_text(content, encoding="utf-8")

    bundles = {
        "spec": ["spec.json"],
        "design": ["technical_design.json", "architecture_design.json", "test_design.json", "test_data_plan.json", "delivery_plan.json"],
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
        if source.resolve() != dest.resolve():
            shutil.copy2(source, dest)
        copied_raw.append(str(dest.relative_to(docs_root)))

    manifest["synced_from"] = str(artifact_dir)
    manifest["synced_human_docs"] = [str(path.relative_to(docs_root)) for path in human_targets.values()]
    manifest["synced_machine_artifacts"] = synced_machine
    manifest["raw_artifacts"] = copied_raw
    manifest["inherited_supplemental_artifacts"] = inherited_supplemental_artifacts
    manifest["generated_runtime_evidence"] = generated_runtime_evidence
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
        "inherited_supplemental_artifacts": inherited_supplemental_artifacts,
        "generated_runtime_evidence": generated_runtime_evidence,
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
            "test": f"human/tests/{doc_id}.md",
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
