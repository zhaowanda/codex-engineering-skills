from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/core/auto-runner/scripts/auto_runner.py"
spec = importlib.util.spec_from_file_location("auto_runner", SCRIPT)
auto_runner = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(auto_runner)

HARNESS_SCRIPT = ROOT / "skills/core/auto-runner/scripts/harness_validation.py"
harness_spec = importlib.util.spec_from_file_location("harness_validation", HARNESS_SCRIPT)
harness_validation = importlib.util.module_from_spec(harness_spec)
assert harness_spec.loader
harness_spec.loader.exec_module(harness_validation)


def prepare_runtime_checkpoint(root: Path, checkpoint: str) -> None:
    runtime = harness_validation.AGENT_RUNTIME
    runtime.start(root, "REQ-HARNESS")
    actions = {
        "source_location": ["requirement_ingested"],
        "design": ["design_completed"],
        "post_implementation": ["write_completed", "implementation_validated"],
        "pre_push": ["test_completed", "review_completed", "push_authorized"],
    }[checkpoint]
    for action in actions:
        runtime.append_event(root, action, "test")
    runtime.checkpoint(root, harness_validation.RUNTIME_CHECKPOINTS[checkpoint], ["test-evidence"])


def write_workspace_docs_config(docs_root: Path) -> str | None:
    config_file = ROOT / ".codex-engineering-docs.json"
    original = config_file.read_text(encoding="utf-8") if config_file.exists() else None
    config_file.write_text(
        json.dumps({"schema": "codex-docs-workspace-config-v1", "docs_root": str(docs_root), "git_url": ""}),
        encoding="utf-8",
    )
    return original


def restore_workspace_docs_config(original: str | None) -> None:
    config_file = ROOT / ".codex-engineering-docs.json"
    if original is None:
        config_file.unlink(missing_ok=True)
    else:
        config_file.write_text(original, encoding="utf-8")


def test_auto_runner_generates_core_artifacts() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "artifacts"
        config_file = ROOT / ".codex-engineering-docs.json"
        original = config_file.read_text(encoding="utf-8") if config_file.exists() else None
        restore_workspace_docs_config(None)
        try:
            result = auto_runner.run(
                input_path=ROOT / "examples/synthetic-e2e-case/requirement.md",
                doc_id="REQ-AUTO-1",
                title="Order export",
                out=out,
            )
        finally:
            restore_workspace_docs_config(original)
        assert result["schema"] == "codex-auto-runner-summary-v1"
        assert (out / "requirement.normalized.txt").exists()
        assert (out / "spec.json").exists()
        assert (out / "technical_design.json").exists()
        assert (out / "architecture_design.json").exists()
        assert (out / "test_design.json").exists()
        assert (out / "docs_quality.json").exists()
        assert (out / "delivery_plan.json").exists()
        assert (out / "delivery_plan_review.json").exists()
        assert (out / "auto_run_summary.json").exists()
        assert result["workflow_profile"].get("base_profile", result["workflow_profile"]["name"]) in {"small_feature", "cross_repo_api", "bugfix", "frontend_change", "data_migration"}
        assert "delivery-plan-reviewer" in result["required_gates"]
        assert "profile_gate_gaps" in result
        assert result["profile_selection_score"] > 0
        assert result["profile_selection_confidence"] in {"high", "medium", "low"}
        assert result["profile_selection_candidates"]
        assert result["workflow_strictness"]["tier"] in {"light", "standard", "regulated"}
        assert result["effective_workflow_controls"]["required_skills"]
        assert result["workflow_metrics"]["governance_level"] in {"light", "standard", "heavy", "critical"}
        assert result["workflow_metrics"]["executed_step_count"] > 0
        assert result["workflow_metrics"]["total_command_duration_ms"] >= 0
        assert result["workflow_metrics"]["cost_budget_decision"] in {"pass", "warn"}
        assert "invalidated_artifact_count" in result["workflow_metrics"]
        assert "strictness_gate_gaps" in result
        assert result["docs_readiness"]["decision"] == "block"
        assert result["next_stage"]
        assert result["can_implement"] is False


def test_harness_validation_blocks_reference_only_edit_target() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = root / "project_understanding"
        project.mkdir(parents=True)
        (project / "evidence_bundle.json").write_text(json.dumps({
            "schema": "codex-evidence-bundle-v1",
            "anchors": [
                {"path": "src/main.vue", "role": "confirmed_modify"},
                {"path": "src/reference.vue", "role": "confirmed_reference"},
            ],
        }), encoding="utf-8")
        (root / "delivery_plan.json").write_text(json.dumps({"allowed_files": ["src/reference.vue"]}), encoding="utf-8")
        result = harness_validation.validate(root)
        assert result["decision"] == "block"
        assert any(item["source"] == "evidence_consistency" for item in result["blockers"])


def test_harness_validation_blocks_oversized_artifact() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "spec.json").write_text(json.dumps({"value": "x" * 500}), encoding="utf-8")
        result = harness_validation.validate(root, {"spec.json": 100})
        assert result["decision"] == "block"
        assert result["artifact_sizes"][0]["within_budget"] is False


def test_harness_source_location_blocks_stale_source_digest() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo = root / "repo"
        source = repo / "src/main.py"
        source.parent.mkdir(parents=True)
        source.write_text("def current(): pass\n", encoding="utf-8")
        project = root / "project_understanding"
        project.mkdir()
        (project / "evidence_bundle.json").write_text(json.dumps({
            "repo_root": str(repo),
            "anchors": [{
                "path": "src/main.py",
                "role": "confirmed_modify",
                "confidence": "high",
                "source_digest": "stale",
            }],
        }), encoding="utf-8")

        result = harness_validation.validate(root, checkpoint="source_location", repo=repo)

        assert result["decision"] == "block"
        assert any(item["message"] == "source digest is missing or stale" for item in result["blockers"])


