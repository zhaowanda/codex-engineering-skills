#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_workflow_contract() -> Any:
    path = Path(__file__).resolve().parents[2] / "delivery-runner/scripts/workflow_contract.py"
    spec = importlib.util.spec_from_file_location("write_guard_workflow_contract", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


WORKFLOW_CONTRACT = load_workflow_contract()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_time(value: str) -> datetime | None:
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def load_json(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: str | Path | None, data: dict[str, Any]) -> None:
    if not path:
        return
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def git(repo: Path, args: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def normalize(rel: str) -> str:
    return rel.strip().replace("\\", "/").lstrip("./")


def is_staging_path(path: str | Path) -> bool:
    return any(part == "_staging" or part.endswith("_staging") for part in Path(path).parts)


def changed_files(repo: Path) -> list[str]:
    files: list[str] = []
    for args in (["diff", "--name-only"], ["diff", "--cached", "--name-only"]):
        code, out, _ = git(repo, args)
        if code == 0 and out:
            files.extend(line.strip() for line in out.splitlines() if line.strip())
    code, out, _ = git(repo, ["ls-files", "--others", "--exclude-standard"])
    if code == 0 and out:
        files.extend(line.strip() for line in out.splitlines() if line.strip())
    return sorted(set(files))


def repo_relative(repo: Path, path_value: str | Path | None) -> str:
    if not path_value:
        return ""
    try:
        path = Path(path_value).resolve()
        return normalize(str(path.relative_to(repo)))
    except Exception:
        return ""


def current_branch(repo: Path) -> str:
    code, out, _ = git(repo, ["branch", "--show-current"])
    return out if code == 0 else ""


def file_mtime(repo: Path, rel: str) -> str:
    path = repo / rel
    if not path.exists():
        return ""
    return iso_z(datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc))


def permit_allowed(permit: dict[str, Any]) -> set[str]:
    return {normalize(str(item)) for item in permit.get("allowed_files", []) or []}


def verify_permit(repo: Path, permit: dict[str, Any], doc_id: str = "") -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    if permit.get("schema") != "codex-edit-permit-v1":
        blockers.append("permit schema is not codex-edit-permit-v1")
    if permit.get("decision") != "ready":
        blockers.append("permit decision is not ready")
    permit_repo = str(permit.get("repo") or "")
    if is_staging_path(repo):
        blockers.append("repo path points to _staging; writes require the registered project checkout")
    if permit_repo and is_staging_path(permit_repo):
        blockers.append("permit repo points to _staging; recreate edit permit for the registered project checkout")
    if permit_repo and str(repo.resolve()) != permit_repo:
        blockers.append("repo does not match permit")
    if doc_id and permit.get("doc_id") and doc_id != permit.get("doc_id"):
        blockers.append("doc_id does not match permit")
    expires = parse_time(str(permit.get("expires_at", "")))
    if not expires:
        blockers.append("permit expires_at is invalid")
    elif utc_now() > expires:
        blockers.append(f"permit expired at {permit.get('expires_at')}")
    branch = current_branch(repo)
    permit_branch = str(permit.get("branch") or "")
    if branch in {"master", "main"}:
        blockers.append(f"current branch is default branch: {branch}")
    if permit_branch and branch and branch != permit_branch:
        blockers.append(f"current branch {branch} does not match permit branch {permit_branch}")
    if not permit_allowed(permit):
        warnings.append("permit has no allowed_files; audit cannot enforce file scope")
    return blockers, warnings


def create_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(args.repo).resolve()
    permit = load_json(args.permit)
    blockers, warnings = verify_permit(repo, permit, args.doc_id)
    files = changed_files(repo)
    result = {
        "schema": "codex-write-guard-snapshot-v1",
        "decision": "ready" if not blockers else "blocked",
        "repo": str(repo),
        "doc_id": args.doc_id or permit.get("doc_id", ""),
        "permit": str(Path(args.permit).resolve()),
        "permit_id": permit.get("permit_id", ""),
        "branch": current_branch(repo),
        "changed_files_at_snapshot": files,
        "file_mtimes": {rel: file_mtime(repo, rel) for rel in files},
        "created_at": iso_z(utc_now()),
        "blockers": blockers,
        "warnings": warnings,
    }
    if files and args.require_clean:
        result["decision"] = "blocked"
        result["blockers"].append("repo already has changed files before snapshot")
    write_json(args.out, result)
    return result


def audit(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(args.repo).resolve()
    permit = load_json(args.permit)
    snapshot = load_json(args.snapshot)
    blockers, warnings = verify_permit(repo, permit, args.doc_id)
    ignored = {
        repo_relative(repo, args.permit),
        repo_relative(repo, args.snapshot),
        repo_relative(repo, args.out),
    }
    ignored.discard("")
    raw_files = changed_files(repo)
    files = [rel for rel in raw_files if normalize(rel) not in ignored]
    allowed = permit_allowed(permit)
    unauthorized: list[str] = []
    if allowed:
        unauthorized = [rel for rel in files if normalize(rel) not in allowed]
        blockers.extend(f"changed file outside permit scope: {rel}" for rel in unauthorized)
    issued_at = parse_time(str(permit.get("issued_at", "")))
    pre_authorized: list[str] = []
    if issued_at:
        for rel in files:
            mtime = parse_time(file_mtime(repo, rel))
            if mtime and mtime < issued_at:
                pre_authorized.append(rel)
        blockers.extend(f"changed file mtime is before permit issued_at: {rel}" for rel in pre_authorized)
    else:
        warnings.append("permit issued_at is invalid; write timing cannot be checked")
    snapshot_files = set(snapshot.get("changed_files_at_snapshot", []) or [])
    new_files = [rel for rel in files if rel not in snapshot_files]
    result = {
        "schema": "codex-write-guard-audit-v1",
        "decision": "ready" if not blockers else "blocked",
        "repo": str(repo),
        "doc_id": args.doc_id or permit.get("doc_id", ""),
        "permit": str(Path(args.permit).resolve()),
        "permit_id": permit.get("permit_id", ""),
        "snapshot": str(Path(args.snapshot).resolve()) if args.snapshot else "",
        "branch": current_branch(repo),
        "changed_files": files,
        "ignored_evidence_files": sorted(ignored),
        "new_files_since_snapshot": new_files,
        "unauthorized_files": unauthorized,
        "pre_authorization_mtime_files": pre_authorized,
        "file_mtimes": {rel: file_mtime(repo, rel) for rel in files},
        "audited_at": iso_z(utc_now()),
        "blockers": blockers,
        "warnings": warnings,
    }
    write_json(args.out, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit workspace writes against edit permits")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_snapshot = sub.add_parser("snapshot")
    p_snapshot.add_argument("--repo", required=True)
    p_snapshot.add_argument("--permit", required=True)
    p_snapshot.add_argument("--doc-id", default="")
    p_snapshot.add_argument("--require-clean", action="store_true")
    p_snapshot.add_argument("--out")
    p_audit = sub.add_parser("audit")
    p_audit.add_argument("--repo", required=True)
    p_audit.add_argument("--permit", required=True)
    p_audit.add_argument("--snapshot", default="")
    p_audit.add_argument("--doc-id", default="")
    p_audit.add_argument("--out")
    p_hook = sub.add_parser("hook-check")
    p_hook.add_argument("--repo", required=True)
    p_hook.add_argument("--permit", required=True)
    p_hook.add_argument("--snapshot", default="")
    p_hook.add_argument("--doc-id", default="")
    p_hook.add_argument("--out")
    args = parser.parse_args()
    result = create_snapshot(args) if args.cmd == "snapshot" else audit(args)
    if args.out:
        output = Path(args.out)
        WORKFLOW_CONTRACT.bind_lineage(output, f"workspace-write-guard:{args.cmd}", WORKFLOW_CONTRACT.command_input_paths(sys.argv, output), command=sys.argv)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("decision") == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
