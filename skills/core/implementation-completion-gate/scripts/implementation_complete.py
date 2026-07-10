#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def changed_files(diff: str) -> list[str]:
    files = []
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            if path != "/dev/null":
                files.append(path)
    return sorted(set(files))


def allowed_files(plan: dict[str, Any]) -> list[str]:
    allowed = []
    for task in plan.get("repo_tasks", []):
        if isinstance(task, dict):
            allowed.extend(str(item) for item in task.get("allowed_files", []) if item)
    return allowed


def added_text(diff: str) -> str:
    return "\n".join(
        line[1:]
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )


def has(pattern: str, value: str) -> bool:
    return bool(re.search(pattern, value, re.I | re.S))


def evidence_followups(diff: str, files: list[str]) -> list[dict[str, Any]]:
    text = added_text(diff)
    haystack = "\n".join(files) + "\n" + text
    lower_files = " ".join(files).lower()
    followups: list[dict[str, Any]] = []

    def add(surface: str, evidence: list[str], rationale: str, gate: str) -> None:
        followups.append(
            {
                "surface": surface,
                "required_by": gate,
                "evidence": evidence,
                "rationale": rationale,
            }
        )

    api = has(r"@(?:Get|Post|Put|Delete|Patch|Request)Mapping|/api/|controller|router|axios|fetch\(|\brequest\.", haystack)
    database = has(r"\b(select|insert|update|delete|merge)\b|mapper|repository|dao|migration|schema|create\s+table|alter\s+table", haystack)
    mq = has(r"kafka|rabbit|rocketmq|messagequeue|producer|consumer|listener|topic|queue|dead.?letter|dlq", haystack)
    cache = has(r"redis|cacheable|cacheput|cacheevict|cachemanager|localcache|caffeine|ttl|expire", haystack)
    write_ops = len(re.findall(r"\.(?:insert|update|delete|save|remove)\w*\(", text, re.I))
    transaction = write_ops >= 2 or has(r"@Transactional|transaction|rollback|idempot", haystack)
    permission = has(r"permission|auth|role|tenant|datascope|preauthorize|requirespermissions|loginuser", haystack)
    frontend = any(file.endswith((".vue", ".tsx", ".jsx", ".ts", ".js")) or "/views/" in file.lower() or "/components/" in file.lower() for file in files)
    config = has(r"\.(yml|yaml|properties|conf|ini)$|application-|bootstrap-|env|config|feature.?flag", lower_files)
    scheduled_or_task = has(r"@Scheduled|cron|xxljob|jobhandler|task|timer|scheduler|quartz", haystack)

    if api:
        add(
            "api_contract",
            ["api naming/path evidence", "request/response schema evidence", "backward compatibility or consumer impact evidence", "API test evidence"],
            "API or route surface changed; consumers need precise contract proof.",
            "code-review-gate/test-evidence-gate",
        )
    if database:
        add(
            "data_model",
            ["table/model field mapping evidence", "migration/rollback evidence", "index/query plan evidence when query shape changes", "data compatibility evidence"],
            "Data model or query surface changed; release needs schema and data safety proof.",
            "design-architecture-reviewer/release-evidence-binder",
        )
    if mq:
        add(
            "mq_interaction",
            ["producer/consumer ownership evidence", "topic/queue contract evidence", "trigger condition evidence", "retry/idempotency/DLQ evidence", "upstream/downstream sequence evidence"],
            "MQ flow changed or is reused; async integration must be explicit and testable.",
            "design-architecture-reviewer/test-evidence-gate",
        )
    if cache:
        add(
            "cache_consistency",
            ["cache key and TTL evidence", "invalidation/refresh evidence", "stale-read tolerance evidence", "fallback evidence"],
            "Cache behavior can change correctness and freshness guarantees.",
            "code-review-gate/test-evidence-gate",
        )
    if transaction:
        add(
            "transaction_idempotency",
            ["transaction boundary evidence", "rollback/partial failure evidence", "idempotency evidence", "concurrency evidence when writes can repeat"],
            "Multi-write or transaction-sensitive change needs failure semantics beyond happy path.",
            "code-design-quality-reviewer/test-evidence-gate",
        )
    if permission:
        add(
            "permission_data_scope",
            ["backend authorization evidence", "tenant/data-scope evidence", "negative permission test evidence", "frontend-only hiding is not accepted as enforcement"],
            "Permission-sensitive behavior must be enforced server-side and tested negatively.",
            "code-review-gate/test-evidence-gate",
        )
    if frontend:
        add(
            "frontend_acceptance",
            ["browser acceptance evidence", "network/API binding evidence", "empty/loading/error state evidence", "permission-visible UI evidence when applicable"],
            "Frontend files changed; user-visible behavior needs browser-level proof.",
            "frontend-acceptance-runner/test-evidence-gate",
        )
    if config:
        add(
            "configuration",
            ["environment matrix evidence", "default/override evidence", "secret-free config evidence", "rollback evidence for config change"],
            "Configuration changes require environment and rollback clarity.",
            "configuration-governor/release-evidence-binder",
        )
    if api or mq or scheduled_or_task:
        add(
            "observability",
            ["log marker evidence", "metric/alert evidence for critical path", "trace/correlation evidence when crossing services", "post-release observation evidence"],
            "Runtime entrypoints need observable success, failure, and latency signals.",
            "post-release-observer/release-evidence-binder",
        )
    return followups


