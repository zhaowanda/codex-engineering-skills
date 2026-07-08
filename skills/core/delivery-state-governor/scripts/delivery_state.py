#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA = "codex-delivery-state-v1"

LANE_GATES = {
    "hotfix": ["doc_id", "git", "implementation", "review", "test", "release", "case_capture"],
    "bugfix": ["doc_id", "reproduction", "git", "implementation", "review", "test", "release"],
    "small_change": ["doc_id", "light_design", "git", "implementation", "review", "test"],
    "standard_requirement": [
        "doc_id",
        "spec",
        "technical_design",
        "architecture_design",
        "delivery_plan",
        "docs_quality",
        "design_review",
        "freeze",
        "git",
        "implementation",
        "review",
        "test",
        "release",
    ],
    "large_prd": [
        "doc_id",
        "ingestion",
        "spec",
        "technical_design",
        "architecture_design",
        "delivery_plan",
        "qa_traceability",
        "docs_quality",
        "design_review",
        "freeze",
        "git",
        "implementation",
        "review",
        "test",
        "uat",
        "release",
        "post_release",
    ],
    "migration": [
        "doc_id",
        "current_baseline",
        "target_architecture",
        "migration_plan",
        "compatibility",
        "dual_run",
        "rollback",
        "git",
        "implementation",
        "integration_test",
        "uat",
        "release",
        "post_release",
    ],
    "review_only": ["doc_id", "review"],
    "docs_reverse": ["doc_id", "baseline_reverse", "owner_review"],
}

TARGET_REQUIRED = {
    "implementation": {
        "bugfix": ["doc_id", "reproduction", "git"],
        "small_change": ["doc_id", "light_design", "git"],
        "standard_requirement": ["doc_id", "spec", "technical_design", "architecture_design", "delivery_plan", "docs_quality", "design_review", "freeze", "git"],
        "large_prd": ["doc_id", "ingestion", "spec", "technical_design", "architecture_design", "delivery_plan", "qa_traceability", "docs_quality", "design_review", "freeze", "git"],
        "migration": ["doc_id", "current_baseline", "target_architecture", "migration_plan", "compatibility", "rollback", "git"],
    },
    "release": {
        "hotfix": ["doc_id", "git", "implementation", "review", "test", "release"],
        "bugfix": ["doc_id", "reproduction", "git", "implementation", "review", "test", "release"],
        "small_change": ["doc_id", "light_design", "git", "implementation", "review", "test"],
        "standard_requirement": ["doc_id", "spec", "technical_design", "architecture_design", "delivery_plan", "git", "implementation", "review", "test", "release"],
        "large_prd": ["doc_id", "ingestion", "spec", "technical_design", "architecture_design", "delivery_plan", "qa_traceability", "git", "implementation", "review", "test", "uat", "release"],
        "migration": ["doc_id", "current_baseline", "target_architecture", "migration_plan", "compatibility", "dual_run", "rollback", "git", "implementation", "integration_test", "uat", "release"],
    },
}


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"not a JSON object: {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def event(action: str, **kwargs: Any) -> dict[str, Any]:
    return {"at": now(), "action": action, **kwargs}


def next_gate(passed: list[str], required: list[str]) -> str:
    for gate in required:
        if gate not in passed:
            return gate
    return "none"


def init_state(doc_id: str, lane: str, artifact_dir: Path, repos: list[str] | None = None) -> dict[str, Any]:
    if lane not in LANE_GATES:
        raise SystemExit(f"unknown lane: {lane}; valid={', '.join(sorted(LANE_GATES))}")
    gates = LANE_GATES[lane]
    state = {
        "schema": SCHEMA,
        "doc_id": doc_id,
        "lane": lane,
        "current_stage": "doc_id",
        "status": "ready",
        "required_gates": gates,
        "passed_gates": ["doc_id"],
        "evidence": {"doc_id": doc_id},
        "repo_states": [
            {"repo": repo, "status": "planned", "current_stage": "planning", "blockers": [], "evidence": {}}
            for repo in list(dict.fromkeys(repos or []))
        ],
        "integration_gates": [],
        "blockers": [],
        "next_action": f"complete next gate: {next_gate(['doc_id'], gates)}",
        "history": [event("init", doc_id=doc_id, lane=lane)],
    }
    write_json(artifact_dir / "delivery_state.json", state)
    return state


def load_state(path: Path) -> dict[str, Any]:
    state = read_json(path)
    if state.get("schema") != SCHEMA:
        raise ValueError(f"unsupported schema: {state.get('schema')}")
    return state


