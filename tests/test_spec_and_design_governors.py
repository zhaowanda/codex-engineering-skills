from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


spec_governor = load_module("spec_governor", ROOT / "skills/core/spec-governor/scripts/spec_governor.py")
technical_design = load_module("technical_design", ROOT / "skills/core/technical-design-governor/scripts/technical_design.py")
architecture_design = load_module("architecture_design", ROOT / "skills/core/architecture-design-governor/scripts/architecture_design.py")
architecture_framing = load_module("architecture_framing", ROOT / "skills/core/architecture-framing-governor/scripts/architecture_framing.py")
project_understand = load_module("project_understand", ROOT / "skills/core/project-understanding-runner/scripts/project_understand.py")
delivery_runner = load_module("delivery_runner", ROOT / "skills/core/delivery-runner/scripts/delivery_runner.py")
ui_ue_design = load_module("ui_ue_design", ROOT / "skills/core/ui-ue-design-governor/scripts/ui_ue_design.py")
ui_ue_review = load_module("ui_ue_review", ROOT / "skills/core/ui-ue-reviewer/scripts/ui_ue_review.py")
frontend_plan = load_module("frontend_plan", ROOT / "skills/core/frontend-implementation-planner/scripts/frontend_plan.py")
api_contract = load_module("api_contract", ROOT / "skills/core/api-contract-governor/scripts/api_contract.py")
data_model = load_module("data_model", ROOT / "skills/core/data-model-governor/scripts/data_model.py")
domain_model = load_module("domain_model", ROOT / "skills/core/domain-model-governor/scripts/domain_model.py")
observability_design = load_module("observability_design", ROOT / "skills/core/observability-design-governor/scripts/observability_design.py")


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_bound_questions(root: Path) -> None:
    spec = json.loads((root / "spec.json").read_text(encoding="utf-8"))
    write_json(root / "open_questions.json", {
        "schema": "codex-open-questions-v1",
        "questions": [],
        "decision": "pass",
        "spec_digest": delivery_runner.canonical_artifact_digest(spec),
    })
    delivery_runner.CONTRACT.bind_lineage(root / "open_questions.json", "test-fixture", [root / "spec.json"], command=["test-fixture", "open_questions"])


def write_bound_design_review(root: Path, implementation_allowed: bool = True) -> None:
    technical = json.loads((root / "technical_design.json").read_text(encoding="utf-8"))
    architecture = json.loads((root / "architecture_design.json").read_text(encoding="utf-8"))
    write_json(root / "design_architecture_review.json", {
        "schema": "codex-design-architecture-review-v1",
        "decision": "pass",
        "blockers": [],
        "score": 100,
        "readiness_gate": {"implementation_allowed": implementation_allowed},
        "input_digests": {
            "technical_design.json": delivery_runner.canonical_artifact_digest(technical),
            "architecture_design.json": delivery_runner.canonical_artifact_digest(architecture),
        },
    })
    delivery_runner.CONTRACT.bind_lineage(
        root / "design_architecture_review.json",
        "test-fixture",
        [root / "technical_design.json", root / "architecture_design.json"],
        command=["test-fixture", "design_review"],
    )


def write_ready_small_feature(root: Path, docs_root: Path, doc_id: str = "REQ-1") -> None:
    (root / "requirement.normalized.txt").write_text("Requirement\n", encoding="utf-8")
    payloads = {
        "requirement_ingestion.json": {"schema": "codex-requirement-ingestion-v1", "doc_id": doc_id, "normalized_text": str(root / "requirement.normalized.txt"), "decision": "ready", "blockers": []},
        "spec.json": {"schema": "codex-spec-v1", "doc_id": doc_id, "decision": "pass", "requirements": [{"id": "REQ-1", "statement": "Update the synthetic feature"}], "acceptance_criteria": [{"id": "AC-1", "statement": "The synthetic feature is updated"}]},
        "open_questions.json": {"schema": "codex-open-questions-v1", "questions": [], "decision": "pass"},
        "domain_model_design.json": {"schema": "codex-domain-model-design-v1", "decision": "pass", "blockers": [], "business_objects": [{"name": "SyntheticFeature"}], "rules": [{"id": "RULE-1", "statement": "Keep behavior compatible"}]},
        "architecture_framing.json": {"schema": "codex-architecture-framing-v1", "decision": "pass", "blockers": [], "system_boundary": {"inside": ["target-repo"]}, "repo_responsibilities": [{"repo": "target-repo", "responsibility": "Own the feature"}]},
        "technical_design.json": {"schema": "codex-technical-design-v1", "decision": "pass", "blockers": [], "design_scope": {"modules": ["app"]}, "process_flow": [{"step": "Apply the change"}], "solution_options": [{"id": "option-a"}], "selected_solution": {"id": "option-a"}, "test_strategy": [{"type": "regression"}]},
        "architecture_design.json": {"schema": "codex-architecture-design-v1", "decision": "pass", "blockers": [], "architecture_scope": {"repos": ["target-repo"]}, "architecture_options": [{"id": "in-place"}], "selected_architecture": {"id": "in-place"}, "component_boundaries": [{"component": "app", "owns": "feature"}]},
        "design_architecture_review.json": {"schema": "codex-design-architecture-review-v1", "decision": "pass", "blockers": [], "score": 100, "readiness_gate": {"implementation_allowed": True}},
        "test_design.json": {"schema": "codex-test-design-v1", "decision": "pass", "test_cases": [{"id": "TC-1", "expected": "feature passes"}], "evidence_required": ["pytest output"]},
        "test_data_plan.json": {"schema": "codex-test-data-plan-v1", "decision": "pass", "datasets": [{"id": "DATA-1", "type": "synthetic"}], "case_data_matrix": [{"case_id": "TC-1", "dataset_ids": ["DATA-1"]}]},
        "delivery_plan.json": {"schema": "codex-delivery-plan-v1", "doc_id": doc_id, "decision": "ready", "repo_tasks": [{"repo": "target-repo", "allowed_files": ["src/app.py"]}], "validation_plan": {"commands": ["pytest"]}, "release_plan": {"order": ["target-repo"]}, "rollback_plan": {"steps": ["revert commit"]}},
        "traceability_matrix.json": {"schema": "codex-traceability-matrix-v1", "decision": "pass", "blockers": [], "coverage": {"acceptance_covered": True}, "acceptance_trace": [{"acceptance": "AC-1", "test": "TC-1"}], "task_trace": [{"task": "target-repo", "acceptance": "AC-1"}]},
        "delivery_plan_review.json": {"schema": "codex-delivery-plan-review-v1", "decision": "pass", "blockers": [], "readiness_gate": {"implementation_allowed": True}},
        "docs_quality.json": {"schema": "codex-docs-quality-aggregate-v1", "decision": "pass", "blockers": [], "reviews": [{"document": "design", "decision": "pass"}]},
        "git_worktree_evidence.json": {"schema": "codex-git-baseline-evidence-v1", "decision": "ready", "fetched": True, "base_updated": True, "branch": "feature/test"},
        "edit_permit.json": {"schema": "codex-edit-permit-v1", "decision": "ready", "doc_id": doc_id, "branch": "feature/test", "allowed_files": ["src/app.py"]},
        "write_guard_snapshot.json": {"schema": "codex-write-guard-snapshot-v1", "decision": "ready", "doc_id": doc_id, "branch": "feature/test", "permit_id": "EDIT-TEST"},
    }
    for name, payload in payloads.items():
        write_json(root / name, payload)
    questions = json.loads((root / "open_questions.json").read_text(encoding="utf-8"))
    questions["spec_digest"] = delivery_runner.canonical_artifact_digest(payloads["spec.json"])
    write_json(root / "open_questions.json", questions)
    for stage in delivery_runner.load_stage_registry():
        path = root / str(stage["artifact"])
        if not path.exists():
            continue
        inputs = []
        for artifact in stage.get("input_artifacts", []):
            source = root / str(artifact)
            if source.exists():
                inputs.append(source)
        delivery_runner.CONTRACT.bind_lineage(path, "test-fixture", inputs, command=["test-fixture", str(stage["name"])])
    write_json(root / "auto_run_summary.json", {
        "doc_id": doc_id,
        "docs_readiness": {"decision": "pass", "docs_root": str(docs_root), "manifest": str(docs_root / f"indexes/{doc_id}.manifest.json")},
    })


