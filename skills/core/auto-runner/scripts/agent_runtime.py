#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess  # nosec B404
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SESSION_SCHEMA = "codex-agent-runtime-session-v1"
EVENT_SCHEMA = "codex-agent-runtime-event-v1"
CHECKPOINT_SCHEMA = "codex-runtime-checkpoint-v1"
ATTESTATION_SCHEMA = "codex-provider-attestation-v1"
ZERO_DIGEST = "0" * 64
SENSITIVE_KEYS = {"authorization", "cookie", "credential", "password", "private_key", "secret", "token"}
SAFE_AUTHORIZATION_LABELS = {"runtime-policy", "external-attestation"}
DESTRUCTIVE_COMMANDS = [
    re.compile(r"(?:^|\s)rm\s+-rf(?:\s|$)"),
    re.compile(r"git\s+reset\s+--hard"),
    re.compile(r"git\s+checkout\s+--"),
    re.compile(r"(?:^|\s)(?:drop|truncate)\s+(?:table|database)\b", re.I),
    re.compile(r"(?:^|\s)git\s+(?:commit|push)\b[^\n]*\s--no-verify(?:\s|$)"),
]
CHECKPOINT_ACTIONS = {
    "intake": {"session_started", "requirement_ingested"},
    "design": {"design_completed"},
    "pre_edit": {"edit_authorized"},
    "post_implementation": {"write_completed", "implementation_validated"},
    "pre_push": {"test_completed", "review_completed", "push_authorized"},
    "release": {"release_authorized", "provider_verified"},
    "close": {"observation_completed", "session_closed"},
}
CHECKPOINT_INPUTS = {
    "intake": ["requirement_ingestion.json", "requirement_ir.json"],
    "design": ["technical_design.json", "architecture_design.json", "delivery_plan.json", "delivery_plan_review.json"],
    "pre_edit": ["edit_permit.json", "delivery_plan.json", "harness_validation.json"],
    "post_implementation": ["delivery_plan.json", "implementation_completion_gate.json", "post_change_implementation_report.json", "diff_impact.json"],
    "pre_push": ["post_change_implementation_report.json", "post_implementation_traceability_matrix.json", "test_evidence_gate.json", "code_review_gate.json"],
    "release": ["ci_execution_evidence.json", "release_change.json", "environment_promotion.json", "uat_acceptance.json"],
    "close": ["post_release_observation.json"],
}
RELEASE_PROVIDER_TYPES = {"ci", "change_management", "deployment", "observability"}


