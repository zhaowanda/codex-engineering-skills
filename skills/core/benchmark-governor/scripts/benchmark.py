#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any


SCHEMA = "codex-benchmark-report-v1"
SCHEMA_RE = re.compile(r"codex-[a-z0-9-]+-v\d+")


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
    privacy = run_json(root, ["python3", "scripts/privacy_scan.py", "--root", ".", "--patterns", "config/private-patterns.example.yaml"])
    health = run_json(root, ["python3", "skills/core/skill-health/scripts/skill_health.py", "--root", "."])
    blockers: list[dict[str, Any]] = []
    if privacy["returncode"] != 0:
        blockers.append({"source": "privacy_scan", "message": "privacy scan failed"})
    if health["json"].get("decision") == "block":
        blockers.append({"source": "skill_health", "message": "skill health blocked"})
    return {
        "schema": SCHEMA,
        "decision": "block" if blockers else "pass",
        "metrics": {
            "skill_count": len(skills),
            "script_count": len(scripts),
            "schema_count": len(schemas),
            "prompt_count": len(prompts),
            "scenario_count": len(scenarios),
            "test_file_count": len(tests),
            "privacy_decision": privacy["json"].get("decision"),
            "skill_health_decision": health["json"].get("decision"),
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
