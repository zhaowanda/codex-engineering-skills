#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "codex-spec-v1"


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def split_lines(text: str) -> list[str]:
    return [line.strip(" \t-*#") for line in text.splitlines() if line.strip(" \t-*#")]


def classify_lane(text: str) -> str:
    lower = text.lower()
    if any(term in lower for term in ["hotfix", "production down", "p0", "urgent"]):
        return "hotfix"
    if any(term in lower for term in ["bug", "fix", "defect", "报错", "修复"]):
        return "bugfix"
    if len(text) > 3000 or len(split_lines(text)) > 30:
        return "large_prd"
    if len(text) < 300:
        return "small_change"
    return "standard_requirement"


def extract_acceptance(lines: list[str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    ac_pattern = re.compile(r"^(ac|acceptance|验收|验收标准|标准)[:：\s-]*(.+)$", re.I)
    for line in lines:
        match = ac_pattern.match(line)
        if match:
            result.append({"id": f"AC-{len(result) + 1}", "criteria": match.group(2).strip(), "evidence_required": []})
    if not result and lines:
        result.append({"id": "AC-1", "criteria": f"User-visible behavior matches: {lines[0]}", "evidence_required": ["test evidence"]})
    return result


def extract_requirements(lines: list[str]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    req_pattern = re.compile(r"^(req|requirement|需求|功能)[:：\s-]*(.+)$", re.I)
    skip_pattern = re.compile(r"^(ac|acceptance|验收|验收标准|标准|rule|规则|out of scope|非目标|assumption|假设|risk|风险)[:：\s-]*", re.I)
    for idx, line in enumerate(lines, start=1):
        match = req_pattern.match(line)
        if match:
            result.append({"id": f"REQ-{len(result) + 1}", "summary": match.group(2).strip(), "source_evidence": f"input line {idx}"})
    if not result:
        for idx, line in enumerate(lines, start=1):
            if skip_pattern.match(line) or "?" in line or "？" in line:
                continue
            result.append({"id": f"REQ-{len(result) + 1}", "summary": line, "source_evidence": f"input line {idx}"})
            if len(result) >= 3:
                break
    return result


def extract_rules(lines: list[str]) -> list[dict[str, str]]:
    rules: list[dict[str, str]] = []
    for line in lines:
        lower = line.lower()
        if any(term in lower for term in ["must", "should", "rule", "when", "if ", "only", "不能", "必须", "规则", "如果", "当"]):
            rules.append({"id": f"BR-{len(rules) + 1}", "rule": line, "source_evidence": "input"})
    return rules


def extract_open_questions(lines: list[str]) -> list[dict[str, str]]:
    questions: list[dict[str, str]] = []
    for line in lines:
        if "?" in line or "？" in line or any(term in line.lower() for term in ["tbd", "todo", "待确认", "不确定"]):
            questions.append({"id": f"Q-{len(questions) + 1}", "question": line, "owner": "product/engineering", "status": "open"})
    return questions


def extract_prefixed(lines: list[str], prefixes: tuple[str, ...]) -> list[str]:
    pattern = re.compile(rf"^({'|'.join(re.escape(item) for item in prefixes)})[:：\s-]*(.+)$", re.I)
    result: list[str] = []
    for line in lines:
        match = pattern.match(line)
        if match:
            result.append(match.group(2).strip())
    return result


def normalize(doc_id: str, title: str, text: str) -> dict[str, Any]:
    lines = split_lines(text)
    summary = lines[0] if lines else title
    lane = classify_lane(text)
    acceptance = extract_acceptance(lines)
    rules = extract_rules(lines)
    questions = extract_open_questions(lines)
    requirements = extract_requirements(lines)
    out_of_scope = extract_prefixed(lines, ("out of scope", "非目标", "不包含"))
    assumptions = extract_prefixed(lines, ("assumption", "假设"))
    risks = [{"id": f"RISK-{idx + 1}", "risk": item, "source_evidence": "input"} for idx, item in enumerate(extract_prefixed(lines, ("risk", "风险")))]
    non_goals = extract_prefixed(lines, ("non-goal", "non goal", "非目标"))
    actors = []
    lower = text.lower()
    for candidate in ["admin", "operator", "customer", "user", "buyer", "管理员", "用户", "客户", "运营"]:
        if candidate in lower or candidate in text:
            actors.append(candidate)
    if not actors:
        actors = ["user"]
    return {
        "schema": SCHEMA,
        "doc_id": doc_id,
        "title": title,
        "lane": lane,
        "requirement_summary": summary,
        "source": {"type": "text", "line_count": len(lines)},
        "actors": sorted(set(actors)),
        "scope": {
            "in_scope": [summary] if summary else [],
            "out_of_scope": out_of_scope,
            "assumptions": assumptions,
            "non_goals": non_goals,
        },
        "requirements": requirements,
        "business_rules": rules,
        "acceptance_criteria": acceptance,
        "risks": risks,
        "open_questions": questions,
        "decision": "blocked" if questions else "ready_for_design",
        "next_action": "Close open questions before design." if questions else "Proceed to technical and architecture design.",
    }


def validate_spec(spec: dict[str, Any]) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if spec.get("schema") != SCHEMA:
        blockers.append({"source": "schema", "message": f"schema must be {SCHEMA}"})
    for key in ["doc_id", "title", "requirement_summary", "lane"]:
        if not spec.get(key):
            blockers.append({"source": key, "message": f"{key} is required"})
    if not as_list(spec.get("actors")):
        blockers.append({"source": "actors", "message": "actors are required"})
    if not as_list(spec.get("requirements")):
        blockers.append({"source": "requirements", "message": "at least one requirement is required"})
    if not as_list(spec.get("acceptance_criteria")):
        blockers.append({"source": "acceptance_criteria", "message": "acceptance criteria are required"})
    scope = spec.get("scope") if isinstance(spec.get("scope"), dict) else {}
    if not as_list(scope.get("in_scope")):
        blockers.append({"source": "scope.in_scope", "message": "in_scope is required"})
    open_questions = [q for q in as_list(spec.get("open_questions")) if isinstance(q, dict) and q.get("status", "open") != "closed"]
    if open_questions:
        blockers.append({"source": "open_questions", "message": "open questions must be closed before implementation", "count": len(open_questions)})
    if not as_list(spec.get("business_rules")):
        warnings.append({"source": "business_rules", "message": "no explicit business rules were extracted"})
    decision = "block" if blockers else "pass"
    return {
        "schema": "codex-spec-validation-v1",
        "decision": decision,
        "blockers": blockers,
        "warnings": warnings,
        "next_action": "Fix spec blockers before design/implementation." if blockers else "Spec is ready for design.",
    }


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize and validate requirement specs")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_norm = sub.add_parser("normalize")
    p_norm.add_argument("--doc-id", required=True)
    p_norm.add_argument("--title", required=True)
    p_norm.add_argument("--input", required=True)
    p_norm.add_argument("--out", required=True)
    p_val = sub.add_parser("validate")
    p_val.add_argument("--file", required=True)
    p_val.add_argument("--out")
    args = parser.parse_args()

    if args.cmd == "normalize":
        result = normalize(args.doc_id, args.title, read_text(Path(args.input)))
        write_json(Path(args.out), result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["decision"] != "blocked" else 1
    result = validate_spec(load_json(Path(args.file)))
    if args.out:
        write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
