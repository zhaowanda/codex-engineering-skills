from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


test_design = load_module("test_design", ROOT / "skills/core/test-design-governor/scripts/test_design.py")
spec_governor = load_module("spec_governor_for_specialized", ROOT / "skills/core/spec-governor/scripts/spec_governor.py")
technical_design = load_module("technical_design_for_specialized", ROOT / "skills/core/technical-design-governor/scripts/technical_design.py")
architecture_design = load_module("architecture_design_for_specialized", ROOT / "skills/core/architecture-design-governor/scripts/architecture_design.py")
test_data = load_module("test_data", ROOT / "skills/core/test-data-governor/scripts/test_data.py")
configuration = load_module("configuration", ROOT / "skills/core/configuration-governor/scripts/configuration.py")
performance = load_module("performance", ROOT / "skills/core/performance-governor/scripts/performance.py")
data_security = load_module("data_security", ROOT / "skills/core/data-security-governor/scripts/data_security.py")


def sample_docs():
    spec = {
        "doc_id": "REQ-1",
        "title": "Admin export",
        "requirement_summary": "Admin exports tenant payment report by email.",
        "requirements": [{"id": "REQ-1", "summary": "Admin exports tenant payment report"}],
        "acceptance_criteria": [{"id": "AC-1", "criteria": "Only admin can export filtered payment report", "evidence_required": ["test evidence"]}],
    }
    technical = {
        "doc_id": "REQ-1",
        "title": "Admin export",
        "api_contracts": [{"contract": "export API", "compatibility": "additive", "old_consumer_impact": "none"}],
        "ui_ue_design": [{"page_or_route": "/reports"}],
        "permission_model": [{"role": "admin", "rule": "tenant scope"}],
        "test_strategy": [{"case": "admin export"}],
    }
    architecture = {
        "doc_id": "REQ-1",
        "title": "Admin export",
        "repo_responsibilities": [
            {"repo": "web-app", "role": "modify"},
            {"repo": "api-service", "role": "modify"},
        ],
        "data_flow": [{"source": "database", "target": "export"}],
    }
    return spec, technical, architecture


def test_test_design_maps_acceptance_and_special_scopes() -> None:
    spec, technical, architecture = sample_docs()
    result = test_design.render(spec, technical, architecture)
    assert result["schema"] == "codex-test-design-v1"
    assert result["acceptance_count"] == 1
    assert result["test_data_required"] is True
    assert result["test_data_plan_ref"] == "test_data_plan.json"
    assert all(case.get("test_data_refs") for case in result["test_cases"])
    assert all(case.get("cleanup_expectations") for case in result["test_cases"])
    assert all(case.get("execution_path") for case in result["test_cases"] if case.get("acceptance_id"))
    assert all(case.get("assertion_points") for case in result["test_cases"] if case.get("acceptance_id"))
    assert all(case.get("execution_required") == "must_run" for case in result["test_cases"] if case.get("acceptance_id"))
    assert all(isinstance(case.get("data_setup_strategy"), dict) for case in result["test_cases"] if case.get("test_data_refs"))
    first_case = next(case for case in result["test_cases"] if case["id"] == "TC-1")
    assert "/reports" in " ".join(first_case["execution_path"])
    assert "export API" in " ".join(first_case["steps"] + first_case["assertion_points"])
    assert "admin" in " ".join(first_case["assertion_points"])
    assert first_case["semantic_refs"]["ui_refs"] == ["/reports"]
    assert "export API" in first_case["semantic_refs"]["api_refs"][0]
    assert any(case["type"] == "regression" for case in result["test_cases"])
    assert result["permission_scope"]
    assert result["integration_scope"]
    assert result["frontend_scope"]
    validation = test_design.validate_design(result)
    assert validation["decision"] == "pass"


def test_test_design_blocks_unclear_requirement_understanding() -> None:
    spec = spec_governor.normalize("REQ-AMB-TD", "Renewal optimization", "优化续费流程，状态更新正确，功能正常。")
    technical = technical_design.render(spec)
    architecture = architecture_design.render(spec, technical)
    result = test_design.render(spec, technical, architecture)
    assert result["decision"] == "block"
    assert result["requirements_understanding_gate"]["design_allowed"] is False
    validation = test_design.validate_design(result)
    assert validation["decision"] == "block"
    sources = {item["source"] for item in validation["blockers"]}
    assert "requirements_understanding_gate" in sources


