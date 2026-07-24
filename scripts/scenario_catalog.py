#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "codex-scenario-catalog-v1"
PRE_EDIT_GATE = "Before editing, require technical_design.json, architecture_design.json, design_architecture_review.json with implementation_allowed=true, delivery_plan_review.json with implementation_allowed=true, Git fetch plus pull --ff-only evidence, and edit_permit.json. For direct edits, create write_guard_snapshot.json after the permit and require write_guard_audit.json before commit or push."
LIGHT_BUGFIX_GATE = "Light bugfix effective gates are reported in auto_run_summary.effective_workflow_controls and omit architecture/test-data gates unless confidence or API/data/UI/cross-repo/MQ/async/scheduler/task/job/cache/integration/security impact raises strictness."
WORKFLOW_GUIDE_MARKER_START = "<!-- GENERATED:WORKFLOW_PROFILES:START -->"
WORKFLOW_GUIDE_MARKER_END = "<!-- GENERATED:WORKFLOW_PROFILES:END -->"
SCENARIO_GUIDE_PATH = Path("docs/scenario-guide.md")
WORKFLOW_GUIDE_PATH = Path("docs/workflow-guide.md")
PROFILE_REGISTRY_PATH = Path("config/workflow-profiles.example.yaml")

SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "one_line_request",
        "label": "One-line request",
        "when": "A small user request arrives as one sentence or a short chat message.",
        "command": "python3 scripts/codex_eng.py auto --input requirement.md --out /tmp/codex-auto",
        "expected_profile": "small_feature-lite",
        "evidence": ["auto_run_summary.json", "domain_model_design.json", "architecture_framing.json", "technical_design.json", "architecture_design.json", "delivery_plan_review.json"],
        "next_step": "Read auto_run_summary.json for next_stage, readiness_blockers, and next_command. " + PRE_EDIT_GATE,
    },
    {
        "id": "long_prd",
        "label": "Long PRD",
        "when": "A copied PRD, Markdown document, or long requirement needs normalization before design.",
        "command": "python3 scripts/codex_eng.py auto --input prd.md --out /tmp/codex-auto",
        "expected_profile": "small_feature",
        "evidence": ["spec.json", "domain_model_design.json", "architecture_framing.json", "technical_design.json", "architecture_design.json", "delivery_plan.json"],
        "next_step": "Resolve open questions first; otherwise continue only with auto_run_summary.next_command. " + PRE_EDIT_GATE,
    },
    {
        "id": "bugfix",
        "label": "Bugfix",
        "when": "A defect or regression needs a lightweight but gated fix path.",
        "command": "python3 scripts/codex_eng.py auto --input bug.md --profile bugfix --out /tmp/codex-auto",
        "expected_profile": "bugfix",
        "evidence": ["spec.json", "technical_design.json", "test_design.json", "delivery_plan_review.json"],
        "next_step": "Add reproduction evidence, then follow auto_run_summary.effective_workflow_controls before any fix. " + LIGHT_BUGFIX_GATE,
    },
    {
        "id": "frontend_change",
        "label": "Frontend change",
        "when": "A page, route, form, table, export, or browser-visible behavior changes.",
        "command": "python3 scripts/codex_eng.py auto --input ui.md --profile frontend_change --out /tmp/codex-auto",
        "expected_profile": "frontend_change",
        "evidence": ["ui_ue_design.json", "ui_ue_review.json", "frontend_acceptance.json", "test_evidence_gate.json", "auto_run_summary.json"],
        "next_step": "UI/UE must name the concrete menu, route, button, form submit, table action, or dialog trigger and cover loading, empty, success, validation error, permission denied, and dependency error states. Replace template browser evidence with real frontend acceptance before review or release.",
    },
    {
        "id": "cross_repo_api",
        "label": "API or cross-repo change",
        "when": "A backend API, route contract, producer/consumer boundary, explicit cross_repo impact, or coordinated multi-repository change is required.",
        "command": "python3 scripts/codex_eng.py auto --input api.md --repo /path/to/repo --project project-name --out /tmp/codex-auto",
        "expected_profile": "cross_repo_api",
        "evidence": ["project_understanding/baseline_quality.json", "architecture_framing.json", "api_contract_design.json", "cross_repo_execution_graph.json", "cross_repo_readiness.json", "traceability_matrix.json", "delivery_plan_review.json"],
        "next_step": "Use project understanding, pre-technical framing, contract evidence, and cross-repo graph/readiness before delivery plan review; then use initial traceability evidence before implementation. " + PRE_EDIT_GATE,
    },
    {
        "id": "data_migration",
        "label": "Data migration",
        "when": "A database, migration, sensitive data, configuration, performance, or rollback-sensitive change is required.",
        "command": "python3 scripts/codex_eng.py auto --input data.md --profile data_migration --out /tmp/codex-auto",
        "expected_profile": "data_migration",
        "evidence": ["configuration_readiness.json", "data_security_review.json", "performance_review.json"],
        "next_step": "Complete real security, performance, configuration, rollback, and release evidence before implementation/release. " + PRE_EDIT_GATE,
    },
    {
        "id": "release_readiness",
        "label": "Release readiness",
        "when": "Implementation exists and the question is whether release is allowed.",
        "command": "python3 scripts/codex_eng.py auto --input release.md --profile release_readiness --out /tmp/codex-auto",
        "expected_profile": "release_readiness",
        "evidence": ["implementation_completion_gate.json", "post_change_implementation_report.json", "code_review_gate.json", "test_evidence_gate.json", "post_implementation_traceability_matrix.json", "release_gate.json"],
        "next_step": "Fill missing release artifacts and post-implementation traceability until release_gate.json returns go or conditional_go.",
    },
    {
        "id": "code_review",
        "label": "Code review",
        "when": "A diff exists and needs design-quality, risk, test, and release evidence review.",
        "command": "git diff > /tmp/codex.diff && python3 scripts/codex_eng.py run diff-impact --diff-file /tmp/codex.diff --out /tmp/codex-diff-impact.json",
        "expected_profile": "review_gates",
        "evidence": ["diff_impact.json", "code_review_gate.json", "test_evidence_gate.json"],
        "next_step": "Bind diff impact, write guard, code review, test, CI, and release evidence before approval.",
    },
]

