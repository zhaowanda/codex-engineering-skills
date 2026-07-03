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
        "questions": [{"id": "Q-1", "required": True, "status": "closed", "answer": "id,status"}],
    }
    result = question_governor.validate_questions(data)
    assert result["decision"] == "pass"


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
    test_delivery_case_capture_summarizes_artifacts()
    test_delivery_case_capture_can_emit_anonymized_replay_skeleton()


if __name__ == "__main__":
    run_all()
    print("PASS requirement_and_case_governors tests")
