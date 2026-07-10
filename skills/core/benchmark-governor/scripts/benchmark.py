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


def requirement_understanding_strict(root: Path) -> bool:
    try:
        spec_governor = load_module("spec_governor_for_benchmark", root / "skills/core/spec-governor/scripts/spec_governor.py")
        ambiguous = spec_governor.normalize("REQ-BENCH-AMB", "续费优化", "优化续费流程，状态更新正确，功能正常。")
        clear = spec_governor.normalize(
            "REQ-BENCH-CLEAR",
            "续费重新试算",
            "\n".join(
                [
                    "业务目的: 减少运营手工核对续费状态的时间。",
                    "流程: 运营在续费列表点击重新试算按钮，系统调用续费试算接口并刷新当前设备的试算结果。",
                    "入口: 续费列表的重新试算按钮。",
                    "Req: 运营可以对单个设备重新触发续费试算。",
                    "Rule: 只有有续费管理权限的运营角色可以触发。",
                    "AC: 给定有权限运营在续费列表点击重新试算按钮，接口返回成功后页面展示新的试算金额和试算时间。",
                    "AC: 无权限角色看不到重新试算按钮且直接调用接口返回无权限。",
                ]
            ),
        )
        no_goal = spec_governor.normalize(
            "REQ-BENCH-NO-GOAL",
            "订单导出",
            "\n".join(
                [
                    "入口: 订单列表导出按钮。",
                    "流程: 运营点击订单列表导出按钮，系统调用导出接口并生成 Excel 文件。",
                    "Req: 运营可以导出订单列表。",
                    "AC: 给定运营点击导出按钮，系统生成包含订单号和状态的 Excel 文件。",
                ]
            ),
        )
        return (
            ambiguous.get("design_allowed") is False
            and ambiguous.get("requirements_understanding", {}).get("decision") == "needs_clarification"
            and clear.get("design_allowed") is True
            and clear.get("requirements_understanding", {}).get("level") == "expert_ready"
            and no_goal.get("design_allowed") is False
            and no_goal.get("requirements_understanding", {}).get("level") == "clarification_required"
            and spec_governor.validate_spec(clear).get("decision") == "pass"
        )
    except Exception:
        return False


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
    quality_gates = health["json"].get("integrated_quality_gates", {}) if isinstance(health["json"].get("integrated_quality_gates"), dict) else {}
    artifact_schema_gate = quality_gates.get("artifact_schema_inventory", {}) if isinstance(quality_gates.get("artifact_schema_inventory"), dict) else {}
    design_template_gate = quality_gates.get("design_template_regression", {}) if isinstance(quality_gates.get("design_template_regression"), dict) else {}
    requirement_understanding_gate = requirement_understanding_strict(root)
    blockers: list[dict[str, Any]] = []
    if privacy["returncode"] != 0:
        blockers.append({"source": "privacy_scan", "message": "privacy scan failed"})
    if health["json"].get("decision") == "block":
        blockers.append({"source": "skill_health", "message": "skill health blocked"})
    if artifact_schema_gate.get("decision") != "pass":
        blockers.append({"source": "artifact_schema_inventory", "message": "artifact schema inventory must pass for expert readiness"})
    if design_template_gate.get("decision") != "pass":
        blockers.append({"source": "design_template_regression", "message": "design template regression must pass for expert readiness"})
    if not requirement_understanding_gate:
        blockers.append({"source": "requirement_understanding", "message": "ambiguous requirements must block and clear business-flow requirements must pass"})
    if scenario_catalog_count and len(documented_scenarios) != scenario_catalog_count:
        blockers.append({"source": "scenario_catalog", "message": "not all scenario catalog entries are documented"})
    if scenario_catalog_count and len(matrix_rows_with_gates) != scenario_catalog_count:
        blockers.append({"source": "scenario_matrix", "message": "not all scenarios have required skills and gate coverage"})
    if forward["returncode"] != 0:
        blockers.append({"source": "forward_test", "message": "forward test failed"})
    if replay["returncode"] != 0:
        blockers.append({"source": "replay_cases", "message": "replay case validation failed"})
    if int(replay["json"].get("complex_case_count") or 0) < 3:
        blockers.append({"source": "replay_cases", "message": "at least three complex replay cases are required"})
    if int(replay["json"].get("scenario_family_coverage_count") or 0) < 5:
        blockers.append({"source": "replay_cases", "message": "replay scenarios must cover at least five behavior families"})
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
            "artifact_schema_inventory_decision": artifact_schema_gate.get("decision"),
            "artifact_schema_warning_count": artifact_schema_gate.get("warning_count", 0),
            "design_template_regression_decision": design_template_gate.get("decision"),
            "requirement_understanding_strict": requirement_understanding_gate,
            "expert_readiness_strict": (
                health["json"].get("decision") == "pass"
                and artifact_schema_gate.get("decision") == "pass"
                and design_template_gate.get("decision") == "pass"
                and requirement_understanding_gate
                and privacy["json"].get("decision") == "pass"
                and forward["json"].get("decision") == "pass"
            ),
            "forward_test_decision": forward["json"].get("decision"),
            "replay_case_count": replay["json"].get("case_count", 0),
            "replay_scenario_count": replay["json"].get("scenario_count", 0),
            "replay_complex_case_count": replay["json"].get("complex_case_count", 0),
            "replay_scenario_family_coverage_count": replay["json"].get("scenario_family_coverage_count", 0),
            "replay_behavior_coverage_score": replay["json"].get("behavior_coverage_score", 0),
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