def load_governance_contract() -> Any:
    path = Path(__file__).resolve().parents[4] / "skills/core/delivery-runner/scripts/governance_contract.py"
    spec = importlib.util.spec_from_file_location("agent_runtime_governance_contract", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load governance contract: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GOVERNANCE_CONTRACT = load_governance_contract()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sanitize(value: Any, key: str = "") -> Any:
    if any(term in key.lower() for term in SENSITIVE_KEYS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(child_key): sanitize(child, str(child_key)) for child_key, child in value.items()}
    if isinstance(value, list):
        return [sanitize(child, key) for child in value[:100]]
    if isinstance(value, str):
        value = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[REDACTED]", value)
        value = re.sub(r"(?i)(password|secret|token)=([^\s&]+)", r"\1=[REDACTED]", value)
        return value[:2000]
    return value


def runtime_paths(artifact_dir: Path) -> tuple[Path, Path]:
    runtime = artifact_dir / "runtime"
    return runtime / "session.json", runtime / "events.jsonl"


def bind_runtime_lineage(artifact_dir: Path, checkpoint_name: str) -> None:
    root = Path(__file__).resolve().parents[4]
    contract_path = root / "skills/core/delivery-runner/scripts/workflow_contract.py"
    spec = importlib.util.spec_from_file_location("agent_runtime_workflow_contract", contract_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load workflow contract: {contract_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    session_path, _ = runtime_paths(artifact_dir)
    module.bind_lineage(session_path, "runtime_session", [], command=["agent-runtime", "start"], workspace=root)
    checkpoint_path = artifact_dir / "runtime/checkpoints" / f"{checkpoint_name}.json"
    inputs = [artifact_dir / name for name in CHECKPOINT_INPUTS.get(checkpoint_name, []) if (artifact_dir / name).exists()]
    module.bind_lineage(
        checkpoint_path,
        f"runtime_{checkpoint_name}",
        inputs,
        command=["agent-runtime", "checkpoint", checkpoint_name],
        workspace=root,
    )


def git_context(repo: Path) -> dict[str, str]:
    def run(*args: str) -> str:
        # Fixed Git executable and argument vector; no shell interpolation.
        result = subprocess.run(  # nosec B603 B607
            ["git", "-C", str(repo), *args], text=True, capture_output=True, check=False
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    return {"repo": str(repo.resolve()), "head": run("rev-parse", "HEAD"), "branch": run("branch", "--show-current")}


def start(
    artifact_dir: Path,
    doc_id: str,
    profile: str = "",
    repos: list[Path] | None = None,
    actor: str = "codex",
    model: str = "",
    max_events: int = 10_000,
) -> dict[str, Any]:
    session_path, events_path = runtime_paths(artifact_dir)
    existing = read_json(session_path)
    if existing:
        if existing.get("doc_id") != doc_id:
            return {"schema": SESSION_SCHEMA, "decision": "block", "blockers": [{"source": "doc_id", "message": "existing runtime session belongs to another doc_id"}]}
        verification = verify(artifact_dir)
        return existing if verification["decision"] == "pass" else verification
    session = {
        "schema": SESSION_SCHEMA,
        "session_id": f"RT-{uuid.uuid4().hex}",
        "doc_id": doc_id,
        "profile": profile,
        "actor": actor,
        "model": model,
        "status": "active",
        "started_at": now(),
        "closed_at": "",
        "event_count": 0,
        "event_root_digest": ZERO_DIGEST,
        "max_events": max_events,
        "repositories": [git_context(repo) for repo in repos or []],
        "decision": "ready",
        "blockers": [],
    }
    write_json(session_path, session)
    events_path.parent.mkdir(parents=True, exist_ok=True)
    events_path.touch(exist_ok=True)
    append_event(artifact_dir, "session_started", "runtime", actor=actor, details={"profile": profile, "model": model})
    return read_json(session_path)


def load_events(events_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    if not events_path.exists():
        return events, [{"source": "events", "message": "runtime events file is missing"}]
    for line_no, raw in enumerate(events_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except Exception:
            blockers.append({"source": "events", "message": "runtime event is invalid JSON", "line": line_no})
            continue
        if not isinstance(item, dict):
            blockers.append({"source": "events", "message": "runtime event must be an object", "line": line_no})
            continue
        events.append(item)
    return events, blockers


def verify(artifact_dir: Path, expected_head: str = "") -> dict[str, Any]:
    session_path, events_path = runtime_paths(artifact_dir)
    session = read_json(session_path)
    blockers: list[dict[str, Any]] = []
    if session.get("schema") != SESSION_SCHEMA:
        blockers.append({"source": "session", "message": "runtime session is missing or has an unsupported schema"})
    events, event_blockers = load_events(events_path)
    blockers.extend(event_blockers)
    previous = ZERO_DIGEST
    for expected_sequence, event in enumerate(events, start=1):
        material = {key: value for key, value in event.items() if key != "event_digest"}
        if event.get("schema") != EVENT_SCHEMA:
            blockers.append({"source": "events", "message": "event schema is invalid", "sequence": expected_sequence})
        if event.get("session_id") != session.get("session_id"):
            blockers.append({"source": "events", "message": "event belongs to another session", "sequence": expected_sequence})
        if event.get("sequence") != expected_sequence:
            blockers.append({"source": "events", "message": "event sequence has a gap or duplicate", "sequence": expected_sequence})
        if event.get("previous_digest") != previous:
            blockers.append({"source": "events", "message": "event previous_digest does not match", "sequence": expected_sequence})
        calculated = digest(material)
        if event.get("event_digest") != calculated:
            blockers.append({"source": "events", "message": "event digest does not match content", "sequence": expected_sequence})
        previous = calculated
    if session and session.get("event_count") != len(events):
        blockers.append({"source": "session", "message": "session event_count does not match event log"})
    if session and session.get("event_root_digest") != previous:
        blockers.append({"source": "session", "message": "session root digest does not match event log"})
    if expected_head:
        heads = {str(item.get("head") or "") for item in session.get("repositories", []) if isinstance(item, dict)}
        if expected_head not in heads:
            blockers.append({"source": "git", "message": "runtime session is not bound to expected Git HEAD", "expected_head": expected_head})
    decision = "block" if blockers else "pass"
    if session:
        session["decision"] = "block" if blockers else "ready"
        session["verification_decision"] = decision
        session["verification_blockers"] = blockers
        session["verified_event_count"] = len(events)
        session["verified_event_root_digest"] = previous
        write_json(session_path, session)
    return {
        "schema": "codex-agent-runtime-verification-v1",
        "session_id": session.get("session_id", ""),
        "decision": decision,
        "status": session.get("status", "missing"),
        "event_count": len(events),
        "event_root_digest": previous,
        "actions": sorted({str(item.get("action") or "") for item in events if item.get("action")}),
        "blockers": blockers,
    }


def append_event(
    artifact_dir: Path,
    action: str,
    tool: str,
    *,
    actor: str = "codex",
    target: str = "",
    decision: str = "allow",
    authorization: str = "runtime-policy",
    details: dict[str, Any] | None = None,
    evidence_refs: list[str] | None = None,
) -> dict[str, Any]:
    session_path, events_path = runtime_paths(artifact_dir)
    session = read_json(session_path)
    if session.get("status") != "active" and action != "session_closed":
        return {"schema": EVENT_SCHEMA, "decision": "block", "blockers": [{"source": "session", "message": "runtime session is not active"}]}
    if int(session.get("event_count") or 0) >= int(session.get("max_events") or 10_000):
        return {"schema": EVENT_SCHEMA, "decision": "block", "blockers": [{"source": "budget", "message": "runtime event budget exceeded"}]}
    event = {
        "schema": EVENT_SCHEMA,
        "event_id": f"EV-{uuid.uuid4().hex}",
        "session_id": session.get("session_id", ""),
        "sequence": int(session.get("event_count") or 0) + 1,
        "previous_digest": session.get("event_root_digest") or ZERO_DIGEST,
        "occurred_at": now(),
        "actor": actor,
        "action": action,
        "tool": tool,
        "target": sanitize(target),
        "decision": decision,
        "authorization": authorization if authorization in SAFE_AUTHORIZATION_LABELS else "[REDACTED]",
        "details": sanitize(details or {}),
        "evidence_refs": sanitize(evidence_refs or []),
    }
    event["event_digest"] = digest(event)
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    session["event_count"] = event["sequence"]
    session["event_root_digest"] = event["event_digest"]
    write_json(session_path, session)
    return event


def authorize(artifact_dir: Path, action: str, target: str, tool: str = "runtime") -> dict[str, Any]:
    session = read_json(runtime_paths(artifact_dir)[0])
    blockers: list[dict[str, Any]] = []
    if session.get("status") != "active":
        blockers.append({"source": "session", "message": "active runtime session is required"})
    if action in {"execute", "write"} and any(pattern.search(target) for pattern in DESTRUCTIVE_COMMANDS):
        blockers.append({"source": "policy", "message": "destructive action is forbidden by open-core runtime policy"})
    decision = "block" if blockers else "allow"
    event = append_event(
        artifact_dir,
        f"{action}_authorized",
        tool,
        target=target,
        decision=decision,
        details={"blockers": blockers},
    ) if session else {}
    return {
        "schema": "codex-agent-runtime-authorization-v1",
        "session_id": session.get("session_id", ""),
        "action": action,
        "target": sanitize(target),
        "decision": decision,
        "event_id": event.get("event_id", ""),
        "blockers": blockers,
    }


def execute(artifact_dir: Path, command: list[str], timeout: int = 300, cwd: Path | None = None) -> dict[str, Any]:
    command_text = " ".join(command)
    auth = authorize(artifact_dir, "execute", command_text, "subprocess")
    if auth["decision"] != "allow":
        return auth
    append_event(artifact_dir, "tool_call_requested", "subprocess", target=command_text, details={"cwd": str(cwd or "")})
    started = datetime.now(timezone.utc)
    try:
        # authorize() rejects prohibited commands; shell=False preserves argument boundaries.
        proc = subprocess.run(  # nosec B603
            command, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False
        )
        timed_out = False
        returncode = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = 124
        stdout = str(exc.stdout or "")
        stderr = str(exc.stderr or "")
    duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    event = append_event(
        artifact_dir,
        "tool_call_completed",
        "subprocess",
        target=command_text,
        decision="allow" if returncode == 0 else "block",
        details={
            "returncode": returncode,
            "duration_ms": duration_ms,
            "timed_out": timed_out,
            "stdout_digest": hashlib.sha256(stdout.encode("utf-8", errors="ignore")).hexdigest(),
            "stderr_digest": hashlib.sha256(stderr.encode("utf-8", errors="ignore")).hexdigest(),
            "stdout_tail": sanitize(stdout[-1000:]),
            "stderr_tail": sanitize(stderr[-1000:]),
        },
    )
    return {
        "schema": "codex-agent-runtime-execution-v1",
        "decision": "pass" if returncode == 0 else "block",
        "returncode": returncode,
        "duration_ms": duration_ms,
        "event_id": event.get("event_id", ""),
        "stdout": stdout,
        "stderr": stderr,
        "blockers": [] if returncode == 0 else [{"source": "command", "message": "runtime command failed", "returncode": returncode}],
    }


def provider_attestation(data: dict[str, Any], expected_subject: str = "", expected_head: str = "") -> dict[str, Any]:
    required = [
        "provider_type",
        "provider_id",
        "evidence_id",
        "immutable_evidence_uri",
        "subject",
        "status",
        "issued_at",
        "verification",
    ]
    blockers = [{"source": "provider", "message": f"provider attestation is missing {field}"} for field in required if not data.get(field)]
    if data.get("schema") != ATTESTATION_SCHEMA:
        blockers.append({"source": "provider", "message": "provider attestation schema is invalid"})
    if data.get("provider_type") not in RELEASE_PROVIDER_TYPES:
        blockers.append({"source": "provider", "message": "provider type is not supported"})
    if data.get("immutable_evidence_uri") and not re.match(r"^[a-z][a-z0-9+.-]*://\S+$", str(data["immutable_evidence_uri"]), re.I):
        blockers.append({"source": "provider", "message": "provider immutable_evidence_uri must be an absolute URI"})
    if data.get("status") not in {"pass", "passed", "approved", "success", "healthy"}:
        blockers.append({"source": "provider", "message": "provider status is not accepted"})
    verification: dict[str, Any] = dict(data.get("verification") or {}) if isinstance(data.get("verification"), dict) else {}
    if verification.get("verified") is not True:
        blockers.append({"source": "provider", "message": "provider attestation is not verified"})
    for field in ["verifier", "verified_at", "evidence_digest"]:
        if not verification.get(field):
            blockers.append({"source": "provider", "message": f"provider verification is missing {field}"})
    if verification.get("evidence_digest") and not re.fullmatch(r"[a-fA-F0-9]{64}", str(verification["evidence_digest"])):
        blockers.append({"source": "provider", "message": "provider evidence_digest must be a SHA-256 hex digest"})
    if expected_subject and data.get("subject") != expected_subject:
        blockers.append({"source": "provider", "message": "provider subject does not match"})
    if expected_head and data.get("git_sha") != expected_head:
        blockers.append({"source": "provider", "message": "provider Git SHA does not match"})
    issued_at = GOVERNANCE_CONTRACT.parse_time(data.get("issued_at"))
    if issued_at is None:
        blockers.append({"source": "provider", "message": "provider issued_at must be a timezone-aware ISO-8601 timestamp"})
    elif issued_at > datetime.now(timezone.utc):
        blockers.append({"source": "provider", "message": "provider issued_at must not be in the future"})
    verified_at = GOVERNANCE_CONTRACT.parse_time(verification.get("verified_at"))
    if verification.get("verified_at") and verified_at is None:
        blockers.append({"source": "provider", "message": "provider verified_at must be a timezone-aware ISO-8601 timestamp"})
    elif verified_at and verified_at > datetime.now(timezone.utc):
        blockers.append({"source": "provider", "message": "provider verified_at must not be in the future"})
    if issued_at and verified_at and verified_at < issued_at:
        blockers.append({"source": "provider", "message": "provider verified_at must not precede issued_at"})
    expires_at = data.get("expires_at")
    if expires_at:
        try:
            expires = GOVERNANCE_CONTRACT.parse_time(expires_at)
            if expires is None:
                raise ValueError("timezone required")
            if expires <= datetime.now(timezone.utc):
                blockers.append({"source": "provider", "message": "provider attestation has expired"})
        except (TypeError, ValueError):
            blockers.append({"source": "provider", "message": "provider expires_at must be a timezone-aware ISO-8601 timestamp"})
    return {
        "schema": "codex-provider-attestation-validation-v1",
        "decision": "block" if blockers else "pass",
        "provider_type": data.get("provider_type", ""),
        "evidence_id": data.get("evidence_id", ""),
        "blockers": blockers,
    }


def checkpoint(
    artifact_dir: Path,
    name: str,
    evidence_refs: list[str] | None = None,
    provider_files: list[Path] | None = None,
) -> dict[str, Any]:
    verification = verify(artifact_dir)
    blockers = list(verification.get("blockers", []))
    required = CHECKPOINT_ACTIONS.get(name, set())
    actions = set(verification.get("actions", []))
    missing = sorted(required - actions)
    if missing:
        blockers.append({"source": "runtime_events", "message": "required runtime actions are missing", "actions": missing})
    session = read_json(runtime_paths(artifact_dir)[0])
    providers: list[dict[str, Any]] = []
    for path in provider_files or []:
        result = provider_attestation(read_json(path), expected_subject=str(session.get("doc_id") or ""))
        providers.append(result)
        blockers.extend(result.get("blockers", []))
    result = {
        "schema": CHECKPOINT_SCHEMA,
        "checkpoint": name,
        "session_id": session.get("session_id", ""),
        "runtime_root_digest": verification.get("event_root_digest", ""),
        "event_count": verification.get("event_count", 0),
        "event_refs": evidence_refs or [],
        "provider_attestations": providers,
        "decision": "block" if blockers else "pass",
        "blockers": blockers,
    }
    write_json(artifact_dir / "runtime/checkpoints" / f"{name}.json", result)
    bind_runtime_lineage(artifact_dir, name)
    result = read_json(artifact_dir / "runtime/checkpoints" / f"{name}.json")
    return result


def accepted_artifact(artifact_dir: Path, filename: str, decisions: set[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = read_json(artifact_dir / filename)
    if not data or str(data.get("decision") or data.get("status") or "") not in decisions:
        return data, [{"source": "runtime_evidence", "message": f"{filename} is missing or not accepted"}]
    if any(data.get(key) for key in ["blockers", "active_blockers", "missing_evidence"]):
        return data, [{"source": "runtime_evidence", "message": f"{filename} contains blockers"}]
    return data, []


def advance(
    artifact_dir: Path,
    name: str,
    provider_files: list[Path] | None = None,
) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    refs: list[str] = []
    if name == "post_implementation":
        implementation, issues = accepted_artifact(artifact_dir, "implementation_completion_gate.json", {"pass", "ready"})
        blockers.extend(issues)
        for filename, decisions in [
            ("post_change_implementation_report.json", {"pass", "warn"}),
            ("diff_impact.json", {"pass", "ready"}),
        ]:
            _, issues = accepted_artifact(artifact_dir, filename, decisions)
            blockers.extend(issues)
            refs.append(filename)
        refs.insert(0, "implementation_completion_gate.json")
        if not blockers:
            append_event(
                artifact_dir,
                "write_completed",
                "runtime-advance",
                target=",".join(str(item) for item in implementation.get("changed_files", [])),
                evidence_refs=refs,
            )
            append_event(artifact_dir, "implementation_validated", "runtime-advance", evidence_refs=refs)
    elif name == "pre_push":
        for filename, decisions in [
            ("harness/post_implementation.json", {"pass"}),
            ("post_implementation_traceability_matrix.json", {"pass", "warn"}),
            ("test_evidence_gate.json", {"pass", "ready"}),
            ("code_review_gate.json", {"pass", "approve", "approved"}),
        ]:
            _, issues = accepted_artifact(artifact_dir, filename, decisions)
            blockers.extend(issues)
            refs.append(filename)
        if not blockers:
            append_event(artifact_dir, "test_completed", "runtime-advance", evidence_refs=["test_evidence_gate.json"])
            append_event(artifact_dir, "review_completed", "runtime-advance", evidence_refs=["code_review_gate.json"])
            append_event(artifact_dir, "push_authorized", "runtime-advance", evidence_refs=refs)
    elif name == "release":
        _, issues = accepted_artifact(artifact_dir, "release_change.json", {"pass", "ready"})
        blockers.extend(issues)
        refs = ["release_change.json"]
        session = read_json(runtime_paths(artifact_dir)[0])
        provider_types = {
            str(read_json(path).get("provider_type") or "")
            for path in provider_files or []
            if provider_attestation(read_json(path), expected_subject=str(session.get("doc_id") or ""))["decision"] == "pass"
        }
        missing_provider_types = sorted(RELEASE_PROVIDER_TYPES - provider_types)
        if missing_provider_types:
            blockers.append(
                {
                    "source": "provider",
                    "message": "release requires verified attestations from all required provider types",
                    "provider_types": missing_provider_types,
                }
            )
        if not blockers:
            append_event(artifact_dir, "release_authorized", "runtime-advance", evidence_refs=refs)
            append_event(artifact_dir, "provider_verified", "runtime-advance", evidence_refs=[str(path) for path in provider_files or []])
    elif name == "close":
        _, issues = accepted_artifact(artifact_dir, "post_release_observation.json", {"pass", "ready"})
        blockers.extend(issues)
        refs = ["post_release_observation.json"]
        if not blockers:
            append_event(artifact_dir, "observation_completed", "runtime-advance", evidence_refs=refs)
            close(artifact_dir)
    else:
        blockers.append({"source": "checkpoint", "message": f"advance does not support {name}"})
    if blockers:
        return {"schema": CHECKPOINT_SCHEMA, "checkpoint": name, "decision": "block", "blockers": blockers}
    return checkpoint(artifact_dir, name, refs, provider_files)


def close(artifact_dir: Path) -> dict[str, Any]:
    session_path, _ = runtime_paths(artifact_dir)
    session = read_json(session_path)
    if session.get("status") != "active":
        return {"schema": SESSION_SCHEMA, "decision": "block", "blockers": [{"source": "session", "message": "active runtime session is required"}]}
    append_event(artifact_dir, "session_closed", "runtime")
    session = read_json(session_path)
    session["status"] = "closed"
    session["closed_at"] = now()
    write_json(session_path, session)
    return session


def main() -> int:
    parser = argparse.ArgumentParser(description="Control the Codex engineering Agent Runtime")
    sub = parser.add_subparsers(dest="command", required=True)
    start_cmd = sub.add_parser("start")
    start_cmd.add_argument("--artifact-dir", required=True)
    start_cmd.add_argument("--doc-id", required=True)
    start_cmd.add_argument("--profile", default="")
    start_cmd.add_argument("--repo", action="append", default=[])
    start_cmd.add_argument("--actor", default=os.environ.get("USER", "codex"))
    start_cmd.add_argument("--model", default="")
    event_cmd = sub.add_parser("import-event")
    event_cmd.add_argument("--artifact-dir", required=True)
    event_cmd.add_argument("--event", required=True)
    verify_cmd = sub.add_parser("verify")
    verify_cmd.add_argument("--artifact-dir", required=True)
    verify_cmd.add_argument("--expected-head", default="")
    auth_cmd = sub.add_parser("authorize")
    auth_cmd.add_argument("--artifact-dir", required=True)
    auth_cmd.add_argument("--action", required=True)
    auth_cmd.add_argument("--target", required=True)
    exec_cmd = sub.add_parser("exec")
    exec_cmd.add_argument("--artifact-dir", required=True)
    exec_cmd.add_argument("--timeout", type=int, default=300)
    exec_cmd.add_argument("args", nargs=argparse.REMAINDER)
    checkpoint_cmd = sub.add_parser("checkpoint")
    checkpoint_cmd.add_argument("--artifact-dir", required=True)
    checkpoint_cmd.add_argument("--name", choices=sorted(CHECKPOINT_ACTIONS), required=True)
    checkpoint_cmd.add_argument("--evidence-ref", action="append", default=[])
    checkpoint_cmd.add_argument("--provider", action="append", default=[])
    advance_cmd = sub.add_parser("advance")
    advance_cmd.add_argument("--artifact-dir", required=True)
    advance_cmd.add_argument("--name", choices=["post_implementation", "pre_push", "release", "close"], required=True)
    advance_cmd.add_argument("--provider", action="append", default=[])
    provider_cmd = sub.add_parser("verify-provider")
    provider_cmd.add_argument("--file", required=True)
    provider_cmd.add_argument("--subject", default="")
    provider_cmd.add_argument("--git-sha", default="")
    waiver_cmd = sub.add_parser("verify-waiver")
    waiver_cmd.add_argument("--file", required=True)
    waiver_cmd.add_argument("--subject", default="")
    waiver_cmd.add_argument("--gate", default="")
    close_cmd = sub.add_parser("close")
    close_cmd.add_argument("--artifact-dir", required=True)
    args = parser.parse_args()

    if args.command == "start":
        result = start(Path(args.artifact_dir), args.doc_id, args.profile, [Path(item) for item in args.repo], args.actor, args.model)
    elif args.command == "import-event":
        payload = read_json(Path(args.event))
        result = append_event(
            Path(args.artifact_dir),
            str(payload.get("action") or "external_event"),
            str(payload.get("tool") or "external"),
            actor=str(payload.get("actor") or "external-agent"),
            target=str(payload.get("target") or ""),
            decision=str(payload.get("decision") or "allow"),
            authorization=str(payload.get("authorization") or "external-attestation"),
            details=payload.get("details") if isinstance(payload.get("details"), dict) else {},
            evidence_refs=[str(item) for item in payload.get("evidence_refs", [])],
        )
    elif args.command == "verify":
        result = verify(Path(args.artifact_dir), args.expected_head)
    elif args.command == "authorize":
        result = authorize(Path(args.artifact_dir), args.action, args.target)
    elif args.command == "exec":
        command = list(args.args)
        if command and command[0] == "--":
            command = command[1:]
        result = execute(Path(args.artifact_dir), command, args.timeout)
    elif args.command == "checkpoint":
        result = checkpoint(Path(args.artifact_dir), args.name, args.evidence_ref, [Path(item) for item in args.provider])
    elif args.command == "advance":
        result = advance(Path(args.artifact_dir), args.name, [Path(item) for item in args.provider])
    elif args.command == "verify-provider":
        result = provider_attestation(read_json(Path(args.file)), args.subject, args.git_sha)
    elif args.command == "verify-waiver":
        result = GOVERNANCE_CONTRACT.validate_waiver(read_json(Path(args.file)), args.subject, args.gate)
    else:
        result = close(Path(args.artifact_dir))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("decision") in {"pass", "ready", "allow"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