def test_test_design_blocks_generic_steps() -> None:
    data = {
        "schema": "codex-test-design-v1",
        "acceptance_count": 1,
        "test_cases": [
            {
                "id": "TC-1",
                "acceptance_id": "AC-1",
                "type": "functional",
                "title": "generic",
                "steps": ["prepare data", "execute affected behavior", "verify expected result"],
                "expected_result": "passes",
                "evidence_required": ["test evidence"],
            }
        ],
        "regression_scope": [{"area": "changed behavior"}],
    }
    validation = test_design.validate_design(data)
    assert validation["decision"] == "block"
    assert any(item["source"] == "test_cases[0].steps" for item in validation["blockers"])


def test_test_design_blocks_placeholder_acceptance() -> None:
    data = {
        "schema": "codex-test-design-v1",
        "acceptance_count": 1,
        "test_cases": [
            {
                "id": "TC-1",
                "acceptance_id": "AC-1",
                "type": "functional",
                "title": "验证：标准",
                "steps": ["准备能触发该验收场景的代表性数据，并记录数据标识：标准"],
                "execution_path": ["BUSINESS: 准备代表性数据 -> 执行业务入口 -> 核对验收结果"],
                "assertion_points": ["验收描述可被直接观察或用证据复现：标准"],
                "data_setup_strategy": {"dataset_ref": "TD-TC-1"},
                "expected_result": "满足验收：标准",
                "evidence_required": ["功能测试"],
            },
            {
                "id": "TC-1-REG",
                "acceptance_id": "AC-1",
                "type": "regression",
                "title": "回归验证：标准 不破坏既有行为",
                "steps": ["执行与「标准」相邻的既有流程"],
                "execution_path": ["BUSINESS: 准备代表性数据 -> 执行业务入口 -> 核对验收结果"],
                "assertion_points": ["验收描述可被直接观察或用证据复现：标准"],
                "data_setup_strategy": {"dataset_ref": "TD-TC-1-REG"},
                "expected_result": "既有行为保持兼容，且本次验收仍通过",
                "evidence_required": ["回归测试证据"],
            },
        ],
        "regression_scope": [{"area": "changed behavior"}],
    }
    validation = test_design.validate_design(data)
    assert validation["decision"] == "block"
    assert any(item["source"] == "test_cases[0].acceptance" for item in validation["blockers"])


def test_test_design_blocks_acceptance_cases_without_execution_details() -> None:
    data = {
        "schema": "codex-test-design-v1",
        "acceptance_count": 1,
        "test_cases": [
            {
                "id": "TC-1",
                "acceptance_id": "AC-1",
                "type": "functional",
                "title": "验证：订单列表展示续期月份",
                "steps": ["打开订单列表并核对续期月份"],
                "expected_result": "满足验收：订单列表展示续期月份",
                "evidence_required": ["功能测试"],
                "test_data_refs": ["TD-TC-1"],
                "cleanup_expectations": ["清理 TD-TC-1"],
            },
            {
                "id": "TC-1-REG",
                "acceptance_id": "AC-1",
                "type": "regression",
                "title": "回归验证：订单列表展示续期月份 不破坏既有行为",
                "steps": ["执行相邻既有流程"],
                "expected_result": "既有行为保持兼容",
                "evidence_required": ["回归测试证据"],
            },
        ],
        "regression_scope": [{"area": "changed behavior"}],
    }
    validation = test_design.validate_design(data)
    assert validation["decision"] == "block"
    sources = {item["source"] for item in validation["blockers"]}
    assert "test_cases[0].assertion_points" in sources
    assert "test_cases[0].execution_path" in sources
    assert "test_cases[0].data_setup_strategy" in sources


