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
        }
        assert all(item["passed"] for item in result["cases"])
        assert (Path(tmp) / "blocked_case/spec.json").exists()
        assert (Path(tmp) / "happy_path_case/auto_run_summary.json").exists()
        assert (Path(tmp) / "synthetic_e2e_run.json").exists() is False


def run_all() -> None:
    test_diff_impact_detects_core_areas()
    test_implementation_completion_blocks_out_of_scope()
    test_implementation_completion_passes_with_allowed_scope()
    test_evidence_collector_detects_missing_and_failed_logs()
    test_synthetic_e2e_runner_completes_core_flow()


if __name__ == "__main__":
    run_all()
    print("PASS automation_and_evidence tests")
