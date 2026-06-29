#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "codex-baseline-quality-v1"
REQUIRED = ["overview", "module_hints", "api_surface_ref", "config_surface_ref", "dependency_surface_ref", "test_hints", "risk_hints", "limitations", "human_followups"]
USER_ROOT_PATTERN = "/" + "Users"
PRIVATE_PATTERNS = [
    ("local_path", re.compile(rf"({re.escape(USER_ROOT_PATTERN)}/[^\s\"',}}]+|/home/[^\s\"',}}]+|[A-Za-z]:\\\\Users\\\\[^\s\"',}}]+)")),
    ("secret", re.compile(r"(?i)(password|secret|token|api[_-]?key)\s*[:=]\s*[^\s,}]+")),
    ("private_hostname", re.compile(r"(?i)\\b[a-z0-9.-]+\\.(internal|corp|local)\\b")),
]


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
    if data:
        shareable = {key: value for key, value in data.items() if key not in {"repo_root"}}
        rendered = json.dumps(shareable, ensure_ascii=False)
        for source, pattern in PRIVATE_PATTERNS:
            matches = sorted(set(match.group(0) for match in pattern.finditer(rendered)))[:5]
            if matches:
                blockers.append({"source": source, "message": "baseline contains private or sensitive content", "matches": matches})
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
