#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
SCHEMA = "codex-auto-runner-summary-v1"
PROFILE_REGISTRY = ROOT / "config/workflow-profiles.example.yaml"


def slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-")
    return text or "requirement"


def default_doc_id(input_path: Path) -> str:
    return f"REQ-{slug(input_path.stem)}"


def default_title(input_path: Path) -> str:
    words = re.sub(r"[_-]+", " ", input_path.stem).strip()
    return words.title() if words else "Requirement"


def default_out(doc_id: str) -> Path:
    return Path("/tmp/codex-auto") / doc_id


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def load_docs_config_module() -> Any:
    candidates = [
        Path(__file__).resolve().parents[1] / "scripts/docs_config.py",
        ROOT / "scripts/docs_config.py",
        ROOT.parent / "scripts/docs_config.py",
    ]
    path = next((candidate for candidate in candidates if candidate.exists()), candidates[0])
    spec = importlib.util.spec_from_file_location("docs_config", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def load_docs_governor_module() -> Any:
    candidates = [
        Path(__file__).resolve().parents[2] / "docs-governor/scripts/docs_governor.py",
        ROOT / "skills/core/docs-governor/scripts/docs_governor.py",
    ]
    path = next((candidate for candidate in candidates if candidate.exists()), candidates[0])
    spec = importlib.util.spec_from_file_location("docs_governor", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def default_docs_root() -> Path | None:
    try:
        return load_docs_config_module().configured_docs_root(ROOT)
    except Exception:
        return None


def docs_readiness(docs_root: Path | None, doc_id: str) -> dict[str, Any]:
    if not docs_root:
        return {
            "schema": "codex-docs-readiness-v1",
            "decision": "block",
            "required": True,
            "docs_root": "",
            "blockers": [{"source": "docs_root", "message": "delivery docs repository root is required before implementation"}],
            "next_command": f"python3 skills/core/docs-governor/scripts/docs_governor.py init --docs-root delivery-docs --doc-id {doc_id}",
        }
    manifest = docs_root / "indexes" / f"{doc_id}.manifest.json"
    blockers: list[dict[str, str]] = []
    if not docs_root.exists():
        blockers.append({"source": "docs_root", "message": "delivery docs repository root does not exist"})
    if not manifest.exists():
        blockers.append({"source": "manifest", "message": "delivery docs manifest is missing"})
    if docs_root.exists():
        proc = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=docs_root, text=True, capture_output=True)
        if proc.returncode != 0 or proc.stdout.strip() != "true":
            blockers.append({"source": "docs_git", "message": "delivery docs root must be a git repository"})
    return {
        "schema": "codex-docs-readiness-v1",
        "decision": "pass" if not blockers else "block",
        "required": True,
        "docs_root": str(docs_root),
        "manifest": str(manifest),
        "blockers": blockers,
        "next_command": f"python3 skills/core/docs-governor/scripts/docs_governor.py init --docs-root {docs_root} --doc-id {doc_id}",
    }


def sync_docs_artifacts(docs_root: Path | None, doc_id: str, title: str, artifact_dir: Path) -> dict[str, Any]:
    if not docs_root:
        return {"decision": "skipped", "reason": "docs_root is not configured"}
    if not docs_root.exists():
        return {"decision": "skipped", "reason": "docs_root does not exist"}
    proc = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=docs_root, text=True, capture_output=True)
    if proc.returncode != 0 or proc.stdout.strip() != "true":
        return {"decision": "skipped", "reason": "docs_root is not a git repository"}
    try:
        return load_docs_governor_module().sync(docs_root, doc_id, artifact_dir, title)
    except Exception as exc:
        return {"decision": "block", "reason": str(exc), "blockers": [{"source": "docs_sync", "message": str(exc)}]}


def parse_scalar(value: str) -> Any:
    value = value.strip().strip('"').strip("'")
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    try:
        return int(value)
    except ValueError:
        return value


