#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


CORE_DIR = Path(__file__).resolve().parents[2]
GIT_WORKTREE = CORE_DIR / "git-worktree-governor/scripts/git_worktree.py"
DELIVERY_STATE = CORE_DIR / "delivery-state-governor/scripts/delivery_state.py"
FULL_DOC_LANES = {"standard_requirement", "large_prd", "migration"}
LIGHT_DOC_LANES = {"bugfix", "small_change", "hotfix"}
DEFAULT_BRANCHES = {"master", "main"}


def load_workflow_contract() -> Any:
    path = CORE_DIR / "delivery-runner/scripts/workflow_contract.py"
    spec = importlib.util.spec_from_file_location("edit_readiness_workflow_contract", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


WORKFLOW_CONTRACT = load_workflow_contract()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_utc(value: str) -> datetime | None:
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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


def run_json(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, text=True, capture_output=True)
    parsed: Any = {}
    if proc.stdout.strip():
        try:
            parsed = json.loads(proc.stdout)
        except Exception:
            parsed = {}
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "json": parsed if isinstance(parsed, dict) else {},
    }


def artifact(path: str) -> dict[str, Any]:
    p = Path(path) if path else None
    data = load_json(p) if p else {}
    return {
        "path": str(p.resolve()) if p and p.exists() else (str(p) if p else ""),
        "exists": bool(p and p.exists()),
        "schema": data.get("schema", ""),
        "decision": data.get("decision", ""),
    }


def artifact_ready(path: str, accepted: set[str]) -> bool:
    item = artifact(path)
    if not item["exists"]:
        return False
    decision = str(item.get("decision") or "")
    return not decision or decision in accepted


def docs_repo_check(args: argparse.Namespace) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    docs_root_value = str(getattr(args, "docs_root", "") or "")
    manifest_value = str(getattr(args, "docs_manifest", "") or "")
    if not docs_root_value:
        blockers.append("docs_root is required before editing")
        return {"decision": "blocked", "docs_root": "", "manifest": manifest_value, "blockers": blockers, "warnings": warnings}
    docs_root = Path(docs_root_value).expanduser()
    manifest = Path(manifest_value).expanduser() if manifest_value else docs_root / "indexes" / f"{args.doc_id}.manifest.json"
    if not docs_root.exists():
        blockers.append("docs_root does not exist")
    elif not (docs_root / ".git").exists():
        blockers.append("docs_root must be a git repository")
    if not manifest.exists():
        blockers.append("docs manifest is missing")
    return {
        "decision": "ready" if not blockers else "blocked",
        "docs_root": str(docs_root),
        "manifest": str(manifest),
        "blockers": blockers,
        "warnings": warnings,
    }


def design_evidence_check(args: argparse.Namespace) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    lane = args.lane
    items = {
        "spec": artifact(args.spec),
        "technical_design": artifact(args.technical_design),
        "architecture_design": artifact(args.architecture_design),
        "test_design": artifact(getattr(args, "test_design", "")),
        "delivery_plan": artifact(args.delivery_plan),
        "delivery_plan_review": artifact(args.delivery_plan_review),
        "design_review": artifact(args.design_review),
        "docs_quality": artifact(args.docs_quality),
        "reproduction": artifact(args.reproduction),
    }
    if lane in FULL_DOC_LANES:
        required = ["spec", "technical_design", "architecture_design", "test_design", "delivery_plan", "delivery_plan_review", "design_review", "docs_quality"]
        for key in required:
            if not items[key]["exists"]:
                blockers.append(f"missing required design artifact: {key}")
        review_data = load_json(args.delivery_plan_review)
        review_gate = review_data.get("readiness_gate", {}) if isinstance(review_data, dict) else {}
        if items["delivery_plan_review"]["exists"] and items["delivery_plan_review"]["decision"] not in {"pass", "ready", "approved"}:
            blockers.append("delivery_plan_review decision is not pass/ready/approved")
        if items["delivery_plan_review"]["exists"] and review_gate.get("implementation_allowed") is not True:
            blockers.append("delivery_plan_review does not allow implementation")
        if items["design_review"]["exists"] and items["design_review"]["decision"] not in {"approved", "pass", "ready"}:
            blockers.append("design_review decision is not approved/pass/ready")
        if items["docs_quality"]["exists"] and items["docs_quality"]["decision"] not in {"pass", "ready"}:
            blockers.append("docs_quality decision is not pass/ready")
    elif lane == "bugfix":
        if not items["reproduction"]["exists"] and not items["spec"]["exists"]:
            blockers.append("bugfix requires reproduction evidence or a lightweight spec before editing")
    elif lane == "small_change":
        if not items["technical_design"]["exists"] and not items["delivery_plan"]["exists"]:
            blockers.append("small_change requires lightweight technical design or delivery plan before editing")
    elif lane == "hotfix":
        if not items["reproduction"]["exists"] and not items["spec"]["exists"]:
            warnings.append("hotfix has no reproduction/spec evidence; retrofit documentation after implementation")
    else:
        blockers.append(f"unknown lane: {lane}")
    return {
        "decision": "ready" if not blockers else "blocked",
        "lane": lane,
        "artifacts": items,
        "blockers": blockers,
        "warnings": warnings,
    }


