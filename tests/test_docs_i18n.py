from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


docs_i18n = load_module("docs_i18n", ROOT / "skills/core/docs-governor/scripts/docs_i18n.py")
doc_model = load_module("doc_model", ROOT / "skills/core/docs-governor/scripts/doc_model.py")
docs_governor = load_module("docs_governor", ROOT / "skills/core/docs-governor/scripts/docs_governor.py")
render_design_templates = load_module("render_design_templates", ROOT / "skills/templates/design-doc-templates/scripts/render_design_templates.py")


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_i18n_renders_status_without_translating_code_identifiers() -> None:
    value = {
        "table": "renewal_order",
        "field": "renewal_month",
        "type": "needs_confirmation",
        "rollback": "code rollback plus schema/data rollback plan if migration is applied",
    }
    rendered = docs_i18n.render_value(value, "zh")
    assert "表=renewal_order" in rendered
    assert "字段=renewal_month" in rendered
    assert "需结合代码和数据库核对" in rendered
    assert "如执行迁移" in rendered
    assert "{\"" not in rendered


def test_sync_inherits_existing_runtime_evidence_before_rendering_human_docs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = root / "docs"
        artifact_dir = root / "artifacts"
        doc_id = "REQ-RUNTIME-INHERIT"
        write_json(
            docs_root / "machine/raw" / doc_id / "runtime_sequence_evidence.json",
            {
                "actor": "运营人员",
                "frontend": {
                    "repo": "operate-platform-fe",
                    "page": "设备置换结算",
                    "route": "/device/replacementSettlement",
                    "entry_menu_or_button": "点击「试算」按钮",
                },
                "backend": {
                    "repo": "sigreal-operate-platform",
                    "controller": "ReplacementSettlementController",
                    "service": "ReplacementSettlementService",
                },
                "interactions": [
                    {
                        "scenario": "BRK-5 续期试算",
                        "trigger": "点击「试算」按钮",
                        "method": "POST",
                        "api": "/operate/api/device/replacementSettlement/renew/paging",
                        "backend_action": "ReplacementSettlementController.renewPaging -> ReplacementSettlementService.renewPaging",
                        "response": "返回续期结算明细分页",
                    }
                ],
            },
        )
        write_json(
            artifact_dir / "spec.json",
            {
                "schema": "codex-spec-v1",
                "doc_id": doc_id,
                "title": "续期试算",
                "requirements": [{"id": "REQ-1", "summary": "续期试算明细筛选"}],
                "acceptance_criteria": [{"id": "AC-1", "criteria": "续期试算明细按筛选条件返回", "type": "positive"}],
            },
        )
        write_json(artifact_dir / "technical_design.json", {"doc_id": doc_id, "module_decomposition": []})
        write_json(artifact_dir / "architecture_design.json", {"doc_id": doc_id, "cross_repo_dependency_graph": []})
        write_json(artifact_dir / "test_design.json", {"doc_id": doc_id, "test_cases": []})
        write_json(artifact_dir / "delivery_plan.json", {"doc_id": doc_id, "status": "ready", "tasks": []})

        result = docs_governor.sync(docs_root, doc_id, artifact_dir, "续期试算", doc_language="zh")

        assert result["decision"] == "pass"
        assert result["inherited_supplemental_artifacts"][0]["artifact"] == "runtime_sequence_evidence.json"
        assert (artifact_dir / "runtime_sequence_evidence.json").exists()
        design_doc = (docs_root / "human/designs" / f"{doc_id}.md").read_text(encoding="utf-8")
        assert "actor A as 运营人员" in design_doc
        assert "设备置换结算<br/>/device/replacementSettlement<br/>operate-platform-fe" in design_doc
        assert "ReplacementSettlementService<br/>sigreal-operate-platform" in design_doc
        assert "POST /operate/api/device/replacementSettlement/renew/paging" in design_doc


def test_sync_synthesizes_runtime_evidence_when_missing() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = root / "docs"
        artifact_dir = root / "artifacts"
        repo_root = root / "repo"
        (repo_root / "src/views/device").mkdir(parents=True)
        (repo_root / "src/views/device/replacementSettlement.vue").write_text(
            """
            export default {
              methods: {
                toggleRecentBatch() { this.recentBatchCollapsed = true }
              }
            }
            """,
            encoding="utf-8",
        )
        doc_id = "REQ-SYNTH-RUNTIME"
        write_json(
            artifact_dir / "spec.json",
            {
                "schema": "codex-spec-v1",
                "doc_id": doc_id,
                "title": "最近批量处理默认折叠",
                "actors": ["运营人员"],
                "acceptance_criteria": [{"id": "AC-1", "criteria": "最近批量处理默认折叠", "type": "positive"}],
            },
        )
        write_json(
            artifact_dir / "technical_design.json",
            {
                "doc_id": doc_id,
                "current_state_analysis": {
                    "business_problem": "最近批量处理默认折叠",
                    "process_gap": "进入页面后最近批量处理历史占用主要视图空间。",
                    "code_entrypoints": ["src/views/device/replacementSettlement.vue"],
                },
                "requirement_breakdown": [{"id": "BRK-1", "summary": "最近批量处理默认折叠"}],
                "module_decomposition": [
                    {
                        "module": "src/views/device/replacementSettlement.vue",
                        "responsibility": "默认折叠最近批量处理区域",
                        "input": "进入设备置换结算页面",
                        "output": "最近批量处理区域处于折叠状态",
                        "requirement_breakdown_id": "BRK-1",
                    }
                ],
                "api_contracts": [
                    {
                        "contract": "/device/replacementSettlement",
                        "requirement_breakdown_id": "BRK-1",
                    }
                ],
                "ui_ue_design": [
                    {
                        "page_or_route": "/device/replacementSettlement",
                        "user_goal": "最近批量处理默认折叠",
                        "entry_point": "进入设备置换结算页面",
                    }
                ],
            },
        )
        write_json(artifact_dir / "architecture_design.json", {"doc_id": doc_id})
        write_json(artifact_dir / "test_design.json", {"doc_id": doc_id, "test_cases": []})
        write_json(artifact_dir / "delivery_plan.json", {"doc_id": doc_id, "status": "ready", "tasks": []})
        write_json(
            artifact_dir / "project_understanding/code_index.json",
            {
                "schema": "codex-code-index-v1",
                "project": "operate-platform-fe",
                "repo_root": str(repo_root),
                "files": [
                    {
                        "path": "src/views/device/replacementSettlement.vue",
                        "symbols": ["toggleRecentBatch"],
                        "routes": ["/device/replacementSettlement"],
                    }
                ],
            },
        )
        write_json(
            artifact_dir / "project_understanding/api_surface.json",
            {
                "schema": "codex-api-surface-v1",
                "project": "operate-platform-fe",
                "routes": [
                    {
                        "kind": "frontend-route",
                        "route": "/device/replacementSettlement",
                        "file": "src/views/device/replacementSettlement.vue",
                    }
                ],
            },
        )

        result = docs_governor.sync(docs_root, doc_id, artifact_dir, "最近批量处理默认折叠", doc_language="zh")

        runtime_path = artifact_dir / "runtime_sequence_evidence.json"
        runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
        design_doc = (docs_root / "human/designs" / f"{doc_id}.md").read_text(encoding="utf-8")
        assert result["generated_runtime_evidence"]["generated"] is True
        assert runtime["actor"] == "运营人员"
        assert runtime["frontend"]["repo"] == "operate-platform-fe"
        assert runtime["interactions"][0]["api"] == "/device/replacementSettlement"
        assert "actor A as 运营人员" in design_doc
        assert "/device/replacementSettlement" in design_doc


