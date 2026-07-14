#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "codex-requirement-ingestion-v1"
IR_SCHEMA = "codex-requirement-ir-v1"

SECTION_KINDS = {
    "背景": "context", "说明": "context", "当前源码事实": "context",
    "纠偏说明": "correction", "更正说明": "correction",
    "原始需求": "requirements", "需求": "requirements", "需要解决的问题": "requirements",
    "本次目标": "requirements", "目标": "requirements", "可执行需求": "requirements",
    "验收标准": "acceptance", "验收": "acceptance", "acceptance criteria": "acceptance",
    "约束": "constraints", "限制": "constraints",
    "非目标": "out_of_scope", "不在范围": "out_of_scope",
    "只读链路验证范围": "reference", "参考资料": "reference", "参考": "reference",
}


def heading_kind(title: str) -> str:
    normalized = title.strip().lower()
    for name, kind in SECTION_KINDS.items():
        if normalized == name.lower():
            return kind
    return "other"


def list_item(line: str) -> tuple[int, str, str] | None:
    match = re.match(r"^(\s*)(?:(\d+)[.)、]\s+|[-*+]\s+)(.+)$", line)
    if not match:
        return None
    indent = len(match.group(1).replace("\t", "    "))
    marker = "number" if match.group(2) else "bullet"
    return indent, marker, match.group(3).strip()


def parse_markdown_ir(text: str, doc_id: str, source_file: Path) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    heading_stack: list[str] = []
    for line_number, raw in enumerate(text.splitlines(), start=1):
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", raw)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()
            heading_stack = heading_stack[: level - 1]
            heading_stack.append(title)
            if level >= 2:
                current = {
                    "title": title,
                    "kind": heading_kind(title),
                    "heading_path": list(heading_stack),
                    "line_start": line_number,
                    "line_end": line_number,
                    "paragraphs": [],
                    "items": [],
                }
                sections.append(current)
            continue
        if current is None or not raw.strip():
            continue
        current["line_end"] = line_number
        parsed = list_item(raw)
        if parsed:
            indent, marker, value = parsed
            item = {"text": value, "line": line_number, "indent": indent, "marker": marker, "children": []}
            if indent > 0 and current["items"]:
                current["items"][-1]["children"].append(item)
            else:
                current["items"].append(item)
        else:
            current["paragraphs"].append({"text": raw.strip(), "line": line_number})

    executable_kinds = {"requirements", "acceptance"}
    executable_lines: list[str] = []
    for section in sections:
        if section["kind"] not in executable_kinds:
            continue
        executable_lines.extend(item["text"] for item in section["paragraphs"])
        for item in section["items"]:
            executable_lines.append(item["text"])
            executable_lines.extend(child["text"] for child in item["children"])
    return {
        "schema": IR_SCHEMA,
        "doc_id": doc_id,
        "source_file": str(source_file),
        "sections": sections,
        "executable_text": "\n".join(executable_lines),
        "excluded_section_kinds": ["context", "correction", "reference", "out_of_scope"],
    }


def read_source(path: Path) -> tuple[str, str]:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return path.read_text(encoding="utf-8", errors="ignore"), "text"
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return json.dumps(data, ensure_ascii=False, indent=2), "json"
    if suffix == ".pdf":
        return "", "pdf_unextracted"
    return path.read_text(encoding="utf-8", errors="ignore"), "text"


def detect_features(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    return {
        "line_count": len(lines),
        "table_like_lines": [line for line in lines if "|" in line or "\t" in line][:20],
        "image_hints": [line for line in lines if re.search(r"image|screenshot|截图|流程图|页面", line, re.I)][:20],
        "rule_hints": [line for line in lines if re.search(r"must|should|rule|if|when|必须|规则|如果|当", line, re.I)][:50],
        "question_hints": [line for line in lines if "?" in line or "？" in line or "待确认" in line][:50],
    }


def ingest(input_path: Path, doc_id: str, out_dir: Path) -> dict[str, Any]:
    text, source_type = read_source(input_path)
    normalized = text.strip() + ("\n" if text.strip() else "")
    out_dir.mkdir(parents=True, exist_ok=True)
    normalized_path = out_dir / "requirement.normalized.txt"
    normalized_path.write_text(normalized, encoding="utf-8")
    requirement_ir = parse_markdown_ir(normalized, doc_id, input_path)
    requirement_ir_path = out_dir / "requirement_ir.json"
    requirement_ir_path.write_text(json.dumps(requirement_ir, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    blockers = []
    if source_type == "pdf_unextracted":
        blockers.append({"source": "pdf", "message": "PDF text was not extracted; export text or run OCR before spec-governor"})
    if not normalized.strip():
        blockers.append({"source": "content", "message": "normalized requirement text is empty"})
    result = {
        "schema": SCHEMA,
        "doc_id": doc_id,
        "source_file": str(input_path),
        "source_type": source_type,
        "normalized_text": str(normalized_path),
        "requirement_ir": str(requirement_ir_path),
        "features": detect_features(normalized),
        "blockers": blockers,
        "decision": "block" if blockers else "ready",
        "next_action": "Run spec-governor on requirement.normalized.txt." if not blockers else "Provide extractable text before spec-governor.",
    }
    (out_dir / "requirement_ingestion.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest requirement document into normalized text")
    parser.add_argument("--input", required=True)
    parser.add_argument("--doc-id", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    result = ingest(Path(args.input), args.doc_id, Path(args.out_dir))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
