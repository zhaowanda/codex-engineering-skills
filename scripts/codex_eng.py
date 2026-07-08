#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


COMMANDS = {
    "inspect": ["python3", "skills/core/delivery-runner/scripts/delivery_runner.py", "inspect"],
    "ingest": ["python3", "skills/core/requirement-document-ingestor/scripts/ingest_requirement.py"],
    "spec": ["python3", "skills/core/spec-governor/scripts/spec_governor.py", "normalize"],
    "technical-design": ["python3", "skills/core/technical-design-governor/scripts/technical_design.py"],
    "architecture-design": ["python3", "skills/core/architecture-design-governor/scripts/architecture_design.py"],
    "test-design": ["python3", "skills/core/test-design-governor/scripts/test_design.py", "render"],
    "test-data": ["python3", "skills/core/test-data-governor/scripts/test_data.py"],
    "diff-impact": ["python3", "skills/core/diff-impact-analyzer/scripts/diff_impact.py"],
    "collect-evidence": ["python3", "skills/core/evidence-auto-collector/scripts/evidence_collect.py"],
    "install-skills": ["python3", "skills/core/skill-installation-governor/scripts/install_skills.py"],
    "install-all": ["python3", "skills/core/skill-installation-governor/scripts/install_skills.py", "--source", "."],
    "artifact-schema": ["python3", "skills/core/artifact-schema-governor/scripts/artifact_schema.py"],
    "prompt-pack": ["python3", "skills/core/prompt-pack-governor/scripts/prompt_pack.py"],
    "contribution": ["python3", "skills/core/contribution-governor/scripts/contribution.py"],
    "security-policy": ["python3", "skills/core/security-policy-governor/scripts/security_policy.py"],
    "docs-site": ["python3", "skills/core/docs-site-governor/scripts/docs_site.py", "validate"],
    "compatibility": ["python3", "skills/core/compatibility-governor/scripts/compatibility.py"],
    "mcp-integration": ["python3", "skills/core/mcp-integration-governor/scripts/mcp_integration.py"],
    "benchmark": ["python3", "skills/core/benchmark-governor/scripts/benchmark.py"],
    "release-package": ["python3", "skills/core/release-package-governor/scripts/release_package.py"],
    "deprecation": ["python3", "skills/core/deprecation-governor/scripts/deprecation.py"],
    "roadmap": ["python3", "skills/core/roadmap-governor/scripts/roadmap.py"],
    "docs-readability": ["python3", "skills/core/docs-readability-governor/scripts/docs_readability.py"],
    "docs-governor": ["python3", "skills/core/docs-governor/scripts/docs_governor.py"],
    "prompt-effectiveness": ["python3", "skills/core/prompt-effectiveness-governor/scripts/prompt_effectiveness.py"],
    "repository-analyze": ["python3", "skills/core/repository-analyzer/scripts/repository_analyzer.py"],
    "api-surface": ["python3", "skills/core/api-surface-extractor/scripts/api_surface.py"],
    "config-surface": ["python3", "skills/core/config-surface-extractor/scripts/config_surface.py"],
    "dependency-surface": ["python3", "skills/core/dependency-surface-analyzer/scripts/dependency_surface.py"],
    "git-history": ["python3", "skills/core/git-history-miner/scripts/git_history.py"],
    "baseline-quality": ["python3", "skills/core/baseline-quality-governor/scripts/baseline_quality.py"],
    "project-understand": ["python3", "skills/core/project-understanding-runner/scripts/project_understand.py"],
    "project-runner": ["python3", "skills/core/project-runner/scripts/project_runner.py"],
    "cross-repo-plan": ["python3", "skills/core/cross-repo-planner/scripts/cross_repo_plan.py"],
    "sync-local-skills": ["python3", "scripts/sync_local_skills.py"],
}


def run_command(args: list[str]) -> int:
    proc = subprocess.run(args, cwd=ROOT)
    return proc.returncode