def test_sync_synthesizes_backend_runtime_evidence_without_fake_frontend() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = root / "docs"
        artifact_dir = root / "artifacts"
        repo_root = root / "repo"
        controller = repo_root / "operate-provider/src/main/java/com/acme/operate/controller/RenewController.java"
        controller.parent.mkdir(parents=True)
        controller.write_text(
            """
            @RestController
            class RenewController {
              @PostMapping("/api/device/renew/trial")
              public TrialResult trial(@RequestBody TrialRequest request) {
                return service.trial(request);
              }
            }
            """,
            encoding="utf-8",
        )
        doc_id = "REQ-SYNTH-BACKEND-RUNTIME"
        write_json(
            artifact_dir / "spec.json",
            {
                "schema": "codex-spec-v1",
                "doc_id": doc_id,
                "title": "续费试算",
                "actors": ["user"],
                "acceptance_criteria": [{"id": "AC-1", "criteria": "续费试算返回金额", "type": "positive"}],
            },
        )
        write_json(
            artifact_dir / "technical_design.json",
            {
                "doc_id": doc_id,
                "current_state_analysis": {
                    "business_problem": "当前试算范围未覆盖目标设备。",
                    "code_entrypoints": ["operate-provider/src/main/java/com/acme/operate/controller/RenewController.java"],
                },
                "requirement_breakdown": [{"id": "BRK-1", "summary": "续费试算返回金额"}],
                "module_decomposition": [
                    {
                        "module": "operate-provider/src/main/java/com/acme/operate/controller/RenewController.java",
                        "responsibility": "接收续费试算请求并返回试算金额",
                        "input": "TrialRequest",
                        "output": "TrialResult",
                        "requirement_breakdown_id": "BRK-1",
                    }
                ],
                "api_contracts": [
                    {
                        "contract": '@PostMapping("/api/device/renew/trial") (operate-provider/src/main/java/com/acme/operate/controller/RenewController.java)',
                        "requirement_breakdown_id": "BRK-1",
                    }
                ],
                "ui_ue_design": [
                    {
                        "page_or_route": '@PostMapping("/api/device/renew/trial") (operate-provider/src/main/java/com/acme/operate/controller/RenewController.java)',
                        "user_goal": "续费试算",
                        "entry_point": "existing entry",
                    }
                ],
            },
        )
        write_json(artifact_dir / "architecture_design.json", {"doc_id": doc_id})
        write_json(artifact_dir / "test_design.json", {"doc_id": doc_id, "test_cases": []})
        write_json(artifact_dir / "delivery_plan.json", {"doc_id": doc_id, "status": "ready", "tasks": []})
        write_json(
            artifact_dir / "project_understanding/code_index.json",
            {
                "schema": "codex-code-index-v1",
                "project": "sigreal-operate-platform",
                "repo_root": str(repo_root),
                "files": [
                    {
                        "path": "operate-provider/src/main/java/com/acme/operate/controller/RenewController.java",
                        "symbols": ["RenewController", "trial"],
                    }
                ],
            },
        )
        write_json(
            artifact_dir / "project_understanding/api_surface.json",
            {
                "schema": "codex-api-surface-v1",
                "project": "sigreal-operate-platform",
                "routes": [
                    {
                        "kind": "spring-controller",
                        "route": "/api/device/renew/trial",
                        "file": "operate-provider/src/main/java/com/acme/operate/controller/RenewController.java",
                    }
                ],
            },
        )

        result = docs_governor.sync(docs_root, doc_id, artifact_dir, "续费试算", doc_language="zh")

        runtime = json.loads((artifact_dir / "runtime_sequence_evidence.json").read_text(encoding="utf-8"))
        design_doc = (docs_root / "human/designs" / f"{doc_id}.md").read_text(encoding="utf-8")
        assert result["generated_runtime_evidence"]["generated"] is True
        assert runtime["actor"] == "业务操作人"
        assert runtime["frontend"].get("route") is None
        assert runtime["interactions"][0].get("frontend_functions") is None
        assert runtime["interactions"][0]["backend_methods"] == ["RenewController", "trial"]
        assert runtime["interactions"][0]["trigger"].startswith("调用 POST /api/device/renew/trial")
        assert "POST /api/device/renew/trial" in design_doc
        assert "打开 @PostMapping" not in design_doc


def test_zh_text_preserves_unquoted_command_tokens() -> None:
    rendered = docs_governor.zh_text("npm run build:test evidence; mvn -pl operate-provider -DskipTests compile evidence")
    readable = docs_governor.render_readable_value(["npm run build:test evidence"], "zh")

    assert "npm run build:test" in rendered
    assert "mvn -pl operate-provider -DskipTests compile" in rendered
    assert "npm run build:测试" not in rendered
    assert "npm run build:test" in readable
    assert "npm run build:测试" not in readable
    named = docs_governor.render_named_items(
        [{"summary": "Validate acceptance criteria", "type": "strategy_summary", "evidence": ["npm run build:test evidence"]}],
        ["summary", "type", "evidence"],
        "empty",
        "zh",
    )
    assert "npm run build:test" in named
    assert "npm run build:测试" not in named


def test_i18n_renders_nested_design_keys_for_human_docs() -> None:
    value = {
        "business_object": "dashboard",
        "owner_module": "target module to be confirmed",
        "confirmation_required": True,
        "read_write_rules": {"read": "confirm query source", "write": "confirm write entrypoint"},
        "sequence": [{"step": 1, "mode": "sync", "success": "contract compatible", "failure": "preserve existing failure behavior"}],
    }
    rendered = docs_i18n.render_value(value, "zh")
    assert "业务对象=dashboard" in rendered
    assert "责任模块=需结合代码核对的责任模块" in rendered
    assert "是否需要核对=是" in rendered
    assert "读取=confirm query source" in rendered
    assert "写入=confirm write entrypoint" in rendered
    assert "方式=sync" in rendered
    assert "成功处理=contract compatible" in rendered
    assert "失败处理=保持既有失败处理方式" in rendered
    assert "business_object" not in rendered
    assert "owner_module" not in rendered
    assert "confirmation_required" not in rendered


def test_i18n_renders_common_design_template_phrases() -> None:
    rendered = docs_i18n.render_value(
        [
            "Use existing contracts and avoid duplicating upstream business rules.",
            "No API impact confirmed yet",
            "preserve existing consumers unless design updates contract",
            "review route consumers before implementation",
            "none unless this slice changes schema/data backfill",
            "no API request expected",
            "confirm only unless implementation proves contract change is required",
            "existing deploy artifact",
        ],
        "zh",
    )
    assert "复用现有契约，避免重复实现上游业务规则。" in rendered
    assert "尚未确认 API 影响" in rendered
    assert "除非设计更新契约，否则保持现有消费方不受影响" in rendered
    assert "实施前检查路由消费方" in rendered
    assert "除非该子需求改变表结构或数据回填，否则无需迁移" in rendered
    assert "预计无 API 请求变更" in rendered
    assert "默认仅确认契约影响，除非实现证明必须变更契约" in rendered
    assert "现有部署制品" in rendered
    assert "No API impact confirmed yet" not in rendered
    assert "Use existing contracts" not in rendered