def make_docs_repo(root: Path, doc_id: str) -> Path:
    docs_root = root / "delivery-docs"
    docs_root.mkdir()
    subprocess.run(["git", "init"], cwd=docs_root, text=True, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=docs_root, text=True, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=docs_root, text=True, capture_output=True, check=True)
    write_json(docs_root / "indexes" / f"{doc_id}.manifest.json", {"schema": "codex-docs-governor-v1", "doc_id": doc_id})
    subprocess.run(["git", "add", "."], cwd=docs_root, text=True, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "docs init"], cwd=docs_root, text=True, capture_output=True, check=True)
    return docs_root


def test_spec_normalize_ready_for_design() -> None:
    text = """
    Admin needs to export orders.
    Rule: only admin can export filtered results.
    AC: exported file contains order id and status.
    AC: non-admin cannot export filtered results.
    """
    spec = spec_governor.normalize("REQ-1", "Order export", text)
    assert spec["schema"] == "codex-spec-v1"
    assert spec["decision"] == "blocked"
    assert spec["acceptance_criteria"]
    assert spec["requirements_understanding"]["level"] == "clarification_required"
    validation = spec_governor.validate_spec(spec)
    assert validation["decision"] == "block"


def test_spec_inferred_acceptance_uses_requirement_language_without_template_prefix() -> None:
    spec = spec_governor.normalize("REQ-ZH", "菜单点击打点", "菜单点击打点")

    assert spec["acceptance_criteria"][0]["criteria"] == "菜单点击打点"
    assert "User-visible behavior matches" not in spec["acceptance_criteria"][0]["criteria"]


def test_spec_normalizes_empty_include_at_least_clause() -> None:
    spec = spec_governor.normalize(
        "REQ-ENUM",
        "续期池移出原因",
        "需求：从续期池移出设备必须填写原因；原因选项至少包括：",
    )

    rendered = json.dumps(spec, ensure_ascii=False)
    assert "原因选项至少包括待确认的具体选项" in rendered
    assert "原因选项至少包括：" not in rendered


def test_spec_blocks_open_questions() -> None:
    spec = spec_governor.normalize("REQ-2", "Unclear request", "User wants report. Which fields?")
    validation = spec_governor.validate_spec(spec)
    assert validation["decision"] == "block"
    assert any(item["source"] == "open_questions" for item in validation["blockers"])


def test_spec_extracts_multiple_requirements_scope_risks_and_questions() -> None:
    text = """
    Req: Admin exports filtered orders.
    Req: Operator sees export history.
    Rule: only admin can export filtered results.
    AC: exported file contains order id and status.
    AC: non-admin cannot see export action.
    Out of scope: scheduled exports.
    Assumption: existing order API remains available.
    Risk: large exports may be slow.
    Which columns are mandatory?
    """
    spec = spec_governor.normalize("REQ-20", "Order export", text)
    assert len(spec["requirements"]) == 2
    assert len(spec["acceptance_criteria"]) == 2
    assert spec["scope"]["out_of_scope"] == ["scheduled exports."]
    assert spec["scope"]["assumptions"] == ["existing order API remains available."]
    assert spec["risks"]
    assert spec["open_questions"]


