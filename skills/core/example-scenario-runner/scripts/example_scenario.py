#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-example-scenario-run-v1"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def classify(text: str, name: str = "") -> str:
    if name in {"bugfix", "small-feature", "config-change", "frontend-change", "cross-repo-api", "data-migration", "release-readiness", "code-review"}:
        return name
    lower = text.lower()
    if "release" in lower or "rollback" in lower:
        return "release-readiness"
    if "code review" in lower or "diff" in lower:
        return "code-review"
    if "api" in lower or "cross-repo" in lower or "contract" in lower:
        return "cross-repo-api"
    if "migration" in lower or "database" in lower or "data" in lower:
        return "data-migration"
    if "bug" in lower or "fix" in lower:
        return "bugfix"
    if "config" in lower or "environment" in lower:
        return "config-change"
    if "ui" in lower or "frontend" in lower or "page" in lower:
        return "frontend-change"
    return "small-feature"


def render_summary(name: str, requirement: str) -> dict[str, Any]:
    kind = classify(requirement, name)
    risk = "high" if kind in {"config-change", "data-migration", "release-readiness", "cross-repo-api"} else "medium" if kind in {"frontend-change", "code-review"} else "low" if kind == "bugfix" else "medium"
    required_controls = ["code review", "test evidence"]
    if kind == "config-change":
        required_controls.append("configuration readiness")
    if kind == "frontend-change":
        required_controls.append("browser acceptance")
    if kind == "cross-repo-api":
        required_controls.extend(["project understanding", "contract traceability"])
    if kind == "data-migration":
        required_controls.extend(["data security review", "rollback evidence", "performance evidence"])
    if kind == "release-readiness":
        required_controls.extend(["environment promotion", "UAT acceptance", "release change approval"])
    if kind == "code-review":
        required_controls.extend(["diff impact", "write guard audit"])
    return {
        "name": name,
        "kind": kind,
        "spec": {"summary": requirement.strip().splitlines()[0] if requirement.strip() else "", "acceptance_criteria": ["behavior is verified", "regression is covered"]},
        "technical_design": {"modules": ["affected module"], "api_or_ui": "frontend route" if kind == "frontend-change" else "service behavior", "data_flow": ["input", "validation", "output"]},
        "architecture_design": {"boundaries": ["single example repo"], "rollback": ["revert commit"], "compatibility": "backward compatible"},
        "test_design": {"cases": ["functional test", "regression test"] + (["browser acceptance"] if kind == "frontend-change" else [])},
        "traceability": {"acceptance_covered": True, "task_scope_defined": True},
        "risk": {"level": risk, "required_controls": required_controls},
    }


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def validate_replay(name: str, path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    replay = load_json(path)
    blockers: list[dict[str, Any]] = []
    rendered = json.dumps(replay, ensure_ascii=False)
    if replay.get("schema") != "codex-delivery-replay-skeleton-v1":
        blockers.append({"source": name, "message": "replay schema must be codex-delivery-replay-skeleton-v1"})
    if replay.get("anonymized") is not True:
        blockers.append({"source": name, "message": "replay must declare anonymized=true"})
    private_markers = ["/" + "Users/", "/" + "var/folders/", "source" + "_code"]
    if any(marker in rendered for marker in private_markers):
        blockers.append({"source": name, "message": "replay contains local paths or source text markers"})
    return replay, blockers


def run(root: Path, out: Path) -> dict[str, Any]:
    scenario_root = root / "examples/scenarios"
    blockers: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []
    names = sorted(path.parent.name for path in scenario_root.glob("*/requirement.md"))
    for name in names:
        requirement_path = scenario_root / name / "requirement.md"
        requirement = read(requirement_path)
        if not requirement:
            blockers.append({"source": name, "message": "requirement.md is missing or empty"})
            continue
        summary = render_summary(name, requirement)
        replay_path = scenario_root / name / "replay.json"
        replay = {}
        if replay_path.exists():
            replay, replay_blockers = validate_replay(name, replay_path)
            blockers.extend(replay_blockers)
            summary["replay"] = {"schema": replay.get("schema", ""), "artifact_count": len(replay.get("artifacts", []) if isinstance(replay.get("artifacts"), list) else [])}
        scenario_out = out / name
        scenario_out.mkdir(parents=True, exist_ok=True)
        (scenario_out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        cases.append({"name": name, "passed": True, "summary": str((scenario_out / "summary.json"))})
    return {
        "schema": SCHEMA,
        "decision": "block" if blockers else "pass",
        "scenario_count": len(cases),
        "cases": cases,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run synthetic example scenarios")
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    output = run(Path(args.root), Path(args.out))
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