def test_render_named_items_splits_dense_human_rows() -> None:
    rendered = docs_governor.render_named_items(
        [
            {
                "applicable": True,
                "entities": [{"business_object": "dashboard", "owner_module": "target module to be confirmed"}],
                "field_rules": [{"field": "status", "meaning": "status"}],
                "ownership": "target module to be confirmed owns code changes",
            }
        ],
        ["applicable", "entities", "field_rules", "ownership"],
        "missing",
        "zh",
    )
    assert "- 是否适用：是" in rendered
    assert "  - 实体/表候选：" in rendered
    assert "  - 字段规则：" in rendered
    assert "business_object" not in rendered


def test_system_sequence_mermaid_uses_readable_participants_and_branches() -> None:
    rendered = docs_governor.render_system_sequence_mermaid(
        {
            "system_interaction_sequence": {
                "applicable": True,
                "participants": ["用户或客户端", "订单服务", "现有契约"],
                "sequence": [
                    {
                        "from": "用户或客户端",
                        "to": "订单服务",
                        "mode": "sync",
                        "action": "提交导出请求",
                        "success": "返回导出任务",
                        "failure": "保留既有错误处理",
                    },
                    {
                        "from": "订单服务",
                        "to": "现有契约",
                        "mode": "sync",
                        "action": "复用既有查询契约",
                        "success": "契约兼容",
                        "failure": "超时后降级",
                    },
                ],
                "timeout_retry": "同步调用需确认超时、重试次数和用户可见错误",
                "idempotency": "写操作绑定业务幂等键",
                "consistency": "避免分布式事务",
            }
        },
        "zh",
    )
    assert "sequenceDiagram" in rendered
    assert "autonumber" in rendered
    assert "participant P1 as 用户/客户端" in rendered
    assert "participant P2 as 订单服务" in rendered
    assert "______" not in rendered
    assert "Note over P1,P2,P3" not in rendered
    assert "P1->>P2: 提交导出请求 [sync]" in rendered
    assert "P2->>P3: 复用既有查询契约 [sync]" in rendered
    assert "P3-->>P2: 契约兼容" in rendered
    assert "P2-->>P1: 返回导出任务" in rendered
    assert "P3-->>P1" not in rendered
    assert "alt 正常返回" in rendered
    assert "else 异常或降级" in rendered
    assert "opt 超时与重试" in rendered
    assert "opt 幂等与一致性" in rendered
    assert "；" not in "\n".join(line for line in rendered.splitlines() if "Note over" in line)
    assert "activate P2" not in rendered
    assert rendered.count("alt 正常返回") == 1


def test_process_mermaid_renders_reviewable_flow_lanes() -> None:
    rendered = docs_governor.render_process_mermaid(
        {
            "process_flow": [
                {
                    "flow_name": "订单导出",
                    "actors": ["管理员", "订单服务"],
                    "success_end_state": "Acceptance criteria pass.",
                    "failure_end_states": ["Validation failure", "Dependency unavailable"],
                    "steps": [
                        {
                            "actor": "管理员",
                            "action": "选择筛选条件并提交导出",
                            "output": "生成导出任务",
                        },
                        {
                            "actor": "订单服务",
                            "action": "校验权限并读取订单",
                            "output": "返回导出文件",
                        },
                    ],
                }
            ]
        },
        "zh",
    )
    assert "flowchart TD" in rendered
    assert 'subgraph F1["1. 订单导出"]' in rendered
    assert 'F1_START((" 开始 ")):::startEnd' in rendered
    assert "管理员<br/>选择筛选条件并提交导出<br/>=> 生成导出任务" in rendered
    assert "订单服务<br/>校验权限并读取订单<br/>=> 返回导出文件" in rendered
    assert "成功: 验收标准通过。" in rendered
    assert "异常/失败: 校验失败, 依赖不可用" in rendered
    assert "-.->" in rendered
    assert "classDef action" in rendered


def test_engineering_sequence_includes_reused_contract_for_single_repo_boundary() -> None:
    rendered = docs_governor.render_system_sequence_mermaid(
        {"system_interaction_sequence": {"applicable": True, "participants": ["用户或客户端"], "sequence": ["用户点击"]}},
        "zh",
        {
            "integration_sequence": [
                {
                    "requirement_breakdown_id": "BRK-1",
                    "action": "结算订单模块新增并填充字段：`续期月份`。",
                }
            ],
            "cross_repo_dependency_graph": [
                {
                    "from": "operate-platform-fe",
                    "to": "operate-platform-fe",
                    "contract": "/device/orderPivot",
                    "change": "confirm only unless implementation proves contract change is required",
                }
            ],
            "deployment_impact_matrix": [{"repo": "operate-platform-fe", "artifact": "existing deploy artifact", "order": 1}],
        },
    )
    assert "单仓/单工程变更" not in rendered
    assert "actor A as 业务参与方" in rendered
    assert "participant B as 浏览器/前端<br/>operate-platform-fe" in rendered
    assert "participant C as 后端接口/既有契约<br/>需确认真实服务" in rendered
    assert "A->>B: BRK-1: 结算订单模块新增并填充字段" in rendered
    assert "B->>C: BRK-1: 请求/复用 /device/orderPivot" in rendered
    assert "C-->>B: BRK-1: 默认仅确认契约影响，除非实现证明必须变更契约" in rendered
    assert "B-->>A: BRK-1: 更新页面反馈" in rendered
    assert "用户/客户端" not in rendered


def test_runtime_sequence_evidence_overrides_generic_architecture_sequence() -> None:
    rendered = docs_governor.render_system_sequence_mermaid(
        {"system_interaction_sequence": {"applicable": True}},
        "zh",
        {
            "cross_repo_dependency_graph": [
                {"from": "operate-platform-fe", "to": "operate-platform-fe", "contract": "/device/orderPivot"}
            ]
        },
        {
            "actor": "运营人员",
            "frontend": {
                "repo": "operate-platform-fe",
                "page": "设备置换结算",
                "route": "/device/replacementSettlement",
            },
            "backend": {
                "repo": "sigreal-operate-platform",
                "controller": "ReplacementSettlementController",
                "service": "ReplacementSettlementService",
            },
            "interactions": [
                {
                    "scenario": "BRK-5 续期试算明细筛选",
                    "trigger": "点击「试算」按钮",
                    "method": "POST",
                    "api": "/operate/api/device/replacementSettlement/renew/paging",
                    "request": "携带租户、自有车、续期池状态等筛选条件",
                    "backend_action": "ReplacementSettlementController.renewPaging -> ReplacementSettlementService.renewPaging",
                    "response": "返回续期结算明细分页",
                    "failure": "筛选条件非法或查询失败",
                }
            ],
        },
    )
    assert "actor A as 运营人员" in rendered
    assert "设备置换结算<br/>/device/replacementSettlement<br/>operate-platform-fe" in rendered
    assert "ReplacementSettlementService<br/>sigreal-operate-platform" in rendered
    assert "点击「试算」按钮" in rendered
    assert "POST /operate/api/device/replacementSettlement/renew/paging" in rendered
    assert "ReplacementSettlementController.renewPaging" in rendered
    assert "业务参与方" not in rendered
    assert "需确认真实服务" not in rendered


