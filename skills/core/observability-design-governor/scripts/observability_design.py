#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-observability-design-v1"


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def load_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def design(spec: dict[str, Any], technical: dict[str, Any] | None = None) -> dict[str, Any]:
    technical = technical or {}
    base = technical.get("observability_design") if isinstance(technical.get("observability_design"), dict) else {}
    text = json.dumps([spec, technical], ensure_ascii=False).lower()
    mq = any(token in text for token in ["mq", "topic", "queue", "consumer", "消息", "队列", "消费"])
    cache = any(token in text for token in ["cache", "redis", "缓存"])
    scheduled = any(token in text for token in ["cron", "schedule", "job", "task", "定时", "任务", "手搓"])
    cross_system = any(token in text for token in ["api", "service", "接口", "调用", "跨系统"])
    return {
        "schema": SCHEMA,
        "doc_id": spec.get("doc_id") or technical.get("doc_id"),
        "title": spec.get("title") or technical.get("title"),
        "decision": "pass",
        "logs": base.get("logs") or ["trace_id", "business_id", "entrypoint", "operation", "result", "failure_reason"],
        "metrics": base.get("metrics") or ["request_count", "error_count", "latency_p95"],
        "traces": base.get("traces") or ["entrypoint", "service_call", "data_operation"],
        "alerts": base.get("alerts") or ["error_rate_threshold", "latency_threshold"],
        "dashboards": ["business success rate", "technical error rate", "latency and dependency health"],
        "mq_observability": ["consumer_lag", "retry_count", "dead_letter_count", "consume_latency"] if mq else [],
        "scheduled_task_observability": ["last_success_time", "duration", "failure_count", "manual_replay_result"] if scheduled else [],
        "cache_observability": ["hit_rate", "miss_rate", "rebuild_latency", "stale_read_count"] if cache else [],
        "cross_system_observability": ["downstream_error_count", "timeout_count", "retry_count", "circuit_breaker_state"] if cross_system else [],
        "data_safety": ["do not log secrets/tokens", "mask sensitive payload values", "log identifiers rather than full business payloads"],
        "post_release_checks": ["sample logs contain trace_id/business_id", "metrics increase on test traffic", "alerts have owner and action", "rollback signal is observable"],
        "blockers": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate observability design")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--technical-design")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = design(load_json(Path(args.spec)), load_json(Path(args.technical_design)) if args.technical_design else {})
    write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