def test_test_design_scopes_semantic_refs_per_acceptance() -> None:
    spec = {
        "doc_id": "REQ-SEM",
        "title": "Renewal optimization",
        "requirements": [{"id": "REQ-1", "summary": "Renewal list changes"}],
        "acceptance_criteria": [
            {"id": "AC-1", "criteria": "结算订单列表展示 `续期月份`。"},
            {"id": "AC-2", "criteria": "未授权角色不能移出续期池。"},
        ],
    }
    technical = {
        "ui_ue_design": [{"page_or_route": "/device/orderPivot"}],
        "api_contracts": [{"contract": "/device/orderPivot"}],
        "data_design": [
            {"slice": "BRK-1", "read_rule": "read through src/views/device/device.vue"},
            {"slice": "BRK-2", "read_rule": "read through src/views/device/pool.vue"},
        ],
        "permission_model": [{"role": "operator", "rule": "preserve existing permission boundary", "negative_case": "unauthorized user cannot access changed behavior"}],
    }
    result = test_design.render(spec, technical, {"repo_responsibilities": [{"repo": "operate-fe"}]})
    ac1 = next(case for case in result["test_cases"] if case["id"] == "TC-1")
    ac2 = next(case for case in result["test_cases"] if case["id"] == "TC-2")
    assert ac1["semantic_refs"]["permission_refs"] == []
    assert "BRK-1" in " ".join(ac1["semantic_refs"]["data_refs"])
    assert "BRK-2" in " ".join(ac2["semantic_refs"]["data_refs"])
    assert ac2["semantic_refs"]["permission_refs"]
    assert not any("PERMISSION:" in item for item in ac1["execution_path"])
    assert any("PERMISSION:" in item for item in ac2["execution_path"])


def test_test_data_governor_renders_plan_from_design() -> None:
    spec, technical, architecture = sample_docs()
    design = test_design.render(spec, technical, architecture)
    result = test_data.render(design)
    assert result["schema"] == "codex-test-data-plan-v1"
    assert result["decision"] == "pass"
    assert result["datasets"]
    assert result["case_data_matrix"]
    planned_ids = {item["id"] for item in result["datasets"]}
    required_ids = {ref for case in design["test_cases"] for ref in case["test_data_refs"]}
    assert required_ids.issubset(planned_ids)
    first_dataset = result["datasets"][0]
    assert first_dataset["setup_method"]
    assert first_dataset["records"][0]["source"] == "synthetic fixture"
    assert first_dataset["cleanup"][0]["owner"] == "test runner"


def test_test_data_governor_blocks_when_source_test_design_is_blocked() -> None:
    gate = {
        "decision": "needs_clarification",
        "design_allowed": False,
        "implementation_allowed": False,
        "blockers": [{"source": "business_flow", "message": "missing flow"}],
    }
    design = {
        "schema": "codex-test-design-v1",
        "decision": "block",
        "doc_id": "REQ-AMB",
        "requirements_understanding_gate": gate,
        "test_cases": [
            {
                "id": "TC-1",
                "title": "验证：模糊需求",
                "type": "functional",
                "test_data_refs": ["TD-TC-1"],
                "cleanup_expectations": ["清理 TD-TC-1"],
            }
        ],
    }
    result = test_data.render(design)
    assert result["decision"] == "block"
    sources = {item["source"] for item in result["blockers"]}
    assert {"test_design", "requirements_understanding_gate"}.issubset(sources)


def test_test_data_governor_uses_case_data_setup_strategy() -> None:
    design = {
        "schema": "codex-test-design-v1",
        "doc_id": "REQ-1",
        "title": "Renewal list",
        "test_cases": [
            {
                "id": "TC-1",
                "title": "验证：续期月份字段展示",
                "type": "functional",
                "test_data_refs": ["TD-CUSTOM"],
                "data_setup_strategy": {
                    "dataset_ref": "TD-CUSTOM",
                    "setup_methods": ["fixture_or_factory", "sql_seed"],
                    "records": [{"name": "续期订单", "state": "已结算", "source": "synthetic fixture"}],
                    "accounts": [{"role": "operator", "purpose": "验证列表展示"}],
                    "cleanup": ["删除续期订单合成记录"],
                    "privacy": ["只使用 synthetic/anonymized 数据"],
                },
            }
        ],
    }
    result = test_data.render(design)
    assert result["decision"] == "pass"
    dataset = result["datasets"][0]
    assert dataset["id"] == "TD-CUSTOM"
    assert dataset["setup_method"] == "fixture_or_factory+sql_seed"
    assert dataset["records"][0]["name"] == "续期订单"
    assert dataset["accounts"][0]["role"] == "operator"
    assert dataset["cleanup"][0]["method"] == "删除续期订单合成记录"