def test_spec_extracts_numbered_acceptance_section_from_prd() -> None:
    text = """
    # 运营系统功能优化需求

    ## 可执行需求
    1. 结算订单模块新增并填充字段：`续期月份`。
    2. 结算订单列表隐藏已作废/已取消订单。

    ## 验收标准
    1. 结算订单列表可看到 `续期月份`，且数据来源与续期结算订单月份一致。
    2. 默认列表和状态统计不展示已作废/已取消结算订单。
    3. 运营人员可以批量录入或导入不续期设备号，并触发批量移出续期池。
    4. 单个或批量移出续期池时，未选择/填写原因不可提交；提交后原因写入后端记录。
    5. 续期试算明细查询时，租户、自有车等筛选条件在明细接口中生效。
    6. 前端通过 `npm run build:test`；后端至少通过 `mvn -pl operate-provider -DskipTests compile`。
    """
    spec = spec_governor.normalize("REQ-SECTION", "运营系统功能优化", text)
    assert len(spec["requirements"]) == 2
    assert len(spec["acceptance_criteria"]) == 6
    criteria = [item["criteria"] for item in spec["acceptance_criteria"]]
    assert "结算订单列表可看到 `续期月份`" in criteria[0]
    assert all(item["criteria"] != "标准" for item in spec["acceptance_criteria"])


def test_spec_adds_expert_quality_fields() -> None:
    text = """
    Goal: reduce manual export work.
    Scenario: Admin exports filtered orders from the orders page.
    Req: Admin exports filtered orders.
    Rule: only admin can export filtered results.
    AC: exported file contains order id and status.
    AC: non-admin cannot see export action.
    """
    spec = spec_governor.normalize("REQ-21", "Order export", text)
    assert spec["personas"]
    assert spec["user_scenarios"]
    assert spec["business_objectives"]
    assert spec["negative_acceptance_criteria"]
    assert any(item["area"] == "permission" for item in spec["impact_surface"])
    validation = spec_governor.validate_spec(spec)
    assert validation["decision"] == "pass"


def test_spec_handles_one_line_request_with_inferred_acceptance() -> None:
    spec = spec_governor.normalize("REQ-ONE", "Checkout copy", "Change checkout button text to Pay now.")
    assert spec["lane"] == "small_change"
    assert spec["requirements"][0]["summary"] == "Change checkout button text to Pay now."
    assert spec["acceptance_criteria"][0]["source_evidence"] == "inferred from first line"
    assert spec["source"]["line_count"] == 1
    validation = spec_governor.validate_spec(spec)
    assert validation["decision"] == "block"
    assert spec["requirements_understanding"]["level"] == "clarification_required"
    assert any(item["source"] == "requirements_understanding" for item in validation["blockers"])


def test_spec_handles_long_prd_without_collapsing_traceability() -> None:
    lines = [
        "Goal: reduce manual operations.",
        "Req: Admin exports filtered orders.",
        "Req: Operator reviews export history.",
        "Req: Customer service audits export failures.",
        "Rule: only admin can export filtered results.",
        "Rule: operators can view export history only.",
        "AC: exported file contains order id and status.",
        "AC: non-admin cannot export filtered results.",
        "Risk: large exports may be slow.",
        "Out of scope: scheduled exports.",
    ]
    lines.extend(f"Detail {idx}: preserve existing report behavior." for idx in range(1, 28))
    spec = spec_governor.normalize("REQ-LONG", "Long order export PRD", "\n".join(lines))
    assert spec["lane"] == "large_prd"
    assert len(spec["requirements"]) == 3
    assert len(spec["business_rules"]) >= 2
    assert len(spec["source_trace"]) > 30
    assert spec["risks"]
    assert spec["scope"]["out_of_scope"] == ["scheduled exports."]


def test_spec_exposes_complex_multi_impact_requirements() -> None:
    text = """
    Goal: reduce failed payment support work.
    Scenario: Admin reviews payment export failures from the dashboard page.
    Req: Add an API endpoint for payment export failures.
    Req: Add a dashboard page for admins.
    Req: Add a database migration for failure reason and retry count.
    Rule: only admin role can access payment failure data.
    Rule: export must finish within the existing latency budget.
    AC: API returns payment failure rows.
    AC: dashboard page shows retry count.
    AC: non-admin cannot view payment failure data.
    AC: export latency remains within the performance budget.
    Risk: payment data may contain sensitive fields.
    """
    spec = spec_governor.normalize("REQ-COMPLEX", "Payment failure dashboard", text)
    impacts = {item["area"] for item in spec["impact_surface"]}
    assert {"api", "ui", "data", "permission", "performance", "security"}.issubset(impacts)
    assert spec["data_classification"]["requires_security_review"] is True
    assert spec["permission_scope"]["negative_cases_required"] is True
    assert spec["negative_acceptance_criteria"]
    assert {"payment", "dashboard"}.issubset({item["name"] for item in spec["business_objects"]})
    assert {"retry_count", "failure_reason"}.issubset({item["name"] for item in spec["data_fields"]})
    assert {"view"}.issubset({item["name"] for item in spec["operations"]})
    assert {item["area"] for item in spec["implicit_constraints"]} >= {"permission", "data", "api", "performance", "security"}
    assert {item["area"] for item in spec["derived_constraint_questions"]} >= {"permission", "data", "api", "performance", "security"}
    assert any(item["source"] == "compatibility_constraints" for item in spec["expert_readiness_gaps"])


def test_spec_blocks_permission_requirement_without_negative_acceptance() -> None:
    text = """
    Req: Admin exports filtered orders.
    Rule: only admin can export filtered results.
    AC: exported file contains order id and status.
    """
    spec = spec_governor.normalize("REQ-22", "Order export", text)
    validation = spec_governor.validate_spec(spec)
    assert validation["decision"] == "block"
    assert any(item["source"] == "negative_acceptance_criteria" for item in validation["blockers"])


