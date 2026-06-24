#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".py",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".sh",
    ".js",
    ".ts",
    ".vue",
    ".java",
}


@dataclass(frozen=True)
class Hit:
    path: str
    line: int
    kind: str
    pattern: str
    excerpt: str


def load_simple_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
    except Exception:
        return load_restricted_yaml(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def load_restricted_yaml(path: Path) -> dict:
    data: dict[str, list[str] | str] = {}
    current: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and ":" in line:
            key, value = line.split(":", 1)
            current = key.strip()
            data[current] = value.strip() or []
            continue
        if current and line.strip().startswith("- "):
            value = line.strip()[2:].strip().strip('"').strip("'")
            existing = data.setdefault(current, [])
            if isinstance(existing, list):
                existing.append(value)
    return data


def iter_files(root: Path, allowed_paths: Iterable[str]) -> Iterable[Path]:
    allowed = tuple(item.rstrip("/") + "/" for item in allowed_paths)
    allowed_files = set()
    if hasattr(iter_files, "allowed_files"):
        allowed_files = getattr(iter_files, "allowed_files")
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel in allowed_files:
            continue
        if any(rel.startswith(prefix) for prefix in allowed):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            yield path


def short_excerpt(line: str, pattern: str) -> str:
    text = line.strip()
    if len(text) <= 180:
        return text
    idx = text.lower().find(pattern.lower())
    if idx < 0:
        return text[:177] + "..."
    start = max(0, idx - 60)
    end = min(len(text), idx + len(pattern) + 60)
    prefix = "..." if start else ""
    suffix = "..." if end < len(text) else ""
    return prefix + text[start:end] + suffix


def scan(root: Path, config: dict) -> list[Hit]:
    blocked_literals = [str(item) for item in config.get("blocked_literals", []) or []]
    blocked_terms = [str(item) for item in config.get("blocked_terms", []) or []]
    blocked_regex = [str(item) for item in config.get("blocked_regex", []) or []]
    allowed_paths = [str(item) for item in config.get("allowed_paths", []) or []]
    setattr(iter_files, "allowed_files", set(str(item) for item in config.get("allowed_files", []) or []))
    regexes = [(pattern, re.compile(pattern)) for pattern in blocked_regex]
    hits: list[Hit] = []
    for path in iter_files(root, allowed_paths):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_no, line in enumerate(text.splitlines(), start=1):
            for literal in blocked_literals:
                if literal and literal in line:
                    hits.append(Hit(rel, line_no, "literal", literal, short_excerpt(line, literal)))
            for term in blocked_terms:
                if term and term.lower() in line.lower():
                    hits.append(Hit(rel, line_no, "term", term, short_excerpt(line, term)))
            for pattern, regex in regexes:
                if regex.search(line):
                    hits.append(Hit(rel, line_no, "regex", pattern, short_excerpt(line, pattern)))
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan repository for private content before open-source release.")
    parser.add_argument("--root", required=True)
    parser.add_argument("--patterns", required=True)
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    patterns = Path(args.patterns).resolve()
    config = load_simple_yaml(patterns)
    hits = scan(root, config)
    payload = {
        "schema": "codex-engineering-skills-privacy-scan-v1",
        "root": str(root),
        "patterns": str(patterns),
        "hit_count": len(hits),
        "decision": "pass" if not hits else "block",
        "hits": [hit.__dict__ for hit in hits],
    }
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not hits else 1


if __name__ == "__main__":
    raise SystemExit(main())
