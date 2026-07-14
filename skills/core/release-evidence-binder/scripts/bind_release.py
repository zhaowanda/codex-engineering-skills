#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-release-gate-v1"
BLOCK_DECISIONS = {"block", "blocked", "no_go", "fail", "failed", "request_changes", "needs_refactor"}
WARN_DECISIONS = {"conditional_go", "needs_review", "needs_revision", "needs_evidence", "warning"}
COMMAND_HINTS = {
    "implementation_completion_gate": "python3 skills/core/implementation-completion-gate/scripts/implementation_complete.py --artifact-dir artifacts/REQ-001 --out artifacts/REQ-001/implementation_completion_gate.json",
    "post_change_implementation_report": "python3 skills/core/post-change-skill-sync/scripts/sync_after_change.py --repo /path/to/repo --artifact-dir artifacts/REQ-001 --doc-id REQ-001",
    "code_review_gate": "python3 skills/core/code-review-gate/scripts/review_gate.py --artifact-dir artifacts/REQ-001 --out artifacts/REQ-001/code_review_gate.json",
    "test_evidence_gate": "python3 skills/core/test-evidence-gate/scripts/test_evidence_gate.py --artifact-dir artifacts/REQ-001 --out artifacts/REQ-001/test_evidence_gate.json",
    "ci_execution_evidence": "attach ci_execution_evidence.json with executed command results",
    "environment_promotion": "python3 skills/core/environment-promotion-governor/scripts/environment_promotion.py template --out artifacts/REQ-001/environment_promotion.json",
    "uat_acceptance": "python3 skills/core/uat-acceptance-governor/scripts/uat_acceptance.py template --out artifacts/REQ-001/uat_acceptance.json",
    "release_change": "python3 skills/core/release-change-governor/scripts/release_change.py template --out artifacts/REQ-001/release_change.json",
    "delivery_plan": "python3 skills/templates/delivery-plan-templates/scripts/render_delivery_plan.py --doc-id REQ-001 --technical-design artifacts/REQ-001/technical_design.json --architecture-design artifacts/REQ-001/architecture_design.json --out artifacts/REQ-001/delivery_plan.json",
    "design_architecture_review": "python3 skills/core/design-architecture-reviewer/scripts/design_arch_review.py review --technical-design artifacts/REQ-001/technical_design.json --architecture-design artifacts/REQ-001/architecture_design.json --out artifacts/REQ-001/design_architecture_review.json",
    "write_guard_audit": "python3 skills/core/workspace-write-guard/scripts/write_guard.py audit --permit artifacts/REQ-001/edit_permit.json --repo /path/to/repo --out artifacts/REQ-001/write_guard_audit.json",
    "evidence_gap_summary": "python3 skills/core/evidence-auto-collector/scripts/evidence_collect.py --diff-impact artifacts/REQ-001/diff_impact.json --artifact-dir artifacts/REQ-001",
}
FOLLOWUP_REQUIRED_ARTIFACTS = {
    "frontend_acceptance": ["frontend_acceptance"],
    "configuration": ["configuration_readiness"],
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def load_policy(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(text)
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def decision_of(data: dict[str, Any]) -> str:
    for key in ["decision", "review_decision", "status"]:
        value = data.get(key)
        if isinstance(value, str):
            return value
    if data.get("pass") is True:
        return "pass"
    if data.get("pass") is False:
        return "fail"
    return ""


def has_blocker_findings(data: dict[str, Any]) -> bool:
    for key in ["blockers", "active_blockers", "release_blockers", "failed_cases", "untested_blockers", "failed_commands"]:
        if as_list(data.get(key)):
            return True
    for item in as_list(data.get("findings")):
        if not isinstance(item, dict):
            continue
        if item.get("severity") in {"blocker", "high"} and item.get("status", "open") not in {"closed", "resolved", "accepted_risk", "waived"}:
            return True
    return False


def has_warning_findings(data: dict[str, Any]) -> bool:
    warning_keys = ["warnings", "active_concerns", "accepted_risks", "missing_evidence", "unknown_commands", "untested_non_blockers"]
    return any(as_list(data.get(key)) for key in warning_keys)


def collect_artifacts(artifact_dir: Path) -> dict[str, dict[str, Any]]:
    names = [
        "delivery_plan",
        "design_architecture_review",
        "implementation_completion_gate",
        "post_change_implementation_report",
        "write_guard_audit",
        "code_review_gate",
        "test_evidence_gate",
        "ci_execution_evidence",
        "frontend_acceptance",
        "configuration_readiness",
        "environment_promotion",
        "uat_acceptance",
        "release_change",
        "data_security_review",
        "performance_diff_review",
        "performance_design_review",
        "evidence_gap_summary",
        "post_release_checks",
        "post_release_observation",
    ]
    return {name: load_json(artifact_dir / f"{name}.json") for name in names}


def required_for(change_type: str) -> list[str]:
    if change_type == "docs":
        return ["delivery_plan", "code_review_gate"]
    if change_type == "config":
        return [
            "delivery_plan",
            "design_architecture_review",
            "implementation_completion_gate",
            "post_change_implementation_report",
            "write_guard_audit",
            "code_review_gate",
            "test_evidence_gate",
            "ci_execution_evidence",
            "configuration_readiness",
            "environment_promotion",
            "uat_acceptance",
            "release_change",
        ]
    return [
        "delivery_plan",
        "design_architecture_review",
        "implementation_completion_gate",
        "post_change_implementation_report",
        "write_guard_audit",
        "code_review_gate",
        "test_evidence_gate",
        "ci_execution_evidence",
        "environment_promotion",
        "uat_acceptance",
        "release_change",
    ]


def rollback_items(evidence: dict[str, dict[str, Any]]) -> list[Any]:
    result: list[Any] = []
    plan = evidence.get("delivery_plan", {})
    result.extend(as_list(plan.get("rollback_order")))
    result.extend(as_list(plan.get("rollback_plan")))
    release_change = evidence.get("release_change", {})
    result.extend(as_list(release_change.get("rollback_plan")))
    post_release = evidence.get("post_release_checks", {})
    result.extend(as_list(post_release.get("rollback_triggers")))
    return result


def post_release_items(evidence: dict[str, dict[str, Any]]) -> list[Any]:
    result: list[Any] = []
    plan = evidence.get("delivery_plan", {})
    result.extend(as_list(plan.get("post_release_checks")))
    release_change = evidence.get("release_change", {})
    result.extend(as_list(release_change.get("post_release_checks")))
    post_release = evidence.get("post_release_checks", {})
    result.extend(as_list(post_release.get("checks")))
    return result


def implementation_followup_gaps(evidence: dict[str, dict[str, Any]], change_type: str) -> list[dict[str, Any]]:
    if change_type == "docs":
        return []
    implementation = evidence.get("implementation_completion_gate", {})
    followups = [item for item in as_list(implementation.get("evidence_followups")) if isinstance(item, dict)]
    if not followups:
        return []
    gaps: list[dict[str, Any]] = []
    evidence_gap = evidence.get("evidence_gap_summary", {})
    followup_surfaces = sorted({str(item.get("surface")) for item in followups if item.get("surface")})
    if not evidence_gap:
        gaps.append({"source": "evidence_gap_summary", "message": "evidence_gap_summary is required to close implementation evidence follow-ups"})
    elif decision_of(evidence_gap) in BLOCK_DECISIONS or as_list(evidence_gap.get("missing_evidence")) or as_list(evidence_gap.get("blockers")):
        gaps.append({"source": "evidence_gap_summary", "message": "implementation evidence follow-ups still have missing or blocking evidence"})
    elif followup_surfaces:
        covered_surfaces = {
            str(item.get("surface"))
            for item in as_list(evidence_gap.get("implementation_followup_requirements"))
            if isinstance(item, dict) and item.get("surface")
        }
        missing_surfaces = [surface for surface in followup_surfaces if surface not in covered_surfaces]
        if missing_surfaces:
            gaps.append({"source": "evidence_gap_summary", "message": "evidence_gap_summary does not cover implementation evidence follow-ups", "missing_surfaces": missing_surfaces})
    for item in followups:
        surface = str(item.get("surface") or "")
        for artifact in FOLLOWUP_REQUIRED_ARTIFACTS.get(surface, []):
            data = evidence.get(artifact, {})
            if not data:
                gaps.append({"source": artifact, "message": f"{artifact}.json is required for implementation follow-up surface: {surface}"})
            elif decision_of(data) in BLOCK_DECISIONS or has_blocker_findings(data):
                gaps.append({"source": artifact, "message": f"{artifact}.json blocks implementation follow-up surface: {surface}"})
    return gaps


def release_policy_gaps(evidence: dict[str, dict[str, Any]], policy: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    policy = policy or {}
    required_envs = [str(item) for item in as_list(policy.get("required_environments"))] or ["pre", "prod"]
    env_required_fields = [str(item) for item in as_list(policy.get("environment_required_fields"))] or ["entry_criteria", "exit_criteria", "validation_evidence", "approver"]
    release_required_fields = [str(item) for item in as_list(policy.get("release_change_required_fields"))] or ["release_window", "approvers", "rollback_owner"]
    environment_aliases = policy.get("environment_aliases") if isinstance(policy.get("environment_aliases"), dict) else {}
    approver_roles = [str(item) for item in as_list(policy.get("required_approver_roles"))]
    approver_required_fields = [str(item) for item in as_list(policy.get("approver_required_fields"))]
    minimum_distinct_approvers = int(policy.get("minimum_distinct_approvers") or 0)
    separation_of_duties = policy.get("separation_of_duties") is True
    ticket_fields = [str(item) for item in as_list(policy.get("required_ticket_fields"))]
    observation_metrics = [str(item) for item in as_list(policy.get("required_observation_metrics"))]
    audit_fields = [str(item) for item in as_list(policy.get("required_audit_fields"))]
    integration_evidence = [str(item) for item in as_list(policy.get("required_integration_evidence"))]
    require_prod_rollback = policy.get("require_prod_rollback_ready", True) is not False
    environment = evidence.get("environment_promotion", {})
    envs = environment.get("environments") if isinstance(environment.get("environments"), list) else []
    by_name = {item.get("name"): item for item in envs if isinstance(item, dict)}
    for env in required_envs:
        aliases = [env, *[str(item) for item in as_list(environment_aliases.get(env))]]
        item = next((by_name.get(alias) for alias in aliases if by_name.get(alias)), None)
        if not item:
            gaps.append({"source": "environment_promotion", "message": f"{env} environment policy is required"})
            continue
        for key in env_required_fields:
            value = item.get(key)
            missing = not as_list(value) if isinstance(value, list) else not value
            if missing:
                gaps.append({"source": "environment_promotion", "message": f"{env}.{key} is required"})
        if env == "prod" and require_prod_rollback and item.get("rollback_ready") is not True:
            gaps.append({"source": "environment_promotion", "message": "prod.rollback_ready must be true"})
    release_change = evidence.get("release_change", {})
    window = release_change.get("release_window") if isinstance(release_change.get("release_window"), dict) else {}
    if "release_window" in release_required_fields and not all(window.get(key) for key in ["start", "end", "timezone"]):
        gaps.append({"source": "release_change", "message": "release_window start/end/timezone are required"})
    for key in release_required_fields:
        if key == "release_window":
            continue
        value = release_change.get(key)
        missing = not as_list(value) if isinstance(value, list) else not value
        if missing:
            message = "release approvers are required" if key == "approvers" else f"{key} is required"
            gaps.append({"source": "release_change", "message": message})
    approvers = as_list(release_change.get("approvers"))
    approver_role_values = set()
    approver_identities = set()
    for item in approvers:
        if isinstance(item, dict):
            approver_role_values.add(str(item.get("role") or item.get("type") or item.get("name") or ""))
            identity = str(item.get("identity") or item.get("name") or "").strip()
            if identity:
                approver_identities.add(identity)
            for field in approver_required_fields:
                if not item.get(field):
                    gaps.append({"source": "release_change", "message": f"approver.{field} is required"})
        elif isinstance(item, str):
            approver_role_values.add(item)
            approver_identities.add(item)
            if approver_required_fields:
                gaps.append({"source": "release_change", "message": "approver must be structured under the active release policy"})
    missing_roles = [role for role in approver_roles if role not in approver_role_values]
    for role in missing_roles:
        gaps.append({"source": "release_change", "message": f"required approver role missing: {role}"})
    if minimum_distinct_approvers and len(approver_identities) < minimum_distinct_approvers:
        gaps.append({"source": "release_change", "message": f"at least {minimum_distinct_approvers} distinct approvers are required"})
    if separation_of_duties:
        implementers = {
            str(item.get("identity") or item.get("name") or "").strip() if isinstance(item, dict) else str(item).strip()
            for item in as_list(release_change.get("implementers"))
            if item
        }
        if not implementers:
            gaps.append({"source": "release_change", "message": "implementers are required for separation-of-duties validation"})
        overlap = sorted(identity for identity in approver_identities & implementers if identity)
        if overlap:
            gaps.append({"source": "release_change", "message": "implementers must not approve their own release", "identities": overlap})
    ticket = release_change.get("ticket") if isinstance(release_change.get("ticket"), dict) else {}
    for field in ticket_fields:
        if not ticket.get(field):
            gaps.append({"source": "release_change", "message": f"ticket.{field} is required"})
    audit = release_change.get("approval_audit") if isinstance(release_change.get("approval_audit"), dict) else {}
    for field in audit_fields:
        if not audit.get(field):
            gaps.append({"source": "release_change", "message": f"approval_audit.{field} is required"})
    integrations = release_change.get("integration_evidence") if isinstance(release_change.get("integration_evidence"), dict) else {}
    for integration in integration_evidence:
        item = integrations.get(integration) if isinstance(integrations.get(integration), dict) else {}
        if not item.get("provider") or not (item.get("evidence_id") or item.get("url")):
            gaps.append({"source": "release_change", "message": f"integration_evidence.{integration} requires provider and evidence_id/url"})
    post_release = evidence.get("post_release_checks", {})
    metric_sources = []
    metric_sources.extend(as_list(release_change.get("observation_metrics")))
    metric_sources.extend(as_list(post_release.get("observation_metrics")))
    metric_sources.extend(as_list(post_release.get("checks")))
    rendered_metrics = set()
    for item in metric_sources:
        if isinstance(item, dict):
            rendered_metrics.add(str(item.get("name") or ""))
        elif isinstance(item, str):
            rendered_metrics.add(item)
    for metric in observation_metrics:
        if metric not in rendered_metrics:
            gaps.append({"source": "post_release_checks", "message": f"observation metric required: {metric}"})
    return gaps


def bind(artifact_dir: Path, change_type: str = "code", policy: dict[str, Any] | None = None) -> dict[str, Any]:
    evidence = collect_artifacts(artifact_dir)
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    evidence_summary: list[dict[str, Any]] = []
    source_files: list[str] = []

    required = required_for(change_type)
    for name in required:
        data = evidence.get(name, {})
        if not data:
            blockers.append({"source": name, "message": f"{name}.json is required for {change_type} release"})
            continue
        source_files.append(f"{name}.json")

    for name, data in evidence.items():
        if not data:
            continue
        if f"{name}.json" not in source_files:
            source_files.append(f"{name}.json")
        decision = decision_of(data)
        area_summary = {
            "area": name,
            "decision": decision,
            "has_blockers": has_blocker_findings(data),
            "has_warnings": has_warning_findings(data),
        }
        evidence_summary.append(area_summary)
        if decision in BLOCK_DECISIONS or has_blocker_findings(data):
            blockers.append({"source": name, "message": f"{name} is blocking release", "decision": decision})
        elif decision in WARN_DECISIONS or has_warning_findings(data):
            warnings.append({"source": name, "message": f"{name} has warnings or accepted risks", "decision": decision})

    ci = evidence.get("ci_execution_evidence", {})
    if ci:
        if as_list(ci.get("failed_commands")) or ci.get("mode") == "plan":
            blockers.append({"source": "ci_execution_evidence", "message": "CI failed or was plan-only"})
        if as_list(ci.get("unknown_commands")):
            warnings.append({"source": "ci_execution_evidence", "message": "CI has unknown command results"})

    frontend = evidence.get("frontend_acceptance", {})
    if frontend and frontend.get("pass") is not True and decision_of(frontend) not in {"pass", "ready"}:
        blockers.append({"source": "frontend_acceptance", "message": "frontend acceptance did not pass"})

    rollback = rollback_items(evidence)
    post_release = post_release_items(evidence)
    if change_type != "docs" and not rollback:
        blockers.append({"source": "rollback", "message": "rollback plan is required"})
    if change_type != "docs" and not post_release:
        blockers.append({"source": "post_release_checks", "message": "post-release checks are required"})
    if change_type != "docs":
        blockers.extend(release_policy_gaps(evidence, policy=policy))
        blockers.extend(implementation_followup_gaps(evidence, change_type))

    missing_evidence = [item["source"] for item in blockers if "is required" in item.get("message", "")]
    next_required_actions = [
        {
            "artifact": f"{name}.json",
            "reason": f"{name}.json is required for {change_type} release",
            "next_command": COMMAND_HINTS.get(name, f"create artifacts/REQ-001/{name}.json with real evidence"),
        }
        for name in sorted(set(missing_evidence))
    ]
    if blockers:
        decision = "no_go"
    elif warnings:
        decision = "conditional_go"
    else:
        decision = "go"
    score = max(0, 100 - len(blockers) * 20 - len(warnings) * 5)
    return {
        "schema": SCHEMA,
        "decision": decision,
        "score": score,
        "change_type": change_type,
        "evidence_summary": evidence_summary,
        "blockers": blockers,
        "warnings": warnings,
        "required_evidence": required,
        "missing_evidence": sorted(set(missing_evidence)),
        "next_required_actions": next_required_actions,
        "rollback_plan": rollback,
        "post_release_checks": post_release,
        "source_files": sorted(set(source_files)),
        "release_policy": policy or {},
        "implementation_evidence_followups": as_list(evidence.get("implementation_completion_gate", {}).get("evidence_followups")),
        "next_action": "Do not release. Fix blockers and re-bind evidence." if blockers else "Proceed to release approval/change process.",
    }


def validate(data: dict[str, Any]) -> tuple[bool, list[str]]:
    issues: list[str] = []
    required = ["schema", "decision", "score", "evidence_summary", "blockers", "warnings", "required_evidence", "missing_evidence", "next_required_actions", "rollback_plan", "post_release_checks", "source_files"]
    for key in required:
        if key not in data:
            issues.append(f"missing {key}")
    if data.get("schema") != SCHEMA:
        issues.append(f"schema must be {SCHEMA}")
    if data.get("decision") not in {"go", "conditional_go", "no_go"}:
        issues.append("decision must be go/conditional_go/no_go")
    if data.get("decision") == "go" and (data.get("blockers") or data.get("warnings") or data.get("missing_evidence")):
        issues.append("go is not allowed with blockers, warnings, or missing evidence")
    if data.get("decision") == "no_go" and not data.get("blockers"):
        issues.append("no_go must include blockers")
    return not issues, issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Bind release evidence into a final gate")
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--change-type", choices=["code", "config", "docs"], default="code")
    parser.add_argument("--policy", help="Optional release policy YAML/JSON file")
    parser.add_argument("--out")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    result = bind(Path(args.artifact_dir), change_type=args.change_type, policy=load_policy(Path(args.policy) if args.policy else None))
    if args.out:
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.validate:
        valid, issues = validate(result)
        if not valid:
            print(json.dumps({"schema": "codex-release-gate-validation-v1", "valid": valid, "issues": issues}, ensure_ascii=False, indent=2))
            return 1
    return 0 if result["decision"] in {"go", "conditional_go"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
