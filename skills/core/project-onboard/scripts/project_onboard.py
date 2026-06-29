#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-project-onboard-v1"
REGISTRY_SCHEMA = "codex-project-registry-v1"
REFERENCE_NAMES = [
    "business-boundary.md",
    "feature-map.md",
    "api-map.md",
    "code-index.md",
    "change-playbook.md",
    "contract-patterns.json",
    "validation-recipes.md",
    "pitfalls.md",
    "Project edit gate",
    "review-cases.md",
]


REFERENCE_FILES = {
    "business-boundary.md": """# Business Boundary

## Executive Summary

- Project: {project}
- Type: {project_type}
- Repository key: {project}
- Git URL: {git_url}

## Business Boundary Model

- Business capabilities owned:
- External business capabilities consumed:
- User roles:
- Tenant / organization boundary:
- Data ownership:
- Reporting / export boundary:
- Permission boundary:
- Operational owner:

## In Scope

- Document the business capabilities owned by this project.
- Record user roles, data ownership, and workflow boundaries.
- Link to feature-map.md for concrete feature ownership.

## Out Of Scope

- Do not store secrets, customer data, production credentials, or private incident details.
- Do not duplicate full source files; keep this as project knowledge and routing guidance.

## Expert Review Checklist

- Boundary decisions are explicit enough to reject unrelated requirements.
- Data ownership and permission assumptions are written before design.
- Cross-project dependencies identify producer and consumer ownership.
""",
    "feature-map.md": """# Feature Map

## Features

| Feature | Owner Module | Entry Points | Notes |
|---|---|---|---|
| To be filled | To be filled from project understanding | To be filled | Keep entries concise |

## Routing Rules

- Use this file to map requirements to modules before broad source reads.
- Prefer code-index.md for file-level lookup hints.
- Every common requirement should route to an owner module or an explicit open question.
- Feature ownership must be updated after major refactors.

## Expert Review Checklist

- Feature names are business-facing, not only folder names.
- Entry points identify pages, routes, jobs, commands, or APIs.
- Ambiguous ownership is marked before planning implementation.
""",
    "api-map.md": """# API Map

## API / Route Surface

| Method | Route / Contract | File | Producer | Consumer | Notes |
|---|---|---|---|---|---|
| To be filled | To be filled from api_surface.json | To be filled | To be filled | To be filled | Keep private |

## Rules

- Record endpoint and contract hints only.
- Do not store real tokens, payloads with customer data, or private hostnames.
- Identify compatibility expectations for changed contracts.
- Mark producer/consumer direction before editing APIs.

## Expert Review Checklist

- API changes identify backward compatibility and rollout risks.
- Frontend/backend contracts include validation and error behavior.
- External integration contracts avoid private credentials and sample real data.
""",
    "code-index.md": """# Code Index

## Index Location

- Canonical index: {index_path}
- Refresh command: `python3 scripts/codex_eng.py project {project_mode} --project {project} --repo <local-checkout> --type {project_type} --overlay-root <private-overlay> --git-url {git_url}`

## Read-First Hints

- Add high-value files and directories for common changes.
- Link generated private code index artifacts instead of copying full source.

## Generated Artifacts

- {index_path}: private generated index from code-index-builder.
- baseline/{project}.baseline.json: private generated baseline from project-baseline-reverser.

## Expert Search Protocol

- Start with this reference before broad `rg`.
- Use code-index-lookup for symbol, route, page, service, and business keyword searches.
- Refresh the canonical index after large renames, route changes, generated code changes, or dependency layout changes.
- Never copy full source snippets into project skill references.
""",
    "change-playbook.md": """# Change Playbook

## Standard Change Flow

1. Run auto-runner with this project repository and project name.
2. Review generated spec, designs, test design, and delivery plan.
3. Run project edit gate before source edits.
4. Run project validation recipes before review.
5. Refresh code index when the implementation changes navigation-relevant files.

## Common Change Types

- Bugfix:
- Small feature:
- Configuration change:
- Frontend change:
- Release-only change:

## Expert Delivery Rules

- Requirement normalization must identify scope, acceptance criteria, non-goals, risks, and open questions.
- Design must cover process flow, data flow, module boundary, contract impact, failure modes, and rollout.
- Plans must name allowed files, read-first files, tests, owner decisions, and stop conditions.
""",
    "contract-patterns.json": """{{
  "schema": "codex-project-contract-patterns-v1",
  "project": "{project}",
  "contracts": [],
  "compatibility_rules": [],
  "routing_rules": [],
  "validation_rules": [],
  "private_data_policy": "Do not store secrets, credentials, customer data, or private hostnames in this file."
}}
""",
    "validation-recipes.md": """# Validation Recipes

## Commands

- Build: To be filled
- Test: To be filled
- Lint: To be filled
- Type check: To be filled
- Browser/API acceptance: To be filled
- Release smoke: To be filled

## Evidence Rules

- Capture command, exit code, and relevant output.
- Link browser or API evidence when user-visible behavior changes.
- State what was not run and why.
- Prefer project-native commands over generic smoke checks.

## Expert Validation Matrix

| Change Type | Required Evidence | Optional Evidence | Stop Condition |
|---|---|---|---|
| Bugfix | Reproduction plus regression test | Log or screenshot | Cannot reproduce |
| Frontend | Browser acceptance | Visual diff | Route not reachable |
| Backend/API | Unit/integration test | Contract test | Compatibility unknown |
| Config | Config diff review | Environment smoke | Secret or env gap |
| Release | Smoke and rollback check | Monitoring check | Rollback owner missing |
""",
    "pitfalls.md": """# Pitfalls

## Known Risks

- Add project-specific traps, fragile modules, migration hazards, flaky tests, and rollback concerns.
- Add hidden coupling, permission pitfalls, time zone issues, cache invalidation, data migration risks, and browser compatibility concerns.

## Guardrails

- Keep entries actionable.
- Include detection signals and safe remediation steps.

## Expert Risk Format

| Risk | Detection Signal | Safe Action | Owner / Review Area |
|---|---|---|---|
| To be filled | To be filled | To be filled | To be filled |
""",
    "Project edit gate": """# Project Edit Gate

## Required Before Editing

- Confirm requirement doc id.
- Confirm target repository and branch.
- Confirm generated spec/design/plan artifacts.
- Confirm allowed files and read-first files.
- Confirm validation commands.
- Confirm code index freshness or refresh it.
- Confirm project registry entry matches the local repo path.
- Confirm private references have been read for the touched area.

## Stop Conditions

- Missing repo path.
- Dirty worktree not related to current task.
- Edit outside allowed file scope.
- Open product/security/configuration blockers.
- Project skill references are missing or stale for the touched area.
- Requirement, design, or plan is too vague to verify implementation.
""",
    "review-cases.md": """# Review Cases

## Cases

| Case | Change Type | Files | Validation | Outcome |
|---|---|---|---|---|
| To be filled | To be filled | To be filled | To be filled | To be filled |

## Usage

- Capture reusable project-specific review examples.
- Keep sensitive details anonymized or private to the overlay.
- Include missed-review examples when bugs escape.
- Link each case to validation evidence and a prevention rule.

## Expert Review Dimensions

- Requirement fit
- Design boundary
- Contract compatibility
- Security and data handling
- Performance and scale
- Test evidence
- Release and rollback readiness
""",
}


