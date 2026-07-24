#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


SUMMARY_CONTRACT_VERSION = "codex-workflow-summary-v1"

STAGE_SOURCE_GROUPS: dict[str, set[str]] = {
    "requirements_clarification": {"requirement_ingestion", "spec", "open_questions", "requirement_questions", "source_location_evidence", "source_location", "project_overlay"},
    "technical_design": {"domain_model_design", "architecture_framing", "technical_design", "api_contract_design", "data_model_design", "ui_ue_design", "ui_ue_review", "observability_design", "cross_repo_plan", "cross_repo_readiness"},
    "design_review": {"architecture_design", "design_review", "design_architecture_review", "harness_design"},
    "delivery_plan_review": {"delivery_plan", "delivery_plan_review", "test_design", "test_data_plan", "traceability_matrix", "profile_gate", "profile_artifact"},
    "docs_sync": {"docs_sync", "docs_quality", "docs_projection_state", "docs_git", "docs_manifest", "docs_root", "docs_source"},
    "git_edit_permit": {"git", "git_plan_baseline_summary", "edit_permit", "write_guard_snapshot"},
    "pre_push": {"post_change", "project_skill_index_sync", "pre_push_evidence", "git_binding"},
    "release": {"environment", "uat", "release_change", "release"},
}

STAGE_PRIORITY = [
    "requirements_clarification",
    "technical_design",
    "design_review",
    "delivery_plan_review",
    "docs_sync",
    "git_edit_permit",
    "pre_push",
    "release",
]


def primary_blocker_stage(blockers: list[dict[str, Any]], fallback: str = "") -> str:
    sources = [str(item.get("source") or "") for item in blockers if isinstance(item, dict)]
    for stage in STAGE_PRIORITY:
        names = STAGE_SOURCE_GROUPS[stage]
        if any(source in names or any(source.startswith(f"{name}.") for name in names) for source in sources):
            return stage
    return fallback or "unknown"


def partition_blockers(blockers: list[dict[str, Any]], primary_stage: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    primary_names = STAGE_SOURCE_GROUPS.get(primary_stage, set())
    primary: list[dict[str, Any]] = []
    secondary: list[dict[str, Any]] = []
    for item in blockers:
        source = str(item.get("source") or "")
        if source in primary_names or any(source.startswith(f"{name}.") for name in primary_names):
            primary.append(item)
        else:
            secondary.append(item)
    return primary, secondary


def summary_fields(
    blockers: list[dict[str, Any]],
    next_stage: str,
    next_action_type: str,
    next_command: str,
    primary_action: dict[str, Any] | None = None,
) -> dict[str, Any]:
    primary_stage = primary_blocker_stage(blockers, next_stage)
    primary_blockers, downstream_blockers = partition_blockers(blockers, primary_stage)
    return {
        "summary_contract_version": SUMMARY_CONTRACT_VERSION,
        "primary_blocker_stage": primary_stage,
        "primary_blockers": primary_blockers,
        "downstream_blockers": downstream_blockers,
        "next_action_type": next_action_type,
        "next_command": next_command,
        "primary_next_action": primary_action or {
            "action_type": next_action_type,
            "stage": next_stage,
            "summary": "",
            "command": next_command,
        },
    }