WORKFLOW_PROFILE_GUIDE: dict[str, str] = {
    "bugfix-lite": "`requirement-document-ingestor -> spec-governor -> requirement-question-governor -> technical-design-governor -> test-design-governor -> delivery-plan-templates -> delivery-plan-reviewer -> git-worktree-governor -> edit-readiness-governor`; use only when the requirement stays single-scope and does not introduce API, UI, cross-repo, data, permission, or runtime integration impact.",
    "bugfix": "`requirement-document-ingestor -> spec-governor -> requirement-question-governor -> technical-design-governor -> test-design-governor -> design-architecture-reviewer -> test-data-governor -> delivery-plan-templates -> traceability-governor initial pass -> delivery-plan-reviewer -> git-worktree-governor -> edit-readiness-governor`; API/data/UI/cross-repo/MQ/async/scheduler/task/job/cache/integration/permission/security signals elevate above the light path.",
    "small_feature-lite": "`requirement-document-ingestor -> spec-governor -> requirement-question-governor -> technical-design-governor -> architecture-design-governor -> design-architecture-reviewer -> test-design-governor -> delivery-plan-templates -> delivery-plan-reviewer -> git-worktree-governor -> edit-readiness-governor`; use only for a small single-scope request with no declared API, UI, cross-repo, data, permission, or runtime integration impact.",
    "small_feature": "Standard design-first profile, then Git/edit readiness gates.",
    "frontend_change": "Standard design-first profile plus pre-technical `ui-ue-design-governor`, `ui-ue-reviewer`, and `frontend-implementation-planner`. Real `frontend-acceptance-runner -> test-evidence-gate` evidence is collected after implementation, before release. UI/UE design must name concrete user entry surfaces and cover loading, empty, success, validation error, permission denied, and dependency error states.",
    "cross_repo_api": "API/cross-repo contract profile with project understanding, pre-technical API/observability design, delivery plan, cross-repo execution graph/readiness before delivery plan review, initial traceability, and release evidence gates.",
    "data_migration": "Standard design-first profile plus configuration, security, and performance design gates before design approval; release gates run only after implementation evidence exists.",
    "release_readiness": "`implementation-completion-gate -> post-change-skill-sync -> workspace-write-guard audit -> diff-impact-analyzer -> change-risk-governor -> evidence-auto-collector -> code-design-quality-reviewer -> frontend-acceptance-runner when UI changed -> test-evidence-gate -> post-implementation traceability -> code-review-gate -> environment-promotion-governor -> uat-acceptance-governor -> release-change-governor -> release-evidence-binder`.",
}

