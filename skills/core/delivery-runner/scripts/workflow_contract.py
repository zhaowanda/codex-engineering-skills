#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess  # nosec B404
from pathlib import Path
from typing import Any

# Only fixed git commands are executed without a shell.
VOLATILE_KEYS = {
    "artifact_digest",
    "command_digest",
    "generated_at",
    "generated_from_branch",
    "generated_from_commit",
    "input_digests",
    "lineage_schema",
    "permit_id",
    "producer",
    "producer_version",
}
LINEAGE_SCHEMA = "codex-workflow-artifact-lineage-v2"
DEFAULT_GIT_TIMEOUT_SECONDS = 2
DEPRECATED_LINEAGE_SCHEMAS = {"codex-workflow-artifact-lineage-v1"}
VALIDATORS = {"builtin:artifact-contract", "builtin:artifact-contract-v2"}
TYPE_CHECKS = {
    "array": lambda value: isinstance(value, list),
    "boolean": lambda value: isinstance(value, bool),
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
    "object": lambda value: isinstance(value, dict),
    "string": lambda value: isinstance(value, str),
}


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
        except (json.JSONDecodeError, UnicodeDecodeError):
            return hashlib.sha256(path.read_bytes()).hexdigest()
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


def git_context(workspace: Path | None = None) -> dict[str, str]:
    if os.environ.get("CODEX_PURE_MODE") == "1":
        return {}
    cwd = workspace or Path.cwd()
    result: dict[str, str] = {}
    timeout_seconds = int(os.environ.get("CODEX_GIT_TIMEOUT_SECONDS", str(DEFAULT_GIT_TIMEOUT_SECONDS)))
    for key, args in {
        "generated_from_commit": ["git", "rev-parse", "HEAD"],
        "generated_from_branch": ["git", "branch", "--show-current"],
    }.items():
        try:
            proc = subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=timeout_seconds)  # nosec B603
        except subprocess.TimeoutExpired:
            continue
        if proc.returncode == 0 and proc.stdout.strip():
            result[key] = proc.stdout.strip()
    return result


def bind_lineage(
    output: Path,
    producer: str,
    inputs: list[Path],
    producer_version: str = "workflow-v4",
    command: list[str] | None = None,
    workspace: Path | None = None,
) -> None:
    if output.suffix.lower() != ".json" or not output.exists():
        return
    data = read_json(output)
    if not data:
        return
    data["producer"] = producer
    data["producer_version"] = producer_version
    data["lineage_schema"] = LINEAGE_SCHEMA
    data["input_digests"] = input_digests(inputs)
    data["command_digest"] = canonical_digest(command or [producer])
    data.update(git_context(workspace))
    for path in inputs:
        if path.name == "edit_permit.json":
            permit = read_json(path)
            if permit.get("permit_id"):
                data["permit_id"] = str(permit["permit_id"])
    data["artifact_digest"] = canonical_digest(data)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def lineage_is_fresh(output: Path, inputs: list[Path]) -> bool:
    if not output.exists():
        return False
    if output.suffix.lower() != ".json":
        return False
    data = read_json(output)
    if not data or data.get("lineage_schema") != LINEAGE_SCHEMA:
        return False
    if data.get("artifact_digest") != canonical_digest(data):
        return False
    recorded_value = data.get("input_digests")
    recorded: dict[str, Any] = recorded_value if isinstance(recorded_value, dict) else {}
    expected = input_digests(inputs)
    return bool(expected) and all(recorded.get(name) == digest for name, digest in expected.items())


