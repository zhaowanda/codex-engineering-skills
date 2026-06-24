#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any


VALID_STATUSES = {"open", "fix_required", "accepted_risk", "waived", "resolved", "recheck_passed"}
ACTIVE_STATUSES = {"open", "fix_required"}
AREAS = [
    "cohesion_assessment",
    "coupling_assessment",
    "responsibility_boundary",
    "abstraction_assessment",
    "data_flow_assessment",
    "api_contract_assessment",
    "permission_boundary_assessment",
    "performance_assessment",
    "security_assessment",
    "configuration_assessment",
    "testability_assessment",
    "maintainability_risks",
]


def read_diff(path: str | None) -> str:
    if not path:
        import sys
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8", errors="ignore")


def changed_files(diff_text: str) -> list[str]:
    files: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                files.append(parts[3][2:] if parts[3].startswith("b/") else parts[3])
    return sorted(set(files))


def added_line_records(diff_text: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    current_file = ""
    new_line = 0
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            current_file = parts[3][2:] if len(parts) >= 4 and parts[3].startswith("b/") else (parts[3] if len(parts) >= 4 else "")
            continue
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            new_line = int(match.group(1)) if match else 0
            continue
        if line.startswith("+") and not line.startswith("+++"):
            records.append({"file": current_file, "line": new_line, "text": line[1:]})
            new_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            continue
        elif current_file:
            new_line += 1
    return records


def stable_finding_id(area: str, severity: str, message: str, file: str, line: int | str, evidence: str) -> str:
    raw = "|".join([area, severity, message, file, str(line), evidence[:120]])
    return "CDQR-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10].upper()


def best_location(records: list[dict[str, Any]], pattern: str) -> tuple[str, int | str]:
    if not pattern:
        return "", ""
    regex = re.compile(pattern, re.I)
    for record in records:
        if regex.search(str(record.get("text", ""))):
            return str(record.get("file", "")), record.get("line", "")
    return "", ""


def finding(
    area: str,
    severity: str,
    message: str,
    evidence: str,
    suggestion: str,
    *,
    records: list[dict[str, Any]],
    pattern: str = "",
    requirement_id: str = "",
    design_ref: str = "",
    test_ref: str = "",
    owner: str = "",
    reviewer: str = "code-design-quality-reviewer",
) -> dict[str, Any]:
    file, line = best_location(records, pattern)
    status = "fix_required" if severity in {"blocker", "high", "medium"} else "open"
    item: dict[str, Any] = {
        "area": area,
        "severity": severity,
        "file": file,
        "line": line,
        "message": message,
        "evidence": evidence[:240],
        "suggestion": suggestion,
        "requirement_id": requirement_id,
        "design_ref": design_ref,
        "test_ref": test_ref,
        "owner": owner,
        "status": status,
        "resolution": "",
        "reviewer": reviewer,
        "updated_at": date.today().isoformat(),
    }
    item["finding_id"] = stable_finding_id(area, severity, message, file, line, evidence)
    return item


def review(
    diff_text: str,
    requirement_id: str = "",
    design_ref: str = "",
    test_ref: str = "",
    owner: str = "",
    reviewer: str = "code-design-quality-reviewer",
) -> dict[str, Any]:
    files = changed_files(diff_text)
    records = added_line_records(diff_text)
    added = [str(record.get("text", "")) for record in records]
    text = "\n".join(added)
    lower_files = " ".join(files).lower()
    findings: list[dict[str, Any]] = []
    touched_layers = {
        "controller": any("controller" in f.lower() for f in files),
        "service": any("service" in f.lower() for f in files),
        "mapper": any("mapper" in f.lower() or "dao" in f.lower() or "repository" in f.lower() for f in files),
        "frontend": any(f.endswith((".vue", ".tsx", ".jsx")) or "/views/" in f.lower() or "/components/" in f.lower() for f in files),
        "permission": any("permission" in f.lower() or "auth" in f.lower() or "role" in f.lower() for f in files),
        "export": any("export" in f.lower() or "report" in f.lower() for f in files),
    }
    controller_added = "\n".join(record["text"] for record in records if "controller" in str(record.get("file", "")).lower())
    service_added = "\n".join(record["text"] for record in records if "service" in str(record.get("file", "")).lower())
    frontend_added = "\n".join(record["text"] for record in records if str(record.get("file", "")).endswith((".vue", ".tsx", ".jsx")) or "/views/" in str(record.get("file", "")).lower() or "/components/" in str(record.get("file", "")).lower())

    def add(area: str, severity: str, message: str, evidence: str, suggestion: str, pattern: str = "") -> None:
        findings.append(finding(area, severity, message, evidence, suggestion, records=records, pattern=pattern, requirement_id=requirement_id, design_ref=design_ref, test_ref=test_ref, owner=owner, reviewer=reviewer))

    if touched_layers["controller"] and re.search(r"select\s+|insert\s+|update\s+|delete\s+", text, re.I):
        add("responsibility_boundary", "blocker", "Controller appears to contain SQL/data access logic", "SQL marker in added controller diff", "Move data access to repository/DAO/service boundary.", r"select\s+|insert\s+|update\s+|delete\s+")
    if controller_added and re.search(r"\b(?:Mapper|Dao|Repository)\b|\.select(?:One|List|ById)?\(|\.insert\(|\.update\(|\.delete\(", controller_added):
        add("responsibility_boundary", "blocker", "Controller appears to call mapper/DAO/repository directly", "controller references persistence boundary", "Route controller through application/service layer.", r"\b(?:Mapper|Dao|Repository)\b|\.select(?:One|List|ById)?\(|\.insert\(|\.update\(|\.delete\(")
    if controller_added and re.search(r"RestTemplate|WebClient|OkHttpClient|HttpClient|Feign|axios|fetch\(", controller_added, re.I):
        add("responsibility_boundary", "high", "Controller appears to perform outbound integration directly", "controller references outbound client", "Move external calls into service/integration adapter with timeout, retry, fallback, and tests.", r"RestTemplate|WebClient|OkHttpClient|HttpClient|Feign|axios|fetch\(")
    if touched_layers["frontend"] and re.search(r"tenantId|dataScope|roleId|permission|auth", text, re.I):
        add("permission_boundary_assessment", "high", "Frontend appears to contain permission or tenant-scope logic", "permission/tenant marker in frontend diff", "Keep authorization/data scope backend-authoritative; frontend can only hide UI affordances.", r"tenantId|dataScope|roleId|permission|auth")
    if frontend_added and re.search(r"if\s*\([^)]*(role|permission|tenant|dataScope|admin|auth)", frontend_added, re.I):
        add("permission_boundary_assessment", "high", "Frontend conditional appears to enforce role/tenant/data-scope behavior", "frontend conditional with permission marker", "Require backend permission/data-scope enforcement evidence.", r"if\s*\([^)]*(role|permission|tenant|dataScope|admin|auth)")
    if re.search(r"@(?:Get|Post|Put|Delete|Patch|Request)Mapping|axios|\$axios|instance\.(?:get|post|put|delete)|fetch\(", text, re.I):
        if not re.search(r"compatib|old consumer|null|default|field|response", text, re.I):
            add("api_contract_assessment", "high", "API-related change lacks explicit compatibility/null/response semantics in diff", "API marker without compatibility marker", "Tie change to technical_design.api_contracts and confirm old consumer impact.", r"@(?:Get|Post|Put|Delete|Patch|Request)Mapping|axios|\$axios|instance\.(?:get|post|put|delete)|fetch\(")
    endpoint_count = len(re.findall(r"@(?:Get|Post|Put|Delete|Patch|Request)Mapping", text, re.I))
    if endpoint_count and not re.search(r"PreAuthorize|RequiresPermissions|Permission|Auth|LoginUser|Security|Tenant|DataScope", text):
        add("permission_boundary_assessment", "high", "New or changed backend endpoint lacks visible auth/data-scope marker", f"mapping count={endpoint_count}", "Bind endpoint to permission model and add/cite backend auth and data-scope evidence.", r"@(?:Get|Post|Put|Delete|Patch|Request)Mapping")
    if re.search(r"tenantId|dataScope|roleId|permission|auth", text, re.I) and not re.search(r"deny|forbid|unauthor|negative|reject", text, re.I):
        add("permission_boundary_assessment", "medium", "Permission/data-scope change lacks negative-case evidence in diff", "permission marker without negative-case marker", "Add or cite negative permission/tenant tests.", r"tenantId|dataScope|roleId|permission|auth")
    if len([v for v in touched_layers.values() if v]) >= 5:
        add("coupling_assessment", "high", "Single change touches too many architectural layers", ", ".join(k for k, v in touched_layers.items() if v), "Split work or confirm cross-layer design in architecture_design.")
    if re.search(r"TODO|FIXME|temporary|hack|quick fix", text, re.I):
        add("maintainability_risks", "medium", "Temporary or unfinished marker added", "TODO/FIXME/hack marker", "Resolve before release or document accepted risk with owner.", r"TODO|FIXME|temporary|hack|quick fix")
    if re.search(r"select\s+\*|group\s+by|order\s+by|distinct|join\s+|limit\s+|page|export|report|batch", text, re.I):
        add("performance_assessment", "medium", "Data/query/export path changed and needs performance evidence", "query/export/report marker in diff", "Bind SQL/index/pagination/sample-size/runtime evidence.", r"select\s+\*|group\s+by|order\s+by|distinct|join\s+|limit\s+|page|export|report|batch")
    if touched_layers["frontend"] and re.search(r"v-for|watch\s*:|computed\s*:|setInterval|setTimeout|axios|fetch|request", text, re.I):
        add("performance_assessment", "medium", "Frontend render/network path changed and needs performance evidence", "frontend performance marker in diff", "Bind browser network/render evidence.", r"v-for|watch\s*:|computed\s*:|setInterval|setTimeout|axios|fetch|request")
    if re.search(r"for\s*\([^)]*\)\s*\{[^}]{0,500}(select|axios|fetch|http|request)|while\s*\(", text, re.I | re.S):
        add("performance_assessment", "high", "Loop may contain DB/API/network work or unbounded processing", "loop with IO marker", "Refactor to bounded/batched access or provide benchmark and safeguards.", r"for\s*\(|while\s*\(")
    if re.search(r"(forEach|map)\s*\([^)]*(select|axios|fetch|http|request)|stream\(\)\.[^;\n]*(map|forEach)[^;\n]*(select|http|request)", text, re.I | re.S):
        add("performance_assessment", "high", "Collection iteration may contain DB/API/network work", "collection iteration with IO marker", "Replace N+1 calls with batch query/API, cache, or bounded concurrency.", r"forEach|map|stream\(\)")
    write_ops = len(re.findall(r"\.(?:insert|update|delete|save|remove)\w*\(", service_added, re.I))
    if write_ops >= 2 and "@Transactional" not in service_added:
        add("data_flow_assessment", "high", "Service change performs multiple writes without visible transaction boundary", f"write operations={write_ops}", "Add/cite transaction boundary, idempotency, rollback, and partial-failure behavior.", r"\.(?:insert|update|delete|save|remove)\w*\(")
    if len(re.findall(r"if\s*\(", text)) + len(re.findall(r"else\s+if", text)) > 12:
        add("abstraction_assessment", "medium", "High branching added in one diff", "branch count > 12", "Extract cohesive policy/rule methods or table-driven mapping.", r"if\s*\(|else\s+if")
    duplicate_literals = [lit for lit in re.findall(r'"([^"]{8,})"', text) if text.count(lit) >= 3]
    if duplicate_literals:
        add("cohesion_assessment", "medium", "Repeated literals suggest scattered business rule or field meaning", duplicate_literals[0], "Centralize repeated field/rule constants in the owning module.", re.escape(duplicate_literals[0]))
    duplicate_business_values = [lit for lit in re.findall(r'["\']([A-Z][A-Z0-9_]{2,}|[a-z][a-z0-9_-]{4,})["\']', text) if text.count(lit) >= 3]
    if duplicate_business_values:
        add("cohesion_assessment", "medium", "Repeated business values suggest duplicated rules or enum drift", duplicate_business_values[0], "Move repeated values to enum/constants/config owned by the domain module.", re.escape(duplicate_business_values[0]))
    if re.search(r"log(?:ger)?\.(?:info|debug|warn|error)\([^;\n]*(password|passwd|pwd|token|secret|phone|mobile|card|pay|payment)", text, re.I):
        add("security_assessment", "blocker", "Sensitive data appears to be logged", "log statement contains sensitive marker", "Remove or mask sensitive fields and bind security evidence.", r"log(?:ger)?\.(?:info|debug|warn|error)")
    secret_key_pattern = "sk-" + r"[A-Za-z0-9_-]{20,}"
    hardcoded_secret_pattern = r"(AKIA[0-9A-Z]{16}|" + secret_key_pattern + r"|password\s*=\s*[\"'][^\"']{6,}|secret\s*=\s*[\"'][^\"']{6,}|token\s*=\s*[\"'][^\"']{10,})"
    if re.search(hardcoded_secret_pattern, text, re.I):
        add("security_assessment", "blocker", "Hardcoded secret or credential-like value added", "secret/credential marker in added diff", "Move secrets to managed configuration/secret store and rotate exposed values.", hardcoded_secret_pattern)
    jdbc_pattern = "j" + r"dbc:[^\"'\s]+"
    config_value_pattern = r"https?://[^\"'\s]+|" + jdbc_pattern + r"|amqp://[^\"'\s]+|redis://[^\"'\s]+|topic\s*=\s*[\"'][^\"']+|queue\s*=\s*[\"'][^\"']+"
    if re.search(config_value_pattern, text, re.I):
        if not re.search(r"config|properties|yaml|yml|env|secret|parameter", lower_files + "\n" + text, re.I):
            config_location_pattern = r"https?://|" + "j" + r"dbc:|amqp://|redis://|topic\s*=|queue\s*="
            add("configuration_assessment", "high", "Environment/provider configuration appears hardcoded in code", "URL/JDBC/MQ topic marker outside config context", "Move endpoint/topic/provider values to governed configuration with environment matrix.", config_location_pattern)
    if re.search(r"(BigDecimal|amount|price|fee|refund|pay|payment|settlement)", text, re.I):
        if not re.search(r"round|scale|RoundingMode|idempot|transaction|reconcile|precision", text, re.I):
            add("data_flow_assessment", "medium", "Money/payment/settlement path changed without visible precision/idempotency/reconciliation evidence", "money/payment marker without finance safety marker", "Confirm precision, idempotency key, reconciliation, and rollback semantics.", r"BigDecimal|amount|price|fee|refund|pay|payment|settlement")
    if re.search(r"public\s+class|interface\s+|abstract\s+class", text) and len(files) <= 2 and "factory" in text.lower():
        add("abstraction_assessment", "medium", "New abstraction/factory introduced in a small change", "factory/abstract marker", "Verify this is required by current requirements, not speculative generalization.", r"public\s+class|interface\s+|abstract\s+class|factory")
    test_files_touched = any(re.search(r"(^|/)(test|tests)/|Test\.|\.spec\.|\.test\.", f, re.I) for f in files)
    risky_change = any(touched_layers.values()) or bool(re.search(r"@(?:Get|Post|Put|Delete|Patch|Request)Mapping|axios|tenantId|dataScope|export|report", text, re.I))
    if risky_change and not test_files_touched:
        add("testability_assessment", "medium", "Risky behavior change has no test file touched in diff", ", ".join(files), "Add tests or bind manual/API/browser/permission evidence before release.")

    active_blockers = [item for item in findings if item["severity"] == "blocker" and item["status"] in ACTIVE_STATUSES]
    active_highs = [item for item in findings if item["severity"] == "high" and item["status"] in ACTIVE_STATUSES]
    active_mediums = [item for item in findings if item["severity"] == "medium" and item["status"] in ACTIVE_STATUSES]
    if active_blockers:
        decision = "block"
    elif active_highs or active_mediums:
        decision = "needs_refactor"
    else:
        decision = "pass"

    def by_area(area: str) -> list[dict[str, Any]]:
        return [item for item in findings if item["area"] == area]

    return {
        "schema": "codex-code-design-quality-review-v1",
        "changed_files": files,
        "findings": findings,
        **{area: by_area(area) for area in AREAS},
        "refactor_suggestions": [item["suggestion"] for item in findings if item["severity"] in {"medium", "high", "blocker"} and item["status"] in ACTIVE_STATUSES],
        "blockers": active_blockers,
        "decision": decision,
        "finding_lifecycle": {
            "active_statuses": sorted(ACTIVE_STATUSES),
            "closed_statuses": ["accepted_risk", "waived", "resolved", "recheck_passed"],
            "rule": "blocker/high cannot pass release while status is open or fix_required",
        },
    }


def validate(data: dict[str, Any]) -> tuple[bool, list[str]]:
    issues: list[str] = []
    required = ["schema", "changed_files", "findings", "refactor_suggestions", "blockers", "decision", *AREAS]
    for key in required:
        if key not in data:
            issues.append(f"missing {key}")
    if data.get("schema") != "codex-code-design-quality-review-v1":
        issues.append("schema must be codex-code-design-quality-review-v1")
    if data.get("decision") not in {"pass", "needs_refactor", "block"}:
        issues.append("decision must be pass/needs_refactor/block")
    if data.get("decision") == "pass" and data.get("blockers"):
        issues.append("pass is not allowed with blockers")
    findings = data.get("findings", [])
    if findings and not isinstance(findings, list):
        issues.append("findings must be a list")
        findings = []
    for idx, item in enumerate(findings):
        if not isinstance(item, dict):
            issues.append(f"findings[{idx}] must be object")
            continue
        for key in ["finding_id", "severity", "area", "message", "status", "updated_at"]:
            if not item.get(key):
                issues.append(f"findings[{idx}] missing {key}")
        if item.get("status") not in VALID_STATUSES:
            issues.append(f"findings[{idx}].status invalid")
        if item.get("status") not in ACTIVE_STATUSES and not item.get("resolution"):
            issues.append(f"findings[{idx}] closed/non-blocking status requires resolution")
        if item.get("severity") in {"blocker", "high"} and item.get("status") in ACTIVE_STATUSES and data.get("decision") == "pass":
            issues.append(f"active blocker/high finding cannot pass: {item.get('finding_id')}")
    return not issues, issues


def resolve_findings(data: dict[str, Any], finding_id: str, status: str, resolution: str, owner: str = "", reviewer: str = "") -> dict[str, Any]:
    if status not in VALID_STATUSES:
        raise SystemExit(f"invalid status: {status}")
    if status not in ACTIVE_STATUSES and not resolution:
        raise SystemExit("resolution is required for accepted_risk/waived/resolved/recheck_passed")
    changed = False
    for item in data.get("findings", []):
        if isinstance(item, dict) and item.get("finding_id") == finding_id:
            item["status"] = status
            item["resolution"] = resolution
            if owner:
                item["owner"] = owner
            if reviewer:
                item["reviewer"] = reviewer
            item["updated_at"] = date.today().isoformat()
            changed = True
    if not changed:
        raise SystemExit(f"finding not found: {finding_id}")
    active_blockers = [item for item in data.get("findings", []) if isinstance(item, dict) and item.get("severity") == "blocker" and item.get("status") in ACTIVE_STATUSES]
    active_highs = [item for item in data.get("findings", []) if isinstance(item, dict) and item.get("severity") == "high" and item.get("status") in ACTIVE_STATUSES]
    active_mediums = [item for item in data.get("findings", []) if isinstance(item, dict) and item.get("severity") == "medium" and item.get("status") in ACTIVE_STATUSES]
    data["blockers"] = active_blockers
    if active_blockers:
        data["decision"] = "block"
    elif active_highs or active_mediums:
        data["decision"] = "needs_refactor"
    else:
        data["decision"] = "pass"
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Code design quality reviewer")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_review = sub.add_parser("review")
    p_review.add_argument("--diff-file")
    p_review.add_argument("--out")
    p_review.add_argument("--requirement-id", default="")
    p_review.add_argument("--design-ref", default="")
    p_review.add_argument("--test-ref", default="")
    p_review.add_argument("--owner", default="")
    p_review.add_argument("--reviewer", default="code-design-quality-reviewer")
    p_validate = sub.add_parser("validate")
    p_validate.add_argument("--file", required=True)
    p_resolve = sub.add_parser("resolve")
    p_resolve.add_argument("--file", required=True)
    p_resolve.add_argument("--finding-id", required=True)
    p_resolve.add_argument("--status", required=True, choices=sorted(VALID_STATUSES))
    p_resolve.add_argument("--resolution", default="")
    p_resolve.add_argument("--owner", default="")
    p_resolve.add_argument("--reviewer", default="")
    p_resolve.add_argument("--out")
    args = parser.parse_args()

    if args.cmd == "review":
        result = review(read_diff(args.diff_file), args.requirement_id, args.design_ref, args.test_ref, args.owner, args.reviewer)
        if args.out:
            Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["decision"] != "block" else 1
    if args.cmd == "validate":
        data = json.loads(Path(args.file).read_text(encoding="utf-8"))
        valid, issues = validate(data)
        print(json.dumps({"schema": "codex-code-design-quality-review-validation-v1", "valid": valid, "issues": issues}, ensure_ascii=False, indent=2))
        return 0 if valid else 1
    data_path = Path(args.file)
    data = json.loads(data_path.read_text(encoding="utf-8"))
    result = resolve_findings(data, args.finding_id, args.status, args.resolution, args.owner, args.reviewer)
    out = Path(args.out) if args.out else data_path
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