def test_harness_source_location_blocks_requirement_irrelevant_anchor() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo = root / "repo"
        source = repo / "src/views/plugIn/accidentAnalysis.vue"
        source.parent.mkdir(parents=True)
        source.write_text("openPlaybackDialog playbackStreamControl DualCameraLivePlayer\n", encoding="utf-8")
        project = root / "project_understanding"
        project.mkdir()
        digest = harness_validation.sha256(source)
        (root / "requirement.normalized.txt").write_text(
            "物联网卡到期监控：前端入口为 src/views/device/iotCardMonitor.vue，后端生成 IoT 续费结算单并发送飞书通知。",
            encoding="utf-8",
        )
        (project / "evidence_bundle.json").write_text(json.dumps({
            "repo_root": str(repo),
            "anchors": [{
                "path": "src/views/plugIn/accidentAnalysis.vue",
                "role": "confirmed_modify",
                "confidence": "high",
                "source_digest": digest,
                "matched_symbols": ["openPlaybackDialog", "DualCameraLivePlayer"],
                "matched_contract_terms": ["/operate/api/dualCamera/playbackStreamControl"],
                "evidence_chain": [{"term": "playbackStreamControl", "line": 1}],
            }],
        }), encoding="utf-8")

        result = harness_validation.validate(root, checkpoint="source_location", repo=repo)

        assert result["decision"] == "block"
        assert any(item["message"] == "confirmed modify anchor is not supported by requirement text" for item in result["blockers"])


def test_harness_source_location_rejects_parent_traversal() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = root / "project_understanding"
        project.mkdir()
        (project / "evidence_bundle.json").write_text(json.dumps({
            "anchors": [{
                "path": "../outside.py",
                "role": "confirmed_modify",
                "confidence": "high",
                "source_digest": "digest",
            }],
        }), encoding="utf-8")

        result = harness_validation.validate(root, checkpoint="source_location", repo=root)

        assert result["decision"] == "block"
        assert any(item["message"] == "confirmed modify anchor is not a safe relative path" for item in result["blockers"])


def test_harness_design_requires_sequence_for_api_change() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "spec.json").write_text(json.dumps({
            "impact_applicability": [{"area": "api", "status": "required"}],
        }), encoding="utf-8")
        (root / "technical_design.json").write_text(json.dumps({"process_flow": [{"steps": ["call API"]}]}), encoding="utf-8")
        (root / "architecture_design.json").write_text(json.dumps({}), encoding="utf-8")
        (root / "delivery_plan.json").write_text(json.dumps({}), encoding="utf-8")

        result = harness_validation.validate(root, checkpoint="design")

        assert result["decision"] == "block"
        messages = {item["message"] for item in result["blockers"]}
        assert "applicable cross-component change requires a populated system interaction sequence" in messages
        assert "architecture design is missing integration_sequence" in messages


def test_harness_blocks_single_repo_multi_repo_claim() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "spec.json").write_text(json.dumps({"repo_impact_map": {"repos": [{"name": "web"}], "multi_repo_required": True}}), encoding="utf-8")
        (root / "technical_design.json").write_text(json.dumps({"process_flow": [{"steps": ["change"]}]}), encoding="utf-8")
        (root / "architecture_design.json").write_text("{}", encoding="utf-8")
        (root / "delivery_plan.json").write_text("{}", encoding="utf-8")
        result = harness_validation.validate(root, checkpoint="design")
        assert any(item["source"] == "repository_scope" for item in result["blockers"])


def test_harness_blocks_protected_scope_change_without_design_change() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "spec.json").write_text(json.dumps({"scope_model": {"reference_only": ["src/reference.vue"]}}), encoding="utf-8")
        (root / "implementation_completion_gate.json").write_text(json.dumps({"decision": "pass", "changed_files": ["src/reference.vue"]}), encoding="utf-8")
        (root / "delivery_plan.json").write_text(json.dumps({"repo_tasks": [{"role": "modify", "allowed_files": ["src/reference.vue"]}]}), encoding="utf-8")
        result = harness_validation.validate(root, checkpoint="post_implementation")
        assert any(item["source"] == "post_change_drift" for item in result["blockers"])


def test_harness_design_allows_explicit_planned_new_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = root / "project_understanding"
        project.mkdir()
        (project / "evidence_bundle.json").write_text(json.dumps({
            "anchors": [{"path": "src/existing.py", "role": "confirmed_modify"}],
        }), encoding="utf-8")
        (root / "spec.json").write_text(json.dumps({}), encoding="utf-8")
        (root / "technical_design.json").write_text(json.dumps({
            "process_flow": [{"steps": ["create module"]}],
            "process_flow_diagram": "```mermaid\nflowchart TD\n  A[create module] --> B[done]\n```",
            "implementation_files": [{"path": "src/new_module.py", "status": "planned_new"}],
        }), encoding="utf-8")
        (root / "architecture_design.json").write_text(json.dumps({}), encoding="utf-8")
        (root / "delivery_plan.json").write_text(json.dumps({}), encoding="utf-8")
        prepare_runtime_checkpoint(root, "design")

        result = harness_validation.validate(root, checkpoint="design")

        assert result["decision"] == "pass"
        assert result["evidence_summary"]["planned_new"] == ["src/new_module.py"]


def test_harness_post_implementation_blocks_plan_to_diff_drift() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "implementation_completion_gate.json").write_text(json.dumps({
            "decision": "pass",
            "changed_files": ["src/unplanned.py"],
        }), encoding="utf-8")
        (root / "delivery_plan.json").write_text(json.dumps({
            "repo_tasks": [{"role": "modify", "allowed_files": ["src/planned.py"]}],
        }), encoding="utf-8")

        result = harness_validation.validate(root, checkpoint="post_implementation")

        assert result["decision"] == "block"
        assert any(item.get("files") == ["src/unplanned.py"] for item in result["blockers"])


def test_harness_pre_push_blocks_missing_project_skill_index_sync() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "post_change_implementation_report.json").write_text(json.dumps({
            "decision": "pass",
            "project_skill_index_requirements": {"required": True, "status": "missing_evidence"},
        }), encoding="utf-8")
        (root / "post_implementation_traceability_matrix.json").write_text(json.dumps({"decision": "pass"}), encoding="utf-8")
        (root / "test_evidence_gate.json").write_text(json.dumps({"decision": "pass"}), encoding="utf-8")
        (root / "code_review_gate.json").write_text(json.dumps({"decision": "approve"}), encoding="utf-8")

        result = harness_validation.validate(root, checkpoint="pre_push")

        assert result["decision"] == "block"
        assert any(item["source"] == "project_skill_index_sync" for item in result["blockers"])


