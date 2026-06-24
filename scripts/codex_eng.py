#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


COMMANDS = {
    "inspect": ["python3", "skills/core/delivery-runner/scripts/delivery_runner.py", "inspect"],
    "ingest": ["python3", "skills/core/requirement-document-ingestor/scripts/ingest_requirement.py"],
    "spec": ["python3", "skills/core/spec-governor/scripts/spec_governor.py", "normalize"],
    "technical-design": ["python3", "skills/core/technical-design-governor/scripts/technical_design.py"],
    "architecture-design": ["python3", "skills/core/architecture-design-governor/scripts/architecture_design.py"],
    "test-design": ["python3", "skills/core/test-design-governor/scripts/test_design.py", "render"],
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
    "prompt-effectiveness": ["python3", "skills/core/prompt-effectiveness-governor/scripts/prompt_effectiveness.py"],
    "repository-analyze": ["python3", "skills/core/repository-analyzer/scripts/repository_analyzer.py"],
    "api-surface": ["python3", "skills/core/api-surface-extractor/scripts/api_surface.py"],
    "config-surface": ["python3", "skills/core/config-surface-extractor/scripts/config_surface.py"],
    "dependency-surface": ["python3", "skills/core/dependency-surface-analyzer/scripts/dependency_surface.py"],
    "git-history": ["python3", "skills/core/git-history-miner/scripts/git_history.py"],
    "baseline-quality": ["python3", "skills/core/baseline-quality-governor/scripts/baseline_quality.py"],
    "project-understand": ["python3", "skills/core/project-understanding-runner/scripts/project_understand.py"],
    "sync-local-skills": ["python3", "scripts/sync_local_skills.py"],
}


def run_command(args: list[str]) -> int:
    proc = subprocess.run(args, cwd=ROOT)
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified CLI for Codex engineering skills")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_inspect = sub.add_parser("inspect")
    p_inspect.add_argument("--artifact-dir", required=True)
    p_e2e = sub.add_parser("synthetic-e2e")
    p_e2e.add_argument("--out-dir", required=True)
    p_passthrough = sub.add_parser("run")
    p_passthrough.add_argument("tool", choices=sorted(COMMANDS))
    p_passthrough.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    if args.cmd == "inspect":
        return run_command(COMMANDS["inspect"] + ["--artifact-dir", args.artifact_dir])
    if args.cmd == "synthetic-e2e":
        return run_command(["python3", "skills/templates/synthetic-e2e-runner/scripts/run_synthetic_e2e.py", "--out-dir", args.out_dir])
    if args.cmd == "run":
        return run_command(COMMANDS[args.tool] + args.args)
    print(json.dumps({"error": "unknown command"}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
