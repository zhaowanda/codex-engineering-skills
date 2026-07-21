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

INSTALL_SCRIPT = ROOT / "skills/core/workspace-write-guard/scripts/install_pre_commit.py"
install_spec = importlib.util.spec_from_file_location("install_write_guard_hooks", INSTALL_SCRIPT)
install_write_guard_hooks = importlib.util.module_from_spec(install_spec)
assert install_spec.loader
install_spec.loader.exec_module(install_write_guard_hooks)


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
    def test_hook_installer_adds_pre_commit_and_pre_push(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = init_repo(Path(tmp))

            result = install_write_guard_hooks.install(repo)

            self.assertEqual(result["status"], "installed")
            pre_commit = repo / ".git/hooks/pre-commit"
            pre_push = repo / ".git/hooks/pre-push"
            self.assertTrue(pre_commit.exists())
            self.assertTrue(pre_push.exists())
            self.assertIn("CODEX_EDIT_PERMIT", pre_commit.read_text(encoding="utf-8"))
            self.assertIn("CODEX_ARTIFACT_DIR", pre_push.read_text(encoding="utf-8"))
            self.assertIn("--checkpoint pre_push", pre_push.read_text(encoding="utf-8"))
            self.assertIn("Agent Runtime script not found", pre_push.read_text(encoding="utf-8"))
            self.assertTrue(all(Path(path).is_file() for path in [install_write_guard_hooks.HARNESS, install_write_guard_hooks.AGENT_RUNTIME]))

    def test_hook_installer_repairs_legacy_missing_pre_push_path_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = init_repo(Path(tmp))
            hooks = repo / ".git/hooks"
            pre_push = hooks / "pre-push"
            pre_push.write_text(
                '#!/usr/bin/env bash\nexec "/missing/company/post-change-skill-sync/scripts/pre-push"\n',
                encoding="utf-8",
            )

            result = install_write_guard_hooks.install(repo, hook_names={"pre-push"})

            self.assertEqual(result["status"], "repaired")
            self.assertEqual(result["repaired"], [str(pre_push.resolve())])
            self.assertEqual(len(result["backups"]), 1)
            self.assertTrue(Path(result["backups"][0]).exists())
            self.assertFalse((hooks / "pre-commit").exists())
            content = pre_push.read_text(encoding="utf-8")
            self.assertNotIn("post-change-skill-sync/scripts/pre-push", content)
            self.assertIn(str(install_write_guard_hooks.HARNESS), content)

    def test_hook_installer_preserves_existing_non_codex_hook_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = init_repo(Path(tmp))
            pre_push = repo / ".git/hooks/pre-push"
            pre_push.write_text("#!/bin/sh\necho custom\n", encoding="utf-8")

            result = install_write_guard_hooks.install(repo, hook_names={"pre-push"})

            self.assertEqual(result["status"], "skipped")
            self.assertEqual(pre_push.read_text(encoding="utf-8"), "#!/bin/sh\necho custom\n")

    def test_pre_push_hook_resolves_artifact_dir_from_branch_and_docs_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = init_repo(root)
            run(["git", "checkout", "-B", "feature/REQ-123-hook"], repo)
            artifact_dir = root / "company-delivery-docs" / "deliveries" / "REQ-123-hook" / "artifacts"
            artifact_dir.mkdir(parents=True)
            runtime = root / "runtime_stub.py"
            runtime.write_text(
                "import sys\nfrom pathlib import Path\nargs=sys.argv\nPath(args[args.index('--artifact-dir')+1], 'runtime').mkdir(parents=True, exist_ok=True)\n",
                encoding="utf-8",
            )
            harness = root / "harness_stub.py"
            harness.write_text(
                "import json, sys\nfrom pathlib import Path\nout=Path(sys.argv[sys.argv.index('--out')+1]); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps({'decision':'pass'}))\n",
                encoding="utf-8",
            )

            result = install_write_guard_hooks.install(repo, hook_names={"pre-push"})
            self.assertEqual(result["status"], "installed")
            env = os.environ.copy()
            env.pop("CODEX_ARTIFACT_DIR", None)
            env["CODEX_AGENT_RUNTIME_SCRIPT"] = str(runtime)
            env["CODEX_HARNESS_SCRIPT"] = str(harness)
            proc = subprocess.run([str(repo / ".git/hooks/pre-push")], cwd=repo, env=env, text=True, capture_output=True)

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((artifact_dir / "harness/pre_push.json").exists())

    def test_pre_push_hook_resolves_unique_docs_slug_when_branch_date_drifted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = init_repo(root)
            run(["git", "checkout", "-B", "feature/REQ-20260720-feishu-approval-capability"], repo)
            artifact_dir = root / "company-delivery-docs" / "deliveries" / "REQ-20260717-feishu-approval-capability" / "artifacts"
            artifact_dir.mkdir(parents=True)
            runtime = root / "runtime_stub.py"
            runtime.write_text(
                "import sys\nfrom pathlib import Path\nargs=sys.argv\nPath(args[args.index('--artifact-dir')+1], 'runtime').mkdir(parents=True, exist_ok=True)\n",
                encoding="utf-8",
            )
            harness = root / "harness_stub.py"
            harness.write_text(
                "import json, sys\nfrom pathlib import Path\nout=Path(sys.argv[sys.argv.index('--out')+1]); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps({'decision':'pass'}))\n",
                encoding="utf-8",
            )

            result = install_write_guard_hooks.install(repo, hook_names={"pre-push"})
            self.assertEqual(result["status"], "installed")
            env = os.environ.copy()
            env.pop("CODEX_ARTIFACT_DIR", None)
            env["CODEX_AGENT_RUNTIME_SCRIPT"] = str(runtime)
            env["CODEX_HARNESS_SCRIPT"] = str(harness)
            proc = subprocess.run([str(repo / ".git/hooks/pre-push")], cwd=repo, env=env, text=True, capture_output=True)

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((artifact_dir / "harness/pre_push.json").exists())

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

    def test_staging_repo_or_permit_blocks_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            staging_root = Path(tmp) / "_staging"
            staging_root.mkdir()
            repo = init_repo(staging_root)
            permit_path = repo / ".codex" / "permit.json"
            snapshot_path = repo / ".codex" / "snapshot.json"
            write_json(permit_path, permit(repo, ["allowed.txt"]))
            snap = write_guard.create_snapshot(Namespace(repo=str(repo), permit=str(permit_path), doc_id="", require_clean=False, out=str(snapshot_path)))
            self.assertEqual(snap["decision"], "blocked")
            self.assertTrue(any("_staging" in item for item in snap["blockers"]))

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