def test_runtime_sequence_evidence_supports_multi_hop_backend_calls() -> None:
    rendered = docs_governor.render_system_sequence_mermaid(
        {},
        "zh",
        {},
        {
            "actor": "运营人员",
            "frontend": {"repo": "operate-platform-fe", "page": "设备置换结算", "route": "/device/replacementSettlement"},
            "backend": {
                "repo": "sigreal-operate-platform",
                "controller": "ReplacementSettlementController",
                "service": "ReplacementSettlementService",
            },
            "downstreams": [
                {"key": "contract", "name": "合同服务", "repo": "sigreal-operate-platform"},
                {"key": "upms", "name": "租户权限服务", "repo": "sigreal-upms"},
                {"key": "mq", "name": "续期结算消息", "repo": "Kafka"},
            ],
            "interactions": [
                {
                    "scenario": "BRK-5 续期试算",
                    "trigger": "点击「试算」按钮",
                    "method": "POST",
                    "api": "/operate/api/device/replacementSettlement/renew/paging",
                    "backend_action": "ReplacementSettlementController.renewPaging -> ReplacementSettlementService.renewPaging",
                    "calls": [
                        {"from": "backend", "to": "contract", "action": "查询合同续期费用口径", "response": "返回合同费用和规则版本"},
                        {"from": "contract", "to": "upms", "action": "按租户范围校验数据权限", "response": "返回可见租户集合"},
                        {"from": "backend", "to": "mq", "action": "发布续期试算审计事件", "mode": "async"},
                    ],
                    "response": "返回续期明细分页",
                }
            ],
        },
    )
    assert "participant D1 as 合同服务<br/>sigreal-operate-platform" in rendered
    assert "participant D2 as 租户权限服务<br/>sigreal-upms" in rendered
    assert "participant D3 as 续期结算消息<br/>Kafka" in rendered
    assert "C->>D1: 查询合同续期费用口径" in rendered
    assert "D1-->>C: 返回合同费用和规则版本" in rendered
    assert "D1->>D2: 按租户范围校验数据权限" in rendered
    assert "D2-->>D1: 返回可见租户集合" in rendered
    assert "C->>D3: 发布续期试算审计事件 [async]" in rendered


def test_architecture_mermaid_prefers_runtime_evidence_and_downstream_calls() -> None:
    rendered = docs_governor.render_architecture_mermaid(
        {
            "cross_repo_dependency_graph": [
                {"from": "operate-platform-fe", "to": "operate-platform-fe", "contract": "/device/orderPivot"}
            ]
        },
        "zh",
        {
            "frontend": {"repo": "operate-platform-fe", "page": "设备置换结算", "route": "/device/replacementSettlement"},
            "backend": {"repo": "sigreal-operate-platform", "service": "ReplacementSettlementService"},
            "downstreams": [{"key": "upms", "name": "租户权限服务", "repo": "sigreal-upms"}],
            "interactions": [
                {
                    "method": "POST",
                    "api": "/operate/api/device/replacementSettlement/renew/paging",
                    "calls": [{"from": "backend", "to": "upms", "action": "校验租户数据范围"}],
                }
            ],
        },
    )
    assert "operate-platform-fe<br/>设备置换结算<br/>/device/replacementSettlement" in rendered
    assert "POST /operate/api/device/replacementSettlement/renew/paging" in rendered
    assert "sigreal-operate-platform<br/>ReplacementSettlementService" in rendered
    assert "租户权限服务<br/>sigreal-upms" in rendered
    assert "B -->|校验租户数据范围| DS1" in rendered
    assert "/device/orderPivot" not in rendered


def test_dependency_graph_items_prefer_runtime_evidence_over_stale_architecture() -> None:
    rendered = docs_governor.render_dependency_graph_items(
        {
            "cross_repo_dependency_graph": [
                {"from": "operate-platform-fe", "to": "operate-platform-fe", "contract": "/device/orderPivot"}
            ]
        },
        {
            "frontend": {"repo": "operate-platform-fe", "page": "设备置换结算"},
            "backend": {"repo": "sigreal-operate-platform", "service": "ReplacementSettlementService"},
            "downstreams": [{"key": "upms", "name": "租户权限服务", "repo": "sigreal-upms"}],
            "interactions": [
                {
                    "method": "POST",
                    "api": "/operate/api/device/replacementSettlement/renew/paging",
                    "calls": [{"from": "backend", "to": "upms", "action": "校验租户数据范围"}],
                }
            ],
        },
        "zh",
    )
    assert "来源：operate-platform-fe / 设备置换结算" in rendered
    assert "契约/API：POST /operate/api/device/replacementSettlement/renew/paging" in rendered
    assert "目标：sigreal-operate-platform / ReplacementSettlementService" in rendered
    assert "下游：backend -> 租户权限服务 / sigreal-upms" in rendered
    assert "/device/orderPivot" not in rendered


def test_runtime_api_contracts_render_request_response_and_error_semantics() -> None:
    rendered = docs_governor.render_runtime_api_contracts(
        {
            "api_contracts": [
                {
                    "name": "续期结算明细分页",
                    "method": "POST",
                    "path": "/operate/api/device/replacementSettlement/renew/paging",
                    "frontend_caller": "点击「试算」后 fetchRenewPaging",
                    "controller": "ReplacementSettlementController.renewPaging",
                    "service": "ReplacementSettlementService.renewPaging",
                    "request_dto": "BasePage<ReplacementSettlementQueryDto>",
                    "request_fields": [
                        {"name": "condition.rootTenantId", "type": "Long", "required": False, "meaning": "运营总公司"},
                        {"name": "condition.poolStatuses", "type": "List<String>", "required": False, "default": "PENDING,EXPIRED", "enum": "PENDING/EXPIRED", "meaning": "续期池状态"},
                    ],
                    "response_vo": "PagingInfoVo<ReplacementSettlementItemVo>",
                    "response_fields": [
                        {"name": "list[].renewRecordId", "type": "Long", "meaning": "续期池 ID"},
                        {"name": "total", "type": "Long", "meaning": "总条数"},
                    ],
                    "error_semantics": ["查询失败时前端提示续期结算明细查询失败"],
                    "compatibility": "筛选条件必须完整透传",
                }
            ]
        },
        "zh",
    )
    assert "### API 契约设计" in rendered
    assert "API：`POST /operate/api/device/replacementSettlement/renew/paging`" in rendered
    assert "后端承接：ReplacementSettlementController.renewPaging -> ReplacementSettlementService.renewPaging" in rendered
    assert "请求 DTO：`BasePage<ReplacementSettlementQueryDto>`" in rendered
    assert "`condition.rootTenantId`；Long；可选；运营总公司" in rendered
    assert "`condition.poolStatuses`；List<String>；可选；默认=PENDING,EXPIRED；枚举=PENDING/EXPIRED；续期池状态" in rendered
    assert "响应 VO：`PagingInfoVo<ReplacementSettlementItemVo>`" in rendered
    assert "`list[].renewRecordId`；Long；续期池 ID" in rendered
    assert "查询失败时前端提示续期结算明细查询失败" in rendered
    assert "兼容性：筛选条件必须完整透传" in rendered


