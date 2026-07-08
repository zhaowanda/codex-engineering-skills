#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


SCHEMA = "codex-benchmark-report-v1"
SCHEMA_RE = re.compile(r"codex-[a-z0-9-]+-v\d+")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def run_json(root: Path, cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, cwd=root, text=True, capture_output=True)
    data: Any = {}
    try:
        data = json.loads(proc.stdout)
    except Exception:
        data = {}
    return {"returncode": proc.returncode, "json": data if isinstance(data, dict) else {}, "stderr": proc.stderr.strip()}


def report(root: Path) -> dict[str, Any]:
    skills = list((root / "skills").glob("*/*/SKILL.md"))
    scripts = list((root / "skills").glob("**/*.py"))
    schemas = set()
    for script in scripts:
        schemas.update(SCHEMA_RE.findall(script.read_text(encoding="utf-8", errors="ignore")))
    prompts = list((root / "prompts").glob("*.md"))
    scenarios = list((root / "examples/scenarios").glob("*/requirement.md"))
    tests = list((root / "tests").glob("test_*.py"))
    cli_text = (root / "scripts/codex_eng.py").read_text(encoding="utf-8") if (root / "scripts/codex_eng.py").exists() else ""
    auto_runner_text = (root / "skills/core/auto-runner/scripts/auto_runner.py").read_text(encoding="utf-8") if (root / "skills/core/auto-runner/scripts/auto_runner.py").exists() else ""
    profiles = run_json(root, ["python3", "scripts/codex_eng.py", "scenarios"])["json"]
    scenario_catalog_count = int(profiles.get("scenario_count") or 0)
    coverage_matrix = profiles.get("coverage_matrix", []) if isinstance(profiles.get("coverage_matrix"), list) else []
    matrix_rows_with_gates = [
        item for item in coverage_matrix if isinstance(item, dict) and item.get("scenario_id") and item.get("required_skills") and item.get("required_gates")
    ]
    documented_text = (root / "docs/scenario-guide.md").read_text(encoding="utf-8") if (root / "docs/scenario-guide.md").exists() else ""
    documented_scenarios = [
        item for item in profiles.get("scenarios", []) if isinstance(item, dict) and str(item.get("id") or "") in documented_text
    ] if isinstance(profiles.get("scenarios"), list) else []
    workflow_profiles = []
    try:
        skill_health = load_module("skill_health_for_benchmark", root / "skills/core/skill-health/scripts/skill_health.py")
        workflow_profiles = skill_health.load_restricted_yaml(root / "config/workflow-profiles.example.yaml").get("profiles", [])
    except Exception:
        workflow_profiles = []
    privacy = run_json(root, ["python3", "scripts/privacy_scan.py", "--root", ".", "--patterns", "config/private-patterns.example.yaml"])
    health = run_json(root, ["python3", "skills/core/skill-health/scripts/skill_health.py", "--root", "."])
    forward = run_json(root, ["python3", "skills/core/forward-test-runner/scripts/forward_test.py", "--root", "."])
    replay = run_json(root, ["python3", "skills/core/delivery-case-capture/scripts/capture_case.py", "--validate-replay-dir", "examples/replay-cases"])
    with tempfile.TemporaryDirectory() as tmp:
        cross_repo = run_json(root, ["python3", "skills/core/cross-repo-planner/scripts/cross_repo_plan.py", "plan", "--example", "--out-dir", tmp])
        cross_repo_validation = run_json(root, ["python3", "skills/core/cross-repo-planner/scripts/cross_repo_plan.py", "validate", "--graph", f"{tmp}/cross_repo_execution_graph.json"])
    cross_repo_cycle_validation = {"decision": ""}
    cross_repo_profile_artifact_step_available = False
    cross_repo_auto_runner_generation_available = False
    try:
        cross_repo_module = load_module("cross_repo_for_benchmark", root / "skills/core/cross-repo-planner/scripts/cross_repo_plan.py")
        graph, _readiness, _release = cross_repo_module.render(
            "REQ-CYCLE",
            {"doc_id": "REQ-CYCLE", "summary": "provider consumer api cycle"},
            {
                "provider": {"name": "provider", "dependencies": ["consumer"]},
                "consumer": {"name": "consumer", "dependencies": ["provider"]},
            },
            {
                "repo_tasks": [
                    {"repo": "provider", "role": "modify", "tasks": ["change api"]},
                    {"repo": "consumer", "role": "modify", "tasks": ["consume api"]},
                ]
            },
        )
        cross_repo_cycle_validation = cross_repo_module.validate_graph(graph)
    except Exception:
        cross_repo_cycle_validation = {"decision": "error"}
    try:
        auto_runner = load_module("auto_runner_for_benchmark", root / "skills/core/auto-runner/scripts/auto_runner.py")
        cross_profile = auto_runner.load_profile_registry().get("cross_repo_api", {})
        cross_repo_profile_artifact_step_available = any(
            isinstance(item, dict) and item.get("name") == "cross_repo_plan"
            for item in cross_profile.get("artifact_steps", [])
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "spec.json").write_text(json.dumps({"doc_id": "REQ-CROSS", "summary": "provider api consumed by frontend"}), encoding="utf-8")
            (out / "delivery_plan.json").write_text(
                json.dumps(
                    {
                        "doc_id": "REQ-CROSS",
                        "repo_tasks": [
                            {"repo": "provider", "role": "modify", "tasks": ["change api"]},
                            {"repo": "frontend", "role": "modify", "tasks": ["consume api"]},
                        ],
                        "cross_repo_order": ["provider", "frontend"],
                    }
                ),
                encoding="utf-8",
            )
            generated: list[str] = []
            skipped: list[str] = []
            steps: list[dict[str, Any]] = []
            auto_runner.run_registry_artifact_steps(cross_profile, out, False, generated, skipped, steps)
            cross_repo_auto_runner_generation_available = (
                (out / "cross_repo_execution_graph.json").exists()
                and (out / "cross_repo_readiness.json").exists()
                and (out / "cross_repo_release_plan.json").exists()
                and all(step.get("passed") for step in steps if not step.get("skipped"))
            )
    except Exception:
        cross_repo_profile_artifact_step_available = False
        cross_repo_auto_runner_generation_available = False
    forward_scenario_results = {}
    forward_cases = forward["json"].get("cases", []) if isinstance(forward["json"].get("cases"), list) else []
    if forward_cases and isinstance(forward_cases[0], dict):
        forward_scenario_results = forward_cases[0].get("scenario_results", {}) if isinstance(forward_cases[0].get("scenario_results"), dict) else {}
    blockers: list[dict[str, Any]] = []
    if privacy["returncode"] != 0:
        blockers.append({"source": "privacy_scan", "message": "privacy scan failed"})
    if health["json"].get("decision") == "block":
        blockers.append({"source": "skill_health", "message": "skill health blocked"})
    if scenario_catalog_count and len(documented_scenarios) != scenario_catalog_count:
        blockers.append({"source": "scenario_catalog", "message": "not all scenario catalog entries are documented"})
    if scenario_catalog_count and len(matrix_rows_with_gates) != scenario_catalog_count:
        blockers.append({"source": "scenario_matrix", "message": "not all scenarios have required skills and gate coverage"})
    if forward["returncode"] != 0:
        blockers.append({"source": "forward_test", "message": "forward test failed"})
    if replay["returncode"] != 0:
        blockers.append({"source": "replay_cases", "message": "replay case validation failed"})
    if cross_repo["returncode"] != 0 or cross_repo_validation["returncode"] != 0:
        blockers.append({"source": "cross_repo_planner", "message": "cross-repo planner example or validation failed"})
    if cross_repo_cycle_validation.get("decision") != "block":
        blockers.append({"source": "cross_repo_planner", "message": "cycle validation did not block"})
    if not cross_repo_profile_artifact_step_available:
        blockers.append({"source": "workflow_profile", "message": "cross_repo_api artifact step is missing"})
    if not cross_repo_auto_runner_generation_available:
        blockers.append({"source": "auto_runner", "message": "cross-repo artifact step did not generate required artifacts"})
    return {
        "schema": SCHEMA,
        "decision": "block" if blockers else "pass",
        "metrics": {
            "skill_count": len(skills),
            "script_count": len(scripts),
            "schema_count": len(schemas),
            "prompt_count": len(prompts),
            "scenario_count": len(scenarios),
            "workflow_profile_count": len(workflow_profiles),
            "setup_command_available": "sub.add_parser(\"setup\")" in cli_text,
            "next_command_available": "sub.add_parser(\"next\")" in cli_text,
            "implement_dry_run_available": "sub.add_parser(\"implement\")" in cli_text and (root / "scripts/implement_dry_run.py").exists(),
            "human_output_available": "--format" in cli_text and "render_auto_human" in cli_text,
            "profile_scoring_available": "profile_selection_confidence" in auto_runner_text and "profile_selection_candidates" in auto_runner_text,
            "scenario_catalog_count": scenario_catalog_count,
            "scenario_matrix_count": len(coverage_matrix),
            "scenario_matrix_gate_coverage_count": len(matrix_rows_with_gates),
            "documented_scenario_count": len(documented_scenarios),
            "forward_tested_scenario_count": sum(1 for value in forward_scenario_results.values() if value),
            "test_file_count": len(tests),
            "privacy_decision": privacy["json"].get("decision"),
            "skill_health_decision": health["json"].get("decision"),
            "skill_expert_level_count": health["json"].get("expert_level_count", 0),
            "skill_advanced_or_better_count": health["json"].get("advanced_or_better_count", 0),
            "skill_expert_readiness": health["json"].get("expert_readiness", ""),
            "skill_content_quality_average": health["json"].get("content_quality_average", 0),
            "skill_content_quality_expert_count": health["json"].get("content_quality_expert_count", 0),
            "forward_test_decision": forward["json"].get("decision"),
            "replay_case_count": replay["json"].get("case_count", 0),
            "replay_scenario_count": replay["json"].get("scenario_count", 0),
            "replay_validation_decision": replay["json"].get("decision"),
            "cross_repo_planner_available": (root / "skills/core/cross-repo-planner/scripts/cross_repo_plan.py").exists(),
            "cross_repo_example_decision": cross_repo["json"].get("decision"),
            "cross_repo_graph_validation_decision": cross_repo_validation["json"].get("decision"),
            "cross_repo_cycle_block_test_available": cross_repo_cycle_validation.get("decision") == "block",
            "cross_repo_profile_artifact_step_available": cross_repo_profile_artifact_step_available,
            "cross_repo_auto_runner_generation_available": cross_repo_auto_runner_generation_available,
        },
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate open-core quality benchmark report")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    output = report(Path(args.root))
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