def load_restricted_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    lines: list[tuple[int, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        lines.append((len(raw) - len(raw.lstrip(" ")), raw.strip()))

    def parse_block(index: int, indent: int) -> tuple[Any, int]:
        if index >= len(lines):
            return {}, index
        container: Any = [] if lines[index][1].startswith("- ") else {}
        while index < len(lines):
            current_indent, text = lines[index]
            if current_indent < indent or current_indent > indent:
                break
            if text.startswith("- "):
                if not isinstance(container, list):
                    break
                item = text[2:].strip()
                index += 1
                if ":" in item:
                    key, value = item.split(":", 1)
                    entry: dict[str, Any] = {}
                    if value.strip():
                        entry[key.strip()] = parse_scalar(value.strip())
                    else:
                        child, index = parse_block(index, indent + 2)
                        entry[key.strip()] = child
                    while index < len(lines) and lines[index][0] > indent:
                        child_indent, child_text = lines[index]
                        if child_indent != indent + 2 or child_text.startswith("- ") or ":" not in child_text:
                            break
                        child_key, child_value = child_text.split(":", 1)
                        index += 1
                        if child_value.strip():
                            entry[child_key.strip()] = parse_scalar(child_value.strip())
                        else:
                            child, index = parse_block(index, child_indent + 2)
                            entry[child_key.strip()] = child
                    container.append(entry)
                else:
                    container.append(parse_scalar(item))
                continue
            if not isinstance(container, dict) or ":" not in text:
                break
            key, value = text.split(":", 1)
            index += 1
            if value.strip():
                container[key.strip()] = parse_scalar(value.strip())
            else:
                child, index = parse_block(index, indent + 2)
                container[key.strip()] = child
        return container, index

    parsed, _ = parse_block(0, lines[0][0] if lines else 0)
    return parsed if isinstance(parsed, dict) else {}


def load_profile_registry(path: Path = PROFILE_REGISTRY) -> dict[str, dict[str, Any]]:
    data = load_restricted_yaml(path)
    profiles: dict[str, dict[str, Any]] = {}
    for item in data.get("profiles", []) if isinstance(data.get("profiles"), list) else []:
        if isinstance(item, dict) and item.get("name"):
            profiles[str(item["name"])] = item
    return profiles


def run_command(name: str, args: list[str]) -> dict[str, Any]:
    proc = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    return {
        "name": name,
        "command": args,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def run_if_needed(name: str, output: Path, command: list[str], force: bool, generated: list[str], skipped: list[str], steps: list[dict[str, Any]]) -> None:
    if output.exists() and not force:
        skipped.append(output.name)
        steps.append({"name": name, "skipped": True, "output": str(output), "reason": "artifact exists"})
        return
    result = run_command(name, command)
    steps.append(result | {"output": str(output)})
    if output.exists():
        generated.append(output.name)


def collect_blockers(steps: list[dict[str, Any]], inspect_status: dict[str, Any], include_inspect: bool = True) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for step in steps:
        if step.get("skipped"):
            continue
        if step.get("name") == "inspect":
            continue
        if step.get("output") and Path(str(step["output"])).exists():
            continue
        if step.get("returncode", 0) != 0:
            blockers.append({"source": step.get("name"), "message": "step returned non-zero", "returncode": step.get("returncode")})
    if include_inspect:
        for item in inspect_status.get("blockers", []) or []:
            if isinstance(item, dict):
                blockers.append(item)
    return blockers


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def profile_score(profile: dict[str, Any], lane: str, impacts: set[str], has_repo: bool, explicit_profile: str | None = None) -> dict[str, Any]:
    name = str(profile.get("name") or "")
    score = 0
    signals: list[str] = []
    if explicit_profile and explicit_profile == name:
        score += 100
        signals.append("explicit_profile")
    trigger_lanes = {str(item) for item in as_list(profile.get("trigger_lanes"))}
    if lane and lane in trigger_lanes:
        score += 45
        signals.append(f"lane:{lane}")
    trigger_impacts = {str(item) for item in as_list(profile.get("trigger_impacts"))}
    matched_impacts = sorted(impacts & trigger_impacts)
    if matched_impacts:
        score += 35 + (5 * len(matched_impacts))
        signals.extend(f"impact:{item}" for item in matched_impacts)
    if has_repo and name == "cross_repo_api":
        score += 50
        signals.append("repo_context")
    if {"data", "security"} & impacts and name == "data_migration":
        score += 45
        signals.append("high_risk_data_or_security")
    if lane in {"bugfix", "hotfix"} and name in {"bugfix", "hotfix"}:
        score += 60
        signals.append("defect_containment")
    if not signals and name == "small_feature":
        score += 5
        signals.append("default_fallback")
    return {"profile": name, "score": score, "signals": signals}


def profile_selection_confidence(candidates: list[dict[str, Any]]) -> str:
    if not candidates:
        return "low"
    ordered = sorted(candidates, key=lambda item: int(item.get("score") or 0), reverse=True)
    top = int(ordered[0].get("score") or 0)
    second = int(ordered[1].get("score") or 0) if len(ordered) > 1 else 0
    if top >= 80 and top - second >= 25:
        return "high"
    if top >= 45 and top - second >= 10:
        return "medium"
    return "low"


def select_workflow_profile_with_reason(spec: dict[str, Any], has_repo: bool = False, explicit_profile: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    profiles = load_profile_registry()
    lane = str(spec.get("lane") or "")
    impacts = {str(item.get("area")) for item in as_list(spec.get("impact_surface")) if isinstance(item, dict) and item.get("area")}
    candidates = sorted(
        (profile_score(profile, lane, impacts, has_repo, explicit_profile) for profile in profiles.values()),
        key=lambda item: int(item.get("score") or 0),
        reverse=True,
    )
    confidence = profile_selection_confidence(candidates)

    def reason_payload(mode: str, selected_profile: str, reason: str, **extra: Any) -> dict[str, Any]:
        payload = {
            "mode": mode,
            "selected_profile": selected_profile,
            "reason": reason,
            "lane": lane,
            "impacts": sorted(impacts),
            "profile_selection_score": next((item.get("score", 0) for item in candidates if item.get("profile") == selected_profile), 0),
            "profile_selection_confidence": confidence,
            "profile_selection_candidates": candidates,
            "fallback_reason": "" if mode != "fallback" else reason,
        }
        payload.update(extra)
        return payload

    if explicit_profile and explicit_profile in profiles:
        return profiles[explicit_profile], reason_payload("explicit_profile", explicit_profile, "Profile was explicitly requested.")
    if has_repo and "cross_repo_api" in profiles:
        return profiles["cross_repo_api"], reason_payload("repo_context", "cross_repo_api", "Project understanding was requested, so cross-repo/API contract gates are required.")
    if lane in {"bugfix", "hotfix"}:
        for profile in profiles.values():
            if lane in {str(item) for item in as_list(profile.get("trigger_lanes"))}:
                profile_name = str(profile.get("name") or "")
                return profile, reason_payload("lane", profile_name, f"Spec lane {lane} takes precedence over impact routing for defect containment.")
    priority = [
        ("data", "data_migration", "Data changes require migration, security, performance, and release evidence gates."),
        ("security", "data_migration", "Security-sensitive data handling requires the high-risk data/security gate set."),
        ("api", "cross_repo_api", "API changes require contract and traceability gates."),
        ("ui", "frontend_change", "UI changes require frontend acceptance evidence."),
    ]
    for impact, profile_name, reason in priority:
        if impact in impacts and profile_name in profiles:
            return profiles[profile_name], reason_payload("impact_surface", profile_name, reason, matched_impact=impact)
    for profile in profiles.values():
        if lane and lane in {str(item) for item in as_list(profile.get("trigger_lanes"))}:
            profile_name = str(profile.get("name") or "")
            return profile, reason_payload("lane", profile_name, f"Spec lane {lane} is declared in profile trigger_lanes.")
    fallback = profiles.get("small_feature", {"name": "small_feature", "required_skills": [], "expected_artifacts": []})
    fallback_name = str(fallback.get("name") or "small_feature")
    return fallback, reason_payload("fallback", fallback_name, "No explicit, repository, impact, or lane trigger matched; using default small feature workflow.")


def select_workflow_profile(spec: dict[str, Any], has_repo: bool = False, explicit_profile: str | None = None) -> dict[str, Any]:
    return select_workflow_profile_with_reason(spec, has_repo, explicit_profile)[0]


def missing_profile_artifacts(profile: dict[str, Any], out: Path) -> list[str]:
    return [str(item) for item in as_list(profile.get("expected_artifacts")) if not (out / str(item)).exists()]


def nested_value(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def profile_gate_gaps(profile: dict[str, Any], out: Path) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for gate in as_list(profile.get("required_gate_artifacts")):
        if not isinstance(gate, dict):
            gaps.append({"artifact": "", "message": "required_gate_artifacts entry is not an object"})
            continue
        artifact_name = str(gate.get("artifact") or "")
        if not artifact_name:
            gaps.append({"artifact": "", "message": "required gate artifact is missing artifact path"})
            continue
        data = read_json(out / artifact_name)
        if not data:
            gaps.append({"artifact": artifact_name, "message": "artifact is missing or invalid"})
            continue
        accepted = {str(item) for item in as_list(gate.get("accepted_decisions"))}
        decision = str(data.get("decision") or data.get("status") or "")
        if accepted and not decision:
            gaps.append({"artifact": artifact_name, "message": "decision/status is missing", "accepted_decisions": sorted(accepted)})
        elif accepted and decision not in accepted:
            gaps.append({"artifact": artifact_name, "message": f"decision {decision} not accepted", "accepted_decisions": sorted(accepted)})
        readiness_path = str(gate.get("readiness_path") or "")
        if readiness_path and nested_value(data, readiness_path) != gate.get("readiness_value"):
            gaps.append({"artifact": artifact_name, "message": f"{readiness_path} is not {gate.get('readiness_value')}"})
    return gaps


def profile_requires(profile: dict[str, Any], skill: str) -> bool:
    return skill in {str(item) for item in as_list(profile.get("required_skills"))}


def render_command_item(value: Any, artifact_dir: Path) -> str:
    return str(value).replace("{artifact_dir}", str(artifact_dir))


def run_registry_artifact_steps(
    profile: dict[str, Any],
    out: Path,
    force: bool,
    generated: list[str],
    skipped: list[str],
    steps: list[dict[str, Any]],
) -> bool:
    registry_steps = [item for item in as_list(profile.get("artifact_steps")) if isinstance(item, dict)]
    if not registry_steps:
        return False
    for item in registry_steps:
        name = str(item.get("name") or item.get("artifact") or "artifact_step")
        artifact = str(item.get("artifact") or "")
        command = [render_command_item(part, out) for part in as_list(item.get("command"))]
        if not artifact or not command:
            steps.append({"name": name, "returncode": 1, "passed": False, "reason": "artifact_steps entry requires artifact and command"})
            continue
        target = out / artifact
        if target.exists() and not force:
            skipped.append(target.name)
            steps.append({"name": name, "skipped": True, "output": str(target), "reason": "artifact exists"})
            continue
        result = run_command(name, command)
        if item.get("allow_fail"):
            result["allowed_failure"] = True
            result["passed"] = True
        steps.append(result | {"output": str(target)})
        if target.exists():
            generated.append(target.name)
    return True


def run_profile_artifact_steps(
    profile: dict[str, Any],
    out: Path,
    spec: Path,
    technical: Path,
    architecture: Path,
    force: bool,
    generated: list[str],
    skipped: list[str],
    steps: list[dict[str, Any]],
) -> None:
    if run_registry_artifact_steps(profile, out, force, generated, skipped, steps):
        return
    if profile_requires(profile, "frontend-acceptance-runner"):
        run_if_needed(
            "frontend_acceptance_template",
            out / "frontend_acceptance.json",
            [
                "python3",
                "skills/core/frontend-acceptance-runner/scripts/frontend_acceptance.py",
                "template",
                "--page-type",
                "custom",
                "--target-url",
                "http://localhost/TBD",
                "--artifact-dir",
                str(out),
                "--out",
                str(out / "frontend_acceptance.json"),
            ],
            force,
            generated,
            skipped,
            steps,
        )
    if profile_requires(profile, "configuration-governor"):
        run_if_needed(
            "configuration_review",
            out / "configuration_readiness.json",
            [
                "python3",
                "skills/core/configuration-governor/scripts/configuration.py",
                "analyze",
                "--spec",
                str(spec),
                "--technical-design",
                str(technical),
                "--architecture-design",
                str(architecture),
                "--out",
                str(out / "configuration_readiness.json"),
            ],
            force,
            generated,
            skipped,
            steps,
        )
    if profile_requires(profile, "data-security-governor"):
        run_if_needed(
            "data_security_review",
            out / "data_security_review.json",
            [
                "python3",
                "skills/core/data-security-governor/scripts/data_security.py",
                "design",
                "--spec",
                str(spec),
                "--technical-design",
                str(technical),
                "--architecture-design",
                str(architecture),
                "--out",
                str(out / "data_security_review.json"),
            ],
            force,
            generated,
            skipped,
            steps,
        )
    if profile_requires(profile, "performance-governor"):
        run_if_needed(
            "performance_review",
            out / "performance_review.json",
            [
                "python3",
                "skills/core/performance-governor/scripts/performance.py",
                "design",
                "--spec",
                str(spec),
                "--technical-design",
                str(technical),
                "--architecture-design",
                str(architecture),
                "--out",
                str(out / "performance_review.json"),
            ],
            force,
            generated,
            skipped,
            steps,
        )
    if profile_requires(profile, "test-evidence-gate"):
        command = [
            "python3",
            "skills/core/test-evidence-gate/scripts/test_evidence_gate.py",
            "--artifact-dir",
            str(out),
            "--out",
            str(out / "test_evidence_gate.json"),
        ]
        if profile_requires(profile, "frontend-acceptance-runner"):
            command.append("--require-frontend")
        run_if_needed("test_evidence_gate", out / "test_evidence_gate.json", command, force, generated, skipped, steps)


def run_release_profile_steps(
    out: Path,
    force: bool,
    generated: list[str],
    skipped: list[str],
    steps: list[dict[str, Any]],
) -> None:
    for name, script, artifact in [
        ("environment_promotion_template", "skills/core/environment-promotion-governor/scripts/environment_promotion.py", "environment_promotion.json"),
        ("uat_acceptance_template", "skills/core/uat-acceptance-governor/scripts/uat_acceptance.py", "uat_acceptance.json"),
        ("release_change_template", "skills/core/release-change-governor/scripts/release_change.py", "release_change.json"),
    ]:
        run_if_needed(name, out / artifact, ["python3", script, "template", "--out", str(out / artifact)], force, generated, skipped, steps)
    run_if_needed(
        "release_evidence_binder",
        out / "release_gate.json",
        [
            "python3",
            "skills/core/release-evidence-binder/scripts/bind_release.py",
            "--artifact-dir",
            str(out),
            "--out",
            str(out / "release_gate.json"),
        ],
        force,
        generated,
        skipped,
        steps,
    )


def run(
    input_path: Path,
    doc_id: str | None = None,
    title: str | None = None,
    repo: Path | None = None,
    project: str | None = None,
    out: Path | None = None,
    force: bool = False,
    profile: str | None = None,
    docs_root: Path | None = None,
) -> dict[str, Any]:
    input_path = input_path.resolve()
    doc_id = doc_id or default_doc_id(input_path)
    title = title or default_title(input_path)
    out = (out or default_out(doc_id)).resolve()
    out.mkdir(parents=True, exist_ok=True)
    effective_docs_root = docs_root.resolve() if docs_root else default_docs_root()
    docs_status = docs_readiness(effective_docs_root, doc_id)
    write_json(out / "auto_run_summary.json", {
        "schema": SCHEMA,
        "decision": "in_progress",
        "doc_id": doc_id,
        "title": title,
        "out_dir": str(out),
        "docs_readiness": docs_status,
    })

    generated: list[str] = []
    skipped: list[str] = []
    steps: list[dict[str, Any]] = []
    explicit_profiles = load_profile_registry()
    selected_profile = explicit_profiles.get(profile, {}) if profile else {}
    profile_selection_reason: dict[str, Any] = {}
    if selected_profile.get("profile_stage_mode") == "release_only":
        profile_selection_reason = {
            "mode": "explicit_profile",
            "selected_profile": str(selected_profile.get("name") or profile or ""),
            "reason": "Release-only profile was explicitly requested.",
        }
        run_registry_artifact_steps(selected_profile, out, force, generated, skipped, steps)
        delivery_status = out / "delivery_status.json"
        inspect_result = run_command(
            "inspect",
            [
                "python3",
                "skills/core/delivery-runner/scripts/delivery_runner.py",
                "inspect",
                "--artifact-dir",
                str(out),
                "--profile",
                profile,
                "--out",
                str(delivery_status),
            ],
        )
        steps.append(inspect_result)
        inspect_status = read_json(delivery_status)
        docs_sync = sync_docs_artifacts(effective_docs_root, doc_id, title, out)
        if docs_sync.get("decision") == "pass":
            docs_status = docs_readiness(effective_docs_root, doc_id)
        blockers = collect_blockers(steps, inspect_status)
        if docs_sync.get("decision") == "block":
            blockers.extend(docs_sync.get("blockers", []))
        missing_profile = missing_profile_artifacts(selected_profile, out)
        gate_gaps = profile_gate_gaps(selected_profile, out)
        summary = {
            "schema": SCHEMA,
            "decision": "block" if blockers else "pass",
            "doc_id": doc_id,
            "title": title,
            "input": str(input_path),
            "out_dir": str(out),
            "generated_artifacts": sorted(set(generated)),
            "skipped_artifacts": skipped,
            "steps": steps,
            "workflow_profile": selected_profile,
            "profile_selection_reason": profile_selection_reason,
            "profile_selection_score": profile_selection_reason.get("profile_selection_score", 0),
            "profile_selection_confidence": profile_selection_reason.get("profile_selection_confidence", ""),
            "profile_selection_candidates": profile_selection_reason.get("profile_selection_candidates", []),
            "fallback_reason": profile_selection_reason.get("fallback_reason", ""),
            "required_gates": selected_profile.get("required_skills", []),
            "docs_readiness": docs_status,
            "docs_sync": docs_sync,
            "missing_profile_artifacts": missing_profile,
            "profile_gate_gaps": gate_gaps,
            "next_profile_command": selected_profile.get("next_safe_command", ""),
            "blockers": blockers,
            "inspect_status": inspect_status,
            "next_stage": inspect_status.get("next_stage", ""),
            "next_command": inspect_status.get("next_command", ""),
            "can_implement": bool(inspect_status.get("can_implement")),
            "can_release": bool(inspect_status.get("can_release")),
            "safety_boundary": "release_artifact_inspection_only",
        }
        write_json(out / "auto_run_summary.json", summary)
        return summary

    if repo and project:
        project_out = out / "project_understanding"
        marker = project_out / "baseline_quality.json"
        run_if_needed(
            "project_understanding",
            marker,
            [
                "python3",
                "skills/core/project-understanding-runner/scripts/project_understand.py",
                "--repo",
                str(repo),
                "--project",
                project,
                "--out",
                str(project_out),
            ],
            force,
            generated,
            skipped,
            steps,
        )
    else:
        project_out = None

    normalized = out / "requirement.normalized.txt"
    run_if_needed(
        "ingest",
        normalized,
        [
            "python3",
            "skills/core/requirement-document-ingestor/scripts/ingest_requirement.py",
            "--input",
            str(input_path),
            "--doc-id",
            doc_id,
            "--out-dir",
            str(out),
        ],
        force,
        generated,
        skipped,
        steps,
    )

    spec = out / "spec.json"
    run_if_needed(
        "spec",
        spec,
        [
            "python3",
            "skills/core/spec-governor/scripts/spec_governor.py",
            "normalize",
            "--doc-id",
            doc_id,
            "--title",
            title,
            "--input",
            str(normalized),
            "--out",
            str(spec),
        ],
        force,
        generated,
        skipped,
        steps,
    )
    spec_data = read_json(spec)
    selected_profile, profile_selection_reason = select_workflow_profile_with_reason(spec_data, bool(repo and project), profile)

    technical = out / "technical_design.json"
    technical_command = ["python3", "skills/core/technical-design-governor/scripts/technical_design.py", "--spec", str(spec), "--out", str(technical)]
    if project_out:
        technical_command.extend(["--project-understanding", str(project_out)])
    run_if_needed(
        "technical_design",
        technical,
        technical_command,
        force,
        generated,
        skipped,
        steps,
    )

    architecture = out / "architecture_design.json"
    architecture_command = [
        "python3",
        "skills/core/architecture-design-governor/scripts/architecture_design.py",
        "--spec",
        str(spec),
        "--technical-design",
        str(technical),
        "--out",
        str(architecture),
    ]
    if project_out:
        architecture_command.extend(["--project-understanding", str(project_out)])
    run_if_needed(
        "architecture_design",
        architecture,
        architecture_command,
        force,
        generated,
        skipped,
        steps,
    )

    test_design = out / "test_design.json"
    run_if_needed(
        "test_design",
        test_design,
        [
            "python3",
            "skills/core/test-design-governor/scripts/test_design.py",
            "render",
            "--spec",
            str(spec),
            "--technical-design",
            str(technical),
            "--architecture-design",
            str(architecture),
            "--out",
            str(test_design),
        ],
        force,
        generated,
        skipped,
        steps,
    )

    design_review = out / "design_architecture_review.json"
    run_if_needed(
        "design_review",
        design_review,
        [
            "python3",
            "skills/core/design-architecture-reviewer/scripts/design_arch_review.py",
            "review",
            "--technical-design",
            str(technical),
            "--architecture-design",
            str(architecture),
            "--out",
            str(design_review),
        ],
        force,
        generated,
        skipped,
        steps,
    )

    delivery_plan = out / "delivery_plan.json"
    delivery_command = [
        "python3",
        "skills/templates/delivery-plan-templates/scripts/render_delivery_plan.py",
        "--doc-id",
        doc_id,
        "--technical-design",
        str(technical),
        "--architecture-design",
        str(architecture),
        "--out",
        str(delivery_plan),
    ]
    if project_out:
        delivery_command.extend(["--project-understanding", str(project_out)])
    run_if_needed(
        "delivery_plan",
        delivery_plan,
        delivery_command,
        force,
        generated,
        skipped,
        steps,
    )

    delivery_plan_review = out / "delivery_plan_review.json"
    run_if_needed(
        "delivery_plan_review",
        delivery_plan_review,
        [
            "python3",
            "skills/core/delivery-plan-reviewer/scripts/delivery_plan_review.py",
            "review",
            "--file",
            str(delivery_plan),
            "--out",
            str(delivery_plan_review),
        ],
        force,
        generated,
        skipped,
        steps,
    )
    run_profile_artifact_steps(selected_profile, out, spec, technical, architecture, force, generated, skipped, steps)

    delivery_status = out / "delivery_status.json"
    inspect_command = [
        "python3",
        "skills/core/delivery-runner/scripts/delivery_runner.py",
        "inspect",
        "--artifact-dir",
        str(out),
        "--out",
        str(delivery_status),
    ]
    if profile:
        inspect_command.extend(["--profile", profile])
    inspect_result = run_command(
        "inspect",
        inspect_command,
    )
    steps.append(inspect_result)
    inspect_status = read_json(delivery_status)
    if not inspect_status and inspect_result.get("stdout_tail"):
        try:
            inspect_status = json.loads(str(inspect_result["stdout_tail"]))
        except Exception:
            inspect_status = {}

    docs_sync = sync_docs_artifacts(effective_docs_root, doc_id, title, out)
    if docs_sync.get("decision") == "pass":
        docs_status = docs_readiness(effective_docs_root, doc_id)
    blockers = collect_blockers(steps, inspect_status, include_inspect=False)
    readiness_blockers = [item for item in inspect_status.get("blockers", []) or [] if isinstance(item, dict)]
    if docs_sync.get("decision") == "block":
        blockers.extend(docs_sync.get("blockers", []))
    if docs_status.get("decision") == "block":
        blockers.extend(docs_status.get("blockers", []))
    missing_profile = missing_profile_artifacts(selected_profile, out)
    gate_gaps = profile_gate_gaps(selected_profile, out)
    summary = {
        "schema": SCHEMA,
        "decision": "block" if blockers else "pass",
        "doc_id": doc_id,
        "title": title,
        "input": str(input_path),
        "out_dir": str(out),
        "generated_artifacts": sorted(set(generated)),
        "skipped_artifacts": skipped,
        "steps": steps,
        "workflow_profile": selected_profile,
        "profile_selection_reason": profile_selection_reason,
        "profile_selection_score": profile_selection_reason.get("profile_selection_score", 0),
        "profile_selection_confidence": profile_selection_reason.get("profile_selection_confidence", ""),
        "profile_selection_candidates": profile_selection_reason.get("profile_selection_candidates", []),
        "fallback_reason": profile_selection_reason.get("fallback_reason", ""),
        "required_gates": selected_profile.get("required_skills", []),
        "docs_readiness": docs_status,
        "docs_sync": docs_sync,
        "readiness_blockers": readiness_blockers,
        "missing_profile_artifacts": missing_profile,
        "profile_gate_gaps": gate_gaps,
        "next_profile_command": selected_profile.get("next_safe_command", ""),
        "blockers": blockers,
        "inspect_status": inspect_status,
        "next_stage": inspect_status.get("next_stage", ""),
        "next_command": inspect_status.get("next_command", ""),
        "can_implement": bool(inspect_status.get("can_implement")),
        "can_release": bool(inspect_status.get("can_release")),
        "safety_boundary": "analysis_and_artifact_generation_only",
    }
    write_json(out / "auto_run_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="One-command safe workflow runner for Codex engineering skills")
    parser.add_argument("--input", required=True)
    parser.add_argument("--doc-id")
    parser.add_argument("--title")
    parser.add_argument("--repo")
    parser.add_argument("--project")
    parser.add_argument("--out")
    parser.add_argument("--profile")
    parser.add_argument("--docs-root")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = run(
        input_path=Path(args.input),
        doc_id=args.doc_id,
        title=args.title,
        repo=Path(args.repo) if args.repo else None,
        project=args.project,
        out=Path(args.out) if args.out else None,
        force=args.force,
        profile=args.profile,
        docs_root=Path(args.docs_root) if args.docs_root else None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