def test_harness_pre_push_blocks_test_evidence_without_commit_binding() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo = root / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, text=True, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "harness@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Harness Test"], cwd=repo, check=True)
        (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=repo, text=True, capture_output=True, check=True)
        (root / "post_change_implementation_report.json").write_text(json.dumps({
            "decision": "pass",
            "project_skill_index_requirements": {"required": False, "status": "not_required"},
        }), encoding="utf-8")
        (root / "post_implementation_traceability_matrix.json").write_text(json.dumps({"decision": "pass"}), encoding="utf-8")
        (root / "test_evidence_gate.json").write_text(json.dumps({"decision": "pass"}), encoding="utf-8")
        (root / "code_review_gate.json").write_text(json.dumps({"decision": "approve"}), encoding="utf-8")

        result = harness_validation.validate(root, checkpoint="pre_push", repo=repo)

        assert result["decision"] == "block"
        assert any(item["message"] == "test evidence does not declare git_head or git_sha" for item in result["blockers"])


def test_harness_pre_push_blocks_uncommitted_delivery_docs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = root / "docs"
        subprocess.run(["git", "init", str(docs_root)], text=True, capture_output=True, check=True)
        doc_id = "REQ-DOCS-PRE-PUSH"
        docs_artifacts = root / "docs-artifacts"
        (docs_artifacts / "spec.json").parent.mkdir(parents=True)
        (docs_artifacts / "spec.json").write_text(json.dumps({"schema": "codex-spec-v1", "doc_id": doc_id}), encoding="utf-8")
        harness_validation.DOCS_GOVERNOR.sync(docs_root, doc_id, docs_artifacts, "Docs pre-push")
        prepare_runtime_checkpoint(root, "pre_push")
        (root / "post_change_implementation_report.json").write_text(json.dumps({
            "decision": "pass",
            "project_skill_index_requirements": {"required": False, "status": "not_required"},
            "docs_binding": {"docs_root": str(docs_root), "doc_id": doc_id, "status": "bound"},
        }), encoding="utf-8")
        (root / "post_implementation_traceability_matrix.json").write_text(json.dumps({"decision": "pass"}), encoding="utf-8")
        (root / "test_evidence_gate.json").write_text(json.dumps({"decision": "pass"}), encoding="utf-8")
        (root / "code_review_gate.json").write_text(json.dumps({"decision": "approve"}), encoding="utf-8")
        (root / "harness/post_implementation.json").parent.mkdir(parents=True)
        (root / "harness/post_implementation.json").write_text(json.dumps({"decision": "pass"}), encoding="utf-8")

        result = harness_validation.validate(root, checkpoint="pre_push")

        assert result["decision"] == "block"
        assert any(item["source"] == "docs_sync" and "uncommitted" in item["message"] for item in result["blockers"])


def test_auto_runner_accepts_ready_docs_repo() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = root / "delivery-docs"
        docs_root.mkdir(parents=True)
        subprocess.run(["git", "init"], cwd=docs_root, text=True, capture_output=True, check=True)
        out = root / "artifacts"
        result = auto_runner.run(
            input_path=ROOT / "examples/synthetic-e2e-case/requirement.md",
            doc_id="REQ-AUTO-DOCS",
            title="Order export",
            out=out,
            docs_root=docs_root,
        )
        assert result["docs_readiness"]["decision"] == "pass"
        assert result["docs_sync"]["decision"] == "pass"
        assert result["doc_language"] == "zh"
        assert (docs_root / "indexes/REQ-AUTO-DOCS.manifest.json").exists()
        spec_doc = (docs_root / "human/specs/REQ-AUTO-DOCS.md").read_text(encoding="utf-8")
        design_doc = (docs_root / "human/designs/REQ-AUTO-DOCS.md").read_text(encoding="utf-8")
        test_doc = (docs_root / "human/tests/REQ-AUTO-DOCS.md").read_text(encoding="utf-8")
        release_doc = (docs_root / "human/releases/REQ-AUTO-DOCS.md").read_text(encoding="utf-8")
        assert "## 一、摘要" in spec_doc
        assert "## 二、背景与目标" in spec_doc
        assert "## 三、范围与非目标" in spec_doc
        assert "## 四、需求澄清" in spec_doc
        assert "### 澄清记录" in spec_doc
        assert "### 澄清状态" in spec_doc
        assert "### 已确认理解" in spec_doc
        assert "### 待澄清问题" in spec_doc
        assert "### 工作假设" in spec_doc
        assert "是否允许进入设计：是" in spec_doc
        assert "## 六、验收标准" in spec_doc
        assert "## 八、需求到验收追踪图" in spec_doc
        assert "`AC-1` exported file contains order id and status." in spec_doc
        assert "```mermaid" in spec_doc + design_doc + release_doc
        assert "## 二、现状问题与设计目标" in design_doc
        assert "## 四、候选方案、对比与决策" in design_doc
        assert "### 技术候选方案详述" in design_doc
        assert "### 技术方案加权对比" in design_doc
        assert "### 技术决策结论" in design_doc
        assert design_doc.index("### 技术候选方案详述") < design_doc.index("### 技术方案加权对比") < design_doc.index("### 技术决策结论")
        assert "### 架构候选方案详述" in design_doc
        assert "### 架构方案加权对比" in design_doc
        assert "### 架构决策结论" in design_doc
        assert design_doc.index("### 架构候选方案详述") < design_doc.index("### 架构方案加权对比") < design_doc.index("### 架构决策结论")
        assert "## 五、决策记录" in design_doc
        assert "## 六、业务流程" in design_doc
        assert "### 数据模型与表结构" in design_doc
        assert "### 多系统交互时序" in design_doc
        assert "### MQ 上下游与触发机制" in design_doc
        assert "### 缓存策略评估" in design_doc
        assert "### 事务与一致性" in design_doc
        assert "### 可观测性设计" in design_doc
        assert "## 十三、风险与未过门禁" in design_doc
        assert "## 十二、测试策略摘要" in design_doc
        assert "### 测试用例" not in design_doc
        assert "`TC-1`" not in design_doc
        assert "Acceptance:" not in design_doc
        assert "## 四、测试用例" in test_doc
        assert "`TC-1`" in test_doc
        assert "关联验收" in test_doc
        assert "为什么测" in test_doc
        assert "项目语义依据" in test_doc
        assert "怎么造数" in test_doc
        assert "怎么执行" in test_doc
        assert "怎么判定通过" in test_doc
        assert "清理要求" in test_doc
        assert "## 六、回归、集成、前端与权限范围" in test_doc
        assert "## 二、发布前检查" in release_doc
        assert "## 三、执行步骤" in release_doc
        assert "## 四、发布与回滚顺序图" in release_doc
        assert "### 测试用例" in release_doc
        assert "### 实现前必须补齐" in release_doc
        assert "## Executive Summary" not in spec_doc + design_doc + test_doc + release_doc
        assert "Evidence References" not in spec_doc + design_doc + test_doc + release_doc
        assert "- -" not in spec_doc + design_doc + test_doc + release_doc
        assert "[{\"" not in spec_doc + design_doc + test_doc + release_doc
        assert "{\"in_scope\"" not in spec_doc
        assert "acceptance_criteria:" not in spec_doc
        machine_spec = json.loads((docs_root / "machine/specs/REQ-AUTO-DOCS.spec.json").read_text(encoding="utf-8"))
        assert machine_spec["schema"] == "codex-docs-machine-bundle-v1"
        assert "spec.json" in machine_spec["artifacts"]
        assert (docs_root / "machine/raw/REQ-AUTO-DOCS/auto_run_summary.json").exists()


