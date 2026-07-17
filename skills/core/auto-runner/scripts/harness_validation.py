#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
from pathlib import Path
from typing import Any

SCHEMA = "codex-harness-checkpoint-v2"
LEGACY_SCHEMAS = ["codex-harness-checkpoint-v1", "codex-harness-validation-v1"]
CHECKPOINTS = ("source_location", "design", "post_implementation", "pre_push")
DEFAULT_BUDGETS = {
    "project_understanding/evidence_bundle.json": 100_000,
    "spec.json": 300_000,
    "technical_design.json": 300_000,
    "architecture_design.json": 300_000,
    "test_design.json": 300_000,
    "delivery_plan.json": 300_000,
    "design_architecture_review.json": 500_000,
    "delivery_plan_review.json": 500_000,
}
EDIT_KEYS = {"allowed_files", "files_to_edit", "modify_files", "implementation_files"}
OWNER_KEYS = {"owner_file", "selected_entrypoint", "primary_file"}
CONFIDENCE = {"low": 0, "medium": 1, "high": 2}
GENERIC_RELEVANCE_TERMS = {
    "add", "change", "device", "feature", "fix", "page", "service", "update",
    "api", "http", "true", "false", "query", "list", "detail", "paging",
    "修改", "功能", "优化", "页面", "设备", "需求", "用户", "接口", "查询",
}


