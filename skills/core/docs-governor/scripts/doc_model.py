#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def expert_design_sections(technical: dict[str, Any]) -> list[dict[str, Any]]:
    data_model = technical.get("data_model_design") if isinstance(technical.get("data_model_design"), dict) else {}
    sequence = technical.get("system_interaction_sequence") if isinstance(technical.get("system_interaction_sequence"), dict) else {}
    cache = technical.get("cache_strategy") if isinstance(technical.get("cache_strategy"), dict) else {}
    tx = technical.get("transaction_consistency") if isinstance(technical.get("transaction_consistency"), dict) else {}
    obs = technical.get("observability_design") if isinstance(technical.get("observability_design"), dict) else {}
    return [
        {
            "section_key": "data_model_schema",
            "groups": [
                {
                    "items": [data_model],
                    "fields": ["applicable", "entities", "field_rules", "ownership", "read_write_rules", "migration_strategy", "rollback_strategy"],
                    "fallback_key": "data_model_missing",
                },
                {
                    "items": as_list(technical.get("table_schema_changes")),
                    "fields": ["table", "field", "type", "nullable", "default", "migration", "rollback"],
                    "fallback_key": "table_schema_missing",
                },
            ],
        },
        {
            "section_key": "system_sequence",
            "groups": [
                {
                    "items": [sequence],
                    "fields": ["applicable", "participants", "sequence", "timeout_retry", "idempotency", "consistency"],
                    "fallback_key": "system_sequence_missing",
                }
            ],
            "diagram": "system_sequence",
        },
        {
            "section_key": "mq_interactions",
            "groups": [
                {
                    "items": as_list(technical.get("mq_interactions")),
                    "fields": ["applicable", "producer", "consumer", "topic_or_queue", "trigger", "payload_fields", "idempotency_key", "retry_policy", "dead_letter_or_compensation", "not_applicable_reason"],
                    "fallback_key": "mq_missing",
                }
            ],
        },
        {
            "section_key": "cache_strategy",
            "groups": [
                {
                    "items": [cache],
                    "fields": ["applicable", "decision", "key_design", "value_shape", "ttl", "invalidation", "consistency_risk", "reason"],
                    "fallback_key": "cache_missing",
                }
            ],
        },
        {
            "section_key": "transaction_consistency",
            "groups": [
                {
                    "items": [tx],
                    "fields": ["applicable", "boundary", "idempotency", "compensation", "rollback", "not_applicable_reason"],
                    "fallback_key": "transaction_missing",
                }
            ],
        },
        {
            "section_key": "observability_design",
            "groups": [
                {
                    "items": [obs],
                    "fields": ["logs", "metrics", "traces", "alerts"],
                    "fallback_key": "observability_missing",
                }
            ],
        },
    ]
