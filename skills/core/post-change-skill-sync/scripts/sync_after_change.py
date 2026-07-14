#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA = "codex-post-change-implementation-report-v1"
IGNORE_DIRS = (".git/", ".idea/", ".vscode/", "node_modules/", "dist/", "build/", "target/", "__pycache__/")


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def should_ignore(path: str) -> bool:
    return any(path.startswith(item) or f"/{item}" in path for item in IGNORE_DIRS)


def git_branch(repo: Path) -> str:
    code, out, _ = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo)
    return out if code == 0 else ""


def git_head(repo: Path) -> str:
    code, out, _ = run(["git", "rev-parse", "--short", "HEAD"], repo)
    return out if code == 0 else ""


def git_changed_files(repo: Path, base_ref: str = "") -> list[str]:
    if not (repo / ".git").exists():
        return []
    if base_ref:
        code, out, _ = run(["git", "diff", "--name-only", f"{base_ref}..HEAD"], repo)
        if code == 0:
            return [line for line in out.splitlines() if line and not should_ignore(line)]
    code, out, _ = run(["git", "status", "--short"], repo)
    if code != 0:
        return []
    files: list[str] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        path = line[2:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        if path and not should_ignore(path):
            full_path = repo / path
            if full_path.is_dir():
                files.extend(
                    child.relative_to(repo).as_posix()
                    for child in full_path.rglob("*")
                    if child.is_file() and not should_ignore(child.relative_to(repo).as_posix())
                )
            else:
                files.append(path)
    return sorted(dict.fromkeys(files))


def git_diff_stat(repo: Path, base_ref: str = "") -> str:
    cmd = ["git", "diff", "--stat"]
    if base_ref:
        cmd.append(f"{base_ref}..HEAD")
    code, out, _ = run(cmd, repo)
    return out if code == 0 else ""


def file_change_summary(files: list[str]) -> dict[str, int]:
    buckets = {
        "api_or_controller": 0,
        "service_or_domain": 0,
        "frontend": 0,
        "config": 0,
        "db_or_mapper": 0,
        "test": 0,
        "docs": 0,
        "workflow_or_skill": 0,
        "other": 0,
    }
    for file in files:
        low = file.lower()
        if any(item in low for item in ["controller", "router", "/api", "api/"]):
            buckets["api_or_controller"] += 1
        elif any(item in low for item in ["service", "domain", "entity", "usecase"]):
            buckets["service_or_domain"] += 1
        elif low.endswith((".vue", ".js", ".ts", ".tsx", ".jsx", ".css", ".scss")) or "src/views" in low or "components/" in low:
            buckets["frontend"] += 1
        elif any(item in low for item in ["application", ".yml", ".yaml", ".properties", "pom.xml", "package.json", "pyproject.toml"]):
            buckets["config"] += 1
        elif any(item in low for item in ["migration", ".sql", "mapper.xml", "repository", "dao"]):
            buckets["db_or_mapper"] += 1
        elif any(item in low for item in ["test", "spec"]):
            buckets["test"] += 1
        elif low.endswith((".md", ".rst", ".adoc")) or low.startswith("docs/"):
            buckets["docs"] += 1
        elif low.startswith(("skills/", "scripts/", "config/workflow")):
            buckets["workflow_or_skill"] += 1
        else:
            buckets["other"] += 1
    return {key: value for key, value in buckets.items() if value}


def infer_validation_needs(files: list[str]) -> list[str]:
    needs: set[str] = set()
    for file in files:
        low = file.lower()
        if low.startswith(("skills/", "scripts/")) or low.endswith(".py"):
            needs.add("python compile and pytest coverage for changed workflow or scripts")
        if low.endswith((".java", ".kt", ".go", ".py")) or any(item in low for item in ["controller", "service", "mapper", "repository"]):
            needs.add("backend unit/integration tests for changed API/service/data paths")
        if low.endswith((".vue", ".js", ".ts", ".tsx", ".jsx")) or "src/views" in low or "components/" in low:
            needs.add("frontend lint/build and browser acceptance for changed pages/routes")
        if any(item in low for item in ["pom.xml", "package.json", "requirements.txt", "pyproject.toml", "build.gradle"]):
            needs.add("dependency/build validation and compatibility check")
        if any(item in low for item in ["application", ".yml", ".yaml", ".properties", "bootstrap"]):
            needs.add("environment/config validation")
        if any(item in low for item in ["migration", ".sql", "mapper.xml", "entity"]):
            needs.add("database migration/data compatibility validation")
    if not needs:
        needs.add("repo-level smoke checks or documented reason why validation is not required")
    return sorted(needs)


def infer_baseline_candidates(files: list[str]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for file in files:
        low = file.lower()
        sections: set[str] = set()
        reason: list[str] = []
        if any(item in low for item in ["controller", "router", "api", "request", "axios"]):
            sections.update(["api_baseline", "module_map"])
            reason.append("API/controller/client contract changed")
        if any(item in low for item in ["service", "domain", "entity", "mapper", "repository", "dao"]):
            sections.update(["module_map", "data_dependency_baseline"])
            reason.append("service/domain/data access behavior changed")
        if any(item in low for item in ["application", ".yml", ".yaml", ".properties", "config"]):
            sections.update(["architecture_baseline", "configuration_baseline"])
            reason.append("runtime configuration changed")
        if low.startswith(("skills/", "scripts/", "config/workflow")):
            sections.update(["workflow_baseline", "skill_catalog"])
            reason.append("workflow or skill behavior changed")
        if any(item in low for item in ["test", "spec"]):
            sections.add("test_baseline")
            reason.append("test behavior or evidence changed")
        if reason:
            candidates.append({
                "changed_file": file,
                "status": "proposed",
                "baseline_sections": sorted(sections),
                "reason": "; ".join(reason),
                "owner_review_required": True,
                "apply_rule": "Review before promoting to long-lived baseline; do not mutate published baselines automatically.",
            })
    return candidates


def infer_project_skill_candidates(files: list[str], baseline_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for idx, item in enumerate(baseline_candidates, start=1):
        sections = set(item.get("baseline_sections") or [])
        if "api_baseline" in sections:
            target = "references/api-map.md"
        elif "workflow_baseline" in sections or "skill_catalog" in sections:
            target = "SKILL.md or references/change-playbook.md"
        elif "test_baseline" in sections:
            target = "references/validation-recipes.md"
        else:
            target = "references/code-index.md"
        candidates.append({
            "candidate_id": f"PSC-{idx:03d}",
            "target": target,
            "source_changed_file": item.get("changed_file", ""),
            "reason": item.get("reason", ""),
            "status": "proposed",
            "owner_review_required": True,
            "promotion_rule": "Promote only stable reusable facts. Requirement-specific details stay in delivery docs evidence.",
        })
    return candidates


def project_skill_index_requirements(artifact_dir: Path, candidates: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    evidence_path = artifact_dir / "project_skill_index_sync.json"
    evidence = load_json(evidence_path)
    blockers: list[dict[str, str]] = []
    required = bool(candidates)
    status = "not_required"
    updated_paths = [str(item) for item in as_list(evidence.get("updated_index_paths")) if str(item).strip()]
    waiver_reason = str(evidence.get("waiver_reason") or "").strip()
    evidence_decision = str(evidence.get("decision") or "").strip()

    if required:
        if evidence_decision == "pass" and updated_paths:
            status = "satisfied"
        elif evidence_decision == "waived" and waiver_reason:
            status = "waived"
        else:
            status = "missing_evidence"
            blockers.append({
                "source": "project_skill_index_sync",
                "message": "project skill sync candidates require project_skill_index_sync.json with decision=pass and updated_index_paths, or decision=waived with waiver_reason",
            })

    return {
        "required": required,
        "status": status,
        "evidence_file": str(evidence_path),
        "candidate_count": len(candidates),
        "updated_index_paths": updated_paths,
        "waiver_reason": waiver_reason,
        "evidence_decision": evidence_decision,
    }, blockers


def docs_binding(artifact_dir: Path, docs_root: Path | None, doc_id: str, require_docs: bool) -> tuple[dict[str, Any], list[dict[str, str]]]:
    auto_summary = load_json(artifact_dir / "auto_run_summary.json")
    if not doc_id:
        doc_id = str(auto_summary.get("doc_id") or "")
    if docs_root is None:
        docs_status = as_dict(auto_summary.get("docs_readiness"))
        if docs_status.get("docs_root"):
            docs_root = Path(str(docs_status["docs_root"]))
    blockers: list[dict[str, str]] = []
    manifest = ""
    if not docs_root:
        if require_docs:
            blockers.append({"source": "docs_root", "message": "docs root is required"})
        return {"status": "missing", "required": require_docs, "docs_root": "", "doc_id": doc_id, "manifest": ""}, blockers
    manifest_path = docs_root / "indexes" / f"{doc_id}.manifest.json" if doc_id else docs_root / "indexes"
    manifest = str(manifest_path)
    if not docs_root.exists():
        blockers.append({"source": "docs_root", "message": "docs root does not exist"})
    elif not (docs_root / ".git").exists():
        blockers.append({"source": "docs_git", "message": "docs root must be a git repository"})
    if doc_id and not manifest_path.exists():
        blockers.append({"source": "docs_manifest", "message": "docs manifest is missing"})
    if not doc_id:
        blockers.append({"source": "doc_id", "message": "doc id is required for final docs binding"})
    status = "bound" if not blockers else "blocked" if require_docs else "incomplete"
    return {"status": status, "required": require_docs, "docs_root": str(docs_root), "doc_id": doc_id, "manifest": manifest}, blockers if require_docs else []


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Post Change Implementation Report",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Decision: `{report['decision']}`",
        f"- Repository: `{report['repo']}`",
        f"- Branch: `{report['branch']}`",
        f"- HEAD: `{report['head']}`",
        f"- Changed files: `{len(report['changed_files'])}`",
        f"- Docs binding: `{report['docs_binding']['status']}`",
        "",
        "## File Summary",
        "",
    ]
    if report["file_summary"]:
        lines.extend(f"- `{key}`: `{value}`" for key, value in report["file_summary"].items())
    else:
        lines.append("- No changed files detected.")
    lines.extend(["", "## Changed Files", ""])
    lines.extend(f"- `{file}`" for file in report["changed_files"]) if report["changed_files"] else lines.append("- none")
    lines.extend(["", "## Validation Needs", ""])
    lines.extend(f"- {item}" for item in report["validation_needs"])
    lines.extend(["", "## Baseline Update Candidates", ""])
    lines.extend(f"- `{item['changed_file']}` -> {', '.join(item['baseline_sections'])}: {item['reason']}" for item in report["baseline_update_candidates"]) if report["baseline_update_candidates"] else lines.append("- none")
    lines.extend(["", "## Project Skill Sync Candidates", ""])
    lines.extend(f"- `{item['candidate_id']}` -> `{item['target']}`: {item['reason']}" for item in report["project_skill_sync_candidates"]) if report["project_skill_sync_candidates"] else lines.append("- none")
    index_requirements = report.get("project_skill_index_requirements", {})
    if isinstance(index_requirements, dict):
        lines.extend([
            "",
            "## Project Skill Index Requirements",
            "",
            f"- Required: `{index_requirements.get('required')}`",
            f"- Status: `{index_requirements.get('status')}`",
            f"- Evidence file: `{index_requirements.get('evidence_file')}`",
        ])
        for path in as_list(index_requirements.get("updated_index_paths")):
            lines.append(f"- Updated index: `{path}`")
        if index_requirements.get("waiver_reason"):
            lines.append(f"- Waiver: {index_requirements['waiver_reason']}")
    if report.get("diff_stat"):
        lines.extend(["", "## Diff Stat", "", "```text", report["diff_stat"], "```"])
    if report["blockers"]:
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{item['source']}`: {item['message']}" for item in report["blockers"])
    return "\n".join(lines) + "\n"


def generate(repo: Path, artifact_dir: Path, doc_id: str = "", docs_root: Path | None = None, require_docs: bool = False, base_ref: str = "") -> dict[str, Any]:
    repo = repo.expanduser().resolve()
    artifact_dir = artifact_dir.expanduser().resolve()
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    if not (repo / ".git").exists():
        blockers.append({"source": "repo", "message": "repo must be a git repository"})
    changed = git_changed_files(repo, base_ref) if not blockers else []
    if not changed:
        warnings.append({"source": "changed_files", "message": "no changed files detected"})
    baseline = infer_baseline_candidates(changed)
    project_skill_candidates = infer_project_skill_candidates(changed, baseline)
    project_skill_index, project_skill_index_blockers = project_skill_index_requirements(artifact_dir, project_skill_candidates)
    blockers.extend(project_skill_index_blockers)
    docs, docs_blockers = docs_binding(artifact_dir, docs_root, doc_id, require_docs)
    blockers.extend(docs_blockers)
    report = {
        "schema": SCHEMA,
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "repo": str(repo),
        "branch": git_branch(repo),
        "head": git_head(repo),
        "base_ref": base_ref,
        "changed_files": changed,
        "file_summary": file_change_summary(changed),
        "diff_stat": git_diff_stat(repo, base_ref),
        "validation_needs": infer_validation_needs(changed),
        "baseline_update_candidates": baseline,
        "project_skill_sync_candidates": project_skill_candidates,
        "project_skill_index_requirements": project_skill_index,
        "docs_binding": docs,
        "blockers": blockers,
        "warnings": warnings,
    }
    write_json(artifact_dir / "post_change_implementation_report.json", report)
    (artifact_dir / "post_change_implementation_report.md").write_text(markdown(report), encoding="utf-8")
    return report


def validate(data: dict[str, Any]) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    if data.get("schema") != SCHEMA:
        blockers.append({"source": "schema", "message": f"schema must be {SCHEMA}"})
    if data.get("decision") not in {"pass", "warn", "block"}:
        blockers.append({"source": "decision", "message": "decision must be pass/warn/block"})
    for key in ["changed_files", "file_summary", "validation_needs", "baseline_update_candidates", "project_skill_sync_candidates", "project_skill_index_requirements", "docs_binding", "blockers", "warnings"]:
        if key not in data:
            blockers.append({"source": key, "message": f"{key} is required"})
    if data.get("decision") == "pass" and data.get("blockers"):
        blockers.append({"source": "decision", "message": "pass is not allowed with blockers"})
    index_requirements = as_dict(data.get("project_skill_index_requirements"))
    if index_requirements.get("required") and index_requirements.get("status") not in {"satisfied", "waived"}:
        blockers.append({"source": "project_skill_index_requirements", "message": "required project skill index sync must be satisfied or waived"})
    return {"schema": "codex-post-change-implementation-report-validation-v1", "decision": "block" if blockers else "pass", "blockers": blockers}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate post-change implementation report")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--doc-id", default="")
    parser.add_argument("--docs-root")
    parser.add_argument("--require-docs", action="store_true")
    parser.add_argument("--base-ref", default="")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    if args.validate:
        data = load_json(Path(args.artifact_dir) / "post_change_implementation_report.json")
        result = validate(data)
    else:
        result = generate(Path(args.repo), Path(args.artifact_dir), args.doc_id, Path(args.docs_root) if args.docs_root else None, args.require_docs, args.base_ref)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("decision") != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
