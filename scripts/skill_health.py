#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/core/skill-health/scripts/skill_health.py"


def load_main():
    spec = importlib.util.spec_from_file_location("skill_health_impl", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load skill health implementation: {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main


if __name__ == "__main__":
    raise SystemExit(load_main()())
