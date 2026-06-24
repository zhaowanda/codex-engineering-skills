from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


sync_local = load_module("sync_local_skills", ROOT / "scripts/sync_local_skills.py")


def write_skill(path: Path, name: str) -> None:
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text(f"---\nname: {name}\ndescription: test\n---\n\n# {name}\n", encoding="utf-8")


def test_sync_links_open_repo_and_preserves_private_overlay() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo = root / "repo"
        skills_root = root / "codex" / "skills"
        write_skill(repo / "skills/core/git-worktree-governor", "git-worktree-governor")
        write_skill(repo / "skills/core/new-open-skill", "new-open-skill")
        write_skill(repo / "skills/templates/design-doc-templates", "design-doc-templates")
        write_skill(skills_root / "company/git-worktree-governor", "git-worktree-governor")
        write_skill(skills_root / "company/private-project", "private-project")

        plan = sync_local.sync(repo, skills_root, dry_run=True, force=True)
        assert plan["decision"] == "plan"
        assert plan["action_count"] == 3

        result = sync_local.sync(repo, skills_root, dry_run=False, force=True)
        assert result["decision"] == "pass"
        assert (skills_root / "company/git-worktree-governor").is_symlink()
        assert (skills_root / "open-core/new-open-skill").is_symlink()
        assert (skills_root / "open-core-templates/design-doc-templates").is_symlink()
        assert (skills_root / "company/private-project/SKILL.md").exists()
        assert (skills_root / ".backup").exists()


def run_all() -> None:
    test_sync_links_open_repo_and_preserves_private_overlay()


if __name__ == "__main__":
    run_all()
    print("PASS local_skill_sync tests")
