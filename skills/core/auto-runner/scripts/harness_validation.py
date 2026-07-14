#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-harness-validation-v1"
DEFAULT_BUDGETS = {
    "evidence_bundle.json": 100_000,
    "spec.json": 300_000,
    "technical_design.json": 300_000,
    "architecture_design.json": 300_000,
    "test_design.json": 300_000,
    "delivery_plan.json": 300_000,
    "design_architecture_review.json": 500_000,
    "delivery_plan_review.json": 500_000,
}
EDIT_KEYS = {"allowed_files", "files_to_edit", "modify_files", "implementation_files"}
OWNER_KEYS = {"owner_file", "selected_entrypoint", "primary_file"}


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def values_for_keys(value: Any, keys: set[str]) -> list[str]:
    result: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in keys:
                candidates = child if isinstance(child, list) else [child]
                for candidate in candidates:
                    if isinstance(candidate, str) and candidate.strip():
                        result.append(candidate.strip())
                    elif isinstance(candidate, dict):
                        for nested_key in ("path", "file"):
                            if candidate.get(nested_key):
                                result.append(str(candidate[nested_key]).strip())
            result.extend(values_for_keys(child, keys))
    elif isinstance(value, list):
        for child in value:
            result.extend(values_for_keys(child, keys))
    return result


def normalize_path(value: str) -> str:
    return value.replace("\\", "/").lstrip("./")


def validate(artifact_dir: Path, budgets: dict[str, int] | None = None) -> dict[str, Any]:
    budgets = budgets or DEFAULT_BUDGETS
    blockers: list[dict[str, Any]] = []
    sizes: list[dict[str, Any]] = []
    for name, maximum in budgets.items():
        path = artifact_dir / name
        if not path.exists():
            continue
        size = path.stat().st_size
        sizes.append({"artifact": name, "bytes": size, "max_bytes": maximum, "within_budget": size <= maximum})
        if size > maximum:
            blockers.append({"source": "artifact_budget", "artifact": name, "message": f"artifact is {size} bytes; budget is {maximum}"})

    bundle_path = artifact_dir / "project_understanding/evidence_bundle.json"
    if not bundle_path.exists():
        bundle_path = artifact_dir / "evidence_bundle.json"
    bundle = read_json(bundle_path) if bundle_path.exists() else {}
    modify = {
        normalize_path(str(item.get("path") or ""))
        for item in bundle.get("anchors", [])
        if isinstance(item, dict) and item.get("role") == "confirmed_modify"
    }
    references = {
        normalize_path(str(item.get("path") or ""))
        for item in bundle.get("anchors", [])
        if isinstance(item, dict) and item.get("role") == "confirmed_reference"
    }
    checked_paths: list[dict[str, str]] = []
    if modify:
        for name in ["technical_design.json", "architecture_design.json", "delivery_plan.json"]:
            data = read_json(artifact_dir / name)
            keys = EDIT_KEYS | (OWNER_KEYS if name != "delivery_plan.json" else set())
            for raw_path in values_for_keys(data, keys):
                path = normalize_path(raw_path)
                if not path or not Path(path).suffix:
                    continue
                checked_paths.append({"artifact": name, "path": path})
                if path in references:
                    blockers.append({"source": "evidence_consistency", "artifact": name, "path": path, "message": "reference-only anchor is used as an implementation target"})

    return {
        "schema": SCHEMA,
        "decision": "block" if blockers else "pass",
        "artifact_dir": str(artifact_dir),
        "artifact_sizes": sizes,
        "evidence_summary": {"confirmed_modify": sorted(modify), "confirmed_reference": sorted(references)},
        "checked_paths": checked_paths,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Harness artifact budgets and evidence consistency")
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--out")
    args = parser.parse_args()
    result = validate(Path(args.artifact_dir))
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