def test_auto_runner_can_generate_chinese_human_docs_when_requested() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = root / "delivery-docs"
        docs_root.mkdir(parents=True)
        subprocess.run(["git", "init"], cwd=docs_root, text=True, capture_output=True, check=True)
        out = root / "artifacts"
        result = auto_runner.run(
            input_path=ROOT / "examples/synthetic-e2e-case/requirement.md",
            doc_id="REQ-AUTO-ZH",
            title="订单导出",
            out=out,
            docs_root=docs_root,
            doc_language="zh",
        )
        assert result["doc_language"] == "zh"
        spec_doc = (docs_root / "human/specs/REQ-AUTO-ZH.md").read_text(encoding="utf-8")
        design_doc = (docs_root / "human/designs/REQ-AUTO-ZH.md").read_text(encoding="utf-8")
        test_doc = (docs_root / "human/tests/REQ-AUTO-ZH.md").read_text(encoding="utf-8")
        release_doc = (docs_root / "human/releases/REQ-AUTO-ZH.md").read_text(encoding="utf-8")
        assert "## 一、摘要" in spec_doc
        assert "### 阅读与评审重点" in spec_doc
        assert "验收规模" in spec_doc
        assert "## 二、背景与目标" in spec_doc
        assert "## 四、需求澄清" in spec_doc
        assert "### 澄清记录" in spec_doc
        assert "## 八、需求到验收追踪图" in spec_doc
        assert "## 二、现状问题与设计目标" in design_doc
        assert "设计覆盖" in design_doc
        assert "实施边界" in design_doc
        assert "## 三、子需求设计矩阵" in design_doc
        assert "## 四、候选方案、对比与决策" in design_doc
        assert "### 技术候选方案详述" in design_doc
        assert "### 技术方案加权对比" in design_doc
        assert "### 技术决策结论" in design_doc
        assert design_doc.index("### 技术候选方案详述") < design_doc.index("### 技术方案加权对比") < design_doc.index("### 技术决策结论")
        assert "### 架构候选方案详述" in design_doc
        assert "### 架构方案加权对比" in design_doc
        assert "### 架构决策结论" in design_doc
        assert design_doc.index("### 架构候选方案详述") < design_doc.index("### 架构方案加权对比") < design_doc.index("### 架构决策结论")
        assert "## 五、决策记录" in design_doc
        assert "## 六、业务流程" in design_doc
        assert "## 七、模块与接口设计" in design_doc
        assert "### 数据模型与表结构" in design_doc
        assert "### 多系统交互时序" in design_doc
        assert "### MQ 上下游与触发机制" in design_doc
        assert "### 缓存策略评估" in design_doc
        assert "### 事务与一致性" in design_doc
        assert "### 可观测性设计" in design_doc
        assert "## 十、交付执行计划" in design_doc
        assert "## 十一、需求追踪关系" in design_doc
        assert "## 十二、测试策略摘要" in design_doc
        assert "### 测试用例" not in design_doc
        assert "`TC-1`" not in design_doc
        assert "## 四、测试用例" in test_doc
        assert "`TC-1`" in test_doc
        assert "关联验收" in test_doc
        assert "为什么测" in test_doc
        assert "项目语义依据" in test_doc
        assert "怎么造数" in test_doc
        assert "怎么执行" in test_doc
        assert "怎么判定通过" in test_doc
        assert "清理要求" in test_doc
        assert "## 五、测试数据准备" in test_doc
        assert "## 六、回归、集成、前端与权限范围" in test_doc
        assert "## 二、发布前检查" in release_doc
        assert "放行原则" in release_doc
        assert "## 四、发布与回滚顺序图" in release_doc
        assert "### 测试用例" in release_doc
        assert "```mermaid" in spec_doc + design_doc + release_doc
        assert "## Executive Summary" not in spec_doc + design_doc + test_doc + release_doc
        assert "Evidence References" not in spec_doc + design_doc + test_doc + release_doc
        assert "Role:" not in design_doc + release_doc
        assert "edit files:" not in design_doc + release_doc
        assert "evidence:" not in spec_doc + design_doc + test_doc + release_doc


def test_auto_runner_auto_detects_chinese_doc_request() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        req = root / "requirement.md"
        req.write_text(
            "文档使用中文描述。\nAC: exported file contains order id and status.",
            encoding="utf-8",
        )
        docs_root = root / "delivery-docs"
        docs_root.mkdir()
        subprocess.run(["git", "init"], cwd=docs_root, text=True, capture_output=True, check=True)
        result = auto_runner.run(req, doc_id="REQ-AUTO-ZH-HINT", out=root / "artifacts", docs_root=docs_root, doc_language="auto")
        assert result["doc_language"] == "zh"
        assert "## 四、需求澄清" in (docs_root / "human/specs/REQ-AUTO-ZH-HINT.md").read_text(encoding="utf-8")


