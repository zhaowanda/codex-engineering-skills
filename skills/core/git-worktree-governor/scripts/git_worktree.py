#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_BRANCHES = {"master", "main"}


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def run_git(repo: Path, args: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def safe_branch_name(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9._/-]{3,120}", name)) and ".." not in name and not name.startswith("-")


def slugify_branch_part(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-").lower()
    slug = re.sub(r"-+", "-", slug)
    return slug[:80] or datetime.now().strftime("%Y%m%d-%H%M%S")


def requirement_branch_name(branch_prefix: str, doc_id: str, fallback: str = "") -> str:
    prefix = branch_prefix.strip("/ ") or "feature"
    suffix = slugify_branch_part(doc_id or fallback or "requirement")
    return f"{prefix}/{suffix}"


def is_staging_path(path: str | Path) -> bool:
    return any(part == "_staging" or part.endswith("_staging") for part in Path(path).parts)


def blocked_schema(repo: Path, remote: str, blocker: str) -> dict[str, Any]:
    return {
        "schema": "codex-git-baseline-evidence-v1",
        "repo": str(repo),
        "remote": remote,
        "base_branch": "",
        "start_branch": "",
        "current_branch": "",
        "status_clean_before": False,
        "status_short": [],
        "baseline_commit": "",
        "blockers": [blocker],
        "warnings": [],
        "decision": "blocked",
        "generated_at": now(),
    }


def detect_base(repo: Path, remote: str, preferred_base: str = "") -> tuple[str | None, list[str]]:
    warnings: list[str] = []
    if preferred_base:
        code, _, _ = run_git(repo, ["rev-parse", "--verify", preferred_base])
        if code == 0:
            return preferred_base, warnings
        code, _, _ = run_git(repo, ["rev-parse", "--verify", f"{remote}/{preferred_base}"])
        if code == 0:
            return preferred_base, warnings
        warnings.append(f"preferred base branch not found locally or on {remote}: {preferred_base}")
    for branch in ["master", "main"]:
        code, _, _ = run_git(repo, ["rev-parse", "--verify", branch])
        if code == 0:
            return branch, warnings
    code, out, _ = run_git(repo, ["symbolic-ref", f"refs/remotes/{remote}/HEAD"])
    if code == 0 and "/" in out:
        candidate = out.rsplit("/", 1)[-1]
        if candidate:
            return candidate, warnings
    return None, warnings


def inspect(repo: Path, remote: str = "origin", base_branch: str = "") -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    repo = repo.expanduser().resolve()
    if not repo.exists():
        return blocked_schema(repo, remote, "repo does not exist")
    if is_staging_path(repo):
        return blocked_schema(repo, remote, "repo path points to _staging; use the registered project checkout for Git preparation")
    code, _, _ = run_git(repo, ["rev-parse", "--git-dir"])
    if code != 0:
        return blocked_schema(repo, remote, "not a git repository")
    _, branch, _ = run_git(repo, ["branch", "--show-current"])
    _, status, _ = run_git(repo, ["status", "--short"])
    _, commit, _ = run_git(repo, ["rev-parse", "HEAD"])
    base, base_warnings = detect_base(repo, remote, base_branch)
    warnings.extend(base_warnings)
    if not base:
        blockers.append("cannot detect base branch")
    if status:
        blockers.append("worktree is not clean")
    return {
        "schema": "codex-git-baseline-evidence-v1",
        "repo": str(repo),
        "remote": remote,
        "base_branch": base or "",
        "branch": branch,
        "start_branch": branch,
        "current_branch": branch,
        "status_clean_before": not bool(status),
        "status_short": status.splitlines(),
        "baseline_commit": commit,
        "blockers": blockers,
        "warnings": warnings,
        "decision": "ready" if not blockers else "blocked",
        "generated_at": now(),
    }


def prepare(repo: Path, branch: str, remote: str = "origin", base_branch: str = "") -> dict[str, Any]:
    evidence = inspect(repo, remote, base_branch)
    evidence.update({"new_branch": branch, "fetched": False, "base_updated": False, "created_branch": False})
    if evidence.get("decision") == "blocked":
        return evidence
    if not safe_branch_name(branch):
        evidence["blockers"].append("unsafe branch name")
        evidence["decision"] = "blocked"
        return evidence
    base = str(evidence["base_branch"])
    code, _, err = run_git(Path(evidence["repo"]), ["fetch", remote])
    evidence["fetched"] = code == 0
    if code != 0:
        evidence["blockers"].append(f"git fetch failed: {err}")
        evidence["decision"] = "blocked"
        return evidence
    code, _, err = run_git(Path(evidence["repo"]), ["checkout", base])
    if code != 0:
        evidence["blockers"].append(f"checkout base failed: {err}")
        evidence["decision"] = "blocked"
        return evidence
    code, _, err = run_git(Path(evidence["repo"]), ["pull", "--ff-only", remote, base])
    evidence["base_updated"] = code == 0
    if code != 0:
        evidence["blockers"].append(f"pull base failed: {err}")
        evidence["decision"] = "blocked"
        return evidence
    code, _, err = run_git(Path(evidence["repo"]), ["checkout", "-b", branch])
    evidence["created_branch"] = code == 0
    if code != 0 and "already exists" in err:
        code, _, err = run_git(Path(evidence["repo"]), ["checkout", branch])
        evidence["created_branch"] = False
        evidence["reused_branch"] = code == 0
    if code != 0:
        evidence["blockers"].append(f"create branch failed: {err}")
        evidence["decision"] = "blocked"
        return evidence
    _, current, _ = run_git(Path(evidence["repo"]), ["branch", "--show-current"])
    _, commit, _ = run_git(Path(evidence["repo"]), ["rev-parse", "HEAD"])
    evidence["current_branch"] = current
    evidence["branch"] = current
    evidence["baseline_commit"] = commit
    if current != branch:
        evidence["blockers"].append("current branch is not the requested feature branch")
    evidence["decision"] = "ready" if not evidence["blockers"] else "blocked"
    evidence["generated_at"] = now()
    return evidence


def load_json_file(path: str) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"failed to read json: {path}: {exc}")
    if not isinstance(data, dict):
        raise SystemExit(f"json root must be object: {path}")
    return data


def plan_modify_tasks(plan: dict[str, Any]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for idx, task in enumerate(plan.get("repo_tasks", [])):
        if not isinstance(task, dict) or task.get("role") != "modify":
            continue
        item = dict(task)
        item["_index"] = idx
        tasks.append(item)
    return tasks


def repo_label(task: dict[str, Any], repo_path: Path) -> str:
    raw = str(task.get("repo") or task.get("name") or repo_path.name or f"repo-{task.get('_index', 0)}")
    return slugify_branch_part(raw)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_artifact(artifact_dir: str | None, evidence: dict[str, Any], filename: str = "git_baseline_evidence.json") -> None:
    if artifact_dir:
        write_json(Path(artifact_dir) / filename, evidence)


def prepare_plan(
    delivery_plan_file: str,
    branch_prefix: str,
    doc_id: str,
    artifact_dir: str | None,
    remote: str = "origin",
    check_only: bool = False,
) -> dict[str, Any]:
    plan = load_json_file(delivery_plan_file)
    tasks = plan_modify_tasks(plan)
    plan_file = Path(delivery_plan_file).expanduser().resolve()
    registry = project_registry()
    branch = requirement_branch_name(branch_prefix, doc_id, plan_file.stem)
    blockers: list[str] = []
    results: list[dict[str, Any]] = []
    if not tasks:
        blockers.append("delivery_plan has no repo_tasks with role=modify")
    out_dir = Path(artifact_dir) if artifact_dir else None
    for task in tasks:
        repo_path, registry_base_branch, repo_blockers, repo_warnings = resolve_plan_repo(task, plan_file, registry)
        if repo_path is None:
            item = {
                "schema": "codex-git-baseline-evidence-v1",
                "repo": "",
                "repo_name": str(task.get("repo") or task.get("name") or ""),
                "task_index": task.get("_index"),
                "blockers": repo_blockers,
                "warnings": repo_warnings,
                "decision": "blocked",
                "generated_at": now(),
            }
            label = repo_label(task, Path(str(task.get("repo_path") or task.get("path") or task.get("repo") or f"repo-{task.get('_index', 0)}")))
            results.append(item)
            if out_dir:
                write_json(out_dir / f"{label}-git_baseline_evidence.json", item)
            blockers.extend(f"{label}: {blocker}" for blocker in repo_blockers)
            continue
        base_branch = str(task.get("base_branch") or registry_base_branch or "")
        result = inspect(repo_path, remote, base_branch) if check_only else prepare(repo_path, branch, remote, base_branch)
        label = repo_label(task, repo_path)
        result["warnings"] = [*repo_warnings, *result.get("warnings", [])]
        result.update({
            "repo_name": str(task.get("repo") or task.get("name") or label),
            "task_index": task.get("_index"),
            "required_by": "delivery_plan.repo_tasks.role=modify",
            "plan_branch": branch,
            "check_only": check_only,
            "resolved_repo_path": str(repo_path),
        })
        results.append(result)
        if out_dir:
            write_json(out_dir / f"{label}-git_baseline_evidence.json", result)
        if result.get("decision") != "ready":
            blockers.extend(f"{label}: {blocker}" for blocker in result.get("blockers", []))
    summary = {
        "schema": "codex-git-plan-baseline-v1",
        "delivery_plan_file": str(plan_file),
        "doc_id": doc_id,
        "branch": branch,
        "check_only": check_only,
        "modify_repo_count": len(tasks),
        "results": results,
        "blockers": blockers,
        "warnings": [warning for item in results for warning in item.get("warnings", [])],
        "decision": "ready" if not blockers else "blocked",
        "generated_at": now(),
    }
    if out_dir:
        write_json(out_dir / "git_plan_baseline_summary.json", summary)
    return summary


def load_evidence(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def unquote_yaml_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_project_registry(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    projects: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        match = re.match(r"\s*-\s+name:\s*(.+)\s*$", line)
        if match:
            name = unquote_yaml_value(match.group(1))
            current = {"name": name}
            projects[name] = current
            continue
        if current is None:
            continue
        match = re.match(r"\s*(default_branch|local_path_hint|git_url):\s*(.+)\s*$", line)
        if match:
            current[match.group(1)] = unquote_yaml_value(match.group(2))
    return projects


def project_registry() -> dict[str, dict[str, str]]:
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    return parse_project_registry(codex_home / "skills" / "company" / "projects.yaml")


def is_git_checkout(path: Path) -> bool:
    return (path / ".git").exists()


def resolve_registered_checkout(entry: dict[str, str], current_root: Path | None = None) -> str:
    hint = str(entry.get("local_path_hint") or entry.get("name") or "").strip()
    if not hint:
        return ""
    hint_path = Path(hint).expanduser()
    candidates: list[Path] = []
    if hint_path.is_absolute():
        candidates.append(hint_path)
    else:
        roots: list[Path] = []
        if current_root:
            roots.append(current_root)
            roots.extend(current_root.parents)
        home = Path.home()
        roots.extend(sorted(path for path in home.glob("*workspace*") if path.is_dir()))
        roots.extend([home / "workspace", home / "workspaces", home])
        seen: set[Path] = set()
        for root in roots:
            try:
                resolved_root = root.expanduser().resolve()
            except OSError:
                continue
            if resolved_root in seen:
                continue
            seen.add(resolved_root)
            candidates.append(resolved_root / hint_path)
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if is_git_checkout(resolved):
            return str(resolved)
    return ""


def resolve_plan_repo(task: dict[str, Any], plan_file: Path, registry: dict[str, dict[str, str]]) -> tuple[Path | None, str, list[str], list[str]]:
    repo_name = str(task.get("repo") or task.get("name") or "").strip()
    raw_path = str(task.get("repo_path") or task.get("path") or "").strip()
    blockers: list[str] = []
    warnings: list[str] = []
    entry = registry.get(repo_name, {}) if repo_name else {}
    registered = resolve_registered_checkout(entry, plan_file.parent) if entry else ""
    if registered and raw_path and Path(raw_path).expanduser().resolve() != Path(registered).resolve():
        warnings.append(f"using registered checkout for {repo_name} instead of delivery_plan repo_path")
    if registered:
        return Path(registered).resolve(), str(entry.get("default_branch") or ""), blockers, warnings
    if not raw_path:
        blockers.append("modify repo task is missing repo_path")
        return None, "", blockers, warnings
    if is_staging_path(raw_path):
        blockers.append("modify repo_path points to _staging; resolve the registered project checkout before git prepare-plan")
        return None, str(entry.get("default_branch") or ""), blockers, warnings
    return Path(raw_path).expanduser().resolve(), str(entry.get("default_branch") or ""), blockers, warnings


def assert_ready(
    repo: Path,
    branch: str = "",
    evidence_file: str | None = None,
    remote: str = "origin",
    base_branch: str = "",
) -> dict[str, Any]:
    current = inspect(repo, remote, base_branch)
    evidence = load_evidence(evidence_file)
    blockers: list[str] = []
    warnings: list[str] = []
    current_branch = str(current.get("current_branch") or "")
    expected_branch = branch or str(evidence.get("new_branch") or evidence.get("branch") or evidence.get("plan_branch") or "")
    if current.get("decision") != "ready":
        blockers.extend(str(item) for item in current.get("blockers", []))
    if current_branch in DEFAULT_BRANCHES:
        blockers.append("current branch is default branch; editing is not allowed")
    if not current_branch:
        blockers.append("cannot detect current branch")
    if expected_branch and current_branch != expected_branch:
        blockers.append(f"current branch {current_branch} does not match expected branch {expected_branch}")
    if evidence_file:
        if not evidence:
            blockers.append("git baseline evidence file is missing or invalid")
        elif evidence.get("decision") != "ready":
            blockers.append("git baseline evidence decision is not ready")
        else:
            evidence_branch = str(evidence.get("new_branch") or evidence.get("branch") or evidence.get("plan_branch") or "")
            if evidence_branch and current_branch != evidence_branch:
                blockers.append(f"current branch {current_branch} does not match evidence branch {evidence_branch}")
            evidence_commit = str(evidence.get("baseline_commit") or "")
            current_commit = str(current.get("baseline_commit") or "")
            if evidence_commit and current_commit and evidence_commit != current_commit:
                warnings.append("current HEAD differs from git baseline evidence commit; review accumulated commits before release")
    return {
        "schema": "codex-git-edit-readiness-v1",
        "repo": str(repo.expanduser().resolve()),
        "current_branch": current_branch,
        "expected_branch": expected_branch,
        "status_clean_before": current.get("status_clean_before"),
        "status_short": current.get("status_short", []),
        "evidence_file": evidence_file or "",
        "evidence_decision": evidence.get("decision", "") if evidence else "",
        "blockers": blockers,
        "warnings": warnings,
        "decision": "ready" if not blockers else "blocked",
        "generated_at": now(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generic Git worktree governor")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check")
    p_check.add_argument("--repo", required=True)
    p_check.add_argument("--remote", default="origin")
    p_check.add_argument("--base-branch", default="")
    p_check.add_argument("--artifact-dir")

    p_prepare = sub.add_parser("prepare")
    p_prepare.add_argument("--repo", required=True)
    p_prepare.add_argument("--branch", required=True)
    p_prepare.add_argument("--remote", default="origin")
    p_prepare.add_argument("--base-branch", default="")
    p_prepare.add_argument("--artifact-dir")

    p_plan = sub.add_parser("prepare-plan")
    p_plan.add_argument("--delivery-plan", required=True)
    p_plan.add_argument("--doc-id", default="")
    p_plan.add_argument("--branch-prefix", default="feature")
    p_plan.add_argument("--remote", default="origin")
    p_plan.add_argument("--artifact-dir")
    p_plan.add_argument("--check-only", action="store_true")

    p_assert = sub.add_parser("assert-ready")
    p_assert.add_argument("--repo", required=True)
    p_assert.add_argument("--branch", default="")
    p_assert.add_argument("--evidence-file")
    p_assert.add_argument("--remote", default="origin")
    p_assert.add_argument("--base-branch", default="")

    args = parser.parse_args()
    if args.cmd == "check":
        evidence = inspect(Path(args.repo), args.remote, args.base_branch)
        write_artifact(args.artifact_dir, evidence)
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
        return 0 if evidence.get("decision") == "ready" else 1
    if args.cmd == "prepare":
        evidence = prepare(Path(args.repo), args.branch, args.remote, args.base_branch)
        write_artifact(args.artifact_dir, evidence)
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
        return 0 if evidence.get("decision") == "ready" else 1
    if args.cmd == "prepare-plan":
        evidence = prepare_plan(args.delivery_plan, args.branch_prefix, args.doc_id, args.artifact_dir, args.remote, args.check_only)
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
        return 0 if evidence.get("decision") == "ready" else 1
    if args.cmd == "assert-ready":
        evidence = assert_ready(Path(args.repo), args.branch, args.evidence_file, args.remote, args.base_branch)
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
        return 0 if evidence.get("decision") == "ready" else 1
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())
