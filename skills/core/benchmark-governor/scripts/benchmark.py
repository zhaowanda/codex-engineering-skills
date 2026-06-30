#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
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
    if forward["returncode"] != 0:
        blockers.append({"source": "forward_test", "message": "forward test failed"})
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
            "documented_scenario_count": len(documented_scenarios),
            "forward_tested_scenario_count": sum(1 for value in forward_scenario_results.values() if value),
            "test_file_count": len(tests),
            "privacy_decision": privacy["json"].get("decision"),
            "skill_health_decision": health["json"].get("decision"),
            "forward_test_decision": forward["json"].get("decision"),
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
