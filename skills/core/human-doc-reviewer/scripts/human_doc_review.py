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
ENGLISH_TEMPLATE_TERMS = [
    "executive summary",
    "current decision",
    "missing readiness",
    "before implementation",
    "evidence references",
    "requirement clarification",
]
DEPTH_TERMS = {
    "review_focus": ["review focus", "评审重点", "阅读与评审重点"],
    "traceability": ["traceability", "追踪", "追溯"],
    "implementation_boundary": ["implementation boundary", "edit constraint", "实施边界", "实现约束", "允许修改文件"],
}


def infer_doc_type(path: Path, text: str) -> str:
    normalized = path.as_posix().lower()
    heading_lines = "\n".join(line for line in text.splitlines()[:12] if line.lstrip().startswith("#")).lower()
    if "/human/designs/" in normalized or re.search(r"(^|/)(designs?|architectures?)(/|$)", normalized):
        return "design"
    if "/human/releases/" in normalized or re.search(r"(^|/)(releases?)(/|$)", normalized):
        return "release"
    if "/human/specs/" in normalized or re.search(r"(^|/)(specs?|requirements?)(/|$)", normalized):
        return "spec"
    if "技术设计" in heading_lines or re.search(r"\b(design|architecture)\b", heading_lines):
        return "design"
    if "发布准备" in heading_lines or re.search(r"\b(release)\b", heading_lines):
        return "release"
    if "需求说明" in heading_lines or re.search(r"\b(spec|requirement)\b", heading_lines):
        return "spec"
    return "general"


def has_any(text: str, lower: str, terms: list[str]) -> bool:
    return any(term in lower or term in text for term in terms)


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
    if not re.search(r"`[^`]+\.json`", text):
        warnings.append({"source": "evidence_refs", "message": "machine artifact JSON evidence references not found"})
    if any(phrase in lower for phrase in GENERIC_PHRASES):
        warnings.append({"source": "generic_phrase", "message": "generic or placeholder phrasing detected"})
    generic_hits = sum(lower.count(phrase) for phrase in GENERIC_PHRASES)
    if generic_hits >= 4:
        warnings.append({"source": "placeholder_density", "message": "document contains many placeholder phrases; likely lacks delivery-specific depth"})
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
    mac_user_root = "/" + "Users/"
    if mac_user_root in text or re.search(r"/home/[^/\s]+|[A-Za-z]:\\\\", text):
        blockers.append({"source": "local_path", "message": "local absolute path detected"})
    if re.search(r"(?i)(password|secret|token)\s*[:=]\s*['\"]?[^'\"\s]+", text):
        blockers.append({"source": "secret", "message": "possible secret detected"})
    strict_blockers = []
    if strict:
        strict_sources = required_sources | {"length", "evidence_refs", "placeholder_density", "bullet_depth", "zh_language_quality"}
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
