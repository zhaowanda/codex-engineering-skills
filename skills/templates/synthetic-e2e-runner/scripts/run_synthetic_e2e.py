#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]


def load_delivery_runner() -> Any:
    path = ROOT / "skills/core/delivery-runner/scripts/delivery_runner.py"
    spec = importlib.util.spec_from_file_location("synthetic_delivery_runner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


DELIVERY_RUNNER = load_delivery_runner()


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


def resolve_required_questions(out_dir: Path) -> None:
    path = out_dir / "open_questions.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for question in data.get("questions", []):
        if isinstance(question, dict) and question.get("required"):
            question["status"] = "closed"
            question["answer"] = "Confirmed by the synthetic product owner."
    data["decision"] = "pass"
    write_json(path, data)


def canonical_digest(data: dict[str, Any]) -> str:
    return DELIVERY_RUNNER.CONTRACT.canonical_digest(data)


def bind_workflow_lineage(out_dir: Path) -> None:
    for stage in DELIVERY_RUNNER.load_stage_registry():
        path = out_dir / str(stage["artifact"])
        if not path.exists():
            continue
        inputs = []
        for artifact in stage.get("input_artifacts", []):
            source = out_dir / str(artifact)
            if source.exists():
                inputs.append(source)
        DELIVERY_RUNNER.CONTRACT.bind_lineage(
            path,
            "synthetic-e2e",
            inputs,
            command=["synthetic-e2e", str(stage["name"])],
            workspace=ROOT,
        )


def write_preimplementation_happy_evidence(out_dir: Path) -> None:
    spec = json.loads((out_dir / "spec.json").read_text(encoding="utf-8"))
    questions = json.loads((out_dir / "open_questions.json").read_text(encoding="utf-8"))
    questions["spec_digest"] = canonical_digest(spec)
    questions["decision"] = "pass"
    write_json(out_dir / "open_questions.json", questions)
    defaults = {
        "domain_model_design.json": {"schema": "codex-domain-model-design-v1", "decision": "pass", "blockers": []},
        "architecture_framing.json": {"schema": "codex-architecture-framing-v1", "decision": "pass", "blockers": [], "system_boundary": {}, "repo_responsibilities": []},
        "test_design.json": {"schema": "codex-test-design-v1", "decision": "pass", "test_cases": [], "evidence_required": []},
        "test_data_plan.json": {"schema": "codex-test-data-plan-v1", "decision": "pass", "datasets": [], "case_data_matrix": []},
        "traceability_matrix.json": {"schema": "codex-traceability-matrix-v1", "decision": "pass", "blockers": []},
        "docs_quality.json": {"schema": "codex-docs-quality-aggregate-v1", "decision": "pass", "blockers": []},
    }
    for artifact, fallback in defaults.items():
        current = json.loads((out_dir / artifact).read_text(encoding="utf-8")) if (out_dir / artifact).exists() else fallback
        current.update({key: value for key, value in fallback.items() if key not in current or key in {"decision", "blockers"}})
        write_json(out_dir / artifact, current)
    technical = json.loads((out_dir / "technical_design.json").read_text(encoding="utf-8"))
    architecture = json.loads((out_dir / "architecture_design.json").read_text(encoding="utf-8"))
    technical.update({"decision": "pass", "blockers": []})
    architecture.update({"decision": "pass", "blockers": []})
    write_json(out_dir / "technical_design.json", technical)
    write_json(out_dir / "architecture_design.json", architecture)
    review_inputs = {
        "technical_design.json": technical,
        "architecture_design.json": architecture,
    }
    for artifact in [
        "ui_ue_design.json",
        "ui_ue_review.json",
        "api_contract_design.json",
        "data_model_design.json",
        "observability_design.json",
        "configuration_readiness.json",
        "data_security_review.json",
        "performance_review.json",
        "cross_repo_readiness.json",
    ]:
        path = out_dir / artifact
        if path.exists():
            review_inputs[artifact] = json.loads(path.read_text(encoding="utf-8"))
    write_json(out_dir / "design_architecture_review.json", {
        "schema": "codex-design-architecture-review-v1",
        "decision": "pass",
        "blockers": [],
        "score": 100,
        "readiness_gate": {"implementation_allowed": True},
        "input_digests": {name: canonical_digest(data) for name, data in review_inputs.items()},
    })
    plan = json.loads((out_dir / "delivery_plan.json").read_text(encoding="utf-8")) if (out_dir / "delivery_plan.json").exists() else {}
    plan.update({"schema": "codex-delivery-plan-v1", "decision": "ready", "doc_id": "REQ-SYN-HAPPY", "repo_tasks": plan.get("repo_tasks", []), "validation_plan": plan.get("validation_plan", {}), "release_plan": plan.get("release_plan", {}), "rollback_plan": plan.get("rollback_plan", {}), "open_gates": []})
    write_json(out_dir / "delivery_plan.json", plan)
    write_json(out_dir / "delivery_plan_review.json", {"schema": "codex-delivery-plan-review-v1", "decision": "pass", "blockers": [], "readiness_gate": {"implementation_allowed": True}})
    write_json(out_dir / "git_worktree_evidence.json", {"schema": "codex-git-baseline-evidence-v1", "decision": "ready", "fetched": True, "base_updated": True, "branch": "feature/REQ-SYN-HAPPY"})
    write_json(out_dir / "edit_permit.json", {"schema": "codex-edit-permit-v1", "decision": "ready", "doc_id": "REQ-SYN-HAPPY", "branch": "feature/REQ-SYN-HAPPY", "allowed_files": ["app/main.py"]})
    write_json(out_dir / "write_guard_snapshot.json", {"schema": "codex-write-guard-snapshot-v1", "decision": "ready", "doc_id": "REQ-SYN-HAPPY", "branch": "feature/REQ-SYN-HAPPY", "permit_id": "EDIT-SYN-HAPPY"})
    bind_workflow_lineage(out_dir)


def write_release_governance_examples(out_dir: Path) -> None:
    write_json(out_dir / "environment_promotion.json", {"decision": "pass", "blockers": [], "environments": [{"name": "pre", "entry_criteria": ["candidate deployed"], "exit_criteria": ["smoke passed"], "validation_evidence": ["pre smoke"], "approver": "release-owner", "rollback_ready": True}, {"name": "prod", "entry_criteria": ["pre passed"], "exit_criteria": ["metrics healthy"], "validation_evidence": ["prod smoke"], "approver": "release-owner", "rollback_ready": True}]})
    write_json(out_dir / "uat_acceptance.json", {"decision": "pass", "blockers": []})
    write_json(out_dir / "release_change.json", {"decision": "pass", "blockers": [], "release_window": {"start": "2026-07-03T10:00:00+08:00", "end": "2026-07-03T11:00:00+08:00", "timezone": "Asia/Shanghai"}, "approvers": ["release-owner"], "rollback_plan": ["rollback synthetic app"], "rollback_owner": "release-owner", "post_release_checks": ["check synthetic metric"]})


def write_frontend_happy_evidence(out_dir: Path) -> None:
    test_design = {}
    if (out_dir / "test_design.json").exists():
        test_design = json.loads((out_dir / "test_design.json").read_text(encoding="utf-8"))
    cases = [item for item in test_design.get("test_cases", []) if isinstance(item, dict)]
    if cases and not (out_dir / "test_data_plan.json").exists():
        datasets = []
        matrix = []
        for case in cases:
            case_id = str(case.get("id") or "TC")
            refs = [str(ref) for ref in case.get("test_data_refs", [])] or [f"TD-{case_id}"]
            for ref in refs:
                datasets.append({"id": ref, "case_ids": [case_id], "data_classification": "synthetic", "setup_method": "fixture_or_factory", "cleanup": [{"method": "delete synthetic fixture data"}]})
            matrix.append({"case_id": case_id, "dataset_ids": refs})
        write_json(out_dir / "test_data_plan.json", {"schema": "codex-test-data-plan-v1", "decision": "pass", "datasets": datasets, "case_data_matrix": matrix, "blockers": [], "warnings": []})
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
    executed_cases = [
        {
            "id": str(case.get("id") or "TC"),
            "name": str(case.get("title") or "synthetic frontend"),
            "status": "passed",
            "dataset_ids": [str(ref) for ref in case.get("test_data_refs", [])],
        }
        for case in cases
    ] or [{"name": "synthetic frontend", "status": "passed"}]
    write_json(
        out_dir / "test_execution_evidence.json",
        {"executed_cases": executed_cases, "failed_cases": [], "untested_blockers": []},
    )


def write_release_happy_evidence(out_dir: Path) -> None:
    write_json(out_dir / "delivery_plan.json", {"decision": "pass", "rollback_order": ["rollback synthetic"], "post_release_checks": ["check synthetic metric"]})
    write_json(out_dir / "design_architecture_review.json", {"decision": "pass", "blockers": [], "warnings": []})
    write_json(out_dir / "implementation_completion_gate.json", {"schema": "codex-implementation-completion-v1", "decision": "pass", "blockers": [], "changed_files": ["synthetic.py"], "evidence_followups": []})
    write_json(out_dir / "post_change_implementation_report.json", {"schema": "codex-post-change-implementation-report-v1", "decision": "pass", "blockers": [], "changed_files": ["synthetic.py"]})
    write_json(out_dir / "write_guard_audit.json", {"schema": "codex-write-guard-audit-v1", "decision": "ready", "blockers": [], "changed_files": ["synthetic.py"], "snapshot": {"artifact": "write_guard_snapshot.json", "verified": True}})
    write_json(out_dir / "diff_impact.json", {"schema": "codex-diff-impact-v1", "decision": "pass", "impact_areas": ["code"], "changed_files": ["synthetic.py"], "blockers": []})
    write_json(out_dir / "post_implementation_traceability_matrix.json", {"schema": "codex-traceability-matrix-v1", "decision": "pass", "blockers": [], "coverage": {"acceptance_covered": True}, "acceptance_trace": [{"acceptance": "synthetic behavior", "status": "covered"}], "task_trace": [{"task": "synthetic.py", "status": "implemented"}]})
    write_json(out_dir / "change_risk.json", {"schema": "codex-change-risk-v1", "decision": "pass", "risk_level": "low", "blockers": []})
    write_json(out_dir / "evidence_gap_summary.json", {"schema": "codex-evidence-gap-summary-v1", "decision": "pass", "required_evidence": ["tests"], "found_evidence": ["tests:test_execution_evidence.json"], "command_logs": [{"command": "pytest", "status": "passed"}], "missing_evidence": [], "blockers": []})
    write_json(out_dir / "code_design_quality.json", {"schema": "codex-code-design-quality-review-v1", "decision": "pass", "changed_files": ["synthetic.py"], "findings": [], "blockers": []})
    write_json(out_dir / "code_review_gate.json", {"schema": "codex-code-review-gate-v1", "decision": "approve", "active_blockers": [], "active_concerns": [], "missing_evidence": [], "evidence_summary": {"reviewed_files": ["synthetic.py"], "test_gate": "pass"}})
    write_json(out_dir / "test_evidence_gate.json", {"schema": "codex-test-evidence-gate-v1", "decision": "pass", "blockers": [], "warnings": [], "evidence_summary": {"executed_cases": 1, "ci_commands": 1}})
    write_json(out_dir / "ci_execution_evidence.json", {"failed_commands": [], "unknown_commands": [], "executed_commands": [{"command": "pytest", "status": "passed"}]})
    write_json(out_dir / "environment_promotion.json", {"schema": "codex-environment-promotion-v1", "decision": "pass", "blockers": [], "environments": [{"name": "pre", "entry_criteria": ["candidate deployed"], "exit_criteria": ["smoke passed"], "validation_evidence": ["pre smoke"], "approver": "release-owner", "rollback_ready": True}, {"name": "prod", "entry_criteria": ["pre passed"], "exit_criteria": ["metrics healthy"], "validation_evidence": ["prod smoke"], "approver": "release-owner", "rollback_ready": True}]})
    write_json(out_dir / "uat_acceptance.json", {"schema": "codex-uat-acceptance-v1", "decision": "pass", "blockers": [], "scope": ["synthetic behavior"], "acceptors": ["synthetic-owner"], "cases": [{"name": "synthetic UAT", "status": "passed"}], "signoff": {"accepted": True, "by": "synthetic-owner", "at": "2026-07-03T10:30:00+08:00"}})
    write_json(out_dir / "release_change.json", {"schema": "codex-release-change-v1", "decision": "pass", "blockers": [], "release_window": {"start": "2026-07-03T10:00:00+08:00", "end": "2026-07-03T11:00:00+08:00", "timezone": "Asia/Shanghai"}, "approvers": ["release-owner"], "rollback_plan": ["rollback synthetic"], "rollback_owner": "release-owner", "post_release_checks": ["check synthetic metric"]})
    bind_workflow_lineage(out_dir)


def write_release_followup_chain_evidence(out_dir: Path) -> None:
    write_release_happy_evidence(out_dir)
    write_json(out_dir / "code_review.json", {"decision": "pass", "findings": []})
    write_json(out_dir / "code_design_quality.json", {"decision": "pass", "findings": []})
    write_json(out_dir / "data_security_review.json", {"decision": "pass", "findings": []})
    write_json(out_dir / "performance_diff_review.json", {"decision": "pass", "risk_level": "low", "evidence_plan": []})
    write_json(
        out_dir / "implementation_completion_gate.json",
        {
            "decision": "pass",
            "blockers": [],
            "evidence_followups": [
                {"surface": "frontend_acceptance", "required_by": "frontend-acceptance-runner", "evidence": ["browser evidence"]},
                {"surface": "transaction_idempotency", "required_by": "test-evidence-gate", "evidence": ["rollback evidence"]},
            ],
        },
    )
    write_json(out_dir / "frontend_acceptance.json", {"decision": "pass", "pass": True, "blockers": []})
    write_json(
        out_dir / "test_execution_evidence.json",
        {
            "executed_cases": [
                {"id": "TC-FOLLOWUP-1", "status": "passed", "name": "frontend follow-up acceptance"},
                {"id": "TC-FOLLOWUP-2", "status": "passed", "name": "transaction idempotency proof"},
            ],
            "failed_cases": [],
            "untested_blockers": [],
        },
    )


def write_docs_manifest(out_dir: Path, doc_id: str) -> Path:
    docs_root = out_dir / "delivery-docs"
    write_json(docs_root / "indexes" / f"{doc_id}.manifest.json", {"schema": "codex-" + "docs-governor-v1", "doc_id": doc_id})
    git_check = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=docs_root, text=True, capture_output=True)
    if git_check.returncode != 0:
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
    release_followup_dir = out_dir / "release_followup_chain_path"
    blocked_dir.mkdir(parents=True, exist_ok=True)
    happy_dir.mkdir(parents=True, exist_ok=True)
    frontend_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    release_blocked_dir.mkdir(parents=True, exist_ok=True)
    release_happy_dir.mkdir(parents=True, exist_ok=True)
    release_followup_dir.mkdir(parents=True, exist_ok=True)
    req = ROOT / "examples/synthetic-e2e-case/requirement.md"
    happy_req = happy_dir / "requirement.md"
    happy_req.write_text(
        "Goal: reduce buyer support tickets caused by an unclear completed-order confirmation message by 20 percent.\n"
        "Metric: completed-order confirmation support tickets decrease by 20 percent.\n"
        "Flow: buyer submits an order, the order completes, and the confirmation message is shown.\n"
        "Route: /orders/complete.\n"
        "Entrypoint: buyer submits the checkout form.\n"
        "Requirement: replace the confirmation phrase with Order received.\n"
        "Rule: keep existing order processing unchanged.\n"
        "Acceptance: a completed order shows Order received.\n",
        encoding="utf-8",
    )
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
            str(happy_req),
            "--doc-id",
            "REQ-SYN-HAPPY",
            "--repo",
            "examples/synthetic-repos/basic-web-service",
            "--project",
            "basic-web-service",
            "--profile",
            "frontend_change",
            "--out",
            str(happy_dir),
            "--docs-root",
            str(happy_docs),
        ],
    )
    steps.append(happy_step)
    resolve_required_questions(happy_dir)
    happy_resolved_step = run_json_step(
        "happy_path_resolved_auto",
        [
            "python3",
            "scripts/codex_eng.py",
            "auto",
            "--input",
            str(happy_req),
            "--doc-id",
            "REQ-SYN-HAPPY",
            "--repo",
            "examples/synthetic-repos/basic-web-service",
            "--project",
            "basic-web-service",
            "--profile",
            "frontend_change",
            "--out",
            str(happy_dir),
            "--docs-root",
            str(happy_docs),
            "--force",
        ],
    )
    steps.append(happy_resolved_step)
    write_preimplementation_happy_evidence(happy_dir)
    happy_ready_step = run_json_step(
        "happy_path_delivery_ready",
        [
            "python3",
            "skills/core/delivery-runner/scripts/delivery_runner.py",
            "inspect",
            "--artifact-dir",
            str(happy_dir),
            "--profile",
            "small_feature",
            "--out",
            str(happy_dir / "implementation_ready_status.json"),
        ],
    )
    steps.append(happy_ready_step)
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
    bind_workflow_lineage(release_happy_dir)
    release_ready_step = run_json_step(
        "release_happy_delivery_ready",
        [
            "python3",
            "skills/core/delivery-runner/scripts/delivery_runner.py",
            "inspect",
            "--artifact-dir",
            str(release_happy_dir),
            "--profile",
            "release_readiness",
            "--out",
            str(release_happy_dir / "release_ready_status.json"),
        ],
    )
    steps.append(release_ready_step)
    write_release_followup_chain_evidence(release_followup_dir)
    release_followup_collect = run_json_step(
        "release_followup_collect",
        ["python3", "skills/core/evidence-auto-collector/scripts/evidence_collect.py", "--diff-impact", str(release_followup_dir / "diff_impact.json"), "--artifact-dir", str(release_followup_dir), "--out", str(release_followup_dir / "evidence_gap_summary.json")],
    )
    steps.append(release_followup_collect)
    release_followup_review = run_json_step(
        "release_followup_review_gate",
        ["python3", "skills/core/code-review-gate/scripts/review_gate.py", "--artifact-dir", str(release_followup_dir), "--out", str(release_followup_dir / "code_review_gate.json")],
    )
    steps.append(release_followup_review)
    release_followup_binder = run_json_step(
        "release_followup_binder",
        ["python3", "skills/core/release-evidence-binder/scripts/bind_release.py", "--artifact-dir", str(release_followup_dir), "--out", str(release_followup_dir / "release_gate.json")],
    )
    steps.append(release_followup_binder)
    happy_summary = json.loads((happy_dir / "auto_run_summary.json").read_text(encoding="utf-8")) if (happy_dir / "auto_run_summary.json").exists() else {}
    happy_ready_status = json.loads((happy_dir / "implementation_ready_status.json").read_text(encoding="utf-8")) if (happy_dir / "implementation_ready_status.json").exists() else {}
    data_summary = json.loads((data_dir / "auto_run_summary.json").read_text(encoding="utf-8")) if (data_dir / "auto_run_summary.json").exists() else {}
    release_ready_status = json.loads((release_happy_dir / "release_ready_status.json").read_text(encoding="utf-8")) if (release_happy_dir / "release_ready_status.json").exists() else {}
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
            and happy_resolved_step.get("returncode") == 0
            and happy_ready_step.get("returncode") == 0
            and (happy_dir / "open_questions.json").exists()
            and json.loads((happy_dir / "open_questions.json").read_text(encoding="utf-8")).get("decision") == "pass"
            and happy_ready_status.get("can_implement") is True
            and happy_ready_status.get("next_stage") == "implementation"
            and happy_ready_status.get("next_action_type") == "ready_to_implement"
            and not happy_ready_status.get("blockers")
        ),
        "decision": "pass" if happy_ready_status.get("can_implement") is True else "block",
        "reason": "resolved questions plus complete design, plan, docs, Git, and edit-permit evidence reach can_implement=true",
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
            and any(gap.get("artifact") in {"open_questions.json", "configuration_readiness.json", "data_security_review.json", "performance_review.json"} for gap in data_summary.get("profile_gate_gaps", []))
        ),
        "decision": data_summary.get("decision", ""),
        "reason": "data migration blocks on unresolved requirements and design-time configuration, security, or performance evidence rather than a post-implementation release gate",
    }
    release_blocked_case = {
        "case": "release_readiness_blocked_path",
        "passed": release_blocked_step.get("returncode") != 0 and release_blocked_step.get("decision") == "no_go",
        "decision": release_blocked_step.get("decision", ""),
        "reason": "release binder blocks missing release evidence",
    }
    release_happy_case = {
        "case": "release_readiness_happy_path",
        "passed": (
            release_happy_step.get("returncode") == 0
            and release_happy_step.get("decision") == "go"
            and release_ready_step.get("returncode") == 0
            and release_ready_status.get("can_release") is True
            and release_ready_status.get("next_action_type") == "ready_to_release"
            and not release_ready_status.get("blockers")
        ),
        "decision": release_happy_step.get("decision", ""),
        "reason": "release binder approves complete clean synthetic evidence",
    }
    release_followup_case = {
        "case": "release_followup_chain_path",
        "passed": (
            release_followup_collect.get("returncode") == 0
            and release_followup_collect.get("decision") == "pass"
            and release_followup_review.get("returncode") == 0
            and release_followup_review.get("decision") == "approve"
            and release_followup_binder.get("returncode") == 0
            and release_followup_binder.get("decision") == "go"
        ),
        "decision": release_followup_binder.get("decision", ""),
        "reason": "implementation follow-ups are collected, reviewed, and release-bound end to end",
    }
    cases = [blocked_case, happy_case, frontend_case, data_case, release_blocked_case, release_happy_case, release_followup_case]
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
