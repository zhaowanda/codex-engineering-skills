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
    return DOCS_I18N.translate_text(rendered, "zh")


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
    return zh_text(rendered) if language == "zh" else rendered


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


def render_system_sequence_mermaid(technical: dict[str, Any], language: str = "en") -> str:
    sequence = technical.get("system_interaction_sequence") if isinstance(technical.get("system_interaction_sequence"), dict) else {}
    if sequence.get("applicable") is not True:
        reason = text(sequence.get("not_applicable_reason") or sequence.get("reason"), "未涉及多系统交互" if language == "zh" else "no multi-system interaction")
        return f"- {reason}"
    participants = [human_value(item, language, "") for item in as_list(sequence.get("participants")) if human_value(item, language, "")]
    steps = []
    for item in as_list(sequence.get("sequence")):
        if isinstance(item, dict):
            steps.append(human_value(item.get("action") or item.get("step") or item, language, ""))
        else:
            steps.append(human_value(item, language, ""))
    steps = [item for item in steps if item]
    if not participants or not steps:
        return "缺少参与方或时序步骤，无法生成时序图。" if language == "zh" else "Participants or sequence steps are missing, so the sequence diagram cannot be generated."
    lines = ["```mermaid", "sequenceDiagram"]
    for participant in participants[:6]:
        alias = re.sub(r"[^A-Za-z0-9_]", "_", participant)[:30] or "Participant"
        lines.append(f"  participant {alias} as {participant[:40]}")
    first = re.sub(r"[^A-Za-z0-9_]", "_", participants[0])[:30] or "A"
    second = re.sub(r"[^A-Za-z0-9_]", "_", participants[1] if len(participants) > 1 else participants[0])[:30] or "B"
    for step in steps[:8]:
        lines.append(f"  {first}->>{second}: {step[:80]}")
        first, second = second, first
    lines.append("```")
    return "\n".join(lines)


def render_expert_technical_sections(technical: dict[str, Any], language: str = "en") -> str:
    lang = "zh" if language == "zh" else "en"
    sections: list[str] = []
    for section in DOC_MODEL.expert_design_sections(technical):
        parts = [f"### {DOCS_I18N.section_title(section['section_key'], lang)}"]
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
            parts.append(render_system_sequence_mermaid(technical, lang))
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
            f"{DOCS_I18N.label(field, 'zh')}：{human_value(item.get(field), 'zh')}" if language == "zh" else f"{DOCS_I18N.label(field, 'en')}: {human_value(item.get(field), 'en')}"
            for field in fields
            if item.get(field) not in (None, "", [], {})
        ]
        if values:
            lines.append("；".join(values) if language == "zh" else "; ".join(values))
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


