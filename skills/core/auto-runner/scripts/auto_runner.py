#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
SCHEMA = "codex-auto-runner-summary-v1"
PROFILE_REGISTRY = ROOT / "config/workflow-profiles.example.yaml"
LOCAL_PATH_PATTERNS = [
    re.compile(r"/private/var/folders/[^\s\"']+"),
    re.compile(r"/var/folders/[^\s\"']+"),
    re.compile(r"/tmp/[^\s\"']+"),
    re.compile(r"/home/[^/\s\"']+(?:/[^\s\"']*)?"),
    re.compile(r"/" + r"Users/[^/\s\"']+(?:/[^\s\"']*)?"),
    re.compile(r"[A-Za-z]:\\[^\s\"']+"),
]


def load_workflow_contract_module() -> Any:
    path = ROOT / "skills/core/delivery-runner/scripts/workflow_contract.py"
    spec = importlib.util.spec_from_file_location("auto_runner_workflow_contract", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


WORKFLOW_CONTRACT = load_workflow_contract_module()


def load_summary_contract_module() -> Any:
    path = ROOT / "skills/core/delivery-runner/scripts/summary_contract.py"
    spec = importlib.util.spec_from_file_location("auto_runner_summary_contract", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SUMMARY_CONTRACT = load_summary_contract_module()


def load_agent_runtime_module() -> Any:
    path = ROOT / "skills/core/auto-runner/scripts/agent_runtime.py"
    spec = importlib.util.spec_from_file_location("auto_runner_agent_runtime", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AGENT_RUNTIME = load_agent_runtime_module()
RUNTIME_ARTIFACT_DIR: Path | None = None


def load_requirement_ingestor_module() -> Any:
    path = ROOT / "skills/core/requirement-document-ingestor/scripts/ingest_requirement.py"
    spec = importlib.util.spec_from_file_location("auto_runner_requirement_ingestor", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REQUIREMENT_INGESTOR = load_requirement_ingestor_module()


def slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-")
    return text or "requirement"


def default_doc_id(input_path: Path) -> str:
    return f"REQ-{slug(input_path.stem)}"


def default_title(input_path: Path) -> str:
    words = re.sub(r"[_-]+", " ", input_path.stem).strip()
    return words.title() if words else "Requirement"


def default_out(doc_id: str) -> Path:
    return Path("/tmp/codex-auto") / doc_id


def canonical_docs_artifact_dir(docs_root: Path, doc_id: str) -> Path:
    return (docs_root / "deliveries" / doc_id / "artifacts").resolve()


def sanitize_unmatched_local_path(value: str) -> str:
    if value.startswith(("/private/var/", "/var/folders/", "/tmp/")):
        return "<tmp>"
    if value.startswith(("/" + "Users/", "/home/")):
        return "<user-home>"
    if re.match(r"^[A-Za-z]:\\", value):
        return "<local-path>"
    return value


def sanitize_local_paths(value: str, artifact_dir: Path | None = None, docs_root: Path | None = None) -> str:
    result = value
    replacements: list[tuple[str, str]] = []
    if artifact_dir:
        replacements.append((str(artifact_dir), "<artifact-dir>"))
        replacements.append((str(artifact_dir).replace(str(Path.home()), "<user-home>"), "<artifact-dir>"))
    if docs_root:
        replacements.append((str(docs_root), "<docs-root>"))
        replacements.append((str(docs_root).replace(str(Path.home()), "<user-home>"), "<docs-root>"))
        if docs_root.parent:
            replacements.append((str(docs_root.parent), "<workspace>"))
            replacements.append((str(docs_root.parent).replace(str(Path.home()), "<user-home>"), "<workspace>"))
    replacements.append((str(ROOT), "<skills-root>"))
    replacements.append((str(Path.home()), "<user-home>"))
    for source, target in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
        if source:
            result = result.replace(source, target)
    for pattern in LOCAL_PATH_PATTERNS:
        result = pattern.sub(lambda match: sanitize_unmatched_local_path(match.group(0)), result)
    return result


def sanitize_for_artifact(value: Any, artifact_dir: Path | None = None, docs_root: Path | None = None) -> Any:
    if isinstance(value, str):
        return sanitize_local_paths(value, artifact_dir, docs_root)
    if isinstance(value, list):
        return [sanitize_for_artifact(item, artifact_dir, docs_root) for item in value]
    if isinstance(value, dict):
        return {str(key): sanitize_for_artifact(item, artifact_dir, docs_root) for key, item in value.items()}
    return value


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    artifact_dir = path.parent if path.name == "auto_run_summary.json" else None
    docs_root = None
    if path.parent.name == "artifacts" and path.parent.parent.parent.name == "deliveries":
        artifact_dir = path.parent
        docs_root = path.parent.parent.parent.parent
    payload = sanitize_for_artifact(data, artifact_dir=artifact_dir, docs_root=docs_root) if artifact_dir or docs_root else data
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def load_docs_config_module() -> Any:
    candidates = [
        Path(__file__).resolve().parents[1] / "scripts/docs_config.py",
        ROOT / "scripts/docs_config.py",
        ROOT.parent / "scripts/docs_config.py",
    ]
    path = next((candidate for candidate in candidates if candidate.exists()), candidates[0])
    spec = importlib.util.spec_from_file_location("docs_config", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_docs_governor_module() -> Any:
    candidates = [
        Path(__file__).resolve().parents[2] / "docs-governor/scripts/docs_governor.py",
        ROOT / "skills/core/docs-governor/scripts/docs_governor.py",
    ]
    path = next((candidate for candidate in candidates if candidate.exists()), candidates[0])
    spec = importlib.util.spec_from_file_location("docs_governor", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def default_docs_root() -> Path | None:
    try:
        return load_docs_config_module().configured_docs_root(ROOT)
    except Exception:
        return None


def docs_source_blockers(docs_root: Path | None, doc_id: str, artifact_dir: Path | None) -> list[dict[str, Any]]:
    if not docs_root or not artifact_dir:
        return []
    canonical_artifact_dir = (docs_root / "deliveries" / doc_id / "artifacts").resolve()
    resolved_artifact_dir = artifact_dir.resolve()
    if resolved_artifact_dir != canonical_artifact_dir and "_staging" in resolved_artifact_dir.parts:
        return [{
            "source": "docs_source",
            "message": "artifact_dir under _staging cannot be used as the docs readiness source; use the reviewed delivery artifacts or the canonical docs delivery artifacts directory",
        }]
    return []


def docs_readiness(docs_root: Path | None, doc_id: str, artifact_dir: Path | None = None) -> dict[str, Any]:
    if not docs_root:
        return {
            "schema": "codex-docs-readiness-v1",
            "decision": "block",
            "required": True,
            "docs_root": "",
            "artifact_dir": str(artifact_dir) if artifact_dir else "",
            "blockers": [{"source": "docs_root", "message": "delivery docs repository root is required before implementation"}],
            "next_command": f"python3 skills/core/docs-governor/scripts/docs_governor.py init --docs-root delivery-docs --doc-id {doc_id}",
        }
    manifest = docs_root / "indexes" / f"{doc_id}.manifest.json"
    validation = load_docs_governor_module().validate(docs_root, doc_id, require_git=True)
    blockers = [dict(item) for item in validation.get("blockers", [])]
    blockers.extend(docs_source_blockers(docs_root, doc_id, artifact_dir))
    return {
        "schema": "codex-docs-readiness-v1",
        "decision": "pass" if not blockers else "block",
        "required": True,
        "docs_root": str(docs_root),
        "artifact_dir": str(artifact_dir) if artifact_dir else "",
        "manifest": str(manifest),
        "canonical_delivery": str(docs_root / "deliveries" / doc_id),
        "blockers": blockers,
        "next_command": f"python3 skills/core/docs-governor/scripts/docs_governor.py init --docs-root {docs_root} --doc-id {doc_id}",
    }


def infer_doc_language(input_text: str, requested: str = "en") -> str:
    requested = str(requested or "en").lower()
    if requested in {"zh", "en"}:
        return requested
    zh_hints = ["文档使用中文", "文档用中文", "中文文档", "用中文描述", "使用中文描述", "中文描述"]
    return "zh" if any(hint in input_text for hint in zh_hints) else "en"


def infer_artifact_doc_language(artifact_dir: Path, requested: str = "auto", current: str = "en") -> str:
    requested = str(requested or "auto").lower()
    if requested in {"zh", "en"}:
        return requested
    if current == "zh":
        return "zh"
    zh_chars = 0
    for name in [
        "spec.json",
        "technical_design.json",
        "architecture_design.json",
        "test_design.json",
        "test_data_plan.json",
        "delivery_plan.json",
        "design_architecture_review.json",
        "delivery_plan_review.json",
    ]:
        path = artifact_dir / name
        if not path.exists():
            continue
        zh_chars += len(re.findall(r"[\u4e00-\u9fff]", path.read_text(encoding="utf-8", errors="ignore")))
        if zh_chars >= 80:
            return "zh"
    return current


def sync_docs_artifacts(docs_root: Path | None, doc_id: str, title: str, artifact_dir: Path, doc_language: str = "en", human_section: str = "all") -> dict[str, Any]:
    if not docs_root:
        return {"decision": "block", "reason": "docs_root is not configured", "blockers": [{"source": "docs_root", "message": "docs_root is not configured"}]}
    if not docs_root.exists():
        return {"decision": "block", "reason": "docs_root does not exist", "blockers": [{"source": "docs_root", "message": "docs_root does not exist"}]}
    canonical_artifact_dir = docs_root / "deliveries" / doc_id / "artifacts"
    if artifact_dir.resolve() != canonical_artifact_dir.resolve() and "_staging" in artifact_dir.parts:
        return {
            "decision": "block",
            "reason": "artifact_dir under _staging cannot be synced into canonical delivery",
            "blockers": [{
                "source": "docs_source",
                "message": "artifact_dir under _staging cannot be synced into canonical delivery; use the reviewed delivery artifacts or the canonical docs delivery artifacts directory",
            }],
        }
    proc = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=docs_root, text=True, capture_output=True)
    if proc.returncode != 0 or proc.stdout.strip() != "true":
        return {"decision": "block", "reason": "docs_root is not a git repository", "blockers": [{"source": "docs_git", "message": "docs_root is not a git repository"}]}
    try:
        return load_docs_governor_module().sync(docs_root, doc_id, artifact_dir, title, doc_language=doc_language, human_section=human_section)
    except Exception as exc:
        return {"decision": "block", "reason": str(exc), "blockers": [{"source": "docs_sync", "message": str(exc)}]}


def run_docs_quality(docs_root: Path | None, docs_sync: dict[str, Any], out: Path) -> dict[str, Any]:
    quality_path = out / "docs_quality.json"
    if not docs_root or docs_sync.get("decision") != "pass":
        quality_path.unlink(missing_ok=True)
        return {
            "schema": "codex-docs-quality-aggregate-v1",
            "decision": "not_applicable",
            "reason": "docs sync must pass before docs quality review",
            "blockers": [],
            "reviews": [],
        }
    reviews: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for rel in docs_sync.get("human_docs", []) if isinstance(docs_sync.get("human_docs"), list) else []:
        doc_path = docs_root / str(rel)
        proc = subprocess.run(["python3", "skills/core/human-doc-reviewer/scripts/human_doc_review.py", "--file", str(doc_path), "--strict"], cwd=ROOT, text=True, capture_output=True)
        data: dict[str, Any] = {}
        if proc.stdout.strip():
            try:
                data = json.loads(proc.stdout)
            except Exception:
                data = {}
        review = {"file": str(doc_path), "returncode": proc.returncode, "result": data}
        reviews.append(review)
        for item in data.get("blockers", []) if isinstance(data.get("blockers"), list) else []:
            if isinstance(item, dict):
                blockers.append({"file": str(doc_path), **item})
        for item in data.get("warnings", []) if isinstance(data.get("warnings"), list) else []:
            if isinstance(item, dict):
                warnings.append({"file": str(doc_path), **item})
        if proc.returncode != 0:
            blockers.append({"file": str(doc_path), "source": "human_doc_review", "message": "review command failed"})
    result = {
        "schema": "codex-docs-quality-aggregate-v1",
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "blockers": blockers,
        "warnings": warnings,
        "reviews": reviews,
    }
    write_json(quality_path, result)
    return result


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [] if not inner else [parse_scalar(item) for item in inner.split(",")]
    value = value.strip('"').strip("'")
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    try:
        return int(value)
    except ValueError:
        return value


def load_restricted_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    lines: list[tuple[int, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        lines.append((len(raw) - len(raw.lstrip(" ")), raw.strip()))

    def parse_block(index: int, indent: int) -> tuple[Any, int]:
        if index >= len(lines):
            return {}, index
        container: Any = [] if lines[index][1].startswith("- ") else {}
        while index < len(lines):
            current_indent, text = lines[index]
            if current_indent < indent or current_indent > indent:
                break
            if text.startswith("- "):
                if not isinstance(container, list):
                    break
                item = text[2:].strip()
                index += 1
                if ":" in item:
                    key, value = item.split(":", 1)
                    entry: dict[str, Any] = {}
                    if value.strip():
                        entry[key.strip()] = parse_scalar(value.strip())
                    else:
                        child, index = parse_block(index, indent + 2)
                        entry[key.strip()] = child
                    while index < len(lines) and lines[index][0] > indent:
                        child_indent, child_text = lines[index]
                        if child_indent != indent + 2 or child_text.startswith("- ") or ":" not in child_text:
                            break
                        child_key, child_value = child_text.split(":", 1)
                        index += 1
                        if child_value.strip():
                            entry[child_key.strip()] = parse_scalar(child_value.strip())
                        else:
                            child, index = parse_block(index, child_indent + 2)
                            entry[child_key.strip()] = child
                    container.append(entry)
                else:
                    container.append(parse_scalar(item))
                continue
            if not isinstance(container, dict) or ":" not in text:
                break
            key, value = text.split(":", 1)
            index += 1
            if value.strip():
                container[key.strip()] = parse_scalar(value.strip())
            else:
                child, index = parse_block(index, indent + 2)
                container[key.strip()] = child
        return container, index

    parsed, _ = parse_block(0, lines[0][0] if lines else 0)
    return parsed if isinstance(parsed, dict) else {}


def load_profile_registry(path: Path = PROFILE_REGISTRY) -> dict[str, dict[str, Any]]:
    data = load_restricted_yaml(path)
    profiles: dict[str, dict[str, Any]] = {}
    for item in data.get("profiles", []) if isinstance(data.get("profiles"), list) else []:
        if isinstance(item, dict) and item.get("name"):
            profiles[str(item["name"])] = item
    return profiles


def project_registry_path() -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
    return codex_home / "skills" / "company" / "projects.yaml"


def load_project_registry(path: Path | None = None) -> dict[str, dict[str, Any]]:
    raw = load_restricted_yaml(path or project_registry_path())
    projects: dict[str, dict[str, Any]] = {}
    for item in raw.get("projects", []) if isinstance(raw.get("projects"), list) else []:
        if isinstance(item, dict) and item.get("name"):
            projects[str(item["name"])] = item
    return projects


def project_checkout_path(project: str, registry_item: dict[str, Any] | None = None) -> Path:
    hint = ""
    if isinstance(registry_item, dict):
        repo = registry_item.get("repo") if isinstance(registry_item.get("repo"), dict) else {}
        if isinstance(repo, dict):
            hint = str(repo.get("local_path_hint") or "")
    candidate = Path.home() / "hl-workspace" / (hint or project)
    return candidate


def project_skill_dir(project: str) -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
    return codex_home / "skills" / "company" / project


def project_query_terms(text: str) -> list[str]:
    stopwords = {
        "需求", "功能", "页面", "系统", "运营", "用户", "设备", "状态", "订单", "导出", "列表", "按钮",
        "接口", "结果", "流程", "业务", "目标", "规则", "模块", "场景", "页面", "表单", "审批", "记录",
        "order", "export", "page", "admin", "list", "button", "form", "result", "query", "filter",
        "system", "user", "device", "status", "state", "task", "flow", "change", "update", "show",
        "view", "open", "manage", "feature", "action",
    }
    terms: list[str] = []
    for term in re.findall(r"(?:/[A-Za-z0-9_{}.*-]+)+|[A-Za-z_][A-Za-z0-9_]{3,}|[\u4e00-\u9fff]{2,12}", text):
        clean = term.strip().lower()
        if clean in stopwords:
            continue
        if clean not in terms:
            terms.append(clean)
    return terms[:40]


def project_reference_score(text: str, project: str) -> int:
    skill_dir = project_skill_dir(project)
    if not skill_dir.is_dir():
        return 0
    terms = project_query_terms(text)
    if not terms:
        return 0
    hits = 0
    files = [skill_dir / "SKILL.md"]
    references = skill_dir / "references"
    if references.is_dir():
        files.extend(sorted(path for path in references.iterdir() if path.is_file())[:12])
    for path in files:
        try:
            blob = path.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            continue
        matched = [term for term in terms if term in blob]
        hits += min(len(matched), 6)
    return hits * 3


def project_signal_score(text: str, registry_item: dict[str, Any]) -> int:
    lower = text.lower()
    repo_type = str(registry_item.get("type") or "")
    roles = {str(item) for item in as_list(registry_item.get("roles"))}
    dependencies = {str(item).lower() for item in as_list(registry_item.get("dependencies"))}
    hint = str((registry_item.get("repo") or {}).get("local_path_hint") or registry_item.get("name") or "").lower() if isinstance(registry_item.get("repo"), dict) else str(registry_item.get("name") or "").lower()
    score = 0
    backend_signals = {
        "data", "database", "table", "history", "status", "state", "retry", "task", "job", "scheduler",
        "mq", "topic", "queue", "callback", "notify", "notification", "device", "version", "approval",
        "persistence", "storage", "sync", "bill", "settlement", "package", "历史", "状态", "重试", "任务",
        "定时", "回调", "通知", "设备", "版本", "审批", "存储", "同步", "结算", "软件包", "升级包", "飞书",
    }
    frontend_signals = {
        "ui", "page", "button", "menu", "table", "form", "route", "browser", "frontend", "dialog",
        "list", "display", "show", "panel", "screen", "页面", "按钮", "菜单", "表单", "路由", "浏览器", "弹窗",
    }
    if repo_type == "backend":
        score += 2
    if repo_type == "frontend":
        score += 1
    if "backend" in roles:
        score += 2
    if "frontend" in roles:
        score += 1
    if hint and hint in lower:
        score += 15
    if any(term in lower for term in backend_signals):
        score += 3 * sum(1 for term in backend_signals if term in lower)
    if any(term in lower for term in frontend_signals):
        score += 2 * sum(1 for term in frontend_signals if term in lower)
    if dependencies and any(dep in lower for dep in dependencies):
        score += 5
    return score


def resolve_project_binding(
    input_text: str,
    repo: Path | None = None,
    project: str | None = None,
    registry: dict[str, dict[str, Any]] | None = None,
) -> tuple[Path | None, str | None, dict[str, Any]]:
    registry = registry or load_project_registry()
    if not registry:
        return repo, project, {
            "repo_root": str(repo) if repo else "",
            "project": project or "",
            "project_skill_loaded": False,
            "project_registry_path": str(project_registry_path()),
            "resolution_mode": "unresolved",
            "resolution_reason": "project registry is missing",
        }

    if project and not repo:
        registry_item = registry.get(project, {})
        checkout = project_checkout_path(project, registry_item)
        if checkout.exists():
            repo = checkout

    if repo and not project:
        for name, item in registry.items():
            checkout = project_checkout_path(name, item)
            if checkout.exists() and checkout.resolve() == repo.resolve():
                project = name
                break

    selected_project = project or ""
    selected_repo = repo
    resolution_mode = "explicit" if repo and project else "unresolved"
    resolution_reason = "repo/project were provided explicitly" if repo and project else "repo/project were not provided"
    candidates: list[dict[str, Any]] = []

    if project:
        current = registry.get(project, {})
        current_type = str(current.get("type") or "")
        if current_type == "frontend":
            for dep_index, dep in enumerate(as_list(current.get("dependencies"))):
                dep_name = str(dep)
                dep_item = registry.get(dep_name, {})
                if str(dep_item.get("type") or "") != "backend":
                    continue
                checkout = project_checkout_path(dep_name, dep_item)
                signal_score = project_signal_score(input_text, dep_item)
                reference_score = project_reference_score(input_text, dep_name)
                candidates.append({
                    "project": dep_name,
                    "repo_root": str(checkout),
                    "score": reference_score + signal_score,
                    "reference_score": reference_score,
                    "signal_score": signal_score,
                    "dependency_index": dep_index,
                    "repo_type": str(dep_item.get("type") or ""),
                    "local_path_hint": str((dep_item.get("repo") or {}).get("local_path_hint") or ""),
                    "skill": str(dep_item.get("skill") or dep_name),
                })
            candidates.sort(
                key=lambda item: (
                    -int(item.get("reference_score") or 0),
                    -int(item.get("signal_score") or 0),
                    int(item.get("dependency_index") or 0),
                    item["project"],
                ),
            )
            best = candidates[0] if candidates else {}
            if best and (int(best.get("reference_score") or 0) > 0 or int(best.get("signal_score") or 0) >= 10):
                candidate_repo = Path(str(best.get("repo_root") or ""))
                if candidate_repo.exists():
                    selected_project = str(best["project"])
                    selected_repo = candidate_repo
                    resolution_mode = "registry_related_repo"
                    resolution_reason = f"current project {project} is frontend and the requirement maps to a direct backend dependency"

    binding = {
        "repo_root": str(selected_repo) if selected_repo else str(repo or ""),
        "project": selected_project,
        "project_skill_loaded": bool(selected_project and selected_project in registry),
        "project_registry_path": str(project_registry_path()),
        "resolution_mode": resolution_mode,
        "resolution_reason": resolution_reason,
        "candidates": candidates[:5],
    }
    if selected_project and selected_repo and selected_repo.exists():
        return selected_repo, selected_project, binding
    return repo, project, binding


def run_command(name: str, args: list[str]) -> dict[str, Any]:
    record_runtime = RUNTIME_ARTIFACT_DIR is not None and name != "inspect"
    if record_runtime:
        AGENT_RUNTIME.append_event(
            RUNTIME_ARTIFACT_DIR,
            "tool_call_requested",
            "subprocess",
            target=" ".join(args),
            details={"step": name},
        )
    started = time.monotonic()
    proc = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    payload: dict[str, Any] = {}
    try:
        parsed = json.loads(proc.stdout)
        payload = parsed if isinstance(parsed, dict) else {}
    except Exception:
        payload = {}
    decision = str(payload.get("decision") or payload.get("status") or "")
    passed = proc.returncode == 0 and decision not in {"block", "blocked", "error", "failed"}
    if record_runtime:
        AGENT_RUNTIME.append_event(
            RUNTIME_ARTIFACT_DIR,
            "tool_call_completed",
            "subprocess",
            target=" ".join(args),
            decision="allow" if passed else "block",
            details={
                "step": name,
                "returncode": proc.returncode,
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
                "stdout_digest": AGENT_RUNTIME.digest(proc.stdout),
                "stderr_digest": AGENT_RUNTIME.digest(proc.stderr),
            },
        )
    return {
        "name": name,
        "command": args,
        "returncode": proc.returncode,
        "passed": passed,
        "decision": decision,
        "duration_ms": round((time.monotonic() - started) * 1000, 2),
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def workflow_metrics(steps: list[dict[str, Any]], generated: list[str], skipped: list[str], profile: dict[str, Any]) -> dict[str, Any]:
    executed = sum(1 for step in steps if not step.get("skipped"))
    reused = sum(1 for step in steps if step.get("cache_status") == "reused")
    invalidated = sum(1 for step in steps if step.get("cache_status") == "invalidated")
    duration = round(sum(float(step.get("duration_ms") or 0) for step in steps), 2)
    budget_value = profile.get("cost_budget")
    budget: dict[str, Any] = budget_value if isinstance(budget_value, dict) else {}
    observed = {
        "executed_steps": executed,
        "generated_artifacts": len(set(generated)),
        "command_duration_ms": duration,
    }
    budget_keys = {
        "max_executed_steps": "executed_steps",
        "max_generated_artifacts": "generated_artifacts",
        "max_command_duration_ms": "command_duration_ms",
    }
    breaches = [
        {"metric": metric, "observed": observed[observed_key], "maximum": budget[metric]}
        for metric, observed_key in budget_keys.items()
        if isinstance(budget.get(metric), (int, float)) and observed[observed_key] > budget[metric]
    ]
    expected_count = len({str(item) for item in as_list(profile.get("expected_artifacts"))})
    reduction = round(100 * max(0, expected_count - len(set(generated))) / expected_count, 2) if expected_count else 0
    return {
        "governance_level": str(profile.get("governance_level") or "standard"),
        "executed_step_count": executed,
        "skipped_step_count": sum(1 for step in steps if step.get("skipped")),
        "generated_artifact_count": len(set(generated)),
        "reused_artifact_count": reused,
        "invalidated_artifact_count": invalidated,
        "total_command_duration_ms": duration,
        "target_artifact_reduction_percent": int(profile.get("target_artifact_reduction_percent") or 0),
        "observed_artifact_reduction_percent": reduction,
        "cost_budget": budget,
        "cost_budget_decision": "warn" if breaches else "pass",
        "cost_budget_breaches": breaches,
    }


def workflow_stage_inputs(output: Path) -> list[Path]:
    registry = load_restricted_yaml(ROOT / "config/workflow-stages.example.yaml")
    for stage in as_list(registry.get("stages")):
        if not isinstance(stage, dict):
            continue
        artifact = Path(str(stage.get("artifact") or ""))
        if not artifact.name or artifact.name != output.name:
            continue
        artifact_dir = output.parents[len(artifact.parts) - 1]
        return [
            artifact_dir / str(item)
            for item in as_list(stage.get("input_artifacts"))
            if (artifact_dir / str(item)).exists()
        ]
    return []


def finalize_runtime_lineage(artifact_dir: Path) -> None:
    runtime_dir = artifact_dir / "runtime"
    session_path = runtime_dir / "session.json"
    if session_path.exists():
        WORKFLOW_CONTRACT.bind_lineage(
            session_path,
            "runtime_session",
            [],
            command=["agent-runtime", "start"],
            workspace=ROOT,
        )
    for checkpoint in ["intake", "design", "pre_edit", "post_implementation", "pre_push", "release", "close"]:
        path = runtime_dir / "checkpoints" / f"{checkpoint}.json"
        if path.exists():
            WORKFLOW_CONTRACT.bind_lineage(
                path,
                f"runtime_{checkpoint}",
                workflow_stage_inputs(path),
                command=["agent-runtime", "checkpoint", checkpoint],
                workspace=ROOT,
            )


def run_if_needed(name: str, output: Path, command: list[str], force: bool, generated: list[str], skipped: list[str], steps: list[dict[str, Any]]) -> None:
    inputs = WORKFLOW_CONTRACT.command_input_paths(command, output) + workflow_stage_inputs(output)
    inputs = list({str(path): path for path in inputs}.values())
    if output.exists() and not force and WORKFLOW_CONTRACT.lineage_is_fresh(output, inputs):
        skipped.append(output.name)
        steps.append({"name": name, "skipped": True, "cache_status": "reused", "output": str(output), "reason": "artifact inputs are unchanged"})
        return
    cache_status = "forced" if output.exists() and force else "invalidated" if output.exists() else "miss"
    result = run_command(name, command)
    steps.append(result | {"output": str(output), "cache_status": cache_status})
    if output.exists():
        WORKFLOW_CONTRACT.bind_lineage(output, name, inputs, command=command, workspace=ROOT)
        generated.append(output.name)


def refresh_clarified_requirement_ir(out: Path, doc_id: str, clarified: Path, generated: list[str]) -> None:
    text = clarified.read_text(encoding="utf-8")
    requirement_ir = REQUIREMENT_INGESTOR.parse_markdown_ir(text, doc_id, clarified)
    requirement_ir_path = out / "requirement_ir.json"
    write_json(requirement_ir_path, requirement_ir)
    if "requirement_ir.json" not in generated:
        generated.append("requirement_ir.json")

    ingestion_path = out / "requirement_ingestion.json"
    ingestion = read_json(ingestion_path)
    if ingestion:
        ingestion["source_file"] = str(clarified)
        ingestion["normalized_text"] = str(clarified)
        ingestion["requirement_ir"] = str(requirement_ir_path)
        ingestion["features"] = REQUIREMENT_INGESTOR.detect_features(text)
        ingestion["next_action"] = "Run spec-governor on requirement.clarified.txt."
        write_json(ingestion_path, ingestion)
        WORKFLOW_CONTRACT.bind_lineage(
            ingestion_path,
            "ingest",
            [clarified],
            command=["auto-runner", "refresh-clarified-requirement-ir", str(clarified)],
            workspace=ROOT,
        )


def collect_blockers(steps: list[dict[str, Any]], inspect_status: dict[str, Any], include_inspect: bool = True) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for step in steps:
        if step.get("skipped"):
            continue
        if step.get("name") == "inspect":
            continue
        if str(step.get("decision") or "") in {"block", "blocked", "error", "failed"}:
            blockers.append({"source": step.get("name"), "message": f"step decision is {step.get('decision')}", "returncode": step.get("returncode")})
            continue
        if step.get("output") and Path(str(step["output"])).exists():
            continue
        if step.get("returncode", 0) != 0:
            blockers.append({"source": step.get("name"), "message": "step returned non-zero", "returncode": step.get("returncode")})
    if include_inspect:
        for item in inspect_status.get("blockers", []) or []:
            if isinstance(item, dict):
                blockers.append(item)
    return blockers


def artifact_decision(data: dict[str, Any]) -> str:
    return str(data.get("decision") or data.get("status") or "")


def unique_blockers(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        key = (str(item.get("source") or ""), str(item.get("message") or ""))
        if key in seen:
            continue
        unique.append(item)
        seen.add(key)
    return unique


def not_applicable_gate(schema: str, reason: str, source: str = "workflow") -> dict[str, Any]:
    return {
        "schema": schema,
        "decision": "not_applicable",
        "reason": reason,
        "blockers": [{"source": source, "message": reason}],
    }


def design_phase_blockers(out: Path, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blockers = [item for item in collect_blockers(steps, {}, include_inspect=False) if isinstance(item, dict)]
    stage_artifacts = {
        "spec": out / "spec.json",
        "open_questions": out / "open_questions.json",
        "technical_design": out / "technical_design.json",
        "architecture_design": out / "architecture_design.json",
        "test_design": out / "test_design.json",
        "delivery_plan": out / "delivery_plan.json",
        "delivery_plan_review": out / "delivery_plan_review.json",
        "design_review": out / "design_architecture_review.json",
        "harness_design": out / "harness_validation.json",
    }
    accepted = {
        "spec": {"pass", "ready_for_design"},
        "open_questions": {"pass", "ready", "answered"},
        "technical_design": {"pass", "ready"},
        "architecture_design": {"pass", "ready"},
        "test_design": {"pass", "ready"},
        "delivery_plan": {"pass", "ready"},
        "delivery_plan_review": {"pass", "ready", "approved"},
        "design_review": {"pass", "approved"},
        "harness_design": {"pass"},
    }
    for source, path in stage_artifacts.items():
        data = read_json(path)
        if not data:
            continue
        decision = artifact_decision(data)
        if decision and decision not in accepted[source]:
            blockers.append({"source": source, "message": f"artifact decision is {decision}"})
        for key in ["blockers", "active_blockers", "missing_evidence"]:
            value = data.get(key)
            if value:
                blockers.append({"source": source, "message": f"{key} present"})
    return unique_blockers(blockers)


def source_location_readiness(out: Path, project_out: Path | None = None) -> dict[str, Any]:
    source_path = (project_out / "source_location_evidence.json") if project_out else out / "source_location_evidence.json"
    bundle_path = (project_out / "evidence_bundle.json") if project_out else out / "evidence_bundle.json"
    harness_path = out / "harness/source_location.json"
    source_data = read_json(source_path)
    bundle_data = read_json(bundle_path)
    harness_data = read_json(harness_path)
    confirmed = [
        str(item.get("path"))
        for item in as_list(source_data.get("confirmed_anchors"))
        if isinstance(item, dict) and item.get("path")
    ]
    rejected = [
        str(item.get("path"))
        for item in as_list(source_data.get("rejected_candidates"))
        if isinstance(item, dict) and item.get("path")
    ]
    blockers: list[dict[str, Any]] = []
    if project_out is None:
        return {
            "decision": "not_applicable",
            "applicable": False,
            "confirmed_anchor_count": 0,
            "rejected_candidate_count": 0,
            "blockers": [],
        }
    if source_data.get("decision") != "pass":
        blockers.append({"source": "source_location_evidence", "message": "requirement-specific source location evidence did not pass"})
    if harness_data and harness_data.get("decision") != "pass":
        blockers.extend(item for item in as_list(harness_data.get("blockers")) if isinstance(item, dict))
    if not confirmed:
        blockers.append({"source": "source_location_evidence", "message": "no confirmed source anchors"})
    if bundle_data.get("stale_references"):
        blockers.append({"source": "project_overlay", "message": "project overlay contains stale references"})
    return {
        "decision": "pass" if not blockers else "block",
        "applicable": True,
        "source_location_decision": str(source_data.get("decision") or ""),
        "harness_decision": str(harness_data.get("decision") or ""),
        "confirmed_anchor_count": len(confirmed),
        "confirmed_anchors": confirmed[:8],
        "rejected_candidate_count": len(rejected),
        "rejected_candidates": rejected[:8],
        "local_project_binding": bundle_data.get("local_project_binding") if isinstance(bundle_data.get("local_project_binding"), dict) else {},
        "blockers": blockers,
    }


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def profile_score(profile: dict[str, Any], lane: str, impacts: set[str], has_repo: bool, explicit_profile: str | None = None) -> dict[str, Any]:
    name = str(profile.get("name") or "")
    score = 0
    signals: list[str] = []
    simple_defect_impacts = {"business_flow", "workflow", "state", "status"}
    if explicit_profile and explicit_profile == name:
        score += 100
        signals.append("explicit_profile")
    if name == "small_feature-lite" and lane == "small_change" and not impacts and not has_repo:
        score += 70
        signals.append("lite_small_change")
    if name == "bugfix-lite" and lane in {"bugfix", "hotfix"} and impacts.issubset(simple_defect_impacts):
        score += 70
        signals.append("lite_defect")
    trigger_lanes = {str(item) for item in as_list(profile.get("trigger_lanes"))}
    if lane and lane in trigger_lanes:
        score += 45
        signals.append(f"lane:{lane}")
    trigger_impacts = {str(item) for item in as_list(profile.get("trigger_impacts"))}
    matched_impacts = sorted(impacts & trigger_impacts)
    if matched_impacts:
        score += 35 + (5 * len(matched_impacts))
        signals.extend(f"impact:{item}" for item in matched_impacts)
    if has_repo and name not in {"small_feature", "small_feature-lite"}:
        score += 5
        signals.append("repo_context")
    if {"data", "security"} & impacts and name == "data_migration":
        score += 45
        signals.append("high_risk_data_or_security")
    if lane in {"bugfix", "hotfix"} and name in {"bugfix", "hotfix"}:
        score += 60
        signals.append("defect_containment")
    if not signals and name in {"small_feature", "small_feature-lite"}:
        score += 5
        signals.append("default_fallback")
    return {"profile": name, "score": score, "signals": signals}


def profile_selection_confidence(candidates: list[dict[str, Any]]) -> str:
    if not candidates:
        return "low"
    ordered = sorted(candidates, key=lambda item: int(item.get("score") or 0), reverse=True)
    top = int(ordered[0].get("score") or 0)
    second = int(ordered[1].get("score") or 0) if len(ordered) > 1 else 0
    if top >= 80 and top - second >= 25:
        return "high"
    if top >= 45 and top - second >= 10:
        return "medium"
    return "low"


def workflow_strictness(spec: dict[str, Any], profile: dict[str, Any], confidence: str = "") -> dict[str, Any]:
    lane = str(spec.get("lane") or "")
    impacts = required_impacts(spec)
    profile_name = str(profile.get("name") or "")
    regulated_impacts = {"data", "database", "security", "permission", "tenant", "payment", "performance", "configuration", "release"}
    standard_upgrade_impacts = {"api", "ui", "frontend", "cross_repo", "mq", "async", "scheduler", "task", "job", "cache", "integration", "business_flow", "workflow", "state", "status"}
    workflow_surface = impacts & {"business_flow", "workflow", "state", "status"}
    mixed_complexity = bool(workflow_surface and impacts & {"api", "cross_repo", "integration", "data", "permission"})
    reasons: list[str] = []
    if profile_name == "small_feature-lite" and not impacts:
        reasons.append("lite small-feature profile with no declared impact")
        tier = "light"
    elif profile_name == "bugfix-lite" and impacts <= workflow_surface:
        reasons.append("lite bugfix profile without elevated impact")
        tier = "light"
    elif impacts & regulated_impacts or "data_migration" in profile_name:
        reasons.extend(sorted(impacts & regulated_impacts) or ["data_migration_profile"])
        tier = "regulated"
    elif mixed_complexity:
        reasons.append("workflow/stateful change spans business flow with contract/data/permission impact")
        tier = "regulated"
    elif lane in {"bugfix", "hotfix"} and impacts & standard_upgrade_impacts:
        reasons.extend(f"{item} impact raises defect fix above light tier" for item in sorted(impacts & standard_upgrade_impacts))
        tier = "standard"
    elif lane in {"bugfix", "hotfix"} and not impacts:
        reasons.append("defect lane without declared high-risk impact")
        tier = "light"
    elif profile_name == "release_readiness":
        reasons.append("release readiness uses release-only evidence")
        tier = "regulated"
    else:
        reasons.append("standard design and evidence path")
        tier = "standard"
    if confidence == "low" and tier == "light":
        tier = "standard"
        reasons.append("low profile confidence raises minimum strictness")
    required_controls = {
        "light": ["spec", "technical_design", "test_design", "delivery_plan_review", "git_edit_permit"],
        "standard": ["spec", "domain_model_design", "architecture_framing", "technical_design", "architecture_design", "design_review", "test_design", "test_data_plan", "initial_traceability", "delivery_plan_review", "docs_quality", "git_edit_permit"],
        "regulated": ["standard_controls", "security_or_configuration_review", "performance_or_release_evidence", "environment_uat_release_gates"],
    }[tier]
    return {
        "tier": tier,
        "reasons": reasons,
        "elevated": tier != "light" if lane in {"bugfix", "hotfix"} else tier == "regulated",
        "elevation_impacts": sorted(impacts & (regulated_impacts | standard_upgrade_impacts)),
        "required_controls": required_controls,
        "lane": lane,
        "impacts": sorted(impacts),
        "profile": profile_name,
    }


def effective_workflow_controls(profile: dict[str, Any], strictness: dict[str, Any]) -> dict[str, Any]:
    tier = strictness.get("tier", "")
    gate_artifacts = as_list(profile.get("required_gate_artifacts"))
    expected_artifacts = as_list(profile.get("expected_artifacts"))
    gate_overrides: list[str] = []
    if tier == "light":
        allowed = {
            "runtime/session.json",
            "runtime/checkpoints/intake.json",
            "runtime/checkpoints/design.json",
            "runtime/checkpoints/pre_edit.json",
            "spec.json",
            "technical_design.json",
            "test_design.json",
            "delivery_plan_review.json",
            "harness_validation.json",
            "docs_quality.json",
        }
        original_gate_count = len(gate_artifacts)
        gate_artifacts = [item for item in gate_artifacts if isinstance(item, dict) and str(item.get("artifact") or "") in allowed]
        expected_artifacts = [item for item in expected_artifacts if str(item) in allowed]
        gate_overrides.append(f"light tier limits effective gates from {original_gate_count} to {len(gate_artifacts)}")
    return {
        "tier": tier,
        "required_controls": strictness.get("required_controls", []),
        "required_skills": as_list(profile.get("required_skills")),
        "required_gate_artifacts": gate_artifacts,
        "expected_artifacts": expected_artifacts,
        "gate_overrides": gate_overrides,
    }


def effective_profile_for_strictness(profile: dict[str, Any], strictness: dict[str, Any]) -> dict[str, Any]:
    controls = effective_workflow_controls(profile, strictness)
    effective = json.loads(json.dumps(profile, ensure_ascii=False))
    effective["required_gate_artifacts"] = controls["required_gate_artifacts"]
    effective["expected_artifacts"] = controls["expected_artifacts"]
    effective["strictness_gate_overrides"] = controls["gate_overrides"]
    return effective


def required_gate_artifact_names(profile: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for item in as_list(profile.get("required_gate_artifacts")):
        if isinstance(item, dict) and item.get("artifact"):
            names.append(str(item["artifact"]))
    return names


def strictness_gate_gaps(profile: dict[str, Any], strictness: dict[str, Any]) -> list[dict[str, Any]]:
    tier = strictness.get("tier")
    if tier != "regulated":
        return []
    skills = {str(item) for item in as_list(profile.get("required_skills"))}
    impacts = {str(item) for item in as_list(strictness.get("impacts"))}
    gaps: list[dict[str, Any]] = []
    if "release-evidence-binder" not in skills:
        gaps.append({"source": "workflow_strictness", "message": "regulated workflow requires release-evidence-binder"})
    if impacts & {"data", "database", "security", "permission"} and "data-security-governor" not in skills:
        gaps.append({"source": "workflow_strictness", "message": "regulated data/security workflow requires data-security-governor"})
    if "configuration" in impacts and "configuration-governor" not in skills:
        gaps.append({"source": "workflow_strictness", "message": "regulated configuration workflow requires configuration-governor"})
    if "performance" in impacts and "performance-governor" not in skills:
        gaps.append({"source": "workflow_strictness", "message": "regulated performance workflow requires performance-governor"})
    return gaps


def unique_extend(target: list[Any], values: list[Any]) -> None:
    seen = {json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, dict) else str(item) for item in target}
    for value in values:
        key = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, dict) else str(value)
        if key not in seen:
            target.append(value)
            seen.add(key)


def merge_workflow_profiles(base: dict[str, Any], overlays: list[dict[str, Any]]) -> dict[str, Any]:
    merged = json.loads(json.dumps(base, ensure_ascii=False))
    source_names = [str(base.get("name") or "")]
    for overlay in overlays:
        overlay_name = str(overlay.get("name") or "")
        if overlay_name and overlay_name not in source_names:
            source_names.append(overlay_name)
        for key in ["required_skills", "optional_skills", "expected_artifacts"]:
            values = as_list(overlay.get(key))
            if values:
                merged.setdefault(key, [])
                unique_extend(merged[key], values)
        if as_list(overlay.get("required_gate_artifacts")):
            merged.setdefault("required_gate_artifacts", [])
            unique_extend(merged["required_gate_artifacts"], as_list(overlay.get("required_gate_artifacts")))
        if as_list(overlay.get("artifact_steps")):
            merged.setdefault("artifact_steps", [])
            unique_extend(merged["artifact_steps"], as_list(overlay.get("artifact_steps")))
        if as_list(overlay.get("notes")):
            merged.setdefault("notes", [])
            unique_extend(merged["notes"], as_list(overlay.get("notes")))
    merged["name"] = "+".join(name for name in source_names if name) or str(base.get("name") or "combined")
    merged["base_profile"] = str(base.get("name") or "")
    merged["overlay_profiles"] = [name for name in source_names[1:] if name]
    merged["composition_mode"] = "merged" if merged["overlay_profiles"] else "single"
    return merged


def impact_overlay_profile_names(impacts: set[str], has_repo: bool) -> list[str]:
    names: list[str] = []
    if impacts & {"api", "cross_repo", "integration"}:
        names.append("cross_repo_api")
    if impacts & {"ui", "frontend"}:
        names.append("frontend_change")
    if {"data", "security", "database", "configuration", "performance", "permission", "release"} & impacts:
        names.append("data_migration")
    return names


def applicability_decisions(spec: dict[str, Any]) -> list[dict[str, Any]]:
    declared = as_list(spec.get("impact_applicability"))
    if declared:
        return [item for item in declared if isinstance(item, dict) and item.get("area")]
    return [
        {"area": str(item.get("area")), "status": "required", "reason": "legacy spec impact surface"}
        for item in as_list(spec.get("impact_surface"))
        if isinstance(item, dict) and item.get("area")
    ]


def required_impacts(spec: dict[str, Any]) -> set[str]:
    return {str(item["area"]) for item in applicability_decisions(spec) if item.get("status") == "required"}


def select_workflow_profile_with_reason(spec: dict[str, Any], has_repo: bool = False, explicit_profile: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    profiles = load_profile_registry()
    lane = str(spec.get("lane") or "")
    impacts = required_impacts(spec)
    candidates = sorted(
        (profile_score(profile, lane, impacts, has_repo, explicit_profile) for profile in profiles.values()),
        key=lambda item: int(item.get("score") or 0),
        reverse=True,
    )
    confidence = profile_selection_confidence(candidates)

    def reason_payload(mode: str, selected_profile: str, reason: str, **extra: Any) -> dict[str, Any]:
        payload = {
            "mode": mode,
            "selected_profile": selected_profile,
            "reason": reason,
            "lane": lane,
            "impacts": sorted(impacts),
            "matched_impact": "",
            "matched_impacts": sorted(impacts),
            "profile_selection_score": next((item.get("score", 0) for item in candidates if item.get("profile") == selected_profile), 0),
            "profile_selection_confidence": confidence,
            "profile_selection_candidates": candidates,
            "fallback_reason": "" if mode != "fallback" else reason,
        }
        payload.update(extra)
        return payload

    base_profile: dict[str, Any]
    mode = ""
    reason = ""
    if explicit_profile and explicit_profile in profiles:
        base_profile = profiles[explicit_profile]
        mode = "explicit_profile"
        reason = "Profile was explicitly requested."
    elif lane in {"bugfix", "hotfix"}:
        simple_defect_impacts = {"business_flow", "workflow", "state", "status"}
        if impacts.issubset(simple_defect_impacts) and "bugfix-lite" in profiles:
            base_profile = profiles["bugfix-lite"]
            reason = "Simple defect without declared impact uses the lite bugfix workflow."
        else:
            base_profile = profiles.get("bugfix", {})
            for profile in profiles.values():
                if lane in {str(item) for item in as_list(profile.get("trigger_lanes"))}:
                    base_profile = profile
                    break
            reason = f"Spec lane {lane} anchors defect containment; impact overlays are merged instead of replacing bugfix gates."
        mode = "lane"
    else:
        if lane == "small_change" and not impacts and not has_repo and "small_feature-lite" in profiles:
            base_profile = profiles["small_feature-lite"]
            mode = "lane"
            reason = "Small single-scope request without declared impact uses the lite small-feature workflow."
        else:
            priority = [
                ("data", "data_migration", "Data changes require migration, security, performance, and release evidence gates."),
                ("database", "data_migration", "Database changes require migration, rollback, performance, and release evidence gates."),
                ("security", "data_migration", "Security-sensitive data handling requires the high-risk data/security gate set."),
                ("permission", "data_migration", "Permission changes require security, test, and release evidence gates."),
                ("configuration", "data_migration", "Configuration changes require configuration, rollback, and release evidence gates."),
                ("performance", "data_migration", "Performance-sensitive changes require performance and release evidence gates."),
                ("release", "data_migration", "Release-sensitive changes require production readiness gates."),
                ("api", "cross_repo_api", "API changes require contract and traceability gates."),
                ("ui", "frontend_change", "UI changes require frontend acceptance evidence."),
                ("frontend", "frontend_change", "Frontend changes require browser acceptance evidence."),
            ]
            base_profile = {}
            for impact, profile_name, item_reason in priority:
                if impact in impacts and profile_name in profiles:
                    base_profile = profiles[profile_name]
                    mode = "impact_surface"
                    reason = item_reason
                    break
            if not base_profile:
                for profile in profiles.values():
                    if lane and lane in {str(item) for item in as_list(profile.get("trigger_lanes"))}:
                        base_profile = profile
                        mode = "lane"
                        reason = f"Spec lane {lane} is declared in profile trigger_lanes."
                        break
            if not base_profile:
                base_profile = profiles.get("small_feature", {"name": "small_feature", "required_skills": [], "expected_artifacts": []})
                mode = "fallback"
                reason = "No explicit, repository, impact, or lane trigger matched; using default small feature workflow."
    overlay_names = [name for name in impact_overlay_profile_names(impacts, has_repo) if name in profiles and name != str(base_profile.get("name") or "")]
    overlays = [profiles[name] for name in overlay_names]
    selected = merge_workflow_profiles(base_profile, overlays) if overlays else base_profile
    selected_name = str(selected.get("name") or base_profile.get("name") or "small_feature")
    primary_impact = next((item for item in ["data", "security", "api", "ui"] if item in impacts), "")
    payload = reason_payload(
        mode,
        selected_name,
        reason,
        matched_impact=primary_impact,
        base_profile=str(base_profile.get("name") or ""),
        overlay_profiles=overlay_names,
        composition_mode=selected.get("composition_mode", "single"),
        applicability=applicability_decisions(spec),
    )
    if overlay_names:
        base_name = str(base_profile.get("name") or "")
        base_score = int(next((item.get("score", 0) for item in candidates if item.get("profile") == base_name), 0) or 0)
        overlay_score = sum(int(next((item.get("score", 0) for item in candidates if item.get("profile") == name), 0) or 0) for name in overlay_names)
        payload["profile_selection_score"] = base_score + overlay_score
    return selected, payload


def select_workflow_profile(spec: dict[str, Any], has_repo: bool = False, explicit_profile: str | None = None) -> dict[str, Any]:
    return select_workflow_profile_with_reason(spec, has_repo, explicit_profile)[0]


def missing_profile_artifacts(profile: dict[str, Any], out: Path) -> list[str]:
    return [str(item) for item in as_list(profile.get("expected_artifacts")) if not (out / str(item)).exists()]


def nested_value(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def canonical_artifact_digest(data: dict[str, Any]) -> str:
    return WORKFLOW_CONTRACT.canonical_digest(data)


def profile_gate_gaps(profile: dict[str, Any], out: Path) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for gate in as_list(profile.get("required_gate_artifacts")):
        if not isinstance(gate, dict):
            gaps.append({"artifact": "", "message": "required_gate_artifacts entry is not an object"})
            continue
        artifact_name = str(gate.get("artifact") or "")
        if not artifact_name:
            gaps.append({"artifact": "", "message": "required gate artifact is missing artifact path"})
            continue
        data = read_json(out / artifact_name)
        if not data:
            gaps.append({"artifact": artifact_name, "message": "artifact is missing or invalid"})
            continue
        accepted = {str(item) for item in as_list(gate.get("accepted_decisions"))}
        decision = str(data.get("decision") or data.get("status") or "")
        if accepted and not decision:
            gaps.append({"artifact": artifact_name, "message": "decision/status is missing", "accepted_decisions": sorted(accepted)})
        elif accepted and decision not in accepted:
            gaps.append({"artifact": artifact_name, "message": f"decision {decision} not accepted", "accepted_decisions": sorted(accepted)})
        readiness_path = str(gate.get("readiness_path") or "")
        if readiness_path and nested_value(data, readiness_path) != gate.get("readiness_value"):
            gaps.append({"artifact": artifact_name, "message": f"{readiness_path} is not {gate.get('readiness_value')}"})
        digest_source = str(gate.get("digest_source") or "")
        digest_path = str(gate.get("digest_path") or "")
        if digest_source and digest_path:
            source_data = read_json(out / digest_source)
            actual_digest = nested_value(data, digest_path)
            expected_digest = canonical_artifact_digest(source_data) if source_data else ""
            if not expected_digest or actual_digest != expected_digest:
                gaps.append({"artifact": artifact_name, "message": f"{digest_path} does not match current {digest_source}"})
    return gaps


def profile_requires(profile: dict[str, Any], skill: str) -> bool:
    return skill in {str(item) for item in as_list(profile.get("required_skills"))}


def render_command_item(value: Any, artifact_dir: Path) -> str:
    return str(value).replace("{artifact_dir}", str(artifact_dir))


def run_registry_artifact_steps(
    profile: dict[str, Any],
    out: Path,
    force: bool,
    generated: list[str],
    skipped: list[str],
    steps: list[dict[str, Any]],
    skip_artifacts: set[str] | None = None,
) -> bool:
    registry_steps = [item for item in as_list(profile.get("artifact_steps")) if isinstance(item, dict)]
    if not registry_steps:
        return False
    skip_artifacts = skip_artifacts or set()
    for item in registry_steps:
        name = str(item.get("name") or item.get("artifact") or "artifact_step")
        artifact = str(item.get("artifact") or "")
        command = [render_command_item(part, out) for part in as_list(item.get("command"))]
        if artifact in skip_artifacts:
            skipped.append(artifact)
            steps.append({"name": name, "skipped": True, "cache_status": "not_applicable", "output": str(out / artifact), "reason": "artifact is generated in pre-technical stage"})
            continue
        if not artifact or not command:
            steps.append({"name": name, "returncode": 1, "passed": False, "reason": "artifact_steps entry requires artifact and command"})
            continue
        target = out / artifact
        inputs = WORKFLOW_CONTRACT.command_input_paths(command, target) + workflow_stage_inputs(target)
        inputs = list({str(path): path for path in inputs}.values())
        if target.exists() and not force and WORKFLOW_CONTRACT.lineage_is_fresh(target, inputs):
            skipped.append(target.name)
            steps.append({"name": name, "skipped": True, "cache_status": "reused", "output": str(target), "reason": "artifact inputs are unchanged"})
            continue
        cache_status = "forced" if target.exists() and force else "invalidated" if target.exists() else "miss"
        result = run_command(name, command)
        if item.get("allow_fail"):
            result["allowed_failure"] = True
            result["passed"] = True
        steps.append(result | {"output": str(target), "cache_status": cache_status})
        if target.exists():
            WORKFLOW_CONTRACT.bind_lineage(target, name, inputs, command=command, workspace=ROOT)
            generated.append(target.name)
    return True


def run_profile_artifact_steps(
    profile: dict[str, Any],
    out: Path,
    spec: Path,
    technical: Path,
    architecture: Path,
    force: bool,
    generated: list[str],
    skipped: list[str],
    steps: list[dict[str, Any]],
) -> None:
    if run_registry_artifact_steps(
        profile,
        out,
        force,
        generated,
        skipped,
        steps,
        skip_artifacts={
            "domain_model_design.json",
            "architecture_framing.json",
            "ui_ue_design.json",
            "ui_ue_review.json",
            "api_contract_design.json",
            "data_model_design.json",
            "observability_design.json",
            "cross_repo_readiness.json",
            "cross_repo_execution_graph.json",
            "cross_repo_release_plan.json",
        },
    ):
        return
    if profile_requires(profile, "frontend-acceptance-runner"):
        run_if_needed(
            "frontend_acceptance_template",
            out / "frontend_acceptance.json",
            [
                "python3",
                "skills/core/frontend-acceptance-runner/scripts/frontend_acceptance.py",
                "template",
                "--page-type",
                "custom",
                "--target-url",
                "http://localhost/TBD",
                "--artifact-dir",
                str(out),
                "--out",
                str(out / "frontend_acceptance.json"),
            ],
            force,
            generated,
            skipped,
            steps,
        )
    if profile_requires(profile, "configuration-governor"):
        run_if_needed(
            "configuration_review",
            out / "configuration_readiness.json",
            [
                "python3",
                "skills/core/configuration-governor/scripts/configuration.py",
                "analyze",
                "--spec",
                str(spec),
                "--technical-design",
                str(technical),
                "--architecture-design",
                str(architecture),
                "--out",
                str(out / "configuration_readiness.json"),
            ],
            force,
            generated,
            skipped,
            steps,
        )
    if profile_requires(profile, "data-security-governor"):
        run_if_needed(
            "data_security_review",
            out / "data_security_review.json",
            [
                "python3",
                "skills/core/data-security-governor/scripts/data_security.py",
                "design",
                "--spec",
                str(spec),
                "--technical-design",
                str(technical),
                "--architecture-design",
                str(architecture),
                "--out",
                str(out / "data_security_review.json"),
            ],
            force,
            generated,
            skipped,
            steps,
        )
    if profile_requires(profile, "performance-governor"):
        run_if_needed(
            "performance_review",
            out / "performance_review.json",
            [
                "python3",
                "skills/core/performance-governor/scripts/performance.py",
                "design",
                "--spec",
                str(spec),
                "--technical-design",
                str(technical),
                "--architecture-design",
                str(architecture),
                "--out",
                str(out / "performance_review.json"),
            ],
            force,
            generated,
            skipped,
            steps,
        )
    if profile_requires(profile, "test-evidence-gate"):
        command = [
            "python3",
            "skills/core/test-evidence-gate/scripts/test_evidence_gate.py",
            "--artifact-dir",
            str(out),
            "--out",
            str(out / "test_evidence_gate.json"),
        ]
        if profile_requires(profile, "frontend-acceptance-runner"):
            command.append("--require-frontend")
        run_if_needed("test_evidence_gate", out / "test_evidence_gate.json", command, force, generated, skipped, steps)


def run_pre_review_planning_steps(
    profile: dict[str, Any],
    out: Path,
    spec: Path,
    delivery_plan: Path,
    force: bool,
    generated: list[str],
    skipped: list[str],
    steps: list[dict[str, Any]],
) -> None:
    if profile_requires(profile, "cross-repo-planner"):
        run_if_needed(
            "cross_repo_plan",
            out / "cross_repo_readiness.json",
            [
                "python3",
                "skills/core/cross-repo-planner/scripts/cross_repo_plan.py",
                "plan",
                "--spec",
                str(spec),
                "--delivery-plan",
                str(delivery_plan),
                "--out-dir",
                str(out),
            ],
            force,
            generated,
            skipped,
            steps,
        )


def run_initial_traceability(
    out: Path,
    force: bool,
    generated: list[str],
    skipped: list[str],
    steps: list[dict[str, Any]],
) -> None:
    before = len(steps)
    run_if_needed(
        "initial_traceability",
        out / "traceability_matrix.json",
        [
            "python3",
            "skills/core/traceability-governor/scripts/traceability.py",
            "--artifact-dir",
            str(out),
            "--out",
            str(out / "traceability_matrix.json"),
        ],
        force,
        generated,
        skipped,
        steps,
    )
    if len(steps) > before:
        steps[-1]["traceability_phase"] = "initial_design_plan"


def run_requirement_questions(
    profile: dict[str, Any],
    out: Path,
    spec: Path,
    force: bool,
    generated: list[str],
    skipped: list[str],
    steps: list[dict[str, Any]],
) -> Path | None:
    if not profile_requires(profile, "requirement-question-governor"):
        return None
    questions = out / "open_questions.json"
    run_if_needed(
        "requirement_questions",
        questions,
        [
            "python3",
            "skills/core/requirement-question-governor/scripts/question_governor.py",
            "generate",
            "--spec",
            str(spec),
            "--out",
            str(questions),
        ],
        True,
        generated,
        skipped,
        steps,
    )
    return questions


def run_design_assurance_steps(
    profile: dict[str, Any],
    out: Path,
    spec: Path,
    technical: Path,
    architecture: Path,
    force: bool,
    generated: list[str],
    skipped: list[str],
    steps: list[dict[str, Any]],
) -> None:
    """Run design-time configuration, security, and performance gates before design approval."""
    for skill, name, artifact, command in [
        (
            "configuration-governor",
            "configuration_review",
            "configuration_readiness.json",
            ["python3", "skills/core/configuration-governor/scripts/configuration.py", "analyze"],
        ),
        (
            "data-security-governor",
            "data_security_review",
            "data_security_review.json",
            ["python3", "skills/core/data-security-governor/scripts/data_security.py", "design"],
        ),
        (
            "performance-governor",
            "performance_review",
            "performance_review.json",
            ["python3", "skills/core/performance-governor/scripts/performance.py", "design"],
        ),
    ]:
        if not profile_requires(profile, skill):
            continue
        run_if_needed(
            name,
            out / artifact,
            command + ["--spec", str(spec), "--technical-design", str(technical), "--architecture-design", str(architecture), "--out", str(out / artifact)],
            force,
            generated,
            skipped,
            steps,
        )


def run_pre_technical_design_steps(
    profile: dict[str, Any],
    out: Path,
    spec: Path,
    project_out: Path | None,
    force: bool,
    generated: list[str],
    skipped: list[str],
    steps: list[dict[str, Any]],
) -> None:
    if profile_requires(profile, "domain-model-governor"):
        run_if_needed(
            "domain_model_design",
            out / "domain_model_design.json",
            [
                "python3",
                "skills/core/domain-model-governor/scripts/domain_model.py",
                "--spec",
                str(spec),
                "--out",
                str(out / "domain_model_design.json"),
            ],
            force,
            generated,
            skipped,
            steps,
        )
    if profile_requires(profile, "architecture-framing-governor"):
        command = [
            "python3",
            "skills/core/architecture-framing-governor/scripts/architecture_framing.py",
            "--spec",
            str(spec),
            "--out",
            str(out / "architecture_framing.json"),
        ]
        if (out / "domain_model_design.json").exists():
            command.extend(["--domain-model-design", str(out / "domain_model_design.json")])
        if project_out:
            command.extend(["--project-understanding", str(project_out)])
        run_if_needed("architecture_framing", out / "architecture_framing.json", command, force, generated, skipped, steps)
    if profile_requires(profile, "ui-ue-design-governor"):
        command = [
            "python3",
            "skills/core/ui-ue-design-governor/scripts/ui_ue_design.py",
            "--spec",
            str(spec),
            "--out",
            str(out / "ui_ue_design.json"),
        ]
        run_if_needed("ui_ue_design", out / "ui_ue_design.json", command, force, generated, skipped, steps)
    if profile_requires(profile, "ui-ue-reviewer"):
        run_if_needed(
            "ui_ue_review",
            out / "ui_ue_review.json",
            [
                "python3",
                "skills/core/ui-ue-reviewer/scripts/ui_ue_review.py",
                "--ui-ue-design",
                str(out / "ui_ue_design.json"),
                "--out",
                str(out / "ui_ue_review.json"),
            ],
            force,
            generated,
            skipped,
            steps,
        )
    if profile_requires(profile, "api-contract-governor"):
        command = [
            "python3",
            "skills/core/api-contract-governor/scripts/api_contract.py",
            "--spec",
            str(spec),
            "--out",
            str(out / "api_contract_design.json"),
        ]
        if (out / "architecture_framing.json").exists():
            command.extend(["--architecture-framing", str(out / "architecture_framing.json")])
        run_if_needed("api_contract_design", out / "api_contract_design.json", command, force, generated, skipped, steps)
    if profile_requires(profile, "data-model-governor"):
        command = [
            "python3",
            "skills/core/data-model-governor/scripts/data_model.py",
            "--spec",
            str(spec),
            "--out",
            str(out / "data_model_design.json"),
        ]
        if (out / "architecture_framing.json").exists():
            command.extend(["--architecture-framing", str(out / "architecture_framing.json")])
        run_if_needed("data_model_design", out / "data_model_design.json", command, force, generated, skipped, steps)
    if profile_requires(profile, "observability-design-governor"):
        command = [
            "python3",
            "skills/core/observability-design-governor/scripts/observability_design.py",
            "--spec",
            str(spec),
            "--out",
            str(out / "observability_design.json"),
        ]
        if (out / "architecture_framing.json").exists():
            command.extend(["--architecture-framing", str(out / "architecture_framing.json")])
        run_if_needed("observability_design", out / "observability_design.json", command, force, generated, skipped, steps)


def run_post_technical_design_steps(
    profile: dict[str, Any],
    out: Path,
    technical: Path,
    force: bool,
    generated: list[str],
    skipped: list[str],
    steps: list[dict[str, Any]],
) -> None:
    if profile_requires(profile, "frontend-implementation-planner"):
        run_if_needed(
            "frontend_implementation_plan",
            out / "frontend_implementation_plan.json",
            [
                "python3",
                "skills/core/frontend-implementation-planner/scripts/frontend_plan.py",
                "--ui-ue-design",
                str(out / "ui_ue_design.json"),
                "--technical-design",
                str(technical),
                "--out",
                str(out / "frontend_implementation_plan.json"),
            ],
            force,
            generated,
            skipped,
            steps,
        )


def run_release_profile_steps(
    out: Path,
    force: bool,
    generated: list[str],
    skipped: list[str],
    steps: list[dict[str, Any]],
) -> None:
    for name, script, artifact in [
        ("environment_promotion_template", "skills/core/environment-promotion-governor/scripts/environment_promotion.py", "environment_promotion.json"),
        ("uat_acceptance_template", "skills/core/uat-acceptance-governor/scripts/uat_acceptance.py", "uat_acceptance.json"),
        ("release_change_template", "skills/core/release-change-governor/scripts/release_change.py", "release_change.json"),
    ]:
        run_if_needed(name, out / artifact, ["python3", script, "template", "--out", str(out / artifact)], force, generated, skipped, steps)
    run_if_needed(
        "release_evidence_binder",
        out / "release_gate.json",
        [
            "python3",
            "skills/core/release-evidence-binder/scripts/bind_release.py",
            "--artifact-dir",
            str(out),
            "--out",
            str(out / "release_gate.json"),
        ],
        force,
        generated,
        skipped,
        steps,
    )


def run(
    input_path: Path,
    doc_id: str | None = None,
    title: str | None = None,
    repo: Path | None = None,
    project: str | None = None,
    out: Path | None = None,
    force: bool = False,
    profile: str | None = None,
    docs_root: Path | None = None,
    doc_language: str = "auto",
) -> dict[str, Any]:
    global RUNTIME_ARTIFACT_DIR
    input_path = input_path.resolve()
    input_text = input_path.read_text(encoding="utf-8", errors="ignore") if input_path.exists() else ""
    effective_doc_language = infer_doc_language(input_text, doc_language)
    doc_id = doc_id or default_doc_id(input_path)
    title = title or default_title(input_path)
    effective_docs_root = docs_root.resolve() if docs_root else default_docs_root()
    if docs_root:
        out = canonical_docs_artifact_dir(docs_root.resolve(), doc_id)
    else:
        out = (out or default_out(doc_id)).resolve()
    out.mkdir(parents=True, exist_ok=True)
    docs_status = docs_readiness(effective_docs_root, doc_id, out)
    resolved_repo, resolved_project, project_binding = resolve_project_binding(input_text, repo, project)
    if resolved_repo:
        repo = resolved_repo
    if resolved_project:
        project = resolved_project
    write_json(out / "auto_run_summary.json", {
        "schema": SCHEMA,
        "decision": "in_progress",
        "doc_id": doc_id,
        "title": title,
        "out_dir": str(out),
        "docs_readiness": docs_status,
        "local_project_binding": project_binding,
    })

    generated: list[str] = []
    skipped: list[str] = []
    steps: list[dict[str, Any]] = []
    explicit_profiles = load_profile_registry()
    selected_profile = explicit_profiles.get(profile, {}) if profile else {}
    runtime_session = AGENT_RUNTIME.start(
        out,
        doc_id,
        str(selected_profile.get("name") or profile or "auto"),
        [repo] if repo else [],
    )
    RUNTIME_ARTIFACT_DIR = out
    generated.extend(["runtime/session.json", "runtime/events.jsonl"])
    profile_selection_reason: dict[str, Any] = {}
    if selected_profile.get("profile_stage_mode") == "release_only":
        profile_selection_reason = {
            "mode": "explicit_profile",
            "selected_profile": str(selected_profile.get("name") or profile or ""),
            "reason": "Release-only profile was explicitly requested.",
        }
        run_registry_artifact_steps(selected_profile, out, force, generated, skipped, steps)
        finalize_runtime_lineage(out)
        delivery_status = out / "delivery_status.json"
        inspect_result = run_command(
            "inspect",
            [
                "python3",
                "skills/core/delivery-runner/scripts/delivery_runner.py",
                "inspect",
                "--artifact-dir",
                str(out),
                "--profile",
                str(profile or ""),
                "--out",
                str(delivery_status),
            ],
        )
        steps.append(inspect_result)
        inspect_status = read_json(delivery_status)
        effective_doc_language = infer_artifact_doc_language(out, doc_language, effective_doc_language)
        docs_sync = sync_docs_artifacts(effective_docs_root, doc_id, title, out, effective_doc_language)
        if docs_sync.get("decision") == "pass":
            docs_status = docs_readiness(effective_docs_root, doc_id, out)
        strictness = workflow_strictness({}, selected_profile, profile_selection_reason.get("profile_selection_confidence", ""))
        effective_profile = effective_profile_for_strictness(selected_profile, strictness)
        blockers = collect_blockers(steps, inspect_status)
        if docs_sync.get("decision") == "block":
            blockers.extend(docs_sync.get("blockers", []))
        strictness_gaps = strictness_gate_gaps(selected_profile, strictness)
        blockers.extend(strictness_gaps)
        missing_profile = missing_profile_artifacts(effective_profile, out)
        gate_gaps = profile_gate_gaps(effective_profile, out)
        blockers.extend({"source": "profile_artifact", "message": f"missing required artifact {name}"} for name in missing_profile)
        blockers.extend({"source": "profile_gate", **item} for item in gate_gaps)
        summary = {
            "schema": SCHEMA,
            "decision": "block" if blockers else "pass",
            "doc_id": doc_id,
            "title": title,
            "input": str(input_path),
            "out_dir": str(out),
            "generated_artifacts": sorted(set(generated)),
            "skipped_artifacts": skipped,
            "steps": steps,
            "workflow_metrics": workflow_metrics(steps, generated, skipped, selected_profile),
            "workflow_profile": selected_profile,
            "profile_selection_reason": profile_selection_reason,
            "profile_selection_score": profile_selection_reason.get("profile_selection_score", 0),
            "profile_selection_confidence": profile_selection_reason.get("profile_selection_confidence", ""),
            "profile_selection_candidates": profile_selection_reason.get("profile_selection_candidates", []),
            "workflow_strictness": strictness,
            "effective_workflow_controls": effective_workflow_controls(selected_profile, strictness),
            "strictness_gate_gaps": strictness_gaps,
            "fallback_reason": profile_selection_reason.get("fallback_reason", ""),
            "required_gates": required_gate_artifact_names(selected_profile),
            "docs_readiness": docs_status,
            "docs_sync": docs_sync,
            "doc_language": effective_doc_language,
            "missing_profile_artifacts": missing_profile,
            "profile_gate_gaps": gate_gaps,
            "next_profile_command": selected_profile.get("next_safe_command", ""),
            "blockers": blockers,
            "inspect_status": inspect_status,
            "next_stage": inspect_status.get("next_stage", ""),
            "next_command": inspect_status.get("next_command", ""),
            "can_implement": bool(inspect_status.get("can_implement")),
            "can_release": bool(inspect_status.get("can_release")),
            "safety_boundary": "release_artifact_inspection_only",
        }
        write_json(out / "auto_run_summary.json", summary)
        return summary

    normalized = out / "requirement.normalized.txt"
    run_if_needed(
        "ingest",
        out / "requirement_ingestion.json",
        [
            "python3",
            "skills/core/requirement-document-ingestor/scripts/ingest_requirement.py",
            "--input",
            str(input_path),
            "--doc-id",
            doc_id,
            "--out-dir",
            str(out),
        ],
        force,
        generated,
        skipped,
        steps,
    )
    if (out / "requirement_ir.json").exists():
        generated.append("requirement_ir.json")

    spec_input = normalized
    clarification_answers = out / "clarification_answers.md"
    if clarification_answers.exists() and clarification_answers.read_text(encoding="utf-8").strip():
        clarified = out / "requirement.clarified.txt"
        clarified.write_text(
            normalized.read_text(encoding="utf-8").rstrip()
            + "\n\n# Confirmed requirement clarifications\n\n"
            + clarification_answers.read_text(encoding="utf-8").strip()
            + "\n",
            encoding="utf-8",
        )
        spec_input = clarified
        refresh_clarified_requirement_ir(out, doc_id, clarified, generated)
        generated.append(clarified.name)

    if "requirement_ingestion.json" not in skipped or not (out / "runtime/checkpoints/intake.json").exists() or spec_input.name == "requirement.clarified.txt":
        AGENT_RUNTIME.append_event(
            out,
            "requirement_ingested",
            "requirement-document-ingestor",
            target=str(spec_input),
            evidence_refs=["requirement_ingestion.json", "requirement_ir.json"],
        )
        AGENT_RUNTIME.checkpoint(out, "intake", ["requirement_ingestion.json", "requirement_ir.json"])
        generated.append("runtime/checkpoints/intake.json")

    if repo and project:
        project_out = out / "project_understanding"
        marker = project_out / "baseline_quality.json"
        run_if_needed(
            "project_understanding",
            marker,
            [
                "python3",
                "skills/core/project-understanding-runner/scripts/project_understand.py",
                "--repo",
                str(repo),
                "--project",
                project,
                "--out",
                str(project_out),
            ],
            force,
            generated,
            skipped,
            steps,
        )
    else:
        project_out = None

    if project_out and repo:
        project_skill_dir = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "skills" / "company" / str(project)
        source_location_command = [
            "python3",
            "skills/core/code-index-lookup/scripts/source_location_evidence.py",
            "--repo",
            str(repo),
            "--index",
            str(project_out / "code_index.json"),
            "--requirement",
            str(spec_input),
            "--out",
            str(project_out / "source_location_evidence.json"),
            "--bundle-out",
            str(project_out / "evidence_bundle.json"),
        ]
        source_location_command.extend(["--project-skill-dir", str(project_skill_dir)])
        run_if_needed(
            "source_location_evidence",
            project_out / "source_location_evidence.json",
            source_location_command,
            force,
            generated,
            skipped,
            steps,
        )
        if (project_out / "evidence_bundle.json").exists():
            generated.append("evidence_bundle.json")
        source_harness_output = out / "harness/source_location.json"
        run_if_needed(
            "harness_source_location",
            source_harness_output,
            [
                "python3",
                "skills/core/auto-runner/scripts/harness_validation.py",
                "--artifact-dir",
                str(out),
                "--checkpoint",
                "source_location",
                "--policy",
                "config/harness-policy.example.yaml",
                "--repo",
                str(repo),
                "--out",
                str(source_harness_output),
            ],
            force,
            generated,
            skipped,
            steps,
        )

    spec = out / "spec.json"
    spec_command = [
        "python3",
        "skills/core/spec-governor/scripts/spec_governor.py",
        "normalize",
        "--doc-id",
        doc_id,
        "--title",
        title,
        "--input",
        str(spec_input),
        "--out",
        str(spec),
    ]
    if project_out:
        spec_command.extend(["--project-understanding", str(project_out)])
    if (out / "requirement_ir.json").exists():
        spec_command.extend(["--requirement-ir", str(out / "requirement_ir.json")])
    run_if_needed(
        "spec",
        spec,
        spec_command,
        force,
        generated,
        skipped,
        steps,
    )
    spec_data = read_json(spec)
    selected_profile, profile_selection_reason = select_workflow_profile_with_reason(spec_data, bool(repo and project), profile)

    run_requirement_questions(selected_profile, out, spec, force, generated, skipped, steps)

    if spec_data.get("decision") == "blocked" or spec_data.get("design_allowed") is False:
        strictness = workflow_strictness(spec_data, selected_profile, profile_selection_reason.get("profile_selection_confidence", ""))
        location_status = source_location_readiness(out, project_out)
        effective_doc_language = infer_artifact_doc_language(out, doc_language, effective_doc_language)
        docs_sync = sync_docs_artifacts(effective_docs_root, doc_id, title, out, effective_doc_language, human_section="spec")
        if docs_sync.get("decision") == "pass":
            docs_status = docs_readiness(effective_docs_root, doc_id, out)
        blockers = collect_blockers(steps, {}, include_inspect=False)
        blockers.extend(
            item for item in as_list((spec_data.get("requirements_understanding") or {}).get("blockers"))
            if isinstance(item, dict)
        )
        if not blockers:
            blockers.append({"source": "spec", "message": "spec blocks downstream design"})
        summary = {
            "schema": SCHEMA,
            "decision": "block",
            "stage_result": {"decision": "block", "can_continue": False, "exit_code": 2, "blockers": blockers},
            "doc_id": doc_id,
            "title": title,
            "input": str(input_path),
            "out_dir": str(out),
            "generated_artifacts": sorted(set(generated)),
            "skipped_artifacts": skipped,
            "steps": steps,
            "workflow_metrics": workflow_metrics(steps, generated, skipped, selected_profile),
            "workflow_profile": selected_profile,
            "profile_selection_reason": profile_selection_reason,
            "profile_selection_score": profile_selection_reason.get("profile_selection_score", 0),
            "profile_selection_confidence": profile_selection_reason.get("profile_selection_confidence", ""),
            "profile_selection_candidates": profile_selection_reason.get("profile_selection_candidates", []),
            "impact_applicability": applicability_decisions(spec_data),
            "workflow_strictness": strictness,
            "effective_workflow_controls": effective_workflow_controls(selected_profile, strictness),
            "required_gates": required_gate_artifact_names(selected_profile),
            "source_location_readiness": location_status,
            "docs_readiness": docs_status,
            "docs_sync": docs_sync,
            "doc_language": effective_doc_language,
            "blockers": blockers,
            "next_stage": "requirements_clarification",
            "next_command": f"python3 scripts/codex_eng.py clarify --artifact-dir {out}",
            "can_implement": False,
            "can_release": False,
            "safety_boundary": "requirements_and_questions_only",
        }
        finalize_runtime_lineage(out)
        write_json(out / "auto_run_summary.json", summary)
        return summary

    run_pre_technical_design_steps(selected_profile, out, spec, project_out, force, generated, skipped, steps)

    technical = out / "technical_design.json"
    technical_command = ["python3", "skills/core/technical-design-governor/scripts/technical_design.py", "--spec", str(spec), "--out", str(technical)]
    if project_out:
        technical_command.extend(["--project-understanding", str(project_out)])
    for arg_name, file_name in [
        ("--architecture-framing", "architecture_framing.json"),
        ("--domain-model-design", "domain_model_design.json"),
        ("--ui-ue-design", "ui_ue_design.json"),
        ("--api-contract-design", "api_contract_design.json"),
        ("--data-model-design", "data_model_design.json"),
        ("--observability-design", "observability_design.json"),
    ]:
        artifact = out / file_name
        if artifact.exists():
            technical_command.extend([arg_name, str(artifact)])
    run_if_needed(
        "technical_design",
        technical,
        technical_command,
        force,
        generated,
        skipped,
        steps,
    )

    run_post_technical_design_steps(selected_profile, out, technical, force, generated, skipped, steps)

    architecture = out / "architecture_design.json"
    architecture_command = [
        "python3",
        "skills/core/architecture-design-governor/scripts/architecture_design.py",
        "--spec",
        str(spec),
        "--technical-design",
        str(technical),
        "--out",
        str(architecture),
    ]
    if project_out:
        architecture_command.extend(["--project-understanding", str(project_out)])
    if (out / "architecture_framing.json").exists():
        architecture_command.extend(["--architecture-framing", str(out / "architecture_framing.json")])
    run_if_needed(
        "architecture_design",
        architecture,
        architecture_command,
        force,
        generated,
        skipped,
        steps,
    )

    run_design_assurance_steps(selected_profile, out, spec, technical, architecture, force, generated, skipped, steps)

    if profile_requires(selected_profile, "cross-repo-planner"):
        delivery_plan_draft = out / "delivery_plan_draft.json"
        draft_command = [
            "python3",
            "skills/templates/delivery-plan-templates/scripts/render_delivery_plan.py",
            "--doc-id",
            doc_id,
            "--technical-design",
            str(technical),
            "--architecture-design",
            str(architecture),
            "--out",
            str(delivery_plan_draft),
        ]
        if project_out:
            draft_command.extend(["--project-understanding", str(project_out)])
        run_if_needed(
            "delivery_plan_draft",
            delivery_plan_draft,
            draft_command,
            force,
            generated,
            skipped,
            steps,
        )
        run_pre_review_planning_steps(selected_profile, out, spec, delivery_plan_draft, force, generated, skipped, steps)

    test_design = out / "test_design.json"
    run_if_needed(
        "test_design",
        test_design,
        [
            "python3",
            "skills/core/test-design-governor/scripts/test_design.py",
            "render",
            "--spec",
            str(spec),
            "--technical-design",
            str(technical),
            "--architecture-design",
            str(architecture),
            "--out",
            str(test_design),
        ],
        force,
        generated,
        skipped,
        steps,
    )

    design_review = out / "design_architecture_review.json"
    design_review_command = [
        "python3",
        "skills/core/design-architecture-reviewer/scripts/design_arch_review.py",
        "review",
        "--technical-design",
        str(technical),
        "--architecture-design",
        str(architecture),
        "--out",
        str(design_review),
    ]
    architecture_framing_artifact = out / "architecture_framing.json"
    if architecture_framing_artifact.exists():
        design_review_command.extend(["--architecture-framing", str(architecture_framing_artifact)])
    for argument, artifact_name in [
        ("--ui-ue-design", "ui_ue_design.json"),
        ("--ui-ue-review", "ui_ue_review.json"),
        ("--api-contract-design", "api_contract_design.json"),
        ("--data-model-design", "data_model_design.json"),
        ("--observability-design", "observability_design.json"),
        ("--configuration-readiness", "configuration_readiness.json"),
        ("--data-security-review", "data_security_review.json"),
        ("--performance-review", "performance_review.json"),
        ("--cross-repo-readiness", "cross_repo_readiness.json"),
        ("--test-design", "test_design.json"),
    ]:
        artifact = out / artifact_name
        if artifact.exists():
            design_review_command.extend([argument, str(artifact)])
    run_if_needed(
        "design_review",
        design_review,
        design_review_command,
        force,
        generated,
        skipped,
        steps,
    )

    test_data_plan = out / "test_data_plan.json"
    run_if_needed(
        "test_data_plan",
        test_data_plan,
        [
            "python3",
            "skills/core/test-data-governor/scripts/test_data.py",
            "render",
            "--test-design",
            str(test_design),
            "--out",
            str(test_data_plan),
        ],
        force,
        generated,
        skipped,
        steps,
    )

    delivery_plan = out / "delivery_plan.json"
    delivery_command = [
        "python3",
        "skills/templates/delivery-plan-templates/scripts/render_delivery_plan.py",
        "--doc-id",
        doc_id,
        "--technical-design",
        str(technical),
        "--architecture-design",
        str(architecture),
        "--out",
        str(delivery_plan),
    ]
    if project_out:
        delivery_command.extend(["--project-understanding", str(project_out)])
    delivery_command.extend([
        "--design-review",
        str(design_review),
        "--test-design",
        str(test_design),
        "--test-data-plan",
        str(test_data_plan),
    ])
    if (out / "cross_repo_readiness.json").exists():
        delivery_command.extend(["--cross-repo-readiness", str(out / "cross_repo_readiness.json")])
    run_if_needed(
        "delivery_plan",
        delivery_plan,
        delivery_command,
        force,
        generated,
        skipped,
        steps,
    )

    if profile_requires(selected_profile, "traceability-governor"):
        run_initial_traceability(out, force, generated, skipped, steps)

    delivery_plan_review = out / "delivery_plan_review.json"
    run_if_needed(
        "delivery_plan_review",
        delivery_plan_review,
        [
            "python3",
            "skills/core/delivery-plan-reviewer/scripts/delivery_plan_review.py",
            "review",
            "--file",
            str(delivery_plan),
            "--out",
            str(delivery_plan_review),
        ],
        force,
        generated,
        skipped,
        steps,
    )
    run_profile_artifact_steps(selected_profile, out, spec, technical, architecture, force, generated, skipped, steps)

    design_outputs = {
        "spec.json",
        "technical_design.json",
        "architecture_design.json",
        "delivery_plan.json",
        "delivery_plan_review.json",
    }
    if design_outputs & set(generated) or not (out / "runtime/checkpoints/design.json").exists():
        AGENT_RUNTIME.append_event(
            out,
            "design_completed",
            "auto-runner",
            evidence_refs=sorted(design_outputs),
        )
        AGENT_RUNTIME.checkpoint(
            out,
            "design",
            ["technical_design.json", "architecture_design.json", "delivery_plan.json", "delivery_plan_review.json"],
        )
        generated.append("runtime/checkpoints/design.json")

    harness_output = out / "harness_validation.json"
    run_if_needed(
        "harness_design",
        harness_output,
        [
            "python3",
            "skills/core/auto-runner/scripts/harness_validation.py",
            "--artifact-dir",
            str(out),
            "--checkpoint",
            "design",
            "--policy",
            "config/harness-policy.example.yaml",
            *(["--repo", str(repo)] if repo else []),
            "--out",
            str(harness_output),
        ],
        force,
        generated,
        skipped,
        steps,
    )

    finalize_runtime_lineage(out)
    effective_doc_language = infer_artifact_doc_language(out, doc_language, effective_doc_language)
    docs_sync = sync_docs_artifacts(effective_docs_root, doc_id, title, out, effective_doc_language)
    if docs_sync.get("decision") == "pass":
        docs_status = docs_readiness(effective_docs_root, doc_id, out)
    docs_quality = run_docs_quality(effective_docs_root, docs_sync, out)
    if (out / "docs_quality.json").exists():
        WORKFLOW_CONTRACT.bind_lineage(
            out / "docs_quality.json",
            "docs_quality",
            workflow_stage_inputs(out / "docs_quality.json"),
            command=["docs_quality", str(effective_docs_root or "")],
            workspace=ROOT,
        )
        generated.append("docs_quality.json")

    design_blockers = design_phase_blockers(out, steps)
    if design_blockers:
        strictness = workflow_strictness(spec_data, selected_profile, profile_selection_reason.get("profile_selection_confidence", ""))
        location_status = source_location_readiness(out, project_out)
        effective_profile = effective_profile_for_strictness(selected_profile, strictness)
        strictness_gaps = strictness_gate_gaps(selected_profile, strictness)
        design_blockers.extend(strictness_gaps)
        design_blockers = unique_blockers(design_blockers)
        primary_stage = SUMMARY_CONTRACT.primary_blocker_stage(design_blockers, "design_review")
        next_command = "python3 scripts/codex_eng.py clarify --artifact-dir {}".format(out) if primary_stage == "requirements_clarification" else "Resolve design-stage blockers before docs sync or implementation readiness."
        summary = {
            "schema": SCHEMA,
            "decision": "block",
            "stage_result": {"decision": "block", "can_continue": False, "exit_code": 2, "blockers": design_blockers},
            "doc_id": doc_id,
            "title": title,
            "input": str(input_path),
            "out_dir": str(out),
            "generated_artifacts": sorted(set(generated)),
            "skipped_artifacts": skipped,
            "steps": steps,
            "workflow_metrics": workflow_metrics(steps, generated, skipped, selected_profile),
            "workflow_profile": selected_profile,
            "profile_selection_reason": profile_selection_reason,
            "profile_selection_score": profile_selection_reason.get("profile_selection_score", 0),
            "profile_selection_confidence": profile_selection_reason.get("profile_selection_confidence", ""),
            "profile_selection_candidates": profile_selection_reason.get("profile_selection_candidates", []),
            "workflow_strictness": strictness,
            "effective_workflow_controls": effective_workflow_controls(selected_profile, strictness),
            "strictness_gate_gaps": strictness_gaps,
            "required_gates": required_gate_artifact_names(selected_profile),
            "source_location_readiness": location_status,
            "docs_readiness": docs_status,
            "docs_sync": docs_sync,
            "docs_quality": docs_quality,
            "doc_language": effective_doc_language,
            "readiness_blockers": [],
            "missing_profile_artifacts": [],
            "profile_gate_gaps": [],
            "next_profile_command": selected_profile.get("next_safe_command", ""),
            "blockers": design_blockers,
            "inspect_status": {},
            "next_stage": primary_stage,
            "next_command": next_command,
            "can_implement": False,
            "can_release": False,
            "runtime_session": runtime_session,
            "safety_boundary": "analysis_and_artifact_generation_only",
            **SUMMARY_CONTRACT.summary_fields(
                design_blockers,
                primary_stage,
                "fix_blocker",
                next_command,
                {
                    "action_type": "fix_blocker",
                    "stage": primary_stage,
                    "summary": "resolve design-stage blockers",
                    "command": next_command,
                },
            ),
        }
        write_json(out / "auto_run_summary.json", summary)
        return summary

    delivery_status = out / "delivery_status.json"
    inspect_command = [
        "python3",
        "skills/core/delivery-runner/scripts/delivery_runner.py",
        "inspect",
        "--artifact-dir",
        str(out),
        "--out",
        str(delivery_status),
    ]
    if profile:
        inspect_command.extend(["--profile", profile])
    inspect_result = run_command(
        "inspect",
        inspect_command,
    )
    steps.append(inspect_result)
    inspect_status = read_json(delivery_status)
    if not inspect_status and inspect_result.get("stdout_tail"):
        try:
            inspect_status = json.loads(str(inspect_result["stdout_tail"]))
        except Exception:
            inspect_status = {}

    strictness = workflow_strictness(spec_data, selected_profile, profile_selection_reason.get("profile_selection_confidence", ""))
    location_status = source_location_readiness(out, project_out)
    effective_profile = effective_profile_for_strictness(selected_profile, strictness)
    strictness_gaps = strictness_gate_gaps(selected_profile, strictness)
    blockers = collect_blockers(steps, inspect_status, include_inspect=False)
    readiness_blockers = [item for item in inspect_status.get("blockers", []) or [] if isinstance(item, dict)]
    if docs_sync.get("decision") == "block":
        blockers.extend(docs_sync.get("blockers", []))
    if docs_status.get("decision") == "block":
        blockers.extend(docs_status.get("blockers", []))
    if docs_quality.get("decision") == "block":
        blockers.extend(docs_quality.get("blockers", []))
    blockers.extend(strictness_gaps)
    missing_profile = missing_profile_artifacts(effective_profile, out)
    gate_gaps = profile_gate_gaps(effective_profile, out)
    blockers.extend(readiness_blockers)
    blockers.extend({"source": "profile_artifact", "message": f"missing required artifact {name}"} for name in missing_profile)
    blockers.extend({"source": "profile_gate", **item} for item in gate_gaps)
    blockers = unique_blockers(blockers)
    next_stage = str(inspect_status.get("next_stage") or "")
    next_action_type = str(inspect_status.get("next_action_type") or "")
    next_command = str(inspect_status.get("next_command") or "")
    primary_action = inspect_status.get("primary_next_action") if isinstance(inspect_status.get("primary_next_action"), dict) else None
    decision = "block" if blockers or not bool(inspect_status.get("can_implement")) else "pass"
    summary = {
        "schema": SCHEMA,
        "decision": decision,
        "stage_result": {"decision": decision, "can_continue": decision == "pass", "exit_code": 0 if decision == "pass" else 2, "blockers": blockers},
        "doc_id": doc_id,
        "title": title,
        "input": str(input_path),
        "out_dir": str(out),
        "generated_artifacts": sorted(set(generated)),
        "skipped_artifacts": skipped,
        "steps": steps,
        "workflow_metrics": workflow_metrics(steps, generated, skipped, selected_profile),
        "workflow_profile": selected_profile,
        "local_project_binding": project_binding,
        "profile_selection_reason": profile_selection_reason,
        "profile_selection_score": profile_selection_reason.get("profile_selection_score", 0),
        "profile_selection_confidence": profile_selection_reason.get("profile_selection_confidence", ""),
        "profile_selection_candidates": profile_selection_reason.get("profile_selection_candidates", []),
        "workflow_strictness": strictness,
        "effective_workflow_controls": effective_workflow_controls(selected_profile, strictness),
        "strictness_gate_gaps": strictness_gaps,
        "fallback_reason": profile_selection_reason.get("fallback_reason", ""),
        "required_gates": required_gate_artifact_names(selected_profile),
        "source_location_readiness": location_status,
        "docs_readiness": docs_status,
        "docs_sync": docs_sync,
        "docs_quality": docs_quality,
        "doc_language": effective_doc_language,
        "readiness_blockers": readiness_blockers,
        "missing_profile_artifacts": missing_profile,
        "profile_gate_gaps": gate_gaps,
        "next_profile_command": selected_profile.get("next_safe_command", ""),
        "blockers": blockers,
        "inspect_status": inspect_status,
        "next_stage": next_stage,
        "next_command": next_command,
        "can_implement": bool(inspect_status.get("can_implement")),
        "can_release": bool(inspect_status.get("can_release")),
        "runtime_session": runtime_session,
        "safety_boundary": "analysis_and_artifact_generation_only",
        **SUMMARY_CONTRACT.summary_fields(blockers, next_stage, next_action_type, next_command, primary_action),
    }
    write_json(out / "auto_run_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="One-command safe workflow runner for Codex engineering skills")
    parser.add_argument("--input", required=True)
    parser.add_argument("--doc-id")
    parser.add_argument("--title")
    parser.add_argument("--repo")
    parser.add_argument("--project")
    parser.add_argument("--out")
    parser.add_argument("--profile")
    parser.add_argument("--docs-root")
    parser.add_argument("--doc-language", choices=["en", "zh", "auto"], default="auto")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = run(
        input_path=Path(args.input),
        doc_id=args.doc_id,
        title=args.title,
        repo=Path(args.repo) if args.repo else None,
        project=args.project,
        out=Path(args.out) if args.out else None,
        force=args.force,
        profile=args.profile,
        docs_root=Path(args.docs_root) if args.docs_root else None,
        doc_language=args.doc_language,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("decision") == "pass":
        return 0
    return 3 if result.get("decision") == "error" else 2


if __name__ == "__main__":
    raise SystemExit(main())
