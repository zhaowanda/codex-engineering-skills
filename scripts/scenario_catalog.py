#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-scenario-catalog-v1"
PRE_EDIT_GATE = "Before editing, require technical_design.json, architecture_design.json, design_architecture_review.json with implementation_allowed=true, delivery_plan_review.json with implementation_allowed=true, Git fetch plus pull --ff-only evidence, and edit_permit.json. For direct edits, create write_guard_snapshot.json after the permit and require write_guard_audit.json before commit or push."

SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "one_line_request",
        "label": "One-line request",
        "when": "A small user request arrives as one sentence or a short chat message.",
        "command": "python3 scripts/codex_eng.py auto --input requirement.md --out /tmp/codex-auto",
        "expected_profile": "small_feature",
        "evidence": ["auto_run_summary.json", "technical_design.json", "architecture_design.json", "delivery_plan_review.json"],
        "next_step": "Read auto_run_summary.json for next_stage, readiness_blockers, and next_command. " + PRE_EDIT_GATE,
    },
    {
        "id": "long_prd",
        "label": "Long PRD",
        "when": "A copied PRD, Markdown document, or long requirement needs normalization before design.",
        "command": "python3 scripts/codex_eng.py auto --input prd.md --out /tmp/codex-auto",
        "expected_profile": "small_feature",
        "evidence": ["spec.json", "technical_design.json", "architecture_design.json", "delivery_plan.json"],
        "next_step": "Resolve open questions first; otherwise continue only with auto_run_summary.next_command. " + PRE_EDIT_GATE,
    },
    {
        "id": "bugfix",
        "label": "Bugfix",
        "when": "A defect or regression needs a lightweight but gated fix path.",
        "command": "python3 scripts/codex_eng.py auto --input bug.md --profile bugfix --out /tmp/codex-auto",
        "expected_profile": "bugfix",
        "evidence": ["spec.json", "technical_design.json", "architecture_design.json", "delivery_plan_review.json"],
        "next_step": "Add reproduction evidence, then follow the pre-edit gate before any fix. " + PRE_EDIT_GATE,
    },
    {
        "id": "frontend_change",
        "label": "Frontend change",
        "when": "A page, route, form, table, export, or browser-visible behavior changes.",
        "command": "python3 scripts/codex_eng.py auto --input ui.md --profile frontend_change --out /tmp/codex-auto",
        "expected_profile": "frontend_change",
        "evidence": ["frontend_acceptance.json", "test_evidence_gate.json", "auto_run_summary.json"],
        "next_step": "Replace template browser evidence with real frontend acceptance before review or release. " + PRE_EDIT_GATE,
    },
    {
        "id": "cross_repo_api",
        "label": "API or cross-repo change",
        "when": "A backend API, route contract, producer/consumer boundary, or existing repository context matters.",
        "command": "python3 scripts/codex_eng.py auto --input api.md --repo /path/to/repo --project project-name --out /tmp/codex-auto",
        "expected_profile": "cross_repo_api",
        "evidence": ["project_understanding/baseline_quality.json", "technical_design.json", "architecture_design.json", "delivery_plan_review.json"],
        "next_step": "Use project understanding and traceability evidence before implementation. " + PRE_EDIT_GATE,
    },
    {
        "id": "data_migration",
        "label": "Data migration",
        "when": "A database, migration, sensitive data, configuration, performance, or rollback-sensitive change is required.",
        "command": "python3 scripts/codex_eng.py auto --input data.md --profile data_migration --out /tmp/codex-auto",
        "expected_profile": "data_migration",
        "evidence": ["configuration_readiness.json", "data_security_review.json", "performance_review.json", "release_gate.json"],
        "next_step": "Complete real security, performance, configuration, rollback, and release evidence before implementation/release. " + PRE_EDIT_GATE,
    },
    {
        "id": "release_readiness",
        "label": "Release readiness",
        "when": "Implementation exists and the question is whether release is allowed.",
        "command": "python3 scripts/codex_eng.py auto --input release.md --profile release_readiness --out /tmp/codex-auto",
        "expected_profile": "release_readiness",
        "evidence": ["implementation_completion_gate.json", "code_review_gate.json", "test_evidence_gate.json", "release_gate.json"],
        "next_step": "Fill missing release artifacts until release_gate.json returns go or conditional_go.",
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


CORE_PRE_EDIT_GATES = [
    "technical_design.json",
    "architecture_design.json",
    "test_design.json",
    "design_architecture_review.json",
    "delivery_plan_review.json",
    "docs_quality.json",
    "git_worktree_evidence.json",
    "edit_permit.json",
]


SCENARIO_MATRIX: dict[str, dict[str, Any]] = {
    "one_line_request": {
        "required_skills": ["spec-governor", "technical-design-governor", "architecture-design-governor", "test-design-governor", "delivery-plan-reviewer"],
        "required_gates": CORE_PRE_EDIT_GATES,
    },
    "long_prd": {
        "required_skills": ["requirement-question-governor", "technical-design-governor", "architecture-design-governor", "test-design-governor", "human-doc-reviewer"],
        "required_gates": CORE_PRE_EDIT_GATES,
    },
    "bugfix": {
        "required_skills": ["spec-governor", "technical-design-governor", "test-design-governor", "git-worktree-governor", "edit-readiness-governor"],
        "required_gates": CORE_PRE_EDIT_GATES,
    },
    "frontend_change": {
        "required_skills": ["frontend-acceptance-runner", "test-evidence-gate", "human-doc-reviewer"],
        "required_gates": CORE_PRE_EDIT_GATES + ["frontend_acceptance.json", "test_evidence_gate.json"],
    },
    "cross_repo_api": {
        "required_skills": ["project-understanding-runner", "traceability-governor", "api-surface-extractor", "delivery-plan-reviewer"],
        "required_gates": ["project_understanding/baseline_quality.json"] + CORE_PRE_EDIT_GATES,
    },
    "data_migration": {
        "required_skills": ["configuration-governor", "data-security-governor", "performance-governor", "release-evidence-binder"],
        "required_gates": CORE_PRE_EDIT_GATES + ["configuration_readiness.json", "data_security_review.json", "performance_review.json", "release_gate.json"],
    },
    "release_readiness": {
        "required_skills": ["implementation-completion-gate", "code-review-gate", "test-evidence-gate", "release-evidence-binder"],
        "required_gates": ["implementation_completion_gate.json", "code_review_gate.json", "test_evidence_gate.json", "ci_execution_evidence.json", "release_gate.json"],
    },
    "code_review": {
        "required_skills": ["diff-impact-analyzer", "code-design-quality-reviewer", "code-review-gate", "test-evidence-gate"],
        "required_gates": ["diff_impact.json", "write_guard_audit.json", "code_review_gate.json", "test_evidence_gate.json"],
    },
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
                "required_skills": SCENARIO_MATRIX.get(item["id"], {}).get("required_skills", []),
                "required_gates": SCENARIO_MATRIX.get(item["id"], {}).get("required_gates", []),
                "anti_bypass": [
                    "no implementation before design review and delivery plan review pass",
                    "no implementation before test_design.json exists",
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


def write_markdown(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="List documented Codex engineering workflow scenarios")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--out")
    args = parser.parse_args()
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
