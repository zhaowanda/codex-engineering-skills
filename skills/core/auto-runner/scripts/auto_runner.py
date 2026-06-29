#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
SCHEMA = "codex-auto-runner-summary-v1"


def slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-")
    return text or "requirement"


def default_doc_id(input_path: Path) -> str:
    return f"REQ-{slug(input_path.stem)}"


def default_title(input_path: Path) -> str:
    words = re.sub(r"[_-]+", " ", input_path.stem).strip()
    return words.title() if words else "Requirement"


def default_out(doc_id: str) -> Path:
    return Path("/tmp/codex-auto") / doc_id


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def run_command(name: str, args: list[str]) -> dict[str, Any]:
    proc = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    return {
        "name": name,
        "command": args,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def run_if_needed(name: str, output: Path, command: list[str], force: bool, generated: list[str], skipped: list[str], steps: list[dict[str, Any]]) -> None:
    if output.exists() and not force:
        skipped.append(output.name)
        steps.append({"name": name, "skipped": True, "output": str(output), "reason": "artifact exists"})
        return
    result = run_command(name, command)
    steps.append(result | {"output": str(output)})
    if output.exists():
        generated.append(output.name)


def collect_blockers(steps: list[dict[str, Any]], inspect_status: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for step in steps:
        if step.get("skipped"):
            continue
        if step.get("name") == "inspect":
            continue
        if step.get("output") and Path(str(step["output"])).exists():
            continue
        if step.get("returncode", 0) != 0:
            blockers.append({"source": step.get("name"), "message": "step returned non-zero", "returncode": step.get("returncode")})
    for item in inspect_status.get("blockers", []) or []:
        if isinstance(item, dict):
            blockers.append(item)
    return blockers


def run(
    input_path: Path,
    doc_id: str | None = None,
    title: str | None = None,
    repo: Path | None = None,
    project: str | None = None,
    out: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    input_path = input_path.resolve()
    doc_id = doc_id or default_doc_id(input_path)
    title = title or default_title(input_path)
    out = (out or default_out(doc_id)).resolve()
    out.mkdir(parents=True, exist_ok=True)

    generated: list[str] = []
    skipped: list[str] = []
    steps: list[dict[str, Any]] = []

    if repo and project:
        project_out = out / "project_understanding"
        marker = project_out / "baseline_quality.json"
        run_if_needed(
            "project_understanding",
            marker,
            [
                "python3",
                "skills/core/project-understanding-runner/scripts/project_understand.py",
                "--repo",
                str(repo),
                "--project",
                project,
                "--out",
                str(project_out),
            ],
            force,
            generated,
            skipped,
            steps,
        )
    else:
        project_out = None

    normalized = out / "requirement.normalized.txt"
    run_if_needed(
        "ingest",
        normalized,
        [
            "python3",
            "skills/core/requirement-document-ingestor/scripts/ingest_requirement.py",
            "--input",
            str(input_path),
            "--doc-id",
            doc_id,
            "--out-dir",
            str(out),
        ],
        force,
        generated,
        skipped,
        steps,
    )

    spec = out / "spec.json"
    run_if_needed(
        "spec",
        spec,
        [
            "python3",
            "skills/core/spec-governor/scripts/spec_governor.py",
            "normalize",
            "--doc-id",
            doc_id,
            "--title",
            title,
            "--input",
            str(normalized),
            "--out",
            str(spec),
        ],
        force,
        generated,
        skipped,
        steps,
    )

    technical = out / "technical_design.json"
    technical_command = ["python3", "skills/core/technical-design-governor/scripts/technical_design.py", "--spec", str(spec), "--out", str(technical)]
    if project_out:
        technical_command.extend(["--project-understanding", str(project_out)])
    run_if_needed(
        "technical_design",
        technical,
        technical_command,
        force,
        generated,
        skipped,
        steps,
    )

    architecture = out / "architecture_design.json"
    architecture_command = [
        "python3",
        "skills/core/architecture-design-governor/scripts/architecture_design.py",
        "--spec",
        str(spec),
        "--technical-design",
        str(technical),
        "--out",
        str(architecture),
    ]
    if project_out:
        architecture_command.extend(["--project-understanding", str(project_out)])
    run_if_needed(
        "architecture_design",
        architecture,
        architecture_command,
        force,
        generated,
        skipped,
        steps,
    )

    test_design = out / "test_design.json"
    run_if_needed(
        "test_design",
        test_design,
        [
            "python3",
            "skills/core/test-design-governor/scripts/test_design.py",
            "render",
            "--spec",
            str(spec),
            "--technical-design",
            str(technical),
            "--architecture-design",
            str(architecture),
            "--out",
            str(test_design),
        ],
        force,
        generated,
        skipped,
        steps,
    )

    design_review = out / "design_architecture_review.json"
    run_if_needed(
        "design_review",
        design_review,
        [
            "python3",
            "skills/core/design-architecture-reviewer/scripts/design_arch_review.py",
            "review",
            "--technical-design",
            str(technical),
            "--architecture-design",
            str(architecture),
            "--out",
            str(design_review),
        ],
        force,
        generated,
        skipped,
        steps,
    )

    delivery_plan = out / "delivery_plan.json"
    delivery_command = [
        "python3",
        "skills/templates/delivery-plan-templates/scripts/render_delivery_plan.py",
        "--doc-id",
        doc_id,
        "--technical-design",
        str(technical),
        "--architecture-design",
        str(architecture),
        "--out",
        str(delivery_plan),
    ]
    if project_out:
        delivery_command.extend(["--project-understanding", str(project_out)])
    run_if_needed(
        "delivery_plan",
        delivery_plan,
        delivery_command,
        force,
        generated,
        skipped,
        steps,
    )

    delivery_status = out / "delivery_status.json"
    inspect_result = run_command(
        "inspect",
        [
            "python3",
            "skills/core/delivery-runner/scripts/delivery_runner.py",
            "inspect",
            "--artifact-dir",
            str(out),
            "--out",
            str(delivery_status),
        ],
    )
    steps.append(inspect_result)
    inspect_status = read_json(delivery_status)
    if not inspect_status and inspect_result.get("stdout_tail"):
        try:
            inspect_status = json.loads(str(inspect_result["stdout_tail"]))
        except Exception:
            inspect_status = {}

    blockers = collect_blockers(steps, inspect_status)
    summary = {
        "schema": SCHEMA,
        "decision": "block" if blockers else "pass",
        "doc_id": doc_id,
        "title": title,
        "input": str(input_path),
        "out_dir": str(out),
        "generated_artifacts": sorted(set(generated)),
        "skipped_artifacts": skipped,
        "steps": steps,
        "blockers": blockers,
        "inspect_status": inspect_status,
        "next_stage": inspect_status.get("next_stage", ""),
        "next_command": inspect_status.get("next_command", ""),
        "can_implement": bool(inspect_status.get("can_implement")),
        "can_release": bool(inspect_status.get("can_release")),
        "safety_boundary": "analysis_and_artifact_generation_only",
    }
    write_json(out / "auto_run_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="One-command safe workflow runner for Codex engineering skills")
    parser.add_argument("--input", required=True)
    parser.add_argument("--doc-id")
    parser.add_argument("--title")
    parser.add_argument("--repo")
    parser.add_argument("--project")
    parser.add_argument("--out")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = run(
        input_path=Path(args.input),
        doc_id=args.doc_id,
        title=args.title,
        repo=Path(args.repo) if args.repo else None,
        project=args.project,
        out=Path(args.out) if args.out else None,
        force=args.force,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
