from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDIT_PATH = ROOT / "skills/core/edit-readiness-governor/scripts/edit_readiness.py"
GIT_PATH = ROOT / "skills/core/git-worktree-governor/scripts/git_worktree.py"
STATE_PATH = ROOT / "skills/core/delivery-state-governor/scripts/delivery_state.py"

spec = importlib.util.spec_from_file_location("edit_readiness", EDIT_PATH)
edit_readiness = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(edit_readiness)

git_spec = importlib.util.spec_from_file_location("git_worktree", GIT_PATH)
git_worktree = importlib.util.module_from_spec(git_spec)
assert git_spec.loader
git_spec.loader.exec_module(git_worktree)

state_spec = importlib.util.spec_from_file_location("delivery_state", STATE_PATH)
delivery_state = importlib.util.module_from_spec(state_spec)
assert state_spec.loader
state_spec.loader.exec_module(delivery_state)


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=True)


def make_repo(root: Path) -> Path:
    remote = root / "repo.git"
    work = root / "repo"
    run(["git", "init", "--bare", str(remote)], root)
    run(["git", "clone", str(remote), str(work)], root)
    run(["git", "config", "user.email", "test@example.com"], work)
    run(["git", "config", "user.name", "Test User"], work)
    (work / "README.md").write_text("# Test\n", encoding="utf-8")
    run(["git", "add", "README.md"], work)
    run(["git", "commit", "-m", "init"], work)
    run(["git", "branch", "-M", "main"], work)
    run(["git", "push", "-u", "origin", "main"], work)
    return work


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def make_docs_repo(root: Path, doc_id: str) -> Path:
    docs_root = root / "delivery-docs"
    docs_root.mkdir()
    run(["git", "init"], docs_root)
    run(["git", "config", "user.email", "test@example.com"], docs_root)
    run(["git", "config", "user.name", "Test User"], docs_root)
    write_json(docs_root / "indexes" / f"{doc_id}.manifest.json", {"schema": "codex-docs-governor-v1", "doc_id": doc_id})
    run(["git", "add", "."], docs_root)
    run(["git", "commit", "-m", "docs init"], docs_root)
    return docs_root


def ready_standard_args(root: Path, repo: Path) -> Namespace:
    artifacts = root / "artifacts"
    docs_root = make_docs_repo(root, "REQ-1")
    git_result = git_worktree.prepare(repo, "feature/req-1", base_branch="main")
    git_file = artifacts / "git_baseline_evidence.json"
    git_worktree.write_artifact(str(artifacts), git_result)
    delivery_state.init_state("REQ-1", "standard_requirement", artifacts)
    state_file = artifacts / "delivery_state.json"
    for gate in ["spec", "technical_design", "architecture_design", "test_design", "delivery_plan", "docs_quality", "design_review", "freeze", "git"]:
        delivery_state.advance_state(state_file, gate, gate, f"{gate}.json")
    spec_file = artifacts / "spec.json"
    technical = artifacts / "technical_design.json"
    architecture = artifacts / "architecture_design.json"
    test_design = artifacts / "test_design.json"
    plan = artifacts / "delivery_plan.json"
    plan_review = artifacts / "delivery_plan_review.json"
    review = artifacts / "design_review.json"
    quality = artifacts / "docs_quality.json"
    write_json(spec_file, {"schema": "spec"})
    write_json(technical, {"schema": "technical"})
    write_json(architecture, {"schema": "architecture"})
    write_json(test_design, {"schema": "codex-test-design-v1", "decision": "pass", "test_cases": [{"id": "TC-1"}]})
    write_json(plan, {"repo_tasks": [{"role": "modify", "paths": ["src/service.py"]}]})
    write_json(plan_review, {"decision": "pass", "readiness_gate": {"implementation_allowed": True}})
    write_json(review, {"decision": "approved"})
    write_json(quality, {"decision": "pass"})
    return Namespace(
        repo=str(repo),
        doc_id="REQ-1",
        lane="standard_requirement",
        branch="feature/req-1",
        git_evidence=str(git_file),
        docs_root=str(docs_root),
        docs_manifest=str(docs_root / "indexes/REQ-1.manifest.json"),
        delivery_state=str(state_file),
        spec=str(spec_file),
        technical_design=str(technical),
        architecture_design=str(architecture),
        test_design=str(test_design),
        delivery_plan=str(plan),
        delivery_plan_review=str(plan_review),
        design_review=str(review),
        docs_quality=str(quality),
        reproduction="",
        allowed_file=["src/service.py"],
        ttl_minutes=30,
    )


