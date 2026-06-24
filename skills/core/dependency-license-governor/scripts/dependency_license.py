#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "codex-dependency-license-v1"
MANIFESTS = ["pyproject.toml", "requirements.txt", "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock"]
HIGH_RISK_LICENSES = ["gpl", "agpl", "lgpl", "sspl", "commons clause", "unknown"]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def project_license(root: Path) -> str:
    text = read(root / "pyproject.toml")
    match = re.search(r"license\s*=\s*\{\s*text\s*=\s*['\"]([^'\"]+)['\"]", text)
    if match:
        return match.group(1)
    match = re.search(r"(?m)^license\s*=\s*['\"]([^'\"]+)['\"]", text)
    return match.group(1) if match else ""


def review(root: Path) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    manifests = [name for name in MANIFESTS if (root / name).exists()]
    license_file = root / "LICENSE"
    license_text = read(license_file).lower()
    metadata_license = project_license(root)
    if not license_file.exists():
        blockers.append({"source": "LICENSE", "message": "LICENSE file is required for open-source release"})
    if not metadata_license:
        warnings.append({"source": "pyproject.toml", "message": "project license metadata is recommended"})
    if not manifests:
        warnings.append({"source": "dependency_manifests", "message": "no dependency manifest found"})
    combined = "\n".join(read(root / name).lower() for name in manifests) + "\n" + license_text + "\n" + metadata_license.lower()
    hits = sorted({item for item in HIGH_RISK_LICENSES if item in combined and item not in {"lgpl"} or item == "lgpl" and "lgpl" in combined})
    for hit in hits:
        severity = "block" if hit in {"agpl", "sspl", "commons clause"} else "warn"
        item = {"source": "license_signal", "message": "license signal requires review", "license": hit}
        if severity == "block":
            blockers.append(item)
        else:
            warnings.append(item)
    return {
        "schema": SCHEMA,
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "license_file": license_file.exists(),
        "project_license": metadata_license,
        "dependency_manifests": manifests,
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Review dependency and license readiness")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    output = review(Path(args.root))
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
