#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-prompt-pack-v1"
REQUIRED_TERMS = ["artifact", "boundary", "evidence", "stop"]
PRIVATE_MARKERS = ["/" + "Users/", "customer", "internal hostname"]


def prompt_files(root: Path) -> list[Path]:
    return sorted((root / "prompts").glob("*.md"))


def validate(root: Path) -> dict[str, Any]:
    files = prompt_files(root)
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    prompts: list[dict[str, Any]] = []
    if not files:
        blockers.append({"source": "prompts", "message": "prompt pack files are required"})
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        lower = text.lower()
        missing = [term for term in REQUIRED_TERMS if term not in lower]
        private_hits = [marker for marker in PRIVATE_MARKERS if marker.lower() in lower]
        if missing:
            blockers.append({"source": path.name, "message": "prompt missing required control terms", "missing": missing})
        if private_hits:
            blockers.append({"source": path.name, "message": "prompt contains private marker", "markers": private_hits})
        if "scenario:" not in lower:
            warnings.append({"source": path.name, "message": "prompt should include Scenario line"})
        prompts.append({"file": path.name, "title": first_heading(text), "chars": len(text)})
    return {
        "schema": SCHEMA,
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "prompt_count": len(files),
        "prompts": prompts,
        "blockers": blockers,
        "warnings": warnings,
    }


def first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="List or validate reusable prompt packs")
    parser.add_argument("--root", default=".")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    output = validate(Path(args.root))
    if args.list:
        print(json.dumps({"schema": SCHEMA, "prompt_count": output["prompt_count"], "prompts": output["prompts"]}, ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