def test_runtime_data_model_renders_source_backed_tables_and_dto_boundary() -> None:
    rendered = docs_governor.render_runtime_data_model(
        {
            "data_models": [
                {
                    "entity": "ObdDeviceRenewPool",
                    "table": "obd_device_renew_pool",
                    "owner": "sigreal-operate-platform / ObdDeviceRenewService",
                    "operation": "续期池明细查询读取；单个/批量不续期写入 exclude_reason 与 exclude_reason_code",
                    "fields": [
                        {"name": "poolStatus", "column": "pool_status", "type": "String", "nullable": False, "meaning": "续期池状态"},
                        {"name": "excludeReasonCode", "column": "exclude_reason_code", "type": "String", "nullable": True, "meaning": "不续期原因编码"},
                    ],
                    "migration": "复用既有字段；本设计不要求新增表结构",
                    "evidence": "ObdDeviceRenewPool.java @TableName",
                }
            ],
            "api_contracts": [
                {
                    "request_dto": "RenewPoolManualExcludeDto",
                    "response_vo": "ResultVo<String>",
                }
            ],
        },
        "zh",
    )
    assert "### 数据模型与表结构" in rendered
    assert "表名：`obd_device_renew_pool`" in rendered
    assert "`poolStatus`；column=`pool_status`；String；非空；续期池状态" in rendered
    assert "`excludeReasonCode`；column=`exclude_reason_code`；String；可空；不续期原因编码" in rendered
    assert "复用既有字段；本设计不要求新增表结构" in rendered
    assert "入参模型：`RenewPoolManualExcludeDto`" in rendered
    assert "出参模型：`ResultVo<String>`" in rendered
    assert "表=需结合代码和数据库核对" not in rendered


def test_runtime_exception_cases_use_real_interaction_and_contract_errors() -> None:
    rendered = docs_governor.render_runtime_exception_cases(
        {
            "interactions": [
                {
                    "scenario": "批量移出不续期",
                    "failure": "未录入设备号、未选原因或原因说明不足时前端拦截；后端失败时展示错误信息",
                }
            ],
            "api_contracts": [
                {
                    "name": "结算单分页查询",
                    "error_semantics": ["查询失败时前端提示结算单查询失败；接口仍返回 ResultVo code/message"],
                }
            ],
        },
        "zh",
    )
    assert "### 异常与边界场景" in rendered
    assert "场景：批量移出不续期；处理方式：未录入设备号、未选原因或原因说明不足时前端拦截" in rendered
    assert "场景：结算单分页查询；处理方式：查询失败时前端提示结算单查询失败" in rendered
    assert "后端仍需保留参数校验、状态校验和 ResultVo code/message 错误语义" in rendered
    assert "missing/invalid input" not in rendered
    assert "return validation error or preserve existing fallback" not in rendered


def test_runtime_data_access_and_permission_replace_template_rules() -> None:
    evidence = {
        "frontend": {"page": "设备置换结算", "route": "/device/replacementSettlement"},
        "data_models": [
            {
                "entity": "ObdDeviceRenewPool",
                "table": "obd_device_renew_pool",
                "operation": "查询续期池明细；单个/批量不续期写入原因",
                "migration": "复用既有字段",
            }
        ],
        "interactions": [
            {"trigger": "点击「批量不续期」按钮"},
            {"trigger": "点击「移出不续期」按钮"},
        ],
    }
    data_rendered = docs_governor.render_runtime_data_access(evidence, "zh")
    permission_rendered = docs_governor.render_runtime_permission_model(evidence, "zh")
    assert "### 数据读写摘要" in data_rendered
    assert "`obd_device_renew_pool`：查询续期池明细；单个/批量不续期写入原因" in data_rendered
    assert "结构影响：复用既有字段" in data_rendered
    assert "### 权限与可见性" in permission_rendered
    assert "页面边界：设备置换结算 / /device/replacementSettlement 沿用现有菜单/按钮权限" in permission_rendered
    assert "原因必填、续期池状态和租户范围仍需后端校验" in permission_rendered
    assert "preserve existing permission boundary" not in permission_rendered
    assert "unauthorized user cannot access changed behavior" not in permission_rendered


def test_runtime_subrequirement_design_answers_expert_review_questions() -> None:
    rendered = docs_governor.render_runtime_subrequirement_design(
        {
            "acceptance_criteria": [
                {"id": "AC-3", "criteria": "运营人员可以批量录入或导入不续期设备号，并触发批量移出续期池。"}
            ]
        },
        {
            "frontend": {
                "repo": "operate-platform-fe",
                "page": "设备置换结算",
                "route": "/device/replacementSettlement",
                "source_file": "src/views/device/replacementSettlement.vue",
            },
            "backend": {
                "repo": "sigreal-operate-platform",
                "controller": "OBDDeviceRenewController",
                "service": "ObdDeviceRenewService",
            },
            "data_models": [{"table": "obd_device_renew_pool"}],
            "interactions": [
                {
                    "scenario": "BRK-3 批量录入不续期设备号",
                    "trigger": "点击「批量不续期」按钮并提交弹窗",
                    "method": "POST",
                    "api": "/operate/api/device/renewPool/batchExclude",
                    "request": "提交 deviceNumbers、reasonCode、reason",
                    "current_gap": "批量不续期当前缺少设备号和原因的完整提交与刷新闭环。",
                    "frontend_functions": ["openBatchExcludeDialog", "submitExcludeRenew", "fetchRenewPaging"],
                    "field_bindings": ["批量设备号输入 -> deviceNumbers", "原因下拉 -> reasonCode"],
                    "frontend_validation": ["deviceNumbers 不能为空", "reasonCode 必选"],
                    "backend_methods": ["OBDDeviceRenewController.batchExcludeRenewPool", "ObdDeviceRenewService.manualExcludeRenewPools"],
                    "backend_rules": ["校验原因必填", "写入续期池不续期状态"],
                    "data_operations": ["写入 obd_device_renew_pool.exclude_reason_code/exclude_reason"],
                    "backend_action": "OBDDeviceRenewController.batchExcludeRenewPool -> ObdDeviceRenewService.manualExcludeRenewPools",
                    "response": "返回批量移出结果并刷新续期汇总和明细",
                    "failure": "未录入设备号、未选原因或原因说明不足时阻止提交",
                }
            ],
        },
        "zh",
    )
    assert "### 子需求落地设计" in rendered
    assert "#### BRK-3 批量录入不续期设备号" in rendered
    assert "当前现状：运营人员在 `operate-platform-fe / 设备置换结算 / /device/replacementSettlement` 触发" in rendered
    assert "批量不续期当前缺少设备号和原因的完整提交与刷新闭环" in rendered
    assert "涉及函数：`openBatchExcludeDialog`、`submitExcludeRenew`、`fetchRenewPaging`" in rendered
    assert "字段/控件绑定：批量设备号输入 -> deviceNumbers；原因下拉 -> reasonCode" in rendered
    assert "前端校验：deviceNumbers 不能为空；reasonCode 必选" in rendered
    assert "涉及方法：`OBDDeviceRenewController.batchExcludeRenewPool`、`ObdDeviceRenewService.manualExcludeRenewPools`" in rendered
    assert "实现规则：校验原因必填；写入续期池不续期状态" in rendered
    assert "前端做法：在 `src/views/device/replacementSettlement.vue`" in rendered
    assert "`POST /operate/api/device/renewPool/batchExclude`" in rendered
    assert "`sigreal-operate-platform / OBDDeviceRenewController / ObdDeviceRenewService`" in rendered
    assert "`obd_device_renew_pool`" in rendered
    assert "关键断言：" in rendered
    assert "AC-3: 运营人员可以批量录入或导入不续期设备号" in rendered
    assert "确认该切片涉及的字段" not in rendered
    assert "校准展示、筛选、状态、原因或刷新结果" not in rendered
    assert "现有链路必须证明请求口径" not in rendered