class EditReadinessTests(unittest.TestCase):
    def test_standard_requirement_requires_design_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root)
            git_result = git_worktree.prepare(repo, "feature/req-missing", base_branch="main")
            git_file = root / "artifacts/git_baseline_evidence.json"
            git_worktree.write_artifact(str(root / "artifacts"), git_result)
            args = Namespace(
                repo=str(repo),
                doc_id="REQ-MISSING",
                lane="standard_requirement",
                branch="feature/req-missing",
                git_evidence=str(git_file),
                docs_root=str(make_docs_repo(root, "REQ-MISSING")),
                docs_manifest=str(root / "delivery-docs/indexes/REQ-MISSING.manifest.json"),
                delivery_state="",
                spec="",
                technical_design="",
                architecture_design="",
                test_design="",
                delivery_plan="",
                delivery_plan_review="",
                design_review="",
                docs_quality="",
                reproduction="",
                allowed_file=[],
            )
            result = edit_readiness.assert_readiness(args)
            self.assertEqual(result["decision"], "blocked")
            self.assertTrue(any("missing required design artifact" in item for item in result["blockers"]))

    def test_standard_requirement_requires_delivery_plan_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root)
            args = ready_standard_args(root, repo)
            args.delivery_plan_review = ""
            result = edit_readiness.assert_readiness(args)
            self.assertEqual(result["decision"], "blocked")
            self.assertTrue(any("delivery_plan_review" in item for item in result["blockers"]))

    def test_delivery_plan_review_must_allow_implementation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root)
            args = ready_standard_args(root, repo)
            write_json(Path(args.delivery_plan_review), {"decision": "pass", "readiness_gate": {"implementation_allowed": False}})
            result = edit_readiness.assert_readiness(args)
            self.assertEqual(result["decision"], "blocked")
            self.assertTrue(any("delivery_plan_review does not allow implementation" in item for item in result["blockers"]))

    def test_requires_docs_git_repo_before_editing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root)
            args = ready_standard_args(root, repo)
            plain_docs = root / "plain-docs"
            write_json(plain_docs / "indexes/REQ-1.manifest.json", {"doc_id": "REQ-1"})
            args.docs_root = str(plain_docs)
            args.docs_manifest = str(plain_docs / "indexes/REQ-1.manifest.json")
            result = edit_readiness.assert_readiness(args)
            self.assertEqual(result["decision"], "blocked")
            self.assertTrue(any("docs_root must be a git repository" in item for item in result["blockers"]))

    def test_requires_git_fetch_and_pull_evidence_before_editing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root)
            args = ready_standard_args(root, repo)
            write_json(Path(args.git_evidence), {"decision": "ready", "current_branch": "feature/req-1"})
            result = edit_readiness.assert_readiness(args)
            self.assertEqual(result["decision"], "blocked")
            self.assertTrue(any("fetch evidence is missing" in item for item in result["blockers"]))
            self.assertTrue(any("pull --ff-only evidence is missing" in item for item in result["blockers"]))

    def test_permit_and_verify_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root)
            args = ready_standard_args(root, repo)
            readiness = edit_readiness.assert_readiness(args)
            self.assertEqual(readiness["decision"], "ready")
            permit = edit_readiness.create_permit(args)
            self.assertEqual(permit["schema"], "codex-edit-permit-v1")
            permit_file = root / "permit.json"
            write_json(permit_file, permit)
            verify = edit_readiness.verify_permit(Namespace(
                permit=str(permit_file),
                repo=str(repo),
                doc_id="REQ-1",
                branch="feature/req-1",
                allowed_file=["src/service.py"],
            ))
            self.assertEqual(verify["decision"], "ready")

    def test_verify_blocks_out_of_scope_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root)
            args = ready_standard_args(root, repo)
            permit = edit_readiness.create_permit(args)
            permit_file = root / "permit.json"
            write_json(permit_file, permit)
            verify = edit_readiness.verify_permit(Namespace(
                permit=str(permit_file),
                repo=str(repo),
                doc_id="REQ-1",
                branch="feature/req-1",
                allowed_file=["src/other.py"],
            ))
            self.assertEqual(verify["decision"], "blocked")
            self.assertTrue(any("exceed permit scope" in item for item in verify["blockers"]))


if __name__ == "__main__":
    unittest.main()
