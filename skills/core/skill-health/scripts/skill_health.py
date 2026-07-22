#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import py_compile
import re
import tempfile
from functools import lru_cache
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
PROFILE_SCHEMA = "codex-workflow-profiles-v3"
STAGE_SCHEMA = "codex-workflow-stages-v4"
DEFAULT_ARTIFACT_VALIDATOR = "builtin:artifact-contract-v2"
DEFAULT_LINEAGE_SCHEMA = "codex-workflow-artifact-lineage-v2"
DEPRECATED_PROFILE_SCHEMAS = {"codex-workflow-profiles-v1", "codex-workflow-profiles-v2"}
# Retained in the public schema inventory so older consumers receive an explicit
# migration contract instead of an unannounced schema removal.
DEPRECATED_STAGE_SCHEMAS = {
    "codex-workflow-stages-v1",
    "codex-workflow-stages-v2",
    "codex-workflow-stages-v3",
}
PUBLIC_SCRIPT_LEAK_TERMS = (
    "pricing-service",
    "notification-service",
    "renewal/recalculate",
    "renewal-status",
    "renewal-pool",
    "operate-platform-fe",
    "sigreal-",
    "open.feishu.cn",
    "larksuite",
    "tenant_access_token",
    "checkout summary",
    "completed-order",
    "create_order",
    "order received",
    "飞书",
    "续费",
    "结算订单",
    "回款",
)
REQUIRED_SEMANTIC_DEPENDENCIES = {
    "architecture_framing": {"domain_model_design"},
    "technical_design": {"requirement_questions", "architecture_framing"},
    "architecture_design": {"technical_design", "architecture_framing"},
    "cross_repo_plan": {"delivery_plan_draft"},
    "test_design": {"architecture_design", "cross_repo_plan"},
    "design_review": {"test_design"},
    "test_data_plan": {"test_design"},
    "delivery_plan": {"test_data_plan"},
    "delivery_plan_review": {"initial_traceability"},
    "write_guard_snapshot": {"edit_permit"},
    "implementation": {"write_guard_snapshot"},
    "change_risk": {"diff_impact"},
    "evidence_collection": {"post_change", "change_risk"},
    "test": {"implementation"},
    "review": {"write_guard_audit", "evidence_collection", "code_design_quality", "test", "post_implementation_traceability"},
    "environment": {"review"},
    "uat": {"environment"},
    "release_change": {"uat"},
    "release": {"release_change"},
}


def artifact_schema_inventory(root: Path) -> dict[str, Any]:
    script = root / "skills/core/artifact-schema-governor/scripts/artifact_schema.py"
    if not script.exists():
        return {"decision": "missing", "blockers": [{"source": str(script), "message": "artifact schema inventory script is missing"}], "warnings": []}
    spec = importlib.util.spec_from_file_location("artifact_schema_for_skill_health", script)
    if spec is None or spec.loader is None:
        return {"decision": "block", "blockers": [{"source": str(script), "message": "artifact schema inventory script cannot be loaded"}], "warnings": []}
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.inventory(root)