def test_spec_blocks_conflicting_permission_rules() -> None:
    text = """
    Req: Export order report.
    Rule: only admin can export order report.
    Rule: operator can export order report.
    AC: admin can export order report.
    """
    spec = spec_governor.normalize("REQ-CONFLICT", "Order export", text)
    validation = spec_governor.validate_spec(spec)
    assert spec["rule_conflicts"]
    assert validation["decision"] == "block"
    assert any(item["source"] == "rule_conflicts" for item in validation["blockers"])


def test_spec_extracts_state_transitions() -> None:
    spec = spec_governor.normalize("REQ-STATE", "Refund state", "Req: change refund status from pending to completed.\nAC: status is completed.")
    assert spec["state_transitions"]
    assert spec["state_transitions"][0]["from"] == "pending"
    assert "completed" in spec["state_transitions"][0]["to"]


def test_technical_and_architecture_design_render_core_sections() -> None:
    spec = spec_governor.normalize(
        "REQ-3",
        "Checkout display",
        "\n".join([
            "业务目的: 让买家在提交订单前确认折扣明细，减少价格疑问。",
            "流程: 买家打开结算页，系统读取定价接口返回的折扣明细并展示在订单汇总区域。",
            "入口: 结算页订单汇总区域加载。",
            "Req: Buyer sees discount before submitting checkout.",
            "Rule: Pricing API remains the source of truth for discount amounts.",
            "AC: Given buyer opens checkout, discount is visible before submit.",
        ]),
    )
    tech = technical_design.render(spec)
    arch = architecture_design.render(spec, tech)
    assert tech["schema"] == "codex-technical-design-v1"
    assert tech["process_flow"]
    assert len(tech["solution_options"]) >= 2
    assert all({"when_to_choose", "implementation_outline", "risk_controls", "test_evidence", "rollout_impact"}.issubset(item) for item in tech["solution_options"])
    assert all({"criterion", "weight", "scores", "winner", "reason"}.issubset(item) for item in tech["option_comparison_matrix"])
    assert {"T1", "T2"}.issubset(tech["option_score_summary"])
    assert tech["implementation_invariants"]
    assert tech["expert_review_checklist"]
    assert tech["requirement_breakdown"]
    assert tech["code_entrypoint_confidence"]["level"] in {"high", "medium", "low"}
    assert tech["field_api_permission_impact"]
    assert {"data_model_design", "table_schema_changes", "system_interaction_sequence", "mq_interactions", "cache_strategy", "transaction_consistency", "observability_design"}.issubset(tech)
    assert tech["decision_confidence"]["level"] in {"high", "medium"}
    assert tech["selected_solution"]["rejected_alternative_reasoning"]
    assert arch["schema"] == "codex-architecture-design-v1"
    assert arch["architecture_options"]
    assert all({"when_to_choose", "integration_impact", "deployment_impact", "rollback_complexity", "risk_controls"}.issubset(item) for item in arch["architecture_options"])
    assert all({"criterion", "weight", "scores", "winner", "reason"}.issubset(item) for item in arch["architecture_fit_matrix"])
    assert {"A1", "A2"}.issubset(arch["architecture_score_summary"])
    assert arch["architecture_invariants"]
    assert arch["expert_review_checklist"]
    assert arch["requirement_breakdown"]
    assert "code_entrypoint_confidence" in arch
    assert arch["architecture_decision_confidence"]["level"] in {"high", "medium"}
    assert arch["selected_architecture"]["rejected_alternative_reasoning"]
    assert arch["repo_responsibilities"][0]["role"] == "modify"


def test_design_options_are_generated_from_impact_surface() -> None:
    spec = spec_governor.normalize(
        "REQ-DYNAMIC",
        "Renewal operations",
        "\n".join([
            "Operator updates renewal list UI.",
            "AC: renewal month field is shown.",
            "AC: tenant filter applies to renewal detail query.",
            "AC: unauthorized role cannot remove devices.",
            "AC: cancelled orders are hidden.",
            "AC: batch import non-renewal devices.",
        ]),
    )
    spec["impact_surface"] = [
        {"area": "ui"},
        {"area": "api"},
        {"area": "data"},
        {"area": "permission"},
        {"area": "business_flow"},
    ]
    tech = technical_design.render(spec)
    arch = architecture_design.render(spec, tech)
    option_names = " ".join(str(item.get("name")) for item in tech["solution_options"])
    arch_names = " ".join(str(item.get("name")) for item in arch["architecture_options"])
    assert len(tech["solution_options"]) >= 5
    assert "前后端权限一致性方案" in option_names
    assert "前后端分层协同方案" in option_names
    assert "按业务子域拆分交付方案" in option_names
    tech_criteria = {str(item.get("criterion")) for item in tech["option_comparison_matrix"]}
    assert {"越权风险控制", "前后端协同清晰度", "子域可拆分性"}.issubset(tech_criteria)
    assert {"越权风险控制", "前后端协同清晰度", "子域可拆分性"}.issubset(set(tech["selected_solution"]["decision_criteria"]))
    assert len(arch["architecture_options"]) >= 4
    assert "权限闭环" in arch_names
    assert "业务子域" in arch_names
    arch_criteria = {str(item.get("criterion")) for item in arch["architecture_fit_matrix"]}
    assert {"权限闭环完整性", "子域发布可控性"}.issubset(arch_criteria)
    assert {"权限闭环完整性", "子域发布可控性"}.issubset(set(arch["selected_architecture"]["decision_criteria"]))
    assert tech["selected_solution"]["selected_option_id"] != "T1"
    assert arch["selected_architecture"]["selected_option_id"] != "A1"