def evaluate(diff: str, plan: dict[str, Any], summary: str) -> dict[str, Any]:
    files = changed_files(diff)
    blockers: list[dict[str, Any]] = []
    allowed = allowed_files(plan)
    if plan:
        if plan.get("decision") in {"block", "blocked", "needs_completion"}:
            blockers.append({"source": "delivery_plan", "message": "delivery plan is not ready for implementation", "decision": plan.get("decision")})
        if plan.get("open_gates"):
            blockers.append({"source": "delivery_plan", "message": "delivery plan has unresolved open_gates", "open_gates": plan.get("open_gates")})
        gate = plan.get("source_design_gate") if isinstance(plan.get("source_design_gate"), dict) else {}
        if gate.get("design_allowed") is False or gate.get("implementation_allowed") is False:
            blockers.append({"source": "requirements_understanding_gate", "message": "requirement understanding blocks implementation completion", "gate": gate})
    if not files:
        blockers.append({"source": "diff", "message": "no changed files detected"})
    if not summary.strip():
        blockers.append({"source": "summary", "message": "implementation summary is required"})
    if allowed:
        out_of_scope = [file for file in files if not any(file.startswith(prefix.strip("/")) or prefix.strip("/") in file for prefix in allowed)]
        if out_of_scope:
            blockers.append({"source": "scope", "message": "changed files outside delivery plan allowed_files", "files": out_of_scope})
    elif plan:
        blockers.append({"source": "delivery_plan", "message": "delivery plan has no allowed_files for scope check"})
    followups = evidence_followups(diff, files)
    warnings = [] if allowed else [{"source": "scope", "message": "scope check is weak without allowed_files"}]
    warnings.extend(
        {"source": "evidence_followup", "message": f"{item['surface']} evidence must be closed by {item['required_by']}"}
        for item in followups
    )
    return {
        "schema": "codex-implementation-completion-v1",
        "decision": "block" if blockers else "pass",
        "changed_files": files,
        "implementation_summary": summary,
        "blockers": blockers,
        "warnings": warnings,
        "evidence_followups": followups,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate implementation completion")
    parser.add_argument("--diff-file", required=True)
    parser.add_argument("--delivery-plan", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--out")
    args = parser.parse_args()
    result = evaluate(Path(args.diff_file).read_text(encoding="utf-8", errors="ignore"), load_json(Path(args.delivery_plan)), args.summary)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
