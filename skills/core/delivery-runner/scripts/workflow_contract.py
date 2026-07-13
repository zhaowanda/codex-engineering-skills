#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


VOLATILE_KEYS = {"generated_at", "updated_at", "producer", "producer_version", "lineage_schema", "input_digests"}
LINEAGE_SCHEMA = "codex-workflow-artifact-lineage-v1"


def canonical_digest(data: Any) -> str:
    def strip_volatile(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: strip_volatile(item)
                for key, item in sorted(value.items())
                if key not in VOLATILE_KEYS
            }
        if isinstance(value, list):
            return [strip_volatile(item) for item in value]
        return value

    payload = json.dumps(strip_volatile(data), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def path_digest(path: Path) -> str:
    if path.is_dir():
        entries: list[dict[str, str]] = []
        for child in sorted(item for item in path.rglob("*") if item.is_file() and ".git" not in item.parts):
            entries.append({"path": child.relative_to(path).as_posix(), "digest": path_digest(child)})
        return canonical_digest(entries)
    if path.suffix.lower() == ".json":
        try:
            return canonical_digest(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            pass
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command_input_paths(command: list[str], output: Path) -> list[Path]:
    result: list[Path] = []
    output_resolved = output.resolve()
    for token in command[1:]:
        candidate = Path(str(token))
        if not candidate.is_absolute():
            candidate = candidate.resolve()
        if candidate == output_resolved or not candidate.exists():
            continue
        if candidate.is_dir() and output_resolved.is_relative_to(candidate):
            continue
        if candidate.is_file() or candidate.is_dir():
            result.append(candidate)
    unique: dict[str, Path] = {}
    for path in result:
        key = path.name
        if key in unique and unique[key] != path:
            key = str(path)
        unique[key] = path
    return list(unique.values())


def input_digests(paths: list[Path]) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in paths:
        key = path.name
        if key in result:
            key = str(path)
        result[key] = path_digest(path)
    return result


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def bind_lineage(output: Path, producer: str, inputs: list[Path], producer_version: str = "workflow-v3") -> None:
    if output.suffix.lower() != ".json" or not output.exists():
        return
    data = read_json(output)
    if not data:
        return
    recorded = data.get("input_digests") if isinstance(data.get("input_digests"), dict) else {}
    recorded.update(input_digests(inputs))
    data["producer"] = producer
    data["producer_version"] = producer_version
    data["lineage_schema"] = LINEAGE_SCHEMA
    data["input_digests"] = recorded
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def lineage_is_fresh(output: Path, inputs: list[Path]) -> bool:
    if not output.exists():
        return False
    if output.suffix.lower() != ".json":
        return False
    data = read_json(output)
    if not data or data.get("lineage_schema") != LINEAGE_SCHEMA:
        return False
    recorded = data.get("input_digests") if isinstance(data.get("input_digests"), dict) else {}
    expected = input_digests(inputs)
    return bool(expected) and all(recorded.get(name) == digest for name, digest in expected.items())


def nested_value(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def validate_artifact_contract(stage: dict[str, Any], data: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if stage.get("validator") != "builtin:artifact-contract":
        issues.append("validator must be builtin:artifact-contract")
    expected_schema = str(stage.get("expected_schema") or "")
    accepted_schemas = {str(item) for item in stage.get("accepted_schemas", [])} if isinstance(stage.get("accepted_schemas"), list) else set()
    if expected_schema:
        accepted_schemas.add(expected_schema)
    if not data:
        return ["artifact is missing or invalid JSON"]
    if accepted_schemas and str(data.get("schema") or "") not in accepted_schemas:
        issues.append(f"schema must be one of {sorted(accepted_schemas)}")
    for field in stage.get("required_fields", []) if isinstance(stage.get("required_fields"), list) else []:
        if nested_value(data, str(field)) is None:
            issues.append(f"required field is missing: {field}")
    accepted = {str(item) for item in stage.get("accepted_decisions", [])} if isinstance(stage.get("accepted_decisions"), list) else set()
    if accepted:
        decision = str(data.get("decision") or data.get("status") or "")
        if decision not in accepted:
            issues.append(f"decision/status must be one of {sorted(accepted)}")
    for key in ["blockers", "active_blockers", "missing_evidence", "release_blockers"]:
        if data.get(key):
            issues.append(f"{key} must be empty")
    return issues
