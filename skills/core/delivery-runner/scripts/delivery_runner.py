#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
FALLBACK_ORDER = [
    ("spec", "spec.json"),
    ("technical_design", "technical_design.json"),
    ("architecture_design", "architecture_design.json"),
    ("test_design", "test_design.json"),
    ("delivery_plan", "delivery_plan.json"),
    ("delivery_plan_review", "delivery_plan_review.json"),
    ("design_review", "design_architecture_review.json"),
    ("docs_quality", "docs_quality.json"),
    ("git", "git_worktree_evidence.json"),
    ("edit_permit", "edit_permit.json"),
    ("implementation", "implementation_completion_gate.json"),
    ("post_change", "post_change_implementation_report.json"),
    ("review", "code_review_gate.json"),
    ("test", "test_evidence_gate.json"),
    ("environment", "environment_promotion.json"),
    ("uat", "uat_acceptance.json"),
    ("release_change", "release_change.json"),
    ("release", "release_gate.json"),
    ("post_release", "post_release_observation.json"),
]
FALLBACK_IMPLEMENTATION_REQUIRED = ["spec", "technical_design", "architecture_design", "test_design", "delivery_plan", "delivery_plan_review", "design_review", "docs_quality", "git", "edit_permit"]
FALLBACK_RELEASE_REQUIRED = ["implementation", "post_change", "review", "test", "environment", "uat", "release_change", "release"]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def is_pass(data: dict[str, Any]) -> bool:
    decision = data.get("decision") or data.get("status")
    if decision in {"pass", "ready", "approve", "approved", "go"}:
        return True
    if data.get("pass") is True:
        return True
    return bool(data) and not any(data.get(key) for key in ["blockers", "active_blockers", "missing_evidence"])


def stage_is_pass(stage: dict[str, Any], data: dict[str, Any]) -> bool:
    accepted = stage.get("accepted_decisions", [])
    if isinstance(accepted, list) and accepted:
        decision = str(data.get("decision") or data.get("status") or "")
        return bool(data) and decision in {str(item) for item in accepted}
    return is_pass(data)


def docs_readiness(artifact_dir: Path) -> dict[str, Any]:
    auto_summary = load_json(artifact_dir / "auto_run_summary.json")
    status = auto_summary.get("docs_readiness") if isinstance(auto_summary.get("docs_readiness"), dict) else {}
    doc_id = str(auto_summary.get("doc_id") or load_json(artifact_dir / "delivery_plan.json").get("doc_id") or "")
    docs_root_value = str(status.get("docs_root") or "")
    blockers: list[dict[str, str]] = []
    if not docs_root_value:
        blockers.append({"source": "docs_root", "message": "delivery docs repository root is required before implementation"})
    manifest = ""
    if docs_root_value:
        docs_root = Path(docs_root_value)
        manifest = str(status.get("manifest") or docs_root / "indexes" / f"{doc_id}.manifest.json")
        if not docs_root.exists():
            blockers.append({"source": "docs_root", "message": "delivery docs repository root does not exist"})
        if doc_id and not Path(manifest).exists():
            blockers.append({"source": "docs_manifest", "message": "delivery docs manifest is missing"})
        if not (docs_root / ".git").exists():
            blockers.append({"source": "docs_git", "message": "delivery docs root must be a git repository"})
    return {
        "decision": "pass" if not blockers else "block",
        "doc_id": doc_id,
        "docs_root": docs_root_value,
        "manifest": manifest,
        "blockers": blockers,
    }


