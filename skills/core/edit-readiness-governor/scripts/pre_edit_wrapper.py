#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


EDIT_READINESS = Path(__file__).with_name("edit_readiness.py")
SCHEMA = "codex-pre-edit-wrapper-v1"


def run_json(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, text=True, capture_output=True)
    parsed: Any = {}
    if proc.stdout.strip():
        try:
            parsed = json.loads(proc.stdout)
        except Exception:
            parsed = {}
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "json": parsed if isinstance(parsed, dict) else {},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a command only after edit permit verification passes")
    parser.add_argument("--permit", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--doc-id", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--allowed-file", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to execute after -- separator")
    args = parser.parse_args()

    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print(json.dumps({"decision": "blocked", "blockers": ["missing command after --"]}, ensure_ascii=False, indent=2))
        return 1

    verify_cmd = [
        sys.executable,
        str(EDIT_READINESS),
        "verify-permit",
        "--permit",
        args.permit,
        "--repo",
        args.repo,
        "--doc-id",
        args.doc_id,
        "--branch",
        args.branch,
        *[part for item in args.allowed_file for part in ["--allowed-file", item]],
    ]
    verify = run_json(verify_cmd)
    verification = verify["json"]
    if verification.get("decision") != "ready":
        print(json.dumps({
            "schema": SCHEMA,
            "decision": "blocked",
            "permit_verification": verification,
            "stderr": verify["stderr"],
            "blockers": verification.get("blockers", []) or ["permit verification failed"],
        }, ensure_ascii=False, indent=2))
        return 1

    if args.dry_run:
        print(json.dumps({
            "schema": SCHEMA,
            "decision": "ready",
            "dry_run": True,
            "permit_verification": verification,
            "command": command,
        }, ensure_ascii=False, indent=2))
        return 0

    proc = subprocess.run(command, text=True)
    print(json.dumps({
        "schema": SCHEMA,
        "decision": "executed" if proc.returncode == 0 else "command_failed",
        "permit_verification": verification,
        "command": command,
        "returncode": proc.returncode,
    }, ensure_ascii=False, indent=2))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
