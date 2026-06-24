#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "codex-docs-readability-v1"
README_TERMS = ["Start Here", "Open-Source Maintenance Checks", "Skill Layers", "First Safety Check"]
REQUIRED_DOCS = ["docs/getting-started.md", "docs/workflow-guide.md", "docs/skill-catalog.md", "docs/scenario-guide.md", "docs/faq.md"]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def local_path_detected(text: str) -> bool:
    return "/" + "Users/" in text or re.search(r"/home/[^/\s]+|[A-Za-z]:\\\\", text) is not None


def review(root: Path) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    readme = read(root / "README.md")
    for term in README_TERMS:
        if term not in readme:
            blockers.append({"source": "README.md", "message": f"README missing readability section: {term}"})
    for doc in REQUIRED_DOCS:
        path = root / doc
        text = read(path)
        if not text:
            blockers.append({"source": doc, "message": "required public doc is missing"})
        elif len(text.strip()) < 120:
            warnings.append({"source": doc, "message": "public doc is very short"})
        if local_path_detected(text):
            blockers.append({"source": doc, "message": "local absolute path detected"})
    if local_path_detected(readme):
        blockers.append({"source": "README.md", "message": "local absolute path detected"})
    return {
        "schema": SCHEMA,
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Review open-source documentation readability")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    output = review(Path(args.root))
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
