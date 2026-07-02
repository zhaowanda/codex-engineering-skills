#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import py_compile
import re
from pathlib import Path
from typing import Any


VALID_CATEGORIES = {
    "workflow-gate",
    "artifact-generator",
    "reviewer",
    "extractor-analyzer",
    "release-governor",
    "meta-governor",
    "template-runner",
}
VALID_MATURITY = {"expert-gate", "deterministic-helper", "advisory-review", "template", "orchestrator"}
VALID_STAGES = {
    "requirements",
    "project-understanding",
    "design",
    "delivery-planning",
    "edit-readiness",
    "post-implementation-review",
    "testing",
    "release",
    "documentation",
    "workflow-orchestration",
    "meta",
}
GATE_MATURITY = {"expert-gate", "advisory-review"}
PROFILE_SCHEMA = "codex-workflow-profiles-v1"
STAGE_SCHEMA = "codex-workflow-stages-v1"


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    data: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()
    return data


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


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def skill_expert_score(skill_text: str, script_text: str, script_count: int, test_refs: int) -> dict[str, Any]:
    combined = f"{skill_text}\n{script_text}".lower()
    dimensions = {
        "instruction_structure": all(section in skill_text for section in ["## Rules", "## Output"]),
        "execution_surface": script_count > 0,
        "schema_contract": bool(re.search(r"codex-[a-z0-9-]+-v\d+", combined)),
        "decision_contract": "decision" in combined and ("blockers" in combined or "warnings" in combined),
        "test_coverage_signal": test_refs > 0,
        "evidence_orientation": any(term in combined for term in ["evidence", "traceability", "readiness", "rollback", "gate"]),
        "failure_path": any(term in combined for term in ["block", "blocked", "no_go", "needs_revision", "missing"]),
    }
    score = 50
    score += 10 if dimensions["instruction_structure"] else 0
    score += 10 if dimensions["execution_surface"] else 0
    score += 10 if dimensions["schema_contract"] else 0
    score += 8 if dimensions["decision_contract"] else 0
    score += 8 if dimensions["test_coverage_signal"] else 0
    score += 7 if dimensions["evidence_orientation"] else 0
    score += 7 if dimensions["failure_path"] else 0
    level = "expert" if score >= 90 else "advanced" if score >= 82 else "standard" if score >= 72 else "basic"
    return {"score": min(score, 100), "level": level, "dimensions": dimensions}