def test_technical_design_adds_expert_data_mq_cache_and_sequence_sections() -> None:
    spec = spec_governor.normalize(
        "REQ-EXPERT-DESIGN",
        "Payment failure events",
        "\n".join([
            "Req: Add database migration for payment failure reason and retry count.",
            "Req: Publish MQ topic payment.failure.changed when retry status changes.",
            "Req: Add API endpoint for admin dashboard query.",
            "Req: Cache high-frequency failure statistics for dashboard display.",
            "Rule: settlement and payment consistency must be preserved.",
            "AC: table has failure_reason and retry_count fields.",
            "AC: producer sends topic after transaction commits.",
            "AC: dashboard reads cached statistics and falls back to source query.",
        ]),
    )
    spec["impact_surface"] = [{"area": "data"}, {"area": "api"}, {"area": "performance"}]
    tech = technical_design.render(spec)

    assert tech["data_model_design"]["applicable"] is True
    assert tech["data_model_design"]["entities"]
    assert tech["table_schema_changes"]
    assert {"table", "field", "type", "nullable", "default", "migration", "rollback"}.issubset(tech["table_schema_changes"][0])
    assert tech["system_interaction_sequence"]["applicable"] is True
    assert {"participants", "sequence", "timeout_retry", "idempotency", "consistency"}.issubset(tech["system_interaction_sequence"])
    assert tech["mq_interactions"][0]["applicable"] is True
    assert {"producer", "consumer", "topic_or_queue", "trigger", "payload_fields", "idempotency_key", "retry_policy", "dead_letter_or_compensation"}.issubset(tech["mq_interactions"][0])
    assert tech["cache_strategy"]["applicable"] is True
    assert {"decision", "key_design", "value_shape", "ttl", "invalidation", "consistency_risk"}.issubset(tech["cache_strategy"])
    assert tech["transaction_consistency"]["applicable"] is True
    assert {"boundary", "idempotency", "compensation", "rollback"}.issubset(tech["transaction_consistency"])
    assert {"logs", "metrics", "traces", "alerts"}.issubset(tech["observability_design"])


def test_specialized_ui_ue_design_review_and_frontend_plan() -> None:
    # Coverage references for skill-health: ui-ue-design-governor, ui-ue-reviewer,
    # frontend-implementation-planner.
    spec = spec_governor.normalize(
        "REQ-UI-UE",
        "Admin dashboard export",
        "\n".join([
            "业务目的: 让管理员在报表页导出筛选结果，减少手工整理。",
            "流程: 管理员打开报表页，选择筛选条件，点击导出按钮，系统生成文件。",
            "入口: 报表页导出按钮。",
            "Req: Admin exports filtered report rows from the dashboard page.",
            "Rule: only admin can see export button.",
            "AC: admin can export filtered rows.",
            "AC: non-admin cannot see export button.",
        ]),
    )
    spec["impact_surface"] = [{"area": "ui"}, {"area": "api"}, {"area": "permission"}]
    tech = technical_design.render(spec, {
        "repository_analysis": {"project": "operate-fe", "entrypoint_hints": ["src/views/report/ReportPage.vue"], "top_level_directories": ["src"]},
        "code_index": {"files": [{"path": "src/views/report/ReportPage.vue", "summary": "report dashboard export button"}]},
    })

    design = ui_ue_design.design(spec, tech)
    review = ui_ue_review.review(design)
    plan = frontend_plan.plan(design, tech)

    assert design["schema"] == "codex-ui-ue-design-v1"
    assert design["decision"] == "pass"
    assert {item["state"] for item in design["state_matrix"]} >= {"loading", "empty", "success", "validation_error", "permission_denied", "dependency_error"}
    assert review["decision"] == "pass"
    assert review["readiness_gate"]["frontend_implementation_allowed"] is True
    assert plan["decision"] == "pass"
    assert plan["routes"][0]["entry_action"] == "报表页导出按钮。"


def test_specialized_api_data_domain_and_observability_artifacts() -> None:
    # Coverage references for skill-health: api-contract-governor,
    # data-model-governor, domain-model-governor, observability-design-governor.
    spec = spec_governor.normalize(
        "REQ-SPECIALIZED",
        "Payment retry dashboard",
        "\n".join([
            "业务目的: 让管理员定位支付重试失败原因。",
            "流程: 管理员打开支付失败页面，查询失败记录，重试后系统更新状态并发布 MQ。",
            "入口: 支付失败页面重试按钮。",
            "Req: Add API endpoint for payment retry failures.",
            "Req: Add database migration for failure_reason and retry_count.",
            "Req: Publish MQ topic payment.retry.changed after retry status changes.",
            "AC: API returns failure_reason and retry_count.",
        ]),
    )
    spec["impact_surface"] = [{"area": "api"}, {"area": "data"}, {"area": "performance"}]
    tech = technical_design.render(spec)

    api = api_contract.design(spec, tech)
    data = data_model.design(spec, tech)
    domain = domain_model.design(spec)
    obs = observability_design.design(spec, tech)

    assert api["schema"] == "codex-api-contract-design-v1"
    assert api["decision"] in {"pass", "block"}
    assert api["contracts"]
    assert data["schema"] == "codex-data-model-design-v1"
    assert data["decision"] in {"pass", "block"}
    assert data["test_data_requirements"]
    assert domain["schema"] == "codex-domain-model-design-v1"
    assert domain["decision"] == "pass"
    assert domain["business_intent"]
    assert obs["schema"] == "codex-observability-design-v1"
    assert obs["mq_observability"]


