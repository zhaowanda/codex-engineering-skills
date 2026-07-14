#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REQUIRED_TERMS = {
    "scope": ["scope", "范围"],
    "decision": ["decision", "决策", "方案"],
    "options": ["option", "alternative", "对比", "方案"],
    "risk": ["risk", "风险"],
    "evidence": ["evidence", "证据", "验证"],
    "rollback": ["rollback", "回滚"],
}
DOC_TYPE_REQUIREMENTS = {
    "spec": {
        "scope",
        "evidence",
        "background",
        "goal",
        "clarification",
        "acceptance",
        "traceability",
        "review_focus",
    },
    "design": {
        "decision",
        "options",
        "risk",
        "evidence",
        "rollback",
        "test",
        "diagram",
        "traceability",
        "implementation_boundary",
    },
    "test": {
        "scope",
        "evidence",
        "acceptance",
        "test",
        "traceability",
    },
    "release": {
        "risk",
        "evidence",
        "rollback",
        "test",
        "diagram",
        "traceability",
        "readiness",
        "post_release",
    },
    "general": {
        "scope",
        "decision",
        "options",
        "risk",
        "evidence",
        "rollback",
        "background",
        "goal",
        "clarification",
        "acceptance",
        "test",
        "diagram",
        "traceability",
        "implementation_boundary",
        "review_focus",
    },
}
RELEASE_TERMS = {
    "readiness": ["readiness", "missing readiness", "发布前检查", "放行原则", "就绪"],
    "post_release": ["post-release", "post release", "observation", "发布后", "观察"],
}
FORMAL_TERMS = {
    "background": ["background", "背景"],
    "goal": ["goal", "objective", "目标"],
    "clarification": ["clarification", "澄清"],
    "acceptance": ["acceptance", "验收"],
    "test": ["test", "测试"],
}
GENERIC_PHRASES = [
    "pending delivery artifact sync",
    "tbd",
    "confirm later",
    "target module to be confirmed",
    "existing producer",
    "待确认",
]
UNRESOLVED_TERMS = [
    "需结合代码核对",
    "需结合代码和数据库核对",
    "需结合代码和数据库确认",
    "需确认",
    "requires code confirmation",
    "requires code and database confirmation",
    "needs confirmation",
    "needs_confirmation",
]
UNRESOLVED_CONTEXT_TERMS = [
    "原因",
    "动作",
    "证据",
    "责任",
    "迁移",
    "回滚",
    "实施前",
    "超时",
    "重试",
    "补偿",
    "幂等",
    "一致性",
    "reason",
    "action",
    "evidence",
    "inspect",
    "migration",
    "rollback",
]
ENGLISH_TEMPLATE_TERMS = [
    "executive summary",
    "current decision",
    "missing readiness",
    "before implementation",
    "evidence references",
    "requirement clarification",
    "owner-module implementation",
    "contract-aware service/api adjustment",
    "data-model explicit handling",
    "single-owner architecture",
    "provider-consumer contract architecture",
    "data-first release architecture",
    "weighted comparison selects",
    "weighted architecture comparison selects",
    "rejected for this pass",
    "user-visible behavior matches",
    "regression coverage for",
    "cross-component integration remains compatible",
    "browser acceptance for changed ui",
    "expected behavior for this sub-requirement",
    "rollback consumers before provider",
    "contract compatibility matrix",
    "owner repo tests plus mapped acceptance evidence",
    "frontend app running",
    "all changed components deployed",
]
WEAK_ACCEPTANCE_PATTERNS = [
    r"`AC-1`\s*标准",
    r"预期结果：标准",
    r"页面展示、接口参数、返回字段和数据落库均满足该验收",
    r"UI, API params, response fields, and persistence satisfy the AC",
]
DESIGN_TEMPLATE_RESIDUE_PATTERNS = [
    r"至少包括[:：]\s*[。.;；]",
    r"\bNone\.\s*$",
    r"Validate acceptance criteria for",
    r"校准展示、筛选、状态、原因或刷新结果",
    r"calibrate display, filter, status, reason, or refresh behavior",
    r"当前链路需要验证[^。\n]+是否能稳定产生",
    r"现有链路必须证明请求口径",
]
NON_BUSINESS_CONTRACT_PATTERNS = [
    r"生产方[:：]?.*vue\.config\.js",
    r"契约[^。\n]*vue\.config\.js",
    r"接口/服务[^。\n]*vue\.config\.js",
    r"将 `/ \(vue\.config\.js\)` 作为显式架构边界",
]
PREMATURE_DECISION_HEADINGS = [
    "决策记录",
    "方案决策",
    "技术决策结论",
    "架构决策结论",
    "decision record",
    "technical decision",
    "architecture decision",
]
OPTION_EXPLANATION_HEADINGS = [
    "候选方案",
    "方案详述",
    "candidate options",
    "options",
]
OPTION_COUNT_FIXED_PATTERNS = [
    r"二选一",
    r"三选一",
    r"固定二",
    r"固定三",
    r"two-option template",
    r"three-option template",
]
DEPTH_TERMS = {
    "review_focus": ["review focus", "评审重点", "阅读与评审重点"],
    "traceability": ["traceability", "追踪", "追溯"],
    "implementation_boundary": ["implementation boundary", "edit constraint", "实施边界", "实现约束", "允许修改文件"],
}


