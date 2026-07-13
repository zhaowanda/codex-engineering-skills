from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


auto_runner = load_module("contract_auto_runner", ROOT / "skills/core/auto-runner/scripts/auto_runner.py")
contract = load_module("workflow_contract_v2", ROOT / "skills/core/delivery-runner/scripts/workflow_contract.py")


def put_nested(data: dict, path: str, value) -> None:
    current = data
    parts = path.split(".")
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def stage_registry() -> list[dict]:
    registry = auto_runner.load_restricted_yaml(ROOT / "config/workflow-stages.example.yaml")
    return [dict(stage, validator=registry["default_validator"], lineage_schema=registry["default_lineage_schema"]) for stage in registry["stages"]]


def vacuous_artifact(stage: dict, empty_value) -> dict:
    schemas = stage.get("accepted_schemas") or []
    data = {
        "schema": stage.get("expected_schema") or schemas[0],
        "decision": (stage.get("accepted_decisions") or ["pass"])[0],
        "blockers": [],
        "producer": "property-test",
        "producer_version": "workflow-v4",
        "lineage_schema": contract.LINEAGE_SCHEMA,
        "command_digest": contract.canonical_digest(["property-test"]),
        "input_digests": {},
    }
    for field in stage.get("required_fields", []):
        if field not in data and field not in {"schema", "decision", "blockers"}:
            put_nested(data, field, empty_value)
    data["artifact_digest"] = contract.canonical_digest(data)
    return data


@given(st.sampled_from(["", [], {}]))
def test_all_stages_reject_vacuous_semantic_evidence(empty_value) -> None:
    for stage in stage_registry():
        issues = contract.validate_artifact_contract(stage, vacuous_artifact(stage, empty_value))
        assert issues, stage["name"]


@given(st.text(min_size=1), st.text(min_size=1))
def test_artifact_digest_detects_any_semantic_tampering(before: str, after: str) -> None:
    if before == after:
        return
    artifact = {"schema": "test-v1", "decision": "pass", "evidence": before}
    artifact["artifact_digest"] = contract.canonical_digest(artifact)
    artifact["evidence"] = after
    assert artifact["artifact_digest"] != contract.canonical_digest(artifact)


def test_lineage_rebuild_drops_removed_inputs(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    output = tmp_path / "output.json"
    first.write_text(json.dumps({"value": 1}), encoding="utf-8")
    second.write_text(json.dumps({"value": 2}), encoding="utf-8")
    output.write_text(json.dumps({"schema": "test-v1", "decision": "pass"}), encoding="utf-8")
    contract.bind_lineage(output, "test", [first, second], command=["first-run"])
    contract.bind_lineage(output, "test", [first], command=["second-run"])
    data = json.loads(output.read_text(encoding="utf-8"))
    assert set(data["input_digests"]) == {"first.json"}
    assert data["artifact_digest"] == contract.canonical_digest(data)
