#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
DIRS = ["human/specs", "human/designs", "human/releases", "machine/specs", "machine/designs", "machine/reviews", "machine/releases", "baseline", "indexes"]
MACHINE_ARTIFACTS = {
    "spec": ("machine/specs", ".spec.json"),
    "design": ("machine/designs", ".design.json"),
    "review": ("machine/reviews", ".review.json"),
    "release": ("machine/releases", ".release.json"),
}


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


def write_text_if_missing(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        path.write_text(text, encoding="utf-8")


def markdown_template(doc_id: str, title: str, kind: str) -> str:
    heading = title or doc_id
    return (
        f"# {heading} {kind}\n\n"
        f"- doc_id: `{doc_id}`\n"
        "- status: initialized\n"
        "- source: docs-governor\n\n"
        "## Summary\n\n"
        "Pending delivery artifact sync.\n\n"
        "## Traceability\n\n"
        "- Requirement, design, review, and release evidence must remain linked by doc_id.\n"
    )


def placeholder_artifact(doc_id: str, artifact_type: str) -> dict[str, Any]:
    return {
        "schema": "codex-docs-machine-placeholder-v1",
        "doc_id": doc_id,
        "artifact_type": artifact_type,
        "status": "initialized",
        "source": "docs-governor",
        "rule": "Replace this placeholder through docs-governor sync after delivery artifacts are generated.",
    }


def materialize_doc_files(docs_root: Path, doc_id: str, title: str = "") -> dict[str, list[str]]:
    human_paths = {
        "spec": docs_root / "human/specs" / f"{doc_id}.md",
        "design": docs_root / "human/designs" / f"{doc_id}.md",
        "release": docs_root / "human/releases" / f"{doc_id}.md",
    }
    machine_paths = {
        name: docs_root / directory / f"{doc_id}{suffix}"
        for name, (directory, suffix) in MACHINE_ARTIFACTS.items()
    }
    for name, path in human_paths.items():
        write_text_if_missing(path, markdown_template(doc_id, title, name))
    for name, path in machine_paths.items():
        if not path.exists() or not path.read_text(encoding="utf-8").strip():
            write_json(path, placeholder_artifact(doc_id, name))
    return {
        "human_docs": [str(path.relative_to(docs_root)) for path in human_paths.values()],
        "machine_artifacts": [str(path.relative_to(docs_root)) for path in machine_paths.values()],
    }


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def text(value: Any, default: str = "TBD") -> str:
    if value in (None, "", [], {}):
        return default
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return ", ".join(text(item, default) for item in value) or default
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def bullet_lines(items: list[str], empty: str = "TBD") -> str:
    compact = [item for item in items if item]
    if not compact:
        return f"- {empty}"
    return "\n".join(item if item.lstrip().startswith("- ") else f"- {item}" for item in compact)


def render_scope(spec: dict[str, Any], fallback: str) -> str:
    scope = spec.get("scope")
    if not isinstance(scope, dict):
        return fallback
    lines: list[str] = []
    for label, key in [("In scope", "in_scope"), ("Out of scope", "out_of_scope"), ("Assumptions", "assumptions"), ("Non-goals", "non_goals")]:
        values = [str(item) for item in as_list(scope.get(key))]
        if values:
            lines.append(f"- {label}: {', '.join(values)}")
    return "\n".join(lines) if lines else f"- {fallback}"


def render_acceptance(spec: dict[str, Any]) -> str:
    lines: list[str] = []
    for item in as_list(spec.get("acceptance_criteria")):
        if not isinstance(item, dict):
            continue
        evidence = ", ".join(str(value) for value in as_list(item.get("evidence_required"))) or "TBD"
        lines.append(f"`{text(item.get('id'))}` {text(item.get('criteria'))} ({text(item.get('type'), 'case')}; evidence: {evidence})")
    return bullet_lines(lines, "No acceptance criteria were synced.")


def render_business_rules(spec: dict[str, Any]) -> str:
    lines = [f"`{text(item.get('id'))}` {text(item.get('rule'))}" for item in as_list(spec.get("business_rules")) if isinstance(item, dict)]
    return bullet_lines(lines, "No explicit business rules were synced.")


def render_requirement_clarification(spec: dict[str, Any]) -> str:
    confirmed: list[str] = []
    for item in as_list(spec.get("business_rules")):
        if isinstance(item, dict):
            confirmed.append(f"{text(item.get('id'))}: {text(item.get('rule'))}")
    permission = spec.get("permission_scope") if isinstance(spec.get("permission_scope"), dict) else {}
    actors = ", ".join(str(item) for item in as_list(permission.get("actors")))
    if actors:
        confirmed.append(f"Actors/roles identified: {actors}")
    if permission.get("negative_cases_required") is True:
        confirmed.append("Negative permission cases are required.")

    assumptions: list[str] = []
    scope = spec.get("scope") if isinstance(spec.get("scope"), dict) else {}
    assumptions.extend(str(item) for item in as_list(scope.get("assumptions")))
    assumptions.extend(str(item) for item in as_list(spec.get("assumptions")))

    questions: list[str] = []
    for item in as_list(spec.get("open_questions")):
        if isinstance(item, dict):
            questions.append(text(item.get("question") or item.get("summary") or item))
        else:
            questions.append(text(item))

    decision = str(spec.get("decision") or "")
    blocked = bool(questions) or decision in {"needs_clarification", "blocked"}
    return (
        "### Clarification Status\n\n"
        f"- Status: {'blocked pending answer' if blocked else 'no blocking clarification recorded'}\n"
        f"- Design can proceed: {'no' if blocked else 'yes'}\n\n"
        "### Confirmed Understanding\n\n"
        f"{bullet_lines(confirmed, 'No confirmed business rules beyond the requirement text.')}\n\n"
        "### Pending Questions\n\n"
        f"{bullet_lines(questions, 'None recorded.')}\n\n"
        "### Working Assumptions\n\n"
        f"{bullet_lines(assumptions, 'None recorded.')}"
    )


def render_open_questions(*documents: dict[str, Any]) -> str:
    lines: list[str] = []
    for data in documents:
        for item in as_list(data.get("open_questions")):
            if isinstance(item, dict):
                lines.append(text(item.get("question") or item.get("summary") or item))
            else:
                lines.append(text(item))
    return bullet_lines(lines, "None recorded.")


def render_process_flows(technical: dict[str, Any]) -> str:
    sections: list[str] = []
    for flow in as_list(technical.get("process_flow")):
        if not isinstance(flow, dict):
            continue
        steps = []
        for step in as_list(flow.get("steps")):
            if isinstance(step, dict):
                steps.append(f"  - {text(step.get('step'))}. {text(step.get('actor'))}: {text(step.get('action'))} -> {text(step.get('output'))}")
        sections.append(
            f"### {text(flow.get('flow_name'), 'Process')}\n\n"
            f"- Actors: {', '.join(str(item) for item in as_list(flow.get('actors'))) or 'TBD'}\n"
            f"- Success state: {text(flow.get('success_end_state'))}\n"
            f"- Failure states: {', '.join(str(item) for item in as_list(flow.get('failure_end_states'))) or 'TBD'}\n\n"
            + ("\n".join(steps) if steps else "- Steps: TBD")
        )
    return "\n\n".join(sections) if sections else "### Process\n\n- TBD"


def render_named_items(items: list[Any], fields: list[str], empty: str) -> str:
    labels = {
        "page_or_route": "page/route",
        "user_goal": "user goal",
        "entry_point": "entry point",
        "permission_visibility": "permission visibility",
        "acceptance_evidence": "acceptance evidence",
        "old_consumer_impact": "consumer impact",
        "failure_handling": "failure handling",
        "data_risk": "data risk",
    }
    lines: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        values = [f"{labels.get(field, field)}: {text(item.get(field))}" for field in fields if item.get(field) not in (None, "", [], {})]
        if values:
            lines.append("; ".join(values))
    return bullet_lines(lines, empty)


def render_delivery_tasks(delivery_plan: dict[str, Any]) -> str:
    lines: list[str] = []
    for repo in as_list(delivery_plan.get("repo_tasks")):
        if not isinstance(repo, dict):
            continue
        allowed_files = ", ".join(str(item) for item in as_list(repo.get("allowed_files"))) or "not narrowed yet"
        tests = ", ".join(str(item) for item in as_list(repo.get("test_commands"))) or "not bound yet"
        lines.append(f"- Repo `{text(repo.get('repo'))}`: {text(repo.get('responsibility'))}; files: {allowed_files}; tests: {tests}")
        for task in as_list(repo.get("tasks"))[:6]:
            if isinstance(task, dict):
                lines.append(f"  - {text(task.get('phase'))}: {text(task.get('summary'))}")
    return "\n".join(lines) if lines else "- No repo tasks were synced."


def render_blockers(*documents: dict[str, Any]) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for data in documents:
        for item in as_list(data.get("blockers")) + as_list(data.get("open_gates")):
            if isinstance(item, dict):
                source = text(item.get("source") or item.get("area"), "gate")
                message = text(item.get("message") or item.get("suggestion") or item)
            else:
                source = "gate"
                message = text(item)
            key = f"{source}: {message}"
            if key not in seen:
                seen.add(key)
                lines.append(key)
    return bullet_lines(lines[:10], "None.")


def render_next_action(status: dict[str, Any], delivery_review: dict[str, Any]) -> str:
    primary = status.get("primary_next_action") if isinstance(status.get("primary_next_action"), dict) else {}
    for value in [primary.get("summary"), status.get("next_command")]:
        if value:
            return text(value)
    blockers = as_list(delivery_review.get("blockers"))
    if blockers and isinstance(blockers[0], dict):
        return text(blockers[0].get("suggestion") or blockers[0].get("message"))
    return "Resolve listed blockers before implementation or release."


def render_evidence_refs(artifact_dir: Path) -> str:
    refs = [
        "spec.json",
        "technical_design.json",
        "architecture_design.json",
        "delivery_plan.json",
        "design_architecture_review.json",
        "delivery_plan_review.json",
        "delivery_status.json",
    ]
    lines = [f"- `{name}`" for name in refs if (artifact_dir / name).exists()]
    return "\n".join(lines) if lines else "- No machine artifacts were synced."


def render_synced_human_docs(doc_id: str, title: str, artifact_dir: Path) -> dict[str, str]:
    requirement = artifact_dir / "requirement.normalized.txt"
    spec = read_json(artifact_dir / "spec.json")
    technical = read_json(artifact_dir / "technical_design.json")
    architecture = read_json(artifact_dir / "architecture_design.json")
    delivery_plan = read_json(artifact_dir / "delivery_plan.json")
    design_review = read_json(artifact_dir / "design_architecture_review.json")
    delivery_review = read_json(artifact_dir / "delivery_plan_review.json")
    status = read_json(artifact_dir / "delivery_status.json")
    requirement_text = requirement.read_text(encoding="utf-8") if requirement.exists() else ""
    heading = title or str(spec.get("title") or doc_id)
    return {
        "spec": (
            f"# {heading} Spec\n\n"
            "## Executive Summary\n\n"
            f"- Doc ID: `{doc_id}`\n"
            f"- Current decision: `{text(spec.get('decision'), 'unknown')}`\n"
            f"- Permission sensitivity: {text((spec.get('permission_scope') or {}).get('sensitive'), 'unknown')}\n\n"
            "## Scope\n\n"
            f"{render_scope(spec, text(spec.get('summary') or heading))}\n\n"
            "## Requirement Clarification\n\n"
            f"{render_requirement_clarification(spec)}\n\n"
            "## Requirement Source\n\n"
            f"{requirement_text.strip() or 'Requirement text not synced.'}\n\n"
            "## Acceptance Criteria\n\n"
            f"{render_acceptance(spec)}\n\n"
            "## Business Rules\n\n"
            f"{render_business_rules(spec)}\n\n"
            "## Open Questions\n\n"
            f"{render_open_questions(spec)}\n\n"
            "## Evidence References\n\n"
            f"{render_evidence_refs(artifact_dir)}\n"
        ),
        "design": (
            f"# {heading} Design\n\n"
            "## Executive Summary\n\n"
            f"- Doc ID: `{doc_id}`\n"
            f"- Technical decision: `{text(technical.get('decision'), 'draft')}`\n"
            f"- Architecture decision: `{text(architecture.get('decision'), 'draft')}`\n"
            f"- Delivery plan decision: `{text(delivery_plan.get('decision'), 'draft')}`\n\n"
            "## Process Flow\n\n"
            f"{render_process_flows(technical)}\n\n"
            "## Module And Contract Design\n\n"
            f"{render_named_items(as_list(technical.get('module_design')), ['module', 'responsibility', 'change_summary'], 'No module design was synced.')}\n\n"
            f"{render_named_items(as_list(technical.get('api_contracts')), ['contract', 'compatibility', 'old_consumer_impact'], 'No API contract changes were confirmed.')}\n\n"
            "## UI / UX Impact\n\n"
            f"{render_named_items(as_list(technical.get('ui_ue_design')), ['page_or_route', 'user_goal', 'entry_point', 'permission_visibility', 'acceptance_evidence'], 'No UI impact was confirmed.')}\n\n"
            "## Architecture And Operations\n\n"
            f"{render_named_items(as_list(architecture.get('integration_sequence')), ['step', 'actor', 'action', 'failure_handling'], 'No integration sequence was synced.')}\n\n"
            f"{render_named_items(as_list(architecture.get('deployment_impact')), ['order', 'config'], 'No deployment impact was synced.')}\n\n"
            f"{render_named_items(as_list(architecture.get('rollback_strategy')), ['repo', 'steps', 'data_risk'], 'No rollback strategy was synced.')}\n\n"
            "## Delivery Plan\n\n"
            f"{render_delivery_tasks(delivery_plan)}\n\n"
            "## Risks And Open Gates\n\n"
            f"{render_blockers(delivery_plan, architecture)}\n\n"
            "## Evidence References\n\n"
            f"{render_evidence_refs(artifact_dir)}\n"
        ),
        "release": (
            f"# {heading} Release\n\n"
            "## Executive Summary\n\n"
            f"- Doc ID: `{doc_id}`\n"
            f"- Next stage: `{text(status.get('next_stage'), 'unknown')}`\n"
            f"- Implementation allowed: `{text(status.get('can_implement'), 'false')}`\n"
            f"- Release allowed: `{text(status.get('can_release'), 'false')}`\n\n"
            "## Missing Readiness\n\n"
            "### Before Implementation\n\n"
            f"{bullet_lines([str(item) for item in as_list(status.get('implementation_missing'))], 'No implementation gaps were synced.')}\n\n"
            "### Before Release\n\n"
            f"{bullet_lines([str(item) for item in as_list(status.get('release_missing'))], 'No release gaps were synced.')}\n\n"
            "## Review Decisions\n\n"
            f"- Design review: `{text(design_review.get('decision'), 'unknown')}`\n"
            f"- Delivery plan review: `{text(delivery_review.get('decision'), 'unknown')}`\n\n"
            "## Blockers\n\n"
            f"{render_blockers(design_review, delivery_review, status)}\n\n"
            "## Next Action\n\n"
            f"- {render_next_action(status, delivery_review)}\n\n"
            "## Evidence References\n\n"
            f"{render_evidence_refs(artifact_dir)}\n"
        ),
    }


def sync(docs_root: Path, doc_id: str, artifact_dir: Path, title: str = "", git_url: str = "") -> dict[str, Any]:
    docs_root = docs_root.expanduser().resolve()
    artifact_dir = artifact_dir.expanduser().resolve()
    manifest = init(docs_root, doc_id, git_url=git_url, title=title)
    human_docs = render_synced_human_docs(doc_id, title, artifact_dir)
    human_targets = {
        "spec": docs_root / manifest["human_docs"]["spec"],
        "design": docs_root / manifest["human_docs"]["design"],
        "release": docs_root / manifest["human_docs"]["release"],
    }
    for name, content in human_docs.items():
        human_targets[name].parent.mkdir(parents=True, exist_ok=True)
        human_targets[name].write_text(content, encoding="utf-8")

    bundles = {
        "spec": ["spec.json"],
        "design": ["technical_design.json", "architecture_design.json", "test_design.json", "delivery_plan.json"],
        "review": ["design_architecture_review.json", "delivery_plan_review.json", "delivery_status.json"],
        "release": ["implementation_completion_gate.json", "code_review_gate.json", "test_evidence_gate.json", "release_gate.json"],
    }
    synced_machine: list[str] = []
    for name, files in bundles.items():
        target = docs_root / manifest["machine_artifacts"][name]
        payload: dict[str, Any] = {
            "schema": "codex-docs-machine-bundle-v1",
            "doc_id": doc_id,
            "artifact_type": name,
            "source_artifact_dir": str(artifact_dir),
            "artifacts": {},
        }
        for filename in files:
            source = artifact_dir / filename
            if source.exists():
                payload["artifacts"][filename] = read_json(source)
        if payload["artifacts"]:
            write_json(target, payload)
            synced_machine.append(str(target.relative_to(docs_root)))

    raw_dir = docs_root / "machine/raw" / doc_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    copied_raw: list[str] = []
    for source in sorted(artifact_dir.glob("*.json")):
        dest = raw_dir / source.name
        shutil.copy2(source, dest)
        copied_raw.append(str(dest.relative_to(docs_root)))

    manifest["synced_from"] = str(artifact_dir)
    manifest["synced_human_docs"] = [str(path.relative_to(docs_root)) for path in human_targets.values()]
    manifest["synced_machine_artifacts"] = synced_machine
    manifest["raw_artifacts"] = copied_raw
    write_json(docs_root / "indexes" / f"{doc_id}.manifest.json", manifest)
    return {
        "schema": "codex-docs-governor-sync-v1",
        "decision": "pass",
        "doc_id": doc_id,
        "docs_root": str(docs_root),
        "artifact_dir": str(artifact_dir),
        "manifest": str(docs_root / "indexes" / f"{doc_id}.manifest.json"),
        "human_docs": manifest["synced_human_docs"],
        "machine_artifacts": manifest["synced_machine_artifacts"],
        "raw_artifacts": copied_raw,
        "blockers": [],
    }


def configure(docs_root: Path, git_url: str = "") -> dict[str, Any]:
    docs_root = docs_root.expanduser().resolve()
    docs_root.mkdir(parents=True, exist_ok=True)
    git_initialized = False
    if not is_git_repo(docs_root):
        proc = subprocess.run(["git", "init"], cwd=docs_root, text=True, capture_output=True)
        git_initialized = proc.returncode == 0
    remote_configured = False
    remote_warning = ""
    if git_url:
        proc = subprocess.run(["git", "remote", "get-url", "origin"], cwd=docs_root, text=True, capture_output=True)
        current = proc.stdout.strip() if proc.returncode == 0 else ""
        if current and current != git_url:
            remote_warning = f"origin already configured as {current}"
        elif not current:
            add = subprocess.run(["git", "remote", "add", "origin", git_url], cwd=docs_root, text=True, capture_output=True)
            remote_configured = add.returncode == 0
        else:
            remote_configured = True
    config_data = load_docs_config_module().save(ROOT, docs_root, git_url)
    return {
        "schema": "codex-docs-workspace-config-v1",
        "decision": "pass" if not remote_warning else "block",
        "docs_root": str(docs_root),
        "git_url": git_url,
        "git_initialized": git_initialized,
        "remote_configured": remote_configured,
        "config": str(ROOT / ".codex-engineering-docs.json"),
        "blockers": [{"source": "git_remote", "message": remote_warning}] if remote_warning else [],
        "next_action": "Run docs-governor init for each new doc_id without repeating the docs remote.",
    }


def init(docs_root: Path, doc_id: str, git_url: str = "", title: str = "") -> dict[str, Any]:
    for directory in DIRS:
        (docs_root / directory).mkdir(parents=True, exist_ok=True)
    config = configure(docs_root, git_url)
    materialized = materialize_doc_files(docs_root, doc_id, title)
    manifest = {
        "schema": "codex-docs-governor-v1",
        "doc_id": doc_id,
        "title": title,
        "docs_root": str(docs_root.expanduser().resolve()),
        "git_initialized": config.get("git_initialized", False),
        "workspace_config": config.get("schema", ""),
        "human_docs": {
            "spec": f"human/specs/{doc_id}.md",
            "design": f"human/designs/{doc_id}.md",
            "release": f"human/releases/{doc_id}.md",
        },
        "machine_artifacts": {
            "spec": f"machine/specs/{doc_id}.spec.json",
            "design": f"machine/designs/{doc_id}.design.json",
            "review": f"machine/reviews/{doc_id}.review.json",
            "release": f"machine/releases/{doc_id}.release.json",
        },
        "materialized": materialized,
        "rule": "Commit docs changes on a branch and merge through normal review; do not store local absolute paths or secrets.",
    }
    write_json(docs_root / "indexes" / f"{doc_id}.manifest.json", manifest)
    return manifest


def is_git_repo(path: Path) -> bool:
    proc = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=path, text=True, capture_output=True)
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def validate(docs_root: Path, doc_id: str, require_git: bool = False) -> dict[str, Any]:
    manifest_path = docs_root / "indexes" / f"{doc_id}.manifest.json"
    blockers: list[dict[str, str]] = []
    for directory in DIRS:
        if not (docs_root / directory).is_dir():
            blockers.append({"source": directory, "message": "required docs directory missing"})
    if not manifest_path.exists():
        blockers.append({"source": "manifest", "message": "doc manifest missing"})
    else:
        manifest = read_json(manifest_path)
        for group in ["human_docs", "machine_artifacts"]:
            values = manifest.get(group) if isinstance(manifest.get(group), dict) else {}
            for name, rel_path in values.items():
                target = docs_root / str(rel_path)
                if not target.exists():
                    blockers.append({"source": f"{group}.{name}", "message": "manifest file missing"})
                elif not target.read_text(encoding="utf-8").strip():
                    blockers.append({"source": f"{group}.{name}", "message": "manifest file is empty"})
    if require_git:
        if not docs_root.exists():
            blockers.append({"source": "docs_root", "message": "docs root missing"})
        elif not is_git_repo(docs_root):
            blockers.append({"source": "docs_git", "message": "docs root must be a git repository"})
    return {
        "schema": "codex-docs-governor-validation-v1",
        "decision": "block" if blockers else "pass",
        "blockers": blockers,
        "manifest": str(manifest_path),
        "git_required": require_git,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize or validate delivery docs structure")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_configure = sub.add_parser("configure")
    p_configure.add_argument("--docs-root", required=True)
    p_configure.add_argument("--git-url", default="")
    p_sync = sub.add_parser("sync")
    p_sync.add_argument("--docs-root", required=True)
    p_sync.add_argument("--doc-id", required=True)
    p_sync.add_argument("--artifact-dir", required=True)
    p_sync.add_argument("--title", default="")
    p_sync.add_argument("--git-url", default="")
    for cmd in ["init", "validate"]:
        p = sub.add_parser(cmd)
        p.add_argument("--docs-root", required=True)
        p.add_argument("--doc-id", required=True)
        p.add_argument("--title", default="")
        p.add_argument("--git-url", default="")
        p.add_argument("--require-git", action="store_true")
    args = parser.parse_args()
    if args.cmd == "configure":
        result = configure(Path(args.docs_root), args.git_url)
    elif args.cmd == "init":
        result = init(Path(args.docs_root), args.doc_id, args.git_url, args.title)
    elif args.cmd == "sync":
        result = sync(Path(args.docs_root), args.doc_id, Path(args.artifact_dir), args.title, args.git_url)
    else:
        result = validate(Path(args.docs_root), args.doc_id, args.require_git)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("decision") != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
