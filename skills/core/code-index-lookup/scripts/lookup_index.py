#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def score_file(file: dict[str, Any], terms: list[str]) -> int:
    haystack = json.dumps(file, ensure_ascii=False).lower()
    score = 0
    for term in terms:
        if term in haystack:
            score += 10
        if term in str(file.get("path", "")).lower():
            score += 20
        if any(term in str(symbol).lower() for symbol in file.get("symbols", [])):
            score += 25
        if any(term in str(route).lower() for route in file.get("routes", [])):
            score += 30
    return score


def lookup(index: dict[str, Any], query: str, limit: int = 10) -> dict[str, Any]:
    terms = [term.lower() for term in query.replace("/", " ").replace("_", " ").split() if term.strip()]
    matches = []
    for file in index.get("files", []):
        if not isinstance(file, dict):
            continue
        score = score_file(file, terms)
        if score:
            matches.append({"score": score, "path": file.get("path"), "symbols": file.get("symbols", [])[:10], "routes": file.get("routes", [])[:10]})
    matches.sort(key=lambda item: item["score"], reverse=True)
    return {
        "schema": "codex-code-index-lookup-v1",
        "project": index.get("project"),
        "query": query,
        "matches": matches[:limit],
        "next_action": "Read top matched files before broad search." if matches else "No index hits; use targeted source search.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Lookup compact code index")
    parser.add_argument("--index", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    result = lookup(load_json(Path(args.index)), args.query, args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["matches"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
