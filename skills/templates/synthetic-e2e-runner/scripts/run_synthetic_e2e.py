#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]


def run_step(name: str, args: list[str], allow_fail: bool = False) -> dict[str, Any]:
    proc = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    return {
        "name": name,
        "returncode": proc.returncode,
        "allowed_failure": allow_fail,
        "passed": proc.returncode == 0 or allow_fail,
        "stdout_tail": proc.stdout[-1000:],
        "stderr_tail": proc.stderr[-1000:],
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_release_governance_examples(out_dir: Path) -> None:
    write_json(out_dir / "environment_promotion.json", {"decision": "pass", "blockers": []})
    write_json(out_dir / "uat_acceptance.json", {"decision": "pass", "blockers": []})
    write_json(out_dir / "release_change.json", {"decision": "pass", "blockers": [], "rollback_plan": ["rollback synthetic app"], "post_release_checks": ["check synthetic metric"]})


def run(out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    req = ROOT / "examples/synthetic-e2e-case/requirement.md"
    steps = [
        run_step("ingest", ["python3", "skills/core/requirement-document-ingestor/scripts/ingest_requirement.py", "--input", str(req), "--doc-id", "REQ-SYN-001", "--out-dir", str(out_dir)]),
        run_step("spec", ["python3", "skills/core/spec-governor/scripts/spec_governor.py", "normalize", "--doc-id", "REQ-SYN-001", "--title", "Order export", "--input", str(out_dir / "requirement.normalized.txt"), "--out", str(out_dir / "spec.json")]),
        run_step("technical_design", ["python3", "skills/core/technical-design-governor/scripts/technical_design.py", "--spec", str(out_dir / "spec.json"), "--out", str(out_dir / "technical_design.json")]),
        run_step("architecture_design", ["python3", "skills/core/architecture-design-governor/scripts/architecture_design.py", "--spec", str(out_dir / "spec.json"), "--technical-design", str(out_dir / "technical_design.json"), "--out", str(out_dir / "architecture_design.json")]),
        run_step("test_design", ["python3", "skills/core/test-design-governor/scripts/test_design.py", "render", "--spec", str(out_dir / "spec.json"), "--technical-design", str(out_dir / "technical_design.json"), "--architecture-design", str(out_dir / "architecture_design.json"), "--out", str(out_dir / "test_design.json")]),
        run_step("delivery_plan", ["python3", "skills/templates/delivery-plan-templates/scripts/render_delivery_plan.py", "--doc-id", "REQ-SYN-001", "--technical-design", str(out_dir / "technical_design.json"), "--architecture-design", str(out_dir / "architecture_design.json"), "--out", str(out_dir / "delivery_plan.json")], allow_fail=True),
    ]
    write_release_governance_examples(out_dir)
    steps.append(run_step("inspect", ["python3", "skills/core/delivery-runner/scripts/delivery_runner.py", "inspect", "--artifact-dir", str(out_dir)]))
    return {
        "schema": "codex-synthetic-e2e-run-v1",
        "out_dir": str(out_dir),
        "steps": steps,
        "decision": "pass" if all(step["passed"] for step in steps) else "block",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run synthetic end-to-end workflow")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    result = run(Path(args.out_dir))
    (Path(args.out_dir) / "synthetic_e2e_run.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
