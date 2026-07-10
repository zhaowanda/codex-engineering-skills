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


ingest_requirement = load_module("ingest_requirement", ROOT / "skills/core/requirement-document-ingestor/scripts/ingest_requirement.py")
spec_governor = load_module("spec_governor", ROOT / "skills/core/spec-governor/scripts/spec_governor.py")
question_governor = load_module("question_governor", ROOT / "skills/core/requirement-question-governor/scripts/question_governor.py")
capture_case = load_module("capture_case", ROOT / "skills/core/delivery-case-capture/scripts/capture_case.py")


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_requirement_ingestor_normalizes_markdown() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        req = root / "requirement.md"
        req.write_text("# Export\n\nAC: file contains id.\n\n| field | rule |\n", encoding="utf-8")
        result = ingest_requirement.ingest(req, "REQ-1", root / "artifacts")
        assert result["schema"] == "codex-requirement-ingestion-v1"
        assert result["decision"] == "ready"
        assert result["features"]["table_like_lines"]
        assert (root / "artifacts/requirement.normalized.txt").exists()


def test_requirement_ingestor_blocks_pdf_without_text() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        pdf = root / "requirement.pdf"
        pdf.write_bytes(b"%PDF")
        result = ingest_requirement.ingest(pdf, "REQ-2", root / "artifacts")
        assert result["decision"] == "block"
        assert result["blockers"]


def test_question_governor_blocks_required_open_questions() -> None:
    spec = {
        "doc_id": "REQ-3",
        "acceptance_criteria": [],
        "open_questions": [{"id": "Q-1", "question": "Which fields?", "status": "open"}],
        "scope": {"in_scope": ["export"]},
    }
    result = question_governor.generate(spec)
    assert result["schema"] == "codex-open-questions-v1"
    assert result["decision"] == "block"
    validation = question_governor.validate_questions(result)
    assert validation["decision"] == "block"


def test_question_governor_passes_closed_required_questions() -> None:
    data = {
        "schema": "codex-open-questions-v1",
        "questions": [{"id": "Q-1", "required": True, "status": "closed", "answer": "id,status", "risk_if_unanswered": "wrong export fields"}],
    }
    result = question_governor.validate_questions(data)
    assert result["decision"] == "pass"


def test_question_governor_generates_expert_questions_from_impacts() -> None:
    spec = {
        "doc_id": "REQ-HIGH",
        "acceptance_criteria": [{"id": "AC-1", "criteria": "export succeeds", "source_evidence": "input"}],
        "scope": {"in_scope": ["payment export"], "out_of_scope": ["retry automation"]},
        "impact_surface": [{"area": "permission"}, {"area": "data"}, {"area": "api"}, {"area": "performance"}, {"area": "security"}],
        "implicit_constraints": [
            {"area": "permission", "question": "Which roles can export?", "status": "requires_confirmation"},
            {"area": "data", "question": "Which fields are exported?", "status": "requires_confirmation"},
        ],
        "negative_acceptance_criteria": [],
        "data_fields": [],
    }
    result = question_governor.generate(spec)
    questions = [item["question"] for item in result["questions"]]
    assert result["decision"] == "block"
    assert any("Which roles can export" in item for item in questions)
    assert any("Which data fields" in item for item in questions)
    assert any("endpoint" in item.lower() for item in questions)
    assert any("latency" in item.lower() for item in questions)
    assert any("sensitive fields" in item.lower() for item in questions)


def test_question_governor_blocks_closed_required_question_without_answer() -> None:
    data = {
        "schema": "codex-open-questions-v1",
        "questions": [{"id": "Q-1", "required": True, "status": "closed", "answer": ""}],
    }
    result = question_governor.validate_questions(data)
    assert result["decision"] == "block"
    assert any("answer" in item["message"] for item in result["blockers"])


