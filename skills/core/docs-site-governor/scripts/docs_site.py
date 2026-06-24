#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "codex-docs-site-v1"
REQUIRED_DOCS = [
    "docs/getting-started.md",
    "docs/workflow-guide.md",
    "docs/architecture.md",
    "docs/open-source-boundary.md",
    "docs/skill-catalog.md",
    "docs/scenario-guide.md",
    "docs/faq.md",
]


def parse_frontmatter_name(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not text.startswith("---"):
        return path.parent.name
    parts = text.split("---", 2)
    for line in parts[1].splitlines():
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip()
    return path.parent.name


def generate(root: Path) -> dict[str, Any]:
    skills = sorted((root / "skills").glob("*/*/SKILL.md"))
    scenarios = sorted((root / "examples/scenarios").glob("*/requirement.md"))
    docs = root / "docs"
    docs.mkdir(exist_ok=True)
    catalog = ["# Skill Catalog", ""]
    for skill in skills:
        rel = skill.parent.relative_to(root).as_posix()
        catalog.append(f"- `{rel}`: {parse_frontmatter_name(skill)}")
    (docs / "skill-catalog.md").write_text("\n".join(catalog) + "\n", encoding="utf-8")
    guide = ["# Scenario Guide", ""]
    for scenario in scenarios:
        name = scenario.parent.name
        first = scenario.read_text(encoding="utf-8", errors="ignore").splitlines()[0].lstrip("# ").strip()
        guide.append(f"- `{name}`: {first}")
    (docs / "scenario-guide.md").write_text("\n".join(guide) + "\n", encoding="utf-8")
    faq = docs / "faq.md"
    if not faq.exists():
        faq.write_text("# FAQ\n\n## Can this repository include private project skills?\n\nNo. Keep private overlays outside open core.\n\n## Do I need to run every gate for every change?\n\nUse the workflow guide and risk governors to choose the required gates.\n", encoding="utf-8")
    return validate(root)


def markdown_links(text: str) -> list[str]:
    return re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)


def validate(root: Path) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for doc in REQUIRED_DOCS:
        if not (root / doc).exists():
            blockers.append({"source": doc, "message": "required doc is missing"})
    for md in sorted(list((root / "docs").glob("*.md")) + [root / "README.md"]):
        if not md.exists():
            continue
        text = md.read_text(encoding="utf-8", errors="ignore")
        for link in markdown_links(text):
            if link.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = (md.parent / link.split("#", 1)[0]).resolve()
            if link and not target.exists():
                blockers.append({"source": md.relative_to(root).as_posix(), "message": "local Markdown link target missing", "link": link})
    if (root / "docs/skill-catalog.md").exists():
        catalog = (root / "docs/skill-catalog.md").read_text(encoding="utf-8", errors="ignore")
        missing = [skill.parent.relative_to(root).as_posix() for skill in (root / "skills").glob("*/*/SKILL.md") if skill.parent.relative_to(root).as_posix() not in catalog]
        if missing:
            warnings.append({"source": "docs/skill-catalog.md", "message": "some skills are missing from catalog", "count": len(missing)})
    return {
        "schema": SCHEMA,
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "required_docs": REQUIRED_DOCS,
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or validate documentation-site readiness")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for cmd in ["generate", "validate"]:
        p = sub.add_parser(cmd)
        p.add_argument("--root", default=".")
    args = parser.parse_args()
    output = generate(Path(args.root)) if args.cmd == "generate" else validate(Path(args.root))
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
