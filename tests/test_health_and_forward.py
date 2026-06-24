from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


skill_health = load_module("skill_health", ROOT / "skills/core/skill-health/scripts/skill_health.py")
overlay_health = load_module("overlay_health", ROOT / "skills/core/overlay-health/scripts/overlay_health.py")
human_doc_review = load_module("human_doc_review", ROOT / "skills/core/human-doc-reviewer/scripts/human_doc_review.py")
forward_test = load_module("forward_test", ROOT / "skills/core/forward-test-runner/scripts/forward_test.py")


def test_skill_health_runs_on_repo() -> None:
    result = skill_health.check(ROOT)
    assert result["schema"] == "codex-skill-health-v1"
    assert result["decision"] in {"pass", "warn"}
    assert result["skill_count"] > 10
    assert not [item for item in result["warnings"] if item["message"] == "skill is not listed in README"]


def test_overlay_health_blocks_missing_registry() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = overlay_health.check(Path(tmp))
        assert result["decision"] == "block"
        assert result["blockers"]


def test_human_doc_review_detects_local_path() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "doc.md"
        local_path = "/" + "Users/example/private"
        doc.write_text(f"Scope\nDecision\nOptions\nRisk\nEvidence\nRollback\n{local_path}\n", encoding="utf-8")
        result = human_doc_review.review(doc)
        assert result["decision"] == "block"
        assert any(item["source"] == "local_path" for item in result["blockers"])


def test_human_doc_review_warns_thin_doc() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "doc.md"
        doc.write_text("short\n", encoding="utf-8")
        result = human_doc_review.review(doc)
        assert result["decision"] == "warn"
        assert result["warnings"]


def test_forward_test_runner_passes_synthetic_case() -> None:
    result = forward_test.run(ROOT)
    assert result["schema"] == "codex-forward-test-run-v1"
    assert result["decision"] == "pass"
    assert result["cases"][0]["passed"] is True


def run_all() -> None:
    test_skill_health_runs_on_repo()
    test_overlay_health_blocks_missing_registry()
    test_human_doc_review_detects_local_path()
    test_human_doc_review_warns_thin_doc()
    test_forward_test_runner_passes_synthetic_case()


if __name__ == "__main__":
    run_all()
    print("PASS health_and_forward tests")
