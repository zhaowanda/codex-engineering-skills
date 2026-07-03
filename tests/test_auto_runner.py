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
        assert "strictness_gate_gaps" in result
        assert result["docs_readiness"]["decision"] == "block"
        assert result["next_stage"]
        assert result["can_implement"] is False


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
        assert (docs_root / "indexes/REQ-AUTO-DOCS.manifest.json").exists()
        spec_doc = (docs_root / "human/specs/REQ-AUTO-DOCS.md").read_text(encoding="utf-8")
        design_doc = (docs_root / "human/designs/REQ-AUTO-DOCS.md").read_text(encoding="utf-8")
        test_doc = (docs_root / "human/tests/REQ-AUTO-DOCS.md").read_text(encoding="utf-8")
        release_doc = (docs_root / "human/releases/REQ-AUTO-DOCS.md").read_text(encoding="utf-8")
        assert "## Executive Summary" in spec_doc
        assert "## Background And Goals" in spec_doc
        assert "## Scope" in spec_doc
        assert "## Requirement Clarification" in spec_doc
        assert "### Clarification Log" in spec_doc
        assert "### Clarification Status" in spec_doc
        assert "### Confirmed Understanding" in spec_doc
        assert "### Pending Questions" in spec_doc
        assert "### Working Assumptions" in spec_doc
        assert "Design can proceed:" in spec_doc
        assert "## Acceptance Criteria" in spec_doc
        assert "## Requirement Traceability Diagram" in spec_doc
        assert "`AC-1` exported file contains order id and status." in spec_doc
        assert "```mermaid" in spec_doc + design_doc + release_doc
        assert "## Current State, Problem, And Goals" in design_doc
        assert "## Decision Records" in design_doc
        assert "## Process Flow" in design_doc
        assert "## Risks And Open Gates" in design_doc
        assert "## Test Strategy Summary" in design_doc
        assert "### Test Cases" not in design_doc
        assert "`TC-1`" not in design_doc
        assert "Acceptance:" not in design_doc
        assert "## Test Cases" in test_doc
        assert "`TC-1`" in test_doc
        assert "Acceptance:" in test_doc
        assert "## Regression, Integration, Frontend, And Permission Scope" in test_doc
        assert "## Missing Readiness" in release_doc
        assert "## Execution Steps" in release_doc
        assert "## Release And Rollback Sequence" in release_doc
        assert "### Test Cases" in release_doc
        assert "### Before Implementation" in release_doc
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
        assert "## 三、方案对比与选择" in design_doc
        assert "## 四、决策记录" in design_doc
        assert "## 五、业务流程" in design_doc
        assert "## 六、模块与接口设计" in design_doc
        assert "## 九、交付执行计划" in design_doc
        assert "## 十、需求追踪关系" in design_doc
        assert "## 十一、测试策略摘要" in design_doc
        assert "### 测试用例" not in design_doc
        assert "`TC-1`" not in design_doc
        assert "## 四、测试用例" in test_doc
        assert "`TC-1`" in test_doc
        assert "关联验收" in test_doc
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
        assert "requirement.normalized.txt" in second["skipped_artifacts"]
        assert "spec.json" in second["skipped_artifacts"]


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
        technical = (out / "technical_design.json").read_text(encoding="utf-8")
        architecture = (out / "architecture_design.json").read_text(encoding="utf-8")
        plan = (out / "delivery_plan.json").read_text(encoding="utf-8")
        assert "basic-web-service" in technical
        assert "basic-web-service" in architecture
        assert "examples/synthetic-repos/basic-web-service" in plan
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
        assert "frontend-acceptance-runner" in result["required_gates"]
        assert "test-evidence-gate" in result["required_gates"]
        assert (out / "frontend_acceptance.json").exists()
        assert (out / "test_evidence_gate.json").exists()
        assert any(step["name"] == "frontend_acceptance_template" for step in result["steps"])
        assert any(gap["artifact"] == "frontend_acceptance.json" for gap in result["profile_gate_gaps"])


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


def test_auto_runner_routes_long_prd_to_small_feature_full_design_path() -> None:
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
        assert result["workflow_profile"].get("base_profile", result["workflow_profile"]["name"]) == "small_feature"
        assert result["profile_selection_reason"]["lane"] == "large_prd"
        assert "architecture-design-governor" in result["required_gates"]


def test_auto_runner_routes_complex_multi_impact_to_high_risk_profile() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        req = root / "complex.md"
        req.write_text(
            """
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
        assert "frontend-acceptance-runner" in result["required_gates"]
        assert "traceability-governor" in result["required_gates"]
        assert (out / "frontend_acceptance.json").exists()
        assert any(gap["artifact"] == "frontend_acceptance.json" for gap in result["profile_gate_gaps"])


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
    assert "frontend-acceptance-runner" in profile["required_skills"]
    assert "project-understanding-runner" in profile["required_skills"]
    assert "frontend_acceptance.json" in profile["expected_artifacts"]
    assert reason["composition_mode"] == "merged"


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
    regulated = auto_runner.workflow_strictness({"lane": "standard_requirement", "impact_surface": [{"area": "data"}]}, {"name": "data_migration"}, "high")
    assert regulated["tier"] == "regulated"
    profile = {"name": "data_migration", "required_skills": ["release-evidence-binder"]}
    gaps = auto_runner.strictness_gate_gaps(profile, regulated)
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
        assert (out / "release_gate.json").exists()
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
        assert proc.returncode == 0
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
        assert proc.returncode == 0
        assert "Codex auto summary" in proc.stdout
        assert "next_command" in proc.stdout
        assert (out / "auto_run_summary.json").exists()


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
    test_auto_runner_routes_long_prd_to_small_feature_full_design_path()
    test_auto_runner_routes_complex_multi_impact_to_high_risk_profile()
    test_workflow_strictness_classifies_light_standard_and_regulated()
    test_auto_runner_release_profile_only_checks_release_artifacts()
    test_codex_eng_auto_cli_runs()
    test_codex_eng_auto_human_output_runs()


if __name__ == "__main__":
    run_all()
    print("PASS auto_runner tests")
