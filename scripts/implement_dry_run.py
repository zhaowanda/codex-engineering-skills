#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-implement-dry-run-v1"
ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def load_docs_config_module() -> Any:
    path = ROOT / "scripts/docs_config.py"
    spec = importlib.util.spec_from_file_location("docs_config", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def default_docs_root() -> Path | None:
    try:
        return load_docs_config_module().configured_docs_root(ROOT)
    except Exception:
        return None


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def collect_plan_scope(plan: dict[str, Any]) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    allowed_files: list[str] = []
    test_commands: list[str] = []
    repo_tasks: list[dict[str, Any]] = []
    for task in as_list(plan.get("repo_tasks")):
        if not isinstance(task, dict):
            continue
        if task.get("role") == "modify":
            allowed_files.extend(str(item) for item in as_list(task.get("allowed_files")) if item)
            test_commands.extend(str(item) for item in as_list(task.get("test_commands")) if item)
            repo_tasks.append({
                "repo": task.get("repo", ""),
                "repo_path": task.get("repo_path", ""),
                "allowed_files": as_list(task.get("allowed_files")),
                "test_commands": as_list(task.get("test_commands")),
            })
    return sorted(set(allowed_files)), sorted(set(test_commands)), repo_tasks


def decision_ready(data: dict[str, Any], accepted: set[str]) -> bool:
    decision = str(data.get("decision") or data.get("status") or "")
    if not data:
        return False
    if decision and decision not in accepted:
        return False
    return not any(data.get(key) for key in ["blockers", "active_blockers", "missing_evidence"])


def docs_ready(docs_root: Path | None, doc_id: str) -> tuple[bool, str, list[str]]:
    if not docs_root:
        return False, "", ["docs_root is required"]
    manifest = docs_root / "indexes" / f"{doc_id}.manifest.json"
    blockers: list[str] = []
    if not docs_root.exists():
        blockers.append("docs_root does not exist")
    if not manifest.exists():
        blockers.append("docs manifest is missing")
    if docs_root.exists() and not (docs_root / ".git").exists():
        blockers.append("docs root must be a git repository")
    return not blockers, str(manifest), blockers


def git_evidence_ready(git_evidence: dict[str, Any], label: str) -> list[str]:
    blockers: list[str] = []
    if not decision_ready(git_evidence, {"ready", "pass"}):
        blockers.append(f"{label}: git evidence is not ready")
    if git_evidence and git_evidence.get("fetched") is not True:
        blockers.append(f"{label}: git fetch evidence is missing")
    if git_evidence and git_evidence.get("base_updated") is not True:
        blockers.append(f"{label}: git pull --ff-only evidence is missing")
    return blockers


def git_ready_for_edit(artifact_dir: Path, fallback_evidence: dict[str, Any]) -> tuple[bool, list[str], list[dict[str, Any]]]:
    summary = load_json(artifact_dir / "git_plan_baseline_summary.json")
    blockers: list[str] = []
    evidence_items: list[dict[str, Any]] = []
    if summary:
        results = summary.get("results", [])
        if isinstance(results, list):
            evidence_items = [item for item in results if isinstance(item, dict)]
        if summary.get("decision") != "ready":
            blockers.append("git_plan_baseline_summary.json is not ready")
    elif fallback_evidence:
        evidence_items = [fallback_evidence]
    else:
        blockers.append("git_worktree_evidence.json")
    if not evidence_items:
        blockers.append("git evidence for modify repositories is missing")
    for idx, item in enumerate(evidence_items):
        label = str(item.get("repo_name") or item.get("repo") or f"repo[{idx}]")
        blockers.extend(git_evidence_ready(item, label))
    return not blockers, blockers, evidence_items


def run(artifact_dir: Path, docs_root: Path | None = None, doc_id: str = "") -> dict[str, Any]:
    plan = load_json(artifact_dir / "delivery_plan.json")
    edit_permit = load_json(artifact_dir / "edit_permit.json")
    git_evidence = load_json(artifact_dir / "git_worktree_evidence.json")
    delivery_status = load_json(artifact_dir / "delivery_status.json")
    auto_summary = load_json(artifact_dir / "auto_run_summary.json")
    effective_doc_id = doc_id or str(auto_summary.get("doc_id") or plan.get("doc_id") or "")
    if not docs_root:
        docs_status = auto_summary.get("docs_readiness") if isinstance(auto_summary.get("docs_readiness"), dict) else {}
        if docs_status.get("docs_root"):
            docs_root = Path(str(docs_status["docs_root"]))
    if not docs_root:
        docs_root = default_docs_root()
    allowed_files, test_commands, repo_tasks = collect_plan_scope(plan)
    missing_gates: list[str] = []
    _, git_blockers, git_evidence_items = git_ready_for_edit(artifact_dir, git_evidence)
    missing_gates.extend(git_blockers)
    if not decision_ready(edit_permit, {"ready", "pass"}):
        missing_gates.append("edit_permit.json")
    if not plan:
        missing_gates.append("delivery_plan.json")
    if not allowed_files:
        missing_gates.append("delivery_plan.allowed_files")
    docs_ok, docs_manifest, docs_blockers = docs_ready(docs_root, effective_doc_id)
    missing_gates.extend(f"docs: {item}" for item in docs_blockers)
    can_edit = not missing_gates and bool(allowed_files)
    return {
        "schema": SCHEMA,
        "artifact_dir": str(artifact_dir),
        "doc_id": effective_doc_id,
        "decision": "ready" if can_edit else "blocked",
        "dry_run": True,
        "can_edit": can_edit,
        "docs_readiness": {
            "decision": "pass" if docs_ok else "block",
            "docs_root": str(docs_root) if docs_root else "",
            "manifest": docs_manifest,
            "blockers": docs_blockers,
        },
        "git_requires_fetch_and_ff_pull": True,
        "git_evidence_count": len(git_evidence_items),
        "allowed_files": allowed_files,
        "forbidden_files": ["files outside delivery_plan.repo_tasks[].allowed_files"],
        "recommended_validation_commands": test_commands,
        "repo_tasks": repo_tasks,
        "missing_gates": missing_gates,
        "delivery_next_action_type": delivery_status.get("next_action_type", ""),
        "next_action": "Proceed with scoped implementation only." if can_edit else "Complete missing gates before editing.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run implementation readiness from delivery artifacts")
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--docs-root")
    parser.add_argument("--doc-id")
    parser.add_argument("--out")
    args = parser.parse_args()
    result = run(Path(args.artifact_dir), Path(args.docs_root) if args.docs_root else None, args.doc_id or "")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
