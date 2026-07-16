from __future__ import annotations

import importlib.util
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/core/auto-runner/scripts/agent_runtime.py"
spec = importlib.util.spec_from_file_location("agent_runtime", SCRIPT)
agent_runtime = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(agent_runtime)
CONTRACT_SCRIPT = ROOT / "skills/core/delivery-runner/scripts/workflow_contract.py"
contract_spec = importlib.util.spec_from_file_location("agent_runtime_test_contract", CONTRACT_SCRIPT)
workflow_contract = importlib.util.module_from_spec(contract_spec)
assert contract_spec and contract_spec.loader
contract_spec.loader.exec_module(workflow_contract)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_provider(path: Path, provider_type: str) -> None:
    write_json(
        path,
        {
            "schema": "codex-provider-attestation-v1",
            "provider_type": provider_type,
            "provider_id": f"{provider_type}-main",
            "evidence_id": f"EVIDENCE-{provider_type}",
            "immutable_evidence_uri": f"https://evidence.example/{provider_type}/1",
            "subject": "REQ-RUNTIME",
            "git_sha": "abc123",
            "status": "passed",
            "issued_at": "2026-07-14T10:00:00Z",
            "verification": {
                "verified": True,
                "verifier": "provider-adapter",
                "verified_at": "2026-07-14T10:01:00Z",
                "evidence_digest": "a" * 64,
            },
        },
    )


def test_runtime_session_and_hash_chain_verify() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        session = agent_runtime.start(root, "REQ-RUNTIME", "small_feature")
        agent_runtime.append_event(root, "requirement_ingested", "test", evidence_refs=["requirement.json"])

        result = agent_runtime.verify(root)

        assert session["schema"] == "codex-agent-runtime-session-v1"
        assert result["decision"] == "pass"
        assert result["event_count"] == 2
        assert result["event_root_digest"] != agent_runtime.ZERO_DIGEST


def test_runtime_detects_tampered_event() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        agent_runtime.start(root, "REQ-RUNTIME")
        events = root / "runtime/events.jsonl"
        rows = events.read_text(encoding="utf-8").splitlines()
        event = json.loads(rows[0])
        event["action"] = "tampered"
        events.write_text(json.dumps(event) + "\n", encoding="utf-8")

        result = agent_runtime.verify(root)

        assert result["decision"] == "block"
        assert any(item["message"] == "event digest does not match content" for item in result["blockers"])


def test_runtime_redacts_secrets_from_imported_event() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        agent_runtime.start(root, "REQ-RUNTIME")

        event = agent_runtime.append_event(
            root,
            "external_event",
            "mcp",
            authorization="Bearer live-authorization-token",
            details={"token": "live-token", "message": "password=hunter2"},
        )

        assert event["details"]["token"] == "[REDACTED]"
        assert "hunter2" not in event["details"]["message"]
        assert event["authorization"] == "[REDACTED]"


def test_runtime_blocks_destructive_command_authorization() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        agent_runtime.start(root, "REQ-RUNTIME")

        result = agent_runtime.authorize(root, "execute", "git reset --hard HEAD~1")

        assert result["decision"] == "block"


def test_runtime_blocks_git_hook_bypass() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        agent_runtime.start(root, "REQ-RUNTIME")

        push = agent_runtime.authorize(root, "execute", "git push origin feature/test --no-verify")
        commit = agent_runtime.authorize(root, "execute", "git commit --no-verify -m bypass")

        assert push["decision"] == "block"
        assert commit["decision"] == "block"
        assert all(item["source"] == "policy" for result in [push, commit] for item in result["blockers"])
        assert all(result["blockers"] for result in [push, commit])


def test_runtime_checkpoint_requires_expected_actions() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        agent_runtime.start(root, "REQ-RUNTIME")

        blocked = agent_runtime.checkpoint(root, "intake")
        agent_runtime.append_event(root, "requirement_ingested", "test")
        passed = agent_runtime.checkpoint(root, "intake", ["requirement.json"])

        assert blocked["decision"] == "block"
        assert passed["decision"] == "pass"


def test_later_events_do_not_stale_historical_checkpoint_lineage() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        requirement = root / "requirement_ingestion.json"
        write_json(requirement, {"decision": "ready"})
        agent_runtime.start(root, "REQ-RUNTIME")
        agent_runtime.append_event(root, "requirement_ingested", "test")
        agent_runtime.checkpoint(root, "intake", ["requirement_ingestion.json"])
        checkpoint = root / "runtime/checkpoints/intake.json"

        agent_runtime.append_event(root, "design_completed", "test")

        assert workflow_contract.lineage_is_fresh(checkpoint, [requirement])
        assert "session.json" not in json.loads(checkpoint.read_text(encoding="utf-8"))["input_digests"]


def test_provider_attestation_binds_subject_and_git_sha() -> None:
    payload = {
        "schema": "codex-provider-attestation-v1",
        "provider_type": "ci",
        "provider_id": "ci-main",
        "evidence_id": "RUN-1",
        "immutable_evidence_uri": "https://ci.example/runs/RUN-1",
        "subject": "REQ-1",
        "git_sha": "abc123",
        "status": "passed",
        "issued_at": "2026-07-14T10:00:00Z",
        "verification": {"verified": True, "verifier": "provider-adapter", "verified_at": "2026-07-14T10:01:00Z", "evidence_digest": "a" * 64},
    }

    passed = agent_runtime.provider_attestation(payload, "REQ-1", "abc123")
    blocked = agent_runtime.provider_attestation(payload, "REQ-2", "def456")

    assert passed["decision"] == "pass"
    assert blocked["decision"] == "block"
    assert len(blocked["blockers"]) == 2