def heading_positions(text: str, terms: list[str]) -> list[int]:
    positions: list[int] = []
    for match in re.finditer(r"(?m)^#{1,5}\s+(.+)$", text):
        heading = match.group(1).strip().lower()
        if any(term.lower() in heading for term in terms):
            positions.append(match.start())
    return positions


def extract_section_text(text: str, heading_term: str) -> str:
    pattern = re.compile(rf"(?m)^#{1,5}\s+.*{re.escape(heading_term)}.*$")
    match = pattern.search(text)
    if not match:
        return ""
    next_match = re.search(r"(?m)^#{1,5}\s+", text[match.end():])
    end = match.end() + next_match.start() if next_match else len(text)
    return text[match.end():end].strip()


def normalized_words(value: str) -> set[str]:
    words = re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z][a-zA-Z0-9_/-]+", value.lower())
    stop = {"当前", "本需求", "需要", "进行", "实现", "优化", "支持", "设计", "目标", "问题", "业务", "the", "and", "for", "with", "this"}
    return {word for word in words if word not in stop}


def similarity_ratio(left: str, right: str) -> float:
    left_words = normalized_words(left)
    right_words = normalized_words(right)
    if not left_words or not right_words:
        return 0.0
    return len(left_words & right_words) / max(len(left_words | right_words), 1)


def infer_doc_type(path: Path, text: str) -> str:
    normalized = path.as_posix().lower()
    heading_lines = "\n".join(line for line in text.splitlines()[:12] if line.lstrip().startswith("#")).lower()
    if "/human/designs/" in normalized or re.search(r"(^|/)(designs?|architectures?)(/|$)", normalized):
        return "design"
    if "/human/tests/" in normalized or re.search(r"(^|/)(tests?|test-designs?)(/|$)", normalized):
        return "test"
    if "/human/releases/" in normalized or re.search(r"(^|/)(releases?)(/|$)", normalized):
        return "release"
    if "/human/specs/" in normalized or re.search(r"(^|/)(specs?|requirements?)(/|$)", normalized):
        return "spec"
    if "技术设计" in heading_lines or re.search(r"\b(design|architecture)\b", heading_lines):
        return "design"
    if "测试设计" in heading_lines or re.search(r"\b(test design|test)\b", heading_lines):
        return "test"
    if "发布准备" in heading_lines or re.search(r"\b(release)\b", heading_lines):
        return "release"
    if "需求说明" in heading_lines or re.search(r"\b(spec|requirement)\b", heading_lines):
        return "spec"
    return "general"


def has_any(text: str, lower: str, terms: list[str]) -> bool:
    return any(term in lower or term in text for term in terms)


