from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "skills/core/git-worktree-governor/scripts/git_worktree.py"
spec = importlib.util.spec_from_file_location("git_worktree", MODULE_PATH)
git_worktree = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(git_worktree)


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=True)


def make_repo(root: Path, name: str = "repo") -> tuple[Path, Path]:
    remote = root / f"{name}.git"
    work = root / name
    run(["git", "init", "--bare", str(remote)], root)
    run(["git", "clone", str(remote), str(work)], root)
    run(["git", "config", "user.email", "test@example.com"], work)
    run(["git", "config", "user.name", "Test User"], work)
    (work / "README.md").write_text("# Test\n", encoding="utf-8")
    run(["git", "add", "README.md"], work)
    run(["git", "commit", "-m", "init"], work)
    run(["git", "branch", "-M", "main"], work)
    run(["git", "push", "-u", "origin", "main"], work)
    return remote, work


class GitWorktreeTests(unittest.TestCase):
    def test_prepare_blocks_dirty_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, repo = make_repo(Path(tmp))
            (repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")
            result = git_worktree.prepare(repo, "feature/dirty", base_branch="main")
            self.assertEqual(result["decision"], "blocked")
            self.assertIn("worktree is not clean", result["blockers"])

    def test_prepare_creates_feature_branch_and_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifact_dir = Path(tmp) / "artifacts"
            _, repo = make_repo(Path(tmp))
            result = git_worktree.prepare(repo, "feature/req-1", base_branch="main")
            git_worktree.write_artifact(str(artifact_dir), result)
            self.assertEqual(result["decision"], "ready")
            self.assertTrue(result["created_branch"])
            self.assertEqual(result["current_branch"], "feature/req-1")
            evidence = json.loads((artifact_dir / "git_baseline_evidence.json").read_text(encoding="utf-8"))
            self.assertEqual(evidence["schema"], "codex-git-baseline-evidence-v1")

    def test_prepare_reuses_existing_feature_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, repo = make_repo(Path(tmp))
            first = git_worktree.prepare(repo, "feature/req-1", base_branch="main")
            run(["git", "checkout", "main"], repo)

            second = git_worktree.prepare(repo, "feature/req-1", base_branch="main")

            self.assertEqual(first["decision"], "ready")
            self.assertEqual(second["decision"], "ready")
            self.assertFalse(second["created_branch"])
            self.assertTrue(second["reused_branch"])
            self.assertEqual(second["current_branch"], "feature/req-1")

    def test_assert_ready_blocks_default_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, repo = make_repo(Path(tmp))
            result = git_worktree.assert_ready(repo, base_branch="main")
            self.assertEqual(result["decision"], "blocked")
            self.assertIn("current branch is default branch; editing is not allowed", result["blockers"])

    def test_assert_ready_passes_with_ready_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifact_dir = Path(tmp) / "artifacts"
            _, repo = make_repo(Path(tmp))
            prepared = git_worktree.prepare(repo, "feature/req-2", base_branch="main")
            git_worktree.write_artifact(str(artifact_dir), prepared)
            result = git_worktree.assert_ready(
                repo,
                branch="feature/req-2",
                evidence_file=str(artifact_dir / "git_baseline_evidence.json"),
                base_branch="main",
            )
            self.assertEqual(result["decision"], "ready")

    def test_prepare_plan_only_prepares_modify_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, repo_a = make_repo(root, "repo-a")
            _, repo_b = make_repo(root, "repo-b")
            plan = {
                "repo_tasks": [
                    {"repo": "repo-a", "repo_path": str(repo_a), "role": "modify", "base_branch": "main"},
                    {"repo": "repo-b", "repo_path": str(repo_b), "role": "read_only", "base_branch": "main"},
                ]
            }
            plan_file = root / "delivery_plan.json"
            plan_file.write_text(json.dumps(plan), encoding="utf-8")
            artifact_dir = root / "artifacts"
            result = git_worktree.prepare_plan(str(plan_file), "feature", "REQ-PLAN", str(artifact_dir))
            self.assertEqual(result["decision"], "ready")
            self.assertEqual(result["modify_repo_count"], 1)
            self.assertTrue((artifact_dir / "repo-a-git_baseline_evidence.json").exists())
            self.assertFalse((artifact_dir / "repo-b-git_baseline_evidence.json").exists())

    def test_prepare_plan_uses_registered_checkout_instead_of_staging_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, repo = make_repo(root, "registered-service")
            staging = root / "_staging" / "registered-service"
            staging.mkdir(parents=True)
            plan = {
                "repo_tasks": [
                    {
                        "repo": "registered-service",
                        "repo_path": str(staging),
                        "role": "modify",
                    }
                ]
            }
            plan_file = root / "delivery_plan.json"
            plan_file.write_text(json.dumps(plan), encoding="utf-8")
            codex_home = root / ".codex"
            registry = codex_home / "skills" / "company" / "projects.yaml"
            registry.parent.mkdir(parents=True)
            registry.write_text(
                "\n".join(
                    [
                        'schema: "codex-project-registry-v1"',
                        "projects:",
                        '  - name: "registered-service"',
                        '    default_branch: "main"',
                        "    repo:",
                        f'      local_path_hint: "{repo}"',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            artifact_dir = root / "artifacts"
            old_codex_home = os.environ.get("CODEX_HOME")
            os.environ["CODEX_HOME"] = str(codex_home)
            try:
                result = git_worktree.prepare_plan(str(plan_file), "feature", "REQ-STAGING", str(artifact_dir), check_only=True)
            finally:
                if old_codex_home is None:
                    os.environ.pop("CODEX_HOME", None)
                else:
                    os.environ["CODEX_HOME"] = old_codex_home

            self.assertEqual(result["decision"], "ready")
            evidence = result["results"][0]
            self.assertEqual(evidence["resolved_repo_path"], str(repo.resolve()))
            self.assertNotIn("_staging", evidence["resolved_repo_path"])
            self.assertTrue(any("using registered checkout" in warning for warning in result["warnings"]))

    def test_direct_prepare_blocks_staging_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            staging_root = Path(tmp) / "_staging"
            staging_root.mkdir()
            _, repo = make_repo(staging_root, "repo")
            result = git_worktree.prepare(repo, "feature/req-staging", base_branch="main")
            self.assertEqual(result["decision"], "blocked")
            self.assertTrue(any("repo path points to _staging" in item for item in result["blockers"]))


if __name__ == "__main__":
    unittest.main()
