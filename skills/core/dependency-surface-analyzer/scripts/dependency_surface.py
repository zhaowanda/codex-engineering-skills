#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "codex-dependency-surface-v1"
FILES = {
    "pyproject.toml": ("python", "pyproject"),
    "requirements.txt": ("python", "pip"),
    "package.json": ("node", "npm"),
    "pom.xml": ("java", "maven"),
    "build.gradle": ("java", "gradle"),
    "go.mod": ("go", "go"),
    "Cargo.toml": ("rust", "cargo"),
}


def extract_package_json(path: Path) -> tuple[list[str], list[str], list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return [], [], []
    deps = sorted(list((data.get("dependencies") or {}).keys()) + list((data.get("devDependencies") or {}).keys()))
    scripts = data.get("scripts") or {}
    build = [f"npm run {name}" for name in scripts if "build" in name]
    tests = [f"npm run {name}" for name in scripts if "test" in name]
    return deps, build, tests


def analyze(repo: Path, project: str) -> dict[str, Any]:
    if not repo.exists() or not repo.is_dir():
        return {
            "schema": SCHEMA,
            "project": project,
            "decision": "block",
            "confidence": "low",
            "confidence_details": [{"dimension": "repo", "score": 0, "reason": "repo path is missing or not a directory"}],
            "ecosystems": [],
            "manifests": [],
            "build_command_hints": [],
            "test_command_hints": [],
            "blockers": [{"source": "repo", "message": "repo path is missing or not a directory"}],
            "warnings": [],
        }
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    manifests: list[dict[str, Any]] = []
    ecosystems: set[str] = set()
    build_hints: list[str] = []
    test_hints: list[str] = []
    for name, (ecosystem, manager) in FILES.items():
        path = repo / name
        if not path.exists():
            continue
        ecosystems.add(ecosystem)
        deps: list[str] = []
        if name == "package.json":
            deps, builds, tests = extract_package_json(path)
            build_hints.extend(builds)
            test_hints.extend(tests)
        else:
            text = path.read_text(encoding="utf-8", errors="ignore")
            deps = sorted(set(re.findall(r"^[A-Za-z0-9_.-]+", text, re.M)))[:100]
        manifests.append({"path": name, "ecosystem": ecosystem, "manager": manager, "dependency_hints": deps[:100]})
    if "python" in ecosystems:
        test_hints.append("pytest")
    if "node" in ecosystems and not test_hints:
        test_hints.append("npm test")
    if not manifests:
        warnings.append({"source": "dependency_surface", "message": "no dependency manifests detected"})
    return {
        "schema": SCHEMA,
        "project": project,
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "confidence": "high" if manifests else "low",
        "confidence_details": [
            {"dimension": "manifests", "score": min(100, len(manifests) * 35), "reason": f"{len(manifests)} dependency manifests detected"},
            {"dimension": "ecosystems", "score": min(100, len(ecosystems) * 50), "reason": f"{len(ecosystems)} ecosystems detected"},
            {"dimension": "test_commands", "score": 100 if test_hints else 0, "reason": "test command hints detected" if test_hints else "no test command hints detected"},
        ],
        "ecosystems": sorted(ecosystems),
        "manifests": manifests,
        "build_command_hints": sorted(set(build_hints)),
        "test_command_hints": sorted(set(test_hints)),
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze dependency surface")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = analyze(Path(args.repo), args.project)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