def delivery_plan_scope(delivery_plan: str | None, allowed_files: list[str]) -> dict[str, Any]:
    if not allowed_files:
        return {"decision": "ready", "checked": False, "warnings": ["no allowed files were bound"], "blockers": []}
    plan = load_json(delivery_plan)
    if not plan:
        return {"decision": "ready", "checked": False, "warnings": ["delivery plan missing; file scope cannot be checked"], "blockers": []}
    scope_text = json.dumps(plan, ensure_ascii=False).lower()
    out_of_scope: list[str] = []
    for item in allowed_files:
        normalized = item.strip().lower()
        basename = Path(normalized).name
        if normalized not in scope_text and basename not in scope_text:
            out_of_scope.append(item)
    blockers = [f"proposed file not referenced by delivery plan scope: {item}" for item in out_of_scope]
    return {
        "decision": "ready" if not blockers else "blocked",
        "checked": True,
        "allowed_files": allowed_files,
        "out_of_scope": out_of_scope,
        "warnings": [],
        "blockers": blockers,
    }


def delivery_state_check(delivery_state: str | None) -> dict[str, Any]:
    if not delivery_state:
        return {"decision": "skipped", "required": False, "blockers": [], "warnings": ["delivery state was not provided"]}
    path = Path(delivery_state)
    if not path.exists():
        return {"decision": "blocked", "required": True, "state": str(path), "blockers": [f"delivery state not found: {path}"], "warnings": []}
    result = run_json(["python3", str(DELIVERY_STATE), "validate", "--state", str(path), "--target", "implementation"])
    data = result["json"]
    blockers = list(data.get("blockers", [])) if isinstance(data.get("blockers"), list) else []
    missing = list(data.get("missing_gates", [])) if isinstance(data.get("missing_gates"), list) else []
    blockers.extend(f"delivery state missing gate: {item}" for item in missing)
    if result["returncode"] != 0 and not blockers:
        blockers.append(result["stderr"] or data.get("decision") or "delivery state is not implementation-ready")
    return {
        "decision": "ready" if not blockers else "blocked",
        "required": True,
        "state": str(path.resolve()),
        "validation": data,
        "blockers": blockers,
        "warnings": [],
    }


def git_check(args: argparse.Namespace) -> dict[str, Any]:
    cmd = ["python3", str(GIT_WORKTREE), "assert-ready", "--repo", args.repo]
    if args.branch:
        cmd.extend(["--branch", args.branch])
    if args.git_evidence:
        cmd.extend(["--evidence-file", args.git_evidence])
    result = run_json(cmd)
    data = result["json"]
    if not data:
        return {
            "decision": "blocked",
            "blockers": [result["stderr"] or "git readiness command failed"],
            "warnings": [],
            "returncode": result["returncode"],
        }
    return data


