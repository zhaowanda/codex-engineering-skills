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


diff_impact = load_module("diff_impact", ROOT / "skills/core/diff-impact-analyzer/scripts/diff_impact.py")
implementation_complete = load_module("implementation_complete", ROOT / "skills/core/implementation-completion-gate/scripts/implementation_complete.py")
post_change_sync = load_module("post_change_sync", ROOT / "skills/core/post-change-skill-sync/scripts/sync_after_change.py")
evidence_collect = load_module("evidence_collect", ROOT / "skills/core/evidence-auto-collector/scripts/evidence_collect.py")
synthetic_e2e = load_module("synthetic_e2e", ROOT / "skills/templates/synthetic-e2e-runner/scripts/run_synthetic_e2e.py")


DIFF = """
diff --git a/src/api/orders.py b/src/api/orders.py
--- a/src/api/orders.py
+++ b/src/api/orders.py
@@
+def export_orders():
+    sql = "select * from orders"
+    if not has_permission(user):
+        raise Exception("denied")
diff --git a/src/page/Orders.vue b/src/page/Orders.vue
--- a/src/page/Orders.vue
+++ b/src/page/Orders.vue
@@
+<button>Export</button>
"""


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_diff_impact_detects_core_areas() -> None:
    result = diff_impact.analyze(DIFF)
    assert result["schema"] == "codex-diff-impact-v1"
    assert {"api", "database", "permission", "frontend"}.issubset(set(result["impact_areas"]))
    assert "frontend_acceptance" in result["evidence_required"]


def test_implementation_completion_blocks_out_of_scope() -> None:
    plan = {"repo_tasks": [{"allowed_files": ["src/service"]}]}
    result = implementation_complete.evaluate(DIFF, plan, "implemented export")
    assert result["decision"] == "block"
    assert any(item["source"] == "scope" for item in result["blockers"])


def test_implementation_completion_passes_with_allowed_scope() -> None:
    plan = {"repo_tasks": [{"allowed_files": ["src/api", "src/page"]}]}
    result = implementation_complete.evaluate(DIFF, plan, "implemented export")
    assert result["decision"] == "pass"
    assert result["changed_files"]
    assert {item["surface"] for item in result["evidence_followups"]} >= {
        "api_contract",
        "data_model",
        "permission_data_scope",
        "frontend_acceptance",
        "observability",
    }
    assert any(item["source"] == "evidence_followup" for item in result["warnings"])


def test_implementation_completion_blocks_unready_delivery_plan_gate() -> None:
    gate = {"design_allowed": False, "implementation_allowed": False, "decision": "needs_clarification"}
    plan = {
        "decision": "needs_completion",
        "source_design_gate": gate,
        "open_gates": ["requirements_understanding_gate: implementation is blocked"],
        "repo_tasks": [{"allowed_files": ["src/api", "src/page"]}],
    }
    result = implementation_complete.evaluate(DIFF, plan, "implemented export")
    assert result["decision"] == "block"
    sources = {item["source"] for item in result["blockers"]}
    assert {"delivery_plan", "requirements_understanding_gate"}.issubset(sources)


def test_implementation_completion_tracks_transaction_cache_and_mq_followups() -> None:
    diff = """
diff --git a/src/service/RenewalService.java b/src/service/RenewalService.java
--- a/src/service/RenewalService.java
+++ b/src/service/RenewalService.java
@@
+public void renew(Order order) {
+    renewalMapper.insert(order);
+    accountRepository.updateBalance(order.getAccountId());
+    redisTemplate.opsForValue().set("renewal:" + order.getId(), order);
+    kafkaTemplate.send("renewal-topic", order);
+}
"""
    plan = {"repo_tasks": [{"allowed_files": ["src/service"]}]}
    result = implementation_complete.evaluate(diff, plan, "implemented renewal flow")
    surfaces = {item["surface"] for item in result["evidence_followups"]}
    assert {"data_model", "mq_interaction", "cache_consistency", "transaction_idempotency", "observability"}.issubset(surfaces)
    tx = next(item for item in result["evidence_followups"] if item["surface"] == "transaction_idempotency")
    assert any("rollback" in evidence for evidence in tx["evidence"])


def test_evidence_collector_detects_missing_and_failed_logs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        log = root / "test.log"
        log.write_text("FAILED test_export\n", encoding="utf-8")
        impact = {"impact_areas": ["frontend"], "evidence_required": ["frontend_acceptance", "permission_negative_test"]}
        result = evidence_collect.collect(impact, [log], root)
        assert result["schema"] == "codex-evidence-gap-summary-v1"
        assert result["decision"] == "block"
        assert result["missing_evidence"]
        assert result["failed_logs"]


def test_evidence_collector_maps_implementation_followups_to_required_artifacts() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_json(root / "implementation_completion_gate.json", {
            "decision": "pass",
            "evidence_followups": [
                {"surface": "mq_interaction", "required_by": "test-evidence-gate"},
                {"surface": "frontend_acceptance", "required_by": "frontend-acceptance-runner"},
                {"surface": "configuration", "required_by": "configuration-governor"},
            ],
        })
        result = evidence_collect.collect({"impact_areas": [], "evidence_required": []}, [], root)
        assert result["decision"] == "block"
        assert "mq_interaction_evidence" in result["required_evidence"]
        assert "frontend_acceptance:frontend_acceptance.json" in result["missing_evidence"]
        assert "configuration_readiness:configuration_readiness.json" in result["missing_evidence"]