SCENARIO_PROFILE_MAP: dict[str, str] = {
    "one_line_request": "small_feature-lite",
    "long_prd": "small_feature",
    "bugfix": "bugfix",
    "frontend_change": "frontend_change",
    "cross_repo_api": "cross_repo_api",
    "data_migration": "data_migration",
    "release_readiness": "release_readiness",
}

SCENARIO_OVERRIDES: dict[str, dict[str, list[str]]] = {
    "bugfix": {
        "required_gates": [
            "spec.json",
            "requirement_ingestion.json",
            "open_questions.json",
            "technical_design.json",
            "test_design.json",
            "test_data_plan.json",
            "traceability_matrix.json",
            "delivery_plan_review.json",
            "harness_validation.json",
            "docs_quality.json",
            "git_worktree_evidence.json",
            "edit_permit.json",
            "write_guard_snapshot.json",
        ],
    },
    "long_prd": {"extra_skills": ["human-doc-reviewer"]},
    "frontend_change": {"extra_skills": ["human-doc-reviewer"]},
    "code_review": {
        "required_skills": ["diff-impact-analyzer", "code-design-quality-reviewer", "code-review-gate", "test-evidence-gate"],
        "required_gates": ["diff_impact.json", "write_guard_audit.json", "code_review_gate.json", "test_evidence_gate.json"],
    },
}


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


def workflow_profiles(root: Path | None = None) -> dict[str, dict[str, Any]]:
    repo_root = root or Path(__file__).resolve().parents[1]
    data = load_restricted_yaml(repo_root / PROFILE_REGISTRY_PATH)
    profiles = {}
    for item in as_list(data.get("profiles")):
        if isinstance(item, dict) and item.get("name"):
            profiles[str(item["name"])] = item
    return profiles


def unique_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def scenario_requirements(scenario_id: str, root: Path | None = None) -> dict[str, list[str]]:
    overrides = SCENARIO_OVERRIDES.get(scenario_id, {})
    profile_name = SCENARIO_PROFILE_MAP.get(scenario_id, "")
    profile = workflow_profiles(root).get(profile_name, {})
    required_skills = list(overrides.get("required_skills", [str(item) for item in as_list(profile.get("required_skills"))]))
    required_skills.extend(str(item) for item in overrides.get("extra_skills", []))
    derived_gates = [
        str(gate.get("artifact"))
        for gate in as_list(profile.get("required_gate_artifacts"))
        if isinstance(gate, dict) and gate.get("artifact")
    ]
    required_gates = list(overrides.get("required_gates", derived_gates))
    return {
        "required_skills": unique_preserve(required_skills),
        "required_gates": unique_preserve(required_gates),
    }


def catalog() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "scenario_count": len(SCENARIOS),
        "scenarios": SCENARIOS,
        "coverage_matrix": [
            {
                "scenario_id": item["id"],
                "expected_profile": item["expected_profile"],
                "required_skills": scenario_requirements(item["id"]).get("required_skills", []),
                "required_gates": scenario_requirements(item["id"]).get("required_gates", []),
                "anti_bypass": [
                    "no implementation before design review and delivery plan review pass",
                    "no implementation before test_design.json exists",
                    "no implementation before test_data_plan.json exists",
                    "no implementation before docs_quality.json is pass/ready",
                    "no implementation before git fetch and pull --ff-only evidence exists",
                    "no direct edits outside edit_permit.json and write_guard evidence",
                ] if item["id"] not in {"release_readiness", "code_review"} else [
                    "no release approval without implementation, review, test, CI, environment, UAT, and release evidence",
                    "no approval when blockers remain active",
                ],
            }
            for item in SCENARIOS
        ],
    }