def assert_readiness(args: argparse.Namespace) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    if not args.doc_id and args.lane != "hotfix":
        blockers.append("doc_id is required before editing")
    if not args.git_evidence:
        blockers.append("git_evidence is required before editing")
    git = git_check(args)
    if git.get("decision") != "ready":
        blockers.extend(f"git: {item}" for item in git.get("blockers", []) or ["assert-ready failed"])
    warnings.extend(f"git: {item}" for item in git.get("warnings", []))
    current_branch = str(git.get("current_branch") or "")
    if current_branch in DEFAULT_BRANCHES:
        blockers.append("git: current branch is default branch; editing is not allowed")
    git_evidence_data = load_json(args.git_evidence)
    if git_evidence_data.get("fetched") is not True:
        blockers.append("git: fetch evidence is missing")
    if git_evidence_data.get("base_updated") is not True:
        blockers.append("git: pull --ff-only evidence is missing")

    design = design_evidence_check(args)
    if design.get("decision") != "ready":
        blockers.extend(f"design: {item}" for item in design.get("blockers", []))
    warnings.extend(f"design: {item}" for item in design.get("warnings", []))

    scope = delivery_plan_scope(args.delivery_plan, args.allowed_file)
    if scope.get("decision") != "ready":
        blockers.extend(f"scope: {item}" for item in scope.get("blockers", []))
    warnings.extend(f"scope: {item}" for item in scope.get("warnings", []))

    state = delivery_state_check(args.delivery_state)
    if state.get("decision") == "blocked":
        blockers.extend(f"state: {item}" for item in state.get("blockers", []))
    warnings.extend(f"state: {item}" for item in state.get("warnings", []))

    docs = docs_repo_check(args)
    if docs.get("decision") != "ready":
        blockers.extend(f"docs: {item}" for item in docs.get("blockers", []))
    warnings.extend(f"docs: {item}" for item in docs.get("warnings", []))

    return {
        "schema": "codex-edit-readiness-v1",
        "decision": "ready" if not blockers else "blocked",
        "repo": str(Path(args.repo).expanduser().resolve()),
        "doc_id": args.doc_id,
        "lane": args.lane,
        "git": git,
        "design": design,
        "scope": scope,
        "delivery_state": state,
        "docs": docs,
        "blockers": blockers,
        "warnings": warnings,
        "next_action": "create edit permit and proceed within scope" if not blockers else "fix blockers before any file write",
    }


def permit_payload(args: argparse.Namespace, readiness: dict[str, Any]) -> dict[str, Any]:
    issued_at = utc_now()
    ttl_minutes = max(1, int(args.ttl_minutes or 30))
    expires_at = issued_at + timedelta(minutes=ttl_minutes)
    branch = readiness.get("git", {}).get("current_branch") or readiness.get("git", {}).get("expected_branch") or args.branch
    payload = {
        "schema": "codex-edit-permit-v1",
        "permit_id": "",
        "decision": "ready",
        "repo": str(Path(args.repo).expanduser().resolve()),
        "doc_id": args.doc_id,
        "lane": args.lane,
        "branch": branch,
        "allowed_files": sorted(set(args.allowed_file)),
        "git_evidence": str(Path(args.git_evidence).expanduser().resolve()) if args.git_evidence else "",
        "delivery_state": str(Path(args.delivery_state).expanduser().resolve()) if args.delivery_state else "",
        "artifacts": {
            "spec": args.spec,
            "technical_design": args.technical_design,
            "architecture_design": args.architecture_design,
            "test_design": getattr(args, "test_design", ""),
            "delivery_plan": args.delivery_plan,
            "delivery_plan_review": args.delivery_plan_review,
            "design_review": args.design_review,
            "docs_quality": args.docs_quality,
            "reproduction": args.reproduction,
        },
        "readiness_hash": stable_hash({
            "git": readiness.get("git", {}),
            "design": readiness.get("design", {}),
            "scope": readiness.get("scope", {}),
            "delivery_state": readiness.get("delivery_state", {}),
            "docs": readiness.get("docs", {}),
        }),
        "issued_at": iso_z(issued_at),
        "expires_at": iso_z(expires_at),
        "ttl_minutes": ttl_minutes,
        "rule": "valid only for this repo, branch, doc_id, allowed files, evidence paths, and expiry window",
    }
    payload["permit_id"] = "EDIT-" + stable_hash(payload)[:16].upper()
    payload["readiness_summary"] = {
        "git_decision": readiness.get("git", {}).get("decision"),
        "design_decision": readiness.get("design", {}).get("decision"),
        "scope_decision": readiness.get("scope", {}).get("decision"),
        "delivery_state_decision": readiness.get("delivery_state", {}).get("decision"),
        "docs_decision": readiness.get("docs", {}).get("decision"),
    }
    return payload


def create_permit(args: argparse.Namespace) -> dict[str, Any]:
    readiness = assert_readiness(args)
    if readiness.get("decision") != "ready":
        return {
            "schema": "codex-edit-permit-v1",
            "decision": "blocked",
            "readiness": readiness,
            "blockers": readiness.get("blockers", []),
            "next_action": "fix readiness blockers before creating edit permit",
        }
    return permit_payload(args, readiness)