def skill_md(project: str, project_type: str, git_url: str) -> str:
    return f"""---
name: {project}
description: Project-specific overlay skill for {project}. Use when a requirement is routed to this {project_type} repository; load references before planning or editing this project.
---

# {project}

Use this private project skill only after the requirement is routed to this repository.

## Repository

- Key: {project}
- Git URL: {git_url}
- Type: {project_type}
- Local checkout: resolve from `projects.yaml` or the current task workspace; do not store local absolute paths in this skill.

## Required References

Read the relevant files under `references/` before design, planning, implementation, review, or release work:

- `business-boundary.md`: business ownership, in/out of scope, roles, and data boundaries.
- `feature-map.md`: feature-to-module routing hints.
- `api-map.md`: API, route, and contract surface hints.
- `code-index.md`: read-first files and generated private index references.
- `change-playbook.md`: project-specific change workflow.
- `contract-patterns.json`: machine-readable contract and compatibility hints.
- `validation-recipes.md`: build, test, lint, browser, and release evidence commands.
- `pitfalls.md`: known traps, fragile paths, and rollback risks.
- `Project edit gate`: project-specific pre-edit stop conditions.
- `review-cases.md`: reusable review examples and expected evidence.

## Rules

- Keep generated indexes, baseline docs, API maps, and business semantics in the private overlay.
- Do not copy private project references into the open-core repository.
- For broad or ambiguous work, run `auto-runner` with this project repository before implementation.
- Run the project edit gate before source, config, test, or documentation edits.
- Start code search from `references/code-index.md` and the canonical private index before broad repository reads.
- Keep `projects.yaml`, the project skill, and the canonical code index synchronized.
"""


