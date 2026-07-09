from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


docs_i18n = load_module("docs_i18n", ROOT / "skills/core/docs-governor/scripts/docs_i18n.py")
doc_model = load_module("doc_model", ROOT / "skills/core/docs-governor/scripts/doc_model.py")
docs_governor = load_module("docs_governor", ROOT / "skills/core/docs-governor/scripts/docs_governor.py")


def test_i18n_renders_status_without_translating_code_identifiers() -> None:
    value = {
        "table": "renewal_order",
        "field": "renewal_month",
        "type": "needs_confirmation",
        "rollback": "code rollback plus schema/data rollback plan if migration is applied",
    }
    rendered = docs_i18n.render_value(value, "zh")
    assert "表=renewal_order" in rendered
    assert "字段=renewal_month" in rendered
    assert "需结合代码和数据库核对" in rendered
    assert "如执行迁移" in rendered
    assert "{\"" not in rendered


def test_expert_design_sections_are_language_neutral() -> None:
    technical = {
        "data_model_design": {"applicable": True},
        "table_schema_changes": [{"table": "renewal_order", "field": "renewal_month", "type": "needs_confirmation"}],
        "system_interaction_sequence": {"applicable": False, "reason": "not_applicable"},
        "mq_interactions": [{"applicable": False}],
        "cache_strategy": {"applicable": True, "decision": "no_cache"},
        "transaction_consistency": {"applicable": True, "boundary": "owner service/repository transaction boundary must be confirmed"},
        "observability_design": {"logs": ["trace_id"], "metrics": ["latency_p95"]},
    }
    sections = doc_model.expert_design_sections(technical)
    assert [section["section_key"] for section in sections] == [
        "data_model_schema",
        "system_sequence",
        "mq_interactions",
        "cache_strategy",
        "transaction_consistency",
        "observability_design",
    ]
    zh_doc = docs_governor.render_expert_technical_sections(technical, "zh")
    en_doc = docs_governor.render_expert_technical_sections(technical, "en")
    assert "### 数据模型与表结构" in zh_doc
    assert "### Data Model And Table Schema" in en_doc
    assert "renewal_order" in zh_doc
    assert "renewal_order" in en_doc
    assert "needs_confirmation" not in zh_doc
    assert "{\"" not in zh_doc