def render_problem_analysis(technical: dict[str, Any], language: str = "en") -> str:
    problem = technical.get("problem_analysis") if isinstance(technical.get("problem_analysis"), dict) else {}
    current = technical.get("current_state_analysis") if isinstance(technical.get("current_state_analysis"), dict) else {}
    data = {**current, **problem}
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
        return "\n".join(f"- {label}：{zh_text(value)}" for label, value in sections if value not in (None, "", [], {})) or "- 未同步到现状问题分析。"
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
    return "\n".join(f"- {label}: {text(value)}" for label, value in sections if value not in (None, "", [], {})) or "- No problem analysis was synced."


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
    test_data_plan = read_json(artifact_dir / "test_data_plan.json")
    delivery_plan = read_json(artifact_dir / "delivery_plan.json")
    design_review = read_json(artifact_dir / "design_architecture_review.json")
    delivery_review = read_json(artifact_dir / "delivery_plan_review.json")
    status = read_json(artifact_dir / "delivery_status.json")
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
            f"{render_design_review_context(technical, architecture, delivery_plan, 'zh')}\n\n"
            "## 二、现状问题与设计目标\n\n"
            f"{render_problem_analysis(technical, 'zh')}\n\n"
            f"{render_named_items([architecture.get('current_architecture')], ['system_context', 'repo_entrypoints', 'upstream_downstream', 'constraints'], '未同步到当前架构分析。', 'zh')}\n\n"
            "## 三、子需求设计矩阵\n\n"
            f"{render_requirement_breakdown_table(technical, 'zh')}\n\n"
            "### 代码入口置信度\n\n"
            f"{render_entrypoint_confidence(technical, 'zh')}\n\n"
            "### 字段/接口/权限影响表\n\n"
            f"{render_field_api_permission_impact(technical, 'zh')}\n\n"
            "### 低置信度需确认项\n\n"
            f"{render_low_confidence_items(technical, architecture, 'zh')}\n\n"
            "## 四、候选方案、对比与决策\n\n"
            f"{render_solution_options(technical, architecture, 'zh')}\n\n"
            "## 五、决策记录\n\n"
            f"{render_decision_records(architecture, technical, language='zh')}\n\n"
            "## 六、业务流程\n\n"
            f"{render_process_flows(technical, 'zh')}\n\n"
            "### 流程图\n\n"
            f"{render_process_mermaid(technical, 'zh')}\n\n"
            "## 七、模块与接口设计\n\n"
            f"{render_named_items(as_list(technical.get('module_decomposition')), ['module', 'responsibility', 'input', 'output', 'coupling_control'], '未同步到模块设计。', 'zh')}\n\n"
            f"{render_named_items(as_list(technical.get('api_contracts')), ['contract', 'compatibility', 'old_consumer_impact'], '未同步到接口影响。', 'zh')}\n\n"
            f"{render_named_items(as_list(technical.get('interface_examples')), ['name', 'request', 'response', 'error_response'], '未同步到接口示例。', 'zh')}\n\n"
            "## 八、数据、权限、页面与异常场景\n\n"
            f"{render_named_items(as_list(technical.get('data_design')), ['read_rule', 'write_rule', 'migration'], '未同步到数据设计。', 'zh')}\n\n"
            f"{render_expert_technical_sections(technical, 'zh')}\n\n"
            f"{render_named_items(as_list(technical.get('permission_model')), ['role', 'rule', 'negative_case'], '未同步到权限规则。', 'zh')}\n\n"
            f"{render_named_items(as_list(technical.get('exception_and_edge_cases')), ['case', 'handling'], '未同步到异常场景。', 'zh')}\n\n"
            f"{render_named_items(as_list(technical.get('ui_ue_design')), ['page_or_route', 'user_goal', 'entry_point', 'permission_visibility', 'acceptance_evidence'], '未同步到页面影响。', 'zh')}\n\n"
            "## 九、架构与运维影响\n\n"
            f"{render_named_items(as_list(architecture.get('cross_repo_dependency_graph')), ['from', 'to', 'contract', 'change'], '未同步到跨仓依赖图。', 'zh')}\n\n"
            "### 模块/仓库关系图\n\n"
            f"{render_architecture_mermaid(architecture, 'zh')}\n\n"
            f"{render_named_items(as_list(architecture.get('integration_sequence')), ['step', 'actor', 'action', 'failure_handling'], '未同步到集成顺序。', 'zh')}\n\n"
            f"{render_named_items(as_list(architecture.get('deployment_impact_matrix')), ['repo', 'artifact', 'order', 'config_change', 'restart_required'], '未同步到发布影响矩阵。', 'zh')}\n\n"
            f"{render_named_items(as_list(architecture.get('rollback_strategy')), ['repo', 'steps', 'data_risk'], '未同步到回滚策略。', 'zh')}\n\n"
            "## 十、交付执行计划\n\n"
            f"{render_delivery_tasks(delivery_plan, 'zh')}\n\n"
            "## 十一、需求追踪关系\n\n"
            "- 追踪关系：每个设计决策必须能回到 `spec.json` 的验收标准，并向前关联到 `test_design.json` 测试用例、`delivery_plan.json` 任务和发布证据。\n"
            "- 如果任一验收标准缺少设计引用、测试用例或交付证据责任人，评审时应阻止进入实现。\n\n"
            "## 十二、测试策略摘要\n\n"
            f"- 本节只保留验收证据映射和测试策略摘要；详细测试用例维护在 `human/tests/{doc_id}.md` 与 `test_design.json`。\n\n"
            f"{render_named_items(as_list(technical.get('acceptance_mapping')), ['acceptance_id', 'design_refs', 'evidence_required'], '未同步到验收证据映射。', 'zh')}\n\n"
            f"{render_named_items(as_list(technical.get('test_strategy')), ['summary', 'type', 'evidence'], '未同步到测试策略。', 'zh')}\n\n"
            "## 十三、风险与未过门禁\n\n"
            f"{render_blockers(delivery_plan, architecture)}\n\n"
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
            f"{render_design_review_context(technical, architecture, delivery_plan, 'en')}\n\n"
            "## Current State, Problem, And Goals\n\n"
            f"{render_problem_analysis(technical, 'en')}\n\n"
            f"{render_named_items([architecture.get('current_architecture')], ['system_context', 'repo_entrypoints', 'upstream_downstream', 'constraints'], 'No current architecture analysis was synced.')}\n\n"
            "## Sub-Requirement Design Matrix\n\n"
            f"{render_requirement_breakdown_table(technical, 'en')}\n\n"
            "### Code Entrypoint Confidence\n\n"
            f"{render_entrypoint_confidence(technical, 'en')}\n\n"
            "### Field / API / Permission Impact\n\n"
            f"{render_field_api_permission_impact(technical, 'en')}\n\n"
            "### Low-Confidence Confirmation Items\n\n"
            f"{render_low_confidence_items(technical, architecture, 'en')}\n\n"
            "## Candidate Options, Comparison, And Decision\n\n"
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
            f"{render_expert_technical_sections(technical, 'en')}\n\n"
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
            "## Test Strategy Summary\n\n"
            f"- This section keeps only acceptance evidence mapping and test strategy summary. Detailed test cases live in `human/tests/{doc_id}.md` and `test_design.json`.\n\n"
            f"{render_named_items(as_list(technical.get('acceptance_mapping')), ['acceptance_id', 'design_refs', 'evidence_required'], 'No acceptance evidence mapping was synced.')}\n\n"
            f"{render_named_items(as_list(technical.get('test_strategy')), ['summary', 'type', 'evidence'], 'No test strategy was synced.')}\n\n"
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
