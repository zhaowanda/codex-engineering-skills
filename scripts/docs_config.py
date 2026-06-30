#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONFIG_NAME = ".codex-engineering-docs.json"


def config_path(root: Path) -> Path:
    return root / CONFIG_NAME


def load(root: Path) -> dict[str, Any]:
    path = config_path(root)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def save(root: Path, docs_root: Path, git_url: str = "") -> dict[str, Any]:
    data = {
        "schema": "codex-docs-workspace-config-v1",
        "docs_root": str(docs_root.expanduser().resolve()),
        "git_url": git_url,
        "rule": "Configure once per workspace; individual deliveries reuse this docs repository by doc_id.",
    }
    config_path(root).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def configured_docs_root(root: Path) -> Path | None:
    data = load(root)
    value = str(data.get("docs_root") or "")
    return Path(value) if value else None
