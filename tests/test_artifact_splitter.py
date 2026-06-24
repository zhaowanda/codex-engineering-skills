from __future__ import annotations

import importlib.util
import json
import tempfile
from argparse import Namespace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/templates/artifact-splitter/scripts/split_artifacts.py"
split_spec = importlib.util.spec_from_file_location("split_artifacts", SCRIPT)
split_artifacts = importlib.util.module_from_spec(split_spec)
assert split_spec.loader
split_spec.loader.exec_module(split_artifacts)


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_split_generates_human_summary_without_absolute_paths() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        technical = root / "technical_design.json"
        architecture = root / "architecture_design.json"
        review = root / "design_review.json"
        plan = root / "delivery_plan.json"
        write_json(technical, {"requirement_trace": [{"requirement_id": "REQ-1", "summary": "show checkout discount"}], "selected_solution": {"selected_option_id": "T1", "selection_reason": "safe", "tradeoffs": ["web only"]}})
        write_json(architecture, {"selected_architecture": {"selected_option_id": "A1", "selection_reason": "low risk", "tradeoffs": ["no API change"]}})
        write_json(review, {"decision": "pass", "score": 96, "level": "expert_ready", "severity_counts": {"blocker": 0, "high": 0, "medium": 0, "low": 0}, "readiness_gate": {"implementation_allowed": True}})
        write_json(plan, {"repo_tasks": [{"repo": "web-app", "role": "modify", "responsibility": "render", "allowed_files": ["src/checkout"]}], "release_plan": {"release_order": ["web-app"], "release_gate": "tests pass"}, "rollback_plan": {"rollback_order": ["web-app"]}, "open_gates": []})
        out_dir = root / "human"
        manifest = split_artifacts.split(Namespace(
            doc_id="REQ-1",
            title="Checkout discount",
            technical_design=str(technical),
            architecture_design=str(architecture),
            design_review=str(review),
            delivery_plan=str(plan),
            out_dir=str(out_dir),
            include_local_paths=False,
        ))
        summary = (out_dir / "human_summary.md").read_text(encoding="utf-8")
        assert manifest["schema"] == "codex-artifact-split-manifest-v1"
        assert "technical_design.json" in summary
        assert str(root) not in summary
        assert "web-app [modify]" in summary


def test_split_can_include_local_paths_when_requested() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        plan = root / "delivery_plan.json"
        write_json(plan, {"repo_tasks": []})
        out_dir = root / "human"
        split_artifacts.split(Namespace(
            doc_id="REQ-1",
            title="Title",
            technical_design="",
            architecture_design="",
            design_review="",
            delivery_plan=str(plan),
            out_dir=str(out_dir),
            include_local_paths=True,
        ))
        summary = (out_dir / "human_summary.md").read_text(encoding="utf-8")
        assert str(plan.resolve()) in summary


def run_all() -> None:
    test_split_generates_human_summary_without_absolute_paths()
    test_split_can_include_local_paths_when_requested()


if __name__ == "__main__":
    run_all()
    print("PASS artifact_splitter tests")
