#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

WAIVER_SCHEMA = "codex-governance-waiver-v1"


def parse_time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo is not None else None


def identity(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    return str(value.get("identity") or value.get("name") or "").strip()


def validate_waiver(
    data: dict[str, Any],
    expected_subject: str = "",
    expected_gate: str = "",
    at: datetime | None = None,
) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    required = [
        "waiver_id",
        "subject",
        "affected_gates",
        "reason",
        "risk",
        "owner",
        "approver",
        "issued_at",
        "expires_at",
        "compensating_controls",
        "audit",
    ]
    if data.get("schema") != WAIVER_SCHEMA:
        blockers.append({"source": "waiver", "message": f"waiver schema must be {WAIVER_SCHEMA}"})
    for field in required:
        if not data.get(field):
            blockers.append({"source": "waiver", "message": f"waiver is missing {field}"})
    if data.get("status") != "approved":
        blockers.append({"source": "waiver", "message": "waiver status must be approved"})

    gates = [str(item).strip() for item in data.get("affected_gates", [])] if isinstance(data.get("affected_gates"), list) else []
    if not gates:
        blockers.append({"source": "waiver", "message": "waiver affected_gates must be a non-empty list"})
    if expected_gate and expected_gate not in gates:
        blockers.append({"source": "waiver", "message": "waiver does not cover the expected gate", "expected_gate": expected_gate})
    if expected_subject and data.get("subject") != expected_subject:
        blockers.append({"source": "waiver", "message": "waiver subject does not match"})

    owner = identity(data.get("owner"))
    approver_value = data.get("approver")
    approver_data: dict[str, Any] = approver_value if isinstance(approver_value, dict) else {}
    approver = identity(approver_data)
    if not owner:
        blockers.append({"source": "waiver", "message": "waiver owner identity is required"})
    if not approver:
        blockers.append({"source": "waiver", "message": "waiver approver identity is required"})
    if owner and owner == approver:
        blockers.append({"source": "waiver", "message": "waiver owner must not self-approve"})
    for field in ["approved_at", "evidence_id"]:
        if not approver_data.get(field):
            blockers.append({"source": "waiver", "message": f"waiver approver.{field} is required"})

    issued = parse_time(data.get("issued_at"))
    expires = parse_time(data.get("expires_at"))
    approved = parse_time(approver_data.get("approved_at"))
    current = at or datetime.now(timezone.utc)
    if issued is None:
        blockers.append({"source": "waiver", "message": "waiver issued_at must be timezone-aware ISO-8601"})
    if expires is None:
        blockers.append({"source": "waiver", "message": "waiver expires_at must be timezone-aware ISO-8601"})
    elif expires <= current:
        blockers.append({"source": "waiver", "message": "waiver has expired"})
    if approved is None:
        blockers.append({"source": "waiver", "message": "waiver approver.approved_at must be timezone-aware ISO-8601"})
    if issued and expires and expires <= issued:
        blockers.append({"source": "waiver", "message": "waiver expires_at must be later than issued_at"})

    controls = data.get("compensating_controls")
    if not isinstance(controls, list) or not [item for item in controls if str(item).strip()]:
        blockers.append({"source": "waiver", "message": "waiver requires compensating_controls"})
    audit_value = data.get("audit")
    audit: dict[str, Any] = audit_value if isinstance(audit_value, dict) else {}
    for field in ["immutable_evidence_uri", "retention_days"]:
        if not audit.get(field):
            blockers.append({"source": "waiver", "message": f"waiver audit.{field} is required"})
    if audit.get("retention_days") and (not isinstance(audit.get("retention_days"), int) or audit["retention_days"] <= 0):
        blockers.append({"source": "waiver", "message": "waiver audit.retention_days must be a positive integer"})

    return {
        "schema": "codex-governance-waiver-validation-v1",
        "decision": "block" if blockers else "pass",
        "waiver_id": data.get("waiver_id", ""),
        "subject": data.get("subject", ""),
        "affected_gates": gates,
        "expires_at": data.get("expires_at", ""),
        "blockers": blockers,
    }