def test_runtime_entrypoint_delivery_and_acceptance_proof_override_stale_plan() -> None:
    evidence = {
        "frontend": {
            "repo": "operate-platform-fe",
            "page": "设备置换结算",
            "route": "/device/replacementSettlement",
            "source_file": "src/views/device/replacementSettlement.vue",
        },
        "backend": {
            "repo": "sigreal-operate-platform",
            "controller": "ReplacementSettlementController",
            "service": "ReplacementSettlementService",
            "source_files": ["operate-provider/src/main/java/com/sigreal/operate/controller/ReplacementSettlementController.java"],
        },
        "interactions": [
                {
                    "scenario": "BRK-5 续期试算明细遵循筛选条件",
                    "trigger": "点击「试算」按钮",
                    "method": "POST",
                    "api": "/operate/api/device/replacementSettlement/renew/paging",
                    "request": "提交 rootTenantId、shortTermRental、poolStatuses",
                }
        ],
    }
    entrypoint = docs_governor.render_runtime_entrypoint_confidence(evidence, "zh")
    delivery = docs_governor.render_runtime_delivery_tasks(
        {"repo_tasks": [{"repo": "operate-platform-fe", "allowed_files": ["src/views/device/device.vue"]}]},
        evidence,
        "zh",
    )
    proof = docs_governor.render_runtime_acceptance_proof(
        {"acceptance_criteria": [{"id": "AC-5", "criteria": "续期试算明细查询时，租户、自有车等筛选条件在明细接口中生效。"}]},
        evidence,
        "zh",
    )
    assert "置信度：`高`" in entrypoint
    assert "no_code_index" not in entrypoint
    assert "`src/views/device/replacementSettlement.vue`" in entrypoint
    assert "src/views/device/device.vue" not in delivery
    assert "允许修改文件：`src/views/device/replacementSettlement.vue`" in delivery
    assert "ReplacementSettlementController.java" in delivery
    assert "| `AC-5` | `BRK-5` | 续期试算明细查询时" in proof
    assert "POST /operate/api/device/replacementSettlement/renew/paging" in proof
    assert "请求参数包含并生效" in proof
    assert "页面展示、接口参数、返回字段和数据落库均满足该验收" not in proof


def test_runtime_acceptance_mapping_supports_dynamic_brk_count() -> None:
    evidence = {
        "frontend": {"repo": "ops-fe", "page": "批量任务", "route": "/jobs"},
        "backend": {"repo": "ops-api", "controller": "JobController", "service": "JobService"},
        "interactions": [
            {
                "scenario": "BRK-8 批量重试失败任务",
                "acceptance_ids": ["AC-12"],
                "trigger": "点击「批量重试」按钮",
                "method": "POST",
                "api": "/api/jobs/retry",
                "backend_action": "JobController.retry -> JobService.retryFailedJobs",
                "response": "返回重试任务数",
            }
        ],
    }
    spec = {
        "acceptance_criteria": [
            {"id": "AC-12", "criteria": "运营人员可以批量重试失败任务，并看到重试任务数。"}
        ]
    }
    rendered = docs_governor.render_runtime_subrequirement_design(spec, evidence, "zh")
    proof = docs_governor.render_runtime_acceptance_proof(spec, evidence, "zh")
    assert "#### BRK-8 批量重试失败任务" in rendered
    assert "AC-12: 运营人员可以批量重试失败任务" in rendered
    assert "| `AC-12` | `BRK-8` | 运营人员可以批量重试失败任务" in proof
    assert "BRK-5" not in rendered


def test_runtime_review_context_prefers_runtime_counts() -> None:
    rendered = docs_governor.render_design_review_context(
        {"module_decomposition": [], "api_contracts": []},
        {"cross_repo_dependency_graph": []},
        {"repo_tasks": [{"repo": "frontend-only"}]},
        "zh",
        {
            "frontend": {"repo": "operate-platform-fe"},
            "backend": {"repo": "sigreal-operate-platform"},
            "data_models": [{"table": "obd_device_renew_pool"}, {"table": "obd_replacement_settlement_order"}],
            "interactions": [
                {"method": "POST", "api": "/api/a"},
                {"method": "POST", "api": "/api/b"},
            ],
        },
    )
    assert "2 个模块、2 个接口/契约、1 条跨仓或模块依赖" in rendered
    assert "交付计划覆盖 2 个仓库" in rendered


def test_runtime_acceptance_proof_uses_command_assertion_for_build_ac() -> None:
    rendered = docs_governor.render_runtime_acceptance_proof(
        {
            "acceptance_criteria": [
                {
                    "id": "AC-6",
                    "criteria": "前端通过 `npm run build:test`；后端至少通过 `mvn -pl operate-provider -DskipTests compile`。",
                }
            ]
        },
        {
            "interactions": [
                {
                    "scenario": "BRK-5 续期试算明细遵循筛选条件",
                    "acceptance_ids": ["AC-6"],
                    "trigger": "点击「试算」按钮",
                    "method": "POST",
                    "api": "/operate/api/device/replacementSettlement/renew/paging",
                }
            ]
        },
        "zh",
    )
    assert "执行并记录构建命令 `npm run build:test`、`mvn -pl operate-provider -DskipTests compile`" in rendered
    assert "请求参数包含并生效" not in rendered


def test_runtime_decision_summary_expands_candidate_options_before_decision() -> None:
    rendered = docs_governor.render_runtime_decision_summary(
        {
            "frontend": {"source_file": "src/views/device/replacementSettlement.vue"},
            "backend": {"source_files": ["operate-provider/src/main/java/Controller.java"]},
            "interactions": [{"method": "POST", "api": "/api/renew/paging"}],
        },
        "zh",
    )
    assert "### 候选方案详述" in rendered
    assert "#### 方案 `R1`" in rendered
    assert "#### 方案 `R2`" in rendered
    assert "#### 方案 `R3`" in rendered
    assert "### 方案对比与选择" in rendered
    assert "### 决策结论" in rendered
    assert rendered.index("#### 方案 `R1`") < rendered.index("### 决策结论")
    assert "方案决策摘要" not in rendered


