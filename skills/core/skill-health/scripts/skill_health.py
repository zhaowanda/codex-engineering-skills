#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import py_compile
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


def check(root: Path) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    readme = (root / "README.md").read_text(encoding="utf-8") if (root / "README.md").exists() else ""
    roadmap = (root / "docs/open-source-roadmap.md").read_text(encoding="utf-8") if (root / "docs/open-source-roadmap.md").exists() else ""
    tests_text = "\n".join(path.read_text(encoding="utf-8") for path in (root / "tests").glob("test_*.py"))
    skills = sorted(root.glob("skills/*/*/SKILL.md"))
    skill_names: set[str] = set()
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
            if profile_name == "release_readiness" and "release-evidence-binder" not in required:
                blockers.append({"source": f"workflow_profile.{profile_name}", "message": "release_readiness must include release-evidence-binder"})
            if profile_name == "frontend_change":
                for required_skill in ["frontend-acceptance-runner", "test-evidence-gate"]:
                    if required_skill not in required:
                        blockers.append({"source": f"workflow_profile.{profile_name}", "message": f"frontend_change must include {required_skill}"})
    return {
        "schema": "codex-skill-health-v1",
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "skill_count": len(skills),
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