def run_capture(args: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    return proc.returncode, proc.stdout, proc.stderr


def run_json_step(name: str, args: list[str]) -> dict[str, Any]:
    proc = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    data: Any = {}
    try:
        data = json.loads(proc.stdout)
    except Exception:
        data = {}
    return {
        "name": name,
        "command": args,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "schema": data.get("schema") if isinstance(data, dict) else "",
        "decision": data.get("decision") if isinstance(data, dict) else "",
        "stdout_tail": proc.stdout[-1000:],
        "stderr_tail": proc.stderr[-1000:],
    }


def parse_json_text(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def human_bool(value: bool) -> str:
    return "yes" if value else "no"


def render_auto_human(result: dict[str, Any]) -> str:
    profile = result.get("workflow_profile") if isinstance(result.get("workflow_profile"), dict) else {}
    reason = result.get("profile_selection_reason") if isinstance(result.get("profile_selection_reason"), dict) else {}
    blockers = result.get("blockers") if isinstance(result.get("blockers"), list) else []
    readiness_blockers = result.get("readiness_blockers") if isinstance(result.get("readiness_blockers"), list) else []
    gate_gaps = result.get("profile_gate_gaps") if isinstance(result.get("profile_gate_gaps"), list) else []
    lines = [
        "Codex auto summary",
        f"- decision: {result.get('decision', '')}",
        f"- doc_id: {result.get('doc_id', '')}",
        f"- profile: {profile.get('name', '')}",
        f"- profile_reason: {reason.get('reason', '')}",
        f"- next_stage: {result.get('next_stage', '')}",
        f"- can_implement: {human_bool(bool(result.get('can_implement')))}",
        f"- can_release: {human_bool(bool(result.get('can_release')))}",
        f"- next_command: {result.get('next_command') or result.get('next_profile_command') or ''}",
    ]
    if blockers:
        lines.append("- blockers:")
        for item in blockers[:5]:
            if isinstance(item, dict):
                lines.append(f"  - {item.get('source', 'unknown')}: {item.get('message', '')}")
    if readiness_blockers:
        lines.append("- readiness_blockers:")
        for item in readiness_blockers[:5]:
            if isinstance(item, dict):
                lines.append(f"  - {item.get('source', 'unknown')}: {item.get('message', '')}")
    docs = result.get("docs_readiness") if isinstance(result.get("docs_readiness"), dict) else {}
    if docs:
        lines.append(f"- docs_readiness: {docs.get('decision', '')}")
        if docs.get("next_command"):
            lines.append(f"- docs_next_command: {docs.get('next_command', '')}")
    if gate_gaps:
        lines.append("- profile_gate_gaps:")
        for item in gate_gaps[:5]:
            if isinstance(item, dict):
                lines.append(f"  - {item.get('artifact', '')}: {item.get('message', '')}")
    return "\n".join(lines) + "\n"


def render_status_human(result: dict[str, Any]) -> str:
    profile = result.get("workflow_profile") if isinstance(result.get("workflow_profile"), dict) else {}
    primary = result.get("primary_next_action") if isinstance(result.get("primary_next_action"), dict) else {}
    blockers = result.get("blockers") if isinstance(result.get("blockers"), list) else []
    lines = [
        "Codex delivery status",
        f"- artifact_dir: {result.get('artifact_dir', '')}",
        f"- profile: {profile.get('name', '')}",
        f"- next_stage: {result.get('next_stage', '')}",
        f"- next_action_type: {result.get('next_action_type', '')}",
        f"- can_implement: {human_bool(bool(result.get('can_implement')))}",
        f"- can_release: {human_bool(bool(result.get('can_release')))}",
        f"- next_summary: {primary.get('summary', '')}",
        f"- next_command: {primary.get('command') or result.get('next_command') or result.get('next_profile_command') or ''}",
    ]
    if blockers:
        lines.append("- blockers:")
        for item in blockers[:5]:
            if isinstance(item, dict):
                lines.append(f"  - {item.get('source', 'unknown')}: {item.get('message', '')}")
    return "\n".join(lines) + "\n"


def render_doctor_human(result: dict[str, Any]) -> str:
    checks = result.get("checks") if isinstance(result.get("checks"), list) else []
    lines = [
        "Codex doctor",
        f"- decision: {result.get('decision', '')}",
        f"- next_action: {result.get('next_action', '')}",
        "- checks:",
    ]
    for item in checks:
        if isinstance(item, dict):
            lines.append(f"  - {item.get('name', '')}: {'pass' if item.get('passed') else 'block'} ({item.get('decision', '')})")
    return "\n".join(lines) + "\n"


def render_implement_human(result: dict[str, Any]) -> str:
    lines = [
        "Codex implement dry-run",
        f"- decision: {result.get('decision', '')}",
        f"- can_edit: {human_bool(bool(result.get('can_edit')))}",
        f"- next_action: {result.get('next_action', '')}",
    ]
    allowed = result.get("allowed_files") if isinstance(result.get("allowed_files"), list) else []
    commands = result.get("recommended_validation_commands") if isinstance(result.get("recommended_validation_commands"), list) else []
    missing = result.get("missing_gates") if isinstance(result.get("missing_gates"), list) else []
    docs = result.get("docs_readiness") if isinstance(result.get("docs_readiness"), dict) else {}
    if docs:
        lines.append(f"- docs_readiness: {docs.get('decision', '')}")
        if docs.get("manifest"):
            lines.append(f"- docs_manifest: {docs.get('manifest', '')}")
    if allowed:
        lines.append("- allowed_files:")
        lines.extend(f"  - {item}" for item in allowed[:10])
    if commands:
        lines.append("- validation_commands:")
        lines.extend(f"  - {item}" for item in commands[:10])
    if missing:
        lines.append("- missing_gates:")
        lines.extend(f"  - {item}" for item in missing[:10])
    return "\n".join(lines) + "\n"


def doctor() -> dict[str, Any]:
    checks = [
        run_json_step("skill_health", ["python3", "scripts/skill_health.py", "--root", "."]),
        run_json_step("privacy_scan", ["python3", "scripts/privacy_scan.py", "--root", ".", "--patterns", "config/private-patterns.example.yaml"]),
        run_json_step("forward_test", ["python3", "skills/core/forward-test-runner/scripts/forward_test.py", "--root", "."]),
        run_json_step("benchmark", ["python3", "skills/core/benchmark-governor/scripts/benchmark.py", "--root", "."]),
    ]
    blockers = [{"source": item["name"], "message": "doctor check failed"} for item in checks if not item["passed"]]
    return {
        "schema": "codex-doctor-v1",
        "decision": "block" if blockers else "pass",
        "checks": checks,
        "blockers": blockers,
        "next_action": "Fix failed checks before publishing or relying on the local skill set." if blockers else "Skills are ready for local use.",
    }


def setup(force: bool = False, output_format: str = "human") -> tuple[int, dict[str, Any]]:
    install_args = ["python3", "install.py", "--force" if force else "--dry-run"]
    install_code, install_stdout, install_stderr = run_capture(install_args)
    doctor_result = doctor()
    result = {
        "schema": "codex-setup-v1",
        "decision": "pass" if install_code == 0 and doctor_result.get("decision") == "pass" else "block",
        "install": {
            "command": install_args,
            "returncode": install_code,
            "passed": install_code == 0,
            "stdout_tail": install_stdout[-1000:],
            "stderr_tail": install_stderr[-1000:],
            "mode": "force" if force else "dry_run",
        },
        "doctor": doctor_result,
        "next_action": "Run with --force to install skills." if not force and install_code == 0 else doctor_result.get("next_action", ""),
    }
    if output_format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("Codex setup")
        print(f"- decision: {result['decision']}")
        print(f"- install_mode: {result['install']['mode']}")
        print(f"- install: {'pass' if result['install']['passed'] else 'block'}")
        print(f"- doctor: {doctor_result.get('decision', '')}")
        print(f"- next_action: {result['next_action']}")
    return (0 if result["decision"] == "pass" else 1), result


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified CLI for Codex engineering skills")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_auto = sub.add_parser("auto")
    p_auto.add_argument("--input", required=True)
    p_auto.add_argument("--doc-id")
    p_auto.add_argument("--title")
    p_auto.add_argument("--repo")
    p_auto.add_argument("--project")
    p_auto.add_argument("--out")
    p_auto.add_argument("--profile")
    p_auto.add_argument("--docs-root")
    p_auto.add_argument("--doc-language", choices=["en", "zh", "auto"], default="auto")
    p_auto.add_argument("--force", action="store_true")
    p_auto.add_argument("--format", choices=["json", "human"], default="json")
    p_setup = sub.add_parser("setup")
    p_setup.add_argument("--force", action="store_true")
    p_setup.add_argument("--format", choices=["json", "human"], default="human")
    p_project = sub.add_parser("project")
    p_project.add_argument("mode", choices=["new", "legacy"])
    p_project.add_argument("--project", required=True)
    p_project.add_argument("--repo", required=True)
    p_project.add_argument("--type", required=True)
    p_project.add_argument("--overlay-root", required=True)
    p_project.add_argument("--default-branch", default="main")
    p_project.add_argument("--git-url")
    p_project.add_argument("--depends-on", action="append", default=[])
    p_project.add_argument("--out")
    p_inspect = sub.add_parser("inspect")
    p_inspect.add_argument("--artifact-dir", required=True)
    p_inspect.add_argument("--profile")
    p_inspect.add_argument("--format", choices=["json", "human"], default="json")
    p_next = sub.add_parser("next")
    p_next.add_argument("--artifact-dir", required=True)
    p_next.add_argument("--profile")
    p_next.add_argument("--format", choices=["json", "human"], default="human")
    p_docs = sub.add_parser("docs")
    p_docs.add_argument("mode", choices=["configure", "init", "validate"])
    p_docs.add_argument("--docs-root", required=True)
    p_docs.add_argument("--doc-id", default="")
    p_docs.add_argument("--doc-language", choices=["en", "zh"], default="en")
    p_docs.add_argument("--git-url", default="")
    p_docs.add_argument("--require-git", action="store_true")
    p_implement = sub.add_parser("implement")
    p_implement.add_argument("--artifact-dir", required=True)
    p_implement.add_argument("--docs-root")
    p_implement.add_argument("--doc-id")
    p_implement.add_argument("--dry-run", action="store_true", default=True)
    p_implement.add_argument("--format", choices=["json", "human"], default="human")
    p_e2e = sub.add_parser("synthetic-e2e")
    p_e2e.add_argument("--out-dir", required=True)
    p_scenarios = sub.add_parser("scenarios")
    p_scenarios.add_argument("--format", choices=["json", "markdown"], default="json")
    p_doctor = sub.add_parser("doctor")
    p_doctor.add_argument("--format", choices=["json", "human"], default="json")
    p_passthrough = sub.add_parser("run")
    p_passthrough.add_argument("tool", choices=sorted(COMMANDS))
    p_passthrough.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    if args.cmd == "auto":
        command = ["python3", "skills/core/auto-runner/scripts/auto_runner.py", "--input", args.input]
        for flag in ["doc_id", "title", "repo", "project", "out", "profile", "docs_root", "doc_language"]:
            value = getattr(args, flag)
            if value:
                command.extend([f"--{flag.replace('_', '-')}", value])
        if args.force:
            command.append("--force")
        if args.format == "json":
            return run_command(command)
        code, stdout, stderr = run_capture(command)
        result = parse_json_text(stdout)
        if result:
            print(render_auto_human(result), end="")
        else:
            print(stdout, end="")
            print(stderr, end="", file=sys.stderr)
        return code
    if args.cmd == "setup":
        code, _ = setup(args.force, args.format)
        return code
    if args.cmd == "project":
        command = [
            "python3",
            "skills/core/project-runner/scripts/project_runner.py",
            args.mode,
            "--project",
            args.project,
            "--repo",
            args.repo,
            "--type",
            args.type,
            "--overlay-root",
            args.overlay_root,
            "--default-branch",
            args.default_branch,
        ]
        if args.git_url:
            command.extend(["--git-url", args.git_url])
        for dependency in args.depends_on:
            command.extend(["--depends-on", dependency])
        if args.out:
            command.extend(["--out", args.out])
        return run_command(command)
    if args.cmd == "inspect":
        command = COMMANDS["inspect"] + ["--artifact-dir", args.artifact_dir]
        if args.profile:
            command.extend(["--profile", args.profile])
        if args.format == "json":
            return run_command(command)
        code, stdout, stderr = run_capture(command)
        result = parse_json_text(stdout)
        if result:
            print(render_status_human(result), end="")
        else:
            print(stdout, end="")
            print(stderr, end="", file=sys.stderr)
        return code
    if args.cmd == "next":
        command = COMMANDS["inspect"] + ["--artifact-dir", args.artifact_dir]
        if args.profile:
            command.extend(["--profile", args.profile])
        code, stdout, stderr = run_capture(command)
        result = parse_json_text(stdout)
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2) if result else stdout, end="" if result else "")
        elif result:
            print(render_status_human(result), end="")
        else:
            print(stdout, end="")
            print(stderr, end="", file=sys.stderr)
        return 0 if result else code
    if args.cmd == "docs":
        command = COMMANDS["docs-governor"] + [args.mode, "--docs-root", args.docs_root]
        if args.mode in {"init", "validate"}:
            if not args.doc_id:
                print("--doc-id is required for docs init/validate", file=sys.stderr)
                return 2
            command.extend(["--doc-id", args.doc_id])
            command.extend(["--doc-language", args.doc_language])
        if args.git_url:
            command.extend(["--git-url", args.git_url])
        if args.require_git:
            command.append("--require-git")
        return run_command(command)
    if args.cmd == "implement":
        command = ["python3", "scripts/implement_dry_run.py", "--artifact-dir", args.artifact_dir]
        if args.docs_root:
            command.extend(["--docs-root", args.docs_root])
        if args.doc_id:
            command.extend(["--doc-id", args.doc_id])
        code, stdout, stderr = run_capture(command)
        result = parse_json_text(stdout)
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2) if result else stdout, end="" if result else "")
        elif result:
            print(render_implement_human(result), end="")
        else:
            print(stdout, end="")
            print(stderr, end="", file=sys.stderr)
        return 0 if result else code
    if args.cmd == "synthetic-e2e":
        return run_command(["python3", "skills/templates/synthetic-e2e-runner/scripts/run_synthetic_e2e.py", "--out-dir", args.out_dir])
    if args.cmd == "scenarios":
        return run_command(["python3", "scripts/scenario_catalog.py", "--format", args.format])
    if args.cmd == "doctor":
        result = doctor()
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(render_doctor_human(result), end="")
        return 0 if result["decision"] == "pass" else 1
    if args.cmd == "run":
        return run_command(COMMANDS[args.tool] + args.args)
    print(json.dumps({"error": "unknown command"}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