def public_script_leak_scan(root: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    public_script_globs = [
        "skills/core/*/scripts/*.py",
        "skills/templates/*/scripts/*.py",
    ]
    for pattern in public_script_globs:
        for path in sorted(root.glob(pattern)):
            rel = path.relative_to(root).as_posix()
            if rel == "skills/core/skill-health/scripts/skill_health.py":
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            lower = text.lower()
            for term in PUBLIC_SCRIPT_LEAK_TERMS:
                needle = term.lower()
                if needle in lower:
                    findings.append({"source": rel, "term": term})
    return {
        "decision": "block" if findings else "pass",
        "finding_count": len(findings),
        "findings": findings[:50],
    }


def design_template_regression(root: Path) -> dict[str, Any]:
    template_script = root / "skills/templates/design-doc-templates/scripts/render_design_templates.py"
    review_script = root / "skills/core/design-architecture-reviewer/scripts/design_arch_review.py"
    if not template_script.exists() or not review_script.exists():
        return {
            "decision": "block",
            "blockers": [{"source": "design_template_regression", "message": "design template or reviewer script is missing"}],
            "examples": [],
        }

    def load_module(name: str, path: Path) -> Any:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    try:
        templates = load_module("render_design_templates_for_skill_health", template_script)
        reviewer = load_module("design_arch_review_for_skill_health", review_script)
        examples = [
            (
                "standard_design_example",
                templates.example_technical("REQ-EXAMPLE", "Summary item display"),
                templates.example_architecture("REQ-EXAMPLE", "Summary item display"),
            ),
            (
                "new_service_design_example",
                templates.new_service_example_technical("REQ-NEW-SERVICE", "Shared rule service"),
                templates.new_service_example_architecture("REQ-NEW-SERVICE", "Shared rule service"),
            ),
        ]
    except Exception as exc:
        return {
            "decision": "block",
            "blockers": [{"source": "design_template_regression", "message": f"failed to load design examples: {exc}"}],
            "examples": [],
        }

    blockers: list[dict[str, Any]] = []
    example_results: list[dict[str, Any]] = []
    for name, technical, architecture in examples:
        result = reviewer.review(technical, architecture)
        example_results.append({
            "name": name,
            "decision": result.get("decision"),
            "score": result.get("score"),
            "level": result.get("level"),
            "implementation_allowed": result.get("readiness_gate", {}).get("implementation_allowed"),
        })
        if result.get("decision") != "pass" or not result.get("readiness_gate", {}).get("implementation_allowed"):
            blockers.append({"source": name, "message": "design template example does not pass design-architecture-reviewer", "decision": result.get("decision"), "score": result.get("score")})
    return {
        "decision": "block" if blockers else "pass",
        "blockers": blockers,
        "examples": example_results,
    }


def real_project_calibration(root: Path) -> dict[str, Any]:
    validator_path = root / "skills/core/delivery-case-capture/scripts/capture_case.py"
    replay_dir = root / "examples/replay-cases"
    if not validator_path.exists() or not replay_dir.exists():
        return {"count": 0, "families": [], "agreement_rate": 0, "validation_decision": "missing"}
    try:
        spec = importlib.util.spec_from_file_location("health_replay_validator", validator_path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        validation = module.validate_replay_dir(replay_dir)
    except Exception as exc:
        return {"count": 0, "families": [], "agreement_rate": 0, "validation_decision": "block", "error": str(exc)}
    real_cases = [
        item for item in as_list(validation.get("cases"))
        if isinstance(item, dict)
        and item.get("valid") is True
        and item.get("source_type") == "anonymized_real_project"
        and isinstance(item.get("ground_truth_match"), bool)
    ]
    families = sorted({str(item.get("scenario")) for item in real_cases if item.get("scenario")})
    agreement_count = sum(1 for item in real_cases if item.get("ground_truth_match") is True)
    return {
        "count": len(real_cases),
        "families": families,
        "agreement_rate": round(100 * agreement_count / len(real_cases), 2) if real_cases else 0,
        "validation_decision": validation.get("decision"),
    }


def workflow_runtime_assessment(root: Path, stage_entries: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        contract_path = root / "skills/core/delivery-runner/scripts/workflow_contract.py"
        contract_spec = importlib.util.spec_from_file_location("health_workflow_contract", contract_path)
        assert contract_spec and contract_spec.loader
        contract = importlib.util.module_from_spec(contract_spec)
        contract_spec.loader.exec_module(contract)
        fail_closed_results = []
        for stage in stage_entries:
            normalized = dict(stage)
            normalized.setdefault("validator", DEFAULT_ARTIFACT_VALIDATOR)
            accepted = as_list(normalized.get("accepted_decisions"))
            schemas = as_list(normalized.get("accepted_schemas"))
            schema = normalized.get("expected_schema") or (schemas[0] if schemas else "placeholder")
            placeholder: dict[str, Any] = {
                "schema": schema,
                "decision": accepted[0] if accepted else "pass",
                "blockers": [],
            }
            for field in as_list(normalized.get("required_fields")):
                if field in {"schema", "decision", "blockers"}:
                    continue
                current = placeholder
                parts = str(field).split(".")
                for part in parts[:-1]:
                    current = current.setdefault(part, {})
                current[parts[-1]] = []
            issues = contract.validate_artifact_contract(normalized, placeholder)
            fail_closed_results.append({"stage": stage.get("name"), "rejected": bool(issues), "issues": issues})

        synthetic_path = root / "skills/templates/synthetic-e2e-runner/scripts/run_synthetic_e2e.py"
        synthetic_spec = importlib.util.spec_from_file_location("health_synthetic_e2e", synthetic_path)
        assert synthetic_spec and synthetic_spec.loader
        synthetic = importlib.util.module_from_spec(synthetic_spec)
        synthetic_spec.loader.exec_module(synthetic)
        with tempfile.TemporaryDirectory() as tmp:
            synthetic_result = synthetic.run(Path(tmp))
        case_results = {
            str(item.get("case")): bool(item.get("passed"))
            for item in as_list(synthetic_result.get("cases"))
            if isinstance(item, dict)
        }
        required_cases = {
            "blocked_case",
            "happy_path_case",
            "frontend_happy_path",
            "data_migration_blocked_path",
            "release_readiness_blocked_path",
            "release_readiness_happy_path",
            "release_followup_chain_path",
        }
        return {
            "decision": "pass" if all(item["rejected"] for item in fail_closed_results) and synthetic_result.get("decision") == "pass" and required_cases.issubset({name for name, passed in case_results.items() if passed}) else "block",
            "fail_closed_stage_count": sum(1 for item in fail_closed_results if item["rejected"]),
            "semantic_fail_closed_stage_count": sum(1 for item in fail_closed_results if item["rejected"]),
            "stage_count": len(fail_closed_results),
            "adversarial_artifact_shape": "correct schema and accepted decision with vacuous required fields",
            "fail_closed_results": fail_closed_results,
            "synthetic_decision": synthetic_result.get("decision"),
            "case_results": case_results,
        }
    except Exception as exc:
        return {"decision": "block", "error": str(exc), "fail_closed_results": [], "case_results": {}}


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
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [] if not inner else [parse_scalar(item) for item in inner.split(",")]
    value = value.strip('"').strip("'")
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


def assigned_names(node: ast.Assign | ast.AnnAssign) -> set[str]:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    return {
        child.id
        for target in targets
        for child in ast.walk(target)
        if isinstance(child, ast.Name)
    }


def node_source_segment(source_lines: list[str], node: ast.AST) -> str:
    start = getattr(node, "lineno", None)
    end = getattr(node, "end_lineno", None)
    if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start:
        return ""
    segment_lines = source_lines[start - 1:end]
    if not segment_lines:
        return ""
    first_col = getattr(node, "col_offset", 0) or 0
    last_col = getattr(node, "end_col_offset", None)
    segment_lines[0] = segment_lines[0][first_col:]
    if isinstance(last_col, int):
        segment_lines[-1] = segment_lines[-1][:last_col]
    return "".join(segment_lines)


def skill_test_aliases(source_lines: list[str], tree: ast.Module, identifiers: set[str]) -> set[str]:
    assignments: list[tuple[set[str], str, set[str]]] = []
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if value is None:
            continue
        assignments.append(
            (
                assigned_names(node),
                node_source_segment(source_lines, value),
                {child.id for child in ast.walk(value) if isinstance(child, ast.Name)},
            )
        )

    aliases: set[str] = set()
    changed = True
    while changed:
        changed = False
        for targets, segment, dependencies in assignments:
            if any(identifier in segment for identifier in identifiers) or dependencies & aliases:
                additions = targets - aliases
                if additions:
                    aliases.update(additions)
                    changed = True
    return aliases


@lru_cache(maxsize=8)
def test_behavior_index(root_str: str) -> tuple[dict[str, Any], ...]:
    root = Path(root_str)
    indexed: list[dict[str, Any]] = []
    for path in (root / "tests").glob("test_*.py"):
        source = path.read_text(encoding="utf-8", errors="ignore")
        source_lines = source.splitlines(keepends=True)
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        assignments: list[dict[str, Any]] = []
        tests: list[dict[str, Any]] = []
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = node.value
                if value is None:
                    continue
                assignments.append({
                    "targets": assigned_names(node),
                    "segment": node_source_segment(source_lines, value),
                    "dependencies": {child.id for child in ast.walk(value) if isinstance(child, ast.Name)},
                })
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith("test_"):
                continue
            tests.append({
                "name": node.name,
                "segment": node_source_segment(source_lines, node),
                "referenced_names": {child.id for child in ast.walk(node) if isinstance(child, ast.Name)},
            })
        indexed.append({"assignments": assignments, "tests": tests})
    return tuple(indexed)


def behavior_test_signals(root: Path, skill_name: str) -> tuple[int, int]:
    identifiers = {
        skill_name,
        skill_name.replace("-", "_"),
        f"skills/core/{skill_name}/",
        f"skills/templates/{skill_name}/",
    }
    positive = 0
    negative = 0
    negative_terms = {"block", "reject", "invalid", "missing", "stale", "tamper", "empty", "fail", "deny"}
    for file_data in test_behavior_index(str(root.resolve())):
        assignments = file_data.get("assignments", [])
        aliases: set[str] = set()
        changed = True
        while changed:
            changed = False
            for item in assignments:
                targets = item.get("targets", set())
                segment = str(item.get("segment", ""))
                dependencies = item.get("dependencies", set())
                if any(identifier and identifier in segment for identifier in identifiers) or dependencies & aliases:
                    additions = set(targets) - aliases
                    if additions:
                        aliases.update(additions)
                        changed = True
        for test in file_data.get("tests", []):
            referenced_names = set(test.get("referenced_names", set()))
            if referenced_names & aliases:
                positive += 1
                if any(term in str(test.get("name", "")).lower() for term in negative_terms):
                    negative += 1
                continue
            segment = str(test.get("segment", ""))
            if not any(identifier and identifier in segment for identifier in identifiers):
                continue
            positive += 1
            if any(term in str(test.get("name", "")).lower() for term in negative_terms):
                negative += 1
    return positive, negative


def skill_expert_score(
    skill_text: str,
    script_text: str,
    script_count: int,
    positive_tests: int,
    negative_tests: int,
    maturity: str,
) -> dict[str, Any]:
    combined = f"{skill_text}\n{script_text}".lower()
    bash_examples = len(re.findall(r"```bash", skill_text))
    schema_mentions = len(set(re.findall(r"codex-[a-z0-9-]+-v\d+", combined)))
    dimensions = {
        "documented_contract": all(section in skill_text for section in ["## Rules", "## Output"]),
        "execution_surface": script_count > 0,
        "schema_contract": schema_mentions > 0,
        "positive_behavior_tests": positive_tests > 0,
        "negative_behavior_tests": negative_tests > 0,
        "real_project_calibration": False,
    }
    content_quality = {
        "command_example": bash_examples > 0,
        "specific_schema_names": schema_mentions > 0,
        "explicit_failure_mode": negative_tests > 0,
        "artifact_or_evidence_boundary": any(term in combined for term in ["artifact", "evidence", "summary", "review", "gate"]),
        "concise_instruction_body": len(re.findall(r"\w+", skill_text)) <= 700,
    }
    quality_score = sum(20 for passed in content_quality.values() if passed)
    score = 25
    score += 15 if dimensions["documented_contract"] else 0
    score += 15 if dimensions["execution_surface"] else 0
    score += 15 if dimensions["schema_contract"] else 0
    score += 15 if dimensions["positive_behavior_tests"] else 0
    score += 15 if dimensions["negative_behavior_tests"] else 0
    raw_level = "expert_contract" if score >= 80 else "advanced" if score >= 65 else "standard" if score >= 50 else "basic"
    level = raw_level if maturity in GATE_MATURITY else "advanced" if raw_level == "expert_contract" else raw_level
    return {
        "score": min(score, 100),
        "level": level,
        "expert_proven": False,
        "test_evidence": {"positive_behavior_tests": positive_tests, "negative_behavior_tests": negative_tests},
        "dimensions": dimensions,
        "content_quality": {
            "score": quality_score,
            "level": "expert" if quality_score >= 80 else "advanced" if quality_score >= 60 else "basic",
            "dimensions": content_quality,
        },
    }


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
        positive_tests, negative_tests = behavior_test_signals(root, name)
        expert_scores.append({
            "skill": name or skill.parent.name,
            "path": rel,
            **skill_expert_score(skill_text, script_text, len(scripts), positive_tests, negative_tests, fm.get("maturity", "")),
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
    schema_inventory = artifact_schema_inventory(root)
    if schema_inventory.get("decision") == "block":
        for item in as_list(schema_inventory.get("blockers")):
            source = item.get("source") if isinstance(item, dict) else "artifact_schema"
            message = item.get("message") if isinstance(item, dict) else str(item)
            blockers.append({"source": source or "artifact_schema", "message": f"artifact schema inventory blocked: {message}"})
    design_templates = design_template_regression(root)
    if design_templates.get("decision") == "block":
        for item in as_list(design_templates.get("blockers")):
            source = item.get("source") if isinstance(item, dict) else "design_template_regression"
            message = item.get("message") if isinstance(item, dict) else str(item)
            blockers.append({"source": source or "design_template_regression", "message": f"design template regression blocked: {message}"})
    public_leaks = public_script_leak_scan(root)
    if public_leaks.get("decision") == "block":
        for item in as_list(public_leaks.get("findings")):
            source = item.get("source") if isinstance(item, dict) else "public_script_leak_scan"
            term = item.get("term") if isinstance(item, dict) else str(item)
            blockers.append({"source": source or "public_script_leak_scan", "message": "public skill script contains project/business-specific leaked term", "term": term})
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
            if profile.get("governance_level") not in {"light", "standard", "heavy", "critical"}:
                blockers.append({"source": f"workflow_profile.{profile_name}", "message": "governance_level must be light, standard, heavy, or critical"})
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
                blocking_decisions = {"block", "blocked", "fail", "failed", "needs_revision", "needs_review", "needs_evidence", "no_go", "request_changes"}
                invalid_accepted = blocking_decisions & {str(item) for item in as_list(gate.get("accepted_decisions"))}
                if invalid_accepted:
                    blockers.append({"source": f"workflow_profile.{profile_name}", "message": "required gate must not accept blocking decisions", "artifact": artifact_name, "invalid_decisions": sorted(invalid_accepted)})
                if bool(gate.get("readiness_path")) != ("readiness_value" in gate):
                    blockers.append({"source": f"workflow_profile.{profile_name}", "message": "readiness_path and readiness_value must be declared together", "artifact": artifact_name})
            if profile_name == "release_readiness" and "release-evidence-binder" not in required:
                blockers.append({"source": f"workflow_profile.{profile_name}", "message": "release_readiness must include release-evidence-binder"})
            if profile_name == "frontend_change":
                for required_skill in ["frontend-implementation-planner"]:
                    if required_skill not in required:
                        blockers.append({"source": f"workflow_profile.{profile_name}", "message": f"frontend_change must include {required_skill}"})
                for post_implementation_skill in ["frontend-acceptance-runner", "test-evidence-gate"]:
                    if post_implementation_skill in required:
                        blockers.append({"source": f"workflow_profile.{profile_name}", "message": f"frontend_change must not require post-implementation skill {post_implementation_skill}"})
    stage_entries: list[dict[str, Any]] = []
    stage_path = root / "config/workflow-stages.example.yaml"
    if stage_path.exists():
        stages_doc = load_restricted_yaml(stage_path)
        if stages_doc.get("schema") != STAGE_SCHEMA:
            blockers.append({"source": "config/workflow-stages.example.yaml", "message": f"stage schema must be {STAGE_SCHEMA}"})
        phase_order = [str(item) for item in as_list(stages_doc.get("phase_order"))]
        phase_rank = {phase: idx for idx, phase in enumerate(phase_order)}
        if not phase_order:
            blockers.append({"source": "config/workflow-stages.example.yaml", "message": "phase_order is required"})
        if stages_doc.get("default_validator") != DEFAULT_ARTIFACT_VALIDATOR:
            blockers.append({"source": "config/workflow-stages.example.yaml", "message": f"default_validator must be {DEFAULT_ARTIFACT_VALIDATOR}"})
        if stages_doc.get("default_lineage_schema") != DEFAULT_LINEAGE_SCHEMA:
            blockers.append({"source": "config/workflow-stages.example.yaml", "message": f"default_lineage_schema must be {DEFAULT_LINEAGE_SCHEMA}"})
        seen_stages: set[str] = set()
        seen_artifacts: set[str] = set()
        stage_entries = stages_doc.get("stages", []) if isinstance(stages_doc.get("stages"), list) else []
        stage_by_name = {str(item.get("name")): item for item in stage_entries if isinstance(item, dict) and item.get("name")}
        for stage in stage_entries:
            if not isinstance(stage, dict):
                blockers.append({"source": "config/workflow-stages.example.yaml", "message": "stage entries must be objects"})
                continue
            name = str(stage.get("name") or "")
            artifact_name = str(stage.get("artifact") or "")
            if not name or not artifact_name:
                blockers.append({"source": "config/workflow-stages.example.yaml", "message": "stage name and artifact are required"})
            phase = str(stage.get("phase") or "")
            if phase not in phase_rank:
                blockers.append({"source": "config/workflow-stages.example.yaml", "message": "stage phase is missing or unknown", "stage": name, "phase": phase})
            if not isinstance(stage.get("depends_on"), list):
                blockers.append({"source": "config/workflow-stages.example.yaml", "message": "stage depends_on must be a list", "stage": name})
            accepted_schemas = as_list(stage.get("accepted_schemas"))
            if not stage.get("expected_schema") and not accepted_schemas:
                blockers.append({"source": "config/workflow-stages.example.yaml", "message": "stage must declare expected_schema or accepted_schemas", "stage": name})
            if not isinstance(stage.get("required_fields"), list) or not stage.get("required_fields"):
                blockers.append({"source": "config/workflow-stages.example.yaml", "message": "stage required_fields must be a non-empty list", "stage": name})
            if not isinstance(stage.get("evidence_fields"), list) or not stage.get("evidence_fields"):
                blockers.append({"source": "config/workflow-stages.example.yaml", "message": "stage evidence_fields must be a non-empty list for semantic validation", "stage": name})
            if (stage.get("implementation_required") or stage.get("release_required")) and not as_list(stage.get("accepted_decisions")):
                blockers.append({"source": "config/workflow-stages.example.yaml", "message": "readiness stage must declare accepted_decisions", "stage": name})
            if name in seen_stages:
                blockers.append({"source": "config/workflow-stages.example.yaml", "message": "duplicate stage name", "stage": name})
            if artifact_name in seen_artifacts:
                blockers.append({"source": "config/workflow-stages.example.yaml", "message": "duplicate stage artifact", "artifact": artifact_name})
            seen_stages.add(name)
            seen_artifacts.add(artifact_name)
        for name, stage in stage_by_name.items():
            declared_dependencies = {str(item) for item in as_list(stage.get("depends_on"))}
            missing_semantic = REQUIRED_SEMANTIC_DEPENDENCIES.get(name, set()) - declared_dependencies
            if missing_semantic:
                blockers.append({"source": "config/workflow-stages.example.yaml", "message": "stage is missing required semantic dependencies", "stage": name, "dependencies": sorted(missing_semantic)})
            for dependency in [str(item) for item in as_list(stage.get("depends_on"))]:
                if dependency not in stage_by_name:
                    blockers.append({"source": "config/workflow-stages.example.yaml", "message": "stage dependency does not exist", "stage": name, "dependency": dependency})
                    continue
                current_phase = str(stage.get("phase") or "")
                dependency_phase = str(stage_by_name[dependency].get("phase") or "")
                if current_phase in phase_rank and dependency_phase in phase_rank and phase_rank[dependency_phase] > phase_rank[current_phase]:
                    blockers.append({"source": "config/workflow-stages.example.yaml", "message": "stage dependency points to a later phase", "stage": name, "dependency": dependency})
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(stage_name: str) -> None:
            if stage_name in visiting:
                blockers.append({"source": "config/workflow-stages.example.yaml", "message": "workflow stage graph contains a cycle", "stage": stage_name})
                return
            if stage_name in visited:
                return
            visiting.add(stage_name)
            for dependency in [str(item) for item in as_list(stage_by_name.get(stage_name, {}).get("depends_on"))]:
                if dependency in stage_by_name:
                    visit(dependency)
            visiting.remove(stage_name)
            visited.add(stage_name)

        for stage_name in stage_by_name:
            visit(stage_name)
        if profile_path.exists():
            for profile in profiles.get("profiles", []) if isinstance(profiles.get("profiles"), list) else []:
                for gate in as_list(profile.get("required_gate_artifacts")):
                    artifact_name = str(gate.get("artifact") or "") if isinstance(gate, dict) else ""
                    if artifact_name and artifact_name not in seen_artifacts:
                        blockers.append({"source": f"workflow_profile.{profile.get('name')}", "message": "required gate artifact is not registered in workflow stages", "artifact": artifact_name})
                if profile.get("profile_stage_mode") == "release_only":
                    continue
                if profile.get("profile_stage_mode") == "lightweight_pre_edit":
                    continue
                required_skills = {str(item) for item in as_list(profile.get("required_skills"))}
                impacts = {str(item) for item in as_list(profile.get("trigger_impacts"))}
                expected_artifacts = {str(item) for item in as_list(profile.get("expected_artifacts"))}
                applicable_artifacts: set[str] = set()
                for stage in stage_entries:
                    if not isinstance(stage, dict) or not stage.get("implementation_required"):
                        continue
                    conditional_skill = str(stage.get("conditional_skill") or "")
                    if conditional_skill and conditional_skill not in required_skills:
                        continue
                    conditional_impacts = {str(item) for item in as_list(stage.get("conditional_impacts"))}
                    if conditional_impacts and not conditional_impacts.intersection(impacts):
                        continue
                    applicable_artifacts.add(str(stage.get("artifact")))
                missing_expected = applicable_artifacts - expected_artifacts
                if missing_expected:
                    blockers.append({"source": f"workflow_profile.{profile.get('name')}", "message": "profile expected_artifacts omits applicable implementation stages", "artifacts": sorted(missing_expected)})
    expert_contract_count = sum(1 for item in expert_scores if item["level"] == "expert_contract")
    expert_level_count = sum(1 for item in expert_scores if item.get("expert_proven") is True)
    advanced_or_better_count = sum(1 for item in expert_scores if item["level"] in {"expert_proven", "expert_contract", "advanced"})
    content_quality_scores = [int(item.get("content_quality", {}).get("score") or 0) for item in expert_scores]
    content_quality_average = round(sum(content_quality_scores) / len(content_quality_scores), 2) if content_quality_scores else 0
    stage_blockers = [item for item in blockers if item.get("source") == "config/workflow-stages.example.yaml"]
    gate_blockers = [item for item in blockers if str(item.get("source") or "").startswith("workflow_profile.")]
    runtime_assessment = workflow_runtime_assessment(root, stage_entries)
    if runtime_assessment.get("decision") != "pass":
        blockers.append({
            "source": "workflow_runtime_assessment",
            "message": "synthetic happy/blocked paths or fail-closed runtime validation did not pass",
            "decision": runtime_assessment.get("decision"),
        })
    calibration = real_project_calibration(root)
    real_replay_count = int(calibration.get("count") or 0)
    real_replay_families = set(as_list(calibration.get("families")))
    real_replay_agreement = float(calibration.get("agreement_rate") or 0)
    framework_dimensions = {
        "skill_contract_quality": round(100 * advanced_or_better_count / len(skills), 2) if skills else 0,
        "dag_integrity": 100 if not stage_blockers else 0,
        "gate_semantics": 100 if not gate_blockers and runtime_assessment.get("fail_closed_stage_count") == runtime_assessment.get("stage_count") else 0,
        "happy_blocked_path_reality": 100 if runtime_assessment.get("decision") == "pass" else 0,
        "real_project_calibration": 100 if real_replay_count >= 3 and len(real_replay_families) >= 3 and real_replay_agreement >= 80 else 60 if real_replay_count else 0,
    }
    framework_overall = round(sum(framework_dimensions.values()) / len(framework_dimensions), 2)
    framework_level = "expert" if framework_overall >= 90 and real_replay_count >= 3 and len(real_replay_families) >= 3 and real_replay_agreement >= 80 else "advanced" if framework_overall >= 80 else "mixed"
    return {
        "schema": "codex-skill-health-v1",
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "skill_count": len(skills),
        "expert_level_count": expert_level_count,
        "expert_contract_count": expert_contract_count,
        "advanced_or_better_count": advanced_or_better_count,
        "content_quality_average": content_quality_average,
        "content_quality_expert_count": sum(1 for score in content_quality_scores if score >= 80),
        "expert_readiness": framework_level,
        "framework_expert_assessment": {
            "overall_score": framework_overall,
            "level": framework_level,
            "dimensions": framework_dimensions,
            "real_project_replay_count": real_replay_count,
            "real_project_replay_family_count": len(real_replay_families),
            "real_project_agreement_rate": real_replay_agreement,
            "replay_validation_decision": calibration.get("validation_decision"),
            "expert_rule": "expert requires overall>=90, three validated anonymized real-project replays across three scenario families, and >=80% expert/framework agreement",
        },
        "workflow_runtime_assessment": runtime_assessment,
        "integrated_quality_gates": {
            "artifact_schema_inventory": {
                "decision": schema_inventory.get("decision"),
                "blocker_count": len(as_list(schema_inventory.get("blockers"))),
                "warning_count": len(as_list(schema_inventory.get("warnings"))),
                "schema_count": schema_inventory.get("schema_count"),
            },
            "design_template_regression": {
                "decision": design_templates.get("decision"),
                "blocker_count": len(as_list(design_templates.get("blockers"))),
                "examples": design_templates.get("examples", []),
            },
            "public_script_leak_scan": {
                "decision": public_leaks.get("decision"),
                "finding_count": public_leaks.get("finding_count", 0),
                "findings": public_leaks.get("findings", []),
            },
        },
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