def load_agent_runtime_module() -> Any:
    path = Path(__file__).with_name("agent_runtime.py")
    spec = importlib.util.spec_from_file_location("harness_agent_runtime", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AGENT_RUNTIME = load_agent_runtime_module()


def load_docs_governor_module() -> Any:
    path = Path(__file__).resolve().parents[2] / "docs-governor/scripts/docs_governor.py"
    spec = importlib.util.spec_from_file_location("harness_docs_governor", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DOCS_GOVERNOR = load_docs_governor_module()
RUNTIME_CHECKPOINTS = {
    "source_location": "intake",
    "design": "design",
    "post_implementation": "post_implementation",
    "pre_push": "pre_push",
}
HARNESS_INPUTS = {
    "source_location": ["runtime/checkpoints/intake.json", "project_understanding/code_index.json", "project_understanding/source_location_evidence.json", "project_understanding/evidence_bundle.json"],
    "design": ["runtime/checkpoints/design.json", "spec.json", "project_understanding/evidence_bundle.json", "technical_design.json", "architecture_design.json", "delivery_plan.json", "delivery_plan_review.json"],
    "post_implementation": ["runtime/checkpoints/post_implementation.json", "delivery_plan.json", "implementation_completion_gate.json", "post_change_implementation_report.json", "diff_impact.json"],
    "pre_push": ["runtime/checkpoints/pre_push.json", "post_change_implementation_report.json", "post_implementation_traceability_matrix.json", "test_evidence_gate.json", "code_review_gate.json"],
}


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def read_text_if_exists(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    except Exception:
        return ""


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [] if not inner else [parse_scalar(item) for item in inner.split(",")]
    value = value.strip('"').strip("'")
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    try:
        return int(value)
    except ValueError:
        return value


def load_restricted_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    lines = [
        (len(raw) - len(raw.lstrip(" ")), raw.strip())
        for raw in path.read_text(encoding="utf-8").splitlines()
        if raw.strip() and not raw.lstrip().startswith("#")
    ]

    def parse_block(index: int, indent: int) -> tuple[Any, int]:
        if index >= len(lines):
            return {}, index
        container: Any = [] if lines[index][1].startswith("- ") else {}
        while index < len(lines):
            current_indent, text = lines[index]
            if current_indent != indent:
                break
            if text.startswith("- "):
                if not isinstance(container, list):
                    break
                container.append(parse_scalar(text[2:]))
                index += 1
                continue
            if not isinstance(container, dict) or ":" not in text:
                break
            key, value = text.split(":", 1)
            index += 1
            if value.strip():
                container[key.strip()] = parse_scalar(value)
            elif index < len(lines) and lines[index][0] > indent:
                child, index = parse_block(index, lines[index][0])
                container[key.strip()] = child
            else:
                container[key.strip()] = {}
        return container, index

    parsed, _ = parse_block(0, lines[0][0] if lines else 0)
    return parsed if isinstance(parsed, dict) else {}


def values_for_keys(value: Any, keys: set[str]) -> list[str]:
    result: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in keys:
                candidates = child if isinstance(child, list) else [child]
                for candidate in candidates:
                    if isinstance(candidate, str) and candidate.strip():
                        result.append(candidate.strip())
                    elif isinstance(candidate, dict):
                        for nested_key in ("path", "file"):
                            if candidate.get(nested_key):
                                result.append(str(candidate[nested_key]).strip())
            result.extend(values_for_keys(child, keys))
    elif isinstance(value, list):
        for child in value:
            result.extend(values_for_keys(child, keys))
    return result


def normalize_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def is_safe_relative_path(value: str) -> bool:
    path = Path(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts


def planned_new_paths(value: Any) -> set[str]:
    result: set[str] = set()
    if isinstance(value, dict):
        marker = str(value.get("status") or value.get("role") or "").lower()
        if marker in {"planned_new", "new", "create"}:
            path = str(value.get("path") or value.get("file") or "").strip()
            if path:
                result.add(normalize_path(path))
        for child in value.values():
            result.update(planned_new_paths(child))
    elif isinstance(value, list):
        for child in value:
            result.update(planned_new_paths(child))
    return result


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def nested_policy(policy: dict[str, Any], key: str) -> dict[str, Any]:
    value = policy.get(key)
    return value if isinstance(value, dict) else {}


def add_blocker(blockers: list[dict[str, Any]], source: str, message: str, **details: Any) -> None:
    blockers.append({"source": source, "message": message, **details})


def requirement_context(artifact_dir: Path) -> str:
    parts = [
        read_text_if_exists(artifact_dir / "requirement.normalized.txt"),
        read_text_if_exists(artifact_dir / "requirement.md"),
        json.dumps(read_json(artifact_dir / "spec.json"), ensure_ascii=False),
    ]
    return "\n".join(part for part in parts if part).lower()


def relevance_terms(anchor: dict[str, Any]) -> list[str]:
    raw_terms: list[str] = []
    for key in ("matched_symbols", "matched_contract_terms", "matched_requirement_terms"):
        value = anchor.get(key)
        if isinstance(value, list):
            raw_terms.extend(str(item) for item in value)
    for item in anchor.get("evidence_chain", []) if isinstance(anchor.get("evidence_chain"), list) else []:
        if isinstance(item, dict) and item.get("term"):
            raw_terms.append(str(item["term"]))
    terms: list[str] = []
    for term in raw_terms:
        normalized = term.strip().lower()
        if not normalized or normalized in GENERIC_RELEVANCE_TERMS:
            continue
        if normalized not in terms:
            terms.append(normalized)
    return terms


def path_tokens(path: str) -> list[str]:
    basename = Path(path).name.lower()
    stem = Path(path).stem.lower()
    split = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", Path(path).stem).lower()
    tokens = [basename, stem, *re.split(r"[^a-z0-9\u4e00-\u9fff]+", split)]
    return [token for token in tokens if len(token) >= 4 and token not in GENERIC_RELEVANCE_TERMS]


def anchor_requirement_relevance(anchor: dict[str, Any], requirement_lower: str) -> tuple[bool, list[str]]:
    if not requirement_lower:
        return True, []
    matched: list[str] = []
    for term in [*path_tokens(str(anchor.get("path") or "")), *relevance_terms(anchor)]:
        if term and term in requirement_lower and term not in matched:
            matched.append(term)
    return bool(matched), matched


def artifact_budget_checkpoint(artifact_dir: Path, budgets: dict[str, int]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    blockers: list[dict[str, Any]] = []
    sizes: list[dict[str, Any]] = []
    for name, maximum in budgets.items():
        path = artifact_dir / name
        if not path.exists() and name == "project_understanding/evidence_bundle.json":
            path = artifact_dir / "evidence_bundle.json"
        if not path.exists():
            continue
        size = path.stat().st_size
        sizes.append({"artifact": name, "bytes": size, "max_bytes": maximum, "within_budget": size <= maximum})
        if size > maximum:
            add_blocker(blockers, "artifact_budget", f"artifact is {size} bytes; budget is {maximum}", artifact=name)
    return blockers, sizes


def source_location_checkpoint(
    artifact_dir: Path,
    repo: Path | None,
    policy: dict[str, Any],
) -> dict[str, Any]:
    bundle_path = artifact_dir / "project_understanding/evidence_bundle.json"
    index_path = artifact_dir / "project_understanding/code_index.json"
    if not bundle_path.exists():
        bundle_path = artifact_dir / "evidence_bundle.json"
        index_path = artifact_dir / "code_index.json"
    if not bundle_path.exists():
        return {"checkpoint": "source_location", "applicable": False, "decision": "pass", "blockers": [], "metrics": {"anchors": 0}}

    bundle = read_json(bundle_path)
    configured_repo = repo or (Path(str(bundle["repo_root"])) if bundle.get("repo_root") else None)
    anchors = [item for item in bundle.get("anchors", []) if isinstance(item, dict)]
    modify = [item for item in anchors if item.get("role") == "confirmed_modify"]
    references = [item for item in anchors if item.get("role") == "confirmed_reference"]
    minimum = str(policy.get("minimum_confidence") or "medium")
    blockers: list[dict[str, Any]] = []
    checked: list[dict[str, Any]] = []
    requirement_lower = requirement_context(artifact_dir)
    if not modify:
        add_blocker(blockers, "source_location", "no confirmed modify anchor exists")
    for anchor in modify:
        relative = normalize_path(str(anchor.get("path") or ""))
        confidence = str(anchor.get("confidence") or "low")
        anchor_repo_root = str(anchor.get("repo_root") or anchor.get("repository_root") or "").strip()
        anchor_repo = str(anchor.get("repo") or anchor.get("repository") or "").strip()
        if not relative:
            add_blocker(blockers, "source_location", "confirmed modify anchor has no path")
            continue
        if not is_safe_relative_path(relative):
            add_blocker(blockers, "source_location", "confirmed modify anchor is not a safe relative path", path=relative)
            continue
        if CONFIDENCE.get(confidence, -1) < CONFIDENCE.get(minimum, 1):
            add_blocker(blockers, "source_location", "anchor confidence is below policy", path=relative, confidence=confidence, minimum=minimum)
        row: dict[str, Any] = {"path": relative, "confidence": confidence}
        relevant, matched_relevance = anchor_requirement_relevance(anchor, requirement_lower)
        row["requirement_relevance_terms"] = matched_relevance
        if policy.get("require_requirement_relevance", True) and not relevant:
            add_blocker(
                blockers,
                "source_location",
                "confirmed modify anchor is not supported by requirement text",
                path=relative,
                matched_symbols=anchor.get("matched_symbols", []),
                matched_contract_terms=anchor.get("matched_contract_terms", []),
            )
        if configured_repo:
            configured_resolved = configured_repo.resolve()
            if anchor_repo_root:
                anchor_root = Path(anchor_repo_root).expanduser()
                try:
                    anchor_resolved = anchor_root.resolve()
                except OSError:
                    anchor_resolved = anchor_root
                if anchor_resolved != configured_resolved:
                    row["repo_mismatch"] = {"anchor_repo_root": str(anchor_resolved), "configured_repo": str(configured_resolved), "anchor_repo": anchor_repo}
                    add_blocker(
                        blockers,
                        "source_location",
                        "confirmed modify anchor belongs to a different repository",
                        path=relative,
                        anchor_repo=anchor_repo,
                        anchor_repo_root=str(anchor_resolved),
                        configured_repo=str(configured_resolved),
                    )
                    checked.append(row)
                    continue
            source = configured_repo / relative
            row["exists"] = source.is_file()
            if not source.is_file():
                add_blocker(blockers, "source_location", "confirmed modify path does not exist", path=relative)
            else:
                actual_digest = sha256(source)
                expected_digest = str(anchor.get("source_digest") or "")
                row["digest_matches"] = bool(expected_digest and expected_digest == actual_digest)
                if policy.get("require_source_digest", True) and not row["digest_matches"]:
                    add_blocker(blockers, "source_location", "source digest is missing or stale", path=relative)
        checked.append(row)

    index = read_json(index_path)
    index_revision = str(index.get("source_revision") or "")
    current_revision = git_head(configured_repo) if configured_repo else ""
    if policy.get("require_fresh_index", True) and index and current_revision and index_revision != current_revision:
        add_blocker(blockers, "code_index", "code index source revision does not match repository HEAD", index_revision=index_revision, current_revision=current_revision)
    return {
        "checkpoint": "source_location",
        "applicable": True,
        "decision": "block" if blockers else "pass",
        "blockers": blockers,
        "metrics": {"anchors": len(anchors), "confirmed_modify": len(modify), "confirmed_reference": len(references)},
        "repository": str(configured_repo or ""),
        "index_revision": index_revision,
        "current_revision": current_revision,
        "checked_anchors": checked,
    }


def applicability_areas(spec: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for item in spec.get("impact_applicability", []):
        if isinstance(item, dict) and item.get("status") == "required" and item.get("area"):
            result.add(str(item["area"]).lower())
    for item in spec.get("impacts", []):
        if isinstance(item, str):
            result.add(item.lower())
        elif isinstance(item, dict) and item.get("area"):
            result.add(str(item["area"]).lower())
    return result


def design_checkpoint(artifact_dir: Path, policy: dict[str, Any], budgets: dict[str, int]) -> dict[str, Any]:
    blockers, sizes = artifact_budget_checkpoint(artifact_dir, budgets)
    technical = read_json(artifact_dir / "technical_design.json")
    architecture = read_json(artifact_dir / "architecture_design.json")
    plan = read_json(artifact_dir / "delivery_plan.json")
    spec = read_json(artifact_dir / "spec.json")
    bundle_path = artifact_dir / "project_understanding/evidence_bundle.json"
    if not bundle_path.exists():
        bundle_path = artifact_dir / "evidence_bundle.json"
    bundle = read_json(bundle_path)
    scope_model = spec.get("scope_model") if isinstance(spec.get("scope_model"), dict) else {}
    scoped_modify = {normalize_path(str(item)) for item in scope_model.get("modify", []) if str(item).strip()}
    scoped_references = {normalize_path(str(item)) for item in scope_model.get("reference_only", []) if str(item).strip()}
    scoped_forbidden = {normalize_path(str(item)) for item in scope_model.get("forbidden", []) if str(item).strip()}
    modify = {
        normalize_path(str(item.get("path") or ""))
        for item in bundle.get("anchors", [])
        if isinstance(item, dict) and item.get("role") == "confirmed_modify"
    }
    references = {
        normalize_path(str(item.get("path") or ""))
        for item in bundle.get("anchors", [])
        if isinstance(item, dict) and item.get("role") == "confirmed_reference"
    }
    if scoped_modify:
        modify = {item for item in scoped_modify if Path(item).suffix}
    references.update(item for item in scoped_references if Path(item).suffix)
    checked_paths: list[dict[str, str]] = []
    planned_new = planned_new_paths([technical, architecture, plan])
    if modify:
        for name, data in [("technical_design.json", technical), ("architecture_design.json", architecture), ("delivery_plan.json", plan)]:
            keys = EDIT_KEYS | (OWNER_KEYS if name != "delivery_plan.json" else set())
            for raw_path in values_for_keys(data, keys):
                path = normalize_path(raw_path)
                if not path or not Path(path).suffix:
                    continue
                checked_paths.append({"artifact": name, "path": path})
                if not is_safe_relative_path(path):
                    add_blocker(blockers, "evidence_consistency", "implementation target is not a safe relative path", artifact=name, path=path)
                elif path in references:
                    add_blocker(blockers, "evidence_consistency", "reference-only anchor is used as an implementation target", artifact=name, path=path)
                elif path not in planned_new and path not in modify and not any(path.startswith(prefix.rstrip("/") + "/") for prefix in modify):
                    add_blocker(blockers, "evidence_consistency", "implementation target is not backed by a confirmed modify anchor", artifact=name, path=path)
                if path in scoped_forbidden:
                    add_blocker(blockers, "scope_consistency", "forbidden path is used as an implementation target", artifact=name, path=path)

    repo_impact = spec.get("repo_impact_map") if isinstance(spec.get("repo_impact_map"), dict) else {}
    repo_names = {str(item.get("name") or "").strip() for item in repo_impact.get("repos", []) if isinstance(item, dict) and str(item.get("name") or "").strip()}
    if repo_impact.get("multi_repo_required") is True and len(repo_names) < 2:
        add_blocker(blockers, "repository_scope", "multi_repo_required=true requires at least two concrete repositories", repositories=sorted(repo_names))
    if bundle.get("stale_references"):
        add_blocker(blockers, "project_overlay", "project overlay contains stale references", stale_references=bundle.get("stale_references"))

    process_flow = technical.get("process_flow")
    if policy.get("require_process_flow", True) and not process_flow:
        add_blocker(blockers, "design_completeness", "technical design is missing process_flow")
    if process_flow and policy.get("require_process_flow_diagram", True) and not str(technical.get("process_flow_diagram") or "").strip():
        add_blocker(blockers, "design_completeness", "technical design is missing process_flow_diagram")
    impacts = applicability_areas(spec)
    sequence_impacts = {str(item).lower() for item in policy.get("sequence_impacts", ["api", "cross_repo", "integration", "business_flow"])}
    sequence = technical.get("system_interaction_sequence")
    if impacts & sequence_impacts:
        if not isinstance(sequence, dict) or sequence.get("applicable") is not True or not sequence.get("participants") or not sequence.get("sequence"):
            add_blocker(blockers, "design_completeness", "applicable cross-component change requires a populated system interaction sequence", impacts=sorted(impacts & sequence_impacts))
        if isinstance(sequence, dict) and sequence.get("applicable") is True and policy.get("require_system_sequence_diagram", True) and not str(technical.get("system_sequence_diagram") or "").strip():
            add_blocker(blockers, "design_completeness", "technical design is missing system_sequence_diagram")
        if not architecture.get("integration_sequence"):
            add_blocker(blockers, "design_completeness", "architecture design is missing integration_sequence")
        elif policy.get("require_integration_sequence_diagram", True) and not str(architecture.get("integration_sequence_diagram") or "").strip():
            add_blocker(blockers, "design_completeness", "architecture design is missing integration_sequence_diagram")
    if isinstance(sequence, dict) and sequence.get("applicable") is True:
        participants = {str(item) for item in sequence.get("participants", []) if str(item).strip()}
        for index, edge in enumerate(sequence.get("sequence", [])):
            if not isinstance(edge, dict):
                add_blocker(blockers, "design_semantics", "sequence entry must be an object", index=index)
                continue
            missing = [key for key in ("from", "to", "action", "success", "failure") if not str(edge.get(key) or "").strip()]
            if missing:
                add_blocker(blockers, "design_semantics", "sequence entry is incomplete", index=index, missing=missing)
            if edge.get("from") not in participants or edge.get("to") not in participants:
                add_blocker(blockers, "design_semantics", "sequence edge references an undeclared participant", index=index)
    state_impacts = {str(item).lower() for item in policy.get("state_impacts", ["state", "status", "workflow", "business_flow"])}
    if impacts & state_impacts and not (technical.get("state_machine") or spec.get("state_machine")):
        add_blocker(blockers, "design_completeness", "stateful change requires a state machine", impacts=sorted(impacts & state_impacts))
    return {
        "checkpoint": "design",
        "applicable": True,
        "decision": "block" if blockers else "pass",
        "blockers": blockers,
        "metrics": {"process_flows": len(process_flow or []), "checked_paths": len(checked_paths), "applicability_areas": sorted(impacts), "scope_roles": len(scope_model.get("roles", []))},
        "artifact_sizes": sizes,
        "evidence_summary": {
            "confirmed_modify": sorted(modify),
            "confirmed_reference": sorted(references),
            "planned_new": sorted(planned_new),
        },
        "checked_paths": checked_paths,
    }


def post_implementation_checkpoint(artifact_dir: Path) -> dict[str, Any]:
    implementation = read_json(artifact_dir / "implementation_completion_gate.json")
    plan = read_json(artifact_dir / "delivery_plan.json")
    spec = read_json(artifact_dir / "spec.json")
    design_change = read_json(artifact_dir / "design_change.json")
    blockers: list[dict[str, Any]] = []
    changed = {normalize_path(str(item)) for item in implementation.get("changed_files", []) if str(item).strip()}
    allowed = {
        normalize_path(str(item))
        for task in plan.get("repo_tasks", [])
        if isinstance(task, dict) and task.get("role", "modify") == "modify"
        for item in task.get("allowed_files", [])
        if str(item).strip()
    }
    if not implementation:
        add_blocker(blockers, "implementation", "implementation completion evidence is missing")
    elif implementation.get("decision") != "pass":
        add_blocker(blockers, "implementation", "implementation completion evidence has not passed")
    if not changed:
        add_blocker(blockers, "plan_to_diff", "no changed files are recorded")
    if plan and not allowed:
        add_blocker(blockers, "plan_to_diff", "delivery plan has no allowed files")
    out_of_scope = sorted(path for path in changed if allowed and not any(path == item or path.startswith(item.rstrip("/") + "/") for item in allowed))
    if out_of_scope:
        add_blocker(blockers, "plan_to_diff", "changed files are outside delivery plan scope", files=out_of_scope)
    scope_model = spec.get("scope_model") if isinstance(spec.get("scope_model"), dict) else {}
    protected = {
        normalize_path(str(item))
        for role in ("reference_only", "contract_confirm_only", "forbidden")
        for item in scope_model.get(role, [])
        if str(item).strip() and Path(str(item)).suffix
    }
    protected_changes = sorted(changed & protected)
    approved_change = design_change.get("decision") in {"approved", "pass"} and bool(design_change.get("scope_changes"))
    if protected_changes and not approved_change:
        add_blocker(blockers, "post_change_drift", "protected scope changed without an approved design_change.json", files=protected_changes)
    return {
        "checkpoint": "post_implementation",
        "applicable": True,
        "decision": "block" if blockers else "pass",
        "blockers": blockers,
        "metrics": {"changed_files": len(changed), "allowed_files": len(allowed), "out_of_scope": len(out_of_scope), "protected_changes": len(protected_changes)},
        "changed_files": sorted(changed),
        "allowed_files": sorted(allowed),
    }


def pre_push_checkpoint(
    artifact_dir: Path,
    repo: Path | None,
    expected_head: str = "",
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or {}
    blockers: list[dict[str, Any]] = []
    post_change = read_json(artifact_dir / "post_change_implementation_report.json")
    traceability = read_json(artifact_dir / "post_implementation_traceability_matrix.json")
    tests = read_json(artifact_dir / "test_evidence_gate.json")
    review = read_json(artifact_dir / "code_review_gate.json")
    post_implementation_harness = read_json(artifact_dir / "harness/post_implementation.json")
    current_head = git_head(repo) if repo else ""
    for name, artifact, accepted in [
        ("post_change", post_change, {"pass", "ready"}),
        ("traceability", traceability, {"pass", "warn"}),
        ("test", tests, {"pass", "ready"}),
        ("review", review, {"pass", "approve", "approved"}),
        ("post_implementation_harness", post_implementation_harness, {"pass"}),
    ]:
        if not artifact or artifact.get("decision") not in accepted:
            add_blocker(blockers, "pre_push", f"{name} evidence is missing or not accepted")
    requirements = post_change.get("project_skill_index_requirements") if isinstance(post_change, dict) else {}
    if isinstance(requirements, dict) and requirements.get("required") and requirements.get("status") not in {"satisfied", "waived"}:
        add_blocker(blockers, "project_skill_index_sync", "project skill index synchronization is not satisfied")
    bound_head = expected_head or str(tests.get("git_head") or tests.get("git_sha") or "")
    if repo and policy.get("require_commit_bound_test_evidence", True) and not bound_head:
        add_blocker(blockers, "git_binding", "test evidence does not declare git_head or git_sha")
    if repo and bound_head and current_head != bound_head:
        add_blocker(blockers, "git_binding", "test evidence is bound to a different commit", evidence_head=bound_head, current_head=current_head)
    docs_binding = post_change.get("docs_binding") if isinstance(post_change.get("docs_binding"), dict) else {}
    docs_validation: dict[str, Any] = {}
    docs_root_value = str(docs_binding.get("docs_root") or "")
    docs_doc_id = str(docs_binding.get("doc_id") or "")
    if docs_root_value and docs_doc_id:
        docs_validation = DOCS_GOVERNOR.validate(
            Path(docs_root_value),
            docs_doc_id,
            require_git=True,
            require_git_sync=policy.get("require_docs_repo_sync", True),
        )
        blockers.extend(
            {"source": "docs_sync", "message": str(item.get("message") or "delivery docs validation failed")}
            for item in docs_validation.get("blockers", [])
        )
    return {
        "checkpoint": "pre_push",
        "applicable": True,
        "decision": "block" if blockers else "pass",
        "blockers": blockers,
        "metrics": {"required_evidence": 5, "accepted_evidence": 5 - sum(1 for item in blockers if item["source"] == "pre_push")},
        "current_head": current_head,
        "evidence_head": bound_head,
        "docs_validation": docs_validation,
    }


def runtime_binding(artifact_dir: Path, harness_checkpoint: str) -> dict[str, Any]:
    runtime_name = RUNTIME_CHECKPOINTS[harness_checkpoint]
    checkpoint_path = artifact_dir / "runtime/checkpoints" / f"{runtime_name}.json"
    checkpoint_data = read_json(checkpoint_path)
    verification = AGENT_RUNTIME.verify(artifact_dir)
    blockers = list(verification.get("blockers", []))
    if checkpoint_data.get("schema") != AGENT_RUNTIME.CHECKPOINT_SCHEMA:
        add_blocker(blockers, "agent_runtime", "required runtime checkpoint is missing or invalid", checkpoint=runtime_name)
    elif checkpoint_data.get("decision") != "pass":
        add_blocker(blockers, "agent_runtime", "required runtime checkpoint has not passed", checkpoint=runtime_name)
    session = read_json(artifact_dir / "runtime/session.json")
    if checkpoint_data and checkpoint_data.get("session_id") != session.get("session_id"):
        add_blocker(blockers, "agent_runtime", "runtime checkpoint belongs to another session", checkpoint=runtime_name)
    events, _ = AGENT_RUNTIME.load_events(artifact_dir / "runtime/events.jsonl")
    event_digests = {str(item.get("event_digest") or "") for item in events}
    checkpoint_root = str(checkpoint_data.get("runtime_root_digest") or "")
    if checkpoint_root and checkpoint_root not in event_digests:
        add_blocker(blockers, "agent_runtime", "runtime checkpoint root is not present in the event chain", checkpoint=runtime_name)
    return {
        "decision": "block" if blockers else "pass",
        "session_id": session.get("session_id", ""),
        "runtime_root_digest": verification.get("event_root_digest", ""),
        "event_refs": checkpoint_data.get("event_refs", []) if isinstance(checkpoint_data.get("event_refs"), list) else [],
        "runtime_checkpoint": runtime_name,
        "blockers": blockers,
    }


def bind_output_lineage(path: Path, artifact_dir: Path, checkpoint: str) -> None:
    root = Path(__file__).resolve().parents[4]
    contract_path = root / "skills/core/delivery-runner/scripts/workflow_contract.py"
    spec = importlib.util.spec_from_file_location("harness_workflow_contract", contract_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    inputs = [artifact_dir / name for name in HARNESS_INPUTS.get(checkpoint, []) if (artifact_dir / name).exists()]
    module.bind_lineage(path, f"harness_{checkpoint}", inputs, command=["harness", checkpoint], workspace=root)


def validate(
    artifact_dir: Path,
    budgets: dict[str, int] | None = None,
    checkpoint: str = "all",
    policy: dict[str, Any] | None = None,
    repo: Path | None = None,
    expected_head: str = "",
) -> dict[str, Any]:
    policy = policy or {}
    configured_budgets = nested_policy(policy, "artifact_budgets")
    effective_budgets = budgets or ({str(key): int(value) for key, value in configured_budgets.items()} if configured_budgets else DEFAULT_BUDGETS)
    selected = list(CHECKPOINTS) if checkpoint == "all" else [checkpoint]
    results: list[dict[str, Any]] = []
    runtime_bindings: list[dict[str, Any]] = []
    for name in selected:
        binding = runtime_binding(artifact_dir, name)
        runtime_bindings.append(binding)
        if name == "source_location":
            results.append(source_location_checkpoint(artifact_dir, repo, nested_policy(policy, name)))
        elif name == "design":
            results.append(design_checkpoint(artifact_dir, nested_policy(policy, name), effective_budgets))
        elif name == "post_implementation":
            results.append(post_implementation_checkpoint(artifact_dir))
        elif name == "pre_push":
            results.append(pre_push_checkpoint(artifact_dir, repo, expected_head, nested_policy(policy, name)))
    blockers = [dict(item, checkpoint=result["checkpoint"]) for result in results for item in result.get("blockers", [])]
    blockers.extend(
        dict(item, checkpoint=name)
        for name, binding in zip(selected, runtime_bindings)
        for item in binding.get("blockers", [])
    )
    sizes = [item for result in results for item in result.get("artifact_sizes", [])]
    checked_paths = [item for result in results for item in result.get("checked_paths", [])]
    evidence_summary: dict[str, Any] = next(
        (result.get("evidence_summary", {}) for result in results if result.get("evidence_summary")), {}
    )
    return {
        "schema": SCHEMA,
        "compatible_schemas": LEGACY_SCHEMAS,
        "checkpoint": checkpoint,
        "decision": "block" if blockers else "pass",
        "artifact_dir": str(artifact_dir),
        "checkpoints": results,
        "artifact_sizes": sizes,
        "evidence_summary": evidence_summary,
        "checked_paths": checked_paths,
        "session_id": runtime_bindings[0].get("session_id", "") if len(runtime_bindings) == 1 else "",
        "runtime_root_digest": runtime_bindings[0].get("runtime_root_digest", "") if len(runtime_bindings) == 1 else "",
        "event_refs": runtime_bindings[0].get("event_refs", []) if len(runtime_bindings) == 1 else [],
        "runtime_bindings": runtime_bindings,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run lifecycle Harness checkpoints")
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--checkpoint", choices=[*CHECKPOINTS, "all"], default="design")
    parser.add_argument("--policy")
    parser.add_argument("--repo")
    parser.add_argument("--expected-head", default="")
    parser.add_argument("--out")
    args = parser.parse_args()
    policy = load_restricted_yaml(Path(args.policy)) if args.policy else {}
    result = validate(
        Path(args.artifact_dir),
        checkpoint=args.checkpoint,
        policy=policy,
        repo=Path(args.repo) if args.repo else None,
        expected_head=args.expected_head,
    )
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if args.checkpoint != "all":
            bind_output_lineage(out, Path(args.artifact_dir), args.checkpoint)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