def verify_permit(args: argparse.Namespace) -> dict[str, Any]:
    permit = load_json(args.permit)
    blockers: list[str] = []
    warnings: list[str] = []
    if permit.get("schema") != "codex-edit-permit-v1":
        blockers.append("permit schema is not codex-edit-permit-v1")
    if permit.get("decision") != "ready":
        blockers.append("permit decision is not ready")
    expires = parse_utc(str(permit.get("expires_at", "")))
    if not expires:
        blockers.append("permit expires_at is invalid")
    elif utc_now() > expires:
        blockers.append(f"permit expired at {permit.get('expires_at')}")
    if args.repo and str(Path(args.repo).expanduser().resolve()) != permit.get("repo"):
        blockers.append("repo does not match permit")
    if args.doc_id and args.doc_id != permit.get("doc_id"):
        blockers.append("doc_id does not match permit")
    if args.branch and args.branch != permit.get("branch"):
        blockers.append("branch does not match permit")
    allowed = set(permit.get("allowed_files", []) or [])
    requested = set(args.allowed_file or [])
    if requested and allowed and not requested.issubset(allowed):
        blockers.append(f"requested files exceed permit scope: {sorted(requested - allowed)}")
    if requested and not allowed:
        warnings.append("permit has no allowed_files; file scope was not bound")
    return {
        "schema": "codex-edit-permit-verification-v1",
        "decision": "ready" if not blockers else "blocked",
        "permit_id": permit.get("permit_id", ""),
        "permit": str(args.permit),
        "blockers": blockers,
        "warnings": warnings,
        "next_action": "write may proceed within permit scope" if not blockers else "rerun edit-readiness permit after fixing blockers",
    }


def add_common_assert_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", required=True)
    parser.add_argument("--doc-id", default="")
    parser.add_argument("--lane", default="standard_requirement")
    parser.add_argument("--branch", default="")
    parser.add_argument("--git-evidence", default="")
    parser.add_argument("--delivery-state", default="")
    parser.add_argument("--spec", default="")
    parser.add_argument("--technical-design", default="")
    parser.add_argument("--architecture-design", default="")
    parser.add_argument("--test-design", default="")
    parser.add_argument("--delivery-plan", default="")
    parser.add_argument("--delivery-plan-review", default="")
    parser.add_argument("--design-review", default="")
    parser.add_argument("--docs-quality", default="")
    parser.add_argument("--docs-root", default="")
    parser.add_argument("--docs-manifest", default="")
    parser.add_argument("--reproduction", default="")
    parser.add_argument("--allowed-file", action="append", default=[])
    parser.add_argument("--out")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generic edit readiness governor")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_assert = sub.add_parser("assert")
    add_common_assert_args(p_assert)

    p_permit = sub.add_parser("permit")
    add_common_assert_args(p_permit)
    p_permit.add_argument("--ttl-minutes", type=int, default=30)

    p_verify = sub.add_parser("verify-permit")
    p_verify.add_argument("--permit", required=True)
    p_verify.add_argument("--repo", default="")
    p_verify.add_argument("--doc-id", default="")
    p_verify.add_argument("--branch", default="")
    p_verify.add_argument("--allowed-file", action="append", default=[])
    p_verify.add_argument("--out")

    p_scope = sub.add_parser("scope-check")
    p_scope.add_argument("--delivery-plan", required=True)
    p_scope.add_argument("--allowed-file", action="append", default=[])
    p_scope.add_argument("--out")

    args = parser.parse_args()
    if args.cmd == "assert":
        result = assert_readiness(args)
    elif args.cmd == "permit":
        result = create_permit(args)
    elif args.cmd == "verify-permit":
        result = verify_permit(args)
    elif args.cmd == "scope-check":
        result = delivery_plan_scope(args.delivery_plan, args.allowed_file)
    else:
        raise AssertionError(args.cmd)
    write_json(getattr(args, "out", None), result)
    if getattr(args, "out", None):
        output = Path(args.out)
        WORKFLOW_CONTRACT.bind_lineage(output, f"edit-readiness:{args.cmd}", WORKFLOW_CONTRACT.command_input_paths(sys.argv, output))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("decision") == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
