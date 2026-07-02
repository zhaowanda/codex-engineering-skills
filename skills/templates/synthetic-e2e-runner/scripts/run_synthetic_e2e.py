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


def run_json_step(name: str, args: list[str], allow_fail: bool = False) -> dict[str, Any]:
    proc = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    step = {
        "name": name,
        "returncode": proc.returncode,
        "allowed_failure": allow_fail,
        "passed": proc.returncode == 0 or allow_fail,
        "stdout_tail": proc.stdout[-1000:],
        "stderr_tail": proc.stderr[-1000:],
    }
    try:
        parsed = json.loads(proc.stdout)
    except Exception:
        parsed = {}
    step["schema"] = parsed.get("schema", "")
    step["decision"] = parsed.get("decision", "")
    return step


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_release_governance_examples(out_dir: Path) -> None:
    write_json(out_dir / "environment_promotion.json", {"decision": "pass", "blockers": []})
    write_json(out_dir / "uat_acceptance.json", {"decision": "pass", "blockers": []})
    write_json(out_dir / "release_change.json", {"decision": "pass", "blockers": [], "rollback_plan": ["rollback synthetic app"], "post_release_checks": ["check synthetic metric"]})


def write_frontend_happy_evidence(out_dir: Path) -> None:
    write_json(
        out_dir / "frontend_acceptance.json",
        {
            "schema": "codex-" + "frontend-acceptance-v1",
            "decision": "pass",
            "pass": True,
            "target_url": "http://localhost/synthetic",
            "page_type": "custom",
            "page_load": {"loaded": True},
            "dom_evidence": [{"selector": "#app", "result": "visible"}],
            "console_errors": [],
            "failed_requests": [],
        },
    )
    write_json(
        out_dir / "test_execution_evidence.json",
        {"executed_cases": [{"name": "synthetic frontend", "status": "passed"}], "failed_cases": [], "untested_blockers": []},
    )


def write_release_happy_evidence(out_dir: Path) -> None:
    write_json(out_dir / "delivery_plan.json", {"decision": "pass", "rollback_order": ["rollback synthetic"], "post_release_checks": ["check synthetic metric"]})
    write_json(out_dir / "design_architecture_review.json", {"decision": "pass", "blockers": [], "warnings": []})
    write_json(out_dir / "implementation_completion_gate.json", {"decision": "pass", "blockers": []})
    write_json(out_dir / "write_guard_audit.json", {"decision": "ready", "blockers": []})
    write_json(out_dir / "code_review_gate.json", {"decision": "approve", "active_blockers": [], "active_concerns": []})
    write_json(out_dir / "test_evidence_gate.json", {"decision": "pass", "blockers": [], "warnings": []})
    write_json(out_dir / "ci_execution_evidence.json", {"failed_commands": [], "unknown_commands": [], "executed_commands": [{"command": "pytest", "status": "passed"}]})
    write_json(out_dir / "environment_promotion.json", {"decision": "pass", "blockers": []})
    write_json(out_dir / "uat_acceptance.json", {"decision": "pass", "blockers": []})
    write_json(out_dir / "release_change.json", {"decision": "pass", "blockers": [], "rollback_plan": ["rollback synthetic"], "post_release_checks": ["check synthetic metric"]})


def write_docs_manifest(out_dir: Path, doc_id: str) -> Path:
    docs_root = out_dir / "delivery-docs"
    write_json(docs_root / "indexes" / f"{doc_id}.manifest.json", {"schema": "codex-" + "docs-governor-v1", "doc_id": doc_id})
    if not (docs_root / ".git").exists():
        subprocess.run(["git", "init"], cwd=docs_root, text=True, capture_output=True)
    return docs_root