def test_auto_runner_blocked_spec_does_not_rewrite_design_doc() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        req = root / "requirement.md"
        req.write_text("优化播放体验。", encoding="utf-8")
        docs_root = root / "delivery-docs"
        docs_root.mkdir()
        subprocess.run(["git", "init"], cwd=docs_root, text=True, capture_output=True, check=True)
        docs_governor = auto_runner.load_docs_governor_module()
        docs_governor.init(docs_root, "REQ-SPEC-ONLY", title="播放优化", doc_language="zh")
        design_path = docs_root / "human/designs/REQ-SPEC-ONLY.md"
        design_path.write_text("# existing design\n", encoding="utf-8")
        result = auto_runner.run(req, doc_id="REQ-SPEC-ONLY", out=root / "artifacts", docs_root=docs_root, doc_language="zh")
        assert result["decision"] == "block"
        assert design_path.read_text(encoding="utf-8") == "# existing design\n"


def test_auto_runner_defaults_to_auto_doc_language_detection() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        req = root / "requirement.md"
        req.write_text(
            "需求：导出订单。\n文档使用中文。\nAC: exported file contains order id and status.",
            encoding="utf-8",
        )
        docs_root = root / "delivery-docs"
        docs_root.mkdir()
        subprocess.run(["git", "init"], cwd=docs_root, text=True, capture_output=True, check=True)
        result = auto_runner.run(req, doc_id="REQ-AUTO-ZH-DEFAULT", out=root / "artifacts", docs_root=docs_root)
        assert result["doc_language"] == "zh"
        assert "## 一、摘要" in (docs_root / "human/specs/REQ-AUTO-ZH-DEFAULT.md").read_text(encoding="utf-8")


def test_auto_runner_blocks_docs_root_without_git_repo() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = root / "delivery-docs"
        manifest = docs_root / "indexes/REQ-AUTO-DOCS.manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text("{}", encoding="utf-8")
        out = root / "artifacts"
        result = auto_runner.run(
            input_path=ROOT / "examples/synthetic-e2e-case/requirement.md",
            doc_id="REQ-AUTO-DOCS",
            title="Order export",
            out=out,
            docs_root=docs_root,
        )
        assert result["docs_readiness"]["decision"] == "block"
        assert any(item["source"] == "docs_git" for item in result["docs_readiness"]["blockers"])


def test_auto_runner_uses_configured_docs_root_by_default() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = root / "delivery-docs"
        manifest = docs_root / "indexes/REQ-AUTO-CONFIG.manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text("{}", encoding="utf-8")
        subprocess.run(["git", "init"], cwd=docs_root, text=True, capture_output=True, check=True)
        original = write_workspace_docs_config(docs_root)
        try:
            result = auto_runner.run(
                input_path=ROOT / "examples/synthetic-e2e-case/requirement.md",
                doc_id="REQ-AUTO-CONFIG",
                title="Order export",
                out=root / "artifacts",
            )
            assert result["docs_readiness"]["decision"] == "pass"
            assert result["docs_readiness"]["docs_root"] == str(docs_root)
        finally:
            restore_workspace_docs_config(original)


def test_auto_runner_is_idempotent_without_force() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "artifacts"
        auto_runner.run(ROOT / "examples/synthetic-e2e-case/requirement.md", doc_id="REQ-AUTO-2", out=out)
        second = auto_runner.run(ROOT / "examples/synthetic-e2e-case/requirement.md", doc_id="REQ-AUTO-2", out=out)
        assert "requirement_ingestion.json" in second["skipped_artifacts"]
        assert "spec.json" in second["skipped_artifacts"]
        assert second["workflow_metrics"]["reused_artifact_count"] > 0
        assert second["workflow_metrics"]["reused_artifact_count"] < second["workflow_metrics"]["skipped_step_count"]


def test_auto_runner_reuses_clarification_answers_as_spec_input() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        requirement = root / "requirement.md"
        requirement.write_text("优化设备视频回放。", encoding="utf-8")
        out = root / "artifacts"
        first = auto_runner.run(requirement, doc_id="REQ-CLARIFIED", out=out)
        assert first["next_command"] == f"python3 scripts/codex_eng.py clarify --artifact-dir {out.resolve()}"
        (out / "clarification_answers.md").write_text(
            "# Requirement Clarification Answers\n\n"
            "Goal: Reduce playback recovery failures.\n"
            "Flow: Operator seeks a playing device video; the system sends one control request, rebuilds the player after success, and shows an error after failure.\n"
            "Entrypoint: Device playback dialog seek action.\n"
            "AC: Playback resumes within two seconds after a successful seek.\n",
            encoding="utf-8",
        )
        second = auto_runner.run(requirement, doc_id="REQ-CLARIFIED", out=out)
        clarified = out / "requirement.clarified.txt"
        assert clarified.exists()
        assert "Reduce playback recovery failures" in clarified.read_text(encoding="utf-8")
        spec_step = next(step for step in second["steps"] if step["name"] == "spec")
        assert str(clarified.resolve()) in spec_step["command"]
        assert "requirement.clarified.txt" in second["generated_artifacts"]


def test_auto_runner_regenerates_transitive_artifacts_when_requirement_changes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        requirement = root / "requirement.md"
        original = (ROOT / "examples/synthetic-e2e-case/requirement.md").read_text(encoding="utf-8")
        requirement.write_text(original, encoding="utf-8")
        out = root / "artifacts"
        auto_runner.run(requirement, doc_id="REQ-LINEAGE", out=out, profile="small_feature")
        before = json.loads((out / "technical_design.json").read_text(encoding="utf-8"))["input_digests"]["spec.json"]
        requirement.write_text(original.replace("order id and status", "order id, status, and owner"), encoding="utf-8")
        second = auto_runner.run(requirement, doc_id="REQ-LINEAGE", out=out, profile="small_feature")
        after = json.loads((out / "technical_design.json").read_text(encoding="utf-8"))["input_digests"]["spec.json"]
        assert before != after
        assert {"requirement_ingestion.json", "spec.json", "technical_design.json", "architecture_design.json"}.issubset(set(second["generated_artifacts"]))
        assert second["workflow_metrics"]["invalidated_artifact_count"] > 0


def test_auto_runner_force_regenerates_existing_artifacts() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "artifacts"
        auto_runner.run(ROOT / "examples/synthetic-e2e-case/requirement.md", doc_id="REQ-AUTO-3", out=out)
        forced = auto_runner.run(ROOT / "examples/synthetic-e2e-case/requirement.md", doc_id="REQ-AUTO-3", out=out, force=True)
        assert "spec.json" in forced["generated_artifacts"]
        assert "spec.json" not in forced["skipped_artifacts"]


