#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-configuration-readiness-v1"
CONFIG_TERMS = {
    "database": ["database", "db", "sql", "数据库"],
    "mq": ["mq", "queue", "topic", "kafka", "rabbit", "消息"],
    "email": ["email", "mail", "smtp", "邮件"],
    "sms": ["sms", "短信"],
    "payment": ["payment", "pay", "refund", "callback", "支付", "退款", "回调"],
    "secret": ["secret", "token", "certificate", "cert", "key", "密钥", "证书"],
    "feature_flag": ["feature flag", "toggle", "灰度", "开关"],
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def text_of(*values: Any) -> str:
    return json.dumps(values, ensure_ascii=False).lower()


def analyze(*docs: dict[str, Any]) -> dict[str, Any]:
    text = text_of(*docs)
    items: list[dict[str, Any]] = []
    for kind, terms in CONFIG_TERMS.items():
        if any(term in text for term in terms):
            items.append({
                "key": f"{kind}_configuration",
                "type": kind,
                "required": True,
                "owner": "",
                "environments": ["dev", "test", "staging", "production"],
                "secret_handling": "no secret values in artifacts; use secret manager or CI variables" if kind == "secret" else "not sensitive unless provider requires credentials",
                "default_strategy": "",
                "rollback_strategy": "",
                "validation_evidence": [],
            })
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for item in items:
        for key in ["owner", "default_strategy", "rollback_strategy"]:
            if not item.get(key):
                blockers.append({"source": item["key"], "message": f"{key} is required"})
        if not item.get("validation_evidence"):
            warnings.append({"source": item["key"], "message": "validation evidence should be attached before release"})
    return {
        "schema": SCHEMA,
        "decision": "blocked" if blockers else "ready",
        "configuration_items": items,
        "blockers": blockers,
        "warnings": warnings,
        "next_action": "Fill owner/default/rollback for configuration items." if blockers else "Attach environment validation evidence before release.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze configuration readiness")
    parser.add_argument("cmd", choices=["analyze"])
    parser.add_argument("--spec", required=True)
    parser.add_argument("--technical-design", required=True)
    parser.add_argument("--architecture-design", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = analyze(load_json(Path(args.spec)), load_json(Path(args.technical_design)), load_json(Path(args.architecture_design)))
    write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