def test_architecture_framing_precedes_and_informs_technical_architecture_design() -> None:
    # Coverage reference for skill-health: architecture-framing-governor.
    spec = spec_governor.normalize(
        "REQ-FRAMING",
        "Payment retry API",
        "\n".join([
            "业务目的: 让管理员通过支付失败页重试支付失败记录。",
            "流程: 管理员点击支付失败页重试按钮，后端更新重试状态并通知下游。",
            "入口: 支付失败页重试按钮。",
            "Req: Add API endpoint for payment retry.",
            "Req: Publish MQ topic payment.retry.changed after retry status changes.",
            "AC: API retry succeeds and emits event.",
        ]),
    )
    spec["impact_surface"] = [{"area": "api"}, {"area": "data"}]
    domain = domain_model.design(spec)
    framing = architecture_framing.design(
        spec,
        domain,
        {
            "repository_analysis": {"project": "payment-service", "entrypoint_hints": ["src/payment/RetryController.java"]},
            "api_surface": {"routes": [{"method": "POST", "route": "/api/payment/retry", "file": "src/payment/RetryController.java"}]},
            "code_index": {"repo_root": "/repo/payment-service", "files": [{"path": "src/payment/RetryController.java"}]},
        },
    )
    tech = technical_design.merge_specialized_artifacts(
        technical_design.render(spec),
        {"architecture_framing": None, "domain_model_design": None, "ui_ue_design": None, "api_contract_design": None, "data_model_design": None, "observability_design": None},
    )
    # Merge through a temp file to exercise the same path used by the CLI.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_json(root / "architecture_framing.json", framing)
        tech = technical_design.merge_specialized_artifacts(technical_design.render(spec), {"architecture_framing": root / "architecture_framing.json"})
        arch = architecture_design.render(spec, tech, {}, framing)
    assert framing["schema"] == "codex-architecture-framing-v1"
    assert framing["decision"] == "pass"
    assert tech["architecture_framing_ref"] == "architecture_framing.json"
    assert tech["project_context"]["architecture_owner_repo"] == "payment-service"
    assert arch["architecture_framing_ref"] == "architecture_framing.json"
    assert arch["architecture_framing"]["system_boundary"]["owner_repo"] == "payment-service"


def test_technical_design_rejects_cache_for_strong_consistency_terms() -> None:
    spec = spec_governor.normalize(
        "REQ-NO-CACHE",
        "Settlement payment consistency",
        "Req: cache payment settlement status only if it remains strongly consistent. AC: settlement query returns committed status only.",
    )
    tech = technical_design.render(spec)
    assert tech["cache_strategy"]["applicable"] is True
    assert tech["cache_strategy"]["decision"] == "no_cache"


def test_config_files_do_not_become_business_contracts() -> None:
    spec = spec_governor.normalize("REQ-CONFIG-ROUTE", "UI collapse", "设备页面最近批量处理默认折叠。AC: 进入页面后最近批量处理区域默认折叠。")
    understanding = {
        "repository_analysis": {"project": "web", "entrypoint_hints": ["src/views/device/device.vue"], "top_level_directories": ["src"]},
        "api_surface": {"routes": [{"method": "", "route": "/", "file": "vue.config.js"}]},
        "code_index": {"files": [{"path": "src/views/device/device.vue", "summary": "device page"}]},
        "dependency_surface": {"test_command_hints": ["npm run build:test"]},
    }
    tech = technical_design.render(spec, understanding)
    arch = architecture_design.render(spec, tech, understanding)
    assert all("vue.config.js" not in str(item.get("contract")) for item in tech["api_contracts"])
    assert all("vue.config.js" not in str(item.get("contract")) for item in arch["cross_repo_contracts"])


def test_design_options_do_not_force_data_or_permission方案_when_irrelevant() -> None:
    spec = spec_governor.normalize("REQ-SIMPLE", "Menu click tracking", "Menu click should be tracked. AC: click event is emitted.")
    spec["impact_surface"] = [{"area": "ui"}]
    tech = technical_design.render(spec)
    option_names = " ".join(str(item.get("name")) for item in tech["solution_options"])
    assert len(tech["solution_options"]) == 2
    assert "字段" not in option_names
    assert "权限一致性" not in option_names


def test_project_understanding_informs_design_and_architecture() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        understanding_dir = Path(tmp) / "understanding"
        project_understand.run(ROOT / "examples/synthetic-repos/basic-web-service", "basic-web-service", understanding_dir)
        spec = spec_governor.normalize("REQ-30", "Order export", "Admin exports orders. AC: exported file contains order id.")
        tech = technical_design.render(spec, technical_design.load_project_understanding(understanding_dir))
        arch = architecture_design.render(spec, tech, architecture_design.load_project_understanding(understanding_dir))
        assert tech["project_context"]["project"] == "basic-web-service"
        assert "app/main.py" in tech["project_context"]["read_first"]
        assert tech["module_decomposition"][0]["module"] != "target module to be confirmed"
        assert tech["code_entrypoint_confidence"]["selected_entrypoint"] != "target module to be confirmed"
        assert arch["repo_responsibilities"][0]["repo"] == "basic-web-service"
        assert arch["repo_responsibilities"][0]["repo_path"].endswith("examples/synthetic-repos/basic-web-service")


def test_delivery_runner_reports_next_stage() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        status = delivery_runner.inspect(root)
        assert status["next_stage"] == "requirement_ingestion"
        assert status["next_action_type"] == "fix_blocker"
        assert status["primary_next_action"]["action_type"] == "fix_blocker"
        assert status["can_implement"] is False

        write_json(root / "requirement_ingestion.json", {"schema": "codex-requirement-ingestion-v1", "doc_id": "REQ-4", "normalized_text": "requirement.normalized.txt", "decision": "ready", "blockers": []})
        (root / "requirement.normalized.txt").write_text("Requirement\n", encoding="utf-8")
        spec = {"schema": "codex-spec-v1", "doc_id": "REQ-4", "decision": "pass", "requirements": [{"id": "REQ-4", "statement": "Synthetic requirement"}], "acceptance_criteria": [{"id": "AC-1", "statement": "Synthetic acceptance"}]}
        write_json(root / "spec.json", spec)
        delivery_runner.CONTRACT.bind_lineage(root / "requirement_ingestion.json", "test-fixture", [], command=["test-fixture", "requirement_ingestion"])
        delivery_runner.CONTRACT.bind_lineage(root / "spec.json", "test-fixture", [root / "requirement.normalized.txt"], command=["test-fixture", "spec"])
        write_bound_questions(root)
        status = delivery_runner.inspect(root)
        assert status["next_stage"] == "domain_model_design"
        assert "domain_model.py" in status["next_command"]