def test_auto_runner_project_understanding_optional() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "artifacts"
        result = auto_runner.run(
            input_path=ROOT / "examples/synthetic-e2e-case/requirement.md",
            doc_id="REQ-AUTO-4",
            repo=ROOT / "examples/synthetic-repos/basic-web-service",
            project="basic-web-service",
            out=out,
        )
        assert (out / "project_understanding/baseline_quality.json").exists()
        assert (out / "project_understanding/evidence_bundle.json").exists()
        assert result["decision"] == "block"
        assert not (out / "technical_design.json").exists()
        assert any(step["name"] == "project_understanding" for step in result["steps"])


def test_auto_runner_explicit_profile_selects_required_gates() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "artifacts"
        result = auto_runner.run(
            input_path=ROOT / "examples/synthetic-e2e-case/requirement.md",
            doc_id="REQ-AUTO-PROFILE",
            out=out,
            profile="frontend_change",
        )
        assert result["workflow_profile"].get("base_profile", result["workflow_profile"]["name"]) == "frontend_change"
        assert "frontend-acceptance-runner" not in result["required_gates"]
        assert "test-evidence-gate" not in result["required_gates"]
        assert (out / "frontend_implementation_plan.json").exists()
        assert not (out / "frontend_acceptance.json").exists()
        assert not (out / "test_evidence_gate.json").exists()


def test_auto_runner_infers_frontend_profile_from_requirement() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        req = root / "requirement.md"
        req.write_text(
            "User needs a new page button. AC: UI button is visible on the orders page.",
            encoding="utf-8",
        )
        out = root / "artifacts"
        result = auto_runner.run(req, doc_id="REQ-AUTO-FE", out=out)
        assert result["workflow_profile"]["name"] == "frontend_change"
        assert result["profile_selection_reason"]["matched_impact"] == "ui"


def test_auto_runner_routes_one_line_request_to_small_feature() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        req = root / "one-line.md"
        req.write_text("Change the checkout confirmation copy to Order received.", encoding="utf-8")
        out = root / "artifacts"
        result = auto_runner.run(req, doc_id="REQ-AUTO-ONE", out=out)
        assert result["workflow_profile"]["name"] == "small_feature"
        assert result["profile_selection_reason"]["mode"] == "lane"
        assert result["profile_selection_reason"]["lane"] == "small_change"


def test_auto_runner_routes_bugfix_to_bugfix_profile() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        req = root / "bugfix.md"
        req.write_text(
            """
            Bug: order detail page shows the wrong status after refund.
            Rule: preserve existing refund workflow.
            AC: refunded orders show Refund complete.
            """,
            encoding="utf-8",
        )
        out = root / "artifacts"
        result = auto_runner.run(req, doc_id="REQ-AUTO-BUG", out=out)
        assert result["workflow_profile"].get("base_profile", result["workflow_profile"]["name"]) == "bugfix"
        assert result["profile_selection_reason"]["mode"] == "lane"
        assert "git-worktree-governor" in result["required_gates"]
        assert result["workflow_strictness"]["tier"] in {"light", "standard"}


def test_auto_runner_elevates_bugfix_when_permission_impact_exists() -> None:
    spec = {
        "lane": "bugfix",
        "impact_surface": [
            {"area": "permission"},
            {"area": "api"},
        ],
    }
    profile, reason = auto_runner.select_workflow_profile_with_reason(spec)
    strictness = auto_runner.workflow_strictness(spec, profile, "high")
    assert profile["base_profile"] == "bugfix"
    assert "data_migration" in profile["overlay_profiles"]
    assert "cross_repo_api" in profile["overlay_profiles"]
    assert "data-security-governor" in profile["required_skills"]
    assert strictness["tier"] == "regulated"
    assert strictness["elevated"] is True
    assert "permission" in strictness["elevation_impacts"]
    assert reason["composition_mode"] == "merged"


def test_auto_runner_elevates_long_prd_with_permission_rules() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        req = root / "long-prd.md"
        lines = [
            "Goal: improve order export operations.",
            "Req: Admin exports filtered orders.",
            "Req: Operator reviews export history.",
            "Rule: only admin can export filtered results.",
            "AC: exported file contains order id and status.",
            "AC: non-admin cannot export filtered results.",
        ]
        lines.extend(f"Detail {idx}: keep existing behavior compatible." for idx in range(1, 30))
        req.write_text("\n".join(lines), encoding="utf-8")
        out = root / "artifacts"
        result = auto_runner.run(req, doc_id="REQ-AUTO-LONG", out=out)
        assert result["workflow_profile"].get("base_profile", result["workflow_profile"]["name"]) == "data_migration"
        assert result["profile_selection_reason"]["lane"] == "large_prd"
        assert result["workflow_strictness"]["tier"] == "regulated"
        assert "permission" in result["workflow_strictness"]["elevation_impacts"]
        assert "architecture-design-governor" in result["required_gates"]


def test_auto_runner_routes_complex_multi_impact_to_high_risk_profile() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        req = root / "complex.md"
        req.write_text(
            """
            Business purpose: reduce manual payment failure investigation time.
            Flow: admin opens the payment failure page and clicks export; the system calls the payment failure API, reads migrated retry-count data, generates the file, and returns it for review.
            Entry: payment failure admin page.
            Req: Add an API endpoint and admin page for payment export failures.
            Req: Add a database migration for retry count.
            Rule: only admin role can access payment failure data.
            Rule: export must stay within the latency budget.
            AC: API returns payment failure rows.
            AC: dashboard page shows retry count.
            AC: non-admin cannot view payment failure data.
            AC: export latency remains within the performance budget.
            Risk: payment data may contain sensitive fields.
            """,
            encoding="utf-8",
        )
        out = root / "artifacts"
        result = auto_runner.run(req, doc_id="REQ-AUTO-COMPLEX", out=out)
        assert result["workflow_profile"]["base_profile"] == "data_migration"
        assert result["workflow_profile"]["composition_mode"] == "merged"
        assert "frontend_change" in result["workflow_profile"]["overlay_profiles"]
        assert "cross_repo_api" in result["workflow_profile"]["overlay_profiles"]
        assert result["profile_selection_reason"]["matched_impact"] == "data"
        assert result["profile_selection_reason"]["composition_mode"] == "merged"
        assert "data-security-governor" in result["required_gates"]
        assert "performance-governor" in result["required_gates"]
        assert "traceability-governor" in result["required_gates"]
        assert (out / "frontend_implementation_plan.json").exists()
        assert not (out / "frontend_acceptance.json").exists()