def test_test_data_governor_blocks_sensitive_or_incomplete_data() -> None:
    plan = {
        "schema": "codex-test-data-plan-v1",
        "datasets": [
            {
                "id": "TD-TC-1",
                "case_ids": ["TC-1"],
                "data_classification": "production",
                "setup_method": "",
                "records": [{"name": "real customer fixture"}],
                "cleanup": [],
            }
        ],
        "case_data_matrix": [{"case_id": "TC-1", "dataset_ids": ["TD-TC-1"]}],
    }
    validation = test_data.validate_plan(plan)
    assert validation["decision"] == "block"
    messages = " ".join(item["message"] for item in validation["blockers"])
    assert "setup_method" in messages
    assert "cleanup" in messages
    assert "sensitive" in messages or "production" in messages


def test_configuration_ignores_business_terms_without_runtime_config_context() -> None:
    spec, technical, architecture = sample_docs()
    result = configuration.analyze(spec, technical, architecture)
    assert result["schema"] == "codex-configuration-readiness-v1"
    assert result["applicable"] is False
    assert result["configuration_items"] == []
    assert result["decision"] == "ready"
    assert result["blockers"] == []


def test_configuration_blocks_incomplete_explicit_runtime_config() -> None:
    result = configuration.analyze(
        {"doc_id": "REQ-CONFIG"},
        {
            "configuration_items": [
                {"key": "feishu_callback_url", "type": "callback", "required": True, "default_strategy": "disabled until configured"}
            ]
        },
        {},
    )
    assert result["applicable"] is True
    kinds = {item["type"] for item in result["configuration_items"]}
    assert kinds == {"callback"}
    assert result["decision"] == "blocked"
    messages = {item["message"] for item in result["blockers"]}
    assert "owner is required" in messages
    assert "rollback_strategy is required" in messages


def test_performance_requires_evidence_for_api_database_export_ui() -> None:
    spec, technical, architecture = sample_docs()
    result = performance.design_review(spec, technical, architecture)
    assert result["schema"] == "codex-performance-review-v1"
    assert result["decision"] == "ready"
    assert result["evidence_status"] == "needs_evidence"
    areas = {item["area"] for item in result["evidence_plan"]}
    assert "api" in areas
    assert "database" in areas
    assert "throughput" in areas
    assert "frontend" in areas


def test_data_security_detects_sensitive_signals() -> None:
    spec, technical, architecture = sample_docs()
    result = data_security.design_review(spec, technical, architecture)
    assert result["schema"] == "codex-data-security-review-v1"
    assert result["decision"] == "ready"
    assert result["review_status"] == "needs_review"
    assert "payment" in result["sensitive_signals"]
    assert result["controls_required"]


def run_all() -> None:
    test_test_design_maps_acceptance_and_special_scopes()
    test_test_design_blocks_unclear_requirement_understanding()
    test_test_design_blocks_generic_steps()
    test_test_design_blocks_placeholder_acceptance()
    test_test_design_blocks_acceptance_cases_without_execution_details()
    test_test_design_scopes_semantic_refs_per_acceptance()
    test_test_data_governor_renders_plan_from_design()
    test_test_data_governor_blocks_when_source_test_design_is_blocked()
    test_test_data_governor_uses_case_data_setup_strategy()
    test_test_data_governor_blocks_sensitive_or_incomplete_data()
    test_configuration_ignores_business_terms_without_runtime_config_context()
    test_configuration_blocks_incomplete_explicit_runtime_config()
    test_performance_requires_evidence_for_api_database_export_ui()
    test_data_security_detects_sensitive_signals()


if __name__ == "__main__":
    run_all()
    print("PASS specialized_governors tests")
