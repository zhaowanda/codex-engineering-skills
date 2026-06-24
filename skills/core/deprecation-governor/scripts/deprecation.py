#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


SCHEMA = "codex-deprecation-review-v1"
REQUIRED_TERMS = ["notice", "migration", "compatibility window", "removal"]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def compatibility(root: Path) -> dict[str, Any]:
    proc = subprocess.run(["python3", "skills/core/compatibility-governor/scripts/compatibility.py", "--root", "."], cwd=root, text=True, capture_output=True)
    try:
        data = json.loads(proc.stdout)
    except Exception:
        data = {}
    return data if isinstance(data, dict) else {}


def review(root: Path) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    text = read(root / "docs/deprecation-policy.md")
    lower = text.lower()
    if not text:
        blockers.append({"source": "docs/deprecation-policy.md", "message": "deprecation policy is required"})
    for term in REQUIRED_TERMS:
        if text and term not in lower:
            blockers.append({"source": "docs/deprecation-policy.md", "message": f"missing deprecation topic: {term}"})
    compat = compatibility(root)
    if compat.get("warnings") and "migration" not in lower and "deprecation" not in lower:
        blockers.append({"source": "compatibility", "message": "compatibility warnings require migration or deprecation notes"})
    if text and "changelog" not in lower:
        warnings.append({"source": "docs/deprecation-policy.md", "message": "policy should mention changelog updates"})
    return {
        "schema": SCHEMA,
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "compatibility_decision": compat.get("decision", ""),
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Review deprecation readiness")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    output = review(Path(args.root))
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
