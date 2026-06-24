#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path


def run(root: Path) -> dict:
    cases = []
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run(
            ["python3", "skills/templates/synthetic-e2e-runner/scripts/run_synthetic_e2e.py", "--out-dir", tmp],
            cwd=root,
            text=True,
            capture_output=True,
        )
        data = {}
        try:
            data = json.loads(proc.stdout)
        except Exception:
            pass
        cases.append({
            "case": "synthetic-e2e",
            "returncode": proc.returncode,
            "schema": data.get("schema"),
            "decision": data.get("decision"),
            "passed": proc.returncode == 0 and data.get("schema") == "codex-synthetic-e2e-run-v1" and data.get("decision") == "pass",
        })
    blockers = [{"source": item["case"], "message": "forward test failed"} for item in cases if not item["passed"]]
    return {
        "schema": "codex-forward-test-run-v1",
        "decision": "block" if blockers else "pass",
        "cases": cases,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run forward tests")
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    result = run(Path(args.root))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