def test_spec_blocks_ambiguous_requirement_without_real_goal_or_flow() -> None:
    spec = spec_governor.normalize("REQ-AMB", "续费优化", "优化续费流程，状态更新正确，功能正常。")
    validation = spec_governor.validate_spec(spec)
    assert spec["decision"] == "blocked"
    assert spec["design_allowed"] is False
    assert spec["requirements_understanding"]["decision"] == "needs_clarification"
    assert spec["requirements_understanding"]["level"] == "clarification_required"
    assert spec["inferred_assumptions"]
    assert validation["decision"] == "block"
    sources = {item["source"] for item in validation["blockers"]}
    assert "requirements_understanding" in sources
    categories = {item["category"] for item in spec["ambiguities"]}
    assert {"ambiguous_action", "state_transition", "acceptance"}.issubset(categories)


def test_spec_requires_explicit_business_purpose_not_inferred_goal() -> None:
    text = """
    入口: 订单列表导出按钮。
    流程: 运营点击订单列表导出按钮，系统调用导出接口并生成 Excel 文件。
    Req: 运营可以导出订单列表。
    AC: 给定运营点击导出按钮，系统生成包含订单号和状态的 Excel 文件。
    """
    spec = spec_governor.normalize("REQ-NO-GOAL", "订单导出", text)
    assert spec["design_allowed"] is False
    assert spec["requirements_understanding"]["level"] == "clarification_required"
    categories = {item["category"] for item in spec["ambiguities"]}
    assert "business_goal" in categories


def test_spec_blocks_ambiguous_auto_processing_and_unclear_defect() -> None:
    samples = [
        ("REQ-AUTO", "自动处理", "支持自动处理订单异常。"),
        ("REQ-BUG", "数据显示", "修复数据显示不正确。"),
    ]
    for doc_id, title, text in samples:
        spec = spec_governor.normalize(doc_id, title, text)
        assert spec["design_allowed"] is False
        assert spec["requirements_understanding"]["decision"] == "needs_clarification"
        assert spec["ambiguities"]


def test_spec_allows_clear_goal_flow_entrypoint_and_acceptance() -> None:
    text = """
    业务目的: 减少运营手工核对续费状态的时间。
    流程: 运营在续费列表点击重新试算按钮，系统调用续费试算接口并刷新当前设备的试算结果。
    入口: 续费列表的重新试算按钮。
    Req: 运营可以对单个设备重新触发续费试算。
    Rule: 只有有续费管理权限的运营角色可以触发。
    AC: 给定有权限运营在续费列表点击重新试算按钮，接口返回成功后页面展示新的试算金额和试算时间。
    AC: 无权限角色看不到重新试算按钮且直接调用接口返回无权限。
    """
    spec = spec_governor.normalize("REQ-CLEAR", "续费重新试算", text)
    validation = spec_governor.validate_spec(spec)
    assert spec["design_allowed"] is True
    assert spec["requirements_understanding"]["decision"] == "pass"
    assert spec["requirements_understanding"]["level"] == "expert_ready"
    assert spec["business_intent"]["confidence"] == "high"
    assert spec["business_flow"]
    assert spec["entrypoints"]
    assert validation["decision"] == "pass"


def test_spec_models_multi_entry_business_flow_and_scores() -> None:
    text = """
    业务目的: 减少运营和系统补偿续费状态不一致导致的人工排查。
    成功指标: 续费状态异常人工处理量下降 50%。
    现状: 当前已有续费列表重新试算按钮、renewal/recalculate 后端接口、renewal-status topic 消费者和夜间补偿 Task。
    流程: 运营在续费列表点击重新试算按钮，前端调用续费试算接口；后端复用试算服务并发送 renewal-status MQ；消费者刷新续费状态，夜间补偿 Task 处理超时未回调记录；无权限用户不可触发。
    入口: 续费列表重新试算按钮。
    入口: renewal-status MQ Consumer 消费续费状态消息。
    入口: 夜间续费状态补偿 Task。
    Req: 运营可以对单个设备重新触发续费试算并修复状态不一致。
    Rule: 只有续费管理权限角色可以触发前端重新试算。
    AC: 有权限运营点击重新试算按钮后，接口返回成功且页面展示新的试算金额和试算时间。
    AC: renewal-status MQ 消费失败时可以重试且不会重复更新同一条状态。
    AC: 夜间补偿 Task 只处理超时未回调记录。
    AC: 无权限角色看不到重新试算按钮且直接调用接口返回无权限。
    """
    spec = spec_governor.normalize("REQ-MULTI-ENTRY", "续费状态修复", text)
    assert spec["design_allowed"] is True
    assert spec["requirements_understanding"]["level"] == "expert_ready"
    assert spec["requirements_understanding"]["scorecard"]["dimensions"]["flow_score"] >= 90
    assert spec["business_flow_model"]["supports_multiple_entrypoints"] is True
    assert len(spec["entrypoints"]) >= 3
    branches = {item["type"] for item in spec["business_flow_model"]["branches"]}
    assert {"permission_denied", "retry", "timeout"}.issubset(branches)
    assert spec["current_business_state"]["known_current_facts"]
    assert spec["success_metrics"]