def unresolved_review(text: str, lower: str) -> dict:
    raw_lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    lines = [line.strip() for line in raw_lines]

    def has_unresolved_term(line: str) -> bool:
        lower_line = line.lower()
        return any(term in line or term.lower() in lower_line for term in UNRESOLVED_TERMS)

    def has_context_term(value: str) -> bool:
        lower_value = value.lower()
        return any(term in value or term.lower() in lower_value for term in UNRESOLVED_CONTEXT_TERMS)

    def markdown_list_block(index: int) -> str:
        start = index
        while start > 0:
            previous = raw_lines[start - 1]
            if previous.lstrip().startswith("#"):
                break
            if previous.startswith("- "):
                start -= 1
                break
            start -= 1
        end = index + 1
        while end < len(raw_lines):
            candidate = raw_lines[end]
            if candidate.lstrip().startswith("#") or candidate.startswith("- "):
                break
            end += 1
        return "\n".join(line.strip() for line in raw_lines[start:end])

    unresolved_indexed_lines = [
        (index, line)
        for index, line in enumerate(lines)
        if not line.startswith("#")
        if not any(skip in line.lower() for skip in ["未记录", "无确认项", "no low-confidence", "no unresolved", "not recorded"])
        if has_unresolved_term(line)
    ]
    if not unresolved_indexed_lines:
        return {"count": 0, "ratio": 0.0, "missing_context": []}
    missing_context = [
        line[:160]
        for index, line in unresolved_indexed_lines
        if not has_context_term(markdown_list_block(index))
    ]
    ratio = len(unresolved_indexed_lines) / max(len(lines), 1)
    return {"count": len(unresolved_indexed_lines), "ratio": ratio, "missing_context": missing_context[:5]}


