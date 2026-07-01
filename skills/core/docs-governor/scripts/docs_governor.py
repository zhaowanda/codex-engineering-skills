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


def short_json_summary(data: dict[str, Any], keys: list[str]) -> str:
    lines: list[str] = []
    for key in keys:
        value = data.get(key)
        if value in (None, "", [], {}):
            continue
        rendered = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
        lines.append(f"- {key}: {rendered}")
    return "\n".join(lines) if lines else "- No synced data available."


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
            f"- doc_id: `{doc_id}`\n"
            f"- decision: `{spec.get('decision', '')}`\n\n"
            "## Requirement\n\n"
            f"{requirement_text.strip() or 'Requirement text not synced.'}\n\n"
            "## Acceptance Criteria\n\n"
            f"{short_json_summary(spec, ['acceptance_criteria', 'negative_acceptance_criteria', 'business_rules', 'open_questions'])}\n"
        ),
        "design": (
            f"# {heading} Design\n\n"
            f"- doc_id: `{doc_id}`\n\n"
            "## Technical Design\n\n"
            f"{short_json_summary(technical, ['process_flow', 'module_design', 'api_contracts', 'ui_ue_design', 'test_strategy', 'open_questions'])}\n\n"
            "## Architecture Design\n\n"
            f"{short_json_summary(architecture, ['system_context', 'component_design', 'integration_sequence', 'deployment_impact', 'rollback_strategy', 'architecture_risks'])}\n\n"
            "## Delivery Plan\n\n"
            f"{short_json_summary(delivery_plan, ['repo_tasks', 'cross_repo_order', 'validation_plan', 'open_gates', 'decision'])}\n"
        ),
        "release": (
            f"# {heading} Release\n\n"
            f"- doc_id: `{doc_id}`\n\n"
            "## Readiness\n\n"
            f"{short_json_summary(status, ['next_stage', 'can_implement', 'can_release', 'implementation_missing', 'release_missing'])}\n\n"
            "## Reviews\n\n"
            f"{short_json_summary(design_review, ['decision', 'blockers', 'warnings'])}\n"
            f"{short_json_summary(delivery_review, ['decision', 'blockers', 'warnings'])}\n"
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
