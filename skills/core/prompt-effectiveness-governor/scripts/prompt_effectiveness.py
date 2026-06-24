#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-prompt-effectiveness-v1"
BASE_TERMS = ["stop", "evidence", "boundary"]
SCENARIO_TERMS = {
    "one-line-request.md": ["artifact", "question", "source"],
    "long-prd.md": ["design", "acceptance", "configuration"],
    "bugfix.md": ["reproduce", "git", "test"],
    "code-review.md": ["finding", "severity", "missing evidence"],
    "release-readiness.md": ["rollback", "no_go", "release"],
    "low-rework-implementation.md": ["design", "git", "token", "allowed files"],
}


def review(root: Path) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    prompt_root = root / "prompts"
    files = sorted(prompt_root.glob("*.md"))
    if not files:
        blockers.append({"source": "prompts", "message": "prompt files are required"})
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        expected = BASE_TERMS + SCENARIO_TERMS.get(path.name, [])
        missing = [term for term in expected if term not in text]
        if missing:
            blockers.append({"source": path.name, "message": "prompt missing effectiveness controls", "missing": missing})
        if len(text) < 300:
            warnings.append({"source": path.name, "message": "prompt may be too short to guide behavior"})
    return {
        "schema": SCHEMA,
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "prompt_count": len(files),
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Review prompt effectiveness")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    output = review(Path(args.root))
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
