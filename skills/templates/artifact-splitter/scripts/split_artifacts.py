#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_json(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def ref(path: str | None, include_local_paths: bool) -> str:
    if not path:
        return ""
    p = Path(path)
    return str(p.resolve()) if include_local_paths else p.name


def bullet(items: list[str]) -> str:
    clean = [item for item in items if item]
    if not clean:
        return "- None\n"
    return "".join(f"- {item}\n" for item in clean)


def first_text(value: Any, *keys: str) -> str:
    if isinstance(value, dict):
        for key in keys:
            if value.get(key):
                return str(value[key])
    return ""


def technical_summary(technical: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for item in as_list(technical.get("requirement_trace")):
        text = first_text(item, "summary", "requirement_id")
        if text:
            lines.append(text)
    return lines


def option_summary(technical: dict[str, Any], architecture: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    selected = technical.get("selected_solution", {}) if isinstance(technical.get("selected_solution"), dict) else {}
    if selected:
        lines.append(f"Technical: {selected.get('selected_option_id', '')} - {selected.get('selection_reason', '')}")
        if selected.get("tradeoffs"):
            lines.append(f"Technical tradeoffs: {', '.join(str(item) for item in as_list(selected.get('tradeoffs')))}")
    selected_arch = architecture.get("selected_architecture", {}) if isinstance(architecture.get("selected_architecture"), dict) else {}
    if selected_arch:
        lines.append(f"Architecture: {selected_arch.get('selected_option_id', '')} - {selected_arch.get('selection_reason', '')}")
        if selected_arch.get("tradeoffs"):
            lines.append(f"Architecture tradeoffs: {', '.join(str(item) for item in as_list(selected_arch.get('tradeoffs')))}")
    return lines


def repo_summary(plan: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for task in as_list(plan.get("repo_tasks")):
        if isinstance(task, dict):
            repo = task.get("repo", "")
            role = task.get("role", "")
            responsibility = task.get("responsibility", "")
            files = ", ".join(str(item) for item in as_list(task.get("allowed_files")))
            suffix = f"; files: {files}" if files else ""
            lines.append(f"{repo} [{role}] - {responsibility}{suffix}")
    return lines


def review_summary(review: dict[str, Any]) -> list[str]:
    if not review:
        return []
    counts = review.get("severity_counts", {})
    return [
        f"Decision: {review.get('decision', '')}",
        f"Score: {review.get('score', '')}",
        f"Level: {review.get('level', '')}",
        f"Findings: blocker={counts.get('blocker', 0)}, high={counts.get('high', 0)}, medium={counts.get('medium', 0)}, low={counts.get('low', 0)}",
        f"Implementation allowed: {review.get('readiness_gate', {}).get('implementation_allowed', False)}",
    ]


def risks_and_gates(plan: dict[str, Any], review: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for item in as_list(plan.get("open_gates")):
        lines.append(str(item))
    for item in as_list(review.get("blockers")):
        if isinstance(item, dict):
            lines.append(str(item.get("message") or item))
        else:
            lines.append(str(item))
    return lines


def render_markdown(
    doc_id: str,
    title: str,
    technical: dict[str, Any],
    architecture: dict[str, Any],
    review: dict[str, Any],
    plan: dict[str, Any],
    artifact_refs: dict[str, str],
) -> str:
    release = plan.get("release_plan", {}) if isinstance(plan.get("release_plan"), dict) else {}
    rollback = plan.get("rollback_plan", {}) if isinstance(plan.get("rollback_plan"), dict) else {}
    return "\n".join([
        f"# {title}",
        "",
        f"- Doc ID: {doc_id}",
        f"- Generated At: {now()}",
        "",
        "## Requirement Summary",
        bullet(technical_summary(technical)),
        "## Selected Design",
        bullet(option_summary(technical, architecture)),
        "## Repository Plan",
        bullet(repo_summary(plan)),
        "## Design Review Gate",
        bullet(review_summary(review)),
        "## Release And Rollback",
        bullet([
            f"Release order: {', '.join(str(item) for item in as_list(release.get('release_order')))}" if release else "",
            f"Rollback order: {', '.join(str(item) for item in as_list(rollback.get('rollback_order')))}" if rollback else "",
            f"Release gate: {release.get('release_gate', '')}" if release else "",
        ]),
        "## Risks And Open Gates",
        bullet(risks_and_gates(plan, review)),
        "## Machine Artifacts",
        bullet([f"{name}: {path}" for name, path in artifact_refs.items() if path]),
        "## Next Actions",
        bullet([
            "Resolve all open gates before Git preparation." if plan.get("open_gates") else "",
            "Run git-worktree-governor prepare-plan after delivery plan is ready." if plan else "",
            "Run edit-readiness-governor before any file write.",
            "Run workspace-write-guard snapshot before direct edits and audit after edits.",
        ]),
        "",
    ])


def split(args: argparse.Namespace) -> dict[str, Any]:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    technical = load_json(args.technical_design)
    architecture = load_json(args.architecture_design)
    review = load_json(args.design_review)
    plan = load_json(args.delivery_plan)
    artifact_refs = {
        "technical_design": ref(args.technical_design, args.include_local_paths),
        "architecture_design": ref(args.architecture_design, args.include_local_paths),
        "design_review": ref(args.design_review, args.include_local_paths),
        "delivery_plan": ref(args.delivery_plan, args.include_local_paths),
    }
    markdown = render_markdown(args.doc_id, args.title, technical, architecture, review, plan, artifact_refs)
    summary_path = out_dir / "human_summary.md"
    summary_path.write_text(markdown, encoding="utf-8")
    manifest = {
        "schema": "codex-artifact-split-manifest-v1",
        "doc_id": args.doc_id,
        "title": args.title,
        "human_summary": str(summary_path.resolve()) if args.include_local_paths else summary_path.name,
        "machine_artifacts": artifact_refs,
        "include_local_paths": args.include_local_paths,
        "source_of_truth": "machine JSON artifacts remain authoritative for gates",
        "generated_at": now(),
    }
    (out_dir / "artifact_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Split machine artifacts into human readable summaries")
    parser.add_argument("--doc-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--technical-design", default="")
    parser.add_argument("--architecture-design", default="")
    parser.add_argument("--design-review", default="")
    parser.add_argument("--delivery-plan", default="")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--include-local-paths", action="store_true")
    args = parser.parse_args()
    manifest = split(args)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