def test_runtime_sequence_diagram_includes_database_when_models_exist() -> None:
    rendered = docs_governor.render_runtime_sequence_evidence(
        {
            "actor": "运营人员",
            "frontend": {"repo": "operate-platform-fe", "page": "设备置换结算", "route": "/device/replacementSettlement"},
            "backend": {"repo": "sigreal-operate-platform", "service": "ReplacementSettlementService"},
            "data_models": [{"table": "obd_device_renew_pool"}, {"table": "obd_replacement_settlement_order"}],
            "interactions": [
                {
                    "scenario": "BRK-5 续期试算",
                    "trigger": "点击试算",
                    "method": "POST",
                    "api": "/api/renew/paging",
                    "backend_action": "ReplacementSettlementController.renewPaging -> ReplacementSettlementService.renewPaging",
                    "data_operations": ["读取 obd_device_renew_pool.pool_status"],
                    "response": "返回分页",
                }
            ],
        },
        "zh",
    )
    assert "participant DB as 数据库表" in rendered
    assert "obd_device_renew_pool" in rendered
    assert "C->>DB: 读取 obd_device_renew_pool.pool_status" in rendered


def test_runtime_module_and_ui_design_replace_template_placeholders() -> None:
    evidence = {
        "frontend": {
            "repo": "operate-platform-fe",
            "page": "设备置换结算",
            "route": "/device/replacementSettlement",
            "entry_menu_or_button": "设备管理工作台 -> 更换结算；点击「试算」按钮",
        },
        "backend": {"repo": "sigreal-operate-platform", "service": "ReplacementSettlementService"},
        "api_contracts": [
            {
                "name": "续期结算明细分页",
                "method": "POST",
                "path": "/operate/api/device/replacementSettlement/renew/paging",
            }
        ],
        "interactions": [
            {"trigger": "点击「试算」按钮"},
            {"trigger": "点击「批量不续期」按钮"},
        ],
    }
    module_rendered = docs_governor.render_runtime_module_design(evidence, "zh")
    ui_rendered = docs_governor.render_runtime_ui_impact(evidence, "zh")
    assert "### 模块职责划分" in module_rendered
    assert "前端模块：operate-platform-fe / 设备置换结算 / /device/replacementSettlement" in module_rendered
    assert "后端模块：sigreal-operate-platform / ReplacementSettlementService" in module_rendered
    assert "ReplacementSettlementQueryDto" in module_rendered
    assert "输入：请求数据" not in module_rendered
    assert "输出：更新后的行为" not in module_rendered
    assert "### 页面与交互影响" in ui_rendered
    assert "页面/路由：设备置换结算 / /device/replacementSettlement" in ui_rendered
    assert "点击「试算」按钮" in ui_rendered
    assert "confirm if UI is affected" not in ui_rendered
    assert "existing entry" not in ui_rendered


def test_runtime_evidence_context_names_frontend_backend_and_apis() -> None:
    rendered = docs_governor.render_runtime_evidence_context(
        {
            "actor": "运营人员",
            "frontend": {
                "repo": "operate-platform-fe",
                "page": "设备置换结算",
                "route": "/device/replacementSettlement",
                "entry_menu_or_button": "点击「试算」按钮",
            },
            "backend": {
                "repo": "sigreal-operate-platform",
                "controller": "ReplacementSettlementController",
                "service": "ReplacementSettlementService",
            },
            "interactions": [
                {"method": "POST", "api": "/operate/api/device/replacementSettlement/renew/paging"}
            ],
        },
        "zh",
    )
    assert "### 源码证据校准" in rendered
    assert "操作角色：运营人员" in rendered
    assert "前端入口：operate-platform-fe / 设备置换结算 / /device/replacementSettlement" in rendered
    assert "用户触发：点击「试算」按钮" in rendered
    assert "后端责任：sigreal-operate-platform / ReplacementSettlementController / ReplacementSettlementService" in rendered
    assert "POST /operate/api/device/replacementSettlement/renew/paging" in rendered


def test_current_architecture_context_prefers_runtime_evidence_over_stale_architecture() -> None:
    rendered = docs_governor.render_current_architecture_context(
        {
            "current_architecture": {
                "system_context": "target-repo owns the initial change boundary",
                "repo_entrypoints": ["/device/orderPivot"],
            }
        },
        {
            "frontend": {"repo": "operate-platform-fe", "page": "设备置换结算", "route": "/device/replacementSettlement"},
            "backend": {
                "repo": "sigreal-operate-platform",
                "controller": "ReplacementSettlementController",
                "service": "ReplacementSettlementService",
            },
            "interactions": [
                {
                    "scenario": "BRK-5 续期试算明细遵循筛选条件",
                    "method": "POST",
                    "api": "/operate/api/device/replacementSettlement/renew/paging",
                }
            ],
        },
        "zh",
    )
    assert "不是纯前端模板变更" in rendered
    assert "operate-platform-fe / 设备置换结算 / /device/replacementSettlement" in rendered
    assert "sigreal-operate-platform / ReplacementSettlementController / ReplacementSettlementService" in rendered
    assert "POST /operate/api/device/replacementSettlement/renew/paging" in rendered
    assert "target-repo" not in rendered
    assert "/device/orderPivot" not in rendered


def test_new_service_design_renders_expert_human_section() -> None:
    architecture = render_design_templates.new_service_example_architecture("REQ-2", "Notification preference service")
    zh = docs_governor.render_new_service_design(architecture, "zh")
    en = docs_governor.render_new_service_design(architecture, "en")
    assert "### 新工程/新服务设计" in zh
    assert "为什么新起工程" in zh
    assert "notification-service" in zh
    assert "CI/CD 基线" in zh
    assert "维护 ownership" in zh
    assert "### New Service / New Repository Design" in en
    assert "Repository Bootstrap" in en


def test_runtime_evidence_overrides_placeholder_owner_text_for_human_rendering() -> None:
    rendered = docs_governor.apply_runtime_evidence_overrides(
        {
            "current": "target-repo uses 需结合代码核对的责任模块",
            "items": ["target module to be confirmed", "相关接口/服务", "/device/orderPivot (src/views/device/replacementSettlement.vue)"],
        },
        {
            "frontend": {"repo": "operate-platform-fe", "page": "设备置换结算", "route": "/device/replacementSettlement"},
            "backend": {
                "repo": "sigreal-operate-platform",
                "controller": "ReplacementSettlementController",
                "service": "ReplacementSettlementService",
            },
            "interactions": [
                {"method": "POST", "api": "/operate/api/device/replacementSettlement/renew/paging"},
                {"method": "POST", "api": "/operate/api/device/renewPool/exclude"},
            ],
        },
        "zh",
    )
    text_value = str(rendered)
    assert "operate-platform-fe / 设备置换结算" in text_value
    assert "sigreal-operate-platform / ReplacementSettlementService" in text_value
    assert "target-repo" not in text_value
    assert "需结合代码核对的责任模块" not in text_value
    assert "target module to be confirmed" not in text_value
    assert "/device/orderPivot" not in text_value
    assert "POST /operate/api/device/replacementSettlement/renew/paging" in text_value