def test_delivery_runner_allows_implementation_when_pre_edit_gates_pass() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = make_docs_repo(root, "REQ-1")
        write_ready_small_feature(root, docs_root)
        status = delivery_runner.inspect(root)
        assert status["can_implement"] is True
        assert status["next_stage"] == "implementation"
        assert status["next_action_type"] == "ready_to_implement"


def test_delivery_runner_requires_delivery_plan_review_before_git_edit() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = make_docs_repo(root, "REQ-1")
        write_ready_small_feature(root, docs_root)
        for name in ["test_design.json", "test_data_plan.json", "delivery_plan.json", "traceability_matrix.json", "delivery_plan_review.json", "docs_quality.json", "git_worktree_evidence.json", "edit_permit.json", "write_guard_snapshot.json"]:
            (root / name).unlink()
        status = delivery_runner.inspect(root)
        assert status["can_implement"] is False
        assert status["next_stage"] == "test_design"
        assert status["next_action_type"] == "fix_blocker"
        assert "test_design.py" in status["next_command"]


def test_delivery_runner_blocks_when_profile_gate_readiness_fails() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = make_docs_repo(root, "REQ-1")
        for name in ["spec", "open_questions", "domain_model_design", "architecture_framing", "technical_design", "architecture_design", "test_design", "test_data_plan", "traceability_matrix", "docs_quality", "delivery_plan", "git_worktree_evidence", "edit_permit"]:
            write_json(root / f"{name}.json", {"decision": "pass"})
        write_json(root / "delivery_plan.json", {"decision": "pass", "doc_id": "REQ-1"})
        write_json(root / "git_worktree_evidence.json", {"decision": "ready", "fetched": True, "base_updated": True})
        write_json(root / "auto_run_summary.json", {
            "doc_id": "REQ-1",
            "docs_readiness": {
                "decision": "pass",
                "docs_root": str(docs_root),
                "manifest": str(docs_root / "indexes/REQ-1.manifest.json"),
            },
        })
        write_json(root / "delivery_plan_review.json", {"decision": "pass", "readiness_gate": {"implementation_allowed": False}})
        write_bound_questions(root)
        write_bound_design_review(root)
        status = delivery_runner.inspect(root, profile_name="small_feature")
        assert status["can_implement"] is False
        assert any(item["source"] == "profile_gate.delivery_plan_review.json" for item in status["blockers"])


def test_delivery_runner_requires_docs_and_fresh_git_before_implementation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for name in ["spec", "open_questions", "domain_model_design", "architecture_framing", "technical_design", "architecture_design", "test_design", "test_data_plan", "traceability_matrix", "docs_quality", "edit_permit"]:
            write_json(root / f"{name}.json", {"decision": "pass"})
        write_json(root / "delivery_plan.json", {"decision": "pass", "doc_id": "REQ-1"})
        write_json(root / "delivery_plan_review.json", {"decision": "pass", "readiness_gate": {"implementation_allowed": True}})
        write_bound_questions(root)
        write_bound_design_review(root)
        write_json(root / "git_worktree_evidence.json", {"decision": "ready"})
        status = delivery_runner.inspect(root)
        assert status["can_implement"] is False
        assert any(item["source"] == "docs_root" for item in status["blockers"])
        assert any("fetch evidence is missing" in item["message"] for item in status["blockers"])
        assert any("pull --ff-only evidence is missing" in item["message"] for item in status["blockers"])


def test_delivery_runner_blocks_when_docs_quality_not_pass() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = make_docs_repo(root, "REQ-1")
        for name in ["spec", "open_questions", "domain_model_design", "architecture_framing", "technical_design", "architecture_design", "test_design", "test_data_plan", "traceability_matrix", "delivery_plan", "git_worktree_evidence", "edit_permit"]:
            write_json(root / f"{name}.json", {"decision": "pass"})
        write_json(root / "docs_quality.json", {"decision": "warn", "warnings": [{"source": "depth"}]})
        write_json(root / "delivery_plan.json", {"decision": "pass", "doc_id": "REQ-1"})
        write_json(root / "delivery_plan_review.json", {"decision": "pass", "readiness_gate": {"implementation_allowed": True}})
        write_bound_questions(root)
        write_bound_design_review(root)
        write_json(root / "git_worktree_evidence.json", {"decision": "ready", "fetched": True, "base_updated": True})
        write_json(root / "auto_run_summary.json", {
            "doc_id": "REQ-1",
            "docs_readiness": {
                "decision": "pass",
                "docs_root": str(docs_root),
                "manifest": str(docs_root / "indexes/REQ-1.manifest.json"),
            },
        })
        status = delivery_runner.inspect(root)
        assert status["can_implement"] is False
        assert any(item["source"] == "docs_quality" for item in status["blockers"])


def test_delivery_runner_skips_conditional_cross_repo_stage_for_small_feature() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = make_docs_repo(root, "REQ-1")
        write_ready_small_feature(root, docs_root)
        status = delivery_runner.inspect(root, profile_name="small_feature")
        assert "cross_repo_plan" not in status["missing_artifacts"]
        assert "cross_repo_plan" not in status["implementation_missing"]
        assert status["can_implement"] is True


