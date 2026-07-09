#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


FIELD_APPLICABLE = "applicable"
FIELD_IDEMPOTENCY = "idempotency"
FIELD_NOT_APPLICABLE_REASON = "not_applicable_reason"
FIELD_REASON = "reason"
FIELD_ROLLBACK = "rollback"


DATA_MODEL_FIELDS = [FIELD_APPLICABLE, "entities", "field_rules", "ownership", "read_write_rules", "migration_strategy", "rollback_strategy"]
TABLE_SCHEMA_FIELDS = ["table", "field", "type", "nullable", "default", "migration", FIELD_ROLLBACK]
SYSTEM_SEQUENCE_FIELDS = [FIELD_APPLICABLE, "participants", "sequence", "timeout_retry", FIELD_IDEMPOTENCY, "consistency"]
MQ_INTERACTION_FIELDS = [
    FIELD_APPLICABLE,
    "producer",
    "consumer",
    "topic_or_queue",
    "trigger",
    "payload_fields",
    f"{FIELD_IDEMPOTENCY}_key",
    "retry_policy",
    "dead_letter_or_compensation",
    FIELD_NOT_APPLICABLE_REASON,
]
CACHE_STRATEGY_FIELDS = [FIELD_APPLICABLE, "decision", "key_design", "value_shape", "ttl", "invalidation", "consistency_risk", FIELD_REASON]
TRANSACTION_CONSISTENCY_FIELDS = [FIELD_APPLICABLE, "boundary", FIELD_IDEMPOTENCY, "compensation", FIELD_ROLLBACK, FIELD_NOT_APPLICABLE_REASON]
OBSERVABILITY_FIELDS = ["logs", "metrics", "traces", "alerts"]


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
                    "fields": DATA_MODEL_FIELDS,
                    "fallback_key": "data_model_missing",
                },
                {
                    "items": as_list(technical.get("table_schema_changes")),
                    "fields": TABLE_SCHEMA_FIELDS,
                    "fallback_key": "table_schema_missing",
                },
            ],
        },
        {
            "section_key": "system_sequence",
            "groups": [
                {
                    "items": [sequence],
                    "fields": SYSTEM_SEQUENCE_FIELDS,
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
                    "fields": MQ_INTERACTION_FIELDS,
                    "fallback_key": "mq_missing",
                }
            ],
        },
        {
            "section_key": "cache_strategy",
            "groups": [
                {
                    "items": [cache],
                    "fields": CACHE_STRATEGY_FIELDS,
                    "fallback_key": "cache_missing",
                }
            ],
        },
        {
            "section_key": "transaction_consistency",
            "groups": [
                {
                    "items": [tx],
                    "fields": TRANSACTION_CONSISTENCY_FIELDS,
                    "fallback_key": "transaction_missing",
                }
            ],
        },
        {
            "section_key": "observability_design",
            "groups": [
                {
                    "items": [obs],
                    "fields": OBSERVABILITY_FIELDS,
                    "fallback_key": "observability_missing",
                }
            ],
        },
    ]
