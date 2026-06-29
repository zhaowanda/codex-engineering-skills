from __future__ import annotations

import importlib.util
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


def test_auto_runner_generates_core_artifacts() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "artifacts"
        result = auto_runner.run(
            input_path=ROOT / "examples/synthetic-e2e-case/requirement.md",
            doc_id="REQ-AUTO-1",
            title="Order export",
            out=out,
        )
        assert result["schema"] == "codex-auto-runner-summary-v1"
        assert (out / "requirement.normalized.txt").exists()
        assert (out / "spec.json").exists()
        assert (out / "technical_design.json").exists()
        assert (out / "architecture_design.json").exists()
        assert (out / "test_design.json").exists()
        assert (out / "delivery_plan.json").exists()
        assert (out / "auto_run_summary.json").exists()
        assert result["next_stage"]
        assert result["can_implement"] is False


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


def run_all() -> None:
    test_auto_runner_generates_core_artifacts()
    test_auto_runner_is_idempotent_without_force()
    test_auto_runner_force_regenerates_existing_artifacts()
    test_auto_runner_project_understanding_optional()
    test_codex_eng_auto_cli_runs()


if __name__ == "__main__":
    run_all()
    print("PASS auto_runner tests")