def test_evidence_collector_passes_when_followup_artifacts_exist() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_json(root / "implementation_completion_gate.json", {
            "decision": "pass",
            "evidence_followups": [
                {"surface": "transaction_idempotency", "required_by": "test-evidence-gate"},
                {"surface": "frontend_acceptance", "required_by": "frontend-acceptance-runner"},
            ],
        })
        write_json(root / "test_execution_evidence.json", {"decision": "pass"})
        write_json(root / "frontend_acceptance.json", {"decision": "pass", "pass": True})
        result = evidence_collect.collect({"impact_areas": [], "evidence_required": []}, [], root)
        assert result["decision"] == "pass"
        assert not result["missing_evidence"]
        assert "transaction_idempotency_evidence:test_execution_evidence.json" in result["found_evidence"]


def test_post_change_sync_generates_report_from_git_changes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo = root / "repo"
        repo.mkdir()
        subprocess = __import__("subprocess")
        subprocess.run(["git", "init"], cwd=repo, text=True, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, text=True, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, text=True, capture_output=True, check=True)
        (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=repo, text=True, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, text=True, capture_output=True, check=True)
        (repo / "src/api").mkdir(parents=True)
        (repo / "src/api/orders.py").write_text("def export_orders():\n    return []\n", encoding="utf-8")
        artifact_dir = root / "artifacts"
        result = post_change_sync.generate(repo, artifact_dir, doc_id="REQ-1")
        assert result["schema"] == "codex-post-change-implementation-report-v1"
        assert result["decision"] == "block"
        assert "src/api/orders.py" in result["changed_files"]
        assert result["baseline_update_candidates"]
        assert result["project_skill_sync_candidates"]
        assert result["project_skill_index_requirements"]["status"] == "missing_evidence"
        assert (artifact_dir / "post_change_implementation_report.json").exists()
        assert post_change_sync.validate(result)["decision"] == "block"
        write_json(
            artifact_dir / "project_skill_index_sync.json",
            {
                "schema": "codex-project-skill-index-sync-v1",
                "decision": "pass",
                "updated_index_paths": ["company/demo/references/code-index.md"],
            },
        )
        satisfied = post_change_sync.generate(repo, artifact_dir, doc_id="REQ-1")
        assert satisfied["decision"] in {"pass", "warn"}
        assert satisfied["project_skill_index_requirements"]["status"] == "satisfied"
        assert post_change_sync.validate(satisfied)["decision"] == "pass"


def test_post_change_sync_allows_explicit_project_skill_index_waiver() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo = root / "repo"
        repo.mkdir()
        subprocess = __import__("subprocess")
        subprocess.run(["git", "init"], cwd=repo, text=True, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, text=True, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, text=True, capture_output=True, check=True)
        (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=repo, text=True, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, text=True, capture_output=True, check=True)
        (repo / "src").mkdir()
        (repo / "src/service.py").write_text("def run():\n    return True\n", encoding="utf-8")
        artifact_dir = root / "artifacts"
        write_json(
            artifact_dir / "project_skill_index_sync.json",
            {
                "schema": "codex-project-skill-index-sync-v1",
                "decision": "waived",
                "waiver_reason": "touches experimental code that is not promoted to the project skill index",
            },
        )
        result = post_change_sync.generate(repo, artifact_dir, doc_id="REQ-1")
        assert result["project_skill_index_requirements"]["status"] == "waived"
        assert post_change_sync.validate(result)["decision"] == "pass"


def test_post_change_sync_blocks_required_docs_when_unbound() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo = root / "repo"
        repo.mkdir()
        subprocess = __import__("subprocess")
        subprocess.run(["git", "init"], cwd=repo, text=True, capture_output=True, check=True)
        artifact_dir = root / "artifacts"
        result = post_change_sync.generate(repo, artifact_dir, require_docs=True)
        assert result["decision"] == "block"
        assert any(item["source"] in {"docs_root", "doc_id"} for item in result["blockers"])


def test_synthetic_e2e_runner_completes_core_flow() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = synthetic_e2e.run(Path(tmp))
        assert result["schema"] == "codex-synthetic-e2e-run-v1"
        assert result["decision"] == "pass"
        assert {item["case"] for item in result["cases"]} == {
            "blocked_case",
            "happy_path_case",
            "frontend_happy_path",
            "data_migration_blocked_path",
            "release_readiness_blocked_path",
            "release_readiness_happy_path",
            "release_followup_chain_path",
        }
        assert all(item["passed"] for item in result["cases"])
        assert (Path(tmp) / "blocked_case/spec.json").exists()
        assert (Path(tmp) / "happy_path_case/auto_run_summary.json").exists()
        assert (Path(tmp) / "synthetic_e2e_run.json").exists() is False


def run_all() -> None:
    test_diff_impact_detects_core_areas()
    test_implementation_completion_blocks_out_of_scope()
    test_implementation_completion_passes_with_allowed_scope()
    test_implementation_completion_blocks_unready_delivery_plan_gate()
    test_evidence_collector_detects_missing_and_failed_logs()
    test_evidence_collector_maps_implementation_followups_to_required_artifacts()
    test_evidence_collector_passes_when_followup_artifacts_exist()
    test_post_change_sync_generates_report_from_git_changes()
    test_post_change_sync_allows_explicit_project_skill_index_waiver()
    test_post_change_sync_blocks_required_docs_when_unbound()
    test_synthetic_e2e_runner_completes_core_flow()


if __name__ == "__main__":
    run_all()
    print("PASS automation_and_evidence tests")