def git_edit_readiness(artifact_dir: Path, git_data: dict[str, Any]) -> dict[str, Any]:
    summary = load_json(artifact_dir / "git_plan_baseline_summary.json")
    blockers: list[dict[str, Any]] = []
    evidence_items: list[dict[str, Any]] = []
    if summary:
        results = summary.get("results", [])
        if isinstance(results, list):
            evidence_items = [item for item in results if isinstance(item, dict)]
        if summary.get("decision") != "ready":
            blockers.append({"source": "git_plan_baseline_summary", "message": "git plan baseline summary is not ready"})
    elif git_data:
        evidence_items = [git_data]
    else:
        blockers.append({"source": "git", "message": "git evidence is missing"})

    for idx, item in enumerate(evidence_items):
        label = str(item.get("repo_name") or item.get("repo") or f"repo[{idx}]")
        if item.get("decision") != "ready":
            blockers.append({"source": "git", "message": f"{label}: git evidence is not ready"})
        if item.get("fetched") is not True:
            blockers.append({"source": "git", "message": f"{label}: git fetch evidence is missing"})
        if item.get("base_updated") is not True:
            blockers.append({"source": "git", "message": f"{label}: git pull --ff-only evidence is missing"})
    return {
        "decision": "ready" if not blockers else "blocked",
        "summary_present": bool(summary),
        "evidence_count": len(evidence_items),
        "blockers": blockers,
    }