def nested_value(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def is_substantive(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, (str, list, dict, tuple, set)):
        return len(value) > 0
    return True


def validate_field_constraint(path: str, value: Any, constraint: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    expected_type = str(constraint.get("type") or "")
    checker = TYPE_CHECKS.get(expected_type)
    if expected_type and checker is None:
        issues.append(f"field {path} declares unsupported type {expected_type}")
    elif checker is not None and not checker(value):
        issues.append(f"field {path} must be {expected_type}")
        return issues
    if constraint.get("non_empty") is True and not is_substantive(value):
        issues.append(f"field {path} must be non-empty")
    if "const" in constraint and value != constraint.get("const"):
        issues.append(f"field {path} must equal {constraint.get('const')!r}")
    enum = constraint.get("enum")
    if isinstance(enum, list) and value not in enum:
        issues.append(f"field {path} must be one of {enum}")
    if isinstance(value, (str, list, dict)):
        minimum = constraint.get("min_length", constraint.get("min_items"))
        maximum = constraint.get("max_length", constraint.get("max_items"))
        if isinstance(minimum, int) and len(value) < minimum:
            issues.append(f"field {path} must contain at least {minimum} item(s)")
        if isinstance(maximum, int) and len(value) > maximum:
            issues.append(f"field {path} must contain at most {maximum} item(s)")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(constraint.get("min_value"), (int, float)) and value < constraint["min_value"]:
            issues.append(f"field {path} must be >= {constraint['min_value']}")
        if isinstance(constraint.get("max_value"), (int, float)) and value > constraint["max_value"]:
            issues.append(f"field {path} must be <= {constraint['max_value']}")
    pattern = constraint.get("pattern")
    if pattern and isinstance(value, str):
        try:
            if not re.search(str(pattern), value):
                issues.append(f"field {path} must match {pattern}")
        except re.error:
            issues.append(f"field {path} declares invalid pattern {pattern}")
    required_keys = constraint.get("required_keys")
    if isinstance(required_keys, list) and isinstance(value, dict):
        missing = [str(key) for key in required_keys if not is_substantive(value.get(str(key)))]
        if missing:
            issues.append(f"field {path} is missing substantive keys {missing}")
    return issues


def validate_cross_field_rules(data: dict[str, Any], rules: Any) -> list[str]:
    issues: list[str] = []
    if not isinstance(rules, list):
        return issues
    for rule in rules:
        if not isinstance(rule, dict):
            issues.append("cross_field_rules entries must be objects")
            continue
        kind = str(rule.get("kind") or "")
        left_path = str(rule.get("field") or "")
        left = nested_value(data, left_path) if left_path else None
        if kind == "requires_when" and left == rule.get("equals"):
            required = [str(item) for item in rule.get("requires", [])] if isinstance(rule.get("requires"), list) else []
            missing = [path for path in required if not is_substantive(nested_value(data, path))]
            if missing:
                issues.append(f"field {left_path}={left!r} requires substantive fields {missing}")
        elif kind == "equals_field":
            other_path = str(rule.get("other") or "")
            if left != nested_value(data, other_path):
                issues.append(f"field {left_path} must equal field {other_path}")
        elif kind not in {"requires_when", "equals_field"}:
            issues.append(f"unsupported cross-field rule {kind or '<missing>'}")
    return issues


def validate_artifact_contract(stage: dict[str, Any], data: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if stage.get("validator") not in VALIDATORS:
        issues.append(f"validator must be one of {sorted(VALIDATORS)}")
    expected_schema = str(stage.get("expected_schema") or "")
    accepted_schemas = {str(item) for item in stage.get("accepted_schemas", [])} if isinstance(stage.get("accepted_schemas"), list) else set()
    if expected_schema:
        accepted_schemas.add(expected_schema)
    if not data:
        return ["artifact is missing or invalid JSON"]
    if accepted_schemas and str(data.get("schema") or "") not in accepted_schemas:
        issues.append(f"schema must be one of {sorted(accepted_schemas)}")
    expected_lineage = str(stage.get("lineage_schema") or "")
    if expected_lineage:
        if data.get("lineage_schema") != expected_lineage:
            issues.append(f"lineage_schema must be {expected_lineage}")
        if not str(data.get("producer") or "").strip():
            issues.append("producer must be non-empty")
        if not str(data.get("producer_version") or "").strip():
            issues.append("producer_version must be non-empty")
        if not re.fullmatch(r"[0-9a-f]{64}", str(data.get("command_digest") or "")):
            issues.append("command_digest must be a SHA-256 digest")
        if not isinstance(data.get("input_digests"), dict):
            issues.append("input_digests must be an object")
        if data.get("artifact_digest") != canonical_digest(data):
            issues.append("artifact_digest does not match artifact content")
    for field in stage.get("required_fields", []) if isinstance(stage.get("required_fields"), list) else []:
        if nested_value(data, str(field)) is None:
            issues.append(f"required field is missing: {field}")
    constraints = stage.get("field_constraints")
    if isinstance(constraints, dict):
        for field, constraint in constraints.items():
            if not isinstance(constraint, dict):
                issues.append(f"field constraint for {field} must be an object")
                continue
            value = nested_value(data, str(field))
            if value is None:
                if constraint.get("required") is True:
                    issues.append(f"constrained field is missing: {field}")
                continue
            issues.extend(validate_field_constraint(str(field), value, constraint))
    evidence_fields = [str(item) for item in stage.get("evidence_fields", [])] if isinstance(stage.get("evidence_fields"), list) else []
    if stage.get("validator") == "builtin:artifact-contract-v2":
        if not evidence_fields:
            issues.append("artifact-contract-v2 requires evidence_fields")
        elif not any(is_substantive(nested_value(data, field)) for field in evidence_fields):
            issues.append(f"at least one evidence field must be substantive: {evidence_fields}")
        issues.extend(validate_cross_field_rules(data, stage.get("cross_field_rules")))
    accepted = {str(item) for item in stage.get("accepted_decisions", [])} if isinstance(stage.get("accepted_decisions"), list) else set()
    if accepted:
        decision = str(data.get("decision") or data.get("status") or "")
        if decision not in accepted:
            issues.append(f"decision/status must be one of {sorted(accepted)}")
    for key in ["blockers", "active_blockers", "missing_evidence", "release_blockers"]:
        if data.get(key):
            issues.append(f"{key} must be empty")
    return issues
