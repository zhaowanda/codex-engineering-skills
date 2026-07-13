#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ARTIFACTS = ["spec.json", "technical_design.json", "architecture_design.json", "delivery_plan.json", "design_architecture_review.json", "code_review_gate.json", "test_evidence_gate.json", "release_gate.json"]
REPLAY_SCHEMA = "codex-delivery-replay-skeleton-v1"
LOCAL_PATH_RE = re.compile("(" + "/U" + r"sers/|" + "/v" + r"ar/folders/|" + "/p" + r"rivate/var/|[A-Za-z]:\\\\)")
PRIVATE_CONTENT_RE = re.compile(r"(source_code|customer_name|secret|password|token|api_key)", re.IGNORECASE)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def summarize(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": data.get("schema", ""),
        "decision": data.get("decision", data.get("status", "")),
        "blocker_count": len(data.get("blockers", []) if isinstance(data.get("blockers"), list) else []),
        "warning_count": len(data.get("warnings", []) if isinstance(data.get("warnings"), list) else []),
    }


def capture(artifact_dir: Path, case_id: str) -> dict[str, Any]:
    summaries = {}
    blockers = []
    for name in ARTIFACTS:
        data = load_json(artifact_dir / name)
        if data:
            summaries[name] = summarize(data)
            if data.get("blockers"):
                blockers.append({"artifact": name, "blockers": data.get("blockers")})
    return {
        "schema": "codex-delivery-case-v1",
        "case_id": case_id,
        "artifact_dir": str(artifact_dir),
        "artifact_summaries": summaries,
        "blockers_observed": blockers,
        "lessons": [],
        "skill_improvement_candidates": [],
        "privacy_note": "Review before sharing; keep real project/customer details in private overlays.",
    }


def replay_skeleton(artifact_dir: Path, case_id: str, scenario: str = "unclassified") -> dict[str, Any]:
    case = capture(artifact_dir, case_id)
    artifacts = []
    for name, summary in case["artifact_summaries"].items():
        artifacts.append({
            "artifact": name,
            "schema": summary.get("schema", ""),
            "decision": summary.get("decision", ""),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
        })
    return {
        "schema": REPLAY_SCHEMA,
        "case_id": case_id,
        "anonymized": True,
        "source_type": "synthetic",
        "scenario": scenario,
        "source": "artifact_summaries_only",
        "artifacts": artifacts,
        "replay_steps": [
            {"step": "ingest_requirement", "expected_artifact": "spec.json"},
            {"step": "review_design", "expected_artifact": "design_architecture_review.json"},
            {"step": "review_delivery", "expected_artifact": "delivery_plan.json"},
            {"step": "review_tests", "expected_artifact": "test_evidence_gate.json"},
            {"step": "bind_release", "expected_artifact": "release_gate.json"},
        ],
        "privacy_note": "No source text, customer names, repo paths, or local absolute paths are included.",
    }


def validate_replay_case(path: Path) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    raw = read_text(path)
    try:
        data = json.loads(raw)
    except Exception as exc:
        return {
            "path": str(path),
            "valid": False,
            "blockers": [{"source": "json", "message": f"invalid JSON: {exc}"}],
            "warnings": [],
        }
    if not isinstance(data, dict):
        blockers.append({"source": "shape", "message": "replay case must be a JSON object"})
        data = {}
    required = ["schema", "case_id", "anonymized", "source_type", "scenario", "source", "artifacts", "replay_steps", "privacy_note"]
    missing = [name for name in required if name not in data]
    if missing:
        blockers.append({"source": "required_fields", "message": f"missing fields: {', '.join(missing)}"})
    if data.get("schema") != REPLAY_SCHEMA:
        blockers.append({"source": "schema", "message": f"schema must be {REPLAY_SCHEMA}"})
    if data.get("anonymized") is not True:
        blockers.append({"source": "privacy", "message": "anonymized must be true"})
    if data.get("source") != "artifact_summaries_only":
        blockers.append({"source": "privacy", "message": "source must be artifact_summaries_only"})
    source_type = str(data.get("source_type") or "synthetic")
    if source_type not in {"synthetic", "anonymized_real_project"}:
        blockers.append({"source": "source_type", "message": "source_type must be synthetic or anonymized_real_project"})
    if source_type == "anonymized_real_project":
        privacy_review = data.get("privacy_review") if isinstance(data.get("privacy_review"), dict) else {}
        ground_truth = data.get("ground_truth") if isinstance(data.get("ground_truth"), dict) else {}
        if privacy_review.get("decision") != "approved" or not privacy_review.get("reviewer") or not privacy_review.get("reviewed_at"):
            blockers.append({"source": "privacy_review", "message": "real-project replay requires approved privacy review with reviewer and reviewed_at"})
        for field in ["expert_decision", "framework_decision", "risk_level"]:
            if not ground_truth.get(field):
                blockers.append({"source": "ground_truth", "message": f"real-project replay requires {field}"})
        if ground_truth.get("match") is not isinstance(ground_truth.get("match"), bool):
            blockers.append({"source": "ground_truth", "message": "real-project replay requires boolean match"})
    if LOCAL_PATH_RE.search(raw):
        blockers.append({"source": "privacy", "message": "local absolute path detected"})
    if PRIVATE_CONTENT_RE.search(raw):
        blockers.append({"source": "privacy", "message": "private content marker detected"})
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        blockers.append({"source": "artifacts", "message": "artifacts must be a non-empty list"})
        artifacts = []
    artifact_names = set()
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            blockers.append({"source": "artifacts", "message": f"artifact {index} must be an object"})
            continue
        missing_artifact = [name for name in ["artifact", "schema", "decision", "blocker_count", "warning_count"] if name not in artifact]
        if missing_artifact:
            blockers.append({"source": "artifacts", "message": f"artifact {index} missing fields: {', '.join(missing_artifact)}"})
        name = str(artifact.get("artifact") or "")
        if name:
            artifact_names.add(name)
        for count_name in ["blocker_count", "warning_count"]:
            if not isinstance(artifact.get(count_name), int) or artifact.get(count_name, -1) < 0:
                blockers.append({"source": "artifacts", "message": f"{name or index} {count_name} must be a non-negative integer"})
    steps = data.get("replay_steps")
    if not isinstance(steps, list) or not steps:
        blockers.append({"source": "replay_steps", "message": "replay_steps must be a non-empty list"})
        steps = []
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            blockers.append({"source": "replay_steps", "message": f"step {index} must be an object"})
            continue
        if not step.get("step") or not step.get("expected_artifact"):
            blockers.append({"source": "replay_steps", "message": f"step {index} needs step and expected_artifact"})
        expected = str(step.get("expected_artifact") or "")
        if expected and artifact_names and expected not in artifact_names:
            blockers.append({"source": "replay_steps", "message": f"step {index} references unknown artifact {expected}"})
    if len(artifacts) < 2:
        warnings.append({"source": "coverage", "message": "replay case should include at least two artifact summaries"})
    return {
        "path": str(path),
        "case_id": data.get("case_id", ""),
        "scenario": data.get("scenario", ""),
        "source_type": source_type,
        "ground_truth_match": (data.get("ground_truth") or {}).get("match") if isinstance(data.get("ground_truth"), dict) else None,
        "artifact_count": len(artifacts),
        "step_count": len(steps),
        "valid": not blockers,
        "blockers": blockers,
        "warnings": warnings,
    }