def review(path: Path, strict: bool = False) -> dict:
    text = path.read_text(encoding="utf-8", errors="ignore")
    lower = text.lower()
    doc_type = infer_doc_type(path, text)
    required_sources = DOC_TYPE_REQUIREMENTS[doc_type]
    blockers = []
    warnings = []
    if len(text.strip()) < 500:
        warnings.append({"source": "length", "message": "document is short; may lack substance"})
    for area, terms in REQUIRED_TERMS.items():
        if area in required_sources and not has_any(text, lower, terms):
            warnings.append({"source": area, "message": f"{area} section or terms not found"})
    for area, terms in FORMAL_TERMS.items():
        if area in required_sources and not has_any(text, lower, terms):
            warnings.append({"source": area, "message": f"{area} formal-document content not found"})
    for area, terms in RELEASE_TERMS.items():
        if area in required_sources and not has_any(text, lower, terms):
            warnings.append({"source": area, "message": f"{area} release-readiness content not found"})
    if "diagram" in required_sources and "```mermaid" not in lower and not any(phrase in text for phrase in ["无法生成", "cannot be generated"]):
        warnings.append({"source": "diagram", "message": "diagram or explicit no-diagram explanation not found"})
    if doc_type == "design":
        if not re.search(r"```mermaid\s+flowchart\b", text, flags=re.I):
            warnings.append({"source": "business_process_diagram", "message": "design document must include a Mermaid business process flowchart"})
        if not re.search(r"```mermaid\s+sequenceDiagram\b", text, flags=re.I):
            warnings.append({"source": "system_sequence_diagram", "message": "design document must include a Mermaid system sequence diagram"})
    if not re.search(r"`[^`]+\.json`", text):
        warnings.append({"source": "evidence_refs", "message": "machine artifact JSON evidence references not found"})
    if any(phrase in lower for phrase in GENERIC_PHRASES):
        warnings.append({"source": "generic_phrase", "message": "generic or placeholder phrasing detected"})
    generic_hits = sum(lower.count(phrase) for phrase in GENERIC_PHRASES)
    if generic_hits >= 4:
        warnings.append({"source": "placeholder_density", "message": "document contains many placeholder phrases; likely lacks delivery-specific depth"})
    unresolved = unresolved_review(text, lower)
    if unresolved["missing_context"]:
        warnings.append({
            "source": "unresolved_without_context",
            "message": "unresolved confirmation items lack reason/action/evidence context",
            "examples": unresolved["missing_context"],
        })
    if unresolved["ratio"] >= 0.12:
        warnings.append({
            "source": "unresolved_density",
            "message": "unresolved confirmation items are too dense for a review-ready human document",
            "count": unresolved["count"],
            "ratio": round(unresolved["ratio"], 3),
        })
    bullet_count = len(re.findall(r"(?m)^- ", text))
    heading_count = len(re.findall(r"(?m)^#{1,3} ", text))
    if bullet_count >= 8 and len(text.strip()) < 1800:
        warnings.append({"source": "bullet_depth", "message": "many bullets but little explanatory content; add review rationale and impact analysis"})
    for area, terms in DEPTH_TERMS.items():
        if area in required_sources and not has_any(text, lower, terms):
            warnings.append({"source": area, "message": f"{area} depth signal not found"})
    if heading_count >= 8 and len(text.strip()) < 1800 and len(text.strip()) / max(heading_count, 1) < 180:
        warnings.append({"source": "section_depth", "message": "sections are very short on average; document may be outline-only"})
    zh_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    if zh_chars >= 80:
        english_hits = [term for term in ENGLISH_TEMPLATE_TERMS if term in lower]
        if english_hits:
            warnings.append({"source": "zh_language_quality", "message": f"Chinese document still contains English template terms: {', '.join(english_hits[:5])}"})
    for pattern in WEAK_ACCEPTANCE_PATTERNS:
        if re.search(pattern, text):
            blockers.append({"source": "weak_acceptance", "message": "weak or placeholder acceptance criteria detected"})
            break
    if doc_type == "design":
        for pattern in DESIGN_TEMPLATE_RESIDUE_PATTERNS:
            if re.search(pattern, text, flags=re.I | re.M):
                blockers.append({"source": "design_template_residue", "message": "design document still contains template residue or generic implementation phrasing", "pattern": pattern})
                break
    for pattern in NON_BUSINESS_CONTRACT_PATTERNS:
        if re.search(pattern, text, flags=re.I):
            blockers.append({"source": "non_business_contract", "message": "configuration/build file is presented as a business contract"})
            break
    if doc_type == "spec" and ("## 可执行需求" in text or "## 验收标准" in text) and len(re.findall(r"`AC-\d+`", text)) <= 1 and len(re.findall(r"(?m)^\d+[.)、]\s*", text)) >= 3:
        blockers.append({"source": "acceptance_coverage", "message": "complex requirement text has too few extracted acceptance criteria"})
    if doc_type == "test" and re.search(r"执行受影响行为|验证预期结果|准备测试数据", text):
        blockers.append({"source": "generic_test_case", "message": "test cases contain generic non-executable steps"})
    if doc_type == "test" and "## 四、测试用例" in text:
        if not any(term in text for term in ["执行路径", "怎么执行", "Execution path", "How to execute"]):
            blockers.append({"source": "test_execution_path", "message": "test cases must include executable UI/API/data/permission paths"})
        if not any(term in text for term in ["断言点", "怎么判定通过", "Assertions", "How to pass"]):
            blockers.append({"source": "test_assertions", "message": "test cases must include concrete assertion points"})
        if not any(term in text for term in ["造数方式", "怎么造数", "Data setup", "How to prepare data"]):
            blockers.append({"source": "test_data_setup", "message": "test cases must explain how test data is prepared"})
    if doc_type == "design":
        option_positions = heading_positions(text, OPTION_EXPLANATION_HEADINGS)
        decision_positions = heading_positions(text, PREMATURE_DECISION_HEADINGS)
        if decision_positions and option_positions and min(decision_positions) < min(option_positions):
            blockers.append({"source": "decision_order", "message": "decision appears before candidate options are explained"})
        if any(re.search(pattern, text, flags=re.I) for pattern in OPTION_COUNT_FIXED_PATTERNS) and "动态" not in text and "dynamic" not in lower:
            warnings.append({"source": "fixed_option_count", "message": "document suggests fixed option count instead of demand-driven option generation"})
        problem_text = extract_section_text(text, "现状问题")
        goal_text = extract_section_text(text, "设计目标")
        if problem_text and goal_text and similarity_ratio(problem_text, goal_text) > 0.78:
            warnings.append({"source": "problem_goal_similarity", "message": "current problem and design goal sections appear overly similar"})
        acceptance_section = extract_section_text(text, "测试策略摘要") or extract_section_text(text, "Test Strategy Summary")
        if acceptance_section:
            generic_assertions = len(re.findall(r"页面展示、接口参数、返回字段和数据落库均满足该验收|UI, API params, response fields, and persistence satisfy the AC", acceptance_section, flags=re.I))
            ac_rows = len(re.findall(r"(?m)^\|\s*`?AC-\d+", acceptance_section))
            if generic_assertions or (ac_rows >= 2 and len(set(re.findall(r"(?m)^\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|([^|]+)\|", acceptance_section))) <= 1):
                blockers.append({"source": "acceptance_assertion_depth", "message": "acceptance proof uses repeated or generic assertions instead of concrete pass/fail checks"})
        brk_sections = len(re.findall(r"(?m)^####\s+BRK-\d+", text))
        concrete_api_mentions = len(re.findall(r"`(?:GET|POST|PUT|DELETE|PATCH)\s+[^`]+`", text))
        if brk_sections and concrete_api_mentions < brk_sections:
            blockers.append({"source": "brk_api_binding", "message": "each BRK section should bind to concrete API contracts"})
        if brk_sections:
            frontend_function_hits = len(re.findall(r"涉及函数[:：]|functions:", text, flags=re.I))
            backend_method_hits = len(re.findall(r"涉及方法[:：]|methods:", text, flags=re.I))
            if frontend_function_hits < brk_sections and backend_method_hits < brk_sections:
                warnings.append({"source": "brk_frontend_function_depth", "message": "BRK sections should bind frontend functions/handlers when source evidence is available"})
            if backend_method_hits < brk_sections and frontend_function_hits < brk_sections:
                warnings.append({"source": "brk_backend_method_depth", "message": "BRK sections should bind backend controller/service methods when source evidence is available"})
        option_detail_count = len(re.findall(r"(?m)^####\s+(方案|Option)\s+`", text))
        if "方案决策摘要" in text and option_detail_count == 0:
            blockers.append({"source": "option_depth", "message": "solution section has only a decision summary and no candidate option details"})
        if "候选方案" in text and option_detail_count < 2:
            warnings.append({"source": "option_count_depth", "message": "candidate option section has too few detailed options for a review-ready design"})
    mac_user_root = "/" + "Users/"
    if mac_user_root in text or re.search(r"/home/[^/\s]+|[A-Za-z]:\\\\", text):
        blockers.append({"source": "local_path", "message": "local absolute path detected"})
    if re.search(r"(?i)(password|secret|token)\s*[:=]\s*['\"]?[^'\"\s]+", text):
        blockers.append({"source": "secret", "message": "possible secret detected"})
    strict_blockers = []
    if strict:
        strict_sources = required_sources | {"length", "evidence_refs", "placeholder_density", "bullet_depth", "zh_language_quality", "unresolved_without_context", "unresolved_density"}
        if doc_type == "design":
            strict_sources |= {"business_process_diagram", "system_sequence_diagram"}
        strict_blockers.extend(
            {"source": item.get("source", "warning"), "message": item.get("message", "strict warning promoted to blocker")}
            for item in warnings
            if item.get("source") in strict_sources
        )
    return {
        "schema": "codex-human-doc-review-v1",
        "decision": "block" if blockers or strict_blockers else "warn" if warnings else "pass",
        "doc_type": doc_type,
        "strict": strict,
        "blockers": blockers + strict_blockers,
        "warnings": warnings,
        "unresolved_summary": {
            "count": unresolved["count"],
            "ratio": round(unresolved["ratio"], 3),
            "missing_context_count": len(unresolved["missing_context"]),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Review human-readable document quality")
    parser.add_argument("--file", required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    result = review(Path(args.file), strict=args.strict)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