def inspect_state(path: Path) -> dict[str, Any]:
    state = load_state(path)
    missing = [gate for gate in state.get("required_gates", []) if gate not in set(state.get("passed_gates", []))]
    result = {
        "schema": "codex-delivery-state-inspection-v1",
        "doc_id": state.get("doc_id"),
        "lane": state.get("lane"),
        "status": state.get("status"),
        "current_stage": state.get("current_stage"),
        "next_gate": missing[0] if missing else "none",
        "missing_gates": missing,
        "blockers": state.get("blockers", []),
        "next_action": state.get("next_action", ""),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def advance_state(path: Path, stage: str, gate: str, evidence: str | None) -> dict[str, Any]:
    state = load_state(path)
    required = state.get("required_gates", [])
    if gate not in required:
        state.setdefault("history", []).append(event("warning", message=f"advanced non-required gate: {gate}"))
    passed = list(dict.fromkeys([*state.get("passed_gates", []), gate]))
    state["current_stage"] = stage
    state["passed_gates"] = passed
    if evidence:
        state.setdefault("evidence", {})[gate] = evidence
    state["blockers"] = []
    state["status"] = "ready" if next_gate(passed, required) != "none" else "closed"
    state["next_action"] = f"complete next gate: {next_gate(passed, required)}"
    state.setdefault("history", []).append(event("advance", stage=stage, gate=gate, evidence=evidence or ""))
    write_json(path, state)
    return state


def block_state(path: Path, reason: str, next_action_text: str) -> dict[str, Any]:
    state = load_state(path)
    state["status"] = "blocked"
    state.setdefault("blockers", []).append(reason)
    state["next_action"] = next_action_text or "resolve blocker and rerun the blocked gate"
    state.setdefault("history", []).append(event("block", reason=reason, next_action=state["next_action"]))
    write_json(path, state)
    return state


def unblock_state(path: Path, reason: str, evidence: str | None) -> dict[str, Any]:
    state = load_state(path)
    state["status"] = "ready"
    state["blockers"] = []
    state["next_action"] = f"complete next gate: {next_gate(state.get('passed_gates', []), state.get('required_gates', []))}"
    if evidence:
        state.setdefault("evidence", {})["unblock"] = evidence
    state.setdefault("history", []).append(event("unblock", reason=reason, evidence=evidence or ""))
    write_json(path, state)
    return state


def validate_state(path: Path, target: str) -> dict[str, Any]:
    state = load_state(path)
    lane = state.get("lane", "")
    required = TARGET_REQUIRED.get(target, {}).get(lane, [])
    passed = set(state.get("passed_gates", []))
    missing = [gate for gate in required if gate not in passed]
    blockers = list(state.get("blockers", []))
    for repo_state in state.get("repo_states", []) if isinstance(state.get("repo_states"), list) else []:
        if isinstance(repo_state, dict) and repo_state.get("status") == "blocked":
            blockers.append(f"{repo_state.get('repo', 'unknown')}: repo state is blocked")
        if isinstance(repo_state, dict) and target == "implementation":
            evidence = repo_state.get("evidence") if isinstance(repo_state.get("evidence"), dict) else {}
            if repo_state.get("requires_git") and not evidence.get("git"):
                blockers.append(f"{repo_state.get('repo', 'unknown')}: git evidence is required before implementation")
            if repo_state.get("requires_edit_permit") and not evidence.get("edit_permit"):
                blockers.append(f"{repo_state.get('repo', 'unknown')}: edit permit evidence is required before implementation")
    if target == "release":
        for gate in state.get("integration_gates", []) if isinstance(state.get("integration_gates"), list) else []:
            if not isinstance(gate, dict):
                blockers.append("integration gate entry must be an object")
                continue
            status = str(gate.get("status") or "")
            if status not in {"passed", "ready", "complete", "waived"}:
                blockers.append(f"{gate.get('gate', 'unknown')}: integration gate is not complete")
    if state.get("status") == "blocked" and not blockers:
        blockers.append("state is blocked")
    decision = "ready" if not missing and not blockers else "blocked"
    result = {
        "schema": "codex-delivery-state-validation-v1",
        "target": target,
        "doc_id": state.get("doc_id"),
        "lane": lane,
        "decision": decision,
        "missing_gates": missing,
        "blockers": blockers,
        "next_action": "proceed" if decision == "ready" else (state.get("next_action") or f"complete gate: {missing[0] if missing else 'unblock'}"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Maintain canonical delivery_state.json")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_init = sub.add_parser("init")
    p_init.add_argument("--doc-id", required=True)
    p_init.add_argument("--lane", required=True)
    p_init.add_argument("--artifact-dir", required=True)
    p_init.add_argument("--repo", action="append", default=[])
    p_inspect = sub.add_parser("inspect")
    p_inspect.add_argument("--state", required=True)
    p_advance = sub.add_parser("advance")
    p_advance.add_argument("--state", required=True)
    p_advance.add_argument("--stage", required=True)
    p_advance.add_argument("--gate", required=True)
    p_advance.add_argument("--evidence")
    p_block = sub.add_parser("block")
    p_block.add_argument("--state", required=True)
    p_block.add_argument("--reason", required=True)
    p_block.add_argument("--next-action", default="")
    p_unblock = sub.add_parser("unblock")
    p_unblock.add_argument("--state", required=True)
    p_unblock.add_argument("--reason", required=True)
    p_unblock.add_argument("--evidence")
    p_validate = sub.add_parser("validate")
    p_validate.add_argument("--state", required=True)
    p_validate.add_argument("--target", choices=["implementation", "release"], required=True)
    args = parser.parse_args()

    if args.cmd == "init":
        result = init_state(args.doc_id, args.lane, Path(args.artifact_dir), args.repo)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "inspect":
        inspect_state(Path(args.state))
        return 0
    if args.cmd == "advance":
        result = advance_state(Path(args.state), args.stage, args.gate, args.evidence)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "block":
        result = block_state(Path(args.state), args.reason, args.next_action)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1
    if args.cmd == "unblock":
        result = unblock_state(Path(args.state), args.reason, args.evidence)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "validate":
        result = validate_state(Path(args.state), args.target)
        return 0 if result["decision"] == "ready" else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
