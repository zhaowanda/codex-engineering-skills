#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-security-policy-v1"
REQUIRED_TERMS = ["vulnerability", "supported versions", "private data", "secret", "privacy scan", "dependency", "response"]


def review(root: Path) -> dict[str, Any]:
    path = root / "SECURITY.md"
    text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    lower = text.lower()
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not text:
        blockers.append({"source": "SECURITY.md", "message": "SECURITY.md is required"})
    for term in REQUIRED_TERMS:
        if text and term not in lower:
            blockers.append({"source": "SECURITY.md", "message": f"missing security topic: {term}"})
    if text and "public issue" not in lower:
        warnings.append({"source": "SECURITY.md", "message": "policy should tell users not to disclose sensitive vulnerabilities in public issues"})
    return {
        "schema": SCHEMA,
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Review security policy readiness")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    output = review(Path(args.root))
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
