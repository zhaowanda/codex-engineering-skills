#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-configuration-readiness-v1"
CONFIG_TERMS = {
    "database": ["datasource", "jdbc", "database_url", "db_config", "数据库配置", "数据源"],
    "mq": ["mq_config", "queue_name", "topic_name", "kafka", "rabbit", "消息配置", "队列配置"],
    "email": ["smtp", "mail_host", "email_config", "邮件配置"],
    "sms": ["sms_provider", "sms_config", "短信配置"],
    "payment": ["payment_config", "payment_provider", "支付配置", "退款配置"],
    "callback": ["callback_url", "callback_secret", "webhook", "回调地址", "回调密钥"],
    "secret": ["secret", "token", "certificate", "cert", "密钥", "证书"],
    "feature_flag": ["feature_flag", "feature flag", "toggle", "灰度开关", "功能开关"],
}
CONFIG_KEYS = {
    "configuration",
    "configuration_items",
    "configuration_requirements",
    "runtime_configuration",
    "environment_variables",
    "deployment_impact",
    "deployment_topology",
    "provider_configuration",
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def text_of(*values: Any) -> str:
    return json.dumps(values, ensure_ascii=False).lower()


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def configuration_context(value: Any, key: str = "") -> list[Any]:
    rows: list[Any] = []
    key_lower = key.lower()
    if key_lower in CONFIG_KEYS or "config" in key_lower or "配置" in key_lower or "environment" in key_lower:
        rows.append(value)
    if isinstance(value, dict):
        for child_key, child in value.items():
            rows.extend(configuration_context(child, str(child_key)))
    elif isinstance(value, list):
        for child in value:
            rows.extend(configuration_context(child, key))
    return rows


def explicit_configuration_items(*docs: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for doc in docs:
        for key in ("configuration_items", "configuration_requirements", "runtime_configuration", "environment_variables"):
            for raw in as_list(doc.get(key)):
                if isinstance(raw, dict):
                    item = dict(raw)
                    item.setdefault("key", str(item.get("name") or item.get("type") or key))
                    item.setdefault("type", str(item.get("type") or "runtime"))
                    item.setdefault("required", True)
                    items.append(item)
    return items


def inferred_configuration_items(*docs: dict[str, Any]) -> list[dict[str, Any]]:
    context = text_of(*configuration_context(list(docs)))
    items: list[dict[str, Any]] = []
    for kind, terms in CONFIG_TERMS.items():
        if any(term in context for term in terms):
            items.append({
                "key": f"{kind}_configuration",
                "type": kind,
                "required": False,
                "owner": "",
                "environments": ["dev", "test", "staging", "production"],
                "secret_handling": "no secret values in artifacts; use secret manager or CI variables" if kind in {"secret", "callback"} else "not sensitive unless provider requires credentials",
                "default_strategy": "",
                "rollback_strategy": "",
                "validation_evidence": [],
                "source": "inferred_from_configuration_context",
            })
    return items


def normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    kind = str(item.get("type") or "runtime")
    return {
        "key": str(item.get("key") or item.get("name") or f"{kind}_configuration"),
        "type": kind,
        "required": bool(item.get("required", True)),
        "owner": str(item.get("owner") or ""),
        "environments": as_list(item.get("environments") or item.get("environment_scope") or ["dev", "test", "staging", "production"]),
        "secret_handling": str(item.get("secret_handling") or ("no secret values in artifacts; use secret manager or CI variables" if kind in {"secret", "callback"} else "not sensitive unless provider requires credentials")),
        "default_strategy": str(item.get("default_strategy") or item.get("default") or ""),
        "rollback_strategy": str(item.get("rollback_strategy") or item.get("rollback") or ""),
        "validation_evidence": as_list(item.get("validation_evidence")),
        "source": str(item.get("source") or "explicit_configuration_item"),
    }


def analyze(*docs: dict[str, Any]) -> dict[str, Any]:
    items_by_key: dict[str, dict[str, Any]] = {}
    for raw in [*explicit_configuration_items(*docs), *inferred_configuration_items(*docs)]:
        item = normalize_item(raw)
        items_by_key[item["key"]] = item
    items = list(items_by_key.values())
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for item in items:
        for key in ["owner", "default_strategy", "rollback_strategy"]:
            if item.get("required") is True and not item.get(key):
                blockers.append({"source": item["key"], "message": f"{key} is required"})
        if not item.get("validation_evidence"):
            warnings.append({"source": item["key"], "message": "validation evidence should be attached before release"})
    if not items:
        warnings.append({"source": "configuration_applicability", "message": "no runtime configuration change detected from explicit configuration context"})
    return {
        "schema": SCHEMA,
        "applicable": bool(items),
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