def load_auto_runner_module() -> Any:
    path = ROOT / "skills/core/auto-runner/scripts/auto_runner.py"
    spec = importlib.util.spec_from_file_location("auto_runner_profiles", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def load_stage_registry() -> list[dict[str, Any]]:
    try:
        auto_runner = load_auto_runner_module()
        data = auto_runner.load_restricted_yaml(ROOT / "config/workflow-stages.example.yaml")
    except Exception:
        data = {}
    stages = data.get("stages", []) if isinstance(data, dict) else []
    if not isinstance(stages, list) or not stages:
        return [
            {"name": name, "artifact": filename, "implementation_required": name in FALLBACK_IMPLEMENTATION_REQUIRED, "release_required": name in FALLBACK_RELEASE_REQUIRED}
            for name, filename in FALLBACK_ORDER
        ]
    normalized: list[dict[str, Any]] = []
    for item in stages:
        if isinstance(item, dict) and item.get("name") and item.get("artifact"):
            normalized.append(item)
    return normalized


def selected_profile(artifact_dir: Path, profile_name: str | None = None) -> dict[str, Any]:
    auto_summary = load_json(artifact_dir / "auto_run_summary.json")
    if isinstance(auto_summary.get("workflow_profile"), dict) and not profile_name:
        return auto_summary["workflow_profile"]
    try:
        auto_runner = load_auto_runner_module()
        profiles = auto_runner.load_profile_registry()
        if profile_name and profile_name in profiles:
            return profiles[profile_name]
        spec = load_json(artifact_dir / "spec.json")
        return auto_runner.select_workflow_profile(spec, (artifact_dir / "project_understanding").exists(), profile_name)
    except Exception:
        return {"name": profile_name or "", "expected_artifacts": [], "required_skills": []}


def missing_profile_artifacts(profile: dict[str, Any], artifact_dir: Path) -> list[str]:
    items = profile.get("expected_artifacts", [])
    if not isinstance(items, list):
        items = [items]
    return [str(item) for item in items if not (artifact_dir / str(item)).exists()]


def nested_value(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def profile_gate_blockers(profile: dict[str, Any], artifact_dir: Path) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    gates = profile.get("required_gate_artifacts", [])
    if not isinstance(gates, list):
        return blockers
    for gate in gates:
        if not isinstance(gate, dict):
            blockers.append({"source": "workflow_profile", "message": "required_gate_artifacts entries must be objects"})
            continue
        artifact_name = str(gate.get("artifact") or "")
        if not artifact_name:
            blockers.append({"source": "workflow_profile", "message": "required gate artifact is missing artifact path"})
            continue
        path = artifact_dir / artifact_name
        data = load_json(path)
        if not data:
            blockers.append({"source": f"profile_gate.{artifact_name}", "message": "required gate artifact is missing or invalid"})
            continue
        accepted = {str(item) for item in gate.get("accepted_decisions", [])} if isinstance(gate.get("accepted_decisions"), list) else set()
        decision = str(data.get("decision") or data.get("status") or "")
        if accepted and not decision:
            blockers.append({"source": f"profile_gate.{artifact_name}", "message": "decision/status is missing", "accepted_decisions": sorted(accepted)})
        elif accepted and decision not in accepted:
            blockers.append({"source": f"profile_gate.{artifact_name}", "message": f"decision {decision} not accepted", "accepted_decisions": sorted(accepted)})
        readiness_path = str(gate.get("readiness_path") or "")
        if readiness_path:
            expected = gate.get("readiness_value")
            actual = nested_value(data, readiness_path)
            if actual != expected:
                blockers.append({"source": f"profile_gate.{artifact_name}", "message": f"{readiness_path} is not {expected}", "actual": actual})
    return blockers


def profile_next_actions(profile: dict[str, Any], artifact_dir: Path) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    gate_blockers = profile_gate_blockers(profile, artifact_dir)
    command_by_artifact = {
        str(step.get("artifact")): " ".join(str(part).replace("{artifact_dir}", str(artifact_dir)) for part in step.get("command", []))
        for step in profile.get("artifact_steps", [])
        if isinstance(step, dict) and step.get("artifact") and isinstance(step.get("command"), list)
    }
    for item in gate_blockers:
        source = str(item.get("source") or "")
        artifact = source.replace("profile_gate.", "", 1) if source.startswith("profile_gate.") else ""
        next_command = command_by_artifact.get(artifact, "")
        actions.append({
            "artifact": artifact,
            "blocker": item.get("message", ""),
            "accepted_decisions": item.get("accepted_decisions", []),
            "next_command": next_command,
            "action_type": "generate_artifact" if next_command else "fix_blocker",
        })
    return actions


def classify_next_action(can_implement: bool, can_release: bool, blockers: list[dict[str, Any]], next_stage: str) -> str:
    if can_release:
        return "ready_to_release"
    if can_implement:
        return "ready_to_implement"
    if blockers:
        return "fix_blocker"
    if next_stage in {"test", "review", "release", "environment", "uat", "release_change"}:
        return "collect_evidence"
    return "generate_artifact"


def primary_next_action(
    next_action_type: str,
    next_stage: str,
    next_artifact: str,
    next_command: str,
    blockers: list[dict[str, Any]],
    actions: list[dict[str, Any]],
) -> dict[str, Any]:
    if next_action_type in {"ready_to_implement", "ready_to_release"}:
        return {"action_type": next_action_type, "stage": next_stage, "summary": next_action_type.replace("_", " "), "command": ""}
    if actions:
        first = next((item for item in actions if item.get("artifact") == next_artifact), actions[0])
        return {
            "action_type": first.get("action_type") or next_action_type,
            "stage": next_stage,
            "artifact": first.get("artifact", ""),
            "summary": first.get("blocker", ""),
            "command": first.get("next_command") or next_command,
        }
    if blockers:
        first_blocker = blockers[0]
        return {
            "action_type": "fix_blocker",
            "stage": next_stage,
            "summary": f"{first_blocker.get('source', 'unknown')}: {first_blocker.get('message', '')}",
            "command": next_command,
        }
    return {"action_type": next_action_type, "stage": next_stage, "summary": "run next workflow command", "command": next_command}


def inspect(artifact_dir: Path, profile_name: str | None = None) -> dict[str, Any]:
    profile = selected_profile(artifact_dir, profile_name)
    profile_skills = {str(item) for item in profile.get("required_skills", [])} if isinstance(profile.get("required_skills"), list) else set()
    stages = [
        stage for stage in load_stage_registry()
        if not stage.get("conditional_skill") or str(stage.get("conditional_skill")) in profile_skills
    ]
    if profile.get("profile_stage_mode") == "release_only":
        stages = [stage for stage in stages if stage.get("release_required")]
    order = [(str(stage["name"]), str(stage["artifact"])) for stage in stages]
    artifacts: dict[str, dict[str, Any]] = {name: load_json(artifact_dir / filename) for name, filename in order}
    state = load_json(artifact_dir / "delivery_state.json")
    profile_missing = missing_profile_artifacts(profile, artifact_dir)
    completed = [str(stage["name"]) for stage in stages if stage_is_pass(stage, artifacts[str(stage["name"])])]
    missing = [name for name, _ in order if not artifacts[name]]
    blockers: list[dict[str, Any]] = []
    for name, data in artifacts.items():
        if not data:
            continue
        for key in ["blockers", "active_blockers", "missing_evidence"]:
            if data.get(key):
                blockers.append({"source": name, "message": f"{key} present", "count": len(data.get(key) if isinstance(data.get(key), list) else [data.get(key)])})
        if data.get("decision") in {"block", "blocked", "no_go", "fail", "failed", "request_changes", "needs_revision"}:
            blockers.append({"source": name, "message": f"blocking decision: {data.get('decision')}"})
    if state.get("blockers"):
        blockers.append({"source": "delivery_state", "message": "delivery state has blockers", "count": len(state.get("blockers", []))})
    docs_status = docs_readiness(artifact_dir)
    if docs_status.get("decision") != "pass":
        blockers.extend(docs_status.get("blockers", []))
    docs_quality = artifacts.get("docs_quality", {})
    if docs_quality and str(docs_quality.get("decision") or "") not in {"pass", "ready"}:
        blockers.append({"source": "docs_quality", "message": "human documentation quality decision is not pass/ready"})
    git_status = git_edit_readiness(artifact_dir, artifacts.get("git", {}))
    if git_status.get("decision") != "ready":
        blockers.extend(git_status.get("blockers", []))
    blockers.extend(profile_gate_blockers(profile, artifact_dir))
    next_required_actions = profile_next_actions(profile, artifact_dir)

    next_stage = "done"
    for name, _ in order:
        if name not in completed:
            next_stage = name
            break
    implementation_required = [str(stage["name"]) for stage in stages if stage.get("implementation_required")]
    if not implementation_required and profile.get("profile_stage_mode") != "release_only":
        implementation_required = FALLBACK_IMPLEMENTATION_REQUIRED
    release_required = [str(stage["name"]) for stage in stages if stage.get("release_required")]
    if not release_required:
        release_required = FALLBACK_RELEASE_REQUIRED
    implementation_missing = [name for name in implementation_required if name not in completed]
    release_missing = [name for name in release_required if name not in completed]
    can_implement = not implementation_missing and not blockers
    can_release = not release_missing and not blockers
    commands = {str(stage["name"]): str(stage.get("next_command") or "") for stage in stages}
    next_command = commands.get(next_stage, "Run the gate for the next missing stage and attach evidence.")
    artifact_by_stage = {name: filename for name, filename in order}
    next_artifact = artifact_by_stage.get(next_stage, "")
    next_action_type = classify_next_action(can_implement, can_release, blockers, next_stage)
    primary_action = primary_next_action(next_action_type, next_stage, next_artifact, next_command, blockers, next_required_actions)
    return {
        "schema": "codex-delivery-runner-status-v1",
        "artifact_dir": str(artifact_dir),
        "state_present": bool(state),
        "completed_stages": completed,
        "missing_artifacts": missing,
        "blockers": blockers,
        "workflow_profile": profile,
        "docs_readiness": docs_status,
        "git_edit_readiness": git_status,
        "profile_missing_artifacts": profile_missing,
        "stage_registry": "config/workflow-stages.example.yaml",
        "next_profile_command": profile.get("next_safe_command", ""),
        "next_required_actions": next_required_actions,
        "next_release_actions": next_required_actions if profile.get("name") == "release_readiness" else [],
        "next_stage": next_stage,
        "next_action_type": next_action_type,
        "primary_next_action": primary_action,
        "next_command": next_command,
        "can_implement": can_implement,
        "can_release": can_release,
        "implementation_missing": implementation_missing,
        "release_missing": release_missing,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect delivery workflow status")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_inspect = sub.add_parser("inspect")
    p_inspect.add_argument("--artifact-dir", required=True)
    p_inspect.add_argument("--profile")
    p_inspect.add_argument("--out")
    args = parser.parse_args()
    result = inspect(Path(args.artifact_dir), args.profile)
    if args.out:
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["blockers"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