def test_delivery_runner_rejects_placeholder_artifact_even_with_pass_decisions() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = make_docs_repo(root, "REQ-1")
        write_ready_small_feature(root, docs_root)
        write_json(root / "technical_design.json", {"schema": "placeholder", "decision": "pass", "blockers": []})
        review = json.loads((root / "design_architecture_review.json").read_text(encoding="utf-8"))
        review["input_digests"]["technical_design.json"] = delivery_runner.CONTRACT.path_digest(root / "technical_design.json")
        write_json(root / "design_architecture_review.json", review)
        status = delivery_runner.inspect(root, profile_name="small_feature")
        assert status["can_implement"] is False
        assert any(item["source"] == "technical_design" and "contract" in item["message"] for item in status["blockers"])


def test_delivery_runner_rejects_vacuous_artifact_with_correct_schema() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = make_docs_repo(root, "REQ-1")
        write_ready_small_feature(root, docs_root)
        write_json(root / "technical_design.json", {
            "schema": "codex-technical-design-v1",
            "decision": "pass",
            "blockers": [],
            "design_scope": {},
            "process_flow": [],
            "solution_options": [],
            "selected_solution": {},
            "test_strategy": [],
        })
        delivery_runner.CONTRACT.bind_lineage(root / "technical_design.json", "test-fixture", [root / "spec.json"], command=["test-fixture", "technical_design"])
        write_bound_design_review(root)
        status = delivery_runner.inspect(root, profile_name="small_feature")
        assert status["can_implement"] is False
        issues = next(item["issues"] for item in status["blockers"] if item["source"] == "technical_design")
        assert any("evidence field" in issue for issue in issues)


def test_delivery_runner_rejects_tampered_lineage_digest() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = make_docs_repo(root, "REQ-1")
        write_ready_small_feature(root, docs_root)
        technical = json.loads((root / "technical_design.json").read_text(encoding="utf-8"))
        technical["selected_solution"] = {"id": "tampered-after-generation"}
        write_json(root / "technical_design.json", technical)
        status = delivery_runner.inspect(root, profile_name="small_feature")
        issues = next(item["issues"] for item in status["blockers"] if item["source"] == "technical_design")
        assert "artifact_digest does not match artifact content" in issues


def test_delivery_runner_requires_write_guard_snapshot() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = make_docs_repo(root, "REQ-1")
        write_ready_small_feature(root, docs_root)
        (root / "write_guard_snapshot.json").unlink()
        status = delivery_runner.inspect(root, profile_name="small_feature")
        assert status["can_implement"] is False
        assert status["next_stage"] == "write_guard_snapshot"


def test_delivery_runner_propagates_spec_staleness() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = make_docs_repo(root, "REQ-1")
        write_ready_small_feature(root, docs_root)
        spec = json.loads((root / "spec.json").read_text(encoding="utf-8"))
        spec["requirement_summary"] = "changed requirement"
        write_json(root / "spec.json", spec)
        questions = json.loads((root / "open_questions.json").read_text(encoding="utf-8"))
        questions["spec_digest"] = delivery_runner.canonical_artifact_digest(spec)
        questions["input_digests"]["spec.json"] = delivery_runner.CONTRACT.path_digest(root / "spec.json")
        write_json(root / "open_questions.json", questions)
        status = delivery_runner.inspect(root, profile_name="small_feature")
        assert status["can_implement"] is False
        assert any(item["source"] in {"domain_model_design", "technical_design"} and "stale" in item["message"] for item in status["blockers"])


def test_delivery_runner_rejects_placeholder_release_chain() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        decisions = {
            "implementation_completion_gate.json": "pass",
            "post_change_implementation_report.json": "pass",
            "write_guard_audit.json": "ready",
            "diff_impact.json": "pass",
            "change_risk.json": "pass",
            "evidence_gap_summary.json": "pass",
            "code_design_quality.json": "pass",
            "test_evidence_gate.json": "pass",
            "post_implementation_traceability_matrix.json": "pass",
            "code_review_gate.json": "approve",
            "environment_promotion.json": "pass",
            "uat_acceptance.json": "pass",
            "release_change.json": "pass",
            "release_gate.json": "go",
        }
        for name, decision in decisions.items():
            write_json(root / name, {"schema": "placeholder", "decision": decision})
        status = delivery_runner.inspect(root, profile_name="release_readiness")
        assert status["can_release"] is False
        assert any("contract" in item["message"] for item in status["blockers"])


def run_all() -> None:
    test_spec_normalize_ready_for_design()
    test_spec_blocks_open_questions()
    test_spec_extracts_multiple_requirements_scope_risks_and_questions()
    test_spec_extracts_numbered_acceptance_section_from_prd()
    test_spec_adds_expert_quality_fields()
    test_spec_handles_one_line_request_with_inferred_acceptance()
    test_spec_handles_long_prd_without_collapsing_traceability()
    test_spec_exposes_complex_multi_impact_requirements()
    test_spec_blocks_permission_requirement_without_negative_acceptance()
    test_spec_blocks_conflicting_permission_rules()
    test_spec_extracts_state_transitions()
    test_technical_and_architecture_design_render_core_sections()
    test_design_options_are_generated_from_impact_surface()
    test_config_files_do_not_become_business_contracts()
    test_project_understanding_informs_design_and_architecture()
    test_delivery_runner_reports_next_stage()
    test_delivery_runner_allows_implementation_when_pre_edit_gates_pass()
    test_delivery_runner_requires_delivery_plan_review_before_git_edit()
    test_delivery_runner_blocks_when_profile_gate_readiness_fails()
    test_delivery_runner_requires_docs_and_fresh_git_before_implementation()
    test_delivery_runner_blocks_when_docs_quality_not_pass()
    test_delivery_runner_skips_conditional_cross_repo_stage_for_small_feature()


if __name__ == "__main__":
    run_all()
    print("PASS spec_and_design_governors tests")