def render_template(template: str, values: dict[str, str]) -> str:
    return template.format(**values)


def write_references(
    skill_dir: Path,
    project: str,
    project_type: str,
    mode: str,
    git_url: str,
) -> list[str]:
    references = skill_dir / "references"
    references.mkdir(parents=True, exist_ok=True)
    values = {
        "project": project,
        "project_type": project_type,
        "project_mode": mode,
        "git_url": git_url,
        "index_path": f"indexes/{project}.code_index.json",
    }
    written: list[str] = []
    for name in REFERENCE_NAMES:
        template = REFERENCE_FILES[name]
        path = references / name
        path.write_text(render_template(template, values), encoding="utf-8")
        written.append(str(path))
    return written


def yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def registry_entry(
    project: str,
    project_type: str,
    default_branch: str,
    git_url: str,
    dependencies: list[str] | None = None,
    local_path_hint: str = "",
) -> dict[str, Any]:
    return {
        "name": project,
        "type": project_type,
        "default_branch": default_branch,
        "skill": project,
        "repo": {
            "git_url": git_url,
            "default_branch": default_branch,
            "local_path_hint": local_path_hint,
        },
        "roles": [project_type],
        "dependencies": dependencies or [],
        "related_projects": dependencies or [],
        "test_strategy": "",
        "assets": {
            "skill": f"skills/{project}/SKILL.md",
            "references": f"skills/{project}/references",
            "index": f"indexes/{project}.code_index.json",
            "baseline": f"baseline/{project}.baseline.json",
        },
    }


def read_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema": REGISTRY_SCHEMA, "projects": []}
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            projects = data.get("projects", [])
            data["projects"] = projects if isinstance(projects, list) else []
            data.setdefault("schema", REGISTRY_SCHEMA)
            return data
    except Exception:
        pass
    projects: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if stripped.startswith("- name:"):
            if current:
                projects.append(current)
            current = {"name": stripped.split(":", 1)[1].strip().strip('"')}
        elif current is not None and ":" in stripped and not stripped.startswith("- "):
            key, value = stripped.split(":", 1)
            current[key.strip()] = value.strip().strip('"')
    if current:
        projects.append(current)
    return {"schema": REGISTRY_SCHEMA, "projects": projects}