def run(out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    blocked_dir = out_dir / "blocked_case"
    happy_dir = out_dir / "happy_path_case"
    frontend_dir = out_dir / "frontend_happy_path"
    data_dir = out_dir / "data_migration_blocked_path"
    release_blocked_dir = out_dir / "release_readiness_blocked_path"
    release_happy_dir = out_dir / "release_readiness_happy_path"
    blocked_dir.mkdir(parents=True, exist_ok=True)
    happy_dir.mkdir(parents=True, exist_ok=True)
    frontend_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    release_blocked_dir.mkdir(parents=True, exist_ok=True)
    release_happy_dir.mkdir(parents=True, exist_ok=True)
    req = ROOT / "examples/synthetic-e2e-case/requirement.md"
    happy_docs = write_docs_manifest(happy_dir, "REQ-SYN-HAPPY")
    frontend_docs = write_docs_manifest(frontend_dir, "REQ-SYN-FE")
    data_docs = write_docs_manifest(data_dir, "REQ-SYN-DATA")
    steps = [
        run_step("blocked_ingest", ["python3", "skills/core/requirement-document-ingestor/scripts/ingest_requirement.py", "--input", str(req), "--doc-id", "REQ-SYN-BLOCKED", "--out-dir", str(blocked_dir)]),
        run_step("blocked_spec", ["python3", "skills/core/spec-governor/scripts/spec_governor.py", "normalize", "--doc-id", "REQ-SYN-BLOCKED", "--title", "Order export", "--input", str(blocked_dir / "requirement.normalized.txt"), "--out", str(blocked_dir / "spec.json")]),
        run_step("blocked_technical_design", ["python3", "skills/core/technical-design-governor/scripts/technical_design.py", "--spec", str(blocked_dir / "spec.json"), "--out", str(blocked_dir / "technical_design.json")]),
        run_step("blocked_architecture_design", ["python3", "skills/core/architecture-design-governor/scripts/architecture_design.py", "--spec", str(blocked_dir / "spec.json"), "--technical-design", str(blocked_dir / "technical_design.json"), "--out", str(blocked_dir / "architecture_design.json")]),
        run_step("blocked_test_design", ["python3", "skills/core/test-design-governor/scripts/test_design.py", "render", "--spec", str(blocked_dir / "spec.json"), "--technical-design", str(blocked_dir / "technical_design.json"), "--architecture-design", str(blocked_dir / "architecture_design.json"), "--out", str(blocked_dir / "test_design.json")]),
        run_step("blocked_design_review", ["python3", "skills/core/design-architecture-reviewer/scripts/design_arch_review.py", "review", "--technical-design", str(blocked_dir / "technical_design.json"), "--architecture-design", str(blocked_dir / "architecture_design.json"), "--out", str(blocked_dir / "design_architecture_review.json")], allow_fail=True),
        run_step("blocked_delivery_plan", ["python3", "skills/templates/delivery-plan-templates/scripts/render_delivery_plan.py", "--doc-id", "REQ-SYN-BLOCKED", "--technical-design", str(blocked_dir / "technical_design.json"), "--architecture-design", str(blocked_dir / "architecture_design.json"), "--out", str(blocked_dir / "delivery_plan.json")], allow_fail=True),
        run_step("blocked_delivery_plan_review", ["python3", "skills/core/delivery-plan-reviewer/scripts/delivery_plan_review.py", "review", "--file", str(blocked_dir / "delivery_plan.json"), "--out", str(blocked_dir / "delivery_plan_review.json")], allow_fail=True),
    ]
    write_release_governance_examples(blocked_dir)
    blocked_inspect = run_json_step("blocked_inspect", ["python3", "skills/core/delivery-runner/scripts/delivery_runner.py", "inspect", "--artifact-dir", str(blocked_dir)], allow_fail=True)
    steps.append(blocked_inspect)
    happy_step = run_json_step(
        "happy_path_auto",
        [
            "python3",
            "scripts/codex_eng.py",
            "auto",
            "--input",
            str(req),
            "--doc-id",
            "REQ-SYN-HAPPY",
            "--repo",
            "examples/synthetic-repos/basic-web-service",
            "--project",
            "basic-web-service",
            "--out",
            str(happy_dir),
            "--docs-root",
            str(happy_docs),
        ],
    )
    steps.append(happy_step)
    frontend_step = run_json_step(
        "frontend_profile_auto",
        ["python3", "scripts/codex_eng.py", "auto", "--input", str(req), "--doc-id", "REQ-SYN-FE", "--profile", "frontend_change", "--out", str(frontend_dir), "--docs-root", str(frontend_docs)],
        allow_fail=True,
    )
    steps.append(frontend_step)
    write_frontend_happy_evidence(frontend_dir)
    frontend_gate = run_json_step(
        "frontend_happy_test_gate",
        ["python3", "skills/core/test-evidence-gate/scripts/test_evidence_gate.py", "--artifact-dir", str(frontend_dir), "--require-frontend", "--out", str(frontend_dir / "test_evidence_gate.json")],
    )
    steps.append(frontend_gate)
    data_step = run_json_step(
        "data_migration_blocked_auto",
        ["python3", "scripts/codex_eng.py", "auto", "--input", str(req), "--doc-id", "REQ-SYN-DATA", "--profile", "data_migration", "--out", str(data_dir), "--docs-root", str(data_docs)],
        allow_fail=True,
    )
    steps.append(data_step)
    release_blocked_step = run_json_step(
        "release_blocked_binder",
        ["python3", "skills/core/release-evidence-binder/scripts/bind_release.py", "--artifact-dir", str(release_blocked_dir), "--out", str(release_blocked_dir / "release_gate.json")],
        allow_fail=True,
    )
    steps.append(release_blocked_step)
    write_release_happy_evidence(release_happy_dir)
    release_happy_step = run_json_step(
        "release_happy_binder",
        ["python3", "skills/core/release-evidence-binder/scripts/bind_release.py", "--artifact-dir", str(release_happy_dir), "--out", str(release_happy_dir / "release_gate.json")],
    )
    steps.append(release_happy_step)
    happy_summary = json.loads((happy_dir / "auto_run_summary.json").read_text(encoding="utf-8")) if (happy_dir / "auto_run_summary.json").exists() else {}
    data_summary = json.loads((data_dir / "auto_run_summary.json").read_text(encoding="utf-8")) if (data_dir / "auto_run_summary.json").exists() else {}
    blocked_case = {
        "case": "blocked_case",
        "passed": blocked_inspect.get("returncode") != 0 and blocked_inspect.get("schema") == ("codex-" + "delivery-runner-status-v1"),
        "decision": blocked_inspect.get("decision", ""),
        "reason": "delivery-runner blocks incomplete synthetic artifacts before implementation",
    }
    happy_case = {
        "case": "happy_path_case",
        "passed": (
            happy_step.get("returncode") == 0
            and happy_summary.get("decision") == "pass"
            and happy_summary.get("docs_quality", {}).get("decision") == "pass"
            and happy_summary.get("can_implement") is False
            and any(gap.get("artifact") in {"frontend_acceptance.json", "test_evidence_gate.json", "release_gate.json"} for gap in happy_summary.get("profile_gate_gaps", []))
        ),
        "decision": happy_summary.get("decision", ""),
        "reason": "project-understanding-backed synthetic repo passes design/docs gates while merged profile evidence still blocks implementation",
    }
    frontend_case = {
        "case": "frontend_happy_path",
        "passed": frontend_gate.get("returncode") == 0 and frontend_gate.get("decision") == "pass",
        "decision": frontend_gate.get("decision", ""),
        "reason": "frontend evidence and test evidence gate can pass with synthetic browser proof",
    }
    data_case = {
        "case": "data_migration_blocked_path",
        "passed": (
            data_summary.get("decision") in {"pass", "block"}
            and data_summary.get("can_implement") is False
            and any(gap.get("artifact") == "release_gate.json" for gap in data_summary.get("profile_gate_gaps", []))
            and any(gap.get("artifact") in {"docs_quality.json", "delivery_plan_review.json"} for gap in data_summary.get("profile_gate_gaps", []))
        ),
        "decision": data_summary.get("decision", ""),
        "reason": "data migration profile blocks until release/security/performance evidence is real",
    }
    release_blocked_case = {
        "case": "release_readiness_blocked_path",
        "passed": release_blocked_step.get("returncode") != 0 and release_blocked_step.get("decision") == "no_go",
        "decision": release_blocked_step.get("decision", ""),
        "reason": "release binder blocks missing release evidence",
    }
    release_happy_case = {
        "case": "release_readiness_happy_path",
        "passed": release_happy_step.get("returncode") == 0 and release_happy_step.get("decision") == "go",
        "decision": release_happy_step.get("decision", ""),
        "reason": "release binder approves complete clean synthetic evidence",
    }
    cases = [blocked_case, happy_case, frontend_case, data_case, release_blocked_case, release_happy_case]
    return {
        "schema": "codex-synthetic-e2e-run-v1",
        "out_dir": str(out_dir),
        "cases": cases,
        "steps": steps,
        "decision": "pass" if all(step["passed"] for step in steps) and all(case["passed"] for case in cases) else "block",
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