def test_auto_runner_merges_repo_context_with_frontend_profile() -> None:
    spec = {
        "lane": "standard_requirement",
        "impact_surface": [
            {"area": "ui"},
            {"area": "api"},
        ],
    }
    profile, reason = auto_runner.select_workflow_profile_with_reason(spec, has_repo=True)
    assert profile["composition_mode"] == "merged"
    assert profile["base_profile"] == "cross_repo_api"
    assert "frontend_change" in profile["overlay_profiles"]
    assert "project-understanding-runner" in profile["required_skills"]
    assert "frontend_implementation_plan.json" in profile["expected_artifacts"]
    assert "frontend_acceptance.json" not in profile["expected_artifacts"]
    assert reason["composition_mode"] == "merged"


def test_auto_runner_does_not_route_repo_context_alone_to_cross_repo_profile() -> None:
    spec = {
        "lane": "standard_requirement",
        "impact_surface": [
            {"area": "ui"},
        ],
    }
    profile, reason = auto_runner.select_workflow_profile_with_reason(spec, has_repo=True)
    assert profile["name"] == "frontend_change"
    assert "cross_repo_api" not in profile.get("overlay_profiles", [])
    assert "cross_repo_readiness.json" not in profile["expected_artifacts"]
    assert reason["mode"] == "impact_surface"


def test_cross_repo_profile_artifact_step_generates_graph_artifacts() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        (out / "spec.json").write_text(
            json.dumps({"doc_id": "REQ-CROSS", "summary": "provider api consumed by frontend"}),
            encoding="utf-8",
        )
        (out / "delivery_plan.json").write_text(
            json.dumps(
                {
                    "doc_id": "REQ-CROSS",
                    "repo_tasks": [
                        {"repo": "provider", "role": "modify", "tasks": ["change api"]},
                        {"repo": "frontend", "role": "modify", "tasks": ["consume api"]},
                    ],
                    "cross_repo_order": ["provider", "frontend"],
                }
            ),
            encoding="utf-8",
        )
        profile = auto_runner.load_profile_registry()["cross_repo_api"]
        generated: list[str] = []
        skipped: list[str] = []
        steps: list[dict] = []
        assert auto_runner.run_registry_artifact_steps(profile, out, False, generated, skipped, steps) is True
        assert (out / "cross_repo_execution_graph.json").exists()
        assert (out / "cross_repo_readiness.json").exists()
        assert (out / "cross_repo_release_plan.json").exists()
        assert json.loads((out / "cross_repo_readiness.json").read_text(encoding="utf-8"))["decision"] == "ready"
        assert all(step.get("passed") for step in steps if not step.get("skipped"))


def test_cross_repo_planning_runs_before_delivery_plan_review() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        (out / "spec.json").write_text(
            json.dumps({"doc_id": "REQ-CROSS", "summary": "provider api consumed by frontend"}),
            encoding="utf-8",
        )
        (out / "delivery_plan.json").write_text(
            json.dumps(
                {
                    "doc_id": "REQ-CROSS",
                    "repo_tasks": [
                        {"repo": "provider", "role": "modify", "tasks": ["change api"]},
                        {"repo": "frontend", "role": "modify", "tasks": ["consume api"]},
                    ],
                    "cross_repo_order": ["provider", "frontend"],
                }
            ),
            encoding="utf-8",
        )
        profile = auto_runner.load_profile_registry()["cross_repo_api"]
        generated: list[str] = []
        skipped: list[str] = []
        steps: list[dict] = []
        auto_runner.run_pre_review_planning_steps(profile, out, out / "spec.json", out / "delivery_plan.json", False, generated, skipped, steps)
        assert steps[0]["name"] == "cross_repo_plan"
        assert (out / "cross_repo_readiness.json").exists()


def test_cross_repo_readiness_is_aggregated_by_final_design_review() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        req = root / "api.md"
        req.write_text("Business purpose: prevent consumer outages during contract evolution.\nFlow: consumer sends its existing request to the provider endpoint; the provider validates it, returns the compatible response, and the consumer completes its workflow unchanged.\nEntry: provider API endpoint.\nRepo: provider owns the endpoint.\nRepo: consumer uses the endpoint.\nDependency: consumer -> provider API.\nReq: Add API contract.\nAC: existing consumer remains compatible.", encoding="utf-8")
        out = root / "artifacts"
        result = auto_runner.run(req, doc_id="REQ-CROSS-REVIEW", out=out, profile="cross_repo_api")
        step_names = [item.get("name") for item in result["steps"]]
        assert step_names.index("delivery_plan_draft") < step_names.index("cross_repo_plan") < step_names.index("design_review")
        review = json.loads((out / "design_architecture_review.json").read_text(encoding="utf-8"))
        assert "cross_repo_readiness.json" in review["input_digests"]


def test_auto_runner_generates_specialty_design_before_technical_design() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        req = root / "frontend.md"
        req.write_text(
            "\n".join([
                "业务目的: 让管理员在报表页导出筛选结果。",
                "流程: 管理员打开报表页，点击导出按钮，系统生成文件。",
                "入口: 报表页导出按钮。",
                "Req: Admin exports filtered report rows from the dashboard page.",
                "AC: admin can export filtered rows.",
            ]),
            encoding="utf-8",
        )
        out = root / "artifacts"
        result = auto_runner.run(req, doc_id="REQ-FE-ORDER", title="Frontend export", out=out, profile="frontend_change", force=True)
        step_names = [step.get("name") for step in result["steps"]]
        assert step_names.index("domain_model_design") < step_names.index("architecture_framing") < step_names.index("technical_design")
        assert step_names.index("ui_ue_design") < step_names.index("technical_design")
        assert step_names.index("test_design") < step_names.index("design_review")
        assert step_names.index("delivery_plan") < step_names.index("initial_traceability") < step_names.index("delivery_plan_review")
        assert step_names.index("frontend_implementation_plan") > step_names.index("technical_design")
        assert result["steps"][step_names.index("initial_traceability")]["traceability_phase"] == "initial_design_plan"
        tech = json.loads((out / "technical_design.json").read_text(encoding="utf-8"))
        assert tech["architecture_framing_ref"] == "architecture_framing.json"
        assert (out / "ui_ue_design.json").exists()
        assert (out / "traceability_matrix.json").exists()
        assert (out / "frontend_implementation_plan.json").exists()