def write_registry(path: Path, entry: dict[str, Any]) -> None:
    registry = read_registry(path)
    projects = [item for item in registry.get("projects", []) if isinstance(item, dict) and item.get("name") != entry["name"]]
    projects.append(entry)
    projects.sort(key=lambda item: str(item.get("name", "")))
    lines = [f"schema: {yaml_quote(REGISTRY_SCHEMA)}", "projects:"]
    for item in projects:
        name = str(item.get("name", ""))
        repo = item.get("repo", {}) if isinstance(item.get("repo"), dict) else {}
        git_url = str(repo.get("git_url") or item.get("git_url") or item.get("root") or "")
        local_path_hint = str(repo.get("local_path_hint") or item.get("local_path_hint") or "")
        assets = item.get("assets", {}) if isinstance(item.get("assets"), dict) else {}
        dependencies = item.get("dependencies", item.get("related_projects", []))
        dependency_items = dependencies if isinstance(dependencies, list) else [dependencies]
        lines.extend(
            [
                f"  - name: {yaml_quote(name)}",
                f"    type: {yaml_quote(str(item.get('type', '')))}",
                f"    default_branch: {yaml_quote(str(item.get('default_branch', 'main')))}",
                f"    skill: {yaml_quote(str(item.get('skill', item.get('name', ''))))}",
                "    repo:",
                f"      git_url: {yaml_quote(git_url)}",
                f"      default_branch: {yaml_quote(str(item.get('default_branch', 'main')))}",
                f"      local_path_hint: {yaml_quote(local_path_hint)}",
                "    roles:",
            ]
        )
        for role in item.get("roles", []) if isinstance(item.get("roles"), list) else [item.get("type", "other")]:
            lines.append(f"      - {yaml_quote(str(role))}")
        non_empty_dependencies = [dependency for dependency in dependency_items if dependency]
        if non_empty_dependencies:
            lines.append("    dependencies:")
            for dependency in non_empty_dependencies:
                lines.append(f"      - {yaml_quote(str(dependency))}")
        else:
            lines.append("    dependencies: []")
        lines.extend(
            [
                f"    test_strategy: {yaml_quote(str(item.get('test_strategy', '')))}",
                "    assets:",
                f"      skill: {yaml_quote(str(assets.get('skill', f'skills/{name}/SKILL.md')))}",
                f"      references: {yaml_quote(str(assets.get('references', f'skills/{name}/references')))}",
                f"      index: {yaml_quote(str(assets.get('index', f'indexes/{name}.code_index.json')))}",
                f"      baseline: {yaml_quote(str(assets.get('baseline', f'baseline/{name}.baseline.json')))}",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def onboard(
    project: str,
    repo: str,
    project_type: str,
    overlay_root: Path,
    default_branch: str,
    mode: str = "new",
    write_registry_file: bool = True,
    git_url: str | None = None,
    dependencies: list[str] | None = None,
) -> dict[str, Any]:
    skill_dir = overlay_root / "skills" / project
    skill_dir.mkdir(parents=True, exist_ok=True)
    repo_path = Path(repo)
    repo_name = repo_path.name if repo else project
    resolved_git_url = git_url or repo_name
    local_path_hint = repo_name
    (skill_dir / "SKILL.md").write_text(skill_md(project, project_type, resolved_git_url), encoding="utf-8")
    references = write_references(skill_dir, project, project_type, mode, resolved_git_url)
    entry = registry_entry(project, project_type, default_branch, resolved_git_url, dependencies, local_path_hint)
    registry_path = overlay_root / "projects.yaml"
    if write_registry_file:
        write_registry(registry_path, entry)
    assets = entry["assets"]
    manifest = {
        "schema": SCHEMA,
        "project": project,
        "mode": mode,
        "skill_path": str(skill_dir / "SKILL.md"),
        "reference_dir": str(skill_dir / "references"),
        "reference_files": references,
        "registry_path": str(registry_path),
        "registry_entry": entry,
        "index_path": str(overlay_root / assets["index"]),
        "baseline_path": str(overlay_root / assets["baseline"]),
        "relative_assets": assets,
        "local_repo_used_for_generation": str(repo),
        "next_action": "Fill expert project references, refresh the code index, and validate overlay health.",
    }
    out = overlay_root / "onboarding" / f"{project}.onboard.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Onboard project into private overlay")
    parser.add_argument("--project", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--type", required=True)
    parser.add_argument("--overlay-root", required=True)
    parser.add_argument("--default-branch", default="main")
    parser.add_argument("--mode", choices=["new", "legacy"], default="new")
    parser.add_argument("--no-write-registry", action="store_true")
    parser.add_argument("--git-url")
    parser.add_argument("--depends-on", action="append", default=[])
    args = parser.parse_args()
    result = onboard(
        args.project,
        args.repo,
        args.type,
        Path(args.overlay_root),
        args.default_branch,
        mode=args.mode,
        write_registry_file=not args.no_write_registry,
        git_url=args.git_url,
        dependencies=args.depends_on,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