def test_provider_attestation_requires_immutable_unexpired_evidence() -> None:
    payload = {
        "schema": "codex-provider-attestation-v1",
        "provider_type": "ci",
        "provider_id": "ci-main",
        "evidence_id": "RUN-1",
        "subject": "REQ-1",
        "status": "passed",
        "issued_at": "2026-07-14T10:00:00Z",
        "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        "verification": {"verified": True, "verifier": "provider-adapter", "verified_at": "2026-07-14T10:01:00Z", "evidence_digest": "a" * 64},
    }

    result = agent_runtime.provider_attestation(payload)

    messages = {item["message"] for item in result["blockers"]}
    assert result["decision"] == "block"
    assert "provider attestation is missing immutable_evidence_uri" in messages
    assert "provider attestation has expired" in messages


def test_governance_waiver_requires_separation_expiry_and_audit() -> None:
    payload = {
        "schema": "codex-governance-waiver-v1",
        "waiver_id": "WV-1",
        "subject": "REQ-1",
        "affected_gates": ["project_skill_index_sync"],
        "reason": "temporary exception",
        "risk": "index may be stale",
        "owner": {"identity": "owner"},
        "approver": {"identity": "approver", "approved_at": "2026-07-15T08:00:00Z", "evidence_id": "APR-1"},
        "issued_at": "2026-07-15T08:00:00Z",
        "expires_at": "2099-07-16T08:00:00Z",
        "compensating_controls": ["manual source-location review"],
        "audit": {"immutable_evidence_uri": "https://evidence.example/WV-1", "retention_days": 365},
        "status": "approved",
    }

    passed = agent_runtime.GOVERNANCE_CONTRACT.validate_waiver(payload, "REQ-1", "project_skill_index_sync")
    payload["approver"]["identity"] = "owner"
    payload["expires_at"] = "2026-07-14T08:00:00Z"
    blocked = agent_runtime.GOVERNANCE_CONTRACT.validate_waiver(payload, "REQ-1", "project_skill_index_sync")

    assert passed["decision"] == "pass"
    messages = {item["message"] for item in blocked["blockers"]}
    assert "waiver owner must not self-approve" in messages
    assert "waiver has expired" in messages


def test_advance_post_implementation_blocks_then_passes_with_evidence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        agent_runtime.start(root, "REQ-RUNTIME")

        blocked = agent_runtime.advance(root, "post_implementation")
        write_json(
            root / "implementation_completion_gate.json",
            {"decision": "pass", "blockers": [], "changed_files": ["src/service.py"]},
        )
        write_json(root / "post_change_implementation_report.json", {"decision": "pass", "blockers": []})
        write_json(root / "diff_impact.json", {"decision": "ready", "blockers": []})
        passed = agent_runtime.advance(root, "post_implementation")

        assert blocked["decision"] == "block"
        assert passed["decision"] == "pass"
        assert {"write_completed", "implementation_validated"} <= set(agent_runtime.verify(root)["actions"])


def test_advance_pre_push_requires_post_implementation_harness() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        agent_runtime.start(root, "REQ-RUNTIME")
        for filename, decision in [
            ("post_implementation_traceability_matrix.json", "pass"),
            ("test_evidence_gate.json", "pass"),
            ("code_review_gate.json", "approve"),
        ]:
            write_json(root / filename, {"decision": decision, "blockers": []})

        blocked = agent_runtime.advance(root, "pre_push")
        write_json(root / "harness/post_implementation.json", {"decision": "pass", "blockers": []})
        passed = agent_runtime.advance(root, "pre_push")

        assert blocked["decision"] == "block"
        assert any("harness/post_implementation.json" in item["message"] for item in blocked["blockers"])
        assert passed["decision"] == "pass"


def test_advance_release_requires_all_provider_types() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        agent_runtime.start(root, "REQ-RUNTIME")
        write_json(root / "release_change.json", {"decision": "pass", "blockers": []})
        provider_dir = root / "runtime/providers"
        provider_files = []
        for provider_type in ["ci", "change_management", "deployment", "observability"]:
            path = provider_dir / f"{provider_type}.json"
            write_provider(path, provider_type)
            provider_files.append(path)

        blocked = agent_runtime.advance(root, "release", provider_files[:3])
        passed = agent_runtime.advance(root, "release", provider_files)

        assert blocked["decision"] == "block"
        assert blocked["blockers"][0]["provider_types"] == ["observability"]
        assert passed["decision"] == "pass"
        assert {item["provider_type"] for item in passed["provider_attestations"]} == {
            "ci",
            "change_management",
            "deployment",
            "observability",
        }


def test_closed_runtime_rejects_new_events() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        agent_runtime.start(root, "REQ-RUNTIME")
        agent_runtime.close(root)

        event = agent_runtime.append_event(root, "write_completed", "test")

        assert event["decision"] == "block"


def test_runtime_close_requires_post_release_observation_and_closes_session() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        agent_runtime.start(root, "REQ-RUNTIME")

        blocked = agent_runtime.advance(root, "close")
        write_json(root / "post_release_observation.json", {"decision": "pass", "blockers": []})
        passed = agent_runtime.advance(root, "close")

        assert blocked["decision"] == "block"
        assert passed["decision"] == "pass"
        assert passed["checkpoint"] == "close"
        assert agent_runtime.verify(root)["status"] == "closed"
