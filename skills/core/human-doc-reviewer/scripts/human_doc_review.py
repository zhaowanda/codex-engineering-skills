#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REQUIRED_TERMS = {
    "scope": ["scope", "范围"],
    "decision": ["decision", "决策", "方案"],
    "options": ["option", "alternative", "对比", "方案"],
    "risk": ["risk", "风险"],
    "evidence": ["evidence", "证据", "验证"],
    "rollback": ["rollback", "回滚"],
}


def review(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="ignore")
    lower = text.lower()
    blockers = []
    warnings = []
    if len(text.strip()) < 500:
        warnings.append({"source": "length", "message": "document is short; may lack substance"})
    for area, terms in REQUIRED_TERMS.items():
        if not any(term in lower or term in text for term in terms):
            warnings.append({"source": area, "message": f"{area} section or terms not found"})
    mac_user_root = "/" + "Users/"
    if mac_user_root in text or re.search(r"/home/[^/\s]+|[A-Za-z]:\\\\", text):
        blockers.append({"source": "local_path", "message": "local absolute path detected"})
    if re.search(r"(?i)(password|secret|token)\s*[:=]\s*['\"]?[^'\"\s]+", text):
        blockers.append({"source": "secret", "message": "possible secret detected"})
    return {
        "schema": "codex-human-doc-review-v1",
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Review human-readable document quality")
    parser.add_argument("--file", required=True)
    args = parser.parse_args()
    result = review(Path(args.file))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
