from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills/core/frontend-acceptance-runner/scripts/frontend_acceptance.py"
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("frontend_acceptance", SCRIPT)
frontend_acceptance = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(frontend_acceptance)


def evidence_template(page_type: str, url: str) -> dict:
    evidence = frontend_acceptance.template(page_type, url)
    evidence["acceptance_refs"] = ["AC-1"]
    return evidence


def test_template_contains_page_specific_fields() -> None:
    result = frontend_acceptance.template("form", "http://localhost:3000/orders/new")
    assert result["schema"] == "codex-frontend-acceptance-v1"
    assert result["page_type"] == "form"
    assert "form_checks" in result
    assert "console_errors" in result
    assert result["browser_evidence"]["tested_route"] == "http://localhost:3000/orders/new"


def test_validate_passes_list_evidence_with_clean_browser_state() -> None:
    evidence = evidence_template("list", "http://localhost:3000/orders")
    evidence.update(
        {
            "pass": True,
            "page_load": {"loaded": True, "final_url": "http://localhost:3000/orders", "title": "Orders"},
            "dom_evidence": [{"selector": "table", "text": "Order ID"}],
            "network_requests": [{"url": "/api/orders", "status": 200}],
            "failed_requests": [],
            "console_errors": [],
        }
    )
    evidence["list_checks"]["columns_checked"] = ["Order ID", "Status"]
    evidence["list_checks"]["filters_checked"] = ["Status"]
    result = frontend_acceptance.validate_evidence(evidence)
    assert result["decision"] == "pass"
    assert result["pass"] is True


def test_validate_blocks_console_and_failed_requests() -> None:
    evidence = evidence_template("detail", "http://localhost:3000/orders/1")
    evidence.update(
        {
            "page_load": {"loaded": True},
            "screenshot_evidence": [{"path": "artifacts/order-detail.png"}],
            "console_errors": ["TypeError"],
            "failed_requests": [{"url": "/api/orders/1", "status": 500}],
        }
    )
    result = frontend_acceptance.validate_evidence(evidence)
    assert result["decision"] == "block"
    messages = " ".join(item["message"] for item in result["blockers"])
    assert "console errors" in messages
    assert "failed network requests" in messages


def test_validate_blocks_thin_form_evidence() -> None:
    evidence = evidence_template("form", "http://localhost:3000/orders/new")
    evidence.update(
        {
            "page_load": {"loaded": True},
            "interaction_evidence": [{"step": "open page"}],
        }
    )
    result = frontend_acceptance.validate_evidence(evidence)
    assert result["decision"] == "block"
    assert any(item["source"] == "form" for item in result["blockers"])


def test_validate_blocks_export_without_output() -> None:
    evidence = evidence_template("export", "http://localhost:3000/orders")
    evidence.update(
        {
            "page_load": {"loaded": True},
            "interaction_evidence": [{"step": "click export"}],
        }
    )
    evidence["export_checks"]["trigger_checked"] = True
    result = frontend_acceptance.validate_evidence(evidence)
    assert result["decision"] == "block"
    assert any("export output" in item["message"] for item in result["blockers"])


def test_validate_blocks_required_or_empty_screenshot_evidence() -> None:
    evidence = evidence_template("detail", "http://localhost:3000/orders/1")
    evidence.update({"page_load": {"loaded": True}, "dom_evidence": [{"selector": "#order"}], "screenshot_required": True})
    missing = frontend_acceptance.validate_evidence(evidence)
    assert missing["decision"] == "block"
    assert any(item["message"] == "screenshot evidence is required" for item in missing["blockers"])

    evidence["screenshot_evidence"] = [{}]
    empty = frontend_acceptance.validate_evidence(evidence)
    assert empty["decision"] == "block"
    assert any("path, selector, or description" in item["message"] for item in empty["blockers"])


def test_validate_blocks_browser_evidence_console_and_network_failures() -> None:
    evidence = evidence_template("detail", "http://localhost:3000/orders/1")
    evidence.update({"page_load": {"loaded": True}, "dom_evidence": [{"selector": "#order"}]})
    evidence["browser_evidence"].update(
        {
            "tested_route": "http://localhost:3000/orders/1",
            "viewport": "1280x720",
            "screenshots": [{"description": "detail page"}],
            "console_errors": ["ReferenceError"],
            "network_failures": [{"url": "/api/orders/1", "status": 503}],
        }
    )
    result = frontend_acceptance.validate_evidence(evidence)
    assert result["decision"] == "block"
    assert result["evidence_summary"]["browser_screenshot_count"] == 1
    messages = " ".join(item["message"] for item in result["blockers"])
    assert "console errors" in messages
    assert "failed network requests" in messages


def test_cli_template_writes_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)
        result = frontend_acceptance.template("dashboard", "http://localhost:3000/dashboard")
        frontend_acceptance.write_json(path / "frontend_acceptance.json", result)
        loaded = frontend_acceptance.load_json(path / "frontend_acceptance.json")
        assert loaded["page_type"] == "dashboard"


def test_validate_blocks_wrong_primary_entrypoint() -> None:
    evidence = evidence_template("custom", "/accident-analysis")
    evidence["page_load"] = {"loaded": True}
    evidence["dom_evidence"] = [{"selector": "#player"}]
    evidence["browser_evidence"]["tested_route"] = "/dual-camera-setting"
    result = frontend_acceptance.validate_evidence(evidence)
    assert any(item["source"] == "entrypoint_binding" for item in result["blockers"])


def test_clean_browser_evidence_fixture_passes_validation() -> None:
    fixture = ROOT / "examples/frontend-acceptance/clean-browser-evidence.json"
    evidence = json.loads(fixture.read_text(encoding="utf-8"))
    result = frontend_acceptance.validate_evidence(evidence)
    assert result["decision"] == "pass"
    assert result["evidence_summary"]["browser_screenshot_count"] == 1
    assert result["evidence_summary"]["console_error_count"] == 0
    assert result["evidence_summary"]["failed_request_count"] == 0


def run_all() -> None:
    test_template_contains_page_specific_fields()
    test_validate_passes_list_evidence_with_clean_browser_state()
    test_validate_blocks_console_and_failed_requests()
    test_validate_blocks_thin_form_evidence()
    test_validate_blocks_export_without_output()
    test_validate_blocks_required_or_empty_screenshot_evidence()
    test_validate_blocks_browser_evidence_console_and_network_failures()
    test_cli_template_writes_file()
    test_clean_browser_evidence_fixture_passes_validation()


if __name__ == "__main__":
    run_all()
    print("PASS frontend_acceptance_runner tests")