def validate_replay_dir(replay_dir: Path) -> dict[str, Any]:
    cases = [validate_replay_case(path) for path in sorted(replay_dir.glob("*.replay.json"))]
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not cases:
        blockers.append({"source": "replay_dir", "message": "no *.replay.json cases found"})
    for case in cases:
        for blocker in case["blockers"]:
            blockers.append({"source": case["path"], "message": blocker["message"], "detail": blocker.get("source")})
        for warning in case["warnings"]:
            warnings.append({"source": case["path"], "message": warning["message"], "detail": warning.get("source")})
    scenarios = sorted({str(case.get("scenario") or "") for case in cases if case.get("scenario")})
    complex_cases = [
        case for case in cases
        if int(case.get("artifact_count") or 0) >= 4 and int(case.get("step_count") or 0) >= 4
    ]
    scenario_families = {
        "frontend": any("frontend" in scenario for scenario in scenarios),
        "backend": any("backend" in scenario or "api" in scenario for scenario in scenarios),
        "data_or_config": any("data" in scenario or "config" in scenario for scenario in scenarios),
        "cross_repo": any("cross_repo" in scenario for scenario in scenarios),
        "release": any("release" in scenario for scenario in scenarios),
        "fullstack": any("fullstack" in scenario for scenario in scenarios),
    }
    covered_family_count = sum(1 for covered in scenario_families.values() if covered)
    real_cases = [case for case in cases if case.get("source_type") == "anonymized_real_project"]
    evaluated_real_cases = [case for case in real_cases if isinstance(case.get("ground_truth_match"), bool)]
    agreement_count = sum(1 for case in evaluated_real_cases if case.get("ground_truth_match") is True)
    return {
        "schema": "codex-delivery-replay-validation-v1",
        "decision": "block" if blockers else "pass",
        "case_count": len(cases),
        "scenario_count": len(scenarios),
        "complex_case_count": len(complex_cases),
        "scenario_families": scenario_families,
        "scenario_family_coverage_count": covered_family_count,
        "behavior_coverage_score": min(100, (len(complex_cases) * 12) + (covered_family_count * 10)),
        "real_project_replay_count": len(real_cases),
        "real_project_agreement_rate": round(100 * agreement_count / len(evaluated_real_cases), 2) if evaluated_real_cases else 0,
        "scenarios": scenarios,
        "cases": cases,
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture delivery case summary")
    parser.add_argument("--artifact-dir")
    parser.add_argument("--case-id")
    parser.add_argument("--out")
    parser.add_argument("--replay-skeleton", action="store_true")
    parser.add_argument("--scenario", default="unclassified")
    parser.add_argument("--validate-replay-dir")
    args = parser.parse_args()
    if args.validate_replay_dir:
        result = validate_replay_dir(Path(args.validate_replay_dir))
    else:
        if not args.artifact_dir or not args.case_id or not args.out:
            parser.error("--artifact-dir, --case-id, and --out are required unless --validate-replay-dir is used")
        result = replay_skeleton(Path(args.artifact_dir), args.case_id, args.scenario) if args.replay_skeleton else capture(Path(args.artifact_dir), args.case_id)
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("decision") != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
