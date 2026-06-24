from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from argparse import Namespace
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/core/workspace-write-guard/scripts/write_guard.py"
spec = importlib.util.spec_from_file_location("write_guard", SCRIPT)
write_guard = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(write_guard)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=True)


def init_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.email", "guard@example.com"], repo)
    run(["git", "config", "user.name", "Guard Test"], repo)
    (repo / "allowed.txt").write_text("base\n", encoding="utf-8")
    (repo / "blocked.txt").write_text("base\n", encoding="utf-8")
    run(["git", "add", "."], repo)
    run(["git", "commit", "-m", "init"], repo)
    run(["git", "checkout", "-b", "feature/guard-test"], repo)
    return repo


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def permit(repo: Path, allowed: list[str], issued_offset_seconds: int = -60) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "schema": "codex-edit-permit-v1",
        "permit_id": "EDIT-TEST",
        "decision": "ready",
        "repo": str(repo.resolve()),
        "doc_id": "REQ-guard-test",
        "lane": "bugfix",
        "branch": "feature/guard-test",
        "allowed_files": allowed,
        "issued_at": iso(now + timedelta(seconds=issued_offset_seconds)),
        "expires_at": iso(now + timedelta(minutes=30)),
    }


class WorkspaceWriteGuardTests(unittest.TestCase):
    def test_allowed_change_passes_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = init_repo(Path(tmp))
            permit_path = repo / ".codex" / "permit.json"
            snapshot_path = repo / ".codex" / "snapshot.json"
            audit_path = repo / ".codex" / "audit.json"
            write_json(permit_path, permit(repo, ["allowed.txt"]))
            snap = write_guard.create_snapshot(Namespace(repo=str(repo), permit=str(permit_path), doc_id="", require_clean=False, out=str(snapshot_path)))
            self.assertEqual(snap["decision"], "ready")
            (repo / "allowed.txt").write_text("base\nchange\n", encoding="utf-8")
            audit = write_guard.audit(Namespace(repo=str(repo), permit=str(permit_path), snapshot=str(snapshot_path), doc_id="", out=str(audit_path)))
            self.assertEqual(audit["decision"], "ready")

    def test_out_of_scope_change_blocks_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = init_repo(Path(tmp))
            permit_path = repo / ".codex" / "permit.json"
            snapshot_path = repo / ".codex" / "snapshot.json"
            write_json(permit_path, permit(repo, ["allowed.txt"]))
            write_guard.create_snapshot(Namespace(repo=str(repo), permit=str(permit_path), doc_id="", require_clean=False, out=str(snapshot_path)))
            (repo / "blocked.txt").write_text("base\nchange\n", encoding="utf-8")
            audit = write_guard.audit(Namespace(repo=str(repo), permit=str(permit_path), snapshot=str(snapshot_path), doc_id="", out=""))
            self.assertEqual(audit["decision"], "blocked")
            self.assertIn("blocked.txt", audit["unauthorized_files"])

    def test_pre_authorization_mtime_blocks_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = init_repo(Path(tmp))
            permit_path = repo / ".codex" / "permit.json"
            snapshot_path = repo / ".codex" / "snapshot.json"
            (repo / "allowed.txt").write_text("base\nold-change\n", encoding="utf-8")
            old_ts = datetime.now(timezone.utc) - timedelta(hours=2)
            os.utime(repo / "allowed.txt", (old_ts.timestamp(), old_ts.timestamp()))
            write_json(permit_path, permit(repo, ["allowed.txt"], issued_offset_seconds=0))
            write_guard.create_snapshot(Namespace(repo=str(repo), permit=str(permit_path), doc_id="", require_clean=False, out=str(snapshot_path)))
            audit = write_guard.audit(Namespace(repo=str(repo), permit=str(permit_path), snapshot=str(snapshot_path), doc_id="", out=""))
            self.assertEqual(audit["decision"], "blocked")
            self.assertIn("allowed.txt", audit["pre_authorization_mtime_files"])


if __name__ == "__main__":
    unittest.main()
