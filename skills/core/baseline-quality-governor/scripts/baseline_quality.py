#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-baseline-quality-v1"
REQUIRED = ["overview", "module_hints", "api_surface_ref", "config_surface_ref", "dependency_surface_ref", "test_hints", "risk_hints", "limitations", "human_followups"]


def load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def review(baseline: Path) -> dict[str, Any]:
    data = load(baseline)
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not data:
        blockers.append({"source": str(baseline), "message": "baseline json is missing or invalid"})
    for key in REQUIRED:
        if data and not data.get(key):
            warnings.append({"source": key, "message": "baseline field is missing or empty"})
    decision = "block" if blockers else "warn" if warnings else "pass"
    return {"schema": SCHEMA, "decision": decision, "baseline": str(baseline), "blockers": blockers, "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser(description="Review baseline quality")
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = review(Path(args.baseline))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