def test_problem_analysis_prefers_runtime_evidence_for_current_behavior() -> None:
    rendered = docs_governor.render_problem_analysis(
        {
            "current_state_analysis": {
                "current_behavior": "target-repo should start from 需结合代码核对的责任模块",
                "business_problem": "续期试算筛选条件未完整生效",
            }
        },
        "zh",
        {
            "frontend": {
                "repo": "operate-platform-fe",
                "page": "设备置换结算",
                "route": "/device/replacementSettlement",
                "entry_menu_or_button": "点击「试算」按钮",
            },
            "backend": {
                "repo": "sigreal-operate-platform",
                "controller": "ReplacementSettlementController",
                "service": "ReplacementSettlementService",
            },
            "interactions": [
                {
                    "scenario": "BRK-5 续期试算明细遵循筛选条件",
                    "method": "POST",
                    "api": "/operate/api/device/replacementSettlement/renew/paging",
                }
            ],
        },
    )
    assert "当前真实行为" in rendered
    assert "点击「试算」按钮" in rendered
    assert "前端：operate-platform-fe / 设备置换结算 / /device/replacementSettlement" in rendered
    assert "后端：sigreal-operate-platform / ReplacementSettlementController / ReplacementSettlementService" in rendered
    assert "POST /operate/api/device/replacementSettlement/renew/paging" in rendered
    assert "target-repo" not in rendered
    assert "需结合代码核对" not in rendered


def test_expert_sections_describe_engineering_sequence_when_architecture_exists() -> None:
    rendered = docs_governor.render_expert_technical_sections(
        {
            "system_interaction_sequence": {
                "applicable": True,
                "participants": ["用户或客户端", "待确认责任模块"],
                "sequence": [{"from": "用户或客户端", "to": "待确认责任模块", "action": "用户点击"}],
            }
        },
        "zh",
        {
            "integration_sequence": [{"requirement_breakdown_id": "BRK-1", "action": "结算订单模块新增并填充字段：`续期月份`。"}],
            "cross_repo_dependency_graph": [
                {
                    "from": "operate-platform-fe",
                    "to": "operate-platform-fe",
                    "contract": "/device/orderPivot",
                    "change": "confirm only unless implementation proves contract change is required",
                }
            ],
            "deployment_impact_matrix": [{"repo": "operate-platform-fe", "artifact": "existing deploy artifact", "order": 1}],
        },
    )
    assert "时序口径：以下图表达运行时触发链路" in rendered
    assert "复用或影响的契约：/device/orderPivot" in rendered
    assert "虽然只修改一个工程，但复用了既有契约" in rendered
    assert "参与方：用户或客户端" not in rendered
    assert "A->>B: BRK-1: 结算订单模块新增并填充字段" in rendered
    assert "B->>C: BRK-1: 请求/复用 /device/orderPivot" in rendered


def test_engineering_sequence_renders_cross_repo_contracts() -> None:
    rendered = docs_governor.render_system_sequence_mermaid(
        {},
        "zh",
        {
            "integration_sequence": [{"requirement_breakdown_id": "BRK-1", "action": "筛选续期订单"}],
            "cross_repo_dependency_graph": [
                {
                    "from": "operate-platform-fe",
                    "to": "sigreal-operate-platform",
                    "contract": "GET /renewal/orders",
                    "change": "响应新增 renewalMonth 字段",
                }
            ],
            "deployment_impact_matrix": [
                {"repo": "sigreal-operate-platform", "artifact": "backend jar", "order": 1},
                {"repo": "operate-platform-fe", "artifact": "frontend bundle", "order": 2},
            ],
        },
    )
    assert "actor A as 业务参与方" in rendered
    assert "participant B as 浏览器/前端<br/>operate-platform-fe" in rendered
    assert "participant C as 后端服务<br/>sigreal-operate-platform" in rendered
    assert "A->>B: BRK-1: 筛选续期订单" in rendered
    assert "B->>C: BRK-1: 请求/复用 GET /renewal/orders" in rendered
    assert "C-->>B: BRK-1: 响应新增 renewalMonth 字段" in rendered
    assert "opt 发布顺序" in rendered


def test_runtime_sequence_includes_mq_when_confirmed() -> None:
    rendered = docs_governor.render_system_sequence_mermaid(
        {
            "mq_interactions": [
                {
                    "applicable": True,
                    "topic_or_queue": "renewal.order.changed",
                    "consumer": "settlement-worker",
                }
            ]
        },
        "zh",
        {
            "integration_sequence": [{"requirement_breakdown_id": "BRK-1", "action": "提交续期订单"}],
            "cross_repo_dependency_graph": [
                {
                    "from": "operate-platform-fe",
                    "to": "sigreal-operate-platform",
                    "contract": "POST /renewal/orders",
                    "change": "返回续期订单结果",
                }
            ]
        },
    )
    assert "participant M as MQ<br/>renewal.order.changed" in rendered
    assert "participant D as settlement-worker" in rendered
    assert "C->>M: 发布消息" in rendered
    assert "M-->>D: 投递消息" in rendered
    assert "D-->>M: 消费确认" in rendered


def test_architecture_mermaid_renders_repo_contract_and_deploy_boundary() -> None:
    rendered = docs_governor.render_architecture_mermaid(
        {
            "cross_repo_dependency_graph": [
                {
                    "from": "operate-platform-fe",
                    "to": "sigreal-operate-platform",
                    "contract": "GET /renewal/orders",
                    "change": "响应新增 renewalMonth 字段",
                }
            ],
            "deployment_impact_matrix": [
                {"repo": "sigreal-operate-platform", "artifact": "backend jar", "order": 1},
                {"repo": "operate-platform-fe", "artifact": "frontend bundle", "order": 2},
            ],
            "rollback_strategy": [{"repo": "operate-platform-fe", "steps": ["revert commit"]}],
        },
        "zh",
    )
    assert "变更仓库/工程边界" in rendered
    assert "operate-platform-fe，可回滚" in rendered
    assert "GET /renewal/orders" in rendered
    assert "发布 #1<br/>backend jar" in rendered
    assert "classDef contract" in rendered


def test_expert_design_sections_are_language_neutral() -> None:
    technical = {
        "data_model_design": {"applicable": True},
        "table_schema_changes": [{"table": "renewal_order", "field": "renewal_month", "type": "needs_confirmation"}],
        "system_interaction_sequence": {"applicable": False, "reason": "not_applicable"},
        "mq_interactions": [{"applicable": False}],
        "cache_strategy": {"applicable": True, "decision": "no_cache"},
        "transaction_consistency": {"applicable": True, "boundary": "owner service/repository transaction boundary must be confirmed"},
        "observability_design": {"logs": ["trace_id"], "metrics": ["latency_p95"]},
    }
    sections = doc_model.expert_design_sections(technical)
    assert [section["section_key"] for section in sections] == [
        "data_model_schema",
        "system_sequence",
        "mq_interactions",
        "cache_strategy",
        "transaction_consistency",
        "observability_design",
    ]
    zh_doc = docs_governor.render_expert_technical_sections(technical, "zh")
    en_doc = docs_governor.render_expert_technical_sections(technical, "en")
    assert "### 数据模型与表结构" in zh_doc
    assert "### Data Model And Table Schema" in en_doc
    assert "renewal_order" in zh_doc
    assert "renewal_order" in en_doc
    assert "needs_confirmation" not in zh_doc
    assert "{\"" not in zh_doc
