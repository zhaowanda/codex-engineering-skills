#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-performance-review-v1"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def text_of(*values: Any) -> str:
    return json.dumps(values, ensure_ascii=False).lower()


def design_review(*docs: dict[str, Any]) -> dict[str, Any]:
    text = text_of(*docs)
    evidence_plan: list[dict[str, Any]] = []
    risk = "low"
    if any(term in text for term in ["api", "endpoint", "接口"]):
        evidence_plan.append({"area": "api", "evidence_types": ["api_timing"], "required": True})
    if any(term in text for term in ["sql", "query", "database", "db", "数据库"]):
        evidence_plan.append({"area": "database", "evidence_types": ["sql_explain", "query_count"], "required": True})
        risk = "medium"
    if any(term in text for term in ["loop", "batch", "export", "report", "批量", "导出", "报表"]):
        evidence_plan.append({"area": "throughput", "evidence_types": ["volume_runtime", "memory"], "required": True})
        risk = "medium"
    if any(term in text for term in ["frontend", "browser", "page", "ui"]):
        evidence_plan.append({"area": "frontend", "evidence_types": ["frontend_acceptance", "bundle_or_runtime"], "required": True})
    if any(term in text for term in ["mq", "queue", "topic", "kafka"]):
        evidence_plan.append({"area": "mq", "evidence_types": ["throughput", "consumer_lag"], "required": True})
        risk = "high"
    decision = "needs_evidence" if evidence_plan else "pass"
    return {
        "schema": SCHEMA,
        "decision": decision,
        "risk_level": risk,
        "evidence_plan": evidence_plan,
        "blockers": [],
        "warnings": [] if evidence_plan else [{"source": "performance", "message": "no performance-sensitive signals detected"}],
        "release_blockers": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate performance design review")
    parser.add_argument("cmd", choices=["design"])
    parser.add_argument("--spec", required=True)
    parser.add_argument("--technical-design", required=True)
    parser.add_argument("--architecture-design", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = design_review(load_json(Path(args.spec)), load_json(Path(args.technical_design)), load_json(Path(args.architecture_design)))
    write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