def check(root: Path) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    readme = (root / "README.md").read_text(encoding="utf-8") if (root / "README.md").exists() else ""
    roadmap = (root / "docs/open-source-roadmap.md").read_text(encoding="utf-8") if (root / "docs/open-source-roadmap.md").exists() else ""
    tests_text = "\n".join(path.read_text(encoding="utf-8") for path in (root / "tests").glob("test_*.py"))
    skills = sorted(root.glob("skills/*/*/SKILL.md"))
    skill_names: set[str] = set()
    expert_scores: list[dict[str, Any]] = []
    for skill in skills:
        rel = skill.relative_to(root).as_posix()
        skill_dir = skill.parent.relative_to(root).as_posix()
        skill_text = skill.read_text(encoding="utf-8")
        fm = parse_frontmatter(skill_text)
        if not fm.get("name") or not fm.get("description"):
            blockers.append({"source": rel, "message": "name and description frontmatter are required"})
        for key in ["category", "maturity", "stage", "gate"]:
            if not fm.get(key):
                blockers.append({"source": rel, "message": f"{key} frontmatter is required"})
        if fm.get("category") and fm["category"] not in VALID_CATEGORIES:
            blockers.append({"source": rel, "message": "category frontmatter is invalid", "category": fm["category"]})
        if fm.get("maturity") and fm["maturity"] not in VALID_MATURITY:
            blockers.append({"source": rel, "message": "maturity frontmatter is invalid", "maturity": fm["maturity"]})
        if fm.get("stage") and fm["stage"] not in VALID_STAGES:
            blockers.append({"source": rel, "message": "stage frontmatter is invalid", "stage": fm["stage"]})
        if fm.get("gate") and fm["gate"] not in {"true", "false"}:
            blockers.append({"source": rel, "message": "gate frontmatter must be true or false", "gate": fm["gate"]})
        if fm.get("maturity") == "expert-gate" and fm.get("gate") != "true":
            blockers.append({"source": rel, "message": "expert-gate skills must declare gate=true"})
        if fm.get("maturity") in {"template", "deterministic-helper", "orchestrator"} and fm.get("gate") == "true":
            blockers.append({"source": rel, "message": "template/helper/orchestrator skills must not declare gate=true"})
        if fm.get("category") in {"template-runner", "extractor-analyzer"} and fm.get("maturity") == "expert-gate":
            blockers.append({"source": rel, "message": "template and extractor skills must not be marked expert-gate"})
        if fm.get("name") and fm["name"] not in rel:
            warnings.append({"source": rel, "message": "frontmatter name differs from folder path", "name": fm["name"]})
        name = fm.get("name", "")
        if name:
            skill_names.add(name)
        if rel not in readme and skill_dir not in readme and name not in readme:
            warnings.append({"source": rel, "message": "skill is not listed in README"})
        scripts = list(skill.parent.glob("scripts/*.py"))
        script_text = "\n".join(script.read_text(encoding="utf-8", errors="ignore") for script in scripts)
        if fm.get("gate") == "true":
            gate_contract_text = f"{skill_text}\n{script_text}"
            missing_terms = [term for term in ["schema", "decision", "blockers"] if term not in gate_contract_text.lower()]
            if missing_terms:
                blockers.append({"source": rel, "message": "gate skills must document or emit schema, decision, and blockers", "missing": missing_terms})
        if fm.get("maturity") == "expert-gate":
            test_ref_count = sum(1 for pattern in [name, name.replace("-", "_")] if pattern and pattern in tests_text)
            if test_ref_count == 0:
                blockers.append({"source": rel, "message": "expert-gate skills require direct test coverage"})
        test_refs = sum(1 for pattern in [name, name.replace("-", "_")] if pattern and pattern in tests_text)
        expert_scores.append({
            "skill": name or skill.parent.name,
            "path": rel,
            **skill_expert_score(skill_text, script_text, len(scripts), test_refs),
        })
        for script in scripts:
            try:
                py_compile.compile(str(script), doraise=True)
            except Exception as exc:
                blockers.append({"source": script.relative_to(root).as_posix(), "message": f"python compile failed: {exc}"})
    if "`done`" not in roadmap:
        warnings.append({"source": "docs/open-source-roadmap.md", "message": "roadmap has no done markers"})
    if not list((root / "tests").glob("test_*.py")):
        blockers.append({"source": "tests", "message": "test files are required"})
    profile_path = root / "config/workflow-profiles.example.yaml"
    if profile_path.exists():
        profiles = load_restricted_yaml(profile_path)
        if profiles.get("schema") != PROFILE_SCHEMA:
            blockers.append({"source": "config/workflow-profiles.example.yaml", "message": f"profile schema must be {PROFILE_SCHEMA}"})
        workflow_docs = (root / "docs/workflow-guide.md").read_text(encoding="utf-8") if (root / "docs/workflow-guide.md").exists() else ""
        for profile in profiles.get("profiles", []) if isinstance(profiles.get("profiles"), list) else []:
            if not isinstance(profile, dict):
                blockers.append({"source": "config/workflow-profiles.example.yaml", "message": "profile entries must be objects"})
                continue
            profile_name = str(profile.get("name") or "")
            if not profile_name:
                blockers.append({"source": "config/workflow-profiles.example.yaml", "message": "profile name is required"})
                continue
            if profile_name not in workflow_docs:
                warnings.append({"source": f"workflow_profile.{profile_name}", "message": "profile is not documented in workflow guide"})
            required = [str(item) for item in as_list(profile.get("required_skills"))]
            if not required:
                blockers.append({"source": f"workflow_profile.{profile_name}", "message": "required_skills is required"})
            missing_skills = [item for item in required if item not in skill_names]
            if missing_skills:
                blockers.append({"source": f"workflow_profile.{profile_name}", "message": "profile references unknown skills", "missing_skills": missing_skills})
            expected_artifacts = {str(item) for item in as_list(profile.get("expected_artifacts"))}
            if profile_name != "release_readiness":
                for required_artifact in ["test_design.json", "docs_quality.json"]:
                    if required_artifact not in expected_artifacts:
                        blockers.append({"source": f"workflow_profile.{profile_name}", "message": f"{required_artifact} must be listed in expected_artifacts"})
            for step in as_list(profile.get("artifact_steps")):
                if not isinstance(step, dict):
                    blockers.append({"source": f"workflow_profile.{profile_name}", "message": "artifact_steps entries must be objects"})
                    continue
                step_name = str(step.get("name") or "")
                artifact_name = str(step.get("artifact") or "")
                command = as_list(step.get("command"))
                if not step_name or not artifact_name:
                    blockers.append({"source": f"workflow_profile.{profile_name}", "message": "artifact_steps name and artifact are required"})
                elif expected_artifacts and artifact_name not in expected_artifacts:
                    blockers.append({"source": f"workflow_profile.{profile_name}", "message": "artifact_steps artifact must be listed in expected_artifacts", "artifact": artifact_name})
                if not command:
                    blockers.append({"source": f"workflow_profile.{profile_name}", "message": "artifact_steps command is required", "artifact": artifact_name})
                if command and str(command[0]) != "python3":
                    warnings.append({"source": f"workflow_profile.{profile_name}", "message": "artifact_steps command should usually start with python3", "artifact": artifact_name})
            gates = as_list(profile.get("required_gate_artifacts"))
            if not gates:
                blockers.append({"source": f"workflow_profile.{profile_name}", "message": "required_gate_artifacts is required"})
            gate_artifacts = {str(gate.get("artifact")) for gate in gates if isinstance(gate, dict)}
            if profile_name != "release_readiness":
                for required_artifact in ["test_design.json", "docs_quality.json"]:
                    if required_artifact not in gate_artifacts:
                        blockers.append({"source": f"workflow_profile.{profile_name}", "message": f"{required_artifact} must be listed in required_gate_artifacts"})
            for gate in gates:
                if not isinstance(gate, dict):
                    blockers.append({"source": f"workflow_profile.{profile_name}", "message": "required_gate_artifacts entries must be objects"})
                    continue
                artifact_name = str(gate.get("artifact") or "")
                if not artifact_name:
                    blockers.append({"source": f"workflow_profile.{profile_name}", "message": "required_gate_artifacts artifact is required"})
                elif expected_artifacts and artifact_name not in expected_artifacts:
                    blockers.append({"source": f"workflow_profile.{profile_name}", "message": "required gate artifact must be listed in expected_artifacts", "artifact": artifact_name})
                if "accepted_decisions" in gate and not as_list(gate.get("accepted_decisions")):
                    blockers.append({"source": f"workflow_profile.{profile_name}", "message": "accepted_decisions must not be empty", "artifact": artifact_name})
                if bool(gate.get("readiness_path")) != ("readiness_value" in gate):
                    blockers.append({"source": f"workflow_profile.{profile_name}", "message": "readiness_path and readiness_value must be declared together", "artifact": artifact_name})
            if profile_name == "release_readiness" and "release-evidence-binder" not in required:
                blockers.append({"source": f"workflow_profile.{profile_name}", "message": "release_readiness must include release-evidence-binder"})
            if profile_name == "frontend_change":
                for required_skill in ["frontend-acceptance-runner", "test-evidence-gate"]:
                    if required_skill not in required:
                        blockers.append({"source": f"workflow_profile.{profile_name}", "message": f"frontend_change must include {required_skill}"})
    stage_path = root / "config/workflow-stages.example.yaml"
    if stage_path.exists():
        stages_doc = load_restricted_yaml(stage_path)
        if stages_doc.get("schema") != STAGE_SCHEMA:
            blockers.append({"source": "config/workflow-stages.example.yaml", "message": f"stage schema must be {STAGE_SCHEMA}"})
        seen_stages: set[str] = set()
        seen_artifacts: set[str] = set()
        for stage in stages_doc.get("stages", []) if isinstance(stages_doc.get("stages"), list) else []:
            if not isinstance(stage, dict):
                blockers.append({"source": "config/workflow-stages.example.yaml", "message": "stage entries must be objects"})
                continue
            name = str(stage.get("name") or "")
            artifact_name = str(stage.get("artifact") or "")
            if not name or not artifact_name:
                blockers.append({"source": "config/workflow-stages.example.yaml", "message": "stage name and artifact are required"})
            if name in seen_stages:
                blockers.append({"source": "config/workflow-stages.example.yaml", "message": "duplicate stage name", "stage": name})
            if artifact_name in seen_artifacts:
                blockers.append({"source": "config/workflow-stages.example.yaml", "message": "duplicate stage artifact", "artifact": artifact_name})
            seen_stages.add(name)
            seen_artifacts.add(artifact_name)
    expert_level_count = sum(1 for item in expert_scores if item["level"] == "expert")
    advanced_or_better_count = sum(1 for item in expert_scores if item["level"] in {"expert", "advanced"})
    return {
        "schema": "codex-skill-health-v1",
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "skill_count": len(skills),
        "expert_level_count": expert_level_count,
        "advanced_or_better_count": advanced_or_better_count,
        "expert_readiness": "expert" if expert_level_count == len(skills) else "advanced" if advanced_or_better_count == len(skills) else "mixed",
        "skill_scores": expert_scores,
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check skill repository health")
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    result = check(Path(args.root))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