def test_workflow_strictness_classifies_light_standard_and_regulated() -> None:
    light = auto_runner.workflow_strictness({"lane": "bugfix", "impact_surface": []}, {"name": "bugfix"}, "high")
    assert light["tier"] == "light"
    controls = auto_runner.effective_workflow_controls(
        {
            "name": "bugfix",
            "expected_artifacts": ["spec.json", "technical_design.json", "architecture_design.json", "test_design.json"],
            "required_gate_artifacts": [{"artifact": "spec.json"}, {"artifact": "architecture_design.json"}, {"artifact": "test_design.json"}],
        },
        light,
    )
    assert "architecture_design.json" not in controls["expected_artifacts"]
    assert all(item["artifact"] != "architecture_design.json" for item in controls["required_gate_artifacts"])
    assert controls["gate_overrides"]
    standard = auto_runner.workflow_strictness({"lane": "small_change", "impact_surface": [{"area": "ui"}]}, {"name": "frontend_change"}, "medium")
    assert standard["tier"] == "standard"
    api_bugfix = auto_runner.workflow_strictness({"lane": "bugfix", "impact_surface": [{"area": "api"}]}, {"name": "bugfix+cross_repo_api"}, "high")
    assert api_bugfix["tier"] == "standard"
    assert api_bugfix["elevated"] is True
    mq_bugfix = auto_runner.workflow_strictness({"lane": "bugfix", "impact_surface": [{"area": "mq"}]}, {"name": "bugfix"}, "high")
    assert mq_bugfix["tier"] == "standard"
    assert mq_bugfix["elevated"] is True
    regulated = auto_runner.workflow_strictness({"lane": "standard_requirement", "impact_surface": [{"area": "data"}]}, {"name": "data_migration"}, "high")
    assert regulated["tier"] == "regulated"
    profile = {"name": "data_migration", "required_skills": ["release-evidence-binder"]}
    gaps = auto_runner.strictness_gate_gaps(profile, regulated)
    assert any("data-security-governor" in item["message"] for item in gaps)
    permission = auto_runner.workflow_strictness({"lane": "bugfix", "impact_surface": [{"area": "permission"}]}, {"name": "bugfix+data_migration"}, "high")
    gaps = auto_runner.strictness_gate_gaps({"name": "bugfix+data_migration", "required_skills": ["release-evidence-binder"]}, permission)
    assert any("data-security-governor" in item["message"] for item in gaps)


def test_auto_runner_release_profile_only_checks_release_artifacts() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        req = root / "release.md"
        req.write_text("Release readiness check.", encoding="utf-8")
        out = root / "artifacts"
        result = auto_runner.run(req, doc_id="REQ-AUTO-REL", out=out, profile="release_readiness")
        assert result["workflow_profile"]["name"] == "release_readiness"
        assert result["safety_boundary"] == "release_artifact_inspection_only"
        assert not (out / "spec.json").exists()
        assert (out / "post_implementation_traceability_matrix.json").exists()
        assert (out / "release_gate.json").exists()
        assert any(step["name"] == "post_implementation_traceability" for step in result["steps"])
        assert "spec" not in result["inspect_status"]["implementation_missing"]
        assert result["inspect_status"]["next_release_actions"]


def test_codex_eng_auto_cli_runs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "artifacts"
        proc = subprocess.run(
            [
                sys.executable,
                "scripts/codex_eng.py",
                "auto",
                "--input",
                "examples/synthetic-e2e-case/requirement.md",
                "--doc-id",
                "REQ-AUTO-CLI",
                "--out",
                str(out),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert proc.returncode == 2
        assert json.loads(proc.stdout)["decision"] == "block"
        assert (out / "auto_run_summary.json").exists()


def test_codex_eng_auto_human_output_runs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "artifacts"
        proc = subprocess.run(
            [
                sys.executable,
                "scripts/codex_eng.py",
                "auto",
                "--input",
                "examples/synthetic-e2e-case/requirement.md",
                "--doc-id",
                "REQ-AUTO-HUMAN",
                "--out",
                str(out),
                "--format",
                "human",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert proc.returncode == 2
        assert "Codex auto summary" in proc.stdout
        assert "decision: block" in proc.stdout
        assert "next_command" in proc.stdout
        assert (out / "auto_run_summary.json").exists()


def test_codex_eng_clarify_help_and_non_tty_fail_closed() -> None:
    help_proc = subprocess.run(
        [sys.executable, "scripts/codex_eng.py", "clarify", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert help_proc.returncode == 0
    assert "--artifact-dir" in help_proc.stdout
    proc = subprocess.run(
        [sys.executable, "scripts/codex_eng.py", "clarify", "--artifact-dir", "/tmp/missing-clarification"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 2
    assert "requires a TTY" in proc.stderr


def run_all() -> None:
    test_auto_runner_generates_core_artifacts()
    test_auto_runner_accepts_ready_docs_repo()
    test_auto_runner_is_idempotent_without_force()
    test_auto_runner_force_regenerates_existing_artifacts()
    test_auto_runner_project_understanding_optional()
    test_auto_runner_explicit_profile_selects_required_gates()
    test_auto_runner_infers_frontend_profile_from_requirement()
    test_auto_runner_routes_one_line_request_to_small_feature()
    test_auto_runner_routes_bugfix_to_bugfix_profile()
    test_auto_runner_elevates_bugfix_when_permission_impact_exists()
    test_auto_runner_elevates_long_prd_with_permission_rules()
    test_auto_runner_routes_complex_multi_impact_to_high_risk_profile()
    test_workflow_strictness_classifies_light_standard_and_regulated()
    test_auto_runner_release_profile_only_checks_release_artifacts()
    test_codex_eng_auto_cli_runs()
    test_codex_eng_auto_human_output_runs()


if __name__ == "__main__":
    run_all()
    print("PASS auto_runner tests")