def render_markdown() -> str:
    lines = [
        "# Scenario Guide",
        "",
        "Use this guide to choose the smallest safe command for common engineering requests.",
        "",
        "| Scenario | Use When | Start Command | Key Evidence | Next Step |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in SCENARIOS:
        evidence = ", ".join(f"`{name}`" for name in item["evidence"])
        lines.append(
            f"| `{item['id']}` {item['label']} | {item['when']} | `{item['command']}` | {evidence} | {item['next_step']} |"
        )
    lines.extend([
        "",
        "## Coverage Matrix",
        "",
        "| Scenario | Required Skills | Required Gates |",
        "| --- | --- | --- |",
    ])
    for row in catalog()["coverage_matrix"]:
        skills = ", ".join(f"`{name}`" for name in row["required_skills"])
        gates = ", ".join(f"`{name}`" for name in row["required_gates"])
        lines.append(f"| `{row['scenario_id']}` | {skills} | {gates} |")
    lines.extend([
        "",
        "For normal requirement handling, prefer `python3 scripts/codex_eng.py auto --input requirement.md` first.",
        "Use explicit `--profile` only when the scenario is already known or the automatic profile choice needs to be constrained.",
        f"Pre-edit gate: {PRE_EDIT_GATE}",
    ])
    return "\n".join(lines) + "\n"


def render_workflow_profile_markdown() -> str:
    profiles = workflow_profiles()
    lines = [
        "## Workflow Profiles",
        "",
        "| Scenario | Required path |",
        "| --- | --- |",
    ]
    for name in [item["expected_profile"] for item in SCENARIOS if item["expected_profile"] in WORKFLOW_PROFILE_GUIDE]:
        if name in profiles:
            lines.append(f"| `{name}` | {WORKFLOW_PROFILE_GUIDE[name]} |")
    lines.extend([
        "",
        "Profiles use schema `codex-workflow-profiles-v3` and select scenario skills and impacts; they do not define execution order. Stage order, schemas, required fields, decisions, dependencies, lineage inputs, Runtime gates, conditional skills, conditional impacts, and next commands are defined by the `codex-workflow-stages-v4` registry in `config/workflow-stages.example.yaml`.",
    ])
    return "\n".join(lines) + "\n"


def replace_marked_section(text: str, start_marker: str, end_marker: str, replacement: str) -> str:
    pattern = re.compile(rf"{re.escape(start_marker)}.*?{re.escape(end_marker)}", flags=re.DOTALL)
    block = f"{start_marker}\n{replacement.rstrip()}\n{end_marker}"
    if pattern.search(text):
        return pattern.sub(block, text)
    return text


def sync_docs(root: Path | None = None) -> list[Path]:
    repo_root = root or Path(__file__).resolve().parents[1]
    updated: list[Path] = []
    scenario_path = repo_root / SCENARIO_GUIDE_PATH
    workflow_path = repo_root / WORKFLOW_GUIDE_PATH

    scenario_content = render_markdown()
    if not scenario_path.exists() or scenario_path.read_text(encoding="utf-8") != scenario_content:
        scenario_path.write_text(scenario_content, encoding="utf-8")
        updated.append(scenario_path)

    workflow_text = workflow_path.read_text(encoding="utf-8")
    replaced = replace_marked_section(workflow_text, WORKFLOW_GUIDE_MARKER_START, WORKFLOW_GUIDE_MARKER_END, render_workflow_profile_markdown())
    if replaced != workflow_text:
        workflow_path.write_text(replaced, encoding="utf-8")
        updated.append(workflow_path)
    return updated


def write_markdown(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="List documented Codex engineering workflow scenarios")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--out")
    parser.add_argument("--sync-docs", action="store_true")
    args = parser.parse_args()
    if args.sync_docs:
        updated = sync_docs()
        print(json.dumps({"updated": [str(path) for path in updated]}, ensure_ascii=False, indent=2))
        return 0
    if args.format == "markdown":
        output = render_markdown()
        if args.out:
            Path(args.out).write_text(output, encoding="utf-8")
        print(output, end="")
        return 0
    data = catalog()
    if args.out:
        Path(args.out).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