def test_question_governor_generates_categorized_clarification_for_ambiguous_spec() -> None:
    spec = spec_governor.normalize("REQ-AMB-Q", "订单同步", "支持订单同步，数据同步成功。")
    result = question_governor.generate(spec)
    assert result["decision"] == "block"
    categories = {item.get("category") for item in result["questions"]}
    assert {"ambiguous_action", "ambiguous_flow", "acceptance"}.issubset(categories)
    assert all(item.get("required") for item in result["questions"] if item.get("category") in {"ambiguous_action", "ambiguous_flow", "acceptance"})
    assert all(item.get("risk_if_unanswered") for item in result["questions"] if item.get("required"))


def test_question_governor_asks_from_weak_understanding_dimensions() -> None:
    spec = spec_governor.normalize("REQ-WEAK-SCORE", "订单导出", "Goal: reduce support work.\nReq: Admin exports orders.\nAC: exported file works.")
    result = question_governor.generate(spec)
    assert result["decision"] == "block"
    assert any(item.get("source", "").startswith("requirements_understanding.") for item in result["questions"])
    assert all(item.get("risk_if_unanswered") for item in result["questions"] if item.get("required"))


def test_delivery_case_capture_summarizes_artifacts() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_json(root / "spec.json", {"schema": "codex-spec-v1", "decision": "ready_for_design"})
        write_json(root / "test_evidence_gate.json", {"schema": "codex-test-evidence-gate-v1", "decision": "block", "blockers": [{"message": "failed"}]})
        result = capture_case.capture(root, "CASE-1")
        assert result["schema"] == "codex-delivery-case-v1"
        assert "spec.json" in result["artifact_summaries"]
        assert result["blockers_observed"]


def test_delivery_case_capture_can_emit_anonymized_replay_skeleton() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_json(root / "spec.json", {"schema": "codex-spec-v1", "decision": "ready_for_design", "blockers": []})
        result = capture_case.replay_skeleton(root, "CASE-REPLAY")
        assert result["schema"] == "codex-delivery-replay-skeleton-v1"
        assert result["anonymized"] is True
        assert result["artifacts"][0]["artifact"] == "spec.json"
        rendered = json.dumps(result)
        assert str(root) not in rendered


def run_all() -> None:
    test_requirement_ingestor_normalizes_markdown()
    test_requirement_ingestor_blocks_pdf_without_text()
    test_question_governor_blocks_required_open_questions()
    test_question_governor_passes_closed_required_questions()
    test_question_governor_generates_expert_questions_from_impacts()
    test_question_governor_blocks_closed_required_question_without_answer()
    test_spec_blocks_ambiguous_requirement_without_real_goal_or_flow()
    test_spec_requires_explicit_business_purpose_not_inferred_goal()
    test_spec_blocks_ambiguous_auto_processing_and_unclear_defect()
    test_spec_allows_clear_goal_flow_entrypoint_and_acceptance()
    test_spec_models_multi_entry_business_flow_and_scores()
    test_question_governor_generates_categorized_clarification_for_ambiguous_spec()
    test_question_governor_asks_from_weak_understanding_dimensions()
    test_delivery_case_capture_summarizes_artifacts()
    test_delivery_case_capture_can_emit_anonymized_replay_skeleton()


if __name__ == "__main__":
    run_all()
    print("PASS requirement_and_case_governors tests")
