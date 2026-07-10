#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "codex-artifact-schema-inventory-v1"
SCHEMA_RE = re.compile(r"codex-[a-z0-9-]+-v\d+")
GATE_TERMS = ["governor", "gate", "review", "runner", "binder", "analyzer"]
GATE_SCRIPT_TERMS = ["governor", "gate", "review", "runner", "binder", "analyzer"]
def schema_name(stem: str) -> str:
    return "codex-" + stem + "-v1"


ALLOWED_DUPLICATE_SCHEMAS = {
    schema_name("architecture-design"): "generator and template intentionally share the same artifact contract",
    schema_name("architecture-framing"): "generator and design template intentionally share the same pre-technical framing contract",
    schema_name("delivery-replay-skeleton"): "case capture and example runner intentionally share replay skeleton fixtures",
    schema_name("delivery-plan"): "delivery plan reviewer validates the generated delivery plan contract",
    schema_name("delivery-runner-status"): "synthetic runner asserts delivery-runner blocking behavior",
    schema_name("edit-permit"): "write guard validates permits emitted by edit readiness",
    schema_name("post-change-implementation-report"): "post-change sync and synthetic runner intentionally share the implementation report contract",
    schema_name("project-registry"): "framework validation and project onboarding share registry contract",
    schema_name("synthetic-e2e-run"): "forward runner reports the synthetic runner contract",
    schema_name("test-data-plan"): "test data governor and synthetic runner intentionally share the test data plan contract",
    schema_name("technical-design"): "generator and template intentionally share the same artifact contract",
}

ALLOWED_SCHEMALESS_HELPERS = {
    "skills/core/docs-governor/scripts/doc_model.py": "language-neutral document model helper; emits no standalone JSON artifact",
    "skills/core/docs-governor/scripts/docs_i18n.py": "i18n rendering helper; emits no standalone JSON artifact",
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def literal_schemas(text: str) -> list[str]:
    return sorted(set(SCHEMA_RE.findall(text)))


def assigned_schemas(text: str) -> list[str]:
    schemas: set[str] = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.upper().endswith("SCHEMA"):
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        schemas.add(node.value.value)
    return sorted(schemas)


def skill_frontmatter(script: Path, root: Path) -> dict[str, str]:
    try:
        rel_parts = script.relative_to(root).parts
    except ValueError:
        return {}
    if len(rel_parts) < 5 or rel_parts[0] != "skills" or rel_parts[3] != "scripts":
        return {}
    skill_md = root.joinpath(*rel_parts[:3], "SKILL.md")
    if not skill_md.exists():
        return {}
    text = read(skill_md)
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    frontmatter: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = value.strip().strip('"').strip("'")
    return frontmatter


def is_gate_like_script(script: Path, root: Path) -> bool:
    fm = skill_frontmatter(script, root)
    if fm.get("gate") == "true" or fm.get("maturity") in {"expert-gate", "advisory-review"}:
        return True
    return any(term in script.stem for term in GATE_SCRIPT_TERMS)


def inventory(root: Path) -> dict[str, Any]:
    scripts = sorted((root / "skills").glob("**/scripts/*.py"))
    artifacts: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen: dict[str, list[str]] = {}
    for script in scripts:
        text = read(script)
        rel = script.relative_to(root).as_posix()
        schemas = sorted(set(literal_schemas(text) + assigned_schemas(text)))
        gate_like = is_gate_like_script(script, root)
        if not schemas and rel in ALLOWED_SCHEMALESS_HELPERS:
            artifacts.append({"script": rel, "schemas": schemas, "gate_like": gate_like, "schema_waiver": ALLOWED_SCHEMALESS_HELPERS[rel]})
            continue
        if not schemas and gate_like:
            blockers.append({"source": rel, "message": "gate-like script has no schema literal"})
        elif not schemas:
            warnings.append({"source": rel, "message": "script has no schema literal"})
        for schema in schemas:
            seen.setdefault(schema, []).append(rel)
        artifacts.append({"script": rel, "schemas": schemas, "gate_like": gate_like})
    allowed_duplicates: list[dict[str, Any]] = []
    for schema, owners in seen.items():
        if len(owners) > 1 and schema in ALLOWED_DUPLICATE_SCHEMAS:
            allowed_duplicates.append({"schema": schema, "reason": ALLOWED_DUPLICATE_SCHEMAS[schema], "owners": owners})
        elif len(owners) > 1 and not schema.endswith("-validation-v1"):
            warnings.append({"source": schema, "message": "schema appears in multiple scripts", "owners": owners})
    return {
        "schema": SCHEMA,
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "script_count": len(scripts),
        "schema_count": len(seen),
        "artifacts": artifacts,
        "allowed_duplicate_schemas": allowed_duplicates,
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory artifact schemas emitted by skill scripts")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    output = inventory(Path(args.root))
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
