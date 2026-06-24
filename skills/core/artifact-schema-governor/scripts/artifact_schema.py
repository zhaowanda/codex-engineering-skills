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
        gate_like = any(term in rel for term in GATE_TERMS)
        if not schemas and gate_like:
            blockers.append({"source": rel, "message": "gate-like script has no schema literal"})
        elif not schemas:
            warnings.append({"source": rel, "message": "script has no schema literal"})
        for schema in schemas:
            seen.setdefault(schema, []).append(rel)
        artifacts.append({"script": rel, "schemas": schemas, "gate_like": gate_like})
    for schema, owners in seen.items():
        if len(owners) > 1 and not schema.endswith("-validation-v1"):
            warnings.append({"source": schema, "message": "schema appears in multiple scripts", "owners": owners})
    return {
        "schema": SCHEMA,
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "script_count": len(scripts),
        "schema_count": len(seen),
        "artifacts": artifacts,
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
